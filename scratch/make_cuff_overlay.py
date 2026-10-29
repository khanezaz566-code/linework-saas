import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Model, Path
from linework.doctor import ink_of

data0 = json.load(open('scratch/m0_current.json'))
paths0 = [Path.from_dict(p) for p in data0['paths']]
m0 = Model(paths0, 257, 255)
small0 = cv2.imread('scratch/small_0.png', 0)
from linework.trace import ink_map
D0 = ink_map(small0)

# Render m0
ink_m0 = ink_of(m0)

# Create RGB overlay:
# Red channel: vector ink
# Green channel: source ink
# Blue: 0
H, W = D0.shape
overlay = np.zeros((H, W, 3), dtype=np.uint8)
overlay[:, :, 2] = (ink_m0 * 255).astype(np.uint8) # Red (BGR index 2)
overlay[:, :, 1] = (D0 * 255).astype(np.uint8)     # Green (BGR index 1)

# Zoom into cuff top-right corner: y in [95..135], x in [65..110]
zoom = overlay[95:135, 65:110]
zoom_big = cv2.resize(zoom, (450, 400), interpolation=cv2.INTER_NEAREST)
cv2.imwrite('scratch/cuff_rgb_overlay.png', zoom_big)
print("Saved cuff_rgb_overlay.png")
