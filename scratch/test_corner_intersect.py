import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework import finisher as FN
from linework import joints as JN

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

den = JN._cr2(t0, t4)
s0 = JN._cr2(c4 - c0, t4) / den
X = c0 + s0 * t0

print(f"c0={c0.round(2)}, t0={t0.round(2)}")
print(f"c4={c4.round(2)}, t4={t4.round(2)}")
print(f"den={den:.3f}, s0={s0:.2f}")
print(f"Ray intersection X = {X.round(2)}")
print(f"Original p0 end = {p0.A[-1].round(2)}")
print(f"Original p4 end = {p4.A[-1].round(2)}")
print(f"Distance from p0 end to X = {np.linalg.norm(p0.A[-1] - X):.2f} px")
print(f"Distance from p4 end to X = {np.linalg.norm(p4.A[-1] - X):.2f} px")
