import os, sys
os.environ['LINEWORK_MEMORY'] = '0'
sys.path.insert(0, os.path.abspath('.'))

from linework import joints as JN
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
import tools.junction_bench as jb
from linework.pipeline import Options, process_icon

g = jb.spool()
r = process_icon(g, Options(finish=False, joins=False), name='spool')
m = r['model']
D = ink_map(g)
doc = Doctor(D)

js = JN.find_joints(m)
for idx, j in enumerate(js):
    bad = JN.check_joint(m, j)
    if bad:
        cand = JN.tool_pen(m, j)
        if cand is None:
            print(f"Joint {idx} ({j.kind}) at {j.xy}: cand is None!")
        else:
            j2 = JN.find_joints(cand)
            bad2 = JN.check_joint(cand, j2[idx]) if idx < len(j2) else []
            s_diff = doc.soft(ink_of(cand)) - doc.soft(ink_of(m))
            t_diff = JN.FN._topo(cand) - JN.FN._topo(m)
            print(f"Joint {idx} ({j.kind}) at {j.xy}: bad {bad} -> {bad2}, soft diff {s_diff:+.2f}, topo diff {t_diff:+d}")
