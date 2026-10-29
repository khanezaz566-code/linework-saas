import sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import topology as T

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_5.json').read_text())
p = m.paths[0]
print(f"Original path 0 nodes: {len(p.A)}")

# Test find_notches with frac=0.45 vs 0.85
notches_old = [k for k in range(1, len(p.A) - 2) if T._is_step(p, k, 0.45)]
notches_new = [k for k in range(1, len(p.A) - 2) if T._is_step(p, k, 0.85)]
print(f"Notches with frac=0.45: {notches_old}")
print(f"Notches with frac=0.85: {notches_new}")

m_fixed = T.merge_nodes(m, 0, frac=0.85)
p_fixed = m_fixed.paths[0]
print(f"Fixed path 0 nodes: {len(p_fixed.A)}")
for k in range(len(p_fixed.A) - 2):
    v1 = p_fixed.A[k+1] - p_fixed.A[k]
    v2 = p_fixed.A[k+2] - p_fixed.A[k+1]
    l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if l1 > 0.5 and l2 > 0.5:
        cos = np.clip((v1 / l1) @ (v2 / l2), -1, 1)
        deg = np.degrees(np.arccos(cos))
        if deg > 90:
            print(f"  Remaining reversal {deg:.1f} deg at pt {k+1}: {p_fixed.A[k+1]}")
