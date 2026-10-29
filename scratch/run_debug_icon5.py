import cv2, json, sys
sys.path.insert(0, '.')
from linework.pipeline import Options, process_icon

crop = cv2.imread('scratch/icon_crop_5.png', 0)
def emit(**kwargs):
    if kwargs.get('engine') in ('trace', 'edit', 'doctor', 'finisher', 'structure', 'joints'):
        print(f"[{kwargs.get('engine')}] {kwargs.get('msg')}")

opts = Options(quality='standard', fresh=True)
r = process_icon(crop, opts, emit=emit, name='icon5_debug')
print("Final IoU:", r['metrics']['iou'])
print("Final paths:", len(r['model'].paths))
print("Final audit/issues:", r['metrics']['issues'])
print("Final finisher:", r['metrics']['finisher'])
print("Final joins:", r['metrics']['joins'])
print("Final structure:", r['metrics']['structure'])
