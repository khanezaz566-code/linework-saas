"""Decision engine (v1.0): turns the last few percent of an icon into explained, verified decisions.

Why it exists
  Doctor / Finisher / Join / Structure all judge a fix by "does the render match the SOURCE PIXELS better".  When the source is
  blurry or wobbly the render copies it at 98-99 % and every "make it exact" fix looks like noise, so it is rejected and nothing
  ever reaches 100 %.  Measured on real sheets: pixel IoU is 98-99 % but almost no ink is more than 1.5 px away from the source -
  the remaining 1-2 % is edge fuzz.  The real defects are *intent* defects (a line that is 0.7 px off straight, a rect edge that is
  0.9 deg off vertical, a ring that is not exact, a sharp corner whose tip was cut off, an end that does not sit on the stroke
  it joins) and a few *hard residual* blobs (ink that really is missing / extra).

How it works  (the loop the owner described)
  1. MEASURE   fidelity (IoU / soft), hard residual (ink > tol px from the other side), intent findings.
  2. DIAGNOSE  every finding has a kind, a location, a severity and a reason ("why this is not 100 %").
  3. PRESCRIBE every fixable finding carries a command (a function Model -> Model); this is the "script" for the Edit engine.
  4. APPLY     commands go through the Edit engine operations (batch per kind, then one by one when the batch is refused).
  5. VERIFY    re-render, re-measure.  A candidate is kept only if (a) hard residual does not grow, (b) fidelity stays inside an
               explicit allowance (intent is a design goal, so a tiny pixel loss is allowed), (c) its own finding is really gone
               and no new finding appeared.
  6. LOOP      until no fixable finding is left or no round makes progress; what is left is classified as
               `source_noise` (we could not prove it is our fault) or `unresolved` (needs retrace / review).
Cleanliness = number of findings that are still open.  An icon is "done" when cleanliness == 0 and fidelity >= floor.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
import numpy as np
import cv2
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from .model import Model, Path
from .render import render_gray
from . import edit as E

# ----------------------------------------------------------------------------------------------- tunables
AXIS_DEG = 1.6          # a straight edge this close to 0/90 deg is meant to be axis aligned
STRAIGHT_PX = 1.0       # a cubic whose control offset is below this (scaled by length) is meant to be a line
EDGE_TOL = 1.0          # px: ink further than this from the other side is a hard residual, closer is edge fuzz
BLOB_MIN = 6            # px^2: smaller hard residual blobs are ignored
SOFT_ALLOW_FRAC = 0.02  # intent fixes may cost this fraction of the current soft mismatch (design goal beats pixel copy)
SOFT_ALLOW_MIN = 12.0   # ... but at least this many px of soft mismatch
MAX_ML = 12.0
SHARP_FACTOR = 1.3      # corner counts as pointed when source ink exists this many round-join radii out (strict variant: full mitre tip)


# ----------------------------------------------------------------------------------------------- measurement
def _ink(model: Model):
    g = render_gray(model.svg(), model.width, model.height)
    return (255 - g.astype(np.float32)) / 255


def hard_masks(D, ink, tol=EDGE_TOL):
    """(miss, extra) boolean masks: source ink with no render ink within tol px, render ink with no source ink within tol px."""
    S = np.asarray(D) > 0.5
    R = ink > 0.5
    dS = ndi.distance_transform_edt(~S)
    dR = ndi.distance_transform_edt(~R)
    return S & (dR > tol), R & (dS > tol)


def blobs(mask, min_area=BLOB_MIN):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a >= min_area:
            out.append(dict(area=int(a), box=(int(x), int(y), int(x + w), int(y + h)), xy=(float(cen[i][0]), float(cen[i][1]))))
    return sorted(out, key=lambda b: -b["area"])


@dataclass
class Score:
    iou: float
    soft: float           # sum |render - source| in px
    hard: int             # hard residual area at EDGE_TOL
    miss: int
    extra: int

    def d(self):
        return dict(iou=round(self.iou, 5), soft=round(self.soft, 1), hard=self.hard, miss=self.miss, extra=self.extra)


def measure(model: Model, D, ink=None) -> Score:
    ink = _ink(model) if ink is None else ink
    D = np.asarray(D, np.float32)
    b, r = ink > 0.5, D > 0.5
    iou = float((b & r).sum() / max((b | r).sum(), 1))
    miss, extra = hard_masks(D, ink)
    return Score(iou, float(np.abs(ink - D).sum()), int(miss.sum() + extra.sum()), int(miss.sum()), int(extra.sum()))


# ----------------------------------------------------------------------------------------------- findings
@dataclass
class Finding:
    kind: str                 # straight | axis | ring | arc | tip | gap | miss | extra
    path: int | None
    xy: tuple
    sev: float                # px of deviation / px^2 of area
    why: str
    fix: object = None        # callable(Model) -> Model, or None when only a diagnosis is possible
    box: tuple | None = None
    resolved: bool = False
    note: str = ""

    def d(self):
        return dict(kind=self.kind, path=self.path, x=round(self.xy[0], 1), y=round(self.xy[1], 1), sev=round(float(self.sev), 2), why=self.why, resolved=self.resolved, note=self.note)


def _chord_dev(c):
    ch = c[3] - c[0]
    L = float(np.linalg.norm(ch))
    if L < 1e-6:
        return L, 0.0
    n = np.array([-ch[1], ch[0]]) / L
    return L, 0.75 * max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n))


def _seg_is_line(c):
    L, dev = _chord_dev(c)
    return L >= 4 and dev <= max(0.35, min(STRAIGHT_PX, 0.006 * L))


def _seg_exact(c):
    ch = c[3] - c[0]
    return np.linalg.norm(c[1] - (c[0] + ch / 3)) < 0.02 and np.linalg.norm(c[2] - (c[0] + 2 * ch / 3)) < 0.02


def _line_flags(p: Path):
    return [_seg_is_line(c) for c in p.segs()]


def _set_line(p: Path, k):
    v = p.A[k + 1] - p.A[k]
    p.Hout[k] = p.A[k] + v / 3
    p.Hin[k + 1] = p.A[k] + 2 * v / 3


def _move_anchor(p: Path, i, new):
    new = np.asarray(new, float)
    idxs = [i]
    if p.closed and len(p.A) > 1:
        if i == 0:
            idxs.append(len(p.A) - 1)
        elif i == len(p.A) - 1:
            idxs.append(0)
    d = new - p.A[i]
    for j in idxs:
        p.A[j] = p.A[j] + d
        p.Hin[j] = p.Hin[j] + d
        p.Hout[j] = p.Hout[j] + d


def _angle_to_axis(v):
    a = np.degrees(np.arctan2(v[1], v[0])) % 180.0
    return min(a, abs(a - 90.0), abs(a - 180.0)), ("h" if min(a, abs(a - 180.0)) < abs(a - 90.0) else "v")


# ---- straight
def find_straight(model: Model):
    out = []
    for i, p in enumerate(model.paths):
        for k, c in enumerate(p.segs()):
            if _seg_is_line(c) and not _seg_exact(c):
                L, dev = _chord_dev(c)
                mid = (c[0] + c[3]) / 2
                out.append(Finding("straight", i, tuple(mid), dev, "cubic is %.2f px off a straight line over %.0f px but is not exactly straight" % (dev, L),
                                   fix=_fix_straight(i)))
    return _one_per_path(out)


def _fix_straight(i):
    def fix(m):
        m = m.copy()
        p = m.paths[i]
        for k, c in enumerate(p.segs()):
            if _seg_is_line(c):
                _set_line(p, k)
        return m
    return fix


# ---- axis
def find_axis(model: Model):
    out = []
    for i, p in enumerate(model.paths):
        segs = p.segs()
        for k, c in enumerate(segs):
            if not _seg_is_line(c):
                continue
            L = float(np.linalg.norm(c[3] - c[0]))
            if L < 3 * p.w:
                continue
            dev, _ = _angle_to_axis(c[3] - c[0])
            if 0.02 < dev <= AXIS_DEG:
                mid = (c[0] + c[3]) / 2
                out.append(Finding("axis", i, tuple(mid), dev, "straight edge of %.0f px is %.2f deg off the grid (0/90)" % (L, dev), fix=_fix_axis(i)))
    return _one_per_path(out)


def _fix_axis(i):
    def fix(m):
        m = m.copy()
        p = m.paths[i]
        n = len(p.A)
        flags = _line_flags(p)
        last = n - 1 if not p.closed else n - 2          # closed paths repeat the first anchor at the end
        for _ in range(3):
            for k, c in enumerate(p.segs()):
                if not flags[k] or np.linalg.norm(p.A[k + 1] - p.A[k]) < 3 * p.w:
                    continue
                dev, kind = _angle_to_axis(p.A[k + 1] - p.A[k])
                if dev > AXIS_DEG:
                    continue
                a, b = p.A[k].copy(), p.A[k + 1].copy()
                if kind == "h":
                    y = (a[1] + b[1]) / 2
                    _move_anchor(p, k, (a[0], y))
                    _move_anchor(p, k + 1, (b[0], y))
                else:
                    x = (a[0] + b[0]) / 2
                    _move_anchor(p, k, (x, a[1]))
                    _move_anchor(p, k + 1, (x, b[1]))
        for k, f in enumerate(flags):
            if f:
                _set_line(p, k)
        return m
    return fix


def _one_per_path(fs):
    best = {}
    for f in fs:
        if f.path not in best or f.sev > best[f.path].sev:
            best[f.path] = f
    return list(best.values())


# ---- ring / arc
def find_rings(model: Model, D):
    out = []
    for i, p in enumerate(model.paths):
        if p.closed:
            q = E.circle(model, i, robust=True)
            if q.paths[i] is not model.paths[i] and not _same(q.paths[i], model.paths[i]):
                dev = _dev_between(p, q.paths[i])
                out.append(Finding("ring", i, tuple(p.A[0]), dev, "closed path is a ring within %.2f px but stored as a free curve" % dev, fix=_fix_ring(i)))
        else:
            from . import finisher as FN
            q = FN.arc_fit(p)
            if q is not None and not _same(q, p):
                dev = _dev_between(p, q)
                out.append(Finding("arc", i, tuple(p.A[len(p.A) // 2]), dev, "open path is one circular arc within %.2f px but stored as a free curve" % dev, fix=_fix_arc(i)))
    return out


def _same(a: Path, b: Path):
    return len(a.A) == len(b.A) and np.allclose(a.A, b.A, atol=0.02) and np.allclose(a.Hout, b.Hout, atol=0.02) and np.allclose(a.Hin, b.Hin, atol=0.02)


def _dev_between(a: Path, b: Path):
    return float(cKDTree(b.flat(0.5)).query(a.flat(1.0))[0].max())


def _fix_ring(i):
    return lambda m: E.circle(m, i, robust=True)


def _fix_arc(i):
    def fix(m):
        from . import finisher as FN
        m = m.copy()
        q = FN.arc_fit(m.paths[i])
        if q is not None:
            m.paths[i] = q
        return m
    return fix


# ---- tips (sharp corners whose apex was cut off by a round join)
def _corner_info(p: Path, min_turn=20.0):
    """Corners of a path as (xy, turn_deg, miter_ratio_needed).  Directions are measured on the flattened curve over ~0.6 w on each
    side of the anchor, so duplicate anchors / zero-length segments / noisy handles cannot fake a hairpin."""
    f = p.flat(0.5)
    n = len(f)
    r = max(3, int(0.6 * p.w / 0.5))
    if n < 2 * r + 2:
        return []
    out = []
    for k in range(len(p.A)):
        if not p.closed and k in (0, len(p.A) - 1):
            continue
        idx = int(np.argmin(np.linalg.norm(f - p.A[k], axis=1)))
        if p.closed:
            a, b = f[(idx - r) % n], f[(idx + r) % n]
        else:
            if idx - r < 0 or idx + r >= n:
                continue
            a, b = f[idx - r], f[idx + r]
        din, dout = f[idx] - a, b - f[idx]
        la, lb = np.linalg.norm(din), np.linalg.norm(dout)
        if la < 1e-6 or lb < 1e-6:
            continue
        turn = float(np.degrees(np.arccos(np.clip(din @ dout / (la * lb), -1, 1))))
        if turn < min_turn:
            continue
        c = p.A[k].copy()
        if any(np.linalg.norm(c - o[0]) < 1.5 for o in out):          # duplicate anchor of the same corner
            continue
        out.append((c, turn, 1.0 / max(np.sin(np.radians(180.0 - turn) / 2), 0.08)))
    return out


# ---- corners: the skeleton rounds / displaces a sharp corner; the design intent is the intersection of the two edges
def _circ(p: Path):
    """Anchors of a path without the repeated closing anchor, as (A, Hin, Hout)."""
    if p.closed and len(p.A) > 1 and np.linalg.norm(p.A[0] - p.A[-1]) < 1e-6:
        return p.A[:-1].copy(), p.Hin[:-1].copy(), p.Hout[:-1].copy()
    return p.A.copy(), p.Hin.copy(), p.Hout.copy()


def _build(A, Hin, Hout, tmpl: Path):
    if tmpl.closed:
        A, Hin, Hout = np.vstack([A, A[:1]]), np.vstack([Hin, Hin[:1]]), np.vstack([Hout, Hout[:1]])
    return Path(A, Hin, Hout, tmpl.w, tmpl.join, tmpl.ml, tmpl.closed)


def _seg(A, Hin, Hout, i, n, closed):
    j = (i + 1) % n
    return np.array([A[i], Hout[i], Hin[j], A[j]])


def _dedupe(A, Hin, Hout, closed, tol=1.2):
    keep = [0]
    for k in range(1, len(A)):
        if np.linalg.norm(A[k] - A[keep[-1]]) < tol:
            Hout[keep[-1]] = Hout[k]                       # merged anchor keeps the outgoing handle of the later one
        else:
            keep.append(k)
    if closed and len(keep) > 3 and np.linalg.norm(A[keep[-1]] - A[keep[0]]) < tol:
        Hin[keep[0]] = Hin[keep[-1]]
        keep.pop()
    return A[keep], Hin[keep], Hout[keep]


def _isect(p0, d0, p1, d1):
    den = d0[0] * d1[1] - d0[1] * d1[0]
    if abs(den) < 1e-6:
        return None
    t = ((p1[0] - p0[0]) * d1[1] - (p1[1] - p0[1]) * d1[0]) / den
    return p0 + t * d0


def _runs(A, Hin, Hout, closed, w):
    """Edges of the drawing: maximal stretches of consecutive segments whose flattened curve stays within 0.08 w of the chord
    from the stretch's first to last anchor (so noisy handles / extra anchors on a straight side do not break it)."""
    n = len(A)
    nseg = n if closed else n - 1
    segs = [_seg(A, Hin, Hout, i, n, closed) for i in range(nseg)]
    if nseg == 0:
        return segs, []
    tol = max(0.5, 0.08 * w)
    flats = []
    for c in segs:
        t = np.linspace(0, 1, 12)
        mt = 1 - t
        flats.append((mt**3)[:, None] * c[0] + (3 * mt**2 * t)[:, None] * c[1] + (3 * mt * t**2)[:, None] * c[2] + (t**3)[:, None] * c[3])

    def ok_run(s0, cnt):
        pts = np.vstack([flats[(s0 + t) % nseg] for t in range(cnt)])
        a, b = pts[0], pts[-1]
        v = b - a
        L = np.linalg.norm(v)
        if L < 1e-6:
            return False
        nrm = np.array([-v[1], v[0]]) / L
        dev = np.abs((pts - a) @ nrm)
        along = (pts - a) @ (v / L)
        return bool(dev.max() <= tol and along.min() >= -tol and along.max() <= L + tol)

    # start the scan at the sharpest anchor so that no edge is cut by the seam of a closed path
    start = 0
    if closed:
        best = -1.0
        for k in range(nseg):
            d_in = segs[(k - 1) % nseg][3] - segs[(k - 1) % nseg][0]
            d_out = segs[k][3] - segs[k][0]
            ln, lo = np.linalg.norm(d_in), np.linalg.norm(d_out)
            if ln < 1e-6 or lo < 1e-6:
                continue
            tr = float(np.degrees(np.arccos(np.clip(d_in @ d_out / (ln * lo), -1, 1))))
            if tr > best:
                best, start = tr, k
    order = [(start + t) % nseg for t in range(nseg)] if closed else list(range(nseg))
    runs, pos = [], 0
    while pos < nseg:
        s0 = order[pos]
        cnt = 1
        if not ok_run(s0, 1):
            pos += 1
            continue
        while pos + cnt < nseg and ok_run(s0, cnt + 1):
            cnt += 1
        s1 = (s0 + cnt - 1) % nseg
        a_i, b_i = s0 % n, (s1 + 1) % n
        L = float(np.linalg.norm(A[b_i] - A[a_i]))
        if L >= 1.5 * w:
            runs.append(dict(s0=s0, s1=s1, a=a_i, b=b_i, dir=(A[b_i] - A[a_i]) / L, length=L))
        pos += cnt
    return segs, runs


def corner_candidates(p: Path):
    """Returns A, Hin, Hout (deduplicated, no repeated closing anchor) and a list of corner dicts (r1, r2, V, turn, first, last, d1, d2)."""
    A, Hin, Hout = _dedupe(*_circ(p), p.closed)
    n = len(A)
    if n < 3:
        return A, Hin, Hout, []
    w = p.w
    segs, runs = _runs(A, Hin, Hout, p.closed, w)
    nseg = len(segs)
    out = []
    for ri, r1 in enumerate(runs):
        if ri + 1 < len(runs):
            r2 = runs[ri + 1]
        elif p.closed and len(runs) > 1:
            r2 = runs[0]
        else:
            continue
        k, tot, guard = r1["s1"] + 1, 0.0, 0
        while k % nseg != r2["s0"] % nseg and guard <= nseg:
            c = segs[k % nseg]
            tot += float(np.linalg.norm(c[3] - c[0]))
            k += 1
            guard += 1
        if guard > nseg or tot > 3 * w:
            continue
        d1, d2 = r1["dir"], r2["dir"]
        turn = float(np.degrees(np.arccos(np.clip(d1 @ d2, -1, 1))))
        if turn < 25 or turn > 155:
            continue
        V = _isect(A[r1["a"]], d1, A[r2["a"]], d2)
        if V is None:
            continue
        first, last = r1["b"], r2["a"]
        if np.linalg.norm(V - A[first]) > 2.5 * w or np.linalg.norm(V - A[last]) > 2.5 * w:
            continue
        out.append(dict(r1=r1, r2=r2, V=V, turn=turn, first=first, last=last, d1=d1, d2=d2))
    return A, Hin, Hout, out


def _sharp_in_source(D, V, d1, d2, w, turn):
    """Evidence from the SOURCE that this corner is sharp (mitre) and not rounded: ink at the mitre tip, 0.9 of the way out."""
    inter = max(np.sin(np.radians(180.0 - turn) / 2), 0.08)
    out = d1 / np.linalg.norm(d1) - d2 / np.linalg.norm(d2)
    n = np.linalg.norm(out)
    if n < 1e-6:
        return False
    out /= n
    # a round join reaches w/2 from the vertex; ink clearly beyond that (1.3 x) proves the corner is pointed, even if the source tip is truncated
    T = V + out * min((w / 2) / inter * 0.9, SHARP_FACTOR * (w / 2))
    H, W = D.shape
    x, y = int(round(T[0])), int(round(T[1]))
    if not (1 <= x < W - 1 and 1 <= y < H - 1):
        return False
    return bool((D[y - 1:y + 2, x - 1:x + 2] > 0.5).any())


def _positive_corners(p: Path, D):
    A, Hin, Hout, cands = corner_candidates(p)
    res = []
    for c in cands:
        if _sharp_in_source(D, c["V"], c["d1"], c["d2"], p.w, c["turn"]):
            res.append(dict(c, disp=float(np.linalg.norm(c["V"] - A[c["first"]])),
                            ml=1.0 / max(np.sin(np.radians(180.0 - c["turn"]) / 2), 0.08)))
    return res


def find_corners(model: Model, D):
    """Vertex restore: the anchor of a sharp corner must sit on the intersection of its two edges (the skeleton displaces it)."""
    out = []
    for i, p in enumerate(model.paths):
        pos = [c for c in _positive_corners(p, D) if c["disp"] >= 0.8]
        if not pos:
            continue
        worst = max(c["disp"] for c in pos)
        out.append(Finding("corner", i, tuple(pos[0]["V"]), worst,
                           "%d sharp corner(s) whose vertex is up to %.1f px off the intersection of its two edges" % (len(pos), worst), fix=_fix_corner(i, D)))
    return out


def _fix_corner(i, D):
    def fix(m):
        m = m.copy()
        p = m.paths[i]
        pos = [c for c in _positive_corners(p, D) if c["disp"] >= 0.8]
        if not pos:
            return m
        A, Hin, Hout, _ = corner_candidates(p)
        n = len(A)
        A2, Hi2, Ho2 = A.copy(), Hin.copy(), Hout.copy()
        drop = set()
        for c in pos:
            V, first, last = c["V"], c["first"], c["last"]
            s_last, s_first = c["r1"]["s1"] % n, c["r2"]["s0"] % n
            e_next = (s_first + 1) % n
            idx = [first]
            while idx[-1] != last and len(idx) <= n:
                idx.append((idx[-1] + 1) % n)
            A2[first] = V
            Hi2[first] = V - (V - A[s_last]) / 3.0
            Ho2[first] = V + (A[e_next] - V) / 3.0
            Ho2[s_last] = A[s_last] + (V - A[s_last]) / 3.0
            Hi2[e_next] = A[e_next] - (A[e_next] - V) / 3.0
            drop |= set(idx[1:])
        keepi = [k for k in range(n) if k not in drop]
        m.paths[i] = _build(A2[keepi], Hi2[keepi], Ho2[keepi], p)
        return m
    return fix


# ---- tip patches: a sharp corner needs its own join (miter / bevel) although the rest of its path is round
def find_tips(model: Model, D, miss_blobs):
    """One finding per sharp corner that has source-only ink next to its apex.  The prescription adds a short 3-anchor stub
    (arms 1.6 w along the two edges, centreline identical to the main path) with a join chosen for THIS corner by rendering both
    options; the arms lie inside the main stroke, only the apex differs."""
    out = []
    if not miss_blobs:
        return out
    for i, p in enumerate(model.paths):
        for c in _positive_corners(p, D):
            V = c["V"]
            near = [b for b in miss_blobs if np.hypot(b["xy"][0] - V[0], b["xy"][1] - V[1]) <= 1.8 * p.w + 3]
            if not near:
                continue
            out.append(Finding("tip", i, tuple(V), sum(b["area"] for b in near),
                               "sharp corner of %.0f deg loses its apex (%d px^2 of source ink missing) because its path uses a %s join" % (180 - c["turn"], sum(b["area"] for b in near), p.join),
                               fix=_fix_tip(i, V, c["d1"], c["d2"], c["ml"], D)))
    return out


def _tip_patch(w, V, d1, d2, join, ml):
    L = 1.6 * w
    P0, P2 = V - d1 * L, V + d2 * L
    A = np.array([P0, V, P2])
    Ho = np.array([P0 + (V - P0) / 3, V + (P2 - V) / 3, P2])
    Hi = np.array([P0, V - (V - P0) / 3, P2 - (P2 - V) / 3])
    return Path(A, Hi, Ho, w, join, ml, False, tag="tip_patch")


def _fix_tip(i, V, d1, d2, ratio, D):
    def fix(m):
        base = measure(m, D)
        best, best_h = None, base.hard
        w = m.paths[i].w
        for join, ml in (("miter", min(MAX_ML, ratio * 1.03 + 0.05)), ("bevel", 4.0)):
            t = m.copy()
            t.paths.append(_tip_patch(w, V, d1, d2, join, ml))
            h = measure(t, D).hard
            if h < best_h:
                best, best_h = t, h
        if m.paths[i].join != "miter":                      # whole-path miter: right when every corner of the path is pointed
            t = m.copy()
            t.paths[i].join, t.paths[i].ml = "miter", min(MAX_ML, ratio * 1.03 + 0.05)
            h = measure(t, D).hard
            if h < best_h:
                best, best_h = t, h
        return best if best is not None else m
    return fix


# ---- gaps: an open end does not sit exactly on the centreline of the stroke it joins
def _end_dir(p: Path, e):
    """Unit direction in which the stroke leaves the path at end e (measured over ~1.5 w, so a hooked last pixel does not matter)."""
    f = p.flat(0.5)
    k = max(3, int(1.5 * p.w / 0.5))
    k = min(k, len(f) - 1)
    v = (f[0] - f[k]) if e == 0 else (f[-1] - f[-1 - k])
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else None


def _ray_hit(X, d, poly, tmax):
    """Smallest |t| (t signed) where the line X + t d crosses polyline `poly`, |t| <= tmax."""
    best = None
    a, b = poly[:-1], poly[1:]
    e = b - a
    den = d[0] * (-e[:, 1]) + d[1] * e[:, 0]
    ok = np.abs(den) > 1e-9
    w = a - X
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (w[:, 0] * (-e[:, 1]) + w[:, 1] * e[:, 0]) / den
        u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den
    good = ok & (u >= -1e-6) & (u <= 1 + 1e-6) & (np.abs(t) <= tmax)
    if not good.any():
        return None
    k = np.where(good)[0][np.argmin(np.abs(t[good]))]
    return float(t[k]), X + t[k] * d


def find_gaps(model: Model, D):
    out = []
    from . import joints as JN
    flats = [p.flat(0.5) for p in model.paths]
    for i, p in enumerate(model.paths):
        if p.closed:
            continue
        for e in (0, 1):
            X = JN._end_pt(p, e).copy()
            d = _end_dir(p, e)
            if d is None:
                continue
            best = None
            for j, f in enumerate(flats):
                if j == i:
                    continue
                if np.linalg.norm(f - X, axis=1).min() > 1.4 * p.w + 2:
                    continue
                h = _ray_hit(X, d, f, 1.3 * p.w + 2)
                if h is not None and (best is None or abs(h[0]) < abs(best[0])):
                    best = (h[0], h[1], j)
            if best is None:
                continue
            t, Q, j = best
            if abs(t) >= 0.7 and _support(D, X, Q) >= 0.9:
                out.append(Finding("gap", i, tuple(X), abs(t), "end of path %d is %.1f px %s the centreline of path %d (should end exactly on it)" % (i, abs(t), "short of" if t > 0 else "past", j), fix=_fix_gap(i, e, Q)))
    return out


def _support(D, a, b, n=14):
    t = np.linspace(0, 1, n)
    P = a[None] * (1 - t[:, None]) + b[None] * t[:, None]
    H, W = D.shape
    x = np.clip(np.round(P[:, 0]).astype(int), 0, W - 1)
    y = np.clip(np.round(P[:, 1]).astype(int), 0, H - 1)
    return float((D[y, x] > 0.5).mean())


def _fix_gap(i, e, Q):
    def fix(m):
        from . import joints as JN
        m = m.copy()
        JN._set_end(m.paths[i], e, Q)
        return m
    return fix


# ---- hard residual blobs
def find_residual(model: Model, D, ink):
    miss, extra = hard_masks(D, ink)
    out = []
    for kind, mk in (("miss", miss), ("extra", extra)):
        for b in blobs(mk):
            out.append(Finding(kind, None, b["xy"], b["area"], "%d px^2 of %s ink further than %.1f px from the other side" % (b["area"], "source-only" if kind == "miss" else "render-only", EDGE_TOL),
                               fix=_fix_region(b["box"], D), box=b["box"]))
    return out, blobs(miss)


def _fix_region(box, D):
    return lambda m: E.refine_region(m, D, box)


# ----------------------------------------------------------------------------------------------- audit
KIND_ORDER = ["ring", "arc", "straight", "axis", "corner", "tip", "gap", "miss", "extra"]
INTENT = {"ring", "arc", "straight", "axis", "gap", "tip", "corner"}


def audit(model: Model, D, ink=None, tip_patches=True):
    ink = _ink(model) if ink is None else ink
    res, miss_blobs = find_residual(model, D, ink)
    fs = []
    fs += find_rings(model, D)
    fs += find_corners(model, D)
    if tip_patches:
        fs += find_tips(model, D, miss_blobs)
    fs += find_straight(model)
    fs += find_axis(model)
    fs += find_gaps(model, D)
    fs += res
    return fs


# ----------------------------------------------------------------------------------------------- the loop
IOU_STEP_KIND = {"straight": 0.0015, "axis": 0.0015, "ring": 0.003, "arc": 0.003, "gap": 0.002, "tip": 0.006, "corner": 0.006}
IOU_STEP = 0.003       # one intent fix may cost at most this much IoU ...
IOU_TOTAL = 0.006       # ... and the whole decision pass at most this much (intent is a design goal, pixels are a blurry copy)
HARD_SLACK = {"ring": 8, "arc": 8, "straight": 2, "axis": 2, "gap": 1, "tip": 2, "corner": 2}


def _accept(kind, old: Score, new: Score, first: Score | None = None):
    """Intent fixes are judged on STRUCTURE (hard residual must not grow beyond a tiny slack) and on a bounded fidelity loss,
    not on the soft pixel sum: a 0.3 px straightening legitimately moves the soft sum by tens of px of edge fuzz."""
    if kind in ("miss", "extra"):
        return new.hard < old.hard and new.soft <= old.soft + max(40.0, 0.03 * old.soft) and (first is None or new.iou >= first.iou - IOU_TOTAL)
    if new.hard > old.hard + HARD_SLACK.get(kind, 2):
        return False
    if first is not None and new.hard > first.hard + 4:     # slack must not accumulate over many small decisions
        return False
    if new.iou < old.iou - IOU_STEP_KIND.get(kind, IOU_STEP):
        return False
    if first is not None and new.iou < first.iou - IOU_TOTAL:
        return False
    if kind == "tip":
        return new.hard < old.hard
    if kind == "corner":
        return new.hard <= old.hard
    return True


def decide(model: Model, D, max_rounds=6, time_budget=None, emit=lambda **k: None, name="icon", tip_patches=True):
    """Run the decision loop. Returns (model, report)."""
    t0 = time.time()
    D = np.asarray(D, np.float32)
    cur = model
    ink = _ink(cur)
    sc = measure(cur, D, ink)
    first = sc
    first_findings = audit(cur, D, ink, tip_patches=tip_patches)
    log = []
    refused = {}
    stuck = set()                       # (kind, path, rounded xy) refused once: do not try again
    rounds = 0
    for rnd in range(max_rounds):
        rounds = rnd + 1
        if time_budget and time.time() - t0 > time_budget:
            break
        fs = [f for f in audit(cur, D, ink, tip_patches=tip_patches) if (f.kind, f.path, round(f.xy[0] / 4), round(f.xy[1] / 4)) not in stuck and f.fix is not None]
        if not fs:
            break
        progressed = False
        for kind in KIND_ORDER:
            group = [f for f in fs if f.kind == kind]
            if not group:
                continue
            # batch first (all fixes of the kind at once), then one by one
            if kind not in ("miss", "extra") and len(group) > 1:
                cand = cur
                for f in group:
                    cand = f.fix(cand)
                cand_ink = _ink(cand)
                ns = measure(cand, D, cand_ink)
                if _accept(kind, sc, ns, first):
                    log.append(dict(round=rnd, kind=kind, n=len(group), how="batch", before=sc.d(), after=ns.d()))
                    cur, ink, sc, progressed = cand, cand_ink, ns, True
                    continue
            for f in group:
                try:
                    cand = f.fix(cur)
                except Exception as ex:                      # a broken prescription must never break the icon
                    stuck.add((f.kind, f.path, round(f.xy[0] / 4), round(f.xy[1] / 4)))
                    continue
                cand_ink = _ink(cand)
                ns = measure(cand, D, cand_ink)
                if _accept(kind, sc, ns, first):
                    log.append(dict(round=rnd, kind=kind, path=f.path, x=round(f.xy[0], 1), y=round(f.xy[1], 1), how="single", why=f.why, before=sc.d(), after=ns.d()))
                    cur, ink, sc, progressed = cand, cand_ink, ns, True
                    break                                    # geometry changed: re-audit before the next decision
                stuck.add((f.kind, f.path, round(f.xy[0] / 4), round(f.xy[1] / 4)))
                refused[(f.kind, f.path, round(f.xy[0] / 4), round(f.xy[1] / 4))] = dict(why=f.why, before=sc.d(), after=ns.d())
            if progressed and kind in ("miss", "extra"):
                break
        emit(engine="decision", msg="round %d: IoU %.4f hard %d" % (rnd + 1, sc.iou, sc.hard), icon=name, t=round(time.time() - t0, 2))
        if not progressed:
            break

    final = audit(cur, D, ink, tip_patches=tip_patches)
    open_f, waived = [], []
    for f in final:
        r = refused.get((f.kind, f.path, round(f.xy[0] / 4), round(f.xy[1] / 4)))
        if r and f.kind in INTENT and r["after"]["hard"] > r["before"]["hard"] + HARD_SLACK.get(f.kind, 2):
            # proof: applying the "ideal" geometry makes the render disagree with the source by more than edge fuzz,
            # so the current geometry is what the source shows.  Recorded, not hidden, but it is not a defect.
            f.resolved = True
            f.note = "waived: ideal geometry would add %d px^2 of hard residual (source disagrees)" % (r["after"]["hard"] - r["before"]["hard"])
            waived.append(f)
            continue
        if r:
            f.note = "refused: soft %+.1f hard %+d" % (r["after"]["soft"] - r["before"]["soft"], r["after"]["hard"] - r["before"]["hard"])
        elif f.kind in ("miss", "extra"):
            f.note = "unresolved: needs retrace / review"
        elif f.kind in INTENT:
            f.note = "open: fix refused by verification (would cost more fidelity than allowed or break another finding)"
        open_f.append(f)
    miss, extra = hard_masks(D, ink, EDGE_TOL)
    fuzz = int(((ink > 0.5) ^ (D > 0.5)).sum()) - sc.hard
    report = dict(
        rounds=rounds, seconds=round(time.time() - t0, 2),
        before=first.d(), after=sc.d(),
        found=len(first_findings), applied=len(log), open=len(open_f), waived=len(waived),
        cleanliness=len(open_f),
        edge_fuzz_px=max(fuzz, 0),                           # pixels that differ only by <= EDGE_TOL: anti-alias / blur, not our fault
        log=log, open_findings=[f.d() for f in open_f], waived_findings=[f.d() for f in waived],
        first_findings=[f.d() for f in first_findings],
    )
    return cur, report


def icon_ok(report, ink_area=None, iou_floor=0.955):
    """Sheet-level gate. An icon passes when its structural residual is edge fuzz only: hard residual <= 0.1 % of the source ink
    (or 8 px^2), no single miss/extra blob above 30 px^2 is still open, and fidelity is above the floor."""
    lim = max(8, int(0.001 * ink_area)) if ink_area else 8
    big = [f for f in report["open_findings"] if f["kind"] in ("miss", "extra") and f["sev"] > 30]
    return report["after"]["hard"] <= lim and not big and report["after"]["iou"] >= iou_floor


def decide_best(model: Model, D, **kw):
    """Run the loop with a loose and a strict notion of 'pointed corner' and keep the better result (never worse than the input)."""
    global SHARP_FACTOR
    keep = SHARP_FACTOR
    best = None
    try:
        for fac in (1.3, 99.0):
            SHARP_FACTOR = fac
            m2, rep = decide(model, D, **kw)
            key = (rep["after"]["hard"] > rep["before"]["hard"] + 4, rep["after"]["hard"], rep["open"], -rep["after"]["iou"])
            if best is None or key < best[0]:
                rep["sharp_factor"] = fac
                best = (key, m2, rep)
    finally:
        SHARP_FACTOR = keep
    return best[1], best[2]
