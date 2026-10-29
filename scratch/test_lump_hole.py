import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
import numpy as np
from tools.junction_bench import spool, star, knot
from linework.pipeline import Options, process_icon
from linework.joints import find_joints, _ink_maps
from linework.render import render_gray
from linework.trace import ink_map

def test_lump_hole(name, fn):
    g = fn()
    D = ink_map(g)
    r = process_icon(g, Options(), name=name)
    m = r['model']
    ink = render_gray(m.svg(), g.shape[1], g.shape[0]) < 128
    ex, mi = _ink_maps(ink, D)
    joints = find_joints(m)
    print(f"=== {name} ===")
    H, W = D.shape
    yy, xx = np.indices((H, W))
    for idx, J in enumerate(joints):
        w = J.w
        # Current square check
        r_box = int(2 * w)
        x0, y0 = int(max(J.xy[0] - r_box, 0)), int(max(J.xy[1] - r_box, 0))
        x1, y1 = int(min(J.xy[0] + r_box + 1, W)), int(min(J.xy[1] + r_box + 1, H))
        sq_lump = float(ex[y0:y1, x0:x1].sum())
        sq_hole = float(mi[y0:y1, x0:x1].sum())
        
        # Circular check of radius 1.2 w
        r_circ = 1.2 * w
        dist_sq = (xx[y0:y1, x0:x1] - J.xy[0])**2 + (yy[y0:y1, x0:x1] - J.xy[1])**2
        mask = dist_sq <= r_circ**2
        circ_lump = float(ex[y0:y1, x0:x1][mask].sum())
        circ_hole = float(mi[y0:y1, x0:x1][mask].sum())
        
        thresh = 0.25 * w * w
        print(f"  J#{idx} ({J.kind}): sq_lump={sq_lump:.1f} circ_lump={circ_lump:.1f} | sq_hole={sq_hole:.1f} circ_hole={circ_hole:.1f} (thresh={thresh:.1f})")

test_lump_hole("spool", spool)
test_lump_hole("star", star)
test_lump_hole("knot", knot)
