import cv2, numpy as np

for name in ["media_1793256433122_39d58747.png", "media_1793256444054_1461b588.png"]:
    p = f"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/{name}"
    im = cv2.imread(p)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    blue = (hsv[:, :, 0] >= 105) & (hsv[:, :, 0] <= 125) & (hsv[:, :, 1] > 100)
    # Find connected components of blue
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(blue.astype(np.uint8))
    print(f"\n{name}: {num-1} blue components")
    for k in range(1, num):
        if stats[k, cv2.CC_STAT_AREA] > 30:
            x, y, w, h, area = stats[k]
            cx, cy = centroids[k]
            print(f"  Component {k}: area={area}, bbox=[x={x}, y={y}, w={w}, h={h}], center=({cx:.1f}, {cy:.1f})")
