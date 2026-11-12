"""Raster -> skeleton graph -> edge-centred branches with measured stroke width."""
from __future__ import annotations
import numpy as np, cv2
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates, gaussian_filter1d
from skimage.morphology import skeletonize
from .geom import resample, arclen, unit

_K = np.ones((3, 3))
_K[1, 1] = 0


def ink_map(gray: np.ndarray) -> np.ndarray:
    """Normalised ink coverage in [0,1] (1 = ink). Handles dark-on-light and light-on-dark."""
    g_u8 = gray if gray.dtype == np.uint8 else np.clip(gray, 0, 255).astype(np.uint8)
    border = np.r_[g_u8[0], g_u8[-1], g_u8[:, 0], g_u8[:, -1]]
    is_dark_bg = np.median(border) < 128
    if is_dark_bg and min(g_u8.shape) >= 20:
        pad = min(8, min(g_u8.shape) // 10)
        if pad > 0:
            inset = np.r_[g_u8[pad], g_u8[-pad - 1], g_u8[:, pad], g_u8[:, -pad - 1]]
            # If inset margin is bright or image has predominantly light pixels, border is an outer frame/matte
            if np.median(inset) > 160 or (g_u8 > 160).sum() > 0.45 * g_u8.size:
                is_dark_bg = False
                dark_mask = (g_u8 < 128).astype(np.uint8)
                n_comp, lab_comp, st_comp, _ = cv2.connectedComponentsWithStats(dark_mask)
                H_c, W_c = g_u8.shape
                bg_val = int(np.median(inset))
                for i_c in range(1, n_comp):
                    x_c, y_c, bw_c, bh_c, _ = st_comp[i_c]
                    is_outer_frame = (bw_c >= 0.85 * W_c and bh_c >= 0.85 * H_c)
                    is_letterbox_bar = (
                        (bw_c >= 0.70 * W_c and (y_c <= 4 or y_c + bh_c >= H_c - 4) and bw_c >= 5 * bh_c) or
                        (bh_c >= 0.70 * H_c and (x_c <= 4 or x_c + bw_c >= W_c - 4) and bh_c >= 5 * bw_c)
                    )
                    if is_outer_frame or is_letterbox_bar:
                        g_u8 = g_u8.copy()
                        g_u8[lab_comp == i_c] = bg_val
    if is_dark_bg:
        g_u8 = 255 - g_u8
    t, _ = cv2.threshold(g_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark, light = g_u8[g_u8 <= t], g_u8[g_u8 > t]
    lo = float(np.median(dark)) if dark.size else 0.0
    hi = float(np.median(light)) if light.size else 255.0
    del dark, light
    if hi - lo < 30:
        lo, hi = 0.0, 255.0
    out = g_u8.astype(np.float32)
    np.subtract(hi, out, out=out)
    out *= (1.0 / (hi - lo))
    np.clip(out, 0.0, 1.0, out=out)
    return out


def _fit_circle(pts: np.ndarray):
    """Algebraic (Kasa) least-squares circle through pts -> (cx, cy, R)."""
    A = np.c_[2.0 * pts[:, 0], 2.0 * pts[:, 1], np.ones(len(pts))]
    b = (pts ** 2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = float(sol[0]), float(sol[1])
    return cx, cy, float(np.sqrt(max(sol[2] + cx * cx + cy * cy, 0.0)))


def find_fused_discs(D: np.ndarray, w: float):
    """Solid round discs (pin-1 markers, graph nodes, lollipop heads) that are fused to strokes.

    A skeleton of disc+stroke makes a spur to the disc centre and drags the neighbouring corner / line off its true path
    (the rounded corner of a chip body touched by its pin-1 dot became a diagonal).  A morphological opening only *locates*
    places where something clearly fatter than the stroke fits; the disc itself is then fitted to the free boundary arcs of
    that place (RANSAC circle fit on the contour), so a disc that overlaps the strokes is still measured exactly.  A circle is
    accepted only if it is (nearly) solid ink inside and its boundary is supported over >= 160 degrees, which rejects the
    outer arc of a rounded corner (hollow inside), filled square blocks and plain junctions.
    Returns [(cx, cy, R)] in pixel-index coordinates.  Isolated discs (the whole component is the disc) are left to
    fitting.add_dots.
    """
    mask = (D > 0.5).astype(np.uint8)
    if mask.size == 0 or min(mask.shape) < 16 or not mask.any():
        return []
    r_s = max(1.5, float(w) / 2.0)
    rho = int(round(1.4 * r_s))
    if rho < 3:
        return []
    op = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rho + 1, 2 * rho + 1)))
    if not op.any():
        return []
    n_o, lab_o, st_o, _ = cv2.connectedComponentsWithStats(op)
    n_m, lab_m, st_m, _ = cv2.connectedComponentsWithStats(mask)
    cnts, _h = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    allpts = np.vstack([c.reshape(-1, 2) for c in cnts]).astype(float) if cnts else np.zeros((0, 2))
    if len(allpts) < 20:
        return []
    r_lo, r_hi = 1.95 * r_s, 3.6 * r_s  # junction hubs and round caps of crossing strokes reach ~1.85 r_s; real discs are fatter
    radii = np.arange(r_lo, r_hi + 0.01, 0.5)
    blur = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 1.0)
    gx_full = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy_full = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    out = []
    H_m, W_m = mask.shape
    for i in range(1, n_o):
        x, y, bw, bh, a = [int(v) for v in st_o[i]]
        if max(bw, bh) > 2 * r_hi + 2 * rho:  # a long fat bar / big filled shape, not a node
            continue
        m = int(np.ceil(r_hi)) + 2
        X0, X1, Y0, Y1 = max(0, x - m), min(W_m, x + bw + m), max(0, y - m), min(H_m, y + bh + m)
        sel = allpts[(allpts[:, 0] >= X0) & (allpts[:, 0] < X1) & (allpts[:, 1] >= Y0) & (allpts[:, 1] < Y1)]
        if len(sel) < 12:
            continue
        ix_, iy_ = sel[:, 0].astype(int), sel[:, 1].astype(int)
        gx, gy = gx_full[iy_, ix_], gy_full[iy_, ix_]
        gn = np.hypot(gx, gy)
        ok = gn > 1e-3
        sel, gx, gy, gn = sel[ok], gx[ok], gy[ok], gn[ok]
        nx, ny = gx / gn, gy / gn  # inward normals (the ink map increases into the ink)
        hh, ww = Y1 - Y0, X1 - X0
        acc = np.zeros((len(radii), hh, ww), np.float32)
        for k, R in enumerate(radii):
            cxs = np.rint(sel[:, 0] + nx * R).astype(int) - X0
            cys = np.rint(sel[:, 1] + ny * R).astype(int) - Y0
            v = (cxs >= 0) & (cxs < ww) & (cys >= 0) & (cys < hh)
            np.add.at(acc[k], (cys[v], cxs[v]), 1.0)
            acc[k] = cv2.boxFilter(acc[k], -1, (3, 3), normalize=False)
        accepted = None
        for _try in range(6):
            kk, cy_l, cx_l = np.unravel_index(int(np.argmax(acc)), acc.shape)
            if acc[kk, cy_l, cx_l] < 8.0:  # votes in a 3x3 cell: at least ~8 boundary points agree on this centre
                break
            cx, cy, R = float(cx_l + X0), float(cy_l + Y0), float(radii[kk])
            acc[:, max(0, cy_l - int(R / 2)):cy_l + int(R / 2) + 1, max(0, cx_l - int(R / 2)):cx_l + int(R / 2) + 1] = 0  # next candidate
            for _ in range(3):  # least-squares refinement on the boundary points that lie on the circle
                dist = np.hypot(sel[:, 0] - cx, sel[:, 1] - cy)
                inl = np.abs(dist - (R - 0.5)) <= 1.2
                if inl.sum() < 10:
                    break
                cx, cy, Rf = _fit_circle(sel[inl])
                R = Rf + 0.5  # contour pixels sit half a pixel inside the true edge
            if not (r_lo <= R <= r_hi):
                continue
            dist = np.hypot(sel[:, 0] - cx, sel[:, 1] - cy)
            inl = np.abs(dist - (R - 0.5)) <= 1.2
            ang = np.arctan2(sel[inl, 1] - cy, sel[inl, 0] - cx)
            bins = np.unique(((ang + np.pi) / (2 * np.pi) * 36).astype(int) % 36)
            if len(bins) < 16:  # < 160 degrees of the circle is a free boundary: merged arcs / fat bars, not a disc
                continue
            yy, xx = np.mgrid[int(max(0, cy - R)):int(min(H_m, cy + R + 1)), int(max(0, cx - R)):int(min(W_m, cx + R + 1))]
            inside = np.hypot(xx - cx, yy - cy) <= max(R - 1.5, 1.0)
            if inside.sum() < 8 or float(mask[yy, xx][inside].mean()) < 0.95:
                continue  # hollow: the outer arc of a rounded corner / ring
            ml = int(lab_m[int(round(min(max(cy, 0), H_m - 1))), int(round(min(max(cx, 0), W_m - 1)))])
            if ml == 0 or float(st_m[ml, cv2.CC_STAT_AREA]) < 1.3 * np.pi * R * R:
                continue  # standalone disc
            if any(np.hypot(cx - ox, cy - oy) < 0.6 * max(R, oR) for ox, oy, oR in out):
                continue  # the same disc seen from a neighbouring opening component
            accepted = (float(cx), float(cy), float(R))
            find_fused_discs.debug.append(dict(cx=float(cx), cy=float(cy), R=float(R), arc_bins=int(len(bins)), r_ratio=float(R / r_s), votes=float(acc[kk, cy_l, cx_l])))
            break
        if accepted is not None:
            out.append(accepted)
    return out


find_fused_discs.debug = []  # diagnostics of the last calls (arc support, radius ratio); only read by tests


def erase_discs(Du: np.ndarray, discs, s: float = 1.0) -> np.ndarray:
    """Copy of the ink map with the fused discs removed (discs given at source scale, Du is at s-times resolution)."""
    out = Du.copy()
    for cx, cy, R in discs:
        cv2.circle(out, (int(round(cx * s)), int(round(cy * s))), int(round(R * s)) + 1, 0.0, -1)
    return out


# ---------------------------------------------------------------- skeleton
def _prune(sk, L, H, W):
    sk = sk.copy()
    for _ in range(3):
        nb = ndi.convolve(sk.astype(int), _K, mode="constant") * sk
        ends = np.argwhere((nb == 1) & sk)
        changed = False
        for e in ends:
            path = [tuple(e)]
            cur = tuple(e)
            prev = None
            ns = []
            while True:
                y, x = cur
                ns = [
                    (y + dy, x + dx)
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]
                    and (y + dy, x + dx) != prev and (y + dy, x + dx) not in path
                ]
                if len(ns) != 1:
                    break
                prev = cur
                cur = ns[0]
                path.append(cur)
                if len(path) > L:
                    break
            if len(path) <= L and len(ns) >= 2:
                for p in path[:-1]:
                    sk[p] = False
                changed = True
        sk = skeletonize(sk)
        if not changed:
            break
    return sk


def skeleton_branches(D: np.ndarray, S: int = 2, prune: int | None = None):
    """Return list of branches: dict(pts (N,2) x/y in source pixel-index coords, sj, ej)."""
    up = cv2.resize(D, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
    mask = up > 0.5
    # Fill tiny pinholes (JPEG artifacts / voids inside solid stroke ink)
    filled = ndi.binary_fill_holes(mask)
    holes = filled & ~mask
    if holes.any():
        hole_labels, num_holes = ndi.label(holes)
        max_hole = max(36, S * S * 16)
        for h_id in range(1, num_holes + 1):
            if np.sum(hole_labels == h_id) <= max_hole:
                mask[hole_labels == h_id] = True
    sk = skeletonize(mask)
    H, W = sk.shape
    dt = ndi.distance_transform_edt(mask)
    v = dt[sk]
    w_up = float(2 * np.median(v)) if v.size else (10.0 * S)
    prune_eff = prune if prune is not None else max(2 * S + 1, int(round(0.42 * w_up)))
    sk = _prune(sk, prune_eff, H, W)
    nb = ndi.convolve(sk.astype(int), _K, mode="constant") * sk
    junc = (nb >= 3) & sk
    jl, nj = ndi.label(junc, structure=np.ones((3, 3)))
    ends = (nb == 1) & sk
    off = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]

    def nbrs(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in off if 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]]

    visited = np.zeros_like(sk)
    branches = []
    _cm = ndi.center_of_mass(np.ones(jl.shape, np.uint8), jl, list(range(1, nj + 1))) if nj else []
    jcent = {i: np.array(_cm[i - 1]) for i in range(1, nj + 1)}

    def trace(start, first):
        path = [start, first]
        visited[start] = True
        prev, cur = start, first
        while True:
            if jl[cur] > 0 and cur != start:
                return path, jl[cur]
            visited[cur] = True
            ns = [n for n in nbrs(cur) if n != prev and n not in path[-4:]]
            ns2 = [n for n in ns if not visited[n] or jl[n] > 0]
            if not ns2:
                return path, 0
            ns2.sort(key=lambda n: abs(n[0] - cur[0]) + abs(n[1] - cur[1]))
            prev, cur = cur, ns2[0]
            path.append(cur)

    starts = [(tuple(p), 0) for p in np.argwhere(ends)]
    for p in map(tuple, np.argwhere(junc)):
        for n in nbrs(p):
            if jl[n] == 0:
                starts.append((p, int(jl[p])))
    for p, sj in starts:
        if sj == 0:
            if visited[p]:
                continue
            ns = nbrs(p)
            if not ns:
                continue
            path, ej = trace(p, ns[0])
            branches.append((path, 0, int(ej)))
        else:
            for n in nbrs(p):
                if jl[n] == 0 and not visited[n]:
                    path, ej = trace(p, n)
                    branches.append((path, sj, int(ej)))
    rem = sk & ~visited & (jl == 0)
    lab, nl = ndi.label(rem, structure=np.ones((3, 3)))
    for i in range(1, nl + 1):
        pts = np.argwhere(lab == i)
        if len(pts) < 20:
            continue
        p = tuple(pts[0])
        path = [p]
        cur = p
        seen = {p}
        while True:
            ns = [n for n in nbrs(cur) if n not in seen]
            if not ns:
                break
            ns.sort(key=lambda n: abs(n[0] - cur[0]) + abs(n[1] - cur[1]))
            cur = ns[0]
            seen.add(cur)
            path.append(cur)
        branches.append((path, -1, -1))

    def conv(rc):  # (row,col) at S-scale -> (x,y) source pixel-index coords
        a = np.asarray(rc, float)[:, ::-1]
        return (a + 0.5) / S - 0.5

    out = []
    for path, sj, ej in branches:
        pts = conv(path)
        if sj > 0:
            pts = np.vstack([conv([jcent[sj]])[0:1], pts])
        if ej > 0:
            pts = np.vstack([pts, conv([jcent[ej]])[0:1]])
        out.append(dict(pts=pts, sj=int(sj), ej=int(ej)))
    return out


# ---------------------------------------------------------------- edge centring
def _profile(D, P, N, R, step=0.25):
    t = np.arange(-R, R + step, step)
    X = P[:, 0, None] + N[:, 0, None] * t[None]
    Y = P[:, 1, None] + N[:, 1, None] * t[None]
    return t, map_coordinates(D, [Y, X], order=1, mode="nearest")


def _edges(t, v):
    """Sub-pixel 50 % crossings on both sides of each profile's centre (vectorised)."""
    n, m = v.shape
    c = m // 2
    L = np.full(n, np.nan)
    R = np.full(n, np.nan)
    if m < 5:
        return L, R
    dt = t[1] - t[0]
    below = v < 0.5
    inside = v[:, c] >= 0.5
    seg = below[:, c + 1 : m - 1]  # candidate crossing j = c+1 .. m-2
    has = seg.any(1) & inside
    j = c + 1 + seg.argmax(1)
    i = np.nonzero(has)[0]
    if len(i):
        a, b = v[i, j[i] - 1], v[i, j[i]]
        f = np.where(a != b, (a - 0.5) / np.where(a != b, a - b, 1), 0)
        R[i] = t[j[i] - 1] + f * dt
    segl = below[:, 1:c]  # j = 1 .. c-1, want the nearest one to the centre
    hasl = (segl.any(1) if segl.shape[1] else np.zeros(n, bool)) & inside
    jl = 1 + (segl.shape[1] - 1 - segl[:, ::-1].argmax(1)) if segl.shape[1] else np.zeros(n, int)
    i = np.nonzero(hasl)[0]
    if len(i):
        a, b = v[i, jl[i] + 1], v[i, jl[i]]
        f = np.where(a != b, (a - 0.5) / np.where(a != b, a - b, 1), 0)
        L[i] = t[jl[i] + 1] - f * dt
    return L, R


def _tang(P):
    T = np.gradient(gaussian_filter1d(P, 3, axis=0, mode="nearest"), axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    return T


def refine_branch(D, P, its=3, R=None, wmax=40.0, w_icon=None):
    """Shift samples to the centre between the two 50%-ink edges; return (P, per-sample width)."""
    P = P.copy()
    W = np.full(len(P), np.nan)
    R = R or 22
    for _ in range(its):
        T = _tang(P)
        N = np.c_[-T[:, 1], T[:, 0]]
        t, v = _profile(D, P, N, R)
        L, Rr = _edges(t, v)
        ok = ~np.isnan(L) & ~np.isnan(Rr)
        w = Rr - L
        ok &= (w > 0) & (w < wmax)
        if ok.sum() >= 4:
            w_ref = float(np.percentile(w[ok], 40))
            if w_icon is not None and w_icon > 0 and len(P) < 2.2 * w_icon:
                w_ref = min(w_ref, 1.22 * w_icon)
            ok &= (w <= 1.32 * w_ref) & (np.abs(L + Rr) <= 0.45 * w_ref)
        elif w_icon is not None and w_icon > 0:
            ok &= (w <= 1.35 * w_icon) & (np.abs(L + Rr) <= 0.45 * w_icon)
        off = np.where(ok, (L + Rr) / 2, 0)
        if ok.sum() > 3:
            num = gaussian_filter1d(np.where(ok, off, 0), 2.5, mode="nearest")
            den = np.maximum(gaussian_filter1d(ok.astype(float), 2.5, mode="nearest"), 1e-3)
            offs = np.where(ok, num / den, 0)
            P = P + N * offs[:, None]
        W = np.where(ok, w, np.nan)
    return P, W


def extend_end(D, P, which, r):
    """Move a free endpoint to (stroke tip - r along tangent) so round caps land exactly on the tip."""
    p = P[0] if which == 0 else P[-1]
    q = P[min(8, len(P) - 1)] if which == 0 else P[-1 - min(8, len(P) - 1)]
    d = unit(p - q)
    ts = np.arange(-4, r + 8, 0.25)
    pts = p[None] + d[None] * ts[:, None]
    v = map_coordinates(D, [pts[:, 1], pts[:, 0]], order=1, mode="nearest")
    k = np.where(v < 0.5)[0]
    k = k[k > np.argmax(ts >= 0)] if len(k) else k
    if not len(k):
        return p
    j = k[0]
    a, b = v[j - 1], v[j]
    tip = ts[j - 1] + ((a - 0.5) / (a - b) if a != b else 0) * 0.25
    return p + d * (tip - r)


def march_acute_end(D, P2, w_prof, rw, end_idx):
    """If end_idx (0 or 1) of P2 has a sharp skeleton hook inside a wide junction zone (w_prof > 1.35*rw),
    march from the last clean single-stroke sample along the unobstructed outer ink edge at distance 0.5*rw
    until reaching the single-stroke width of the through-branch."""
    pts = P2 if end_idx == 0 else P2[::-1]
    wp = w_prof if end_idx == 0 else w_prof[::-1]
    n = len(pts)
    if n < max(16, int(2.4 * rw)):
        return P2, False
    clean_mask = np.isfinite(wp) & (wp >= 0.70 * rw) & (wp <= 1.20 * rw)
    clean_idx = np.nonzero(clean_mask)[0]
    if not len(clean_idx):
        return P2, False
    k_clean = int(clean_idx[0])
    if not (max(3, int(0.45 * rw)) <= k_clean <= int(1.65 * rw)):
        return P2, False
    if not np.isfinite(wp[:k_clean]).any() or float(np.nanmax(wp[:k_clean])) < 1.55 * rw:
        return P2, False
    k_back = min(n - 1, k_clean + max(6, int(0.95 * rw)))
    if k_back <= k_clean + 2:
        return P2, False
    cur_pt = pts[k_clean].copy()
    cur_dir = unit(pts[k_clean] - pts[k_back])
    v_stub = pts[0] - pts[k_clean]
    if np.linalg.norm(v_stub) < 0.35 * rw:
        return P2, False
    u_stub = unit(v_stub)
    hook_deg = float(np.degrees(np.arccos(np.clip(u_stub @ cur_dir, -1.0, 1.0))))
    if hook_deg < 28.0:
        return P2, False

    N_dir = np.array([-cur_dir[1], cur_dir[0]])
    stub_side = 1 if (v_stub @ N_dir) >= 0 else -1
    traced = [cur_pt.copy()]
    reached = False
    for step in range(int(2.8 * rw)):
        cand = cur_pt + cur_dir * 1.0
        N_dir = np.array([-cur_dir[1], cur_dir[0]])
        t, v = _profile(D, cand[None, :], N_dir[None, :], 22)
        L, Rr = _edges(t, v)
        l_val, r_val = float(L[0]), float(Rr[0])
        if stub_side > 0:
            if not np.isfinite(l_val):
                break
            off_n = l_val + 0.5 * rw
        else:
            if not np.isfinite(r_val):
                break
            off_n = r_val - 0.5 * rw
        if abs(off_n) > 0.45 * rw:
            break
        next_pt = cand + N_dir * off_n
        w_tot = r_val - l_val if (np.isfinite(l_val) and np.isfinite(r_val)) else 99.0
        cur_dir = unit(0.65 * cur_dir + 0.35 * unit(next_pt - cur_pt))
        cur_pt = next_pt
        traced.append(cur_pt.copy())
        if step >= 3 and w_tot <= 1.08 * rw:
            reached = True
            break
    if not reached or len(traced) < 4:
        return P2, False
    new_pts = np.vstack([np.array(traced[::-1]), pts[k_clean + 1:]])
    return (new_pts if end_idx == 0 else new_pts[::-1]), True


def de_flare_branch(P0, P2, L, Rr, N, rw):
    """Where a branch widens on ONE side (1.08*rw < w <= 1.95*rw) because a second stroke merges into it at a shallow angle,
    lock the branch to its unflared ink edge instead of drifting into the merging stroke."""
    w = Rr - L
    flared = np.isfinite(w) & (w > 1.08 * rw) & (w <= 1.95 * rw)
    if not flared.any():
        return P2
    P_out = P2.copy()
    dL = np.abs(L + 0.5 * rw)
    dR = np.abs(Rr - 0.5 * rw)
    use_L = flared & (dL <= 0.15 * rw) & (dR > 0.22 * rw)
    use_R = flared & (dR <= 0.15 * rw) & (dL > 0.22 * rw)
    if use_L.any():
        P_out[use_L] = P0[use_L] + N[use_L] * (L[use_L] + 0.5 * rw)[:, None]
    if use_R.any():
        P_out[use_R] = P0[use_R] + N[use_R] * (Rr[use_R] - 0.5 * rw)[:, None]
    return P_out


def refined_branches(D, S=2, prune=None):
    """Full tracing stage -> list of dict(pts, w, sj, ej), coords in source pixel-index space."""
    mask = D > 0.5
    if not mask.any():
        return []
    dt = ndi.distance_transform_edt(mask)
    br_raw = skeleton_branches(D, S, prune=prune)
    d_vals = []
    H, W_im = D.shape
    for b in br_raw:
        pts = b["pts"]
        if len(pts) >= 4:
            xs = np.clip(np.round(pts[:, 0]).astype(int), 0, W_im - 1)
            ys = np.clip(np.round(pts[:, 1]).astype(int), 0, H - 1)
            d_vals.append(2.0 * dt[ys, xs])
    w_icon = float(np.percentile(np.concatenate(d_vals), 45)) if d_vals else None

    # Precompute which junctions have a nearly-collinear through-pair (dot < -0.90)
    j_dirs = {}
    for idx_b, b in enumerate(br_raw):
        pts_b = b["pts"]
        if len(pts_b) < 8:
            continue
        if b["sj"] > 0:
            d0 = unit(pts_b[min(len(pts_b) - 1, 24)] - pts_b[min(len(pts_b) - 1, 4)])
            j_dirs.setdefault(b["sj"], []).append((idx_b, d0))
        if b["ej"] > 0:
            d1 = unit(pts_b[max(0, len(pts_b) - 25)] - pts_b[max(0, len(pts_b) - 5)])
            j_dirs.setdefault(b["ej"], []).append((idx_b, d1))
    through_juncs = {}
    for jid, items in j_dirs.items():
        if len(items) >= 3:
            best_pair = None
            best_dot = 1.0
            for a_i in range(len(items)):
                for b_i in range(a_i + 1, len(items)):
                    if items[a_i][0] == items[b_i][0]:
                        continue
                    dt_val = float(items[a_i][1] @ items[b_i][1])
                    if dt_val < best_dot:
                        best_dot = dt_val
                        best_pair = {items[a_i][0], items[b_i][0]}
            if best_dot < -0.90 and best_pair is not None:
                through_juncs[jid] = best_pair

    detached_juncs = set()
    out = []
    for idx_b, b in enumerate(br_raw):
        P = resample(b["pts"], 1.0)
        if len(P) < 3:
            continue
        P2, W = refine_branch(D, P, w_icon=w_icon)
        w = float(np.nanmedian(W)) if np.isfinite(W).any() else (w_icon or 0.0)
        if w <= 0:
            continue
        sj, ej = b["sj"], b["ej"]
        if sj == 0:
            P2[0] = extend_end(D, P2, 0, w / 2)
        if ej == 0:
            P2[-1] = extend_end(D, P2, 1, w / 2)

        if len(P) >= max(14, int(2.2 * w)) and len(P) == len(P2):
            T = _tang(P)
            N = np.c_[-T[:, 1], T[:, 0]]
            t, v = _profile(D, P, N, 22)
            L, Rr = _edges(t, v)
            w_prof = Rr - L

            # 1. Check for a merged double-width run near either end
            wide = np.isfinite(w_prof) & (w_prof >= 1.38 * w) & (w_prof <= 2.35 * w)
            best_run = (0, 0, 0)
            j = 0
            while j < len(wide):
                if not wide[j]:
                    j += 1
                    continue
                m = j
                while m < len(wide) and wide[m]:
                    m += 1
                if m - j > best_run[0]:
                    best_run = (m - j, j, m)
                j = m
            rlen, j0, j1 = best_run
            if rlen >= max(12, int(2.0 * w)) and float(np.nanmax(w_prof[j0:j1])) >= 1.62 * w:
                off_L = gaussian_filter1d(np.where(np.isfinite(L), L + 0.5 * w, 0.0), 2.0, mode="nearest")
                off_R = gaussian_filter1d(np.where(np.isfinite(Rr), Rr - 0.5 * w, 0.0), 2.0, mode="nearest")
                pL = P + N * off_L[:, None]
                pR = P + N * off_R[:, None]

                def straight_dev(pts):
                    ch = pts[-1] - pts[0]
                    cl = float(np.linalg.norm(ch))
                    if cl < 1e-6:
                        return 0.0
                    u = ch / cl
                    return float(np.abs((pts[:, 0] - pts[0, 0]) * u[1] - (pts[:, 1] - pts[0, 1]) * u[0]).max())

                if j0 <= int(0.9 * w) and len(P) - j1 >= int(1.5 * w):
                    ks = min(len(P) - 1, j1 + int(0.4 * w))
                    dev_L = straight_dev(pL[max(2, j0):j1])
                    dev_R = straight_dev(pR[max(2, j0):j1])
                    if min(dev_L, dev_R) <= 0.12 * w and max(dev_L, dev_R) >= 0.25 * w:
                        alpha = np.linspace(1.0, 0.0, ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[0:1], pL[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pR[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        else:
                            wall_pts = np.vstack([P2[0:1], pR[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pL[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        out.append(dict(pts=curve_pts, w=w, sj=-2, ej=ej))
                        out.append(dict(pts=wall_pts, w=w, sj=sj, ej=-2))
                        continue
                elif len(P) - j1 <= int(0.9 * w) and j0 >= int(1.5 * w):
                    ks = max(0, j0 - int(0.4 * w))
                    dev_L = straight_dev(pL[j0:min(len(P) - 2, j1)])
                    dev_R = straight_dev(pR[j0:min(len(P) - 2, j1)])
                    if min(dev_L, dev_R) <= 0.12 * w and max(dev_L, dev_R) >= 0.25 * w:
                        alpha = np.linspace(0.0, 1.0, len(P) - ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[ks:ks+1], pL[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pR[ks:]])
                        else:
                            wall_pts = np.vstack([P2[ks:ks+1], pR[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pL[ks:]])
                        out.append(dict(pts=curve_pts, w=w, sj=sj, ej=-2))
                        out.append(dict(pts=wall_pts, w=w, sj=-2, ej=ej))
                        continue

            # 2. Check for acute/tangential junction hook at either end (only when joining a collinear through-pair)
            if sj in through_juncs and idx_b not in through_juncs[sj]:
                P2, ok0 = march_acute_end(D, P2, w_prof, w, 0)
                if ok0:
                    detached_juncs.add(sj)
                    sj = -2
            if ej in through_juncs and idx_b not in through_juncs[ej] and len(P2) == len(w_prof):
                P2, ok1 = march_acute_end(D, P2, w_prof, w, 1)
                if ok1:
                    detached_juncs.add(ej)
                    ej = -2

        out.append(dict(pts=P2, w=w, sj=sj, ej=ej))

    # For any through-junction where the 3rd acute branch was detached, remove the junction centroid pull and one-sided flare on the remaining 2 collinear branches
    for jid in detached_juncs:
        rem = [(i, 0 if b["sj"] == jid else 1) for i, b in enumerate(out) if b["sj"] == jid or b["ej"] == jid]
        if len(rem) == 2:
            for i_o, _ in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                if len(pts_o) >= 8:
                    T_o = _tang(pts_o)
                    N_o = np.c_[-T_o[:, 1], T_o[:, 0]]
                    t_o, v_o = _profile(D, pts_o, N_o, 22)
                    L_o, Rr_o = _edges(t_o, v_o)
                    out[i_o]["pts"] = de_flare_branch(pts_o, pts_o, L_o, Rr_o, N_o, rw_o)
            projs = []
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    anchor = pts_o[kp]
                    far = pts_o[min(len(pts_o) - 1, kp + max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[0] - anchor))
                else:
                    anchor = pts_o[-1 - kp]
                    far = pts_o[max(0, len(pts_o) - 1 - kp - max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[-1] - anchor))
                projs.append(anchor + u_dir * dist)
            mid_j = 0.5 * (projs[0] + projs[1])
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"].copy()
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[kp]
                else:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[-1 - s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[-1 - kp]
                out[i_o]["pts"] = pts_o
    return out
