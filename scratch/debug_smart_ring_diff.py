import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from scratch.test_smart_ring import smart_apply_ring
from linework import pipeline as P, rings as RG
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.pipeline import ink_of
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for idx in [0, 2]:
    k, crop, off = jobs[idx]
    D = ink_map(crop)
    w_est = estimate_width(D)
    doc = Doctor(D)
    br = refined_branches(D)
    chs, W0 = build_chains(br)
    m0 = initial_model(chs, D, sigma=1.2, err=0.3)
    print(f"=== ICON {idx} ===")
    for pi, p in enumerate(m0.paths):
        print(f"  m0[{pi}]: len={p.length():.1f}, closed={p.closed}, A0={np.round(p.A[0],1)}, A1={np.round(p.A[-1],1)}")
    found = [r for r in RG.detect_rings(D, w_est) if r["r"] > 15]
    for r in found:
        new = smart_apply_ring(m0, r)
        print(f"  After ring r={r['r']:.1f}: {len(new.paths)} paths")
        for pi, p in enumerate(new.paths):
            print(f"    new[{pi}]: len={p.length():.1f}, closed={p.closed}, A0={np.round(p.A[0],1)}, A1={np.round(p.A[-1],1)}")
