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
k, crop, off = jobs[0]
D = ink_map(crop)
w_est = estimate_width(D)
doc = Doctor(D)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
found = [r for r in RG.detect_rings(D, w_est) if r["r"] > 40]
r = found[0]
new = smart_apply_ring(m0, r)
print("m0 soft:", doc.soft(ink_of(m0)), "iou:", doc.iou(ink_of(m0)))
print("new soft:", doc.soft(ink_of(new)), "iou:", doc.iou(ink_of(new)))
# What if we refine the blades (keeping the closed circles fixed!) with opt.refine?
free_blades = [i for i, p in enumerate(new.paths) if not p.closed]
new_ref = opt.refine(new, D, free=free_blades, iters=18, taus=(1.0, 0.5))
print("new_ref soft:", doc.soft(ink_of(new_ref)), "iou:", doc.iou(ink_of(new_ref)))
