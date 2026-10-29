import json, os
import cv2

jid = '225b51e61676'
orig = cv2.imread(f'data/{jid}/original.png')
with open(f'data/{jid}/job.json') as f:
    job = json.load(f)

os.makedirs('scratch/crops_225', exist_ok=True)
for ic in job['icons']:
    k = ic['k']
    x0, y0, x1, y1 = ic['box']
    crop = orig[y0:y1, x0:x1]
    cv2.imwrite(f'scratch/crops_225/icon_{k}.png', crop)

print("Saved crops to scratch/crops_225")
