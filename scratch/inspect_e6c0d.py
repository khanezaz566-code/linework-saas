import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C, joints as JN
from linework.model import Model

job = json.load(open("data/e6c0d92fb976/job.json"))
for i, ic in enumerate(job.get("icons", [])):
    m = ic.get("metrics", ic)
    print(f"icon_{i:2d}: box={ic.get('box')}, iou={m.get('iou', 0)*100:.2f}%, paths={m.get('paths')}, nodes={m.get('nodes')}, from_mem={m.get('from_memory')}, joins={m.get('joins')}")

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
os.makedirs("scratch/e6c0d_vis", exist_ok=True)
for k, crop, off in jobs:
    mod = Model.from_json(open(f"data/e6c0d92fb976/icon_local_{k}.json").read())
    # Render source crop vs Illustrator outline overlay (blue centerline + red anchor dots on dark background, matching user screenshot!)
    h_c, w_c = crop.shape
    # Left panel: source image
    left = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    # Right panel: dark gray background + black strokes + blue centerline + anchor squares (exact Illustrator preview!)
    right = np.full((h_c, w_c, 3), 90, np.uint8)
    ink_mask = crop < 128
    right[ink_mask] = (15, 15, 15)
    for p in mod.paths:
        f = p.flat(0.5).astype(np.int32)
        cv2.polylines(right, [f], p.closed, (255, 140, 60), 1, cv2.LINE_AA)
        for a in p.A.astype(np.int32):
            cv2.circle(right, tuple(a), 2, (80, 220, 255), -1)
    vis = np.hstack([left, right])
    cv2.imwrite(f"scratch/e6c0d_vis/icon_{k:02d}.png", vis)
print("Saved 12 side-by-side panels to scratch/e6c0d_vis/")
