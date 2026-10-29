import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework import pipeline as P, chains as C, joints as JN
from linework.trace import ink_map, refined_branches
from scratch.test_cross_v2 import build_chains_v2

# Also keep existing bridge_cands / stair_junc / spurs logic from chains.py alongside multi-pair + micro-bridge clustering!
C.build_chains = build_chains_v2
P.build_chains = build_chains_v2

gray = cv2.imread("data/ea3cb3bb04a7/original.png", cv2.IMREAD_GRAYSCALE)
W, H, jobs = P.process_sheet(gray)
for idx in (4, 5, 6, 7):
    _, crop, off = jobs[idx]
    D = ink_map(crop)
    br = refined_branches(D)
    ch, W0 = build_chains_v2(br)
    r = P.process_icon(crop, P.Options(quality="fast", memory=False), name=f"ea3_{idx}")
    m = r["model"]
    print(f"=== ea3 icon_{idx}: branches={len(br)}, chains={len(ch)}, final_paths={len(m.paths)}, IoU={r['metrics']['iou']*100:.2f}% ===")
    if idx == 4:
        for pi, p in enumerate(m.paths):
            print(f"  path {pi:2d}: w={p.w:4.1f}, closed={p.closed}, nA={len(p.A)}, A0={p.A[0].round(1).tolist()} -> A-1={p.A[-1].round(1).tolist()}")
