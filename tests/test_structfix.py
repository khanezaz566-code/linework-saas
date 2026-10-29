import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.trace import ink_map
from linework.doctor import Doctor, ink_of
from linework import structfix as SF, structure as ST
from linework.geom import fit_curve


def curve(pts, w):
    return Path.from_segs(fit_curve(np.asarray(pts, float), 0.8, 0.45), w)


def test_wobbling_stroke_is_smoothed_and_match_stays_close():
    t = np.linspace(0, 1, 240)
    wob = np.c_[40 + t * 300, 100 + 25 * np.sin(t * 5) + 2.5 * np.sin(t * 70)]
    m = Model([curve(wob, 10)], 400, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    m2, ink2, cur2, rep = SF.run_structure_engine(m, D, doc, ink_of, doc.soft(ink_of(m)), 10.0)
    assert rep["fixed"] >= 1 and any(s["how"] == "wobble" for s in rep["sites"])
    assert doc.iou(ink2) > 0.75  # wobble removed on purpose: costs a little overlap with the wobbly source


def test_fused_double_line_is_split_in_two():
    m = Model([curve(np.c_[np.linspace(40, 300, 120), np.full(120, 100.0)], 24)], 340, 200)
    cands = SF.double_candidates(m, 10.0)
    assert len(cands) == 1 and len(cands[0][1].paths) == 2
    ys = sorted(float(p.A[0][1]) for p in cands[0][1].paths)
    assert abs((ys[1] - ys[0]) - 14) < 1.5


def test_clean_icon_is_left_alone():
    m = Model([curve(np.c_[np.linspace(40, 300, 120), np.full(120, 100.0)], 10)], 340, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    m2, ink2, cur2, rep = SF.run_structure_engine(m, D, doc, ink_of, doc.soft(ink_of(m)), 10.0)
    assert rep["fixed"] == 0
