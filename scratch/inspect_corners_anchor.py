import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.geom import corners

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)

p = np.asarray(chains[0]['pts'], float)
cs = corners(p, win=7, ang=35)
print(f"Corners count: {len(cs)}")
for c_idx in cs:
    pt = p[c_idx]
    if 290 <= pt[0] <= 340 and 315 <= pt[1] <= 340:
        print(f"Corner at index {c_idx}: pt={pt}")
