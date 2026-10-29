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
print(f"Found {len(js)} joints before join engine:")
for idx, j in enumerate(js[:5]):
    print(f"\nJoint {idx} ({j.kind}): xy={j.xy}, ends={j.ends}, through={j.through}")
    cand = JN.tool_pen(m, j)
    if cand is not None:
        c_soft = doc.soft(ink_of(cand))
        m_soft = doc.soft(ink_of(m))
        c_topo = JN.FN._topo(cand)
        m_topo = JN.FN._topo(m)
        print(f"  tool_pen result: soft {m_soft:.2f} -> {c_soft:.2f} (diff {c_soft - m_soft:+.2f}), topo {m_topo} -> {c_topo}")
        j_after = JN.find_joints(cand)
        if idx < len(j_after):
            print(f"  check_joint after tool_pen: {JN.check_joint(cand, j_after[idx])}")
    else:
        print("  tool_pen returned None!")
