import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.geom import fit_curve
from linework.model import Path, Model
from linework.doctor import Doctor, ink_of

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)
p = np.asarray(chains[0]['pts'], float)
w = chains[0]['w']

# What does fit_curve(p, 0.8, 0.3) produce on the whole chain?
segs = fit_curve(p, 0.8, 0.3)
print(f"Direct fit_curve segs: {len(segs)}")
path = Path.from_segs(segs, w)
m = Model([path], crop.shape[1], crop.shape[0])
doc = Doctor(D)
iou = doc.iou(ink_of(m))
print(f"Direct fit_curve IoU: {iou*100:.2f}%")

# Check reversals on direct fit_curve
reversals = []
for idx in range(len(path.A) - 2):
    v1 = path.A[idx+1] - path.A[idx]
    v2 = path.A[idx+2] - path.A[idx+1]
    l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if l1 > 0.5 and l2 > 0.5:
        cos = np.clip((v1 / l1) @ (v2 / l2), -1, 1)
        deg = np.degrees(np.arccos(cos))
        if deg > 90:
            reversals.append((deg, path.A[idx+1]))
print(f"Direct fit reversals > 90 deg: {len(reversals)}")
for deg, pt in reversals:
    print(f"  {deg:.1f} deg at {pt}")
