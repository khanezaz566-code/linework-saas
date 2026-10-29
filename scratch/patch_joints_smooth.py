with open('linework/joints.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is None:
                return None
            cand = c
        return cand
    # L: intersection of the two reference rays
    geo = [(i, e, FN.end_geometry(cand.paths[i], e)) for i, e in J.ends]
    if len(geo) != 2 or any(g is None for _, _, g in geo):
        return None
    (i1, e1, g1), (i2, e2, g2) = geo
    c1, t1, c2, t2 = g1[0], g1[1], g2[0], g2[1]
    den = _cr2(t1, t2)
    if abs(den) < 0.15:  # nearly parallel
        return None
    s1 = _cr2(c2 - c1, t2) / den
    X = c1 + s1 * t1
    if np.linalg.norm(X - J.xy) > 2.0 * J.w:
        return None
    for (i, e, _) in geo:
        c = FN.fix_end(cand, i, e, target=X, smooth=arc)
        if c is None:
            return None
        cand = c
    return cand


def _cr2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def tool_unite(m: Model, J: Joint, D):
    """Shape Builder, unite: two strokes that are really one stroke cut by the joint (a ring in two arcs, a line cut by a crossing) become one
    stroke; what is left of the joint (a spoke on that ring) is then an ordinary T."""
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J.ends and (p[2], p[3]) in J.ends]
    if not pairs:
        return None
    return FN.join_pairs(m, pairs)'''

replacement = '''def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None
    # L: intersection of the two reference rays
    geo = [(i, e, FN.end_geometry(cand.paths[i], e)) for i, e in J.ends]
    if len(geo) != 2 or any(g is None for _, _, g in geo):
        return None
    (i1, e1, g1), (i2, e2, g2) = geo
    c1, t1, c2, t2 = g1[0], g1[1], g2[0], g2[1]
    den = _cr2(t1, t2)
    if abs(den) < 0.15:  # nearly parallel
        return None
    s1 = _cr2(c2 - c1, t2) / den
    X = c1 + s1 * t1
    if np.linalg.norm(X - J.xy) > 2.0 * J.w:
        return None
    changed = False
    for (i, e, _) in geo:
        c = FN.fix_end(cand, i, e, target=X, smooth=arc)
        if c is not None:
            cand = c
            changed = True
    return cand if changed else None


def _cr2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def smooth_continuation_pairs(m: Model, J: Joint, D):
    """Find pairs of ends meeting at joint J that form a smooth continuation (collinear, curved bar, or circular arc)
    and should be united by Shape Builder into one continuous through-stroke."""
    cands = []
    ends = J.ends
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
            a = _end_pt(P, ei)
            b = _end_pt(Q, ej)
            dist = float(np.linalg.norm(b - a))
            w = max(wa, wb)
            if dist > 2.5 * w:
                continue
            ga = FN.end_geometry(P, ei)
            gb = FN.end_geometry(Q, ej)
            ta = ga[1] if ga is not None else unit(a - (P.A[1] if ei == 0 else P.A[-2]))
            tb = gb[1] if gb is not None else unit(b - (Q.A[1] if ej == 0 else Q.A[-2]))
            dot = float(ta @ tb)
            if dot < -0.30:  # angle between continuing directions < 72 degrees
                n = max(3, int(dist))
                pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
                xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
                ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
                if float((D[ys, xs] > 0.5).mean()) >= 0.78:
                    cands.append((dist, i, ei, j, ej, dot))
    if not cands:
        return []
    cands.sort(key=lambda t: (t[0], t[5]))
    best = cands[0]
    return [(best[1], best[2], best[3], best[4])]


def tool_unite(m: Model, J: Joint, D):
    """Shape Builder, unite: two strokes that are really one stroke cut by the joint (a ring in two arcs, a line cut by a crossing,
    or a curved bar) become one stroke; what is left of the joint is then an ordinary T."""
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J.ends and (p[2], p[3]) in J.ends]
    if not pairs:
        pairs = smooth_continuation_pairs(m, J, D)
    if not pairs:
        return None
    return FN.join_pairs(m, pairs)'''

assert target in text, "Target not found in joints.py"
text = text.replace(target, replacement, 1)

with open('linework/joints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Successfully patched linework/joints.py!")
