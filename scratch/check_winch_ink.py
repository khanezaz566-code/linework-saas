import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P
from linework.trace import ink_map
from linework import lessons as LS
from linework.model import Model

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
k, crop, off = jobs[4]
D = ink_map(crop)
key = LS.crop_key(crop, "standard", 0.0)
mf = Model.from_json(LS.best_get(key)["model"])

# Print top ink edge y for x = 165..300 in steps of 5
for x in range(165, 300, 4):
    ys = np.nonzero(D[:110, x] > 0.5)[0]
    y_top = ys[0] if len(ys) else -1
    y_bot = ys[-1] if len(ys) else -1
    print(f"x={x:3d}: ink y=[{y_top:2d}..{y_bot:2d}] (thick={y_bot-y_top+1:2d})")

print("=== Flattened min y of mf top arches ===")
for pi in [0, 1, 2, 5, 6, 9]:
    p = mf.paths[pi]
    f = p.flat(0.5)
    f_top = f[f[:, 1] < 85]
    print(f"mf[{pi}]: w={p.w:.2f}, min_y={f_top[:, 1].min():.2f}, max_y={f_top[:, 1].max():.2f}, pts={np.round(f_top[::4], 1).tolist()}")
