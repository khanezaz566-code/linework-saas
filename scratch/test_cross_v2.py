import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework.trace import ink_map, refined_branches
from linework.geom import resample, unit, hermite, line_inter
from linework import chains as C, pipeline as P

def build_chains_v2(branches, snap_width=True):
    br = [dict(b) for b in branches]
    for b in br:
        b["pts"] = resample(np.asarray(b["pts"], float), 1.0)
    if not br:
        return [], 0.0
    W0 = C.global_width(br)
    tol = max(1.3, 0.08 * W0)

    def oriented(b, e):
        return b["pts"] if e == 1 else b["pts"][::-1]

    def end_info(b, e, T):
        q = oriented(b, e)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
        n = len(q)
        if L[-1] > 2.2 * T and n >= 14:
            k_near = n - 1 - int(np.searchsorted(L, 0.30 * T))
            k_mid  = n - 1 - int(np.searchsorted(L, 0.70 * T))
            k_neck_far = n - 1 - int(np.searchsorted(L, 1.35 * T))
            k_far  = n - 1 - int(np.searchsorted(L, min(2.4 * T, 0.9 * L[-1])))
            k_near = min(n - 2, max(k_near, k_mid + 2))
            if k_near > k_mid > k_neck_far > k_far >= 0:
                d_near = unit(q[k_near] - q[k_mid])
                d_mid  = unit(q[k_mid] - q[k_neck_far])
                d_far  = unit(q[k_neck_far] - q[k_far])
                d_tip  = unit(q[-1] - q[k_near])
                if d_mid @ d_far < np.cos(np.radians(25)) and d_near @ d_mid >= np.cos(np.radians(18)) and d_tip @ d_near >= np.cos(np.radians(22)):
                    k = max(n - 1 - int(np.searchsorted(L, 0.45 * T)), 2)
                    return dict(A=q[k].copy(), d=unit(q[k_near] - q[k_neck_far]), kept=q[: k + 1], full=q)
        T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
        k = n - 1 - int(np.searchsorted(L, T_eff))
        k = max(k, 2)
        lo = max(k - 14, 0)
        d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
        return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

    def is_free_tip(idx):
        b = br[idx]
        return (b["sj"] == 0 or b["ej"] == 0) and len(b["pts"]) < 3.2 * W0

    def is_short_bridge(idx):
        b = br[idx]
        return b["sj"] > 0 and b["ej"] > 0 and len(b["pts"]) < 2.0 * W0

    # Cluster ultra-short internal junction micro-bridges (len <= 1.25 * W0)
    # where a single multi-way intersection split into multiple degree-3+ skeleton junctions
    par_j = {}
    def find_j(j):
        while par_j.get(j, j) != j:
            par_j[j] = par_j.get(par_j[j], par_j[j])
            j = par_j[j]
        return j

    raw_ends = {}
    for i, b in enumerate(br):
        if b["sj"] > 0:
            raw_ends.setdefault(b["sj"], []).append((i, 0))
        if b["ej"] > 0:
            raw_ends.setdefault(b["ej"], []).append((i, 1))

    raw_info = {}
    j_xy = {}
    for j, l in raw_ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        j_xy[j] = np.mean([oriented(br[i], e)[-1] for i, e in l], axis=0)
        for (i, e) in l:
            raw_info[(i, e)] = end_info(br[i], e, w)

    # First union junctions that are spatially within 0.65 * W0 (e.g. when a <4px bridge was dropped) or connected by <= 1.35 * W0 bridge
    j_keys = sorted(raw_ends.keys())
    for a_idx in range(len(j_keys)):
        for b_idx in range(a_idx + 1, len(j_keys)):
            j0, j1 = j_keys[a_idx], j_keys[b_idx]
            w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends[j0] + raw_ends[j1]]))
            dist_j = float(np.linalg.norm(j_xy[j0] - j_xy[j1]))
            if dist_j <= 0.65 * max(W0, w_b):
                par_j[find_j(j0)] = find_j(j1)

    skip_bridges = set()
    for ib, b in enumerate(br):
        j0, j1 = b["sj"], b["ej"]
        if j0 <= 0 or j1 <= 0 or j0 == j1:
            continue
        L_b = len(b["pts"])
        w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends.get(j0, []) + raw_ends.get(j1, [])])) if (j0 in raw_ends and j1 in raw_ends) else W0
        if L_b <= 1.35 * max(W0, w_b):
            out0 = [(i, e) for (i, e) in raw_ends.get(j0, []) if i != ib and len(br[i]["pts"]) > 1.5 * W0]
            out1 = [(i, e) for (i, e) in raw_ends.get(j1, []) if i != ib and len(br[i]["pts"]) > 1.5 * W0]
            has_cross_pair = False
            for a in out0:
                for c in out1:
                    if a[0] != c[0]:
                        ang = np.degrees(np.arccos(np.clip(-raw_info[a]["d"] @ raw_info[c]["d"], -1, 1)))
                        if ang < 25.0:
                            has_cross_pair = True
                            break
            if has_cross_pair or L_b <= 0.85 * max(W0, w_b) or find_j(j0) == find_j(j1):
                par_j[find_j(j0)] = find_j(j1)
                skip_bridges.add(ib)
    for ib, b in enumerate(br):
        if b["sj"] > 0 and b["ej"] > 0 and find_j(b["sj"]) == find_j(b["ej"]) and len(b["pts"]) <= 2.0 * W0:
            skip_bridges.add(ib)

    ends = {}
    for i, b in enumerate(br):
        if i in skip_bridges:
            continue
        if b["sj"] > 0:
            ends.setdefault(find_j(b["sj"]), []).append((i, 0))
        if b["ej"] > 0:
            ends.setdefault(find_j(b["ej"]), []).append((i, 1))

    info, link, ext = {}, {}, {}
    for j, l in ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        T = 1.0 * w
        for (i, e) in l:
            info[(i, e)] = end_info(br[i], e, T)

    used_j = set()
    stair_junc = {}
    for j, l in ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        pair_cands = []
        for x in range(len(l)):
            for y in range(x + 1, len(l)):
                a, b = l[x], l[y]
                if a[0] == b[0]:
                    continue
                ta, tb = info[a]["d"], info[b]["d"]
                ang = np.degrees(np.arccos(np.clip(-ta @ tb, -1, 1)))
                v = info[b]["A"] - info[a]["A"]
                nv = np.linalg.norm(v)
                if nv > 0.25 * w:
                    u = v / nv
                    ang_c = max(
                        np.degrees(np.arccos(np.clip(ta @ u, -1, 1))),
                        np.degrees(np.arccos(np.clip((-tb) @ u, -1, 1))),
                    )
                    eff_ang = max(ang, 0.85 * ang_c)
                else:
                    eff_ang = ang
                pair_cands.append((eff_ang, a, b))
        pair_cands.sort(key=lambda t: t[0])
        if len(l) == 2 and pair_cands:
            ang, a, b = pair_cands[0]
            A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
            if ang < 28:
                pts = hermite(A1, d1, A2, d2)
            else:
                C_pt = line_inter(A1, d1, A2, d2) if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-3 else None
                cen = np.mean([info[a]["full"][-1], info[b]["full"][-1]], axis=0)
                if C_pt is not None and np.linalg.norm(C_pt - cen) < 3 * w and (C_pt - A1) @ d1 > -2 and (C_pt - A2) @ d2 > -2:
                    n1 = max(2, int(np.linalg.norm(C_pt - A1)) + 1)
                    n2 = max(2, int(np.linalg.norm(A2 - C_pt)) + 1)
                    pts = np.vstack([np.linspace(A1, C_pt, n1), np.linspace(C_pt, A2, n2)[1:]])
                else:
                    pts = hermite(A1, d1, A2, d2)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
        elif len(l) >= 3:
            # Greedily link ALL mutually disjoint collinear pairs with eff_ang < 28
            used = set()
            linked_pairs = []
            for eff_ang, a, b in pair_cands:
                if eff_ang >= 28.0:
                    break
                if a in used or b in used:
                    continue
                used.add(a)
                used.add(b)
                linked_pairs.append((eff_ang, a, b))
            if linked_pairs:
                # Compute shared center C_pt if multiple lines cross or spokes meet
                M = np.zeros((2, 2))
                v_ls = np.zeros(2)
                for o in l:
                    d = info[o]["d"]
                    Pm = np.eye(2) - np.outer(d, d)
                    M += Pm
                    v_ls += Pm @ info[o]["A"]
                cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
                try:
                    C_pt = np.linalg.solve(M, v_ls)
                    if np.linalg.norm(C_pt - cen) > 2.5 * w:
                        C_pt = cen
                except Exception:
                    C_pt = cen
                thr_list = []
                for eff_ang, a, b in linked_pairs:
                    A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
                    if len(linked_pairs) >= 2 and eff_ang < 15.0:
                        n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
                        pts = np.linspace(A1, A2, n_pts)
                    else:
                        pts = hermite(A1, d1, A2, d2)
                    link[a] = (b, pts)
                    link[b] = (a, pts[::-1])
                    thr_list.append(np.vstack([info[a]["kept"][-int(2 * w):], pts, info[b]["kept"][-int(2 * w):][::-1]]))
                thr = np.vstack(thr_list)
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
                v_ls = np.zeros(2)
                for o in l:
                    d = info[o]["d"]
                    Pm = np.eye(2) - np.outer(d, d)
                    M += Pm
                    v_ls += Pm @ info[o]["A"]
                cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
                try:
                    C_pt = np.linalg.solve(M, v_ls)
                    if np.linalg.norm(C_pt - cen) > 2.5 * w:
                        C_pt = cen
                except Exception:
                    C_pt = cen
                for o in l:
                    ext[o] = C_pt

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

    seen = set(skip_bridges)
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
                P_pts, w = build(i, es)
                final.append(P_pts)
                widths.append(w)
                break
    for i in range(nb):
        if i not in seen:
            P_pts, w = build(i, 0)
            final.append(P_pts)
            widths.append(w)
    out = []
    for P_pts, w in zip(final, widths):
        if snap_width and abs(w - W0) < tol:
            w = W0
        out.append(dict(pts=resample(P_pts, 1.0), w=float(w)))
    return out, W0

C.build_chains = build_chains_v2
P.build_chains = build_chains_v2

from scratch.test_cross_and_star import make_cross, make_x_cross, make_star_6, make_star_8
for name, fn in [("cross_90", make_cross), ("cross_x", make_x_cross), ("star_6", make_star_6), ("star_8", make_star_8)]:
    g = fn()
    D = ink_map(g)
    br = refined_branches(D)
    ch, W0 = build_chains_v2(br)
    r = P.process_icon(g, P.Options(quality="fast", memory=False), name=name)
    m = r["model"]
    print(f"=== {name}: branches={len(br)}, chains={len(ch)}, final_paths={len(m.paths)}, IoU={r['metrics']['iou']*100:.2f}% ===")
    for i, p in enumerate(m.paths):
        print(f"  path {i}: nA={len(p.A)}, A={p.A.round(1).tolist()}")
