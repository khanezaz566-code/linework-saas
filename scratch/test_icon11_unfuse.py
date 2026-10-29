import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter1d
from linework import pipeline as P, trace as TR, lessons as LS
from linework.geom import resample, unit

def march_acute_end(D, P2, w_prof, rw, end_idx):
    """If end_idx (0 or 1) of P2 has a sharp skeleton hook inside a wide junction zone (w_prof > 1.35*rw),
    march from the last clean single-stroke sample along the unobstructed outer ink edge at distance 0.5*rw
    until reaching the single-stroke width of the through-branch.
    """
    pts = P2 if end_idx == 0 else P2[::-1]
    wp = w_prof if end_idx == 0 else w_prof[::-1]
    n = len(pts)
    if n < max(16, int(2.4 * rw)):
        return P2, False
    # Find first sample k_clean where stroke width is normal (<= 1.20 * rw)
    clean_mask = np.isfinite(wp) & (wp >= 0.70 * rw) & (wp <= 1.20 * rw)
    clean_idx = np.nonzero(clean_mask)[0]
    if not len(clean_idx):
        return P2, False
    k_clean = int(clean_idx[0])
    if not (max(3, int(0.45 * rw)) <= k_clean <= int(1.65 * rw)):
        return P2, False
    if float(np.nanmax(wp[:k_clean])) < 1.55 * rw:
        return P2, False
    k_back = min(n - 1, k_clean + max(6, int(0.95 * rw)))
    if k_back <= k_clean + 2:
        return P2, False
    cur_pt = pts[k_clean].copy()
    cur_dir = unit(pts[k_clean] - pts[k_back])
    v_stub = pts[0] - pts[k_clean]
    if np.linalg.norm(v_stub) < 0.35 * rw:
        return P2, False
    u_stub = unit(v_stub)
    hook_deg = float(np.degrees(np.arccos(np.clip(u_stub @ cur_dir, -1.0, 1.0))))
    if hook_deg < 28.0:
        return P2, False

    N_dir = np.array([-cur_dir[1], cur_dir[0]])
    stub_side = 1 if (v_stub @ N_dir) >= 0 else -1
    traced = [cur_pt.copy()]
    reached = False
    for step in range(int(2.8 * rw)):
        cand = cur_pt + cur_dir * 1.0
        N_dir = np.array([-cur_dir[1], cur_dir[0]])
        t, v = TR._profile(D, cand[None, :], N_dir[None, :], 22)
        L, Rr = TR._edges(t, v)
        l_val, r_val = float(L[0]), float(Rr[0])
        if stub_side > 0:
            if not np.isfinite(l_val):
                break
            off_n = l_val + 0.5 * rw
        else:
            if not np.isfinite(r_val):
                break
            off_n = r_val - 0.5 * rw
        if abs(off_n) > 0.45 * rw:
            break
        next_pt = cand + N_dir * off_n
        w_tot = r_val - l_val if (np.isfinite(l_val) and np.isfinite(r_val)) else 99.0
        cur_dir = unit(0.65 * cur_dir + 0.35 * unit(next_pt - cur_pt))
        cur_pt = next_pt
        traced.append(cur_pt.copy())
        if step >= 3 and w_tot <= 1.08 * rw:
            reached = True
            break
    if not reached or len(traced) < 4:
        return P2, False
    new_pts = np.vstack([np.array(traced[::-1]), pts[k_clean + 1:]])
    return (new_pts if end_idx == 0 else new_pts[::-1]), True


def de_flare_branch(P0, P2, L, Rr, N, rw):
    """Where a branch widens on ONE side (1.08*rw < w <= 1.95*rw) because a second stroke merges into it at a shallow angle,
    lock the branch to its unflared ink edge (where |L + 0.5*rw| <= 0.14*rw or |Rr - 0.5*rw| <= 0.14*rw) instead of drifting
    into the merging stroke."""
    w = Rr - L
    flared = np.isfinite(w) & (w > 1.08 * rw) & (w <= 1.95 * rw)
    if not flared.any():
        return P2
    P_out = P2.copy()
    dL = np.abs(L + 0.5 * rw)
    dR = np.abs(Rr - 0.5 * rw)
    use_L = flared & (dL <= 0.15 * rw) & (dR > 0.22 * rw)
    use_R = flared & (dR <= 0.15 * rw) & (dL > 0.22 * rw)
    if use_L.any():
        P_out[use_L] = P0[use_L] + N[use_L] * (L[use_L] + 0.5 * rw)[:, None]
    if use_R.any():
        P_out[use_R] = P0[use_R] + N[use_R] * (Rr[use_R] - 0.5 * rw)[:, None]
    return P_out


def patched_refined_branches(D, S=2):
    mask = D > 0.5
    if not mask.any():
        return []
    dt = ndi.distance_transform_edt(mask)
    br_raw = TR.skeleton_branches(D, S)
    d_vals = []
    H, W_im = D.shape
    for b in br_raw:
        pts = b["pts"]
        if len(pts) >= 4:
            xs = np.clip(np.round(pts[:, 0]).astype(int), 0, W_im - 1)
            ys = np.clip(np.round(pts[:, 1]).astype(int), 0, H - 1)
            d_vals.append(2.0 * dt[ys, xs])
    w_icon = float(np.percentile(np.concatenate(d_vals), 45)) if d_vals else None
    # Precompute which junctions have a nearly-collinear through-pair (dot < -0.90)
    j_dirs = {}
    for idx_b, b in enumerate(br_raw):
        pts_b = b["pts"]
        if len(pts_b) < 8:
            continue
        if b["sj"] > 0:
            d0 = unit(pts_b[min(len(pts_b) - 1, 24)] - pts_b[min(len(pts_b) - 1, 4)])
            j_dirs.setdefault(b["sj"], []).append((idx_b, d0))
        if b["ej"] > 0:
            d1 = unit(pts_b[max(0, len(pts_b) - 25)] - pts_b[max(0, len(pts_b) - 5)])
            j_dirs.setdefault(b["ej"], []).append((idx_b, d1))
    through_juncs = {}
    for jid, items in j_dirs.items():
        if len(items) >= 3:
            best_pair = None
            best_dot = 1.0
            for a_i in range(len(items)):
                for b_i in range(a_i + 1, len(items)):
                    if items[a_i][0] == items[b_i][0]:
                        continue
                    dt_val = float(items[a_i][1] @ items[b_i][1])
                    if dt_val < best_dot:
                        best_dot = dt_val
                        best_pair = {items[a_i][0], items[b_i][0]}
            if best_dot < -0.90 and best_pair is not None:
                through_juncs[jid] = best_pair

    detached_juncs = set()
    out = []
    for idx_b, b in enumerate(br_raw):
        P0 = resample(b["pts"], 1.0)
        if len(P0) < 4:
            continue
        P2, W = TR.refine_branch(D, P0, w_icon=w_icon)
        rw = float(np.nanmedian(W)) if np.isfinite(W).any() else (w_icon or 0.0)
        if rw <= 0:
            continue
        sj, ej = b["sj"], b["ej"]
        if sj == 0:
            P2[0] = TR.extend_end(D, P2, 0, rw / 2)
        if ej == 0:
            P2[-1] = TR.extend_end(D, P2, 1, rw / 2)

        if len(P0) >= max(14, int(2.2 * rw)) and len(P0) == len(P2):
            T = TR._tang(P0)
            N = np.c_[-T[:, 1], T[:, 0]]
            t, v = TR._profile(D, P0, N, 22)
            L, Rr = TR._edges(t, v)
            w_prof = Rr - L

            # 1. Check for a merged double-width run near either end
            wide = np.isfinite(w_prof) & (w_prof >= 1.38 * rw) & (w_prof <= 2.35 * rw)
            best_run = (0, 0, 0)
            j = 0
            while j < len(wide):
                if not wide[j]:
                    j += 1
                    continue
                m = j
                while m < len(wide) and wide[m]:
                    m += 1
                if m - j > best_run[0]:
                    best_run = (m - j, j, m)
                j = m
            rlen, j0, j1 = best_run
            if rlen >= max(12, int(2.0 * rw)) and float(np.nanmax(w_prof[j0:j1])) >= 1.62 * rw:
                off_L = gaussian_filter1d(np.where(np.isfinite(L), L + 0.5 * rw, 0.0), 2.0, mode="nearest")
                off_R = gaussian_filter1d(np.where(np.isfinite(Rr), Rr - 0.5 * rw, 0.0), 2.0, mode="nearest")
                pL = P0 + N * off_L[:, None]
                pR = P0 + N * off_R[:, None]

                def straight_dev(pts):
                    ch = pts[-1] - pts[0]
                    cl = float(np.linalg.norm(ch))
                    if cl < 1e-6:
                        return 0.0
                    u = ch / cl
                    return float(np.abs((pts[:, 0] - pts[0, 0]) * u[1] - (pts[:, 1] - pts[0, 1]) * u[0]).max())

                if j0 <= int(0.9 * rw) and len(P0) - j1 >= int(1.5 * rw):
                    ks = min(len(P0) - 1, j1 + int(0.4 * rw))
                    dev_L = straight_dev(pL[max(2, j0):j1])
                    dev_R = straight_dev(pR[max(2, j0):j1])
                    if min(dev_L, dev_R) <= 0.12 * rw and max(dev_L, dev_R) >= 0.25 * rw:
                        alpha = np.linspace(1.0, 0.0, ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[0:1], pL[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pR[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        else:
                            wall_pts = np.vstack([P2[0:1], pR[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pL[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        out.append(dict(pts=curve_pts, w=rw, sj=-2, ej=ej))
                        out.append(dict(pts=wall_pts, w=rw, sj=sj, ej=-2))
                        continue
                elif len(P0) - j1 <= int(0.9 * rw) and j0 >= int(1.5 * rw):
                    ks = max(0, j0 - int(0.4 * rw))
                    dev_L = straight_dev(pL[j0:min(len(P0) - 2, j1)])
                    dev_R = straight_dev(pR[j0:min(len(P0) - 2, j1)])
                    if min(dev_L, dev_R) <= 0.12 * rw and max(dev_L, dev_R) >= 0.25 * rw:
                        alpha = np.linspace(0.0, 1.0, len(P0) - ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[ks:ks+1], pL[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pR[ks:]])
                        else:
                            wall_pts = np.vstack([P2[ks:ks+1], pR[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pL[ks:]])
                        out.append(dict(pts=curve_pts, w=rw, sj=sj, ej=-2))
                        out.append(dict(pts=wall_pts, w=rw, sj=-2, ej=ej))
                        continue

            # 2. Check for acute/tangential junction hook at either end (only when joining a collinear through-pair)
            if sj in through_juncs and idx_b not in through_juncs[sj]:
                P2, ok0 = march_acute_end(D, P2, w_prof, rw, 0)
                if ok0:
                    detached_juncs.add(sj)
                    sj = -2
            if ej in through_juncs and idx_b not in through_juncs[ej] and len(P2) == len(w_prof):
                P2, ok1 = march_acute_end(D, P2, w_prof, rw, 1)
                if ok1:
                    detached_juncs.add(ej)
                    ej = -2

        out.append(dict(pts=P2, w=rw, sj=sj, ej=ej))

    # For any through-junction where the 3rd acute branch was detached, remove the junction centroid pull and one-sided flare on the remaining 2 collinear branches
    for jid in detached_juncs:
        rem = [(i, 0 if b["sj"] == jid else 1) for i, b in enumerate(out) if b["sj"] == jid or b["ej"] == jid]
        if len(rem) == 2:
            for i_o, _ in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                if len(pts_o) >= 8:
                    T_o = TR._tang(pts_o)
                    N_o = np.c_[-T_o[:, 1], T_o[:, 0]]
                    t_o, v_o = TR._profile(D, pts_o, N_o, 22)
                    L_o, Rr_o = TR._edges(t_o, v_o)
                    out[i_o]["pts"] = de_flare_branch(pts_o, pts_o, L_o, Rr_o, N_o, rw_o)
            projs = []
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    anchor = pts_o[kp]
                    far = pts_o[min(len(pts_o) - 1, kp + max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[0] - anchor))
                else:
                    anchor = pts_o[-1 - kp]
                    far = pts_o[max(0, len(pts_o) - 1 - kp - max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[-1] - anchor))
                projs.append(anchor + u_dir * dist)
            mid_j = 0.5 * (projs[0] + projs[1])
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"].copy()
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[kp]
                else:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[-1 - s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[-1 - kp]
                out[i_o]["pts"] = pts_o
    return out

if __name__ == "__main__":
    LS.clear()
    TR.refined_branches = patched_refined_branches
    P.refined_branches = patched_refined_branches
    gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
    W, H, jobs = P.process_sheet(gray)
    k, crop, off = jobs[11]
    opts = P.Options(quality="precise", target_iou=0.985, fresh=True, memory=False, time_budget=12.0)
    res = P.process_icon(crop, opts, name="icon_11")
    mod = res["model"]
    met = res["metrics"]
    print(f"icon_11: iou={met['iou']*100:.2f}%, paths={met['paths']}, nodes={met['nodes']}, joins={met.get('joins')}")
    ink = P.ink_of(mod)
    rend = ((1.0 - np.clip(ink, 0, 1)) * 255).astype(np.uint8)
    diff = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    extra = (ink > 0.5) & (crop >= 128)
    missing = (ink <= 0.5) & (crop < 128)
    diff[extra] = (0, 0, 255)
    diff[missing] = (255, 0, 0)
    y0, y1, x0, x1 = 195, 305, 125, 345
    scale = 3
    comb = np.vstack([
        cv2.resize(cv2.cvtColor(crop[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR), ((x1-x0)*scale, (y1-y0)*scale), interpolation=cv2.INTER_NEAREST),
        cv2.resize(cv2.cvtColor(rend[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR), ((x1-x0)*scale, (y1-y0)*scale), interpolation=cv2.INTER_NEAREST),
        cv2.resize(diff[y0:y1, x0:x1], ((x1-x0)*scale, (y1-y0)*scale), interpolation=cv2.INTER_NEAREST),
    ])
    cv2.imwrite("scratch/e6c0d_vis/icon_11_unfused_zoom.png", comb)
    print("Saved scratch/e6c0d_vis/icon_11_unfused_zoom.png")
