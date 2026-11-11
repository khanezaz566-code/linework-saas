"""Generator for 36-icon heavy-join presentation sheets.
Each sheet contains 36 complex icons (6x6 grid) packed with intricate joins:
multi-line crossings, T-junctions, radial hubs, concentric ring spokes,
circuit busses, diamond lattices, mechanical gears, and interlocking knots.
Supports seed/sheet_idx parameterization to generate 100 distinct sheets.
"""
from __future__ import annotations
import math
from pathlib import Path
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

# ----------------- 36 Heavy Join Icon Drawers ----------------- #

def draw_chip_qfp(canvas, cx, cy, sw, seed=0):
    """1. QFP Chip: Central body with 16 pins meeting package at T-junctions."""
    rrect(canvas, cx - 28, cy - 28, cx + 28, cy + 28, 6, sw)
    circle(canvas, cx - 18, cy - 18, 4, sw)
    # 4 pins on each side
    pins = [-18, -6, 6, 18]
    for p in pins:
        # Top & Bottom
        line(canvas, [pt(cx, cy, p, -28), pt(cx, cy, p, -42)], sw)
        line(canvas, [pt(cx, cy, p, 28), pt(cx, cy, p, 42)], sw)
        # Left & Right
        line(canvas, [pt(cx, cy, -28, p), pt(cx, cy, -42, p)], sw)
        line(canvas, [pt(cx, cy, 28, p), pt(cx, cy, 42, p)], sw)

def draw_ship_helm(canvas, cx, cy, sw, seed=0):
    """2. Ship Helm: Outer wheel + hub + 8 spokes extending as handles."""
    circle(canvas, cx, cy, 32, sw)
    circle(canvas, cx, cy, 14, sw)
    circle(canvas, cx, cy, 5, sw)
    rot = (seed * 7) % 45
    for a_deg in range(rot, rot + 360, 45):
        rad = math.radians(a_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        p_hub = pt(cx, cy, 14 * cos_a, 14 * sin_a)
        p_rim = pt(cx, cy, 32 * cos_a, 32 * sin_a)
        p_tip = pt(cx, cy, 45 * cos_a, 45 * sin_a)
        line(canvas, [p_hub, p_rim], sw)
        line(canvas, [p_rim, p_tip], sw)

def draw_compass_rose(canvas, cx, cy, sw, seed=0):
    """3. Compass Rose: 8-point faceted star with acute apexes and internal cross joins."""
    rot = (seed * 11) % 45
    pts_outer = []
    for i in range(8):
        a = math.radians(rot + i * 45)
        pts_outer.append(pt(cx, cy, 44 * math.cos(a), 44 * math.sin(a)))
    pts_inner = []
    for i in range(8):
        a = math.radians(rot + 22.5 + i * 45)
        pts_inner.append(pt(cx, cy, 20 * math.cos(a), 20 * math.sin(a)))
    # Interleave star points
    star = []
    for i in range(8):
        star.append(pts_outer[i])
        star.append(pts_inner[i])
    line(canvas, star, sw, closed=True)
    # Crosslines uniting at center ring
    circle(canvas, cx, cy, 7, sw)
    for i in range(4):
        a_inner = math.radians(rot + 22.5 + i * 45)
        line(canvas, [pts_inner[i], pt(cx, cy, 7 * math.cos(a_inner), 7 * math.sin(a_inner))], sw)
        a_opp = math.radians(rot + 22.5 + (i + 4) * 45)
        line(canvas, [pts_inner[i + 4], pt(cx, cy, 7 * math.cos(a_opp), 7 * math.sin(a_opp))], sw)

def draw_pcb_schematic(canvas, cx, cy, sw, seed=0):
    """4. PCB Schematic: Orthogonal bus lines with T-taps, vias, and cross-overs."""
    # Main bus lines
    line(canvas, [pt(cx, cy, -42, -20), pt(cx, cy, 42, -20)], sw)
    line(canvas, [pt(cx, cy, -42, 20), pt(cx, cy, 42, 20)], sw)
    line(canvas, [pt(cx, cy, -20, -42), pt(cx, cy, -20, 42)], sw)
    line(canvas, [pt(cx, cy, 20, -42), pt(cx, cy, 20, 42)], sw)
    # Diagonal tap and vias
    circle(canvas, cx - 20, cy - 20, 5, sw)
    circle(canvas, cx + 20, cy + 20, 5, sw)
    line(canvas, [pt(cx, cy, 0, -20), pt(cx, cy, 0, 0), pt(cx, cy, 20, 0)], sw)
    circle(canvas, cx, cy, 4, sw)

def draw_radar_crosshair(canvas, cx, cy, sw, seed=0):
    """5. Radar Scope: 3 concentric circles + full crosshairs with tick marks."""
    circle(canvas, cx, cy, 44, sw)
    circle(canvas, cx, cy, 28, sw)
    circle(canvas, cx, cy, 12, sw)
    line(canvas, [pt(cx, cy, -48, 0), pt(cx, cy, 48, 0)], sw)
    line(canvas, [pt(cx, cy, 0, -48), pt(cx, cy, 0, 48)], sw)
    # Ticks on crosshair
    for off in [-28, -12, 12, 28]:
        line(canvas, [pt(cx, cy, off, -4), pt(cx, cy, off, 4)], sw)
        line(canvas, [pt(cx, cy, -4, off), pt(cx, cy, 4, off)], sw)

def draw_wire_mesh_cart(canvas, cx, cy, sw, seed=0):
    """6. Shopping Cart Basket: Wireframe grid with multiple 4-way X-junctions."""
    # Outer basket trapezoid
    line(canvas, [pt(cx, cy, -38, -25), pt(cx, cy, 38, -25), pt(cx, cy, 26, 18), pt(cx, cy, -30, 18)], sw, closed=True)
    # Handle & chassis
    line(canvas, [pt(cx, cy, -45, -34), pt(cx, cy, -38, -25)], sw)
    line(canvas, [pt(cx, cy, -30, 18), pt(cx, cy, -30, 28), pt(cx, cy, 28, 28)], sw)
    # Caster wheels
    circle(canvas, cx - 24, cy + 36, 7, sw)
    circle(canvas, cx + 20, cy + 36, 7, sw)
    # Grid lines inside basket
    line(canvas, [pt(cx, cy, -15, -25), pt(cx, cy, -12, 18)], sw)
    line(canvas, [pt(cx, cy, 10, -25), pt(cx, cy, 8, 18)], sw)
    line(canvas, [pt(cx, cy, -34, -4), pt(cx, cy, 32, -4)], sw)
    line(canvas, [pt(cx, cy, -32, 7), pt(cx, cy, 29, 7)], sw)

def draw_bicycle_frame(canvas, cx, cy, sw, seed=0):
    """7. Bicycle Frame: Triangular tube truss meeting spoked wheels."""
    # Wheels
    circle(canvas, cx - 28, cy + 18, 16, sw)
    circle(canvas, cx + 28, cy + 18, 16, sw)
    # Bottom bracket, seat node, head tube node
    p_rear = pt(cx, cy, -28, 18)
    p_front = pt(cx, cy, 28, 18)
    p_bb = pt(cx, cy, -4, 18)
    p_seat = pt(cx, cy, -12, -10)
    p_head = pt(cx, cy, 20, -14)
    # Frame tubes
    line(canvas, [p_rear, p_bb, p_seat, p_rear], sw, closed=True)  # rear triangle
    line(canvas, [p_bb, p_head, p_seat], sw)  # main triangle
    line(canvas, [p_head, p_front], sw)  # fork
    # Handlebar & seat post
    line(canvas, [p_head, pt(cx, cy, 18, -26), pt(cx, cy, 10, -26)], sw)
    line(canvas, [p_seat, pt(cx, cy, -14, -18), pt(cx, cy, -7, -18)], sw)

def draw_spider_web(canvas, cx, cy, sw, seed=0):
    """8. Spider Web: 8 radial spokes crossed by 3 concentric polygon rings."""
    rot = (seed * 5) % 45
    # Center hub ring
    circle(canvas, cx, cy, 8, sw)
    for i in range(8):
        a = math.radians(rot + i * 45)
        p_hub = pt(cx, cy, 8 * math.cos(a), 8 * math.sin(a))
        p_spoke = pt(cx, cy, 45 * math.cos(a), 45 * math.sin(a))
        line(canvas, [p_hub, p_spoke], sw)
    for r in [20, 32, 44]:
        ring_pts = []
        for i in range(8):
            a = math.radians(rot + i * 45)
            ring_pts.append(pt(cx, cy, r * math.cos(a), r * math.sin(a)))
        line(canvas, ring_pts, sw, closed=True)

def draw_anchor_heavy(canvas, cx, cy, sw, seed=0):
    """9. Nautical Anchor: Eye ring + stock crossbar + shank + curved arms & triangular flukes."""
    circle(canvas, cx, cy - 32, 10, sw)
    line(canvas, [pt(cx, cy, -32, -22), pt(cx, cy, 32, -22)], sw)  # stock
    line(canvas, [pt(cx, cy, 0, -22), pt(cx, cy, 0, 36)], sw)  # shank
    arc(canvas, cx, cy + 18, 32, 20, 160, sw)  # curved arms
    # Triangular flukes at ends of arms
    line(canvas, [pt(cx, cy, -30, 29), pt(cx, cy, -40, 16), pt(cx, cy, -22, 18)], sw, closed=True)
    line(canvas, [pt(cx, cy, 30, 29), pt(cx, cy, 40, 16), pt(cx, cy, 22, 18)], sw, closed=True)

def draw_dial_padlock(canvas, cx, cy, sw, seed=0):
    """10. Dial Padlock: Arch shackle + slotted body with 3 rotary wheels and center notch."""
    rrect(canvas, cx - 32, cy - 8, cx + 32, cy + 42, 8, sw)
    arc(canvas, cx, cy - 8, 20, 180, 360, sw)
    line(canvas, [pt(cx, cy, -20, -8), pt(cx, cy, -20, 0)], sw)
    line(canvas, [pt(cx, cy, 20, -8), pt(cx, cy, 20, 0)], sw)
    # 3 horizontal dial bars
    for y_off in [6, 17, 28]:
        line(canvas, [pt(cx, cy, -22, y_off), pt(cx, cy, 22, y_off)], sw)
        line(canvas, [pt(cx, cy, -8, y_off - 4), pt(cx, cy, -8, y_off + 4)], sw)
        line(canvas, [pt(cx, cy, 8, y_off - 4), pt(cx, cy, 8, y_off + 4)], sw)

def draw_scissors_shears(canvas, cx, cy, sw, seed=0):
    """11. Scissors: Crossed blades, pivot rivet, and finger loops."""
    # Pivot rivet
    circle(canvas, cx, cy - 5, 5, sw)
    # Left blade & handle
    line(canvas, [pt(cx, cy, -14, -42), pt(cx, cy, 0, -5), pt(cx, cy, 14, 22)], sw)
    circle(canvas, cx + 18, cy + 30, 9, sw)
    # Right blade & handle
    line(canvas, [pt(cx, cy, 14, -42), pt(cx, cy, 0, -5), pt(cx, cy, -14, 22)], sw)
    circle(canvas, cx - 18, cy + 30, 9, sw)

def draw_interlocking_gears(canvas, cx, cy, sw, seed=0):
    """12. Interlocking Gears: Two cogs with teeth profiles touching at pitch point."""
    # Upper left gear (r=22)
    c1x, c1y = cx - 18, cy - 16
    circle(canvas, c1x, c1y, 18, sw)
    circle(canvas, c1x, c1y, 6, sw)
    for a in range(0, 360, 60):
        rad = math.radians(a + seed * 10)
        p0 = pt(c1x, c1y, 18 * math.cos(rad), 18 * math.sin(rad))
        p1 = pt(c1x, c1y, 27 * math.cos(rad), 27 * math.sin(rad))
        line(canvas, [p0, p1], sw)
    # Lower right gear (r=22)
    c2x, c2y = cx + 18, cy + 18
    circle(canvas, c2x, c2y, 18, sw)
    circle(canvas, c2x, c2y, 6, sw)
    for a in range(30, 390, 60):
        rad = math.radians(a + seed * 10)
        p0 = pt(c2x, c2y, 18 * math.cos(rad), 18 * math.sin(rad))
        p1 = pt(c2x, c2y, 27 * math.cos(rad), 27 * math.sin(rad))
        line(canvas, [p0, p1], sw)

def draw_benzene_molecule(canvas, cx, cy, sw, seed=0):
    """13. Benzene & Functional Branches: Hexagon ring + inner alternating bonds + 3 branches."""
    hex_pts = []
    for i in range(6):
        a = math.radians(30 + i * 60)
        hex_pts.append(pt(cx, cy, 36 * math.cos(a), 36 * math.sin(a)))
    line(canvas, hex_pts, sw, closed=True)
    # 3 inner double bonds
    for i in [0, 2, 4]:
        a0 = math.radians(30 + i * 60)
        a1 = math.radians(30 + (i + 1) * 60)
        p0 = pt(cx, cy, 22 * math.cos(a0), 22 * math.sin(a0))
        p1 = pt(cx, cy, 22 * math.cos(a1), 22 * math.sin(a1))
        line(canvas, [p0, p1], sw)
    # Branching groups
    line(canvas, [hex_pts[0], pt(cx, cy, 48 * math.cos(math.radians(30)), 48 * math.sin(math.radians(30)))], sw)
    line(canvas, [hex_pts[2], pt(cx, cy, 48 * math.cos(math.radians(150)), 48 * math.sin(math.radians(150)))], sw)
    line(canvas, [hex_pts[4], pt(cx, cy, 48 * math.cos(math.radians(270)), 48 * math.sin(math.radians(270)))], sw)

def draw_flowchart_tree(canvas, cx, cy, sw, seed=0):
    """14. Decision Flowchart: Diamond decision node branching to boxes via orthogonal elbows."""
    # Diamond at top
    line(canvas, [pt(cx, cy, 0, -36), pt(cx, cy, 24, -20), pt(cx, cy, 0, -4), pt(cx, cy, -24, -20)], sw, closed=True)
    # Down stem to center box
    line(canvas, [pt(cx, cy, 0, -4), pt(cx, cy, 0, 16)], sw)
    rrect(canvas, cx - 18, cy + 16, cx + 18, cy + 38, 4, sw)
    # Right branch with elbow
    line(canvas, [pt(cx, cy, 24, -20), pt(cx, cy, 38, -20), pt(cx, cy, 38, 16)], sw)
    circle(canvas, cx + 38, cy + 24, 8, sw)
    # Left branch with elbow
    line(canvas, [pt(cx, cy, -24, -20), pt(cx, cy, -38, -20), pt(cx, cy, -38, 16)], sw)
    circle(canvas, cx - 38, cy + 24, 8, sw)

def draw_audio_equalizer(canvas, cx, cy, sw, seed=0):
    """15. Audio Equalizer: 5 vertical meter columns with cross ticks and peak caps."""
    cols = [-32, -16, 0, 16, 32]
    heights = [18, 36, 42, 28, 22]
    for idx, (x_col, h) in enumerate(zip(cols, heights)):
        line(canvas, [pt(cx, cy, x_col, 36), pt(cx, cy, x_col, 36 - h)], sw)
        # Ticks along the column
        for y_tick in range(36 - h, 36, 10):
            line(canvas, [pt(cx, cy, x_col - 5, y_tick), pt(cx, cy, x_col + 5, y_tick)], sw)
        # Peak cap
        line(canvas, [pt(cx, cy, x_col - 6, 36 - h - 6), pt(cx, cy, x_col + 6, 36 - h - 6)], sw)
    line(canvas, [pt(cx, cy, -42, 36), pt(cx, cy, 42, 36)], sw)  # baseline

def draw_floorplan_partition(canvas, cx, cy, sw, seed=0):
    """16. Architectural Floorplan: Perimeter walls, T-partitions, and door swing arc."""
    # Outer rectangle
    rrect(canvas, cx - 40, cy - 35, cx + 40, cy + 35, 4, sw)
    # Internal dividing wall (T-junctions)
    line(canvas, [pt(cx, cy, -40, 5), pt(cx, cy, 10, 5)], sw)
    line(canvas, [pt(cx, cy, 10, -35), pt(cx, cy, 10, 35)], sw)
    # Door swing arc meeting door jamb
    line(canvas, [pt(cx, cy, 10, 5), pt(cx, cy, 24, 19)], sw)
    arc(canvas, cx + 10, cy + 5, 20, 0, 45, sw)

def draw_camera_prism(canvas, cx, cy, sw, seed=0):
    """17. SLR Camera: Body + pentaprism top + concentric lens rings + shutter stem."""
    rrect(canvas, cx - 42, cy - 14, cx + 42, cy + 34, 6, sw)
    # Pentaprism apex
    line(canvas, [pt(cx, cy, -22, -14), pt(cx, cy, -14, -34), pt(cx, cy, 14, -34), pt(cx, cy, 22, -14)], sw)
    # Concentric lens
    circle(canvas, cx, cy + 10, 20, sw)
    circle(canvas, cx, cy + 10, 9, sw)
    # Shutter button & flash mount
    line(canvas, [pt(cx, cy, -32, -14), pt(cx, cy, -32, -22), pt(cx, cy, -24, -22)], sw)
    line(canvas, [pt(cx, cy, 0, -34), pt(cx, cy, 0, -40)], sw)

def draw_drone_quadcopter(canvas, cx, cy, sw, seed=0):
    """18. Quadcopter Drone: Center fuselage + 4 diagonal arms + 4 rotor rings."""
    circle(canvas, cx, cy, 12, sw)
    # 4 diagonal arms
    dirs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for dx, dy in dirs:
        p_hub = pt(cx, cy, dx * 10, dy * 10)
        p_motor = pt(cx, cy, dx * 28, dy * 28)
        line(canvas, [p_hub, p_motor], sw)
        circle(canvas, cx + dx * 28, cy + dy * 28, 11, sw)

def draw_hourglass_caged(canvas, cx, cy, sw, seed=0):
    """19. Hourglass: Top/bottom plates + 3 vertical frame bars + pinched waist glass."""
    # Top & bottom plates
    line(canvas, [pt(cx, cy, -34, -36), pt(cx, cy, 34, -36)], sw)
    line(canvas, [pt(cx, cy, -34, 36), pt(cx, cy, 34, 36)], sw)
    # Side support bars
    line(canvas, [pt(cx, cy, -30, -36), pt(cx, cy, -30, 36)], sw)
    line(canvas, [pt(cx, cy, 30, -36), pt(cx, cy, 30, 36)], sw)
    # Pinched hourglass bulb
    line(canvas, [pt(cx, cy, -20, -32), pt(cx, cy, -3, 0), pt(cx, cy, -20, 32)], sw)
    line(canvas, [pt(cx, cy, 20, -32), pt(cx, cy, 3, 0), pt(cx, cy, 20, 32)], sw)
    line(canvas, [pt(cx, cy, -20, -32), pt(cx, cy, 20, -32)], sw)
    line(canvas, [pt(cx, cy, -20, 32), pt(cx, cy, 20, 32)], sw)

def draw_telescope_tripod(canvas, cx, cy, sw, seed=0):
    """20. Telescope on Tripod: Angled optical barrel, finder scope, mount hub, 3 splayed legs."""
    # Barrel (angled at 30 deg)
    p0 = pt(cx, cy, -30, 10)
    p1 = pt(cx, cy, 35, -28)
    line(canvas, [p0, p1], sw)
    line(canvas, [pt(cx, cy, -28, 14), pt(cx, cy, 37, -24)], sw)
    line(canvas, [p0, pt(cx, cy, -28, 14)], sw)
    line(canvas, [p1, pt(cx, cy, 37, -24)], sw)
    # Finder scope mounted on barrel
    line(canvas, [pt(cx, cy, 5, -24), pt(cx, cy, 30, -38)], sw)
    # Tripod mount hub
    circle(canvas, cx - 2, cy + 2, 5, sw)
    # 3 splayed legs meeting at hub
    line(canvas, [pt(cx, cy, -2, 7), pt(cx, cy, -32, 40)], sw)
    line(canvas, [pt(cx, cy, -2, 7), pt(cx, cy, -2, 42)], sw)
    line(canvas, [pt(cx, cy, -2, 7), pt(cx, cy, 28, 40)], sw)
    # Spreader strut
    line(canvas, [pt(cx, cy, -18, 26), pt(cx, cy, 16, 26)], sw)

def draw_lightbulb_threads(canvas, cx, cy, sw, seed=0):
    """21. Lightbulb: Pear bulb outline + filament posts + screw base zigzag + contact foot."""
    # Bulb outline
    arc(canvas, cx, cy - 14, 26, 140, 400, sw)
    line(canvas, [pt(cx, cy, -17, 6), pt(cx, cy, -14, 20)], sw)
    line(canvas, [pt(cx, cy, 17, 6), pt(cx, cy, 14, 20)], sw)
    # Filament leads & loop
    line(canvas, [pt(cx, cy, -8, 20), pt(cx, cy, -8, -6), pt(cx, cy, 0, -18), pt(cx, cy, 8, -6), pt(cx, cy, 8, 20)], sw)
    # Screw threads
    line(canvas, [pt(cx, cy, -14, 20), pt(cx, cy, 14, 20)], sw)
    line(canvas, [pt(cx, cy, -12, 27), pt(cx, cy, 12, 27)], sw)
    line(canvas, [pt(cx, cy, -10, 34), pt(cx, cy, 10, 34)], sw)
    arc(canvas, cx, cy + 34, 6, 0, 180, sw)

def draw_dna_helix(canvas, cx, cy, sw, seed=0):
    """22. DNA Double Helix: Intersecting sinusoidal strands connected by horizontal base rungs."""
    pts1, pts2 = [], []
    for y in range(-38, 42, 4):
        x1 = int(round(18 * math.sin(math.radians((y + 38) * 4.5))))
        x2 = -x1
        pts1.append(pt(cx, cy, x1, y))
        pts2.append(pt(cx, cy, x2, y))
    line(canvas, pts1, sw)
    line(canvas, pts2, sw)
    # Horizontal rungs connecting the two strands
    for y_rung in range(-32, 36, 12):
        x_rung = int(round(18 * math.sin(math.radians((y_rung + 38) * 4.5))))
        line(canvas, [pt(cx, cy, -abs(x_rung), y_rung), pt(cx, cy, abs(x_rung), y_rung)], sw)

def draw_warded_key(canvas, cx, cy, sw, seed=0):
    """23. Warded Skeleton Key: Bow ring + collar + shaft + stepped bit teeth."""
    circle(canvas, cx - 22, cy, 16, sw)
    circle(canvas, cx - 22, cy, 6, sw)
    # Shaft
    line(canvas, [pt(cx, cy, -6, 0), pt(cx, cy, 40, 0)], sw)
    # Collar ring
    line(canvas, [pt(cx, cy, 2, -7), pt(cx, cy, 2, 7)], sw)
    # Stepped bit with notches
    bit = [pt(cx, cy, 26, 0), pt(cx, cy, 26, 20), pt(cx, cy, 33, 20), pt(cx, cy, 33, 11), pt(cx, cy, 40, 11), pt(cx, cy, 40, 0)]
    line(canvas, bit, sw)

def draw_musical_staff_clef(canvas, cx, cy, sw, seed=0):
    """24. Musical Staff & Treble Clef: 5 parallel staff lines intersected by clef curves."""
    # 5 staff lines
    for y_off in [-24, -12, 0, 12, 24]:
        line(canvas, [pt(cx, cy, -40, y_off), pt(cx, cy, 40, y_off)], sw)
    # Treble clef vertical spine & loops
    line(canvas, [pt(cx, cy, 0, -36), pt(cx, cy, 0, 34)], sw)
    arc(canvas, cx, cy + 34, 6, 0, 180, sw)  # bottom hook
    arc(canvas, cx, cy - 18, 10, 180, 360, sw)  # top loop
    arc(canvas, cx, cy + 6, 14, 0, 360, sw)  # center spiral

def draw_heraldic_shield(canvas, cx, cy, sw, seed=0):
    """25. Heraldic Shield: Pointed shield body + quartered cross lines + diagonal sash."""
    line(canvas, [pt(cx, cy, -35, -34), pt(cx, cy, 35, -34), pt(cx, cy, 35, 6), pt(cx, cy, 0, 42), pt(cx, cy, -35, 6)], sw, closed=True)
    # Quartering cross
    line(canvas, [pt(cx, cy, -35, 0), pt(cx, cy, 35, 0)], sw)
    line(canvas, [pt(cx, cy, 0, -34), pt(cx, cy, 0, 42)], sw)
    # Diagonal sash
    line(canvas, [pt(cx, cy, -35, -20), pt(cx, cy, 20, 35)], sw)

def draw_wind_turbine(canvas, cx, cy, sw, seed=0):
    """26. Wind Turbine: Nacelle hub + 3 aerodynamic blades + tapered tower mast."""
    circle(canvas, cx, cy - 10, 8, sw)
    rot = (seed * 17) % 120
    # 3 blades at 120 deg
    for i in range(3):
        a = math.radians(rot - 90 + i * 120)
        p_hub = pt(cx, cy - 10, 8 * math.cos(a), 8 * math.sin(a))
        p_tip = pt(cx, cy - 10, 44 * math.cos(a), 44 * math.sin(a))
        line(canvas, [p_hub, p_tip], sw)
    # Tower mast
    line(canvas, [pt(cx, cy, -5, -2), pt(cx, cy, -14, 42)], sw)
    line(canvas, [pt(cx, cy, 5, -2), pt(cx, cy, 14, 42)], sw)
    line(canvas, [pt(cx, cy, -22, 42), pt(cx, cy, 22, 42)], sw)

def draw_ribbed_umbrella(canvas, cx, cy, sw, seed=0):
    """27. Ribbed Umbrella: Canopy arches + 5 ribs meeting ferrule + shaft + J-handle."""
    # Canopy top arc
    arc(canvas, cx, cy - 10, 36, 180, 360, sw)
    # Scalloped bottom arcs
    scallops = [-36, -18, 0, 18, 36]
    for i in range(len(scallops) - 1):
        x_mid = (scallops[i] + scallops[i + 1]) / 2.0
        arc(canvas, cx + x_mid, cy - 10, 9, 0, 180, sw)
    # Ferrule tip & shaft
    line(canvas, [pt(cx, cy, 0, -46), pt(cx, cy, 0, 30)], sw)
    # J-handle hook
    arc(canvas, cx - 8, cy + 30, 8, 0, 180, sw)

def draw_spanner_wrench(canvas, cx, cy, sw, seed=0):
    """28. Dual Wrench: Open U-jaw head + shaft + 12-point ring head."""
    # Open jaw at left
    line(canvas, [pt(cx, cy, -38, -12), pt(cx, cy, -22, -12), pt(cx, cy, -22, 12), pt(cx, cy, -38, 12)], sw)
    arc(canvas, cx - 22, cy, 18, 90, 270, sw)
    # Central shaft
    line(canvas, [pt(cx, cy, -4, -7), pt(cx, cy, 20, -7)], sw)
    line(canvas, [pt(cx, cy, -4, 7), pt(cx, cy, 20, 7)], sw)
    # Ring head at right
    circle(canvas, cx + 28, cy, 16, sw)
    circle(canvas, cx + 28, cy, 8, sw)

def draw_subway_interchange(canvas, cx, cy, sw, seed=0):
    """29. Transit Subway Map: Central interchange ring + 4 crossing colored lines."""
    circle(canvas, cx, cy, 14, sw)
    # 4 transit lines terminating or passing through ring
    line(canvas, [pt(cx, cy, -42, 0), pt(cx, cy, -14, 0)], sw)
    line(canvas, [pt(cx, cy, 14, 0), pt(cx, cy, 42, 0)], sw)
    line(canvas, [pt(cx, cy, 0, -42), pt(cx, cy, 0, -14)], sw)
    line(canvas, [pt(cx, cy, 0, 14), pt(cx, cy, 0, 42)], sw)
    # Diagonal branch with station tick
    line(canvas, [pt(cx, cy, 10, 10), pt(cx, cy, 38, 38)], sw)
    line(canvas, [pt(cx, cy, 28, 24), pt(cx, cy, 24, 28)], sw)

def draw_crown_fleur(canvas, cx, cy, sw, seed=0):
    """30. Royal Crown: Base band with jewels + 5 peaked spikes with cross finials."""
    rrect(canvas, cx - 38, cy + 18, cx + 38, cy + 32, 4, sw)
    for x_j in [-24, 0, 24]:
        circle(canvas, cx + x_j, cy + 25, 3, sw)
    # 5 peaked points
    pts_peaks = [pt(cx, cy, -38, 18), pt(cx, cy, -32, -12), pt(cx, cy, -18, 8), pt(cx, cy, 0, -22), pt(cx, cy, 18, 8), pt(cx, cy, 32, -12), pt(cx, cy, 38, 18)]
    line(canvas, pts_peaks, sw)
    # Cross finial on central peak
    line(canvas, [pt(cx, cy, 0, -22), pt(cx, cy, 0, -36)], sw)
    line(canvas, [pt(cx, cy, -6, -30), pt(cx, cy, 6, -30)], sw)

def draw_isometric_cube(canvas, cx, cy, sw, seed=0):
    """31. Isometric 3D Cube: Outer hexagon + center Y-junction + internal struts."""
    pts_hex = []
    for i in range(6):
        a = math.radians(30 + i * 60)
        pts_hex.append(pt(cx, cy, 38 * math.cos(a), 38 * math.sin(a)))
    line(canvas, pts_hex, sw, closed=True)
    # 3 internal edges meeting at center (Y-junction)
    line(canvas, [pt(cx, cy, 0, 0), pts_hex[1]], sw)
    line(canvas, [pt(cx, cy, 0, 0), pts_hex[3]], sw)
    line(canvas, [pt(cx, cy, 0, 0), pts_hex[5]], sw)

def draw_dial_gauge(canvas, cx, cy, sw, seed=0):
    """32. Pressure Gauge: Circular bezel + 10 radial dial ticks + needle pointer."""
    circle(canvas, cx, cy, 40, sw)
    # Dial ticks
    for a in range(210, 510, 30):
        rad = math.radians(a)
        p0 = pt(cx, cy, 28 * math.cos(rad), 28 * math.sin(rad))
        p1 = pt(cx, cy, 40 * math.cos(rad), 40 * math.sin(rad))
        line(canvas, [p0, p1], sw)
    # Center pivot & needle
    circle(canvas, cx, cy, 7, sw)
    rot_needle = math.radians(255 + (seed * 60) % 180)
    line(canvas, [pt(cx, cy, 0, 0), pt(cx, cy, 22 * math.cos(rot_needle), 22 * math.sin(rot_needle))], sw)

def draw_racket_grid(canvas, cx, cy, sw, seed=0):
    """33. Racket String Grid: Oval head + handle shaft + tight orthogonal string grid."""
    arc(canvas, cx, cy - 10, 30, 0, 360, sw)
    # Handle shaft & grip
    line(canvas, [pt(cx, cy, -4, 20), pt(cx, cy, -4, 44), pt(cx, cy, 4, 44), pt(cx, cy, 4, 20)], sw)
    # String grid (4 vertical, 4 horizontal)
    for x_s in [-16, -6, 6, 16]:
        line(canvas, [pt(cx, cy, x_s, -32), pt(cx, cy, x_s, 14)], sw)
    for y_s in [-24, -14, -4, 6]:
        line(canvas, [pt(cx, cy, -22, y_s), pt(cx, cy, 22, y_s)], sw)

def draw_car_steering(canvas, cx, cy, sw, seed=0):
    """34. Car Steering Wheel: Outer rim + 3 wide hub spokes with center airbag."""
    circle(canvas, cx, cy, 40, sw)
    circle(canvas, cx, cy, 14, sw)
    # Left spoke (dual lines)
    line(canvas, [pt(cx, cy, -40, -4), pt(cx, cy, -14, -4)], sw)
    line(canvas, [pt(cx, cy, -40, 8), pt(cx, cy, -14, 8)], sw)
    # Right spoke (dual lines)
    line(canvas, [pt(cx, cy, 14, -4), pt(cx, cy, 40, -4)], sw)
    line(canvas, [pt(cx, cy, 14, 8), pt(cx, cy, 40, 8)], sw)
    # Bottom spoke
    line(canvas, [pt(cx, cy, -5, 14), pt(cx, cy, -5, 40)], sw)
    line(canvas, [pt(cx, cy, 5, 14), pt(cx, cy, 5, 40)], sw)

def draw_celtic_knot(canvas, cx, cy, sw, seed=0):
    """35. Celtic Triquetra Knot: 3 interlacing vesica arcs overlapping at shared vertices."""
    # 3 arcs centered around a triangle
    r = 24
    for i in range(3):
        a = math.radians(i * 120 - 90)
        c_arc_x = cx + 14 * math.cos(a)
        c_arc_y = cy + 14 * math.sin(a)
        circle(canvas, c_arc_x, c_arc_y, r, sw)
    circle(canvas, cx, cy, 20, sw)

def draw_scaffolding_tower(canvas, cx, cy, sw, seed=0):
    """36. Scaffolding / Truss Tower: 2 vertical stiles + 5 horizontal rungs + 4 diagonal X-braces."""
    line(canvas, [pt(cx, cy, -28, -42), pt(cx, cy, -28, 42)], sw)
    line(canvas, [pt(cx, cy, 28, -42), pt(cx, cy, 28, 42)], sw)
    # 5 rungs
    y_rungs = [-40, -20, 0, 20, 40]
    for yr in y_rungs:
        line(canvas, [pt(cx, cy, -28, yr), pt(cx, cy, 28, yr)], sw)
    # X-braces between tiers
    line(canvas, [pt(cx, cy, -28, -40), pt(cx, cy, 28, -20)], sw)
    line(canvas, [pt(cx, cy, 28, -40), pt(cx, cy, -28, -20)], sw)
    line(canvas, [pt(cx, cy, -28, 0), pt(cx, cy, 28, 20)], sw)
    line(canvas, [pt(cx, cy, 28, 0), pt(cx, cy, -28, 20)], sw)

HEAVY_JOIN_DRAWERS = [
    draw_chip_qfp, draw_ship_helm, draw_compass_rose, draw_pcb_schematic,
    draw_radar_crosshair, draw_wire_mesh_cart, draw_bicycle_frame, draw_spider_web,
    draw_anchor_heavy, draw_dial_padlock, draw_scissors_shears, draw_interlocking_gears,
    draw_benzene_molecule, draw_flowchart_tree, draw_audio_equalizer, draw_floorplan_partition,
    draw_camera_prism, draw_drone_quadcopter, draw_hourglass_caged, draw_telescope_tripod,
    draw_lightbulb_threads, draw_dna_helix, draw_warded_key, draw_musical_staff_clef,
    draw_heraldic_shield, draw_wind_turbine, draw_ribbed_umbrella, draw_spanner_wrench,
    draw_subway_interchange, draw_crown_fleur, draw_isometric_cube, draw_dial_gauge,
    draw_racket_grid, draw_car_steering, draw_celtic_knot, draw_scaffolding_tower
]

def make_sheet(sheet_idx: int = 0, output_path: str | None = None) -> np.ndarray:
    """Generate a single 36-icon sheet (6x6 grid) with parameterized heavy joins."""
    ROWS, COLS = 6, 6
    CELL_W, CELL_H = 180, 180
    PAD = 40
    W = COLS * CELL_W + 2 * PAD
    H = ROWS * CELL_H + 2 * PAD
    SW = 6

    canvas = np.full((H, W), 255, dtype=np.uint8)

    # Shuffle or shift drawer assignment based on sheet_idx so every sheet has a distinct arrangement
    indices = [(i + sheet_idx * 7) % len(HEAVY_JOIN_DRAWERS) for i in range(36)]

    for slot, drawer_idx in enumerate(indices):
        r_idx = slot // COLS
        c_idx = slot % COLS
        cx = PAD + c_idx * CELL_W + CELL_W // 2
        cy = PAD + r_idx * CELL_H + CELL_H // 2
        drawer = HEAVY_JOIN_DRAWERS[drawer_idx]
        drawer(canvas, cx, cy, SW, seed=sheet_idx + slot)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, canvas)
    return canvas

if __name__ == "__main__":
    out = "tests/sheet_heavy_joins_0.png"
    make_sheet(0, out)
    print(f"Successfully generated 36-icon heavy-join sheet at {out}")
