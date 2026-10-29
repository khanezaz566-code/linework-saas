import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, lessons as LS

LS.clear()
gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
os.makedirs("scratch/e6c0d_vis", exist_ok=True)

target_icons = [0, 2, 4, 11]
for k, crop, off in jobs:
    if k not in target_icons:
        continue
    opts = P.Options(quality="standard", fresh=True, memory=False, time_budget=15.0)
    res = P.process_icon(crop, opts, name=f"icon_{k}")
    mod = res["model"]
    met = res["metrics"]
    print(f"icon_{k:02d}: iou={met['iou']*100:.2f}%, paths={met['paths']}, nodes={met['nodes']}, joins={met.get('joins')}")
    h_c, w_c = crop.shape
    left = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    right = np.full((h_c, w_c, 3), 90, np.uint8)
    ink_mask = crop < 128
    right[ink_mask] = (15, 15, 15)
    for p in mod.paths:
        f = p.flat(0.5).astype(np.int32)
        cv2.polylines(right, [f], p.closed, (255, 140, 60), 1, cv2.LINE_AA)
        for a in p.A.astype(np.int32):
            cv2.circle(right, tuple(a), 2, (80, 220, 255), -1)
    vis = np.hstack([left, right])
    cv2.imwrite(f"scratch/e6c0d_vis/icon_{k:02d}_fixed.png", vis)
print("Done!")
