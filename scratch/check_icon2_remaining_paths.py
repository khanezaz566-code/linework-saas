import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from scratch.test_smart_ring import smart_apply_ring
from linework import pipeline as P, rings as RG
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[2]
D = ink_map(crop)
w_est = estimate_width(D)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
found = [r for r in RG.detect_rings(D, w_est) if r["r"] > 15]
m_cur = m0
for r in sorted(found, key=lambda x: -x["r"]):
    new = smart_apply_ring(m_cur, r)
    if new is not None:
        m_cur = new
cx, cy = 238.3, 265.2
for pi, p in enumerate(m_cur.paths):
    f = p.flat(1.0)
    rs = np.hypot(f[:, 0] - cx, f[:, 1] - cy)
    print(f"p[{pi:2d}]: closed={p.closed}, len={p.length():5.1f}, r=[{rs.min():5.1f}..{rs.max():5.1f}], A0={np.round(p.A[0],1)}, A1={np.round(p.A[-1],1)}")
