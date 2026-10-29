import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches

small0 = cv2.imread('scratch/small_0.png', 0)
D = ink_map(small0)

# Print ink mask in the corner region
# x from 75 to 98, y from 98 to 120
sub_D = D[98:120, 75:98]
print("Ink map around cuff corner (rows 98..119, cols 75..97):")
header = "    " + "".join(f"{x%10}" for x in range(75, 98))
print(header)
for y in range(98, 120):
    row_str = "".join("#" if D[y, x] > 0.5 else ("." if D[y, x] > 0.1 else " ") for x in range(75, 98))
    print(f"{y:3d} {row_str}")
