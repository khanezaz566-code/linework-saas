import sys, os, json
sys.path.insert(0, os.getcwd())
import numpy as np
from linework import joints as JN, finisher as FN
from linework.model import Model

for idx in range(9):
    ipath = f"data/ea3cb3bb04a7/icon_{idx}.json"
    with open(ipath, "r", encoding="utf-8") as f:
        raw = f.read()
    m = Model.from_json(raw)
    js = JN.find_joints(m)
    print(f"=== ea3cb3bb04a7 icon_{idx} (w~{m.paths[0].w:.1f}, paths={len(m.paths)}) ===")
    for J in js:
        if J.kind in ("T", "Y"):
            for (i, e) in J.ends:
                end = JN._end_pt(m.paths[i], e)
                others = [j for j in J.through if j != i] or J.through
                if others:
                    dmin = min(JN._nearest_on(m.paths[j], end)[1] for j in others)
                    if dmin > 0.25:
                        print(f"  J({J.kind}) xy={J.xy.round(1)} end=({i},{e}) pt={end.round(1)} through={others} dmin={dmin:.2f}")
        elif J.kind == "L":
            pts = np.array([JN._end_pt(m.paths[i], e) for i, e in J.ends])
            dmax = float(np.linalg.norm(pts - pts.mean(0), axis=1).max())
            if dmax > 0.25:
                print(f"  J(L) xy={J.xy.round(1)} ends={J.ends} dmax={dmax:.2f}")
