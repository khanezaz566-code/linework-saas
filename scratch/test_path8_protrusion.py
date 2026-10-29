import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.finisher import _protrusion, _end_info

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / 'icon_local_9.json').read_text())
p = m.paths[8]
for e in (0, 1):
    a, b = _end_info(p, e)
    pr = _protrusion(m, 8, a, p.w, b)
    print(f"Path 8 end {e}: pt={a}, protrusion={pr:.2f}px (w={p.w:.2f})")
