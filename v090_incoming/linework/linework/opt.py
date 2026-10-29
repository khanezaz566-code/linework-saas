"""Gradient-based Edit core: fits Bezier control points + stroke widths to the source ink map.

Soft coverage of every path:  c = sigmoid((w/2 - dist(pixel, path)) / tau),  union = max over paths.
Loss = sum (union - ink)^2 + weak priors.  Analytic gradients through the point-to-polyline distance,
optimised with L-BFGS over tau = coarse -> fine, so edges snap to sub-pixel accuracy.
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from .model import Model, Path


def _ctrl(p: Path):
    n = len(p.A) - 1
    C = np.zeros((3 * n + 1, 2))
    C[0] = p.A[0]
    for i in range(n):
        C[3 * i + 1] = p.Hout[i]
        C[3 * i + 2] = p.Hin[i + 1]
        C[3 * i + 3] = p.A[i + 1]
    return C


def _unctrl(p: Path, C):
    n = len(p.A) - 1
    if p.closed:
        C = C.copy()
        C[-1] = C[0]
    p.A[0] = C[0]
    for i in range(n):
        p.Hout[i] = C[3 * i + 1]
        p.Hin[i + 1] = C[3 * i + 2]
        p.A[i + 1] = C[3 * i + 3]
    if p.closed:
        p.Hin[0] = p.Hin[-1]
        p.Hout[-1] = p.Hout[0]


def _sample_matrix(C, step=0.9):
    """Dense matrix M (nS x nC): samples = M @ C."""
    n = (len(C) - 1) // 3
    rows, blocks = [], []
    for i in range(n):
        c = C[3 * i : 3 * i + 4]
        L = sum(np.linalg.norm(c[k + 1] - c[k]) for k in range(3))
        k = max(4, int(np.ceil(L / step)))
        t = np.linspace(0, 1, k + 1)
        if i < n - 1:
            t = t[:-1]
        mt = 1 - t
        B = np.stack([mt**3, 3 * mt**2 * t, 3 * mt * t**2, t**3], 1)
        blocks.append((i, B))
    nS = sum(len(B) for _, B in blocks)
    M = np.zeros((nS, len(C)))
    r = 0
    for i, B in blocks:
        M[r : r + len(B), 3 * i : 3 * i + 4] = B
        r += len(B)
    return M


def _poly_dist(X, S):
    """Distance from points X (m,2) to polyline S (nS,2); returns d, seg index, t."""
    tree = cKDTree(S)
    _, j = tree.query(X)
    nS = len(S)
    best_d = np.full(len(X), np.inf)
    best_s = np.zeros(len(X), int)
    best_t = np.zeros(len(X))
    for off in (-1, 0):
        s = np.clip(j + off, 0, nS - 2)
        a, b = S[s], S[s + 1]
        ab = b - a
        den = np.maximum((ab * ab).sum(1), 1e-12)
        t = np.clip(((X - a) * ab).sum(1) / den, 0, 1)
        q = a + ab * t[:, None]
        d = np.hypot(X[:, 0] - q[:, 0], X[:, 1] - q[:, 1])
        m = d < best_d
        best_d = np.where(m, d, best_d)
        best_s = np.where(m, s, best_s)
        best_t = np.where(m, t, best_t)
    return best_d, best_s, best_t


def refine(model: Model, D: np.ndarray, free=None, window=None, taus=(1.0, 0.6, 0.38), iters=30,
           lam_pos=0.02, lam_w=0.05, fit_width=True, wtarget=None, mu_g1=300.0, g1_deg=30.0):
    """Return a refined copy of `model`. `free`: indices of paths to optimise (default all);
    `window`: (x0,y0,x1,y1) restricting the loss region."""
    m = model.copy()
    H, W = D.shape
    x0, y0, x1, y1 = (0, 0, W, H) if window is None else (max(int(window[0]), 0), max(int(window[1]), 0), min(int(window[2]), W), min(int(window[3]), H))
    if x1 - x0 < 3 or y1 - y0 < 3:
        return m
    free = list(range(len(m.paths))) if free is None else [i for i in free if 0 <= i < len(m.paths)]
    if not free:
        return m
    Dw = D[y0:y1, x0:x1]
    from . import focus as FC
    Wf = FC.weights(D)[y0:y1, x0:x1].ravel()
    wh = (y1 - y0, x1 - x0)
    C0 = {i: _ctrl(m.paths[i]) for i in free}
    w0 = {i: m.paths[i].w for i in free}
    fixed = [i for i in range(len(m.paths)) if i not in free]

    for stage, tau in enumerate(taus):
        # pixel sets per free path (band around current polyline)
        Ms, idxs, pix = {}, {}, {}
        for i in free:
            p = m.paths[i]
            Ms[i] = _sample_matrix(_ctrl(p))
            S = Ms[i] @ _ctrl(p)
            mk = np.zeros(wh, np.uint8)
            q = np.round((S - [x0, y0]) * 16).astype(np.int32)
            cv2.polylines(mk, [q], False, 1, thickness=int(p.w + 6 + 6 * tau), lineType=cv2.LINE_8, shift=4)
            ii = np.flatnonzero(mk.ravel())
            idxs[i] = ii
            yy, xx = np.divmod(ii, wh[1])
            pix[i] = np.stack([xx + x0 + 0.5, yy + y0 + 0.5], 1)
        # constant coverage from fixed paths
        base = np.zeros(wh, np.float32)
        for i in fixed:
            p = m.paths[i]
            S = p.flat(0.7)
            mk = np.zeros(wh, np.uint8)
            q = np.round((S - [x0, y0]) * 16).astype(np.int32)
            cv2.polylines(mk, [q], False, 1, thickness=int(p.w + 6 + 6 * tau), lineType=cv2.LINE_8, shift=4)
            ii = np.flatnonzero(mk.ravel())
            yy, xx = np.divmod(ii, wh[1])
            X = np.stack([xx + x0 + 0.5, yy + y0 + 0.5], 1)
            d, _, _ = _poly_dist(X, S)
            c = 1 / (1 + np.exp(-(p.w / 2 - d) / tau))
            bf = base.ravel()
            bf[ii] = np.maximum(bf[ii], c)
        joints = {}
        for i in free:
            C = _ctrl(m.paths[i])
            n = (len(C) - 1) // 3
            ks = []
            rng = range(0 if m.paths[i].closed else 1, n if m.paths[i].closed else n)
            for k in rng:
                a = C[3 * k]
                hin = C[3 * k - 1] if k > 0 else C[-2]
                hout = C[3 * k + 1]
                p, q = a - hin, hout - a
                np_, nq = np.linalg.norm(p), np.linalg.norm(q)
                if np_ < 1e-6 or nq < 1e-6:
                    continue
                if np.degrees(np.arccos(np.clip(p @ q / (np_ * nq), -1, 1))) < g1_deg:
                    ks.append(k)
            joints[i] = np.array(ks, int)
        union_idx = np.unique(np.concatenate([idxs[i] for i in free]))
        sizes = [(len(C0[i]) * 2) for i in free]
        offs = np.r_[0, np.cumsum(sizes)]
        nw = len(free) if fit_width else 0
        th0 = np.concatenate([_ctrl(m.paths[i]).ravel() for i in free] + ([[m.paths[i].w for i in free]] if fit_width else []))
        thref = np.concatenate([C0[i].ravel() for i in free] + ([[w0[i] for i in free]] if fit_width else []))
        if wtarget is None:
            wt = np.array([w0[i] for i in free])
        else:
            wt = np.full(len(free), wtarget)

        def unpack(th):
            Cs = {i: th[offs[k] : offs[k + 1]].reshape(-1, 2) for k, i in enumerate(free)}
            ws = th[offs[-1] :] if fit_width else np.array([m.paths[i].w for i in free])
            return Cs, ws

        def f(th):
            Cs, ws = unpack(th)
            cov = base.ravel().copy()
            owner = np.full(cov.shape, -1, np.int16)
            store = {}
            for k, i in enumerate(free):
                C = Cs[i].copy()
                if m.paths[i].closed:
                    C[-1] = C[0]
                S = Ms[i] @ C
                d, s, t = _poly_dist(pix[i], S)
                r = ws[k] / 2
                c = 1 / (1 + np.exp(-(r - d) / tau))
                ii = idxs[i]
                upd = c > cov[ii]
                cov[ii[upd]] = c[upd]
                owner[ii[upd]] = k
                store[k] = (S, d, s, t, c, upd)
            diff = cov[union_idx] - Dw.ravel()[union_idx]
            wtd = Wf[union_idx]
            loss = float((wtd * diff**2).sum())
            gfull = np.zeros(cov.shape)
            gfull[union_idx] = 2 * wtd * diff
            g = np.zeros_like(th)
            for k, i in enumerate(free):
                S, d, s, t, c, upd = store[k]
                ii = idxs[i]
                own = upd & (owner[ii] == k)
                if not own.any():
                    continue
                gc = gfull[ii][own]
                cc = c[own]
                sg = cc * (1 - cc) / tau
                gd = -gc * sg
                if fit_width:
                    g[offs[-1] + k] += float((gc * sg).sum()) * 0.5
                X = pix[i][own]
                dd = d[own]
                ss = s[own]
                tt = t[own]
                q = S[ss] * (1 - tt)[:, None] + S[ss + 1] * tt[:, None]
                e = (q - X) / np.maximum(dd, 1e-6)[:, None]
                ge = gd[:, None] * e
                nS_ = len(S)
                w0_, w1_ = (1 - tt)[:, None], tt[:, None]
                gS = np.empty_like(S)
                for ax in (0, 1):  # scatter-add with bincount (much faster than np.add.at)
                    gS[:, ax] = (np.bincount(ss, ge[:, ax] * w0_[:, 0], nS_) + np.bincount(ss + 1, ge[:, ax] * w1_[:, 0], nS_ + 1)[:nS_])
                gC = Ms[i].T @ gS
                if m.paths[i].closed:
                    gC[0] += gC[-1]
                    gC[-1] = 0
                g[offs[k] : offs[k + 1]] += gC.ravel()
            # G1 continuity at joints that are smooth in the current model
            for k, i in enumerate(free):
                ks = joints[i]
                if not len(ks) or mu_g1 <= 0:
                    continue
                C = Cs[i]
                ia = 3 * ks
                ih = np.where(ks > 0, 3 * ks - 1, len(C) - 2)
                io = 3 * ks + 1
                p = C[ia] - C[ih]
                q = C[io] - C[ia]
                npn = np.maximum(np.linalg.norm(p, axis=1), 1e-3)
                nqn = np.maximum(np.linalg.norm(q, axis=1), 1e-3)
                cr = p[:, 0] * q[:, 1] - p[:, 1] * q[:, 0]
                sn = cr / (npn * nqn)
                loss += mu_g1 * float((sn**2).sum())
                dc = (2 * mu_g1 * sn / (npn * nqn))[:, None]
                dp = np.stack([q[:, 1], -q[:, 0]], 1)
                dq = np.stack([-p[:, 1], p[:, 0]], 1)
                gk = np.zeros_like(C)
                np.add.at(gk, ia, dc * (dp - dq))
                np.add.at(gk, ih, dc * (-dp))
                np.add.at(gk, io, dc * dq)
                if m.paths[i].closed:
                    gk[0] += gk[-1]
                    gk[-1] = 0
                g[offs[k] : offs[k + 1]] += gk.ravel()
            # priors
            dth = th - thref
            pos_part = dth[: offs[-1]]
            loss += lam_pos * float((pos_part**2).sum())
            g[: offs[-1]] += 2 * lam_pos * pos_part
            if fit_width:
                dw = th[offs[-1] :] - wt
                loss += lam_w * float((dw**2).sum())
                g[offs[-1] :] += 2 * lam_w * dw
            return loss, g

        nctrl = len(th0) - nw
        bnds = [(None, None)] * nctrl + [(max(1.0, 0.5 * w0[i]), 2.0 * w0[i]) for i in free] if fit_width else None
        res = minimize(f, th0, jac=True, method="L-BFGS-B", bounds=bnds, options=dict(maxiter=iters, maxcor=12, ftol=2e-6, gtol=1e-6))
        Cs, ws = unpack(res.x)
        for k, i in enumerate(free):
            p = m.paths[i]
            _unctrl(p, Cs[i])
            if fit_width:
                p.w = float(ws[k])
    return m
