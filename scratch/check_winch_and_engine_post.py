import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, lessons as LS, joints as JN
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for idx in [1, 4]:
    k, crop, off = jobs[idx]
    D = ink_map(crop)
    br = refined_branches(D)
    chs, W0 = build_chains(br)
    m0 = initial_model(chs, D, sigma=1.2, err=0.3)
    key = LS.crop_key(crop, "standard", 0.0)
    prev = LS.best_get(key)
    mf = Model.from_json(prev["model"])
    print(f"=== ICON {idx} (m0: {len(m0.paths)} paths, mf: {len(mf.paths)} paths) ===")
    if idx == 4:
        print("  --- m0 top arches ---")
        for pi, p in enumerate(m0.paths):
            if p.A[:, 1].min() <= 85 and 150 <= p.A[:, 0].mean() <= 350:
                print(f"  m0[{pi}]: len={p.length():.1f}, A={np.round(p.A, 1).tolist()}")
        print("  --- mf top arches ---")
        for pi, p in enumerate(mf.paths):
            if p.A[:, 1].min() <= 85 and 150 <= p.A[:, 0].mean() <= 350:
                print(f"  mf[{pi}]: len={p.length():.1f}, A={np.round(p.A, 1).tolist()}")
    if idx == 1:
        print("  --- mf pipe mount paths ---")
        for pi, p in enumerate(mf.paths):
            if 115 <= p.A[:, 1].min() <= 195 and 115 <= p.A[:, 0].mean() <= 345:
                print(f"  mf[{pi}]: len={p.length():.1f}, closed={p.closed}, A={np.round(p.A, 1).tolist()}")
