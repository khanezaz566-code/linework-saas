import cv2, numpy as np

for name in ["media_1793256433122_39d58747.png", "media_1793256444054_1461b588.png"]:
    p = f"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/{name}"
    im = cv2.imread(p)
    print(name, "shape:", im.shape)
    # Find red pixels (user markings are usually bright red)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 150, 150), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 150, 150), (180, 255, 255))
    red = mask1 | mask2
    pts = np.argwhere(red > 0)
    if len(pts):
        y0, x0 = pts.min(axis=0)
        y1, x1 = pts.max(axis=0)
        print(f"  Red marking bbox: y=[{y0}, {y1}], x=[{x0}, {x1}], center=[{(x0+x1)//2}, {(y0+y1)//2}]")
