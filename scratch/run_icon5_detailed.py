import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np

from linework import trace as T
from linework.pipeline import Options, _process_icon_scaled

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]

opts = Options(**job['options'])
res = _process_icon_scaled(crop, opts, lambda **k: None, "icon")
mod = res["model"]

print(f"\nFinal scaled model: {len(mod.paths)} paths")
for i, p in enumerate(mod.paths):
    print(f"\nPath {i}: len={len(p.A)} closed={p.closed} w={p.w:.2f}")
    for ki in range(len(p.A)):
        print(f"   A[{ki}] = {p.A[ki].round(2)}, Hin = {p.Hin[ki].round(2)}, Hout = {p.Hout[ki].round(2)}")
