"""Split an icon sheet into individual icons (connected clusters of ink)."""
from __future__ import annotations
import numpy as np, cv2
from skimage.morphology import skeletonize
from scipy import ndimage as ndi


def estimate_width(D):
    mask = D > 0.5
    if mask.sum() < 50:
        return 8.0
    sk = skeletonize(mask)
    dt = ndi.distance_transform_edt(mask)
    v = dt[sk]
    if v.size == 0:
        return 8.0
    return float(2 * np.median(v))


def find_icons(D, merge=1.15, min_area_w2=6.0):
    """Return (w_est, list of dict(box=(x0,y0,x1,y1), label_mask_fn)) in reading order."""
    mask = (D > 0.5).astype(np.uint8)
    w = estimate_width(D)
    k = int(max(3, round(2 * merge * w)))
    k += (k + 1) % 2
    dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(dil)
    icons = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        ink = int((mask[lab == i]).sum())
        if ink < min_area_w2 * w * w * 0.5:
            continue
        icons.append(dict(id=i, box=[int(x), int(y), int(x + bw), int(y + bh)], ink=ink))
    # an icon sitting entirely inside another icon's box (e.g. the X on a cushion) belongs to it
    def inside(a, b, tol=4):
        return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol
    keep = []
    for ic in sorted(icons, key=lambda c: -((c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]))):
        host = next((h for h in keep if inside(ic["box"], h["box"])), None)
        if host is not None:
            lab[lab == ic["id"]] = host["id"]
            host["ink"] += ic["ink"]
        else:
            keep.append(ic)
    icons = keep
    # reading order: cluster rows by vertical centre
    if icons:
        hs = np.median([ic["box"][3] - ic["box"][1] for ic in icons])
        icons.sort(key=lambda ic: ((ic["box"][1] + ic["box"][3]) / 2))
        rows, cur = [], [icons[0]]
        for ic in icons[1:]:
            cy = (ic["box"][1] + ic["box"][3]) / 2
            if abs(cy - np.mean([(c["box"][1] + c["box"][3]) / 2 for c in cur])) < 0.5 * hs:
                cur.append(ic)
            else:
                rows.append(cur)
                cur = [ic]
        rows.append(cur)
        icons = [ic for r in rows for ic in sorted(r, key=lambda c: c["box"][0])]
    return w, icons, lab


def crop_icon(gray, lab, ic, pad, bg):
    H, W = gray.shape
    x0, y0, x1, y1 = ic["box"]
    X0, Y0, X1, Y1 = max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, W), min(y1 + pad, H)
    g = gray[Y0:Y1, X0:X1].copy()
    own = (lab[Y0:Y1, X0:X1] == ic["id"])
    # keep only this icon's cluster (dilated slightly to preserve anti-aliased edges)
    own = cv2.dilate(own.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    g[~own] = bg
    # extra white margin so strokes at the crop border are not clipped
    g = cv2.copyMakeBorder(g, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=int(bg))
    return g, (X0 - 6, Y0 - 6)
