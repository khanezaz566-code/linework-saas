import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.trace import ink_map
from linework import rings as RG
from linework.pipeline import Options, process_icon


def sheet():
    g = np.full((220, 220), 255, np.uint8)
    cv2.circle(g, (110, 110), 60, 0, 6, cv2.LINE_AA)     # ring
    cv2.rectangle(g, (100, 20), (120, 70), 0, 6, cv2.LINE_AA)  # key touching the ring from outside
    return g


def test_ring_found_despite_touching_stroke():
    g = sheet()
    R = RG.detect_rings(ink_map(g), 6.0)
    big = max(R, key=lambda r: r["r"])
    assert abs(big["cx"] - 110.5) < 1.0 and abs(big["cy"] - 110.5) < 1.0 and abs(big["r"] - 60) < 1.0


def test_pipeline_keeps_ring_round():
    r = process_icon(sheet(), Options(quality="fast"), name="t")
    assert r["metrics"]["iou"] > 0.95
    closed = [p for p in r["model"].paths if p.closed]
    assert closed, "ring must be one closed path"


def test_widths_never_negative():
    r = process_icon(sheet(), Options(quality="fast"), name="t")
    assert min(p.w for p in r["model"].paths) > 0

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
