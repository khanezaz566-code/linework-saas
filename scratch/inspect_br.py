import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.trace import ink_map, skeleton_branches, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.split import estimate_width
from linework.doctor import Doctor, ink_of

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][8]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
k = 10.0 / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

s = 2
Du = ink_map(cv2.resize(small, (small.shape[1] * s, small.shape[0] * s), interpolation=cv2.INTER_CUBIC))

# Test with prune = 25
br_raw = skeleton_branches(Du, S=2, prune=25)
print('Icon 8 With prune=25, br_raw count:', len(br_raw))
for i, b in enumerate(br_raw):
    print(f"b[{i}]: len={len(b['pts'])}, sj={b['sj']}, ej={b['ej']}")
