import json, os
import cv2
import numpy as np

jid = '225b51e61676'
jpath = f'data/{jid}/job.json'
with open(jpath) as f:
    job = json.load(f)

print(job['name'])
for ic in job['icons']:
    print(f"k={ic['k']} box={ic['box']} iou={ic.get('iou')}")
