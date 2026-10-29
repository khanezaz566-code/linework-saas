import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True

for icon_idx in [0, 1]:
    box = job['icons'][icon_idx]['box']
    crop = orig[box[1]:box[3], box[0]:box[2]]
    w0 = estimate_width(ink_map(crop))
    k = opts.norm_stroke / w0
    H, W = crop.shape
    small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
    def log_ev(**kw):
        msg = kw.get('msg', '')
        if 'Join check' in msg or 'Finisher' in msg:
            print(f"Icon {icon_idx}: {msg}")
    res = _process_icon(small, opts, emit=log_ev, name=f'ic{icon_idx}')
    print(f"Icon {icon_idx} joins report:", res.get('joins'))
