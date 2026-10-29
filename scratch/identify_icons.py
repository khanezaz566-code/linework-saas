import json, os, glob
import cv2
import numpy as np

# Let's inspect the original images of all icons in 225b51e61676, 4d5d81238877, 0a2b06637601
# We want to identify the icon names (e.g. YouTube, Twitter, Instagram, etc.)
for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    orig = cv2.imread(f'data/{jid}/original.png')
    with open(f'data/{jid}/job.json') as f:
        job = json.load(f)
    print(f"\n=== Job {jid} ===")
    for ic in job['icons']:
        k = ic['k']
        box = ic['box']
        crop = orig[box[1]:box[3], box[0]:box[2]]
        # Find if crop contains a V shape or junction
        print(f"Icon {k}: box={box}, size={crop.shape}")
