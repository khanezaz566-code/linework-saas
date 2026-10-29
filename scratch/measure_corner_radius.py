import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map
from linework.model import Path
import json

data0 = json.load(open('scratch/m0_current.json'))
p2 = Path.from_dict(data0['paths'][2])

print("Top-left corner of cuff on p2:")
print(f"Node 2: {p2.A[2]}")
print(f"Node 3: {p2.A[3]}")
print(f"Node 4: {p2.A[4]}")
print(f"Distance Node 2 to Node 4: {np.linalg.norm(p2.A[2] - p2.A[4]):.2f}")
# Centerline points on the top-left corner:
f2 = p2.segs()[2] # segment between node 2 and node 3
f3 = p2.segs()[3] # segment between node 3 and node 4
# Let's sample points
from linework.geom import bez
t = np.linspace(0, 1, 20)
pts = np.vstack([bez(f2, t), bez(f3, t)])
# Fit circle to top-left corner centerline:
from linework.rings import _kasa
cx, cy, r = _kasa(pts)
print(f"Top-left corner circle fit: center=({cx:.1f}, {cy:.1f}), radius={r:.2f} px")
