import cv2, numpy as np

crop = cv2.imread('scratch/icon_crop_5.png', 0)
# Look at region around [300, 325]
# Let's crop [260:380, 290:370]
region = crop[260:380, 290:370]
print(f"Region size: {region.shape}")
cv2.imwrite('scratch/anchor_fluke_raster.png', cv2.resize(region, (320, 480), interpolation=cv2.INTER_NEAREST))
# Check what the ink looks like
ink = (region < 128).astype(int)
print("Ink map in 10x10 blocks or summary:")
for y in range(0, ink.shape[0], 6):
    line = "".join("#" if ink[y, x] else "." for x in range(0, ink.shape[1], 4))
    print(f"{260+y:3d}: {line}")
