"""Join Checker engine.

Flow (after the Finisher):  find every join  ->  check each join on its own  ->  all PASS: output unchanged
                                                                             ->  some FAIL: Repair Toolbox, then check again.

A join is one of
  T  an end that lands on another stroke           (pass: end lies ON that stroke's centerline)
  L  two ends that meet in one point (a corner)    (pass: they are ONE stroke with a corner node - merged)
  Y  three or more ends that meet (hub / star)     (pass: all ends meet in one common point)
  X  a straight stroke cut where another crosses   (pass: it is one continuous stroke - joined)
and every join must additionally have no hook / jog, no nub (cap poking out) and no lump / hole of ink compared with the source.

The Repair Toolbox mirrors the three Illustrator tool groups:
  shape_builder  merge / trim overlaps and extra ink            (merge_corners, tip retract, nub tuck)
  line_arc       rebuild a segment as an exact line or arc      (fix_end, join_pairs, make straight, arc_fit)
  pen            node surgery: move / add / delete anchors      (snap_end, junction_snap, cut hook + re-anchor)
Every candidate is verified: global match to the source must not get worse, topology must not get worse and the number of
failing joins must go down.  Nothing is ever kept that the check cannot confirm.
"""
from __future__ import annotations
import numpy as np
from .model import Model, Path
from . import finisher as FN
from . import edit as E
from . import topology as T

# tolerances (fractions of the stroke width w)
ON_CENTER = 0.15
CLUSTER = 0.9
REACH = 1.6
Y_SPREAD = 0.25
INK_FRAC = 0.75

REASONS = ("off_center", "corner_split", "y_spread", "split", "hook", "nub", "lump", "hole")
# which tool groups are tried (in order) for a reason
PLAN = {
    "off_center": ("pen", "line_arc", "shape_builder"),
    "hook": ("shape_builder", "pen", "line_arc"),
    "split": ("line_arc", "shape_builder"),
    "corner_split": ("shape_builder",),
    "y_spread": ("shape_builder", "pen", "line_arc"),
    "lump": ("shape_builder", "pen"),
    "nub": ("shape_builder", "pen"),
    "hole": ("pen", "line_arc"),
}


# ------------------------------------------------------------------ geometry helpers
def _ends(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        out += [(i, 0, p.A[0].copy(), p.w), (i, 1, p.A[-1].copy(), p.w)]
    return out


def _dir(p: Path, e: int):
    """Unit direction of the stroke pointing OUT of end e (measured outside the junction zone when possible)."""
    g = FN.end_geometry(p, e)
    if g is not None:
        return g[1] / max(np.linalg.norm(g[1]), 1e-9)
    f = p.flat(1.0)
    t = f[0] - f[min(len(f) - 1, 6)] if e == 0 else f[-1] - f[max(0, len(f) - 7)]
    return t / max(np.linalg.norm(t), 1e-9)


class _Trees:
    def __init__(self, m):
        self.m, self.c = m, {}

    def get(self, skip):
        if skip not in self.c:
            self.c[skip] = FN._others_tree(self.m, skip)
        return self.c[skip]


def snap_end(m: Model, i, e, X):
    """Pen tool: move the end anchor of path i to X (its handle travels with it)."""
    m = m.copy()
    p = m.paths[i]
    q = p if e == 1 else FN._reversed(p)
    v = np.asarray(X, float) - q.A[-1]
    q.A[-1] = q.A[-1] + v
    q.Hin[-1] = q.Hin[-1] + v
    m.paths[i] = q if e == 1 else FN._reversed(q)
    return m


def common_point(ends_pts, dirs):
    """Least-squares point closest to the lines through each end along its direction (None when the lines are parallel)."""
    A = np.zeros((2, 2))
    b = np.zeros(2)
    for a, t in zip(ends_pts, dirs):
        M = np.eye(2) - np.outer(t, t)
        A += M
        b += M @ a
    if abs(np.linalg.det(A)) < 1e-3:
        return None
    return np.linalg.solve(A, b)


def junction_snap(m: Model, ends, max_move=REACH):
    """Pen tool: move all given ends (i, e) to their common intersection point. Returns the model or None."""
    pts = [m.paths[i].A[0 if e == 0 else -1] for i, e in ends]
    w = max(m.paths[i].w for i, e in ends)
    X = common_point(pts, [_dir(m.paths[i], e) for i, e in ends])
    cen = np.mean(pts, axis=0)
    if X is None or np.linalg.norm(X - cen) > max_move * w:
        X = cen
    for a in pts:
        if np.linalg.norm(X - a) > max_move * w:
            return None
    out = m
    for i, e in ends:
        out = snap_end(out, i, e, X)
    return out


# ------------------------------------------------------------------ find + check
def inspect(m: Model, D, ink):
    """All joins of the model with their check result: [dict(kind, x, y, ends, reasons, w, target)]. reasons == [] means PASS."""
    ends = _ends(m)
    n = len(ends)
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for a in range(n):
        for b in range(a + 1, n):
            ia, _, pa, wa = ends[a]
            ib, _, pb, wb = ends[b]
            if ia != ib and np.linalg.norm(pa - pb) <= CLUSTER * max(wa, wb) and abs(wa - wb) <= 0.35 * max(wa, wb):
                par[find(a)] = find(b)
    groups = {}
    for k in range(n):
        groups.setdefault(find(k), []).append(k)

    trees = _Trees(m)
    joints = []

    def through(c, skip_paths, w):
        for j, q in enumerate(m.paths):
            if j in skip_paths:
                continue
            f = q.flat(1.0)
            if np.linalg.norm(f - c, axis=1).min() < 0.7 * w:
                return True
        return False

    singles = []
    for g in groups.values():
        if len(g) == 1:
            singles.append(g[0])
            continue
        pts = np.array([ends[k][2] for k in g])
        c = pts.mean(0)
        w = max(ends[k][3] for k in g)
        if through(c, {ends[k][0] for k in g}, w):
            singles += g
            continue
        es = [(ends[k][0], ends[k][1]) for k in g]
        kind = "L" if len(g) == 2 else "Y"
        reasons = []
        spread = float(np.linalg.norm(pts - c, axis=1).max())
        if kind == "L":
            reasons.append("corner_split")
        elif spread > Y_SPREAD * w:
            reasons.append("y_spread")
        joints.append(dict(kind=kind, x=float(c[0]), y=float(c[1]), ends=es, reasons=reasons, w=float(w), target=None))
    for k in singles:
        i, e, a, w = ends[k]
        tree, P, own = trees.get(i)
        if tree is None:
            continue
        d, kk = tree.query(a)
        if d > REACH * w:
            continue
        X = P[kk].copy()
        if d > 0.5 * w:
            v = (X - a) / max(d, 1e-9)
            if float(_dir(m.paths[i], e) @ v) < 0.5:  # not pointing at it: a free end close to another stroke
                continue
        reasons = ["off_center"] if d > ON_CENTER * w + 0.2 else []
        joints.append(dict(kind="T", x=float(a[0]), y=float(a[1]), ends=[(i, e)], reasons=reasons, w=float(w), target=X))
    # collinear pieces of one straight stroke that were left cut at a crossing
    for (i, ei, j, ej) in FN.collinear_pairs(m, D):
        a = m.paths[i].A[0 if ei == 0 else -1]
        b = m.paths[j].A[0 if ej == 0 else -1]
        c = 0.5 * (a + b)
        joints.append(dict(kind="X", x=float(c[0]), y=float(c[1]), ends=[(i, ei), (j, ej)], reasons=["split"],
                           w=float(max(m.paths[i].w, m.paths[j].w)), target=None))
    hk = {(i, e) for _, i, e, _ in FN.end_hooks(m)}
    nb = {(i, e) for _, i, e, _ in FN.cap_hits(m)}
    H, W = ink.shape
    for jn in joints:
        for es in jn["ends"]:
            if es in hk and "hook" not in jn["reasons"]:
                jn["reasons"].append("hook")
            if es in nb and "nub" not in jn["reasons"]:
                jn["reasons"].append("nub")
        if jn["kind"] != "X":
            r = int(max(3, 1.5 * jn["w"]))
            x0, x1 = int(max(jn["x"] - r, 0)), int(min(jn["x"] + r + 1, W))
            y0, y1 = int(max(jn["y"] - r, 0)), int(min(jn["y"] + r + 1, H))
            if x1 > x0 and y1 > y0:
                extra = float(((ink[y0:y1, x0:x1] > 0.5) & (D[y0:y1, x0:x1] < 0.3)).sum())
                miss = float(((ink[y0:y1, x0:x1] < 0.5) & (D[y0:y1, x0:x1] > 0.7)).sum())
                if extra > INK_FRAC * jn["w"] ** 2:
                    jn["reasons"].append("lump")
                if miss > INK_FRAC * jn["w"] ** 2:
                    jn["reasons"].append("hole")
    return joints


def bad_count(joints):
    return sum(len(j["reasons"]) for j in joints)


# ------------------------------------------------------------------ Repair Toolbox
def _refine_on_line(P, own, k, a, t):
    """Exact point where the ray a + s t meets the centerline polyline near sample k (the samples are 0.5 px apart, so snapping to a
    sample alone would be off by a fraction of a pixel). Falls back to the sample itself."""
    best, bd = P[k].copy(), 1e18
    for kk in (k - 1, k):
        if kk < 0 or kk + 1 >= len(P) or own[kk] != own[k] or own[kk + 1] != own[k]:
            continue
        b0, b1 = P[kk], P[kk + 1]
        d = b1 - b0
        den = t[1] * d[0] - t[0] * d[1]
        if abs(den) < 1e-9:
            continue
        v = b0 - a
        u = (t[0] * v[1] - t[1] * v[0]) / den  # position along the segment
        if -1e-6 <= u <= 1 + 1e-6:
            X = b0 + u * d
            if np.linalg.norm(X - P[k]) < bd:
                best, bd = X, np.linalg.norm(X - P[k])
    return best


def _ray_target(m, i, e, w, trees):
    """Where the stroke's own straight direction meets the centerline it joins (falls back to the nearest point)."""
    p = m.paths[i]
    tree, P, own = trees.get(i)
    if tree is None:
        return None
    a = p.A[0 if e == 0 else -1]
    t = _dir(p, e)
    s = np.arange(-1.0 * w, REACH * w, 0.25)
    d, k = tree.query(a + s[:, None] * t)
    j = int(np.argmin(d))
    if d[j] < 0.5 * w:
        return _refine_on_line(P, own, int(k[j]), a, t)
    d0, k0 = tree.query(a)
    return P[k0].copy() if d0 <= REACH * w else None


def tool_pen(m, jn, reason, D=None):
    out, trees = [], _Trees(m)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "corner_split"):
        c = junction_snap(m, jn["ends"])
        if c is not None:
            out.append(c)
    if jn["kind"] == "T" and reason in ("off_center", "hole", "lump", "nub"):
        i, e = jn["ends"][0]
        X = _ray_target(m, i, e, m.paths[i].w, trees)
        if X is not None:
            out.append(snap_end(m, i, e, X))
    if reason == "hook":
        for i, e in jn["ends"]:
            cut = FN.move_end(m, i, e, 1.4 * m.paths[i].w)
            if cut is not None:
                out.append(cut)
                if jn["target"] is not None:
                    out.append(snap_end(cut, i, e, jn["target"]))
    if reason in ("lump", "nub") and jn["kind"] in ("L", "Y"):  # delete the last anchor stub of every end at the join
        c = m
        for i, e in jn["ends"]:
            r = FN.move_end(c, i, e, 0.5 * c.paths[i].w)
            c = r if r is not None else c
        if c is not m:
            out.append(c)
    return out


def tool_line_arc(m, jn, reason, D=None):
    out = []
    if reason in ("hook", "off_center", "hole"):
        for i, e in jn["ends"]:
            c = FN.fix_end(m, i, e)
            if c is not None:
                out.append(c)
    if reason == "split" and jn["kind"] == "X":
        (i, ei), (j, ej) = jn["ends"]
        out.append(FN.join_pairs(m, [(i, ei, j, ej)]))
        if D is not None:
            all_pairs = FN.collinear_pairs(m, D)
            if len(all_pairs) > 1:
                out.append(FN.join_pairs(m, all_pairs))
    for i, e in jn["ends"]:  # rebuild the whole stroke as an exact line / exact arc, then it is re-checked
        p = m.paths[i]
        f = p.flat(1.0)
        a, b = f[0], f[-1]
        L = np.linalg.norm(b - a)
        if L > 2 * p.w:
            dev = np.abs((f[:, 0] - a[0]) * (b[1] - a[1]) - (f[:, 1] - a[1]) * (b[0] - a[0])).max() / L
            if dev <= 0.35 * p.w and len(p.A) > 2:
                out.append(FN.make_straight(m, i))
        q = FN.arc_fit(p)
        if q is not None:
            c = m.copy()
            c.paths[i] = q
            out.append(c)
    return out


def tool_shape_builder(m, jn, reason, D=None):
    out = []
    if reason == "corner_split" and jn["kind"] == "L":
        (i, ei), (j, ej) = jn["ends"]
        out.append(FN.merge_corners(m, [(i, ei, j, ej)]))
        c = junction_snap(m, jn["ends"])
        if c is not None:
            out.append(FN.merge_corners(c, [(i, ei, j, ej)]))
    if jn["kind"] in ("Y", "L"):
        ends = jn["ends"]
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        out.append(FN.merge_corners(m, [(ia, ea, ib, eb)]))
    if reason in ("off_center", "y_spread", "nub"):  # a stub shorter than ~2.5 w that is one of the join's ends: delete it (Shape Builder: delete region)
        for i in sorted({i for i, e in jn["ends"]}, reverse=True):
            if m.paths[i].length() < 2.5 * m.paths[i].w:
                out.append(E.remove_path(m, i))
    if reason == "hook":
        for i, e in jn["ends"]:
            p = m.paths[i]
            if len(p.A) > 2:
                p_drop = p.copy()
                if e == 0:
                    p_drop.A = p.A[1:].copy(); p_drop.Hin = p.Hin[1:].copy(); p_drop.Hout = p.Hout[1:].copy()
                else:
                    p_drop.A = p.A[:-1].copy(); p_drop.Hin = p.Hin[:-1].copy(); p_drop.Hout = p.Hout[:-1].copy()
                c = m.copy()
                c.paths[i] = p_drop
                out.append(c)
                pt = p_drop.A[0 if e == 0 else -1]
                for j, q in enumerate(m.paths):
                    if j != i and not q.closed:
                        for ej in (0, 1):
                            q_pt = q.A[0 if ej == 0 else -1]
                            if np.linalg.norm(pt - q_pt) <= 1.5 * max(p.w, q.w):
                                mid = 0.5 * (pt + q_pt)
                                c_snap = c.copy()
                                if e == 0:
                                    c_snap.paths[i].A[0] = mid; c_snap.paths[i].Hin[0] = mid; c_snap.paths[i].Hout[0] = mid
                                else:
                                    c_snap.paths[i].A[-1] = mid; c_snap.paths[i].Hin[-1] = mid; c_snap.paths[i].Hout[-1] = mid
                                if ej == 0:
                                    c_snap.paths[j].A[0] = mid; c_snap.paths[j].Hin[0] = mid; c_snap.paths[j].Hout[0] = mid
                                else:
                                    c_snap.paths[j].A[-1] = mid; c_snap.paths[j].Hin[-1] = mid; c_snap.paths[j].Hout[-1] = mid
                                out.append(FN.merge_corners(c_snap, [(i, e, j, ej)]))
    if jn["kind"] in ("X", "Y"):
        ends = jn["ends"]
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    out.append(FN.join_pairs(m, [(ia, ea, ib, eb)]))
    if reason == "lump":
        for i, e in jn["ends"]:
            for f in (0.5, 0.9, 1.4):
                c = FN.move_end(m, i, e, f * m.paths[i].w)
                if c is not None:
                    out.append(c)
    if reason == "nub":
        for i, e in jn["ends"]:
            r = FN.best_end_move(m, i, e, m.paths[i].w)
            if r is not None:
                out.append(r[0])
            for f in (0.5, 1.0, 1.5, 2.0):
                c = FN.move_end(m, i, e, f * m.paths[i].w)
                if c is not None:
                    out.append(c)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "nub", "corner_split"):
        ends = jn["ends"]
        pairs_to_merge = []
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        pairs_to_merge.append((ia, ea, ib, eb))
        if len(pairs_to_merge) > 1:
            try:
                out.append(FN.merge_corners(m, pairs_to_merge))
            except Exception:
                pass
    return out


TOOLS = dict(shape_builder=tool_shape_builder, line_arc=tool_line_arc, pen=tool_pen)


# ------------------------------------------------------------------ driver
def run(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_rounds=6, max_tries=60, skip=()):
    """Returns (model, ink, soft, report). report = dict(joints, bad_before, bad_after, fixed, items=[...], rounds)."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    start = cur
    topo0 = FN._topo(model)
    joints = inspect(model, D, ink)
    drift_cap = max(0.025 * max(doctor.area, 1), 1.5 * len(joints) * (w ** 2))
    rep = dict(joints=len(joints), bad_before=bad_count(joints), bad_after=bad_count(joints), fixed=0, tries=0, rounds=0, items=[])
    tries = 0
    given_up = set()  # joins no tool could improve (keyed by rounded position)
    for rnd in range(max_rounds):
        rep["rounds"] = rnd + 1
        progress = False
        while time_ok() and tries < max_tries:
            todo = [j for j in joints if j["reasons"] and (round(j["x"]), round(j["y"])) not in given_up]
            if not todo:
                break
            # structural joins first (cut strokes, corners, hubs), then ends landing on a stroke: snapping the ends of a cut stroke
            # onto the crossing centerline would otherwise hide that it is still two pieces
            j0 = min(todo, key=lambda j: ("XLYT".index(j["kind"]), -len(j["reasons"])))
            base_bad = bad_count(joints)
            done = None
            for reason in list(j0["reasons"]):
                if reason in ("nub", "lump", "hole") and j0["kind"] in ("L", "Y") and ("corner_split" in j0["reasons"] or "y_spread" in j0["reasons"]):
                    continue  # at a corner / hub the structural fix (merge, common point) removes these; trimming first only makes it worse
                for tool in PLAN.get(reason, ()):
                    if tool in skip:
                        continue
                    best = None
                    for cand in TOOLS[tool](model, j0, reason, D=D):
                        if cand is None:
                            continue
                        tries += 1
                        ink2 = ink_of(cand)
                        s2 = doctor.soft(ink2)
                        t2 = FN._topo(cand)
                        if t2 > topo0:  # same weld fallback as the Finisher: a cut / merge may open a hairline gap
                            cw = T.weld_all(cand)
                            if FN._topo(cw) <= topo0:
                                cand = cw
                                ink2 = ink_of(cand)
                                s2 = doctor.soft(ink2)
                                t2 = FN._topo(cand)
                        if t2 > topo0:
                            continue
                        allow = (1.8 if j0["kind"] == "X" else 1.0) * j0["w"] ** 2
                        if s2 > cur + max(2.0, 0.003 * cur, allow) or (s2 - start) > drift_cap:
                            continue
                        jn2 = inspect(cand, D, ink2)
                        b2 = bad_count(jn2)
                        is_better = (b2 < base_bad) or (b2 <= base_bad and (len(cand.paths) < len(model.paths) or t2 < topo0))
                        if is_better:
                            key = (b2, t2, len(cand.paths), s2)
                            if best is None or key < best[0]:
                                best = (key, cand, ink2, s2, jn2)
                    if best is not None:
                        done = (tool, reason, best)
                        break
                if done:
                    break
            rep["items"].append(dict(kind=j0["kind"], x=j0["x"], y=j0["y"], reasons=list(j0["reasons"]), fixed=done is not None,
                                     tool=done[0] if done else None))
            if done:
                _, _, (key, cand, ink2, s2, jn2) = done
                model, ink, cur, joints = cand, ink2, s2, jn2
                topo0 = min(topo0, FN._topo(model))
                rep["fixed"] += 1
                progress = True
            else:
                given_up.add((round(j0["x"]), round(j0["y"])))
        if not progress:
            break
    rep["tries"] = tries
    rep["bad_after"] = bad_count(joints)
    rep["failing"] = [dict(kind=j["kind"], x=j["x"], y=j["y"], reasons=j["reasons"]) for j in joints if j["reasons"]]
    return model, ink, cur, rep
