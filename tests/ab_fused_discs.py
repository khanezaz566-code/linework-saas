"""A/B: fused-disc handling on vs off, on every drawer where a fused disc is detected."""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("OMP_NUM_THREADS", "1")
from concurrent.futures import ProcessPoolExecutor
import cv2, numpy as np


def job(args):
    idx, jq, off = args
    from tests.diag_join_problems import make
    from linework.pipeline import process_icon, Options
    if off:
        os.environ["DISABLE_FUSED_DISCS"] = "1"
    else:
        os.environ.pop("DISABLE_FUSED_DISCS", None)
    img, name = make(idx, jq or None)
    r = process_icon(img, Options(fresh=True, memory=False, quality="standard", joins=True, decision=True), name=name)
    m = r["metrics"]
    iss = m["issues"]
    return dict(idx=idx, name=name, off=off, iou=round(m["iou"] * 100, 2), gaps=iss["gaps"], notches=iss["notches"], spurs=iss["spurs"],
                kinks=iss["kinks"], regions=iss["regions"], paths=m["paths"], joins_unres=len(m["joins"]["unresolved"]))


if __name__ == "__main__":
    from tests.diag_join_problems import ALL
    from linework.trace import ink_map, find_fused_discs
    from linework.split import estimate_width
    from tests.diag_join_problems import make
    jq = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    hits = []
    for i in range(len(ALL)):
        img, _ = make(i, jq or None)
        D = ink_map(img)
        if find_fused_discs(D, estimate_width(D)):
            hits.append(i)
    hits = hits[:limit]
    if len(sys.argv) > 3:
        only = set(sys.argv[3].split(","))
        hits = [i for i in hits if ALL[i].__name__ in only]
    print("tested drawers:", [ALL[i].__name__ for i in hits], flush=True)
    tasks = [(i, jq, off) for i in hits for off in (False, True)]
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(job, tasks))
    by = {}
    for r in res:
        by.setdefault(r["idx"], {})[r["off"]] = r
    better = worse = same = 0
    for i in hits:
        on, off = by[i][False], by[i][True]
        d = on["iou"] - off["iou"]
        tag = "BETTER" if d > 0.15 else ("WORSE " if d < -0.15 else "same  ")
        better += tag == "BETTER"; worse += tag == "WORSE "; same += tag == "same  "
        print(f"{tag} {on['name']:<30} iou on={on['iou']:6.2f} off={off['iou']:6.2f}  gaps {on['gaps']}/{off['gaps']}  notch {on['notches']}/{off['notches']}  spurs {on['spurs']}/{off['spurs']}  regions {on['regions']}/{off['regions']}  paths {on['paths']}/{off['paths']}")
    print(f"better={better} worse={worse} same={same}  mean on={np.mean([by[i][False]['iou'] for i in hits]):.2f} off={np.mean([by[i][True]['iou'] for i in hits]):.2f}")
    Path("tests/ab_fused.json").write_text(json.dumps(res, indent=1))
