import json, os, glob
import numpy as np

# Let's check each icon's paths in 225b51e61676
for k in range(10):
    svg_p = f'data/225b51e61676/icon_{k}.svg'
    json_p = f'data/225b51e61676/icon_{k}.json'
    with open(json_p) as f:
        d = json.load(f)
    print(f"Icon {k}: {len(d['paths'])} paths")
    for pi, p in enumerate(d['paths']):
        pts = np.array(p['points'])
        print(f"   path {pi}: n_pts={len(pts)}, closed={p.get('closed')}, start={pts[0].round(1)}, end={pts[-1].round(1)}")
