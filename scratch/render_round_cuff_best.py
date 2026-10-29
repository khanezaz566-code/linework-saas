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

Xc = np.array([88.44, 104.81])
R = 10.0
kappa = 0.55228475 * R
P_start = np.array([Xc[0] - R, Xc[1]])
P_end   = np.array([Xc[0], Xc[1] + R])

p2 = Path.from_dict(data0['paths'][2]).copy()
p4 = Path.from_dict(data0['paths'][4]).copy()
p3 = Path.from_dict(data0['paths'][3]).copy()

p2.A[1] = P_start.copy()
p2.Hout[1] = P_start + np.array([kappa, 0.0])
p2.A[0] = P_end.copy()
p2.Hin[0] = P_end - np.array([0.0, kappa])
p2.Hout[0] = P_end.copy()

p4.A[0] = P_end.copy()
p4.Hin[0] = P_end.copy()
p4.Hout[0] = P_end + (p4.A[1] - P_end) / 3.0

pt_on_p4, _ = J._nearest_on(p4, p3.A[0])
J._set_end(p3, 0, pt_on_p4)
k = J.insert_anchor(p4, pt_on_p4)
J._set_end(p3, 0, p4.A[k])

m_round = Model([p2, p4, p3] + [Path.from_dict(p) for idx, p in enumerate(data0['paths']) if idx not in (2, 3, 4)], 257, 255)
ink_round = ink_of(m_round)

H, W = D0.shape
overlay_round = np.zeros((H, W, 3), dtype=np.uint8)
overlay_round[:, :, 2] = (ink_round * 255).astype(np.uint8) # Red (BGR)
overlay_round[:, :, 1] = (D0 * 255).astype(np.uint8)         # Green (BGR)

zoom_round = overlay_round[95:135, 65:110]
zoom_round_big = cv2.resize(zoom_round, (450, 400), interpolation=cv2.INTER_NEAREST)
cv2.imwrite('scratch/cuff_rgb_round_best.png', zoom_round_big)

# Also save standalone black/white render
img_bw = (ink_round * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_bw_round_best.png', cv2.resize(img_bw[95:135, 65:110], (200, 200), interpolation=cv2.INTER_NEAREST))
print("Saved cuff_rgb_round_best.png and cuff_bw_round_best.png")
