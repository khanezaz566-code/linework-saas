"""Presentation Template Engine for Linework AI
Generates Adobe Stock / Shutterstock / Microstock style presentation sheets.
Supports 17 diverse microstock layout designs across 3 creative design families:
  Family 1 (Stock Bestsellers):
    - vectuz_sidebar: Classic Adobe Stock Left Vertical Split Banner
    - vectuz_right: Mirrored Right Vertical Split Banner
    - top_banner: Shutterstock Magazine Full-Width Top Header Bar
    - bottom_dock: Creative Market Bottom Dock Gallery
    - split_duo: 50/50 Dual Light & Dark Contrast Theme Split
    - floating_card: Dribbble/Behance Modern Minimalist Floating Card
    - framed_editorial: Luxury Passe-Partout Framed Artboard
    - hero_spotlight: Spotlight Circle with 1 Prominent Hero Icon + Grid
  Family 2 (Waves & Organic Flow):
    - wave_flow: Smooth S-Curve Fluid Double Wave Ribbon
    - eco_leaf: Organic Botanical Petal Curve Banner
    - droplet_flow: Smooth Liquid Teardrop Splash
  Family 3 (Geometric & Tech Badges):
    - hexagon_shield: 3D Layered Hexagon Cyber Shield Badge
    - origami_fold: Angular Folded Geometric Origami Facet
    - diagonal_slash: Dynamic 45-degree Athletic Speed Stripes
    - bubble_orbital: Concentric Planetary Rings & Bubble Spheres
    - halftone_burst: Retro Tech Radial Halftone Dot Matrix
    - pixel_matrix: Digital AI Square Glitch Dissolve
"""
from __future__ import annotations
import math, re
from typing import Any
import numpy as np
from .model import Model, Path

# 17 Professional Microstock Design Layouts across 3 Families
DESIGNS: dict[str, dict[str, Any]] = {
    # --- Family 1: Stock Bestsellers ---
    "vectuz_sidebar": {
        "id": "vectuz_sidebar",
        "family": "bestsellers",
        "name": "Side Cover (Left)",
        "badge": "Adobe Stock",
        "desc": "Left vertical banner with top colored card & dark showcase"
    },
    "split_duo": {
        "id": "split_duo",
        "family": "bestsellers",
        "name": "Dual Theme 50/50",
        "badge": "Bestseller",
        "desc": "50% Light + 50% Dark theme split with central floating pill"
    },
    "top_banner": {
        "id": "top_banner",
        "family": "bestsellers",
        "name": "Top Header Bar",
        "badge": "Shutterstock",
        "desc": "Wide top magazine banner with count pill & specs"
    },
    "floating_card": {
        "id": "floating_card",
        "family": "bestsellers",
        "name": "Floating Card",
        "badge": "Dribbble UI",
        "desc": "Modern floating badge card with drop shadow"
    },
    "bottom_dock": {
        "id": "bottom_dock",
        "family": "bestsellers",
        "name": "Bottom Dock",
        "badge": "Creative Mkt",
        "desc": "Bottom dock strip with title, big count & mini showcase"
    },
    "hero_spotlight": {
        "id": "hero_spotlight",
        "family": "bestsellers",
        "name": "Hero Spotlight",
        "badge": "Spotlight",
        "desc": "Large dark circle highlighting 1 hero icon + grid"
    },
    "framed_editorial": {
        "id": "framed_editorial",
        "family": "bestsellers",
        "name": "Framed Luxury",
        "badge": "Passe-Partout",
        "desc": "Double vector borders with corner crosshairs & badges"
    },
    "vectuz_right": {
        "id": "vectuz_right",
        "family": "bestsellers",
        "name": "Side Cover (Right)",
        "badge": "Mirrored",
        "desc": "Right vertical cover card with left icon artboard"
    },

    # --- Family 2: Waves & Organic Flow ---
    "wave_flow": {
        "id": "wave_flow",
        "family": "organic",
        "name": "Wave Flow Ribbon",
        "badge": "Organic Wave",
        "desc": "Fluid S-curve double wave ribbon with giant numeral"
    },
    "eco_leaf": {
        "id": "eco_leaf",
        "family": "organic",
        "name": "Botanical Eco Leaf",
        "badge": "Eco / Nature",
        "desc": "Organic curved petal badge with layered accents"
    },
    "droplet_flow": {
        "id": "droplet_flow",
        "family": "organic",
        "name": "Liquid Teardrop",
        "badge": "Fluid Flow",
        "desc": "Smooth teardrop splash curve with droplet accents"
    },

    # --- Family 3: Tech & Geometric Badges ---
    "hexagon_shield": {
        "id": "hexagon_shield",
        "family": "geometric",
        "name": "Hexagon Shield",
        "badge": "Cyber Tech",
        "desc": "3D layered hexagon cyber badge with numeral"
    },
    "origami_fold": {
        "id": "origami_fold",
        "family": "geometric",
        "name": "Origami Fold",
        "badge": "Geometric",
        "desc": "Angled geometric folded polygon facets with depth"
    },
    "diagonal_slash": {
        "id": "diagonal_slash",
        "family": "geometric",
        "name": "Diagonal Slashes",
        "badge": "Speed Lines",
        "desc": "Dynamic 45° athletic speed stripes and angled cut"
    },
    "bubble_orbital": {
        "id": "bubble_orbital",
        "family": "geometric",
        "name": "Orbital Rings",
        "badge": "Planetary",
        "desc": "Concentric bubble spheres & orbital rings badge"
    },
    "halftone_burst": {
        "id": "halftone_burst",
        "family": "geometric",
        "name": "Halftone Burst",
        "badge": "Dot Matrix",
        "desc": "Radial halftone tech dot matrix burst badge"
    },
    "pixel_matrix": {
        "id": "pixel_matrix",
        "family": "geometric",
        "name": "Pixel Matrix",
        "badge": "Digital AI",
        "desc": "Tech digital square matrix glitch dissolve"
    }
}

# Microstock Trending Style Presets
PRESETS: dict[str, dict[str, Any]] = {
    "vectuz_yellow": {
        "id": "vectuz_yellow",
        "name": "Adobe Stock Gold / Yellow",
        "banner_bg": "#F5B800",
        "banner_text": "#1E1E1E",
        "banner_sub": "#374151",
        "highlight_bg": "#181B24",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#181B24",
        "accent": "#F5B800",
    },
    "vectuz_cyan": {
        "id": "vectuz_cyan",
        "name": "Tech & AI Mint / Cyan",
        "banner_bg": "#00D2A0",
        "banner_text": "#064E3B",
        "banner_sub": "#047857",
        "highlight_bg": "#0F172A",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#0F172A",
        "accent": "#00D2A0",
    },
    "vectuz_coral": {
        "id": "vectuz_coral",
        "name": "Beauty & Medical Coral",
        "banner_bg": "#FF4757",
        "banner_text": "#FFFFFF",
        "banner_sub": "#FFE4E6",
        "highlight_bg": "#1E1322",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#18181B",
        "accent": "#FF4757",
    },
    "vectuz_purple": {
        "id": "vectuz_purple",
        "name": "Creative & App Iris Purple",
        "banner_bg": "#8B5CF6",
        "banner_text": "#FFFFFF",
        "banner_sub": "#EDE9FE",
        "highlight_bg": "#120E24",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#18181B",
        "accent": "#8B5CF6",
    },
    "vectuz_emerald": {
        "id": "vectuz_emerald",
        "name": "Nature & Ecology Emerald",
        "banner_bg": "#10B981",
        "banner_text": "#FFFFFF",
        "banner_sub": "#D1FAE5",
        "highlight_bg": "#061A14",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#061A14",
        "accent": "#10B981",
    },
    "vectuz_orange": {
        "id": "vectuz_orange",
        "name": "Industry & Logistics Orange",
        "banner_bg": "#F97316",
        "banner_text": "#FFFFFF",
        "banner_sub": "#FFEDD5",
        "highlight_bg": "#1C1917",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#1C1917",
        "accent": "#F97316",
    },
    "vectuz_blue": {
        "id": "vectuz_blue",
        "name": "Corporate & Finance Royal Blue",
        "banner_bg": "#2563EB",
        "banner_text": "#FFFFFF",
        "banner_sub": "#DBEAFE",
        "highlight_bg": "#0B1329",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "checkered",
        "icon_stroke": "#0B1329",
        "accent": "#2563EB",
    },
    "minimal_white": {
        "id": "minimal_white",
        "name": "Minimalist White Studio",
        "banner_bg": "#F4F4F5",
        "banner_text": "#18181B",
        "banner_sub": "#71717A",
        "highlight_bg": "#18181B",
        "highlight_stroke": "#FFFFFF",
        "artboard_bg": "#FFFFFF",
        "icon_stroke": "#18181B",
        "accent": "#18181B",
    },
    "midnight_dark": {
        "id": "midnight_dark",
        "name": "Midnight Dark Edition",
        "banner_bg": "#18181B",
        "banner_text": "#F4F4F5",
        "banner_sub": "#A1A1AA",
        "highlight_bg": "#09090B",
        "highlight_stroke": "#00F5A0",
        "artboard_bg": "#0F172A",
        "icon_stroke": "#F4F4F5",
        "accent": "#00F5A0",
    }
}

def resolve_config(cfg: dict | None) -> dict[str, Any]:
    c = dict(PRESETS["vectuz_yellow"])
    c.update({
        "design": "modular_maker",
        "banner_shape": "square_solid",
        "title_highlight": "solid_square",
        "showcase_shape": "square_box",
        "decor_element": "artboard_square_box",
        "panel_pos": "left",
        "title": "TECHNOLOGY",
        "count": "24",
        "subtitle": "Editable Line Icons",
        "layout": "landscape_16_9",
        "stroke_scale": 1.0,
        "show_highlight": True,
        "highlight_mode": "hero_1",
        "font_family": "bebas",
        "icon_layout": "auto_grid",
        "artboard_margin": 0.06,
        "highlight_index": 0,
        "title_fs": 0,
        "count_fs": 0,
        "sub_fs": 0,
        "shape_accent": ""
    })
    if cfg:
        p_name = cfg.get("preset")
        if p_name and p_name in PRESETS:
            c.update(PRESETS[p_name])
        for k, v in cfg.items():
            if v is not None and v != "":
                c[k] = v
    return c

def sanitize_text(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 0.1, 0.1, 0.1
    return int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0

def escape_ps_text(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def _extract_icon_paths(model: Model, box: list[float] | tuple[float, ...], pad: float = 6.0, icon_obj: dict | None = None) -> list[Path]:
    if icon_obj and icon_obj.get("paths"):
        return icon_obj["paths"]
    x1, y1, x2, y2 = box
    matched = []
    for p in model.paths:
        if len(p.A) == 0:
            continue
        cx = float(np.mean(p.A[:, 0]))
        cy = float(np.mean(p.A[:, 1]))
        if (x1 - pad) <= cx <= (x2 + pad) and (y1 - pad) <= cy <= (y2 + pad):
            matched.append(p)
    return matched

def _render_paths_svg(paths: list[Path], stroke: str, stroke_scale: float, scale: float, ox: float, oy: float) -> str:
    elems = []
    for p in paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        d = p.d()
        elems.append(
            f'<path d="{d}" stroke="{stroke}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )
    body = "\n        ".join(elems)
    return f'<g transform="translate({ox:.2f}, {oy:.2f}) scale({scale:.4f})">\n        {body}\n      </g>'

def _calc_dims(layout: str, mW: float, mH: float) -> tuple[int, int, int]:
    if layout == "auto_dock":
        H = int(max(400, mH))
        banner_w = max(380, int(round(H * 0.35)))
        W = banner_w + int(max(400, mW))
    elif layout == "square":
        W, H, banner_w = 2400, 2400, 640
    elif layout == "landscape_4_3":
        W, H, banner_w = 2400, 1800, 620
    elif layout == "landscape_16_10":
        W, H, banner_w = 1920, 1200, 480
    else:  # landscape_16_9 (Default 4K Ultra-HD presentation: 3840 x 2160)
        W, H, banner_w = 3840, 2160, 960
    return W, H, banner_w

def _get_checkered_defs(W: int) -> tuple[str, str]:
    chk_size = max(16, int(round(W / 120)))
    chk_half = chk_size / 2
    defs = f"""
    <pattern id="stockCheckeredPattern" width="{chk_size}" height="{chk_size}" patternUnits="userSpaceOnUse">
      <rect width="{chk_size}" height="{chk_size}" fill="#ffffff"/>
      <rect x="0" y="0" width="{chk_half}" height="{chk_half}" fill="#f1f3f6"/>
      <rect x="{chk_half}" y="{chk_half}" width="{chk_half}" height="{chk_half}" fill="#f1f3f6"/>
    </pattern>"""
    return defs, 'url(#stockCheckeredPattern)'


def _compute_optimal_grid(N: int, target_aspect: float = 1.3) -> tuple[int, int]:
    if N <= 0:
        return 1, 1
    standard_grids = {
        1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 5: (5, 1),
        6: (3, 2), 8: (4, 2), 9: (3, 3), 10: (5, 2), 12: (4, 3),
        15: (5, 3), 16: (4, 4), 18: (6, 3), 20: (5, 4), 21: (7, 3),
        24: (6, 4), 25: (5, 5), 28: (7, 4), 30: (6, 5), 32: (8, 4),
        35: (7, 5), 36: (6, 6), 40: (8, 5), 45: (9, 5), 48: (8, 6),
        50: (10, 5), 60: (10, 6), 64: (8, 8), 70: (10, 7), 80: (10, 8),
        100: (10, 10)
    }
    if N in standard_grids:
        return standard_grids[N]

    best_c, best_r = N, 1
    best_diff = 999.0
    for r in range(1, int(math.isqrt(N)) + 4):
        c = math.ceil(N / r)
        aspect = c / r
        diff = abs(aspect - target_aspect)
        if diff < best_diff:
            best_diff = diff
            best_c, best_r = c, r
    return best_c, best_r


def _render_artboard_outer_frame(
    decor: str, sheet_x: float, sheet_y: float, sheet_w: float, sheet_h: float,
    pad_x: float, pad_y: float, banner_bg: str, stroke_color: str, accent: str, title: str, count_val: str
) -> str:
    if decor == "none":
        return ""
    bx = sheet_x + pad_x * 0.45
    by = sheet_y + pad_y * 0.45
    bw = sheet_w - pad_x * 0.90
    bh = sheet_h - pad_y * 0.90
    frame_col = accent if accent else banner_bg

    if decor == "artboard_double_frame":
        return f"""
      <g id="artboardDoubleFrame" opacity="0.85">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" fill="none" stroke="{frame_col}" stroke-width="4"/>
        <rect x="{bx+14:.1f}" y="{by+14:.1f}" width="{bw-28:.1f}" height="{bh-28:.1f}" rx="4" fill="none" stroke="{stroke_color}" stroke-opacity="0.28" stroke-width="1.5" stroke-dasharray="12,6"/>
      </g>"""
    elif decor == "artboard_corner_ticks":
        t = 28
        return f"""
      <g id="artboardCornerTicks" stroke="{stroke_color}" stroke-width="2.5" opacity="0.55" fill="none">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" stroke-opacity="0.18" stroke-width="1.5"/>
        <path d="M{bx-12:.1f},{by:.1f} h{t} M{bx:.1f},{by-12:.1f} v{t}"/>
        <path d="M{bx+bw-t+12:.1f},{by:.1f} h{t} M{bx+bw:.1f},{by-12:.1f} v{t}"/>
        <path d="M{bx-12:.1f},{by+bh:.1f} h{t} M{bx:.1f},{by+bh-t+12:.1f} v{t}"/>
        <path d="M{bx+bw-t+12:.1f},{by+bh:.1f} h{t} M{bx+bw:.1f},{by+bh-t+12:.1f} v{t}"/>
      </g>"""
    elif decor == "artboard_hud_corners":
        L = 48
        return f"""
      <g id="artboardHudCorners" fill="none">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" stroke="{stroke_color}" stroke-opacity="0.15" stroke-width="1.5"/>
        <path d="M{bx:.1f},{by+L:.1f} V{by:.1f} H{bx+L:.1f}" stroke="{frame_col}" stroke-width="6"/>
        <path d="M{bx+bw-L:.1f},{by:.1f} H{bx+bw:.1f} V{by+L:.1f}" stroke="{frame_col}" stroke-width="6"/>
        <path d="M{bx:.1f},{by+bh-L:.1f} V{by+bh:.1f} H{bx+L:.1f}" stroke="{frame_col}" stroke-width="6"/>
        <path d="M{bx+bw-L:.1f},{by+bh:.1f} H{bx+bw:.1f} V{by+bh-L:.1f}" stroke="{frame_col}" stroke-width="6"/>
      </g>"""
    elif decor == "artboard_dashed_frame":
        return f"""
      <g id="artboardDashedFrame">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="12" fill="none" stroke="{stroke_color}" stroke-opacity="0.35" stroke-width="3" stroke-dasharray="16,10"/>
      </g>"""
    elif decor == "artboard_header_footer":
        return f"""
      <g id="artboardHeaderFooter">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" fill="none" stroke="{stroke_color}" stroke-opacity="0.22" stroke-width="2"/>
        <line x1="{bx+24:.1f}" y1="{by+42:.1f}" x2="{bx+bw-24:.1f}" y2="{by+42:.1f}" stroke="{stroke_color}" stroke-opacity="0.18" stroke-width="1.5"/>
        <text x="{bx+28:.1f}" y="{by+28:.1f}" font-size="13" font-weight="800" letter-spacing="2" fill="{stroke_color}" opacity="0.55" class="mono">{sanitize_text(title)} // {sanitize_text(count_val)} ICONS</text>
        <text x="{bx+bw-28:.1f}" y="{by+28:.1f}" font-size="13" font-weight="800" letter-spacing="2" fill="{stroke_color}" opacity="0.55" text-anchor="end" class="mono">100% VECTOR GRID</text>
        <line x1="{bx+24:.1f}" y1="{by+bh-38:.1f}" x2="{bx+bw-24:.1f}" y2="{by+bh-38:.1f}" stroke="{stroke_color}" stroke-opacity="0.18" stroke-width="1.5"/>
        <text x="{bx+bw/2:.1f}" y="{by+bh-14:.1f}" font-size="12" font-weight="700" letter-spacing="3" fill="{stroke_color}" opacity="0.5" text-anchor="middle" class="mono">PIXEL PERFECT &#8226; EDITABLE STROKE &#8226; SCALABLE</text>
      </g>"""
    else:
        # Default crisp Square Box around the Icon Set artboard
        return f"""
      <g id="artboardSquareBox">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="6" fill="none" stroke="{stroke_color}" stroke-opacity="0.22" stroke-width="2.5"/>
        <rect x="{bx-4:.1f}" y="{by-4:.1f}" width="10" height="10" fill="{frame_col}"/>
        <rect x="{bx+bw-6:.1f}" y="{by-4:.1f}" width="10" height="10" fill="{frame_col}"/>
        <rect x="{bx-4:.1f}" y="{by+bh-6:.1f}" width="10" height="10" fill="{frame_col}"/>
        <rect x="{bx+bw-6:.1f}" y="{by+bh-6:.1f}" width="10" height="10" fill="{frame_col}"/>
      </g>"""


def _render_cell_box_svg(
    decor: str, cx: float, cy: float, cell_w: float, cell_h: float,
    banner_bg: str, stroke_color: str, accent: str, idx: int
) -> str:
    s = min(cell_w * 0.84, cell_h * 0.84)
    x = cx - s / 2
    y = cy - s / 2
    col = accent if accent else banner_bg

    if decor == "cell_square_boxes":
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="4" fill="#ffffff" fill-opacity="0.65" stroke="{stroke_color}" stroke-opacity="0.24" stroke-width="2"/>'
    elif decor == "cell_rounded_cards":
        rx = min(22, int(s * 0.14))
        return (
            f'<rect x="{x+3:.1f}" y="{y+5:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{rx}" fill="#000000" fill-opacity="0.06"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{rx}" fill="#ffffff" fill-opacity="0.85" stroke="{stroke_color}" stroke-opacity="0.18" stroke-width="1.8"/>'
        )
    elif decor == "cell_dashed_boxes":
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="6" fill="none" stroke="{stroke_color}" stroke-opacity="0.32" stroke-width="2" stroke-dasharray="8,6"/>'
    elif decor == "cell_full_table_grid":
        gx = cx - cell_w / 2
        gy = cy - cell_h / 2
        return f'<rect x="{gx:.1f}" y="{gy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="none" stroke="{stroke_color}" stroke-opacity="0.18" stroke-width="1.5"/>'
    elif decor == "cell_corner_brackets":
        L = max(10, int(s * 0.16))
        return (
            f'<path d="M{x:.1f},{y+L:.1f} V{y:.1f} H{x+L:.1f} M{x+s-L:.1f},{y:.1f} H{x+s:.1f} V{y+L:.1f} '
            f'M{x:.1f},{y+s-L:.1f} V{y+s:.1f} H{x+L:.1f} M{x+s-L:.1f},{y+s:.1f} H{x+s:.1f} V{y+s-L:.1f}" '
            f'fill="none" stroke="{stroke_color}" stroke-opacity="0.38" stroke-width="2.2"/>'
        )
    elif decor == "cell_soft_tint_squares":
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="12" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-opacity="0.32" stroke-width="1.5"/>'
    elif decor == "cell_circle_badges":
        r = s * 0.48
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#ffffff" fill-opacity="0.6" stroke="{stroke_color}" stroke-opacity="0.22" stroke-width="2"/>'
    elif decor == "cell_hex_frames":
        r = s * 0.50
        pts = " ".join(f"{cx + r * math.cos(math.radians(60 * k - 30)):.1f},{cy + r * math.sin(math.radians(60 * k - 30)):.1f}" for k in range(6))
        return f'<polygon points="{pts}" fill="#ffffff" fill-opacity="0.6" stroke="{stroke_color}" stroke-opacity="0.24" stroke-width="2"/>'
    elif decor == "cell_brutal_squares":
        return (
            f'<rect x="{x+6:.1f}" y="{y+6:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{stroke_color}" fill-opacity="0.85"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" fill="#ffffff" stroke="{stroke_color}" stroke-width="2.5"/>'
        )
    return ""


def _render_adaptive_sheet_icons(
    model: Model, icons_meta: list[dict] | None, c: dict,
    sheet_x: float, sheet_y: float, sheet_w: float, sheet_h: float
) -> str:
    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    layout_mode = str(c.get("icon_layout") or "auto_grid").lower()
    decor = str(c.get("decor_element") or "artboard_square_box").lower()
    banner_bg = c.get("banner_bg", "#F5B800")
    accent = c.get("shape_accent") or c.get("accent") or banner_bg
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))

    try:
        margin_pct = float(c.get("artboard_margin") or 0.06)
    except Exception:
        margin_pct = 0.06
    margin_pct = max(0.02, min(0.20, margin_pct))

    pad_x = sheet_w * margin_pct
    pad_y = sheet_h * margin_pct

    outer_frame_svg = _render_artboard_outer_frame(
        decor, sheet_x, sheet_y, sheet_w, sheet_h,
        pad_x, pad_y, banner_bg, stroke_color, accent, c.get("title", "ICONS"), count_val
    )

    avail_icons = icons_meta or []
    N = len(avail_icons)

    has_cell_box = decor.startswith("cell_")
    # Extra inner padding so icons sit comfortably inside outer frame
    inner_pad_x = pad_x * 1.15
    inner_pad_y = pad_y * 1.15

    # Mode 1: Auto-Grid by Icon Count (Adobe Stock standard)
    if layout_mode == "auto_grid" and N >= 1:
        target_aspect = sheet_w / max(1.0, sheet_h)
        cols, rows = _compute_optimal_grid(N, target_aspect)

        grid_w = sheet_w - 2 * inner_pad_x
        grid_h = sheet_h - 2 * inner_pad_y

        cell_w = grid_w / cols
        cell_h = grid_h / rows
        fill_ratio = 0.50 if has_cell_box else 0.68
        target_size = min(cell_w * fill_ratio, cell_h * fill_ratio)

        rendered = [outer_frame_svg] if outer_frame_svg else []
        for i, ic in enumerate(avail_icons):
            col_i = i % cols
            row_i = i // cols
            cell_cx = sheet_x + inner_pad_x + col_i * cell_w + cell_w / 2
            cell_cy = sheet_y + inner_pad_y + row_i * cell_h + cell_h / 2

            if has_cell_box:
                rendered.append(_render_cell_box_svg(decor, cell_cx, cell_cy, cell_w, cell_h, banner_bg, stroke_color, accent, i))

            paths = _extract_icon_paths(model, ic["box"], icon_obj=ic)
            if not paths:
                continue
            valid_pts = [p.A for p in paths if len(p.A) > 0]
            if valid_pts:
                all_pts = np.concatenate(valid_pts)
                bx1, bx2 = float(np.min(all_pts[:, 0])), float(np.max(all_pts[:, 0]))
                by1, by2 = float(np.min(all_pts[:, 1])), float(np.max(all_pts[:, 1]))
            else:
                bx1, by1, bx2, by2 = ic["box"]
            bw, bh = max(1.0, bx2 - bx1), max(1.0, by2 - by1)
            s = target_size / max(bw, bh)
            ox = cell_cx - (bw * s) / 2 - bx1 * s
            oy = cell_cy - (bh * s) / 2 - by1 * s
            rendered.append(_render_paths_svg(paths, stroke_color, stroke_scale, s, ox, oy))
        if rendered:
            return "\n    ".join(rendered)

    # Mode 2: Tight Bounding Box Auto-Fit (Trims empty borders around paths)
    valid_paths = [p for p in model.paths if len(p.A) > 0]
    if valid_paths:
        all_xs = np.concatenate([p.A[:, 0] for p in valid_paths])
        all_ys = np.concatenate([p.A[:, 1] for p in valid_paths])
        min_x, max_x = float(np.min(all_xs)), float(np.max(all_xs))
        min_y, max_y = float(np.min(all_ys)), float(np.max(all_ys))
        t_w = max(10.0, max_x - min_x)
        t_h = max(10.0, max_y - min_y)
    else:
        min_x, min_y = 0.0, 0.0
        t_w, t_h = max(10.0, model.width), max(10.0, model.height)

    avail_w = sheet_w - 2 * inner_pad_x
    avail_h = sheet_h - 2 * inner_pad_y
    scale = min(avail_w / t_w, avail_h / t_h)
    target_w = t_w * scale
    target_h = t_h * scale
    off_x = sheet_x + inner_pad_x + (avail_w - target_w) / 2 - min_x * scale
    off_y = sheet_y + inner_pad_y + (avail_h - target_h) / 2 - min_y * scale

    return (outer_frame_svg + "\n    " if outer_frame_svg else "") + _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)


def _get_font_css(font_family: str = "bebas") -> tuple[str, str, str, str]:
    font_family = str(font_family or "bebas").lower()
    fonts_import = """
      @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&amp;family=Montserrat:wght@700;800;900&amp;family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=Space+Grotesk:wght@700&amp;family=Playfair+Display:wght@700;900&amp;family=JetBrains+Mono:wght@700;800&amp;family=Oswald:wght@700&amp;family=Outfit:wght@700;900&amp;display=swap');
    """
    if font_family == "montserrat":
        title_font = "'Montserrat', 'Arial Black', sans-serif"
        count_font = "'Montserrat', 'Arial Black', sans-serif"
        sub_font = "'Montserrat', 'Segoe UI', sans-serif"
    elif font_family == "jakarta":
        title_font = "'Plus Jakarta Sans', 'Segoe UI', sans-serif"
        count_font = "'Plus Jakarta Sans', 'Segoe UI', sans-serif"
        sub_font = "'Plus Jakarta Sans', 'Segoe UI', sans-serif"
    elif font_family == "space":
        title_font = "'Space Grotesk', 'Century Gothic', 'Segoe UI', sans-serif"
        count_font = "'Space Grotesk', 'Century Gothic', 'Segoe UI', sans-serif"
        sub_font = "'Space Grotesk', 'Century Gothic', sans-serif"
    elif font_family == "playfair":
        title_font = "'Playfair Display', 'Georgia', serif"
        count_font = "'Playfair Display', 'Georgia', serif"
        sub_font = "'Plus Jakarta Sans', 'Segoe UI', sans-serif"
    elif font_family == "oswald":
        title_font = "'Oswald', 'Impact', sans-serif"
        count_font = "'Oswald', 'Impact', sans-serif"
        sub_font = "'Plus Jakarta Sans', sans-serif"
    elif font_family == "outfit":
        title_font = "'Outfit', 'Segoe UI', sans-serif"
        count_font = "'Outfit', 'Segoe UI', sans-serif"
        sub_font = "'Outfit', sans-serif"
    elif font_family == "mono":
        title_font = "'JetBrains Mono', 'Consolas', monospace"
        count_font = "'JetBrains Mono', 'Consolas', monospace"
        sub_font = "'JetBrains Mono', 'Consolas', monospace"
    else:  # default "bebas"
        title_font = "'Bebas Neue', 'Impact', 'Arial Black', sans-serif"
        count_font = "'Bebas Neue', 'Impact', 'Arial Black', sans-serif"
        sub_font = "'Montserrat', 'Trebuchet MS', 'Segoe UI', sans-serif"
    return fonts_import, title_font, count_font, sub_font


# =========================================================================
# 25 Title & Text Highlighters (Category 2)
# =========================================================================
def _render_title_highlight(
    title: str, subtitle: str,
    cx: float, cy: float,
    title_fs: int, sub_fs: int,
    banner_text: str, banner_sub: str,
    title_font: str, sub_font: str,
    style: str = "solid_square",
    is_centered: bool = True,
    max_w: float = 600,
    accent: str = ""
) -> str:
    title_clean = sanitize_text(title)
    sub_clean = sanitize_text(subtitle)
    anchor = "middle" if is_centered else "start"
    style = str(style or "solid_square").lower()

    est_w = min(max_w, max(260, int(len(title) * title_fs * 0.64) + 64))
    rect_x = cx - est_w / 2 if is_centered else cx
    box_h = int(title_fs * 1.48)
    box_y = cy - int(title_fs * 0.92)
    hl_fill = accent if accent else "rgba(0,0,0,0.22)"
    hl_text = "#FFFFFF" if accent else banner_text

    # 25 Distinct Highlighter Geometries
    bg_shape = ""
    if style in ("solid_square", "square"):
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.35" stroke-width="2.5"/>'
    elif style in ("frosted_pill", "pill"):
        rx = box_h // 2
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="{hl_fill}" stroke="rgba(255,255,255,0.35)" stroke-width="2"/>'
    elif style == "rounded_badge":
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="14" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.25" stroke-width="2"/>'
    elif style in ("ribbon_tails", "ribbon"):
        notch = 18
        pts = f"{rect_x-12:.1f},{box_y:.1f} {rect_x+est_w+12:.1f},{box_y:.1f} {rect_x+est_w-notch+12:.1f},{box_y+box_h/2:.1f} {rect_x+est_w+12:.1f},{box_y+box_h:.1f} {rect_x-12:.1f},{box_y+box_h:.1f} {rect_x+notch-12:.1f},{box_y+box_h/2:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.3" stroke-width="2"/>'
    elif style == "skew_parallelogram":
        sk = 18
        pts = f"{rect_x+sk:.1f},{box_y:.1f} {rect_x+est_w+sk:.1f},{box_y:.1f} {rect_x+est_w-sk:.1f},{box_y+box_h:.1f} {rect_x-sk:.1f},{box_y+box_h:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.35" stroke-width="2"/>'
    elif style == "hex_tag":
        p = 22
        pts = f"{rect_x+p:.1f},{box_y:.1f} {rect_x+est_w-p:.1f},{box_y:.1f} {rect_x+est_w:.1f},{box_y+box_h/2:.1f} {rect_x+est_w-p:.1f},{box_y+box_h:.1f} {rect_x+p:.1f},{box_y+box_h:.1f} {rect_x:.1f},{box_y+box_h/2:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.4" stroke-width="2.2"/>'
    elif style == "chamfer_plate":
        c_cut = 14
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        pts = f"{x1+c_cut:.1f},{y1:.1f} {x2-c_cut:.1f},{y1:.1f} {x2:.1f},{y1+c_cut:.1f} {x2:.1f},{y2-c_cut:.1f} {x2-c_cut:.1f},{y2:.1f} {x1+c_cut:.1f},{y2:.1f} {x1:.1f},{y2-c_cut:.1f} {x1:.1f},{y1+c_cut:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.45" stroke-width="2.5"/>'
    elif style in ("neon_underline", "glow_bar"):
        hl_text = banner_text
        bar_h = 8
        bg_shape = (
            f'<rect x="{rect_x:.1f}" y="{cy+10:.1f}" width="{est_w:.1f}" height="{bar_h}" rx="4" fill="{accent or banner_text}"/>'
            f'<circle cx="{cx:.1f}" cy="{cy+14:.1f}" r="6" fill="#ffffff"/>'
        )
    elif style == "double_rule":
        hl_text = banner_text
        bg_shape = (
            f'<line x1="{rect_x:.1f}" y1="{box_y:.1f}" x2="{rect_x+est_w:.1f}" y2="{box_y:.1f}" stroke="{banner_text}" stroke-width="3.5"/>'
            f'<line x1="{rect_x+20:.1f}" y1="{box_y+6:.1f}" x2="{rect_x+est_w-20:.1f}" y2="{box_y+6:.1f}" stroke="{banner_text}" stroke-width="1.5" opacity="0.6"/>'
            f'<line x1="{rect_x:.1f}" y1="{box_y+box_h:.1f}" x2="{rect_x+est_w:.1f}" y2="{box_y+box_h:.1f}" stroke="{banner_text}" stroke-width="3.5"/>'
        )
    elif style in ("corner_brackets", "brackets"):
        hl_text = banner_text
        t = 20
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<path d="M{x1+t:.1f},{y1:.1f} H{x1:.1f} V{y1+t:.1f} M{x2-t:.1f},{y1:.1f} H{x2:.1f} V{y1+t:.1f} '
            f'M{x1+t:.1f},{y2:.1f} H{x1:.1f} V{y2-t:.1f} M{x2-t:.1f},{y2:.1f} H{x2:.1f} V{y2-t:.1f}" '
            f'fill="none" stroke="{accent or banner_text}" stroke-width="4"/>'
        )
    elif style == "left_accent_bar":
        bg_shape = (
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" fill-opacity="0.7"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="12" height="{box_h:.1f}" fill="{accent or banner_text}"/>'
        )
    elif style == "brush_stroke":
        d = f"M{rect_x-8:.1f},{box_y+8:.1f} Q{cx:.1f},{box_y-6:.1f} {rect_x+est_w+10:.1f},{box_y+4:.1f} L{rect_x+est_w-4:.1f},{box_y+box_h-4:.1f} Q{cx:.1f},{box_y+box_h+8:.1f} {rect_x+4:.1f},{box_y+box_h-2:.1f} Z"
        bg_shape = f'<path d="{d}" fill="{hl_fill}"/>'
    elif style == "offset_shadow_box":
        bg_shape = (
            f'<rect x="{rect_x+8:.1f}" y="{box_y+8:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="#09090B"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="#09090B" stroke-width="3"/>'
        )
    elif style == "dotted_coupon":
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="8" fill="{hl_fill}" stroke="{banner_text}" stroke-width="2.5" stroke-dasharray="8,6"/>'
    elif style == "gradient_glow_pill":
        rx = box_h // 2
        bg_shape = (
            f'<rect x="{rect_x-5:.1f}" y="{box_y-5:.1f}" width="{est_w+10:.1f}" height="{box_h+10:.1f}" rx="{rx+5}" fill="none" stroke="{accent or banner_text}" stroke-opacity="0.45" stroke-width="2"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.5" stroke-width="2"/>'
        )
    elif style == "ticket_stub":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        my = (y1 + y2) / 2
        d = f"M{x1:.1f},{y1:.1f} H{x2:.1f} V{my-10:.1f} A10,10 0 0,0 {x2:.1f},{my+10:.1f} V{y2:.1f} H{x1:.1f} V{my+10:.1f} A10,10 0 0,0 {x1:.1f},{my-10:.1f} Z"
        bg_shape = f'<path d="{d}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.35" stroke-width="2"/>'
    elif style == "arrow_pointer":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        my = (y1 + y2) / 2
        pts = f"{x1:.1f},{y1:.1f} {x2-18:.1f},{y1:.1f} {x2+8:.1f},{my:.1f} {x2-18:.1f},{y2:.1f} {x1:.1f},{y2:.1f}"
        bg_shape = (
            f'<polygon points="{pts}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.3" stroke-width="2"/>'
            f'<circle cx="{x2-10:.1f}" cy="{my:.1f}" r="5" fill="{banner_text}"/>'
        )
    elif style == "speech_callout":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="12" fill="{hl_fill}"/>'
            f'<polygon points="{cx-12:.1f},{y2:.1f} {cx+12:.1f},{y2:.1f} {cx:.1f},{y2+14:.1f}" fill="{hl_fill}"/>'
        )
    elif style == "circle_seal_bg":
        r = int(box_h * 0.72)
        bg_shape = (
            f'<circle cx="{cx:.1f}" cy="{box_y+box_h/2:.1f}" r="{r}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.3" stroke-width="2" stroke-dasharray="6,4"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="8" fill="{hl_fill}"/>'
        )
    elif style == "diamond_crest":
        my = box_y + box_h / 2
        bg_shape = (
            f'<polygon points="{cx:.1f},{box_y-16:.1f} {cx+42:.1f},{my:.1f} {cx:.1f},{box_y+box_h+16:.1f} {cx-42:.1f},{my:.1f}" fill="{accent or banner_text}" opacity="0.35"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="4" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.35" stroke-width="2"/>'
        )
    elif style == "crown_header":
        hl_text = banner_text
        bg_shape = (
            f'<polygon points="{cx-36:.1f},{box_y-6:.1f} {cx-24:.1f},{box_y-22:.1f} {cx-8:.1f},{box_y-10:.1f} {cx:.1f},{box_y-28:.1f} {cx+8:.1f},{box_y-10:.1f} {cx+24:.1f},{box_y-22:.1f} {cx+36:.1f},{box_y-6:.1f}" fill="{accent or banner_text}"/>'
            f'<rect x="{rect_x:.1f}" y="{cy+8:.1f}" width="{est_w:.1f}" height="4" fill="{banner_text}"/>'
        )
    elif style == "crosshair_target":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="{banner_text}" stroke-opacity="0.4" stroke-width="1.5"/>'
            f'<path d="M{x1-8:.1f},{y1:.1f} h16 M{x1:.1f},{y1-8:.1f} v16 M{x2-8:.1f},{y1:.1f} h16 M{x2:.1f},{y1-8:.1f} v16 '
            f'M{x1-8:.1f},{y2:.1f} h16 M{x1:.1f},{y2-8:.1f} v16 M{x2-8:.1f},{y2:.1f} h16 M{x2:.1f},{y2-8:.1f} v16" stroke="{banner_text}" stroke-width="2"/>'
        )
    elif style == "extrude_3d_box":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        d = 10
        bg_shape = (
            f'<polygon points="{x1+d:.1f},{y2+d:.1f} {x2+d:.1f},{y2+d:.1f} {x2+d:.1f},{y1+d:.1f} {x2:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x1:.1f},{y2:.1f}" fill="#09090B" opacity="0.65"/>'
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="{banner_text}" stroke-width="2.5"/>'
        )
    elif style == "minimal_pill_outline":
        hl_text = banner_text
        rx = box_h // 2
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="none" stroke="{accent or banner_text}" stroke-width="3"/>'
    else:
        hl_text = banner_text

    sub_y = box_y + box_h + int(sub_fs * 1.45) + 8
    return f"""
    <g id="titleHighlighterGroup">
      {bg_shape}
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3"
            fill="{hl_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <text x="{cx}" y="{sub_y}" font-size="{sub_fs}" font-weight="700" letter-spacing="1.2"
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""


# =========================================================================
# 25 Showcase Box & Icon Frame Shapes (Category 3 — Default: Square Box!)
# =========================================================================
def _render_showcase_box(
    model: Model, icons_meta: list[dict], c: dict,
    cx: float, cy: float, w: float, h: float,
    stroke_scale: float
) -> str:
    shape = str(c.get("showcase_shape") or "square_box").lower()
    if shape in ("none", "off", "hidden", "0", "false") or not c.get("show_highlight", True):
        return ""
    hl_bg = c["highlight_bg"]
    hl_stroke = c["highlight_stroke"]
    accent = c.get("shape_accent") or c.get("accent") or "#38bdf8"
    hl_mode = c.get("highlight_mode", "hero_1")
    highlight_index = int(c.get("highlight_index") or 0)
    num_hl = 1 if hl_mode == "hero_1" else (6 if hl_mode == "mini_6" else 4)
    cols = 1 if hl_mode == "hero_1" else 2

    # Base square box dimensions
    side = min(w * 0.90, h * 0.88)
    bx = cx - side / 2
    by = cy - side / 2

    # Inner icon bounds
    pad_ratio = 0.16
    ix = bx + side * pad_ratio
    iy = by + side * pad_ratio
    iw = side * (1.0 - 2 * pad_ratio)
    ih = side * (1.0 - 2 * pad_ratio)

    hero_paths = _extract_highlight_svg(
        model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
        iw, ih, ix, iy, cols=cols, highlight_index=highlight_index
    )

    frame_svg = ""
    if shape in ("square_box", "square"):
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="4" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2.5"/>'
            f'<rect x="{bx-4:.1f}" y="{by-4:.1f}" width="8" height="8" fill="{accent}"/>'
            f'<rect x="{bx+side-4:.1f}" y="{by-4:.1f}" width="8" height="8" fill="{accent}"/>'
            f'<rect x="{bx-4:.1f}" y="{by+side-4:.1f}" width="8" height="8" fill="{accent}"/>'
            f'<rect x="{bx+side-4:.1f}" y="{by+side-4:.1f}" width="8" height="8" fill="{accent}"/>'
        )
    elif shape in ("rounded_square", "card"):
        frame_svg = f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="28" fill="{hl_bg}" stroke="rgba(255,255,255,0.25)" stroke-width="2.5"/>'
    elif shape == "double_border_square":
        frame_svg = (
            f'<rect x="{bx-8:.1f}" y="{by-8:.1f}" width="{side+16:.1f}" height="{side+16:.1f}" rx="8" fill="none" stroke="{hl_bg}" stroke-width="3"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="4" fill="{hl_bg}" stroke="{accent}" stroke-opacity="0.55" stroke-width="2"/>'
        )
    elif shape == "dashed_square":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="10" fill="{hl_bg}"/>'
            f'<rect x="{bx+10:.1f}" y="{by+10:.1f}" width="{side-20:.1f}" height="{side-20:.1f}" rx="6" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5" stroke-dasharray="12,8"/>'
        )
    elif shape == "offset_brutal_square":
        frame_svg = (
            f'<rect x="{bx+12:.1f}" y="{by+12:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{accent}"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{hl_bg}" stroke="#ffffff" stroke-width="3"/>'
        )
    elif shape == "chamfer_square":
        c_cut = side * 0.14
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        pts = f"{x1+c_cut:.1f},{y1:.1f} {x2-c_cut:.1f},{y1:.1f} {x2:.1f},{y1+c_cut:.1f} {x2:.1f},{y2-c_cut:.1f} {x2-c_cut:.1f},{y2:.1f} {x1+c_cut:.1f},{y2:.1f} {x1:.1f},{y2-c_cut:.1f} {x1:.1f},{y1+c_cut:.1f}"
        frame_svg = f'<polygon points="{pts}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
    elif shape == "hud_tech_box":
        L = side * 0.18
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{hl_bg}" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>'
            f'<path d="M{x1:.1f},{y1+L:.1f} V{y1:.1f} H{x1+L:.1f} M{x2-L:.1f},{y1:.1f} H{x2:.1f} V{y1+L:.1f} '
            f'M{x1:.1f},{y2-L:.1f} V{y2:.1f} H{x1+L:.1f} M{x2-L:.1f},{y2:.1f} H{x2:.1f} V{y2-L:.1f}" fill="none" stroke="{accent}" stroke-width="5"/>'
        )
    elif shape == "glass_card":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="24" fill="{hl_bg}" fill-opacity="0.88" stroke="#ffffff" stroke-opacity="0.4" stroke-width="2"/>'
            f'<path d="M{bx+24:.1f},{by:.1f} H{bx+side*0.55:.1f} L{bx:.1f},{by+side*0.55:.1f} V{by+24:.1f} Z" fill="#ffffff" fill-opacity="0.07"/>'
        )
    elif shape == "polaroid_frame":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side+36:.1f}" rx="6" fill="#ffffff" stroke="rgba(0,0,0,0.2)" stroke-width="2"/>'
            f'<rect x="{bx+14:.1f}" y="{by+14:.1f}" width="{side-28:.1f}" height="{side-28:.1f}" fill="{hl_bg}"/>'
            f'<text x="{cx:.1f}" y="{by+side+22:.1f}" font-size="13" font-weight="800" letter-spacing="2" fill="#1e293b" text-anchor="middle" class="mono">ICON SHOWCASE</text>'
        )
    elif shape == "stamp_perforated":
        frame_svg = (
            f'<rect x="{bx-6:.1f}" y="{by-6:.1f}" width="{side+12:.1f}" height="{side+12:.1f}" fill="none" stroke="{hl_bg}" stroke-width="8" stroke-dasharray="4,10" stroke-linecap="round"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{hl_bg}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>'
        )
    elif shape == "ticket_box":
        r_n = 18
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        d = (
            f"M{x1+r_n:.1f},{y1:.1f} H{x2-r_n:.1f} A{r_n},{r_n} 0 0,0 {x2:.1f},{y1+r_n:.1f} "
            f"V{y2-r_n:.1f} A{r_n},{r_n} 0 0,0 {x2-r_n:.1f},{y2:.1f} "
            f"H{x1+r_n:.1f} A{r_n},{r_n} 0 0,0 {x1:.1f},{y2-r_n:.1f} "
            f"V{y1+r_n:.1f} A{r_n},{r_n} 0 0,0 {x1+r_n:.1f},{y1:.1f} Z"
        )
        frame_svg = f'<path d="{d}" fill="{hl_bg}" stroke="{accent}" stroke-opacity="0.45" stroke-width="2.5"/>'
    elif shape == "shield_crest":
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        d = f"M{cx:.1f},{y1:.1f} L{x2:.1f},{y1+side*0.18:.1f} V{y1+side*0.55:.1f} C{x2:.1f},{y1+side*0.82:.1f} {cx:.1f},{y2+10:.1f} {cx:.1f},{y2+10:.1f} C{cx:.1f},{y2+10:.1f} {x1:.1f},{y1+side*0.82:.1f} {x1:.1f},{y1+side*0.55:.1f} V{y1+side*0.18:.1f} Z"
        frame_svg = f'<path d="{d}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
    elif shape in ("hexagon_pod", "hexagon"):
        r = side * 0.54
        pts = " ".join(f"{cx + r * math.cos(math.radians(60 * k - 30)):.1f},{cy + r * math.sin(math.radians(60 * k - 30)):.1f}" for k in range(6))
        frame_svg = f'<polygon points="{pts}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
    elif shape == "octagon_badge":
        r = side * 0.54
        pts = " ".join(f"{cx + r * math.cos(math.radians(45 * k + 22.5)):.1f},{cy + r * math.sin(math.radians(45 * k + 22.5)):.1f}" for k in range(8))
        frame_svg = f'<polygon points="{pts}" fill="{hl_bg}" stroke="rgba(255,255,255,0.3)" stroke-width="2.5"/>'
    elif shape == "diamond_rhombus":
        r = side * 0.56
        pts = f"{cx:.1f},{cy-r:.1f} {cx+r:.1f},{cy:.1f} {cx:.1f},{cy+r:.1f} {cx-r:.1f},{cy:.1f}"
        frame_svg = f'<polygon points="{pts}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
    elif shape == "circle_clean":
        r = side * 0.50
        frame_svg = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2.5"/>'
    elif shape in ("orbital_rings", "circle"):
        r = side * 0.46
        frame_svg = (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+18:.1f}" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="1.8" stroke-dasharray="8,6"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
        )
    elif shape == "starburst_seal":
        pts_list = []
        n_pts = 24
        for k in range(n_pts * 2):
            rad = side * (0.54 if k % 2 == 0 else 0.46)
            ang = math.pi * k / n_pts
            pts_list.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
        frame_svg = f'<polygon points="{" ".join(pts_list)}" fill="{hl_bg}" stroke="{accent}" stroke-width="2"/>'
    elif shape == "squircle_super":
        frame_svg = f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="{int(side*0.32)}" fill="{hl_bg}" stroke="rgba(255,255,255,0.3)" stroke-width="2.5"/>'
    elif shape == "arch_window":
        r = side / 2
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        d = f"M{x1:.1f},{y1+r:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2:.1f},{y1+r:.1f} V{y2:.1f} H{x1:.1f} Z"
        frame_svg = f'<path d="{d}" fill="{hl_bg}" stroke="rgba(255,255,255,0.3)" stroke-width="2.5"/>'
    elif shape == "folder_tab_box":
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        d = f"M{x1:.1f},{y1-14:.1f} H{x1+side*0.42:.1f} L{x1+side*0.50:.1f},{y1:.1f} H{x2:.1f} V{y2:.1f} H{x1:.1f} Z"
        frame_svg = f'<path d="{d}" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2.2"/>'
    elif shape == "browser_window":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="12" fill="{hl_bg}" stroke="rgba(255,255,255,0.3)" stroke-width="2"/>'
            f'<line x1="{bx:.1f}" y1="{by+28:.1f}" x2="{bx+side:.1f}" y2="{by+28:.1f}" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/>'
            f'<circle cx="{bx+18:.1f}" cy="{by+14:.1f}" r="4.5" fill="#ef4444"/>'
            f'<circle cx="{bx+32:.1f}" cy="{by+14:.1f}" r="4.5" fill="#f59e0b"/>'
            f'<circle cx="{bx+46:.1f}" cy="{by+14:.1f}" r="4.5" fill="#10b981"/>'
        )
    elif shape == "crosshair_grid_box":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{hl_bg}" stroke="rgba(255,255,255,0.35)" stroke-width="2"/>'
            f'<line x1="{cx:.1f}" y1="{by:.1f}" x2="{cx:.1f}" y2="{by+side:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" stroke-dasharray="6,6"/>'
            f'<line x1="{bx:.1f}" y1="{cy:.1f}" x2="{bx+side:.1f}" y2="{cy:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" stroke-dasharray="6,6"/>'
        )
    elif shape == "glow_neon_box":
        frame_svg = (
            f'<rect x="{bx-6:.1f}" y="{by-6:.1f}" width="{side+12:.1f}" height="{side+12:.1f}" rx="18" fill="none" stroke="{accent}" stroke-opacity="0.4" stroke-width="4"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="14" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
        )
    elif shape == "isometric_stack":
        frame_svg = (
            f'<rect x="{bx+16:.1f}" y="{by+16:.1f}" width="{side:.1f}" height="{side:.1f}" rx="8" fill="{hl_bg}" fill-opacity="0.35" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/>'
            f'<rect x="{bx+8:.1f}" y="{by+8:.1f}" width="{side:.1f}" height="{side:.1f}" rx="8" fill="{hl_bg}" fill-opacity="0.65" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="8" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
        )
    else:
        frame_svg = f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="6" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2.5"/>'

    return f"""
    <g id="showcaseBoxComponent">
      {frame_svg}
      {hero_paths}
    </g>"""


def _extract_highlight_svg(model: Model, icons_meta: list[dict], hl_mode: str, count: int, hl_stroke: str, stroke_scale: float,
                           inner_w: float, inner_h: float, ox: float, oy: float, cols: int = 2, highlight_index: int = 0) -> str:
    avail_icons = icons_meta or []
    if not avail_icons:
        return ""
    if hl_mode == "hero_1":
        idx = max(0, min(len(avail_icons) - 1, int(highlight_index)))
        ic = avail_icons[idx]
        ic_paths = _extract_icon_paths(model, ic["box"], icon_obj=ic)
        if not ic_paths:
            return ""
        valid_pts = [p.A for p in ic_paths if len(p.A) > 0]
        if valid_pts:
            all_pts = np.concatenate(valid_pts)
            bx1, bx2 = float(np.min(all_pts[:, 0])), float(np.max(all_pts[:, 0]))
            by1, by2 = float(np.min(all_pts[:, 1])), float(np.max(all_pts[:, 1]))
        else:
            bx1, by1, bx2, by2 = ic["box"]
        bw, bh = max(1.0, bx2 - bx1), max(1.0, by2 - by1)
        hero_size = min(inner_w * 0.72, inner_h * 0.72)
        h_scale = hero_size / max(bw, bh)
        h_ox = ox + (inner_w - bw * h_scale) / 2 - bx1 * h_scale
        h_oy = oy + (inner_h - bh * h_scale) / 2 - by1 * h_scale
        return _render_paths_svg(ic_paths, hl_stroke, stroke_scale, h_scale, h_ox, h_oy)

    start_idx = max(0, min(len(avail_icons) - 1, int(highlight_index)))
    rows = max(1, math.ceil(count / cols))
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    rendered = []
    for k in range(min(count, len(avail_icons))):
        i = (start_idx + k) % len(avail_icons)
        ic = avail_icons[i]
        ic_paths = _extract_icon_paths(model, ic["box"], icon_obj=ic)
        if not ic_paths:
            continue
        valid_pts = [p.A for p in ic_paths if len(p.A) > 0]
        if valid_pts:
            all_pts = np.concatenate(valid_pts)
            bx1, bx2 = float(np.min(all_pts[:, 0])), float(np.max(all_pts[:, 0]))
            by1, by2 = float(np.min(all_pts[:, 1])), float(np.max(all_pts[:, 1]))
        else:
            bx1, by1, bx2, by2 = ic["box"]
        bw, bh = max(1.0, bx2 - bx1), max(1.0, by2 - by1)
        col_i = k % cols
        row_i = k // cols
        target_cell = min(cell_w * 0.62, cell_h * 0.62)
        ic_scale = target_cell / max(bw, bh)
        cx = ox + col_i * cell_w + (cell_w - bw * ic_scale) / 2 - bx1 * ic_scale
        cy = oy + row_i * cell_h + (cell_h - bh * ic_scale) / 2 - by1 * ic_scale
        rendered.append(_render_paths_svg(ic_paths, hl_stroke, stroke_scale, ic_scale, cx, cy))
    return "\n        ".join(rendered)


# =========================================================================
# 25 Cover / Banner Shapes (Category 1 — Default: Square Solid Box)
# =========================================================================
def _render_cover_shape_svg(
    banner_shape: str, x: float, y: float, w: float, h: float,
    banner_bg: str, hl_bg: str, accent: str, is_right: bool = False
) -> str:
    shape = str(banner_shape or "square_solid").lower()
    pad = int(min(w, h) * 0.04)

    # For right-side panels, we mirror horizontal custom paths around panel center if needed
    transform_open = f'<g transform="translate({2*x+w:.1f}, 0) scale(-1, 1)">' if (is_right and shape not in ("square_solid", "rounded_card", "double_split_box", "floating_island", "arch_dome")) else "<g>"
    transform_close = "</g>"

    if shape == "square_solid":
        body = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{banner_bg}"/>'
    elif shape == "rounded_card":
        body = f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="32" fill="{banner_bg}"/>'
    elif shape == "double_split_box":
        top_h = int(h * 0.54)
        body = (
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{top_h-pad:.1f}" rx="20" fill="{banner_bg}"/>'
            f'<rect x="{x+pad:.1f}" y="{y+top_h+pad//2:.1f}" width="{w-pad*2:.1f}" height="{h-top_h-pad*1.5:.1f}" rx="20" fill="{hl_bg}" fill-opacity="0.25"/>'
        )
    elif shape == "chamfer_box":
        c = 44
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        pts = f"{x1+c:.1f},{y1:.1f} {x2-c:.1f},{y1:.1f} {x2:.1f},{y1+c:.1f} {x2:.1f},{y2-c:.1f} {x2-c:.1f},{y2:.1f} {x1+c:.1f},{y2:.1f} {x1:.1f},{y2-c:.1f} {x1:.1f},{y1+c:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}"/>'
    elif shape == "notched_ticket":
        r = 36
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        d = f"M{x1+r:.1f},{y1:.1f} H{x2-r:.1f} A{r},{r} 0 0,0 {x2:.1f},{y1+r:.1f} V{y2-r:.1f} A{r},{r} 0 0,0 {x2-r:.1f},{y2:.1f} H{x1+r:.1f} A{r},{r} 0 0,0 {x1:.1f},{y2-r:.1f} V{y1+r:.1f} A{r},{r} 0 0,0 {x1+r:.1f},{y1:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "curved_right":
        d = f"M{x:.1f},{y:.1f} L{x+w*0.86:.1f},{y:.1f} Q{x+w*1.12:.1f},{y+h*0.5:.1f} {x+w*0.86:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "concave_arch":
        d = f"M{x:.1f},{y:.1f} L{x+w:.1f},{y:.1f} Q{x+w*0.78:.1f},{y+h*0.5:.1f} {x+w:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("s_wave_smooth", "wave_flow"):
        d = f"M{x:.1f},{y:.1f} L{x+w*0.92:.1f},{y:.1f} C{x+w*1.15:.1f},{y+h*0.30:.1f} {x+w*0.72:.1f},{y+h*0.70:.1f} {x+w*0.98:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "double_wave":
        d1 = f"M{x:.1f},{y:.1f} L{x+w*0.96:.1f},{y:.1f} C{x+w*1.18:.1f},{y+h*0.32:.1f} {x+w*0.74:.1f},{y+h*0.68:.1f} {x+w*1.02:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d2 = f"M{x:.1f},{y:.1f} L{x+w*0.86:.1f},{y:.1f} C{x+w*1.08:.1f},{y+h*0.35:.1f} {x+w*0.64:.1f},{y+h*0.65:.1f} {x+w*0.90:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d1}" fill="{banner_bg}" fill-opacity="0.45"/><path d="{d2}" fill="{banner_bg}"/>'
    elif shape == "triple_liquid":
        d1 = f"M{x:.1f},{y:.1f} L{x+w*1.02:.1f},{y:.1f} C{x+w*1.20:.1f},{y+h*0.25:.1f} {x+w*0.78:.1f},{y+h*0.75:.1f} {x+w*1.04:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d2 = f"M{x:.1f},{y:.1f} L{x+w*0.94:.1f},{y:.1f} C{x+w*1.12:.1f},{y+h*0.30:.1f} {x+w*0.70:.1f},{y+h*0.70:.1f} {x+w*0.96:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d3 = f"M{x:.1f},{y:.1f} L{x+w*0.85:.1f},{y:.1f} C{x+w*1.02:.1f},{y+h*0.35:.1f} {x+w*0.62:.1f},{y+h*0.65:.1f} {x+w*0.88:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d1}" fill="{accent}" fill-opacity="0.35"/><path d="{d2}" fill="{banner_bg}" fill-opacity="0.65"/><path d="{d3}" fill="{banner_bg}"/>'
    elif shape == "diagonal_slash":
        pts1 = f"{x:.1f},{y:.1f} {x+w*1.04:.1f},{y:.1f} {x+w*0.84:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        pts2 = f"{x+w*1.06:.1f},{y:.1f} {x+w*1.10:.1f},{y:.1f} {x+w*0.90:.1f},{y+h:.1f} {x+w*0.86:.1f},{y+h:.1f}"
        body = f'<polygon points="{pts1}" fill="{banner_bg}"/><polygon points="{pts2}" fill="{accent}"/>'
    elif shape == "dual_chevron":
        pts1 = f"{x:.1f},{y:.1f} {x+w*0.88:.1f},{y:.1f} {x+w*1.04:.1f},{y+h*0.5:.1f} {x+w*0.88:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        pts2 = f"{x+w*0.92:.1f},{y:.1f} {x+w*0.97:.1f},{y:.1f} {x+w*1.13:.1f},{y+h*0.5:.1f} {x+w*0.97:.1f},{y+h:.1f} {x+w*0.92:.1f},{y+h:.1f} {x+w*1.08:.1f},{y+h*0.5:.1f}"
        body = f'<polygon points="{pts1}" fill="{banner_bg}"/><polygon points="{pts2}" fill="{accent}" fill-opacity="0.65"/>'
    elif shape == "origami_fold":
        p1 = f"{x:.1f},{y:.1f} {x+w*0.96:.1f},{y:.1f} {x+w*0.80:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        p2 = f"{x+w*0.96:.1f},{y:.1f} {x+w*1.08:.1f},{y+h*0.42:.1f} {x+w*0.80:.1f},{y+h:.1f}"
        body = f'<polygon points="{p1}" fill="{banner_bg}"/><polygon points="{p2}" fill="{banner_bg}" fill-opacity="0.6"/>'
    elif shape == "stepped_blocks":
        h3 = h / 3.0
        body = (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w*0.98:.1f}" height="{h3+2:.1f}" fill="{banner_bg}"/>'
            f'<rect x="{x:.1f}" y="{y+h3:.1f}" width="{w*0.92:.1f}" height="{h3+2:.1f}" fill="{banner_bg}"/>'
            f'<rect x="{x:.1f}" y="{y+h3*2:.1f}" width="{w*0.86:.1f}" height="{h3:.1f}" fill="{banner_bg}"/>'
        )
    elif shape in ("hexagon_panel", "hexagon_shield"):
        pts = f"{x:.1f},{y:.1f} {x+w*0.88:.1f},{y:.1f} {x+w*1.02:.1f},{y+h*0.25:.1f} {x+w*1.02:.1f},{y+h*0.75:.1f} {x+w*0.88:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}"/>'
    elif shape in ("leaf_organic", "eco_leaf"):
        d = f"M{x:.1f},{y:.1f} L{x+w*0.86:.1f},{y:.1f} C{x+w*1.12:.1f},{y+h*0.22:.1f} {x+w*1.12:.1f},{y+h*0.78:.1f} {x+w*0.72:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("droplet_curve", "droplet_flow"):
        d = f"M{x:.1f},{y:.1f} L{x+w*0.78:.1f},{y:.1f} C{x+w*0.78:.1f},{y+h*0.35:.1f} {x+w*1.14:.1f},{y+h*0.62:.1f} {x+w*0.86:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "scallop_edge":
        circles = []
        n_sc = 9
        r_sc = (h / n_sc) * 0.62
        for k in range(n_sc):
            cy_k = y + (k + 0.5) * (h / n_sc)
            circles.append(f'<circle cx="{x+w*0.88:.1f}" cy="{cy_k:.1f}" r="{r_sc:.1f}" fill="{banner_bg}"/>')
        body = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w*0.88:.1f}" height="{h:.1f}" fill="{banner_bg}"/>' + "".join(circles)
    elif shape == "zigzag_saw":
        pts = [f"{x:.1f},{y:.1f}", f"{x+w*0.90:.1f},{y:.1f}"]
        n_z = 12
        step_y = h / n_z
        for k in range(n_z):
            pts.append(f"{x+w*0.98:.1f},{y+(k+0.5)*step_y:.1f}")
            pts.append(f"{x+w*0.90:.1f},{y+(k+1.0)*step_y:.1f}")
        pts.append(f"{x:.1f},{y+h:.1f}")
        body = f'<polygon points="{" ".join(pts)}" fill="{banner_bg}"/>'
    elif shape == "ribbon_banner":
        x1, y1, x2, y2 = x + pad, y, x + w - pad, y + h - pad
        pts = f"{x1:.1f},{y1:.1f} {x2:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x+w/2:.1f},{y2-56:.1f} {x1:.1f},{y2:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}"/>'
    elif shape == "floating_island":
        body = (
            f'<rect x="{x+pad+14:.1f}" y="{y+pad+18:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="28" fill="#000000" fill-opacity="0.22"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="28" fill="{banner_bg}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="3"/>'
        )
    elif shape == "layered_cards":
        body = (
            f'<rect x="{x+pad+24:.1f}" y="{y+pad+24:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="20" fill="{banner_bg}" fill-opacity="0.35"/>'
            f'<rect x="{x+pad+12:.1f}" y="{y+pad+12:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="20" fill="{banner_bg}" fill-opacity="0.65"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="20" fill="{banner_bg}"/>'
        )
    elif shape == "cyber_hud_frame":
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        pts = f"{x1:.1f},{y1:.1f} {x2-48:.1f},{y1:.1f} {x2:.1f},{y1+48:.1f} {x2:.1f},{y2-80:.1f} {x2-28:.1f},{y2-52:.1f} {x2-28:.1f},{y2:.1f} {x1+36:.1f},{y2:.1f} {x1:.1f},{y2-36:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}" stroke="{accent}" stroke-width="4"/>'
    elif shape == "arch_dome":
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        r = (x2 - x1) / 2
        d = f"M{x1:.1f},{y1+r:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2:.1f},{y1+r:.1f} V{y2:.1f} H{x1:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("pixel_dissolve", "pixel_matrix"):
        solid_w = w * 0.84
        sq = 44
        rects = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{solid_w:.1f}" height="{h:.1f}" fill="{banner_bg}"/>']
        for r_i in range(int(h // sq)):
            for c_i in range(3):
                if (r_i * 7 + c_i * 3) % 5 < (3 - c_i):
                    px = x + solid_w + c_i * sq
                    py = y + r_i * sq
                    rects.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{sq-4}" height="{sq-4}" rx="4" fill="{banner_bg}" fill-opacity="{0.85 - c_i*0.25:.2f}"/>')
        body = "".join(rects)
    else:
        body = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{banner_bg}"/>'

    return f"{transform_open}{body}{transform_close}"


# =========================================================================
# Cover Decorative Patterns (Category 4 Subset)
# =========================================================================
def _render_cover_decor_svg(decor: str, x: float, y: float, w: float, h: float, banner_text: str, accent: str) -> str:
    decor = str(decor or "").lower()
    col = banner_text
    if decor == "cover_halftone_dots":
        dots = []
        cx, cy = x + w / 2, y + h * 0.5
        for ring_r, dot_r, n in [(140, 4, 16), (220, 6, 24), (300, 8, 32), (380, 5, 36)]:
            for i in range(n):
                ang = 2 * math.pi * i / n
                dots.append(f'<circle cx="{cx+ring_r*math.cos(ang):.1f}" cy="{cy+ring_r*math.sin(ang):.1f}" r="{dot_r}" fill="{col}" opacity="0.12"/>')
        return "<g>" + "".join(dots) + "</g>"
    elif decor == "cover_diagonal_stripes":
        lines = []
        for k in range(-10, 30):
            y_k = y + k * 90
            lines.append(f'<line x1="{x:.1f}" y1="{y_k:.1f}" x2="{x+w:.1f}" y2="{y_k-w*0.6:.1f}" stroke="{col}" stroke-width="14" opacity="0.06"/>')
        return "<g>" + "".join(lines) + "</g>"
    elif decor == "cover_circuit_traces":
        return f"""
        <g stroke="{col}" stroke-width="2.5" opacity="0.16" fill="none">
          <path d="M{x+30:.1f},{y+40:.1f} H{x+140:.1f} L{x+180:.1f},{y+80:.1f} V{y+220:.1f}"/>
          <circle cx="{x+180:.1f}" cy="{y+220:.1f}" r="6" fill="{col}"/>
          <path d="M{x+w-40:.1f},{y+h-60:.1f} H{x+w-160:.1f} L{x+w-210:.1f},{y+h-110:.1f} V{y+h-280:.1f}"/>
          <circle cx="{x+w-210:.1f}" cy="{y+h-280:.1f}" r="6" fill="{col}"/>
        </g>"""
    elif decor == "cover_blueprint_grid":
        step = 80
        v_lines = "".join(f'<line x1="{x+i*step:.1f}" y1="{y:.1f}" x2="{x+i*step:.1f}" y2="{y+h:.1f}"/>' for i in range(1, int(w // step) + 1))
        h_lines = "".join(f'<line x1="{x:.1f}" y1="{y+j*step:.1f}" x2="{x+w:.1f}" y2="{y+j*step:.1f}"/>' for j in range(1, int(h // step) + 1))
        return f'<g stroke="{col}" stroke-width="1.2" opacity="0.10">{v_lines}{h_lines}</g>'
    elif decor == "cover_concentric_rings":
        cx, cy = x + w / 2, y + h * 0.48
        rings = "".join(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{col}" stroke-width="2" opacity="0.10"/>' for r in (120, 200, 280, 360, 440))
        return f"<g>{rings}</g>"
    elif decor == "cover_geometric_poly":
        return f"""
        <g fill="{col}" opacity="0.08">
          <polygon points="{x:.1f},{y:.1f} {x+w*0.6:.1f},{y:.1f} {x:.1f},{y+h*0.35:.1f}"/>
          <polygon points="{x+w:.1f},{y+h:.1f} {x+w*0.3:.1f},{y+h:.1f} {x+w:.1f},{y+h*0.6:.1f}"/>
        </g>"""
    elif decor == "cover_dot_matrix":
        dots = []
        for r_i in range(5):
            for c_i in range(5):
                dots.append(f'<circle cx="{x+40+c_i*22:.1f}" cy="{y+40+r_i*22:.1f}" r="3.5" fill="{col}" opacity="0.22"/>')
                dots.append(f'<circle cx="{x+w-130+c_i*22:.1f}" cy="{y+h-130+r_i*22:.1f}" r="3.5" fill="{col}" opacity="0.22"/>')
        return "<g>" + "".join(dots) + "</g>"
    elif decor == "cover_floating_shapes":
        return f"""
        <g stroke="{col}" stroke-width="3" opacity="0.18" fill="none">
          <circle cx="{x+64:.1f}" cy="{y+84:.1f}" r="18"/>
          <rect x="{x+w-96:.1f}" y="{y+70:.1f}" width="32" height="32" rx="4"/>
          <path d="M{x+56:.1f},{y+h-80:.1f} h28 M{x+70:.1f},{y+h-94:.1f} v28"/>
          <polygon points="{x+w-70:.1f},{y+h-96:.1f} {x+w-50:.1f},{y+h-60:.1f} {x+w-90:.1f},{y+h-60:.1f}"/>
        </g>"""
    elif decor == "cover_chevron_stripes":
        stripes = []
        for k in range(6):
            yk = y + 60 + k * 36
            stripes.append(f'<polyline points="{x+32:.1f},{yk:.1f} {x+52:.1f},{yk-14:.1f} {x+72:.1f},{yk:.1f}" fill="none" stroke="{col}" stroke-width="4" opacity="0.20"/>')
        return "<g>" + "".join(stripes) + "</g>"
    return ""


# =========================================================================
# Master Modular Template Maker Compositor
# =========================================================================
def _build_modular_template(model: Model, icons_meta: list[dict], c: dict, W: int, H: int, banner_w: int) -> str:
    stroke_scale = float(c.get("stroke_scale", 1.0))
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    panel_pos = str(c.get("panel_pos") or "left").lower()
    banner_shape = str(c.get("banner_shape") or "square_solid").lower()
    title_hl_style = str(c.get("title_highlight") or "solid_square").lower()
    decor = str(c.get("decor_element") or "artboard_square_box").lower()

    artboard_bg = c.get("artboard_bg", "checkered")
    defs_svg = ""
    if artboard_bg == "checkered":
        d_svg, sheet_bg_fill = _get_checkered_defs(W)
        defs_svg = d_svg
    else:
        sheet_bg_fill = artboard_bg

    banner_bg = c["banner_bg"]
    banner_text = c["banner_text"]
    banner_sub = c["banner_sub"]
    hl_bg = c["highlight_bg"]
    accent = c.get("shape_accent") or c.get("accent") or ""
    show_highlight = c.get("show_highlight", True)

    fonts_import, title_font, count_font, sub_font = _get_font_css(c.get("font_family", "bebas"))

    # Horizontal Top or Bottom Bar Mode
    if panel_pos in ("top", "bottom"):
        bar_h = int(round(H * 0.24))
        is_bottom = (panel_pos == "bottom")
        bar_y = (H - bar_h) if is_bottom else 0
        sheet_y = 0 if is_bottom else bar_h
        sheet_h = H - bar_h

        paths_svg_group = _render_adaptive_sheet_icons(
            model, icons_meta, c,
            sheet_x=0, sheet_y=sheet_y, sheet_w=W, sheet_h=sheet_h
        )

        title_fs = int(c.get("title_fs") or 0) or max(36, int(round(bar_h * 0.24)))
        count_fs = int(c.get("count_fs") or 0) or max(84, int(round(bar_h * 0.46)))
        sub_fs = int(c.get("sub_fs") or 0) or max(16, int(round(bar_h * 0.09)))

        title_svg = _render_title_highlight(
            title=c["title"], subtitle=c["subtitle"],
            cx=int(W * 0.34), cy=bar_y + int(bar_h * 0.44),
            title_fs=title_fs, sub_fs=sub_fs,
            banner_text=banner_text, banner_sub=banner_sub,
            title_font=title_font, sub_font=sub_font,
            style=title_hl_style, is_centered=True,
            max_w=W * 0.38, accent=accent
        )

        hl_svg = ""
        if show_highlight:
            sc_size = int(bar_h * 0.82)
            hl_svg = _render_showcase_box(
                model, icons_meta, c,
                cx=W - int(W * 0.12), cy=bar_y + bar_h / 2,
                w=sc_size, h=sc_size, stroke_scale=stroke_scale
            )

        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      {fonts_import}
      text {{ font-family: {sub_font}; }}
      .title {{ font-family: {title_font}; }}
      .count {{ font-family: {count_font}; }}
      .sub {{ font-family: {sub_font}; }}
      .mono {{ font-family: 'JetBrains Mono', 'Consolas', monospace; }}
    </style>{defs_svg}
  </defs>
  <rect x="0" y="{sheet_y}" width="{W}" height="{sheet_h}" fill="{sheet_bg_fill}"/>
  <g id="stockIconSheet">
    {paths_svg_group}
  </g>
  <g id="stockCoverBar">
    <rect x="0" y="{bar_y}" width="{W}" height="{bar_h}" fill="{banner_bg}"/>
    <text x="{int(W * 0.09)}" y="{bar_y + int(bar_h * 0.66)}" font-size="{count_fs}" font-weight="900" fill="{banner_text}" text-anchor="middle" class="count">{sanitize_text(count_val)}</text>
    {title_svg}
    {hl_svg}
  </g>
</svg>"""

    # Left or Right Vertical Cover Panel + Square Icon Set Box
    is_right = (panel_pos == "right")
    sheet_w = W - banner_w
    sheet_h = H
    sheet_x = 0 if is_right else banner_w
    panel_x = (W - banner_w) if is_right else 0

    paths_svg_group = _render_adaptive_sheet_icons(
        model, icons_meta, c,
        sheet_x=sheet_x, sheet_y=0, sheet_w=sheet_w, sheet_h=sheet_h
    )

    cover_shape_svg = _render_cover_shape_svg(
        banner_shape, panel_x, 0, banner_w, H,
        banner_bg, hl_bg, accent or hl_bg, is_right=is_right
    )
    cover_decor_svg = _render_cover_decor_svg(
        decor, panel_x, 0, banner_w, H, banner_text, accent or hl_bg
    )

    inner_cx = panel_x + banner_w * 0.48 if not is_right else panel_x + banner_w * 0.52
    inner_w = banner_w * 0.80

    title_fs = int(c.get("title_fs") or 0) or max(36, int(round(banner_w * 0.082)))
    count_fs = int(c.get("count_fs") or 0) or max(96, int(round(banner_w * 0.30)))
    sub_fs = int(c.get("sub_fs") or 0) or max(16, int(round(banner_w * 0.044)))

    if show_highlight:
        title_cy = int(H * 0.12)
        count_cy = int(H * 0.42)
        box_cy = int(H * 0.72)
        box_size = min(inner_w * 0.86, H * 0.40)
    else:
        title_cy = int(H * 0.28)
        count_cy = int(H * 0.64)
        box_cy = 0
        box_size = 0

    title_svg = _render_title_highlight(
        title=c["title"], subtitle=c["subtitle"],
        cx=inner_cx, cy=title_cy,
        title_fs=title_fs, sub_fs=sub_fs,
        banner_text=banner_text, banner_sub=banner_sub,
        title_font=title_font, sub_font=sub_font,
        style=title_hl_style, is_centered=True,
        max_w=inner_w, accent=accent
    )

    hl_svg = ""
    if show_highlight and box_size > 80:
        hl_svg = _render_showcase_box(
            model, icons_meta, c,
            cx=inner_cx, cy=box_cy,
            w=box_size, h=box_size,
            stroke_scale=stroke_scale
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      {fonts_import}
      text {{ font-family: {sub_font}; }}
      .title {{ font-family: {title_font}; }}
      .count {{ font-family: {count_font}; }}
      .sub {{ font-family: {sub_font}; }}
      .mono {{ font-family: 'JetBrains Mono', 'Consolas', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="stockSideBanner">
    {cover_shape_svg}
    {cover_decor_svg}
    {title_svg}

    <text x="{inner_cx:.1f}" y="{count_cy}"
          font-size="{count_fs}" font-weight="900" fill="{banner_text}" letter-spacing="-3"
          text-anchor="middle" class="count">
      {sanitize_text(count_val)}
    </text>

    {hl_svg}
  </g>
</svg>"""


# =========================================================================
# Master SVG Dispatcher
# =========================================================================
def build_template_svg(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate high-resolution SVG presentation sheet using the Modular Template Maker Engine."""
    c = resolve_config(config)
    icons_meta = icons_meta or []

    # Map legacy design names to modular settings if passed
    design = str(c.get("design") or "modular_maker").lower()
    if design == "vectuz_right" or design == "side_cover_right":
        c["panel_pos"] = "right"
    elif design == "top_banner":
        c["panel_pos"] = "top"
    elif design == "bottom_dock":
        c["panel_pos"] = "bottom"
    elif design in ("wave_flow", "eco_leaf", "droplet_flow", "origami_fold", "diagonal_slash", "pixel_matrix"):
        if c.get("banner_shape") == "square_solid":
            c["banner_shape"] = design

    mW, mH = max(10, model.width), max(10, model.height)
    layout = c.get("layout", "landscape_16_9")
    W, H, banner_w = _calc_dims(layout, mW, mH)

    return _build_modular_template(model, icons_meta, c, W, H, banner_w)


# =========================================================================
# EPS 3.0 Export
# =========================================================================
def build_template_eps(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate professional Adobe-standard Encapsulated PostScript (EPS 3.0) presentation template."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))

    mW, mH = max(10, model.width), max(10, model.height)
    layout = c.get("layout", "landscape_16_9")
    W, H, banner_w = _calc_dims(layout, mW, mH)

    sheet_x = banner_w
    sheet_w = W - banner_w
    sheet_h = H

    avail_w = sheet_w * 0.88
    avail_h = sheet_h * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (sheet_h - target_h) / 2

    bbg_r, bbg_g, bbg_b = hex_to_rgb(c["banner_bg"])
    stk_r, stk_g, stk_b = hex_to_rgb(c["icon_stroke"])
    hlbg_r, hlbg_g, hlbg_b = hex_to_rgb(c["highlight_bg"])
    stroke_scale = float(c["stroke_scale"])

    banner_pad = int(banner_w * 0.10)
    inner_w = banner_w - (banner_pad * 2)
    top_h = int(round(H * 0.54))

    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Stock Presentation Engine",
        f"%%Title: {escape_ps_text(c['title'])} - {count_val} Icons",
        f"%%BoundingBox: 0 0 {W} {H}",
        f"%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%Pages: 1",
        "%%EndComments",
        "",
        "/M { moveto } bind def",
        "/L { lineto } bind def",
        "/C { curveto } bind def",
        "/CP { closepath } bind def",
        "/S { stroke } bind def",
        "/F { fill } bind def",
        "/RGB { setrgbcolor } bind def",
        "/LW { setlinewidth } bind def",
        "/LC { setlinecap } bind def",
        "/LJ { setlinejoin } bind def",
        "",
        f"0 {H} translate",
        "1 -1 scale",
        "",
        "1 1 1 RGB",
        f"0 0 {W} {H} rectfill",
        f"{bbg_r:.3f} {bbg_g:.3f} {bbg_b:.3f} RGB",
        f"{banner_pad} {int(round(H * 0.035))} {inner_w} {top_h} rectfill",
        f"{hlbg_r:.3f} {hlbg_g:.3f} {hlbg_b:.3f} RGB",
        f"{banner_pad} {top_h + int(round(H * 0.025))} {inner_w} {H - top_h - int(round(H * 0.06))} rectfill",
        "",
        "1 LC 1 LJ",
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
    ]

    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        s = p.segs()
        if not s:
            continue
        p0 = s[0][0] * scale + np.array([off_x, off_y])
        lines.append(f"{p0[0]:.2f} {p0[1]:.2f} M")
        for c_seg in s:
            p1 = c_seg[1] * scale + np.array([off_x, off_y])
            p2 = c_seg[2] * scale + np.array([off_x, off_y])
            p3 = c_seg[3] * scale + np.array([off_x, off_y])
            lines.append(f"{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.append("%%EOF")
    return "\n".join(lines)


def build_model_eps(model: Model, stroke_color: str = "#000000", stroke_scale: float = 1.0, bg: str | None = None) -> str:
    """Generate clean Adobe Illustrator compatible EPS 3.0 vector file from a Model."""
    W = int(model.width) or 1000
    H = int(model.height) or 1000
    stk_r, stk_g, stk_b = hex_to_rgb(stroke_color)
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Vector Precision Engine",
        f"%%BoundingBox: 0 0 {W} {H}",
        f"%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%Pages: 1",
        "%%EndComments",
        "",
        "/M { moveto } bind def",
        "/L { lineto } bind def",
        "/C { curveto } bind def",
        "/CP { closepath } bind def",
        "/S { stroke } bind def",
        "/F { fill } bind def",
        "/RGB { setrgbcolor } bind def",
        "/LW { setlinewidth } bind def",
        "/LC { setlinecap } bind def",
        "/LJ { setlinejoin } bind def",
        "",
        f"0 {H} translate",
        "1 -1 scale",
    ]
    if bg and bg.lower() not in ("none", "transparent"):
        bg_r, bg_g, bg_b = hex_to_rgb(bg)
        lines += [
            f"{bg_r:.3f} {bg_g:.3f} {bg_b:.3f} RGB",
            f"0 0 {W} {H} rectfill",
        ]
    lines += [
        "1 LC 1 LJ",
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
    ]
    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        s = p.segs()
        if not s:
            continue
        lines.append(f"{s[0][0][0]:.2f} {s[0][0][1]:.2f} M")
        for c_seg in s:
            lines.append(f"{c_seg[1][0]:.2f} {c_seg[1][1]:.2f} {c_seg[2][0]:.2f} {c_seg[2][1]:.2f} {c_seg[3][0]:.2f} {c_seg[3][1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")
    lines.append("%%EOF")
    return "\n".join(lines)


# =========================================================================
# 24-Icon Live Demo Vector Sheet
# =========================================================================
def make_line_path(points, w=4.0, closed=False):
    pts = np.asarray(points, float)
    N = len(pts)
    A = pts.copy()
    Hin = np.zeros_like(A)
    Hout = np.zeros_like(A)
    for i in range(N - 1):
        p0 = A[i]
        p1 = A[i + 1]
        Hout[i] = p0 + (p1 - p0) / 3.0
        Hin[i + 1] = p0 + 2.0 * (p1 - p0) / 3.0
    if closed:
        p0 = A[-1]
        p1 = A[0]
        Hout[-1] = p0 + (p1 - p0) / 3.0
        Hin[0] = p0 + 2.0 * (p1 - p0) / 3.0
    return Path(A, Hin, Hout, w, closed=closed)


def make_circle_path(cx, cy, r, w=4.0):
    k = 0.5522847498 * r
    A = np.array([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy], [cx, cy - r]], float)
    Hout = np.array([[cx + k, cy - r], [cx + r, cy + k], [cx - k, cy + r], [cx - r, cy - k], [cx + k, cy - r]], float)
    Hin = np.array([[cx - k, cy - r], [cx + r, cy - k], [cx + k, cy + r], [cx - r, cy + k], [cx - k, cy - r]], float)
    return Path(A, Hin, Hout, w, closed=True)


_CACHED_DEMO_DATA = None


def generate_demo_sheet() -> tuple[Model, list[dict]]:
    """Generates a high-quality 24-icon demo vector sheet for instant Template Studio design and preview."""
    global _CACHED_DEMO_DATA
    if _CACHED_DEMO_DATA is not None:
        m, icons = _CACHED_DEMO_DATA
        return m.copy(), [dict(ic) for ic in icons]

    paths = []
    icons = []
    w = 4.0
    for idx in range(24):
        col = idx % 6
        row = idx // 6
        cx = col * 400 + 200
        cy = row * 400 + 200
        icons.append({'id': f'icon_{idx}', 'box': [cx - 110, cy - 110, cx + 110, cy + 110], 'status': 'done'})

        if idx == 0:  # Search
            paths.append(make_circle_path(cx - 10, cy - 10, 36, w))
            paths.append(make_line_path([[cx + 15, cy + 15], [cx + 46, cy + 46]], w * 1.2))
        elif idx == 1:  # Settings
            paths.append(make_circle_path(cx, cy, 24, w))
            for a in range(0, 360, 45):
                rad = math.radians(a)
                p1 = [cx + 32 * math.cos(rad), cy + 32 * math.sin(rad)]
                p2 = [cx + 46 * math.cos(rad), cy + 46 * math.sin(rad)]
                paths.append(make_line_path([p1, p2], w * 1.3))
        elif idx == 2:  # User
            paths.append(make_circle_path(cx, cy - 22, 22, w))
            paths.append(make_line_path([[cx - 46, cy + 46], [cx - 36, cy + 18], [cx, cy + 12], [cx + 36, cy + 18], [cx + 46, cy + 46]], w))
        elif idx == 3:  # Home
            paths.append(make_line_path([[cx - 52, cy - 5], [cx, cy - 50], [cx + 52, cy - 5]], w))
            paths.append(make_line_path([[cx - 40, cy - 5], [cx - 40, cy + 48], [cx + 40, cy + 48], [cx + 40, cy - 5]], w))
            paths.append(make_line_path([[cx - 16, cy + 48], [cx - 16, cy + 16], [cx + 16, cy + 16], [cx + 16, cy + 48]], w))
        elif idx == 4:  # Heart
            pts = [[cx, cy + 44], [cx - 46, cy + 6], [cx - 38, cy - 32], [cx - 16, cy - 40], [cx, cy - 18], [cx + 16, cy - 40], [cx + 38, cy - 32], [cx + 46, cy + 6], [cx, cy + 44]]
            paths.append(make_line_path(pts, w, closed=True))
        elif idx == 5:  # Star
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                r = 48 if i % 2 == 0 else 22
                pts.append([cx + r * math.cos(ang), cy + r * math.sin(ang)])
            paths.append(make_line_path(pts, w, closed=True))
        elif idx == 6:  # Mail
            paths.append(make_line_path([[cx - 48, cy - 34], [cx + 48, cy - 34], [cx + 48, cy + 34], [cx - 48, cy + 34]], w, closed=True))
            paths.append(make_line_path([[cx - 48, cy - 34], [cx, cy + 6], [cx + 48, cy - 34]], w))
        elif idx == 7:  # Bell
            paths.append(make_line_path([[cx - 40, cy + 32], [cx - 32, cy + 32], [cx - 32, cy - 8], [cx, cy - 44], [cx + 32, cy - 8], [cx + 32, cy + 32], [cx + 40, cy + 32]], w))
            paths.append(make_circle_path(cx, cy + 42, 6, w))
        elif idx == 8:  # Lock
            paths.append(make_line_path([[cx - 42, cy - 4], [cx + 42, cy - 4], [cx + 42, cy + 46], [cx - 42, cy + 46]], w, closed=True))
            paths.append(make_line_path([[cx - 24, cy - 4], [cx - 24, cy - 36], [cx + 24, cy - 36], [cx + 24, cy - 4]], w))
            paths.append(make_circle_path(cx, cy + 18, 6, w))
        elif idx == 9:  # Cloud
            paths.append(make_line_path([[cx - 48, cy + 28], [cx + 48, cy + 28]], w))
            paths.append(make_line_path([[cx - 48, cy + 28], [cx - 48, cy + 6], [cx - 28, cy - 20], [cx, cy - 36], [cx + 32, cy - 20], [cx + 48, cy + 6], [cx + 48, cy + 28]], w))
        elif idx == 10:  # Camera
            paths.append(make_line_path([[cx - 46, cy - 24], [cx + 46, cy - 24], [cx + 46, cy + 40], [cx - 46, cy + 40]], w, closed=True))
            paths.append(make_line_path([[cx - 22, cy - 24], [cx - 14, cy - 38], [cx + 14, cy - 38], [cx + 22, cy - 24]], w))
            paths.append(make_circle_path(cx, cy + 8, 20, w))
        elif idx == 11:  # Shopping cart
            paths.append(make_line_path([[cx - 50, cy - 36], [cx - 34, cy - 36], [cx - 20, cy + 16], [cx + 42, cy + 16], [cx + 48, cy - 20], [cx - 28, cy - 20]], w))
            paths.append(make_circle_path(cx - 14, cy + 34, 8, w))
            paths.append(make_circle_path(cx + 32, cy + 34, 8, w))
        elif idx == 12:  # Calendar
            paths.append(make_line_path([[cx - 44, cy - 32], [cx + 44, cy - 32], [cx + 44, cy + 42], [cx - 44, cy + 42]], w, closed=True))
            paths.append(make_line_path([[cx - 44, cy - 10], [cx + 44, cy - 10]], w))
            paths.append(make_line_path([[cx - 24, cy - 42], [cx - 24, cy - 24]], w * 1.2))
            paths.append(make_line_path([[cx + 24, cy - 42], [cx + 24, cy - 24]], w * 1.2))
        elif idx == 13:  # Chat bubble
            paths.append(make_line_path([[cx - 44, cy - 34], [cx + 44, cy - 34], [cx + 44, cy + 20], [cx - 10, cy + 20], [cx - 32, cy + 42], [cx - 28, cy + 20], [cx - 44, cy + 20]], w, closed=True))
        elif idx == 14:  # Folder
            paths.append(make_line_path([[cx - 46, cy - 30], [cx - 14, cy - 30], [cx - 4, cy - 18], [cx + 46, cy - 18], [cx + 46, cy + 34], [cx - 46, cy + 34]], w, closed=True))
        elif idx == 15:  # Document
            paths.append(make_line_path([[cx - 36, cy - 44], [cx + 14, cy - 44], [cx + 36, cy - 22], [cx + 36, cy + 44], [cx - 36, cy + 44]], w, closed=True))
            paths.append(make_line_path([[cx + 14, cy - 44], [cx + 14, cy - 22], [cx + 36, cy - 22]], w))
            paths.append(make_line_path([[cx - 22, cy + 8], [cx + 22, cy + 8]], w))
            paths.append(make_line_path([[cx - 22, cy + 24], [cx + 12, cy + 24]], w))
        elif idx == 16:  # Clock
            paths.append(make_circle_path(cx, cy, 44, w))
            paths.append(make_line_path([[cx, cy], [cx, cy - 26]], w * 1.2))
            paths.append(make_line_path([[cx, cy], [cx + 20, cy]], w * 1.2))
        elif idx == 17:  # Bookmark
            paths.append(make_line_path([[cx - 32, cy - 44], [cx + 32, cy - 44], [cx + 32, cy + 44], [cx, cy + 20], [cx - 32, cy + 44]], w, closed=True))
        elif idx == 18:  # Shield
            paths.append(make_line_path([[cx, cy - 44], [cx + 42, cy - 30], [cx + 36, cy + 14], [cx, cy + 44], [cx - 36, cy + 14], [cx - 42, cy - 30]], w, closed=True))
            paths.append(make_line_path([[cx - 18, cy + 2], [cx - 6, cy + 16], [cx + 20, cy - 14]], w * 1.2))
        elif idx == 19:  # Download
            paths.append(make_line_path([[cx, cy - 36], [cx, cy + 16]], w * 1.2))
            paths.append(make_line_path([[cx - 20, cy - 4], [cx, cy + 16], [cx + 20, cy - 4]], w * 1.2))
            paths.append(make_line_path([[cx - 42, cy + 12], [cx - 42, cy + 40], [cx + 42, cy + 40], [cx + 42, cy + 12]], w))
        elif idx == 20:  # Upload
            paths.append(make_line_path([[cx, cy + 20], [cx, cy - 32]], w * 1.2))
            paths.append(make_line_path([[cx - 20, cy - 12], [cx, cy - 32], [cx + 20, cy - 12]], w * 1.2))
            paths.append(make_line_path([[cx - 42, cy + 12], [cx - 42, cy + 40], [cx + 42, cy + 40], [cx + 42, cy + 12]], w))
        elif idx == 21:  # Compass
            paths.append(make_circle_path(cx, cy, 44, w))
            paths.append(make_line_path([[cx, cy - 32], [cx + 10, cy], [cx, cy + 32], [cx - 10, cy]], w, closed=True))
        elif idx == 22:  # Battery
            paths.append(make_line_path([[cx - 46, cy - 24], [cx + 38, cy - 24], [cx + 38, cy + 24], [cx - 46, cy + 24]], w, closed=True))
            paths.append(make_line_path([[cx + 38, cy - 12], [cx + 46, cy - 12], [cx + 46, cy + 12], [cx + 38, cy + 12]], w, closed=True))
            paths.append(make_line_path([[cx - 30, cy - 12], [cx - 30, cy + 12]], w * 1.4))
            paths.append(make_line_path([[cx - 12, cy - 12], [cx - 12, cy + 12]], w * 1.4))
        elif idx == 23:  # Globe
            paths.append(make_circle_path(cx, cy, 44, w))
            paths.append(make_line_path([[cx - 44, cy], [cx + 44, cy]], w))
            paths.append(make_line_path([[cx, cy - 44], [cx, cy + 44]], w))
            paths.append(make_line_path([[cx - 22, cy - 38], [cx - 28, cy], [cx - 22, cy + 38]], w))
            paths.append(make_line_path([[cx + 22, cy - 38], [cx + 28, cy], [cx + 22, cy + 38]], w))

    m = Model(paths, 2400, 1600)
    _CACHED_DEMO_DATA = (m, icons)
    return m.copy(), [dict(ic) for ic in icons]
