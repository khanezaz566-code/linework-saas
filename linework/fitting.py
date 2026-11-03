"""Initial model construction: chain polylines -> smooth Bezier paths with reconstructed sharp corners."""
from __future__ import annotations
import numpy as np, cv2
from .geom import resample, corners, linefit, line_inter, smooth, fit_curve
from .model import Model, Path

SS = 4


def draw_stroke(im, pts, w, miter, x0, y0, ml=8.0, ss=SS):
    """Rasterise a polyline stroke (round caps, round or miter joins) into `im` (uint8, scale ss)."""
    P = (pts - [x0, y0]) * ss
    r = w * ss / 2
    for a, b in zip(P[:-1], P[1:]):
        d = b - a
        n = np.linalg.norm(d)
        if n < 1e-6:
            continue
        d = d / n
        nn = np.array([-d[1], d[0]]) * r
        cv2.fillPoly(im, [np.round(np.array([a + nn, b + nn, b - nn, a - nn]) * 16).astype(np.int32)], 1, shift=4)
    for e in (P[0], P[-1]):
        cv2.circle(im, tuple(np.round(e).astype(int)), int(round(r)), 1, -1)
    for j in range(1, len(P) - 1):
        a, c, b = P[j - 1], P[j], P[j + 1]
        d1, d2 = c - a, b - c
        n1, n2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        d1, d2 = d1 / n1, d2 / n2
        cr = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cr) < 0.017 and d1 @ d2 > 0:
            continue
        if not miter:
            cv2.circle(im, tuple(np.round(c).astype(int)), int(round(r)), 1, -1)
            continue
        sg = -1 if cr > 0 else 1
        n1v = np.array([-d1[1], d1[0]]) * sg * r
        n2v = np.array([-d2[1], d2[0]]) * sg * r
        bis = n1v + n2v
        bl = np.linalg.norm(bis)
        if bl < 1e-6:
            continue
        ch = (bl / 2) / r
        mt = c + bis / bl * (r / ch) if ch > 1 / ml else None
        poly = [c, c + n1v, c + n2v] if mt is None else [c, c + n1v, mt, c + n2v]
        cv2.fillPoly(im, [np.round(np.array(poly) * 16).astype(np.int32)], 1, shift=4)


class CornerSolver:
    """Chooses, per detected corner, the best of {keep skeleton corner, extended/mitred corner}
    by rasterising candidates against the source ink map."""

    def __init__(self, D):
        self.D = D

    def local_cost(self, cands, w, center, rad):
        H, W = self.D.shape
        x0 = max(int(center[0] - rad), 0)
        y0 = max(int(center[1] - rad), 0)
        n = int(2 * rad)
        crop = self.D[y0 : y0 + n, x0 : x0 + n]
        if crop.size == 0:
            return [0] * len(cands)
        ref = cv2.resize(crop, None, fx=SS, fy=SS, interpolation=cv2.INTER_CUBIC) > 0.5
        rs = []
        for pts, miter in cands:
            im = np.zeros(ref.shape, np.uint8)
            draw_stroke(im, pts, w, miter, x0, y0)
            rs.append(im > 0)
        U = np.zeros(ref.shape, np.uint8)
        for r in rs:
            U |= r.astype(np.uint8)
        U = cv2.dilate(U, np.ones((SS * 4 + 1,) * 2, np.uint8)) > 0
        return [int(((r ^ ref) & U).sum()) for r in rs]

    def pieces(self, p, w):
        r = w / 2
        cs = corners(p, win=7, ang=35)
        out, cur = [], 0
        for i in cs:
            k = int(round(r * 1.1))
            a, b = i - k, i + k
            if b + 3 >= len(p) or a < 1:
                continue
            if a - 3 < cur:
                # corners packed closer than a stroke width (fine gear teeth): too tight to solve, but still keep them sharp
                if i - cur > 3:
                    out.append(("curve", p[cur : i + 1]))
                    cur = i
                continue
            ctx = int(3 * r)
            base = p[max(0, i - ctx) : i + ctx + 1]
            Cs = []
            if a - 14 >= cur and b + 14 < len(p):
                c1, d1, r1 = linefit(p[a - 14 : a])
                c2, d2, r2 = linefit(p[b : b + 14])
                if r1 < 0.5 and r2 < 0.5:
                    if d1 @ (p[a] - p[a - 14]) < 0:
                        d1 = -d1
                    if d2 @ (p[b + 13] - p[b]) < 0:
                        d2 = -d2
                    if np.degrees(np.arccos(np.clip(d1 @ d2, -1, 1))) >= 30:
                        C = line_inter(c1, d1, c2, d2)
                        if C is not None and np.linalg.norm(C - p[i]) < 3 * r:
                            for al in (0.4, 0.7, 1.0, 1.15):
                                Cs.append(p[i] + al * (C - p[i]))
            m = (p[i - 7] + p[i + 7]) / 2
            u = p[i] - m
            nu = np.linalg.norm(u)
            if nu > 1e-6:
                u = u / nu
                for s in (0, 1.5, 3.0, 5.0):
                    Cs.append(p[i] + u * s)
            cands = [(base, False), (base, True)]
            meta = [None, None]
            vin_base = p[i] - p[a]
            vout_base = p[b] - p[i]
            l_in_b, l_out_b = np.linalg.norm(vin_base), np.linalg.norm(vout_base)
            base_turn = float((vin_base / max(l_in_b, 1e-6)) @ (vout_base / max(l_out_b, 1e-6)))

            for C in Cs:
                v_in = C - p[a]
                v_out = p[b] - C
                l_in, l_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
                if l_in > 1e-3 and l_out > 1e-3:
                    cos_turn = float((v_in / l_in) @ (v_out / l_out))
                    if (cos_turn < -0.3 and base_turn > -0.2) or (cos_turn < base_turn - 0.35):
                        continue
                line = np.vstack([p[max(0, i - ctx) : a + 1], C, p[b : i + ctx + 1]])
                for mi in (False, True):
                    cands.append((line, mi))
                    meta.append((C, mi))
            costs = self.local_cost(cands, w, p[i], 4 * r)
            j = int(np.argmin(costs))
            if costs[j] >= min(costs[0], costs[1]) - 4:
                continue
            C, mi = meta[j]
            out.append(("curve", p[cur : a + 1]))
            n1 = max(2, int(np.linalg.norm(C - p[a])))
            out.append(("line", np.linspace(p[a], C, n1 + 1)))
            n2 = max(2, int(np.linalg.norm(p[b] - C)))
            out.append(("line", np.linspace(C, p[b], n2 + 1)))
            cur = b
        out.append(("curve", p[cur:]))
        return out


def initial_model(chains, D, sigma=2.0, err=0.3, dw=0.1) -> Model:
    """chains: list of dict(pts in source pixel-index coords, w). Returns Model in svg coords."""
    solver = CornerSolver(D)
    paths = []
    for c in chains:
        p = resample(np.asarray(c["pts"], float) + 0.5, 1.0)
        if len(p) < 4:
            continue
        closed = (
            len(p) >= max(12, int(2.6 * c["w"]))
            and np.linalg.norm(p[0] - p[-1]) < 0.6 * c["w"]
            and np.linalg.norm(p - p[0], axis=1).max() >= 0.75 * c["w"]
        )
        if closed:
            p[-1] = p[0]
        segs = []
        for kind, q in solver.pieces(p, c["w"]):
            if len(q) < 2:
                continue
            if kind == "curve":
                segs += fit_curve(q, sigma, err)
            else:
                segs.append(np.array([q[0], q[0] + (q[-1] - q[0]) / 3, q[0] + 2 * (q[-1] - q[0]) / 3, q[-1]]))
        if not segs:
            continue
        paths.append(Path.from_segs(segs, c["w"] + dw, closed=closed))
    H, W = D.shape
    return Model(paths, W, H)


def add_dots(model: Model, D, min_frac=0.25):
    """Compact ink blobs left uncovered by the traced strokes (dots, i-dots, solid circular disks) become clean dots or solid circles."""
    import cv2 as _cv2
    from .render import render_gray
    from . import edit as _E
    ws = [p.w for p in model.paths] or [8.0]
    w0 = float(np.median(ws))
    src_mask = (D > 0.5).astype(np.uint8)
    n_src, src_lab, src_st, src_ce = _cv2.connectedComponentsWithStats(src_mask)
    added = 0

    # 1. Detect standalone solid filled black circles up to 5.5 * w0 diameter
    #    (e.g., solid WiFi dots or solid circular inner disks that skeletonization Either skipped or distorted into a stub)
    for sl in range(1, n_src):
        sx, sy, sbw, sbh, sa = src_st[sl]
        if sa < min_frac * np.pi * (w0 / 2) ** 2 or max(sbw, sbh) > 5.5 * w0:
            continue
        if min(sbw, sbh) < 0.72 * max(sbw, sbh):
            continue
        ell_area = np.pi * (sbw / 2.0) * (sbh / 2.0)
        if not (0.72 * ell_area <= sa <= 1.22 * ell_area):
            continue
        comp_mask = (src_lab[sy:sy + sbh, sx:sx + sbw] == sl).astype(np.uint8)
        cnts, hier = _cv2.findContours(comp_mask, _cv2.RETR_CCOMP, _cv2.CHAIN_APPROX_NONE)
        if not cnts or (hier is not None and any(h[3] != -1 for h in hier[0])):
            continue  # Has an internal hole -> hollow ring, not a solid disk
        pts_c = cnts[0].reshape(-1, 2).astype(float) + np.array([sx + 0.5, sy + 0.5])
        cx_s, cy_s = float(src_ce[sl][0]) + 0.5, float(src_ce[sl][1]) + 0.5
        r_s = float(np.sqrt(sa / np.pi))
        if r_s >= 0.75 * w0:
            rad_d = np.abs(np.hypot(pts_c[:, 0] - cx_s, pts_c[:, 1] - cy_s) - r_s)
            if float(np.percentile(rad_d, 90)) > max(1.15, 0.14 * r_s):
                continue
        # Check if existing paths inside this isolated component are missing or just a distorted stub
        inside_idxs = []
        for idx_p, p in enumerate(model.paths):
            fp = p.flat(1.0)
            if ((fp[:, 0] >= sx - 2) & (fp[:, 0] <= sx + sbw + 2) & (fp[:, 1] >= sy - 2) & (fp[:, 1] <= sy + sbh + 2)).mean() > 0.85:
                inside_idxs.append(idx_p)
        # Only replace if no paths exist yet, or existing path doesn't cover the disk well
        if inside_idxs:
            if r_s <= 1.25 * w0:
                continue
            g_tmp = render_gray(model.svg(), model.width, model.height)
            cov_frac = float(((g_tmp[sy:sy + sbh, sx:sx + sbw] < 128) & (comp_mask > 0)).sum()) / max(1.0, float(sa))
            if cov_frac >= 0.92 and len(inside_idxs) == 1:
                continue
            for idx_p in sorted(inside_idxs, reverse=True):
                model.paths.pop(idx_p)
        c = np.array([cx_s, cy_s])
        diam = float(2.0 * r_s)
        if diam > 1.35 * w0:
            A_c, Hi_c, Ho_c = _E.ellipse_beziers(c, diam / 4.0, diam / 4.0, 0.0)
            model.paths.append(Path(A_c, Hi_c, Ho_c, max(diam / 2.0, 2.0), closed=True))
        else:
            A = np.array([c, c + [0.05, 0.0]])
            model.paths.append(Path(A, A.copy(), A.copy(), max(diam, 2.0)))
        added += 1

    # 2. Standard residual uncovered compact dot pass
    g = render_gray(model.svg(), model.width, model.height) if model.paths else np.full(D.shape, 255, np.uint8)
    covered_raw = (g < 128).astype(np.uint8)
    covered = _cv2.dilate(covered_raw, np.ones((3, 3), np.uint8))
    resid = src_mask & (1 - covered)
    n, lab, st, ce = _cv2.connectedComponentsWithStats(resid)
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a < min_frac * np.pi * (w0 / 2) ** 2 or max(bw, bh) > 2.6 * w0 or a < 0.5 * bw * bh:
            continue
        # Never add a fake dot on an uncovered corner tip of a large connected stroke component
        cy_i, cx_i = int(round(ce[i][1])), int(round(ce[i][0]))
        if 0 <= cy_i < src_lab.shape[0] and 0 <= cx_i < src_lab.shape[1]:
            sl = src_lab[cy_i, cx_i]
            if sl > 0 and src_st[sl, _cv2.CC_STAT_AREA] > 5.5 * w0 * w0:
                continue
        c = ce[i] + 0.5
        diam = float(2 * np.sqrt(a / np.pi))
        if diam > 1.35 * w0:
            A_c, Hi_c, Ho_c = _E.ellipse_beziers(c, diam / 4.0, diam / 4.0, 0.0)
            model.paths.append(Path(A_c, Hi_c, Ho_c, max(diam / 2.0, 2.0), closed=True))
        else:
            A = np.array([c, c + [0.05, 0.0]])
            model.paths.append(Path(A, A.copy(), A.copy(), max(diam, 2.0)))
        added += 1
    return added
