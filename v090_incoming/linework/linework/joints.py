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
from . import finisher as FN
from . import topology as T


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
    # cluster ends that meet each other
    n = len(ends)
    par = list(range(n))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    E = np.array([x[2] for x in ends])
    wmax = max(x[3] for x in ends)
    for a, b in cKDTree(E).query_pairs(0.9 * wmax):
        if ends[a][0] != ends[b][0] and np.linalg.norm(E[a] - E[b]) <= 0.9 * max(ends[a][3], ends[b][3]):
            par[f(a)] = f(b)
    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        mids = np.mean([ends[k][2] for k in g], axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        for k in g:
            for q in tree.query_ball_point(ends[k][2], 1.0 * ends[k][3]):
                if own[q] not in mem_paths:
                    thr.add(int(own[q]))
        if len(g) >= 3 and not thr:  # e.g. a ring in two arcs plus a spoke: the other strokes of the cluster are what each end must touch
            out.append(Joint("Y", mids, members, sorted(mem_paths), w))
        elif len(g) >= 2 and not thr:
            out.append(Joint("L", mids, members, [], w))
        elif thr:
            out.append(Joint("T" if len(g) == 1 else "Y", mids, members, sorted(thr), w))
        # a single free end touching nothing is not a joint
    return out


# ------------------------------------------------------------------ small vector-editor operations
def _end_pt(p: Path, e):
    return p.A[0] if e == 0 else p.A[-1]


def _set_end(p: Path, e, X):
    d = np.asarray(X, float) - _end_pt(p, e)
    if e == 0:
        p.A[0] += d
        p.Hout[0] += d
        p.Hin[0] += d
    else:
        p.A[-1] += d
        p.Hin[-1] += d
        p.Hout[-1] += d


def _nearest_on(p: Path, X):
    f = p.flat(0.25)
    k = int(np.argmin(np.linalg.norm(f - X, axis=1)))
    return f[k], float(np.linalg.norm(f[k] - X))


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
    keep = [0]
    for k in range(1, len(p.A)):
        if np.linalg.norm(p.A[k] - p.A[keep[-1]]) < tol and k < len(p.A) - 1:
            continue
        keep.append(k)
    if len(keep) == len(p.A) or len(keep) < 2:
        return p
    return Path(p.A[keep], p.Hin[keep], p.Hout[keep], p.w, p.join, p.ml, p.closed)


# ------------------------------------------------------------------ Join Checker
def check_joint(m: Model, J: Joint, extra=None, missing=None):
    """Returns the list of failed checks (empty = the joint is clean)."""
    bad = []
    w = J.w
    tol = 0.5 + 0.04 * w
    # touch
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            end = _end_pt(m.paths[i], e)
            others = [j for j in J.through if j != i] or J.through
            dmin = min(_nearest_on(m.paths[j], end)[1] for j in others)
            if dmin > tol:
                bad.append("touch")
                break
    else:
        pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
        if np.linalg.norm(pts - pts.mean(0), axis=1).max() > 0.6 + 0.02 * w:
            bad.append("touch")
    # hook / nub
    for (i, e) in J.ends:
        p = m.paths[i]
        g = FN.end_geometry(p, e)
        if g is not None and (g[2] >= 12.0 or g[4] >= max(0.8, 0.12 * p.w)) and FN._straight_before_end(p, e, g[1]):
            bad.append("hook")
            break
    for (i, e) in J.ends:
        p = m.paths[i]
        a, b = FN._end_info(p, e)
        if FN._protrusion(m, i, a, p.w, b) > 0.1 * p.w:
            bad.append("nub")
            break
    # ink around the joint
    if extra is not None:
        r = int(2 * w)
        x0, y0 = int(max(J.xy[0] - r, 0)), int(max(J.xy[1] - r, 0))
        x1, y1 = int(J.xy[0] + r + 1), int(J.xy[1] + r + 1)
        if extra[y0:y1, x0:x1].sum() > 0.15 * w * w:
            bad.append("lump")
        if missing[y0:y1, x0:x1].sum() > 0.15 * w * w:
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
def tool_pen(m: Model, J: Joint):
    m = m.copy()
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            p = m.paths[i]
            end = _end_pt(p, e)
            best = min(((j, *_nearest_on(m.paths[j], end)) for j in J.through if j != i), key=lambda t: t[2], default=None)
            if best is None:
                continue
            j, X, d = best
            if d > 1.2 * J.w:
                continue
            q = m.paths[j]
            k = insert_anchor(q, X)
            X = q.A[k].copy()
            _set_end(p, e, X)
    else:
        if len(J.ends) > 2:  # three or more ends are not one corner: unite the pieces of one stroke first (tool_unite)
            return m
        mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
        for (i, e) in J.ends:
            _set_end(m.paths[i], e, mid)
        if len(J.ends) == 2 and J.ends[0][0] != J.ends[1][0]:
            m = FN.merge_corners(m, [(J.ends[0][0], J.ends[0][1], J.ends[1][0], J.ends[1][1])])
    for i in range(len(m.paths)):
        m.paths[i] = delete_duplicate_anchors(m.paths[i])
    return m


def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is None:
                return None
            cand = c
        return cand
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
    for (i, e, _) in geo:
        c = FN.fix_end(cand, i, e, target=X, smooth=arc)
        if c is None:
            return None
        cand = c
    return cand


def _cr2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def tool_unite(m: Model, J: Joint, D):
    """Shape Builder, unite: two strokes that are really one stroke cut by the joint (a ring in two arcs, a line cut by a crossing) become one
    stroke; what is left of the joint (a spoke on that ring) is then an ordinary T."""
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J.ends and (p[2], p[3]) in J.ends]
    if not pairs:
        return None
    return FN.join_pairs(m, pairs)


def tool_shape(m: Model, J: Joint, D):
    r = 2.2 * J.w
    box = [int(J.xy[0] - r), int(J.xy[1] - r), int(J.xy[0] + r), int(J.xy[1] + r)]
    return FN._redraw_region(m, D, box, J.w, margin=0)


# ------------------------------------------------------------------ engine
def run_join_engine(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_fail=30):  # noqa: C901
    """Returns (model, ink, soft, report)."""
    st = dict(model=model, ink=ink_of(model))
    st["cur"] = doctor.soft(st["ink"])
    start = st["cur"]
    st["topo"] = FN._topo(model)
    cap = 0.006 * max(doctor.area, 1)
    rep = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)

    def tol():
        return max(2.0, 0.003 * st["cur"])

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
        if len(after) < len(before):
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
            return True
        return False

    # stage 1: build every joint carefully (ends exactly on the centreline they join) - batch first, then joint by joint
    ex, mi = _ink_maps(st["ink"], D)
    joints = find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in check_joint(st["model"], J)]
    if need:
        cand = st["model"]
        for J in need:
            cand = tool_pen(cand, J) if cand is st["model"] else _apply_pen_again(cand, J)
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 <= st["cur"] + tol() and FN._topo(cand) <= st["topo"]:
            st.update(model=cand, ink=ink2, cur=s2, topo=FN._topo(cand))
            rep["built"] = len(need)
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
                break
        if not done:
            ex, mi = _ink_maps(st["ink"], D)
            J = nearest(st["model"], xy, 1.5 * jw)
            rep["unresolved"].append(dict(x=float(xy[0]), y=float(xy[1]), reasons=before))
    rep["drift"] = float(st["cur"] - start)
    return st["model"], st["ink"], st["cur"], rep


def _apply_pen_again(m, J):
    """Pen tool on a model that has already been changed by earlier joints of this batch: re-find the joint near J and apply."""
    js = find_joints(m)
    if not js:
        return m
    k = int(np.argmin([np.linalg.norm(j.xy - J.xy) for j in js]))
    return tool_pen(m, js[k]) if np.linalg.norm(js[k].xy - J.xy) <= 1.5 * J.w else m
