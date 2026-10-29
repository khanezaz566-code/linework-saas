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
                for s in (0, 2, 4, 6, 8, 10, 12):
                    Cs.append(p[i] + u * s)
            cands = [(base, False), (base, True)]
            meta = [None, None]
            for C in Cs:
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
        closed = np.linalg.norm(p[0] - p[-1]) < 0.6 * c["w"]
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
    """Compact ink blobs left uncovered by the traced strokes (dots, i-dots, noses) become zero-length round-capped strokes."""
    import cv2 as _cv2
    from .render import render_gray
    g = render_gray(model.svg(), model.width, model.height) if model.paths else np.full(D.shape, 255, np.uint8)
    covered = (g < 128).astype(np.uint8)
    covered = _cv2.dilate(covered, np.ones((3, 3), np.uint8))
    resid = ((D > 0.5).astype(np.uint8)) & (1 - covered)
    n, lab, st, ce = _cv2.connectedComponentsWithStats(resid)
    ws = [p.w for p in model.paths] or [8.0]
    w0 = float(np.median(ws))
    added = 0
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a < min_frac * np.pi * (w0 / 2) ** 2 or max(bw, bh) > 1.8 * w0 or a < 0.5 * bw * bh:
            continue
        c = ce[i] + 0.5
        diam = float(2 * np.sqrt(a / np.pi))
        A = np.array([c, c + [0.05, 0.0]])
        model.paths.append(Path(A, A.copy(), A.copy(), max(diam, 2.0)))
        added += 1
    return added
