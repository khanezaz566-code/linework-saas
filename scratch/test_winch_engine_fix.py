import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C
from linework.geom import resample, unit, hermite, line_inter

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

# Test on icon_1 (Engine) and icon_4 (Winch)
for k in (1, 4):
    crop = jobs[k][1]
    D = TR.ink_map(crop)
    br = TR.refined_branches(D)
    print(f"=== icon_{k} ===")
    for i, b in enumerate(br):
        q = np.asarray(b["pts"], float)
        v = q[-1] - q[0]
        lv = np.linalg.norm(v)
        if lv > 1e-3:
            n_vec = np.array([-v[1], v[0]]) / lv
            arch_dev = float(np.max(np.abs((q - q[0]) @ n_vec)))
        else:
            arch_dev = 0.0
        if len(q) < 35 and arch_dev > 1.5:
            print(f"  short arch br {i:2d}: len={len(q):2d}, arch_dev={arch_dev:.2f}, p0={q[0].round(1).tolist()} -> p1={q[-1].round(1).tolist()}")
