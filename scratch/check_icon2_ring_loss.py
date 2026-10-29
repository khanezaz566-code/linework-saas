import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from scratch.test_smart_ring import smart_apply_ring
from linework import pipeline as P, rings as RG, opt
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.pipeline import ink_of
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[2]
D = ink_map(crop)
w_est = estimate_width(D)
doc = Doctor(D)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
print("m0 soft:", doc.soft(ink_of(m0)), "iou:", doc.iou(ink_of(m0)), "paths:", len(m0.paths))
found = [r for r in RG.detect_rings(D, w_est) if r["r"] > 15]
m_cur = m0
for r in sorted(found, key=lambda x: -x["r"]):
    new = smart_apply_ring(m_cur, r)
    if new is not None:
        m_cur = new
        print(f"After ring r={r['r']:.1f}: soft={doc.soft(ink_of(m_cur)):.1f}, paths={len(m_cur.paths)}")
free_non_rings = [i for i, p in enumerate(m_cur.paths) if not (p.closed and len(p.segs()) == 4)]
m_ref = opt.refine(m_cur, D, free=free_non_rings, iters=22, taus=(1.0, 0.5, 0.35))
print("m_ref soft:", doc.soft(ink_of(m_ref)), "iou:", doc.iou(ink_of(m_ref)), "paths:", len(m_ref.paths))
