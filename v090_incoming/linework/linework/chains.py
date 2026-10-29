"""Junction-aware assembly: trimmed branches -> long continuous centerline chains.

Branches are cut back by ~one stroke width around every junction (the skeleton is distorted there),
then re-linked: collinear ends become one smooth through-stroke, T-stems are extended to the
through-stroke's centreline, and corners/Y-joins meet at the intersection of their end tangents.
"""
from __future__ import annotations
import numpy as np
from .geom import resample, unit, hermite, line_inter


def global_width(branches):
    ws = np.array([b["w"] for b in branches])
    lens = np.array([len(b["pts"]) for b in branches], float)
    m = float(np.median(ws))
    sel = (ws > 0.85 * m) & (ws < 1.15 * m)
    W0 = float(np.average(ws[sel], weights=lens[sel])) if sel.any() else m
    return W0


def build_chains(branches, snap_width=True):
    br = [dict(b) for b in branches]
    for b in br:
        b["pts"] = resample(np.asarray(b["pts"], float), 1.0)
    if not br:
        return [], 0.0
    W0 = global_width(br)
    tol = max(1.3, 0.08 * W0)

    def oriented(b, e):  # points ordered far -> junction end
        return b["pts"] if e == 1 else b["pts"][::-1]

    def end_info(b, e, T):
        q = oriented(b, e)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
        n = len(q)
        T = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
        k = n - 1 - int(np.searchsorted(L, T))
        k = max(k, 2)
        lo = max(k - 14, 0)
        d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
        return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

    ends = {}
    for i, b in enumerate(br):
        if b["sj"] > 0:
            ends.setdefault(b["sj"], []).append((i, 0))
        if b["ej"] > 0:
            ends.setdefault(b["ej"], []).append((i, 1))
    info, link, ext = {}, {}, {}
    for j, l in ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        T = 1.0 * w
        for (i, e) in l:
            info[(i, e)] = end_info(br[i], e, T)
        best = None
        for x in range(len(l)):
            for y in range(x + 1, len(l)):
                a, b = l[x], l[y]
                if a[0] == b[0]:
                    continue
                ang = np.degrees(np.arccos(np.clip(-info[a]["d"] @ info[b]["d"], -1, 1)))
                if best is None or ang < best[0]:
                    best = (ang, a, b)
        used = set()
        if len(l) == 2 and best:
            ang, a, b = best
            A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
            if ang < 28:
                pts = hermite(A1, d1, A2, d2)
            else:
                C = line_inter(A1, d1, A2, d2) if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-3 else None
                cen = np.mean([info[a]["full"][-1], info[b]["full"][-1]], axis=0)
                if C is not None and np.linalg.norm(C - cen) < 3 * w and (C - A1) @ d1 > -2 and (C - A2) @ d2 > -2:
                    n1 = max(2, int(np.linalg.norm(C - A1)) + 1)
                    n2 = max(2, int(np.linalg.norm(A2 - C)) + 1)
                    pts = np.vstack([np.linspace(A1, C, n1), np.linspace(C, A2, n2)[1:]])
                else:
                    pts = hermite(A1, d1, A2, d2)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
            used = {a, b}
        elif len(l) >= 3 and best and best[0] < 28:
            ang, a, b = best
            A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
            pts = hermite(A1, d1, A2, d2)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
            used = {a, b}
            thr = np.vstack([info[a]["kept"][-int(2 * w):], pts])
            for o in l:
                if o in used:
                    continue
                A, d = info[o]["A"], info[o]["d"]
                ts = np.arange(0, 4 * w, 0.5)
                ray = A[None] + d[None] * ts[:, None]
                dist = np.array([np.min(np.linalg.norm(thr - r, axis=1)) for r in ray])
                ext[o] = A + d * ts[int(np.argmin(dist))]
        else:
            M = np.zeros((2, 2))
            v = np.zeros(2)
            for o in l:
                d = info[o]["d"]
                Pm = np.eye(2) - np.outer(d, d)
                M += Pm
                v += Pm @ info[o]["A"]
            try:
                C = np.linalg.solve(M, v)
            except Exception:
                C = np.mean([info[o]["full"][-1] for o in l], axis=0)
            cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
            if np.linalg.norm(C - cen) > 2.5 * w:
                C = cen
            for o in l:
                ext[o] = C

    nb = len(br)

    def body(i, e_start):
        pts = br[i]["pts"]
        lo, hi = 0, len(pts) - 1
        if (i, 0) in info:
            lo = int(np.argmin(np.linalg.norm(pts - info[(i, 0)]["A"], axis=1)))
        if (i, 1) in info:
            hi = int(np.argmin(np.linalg.norm(pts - info[(i, 1)]["A"], axis=1)))
        q = pts[lo : hi + 1] if hi > lo else pts[lo : lo + 2]
        return q if e_start == 0 else q[::-1]

    def ext_pts(key, toward_junction):
        A, E = info[key]["A"], ext[key]
        n = max(2, int(np.linalg.norm(E - A)) + 1)
        seg = np.linspace(A, E, n)
        return seg[1:] if toward_junction else seg[::-1][:-1]

    seen = set()
    final, widths = [], []

    def build(i, es):
        parts, cur, e, wsum, wn = [], i, es, 0.0, 0
        if (cur, e) in info and (cur, e) in ext:
            parts.append(ext_pts((cur, e), False))
        while True:
            seen.add(cur)
            q = body(cur, e)
            parts.append(q)
            wsum += br[cur]["w"] * len(q)
            wn += len(q)
            te = 1 - e
            key = (cur, te)
            if key in link:
                (j, e2), bp = link[key]
                parts.append(bp[1:-1] if len(bp) > 2 else bp[:0])
                if j in seen:
                    break
                cur, e = j, e2
                continue
            if key in info and key in ext:
                parts.append(ext_pts(key, True))
            break
        return np.vstack(parts), wsum / max(wn, 1)

    for i in range(nb):
        if i in seen:
            continue
        for es in (0, 1):
            if (i, es) not in link:
                P, w = build(i, es)
                final.append(P)
                widths.append(w)
                break
    for i in range(nb):
        if i not in seen:
            P, w = build(i, 0)
            final.append(P)
            widths.append(w)
    out = []
    for P, w in zip(final, widths):
        if snap_width and abs(w - W0) < tol:
            w = W0
        out.append(dict(pts=resample(P, 1.0), w=float(w)))
    return out, W0
