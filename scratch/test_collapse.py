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

from linework import joints as JN
den = JN._cr2(g0[1], g4[1])
s0 = JN._cr2(g4[0] - g0[0], g4[1]) / den
X = g0[0] + s0 * g0[1]

cand = mod.copy()
cand = FN.fix_end(cand, 0, 1, target=X)
cand = FN.fix_end(cand, 4, 1, target=X)
merged = FN.merge_corners(cand, [(0, 1, 4, 1)])
p_merged = merged.paths[0]

q2, q1 = FN.collapse_straight_runs(p_merged)
print(f"p_merged len: {len(p_merged.A)} -> q1 len: {len(q1.A)}, q2 len: {len(q2.A)}")
for ki in range(len(q2.A)):
    print(f"  q2 node {ki}: A={q2.A[ki].round(2)} Hin={q2.Hin[ki].round(2)} Hout={q2.Hout[ki].round(2)}")
