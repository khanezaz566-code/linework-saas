import os, sys, cv2, json, numpy as np
os.environ["LINEWORK_MEMORY"] = "0"
sys.path.insert(0, ".")
from linework.pipeline import Options, process_icon
from linework import structure as ST
from linework.trace import ink_map

orig = cv2.imread("data/aca01e4ff5aa/original.png", cv2.IMREAD_GRAYSCALE)
j = json.load(open("data/aca01e4ff5aa/job.json"))

test_icons = [
    (2, "Radiator slat jog"),
    (5, "Anchor fluke barb spur"),
    (6, "Life vest collar & straps"),
    (8, "Cleat curved bar & junctions"),
    (9, "Hydrant spout pipe penetration"),
]

for idx, desc in test_icons:
    box = j["icons"][idx]["box"]
    crop = orig[box[1]:box[3], box[0]:box[2]]
    r = process_icon(crop, Options(quality="fast", structure=True), name=f"icon_{idx}")
    iou = r["metrics"]["iou"]
    struct = r["metrics"].get("structure", {})
    joins = r["metrics"].get("joins", {})
    fin = r["metrics"].get("finisher", {})
    print(f"\n=== Icon {idx} ({desc}) ===")
    print(f"  Match IoU: {iou*100:.2f}% (initial: {r['metrics'].get('iou_initial', 0)*100:.2f}%)")
    print(f"  Structure before: {struct.get('before', 0):.2f} -> after: {struct.get('after', 0):.2f}, fixed: {struct.get('fixed', 0)}")
    print(f"  Joins: total {joins.get('total')}, clean_first {joins.get('clean_first')}, repaired {sum((joins.get('fixed') or {}).values())}, unresolved {len(joins.get('unresolved', []))}")
    print(f"  Finisher: found {fin.get('found')}, fixed {fin.get('fixed')}")
    # Save svg for inspection
    with open(f"out/test_icon_{idx}.svg", "w") as f:
        f.write(r["svg"])
