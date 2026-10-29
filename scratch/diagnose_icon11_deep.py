import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P
from linework.trace import ink_map, skeleton_branches, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[11]
D = ink_map(crop)
br_raw = skeleton_branches(D, S=2)
br_ref = refined_branches(D, S=2)
chs, W0 = build_chains(br_ref)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)

print(f"=== ICON 11: {len(br_ref)} refined branches, {len(chs)} chains, W0={W0:.2f} ===")
for i, b in enumerate(br_ref):
    pts = b["pts"]
    if ((pts[:, 1] >= 200) & (pts[:, 1] <= 300)).any():
        print(f"  br[{i:2d}]: len={len(pts):3d}, w={b['w']:.2f}, sj={b['sj']:2d}, ej={b['ej']:2d}, p0={np.round(pts[0],1)}, p_mid={np.round(pts[len(pts)//2],1)}, p1={np.round(pts[-1],1)}")

# Save zoomed visual of raw skeleton vs refined_branches vs chains on icon_11
vis_sk = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
for i, b in enumerate(br_raw):
    pts = np.round(b["pts"]).astype(np.int32)
    cv2.polylines(vis_sk, [pts], False, (0, 0, 255), 1, cv2.LINE_AA)

vis_ref = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
for i, b in enumerate(br_ref):
    pts = np.round(b["pts"]).astype(np.int32)
    cv2.polylines(vis_ref, [pts], False, (255, 100, 0), 1, cv2.LINE_AA)
    cv2.circle(vis_ref, tuple(pts[0]), 2, (0, 200, 0), -1)
    cv2.circle(vis_ref, tuple(pts[-1]), 2, (0, 0, 255), -1)

vis_ch = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
for i, ch in enumerate(chs):
    pts = np.round(ch["pts"]).astype(np.int32)
    cv2.polylines(vis_ch, [pts], False, (0, 180, 0), 2, cv2.LINE_AA)
    cv2.circle(vis_ch, tuple(pts[0]), 3, (255, 0, 0), -1)
    cv2.circle(vis_ch, tuple(pts[-1]), 3, (0, 0, 255), -1)

cv2.imwrite("scratch/e6c0d_vis/icon_11_stages.png", np.hstack([vis_sk, vis_ref, vis_ch]))
print("Saved scratch/e6c0d_vis/icon_11_stages.png")
