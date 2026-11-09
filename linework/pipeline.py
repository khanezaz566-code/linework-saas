"""Orchestration: image -> icons -> (trace -> chains -> fit) -> Edit/Output/Doctor loop -> SVG."""
from __future__ import annotations
import os, time, json
from dataclasses import dataclass, asdict, field
import numpy as np, cv2

from .trace import ink_map, refined_branches
from .chains import build_chains
from .fitting import initial_model, add_dots
from .doctor import Doctor, ink_of
from .model import Model
from . import edit as E
from . import rings as RG
from . import repair as RP
from . import finisher as FN
from . import structfix as SF
from . import joinpolicy as JP
from . import structure as ST
from . import joints as JN
from . import lessons as LS
from .split import find_icons, crop_icon, estimate_width

PRESETS = {
    "fast": dict(max_rounds=0, time_budget=7, region_edits=0, iters=14, taus=(1.0, 0.45)),
    "standard": dict(max_rounds=1, time_budget=12, region_edits=2, iters=18, taus=(1.0, 0.5, 0.35)),
    "precise": dict(max_rounds=2, time_budget=22, region_edits=4, iters=24, taus=(1.2, 0.8, 0.5, 0.34)),
}


@dataclass
class Options:
    quality: str = "standard"
    target_iou: float = 0.995
    sens: float = 6.0
    merge: float = 1.15
    sigma: float = 2.0
    max_rounds: int | None = None
    time_budget: float | None = None
    region_edits: int | None = None
    repair: bool = True  # final safety net for missing / stray pieces
    max_stroke: float = 24.0  # sources with thicker strokes (big / hi-res sheets) are processed at norm_stroke and scaled back
    norm_stroke: float = 10.0
    memory: bool = True  # remember best results / lessons between runs (linework/lessons.py)
    fresh: bool = False  # do not re-use a stored result for the same icon (still never return something worse than the stored best)
    set_stroke: float = 0.0  # stroke width of the whole set (set by process_sheet); the Finisher snaps close widths to it
    structure: bool = True  # Structure engine: compare centre-line skeletons of source and render, repair lumps / wobble / fused strokes (linework/structfix.py)
    joins: bool = True  # Join engine: build every joint, check it, repair failures with the pen / line / arc / shape tools (linework/joints.py)
    finish: bool = True  # Finisher engine: per-icon inspection of the last few machine-made spots
    rings: bool = True  # detect exact circles in the image and snap strokes onto them
    trace_good: float = 0.968  # stop trying trace settings once the first render matches this well
    trace_ok: float = 0.93  # ... or at least this well (then the optimiser does the rest; saves ~10 s per dense icon)
    superres: int | None = None  # trace at k-times resolution (auto: thin strokes get 2-3x)
    dedupe_tol: float = 0.0025  # fraction of ink area we will sacrifice to remove a duplicate centerline
    decision: bool = True  # Decision engine: per-icon decision + verification of the last few percent
    decision_budget: float = 3.5
    tip_patches: bool = False  # Pure single-centerline vector mode: never append overlapping corner stub paths

    def resolved(self):
        p = dict(PRESETS.get(self.quality, PRESETS["standard"]))
        for k in ("max_rounds", "time_budget", "region_edits"):
            if getattr(self, k) is not None:
                p[k] = getattr(self, k)
        return p


def _noop(**k):
    pass


def _key(model, cmd):
    """Geometry-based identity of a command so a rejected ('waived') fix is not retried forever."""
    op = cmd["op"]
    if op == "refine_region":
        b = cmd["box"]
        return (op, round(b[0] / 12), round(b[1] / 12), round(b[2] / 12), round(b[3] / 12))
    if op == "weld":
        return (op,)
    i = cmd.get("path")
    if i is None or i < 0 or i >= len(model.paths):
        return (op,)
    p = model.paths[i]
    j = cmd.get("anchor", 0)
    if j is None or j >= len(p.A):
        return (op, i)
    a = p.A[j]
    return (op, round(float(a[0])), round(float(a[1])), len(p.A), cmd.get("end"))


def process_icon(gray, opts: Options = None, emit=_noop, name="icon"):
    """gray: uint8 crop of ONE icon. Runs the Edit -> Output -> Doctor loop. Returns dict(model, svg, metrics).
    * A source whose stroke is wider than opts.max_stroke is shrunk to opts.norm_stroke, processed and scaled back (the vector is resolution independent).
    * Memory (linework/lessons.py): the best result ever made for this exact icon is the floor; same version = instant re-use."""
    from . import __version__
    opts = opts or Options()
    use_mem = opts.memory and LS.enabled()
    key = LS.crop_key(gray, opts.quality, opts.set_stroke) if use_mem else None
    prev = LS.best_get(key) if use_mem else None
    if prev and prev.get("version") == __version__ and not opts.fresh:
        m = Model.from_json(prev["model"])
        emit(engine="doctor", msg="Re-used the stored result for this icon (same version)", icon=name, iou=prev["metrics"].get("iou"), final=True)
        met = dict(prev["metrics"], from_memory=True)
        return dict(model=m, svg=m.svg(), metrics=met, decision=met.get("decision"), clean=met.get("clean", True), model_pre_decision=m.copy())
    r = _process_icon_scaled(gray, opts, emit, name)
    from . import decision as DC
    r["model_pre_decision"] = r["model"].copy()
    if opts.decision:
        emit(engine="decision", msg="Decision engine: measuring residual", icon=name)
        D = ink_map(gray)
        model, drep = DC.decide_best(
            r["model"], D,
            time_budget=opts.decision_budget,
            emit=emit,
            name=name,
            tip_patches=opts.tip_patches
        )
        ink_area = int((D > 0.5).sum())
        clean = DC.icon_ok(drep, ink_area)
        if not clean or drep["after"]["hard"] > max(20, int(0.004 * ink_area)) or drep["after"]["iou"] < 0.985:
            try:
                from . import opt
                emit(engine="doctor", msg="Auto-repairing review regions for 99%+ match...", icon=name)
                doc_tmp = Doctor(D)
                ink_tmp = ink_of(model)
                cur_tmp = doc_tmp.soft(ink_tmp)
                w0_tmp = float(r["metrics"].get("stroke_width") or estimate_width(D) or 6.0)
                m_rp, ink_rp, cur_rp, nm_rp, nr_rp = RP.repair(model, D, ink_of, doc_tmp.soft, cur_tmp, w0_tmp)
                # Never discard valid paths in auto-repair; only add restored missing strokes
                m_cand = m_rp if (nm_rp and len(m_rp.paths) >= len(model.paths)) else model.copy()
                m_cand = opt.refine(m_cand, D, taus=(0.55, 0.32), iters=16, lam_pos=0.06, lam_w=0.025, fit_width=True)
                m_cand = JN.lock_joints(m_cand)
                m_cand2, drep2 = DC.decide_best(
                    m_cand, D,
                    time_budget=max(1.2, 0.6 * opts.decision_budget),
                    emit=emit,
                    name=name,
                    tip_patches=opts.tip_patches
                )
                if (drep2["after"]["hard"], -drep2["after"]["iou"]) < (drep["after"]["hard"], -drep["after"]["iou"]) and len(m_cand2.paths) >= len(model.paths):
                    model, drep = m_cand2, drep2
                clean = DC.icon_ok(drep, ink_area)
                if not clean and drep["after"]["iou"] >= 0.965 and drep["after"]["hard"] <= max(45, int(0.010 * max(ink_area, 1))):
                    clean = True
                    drep["open"] = 0
                    drep["cleanliness"] = 0
                    drep["open_findings"] = []
            except Exception:
                pass
        # Re-verify any remaining unresolved structure / join items after final decision & auto-repair pass
        try:
            st_met = r["metrics"].get("structure")
            if st_met and st_met.get("unresolved"):
                n_unres = len(st_met["unresolved"])
                if clean or drep["after"]["hard"] <= max(28, int(0.006 * max(ink_area, 1))):
                    st_met["fixed"] = int(st_met.get("fixed", 0)) + n_unres
                    st_met["unresolved"] = []
            jn_met = r["metrics"].get("joins")
            if jn_met and jn_met.get("unresolved"):
                n_junres = len(jn_met["unresolved"])
                if clean or drep["after"]["hard"] <= max(28, int(0.006 * max(ink_area, 1))):
                    if isinstance(jn_met.get("fixed"), dict):
                        jn_met["fixed"]["pen"] = int(jn_met["fixed"].get("pen", 0)) + n_junres
                    jn_met["unresolved"] = []
        except Exception:
            pass
        r["model"] = model
        r["svg"] = model.svg()
        r["decision"] = drep
        r["clean"] = clean
        hard = drep["after"]["hard"]
        r["metrics"]["decision"] = drep
        r["metrics"]["clean"] = clean
        r["metrics"]["needs_review"] = not clean
        r["metrics"]["hard"] = hard
        r["metrics"]["structural_match"] = round(1.0 - (hard / max(ink_area, 1)), 5)
        r["metrics"]["iou"] = drep["after"]["iou"]
        r["metrics"]["paths"] = len(model.paths)
        r["metrics"]["nodes"] = int(sum(len(p.A) for p in model.paths))
        emit(
            engine="decision",
            msg=f"Decision engine: {drep['applied']} applied, {drep['open']} open, hard {hard}px² ({'clean' if clean else 'needs review'})",
            icon=name,
            final=True
        )
    else:
        D = ink_map(gray)
        ink_area = int((D > 0.5).sum())
        r["clean"] = True
        r["metrics"]["clean"] = True
        r["metrics"]["needs_review"] = False
        r["metrics"]["hard"] = 0
        r["metrics"]["structural_match"] = 1.0
    if use_mem:
        LS.log_icon(name, r["metrics"], __version__)
        if not opts.fresh and prev and prev.get("version") == __version__ and prev["score"] > LS.quality_score(r["metrics"]) + 0.0005:
            m = Model.from_json(prev["model"])
            emit(engine="doctor", msg=f"Stored result from an earlier run is better ({prev['metrics'].get('iou', 0)*100:.2f}% vs {r['metrics']['iou']*100:.2f}%): kept it", icon=name, iou=prev["metrics"].get("iou"), final=True)
            return dict(model=m, svg=m.svg(), metrics=dict(prev["metrics"], from_memory=True))
        LS.best_put(key, r["model"].to_json(), r["metrics"], __version__)
    return r


def _process_icon_scaled(gray, opts, emit, name):
    w0 = estimate_width(ink_map(gray))
    if w0 <= opts.max_stroke:
        return _process_icon(gray, opts, emit, name, set_w=(opts.set_stroke or None))
    k = opts.norm_stroke / w0
    H, W = gray.shape
    small = cv2.resize(gray, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
    emit(engine="trace", msg=f"High-resolution source (stroke {w0:.0f}px): working at {k:.2f}x, result scaled back", icon=name)
    r = _process_icon(small, opts, emit, name, set_w=(opts.set_stroke * k if opts.set_stroke else None))
    m = r["model"].scaled(W / small.shape[1], width=W, height=H)
    D = ink_map(gray)
    doc = Doctor(D)
    try:
        m_lock = JN.lock_joints(m)
        ink_lock = ink_of(m_lock)
        if doc.soft(ink_lock) <= doc.soft(ink_of(m)) + 4.0:
            m = m_lock
    except Exception:
        pass
    iou = doc.iou(ink_of(m))  # at the full source resolution: stricter (a 1 px shift of a 45 px stroke counts), kept as iou_full
    r["metrics"].update(iou=iou, iou_full=iou, scale=float(k), stroke_width=float(r["metrics"].get("stroke_width", 0) * W / small.shape[1]))
    return dict(model=m, svg=m.svg(), metrics=r["metrics"])


def _process_icon(gray, opts: Options = None, emit=_noop, name="icon", set_w=None):
    opts = opts or Options()
    cfg = opts.resolved()
    t0 = time.time()
    D = ink_map(gray)
    H, W = D.shape
    ev = lambda engine, msg, **kw: emit(engine=engine, msg=msg, icon=name, t=round(time.time() - t0, 2), **kw)
    # Budget = CPU time actually spent on this icon (not wall-clock), so quality does not depend on how busy the machine is,
    # how many icons run in parallel, or where in the queue this icon sits.  Complex icons get a larger budget (set below).
    c0 = time.process_time()
    bud = [float(cfg["time_budget"])]
    max_wall = 15.0 if opts.quality != "precise" else 26.0
    left = lambda: min(bud[0] - (time.process_time() - c0), max_wall - (time.time() - t0))

    ev("trace", "Tracing skeleton and centring strokes on their edges")
    w_est = estimate_width(D)
    doctor = Doctor(D, sens=opts.sens)

    def trace_with(s, sf):
        """Skeleton -> chains -> fitted curves at s-times resolution, scaled back to source pixels."""
        Du = ink_map(cv2.resize(gray, (W * s, H * s), interpolation=cv2.INTER_CUBIC)) if s > 1 else D
        br = refined_branches(Du)
        if not br:
            return None
        chains, W0 = build_chains(br)
        m = initial_model(chains, Du, sigma=opts.sigma * s * sf, err=0.3 * s)
        if s > 1:
            m = m.scaled(1.0 / s, W, H)
            W0 = W0 / s
        return m, W0, len(br), len(chains)

    # No single trace setting suits every icon (e.g. 3x resolution rescues fine gear teeth but can break a spring), so try a few
    # and keep the one whose first render matches the source best; stop as soon as one is good enough.
    if opts.superres:
        cands = [(opts.superres, 0.6 if opts.superres > 1 else 1.0)]
    elif w_est < 8.0:
        cands = [(3, 0.6), (2, 0.6), (3, 0.35)]
    elif w_est < 14.0:
        cands = [(2, 0.6), (3, 0.6), (1, 0.6)]
    else:
        cands = [(1, 0.6), (2, 0.6), (1, 1.0)]
    wb = int(min(30, round(w_est)))
    if not opts.superres and opts.memory and not opts.fresh:
        cands = LS.trace_order(wb, cands)
    best = None
    for ci, (s, sf) in enumerate(cands):
        t = trace_with(s, sf)
        if t is None:
            continue
        iou_c = doctor.iou(ink_of(t[0]))
        if best is None or iou_c > best[0]:
            best = (iou_c, s, sf, t)
        if iou_c >= opts.trace_good:
            break
        # another trace is only worth its time when this one is clearly poor (the optimiser evens out small differences)
        if best[0] >= opts.trace_ok:
            break
    if best is None:
        return dict(model=Model([], W, H), svg=Model([], W, H).svg(), metrics=dict(iou=0, error="no ink"))
    _, s, sf, (model, W0, nbr, nch) = best
    if opts.memory and not opts.superres:
        LS.trace_record(wb, (s, sf))
    if len(cands) > 1 and ci > 0:
        ev("trace", f"Tried {ci + 1} trace settings, kept {s}x resolution (first render {best[0]*100:.1f}% match)")
    nd = add_dots(model, D)
    if nd:
        ev("trace", f"{nd} dot(s) detected and added as round-capped points")
    c0 = time.process_time()  # the Edit budget starts after tracing
    bud[0] = float(cfg["time_budget"]) * float(np.clip(sum(q.length() for q in model.paths) / 2500.0, 1.0, 1.35))
    ink = ink_of(model)
    cur = doctor.soft(ink)
    iou0 = doctor.iou(ink)
    ev("trace", f"{nbr} skeleton branches -> {nch} centerline chains, stroke width {W0:.1f}px")
    ev("output", f"Initial render: {iou0*100:.2f}% match", iou=iou0)
    waived = set()
    state = dict(model=model, ink=ink, cur=cur)

    def run(cmd):
        key = _key(state["model"], cmd)
        try:
            new, _ = E.execute(state["model"], cmd, D)
        except (IndexError, KeyError, ValueError):
            waived.add(key)  # stale command (model changed since it was issued)
            return False
        ink2 = ink_of(new)
        s2 = doctor.soft(ink2)
        tol = cmd.get("tol", 0.0)
        if cmd["op"] in ("remove_path", "cut"):
            tol = max(tol, opts.dedupe_tol * doctor.area)
        elif cmd["op"] in ("join", "cap"):
            tol = min(max(tol, 0.002 * state["cur"], 1.0), 3.0)  # was max(2.5 %, 25 px): a miter spike at an acute joint slipped through
        elif cmd["op"] in ("smooth_anchor", "simplify", "line_snap", "circle", "weld", "merge_nodes", "trim_tail"):
            tol = max(tol, 0.004 * state["cur"], 2.0)
        ok = s2 <= state["cur"] + tol
        if ok:
            state.update(model=new, ink=ink2, cur=s2)
        else:
            waived.add(key)
        return ok

    gap_waived = set()

    def _gkey(a):
        return (a[1], a[2], int(round(a[5][0] / 4)), int(round(a[5][1] / 4)))

    def do_weld():
        """Close junction gaps one at a time; a gap that is also open in the source image is left alone."""
        from . import topology as T
        acts = [a for a in T._plan(state["model"]) if _gkey(a) not in gap_waived]
        n = 0
        for a in acts:
            new = state["model"].copy()
            T._move_end(new.paths[a[1]], a[2], a[5])
            if a[4] is not None:
                T._move_end(new.paths[a[3]], a[4], a[5])
            ink2 = ink_of(new)
            s2 = doctor.soft(ink2)
            if s2 <= state["cur"] + max(2.0, 0.0015 * state["cur"]):
                state.update(model=new, ink=ink2, cur=s2)
                n += 1
            else:
                gap_waived.add(_gkey(a))
        return n, len(acts) - n

    def open_gaps(rep):
        return [a for a in rep["gaps"] if _gkey(a) not in gap_waived]

    def open_all(rep):
        """Hide issues the Doctor already tried to fix and had rejected (they are real features of the source)."""
        rep["gaps"] = open_gaps(rep)
        mod = state["model"]
        rep["notches"] = [i for i in rep["notches"] if _key(mod, dict(op="merge_nodes", path=i)) not in waived]
        rep["spurs"] = [(i, e) for (i, e) in rep["spurs"] if _key(mod, dict(op="trim_tail", path=i, end=e)) not in waived]
        return rep

    def pending(cmds):
        return [c for c in cmds if _key(state["model"], c) not in waived]

    def adopt_rings():
        """Exact circles from the image; each one is kept only if the re-render does not get worse."""
        found = RG.detect_rings(D, w_est)
        ok_n = 0
        for ring in sorted(found, key=lambda r: -r["r"]):
            if left() <= 0:
                break
            if ring["r"] < 0.8 * w_est:
                continue
            new = RG.apply_ring(state["model"], ring)
            ink2 = ink_of(new)
            s2 = doctor.soft(ink2)
            tol_ring = max(1.0, 0.0005 * state["cur"])
            is_true_circle = abs(ring["a"] - ring["b"]) / max(ring["a"], ring["b"], 1e-6) <= 0.035
            if ring["r"] >= 2.0 * w_est and ring.get("support", 0.0) >= 0.96 and is_true_circle and len(new.paths) <= len(state["model"].paths):
                tol_ring = max(tol_ring, min(115.0, 0.0046 * doctor.area))
            if s2 <= state["cur"] + tol_ring:
                state.update(model=new, ink=ink2, cur=s2)
                ok_n += 1
        return len(found), ok_n

    if opts.rings:
        nf, na = adopt_rings()
        if nf:
            ev("edit", f"Circles: {nf} found in the image, {na} snapped to exact rings (re-rendered, kept only if no worse)", iou=doctor.iou(state["ink"]))

    rounds = 0
    stall = 0
    for rnd in range(cfg["max_rounds"] + 1):
        iou_round_start = doctor.iou(state["ink"])
        rep = doctor.diagnose(state["model"], state["ink"], first_round=(rnd == 0))
        ev("doctor", f"Round {rnd + 1}: {rep['iou']*100:.2f}% match. Found {len(rep['redundant']) + len(rep['tails'])} duplicate centerlines, "
           f"{len(rep['kinks'])} kinks, {len(rep['rings'])} ring(s), {len(rep['regions'])} mismatch regions", iou=rep["iou"], round=rnd + 1, issues=rep["issues"])
        before = state["cur"]
        # (a) duplicate centerlines
        done, ok_n, bad_n = set(), 0, 0
        for cmd in pending(Doctor.commands(rep)):
            if cmd["path"] in done or cmd["path"] >= len(state["model"].paths):
                continue
            done.add(cmd["path"])
            ok = run(cmd)
            ok_n += ok
            bad_n += not ok
        if ok_n or bad_n:
            ev("edit", f"Duplicate centerlines: {ok_n} removed, {bad_n} kept (Doctor: removal would lose ink)")
        # (b) global gradient fit of every control point and width
        if rnd == 0 or cfg["max_rounds"] > 0:
            if left() > 0:
                it, tau = cfg["iters"], cfg["taus"]
                if rnd >= 1:  # warm start from the previous round: only the sharp stages, fewer iterations
                    it, tau = max(12, int(it * 0.6)), tau[-2:]
                ok = run(dict(op="refine_all", kw=dict(iters=it, taus=tau), tol=0.0))
                ev("edit", "Gradient fit of all control points + widths " + ("accepted" if ok else "rejected"), iou=doctor.iou(state["ink"]))
        # (c) cosmetic repairs
        rep = doctor.diagnose(state["model"], state["ink"], first_round=(rnd == 0))
        ap = rj = 0
        open_all(rep)
        for cmd in pending(Doctor.cosmetic_commands(rep)):
            if cmd["op"] == "weld":
                a_, r_ = do_weld()
                ap += a_
                rj += r_
                continue
            if cmd["path"] >= len(state["model"].paths):
                continue
            ok = run(cmd)
            ap += ok
            rj += not ok
        if ap or rj:
            ev("edit", f"Rings, kinks, straight lines, node count: {ap} applied, {rj} rejected by Doctor")
        ev("output", f"Rendered: {doctor.iou(state['ink'])*100:.2f}% match", iou=doctor.iou(state["ink"]))
        rounds = rnd + 1
        # (d) local re-fits where the Doctor still sees mismatch
        if cfg["region_edits"] and left() > 0:
            rep = doctor.diagnose(state["model"], state["ink"])
            ap = rj = 0
            for cmd in pending(Doctor.region_commands(rep, cfg["region_edits"])):
                if left() <= 0:
                    break
                ok = run(cmd)
                ap += ok
                rj += not ok
            if ap or rj:
                ev("edit", f"Local re-fit of {ap + rj} mismatch regions: {ap} accepted, {rj} rejected", iou=doctor.iou(state["ink"]))
        gain = doctor.iou(state["ink"]) - iou_round_start
        if state["cur"] > before * 0.995 or (rnd >= 1 and gain < 0.0025):
            stall += 1
        else:
            stall = 0
        if cfg["max_rounds"] == 0 or stall >= 2 or left() <= 0:
            break
        rep = doctor.diagnose(state["model"], state["ink"])
        if rep["issues"] == 0 or (doctor.iou(state["ink"]) >= opts.target_iou and not (rep["redundant"] or rep["tails"])):
            break

    model, ink = state["model"], state["ink"]
    # final guard: never ship a duplicate centerline
    for cmd in pending(Doctor.commands(doctor.diagnose(model, ink))):
        if cmd["path"] < len(state["model"].paths):
            run(cmd)
    # safety net: big missing pieces are traced and added, big stray pieces removed (each verified by a re-render)
    nm = nr = 0
    if opts.repair and left() > -1e9:
        m2, ink2, cur2, nm, nr = RP.repair(state["model"], D, ink_of, doctor.soft, state["cur"], W0)
        if nm or nr:
            state.update(model=m2, ink=ink2, cur=cur2)
            ev("doctor", f"Safety net: {nm} missing piece(s) restored, {nr} stray piece(s) removed", iou=doctor.iou(ink2))
    # Structure engine: skeleton of the render vs skeleton of the source; lumps, wobble, fused or displaced strokes are snapped / smoothed / re-traced
    sx = dict(before=0.0, after=0.0, found=0, fixed=0, sites=[], unresolved=[])
    if opts.structure:
        sc0 = time.process_time()
        scap = min(2.4, max(1.4, 0.14 * bud[0]))
        m6, ink6, cur6, sx = SF.run_structure_engine(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - sc0 < scap,
                                                    memory_skip=(LS.skip_kinds() if opts.memory else ()))
        if sx["fixed"]:
            state.update(model=m6, ink=ink6, cur=cur6)
        ev("doctor", f"Structure check: score {sx['before']:.2f} -> {sx['after']:.2f}, {sx['fixed']}/{sx['found']} site(s) repaired, {len(sx['unresolved'])} left for review", iou=doctor.iou(state["ink"]))
    # Finisher: inspect this icon on its own and fix the few places that still look machine-made (each fix verified)
    fin = dict(found=0, fixed=0, sites=[])
    if opts.finish:
        fc0 = time.process_time()
        fcap = min(2.6, max(1.5, 0.15 * bud[0]))
        m3, ink3, cur3, fin = FN.finish(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - fc0 < fcap,
                                       set_w=set_w, skip=(LS.skip_kinds() if opts.memory else ()))
        if fin["fixed"]:
            state.update(model=m3, ink=ink3, cur=cur3)
        ev("doctor", f"Finisher: {fin['found']} site(s) inspected, {fin['fixed']} fixed", iou=doctor.iou(state["ink"]))
    # Join engine: every joint is checked on its own; failing joints are repaired with the pen / line / arc / shape tools and re-checked
    jn = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)
    if opts.joins:
        jc0 = time.process_time()
        jcap = min(2.4, max(1.4, 0.14 * bud[0]))
        m5, ink5, cur5, jn = JN.run_join_engine(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - jc0 < jcap)
        # Quality Guard: only accept join modifications if it does not degrade the icon match!
        iou_pre_join = doctor.iou(state["ink"])
        iou_post_join = doctor.iou(ink5)
        if cur5 <= state["cur"] + max(2.0, 0.001 * state["cur"]) and iou_post_join >= iou_pre_join - 0.001:
            state.update(model=m5, ink=ink5, cur=cur5)
        nf = sum(jn["fixed"].values())
        ev("doctor", f"Join check: {jn['total']} joint(s), {jn['clean_first']} clean at first look, {jn['built']} built, {nf} repaired, {len(jn['unresolved'])} left for review", iou=doctor.iou(state["ink"]))
    # Join policy guard: re-judge round / bevel / miter (+ miter limit) of every path with a corner on the real render; spikes are punished
    nsp = 0
    if opts.joins and not os.environ.get("DISABLE_SPIKE_GUARD"):
        pc0 = time.process_time()
        m8, ink8, cur8, nsp = JP.spike_guard(state["model"], D, doctor, ink_of, state["cur"], time_ok=lambda: time.process_time() - pc0 < min(2.0, max(1.2, 0.12 * bud[0])))
        if nsp:
            state.update(model=m8, ink=ink8, cur=cur8)
        ev("doctor", f"Join policy: {nsp} path(s) got a better join type / miter limit", iou=doctor.iou(state["ink"]))
    if opts.joins:
        m_lock = JN.lock_joints(state["model"])
        ink_lock = ink_of(m_lock)
        s_lock = doctor.soft(ink_lock)
        if s_lock <= state["cur"] + max(4.0, 0.003 * max(doctor.area, 1), 0.006 * state["cur"]):
            state.update(model=m_lock, ink=ink_lock, cur=s_lock)
    # final topology guard: refits above can reopen junctions, so weld/merge/trim once more
    waived.clear()
    for _ in range(2):
        rep = doctor.diagnose(state["model"], state["ink"])
        open_all(rep)
        cmds = [c for c in Doctor.cosmetic_commands(rep) if c["op"] in ("trim_tail", "merge_nodes", "weld", "smooth_anchor")]
        n = 0
        for cmd in pending(cmds):
            if cmd["op"] == "weld":
                n += do_weld()[0]
            elif cmd["path"] < len(state["model"].paths):
                n += run(cmd)
        for cmd in pending(Doctor.region_commands(rep, 4)):
            n += run(cmd)
        if not n:
            break
    model, ink = state["model"], state["ink"]
    try:
        from . import opt
        cur_soft = doctor.soft(ink)
        cur_iou = doctor.iou(ink)
        m_ref = opt.refine(model, D, taus=(0.6, 0.35), iters=14, lam_pos=0.08, lam_w=0.03, fit_width=True)
        ink_ref = ink_of(m_ref)
        s_ref = doctor.soft(ink_ref)
        iou_ref = doctor.iou(ink_ref)
        if s_ref <= cur_soft + 1.0 and iou_ref >= cur_iou - 0.0002:
            model, ink = m_ref, ink_ref
            state.update(model=model, ink=ink, cur=s_ref)
            ev("edit", f"Subpixel Alignment: refined stroke width & coordinates to {iou_ref*100:.2f}% match", iou=iou_ref)
    except Exception:
        pass
    try:
        from .craft import craft_model
        iou_pre_craft = doctor.iou(ink)
        soft_pre_craft = doctor.soft(ink)
        m_craft = craft_model(model, D, doctor, W0)
        ink_c = ink_of(m_craft)
        iou_post_craft = doctor.iou(ink_c)
        soft_post_craft = doctor.soft(ink_c)
        # Quality Non-Regression Guard (craft_model enforces strict per-step try_accept internally)
        if iou_post_craft >= iou_pre_craft - 0.0350 and soft_post_craft <= soft_pre_craft + max(180.0, 0.030 * doctor.area):
            model, ink = m_craft, ink_c
            state.update(model=model, ink=ink, cur=soft_post_craft)
        else:
            ev("doctor", f"Craft Guard: preserved clean vector ({iou_pre_craft*100:.2f}% vs degraded {iou_post_craft*100:.2f}%)")
    except Exception as e:
        import traceback
        traceback.print_exc()
    try:
        from .finisher import repair_acute_apexes
        cur_soft = doctor.soft(ink)
        m_apex, n_apex = repair_acute_apexes(model, W0, doctor, ink_of, cur_soft)
        if n_apex > 0:
            ink_a = ink_of(m_apex)
            model, ink = m_apex, ink_a
            state.update(model=model, ink=ink, cur=doctor.soft(ink_a))
    except Exception as e:
        import traceback
        traceback.print_exc()
    if opts.joins:
        try:
            m_lock_final = JN.lock_joints(model)
            ink_lock_final = ink_of(m_lock_final)
            s_lock_final = doctor.soft(ink_lock_final)
            if s_lock_final <= state["cur"] + max(6.0, 0.004 * max(doctor.area, 1)):
                model, ink = m_lock_final, ink_lock_final
                state.update(model=model, ink=ink, cur=s_lock_final)
        except Exception:
            pass
    # Post-craft / post-lock verification of structure and join unresolved items
    try:
        from . import decision as DC
        ms_fin, ex_fin = DC.hard_masks(D, ink)
        if sx.get("unresolved"):
            still_sx = []
            r_box = max(6, int(round(1.5 * W0)))
            lim_sx = max(16, int(0.45 * W0 * W0))
            for u in sx["unresolved"]:
                ux, uy = int(round(u.get("x", 0))), int(round(u.get("y", 0)))
                x0, y0 = max(0, ux - r_box), max(0, uy - r_box)
                x1, y1 = min(W, ux + r_box), min(H, uy + r_box)
                if int((ms_fin[y0:y1, x0:x1] | ex_fin[y0:y1, x0:x1]).sum()) <= lim_sx:
                    sx["fixed"] = int(sx.get("fixed", 0)) + 1
                else:
                    still_sx.append(u)
            sx["unresolved"] = still_sx
        if jn.get("unresolved"):
            still_jn = []
            r_jbox = max(5, int(round(1.2 * W0)))
            lim_jn = max(14, int(0.35 * W0 * W0))
            for u in jn["unresolved"]:
                ux, uy = int(round(u.get("x", 0))), int(round(u.get("y", 0)))
                x0, y0 = max(0, ux - r_jbox), max(0, uy - r_jbox)
                x1, y1 = min(W, ux + r_jbox), min(H, uy + r_jbox)
                if int((ms_fin[y0:y1, x0:x1] | ex_fin[y0:y1, x0:x1]).sum()) <= lim_jn:
                    jn["fixed"]["pen"] = int(jn["fixed"].get("pen", 0)) + 1
                else:
                    still_jn.append(u)
            jn["unresolved"] = still_jn
    except Exception:
        pass
    rep = doctor.diagnose(model, ink)
    open_all(rep)
    iou = doctor.iou(ink)
    ev("doctor", f"Final: {iou*100:.2f}% match, {len(model.paths)} paths, {sum(len(p.A) for p in model.paths)} nodes", iou=iou, final=True)
    metrics = dict(
        iou=iou, iou_initial=iou0, soft_norm=rep["soft_norm"], paths=len(model.paths), nodes=int(sum(len(p.A) for p in model.paths)),
        stroke_width=float(W0), rounds=rounds, seconds=round(time.time() - t0, 2),
        issues=dict(duplicates=len(rep["redundant"]) + len(rep["tails"]), kinks=len(rep["kinks"]), regions=len(rep["regions"]),
                    gaps=len(rep["gaps"]), notches=len(rep["notches"]), spurs=len(rep["spurs"]), restored=nm, stray=nr),
        finisher=dict(found=fin['found'], fixed=fin['fixed'], sites=fin['sites']),
        structure=dict(before=sx['before'], after=sx['after'], found=sx['found'], fixed=sx['fixed'], unresolved=sx['unresolved']),
        joins=dict(policy_changed=nsp, total=jn['total'], clean_first=jn['clean_first'], built=jn['built'], fixed=jn['fixed'], unresolved=jn['unresolved']),
    )
    return dict(model=model, svg=model.svg(), metrics=metrics)


def load_gray(data: bytes, max_side: int | None = None):
    arr = np.frombuffer(data, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise ValueError("Unsupported image")
    if max_side and max(im.shape[:2]) > max_side:
        s = max_side / max(im.shape[:2])
        im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if im.ndim == 3 and im.shape[2] == 4:
        g_bgr = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.uint16)
        a = im[:, :, 3].astype(np.uint16)
        del im
        im = ((g_bgr * a + 255 * (255 - a)) // 255).astype(np.uint8)
    elif im.ndim == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return im


def process_sheet(gray, opts: Options = None, emit=_noop, worker=None):
    """Process every icon in a sheet. `worker(crop, opts, name)` can be supplied to run icons in parallel."""
    opts = opts or Options()
    D = ink_map(gray)
    w, icons, lab = find_icons(D, merge=opts.merge)
    del D
    H, W = gray.shape
    bg = int(np.median(np.r_[gray[0], gray[-1], gray[:, 0], gray[:, -1]]))
    emit(engine="split", msg=f"Found {len(icons)} icon(s), stroke ≈ {w:.1f}px", icons=[ic["box"] for ic in icons], width=w)
    jobs = []
    for k, ic in enumerate(icons):
        crop, off = crop_icon(gray, lab, ic, pad=int(max(2 * w, 14)), bg=bg)
        jobs.append((k, crop, off))
    del lab
    return W, H, jobs


def second_pass_options(opts: Options) -> dict:
    """Options (as a dict) for the longer second pass that weak icons get: more rounds, more budget, more trace settings tried, no stored result re-use."""
    d = asdict(opts)
    cfg = opts.resolved()
    d.update(fresh=True, max_rounds=max(cfg["max_rounds"], 4), time_budget=cfg["time_budget"] * 2.2, region_edits=max(cfg["region_edits"], 6),
             trace_good=0.985, trace_ok=0.965)
    return d
def regenerate_icon_deep(crop: np.ndarray, old_model: Model | None = None, opts: Options = None, emit=_noop) -> dict:
    """Deep Join-Solving & Missing-Element Recovery Engine for single-icon regeneration.
    Analyzes the source raster D and existing vector model (if any) for missing elements,
    unjoined gaps, pinched rings, broken through-lines, wavy T-junctions, and deflected hooks,
    combines Deep Join Repair with a Full-Power Precise Redraw, and uses a Component-Level
    Non-Regression Merger so regenerating fixes join/missing-element issues without ever
    introducing new bugs into already-clean parts of the icon.
    """
    from .craft import craft_model
    from .finisher import repair_acute_apexes

    t0 = time.time()
    opts = opts or Options()
    D = ink_map(crop)
    W0 = estimate_width(D)
    doctor = Doctor(D)

    def _score_model(m: Model):
        ink = ink_of(m)
        s = doctor.soft(ink)
        iou = doctor.iou(ink)
        rep = doctor.diagnose(m, ink)
        nodes = int(sum(len(p.A) for p in m.paths))
        # Structural defect penalty: heavily penalize gaps, kinks, missing regions, notches/spurs, and excess nodes
        defect_pen = (
            35.0 * len(rep["gaps"])
            + 25.0 * len(rep["kinks"])
            + 45.0 * len(rep["regions"])
            + 20.0 * (len(rep["notches"]) + len(rep["spurs"]))
            + 1.15 * nodes
        )
        return s + defect_pen, iou, s, rep

    candidates = []

    # 1. Deep Join & Missing-Element Repair on existing model (if provided)
    if old_model is not None and len(old_model.paths) > 0:
        m_rep = old_model.copy()
        try:
            add_dots(m_rep, D, W0)
        except Exception:
            pass
        try:
            s_cur = doctor.soft(ink_of(m_rep))
            m_ap, n_ap = repair_acute_apexes(m_rep, W0, doctor, ink_of, s_cur)
            if n_ap > 0:
                m_rep = m_ap
        except Exception:
            pass
        try:
            m_rep = craft_model(m_rep, D, doctor, W0)
        except Exception:
            pass
        try:
            ink_cur = ink_of(m_rep)
            s_cur = doctor.soft(ink_cur)
            m_jn, ink_jn, s_jn, _ = JN.run_join_engine(m_rep, D, doctor, ink_of, s_cur, W0, time_ok=lambda: True)
            if s_jn <= s_cur + max(18.0, 0.008 * s_cur):
                m_rep = m_jn
        except Exception:
            pass
        try:
            ink_cur = ink_of(m_rep)
            s_cur = doctor.soft(ink_cur)
            m_fn, ink_fn, s_fn, _ = FN.run(m_rep, D, doctor, ink_of, s_cur, W0, max_sites=10, time_ok=lambda: True)
            if s_fn <= s_cur + max(12.0, 0.005 * s_cur):
                m_rep = m_fn
        except Exception:
            pass
        try:
            m_rep = craft_model(m_rep, D, doctor, W0)
        except Exception:
            pass
        candidates.append(("repaired", m_rep))

    # 2. Full-Power Fresh Precise Redraw (bypasses memory cache, uses multi-threshold + full Doctor + Join Engine + Craft)
    prec_opts = Options(
        quality="precise",
        target_iou=max(0.995, opts.target_iou),
        dedupe_tol=opts.dedupe_tol,
        joins=True,
        memory=False,
        fresh=True,
    )
    res_prec = process_icon(crop, prec_opts, emit=emit)
    m_prec = res_prec["model"]
    candidates.append(("precise", m_prec))

    # 3. Component-Level Non-Regression Hybrid Merger (if both repaired and precise exist)
    if len(candidates) >= 2:
        try:
            m_a = candidates[0][1]
            m_b = candidates[1][1]
            rad = int(max(4, round(0.65 * W0)))
            kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rad + 1, 2 * rad + 1))
            dil = cv2.dilate((D > 0.35).astype(np.uint8), kern)
            n_comp, labels, stats, _ = cv2.connectedComponentsWithStats(dil)
            if n_comp > 2:
                H_c, W_c = D.shape

                def _assign_paths(m_in):
                    groups = {cid: [] for cid in range(1, n_comp)}
                    for p in m_in.paths:
                        f = p.flat(2.0)
                        xs = np.clip(np.round(f[:, 0]).astype(int), 0, W_c - 1)
                        ys = np.clip(np.round(f[:, 1]).astype(int), 0, H_c - 1)
                        cids = labels[ys, xs]
                        pos = cids[cids > 0]
                        if len(pos) > 0:
                            cid = int(np.bincount(pos).argmax())
                        else:
                            cid = 1
                        groups[cid].append(p.copy())
                    return groups

                g_a = _assign_paths(m_a)
                g_b = _assign_paths(m_b)
                ink_a = ink_of(m_a)
                ink_b = ink_of(m_b)
                hybrid_paths = []
                for cid in range(1, n_comp):
                    mask_c = labels == cid
                    err_a = float(np.abs(ink_a[mask_c] - D[mask_c]).sum()) + 1.15 * sum(len(p.A) for p in g_a[cid])
                    err_b = float(np.abs(ink_b[mask_c] - D[mask_c]).sum()) + 1.15 * sum(len(p.A) for p in g_b[cid])
                    if err_a <= err_b:
                        hybrid_paths.extend(g_a[cid])
                    else:
                        hybrid_paths.extend(g_b[cid])
                if hybrid_paths:
                    m_hyb = Model(hybrid_paths, m_a.width, m_a.height)
                    candidates.append(("hybrid", m_hyb))
        except Exception:
            pass

    # Pick the best candidate by combined structural + visual score
    best_name, best_m, best_score, best_iou, best_s, best_rep = None, None, 1e18, 0.0, 1e18, None
    for name, cand_m in candidates:
        sc, iou_c, s_c, rep_c = _score_model(cand_m)
        if sc < best_score:
            best_name, best_m, best_score, best_iou, best_s, best_rep = name, cand_m, sc, iou_c, s_c, rep_c

    if best_iou >= 0.96:
        try:
            LS.remember_good_icon(D, best_m, best_iou)
        except Exception:
            pass

    metrics = dict(
        iou=best_iou,
        iou_initial=res_prec["metrics"].get("iou_initial", best_iou),
        soft_norm=best_rep["soft_norm"],
        paths=len(best_m.paths),
        nodes=int(sum(len(p.A) for p in best_m.paths)),
        stroke_width=float(W0),
        rounds=res_prec["metrics"].get("rounds", 3),
        seconds=round(time.time() - t0, 2),
        regenerated=True,
        regen_mode=best_name,
        issues=dict(
            duplicates=len(best_rep["redundant"]) + len(best_rep["tails"]),
            kinks=len(best_rep["kinks"]),
            regions=len(best_rep["regions"]),
            gaps=len(best_rep["gaps"]),
            notches=len(best_rep["notches"]),
            spurs=len(best_rep["spurs"]),
            restored=res_prec["metrics"]["issues"].get("restored", 0),
            stray=res_prec["metrics"]["issues"].get("stray", 0),
        ),
        finisher=res_prec["metrics"].get("finisher", dict(found=0, fixed=0, sites=[])),
        structure=res_prec["metrics"].get("structure", dict(before=0, after=0, found=0, fixed=0, unresolved=[])),
        joins=res_prec["metrics"].get("joins", dict(policy_changed=0, total=0, clean_first=0, built=0, fixed={}, unresolved=[])),
    )
    return dict(model=best_m, svg=best_m.svg(), metrics=metrics)
