"""Curve geometry helpers: Bezier evaluation, Schneider curve fitting, resampling, corner detection."""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d


def bez(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return mt**3 * c[0] + 3 * mt**2 * t * c[1] + 3 * mt * t**2 * c[2] + t**3 * c[3]


def _d1(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return 3 * mt**2 * (c[1] - c[0]) + 6 * mt * t * (c[2] - c[1]) + 3 * t**2 * (c[3] - c[2])


def _d2(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return 6 * mt * (c[2] - 2 * c[1] + c[0]) + 6 * t * (c[3] - 2 * c[2] + c[1])


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v * 0


def arclen(p):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]


def resample(p, step=1.0):
    p = np.asarray(p, float)
    d = arclen(p)
    if d[-1] < 1e-9:
        return p[:2] if len(p) >= 2 else np.vstack([p, p])
    n = max(2, int(d[-1] / step) + 1)
    s = np.linspace(0, d[-1], n)
    return np.c_[np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]


# ---------------------------------------------------------------- Schneider fit
def _chord(p):
    d = arclen(p)
    return d / d[-1] if d[-1] > 0 else d


def _gen(p, u, t1, t2):
    A1 = (3 * (1 - u) ** 2 * u)[:, None] * t1
    A2 = (3 * (1 - u) * u**2)[:, None] * t2
    C = np.array([[np.sum(A1 * A1), np.sum(A1 * A2)], [np.sum(A1 * A2), np.sum(A2 * A2)]])
    b0, b3 = p[0], p[-1]
    tmp = p - (((1 - u) ** 3 + 3 * (1 - u) ** 2 * u)[:, None] * b0 + ((3 * (1 - u) * u**2) + u**3)[:, None] * b3)
    X = np.array([np.sum(A1 * tmp), np.sum(A2 * tmp)])
    det = C[0, 0] * C[1, 1] - C[0, 1] ** 2
    seg = np.linalg.norm(b3 - b0)
    if abs(det) > 1e-12:
        a1 = (X[0] * C[1, 1] - X[1] * C[0, 1]) / det
        a2 = (C[0, 0] * X[1] - C[0, 1] * X[0]) / det
    else:
        a1 = a2 = 0
    if a1 < 1e-6 * seg or a2 < 1e-6 * seg:
        a1 = a2 = seg / 3
    return np.array([b0, b0 + t1 * a1, b3 + t2 * a2, b3])


def _reparam(c, p, u):
    for _ in range(3):
        d = bez(c, u) - p
        d1 = _d1(c, u)
        d2 = _d2(c, u)
        num = np.sum(d * d1, 1)
        den = np.sum(d1 * d1, 1) + np.sum(d * d2, 1)
        den = np.where(abs(den) < 1e-12, 1e-12, den)
        u = np.clip(u - num / den, 0, 1)
    return u


def _fitcubic(p, t1, t2, err, depth=0):
    if len(p) == 2:
        d = np.linalg.norm(p[1] - p[0]) / 3
        return [np.array([p[0], p[0] + t1 * d, p[1] + t2 * d, p[1]])]
    u = _chord(p)
    c = _gen(p, u, t1, t2)
    i = 0
    for it in range(6):
        e = np.sum((bez(c, u) - p) ** 2, 1)
        i = int(np.argmax(e))
        if e[i] < err**2:
            return [c]
        if it == 5:
            break
        u = _reparam(c, p, u)
        c = _gen(p, u, t1, t2)
    i = max(1, min(len(p) - 2, i))
    tc = unit(p[i - 1] - p[i + 1])
    if depth > 40:
        return [c]
    return _fitcubic(p[: i + 1], t1, tc, err, depth + 1) + _fitcubic(p[i:], -tc, t2, err, depth + 1)


def fitpath(p, err=0.3):
    """Fit a chain of cubic Beziers (list of 4x2 arrays) to polyline p."""
    p = np.asarray(p, float)
    if len(p) < 2:
        return []
    k = min(6, len(p) - 1)
    t1 = unit(p[min(k, len(p) - 1)] - p[0])
    t2 = unit(p[max(-k - 1, -len(p))] - p[-1])
    return _fitcubic(p, t1, t2, err)


def smooth(q, sigma):
    """Gaussian-smooth a polyline while pinning both endpoints."""
    if len(q) <= 8 or sigma <= 0:
        return q
    m = min(int(3 * sigma) + 1, len(q) - 1)
    ext = np.vstack([2 * q[0] - q[1 : m + 1][::-1], q, 2 * q[-1] - q[-m - 1 : -1][::-1]])
    sm = gaussian_filter1d(ext, sigma, axis=0, mode="nearest")[m : m + len(q)]
    sm[0] = q[0]
    sm[-1] = q[-1]
    return sm


def corners(p, win=7, ang=40):
    """Indices of local turning-angle maxima above `ang` degrees (window +-win samples)."""
    n = len(p)
    th = np.zeros(n)
    for i in range(win, n - win):
        a = p[i] - p[i - win]
        b = p[i + win] - p[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-6 or nb < 1e-6:
            continue
        th[i] = np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1)))
    res = []
    for i in range(win, n - win):
        if th[i] > ang and th[i] >= th[max(0, i - win) : i + win + 1].max():
            if not res or i - res[-1] > win:
                res.append(i)
    return res


def fit_curve(q, sigma=1.5, err=0.3):
    """Smooth + fit, splitting at sharp corners so they stay sharp."""
    cs = corners(q, 7, 35) if len(q) > 16 else []
    cuts = [0] + cs + [len(q) - 1]
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 1:
            continue
        out += fitpath(smooth(q[a : b + 1], sigma), err)
    return out


def linefit(q):
    c = q.mean(0)
    _, _, vt = np.linalg.svd(q - c)
    d = vt[0]
    res = np.abs((q - c) @ np.array([-d[1], d[0]])).max()
    return c, d, res


def line_inter(c1, d1, c2, d2):
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-6:
        return None
    t = np.linalg.solve(A, c2 - c1)
    return c1 + d1 * t[0]


def hermite(A1, d1, A2, d2):
    L = np.linalg.norm(A2 - A1)
    n = max(2, int(L) + 1)
    c = np.array([A1, A1 + d1 * L / 3, A2 + d2 * L / 3, A2])
    return bez(c, np.linspace(0, 1, n))
