"""Join engine: every joint is built carefully, then a Join Checker inspects each joint on its own; a joint that fails is repaired with one of
three tools (named after the vector-editor tools they imitate) and re-checked.  Only a joint that passes (or at least fails fewer checks) is kept,
and every repair is also verified against the source (match must not get worse, no new gap / notch / spur).

Joint = a place where strokes meet:  T (a stroke ends on another stroke), L/Y (several strokes end at the same point), X (crossing, not repaired).

Join Checker (per joint)
  touch   every stroke end lies exactly on the centreline it joins (T) / on the common point (L)         tol  0.5 px + 4 % w
  hook    no end bends or jogs away from its own straight stroke in its last 1.4 w
  nub     no round cap sticks out of the stroke it ends in
  ink     no lump (render-only ink) and no hole (source-only ink) within 2 w of the joint
  nodes   no two anchors of one stroke closer than 0.4 px at the joint

Tools
  pen      Add / Delete / Convert anchor:  add an anchor on the through-stroke at the joint, put the end exactly on it, delete duplicate anchors,
           make a 2-stroke corner one stroke with a corner node
  line     Line / Arc tool: replace the last 1.4 w of an end by a straight run (line) or by a run that keeps the stroke's tangent (arc), ending on the joint;
           for L joints the ends meet in the intersection of their own directions
  shape    Shape Builder: re-trace the source inside the joint region, replace the strokes lying inside it, weld
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from scipy.spatial import cKDTree
from .model import Model, Path
from .geom import unit
from . import finisher as FN
from . import topology as T


# ============================================================
# CONFIGURATION: Batch join & tolerance controls
# ============================================================
TOLERANCE_CAP_BASE = 4.0              # Base tolerance in pixels
TOLERANCE_GROWTH_RATE = 0.003         # Per unit area
TOLERANCE_BUDGET_PER_JOIN = 0.004     # Drift budget per join  
TOLERANCE_DECAY_FACTOR = 0.92         # Reduce budget after each join (0.92 = 8% reduction)
ENDPOINT_SNAP_DISTANCE = 0.8          # Tighter spatial search (0.8 vs 1.5 for batch ops)
GEOMETRIC_LOCK_FORCE = True           # Force lock even if softness slightly increases
BATCH_MODE = True                     # Enable batch join optimizations


class ToleranceBudget:
    """Manages tolerance accumulation in batch join operations."""

    def __init__(self, base_tolerance, doctor_area, tolerance_budget):
        self.base = max(base_tolerance, TOLERANCE_GROWTH_RATE * max(doctor_area, 1))
        self.budget = tolerance_budget
        self.initial_budget = tolerance_budget
        self.joins_applied = 0

    def get_tolerance(self):
        """Return current tolerance, respecting budget."""
        return max(self.base, self.budget)

    def use_tolerance(self, amount=None):
        """Reduce budget after a successful join."""
        if amount is None:
            amount = self.initial_budget * (1.0 - TOLERANCE_DECAY_FACTOR)
        self.budget = max(self.base * 0.5, self.budget - amount)
        self.joins_applied += 1

    def reset(self):
        """Reset budget for new batch."""
        self.budget = self.initial_budget
        self.joins_applied = 0



@dataclass
class Joint:
    kind: str
    xy: np.ndarray
    ends: list = field(default_factory=list)  # [(path, end)]
    through: list = field(default_factory=list)  # [path]
    w: float = 10.0


# ------------------------------------------------------------------ find
def find_joints(m: Model):
    ends = [(i, e, (p.A[0] if e == 0 else p.A[-1]), p.w) for i, p in enumerate(m.paths) if not p.closed and len(p.A) >= 2 for e in (0, 1)]
    if not ends:
        return []
    pts, own = [], []
    for j, p in enumerate(m.paths):
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    P = np.vstack(pts)
    own = np.array(own)
    tree = cKDTree(P)
    n = len(ends)
    E = np.array([x[2] for x in ends])
    wmax = max(x[3] for x in ends)

    def _out_tangent(i, e):
        p = m.paths[i]
        if len(p.A) < 2:
            return np.array([1.0, 0.0])
        v = (p.A[0] - p.Hout[0]) if e == 0 else (p.A[-1] - p.Hin[-1])
        if np.linalg.norm(v) < 1e-5:
            v = (p.A[0] - p.A[1]) if e == 0 else (p.A[-1] - p.A[-2])
        nv = np.linalg.norm(v)
        return v / nv if nv > 1e-5 else np.array([1.0, 0.0])

    tangs = [_out_tangent(x[0], x[1]) for x in ends]

    def is_interior(j_path, pt, w_ref):
        qp = m.paths[j_path]
        if qp.closed:
            return True
        return min(float(np.linalg.norm(pt - qp.A[0])), float(np.linalg.norm(pt - qp.A[-1]))) > 0.35 * min(w_ref, qp.w)

    on_thr = [False] * n
    for k, (pi, pe, pt, pw) in enumerate(ends):
        idxs = tree.query_ball_point(pt, 0.45 * pw)
        if any(own[q] != pi and is_interior(int(own[q]), pt, pw) for q in idxs):
            on_thr[k] = True

    par = list(range(n))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a, b in cKDTree(E).query_pairs(0.85 * wmax):
        if ends[a][0] == ends[b][0]:
            continue
        cos_t = float(tangs[a] @ tangs[b])
        den = abs(float(tangs[a][0] * tangs[b][1] - tangs[a][1] * tangs[b][0]))
        d_ab = float(np.linalg.norm(E[a] - E[b]))
        w_min = min(ends[a][3], ends[b][3])
        w_max = max(ends[a][3], ends[b][3])
        if w_max > 1.8 * w_min:
            continue
        # Never group two parallel side-by-side strokes (e.g. parallel straps or legs) into the same joint
        if cos_t > 0.50 and d_ab > 0.24 * w_min:
            continue
        if cos_t > 0.65 and den < 0.15:
            continue
        if (on_thr[a] or on_thr[b]) and d_ab > 0.32 * w_min:
            continue
        if d_ab > 0.35 * w_min:
            if den < 0.20:
                continue
            diff = E[b] - E[a]
            sa = float(diff[0] * tangs[b][1] - diff[1] * tangs[b][0]) / (tangs[a][0] * tangs[b][1] - tangs[a][1] * tangs[b][0])
            sb = float(diff[0] * tangs[a][1] - diff[1] * tangs[a][0]) / (tangs[a][0] * tangs[b][1] - tangs[a][1] * tangs[b][0])
            if not (-0.25 * w_min <= sa <= 0.85 * w_min and -0.25 * w_min <= sb <= 0.85 * w_min):
                continue
        limit = 0.30 * w_min if (on_thr[a] or on_thr[b]) else 0.85 * w_min
        if d_ab <= limit:
            par[f(a)] = f(b)

    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        pts_g = np.array([ends[k][2] for k in g])
        mids = pts_g.mean(axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        if len(g) >= 2:
            for q_idx in tree.query_ball_point(mids, 0.45 * w):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and is_interior(j_path, mids, w) and _nearest_on(m.paths[j_path], mids)[1] <= 0.35 * min(w, m.paths[j_path].w):
                    thr.add(j_path)
        else:
            k = g[0]
            pt, pw = ends[k][2], ends[k][3]
            t_k = tangs[k]
            for q_idx in tree.query_ball_point(pt, 0.45 * pw):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, pt, pw):
                    pt_on, d_on = _nearest_on(m.paths[j_path], pt)
                    if d_on <= 0.35 * min(pw, m.paths[j_path].w):
                        fj = m.paths[j_path].flat(0.5)
                        kj = int(np.argmin(np.linalg.norm(fj - pt_on, axis=1)))
                        tau_j = unit(fj[min(kj + 1, len(fj) - 1)] - fj[max(kj - 1, 0)])
                        if d_on > 0.16 * min(pw, m.paths[j_path].w):
                            if abs(float(t_k @ tau_j)) > np.cos(np.radians(16.0)):
                                continue
                            if float(unit(pt_on - pt) @ t_k) < np.cos(np.radians(48.0)):
                                continue
                        thr.add(j_path)
            if not thr:
                s_steps = np.arange(-0.42 * pw, 0.42 * pw, 0.20)
                ray = pt[None, :] + s_steps[:, None] * tangs[k][None, :]
                d_ray, idx_ray = tree.query(ray)
                order = np.argsort(np.abs(s_steps))
                for m_idx in order:
                    dr, ir = float(d_ray[m_idx]), int(idx_ray[m_idx])
                    j_path = int(own[ir])
                    if dr <= 0.25 * min(pw, m.paths[j_path].w) and float(np.linalg.norm(P[ir] - pt)) <= 0.42 * min(pw, m.paths[j_path].w) and j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, P[ir], pw):
                        fj = m.paths[j_path].flat(0.5)
                        kj = int(np.argmin(np.linalg.norm(fj - P[ir], axis=1)))
                        tau_j = unit(fj[min(kj + 1, len(fj) - 1)] - fj[max(kj - 1, 0)])
                        if abs(float(t_k @ tau_j)) <= np.cos(np.radians(16.0)):
                            thr.add(j_path)
                            break
        if len(g) >= 3 and not thr:
            out.append(Joint("Y", mids, members, sorted(mem_paths), w))
        elif len(g) >= 2 and not thr:
            out.append(Joint("L", mids, members, [], w))
        elif thr:
            out.append(Joint("T" if len(g) == 1 else "Y", mids, members, sorted(thr), w))
    return out


# ------------------------------------------------------------------ small vector-editor operations
def _end_pt(p: Path, e):
    return p.A[0] if e == 0 else p.A[-1]


def _is_part_of_curve(p: Path, e: int) -> bool:
    """Return True if the end segment at `e` is part of a continuous curve/arc with its neighbor segment."""
    if len(p.A) < 3:
        return False
    if e == 0:
        v0 = p.A[1] - p.A[0]
        v1 = p.A[2] - p.A[1]
        L0, L1 = float(np.linalg.norm(v0)), float(np.linalg.norm(v1))
        if L0 < 1e-4 or L1 < 1e-4:
            return False
        u0, u1 = v0 / L0, v1 / L1
        perp1 = np.array([-u1[1], u1[0]])
        dev_nb = max(abs(float((p.Hout[1] - p.A[1]) @ perp1)), abs(float((p.Hin[2] - p.A[1]) @ perp1)))
        if dev_nb > max(0.45, 0.055 * p.w):
            return True
        if L0 < 2.2 * p.w and np.cos(np.radians(48.0)) <= float(u0 @ u1) < np.cos(np.radians(5.0)):
            return True
    else:
        v0 = p.A[-1] - p.A[-2]
        v1 = p.A[-2] - p.A[-3]
        L0, L1 = float(np.linalg.norm(v0)), float(np.linalg.norm(v1))
        if L0 < 1e-4 or L1 < 1e-4:
            return False
        u0, u1 = v0 / L0, v1 / L1
        perp1 = np.array([-u1[1], u1[0]])
        dev_nb = max(abs(float((p.Hout[-3] - p.A[-3]) @ perp1)), abs(float((p.Hin[-2] - p.A[-3]) @ perp1)))
        if dev_nb > max(0.45, 0.055 * p.w):
            return True
        if L0 < 2.2 * p.w and np.cos(np.radians(48.0)) <= float(u0 @ u1) < np.cos(np.radians(5.0)):
            return True
    return False


def _set_end_clean_handles(p: Path, e: int, X: np.ndarray, d: np.ndarray, was_str: bool):
    part_of_curve = _is_part_of_curve(p, e)
    if e == 0:
        v = p.A[1] - p.A[0]
        L = float(np.linalg.norm(v))
        if L > 1e-4:
            u = v / L
            perp = np.array([-u[1], u[0]])
            dev0 = float((p.Hout[0] - p.A[0]) @ perp)
            dev1 = float((p.Hin[1] - p.A[0]) @ perp)
            is_scurve = (dev0 * dev1 < 0) and (abs(dev0) + abs(dev1) < 0.40 * p.w)
            tol_sh = max(0.35, 0.045 * p.w) if part_of_curve else max(0.85, 0.12 * p.w)
            is_shallow = (max(abs(dev0), abs(dev1)) <= tol_sh) and (not part_of_curve or L >= 2.2 * p.w)
        else:
            is_scurve, is_shallow = True, True
        if (was_str and not part_of_curve) or is_scurve or is_shallow or np.linalg.norm(p.Hout[0] - p.A[0]) < 0.12 * min(p.w, max(L, 1.0)):
            p.Hout[0] = p.A[0] + v / 3.0
            p.Hin[1] = p.A[0] + 2.0 * v / 3.0
        else:
            p.Hout[0] += d
    else:
        v = p.A[-1] - p.A[-2]
        L = float(np.linalg.norm(v))
        if L > 1e-4:
            u = v / L
            perp = np.array([-u[1], u[0]])
            dev0 = float((p.Hout[-2] - p.A[-2]) @ perp)
            dev1 = float((p.Hin[-1] - p.A[-2]) @ perp)
            is_scurve = (dev0 * dev1 < 0) and (abs(dev0) + abs(dev1) < 0.40 * p.w)
            tol_sh = max(0.35, 0.045 * p.w) if part_of_curve else max(0.85, 0.12 * p.w)
            is_shallow = (max(abs(dev0), abs(dev1)) <= tol_sh) and (not part_of_curve or L >= 2.2 * p.w)
        else:
            is_scurve, is_shallow = True, True
        if (was_str and not part_of_curve) or is_scurve or is_shallow or np.linalg.norm(p.Hin[-1] - p.A[-1]) < 0.12 * min(p.w, max(L, 1.0)):
            p.Hout[-2] = p.A[-2] + v / 3.0
            p.Hin[-1] = p.A[-2] + 2.0 * v / 3.0
        else:
            p.Hin[-1] += d


def _set_end(p: Path, e, X):
    X = np.asarray(X, float)
    if e == 0:
        if len(p.A) > 2 and np.linalg.norm(p.A[1] - p.A[0]) < 1.35 * p.w:
            v_next = p.A[1] - p.A[2]
            l_next = float(np.linalg.norm(v_next))
            v_tip = X - p.A[1]
            l_tip = float(np.linalg.norm(v_tip))
            seg_next = np.array([p.A[1], p.Hout[1], p.Hin[2], p.A[2]])
            next_is_str = FN._straight(seg_next, 0.55)
            is_hook = next_is_str and l_next > 1e-4 and l_tip > 1e-4 and float((v_tip / l_tip) @ (v_next / l_next)) < np.cos(np.radians(16.0))
            if np.linalg.norm(p.A[1] - X) < 0.45 * p.w or (l_next > 1e-4 and v_tip @ v_next < 0) or is_hook:
                p.A = p.A[1:]
                p.Hin = p.Hin[1:]
                p.Hout = p.Hout[1:]
        seg0 = np.array([p.A[0], p.Hout[0], p.Hin[1], p.A[1]])
        was_str = FN._straight(seg0, 0.55)
        d = X - p.A[0]
        p.A[0] = X.copy()
        p.Hin[0] = X.copy()
        _set_end_clean_handles(p, 0, X, d, was_str)
    else:
        if len(p.A) > 2 and np.linalg.norm(p.A[-1] - p.A[-2]) < 1.35 * p.w:
            v_prev = p.A[-2] - p.A[-3]
            l_prev = float(np.linalg.norm(v_prev))
            v_tip = X - p.A[-2]
            l_tip = float(np.linalg.norm(v_tip))
            seg_prev = np.array([p.A[-3], p.Hout[-3], p.Hin[-2], p.A[-2]])
            prev_is_str = FN._straight(seg_prev, 0.55)
            is_hook = prev_is_str and l_prev > 1e-4 and l_tip > 1e-4 and float((v_tip / l_tip) @ (v_prev / l_prev)) < np.cos(np.radians(16.0))
            if np.linalg.norm(p.A[-2] - X) < 0.45 * p.w or (l_prev > 1e-4 and v_tip @ v_prev < 0) or is_hook:
                p.A = p.A[:-1]
                p.Hin = p.Hin[:-1]
                p.Hout = p.Hout[:-1]
        seg_last = np.array([p.A[-2], p.Hout[-2], p.Hin[-1], p.A[-1]])
        was_str = FN._straight(seg_last, 0.55)
        d = X - p.A[-1]
        p.A[-1] = X.copy()
        p.Hout[-1] = X.copy()
        _set_end_clean_handles(p, 1, X, d, was_str)


def _nearest_on(p: Path, X):
    f = p.flat(0.20)
    d_arr = np.linalg.norm(f - X, axis=1)
    k = int(np.argmin(d_arr))
    return f[k].copy(), float(d_arr[k])


def insert_anchor(p: Path, X, snap=0.6):
    """Add Anchor Point tool: put an anchor on stroke p at the point nearest X (shape unchanged). Returns the anchor index."""
    best = None
    for k, c in enumerate(p.segs()):
        t = np.linspace(0, 1, 60)
        mt = 1 - t
        Q = (mt**3)[:, None] * c[0] + (3 * mt**2 * t)[:, None] * c[1] + (3 * mt * t**2)[:, None] * c[2] + (t**3)[:, None] * c[3]
        d = np.linalg.norm(Q - X, axis=1)
        j = int(np.argmin(d))
        if best is None or d[j] < best[0]:
            best = (d[j], k, float(t[j]), Q[j])
    _, k, t, Pt = best
    c = p.segs()[k]
    dt = 1.0 / 60
    for _ in range(4):  # refine the parameter: the 60-sample grid alone puts the anchor up to ~1 px off
        tt = np.clip(np.linspace(t - dt, t + dt, 21), 0, 1)
        mt = 1 - tt
        Q = (mt**3)[:, None] * c[0] + (3 * mt**2 * tt)[:, None] * c[1] + (3 * mt * tt**2)[:, None] * c[2] + (tt**3)[:, None] * c[3]
        j = int(np.argmin(np.linalg.norm(Q - X, axis=1)))
        t, Pt, dt = float(tt[j]), Q[j], dt / 5
    for idx in (k, k + 1):  # already (almost) an anchor?
        if np.linalg.norm(p.A[idx] - Pt) < snap:
            return idx
    c = p.segs()[k]
    a, b, cc, d = c
    ab, bc, cd = a + (b - a) * t, b + (cc - b) * t, cc + (d - cc) * t
    abc, bcd = ab + (bc - ab) * t, bc + (cd - bc) * t
    P = abc + (bcd - abc) * t
    p.A = np.insert(p.A, k + 1, P, axis=0)
    p.Hin = np.insert(p.Hin, k + 1, abc, axis=0)
    p.Hout = np.insert(p.Hout, k + 1, bcd, axis=0)
    p.Hout[k] = ab
    p.Hin[k + 2] = cd
    return k + 1


def delete_duplicate_anchors(p: Path, tol=0.4):
    """Delete Anchor Point tool: drop an anchor that sits within tol of its neighbour."""
    eff_tol = max(tol, 0.22 * p.w if p.w > 0 else tol)
    keep = [0]
    for k in range(1, len(p.A)):
        if np.linalg.norm(p.A[k] - p.A[keep[-1]]) < eff_tol and k < len(p.A) - 1:
            continue
        keep.append(k)
    if p.closed and len(keep) > 3 and np.linalg.norm(p.A[keep[-1]] - p.A[0]) < eff_tol:
        keep.pop()
        keep.append(len(p.A) - 1)
    if len(keep) == len(p.A) or len(keep) < 2:
        res = p
    else:
        res = Path(p.A[keep], p.Hin[keep], p.Hout[keep], p.w, p.join, p.ml, p.closed)
    from .topology import prune_apex_overshoot
    return prune_apex_overshoot(res)


# ------------------------------------------------------------------ Join Checker
def check_joint(m: Model, J: Joint, extra=None, missing=None):
    """Returns the list of failed checks (empty = the joint is clean)."""
    bad = []
    w = J.w
    tol = max(0.35, 0.03 * w)
    mem = {i for i, _ in J.ends}
    ext_thr = [j for j in J.through if j not in mem]
    # touch
    if J.kind in ("T", "Y") and ext_thr:
        for (i, e) in J.ends:
            end = _end_pt(m.paths[i], e)
            dmin = min(_nearest_on(m.paths[j], end)[1] for j in ext_thr)
            if dmin > tol:
                bad.append("touch")
                break
    else:
        pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
        if np.linalg.norm(pts - pts.mean(0), axis=1).max() > tol:
            bad.append("touch")
    # hook / nub
    for (i, e) in J.ends:
        p = m.paths[i]
        g = FN.end_geometry(p, e)
        if g is not None:
            c, t, ang, end_pt, dev = g
            is_hook = (ang >= 20.0 and dev >= max(1.0, 0.15 * p.w)) or (ang >= 35.0) or (dev >= 0.25 * p.w)
            if is_hook and FN._straight_before_end(p, e, t):
                bad.append("hook")
                break
    for (i, e) in J.ends:
        p = m.paths[i]
        a, b = FN._end_info(p, e)
        if FN._protrusion(m, i, a, p.w, b) > 0.18 * p.w:
            bad.append("nub")
            break
    # ink around the joint
    if extra is not None:
        r = int(1.2 * w)
        x0, y0 = int(max(J.xy[0] - r, 0)), int(max(J.xy[1] - r, 0))
        x1, y1 = int(min(J.xy[0] + r + 1, extra.shape[1])), int(min(J.xy[1] + r + 1, extra.shape[0]))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        circ = (xx - J.xy[0])**2 + (yy - J.xy[1])**2 <= (1.1 * w)**2
        if extra[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("lump")
        if missing[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("hole")
    # duplicate nodes
    for i in {i for i, _ in J.ends}:
        A = m.paths[i].A
        if len(A) > 2 and (np.linalg.norm(np.diff(A, axis=0), axis=1) < 0.4).any():
            bad.append("nodes")
            break
    return bad


def _ink_maps(ink, D):
    return ((ink > 0.5) & (D < 0.3)).astype(np.float32), ((ink < 0.5) & (D > 0.5)).astype(np.float32)


# ------------------------------------------------------------------ tools
def tool_pen(m: Model, J: Joint, merge_l=True):
    m = m.copy()
    mem = {i for i, _ in J.ends}
    ext_thr = [j for j in J.through if j not in mem]
    if J.kind in ("T", "Y") and ext_thr:
        for (i, e) in J.ends:
            if i >= len(m.paths):
                continue
            p = m.paths[i]
            end = _end_pt(p, e)
            g = FN.end_geometry(p, e)
            t = g[1] if g is not None else _local_end_dir(p, e)
            best = None
            f_p = p.flat(0.25)
            f_p_rev = f_p if e == 0 else f_p[::-1]
            cum_p = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(f_p_rev, axis=0), axis=1))]
            max_back_k = int(np.searchsorted(cum_p, min(0.95 * p.w, 0.45 * float(cum_p[-1]))))
            for j in ext_thr:
                if j >= len(m.paths) or j == i:
                    continue
                q = m.paths[j]
                f = q.flat(0.25)
                tree_q = cKDTree(f)
                X_cand, d_cand = _nearest_on(q, end)
                s_retract = 0.0
                # Check if stroke p already crossed q's centerline slightly before its end (overshoot nub)
                if max_back_k >= 3:
                    d_sub, idx_sub = tree_q.query(f_p_rev[:max_back_k + 1])
                    k_cross = int(np.argmin(d_sub))
                    if k_cross >= 1 and float(d_sub[k_cross]) <= 0.18 * min(p.w, q.w) and float(d_sub[0]) > float(d_sub[k_cross]) + 0.08 * p.w:
                        s_retract = float(cum_p[k_cross])
                        X_cand = f[int(idx_sub[k_cross])].copy()
                        d_cand = float(d_sub[k_cross])
                if s_retract == 0.0 and t is not None and (d_cand > 0.15 * min(p.w, q.w) or FN._straight_before_end(p, e, t)):
                    s_steps = np.arange(-0.85 * J.w, min(1.8 * J.w, 20.0), 0.25)
                    ray = end[None, :] + s_steps[:, None] * t[None, :]
                    d_ray, idx_ray = tree_q.query(ray)
                    min_idx = int(np.argmin(d_ray))
                    if d_ray[min_idx] < 0.35 * min(p.w, q.w):
                        X_ray = f[idx_ray[min_idx]]
                        if float(np.linalg.norm(X_ray - end)) <= 1.25 * J.w:
                            X_cand = X_ray
                            d_cand = float(np.linalg.norm(X_cand - end))
                if best is None or d_cand < best[2]:
                    best = (j, X_cand, d_cand, s_retract)
            if best is None or best[2] > 1.5 * J.w:
                continue
            j, X, d, s_retract = best
            if s_retract >= 0.12 * p.w:
                mm = FN.move_end(Model([p], 0, 0), 0, e, s_retract)
                if mm is not None:
                    p = mm.paths[0]
                    m.paths[i] = p
            q = m.paths[j]
            X, _ = _nearest_on(q, X)
            _set_end(p, e, X)
    else:
        if len(J.ends) == 2 and J.ends[0][0] != J.ends[1][0]:
            (i1, e1), (i2, e2) = J.ends[0], J.ends[1]
            g1 = FN.end_geometry(m.paths[i1], e1)
            g2 = FN.end_geometry(m.paths[i2], e2)
            c1, t1 = (g1[0], g1[1]) if g1 is not None else (_end_pt(m.paths[i1], e1), _local_end_dir(m.paths[i1], e1))
            c2, t2 = (g2[0], g2[1]) if g2 is not None else (_end_pt(m.paths[i2], e2), _local_end_dir(m.paths[i2], e2))
            X = None
            den = _cr2(t1, t2)
            if abs(den) >= 0.15:
                s1 = _cr2(c2 - c1, t2) / den
                X = c1 + s1 * t1
            mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
            if X is None or np.linalg.norm(X - mid) > 1.2 * J.w:
                X = mid
            for (i, e) in J.ends:
                _set_end(m.paths[i], e, X)
            if merge_l:
                m = FN.merge_corners(m, [(J.ends[0][0], J.ends[0][1], J.ends[1][0], J.ends[1][1])])
        else:
            mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends if i < len(m.paths)], axis=0)
            for (i, e) in J.ends:
                if i < len(m.paths):
                    _set_end(m.paths[i], e, mid)
    for i in {i for i, _ in J.ends if i < len(m.paths)}:
        m.paths[i] = delete_duplicate_anchors(m.paths[i], tol=0.25)
    return m


def lock_joints(m: Model) -> Model:
    """Lock all detected joint endpoints to 0.00 px on their through-stroke or shared vertex without deleting paths."""
    m = m.copy()
    for _ in range(2):
        js = find_joints(m)
        changed = False
        for J in js:
            if J.kind == "X":
                continue
            mem = {i for i, _ in J.ends}
            ext_thr = [j for j in J.through if j not in mem]
            if J.kind in ("T", "Y") and ext_thr:
                need = any(min(_nearest_on(m.paths[j], _end_pt(m.paths[i], e))[1] for j in ext_thr) > 0.015 for i, e in J.ends)
            else:
                pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
                need = float(np.linalg.norm(pts - pts.mean(0), axis=1).max()) > 0.015
            if need:
                m = tool_pen(m, J, merge_l=False)
                changed = True
        if not changed:
            break
    return m


def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is None:
                end = _end_pt(cand.paths[i], e)
                best_X = None
                for j in J.through:
                    if j < len(cand.paths) and j != i:
                        pt_on_q, d = _nearest_on(cand.paths[j], end)
                        if best_X is None or d < best_X[1]:
                            best_X = (pt_on_q, d)
                target = best_X[0] if best_X is not None and best_X[1] <= 2.2 * J.w else None
                c = FN.fix_end(cand, i, e, target=target, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None
    # L: intersection of the two reference rays
    geo = [(i, e, FN.end_geometry(cand.paths[i], e)) for i, e in J.ends]
    if len(geo) != 2 or any(g is None for _, _, g in geo):
        return None
    (i1, e1, g1), (i2, e2, g2) = geo
    c1, t1, c2, t2 = g1[0], g1[1], g2[0], g2[1]
    den = _cr2(t1, t2)
    if abs(den) < 0.15:  # nearly parallel
        return None
    s1 = _cr2(c2 - c1, t2) / den
    X = c1 + s1 * t1
    if np.linalg.norm(X - J.xy) > 2.0 * J.w:
        return None
    changed = False
    for (i, e, _) in geo:
        c = FN.fix_end(cand, i, e, target=X, smooth=arc)
        if c is not None:
            cand = c
            changed = True
    return cand if changed else None


def _cr2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def _local_end_dir(p: Path, e: int):
    f = p.flat(0.5)
    if e == 0:
        f = f[::-1]
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
    fr = f[::-1]
    k0 = min(int(np.searchsorted(cum, 0.2 * p.w)), len(fr) - 1)
    k1 = min(int(np.searchsorted(cum, min(1.1 * p.w, 0.45 * float(cum[-1])))), len(fr) - 1)
    if k1 <= k0:
        return unit(f[-1] - f[max(0, len(f) - 2)])
    return unit(fr[k0] - fr[k1])


def smooth_continuation_pairs(m: Model, J: Joint, D):
    """Find pairs of ends meeting at joint J that form a smooth continuation (collinear, curved bar, or circular arc)
    and should be united by Shape Builder into one continuous through-stroke."""
    from .rings import _kasa
    cands = []
    ends = J.ends
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            j, ej = ends[y]
            if i >= len(m.paths) or j >= len(m.paths) or i == j:
                continue
            P, Q = m.paths[i], m.paths[j]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            a = _end_pt(P, ei)
            b = _end_pt(Q, ej)
            dist = float(np.linalg.norm(b - a))
            w = max(wa, wb)
            if dist > 2.5 * w:
                continue
            LP, LQ = P.length(), Q.length()
            f_all = np.vstack([P.flat(1.0), Q.flat(1.0)])
            on_circle = False
            if len(f_all) >= 10:
                cx, cy, r = _kasa(f_all)
                if 1.2 * w <= r <= 50.0 * w and (LP + LQ) >= 0.55 * r:
                    rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r)
                    if float(np.percentile(rad_err, 95)) <= 0.22 * w and float(rad_err.max()) <= 0.35 * w:
                        on_circle = True
            ga = FN.end_geometry(P, ei)
            gb = FN.end_geometry(Q, ej)
            ta = ga[1] if ga is not None else unit(a - (P.A[1] if ei == 0 else P.A[-2]))
            tb = gb[1] if gb is not None else unit(b - (Q.A[1] if ej == 0 else Q.A[-2]))
            ta_loc = _local_end_dir(P, ei)
            tb_loc = _local_end_dir(Q, ej)
            dot = float(ta @ tb)
            dot_loc = float(ta_loc @ tb_loc)
            if not on_circle:
                if dot > -0.85 or dot_loc > -0.82:
                    continue
            else:
                if dot > -0.55 or dot_loc > -0.55:
                    continue
            n = max(3, int(dist))
            pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
            xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
            if float((D[ys, xs] > 0.5).mean()) >= 0.78:
                cands.append((0 if on_circle else 1, dist, i, ei, j, ej, min(dot, dot_loc)))
    if not cands:
        return []
    cands.sort(key=lambda t: (t[0], t[1], t[6]))
    best = cands[0]
    return [(best[2], best[3], best[4], best[5])]


def corner_continuation_pairs(m: Model, J: Joint, D):
    """Find pairs of ends meeting at multi-way joint J that form a corner (roughly 90 deg)
    and should be united by Shape Builder into one continuous corner stroke."""
    ends = J.ends
    if len(ends) < 3:
        return []
    best_pair = None
    best_score = 999.0
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            k, ek = ends[y]
            if i >= len(m.paths) or k >= len(m.paths) or i == k:
                continue
            P, Q = m.paths[i], m.paths[k]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            w = max(wa, wb)
            if P.length() < 1.6 * w or Q.length() < 1.6 * w:
                continue
            gP = FN.end_geometry(P, ei)
            gQ = FN.end_geometry(Q, ek)
            cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei == 0 else -1], _local_end_dir(P, ei))
            cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ek == 0 else -1], _local_end_dir(Q, ek))
            cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
            if abs(cr) < 0.40:
                continue
            sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / cr
            sQ = float((cQ - cP)[0] * tP[1] - (cQ - cP)[1] * tP[0]) / cr
            if sP < -0.2 * w or sQ < -0.2 * w:
                continue
            Xc = cP + sP * tP
            dist_j = float(np.linalg.norm(Xc - J.xy))
            if dist_j > 1.35 * w:
                continue
            dot = float(tP @ tQ)
            if abs(dot) < 0.65:
                score = abs(dot) + 0.5 * (dist_j / w)
                if score < best_score:
                    best_score = score
                    best_pair = (i, ei, k, ek, Xc)
    if best_pair is not None:
        return [best_pair]
    return []


def tool_unite(m: Model, J: Joint, D):
    """Shape Builder, unite: two strokes that are really one stroke cut by the joint (a ring in two arcs, a line cut by a crossing,
    or a curved bar) become one stroke; what is left of the joint is then an ordinary T."""
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J.ends and (p[2], p[3]) in J.ends]
    if not pairs:
        pairs = smooth_continuation_pairs(m, J, D)
    if pairs:
        return FN.join_pairs(m, pairs)
    if len(J.ends) >= 3:
        cp = corner_continuation_pairs(m, J, D)
        if cp:
            return FN.merge_corners(m, cp, joint_ends=J.ends, D=D)
    return None


def tool_shape(m: Model, J: Joint, D):
    r = 2.2 * J.w
    box = [int(J.xy[0] - r), int(J.xy[1] - r), int(J.xy[0] + r), int(J.xy[1] + r)]
    return FN._redraw_region(m, D, box, J.w, margin=0)


# ------------------------------------------------------------------ engine
def run_join_engine(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_fail=30, batch_mode=BATCH_MODE):  # noqa: C901
    """Returns (model, ink, soft, report)."""
    st = dict(model=model, ink=ink_of(model))
    st["cur"] = doctor.soft(st["ink"])
    start = st["cur"]
    st["topo"] = FN._topo(model)
    cap = 0.006 * max(doctor.area, 1)
    rep = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)

    if batch_mode:
        tolerance_budget = TOLERANCE_BUDGET_PER_JOIN * max(doctor.area, 1)
        st['budget'] = ToleranceBudget(TOLERANCE_CAP_BASE, doctor.area, tolerance_budget)

    def tol():
        if batch_mode and 'budget' in st:
            return st['budget'].get_tolerance()
        return max(4.0, 0.003 * max(doctor.area, 1), 0.006 * st["cur"])

    def nearest(m, xy, rad):
        js = find_joints(m)
        if not js:
            return None
        d = [np.linalg.norm(j.xy - xy) for j in js]
        k = int(np.argmin(d))
        return js[k] if d[k] <= rad else None

    def try_accept(cand, J, before):
        if cand is None:
            return False
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 > st["cur"] + tol() or (s2 - start) > cap:
            return False
        t2 = FN._topo(cand)
        if t2 > st["topo"]:
            return False
        J2 = nearest(cand, J.xy, 1.5 * J.w)
        ex, mi = _ink_maps(ink2, D)
        after = [] if J2 is None else check_joint(cand, J2, ex, mi)
        struct_keys = {"touch", "hook", "nub", "nodes"}
        s_before = set(before) & struct_keys
        s_after = set(after) & struct_keys
        improved_structural = (len(s_after) < len(s_before)) and not (s_after - s_before)
        simplified_joint = J2 is not None and (len(J2.ends) < len(J.ends) or (J.kind == "Y" and J2.kind == "T")) and not (set(after) - set(before))
        if len(after) < len(before) or improved_structural or simplified_joint:
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
            return True
        return False

    # stage 0: unite any stroke cut at a multi-end joint so it becomes a continuous through-stroke before locking T-stems
    for J in [j for j in find_joints(st["model"]) if len(j.ends) >= 2]:
        if not time_ok():
            break
        J_cur = nearest(st["model"], J.xy, 1.5 * J.w)
        if J_cur is None or len(J_cur.ends) < 2:
            continue
        cand_u = tool_unite(st["model"], J_cur, D)
        if cand_u is not None:
            ink_u = ink_of(cand_u)
            s_u = doctor.soft(ink_u)
            tol_u = max(tol(), 0.0045 * max(doctor.area, 1))
            if s_u <= st["cur"] + tol_u and (s_u - start) <= cap and FN._topo(cand_u) <= st["topo"]:
                st.update(model=cand_u, ink=ink_u, cur=s_u, topo=FN._topo(cand_u))
                rep["fixed"]["unite"] += 1
                if batch_mode and 'budget' in st:
                    st['budget'].use_tolerance()

    # stage 1: build every joint carefully (ends exactly on the centreline they join) - fast batch first
    ex, mi = _ink_maps(st["ink"], D)
    joints = find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in check_joint(st["model"], J)]
    if need:
        cand = st["model"]
        for J in need:
            cand = tool_pen(cand, J) if cand is st["model"] else _apply_pen_again(cand, J, spatial_tolerance=ENDPOINT_SNAP_DISTANCE if batch_mode else 1.5)
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 <= st["cur"] + tol() and FN._topo(cand) <= st["topo"]:
            st.update(model=cand, ink=ink2, cur=s2, topo=FN._topo(cand))
            rep["built"] = len(need)
            if batch_mode and 'budget' in st:
                st['budget'].use_tolerance()
        else:
            cand2 = lock_joints(st["model"])
            ink2 = ink_of(cand2)
            s2 = doctor.soft(ink2)
            if s2 <= st["cur"] + tol():
                st.update(model=cand2, ink=ink2, cur=s2, topo=FN._topo(cand2))
                rep["built"] = len(need)
                if batch_mode and 'budget' in st:
                    st['budget'].use_tolerance()
    # stage 2: check every joint, repair the ones that fail
    joints = find_joints(st["model"])
    ex, mi = _ink_maps(st["ink"], D)
    fails = []
    for J in joints:
        bad = check_joint(st["model"], J, ex, mi)
        if not bad:
            rep["clean_first"] += 1
        else:
            fails.append((len(bad), J.xy.copy(), J.w, bad))
    fails.sort(key=lambda t: -t[0])
    for _, xy, jw, _ in fails[:max_fail]:
        if not time_ok():
            break
        ex, mi = _ink_maps(st["ink"], D)
        J = nearest(st["model"], xy, 1.5 * jw)
        if J is None:
            continue
        before = check_joint(st["model"], J, ex, mi)
        if not before:
            continue
        done = False
        for name, fn in (("unite", lambda: tool_unite(st["model"], J, D)), ("pen", lambda: tool_pen(st["model"], J)), ("line", lambda: tool_line(st["model"], J)),
                         ("arc", lambda: tool_line(st["model"], J, arc=True)), ("shape", lambda: tool_shape(st["model"], J, D))):
            if not time_ok():
                break
            try:
                cand = fn()
            except Exception:
                cand = None
            if try_accept(cand, J, before):
                rep["fixed"][name] += 1
                done = True
                if batch_mode and 'budget' in st:
                    st['budget'].use_tolerance()
                break
        if not done:
            ex, mi = _ink_maps(st["ink"], D)
            J = nearest(st["model"], xy, 1.5 * jw)
            rep["unresolved"].append(dict(x=float(xy[0]), y=float(xy[1]), reasons=before))
    # Final geometric lock so no joint ends up with a residual sub-pixel gap or overshoot
    cand_lock = lock_joints(st["model"])
    ink_lock = ink_of(cand_lock)
    s_lock = doctor.soft(ink_lock)
    t_lock = FN._topo(cand_lock)
    if GEOMETRIC_LOCK_FORCE:
        accept_lock = (
            (t_lock < st["topo"]) or
            (t_lock == st["topo"] and s_lock <= st["cur"] + 0.002 * max(doctor.area, 1))
        )
    else:
        accept_lock = (s_lock <= st["cur"] + tol())

    if accept_lock:
        st.update(model=cand_lock, ink=ink_lock, cur=s_lock, topo=t_lock)
        if batch_mode and 'budget' in st:
            st['budget'].use_tolerance()

    if batch_mode:
        rep["batch_mode"] = True
        if 'budget' in st:
            rep["final_tolerance_budget"] = float(st['budget'].budget)
            rep["joins_applied"] = st['budget'].joins_applied
        rep["final_topology"] = st.get("topo", -1)
    else:
        rep["batch_mode"] = False

    rep["drift"] = float(st["cur"] - start)
    return st["model"], st["ink"], st["cur"], rep


def _apply_pen_again(m, J, spatial_tolerance=0.8):
    """Pen tool on a model that has already been changed by earlier joints of this batch: re-find the joint near J and apply with aliasing prevention."""
    js = find_joints(m)
    if not js:
        return m
    distances = [np.linalg.norm(j.xy - J.xy) for j in js]
    k = int(np.argmin(distances))
    dist = distances[k]
    max_distance = spatial_tolerance * J.w
    if dist > max_distance:
        return m
    J_found = js[k]
    if J_found.kind != J.kind or abs(len(J_found.ends) - len(J.ends)) > 1:
        return m
    return tool_pen(m, J_found)
