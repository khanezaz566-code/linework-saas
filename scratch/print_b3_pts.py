import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)
br = refined_branches(D)

b3 = br[3]
print("First 25 pts of Branch 3:")
for i, pt in enumerate(b3["pts"][:25]):
    print(f"  {i}: {np.round(pt, 2)}")
