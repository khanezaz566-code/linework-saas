import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2, numpy as np
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map
import linework.joints as JN

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][0]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Patch smooth_continuation_pairs with stricter dot requirement
orig_scp = JN.smooth_continuation_pairs
def patched_scp(m, J, D):
    # Require dot <= -0.85
    cands = []
    ends = J.ends
    from linework.rings import _kasa
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            j, ej = ends[y]
            if i >= len(m.paths) or j >= len(m.paths) or i == j:
                continue
            P, Q = m.paths[i], m.paths[j]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            a = JN._end_pt(P, ei)
            b = JN._end_pt(Q, ej)
            dist = float(np.linalg.norm(b - a))
            w = max(wa, wb)
            if dist > 2.5 * w:
                continue
            LP, LQ = P.length(), Q.length()
            f_all = np.vstack([P.flat(1.0), Q.flat(1.0)])
            on_circle = False
            if len(f_all) >= 12:
                cx, cy, r = _kasa(f_all)
                if 1.5 * w <= r <= 50.0 * w and (LP + LQ) >= 1.15 * r:
                    rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r)
                    if float(np.percentile(rad_err, 95)) <= 0.22 * w and float(rad_err.max()) <= 0.35 * w:
                        on_circle = True
            import linework.finisher as FN
            from linework.trace import unit
            ga = FN.end_geometry(P, ei)
            gb = FN.end_geometry(Q, ej)
            ta = ga[1] if ga is not None else unit(a - (P.A[1] if ei == 0 else P.A[-2]))
            tb = gb[1] if gb is not None else unit(b - (Q.A[1] if ej == 0 else Q.A[-2]))
            ta_loc = JN._local_end_dir(P, ei)
            tb_loc = JN._local_end_dir(Q, ej)
            dot = float(ta @ tb)
            dot_loc = float(ta_loc @ tb_loc)
            if not on_circle:
                if dot > -0.85 or dot_loc > -0.85:
                    continue
            else:
                if dot > -0.45 or dot_loc > -0.55:
                    continue
            n = max(3, int(dist))
            pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
            xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
            if float((D[ys, xs] > 0.5).mean()) >= 0.78:
                cands.append((0 if on_circle else 1, dist, i, ei, j, ej, min(dot, dot_loc)))
    if not cands:
        return []
    cands.sort(key=lambda t: (t[0], t[1], t[6]))
    best = cands[0]
    return [(best[2], best[3], best[4], best[5])]

JN.smooth_continuation_pairs = patched_scp

res = _process_icon(small, opts, emit=lambda **k: None, name='ic0')
m_out = res['model']
print('Fixed Icon 0:')
for i, p in enumerate(m_out.paths):
    print(f"p[{i}]: len={p.length():.1f}, closed={p.closed}, A[0]={np.round(p.A[0], 1)}, A[-1]={np.round(p.A[-1], 1)}")
