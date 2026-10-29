import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework.trace import ink_map, refined_branches
from linework.geom import resample, unit, hermite, line_inter
from linework import chains as C, pipeline as P

def build_chains_clean(branches, snap_width=True):
    br = [dict(b) for b in branches]
    for b in br:
        b["pts"] = resample(np.asarray(b["pts"], float), 1.0)
    if not br:
        return [], 0.0
    W0 = C.global_width(br)
    tol = max(1.3, 0.08 * W0)

    def oriented(b, e):
        return b["pts"] if e == 1 else b["pts"][::-1]

    def end_info(b, e, T, has_free_tip=False):
        q = oriented(b, e)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
        n = len(q)
        if has_free_tip and L[-1] > 1.8 * T and n >= 12:
            k_near = n - 1 - int(np.searchsorted(L, 0.25 * T))
            k_mid  = n - 1 - int(np.searchsorted(L, 0.65 * T))
            k_far  = n - 1 - int(np.searchsorted(L, min(2.2 * T, 0.9 * L[-1])))
            k_near = min(n - 2, max(k_near, k_mid + 2))
            if k_near > k_mid > k_far >= 0:
                d_near = unit(q[k_near] - q[k_mid])
                d_far  = unit(q[k_mid] - q[k_far])
                d_tip  = unit(q[-1] - q[k_near])
                k_vfar = n - 1 - int(np.searchsorted(L, min(2.8 * T, 0.95 * L[-1])))
                straight_before = (k_far > k_vfar + 1) and (d_far @ unit(q[k_far] - q[k_vfar]) > np.cos(np.radians(8)))
                if (d_near @ d_far < np.cos(np.radians(32)) and d_tip @ d_near >= np.cos(np.radians(22))) or (
                    straight_before and d_near @ d_far < np.cos(np.radians(18))
                ):
                    k = max(n - 1 - int(np.searchsorted(L, 0.35 * T)), 2)
                    return dict(A=q[k].copy(), d=d_near, kept=q[: k + 1], full=q)
        T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
        k = n - 1 - int(np.searchsorted(L, T_eff))
        k = max(k, 2)
        lo = max(k - 14, 0)
        d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
        k_neck = min(n - 2, max(k + 3, n - 1 - int(np.searchsorted(L, 0.35 * T_eff))))
        if L[-1] >= 2.2 * T and k_neck > k and lo >= 8:
            d_prev = unit(q[lo] - q[max(lo - 12, 0)])
            d_neck = unit(q[k_neck] - q[k])
            d_tip0 = unit(q[-1] - q[k_neck])
            if d_prev @ d < np.cos(np.radians(15)) and d_neck @ d < np.cos(np.radians(20)) and d_tip0 @ d_neck >= np.cos(np.radians(22)):
                return dict(A=q[k_neck].copy(), d=d_neck, kept=q[: k_neck + 1], full=q)
        return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

    def is_free_tip(idx):
        b = br[idx]
        return (b["sj"] == 0 or b["ej"] == 0) and len(b["pts"]) < 3.2 * W0

    def is_short_bridge(idx):
        b = br[idx]
        return b["sj"] > 0 and b["ej"] > 0 and len(b["pts"]) < 2.0 * W0

    # Cluster multi-way star/crossing junctions that split into micro-junctions with collinear outer spokes
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

    par_j = {}
    def find_j(j):
        while par_j.get(j, j) != j:
            par_j[j] = par_j.get(par_j[j], par_j[j])
            j = par_j[j]
        return j

    def has_collinear_cross(j0, j1, skip_ib=-1):
        out0 = [(i, e) for (i, e) in raw_ends.get(j0, []) if i != skip_ib and len(br[i]["pts"]) > 1.5 * W0]
        out1 = [(i, e) for (i, e) in raw_ends.get(j1, []) if i != skip_ib and len(br[i]["pts"]) > 1.5 * W0]
        for a in out0:
            for c in out1:
                if a[0] != c[0]:
                    ta, tc = raw_info[a]["d"], raw_info[c]["d"]
                    ang = np.degrees(np.arccos(np.clip(-ta @ tc, -1, 1)))
                    if ang < 22.0:
                        v = raw_info[c]["A"] - raw_info[a]["A"]
                        nv = np.linalg.norm(v)
                        if nv > 1e-3:
                            u = v / nv
                            ang_c = max(np.degrees(np.arccos(np.clip(ta @ u, -1, 1))), np.degrees(np.arccos(np.clip((-tc) @ u, -1, 1))))
                            if ang_c < 22.0:
                                return True
        return False

    skip_bridges = set()
    j_keys = sorted(raw_ends.keys())
    for a_idx in range(len(j_keys)):
        for b_idx in range(a_idx + 1, len(j_keys)):
            j0, j1 = j_keys[a_idx], j_keys[b_idx]
            w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends[j0] + raw_ends[j1]]))
            if float(np.linalg.norm(j_xy[j0] - j_xy[j1])) <= 0.65 * max(W0, w_b) and has_collinear_cross(j0, j1):
                par_j[find_j(j0)] = find_j(j1)

    for ib, b in enumerate(br):
        j0, j1 = b["sj"], b["ej"]
        if j0 <= 0 or j1 <= 0 or j0 == j1:
            continue
        L_b = len(b["pts"])
        w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends.get(j0, []) + raw_ends.get(j1, [])])) if (j0 in raw_ends and j1 in raw_ends) else W0
        if L_b <= 1.25 * max(W0, w_b) and (has_collinear_cross(j0, j1, ib) or find_j(j0) == find_j(j1)):
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
        has_ft = any(br[i]["sj"] == 0 or br[i]["ej"] == 0 for i, _ in l)
        for (i, e) in l:
            info[(i, e)] = end_info(br[i], e, T, has_free_tip=has_ft)

    stair_junc = {}
    bridge_cands = []
    for ib, b in enumerate(br):
        if ib in skip_bridges or not is_short_bridge(ib):
            continue
        j0, j1 = find_j(b["sj"]), find_j(b["ej"])
        if j0 == j1 or len(ends.get(j0, [])) != 3 or len(ends.get(j1, [])) != 3:
            continue
        tips0 = [(i, e) for (i, e) in ends[j0] if i != ib and is_free_tip(i)]
        tips1 = [(i, e) for (i, e) in ends[j1] if i != ib and is_free_tip(i)]
        for a in tips0:
            for c in tips1:
                ta, tc = info[a]["d"], info[c]["d"]
                ang_tips = np.degrees(np.arccos(np.clip(-ta @ tc, -1, 1)))
                if ang_tips > 25:
                    continue
                tb0, tb1 = info[(ib, 0)]["d"], info[(ib, 1)]["d"]
                a0 = np.degrees(np.arccos(np.clip(-ta @ tb0, -1, 1)))
                a1 = np.degrees(np.arccos(np.clip(-tc @ tb1, -1, 1)))
                if max(a0, a1) < 55:
                    bridge_cands.append((a0 + a1 + ang_tips, j0, a, (ib, 0), j1, c, (ib, 1)))
    used_j = set()
    for score, j0, a, b0, j1, c, b1 in sorted(bridge_cands):
        if j0 in used_j or j1 in used_j:
            continue
        used_j.add(j0)
        used_j.add(j1)
        skip_bridges.add(b0[0])
        T1, T2 = info[a]["kept"][0].copy(), info[c]["kept"][0].copy()
        if np.linalg.norm(T2 - T1) < 3.8 * W0 and np.linalg.norm(T2 - T1) > 1e-3:
            u_bar = unit(T2 - T1)
            for tip in (a, c):
                br[tip[0]]["pts"] = T1 + ((br[tip[0]]["pts"] - T1) @ u_bar)[:, None] * u_bar[None, :]
                info[tip]["kept"] = T1 + ((info[tip]["kept"] - T1) @ u_bar)[:, None] * u_bar[None, :]
                info[tip]["A"] = info[tip]["kept"][-1].copy()
        A1, A2 = info[a]["A"], info[c]["A"]
        n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
        pts = np.linspace(A1, A2, n_pts)
        link[a] = (c, pts)
        link[c] = (a, pts[::-1])
        for jx, used_tip in ((j0, a), (j1, c)):
            w_j = float(np.mean([br[i]["w"] for i, _ in ends[jx]]))
            thr = np.vstack([info[a]["kept"], pts, info[c]["kept"][::-1]])
            for o in ends[jx]:
                if o == used_tip or o[0] == b0[0]:
                    continue
                Ao, do = info[o]["A"], info[o]["d"]
                ts = np.arange(0, 4 * w_j, 0.5)
                ray = Ao[None] + do[None] * ts[:, None]
                dist = np.array([np.min(np.linalg.norm(thr - r, axis=1)) for r in ray])
                ext[o] = Ao + do * ts[int(np.argmin(dist))]
    for j0, l in ends.items():
        if j0 in used_j or len(l) != 3:
            continue
        tips0 = [(i, e) for (i, e) in l if is_free_tip(i)]
        if len(tips0) != 1:
            continue
        a = tips0[0]
        others = [(i, e) for (i, e) in l if (i, e) != a]
        free_br = []
        claimed_br = 0
        for i, e in others:
            other_j = find_j(br[i]["ej"] if e == 0 else br[i]["sj"])
            if other_j in used_j:
                claimed_br += 1
            elif is_short_bridge(i):
                ang = np.degrees(np.arccos(np.clip(-info[a]["d"] @ info[(i, e)]["d"], -1, 1)))
                if ang < 55:
                    free_br.append((ang, (i, e)))
        if claimed_br >= 1 and len(free_br) == 1:
            used_j.add(j0)
            stair_junc[j0] = (a, free_br[0][1])
    for ib, b in enumerate(br):
        if is_short_bridge(ib) and find_j(b["sj"]) in used_j and find_j(b["ej"]) in used_j:
            skip_bridges.add(ib)
            for e in (0, 1):
                ext.pop((ib, e), None)
    for j0, l in ends.items():
        if j0 in used_j or len(l) != 3:
            continue
        spurs = [(i, e) for (i, e) in l if (br[i]["sj"] == 0 or br[i]["ej"] == 0) and len(br[i]["pts"]) <= 2.4 * W0]
        if len(spurs) != 1:
            continue
        spur = spurs[0]
        others = [(i, e) for (i, e) in l if (i, e) != spur]
        if len(others) != 2 or others[0][0] == others[1][0]:
            continue
        L_spur_pts = len(br[spur[0]]["pts"])
        if min(len(br[others[0][0]]["pts"]), len(br[others[1][0]]["pts"])) <= 1.3 * L_spur_pts:
            continue
        a, b = others[0], others[1]
        J_pt = info[spur]["full"][-1]
        T_tip = info[spur]["kept"][0]
        u_spur = unit(T_tip - J_pt) if np.linalg.norm(T_tip - J_pt) > 1e-3 else -info[spur]["d"]
        d1, d2 = info[a]["d"], info[b]["d"]
        cr1 = d1[0] * u_spur[1] - d1[1] * u_spur[0]
        cr2 = d2[0] * u_spur[1] - d2[1] * u_spur[0]
        if (
            d1 @ u_spur > np.cos(np.radians(58))
            and d2 @ u_spur > np.cos(np.radians(58))
            and cr1 * cr2 < 0
            and unit(d1 + d2) @ u_spur > np.cos(np.radians(26))
        ):
            used_j.add(j0)
            skip_bridges.add(spur[0])
            A1, A2 = info[a]["A"], info[b]["A"]
            C_pt = line_inter(A1, d1, A2, d2) if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-3 else None
            L_spur = float(np.linalg.norm(T_tip - J_pt))
            w_j = float(np.mean([br[i]["w"] for i, _ in l]))
            if C_pt is not None and (C_pt - A1) @ d1 > 0 and (C_pt - A2) @ d2 > 0:
                proj = float((C_pt - J_pt) @ u_spur)
                max_proj = L_spur + 0.25 * w_j
                V = (J_pt + max_proj * u_spur) if proj > max_proj else (T_tip.copy() if proj < 0.2 * L_spur else C_pt)
            else:
                V = T_tip.copy()
            ext[a] = V
            ext[b] = V

    for j, l in ends.items():
        if j in used_j and j not in stair_junc:
            continue
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        if j in stair_junc:
            a, b = stair_junc[j]
            pair_cands = [(0.0, a, b)]
            allow_staircase = True
        else:
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
                    short_stem = min(len(br[a[0]]["pts"]), len(br[b[0]]["pts"])) < 1.2 * w
                    if nv > 0.25 * w and not short_stem:
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
            allow_staircase = False
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
        elif len(l) >= 3 and pair_cands and (pair_cands[0][0] < 28 or allow_staircase):
            used = set()
            linked_pairs = []
            for eff_ang, a, b in pair_cands:
                if eff_ang >= 28.0 and not (allow_staircase and not linked_pairs):
                    break
                if a in used or b in used:
                    continue
                used.add(a)
                used.add(b)
                linked_pairs.append((eff_ang, a, b))
                if allow_staircase:
                    break
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
            try:
                C_pt = np.linalg.solve(M, v_ls)
            except Exception:
                C_pt = np.mean([info[o]["full"][-1] for o in l], axis=0)
            cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
            if np.linalg.norm(C_pt - cen) > 2.5 * w:
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

if __name__ == "__main__":
    C.build_chains = build_chains_clean
    P.build_chains = build_chains_clean
    gray = cv2.imread("data/ea3cb3bb04a7/original.png", cv2.IMREAD_GRAYSCALE)
    W, H, jobs = P.process_sheet(gray)
    _, crop, off = jobs[4]
    D = ink_map(crop)
    br = refined_branches(D)
    ch, W0 = build_chains_clean(br)
    print(f"=== Hourglass chains={len(ch)} ===")
    for i, c in enumerate(ch):
        print(f"  ch {i:2d}: len={len(c['pts']):3d}, w={c['w']:4.1f}, p0={c['pts'][0].round(1).tolist()} -> p1={c['pts'][-1].round(1).tolist()}")
