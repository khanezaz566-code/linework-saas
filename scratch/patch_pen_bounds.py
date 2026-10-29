with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add safe path boundary checks in tool_pen
old_pen_top = '''def tool_pen(m: Model, J: Joint):
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
                q = m.paths[j]'''

new_pen_top = '''def tool_pen(m: Model, J: Joint):
    m = m.copy()
    if J.kind in ("T", "Y"):
        for (i, e) in J.ends:
            if i >= len(m.paths):
                continue
            p = m.paths[i]
            end = _end_pt(p, e)
            g = FN.end_geometry(p, e)
            t = g[1] if g is not None else None
            best = None
            for j in J.through:
                if j >= len(m.paths) or j == i:
                    continue
                q = m.paths[j]'''

text = text.replace(old_pen_top.replace('\r\n', '\n'), new_pen_top.replace('\r\n', '\n'))

# Also in Stage 1 fallback use _apply_pen_again
old_fallback = '''        else:
            for J in need:
                cand_single = tool_pen(st["model"], J)
                if cand_single is not None:
                    ink2 = ink_of(cand_single)
                    s2 = doctor.soft(ink2)
                    if s2 <= st["cur"] + tol() and FN._topo(cand_single) <= st["topo"]:
                        st.update(model=cand_single, ink=ink2, cur=s2, topo=FN._topo(cand_single))
                        rep["built"] += 1'''

new_fallback = '''        else:
            for J in need:
                cand_single = _apply_pen_again(st["model"], J)
                if cand_single is not None and cand_single is not st["model"]:
                    ink2 = ink_of(cand_single)
                    s2 = doctor.soft(ink2)
                    if s2 <= st["cur"] + tol() and FN._topo(cand_single) <= st["topo"]:
                        st.update(model=cand_single, ink=ink2, cur=s2, topo=FN._topo(cand_single))
                        rep["built"] += 1'''

text = text.replace(old_fallback.replace('\r\n', '\n'), new_fallback.replace('\r\n', '\n'))

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched tool_pen boundaries and fallback')
