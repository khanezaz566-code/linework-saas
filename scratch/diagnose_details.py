import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, trace as TR, chains as C, joints as JN, rings as RG, finisher as FN

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

# 1. Inspect icon_3 (Compass) junctions with free-tip spurs
D3 = TR.ink_map(jobs[3][1])
br3 = TR.refined_branches(D3)
W0_3 = C.global_width(br3)
ends3 = {}
for i, b in enumerate(br3):
    if b["sj"] > 0: ends3.setdefault(b["sj"], []).append((i, 0))
    if b["ej"] > 0: ends3.setdefault(b["ej"], []).append((i, 1))
print("=== icon_3 (Compass) free-tip junctions ===")
for j, l in ends3.items():
    if any(br3[i]["sj"] == 0 or br3[i]["ej"] == 0 for i, _ in l):
        print(f"  j={j}: members={[(i, e, len(br3[i]['pts']), br3[i]['sj'], br3[i]['ej']) for i, e in l]}")

# 2. Inspect icon_1 (Engine) branches around the two circular pipe mounts (y in 130..210)
D1 = TR.ink_map(jobs[1][1])
br1 = TR.refined_branches(D1)
print("\n=== icon_1 (Engine) pipe mount branches ===")
for i, b in enumerate(br1):
    pts = np.asarray(b["pts"])
    if (130 < pts[:, 1].mean() < 225) and (130 < pts[:, 0].mean() < 360):
        print(f"  br {i:2d}: len={len(pts):3d}, sj={b['sj']:2d}, ej={b['ej']:2d}, p0={pts[0].round(1).tolist()} -> pm={pts[len(pts)//2].round(1).tolist()} -> p1={pts[-1].round(1).tolist()}")

# 3. Inspect icon_4 (Winch) top cap branches br 1..5 points
D4 = TR.ink_map(jobs[4][1])
br4 = TR.refined_branches(D4)
print("\n=== icon_4 (Winch) br 1..5 points ===")
for i in (0, 1, 2, 3, 4, 5, 9):
    pts = np.asarray(br4[i]["pts"])
    print(f"  br {i}: len={len(pts)}, ymin={pts[:,1].min():.1f}, ymax={pts[:,1].max():.1f}, p0={pts[0].round(1).tolist()} -> mid={pts[len(pts)//2].round(1).tolist()} -> p1={pts[-1].round(1).tolist()}")
