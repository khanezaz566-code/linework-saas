import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_2.json').read_text())
p = m.paths[17]
print(f"Path 17: closed={p.closed}, w={p.w:.2f}, segs={len(p.segs())}")
for idx in range(len(p.A)):
    print(f"Node {idx}: A={p.A[idx]}, Hin={p.Hin[idx]}, Hout={p.Hout[idx]}")
