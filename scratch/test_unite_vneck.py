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

# Unite pair (1, 1, 2, 0)
m_united = FN.join_pairs(m, [(1, 1, 2, 0)])
print(f"United model paths: {len(m_united.paths)}")
soft_old = doc.soft(ink_of(m))
soft_new = doc.soft(ink_of(m_united))
print(f"Soft: {soft_old:.1f} -> {soft_new:.1f}")
# Now find joints near [285, 62] in m_united
new_js = JN.find_joints(m_united)
new_J = min(new_js, key=lambda j: np.linalg.norm(j.xy - [285, 62]))
fails = JN.check_joint(m_united, new_J)
print(f"New joint at {new_J.xy} ({new_J.kind}): fails={fails}, ends={new_J.ends}, through={new_J.through}")
