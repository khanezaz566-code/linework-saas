import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN
from linework.doctor import Doctor, ink_of

# Load m0
data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, data0.get('width', 257), data0.get('height', 255))
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)
doctor0 = Doctor(D0)

print("Original m0 soft:", doctor0.soft(ink_of(m0)), "topo:", FN._topo(m0))

# Path 2 (cuff top) and Path 4 (cuff right) meeting at (90.73, 112.61)
# Let's inspect their geometry
p2 = m0.paths[2]
p4 = m0.paths[4]
p3 = m0.paths[3]

g2 = FN.end_geometry(p2, 0)
g4 = FN.end_geometry(p4, 0)
c2, t2 = (g2[0], g2[1]) if g2 is not None else (p2.A[0], J._local_end_dir(p2, 0))
c4, t4 = (g4[0], g4[1]) if g4 is not None else (p4.A[0], J._local_end_dir(p4, 0))

cr = float(t2[0] * t4[1] - t2[1] * t4[0])
print(f"t2={np.round(t2, 2)}, t4={np.round(t4, 2)}, cross={cr:.3f}, dot={t2@t4:.3f}")

s2 = float((c4 - c2)[0] * t4[1] - (c4 - c2)[1] * t4[0]) / cr
Xc = c2 + s2 * t2
print(f"Ray intersection Xc = {np.round(Xc, 2)}")

# Approach A: Simply move ends of p2 and p4 to Xc (or reconstruct corner), and snap p3 to nearest on (p2/p4)
mA = m0.copy()
# Move p2 end 0 to Xc, p4 end 0 to Xc
J._set_end(mA.paths[2], 0, Xc)
J._set_end(mA.paths[4], 0, Xc)
# Snap p3 end 0 to nearest on p4 (or p2)
pt_on_p4, d4 = J._nearest_on(mA.paths[4], mA.paths[3].A[0])
pt_on_p2, d2 = J._nearest_on(mA.paths[2], mA.paths[3].A[0])
if d4 <= d2:
    J._set_end(mA.paths[3], 0, pt_on_p4)
    k = J.insert_anchor(mA.paths[4], pt_on_p4)
    J._set_end(mA.paths[3], 0, mA.paths[4].A[k])
else:
    J._set_end(mA.paths[3], 0, pt_on_p2)
    k = J.insert_anchor(mA.paths[2], pt_on_p2)
    J._set_end(mA.paths[3], 0, mA.paths[2].A[k])

print("Approach A soft:", doctor0.soft(ink_of(mA)), "topo:", FN._topo(mA))
imgA = (ink_of(mA) * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_approachA.png', cv2.resize(imgA[95:130, 70:105], (200, 200), interpolation=cv2.INTER_NEAREST))
print("Saved cuff_approachA.png")
