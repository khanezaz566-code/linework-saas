import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)
m0 = initial_model(chains, D)
p = m0.paths[0]
for idx in range(23, 33):
    print(f"pt {idx}: A={p.A[idx]}, Hin={p.Hin[idx]}, Hout={p.Hout[idx]}")
