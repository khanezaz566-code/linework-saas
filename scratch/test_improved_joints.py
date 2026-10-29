import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
import numpy as np
from tools.junction_bench import ICONS
from linework.pipeline import Options, process_icon
from linework.joints import find_joints, _ink_maps, _end_pt, _nearest_on
from linework.render import render_gray
from linework.trace import ink_map
import linework.joints as JT
import linework.finisher as FN

def improved_check_joint(m, J, extra=None, missing=None):
    bad = []
    w = J.w
    tol = max(0.8, 0.06 * w)
    # touch
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            end = _end_pt(m.paths[i], e)
            others = [j for j in J.through if j != i] or J.through
            if others:
                dmin = min(_nearest_on(m.paths[j], end)[1] for j in others)
                if dmin > tol:
                    bad.append("touch")
                    break
    else:
        pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
        if np.linalg.norm(pts - pts.mean(0), axis=1).max() > 0.8 + 0.04 * w:
            bad.append("touch")
    # hook / nub
    for (i, e) in J.ends:
        p = m.paths[i]
        g = FN.end_geometry(p, e)
        if g is not None and (g[2] >= 18.0 or g[4] >= max(1.0, 0.15 * p.w)) and FN._straight_before_end(p, e, g[1]):
            bad.append("hook")
            break
    for (i, e) in J.ends:
        p = m.paths[i]
        a, b = FN._end_info(p, e)
        if FN._protrusion(m, i, a, p.w, b) > 0.18 * p.w:
            bad.append("nub")
            break
    # ink around the joint
    if extra is not None:
        r = int(1.2 * w)
        x0, y0 = int(max(J.xy[0] - r, 0)), int(max(J.xy[1] - r, 0))
        x1, y1 = int(min(J.xy[0] + r + 1, extra.shape[1])), int(min(J.xy[1] + r + 1, extra.shape[0]))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        circ = (xx - J.xy[0])**2 + (yy - J.xy[1])**2 <= (1.1 * w)**2
        if extra[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("lump")
        if missing[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("hole")
    # duplicate nodes
    for i in {i for i, _ in J.ends}:
        A = m.paths[i].A
        if len(A) > 2 and (np.linalg.norm(np.diff(A, axis=0), axis=1) < 0.4).any():
            bad.append("nodes")
            break
    return bad

# Monkey-patch check_joint to evaluate
orig_check = JT.check_joint
JT.check_joint = improved_check_joint

# Also improve tool_line
orig_tool_line = JT.tool_line
def improved_tool_line(m, J, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            end = _end_pt(cand.paths[i], e)
            best_X = None
            for j in J.through:
                if j < len(cand.paths) and j != i:
                    pt_on_q, d = _nearest_on(cand.paths[j], end)
                    if best_X is None or d < best_X[1]:
                        best_X = (pt_on_q, d)
            target = best_X[0] if best_X is not None and best_X[1] <= 2.0 * J.w else None
            c = FN.fix_end(cand, i, e, target=target, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None
    return orig_tool_line(m, J, arc=arc)

JT.tool_line = improved_tool_line

print("Running evaluation on 7 benchmark icons...", flush=True)
for name, fn in ICONS.items():
    g = fn()
    r = process_icon(g, Options(), name=name)
    jn = r['metrics'].get('joins', {})
    total = jn.get('total', 0)
    clean = jn.get('clean_first', 0)
    repaired = sum((jn.get('fixed') or {}).values())
    unresolved = len(jn.get('unresolved', []))
    unres_reasons = [u.get('reasons') for u in jn.get('unresolved', [])]
    print(f"{name:6s}: iou={r['metrics']['iou']*100:.2f}% | total={total:2d} clean={clean:2d} repaired={repaired:2d} unresolved={unresolved:2d} | reasons={unres_reasons}", flush=True)
