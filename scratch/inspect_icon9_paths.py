import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework import joints as JN

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / 'icon_local_9.json').read_text())
print("Icon 9 paths:")
for i, p in enumerate(m.paths):
    f = p.flat(1.0)
    print(f"Path {i}: closed={p.closed}, len={p.length():.1f}, w={p.w:.2f}, x=[{f[:,0].min():.1f}, {f[:,0].max():.1f}], y=[{f[:,1].min():.1f}, {f[:,1].max():.1f}]")

for j in JN.find_joints(m):
    fails = JN.check_joint(m, j)
    if fails:
        print(f"Joint {j.kind} at {j.xy}: fails={fails}, ends={j.ends}, through={j.through}")
