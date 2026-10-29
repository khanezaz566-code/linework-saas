import os

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\finisher.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_fix = '''def fix_end(m: Model, i, e, reach=4.5):
    """Replace the last 1.4 w of path i\'s end e by a straight run along the stroke\'s own direction, ending ON the centerline of the stroke it
    joins (or, for a free end, at the same distance as before). Returns the new model or None."""
    p = m.paths[i]
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(p)
        cand = fix_end(m_rev, i, 1, reach=reach)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
    g = end_geometry(p, e)
    if g is None:
        return None
    c, t, ang, end, dev = g
    tree, P, own = _others_tree(m, i)
    X = None
    if tree is not None:
        s = np.arange(0.2 * p.w, reach * p.w, 0.4)
        ray = c + s[:, None] * t
        d, k = tree.query(ray)
        j = int(np.argmin(d))
        if d[j] < 0.6 * p.w:
            X = P[k[j]].copy()
    if X is None:
        if ang < 12.0 and dev < max(0.8, 0.12 * p.w):
            return None
        X = c + t * max(1.0 * p.w, float(np.linalg.norm(end - c)))
    cand = move_end(m, i, e, 1.4 * p.w)
    if cand is None:
        return None
    q = cand.paths[i]
    cut = q.A[-1]
    v = X - cut
    L = np.linalg.norm(v)
    if L < 0.3 or np.degrees(np.arccos(np.clip((v / L) @ t, -1, 1))) > 30.0:
        return None
    u = v / L
    hin = np.linalg.norm(q.Hin[-1] - cut)
    q.Hin[-1] = cut - u * hin  # keep the stroke smooth (G1) where the straight run starts
    q.Hout[-1] = cut + v / 3
    q.A = np.vstack([q.A, X])
    q.Hin = np.vstack([q.Hin, X - v / 3])
    q.Hout = np.vstack([q.Hout, X])
    return cand'''

new_fix = '''def fix_end(m: Model, i, e, reach=4.5, target=None, smooth=False):
    """Replace the last 1.4 w of path i\'s end e by a straight run along the stroke\'s own direction, ending ON the centerline of the stroke it
    joins (or, for a free end, at the same distance as before). Returns the new model or None."""
    p = m.paths[i]
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(p)
        cand = fix_end(m_rev, i, 1, reach=reach, target=target, smooth=smooth)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
    g = end_geometry(p, e)
    if g is None:
        return None
    c, t, ang, end, dev = g
    tree, P, own = _others_tree(m, i)
    X = None if target is None else np.asarray(target, float)
    if X is None and tree is not None:
        s = np.arange(0.2 * p.w, reach * p.w, 0.4)
        ray = c + s[:, None] * t
        d, k = tree.query(ray)
        j = int(np.argmin(d))
        if d[j] < 0.6 * p.w:
            X = P[k[j]].copy()
    if X is None:
        if ang < 12.0 and dev < max(0.8, 0.12 * p.w):
            return None
        X = c + t * max(1.0 * p.w, float(np.linalg.norm(end - c)))
    cand = move_end(m, i, e, 1.4 * p.w)
    if cand is None:
        return None
    q = cand.paths[i]
    cut = q.A[-1]
    v = X - cut
    L = np.linalg.norm(v)
    if L < 0.3 or np.degrees(np.arccos(np.clip((v / L) @ t, -1, 1))) > 30.0:
        return None
    u = v / L
    hin = np.linalg.norm(q.Hin[-1] - cut)
    if smooth:  # arc-like run: leave along the stroke\'s own tangent and arrive along it
        q.Hin[-1] = cut - t * hin
        q.Hout[-1] = cut + t * (L / 3)
        q.A = np.vstack([q.A, X])
        q.Hin = np.vstack([q.Hin, X - t * (L / 3)])
        q.Hout = np.vstack([q.Hout, X])
        return cand
    q.Hin[-1] = cut - u * hin  # keep the stroke smooth (G1) where the straight run starts
    q.Hout[-1] = cut + v / 3
    q.A = np.vstack([q.A, X])
    q.Hin = np.vstack([q.Hin, X - v / 3])
    q.Hout = np.vstack([q.Hout, X])
    return cand'''

code_norm = code.replace('\r\n', '\n')
old_norm = old_fix.replace('\r\n', '\n')
new_norm = new_fix.replace('\r\n', '\n')
assert old_norm in code_norm, 'old_norm not in code_norm'
code_norm = code_norm.replace(old_norm, new_norm, 1)
with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\finisher.py', 'w', encoding='utf-8') as f:
    f.write(code_norm)
print('Updated finisher.fix_end successfully')
