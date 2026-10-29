import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

D4 = TR.ink_map(jobs[4][1])
br4 = TR.refined_branches(D4)
ch4, W0_4 = C.build_chains(br4)
print("=== icon_4 (Winch) chains ===")
for i, c in enumerate(ch4):
    pts = c["pts"]
    print(f"  ch {i:2d}: len={len(pts):3d}, p0={pts[0].round(1).tolist()} -> mid={pts[len(pts)//2].round(1).tolist()} -> p1={pts[-1].round(1).tolist()}")
