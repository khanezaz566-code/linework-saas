"""Structure check: does the render have the same centre-line skeleton as the source?

The Doctor's pixel overlap (IoU / soft mismatch) cannot see most of what people call "small defects": a lump where two strokes merge, a jog, a wobble,
a doubled outline that fused into one thick stroke.  They move the *centre line* by 0.3-1.5 stroke widths over a stretch of 1-3 stroke widths, which
costs only a few pixels of overlap.  Here both images are reduced to the same kind of skeleton and compared point by point:

  render-off   a skeleton point of the RENDER that is far from every skeleton point of the SOURCE   (lump, jog, hook, extra or displaced stroke)
  source-off   a skeleton point of the SOURCE that is far from the RENDER skeleton                    (missing / fused / displaced stroke)

Sites are connected clusters of such points, sorted by severity; `score` is the total severity in stroke widths (0 = same skeleton).
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
from .trace import _prune


def skeleton_points(mask, S=2, prune_w=None):
    """Skeleton (pruned of short spurs) of a boolean mask as (n,2) x/y points in source pixel coordinates."""
    up = cv2.resize(mask.astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST) > 0
    sk = skeletonize(up)
    H, W = sk.shape
    sk = _prune(sk, int(prune_w if prune_w else 7 * S), H, W)
    ys, xs = np.nonzero(sk)
    return np.c_[xs + 0.5, ys + 0.5] / S


def _radius_at(mask, pts):
    from scipy import ndimage as ndi
    dt = ndi.distance_transform_edt(mask)
    q = np.clip(pts.astype(int), 0, [mask.shape[1] - 1, mask.shape[0] - 1])
    return dt[q[:, 1], q[:, 0]]


def compare(D, ink, w, thr=0.12, thick_thr=0.15, min_len=0.8, S=2):
    """Returns dict(score, sites=[dict(kind, x, y, size, severity, box)]) for source ink map D and render ink map `ink`.
    kinds: render-off / source-off (centre line displaced) and thick / thin (render stroke thicker / thinner than the source at the same place)."""
    src = skeleton_points(D > 0.5, S, prune_w=max(4, 0.7 * w * S))
    ren = skeleton_points(ink > 0.5, S, prune_w=max(4, 0.7 * w * S))
    if len(src) == 0 or len(ren) == 0:
        return dict(score=0.0, sites=[])
    ts, tr = cKDTree(src), cKDTree(ren)
    d_ren, i_ren = ts.query(ren)  # render points -> source skeleton
    d_src = tr.query(src)[0]
    r_ren = _radius_at(ink > 0.5, ren)
    r_srcm = _radius_at(D > 0.5, src)[i_ren]  # source radius at the nearest source skeleton point
    dr = (r_ren - r_srcm) / w  # >0: render thicker
    near = d_ren <= 0.5 * w  # thickness is only comparable where the skeletons agree on the position
    sites = []
    H, W = D.shape
    for kind, pts, d in (("render-off", ren, d_ren), ("source-off", src, d_src), ("thick", ren, np.where(near & (dr > thick_thr), (dr - thick_thr) * w + thr * w, 0.0)),
                         ("thin", ren, np.where(near & (dr < -thick_thr), (-dr - thick_thr) * w + thr * w, 0.0))):
        bad = d > thr * w
        if not bad.any():
            continue
        mk = np.zeros((H, W), np.uint8)
        q = np.clip(pts[bad].astype(int), 0, [W - 1, H - 1])
        mk[q[:, 1], q[:, 0]] = 1
        k = int(max(3, 0.6 * w)) | 1
        n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.dilate(mk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))))
        pl = lab[np.clip(pts[bad][:, 1].astype(int), 0, H - 1), np.clip(pts[bad][:, 0].astype(int), 0, W - 1)]
        dd = d[bad]
        for c in range(1, n):
            sel = pl == c
            if sel.sum() < 2:
                continue
            length = sel.sum() / S  # skeleton pixels at S x resolution ~ length in source px
            if length < min_len * w:
                continue
            sev = float(((dd[sel] - thr * w) / w).clip(0).sum() / S)
            x, y, bw, bh, _ = st[c]
            sites.append(dict(kind=kind, x=float(cen[c][0]), y=float(cen[c][1]), size=float(length / w), severity=sev,
                              box=[int(x), int(y), int(x + bw), int(y + bh)]))
    sites.sort(key=lambda s: -s["severity"])
    return dict(score=float(sum(s["severity"] for s in sites)), sites=sites)
