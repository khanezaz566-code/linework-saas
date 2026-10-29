import cv2, numpy as np

crop = cv2.imread('scratch/icon_crop_2.png', 0)
# Region [200:330, 80:110]
region = crop[200:330, 80:110]
ink = (region < 128).astype(int)
print("Raster in Icon 2 slat area [200:330, 80:110]:")
for y in range(0, ink.shape[0], 6):
    line = "".join("#" if ink[y, x] else "." for x in range(0, ink.shape[1], 2))
    print(f"{200+y:3d}: {line}")
