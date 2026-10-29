import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework import pipeline as P, chains as C
from linework.trace import ink_map, refined_branches
from linework.geom import resample, unit

def oriented(b, e):
    return b["pts"] if e == 1 else b["pts"][::-1]

def new_end_info(b, e, T):
    q = oriented(b, e)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
    n = len(q)
    if L[-1] > 2.2 * T and n >= 14:
        k_near = n - 1 - int(np.searchsorted(L, 0.30 * T))
        k_mid  = n - 1 - int(np.searchsorted(L, 0.70 * T))
        k_ neck_far = n - 1 - int(np.searchsorted(L, 1.35 * T))
        k_far  = n - 1 - int(np.searchsorted(L, min(2.4 * T, 0.9 * L[-1])))
        k_near = min(n - 2, max(k_near, k_mid + 2))
        if k_near > k_mid > k_neck_far > k_far >= 0:
            d_near = unit(q[k_near] - q[k_mid])
            d_mid  = unit(q[k_mid] - q[k_neck_far])
            d_far  = unit(q[k_neck_far] - q[k_far])
            d_tip  = unit(q[-1] - q[k_near])
            # Real corner at ~1.4-2.2*T before junction: d_mid and d_near both point along the new post-corner direction
            if d_mid @ d_far < np.cos(np.radians(25)) and d_near @ d_mid >= np.cos(np.radians(18)) and d_tip @ d_near >= np.cos(np.radians(22)):
                k = max(n - 1 - int(np.searchsorted(L, 0.45 * T)), 2)
                return dict(A=q[k].copy(), d=unit(q[k_near] - q[k_neck_far]), kept=q[: k + 1], full=q, branch="bend")
    T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
    k = n - 1 - int(np.searchsorted(L, T_eff))
    k = max(k, 2)
    lo = max(k - 14, 0)
    d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
    return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q, branch="std")
