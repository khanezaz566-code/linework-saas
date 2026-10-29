import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map
import linework.joints as J

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True

box = job['icons'][0]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Intercept run_join_engine
orig_run_join_engine = J.run_join_engine
def dbg_join_engine(model, D, doctor, ink_of, cur, w, **kwargs):
    print("--- run_join_engine called ---")
    js = J.find_joints(model)
    print(f"find_joints returned {len(js)} joints")
    for idx, j in enumerate(js):
        if len(j.ends) >= 3:
            print(f"Multi-end joint {idx}: kind={j.kind}, xy={np.round(j.xy, 1)}, ends={j.ends}")
            cp = J.corner_continuation_pairs(model, j, D)
            print(f"  corner_continuation_pairs: {cp}")
            tu = J.tool_unite(model, j, D)
            print(f"  tool_unite returned: {tu is not None}")
    return orig_run_join_engine(model, D, doctor, ink_of, cur, w, **kwargs)

J.run_join_engine = dbg_join_engine
_process_icon(small, opts, emit=lambda **k: None, name='ic0')
