"""Set-level consistency: an icon set must look like ONE set, from the first icon to the last.

* harmonize_widths: stroke widths are clustered over the WHOLE set (not icon by icon) and every icon is snapped to the shared weight classes
  (each change verified against that icon's source: kept only if the match does not get worse).
* weak_icons / better: icons that came out clearly worse than the rest of the set get a second, longer pass; the better result wins.
"""
from __future__ import annotations
import numpy as np
from .model import Model
from .doctor import Doctor, ink_of
from .trace import ink_map
from . import finisher as FN
from . import lessons as LS


def harmonize_widths(models, crops, max_dev=0.4):
    """models/crops: parallel lists (crop-local models, uint8 crops). Returns (new_models, report)."""
    allp, own = [], []
    for k, m in enumerate(models):
        for p in m.paths:
            allp.append(p)
            own.append(k)
    if len(allp) < 2:
        return models, dict(changed=0, classes=[])
    big = Model(allp, 0, 0)
    plan = FN.width_plan(big, max_dev=max_dev)
    # class centres actually used
    centers = sorted({round(w, 2) for w in plan.values()})
    per = {}
    for gi, w in plan.items():
        per.setdefault(own[gi], []).append((gi, w))
    # index of each global path inside its own model
    local, cnt = {}, {}
    for gi, k in enumerate(own):
        local[gi] = cnt.get(k, 0)
        cnt[k] = local[gi] + 1
    out, changed = list(models), 0
    for k, items in per.items():
        m = models[k]
        D = ink_map(crops[k])
        doc = Doctor(D)
        cur = doc.soft(ink_of(m))
        topo0 = FN._topo(m)
        for dev in (max_dev, 0.12):
            cand = m.copy()
            n = 0
            for gi, w in items:
                p = cand.paths[local[gi]]
                if abs(p.w - w) / w <= dev and abs(p.w - w) > 1e-6:
                    p.w = w
                    n += 1
            if not n:
                continue
            s2 = doc.soft(ink_of(cand))
            if s2 <= cur + max(2.0, 0.003 * cur) and FN._topo(cand) <= topo0:
                out[k] = cand
                changed += 1
                break
    return out, dict(changed=changed, classes=centers)


def result_key(model, met):
    """(hard, open, -iou) - lower is better."""
    if not model or not met:
        return (999999, 999999, 0.0)
    drep = met.get("decision")
    if drep and "after" in drep:
        hard = drep["after"].get("hard", 999999)
        open_cnt = drep.get("open", len(drep.get("open_findings", [])))
        iou = drep["after"].get("iou", met.get("iou", 0.0))
        return (hard, open_cnt, -iou)
    return (met.get("hard", 999999), 0, -met.get("iou", 0.0))


def weak_icons(mets, max_n=None, floor=0.955, rel=0.02):
    """Indices (into mets) of icons clearly worse than the rest of the set or failing the clean gate."""
    sc = [LS.quality_score(m) if m else None for m in mets]
    ok = [s for s in sc if s is not None]
    med = float(np.median(ok)) if len(ok) >= 3 else 1.0
    weak = []
    for k, m in enumerate(mets):
        if not m:
            continue
        is_clean = m.get("clean", True)
        needs_rev = m.get("needs_review", False)
        if not is_clean or needs_rev:
            weak.append((-1.0, k))  # un-clean icons get top priority
            continue
        s = sc[k]
        if s is not None and (s < med - rel or (m.get("iou", 1.0) < floor)):
            weak.append((s, k))
    weak.sort(key=lambda t: t[0])
    indices = [k for _, k in weak]
    if max_n is not None:
        indices = indices[:max_n]
    return indices


def escalate_weak_icon(crop, off, base_opts, current_model, current_metrics, emit=lambda **kw: None, name="icon", sheet_deadline=None):
    """Escalates an un-clean icon across up to 3 rungs:
    1. next higher quality preset
    2. alternative trace candidate / different threshold
    3. safe mode (simpler fit, no aggressive refine)
    Returns (best_model, best_metrics). Never replaces with a worse result.
    If still not clean, marks needs_review=True.
    """
    import copy, time
    from .pipeline import process_icon, Options

    best_model = current_model
    best_metrics = dict(current_metrics)
    best_key = result_key(best_model, best_metrics)

    if best_metrics.get("clean", True) and not best_metrics.get("needs_review", False):
        return best_model, best_metrics

    # Quality progression
    next_q = {
        "fast": "standard",
        "standard": "precise",
        "precise": "precise"
    }.get(base_opts.quality, "precise")

    # Rung 1: Next higher quality preset
    if sheet_deadline is None or time.time() < sheet_deadline:
        emit(engine="doctor", msg=f"Escalation rung 1 (higher quality preset: {next_q}) for {name}", icon=name)
        opt1 = copy.copy(base_opts)
        opt1.quality = next_q
        opt1.fresh = True
        if base_opts.quality == "precise":
            opt1.max_rounds = 8
        r1 = process_icon(crop, opt1, emit=emit, name=name)
        k1 = result_key(r1["model"], r1["metrics"])
        if k1 < best_key:
            best_model, best_metrics, best_key = r1["model"], r1["metrics"], k1
        if best_metrics.get("clean", False):
            emit(engine="doctor", msg=f"Escalation rung 1 succeeded (clean) for {name}", icon=name)
            return best_model, best_metrics

    # Rung 2: Alternative trace candidate / different threshold
    if sheet_deadline is None or time.time() < sheet_deadline:
        emit(engine="doctor", msg=f"Escalation rung 2 (alternative trace candidate) for {name}", icon=name)
        opt2 = copy.copy(base_opts)
        opt2.quality = next_q
        opt2.fresh = True
        opt2.superres = 3 if getattr(base_opts, "superres", None) != 3 else 2
        opt2.sens = base_opts.sens * 1.3
        r2 = process_icon(crop, opt2, emit=emit, name=name)
        k2 = result_key(r2["model"], r2["metrics"])
        if k2 < best_key:
            best_model, best_metrics, best_key = r2["model"], r2["metrics"], k2
        if best_metrics.get("clean", False):
            emit(engine="doctor", msg=f"Escalation rung 2 succeeded (clean) for {name}", icon=name)
            return best_model, best_metrics

    # Rung 3: Safe mode (simpler fit, no aggressive refine)
    if sheet_deadline is None or time.time() < sheet_deadline:
        emit(engine="doctor", msg=f"Escalation rung 3 (safe mode: simpler fit, no aggressive refine) for {name}", icon=name)
        opt3 = copy.copy(base_opts)
        opt3.quality = "standard"
        opt3.structure = False
        opt3.finish = False
        opt3.joins = True
        opt3.repair = True
        opt3.fresh = True
        r3 = process_icon(crop, opt3, emit=emit, name=name)
        k3 = result_key(r3["model"], r3["metrics"])
        if k3 < best_key:
            best_model, best_metrics, best_key = r3["model"], r3["metrics"], k3

    if not best_metrics.get("clean", False):
        best_metrics["needs_review"] = True
        best_metrics["clean"] = False
        drep = best_metrics.get("decision", {})
        emit(engine="doctor", msg=f"Escalation complete: {name} remains open ({drep.get('open', 0)} open findings, needs review)", icon=name)

    return best_model, best_metrics


def better(old_metrics, new_metrics):
    return LS.quality_score(new_metrics) > LS.quality_score(old_metrics) + 1e-4
