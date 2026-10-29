"""Presentation Template Engine: Combines icon set metadata + redrawn vector icon sheet into a professional presentation artboard.

Outputs:
  - High-resolution SVG presentation template
  - Encapsulated PostScript (EPS 3.0) presentation template
  - Standalone EPS for the icon sheet
"""
from __future__ import annotations
import math, re
from typing import Any
from .model import Model

PRESETS: dict[str, dict[str, Any]] = {
    "obsidian": {
        "id": "obsidian",
        "name": "Obsidian Dark",
        "bg": "#090d14",
        "panel_bg": "#121824",
        "panel_border": "#00f5a0",
        "panel_border_alpha": 0.25,
        "accent": "#00f5a0",
        "title_color": "#ffffff",
        "subtitle_color": "#94a3b8",
        "badge_bg": "#00f5a0",
        "badge_bg_alpha": 0.12,
        "badge_text": "#00f5a0",
        "icon_stroke": "#00f5a0",
        "card_bg": "#0d131d",
        "card_border": "#1e293b",
        "text_dim": "#64748b",
        "dot_grid": "rgba(255,255,255,0.06)",
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimalist Studio",
        "bg": "#f8fafc",
        "panel_bg": "#ffffff",
        "panel_border": "#0284c7",
        "panel_border_alpha": 0.2,
        "accent": "#0284c7",
        "title_color": "#0f172a",
        "subtitle_color": "#64748b",
        "badge_bg": "#0284c7",
        "badge_bg_alpha": 0.1,
        "badge_text": "#0284c7",
        "icon_stroke": "#0f172a",
        "card_bg": "#ffffff",
        "card_border": "#e2e8f0",
        "text_dim": "#94a3b8",
        "dot_grid": "rgba(0,0,0,0.04)",
    },
    "cyber": {
        "id": "cyber",
        "name": "Cyber Neon",
        "bg": "#0a0a16",
        "panel_bg": "#131326",
        "panel_border": "#f43f5e",
        "panel_border_alpha": 0.35,
        "accent": "#f43f5e",
        "title_color": "#ffffff",
        "subtitle_color": "#c4b5fd",
        "badge_bg": "#f43f5e",
        "badge_bg_alpha": 0.15,
        "badge_text": "#fb7185",
        "icon_stroke": "#38bdf8",
        "card_bg": "#0f1022",
        "card_border": "#27274a",
        "text_dim": "#71717a",
        "dot_grid": "rgba(168,85,247,0.08)",
    },
    "gold": {
        "id": "gold",
        "name": "Luxury Gold",
        "bg": "#121110",
        "panel_bg": "#1c1a17",
        "panel_border": "#d4af37",
        "panel_border_alpha": 0.3,
        "accent": "#d4af37",
        "title_color": "#fef3c7",
        "subtitle_color": "#a8a29e",
        "badge_bg": "#d4af37",
        "badge_bg_alpha": 0.15,
        "badge_text": "#facc15",
        "icon_stroke": "#d4af37",
        "card_bg": "#161412",
        "card_border": "#2d2822",
        "text_dim": "#78716c",
        "dot_grid": "rgba(212,175,55,0.06)",
    },
    "cream": {
        "id": "cream",
        "name": "Pastel Cream",
        "bg": "#faf7f2",
        "panel_bg": "#ffffff",
        "panel_border": "#e11d48",
        "panel_border_alpha": 0.2,
        "accent": "#e11d48",
        "title_color": "#292524",
        "subtitle_color": "#78716c",
        "badge_bg": "#e11d48",
        "badge_bg_alpha": 0.1,
        "badge_text": "#be123c",
        "icon_stroke": "#292524",
        "card_bg": "#ffffff",
        "card_border": "#e7e5e4",
        "text_dim": "#a8a29e",
        "dot_grid": "rgba(0,0,0,0.03)",
    },
    "blueprint": {
        "id": "blueprint",
        "name": "Blueprint Tech",
        "bg": "#0a192f",
        "panel_bg": "#112240",
        "panel_border": "#38bdf8",
        "panel_border_alpha": 0.3,
        "accent": "#38bdf8",
        "title_color": "#f8fafc",
        "subtitle_color": "#8892b0",
        "badge_bg": "#38bdf8",
        "badge_bg_alpha": 0.15,
        "badge_text": "#38bdf8",
        "icon_stroke": "#38bdf8",
        "card_bg": "#0d1b2a",
        "card_border": "#1e3a5f",
        "text_dim": "#64748b",
        "dot_grid": "rgba(56,189,248,0.1)",
    },
}


def hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    """Convert hex string (e.g. '#00f5a0' or '00f5a0') to 0.0-1.0 RGB tuple."""
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b)
    except Exception:
        return (0.0, 0.0, 0.0)


def sanitize_text(text: str) -> str:
    """Escape text for XML/SVG safety."""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def escape_ps_text(text: str) -> str:
    """Escape text for PostScript string literal (inside parentheses)."""
    t = str(text or "")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def resolve_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(cfg or {})
    preset_key = cfg.get("preset", "obsidian")
    base = dict(PRESETS.get(preset_key, PRESETS["obsidian"]))
    
    # Overwrite with any custom color or style overrides
    for k in (
        "bg", "panel_bg", "panel_border", "accent", "title_color",
        "subtitle_color", "badge_bg", "badge_text", "icon_stroke", "card_bg"
    ):
        if cfg.get(k):
            base[k] = cfg[k]

    base["title"] = cfg.get("title") or "Minimal Vector Line Icons"
    base["subtitle"] = cfg.get("subtitle") or "Clean Centerline Vector Icon Collection"
    base["icon_count"] = int(cfg.get("icon_count") or 12)
    base["grid_size"] = cfg.get("grid_size") or "64 × 64 px"
    base["author"] = cfg.get("author") or "Linework AI Precision Engine"
    base["stroke_scale"] = float(cfg.get("stroke_scale") or 1.0)
    base["layout"] = cfg.get("layout") or "landscape"  # "landscape" (1600x1000) or "square" (1200x1200)
    base["show_grid"] = cfg.get("show_grid", True)
    base["show_badges"] = cfg.get("show_badges", True)
    return base


def build_template_svg(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate high-resolution SVG presentation artboard with Left Metadata Card and Right Traced Icon Sheet."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count = len(icons_meta) if icons_meta else c["icon_count"]
    
    if c["layout"] == "square":
        W, H = 1200, 1200
        left_w = 380
        left_x = 40
        right_x = 445
        right_w = 715
    else:  # landscape 1600 x 1000 (standard Dribbble/Behance/Marketplace presentation)
        W, H = 1600, 1000
        left_w = 460
        left_x = 60
        right_x = 550
        right_w = 990

    top_y = 60
    content_h = H - 120

    # Calculate scale and translation for the Model on the right side
    mW, mH = max(1, model.width), max(1, model.height)
    avail_w = right_w - 80
    avail_h = content_h - 80
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = right_x + 40 + (avail_w - target_w) / 2
    off_y = top_y + 40 + (avail_h - target_h) / 2

    # Render model paths with custom stroke color and scale
    stroke_color = c["icon_stroke"]
    stroke_scale = c["stroke_scale"]
    
    path_elems = []
    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        d = p.d()
        path_elems.append(
            f'<path d="{d}" stroke="{stroke_color}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )
    paths_svg = "\n      ".join(path_elems)

    # Decorative dots grid pattern
    dots_svg = ""
    if c.get("show_grid"):
        dots_svg = f"""
    <defs>
      <pattern id="dotPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.5" fill="{c['dot_grid']}"/>
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#dotPattern)"/>
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&amp;family=JetBrains+Mono:wght@500;700&amp;display=swap');
    text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
    .mono {{ font-family: 'JetBrains Mono', monospace; }}
  </style>

  <!-- Background Canvas -->
  <rect width="{W}" height="{H}" fill="{c['bg']}"/>
  {dots_svg}

  <!-- ================= LEFT SECTION: PRESENTATION METADATA & SPECS ================= -->
  <g id="leftTemplateSection">
    <!-- Panel Backdrop Card -->
    <rect x="{left_x}" y="{top_y}" width="{left_w}" height="{content_h}" rx="24" 
          fill="{c['panel_bg']}" stroke="{c['panel_border']}" stroke-width="1.5" stroke-opacity="{c.get('panel_border_alpha', 0.25)}"/>

    <!-- Category Pill Badge -->
    <rect x="{left_x + 36}" y="{top_y + 36}" width="165" height="30" rx="8" 
          fill="{c['badge_bg']}" fill-opacity="{c.get('badge_bg_alpha', 0.15)}"/>
    <text x="{left_x + 48}" y="{top_y + 56}" font-size="11" font-weight="700" letter-spacing="1" fill="{c['badge_text']}" class="mono">
      VECTOR ICON SET
    </text>

    <!-- Main Title -->
    <text x="{left_x + 36}" y="{top_y + 112}" font-size="28" font-weight="800" fill="{c['title_color']}" letter-spacing="-0.5">
      {sanitize_text(c['title'])}
    </text>

    <!-- Subtitle / Description -->
    <text x="{left_x + 36}" y="{top_y + 144}" font-size="14" font-weight="500" fill="{c['subtitle_color']}">
      {sanitize_text(c['subtitle'])}
    </text>

    <!-- Highlight Spec: Live Editable Stroke Badge -->
    <g transform="translate({left_x + 36}, {top_y + 175})">
      <rect width="{left_w - 72}" height="56" rx="14" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <circle cx="28" cy="28" r="14" fill="{c['accent']}" fill-opacity="0.15"/>
      <path d="M22 28l4 4 8-8" stroke="{c['accent']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      <text x="52" y="24" font-size="13" font-weight="700" fill="{c['title_color']}">100% Vector &amp; Editable Stroke</text>
      <text x="52" y="42" font-size="11" font-weight="500" fill="{c['text_dim']}">Single centerline paths · Infinite scale</text>
    </g>

    <!-- 2x2 Specifications Mini Grid -->
    <g transform="translate({left_x + 36}, {top_y + 250})">
      <!-- Stat 1: Icon Count -->
      <rect x="0" y="0" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="16" y="28" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">COUNT</text>
      <text x="16" y="52" font-size="20" font-weight="800" fill="{c['title_color']}">{count} Icons</text>

      <!-- Stat 2: Grid Size -->
      <rect x="{(left_w - 86) / 2 + 14}" y="0" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="{(left_w - 86) / 2 + 30}" y="28" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">GRID</text>
      <text x="{(left_w - 86) / 2 + 30}" y="52" font-size="18" font-weight="800" fill="{c['title_color']}">{sanitize_text(c['grid_size'])}</text>

      <!-- Stat 3: Formats -->
      <rect x="0" y="80" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="16" y="108" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">FORMAT</text>
      <text x="16" y="132" font-size="16" font-weight="800" fill="{c['title_color']}">SVG · EPS</text>

      <!-- Stat 4: Precision -->
      <rect x="{(left_w - 86) / 2 + 14}" y="80" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="{(left_w - 86) / 2 + 30}" y="108" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">QUALITY</text>
      <text x="{(left_w - 86) / 2 + 30}" y="132" font-size="16" font-weight="800" fill="{c['accent']}">Clean Joints</text>
    </g>

    <!-- Features Checklist -->
    <g transform="translate({left_x + 36}, {top_y + 420})">
      <text x="0" y="15" font-size="12" font-weight="700" letter-spacing="1" fill="{c['text_dim']}" class="mono">KEY FEATURES</text>

      <!-- Item 1 -->
      <circle cx="8" cy="45" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 45l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="49" font-size="13" font-weight="600" fill="{c['title_color']}">Clean Centerline Strokes</text>

      <!-- Item 2 -->
      <circle cx="8" cy="77" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 77l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="81" font-size="13" font-weight="600" fill="{c['title_color']}">Perfect Circular Arcs &amp; Welded Corners</text>

      <!-- Item 3 -->
      <circle cx="8" cy="109" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 109l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="113" font-size="13" font-weight="600" fill="{c['title_color']}">Zero Stray Nodes or Overlapping Ink</text>

      <!-- Item 4 -->
      <circle cx="8" cy="141" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 141l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="145" font-size="13" font-weight="600" fill="{c['title_color']}">Fully Scalable to Any Dimension</text>
    </g>

    <!-- Author & License Footer Tag -->
    <g transform="translate({left_x + 36}, {top_y + content_h - 45})">
      <line x1="0" y1="-15" x2="{left_w - 72}" y2="-15" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="0" y="8" font-size="12" font-weight="600" fill="{c['text_dim']}">
        {sanitize_text(c['author'])}
      </text>
      <text x="{left_w - 72}" y="8" text-anchor="end" font-size="11" font-weight="700" fill="{c['accent']}" class="mono">
        PREMIUM ASSET
      </text>
    </g>
  </g>

  <!-- ================= RIGHT SECTION: TRACED VECTOR ICON SHEET ================= -->
  <g id="rightIconSheetSection">
    <!-- Icon Artboard Framing Container -->
    <rect x="{right_x}" y="{top_y}" width="{right_w}" height="{content_h}" rx="24" 
          fill="{c['card_bg']}" stroke="{c['panel_border']}" stroke-width="1.5" stroke-opacity="{c.get('panel_border_alpha', 0.25)}"/>

    <!-- Corner Alignment Marks -->
    <path d="M{right_x + 20} {top_y + 35} L{right_x + 20} {top_y + 20} L{right_x + 35} {top_y + 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + right_w - 20} {top_y + 35} L{right_x + right_w - 20} {top_y + 20} L{right_x + right_w - 35} {top_y + 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + 20} {top_y + content_h - 35} L{right_x + 20} {top_y + content_h - 20} L{right_x + 35} {top_y + content_h - 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + right_w - 20} {top_y + content_h - 35} L{right_x + right_w - 20} {top_y + content_h - 20} L{right_x + right_w - 35} {top_y + content_h - 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>

    <!-- Scaled & Centered Vector Centerline Icons -->
    <g transform="translate({off_x:.2f}, {off_y:.2f})">
      {paths_svg}
    </g>
  </g>

</svg>"""
    return svg


def build_template_eps(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate professional Adobe-standard Encapsulated PostScript (EPS 3.0) presentation template."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count = len(icons_meta) if icons_meta else c["icon_count"]

    if c["layout"] == "square":
        W, H = 1200, 1200
        left_w = 380
        left_x = 40
        right_x = 445
        right_w = 715
    else:
        W, H = 1600, 1000
        left_w = 460
        left_x = 60
        right_x = 550
        right_w = 990

    top_y = 60
    content_h = H - 120

    # Model positioning
    mW, mH = max(1, model.width), max(1, model.height)
    avail_w = right_w - 80
    avail_h = content_h - 80
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = right_x + 40 + (avail_w - target_w) / 2
    off_y = top_y + 40 + (avail_h - target_h) / 2

    # Color values
    bg_r, bg_g, bg_b = hex_to_rgb(c["bg"])
    pbg_r, pbg_g, pbg_b = hex_to_rgb(c["panel_bg"])
    acc_r, acc_g, acc_b = hex_to_rgb(c["accent"])
    tit_r, tit_g, tit_b = hex_to_rgb(c["title_color"])
    sub_r, sub_g, sub_b = hex_to_rgb(c["subtitle_color"])
    cbg_r, cbg_g, cbg_b = hex_to_rgb(c["card_bg"])
    stk_r, stk_g, stk_b = hex_to_rgb(c["icon_stroke"])
    dim_r, dim_g, dim_b = hex_to_rgb(c["text_dim"])
    stroke_scale = c["stroke_scale"]

    # Build PostScript code
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Presentation Engine",
        f"%%Title: {escape_ps_text(c['title'])}",
        f"%%BoundingBox: 0 0 {W} {H}",
        f"%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%Pages: 1",
        "%%EndComments",
        "",
        "% Helper macros",
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
        "% Rounded rectangle: x y w h r roundrect",
        "/roundrect {",
        "  /r exch def /h exch def /w exch def /y exch def /x exch def",
        "  newpath",
        "  x r add y M",
        "  x w add y x w add y h add r arcto 4 {pop} repeat",
        "  x w add y h add x y h add r arcto 4 {pop} repeat",
        "  x y h add x y r arcto 4 {pop} repeat",
        "  x y x w add y r arcto 4 {pop} repeat",
        "  CP",
        "} bind def",
        "",
        "% Transform origin to top-left (SVG coordinate alignment)",
        f"0 {H} translate",
        "1 -1 scale",
        "",
        "% Background",
        f"{bg_r:.3f} {bg_g:.3f} {bg_b:.3f} RGB",
        f"0 0 {W} {H} rectfill",
        "",
        "% Left Panel Backdrop",
        f"{left_x} {top_y} {left_w} {content_h} 24 roundrect",
        f"{pbg_r:.3f} {pbg_g:.3f} {pbg_b:.3f} RGB F",
        f"{left_x} {top_y} {left_w} {content_h} 24 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1.5 LW 1 LC 1 LJ S",
        "",
        "% Right Framing Container",
        f"{right_x} {top_y} {right_w} {content_h} 24 roundrect",
        f"{cbg_r:.3f} {cbg_g:.3f} {cbg_b:.3f} RGB F",
        f"{right_x} {top_y} {right_w} {content_h} 24 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1.5 LW 1 LC 1 LJ S",
        "",
        "% Left Panel Text & Typography",
        "% Note: font rendering with scale 1 -1 needs inverted font matrix to read correctly",
        "/drawText {",
        "  gsave",
        "  1 -1 scale",
        "  moveto show",
        "  grestore",
        "} bind def",
        "",
        "% Category badge",
        f"{left_x + 36} {top_y + 36} 165 30 8 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1 LW S",
        f"/Helvetica-Bold findfont 11 scalefont setfont",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB",
        f"({escape_ps_text('VECTOR ICON SET')}) {left_x + 48} {- (top_y + 56)} drawText",
        "",
        "% Title",
        f"/Helvetica-Bold findfont 26 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text(c['title'])}) {left_x + 36} {- (top_y + 112)} drawText",
        "",
        "% Subtitle",
        f"/Helvetica findfont 13 scalefont setfont",
        f"{sub_r:.3f} {sub_g:.3f} {sub_b:.3f} RGB",
        f"({escape_ps_text(c['subtitle'])}) {left_x + 36} {- (top_y + 144)} drawText",
        "",
        "% Editable badge container",
        f"{left_x + 36} {top_y + 175} {left_w - 72} 56 12 roundrect",
        f"{cbg_r:.3f} {cbg_g:.3f} {cbg_b:.3f} RGB F",
        f"{left_x + 36} {top_y + 175} {left_w - 72} 56 12 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1 LW S",
        f"/Helvetica-Bold findfont 13 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text('100% Vector & Editable Stroke')}) {left_x + 56} {- (top_y + 200)} drawText",
        f"/Helvetica findfont 11 scalefont setfont",
        f"{dim_r:.3f} {dim_g:.3f} {dim_b:.3f} RGB",
        f"({escape_ps_text('Clean single centerlines')}) {left_x + 56} {- (top_y + 218)} drawText",
        "",
        "% Specifications block",
        f"/Helvetica-Bold findfont 16 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text(str(count) + ' Icons  |  Grid: ' + str(c.get('grid_size', '64x64')) + '  |  SVG + EPS')}) {left_x + 36} {- (top_y + 280)} drawText",
        "",
        "% Features List",
        f"/Helvetica-Bold findfont 12 scalefont setfont",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB",
        f"({escape_ps_text('[v] Clean Single Centerlines')}) {left_x + 36} {- (top_y + 340)} drawText",
        f"({escape_ps_text('[v] Perfect Circular Arcs & Welded Corners')}) {left_x + 36} {- (top_y + 372)} drawText",
        f"({escape_ps_text('[v] Zero Stray Nodes or Overlaps')}) {left_x + 36} {- (top_y + 404)} drawText",
        f"({escape_ps_text('[v] Fully Scalable to Any Dimension')}) {left_x + 36} {- (top_y + 436)} drawText",
        "",
        "% Footer",
        f"/Helvetica findfont 12 scalefont setfont",
        f"{dim_r:.3f} {dim_g:.3f} {dim_b:.3f} RGB",
        f"({escape_ps_text(c['author'])}) {left_x + 36} {- (top_y + content_h - 45)} drawText",
        "",
        "% ================= RIGHT SECTION: VECTOR ICON PATHS =================",
        "gsave",
        f"{off_x:.3f} {off_y:.3f} translate",
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
        "1 LC 1 LJ",
    ]

    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        for i, seg in enumerate(p.segs()):
            p0, p1, p2, p3 = seg
            if i == 0:
                lines.append(f"{p0[0]:.2f} {p0[1]:.2f} M")
            lines.append(f"{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.extend([
        "grestore",
        "",
        "%%EOF"
    ])
    return "\n".join(lines)


def build_model_eps(model: Model, stroke_color: str = "#000000", stroke_scale: float = 1.0, bg: str | None = None) -> str:
    """Generate standalone EPS for just the clean icon sheet without template framing."""
    W, H = max(1, model.width), max(1, model.height)
    stk_r, stk_g, stk_b = hex_to_rgb(stroke_color)

    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Clean Vector Engine",
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
        bgr, bgg, bgb = hex_to_rgb(bg)
        lines.extend([
            f"{bgr:.3f} {bgg:.3f} {bgb:.3f} RGB",
            f"0 0 {W} {H} rectfill",
        ])

    lines.extend([
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
        "1 LC 1 LJ",
    ])

    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        for i, seg in enumerate(p.segs()):
            p0, p1, p2, p3 = seg
            if i == 0:
                lines.append(f"{p0[0]:.2f} {p0[1]:.2f} M")
            lines.append(f"{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.append("%%EOF")
    return "\n".join(lines)
