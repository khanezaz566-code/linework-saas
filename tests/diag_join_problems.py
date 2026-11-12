"""Diagnose why joins are sometimes bad: run join-heavy icons under realistic inputs
(clean / JPEG-degraded) and report join + finisher + topology stats per icon."""
from __future__ import annotations
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import cv2, numpy as np
from linework.pipeline import process_icon, Options
from tests.make_heavy_joins_sheet import HEAVY_JOIN_DRAWERS
from tests.more_complex_drawers import MORE_COMPLEX_DRAWERS

ALL = HEAVY_JOIN_DRAWERS + MORE_COMPLEX_DRAWERS


import os
SCALE = float(os.environ.get("DIAG_SCALE", "1"))


def make(idx, jpeg_q=None, sw=6):
    d = ALL[idx % len(ALL)]
    c = np.full((200, 200), 255, np.uint8)
    d(c, 100, 100, sw=sw, seed=idx * 7 + 13)
    if SCALE != 1:  # emulate a 1-2K export: same artwork, much thicker strokes
        c = cv2.resize(c, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    if jpeg_q:
        ok, buf = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, jpeg_q])
        c = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    return c, d.__name__


def run(args):
    idx, jq = args
    img, name = make(idx, jq)
    t = time.time()
    r = process_icon(img, Options(fresh=True, memory=False, quality="standard", joins=True, decision=True), name=f"{name}")
    m = r["metrics"]
    j = m["joins"]
    return dict(idx=idx, name=name, jpeg=jq, iou=round(m["iou"] * 100, 2), sec=round(time.time() - t, 1),
                issues=m["issues"], fin=m["finisher"]["found"], fin_fixed=m["finisher"]["fixed"],
                joins_total=j["total"], joins_clean=j["clean_first"], joins_built=j["built"],
                joins_unres=len(j["unresolved"]), unres=[str(u)[:90] for u in j["unresolved"][:3]],
                struct_unres=len(m["structure"]["unresolved"]))


if __name__ == "__main__":
    jq = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "0" else None
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    Pool = ThreadPoolExecutor if (len(sys.argv) > 3 and sys.argv[3] == "thread") else ProcessPoolExecutor
    with Pool(4) as ex:
        res = list(ex.map(run, [(i, jq) for i in range(n)]))
    for r in res:
        print(json.dumps(r))
    bad = [r for r in res if r["joins_unres"] or r["issues"]["gaps"] or r["issues"]["notches"] or r["issues"]["spurs"]]
    print(f"\n{len(bad)}/{len(res)} icons with join/topology leftovers; mean IoU {np.mean([r['iou'] for r in res]):.2f}")
    Path(f"tests/diag_join_{jq}.json").write_text(json.dumps(res, indent=1))

