import sys, os, json
sys.path.insert(0, os.getcwd())
import numpy as np
from scipy.spatial import cKDTree
from linework import joints as JN
from linework.model import Model

def find_joints_v2(m: Model):
    ends = [(i, e, (p.A[0] if e == 0 else p.A[-1]), p.w) for i, p in enumerate(m.paths) if not p.closed and len(p.A) >= 2 for e in (0, 1)]
    if not ends:
        return []
    pts, own = [], []
    for j, p in enumerate(m.paths):
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    P = np.vstack(pts)
    own = np.array(own)
    tree = cKDTree(P)
    n = len(ends)
    E = np.array([x[2] for x in ends])
    wmax = max(x[3] for x in ends)

    def _out_tangent(i, e):
        p = m.paths[i]
        if len(p.A) < 2:
            return np.array([1.0, 0.0])
        v = (p.A[0] - p.Hout[0]) if e == 0 else (p.A[-1] - p.Hin[-1])
        if np.linalg.norm(v) < 1e-5:
            v = (p.A[0] - p.A[1]) if e == 0 else (p.A[-1] - p.A[-2])
        nv = np.linalg.norm(v)
        return v / nv if nv > 1e-5 else np.array([1.0, 0.0])

    tangs = [_out_tangent(x[0], x[1]) for x in ends]

    def is_interior(j_path, pt, w_ref):
        qp = m.paths[j_path]
        if qp.closed:
            return True
        return min(float(np.linalg.norm(pt - qp.A[0])), float(np.linalg.norm(pt - qp.A[-1]))) > 0.65 * min(w_ref, qp.w)

    # Check if each end already sits on the INTERIOR of a through-path (within 0.30*w)
    on_thr = [False] * n
    for k, (pi, pe, pt, pw) in enumerate(ends):
        idxs = tree.query_ball_point(pt, 0.30 * pw)
        if any(own[q] != pi and is_interior(int(own[q]), pt, pw) for q in idxs):
            on_thr[k] = True

    par = list(range(n))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a, b in cKDTree(E).query_pairs(0.85 * wmax):
        if ends[a][0] == ends[b][0]:
            continue
        if tangs[a] @ tangs[b] > 0.65:
            continue
        d_ab = float(np.linalg.norm(E[a] - E[b]))
        w_min = min(ends[a][3], ends[b][3])
        w_max = max(ends[a][3], ends[b][3])
        if w_max > 1.8 * w_min:
            continue
        # If both ends are already anchored on through-strokes at different spots (>0.30*w apart), they are separate T-joints
        limit = 0.30 * w_min if (on_thr[a] and on_thr[b]) else 0.75 * w_min
        if d_ab <= limit:
            par[f(a)] = f(b)

    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        pts_g = np.array([ends[k][2] for k in g])
        mids = pts_g.mean(axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        if len(g) >= 2:
            for q_idx in tree.query_ball_point(mids, 0.45 * w):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and is_interior(j_path, mids, w) and JN._nearest_on(m.paths[j_path], mids)[1] <= 0.35 * min(w, m.paths[j_path].w):
                    thr.add(j_path)
        else:
            k = g[0]
            pt, pw = ends[k][2], ends[k][3]
            for q_idx in tree.query_ball_point(pt, 0.45 * pw):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, pt, pw):
                    if JN._nearest_on(m.paths[j_path], pt)[1] <= 0.35 * min(pw, m.paths[j_path].w):
                        thr.add(j_path)
            if not thr:
                # Raycast along outward tangent up to 0.85*w for undershot T-stems
                s_steps = np.arange(0.1 * pw, 0.85 * pw, 0.25)
                ray = pt[None, :] + s_steps[:, None] * tangs[k][None, :]
                d_ray, idx_ray = tree.query(ray)
                for dr, ir in zip(d_ray, idx_ray):
                    j_path = int(own[ir])
                    if dr <= 0.25 * min(pw, m.paths[j_path].w) and j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, P[ir], pw):
                        thr.add(j_path)
                        break
        if len(g) >= 3 and not thr:
            out.append(JN.Joint("Y", mids, members, sorted(mem_paths), w))
        elif len(g) >= 2 and not thr:
            out.append(JN.Joint("L", mids, members, [], w))
        elif thr:
            out.append(JN.Joint("T" if len(g) == 1 else "Y", mids, members, sorted(thr), w))
    return out

if __name__ == "__main__":
    for idx in range(9):
        ipath = f"data/ea3cb3bb04a7/icon_local_{idx}.json"
        m = Model.from_json(open(ipath).read())
        js_old = JN.find_joints(m)
        js_new = find_joints_v2(m)
        bad_new = []
        for J in js_new:
            if J.kind in ("T", "Y"):
                for (i, e) in J.ends:
                    end = JN._end_pt(m.paths[i], e)
                    others = [j for j in J.through if j != i] or J.through
                    if others:
                        dmin = min(JN._nearest_on(m.paths[j], end)[1] for j in others)
                        if dmin > 0.25:
                            bad_new.append((J.kind, round(dmin, 2), (i, e)))
            elif J.kind == "L":
                pts = np.array([JN._end_pt(m.paths[i], e) for i, e in J.ends])
                dmax = float(np.linalg.norm(pts - pts.mean(0), axis=1).max())
                if dmax > 0.25:
                    bad_new.append(("L", round(dmax, 2), J.ends))
        print(f"icon_local_{idx}: old_joints={len(js_old)}, new_joints={len(js_new)}, bad_new(>0.25px)={bad_new}")
