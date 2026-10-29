import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, lessons as LS, joints as JN
from linework.trace import ink_map
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for idx in [0, 1, 2, 4, 5]:
    k, crop, off = jobs[idx]
    D = ink_map(crop)
    key = LS.crop_key(crop, "standard", 0.0)
    mf = Model.from_json(LS.best_get(key)["model"])
    js = JN.find_joints(mf)
    print(f"=== ICON {idx} ===")
    for J in js:
        bad = JN.check_joint(mf, J)
        if bad:
            print(f"  FAIL Joint kind={J.kind} xy={np.round(J.xy, 1)} ends={J.ends} thr={J.through} bad={bad}")
            for i, e in J.ends:
                pt = JN._end_pt(mf.paths[i], e)
                d_thr = [JN._nearest_on(mf.paths[j], pt)[1] for j in J.through if j != i]
                print(f"    end ({i},{e}) at {np.round(pt, 2)}, d_thr={np.round(d_thr, 3)}")
