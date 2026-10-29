import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
import linework.joints as J
import linework.finisher as FN
from linework.doctor import Doctor, ink_of
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

# Let's write the proposed corner_continuation_pairs and test it directly with finisher & joints
def corner_continuation_pairs(m: Model, J_joint: J.Joint, D):
    ends = J_joint.ends
    if len(ends) < 3:
        return []
    best_pair = None
    best_score = 999.0
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            k, ek = ends[y]
            if i >= len(m.paths) or k >= len(m.paths) or i == k:
                continue
            P, Q = m.paths[i], m.paths[k]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            w = max(wa, wb)
            gP = FN.end_geometry(P, ei)
            gQ = FN.end_geometry(Q, ek)
            cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei == 0 else -1], J._local_end_dir(P, ei))
            cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ek == 0 else -1], J._local_end_dir(Q, ek))
            cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
            if abs(cr) < 0.40:
                continue
            sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / cr
            sQ = float((cQ - cP)[0] * tP[1] - (cQ - cP)[1] * tP[0]) / cr
            if sP < -0.2 * w or sQ < -0.2 * w:
                continue
            Xc = cP + sP * tP
            dist_j = float(np.linalg.norm(Xc - J_joint.xy))
            if dist_j > 1.35 * w:
                continue
            dot = float(tP @ tQ)
            if abs(dot) < 0.65:
                score = abs(dot) + 0.5 * (dist_j / w)
                if score < best_score:
                    best_score = score
                    best_pair = (i, ei, k, ek, Xc)
    if best_pair is not None:
        return [best_pair]
    return []

# Patched merge_corners with 3rd branch snapping and closed loop support
def enhanced_merge_corners(m: Model, pairs, joint_ends=None):
    m = m.copy()
    dead = set()
    for item in pairs:
        i, ei, j, ej = item[:4]
        Xc_override = item[4] if len(item) > 4 else None
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else FN._reversed(P)
        Q = Q if ej == 0 else FN._reversed(Q)
        mid = (P.A[-1] + Q.A[0]) / 2
        w_max = max(P.w, Q.w)
        X_corner = Xc_override
        if X_corner is None:
            gP = FN.end_geometry(P, 1)
            gQ = FN.end_geometry(Q, 0)
            if gP is not None and gQ is not None:
                cP, tP = gP[0], gP[1]
                cQ, tQ = gQ[0], gQ[1]
                den = float(tP[0] * tQ[1] - tP[1] * tQ[0])
                if abs(den) >= 0.15:
                    sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / den
                    Xc = cP + sP * tP
                    if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                        X_corner = Xc
        corner_pt = mid if X_corner is None else X_corner
        dP, dQ = corner_pt - P.A[-1], corner_pt - Q.A[0]
        A = np.vstack([P.A, Q.A[1:]])
        Hin = np.vstack([P.Hin, Q.Hin[1:]])
        Hout = np.vstack([P.Hout[:-1], Q.Hout])
        idx = len(P.A) - 1
        A[idx] = corner_pt
        Hin[idx] = P.Hin[-1] + dP
        Hout[idx] = Q.Hout[0] + dQ
        if idx >= 1:
            vP = A[idx] - A[idx - 1]
            Hout[idx - 1] = A[idx - 1] + vP / 3.0
            Hin[idx] = A[idx] - vP / 3.0
        if idx + 1 < len(A):
            vQ = A[idx + 1] - A[idx]
            Hout[idx] = A[idx] + vQ / 3.0
            Hin[idx + 1] = A[idx + 1] - vQ / 3.0
        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.25 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            Hin[0] = Hin[-1].copy()
            Hout[-1] = Hout[0].copy()
            closed = True
        m.paths[i] = FN._clean_seam(Path(A, Hin, Hout, w_merged, "round", 4.0, closed))
        dead.add(j)
    
    # Snap any other ends that met at the same joint
    if joint_ends:
        merged_idx = pairs[0][0]
        p_merged = m.paths[merged_idx]
        for (k_idx, e_k) in joint_ends:
            if k_idx in dead or k_idx == merged_idx:
                continue
            pk = m.paths[k_idx]
            end_pt = J._end_pt(pk, e_k)
            pt_on, d_on = J._nearest_on(p_merged, end_pt)
            if d_on <= 1.5 * p_merged.w:
                J._set_end(pk, e_k, pt_on)
                ak = J.insert_anchor(p_merged, pt_on)
                J._set_end(pk, e_k, p_merged.A[ak])
    
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m

print("Enhanced functions defined.")

# Test on m0
data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, 257, 255)
small0 = cv2.imread('scratch/small_0.png', 0)
D0 = ink_map(small0)
doctor0 = Doctor(D0)

js0 = J.find_joints(m0)
j_cuff = [j for j in js0 if len(j.ends) == 3 and any(np.linalg.norm(np.array([90.73, 112.61]) - m0.paths[p].A[0 if e==0 else -1]) < 5 for p, e in j.ends)][0]
print("Found cuff joint:", j_cuff)

cp0 = corner_continuation_pairs(m0, j_cuff, D0)
print("Detected corner continuation pairs:", cp0)

if cp0:
    m_test0 = enhanced_merge_corners(m0, cp0, joint_ends=j_cuff.ends)
    print("Initial topo:", FN._topo(m0), "-> Merged topo:", FN._topo(m_test0))
    print("Initial soft:", doctor0.soft(ink_of(m0)), "-> Merged soft:", doctor0.soft(ink_of(m_test0)))
    
    img_res = (ink_of(m_test0) * 255).astype(np.uint8)
    cv2.imwrite('scratch/test_merged_cuff0.png', cv2.resize(img_res[95:135, 65:110], (200, 200), interpolation=cv2.INTER_NEAREST))
    print("Saved test_merged_cuff0.png")

# Test on Icon 1
data1 = json.load(open('scratch/m1_current.json'))
paths1 = [Path.from_dict(p) for p in data1['paths']]
small1 = cv2.imread('scratch/small_1.png', 0)
H1, W1 = small1.shape
m1 = Model(paths1, W1, H1)
D1 = ink_map(small1)
doctor1 = Doctor(D1)

js1 = J.find_joints(m1)
j_cuff1 = [j for j in js1 if len(j.ends) == 3 and any(np.linalg.norm(np.array([89.11, 144.11]) - m1.paths[p].A[0 if e==0 else -1]) < 5 for p, e in j.ends)][0]
print("\nIcon 1 found cuff joint:", j_cuff1)

cp1 = corner_continuation_pairs(m1, j_cuff1, D1)
print("Icon 1 detected corner continuation pairs:", cp1)

if cp1:
    m_test1 = enhanced_merge_corners(m1, cp1, joint_ends=j_cuff1.ends)
    print("Icon 1 Initial topo:", FN._topo(m1), "-> Merged topo:", FN._topo(m_test1))
    print("Icon 1 Initial soft:", doctor1.soft(ink_of(m1)), "-> Merged soft:", doctor1.soft(ink_of(m_test1)))
    
    img_res1 = (ink_of(m_test1) * 255).astype(np.uint8)
    cv2.imwrite('scratch/test_merged_cuff1.png', cv2.resize(img_res1[115:155, 65:110], (200, 200), interpolation=cv2.INTER_NEAREST))
    print("Saved test_merged_cuff1.png")
