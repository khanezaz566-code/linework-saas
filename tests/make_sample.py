"""Generate a synthetic monoline icon sheet (different stroke width / style from the demo sheet)."""
import math, sys
from PIL import Image, ImageDraw
S = 4
W, H, SW = 1200, 760, 11
img = Image.new("L", (W * S, H * S), 255)
d = ImageDraw.Draw(img)

def line(pts, w=SW, closed=False):
    pts = [(x * S, y * S) for x, y in pts]
    if closed:
        pts = pts + [pts[0], pts[1]]
    d.line(pts, fill=0, width=int(w * S), joint="curve")
    r = w * S / 2
    for x, y in (pts if closed else [pts[0], pts[-1]]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=0)

def circle(cx, cy, r, w=SW):
    pts = [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in [i * 2 * math.pi / 120 for i in range(121)]]
    line(pts, w, closed=False)

def arc(cx, cy, r, a0, a1, w=SW):
    n = 60
    pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    line(pts, w)

def rrect(x0, y0, x1, y1, r, w=SW):
    pts = []
    for (cx, cy, a) in [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]:
        for i in range(0, 31):
            t = math.radians(a + 90 * i / 30)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    line(pts, w, closed=True)

# row 1
cx, cy = 200, 190                                      # home
line([(cx - 90, cy), (cx, cy - 85), (cx + 90, cy)])
line([(cx - 68, cy - 14), (cx - 68, cy + 85), (cx + 68, cy + 85), (cx + 68, cy - 14)])
line([(cx - 22, cy + 85), (cx - 22, cy + 30), (cx + 22, cy + 30), (cx + 22, cy + 85)])
cx, cy = 600, 190                                      # search
circle(cx - 14, cy - 14, 62)
line([(cx + 30, cy + 30), (cx + 88, cy + 88)])
cx, cy = 1000, 190                                     # mail
rrect(cx - 95, cy - 65, cx + 95, cy + 65, 16)
line([(cx - 92, cy - 52), (cx, cy + 14), (cx + 92, cy - 52)])
# row 2
cx, cy = 200, 560                                      # user
circle(cx, cy - 40, 38)
arc(cx, cy + 105, 85, 195, 345)
cx, cy = 600, 560                                      # check in circle
circle(cx, cy, 88)
line([(cx - 38, cy + 2), (cx - 10, cy + 32), (cx + 42, cy - 28)])
cx, cy = 1000, 560                                     # calendar
rrect(cx - 90, cy - 70, cx + 90, cy + 85, 18)
line([(cx - 90, cy - 22), (cx + 90, cy - 22)])
line([(cx - 40, cy - 92), (cx - 40, cy - 52)])
line([(cx + 40, cy - 92), (cx + 40, cy - 52)])
line([(cx - 40, cy + 20), (cx - 40, cy + 20.1)])
line([(cx + 5, cy + 20), (cx + 5, cy + 20.1)])
line([(cx - 40, cy + 55), (cx - 40, cy + 55.1)])
img = img.resize((W, H), Image.LANCZOS)
img.save(sys.argv[1] if len(sys.argv) > 1 else "samples/basic-set.png")
