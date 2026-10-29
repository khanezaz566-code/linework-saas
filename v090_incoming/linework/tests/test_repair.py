import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.pipeline import Options, process_icon
from linework.trace import ink_map
from linework.model import Model
from linework.doctor import Doctor, ink_of
from linework import repair as RP


def icon():
    g = np.full((260, 260), 255, np.uint8)
    cv2.rectangle(g, (40, 40), (220, 220), 0, 10, cv2.LINE_AA)
    cv2.line(g, (60, 130), (200, 130), 0, 10, cv2.LINE_AA)
    cv2.circle(g, (130, 80), 22, 0, 8, cv2.LINE_AA)
    cv2.line(g, (90, 170), (170, 190), 0, 10, cv2.LINE_AA)
    return g


def test_missing_stroke_is_restored():
    g = icon(); D = ink_map(g)
    full = process_icon(g, Options(quality="fast", repair=False), name="t")["model"]
    doc = Doctor(D)
    # knock out the longest interior stroke -> a big piece of the source is now missing
    victim = max((i for i, p in enumerate(full.paths) if p.length() < 200 and p.length() > 100), key=lambda i: full.paths[i].length(), default=None)
    assert victim is not None
    broken = Model([p for i, p in enumerate(full.paths) if i != victim], full.width, full.height)
    s0 = doc.soft(ink_of(broken))
    m, ink, cur, nadd, nrem = RP.repair(broken, D, ink_of, doc.soft, s0, 10.0)
    assert nadd >= 1 and cur < 0.4 * s0, (nadd, s0, cur)


def test_stray_stroke_is_removed():
    g = icon(); D = ink_map(g)
    full = process_icon(g, Options(quality="fast", repair=False), name="t")["model"]
    doc = Doctor(D)
    from linework.model import Path
    A = np.array([[60., 235.], [200., 245.]])
    stray = Path(A, A.copy(), A.copy(), 10.0)
    bad = Model(full.paths + [stray], full.width, full.height)
    s0 = doc.soft(ink_of(bad))
    m, ink, cur, nadd, nrem = RP.repair(bad, D, ink_of, doc.soft, s0, 10.0)
    assert nrem >= 1 and cur < s0

if __name__ == "__main__":
    test_missing_stroke_is_restored(); print("ok missing")
    test_stray_stroke_is_removed(); print("ok stray")
