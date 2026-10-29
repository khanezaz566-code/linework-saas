import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.abspath('.'))

from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][0]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

def debug_emit(engine, msg, **kwargs):
    print(f"[{engine}] {msg}")

res = _process_icon(small, opts, emit=debug_emit, name='ic0')
m = res['model']

print("\nFINAL MODEL PATHS:")
for i, p in enumerate(m.paths):
    print(f"Path {i}: len={p.length():.1f}, closed={p.closed}, nodes={len(p.A)}")
    for ai, a in enumerate(p.A):
        # Cuff top right is around x in [70, 110], y in [90, 140]
        if 70 <= a[0] <= 110 and 90 <= a[1] <= 140:
            print(f"    A[{ai}] = {np.round(a, 2)}, Hin={np.round(p.Hin[ai], 2)}, Hout={np.round(p.Hout[ai], 2)}")
