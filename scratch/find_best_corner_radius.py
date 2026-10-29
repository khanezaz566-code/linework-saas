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

# Let's inspect the top-left corner radius on Path 2 to get the exact radius of the cuff!
p2_orig = Path.from_dict(data0['paths'][2])
# Top edge y = 104.8. Right edge x = 88.4.
# Left edge x = 39.3. Top-left corner arc is between Node 2 (x=52.3) and Node 4 (x=39.4).
# Radius R = 52.3 - 39.4 ≈ 12.9 px.
# Let's test R in [8, 10, 12, 14] to find which R minimizes doctor soft!
best_R = None
best_soft = 999.0

Xc = np.array([88.44, 104.81])

for R in [8.0, 9.0, 10.0, 11.0, 12.0, 13.0]:
    kappa = 0.55228475 * R
    # Quarter arc in quadrant 1 (top-right):
    # Arc goes from (Xc[0] - R, Xc[1]) around to (Xc[0], Xc[1] + R)
    P_start = np.array([Xc[0] - R, Xc[1]])
    P_end   = np.array([Xc[0], Xc[1] + R])
    
    # In p2_orig:
    # A[1] is [77.16, 104.81].
    # Notice: if R = 11.28, P_start is exactly [77.16, 104.81]!
    p2 = p2_orig.copy()
    p4 = Path.from_dict(data0['paths'][4]).copy()
    p3 = Path.from_dict(data0['paths'][3]).copy()
    
    # We replace p2 Node 0 [90.73, 112.61] by the corner arc:
    # Set p2 A[1] = P_start, Hout[1] = P_start + np.array([kappa, 0])
    # Set p2 A[0] = P_end,   Hin[0]  = P_end - np.array([0, kappa]), Hout[0] = P_end
    p2.A[1] = P_start.copy()
    p2.Hout[1] = P_start + np.array([kappa, 0.0])
    p2.A[0] = P_end.copy()
    p2.Hin[0] = P_end - np.array([0.0, kappa])
    p2.Hout[0] = P_end.copy()
    
    # On p4:
    # p4 goes from A[0] down to A[2] = [88.44, 202.75]
    # Set p4 A[0] = P_end
    # Set p4 Hout[0] = P_end + (p4.A[1] - P_end) / 3.0
    p4.A[0] = P_end.copy()
    p4.Hin[0] = P_end.copy()
    p4.Hout[0] = P_end + (p4.A[1] - P_end) / 3.0
    
    # Snap p3 (thumb) to p4 (or p2)
    pt_on_p4, _ = J._nearest_on(p4, p3.A[0])
    J._set_end(p3, 0, pt_on_p4)
    k = J.insert_anchor(p4, pt_on_p4)
    J._set_end(p3, 0, p4.A[k])
    
    m_test = Model([p2, p4, p3] + [Path.from_dict(p) for idx, p in enumerate(data0['paths']) if idx not in (2, 3, 4)], 257, 255)
    s = Doctor(D0).soft(ink_of(m_test))
    print(f"R={R:.1f}: soft={s:.2f}")
    if s < best_soft:
        best_soft = s
        best_R = R

print(f"Best R={best_R} with soft={best_soft:.2f}")
