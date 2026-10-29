import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options
from linework.split import estimate_width
from linework import trace as T
from linework import finisher as FN
from linework import joints as JN

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Let's inspect ends in find_joints
from linework.pipeline import _process_icon

# Let's run until Before Join Engine
res = _process_icon(small, opts, name="icon_5_small")
m = res["model"]

print("Model paths:")
for i, p in enumerate(m.paths):
    print(f"P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)} w={p.w:.2f}")

ends = []
for i, p in enumerate(m.paths):
    if p.closed:
        continue
    ends.append((i, 0, p.A[0], p.w))
    ends.append((i, 1, p.A[-1], p.w))

print("\nAll open ends:")
for idx, (i, e, pt, pw) in enumerate(ends):
    print(f"  end {idx}: path {i} end {e} at {pt.round(2)}")

# Check distance between P0 end 1 and P4 end 1:
pt0 = m.paths[0].A[-1]
pt4 = m.paths[4].A[-1]
print("Dist between P0[-1] and P4[-1]:", np.linalg.norm(pt0 - pt4))

# Let's run find_joints step by step
from scipy.spatial import cKDTree
E = np.array([pt for _, _, pt, _ in ends])
tree = cKDTree(E)
print("query_pairs(0.85 * max_w):", tree.query_pairs(0.85 * 10.0))
# Let's check tangs
tangs = []
for i, e, pt, pw in ends:
    p = m.paths[i]
    tangs.append(JN._local_end_dir(p, e))

for a, b in tree.query_pairs(0.85 * 10.0):
    i_a, e_a = ends[a][0], ends[a][1]
    i_b, e_b = ends[b][0], ends[b][1]
    print(f"Pair ({a}, {b}) -> P{i_a}[{e_a}] and P{i_b}[{e_b}]: tangs dot = {tangs[a] @ tangs[b]:.3f}")
