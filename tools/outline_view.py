"""Outline view for any Linework SVG, like the outline mode of a vector editor: grey stroke, blue centrelines, red rings on joints that are not clean.
usage: python tools/outline_view.py result.svg out.png [zoom=1.0]
Red = end bent / jogged away from its own straight stroke (hook), orange = round cap sticking out of the stroke it ends in (nub).
Also prints one line per marked joint with its position, so it can be found in the editor."""
import os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linework.model import Model
from linework.render import render_gray
from linework import finisher as FN

svg, out = sys.argv[1], sys.argv[2]
z = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
m = Model.from_svg(open(svg).read())
g = render_gray(m.svg(stroke="#bbbbbb"), m.width, m.height)
im = cv2.cvtColor(cv2.resize(g, None, fx=z, fy=z, interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
for p in m.paths:
    cv2.polylines(im, [np.round(p.flat(0.5) * z).astype(np.int32)], p.closed, (255, 80, 0), 1, cv2.LINE_AA)
for ang, i, e, xy in FN.end_hooks(m):
    cv2.circle(im, tuple(np.round(xy * z).astype(int)), int(max(8, 0.9 * m.paths[i].w * z)), (0, 0, 255), 2, cv2.LINE_AA)
    print("hook  path %d end %d at (%.0f, %.0f)  %.0f deg" % (i, e, xy[0], xy[1], ang))
for pr, i, e, xy in FN.cap_hits(m):
    cv2.circle(im, tuple(np.round(xy * z).astype(int)), int(max(8, 0.9 * m.paths[i].w * z)), (0, 140, 255), 2, cv2.LINE_AA)
    print("nub   path %d end %d at (%.0f, %.0f)  %.0f%% of the stroke width" % (i, e, xy[0], xy[1], 100 * pr))
from linework import joints as JN
for j in JN.find_joints(m):
    fails = JN.check_joint(m, j)
    col = (0, 170, 0) if not fails else (200, 0, 200)
    cv2.circle(im, (int(round(j.xy[0] * z)), int(round(j.xy[1] * z))), int(max(5, 0.6 * j.w * z)), col, 1, cv2.LINE_AA)
    if fails:
        print("joint %s at (%.0f, %.0f)  %s" % (j.kind, j.xy[0], j.xy[1], ",".join(fails)))
cv2.imwrite(out, im)
