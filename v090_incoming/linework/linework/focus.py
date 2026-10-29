"""Focus weights: the plain pixel mismatch treats a 1 px error on a long smooth edge and a 1 px error that closes a 2 px white gap, fills the
wedge inside an acute tip, or blobs a thin stroke end as the same.  To a viewer they are very different.  `weights(D)` returns a map >= 1 that is
larger on exactly those places:
  * thin white  (corridors / wedges / slivers narrower than ~0.6 stroke widths between ink)
  * thin black  (tips and thin strokes narrower than ~0.6 stroke widths)
The Doctor's soft mismatch and the optimiser loss use it, so every verification step "feels" these places and keeps them instead of trading them for a
slightly better average edge.  Cached per source map.
"""
from __future__ import annotations
import numpy as np, cv2

_CACHE = {}
GAIN = 3.0


def _thin(mask, d):
    k = max(3, int(round(d)) | 1)
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m = mask.astype(np.uint8)
    op = cv2.dilate(cv2.erode(m, se), se)
    return (m > 0) & (op == 0)


def weights(D, w=None, gain=GAIN):
    key = (D.shape, float(D.sum()), float(D[::7, ::7].sum()), gain)
    if key in _CACHE:
        return _CACHE[key]
    if w is None:
        from .split import estimate_width
        w = estimate_width(D)
    ink = D > 0.5
    thin = _thin(~ink, 0.6 * w) | _thin(ink, 0.6 * w)
    # a one-pixel fringe between ink and background is "thin white" for blurry edges: ignore specks smaller than a pixel row
    thin = cv2.morphologyEx(thin.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
    Wt = 1.0 + gain * cv2.GaussianBlur(cv2.dilate(thin.astype(np.float32), np.ones((3, 3), np.uint8)), (0, 0), 1.0).clip(0, 1)
    Wt = Wt.astype(np.float32)
    if len(_CACHE) > 16:
        _CACHE.clear()
    _CACHE[key] = Wt
    return Wt
