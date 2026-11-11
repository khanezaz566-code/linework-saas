import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from linework.pipeline import Options, process_icon
from tests.make_heavy_joins_sheet import (
    draw_interlocking_gears, draw_benzene_molecule, draw_dial_gauge,
    draw_audio_equalizer, draw_warded_key
)

icons = [
    ('gears', draw_interlocking_gears),
    ('benzene', draw_benzene_molecule),
    ('dial_gauge', draw_dial_gauge),
    ('equalizer', draw_audio_equalizer),
    ('key', draw_warded_key)
]

opts = Options(fresh=True, memory=False, quality='standard', joins=True, decision=True)

for name, fn in icons:
    canvas = np.full((180, 180), 255, dtype=np.uint8)
    fn(canvas, 90, 90, 6, seed=0)
    res = process_icon(canvas, opts, name=name)
    met = res['metrics']
    iou = met['iou'] * 100
    hard = met['hard']
    print(f"{name:<15}: IoU = {iou:6.2f}%, hard = {hard:3d}, paths = {met['paths']}, nodes = {met['nodes']}")
    if 'decision' in res:
        drep = res['decision']
        if drep.get('open_findings'):
            print(f"   open_findings: {drep['open_findings']}")
