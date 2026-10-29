import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json, cv2
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map

job = json.load(open('data/b95d5c14c7a9/job.json'))
box = job['icons'][7]['box']
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
crop = orig[box[1]:box[3], box[0]:box[2]]

w0 = estimate_width(ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D = ink_map(small)

import linework.pipeline as pipe
orig_fn = pipe.initial_model
def debug_initial_model(*a, **kw):
    m = orig_fn(*a, **kw)
    print('initial_model paths:', len(m.paths))
    return m
pipe.initial_model = debug_initial_model

import linework.rings as RG
orig_apply_ring = RG.apply_ring
def debug_apply_ring(m, r):
    res = orig_apply_ring(m, r)
    print(f'apply_ring: {len(m.paths)} -> {len(res.paths)}')
    return res
RG.apply_ring = debug_apply_ring

import linework.edit as E
orig_exec = E.execute
def debug_exec(m, cmd, D):
    res, extra = orig_exec(m, cmd, D)
    if len(res.paths) != len(m.paths):
        print(f"E.execute {cmd['op']}: {len(m.paths)} -> {len(res.paths)}")
    return res, extra
E.execute = debug_exec

import linework.structfix as SF
orig_sf = SF.run_structure_engine
def debug_sf(m, *a, **kw):
    m_out, ink, cur, sx = orig_sf(m, *a, **kw)
    print(f'structfix: {len(m.paths)} -> {len(m_out.paths)}')
    return m_out, ink, cur, sx
SF.run_structure_engine = debug_sf

import linework.finisher as FN
orig_fnish = FN.finish
def debug_fnish(m, *a, **kw):
    m_out, ink, cur, fin = orig_fnish(m, *a, **kw)
    print(f'finisher: {len(m.paths)} -> {len(m_out.paths)}')
    return m_out, ink, cur, fin
FN.finish = debug_fnish

import linework.joints as JN
orig_jn = JN.run_join_engine
def debug_jn(m, *a, **kw):
    m_out, ink, cur, jn = orig_jn(m, *a, **kw)
    print(f'join_engine: {len(m.paths)} -> {len(m_out.paths)}')
    return m_out, ink, cur, jn
JN.run_join_engine = debug_jn

res = _process_icon(small, opts, emit=lambda **k: None, name='ic7')
print('final paths:', len(res['model'].paths))
for i, p in enumerate(res['model'].paths):
    print(f"Path {i}: len={p.length():.2f}, closed={p.closed}, nodes={len(p.A)}")
