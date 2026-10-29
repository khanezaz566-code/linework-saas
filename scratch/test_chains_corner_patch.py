import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.trace import ink_map, refined_branches
import linework.chains as CH
from linework.chains import global_width, resample, unit, line_inter, hermite
from linework.fitting import initial_model
from linework.doctor import Doctor, ink_of
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width

# Let's inspect what happens if we patch chains.build_chains with corner pair support
def corner_pair_for_junction(l, info, br, w, cen):
    """If a multi-way junction has no collinear through-stroke, check if two branches form a clean corner."""
    best = None
    for x in range(len(l)):
        for y in range(x + 1, len(l)):
            a, b = l[x], l[y]
            if a[0] == b[0]:
                continue
            A1, d1 = info[a]["A"], info[a]["d"]
            A2, d2 = info[b]["A"], info[b]["d"]
            cr = float(d1[0] * d2[1] - d1[1] * d2[0])
            if abs(cr) < 0.40:
                continue
            dot = float(d1 @ d2)
            if abs(dot) > 0.65:
                continue
            # Ray intersection
            s1 = float((A2 - A1)[0] * d2[1] - (A2 - A1)[1] * d2[0]) / cr
            s2 = float((A2 - A1)[0] * d1[1] - (A2 - A1)[1] * d1[0]) / cr
            if s1 < -0.2 * w or s2 < -0.2 * w or s1 > 2.5 * w or s2 > 2.5 * w:
                continue
            C = A1 + s1 * d1
            dist_cen = float(np.linalg.norm(C - cen))
            if dist_cen > 1.35 * w:
                continue
            score = abs(dot) + 0.5 * (dist_cen / w)
            if best is None or score < best[0]:
                best = (score, a, b, C, A1, d1, A2, d2)
    return best

# Let's test on Icon 0 branches
job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True
box = job['icons'][0]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
k = opts.norm_stroke / w0
H, W = crop.shape
small0 = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D = ink_map(small0)
br = refined_branches(D)
W0 = global_width(br)

# Test corner detection at junctions
ends = {}
for i, b in enumerate(br):
    if b["sj"] > 0:
        ends.setdefault(b["sj"], []).append((i, 0))
    if b["ej"] > 0:
        ends.setdefault(b["ej"], []).append((i, 1))

from linework.chains import build_chains
def oriented(b, e):
    return b["pts"] if e == 1 else b["pts"][::-1]

def end_info(b, e, T):
    q = oriented(b, e)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
    n = len(q)
    T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
    k = n - 1 - int(np.searchsorted(L, T_eff))
    k = max(k, 2)
    step = max(8, int(round(1.35 * T)))
    lo = max(k - step, 0)
    d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
    return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

info = {}
for j, l in ends.items():
    w = float(np.mean([br[i]["w"] for i, _ in l]))
    for (i, e) in l:
        info[(i, e)] = end_info(br[i], e, w)

for j, l in ends.items():
    if len(l) >= 3:
        cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
        cp = corner_pair_for_junction(l, info, br, W0, cen)
        if cp:
            score, a, b, C, A1, d1, A2, d2 = cp
            print(f"Junction {j} at {np.round(cen, 1)} found corner pair: {a} and {b}, C={np.round(C, 1)}, score={score:.2f}")
