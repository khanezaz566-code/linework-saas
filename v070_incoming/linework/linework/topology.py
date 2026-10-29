"""Topology repair: junction gaps, micro-segment notches and corner spurs.

These are the defects a vector editor shows as two separate paths that nearly meet, a tiny staircase at a
corner, or a little curl at the end of a stroke.  Detectors feed the Doctor; the repair functions are Edit commands.
"""
from __future__ import annotations
import numpy as np
from .geom import unit
from .model import Model, Path


def _end(p: Path, e):
    """(point, outward unit tangent) of open end e (0 = start, 1 = end)."""
    if e == 0:
        a, h, nb = p.A[0], p.Hout[0], p.A[1]
        d = a - h
        if np.linalg.norm(d) < 1e-6:
            d = a - nb
    else:
        a, h, nb = p.A[-1], p.Hin[-1], p.A[-2]
        d = a - h
        if np.linalg.norm(d) < 1e-6:
            d = a - nb
    return a.copy(), unit(d)


def _move_end(p: Path, e, target):
    if e == 0:
        d = target - p.A[0]
        p.A[0] = target
        p.Hout[0] = p.Hout[0] + d
        p.Hin[0] = p.Hin[0] + d
    else:
        d = target - p.A[-1]
        p.A[-1] = target
        p.Hin[-1] = p.Hin[-1] + d
        p.Hout[-1] = p.Hout[-1] + d


def _ends(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        for e in (0, 1):
            pt, t = _end(p, e)
            out.append((i, e, pt, t))
    return out


def _plan(m: Model, r_end=1.0, r_t=0.7, min_gap=0.35):
    """Return list of (kind, i, e, j, e2_or_None, target, gap) weld actions without applying them."""
    ends = _ends(m)
    acts, used = [], set()
    pairs = []
    for a in range(len(ends)):
        for b in range(a + 1, len(ends)):
            i, e, p1, _ = ends[a]
            j, f, p2, _ = ends[b]
            d = float(np.linalg.norm(p1 - p2))
            w = max(m.paths[i].w, m.paths[j].w)
            if d <= r_end * w and (i != j):
                pairs.append((d, a, b))
    for d, a, b in sorted(pairs):
        if a in used or b in used:
            continue
        i, e, p1, t1 = ends[a]
        j, f, p2, t2 = ends[b]
        w = max(m.paths[i].w, m.paths[j].w)
        cr = t1[0] * t2[1] - t1[1] * t2[0]
        target = (p1 + p2) / 2
        if abs(cr) > 0.25:  # a real corner: meet at the intersection of the two stroke axes
            s = np.linalg.solve(np.array([[t1[0], -t2[0]], [t1[1], -t2[1]]]), p2 - p1)
            if -0.9 * w <= s[0] <= 1.2 * w and -0.9 * w <= s[1] <= 1.2 * w:
                target = p1 + s[0] * t1
        gap = float(np.linalg.norm(p1 - target) + np.linalg.norm(p2 - target))
        if gap > min_gap:
            acts.append(("corner", i, e, j, f, target, gap))
        used.update((a, b))
    # T-junctions: free ends that stop short of (or inside) another stroke
    polys = [p.flat(1.0) for p in m.paths]
    for a, (i, e, p1, t1) in enumerate(ends):
        if a in used:
            continue
        w = m.paths[i].w
        best = None
        for j, f in enumerate(polys):
            if j == i:
                continue
            dd = np.linalg.norm(f - p1, axis=1)
            k = int(dd.argmin())
            if dd[k] <= r_t * w and (best is None or dd[k] < best[0]):
                best = (float(dd[k]), j, f[k])
        if best and best[0] > min_gap:
            acts.append(("tee", i, e, best[1], None, best[2], best[0]))
    return acts


def find_gaps(m: Model, **kw):
    """Number of unwelded junctions (the Doctor flags these)."""
    return _plan(m, **kw)


def weld_all(m: Model, **kw):
    m = m.copy()
    for kind, i, e, j, f, target, gap in _plan(m, **kw):
        _move_end(m.paths[i], e, target)
        if f is not None:
            _move_end(m.paths[j], f, target)
    return m


def _turn(p: Path, k):
    """Signed turning angle (deg) at interior anchor k."""
    din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
    if np.linalg.norm(din) < 1e-6:
        din = p.A[k] - p.A[k - 1]
    if np.linalg.norm(dout) < 1e-6:
        dout = p.A[k + 1] - p.A[k]
    a, b = unit(din), unit(dout)
    return float(np.degrees(np.arctan2(a[0] * b[1] - a[1] * b[0], a @ b)))


def _is_step(p: Path, k, frac):
    """Tiny segment k->k+1 that is a corner chamfer or a zig-zag step rather than part of a smooth curve."""
    if np.linalg.norm(p.A[k + 1] - p.A[k]) >= frac * p.w:
        return False
    t1, t2 = _turn(p, k), _turn(p, k + 1)
    if t1 * t2 < 0:
        return min(abs(t1), abs(t2)) > 15.0
    return abs(t1) > 25.0 and abs(t2) > 25.0 and abs(t1 + t2) > 50.0


def merge_nodes(m: Model, i, frac=0.45):
    """Collapse chamfer/zig-zag steps at a corner into one clean anchor."""
    m = m.copy()
    p = m.paths[i]
    if p.closed:
        return m
    changed = True
    while changed and len(p.A) > 3:
        changed = False
        for k in range(1, len(p.A) - 2):
            if not _is_step(p, k, frac):
                continue
            M = (p.A[k] + p.A[k + 1]) / 2
            tin = unit(p.A[k] - p.Hin[k]) if np.linalg.norm(p.A[k] - p.Hin[k]) > 1e-6 else unit(p.A[k] - p.A[k - 1])
            tout = unit(p.Hout[k + 1] - p.A[k + 1]) if np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]) > 1e-6 else unit(p.A[k + 2] - p.A[k + 1])
            P = M
            cr = tin[0] * tout[1] - tin[1] * tout[0]
            if abs(cr) > 0.2:
                s = np.linalg.solve(np.array([[tin[0], -tout[0]], [tin[1], -tout[1]]]), p.A[k + 1] - p.A[k])
                cand = p.A[k] + s[0] * tin
                if np.linalg.norm(cand - M) < 0.8 * p.w:
                    P = cand
            lin = max(np.linalg.norm(p.A[k] - p.Hin[k]), 1.0)
            lout = max(np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]), 1.0)
            p.A = np.vstack([p.A[:k], P, p.A[k + 2:]])
            p.Hin = np.vstack([p.Hin[:k], P - tin * lin, p.Hin[k + 2:]])
            p.Hout = np.vstack([p.Hout[:k], P + tout * lout, p.Hout[k + 2:]])
            changed = True
            break
    return m


def find_notches(m: Model, frac=0.45):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 4:
            continue
        if any(_is_step(p, k, frac) for k in range(1, len(p.A) - 2)):
            out.append(i)
    return out


def _spur(p: Path, e, frac=0.9, ang=35.0):
    n = len(p.A)
    if p.closed or n < 3:
        return False
    if e == 0:
        a, b, c = p.A[0], p.A[1], p.A[2]
    else:
        a, b, c = p.A[-1], p.A[-2], p.A[-3]
    s1, s2 = a - b, b - c
    if np.linalg.norm(s1) >= frac * p.w or np.linalg.norm(s2) < 1e-6:
        return False
    cosv = float(unit(s1) @ unit(s2))
    return np.degrees(np.arccos(np.clip(cosv, -1, 1))) > ang


def find_spurs(m: Model):
    return [(i, e) for i, p in enumerate(m.paths) for e in (0, 1) if _spur(p, e)]


def trim_tail(m: Model, i, e):
    m = m.copy()
    p = m.paths[i]
    if not _spur(p, e):
        return m
    if e == 0:
        p.A, p.Hin, p.Hout = p.A[1:], p.Hin[1:], p.Hout[1:]
        p.Hin[0] = p.A[0]
    else:
        p.A, p.Hin, p.Hout = p.A[:-1], p.Hin[:-1], p.Hout[:-1]
        p.Hout[-1] = p.A[-1]
    return m
