import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.geom import corners, linefit, line_inter, unit

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)
p = np.asarray(chains[0]['pts'], float)
w = chains[0]['w']
r = w / 2

cs = corners(p, win=7, ang=35)
print(f"Total corners in chain 0: {len(cs)}")
for i in cs:
    if 700 <= i <= 760:
        print(f"Corner at {i}: {p[i]}")
        k = int(round(r * 1.1))
        a, b = i - k, i + k
        m = (p[i - 7] + p[i + 7]) / 2
        u = p[i] - m
        nu = np.linalg.norm(u)
        u = u / nu if nu > 1e-6 else np.zeros(2)
        # Check angle of base curve
        vin = unit(p[i] - p[a])
        vout = unit(p[b] - p[i])
        base_cos = float(vin @ vout)
        print(f"  base_cos: {base_cos:.3f} (ang: {np.degrees(np.arccos(np.clip(base_cos, -1, 1))):.1f} deg)")
