"""Structure engine: finds places where the render's centre line differs from the source's (structure.compare) and tries stronger,
region-level repairs than the Finisher's local touches.  Every candidate is kept only if
  * the structure score (total severity, in stroke widths) goes down,
  * the soft mismatch does not get worse beyond a small tolerance,
  * the topology (gaps / notches / spurs) does not get worse.
Repairs, in order of strength, per site:
  snap     points of nearby strokes are pulled onto the source's centre line, then the displacement is smoothed   (lumps, jogs, displaced strokes)
  smooth   the nearby stroke is low-pass filtered along its length                                                  (wobble that follows a noisy source)
  retrace  the strokes inside the region are replaced by a fresh trace of the source                                (anything snap / smooth cannot save)
  width    the nearby stroke gets the source's local width                                                          (thick / thin sites)
Escalation: sites that survive all four are reported in `unresolved` so that the pipeline / UI / lessons can show and remember them.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from .model import Model, Path
from .geom import resample, fit_curve
from . import structure as ST
from . import topology as T
from . import finisher as FN


def _near_paths(m: Model, box, w, grow=1.5):
    x0, y0, x1, y1 = box[0] - grow * w, box[1] - grow * w, box[2] + grow * w, box[3] + grow * w
    out = []
    for i, p in enumerate(m.paths):
        f = p.flat(2.0)
        if ((f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)).any():
            out.append(i)
    return out


def _refit(p: Path, pts):
    segs = fit_curve(pts, 0.8, 0.45)
    if not segs:
        return None
    q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
    q.ml = p.ml
    return q


def _smooth_field(delta, weight, sigma, closed):
    mode = "wrap" if closed else "nearest"
    d = gaussian_filter1d(delta * weight[:, None], sigma, axis=0, mode=mode)
    wt = gaussian_filter1d(weight, sigma, mode=mode)
    return d / np.maximum(wt, 1e-6)[:, None] * np.clip(wt * 1.0, 0, 1)[:, None]


def _edit_path(p: Path, box, w, src_tree, src_pts, mode):
    f = resample(p.flat(), 0.75)
    if len(f) < 8:
        return None
    x0, y0, x1, y1 = box[0] - 1.5 * w, box[1] - 1.5 * w, box[2] + 1.5 * w, box[3] + 1.5 * w
    inb = ((f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)).astype(np.float64)
    if inb.sum() < 3:
        return None
    sig = max(1.0, (1.5 if mode == "snap" else 3.0) * w / 0.75)
    if mode == "snap":
        d, idx = src_tree.query(f)
        tgt = src_pts[idx]
        delta = np.where((d < 1.0 * w)[:, None], tgt - f, 0.0)
        delta = _smooth_field(delta, np.where(d < 1.0 * w, 1.0, 0.0) * inb + 1e-3, sig * 0.5, p.closed)
        g = f + delta * inb[:, None]
    else:
        sm = gaussian_filter1d(f, sig, axis=0, mode="wrap" if p.closed else "nearest")
        g = f + (sm - f) * gaussian_filter1d(inb, 2.0, mode="nearest")[:, None]
    if not p.closed:  # open stroke: keep its end points where they are
        g[0], g[-1] = f[0], f[-1]
    return _refit(p, g)


def _offset_path(p: Path, d):
    """Parallel copy of p, `d` px to the left of its direction of travel (closed or open)."""
    f = resample(p.flat(), 0.75)
    if len(f) < 8:
        return None
    t = np.gradient(f, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    n = np.c_[-t[:, 1], t[:, 0]]
    g = f + n * d
    q = _refit(p, g)
    return q


def double_candidates(m: Model, w, ratio=1.35):
    """Strokes much wider than the set stroke width are fused double lines: one candidate per path, replaced by two parallel strokes of width w."""
    out = []
    for i, p in enumerate(m.paths):
        if p.w > ratio * w and p.length() > 2.5 * w:
            d = (p.w - w) / 2.0
            a, b = _offset_path(p, d), _offset_path(p, -d)
            if a is None or b is None:
                continue
            a.w = b.w = float(w)
            m2 = m.copy()
            m2.paths[i] = a
            m2.paths.append(b)
            out.append((i, m2, 0.6 * w * p.length()))
    return out


def wobble_candidates(m: Model, w, sig=2.5, lo=0.05, hi=0.45):
    """Strokes whose centre line oscillates around its own smooth version (several sign changes, small amplitude): smooth them."""
    out = []
    for i, p in enumerate(m.paths):
        L = p.length()
        if L < 5 * w:
            continue
        f = resample(p.flat(), 0.75)
        if len(f) < 16:
            continue
        sm = gaussian_filter1d(f, sig * w / 0.75, axis=0, mode="wrap" if p.closed else "nearest")
        e = f - sm
        t = np.gradient(sm, axis=0)
        t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        lat = e[:, 0] * -t[:, 1] + e[:, 1] * t[:, 0]
        core = lat[int(2 * sig * w / 0.75): len(lat) - int(2 * sig * w / 0.75)] if not p.closed else lat
        if len(core) < 8:
            continue
        rms = float(np.sqrt((core ** 2).mean())) / w
        sgn = np.sign(core[np.abs(core) > 0.02 * w])
        zc = int((np.diff(sgn) != 0).sum()) if len(sgn) > 1 else 0
        if lo <= rms <= hi and zc >= max(4, int(L / (10 * w) * 4)):
            g = sm.copy()
            if not p.closed:
                k = int(2 * sig * w / 0.75)
                ramp = np.clip(np.arange(len(f)) / max(k, 1), 0, 1) * np.clip((len(f) - 1 - np.arange(len(f))) / max(k, 1), 0, 1)
                g = f + (sm - f) * ramp[:, None]
                g[0], g[-1] = f[0], f[-1]
            q = _refit(p, g)
            if q is not None:
                m2 = m.copy()
                m2.paths[i] = q
                out.append((i, m2, rms * w * L * 2.0))
    return out


def run_structure_engine(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_sites=8, memory_skip=()):
    """Returns (model, ink, soft, report) where report = dict(before, after, sites=[...], fixed, unresolved=[...])."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    res = ST.compare(D, ink, w)
    before = res["score"]
    st = dict(model=model, ink=ink, cur=cur, score=before, topo=FN._topo(model))
    start_soft = cur
    drift_cap = 0.008 * max(doctor.area, 1)
    sites, fixed = [], 0
    src_pts = ST.skeleton_points(D > 0.5, 2, prune_w=max(4, 0.7 * w * 2))
    src_tree = cKDTree(src_pts) if len(src_pts) else None
    tol = lambda c: max(3.0, 0.005 * c)
    # intent checks that do not depend on the source being right: fused double lines, wobbling centre lines
    intent = []
    for kind, fn in (("fused", double_candidates), ("wobble", wobble_candidates)):
        for i, c0, allow in fn(st["model"], w):
            if not time_ok():
                break
            if kind in memory_skip:
                continue
            cur_m = st["model"]
            c = c0 if len(cur_m.paths) == len(c0.paths) - (1 if kind == "fused" else 0) else None
            if c is None:
                continue
            ink2 = ink_of(c)
            s2 = doctor.soft(ink2)
            if s2 > st["cur"] + allow + tol(st["cur"]) or (s2 - start_soft) > drift_cap + allow:
                continue
            t2 = FN._topo(c)
            if t2 > st["topo"]:
                continue
            st.update(model=c, ink=ink2, cur=s2, topo=t2)
            fixed += 1
            intent.append(dict(kind=kind, x=float(c.paths[i].A[0][0]), y=float(c.paths[i].A[0][1]), severity=0.0, fixed=True, how=kind))
            if kind == "fused":
                break  # path indices changed; the next pass of the pipeline will pick the others up
    sites.extend(intent)
    st["score"] = ST.compare(D, st["ink"], w)["score"] if intent else st["score"]
    tried = 0
    queue = list(res["sites"][:max_sites])
    for s in queue:
        if not time_ok() or src_tree is None:
            break
        if tried >= max_sites:
            break
        tried += 1
        box = s["box"]
        near = _near_paths(st["model"], box, w)
        if not near or len(near) > 6:
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=False, how="none"))
            continue
        cands = []
        if s["kind"] in ("thick", "thin"):
            # local width correction (single stroke dominating the site only)
            if len(near) == 1:
                i = near[0]
                for fac in ((0.88, 0.8) if s["kind"] == "thick" else (1.12, 1.25)):
                    m2 = st["model"].copy()
                    m2.paths[i].w = float(m2.paths[i].w * fac)
                    cands.append(("width", m2))
        else:
            for how in ("snap", "smooth"):
                m2 = st["model"].copy()
                okc = False
                for i in near:
                    q = _edit_path(m2.paths[i], box, w, src_tree, src_pts, how)
                    if q is not None:
                        m2.paths[i] = q
                        okc = True
                if okc:
                    cands.append((how, m2))
            rt = FN._redraw_region(st["model"], D, box, w)
            if rt is not None:
                cands.append(("retrace", rt))
        best = None
        for how, c in cands:
            if not time_ok():
                break
            ink2 = ink_of(c)
            s2 = doctor.soft(ink2)
            if s2 > st["cur"] + tol(st["cur"]) or (s2 - start_soft) > drift_cap:
                continue
            sc = ST.compare(D, ink2, w)["score"]
            gain = st["score"] - sc
            if gain < max(0.05, 0.1 * s["severity"]):
                continue
            t2 = FN._topo(c)
            if t2 > st["topo"]:
                continue
            if best is None or gain > best[0]:
                best = (gain, how, c, ink2, s2, sc, t2)
        if best and best[1] not in memory_skip:
            _, how, c, ink2, s2, sc, t2 = best
            st.update(model=c, ink=ink2, cur=s2, score=sc, topo=t2)
            fixed += 1
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=True, how=how))
        else:
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=False, how="none"))
    rep = dict(before=float(before), after=float(st["score"]), found=len(res["sites"]), fixed=fixed, sites=sites,
               unresolved=[dict(kind=x["kind"], x=x["x"], y=x["y"], severity=x["severity"]) for x in sites if not x["fixed"]])
    return st["model"], st["ink"], st["cur"], rep
