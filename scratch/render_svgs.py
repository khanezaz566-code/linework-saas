import json, os
from pathlib import Path
import resvg_py

d = Path('data/aca01e4ff5aa')
for k in range(12):
    svg_file = d / f'icon_{k}.svg'
    if svg_file.exists():
        svg_data = svg_file.read_text(encoding='utf-8')
        png_data = resvg_py.svg_to_bytes(svg_string=svg_data, width=300)
        Path(f'scratch/rendered_icon_{k}.png').write_bytes(png_data)
        print(f"Rendered icon {k}")
