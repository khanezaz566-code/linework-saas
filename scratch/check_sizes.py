import cv2, numpy as np

for k in range(12):
    im = cv2.imread(f'scratch/icon_crop_{k}.png', 0)
    # Check ink percentage and dimensions
    ink_pct = (im < 128).mean() * 100
    print(f"Icon {k}: {im.shape[1]}x{im.shape[0]} px, ink: {ink_pct:.1f}%")
