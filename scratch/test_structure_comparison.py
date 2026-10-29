import sys, cv2, numpy as np
sys.path.insert(0, '.')
from linework.pipeline import process_sheet, process_icon, Options

g = cv2.imread('samples/basic-set.png', 0)
W, H, jobs = process_sheet(g, Options(quality='standard'))

print(f"Testing {len(jobs)} icons: structure=False vs structure=True...")
for k, crop, off in jobs:
    r_no_st = process_icon(crop, Options(quality='standard', structure=False, fresh=True), name=f"icon{k+1}")
    r_st = process_icon(crop, Options(quality='standard', structure=True, fresh=True), name=f"icon{k+1}")
    iou_no = r_no_st['metrics']['iou']
    iou_st = r_st['metrics']['iou']
    sx = r_st['metrics'].get('structure', {})
    found = sx.get('found', 0)
    fixed = sx.get('fixed', 0)
    unresolved = len(sx.get('unresolved', []))
    print(f"Icon {k+1}: no_structure={iou_no*100:.2f}% | structure={iou_st*100:.2f}% (delta={((iou_st - iou_no)*100):+.2f}%) | sites found={found}, fixed={fixed}, unres={unresolved}")
