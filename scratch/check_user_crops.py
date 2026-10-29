import json, os, glob
import cv2
import numpy as np

# Load user images
u1 = cv2.imread("C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/media_1793256433122_39d58747.png")
u2 = cv2.imread("C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/media_1793256444054_1461b588.png")

print(f"User image 1 shape: {u1.shape}")
print(f"User image 2 shape: {u2.shape}")

# Let's inspect the crops in scratch/crops_225
for k in range(10):
    cp = f'scratch/crops_225/icon_{k}.png'
    if os.path.exists(cp):
        c = cv2.imread(cp)
        print(f"Icon {k} shape: {c.shape}")
