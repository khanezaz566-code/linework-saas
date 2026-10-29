import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')

# Let's inspect Icon 5 (Anchor), Icon 6 (Life vest), Icon 9 (Hydrant), Icon 8 (Cleat)
def inspect_icon(k, desc):
    print(f"\n=================== ICON {k}: {desc} ===================")
    m = Model.from_json((d / f'icon_local_{k}.json').read_text())
    orig = cv2.imread(f'scratch/icon_crop_{k}.png', 0)
    print(f"Paths count: {len(m.paths)}")
    for i, p in enumerate(m.paths):
        A = p.A
        print(f"Path {i}: closed={p.closed}, w={p.w:.2f}, segs={len(p.segs())}, pts={len(A)}")
        # Check if path has any self-intersections or sharp kinks
        if len(A) >= 3:
            for s in range(len(A) - 2):
                v1 = A[s+1] - A[s]
                v2 = A[s+2] - A[s+1]
                L1, L2 = np.linalg.norm(v1), np.linalg.norm(v2)
                if L1 > 0.5 and L2 > 0.5:
                    cos = np.clip(np.dot(v1, v2) / (L1 * L2), -1, 1)
                    deg = np.degrees(np.arccos(cos))
                    if deg > 60:
                        print(f"  Path {i} sharp angle {deg:.1f} deg at node {s+1}: {A[s+1]}")

inspect_icon(5, "Anchor")
inspect_icon(8, "Cleat")
inspect_icon(9, "Hydrant")
inspect_icon(6, "Life vest")
