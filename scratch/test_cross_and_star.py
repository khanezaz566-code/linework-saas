import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework import pipeline as P

def make_cross():
    g = np.full((240, 240), 255, np.uint8)
    cv2.line(g, (30, 120), (210, 120), 0, 10, cv2.LINE_AA)
    cv2.line(g, (120, 30), (120, 210), 0, 10, cv2.LINE_AA)
    return g

def make_x_cross():
    g = np.full((240, 240), 255, np.uint8)
    cv2.line(g, (40, 40), (200, 200), 0, 10, cv2.LINE_AA)
    cv2.line(g, (40, 200), (200, 40), 0, 10, cv2.LINE_AA)
    return g

def make_star_6():
    g = np.full((260, 260), 255, np.uint8)
    c = np.array([130, 130])
    for k in range(3):
        a = k * np.pi / 3
        p0 = (c - 95 * np.array([np.cos(a), np.sin(a)])).astype(int)
        p1 = (c + 95 * np.array([np.cos(a), np.sin(a)])).astype(int)
        cv2.line(g, tuple(p0), tuple(p1), 0, 10, cv2.LINE_AA)
    return g

def make_star_8():
    g = np.full((260, 260), 255, np.uint8)
    c = np.array([130, 130])
    for k in range(4):
        a = k * np.pi / 4
        p0 = (c - 95 * np.array([np.cos(a), np.sin(a)])).astype(int)
        p1 = (c + 95 * np.array([np.cos(a), np.sin(a)])).astype(int)
        cv2.line(g, tuple(p0), tuple(p1), 0, 10, cv2.LINE_AA)
    return g

for name, fn in [("cross_90", make_cross), ("cross_x", make_x_cross), ("star_6", make_star_6), ("star_8", make_star_8)]:
    g = fn()
    D = ink_map(g)
    br = refined_branches(D)
    ch, W0 = build_chains(br)
    r = P.process_icon(g, P.Options(quality="fast", memory=False), name=name)
    m = r["model"]
    print(f"=== {name}: branches={len(br)}, chains={len(ch)}, final_paths={len(m.paths)}, IoU={r['metrics']['iou']*100:.2f}% ===")
    for i, b in enumerate(br):
        print(f"  br {i}: len={len(b['pts'])}, sj={b['sj']}, ej={b['ej']}, p0={b['pts'][0].round(1).tolist()} -> p1={b['pts'][-1].round(1).tolist()}")
    for i, p in enumerate(m.paths):
        print(f"  path {i}: nA={len(p.A)}, A={p.A.round(1).tolist()}")
