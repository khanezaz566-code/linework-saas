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
        "shape_accent": "",
        "header_y_offset": 0,
        "count_y_offset": 0,
        "showcase_y_offset": 0,
        "badge_y_offset": 0,
        "showcase_scale": 1.0,
        "element_spacing": 0,
        "show_showcase_badge": True,
        # Custom Image Template (ChatGPT / AI Mockup) Parameters
        "custom_image_url": "",
        "custom_image_b64": "",
        "custom_img_w": 1920.0,
        "custom_img_h": 1080.0,
        "custom_grid_x": 0.40,
        "custom_grid_y": 0.10,
        "custom_grid_w": 0.55,
        "custom_grid_h": 0.78,
        "custom_grid_cols": 0,
        "custom_hero_enable": True,
        "custom_hero_x": 0.18,
        "custom_hero_y": 0.68,
        "custom_hero_size": 0.20,
        "custom_text_enable": True,
        "custom_title_x": 0.18,
        "custom_title_y": 0.18,
        "custom_sub_x": 0.18,
        "custom_sub_y": 0.24,
        "custom_count_x": 0.18,
        "custom_count_y": 0.44,
        "custom_show_title": True,
        "custom_show_sub": True,
        "custom_show_count": True
    })
    if cfg:
        p_name = cfg.get("preset")
        if p_name and p_name in PRESETS:
            c.update(PRESETS[p_name])
        for k, v in cfg.items():
            if v is not None and v != "":
                c[k] = v

    # Automatic high-contrast fallback for banner_sub if not explicitly specified
    if not (cfg and "banner_sub" in cfg and cfg["banner_sub"]):
        bt = str(c.get("banner_text", "")).lower()
        if bt in ("#ffffff", "#f4f4f5", "#fff", "white") or bt.startswith("#f") or bt.startswith("#e"):
            c["banner_sub"] = "#E2E8F0"
        elif bt in ("#18181b", "#1e1e1e", "#0f172a", "#000000", "#000", "black"):
            c["banner_sub"] = "#475569"

    # Synchronize accent and shape_accent so both work interchangeably
    if cfg and cfg.get("shape_accent"):
        c["accent"] = cfg["shape_accent"]
        c["shape_accent"] = cfg["shape_accent"]
    elif cfg and cfg.get("accent"):
        c["shape_accent"] = cfg["accent"]
        c["accent"] = cfg["accent"]
    elif not c.get("shape_accent") and c.get("accent"):
        c["shape_accent"] = c["accent"]

    return c

def sanitize_text(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _clean_template_title(raw_title: str) -> str:
    """Clean raw filename/hash artifacts from template titles so covers always look agency-grade."""
    if not raw_title:
        return "VECTOR ICONS"
    s = str(raw_title).strip()
    # Replace separators with spaces
    s = re.sub(r'[_\-\./\\]+', ' ', s)
    tokens = s.split()
    cleaned = []
    filler = {
        "CREATE", "MAKE", "GENERATE", "ICON", "ICONS", "SET", "PACK", "SHEET",
        "COLLECTION", "CO", "LINE", "OUTLINE", "VECTOR", "STOCK", "IMAGE",
        "FILE", "RAW", "SCREENSHOT", "SAMPLE", "DEMO", "PNG", "JPG", "JPEG", "SVG"
    }
    for tok in tokens:
        up = tok.upper()
        # Strip hex hashes (e.g. D2A691F6, CF35B945) or resolution/version tags (2X, 2K, 4K, 1024, V1)
        if re.fullmatch(r'[0-9A-F]{6,}', up):
            continue
        if re.fullmatch(r'\d+[A-Z]*|[A-Z]*\d+[A-Z]*', up):
            continue
        if len(up) <= 1:
            continue
        cleaned.append(up)
    # Remove generic filler words if we have meaningful subject words
    subject = [w for w in cleaned if w not in filler]
    final_words = subject if subject else [w for w in cleaned if w not in ("CREATE", "MAKE", "CO", "PNG", "JPG")]
    if not final_words:
        return "VECTOR ICONS"
    # Keep at most 3 punchy words so the cover headline is always bold and legible
    if len(final_words) > 3 and final_words[0] == "MINIMAL":
        final_words = final_words[1:4]
    else:
        final_words = final_words[:3]
    res = " ".join(final_words)
    return res if res else "VECTOR ICONS"


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

def _render_paths_svg(
    paths: list[Path], stroke: str, stroke_scale: float,
    scale: float, ox: float, oy: float,
    target_screen_sw: float | None = None
) -> str:
    elems = []
    safe_scale = max(scale, 1e-4)
    for p in paths:
        if target_screen_sw is not None and target_screen_sw > 0:
            # 100% uniform screen-space stroke thickness across all icons regardless of per-icon scale
            sw = max(0.3, target_screen_sw / safe_scale)
        else:
            sw = max(0.5, p.w * stroke_scale)
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
        W, H, banner_w = 2400, 2400, 680
    elif layout == "landscape_4_3":
        W, H, banner_w = 2400, 1800, 660
    elif layout == "landscape_16_10":
        W, H, banner_w = 1920, 1200, 520
    else:  # landscape_16_9 (Default 4K Ultra-HD presentation: 3840 x 2160)
        W, H, banner_w = 3840, 2160, 1020
    return W, H, banner_w

def _get_checkered_defs(W: int) -> tuple[str, str]:
    chk_size = max(18, int(round(W / 110)))
    chk_half = chk_size / 2
    defs = f"""
    <pattern id="stockCheckeredPattern" width="{chk_size}" height="{chk_size}" patternUnits="userSpaceOnUse">
      <rect width="{chk_size}" height="{chk_size}" fill="#ffffff"/>
      <rect x="0" y="0" width="{chk_half}" height="{chk_half}" fill="#f3f5f8"/>
      <rect x="{chk_half}" y="{chk_half}" width="{chk_half}" height="{chk_half}" fill="#f3f5f8"/>
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
    clean_t = sanitize_text(_clean_template_title(title))
    meta_fs = max(12, int(round(sheet_h * 0.0082)))

    sr, sg, sb = hex_to_rgb(stroke_color)
    stk_txt = "#09090B" if (0.299 * sr + 0.587 * sg + 0.114 * sb) > 0.55 else "#FFFFFF"
    fr, fg, fb = hex_to_rgb(frame_col)
    frm_txt = "#09090B" if (0.299 * fr + 0.587 * fg + 0.114 * fb) > 0.55 else "#FFFFFF"

    # Common top & bottom microstock editorial metadata strip inside the artboard frame
    header_strip = f"""
        <g opacity="0.72">
          <rect x="{bx+24:.1f}" y="{by-meta_fs-6:.1f}" width="{len(clean_t)*meta_fs*0.72 + 160:.1f}" height="{meta_fs*2.0:.1f}" rx="6" fill="{stroke_color}"/>
          <text x="{bx+42:.1f}" y="{by+meta_fs*0.38:.1f}" font-size="{meta_fs}" font-weight="800" letter-spacing="2.5" fill="{stk_txt}" class="mono">{clean_t} // {sanitize_text(count_val)} SET</text>
          <rect x="{bx+bw-290:.1f}" y="{by-meta_fs-6:.1f}" width="266" height="{meta_fs*2.0:.1f}" rx="6" fill="{frame_col}"/>
          <text x="{bx+bw-157:.1f}" y="{by+meta_fs*0.38:.1f}" font-size="{meta_fs}" font-weight="800" letter-spacing="2" fill="{frm_txt}" text-anchor="middle" class="mono">100% UNIFORM VECTOR</text>
        </g>"""

    if decor == "artboard_double_frame":
        return f"""
      <g id="artboardDoubleFrame" opacity="0.92">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="14" fill="none" stroke="{frame_col}" stroke-width="4.5"/>
        <rect x="{bx+14:.1f}" y="{by+14:.1f}" width="{bw-28:.1f}" height="{bh-28:.1f}" rx="8" fill="none" stroke="{stroke_color}" stroke-opacity="0.24" stroke-width="1.8" stroke-dasharray="12,6"/>
        {header_strip}
      </g>"""
    elif decor == "artboard_corner_ticks":
        t = 36
        return f"""
      <g id="artboardCornerTicks" fill="none">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" stroke="{stroke_color}" stroke-opacity="0.18" stroke-width="2"/>
        <g stroke="{stroke_color}" stroke-width="3.5" opacity="0.65">
          <path d="M{bx-14:.1f},{by:.1f} h{t} M{bx:.1f},{by-14:.1f} v{t}"/>
          <path d="M{bx+bw-t+14:.1f},{by:.1f} h{t} M{bx+bw:.1f},{by-14:.1f} v{t}"/>
          <path d="M{bx-14:.1f},{by+bh:.1f} h{t} M{bx:.1f},{by+bh-t+14:.1f} v{t}"/>
          <path d="M{bx+bw-t+14:.1f},{by+bh:.1f} h{t} M{bx+bw:.1f},{by+bh-t+14:.1f} v{t}"/>
        </g>
        {header_strip}
      </g>"""
    elif decor == "artboard_hud_corners":
        L = 56
        return f"""
      <g id="artboardHudCorners" fill="none">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" stroke="{stroke_color}" stroke-opacity="0.16" stroke-width="2"/>
        <path d="M{bx:.1f},{by+L:.1f} V{by:.1f} H{bx+L:.1f}" stroke="{frame_col}" stroke-width="7"/>
        <path d="M{bx+bw-L:.1f},{by:.1f} H{bx+bw:.1f} V{by+L:.1f}" stroke="{frame_col}" stroke-width="7"/>
        <path d="M{bx:.1f},{by+bh-L:.1f} V{by+bh:.1f} H{bx+L:.1f}" stroke="{frame_col}" stroke-width="7"/>
        <path d="M{bx+bw-L:.1f},{by+bh:.1f} H{bx+bw:.1f} V{by+bh-L:.1f}" stroke="{frame_col}" stroke-width="7"/>
        {header_strip}
      </g>"""
    elif decor == "artboard_dashed_frame":
        return f"""
      <g id="artboardDashedFrame">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="16" fill="none" stroke="{stroke_color}" stroke-opacity="0.32" stroke-width="3.5" stroke-dasharray="16,10"/>
        {header_strip}
      </g>"""
    elif decor == "artboard_header_footer":
        return f"""
      <g id="artboardHeaderFooter">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="12" fill="none" stroke="{stroke_color}" stroke-opacity="0.22" stroke-width="2.5"/>
        <line x1="{bx+24:.1f}" y1="{by+48:.1f}" x2="{bx+bw-24:.1f}" y2="{by+48:.1f}" stroke="{stroke_color}" stroke-opacity="0.16" stroke-width="1.8"/>
        <text x="{bx+32:.1f}" y="{by+32:.1f}" font-size="{meta_fs}" font-weight="800" letter-spacing="2.5" fill="{stroke_color}" opacity="0.65" class="mono">{clean_t} // {sanitize_text(count_val)} VECTOR ICONS</text>
        <text x="{bx+bw-32:.1f}" y="{by+32:.1f}" font-size="{meta_fs}" font-weight="800" letter-spacing="2.5" fill="{stroke_color}" opacity="0.65" text-anchor="end" class="mono">100% PRECISION GRID</text>
        <line x1="{bx+24:.1f}" y1="{by+bh-44:.1f}" x2="{bx+bw-24:.1f}" y2="{by+bh-44:.1f}" stroke="{stroke_color}" stroke-opacity="0.16" stroke-width="1.8"/>
        <text x="{bx+bw/2:.1f}" y="{by+bh-16:.1f}" font-size="{max(11, meta_fs-1)}" font-weight="700" letter-spacing="3.5" fill="{stroke_color}" opacity="0.55" text-anchor="middle" class="mono">PIXEL PERFECT &#8226; UNIFORM STROKE &#8226; INFINITE SCALE</text>
      </g>"""
    else:
        # Default Pro Studio Artboard Frame with corner nodes + spec badges
        return f"""
      <g id="artboardSquareBox">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="12" fill="none" stroke="{stroke_color}" stroke-opacity="0.20" stroke-width="2.5"/>
        <rect x="{bx+10:.1f}" y="{by+10:.1f}" width="{bw-20:.1f}" height="{bh-20:.1f}" rx="8" fill="none" stroke="{stroke_color}" stroke-opacity="0.08" stroke-width="1.5"/>
        <rect x="{bx-5:.1f}" y="{by-5:.1f}" width="12" height="12" rx="2" fill="{frame_col}" stroke="{stroke_color}" stroke-width="2"/>
        <rect x="{bx+bw-7:.1f}" y="{by-5:.1f}" width="12" height="12" rx="2" fill="{frame_col}" stroke="{stroke_color}" stroke-width="2"/>
        <rect x="{bx-5:.1f}" y="{by+bh-7:.1f}" width="12" height="12" rx="2" fill="{frame_col}" stroke="{stroke_color}" stroke-width="2"/>
        <rect x="{bx+bw-7:.1f}" y="{by+bh-7:.1f}" width="12" height="12" rx="2" fill="{frame_col}" stroke="{stroke_color}" stroke-width="2"/>
        {header_strip}
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
        return (
            f'<rect x="{x+4:.1f}" y="{y+6:.1f}" width="{s:.1f}" height="{s:.1f}" rx="8" fill="#000000" fill-opacity="0.05"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="8" fill="#ffffff" fill-opacity="0.88" stroke="{stroke_color}" stroke-opacity="0.20" stroke-width="2"/>'
        )
    elif decor == "cell_rounded_cards":
        rx = min(28, int(s * 0.16))
        return (
            f'<rect x="{x+4:.1f}" y="{y+8:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{rx}" fill="#000000" fill-opacity="0.07"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{rx}" fill="#ffffff" fill-opacity="0.92" stroke="{stroke_color}" stroke-opacity="0.14" stroke-width="2"/>'
            f'<circle cx="{x+s-18:.1f}" cy="{y+18:.1f}" r="3.5" fill="{col}" fill-opacity="0.55"/>'
        )
    elif decor == "cell_dashed_boxes":
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="10" fill="#ffffff" fill-opacity="0.55" stroke="{stroke_color}" stroke-opacity="0.30" stroke-width="2.2" stroke-dasharray="10,7"/>'
    elif decor == "cell_full_table_grid":
        gx = cx - cell_w / 2
        gy = cy - cell_h / 2
        return f'<rect x="{gx:.1f}" y="{gy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="none" stroke="{stroke_color}" stroke-opacity="0.16" stroke-width="1.6"/>'
    elif decor == "cell_corner_brackets":
        L = max(12, int(s * 0.17))
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{col}" fill-opacity="0.04"/>'
            f'<path d="M{x:.1f},{y+L:.1f} V{y:.1f} H{x+L:.1f} M{x+s-L:.1f},{y:.1f} H{x+s:.1f} V{y+L:.1f} '
            f'M{x:.1f},{y+s-L:.1f} V{y+s:.1f} H{x+L:.1f} M{x+s-L:.1f},{y+s:.1f} H{x+s:.1f} V{y+s-L:.1f}" '
            f'fill="none" stroke="{stroke_color}" stroke-opacity="0.42" stroke-width="2.5"/>'
        )
    elif decor == "cell_soft_tint_squares":
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="18" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-opacity="0.35" stroke-width="2"/>'
    elif decor == "cell_circle_badges":
        r = s * 0.48
        return (
            f'<circle cx="{cx+3:.1f}" cy="{cy+6:.1f}" r="{r:.1f}" fill="#000000" fill-opacity="0.06"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#ffffff" fill-opacity="0.88" stroke="{stroke_color}" stroke-opacity="0.20" stroke-width="2"/>'
        )
    elif decor == "cell_hex_frames":
        r = s * 0.50
        pts = " ".join(f"{cx + r * math.cos(math.radians(60 * k - 30)):.1f},{cy + r * math.sin(math.radians(60 * k - 30)):.1f}" for k in range(6))
        return f'<polygon points="{pts}" fill="#ffffff" fill-opacity="0.82" stroke="{stroke_color}" stroke-opacity="0.24" stroke-width="2.2"/>'
    elif decor == "cell_brutal_squares":
        return (
            f'<rect x="{x+8:.1f}" y="{y+8:.1f}" width="{s:.1f}" height="{s:.1f}" rx="6" fill="{stroke_color}" fill-opacity="0.88"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="6" fill="#ffffff" stroke="{stroke_color}" stroke-width="3"/>'
        )
    else:
        # Subtle Studio Swiss-Grid Cell Pedestal even when an artboard_* frame is active
        rx = min(20, int(s * 0.12))
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{rx}" '
            f'fill="{stroke_color}" fill-opacity="0.025" stroke="{stroke_color}" stroke-opacity="0.10" stroke-width="1.4"/>'
        )


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
    inner_pad_x = pad_x * 1.18
    inner_pad_y = pad_y * 1.18

    # Mode 1: Auto-Grid by Icon Count (Adobe Stock standard)
    if layout_mode == "auto_grid" and N >= 1:
        target_aspect = sheet_w / max(1.0, sheet_h)
        cols, rows = _compute_optimal_grid(N, target_aspect)

        grid_w = sheet_w - 2 * inner_pad_x
        grid_h = sheet_h - 2 * inner_pad_y

        cell_w = grid_w / cols
        cell_h = grid_h / rows
        fill_ratio = 0.50 if has_cell_box else 0.56
        target_size = min(cell_w * fill_ratio, cell_h * fill_ratio)
        # 100% uniform screen-space stroke width across every single icon in the grid!
        uniform_grid_sw = max(3.5, target_size * 0.044 * stroke_scale)

        rendered = [outer_frame_svg] if outer_frame_svg else []
        for i, ic in enumerate(avail_icons):
            col_i = i % cols
            row_i = i // cols
            cell_cx = sheet_x + inner_pad_x + col_i * cell_w + cell_w / 2
            cell_cy = sheet_y + inner_pad_y + row_i * cell_h + cell_h / 2

            if decor != "none":
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
            # Optical balance so wide/flat and tall/narrow icons look visually harmonious
            optical_span = 0.78 * max(bw, bh) + 0.22 * math.sqrt(bw * bh)
            s = min(target_size / max(bw, bh), (target_size * 0.94) / max(1.0, optical_span))
            ox = cell_cx - (bw * s) / 2 - bx1 * s
            oy = cell_cy - (bh * s) / 2 - by1 * s
            rendered.append(_render_paths_svg(paths, stroke_color, stroke_scale, s, ox, oy, target_screen_sw=uniform_grid_sw))
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
        med_w = float(np.median([p.w for p in valid_paths if p.w > 0] or [4.0]))
    else:
        min_x, min_y = 0.0, 0.0
        t_w, t_h = max(10.0, model.width), max(10.0, model.height)
        med_w = 4.0

    avail_w = sheet_w - 2 * inner_pad_x
    avail_h = sheet_h - 2 * inner_pad_y
    scale = min(avail_w / t_w, avail_h / t_h)
    target_w = t_w * scale
    target_h = t_h * scale
    off_x = sheet_x + inner_pad_x + (avail_w - target_w) / 2 - min_x * scale
    off_y = sheet_y + inner_pad_y + (avail_h - target_h) / 2 - min_y * scale
    uniform_sheet_sw = max(3.2, med_w * scale * stroke_scale)

    rendered_cells = []
    if decor != "none" and avail_icons:
        boxes = [ic["box"] for ic in avail_icons if "box" in ic and len(ic["box"]) == 4]
        if boxes:
            box_ws = [max(10.0, (b[2] - b[0]) * scale) for b in boxes]
            box_hs = [max(10.0, (b[3] - b[1]) * scale) for b in boxes]
            med_bw = float(np.median(box_ws))
            med_bh = float(np.median(box_hs))

            cxs = [((b[0] + b[2]) / 2.0) * scale + off_x for b in boxes]
            cys = [((b[1] + b[3]) / 2.0) * scale + off_y for b in boxes]
            dxs = [abs(cxs[a] - cxs[b]) for a in range(len(cxs)) for b in range(a + 1, len(cxs)) if abs(cxs[a] - cxs[b]) > 25]
            dys = [abs(cys[a] - cys[b]) for a in range(len(cys)) for b in range(a + 1, len(cys)) if abs(cys[a] - cys[b]) > 25]
            min_gap_x = min(dxs) if dxs else 999.0
            min_gap_y = min(dys) if dys else 999.0
            max_allowed = min(min_gap_x, min_gap_y) * 0.92 if min(min_gap_x, min_gap_y) < 900.0 else max(med_bw, med_bh) * 1.5
            ideal_dim = min(max_allowed, max(med_bw, med_bh) * 1.45)

            for i, ic in enumerate(avail_icons):
                bx1, by1, bx2, by2 = ic.get("box", [0, 0, 100, 100])
                ic_cx = ((bx1 + bx2) / 2.0) * scale + off_x
                ic_cy = ((by1 + by2) / 2.0) * scale + off_y
                ic_w = max(10.0, (bx2 - bx1) * scale)
                ic_h = max(10.0, (by2 - by1) * scale)
                c_dim = min(max_allowed, max(ideal_dim, max(ic_w, ic_h) * 1.25))
                rendered_cells.append(
                    _render_cell_box_svg(decor, ic_cx, ic_cy, c_dim, c_dim, banner_bg, stroke_color, accent, i)
                )

    res_parts = []
    if outer_frame_svg:
        res_parts.append(outer_frame_svg)
    if rendered_cells:
        res_parts.extend(rendered_cells)
    res_parts.append(
        _render_paths_svg(
            model.paths, stroke_color, stroke_scale, scale, off_x, off_y, target_screen_sw=uniform_sheet_sw
        )
    )
    return "\n    ".join(res_parts)


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
    accent: str = "",
    hl_bg: str = "#181B24"
) -> str:
    cleaned_raw = _clean_template_title(title)
    title_clean = sanitize_text(cleaned_raw)
    sub_clean = sanitize_text(subtitle.upper() if subtitle else "EDITABLE LINE ICONS")
    anchor = "middle" if is_centered else "start"
    style = str(style or "solid_square").lower()

    # Auto-fit title font size so headline is always large & bold without overflowing box
    is_condensed = ("Bebas" in title_font) or ("Oswald" in title_font)
    char_ratio = 0.56 if is_condensed else 0.78
    est_w = min(max_w, max(max_w * 0.84, int(len(cleaned_raw) * title_fs * char_ratio) + 84))
    max_fit_fs = int((est_w - 64) / max(1.0, len(cleaned_raw) * char_ratio))
    eff_title_fs = max(34, min(title_fs, max_fit_fs))

    rect_x = cx - est_w / 2 if is_centered else cx
    box_h = max(72, int(eff_title_fs * (1.46 if is_condensed else 1.62)))
    box_y = cy - int(eff_title_fs * 0.88)
    text_y = box_y + int(box_h * (0.72 if is_condensed else 0.68))

    hl_fill = hl_bg
    if accent and accent.upper() not in ("#F5B800", "#00D2A0", "#FF4757", "#8B5CF6", "#10B981", "#F97316", "#2563EB", "#F4F4F5"):
        hl_fill = accent
    hr, hg, hb = hex_to_rgb(hl_fill)
    hl_text = "#09090B" if (0.299 * hr + 0.587 * hg + 0.114 * hb) > 0.55 else "#FFFFFF"

    # Top micro-pill tag above main headline
    tag_fs = max(13, int(sub_fs * 0.56))
    tag_w = min(est_w * 0.78, max(220, tag_fs * 18))
    tag_h = int(tag_fs * 2.1)
    tag_y = box_y - tag_h - 14
    top_tag_svg = f"""
      <rect x="{cx - tag_w/2:.1f}" y="{tag_y:.1f}" width="{tag_w:.1f}" height="{tag_h:.1f}" rx="{tag_h//2}"
            fill="{banner_text}" fill-opacity="0.12" stroke="{banner_text}" stroke-opacity="0.22" stroke-width="1.5"/>
      <text x="{cx:.1f}" y="{tag_y + tag_h*0.68:.1f}" font-size="{tag_fs}" font-weight="800" letter-spacing="3"
            fill="{banner_text}" text-anchor="middle" class="mono">&#9733; PREMIUM VECTOR PACK &#9733;</text>"""

    # 25 Distinct Highlighter Geometries
    bg_shape = ""
    if style in ("solid_square", "square"):
        bg_shape = (
            f'<rect x="{rect_x+8:.1f}" y="{box_y+8:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="8" fill="#000000" fill-opacity="0.20"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="8" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.28" stroke-width="2.5"/>'
        )
    elif style in ("frosted_pill", "pill"):
        rx = box_h // 2
        bg_shape = (
            f'<rect x="{rect_x+6:.1f}" y="{box_y+8:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="#000000" fill-opacity="0.18"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="{hl_fill}" stroke="rgba(255,255,255,0.4)" stroke-width="2.5"/>'
        )
    elif style == "rounded_badge":
        bg_shape = (
            f'<rect x="{rect_x+6:.1f}" y="{box_y+8:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="16" fill="#000000" fill-opacity="0.18"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="16" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.3" stroke-width="2.5"/>'
        )
    elif style in ("ribbon_tails", "ribbon"):
        notch = 20
        pts = f"{rect_x-12:.1f},{box_y:.1f} {rect_x+est_w+12:.1f},{box_y:.1f} {rect_x+est_w-notch+12:.1f},{box_y+box_h/2:.1f} {rect_x+est_w+12:.1f},{box_y+box_h:.1f} {rect_x-12:.1f},{box_y+box_h:.1f} {rect_x+notch-12:.1f},{box_y+box_h/2:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.3" stroke-width="2.5"/>'
    elif style == "skew_parallelogram":
        sk = 18
        pts = f"{rect_x+sk:.1f},{box_y:.1f} {rect_x+est_w+sk:.1f},{box_y:.1f} {rect_x+est_w-sk:.1f},{box_y+box_h:.1f} {rect_x-sk:.1f},{box_y+box_h:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="2.5"/>'
    elif style == "hex_tag":
        p = 24
        pts = f"{rect_x+p:.1f},{box_y:.1f} {rect_x+est_w-p:.1f},{box_y:.1f} {rect_x+est_w:.1f},{box_y+box_h/2:.1f} {rect_x+est_w-p:.1f},{box_y+box_h:.1f} {rect_x+p:.1f},{box_y+box_h:.1f} {rect_x:.1f},{box_y+box_h/2:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.4" stroke-width="2.5"/>'
    elif style == "chamfer_plate":
        c_cut = 16
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        pts = f"{x1+c_cut:.1f},{y1:.1f} {x2-c_cut:.1f},{y1:.1f} {x2:.1f},{y1+c_cut:.1f} {x2:.1f},{y2-c_cut:.1f} {x2-c_cut:.1f},{y2:.1f} {x1+c_cut:.1f},{y2:.1f} {x1:.1f},{y2-c_cut:.1f} {x1:.1f},{y1+c_cut:.1f}"
        bg_shape = f'<polygon points="{pts}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.45" stroke-width="2.5"/>'
    elif style in ("neon_underline", "glow_bar"):
        hl_text = banner_text
        bar_h = 10
        bg_shape = (
            f'<rect x="{rect_x:.1f}" y="{box_y+box_h-6:.1f}" width="{est_w:.1f}" height="{bar_h}" rx="5" fill="{accent or banner_text}"/>'
            f'<circle cx="{cx:.1f}" cy="{box_y+box_h-1:.1f}" r="7" fill="#ffffff"/>'
        )
    elif style == "double_rule":
        hl_text = banner_text
        bg_shape = (
            f'<line x1="{rect_x:.1f}" y1="{box_y:.1f}" x2="{rect_x+est_w:.1f}" y2="{box_y:.1f}" stroke="{banner_text}" stroke-width="4"/>'
            f'<line x1="{rect_x+24:.1f}" y1="{box_y+8:.1f}" x2="{rect_x+est_w-24:.1f}" y2="{box_y+8:.1f}" stroke="{banner_text}" stroke-width="1.8" opacity="0.6"/>'
            f'<line x1="{rect_x:.1f}" y1="{box_y+box_h:.1f}" x2="{rect_x+est_w:.1f}" y2="{box_y+box_h:.1f}" stroke="{banner_text}" stroke-width="4"/>'
        )
    elif style in ("corner_brackets", "brackets"):
        hl_text = banner_text
        t = 24
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{banner_text}" fill-opacity="0.08"/>'
            f'<path d="M{x1+t:.1f},{y1:.1f} H{x1:.1f} V{y1+t:.1f} M{x2-t:.1f},{y1:.1f} H{x2:.1f} V{y1+t:.1f} '
            f'M{x1+t:.1f},{y2:.1f} H{x1:.1f} V{y2-t:.1f} M{x2-t:.1f},{y2:.1f} H{x2:.1f} V{y2-t:.1f}" '
            f'fill="none" stroke="{accent or banner_text}" stroke-width="5"/>'
        )
    elif style == "left_accent_bar":
        bg_shape = (
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="8" fill="{hl_fill}"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="16" height="{box_h:.1f}" rx="4" fill="{accent or banner_text}"/>'
        )
    elif style == "brush_stroke":
        d = f"M{rect_x-8:.1f},{box_y+8:.1f} Q{cx:.1f},{box_y-6:.1f} {rect_x+est_w+10:.1f},{box_y+4:.1f} L{rect_x+est_w-4:.1f},{box_y+box_h-4:.1f} Q{cx:.1f},{box_y+box_h+8:.1f} {rect_x+4:.1f},{box_y+box_h-2:.1f} Z"
        bg_shape = f'<path d="{d}" fill="{hl_fill}"/>'
    elif style == "offset_shadow_box":
        bg_shape = (
            f'<rect x="{rect_x+10:.1f}" y="{box_y+10:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="6" fill="#09090B" fill-opacity="0.85"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="6" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.4" stroke-width="3"/>'
        )
    elif style == "dotted_coupon":
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="10" fill="{hl_fill}" stroke="#ffffff" stroke-width="2.5" stroke-dasharray="10,7"/>'
    elif style == "gradient_glow_pill":
        rx = box_h // 2
        bg_shape = (
            f'<rect x="{rect_x-6:.1f}" y="{box_y-6:.1f}" width="{est_w+12:.1f}" height="{box_h+12:.1f}" rx="{rx+6}" fill="none" stroke="{accent or banner_text}" stroke-opacity="0.45" stroke-width="2.5"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.5" stroke-width="2"/>'
        )
    elif style == "ticket_stub":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        my = (y1 + y2) / 2
        d = f"M{x1:.1f},{y1:.1f} H{x2:.1f} V{my-12:.1f} A12,12 0 0,0 {x2:.1f},{my+12:.1f} V{y2:.1f} H{x1:.1f} V{my+12:.1f} A12,12 0 0,0 {x1:.1f},{my-12:.1f} Z"
        bg_shape = f'<path d="{d}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="2.5"/>'
    elif style == "arrow_pointer":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        my = (y1 + y2) / 2
        pts = f"{x1:.1f},{y1:.1f} {x2-18:.1f},{y1:.1f} {x2+10:.1f},{my:.1f} {x2-18:.1f},{y2:.1f} {x1:.1f},{y2:.1f}"
        bg_shape = (
            f'<polygon points="{pts}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.3" stroke-width="2.5"/>'
            f'<circle cx="{x2-10:.1f}" cy="{my:.1f}" r="5" fill="#ffffff"/>'
        )
    elif style == "speech_callout":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="14" fill="{hl_fill}"/>'
            f'<polygon points="{cx-14:.1f},{y2:.1f} {cx+14:.1f},{y2:.1f} {cx:.1f},{y2+16:.1f}" fill="{hl_fill}"/>'
        )
    elif style == "circle_seal_bg":
        r = int(box_h * 0.72)
        bg_shape = (
            f'<circle cx="{cx:.1f}" cy="{box_y+box_h/2:.1f}" r="{r}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.3" stroke-width="2" stroke-dasharray="6,4"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="10" fill="{hl_fill}"/>'
        )
    elif style == "diamond_crest":
        my = box_y + box_h / 2
        bg_shape = (
            f'<polygon points="{cx:.1f},{box_y-18:.1f} {cx+46:.1f},{my:.1f} {cx:.1f},{box_y+box_h+18:.1f} {cx-46:.1f},{my:.1f}" fill="{accent or banner_text}" opacity="0.35"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="6" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="2.5"/>'
        )
    elif style == "crown_header":
        hl_text = banner_text
        bg_shape = (
            f'<polygon points="{cx-36:.1f},{box_y-6:.1f} {cx-24:.1f},{box_y-22:.1f} {cx-8:.1f},{box_y-10:.1f} {cx:.1f},{box_y-28:.1f} {cx+8:.1f},{box_y-10:.1f} {cx+24:.1f},{box_y-22:.1f} {cx+36:.1f},{box_y-6:.1f}" fill="{accent or banner_text}"/>'
            f'<rect x="{rect_x:.1f}" y="{box_y+box_h-4:.1f}" width="{est_w:.1f}" height="5" fill="{banner_text}"/>'
        )
    elif style == "crosshair_target":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        bg_shape = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.4" stroke-width="2"/>'
            f'<path d="M{x1-8:.1f},{y1:.1f} h16 M{x1:.1f},{y1-8:.1f} v16 M{x2-8:.1f},{y1:.1f} h16 M{x2:.1f},{y1-8:.1f} v16 '
            f'M{x1-8:.1f},{y2:.1f} h16 M{x1:.1f},{y2-8:.1f} v16 M{x2-8:.1f},{y2:.1f} h16 M{x2:.1f},{y2-8:.1f} v16" stroke="{banner_text}" stroke-width="2.5"/>'
        )
    elif style == "extrude_3d_box":
        x1, y1, x2, y2 = rect_x, box_y, rect_x + est_w, box_y + box_h
        d = 12
        bg_shape = (
            f'<polygon points="{x1+d:.1f},{y2+d:.1f} {x2+d:.1f},{y2+d:.1f} {x2+d:.1f},{y1+d:.1f} {x2:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x1:.1f},{y2:.1f}" fill="#09090B" opacity="0.75"/>'
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" fill="{hl_fill}" stroke="#ffffff" stroke-opacity="0.45" stroke-width="2.5"/>'
        )
    elif style == "minimal_pill_outline":
        hl_text = banner_text
        rx = box_h // 2
        bg_shape = f'<rect x="{rect_x:.1f}" y="{box_y:.1f}" width="{est_w:.1f}" height="{box_h:.1f}" rx="{rx}" fill="{banner_text}" fill-opacity="0.08" stroke="{accent or banner_text}" stroke-width="3.5"/>'
    else:
        hl_text = banner_text

    sub_y = box_y + box_h + int(sub_fs * 1.45) + 14
    rule_w = max(28, int(est_w * 0.10))
    sub_text_w = min(est_w * 0.72, len(sub_clean) * sub_fs * 0.62 + 24)
    return f"""
    <g id="titleHighlighterGroup">
      {top_tag_svg}
      {bg_shape}
      <text x="{cx:.1f}" y="{text_y:.1f}" font-size="{eff_title_fs}" font-weight="900" letter-spacing="3.5"
            fill="{hl_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <line x1="{cx - sub_text_w/2 - rule_w - 10:.1f}" y1="{sub_y - sub_fs*0.34:.1f}" x2="{cx - sub_text_w/2 - 10:.1f}" y2="{sub_y - sub_fs*0.34:.1f}" stroke="{banner_sub}" stroke-width="2.5" opacity="0.55"/>
      <text x="{cx:.1f}" y="{sub_y:.1f}" font-size="{sub_fs}" font-weight="800" letter-spacing="2.2"
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
      <line x1="{cx + sub_text_w/2 + 10:.1f}" y1="{sub_y - sub_fs*0.34:.1f}" x2="{cx + sub_text_w/2 + rule_w + 10:.1f}" y2="{sub_y - sub_fs*0.34:.1f}" stroke="{banner_sub}" stroke-width="2.5" opacity="0.55"/>
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
    pad_ratio = 0.17
    ix = bx + side * pad_ratio
    iy = by + side * pad_ratio
    iw = side * (1.0 - 2 * pad_ratio)
    ih = side * (1.0 - 2 * pad_ratio)

    hero_paths = _extract_highlight_svg(
        model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
        iw, ih, ix, iy, cols=cols, highlight_index=highlight_index
    )

    # Subtle internal studio grid & spotlight glow inside the showcase card
    inner_studio_decor = (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{side*0.34:.1f}" fill="{accent}" fill-opacity="0.10"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{side*0.38:.1f}" fill="none" stroke="#ffffff" stroke-opacity="0.08" stroke-width="1.5" stroke-dasharray="8,6"/>'
        f'<line x1="{bx+20:.1f}" y1="{cy:.1f}" x2="{bx+side-20:.1f}" y2="{cy:.1f}" stroke="#ffffff" stroke-opacity="0.05" stroke-width="1.2"/>'
        f'<line x1="{cx:.1f}" y1="{by+20:.1f}" x2="{cx:.1f}" y2="{by+side-20:.1f}" stroke="#ffffff" stroke-opacity="0.05" stroke-width="1.2"/>'
    )

    # Top micro-badge on the showcase card (hidden on clean/minimal modes or if disabled)
    showcase_badge = ""
    if c.get("show_showcase_badge", True) and shape not in ("clean_none", "pure_clean", "clean"):
        badge_w = min(side * 0.66, 230)
        badge_h = max(24, int(side * 0.072))
        badge_fs = max(11, int(badge_h * 0.50))
        showcase_badge = (
            f'<rect x="{cx - badge_w/2:.1f}" y="{by - badge_h/2:.1f}" width="{badge_w:.1f}" height="{badge_h:.1f}" rx="{badge_h//2}" '
            f'fill="{accent}" stroke="{hl_bg}" stroke-width="3"/>'
            f'<text x="{cx:.1f}" y="{by + badge_fs*0.36:.1f}" font-size="{badge_fs}" font-weight="900" letter-spacing="2" '
            f'fill="#09090B" text-anchor="middle" class="mono">FEATURED PREVIEW</text>'
        )

    frame_svg = ""
    if shape in ("square_box", "square"):
        frame_svg = (
            f'<rect x="{bx+10:.1f}" y="{by+14:.1f}" width="{side:.1f}" height="{side:.1f}" rx="12" fill="#000000" fill-opacity="0.24"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="12" fill="{hl_bg}" stroke="rgba(255,255,255,0.32)" stroke-width="2.5"/>'
            f'<rect x="{bx+10:.1f}" y="{by+10:.1f}" width="{side-20:.1f}" height="{side-20:.1f}" rx="8" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1.5"/>'
            f'<rect x="{bx-5:.1f}" y="{by-5:.1f}" width="12" height="12" rx="2" fill="{accent}"/>'
            f'<rect x="{bx+side-7:.1f}" y="{by-5:.1f}" width="12" height="12" rx="2" fill="{accent}"/>'
            f'<rect x="{bx-5:.1f}" y="{by+side-7:.1f}" width="12" height="12" rx="2" fill="{accent}"/>'
            f'<rect x="{bx+side-7:.1f}" y="{by+side-7:.1f}" width="12" height="12" rx="2" fill="{accent}"/>'
        )
    elif shape in ("rounded_square", "card"):
        frame_svg = (
            f'<rect x="{bx+10:.1f}" y="{by+14:.1f}" width="{side:.1f}" height="{side:.1f}" rx="32" fill="#000000" fill-opacity="0.24"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="32" fill="{hl_bg}" stroke="rgba(255,255,255,0.30)" stroke-width="2.5"/>'
        )
    elif shape == "double_border_square":
        frame_svg = (
            f'<rect x="{bx-8:.1f}" y="{by-8:.1f}" width="{side+16:.1f}" height="{side+16:.1f}" rx="12" fill="none" stroke="{hl_bg}" stroke-width="3.5"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="8" fill="{hl_bg}" stroke="{accent}" stroke-opacity="0.65" stroke-width="2.5"/>'
        )
    elif shape == "dashed_square":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="12" fill="{hl_bg}"/>'
            f'<rect x="{bx+12:.1f}" y="{by+12:.1f}" width="{side-24:.1f}" height="{side-24:.1f}" rx="8" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5" stroke-dasharray="12,8"/>'
        )
    elif shape == "offset_brutal_square":
        frame_svg = (
            f'<rect x="{bx+14:.1f}" y="{by+14:.1f}" width="{side:.1f}" height="{side:.1f}" rx="6" fill="{accent}"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="6" fill="{hl_bg}" stroke="#ffffff" stroke-width="3"/>'
        )
    elif shape == "chamfer_square":
        c_cut = side * 0.14
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        pts = f"{x1+c_cut:.1f},{y1:.1f} {x2-c_cut:.1f},{y1:.1f} {x2:.1f},{y1+c_cut:.1f} {x2:.1f},{y2-c_cut:.1f} {x2-c_cut:.1f},{y2:.1f} {x1+c_cut:.1f},{y2:.1f} {x1:.1f},{y2-c_cut:.1f} {x1:.1f},{y1+c_cut:.1f}"
        frame_svg = f'<polygon points="{pts}" fill="{hl_bg}" stroke="{accent}" stroke-width="3"/>'
    elif shape in ("hud_tech_box", "modern_cad_box"):
        L = side * 0.18
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="4" fill="{hl_bg}" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>'
            f'<path d="M{x1:.1f},{y1+L:.1f} V{y1:.1f} H{x1+L:.1f} M{x2-L:.1f},{y1:.1f} H{x2:.1f} V{y1+L:.1f} '
            f'M{x1:.1f},{y2-L:.1f} V{y2:.1f} H{x1+L:.1f} M{x2-L:.1f},{y2:.1f} H{x2:.1f} V{y2-L:.1f}" fill="none" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="{accent}"/>'
        )
    elif shape in ("glass_card", "frosted_glass"):
        frame_svg = (
            f'<rect x="{bx+8:.1f}" y="{by+12:.1f}" width="{side:.1f}" height="{side:.1f}" rx="28" fill="#000000" fill-opacity="0.22"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="28" fill="{hl_bg}" fill-opacity="0.92" stroke="#ffffff" stroke-opacity="0.45" stroke-width="2.5"/>'
            f'<path d="M{bx+28:.1f},{by:.1f} H{bx+side*0.55:.1f} L{bx:.1f},{by+side*0.55:.1f} V{by+28:.1f} Z" fill="#ffffff" fill-opacity="0.08"/>'
        )
    elif shape in ("floating_card", "elevated_card"):
        frame_svg = (
            f'<rect x="{bx+14:.1f}" y="{by+20:.1f}" width="{side:.1f}" height="{side:.1f}" rx="24" fill="#000000" fill-opacity="0.30"/>'
            f'<rect x="{bx+6:.1f}" y="{by+10:.1f}" width="{side:.1f}" height="{side:.1f}" rx="24" fill="#000000" fill-opacity="0.18"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="24" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2"/>'
            f'<rect x="{bx+8:.1f}" y="{by+8:.1f}" width="{side-16:.1f}" height="{side-16:.1f}" rx="18" fill="none" stroke="{accent}" stroke-opacity="0.25" stroke-width="1.2"/>'
        )
    elif shape in ("clean_glow", "clean_spotlight"):
        r = side * 0.46
        frame_svg = (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+22:.1f}" fill="{accent}" fill-opacity="0.14"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{hl_bg}" fill-opacity="0.80" stroke="{accent}" stroke-opacity="0.5" stroke-width="1.8"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r-12:.1f}" fill="none" stroke="#ffffff" stroke-opacity="0.12" stroke-width="1.2" stroke-dasharray="6,6"/>'
        )
    elif shape in ("clean_none", "pure_clean", "clean"):
        r = side * 0.44
        frame_svg = (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+16:.1f}" fill="{accent}" fill-opacity="0.10"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{accent}" stroke-opacity="0.25" stroke-width="1.2" stroke-dasharray="4,8"/>'
        )
    elif shape == "polaroid_frame":
        frame_svg = (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side+36:.1f}" rx="8" fill="#ffffff" stroke="rgba(0,0,0,0.2)" stroke-width="2"/>'
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
    elif shape in ("orbital_rings", "circle_spotlight", "circle"):
        r = side * 0.46
        frame_svg = (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+20:.1f}" fill="none" stroke="{accent}" stroke-opacity="0.45" stroke-width="1.8" stroke-dasharray="8,6"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+8:.1f}" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>'
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
    elif shape in ("squircle_super", "minimal_squircle", "squircle_modern", "squircle"):
        rx_val = int(side * 0.28)
        frame_svg = (
            f'<rect x="{bx+10:.1f}" y="{by+16:.1f}" width="{side:.1f}" height="{side:.1f}" rx="{rx_val}" fill="#000000" fill-opacity="0.26"/>'
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="{rx_val}" fill="{hl_bg}" stroke="rgba(255,255,255,0.32)" stroke-width="2.5"/>'
            f'<rect x="{bx+10:.1f}" y="{by+10:.1f}" width="{side-20:.1f}" height="{side-20:.1f}" rx="{max(6, rx_val-8)}" fill="none" stroke="{accent}" stroke-opacity="0.35" stroke-width="1.5"/>'
        )
    elif shape in ("arch_window", "arch_capsule"):
        r = side / 2
        x1, y1, x2, y2 = bx, by, bx + side, by + side
        d = f"M{x1:.1f},{y1+r:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2:.1f},{y1+r:.1f} V{y2:.1f} H{x1:.1f} Z"
        frame_svg = (
            f'<path d="M{x1+8:.1f},{y1+r+10:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2+8:.1f},{y1+r+10:.1f} V{y2+10:.1f} H{x1+8:.1f} Z" fill="#000000" fill-opacity="0.25"/>'
            f'<path d="{d}" fill="{hl_bg}" stroke="{accent}" stroke-width="2.5"/>'
            f'<path d="M{x1+10:.1f},{y1+r+8:.1f} A{r-10:.1f},{r-10:.1f} 0 0,1 {x2-10:.1f},{y1+r+8:.1f} V{y2-10:.1f} H{x1+10:.1f} Z" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>'
        )
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
        frame_svg = f'<rect x="{bx:.1f}" y="{by:.1f}" width="{side:.1f}" height="{side:.1f}" rx="12" fill="{hl_bg}" stroke="rgba(255,255,255,0.28)" stroke-width="2.5"/>'

    return f"""
    <g id="showcaseBoxComponent">
      {frame_svg}
      {inner_studio_decor}
      {hero_paths}
      {showcase_badge}
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
        hero_sw = max(5.0, hero_size * 0.048 * stroke_scale)
        return _render_paths_svg(ic_paths, hl_stroke, stroke_scale, h_scale, h_ox, h_oy, target_screen_sw=hero_sw)

    start_idx = max(0, min(len(avail_icons) - 1, int(highlight_index)))
    rows = max(1, math.ceil(count / cols))
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    target_cell = min(cell_w * 0.62, cell_h * 0.62)
    mini_sw = max(3.2, target_cell * 0.048 * stroke_scale)
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
        ic_scale = target_cell / max(bw, bh)
        cx = ox + col_i * cell_w + (cell_w - bw * ic_scale) / 2 - bx1 * ic_scale
        cy = oy + row_i * cell_h + (cell_h - bh * ic_scale) / 2 - by1 * ic_scale
        rendered.append(_render_paths_svg(ic_paths, hl_stroke, stroke_scale, ic_scale, cx, cy, target_screen_sw=mini_sw))
    return "\n        ".join(rendered)


# =========================================================================
# 25 Cover / Banner Shapes (Category 1 — Default: Square Solid Box)
# =========================================================================
def _render_cover_shape_svg(
    banner_shape: str, x: float, y: float, w: float, h: float,
    banner_bg: str, hl_bg: str, accent: str, is_right: bool = False, banner_text: str = "#18181B"
) -> str:
    shape = str(banner_shape or "square_solid").lower()
    pad = int(min(w, h) * 0.036)

    # For right-side panels, we mirror horizontal custom paths around panel center if needed
    transform_open = f'<g transform="translate({2*x+w:.1f}, 0) scale(-1, 1)">' if (is_right and shape not in ("square_solid", "rounded_card", "double_split_box", "floating_island", "arch_dome")) else "<g>"
    transform_close = "</g>"

    if shape == "square_solid":
        seam_x = x if is_right else (x + w - 10)
        shadow_x = (x - 28) if is_right else (x + w)
        body = (
            f'<rect x="{shadow_x:.1f}" y="{y:.1f}" width="28" height="{h:.1f}" fill="#000000" fill-opacity="0.07"/>'
            f'<rect x="{shadow_x:.1f}" y="{y:.1f}" width="12" height="{h:.1f}" fill="#000000" fill-opacity="0.06"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{banner_bg}"/>'
            f'<polygon points="{x:.1f},{y:.1f} {x+w:.1f},{y:.1f} {x:.1f},{y+h*0.42:.1f}" fill="#ffffff" fill-opacity="0.07"/>'
            f'<polygon points="{x+w:.1f},{y+h:.1f} {x:.1f},{y+h:.1f} {x+w:.1f},{y+h*0.58:.1f}" fill="#000000" fill-opacity="0.05"/>'
            f'<rect x="{x+28:.1f}" y="{y+28:.1f}" width="{w-56:.1f}" height="{h-56:.1f}" rx="20" fill="none" stroke="{banner_text}" stroke-opacity="0.15" stroke-width="2.2"/>'
            f'<rect x="{seam_x:.1f}" y="{y:.1f}" width="10" height="{h:.1f}" fill="{hl_bg}" fill-opacity="0.88"/>'
        )
    elif shape == "rounded_card":
        body = (
            f'<rect x="{x+pad+12:.1f}" y="{y+pad+16:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="36" fill="#000000" fill-opacity="0.16"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="36" fill="{banner_bg}" stroke="{hl_bg}" stroke-opacity="0.25" stroke-width="3"/>'
            f'<rect x="{x+pad+20:.1f}" y="{y+pad+20:.1f}" width="{w-pad*2-40:.1f}" height="{h-pad*2-40:.1f}" rx="24" fill="none" stroke="{banner_text}" stroke-opacity="0.14" stroke-width="2"/>'
        )
    elif shape == "double_split_box":
        top_h = int(h * 0.53)
        body = (
            f'<rect x="{x+pad+10:.1f}" y="{y+pad+14:.1f}" width="{w-pad*2:.1f}" height="{top_h-pad:.1f}" rx="28" fill="#000000" fill-opacity="0.14"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{top_h-pad:.1f}" rx="28" fill="{banner_bg}"/>'
            f'<rect x="{x+pad+18:.1f}" y="{y+pad+18:.1f}" width="{w-pad*2-36:.1f}" height="{top_h-pad-36:.1f}" rx="18" fill="none" stroke="{banner_text}" stroke-opacity="0.15" stroke-width="2"/>'
            f'<rect x="{x+pad+10:.1f}" y="{y+top_h+pad//2+14:.1f}" width="{w-pad*2:.1f}" height="{h-top_h-pad*1.5:.1f}" rx="28" fill="#000000" fill-opacity="0.16"/>'
            f'<rect x="{x+pad:.1f}" y="{y+top_h+pad//2:.1f}" width="{w-pad*2:.1f}" height="{h-top_h-pad*1.5:.1f}" rx="28" fill="{banner_bg}"/>'
            f'<rect x="{x+pad:.1f}" y="{y+top_h+pad//2:.1f}" width="{w-pad*2:.1f}" height="{h-top_h-pad*1.5:.1f}" rx="28" fill="{hl_bg}" fill-opacity="0.14" stroke="{hl_bg}" stroke-opacity="0.25" stroke-width="2.5"/>'
        )
    elif shape == "chamfer_box":
        c = 44
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        pts = f"{x1+c:.1f},{y1:.1f} {x2-c:.1f},{y1:.1f} {x2:.1f},{y1+c:.1f} {x2:.1f},{y2-c:.1f} {x2-c:.1f},{y2:.1f} {x1+c:.1f},{y2:.1f} {x1:.1f},{y2-c:.1f} {x1:.1f},{y1+c:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}" stroke="{hl_bg}" stroke-opacity="0.3" stroke-width="3"/>'
    elif shape == "notched_ticket":
        r = 36
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        d = f"M{x1+r:.1f},{y1:.1f} H{x2-r:.1f} A{r},{r} 0 0,0 {x2:.1f},{y1+r:.1f} V{y2-r:.1f} A{r},{r} 0 0,0 {x2-r:.1f},{y2:.1f} H{x1+r:.1f} A{r},{r} 0 0,0 {x1:.1f},{y2-r:.1f} V{y1+r:.1f} A{r},{r} 0 0,0 {x1+r:.1f},{y1:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}" stroke="{hl_bg}" stroke-opacity="0.3" stroke-width="3"/>'
    elif shape == "curved_right":
        d = f"M{x:.1f},{y:.1f} L{x+w*0.88:.1f},{y:.1f} Q{x+w*1.12:.1f},{y+h*0.5:.1f} {x+w*0.88:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "concave_arch":
        d = f"M{x:.1f},{y:.1f} L{x+w:.1f},{y:.1f} Q{x+w*0.80:.1f},{y+h*0.5:.1f} {x+w:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("s_wave_smooth", "wave_flow"):
        d1 = f"M{x:.1f},{y:.1f} L{x+w*0.97:.1f},{y:.1f} C{x+w*1.18:.1f},{y+h*0.30:.1f} {x+w*0.76:.1f},{y+h*0.70:.1f} {x+w*1.03:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d2 = f"M{x:.1f},{y:.1f} L{x+w*0.92:.1f},{y:.1f} C{x+w*1.14:.1f},{y+h*0.30:.1f} {x+w*0.72:.1f},{y+h*0.70:.1f} {x+w*0.98:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d1}" fill="{hl_bg}" fill-opacity="0.22"/><path d="{d2}" fill="{banner_bg}"/>'
    elif shape == "double_wave":
        d1 = f"M{x:.1f},{y:.1f} L{x+w*0.98:.1f},{y:.1f} C{x+w*1.18:.1f},{y+h*0.32:.1f} {x+w*0.76:.1f},{y+h*0.68:.1f} {x+w*1.04:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d2 = f"M{x:.1f},{y:.1f} L{x+w*0.90:.1f},{y:.1f} C{x+w*1.10:.1f},{y+h*0.35:.1f} {x+w*0.68:.1f},{y+h*0.65:.1f} {x+w*0.94:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d1}" fill="{banner_bg}" fill-opacity="0.45"/><path d="{d2}" fill="{banner_bg}"/>'
    elif shape == "triple_liquid":
        d1 = f"M{x:.1f},{y:.1f} L{x+w*1.02:.1f},{y:.1f} C{x+w*1.20:.1f},{y+h*0.25:.1f} {x+w*0.78:.1f},{y+h*0.75:.1f} {x+w*1.04:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d2 = f"M{x:.1f},{y:.1f} L{x+w*0.95:.1f},{y:.1f} C{x+w*1.12:.1f},{y+h*0.30:.1f} {x+w*0.72:.1f},{y+h*0.70:.1f} {x+w*0.97:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        d3 = f"M{x:.1f},{y:.1f} L{x+w*0.88:.1f},{y:.1f} C{x+w*1.04:.1f},{y+h*0.35:.1f} {x+w*0.66:.1f},{y+h*0.65:.1f} {x+w*0.91:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d1}" fill="{accent}" fill-opacity="0.35"/><path d="{d2}" fill="{banner_bg}" fill-opacity="0.65"/><path d="{d3}" fill="{banner_bg}"/>'
    elif shape == "diagonal_slash":
        pts1 = f"{x:.1f},{y:.1f} {x+w*1.04:.1f},{y:.1f} {x+w*0.86:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        pts2 = f"{x+w*1.06:.1f},{y:.1f} {x+w*1.10:.1f},{y:.1f} {x+w*0.92:.1f},{y+h:.1f} {x+w*0.88:.1f},{y+h:.1f}"
        body = f'<polygon points="{pts1}" fill="{banner_bg}"/><polygon points="{pts2}" fill="{accent}"/>'
    elif shape == "dual_chevron":
        pts1 = f"{x:.1f},{y:.1f} {x+w*0.90:.1f},{y:.1f} {x+w*1.04:.1f},{y+h*0.5:.1f} {x+w*0.90:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        pts2 = f"{x+w*0.93:.1f},{y:.1f} {x+w*0.98:.1f},{y:.1f} {x+w*1.12:.1f},{y+h*0.5:.1f} {x+w*0.98:.1f},{y+h:.1f} {x+w*0.93:.1f},{y+h:.1f} {x+w*1.07:.1f},{y+h*0.5:.1f}"
        body = f'<polygon points="{pts1}" fill="{banner_bg}"/><polygon points="{pts2}" fill="{accent}" fill-opacity="0.65"/>'
    elif shape == "origami_fold":
        p1 = f"{x:.1f},{y:.1f} {x+w*0.96:.1f},{y:.1f} {x+w*0.84:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        p2 = f"{x+w*0.96:.1f},{y:.1f} {x+w*1.08:.1f},{y+h*0.42:.1f} {x+w*0.84:.1f},{y+h:.1f}"
        body = f'<polygon points="{p1}" fill="{banner_bg}"/><polygon points="{p2}" fill="{banner_bg}" fill-opacity="0.6"/>'
    elif shape == "stepped_blocks":
        h3 = h / 3.0
        body = (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w*0.98:.1f}" height="{h3+2:.1f}" fill="{banner_bg}"/>'
            f'<rect x="{x:.1f}" y="{y+h3:.1f}" width="{w*0.93:.1f}" height="{h3+2:.1f}" fill="{banner_bg}"/>'
            f'<rect x="{x:.1f}" y="{y+h3*2:.1f}" width="{w*0.88:.1f}" height="{h3:.1f}" fill="{banner_bg}"/>'
        )
    elif shape in ("hexagon_panel", "hexagon_shield"):
        pts = f"{x:.1f},{y:.1f} {x+w*0.90:.1f},{y:.1f} {x+w*1.02:.1f},{y+h*0.25:.1f} {x+w*1.02:.1f},{y+h*0.75:.1f} {x+w*0.90:.1f},{y+h:.1f} {x:.1f},{y+h:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}"/>'
    elif shape in ("leaf_organic", "eco_leaf"):
        d = f"M{x:.1f},{y:.1f} L{x+w*0.88:.1f},{y:.1f} C{x+w*1.12:.1f},{y+h*0.22:.1f} {x+w*1.12:.1f},{y+h*0.78:.1f} {x+w*0.78:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("droplet_curve", "droplet_flow"):
        d = f"M{x:.1f},{y:.1f} L{x+w*0.84:.1f},{y:.1f} C{x+w*0.84:.1f},{y+h*0.35:.1f} {x+w*1.14:.1f},{y+h*0.62:.1f} {x+w*0.88:.1f},{y+h:.1f} L{x:.1f},{y+h:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape == "scallop_edge":
        circles = []
        n_sc = 9
        r_sc = (h / n_sc) * 0.62
        for k in range(n_sc):
            cy_k = y + (k + 0.5) * (h / n_sc)
            circles.append(f'<circle cx="{x+w*0.90:.1f}" cy="{cy_k:.1f}" r="{r_sc:.1f}" fill="{banner_bg}"/>')
        body = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w*0.90:.1f}" height="{h:.1f}" fill="{banner_bg}"/>' + "".join(circles)
    elif shape == "zigzag_saw":
        pts = [f"{x:.1f},{y:.1f}", f"{x+w*0.92:.1f},{y:.1f}"]
        n_z = 12
        step_y = h / n_z
        for k in range(n_z):
            pts.append(f"{x+w*0.99:.1f},{y+(k+0.5)*step_y:.1f}")
            pts.append(f"{x+w*0.92:.1f},{y+(k+1.0)*step_y:.1f}")
        pts.append(f"{x:.1f},{y+h:.1f}")
        body = f'<polygon points="{" ".join(pts)}" fill="{banner_bg}"/>'
    elif shape == "ribbon_banner":
        x1, y1, x2, y2 = x + pad, y, x + w - pad, y + h - pad
        pts = f"{x1:.1f},{y1:.1f} {x2:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x+w/2:.1f},{y2-48:.1f} {x1:.1f},{y2:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}"/>'
    elif shape == "floating_island":
        body = (
            f'<rect x="{x+pad+14:.1f}" y="{y+pad+18:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="32" fill="#000000" fill-opacity="0.22"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="32" fill="{banner_bg}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="3"/>'
            f'<rect x="{x+pad+20:.1f}" y="{y+pad+20:.1f}" width="{w-pad*2-40:.1f}" height="{h-pad*2-40:.1f}" rx="22" fill="none" stroke="{banner_text}" stroke-opacity="0.14" stroke-width="2"/>'
        )
    elif shape == "layered_cards":
        body = (
            f'<rect x="{x+pad+24:.1f}" y="{y+pad+24:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="24" fill="{banner_bg}" fill-opacity="0.35"/>'
            f'<rect x="{x+pad+12:.1f}" y="{y+pad+12:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="24" fill="{banner_bg}" fill-opacity="0.65"/>'
            f'<rect x="{x+pad:.1f}" y="{y+pad:.1f}" width="{w-pad*2:.1f}" height="{h-pad*2:.1f}" rx="24" fill="{banner_bg}"/>'
        )
    elif shape == "cyber_hud_frame":
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        pts = f"{x1:.1f},{y1:.1f} {x2-48:.1f},{y1:.1f} {x2:.1f},{y1+48:.1f} {x2:.1f},{y2-80:.1f} {x2-28:.1f},{y2-52:.1f} {x2-28:.1f},{y2:.1f} {x1+36:.1f},{y2:.1f} {x1:.1f},{y2-36:.1f}"
        body = f'<polygon points="{pts}" fill="{banner_bg}" stroke="{accent}" stroke-width="4.5"/>'
    elif shape == "arch_dome":
        x1, y1, x2, y2 = x + pad, y + pad, x + w - pad, y + h - pad
        r = (x2 - x1) / 2
        d = f"M{x1:.1f},{y1+r:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2:.1f},{y1+r:.1f} V{y2:.1f} H{x1:.1f} Z"
        body = f'<path d="{d}" fill="{banner_bg}"/>'
    elif shape in ("pixel_dissolve", "pixel_matrix"):
        solid_w = w * 0.86
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


def _render_count_medallion_svg(
    cx: float, count_cy: float, count_fs: int, count_val: str,
    banner_text: str, hl_bg: str, accent: str, inner_w: float
) -> str:
    """Renders an agency-grade monumental count badge lockup so the cover center never looks empty."""
    c_str = sanitize_text(count_val)
    med_y = count_cy - count_fs * 0.34
    ring_r = min(inner_w * 0.44, count_fs * 0.64)
    pill_w = min(inner_w * 0.78, max(260, count_fs * 1.18))
    pill_h = max(44, int(count_fs * 0.19))
    pill_y = count_cy + int(count_fs * 0.08)
    pill_fs = max(16, int(pill_h * 0.45))

    return f"""
    <g id="monumentalCountLockup">
      <circle cx="{cx:.1f}" cy="{med_y:.1f}" r="{ring_r+16:.1f}" fill="none" stroke="{banner_text}" stroke-opacity="0.16" stroke-width="2" stroke-dasharray="12,8"/>
      <circle cx="{cx:.1f}" cy="{med_y:.1f}" r="{ring_r:.1f}" fill="{banner_text}" fill-opacity="0.07" stroke="{banner_text}" stroke-opacity="0.14" stroke-width="2"/>
      <line x1="{cx - inner_w*0.42:.1f}" y1="{med_y:.1f}" x2="{cx - ring_r - 24:.1f}" y2="{med_y:.1f}" stroke="{banner_text}" stroke-opacity="0.25" stroke-width="3"/>
      <line x1="{cx + ring_r + 24:.1f}" y1="{med_y:.1f}" x2="{cx + inner_w*0.42:.1f}" y2="{med_y:.1f}" stroke="{banner_text}" stroke-opacity="0.25" stroke-width="3"/>
      <text x="{cx+6:.1f}" y="{count_cy+8:.1f}"
            font-size="{count_fs}" font-weight="900" fill="#000000" opacity="0.12" letter-spacing="-3"
            text-anchor="middle" class="count">{c_str}</text>
      <text x="{cx:.1f}" y="{count_cy:.1f}"
            font-size="{count_fs}" font-weight="900" fill="{banner_text}" letter-spacing="-3"
            text-anchor="middle" class="count">{c_str}</text>
      <rect x="{cx - pill_w/2 + 4:.1f}" y="{pill_y + 5:.1f}" width="{pill_w:.1f}" height="{pill_h:.1f}" rx="{pill_h//2}" fill="#000000" fill-opacity="0.20"/>
      <rect x="{cx - pill_w/2:.1f}" y="{pill_y:.1f}" width="{pill_w:.1f}" height="{pill_h:.1f}" rx="{pill_h//2}" fill="{hl_bg}" stroke="#ffffff" stroke-opacity="0.28" stroke-width="2"/>
      <text x="{cx:.1f}" y="{pill_y + pill_h*0.66:.1f}" font-size="{pill_fs}" font-weight="800" letter-spacing="3.5" fill="#FFFFFF" text-anchor="middle" class="mono">VECTOR ICON PACK</text>
    </g>"""


def _render_format_badges_bar_svg(cx: float, y: float, inner_w: float, banner_text: str, hl_bg: str) -> str:
    """Renders crisp deliverable file format spec pills (SVG, EPS 10, PNG HD, VECTOR) at the footer of the cover."""
    badges = ["SVG", "EPS 10", "PNG HD", "AI VECTOR"]
    gap = 12
    total_w = min(inner_w * 0.96, 740)
    bw = (total_w - gap * (len(badges) - 1)) / len(badges)
    bh = max(34, int(total_w * 0.056))
    fs = max(13, int(bh * 0.44))
    start_x = cx - total_w / 2
    elems = []
    for i, label in enumerate(badges):
        bx = start_x + i * (bw + gap)
        elems.append(
            f'<rect x="{bx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" '
            f'fill="{banner_text}" fill-opacity="0.12" stroke="{banner_text}" stroke-opacity="0.24" stroke-width="1.8"/>'
            f'<text x="{bx + bw/2:.1f}" y="{y + bh*0.67:.1f}" font-size="{fs}" font-weight="800" letter-spacing="1.5" '
            f'fill="{banner_text}" text-anchor="middle" class="mono">{label}</text>'
        )
    return '<g id="coverFormatBadgesBar">' + "".join(elems) + "</g>"


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
    ui_scale = max(1.0, H / 1080.0)

    # Horizontal Top or Bottom Bar Mode
    if panel_pos in ("top", "bottom"):
        bar_h = int(round(H * 0.25))
        is_bottom = (panel_pos == "bottom")
        bar_y = (H - bar_h) if is_bottom else 0
        sheet_y = 0 if is_bottom else bar_h
        sheet_h = H - bar_h

        paths_svg_group = _render_adaptive_sheet_icons(
            model, icons_meta, c,
            sheet_x=0, sheet_y=sheet_y, sheet_w=W, sheet_h=sheet_h
        )

        raw_t_fs = int(c.get("title_fs") or 0)
        raw_c_fs = int(c.get("count_fs") or 0)
        raw_s_fs = int(c.get("sub_fs") or 0)
        title_fs = int(round(raw_t_fs * ui_scale * 0.85)) if (0 < raw_t_fs <= 120) else (raw_t_fs or max(48, int(round(bar_h * 0.22))))
        count_fs = int(round(raw_c_fs * ui_scale * 0.72)) if (0 < raw_c_fs <= 260) else (raw_c_fs or max(110, int(round(bar_h * 0.48))))
        sub_fs = int(round(raw_s_fs * ui_scale * 0.85)) if (0 < raw_s_fs <= 48) else (raw_s_fs or max(20, int(round(bar_h * 0.075))))

        header_y_off = float(c.get("header_y_offset") or 0.0) * ui_scale
        count_y_off = float(c.get("count_y_offset") or 0.0) * ui_scale
        showcase_y_off = float(c.get("showcase_y_offset") or 0.0) * ui_scale
        spacing_val = float(c.get("element_spacing") or 0.0) * ui_scale
        sc_scale = float(c.get("showcase_scale") or 1.0)
        if sc_scale <= 0:
            sc_scale = 1.0

        title_svg = _render_title_highlight(
            title=c["title"], subtitle=c["subtitle"],
            cx=int(W * 0.44), cy=bar_y + int(bar_h * 0.48) + int(header_y_off),
            title_fs=title_fs, sub_fs=sub_fs,
            banner_text=banner_text, banner_sub=banner_sub,
            title_font=title_font, sub_font=sub_font,
            style=title_hl_style, is_centered=True,
            max_w=W * 0.42, accent=accent, hl_bg=hl_bg
        )

        hl_svg = ""
        if show_highlight:
            sc_size = int(bar_h * 0.84 * sc_scale)
            hl_svg = _render_showcase_box(
                model, icons_meta, c,
                cx=W - int(W * 0.11), cy=bar_y + bar_h / 2 + int(showcase_y_off),
                w=sc_size, h=sc_size, stroke_scale=stroke_scale
            )

        seam_y = bar_y if is_bottom else (bar_y + bar_h - 8)
        count_box_x = int(W * 0.04)
        count_box_w = int(W * 0.14)
        count_box_h = int(bar_h * 0.74)
        count_box_y = bar_y + (bar_h - count_box_h) // 2 + int(count_y_off)

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
    <rect x="24" y="{bar_y+20}" width="{W-48}" height="{bar_h-40}" rx="18" fill="none" stroke="{banner_text}" stroke-opacity="0.15" stroke-width="2"/>
    <rect x="0" y="{seam_y}" width="{W}" height="8" fill="{hl_bg}"/>
    <rect x="{count_box_x}" y="{count_box_y}" width="{count_box_w}" height="{count_box_h}" rx="20" fill="{banner_text}" fill-opacity="0.09" stroke="{banner_text}" stroke-opacity="0.2" stroke-width="2"/>
    <text x="{count_box_x + count_box_w/2:.1f}" y="{bar_y + int(bar_h * 0.62)}" font-size="{count_fs}" font-weight="900" fill="{banner_text}" text-anchor="middle" class="count">{sanitize_text(count_val)}</text>
    <text x="{count_box_x + count_box_w/2:.1f}" y="{bar_y + int(bar_h * 0.80)}" font-size="{max(14, int(bar_h*0.042))}" font-weight="800" letter-spacing="3" fill="{banner_text}" text-anchor="middle" class="mono">ICONS PACK</text>
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
        banner_bg, hl_bg, accent or hl_bg, is_right=is_right, banner_text=banner_text
    )
    cover_decor_svg = _render_cover_decor_svg(
        decor, panel_x, 0, banner_w, H, banner_text, accent or hl_bg
    )

    inner_cx = panel_x + banner_w * 0.49 if not is_right else panel_x + banner_w * 0.51
    inner_w = banner_w * 0.82

    raw_t_fs = int(c.get("title_fs") or 0)
    raw_c_fs = int(c.get("count_fs") or 0)
    raw_s_fs = int(c.get("sub_fs") or 0)

    # Auto-scale 1080p UI slider values up to 4K canvas proportions!
    title_fs = int(round(raw_t_fs * ui_scale)) if (0 < raw_t_fs <= 120) else (raw_t_fs or max(68, int(round(banner_w * 0.102))))
    count_fs = int(round(raw_c_fs * ui_scale * 0.88)) if (0 < raw_c_fs <= 260) else (raw_c_fs or max(180, int(round(banner_w * 0.27))))
    sub_fs = int(round(raw_s_fs * ui_scale * 0.82)) if (0 < raw_s_fs <= 48) else (raw_s_fs or max(24, int(round(banner_w * 0.032))))

    header_y_off = float(c.get("header_y_offset") or 0.0) * ui_scale
    count_y_off = float(c.get("count_y_offset") or 0.0) * ui_scale
    showcase_y_off = float(c.get("showcase_y_offset") or 0.0) * ui_scale
    badge_y_off = float(c.get("badge_y_offset") or 0.0) * ui_scale
    spacing_val = float(c.get("element_spacing") or 0.0) * ui_scale
    sc_scale = float(c.get("showcase_scale") or 1.0)
    if sc_scale <= 0:
        sc_scale = 1.0

    if show_highlight:
        # spacing_val smoothly expands the gap: header moves up (-spacing_val), showcase moves down (+spacing_val)
        title_cy = int(H * 0.135 + header_y_off - spacing_val)
        count_cy = int(H * 0.405 + count_y_off)
        box_cy = int(H * 0.725 + showcase_y_off + spacing_val)
        base_size = min(inner_w * 0.82, H * 0.35)
        box_size = max(50.0, base_size * sc_scale)
    else:
        title_cy = int(H * 0.24 + header_y_off - spacing_val)
        count_cy = int(H * 0.60 + count_y_off + spacing_val)
        box_cy = 0
        box_size = 0

    title_svg = _render_title_highlight(
        title=c["title"], subtitle=c["subtitle"],
        cx=inner_cx, cy=title_cy,
        title_fs=title_fs, sub_fs=sub_fs,
        banner_text=banner_text, banner_sub=banner_sub,
        title_font=title_font, sub_font=sub_font,
        style=title_hl_style, is_centered=True,
        max_w=inner_w, accent=accent, hl_bg=hl_bg
    )

    count_medallion_svg = _render_count_medallion_svg(
        cx=inner_cx, count_cy=count_cy, count_fs=count_fs, count_val=count_val,
        banner_text=banner_text, hl_bg=hl_bg, accent=accent or hl_bg, inner_w=inner_w
    )

    hl_svg = ""
    if show_highlight and box_size > 50:
        hl_svg = _render_showcase_box(
            model, icons_meta, c,
            cx=inner_cx, cy=box_cy,
            w=box_size, h=box_size,
            stroke_scale=stroke_scale
        )

    badges_y = int(H * 0.928 + badge_y_off + (spacing_val * 0.3))
    format_badges_svg = _render_format_badges_bar_svg(
        cx=inner_cx, y=badges_y, inner_w=inner_w, banner_text=banner_text, hl_bg=hl_bg
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
    {count_medallion_svg}
    {hl_svg}
    {format_badges_svg}
  </g>
</svg>"""


def _build_custom_image_template(
    model: Model, icons_meta: list[dict], c: dict, W: int, H: int
) -> str:
    """Renders custom uploaded JPEG/PNG template (ChatGPT / Midjourney / Canva / Stock Mockup)
    with seamless overlay of sheet icons, hero showcase icon, and editable typography."""
    img_src = str(c.get("custom_image_url") or c.get("custom_image_b64") or "").strip()

    # If img_src is a relative server path /api/custom_templates/{id}/image, convert to base64 for resvg
    if img_src.startswith("/api/custom_templates/"):
        parts = img_src.split("/")
        if len(parts) >= 4:
            tpl_id = parts[3]
            from pathlib import Path
            import base64
            for d in (Path("data/custom_templates"), Path("server/data/custom_templates")):
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    p = d / f"{tpl_id}{ext}"
                    if p.exists():
                        mime = "image/png" if ext == ".png" else "image/jpeg"
                        b64_data = base64.b64encode(p.read_bytes()).decode("ascii")
                        img_src = f"data:{mime};base64,{b64_data}"
                        break
                if img_src.startswith("data:"):
                    break
    elif img_src.startswith("/static/"):
        from pathlib import Path
        import base64
        local_p = Path("server") / img_src.lstrip("/")
        if local_p.exists():
            mime = "image/png" if local_p.suffix == ".png" else "image/jpeg"
            b64_data = base64.b64encode(local_p.read_bytes()).decode("ascii")
            img_src = f"data:{mime};base64,{b64_data}"

    bg_svg = ""
    if img_src:
        bg_svg = f'<image href="{img_src}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice"/>'
    else:
        bg_svg = (
            f'<rect width="{W}" height="{H}" fill="#11141D"/>'
            f'<rect x="{int(W*0.03)}" y="{int(H*0.05)}" width="{int(W*0.94)}" height="{int(H*0.90)}" rx="20" fill="#181B24" stroke="rgba(255,255,255,0.08)" stroke-width="2" stroke-dasharray="10,8"/>'
            f'<text x="{W/2:.1f}" y="{H/2:.1f}" fill="#94A3B8" font-size="28" font-weight="700" text-anchor="middle" font-family="sans-serif">Upload your ChatGPT / AI Presentation Mockup Image</text>'
        )

    fonts_import, title_font, count_font, sub_font = _get_font_css(c.get("font_family", "bebas"))

    # Editable Text Overlays
    text_overlay_svg = ""
    if c.get("custom_text_enable", True):
        raw_t = str(c.get("title") or "TECHNOLOGY").strip()
        if any(sep in raw_t for sep in ("_", "/", "\\")) or re.search(r'[0-9a-f]{6,}', raw_t, re.I):
            title_val = sanitize_text(_clean_template_title(raw_t))
        else:
            title_val = sanitize_text(raw_t)
        sub_val = sanitize_text((c.get("subtitle") or "Editable Line Icons").upper())
        count_val = sanitize_text(c.get("count") or (len(icons_meta) if icons_meta else "24"))

        banner_text = c.get("banner_text", "#FFFFFF")
        banner_sub = c.get("banner_sub", "#E2E8F0")

        title_fs = int(c.get("title_fs") or 56)
        sub_fs = int(c.get("sub_fs") or 22)
        count_fs = int(c.get("count_fs") or 140)

        tx = float(c.get("custom_title_x", 0.18)) * W
        ty = float(c.get("custom_title_y", 0.18)) * H
        sx = float(c.get("custom_sub_x", 0.18)) * W
        sy = float(c.get("custom_sub_y", 0.24)) * H
        cx = float(c.get("custom_count_x", 0.18)) * W
        cy = float(c.get("custom_count_y", 0.44)) * H

        show_title = c.get("custom_show_title", True)
        show_sub = c.get("custom_show_sub", True)
        show_count = c.get("custom_show_count", True)

        txt_parts = []
        if show_title and title_val:
            txt_parts.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="{title_fs}" font-weight="900" letter-spacing="3" '
                f'fill="{banner_text}" text-anchor="middle" style="font-family:{title_font};">{title_val}</text>'
            )
        if show_sub and sub_val:
            txt_parts.append(
                f'<text x="{sx:.1f}" y="{sy:.1f}" font-size="{sub_fs}" font-weight="800" letter-spacing="2.2" '
                f'fill="{banner_sub}" text-anchor="middle" style="font-family:{sub_font};">{sub_val}</text>'
            )
        if show_count and count_val:
            txt_parts.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{count_fs}" font-weight="900" letter-spacing="-3" '
                f'fill="{banner_text}" text-anchor="middle" class="count">{count_val}</text>'
            )
        text_overlay_svg = f'<g id="customTextOverlays">{"".join(txt_parts)}</g>'

    # Hero Showcase Icon
    hero_svg = ""
    if c.get("custom_hero_enable", True):
        hx = float(c.get("custom_hero_x", 0.18)) * W
        hy = float(c.get("custom_hero_y", 0.68)) * H
        h_size = float(c.get("custom_hero_size", 0.20)) * min(W, H)
        stroke_scale = float(c.get("stroke_scale", 1.0))
        hero_svg = _render_showcase_box(
            model, icons_meta, c,
            cx=hx, cy=hy, w=h_size * 1.5, h=h_size * 1.5,
            stroke_scale=stroke_scale
        )

    # Sheet Icons Grid Overlay
    gx = float(c.get("custom_grid_x", 0.40)) * W
    gy = float(c.get("custom_grid_y", 0.10)) * H
    gw = float(c.get("custom_grid_w", 0.55)) * W
    gh = float(c.get("custom_grid_h", 0.78)) * H

    c_copy = dict(c)
    if "custom_decor" in c:
        c_copy["decor_element"] = c["custom_decor"]
    else:
        c_copy["decor_element"] = "none"

    grid_icons_svg = _render_adaptive_sheet_icons(
        model, icons_meta, c_copy,
        sheet_x=gx, sheet_y=gy, sheet_w=gw, sheet_h=gh
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
    </style>
  </defs>
  <!-- Background Image Template -->
  {bg_svg}
  <!-- Sheet Icons Overlay -->
  <g id="customGridIconsGroup">
    {grid_icons_svg}
  </g>
  <!-- Hero Showcase Icon -->
  {hero_svg}
  <!-- Editable Text Overlays -->
  {text_overlay_svg}
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
    if design == "custom_image" or c.get("custom_image_url"):
        try:
            W = int(float(c.get("custom_img_w") or 1920))
            H = int(float(c.get("custom_img_h") or 1080))
        except Exception:
            W, H = 1920, 1080
        W = max(800, min(3840, W))
        H = max(450, min(2160, H))
        return _build_custom_image_template(model, icons_meta, c, W, H)

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
        f"%%Title: {escape_ps_text(_clean_template_title(c['title']))} - {count_val} Icons",
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

    valid_ws = [p.w for p in model.paths if p.w > 0]
    med_w = float(np.median(valid_ws)) if valid_ws else 4.0
    uniform_eps_sw = max(2.5, med_w * stroke_scale * scale)

    for p in model.paths:
        lines.append(f"{uniform_eps_sw:.2f} LW")
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


def make_arc_path(cx, cy, r, deg_start, deg_end, w=4.0, steps=8):
    """Generates a smooth circular arc using cubic spline interpolation."""
    angs = np.linspace(math.radians(deg_start), math.radians(deg_end), steps)
    pts = np.column_stack([cx + r * np.cos(angs), cy + r * np.sin(angs)])
    N = len(pts)
    A = pts.copy()
    Hin = np.zeros_like(A)
    Hout = np.zeros_like(A)
    d_ang = (math.radians(deg_end) - math.radians(deg_start)) / max(1, steps - 1)
    t_len = (4.0 / 3.0) * math.tan(d_ang / 4.0) * r
    for i, a in enumerate(angs):
        tx, ty = -math.sin(a), math.cos(a)
        Hout[i] = A[i] + np.array([tx * t_len, ty * t_len])
        Hin[i] = A[i] - np.array([tx * t_len, ty * t_len])
    return Path(A, Hin, Hout, w, closed=False)


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
            paths.append(make_line_path([[cx + 15, cy + 15], [cx + 46, cy + 46]], w))
        elif idx == 1:  # Settings
            paths.append(make_circle_path(cx, cy, 24, w))
            for a in range(0, 360, 45):
                rad = math.radians(a)
                p1 = [cx + 32 * math.cos(rad), cy + 32 * math.sin(rad)]
                p2 = [cx + 46 * math.cos(rad), cy + 46 * math.sin(rad)]
                paths.append(make_line_path([p1, p2], w))
        elif idx == 2:  # User
            paths.append(make_circle_path(cx, cy - 20, 22, w))
            paths.append(make_arc_path(cx, cy + 52, 42, 195, 345, w))
        elif idx == 3:  # Home
            paths.append(make_line_path([[cx - 52, cy - 5], [cx, cy - 50], [cx + 52, cy - 5]], w))
            paths.append(make_line_path([[cx - 40, cy - 5], [cx - 40, cy + 48], [cx + 40, cy + 48], [cx + 40, cy - 5]], w))
            paths.append(make_line_path([[cx - 16, cy + 48], [cx - 16, cy + 16], [cx + 16, cy + 16], [cx + 16, cy + 48]], w))
        elif idx == 4:  # Heart
            paths.append(make_arc_path(cx - 22, cy - 14, 22, 135, 360, w))
            paths.append(make_arc_path(cx + 22, cy - 14, 22, 180, 405, w))
            paths.append(make_line_path([[cx - 38, cy + 2], [cx, cy + 42], [cx + 38, cy + 2]], w))
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
            paths.append(make_arc_path(cx, cy - 8, 32, 180, 360, w))
            paths.append(make_line_path([[cx - 32, cy - 8], [cx - 32, cy + 28]], w))
            paths.append(make_line_path([[cx + 32, cy - 8], [cx + 32, cy + 28]], w))
            paths.append(make_line_path([[cx - 44, cy + 28], [cx + 44, cy + 28]], w))
            paths.append(make_arc_path(cx, cy + 28, 12, 0, 180, w))
        elif idx == 8:  # Lock
            paths.append(make_line_path([[cx - 42, cy - 4], [cx + 42, cy - 4], [cx + 42, cy + 46], [cx - 42, cy + 46]], w, closed=True))
            paths.append(make_arc_path(cx, cy - 18, 24, 180, 360, w))
            paths.append(make_line_path([[cx - 24, cy - 18], [cx - 24, cy - 4]], w))
            paths.append(make_line_path([[cx + 24, cy - 18], [cx + 24, cy - 4]], w))
            paths.append(make_circle_path(cx, cy + 20, 7, w))
        elif idx == 9:  # Cloud
            paths.append(make_line_path([[cx - 32, cy + 30], [cx + 34, cy + 30]], w))
            paths.append(make_arc_path(cx - 32, cy + 12, 18, 90, 270, w))
            paths.append(make_arc_path(cx - 6, cy - 8, 26, 165, 350, w))
            paths.append(make_arc_path(cx + 32, cy + 10, 20, 260, 450, w))
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
            paths.append(make_line_path([[cx - 24, cy - 42], [cx - 24, cy - 24]], w))
            paths.append(make_line_path([[cx + 24, cy - 42], [cx + 24, cy - 24]], w))
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
            paths.append(make_line_path([[cx, cy], [cx, cy - 26]], w))
            paths.append(make_line_path([[cx, cy], [cx + 20, cy]], w))
        elif idx == 17:  # Bookmark
            paths.append(make_line_path([[cx - 32, cy - 44], [cx + 32, cy - 44], [cx + 32, cy + 44], [cx, cy + 20], [cx - 32, cy + 44]], w, closed=True))
        elif idx == 18:  # Shield
            paths.append(make_line_path([[cx, cy - 44], [cx + 42, cy - 30], [cx + 36, cy + 14], [cx, cy + 44], [cx - 36, cy + 14], [cx - 42, cy - 30]], w, closed=True))
            paths.append(make_line_path([[cx - 18, cy + 2], [cx - 6, cy + 16], [cx + 20, cy - 14]], w))
        elif idx == 19:  # Download
            paths.append(make_line_path([[cx, cy - 36], [cx, cy + 16]], w))
            paths.append(make_line_path([[cx - 20, cy - 4], [cx, cy + 16], [cx + 20, cy - 4]], w))
            paths.append(make_line_path([[cx - 42, cy + 12], [cx - 42, cy + 40], [cx + 42, cy + 40], [cx + 42, cy + 12]], w))
        elif idx == 20:  # Upload
            paths.append(make_line_path([[cx, cy + 20], [cx, cy - 32]], w))
            paths.append(make_line_path([[cx - 20, cy - 12], [cx, cy - 32], [cx + 20, cy - 12]], w))
            paths.append(make_line_path([[cx - 42, cy + 12], [cx - 42, cy + 40], [cx + 42, cy + 40], [cx + 42, cy + 12]], w))
        elif idx == 21:  # Compass
            paths.append(make_circle_path(cx, cy, 44, w))
            paths.append(make_line_path([[cx, cy - 32], [cx + 10, cy], [cx, cy + 32], [cx - 10, cy]], w, closed=True))
        elif idx == 22:  # Battery
            paths.append(make_line_path([[cx - 46, cy - 24], [cx + 38, cy - 24], [cx + 38, cy + 24], [cx - 46, cy + 24]], w, closed=True))
            paths.append(make_line_path([[cx + 38, cy - 12], [cx + 46, cy - 12], [cx + 46, cy + 12], [cx + 38, cy + 12]], w, closed=True))
            paths.append(make_line_path([[cx - 30, cy - 12], [cx - 30, cy + 12]], w))
            paths.append(make_line_path([[cx - 12, cy - 12], [cx - 12, cy + 12]], w))
        elif idx == 23:  # Globe
            paths.append(make_circle_path(cx, cy, 44, w))
            paths.append(make_line_path([[cx - 44, cy], [cx + 44, cy]], w))
            paths.append(make_line_path([[cx, cy - 44], [cx, cy + 44]], w))
            paths.append(make_line_path([[cx - 22, cy - 38], [cx - 28, cy], [cx - 22, cy + 38]], w))
            paths.append(make_line_path([[cx + 22, cy - 38], [cx + 28, cy], [cx + 22, cy + 38]], w))

    m = Model(paths, 2400, 1600)
    _CACHED_DEMO_DATA = (m, icons)
    return m.copy(), [dict(ic) for ic in icons]
