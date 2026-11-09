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
        "design": "vectuz_sidebar",
        "title": "TECHNOLOGY",
        "count": "24",
        "subtitle": "Editable Line Icons",
        "layout": "landscape_16_9",
        "stroke_scale": 1.0,
        "show_highlight": True,
        "highlight_mode": "mini_4",
        "font_family": "bebas",
        "title_highlight": "pill",
        "showcase_shape": "card"
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

def _extract_icon_paths(model: Model, box: list[float] | tuple[float, ...], pad: float = 6.0) -> list[Path]:
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


def _get_font_css(font_family: str = "bebas") -> tuple[str, str, str, str]:
    font_family = str(font_family or "bebas").lower()
    fonts_import = """
      @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&amp;family=Montserrat:wght@700;800;900&amp;family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=Space+Grotesk:wght@700&amp;family=Playfair+Display:wght@700;900&amp;family=JetBrains+Mono:wght@700;800&amp;display=swap');
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
    elif font_family == "mono":
        title_font = "'JetBrains Mono', 'Consolas', monospace"
        count_font = "'JetBrains Mono', 'Consolas', monospace"
        sub_font = "'JetBrains Mono', 'Consolas', monospace"
    else:  # default "bebas"
        title_font = "'Bebas Neue', 'Impact', 'Arial Black', sans-serif"
        count_font = "'Bebas Neue', 'Impact', 'Arial Black', sans-serif"
        sub_font = "'Montserrat', 'Trebuchet MS', 'Segoe UI', sans-serif"
    return fonts_import, title_font, count_font, sub_font


def _render_title_highlight(
    title: str, subtitle: str,
    cx: float, cy: float,
    title_fs: int, sub_fs: int,
    banner_text: str, banner_sub: str,
    title_font: str, sub_font: str,
    style: str = "pill",
    is_centered: bool = True,
    max_w: float = 600
) -> str:
    title_clean = sanitize_text(title)
    sub_clean = sanitize_text(subtitle)
    anchor = "middle" if is_centered else "start"
    
    est_w = min(max_w, max(280, int(len(title) * title_fs * 0.65) + 60))
    rect_x = cx - est_w / 2 if is_centered else cx

    if style == "pill":
        pill_h = int(title_fs * 1.55)
        pill_y = cy - int(title_fs * 0.95)
        rx = pill_h // 2
        return f"""
    <!-- Title Highlight: Frosted Pill Plate -->
    <g id="titleHighlightPill">
      <rect x="{rect_x}" y="{pill_y}" width="{est_w}" height="{pill_h}" rx="{rx}"
            fill="rgba(0,0,0,0.22)" stroke="rgba(255,255,255,0.25)" stroke-width="2"/>
      <text x="{cx}" y="{pill_y - 12}" font-size="{max(11, int(title_fs * 0.28))}" font-weight="800" 
            letter-spacing="3" fill="{banner_sub}" text-anchor="{anchor}" class="mono">
        &#9679; 100% VECTOR ICON SET &#9679;
      </text>
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3" 
            fill="{banner_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <text x="{cx}" y="{cy + int(sub_fs * 1.6)}" font-size="{sub_fs}" font-weight="700" letter-spacing="1" 
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""
    elif style == "glow_bar":
        bar_w = min(est_w, 420)
        bar_x = cx - bar_w / 2 if is_centered else cx
        return f"""
    <!-- Title Highlight: Glow Accent Bar -->
    <g id="titleHighlightGlowBar">
      <text x="{cx}" y="{cy - 14}" font-size="{max(11, int(title_fs * 0.26))}" font-weight="800" 
            letter-spacing="2.5" fill="{banner_sub}" text-anchor="{anchor}" class="mono">
        PREMIUM COLLECTION
      </text>
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3" 
            fill="{banner_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <rect x="{bar_x}" y="{cy + 10}" width="{bar_w}" height="4.5" rx="2.25" fill="{banner_text}" opacity="0.9"/>
      <circle cx="{cx if is_centered else cx + 20}" cy="{cy + 12}" r="4" fill="{banner_sub}"/>
      <text x="{cx}" y="{cy + int(sub_fs * 1.8) + 14}" font-size="{sub_fs}" font-weight="700" letter-spacing="1" 
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""
    elif style == "brackets":
        b_pad = 20
        b_x1 = (cx - est_w / 2) if is_centered else cx
        b_x2 = b_x1 + est_w
        b_y1 = cy - int(title_fs * 0.9) - b_pad
        b_y2 = cy + int(sub_fs * 1.6) + b_pad
        tick = 22
        return f"""
    <!-- Title Highlight: Architectural Brackets -->
    <g id="titleHighlightBrackets">
      <path d="M {b_x1 + tick} {b_y1} L {b_x1} {b_y1} L {b_x1} {b_y1 + tick}" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5"/>
      <path d="M {b_x2 - tick} {b_y1} L {b_x2} {b_y1} L {b_x2} {b_y1 + tick}" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5"/>
      <path d="M {b_x1 + tick} {b_y2} L {b_x1} {b_y2} L {b_x1} {b_y2 - tick}" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5"/>
      <path d="M {b_x2 - tick} {b_y2} L {b_x2} {b_y2} L {b_x2} {b_y2 - tick}" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="2.5"/>
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3" 
            fill="{banner_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <text x="{cx}" y="{cy + int(sub_fs * 1.6)}" font-size="{sub_fs}" font-weight="700" letter-spacing="1" 
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""
    elif style == "ribbon":
        rib_w = min(est_w, 360)
        rib_x = cx - rib_w / 2 if is_centered else cx
        return f"""
    <!-- Title Highlight: Ribbon Tag -->
    <g id="titleHighlightRibbon">
      <rect x="{rib_x}" y="{cy - title_fs - 24}" width="{rib_w}" height="28" rx="14"
            fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
      <text x="{cx}" y="{cy - title_fs - 5}" font-size="12" font-weight="800" letter-spacing="2.5" 
            fill="{banner_text}" text-anchor="{anchor}" class="mono">
        &#9733; PREMIUM MICROSTOCK &#9733;
      </text>
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3" 
            fill="{banner_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <text x="{cx}" y="{cy + int(sub_fs * 1.6)}" font-size="{sub_fs}" font-weight="700" letter-spacing="1" 
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""
    else:  # "clean"
        return f"""
    <!-- Title Highlight: Clean Minimal -->
    <g id="titleHighlightClean">
      <text x="{cx}" y="{cy}" font-size="{title_fs}" font-weight="900" letter-spacing="3" 
            fill="{banner_text}" text-anchor="{anchor}" style="font-family:{title_font};">
        {title_clean}
      </text>
      <text x="{cx}" y="{cy + int(sub_fs * 1.6)}" font-size="{sub_fs}" font-weight="700" letter-spacing="1" 
            fill="{banner_sub}" text-anchor="{anchor}" style="font-family:{sub_font};">
        {sub_clean}
      </text>
    </g>"""


def _render_showcase_box(
    model: Model, icons_meta: list[dict], c: dict,
    cx: float, cy: float, w: float, h: float,
    stroke_scale: float
) -> str:
    shape = str(c.get("showcase_shape") or "card").lower()
    hl_bg = c["highlight_bg"]
    hl_stroke = c["highlight_stroke"]
    hl_mode = c.get("highlight_mode", "hero_1")
    num_hl = 1 if hl_mode == "hero_1" else (6 if hl_mode == "mini_6" else 4)
    cols = 1 if hl_mode == "hero_1" else 2

    if shape == "circle":
        r = int(min(w, h) * 0.44)
        hero_paths = _extract_highlight_svg(
            model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
            r * 1.35, r * 1.35,
            cx - r * 0.675, cy - r * 0.675, cols=cols
        )
        return f"""
    <!-- Redesigned Showcase: Luxury Orbital Ring -->
    <g id="showcaseOrbitalRing">
      <!-- Outer Dashed Ring -->
      <circle cx="{cx}" cy="{cy}" r="{r + 28}" fill="none" 
              stroke="rgba(255,255,255,0.22)" stroke-width="1.5" stroke-dasharray="6,6"/>
      <!-- Cardinal Crosshairs -->
      <line x1="{cx}" y1="{cy - r - 36}" x2="{cx}" y2="{cy - r - 20}" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <line x1="{cx}" y1="{cy + r + 20}" x2="{cx}" y2="{cy + r + 36}" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <line x1="{cx - r - 36}" y1="{cy}" x2="{cx - r - 20}" y2="{cy}" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <line x1="{cx + r + 20}" y1="{cy}" x2="{cx + r + 36}" y2="{cy}" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <!-- Mid Glow Ring -->
      <circle cx="{cx}" cy="{cy}" r="{r + 8}" fill="none" 
              stroke="rgba(255,255,255,0.35)" stroke-width="2"/>
      <!-- Dark Glass Base Circle -->
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="{hl_bg}" 
              stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
      {hero_paths}
      <!-- Bottom Capsule Tag -->
      <rect x="{cx - 100}" y="{cy + r + 14}" width="200" height="30" rx="15"
            fill="rgba(0,0,0,0.35)" stroke="rgba(255,255,255,0.22)" stroke-width="1.5"/>
      <text x="{cx}" y="{cy + r + 34}" font-size="12" font-weight="800" 
            letter-spacing="2" fill="#38bdf8" text-anchor="middle" class="mono">
        &#9733; FEATURED HERO ICON
      </text>
    </g>"""
    elif shape == "hexagon":
        hex_r = int(min(w, h) * 0.44)
        hero_paths = _extract_highlight_svg(
            model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
            hex_r * 1.35, hex_r * 1.35,
            cx - hex_r * 0.675, cy - hex_r * 0.675, cols=cols
        )
        return f"""
    <!-- Redesigned Showcase: Cyber Hexagon Shield -->
    <g id="showcaseCyberHexagon">
      <polygon points="{cx},{cy - hex_r - 18} {cx + hex_r + 16},{cy - (hex_r+18)//2} {cx + hex_r + 16},{cy + (hex_r+18)//2} {cx},{cy + hex_r + 18} {cx - hex_r - 16},{cy + (hex_r+18)//2} {cx - hex_r - 16},{cy - (hex_r+18)//2}"
               fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" stroke-dasharray="8,6"/>
      <polygon points="{cx},{cy - hex_r} {cx + hex_r},{cy - hex_r//2} {cx + hex_r},{cy + hex_r//2} {cx},{cy + hex_r} {cx - hex_r},{cy + hex_r//2} {cx - hex_r},{cy - hex_r//2}"
               fill="{hl_bg}" stroke="rgba(255,255,255,0.25)" stroke-width="2.5"/>
      {hero_paths}
      <rect x="{cx - 90}" y="{cy + hex_r + 14}" width="180" height="28" rx="14"
            fill="rgba(0,0,0,0.35)" stroke="rgba(255,255,255,0.22)" stroke-width="1.5"/>
      <text x="{cx}" y="{cy + hex_r + 32}" font-size="11" font-weight="800" 
            letter-spacing="2" fill="#38bdf8" text-anchor="middle" class="mono">
        &#9679; CYBER SHIELD HERO
      </text>
    </g>"""
    else:  # "card" (Modern Squircle Card - Default)
        card_w = int(w * 0.94)
        card_h = int(h * 0.94)
        card_x = int(cx - card_w / 2)
        card_y = int(cy - card_h / 2)
        rx = min(32, int(card_w * 0.08))

        hero_paths = _extract_highlight_svg(
            model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
            card_w * 0.78, card_h * 0.65,
            card_x + card_w * 0.11, card_y + card_h * 0.18, cols=cols
        )
        return f"""
    <!-- Redesigned Showcase: Modern Squircle Luxury Card -->
    <g id="showcaseSquircleCard">
      <!-- Outer Ambient Border Glow -->
      <rect x="{card_x - 6}" y="{card_y - 6}" width="{card_w + 12}" height="{card_h + 12}" rx="{rx + 4}"
            fill="rgba(0,0,0,0.2)" stroke="rgba(255,255,255,0.22)" stroke-width="2" stroke-dasharray="12,8"/>

      <!-- Main Dark Glass Card -->
      <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{rx}"
            fill="{hl_bg}" stroke="rgba(255,255,255,0.2)" stroke-width="2"/>

      <!-- Corner Crosshairs / Precision Ticks -->
      <path d="M {card_x + 18} {card_y + 32} L {card_x + 18} {card_y + 18} L {card_x + 32} {card_y + 18}" 
            fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <path d="M {card_x + card_w - 32} {card_y + 18} L {card_x + card_w - 18} {card_y + 18} L {card_x + card_w - 18} {card_y + 32}" 
            fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <path d="M {card_x + 18} {card_y + card_h - 32} L {card_x + 18} {card_y + card_h - 18} L {card_x + 32} {card_y + card_h - 18}" 
            fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
      <path d="M {card_x + card_w - 32} {card_y + card_h - 18} L {card_x + card_w - 18} {card_y + card_h - 18} L {card_x + card_w - 18} {card_y + card_h - 32}" 
            fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>

      <!-- Top Badge Pill -->
      <rect x="{cx - 105}" y="{card_y + 18}" width="210" height="30" rx="15"
            fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>
      <text x="{cx}" y="{card_y + 38}" font-size="12" font-weight="800" 
            letter-spacing="2" fill="#38bdf8" text-anchor="middle" class="mono">
        &#9733; FEATURED HERO ICON
      </text>

      {hero_paths}

      <!-- Bottom Specs Line -->
      <text x="{cx}" y="{card_y + card_h - 18}" font-size="13" font-weight="700" 
            letter-spacing="2" fill="#94a3b8" text-anchor="middle" class="mono">
        &#9679; 100% VECTOR &#8226; EDITABLE STROKE
      </text>
    </g>"""


def _extract_highlight_svg(model: Model, icons_meta: list[dict], hl_mode: str, count: int, hl_stroke: str, stroke_scale: float,
                           inner_w: float, inner_h: float, ox: float, oy: float, cols: int = 2) -> str:
    avail_icons = icons_meta or []
    if not avail_icons:
        return ""
    if hl_mode == "hero_1":
        ic = avail_icons[0]
        ic_paths = _extract_icon_paths(model, ic["box"])
        if not ic_paths:
            return ""
        bx1, by1, bx2, by2 = ic["box"]
        bw, bh = max(1, bx2 - bx1), max(1, by2 - by1)
        hero_size = min(inner_w * 0.68, inner_h * 0.68)
        h_scale = hero_size / max(bw, bh)
        h_ox = ox + (inner_w - bw * h_scale) / 2 - bx1 * h_scale
        h_oy = oy + (inner_h - bh * h_scale) / 2 - by1 * h_scale
        return _render_paths_svg(ic_paths, hl_stroke, stroke_scale, h_scale, h_ox, h_oy)

    rows = max(1, math.ceil(count / cols))
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    rendered = []
    for i in range(min(count, len(avail_icons))):
        ic = avail_icons[i]
        ic_paths = _extract_icon_paths(model, ic["box"])
        if not ic_paths:
            continue
        bx1, by1, bx2, by2 = ic["box"]
        bw, bh = max(1, bx2 - bx1), max(1, by2 - by1)
        col_i = i % cols
        row_i = i // cols
        target_cell = min(cell_w * 0.62, cell_h * 0.62)
        ic_scale = target_cell / max(bw, bh)
        cx = ox + col_i * cell_w + (cell_w - bw * ic_scale) / 2 - bx1 * ic_scale
        cy = oy + row_i * cell_h + (cell_h - bh * ic_scale) / 2 - by1 * ic_scale
        rendered.append(_render_paths_svg(ic_paths, hl_stroke, stroke_scale, ic_scale, cx, cy))
    return "\n        ".join(rendered)


# =========================================================================
# Layout 1 & 2: Vectuz Sidebar (Left & Right)
# =========================================================================
def _build_vectuz_sidebar(model: Model, icons_meta: list[dict], c: dict, W: int, H: int, banner_w: int, is_right: bool = False) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)
    sheet_w = W - banner_w
    sheet_h = H
    sheet_x = 0 if is_right else banner_w
    banner_x_offset = (W - banner_w) if is_right else 0

    avail_w = sheet_w * 0.88
    avail_h = sheet_h * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (sheet_h - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

    artboard_bg = c.get("artboard_bg", "checkered")
    defs_svg = ""
    if artboard_bg == "checkered":
        d_svg, sheet_bg_fill = _get_checkered_defs(W)
        defs_svg = d_svg
    else:
        sheet_bg_fill = artboard_bg

    show_highlight = c.get("show_highlight", True)
    banner_bg = c["banner_bg"]
    banner_text = c["banner_text"]
    banner_sub = c["banner_sub"]

    banner_pad = banner_x_offset + int(banner_w * 0.10)
    inner_w = banner_w - int(banner_w * 0.20)

    if show_highlight:
        top_h = int(round(H * 0.54))
        box_y = top_h + int(round(H * 0.025))
        box_h = H - box_y - int(round(H * 0.035))
    else:
        top_h = H - int(round(H * 0.06))
        box_y = 0
        box_h = 0

    fonts_import, title_font, count_font, sub_font = _get_font_css(c.get("font_family", "bebas"))
    title_hl_style = str(c.get("title_highlight", "pill"))

    title_fs = max(32, int(round(banner_w * 0.082)))
    count_fs = max(88, int(round(banner_w * 0.32)))
    sub_fs = max(16, int(round(banner_w * 0.046)))

    title_svg = _render_title_highlight(
        title=c['title'], subtitle=c['subtitle'],
        cx=banner_pad + inner_w / 2, cy=int(round(H * 0.035)) + int(top_h * 0.18),
        title_fs=title_fs, sub_fs=sub_fs,
        banner_text=banner_text, banner_sub=banner_sub,
        title_font=title_font, sub_font=sub_font,
        style=title_hl_style, is_centered=True,
        max_w=inner_w * 0.94
    )

    hl_svg = ""
    if show_highlight and box_h > 100:
        hl_svg = _render_showcase_box(
            model, icons_meta, c,
            cx=banner_pad + inner_w / 2, cy=box_y + box_h / 2,
            w=inner_w, h=box_h,
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

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{sheet_h}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="stockSideBanner">
    <rect x="{banner_pad}" y="{int(round(H * 0.035))}" width="{inner_w}" height="{top_h - int(round(H * 0.035))}" 
          rx="{max(18, int(round(banner_w * 0.045)))}" fill="{banner_bg}"/>

    {title_svg}

    <text x="{banner_pad + inner_w / 2}" y="{int(round(H * 0.035)) + int(top_h * 0.62)}" 
          font-size="{count_fs}" font-weight="900" fill="{banner_text}" letter-spacing="-3" 
          text-anchor="middle" class="count">
      {sanitize_text(count_val)}
    </text>

    {hl_svg}
  </g>
</svg>"""


# =========================================================================
# Layout 3: Wave Flow Ribbon (Image 1 Style)
# =========================================================================
def _build_wave_flow(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    bw = int(round(W * 0.27))
    sheet_x = int(bw * 0.85)
    sheet_w = W - sheet_x

    avail_w = sheet_w * 0.88
    avail_h = H * 0.86
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    # Wave curves (smooth S-curve double layer)
    wave_d1 = f"M0,0 L{bw*0.88:.1f},0 C{bw*1.15:.1f},{H*0.28:.1f} {bw*0.60:.1f},{H*0.68:.1f} {bw*0.94:.1f},{H:.1f} L0,{H:.1f} Z"
    wave_d2 = f"M0,0 L{bw*0.76:.1f},0 C{bw*1.04:.1f},{H*0.32:.1f} {bw*0.50:.1f},{H*0.62:.1f} {bw*0.82:.1f},{H:.1f} L0,{H:.1f} Z"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Wave Flow Ribbon Banner -->
  <g id="waveFlowBanner">
    <path d="{wave_d1}" fill="{banner_bg}"/>
    <path d="{wave_d2}" fill="#ffffff" fill-opacity="0.22"/>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.32)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.52)}" font-size="120" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.62)}" font-size="18" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>

    <!-- Mini Spec Pill -->
    <rect x="{int(bw * 0.15)}" y="{int(H * 0.76)}" width="{int(bw * 0.50)}" height="42" rx="21" fill="{c['highlight_bg']}"/>
    <text x="{int(bw * 0.40)}" y="{int(H * 0.76) + 26}" font-size="13" font-weight="800" letter-spacing="1.5" fill="#ffffff" text-anchor="middle" class="mono">
      EDITABLE LINE ICONS
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 4: Hexagon Cyber Shield (Image 2 Style)
# =========================================================================
def _build_hexagon_shield(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    panel_w = int(round(W * 0.30))
    sheet_x = panel_w
    sheet_w = W - panel_w

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    cx = panel_w // 2
    cy = int(H * 0.48)
    r_outer = int(panel_w * 0.40)
    r_inner = int(panel_w * 0.34)

    def hex_pts(radius):
        pts = []
        for i in range(6):
            ang = math.radians(60 * i - 30)
            pts.append(f"{cx + radius * math.cos(ang):.1f},{cy + radius * math.sin(ang):.1f}")
        return " ".join(pts)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Hexagon Shield Panel -->
  <g id="hexagonShieldPanel">
    <rect x="0" y="0" width="{panel_w}" height="{H}" fill="{banner_bg}"/>

    <text x="{cx}" y="{int(H * 0.16)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>
    <text x="{cx}" y="{int(H * 0.20)}" font-size="14" font-weight="700" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>

    <!-- 3D Layered Hexagon Badge -->
    <polygon points="{hex_pts(r_outer)}" fill="{hl_bg}" stroke="#ffffff" stroke-width="6"/>
    <polygon points="{hex_pts(r_inner)}" fill="{banner_bg}" opacity="0.35"/>

    <text x="{cx}" y="{cy + 36}" font-size="100" font-weight="900" letter-spacing="-2" fill="#ffffff" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{cx}" y="{cy + r_outer + 48}" font-size="15" font-weight="800" letter-spacing="2" fill="{banner_text}" text-anchor="middle" class="mono">
      CYBER SHIELD &#8226; VECTOR ICONS
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 5: Origami Fold (Image 2 Style)
# =========================================================================
def _build_origami_fold(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    bw = int(round(W * 0.28))
    sheet_x = int(bw * 0.85)
    sheet_w = W - sheet_x

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Origami Fold Banner -->
  <g id="origamiFoldBanner">
    <polygon points="0,0 {bw*0.95:.1f},0 {bw*0.62:.1f},{H:.1f} 0,{H:.1f}" fill="{banner_bg}"/>
    <polygon points="{bw*0.95:.1f},0 {bw*1.18:.1f},{H*0.42:.1f} {bw*0.62:.1f},{H:.1f}" fill="{banner_bg}" fill-opacity="0.55"/>
    <polygon points="{bw*1.18:.1f},{H*0.42:.1f} {bw*0.92:.1f},{H*0.82:.1f} {bw*0.62:.1f},{H:.1f}" fill="{c['highlight_bg']}" fill-opacity="0.75"/>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.30)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.50)}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.60)}" font-size="17" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 6: Diagonal Speed Slashes (Image 2 Style)
# =========================================================================
def _build_diagonal_slash(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    bw = int(round(W * 0.28))
    sheet_x = int(bw * 0.85)
    sheet_w = W - sheet_x

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Dynamic Diagonal Speed Slashes -->
  <g id="diagonalSlashBanner">
    <polygon points="0,0 {bw*0.75:.1f},0 {bw*0.25:.1f},{H:.1f} 0,{H:.1f}" fill="{banner_bg}"/>
    <polygon points="{bw*0.80:.1f},0 {bw*0.96:.1f},0 {bw*0.46:.1f},{H:.1f} {bw*0.30:.1f},{H:.1f}" fill="{banner_bg}" fill-opacity="0.65"/>
    <polygon points="{bw*1.01:.1f},0 {bw*1.12:.1f},0 {bw*0.62:.1f},{H:.1f} {bw*0.51:.1f},{H:.1f}" fill="{banner_bg}" fill-opacity="0.35"/>

    <text x="{int(bw * 0.36)}" y="{int(H * 0.32)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{int(bw * 0.36)}" y="{int(H * 0.52)}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{int(bw * 0.36)}" y="{int(H * 0.62)}" font-size="18" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 7: Concentric Orbital Rings (Image 2 Style)
# =========================================================================
def _build_bubble_orbital(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    panel_w = int(round(W * 0.28))
    sheet_x = panel_w
    sheet_w = W - panel_w

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    cx = int(panel_w * 0.50)
    cy = int(H * 0.48)
    r = int(panel_w * 0.36)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Orbital Rings Banner -->
  <g id="bubbleOrbitalBanner">
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="{banner_bg}"/>
    <circle cx="{cx}" cy="{cy}" r="{int(r * 1.25)}" fill="none" stroke="{banner_bg}" stroke-width="4" stroke-dasharray="14,10" opacity="0.6"/>
    <circle cx="{cx - 80}" cy="{cy - 160}" r="{int(r * 0.35)}" fill="{banner_bg}" opacity="0.45"/>
    <circle cx="{cx + 100}" cy="{cy + 170}" r="{int(r * 0.28)}" fill="{banner_bg}" opacity="0.5"/>

    <text x="{cx}" y="{int(H * 0.18)}" font-size="28" font-weight="900" letter-spacing="3" fill="{c['icon_stroke']}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{cx}" y="{cy + 38}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{cx}" y="{cy + r + 54}" font-size="18" font-weight="800" letter-spacing="1" fill="{c['icon_stroke']}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 8: Botanical Eco Leaf (Image 2 Style)
# =========================================================================
def _build_eco_leaf(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    bw = int(round(W * 0.28))
    sheet_x = int(bw * 0.85)
    sheet_w = W - sheet_x

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    leaf_d1 = f"M0,0 L{bw*0.85:.1f},0 C{bw*1.12:.1f},{H*0.22:.1f} {bw*1.18:.1f},{H*0.48:.1f} {bw*0.90:.1f},{H*0.75:.1f} C{bw*0.72:.1f},{H*0.92:.1f} {bw*0.35:.1f},{H:.1f} 0,{H:.1f} Z"
    leaf_d2 = f"M0,0 C{bw*0.80:.1f},{H*0.25:.1f} {bw*0.88:.1f},{H*0.55:.1f} 0,{H*0.82:.1f} Z"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Eco Leaf Petal Banner -->
  <g id="ecoLeafBanner">
    <path d="{leaf_d1}" fill="{banner_bg}"/>
    <path d="{leaf_d2}" fill="#ffffff" fill-opacity="0.35"/>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.32)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.52)}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{int(bw * 0.40)}" y="{int(H * 0.62)}" font-size="18" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 9: Liquid Teardrop (Image 2 Style)
# =========================================================================
def _build_droplet_flow(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    bw = int(round(W * 0.28))
    sheet_x = int(bw * 0.85)
    sheet_w = W - sheet_x

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    drop_d = f"M0,0 L{bw*0.82:.1f},0 C{bw*1.22:.1f},{H*0.32:.1f} {bw*1.22:.1f},{H*0.68:.1f} {bw*0.82:.1f},{H:.1f} L0,{H:.1f} Z"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Teardrop Splash Banner -->
  <g id="dropletBanner">
    <path d="{drop_d}" fill="{banner_bg}"/>
    <circle cx="{bw * 0.95}" cy="{H * 0.22}" r="{bw * 0.12}" fill="{banner_bg}" opacity="0.4"/>
    <circle cx="{bw * 0.98}" cy="{H * 0.78}" r="{bw * 0.16}" fill="{banner_bg}" opacity="0.45"/>

    <text x="{int(bw * 0.42)}" y="{int(H * 0.32)}" font-size="28" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{int(bw * 0.42)}" y="{int(H * 0.52)}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{int(bw * 0.42)}" y="{int(H * 0.62)}" font-size="18" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 10: Halftone Dot Matrix Burst (Image 2 Style)
# =========================================================================
def _build_halftone_burst(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    panel_w = int(round(W * 0.28))
    sheet_x = panel_w
    sheet_w = W - panel_w

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    cx = panel_w // 2
    cy = int(H * 0.48)

    dots = []
    for ring_r, dot_r, num_dots in [(160, 5, 16), (220, 8, 24), (280, 11, 32)]:
        for i in range(num_dots):
            ang = 2 * math.pi * i / num_dots
            dx = cx + ring_r * math.cos(ang)
            dy = cy + ring_r * math.sin(ang)
            dots.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="{dot_r}" fill="{banner_bg}" opacity="0.35"/>')

    dots_svg = "\n      ".join(dots)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Halftone Dot Matrix Banner -->
  <g id="halftoneBurstBanner">
    {dots_svg}

    <circle cx="{cx}" cy="{cy}" r="120" fill="{banner_bg}"/>

    <text x="{cx}" y="{int(H * 0.20)}" font-size="28" font-weight="900" letter-spacing="3" fill="{c['icon_stroke']}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{cx}" y="{cy + 36}" font-size="100" font-weight="900" letter-spacing="-2" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{cx}" y="{cy + 170}" font-size="17" font-weight="800" letter-spacing="1.5" fill="{c['icon_stroke']}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 11: Pixel Matrix (Image 2 Style)
# =========================================================================
def _build_pixel_matrix(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    panel_w = int(round(W * 0.28))
    sheet_x = panel_w
    sheet_w = W - panel_w

    avail_w = sheet_w * 0.88
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    solid_w = int(panel_w * 0.72)
    sq_size = 48
    pixels = []
    np.random.seed(42)
    for row in range(int(H // sq_size)):
        py = row * sq_size
        for col in range(5):
            px = solid_w + col * sq_size
            if np.random.rand() > (col * 0.22):
                alpha = round(1.0 - col * 0.20, 2)
                pixels.append(f'<rect x="{px}" y="{py}" width="{sq_size-4}" height="{sq_size-4}" rx="4" fill="{banner_bg}" fill-opacity="{alpha}"/>')

    pixels_svg = "\n      ".join(pixels)
    cx = solid_w // 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- Left Pixel Matrix Dissolve Banner -->
  <g id="pixelMatrixBanner">
    <rect x="0" y="0" width="{solid_w}" height="{H}" fill="{banner_bg}"/>
    {pixels_svg}

    <text x="{cx}" y="{int(H * 0.32)}" font-size="26" font-weight="900" letter-spacing="3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])}
    </text>

    <text x="{cx}" y="{int(H * 0.52)}" font-size="110" font-weight="900" letter-spacing="-3" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(count_val)}
    </text>

    <text x="{cx}" y="{int(H * 0.62)}" font-size="17" font-weight="800" letter-spacing="1" fill="{banner_sub}" text-anchor="middle">
      {sanitize_text(c['subtitle'])}
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 12: Top Header Magazine Bar (Shutterstock Style)
# =========================================================================
def _build_top_banner(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    top_h = int(round(H * 0.22))
    sheet_y = top_h
    sheet_h = H - top_h

    avail_w = W * 0.90
    avail_h = sheet_h * 0.86
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = (W - target_w) / 2
    off_y = sheet_y + (sheet_h - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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
    hl_stroke = c["highlight_stroke"]

    card_margin = int(W * 0.02)
    card_h = top_h - card_margin * 2
    badge_w = int(card_h * 1.5)
    badge_x = card_margin
    badge_y = card_margin

    title_x = badge_x + badge_w + int(W * 0.03)
    title_fs = max(32, int(round(top_h * 0.28)))
    sub_fs = max(16, int(round(top_h * 0.12)))

    show_highlight = c.get("show_highlight", True)
    right_box_svg = ""
    if show_highlight:
        rb_w = int(W * 0.24)
        rb_x = W - card_margin - rb_w
        rb_y = card_margin
        hl_mode = c.get("highlight_mode", "mini_4")
        num_hl = 1 if hl_mode == "hero_1" else 4
        hl_paths = _extract_highlight_svg(
            model, icons_meta, hl_mode, num_hl, hl_stroke, stroke_scale,
            rb_w * 0.86, card_h * 0.70, rb_x + rb_w * 0.07, rb_y + card_h * 0.10, cols=num_hl
        )
        right_box_svg = f"""
    <g id="topHighlightBox">
      <rect x="{rb_x}" y="{rb_y}" width="{rb_w}" height="{card_h}" rx="16" fill="{hl_bg}" stroke="#334155" stroke-width="1.5"/>
      {hl_paths}
      <text x="{rb_x + rb_w / 2}" y="{rb_y + card_h - 10}" font-size="11" font-weight="700" letter-spacing="1" fill="#94a3b8" text-anchor="middle" class="mono">
        INVERTED CONTRAST
      </text>
    </g>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="{sheet_y}" width="{W}" height="{sheet_h}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="stockTopHeader">
    <rect x="0" y="0" width="{W}" height="{top_h}" fill="{banner_bg}"/>
    <line x1="0" y1="{top_h}" x2="{W}" y2="{top_h}" stroke="#1e293b" stroke-width="3"/>

    <rect x="{badge_x}" y="{badge_y}" width="{badge_w}" height="{card_h}" rx="18" fill="{hl_bg}"/>
    <text x="{badge_x + badge_w / 2}" y="{badge_y + int(card_h * 0.58)}" font-size="{int(card_h * 0.44)}" font-weight="900" fill="#ffffff" text-anchor="middle" letter-spacing="-1">
      {sanitize_text(count_val)}
    </text>
    <text x="{badge_x + badge_w / 2}" y="{badge_y + int(card_h * 0.82)}" font-size="{int(card_h * 0.16)}" font-weight="800" fill="#00f5a0" text-anchor="middle" letter-spacing="2">
      ICONS
    </text>

    <text x="{title_x}" y="{badge_y + int(card_h * 0.46)}" font-size="{title_fs}" font-weight="900" letter-spacing="2" fill="{banner_text}">
      {sanitize_text(c['title'])}
    </text>
    <text x="{title_x}" y="{badge_y + int(card_h * 0.78)}" font-size="{sub_fs}" font-weight="700" letter-spacing="0.5" fill="{banner_sub}">
      {sanitize_text(c['subtitle'])} &#8226; 100% Scalable Vector Artboard
    </text>

    {right_box_svg}
  </g>
</svg>"""


# =========================================================================
# Layout 13: Bottom Dock Bar (Creative Market Style)
# =========================================================================
def _build_bottom_dock(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    dock_h = int(round(H * 0.18))
    sheet_h = H - dock_h

    avail_w = W * 0.90
    avail_h = sheet_h * 0.86
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = (W - target_w) / 2
    off_y = (sheet_h - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    dock_y = sheet_h
    dock_pad = int(W * 0.03)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{sheet_h}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="stockBottomDock">
    <rect x="0" y="{dock_y}" width="{W}" height="{dock_h}" fill="{banner_bg}"/>
    <line x1="0" y1="{dock_y}" x2="{W}" y2="{dock_y}" stroke="{hl_bg}" stroke-width="4"/>

    <text x="{dock_pad}" y="{dock_y + int(dock_h * 0.46)}" font-size="{max(28, int(dock_h * 0.28))}" font-weight="900" letter-spacing="2" fill="{banner_text}">
      {sanitize_text(c['title'])}
    </text>
    <text x="{dock_pad}" y="{dock_y + int(dock_h * 0.76)}" font-size="{max(15, int(dock_h * 0.13))}" font-weight="700" letter-spacing="0.5" fill="{banner_sub}">
      {sanitize_text(c['subtitle'])} &#8226; Clean Stroke Geometry
    </text>

    <rect x="{int(W * 0.52)}" y="{dock_y + int(dock_h * 0.16)}" width="{int(W * 0.18)}" height="{int(dock_h * 0.68)}" rx="20" fill="{hl_bg}"/>
    <text x="{int(W * 0.61)}" y="{dock_y + int(dock_h * 0.62)}" font-size="{int(dock_h * 0.44)}" font-weight="900" fill="#ffffff" text-anchor="middle">
      {sanitize_text(count_val)} <tspan font-size="{int(dock_h * 0.18)}" fill="#00f5a0" font-weight="800">ICONS</tspan>
    </text>

    <text x="{W - dock_pad}" y="{dock_y + int(dock_h * 0.45)}" font-size="14" font-weight="800" letter-spacing="1" fill="{banner_text}" text-anchor="end" class="mono">
      EDITABLE LINE ICONS
    </text>
    <text x="{W - dock_pad}" y="{dock_y + int(dock_h * 0.72)}" font-size="13" font-weight="700" letter-spacing="1" fill="{banner_sub}" text-anchor="end" class="mono">
      SVG &#8226; EPS 3.0 &#8226; 4K PNG
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 14: Dual Theme 50/50 Split (Light & Dark Contrast)
# =========================================================================
def _build_split_duo(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    half_w = W // 2
    avail_w = half_w * 0.86
    avail_h = H * 0.72
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale

    off_x1 = (half_w - target_w) / 2
    off_y = (H - target_h) / 2 + 30
    off_x2 = half_w + (half_w - target_w) / 2

    stroke_scale = float(c["stroke_scale"])
    left_paths = _render_paths_svg(model.paths, c["icon_stroke"], stroke_scale, scale, off_x1, off_y)
    right_paths = _render_paths_svg(model.paths, c["highlight_stroke"], stroke_scale, scale, off_x2, off_y)

    artboard_bg = c.get("artboard_bg", "checkered")
    defs_svg = ""
    if artboard_bg == "checkered":
        d_svg, left_bg_fill = _get_checkered_defs(W)
        defs_svg = d_svg
    else:
        left_bg_fill = artboard_bg

    banner_bg = c["banner_bg"]
    banner_text = c["banner_text"]

    pill_w = int(W * 0.58)
    pill_h = 120
    pill_x = (W - pill_w) // 2
    pill_y = 40

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{half_w}" height="{H}" fill="{left_bg_fill}"/>
  <g id="lightSideIcons">
    {left_paths}
  </g>
  <text x="{half_w / 2}" y="{H - 36}" font-size="14" font-weight="800" letter-spacing="2" fill="#64748b" text-anchor="middle" class="mono">
    LIGHT THEME
  </text>

  <rect x="{half_w}" y="0" width="{half_w}" height="{H}" fill="#0F172A"/>
  <g id="darkSideIcons">
    {right_paths}
  </g>
  <text x="{half_w + half_w / 2}" y="{H - 36}" font-size="14" font-weight="800" letter-spacing="2" fill="#94a3b8" text-anchor="middle" class="mono">
    DARK THEME
  </text>

  <line x1="{half_w}" y1="0" x2="{half_w}" y2="{H}" stroke="#334155" stroke-width="3" stroke-dasharray="14,10"/>

  <g id="splitCenterPill">
    <rect x="{pill_x}" y="{pill_y}" width="{pill_w}" height="{pill_h}" rx="60" fill="{banner_bg}" stroke="#0f172a" stroke-width="4"/>
    <text x="{W / 2}" y="{pill_y + 74}" font-size="34" font-weight="900" letter-spacing="2" fill="{banner_text}" text-anchor="middle">
      {sanitize_text(c['title'])} <tspan font-weight="900" fill="{banner_text}">&#8226;</tspan> {sanitize_text(count_val)} ICONS <tspan font-size="20" font-weight="700">&#8226; DUAL THEME</tspan>
    </text>
  </g>
</svg>"""


# =========================================================================
# Layout 15: Floating Modern Card (Dribbble / Minimal)
# =========================================================================
def _build_floating_card(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    avail_w = W * 0.90
    avail_h = H * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = (W - target_w) / 2
    off_y = (H - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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
    hl_stroke = c["highlight_stroke"]

    card_w = int(W * 0.24)
    card_h = int(H * 0.36)
    card_x = 64
    card_y = 64

    show_highlight = c.get("show_highlight", True)
    mini_box_svg = ""
    if show_highlight and card_h > 180:
        mb_h = int(card_h * 0.38)
        mb_y = card_y + card_h - mb_h - 20
        mb_w = card_w - 48
        mb_x = card_x + 24
        hl_paths = _extract_highlight_svg(
            model, icons_meta, "mini_4", 4, hl_stroke, stroke_scale,
            mb_w * 0.88, mb_h * 0.75, mb_x + mb_w * 0.06, mb_y + mb_h * 0.12, cols=4
        )
        mini_box_svg = f"""
      <rect x="{mb_x}" y="{mb_y}" width="{mb_w}" height="{mb_h}" rx="14" fill="{hl_bg}"/>
      {hl_paths}"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
    <filter id="cardShadow" x="-10%" y="-10%" width="125%" height="125%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="floatingGlassCard" filter="url(#cardShadow)">
    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="28" fill="{banner_bg}" stroke="#ffffff" stroke-width="2" stroke-opacity="0.4"/>

    <text x="{card_x + 28}" y="{card_y + 60}" font-size="24" font-weight="900" letter-spacing="2" fill="{banner_text}">
      {sanitize_text(c['title'])}
    </text>

    <text x="{card_x + 28}" y="{card_y + 148}" font-size="76" font-weight="900" letter-spacing="-2" fill="{banner_text}">
      {sanitize_text(count_val)}
    </text>

    <text x="{card_x + 28}" y="{card_y + 188}" font-size="15" font-weight="700" letter-spacing="0.5" fill="{banner_sub}">
      {sanitize_text(c['subtitle'])}
    </text>

    {mini_box_svg}
  </g>
</svg>"""


# =========================================================================
# Layout 16: Framed Passe-Partout (Luxury Editorial)
# =========================================================================
def _build_framed_editorial(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    pad = int(W * 0.04)
    avail_w = (W - pad * 2) * 0.86
    avail_h = (H - pad * 2) * 0.74
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = (W - target_w) / 2
    off_y = (H - target_h) / 2 + 10

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

    artboard_bg = c.get("artboard_bg", "checkered")
    defs_svg = ""
    if artboard_bg == "checkered":
        d_svg, sheet_bg_fill = _get_checkered_defs(W)
        defs_svg = d_svg
    else:
        sheet_bg_fill = artboard_bg

    banner_bg = c["banner_bg"]
    banner_text = c["banner_text"]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{sheet_bg_fill}"/>

  <rect x="{pad}" y="{pad}" width="{W - pad * 2}" height="{H - pad * 2}" rx="12" fill="none" stroke="{banner_bg}" stroke-width="4"/>
  <rect x="{pad + 18}" y="{pad + 18}" width="{W - pad * 2 - 36}" height="{H - pad * 2 - 36}" rx="8" fill="none" stroke="{banner_bg}" stroke-width="1.5" stroke-dasharray="16,8"/>

  <path d="M{pad-12},{pad} h24 M{pad},{pad-12} v24" stroke="{banner_bg}" stroke-width="2"/>
  <path d="M{W-pad-12},{pad} h24 M{W-pad},{pad-12} v24" stroke="{banner_bg}" stroke-width="2"/>
  <path d="M{pad-12},{H-pad} h24 M{pad},{H-pad-12} v24" stroke="{banner_bg}" stroke-width="2"/>
  <path d="M{W-pad-12},{H-pad} h24 M{W-pad},{H-pad-12} v24" stroke="{banner_bg}" stroke-width="2"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <text x="{W / 2}" y="{pad + 68}" font-size="14" font-weight="800" letter-spacing="4" fill="#64748b" text-anchor="middle" class="mono">
    &#8212; VECTOR ICON COLLECTION &#8212;
  </text>
  <text x="{W / 2}" y="{pad + 116}" font-size="38" font-weight="900" letter-spacing="4" fill="{c['icon_stroke']}" text-anchor="middle">
    {sanitize_text(c['title'])}
  </text>

  <rect x="{(W - 680) / 2}" y="{H - pad - 68}" width="680" height="52" rx="26" fill="{banner_bg}"/>
  <text x="{W / 2}" y="{H - pad - 35}" font-size="16" font-weight="900" letter-spacing="2" fill="{banner_text}" text-anchor="middle" class="mono">
    [ {sanitize_text(count_val)} EDITABLE LINE ICONS &#8226; 100% VECTOR ]
  </text>
</svg>"""


# =========================================================================
# Layout 17: Hero Spotlight (Large Highlight Icon Circle)
# =========================================================================
def _build_hero_spotlight(model: Model, icons_meta: list[dict], c: dict, W: int, H: int) -> str:
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "24"))
    mW, mH = max(10, model.width), max(10, model.height)

    panel_w = int(round(W * 0.32))
    sheet_x = panel_w
    sheet_w = W - panel_w
    sheet_h = H

    avail_w = sheet_w * 0.88
    avail_h = sheet_h * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (sheet_h - target_h) / 2

    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

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

    fonts_import, title_font, count_font, sub_font = _get_font_css(c.get("font_family", "bebas"))
    title_hl_style = str(c.get("title_highlight", "pill"))

    # Title with highlight element (matching template)
    title_svg = _render_title_highlight(
        title=c['title'], subtitle=c['subtitle'],
        cx=panel_w / 2, cy=int(H * 0.13),
        title_fs=max(36, int(panel_w * 0.082)),
        sub_fs=max(16, int(panel_w * 0.038)),
        banner_text=banner_text, banner_sub=banner_sub,
        title_font=title_font, sub_font=sub_font,
        style=title_hl_style, is_centered=True,
        max_w=panel_w * 0.88
    )

    # Redesigned Showcase Box (replacing the raw black circle)
    sc_cx = panel_w / 2
    sc_cy = int(H * 0.47)
    sc_w = int(panel_w * 0.84)
    sc_h = int(panel_w * 0.84)
    showcase_svg = _render_showcase_box(
        model, icons_meta, c,
        cx=sc_cx, cy=sc_cy, w=sc_w, h=sc_h,
        stroke_scale=stroke_scale
    )

    # Big punchy count number with bottom pill badge
    count_fs = max(96, int(panel_w * 0.28))

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

  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{sheet_h}" fill="{sheet_bg_fill}"/>

  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <g id="spotlightPanel">
    <rect x="0" y="0" width="{panel_w}" height="{H}" fill="{banner_bg}"/>

    {title_svg}

    {showcase_svg}

    <!-- Bottom Big Count Badge -->
    <g id="spotlightCountBadge">
      <text x="{panel_w / 2}" y="{int(H * 0.835)}" font-size="{count_fs}" font-weight="900" 
            letter-spacing="-3" fill="{banner_text}" text-anchor="middle" class="count">
        {sanitize_text(count_val)}
      </text>
      <rect x="{panel_w/2 - 130}" y="{int(H * 0.865)}" width="260" height="38" rx="19" 
            fill="rgba(0,0,0,0.22)" stroke="rgba(255,255,255,0.22)" stroke-width="1.5"/>
      <text x="{panel_w / 2}" y="{int(H * 0.865) + 25}" font-size="16" font-weight="800" 
            letter-spacing="3" fill="{banner_sub}" text-anchor="middle" class="mono">
        EDITABLE ICONS
      </text>
    </g>
  </g>
</svg>"""


# =========================================================================
# Master SVG Dispatcher (Supports all 17 designs)
# =========================================================================
def build_template_svg(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate high-resolution SVG presentation sheet supporting 17 distinct microstock designs."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    design = str(c.get("design") or "vectuz_sidebar").lower()

    mW, mH = max(10, model.width), max(10, model.height)
    layout = c.get("layout", "landscape_16_9")
    W, H, banner_w = _calc_dims(layout, mW, mH)

    # Family 1: Stock Bestsellers
    if design == "vectuz_right":
        return _build_vectuz_sidebar(model, icons_meta, c, W, H, banner_w, is_right=True)
    elif design == "top_banner":
        return _build_top_banner(model, icons_meta, c, W, H)
    elif design == "bottom_dock":
        return _build_bottom_dock(model, icons_meta, c, W, H)
    elif design == "split_duo":
        return _build_split_duo(model, icons_meta, c, W, H)
    elif design == "floating_card":
        return _build_floating_card(model, icons_meta, c, W, H)
    elif design == "framed_editorial":
        return _build_framed_editorial(model, icons_meta, c, W, H)
    elif design == "hero_spotlight":
        return _build_hero_spotlight(model, icons_meta, c, W, H)

    # Family 2: Waves & Organic Flow (Images 1 & 2)
    elif design == "wave_flow":
        return _build_wave_flow(model, icons_meta, c, W, H)
    elif design == "eco_leaf":
        return _build_eco_leaf(model, icons_meta, c, W, H)
    elif design == "droplet_flow":
        return _build_droplet_flow(model, icons_meta, c, W, H)

    # Family 3: Tech & Geometric Badges (Image 2)
    elif design == "hexagon_shield":
        return _build_hexagon_shield(model, icons_meta, c, W, H)
    elif design == "origami_fold":
        return _build_origami_fold(model, icons_meta, c, W, H)
    elif design == "diagonal_slash":
        return _build_diagonal_slash(model, icons_meta, c, W, H)
    elif design == "bubble_orbital":
        return _build_bubble_orbital(model, icons_meta, c, W, H)
    elif design == "halftone_burst":
        return _build_halftone_burst(model, icons_meta, c, W, H)
    elif design == "pixel_matrix":
        return _build_pixel_matrix(model, icons_meta, c, W, H)

    else:  # "vectuz_sidebar" (default Adobe Stock standard)
        return _build_vectuz_sidebar(model, icons_meta, c, W, H, banner_w, is_right=False)


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
