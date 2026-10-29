import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
from linework.doctor import ink_of, Doctor
import linework.joints as J
import linework.finisher as FN

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, 257, 255)
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)
doctor0 = Doctor(D0)

# Function to merge corners with round corner support
def merge_round_corners(m: Model, pair_info, D, joint_ends=None):
    i, ei, j, ej, Xc = pair_info
    m = m.copy()
    P, Q = m.paths[i], m.paths[j]
    P = P if ei == 1 else FN._reversed(P)
    Q = Q if ej == 0 else FN._reversed(Q)
    w = max(P.w, Q.w)
    
    # Check if corner is round by looking at ink at Xc
    ix, iy = int(np.clip(round(Xc[0]), 0, D.shape[1]-1)), int(np.clip(round(Xc[1]), 0, D.shape[0]-1))
    is_round = D[iy, ix] < 0.70
    print(f"Corner at {np.round(Xc, 1)}: D={D[iy, ix]:.2f}, is_round={is_round}")
    
    gP = FN.end_geometry(P, 1)
    gQ = FN.end_geometry(Q, 0)
    tP = gP[1] if gP is not None else J._local_end_dir(P, 1)
    tQ = gQ[1] if gQ is not None else J._local_end_dir(Q, 0)
    
    # If round, find optimal radius R
    if is_round:
        # Search R between 0.6 * w and 1.4 * w
        best_R = 1.0 * w
        best_diff = 999.0
        # Diag direction outside corner: opposite of tP - tQ
        # Actually test R=1.0*w first
        R = 1.0 * w
        kappa = 0.55228475 * R
        P_start = Xc - R * tP
        P_end   = Xc + R * tQ
        
        # P ends at P_start, with handle into corner
        # Q starts at P_end, with handle away from corner
        P_mod = P.copy()
        Q_mod = Q.copy()
        
        # Set last node of P_mod to P_start, and outgoing handle
        P_mod.A[-1] = P_start.copy()
        P_mod.Hin[-1] = P_start - tP * (w / 3.0)
        P_mod.Hout[-1] = P_start + tP * kappa
        
        # Set first node of Q_mod to P_end, and incoming handle
        Q_mod.A[0] = P_end.copy()
        Q_mod.Hin[0] = P_end - tQ * kappa
        Q_mod.Hout[0] = P_end + tQ * (w / 3.0)
        
        # Combine P_mod and Q_mod
        A = np.vstack([P_mod.A, Q_mod.A])
        Hin = np.vstack([P_mod.Hin, Q_mod.Hin])
        Hout = np.vstack([P_mod.Hout, Q_mod.Hout])
        
        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.25 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            Hin[0] = Hin[-1].copy()
            Hout[-1] = Hout[0].copy()
            closed = True
        p_new = FN._clean_seam(Path(A, Hin, Hout, w_merged, "round", 4.0, closed))
        m.paths[i] = p_new
        m.paths = [p for k, p in enumerate(m.paths) if k != j]
    else:
        # Sharp miter corner
        m = FN.merge_corners(m, [(i, 1, j, 0, Xc)])
    
    # Snap other ends
    if joint_ends:
        p_merged = m.paths[i]
        for (k_idx, e_k) in joint_ends:
            actual_k = k_idx if k_idx < j else (k_idx - 1)
            if actual_k == i or actual_k >= len(m.paths) or k_idx == j:
                continue
            pk = m.paths[actual_k]
            end_pt = pk.A[0 if e_k == 0 else -1]
            f = p_merged.flat(0.25)
            k_near = int(np.argmin(np.linalg.norm(f - end_pt, axis=1)))
            pt_on = f[k_near]
            if e_k == 0:
                pk.A[0] = pt_on.copy()
                pk.Hout[0] = pt_on.copy()
            else:
                pk.A[-1] = pt_on.copy()
                pk.Hin[-1] = pt_on.copy()
            ak = J.insert_anchor(p_merged, pt_on)
            if e_k == 0:
                pk.A[0] = p_merged.A[ak].copy()
            else:
                pk.A[-1] = p_merged.A[ak].copy()
    return m

# Test on m0
js = J.find_joints(m0)
j_cuff = [j for j in js if len(j.ends) == 3 and any(np.linalg.norm(np.array([90.73, 112.61]) - m0.paths[p].A[0 if e==0 else -1]) < 5 for p, e in j.ends)][0]
cp = J.corner_continuation_pairs(m0, j_cuff, D0)[0]
print("Corner pair:", cp)

m_merged = merge_round_corners(m0, cp, D0, joint_ends=j_cuff.ends)
print("Initial soft:", doctor0.soft(ink_of(m0)), "-> Merged soft:", doctor0.soft(ink_of(m_merged)))
print("Initial topo:", FN._topo(m0), "-> Merged topo:", FN._topo(m_merged))

img_res = (ink_of(m_merged) * 255).astype(np.uint8)
cv2.imwrite('scratch/cuff_merged_round_perfect.png', cv2.resize(img_res[95:135, 65:110], (200, 200), interpolation=cv2.INTER_NEAREST))
print("Saved cuff_merged_round_perfect.png")
