import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C, joints as JN, rings as RG, finisher as FN
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

# 1. Check icon_0 (Propeller) middle ring (r ~ 52)
D0 = TR.ink_map(jobs[0][1])
m0 = Model.from_json(open("data/e6c0d92fb976/icon_local_0.json").read())
p1 = m0.paths[1]
f1 = p1.flat(1.0)
cx, cy, r = RG._kasa(f1)
rad_err = np.abs(np.hypot(f1[:, 0] - cx, f1[:, 1] - cy) - r)
print(f"icon_0 path 1 circle fit: cx={cx:.2f}, cy={cy:.2f}, r={r:.2f}, max_rad_err={rad_err.max():.2f}, mean_rad_err={rad_err.mean():.2f}")

# Why did RG.detect_rings miss r=52.1 on icon_0?
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
sk = skeletonize(D0 > 0.5)
ys, xs = np.nonzero(sk)
P_sk = np.c_[xs, ys].astype(float)
d_sk = np.hypot(P_sk[:, 0] - cx, P_sk[:, 1] - cy)
print("Skeleton points within 3px of r=52.1:", (np.abs(d_sk - r) < 3.0).sum())
e = RG._fit_ellipse_pts(P_sk, cx, cy, r, 10.0)
print("_fit_ellipse_pts at r=52.1:", e)

# 2. Check icon_3 (Compass Rose) sharp tips
D3 = TR.ink_map(jobs[3][1])
br3 = TR.refined_branches(D3)
ch3, W0_3 = C.build_chains(br3)
print(f"\nicon_3 (Compass): branches={len(br3)}, chains={len(ch3)}, W0={W0_3:.2f}")
for i, b in enumerate(br3):
    if b["sj"] == 0 or b["ej"] == 0:
        print(f"  free-tip br {i}: len={len(b['pts'])}, sj={b['sj']}, ej={b['ej']}, p0={b['pts'][0].round(1).tolist()} -> p1={b['pts'][-1].round(1).tolist()}")

# 3. Check icon_4 (Winch) coil tops and bottoms
D4 = TR.ink_map(jobs[4][1])
br4 = TR.refined_branches(D4)
ch4, W0_4 = C.build_chains(br4)
print(f"\nicon_4 (Winch): branches={len(br4)}, chains={len(ch4)}, W0={W0_4:.2f}")
for i, b in enumerate(br4):
    p0, p1 = b["pts"][0], b["pts"][-1]
    if (110 < p0[0] < 320 and (p0[1] < 95 or p0[1] > 220)) or (110 < p1[0] < 320 and (p1[1] < 95 or p1[1] > 220)):
        print(f"  coil br {i:2d}: len={len(b['pts']):3d}, sj={b['sj']:2d}, ej={b['ej']:2d}, p0={p0.round(1).tolist()} -> p1={p1.round(1).tolist()}")
