import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[1]
D = ink_map(crop)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
for pi, p in enumerate(m0.paths):
    if 115 <= p.A[:, 1].min() <= 195 and 115 <= p.A[:, 0].mean() <= 355:
        print(f"m0[{pi}]: len={p.length():.1f}, A={np.round(p.A, 1).tolist()}")
