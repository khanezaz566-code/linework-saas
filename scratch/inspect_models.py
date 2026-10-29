import json, sys
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')
for k in range(12):
    m = Model.from_json((d / f'icon_local_{k}.json').read_text())
    print(f"Icon {k}: paths={len(m.paths)}, W={m.width}, H={m.height}")
