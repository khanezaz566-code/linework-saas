import cv2, numpy as np

for name in ["media_1793256433122_39d58747.png", "media_1793256444054_1461b588.png"]:
    p = f"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/{name}"
    im = cv2.imread(p)
    # Check if there is any colored annotation (saturation > 50)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    colored = sat > 80
    if colored.any():
        pts = np.argwhere(colored)
        y0, x0 = pts.min(axis=0)
        y1, x1 = pts.max(axis=0)
        print(f"{name} has annotations: y=[{y0}, {y1}], x=[{x0}, {x1}]")
        # Hue values of annotations
        hues = hsv[colored, 0]
        print(f"  hues mean: {hues.mean():.1f}, min: {hues.min()}, max: {hues.max()}")
    else:
        print(f"{name} is grayscale or low saturation")
