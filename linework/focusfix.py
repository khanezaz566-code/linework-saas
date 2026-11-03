"""User-guided repair ("Mark & Fix").

The user draws boxes around the places that look wrong.  Only those places are re-analysed, with *relaxed* detection
(the user already told us something is wrong there) but *strict* protection of everything else:

  1. missing strokes   - source ink inside a box that the vector does not cover is traced and added
  2. stray strokes     - vector ink inside a box that the source does not have is removed
  3. open joins        - loose ends inside a box are welded to their partner / the stroke they should hit (radius larger than
                         in the automatic pass, but only when the source really has ink between the two points)
  4. engine tools      - craft / join engine / finisher run on the whole icon and are kept only if the marked place gets
                         better and the rest of the icon does not get worse
  5. deep (optional)   - a fresh full-power redraw; per connected piece the better of old/new is taken, judged on the marks

Every step is verified by a full re-render and accepted only when:
  * the error inside the marks goes down (or an open join inside the marks disappears without hurting the match), AND
  * the error outside the marks does not grow more than a tiny tolerance, AND
  * the global IoU does not drop by more than 0.4 %.
So marking one spot can never break another part of the icon.
"""
from __future__ import annotations
import time
import numpy as np, cv2

from .model import Model
from .doctor import Doctor, ink_of
from .trace import ink_map
from .geom import resample
from . import topology as T
from . import repair as RP


def _noop(**k):
    pass


def region_mask(shape, regions, pad):
    """Boolean mask (H, W) of the union of the marked boxes, grown by `pad` px. Boxes are (x0, y0, x1, y1) in crop pixels."""
    H, W = shape
    m = np.zeros((H, W), bool)
    for r in regions:
        x0, y0, x1, y1 = [float(v) for v in r]
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        a, b = int(max(0, np.floor(x0 - pad))), int(min(W, np.ceil(x1 + pad)))
        c, d = int(max(0, np.floor(y0 - pad))), int(min(H, np.ceil(y1 + pad)))
        if b > a and d > c:
            m[c:d, a:b] = True
    return m


def _px(p, W, H):
    return int(np.clip(round(p[0] - 0.5), 0, W - 1)), int(np.clip(round(p[1] - 0.5), 0, H - 1))


def gaps_in(m: Model, mask, **kw):
    """Open-join actions of topology._plan whose loose end (or target) lies inside the marked area."""
    H, W = mask.shape
    out = []
    for act in T._plan(m, **kw):
        kind, gi, ge, gj, gf, target, gap = act
        if gi >= len(m.paths):
            continue
        p1, _ = T._end(m.paths[gi], ge)
        x, y = _px(p1, W, H)
        tx, ty = _px(target, W, H)
        if mask[y, x] or mask[ty, tx]:
            out.append(act)
    return out


def _support(D, a, b, n=16):
    """Mean source-ink along the straight line a -> b (1 = the source really has ink all the way)."""
    H, W = D.shape
    ts = np.linspace(0.0, 1.0, n)[:, None]
    pts = a[None, :] * (1 - ts) + b[None, :] * ts
    xs = np.clip(np.round(pts[:, 0] - 0.5).astype(int), 0, W - 1)
    ys = np.clip(np.round(pts[:, 1] - 0.5).astype(int), 0, H - 1)
    return float(D[ys, xs].mean())


def _local_iou(doctor, ink, mask):
    b = (ink > 0.5) & mask
    r = doctor.ref & mask
    return float((b & r).sum() / max((b | r).sum(), 1))


def focus_fix(crop, old_model: Model, regions, opts=None, emit=_noop, deep=False, old_metrics=None):
    """Repair only the marked places of `old_model`. Returns dict(model, svg, metrics, report)."""
    from . import pipeline as P
    from .craft import craft_model

    t0 = time.time()
    D = ink_map(crop)
    H, W = D.shape
    if (old_model.height, old_model.width) != (H, W):
        raise ValueError("stored vector does not match the icon crop; regenerate the whole icon first")
    W0 = float(P.estimate_width(D))
    doctor = Doctor(D)
    mask = region_mask(D.shape, regions, pad=max(3.0, 0.6 * W0))
    if not mask.any():
        raise ValueError("no valid marked area")

    m0 = old_model.copy()
    ink0 = ink_of(m0)
    err0 = np.abs(ink0 - D)
    e_in0, e_out0 = float(err0[mask].sum()), float(err0[~mask].sum())
    iou0 = doctor.iou(ink0)
    liou0 = _local_iou(doctor, ink0, mask)
    plan_kw = dict(r_end=1.35, r_t=1.15, min_gap=0.08)
    gaps0 = len(gaps_in(m0, mask, **plan_kw))
    out_tol = max(8.0, 0.004 * e_out0)

    st = dict(m=m0, ink=ink0, e_in=e_in0, e_out=e_out0, iou=iou0, gaps=gaps0)
    actions = []

    def consider(cand: Model, label: str, where=None, need_gain=0.25, gap_ok=True):
        """Verify `cand` by a full re-render; adopt it only if it helps inside the marks and does no harm outside."""
        try:
            ink2 = ink_of(cand)
        except Exception:
            return False
        err2 = np.abs(ink2 - D)
        i2, o2 = float(err2[mask].sum()), float(err2[~mask].sum())
        iou2 = doctor.iou(ink2)
        if o2 > e_out0 + out_tol or iou2 < iou0 - 0.004:
            return False
        better = i2 < st["e_in"] - need_gain
        g2 = st["gaps"]
        if gap_ok and not better:
            g2 = len(gaps_in(cand, mask, **plan_kw))
            better = g2 < st["gaps"] and i2 <= st["e_in"] + max(6.0, 0.05 * st["e_in"])
        elif gap_ok:
            g2 = len(gaps_in(cand, mask, **plan_kw))
        if not better:
            return False
        st.update(m=cand, ink=ink2, e_in=i2, e_out=o2, iou=iou2, gaps=g2)
        a = dict(type=label)
        if where is not None:
            a["at"] = [round(float(where[0]), 1), round(float(where[1]), 1)]
        actions.append(a)
        return True

    # 1 ---- missing strokes ------------------------------------------------------------------------------
    emit(engine="focus", msg="Checking the marked areas for missing strokes")
    miss = (D > 0.40) & (st["ink"] < 0.40) & mask
    for comp in RP._chunks(miss, W0, max(0.08 * W0 * W0, 5))[:12]:
        new = RP.trace_missing(D, comp, W0)
        if not new:
            continue
        ys, xs = np.nonzero(comp)
        consider(Model(st["m"].paths + new, st["m"].width, st["m"].height), "missing stroke restored", (xs.mean(), ys.mean()))

    # 2 ---- stray strokes --------------------------------------------------------------------------------
    emit(engine="focus", msg="Checking the marked areas for stray / extra strokes")
    extra = (st["ink"] > 0.5) & (D < 0.30) & mask
    for comp in RP._chunks(extra, W0, max(0.25 * W0 * W0, 8))[:8]:
        dil = cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        hits = []
        for i, p in enumerate(st["m"].paths):
            f = resample(p.flat(), 1.0)
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, W - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, H - 1)
            if float(dil[ys, xs].mean()) > 0.5:
                hits.append(i)
        yy, xx = np.nonzero(comp)
        for i in sorted(hits, reverse=True):
            cand = Model([p for j, p in enumerate(st["m"].paths) if j != i], st["m"].width, st["m"].height)
            if consider(cand, "stray stroke removed", (xx.mean(), yy.mean()), need_gain=0.5, gap_ok=False):
                break

    # 3 ---- open joins -----------------------------------------------------------------------------------
    emit(engine="focus", msg="Closing open joins inside the marked areas")
    for _ in range(4):
        progressed = False
        for kind, gi, ge, gj, gf, target, gap in gaps_in(st["m"], mask, r_end=2.4, r_t=1.9, min_gap=0.0):
            mm = st["m"]
            if gi >= len(mm.paths) or (gj is not None and gj >= len(mm.paths)):
                continue
            p1, _ = T._end(mm.paths[gi], ge)
            if _support(D, p1, target) < 0.55:
                continue  # the source has no ink between the loose end and its target: not a real join
            if gf is not None:
                p2, _ = T._end(mm.paths[gj], gf)
                if _support(D, p2, target) < 0.55:
                    continue
            cand = mm.copy()
            T._move_end(cand.paths[gi], ge, target)
            if gf is not None:
                T._move_end(cand.paths[gj], gf, target)
            if consider(cand, "open join closed" if kind == "corner" else "line joined to stroke", target):
                progressed = True
                break
        if not progressed:
            break

    # 4 ---- engine tools, gated by the marks -----------------------------------------------------------------
    def tool(label, fn):
        emit(engine="focus", msg=f"Engine pass: {label}")
        try:
            cand = fn(st["m"].copy())
        except Exception:
            return
        if cand is not None and len(cand.paths) > 0:
            consider(cand, label)

    tool("geometry clean-up", lambda mm: craft_model(mm, D, doctor, W0))
    if st["gaps"] > 0 or deep:
        def _jn(mm):
            s_cur = doctor.soft(ink_of(mm))
            r = P.JN.run_join_engine(mm, D, doctor, ink_of, s_cur, W0, time_ok=lambda: True)
            return r[0]

        def _fn(mm):
            s_cur = doctor.soft(ink_of(mm))
            r = P.FN.run(mm, D, doctor, ink_of, s_cur, W0, max_sites=10, time_ok=lambda: True)
            return r[0]

        tool("join engine", _jn)
        tool("finisher", _fn)

    # 5 ---- deep: fresh full-power redraw, taken piece by piece where it is better on the marks ---------------
    if deep:
        emit(engine="focus", msg="Deep mode: full-power redraw of the icon")
        try:
            fresh = P.process_icon(crop, P.Options(quality="precise", target_iou=0.995, joins=True, memory=False, fresh=True), emit=emit)["model"]
            fresh = craft_model(fresh, D, doctor, W0)
            hyb = _hybrid_on_marks(st["m"], fresh, D, mask, W0, st["ink"], ink_of(fresh))
            if hyb is not None:
                consider(hyb, "redrawn from source")
        except Exception:
            pass

    final = st["m"]
    ink_f = st["ink"]
    gaps_left = len(gaps_in(final, mask, **plan_kw))
    liou1 = _local_iou(doctor, ink_f, mask)
    changed = len(actions) > 0
    if changed:
        note = f"{len(actions)} fix(es) applied inside the marked area; nothing outside it was allowed to get worse."
    else:
        note = (f"Nothing could be improved safely here: the vector already matches the source in the marked area "
                f"({liou0 * 100:.1f}% local match). If a line still looks wrong, mark a slightly larger area or enable Deep mode.")
    if gaps_left:
        note += f" {gaps_left} loose end(s) remain in the marks: the engine could not verify a safe join there (no source ink bridging them, or closing it would hurt the match)."
    report = dict(
        regions=len(regions), actions=actions, changed=changed, deep=bool(deep),
        gaps_before=int(gaps0), gaps_after=int(gaps_left),
        local_match_before=round(liou0, 4), local_match_after=round(liou1, 4),
        iou_before=round(iou0, 4), iou_after=round(float(st["iou"]), 4), note=note,
    )

    rep = doctor.diagnose(final, ink_f)
    om = dict(old_metrics or {})
    oi = dict(om.get("issues") or {})
    metrics = dict(om)
    metrics.update(
        iou=float(st["iou"]), soft_norm=rep["soft_norm"], paths=len(final.paths),
        nodes=int(sum(len(p.A) for p in final.paths)), stroke_width=float(W0),
        seconds=round(time.time() - t0, 2), regenerated=True, regen_mode="focus", focus=report,
        issues=dict(
            duplicates=len(rep["redundant"]) + len(rep["tails"]), kinks=len(rep["kinks"]), regions=len(rep["regions"]),
            gaps=len(rep["gaps"]), notches=len(rep["notches"]), spurs=len(rep["spurs"]),
            restored=oi.get("restored", 0), stray=oi.get("stray", 0),
        ),
    )
    return dict(model=final, svg=final.svg(), metrics=metrics, report=report)


def _hybrid_on_marks(m_cur: Model, m_new: Model, D, mask, W0, ink_cur, ink_new):
    """Per connected piece of the source that touches the marks, keep whichever model (current / fresh) fits it better,
    counting errors inside the marks 4x. Pieces that do not touch the marks stay exactly as they are."""
    rad = int(max(4, round(0.65 * W0)))
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rad + 1, 2 * rad + 1))
    dil = cv2.dilate((D > 0.35).astype(np.uint8), kern)
    n, labels = cv2.connectedComponents(dil)
    if n <= 1:
        return None
    H, W = D.shape

    def groups(m):
        g = {c: [] for c in range(1, n)}
        for p in m.paths:
            f = p.flat(2.0)
            xs = np.clip(np.round(f[:, 0]).astype(int), 0, W - 1)
            ys = np.clip(np.round(f[:, 1]).astype(int), 0, H - 1)
            ids = labels[ys, xs]
            ids = ids[ids > 0]
            g[int(np.bincount(ids).argmax()) if len(ids) else 1].append(p.copy())
        return g

    gc, gn = groups(m_cur), groups(m_new)
    touched = set(int(c) for c in np.unique(labels[mask]) if c > 0)
    wgt = np.where(mask, 4.0, 1.0)
    out = []
    for c in range(1, n):
        if c not in touched:
            out.extend(gc[c])
            continue
        sel = labels == c
        ea = float((np.abs(ink_cur - D) * wgt)[sel].sum()) + 1.15 * sum(len(p.A) for p in gc[c])
        eb = float((np.abs(ink_new - D) * wgt)[sel].sum()) + 1.15 * sum(len(p.A) for p in gn[c])
        out.extend(gc[c] if ea <= eb else gn[c])
    return Model(out, m_cur.width, m_cur.height) if out else None
