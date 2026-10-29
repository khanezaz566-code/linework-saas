import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN
from linework.doctor import Doctor, ink_of

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, data0.get('width', 257), data0.get('height', 255))
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)
doctor0 = Doctor(D0)

# Cuff top horizontal line: y ≈ 104.8.
# Cuff right vertical line: x ≈ 88.44.
# Intersection is at C = [88.44, 104.81].
# Corner radius: let's use R = 11.28 px (so start at x = 88.44 - 11.28 = 77.16, end at y = 104.81 + 11.28 = 116.09).
# Standard cubic Bezier arc for a 90 degree quadrant of radius R:
# kappa = 4/3 * (sqrt(2) - 1) ≈ 0.55228475 * R
R = 11.28
kappa = 0.55228475 * R
# Start of arc: P0 = [77.16, 104.81], tangent is [+1, 0], handle Hout0 = P0 + [kappa, 0]
# End of arc: P1 = [88.44, 116.09], tangent is [0, +1], handle Hin1 = P1 - [0, kappa]
P0 = np.array([77.16, 104.81])
Hout0 = P0 + np.array([kappa, 0.0])
P1 = np.array([88.44, 116.09])
Hin1 = P1 - np.array([0.0, kappa])

# Let's test making Path 2 and Path 4 into one continuous cuff path with this rounded corner!
p2 = m0.paths[2]
p4 = m0.paths[4]

# Path 2 has nodes 1..9 (cuff top, left, bottom)
# Path 4 has nodes 1..2 (cuff right)
# Let's combine them:
# Node 1 of p2 is at P0.
# We replace node 0 of p2 with P1 (or connect through P0->P1).
# In p2: Node 1 is [77.16, 104.81]. Its Hout towards node 0 will be Hout0!
# Then the next node is P1 = [88.44, 116.09], with Hin = Hin1, Hout = P1 + [0, 1.5] (downwards)!
# Then node 1 of p4 is at [88.44, 120.85]!
p_cuff = p2.copy()
# p_cuff currently goes: node 0 [90.7, 112.6] -> node 1 [77.2, 104.8] -> ... -> node 9 [88.5, 202.7]
# Let's reverse p4 so it goes from [88.44, 202.75] up to [88.44, 120.85]
# Or join p2 (from bottom-right around to top-right) and p4 (from top-right down to bottom-right):
# Notice: p2 node 9 is bottom-right [88.5, 202.7].
# p2 node 1 is top-right [77.16, 104.81].
# p2 node 0 was [90.73, 112.61].
# If we replace node 0 of p2 with:
# A[0] = P1, Hin[0] = Hin1, Hout[0] = P1 + [0, (120.85 - 116.09)/3]
# and set Hout of node 1 to Hout0!
# And then attach p4 nodes (120.85 down to 202.75):

# Let's see: what if p2 and p4 stay as 2 paths, but p2 curves into p4?
# On p2:
mB = m0.copy()
p2B = mB.paths[2]
p4B = mB.paths[4]
p3B = mB.paths[3]

# In p2B: A[1] is [77.16, 104.81].
# Set A[0] = P1 = [88.44, 116.09].
# Set Hin[0] = Hin1.
# Set Hout[1] (which points towards node 0) = Hout0!
p2B.A[0] = P1.copy()
p2B.Hin[0] = Hin1.copy()
p2B.Hout[0] = P1.copy()
p2B.Hout[1] = Hout0.copy()

# On p4B:
# A[0] was [90.73, 112.61], A[1] is [88.44, 120.85].
# Move A[0] to P1 = [88.44, 116.09]!
p4B.A[0] = P1.copy()
p4B.Hin[0] = P1.copy()
p4B.Hout[0] = P1 + (p4B.A[1] - P1) / 3.0
p4B.Hin[1] = p4B.A[1] - (p4B.A[1] - P1) / 3.0

# On p3B (thumb):
# Snap end 0 to nearest on p4B (or p2B):
pt_on_p4, d4 = J._nearest_on(p4B, p3B.A[0])
J._set_end(p3B, 0, pt_on_p4)
k = J.insert_anchor(p4B, pt_on_p4)
J._set_end(p3B, 0, p4B.A[k])

print("Approach B soft:", doctor0.soft(ink_of(mB)), "topo:", FN._topo(mB))
imgB = (ink_of(mB) * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_approachB_round.png', cv2.resize(imgB[95:130, 70:105], (200, 200), interpolation=cv2.INTER_NEAREST))
print("Saved cuff_approachB_round.png")
