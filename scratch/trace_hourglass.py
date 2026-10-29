import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework import pipeline as P, chains as C
from linework.trace import ink_map, refined_branches
from linework.geom import resample, unit

gray = cv2.imread("data/ea3cb3bb04a7/original.png", cv2.IMREAD_GRAYSCALE)
W, H, jobs = P.process_sheet(gray)
_, crop, off = jobs[4]
D = ink_map(crop)
br = refined_branches(D)
for b in br:
    b["pts"] = resample(np.asarray(b["pts"], float), 1.0)
W0 = C.global_width(br)

def oriented(b, e):
    return b["pts"] if e == 1 else b["pts"][::-1]

def end_info(b, e, T):
    q = oriented(b, e)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
    n = len(q)
    if L[-1] > 1.8 * T and n >= 12:
        k_near = n - 1 - int(np.searchsorted(L, 0.25 * T))
        k_mid  = n - 1 - int(np.searchsorted(L, 0.65 * T))
        k_far  = n - 1 - int(np.searchsorted(L, min(2.2 * T, 0.9 * L[-1])))
        k_near = min(n - 2, max(k_near, k_mid + 2))
        if k_near > k_mid > k_far >= 0:
            d_near = unit(q[k_near] - q[k_mid])
            d_far  = unit(q[k_mid] - q[k_far])
            d_tip  = unit(q[-1] - q[k_near])
            k_vfar = n - 1 - int(np.searchsorted(L, min(2.8 * T, 0.95 * L[-1])))
            straight_before = (k_far > k_vfar + 1) and (d_far @ unit(q[k_far] - q[k_vfar]) > np.cos(np.radians(8)))
            if (d_near @ d_far < np.cos(np.radians(32)) and d_tip @ d_near >= np.cos(np.radians(22))) or (
                straight_before and d_near @ d_far < np.cos(np.radians(18))
            ):
                k = max(n - 1 - int(np.searchsorted(L, 0.35 * T)), 2)
                return dict(A=q[k].copy(), d=d_near, kept=q[: k + 1], full=q, branch="bend")
    T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
    k = n - 1 - int(np.searchsorted(L, T_eff))
    k = max(k, 2)
    lo = max(k - 14, 0)
    d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
    k_neck = min(n - 2, max(k + 3, n - 1 - int(np.searchsorted(L, 0.35 * T_eff))))
    if k_neck > k:
        d_neck = unit(q[k_neck] - q[k])
        d_tip0 = unit(q[-1] - q[k_neck])
        if d_neck @ d < np.cos(np.radians(20)) and d_tip0 @ d_neck >= np.cos(np.radians(22)):
            return dict(A=q[k_neck].copy(), d=d_neck, kept=q[: k_neck + 1], full=q, branch="neck")
    return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q, branch="std")

ends = {}
for i, b in enumerate(br):
    if b["sj"] > 0:
        ends.setdefault(b["sj"], []).append((i, 0))
    if b["ej"] > 0:
        ends.setdefault(b["ej"], []).append((i, 1))
info = {}
for j, l in ends.items():
    w = float(np.mean([br[i]["w"] for i, _ in l]))
    for (i, e) in l:
        info[(i, e)] = end_info(br[i], e, w)

for j in (3, 4, 5, 6, 7, 8, 23, 26, 27, 28, 29, 30):
    l = ends[j]
    w = float(np.mean([br[i]["w"] for i, _ in l]))
    print(f"=== j={j} (w={w:.1f}) ===")
    for a in l:
        print(f"  end {a}: len={len(br[a[0]]['pts'])}, mode={info[a]['branch']}, A={info[a]['A'].round(1).tolist()}, d={info[a]['d'].round(2).tolist()}")
    for x in range(len(l)):
        for y in range(x + 1, len(l)):
            a, b = l[x], l[y]
            ta, tb = info[a]["d"], info[b]["d"]
            ang = np.degrees(np.arccos(np.clip(-ta @ tb, -1, 1)))
            v = info[b]["A"] - info[a]["A"]
            nv = np.linalg.norm(v)
            if nv > 0.25 * w:
                u = v / nv
                ang_c = max(np.degrees(np.arccos(np.clip(ta @ u, -1, 1))), np.degrees(np.arccos(np.clip((-tb) @ u, -1, 1))))
                eff_ang = max(ang, 0.85 * ang_c)
            else:
                eff_ang = ang
            print(f"  pair {a} - {b}: ang={ang:.1f}, eff_ang={eff_ang:.1f}")
