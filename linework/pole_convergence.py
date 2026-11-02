"""Pole and Apex Convergence Repair.
Detects poles and apexes where multiple strokes converge (e.g. Globe North/South poles,
compass stars, fan spokes, converging arcs) and closes gaps between meridian/spoke ends
and through-strokes/apex points with full Doctor validation.
"""
from __future__ import annotations
import numpy as np
from .model import Model


def repair_pole_convergences(m: Model, W0: float, doctor, ink_of, cur_soft: float):
    """Detects multi-stroke convergences to cardinal poles of circles or shared apexes.
    Returns (repaired_model, num_fixed).
    """
    open_paths = [(i, p) for i, p in enumerate(m.paths) if not p.closed and len(p.A) >= 2]
    if len(open_paths) < 2:
        return m, 0

    ends = []
    for i, p in open_paths:
        ends.append((i, 0, p.A[0], (p.A[0] - p.A[1]), p.w))
        ends.append((i, 1, p.A[-1], (p.A[-1] - p.A[-2]), p.w))

    # Detect circle poles across any closed circular path
    circle_poles = []
    for i, p in enumerate(m.paths):
        if p.closed and len(p.A) >= 3:
            pts = p.flat(0.5)
            cy, cx = pts[:, 1].mean(), pts[:, 0].mean()
            dists = np.linalg.norm(pts - np.array([cx, cy]), axis=1)
            r = float(np.mean(dists))
            if r > 10.0 and float(np.std(dists) / r) < 0.08:
                w_circ = p.w
                # Cardinal poles: North, South, West, East
                circle_poles.append((np.array([cx, cy - r]), w_circ))
                circle_poles.append((np.array([cx, cy + r]), w_circ))
                circle_poles.append((np.array([cx - r, cy]), w_circ))
                circle_poles.append((np.array([cx + r, cy]), w_circ))

    cur_m = m.copy()
    cur_s = cur_soft
    total_fixed = 0

    for pole_pt, w_circ in circle_poles:
        w_eff = max(W0, w_circ)
        nearby = []
        for pi, pe, pt, tang, pw in ends:
            d = float(np.linalg.norm(pt - pole_pt))
            if d <= 2.8 * max(w_eff, pw):
                nv = float(np.linalg.norm(tang))
                if nv > 1e-4:
                    u_tang = tang / nv
                    vec_to_pole = pole_pt - pt
                    d_pole = float(np.linalg.norm(vec_to_pole))
                    if d_pole > 1e-4:
                        u_to_pole = vec_to_pole / d_pole
                        # Pointing toward pole
                        if float(u_tang @ u_to_pole) > 0.30:
                            nearby.append((pi, pe, d, pt))

        if len(nearby) >= 2:
            cand_m = cur_m.copy()
            for pi, pe, d, _ in nearby:
                if d < 1.0:
                    continue  # already at the pole
                p = cand_m.paths[pi]
                if pe == 0:
                    # Prepend pole extension anchor
                    p.A = np.vstack([[pole_pt], p.A])
                    p.Hin = np.vstack([[pole_pt], p.Hin])
                    p.Hout = np.vstack([[pole_pt + (p.A[1] - pole_pt) * 0.3], p.Hout])
                else:
                    # Append pole extension anchor
                    p.A = np.vstack([p.A, [pole_pt]])
                    p.Hin = np.vstack([p.Hin, [pole_pt + (p.A[-2] - pole_pt) * 0.3]])
                    p.Hout = np.vstack([p.Hout, [pole_pt]])

            cand_ink = ink_of(cand_m)
            s_cand = doctor.soft(cand_ink)
            iou_cand = doctor.iou(cand_ink)
            iou_cur = doctor.iou(ink_of(cur_m))
            # Safe Fallback: only keep if soft improves or preserves within small tol
            if s_cand <= cur_s + max(3.0, 0.003 * cur_s) or iou_cand >= iou_cur - 0.001:
                cur_m = cand_m
                cur_s = s_cand
                total_fixed += 1

    return cur_m, total_fixed
