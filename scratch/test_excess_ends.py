import os, sys
os.environ['LINEWORK_MEMORY'] = '0'
sys.path.insert(0, os.path.abspath('.'))

import numpy as np
from linework import joints as JN
from linework import finisher as FN
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
import tools.junction_bench as jb
from linework.pipeline import Options, process_icon

g = jb.spool()
# test what excess_ends currently returns on m before finish
r0 = process_icon(g, Options(finish=False, joins=False), name='spool')
m0 = r0['model']
D = ink_map(g)
doc = Doctor(D)
ink0 = ink_of(m0)

ex_all = FN.excess_ends(m0, ink0, D)
print(f"excess_ends returned {len(ex_all)} ends on m0:")
for ex, i, e, xy in ex_all:
    tree, P, own = FN._others_tree(m0, i)
    dmin = float(tree.query(xy)[0]) if tree is not None else 999.0
    w = m0.paths[i].w
    print(f"  end ({i},{e}) at {np.round(xy, 1)}: dist to others = {dmin:.2f} px ({dmin/w:.2f}*w)")
