"""Presentation Template Engine for Linework AI
Generates Adobe Stock / Shutterstock / Microstock style presentation sheets.
Supports vertical cover banners (Vectuz microstock standard), giant count numerals,
dark showcase cards with inverted highlight icons, transparent checkered artboards,
automatic docking with ANY icon sheet size, and export to SVG, EPS 3.0, and PNG.
"""
from __future__ import annotations
import math, re
from typing import Any
import numpy as np
from .model import Model, Path

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
        "name": "Minimalist Pure White",
        "banner_bg": "#F1F5F9",
        "banner_text": "#0F172A",
        "banner_sub": "#64748B",
        "highlight_bg": "#0F172A",
        "highlight_stroke": "#38BDF8",
        "artboard_bg": "#FFFFFF",
        "icon_stroke": "#0F172A",
        "accent": "#0284C7",
    },
    "midnight_dark": {
        "id": "midnight_dark",
        "name": "Obsidian Cyber Dark",
        "banner_bg": "#1E293B",
        "banner_text": "#38BDF8",
        "banner_sub": "#94A3B8",
        "highlight_bg": "#090D14",
        "highlight_stroke": "#00F5A0",
        "artboard_bg": "#0A0F1D",
        "icon_stroke": "#38BDF8",
        "accent": "#00F5A0",
    },
}

# Backward compatibility map
PRESETS["obsidian"] = PRESETS["midnight_dark"]
PRESETS["minimal"] = PRESETS["minimal_white"]
PRESETS["cyber"] = PRESETS["vectuz_coral"]
PRESETS["gold"] = PRESETS["vectuz_yellow"]
PRESETS["cream"] = PRESETS["vectuz_orange"]
PRESETS["blueprint"] = PRESETS["vectuz_blue"]


def hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    """Convert hex string (e.g. '#00f5a0') to 0.0-1.0 RGB tuple."""
    h = str(hex_code or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    try:
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
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
    """Escape text for PostScript string literal."""
    t = str(text or "")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def resolve_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(cfg or {})
    preset_key = cfg.get("preset", "vectuz_yellow")
    base = dict(PRESETS.get(preset_key, PRESETS["vectuz_yellow"]))

    # Color & style overrides
    for k in (
        "banner_bg", "banner_text", "banner_sub", "highlight_bg",
        "highlight_stroke", "artboard_bg", "icon_stroke", "accent"
    ):
        if cfg.get(k):
            base[k] = cfg[k]

    # Map legacy keys if passed
    if cfg.get("bg"):
        base["artboard_bg"] = cfg["bg"]
    if cfg.get("panel_bg"):
        base["banner_bg"] = cfg["panel_bg"]

    base["title"] = str(cfg.get("title") or "TECHNOLOGY").upper()
    base["count"] = str(cfg.get("count") or cfg.get("icon_count") or "24")
    base["subtitle"] = str(cfg.get("subtitle") or "Editable Line Icons")
    base["stroke_scale"] = float(cfg.get("stroke_scale") or cfg.get("scale") or 1.0)
    base["layout"] = cfg.get("layout") or "landscape_16_9"
    base["show_highlight"] = cfg.get("show_highlight", True)
    if isinstance(base["show_highlight"], str):
        base["show_highlight"] = base["show_highlight"].lower() not in ("0", "false", "no")
    base["highlight_mode"] = cfg.get("highlight_mode") or "mini_4"  # mini_4, mini_6, hero_1
    return base


def _extract_icon_paths(model: Model, box: list[int] | tuple[int, ...]) -> list[Path]:
    """Find paths in model whose anchor centers lie within box [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = box
    pad = 8
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
    """Render a list of paths translated by ox, oy and scaled by scale."""
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


def build_template_svg(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate high-resolution SVG presentation sheet with Adobe Stock side cover banner + right icon artboard."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "15"))

    mW, mH = max(10, model.width), max(10, model.height)
    layout = c.get("layout", "landscape_16_9")

    # Dimensions calculation based on layout mode
    if layout == "auto_dock":
        H = mH
        banner_w = max(380, int(round(H * 0.35)))
        W = banner_w + mW
    elif layout == "square":
        W, H = 2400, 2400
        banner_w = 640
    elif layout == "landscape_4_3":
        W, H = 2400, 1800
        banner_w = 620
    elif layout == "landscape_16_10":
        W, H = 1920, 1200
        banner_w = 480
    else:  # landscape_16_9 (Default 4K Ultra-HD presentation: 3840 x 2160)
        W, H = 3840, 2160
        banner_w = 960

    # Margins and positioning
    sheet_x = banner_w
    sheet_w = W - banner_w
    sheet_h = H

    # Calculate model placement on the right artboard
    avail_w = sheet_w * 0.88
    avail_h = sheet_h * 0.88
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = sheet_x + (sheet_w - target_w) / 2
    off_y = (sheet_h - target_h) / 2

    # Render right icon sheet paths
    stroke_color = c["icon_stroke"]
    stroke_scale = float(c["stroke_scale"])
    paths_svg_group = _render_paths_svg(model.paths, stroke_color, stroke_scale, scale, off_x, off_y)

    # Right Artboard Background (Checkered transparent grid vs solid)
    artboard_bg = c.get("artboard_bg", "checkered")
    defs_svg = ""
    if artboard_bg == "checkered":
        chk_size = max(16, int(round(W / 120)))
        chk_half = chk_size / 2
        defs_svg = f"""
    <pattern id="stockCheckeredPattern" width="{chk_size}" height="{chk_size}" patternUnits="userSpaceOnUse">
      <rect width="{chk_size}" height="{chk_size}" fill="#ffffff"/>
      <rect x="0" y="0" width="{chk_half}" height="{chk_half}" fill="#f1f3f6"/>
      <rect x="{chk_half}" y="{chk_half}" width="{chk_half}" height="{chk_half}" fill="#f1f3f6"/>
    </pattern>"""
        sheet_bg_fill = 'url(#stockCheckeredPattern)'
    else:
        sheet_bg_fill = artboard_bg

    # Banner Layout calculations
    show_highlight = c.get("show_highlight", True)
    banner_bg = c["banner_bg"]
    banner_text = c["banner_text"]
    banner_sub = c["banner_sub"]
    hl_bg = c["highlight_bg"]
    hl_stroke = c["highlight_stroke"]

    banner_pad = int(banner_w * 0.10)
    inner_w = banner_w - (banner_pad * 2)

    # Height split: Top colored banner vs Bottom dark showcase box
    if show_highlight:
        top_h = int(round(H * 0.54))
        box_y = top_h + int(round(H * 0.025))
        box_h = H - box_y - int(round(H * 0.035))
    else:
        top_h = H - int(round(H * 0.06))
        box_y = 0
        box_h = 0

    # Typography scaling based on banner width
    title_fs = max(24, int(round(banner_w * 0.068)))
    count_fs = max(72, int(round(banner_w * 0.28)))
    sub_fs = max(14, int(round(banner_w * 0.042)))

    # Subtitle multi-line parsing
    raw_sub = str(c.get("subtitle") or "Editable Line Icons")
    sub_words = raw_sub.replace("\\n", "\n").split()
    if len(sub_words) >= 3 and "\n" not in raw_sub:
        sub_lines = [" ".join(sub_words[:2]), " ".join(sub_words[2:])]
    else:
        sub_lines = raw_sub.split("\n") if "\n" in raw_sub else [raw_sub]

    sub_tspan_svg = ""
    for idx, s_line in enumerate(sub_lines):
        dy_attr = f' dy="{int(sub_fs * 1.3)}"' if idx > 0 else ""
        sub_tspan_svg += f'<tspan x="{banner_pad}"{dy_attr}>{sanitize_text(s_line)}</tspan>'

    # Highlight Showcase Box content
    hl_svg = ""
    if show_highlight and box_h > 100:
        box_rx = max(16, int(round(banner_w * 0.04)))
        hl_mode = c.get("highlight_mode", "mini_4")

        # Extract icons for highlight box
        hl_paths_svg = ""
        avail_icons = icons_meta if icons_meta else []
        
        if hl_mode == "hero_1" and avail_icons:
            # 1 Giant Hero Icon
            ic = avail_icons[0]
            ic_paths = _extract_icon_paths(model, ic["box"])
            if ic_paths:
                bx1, by1, bx2, by2 = ic["box"]
                bw, bh = max(1, bx2 - bx1), max(1, by2 - by1)
                hero_size = min(inner_w * 0.65, box_h * 0.60)
                h_scale = hero_size / max(bw, bh)
                h_ox = banner_pad + (inner_w - bw * h_scale) / 2 - bx1 * h_scale
                h_oy = box_y + (box_h - bh * h_scale) / 2 - by1 * h_scale
                hl_paths_svg = _render_paths_svg(ic_paths, hl_stroke, stroke_scale, h_scale, h_ox, h_oy)

        else:
            # 4 Icons (2x2 grid) or 6 Icons (2x3 grid)
            cols = 2
            rows = 3 if hl_mode == "mini_6" and len(avail_icons) >= 6 else 2
            num_showcase = cols * rows
            cell_w = inner_w / cols
            cell_h = (box_h - int(banner_w * 0.12)) / rows

            rendered_cells = []
            for i in range(min(num_showcase, len(avail_icons))):
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
                cx = banner_pad + col_i * cell_w + (cell_w - bw * ic_scale) / 2 - bx1 * ic_scale
                cy = box_y + int(banner_w * 0.06) + row_i * cell_h + (cell_h - bh * ic_scale) / 2 - by1 * ic_scale
                rendered_cells.append(_render_paths_svg(ic_paths, hl_stroke, stroke_scale, ic_scale, cx, cy))

            hl_paths_svg = "\n        ".join(rendered_cells)

        hl_tag_fs = max(11, int(round(banner_w * 0.030)))
        hl_svg = f"""
    <!-- Bottom Dark Showcase Box (Inverted White Icons Preview) -->
    <g id="highlightShowcaseBox">
      <rect x="{banner_pad}" y="{box_y}" width="{inner_w}" height="{box_h}" rx="{box_rx}"
            fill="{hl_bg}" stroke="#333a4d" stroke-width="1.5" stroke-opacity="0.3"/>
      {hl_paths_svg}
      <text x="{banner_pad + inner_w / 2}" y="{box_y + box_h - int(banner_w * 0.045)}" 
            font-size="{hl_tag_fs}" font-weight="700" letter-spacing="1.5" fill="#94a3b8" 
            text-anchor="middle" class="mono">
        DARK THEME PREVIEW
      </text>
    </g>"""

    # Assemble complete SVG
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800;900&amp;family=JetBrains+Mono:wght@600;700&amp;display=swap');
      text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>{defs_svg}
  </defs>

  <!-- Right Artboard Background -->
  <rect x="{sheet_x}" y="0" width="{sheet_w}" height="{sheet_h}" fill="{sheet_bg_fill}"/>

  <!-- Right Traced Vector Icons Sheet -->
  <g id="stockIconSheet">
    {paths_svg_group}
  </g>

  <!-- ================= LEFT SIDE COVER BANNER (ADOBE STOCK STANDARD) ================= -->
  <g id="stockSideBanner">
    <!-- Top Colored Banner Card -->
    <rect x="{banner_pad}" y="{int(round(H * 0.035))}" width="{inner_w}" height="{top_h - int(round(H * 0.035))}" 
          rx="{max(16, int(round(banner_w * 0.04)))}" fill="{banner_bg}"/>

    <!-- Category / Title -->
    <text x="{banner_pad + int(inner_w * 0.08)}" y="{int(round(H * 0.035)) + int(top_h * 0.16)}" 
          font-size="{title_fs}" font-weight="900" letter-spacing="2" fill="{banner_text}">
      {sanitize_text(c['title'])}
    </text>

    <!-- Giant Count Number -->
    <text x="{banner_pad + int(inner_w * 0.08)}" y="{int(round(H * 0.035)) + int(top_h * 0.52)}" 
          font-size="{count_fs}" font-weight="900" fill="{banner_text}" letter-spacing="-2">
      {sanitize_text(count_val)}
    </text>

    <!-- Subtitle / Editable Line Icons Badge -->
    <text x="{banner_pad + int(inner_w * 0.08)}" y="{int(round(H * 0.035)) + int(top_h * 0.68)}" 
          font-size="{sub_fs}" font-weight="700" fill="{banner_sub}" letter-spacing="0.5">
      {sub_tspan_svg}
    </text>

    {hl_svg}
  </g>
</svg>"""
    return svg


def build_template_eps(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate professional Adobe-standard Encapsulated PostScript (EPS 3.0) presentation template."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count_val = str(c.get("count") or (len(icons_meta) if icons_meta else "15"))

    mW, mH = max(10, model.width), max(10, model.height)
    layout = c.get("layout", "landscape_16_9")

    if layout == "auto_dock":
        H = mH
        banner_w = max(380, int(round(H * 0.35)))
        W = banner_w + mW
    elif layout == "square":
        W, H = 2400, 2400
        banner_w = 640
    elif layout == "landscape_4_3":
        W, H = 2400, 1800
        banner_w = 620
    elif layout == "landscape_16_10":
        W, H = 1920, 1200
        banner_w = 480
    else:  # landscape_16_9
        W, H = 3840, 2160
        banner_w = 960

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

    # RGB values
    bbg_r, bbg_g, bbg_b = hex_to_rgb(c["banner_bg"])
    btxt_r, btxt_g, btxt_b = hex_to_rgb(c["banner_text"])
    hlbg_r, hlbg_g, hlbg_b = hex_to_rgb(c["highlight_bg"])
    hlstk_r, hlstk_g, hlstk_b = hex_to_rgb(c["highlight_stroke"])
    stk_r, stk_g, stk_b = hex_to_rgb(c["icon_stroke"])
    stroke_scale = float(c["stroke_scale"])

    banner_pad = int(banner_w * 0.10)
    inner_w = banner_w - (banner_pad * 2)
    show_highlight = c.get("show_highlight", True)

    if show_highlight:
        top_h = int(round(H * 0.54))
        box_y = top_h + int(round(H * 0.025))
        box_h = H - box_y - int(round(H * 0.035))
    else:
        top_h = H - int(round(H * 0.06))
        box_y = 0
        box_h = 0

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
        f"0 {H} translate",
        "1 -1 scale",
        "",
        "% Right Artboard Background (Clean Stock White)",
        "1.0 1.0 1.0 RGB",
        f"{sheet_x} 0 {sheet_w} {sheet_h} rectfill",
        "",
        "% Top Colored Banner",
        f"{bbg_r:.3f} {bbg_g:.3f} {bbg_b:.3f} RGB",
        f"{banner_pad} {int(round(H * 0.035))} {inner_w} {top_h - int(round(H * 0.035))} 24 roundrect F",
    ]

    if show_highlight and box_h > 100:
        lines += [
            "",
            "% Bottom Dark Showcase Card",
            f"{hlbg_r:.3f} {hlbg_g:.3f} {hlbg_b:.3f} RGB",
            f"{banner_pad} {box_y} {inner_w} {box_h} 24 roundrect F",
        ]

    # Render vector paths in EPS
    lines += [
        "",
        "% Vector Icons on Sheet",
        "1 LC 1 LJ",
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
        "gsave",
        f"{off_x:.2f} {off_y:.2f} translate",
        f"{scale:.4f} {scale:.4f} scale",
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
            lines.append(
                f"{c_seg[1][0]:.2f} {c_seg[1][1]:.2f} "
                f"{c_seg[2][0]:.2f} {c_seg[2][1]:.2f} "
                f"{c_seg[3][0]:.2f} {c_seg[3][1]:.2f} C"
            )
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.append("grestore")
    lines.append("%%EOF")
    return "\n".join(lines)


def build_model_eps(model: Model, stroke_color: str = "#000000", stroke_scale: float = 1.0, bg: str | None = None) -> str:
    """Export a standalone Model directly to Adobe PostScript EPS 3.0 format."""
    W = max(1, model.width)
    H = max(1, model.height)
    stk_r, stk_g, stk_b = hex_to_rgb(stroke_color)
    lines = [
        "%%!PS-Adobe-3.0 EPSF-3.0",
        "%%%%Creator: Linework AI Vector Precision Engine",
        f"%%%%BoundingBox: 0 0 {W} {H}",
        f"%%%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%%%Pages: 1",
        "%%%%EndComments",
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
