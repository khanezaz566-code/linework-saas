import sys, cv2, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
from linework import structfix as SF
from scipy.ndimage import gaussian_filter1d
from linework.geom import resample

crop = cv2.imread('scratch/icon_crop_2.png', 0)
D = ink_map(crop)
doc = Doctor(D)

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_2.json').read_text())
p = m.paths[17]
w = p.w
f = resample(p.flat(), 0.75)
sig = 3.5

# Let's test different smoothing levels on Path 17:
for s_val in (2.0, 3.5, 5.0, 8.0):
    sm = gaussian_filter1d(f, s_val * w / 0.75, axis=0, mode="nearest")
    # keep endpoints
    k = int(2 * s_val * w / 0.75)
    ramp = np.clip(np.arange(len(f)) / max(k, 1), 0, 1) * np.clip((len(f) - 1 - np.arange(len(f))) / max(k, 1), 0, 1)
    g = f + (sm - f) * ramp[:, None]
    g[0], g[-1] = f[0], f[-1]
    q = SF._refit(p, g)
    if q is not None:
        m2 = m.copy()
        m2.paths[17] = q
        soft2 = doc.soft(ink_of(m2))
        iou2 = doc.iou(ink_of(m2))
        print(f"sig={s_val:3.1f}: soft={soft2:.1f} (delta={soft2 - doc.soft(ink_of(m)):+.1f}px), iou={iou2*100:.2f}%, max_x_dev={abs(q.A[:,0] - 98.5).max():.1f}px")
