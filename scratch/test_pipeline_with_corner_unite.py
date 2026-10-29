import sys, os, numpy as np, cv2, json
sys.path.insert(0, os.path.abspath('.'))

import linework.joints as J
import linework.finisher as FN
from linework.model import Model
from linework.doctor import ink_of

def corner_continuation_pairs(m: Model, J_joint: J.Joint, D):
    ends = J_joint.ends
    if len(ends) < 3:
        return []
    best_pair = None
    best_score = 999.0
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            k, ek = ends[y]
            if i >= len(m.paths) or k >= len(m.paths) or i == k:
                continue
            P, Q = m.paths[i], m.paths[k]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            w = max(wa, wb)
            gP = FN.end_geometry(P, ei)
            gQ = FN.end_geometry(Q, ek)
            cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei == 0 else -1], J._local_end_dir(P, ei))
            cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ek == 0 else -1], J._local_end_dir(Q, ek))
            cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
            if abs(cr) < 0.40:
                continue
            sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / cr
            Xc = cP + sP * tP
            if np.linalg.norm(Xc - J_joint.xy) > 1.35 * w:
                continue
            dot = float(tP @ tQ)
            if abs(dot) < 0.65:
                score = abs(dot)
                if score < best_score:
                    best_score = score
                    best_pair = (i, ei, k, ek)
    if best_pair is not None:
        return [best_pair]
    return []

orig_tool_unite = J.tool_unite
def patched_tool_unite(m: Model, J_joint: J.Joint, D):
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J_joint.ends and (p[2], p[3]) in J_joint.ends]
    if not pairs:
        pairs = J.smooth_continuation_pairs(m, J_joint, D)
    if pairs:
        return FN.join_pairs(m, pairs)
    if len(J_joint.ends) >= 3:
        cp = corner_continuation_pairs(m, J_joint, D)
        if cp:
            return FN.merge_corners(m, cp)
    return None
J.tool_unite = patched_tool_unite

# Now run pipeline on Icon 0 and Icon 1
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True

for icon_idx in [0, 1]:
    box = job['icons'][icon_idx]['box']
    crop = orig[box[1]:box[3], box[0]:box[2]]
    w0 = estimate_width(ink_map(crop))
    k = opts.norm_stroke / w0
    H, W = crop.shape
    small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

    res = _process_icon(small, opts, emit=lambda **k: None, name=f'ic{icon_idx}')
    m = res['model']
    print(f"\nIcon {icon_idx} result:")
    print(f"Paths count: {len(m.paths)}")
    for pi, p in enumerate(m.paths):
        print(f"  Path {pi}: len={p.length():.1f}, closed={p.closed}, nodes={len(p.A)}")
    
    img = (ink_of(m) * 255).astype(np.uint8)
    if icon_idx == 0:
        cuff_crop = img[90:140, 65:115]
    else:
        cuff_crop = img[110:160, 65:115]
    cuff_crop_4x = cv2.resize(cuff_crop, (200, 200), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'scratch/patched_cuff_{icon_idx}.png', cuff_crop_4x)
    print(f"Saved patched_cuff_{icon_idx}.png")
