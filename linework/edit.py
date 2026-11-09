"""Edit engine: executes commands issued by the Doctor on a Model and returns a *new* Model.

Commands (dicts):
  remove_path   {path}                      drop a redundant path
  cut           {path, a, b}                drop samples a..b of a path (1px resampled) and refit the rest
  smooth_anchor {path, anchor}              make a near-smooth joint truly G1
  circle        {path}                      replace a ring by an exact ellipse
  simplify      {path, err}                 refit with fewer nodes (keeps sharp corners)
  line_snap     {path}                      straighten segments that are straight within tolerance
  refine_all    {}                          gradient optimiser over every path (control points + widths)
  refine_region {box}                       gradient optimiser restricted to the paths/pixels around a box
  weld          {}                          close junction gaps (corner intersection / T snap)
  merge_nodes   {path}                      collapse micro-segment staircases at corners
  trim_tail     {path, end}                 drop a short curled spur at a stroke end
  join          {path, join}                switch a path between round and miter joins
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.spatial import cKDTree
from .geom import resample, unit, fit_curve, corners, bez, arclen
from .model import Model, Path
from . import opt
from . import topology as T


# ------------------------------------------------------------------ simple structural commands
def remove_path(m: Model, i):
    m = m.copy()
    del m.paths[i]
    return m


def _refit(poly, base: Path, sigma=1.2, err=0.3):
    segs = fit_curve(poly, sigma, err)
    if not segs:
        return None
    p = Path.from_segs(segs, base.w, closed=False, join=base.join)
    p.ml = base.ml
    return p


def cut(m: Model, i, a, b):
    """Remove flat samples [a,b] of path i (1px resampled); keep the pieces that are long enough."""
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 1.0)
    a, b = max(0, int(a)), min(len(f) - 1, int(b))
    pieces = []
    if p.closed:
        g = np.vstack([f[b:], f[: a + 1]]) if a > b else np.vstack([f[b:-1], f[: a + 1]])
        pieces = [g]
    else:
        if a > 2:
            pieces.append(f[: a + 1])
        if len(f) - 1 - b > 2:
            pieces.append(f[b:])
    new = []
    for q in pieces:
        if len(q) >= 4:
            r = _refit(q, p)
            if r:
                new.append(r)
    m.paths[i : i + 1] = new
    return m


def smooth_anchor(m: Model, i, k):
    m = m.copy()
    p = m.paths[i]
    a = p.A[k]
    din, dout = a - p.Hin[k], p.Hout[k] - a
    ln, lo = np.linalg.norm(din), np.linalg.norm(dout)
    if ln < 1e-6 or lo < 1e-6:
        return m
    u = unit(unit(din) + unit(dout))
    p.Hin[k] = a - u * ln
    p.Hout[k] = a + u * lo
    if p.closed and k == 0:
        p.Hin[-1] = p.Hin[0]
        p.Hout[-1] = p.Hout[0]
    return m


def simplify(m: Model, i, err=0.45):
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 0.75)
    segs = fit_curve(f, 0.8, err)
    if not segs or len(segs) >= len(p.segs()):
        return m
    q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
    q.ml = p.ml
    m.paths[i] = q
    return m


def line_snap(m: Model, i, tol=None):
    m = m.copy()
    p = m.paths[i]
    tol = max(0.35, 0.05 * p.w) if tol is None else tol
    for k, c in enumerate(p.segs()):
        ch = c[3] - c[0]
        L = np.linalg.norm(ch)
        if L < 6:
            continue
        n = np.array([-ch[1], ch[0]]) / L
        dev = max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n))
        if dev * 0.75 < tol:  # Bezier max deviation ~ 3/4 of control offset
            p.Hout[k] = c[0] + ch / 3
            p.Hin[k + 1] = c[0] + 2 * ch / 3
    return m


def ellipse_beziers(c, a, b, theta):
    k = 0.5522847498
    ct, st = np.cos(theta), np.sin(theta)
    R = np.array([[ct, -st], [st, ct]])
    base = [(a, 0), (0, b), (-a, 0), (0, -b)]
    tan = [(0, k * b), (-k * a, 0), (0, -k * b), (k * a, 0)]
    A = [c + R @ np.array(p) for p in base] + [c + R @ np.array(base[0])]
    Ho = [A[i] + R @ np.array(tan[i]) for i in range(4)] + [A[4]]
    Hi = [A[0]] + [A[i + 1] - R @ np.array(tan[(i + 1) % 4]) for i in range(4)]
    return np.array(A), np.array(Hi), np.array(Ho)


def fit_ellipse(flat):
    if len(flat) < 8:
        return None
    (cx, cy), (MA, ma), ang = cv2.fitEllipse(flat.astype(np.float32))
    a, b, th = MA / 2, ma / 2, np.radians(ang)
    A, Hi, Ho = ellipse_beziers(np.array([cx, cy]), a, b, th)
    ell = Path(A, Hi, Ho, 1.0, closed=True)
    dev = cKDTree(ell.flat(0.5)).query(flat)[0]
    return ell, float(dev.max()), float(dev.mean())


def robust_ellipse(flat, w, inlier_frac=0.7, iters=5):
    """Ellipse fitted only to the points that agree with it (a ring touched by another stroke gets pulled out of shape by
    the touching part; the rest of the ring still defines the true circle). Returns (Path, inlier_fraction, max_inlier_dev)."""
    if len(flat) < 12:
        return None
    pts = flat
    thr = max(1.5, 0.25 * w)
    for _ in range(iters):
        if len(pts) < 8:
            return None
        (cx, cy), (MA, ma), ang = cv2.fitEllipse(pts.astype(np.float32))
        if min(MA, ma) < 2:
            return None
        A, Hi, Ho = ellipse_beziers(np.array([cx, cy]), MA / 2, ma / 2, np.radians(ang))
        ell = Path(A, Hi, Ho, 1.0, closed=True)
        tree = cKDTree(ell.flat(0.5))
        d = tree.query(flat)[0]
        keep = flat[d < thr]
        if len(keep) == len(pts):
            break
        pts = keep
    frac = float((d < thr).mean())
    return (ell, frac, float(d[d < thr].max())) if frac >= inlier_frac else None


def circle(m: Model, i, max_dev=0.9, robust=False):
    m = m.copy()
    p = m.paths[i]
    f05 = p.flat(0.5)
    if len(f05) >= 8:
        x0, x1 = np.percentile(f05[:, 0], [2, 98])
        y0, y1 = np.percentile(f05[:, 1], [2, 98])
        bw_r, bh_r = float(x1 - x0), float(y1 - y0)
        d_rect = np.minimum(
            np.minimum(np.abs(f05[:, 0] - x0), np.abs(f05[:, 0] - x1)),
            np.minimum(np.abs(f05[:, 1] - y0), np.abs(f05[:, 1] - y1)),
        )
        cx_e, cy_e = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        r_e = 0.25 * (bw_r + bh_r)
        d_ell = np.abs(np.hypot(f05[:, 0] - cx_e, f05[:, 1] - cy_e) - r_e)
        # Never turn an axis-aligned square/rectangle into a circle!
        if float(d_rect.mean()) <= float(d_ell.mean()) * 1.12:
            return m
        if float(np.percentile(d_rect, 85)) <= max(1.25, 0.13 * p.w) and max(bw_r, bh_r) <= 3.6 * p.w:
            return m
    else:
        bw_r, bh_r = 0.0, 0.0
    r = fit_ellipse(p.flat())
    # Only allow robust_ellipse fallback on rings (>= 2.4 * w), never on small buttons/squares
    if robust and max(bw_r, bh_r) >= 2.4 * p.w and (r is None or r[1] > max_dev):
        rr = robust_ellipse(p.flat(), p.w)
        r = (rr[0], rr[2]) if rr else None
        lim = max(max_dev, 1.5, 0.25 * p.w)
    else:
        lim = max_dev
    if r is None or r[1] > lim:
        return m
    ell = r[0]
    ell.w, ell.join = p.w, p.join
    m.paths[i] = ell
    return m


# ------------------------------------------------------------------ gradient optimiser (see opt.py)
def _is_exact_ring(p: Path) -> bool:
    if not p.closed:
        return False
    if len(p.A) in (4, 5):
        return bool(np.linalg.norm((p.A[0] + p.A[2]) - (p.A[1] + p.A[3])) < 0.75)
    return False


def refine_all(m: Model, D, **kw):
    if kw.get("free") is None:
        non_rings = [i for i, p in enumerate(m.paths) if not _is_exact_ring(p)]
        if 0 < len(non_rings) < len(m.paths):
            kw = dict(kw, free=non_rings)
    return opt.refine(m, D, **kw)


def refine_region(m: Model, D, box, margin=12, **kw):
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    free = []
    for i, p in enumerate(m.paths):
        if _is_exact_ring(p):
            continue
        f = p.flat(2.0)
        if (f[:, 0] > x0 - p.w).any() and (f[:, 0] < x1 + p.w).any():
            inside = (f[:, 0] > x0 - p.w) & (f[:, 0] < x1 + p.w) & (f[:, 1] > y0 - p.w) & (f[:, 1] < y1 + p.w)
            if inside.any():
                free.append(i)
    if not free:
        return m
    kw.setdefault("taus", (0.6, 0.38, 0.3))
    kw.setdefault("iters", 40)
    return opt.refine(m, D, free=free, window=(x0, y0, x1, y1), **kw)


def set_join(m: Model, i, join, ml=4.0):
    m = m.copy()
    m.paths[i].join = join
    m.paths[i].ml = ml
    return m


# ------------------------------------------------------------------ dispatcher
def execute(m: Model, cmd: dict, D=None):
    """Run one command. Returns (new_model, info)."""
    op = cmd["op"]
    if op == "remove_path":
        return remove_path(m, cmd["path"]), None
    if op == "cut":
        return cut(m, cmd["path"], cmd["a"], cmd["b"]), None
    if op == "smooth_anchor":
        return smooth_anchor(m, cmd["path"], cmd["anchor"]), None
    if op == "circle":
        return circle(m, cmd["path"], robust=cmd.get("robust", False)), None
    if op == "simplify":
        return simplify(m, cmd["path"], cmd.get("err", 0.45)), None
    if op == "line_snap":
        return line_snap(m, cmd["path"]), None
    if op == "refine_all":
        return refine_all(m, D, **cmd.get("kw", {})), None
    if op == "refine_region":
        return refine_region(m, D, cmd["box"], **cmd.get("kw", {})), None
    if op == "weld":
        return T.weld_all(m), None
    if op == "merge_nodes":
        return T.merge_nodes(m, cmd["path"]), None
    if op == "trim_tail":
        return T.trim_tail(m, cmd["path"], cmd["end"]), None
    if op == "join":
        from . import joinpolicy as JP
        return JP.choose_join(m, cmd["path"], D), None
    raise ValueError(op)
