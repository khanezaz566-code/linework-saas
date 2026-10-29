import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, lessons as LS
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[11]
D = ink_map(crop)
br = refined_branches(D)
chs, W0 = build_chains(br)
m0 = initial_model(chs, D, sigma=1.2, err=0.3)
key = LS.crop_key(crop, "standard", 0.0)
mf = Model.from_json(LS.best_get(key)["model"])

print("=== m0 paths near x=180..325, y=195..255 ===")
for pi, p in enumerate(m0.paths):
    if (p.A[:, 1] >= 195).any() and (p.A[:, 1] <= 255).any():
        print(f"m0[{pi}]: len={p.length():.1f}, A={np.round(p.A, 1).tolist()}")

print("=== mf paths near x=180..325, y=195..255 ===")
for pi, p in enumerate(mf.paths):
    if (p.A[:, 1] >= 195).any() and (p.A[:, 1] <= 255).any():
        print(f"mf[{pi}]: len={p.length():.1f}, A={np.round(p.A, 1).tolist()}")
