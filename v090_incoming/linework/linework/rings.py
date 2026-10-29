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
    for i in range(0, len(radii_all), 24):
        radii = radii_all[i:i + 24]
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


def ring_arcs(ring, D, gap=0.8):
    """The parts of a (partly hidden) circle that the image really shows: open exact arcs, one per supported span.  A full ring if nothing is hidden."""
    c = np.array([ring["cx"] - 0.5, ring["cy"] - 0.5])
    r = float(ring["r"])
    w = ring["w"]
    n = max(90, int(2 * np.pi * r / 0.7))
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xs = np.clip(np.round(c[0] + r * np.cos(th)).astype(int), 0, D.shape[1] - 1)
    ys = np.clip(np.round(c[1] + r * np.sin(th)).astype(int), 0, D.shape[0] - 1)
    ok = D[ys, xs] > 0.5
    # a hidden stretch is a run of unsupported samples at least gap * w long (arc length)
    run_min = max(2, int(gap * w / (2 * np.pi * r / n)))
    if ok.all():
        return None
    k0 = int(np.argmin(ok))  # start at an unsupported sample so no span wraps
    ok = np.roll(ok, -k0)
    th = np.roll(th, -k0)
    # fill short unsupported runs
    i = 0
    while i < n:
        if not ok[i]:
            j = i
            while j < n and not ok[j]:
                j += 1
            if j - i < run_min and i > 0 and j < n:
                ok[i:j] = True
            i = j
        else:
            i += 1
    arcs = []
    i = 0
    while i < n:
        if ok[i]:
            j = i
            while j < n and ok[j]:
                j += 1
            if (j - i) * (2 * np.pi * r / n) >= 1.5 * w:
                arcs.append((th[i], th[i] + (j - i) * (2 * np.pi / n)))
            i = j
        else:
            i += 1
    out = []
    for t0, t3 in arcs:
        nseg = int(np.ceil((t3 - t0) / (np.pi / 2) - 1e-9))
        step = (t3 - t0) / nseg
        segs = []
        for k in range(nseg):
            a0, a1 = t0 + k * step, t0 + (k + 1) * step
            P0 = c + r * np.array([np.cos(a0), np.sin(a0)])
            P3 = c + r * np.array([np.cos(a1), np.sin(a1)])
            h = 4.0 / 3.0 * np.tan(step / 4.0) * r
            segs.append([P0, P0 + h * np.array([-np.sin(a0), np.cos(a0)]), P3 - h * np.array([-np.sin(a1), np.cos(a1)]), P3])
        out.append(Path.from_segs(segs, w, closed=False))
    return out


def apply_ring(model: Model, ring, clear=0.9, D=None):
    """Add the exact ring and cut every older stroke back to its edge.  With `D`, a ring that is partly hidden is added as the arcs that are visible."""
    from scipy.spatial import cKDTree
    rp = _ring_path(ring)
    extra = ring_arcs(ring, D) if D is not None else None
    if extra is not None and not extra:
        extra = None
    tree = cKDTree(rp.flat(0.5))
    w = ring["w"]
    paths = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        d = tree.query(f)[0]
        bad = d < clear * max(w, p.w) * 0.5 + 0.5 * w * 0.8
        if not bad.any():
            paths.append(p)
            continue
        if bad.all():
            continue
        if p.closed:
            k = int(np.argmax(bad))
            f, bad = np.roll(f, -k, axis=0), np.roll(bad, -k)
        j = 0
        while j < len(f):
            if bad[j]:
                j += 1
                continue
            k = j
            while k < len(f) and not bad[k]:
                k += 1
            seg = f[j:k]
            if len(seg) >= 4:
                q = E._refit(seg, p)
                if q:
                    paths.append(q)
            j = k
    paths.extend(extra if extra is not None else [rp])
    return Model(paths, model.width, model.height)


def snap_to_ring(model: Model, ring, frac=0.8, tol_w=0.7):
    """Gentle variant for rings that are partly hidden behind other strokes: nothing is cut.  Every stroke that lies (almost) entirely along the circle is
    redrawn as an exact arc of that circle; returns the new model, or None when no stroke qualifies."""
    c = np.array([ring["cx"] - 0.5, ring["cy"] - 0.5])
    r = float(ring["r"])
    w = ring["w"]
    paths, hit = [], 0
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 8:
            paths.append(p)
            continue
        d = np.abs(np.linalg.norm(f - c, axis=1) - r)
        if (d < tol_w * w).mean() < frac or p.length() < 2.5 * w:
            paths.append(p)
            continue
        ang = np.unwrap(np.arctan2(f[:, 1] - c[1], f[:, 0] - c[0]))
        span = float(ang[-1] - ang[0])
        if abs(span) < 0.5 or (np.sign(np.diff(ang)) == np.sign(span)).mean() < 0.95:
            paths.append(p)
            continue
        closed = p.closed or abs(span) > 6.1
        if closed:
            span = 2 * np.pi * np.sign(span)
        n = int(np.ceil(abs(span) / (np.pi / 2) - 1e-9))
        step = span / n
        segs = []
        for k in range(n):
            t0, t1 = ang[0] + k * step, ang[0] + (k + 1) * step
            P0 = c + r * np.array([np.cos(t0), np.sin(t0)])
            P3 = c + r * np.array([np.cos(t1), np.sin(t1)])
            h = 4.0 / 3.0 * np.tan(abs(step) / 4.0) * r * np.sign(span)
            segs.append([P0, P0 + h * np.array([-np.sin(t0), np.cos(t0)]), P3 - h * np.array([-np.sin(t1), np.cos(t1)]), P3])
        q = Path.from_segs(segs, p.w, closed=closed, join=p.join)
        q.ml = p.ml
        paths.append(q)
        hit += 1
    return Model(paths, model.width, model.height) if hit else None
