path = 'linework/joints.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

old_tool_line = '''def tool_line(m: Model, J: Joint, arc=False):
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

new_tool_line = '''def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is None:
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

assert old_tool_line in code, "old_tool_line not found!"
code = code.replace(old_tool_line, new_tool_line)

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(code)

print("Updated tool_line in linework/joints.py")
