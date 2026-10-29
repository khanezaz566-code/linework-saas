# Let's inspect the shapes of the icons:
# 1. Life vest: media_1793018607536_5c1de092.png
# 2. Anchor: media_1793018609932_2072e533.png
# 3. Gas bottle / extinguisher / compressor: media_1793018612798_1ff26844.png
# 4. Cleat: media_1793018619657_c79ec548.png
# 5. Radiator / coil: media_1793018622949_43eb2c9a.png

import cv2, numpy as np

for k in range(12):
    im = cv2.imread(f'scratch/marine_icon_{k}.png', 0)
    # Check simple properties
    h, w = im.shape
    print(f"Icon {k}: shape {w}x{h}")
