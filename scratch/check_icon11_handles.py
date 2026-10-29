import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, lessons as LS, finisher as FN
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[11]
key = LS.crop_key(crop, "standard", 0.0)
mf = Model.from_json(LS.best_get(key)["model"])
p = mf.paths[12]
for idx in range(len(p.A)):
    print(f"node {idx}: A={np.round(p.A[idx], 1)}, Hin={np.round(p.Hin[idx], 1)}, Hout={np.round(p.Hout[idx], 1)}")
print("bad_handle_paths:", FN.bad_handle_paths(mf))
