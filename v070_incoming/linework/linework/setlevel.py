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


def weak_icons(mets, max_n=3, floor=0.955, rel=0.02):
    """Indices (into mets) of icons clearly worse than the rest of the set."""
    sc = [LS.quality_score(m) if m else None for m in mets]
    ok = [s for s in sc if s is not None]
    if len(ok) < 3:
        return []
    med = float(np.median(ok))
    weak = [(s, k) for k, s in enumerate(sc) if s is not None and (s < med - rel or (mets[k].get("iou", 1) < floor))]
    return [k for _, k in sorted(weak)[:max_n]]


def better(old_metrics, new_metrics):
    return LS.quality_score(new_metrics) > LS.quality_score(old_metrics) + 1e-4
