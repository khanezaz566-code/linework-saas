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
    g = gray.astype(np.float32)
    border = np.r_[g[0], g[-1], g[:, 0], g[:, -1]]
    if np.median(border) < 128:
        g = 255 - g
    t, _ = cv2.threshold(g.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark, light = g[g <= t], g[g > t]
    lo = float(np.median(dark)) if dark.size else 0.0
    hi = float(np.median(light)) if light.size else 255.0
    if hi - lo < 30:
        lo, hi = 0.0, 255.0
    return np.clip((hi - g) / (hi - lo), 0, 1).astype(np.float32)


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
    sk = skeletonize(mask)
    H, W = sk.shape
    sk = _prune(sk, prune if prune is not None else 7 * S, H, W)
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


def refine_branch(D, P, its=3, R=None, wmax=40.0):
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
        ok &= w < wmax
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


def refined_branches(D, S=2):
    """Full tracing stage -> list of dict(pts, w, sj, ej), coords in source pixel-index space."""
    out = []
    for b in skeleton_branches(D, S):
        P = resample(b["pts"], 1.0)
        if len(P) < 4:
            continue
        P2, W = refine_branch(D, P)
        w = float(np.nanmedian(W)) if np.isfinite(W).any() else 0.0
        if w <= 0:
            continue
        if b["sj"] == 0:
            P2[0] = extend_end(D, P2, 0, w / 2)
        if b["ej"] == 0:
            P2[-1] = extend_end(D, P2, 1, w / 2)
        out.append(dict(pts=P2, w=w, sj=b["sj"], ej=b["ej"]))
    return out
