# Linework

Raster icon sheet in, clean single-centerline SVG out. Three backend engines loop until the result matches:

- **Edit** – fits Bezier centerlines, merges duplicate/double lines, smooths kinks (gradient optimiser).
- **Output** – renders the SVG (resvg).
- **Doctor** – compares the render with your image, sends fix commands back to Edit; every fix is re-rendered and rejected if it makes the match worse.

## Run
    pip install -r requirements.txt
    python run.py            # http://localhost:8000   (PORT=9000 python run.py to change)
or `docker build -t linework . && docker run -p 8000:8000 linework`

## Use
Open the page, drop any icon sheet (PNG/JPG/WebP, one icon or many), pick Fast / Standard / Precise.
Watch the engines live, click an icon to zoom, switch Vector / Original / Overlay / Diff,
restyle (colour, weight, background) live, then download SVG or a ZIP of per-icon SVGs.

Note: 100% pixel-identical is not reachable from a blurry JPG; expect ~97-99%. The Doctor aims for 99.5% and stops when no fix improves the match.
Tests: `python tests/test_topology.py; python tests/test_rings.py; python tests/test_budget.py; python tests/test_repair.py`. See CHANGELOG.md. To merge this update into an older copy, give ANTIGRAVITY_PROMPT.md to your coding agent.

## Memory and set consistency (0.6.0)
Results are remembered in `data/lessons` (set `LINEWORK_MEMORY=0` to switch off, `LINEWORK_DATA=<dir>` to move it). `python -m linework.lessons` prints which defect kinds keep coming back; the server serves it at `/api/lessons`.
After all icons of a sheet are done the set pass unifies stroke widths and re-runs clearly weaker icons.

## Join engine (0.7.0)
Every joint (T / L / Y) is checked on its own and failing ones are repaired with the pen / line / arc / shape / unite tools; see `linework/joints.py` and `CHANGELOG.md`. `python tools/outline_view.py result.svg out.png` shows centrelines and marks hooks and nubs.
