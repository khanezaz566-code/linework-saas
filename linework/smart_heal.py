"""Smartness Engine: Post-98% self-healing, broken path recovery, missed joint snapping,
small feature recovery, and geometric regularization for centerline vector line-art.
"""
from __future__ import annotations
import time
import numpy as np
import cv2
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize

from .model import Model, Path
from .geom import unit, bez
from . import finisher as FN
from . import joints as JN
from . import decision as DC
from . import topology as T
from . import edit as E


def find_broken_path_candidates(m: Model, D: np.ndarray, w: float):
    """Find pairs of open stroke ends (i, ei, j, ej) that are separated by a small gap
    where source raster ink D confirms they are two halves of the same continuous stroke."""
    H, W = D.shape
    open_ends = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        # Tangent pointing outward away from path body
        t0 = p.A[0] - p.Hout[0]
        if np.linalg.norm(t0) < 1e-4:
            t0 = p.A[0] - p.A[1]
        t0 = unit(t0)

        t1 = p.A[-1] - p.Hin[-1]
        if np.linalg.norm(t1) < 1e-4:
            t1 = p.A[-1] - p.A[-2]
        t1 = unit(t1)

        open_ends.append((i, 0, p.A[0], t0, p.w))
        open_ends.append((i, 1, p.A[-1], t1, p.w))

    cands = []
    max_gap = max(4.5, 3.0 * w)

    for a_idx in range(len(open_ends)):
        for b_idx in range(a_idx + 1, len(open_ends)):
            i, ei, pa, ta, wa = open_ends[a_idx]
            j, ej, pb, tb, wb = open_ends[b_idx]
            if i == j:
                continue
            w_pair = max(wa, wb)
            if abs(wa - wb) > 0.40 * w_pair:
                continue

            d_ab = float(np.linalg.norm(pb - pa))
            if d_ab < 0.20 * w_pair or d_ab > max_gap:
                continue

            v_ab = unit(pb - pa)
            dot_a = float(ta @ v_ab)
            dot_b = float(tb @ (-v_ab))
            facing = (dot_a > 0.30 and dot_b > 0.30) or float(ta @ tb) < -0.60

            # Check circular continuation if not straight facing
            from .rings import _kasa
            f_all = np.vstack([m.paths[i].flat(1.0), m.paths[j].flat(1.0)])
            on_circle = False
            if len(f_all) >= 8:
                cx, cy, r_circ = _kasa(f_all)
                if 1.0 * w_pair <= r_circ <= 40.0 * w_pair:
                    rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r_circ)
                    if float(np.percentile(rad_err, 90)) <= 0.28 * w_pair:
                        on_circle = True

            if not facing and not on_circle:
                continue

            # Check raster support along the gap
            n_samples = max(4, int(d_ab * 2.0))
            ts = np.linspace(0.0, 1.0, n_samples)
            pts = pa[None, :] + ts[:, None] * (pb - pa)[None, :]
            xs = np.clip(np.round(pts[:, 0]).astype(int), 0, W - 1)
            ys = np.clip(np.round(pts[:, 1]).astype(int), 0, H - 1)
            vals = D[ys, xs]

            # Cross-profile sample
            perp = np.array([-v_ab[1], v_ab[0]]) * (0.35 * w_pair)
            xs_p1 = np.clip(np.round(pts[:, 0] + perp[0]).astype(int), 0, W - 1)
            ys_p1 = np.clip(np.round(pts[:, 1] + perp[1]).astype(int), 0, H - 1)
            xs_p2 = np.clip(np.round(pts[:, 0] - perp[0]).astype(int), 0, W - 1)
            ys_p2 = np.clip(np.round(pts[:, 1] - perp[1]).astype(int), 0, H - 1)
            vals_max = np.maximum(vals, np.maximum(D[ys_p1, xs_p1], D[ys_p2, xs_p2]))

            mean_ink = float(vals_max.mean())
            min_ink = float(vals_max.min())

            if mean_ink >= 0.28 and min_ink >= 0.08:
                cands.append((d_ab, i, ei, j, ej, mean_ink))

    cands.sort(key=lambda t: t[0])
    return cands


def heal_broken_paths(model: Model, D: np.ndarray, w: float, doctor, ink_of, cur: float, time_ok=lambda: True):
    """Heal broken collinear and circular stroke pieces across raster ink bridges."""
    m = model.copy()
    cur_soft = cur
    total_healed = 0

    for _ in range(8):
        if not time_ok():
            break
        cands = find_broken_path_candidates(m, D, w)
        if not cands:
            break

        applied = False
        for d_ab, i, ei, j, ej, mean_ink in cands:
            if not time_ok():
                break
            if i >= len(m.paths) or j >= len(m.paths):
                continue
            cand_m = FN.join_pairs(m, [(i, ei, j, ej)])
            if cand_m is None or len(cand_m.paths) >= len(m.paths):
                continue

            ink_cand = ink_of(cand_m)
            s_cand = doctor.soft(ink_cand)
            iou_cand = doctor.iou(ink_cand)
            iou_cur = doctor.iou(ink_of(m))

            # Acceptance condition: soft mismatch does not degrade, or IoU improves
            if s_cand <= cur_soft + max(4.0, 0.003 * doctor.area) or iou_cand >= iou_cur - 0.0002:
                m = cand_m
                cur_soft = s_cand
                total_healed += 1
                applied = True
                break
        if not applied:
            break

    return m, cur_soft, total_healed


def snap_missed_joints(model: Model, D: np.ndarray, w: float, doctor, ink_of, cur: float, time_ok=lambda: True):
    """Find open endpoints terminating very close to another path without being connected,
    project them onto the target centerline, insert anchor if needed, and lock."""
    H, W = D.shape
    m = model.copy()
    cur_soft = cur
    total_snapped = 0

    for round_idx in range(4):
        if not time_ok():
            break
        open_ends = []
        for i, p in enumerate(m.paths):
            if p.closed or len(p.A) < 2:
                continue
            t0 = p.A[0] - p.Hout[0] if np.linalg.norm(p.A[0] - p.Hout[0]) > 1e-4 else p.A[0] - p.A[1]
            t1 = p.A[-1] - p.Hin[-1] if np.linalg.norm(p.A[-1] - p.Hin[-1]) > 1e-4 else p.A[-1] - p.A[-2]
            open_ends.append((i, 0, p.A[0], unit(t0), p.w))
            open_ends.append((i, 1, p.A[-1], unit(t1), p.w))

        snapped_in_round = False
        for i, e, pt, tangent, w_p in open_ends:
            if not time_ok():
                break
            if i >= len(m.paths):
                continue

            best_target = None
            min_dist = max(3.5, 2.2 * w)

            for j, q in enumerate(m.paths):
                if j == i:
                    continue
                f_q = q.flat(0.3)
                if len(f_q) == 0:
                    continue
                tree_q = cKDTree(f_q)

                # Nearest point
                d_near, idx_near = tree_q.query(pt)
                if d_near > min_dist:
                    continue

                # Ray projection
                steps = np.arange(0.0, min_dist, 0.25)
                ray = pt[None, :] + steps[:, None] * tangent[None, :]
                d_ray, idx_ray = tree_q.query(ray)
                min_ray_idx = int(np.argmin(d_ray))

                if d_ray[min_ray_idx] <= 0.40 * min(w_p, q.w):
                    target_pt = f_q[idx_ray[min_ray_idx]]
                    dist_to_target = float(np.linalg.norm(target_pt - pt))
                else:
                    target_pt = f_q[idx_near]
                    dist_to_target = float(d_near)

                if dist_to_target < 0.15 * min(w_p, q.w) or dist_to_target > min_dist:
                    continue

                # Raster ink between pt and target_pt
                n_pts = max(4, int(dist_to_target * 2))
                ts = np.linspace(0.0, 1.0, n_pts)
                segment_pts = pt[None, :] + ts[:, None] * (target_pt - pt)[None, :]
                xs = np.clip(np.round(segment_pts[:, 0]).astype(int), 0, W - 1)
                ys = np.clip(np.round(segment_pts[:, 1]).astype(int), 0, H - 1)
                vals = D[ys, xs]

                if vals.mean() >= 0.28:
                    if best_target is None or dist_to_target < best_target[0]:
                        best_target = (dist_to_target, j, target_pt)

            if best_target is not None:
                _, j, X_target = best_target
                cand_m = m.copy()
                JN._set_end(cand_m.paths[i], e, X_target)
                JN.insert_anchor(cand_m.paths[j], X_target)
                cand_m = JN.lock_joints(cand_m)

                ink_cand = ink_of(cand_m)
                s_cand = doctor.soft(ink_cand)

                if s_cand <= cur_soft + max(3.5, 0.003 * doctor.area):
                    m = cand_m
                    cur_soft = s_cand
                    total_snapped += 1
                    snapped_in_round = True
                    break
        if not snapped_in_round:
            break

    return m, cur_soft, total_snapped


def recover_small_features(model: Model, D: np.ndarray, w: float, doctor, ink_of, cur: float, time_ok=lambda: True):
    """Inspect hard residual miss-blobs without arbitrary waivers to restore
    small missing dots, inner ticks, or thin sub-strokes."""
    H, W = D.shape
    m = model.copy()
    cur_soft = cur
    total_recovered = 0

    ink_cur = ink_of(m)
    miss, extra = DC.hard_masks(D, ink_cur)

    n_comp, labels, stats, centroids = cv2.connectedComponentsWithStats((miss > 0.5).astype(np.uint8))

    blobs = []
    min_area = max(3, int(0.20 * w * w))
    max_area = int(6.0 * w * w)

    if m.paths:
        existing_pts = np.vstack([p.flat(1.0) for p in m.paths])
        tree_exist = cKDTree(existing_pts)
    else:
        tree_exist = None

    for c_id in range(1, n_comp):
        x, y, bw, bh, area = stats[c_id]
        if area < min_area or area > max_area:
            continue
        cx, cy = centroids[c_id]

        if tree_exist is not None and tree_exist.query([cx, cy])[0] < 0.65 * w:
            continue

        blobs.append((area, cx, cy, x, y, bw, bh, c_id))

    blobs.sort(key=lambda t: -t[0])

    for area, cx, cy, x, y, bw, bh, c_id in blobs[:10]:
        if not time_ok():
            break
        aspect = max(bw, bh) / max(1, min(bw, bh))
        radius = float(np.sqrt(area / np.pi))
        w_blob = float(np.clip(2.0 * radius, 0.6 * w, 1.8 * w))

        cand_path = None
        if aspect <= 1.6:
            c_pt = np.array([cx, cy])
            cand_path = Path(np.array([c_pt, c_pt]), np.array([c_pt, c_pt]), np.array([c_pt, c_pt]), w=w_blob, join="round")
        else:
            pad = int(max(3, round(0.5 * w)))
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(W, x + bw + pad), min(H, y + bh + pad)
            mask_blob = (labels[y0:y1, x0:x1] == c_id).astype(np.uint8)

            skel = skeletonize(mask_blob > 0)
            ys_sk, xs_sk = np.nonzero(skel)
            if len(ys_sk) >= 3:
                pts_sk = np.c_[xs_sk + x0 + 0.5, ys_sk + y0 + 0.5]
                cov = np.cov(pts_sk.T)
                eigvals, eigvecs = np.linalg.eigh(cov)
                v_main = eigvecs[:, 1]
                proj = pts_sk @ v_main
                order = np.argsort(proj)
                pts_sorted = pts_sk[order]

                p_start = pts_sorted[0]
                p_end = pts_sorted[-1]
                chord = p_end - p_start
                if np.linalg.norm(chord) >= 0.8 * w:
                    A = np.array([p_start, p_end])
                    Hin = np.array([p_start, p_start + 2.0 * chord / 3.0])
                    Hout = np.array([p_start + chord / 3.0, p_end])
                    cand_path = Path(A, Hin, Hout, w=w_blob, join="round")

        if cand_path is not None:
            cand_m = Model(m.paths + [cand_path], m.width, m.height)
            ink_cand = ink_of(cand_m)
            miss_cand, extra_cand = DC.hard_masks(D, ink_cand)
            hard_before = int(miss.sum() + extra.sum())
            hard_after = int(miss_cand.sum() + extra_cand.sum())
            s_cand = doctor.soft(ink_cand)

            if hard_after < hard_before and s_cand <= cur_soft + max(2.5, 0.002 * doctor.area):
                m = cand_m
                cur_soft = s_cand
                miss, extra = miss_cand, extra_cand
                total_recovered += 1
                if m.paths:
                    existing_pts = np.vstack([p.flat(1.0) for p in m.paths])
                    tree_exist = cKDTree(existing_pts)

    return m, cur_soft, total_recovered


def polish_straights_and_wobble(model: Model, D: np.ndarray, w: float, doctor, ink_of, cur: float, time_ok=lambda: True):
    """Straighten segments with wobbles/unnecessary extra bends while preserving true curves and sharp corners."""
    m = model.copy()
    cur_soft = cur
    total_straightened = 0

    for i, p in enumerate(list(m.paths)):
        if not time_ok():
            break
        if i >= len(m.paths) or len(p.segs()) < 1:
            continue

        segs = p.segs()
        changed = False
        new_p = p.copy()

        for k, c in enumerate(segs):
            v = c[3] - c[0]
            L = float(np.linalg.norm(v))
            if L < 1.8 * w:
                continue
            u = v / L
            perp = np.array([-u[1], u[0]])

            ts = np.linspace(0.0, 1.0, 15)
            pts = bez(c, ts)
            devs = np.abs((pts - c[0]) @ perp)
            max_dev = float(devs.max())

            tol_dev = max(0.40, 0.14 * w)
            if max_dev <= tol_dev:
                new_p.Hout[k] = new_p.A[k] + v / 3.0
                new_p.Hin[k + 1] = new_p.A[k] + 2.0 * v / 3.0

                dx, dy = abs(v[0]), abs(v[1])
                if dy <= 0.08 * w and dx >= 2.0 * w:
                    avg_y = 0.5 * (new_p.A[k][1] + new_p.A[k + 1][1])
                    new_p.A[k][1] = avg_y
                    new_p.A[k + 1][1] = avg_y
                    new_p.Hout[k][1] = avg_y
                    new_p.Hin[k + 1][1] = avg_y
                    changed = True
                elif dx <= 0.08 * w and dy >= 2.0 * w:
                    avg_x = 0.5 * (new_p.A[k][0] + new_p.A[k + 1][0])
                    new_p.A[k][0] = avg_x
                    new_p.A[k + 1][0] = avg_x
                    new_p.Hout[k][0] = avg_x
                    new_p.Hin[k + 1][0] = avg_x
                    changed = True
                else:
                    changed = True

        if changed:
            cand_m = m.copy()
            cand_m.paths[i] = new_p
            ink_cand = ink_of(cand_m)
            s_cand = doctor.soft(ink_cand)

            if s_cand <= cur_soft + max(2.0, 0.0015 * doctor.area):
                m = cand_m
                cur_soft = s_cand
                total_straightened += 1

    return m, cur_soft, total_straightened


def run_smart_heal(model: Model, D: np.ndarray, w: float, doctor, ink_of, cur: float, time_ok=lambda: True):
    """Run full Smartness Engine: Broken path healing -> Missed joint snapping -> Small feature recovery -> Anti-wobble polish."""
    m = model.copy()
    cur_soft = cur
    t0 = time.time()

    # 1. Broken path healing (vagga path recovery)
    m, cur_soft, n_healed = heal_broken_paths(m, D, w, doctor, ink_of, cur_soft, time_ok=time_ok)

    # 2. Missed joint snapping & locking (join mis recovery)
    m, cur_soft, n_snapped = snap_missed_joints(m, D, w, doctor, ink_of, cur_soft, time_ok=time_ok)

    # 3. Small missing feature recovery (dots, ticks)
    m, cur_soft, n_recovered = recover_small_features(m, D, w, doctor, ink_of, cur_soft, time_ok=time_ok)

    # 4. Anti-wobble & straightness regularization (line golo eke beke jay fix)
    m, cur_soft, n_straightened = polish_straights_and_wobble(m, D, w, doctor, ink_of, cur_soft, time_ok=time_ok)

    # Final lock
    m_locked = JN.lock_joints(m)
    ink_l = ink_of(m_locked)
    s_l = doctor.soft(ink_l)
    if s_l <= cur_soft + max(3.0, 0.002 * doctor.area):
        m = m_locked
        cur_soft = s_l

    report = dict(
        healed_paths=n_healed,
        snapped_joints=n_snapped,
        recovered_features=n_recovered,
        straightened_segments=n_straightened,
        seconds=round(time.time() - t0, 3)
    )
    return m, ink_of(m), cur_soft, report
