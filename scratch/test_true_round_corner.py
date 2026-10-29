import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
from linework.doctor import ink_of, Doctor
import linework.joints as J

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)

Xc = np.array([88.44, 104.81])
R = 10.0
kappa = 0.55228475 * R
P_start = np.array([Xc[0] - R, Xc[1]]) # [78.44, 104.81]
P_end   = np.array([Xc[0], Xc[1] + R]) # [88.44, 114.81]

p2 = Path.from_dict(data0['paths'][2]).copy()
p4 = Path.from_dict(data0['paths'][4]).copy()
p3 = Path.from_dict(data0['paths'][3]).copy()

# On p2:
# Segment 0 goes from A[0] to A[1].
# A[0] is at the vertical edge [88.44, 114.81]. Tangent pointing towards A[1] is UP: [0, -1].
# A[1] is at the horizontal edge [78.44, 104.81]. Tangent entering A[1] from A[0] is LEFT: [-1, 0].
# So:
# Hout[0] = A[0] + [0, -kappa]
# Hin[1]  = A[1] + [kappa, 0]
p2.A[0] = P_end.copy()
p2.Hout[0] = P_end + np.array([0.0, -kappa])
p2.Hin[1]  = P_start + np.array([kappa, 0.0])
p2.A[1]    = P_start.copy()

# On p4:
# p4 goes from A[0] down to A[2] = [88.44, 202.75].
# A[0] is at P_end = [88.44, 114.81].
# Downward segment to A[1] = [88.44, 120.85]:
p4.A[0] = P_end.copy()
v4 = p4.A[1] - P_end
p4.Hout[0] = P_end + v4 / 3.0
p4.Hin[1]  = p4.A[1] - v4 / 3.0

# Snap p3 (thumb) to p4:
pt_on_p4, _ = J._nearest_on(p4, p3.A[0])
J._set_end(p3, 0, pt_on_p4)
k = J.insert_anchor(p4, pt_on_p4)
J._set_end(p3, 0, p4.A[k])

m_round = Model([p2, p4, p3] + [Path.from_dict(p) for idx, p in enumerate(data0['paths']) if idx not in (2, 3, 4)], 257, 255)
ink_round = ink_of(m_round)
s = Doctor(D0).soft(ink_round)
print(f"Doctor soft with true round corner: {s:.2f} (original was 271.43)")

img_bw = (ink_round * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_bw_true_round.png', cv2.resize(img_bw[95:135, 65:110], (200, 200), interpolation=cv2.INTER_NEAREST))
print("Saved cuff_bw_true_round.png")
