import sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
from linework.finisher import _others_tree, move_end

crop = cv2.imread('scratch/icon_crop_9.png', 0)
D = ink_map(crop)
doc = Doctor(D)

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_9.json').read_text())

def check_penetrating_stubs(m, D):
    hits = []
    for i, p in enumerate(m.paths):
        if p.closed: continue
        w = p.w
        tree, P, own = _others_tree(m, i)
        if tree is None: continue
        for e in (0, 1):
            f = p.flat(0.5)
            if e == 0:
                f = f[::-1]
            a = f[-1]
            # samples along the last 2.8 * w
            cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
            max_k = int(np.searchsorted(cum, 2.8 * w))
            if max_k < 4: continue
            pts = f[::-1][:max_k]
            ds, idxs = tree.query(pts)
            # Find any local minimum of ds where distance to another stroke < 0.4 * w
            for step_k in range(3, len(ds)):
                dist_to_other = ds[step_k]
                j = own[idxs[step_k]]
                if dist_to_other < 0.35 * w:
                    # We crossed stroke j at arc-length cum[step_k] behind end a
                    s = cum[step_k]
                    if s >= 0.6 * w:
                        # Check if between pt and a, there are white pixels in D (a hole / overshoot)
                        test_pts = f[::-1][:step_k]
                        xs = np.clip(test_pts[:, 0].astype(int), 0, D.shape[1] - 1)
                        ys = np.clip(test_pts[:, 1].astype(int), 0, D.shape[0] - 1)
                        # or check if j is a closed path and a is on or past its far wall
                        has_hole = (D[ys, xs] < 0.4).any()
                        is_closed = m.paths[j].closed
                        if has_hole or is_closed:
                            hits.append((i, e, s, a, j, dist_to_other))
                            break
    return hits

hits = check_penetrating_stubs(m, D)
print(f"Penetrating stubs found: {len(hits)}")
for h in hits:
    print(f"  Path {h[0]} end {h[1]}: cut={h[2]:.2f}px at {h[3]} crossing path {h[4]}")
    m_cand = move_end(m, h[0], h[1], h[2])
    if m_cand is not None:
        s_before = doc.soft(ink_of(m))
        s_after = doc.soft(ink_of(m_cand))
        print(f"    Soft before={s_before:.1f} -> after={s_after:.1f} (delta={s_after - s_before:+.1f}px)")
