with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace stage 1 with clean fast batch (and move on to stage 2 if batch doesn't pass together)
old_stage1_block = '''    # stage 1: build every joint carefully (ends exactly on the centreline they join) - batch first, then fallback to per-joint
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
                cand_single = _apply_pen_again(st["model"], J)
                if cand_single is not None and cand_single is not st["model"]:
                    ink2 = ink_of(cand_single)
                    s2 = doctor.soft(ink2)
                    if s2 <= st["cur"] + tol() and FN._topo(cand_single) <= st["topo"]:
                        st.update(model=cand_single, ink=ink2, cur=s2, topo=FN._topo(cand_single))
                        rep["built"] += 1'''

new_stage1_block = '''    # stage 1: build every joint carefully (ends exactly on the centreline they join) - fast batch first
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

assert old_stage1_block.replace('\r\n', '\n') in text.replace('\r\n', '\n'), "old_stage1_block not found"
text = text.replace(old_stage1_block.replace('\r\n', '\n'), new_stage1_block.replace('\r\n', '\n'))

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\linework\joints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed stage 1 cleanly')
