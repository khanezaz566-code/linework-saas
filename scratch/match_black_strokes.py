import cv2, numpy as np
from pathlib import Path

orig = cv2.imread('data/aca01e4ff5aa/original.png', 0)
orig_bin = (orig < 128).astype(np.uint8)

brain_dir = Path(r'C:\Users\USER\.gemini\antigravity\brain\970fe8ba-3395-424d-a702-a938d367e356\.user_uploaded')
uploaded = [
    ('life_vest', 'media_1793018607536_5c1de092.png'),
    ('anchor', 'media_1793018609932_2072e533.png'),
    ('cylinder', 'media_1793018612798_1ff26844.png'),
    ('cleat', 'media_1793018619657_c79ec548.png'),
    ('radiator', 'media_1793018622949_43eb2c9a.png')
]

j_icons = [
    [106, 43, 588, 525],
    [761, 66, 1320, 502],
    [1490, 16, 1967, 547],
    [2168, 48, 2641, 520],
    [82, 595, 702, 974],
    [833, 528, 1247, 1039],
    [1507, 529, 1949, 1038],
    [2139, 624, 2671, 945],
    [81, 1073, 612, 1465],
    [844, 1026, 1240, 1514],
    [1483, 1026, 1973, 1514],
    [2173, 1026, 2638, 1514]
]

for name, fname in uploaded:
    img = cv2.imread(str(brain_dir / fname))
    # Extract only black pixels (ignore red markup)
    # Red markup has high R, low G, low B
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    black = (r < 80) & (g < 80) & (b < 80)
    black = black.astype(np.uint8)
    
    # Try different scales
    best_val = -1
    best_loc = (0, 0)
    best_s = 1.0
    for s in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        h_s, w_s = int(black.shape[0] * s), int(black.shape[1] * s)
        if h_s >= orig_bin.shape[0] or w_s >= orig_bin.shape[1] or h_s < 20 or w_s < 20:
            continue
        tpl = cv2.resize(black, (w_s, h_s), interpolation=cv2.INTER_NEAREST)
        res = cv2.matchTemplate(orig_bin, tpl, cv2.TM_CCOEFF_NORMED)
        min_v, max_v, min_l, max_l = cv2.minMaxLoc(res)
        if max_v > best_val:
            best_val = max_v
            best_loc = max_l
            best_s = s
    
    # Check which icon box best_loc falls into
    bx, by = best_loc
    matching_k = None
    for k, (x0, y0, x1, y1) in enumerate(j_icons):
        if x0 <= bx <= x1 and y0 <= by <= y1:
            matching_k = k
            break
        # Or overlap
        if not (bx > x1 or bx + 50 < x0 or by > y1 or by + 50 < y0):
            matching_k = k
    print(f"{name:10} ({fname}) -> matched Icon {matching_k} at {best_loc} (score {best_val:.3f}, scale {best_s})")
