import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.abspath('.'))

from linework.pipeline import Options
from linework.split import estimate_width
from linework.trace import ink_map, refined_branches, skeleton_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor, ink_of
import linework.joints as J
import linework.finisher as FN

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][0]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
Du = ink_map(small)

print(f"=== STAGE 1: SKELETON BRANCHES (small shape {small.shape}) ===")
br = refined_branches(Du)
print(f"Branches count: {len(br)}")
for i, b in enumerate(br):
    pts = b['pts']
    # Check if in cuff top-right area (x in [30, 90], y in [20, 80])
    in_area = any(30 <= p[0] <= 90 and 20 <= p[1] <= 80 for p in pts)
    if in_area:
        print(f"  Branch {i}: pts={len(pts)}, start={pts[0]}, end={pts[-1]}, sj={b['sj']}, ej={b['ej']}")

print("\n=== STAGE 2: CHAINS ===")
chains, W0 = build_chains(br)
print(f"Chains count: {len(chains)}")
for i, c in enumerate(chains):
    pts = c['pts']
    in_area = any(30 <= p[0] <= 90 and 20 <= p[1] <= 80 for p in pts)
    if in_area:
        print(f"  Chain {i}: pts={len(pts)}, start={pts[0]}, end={pts[-1]}")

print("\n=== STAGE 3: INITIAL MODEL ===")
m_init = initial_model(chains, Du, sigma=2.0 * 0.6, err=0.3)
print(f"Initial model paths: {len(m_init.paths)}")
for i, p in enumerate(m_init.paths):
    in_area = any(30 <= a[0] <= 90 and 20 <= a[1] <= 80 for a in p.A)
    if in_area:
        print(f"  Path {i}: len={p.length():.1f}, closed={p.closed}, nodes={len(p.A)}")
        for ai, a in enumerate(p.A):
            if 30 <= a[0] <= 90 and 20 <= a[1] <= 80:
                print(f"    A[{ai}] = {np.round(a, 2)}")
