import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.finisher import _others_tree

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / 'icon_local_9.json').read_text())
p = m.paths[8]
a = p.A[-1]
tree, P, own = _others_tree(m, 8)
d, k = tree.query(a)
j = own[k]
rj = m.paths[j].w / 2
print(f"Nearest other stroke: path {j} (closed={m.paths[j].closed}, w={m.paths[j].w:.2f})")
print(f"Distance to path {j}: {d:.2f}px, rj={rj:.2f}px")
print(f"Nearest pt on path {j}: {P[k]}")
