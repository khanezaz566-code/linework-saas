import os, sys
os.environ['LINEWORK_MEMORY'] = '0'
sys.path.insert(0, os.path.abspath('.'))

import numpy as np
from linework.pipeline import Options, process_icon
from linework import joints as JN
import tools.junction_bench as jb

for name, fn in [('spool', jb.spool), ('star', jb.star), ('hub', jb.hub)]:
    print(f"\n==================== {name} ====================")
    g = fn()
    r = process_icon(g, Options(), name=name)
    m = r['model']
    jn_report = r['metrics'].get('joins', {})
    print(f"Joins report: total={jn_report.get('total')}, clean_first={jn_report.get('clean_first')}, fixed={jn_report.get('fixed')}, unresolved={len(jn_report.get('unresolved', []))}")
    for u in jn_report.get('unresolved', []):
        print(f"  Unresolved at ({u['x']:.1f}, {u['y']:.1f}): {u['reasons']}")
    
    js = JN.find_joints(m)
    for idx, j in enumerate(js):
        fails = JN.check_joint(m, j)
        if fails:
            print(f"  Active check_joint failure: Joint {idx} {j.kind} at ({j.xy[0]:.1f}, {j.xy[1]:.1f}): {fails}")
            for (i, e) in j.ends:
                end = JN._end_pt(m.paths[i], e)
                others = [k for k in j.through if k != i] or j.through
                for o in others:
                    pt, d = JN._nearest_on(m.paths[o], end)
                    print(f"     end ({i},{e}) at ({end[0]:.2f}, {end[1]:.2f}) -> path {o} nearest ({pt[0]:.2f}, {pt[1]:.2f}), dist={d:.3f} px (tol = {0.5 + 0.04 * j.w:.3f})")
