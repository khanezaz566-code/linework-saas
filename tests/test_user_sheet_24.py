import cv2, numpy as np, time
from linework.pipeline import process_sheet, process_icon, Options
from linework.doctor import Doctor, ink_of

sheet_path = r"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/media_1794413526422_b2a535be.png"
img = cv2.imread(sheet_path, cv2.IMREAD_GRAYSCALE)

opts = Options(fresh=True, memory=False, quality='standard', joins=True, decision=True)
W, H, jobs = process_sheet(img, opts)
print(f"Sheet size: {W}x{H}, Icons found: {len(jobs)}")

ious = []
svgs = []
t0 = time.time()
for k, crop, off in jobs:
    t_start = time.time()
    res = process_icon(crop, opts, name=f"sheet_icon_{k:02d}")
    m = res["model"]
    iou = float(res.get("metrics", {}).get("iou", 0.0))
    ious.append(iou)
    svgs.append(m.svg())
    dt = time.time() - t_start
    print(f"Icon {k:02d}: {crop.shape[1]}x{crop.shape[0]} at ({off[0]},{off[1]}), paths={len(m.paths)}, IoU={iou*100:.2f}%, time={dt:.2f}s")

elapsed = time.time() - t0
print(f"\n==========================================")
print(f"Total icons: {len(jobs)}")
print(f"Average IoU: {np.mean(ious)*100:.2f}%")
print(f"Min IoU: {np.min(ious)*100:.2f}% (Icon {np.argmin(ious)})")
print(f"Max IoU: {np.max(ious)*100:.2f}% (Icon {np.argmax(ious)})")
print(f"Icons >= 98%: {sum(iou >= 0.98 for iou in ious)} / {len(jobs)}")
print(f"Total time: {elapsed:.2f}s ({elapsed/len(jobs):.2f}s per icon)")
print(f"==========================================")
