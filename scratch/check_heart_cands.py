import sys, os, numpy as np
sys.path.insert(0, os.path.abspath('.'))
import json, cv2
from linework.pipeline import Options
from linework.split import estimate_width
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor, ink_of

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][4]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

for s, sf in [(2, 0.6), (3, 0.6), (1, 0.6)]:
    W_s, H_s = small.shape[1], small.shape[0]
    Du = ink_map(cv2.resize(small, (W_s * s, H_s * s), interpolation=cv2.INTER_CUBIC)) if s > 1 else ink_map(small)
    br = refined_branches(Du)
    chains, W0 = build_chains(br)
    m = initial_model(chains, Du, sigma=opts.sigma * s * sf, err=0.3 * s)
    if s > 1: m = m.scaled(1.0 / s, W_s, H_s)
    doc = Doctor(ink_map(small))
    print(f's={s}, sf={sf}: len(A)={len(m.paths[0].A)}, iou={doc.iou(ink_of(m)):.4f}')
    for idx, a in enumerate(m.paths[0].A):
        if a[1] >= 60.0 and abs(a[0] - 133.0) < 5.0:
            print(f'   anchor at crevice: A[{idx}] = {np.round(a, 2)}')
