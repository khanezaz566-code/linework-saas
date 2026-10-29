import json, os, glob
import numpy as np

# Find 3-way junction: horizontal line + vertical + diagonal
for k in range(10):
    svg_p = f'data/225b51e61676/icon_{k}.svg'
    with open(svg_p) as f:
        svg_text = f.read()
    json_p = f'data/225b51e61676/icon_{k}.json'
    with open(json_p) as f:
        d = json.load(f)
    print(f"\nIcon {k}:")
    for pi, p in enumerate(d['paths']):
        A = np.array(p['A'])
        Hin = np.array(p['Hin'])
        Hout = np.array(p['Hout'])
        # Check start and end curvature
        c_start = np.linalg.norm(A[0] - Hout[0])
        c_end = np.linalg.norm(A[-1] - Hin[-1])
        print(f"  path {pi}: start={A[0].round(1)} c_start={c_start:.1f} | end={A[-1].round(1)} c_end={c_end:.1f} | len={len(A)}")
