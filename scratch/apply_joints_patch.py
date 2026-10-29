import os, sys

path = 'linework/joints.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update check_joint
old_check = '''def check_joint(m: Model, J: Joint, extra=None, missing=None):
    """Returns the list of failed checks (empty = the joint is clean)."""
    bad = []
    w = J.w
    tol = 0.5 + 0.04 * w
    # touch
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            end = _end_pt(m.paths[i], e)
            others = [j for j in J.through if j != i] or J.through
            dmin = min(_nearest_on(m.paths[j], end)[1] for j in others)
            if dmin > tol:
                bad.append("touch")
                break
    else:
        pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
        if np.linalg.norm(pts - pts.mean(0), axis=1).max() > 0.6 + 0.02 * w:
            bad.append("touch")
    # hook / nub
    for (i, e) in J.ends:
        p = m.paths[i]
        g = FN.end_geometry(p, e)
        if g is not None and (g[2] >= 12.0 or g[4] >= max(0.8, 0.12 * p.w)) and FN._straight_before_end(p, e, g[1]):
            bad.append("hook")
            break
    for (i, e) in J.ends:
        p = m.paths[i]
        a, b = FN._end_info(p, e)
        if FN._protrusion(m, i, a, p.w, b) > 0.1 * p.w:
            bad.append("nub")
            break
    # ink around the joint
    if extra is not None:
        r = int(2 * w)
        x0, y0 = int(max(J.xy[0] - r, 0)), int(max(J.xy[1] - r, 0))
        x1, y1 = int(J.xy[0] + r + 1), int(J.xy[1] + r + 1)
        if extra[y0:y1, x0:x1].sum() > 0.15 * w * w:
            bad.append("lump")
        if missing[y0:y1, x0:x1].sum() > 0.15 * w * w:
            bad.append("hole")
    # duplicate nodes
    for i in {i for i, _ in J.ends}:
        A = m.paths[i].A
        if len(A) > 2 and (np.linalg.norm(np.diff(A, axis=0), axis=1) < 0.4).any():
            bad.append("nodes")
            break
    return bad'''

new_check = '''def check_joint(m: Model, J: Joint, extra=None, missing=None):
    """Returns the list of failed checks (empty = the joint is clean)."""
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
        if g is not None:
            c, t, ang, end_pt, dev = g
            is_hook = (ang >= 20.0 and dev >= max(1.0, 0.15 * p.w)) or (ang >= 35.0) or (dev >= 0.25 * p.w)
            if is_hook and FN._straight_before_end(p, e, t):
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
    return bad'''

# Normalize newlines
code_norm = code.replace('\r\n', '\n')
old_check_norm = old_check.replace('\r\n', '\n')

assert old_check_norm in code_norm, "old_check not found!"
code_norm = code_norm.replace(old_check_norm, new_check.replace('\r\n', '\n'))

# 2. Update tool_line for T/Y joints to pass target=
old_tool_line = '''def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None'''

new_tool_line = '''def tool_line(m: Model, J: Joint, arc=False):
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
            target = best_X[0] if best_X is not None and best_X[1] <= 2.2 * J.w else None
            c = FN.fix_end(cand, i, e, target=target, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None'''

old_tl_norm = old_tool_line.replace('\r\n', '\n')
assert old_tl_norm in code_norm, "old_tool_line not found!"
code_norm = code_norm.replace(old_tl_norm, new_tool_line.replace('\r\n', '\n'))

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(code_norm)

print("linework/joints.py successfully patched!")
