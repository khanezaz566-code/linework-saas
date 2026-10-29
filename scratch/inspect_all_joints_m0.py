import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, 257, 255)

js = J.find_joints(m0)
for idx, j in enumerate(js):
    print(f"\nJoint {idx}: {j.kind} at {np.round(j.xy, 1)}, ends={j.ends}")
    for p, e in j.ends:
        path = m0.paths[p]
        print(f"  Path {p} (len={path.length():.1f}): A[0]={np.round(path.A[0], 1)}, A[-1]={np.round(path.A[-1], 1)}")
