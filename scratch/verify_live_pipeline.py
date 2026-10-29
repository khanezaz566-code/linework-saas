import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map
from linework.doctor import ink_of

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

    print(f"\nProcessing Icon {icon_idx}...")
    res = _process_icon(small, opts, emit=lambda **k: None, name=f'ic{icon_idx}')
    m = res['model']
    print(f"Icon {icon_idx} done: paths={len(m.paths)}, iou={res['metrics']['iou']*100:.2f}%")
    
    img = (ink_of(m) * 255).astype(np.uint8)
    if icon_idx == 0:
        cuff_crop = img[90:140, 65:115]
    else:
        cuff_crop = img[110:160, 65:115]
    cuff_crop_4x = cv2.resize(cuff_crop, (200, 200), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'scratch/live_cuff_{icon_idx}.png', cuff_crop_4x)
    print(f"Saved scratch/live_cuff_{icon_idx}.png")
