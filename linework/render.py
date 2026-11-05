"""Output engine: SVG -> grayscale raster. Uses resvg (fast, exact AA); falls back to cairosvg / Chromium / OpenCV."""
from __future__ import annotations
import io, os, tempfile, re
import numpy as np, cv2

_BACKEND = None


def _pick():
    global _BACKEND
    if _BACKEND:
        return _BACKEND
    try:
        import resvg_py  # noqa
        _BACKEND = "resvg"
    except Exception:
        try:
            import cairosvg  # noqa
            _BACKEND = "cairosvg"
        except Exception:
            try:
                from playwright.sync_api import sync_playwright  # noqa
                _BACKEND = "playwright"
            except Exception:
                _BACKEND = "opencv"
    return _BACKEND


def backend_name():
    return _pick()


def _opencv_svg_to_gray(svg_str: str, width: int, height: int) -> np.ndarray:
    """Zero-dependency pure OpenCV rasterizer for SVG paths (ideal for WebAssembly / Pyodide)."""
    img = np.full((height, width), 255, dtype=np.uint8)
    for m in re.finditer(r'<path\s+[^>]*?d=["\']([^"\']+)["\'][^>]*?stroke-width=["\']([^"\']+)["\']', svg_str):
        d_str, sw_str = m.group(1), m.group(2)
        w = max(1, int(round(float(sw_str))))
        tokens = re.split(r'([MCZ])', d_str)
        curr = (0.0, 0.0)
        cmd = None
        polyline = []
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            if t in ('M', 'C', 'Z'):
                cmd = t
            elif cmd == 'M':
                coords = [float(x) for x in re.split(r'[\s,]+', t) if x]
                if len(coords) >= 2:
                    curr = (coords[0], coords[1])
                    polyline.append([curr[0], curr[1]])
            elif cmd == 'C':
                coords = [float(x) for x in re.split(r'[\s,]+', t) if x]
                for i in range(0, len(coords) - 5, 6):
                    p0 = curr
                    p1 = (coords[i], coords[i+1])
                    p2 = (coords[i+2], coords[i+3])
                    p3 = (coords[i+4], coords[i+5])
                    curr = p3
                    for step in range(1, 11):
                        s = step / 10.0
                        bx = (1-s)**3 * p0[0] + 3*(1-s)**2 * s * p1[0] + 3*(1-s) * s**2 * p2[0] + s**3 * p3[0]
                        by = (1-s)**3 * p0[1] + 3*(1-s)**2 * s * p1[1] + 3*(1-s) * s**2 * p2[1] + s**3 * p3[1]
                        polyline.append([bx, by])
            elif cmd == 'Z':
                pass
        if len(polyline) > 1:
            pts = np.array(polyline, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=False, color=0, thickness=w, lineType=cv2.LINE_AA)
    return img


def render_gray(svg: str, width: int, height: int) -> np.ndarray:
    """Render an SVG string (white background rect expected) to a uint8 grayscale array (height, width)."""
    b = _pick()
    if b == "resvg":
        import resvg_py
        data = bytes(resvg_py.svg_to_bytes(svg_string=svg))
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    elif b == "cairosvg":
        import cairosvg
        data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    elif b == "playwright":
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as td:
            fn = os.path.join(td, "a.svg")
            open(fn, "w").write(svg)
            with sync_playwright() as p:
                br = p.chromium.launch()
                pg = br.new_page(viewport={"width": width, "height": height})
                pg.goto("file://" + fn)
                pg.screenshot(path=os.path.join(td, "a.png"))
                br.close()
            im = cv2.imread(os.path.join(td, "a.png"), cv2.IMREAD_UNCHANGED)
    else:
        return _opencv_svg_to_gray(svg, width, height)

    if im.ndim == 3 and im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        rgb = im[:, :, :3].astype(np.float32) * a + 255 * (1 - a)
        g = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    elif im.ndim == 3:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    else:
        g = im
    if g.shape != (height, width):
        g = cv2.resize(g, (width, height), interpolation=cv2.INTER_AREA)
    return g
