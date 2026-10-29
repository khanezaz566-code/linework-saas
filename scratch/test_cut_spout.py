import sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
from linework import structure as ST

crop = cv2.imread('scratch/icon_crop_9.png', 0)
D = ink_map(crop)
doc = Doctor(D)

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_9.json').read_text())
p8 = m.paths[8]
print(f"Path 8 original: A[0]={p8.A[0]}, A[-1]={p8.A[-1]}")

cur_soft = doc.soft(ink_of(m))
cur_iou = doc.iou(ink_of(m))
st_before = ST.compare(D, ink_of(m), p8.w)
print(f"Before cut: soft={cur_soft:.1f}, iou={cur_iou*100:.2f}%, struct_score={st_before['score']:.2f}")

# Cut Path 8 back from x=350.6 to x=334.0
m_cut = m.copy()
p8_cut = m_cut.paths[8]
# Shorten the segment
from linework.finisher import _split_last
# Distance to cut: 350.56 - 334.0 = 16.56 px
# Path 8 has 2 segs
c = p8_cut.segs()[-1]
new_c = _split_last(c, 16.56)
if new_c is not None:
    p8_cut.A[-1] = new_c[3]
    p8_cut.Hin[-1] = new_c[2]
    p8_cut.Hout[-2] = new_c[1]
    
new_soft = doc.soft(ink_of(m_cut))
new_iou = doc.iou(ink_of(m_cut))
st_after = ST.compare(D, ink_of(m_cut), p8.w)
print(f"After cut:  soft={new_soft:.1f}, iou={new_iou*100:.2f}%, struct_score={st_after['score']:.2f}")
print(f"Soft delta: {new_soft - cur_soft:+.1f}px (Improvement={new_soft < cur_soft})")
print(f"Structure score: {st_before['score']:.2f} -> {st_after['score']:.2f}")
