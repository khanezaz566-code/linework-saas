import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2, numpy as np
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import ink_of
from linework.split import estimate_width
from linework.pipeline import Options
from tests.diag_join_problems import make

idx = int(sys.argv[1]); jq = int(sys.argv[2]) or None
img, name = make(idx, jq)
opts = Options()
D0 = ink_map(img)
w0 = estimate_width(D0)
k = opts.norm_stroke / w0
small = cv2.resize(img, (int(round(img.shape[1] * k)), int(round(img.shape[0] * k))), interpolation=cv2.INTER_AREA)
D = ink_map(small)
w_est = estimate_width(D)
print("name", name, "w0", round(w0, 1), "k", round(k, 3), "small", small.shape, "w_est", round(w_est, 1), "norm_stroke", opts.norm_stroke, "max_stroke", opts.max_stroke)
res = []
for s, sf in [(1, 0.6), (2, 0.6), (3, 0.6)]:
    H, W = D.shape
    Du = ink_map(cv2.resize(small, (W * s, H * s), interpolation=cv2.INTER_CUBIC)) if s > 1 else D
    br = refined_branches(Du)
    chains, W0 = build_chains(br)
    m = initial_model(chains, Du, sigma=opts.sigma * s * sf, err=0.3 * s)
    if s > 1:
        m = m.scaled(1.0 / s, W, H)
    ink = ink_of(m)
    inter = ((ink > .5) & (D > .5)).sum(); uni = ((ink > .5) | (D > .5)).sum()
    print(f"s={s}: branches={len(br)} chains={len(chains)} paths={len(m.paths)} iou={inter/uni:.4f}")
    res.append((s, ink))
S = 4
tiles = [cv2.resize(np.where(D > .5, 0, 255).astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)]
for s, ink in res:
    tiles.append(cv2.resize(np.where(ink > .5, 0, 255).astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST))
y0, y1, x0, x1 = int(70 * S * 0.6), int(160 * S * 0.6) + 40, int(60 * S * 0.6), int(150 * S * 0.6) + 40
Hs, Ws = tiles[0].shape
crop = [t[Hs // 5: Hs * 3 // 5, Ws // 5: Ws * 3 // 5] for t in tiles]
cv2.imwrite(f"tests/trace_stage_{idx}.png", np.hstack([np.pad(c, ((0, 0), (0, 4)), constant_values=128) for c in crop]))
