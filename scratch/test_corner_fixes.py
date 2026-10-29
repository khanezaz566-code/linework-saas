import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN
from linework.doctor import Doctor, ink_of

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, data0.get('width', 0), data0.get('height', 0))
small0 = cv2.imread('scratch/small_0.png', 0)

# Current rendering of cuff corner
img_orig = (ink_of(m0) * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_current.png', cv2.resize(img_orig[95:130, 70:105], (200, 200), interpolation=cv2.INTER_NEAREST))

print("Baseline saved. Let's inspect Path 2 and Path 4.")
p2 = m0.paths[2]
p4 = m0.paths[4]
p3 = m0.paths[3]

print(f"p2 A[0]={p2.A[0]}, A[1]={p2.A[1]}")
print(f"p4 A[0]={p4.A[0]}, A[1]={p4.A[1]}")
print(f"p3 A[0]={p3.A[0]}, A[1]={p3.A[1]}")
