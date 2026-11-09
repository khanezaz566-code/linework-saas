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
    target = np.asarray(target, float)
    if e == 0:
        p_old = p.A[0].copy()
        d = target - p_old
        p_other = p.A[1]
        chord_old = p_other - p_old
        L_old = float(np.linalg.norm(chord_old))
        was_straight = True
        if L_old > 1e-4:
            u = chord_old / L_old
            perp = np.array([-u[1], u[0]])
            dev0 = float((p.Hout[0] - p_old) @ perp)
            dev1 = float((p.Hin[1] - p_old) @ perp)
            tol_str = max(0.32, 0.04 * p.w)
            if abs(dev0) > tol_str or abs(dev1) > tol_str:
                was_straight = False
            elif len(p.A) >= 3 and L_old < 2.2 * p.w:
                v_next = p.A[2] - p.A[1]
                L_next = float(np.linalg.norm(v_next))
                if L_next > 1e-4:
                    u_next = v_next / L_next
                    perp_n = np.array([-u_next[1], u_next[0]])
                    if max(abs(float((p.Hout[1] - p.A[1]) @ perp_n)), abs(float((p.Hin[2] - p.A[1]) @ perp_n))) > tol_str:
                        was_straight = False
        p.A[0] = target.copy()
        if was_straight:
            chord = p_other - target
            p.Hin[0] = target.copy()
            p.Hout[0] = target + chord / 3.0
            p.Hin[1] = target + 2.0 * chord / 3.0
            if len(p.A) == 2:
                p.Hout[1] = p_other.copy()
        else:
            p.Hout[0] = p.Hout[0] + d
            p.Hin[0] = target.copy()
    else:
        p_old = p.A[-1].copy()
        d = target - p_old
        p_other = p.A[-2]
        chord_old = p_old - p_other
        L_old = float(np.linalg.norm(chord_old))
        was_straight = True
        if L_old > 1e-4:
            u = chord_old / L_old
            perp = np.array([-u[1], u[0]])
            dev0 = float((p.Hout[-2] - p_other) @ perp)
            dev1 = float((p.Hin[-1] - p_other) @ perp)
            tol_str = max(0.32, 0.04 * p.w)
            if abs(dev0) > tol_str or abs(dev1) > tol_str:
                was_straight = False
            elif len(p.A) >= 3 and L_old < 2.2 * p.w:
                v_prev = p.A[-2] - p.A[-3]
                L_prev = float(np.linalg.norm(v_prev))
                if L_prev > 1e-4:
                    u_prev = v_prev / L_prev
                    perp_p = np.array([-u_prev[1], u_prev[0]])
                    if max(abs(float((p.Hout[-3] - p.A[-3]) @ perp_p)), abs(float((p.Hin[-2] - p.A[-3]) @ perp_p))) > tol_str:
                        was_straight = False
        p.A[-1] = target.copy()
        if was_straight:
            chord = target - p_other
            p.Hout[-2] = p_other + chord / 3.0
            p.Hin[-1] = p_other + 2.0 * chord / 3.0
            p.Hout[-1] = target.copy()
            if len(p.A) == 2:
                p.Hin[0] = p_other.copy()
        else:
            p.Hin[-1] = p.Hin[-1] + d
            p.Hout[-1] = target.copy()


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
    polys = [p.flat(1.0) for p in m.paths]
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
        cross_tol = max(0.6, 0.08 * w)
        if d > min_gap and any(
            k != i and k != j and len(polys[k]) > 0
            and float(np.min(np.linalg.norm(polys[k] - p1, axis=1))) <= cross_tol
            and float(np.min(np.linalg.norm(polys[k] - p2, axis=1))) <= cross_tol
            for k in range(len(polys))
        ):
            continue
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
    # T-junctions: free ends that stop short of (or inside) another stroke along their outward trajectory
    for a, (i, e, p1, t1) in enumerate(ends):
        if a in used:
            continue
        w = m.paths[i].w
        best = None
        perp_t1 = np.array([-t1[1], t1[0]])
        for j, f in enumerate(polys):
            if j == i or len(f) < 2:
                continue
            dd = np.linalg.norm(f - p1, axis=1)
            k = int(dd.argmin())
            d_min = float(dd[k])
            if d_min > r_t * w:
                continue
            target_pt = f[k]
            # Prefer forward ray intersection along t1 when available
            vecs = f - p1
            s_ray = vecs @ t1
            p_ray = np.abs(vecs @ perp_t1)
            m_ray = (s_ray >= -0.15 * w) & (s_ray <= r_t * w) & (p_ray <= 0.38 * w)
            if m_ray.any():
                idx_r = int(np.where(m_ray)[0][np.argmin(p_ray[m_ray] + 0.25 * np.abs(s_ray[m_ray]))])
                target_pt = f[idx_r]
                k = idx_r
                d_min = float(np.linalg.norm(target_pt - p1))
            elif d_min > 0.22 * w:
                # Never yank a free spiral or curve end sideways onto an adjacent parallel stroke
                u_step = (target_pt - p1) / max(d_min, 1e-6)
                if float(u_step @ t1) < np.cos(np.radians(42.0)):
                    continue
            tau_j = unit(f[min(k + 1, len(f) - 1)] - f[max(k - 1, 0)])
            if d_min > 0.18 * w and abs(float(t1 @ tau_j)) > np.cos(np.radians(18.0)):
                continue
            if best is None or d_min < best[0]:
                best = (d_min, j, target_pt)
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


def _turn(p: Path, k: int) -> float:
    """Signed turning angle (deg) at anchor k."""
    n = len(p.A)
    if n < 3:
        return 0.0
    if p.closed:
        N = n - 1
        if N < 2:
            return 0.0
        k_mod = k % N
        din = p.A[k_mod] - p.Hin[k_mod]
        if np.linalg.norm(din) < 1e-6:
            prev_idx = (k_mod - 1) % N
            din = p.A[k_mod] - p.A[prev_idx]
        dout = p.Hout[k_mod] - p.A[k_mod]
        if np.linalg.norm(dout) < 1e-6:
            next_idx = (k_mod + 1) % N
            dout = p.A[next_idx] - p.A[k_mod]
    else:
        k_clamped = max(0, min(n - 1, k))
        din = p.A[k_clamped] - p.Hin[k_clamped]
        if np.linalg.norm(din) < 1e-6:
            prev_idx = max(0, k_clamped - 1)
            din = p.A[k_clamped] - p.A[prev_idx]
            if np.linalg.norm(din) < 1e-6 and k_clamped + 1 < n:
                din = p.A[k_clamped + 1] - p.A[k_clamped]
        dout = p.Hout[k_clamped] - p.A[k_clamped]
        if np.linalg.norm(dout) < 1e-6:
            next_idx = min(n - 1, k_clamped + 1)
            dout = p.A[next_idx] - p.A[k_clamped]
            if np.linalg.norm(dout) < 1e-6 and k_clamped - 1 >= 0:
                dout = p.A[k_clamped] - p.A[k_clamped - 1]

    norm_in = float(np.linalg.norm(din))
    norm_out = float(np.linalg.norm(dout))
    if norm_in < 1e-6 or norm_out < 1e-6:
        return 0.0
    a, b = din / norm_in, dout / norm_out
    return float(np.degrees(np.arctan2(a[0] * b[1] - a[1] * b[0], a @ b)))


def _is_step(p: Path, k: int, frac: float) -> bool:
    """Tiny segment k->k+1 that is a corner chamfer or a zig-zag step rather than part of a smooth curve."""
    n = len(p.A)
    if n < 2:
        return False
    if p.closed:
        N = n - 1
        if N < 3:
            return False
        k0 = k % N
        k1 = (k + 1) % N
    else:
        if k + 1 >= n:
            return False
        k0 = k
        k1 = k + 1
    if np.linalg.norm(p.A[k1] - p.A[k0]) >= frac * p.w:
        return False
    t1, t2 = _turn(p, k0), _turn(p, k1)
    if t1 * t2 < 0:
        return min(abs(t1), abs(t2)) > 15.0
    return abs(t1) > 25.0 and abs(t2) > 25.0 and abs(t1 + t2) > 50.0


def merge_nodes(m: Model, i, frac=0.85):
    """Collapse chamfer/zig-zag steps at a corner into one clean anchor."""
    m = m.copy()
    p = m.paths[i]
    changed = True
    while changed and len(p.A) > (4 if p.closed else 3):
        changed = False
        limit = len(p.A) - 1 if p.closed else len(p.A) - 2
        for k in range(0 if p.closed else 1, limit):
            if not _is_step(p, k, frac):
                continue
            k_prev = (k - 1) % (len(p.A) - 1) if p.closed else k - 1
            k_next = (k + 2) % (len(p.A) - 1) if p.closed else k + 2
            M = (p.A[k] + p.A[k + 1]) / 2
            tin = unit(p.A[k] - p.Hin[k]) if np.linalg.norm(p.A[k] - p.Hin[k]) > 1e-6 else unit(p.A[k] - p.A[k_prev])
            tout = unit(p.Hout[k + 1] - p.A[k + 1]) if np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]) > 1e-6 else unit(p.A[k_next] - p.A[k + 1])
            P = M
            cr = tin[0] * tout[1] - tin[1] * tout[0]
            if abs(cr) > 0.2:
                try:
                    s = np.linalg.solve(np.array([[tin[0], -tout[0]], [tin[1], -tout[1]]]), p.A[k + 1] - p.A[k])
                    cand = p.A[k] + s[0] * tin
                    if np.linalg.norm(cand - M) < 0.8 * p.w:
                        P = cand
                except Exception:
                    pass
            lin = max(np.linalg.norm(p.A[k] - p.Hin[k]), 1.0)
            lout = max(np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]), 1.0)
            if not p.closed:
                p.A = np.vstack([p.A[:k], P, p.A[k + 2:]])
                p.Hin = np.vstack([p.Hin[:k], P - tin * lin, p.Hin[k + 2:]])
                p.Hout = np.vstack([p.Hout[:k], P + tout * lout, p.Hout[k + 2:]])
            else:
                p.A = np.delete(p.A, k + 1, axis=0)
                p.Hin = np.delete(p.Hin, k + 1, axis=0)
                p.Hout = np.delete(p.Hout, k + 1, axis=0)
                p.A[k] = P
                p.Hin[k] = P - tin * lin
                p.Hout[k] = P + tout * lout
                p.A[-1] = p.A[0]
                p.Hin[-1] = p.Hin[0]
                p.Hout[-1] = p.Hout[0]
            changed = True
            break
    return m


def find_notches(m: Model, frac=0.85):
    out = []
    for i, p in enumerate(m.paths):
        min_n = 5 if p.closed else 4
        if len(p.A) < min_n:
            continue
        limit = len(p.A) - 1 if p.closed else len(p.A) - 2
        start_k = 0 if p.closed else 1
        if any(_is_step(p, k, frac) for k in range(start_k, limit)):
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


def _is_junction_end(m: Model, i: int, e: int) -> bool:
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return False
    a = p.A[0] if e == 0 else p.A[-1]
    b = p.A[1] if e == 0 else p.A[-2]
    d_a, d_b = np.inf, np.inf
    for j, q in enumerate(m.paths):
        if j == i:
            continue
        f = q.flat(1.0)
        da = float(np.linalg.norm(f - a, axis=1).min())
        db = float(np.linalg.norm(f - b, axis=1).min())
        if da < d_a:
            d_a = da
        if db < d_b:
            d_b = db
    if d_a <= 0.25 * p.w:
        return True
    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)


def find_spurs(m: Model):
    return [(i, e) for i, p in enumerate(m.paths) for e in (0, 1) if _spur(p, e) and not _is_junction_end(m, i, e)]


def trim_tail(m: Model, i, e):
    m = m.copy()
    p = m.paths[i]
    if not _spur(p, e) or _is_junction_end(m, i, e):
        return m
    if e == 0:
        p.A, p.Hin, p.Hout = p.A[1:], p.Hin[1:], p.Hout[1:]
        p.Hin[0] = p.A[0]
    else:
        p.A, p.Hin, p.Hout = p.A[:-1], p.Hin[:-1], p.Hout[:-1]
        p.Hout[-1] = p.A[-1]
    return m


def prune_apex_overshoot(p: Path) -> Path:
    """Drop false overshoot tongues at acute V-apexes / crevices / notches where medial axis
    doubles back by > 115 deg within < 0.45 * w."""
    n = len(p.A)
    if n < 4:
        return p
    w = p.w
    A = p.A.copy()
    Hin = p.Hin.copy()
    Hout = p.Hout.copy()

    changed = True
    while changed and len(A) >= (5 if p.closed else 4):
        changed = False
        N = len(A) - 1 if p.closed else len(A)
        for k in range(N):
            prev_idx = (k - 1) % N if p.closed else k - 1
            next_idx = (k + 1) % N if p.closed else k + 1
            if not p.closed and (prev_idx < 0 or next_idx >= len(A)):
                continue
            v_in = A[k] - A[prev_idx]
            v_out = A[next_idx] - A[k]
            l_in = float(np.linalg.norm(v_in))
            l_out = float(np.linalg.norm(v_out))
            if l_in < 1e-4 or l_out < 1e-4:
                continue
            u_in = v_in / l_in
            u_out = v_out / l_out
            cos_turn = float(u_in @ u_out)

            # Double back by > 115 degrees with short segment (< 0.45 * w)
            if cos_turn < -0.40 and (l_in < 0.45 * w or l_out < 0.45 * w):
                p_prev = A[prev_idx]
                p_next = A[next_idx]
                chord = p_next - p_prev
                L_chord = float(np.linalg.norm(chord))
                if L_chord > 1e-4:
                    if (Hout[prev_idx] - p_prev) @ (A[k] - p_prev) > 0:
                        Hout[prev_idx] = p_prev + (chord / 3.0)
                    if (Hin[next_idx] - p_next) @ (A[k] - p_next) > 0:
                        Hin[next_idx] = p_next - (chord / 3.0)

                A = np.delete(A, k, axis=0)
                Hin = np.delete(Hin, k, axis=0)
                Hout = np.delete(Hout, k, axis=0)
                if p.closed:
                    if k == 0 or k == N:
                        A[-1] = A[0]
                        Hin[-1] = Hin[0]
                        Hout[-1] = Hout[0]
                changed = True
                break

    # Drop adjacent duplicate anchors closer than max(0.4, 0.22 * w)
    N = len(A) - 1 if p.closed else len(A)
    keep = [0]
    for k in range(1, N):
        if np.linalg.norm(A[k] - A[keep[-1]]) < max(0.4, 0.22 * w):
            continue
        keep.append(k)
    if p.closed:
        if np.linalg.norm(A[keep[-1]] - A[0]) < max(0.4, 0.22 * w) and len(keep) > 3:
            keep.pop()
        keep.append(len(A) - 1)
    else:
        if (len(A) - 1) not in keep:
            keep.append(len(A) - 1)

    if len(keep) != len(A):
        A = A[keep]
        Hin = Hin[keep]
        Hout = Hout[keep]
        if p.closed:
            A[-1] = A[0]
            Hin[-1] = Hin[0]
            Hout[-1] = Hout[0]

    return Path(A, Hin, Hout, p.w, p.join, p.ml, p.closed)


def prune_all_apexes(m: Model) -> Model:
    """Apply prune_apex_overshoot to all paths in the model."""
    m = m.copy()
    for i in range(len(m.paths)):
        m.paths[i] = prune_apex_overshoot(m.paths[i])
    return m
