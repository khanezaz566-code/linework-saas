"""20 Ultra-Complex Icon Drawers for Extreme Join & Topology Stress Testing.
Covers multi-way line intersections, serpentine tracks, curved lancets, concentric waves,
high-density nodal crossings, and specific geometric cases reported by users.
"""
from __future__ import annotations
import math
import numpy as np
import cv2

def pt(cx, cy, dx, dy):
    return (int(round(cx + dx)), int(round(cy + dy)))

def line(canvas, pts, sw=6, closed=False):
    for i in range(len(pts) - (0 if closed else 1)):
        p0 = pts[i]
        p1 = pts[(i + 1) % len(pts)]
        cv2.line(canvas, p0, p1, 0, sw, cv2.LINE_AA)

def circle(canvas, cx, cy, r, sw=6):
    cv2.circle(canvas, (int(round(cx)), int(round(cy))), int(round(r)), 0, sw, cv2.LINE_AA)

def arc(canvas, cx, cy, r, a0, a1, sw=6):
    cv2.ellipse(canvas, (int(round(cx)), int(round(cy))), (int(round(r)), int(round(r))), 0, a0, a1, 0, sw, cv2.LINE_AA)

def rrect(canvas, x0, y0, x1, y1, r, sw=6):
    r = min(r, abs(x1 - x0) // 2, abs(y1 - y0) // 2)
    cv2.line(canvas, (x0 + r, y0), (x1 - r, y0), 0, sw, cv2.LINE_AA)
    cv2.line(canvas, (x1, y0 + r), (x1, y1 - r), 0, sw, cv2.LINE_AA)
    cv2.line(canvas, (x1 - r, y1), (x0 + r, y1), 0, sw, cv2.LINE_AA)
    cv2.line(canvas, (x0, y1 - r), (x0, y0 + r), 0, sw, cv2.LINE_AA)
    cv2.ellipse(canvas, (x0 + r, y0 + r), (r, r), 0, 180, 270, 0, sw, cv2.LINE_AA)
    cv2.ellipse(canvas, (x1 - r, y0 + r), (r, r), 0, 270, 360, 0, sw, cv2.LINE_AA)
    cv2.ellipse(canvas, (x1 - r, y1 - r), (r, r), 0, 0, 90, 0, sw, cv2.LINE_AA)
    cv2.ellipse(canvas, (x0 + r, y1 - r), (r, r), 0, 90, 180, 0, sw, cv2.LINE_AA)

def draw_star4(canvas, cx, cy, r_out, r_in, sw=5):
    """Draw a 4-pointed diamond sparkle star."""
    pts = [
        pt(cx, cy, 0, -r_out),
        pt(cx, cy, r_in, -r_in),
        pt(cx, cy, r_out, 0),
        pt(cx, cy, r_in, r_in),
        pt(cx, cy, 0, r_out),
        pt(cx, cy, -r_in, r_in),
        pt(cx, cy, -r_out, 0),
        pt(cx, cy, -r_in, -r_in),
    ]
    line(canvas, pts, sw, closed=True)

# ----------------- 20 Ultra-Complex Drawers ----------------- #

def draw_pen_nib_sparkle(canvas, cx, cy, sw, seed=0):
    """37. Fountain Pen Nib with Split Tines, Breather Hole & 4-Point Sparkles."""
    rot = math.radians(-30 + (seed % 5) * 5)
    cos_r, sin_r = math.cos(rot), math.sin(rot)
    def rot_pt(dx, dy):
        rx = dx * cos_r - dy * sin_r
        ry = dx * sin_r + dy * cos_r
        return pt(cx, cy, rx, ry)
    
    nib_pts = [
        rot_pt(0, -42),
        rot_pt(24, 0),
        rot_pt(18, 22),
        rot_pt(10, 28),
        rot_pt(-10, 28),
        rot_pt(-18, 22),
        rot_pt(-24, 0),
    ]
    line(canvas, nib_pts, sw, closed=True)
    bh = rot_pt(0, -6)
    circle(canvas, bh[0], bh[1], 4, sw)
    line(canvas, [rot_pt(0, -42), rot_pt(0, -10)], sw)
    line(canvas, [rot_pt(-14, 38), rot_pt(14, 38)], sw)
    line(canvas, [rot_pt(-10, 28), rot_pt(-14, 38)], sw)
    line(canvas, [rot_pt(10, 28), rot_pt(14, 38)], sw)
    draw_star4(canvas, cx + int(36 * cos_r), cy - int(32 * sin_r), 12, 4, max(4, sw - 1))
    draw_star4(canvas, cx - int(34 * cos_r), cy + int(32 * sin_r), 9, 3, max(4, sw - 1))

def draw_smart_keypad_rfid(canvas, cx, cy, sw, seed=0):
    """38. Smart Door Lock: 3x3 Squircle Keypad + RFID Contactless Waves + Keyhole."""
    rrect(canvas, cx - 42, cy - 44, cx + 16, cy + 44, 8, sw)
    bw, bh, br = 11, 11, 2
    for r_i in range(3):
        for c_i in range(3):
            bx0 = cx - 36 + c_i * 16
            by0 = cy - 36 + r_i * 16
            rrect(canvas, bx0, by0, bx0 + bw, by0 + bh, br, max(3, sw - 2))
    circle(canvas, cx - 12, cy + 24, 5, sw)
    line(canvas, [pt(cx, cy, -12, 24), pt(cx, cy, -12, 36)], sw)
    line(canvas, [pt(cx, cy, 16, 12), pt(cx, cy, 40, 12)], sw)
    line(canvas, [pt(cx, cy, 16, 24), pt(cx, cy, 40, 24)], sw)
    arc(canvas, cx + 40, cy + 18, 6, -90, 90, sw)
    rrect(canvas, cx + 16, cy - 42, cx + 44, cy - 14, 3, max(4, sw - 1))
    circle(canvas, cx + 30, cy - 20, 2, max(3, sw - 2))
    arc(canvas, cx + 30, cy - 20, 7, -140, -40, max(3, sw - 2))
    arc(canvas, cx + 30, cy - 20, 12, -140, -40, max(3, sw - 2))

def draw_inbox_arrow_v_notch(canvas, cx, cy, sw, seed=0):
    """39. Downwards Arrow Meeting Envelope V-Fold Acute Notch (Image 5 Topology)."""
    tray = [
        pt(cx, cy, -38, -12),
        pt(cx, cy, -38, 36),
        pt(cx, cy, 38, 36),
        pt(cx, cy, 38, -12),
    ]
    line(canvas, tray, sw)
    flap = [
        pt(cx, cy, -38, -12),
        pt(cx, cy, 0, 16),
        pt(cx, cy, 38, -12),
    ]
    line(canvas, flap, sw)
    line(canvas, [pt(cx, cy, -38, 36), pt(cx, cy, -14, 18)], sw)
    line(canvas, [pt(cx, cy, 38, 36), pt(cx, cy, 14, 18)], sw)
    line(canvas, [pt(cx, cy, 0, -42), pt(cx, cy, 0, -2)], sw)
    line(canvas, [pt(cx, cy, -12, -14), pt(cx, cy, 0, -2)], sw)
    line(canvas, [pt(cx, cy, 12, -14), pt(cx, cy, 0, -2)], sw)

def draw_dome_corner_junction(canvas, cx, cy, sw, seed=0):
    """40. Stepped Profile with Curved Dome Roof & Radio Waves (Image 4 Topology)."""
    line(canvas, [pt(cx, cy, -40, -38), pt(cx, cy, -40, 42)], sw)
    arc(canvas, cx - 35, cy - 38, 5, 180, 270, sw)
    line(canvas, [pt(cx, cy, -35, -43), pt(cx, cy, -30, -43)], sw)
    line(canvas, [pt(cx, cy, -30, -43), pt(cx, cy, -30, 42)], sw)
    line(canvas, [pt(cx, cy, -30, 0), pt(cx, cy, -16, 0)], sw)
    line(canvas, [pt(cx, cy, -30, 24), pt(cx, cy, -16, 24)], sw)
    line(canvas, [pt(cx, cy, -16, -24), pt(cx, cy, -16, 42)], sw)
    line(canvas, [pt(cx, cy, -16, -24), pt(cx, cy, -8, -24)], sw)
    line(canvas, [pt(cx, cy, -8, -24), pt(cx, cy, -8, -32)], sw)
    arc(canvas, cx + 12, cy - 24, 20, 180, 270, sw)
    line(canvas, [pt(cx, cy, 12, -44), pt(cx, cy, 26, -44)], sw)
    arc(canvas, cx + 26, cy - 36, 8, 270, 360, sw)
    line(canvas, [pt(cx, cy, 34, -36), pt(cx, cy, 34, 42)], sw)
    line(canvas, [pt(cx, cy, -16, 42), pt(cx, cy, 34, 42)], sw)
    arc(canvas, cx + 28, cy + 18, 14, -60, 60, sw)
    arc(canvas, cx + 28, cy + 18, 22, -60, 60, sw)
    arc(canvas, cx + 28, cy + 18, 30, -60, 60, sw)

def draw_mandala_rosette(canvas, cx, cy, sw, seed=0):
    """41. Concentric Floral Mandala with 12 Intersecting Petal Arcs."""
    circle(canvas, cx, cy, 8, sw)
    for i in range(6):
        a = math.radians(i * 60 + (seed * 10) % 60)
        px = cx + 16 * math.cos(a)
        py = cy + 16 * math.sin(a)
        circle(canvas, px, py, 12, max(4, sw - 1))
    circle(canvas, cx, cy, 40, sw)
    for i in range(6):
        a = math.radians(i * 60 + 30 + (seed * 10) % 60)
        p_in = pt(cx, cy, 28 * math.cos(a), 28 * math.sin(a))
        p_out = pt(cx, cy, 40 * math.cos(a), 40 * math.sin(a))
        line(canvas, [p_in, p_out], sw)

def draw_guilloche_security(canvas, cx, cy, sw, seed=0):
    """42. Banknote Security Guilloche: High-Frequency Intersecting Rosettes."""
    circle(canvas, cx, cy, 10, sw)
    for phase in [0, math.pi / 8]:
        pts = []
        steps = 120
        for s in range(steps + 1):
            t = (s / steps) * 2 * math.pi
            r_val = 26 + 12 * math.cos(6 * t + phase)
            gx = cx + r_val * math.cos(t)
            gy = cy + r_val * math.sin(t)
            pts.append((int(round(gx)), int(round(gy))))
        line(canvas, pts, max(4, sw - 1), closed=True)
    circle(canvas, cx, cy, 42, sw)

def draw_bga_microcontroller(canvas, cx, cy, sw, seed=0):
    """43. BGA Microcontroller with Serpentine Delay Lines & Decoupling Caps."""
    rrect(canvas, cx - 22, cy - 22, cx + 22, cy + 22, 4, sw)
    circle(canvas, cx - 14, cy - 14, 3, sw)
    line(canvas, [
        pt(cx, cy, -22, -10),
        pt(cx, cy, -28, -10),
        pt(cx, cy, -28, -18),
        pt(cx, cy, -34, -18),
        pt(cx, cy, -34, -10),
        pt(cx, cy, -42, -10)
    ], sw)
    line(canvas, [
        pt(cx, cy, 22, 10),
        pt(cx, cy, 28, 10),
        pt(cx, cy, 28, 18),
        pt(cx, cy, 34, 18),
        pt(cx, cy, 34, 10),
        pt(cx, cy, 42, 10)
    ], sw)
    line(canvas, [pt(cx, cy, -22, 6), pt(cx, cy, -42, 6)], sw)
    line(canvas, [pt(cx, cy, 22, -6), pt(cx, cy, 42, -6)], sw)
    rrect(canvas, cx - 8, cy - 38, cx + 8, cy - 28, 2, max(4, sw - 1))
    line(canvas, [pt(cx, cy, -4, -28), pt(cx, cy, -4, -22)], sw)
    line(canvas, [pt(cx, cy, 4, -28), pt(cx, cy, 4, -22)], sw)
    rrect(canvas, cx - 8, cy + 28, cx + 8, cy + 38, 2, max(4, sw - 1))
    line(canvas, [pt(cx, cy, 0, 22), pt(cx, cy, 0, 28)], sw)

def draw_watch_tourbillon(canvas, cx, cy, sw, seed=0):
    """44. Watch Tourbillon: Balance Wheel + 3-Spoke Cage + Hairspring Spiral."""
    circle(canvas, cx, cy, 40, sw)
    circle(canvas, cx, cy, 10, sw)
    for i in range(3):
        a = math.radians(i * 120 + 90)
        p_hub = pt(cx, cy, 10 * math.cos(a), 10 * math.sin(a))
        p_rim = pt(cx, cy, 40 * math.cos(a), 40 * math.sin(a))
        line(canvas, [p_hub, p_rim], sw)
        p_screw_out = pt(cx, cy, 44 * math.cos(a + 0.2), 44 * math.sin(a + 0.2))
        p_screw_in = pt(cx, cy, 36 * math.cos(a + 0.2), 36 * math.sin(a + 0.2))
        line(canvas, [p_screw_in, p_screw_out], sw)
    spiral_pts = []
    for deg in range(0, 720, 20):
        rad = math.radians(deg)
        r_sp = 12 + 14 * (deg / 720)
        sp_x = cx + r_sp * math.cos(rad)
        sp_y = cy + r_sp * math.sin(rad)
        spiral_pts.append((int(round(sp_x)), int(round(sp_y))))
    line(canvas, spiral_pts, max(3, sw - 2))

def draw_cathedral_rose_window(canvas, cx, cy, sw, seed=0):
    """45. Gothic Rose Window: 8 Lancet Arches + Trefoils + Outer Mullions."""
    circle(canvas, cx, cy, 42, sw)
    circle(canvas, cx, cy, 26, sw)
    circle(canvas, cx, cy, 10, sw)
    for i in range(8):
        a = math.radians(i * 45)
        line(canvas, [
            pt(cx, cy, 10 * math.cos(a), 10 * math.sin(a)),
            pt(cx, cy, 26 * math.cos(a), 26 * math.sin(a))
        ], sw)
        line(canvas, [
            pt(cx, cy, 26 * math.cos(a), 26 * math.sin(a)),
            pt(cx, cy, 42 * math.cos(a), 42 * math.sin(a))
        ], sw)
        a_mid = math.radians(i * 45 + 22.5)
        circle(canvas, cx + 34 * math.cos(a_mid), cy + 34 * math.sin(a_mid), 4, max(3, sw - 2))

def draw_biometric_fingerprint(canvas, cx, cy, sw, seed=0):
    """46. Biometric Fingerprint: Concentric Undulating Ridge Arcs with Clear Spacing."""
    arc(canvas, cx, cy + 4, 10, 180, 360, sw)
    line(canvas, [pt(cx, cy, -10, 4), pt(cx, cy, -10, 20)], sw)
    line(canvas, [pt(cx, cy, 10, 4), pt(cx, cy, 10, 20)], sw)
    for r_ridge in [20, 30, 40]:
        arc(canvas, cx, cy, r_ridge, 190, 350, sw)
        line(canvas, [pt(cx, cy, -r_ridge, 0), pt(cx, cy, -r_ridge, 24)], sw)
        line(canvas, [pt(cx, cy, r_ridge, 0), pt(cx, cy, r_ridge, 24)], sw)
    line(canvas, [pt(cx, cy, -30, 10), pt(cx, cy, -22, 24)], sw)

def draw_space_station_iss(canvas, cx, cy, sw, seed=0):
    """47. Space Station: Central Module + Truss Backbone + Solar Array Grids."""
    rrect(canvas, cx - 12, cy - 20, cx + 12, cy + 20, 4, sw)
    circle(canvas, cx, cy, 5, sw)
    line(canvas, [pt(cx, cy, -44, 0), pt(cx, cy, 44, 0)], sw)
    rrect(canvas, cx - 44, cy - 36, cx - 24, cy - 6, 2, max(4, sw - 1))
    rrect(canvas, cx - 44, cy + 6, cx - 24, cy + 36, 2, max(4, sw - 1))
    line(canvas, [pt(cx, cy, -34, -36), pt(cx, cy, -34, -6)], max(3, sw - 2))
    line(canvas, [pt(cx, cy, -34, 6), pt(cx, cy, -34, 36)], max(3, sw - 2))
    rrect(canvas, cx + 24, cy - 36, cx + 44, cy - 6, 2, max(4, sw - 1))
    rrect(canvas, cx + 24, cy + 6, cx + 44, cy + 36, 2, max(4, sw - 1))
    line(canvas, [pt(cx, cy, 34, -36), pt(cx, cy, 34, -6)], max(3, sw - 2))
    line(canvas, [pt(cx, cy, 34, 6), pt(cx, cy, 34, 36)], max(3, sw - 2))

def draw_bonsai_tree(canvas, cx, cy, sw, seed=0):
    """48. Bonsai Tree: Planter Pot + Gnarled Branching Trunk + Foliage Clouds."""
    pot_pts = [
        pt(cx, cy, -28, 26),
        pt(cx, cy, 28, 26),
        pt(cx, cy, 22, 42),
        pt(cx, cy, -22, 42),
    ]
    line(canvas, pot_pts, sw, closed=True)
    trunk = [
        pt(cx, cy, 0, 26),
        pt(cx, cy, -6, 12),
        pt(cx, cy, 4, -2),
        pt(cx, cy, 0, -18)
    ]
    line(canvas, trunk, sw + 1)
    line(canvas, [pt(cx, cy, -6, 12), pt(cx, cy, -22, 4)], sw)
    line(canvas, [pt(cx, cy, 4, -2), pt(cx, cy, 22, -10)], sw)
    line(canvas, [pt(cx, cy, 0, -18), pt(cx, cy, -14, -28)], sw)
    circle(canvas, cx - 24, cy + 2, 10, max(4, sw - 1))
    circle(canvas, cx + 24, cy - 12, 12, max(4, sw - 1))
    circle(canvas, cx - 12, cy - 32, 12, max(4, sw - 1))
    circle(canvas, cx + 6, cy - 30, 10, max(4, sw - 1))

def draw_astrolabe_celestial(canvas, cx, cy, sw, seed=0):
    """49. Astrolabe: Suspension Throne + Graduated Rim + Ecliptic + Alidade."""
    line(canvas, [pt(cx, cy, -12, -40), pt(cx, cy, 0, -46)], sw)
    line(canvas, [pt(cx, cy, 0, -46), pt(cx, cy, 12, -40)], sw)
    circle(canvas, cx, cy - 46, 5, sw)
    circle(canvas, cx, cy, 40, sw)
    circle(canvas, cx, cy, 34, sw)
    circle(canvas, cx + 6, cy - 6, 20, max(4, sw - 1))
    line(canvas, [pt(cx, cy, -38, 24), pt(cx, cy, 38, -24)], sw)
    circle(canvas, cx, cy, 4, sw)

def draw_steam_locomotive(canvas, cx, cy, sw, seed=0):
    """50. Steam Locomotive: Boiler + Cowcatcher + 3 Spoked Driving Wheels + Rods."""
    cab = [
        pt(cx, cy, -40, 14),
        pt(cx, cy, -40, -22),
        pt(cx, cy, -14, -22),
        pt(cx, cy, -14, -10),
        pt(cx, cy, 36, -10),
        pt(cx, cy, 36, 14),
    ]
    line(canvas, cab, sw, closed=True)
    line(canvas, [pt(cx, cy, 24, -10), pt(cx, cy, 24, -24)], sw)
    line(canvas, [pt(cx, cy, 20, -24), pt(cx, cy, 28, -24)], sw)
    arc(canvas, cx + 6, cy - 10, 6, 180, 360, sw)
    line(canvas, [pt(cx, cy, 36, 8), pt(cx, cy, 44, 20)], sw)
    line(canvas, [pt(cx, cy, 44, 20), pt(cx, cy, 32, 20)], sw)
    for wx in [-28, -2, 24]:
        circle(canvas, cx + wx, cy + 24, 10, sw)
        line(canvas, [pt(cx, cy, wx - 10, 24), pt(cx, cy, wx + 10, 24)], max(3, sw - 2))
        line(canvas, [pt(cx, cy, wx, 14), pt(cx, cy, wx, 34)], max(3, sw - 2))
    line(canvas, [pt(cx, cy, -28, 24), pt(cx, cy, 24, 24)], sw)

def draw_filigree_skeleton_key(canvas, cx, cy, sw, seed=0):
    """51. Filigree Skeleton Key: Quad-Cloverleaf Bow + Stepped Bit Wards."""
    circle(canvas, cx, cy - 32, 8, max(4, sw - 1))
    circle(canvas, cx - 10, cy - 24, 8, max(4, sw - 1))
    circle(canvas, cx + 10, cy - 24, 8, max(4, sw - 1))
    circle(canvas, cx, cy - 16, 8, max(4, sw - 1))
    circle(canvas, cx, cy - 8, 5, sw)
    circle(canvas, cx, cy - 2, 5, sw)
    line(canvas, [pt(cx, cy, 0, -8), pt(cx, cy, 0, 42)], sw)
    bit = [
        pt(cx, cy, 0, 18),
        pt(cx, cy, 22, 18),
        pt(cx, cy, 22, 26),
        pt(cx, cy, 12, 26),
        pt(cx, cy, 12, 32),
        pt(cx, cy, 22, 32),
        pt(cx, cy, 22, 40),
        pt(cx, cy, 0, 40),
    ]
    line(canvas, bit, sw)

def draw_heraldic_coat_of_arms(canvas, cx, cy, sw, seed=0):
    """52. Heraldic Coat of Arms: Shield + Quartering + Helmet Crest + Mantling."""
    shield = [
        pt(cx, cy, -26, -18),
        pt(cx, cy, 26, -18),
        pt(cx, cy, 26, 12),
        pt(cx, cy, 0, 38),
        pt(cx, cy, -26, 12),
    ]
    line(canvas, shield, sw, closed=True)
    line(canvas, [pt(cx, cy, 0, -18), pt(cx, cy, 0, 38)], sw)
    line(canvas, [pt(cx, cy, -26, 6), pt(cx, cy, 26, 6)], sw)
    arc(canvas, cx, cy - 24, 10, 180, 360, sw)
    line(canvas, [pt(cx, cy, -10, -24), pt(cx, cy, 10, -24)], sw)
    line(canvas, [pt(cx, cy, -4, -28), pt(cx, cy, 4, -28)], max(3, sw - 2))
    line(canvas, [pt(cx, cy, -26, -18), pt(cx, cy, -38, -12)], sw)
    line(canvas, [pt(cx, cy, -38, -12), pt(cx, cy, -32, 6)], sw)
    line(canvas, [pt(cx, cy, 26, -18), pt(cx, cy, 38, -12)], sw)
    line(canvas, [pt(cx, cy, 38, -12), pt(cx, cy, 32, 6)], sw)

def draw_audio_mixing_desk(canvas, cx, cy, sw, seed=0):
    """53. Audio Mixing Desk: 3 Channel Strips + Fader Tracks & Knobs + VU meters."""
    rrect(canvas, cx - 38, cy - 42, cx + 38, cy + 42, 4, sw)
    for col_i, col_x in enumerate([-22, 0, 22]):
        circle(canvas, cx + col_x, cy - 26, 6, sw)
        line(canvas, [pt(cx, cy, col_x, -32), pt(cx, cy, col_x, -26)], max(3, sw - 2))
        line(canvas, [pt(cx, cy, col_x, -10), pt(cx, cy, col_x, 30)], sw)
        knob_y = -4 + col_i * 12
        line(canvas, [pt(cx, cy, col_x - 8, knob_y), pt(cx, cy, col_x + 8, knob_y)], sw + 2)

def draw_geodesic_dome(canvas, cx, cy, sw, seed=0):
    """54. Geodesic Dome: Multi-Line Strut Network Meeting at 5-Way Apexes."""
    line(canvas, [pt(cx, cy, -42, 28), pt(cx, cy, 42, 28)], sw)
    dome_rim = [
        pt(cx, cy, -42, 28),
        pt(cx, cy, -38, 2),
        pt(cx, cy, -24, -22),
        pt(cx, cy, 0, -36),
        pt(cx, cy, 24, -22),
        pt(cx, cy, 38, 2),
        pt(cx, cy, 42, 28),
    ]
    line(canvas, dome_rim, sw)
    h_mid = pt(cx, cy, 0, -10)
    h_l = pt(cx, cy, -20, 10)
    h_r = pt(cx, cy, 20, 10)
    line(canvas, [dome_rim[3], h_mid], sw)
    line(canvas, [dome_rim[2], h_mid], sw)
    line(canvas, [dome_rim[4], h_mid], sw)
    line(canvas, [h_mid, h_l], sw)
    line(canvas, [h_mid, h_r], sw)
    line(canvas, [dome_rim[1], h_l], sw)
    line(canvas, [dome_rim[0], h_l], sw)
    line(canvas, [pt(cx, cy, 0, 28), h_l], sw)
    line(canvas, [pt(cx, cy, 0, 28), h_r], sw)
    line(canvas, [dome_rim[5], h_r], sw)
    line(canvas, [dome_rim[6], h_r], sw)

def draw_anatomical_heart(canvas, cx, cy, sw, seed=0):
    """55. Anatomical Heart: Aortic Arch + Carotid Branches + Vena Cava + Ventricles."""
    heart_body = [
        pt(cx, cy, -22, -8),
        pt(cx, cy, -28, 14),
        pt(cx, cy, 0, 42),
        pt(cx, cy, 24, 18),
        pt(cx, cy, 20, -8),
    ]
    line(canvas, heart_body, sw, closed=True)
    line(canvas, [pt(cx, cy, -4, -8), pt(cx, cy, 0, 42)], sw)
    arc(canvas, cx - 6, cy - 18, 14, 180, 360, sw)
    line(canvas, [pt(cx, cy, -20, -18), pt(cx, cy, -20, -8)], sw)
    for bx in [-14, -6, 2]:
        line(canvas, [pt(cx, cy, bx, -32), pt(cx, cy, bx, -44)], sw)
    line(canvas, [pt(cx, cy, 12, -8), pt(cx, cy, 12, -38)], sw)
    line(canvas, [pt(cx, cy, 20, -8), pt(cx, cy, 20, -38)], sw)
    line(canvas, [pt(cx, cy, 12, -38), pt(cx, cy, 20, -38)], sw)

def draw_isometric_engine_v6(canvas, cx, cy, sw, seed=0):
    """56. Isometric V6 Engine Block: 60-Degree Banks + Manifold Runners."""
    base = [
        pt(cx, cy, 0, 38),
        pt(cx, cy, 32, 22),
        pt(cx, cy, 32, 6),
        pt(cx, cy, 0, 22),
        pt(cx, cy, -32, 6),
        pt(cx, cy, -32, 22),
    ]
    line(canvas, base, sw, closed=True)
    line(canvas, [pt(cx, cy, 0, 22), pt(cx, cy, 0, -14)], sw)
    line(canvas, [pt(cx, cy, -32, 6), pt(cx, cy, -22, -26)], sw)
    line(canvas, [pt(cx, cy, -22, -26), pt(cx, cy, 0, -14)], sw)
    line(canvas, [pt(cx, cy, 32, 6), pt(cx, cy, 22, -26)], sw)
    line(canvas, [pt(cx, cy, 22, -26), pt(cx, cy, 0, -14)], sw)
    for rx in [-12, 0, 12]:
        arc(canvas, cx + rx, cy - 28, 6, 180, 360, sw)

MORE_COMPLEX_DRAWERS = [
    draw_pen_nib_sparkle, draw_smart_keypad_rfid, draw_inbox_arrow_v_notch, draw_dome_corner_junction,
    draw_mandala_rosette, draw_guilloche_security, draw_bga_microcontroller, draw_watch_tourbillon,
    draw_cathedral_rose_window, draw_biometric_fingerprint, draw_space_station_iss, draw_bonsai_tree,
    draw_astrolabe_celestial, draw_steam_locomotive, draw_filigree_skeleton_key, draw_heraldic_coat_of_arms,
    draw_audio_mixing_desk, draw_geodesic_dome, draw_anatomical_heart, draw_isometric_engine_v6
]
