import cv2, json, sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model

d = Path('data/aca01e4ff5aa')
m = Model.from_json((d / f'icon_local_2.json').read_text())
crop = cv2.imread('scratch/icon_crop_2.png', 0)

# Check all paths in Icon 2 and their positions
print(f"Icon 2 dimensions: {crop.shape[1]}x{crop.shape[0]}")
for i, p in enumerate(m.paths):
    f = p.flat(1.0)
    print(f"Path {i:2d}: closed={str(p.closed):5s} w={p.w:.1f} len={p.length():5.1f} x=[{f[:,0].min():5.1f}, {f[:,0].max():5.1f}] y=[{f[:,1].min():5.1f}, {f[:,1].max():5.1f}]")
