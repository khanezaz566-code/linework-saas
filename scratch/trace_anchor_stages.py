import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
print(f"Refined branches count: {len(branches)}")
chains, w_est = build_chains(branches, 10.0)
print(f"Chains count: {len(chains)}, w_est={w_est}")
for i, c in enumerate(chains):
    pts = np.asarray(c['pts'])
    print(f"Chain {i}: pts={len(pts)}")
    # find sharp reversals
    for p_idx in range(len(pts) - 2):
        v1 = pts[p_idx+1] - pts[p_idx]
        v2 = pts[p_idx+2] - pts[p_idx+1]
        L1, L2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if L1 > 0.5 and L2 > 0.5:
            cos = np.clip(np.dot(v1, v2) / (L1 * L2), -1, 1)
            deg = np.degrees(np.arccos(cos))
            if deg > 90:
                print(f"  Chain {i} reversal {deg:.1f} deg at pt {p_idx+1}: {pts[p_idx+1]}")
