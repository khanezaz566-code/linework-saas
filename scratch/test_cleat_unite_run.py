import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import joints as JN
from linework import finisher as FN
from linework.geom import unit
from linework.trace import ink_map
from linework.doctor import Doctor, ink_of

def smooth_pairs(m, J, D):
    cands = []
    for x in range(len(J.ends)):
        for y in range(x + 1, len(J.ends)):
            i, ei = J.ends[x]
            j, ej = J.ends[y]
            if i == j: continue
            P, Q = m.paths[i], m.paths[j]
            if abs(P.w - Q.w) > 0.25 * max(P.w, Q.w): continue
            a = P.A[0] if ei == 0 else P.A[-1]
            b = Q.A[0] if ej == 0 else Q.A[-1]
            dist = np.linalg.norm(b - a)
            w = max(P.w, Q.w)
            if dist > 2.5 * w: continue
            ga = FN.end_geometry(P, ei)
            gb = FN.end_geometry(Q, ej)
            ta = ga[1] if ga is not None else unit(a - (P.A[1] if ei == 0 else P.A[-2]))
            tb = gb[1] if gb is not None else unit(b - (Q.A[1] if ej == 0 else Q.A[-2]))
            dot = float(ta @ tb)
            if dot < -0.3:
                n = max(3, int(dist))
                pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
                xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
                ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
                if (D[ys, xs] > 0.5).mean() >= 0.8:
                    cands.append((dist, i, ei, j, ej))
    if not cands:
        return []
    cands.sort(key=lambda t: t[0])
    return [(cands[0][1], cands[0][2], cands[0][3], cands[0][4])]

crop = cv2.imread('scratch/icon_crop_8.png', 0)
D = ink_map(crop)
doc = Doctor(D)
m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_8.json').read_text())

cur_soft = doc.soft(ink_of(m))
print(f"Icon 8 before unite: soft={cur_soft:.1f}, iou={doc.iou(ink_of(m))*100:.2f}%, paths={len(m.paths)}")

# Find joints
js = JN.find_joints(m)
for J in js:
    sp = smooth_pairs(m, J, D)
    if sp:
        print(f"Uniting pair in joint at {J.xy}: {sp}")
        m_cand = FN.join_pairs(m, sp)
        if m_cand is not None:
            cand_soft = doc.soft(ink_of(m_cand))
            if cand_soft <= cur_soft + 10.0:
                m = m_cand
                cur_soft = cand_soft
                print(f"  Accepted! Paths now: {len(m.paths)}, iou={doc.iou(ink_of(m))*100:.2f}%")

# Now check unresolved joints after unite
fails_after = 0
for J in JN.find_joints(m):
    fails = JN.check_joint(m, J)
    if fails:
        fails_after += 1
        print(f"Remaining failed joint {J.kind} at {J.xy}: {fails}")
print(f"Failed joints: before=5 -> after={fails_after}")
