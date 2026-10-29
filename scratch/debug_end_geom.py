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

print(f"Path 0 length={p0.length():.1f}, w={p0.w:.1f}")
g0_0 = FN.end_geometry(p0, 0)
g0_1 = FN.end_geometry(p0, 1)
print(f"Path 0 end 0 geom: {g0_0}")
print(f"Path 0 end 1 geom: {g0_1}")
if g0_1 is not None:
    print(f"Path 0 end 1 straight_before_end: {FN._straight_before_end(p0, 1, g0_1[1])}")

print(f"\nPath 4 length={p4.length():.1f}, w={p4.w:.1f}")
g4_0 = FN.end_geometry(p4, 0)
g4_1 = FN.end_geometry(p4, 1)
print(f"Path 4 end 0 geom: {g4_0}")
print(f"Path 4 end 1 geom: {g4_1}")
if g4_1 is not None:
    print(f"Path 4 end 1 straight_before_end: {FN._straight_before_end(p4, 1, g4_1[1])}")

print("\nFN.end_hooks on initial_model:")
print(FN.end_hooks(mod))
