"""Safety net: find big pieces of the source that are missing from the render (or big pieces of render that are not in the
source) and repair them.  Run after the Edit/Doctor loop; every repair is verified by a full re-render and kept only if the
mismatch gets smaller.
"""
from __future__ import annotations
import numpy as np, cv2
from .model import Model
from .geom import resample
from .trace import refined_branches
from .chains import build_chains
from .fitting import initial_model


def _chunks(mask, w, min_area):
    """Connected blobs of `mask` that are fat enough to be real strokes (thin edge slivers are removed by an opening)."""
    k = int(max(3, round(0.45 * w)))
    k += (k + 1) % 2
    op = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(op, connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= min_area:
            out.append(lab == i)
    return out


def missing_chunks(D, ink, w):
    return _chunks((D > 0.5) & (ink < 0.5), w, max(1.0 * w * w, 30))


def extra_chunks(D, ink, w):
    return _chunks((ink > 0.5) & (D < 0.3), w, max(1.0 * w * w, 30))


def trace_missing(D, comp, w):
    """Trace only the source ink inside (a dilated copy of) one missing blob; returns new Paths (source pixel coords)."""
    reg = cv2.dilate(comp.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.6 * w) | 1, int(1.6 * w) | 1))) > 0
    Dc = np.where(reg, D, 0).astype(np.float32)
    br = refined_branches(Dc)
    if not br:
        return []
    chains, _ = build_chains(br)
    m = initial_model(chains, Dc, sigma=2.0)
    return m.paths


def repair(model: Model, D, ink_of, soft, state_cur, w, max_items=8):
    """Returns (model, ink, soft, n_added, n_removed). `ink_of(model)` renders; `soft(ink)` is the Doctor's mismatch."""
    cur = state_cur
    ink = ink_of(model)
    added = removed = 0
    for comp in missing_chunks(D, ink, w)[:max_items]:
        new_paths = trace_missing(D, comp, w)
        if not new_paths:
            continue
        cand = Model(model.paths + new_paths, model.width, model.height)
        ink2 = ink_of(cand)
        s2 = soft(ink2)
        if s2 < cur - 0.5:
            model, ink, cur = cand, ink2, s2
            added += 1
    for comp in extra_chunks(D, ink, w)[:max_items]:
        dil = cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        hits = []
        for i, p in enumerate(model.paths):
            f = resample(p.flat(), 1.0)
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, dil.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, dil.shape[0] - 1)
            share = float(dil[ys, xs].mean())
            if share > 0.5:
                hits.append(i)
        for i in sorted(hits, reverse=True):
            cand = Model([p for j, p in enumerate(model.paths) if j != i], model.width, model.height)
            ink2 = ink_of(cand)
            s2 = soft(ink2)
            if s2 < cur - 0.5:
                model, ink, cur = cand, ink2, s2
                removed += 1
                break
    return model, ink, cur, added, removed
