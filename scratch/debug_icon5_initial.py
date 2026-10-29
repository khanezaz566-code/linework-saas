import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D_sm = T.ink_map(small)

br = T.refined_branches(D_sm)
chains, W0 = CH.build_chains(br)
print(f"Chains: {len(chains)}, W0={W0:.2f}")
for i, c in enumerate(chains):
    pts = c["pts"]
    print(f"  Chain {i}: len={len(pts)} start={pts[0].round(1)} end={pts[-1].round(1)} w={c['w']:.2f}")

mod = FIT.initial_model(chains, D_sm, sigma=opts.sigma * 1.0 * 0.6, err=0.3)
print(f"\nInitial model: {len(mod.paths)} paths")
for i, p in enumerate(mod.paths):
    print(f"  Path {i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
    for ki in range(len(p.A)):
        print(f"     node {ki}: A={p.A[ki].round(2)} Hin={p.Hin[ki].round(2)} Hout={p.Hout[ki].round(2)}")
