import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of

m = Model.from_json(open('data/b95d5c14c7a9/icon_4.json').read())
job = json.load(open('data/b95d5c14c7a9/job.json'))
p = m.paths[0]

# Inspect anchors near apex
print("Before fix, anchors near apex:")
for k in [12, 13, 14, 0, 1]:
    print(f"A[{k}] = {np.round(p.A[k], 2)}")

# Remove the tongue anchor A[0]/A[14]:
# A[13] is at [2432.33, 277.44]
# Ray from A[12]->A[13] and Ray from A[2]->A[1]
# Intersection Xc
A = np.delete(p.A[:-1], 0, axis=0) # remove 0
Hin = np.delete(p.Hin[:-1], 0, axis=0)
Hout = np.delete(p.Hout[:-1], 0, axis=0)

# close it
A = np.vstack([A, A[0:1]])
Hin = np.vstack([Hin, Hin[0:1]])
Hout = np.vstack([Hout, Hout[0:1]])

p_fixed = Path(A, Hin, Hout, p.w, p.join, p.ml, True)
m_fixed = Model([p_fixed], m.width, m.height)

crop = cv2.imread('scratch/b95d5c14c7a9/icon_4.png', 0)
doc = Doctor(cv2.imread('scratch/b95d5c14c7a9/icon_4.png', 0) < 128)
# Translate to local crop coords
dx = job['icons'][4]['box'][0]
dy = job['icons'][4]['box'][1]
p_local = Path(p_fixed.A - [dx, dy], p_fixed.Hin - [dx, dy], p_fixed.Hout - [dx, dy], p.w, p.join, p.ml, True)
m_local = Model([p_local], crop.shape[1], crop.shape[0])

ink = ink_of(m_local)
cv2.imwrite('scratch/heart_fixed_crevice.png', ink[60:150, 220:320] * 255)
cv2.imwrite('scratch/heart_orig_crevice.png', (crop[60:150, 220:320] < 128).astype(np.uint8) * 255)
print("Saved heart fixed crevice!")
