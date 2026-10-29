import sys, os, json
sys.path.insert(0, ".")
from linework.model import Model, Path
from linework.trace import ink_map
from linework.doctor import Doctor
from linework.render import render_gray
from tools.junction_bench import star
from linework import finisher as FN
from linework import joincheck as JC
from linework import topology as T
import numpy as np

# 1. Update _is_junction_end
orig_is_junc = T._is_junction_end
def new_is_junction_end(m: Model, i: int, e: int) -> bool:
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return False
    a = p.A[0] if e == 0 else p.A[-1]
    b = p.A[1] if e == 0 else p.A[-2]
    d_a, d_b = np.inf, np.inf
    for j, q in enumerate(m.paths):
        if j == i:
            continue
        f = q.flat(1.0)
        da = float(np.linalg.norm(f - a, axis=1).min())
        db = float(np.linalg.norm(f - b, axis=1).min())
        if da < d_a:
            d_a = da
        if db < d_b:
            d_b = db
    if d_a <= 0.25 * p.w:  # clearly touching another stroke
        return True
    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)
T._is_junction_end = new_is_junction_end

# 2. Update merge_corners with clean seam
def clean_path(p):
    A, Hin, Hout = list(p.A), list(p.Hin), list(p.Hout)
    changed = True
    while changed and len(A) > 2:
        changed = False
        for k in range(len(A) - 1):
            if np.linalg.norm(A[k+1] - A[k]) < 0.25 * p.w:
                A.pop(k)
                Hin.pop(k)
                Hout.pop(k)
                changed = True
                break
    return Path(np.array(A), np.array(Hin), np.array(Hout), p.w, p.join, p.ml, p.closed)

orig_merge_corners = FN.merge_corners
def new_merge_corners(m: Model, pairs):
    cand = orig_merge_corners(m, pairs)
    cand.paths = [clean_path(p) for p in cand.paths]
    return cand
FN.merge_corners = new_merge_corners

# Now run JC.run on m0
g = star()
D = ink_map(g)
doc = Doctor(D)
def ink_of(mod):
    return render_gray(mod.svg(), g.shape[1], g.shape[0]) < 128

m = Model.from_json(json.load(open('scratch/star_m0.json')))
cur = doc.soft(ink_of(m))
m_after, ink_after, cur_after, rep = JC.run(m, D, doc, ink_of, cur, 10.0)
print('JC Report:', rep['bad_before'], '->', rep['bad_after'], 'fixed:', rep['fixed'])
for item in rep['items']:
    print('  item:', item)
print('Failing:')
for f in rep['failing']:
    print('  fail:', f)
