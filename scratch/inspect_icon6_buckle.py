import json, sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / 'icon_local_6.json').read_text())
crop = cv2.imread('scratch/icon_crop_6.png', 0)

# Region around [229, 320]
region = crop[300:340, 210:250]
ink = (region < 128).astype(int)
print("Raster at Icon 6 buckle [300:340, 210:250]:")
for y in range(0, ink.shape[0], 2):
    line = "".join("#" if ink[y, x] else "." for x in range(0, ink.shape[1], 2))
    print(f"{300+y:3d}: {line}")

print("\nPaths passing near [229, 320]:")
for i, p in enumerate(m.paths):
    f = p.flat(0.5)
    near = np.linalg.norm(f - [229, 320], axis=1) < 15
    if near.any():
        print(f"Path {i}: closed={p.closed}, w={p.w:.2f}")
        for pt in f[near]:
            print(f"  {pt}")
