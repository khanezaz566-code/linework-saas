import sys, os, json
sys.path.insert(0, os.getcwd())
import numpy as np
from linework import joints as JN, finisher as FN, topology as T
from linework.model import Model

for idx in range(9):
    ipath = f"data/ea3cb3bb04a7/icon_local_{idx}.json"
    with open(ipath, "r", encoding="utf-8") as f:
        m = Model.from_json(f.read())
    print(f"=== ea3cb3bb04a7 icon_local_{idx}: {m.width}x{m.height}, paths={len(m.paths)} ===")
    for pi, p in enumerate(m.paths):
        segs = p.segs()
        short = [(si, round(float(np.linalg.norm(c[3]-c[0])), 2)) for si, c in enumerate(segs) if np.linalg.norm(c[3]-c[0]) < 0.9 * p.w]
        if short or len(p.A) >= 4:
            print(f"  path {pi}: w={p.w:.1f}, closed={p.closed}, nA={len(p.A)}, A0={p.A[0].round(1)}, A-1={p.A[-1].round(1)}, short_segs={short}")
