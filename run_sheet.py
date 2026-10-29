import os
os.environ.setdefault('LINEWORK_MEMORY', '0')
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
import sys, time, json, cv2, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from multiprocessing import Pool
from linework.pipeline import *
from linework.model import Model
import linework.render as R

SRC = sys.argv[1]
Q = sys.argv[2] if len(sys.argv) > 2 else 'standard'
OUT = sys.argv[3] if len(sys.argv) > 3 else '/tmp/sheet'
if os.path.dirname(OUT):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

def work(a):
    k, crop, off = a
    r = process_icon(crop, Options(quality=Q), name=f'icon{k+1}')
    return k, off, r['model'].to_json(), r['metrics']

def work2(a):
    k, crop, off, o2 = a
    r = process_icon(crop, Options(**o2), name=f'icon{k+1}')
    return k, off, r['model'].to_json(), r['metrics']

if __name__ == '__main__':
    g = cv2.imread(SRC, 0)
    t = time.time()
    W, H, jobs = process_sheet(g, Options(quality=Q))
    with Pool(2) as p:
        res = p.map(work, jobs)
    from linework import setlevel as SL
    res = sorted(res, key=lambda t: t[0])
    weak = SL.weak_icons([t[3] for t in res])
    if weak:
        o2 = second_pass_options(Options(quality=Q))
        t2 = time.time()
        with Pool(2) as p:
            r2 = p.map(work2, [(jobs[k][0], jobs[k][1], jobs[k][2], o2) for k in weak])
        for new in r2:
            k = new[0]
            old = [t for t in res if t[0] == k][0]
            print('SECOND PASS icon', k+1, '%.4f -> %.4f' % (old[3]['iou'], new[3]['iou']), 'kept new' if SL.better(old[3], new[3]) else 'kept old')
            if SL.better(old[3], new[3]):
                res[res.index(old)] = new
        print('second pass took', round(time.time() - t2), 's')
    mods = [Model.from_json(t[2]) for t in res]
    mods, rep = SL.harmonize_widths(mods, [jobs[t[0]][1] for t in res])
    print('SET widths: icons changed', rep['changed'], 'classes', rep['classes'])
    res = [(t[0], t[1], m.to_json(), t[3]) for t, m in zip(res, mods)]
    allm = Model([], W, H)
    for k, off, mj, met in sorted(res):
        m = Model.from_json(mj)
        m.translate(*off)
        allm.paths += m.paths
        jn = met.get('joins', {})
        jn_tuple = (jn.get('total'), jn.get('clean_first'), sum((jn.get('fixed') or {}).values()), len(jn.get('unresolved', [])))
        sx = met.get('structure', {})
        sx_counts = dict(__import__('collections').Counter(x.get('how') for x in sx.get('sites', []) if x.get('fixed')))
        sx_tuple = (sx.get('found', 0), sx.get('fixed', 0), len(sx.get('unresolved', [])))
        print(k+1, 'IoU %.4f (init %.4f) paths %d nodes %d  %ss' % (
            met['iou'], met['iou_initial'], met['paths'], met['nodes'], met['seconds']
        ), met['issues'], 'JOIN', jn_tuple, 'STRUCT', sx_tuple, sx_counts, 'FIN', __import__('collections').Counter((x['kind'], x['fixed']) for x in met.get('finisher', {}).get('sites', [])))
    svg = allm.svg()
    open(OUT + '.svg', 'w').write(svg)
    img = R.render_gray(svg, W, H)
    cv2.imwrite(OUT + '.png', img)
    a = cv2.imread(SRC, 0)
    from linework.trace import ink_map
    D = ink_map(a)
    b = img < 128
    ref = D > 0.5
    print('SHEET IoU', (b & ref).sum() / (b | ref).sum(), 'time', round(time.time() - t))
    d = np.full(ref.shape + (3,), 255, np.uint8)
    d[ref & b] = (190, 190, 190)
    d[ref & ~b] = (0, 0, 255)
    d[~ref & b] = (255, 0, 0)
    cv2.imwrite(OUT + '_diff.png', d)
