import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C, joints as JN, rings as RG
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for k in (0, 1, 3, 4):
    crop = jobs[k][1]
    D = TR.ink_map(crop)
    w_est = P.estimate_width(D)
    rings = RG.detect_rings(D, w_est)
    mod = Model.from_json(open(f"data/e6c0d92fb976/icon_local_{k}.json").read())
    print(f"=== icon_{k}: shape={crop.shape}, w_est={w_est:.1f}, detected_rings={len(rings)}, final_paths={len(mod.paths)} ===")
    for r in rings:
        print(f"  ring: cx={r['cx']:.1f}, cy={r['cy']:.1f}, r={r['r']:.1f}, w={r['w']:.1f}, sup={r['support']:.3f}")
    for pi, p in enumerate(mod.paths):
        print(f"  path {pi:2d}: closed={p.closed}, nA={len(p.A):2d}, len={p.length():6.1f}, w={p.w:4.1f}, A0={p.A[0].round(1).tolist()} -> A1={p.A[-1].round(1).tolist()}")
