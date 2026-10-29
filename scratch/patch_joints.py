import re

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace find_joints through-stroke and end query tolerances
old_find = '''    for a, b in cKDTree(E).query_pairs(0.9 * wmax):
        if ends[a][0] != ends[b][0] and np.linalg.norm(E[a] - E[b]) <= 0.9 * max(ends[a][3], ends[b][3]):
            par[f(a)] = f(b)
    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        mids = np.mean([ends[k][2] for k in g], axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        for k in g:
            for q in tree.query_ball_point(ends[k][2], 1.0 * ends[k][3]):
                if own[q] not in mem_paths:
                    thr.add(int(own[q]))'''

new_find = '''    for a, b in cKDTree(E).query_pairs(1.2 * wmax):
        if ends[a][0] != ends[b][0] and np.linalg.norm(E[a] - E[b]) <= 1.2 * max(ends[a][3], ends[b][3]):
            par[f(a)] = f(b)
    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        mids = np.mean([ends[k][2] for k in g], axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        for k in g:
            for q in tree.query_ball_point(ends[k][2], 1.35 * ends[k][3]):
                if own[q] not in mem_paths:
                    thr.add(int(own[q]))'''

text = text.replace(old_find.replace('\r\n', '\n'), new_find.replace('\r\n', '\n'))

# Improve tool_pen for L corners and T intersections
old_pen = '''def tool_pen(m: Model, J: Joint):
    m = m.copy()
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            p = m.paths[i]
            end = _end_pt(p, e)
            best = min(((j, *_nearest_on(m.paths[j], end)) for j in J.through if j != i), key=lambda t: t[2], default=None)
            if best is None:
                continue
            j, X, d = best
            if d > 1.2 * J.w:
                continue
            q = m.paths[j]
            k = insert_anchor(q, X)
            X = q.A[k].copy()
            _set_end(p, e, X)
    else:
        if len(J.ends) > 2:  # three or more ends are not one corner: unite the pieces of one stroke first (tool_unite)
            return m
        mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
        for (i, e) in J.ends:
            _set_end(m.paths[i], e, mid)
        if len(J.ends) == 2 and J.ends[0][0] != J.ends[1][0]:
            m = FN.merge_corners(m, [(J.ends[0][0], J.ends[0][1], J.ends[1][0], J.ends[1][1])])
    for i in range(len(m.paths)):
        m.paths[i] = delete_duplicate_anchors(m.paths[i])
    return m'''

new_pen = '''def tool_pen(m: Model, J: Joint):
    m = m.copy()
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            p = m.paths[i]
            end = _end_pt(p, e)
            g = FN.end_geometry(p, e)
            t = g[1] if g is not None else None
            best = None
            for j in J.through:
                if j == i:
                    continue
                q = m.paths[j]
                X_cand, d_cand = _nearest_on(q, end)
                if t is not None:
                    s_steps = np.arange(0.2, min(1.8 * J.w, 20.0), 0.4)
                    ray = end[None, :] + s_steps[:, None] * t[None, :]
                    f = q.flat(0.25)
                    tree_q = cKDTree(f)
                    d_ray, idx_ray = tree_q.query(ray)
                    min_idx = int(np.argmin(d_ray))
                    if d_ray[min_idx] < 0.5 * min(p.w, q.w):
                        X_cand = f[idx_ray[min_idx]]
                        d_cand = float(np.linalg.norm(X_cand - end))
                if best is None or d_cand < best[2]:
                    best = (j, X_cand, d_cand)
            if best is None or best[2] > 1.5 * J.w:
                continue
            j, X, d = best
            q = m.paths[j]
            k = insert_anchor(q, X)
            X = q.A[k].copy()
            _set_end(p, e, X)
    else:
        if len(J.ends) > 2:  # three or more ends are not one corner: unite the pieces of one stroke first (tool_unite)
            return m
        if len(J.ends) == 2 and J.ends[0][0] != J.ends[1][0]:
            geo = [(i, e, FN.end_geometry(m.paths[i], e)) for i, e in J.ends]
            X = None
            if all(g is not None for _, _, g in geo):
                (i1, e1, g1), (i2, e2, g2) = geo
                c1, t1, c2, t2 = g1[0], g1[1], g2[0], g2[1]
                den = _cr2(t1, t2)
                if abs(den) >= 0.15:
                    s1 = _cr2(c2 - c1, t2) / den
                    X = c1 + s1 * t1
            if X is None or np.linalg.norm(X - J.xy) > 1.8 * J.w:
                X = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
            for (i, e) in J.ends:
                _set_end(m.paths[i], e, X)
            m = FN.merge_corners(m, [(J.ends[0][0], J.ends[0][1], J.ends[1][0], J.ends[1][1])])
        else:
            mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
            for (i, e) in J.ends:
                _set_end(m.paths[i], e, mid)
    for i in range(len(m.paths)):
        m.paths[i] = delete_duplicate_anchors(m.paths[i])
    return m'''

text = text.replace(old_pen.replace('\r\n', '\n'), new_pen.replace('\r\n', '\n'))

# Improve tol() and Stage 1 individual fallback in run_join_engine
old_engine_part = '''    def tol():
        return max(2.0, 0.003 * st["cur"])'''

new_engine_part = '''    def tol():
        return max(4.0, 0.003 * max(doctor.area, 1), 0.006 * st["cur"])'''

text = text.replace(old_engine_part.replace('\r\n', '\n'), new_engine_part.replace('\r\n', '\n'))

old_stage1 = '''    # stage 1: build every joint carefully (ends exactly on the centreline they join) - batch first, then joint by joint
    ex, mi = _ink_maps(st["ink"], D)
    joints = find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in check_joint(st["model"], J)]
    if need:
        cand = st["model"]
        for J in need:
            cand = tool_pen(cand, J) if cand is st["model"] else _apply_pen_again(cand, J)
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 <= st["cur"] + tol() and FN._topo(cand) <= st["topo"]:
            st.update(model=cand, ink=ink2, cur=s2, topo=FN._topo(cand))
            rep["built"] = len(need)'''

new_stage1 = '''    # stage 1: build every joint carefully (ends exactly on the centreline they join) - batch first, then fallback to per-joint
    ex, mi = _ink_maps(st["ink"], D)
    joints = find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in check_joint(st["model"], J)]
    if need:
        cand = st["model"]
        for J in need:
            cand = tool_pen(cand, J) if cand is st["model"] else _apply_pen_again(cand, J)
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 <= st["cur"] + tol() and FN._topo(cand) <= st["topo"]:
            st.update(model=cand, ink=ink2, cur=s2, topo=FN._topo(cand))
            rep["built"] = len(need)
        else:
            for J in need:
                cand_single = tool_pen(st["model"], J)
                if cand_single is not None:
                    ink2 = ink_of(cand_single)
                    s2 = doctor.soft(ink2)
                    if s2 <= st["cur"] + tol() and FN._topo(cand_single) <= st["topo"]:
                        st.update(model=cand_single, ink=ink2, cur=s2, topo=FN._topo(cand_single))
                        rep["built"] += 1'''

text = text.replace(old_stage1.replace('\r\n', '\n'), new_stage1.replace('\r\n', '\n'))

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated linework/joints.py successfully')
