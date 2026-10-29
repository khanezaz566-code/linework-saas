import cv2, numpy as np
crop = cv2.imread('scratch/icon_crop_9.png', 0)
# Look at y=271, x=330..355
y = 271
print("Source ink in crop 9 at y=271, x=330..355:")
for x in range(330, 356):
    val = crop[y, x]
    print(f"x={x:3d}: val={val:3d} {'#' if val < 128 else '.'}")
