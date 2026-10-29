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

    res = _process_icon(small, opts, emit=lambda **k: None, name=f'ic{icon_idx}')
    m = res['model']
    
    # Create 3-channel image for visualization
    vis = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (128, 0, 255), (255, 128, 0)]
    for p_i, p in enumerate(m.paths):
        f = p.flat(0.5).astype(np.int32)
        col = colors[p_i % len(colors)]
        cv2.polylines(vis, [f], p.closed, col, 2, cv2.LINE_AA)
        # Mark anchors
        for pt in p.A.astype(np.int32):
            cv2.circle(vis, tuple(pt), 2, (0, 0, 0), -1)
            cv2.circle(vis, tuple(pt), 1, (255, 255, 255), -1)

    if icon_idx == 0:
        cuff_vis = vis[90:140, 65:115]
    else:
        cuff_vis = vis[110:160, 65:115]
    cuff_vis_4x = cv2.resize(cuff_vis, (300, 300), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'scratch/overlay_cuff_{icon_idx}.png', cuff_vis_4x)
    print(f"Saved scratch/overlay_cuff_{icon_idx}.png")
