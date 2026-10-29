import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.trace import ink_map, refined_branches

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
print(f"Total branches: {len(branches)}")
for bi, b in enumerate(branches):
    # find points in [290..340, 310..340]
    pts = b['pts']
    in_box = [p for p in pts if 290 <= p[0] <= 340 and 310 <= p[1] <= 340]
    if in_box:
        print(f"Branch {bi}: {len(in_box)} points in fluke region")
        # print the sequence of points
        for p in pts:
            if 290 <= p[0] <= 340 and 310 <= p[1] <= 340:
                print(f"  {p}")
