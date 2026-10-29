import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN
from linework.doctor import Doctor, ink_of

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)

p2 = Path.from_dict(data0['paths'][2])
p4 = Path.from_dict(data0['paths'][4])
p3 = Path.from_dict(data0['paths'][3])

# Case 1: Separate paths meeting at Xc = [88.44, 106.24]
m1 = Model([p.copy() for p in paths0], 257, 255)
Xc = np.array([88.44, 106.24])
J._set_end(m1.paths[2], 0, Xc)
J._set_end(m1.paths[4], 0, Xc)
pt_on_p4, _ = J._nearest_on(m1.paths[4], m1.paths[3].A[0])
J._set_end(m1.paths[3], 0, pt_on_p4)
k = J.insert_anchor(m1.paths[4], pt_on_p4)
J._set_end(m1.paths[3], 0, m1.paths[4].A[k])
img1 = (ink_of(m1) * 255).astype(np.uint8)

# Case 2: One merged path with vertex at Xc and stroke-linejoin="round"
m2 = m0 = Model([p.copy() for p in paths0], 257, 255)
# Merge p2 and p4 at end 0
# p2 goes from node 9 (bottom-right) to node 1 (top-right).
# If we reverse p2: it goes from node 1 (top-right) around to node 9 (bottom-right).
# p4 goes from node 0 (top-right) down to node 2 (bottom-right).
# So: reversed(p2) followed by reversed(p4) -> or p4 followed by reversed(p2) -> is a closed loop!
# Or: p2 goes around to top-right, then turns into p4 going down to bottom-right:
# Let's inspect p2.A and p4.A order:
# p2: A[0] is top-right, A[-1] is bottom-right.
# p4: A[0] is top-right, A[-1] is bottom-right.
# So if we reverse p2: p2_rev has A[0]=bottom-right, A[-1]=top-right.
# Then p4 has A[0]=top-right, A[-1]=bottom-right.
# Joining p2_rev and p4 gives a path from bottom-right -> around cuff -> top-right corner -> down right side -> bottom-right!
p2_rev = FN._reversed(p2)
# Set top-right corner vertex to Xc:
p2_rev.A[-1] = Xc.copy()
p2_rev.Hin[-1] = p2_rev.A[-2] + (Xc - p2_rev.A[-2]) * 0.66
p4_copy = p4.copy()
p4_copy.A[0] = Xc.copy()
p4_copy.Hout[0] = Xc + (p4_copy.A[1] - Xc) * 0.33

# Combine p2_rev and p4_copy:
A_comb = np.vstack([p2_rev.A, p4_copy.A[1:]])
Hin_comb = np.vstack([p2_rev.Hin, p4_copy.Hin[1:]])
Hout_comb = np.vstack([p2_rev.Hout[:-1], p4_copy.Hout])
Hin_comb[len(p2_rev.A) - 1] = Xc - np.array([3.0, 0.0]) # coming from left
Hout_comb[len(p2_rev.A) - 1] = Xc + np.array([0.0, 3.0]) # going down
p_merged = Path(A_comb, Hin_comb, Hout_comb, p2.w, join="round", ml=4.0, closed=False)

# Build m2 with p_merged instead of p2 and p4
other_paths2 = [p.copy() for idx, p in enumerate(paths0) if idx not in (2, 4)]
p3_copy2 = other_paths2[2] # was p3
pt_on_m, _ = J._nearest_on(p_merged, p3_copy2.A[0])
J._set_end(p3_copy2, 0, pt_on_m)
k2 = J.insert_anchor(p_merged, pt_on_m)
J._set_end(p3_copy2, 0, p_merged.A[k2])

m2 = Model([p_merged] + other_paths2, 257, 255)
img2 = (ink_of(m2) * 255).astype(np.uint8)

# Case 3: Rounded fillet arc at corner (radius R = 10 px)
# Instead of sharp vertex Xc, an arc between [77.16, 104.81] and [88.44, 116.09]
R = 10.0
kappa = 0.55228475 * R
P_start = np.array([Xc[0] - R, Xc[1]]) # [78.44, 106.24]
P_end   = np.array([Xc[0], Xc[1] + R]) # [88.44, 116.24]
# In p_merged: corner node was at index len(p2_rev.A) - 1.
# Replace that single corner node by a smooth bezier curve:
# Node at P_start with Hout = P_start + [kappa, 0]
# Node at P_end with Hin = P_end - [0, kappa]
idx_c = len(p2_rev.A) - 1
A_arc = np.insert(A_comb, idx_c + 1, P_end, axis=0)
Hin_arc = np.insert(Hin_comb, idx_c + 1, P_end - np.array([0.0, kappa]), axis=0)
Hout_arc = np.insert(Hout_comb, idx_c + 1, P_end + np.array([0.0, 3.0]), axis=0)

A_arc[idx_c] = P_start
Hin_arc[idx_c] = P_start - np.array([3.0, 0.0])
Hout_arc[idx_c] = P_start + np.array([kappa, 0.0])

p_arc = Path(A_arc, Hin_arc, Hout_arc, p2.w, join="round", ml=4.0, closed=False)
other_paths3 = [p.copy() for idx, p in enumerate(paths0) if idx not in (2, 4)]
p3_copy3 = other_paths3[2]
pt_on_arc, _ = J._nearest_on(p_arc, p3_copy3.A[0])
J._set_end(p3_copy3, 0, pt_on_arc)
k3 = J.insert_anchor(p_arc, pt_on_arc)
J._set_end(p3_copy3, 0, p_arc.A[k3])

m3 = Model([p_arc] + other_paths3, 257, 255)
img3 = (ink_of(m3) * 255).astype(np.uint8)

# Save comparison of all 3
c1 = cv2.resize(img1[95:130, 70:105], (150, 150), interpolation=cv2.INTER_NEAREST)
c2 = cv2.resize(img2[95:130, 70:105], (150, 150), interpolation=cv2.INTER_NEAREST)
c3 = cv2.resize(img3[95:130, 70:105], (150, 150), interpolation=cv2.INTER_NEAREST)

comp = np.hstack([c1, c2, c3])
cv2.imwrite('scratch/compare_corner_styles.png', comp)
print("Saved compare_corner_styles.png: [Case 1: 2 paths meeting at Xc | Case 2: 1 merged path with round join | Case 3: Bezier fillet arc]")
