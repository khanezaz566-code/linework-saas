import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.abspath('.'))
from scratch.trace_cuff_defect import small, opts, Du
from linework.pipeline import _process_icon
import linework.finisher as FN
from linework.doctor import ink_of

res = _process_icon(small, opts, emit=lambda **k: None, name='ic0')
m = res['model']
p2, p4 = m.paths[2], m.paths[4]

m_merged = FN.merge_corners(m, [(2, 0, 4, 0)])
p_cuff = m_merged.paths[2]
print('Merged cuff nodes:')
for ai, a in enumerate(p_cuff.A):
    print(f'  A[{ai}] = {np.round(a, 2)}')

img_orig = (ink_of(m) * 255).astype(np.uint8)
img_merged = (ink_of(m_merged) * 255).astype(np.uint8)

# Crop around cuff top right: x in [70, 110], y in [95, 135]
c1 = cv2.resize(img_orig[95:135, 70:110], (200, 200), interpolation=cv2.INTER_NEAREST)
c2 = cv2.resize(img_merged[95:135, 70:110], (200, 200), interpolation=cv2.INTER_NEAREST)
comp = np.hstack([c1, c2])
cv2.imwrite('scratch/cuff_corner_comp.png', comp)
print('Saved cuff_corner_comp.png')
