import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import joints as JN
from linework import finisher as FN
from linework.geom import unit
from linework.trace import ink_map
import cv2

def test_icon_unite(k):
    d = Path('data/aca01e4ff5aa')
    m = Model.from_json((d / f'icon_local_{k}.json').read_text())
    crop = cv2.imread(f'scratch/icon_crop_{k}.png', 0)
    D = ink_map(crop)
    
    print(f"\n--- Icon {k} (paths: {len(m.paths)}) ---")
    js = JN.find_joints(m)
    for J in js:
        if J.kind in ("Y", "L") and len(J.ends) >= 2:
            # Check smooth continuation pairs
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
                    # opposite directions
                    dot = float(ta @ tb)
                    if dot < -0.35: # angle between stroke trajectories < 70 deg
                        n = max(3, int(dist))
                        pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
                        xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
                        ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
                        ink_frac = float((D[ys, xs] > 0.5).mean())
                        if ink_frac >= 0.8:
                            cands.append((dist, i, ei, j, ej, dot))
            if cands:
                print(f"Joint at {J.xy} found {len(cands)} smooth unite cand(s):")
                for c in cands:
                    print(f"  dist={c[0]:.2f}, paths=({c[1]}, {c[3]}), dot={c[4]:.3f}")

test_icon_unite(8) # Cleat
test_icon_unite(6) # Life vest
