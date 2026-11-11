"""Split an icon sheet into individual icons (connected clusters of ink)."""
from __future__ import annotations
import numpy as np, cv2
from skimage.morphology import skeletonize
from scipy import ndimage as ndi


def estimate_width(D):
    mask = (D > 0.5).astype(np.uint8)
    if int(mask.sum()) < 50:
        return 8.0
    if max(mask.shape) > 900:
        ys, xs = np.where(mask > 0)
        vals = []
        for frac in (0.3, 0.7):
            idx = int(len(ys) * frac)
            y0, x0 = int(ys[idx]), int(xs[idx])
            sub = mask[max(0, y0 - 160):y0 + 160, max(0, x0 - 160):x0 + 160]
            if int(sub.sum()) >= 30:
                sk_s = skeletonize(sub > 0)
                dt_s = cv2.distanceTransform(sub, cv2.DIST_L2, 5)
                v_s = dt_s[sk_s]
                if v_s.size:
                    vals.append(v_s)
        if vals:
            v = np.concatenate(vals)
            return float(2 * np.median(v))
    sk = skeletonize(mask > 0)
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    v = dt[sk]
    if v.size == 0:
        return 8.0
    return float(2 * np.median(v))


def find_icons(D, merge=1.15, min_area_w2=6.0):
    """Return (w_est, list of dict(box=(x0,y0,x1,y1), label_mask_fn)) in reading order."""
    mask = (D > 0.5).astype(np.uint8)
    H_m, W_m = mask.shape
    # Filter out outer border/matte components spanning the whole sheet
    if min(H_m, W_m) >= 40:
        n_raw, lab_raw, st_raw, _ = cv2.connectedComponentsWithStats(mask)
        for i_r in range(1, n_raw):
            x_r, y_r, bw_r, bh_r, _ = st_raw[i_r]
            is_outer_frame = (bw_r >= 0.85 * W_m and bh_r >= 0.85 * H_m)
            is_letterbox_bar = (
                (bw_r >= 0.70 * W_m and (y_r <= 4 or y_r + bh_r >= H_m - 4) and bw_r >= 5 * bh_r) or
                (bh_r >= 0.70 * H_m and (x_r <= 4 or x_r + bw_r >= W_m - 4) and bh_r >= 5 * bw_r)
            )
            if is_outer_frame or is_letterbox_bar:
                mask = mask.copy()
                mask[lab_raw == i_r] = 0
    w = estimate_width(D)
    k = int(max(3, round(2 * merge * w)))
    k += (k + 1) % 2
    if k > 15 and max(mask.shape) > 900:
        kr = int(max(3, round(1.82 * merge * w)))
        kr += (kr + 1) % 2
        dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kr, kr)))
    else:
        dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(dil)
    del dil
    icons = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        sub_lab = lab[y:y + bh, x:x + bw]
        sub_mask = mask[y:y + bh, x:x + bw]
        ink = int(sub_mask[sub_lab == i].sum())
        if ink < min_area_w2 * w * w * 0.5:
            continue
        icons.append(dict(id=i, box=[int(x), int(y), int(x + bw), int(y + bh)], ink=ink))
    del mask
    # an icon sitting entirely inside another icon's box (e.g. the X on a cushion) belongs to it
    def inside(a, b, tol=4):
        return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol
    keep = []
    for ic in sorted(icons, key=lambda c: -((c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]))):
        host = next((h for h in keep if inside(ic["box"], h["box"])), None)
        if host is not None:
            bx0, by0, bx1, by1 = ic["box"]
            sub_l = lab[by0:by1, bx0:bx1]
            sub_l[sub_l == ic["id"]] = host["id"]
            host["ink"] += ic["ink"]
        else:
            keep.append(ic)
    icons = keep
    # Companion merging: merge disconnected pieces belonging to the same icon (e.g. pause bars ||,
    # colon :, equals sign =, exclamation/question mark dots, detached user head/body)
    if len(icons) > 1:
        sizes = [max(ic["box"][2] - ic["box"][0], ic["box"][3] - ic["box"][1]) for ic in icons]
        med_size = float(np.median(sizes))
        max_dim = max(med_size * 1.55, 60.0)
        max_gap = max(4.0 * w, 28.0)
        merged = True
        while merged:
            merged = False
            n_ic = len(icons)
            for i in range(n_ic):
                if merged:
                    break
                b1 = icons[i]["box"]
                for j in range(i + 1, n_ic):
                    b2 = icons[j]["box"]
                    x_ov = min(b1[2], b2[2]) - max(b1[0], b2[0])
                    y_ov = min(b1[3], b2[3]) - max(b1[1], b2[1])
                    dx = max(0, max(b1[0] - b2[2], b2[0] - b1[2]))
                    dy = max(0, max(b1[1] - b2[3], b2[1] - b1[3]))

                    should_merge = False
                    if x_ov > 0 and dy <= max_gap:
                        should_merge = True
                    elif y_ov > 0 and dx <= max_gap:
                        should_merge = True
                    elif dx <= w * 1.5 and dy <= w * 1.5:
                        should_merge = True

                    if should_merge:
                        nb = [min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3])]
                        if (nb[2] - nb[0]) <= max_dim and (nb[3] - nb[1]) <= max_dim:
                            id1, id2 = icons[i]["id"], icons[j]["id"]
                            sub_l = lab[nb[1]:nb[3], nb[0]:nb[2]]
                            sub_l[sub_l == id2] = id1
                            icons[i]["box"] = nb
                            icons[i]["ink"] += icons[j]["ink"]
                            icons.pop(j)
                            merged = True
                            break
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
