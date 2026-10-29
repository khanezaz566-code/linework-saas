import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C, joints as JN, rings as RG, finisher as FN
from linework.fitting import initial_model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

# Check icon_3 (Compass) at 1x and 2x
for s in (1, 2):
    crop = jobs[3][1]
    Du = TR.ink_map(cv2.resize(crop, (crop.shape[1]*s, crop.shape[0]*s), interpolation=cv2.INTER_CUBIC)) if s > 1 else TR.ink_map(crop)
    br = TR.refined_branches(Du)
    ch, W0 = C.build_chains(br)
    print(f"icon_3 at s={s}: br={len(br)}, ch={len(ch)}, W0={W0:.2f}")
    for ci, c in enumerate(ch):
        pts = c["pts"] / s
        # Check if chain passes near N tip (236, 123), W tip (124, 236), SW tip (160, 312), NW tip (181, 180)
        for name, pt in [("N", [236.5, 123.6]), ("W", [124.1, 235.8]), ("SW", [160.7, 312.3]), ("NW", [181.0, 180.0])]:
            d = np.min(np.linalg.norm(pts - pt, axis=1))
            if d < 15:
                print(f"  [s={s}] near {name}: ch {ci} len={len(c['pts'])/s:.1f} p0={pts[0].round(1).tolist()} -> p1={pts[-1].round(1).tolist()}")
