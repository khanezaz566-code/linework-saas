import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor, ink_of

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)
br = refined_branches(D)

# Let's inspect all junctions with >= 3 branches in br
from linework.chains import global_width
W0 = global_width(br)
print(f"Global width: {W0:.2f}")

ends = {}
for i, b in enumerate(br):
    if b["sj"] > 0:
        ends.setdefault(b["sj"], []).append((i, 0))
    if b["ej"] > 0:
        ends.setdefault(b["ej"], []).append((i, 1))

print("Junctions with >= 3 ends:")
for j, l in ends.items():
    if len(l) >= 3:
        cen = np.mean([b["pts"][0 if e==0 else -1] for b_idx, e in l for b in [br[b_idx]]], axis=0)
        print(f"Junction {j} at {np.round(cen, 1)}: {len(l)} ends: {l}")
