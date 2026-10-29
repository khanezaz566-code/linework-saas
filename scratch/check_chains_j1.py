import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches
from linework.chains import global_width, resample, unit, line_inter

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)
br = refined_branches(D)
W0 = global_width(br)

def oriented(b, e):
    return b["pts"] if e == 1 else b["pts"][::-1]

def end_info(b, e, T):
    q = oriented(b, e)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
    n = len(q)
    T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
    k = n - 1 - int(np.searchsorted(L, T_eff))
    k = max(k, 2)
    step = max(8, int(round(1.35 * T)))
    lo = max(k - step, 0)
    d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
    return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

T = 1.0 * W0
info3 = end_info(br[3], 1, T)
info5 = end_info(br[5], 1, T)
info8 = end_info(br[8], 1, T)

print("Junction 5:")
print("info 3 (1): A=", np.round(info3["A"], 1), "d=", np.round(info3["d"], 2))
print("info 5 (1): A=", np.round(info5["A"], 1), "d=", np.round(info5["d"], 2))
print("info 8 (1): A=", np.round(info8["A"], 1), "d=", np.round(info8["d"], 2))

# What are the angles between pairs at Junction 5?
for name_a, ia, name_b, ib in [("3", info3, "5", info5), ("3", info3, "8", info8), ("5", info5, "8", info8)]:
    ta, tb = ia["d"], ib["d"]
    ang = np.degrees(np.arccos(np.clip(-ta @ tb, -1, 1)))
    print(f"Angle between {name_a} and {name_b}: {ang:.1f} deg, dot={ta@tb:.2f}")
