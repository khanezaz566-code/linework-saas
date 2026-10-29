import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C
from linework.geom import resample, unit

# Test the updated end_info on icon_1 (Engine), icon_4 (Winch), icon_3 (Compass), and Hourglass
gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

def check_chains_with_new_end_info(crop, label):
    D = TR.ink_map(crop)
    br = TR.refined_branches(D)
    ch, W0 = C.build_chains(br)
    print(f"=== {label}: br={len(br)}, ch={len(ch)}, W0={W0:.2f} ===")
    for i, c in enumerate(ch):
        pts = c["pts"]
        print(f"  ch {i:2d}: len={len(pts):3d}, p0={pts[0].round(1).tolist()} -> mid={pts[len(pts)//2].round(1).tolist()} -> p1={pts[-1].round(1).tolist()}")

if __name__ == "__main__":
    check_chains_with_new_end_info(jobs[1][1], "icon_1 (Engine) BEFORE")
