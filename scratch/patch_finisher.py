with open('linework/finisher.py', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = '''        is_local_bulge = L >= 4.5 * p.w and len(p.A) >= 4 and (devs <= 0.15 * p.w).mean() >= 0.55
        short_dev = 0.38 if len(p.A) == 3 else 0.22
        eff_dev = max(0.5, (0.42 if is_local_bulge else (max(dev_frac, short_dev) if L < 3.5 * p.w and len(p.A) >= 3 else dev_frac)) * p.w)'''

replacement1 = '''        dx, dy = abs(v[0]), abs(v[1])
        is_axis_aligned = (min(dx, dy) <= 0.25 * p.w) and (max(dx, dy) >= 4.0 * p.w)
        is_local_bulge = L >= 4.5 * p.w and len(p.A) >= 4 and (devs <= 0.15 * p.w).mean() >= 0.55
        short_dev = 0.38 if len(p.A) == 3 else 0.22
        eff_dev = max(0.5, ((1.5 if is_axis_aligned else 0.42) if (is_axis_aligned or is_local_bulge) else (max(dev_frac, short_dev) if L < 3.5 * p.w and len(p.A) >= 3 else dev_frac)) * p.w)'''

assert target1 in text, "Target 1 not found in finisher.py"
text = text.replace(target1, replacement1, 1)

target2 = '''def cap_hits(m: Model, frac=0.1):
    """Round caps / stubs that stick out of the stroke they end in or cross (the small nubs and overshoots at junctions)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            a, b = _end_info(p, e)
            pr = _protrusion(m, i, a, p.w, b)
            if pr > frac * p.w:
                out.append((pr / p.w, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])'''

replacement2 = '''def cap_hits(m: Model, frac=0.1):
    """Round caps / stubs that stick out of the stroke they end in or cross (the small nubs and overshoots at junctions)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            a, b = _end_info(p, e)
            pr = _protrusion(m, i, a, p.w, b)
            if pr > frac * p.w:
                out.append((pr / p.w, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])


def find_penetrating_stubs(m: Model, D):
    """Detect open strokes that have crossed another stroke or entered a closed loop and continue past it
    into white/empty space. Returns [(i, e, cut_distance, end_xy, crossing_path_j)]."""
    hits = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        w = p.w
        tree, P, own = _others_tree(m, i)
        if tree is None:
            continue
        for e in (0, 1):
            f = p.flat(0.5)
            if e == 0:
                f = f[::-1]
            a = f[-1]
            cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
            max_k = int(np.searchsorted(cum, 3.2 * w))
            if max_k < 4:
                continue
            pts = f[::-1][:max_k]
            ds, idxs = tree.query(pts)
            for step_k in range(3, len(ds)):
                dist_to_other = ds[step_k]
                j = own[idxs[step_k]]
                if dist_to_other < 0.40 * w:
                    s = float(cum[step_k])
                    if s >= 0.55 * w:
                        test_pts = f[::-1][:step_k]
                        xs = np.clip(test_pts[:, 0].astype(int), 0, D.shape[1] - 1)
                        ys = np.clip(test_pts[:, 1].astype(int), 0, D.shape[0] - 1)
                        has_hole = float((D[ys, xs] < 0.45).mean()) >= 0.20
                        is_closed = m.paths[j].closed
                        if has_hole or is_closed:
                            hits.append((i, e, s, a.copy(), j))
                            break
    return hits'''

assert target2 in text, "Target 2 not found in finisher.py"
text = text.replace(target2, replacement2, 1)

target3 = '''        # the moved path may have been re-oriented; later hits are re-detected below
    # 4d. thick tips / lumps: ends with excess ink around them are pulled back by whatever amount helps most (verified)'''

replacement3 = '''        # the moved path may have been re-oriented; later hits are re-detected below
    # 4b2. penetrating stubs: open strokes that cross another stroke and overshoot past it
    for i, e, dl, xy, j in find_penetrating_stubs(st["model"], D)[:25]:
        if not time_ok():
            break
        if i >= len(st["model"].paths):
            continue
        cand = move_end(st["model"], i, e, dl)
        if cand is not None:
            attempt(cand, "caps", xy, improve=True)
    # 4d. thick tips / lumps: ends with excess ink around them are pulled back by whatever amount helps most (verified)'''

assert target3 in text, "Target 3 not found in finisher.py"
text = text.replace(target3, replacement3, 1)

with open('linework/finisher.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Successfully patched linework/finisher.py!")
