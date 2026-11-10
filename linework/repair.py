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
    k = 3
    op = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(op, connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= min_area:
            out.append(lab == i)
    return out


def missing_chunks(D, ink, w):
    return _chunks((D > 0.45) & (ink < 0.40), w, max(12, int(0.20 * w * w)))


def extra_chunks(D, ink, w):
    return _chunks((ink > 0.50) & (D < 0.25), w, max(16, int(0.35 * w * w)))


def trace_missing(D, comp, w):
    """Trace only the source ink inside (a dilated copy of) one missing blob; returns new Paths (source pixel coords)."""
    reg = cv2.dilate(comp.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.6 * w) | 1, int(1.6 * w) | 1))) > 0
    Dc = np.where(reg, D, 0).astype(np.float32)
    br = refined_branches(Dc, prune=max(3, int(round(0.35 * w))))
    if not br:
        return []
    chains, _ = build_chains(br)
    m = initial_model(chains, Dc, sigma=1.5)
    return m.paths


def repair(model: Model, D, ink_of, soft, state_cur, w, max_items=12):
    """Returns (model, ink, soft, n_added, n_removed). `ink_of(model)` renders; `soft(ink)` is the Doctor's mismatch."""
    cur = state_cur
    ink = ink_of(model)
    added = removed = 0
    for comp in missing_chunks(D, ink, w)[:max_items]:
        new_paths = trace_missing(D, comp, w)
        if not new_paths:
            continue
        valid_paths = []
        for np_p in new_paths:
            f = resample(np_p.flat(), 1.0)
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, D.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, D.shape[0] - 1)
            if float((D[ys, xs] > 0.35).mean()) >= 0.60:
                valid_paths.append(np_p)
        if not valid_paths:
            continue
        cand = Model(model.paths + valid_paths, model.width, model.height)
        ink2 = ink_of(cand)
        s2 = soft(ink2)
        if s2 <= cur + max(1.5, 0.001 * cur):
            model, ink, cur = cand, ink2, s2
            added += len(valid_paths)
    for comp in extra_chunks(D, ink, w)[:max_items]:
        dil = cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        hits = []
        for i, p in enumerate(model.paths):
            f = resample(p.flat(), 1.0)
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, dil.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, dil.shape[0] - 1)
            share = float(dil[ys, xs].mean())
            # NEVER delete a stroke if its centerline sits on actual source ink!
            src_ink_share = float((D[ys, xs] > 0.35).mean())
            if share > 0.65 and src_ink_share < 0.20:
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
