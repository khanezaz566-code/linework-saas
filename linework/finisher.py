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
from .geom import resample, fit_curve, bez, unit, line_inter
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
        if (0.3 * p.w < L < 1.5 * p.w and not p.closed) or (p.closed and L < 1.5 * p.w):
            out.append((i, p.A.mean(0)))
        elif L <= 0.3 * p.w and not p.closed:
            tree, _, _ = _others_tree(m, i)
            if tree is not None and tree.query(p.A.mean(0))[0] < 0.6 * p.w:
                out.append((i, p.A.mean(0)))
    return out


def hairline_paths(m: Model, frac=0.4):
    """Paths far thinner than the icon's strokes: JPEG shadows / faint grey that were traced as a hair-thin line."""
    ws = [(p.w, p.length()) for p in m.paths if p.length() > 3 * p.w]
    if len(ws) < 3:
        return []
    med = float(np.median([w for w, _ in ws]))
    return [(i, p.A.mean(0)) for i, p in enumerate(m.paths) if p.w < frac * med and p.length() > 0]


def wobbly_straights(m: Model, dev_frac=0.12, min_len=1.8):
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
        devs = np.abs((f - f[0]) @ n)
        dev = float(devs.max())
        proj = (f - f[0]) @ (v / L)
        dx, dy = abs(v[0]), abs(v[1])
        is_axis_aligned = (min(dx, dy) <= 0.25 * p.w) and (max(dx, dy) >= 4.0 * p.w)
        is_local_bulge = L >= 4.5 * p.w and len(p.A) >= 4 and (devs <= 0.15 * p.w).mean() >= 0.55
        short_dev = 0.38 if len(p.A) == 3 else 0.22
        eff_dev = max(0.5, ((1.5 if is_axis_aligned else 0.42) if (is_axis_aligned or is_local_bulge) else (max(dev_frac, short_dev) if L < 3.5 * p.w and len(p.A) >= 3 else dev_frac)) * p.w)
        if dev <= eff_dev and proj.min() > -0.5 * p.w and proj.max() < L + 0.5 * p.w:
            segs = p.segs()
            exact = len(segs) == 1 and _straight(segs[0], 0.05)
            if not exact:
                out.append((i, f[len(f) // 2]))
    return out


def z_fold_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 3:
            continue
        A = p.A
        for k in range(len(A) - 2):
            v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.60:
                out.append((i, A[k + 1].copy()))
                break
    return out


def fix_z_fold_cands(m: Model, i: int):
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return []
    cands = []
    A, Hin, Hout = p.A.copy(), p.Hin.copy(), p.Hout.copy()
    if len(A) == 3:
        for drop in (1, 0, 2):
            keep = [j for j in range(3) if j != drop]
            a, b = A[keep[0]].copy(), A[keep[1]].copy()
            q = Path([a, b], [a, a + (b - a) * 2.0 / 3.0], [a + (b - a) / 3.0, b], p.w, p.join, p.ml, False)
            m1 = m.copy()
            m1.paths[i] = q
            cands.append(m1)
        return cands
    for k in range(len(A) - 2):
        v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
        L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.60:
            if k + 3 < len(A):
                v3 = A[k + 3] - A[k + 2]
                L3 = float(np.linalg.norm(v3))
                if L3 > 1e-3 and (v2 / L2) @ (v3 / L3) < -0.60:
                    # Candidate 1: split Z-fold into the two overlapping strokes (preserving curved handles on k+2 -> k+3)
                    idx2 = list(range(k + 3, len(A)))
                    idx1_base = list(range(0, k + 1)) + [k + 2, k + 3]
                    A1_b, Hi1_b, Ho1_b = A[idx1_base].copy(), Hin[idx1_base].copy(), Hout[idx1_base].copy()
                    d0 = A1_b[k + 1] - A1_b[k]
                    Ho1_b[k] = A1_b[k] + d0 / 3.0
                    Hi1_b[k + 1] = A1_b[k] + 2.0 * d0 / 3.0
                    Ho1_b[-1] = A1_b[-1].copy()
                    p1_base = Path(A1_b, Hi1_b, Ho1_b, p.w, p.join, p.ml, False)
                    for merge_k in (True, False):
                        if merge_k and k >= 1 and np.linalg.norm(A[k + 2] - A[k]) <= 0.85 * p.w:
                            idx1 = list(range(0, k)) + [k + 2, k + 3]
                            A1, Hi1, Ho1 = A[idx1].copy(), Hin[idx1].copy(), Hout[idx1].copy()
                            Hi1[k] = Hin[k].copy()
                            Ho1[-1] = A1[-1].copy()
                            p1 = Path(A1, Hi1, Ho1, p.w, p.join, p.ml, False)
                        elif not merge_k:
                            p1 = p1_base.copy()
                        else:
                            continue
                        u_wall = unit(A[-1] - A[k + 3]) if len(A) > k + 4 and np.linalg.norm(A[-1] - A[k + 3]) > 1e-3 else unit(A[k + 3] - A[k + 1])
                        n_wall = np.array([-u_wall[1], u_wall[0]])
                        f1 = p1.flat(0.25)
                        rel = f1 - A[k + 3]
                        behind = (rel @ u_wall) < -0.5 * p.w
                        if behind.any():
                            sub = f1[behind]
                            lat_d = np.abs((sub - A[k + 3]) @ n_wall)
                            P0_wall = sub[int(np.argmin(lat_d))].copy()
                        else:
                            proj_back = float((A[k] - A[k + 1]) @ u_wall)
                            P0_wall = A[k + 1] + min(proj_back, -0.2 * p.w) * u_wall if proj_back < 0 else A[k + 1].copy()
                        # If the wall from P0_wall through A[idx2] is colinear, collapse redundant middle node A[k+3]
                        if len(idx2) == 2 and abs(float((A[idx2[-1]] - P0_wall) @ n_wall)) <= 0.15 * p.w:
                            A2 = np.vstack([[P0_wall], [A[idx2[-1]]]])
                            d2 = A2[1] - A2[0]
                            Hi2 = np.vstack([[P0_wall], [P0_wall + 2.0 * d2 / 3.0]])
                            Ho2 = np.vstack([[P0_wall + d2 / 3.0], [A2[1]]])
                        else:
                            A2 = np.vstack([[P0_wall], A[idx2]])
                            Hi2 = np.vstack([[P0_wall], Hin[idx2]])
                            Ho2 = np.vstack([[P0_wall + (A2[1] - P0_wall) / 3.0], Hout[idx2]])
                            Hi2[1] = P0_wall + 2.0 * (A2[1] - P0_wall) / 3.0
                        p2 = Path(A2, Hi2, Ho2, p.w, p.join, p.ml, False)
                        # Snap p1's end onto p2 so T.find_gaps sees 0 gap at both ends
                        f2 = p2.flat(0.25)
                        end1 = f2[int(np.argmin(np.linalg.norm(f2 - p1.A[-1], axis=1)))].copy()
                        d_end = end1 - p1.A[-1]
                        p1.A[-1] = end1
                        p1.Hin[-1] = p1.Hin[-1] + d_end
                        p1.Hout[-1] = end1.copy()
                        m_split = m.copy()
                        m_split.paths[i] = p1
                        m_split.paths.append(p2)
                        cands.append(m_split)
            # Candidate 2: drop only spike k+1 (preserving handles on k+2 -> k+3)
            for drop_set in ((k + 1,), (k + 2,), (k + 1, k + 2)):
                keep = [j for j in range(len(A)) if j not in drop_set and j < len(A)]
                if len(keep) < 2:
                    continue
                Ak, Hik, Hok = A[keep].copy(), Hin[keep].copy(), Hout[keep].copy()
                if k < len(Ak) - 1:
                    d = Ak[k + 1] - Ak[k]
                    Hok[k] = Ak[k] + d / 3.0
                    Hik[k + 1] = Ak[k] + 2.0 * d / 3.0
                m1 = m.copy()
                m1.paths[i] = Path(Ak, Hik, Hok, p.w, p.join, p.ml, False)
                cands.append(m1)
            break
    cands.append(fix_z_fold(m, i))
    return cands


def fix_z_fold(m: Model, i: int):
    m = m.copy()
    p = m.paths[i]
    if p.closed or len(p.A) < 4:
        return m
    A, Hin, Hout = p.A.copy(), p.Hin.copy(), p.Hout.copy()
    changed = True
    while changed and len(A) >= 4:
        changed = False
        for k in range(len(A) - 2):
            v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.65:
                if k + 3 < len(A):
                    v3 = A[k + 3] - A[k + 2]
                    L3 = float(np.linalg.norm(v3))
                    if L3 > 1e-3 and (v2 / L2) @ (v3 / L3) < -0.65:
                        keep = [j for j in range(len(A)) if j not in (k + 1, k + 2)]
                    else:
                        keep = [j for j in range(len(A)) if j != k + 1]
                else:
                    keep = [j for j in range(len(A)) if j != k + 1]
                A, Hin, Hout = A[keep], Hin[keep], Hout[keep]
                if k < len(A) - 1:
                    d = A[k + 1] - A[k]
                    Hout[k] = A[k] + d / 3.0
                    Hin[k + 1] = A[k] + 2.0 * d / 3.0
                changed = True
                break
    m.paths[i] = Path(A, Hin, Hout, p.w, p.join, p.ml, False)
    return m


def make_straight(m: Model, i):
    m = m.copy()
    p = m.paths[i]
    a, b = p.A[0].copy(), p.A[-1].copy()
    q = Path([a, b], [a, a + (b - a) * 2 / 3], [a + (b - a) / 3, b], p.w, p.join, p.ml, False)
    m.paths[i] = q
    return m


def _reversed(p: Path):
    return Path(p.A[::-1].copy(), p.Hout[::-1].copy(), p.Hin[::-1].copy(), p.w, p.join, p.ml, False)


def _cr(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


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


def _end_frame(p: Path, e: int):
    """Oriented flat polyline (end last) and the cumulative arc length measured from the END backwards."""
    f = resample(p.flat(), 0.5)
    if e == 0:
        f = f[::-1]
    back = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]  # back[k] = arc length from end to f[::-1][k]
    return f, back


def end_geometry(p: Path, e: int):
    """(cut point c at 1.4 w from the end, reference direction t pointing to the end, hook angle in degrees, end point, dev).
    The reference direction is measured on the stretch 1.4-3.6 w from the end, i.e. outside the zone where junction artefacts live;
    the hook angle compares it with the direction of the last 0.9 w."""
    f, back = _end_frame(p, e)
    fr = f[::-1]
    if back[-1] < 2.0 * p.w:
        return None
    sel = (back >= 1.2 * p.w) & (back <= min(float(back[-1]), 3.6 * p.w))
    if sel.sum() < 4:
        sel = (back >= 0.8 * p.w) & (back <= float(back[-1]))
        if sel.sum() < 4:
            return None
    seg = fr[sel]
    c = fr[min(int(np.searchsorted(back, min(1.4 * p.w, 0.45 * float(back[-1])))), len(fr) - 1)]
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
    body = fr[(back >= 1.4 * p.w) & (back <= min(float(back[-1]), 6.0 * p.w))]
    if len(body) >= 4:
        chord = body[-1] - body[0]
        clen = float(np.linalg.norm(chord))
        if clen > 1e-6:
            u_ch = chord / clen
            perp = np.abs((body[:, 0] - body[0, 0]) * u_ch[1] - (body[:, 1] - body[0, 1]) * u_ch[0])
            if float(perp.max()) > max(0.65, 0.08 * p.w):
                return False
    sel = (back >= 3.6 * p.w) & (back <= 6.0 * p.w)
    if sel.sum() < 4:
        sel = (back >= 1.8 * p.w) & (back <= float(back[-1]))
        if sel.sum() < 4:
            return False
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
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(p)
        cand = fix_end(m_rev, i, 1, reach=reach, target=target, smooth=smooth)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
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
            if d > reach * max(wa, wb):
                continue
            vc = cb - ca
            u = vc / np.linalg.norm(vc) if np.linalg.norm(vc) > 0.5 else v / max(d, 1e-9)  # direction between the cut points (outside the hook zone)
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
    if not _straight_before_end(p, e, g[1]):
        return p
    mm = move_end(Model([p], 0, 0), 0, e, 1.4 * p.w)
    return p if mm is None else mm.paths[0]


def _clean_seam(p: Path) -> Path:
    A, Hin, Hout = list(p.A), list(p.Hin), list(p.Hout)
    changed = True
    while changed and len(A) > 2:
        changed = False
        for k in range(len(A) - 1):
            if np.linalg.norm(A[k + 1] - A[k]) < 0.25 * p.w:
                A.pop(k)
                Hin.pop(k)
                Hout.pop(k)
                changed = True
                break
    return Path(np.array(A), np.array(Hin), np.array(Hout), p.w, p.join, p.ml, p.closed)

def join_pairs(m: Model, pairs):
    from .rings import _kasa
    m = m.copy()
    dead = set()
    for (i, ei, j, ej) in pairs:
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)  # P ends at the cut
        Q = Q if ej == 0 else _reversed(Q)  # Q starts at the cut
        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        f_p, f_q = P.flat(1.0), Q.flat(1.0)
        f_all = np.vstack([f_p, f_q])
        if len(f_all) >= 12:
            cx, cy, r = _kasa(f_all)
            if 1.5 * w_merged <= r <= 50.0 * w_merged and (LP + LQ) >= 1.15 * r:
                rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r)
                if float(np.percentile(rad_err, 95)) <= 0.22 * w_merged and float(rad_err.max()) <= 0.35 * w_merged:
                    if np.linalg.norm(f_all[0] - f_all[-1]) <= 1.8 * w_merged and (LP + LQ) >= 5.0 * r:
                        A, Hin, Hout = E.ellipse_beziers(np.array([cx, cy]), r, r, 0.0)
                        m.paths[i] = Path(A, Hin, Hout, w_merged, P.join, P.ml, True)
                        dead.add(j)
                        continue
                    else:
                        th_a = float(np.arctan2(f_p[-1, 1] - cy, f_p[-1, 0] - cx))
                        th_b = float(np.arctan2(f_q[0, 1] - cy, f_q[0, 0] - cx))
                        dth = (th_b - th_a + np.pi) % (2 * np.pi) - np.pi
                        n_bridge = max(2, int(abs(dth) * r / 2.0))
                        ths = th_a + np.linspace(0.0, dth, n_bridge)[1:-1]
                        bridge = np.c_[cx + r * np.cos(ths), cy + r * np.sin(ths)] if len(ths) else np.zeros((0, 2))
                        f_comb = np.vstack([f_p, bridge, f_q])
                        ang = np.arctan2(f_comb[:, 1] - cy, f_comb[:, 0] - cx)
                        f_proj = np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang)]
                        f_proj[0], f_proj[-1] = f_p[0], f_q[-1]
                        q_arc = E._refit(f_proj, P, sigma=0.5, err=0.22)
                        if q_arc is not None:
                            q_arc.w = w_merged
                            m.paths[i] = q_arc
                            dead.add(j)
                            continue
        P = _cut_if_hooked(P, 1)
        Q = _reversed(_cut_if_hooked(_reversed(Q), 1))
        a, b = P.A[-1], Q.A[0]
        if np.linalg.norm(b - a) < 1.0:
            mid = 0.5 * (a + b)
            A = np.vstack([P.A[:-1], [mid], Q.A[1:]])
            Hin = np.vstack([P.Hin[:-1], [P.Hin[-1] + (mid - a)], Q.Hin[1:]])
            Hout = np.vstack([P.Hout[:-1], [Q.Hout[0] + (mid - b)], Q.Hout[1:]])
        else:
            A = np.vstack([P.A, Q.A])
            Hin = np.vstack([P.Hin, Q.Hin])
            Hout = np.vstack([P.Hout, Q.Hout])
            Hout[len(P.A) - 1] = a + (b - a) / 3
            Hin[len(P.A)] = a + 2 * (b - a) / 3
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.22 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            closed = True
        m.paths[i] = _clean_seam(Path(A, Hin, Hout, w_merged, P.join, P.ml, closed))
        dead.add(j)
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m
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


def find_penetrating_stubs(m: Model, D):
    """Detect open strokes that have crossed another stroke or entered a closed loop and continue past it
    into white/empty space. Returns [(i, e, cut_distance, end_xy, crossing_path_j)]."""
    hits = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        w = p.w
        tree, P, own = _others_tree(m, i)
        if tree is None:
            continue
        for e in (0, 1):
            f = p.flat(0.5)
            if e == 0:
                f = f[::-1]
            a = f[-1]
            cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
            max_k = int(np.searchsorted(cum, 3.2 * w))
            if max_k < 4:
                continue
            pts = f[::-1][:max_k]
            ds, idxs = tree.query(pts)
            for step_k in range(3, len(ds)):
                dist_to_other = ds[step_k]
                j = own[idxs[step_k]]
                if dist_to_other < 0.40 * w:
                    s = float(cum[step_k])
                    if s >= 0.55 * w:
                        test_pts = f[::-1][:step_k]
                        xs = np.clip(test_pts[:, 0].astype(int), 0, D.shape[1] - 1)
                        ys = np.clip(test_pts[:, 1].astype(int), 0, D.shape[0] - 1)
                        has_hole = float((D[ys, xs] < 0.45).mean()) >= 0.20
                        is_closed = m.paths[j].closed
                        if has_hole or is_closed:
                            hits.append((i, e, s, a.copy(), j))
                            break
    return hits


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
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(m.paths[i])
        cand = move_end(m_rev, i, 1, delta)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
    m = m.copy()
    p = m.paths[i]
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


def _make_arc_path(cx, cy, r, t0, t1, w, join="round", ml=4.0):
    c = np.array([cx, cy], float)
    span = float(t1 - t0)
    n = max(1, int(np.ceil(abs(span) / (np.pi / 2) - 1e-9)))
    step = span / n
    segs = []
    for k in range(n):
        a0, a1 = t0 + k * step, t0 + (k + 1) * step
        P0 = c + r * np.array([np.cos(a0), np.sin(a0)])
        P3 = c + r * np.array([np.cos(a1), np.sin(a1)])
        h = 4.0 / 3.0 * np.tan(step / 4.0) * r
        P1 = P0 + h * np.array([-np.sin(a0), np.cos(a0)])
        P2 = P3 - h * np.array([-np.sin(a1), np.cos(a1)])
        segs.append([P0, P1, P2, P3])
    q = Path.from_segs(segs, w, closed=False, join=join)
    q.ml = ml
    return q


def robust_arc_fit(p: Path, tol_frac=0.12):
    """Return candidate exact circular-arc replacements for open path p, tolerating up to 2.2*w junction noise at ends."""
    from .rings import _kasa
    f = resample(p.flat(), 1.0)
    if len(f) < 12:
        return []
    tol = max(0.7, tol_frac * p.w)
    cands = []
    max_trim = min(int(round(2.2 * p.w)), len(f) // 4)
    for t_start in (0, int(round(0.8 * p.w)), int(round(1.5 * p.w)), max_trim):
        for t_end in (0, int(round(0.8 * p.w)), int(round(1.5 * p.w)), max_trim):
            sub = f[t_start : len(f) - t_end] if t_end > 0 else f[t_start:]
            if len(sub) < max(10, int(0.65 * len(f))):
                continue
            cx, cy, r = _kasa(sub)
            if not (1.2 * p.w < r < 60 * p.w):
                continue
            c = np.array([cx, cy])
            dist_sub = np.linalg.norm(sub - c, axis=1)
            dev_sub = float(np.abs(dist_sub - r).max())
            if dev_sub > tol:
                continue
            ang_all = np.unwrap(np.arctan2(f[:, 1] - cy, f[:, 0] - cx))
            ang_sub = ang_all[t_start : len(f) - t_end] if t_end > 0 else ang_all[t_start:]
            span_sub = float(ang_sub[-1] - ang_sub[0])
            if abs(span_sub) < (0.6 if (t_start == 0 and t_end == 0) else 1.8) or abs(span_sub) > 6.0:
                continue
            d_sub = np.diff(ang_sub)
            if (np.sign(d_sub) == np.sign(span_sub)).mean() < 0.95:
                continue
            span_all = float(ang_all[-1] - ang_all[0])
            if np.sign(span_all) == np.sign(span_sub) and 0.6 <= abs(span_all) <= 6.1:
                q_full = _make_arc_path(cx, cy, r, ang_all[0], ang_all[-1], p.w, p.join, p.ml)
                if not (t_start == 0 and t_end == 0 and dev_sub < 0.12 and len(p.segs()) <= len(q_full.segs())):
                    cands.append((t_start + t_end + dev_sub, q_full))
            if t_start > 0 or t_end > 0:
                q_sub = _make_arc_path(cx, cy, r, ang_sub[0], ang_sub[-1], p.w, p.join, p.ml)
                cands.append((t_start + t_end + dev_sub + 5.0, q_sub))
    cands.sort(key=lambda x: x[0])
    return [q for _, q in cands[:4]]


def arc_fit(p: Path, tol_frac=0.1):
    """If open path p is (nearly) one circular arc, return the exact-arc replacement Path, else None."""
    from .rings import _kasa
    f = resample(p.flat(), 1.0)
    if len(f) < 8:
        return None
    cx, cy, r = _kasa(f)
    c = np.array([cx, cy])
    dist = np.linalg.norm(f - c, axis=1)
    if np.abs(dist - r).max() <= max(0.6, tol_frac * p.w) and (1.2 * p.w < r < 60 * p.w):
        ang = np.unwrap(np.arctan2(f[:, 1] - cy, f[:, 0] - cx))
        d = np.diff(ang)
        span = float(ang[-1] - ang[0])
        if 0.6 <= abs(span) <= 5.8 and (np.sign(d) == np.sign(span)).mean() >= 0.95:
            q = _make_arc_path(cx, cy, r, ang[0], ang[-1], p.w, p.join, p.ml)
            g = resample(q.flat(), 1.0)
            cur = resample(p.flat(), 1.0)
            k = min(len(g), len(cur))
            if np.abs(np.linalg.norm(g[:k] - c, axis=1) - r).max() > 0.1 and np.abs(dist - r).max() < 0.12:
                return None
            return q
    cands = robust_arc_fit(p, tol_frac=max(tol_frac, 0.12))
    return cands[0] if cands else None


def arc_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        q = arc_fit(p)
        if q is not None:
            out.append((i, p.A[len(p.A) // 2], q))
    return out


def _straight(c, tol=0.6):
    v = c[3] - c[0]
    L = np.linalg.norm(v)
    if L < (1.5 if tol <= 0.1 else 8):
        return False
    n = np.array([-v[1], v[0]]) / L
    return max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n)) * 0.75 < tol


def _from_segs_exact(segs, w, closed=False, join="round", ml=4.0):
    q = Path.from_segs(segs, w, closed=closed, join=join)
    q.ml = ml
    return q


def excess_ends(m: Model, ink, D, frac=0.1):
    """Open-path ends with ink in the render that the source does not have around them (thick tips, lumps).
    Returns [(excess_px, path, end, xy)] sorted by excess."""
    extra = ((ink > 0.5) & (D < 0.3)).astype(np.float32)
    H, W = extra.shape
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        tree, P, _ = _others_tree(m, i)
        r = int(max(3, 1.4 * p.w))
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            iy, ix = int(round(a[1])), int(round(a[0]))
            if 0 <= iy < H and 0 <= ix < W and D[iy, ix] > 0.45:
                if tree is not None and float(tree.query(a)[0]) <= 0.45 * p.w:
                    continue
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
    w_med = float(np.median([p.w for p in m.paths])) if m.paths else 10.0
    eff_tol = max(tol, 0.40 * w_med)
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei, a, wa = ends[x]
            j, ej, b, wb = ends[y]
            if i == j or (i, ei) in used or (j, ej) in used:
                continue
            pair_tol = max(eff_tol, 0.40 * min(wa, wb))
            if np.linalg.norm(a - b) > pair_tol or abs(wa - wb) > 0.2 * max(wa, wb):
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


def merge_corners(m: Model, pairs, joint_ends=None, D=None):
    """One stroke with a corner node instead of two strokes with two overlapping caps (the join is then drawn once, cleanly)."""
    m = m.copy()
    dead = set()
    for item in pairs:
        i, ei, j, ej = item[:4]
        Xc_override = item[4] if len(item) > 4 else None
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)
        Q = Q if ej == 0 else _reversed(Q)
        mid = (P.A[-1] + Q.A[0]) / 2
        w_max = max(P.w, Q.w)
        gP = end_geometry(P, 1)
        gQ = end_geometry(Q, 0)
        from . import joints as J_mod
        tP = gP[1] if gP is not None else J_mod._local_end_dir(P, 1)
        tQ = gQ[1] if gQ is not None else J_mod._local_end_dir(Q, 0)
        # Attempt ray intersection of incoming straight rays
        X_corner = Xc_override
        if X_corner is None:
            if gP is not None and gQ is not None:
                cP, tP_g = gP[0], gP[1]
                cQ, tQ_g = gQ[0], gQ[1]
                den = float(tP_g[0] * tQ_g[1] - tP_g[1] * tQ_g[0])
                if abs(den) >= 0.15:
                    sP = float((cQ - cP)[0] * tQ_g[1] - (cQ - cP)[1] * tQ_g[0]) / den
                    Xc = cP + sP * tP_g
                    if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                        X_corner = Xc
        if X_corner is None:
            fP, fQ = P.flat(0.5), Q.flat(0.5)
            kP = min(len(fP) - 1, max(3, int(round(1.0 * P.w))))
            kQ = min(len(fQ) - 1, max(3, int(round(1.0 * Q.w))))
            tP_f = unit(fP[-1] - fP[-1 - kP]) if len(fP) > kP else unit(P.A[-1] - P.A[0])
            tQ_f = unit(fQ[kQ] - fQ[0]) if len(fQ) > kQ else unit(Q.A[-1] - Q.A[0])
            den = float(tP_f[0] * tQ_f[1] - tP_f[1] * tQ_f[0])
            if abs(den) >= 0.15:
                sP = float((Q.A[0] - P.A[-1])[0] * tQ_f[1] - (Q.A[0] - P.A[-1])[1] * tQ_f[0]) / den
                Xc = P.A[-1] + sP * tP_f
                if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                    X_corner = Xc
        corner_pt = mid if X_corner is None else X_corner

        # Check if corner is round (fillet in raster ink)
        is_round = False
        if D is not None and X_corner is not None:
            ix = int(np.clip(round(corner_pt[0]), 0, D.shape[1] - 1))
            iy = int(np.clip(round(corner_pt[1]), 0, D.shape[0] - 1))
            bisect = tP + tQ
            nb = float(np.linalg.norm(bisect))
            if nb > 1e-4:
                u_out = bisect / nb
                tx = int(np.clip(round(corner_pt[0] + 0.25 * w_max * u_out[0]), 0, D.shape[1] - 1))
                ty = int(np.clip(round(corner_pt[1] + 0.25 * w_max * u_out[1]), 0, D.shape[0] - 1))
                if D[ty, tx] < 0.40 or D[iy, ix] < 0.70:
                    is_round = True
            elif D[iy, ix] < 0.70:
                is_round = True

        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)

        if is_round and X_corner is not None:
            R = min(1.2 * w_merged, 0.45 * min(LP, LQ))
            kappa = 0.55228475 * R
            P_start = corner_pt - R * tP
            P_end = corner_pt - R * tQ
            P_mod, Q_mod = P.copy(), Q.copy()
            if len(P_mod.A) > 2 and np.linalg.norm(P_mod.A[-2] - P_start) < 0.45 * w_merged:
                P_mod.A = P_mod.A[:-1]
                P_mod.Hin = P_mod.Hin[:-1]
                P_mod.Hout = P_mod.Hout[:-1]
            if len(Q_mod.A) > 2 and np.linalg.norm(Q_mod.A[1] - P_end) < 0.45 * w_merged:
                Q_mod.A = Q_mod.A[1:]
                Q_mod.Hin = Q_mod.Hin[1:]
                Q_mod.Hout = Q_mod.Hout[1:]
            P_mod.A[-1] = P_start.copy()
            P_mod.Hin[-1] = P_start - tP * (w_merged / 3.0)
            P_mod.Hout[-1] = P_start + tP * kappa
            Q_mod.A[0] = P_end.copy()
            Q_mod.Hin[0] = P_end + tQ * kappa
            Q_mod.Hout[0] = P_end - tQ * (w_merged / 3.0)
            A = np.vstack([P_mod.A, Q_mod.A])
            Hin = np.vstack([P_mod.Hin, Q_mod.Hin])
            Hout = np.vstack([P_mod.Hout, Q_mod.Hout])
        else:
            dP, dQ = corner_pt - P.A[-1], corner_pt - Q.A[0]
            A = np.vstack([P.A, Q.A[1:]])
            Hin = np.vstack([P.Hin, Q.Hin[1:]])
            Hout = np.vstack([P.Hout[:-1], Q.Hout])
            idx = len(P.A) - 1
            A[idx] = corner_pt
            Hin[idx] = P.Hin[-1] + dP
            Hout[idx] = Q.Hout[0] + dQ
            # Straighten incoming/outgoing handles if straight into corner
            if idx >= 1:
                segP = np.array([A[idx - 1], Hout[idx - 1], Hin[idx], A[idx]])
                if _straight(segP, 0.4) or (gP is not None and _straight_before_end(P, 1, gP[1])):
                    vP = A[idx] - A[idx - 1]
                    Hout[idx - 1] = A[idx - 1] + vP / 3.0
                    Hin[idx] = A[idx] - vP / 3.0
            if idx + 1 < len(A):
                segQ = np.array([A[idx], Hout[idx], Hin[idx + 1], A[idx + 1]])
                if _straight(segQ, 0.4) or (gQ is not None and _straight_before_end(Q, 0, gQ[1])):
                    vQ = A[idx + 1] - A[idx]
                    Hout[idx] = A[idx] + vQ / 3.0
                    Hin[idx + 1] = A[idx + 1] - vQ / 3.0

        join_type = "round" if is_round else ("miter" if (P.join == "miter" or Q.join == "miter") else P.join)
        ml_val = min(4.0, P.ml, Q.ml)  # was max(): a limit of 10 spread to merged paths and made spikes at acute joints
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.25 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            Hin[0] = Hin[-1].copy()
            Hout[-1] = Hout[0].copy()
            closed = True
        if is_round:
            m.paths[i] = Path(A, Hin, Hout, w_merged, join_type, ml_val, closed)
        else:
            m.paths[i] = _clean_seam(Path(A, Hin, Hout, w_merged, join_type, ml_val, closed))
        dead.add(j)
    if joint_ends and pairs:
        merged_i = pairs[0][0]
        p_merged = m.paths[merged_i]
        for (k_idx, e_k) in joint_ends:
            if k_idx in dead or k_idx == merged_i or k_idx >= len(m.paths):
                continue
            pk = m.paths[k_idx]
            end_pt = pk.A[0 if e_k == 0 else -1]
            f = p_merged.flat(0.25)
            k_near = int(np.argmin(np.linalg.norm(f - end_pt, axis=1)))
            pt_on, d_on = f[k_near], float(np.linalg.norm(f[k_near] - end_pt))
            if d_on <= 1.5 * p_merged.w:
                from . import joints as J_mod
                J_mod._set_end(pk, e_k, pt_on)
                ak = J_mod.insert_anchor(p_merged, pt_on)
                J_mod._set_end(pk, e_k, p_merged.A[ak])
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m


def _rotate_closed_to_turn(p: Path) -> Path:
    if not p.closed or len(p.A) <= 5:
        return p
    segs = p.segs()
    n = len(segs)
    best_k, best_turn = 0, -1.0
    for k in range(n):
        s_prev = segs[(k - 1) % n]
        s_curr = segs[k]
        d_in = unit(s_prev[3] - s_prev[0])
        d_out = unit(s_curr[3] - s_curr[0])
        turn = 1.0 - float(d_in @ d_out)
        if turn > best_turn:
            best_turn = turn
            best_k = k
    if best_k == 0 or best_turn < 0.005:
        return p
    new_segs = segs[best_k:] + segs[:best_k]
    return _from_segs_exact(new_segs, p.w, closed=True, join=p.join, ml=p.ml)


def _collapse_pass(p: Path, max_dev: float, ang_deg: float, snap_line: bool = False) -> Path:
    q = _rotate_closed_to_turn(p) if p.closed else p
    segs = q.segs()
    n = len(segs)
    if n < 2:
        return p
    cos_lim = np.cos(np.radians(ang_deg))
    cos_short = np.cos(np.radians(max(ang_deg, 18.0)))

    def fit_run(k0, k1):
        A0 = segs[k0][0]
        A1 = segs[k1 - 1][3]
        v = A1 - A0
        L = float(np.linalg.norm(v))
        if L < max(4.0, 0.9 * q.w):
            return None
        u = v / L
        n_vec = np.array([-u[1], u[0]])
        all_pts, weights = [], []
        for k in range(k0, k1):
            c = segs[k]
            sv = c[3] - c[0]
            sL = float(np.linalg.norm(sv))
            if sL > 1e-4:
                su = sv / sL
                lim = cos_lim if sL >= 0.7 * q.w else cos_short
                if su @ u < lim:
                    return None
            pts = bez(c, np.linspace(0, 1, 9))
            dev = np.abs((pts - A0) @ n_vec).max()
            if dev > max_dev:
                return None
            proj = (pts - A0) @ u
            if np.any(np.diff(proj) < -0.25):
                return None
            all_pts.append(pts)
            weights.append(np.full(len(pts), max(sL, 1.0)))
        if not snap_line:
            return A0.copy(), A1.copy()
        P = np.vstack(all_pts)
        W = np.concatenate(weights)
        W /= W.sum()
        mean = (P * W[:, None]).sum(0)
        _, _, vt = np.linalg.svd((P - mean) * np.sqrt(W[:, None]))
        d = vt[0]
        if d @ u < 0:
            d = -d
        if abs(d[1]) < np.sin(np.radians(1.5)):
            d = np.array([np.sign(d[0]), 0.0])
        elif abs(d[0]) < np.sin(np.radians(1.5)):
            d = np.array([0.0, np.sign(d[1])])
        P0 = mean + ((A0 - mean) @ d) * d
        P1 = mean + ((A1 - mean) @ d) * d
        return P0, P1

    new_segs, is_merged = [], []
    i = 0
    changed = False
    while i < n:
        best_j = i + 1
        best_end = None
        for j in range(i + 2, n + 1):
            res = fit_run(i, j)
            if res is not None:
                best_j = j
                best_end = res
        if best_j > i + 1:
            P0, P1 = best_end
            new_segs.append(np.array([P0, P0 + (P1 - P0) / 3.0, P0 + 2.0 * (P1 - P0) / 3.0, P1]))
            is_merged.append(True)
            i = best_j
            changed = True
        else:
            new_segs.append(segs[i].copy())
            is_merged.append(False)
            i += 1
    if not changed:
        return p
    m_len = len(new_segs)
    for k in range(m_len if q.closed else m_len - 1):
        k_next = (k + 1) % m_len
        s1, s2 = new_segs[k], new_segs[k_next]
        if np.linalg.norm(s1[3] - s2[0]) > 1e-4:
            d1 = unit(s1[3] - s1[0])
            d2 = unit(s2[3] - s2[0])
            C = line_inter(s1[0], d1, s2[0], d2) if (is_merged[k] and is_merged[k_next]) else None
            if C is not None and np.linalg.norm(C - s1[3]) < 0.5 * q.w:
                pt = C
            else:
                pt = s1[3] if is_merged[k] and not is_merged[k_next] else (s2[0] if is_merged[k_next] else 0.5 * (s1[3] + s2[0]))
            s1[3] = pt.copy()
            s2[0] = pt.copy()
            if is_merged[k]:
                s1[1] = s1[0] + (s1[3] - s1[0]) / 3.0
                s1[2] = s1[0] + 2.0 * (s1[3] - s1[0]) / 3.0
            if is_merged[k_next]:
                s2[1] = s2[0] + (s2[3] - s2[0]) / 3.0
                s2[2] = s2[0] + 2.0 * (s2[3] - s2[0]) / 3.0
    return _from_segs_exact(new_segs, q.w, closed=q.closed, join=q.join, ml=q.ml)


def collapse_straight_runs(p: Path):
    q = _collapse_pass(p, max_dev=0.22, ang_deg=3.5, snap_line=False)
    q2 = _collapse_pass(q, max_dev=max(0.5, 0.11 * p.w), ang_deg=12.0, snap_line=True)
    return q2, q


def _fit_single_cubic(pts, t0=None, t1=None):
    from scipy.spatial import cKDTree
    P0, P3 = pts[0].copy(), pts[-1].copy()
    seg_d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    L = float(seg_d.sum())
    if L < 1e-4:
        return None, 1e9
    u = np.r_[0.0, np.cumsum(seg_d) / L]
    for _ in range(2):
        mt = 1.0 - u
        b0 = mt ** 3
        b1 = 3 * (mt ** 2) * u
        b2 = 3 * mt * (u ** 2)
        b3 = u ** 3
        rhs = pts - b0[:, None] * P0 - b3[:, None] * P3
        if t0 is not None and t1 is not None:
            M = np.zeros((2, 2))
            v = np.zeros(2)
            c1 = b1[:, None] * t0[None, :]
            c2 = -b2[:, None] * t1[None, :]
            M[0, 0] = (c1 * c1).sum()
            M[0, 1] = M[1, 0] = (c1 * c2).sum()
            M[1, 1] = (c2 * c2).sum()
            v[0] = (c1 * rhs).sum()
            v[1] = (c2 * rhs).sum()
            try:
                a1, a2 = np.linalg.solve(M + 1e-9 * np.eye(2), v)
            except Exception:
                a1 = a2 = L / 3.0
            a1 = float(np.clip(a1, 0.05 * L, 0.85 * L))
            a2 = float(np.clip(a2, 0.05 * L, 0.85 * L))
            P1 = P0 + a1 * t0
            P2 = P3 - a2 * t1
        else:
            A_mat = np.c_[b1, b2]
            sol, *_ = np.linalg.lstsq(A_mat, rhs, rcond=None)
            P1, P2 = sol[0], sol[1]
        c = np.array([P0, P1, P2, P3])
        Q = bez(c, u)
        Qp = 3 * ((1 - u)[:, None] ** 2 * (P1 - P0) + 2 * (1 - u)[:, None] * u[:, None] * (P2 - P1) + (u[:, None] ** 2) * (P3 - P2))
        num = ((Q - pts) * Qp).sum(1)
        den = (Qp * Qp).sum(1) + 1e-9
        u = np.clip(u - num / den, 0.0, 1.0)
    c = np.array([P0, P1, P2, P3])
    dense = bez(c, np.linspace(0, 1, max(24, int(L))))
    err = float(cKDTree(dense).query(pts)[0].max())
    return c, err


def simplify_path_segments(st, pi: int, doctor, ink_of, start_s: float, drift_cap: float, sites: list, skip=()):
    """Collapse redundant anchors in st['model'].paths[pi]: collinear straight pairs and G1-smooth single-cubic pairs."""
    if "density" in skip or pi >= len(st["model"].paths):
        return
    m = st["model"]
    p0 = _rotate_closed_to_turn(m.paths[pi]) if m.paths[pi].closed else m.paths[pi]
    if p0 is not m.paths[pi]:
        m = m.copy()
        m.paths[pi] = p0
        st["model"] = m

    tried_bad = set()
    while True:
        m = st["model"]
        p = m.paths[pi]
        segs = p.segs()
        n = len(segs)
        if n < 2:
            break
        max_dev_str = max(0.65, 0.12 * p.w)
        cos_lim = np.cos(np.radians(14.0))
        cos_short = np.cos(np.radians(22.0))
        num_pairs = n if p.closed else n - 1
        best = None
        for k in range(num_pairs):
            k2 = (k + 1) % n
            s1, s2 = segs[k], segs[k2]
            A0, AM, A1 = s1[0], s1[3], s2[3]
            key = (round(float(AM[0]), 1), round(float(AM[1]), 1), n)
            if key in tried_bad:
                continue
            v = A1 - A0
            L = float(np.linalg.norm(v))
            if L < max(3.5, 0.6 * p.w):
                continue
            u = v / L
            n_vec = np.array([-u[1], u[0]])
            v1, v2 = s1[3] - s1[0], s2[3] - s2[0]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 < 1e-4 or L2 < 1e-4:
                continue
            pts1 = bez(s1, np.linspace(0, 1, 13))
            pts2 = bez(s2, np.linspace(0, 1, 13))
            pts = np.vstack([pts1, pts2[1:]])
            dev_str = float(np.abs((pts - A0) @ n_vec).max())
            lim1 = cos_lim if L1 >= 0.7 * p.w else cos_short
            lim2 = cos_lim if L2 >= 0.7 * p.w else cos_short

            cands_seg = []
            if (v1 / L1) @ u >= lim1 and (v2 / L2) @ u >= lim2 and dev_str <= max_dev_str and not np.any(np.diff((pts - A0) @ u) < -0.2):
                cands_seg.append((dev_str, np.array([A0, A0 + v / 3.0, A0 + 2.0 * v / 3.0, A1])))
            tin = unit(s1[3] - s1[2]) if np.linalg.norm(s1[3] - s1[2]) > 0.2 else v1 / L1
            tout = unit(s2[1] - s2[0]) if np.linalg.norm(s2[1] - s2[0]) > 0.2 else v2 / L2
            if tin @ tout >= np.cos(np.radians(18.0)) and (v1 / L1) @ (v2 / L2) >= np.cos(np.radians(38.0)):
                t0 = unit(s1[1] - s1[0]) if np.linalg.norm(s1[1] - s1[0]) > 0.2 else v1 / L1
                t1 = unit(s2[3] - s2[2]) if np.linalg.norm(s2[3] - s2[2]) > 0.2 else v2 / L2
                c_fit, err_c = _fit_single_cubic(pts, t0, t1)
                if c_fit is not None and err_c <= max(0.35, 0.04 * p.w):
                    cands_seg.append((err_c + 0.05, c_fit))
            if cands_seg:
                score = min(c[0] for c in cands_seg)
                if best is None or score < best[0]:
                    best = (score, k, k2, key, AM.copy(), [c[1] for c in cands_seg])
        if best is None:
            break
        score, k, k2, key, AM, seg_list = best
        accepted = False
        for merged_seg in seg_list:
            if k2 > k:
                new_segs = segs[:k] + [merged_seg] + segs[k2 + 1:]
            else:
                new_segs = [merged_seg] + segs[1:k]
            q_cand = _from_segs_exact(new_segs, p.w, closed=p.closed, join=p.join, ml=p.ml)
            cand_m = m.copy()
            cand_m.paths[pi] = q_cand
            ink2 = ink_of(cand_m)
            s_new = doctor.soft(ink2)
            t2 = _topo(cand_m)
            tol = max(3.5, 0.005 * st["cur"]) if score < 0.22 else max(2.0, 0.003 * st["cur"])
            if s_new <= st["cur"] + tol and t2 <= st["topo"] and (s_new - start_s) <= drift_cap:
                st.update(model=cand_m, ink=ink2, cur=s_new, topo=t2)
                sites.append(dict(kind="density", x=float(AM[0]), y=float(AM[1]), fixed=True))
                accepted = True
                break
        if not accepted:
            tried_bad.add(key)


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


def acute_apex_candidates(m: Model, D, w_fallback=10.0):
    """Detect acute corners (interior angle < 95 deg) where a round stroke-join stops short of the raster tip."""
    H, W = D.shape
    cands = []
    for pi, p in enumerate(m.paths):
        A = p.A
        N = len(A)
        if N < 3:
            continue
        check_indices = range(N) if p.closed else range(1, N - 1)
        for j in check_indices:
            prev_idx = (j - 1) % (N - 1) if p.closed else (j - 1)
            next_idx = (j + 1) % (N - 1) if p.closed else (j + 1)
            v_in = A[j] - A[prev_idx]
            v_out = A[next_idx] - A[j]
            len_in = float(np.linalg.norm(v_in))
            len_out = float(np.linalg.norm(v_out))
            if len_in < 1.0 or len_out < 1.0:
                continue
            u_in = v_in / len_in
            u_out = v_out / len_out
            cos_turn = float(u_in @ u_out)
            if -cos_turn > -0.1:  # interior angle < 95 deg
                bisect = u_in - u_out
                b_norm = float(np.linalg.norm(bisect))
                if b_norm < 1e-4:
                    continue
                u_bisect = bisect / b_norm

                w_eff = p.w or w_fallback
                r = int(round(1.5 * w_eff))
                y0, y1 = max(0, int(A[j][1] - r)), min(H, int(A[j][1] + r + 1))
                x0, x1 = max(0, int(A[j][0] - r)), min(W, int(A[j][0] + r + 1))
                ys, xs = np.where(D[y0:y1, x0:x1] > 0.4)
                if len(ys) == 0:
                    continue
                pts = np.column_stack([x0 + xs, y0 + ys])
                projs = (pts - A[j]) @ u_bisect
                best_idx = projs.argmax()
                p_tip = pts[best_idx].astype(float)

                a_target = p_tip - 0.48 * w_eff * u_bisect
                delta = a_target - A[j]
                d_len = float(np.linalg.norm(delta))
                if d_len < 0.5 or d_len > 0.7 * w_eff:
                    shifts = [u_bisect * s for s in [1.5, 3.0, 4.5] if s < 0.55 * w_eff]
                else:
                    shifts = [delta * frac for frac in [0.4, 0.7, 1.0]] + [u_bisect * s for s in [1.5, 3.0, 4.5] if s < 0.55 * w_eff]

                for sh in shifts:
                    cand = m.copy()
                    cp = cand.paths[pi]
                    cp.A[j] = A[j] + sh
                    cp.Hin[j] = cp.Hin[j] + sh
                    cp.Hout[j] = cp.Hout[j] + sh
                    if p.closed and (j == 0 or j == N - 1):
                        cp.A[0] = cp.A[j].copy()
                        cp.A[-1] = cp.A[j].copy()
                    cands.append((cand, (float(A[j][0]), float(A[j][1]))))
    return cands


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
        if not ok and s2 <= lim and (s2 - start) <= drift_cap and t2 > st["topo"]:
            cw = T.weld_all(cand)
            tw = _topo(cw)
            if tw <= st["topo"]:
                ink_w = ink_of(cw)
                sw = doctor.soft(ink_w)
                if sw <= lim and (sw - start) <= drift_cap:
                    cand, ink2, s2, t2, ok = cw, ink_w, sw, tw, True
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
    for _ in range(3):
        if not time_ok():
            break
        pairs = collinear_pairs(st["model"], D)
        if not pairs:
            break
        mid = np.mean([st["model"].paths[p[0]].A[0 if p[1] == 0 else -1] for p in pairs], axis=0)
        if attempt(join_pairs(st["model"], pairs), "join", mid):
            continue
        sites.pop()
        any_ok = False
        for pr in pairs[:20]:
            if not time_ok():
                break
            n_ = len(st["model"].paths)
            if max(pr[0], pr[2]) < n_:
                if attempt(join_pairs(st["model"], [pr]), "join", st["model"].paths[pr[0]].A[0 if pr[1] == 0 else -1]):
                    any_ok = True
        if not any_ok:
            break
    # 0b. wobbly strokes that are really one straight line
    for i, xy in wobbly_straights(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(make_straight(st["model"], i), "straighten", xy, tol=max(3.5, 0.006 * st["cur"]))
    # 0c. Z-folds / switchbacks
    for i, xy in z_fold_paths(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            for zcand in fix_z_fold_cands(st["model"], i):
                if attempt(zcand, "handles", xy, tol=max(12.0, 0.02 * st["cur"])):
                    break
                sites.pop()
    # 1. handles that loop / overshoot
    for i, xy in sorted(bad_handle_paths(st["model"]), key=lambda t: -t[0]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(redraw_path(st["model"], i), "handles", xy)
    # 1b. apex overshoots and crevice tongues
    for i in range(len(st["model"].paths)):
        if i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        p_pruned = T.prune_apex_overshoot(p)
        if len(p_pruned.A) < len(p.A):
            cand = st["model"].copy()
            cand.paths[i] = p_pruned
            xy = p.A[len(p.A) // 2].copy()
            if not attempt(cand, "density", xy):
                sites.pop()
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
    # 4b2. penetrating stubs: open strokes that cross another stroke and overshoot past it
    for i, e, dl, xy, j in find_penetrating_stubs(st["model"], D)[:25]:
        if not time_ok():
            break
        if i >= len(st["model"].paths):
            continue
        cand = move_end(st["model"], i, e, dl)
        if cand is not None:
            attempt(cand, "caps", xy, improve=True)
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
        c1 = merge_corners(st["model"], cp, D=D)
        if not attempt(c1, "corners", st["model"].paths[cp[0][0]].A[0]):
            sites.pop()
            for pr in cp[:15]:
                if not time_ok():
                    break
                if max(pr[0], pr[2]) < len(st["model"].paths):
                    attempt(merge_corners(st["model"], [pr], D=D), "corners", st["model"].paths[pr[0]].A[0])
    # 4c. round shapes: wobbly circular arcs / near-circles become exact circles and arcs
    for i in range(len(st["model"].paths)):
        if not time_ok() or i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        if p.closed:
            continue
        q0 = arc_fit(p)
        cands_arc = ([q0] if q0 is not None else []) + [q for q in robust_arc_fit(p) if q0 is None or len(q.A) != len(q0.A) or not np.allclose(q.A, q0.A, atol=0.1)]
        if cands_arc:
            xy = p.A[len(p.A) // 2].copy()
            accepted_arc = False
            for q in cands_arc[:4]:
                c1 = st["model"].copy()
                c1.paths[i] = q
                if attempt(c1, "arcs", xy, tol=max(3.0, 0.01 * st["cur"])):
                    accepted_arc = True
                    break
                sites.pop()
            if not accepted_arc:
                sites.append(dict(kind="arcs", x=float(xy[0]), y=float(xy[1]), fixed=False))
    for i, p in enumerate(list(st["model"].paths)):
        if i < len(st["model"].paths) and p.closed and len(p.segs()) >= 3:
            c1 = E.circle(st["model"], i, max_dev=max(0.9, 0.12 * p.w), robust=True)
            q = c1.paths[i]
            if len(q.segs()) == 4 and (len(p.segs()) != 4 or not np.allclose(q.A, p.A, atol=0.05)):
                attempt(c1, "circles", p.A.mean(0), tol=max(3.0, 0.01 * st["cur"], 0.025 * p.length()))
    # 4d. collapse multi-node straight runs and redundant intermediate nodes on straight/smooth segments
    for i in range(len(st["model"].paths)):
        if i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        if p.closed and len(p.segs()) == 4 and E.fit_ellipse(p.flat()) is not None:
            continue
        q2, q1 = collapse_straight_runs(p)
        for q_cand in (q2, q1):
            if len(q_cand.A) < len(st["model"].paths[i].A):
                cand = st["model"].copy()
                cand.paths[i] = q_cand
                xy = p.A[len(p.A) // 2].copy()
                if attempt(cand, "density", xy):
                    break
                sites.pop()
        if time_ok():
            simplify_path_segments(st, i, doctor, ink_of, start, drift_cap, sites, skip=skip)
    # 5. specks
    for i, xy in sorted(speck_paths(st["model"]), key=lambda t: -t[0]):
        if i < len(st["model"].paths):
            attempt(E.remove_path(st["model"], i), "specks", xy, tol=0.6 * w)
    # 5b. acute apexes: round joins on acute corners that fall short of the raster tip are extended along the bisector to meet the true raster apex
    if "apexes" not in skip:
        for cand, xy in acute_apex_candidates(st["model"], D, w_fallback=w)[:30]:
            if not time_ok():
                break
            attempt(cand, "apex", xy, improve=True)
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
    # 7. final junction Z-fold & straightness polish
    for i, xy in z_fold_paths(st["model"]):
        if i < len(st["model"].paths):
            for zcand in fix_z_fold_cands(st["model"], i):
                if attempt(zcand, "handles", xy, tol=max(12.0, 0.025 * st["cur"])):
                    break
                sites.pop()
    for i, xy in wobbly_straights(st["model"]):
        if i < len(st["model"].paths):
            attempt(make_straight(st["model"], i), "straighten", xy, tol=max(12.0, 0.025 * st["cur"]))
    st["model"] = T.prune_all_apexes(st["model"])
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
