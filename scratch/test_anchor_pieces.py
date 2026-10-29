import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import CornerSolver

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)

solver = CornerSolver(D)
p = np.asarray(chains[0]['pts'], float)
pcs = solver.pieces(p, chains[0]['w'])
print(f"Pieces count: {len(pcs)}")
total_pts = sum(len(q) for _, q in pcs)
print(f"Total points across pieces: {total_pts}")

# Check sharp reversals
all_pts = np.vstack([q if i == 0 else q[1:] for i, (_, q) in enumerate(pcs)])
print(f"All pts shape: {all_pts.shape}")
reversals = []
for idx in range(len(all_pts) - 2):
    v1 = all_pts[idx+1] - all_pts[idx]
    v2 = all_pts[idx+2] - all_pts[idx+1]
    l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if l1 > 0.5 and l2 > 0.5:
        cos = np.clip((v1 / l1) @ (v2 / l2), -1, 1)
        deg = np.degrees(np.arccos(cos))
        if deg > 90:
            reversals.append((deg, all_pts[idx+1]))
print(f"Reversals > 90 deg: {len(reversals)}")
for deg, pt in reversals:
    print(f"  {deg:.1f} deg at {pt}")
