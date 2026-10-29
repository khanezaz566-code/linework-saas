import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
from linework.doctor import ink_of, Doctor
import linework.joints as J
import linework.finisher as FN

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)

# Build Case 2: One merged path with corner at Xc
Xc = np.array([88.44, 106.24])
p2 = Path.from_dict(data0['paths'][2])
p4 = Path.from_dict(data0['paths'][4])
p3 = Path.from_dict(data0['paths'][3])

p2_rev = FN._reversed(p2)
p2_rev.A[-1] = Xc.copy()
p2_rev.Hin[-1] = p2_rev.A[-2] + (Xc - p2_rev.A[-2]) * 0.66
p4_copy = p4.copy()
p4_copy.A[0] = Xc.copy()
p4_copy.Hout[0] = Xc + (p4_copy.A[1] - Xc) * 0.33

A_comb = np.vstack([p2_rev.A, p4_copy.A[1:]])
Hin_comb = np.vstack([p2_rev.Hin, p4_copy.Hin[1:]])
Hout_comb = np.vstack([p2_rev.Hout[:-1], p4_copy.Hout])
Hin_comb[len(p2_rev.A) - 1] = Xc - np.array([3.0, 0.0])
Hout_comb[len(p2_rev.A) - 1] = Xc + np.array([0.0, 3.0])
p_merged = Path(A_comb, Hin_comb, Hout_comb, p2.w, join="round", ml=4.0, closed=False)

other_paths2 = [p.copy() for idx, p in enumerate(paths0) if idx not in (2, 4)]
p3_copy2 = other_paths2[2]
pt_on_m, _ = J._nearest_on(p_merged, p3_copy2.A[0])
J._set_end(p3_copy2, 0, pt_on_m)
k2 = J.insert_anchor(p_merged, pt_on_m)
J._set_end(p3_copy2, 0, p_merged.A[k2])

m2 = Model([p_merged] + other_paths2, 257, 255)
ink_m2 = ink_of(m2)

H, W = D0.shape
overlay2 = np.zeros((H, W, 3), dtype=np.uint8)
overlay2[:, :, 2] = (ink_m2 * 255).astype(np.uint8) # Red (BGR)
overlay2[:, :, 1] = (D0 * 255).astype(np.uint8)     # Green (BGR)

zoom2 = overlay2[95:135, 65:110]
zoom2_big = cv2.resize(zoom2, (450, 400), interpolation=cv2.INTER_NEAREST)
cv2.imwrite('scratch/cuff_rgb_overlay2.png', zoom2_big)
print("Doctor soft score: m0=", Doctor(D0).soft(ink_of(Model(paths0, 257, 255))), "m2=", Doctor(D0).soft(ink_m2))
