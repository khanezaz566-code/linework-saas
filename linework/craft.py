"""Professional Designer Vector Craftsmanship Engine (linework/craft.py).

Transforms mechanically traced / stitched centerline paths into clean, human-crafted,
Adobe Illustrator-grade SVG paths with minimal intentional anchor points and balanced
Bezier handles, while strictly preserving visual accuracy via the Doctor.
"""
from __future__ import annotations
import numpy as np
from .model import Model, Path
from .geom import unit, bez, _chord, _reparam
from .doctor import Doctor, ink_of
from .rings import _kasa
from . import edit as E
from . import topology as T
from .finisher import _intersect_rays


def fit_free_cubic(pts: np.ndarray):
    """Fit a single cubic Bezier [b0, b1, b2, b3] with pinned endpoints b0=pts[0], b3=pts[-1]
    and optimal interior control points b1, b2 via 2x2 linear least-squares + Newton reparameterization.
    """
    pts = np.asarray(pts, float)
    b0, b3 = pts[0], pts[-1]
    chord = b3 - b0
    Lc = float(np.linalg.norm(chord))
    if len(pts) <= 3 or Lc < 1e-4:
        return np.array([b0, b0 + chord / 3.0, b0 + 2.0 * chord / 3.0, b3]), 0.0

    # Pure straight line check: if all points lie within 0.30px of chord, use exact 1/3, 2/3 linear handles
    u_c = chord / Lc
    perp = np.array([-u_c[1], u_c[0]])
    lin_err = float(np.max(np.abs((pts - b0) @ perp)))
    if lin_err <= 0.30:
        return np.array([b0, b0 + chord / 3.0, b0 + 2.0 * chord / 3.0, b3]), lin_err

    u = _chord(pts)
    c = None
    for _ in range(6):
        mt = 1.0 - u
        A1 = 3.0 * (mt ** 2) * u
        A2 = 3.0 * mt * (u ** 2)
        M = np.column_stack([A1, A2])
        rhs = pts - ((mt ** 3)[:, None] * b0 + (u ** 3)[:, None] * b3)
        sol, _, _, _ = np.linalg.lstsq(M, rhs, rcond=None)
        c = np.array([b0, sol[0], sol[1], b3])
        u = _reparam(c, pts, u)

    # Guard against over-extended or looping handles
    if np.linalg.norm(c[1] - b0) > 0.80 * Lc or np.linalg.norm(b3 - c[2]) > 0.80 * Lc:
        return c, 999.0
    # Ensure handles do not point backward relative to chord by > 90 deg
    if (c[1] - b0) @ u_c < 0 or (b3 - c[2]) @ u_c < 0:
        return c, 999.0

    err = float(np.sqrt(np.max(np.sum((bez(c, u) - pts) ** 2, axis=1))))
    return c, err


def craft_model(model: Model, D: np.ndarray, doctor: Doctor, W0: float = 10.0) -> Model:
    """Optimize a vector Model to human-crafted Illustrator standard (minimal anchors,
    4-anchor circles, 2-anchor straight lines, smooth balanced Bezier curves) with
    strict zero-regression Doctor verification."""
    if not model.paths:
        return model

    cur_m = model.copy()
    cur_ink = ink_of(cur_m)
    s0 = doctor.soft(cur_ink)
    iou0 = doctor.iou(cur_ink)
    cur_s = s0
    cur_iou = iou0

    # Strict Zero-Regression Floor:
    # Never allow an icon with >= 98.50% IOU to drop below 98.50%, and never drop > 0.20% total.
    if iou0 >= 0.9850:
        min_allowed_iou = max(0.9850, iou0 - 0.0020)
    elif iou0 >= 0.9800:
        min_allowed_iou = max(0.9800, iou0 - 0.0008)
    else:
        min_allowed_iou = iou0 - 0.0006
    max_allowed_soft = s0 + max(28.0, 0.0038 * doctor.area)

    def try_accept(cand_m: Model, step_soft_tol: float = 14.0, step_iou_drop: float = 0.0004, structural: bool = False) -> bool:
        nonlocal cur_m, cur_ink, cur_s, cur_iou
        c_ink = ink_of(cand_m)
        c_s = doctor.soft(c_ink)
        c_iou = doctor.iou(c_ink)
        # Strict Regression Guard: quality must never degrade noticeably
        if iou0 >= 0.9750:
            struct_min_iou = max(0.9750, iou0 - 0.0015)
        else:
            struct_min_iou = iou0 - 0.0015
        struct_min_iou = min(struct_min_iou, min_allowed_iou - 0.0008)
        struct_max_soft = max(s0 + max(24.0, 0.0030 * doctor.area), max_allowed_soft + 12.0)
        if c_iou < (struct_min_iou if structural else min_allowed_iou) or c_s > (struct_max_soft if structural else max_allowed_soft):
            return False
        eff_drop = min(step_iou_drop, 0.0012) if structural else min(step_iou_drop, 0.0004)
        eff_soft = min(step_soft_tol, 22.0) if structural else min(step_soft_tol, 12.0)
        if c_s <= cur_s + max(eff_soft, 0.012 * cur_s) and c_iou >= cur_iou - eff_drop:
            cur_m, cur_ink, cur_s, cur_iou = cand_m, c_ink, c_s, c_iou
            return True
        return False

    # ------------------------------------------------------------------
    # 1. Collapse coincident / duplicate consecutive anchors (< 0.5px)
    # ------------------------------------------------------------------
    for i in range(len(cur_m.paths)):
        p = cur_m.paths[i]
        segs = p.segs()
        min_s = 3 if p.closed else 1
        if len(segs) <= min_s:
            continue
        non_deg = [s for s in segs if np.linalg.norm(s[3] - s[0]) >= 0.45]
        if len(non_deg) >= min_s and len(non_deg) < len(segs):
            # Reconnect endpoints cleanly
            for k in range(len(non_deg) - 1):
                mid = 0.5 * (non_deg[k][3] + non_deg[k + 1][0])
                non_deg[k][3] = mid
                non_deg[k + 1][0] = mid
            if p.closed:
                mid = 0.5 * (non_deg[-1][3] + non_deg[0][0])
                non_deg[-1][3] = mid
                non_deg[0][0] = mid
            cand = cur_m.copy()
            np_p = Path.from_segs(non_deg, p.w, closed=p.closed, join=p.join)
            np_p.ml = p.ml
            cand.paths[i] = np_p
            try_accept(cand, step_soft_tol=3.0, step_iou_drop=0.0003)

    # ------------------------------------------------------------------
    # 2. Remove redundant micro-stubs covered by other strokes
    # ------------------------------------------------------------------
    for i in range(len(cur_m.paths) - 1, -1, -1):
        p = cur_m.paths[i]
        if not p.closed and len(p.A) <= 3 and p.length() < 0.45 * p.w:
            cand = cur_m.copy()
            del cand.paths[i]
            try_accept(cand, step_soft_tol=0.5, step_iou_drop=0.0001)

    # ------------------------------------------------------------------
    # 2.5. Smart Self-Check Auto-Join, Broken Through-Line & Endpoint Hook Solver
    # ------------------------------------------------------------------
    H_im, W_im = D.shape

    def _has_ink_line(p_a, p_b, min_frac=0.88):
        ts_s = np.linspace(0.0, 1.0, 16)[:, None]
        line_pts = p_a * (1.0 - ts_s) + p_b * ts_s
        xs_s = np.clip(np.round(line_pts[:, 0] - 0.5).astype(int), 0, W_im - 1)
        ys_s = np.clip(np.round(line_pts[:, 1] - 0.5).astype(int), 0, H_im - 1)
        return float((D[ys_s, xs_s] > 0.5).mean()) >= min_frac

    def _straighten_through_runs():
        nonlocal cur_m
        for pi in range(len(cur_m.paths)):
            p = cur_m.paths[pi]
            segs = p.segs()
            n_s = len(segs)
            if n_s < 3:
                continue
            runs = []
            for a in range(n_s):
                for b in range(n_s, a + 1, -1):
                    p0 = segs[a][0]
                    p1 = segs[b - 1][3]
                    chord = p1 - p0
                    L_ch = float(np.linalg.norm(chord))
                    if L_ch < 2.5 * p.w:
                        continue
                    u_ch = chord / L_ch
                    perp = np.array([-u_ch[1], u_ch[0]])
                    max_dev = 0.0
                    for k in range(a, b):
                        s = segs[k]
                        max_dev = max(
                            max_dev,
                            abs(float((s[0] - p0) @ perp)),
                            abs(float((s[1] - p0) @ perp)),
                            abs(float((s[2] - p0) @ perp)),
                            abs(float((s[3] - p0) @ perp)),
                        )
                    if (max_dev / L_ch <= 0.022) and (max_dev <= 0.48 * p.w):
                        if _has_ink_line(p0, p1, min_frac=0.88):
                            runs.append((L_ch, a, b, p0, p1))
                            break

            if not runs:
                continue
            runs.sort(key=lambda r: -r[0])
            chosen = []
            used_segs = set()
            for L_ch, a, b, p0, p1 in runs:
                if any(idx in used_segs for idx in range(a, b)):
                    continue
                for idx in range(a, b):
                    used_segs.add(idx)
                chosen.append((a, b, p0, p1))

            chosen.sort(key=lambda r: -r[0])
            cand = cur_m.copy()
            cand_p = cand.paths[pi]
            cand_segs = cand_p.segs()
            for a, b, p0, p1 in chosen:
                chord = p1 - p0
                s_straight = np.array([p0, p0 + chord / 3.0, p0 + 2.0 * chord / 3.0, p1])
                cand_segs = cand_segs[:a] + [s_straight] + cand_segs[b:]
                u_line = chord / float(np.linalg.norm(chord))
                L_chord = float(np.linalg.norm(chord))
                for pj, other_p in enumerate(cand.paths):
                    if pj == pi:
                        continue
                    for e in (0, 1):
                        ep = other_p.A[0] if e == 0 else other_p.A[-1]
                        t_proj = float((ep - p0) @ u_line)
                        if 0.0 <= t_proj <= L_chord:
                            pt_proj = p0 + t_proj * u_line
                            dist = float(np.linalg.norm(ep - pt_proj))
                            if dist <= 1.2 * other_p.w and _has_ink_line(ep, pt_proj, min_frac=0.85):
                                T._move_end(other_p, e, pt_proj)

            np_p = Path.from_segs(cand_segs, p.w, closed=p.closed, join=p.join)
            np_p.ml = p.ml
            cand.paths[pi] = np_p
            try_accept(cand, step_soft_tol=28.0, step_iou_drop=0.0010, structural=True)

    def _straighten_collinear_stem_trunks():
        nonlocal cur_m
        for pi in range(len(cur_m.paths)):
            p = cur_m.paths[pi]
            segs = p.segs()
            n_s = len(segs)
            if n_s < 4:
                continue
            cand = cur_m.copy()
            cand_p = cand.paths[pi]
            cand_segs = cand_p.segs()
            changed_stem = False
            for i in range(n_s):
                s_i = cand_segs[i]
                ch_i = s_i[3] - s_i[0]
                L_i = float(np.linalg.norm(ch_i))
                if L_i < 2.0 * p.w:
                    continue
                u_i = ch_i / L_i
                perp_i = np.array([-u_i[1], u_i[0]])
                dev_i = max(abs(float((s_i[1] - s_i[0]) @ perp_i)), abs(float((s_i[2] - s_i[0]) @ perp_i)))
                if dev_i > 0.20 * p.w:
                    continue
                
                for j in range(i + 2, n_s):
                    s_j = cand_segs[j]
                    ch_j = s_j[3] - s_j[0]
                    L_j = float(np.linalg.norm(ch_j))
                    if L_j < 2.0 * p.w:
                        continue
                    u_j = ch_j / L_j
                    perp_j = np.array([-u_j[1], u_j[0]])
                    dev_j = max(abs(float((s_j[1] - s_j[0]) @ perp_j)), abs(float((s_j[2] - s_j[0]) @ perp_j)))
                    if dev_j > 0.20 * p.w:
                        continue
                    
                    if float(u_i @ u_j) < np.cos(np.radians(10.0)):
                        continue
                    
                    v_span = s_j[3] - s_i[0]
                    L_span = float(np.linalg.norm(v_span))
                    if L_span < 3.0 * p.w:
                        continue
                    u_span = v_span / L_span
                    if float(u_i @ u_span) < np.cos(np.radians(10.0)):
                        continue
                    
                    perp_span = np.array([-u_span[1], u_span[0]])
                    lat_dev = max(
                        abs(float((s_i[3] - s_i[0]) @ perp_span)),
                        abs(float((s_j[0] - s_i[0]) @ perp_span))
                    )
                    if lat_dev > 0.35 * p.w:
                        continue
                    
                    if _has_ink_line(s_i[0], s_j[3], min_frac=0.88):
                        p_base = s_i[0]
                        t_end_i = float((s_i[3] - p_base) @ u_span)
                        pt_end_i = p_base + t_end_i * u_span
                        cand_segs[i][3] = pt_end_i
                        cand_segs[i][1] = p_base + (pt_end_i - p_base) / 3.0
                        cand_segs[i][2] = p_base + 2.0 * (pt_end_i - p_base) / 3.0
                        cand_segs[i + 1][0] = pt_end_i
                        
                        t_start_j = float((s_j[0] - p_base) @ u_span)
                        pt_start_j = p_base + t_start_j * u_span
                        cand_segs[j - 1][3] = pt_start_j
                        cand_segs[j][0] = pt_start_j
                        pt_end_j = s_j[3]
                        cand_segs[j][1] = pt_start_j + (pt_end_j - pt_start_j) / 3.0
                        cand_segs[j][2] = pt_start_j + 2.0 * (pt_end_j - pt_start_j) / 3.0
                        changed_stem = True
            
            if changed_stem:
                np_p = Path.from_segs(cand_segs, p.w, closed=p.closed, join=p.join)
                np_p.ml = p.ml
                cand.paths[pi] = np_p
                try_accept(cand, step_soft_tol=28.0, step_iou_drop=0.0010, structural=True)

    def _reconstruct_broken_through_lines():
        # Detect when a continuous straight line is split at a 3/4-way junction with one or both ends hooked sideways
        changed_tl = True
        while changed_tl:
            changed_tl = False
            n_p = len(cur_m.paths)
            for i in range(n_p):
                pi = cur_m.paths[i]
                if pi.closed or len(pi.A) < 3:
                    continue
                for ei in (0, 1):
                    p_end_i = pi.A[0] if ei == 0 else pi.A[-1]
                    p_base_i = pi.A[1] if ei == 0 else pi.A[-2]
                    p_prev_i = pi.A[2] if ei == 0 else pi.A[-3]
                    l_hook_i = float(np.linalg.norm(p_end_i - p_base_i))
                    l_int_i = float(np.linalg.norm(p_base_i - p_prev_i))
                    if l_hook_i > 3.2 * pi.w or l_int_i < 1.2 * pi.w:
                        continue
                    u_hook_i = unit(p_end_i - p_base_i)
                    u_int_i = unit(p_base_i - p_prev_i)
                    if float(u_hook_i @ u_int_i) > np.cos(np.radians(35.0)):
                        continue
                    perp_i = np.array([-u_int_i[1], u_int_i[0]])
                    for j in range(i + 1, n_p):
                        pj = cur_m.paths[j]
                        if pj.closed or len(pj.A) < 3:
                            continue
                        for ej in (0, 1):
                            p_end_j = pj.A[0] if ej == 0 else pj.A[-1]
                            p_base_j = pj.A[1] if ej == 0 else pj.A[-2]
                            p_prev_j = pj.A[2] if ej == 0 else pj.A[-3]
                            l_hook_j = float(np.linalg.norm(p_end_j - p_base_j))
                            l_int_j = float(np.linalg.norm(p_base_j - p_prev_j))
                            if l_hook_j > 3.2 * pj.w or l_int_j < 1.2 * pj.w:
                                continue
                            u_hook_j = unit(p_end_j - p_base_j)
                            u_int_j = unit(p_base_j - p_prev_j)
                            if float(u_hook_j @ u_int_j) > np.cos(np.radians(35.0)):
                                continue
                            gap_bases = float(np.linalg.norm(p_base_j - p_base_i))
                            if gap_bases > 2.2 * pi.w:
                                continue
                            # u_int_i and u_int_j should point toward each other (collinear opposing)
                            if float(u_int_i @ (-u_int_j)) < np.cos(np.radians(15.0)):
                                continue
                            if abs(float((p_base_j - p_prev_i) @ perp_i)) > 0.48 * pi.w:
                                continue
                            if not _has_ink_line(p_prev_i, p_prev_j, min_frac=0.90):
                                continue
                            # Weld pi (without its hook) and pj (without its hook) across straight segment p_prev_i <-> p_prev_j
                            segs_i = pi.segs()[1:] if ei == 0 else pi.segs()[:-1]
                            segs_j = pj.segs()[1:] if ej == 0 else pj.segs()[:-1]
                            if not segs_i or not segs_j:
                                continue
                            # Orient segs_i to end at p_base_i, and segs_j to start at p_base_j
                            if ei == 0:
                                segs_i = [s[::-1].copy() for s in segs_i[::-1]]
                            if ej == 1:
                                segs_j = [s[::-1].copy() for s in segs_j[::-1]]
                            # Merge last segment of segs_i and first segment of segs_j into one straight segment p_prev_i -> p_prev_j
                            pt_a = segs_i[-1][0]
                            pt_b = segs_j[0][3]
                            ch_ab = pt_b - pt_a
                            s_bridge = np.array([pt_a, pt_a + ch_ab / 3.0, pt_a + 2.0 * ch_ab / 3.0, pt_b])
                            merged_segs = segs_i[:-1] + [s_bridge] + segs_j[1:]
                            cand = cur_m.copy()
                            np_m = Path.from_segs(merged_segs, pi.w, closed=False, join=pi.join)
                            np_m.ml = pi.ml
                            cand.paths[i] = np_m
                            del cand.paths[j]
                            # Also snap any nearby open endpoints (within 2.0 * w of the junction) onto the restored straight line
                            mid_junc = 0.5 * (p_base_i + p_base_j)
                            u_line = unit(pt_b - pt_a)
                            for m_idx, pm in enumerate(cand.paths):
                                if m_idx == i or pm.closed:
                                    continue
                                for em_idx in (0, 1):
                                    ep = pm.A[0] if em_idx == 0 else pm.A[-1]
                                    if float(np.linalg.norm(ep - mid_junc)) <= 2.0 * pi.w:
                                        t_proj = float((ep - pt_a) @ u_line)
                                        L_ab = float(np.linalg.norm(ch_ab))
                                        if 0.0 <= t_proj <= L_ab:
                                            pt_proj = pt_a + t_proj * u_line
                                            if _has_ink_line(ep, pt_proj, min_frac=0.88):
                                                T._move_end(pm, em_idx, pt_proj)
                            if try_accept(cand, step_soft_tol=28.0, step_iou_drop=0.0020, structural=True):
                                changed_tl = True
                                break
                        if changed_tl:
                            break
                    if changed_tl:
                        break
                if changed_tl:
                    break

    def _straighten_endpoint_hooks():
        polys_all = [p.flat(1.0) for p in cur_m.paths]
        for i in range(len(cur_m.paths)):
            p = cur_m.paths[i]
            if p.closed:
                continue
            # Case A: 2-anchor open path with bowed handle due to sideways endpoint deflection at a T-junction
            if len(p.A) == 2:
                s = p.segs()[0]
                ch = s[3] - s[0]
                L = float(np.linalg.norm(ch))
                if 1.15 * p.w <= L <= 4.5 * p.w:
                    u_c = ch / L
                    perp_c = np.array([-u_c[1], u_c[0]])
                    dev1 = abs(float((s[1] - s[0]) @ perp_c))
                    dev2 = abs(float((s[2] - s[0]) @ perp_c))
                    if max(dev1, dev2) >= 0.16 * p.w:
                        for e_idx in (0, 1):
                            p_end = s[0] if e_idx == 0 else s[3]
                            p_base = s[3] if e_idx == 0 else s[0]
                            h_far = s[1] if e_idx == 0 else s[2]
                            u_int = unit(h_far - p_base)
                            if float(u_int @ unit(p_end - p_base)) > np.cos(np.radians(7.0)):
                                continue
                            perp_u = np.array([-u_int[1], u_int[0]])
                            best_hit2 = None
                            for j, fj in enumerate(polys_all):
                                if j == i or len(fj) < 2:
                                    continue
                                if float(np.min(np.linalg.norm(fj - p_end, axis=1))) > 0.75 * p.w:
                                    continue
                                vecs = fj - p_base
                                ts = vecs @ u_int
                                ps = np.abs(vecs @ perp_u)
                                mask_ray = (ts > 0.6 * L) & (ts <= 1.35 * L) & (ps <= 0.45 * p.w)
                                if not mask_ray.any():
                                    continue
                                idx_hit = int(np.where(mask_ray)[0][np.argmin(ps[mask_ray])])
                                pt_hit = fj[idx_hit]
                                if best_hit2 is None or float(np.linalg.norm(pt_hit - p_base)) < best_hit2[0]:
                                    best_hit2 = (float(np.linalg.norm(pt_hit - p_base)), pt_hit)
                            if best_hit2 is not None:
                                pt_hit = best_hit2[1]
                                if _has_ink_line(p_base, pt_hit, min_frac=0.88):
                                    p0_n = pt_hit if e_idx == 0 else p_base
                                    p1_n = p_base if e_idx == 0 else pt_hit
                                    ch_n = p1_n - p0_n
                                    new_s = np.array([p0_n, p0_n + ch_n / 3.0, p0_n + 2.0 * ch_n / 3.0, p1_n])
                                    cand = cur_m.copy()
                                    np_p = Path.from_segs([new_s], p.w, closed=False, join=p.join)
                                    np_p.ml = p.ml
                                    cand.paths[i] = np_p
                                    if try_accept(cand, step_soft_tol=22.0, step_iou_drop=0.0014, structural=True):
                                        polys_all[i] = cand.paths[i].flat(1.0)
                                        break
                continue
            if len(p.A) < 3:
                continue
            for e_idx in (0, 1):
                p_cur = cur_m.paths[i]
                if len(p_cur.A) < 3:
                    continue
                p_end = p_cur.A[0] if e_idx == 0 else p_cur.A[-1]
                p_base = p_cur.A[1] if e_idx == 0 else p_cur.A[-2]
                p_prev = p_cur.A[2] if e_idx == 0 else p_cur.A[-3]
                len_last = float(np.linalg.norm(p_end - p_base))
                len_prev = float(np.linalg.norm(p_base - p_prev))
                if len_last >= 2.15 * p_cur.w or len_prev < 0.4 * p_cur.w:
                    continue
                u_last = unit(p_end - p_base)
                u_int = unit(p_base - p_prev)
                if float(u_last @ u_int) > np.cos(np.radians(14.0)):
                    continue
                # Check if p_end is near another path j and u_int ray hits path j across solid ink in D
                best_hit = None
                perp_u = np.array([-u_int[1], u_int[0]])
                max_ray_t = 2.8 * p_cur.w if len_last < 1.35 * p_cur.w else 1.65 * p_cur.w
                for j, fj in enumerate(polys_all):
                    if j == i or len(fj) < 2:
                        continue
                    if float(np.min(np.linalg.norm(fj - p_end, axis=1))) > 0.75 * p_cur.w:
                        continue
                    # First check if an open endpoint of path j lies directly on the u_int ray (acute corner apex)
                    qj = cur_m.paths[j]
                    pt_hit = None
                    if not qj.closed and len(qj.A) >= 2:
                        for q_ep in (qj.A[0], qj.A[-1]):
                            if float(np.linalg.norm(q_ep - p_end)) <= 1.35 * p_cur.w:
                                v_ep = q_ep - p_base
                                t_ep = float(v_ep @ u_int)
                                p_ep = abs(float(v_ep @ perp_u))
                                if 0.2 * p_cur.w < t_ep <= max_ray_t and p_ep <= 0.45 * p_cur.w:
                                    pt_hit = q_ep.copy()
                                    break
                    if pt_hit is None:
                        vecs = fj - p_base
                        ts = vecs @ u_int
                        ps = np.abs(vecs @ perp_u)
                        mask_ray = (ts > 0.2 * p_cur.w) & (ts <= max_ray_t) & (ps <= 0.45 * p_cur.w)
                        if not mask_ray.any():
                            continue
                        idx_hit = int(np.where(mask_ray)[0][np.argmin(ps[mask_ray])])
                        pt_hit = fj[idx_hit]
                    if best_hit is None or float(np.linalg.norm(pt_hit - p_base)) < best_hit[0]:
                        best_hit = (float(np.linalg.norm(pt_hit - p_base)), pt_hit)
                if best_hit is not None:
                    pt_hit = best_hit[1]
                    if _has_ink_line(p_base, pt_hit, min_frac=0.85):
                        segs_p = p_cur.segs()
                        if e_idx == 0 and len(segs_p) >= 2:
                            new_s0 = segs_p[1].copy()
                            ch_s = new_s0[3] - pt_hit
                            new_s0[0] = pt_hit
                            new_s0[1] = pt_hit + ch_s / 3.0
                            new_s0[2] = pt_hit + 2.0 * ch_s / 3.0
                            new_segs = [new_s0] + segs_p[2:]
                        elif e_idx == 1 and len(segs_p) >= 2:
                            new_s1 = segs_p[-2].copy()
                            ch_s = pt_hit - new_s1[0]
                            new_s1[1] = new_s1[0] + ch_s / 3.0
                            new_s1[2] = new_s1[0] + 2.0 * ch_s / 3.0
                            new_s1[3] = pt_hit
                            new_segs = segs_p[:-2] + [new_s1]
                        else:
                            continue
                        cand = cur_m.copy()
                        np_p = Path.from_segs(new_segs, p_cur.w, closed=False, join=p_cur.join)
                        np_p.ml = p_cur.ml
                        cand.paths[i] = np_p
                        if try_accept(cand, step_soft_tol=22.0, step_iou_drop=0.0014, structural=True):
                            polys_all[i] = cand.paths[i].flat(1.0)

            # Case C: Orthogonal terminal lip deflection at perpendicular T-junctions
            p_cur = cur_m.paths[i]
            if p_cur.closed or len(p_cur.A) < 3:
                continue
            for e_idx in (0, 1):
                p_end = p_cur.A[0] if e_idx == 0 else p_cur.A[-1]
                p_base = p_cur.A[1] if e_idx == 0 else p_cur.A[-2]
                p_prev = p_cur.A[2] if e_idx == 0 else p_cur.A[-3]
                v_body = p_base - p_prev
                L_body = float(np.linalg.norm(v_body))
                if L_body < 0.5 * p_cur.w:
                    continue
                dx_body = abs(v_body[0])
                dy_body = abs(v_body[1])
                v_end = p_end - p_base
                L_end = float(np.linalg.norm(v_end))
                if L_end < 0.4 * p_cur.w or L_end > 3.0 * p_cur.w:
                    continue

                if dy_body <= 0.15 * p_cur.w and dx_body >= 0.6 * p_cur.w:
                    y_line = p_base[1]
                    dy_end = abs(p_end[1] - y_line)
                    if 0.08 * p_cur.w <= dy_end <= 0.38 * p_cur.w:
                        sign_x = 1.0 if v_end[0] > 0 else -1.0
                        best_x = None
                        for j, fj in enumerate(polys_all):
                            if j == i or len(fj) < 2:
                                continue
                            if float(np.min(np.linalg.norm(fj - p_end, axis=1))) > 0.85 * p_cur.w:
                                continue
                            d_pts = np.abs(fj[:, 1] - y_line)
                            mask_y = d_pts <= 0.35 * p_cur.w
                            if mask_y.any():
                                x_hits = fj[mask_y, 0]
                                valid_x = x_hits[(x_hits - p_base[0]) * sign_x > 0]
                                if len(valid_x) > 0:
                                    x_cand = float(valid_x[np.argmin(np.abs(valid_x - p_end[0]))])
                                    if best_x is None or abs(x_cand - p_end[0]) < abs(best_x - p_end[0]):
                                        best_x = x_cand
                        if best_x is not None:
                            p_snapped = np.array([best_x, y_line])
                            if _has_ink_line(p_base, p_snapped, min_frac=0.85):
                                cand = cur_m.copy()
                                T._move_end(cand.paths[i], e_idx, p_snapped)
                                p_c = cand.paths[i]
                                if e_idx == 0:
                                    p_c.Hin[0] = p_snapped
                                    p_c.Hout[0] = p_snapped + (p_base - p_snapped) / 3.0
                                    p_c.Hin[1] = np.array([p_base[0], y_line]) + (p_snapped - p_base) / 3.0
                                else:
                                    p_c.Hout[-1] = p_snapped
                                    p_c.Hin[-1] = p_snapped + (p_base - p_snapped) / 3.0
                                    p_c.Hout[-2] = np.array([p_base[0], y_line]) + (p_snapped - p_base) / 3.0
                                if try_accept(cand, step_soft_tol=28.0, step_iou_drop=0.0016, structural=True):
                                    polys_all[i] = cand.paths[i].flat(1.0)
                                    break
                elif dx_body <= 0.15 * p_cur.w and dy_body >= 0.6 * p_cur.w:
                    x_line = p_base[0]
                    dx_end = abs(p_end[0] - x_line)
                    if 0.08 * p_cur.w <= dx_end <= 0.38 * p_cur.w:
                        sign_y = 1.0 if v_end[1] > 0 else -1.0
                        best_y = None
                        for j, fj in enumerate(polys_all):
                            if j == i or len(fj) < 2:
                                continue
                            if float(np.min(np.linalg.norm(fj - p_end, axis=1))) > 0.85 * p_cur.w:
                                continue
                            d_pts = np.abs(fj[:, 0] - x_line)
                            mask_x = d_pts <= 0.35 * p_cur.w
                            if mask_x.any():
                                y_hits = fj[mask_x, 1]
                                valid_y = y_hits[(y_hits - p_base[1]) * sign_y > 0]
                                if len(valid_y) > 0:
                                    y_cand = float(valid_y[np.argmin(np.abs(valid_y - p_end[1]))])
                                    if best_y is None or abs(y_cand - p_end[1]) < abs(best_y - p_end[1]):
                                        best_y = y_cand
                        if best_y is not None:
                            p_snapped = np.array([x_line, best_y])
                            if _has_ink_line(p_base, p_snapped, min_frac=0.85):
                                cand = cur_m.copy()
                                T._move_end(cand.paths[i], e_idx, p_snapped)
                                p_c = cand.paths[i]
                                if e_idx == 0:
                                    p_c.Hin[0] = p_snapped
                                    p_c.Hout[0] = p_snapped + (p_base - p_snapped) / 3.0
                                    p_c.Hin[1] = np.array([x_line, p_base[1]]) + (p_snapped - p_base) / 3.0
                                else:
                                    p_c.Hout[-1] = p_snapped
                                    p_c.Hin[-1] = p_snapped + (p_base - p_snapped) / 3.0
                                    p_c.Hout[-2] = np.array([x_line, p_base[1]]) + (p_snapped - p_base) / 3.0
                                if try_accept(cand, step_soft_tol=28.0, step_iou_drop=0.0016, structural=True):
                                    polys_all[i] = cand.paths[i].flat(1.0)
                                    break

    # ------------------------------------------------------------------
    # 2.6. Universal Multi-Branch Junction (Degree >= 2) Regularizer
    # ------------------------------------------------------------------
    def _regularize_multi_branch_junctions():
        cluster_radius = 1.35 * W0
        ends = []
        for i_p, p_p in enumerate(cur_m.paths):
            if p_p.closed or len(p_p.A) < 2:
                continue
            ends.append((i_p, 0, p_p.A[0], unit(p_p.A[0] - p_p.A[1])))
            ends.append((i_p, 1, p_p.A[-1], unit(p_p.A[-1] - p_p.A[-2])))

        if len(ends) >= 2:
            adj = {idx: set() for idx in range(len(ends))}
            for a in range(len(ends)):
                for b in range(a + 1, len(ends)):
                    if ends[a][0] == ends[b][0]:
                        continue
                    dist = float(np.linalg.norm(ends[a][2] - ends[b][2]))
                    if dist <= cluster_radius:
                        adj[a].add(b)
                        adj[b].add(a)

            visited = set()
            for idx in range(len(ends)):
                if idx not in visited and adj[idx]:
                    comp = []
                    queue = [idx]
                    visited.add(idx)
                    while queue:
                        curr = queue.pop(0)
                        comp.append(curr)
                        for nb in adj[curr]:
                            if nb not in visited:
                                visited.add(nb)
                                queue.append(nb)
                    if len(comp) >= 2:
                        cluster_ends = [ends[i_e] for i_e in comp]
                        # Dash guard: do not cluster collinear dashes/stubs
                        dirs = [item[3] for item in cluster_ends]
                        has_branching = False
                        for d1_idx in range(len(dirs)):
                            for d2_idx in range(d1_idx + 1, len(dirs)):
                                cr_val = abs(dirs[d1_idx][0] * dirs[d2_idx][1] - dirs[d1_idx][1] * dirs[d2_idx][0])
                                if cr_val >= 0.35: # angle >= 20 deg
                                    has_branching = True
                                    break
                            if has_branching:
                                break
                        if not has_branching:
                            continue

                        j_cand = np.mean([item[2] for item in cluster_ends], axis=0)

                        horiz_pts = [item[2] for item in cluster_ends if abs(item[3][1]) <= 0.28 and abs(item[3][0]) >= 0.85]
                        vert_pts = [item[2] for item in cluster_ends if abs(item[3][0]) <= 0.28 and abs(item[3][1]) >= 0.85]
                        if horiz_pts and vert_pts:
                            y_corner = float(np.mean([pt[1] for pt in horiz_pts]))
                            x_corner = float(np.mean([pt[0] for pt in vert_pts]))
                            c_corner = np.array([x_corner, y_corner])
                            if float(np.linalg.norm(c_corner - j_cand)) <= 1.25 * W0:
                                xi = int(np.clip(round(x_corner), 0, W_im - 1))
                                yi = int(np.clip(round(y_corner), 0, H_im - 1))
                                if D[yi, xi] > 0.35:
                                    j_cand = c_corner

                        valid = True
                        for i_p, e_idx, pt, _ in cluster_ends:
                            if float(np.linalg.norm(pt - j_cand)) > 0.15:
                                ts = np.linspace(0.0, 1.0, 10)[:, None]
                                l_pts = pt * (1.0 - ts) + j_cand * ts
                                xs = np.clip(np.round(l_pts[:, 0] - 0.5).astype(int), 0, W_im - 1)
                                ys = np.clip(np.round(l_pts[:, 1] - 0.5).astype(int), 0, H_im - 1)
                                if float((D[ys, xs] > 0.35).mean()) < 0.68:
                                    valid = False
                                    break
                        if valid:
                            cand = cur_m.copy()
                            for i_p, e_idx, pt, _ in cluster_ends:
                                T._move_end(cand.paths[i_p], e_idx, j_cand)
                            try_accept(cand, step_soft_tol=35.0, step_iou_drop=0.0035, structural=True)

    # ------------------------------------------------------------------
    # 2.7. Universal Acute & Sharp Corner Apex Ray-Extension Regularizer
    # ------------------------------------------------------------------
    def _regularize_acute_and_corner_apexes():
        for i_p, p_p in enumerate(cur_m.paths):
            A = p_p.A
            N = len(A)
            if N < 3:
                continue
            w_eff = p_p.w or W0
            num_pts = N - 1 if p_p.closed else N
            for k in range(num_pts):
                if not p_p.closed and (k == 0 or k == num_pts - 1):
                    continue
                kp = (k - 1) % num_pts if p_p.closed else k - 1
                kn = (k + 1) % num_pts if p_p.closed else k + 1
                facet_indices = [k]
                len_fwd = float(np.linalg.norm(A[kn] - A[k]))
                if len_fwd <= 1.35 * w_eff and num_pts >= 4:
                    if not p_p.closed and kn + 1 >= N:
                        continue
                    facet_indices.append(kn)
                    kn = (kn + 1) % num_pts if p_p.closed else kn + 1

                if not p_p.closed and (kn >= N or kp < 0):
                    continue

                k_start = facet_indices[0]
                k_end = facet_indices[-1]

                v_in = A[k_start] - A[kp]
                l_in = float(np.linalg.norm(v_in))
                if l_in < 1.0:
                    continue
                u_in = v_in / l_in

                v_out = A[kn] - A[k_end]
                l_out = float(np.linalg.norm(v_out))
                if l_out < 1.0:
                    continue
                u_out = v_out / l_out

                cos_turn = float(u_in @ u_out)
                if cos_turn > np.cos(np.radians(55.0)):
                    continue

                # CURVE GUARD: never turn smooth curves into sharp corner apexes!
                perp_in = np.array([-u_in[1], u_in[0]])
                perp_out = np.array([-u_out[1], u_out[0]])
                dev_in = max(abs(float((p_p.Hout[kp] - A[kp]) @ perp_in)), abs(float((p_p.Hin[k_start] - A[kp]) @ perp_in)))
                dev_out = max(abs(float((p_p.Hout[k_end] - A[k_end]) @ perp_out)), abs(float((p_p.Hin[kn] - A[k_end]) @ perp_out)))
                if dev_in > 0.35 * w_eff or dev_out > 0.35 * w_eff:
                    continue  # Segment has intentional curvature; preserve curve!

                C = _intersect_rays(A[kp], A[k_start], A[kn], A[k_end])
                if C is None:
                    continue

                near_open_ends = []
                for j_o, q_o in enumerate(cur_m.paths):
                    if j_o == i_p or q_o.closed or len(q_o.A) < 2:
                        continue
                    for e_idx in (0, 1):
                        ep = q_o.A[0] if e_idx == 0 else q_o.A[-1]
                        if float(np.linalg.norm(ep - C)) <= 0.85 * w_eff:
                            near_open_ends.append((j_o, e_idx))

                if len(facet_indices) > 1 and len_fwd > 0.75 * w_eff and not near_open_ends:
                    continue

                mid_facet = 0.5 * (A[k_start] + A[k_end])
                shift_dist = float(np.linalg.norm(C - mid_facet))
                max_shift = 1.65 * w_eff if near_open_ends else 1.25 * w_eff
                if shift_dist > max_shift or shift_dist < 0.25:
                    continue

                ts = np.linspace(0.0, 1.0, 12)[:, None]
                line_pts = mid_facet * (1.0 - ts) + C * ts
                xs = np.clip(np.round(line_pts[:, 0] - 0.5).astype(int), 0, W_im - 1)
                ys = np.clip(np.round(line_pts[:, 1] - 0.5).astype(int), 0, H_im - 1)
                if float((D[ys, xs] > 0.45).mean()) < 0.80:
                    continue

                cand = cur_m.copy()
                cp = cand.paths[i_p]
                if len(facet_indices) == 1:
                    cp.A[k_start] = C.copy()
                    ch_in = C - cp.A[kp]
                    ch_out = cp.A[kn] - C
                    cp.Hin[k_start] = C - ch_in / 3.0
                    cp.Hout[k_start] = C + ch_out / 3.0
                elif not p_p.closed and len(facet_indices) == 2:
                    cp.A[k_start] = C.copy()
                    cp.A = np.delete(cp.A, k_end, axis=0)
                    cp.Hin = np.delete(cp.Hin, k_end, axis=0)
                    cp.Hout = np.delete(cp.Hout, k_end, axis=0)
                    ch_in = C - cp.A[kp]
                    ch_out = cp.A[k_start + 1] - C
                    cp.Hout[kp] = cp.A[kp] + ch_in / 3.0
                    cp.Hin[k_start] = C - ch_in / 3.0
                    cp.Hout[k_start] = C + ch_out / 3.0
                    cp.Hin[k_start + 1] = C + 2.0 * ch_out / 3.0
                else:
                    for idx_f in facet_indices:
                        cp.A[idx_f] = C.copy()
                        cp.Hin[idx_f] = C.copy()
                        cp.Hout[idx_f] = C.copy()
                    if p_p.closed and (0 in facet_indices or (N - 1) in facet_indices):
                        cp.A[0] = C.copy()
                        cp.A[-1] = C.copy()
                for j_o, e_idx in near_open_ends:
                    T._move_end(cand.paths[j_o], e_idx, C)
                if try_accept(cand, step_soft_tol=35.0, step_iou_drop=0.0025, structural=True):
                    break

    # ------------------------------------------------------------------
    # 2.8. Circle-Stroke Tangent Regularizer (Robot Arm Hinge & Pulley Cables)
    # ------------------------------------------------------------------
    def _regularize_circle_tangents():
        for i_c, p_circ in enumerate(cur_m.paths):
            if not p_circ.closed or len(p_circ.A) < 4:
                continue
            f_circ = p_circ.flat(1.0)
            if len(f_circ) < 8:
                continue
            cx, cy, r_circ = _kasa(f_circ)
            if r_circ < 1.0 * W0:
                continue
            rad_err = np.abs(np.hypot(f_circ[:, 0] - cx, f_circ[:, 1] - cy) - r_circ)
            if float(np.percentile(rad_err, 90)) > 0.22 * W0:
                continue
            center = np.array([cx, cy])

            for j_o, p_open in enumerate(cur_m.paths):
                if p_open.closed or len(p_open.A) < 2 or j_o == i_c:
                    continue
                for e_idx in (0, 1):
                    p_end = p_open.A[0] if e_idx == 0 else p_open.A[-1]
                    p_near = p_open.A[1] if e_idx == 0 else p_open.A[-2]
                    v_arm = p_near - p_end
                    l_arm = float(np.linalg.norm(v_arm))
                    if l_arm < 1.0:
                        continue
                    u_arm = v_arm / l_arm

                    dist_center = float(np.linalg.norm(p_end - center))
                    if abs(dist_center - r_circ) <= 0.85 * W0:
                        u_rad = unit(p_end - center)
                        cos_tangent = abs(float(u_rad @ u_arm))
                        if cos_tangent <= np.sin(np.radians(26.0)):
                            norm_arm = np.array([-u_arm[1], u_arm[0]])
                            if float(norm_arm @ (p_end - center)) < 0.0:
                                norm_arm = -norm_arm
                            pt_tangent = center + r_circ * norm_arm
                            if float(np.linalg.norm(pt_tangent - p_end)) <= 0.85 * W0:
                                cand = cur_m.copy()
                                T._move_end(cand.paths[j_o], e_idx, pt_tangent)
                                p_c = cand.paths[j_o]
                                h_len = min(l_arm / 3.0, 0.45 * r_circ)
                                if e_idx == 0:
                                    p_c.Hin[0] = pt_tangent.copy()
                                    p_c.Hout[0] = pt_tangent + u_arm * h_len
                                else:
                                    p_c.Hout[-1] = pt_tangent.copy()
                                    p_c.Hin[-1] = pt_tangent + u_arm * h_len
                                try_accept(cand, step_soft_tol=22.0, step_iou_drop=0.0012, structural=True)
                        elif cos_tangent >= np.cos(np.radians(22.0)):
                            pt_radial = center + r_circ * u_rad
                            if float(np.linalg.norm(pt_radial - p_end)) <= 0.85 * W0:
                                cand = cur_m.copy()
                                T._move_end(cand.paths[j_o], e_idx, pt_radial)
                                try_accept(cand, step_soft_tol=22.0, step_iou_drop=0.0012, structural=True)

    _reconstruct_broken_through_lines()
    _straighten_through_runs()
    _straighten_collinear_stem_trunks()
    _straighten_endpoint_hooks()
    _regularize_multi_branch_junctions()
    _regularize_acute_and_corner_apexes()
    _regularize_circle_tangents()

    # Self-check any remaining unjoined endpoints (gaps) where source image D has continuous black ink
    for kind, gi, ge, gj, gf, target, gap in T._plan(cur_m, r_end=1.35, r_t=1.15, min_gap=0.08):
        if gi >= len(cur_m.paths) or gj >= len(cur_m.paths):
            continue
        p1, t1 = T._end(cur_m.paths[gi], ge)
        # Verify continuous source ink between p1 and target
        ts_s = np.linspace(0.0, 1.0, 12)[:, None]
        line_pts = p1 * (1.0 - ts_s) + target * ts_s
        xs_s = np.clip(np.round(line_pts[:, 0] - 0.5).astype(int), 0, W_im - 1)
        ys_s = np.clip(np.round(line_pts[:, 1] - 0.5).astype(int), 0, H_im - 1)
        if float((D[ys_s, xs_s] > 0.40).mean()) < 0.68:
            continue
        # For T-junctions, also check if extending along outward ray t1 hits path gj cleanly
        cand = cur_m.copy()
        best_target = target
        if kind == "tee" and gf is None:
            fj = cur_m.paths[gj].flat(0.5)
            vecs = fj - p1
            ts_r = vecs @ t1
            perp_u = np.array([-t1[1], t1[0]])
            ps_r = np.abs(vecs @ perp_u)
            m_ray = (ts_r > 0.0) & (ts_r <= 2.2 * cur_m.paths[gi].w) & (ps_r <= 0.55 * cur_m.paths[gi].w)
            if m_ray.any():
                idx_r = int(np.where(m_ray)[0][np.argmin(ps_r[m_ray])])
                best_target = fj[idx_r]
        T._move_end(cand.paths[gi], ge, best_target)
        if gf is not None:
            T._move_end(cand.paths[gj], gf, best_target)
        try_accept(cand, step_soft_tol=32.0, step_iou_drop=0.0035, structural=True)

    # ------------------------------------------------------------------
    # 3. Canonical 4-Anchor Circle / Ring Reconstruction
    # ------------------------------------------------------------------
    try:
        from . import rings as RG
        found_rings = [r for r in RG.detect_rings(D, W0) if r["r"] >= 1.2 * W0 and r.get("support", 0.0) >= 0.95]
        found_rings.sort(key=lambda r: -r["r"])
        for ring in found_rings:
            already_closed = False
            for p_chk in cur_m.paths:
                if p_chk.closed and len(p_chk.A) <= 6:
                    f_chk = p_chk.flat(1.0)
                    if len(f_chk) >= 8:
                        cx_p, cy_p, r_p = _kasa(f_chk)
                        if np.hypot(cx_p - ring["cx"], cy_p - ring["cy"]) <= 0.45 * W0 and abs(r_p - ring["r"]) <= 0.45 * W0:
                            already_closed = True
                            break
            if not already_closed:
                cand_ring = RG.apply_ring(cur_m, ring)
                if len(cand_ring.paths) <= len(cur_m.paths) + 3:
                    try_accept(cand_ring, step_soft_tol=125.0, step_iou_drop=0.0065, structural=True)
    except Exception:
        pass

    for i in range(len(cur_m.paths)):
        p = cur_m.paths[i]
        if p.closed and len(p.A) > 5:
            f = p.flat(0.5)
            if len(f) >= 12:
                # Guard: never convert an axis-aligned square/rectangle into a circle
                rx0, rx1 = np.percentile(f[:, 0], [3, 97])
                ry0, ry1 = np.percentile(f[:, 1], [3, 97])
                d_rect = np.minimum(
                    np.minimum(np.abs(f[:, 0] - rx0), np.abs(f[:, 0] - rx1)),
                    np.minimum(np.abs(f[:, 1] - ry0), np.abs(f[:, 1] - ry1)),
                )
                cx, cy, r = _kasa(f)
                rad_err = np.abs(np.hypot(f[:, 0] - cx, f[:, 1] - cy) - r)
                if float(d_rect.mean()) <= float(rad_err.mean()) * 1.12:
                    continue
                if float(np.percentile(d_rect, 85)) <= max(1.25, 0.13 * p.w) and max(rx1 - rx0, ry1 - ry0) <= 3.6 * p.w:
                    continue
                if r >= 0.50 * p.w:
                    tol_rad = 0.22 * p.w if r >= 1.2 * p.w else 0.18 * p.w
                    if float(np.percentile(rad_err, 90)) <= tol_rad:
                        center = np.array([cx, cy])
                        A_c, Hi_c, Ho_c = E.ellipse_beziers(center, r, r, 0.0)
                        cand = cur_m.copy()
                        cand.paths[i] = Path(A_c, Hi_c, Ho_c, p.w, p.join, p.ml, True)
                        if not try_accept(cand, step_soft_tol=24.0, step_iou_drop=0.0012, structural=True):
                            for j, q in enumerate(cand.paths):
                                if j == i or q.closed:
                                    continue
                                for e_idx, pt in ((0, q.A[0]), (1, q.A[-1])):
                                    d_old = float(np.min(np.linalg.norm(f - pt, axis=1)))
                                    if d_old <= 0.35 * p.w:
                                        u_rad = unit(pt - center)
                                        T._move_end(q, e_idx, center + r * u_rad)
                            try_accept(cand, step_soft_tol=24.0, step_iou_drop=0.0012, structural=True)

    # ------------------------------------------------------------------
    # 3.1. Smart Canonical Square / Rectangle Reconstructor & Grid Equalizer
    # ------------------------------------------------------------------
    def _make_rect_path(x0: float, y0: float, x1: float, y1: float, w: float, join: str = "round", ml: float = 4.0) -> Path:
        pts_r = [
            np.array([x0, y0], float),
            np.array([x1, y0], float),
            np.array([x1, y1], float),
            np.array([x0, y1], float),
        ]
        segs_r = []
        for k_r in range(4):
            a_r, b_r = pts_r[k_r], pts_r[(k_r + 1) % 4]
            d_r = b_r - a_r
            segs_r.append(np.array([a_r, a_r + d_r / 3.0, a_r + 2.0 * d_r / 3.0, b_r]))
        pr = Path.from_segs(segs_r, w, closed=True, join=join)
        pr.ml = ml
        return pr

    rect_infos = []  # [(path_idx, cx, cy, bw, bh, w)]
    for i in range(len(cur_m.paths)):
        p = cur_m.paths[i]
        if not p.closed or len(p.A) < 5:
            continue
        f = p.flat(0.5)
        if len(f) < 12:
            continue
        x0, x1 = float(np.percentile(f[:, 0], 1.5)), float(np.percentile(f[:, 0], 98.5))
        y0, y1 = float(np.percentile(f[:, 1], 1.5)), float(np.percentile(f[:, 1], 98.5))
        bw, bh = x1 - x0, y1 - y0
        if bw < 1.05 * p.w or bh < 1.05 * p.w or max(bw, bh) > 6.2 * p.w:
            continue
        d_rect = np.minimum(
            np.minimum(np.abs(f[:, 0] - x0), np.abs(f[:, 0] - x1)),
            np.minimum(np.abs(f[:, 1] - y0), np.abs(f[:, 1] - y1)),
        )
        cx_c, cy_c, r_c = _kasa(f)
        rad_c = np.abs(np.hypot(f[:, 0] - cx_c, f[:, 1] - cy_c) - r_c)
        if float(d_rect.mean()) > float(rad_c.mean()) * 0.92:
            continue
        if float(np.percentile(d_rect, 85)) > max(1.20, 0.13 * p.w) or float(d_rect.mean()) > max(0.55, 0.062 * p.w):
            continue
        if float(np.percentile(d_rect, 96)) > max(1.75, 0.19 * p.w):
            continue
        # Verify all 4 corners have ink in D (protects rounded-corner shapes)
        corners_ok = True
        for cx_k, cy_k in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ix = int(np.clip(round(cx_k - 0.5), 0, W_im - 1))
            iy = int(np.clip(round(cy_k - 0.5), 0, H_im - 1))
            if float(D[iy, ix]) < 0.45:
                corners_ok = False
                break
        if not corners_ok:
            continue
        cx_r, cy_r = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        if abs(bw - bh) <= 0.10 * max(bw, bh):
            s_eq = 0.5 * (bw + bh)
            bw, bh = s_eq, s_eq
        cur_m.paths[i] = _make_rect_path(cx_r - 0.5 * bw, cy_r - 0.5 * bh, cx_r + 0.5 * bw, cy_r + 0.5 * bh, p.w, p.join, p.ml)
        rect_infos.append([i, cx_r, cy_r, bw, bh, p.w])

    # Equalize repeating squares/rectangles (e.g. 3x3 keypad grids, paired plug slots)
    if len(rect_infos) >= 2:
        used_g = set()
        for a_idx in range(len(rect_infos)):
            if a_idx in used_g:
                continue
            grp = [a_idx]
            used_g.add(a_idx)
            _, _, _, bw_a, bh_a, _ = rect_infos[a_idx]
            for b_idx in range(a_idx + 1, len(rect_infos)):
                if b_idx in used_g:
                    continue
                _, _, _, bw_b, bh_b, _ = rect_infos[b_idx]
                if abs(bw_a - bw_b) <= 0.22 * max(bw_a, bw_b) and abs(bh_a - bh_b) <= 0.22 * max(bh_a, bh_b):
                    grp.append(b_idx)
                    used_g.add(b_idx)
            if len(grp) >= 2:
                med_bw = float(np.median([rect_infos[g][3] for g in grp]))
                med_bh = float(np.median([rect_infos[g][4] for g in grp]))
                med_w = float(np.median([rect_infos[g][5] for g in grp]))
                if abs(med_bw - med_bh) <= 0.10 * max(med_bw, med_bh):
                    med_bw = med_bh = 0.5 * (med_bw + med_bh)
                cxs = [rect_infos[g][1] for g in grp]
                cys = [rect_infos[g][2] for g in grp]
                for g in grp:
                    near_x = [x_v for x_v in cxs if abs(x_v - rect_infos[g][1]) <= 0.30 * W0]
                    near_y = [y_v for y_v in cys if abs(y_v - rect_infos[g][2]) <= 0.30 * W0]
                    rect_infos[g][1] = float(np.median(near_x))
                    rect_infos[g][2] = float(np.median(near_y))
                best_grp_paths = None
                best_grp_soft = None
                for s_sc, w_sc in ((1.0, 1.0), (0.975, 0.96), (0.955, 0.94)):
                    cand_g = cur_m.copy()
                    bw_t, bh_t, w_t = med_bw * s_sc, med_bh * s_sc, med_w * w_sc
                    for g in grp:
                        pi_g, cx_g, cy_g, _, _, _ = rect_infos[g]
                        p_old = cand_g.paths[pi_g]
                        cand_g.paths[pi_g] = _make_rect_path(
                            cx_g - 0.5 * bw_t, cy_g - 0.5 * bh_t,
                            cx_g + 0.5 * bw_t, cy_g + 0.5 * bh_t,
                            w_t, p_old.join, p_old.ml,
                        )
                    s_g = doctor.soft(ink_of(cand_g))
                    if best_grp_soft is None or s_g < best_grp_soft:
                        best_grp_soft = s_g
                        best_grp_paths = [cand_g.paths[rect_infos[g][0]] for g in grp]
                for idx_k, g in enumerate(grp):
                    cur_m.paths[rect_infos[g][0]] = best_grp_paths[idx_k]
    if rect_infos:
        cur_ink = ink_of(cur_m)
        cur_s = doctor.soft(cur_ink)
        cur_iou = doctor.iou(cur_ink)
        min_allowed_iou = min(min_allowed_iou, cur_iou - 0.0010)
        max_allowed_soft = max(max_allowed_soft, cur_s + 24.0)

    # Remove redundant short open duplicate strokes that lie on top of existing paths
    from scipy.spatial import cKDTree as _cKDTree
    i_rem = 0
    while i_rem < len(cur_m.paths):
        p_r = cur_m.paths[i_rem]
        if not p_r.closed and 0.35 * p_r.w < p_r.length() < 4.5 * W0 and len(cur_m.paths) > 1:
            other_pts = [q_r.flat(0.5) for j_r, q_r in enumerate(cur_m.paths) if j_r != i_rem]
            if other_pts:
                tr_o = _cKDTree(np.vstack(other_pts))
                ds_o, _ = tr_o.query(p_r.flat(0.5))
                if float((ds_o < 0.45 * max(p_r.w, W0)).mean()) >= 0.65:
                    cand_rem = E.remove_path(cur_m, i_rem)
                    if try_accept(cand_rem, step_soft_tol=10.0, step_iou_drop=0.0006, structural=True):
                        continue
        i_rem += 1

    # Center-align short nearly-orthogonal open strokes (e.g. keyholes, ticks) on their ink centroid
    for i_s, p_s in enumerate(cur_m.paths):
        if p_s.closed or len(p_s.A) < 2:
            continue
        f_s = p_s.flat(1.0)
        dx_a = abs(float(p_s.A[-1, 0] - p_s.A[0, 0]))
        dy_a = abs(float(p_s.A[-1, 1] - p_s.A[0, 1]))
        dx_s = float(np.ptp(f_s[:, 0]))
        dy_s = float(np.ptp(f_s[:, 1]))
        if dx_a <= 0.55 * p_s.w and dx_s <= 0.68 * p_s.w and 1.1 * p_s.w <= dy_a <= 4.0 * p_s.w:
            y0_i = max(0, int(round(min(p_s.A[0, 1], p_s.A[-1, 1]))))
            y1_i = min(H_im, int(round(max(p_s.A[0, 1], p_s.A[-1, 1]))) + 1)
            x0_i = max(0, int(round(min(p_s.A[0, 0], p_s.A[-1, 0]) - 0.85 * p_s.w)))
            x1_i = min(W_im, int(round(max(p_s.A[0, 0], p_s.A[-1, 0]) + 0.85 * p_s.w)) + 1)
            sub_d = D[y0_i:y1_i, x0_i:x1_i]
            if sub_d.size > 0 and float(sub_d.sum()) > 1.0:
                xs_grid = np.arange(x0_i, x1_i, dtype=float)[None, :] + 0.5
                x_cent = float((sub_d * xs_grid).sum() / sub_d.sum())
                if abs(x_cent - 0.5 * float(p_s.A[0, 0] + p_s.A[-1, 0])) <= 0.55 * p_s.w:
                    A0 = np.array([x_cent, float(p_s.A[0, 1])])
                    A1 = np.array([x_cent, float(p_s.A[-1, 1])])
                    if _has_ink_line(A0, A1, min_frac=0.90):
                        ch_s = A1 - A0
                        cur_m.paths[i_s] = Path(
                            np.array([A0, A1]),
                            np.array([A0, A0 + 2.0 * ch_s / 3.0]),
                            np.array([A0 + ch_s / 3.0, A1]),
                            p_s.w, p_s.join, p_s.ml, False
                        )
                        cur_ink = ink_of(cur_m)
                        cur_s = doctor.soft(cur_ink)
                        cur_iou = doctor.iou(cur_ink)

    # ------------------------------------------------------------------
    # 4. Whole-Path Straight Line Simplification (2 Anchors) & Collinear Split Welding
    # ------------------------------------------------------------------
    weld_col = True
    while weld_col:
        weld_col = False
        for i in range(len(cur_m.paths)):
            pi = cur_m.paths[i]
            if pi.closed or len(pi.A) < 2:
                continue
            for j in range(i + 1, len(cur_m.paths)):
                pj = cur_m.paths[j]
                if pj.closed or len(pj.A) < 2 or abs(pi.w - pj.w) > 0.35 * max(pi.w, pj.w):
                    continue
                for ei in (0, 1):
                    epi = pi.A[0] if ei == 0 else pi.A[-1]
                    ui = unit((pi.A[0] - pi.A[1]) if ei == 0 else (pi.A[-1] - pi.A[-2]))
                    for ej in (0, 1):
                        epj = pj.A[0] if ej == 0 else pj.A[-1]
                        if float(np.linalg.norm(epi - epj)) > 0.35 * pi.w:
                            continue
                        uj = unit((pj.A[0] - pj.A[1]) if ej == 0 else (pj.A[-1] - pj.A[-2]))
                        if float(ui @ (-uj)) < np.cos(np.radians(12.0)):
                            continue
                        segs_i = pi.segs()
                        segs_j = pj.segs()
                        if ei == 0:
                            segs_i = [s[::-1].copy() for s in segs_i[::-1]]
                        if ej == 1:
                            segs_j = [s[::-1].copy() for s in segs_j[::-1]]
                        mid_ep = 0.5 * (segs_i[-1][3] + segs_j[0][0])
                        segs_i[-1][3] = mid_ep
                        segs_j[0][0] = mid_ep
                        cand = cur_m.copy()
                        np_w = Path.from_segs(segs_i + segs_j, 0.5 * (pi.w + pj.w), closed=False, join=pi.join)
                        np_w.ml = pi.ml
                        cand.paths[i] = np_w
                        del cand.paths[j]
                        if try_accept(cand, step_soft_tol=12.0, step_iou_drop=0.0008):
                            weld_col = True
                            break
                    if weld_col:
                        break
                if weld_col:
                    break
            if weld_col:
                break

    for i in range(len(cur_m.paths)):
        p = cur_m.paths[i]
        if not p.closed and len(p.A) > 2:
            f = p.flat(1.0)
            chord = p.A[-1] - p.A[0]
            L = float(np.linalg.norm(chord))
            if L > 2.0:
                u_ch = chord / L
                perp = np.array([-u_ch[1], u_ch[0]])
                max_dev = float(np.max(np.abs((f - p.A[0]) @ perp)))
                if max_dev <= max(0.65, 0.052 * p.w):
                    A_l = np.array([p.A[0], p.A[-1]])
                    Hi_l = np.array([p.A[0], p.A[0] + 2.0 * chord / 3.0])
                    Ho_l = np.array([p.A[0] + chord / 3.0, p.A[-1]])
                    cand = cur_m.copy()
                    cand.paths[i] = Path(A_l, Hi_l, Ho_l, p.w, p.join, p.ml, False)
                    try_accept(cand, step_soft_tol=22.0, step_iou_drop=0.0010)

    # ------------------------------------------------------------------
    # 4.5 - 6. Iterative V-Notch / Z-Fold Removal, Chamfer Collapse & Pairwise Cubic Simplification
    # ------------------------------------------------------------------
    for _pass in range(2):
        # Rotate closed paths so anchor 0 is at the sharpest corner BEFORE V-notch removal
        for i in range(len(cur_m.paths)):
            p = cur_m.paths[i]
            if p.closed and len(p.A) > 5:
                segs = p.segs()
                N = len(segs)
                turns = []
                for k in range(N):
                    v1 = unit(segs[(k - 1) % N][3] - segs[(k - 1) % N][0])
                    v2 = unit(segs[k][3] - segs[k][0])
                    turns.append(float(np.degrees(np.arccos(np.clip(v1 @ v2, -1.0, 1.0)))))
                best_k = int(np.argmax(turns))
                if best_k != 0:
                    segs = segs[best_k:] + segs[:best_k]
                    np_p = Path.from_segs(segs, p.w, closed=True, join=p.join)
                    np_p.ml = p.ml
                    cur_m.paths[i] = np_p

        # 4.5. Collinear Junction V-Notch & Terminal Z-Fold Removal
        for i in range(len(cur_m.paths)):
            changed = True
            while changed:
                changed = False
                p = cur_m.paths[i]
                segs = p.segs()
                min_s = 4 if p.closed else 2
                if len(segs) <= min_s:
                    break
                for k in range(len(segs) - 1):
                    s1, s2 = segs[k], segs[k + 1]
                    l1 = float(np.linalg.norm(s1[3] - s1[0]))
                    l2 = float(np.linalg.norm(s2[3] - s2[0]))
                    if min(l1, l2) >= 1.85 * p.w or max(l1, l2) >= 6.0 * p.w:
                        continue
                    ch_bridge = s2[3] - s1[0]
                    L_br = float(np.linalg.norm(ch_bridge))
                    if L_br < 2.0:
                        continue
                    u_br = ch_bridge / L_br
                    perp_br = np.array([-u_br[1], u_br[0]])
                    dent = abs(float((s1[3] - s1[0]) @ perp_br))
                    is_switchback = float((s1[3] - s1[0]) @ (s2[3] - s2[0])) < 0.0
                    has_ink_br = _has_ink_line(s1[0], s2[3], min_frac=0.90)
                    max_dent = 1.15 * p.w if has_ink_br else 0.75 * p.w
                    if not ((0.0 if is_switchback else 0.35) <= dent <= max_dent):
                        continue
                    if (min(l1, l2) >= 1.35 * p.w or max(l1, l2) >= 2.5 * p.w) and not has_ink_br:
                        continue
                    # Check if bridge aligns with neighboring segments
                    aligned = False
                    if k > 0:
                        u_prev = unit(segs[k - 1][3] - segs[k - 1][0])
                        if float(u_prev @ u_br) >= np.cos(np.radians(18.0)):
                            aligned = True
                    if k + 2 < len(segs):
                        u_next = unit(segs[k + 2][3] - segs[k + 2][0])
                        if float(u_br @ u_next) >= np.cos(np.radians(18.0)):
                            aligned = True
                    if not aligned:
                        continue
                    s_merged = np.array([s1[0], s1[0] + ch_bridge / 3.0, s1[0] + 2.0 * ch_bridge / 3.0, s2[3]])
                    new_segs = segs[:k] + [s_merged] + segs[k + 2:]
                    cand = cur_m.copy()
                    np_p = Path.from_segs(new_segs, p.w, closed=p.closed, join=p.join)
                    np_p.ml = p.ml
                    cand.paths[i] = np_p
                    if try_accept(cand, step_soft_tol=40.0 if has_ink_br else 18.0, step_iou_drop=0.0022 if has_ink_br else 0.0012, structural=has_ink_br):
                        changed = True
                        break

        # 4.6. Collinear Segment Handle-Belly Flattening (removes handle waves across T-junctions)
        for i in range(len(cur_m.paths)):
            p = cur_m.paths[i]
            segs = p.segs()
            if len(segs) < 2:
                continue
            for k in range(len(segs)):
                s = segs[k]
                ch = s[3] - s[0]
                L = float(np.linalg.norm(ch))
                if L < 2.0 or L > 6.5 * p.w:
                    continue
                u_c = ch / L
                perp = np.array([-u_c[1], u_c[0]])
                dev1 = abs(float((s[1] - s[0]) @ perp))
                dev2 = abs(float((s[2] - s[0]) @ perp))
                if not (0.12 * p.w <= max(dev1, dev2) <= 0.95 * p.w):
                    continue
                aligned_nb = False
                if k > 0 or p.closed:
                    s_prev = segs[(k - 1) % len(segs)]
                    if float(unit(s_prev[3] - s_prev[0]) @ u_c) >= np.cos(np.radians(12.0)):
                        aligned_nb = True
                if k + 1 < len(segs) or p.closed:
                    s_next = segs[(k + 1) % len(segs)]
                    if float(u_c @ unit(s_next[3] - s_next[0])) >= np.cos(np.radians(12.0)):
                        aligned_nb = True
                if aligned_nb and _has_ink_line(s[0], s[3], min_frac=0.90):
                    new_segs = [sg.copy() for sg in segs]
                    new_segs[k][1] = s[0] + ch / 3.0
                    new_segs[k][2] = s[0] + 2.0 * ch / 3.0
                    cand = cur_m.copy()
                    np_p = Path.from_segs(new_segs, p.w, closed=p.closed, join=p.join)
                    np_p.ml = p.ml
                    cand.paths[i] = np_p
                    if try_accept(cand, step_soft_tol=24.0, step_iou_drop=0.0015, structural=True):
                        segs = new_segs

        # 5. Corner Chamfer Collapse [DISABLED: curve & rounded corner protection]
        # if False:
        # for i in range(len(cur_m.paths)):
        # changed = True
        # while changed:
        # changed = False
        # p = cur_m.paths[i]
        # segs = p.segs()
        # min_segs = 4 if p.closed else 2
        # if len(segs) <= min_segs:
        # break
        # for k in range(len(segs)):
        # if not p.closed and (k == 0 or k == len(segs) - 1):
        # continue
        # s_curr = segs[k]
        # seg_len = float(np.linalg.norm(s_curr[3] - s_curr[0]))
        # if seg_len >= 0.75 * p.w:
        # continue
        # kp = (k - 1) % len(segs)
        # kn = (k + 1) % len(segs)
        # s_prev, s_next = segs[kp], segs[kn]
        # v_in = unit(s_prev[3] - s_prev[0])
        # v_out = unit(s_next[3] - s_next[0])
        # ang = float(np.degrees(np.arccos(np.clip(v_in @ v_out, -1.0, 1.0))))
        # if ang < 35.0:
        # continue
        #         # # CURVE GUARD: never collapse chamfer on curved segments!
        # L_prev = float(np.linalg.norm(s_prev[3] - s_prev[0]))
        # L_next = float(np.linalg.norm(s_next[3] - s_next[0]))
        # if L_prev < 1.0 or L_next < 1.0:
        # continue
        # u_prev = (s_prev[3] - s_prev[0]) / L_prev
        # u_next = (s_next[3] - s_next[0]) / L_next
        # perp_prev = np.array([-u_prev[1], u_prev[0]])
        # perp_next = np.array([-u_next[1], u_next[0]])
        # dev_prev = max(abs(float((s_prev[1] - s_prev[0]) @ perp_prev)), abs(float((s_prev[2] - s_prev[0]) @ perp_prev)))
        # dev_next = max(abs(float((s_next[1] - s_next[0]) @ perp_next)), abs(float((s_next[2] - s_next[0]) @ perp_next)))
        # if dev_prev > 0.25 * p.w or dev_next > 0.25 * p.w:
        # continue  # Keep smooth curves intact!
        # ch_curr = s_curr[3] - s_curr[0]
        # L_curr = float(np.linalg.norm(ch_curr))
        # if L_curr < 0.5:
        # continue
        # u_curr = ch_curr / L_curr
        # perp_curr = np.array([-u_curr[1], u_curr[0]])
        # dev_curr = max(abs(float((s_curr[1] - s_curr[0]) @ perp_curr)), abs(float((s_curr[2] - s_curr[0]) @ perp_curr)))
        # # ROUNDED CORNER GUARD: deliberate round corner arcs must never be chamfered!
        # if dev_curr > 0.05 * p.w or dev_curr > 0.45:
        # continue
        # C = _intersect_rays(s_prev[0], s_prev[3], s_next[3], s_next[0])
        # mid = 0.5 * (s_curr[0] + s_curr[3])
        # if C is None or np.linalg.norm(C - mid) > 1.0 * p.w:
        # continue
        # xi = int(np.clip(round(C[0]), 0, W_im - 1))
        # yi = int(np.clip(round(C[1]), 0, H_im - 1))
        # if D[yi, xi] < 0.35:
        # continue  # Source corner has no sharp ink (it is a smooth round corner)
        # new_prev = s_prev.copy()
        # new_next = s_next.copy()
        # ch_in = C - new_prev[0]
        # ch_out = new_next[3] - C
        # new_prev[1] = new_prev[0] + ch_in / 3.0
        # new_prev[2] = new_prev[0] + 2.0 * ch_in / 3.0
        # new_prev[3] = C
        # new_next[0] = C
        # new_next[1] = C + ch_out / 3.0
        # new_next[2] = C + 2.0 * ch_out / 3.0
        # new_segs = []
        # for idx_s in range(len(segs)):
        # if idx_s == k:
        # continue
        # elif idx_s == kp:
        # new_segs.append(new_prev)
        # elif idx_s == kn:
        # new_segs.append(new_next)
        # else:
        # new_segs.append(segs[idx_s])
        # cand = cur_m.copy()
        # np_p = Path.from_segs(new_segs, p.w, closed=p.closed, join=p.join)
        # np_p.ml = p.ml
        # cand.paths[i] = np_p
        # if try_accept(cand, step_soft_tol=5.0, step_iou_drop=0.0004):
        # changed = True
        # break
        #         # 5.5. Merge Adjacent Collinear Straight Segment Runs
        for i in range(len(cur_m.paths)):
            p = cur_m.paths[i]
            segs = p.segs()
            if len(segs) < 2:
                continue
            changed_str = True
            while changed_str and len(segs) >= 2:
                changed_str = False
                for k in range(len(segs) - 1):
                    s1, s2 = segs[k], segs[k + 1]
                    v1 = s1[3] - s1[0]
                    v2 = s2[3] - s2[0]
                    L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
                    if L1 < 1.0 or L2 < 1.0:
                        continue
                    u1, u2 = v1 / L1, v2 / L2
                    perp1 = np.array([-u1[1], u1[0]])
                    perp2 = np.array([-u2[1], u2[0]])
                    dev1 = max(abs(float((s1[1] - s1[0]) @ perp1)), abs(float((s1[2] - s1[0]) @ perp1)))
                    dev2 = max(abs(float((s2[1] - s2[0]) @ perp2)), abs(float((s2[2] - s2[0]) @ perp2)))
                    max_d = max(0.40, 0.05 * p.w)
                    if dev1 <= max_d and dev2 <= max_d:
                        ch_total = s2[3] - s1[0]
                        L_tot = float(np.linalg.norm(ch_total))
                        if L_tot > 1.0:
                            u_tot = ch_total / L_tot
                            if float(u1 @ u_tot) >= np.cos(np.radians(6.0)) and float(u2 @ u_tot) >= np.cos(np.radians(6.0)):
                                s_new = np.array([s1[0], s1[0] + ch_total / 3.0, s1[0] + 2.0 * ch_total / 3.0, s2[3]])
                                cand_segs = segs[:k] + [s_new] + segs[k + 2:]
                                cand_p = Path.from_segs(cand_segs, p.w, closed=p.closed, join=p.join)
                                cand_p.ml = p.ml
                                cand_m = cur_m.copy()
                                cand_m.paths[i] = cand_p
                                if try_accept(cand_m, step_soft_tol=18.0, step_iou_drop=0.0010, structural=True):
                                    segs = cand_segs
                                    changed_str = True
                                    break

        # 6. Greedy Pairwise Cubic Simplification [DISABLED: curve & rounded corner protection]
        # if False:
        # for i in range(len(cur_m.paths)):
        # p = cur_m.paths[i]
        # segs = p.segs()
        # min_segs = 4 if p.closed else 1
        # if len(segs) <= min_segs:
        # continue
        #         # # Rotate closed path so anchor 0 is at the sharpest corner
        # if p.closed and len(segs) > 4:
        # N = len(segs)
        # turns = []
        # for k in range(N):
        # v1 = unit(segs[(k - 1) % N][3] - segs[(k - 1) % N][0])
        # v2 = unit(segs[k][3] - segs[k][0])
        # turns.append(float(np.degrees(np.arccos(np.clip(v1 @ v2, -1.0, 1.0)))))
        # best_k = int(np.argmax(turns))
        # if best_k != 0:
        # segs = segs[best_k:] + segs[:best_k]
        #         # seg_orig_pts = [bez(s, np.linspace(0, 1, 20)) for s in segs]
        # max_err_px = max(0.60, 0.045 * p.w)
        # skip_seams = set()
        #         # while len(segs) > min_segs:
        # best_err = 999.0
        # best_idx = -1
        # best_cubic = None
        # best_pts = None
        # best_seam_key = None
        #         # for k in range(len(segs) - 1):
        # s1, s2 = segs[k], segs[k + 1]
        # seam_key = (round(float(s1[3][0]), 1), round(float(s1[3][1]), 1))
        # if seam_key in skip_seams:
        # continue
        # v1 = s1[3] - s1[0]
        # v2 = s2[3] - s2[0]
        # L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        # if L1 < 1.0 or L2 < 1.0:
        # continue
        # u1, u2 = v1 / L1, v2 / L2
        # if float(u1 @ u2) < np.cos(np.radians(24.0)):
        # continue
        #         # t_in = unit(s1[3] - s1[2]) if np.linalg.norm(s1[3] - s1[2]) > 1e-4 else u1
        # t_out = unit(s2[1] - s2[0]) if np.linalg.norm(s2[1] - s2[0]) > 1e-4 else u2
        # if float(t_in @ t_out) < np.cos(np.radians(24.0)):
        # continue
        # p1_orig = seg_orig_pts[k]
        # p2_orig = seg_orig_pts[k + 1]
        # loc_in = unit(p1_orig[-1] - p1_orig[max(0, len(p1_orig) - 5)])
        # loc_out = unit(p2_orig[min(len(p2_orig) - 1, 4)] - p2_orig[0])
        # if float(loc_in @ loc_out) < np.cos(np.radians(24.0)):
        # continue
        #         # # Tangent turn from start of s1 to end of s2: max 34 degrees
        # t_start = unit(s1[1] - s1[0]) if np.linalg.norm(s1[1] - s1[0]) > 1e-4 else u1
        # t_end = unit(s2[3] - s2[2]) if np.linalg.norm(s2[3] - s2[2]) > 1e-4 else u2
        # if float(t_start @ t_end) < np.cos(np.radians(34.0)):
        # continue
        #         # pts_pair = np.vstack([p1_orig, p2_orig[1:]])
        # c_m, err = fit_free_cubic(pts_pair)
        # eff_err = err
        # if eff_err < best_err:
        # best_err = eff_err
        # best_idx = k
        # best_cubic = c_m
        # best_pts = pts_pair
        # best_seam_key = seam_key
        #         # if best_idx < 0 or best_err > max_err_px:
        # break
        #         # cand_segs = segs[:best_idx] + [best_cubic] + segs[best_idx + 2:]
        # cand_p = Path.from_segs(cand_segs, p.w, closed=p.closed, join=p.join)
        # cand_p.ml = p.ml
        # cand_m = cur_m.copy()
        # cand_m.paths[i] = cand_p
        # if try_accept(cand_m, step_soft_tol=24.0, step_iou_drop=0.0012):
        # segs = cand_segs
        # seg_orig_pts = seg_orig_pts[:best_idx] + [best_pts] + seg_orig_pts[best_idx + 2:]
        # else:
        # skip_seams.add(best_seam_key)
        #         # _straighten_endpoint_hooks()
        #         # # ------------------------------------------------------------------
    # 7. Handle Regularization (Exact Linear & Smooth G1 Handle Polish)
    # ------------------------------------------------------------------
    cand = cur_m.copy()
    modified_handles = False
    for p in cand.paths:
        segs = p.segs()
        seg_changed = False
        for k, s in enumerate(segs):
            ch = s[3] - s[0]
            L = float(np.linalg.norm(ch))
            if L < 1.0:
                continue
            u_c = ch / L
            perp = np.array([-u_c[1], u_c[0]])
            dev1 = abs(float((s[1] - s[0]) @ perp))
            dev2 = abs(float((s[2] - s[0]) @ perp))

            dx = abs(ch[0])
            dy = abs(ch[1])
            is_ortho = False
            if L >= 1.0 * p.w and _has_ink_line(s[0], s[3], min_frac=0.88):
                if dy <= 0.28 * p.w and dx >= 1.0 * p.w and dy < 0.22 * dx:
                    is_ortho = True
                elif dx <= 0.28 * p.w and dy >= 1.0 * p.w and dx < 0.22 * dy:
                    is_ortho = True

            if max(dev1, dev2) <= max(0.22, 0.025 * p.w):
                s[1] = s[0] + ch / 3.0
                s[2] = s[0] + 2.0 * ch / 3.0
                seg_changed = True
            else:
                h1 = float(np.linalg.norm(s[1] - s[0]))
                h2 = float(np.linalg.norm(s[3] - s[2]))
                if h1 > 0.78 * L:
                    s[1] = s[0] + unit(s[1] - s[0]) * (0.75 * L)
                    seg_changed = True
                if h2 > 0.78 * L:
                    s[2] = s[3] - unit(s[3] - s[2]) * (0.75 * L)
                    seg_changed = True
        if seg_changed:
            np_p = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
            p.A, p.Hin, p.Hout = np_p.A, np_p.Hin, np_p.Hout
            modified_handles = True
    if modified_handles:
        try_accept(cand, step_soft_tol=12.0, step_iou_drop=0.0006)

    return cur_m
