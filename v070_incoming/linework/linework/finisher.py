"""Finisher engine: the last engine of the loop.  It runs once every icon is on the canvas and inspects each icon on its own,
looking for the 3-4 small places where a machine drawing still gives itself away, and fixes each one so the result reads as
hand-made vector art.

Sites it looks for (each is located, fixed, and the fix is verified by a re-render):
  handles   a segment whose handles point backwards or are far longer than the segment (loops, bulges, overshoots)  -> redraw path
  density   far more nodes than the shape needs (wobble)                                                          -> simplify
  align     near-vertical / near-horizontal straight strokes that are off-axis by a hair, edges of the same shape
            that are 0.3-1 px apart                                                                                -> exact axis, shared coordinate
  widths    strokes of one icon that differ by a few percent in width                                             -> one width per weight class
  specks    tiny leftovers shorter than a stroke width                                                          -> remove
  hotspots  places where render and source still disagree                                                         -> re-fit harder, then re-draw locally
A fix is kept only if the match to the source does not get worse (beyond a tiny cosmetic tolerance), no new gap / notch / spur
appears, and the total cosmetic drift is capped.  So the Finisher can polish, but it cannot damage the match.
"""
from __future__ import annotations
import time
import numpy as np, cv2
from .model import Model, Path
from .geom import resample, fit_curve
from . import edit as E
from . import topology as T


def _topo(m):
    return len(T.find_gaps(m)) + len(T.find_notches(m)) + len(T.find_spurs(m))


# ------------------------------------------------------------------ detectors
def bad_handle_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed and len(p.segs()) >= 4:
            continue  # exact rings are handled elsewhere
        for k, c in enumerate(p.segs()):
            v = c[3] - c[0]
            L = np.linalg.norm(v)
            if L < 3:
                continue
            u = v / L
            h0, h1 = c[1] - c[0], c[3] - c[2]
            if (h0 @ u < -0.6 and np.linalg.norm(h0) > 1.5) or (h1 @ u < -0.6 and np.linalg.norm(h1) > 1.5) or \
               np.linalg.norm(h0) > 1.6 * L + 2 or np.linalg.norm(h1) > 1.6 * L + 2:
                out.append((i, c[0] + v / 2))
                break
    return out


def dense_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        n = len(p.segs())
        if n >= 4 and n > p.length() / (4.0 * p.w) + 1:
            out.append((i, p.A[len(p.A) // 2]))
    return out


def speck_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        L = p.length()
        if 0.3 * p.w < L < 1.5 * p.w and not p.closed:
            out.append((i, p.A.mean(0)))
    return out


def hairline_paths(m: Model, frac=0.4):
    """Paths far thinner than the icon's strokes: JPEG shadows / faint grey that were traced as a hair-thin line."""
    ws = [(p.w, p.length()) for p in m.paths if p.length() > 3 * p.w]
    if len(ws) < 3:
        return []
    med = float(np.median([w for w, _ in ws]))
    return [(i, p.A.mean(0)) for i, p in enumerate(m.paths) if p.w < frac * med and p.length() > 0]


def wobbly_straights(m: Model, dev_frac=0.12, min_len=4.0):
    """Open paths that are really one straight stroke (every point within dev_frac*w of the chord) but carry extra nodes / bends."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        f = p.flat(1.0)
        v = f[-1] - f[0]
        L = np.linalg.norm(v)
        if L < min_len * p.w:
            continue
        n = np.array([-v[1], v[0]]) / L
        dev = np.abs((f - f[0]) @ n).max()
        proj = (f - f[0]) @ (v / L)
        if dev <= max(0.5, dev_frac * p.w) and proj.min() > -0.5 * p.w and proj.max() < L + 0.5 * p.w:
            segs = p.segs()
            exact = len(segs) == 1 and _straight(segs[0], 0.05)
            if not exact:
                out.append((i, f[len(f) // 2]))
    return out


def make_straight(m: Model, i):
    m = m.copy()
    p = m.paths[i]
    a, b = p.A[0].copy(), p.A[-1].copy()
    q = Path([a, b], [a, a + (b - a) * 2 / 3], [a + (b - a) / 3, b], p.w, p.join, p.ml, False)
    m.paths[i] = q
    return m


def _reversed(p: Path):
    return Path(p.A[::-1].copy(), p.Hout[::-1].copy(), p.Hin[::-1].copy(), p.w, p.join, p.ml, False)


def collinear_pairs(m: Model, D, ang=15.0, reach=2.6):
    """Open paths that were cut where another stroke crosses them: facing endpoints <= reach*w apart, pointing at each other,
    joined by source ink.  Returns [(i, end_i, j, end_j)] with each endpoint used once."""
    ends = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            h = p.Hout[0] if e == 0 else p.Hin[-1]
            t = a - h
            g = end_geometry(p, e)
            if g is not None:  # direction of the stroke itself, measured outside the zone where junction artefacts live
                t = g[1]
            if np.linalg.norm(t) < 1e-6:
                f = p.flat(1.0)
                t = f[0] - f[min(len(f) - 1, 6)] if e == 0 else f[-1] - f[max(0, len(f) - 7)]
            ends.append((i, e, a, t / max(np.linalg.norm(t), 1e-9), p.w, g[0] if g is not None else a))
    c = np.cos(np.radians(ang))
    cands = []
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei, a, ta, wa, ca = ends[x]
            j, ej, b, tb, wb, cb = ends[y]
            if i == j or abs(wa - wb) > 0.2 * max(wa, wb):
                continue
            if abs(_cr(cb - ca, ta)) > 0.6 * max(wa, wb):  # the other piece must lie on this piece's own line
                continue
            v = b - a
            d = np.linalg.norm(v)
            if d < 0.5 or d > reach * max(wa, wb):
                continue
            vc = cb - ca
            u = vc / np.linalg.norm(vc) if np.linalg.norm(vc) > 0.5 else v / d  # direction between the cut points (outside the hook zone)
            if ta @ u < c or tb @ (-u) < c:
                continue
            n = max(3, int(d))
            pts = a + v * np.linspace(0, 1, n)[:, None]
            xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
            if (D[ys, xs] > 0.5).mean() < 0.9:
                continue
            cands.append((d, i, ei, j, ej))
    used, out = set(), []
    for d, i, ei, j, ej in sorted(cands):
        if (i, ei) in used or (j, ej) in used:
            continue
        used.add((i, ei))
        used.add((j, ej))
        out.append((i, ei, j, ej))
    return out


def _cut_if_hooked(p: Path, e: int):
    """Cut the last 1.4 w off end e when that end is bent / jogged away from its own stroke (see end_geometry)."""
    g = end_geometry(p, e)
    if g is None or not (g[2] >= 12.0 or g[4] >= max(0.8, 0.12 * p.w)):
        return p
    mm = move_end(Model([p], 0, 0), 0, e, 1.4 * p.w)
    return p if mm is None else mm.paths[0]


def join_pairs(m: Model, pairs):
    m = m.copy()
    dead = set()
    for (i, ei, j, ej) in pairs:
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)  # P ends at the cut
        Q = Q if ej == 0 else _reversed(Q)  # Q starts at the cut
        P = _cut_if_hooked(P, 1)
        Q = _reversed(_cut_if_hooked(_reversed(Q), 1))
        a, b = P.A[-1], Q.A[0]
        A = np.vstack([P.A, Q.A])
        Hin = np.vstack([P.Hin, [b - (b - a) / 3], Q.Hin[1:]])
        Hout = np.vstack([P.Hout[:-1], [a + (b - a) / 3], Q.Hout])
        # rebuild with one connecting segment between P's last anchor and Q's first anchor
        A = np.vstack([P.A, Q.A])
        Hin = np.vstack([P.Hin, Q.Hin])
        Hout = np.vstack([P.Hout, Q.Hout])
        Hout[len(P.A) - 1] = a + (b - a) / 3
        Hin[len(P.A)] = b - (b - a) / 3
        m.paths[i] = Path(A, Hin, Hout, (P.w + Q.w) / 2, P.join, P.ml, False)
        dead.add(j)
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m


def _others_tree(m: Model, skip):
    from scipy.spatial import cKDTree
    pts, own = [], []
    for j, p in enumerate(m.paths):
        if j == skip:
            continue
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    if not pts:
        return None, None, None
    P = np.vstack(pts)
    return cKDTree(P), P, np.array(own)


def _cr(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def _end_info(p: Path, e: int, back=2.0):
    """(end point, a point `back` stroke widths behind it along the path) for end e of an open path."""
    f = p.flat(0.5)
    if e == 0:
        f = f[::-1]
    a = f[-1]
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
    k = int(np.searchsorted(cum, back * p.w))
    return a, f[::-1][min(k, len(f) - 1)]


def _protrusion(m: Model, i, a, w_i, b=None):
    """How far (px) a round cap of width w_i at `a` sticks out of the stroke it ends in or has crossed.
    Covers (1) a cap inside stroke j that pokes through j's far edge, and (2) a stub: the path crossed j's centerline
    (a and `b`, a point further back on the path, lie on opposite sides) and its end overshoots j's far edge."""
    tree, P, own = _others_tree(m, i)
    if tree is None:
        return 0.0
    d, k = tree.query(a)
    if d > w_i * 2.2:
        return 0.0
    j = own[k]
    rj = m.paths[j].w / 2
    out = max(0.0, w_i / 2 + d - rj) if d < rj else 0.0
    if b is not None:
        kk = [x for x in (k - 1, k + 1) if 0 <= x < len(P) and own[x] == j]
        if kk:
            tau = P[max(kk)] - P[min(kk)]
            if np.linalg.norm(tau) > 1e-9:
                sa = _cr(a - P[k], tau) / np.linalg.norm(tau)
                db, kb = tree.query(b)
                if own[kb] == j and db < w_i * 3:
                    kb2 = [x for x in (kb - 1, kb + 1) if 0 <= x < len(P) and own[x] == j]
                    if kb2:
                        tb = P[max(kb2)] - P[min(kb2)]
                        if np.linalg.norm(tb) > 1e-9:
                            sb = _cr(b - P[kb], tb) / np.linalg.norm(tb)
                            if sa * sb < 0 and abs(sa) > 0.15 * w_i and abs(sb) > 0.15 * w_i:
                                out = max(out, w_i / 2 + d - rj)
    return out


def cap_hits(m: Model, frac=0.1):
    """Round caps / stubs that stick out of the stroke they end in or cross (the small nubs and overshoots at junctions)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            a, b = _end_info(p, e)
            pr = _protrusion(m, i, a, p.w, b)
            if pr > frac * p.w:
                out.append((pr / p.w, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])


def _split_last(c, length):
    """Cut `length` px off the end of Bezier c (4,2): returns the shortened Bezier, or None if the segment is too short."""
    t = np.linspace(0, 1, 40)
    mt = 1 - t
    P = (mt**3)[:, None] * c[0] + (3 * mt**2 * t)[:, None] * c[1] + (3 * mt * t**2)[:, None] * c[2] + (t**3)[:, None] * c[3]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    L = seg.sum()
    if L < length + 1.5:
        return None
    cum = np.r_[0, np.cumsum(seg)]
    s = float(np.interp(L - length, cum, t))
    a, b, cc, d = c
    ab, bc, cd = a + (b - a) * s, b + (cc - b) * s, cc + (d - cc) * s
    abc, bcd = ab + (bc - ab) * s, bc + (cd - bc) * s
    return np.array([a, ab, abc, abc + (bcd - abc) * s])


def move_end(m: Model, i, e, delta):
    """delta > 0 retracts the end of path i by that many px along the path; delta < 0 extends it along its end tangent."""
    m = m.copy()
    p = m.paths[i]
    if e == 0:
        p = _reversed(p)
    if delta > 0:
        rest = delta
        while True:  # a short last segment is dropped entirely and the remainder is taken off the one before
            c = p.segs()[-1]
            c2 = _split_last(c, rest)
            if c2 is not None:
                break
            if len(p.A) <= 2:
                return None
            tt = np.linspace(0, 1, 30)
            pts = np.array([(1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u * u * c[2] + u**3 * c[3] for u in tt])
            rest -= float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
            p = Path(p.A[:-1], p.Hin[:-1], np.vstack([p.Hout[:-2], p.A[-2:-1]]), p.w, p.join, p.ml, False)
            if rest <= 0.5:
                m.paths[i] = p
                return m
        p.A[-1] = c2[3]
        p.Hin[-1] = c2[2]
        p.Hout[-2] = c2[1]
    else:
        t = p.A[-1] - p.Hin[-1]
        n = np.linalg.norm(t)
        if n < 1e-6:
            return None
        v = t / n * (-delta)
        p.A[-1] = p.A[-1] + v
        p.Hin[-1] = p.Hin[-1] + v
    m.paths[i] = p
    return m


def best_end_move(m: Model, i, e, w):
    """Pick the retract/extend amount that leaves the least cap sticking out; returns (model, new_protrusion) or None."""
    p = m.paths[i]
    a0, b0 = _end_info(p, e)
    base = _protrusion(m, i, a0, p.w, b0)
    best = None
    for dl in (-0.5, -0.3, -0.15, 0.15, 0.3, 0.5, 0.75, 1.0, 1.25, 1.6):
        cand = move_end(m, i, e, dl * p.w)
        if cand is None:
            continue
        q = cand.paths[i]
        a1, b1 = _end_info(q, 1)
        pr = _protrusion(cand, i, a1, q.w, b1)
        if pr < base - 0.05 * p.w and (best is None or pr < best[1] - 1e-6 or (abs(pr - best[1]) < 1e-6 and abs(dl) < best[2])):
            best = (cand, pr, abs(dl))
    return None if best is None else (best[0], best[1])


def arc_fit(p: Path, tol_frac=0.1):
    """If open path p is (nearly) one circular arc, return the exact-arc replacement Path, else None."""
    from .rings import _kasa
    f = resample(p.flat(), 1.0)
    if len(f) < 8:
        return None
    cx, cy, r = _kasa(f)
    c = np.array([cx, cy])
    dist = np.linalg.norm(f - c, axis=1)
    if np.abs(dist - r).max() > max(0.6, tol_frac * p.w) or not (1.2 * p.w < r < 60 * p.w):
        return None
    ang = np.unwrap(np.arctan2(f[:, 1] - cy, f[:, 0] - cx))
    d = np.diff(ang)
    span = float(ang[-1] - ang[0])
    if abs(span) < 0.6 or abs(span) > 5.8 or (np.sign(d) == np.sign(span)).mean() < 0.95:
        return None
    n = int(np.ceil(abs(span) / (np.pi / 2) - 1e-9))
    step = span / n
    segs = []
    for k in range(n):
        t0, t1 = ang[0] + k * step, ang[0] + (k + 1) * step
        P0 = c + r * np.array([np.cos(t0), np.sin(t0)])
        P3 = c + r * np.array([np.cos(t1), np.sin(t1)])
        h = 4.0 / 3.0 * np.tan(step / 4.0) * r
        P1 = P0 + h * np.array([-np.sin(t0), np.cos(t0)])
        P2 = P3 - h * np.array([-np.sin(t1), np.cos(t1)])
        segs.append([P0, P1, P2, P3])
    q = Path.from_segs(segs, p.w, closed=False, join=p.join)
    q.ml = p.ml
    # already exact? then nothing to gain
    g = resample(q.flat(), 1.0)
    cur = resample(p.flat(), 1.0)
    k = min(len(g), len(cur))
    if np.abs(np.linalg.norm(g[:k] - c, axis=1) - r).max() > 0.1 and np.abs(dist - r).max() < 0.12:
        return None
    return q


def arc_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        q = arc_fit(p)
        if q is not None:
            out.append((i, p.A[len(p.A) // 2], q))
    return out


def excess_ends(m: Model, ink, D, frac=0.1):
    """Open-path ends with ink in the render that the source does not have around them (thick tips, lumps).
    Returns [(excess_px, path, end, xy)] sorted by excess."""
    extra = ((ink > 0.5) & (D < 0.3)).astype(np.float32)
    H, W = extra.shape
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        r = int(max(3, 1.4 * p.w))
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            x0, x1 = int(max(a[0] - r, 0)), int(min(a[0] + r + 1, W))
            y0, y1 = int(max(a[1] - r, 0)), int(min(a[1] + r + 1, H))
            if x1 <= x0 or y1 <= y0:
                continue
            ex = float(extra[y0:y1, x0:x1].sum())
            if ex >= frac * p.w * p.w:
                out.append((ex, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])


def corner_pairs(m: Model, tol=1.2):
    """Two open paths that simply end at the same point (a corner drawn as two strokes with two overlapping round caps)
    and nothing else touches that point -> [(i, end_i, j, end_j)]."""
    ends = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        ends += [(i, 0, p.A[0], p.w), (i, 1, p.A[-1], p.w)]
    out, used = [], set()
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei, a, wa = ends[x]
            j, ej, b, wb = ends[y]
            if i == j or (i, ei) in used or (j, ej) in used:
                continue
            if np.linalg.norm(a - b) > tol or abs(wa - wb) > 0.2 * max(wa, wb):
                continue
            mid = (a + b) / 2
            third = False
            for k, q in enumerate(m.paths):
                if k in (i, j):
                    continue
                f = q.flat(1.0)
                if np.linalg.norm(f - mid, axis=1).min() < 0.7 * max(wa, wb):
                    third = True
                    break
            if third:
                continue
            used.add((i, ei))
            used.add((j, ej))
            out.append((i, ei, j, ej))
    return out


def merge_corners(m: Model, pairs):
    """One stroke with a corner node instead of two strokes with two overlapping caps (the join is then drawn once, cleanly)."""
    m = m.copy()
    dead = set()
    for (i, ei, j, ej) in pairs:
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)
        Q = Q if ej == 0 else _reversed(Q)
        mid = (P.A[-1] + Q.A[0]) / 2
        dP, dQ = mid - P.A[-1], mid - Q.A[0]
        A = np.vstack([P.A, Q.A[1:]])
        Hin = np.vstack([P.Hin, Q.Hin[1:]])
        Hout = np.vstack([P.Hout[:-1], Q.Hout])
        A[len(P.A) - 1] = mid
        Hin[len(P.A) - 1] = P.Hin[-1] + dP
        Hout[len(P.A) - 1] = Q.Hout[0] + dQ
        m.paths[i] = Path(A, Hin, Hout, (P.w + Q.w) / 2, P.join, P.ml, False)
        dead.add(j)
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m


def _end_frame(p: Path, e: int):
    """Oriented flat polyline (end last) and the cumulative arc length measured from the END backwards."""
    f = resample(p.flat(), 0.5)
    if e == 0:
        f = f[::-1]
    back = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]  # back[k] = arc length from end to f[::-1][k]
    return f, back


def end_geometry(p: Path, e: int):
    """(cut point c at 1.4 w from the end, reference direction t pointing to the end, hook angle in degrees, end point).
    The reference direction is measured on the stretch 1.4-3.6 w from the end, i.e. outside the zone where junction artefacts live;
    the hook angle compares it with the direction of the last 0.9 w."""
    f, back = _end_frame(p, e)
    fr = f[::-1]
    if back[-1] < 4.0 * p.w:
        return None
    sel = (back >= 1.4 * p.w) & (back <= 3.6 * p.w)
    if sel.sum() < 4:
        return None
    seg = fr[sel]
    c = fr[np.searchsorted(back, 1.4 * p.w)]
    # PCA direction of the reference stretch, oriented from far to near the end
    u, sv, vt = np.linalg.svd(seg - seg.mean(0), full_matrices=False)
    t = vt[0]
    if t @ (seg[0] - seg[-1]) < 0:  # seg[0] is nearest the end
        t = -t
    t = t / np.linalg.norm(t)
    k = np.searchsorted(back, 0.9 * p.w)
    te = fr[0] - fr[min(k, len(fr) - 1)]
    n = np.linalg.norm(te)
    ang = 0.0 if n < 1e-6 else float(np.degrees(np.arccos(np.clip((te / n) @ t, -1, 1))))
    dev = abs(float((fr[0] - c)[0] * t[1] - (fr[0] - c)[1] * t[0]))  # sideways offset of the end from the stroke's own straight line
    return c, t, ang, fr[0], dev


def _straight_before_end(p: Path, e: int, t, tol_deg=7.0):
    """True when the stroke runs straight into its end (direction of the stretch 3.6-6 w from the end equals the reference direction),
    so a bend in the last 1.4 w is an artefact, not a curve."""
    f, back = _end_frame(p, e)
    fr = f[::-1]
    sel = (back >= 3.6 * p.w) & (back <= 6.0 * p.w)
    if sel.sum() < 4:
        return back[-1] < 6.0 * p.w  # short stroke: cannot tell, accept
    seg = fr[sel]
    u, sv, vt = np.linalg.svd(seg - seg.mean(0), full_matrices=False)
    d = vt[0]
    return abs(float(d @ t)) >= np.cos(np.radians(tol_deg))


def end_hooks(m: Model, min_angle=12.0):
    """Open-path ends whose last stretch bends away from a stroke that is straight up to there (hooks, curls, jogs at joints)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            g = end_geometry(p, e)
            if g is not None and (g[2] >= min_angle or g[4] >= max(0.8, 0.12 * p.w)) and _straight_before_end(p, e, g[1]):
                out.append((max(g[2], 90.0 * g[4] / max(p.w, 1e-6)), i, e, g[3]))
    return sorted(out, key=lambda t: -t[0])


def fix_end(m: Model, i, e, reach=4.5, target=None, smooth=False):
    """Replace the last 1.4 w of path i's end e by a straight run along the stroke's own direction, ending ON the centerline of the stroke it
    joins (or, for a free end, at the same distance as before). Returns the new model or None."""
    p = m.paths[i]
    g = end_geometry(p, e)
    if g is None:
        return None
    c, t, ang, end, dev = g
    tree, P, own = _others_tree(m, i)
    X = None if target is None else np.asarray(target, float)
    if X is None and tree is not None:
        s = np.arange(0.2 * p.w, reach * p.w, 0.4)
        ray = c + s[:, None] * t
        d, k = tree.query(ray)
        j = int(np.argmin(d))
        if d[j] < 0.6 * p.w:
            X = P[k[j]].copy()
    if X is None:
        if ang < 12.0 and dev < max(0.8, 0.12 * p.w):
            return None
        X = c + t * max(1.0 * p.w, float(np.linalg.norm(end - c)))
    cand = move_end(m, i, e, 1.4 * p.w)
    if cand is None:
        return None
    q = cand.paths[i]
    cut = q.A[-1]
    v = X - cut
    L = np.linalg.norm(v)
    if L < 0.3 or np.degrees(np.arccos(np.clip((v / L) @ t, -1, 1))) > 30.0:
        return None
    u = v / L
    hin = np.linalg.norm(q.Hin[-1] - cut)
    if smooth:  # arc-like run: leave along the stroke's own tangent and arrive along it
        q.Hin[-1] = cut - t * hin
        q.Hout[-1] = cut + t * (L / 3)
        q.A = np.vstack([q.A, X])
        q.Hin = np.vstack([q.Hin, X - t * (L / 3)])
        q.Hout = np.vstack([q.Hout, X])
        return cand
    q.Hin[-1] = cut - u * hin  # keep the stroke smooth (G1) where the straight run starts
    q.Hout[-1] = cut + v / 3
    q.A = np.vstack([q.A, X])
    q.Hin = np.vstack([q.Hin, X - v / 3])
    q.Hout = np.vstack([q.Hout, X])
    return cand


def _straight(c, tol=0.6):
    v = c[3] - c[0]
    L = np.linalg.norm(v)
    if L < 8:
        return False
    n = np.array([-v[1], v[0]]) / L
    return max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n)) * 0.75 < tol


# ------------------------------------------------------------------ fixers
def redraw_path(m: Model, i):
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 0.75)
    segs = fit_curve(f, 0.8, 0.45)
    if segs:
        q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
        q.ml = p.ml
        m.paths[i] = q
    return m


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def u(self, a, b):
        self.p[self.f(a)] = self.f(b)


def align_groups(m: Model, ang=2.5, par_tol=1.0, max_shift=1.5):
    """Returns a list of (axis, [(path, anchor)...], new_coordinate) alignments (not applied)."""
    nodes = []
    for i, p in enumerate(m.paths):
        n = len(p.A) - (1 if p.closed else 0)
        for k in range(n):
            nodes.append((i, k, p.A[k]))
    if not nodes:
        return []
    xy = np.array([n[2] for n in nodes])
    idx = {(n[0], n[1]): j for j, n in enumerate(nodes)}
    ufx, ufy = _UF(len(nodes)), _UF(len(nodes))
    from scipy.spatial import cKDTree
    for a, b in cKDTree(xy).query_pairs(0.8):
        ufx.u(a, b)
        ufy.u(a, b)
    vx, vy = [], []  # nodes taking part in vertical / horizontal straight strokes
    sa = np.sin(np.radians(ang))
    for i, p in enumerate(m.paths):
        for k, c in enumerate(p.segs()):
            if not _straight(c):
                continue
            k1 = (k + 1) % (len(p.A) - 1) if p.closed else k + 1
            a, b = idx[(i, k)], idx[(i, k1)]
            v = c[3] - c[0]
            L = np.linalg.norm(v)
            if abs(v[0]) < sa * L:
                ufx.u(a, b)
                vx += [a, b]
            elif abs(v[1]) < sa * L:
                ufy.u(a, b)
                vy += [a, b]
    out = []
    for axis, uf, vs in ((0, ufx, vx), (1, ufy, vy)):
        # parallel strokes of the same shape: cluster group means that are within par_tol
        groups = {}
        for j in set(vs):
            groups.setdefault(uf.f(j), []).append(j)
        means = sorted((np.mean([xy[j][axis] for j in g]), r) for r, g in groups.items())
        for (m0, r0), (m1, r1) in zip(means, means[1:]):
            if m1 - m0 <= par_tol:
                uf.u(r0, r1)
        allg = {}
        for j in range(len(nodes)):
            allg.setdefault(uf.f(j), []).append(j)
        for r, g in allg.items():
            if len(g) < 2:
                continue
            vals = np.array([xy[j][axis] for j in g])
            new = float(vals.mean())
            if np.abs(vals - new).max() < 0.02 or np.abs(vals - new).max() > max_shift:
                continue
            if not any(j in set(vs) for j in g):
                continue
            out.append((axis, [(nodes[j][0], nodes[j][1]) for j in g], new))
    return out


def apply_align(m: Model, groups):
    m = m.copy()
    for axis, members, new in groups:
        for (i, k) in members:
            p = m.paths[i]
            d = new - p.A[k][axis]
            for arr in (p.A, p.Hin, p.Hout):
                arr[k][axis] += d
            if p.closed and k == 0:
                for arr in (p.A, p.Hin, p.Hout):
                    arr[-1][axis] = arr[0][axis]
    for i in {g[0] for grp in groups for g in grp[1]}:
        p = m.paths[i]
        for k, c in enumerate(p.segs()):
            if _straight(c, 1.2):
                v = c[3] - c[0]
                p.Hout[k] = c[0] + v / 3
                p.Hin[k + 1] = c[0] + 2 * v / 3
    return m


def width_plan(m: Model, ratio=1.22, max_dev=0.4, anchor=None):
    """Cluster stroke widths into weight classes (long paths only) and return {path: class width} for paths that are off by 3-40 %."""
    items = [(p.w, p.length(), i) for i, p in enumerate(m.paths) if p.length() > 3 * p.w]
    if len(items) < 2:
        return {}
    items.sort()
    cl, cur = [], [items[0]]
    for it in items[1:]:
        if it[0] / cur[0][0] <= ratio:
            cur.append(it)
        else:
            cl.append(cur)
            cur = [it]
    cl.append(cur)
    centers = []
    for c in cl:
        w = np.array([t[0] for t in c])
        L = np.array([t[1] for t in c])
        o = np.argsort(w)
        cw = np.cumsum(L[o])
        centers.append(float(w[o][np.searchsorted(cw, cw[-1] / 2)]))
    if anchor:  # the set-wide stroke width wins over this icon's own estimate when they are close
        jn = int(np.argmin([abs(anchor - c) for c in centers]))
        if abs(anchor - centers[jn]) / anchor < 0.2:
            centers[jn] = float(anchor)
    plan = {}
    for i, p in enumerate(m.paths):
        j = int(np.argmin([abs(p.w - c) for c in centers]))
        dev = abs(p.w - centers[j]) / centers[j]
        if 0.03 < dev <= max_dev:
            plan[i] = centers[j]
    return plan


# ------------------------------------------------------------------ engine
def finish(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_hot=4, set_w=None, skip=()):
    """Returns (model, ink, soft, report) where report = dict(sites=[...], found=int, fixed=int, drift=float)."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    start = cur
    topo = _topo(model)
    drift_cap = 0.006 * max(doctor.area, 1)
    sites = []
    st = dict(model=model, ink=ink, cur=cur, topo=topo)

    def tol_for(cur_):
        return max(2.0, 0.003 * cur_)

    def attempt(cand, kind, xy, tol=None, improve=False):
        """verify `cand`; returns True when kept."""
        if cand is None or kind in skip:
            return False
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        lim = st["cur"] - 0.5 if improve else st["cur"] + (tol_for(st["cur"]) if tol is None else tol)
        ok = s2 <= lim and (s2 - start) <= drift_cap
        t2 = _topo(cand) if ok else st["topo"]  # topology is the slow check: only for candidates that already pass on match
        ok = ok and t2 <= st["topo"]
        sites.append(dict(kind=kind, x=float(xy[0]), y=float(xy[1]), fixed=bool(ok)))
        if ok:
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
        return ok

    # 0. hair-thin traces of faint grey (never real strokes)
    for i, xy in sorted(hairline_paths(st["model"]), key=lambda t: -t[0]):
        if i < len(st["model"].paths):
            p = st["model"].paths[i]
            attempt(E.remove_path(st["model"], i), "hairline", xy, tol=0.6 * p.w * p.length())
    # 0c. hooks / jogs at the ends of strokes: straight run along the stroke's own direction, ending on the centerline it joins
    done_h = 0
    for ang, i, e, xy in end_hooks(st["model"])[:40]:
        if not time_ok() or done_h >= 40:
            break
        if i < len(st["model"].paths):
            cand = fix_end(st["model"], i, e)
            if cand is not None:
                attempt(cand, "ends", xy)
                done_h += 1
    # 0a. strokes that were cut where another stroke crosses them -> one continuous stroke
    pairs = collinear_pairs(st["model"], D)
    if pairs:
        mid = np.mean([st["model"].paths[p[0]].A[0 if p[1] == 0 else -1] for p in pairs], axis=0)
        if not attempt(join_pairs(st["model"], pairs), "join", mid):
            sites.pop()
            for pr in pairs[:20]:
                if not time_ok():
                    break
                n_ = len(st["model"].paths)
                if max(pr[0], pr[2]) < n_:
                    attempt(join_pairs(st["model"], [pr]), "join", st["model"].paths[pr[0]].A[0 if pr[1] == 0 else -1])
    # 0b. wobbly strokes that are really one straight line
    for i, xy in wobbly_straights(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(make_straight(st["model"], i), "straighten", xy)
    # 1. handles that loop / overshoot
    for i, xy in sorted(bad_handle_paths(st["model"]), key=lambda t: -t[0]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(redraw_path(st["model"], i), "handles", xy)
    # 2. needless nodes
    for i, xy in sorted(dense_paths(st["model"]), key=lambda t: -t[0]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(E.simplify(st["model"], i, 0.7), "density", xy)
    # 3. alignment of straight strokes: all at once, else one group at a time
    groups = align_groups(st["model"])
    if groups:
        c0 = np.mean([st["model"].paths[g[1][0][0]].A[g[1][0][1]] for g in groups], axis=0)
        n0 = len(sites)
        if not attempt(apply_align(st["model"], groups), "align", c0):
            sites.pop()
            for g in groups[:16]:
                if not time_ok():
                    break
                p = st["model"].paths[g[1][0][0]]
                attempt(apply_align(st["model"], [g]), "align", p.A[g[1][0][1]])
    # 4. widths
    plan = width_plan(st["model"], anchor=set_w) if "widths" not in skip else {}
    if plan:
        cand = st["model"].copy()
        for i, wv in plan.items():
            cand.paths[i].w = wv
        mid = np.mean([st["model"].paths[i].A.mean(0) for i in plan], axis=0)
        if not attempt(cand, "widths", mid):
            sites.pop()
            for i, wv in list(plan.items())[:12]:
                if not time_ok():
                    break
                c1 = st["model"].copy()
                c1.paths[i].w = wv
                attempt(c1, "widths", st["model"].paths[i].A.mean(0))
    # 4b. caps that stick out of the stroke they end in (nubs at junctions)
    done = 0
    for pr, i, e, xy in cap_hits(st["model"])[:40]:
        if not time_ok() or done >= 30:
            break
        if i >= len(st["model"].paths):
            continue
        mv = best_end_move(st["model"], i, e, w)
        if mv is not None:
            if not attempt(mv[0], "caps", xy):
                sites.pop()
                attempt(T.weld_all(mv[0]), "caps", xy)
            done += 1
        # the moved path may have been re-oriented; later hits are re-detected below
    # 4d. thick tips / lumps: ends with excess ink around them are pulled back by whatever amount helps most (verified)
    for ex, i, e, xy in excess_ends(st["model"], st["ink"], D)[:20]:
        if not time_ok():
            break
        if i >= len(st["model"].paths):
            continue
        wi = st["model"].paths[i].w
        best = None
        for dl in (0.5, 0.9, 1.4):
            cand = move_end(st["model"], i, e, dl * wi)
            if cand is None:
                continue
            s2 = doctor.soft(ink_of(cand))
            if best is None or s2 < best[0]:
                best = (s2, cand)
            elif s2 > best[0]:
                break  # getting worse the further we pull back
        if best is not None and best[0] < st["cur"] - 0.5:
            attempt(best[1], "tips", xy, improve=True)
    # 4e. corners drawn as two strokes -> one stroke with a corner node
    cp = corner_pairs(st["model"])
    if cp:
        c1 = merge_corners(st["model"], cp)
        if not attempt(c1, "corners", st["model"].paths[cp[0][0]].A[0]):
            sites.pop()
            for pr in cp[:15]:
                if not time_ok():
                    break
                if max(pr[0], pr[2]) < len(st["model"].paths):
                    attempt(merge_corners(st["model"], [pr]), "corners", st["model"].paths[pr[0]].A[0])
    # 4c. round shapes: wobbly circular arcs / near-circles become exact circles and arcs
    for i, xy, q in arc_paths(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            c1 = st["model"].copy()
            c1.paths[i] = q
            attempt(c1, "arcs", xy, tol=max(3.0, 0.01 * st["cur"]))
    for i, p in enumerate(list(st["model"].paths)):
        if not time_ok():
            break
        if i < len(st["model"].paths) and p.closed and len(p.segs()) >= 3:
            c1 = E.circle(st["model"], i, max_dev=max(0.9, 0.12 * p.w), robust=True)
            q = c1.paths[i]
            if len(q.segs()) == 4 and (len(p.segs()) != 4 or not np.allclose(q.A, p.A, atol=0.05)):
                attempt(c1, "circles", p.A.mean(0), tol=max(3.0, 0.01 * st["cur"]))
    # 5. specks
    for i, xy in sorted(speck_paths(st["model"]), key=lambda t: -t[0]):
        if i < len(st["model"].paths):
            attempt(E.remove_path(st["model"], i), "specks", xy, tol=0.6 * w)
    # 6. hot spots: re-fit harder, then redraw locally
    regs = sorted(doctor.regions(st["ink"], win=9), key=lambda r: -r[4])[:max_hot]
    for r in regs:
        if not time_ok():
            break
        xy = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        box = [int(r[0]), int(r[1]), int(r[2]), int(r[3])]
        before = st["cur"]
        if attempt(E.refine_region(st["model"], D, box, taus=(0.8, 0.5, 0.35, 0.28), iters=60), "hotspots", xy, improve=True):
            continue
        sites.pop()
        cand = _redraw_region(st["model"], D, box, w)
        if not attempt(cand, "hotspots", xy, improve=True):
            pass
    found = len(sites)
    fixed = sum(s["fixed"] for s in sites)
    return st["model"], st["ink"], st["cur"], dict(sites=sites, found=found, fixed=fixed, drift=float(st["cur"] - start))


def _redraw_region(m: Model, D, box, w, margin=None):
    """Replace the paths that lie (almost) entirely inside `box` by a fresh trace of the source ink inside it."""
    from .trace import refined_branches
    from .chains import build_chains
    from .fitting import initial_model
    margin = int(1.2 * w) if margin is None else margin
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    inside = []
    for i, p in enumerate(m.paths):
        f = p.flat(2.0)
        ok = (f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)
        if ok.mean() > 0.9:
            inside.append(i)
    if not inside:
        return None
    mask = np.zeros(D.shape, np.float32)
    mask[max(y0, 0):y1, max(x0, 0):x1] = 1
    Dc = (D * mask).astype(np.float32)
    br = refined_branches(Dc)
    if not br:
        return None
    chains, _ = build_chains(br)
    nm = initial_model(chains, Dc, sigma=2.0)
    if not nm.paths:
        return None
    keep = [p for i, p in enumerate(m.paths) if i not in set(inside)]
    out = Model(keep + nm.paths, m.width, m.height)
    return T.weld_all(out)
