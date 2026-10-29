import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, rings as RG, edit as E
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.pipeline import ink_of
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[10]
D = ink_map(crop)
w_est = estimate_width(D)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
found = RG.detect_rings(D, w_est)
for pi, p in enumerate(m0.paths):
    f = p.flat(0.5)
    cx, cy, r = RG._kasa(f)
    print(f"m0[{pi}]: cx={cx:.2f}, cy={cy:.2f}, r={r:.2f}, w={p.w:.2f}")
for ring in found:
    print(f"ring:   cx={ring['cx']:.2f}, cy={ring['cy']:.2f}, r={ring['r']:.2f}, a={ring['a']:.2f}, b={ring['b']:.2f}, w={ring['w']:.2f}")
