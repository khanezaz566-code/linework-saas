import json, os, glob
import numpy as np

for k in range(10):
    json_p = f'data/225b51e61676/icon_{k}.json'
    if not os.path.exists(json_p): continue
    with open(json_p) as f:
        d = json.load(f)
    print(f"\n--- Icon {k} (total paths: {len(d['paths'])}) ---")
    for pi, p in enumerate(d['paths']):
        A = np.array(p['A'])
        print(f"  path {pi}: closed={p.get('closed')}, len(A)={len(A)}, start={A[0].round(1)}, end={A[-1].round(1)}, w={p.get('w')}")
