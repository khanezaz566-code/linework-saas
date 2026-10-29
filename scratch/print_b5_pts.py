import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)
br = refined_branches(D)

b5 = br[5]
print("First 15 pts of Branch 5:")
for i, pt in enumerate(b5["pts"][:15]):
    print(f"  {i}: {np.round(pt, 2)}")
