import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches
from linework.chains import global_width, resample, unit

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)
br = refined_branches(D)
W0 = global_width(br)

print("Junction 1 branches:")
for b_idx in [3, 4, 5]:
    b = br[b_idx]
    pts = b["pts"]
    print(f"Branch {b_idx}: len={len(pts)}, start={np.round(pts[0], 1)}, end={np.round(pts[-1], 1)}, sj={b['sj']}, ej={b['ej']}")
    # Print direction near start (first 10 pts)
    d = unit(pts[min(10, len(pts)-1)] - pts[0])
    print(f"  dir away from start: {np.round(d, 2)}")
