import json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_5.json').read_text())
p = m.paths[0]
for idx in range(38, len(p.A)):
    print(f"Node {idx}: A={p.A[idx]}, Hin={p.Hin[idx]}, Hout={p.Hout[idx]}")
