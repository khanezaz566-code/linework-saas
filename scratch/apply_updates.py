import re

# 1. Update finisher.py
with open("linework/finisher.py", "r", encoding="utf-8") as f:
    text = f.read()

clean_seam_def = """def _clean_seam(p: Path) -> Path:
    A, Hin, Hout = list(p.A), list(p.Hin), list(p.Hout)
    changed = True
    while changed and len(A) > 2:
        changed = False
        for k in range(len(A) - 1):
            if np.linalg.norm(A[k + 1] - A[k]) < 0.25 * p.w:
                A.pop(k)
                Hin.pop(k)
                Hout.pop(k)
                changed = True
                break
    return Path(np.array(A), np.array(Hin), np.array(Hout), p.w, p.join, p.ml, p.closed)

"""

if "_clean_seam" not in text:
    # insert before join_pairs
    text = text.replace("def join_pairs(m: Model, pairs):", clean_seam_def + "def join_pairs(m: Model, pairs):")

old_join_w = "m.paths[i] = Path(A, Hin, Hout, (P.w + Q.w) / 2, P.join, P.ml, False)"
new_join_w = """LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        m.paths[i] = _clean_seam(Path(A, Hin, Hout, w_merged, P.join, P.ml, False))"""

text = text.replace(old_join_w, new_join_w)

with open("linework/finisher.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated linework/finisher.py")

# 2. Update topology.py
with open("linework/topology.py", "r", encoding="utf-8") as f:
    topo_text = f.read()

old_topo_return = "    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)"
new_topo_return = """    if d_a <= 0.25 * p.w:
        return True
    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)"""

topo_text = topo_text.replace(old_topo_return, new_topo_return)
with open("linework/topology.py", "w", encoding="utf-8") as f:
    f.write(topo_text)
print("Updated linework/topology.py")

# 3. Update joincheck.py
with open("linework/joincheck.py", "r", encoding="utf-8") as f:
    jc_text = f.read()

# INK_FRAC
jc_text = jc_text.replace("INK_FRAC = 0.6", "INK_FRAC = 0.75")

# drift_cap and allow
old_drift = "drift_cap = 0.006 * max(doctor.area, 1)"
new_drift = "drift_cap = max(0.025 * max(doctor.area, 1), 1.5 * len(joints) * (w ** 2))"
jc_text = jc_text.replace(old_drift, new_drift)

old_allow = 'allow = 0.8 * j0["w"] ** 2'
new_allow = 'allow = (1.8 if j0["kind"] == "X" else 1.0) * j0["w"] ** 2'
jc_text = jc_text.replace(old_allow, new_allow)

# Update tool_shape_builder for multi-pair weld and nub moves
old_sb_nub = """    if reason == "nub":
        for i, e in jn["ends"]:
            r = FN.best_end_move(m, i, e, m.paths[i].w)
            if r is not None:
                out.append(r[0])"""

new_sb_nub = """    if reason == "nub":
        for i, e in jn["ends"]:
            r = FN.best_end_move(m, i, e, m.paths[i].w)
            if r is not None:
                out.append(r[0])
            for f in (0.5, 1.0, 1.5, 2.0):
                c = FN.move_end(m, i, e, f * m.paths[i].w)
                if c is not None:
                    out.append(c)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "nub", "corner_split"):
        ends = jn["ends"]
        pairs_to_merge = []
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        pairs_to_merge.append((ia, ea, ib, eb))
        if len(pairs_to_merge) > 1:
            try:
                out.append(FN.merge_corners(m, pairs_to_merge))
            except Exception:
                pass"""

jc_text = jc_text.replace(old_sb_nub, new_sb_nub)

with open("linework/joincheck.py", "w", encoding="utf-8") as f:
    f.write(jc_text)
print("Updated linework/joincheck.py")
