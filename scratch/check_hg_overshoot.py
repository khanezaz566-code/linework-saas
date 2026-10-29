import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, joints as JN
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map

gray = cv2.imread("data/ea3cb3bb04a7/original.png", 0)
_, jobs = P.process_sheet(gray)[1:]
crop = jobs[4][1]
D = ink_map(crop)
doc = Doctor(D)
r = P.process_icon(crop, P.Options(quality="fast", memory=False, joins=False), name="hg")
m0 = r["model"]
print("Before joins IoU:", doc.iou(ink_of(m0)))
for idx, J in enumerate(JN.find_joints(m0)):
    bad = JN.check_joint(m0, J)
    if bad:
        m1 = JN.tool_pen(m0, J, merge_l=False)
        print(f"  J[{idx}] kind={J.kind} xy={J.xy.round(1)} ends={J.ends} thr={J.through} bad={bad} -> dIoU={(doc.iou(ink_of(m1)) - doc.iou(ink_of(m0)))*100:+.3f}%")
