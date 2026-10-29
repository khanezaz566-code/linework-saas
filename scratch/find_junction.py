import json, os, glob
import cv2
import numpy as np

# Let's inspect the SVG paths of all icons in 225b51e61676, 4d5d81238877, 0a2b06637601
for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    for f in sorted(glob.glob(f'data/{jid}/icon_local_*.json')):
        with open(f) as fp:
            m = json.load(fp)
        for i, p in enumerate(m.get('paths', [])):
            pts = np.array(p.get('points', []))
            # check if there's a V shape or junction
            pass

print("Searching done")
