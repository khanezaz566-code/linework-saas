import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
from linework.doctor import ink_of, Doctor
import linework.joints as J
import linework.finisher as FN

def enhanced_merge_corners(m: Model, pairs, joint_ends=None, D=None):
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
        gP = FN.end_geometry(P, 1)
        gQ = FN.end_geometry(Q, 0)
        tP = gP[1] if gP is not None else J._local_end_dir(P, 1)
        tQ = gQ[1] if gQ is not None else J._local_end_dir(Q, 0)
        X_corner = Xc_override
        if X_corner is None:
            if gP is not None and gQ is not None:
                cP, tP_g = gP[0], gP[1]
                cQ, tQ_g = gQ[0], gQ[1]
                den = float(tP_g[0] * tQ_g[1] - tP_g[1] * tQ_g[0])
                if abs(den) >= 0.15:
                    sP = float((cQ - cP)[0] * tQ_g[1] - (cQ - cP)[1] * tQ_g[0]) / den
                    Xc = cP + sP * tP_g
                    if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                        X_corner = Xc
        corner_pt = mid if X_corner is None else X_corner
        
        # Check if corner is round
        is_round = False
        if D is not None:
            ix = int(np.clip(round(corner_pt[0]), 0, D.shape[1] - 1))
            iy = int(np.clip(round(corner_pt[1]), 0, D.shape[0] - 1))
            bisect = tP + tQ
            nb = np.linalg.norm(bisect)
            if nb > 1e-4:
                u_out = bisect / nb
                tx = int(np.clip(round(corner_pt[0] + 0.25 * w_max * u_out[0]), 0, D.shape[1] - 1))
                ty = int(np.clip(round(corner_pt[1] + 0.25 * w_max * u_out[1]), 0, D.shape[0] - 1))
                if D[ty, tx] < 0.40 or D[iy, ix] < 0.70:
                    is_round = True
            elif D[iy, ix] < 0.70:
                is_round = True

        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)

        if is_round and X_corner is not None:
            R = min(1.2 * w_merged, 0.45 * min(LP, LQ))
            kappa = 0.55228475 * R
            P_start = corner_pt - R * tP
            P_end   = corner_pt - R * tQ
            P_mod, Q_mod = P.copy(), Q.copy()
            P_mod.A[-1] = P_start.copy()
            P_mod.Hin[-1] = P_start - tP * (w_merged / 3.0)
            P_mod.Hout[-1] = P_start + tP * kappa
            Q_mod.A[0] = P_end.copy()
            Q_mod.Hin[0] = P_end + tQ * kappa
            Q_mod.Hout[0] = P_end - tQ * (w_merged / 3.0)
            A = np.vstack([P_mod.A, Q_mod.A])
            Hin = np.vstack([P_mod.Hin, Q_mod.Hin])
            Hout = np.vstack([P_mod.Hout, Q_mod.Hout])
        else:
            dP, dQ = corner_pt - P.A[-1], corner_pt - Q.A[0]
            A = np.vstack([P.A, Q.A[1:]])
            Hin = np.vstack([P.Hin, Q.Hin[1:]])
            Hout = np.vstack([P.Hout[:-1], Q.Hout])
            idx = len(P.A) - 1
            A[idx] = corner_pt
            Hin[idx] = P.Hin[-1] + dP
            Hout[idx] = Q.Hout[0] + dQ
            if idx >= 1:
                segP = np.array([A[idx - 1], Hout[idx - 1], Hin[idx], A[idx]])
                if FN._straight(segP, 0.4) or (gP is not None and FN._straight_before_end(P, 1, gP[1])):
                    vP = A[idx] - A[idx - 1]
                    Hout[idx - 1] = A[idx - 1] + vP / 3.0
                    Hin[idx] = A[idx] - vP / 3.0
            if idx + 1 < len(A):
                segQ = np.array([A[idx], Hout[idx], Hin[idx + 1], A[idx + 1]])
                if FN._straight(segQ, 0.4) or (gQ is not None and FN._straight_before_end(Q, 0, gQ[1])):
                    vQ = A[idx + 1] - A[idx]
                    Hout[idx] = A[idx] + vQ / 3.0
                    Hin[idx + 1] = A[idx + 1] - vQ / 3.0

        join_type = 'round' if is_round else ('miter' if (P.join == 'miter' or Q.join == 'miter') else P.join)
        ml_val = max(P.ml, Q.ml)
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.25 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            Hin[0] = Hin[-1].copy()
            Hout[-1] = Hout[0].copy()
            closed = True
        if is_round:
            m.paths[i] = Path(A, Hin, Hout, w_merged, join_type, ml_val, closed)
        else:
            m.paths[i] = FN._clean_seam(Path(A, Hin, Hout, w_merged, join_type, ml_val, closed))
        dead.add(j)

    if joint_ends and pairs:
        merged_i = pairs[0][0]
        p_merged = m.paths[merged_i]
        for (k_idx, e_k) in joint_ends:
            if k_idx in dead or k_idx == merged_i or k_idx >= len(m.paths):
                continue
            pk = m.paths[k_idx]
            end_pt = pk.A[0 if e_k == 0 else -1]
            f = p_merged.flat(0.25)
            k_near = int(np.argmin(np.linalg.norm(f - end_pt, axis=1)))
            pt_on, d_on = f[k_near], float(np.linalg.norm(f[k_near] - end_pt))
            if d_on <= 1.5 * p_merged.w:
                J._set_end(pk, e_k, pt_on)
                ak = J.insert_anchor(p_merged, pt_on)
                J._set_end(pk, e_k, p_merged.A[ak])
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m

FN.merge_corners = enhanced_merge_corners
J.merge_corners = enhanced_merge_corners

def enhanced_tool_unite(m: Model, J_joint: J.Joint, D):
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J_joint.ends and (p[2], p[3]) in J_joint.ends]
    if not pairs:
        pairs = J.smooth_continuation_pairs(m, J_joint, D)
    if pairs:
        return FN.join_pairs(m, pairs)
    if len(J_joint.ends) >= 3:
        cp = J.corner_continuation_pairs(m, J_joint, D)
        if cp:
            return enhanced_merge_corners(m, cp, joint_ends=J_joint.ends, D=D)
    return None

J.tool_unite = enhanced_tool_unite

# Test on m0
data0 = json.load(open('scratch/m0_current.json'))
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)
doctor0 = Doctor(D0)
m0 = Model([Path.from_dict(p) for p in data0['paths']], 257, 255)

m_out, ink_out, s_out, rep = J.run_join_engine(m0, D0, doctor0, ink_of, doctor0.soft(ink_of(m0)), 6.0)
print('m0 result:')
print('  Unite count:', rep['fixed']['unite'])
print('  Paths: ', len(m0.paths), '->', len(m_out.paths))
print('  Soft:  ', doctor0.soft(ink_of(m0)), '->', s_out)

# Test on m1
data1 = json.load(open('scratch/m1_current.json'))
small1 = cv2.imread('scratch/small_1.png', 0)
D1 = ink_map(small1)
H1, W1 = small1.shape
doctor1 = Doctor(D1)
m1 = Model([Path.from_dict(p) for p in data1['paths']], W1, H1)

m1_out, ink1_out, s1_out, rep1 = J.run_join_engine(m1, D1, doctor1, ink_of, doctor1.soft(ink_of(m1)), 6.0)
print('m1 result:')
print('  Unite count:', rep1['fixed']['unite'])
print('  Paths: ', len(m1.paths), '->', len(m1_out.paths))
print('  Soft:  ', doctor1.soft(ink_of(m1)), '->', s1_out)
