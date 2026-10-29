import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.trace import ink_map, refined_branches
from linework.chains import global_width, resample, unit, line_inter
from linework.pipeline import Options
from linework.split import estimate_width

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True
box1 = job['icons'][1]['box']
crop1 = orig[box1[1]:box1[3], box1[0]:box1[2]]
w0 = estimate_width(ink_map(crop1))
k = opts.norm_stroke / w0
H, W = crop1.shape
small1 = cv2.resize(crop1, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

D1 = ink_map(small1)
br1 = refined_branches(D1)
W1 = global_width(br1)
print(f"Icon 1 Global width: {W1:.2f}")

ends = {}
for i, b in enumerate(br1):
    if b["sj"] > 0:
        ends.setdefault(b["sj"], []).append((i, 0))
    if b["ej"] > 0:
        ends.setdefault(b["ej"], []).append((i, 1))

print("Icon 1 Junctions with >= 3 ends:")
for j, l in ends.items():
    if len(l) >= 3:
        cen = np.mean([b["pts"][0 if e==0 else -1] for b_idx, e in l for b in [br1[b_idx]]], axis=0)
        print(f"Junction {j} at {np.round(cen, 1)}: {len(l)} ends: {l}")
