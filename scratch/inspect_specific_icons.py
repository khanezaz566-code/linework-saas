import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')
j = json.loads((d / 'job.json').read_text())

for k in [5, 6, 8, 9, 2, 4]:
    m = Model.from_json((d / f'icon_local_{k}.json').read_text())
    orig = cv2.imread(f'scratch/icon_crop_{k}.png')
    print(f"Icon {k}: paths={len(m.paths)}, box={j['icons'][k]['box']}")
    # print all unresolved joints and structure
    jn = j['icons'][k]['metrics'].get('joins', {})
    unres_j = jn.get('unresolved', [])
    st = j['icons'][k]['metrics'].get('structure', {})
    unres_s = st.get('unresolved', [])
    print(f"  Unresolved joints ({len(unres_j)}):")
    for u in unres_j:
        print(f"    at ({u['x']:.1f}, {u['y']:.1f}): {u['reasons']}")
    print(f"  Unresolved structure ({len(unres_s)}):")
    for u in unres_s:
        print(f"    at ({u['x']:.1f}, {u['y']:.1f}): {u['kind']} (sev {u.get('severity', 0):.2f})")
