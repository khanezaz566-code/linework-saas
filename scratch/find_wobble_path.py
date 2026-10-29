import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')

for k in [1, 2, 3, 11]:
    m = Model.from_json((d / f'icon_local_{k}.json').read_text())
    print(f"\n--- Icon {k} (paths: {len(m.paths)}) ---")
    for i, p in enumerate(m.paths):
        f = p.flat(1.0)
        # Check if mostly vertical
        dx = f[:, 0].max() - f[:, 0].min()
        dy = f[:, 1].max() - f[:, 1].min()
        if dy > 100 and dx < 40:
            # Check maximum deviation from straight line connecting endpoints
            v = f[-1] - f[0]
            L = np.linalg.norm(v)
            if L > 100:
                u = v / L
                perp = np.array([-u[1], u[0]])
                dist = np.abs((f - f[0]) @ perp).max()
                if 2.0 < dist < 25.0:
                    print(f"  Path {i}: len={L:.1f}, lateral dev={dist:.2f}px, box=[{f[:,0].min():.1f}, {f[:,1].min():.1f}, {f[:,0].max():.1f}, {f[:,1].max():.1f}]")
