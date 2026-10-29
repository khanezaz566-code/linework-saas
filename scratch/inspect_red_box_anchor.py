import cv2, numpy as np

img = cv2.imread(r'C:\Users\USER\.gemini\antigravity\brain\970fe8ba-3395-424d-a702-a938d367e356\.user_uploaded\media_1793018609932_2072e533.png')
# Find the red box coordinates
is_red = (img[:, :, 2] > 180) & (img[:, :, 1] < 50) & (img[:, :, 0] < 50)
ys, xs = np.nonzero(is_red)
x0, x1 = xs.min(), xs.max()
y0, y1 = ys.min(), ys.max()
print(f"Red box bounds: x=[{x0}, {x1}], y=[{y0}, {y1}]")

# Crop the red box and slightly around it
crop = img[max(0, y0-20):min(img.shape[0], y1+20), max(0, x0-20):min(img.shape[1], x1+20)]
cv2.imwrite('scratch/anchor_red_box.png', crop)

# Also let's print the stroke contour in this red box
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
for y in range(0, crop.shape[0], 2):
    row = "".join("#" if gray[y, x] < 100 else ("R" if is_red[max(0, y0-20)+y, max(0, x0-20)+x] else ".") for x in range(0, crop.shape[1], 2))
    print(row)
