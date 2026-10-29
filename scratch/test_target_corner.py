import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework import finisher as FN

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D_sm = T.ink_map(small)

br = T.refined_branches(D_sm)
chains, W0 = CH.build_chains(br)
mod = FIT.initial_model(chains, D_sm, sigma=opts.sigma * 1.0 * 0.6, err=0.3)

p0 = mod.paths[0]
p4 = mod.paths[4]

g0 = FN.end_geometry(p0, 1)
g4 = FN.end_geometry(p4, 1)

c0, t0 = g0[0], g0[1]
c4, t4 = g4[0], g4[1]

from linework import joints as JN
den = JN._cr2(t0, t4)
s0 = JN._cr2(c4 - c0, t4) / den
X = c0 + s0 * t0

cand = mod.copy()
c_0 = FN.fix_end(cand, 0, 1, target=X)
if c_0 is not None:
    cand = c_0
c_4 = FN.fix_end(cand, 4, 1, target=X)
if c_4 is not None:
    cand = c_4

print("cand path 0 end:", cand.paths[0].A[-1].round(2))
print("cand path 4 end:", cand.paths[4].A[-1].round(2))
print("GAP:", np.linalg.norm(cand.paths[0].A[-1] - cand.paths[4].A[-1]))

# Now merge corner
merged = FN.merge_corners(cand, [(0, 1, 4, 1)])
print("Merged model paths:", len(merged.paths))
p_merged = merged.paths[0]
print(f"p_merged len={len(p_merged.A)} start={p_merged.A[0].round(2)} end={p_merged.A[-1].round(2)}")
for ki in range(len(p_merged.A)):
    print(f"  node {ki}: A={p_merged.A[ki].round(2)} Hin={p_merged.Hin[ki].round(2)} Hout={p_merged.Hout[ki].round(2)}")
