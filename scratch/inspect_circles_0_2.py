import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P
from linework.rings import _kasa

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for idx in [0, 2]:
    k, crop, off = jobs[idx]
    res = P.process_icon(crop, P.Options(fresh=True, memory=False), name=f"icon_{k}")
    m = res["model"]
    print(f"=== ICON {idx} ({len(m.paths)} paths) ===")
    for pi, p in enumerate(m.paths):
        f = p.flat(0.5)
        cx, cy, r = _kasa(f)
        rad_err = np.abs(np.hypot(f[:, 0] - cx, f[:, 1] - cy) - r)
        if p.closed or (p.length() > 50 and rad_err.max() < 8.0):
            print(f"  path[{pi}]: closed={p.closed}, nA={len(p.A)}, len={p.length():.1f}, r={r:.2f}, max_rad_err={rad_err.max():.3f}, p95_err={np.percentile(rad_err, 95):.3f}")
            print(f"    A={np.round(p.A, 2).tolist()}")
