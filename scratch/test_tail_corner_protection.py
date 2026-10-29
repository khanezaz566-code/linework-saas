import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework import trace as T
from linework.doctor import Doctor, ink_of

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

orig_redundancy = Doctor.redundancy

def new_redundancy(self, model):
    red, tails = orig_redundancy(self, model)
    flats = [p.flat(0.5) for p in model.paths]
    filtered_tails = []
    for (i, k, j) in tails:
        p = model.paths[i]
        f = flats[i]
        tail_pts = f[k:j+1]
        if len(tail_pts) < 2:
            continue
        v_tail = tail_pts[-1] - tail_pts[0]
        lv = np.linalg.norm(v_tail)
        if lv < 1e-4:
            continue
        t_tail = v_tail / lv
        other_idx = -1
        min_d = 1e9
        pt_mid = tail_pts[len(tail_pts) // 2]
        for m_idx, fm in enumerate(flats):
            if m_idx == i or m_idx in red or len(fm) < 2:
                continue
            d = np.linalg.norm(fm - pt_mid, axis=1).min()
            if d < min_d:
                min_d = d
                other_idx = m_idx
        if other_idx >= 0 and min_d < 0.6 * p.w:
            fm = flats[other_idx]
            k_other = int(np.argmin(np.linalg.norm(fm - pt_mid, axis=1)))
            lo = max(0, k_other - 4)
            hi = min(len(fm) - 1, k_other + 4)
            v_other = fm[hi] - fm[lo]
            if np.linalg.norm(v_other) > 1e-4:
                t_other = v_other / np.linalg.norm(v_other)
                cos_ang = abs(float(t_tail @ t_other))
                print(f"Tail candidate path {i} [{k}:{j}] vs path {other_idx}: cos_ang = {cos_ang:.3f}")
                if cos_ang < 0.85:
                    print(f"  -> REJECTED tail (corner/junction angle, not duplicate run)")
                    continue
        filtered_tails.append((i, k, j))
    return red, filtered_tails

Doctor.redundancy = new_redundancy

res = _process_icon(small, opts, name="icon_5_small")
m = res["model"]
print(f"\nFinal paths after protecting corner from tail cut: {len(m.paths)}")
for i, p in enumerate(m.paths):
    print(f"P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
