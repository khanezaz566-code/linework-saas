import sys, numpy as np
sys.path.insert(0, '.')
from pathlib import Path
from linework.model import Model
from scipy.ndimage import gaussian_filter1d
from linework.geom import resample

m = Model.from_json(Path('data/aca01e4ff5aa/icon_local_2.json').read_text())
p = m.paths[17]
w = p.w
sig = 2.5
L = p.length()
f = resample(p.flat(), 0.75)
sm = gaussian_filter1d(f, sig * w / 0.75, axis=0, mode="nearest")
e = f - sm
t = np.gradient(sm, axis=0)
t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
lat = e[:, 0] * -t[:, 1] + e[:, 1] * t[:, 0]
k_clip = int(2 * sig * w / 0.75)
core = lat[k_clip: len(lat) - k_clip] if not p.closed else lat
rms = float(np.sqrt((core ** 2).mean())) / w
sgn = np.sign(core[np.abs(core) > 0.02 * w])
zc = int((np.diff(sgn) != 0).sum()) if len(sgn) > 1 else 0
print(f"Path 17: L={L:.1f}, w={w:.2f}, rms={rms:.3f}, zc={zc}")

# Also check chord deviation (distance from straight line connecting endpoints)
v = f[-1] - f[0]
Lv = np.linalg.norm(v)
uv = v / Lv
perp = np.array([-uv[1], uv[0]])
chord_dev = (f - f[0]) @ perp
max_chord_dev = float(np.abs(chord_dev).max())
print(f"Chord deviation: {max_chord_dev:.2f}px ({max_chord_dev/w:.2f} * w)")
# Is it predominantly along one axis?
dx = abs(v[0])
dy = abs(v[1])
axis_ratio = max(dx, dy) / max(min(dx, dy), 1e-3)
print(f"Axis ratio: {axis_ratio:.1f} (dx={dx:.1f}, dy={dy:.1f})")
