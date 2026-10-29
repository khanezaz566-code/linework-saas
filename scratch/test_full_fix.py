import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework import trace as T
from linework import finisher as FN
from linework import joints as JN
from linework import doctor as DOC

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Patch 1: Doctor redundancy - do not cut tails that meet at an angle
orig_red = DOC.Doctor.redundancy

def patched_redundancy(self, model):
    red, tails = orig_red(self, model)
    if not tails:
        return red, tails
    flats = [p.flat(0.5) for p in model.paths]
    filtered_tails = []
    for (i, k, j) in tails:
        p = model.paths[i]
        f = flats[i]
        tail_pts = f[k:j+1]
        if len(tail_pts) < 2:
            continue
        v_tail = tail_pts[-1] - tail_pts[0] if (j >= len(f) - 3) else (tail_pts[0] - tail_pts[-1])
        lv = np.linalg.norm(v_tail)
        if lv < 1e-4:
            continue
        t_tail = v_tail / lv
        other_idx = -1
        min_d = 1e9
        pt_mid = tail_pts[len(tail_pts) // 2]
        for m_idx, fm in enumerate(flats):
            if m_idx == i or m_idx in red or len(fm) < 2:
                continue
            d = np.linalg.norm(fm - pt_mid, axis=1).min()
            if d < min_d:
                min_d = d
                other_idx = m_idx
        if other_idx >= 0 and min_d < 0.6 * p.w:
            fm = flats[other_idx]
            k_other = int(np.argmin(np.linalg.norm(fm - pt_mid, axis=1)))
            lo = max(0, k_other - 4)
            hi = min(len(fm) - 1, k_other + 4)
            v_other = fm[hi] - fm[lo]
            if np.linalg.norm(v_other) > 1e-4:
                t_other = v_other / np.linalg.norm(v_other)
                cos_ang = abs(float(t_tail @ t_other))
                if cos_ang < 0.88:  # Angle > 28 degrees -> real corner/junction, not duplicate run!
                    continue
        filtered_tails.append((i, k, j))
    return red, filtered_tails

DOC.Doctor.redundancy = patched_redundancy

# Patch 2: Finisher corner_pairs adaptive tol
orig_cp = FN.corner_pairs
def patched_cp(m, tol=1.2):
    w_med = float(np.median([p.w for p in m.paths])) if m.paths else 10.0
    eff_tol = max(tol, 0.40 * w_med)
    return orig_cp(m, tol=eff_tol)
FN.corner_pairs = patched_cp

# Patch 3: Joints find_joints allow acute corners
orig_fj = JN.find_joints
def patched_fj(m):
    # Call original find_joints with acute corner support
    ends = [(i, e, (p.A[0] if e == 0 else p.A[-1]), p.w) for i, p in enumerate(m.paths) if not p.closed and len(p.A) >= 2 for e in (0, 1)]
    if not ends:
        return []
    pts, own = [], []
    for j, p in enumerate(m.paths):
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    from scipy.spatial import cKDTree
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
        cos_t = tangs[a] @ tangs[b]
        den = abs(tangs[a][0] * tangs[b][1] - tangs[a][1] * tangs[b][0])
        # If parallel pointing same direction without corner intersection, skip
        if cos_t > 0.65 and den < 0.15:
            continue
        d_ab = float(np.linalg.norm(E[a] - E[b]))
        w_min = min(ends[a][3], ends[b][3])
        w_max = max(ends[a][3], ends[b][3])
        if w_max > 1.8 * w_min:
            continue
        limit = 0.30 * w_min if (on_thr[a] and on_thr[b]) else 0.85 * w_min
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
                s_steps = np.arange(-0.55 * pw, 0.85 * pw, 0.25)
                ray = pt[None, :] + s_steps[:, None] * tangs[k][None, :]
                d_ray, idx_ray = tree.query(ray)
                order = np.argsort(np.abs(s_steps))
                for m_idx in order:
                    dr, ir = float(d_ray[m_idx]), int(idx_ray[m_idx])
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

JN.find_joints = patched_fj

res = _process_icon(small, opts, name="icon_5_small")
m = res["model"]
print(f"\nFinal paths count: {len(m.paths)}")
for i, p in enumerate(m.paths):
    print(f"P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)} closed={p.closed}")
