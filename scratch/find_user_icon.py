import json, os, glob
import cv2
import numpy as np

for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    jpath = f'data/{jid}/job.json'
    if not os.path.exists(jpath): continue
    with open(jpath) as f:
        job = json.load(f)
    print(f"=== Job {jid}: {job.get('name')} ===")
    for ic in job.get('icons', []):
        k = ic.get('k')
        met = ic.get('metrics', {})
        print(f"  icon {k}: box={ic.get('box')} paths={met.get('paths')} iou={ic.get('iou')}")
