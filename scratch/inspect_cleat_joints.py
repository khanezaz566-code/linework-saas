import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import joints as JN

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / 'icon_local_8.json').read_text())
for j in JN.find_joints(m):
    fails = JN.check_joint(m, j)
    if fails:
        print(f"Joint {j.kind} at {j.xy}: fails={fails}, ends={j.ends}, through={j.through}")
        for (i, e) in j.ends:
            p = m.paths[i]
            end = p.A[0] if e == 0 else p.A[-1]
            adj = p.A[1] if e == 0 else p.A[-2]
            print(f"  Path {i} end {e}: pt={end}, adj={adj}, dir={end - adj}")
        for th in j.through:
            q = m.paths[th]
            print(f"  Through path {th}: closed={q.closed}, w={q.w}")
