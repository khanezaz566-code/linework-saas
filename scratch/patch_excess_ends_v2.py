with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\finisher.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = '''def excess_ends(m: Model, ink, D, frac=0.1):
    """Open-path ends with ink in the render that the source does not have around them (thick tips, lumps).
    Returns [(excess_px, path, end, xy)] sorted by excess."""
    extra = ((ink > 0.5) & (D < 0.3)).astype(np.float32)
    H, W = extra.shape
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        tree, P, _ = _others_tree(m, i)
        r = int(max(3, 1.4 * p.w))
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            if tree is not None and float(tree.query(a)[0]) <= 0.85 * p.w:
                continue  # junction end: do not pull back stroke ends that join other strokes
            x0, x1 = int(max(a[0] - r, 0)), int(min(a[0] + r + 1, W))
            y0, y1 = int(max(a[1] - r, 0)), int(min(a[1] + r + 1, H))
            if x1 <= x0 or y1 <= y0:
                continue
            ex = float(extra[y0:y1, x0:x1].sum())
            if ex >= frac * p.w * p.w:
                out.append((ex, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])'''

new_code = '''def excess_ends(m: Model, ink, D, frac=0.1):
    """Open-path ends with ink in the render that the source does not have around them (thick tips, lumps).
    Returns [(excess_px, path, end, xy)] sorted by excess."""
    extra = ((ink > 0.5) & (D < 0.3)).astype(np.float32)
    H, W = extra.shape
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        tree, P, _ = _others_tree(m, i)
        r = int(max(3, 1.4 * p.w))
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            iy, ix = int(round(a[1])), int(round(a[0]))
            if 0 <= iy < H and 0 <= ix < W and D[iy, ix] > 0.45:
                if tree is not None and float(tree.query(a)[0]) <= 0.45 * p.w:
                    continue
            x0, x1 = int(max(a[0] - r, 0)), int(min(a[0] + r + 1, W))
            y0, y1 = int(max(a[1] - r, 0)), int(min(a[1] + r + 1, H))
            if x1 <= x0 or y1 <= y0:
                continue
            ex = float(extra[y0:y1, x0:x1].sum())
            if ex >= frac * p.w * p.w:
                out.append((ex, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])'''

text_norm = text.replace('\r\n', '\n')
old_norm = old_code.replace('\r\n', '\n')
new_norm = new_code.replace('\r\n', '\n')
assert old_norm in text_norm, 'old_norm not in text_norm'
text_norm = text_norm.replace(old_norm, new_norm, 1)

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\finisher.py', 'w', encoding='utf-8') as f:
    f.write(text_norm)
print('Updated excess_ends with D check')
