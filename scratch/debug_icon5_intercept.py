import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework.doctor import Doctor, ink_of
from linework import edit as E
from linework import finisher as FN
from linework import joints as JN
from linework import structfix as SF

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D_sm = T.ink_map(small)

# Let's inspect Finisher corner pairs right after Structfix
from linework.pipeline import _process_icon
# Let's intercept finisher and joints
orig_finish = FN.finish
def debug_finish(m, *args, **kwargs):
    print("--- BEFORE FINISHER ---")
    for i, p in enumerate(m.paths):
        print(f"  P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
    cp = FN.corner_pairs(m, tol=1.2)
    print("FN.corner_pairs(tol=1.2):", cp)
    cp_wide = FN.corner_pairs(m, tol=3.5)
    print("FN.corner_pairs(tol=3.5):", cp_wide)
    res = orig_finish(m, *args, **kwargs)
    m_out = res[0]
    print("--- AFTER FINISHER ---")
    for i, p in enumerate(m_out.paths):
        print(f"  P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
    return res

FN.finish = debug_finish

orig_joints = JN.run_join_engine
def debug_joints(m, *args, **kwargs):
    print("--- BEFORE JOIN ENGINE ---")
    for i, p in enumerate(m.paths):
        print(f"  P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
    js = JN.find_joints(m)
    print(f"JN.find_joints: {len(js)} joints found")
    for J in js:
        print(f"  Joint {J.kind} at {J.xy.round(2)}: ends={J.ends} thr={J.through}")
    res = orig_joints(m, *args, **kwargs)
    m_out = res[0]
    print("--- AFTER JOIN ENGINE ---")
    for i, p in enumerate(m_out.paths):
        print(f"  P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
    return res

JN.run_join_engine = debug_joints

res = _process_icon(small, opts, name="icon_5_small")
