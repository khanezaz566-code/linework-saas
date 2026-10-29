import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C
from linework.geom import resample, unit

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
D1 = TR.ink_map(jobs[1][1])
br1 = TR.refined_branches(D1)
for b in br1:
    b["pts"] = resample(np.asarray(b["pts"], float), 1.0)

for j_id in (5, 6, 7, 8):
    members = []
    for i, b in enumerate(br1):
        if b["sj"] == j_id: members.append((i, 0))
        if b["ej"] == j_id: members.append((i, 1))
    print(f"=== Junction j={j_id} ===")
    for i, e in members:
        q = br1[i]["pts"] if e == 1 else br1[i]["pts"][::-1]
        d_10 = unit(q[-10] - q[max(len(q)-24, 0)]) if len(q) >= 12 else unit(q[-1] - q[0])
        d_4  = unit(q[-4] - q[max(len(q)-12, 0)]) if len(q) >= 6 else unit(q[-1] - q[0])
        print(f"  (br {i:2d}, e={e}): len={len(q):3d}, d_10={d_10.round(2).tolist()}, d_4={d_4.round(2).tolist()}, q[-10]={q[max(len(q)-10,0)].round(1).tolist()}, q[-4]={q[max(len(q)-4,0)].round(1).tolist()}, q[-1]={q[-1].round(1).tolist()}")
