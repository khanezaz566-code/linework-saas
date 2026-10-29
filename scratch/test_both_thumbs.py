import sys, os, numpy as np, cv2, json
sys.path.insert(0, os.path.abspath('.'))

from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map
from linework.doctor import ink_of
from linework.model import Model
import linework.joints as J
import linework.finisher as FN

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True

def run_icon(idx):
    box = job['icons'][idx]['box']
    crop = orig[box[1]:box[3], box[0]:box[2]]
    w0 = estimate_width(ink_map(crop))
    k = opts.norm_stroke / w0
    H, W = crop.shape
    small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
    res = _process_icon(small, opts, emit=lambda **k: None, name=f'ic{idx}')
    return res['model'], ink_map(small), small

print("Running Icon 0...")
m0, D0, small0 = run_icon(0)
print("Running Icon 1...")
m1, D1, small1 = run_icon(1)

def find_corner_pairs_at_joints(m: Model):
    pairs = []
    used_ends = set()
    js = J.find_joints(m)
    for j in js:
        if len(j.ends) < 3:
            continue
        ends = j.ends
        best_pair = None
        best_score = 999.0
        for x in range(len(ends)):
            for y in range(x + 1, len(ends)):
                i, ei = ends[x]
                k, ek = ends[y]
                if i >= len(m.paths) or k >= len(m.paths) or i == k:
                    continue
                if (i, ei) in used_ends or (k, ek) in used_ends:
                    continue
                P, Q = m.paths[i], m.paths[k]
                wa, wb = P.w, Q.w
                if abs(wa - wb) > 0.25 * max(wa, wb):
                    continue
                w = max(wa, wb)
                
                gP = FN.end_geometry(P, ei)
                gQ = FN.end_geometry(Q, ek)
                cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei==0 else -1], J._local_end_dir(P, ei))
                cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ek==0 else -1], J._local_end_dir(Q, ek))
                
                cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
                if abs(cr) < 0.40:
                    continue
                
                sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / cr
                Xc = cP + sP * tP
                if np.linalg.norm(Xc - j.xy) > 1.35 * w:
                    continue
                
                dot = float(tP @ tQ)
                score = abs(dot)
                if score < best_score:
                    best_score = score
                    best_pair = (i, ei, k, ek)
        if best_pair is not None and best_score < 0.60:
            pairs.append(best_pair)
            used_ends.add((best_pair[0], best_pair[1]))
            used_ends.add((best_pair[2], best_pair[3]))
    return pairs

print("Icon 0 corner pairs:", find_corner_pairs_at_joints(m0))
print("Icon 1 corner pairs:", find_corner_pairs_at_joints(m1))
