import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import joints as JN
from linework import finisher as FN
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map

crop = cv2.imread('scratch/icon_crop_6.png', 0)
D = ink_map(crop)
doc = Doctor(D)
m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_6.json').read_text())

# Joint Y at [285.26, 62.32]
target_J = None
for J in JN.find_joints(m):
    if np.linalg.norm(J.xy - [285.26, 62.32]) < 5:
        target_J = J
        break

print(f"Target joint: {target_J}")
print(f"Old tool_line: {JN.tool_line(m, target_J)}")

# New tool_line logic:
def improved_tool_line(m, J, arc=False):
    cand = m
    changed = False
    for (i, e) in J.ends:
        c = FN.fix_end(cand, i, e, smooth=arc)
        if c is not None:
            cand = c
            changed = True
    return cand if changed else None

cand = improved_tool_line(m, target_J)
print(f"Improved tool_line result: {cand is not None}")
if cand is not None:
    soft_old = doc.soft(ink_of(m))
    soft_new = doc.soft(ink_of(cand))
    fails_old = JN.check_joint(m, target_J)
    # find corresponding joint in cand
    new_js = JN.find_joints(cand)
    new_J = min(new_js, key=lambda j: np.linalg.norm(j.xy - target_J.xy))
    fails_new = JN.check_joint(cand, new_J)
    print(f"Fails: {fails_old} -> {fails_new}")
    print(f"Soft: {soft_old:.1f} -> {soft_new:.1f}")
