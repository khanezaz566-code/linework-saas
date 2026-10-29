import json, os, glob
import cv2
import numpy as np

# Let's inspect 4d5d81238877
jid = '4d5d81238877'
orig = cv2.imread(f'data/{jid}/original.png')
with open(f'data/{jid}/job.json') as f:
    job = json.load(f)

os.makedirs('scratch/crops_4d5', exist_ok=True)
for ic in job['icons']:
    k = ic['k']
    x0, y0, x1, y1 = ic['box']
    crop = orig[y0:y1, x0:x1]
    cv2.imwrite(f'scratch/crops_4d5/icon_{k}.png', crop)

# Let's check icon 0, 1 SVGs
for k in [0, 1, 7]:
    svg_p = f'data/{jid}/icon_{k}.svg'
    if os.path.exists(svg_p):
        print(f"=== {jid} icon {k} ===")
        with open(svg_p) as f:
            print(f.read())
