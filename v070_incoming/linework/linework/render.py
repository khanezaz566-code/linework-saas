"""Output engine: SVG -> grayscale raster. Uses resvg (fast, exact AA); falls back to cairosvg / Chromium."""
from __future__ import annotations
import io, os, tempfile
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
            _BACKEND = "playwright"
    return _BACKEND


def backend_name():
    return _pick()


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
    else:
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
