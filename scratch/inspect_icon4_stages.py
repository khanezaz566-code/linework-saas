import sys, os, numpy as np
sys.path.insert(0, os.path.abspath('.'))
import json, cv2
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][4]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Hook edit operations
import linework.edit as E
orig_exec = E.execute
def track_exec(m, cmd, D):
    res, extra = orig_exec(m, cmd, D)
    for p in res.paths:
        for a in p.A:
            if abs(a[0] - 133.0) < 0.5 and a[1] > 63.0:
                print(f"BINGO! E.execute {cmd['op']} created stub anchor: {a}")
                return res, extra
    return res, extra
E.execute = track_exec

import linework.structfix as SF
orig_sf = SF.run_structure_engine
def track_sf(m, *a, **kw):
    res, ink, cur, sx = orig_sf(m, *a, **kw)
    for p in res.paths:
        for a in p.A:
            if abs(a[0] - 133.0) < 0.5 and a[1] > 63.0:
                print(f"BINGO! structfix created stub anchor: {a}")
                return res, ink, cur, sx
    return res, ink, cur, sx
SF.run_structure_engine = track_sf

import linework.finisher as FN
orig_fn = FN.finish
def track_fn(m, *a, **kw):
    res, ink, cur, fin = orig_fn(m, *a, **kw)
    for p in res.paths:
        for a in p.A:
            if abs(a[0] - 133.0) < 0.5 and a[1] > 63.0:
                print(f"BINGO! finisher created stub anchor: {a}")
                return res, ink, cur, fin
    return res, ink, cur, fin
FN.finish = track_fn

import linework.joints as JN
orig_jn = JN.run_join_engine
def track_jn(m, *a, **kw):
    res, ink, cur, jn = orig_jn(m, *a, **kw)
    for p in res.paths:
        for a in p.A:
            if abs(a[0] - 133.0) < 0.5 and a[1] > 63.0:
                print(f"BINGO! run_join_engine created stub anchor: {a}")
                return res, ink, cur, jn
    return res, ink, cur, jn
JN.run_join_engine = track_jn

orig_lock = JN.lock_joints
def track_lock(m):
    res = orig_lock(m)
    for p in res.paths:
        for a in p.A:
            if abs(a[0] - 133.0) < 0.5 and a[1] > 63.0:
                print(f"BINGO! lock_joints created stub anchor: {a}")
                return res
    return res
JN.lock_joints = track_lock

res = _process_icon(small, opts, emit=lambda **k: None, name='ic4')
