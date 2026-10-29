import json, cv2, numpy as np
from pathlib import Path

brain_dir = Path(r'C:\Users\USER\.gemini\antigravity\brain\970fe8ba-3395-424d-a702-a938d367e356\.user_uploaded')

# Compare each uploaded image with all icon crops
names = [
    'media_1793018607536_5c1de092.png',
    'media_1793018609932_2072e533.png',
    'media_1793018612798_1ff26844.png',
    'media_1793018619657_c79ec548.png',
    'media_1793018622949_43eb2c9a.png'
]

for name in names:
    img = cv2.imread(str(brain_dir / name))
    h, w = img.shape[:2]
    # mask out red lines: red lines have R > 150, G < 50, B < 50
    is_red = (img[:, :, 2] > 150) & (img[:, :, 1] < 60) & (img[:, :, 0] < 60)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray[is_red] = 255
    # threshold
    bin_u = (gray < 128).astype(np.uint8)
    
    # compare with each icon crop
    best_iou = 0
    best_k = -1
    for k in range(12):
        crop = cv2.imread(f'scratch/icon_crop_{k}.png', 0)
        bin_c = (crop < 128).astype(np.uint8)
        # resize bin_u to bin_c shape
        r_u = cv2.resize(bin_u, (bin_c.shape[1], bin_c.shape[0]), interpolation=cv2.INTER_NEAREST)
        iou = (r_u & bin_c).sum() / max((r_u | bin_c).sum(), 1)
        if iou > best_iou:
            best_iou = iou
            best_k = k
    print(f"{name} -> Icon {best_k} with IoU={best_iou:.3f}")
