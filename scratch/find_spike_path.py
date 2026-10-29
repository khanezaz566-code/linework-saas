import cv2, json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_5.json').read_text())
# Path 0 vs Path 2 vs Path 1
for i, p in enumerate(m.paths):
    pts = p.flat(0.5)
    in_spike = [pt for pt in pts if 310 <= pt[0] <= 370 and 320 <= pt[1] <= 360]
    print(f"Path {i}: {len(in_spike)} pts in spike area")
    if in_spike:
        print(f"  first 5: {in_spike[:5]}")
        print(f"  last 5: {in_spike[-5:]}")
