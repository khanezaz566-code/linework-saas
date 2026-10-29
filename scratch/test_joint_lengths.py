import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, 257, 255)
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)

js = J.find_joints(m0)
for idx, j in enumerate(js):
    if len(j.ends) >= 3:
        cp = J.corner_continuation_pairs(m0, j, D0)
        print(f"Joint {idx} (xy={np.round(j.xy, 1)}): corner pairs = {cp}")
