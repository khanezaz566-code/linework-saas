"""Orchestration: image -> icons -> (trace -> chains -> fit) -> Edit/Output/Doctor loop -> SVG."""
from __future__ import annotations
import time, json
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
from . import joints as JN
from . import lessons as LS
from .split import find_icons, crop_icon, estimate_width

PRESETS = {
    "fast": dict(max_rounds=0, time_budget=25, region_edits=0, iters=18, taus=(1.0, 0.45)),
    "standard": dict(max_rounds=2, time_budget=90, region_edits=4, iters=22, taus=(1.0, 0.5, 0.35)),
    "precise": dict(max_rounds=5, time_budget=240, region_edits=8, iters=45, taus=(1.2, 0.8, 0.5, 0.34)),
}


@dataclass
class Options:
    quality: str = "standard"
    target_iou: float = 0.995
    sens: float = 6.0
    merge: float = 1.5
    sigma: float = 2.0
    max_rounds: int | None = None
    time_budget: float | None = None
    region_edits: int | None = None
    repair: bool = True  # final safety net for missing / stray pieces
    max_stroke: float = 14.0  # sources with thicker strokes (big / hi-res sheets) are processed at norm_stroke and scaled back
    norm_stroke: float = 10.0
    memory: bool = True  # remember best results / lessons between runs (linework/lessons.py)
    fresh: bool = False  # do not re-use a stored result for the same icon (still never return something worse than the stored best)
    set_stroke: float = 0.0  # stroke width of the whole set (set by process_sheet); the Finisher snaps close widths to it
    joins: bool = True  # Join engine: build every joint, check it, repair failures with the pen / line / arc / shape tools (linework/joints.py)
    finish: bool = True  # Finisher engine: per-icon inspection of the last few machine-made spots
    rings: bool = True  # detect exact circles in the image and snap strokes onto them
    trace_good: float = 0.968  # stop trying trace settings once the first render matches this well
    trace_ok: float = 0.93  # ... or at least this well (then the optimiser does the rest; saves ~10 s per dense icon)
    superres: int | None = None  # trace at k-times resolution (auto: thin strokes get 2-3x)
    dedupe_tol: float = 0.0025  # fraction of ink area we will sacrifice to remove a duplicate centerline

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
        return dict(model=m, svg=m.svg(), metrics=met)
    r = _process_icon_scaled(gray, opts, emit, name)
    if use_mem:
        LS.log_icon(name, r["metrics"], __version__)
        if prev and prev["score"] > LS.quality_score(r["metrics"]) + 0.0005:
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
    iou = doc.iou(ink_of(m))  # at the full source resolution: stricter (a 1 px shift of a 45 px stroke counts), kept as iou_full
    r["metrics"].update(iou_full=iou, scale=float(k), stroke_width=float(r["metrics"].get("stroke_width", 0) * W / small.shape[1]))
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
    left = lambda: min(bud[0] - (time.process_time() - c0), 10.0 * bud[0] - (time.time() - t0))  # 2nd term: hang guard only

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
    elif w_est < 8:
        cands = [(3, 0.6), (2, 0.6), (3, 0.35)]
    elif w_est < 14:
        cands = [(2, 0.6), (3, 0.6), (1, 0.6)]
    else:
        cands = [(1, 0.6), (2, 0.6), (1, 1.0)]
    wb = int(min(30, round(w_est)))
    if not opts.superres:
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
    bud[0] = float(cfg["time_budget"]) * float(np.clip(sum(q.length() for q in model.paths) / 2500.0, 1.0, 3.0))
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
            new = RG.apply_ring(state["model"], ring)
            ink2 = ink_of(new)
            s2 = doctor.soft(ink2)
            if s2 <= state["cur"] + max(1.0, 0.0005 * state["cur"]):
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
        if cfg["max_rounds"] == 0 or stall >= 1 or left() <= 0:
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
    # Finisher: inspect this icon on its own and fix the few places that still look machine-made (each fix verified)
    fin = dict(found=0, fixed=0, sites=[])
    if opts.finish:
        fc0 = time.process_time()
        fcap = max(8.0, 0.25 * bud[0])
        m3, ink3, cur3, fin = FN.finish(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - fc0 < fcap,
                                       set_w=set_w, skip=(LS.skip_kinds() if opts.memory else ()))
        if fin["fixed"]:
            state.update(model=m3, ink=ink3, cur=cur3)
        ev("doctor", f"Finisher: {fin['found']} site(s) inspected, {fin['fixed']} fixed", iou=doctor.iou(state["ink"]))
    # Join engine: every joint is checked on its own; failing joints are repaired with the pen / line / arc / shape tools and re-checked
    jn = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)
    if opts.joins:
        jc0 = time.process_time()
        jcap = max(6.0, 0.2 * bud[0])
        m5, ink5, cur5, jn = JN.run_join_engine(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - jc0 < jcap)
        state.update(model=m5, ink=ink5, cur=cur5)
        nf = sum(jn["fixed"].values())
        ev("doctor", f"Join check: {jn['total']} joint(s), {jn['clean_first']} clean at first look, {jn['built']} built, {nf} repaired, {len(jn['unresolved'])} left for review", iou=doctor.iou(state["ink"]))
    # final topology guard: refits above can reopen junctions, so weld/merge/trim once more
    for _ in range(2):
        rep = doctor.diagnose(state["model"], state["ink"])
        open_all(rep)
        cmds = [c for c in Doctor.cosmetic_commands(rep) if c["op"] in ("trim_tail", "merge_nodes", "weld")]
        n = 0
        for cmd in pending(cmds):
            if cmd["op"] == "weld":
                n += do_weld()[0]
            elif cmd["path"] < len(state["model"].paths):
                n += run(cmd)
        if not n:
            break
    model, ink = state["model"], state["ink"]
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
        joins=dict(total=jn['total'], clean_first=jn['clean_first'], built=jn['built'], fixed=jn['fixed'], unresolved=jn['unresolved']),
    )
    return dict(model=model, svg=model.svg(), metrics=metrics)


def load_gray(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise ValueError("Unsupported image")
    if im.ndim == 3 and im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        rgb = im[:, :, :3].astype(np.float32) * a + 255 * (1 - a)
        im = rgb.astype(np.uint8)
    if im.ndim == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return im


def process_sheet(gray, opts: Options = None, emit=_noop, worker=None):
    """Process every icon in a sheet. `worker(crop, opts, name)` can be supplied to run icons in parallel."""
    opts = opts or Options()
    D = ink_map(gray)
    w, icons, lab = find_icons(D, merge=opts.merge)
    H, W = gray.shape
    bg = int(np.median(np.r_[gray[0], gray[-1], gray[:, 0], gray[:, -1]]))
    emit(engine="split", msg=f"Found {len(icons)} icon(s), stroke ≈ {w:.1f}px", icons=[ic["box"] for ic in icons], width=w)
    jobs = []
    for k, ic in enumerate(icons):
        crop, off = crop_icon(gray, lab, ic, pad=int(max(2 * w, 14)), bg=bg)
        jobs.append((k, crop, off))
    return W, H, jobs


def second_pass_options(opts: Options) -> dict:
    """Options (as a dict) for the longer second pass that weak icons get: more rounds, more budget, more trace settings tried, no stored result re-use."""
    d = asdict(opts)
    cfg = opts.resolved()
    d.update(fresh=True, max_rounds=max(cfg["max_rounds"], 4), time_budget=cfg["time_budget"] * 2.2, region_edits=max(cfg["region_edits"], 6),
             trace_good=0.985, trace_ok=0.965)
    return d
