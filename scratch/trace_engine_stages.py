import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[1]
H_c, W_c = crop.shape
for s in (1, 2):
    Du = ink_map(cv2.resize(crop, (W_c * s, H_c * s), interpolation=cv2.INTER_CUBIC)) if s > 1 else ink_map(crop)
    br = refined_branches(Du)
    chs, W0 = build_chains(br)
    m = initial_model(chs, Du, sigma=2.0 * s * 0.6, err=0.3 * s)
    if s > 1:
        m = m.scaled(1.0 / s, W_c, H_c)
    print(f"=== s={s} ===")
    for pi in (3, 4):
        p = m.paths[pi]
        print(f"  path[{pi}]: A={np.round(p.A, 1).tolist()}")
