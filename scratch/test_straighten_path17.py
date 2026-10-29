import sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.doctor import Doctor, ink_of
from linework.finisher import make_straight

crop = cv2.imread('scratch/icon_crop_2.png', 0)
from linework.trace import ink_map
D = ink_map(crop)
doc = Doctor(D)

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_2.json').read_text())
cur_soft = doc.soft(ink_of(m))
cur_iou = doc.iou(ink_of(m))
print(f"Current Icon 2: IoU={cur_iou*100:.2f}%, soft={cur_soft:.1f}")

m_straight = make_straight(m, 17)
new_soft = doc.soft(ink_of(m_straight))
new_iou = doc.iou(ink_of(m_straight))
print(f"After make_straight(17): IoU={new_iou*100:.2f}%, soft={new_soft:.1f} (delta soft: {new_soft - cur_soft:+.1f}px)")
