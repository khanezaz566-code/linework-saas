import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options, _process_icon_scaled
from linework import trace as T
from linework.doctor import Doctor, ink_of

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]

# Let's inspect the actual icon_5.svg and icon_5.json that is saved in data/225b51e61676
with open("data/225b51e61676/icon_5.json") as f:
    saved = json.load(f)

print("Saved icon_5 paths count:", len(saved['paths']))
for i, p in enumerate(saved['paths']):
    A = np.array(p['A'])
    Hin = np.array(p['Hin'])
    Hout = np.array(p['Hout'])
    print(f"Path {i}: closed={p['closed']} len={len(A)}")
    print(f"   A[0]={A[0].round(2)} Hin[0]={Hin[0].round(2)} Hout[0]={Hout[0].round(2)}")
    print(f"   A[-1]={A[-1].round(2)} Hin[-1]={Hin[-1].round(2)} Hout[-1]={Hout[-1].round(2)}")
    if len(A) >= 3:
        print(f"   A[1]={A[1].round(2)} A[-2]={A[-2].round(2)}")
