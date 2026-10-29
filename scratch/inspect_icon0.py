import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.split import estimate_width

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][0]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
k = 10.0 / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

Du = ink_map(small)
br = refined_branches(Du)
print('Icon 0: branches count =', len(br))
for i, b in enumerate(br):
    print(f"b[{i}]: len={len(b['pts'])}, sj={b['sj']}, ej={b['ej']}")

chains, W0 = build_chains(br)
print('Icon 0: chains count =', len(chains))
for i, c in enumerate(chains):
    print(f"c[{i}]: len={len(c['pts'])}, w={c['w']:.1f}")

m = initial_model(chains, Du, sigma=2.0 * 0.6, err=0.3)
print('Icon 0: initial_model paths =', len(m.paths))
for i, p in enumerate(m.paths):
    print(f"p[{i}]: len={p.length():.1f}, closed={p.closed}, A[0]={np.round(p.A[0], 1)}, A[-1]={np.round(p.A[-1], 1)}")
