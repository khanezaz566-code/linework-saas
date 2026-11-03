"""Exact circles. Mechanical / icon art is full of rings (hubs, bearings, pins). A skeleton trace breaks a ring wherever
another stroke touches it, and the pieces drift out of round.  Here the rings are found in the *image* (Hough on the
skeleton, then least-squares refinement, then an ink-support test), added as exact closed circles, and the old pieces
that lie on top of them are cut away so every stroke simply ends on the ring.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from skimage.transform import hough_circle, hough_circle_peaks
from .geom import resample
from .model import Model, Path
from . import edit as E


def _kasa(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x * x + y * y
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    r2 = c[2] + c[0] ** 2 + c[1] ** 2
    return float(c[0]), float(c[1]), float(np.sqrt(max(r2, 1e-6)))


def _profile_width(D, cx, cy, r, w, n=72):
    offs = np.arange(-2.5 * w, 2.5 * w + 1e-6, 0.25)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r + offs[None, :]
    xs, ys = cx + rr * np.cos(ang)[:, None], cy + rr * np.sin(ang)[:, None]
    v = ndi.map_coordinates(D, [ys, xs], order=1, mode="constant", cval=0.0)
    mid = len(offs) // 2
    widths, support = [], 0
    for row in v:
        if row[mid] < 0.5:
            continue
        support += 1
        a = b = mid
        while a > 0 and row[a - 1] >= 0.5:
            a -= 1
        while b < len(row) - 1 and row[b + 1] >= 0.5:
            b += 1
        widths.append((b - a + 1) * 0.25)
    if not widths:
        return None, 0.0
    return float(np.median(widths)), support / n


def _fit_ellipse_pts(P, cx, cy, r, w):
    """Least-squares ellipse (cv2.fitEllipse) on skeleton points near the circle; returns (cx, cy, a, b, theta) or None."""
    import cv2
    d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    tol = max(2.0, 0.25 * w, 0.03 * r)
    sel = np.abs(d - r) < tol
    if sel.sum() < 12:
        return None
    pts = P[sel]
    e = None
    for _ in range(3):
        if len(pts) < 8:
            return None
        (ex, ey), (MA, ma), ang = cv2.fitEllipse(pts.astype(np.float32))
        a, b, th = MA / 2, ma / 2, np.radians(ang)
        if min(a, b) < 2:
            return None
        e = (ex, ey, a, b, th)
        A, Hi, Ho = E.ellipse_beziers(np.array([ex, ey]), a, b, th)
        flat = Path(A, Hi, Ho, 1.0, closed=True).flat(0.5)
        from scipy.spatial import cKDTree
        dd = cKDTree(flat).query(P)[0]
        pts = P[dd < tol]
    return e


def detect_rings(D, w, min_support=0.93, max_rings=80):
    """Circles and ellipses found in the image. Returns dicts in SVG coordinates (pixel-edge convention)."""
    mask = D > 0.5
    if mask.sum() < 30:
        return []
    sk = skeletonize(mask)
    skd = ndi.binary_dilation(sk, iterations=1)  # tolerate the skeleton wobbling near junctions
    dt = ndi.distance_transform_edt(mask)
    H, W = D.shape
    rmax = int(min(H, W) / 2)
    rmin = 3
    cand = []
    hs = 2 if rmax > 40 else 1  # coarse grid for big icons: Hough cost grows with (pixels x radii)
    if hs > 1:
        import cv2
        skh = cv2.resize(skd.astype(np.uint8), (W // hs, H // hs), interpolation=cv2.INTER_AREA) > 0
    else:
        skh = skd
    rh = int(min(skh.shape) / 2)
    radii_all = np.arange(max(2, rmin // hs), max(rh, 3))
    radii_all = radii_all[:: (1 if rh <= 60 else 2)]
    for i in range(0, len(radii_all), 6):
        radii = radii_all[i:i + 6]
        acc = hough_circle(skh, radii, normalize=True)
        a, xs, ys, rs = hough_circle_peaks(acc, radii, min_xdistance=2, min_ydistance=2, threshold=0.3, total_num_peaks=40)
        cand += [(aa, xx * hs, yy * hs, rr * hs) for aa, xx, yy, rr in zip(a, xs, ys, rs)]
    cand.sort(key=lambda t: -t[0])
    ys_, xs_ = np.nonzero(sk)
    P = np.c_[xs_, ys_].astype(float)
    out = []
    for a, cx, cy, r in cand:
        cx, cy, r = float(cx), float(cy), float(r)
        for _ in range(3):  # least-squares circle refinement on skeleton points close to the circle
            d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
            sel = np.abs(d - r) < max(2.0, 0.25 * w)
            if sel.sum() < 12:
                break
            cx, cy, r = _kasa(P[sel])
        if r < rmin or r > rmax * 1.1:
            continue
        e = _fit_ellipse_pts(P, cx, cy, r, w)
        if e is None:
            continue
        ex, ey, ea, eb, th = e
        if max(ea, eb) > rmax * 1.2 or max(ea, eb) / max(min(ea, eb), 1e-6) > 1.6:
            continue
        rr = (ea + eb) / 2
        pts_chk = P[np.abs(np.hypot(P[:, 0] - ex, P[:, 1] - ey) - rr) < max(2.5, 0.35 * w)]
        if len(pts_chk) >= 12:
            rx0, rx1 = np.percentile(pts_chk[:, 0], [3, 97])
            ry0, ry1 = np.percentile(pts_chk[:, 1], [3, 97])
            d_rect = np.minimum(
                np.minimum(np.abs(pts_chk[:, 0] - rx0), np.abs(pts_chk[:, 0] - rx1)),
                np.minimum(np.abs(pts_chk[:, 1] - ry0), np.abs(pts_chk[:, 1] - ry1)),
            )
            d_circ = np.abs(np.hypot(pts_chk[:, 0] - ex, pts_chk[:, 1] - ey) - rr)
            if float(d_rect.mean()) <= float(d_circ.mean()) * 1.08:
                continue
        # support + width measured along the fitted centreline
        A, Hi, Ho = E.ellipse_beziers(np.array([ex, ey]), ea, eb, th)
        flat = Path(A, Hi, Ho, 1.0, closed=True).flat(1.0)
        xi = np.clip(np.round(flat[:, 0]).astype(int), 0, W - 1)
        yi = np.clip(np.round(flat[:, 1]).astype(int), 0, H - 1)
        sup = float((D[yi, xi] > 0.5).mean())
        if sup < min_support:
            continue
        ww = float(2 * np.median(dt[yi, xi]))
        if not (0.45 * w <= ww <= 1.8 * w):
            continue
        rr = (ea + eb) / 2
        if any(np.hypot(ex - o["cx"] + 0.5, ey - o["cy"] + 0.5) < 3.0 and abs(rr - o["r"]) < 0.7 * w for o in out):
            continue
        if abs(ea - eb) / max(ea, eb) < 0.015:  # a true circle: keep it exactly round
            ea = eb = rr
        out.append(dict(cx=ex + 0.5, cy=ey + 0.5, a=ea, b=eb, th=th, r=rr, w=ww, support=sup))
        if len(out) >= max_rings:
            break
    return out


def _ring_path(ring):
    A, Hi, Ho = E.ellipse_beziers(np.array([ring["cx"], ring["cy"]]), ring["a"], ring["b"], ring["th"])
    return Path(A, Hi, Ho, ring["w"], closed=True)


def apply_ring(model: Model, ring, clear=0.9):
    """Add the exact ring and cut every older stroke back to its centerline, snapping spoke ends onto the ring."""
    from scipy.spatial import cKDTree
    from . import joints as JN
    rp = _ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]
    cx, cy = ring["cx"], ring["cy"]

    # Refine ring width and center/radius from tangential model segments that lie on this ring
    on_ring_pts = []
    on_ring_ws = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            continue
        d = tree.query(f)[0]
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))
        w_m = max(w, p.w)
        sel = (d < 0.65 * w_m) & (rad_dot < 0.45)
        if sel.sum() >= 6:
            on_ring_pts.append(f[sel])
            on_ring_ws.append((p.w, float(sel.sum())))
    if on_ring_ws:
        w_new = float(sum(pw * lw for pw, lw in on_ring_ws) / sum(lw for _, lw in on_ring_ws))
        ring = dict(ring, w=w_new)
    if on_ring_pts:
        pts_all = np.vstack(on_ring_pts)
        if len(pts_all) >= 16 and abs(ring["a"] - ring["b"]) / max(ring["a"], ring["b"], 1e-6) < 0.02:
            cx_k, cy_k, r_k = _kasa(pts_all)
            if abs(r_k - ring["r"]) < 0.35 * w and np.hypot(cx_k - cx, cy_k - cy) < 0.35 * w:
                ring = dict(ring, cx=cx_k, cy=cy_k, a=r_k, b=r_k, r=r_k)
                cx, cy = cx_k, cy_k

    rp = _ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]

    paths = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            paths.append(p)
            continue
        d, idx = tree.query(f)
        w_m = max(w, p.w)
        if not (d < 0.75 * w_m).any():
            paths.append(p)
            continue
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))

        bad = (d < 0.35 * w_m) | ((d < 0.75 * w_m) & (rad_dot < 0.48))
        if not bad.any():
            paths.append(p)
            continue
        if bad.mean() >= 0.82:
            continue
        n_f = len(f)
        lim = max(3, int(round(0.85 * w_m)))
        if not p.closed and not bad[min(lim, n_f):max(min(lim, n_f), n_f - lim)].any():
            q = p.copy()
            if bad[:min(lim, n_f)].any() or d[0] <= 0.65 * w_m:
                JN._set_end(q, 0, rp_flat[int(idx[0])])
            if bad[max(0, n_f - lim):].any() or d[-1] <= 0.65 * w_m:
                JN._set_end(q, 1, rp_flat[int(idx[-1])])
            paths.append(q)
            continue
        if p.closed:
            k = int(np.argmax(bad))
            f, d, bad = np.roll(f, -k, axis=0), np.roll(d, -k), np.roll(bad, -k)
        j = 0
        while j < len(f):
            if bad[j]:
                j += 1
                continue
            k = j
            while k < len(f) and not bad[k]:
                k += 1
            seg = f[j:k]
            if len(seg) >= 4 and (float(d[j:k].max()) >= 0.80 * w_m or (j == 0 and k == len(f))):
                if j > 0:
                    v0 = seg[0] - seg[min(len(seg) - 1, 4)]
                    n0 = float(np.linalg.norm(v0))
                    pt0 = seg[0] + (v0 / n0) * float(d[j]) if n0 > 1e-6 else seg[0]
                    snap0 = rp_flat[int(tree.query(pt0)[1])]
                    seg = np.vstack([[snap0], seg])
                if k < len(f):
                    v1 = seg[-1] - seg[max(0, len(seg) - 5)]
                    n1 = float(np.linalg.norm(v1))
                    pt1 = seg[-1] + (v1 / n1) * float(d[k - 1]) if n1 > 1e-6 else seg[-1]
                    snap1 = rp_flat[int(tree.query(pt1)[1])]
                    seg = np.vstack([seg, [snap1]])
                q = E._refit(seg, p)
                if q:
                    if j > 0:
                        JN._set_end(q, 0, seg[0])
                    if k < len(f):
                        JN._set_end(q, 1, seg[-1])
                    paths.append(q)
            j = k
    paths.append(rp)
    return Model(paths, model.width, model.height)
