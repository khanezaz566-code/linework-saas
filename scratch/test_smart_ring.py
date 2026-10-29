import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from scipy.spatial import cKDTree
from linework import pipeline as P, rings as RG, edit as E, joints as JN
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.pipeline import ink_of
from linework.split import estimate_width
from linework.model import Model, Path
from linework.geom import resample, unit

def smart_apply_ring(model: Model, ring):
    rp = RG._ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]
    cx, cy = ring["cx"], ring["cy"]

    # Collect points from model paths that move tangentially along this ring to refine (cx, cy, r, w)
    on_ring_pts = []
    on_ring_ws = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            continue
        d = tree.query(f)[0]
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))
        w_m = max(w, p.w)
        sel = (d < 0.65 * w_m) & (rad_dot < 0.45)
        if sel.sum() >= 6:
            on_ring_pts.append(f[sel])
            on_ring_ws.append((p.w, float(sel.sum())))
    if on_ring_ws:
        w_new = float(sum(pw * lw for pw, lw in on_ring_ws) / sum(lw for _, lw in on_ring_ws))
        ring = dict(ring, w=w_new)
    if on_ring_pts:
        pts_all = np.vstack(on_ring_pts)
        if len(pts_all) >= 16 and abs(ring["a"] - ring["b"]) / max(ring["a"], ring["b"], 1e-6) < 0.02:
            cx_k, cy_k, r_k = RG._kasa(pts_all)
            if abs(r_k - ring["r"]) < 0.35 * w and np.hypot(cx_k - cx, cy_k - cy) < 0.35 * w:
                ring = dict(ring, cx=cx_k, cy=cy_k, a=r_k, b=r_k, r=r_k)
                cx, cy = cx_k, cy_k

    rp = RG._ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]

    paths = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            paths.append(p)
            continue
        d, idx = tree.query(f)
        w_m = max(w, p.w)
        if not (d < 0.75 * w_m).any():
            paths.append(p)
            continue
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))

        # A sample belongs to the ring if it is inside the centerline core OR close & moving tangentially along the ring
        bad = (d < 0.35 * w_m) | ((d < 0.75 * w_m) & (rad_dot < 0.48))
        if not bad.any():
            paths.append(p)
            continue
        if bad.mean() >= 0.82:
            continue
        # If bad only touches the very ends of an open spoke/blade (< 0.8*w at either end), keep p intact and snap its ends onto rp!
        n_f = len(f)
        lim = max(3, int(round(0.85 * w_m)))
        if not p.closed and not bad[min(lim, n_f):max(min(lim, n_f), n_f - lim)].any():
            q = p.copy()
            if bad[:min(lim, n_f)].any() or d[0] <= 0.65 * w_m:
                JN._set_end(q, 0, rp_flat[int(idx[0])])
            if bad[max(0, n_f - lim):].any() or d[-1] <= 0.65 * w_m:
                JN._set_end(q, 1, rp_flat[int(idx[-1])])
            paths.append(q)
            continue

        if p.closed:
            k = int(np.argmax(bad))
            f, d, bad = np.roll(f, -k, axis=0), np.roll(d, -k), np.roll(bad, -k)
        j = 0
        while j < len(f):
            if bad[j]:
                j += 1
                continue
            k = j
            while k < len(f) and not bad[k]:
                k += 1
            seg = f[j:k]
            if len(seg) >= 4 and float(d[j:k].max()) >= 0.80 * w_m:
                if j > 0:
                    v0 = seg[0] - seg[min(len(seg) - 1, 4)]
                    n0 = float(np.linalg.norm(v0))
                    pt0 = seg[0] + (v0 / n0) * float(d[j]) if n0 > 1e-6 else seg[0]
                    snap0 = rp_flat[int(tree.query(pt0)[1])]
                    seg = np.vstack([[snap0], seg])
                if k < len(f):
                    v1 = seg[-1] - seg[max(0, len(seg) - 5)]
                    n1 = float(np.linalg.norm(v1))
                    pt1 = seg[-1] + (v1 / n1) * float(d[k - 1]) if n1 > 1e-6 else seg[-1]
                    snap1 = rp_flat[int(tree.query(pt1)[1])]
                    seg = np.vstack([seg, [snap1]])
                q = E._refit(seg, p)
                if q:
                    if j > 0:
                        JN._set_end(q, 0, seg[0])
                    if k < len(f):
                        JN._set_end(q, 1, seg[-1])
                    paths.append(q)
            j = k
    paths.append(rp)
    return Model(paths, model.width, model.height)

if __name__ == "__main__":
    gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
    W, H, jobs = P.process_sheet(gray)
    for idx in [0, 2, 3, 5, 10]:
        k, crop, off = jobs[idx]
        D = ink_map(crop)
        w_est = estimate_width(D)
        doc = Doctor(D)
        br = refined_branches(D)
        chs, W0 = build_chains(br)
        m0 = initial_model(chs, D, sigma=1.2, err=0.3)
        cur = doc.soft(ink_of(m0))
        found = RG.detect_rings(D, w_est)
        print(f"=== ICON {idx} (cur={cur:.1f}, paths={len(m0.paths)}) ===")
        m_cur = m0
        s_cur = cur
        for ring in sorted(found, key=lambda r: -r["r"]):
            if ring["r"] < 0.8 * w_est:
                continue
            new = smart_apply_ring(m_cur, ring)
            if new is None:
                continue
            s2 = doc.soft(ink_of(new))
            print(f"  ring r={ring['r']:.2f}, sup={ring['support']:.3f} -> s2={s2:.1f} (diff={s2 - s_cur:+.1f}), paths={len(new.paths)}")
            if s2 <= s_cur + max(60.0, 0.04 * s_cur):
                m_cur, s_cur = new, s2
