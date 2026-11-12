import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2, numpy as np
from linework.pipeline import process_icon, Options
from linework import topology as T
from linework.doctor import ink_of
from tests.diag_join_problems import make

idx = int(sys.argv[1])
img, name = make(idx, 85 if len(sys.argv) > 2 else None)
r = process_icon(img, Options(fresh=True, memory=False, quality="standard", joins=True, decision=True), name=name)
m = r["model"]
acts = T._plan(m)
print(name, "iou", r["metrics"]["iou"], "gaps(raw plan)", len(acts))
S = 1000 // max(img.shape) if max(img.shape) < 1000 else 1
S = max(1, S)
ink = ink_of(m)
vis = cv2.cvtColor(cv2.resize(img, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
rend = cv2.resize((ink * 255).astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_LINEAR)
vis[..., 2] = np.maximum(vis[..., 2], (255 - np.minimum(255, 255 - rend)) * 0)  # keep source as-is
over = np.full_like(vis, 255)
over[rend > 127] = (60, 60, 60)
for k, i, e, j, f, target, gap in acts:
    pt = T._end(m.paths[i], e)[0]
    print(f"  kind={k} path={i} end={e} other={j} gap={gap:.2f} w={m.paths[i].w:.1f} at=({pt[0]:.1f},{pt[1]:.1f}) target=({target[0]:.1f},{target[1]:.1f})")
    cv2.circle(over, (int(pt[0] * S), int(pt[1] * S)), 22, (0, 0, 255), 2)
cv2.imwrite(f"tests/gapvis_{idx}.png", np.hstack([vis, over]))
