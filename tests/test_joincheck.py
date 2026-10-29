import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import joincheck as JC


def line(a, b, w):
    a, b = np.array(a, float), np.array(b, float)
    return Path([a, b], [a, a + (b - a) / 3 * 2], [a + (b - a) / 3, b], w)


def reasons(m, D):
    return sorted(r for j in JC.inspect(m, D, ink_of(m)) for r in j["reasons"])


def test_clean_tee_passes_and_is_left_alone():
    ideal = Model([line((20, 100), (200, 100), 10), line((110, 20), (110, 100), 10)], 220, 140)
    D = ink_of(ideal)
    js = JC.inspect(ideal, D, D)
    assert js and all(not j["reasons"] for j in js), js
    doc = Doctor(D)
    m, ink, cur, rep = JC.run(ideal, D, doc, ink_of, doc.soft(D), 10.0)
    assert rep["fixed"] == 0 and rep["bad_after"] == 0 and len(m.paths) == 2


def test_tee_end_short_of_the_centerline_is_snapped_onto_it():
    ideal = Model([line((20, 100), (200, 100), 10), line((110, 20), (110, 100), 10)], 220, 140)
    D = ink_of(ideal)
    bad = Model([line((20, 100), (200, 100), 10), line((110, 20), (110, 94), 10)], 220, 140)  # branch stops 6 px (0.6 w) short of the centerline
    assert "off_center" in reasons(bad, D)
    doc = Doctor(D)
    m, ink, cur, rep = JC.run(bad, D, doc, ink_of, doc.soft(ink_of(bad)), 10.0)
    assert rep["fixed"] >= 1 and rep["bad_after"] == 0, rep
    assert cur <= doc.soft(ink_of(bad)) + 1.0
    assert abs(m.paths[1].A[-1][1] - 100) < 1.5 and abs(m.paths[1].A[-1][0] - 110) < 1.5


def test_hub_with_scattered_ends_meets_in_one_point():
    c = np.array([110., 110.])
    ang = [0.0, 2.1, 4.2]
    ideal = Model([line(c + 90 * np.array([np.cos(a), np.sin(a)]), c, 10) for a in ang], 220, 220)
    D = ink_of(ideal)
    bad = Model([line(c + 90 * np.array([np.cos(a), np.sin(a)]), c + 5 * np.array([np.cos(a + 1.3), np.sin(a + 1.3)]), 10) for a in ang], 220, 220)
    assert "y_spread" in reasons(bad, D)
    doc = Doctor(D)
    m, ink, cur, rep = JC.run(bad, D, doc, ink_of, doc.soft(ink_of(bad)), 10.0)
    assert rep["fixed"] >= 1 and "y_spread" not in reasons(m, D), rep


def test_corner_drawn_as_two_strokes_becomes_one_stroke():
    ideal = Model([Path.from_segs([[np.array([30., 30.]), np.array([30., 70.]), np.array([30., 100.]), np.array([30., 130.])],
                                   [np.array([30., 130.]), np.array([70., 130.]), np.array([110., 130.]), np.array([150., 130.])]], 10.0)], 200, 160)
    D = ink_of(ideal)
    two = Model([line((30, 30), (30, 130), 10), line((30, 130), (150, 130), 10)], 200, 160)
    assert "corner_split" in reasons(two, D)
    doc = Doctor(D)
    m, ink, cur, rep = JC.run(two, D, doc, ink_of, doc.soft(ink_of(two)), 10.0)
    assert len(m.paths) == 1 and "corner_split" not in reasons(m, D), rep


def test_cut_stroke_through_a_crossing_is_rejoined():
    D = ink_of(Model([line((10, 80), (190, 80), 10), line((100, 10), (100, 150), 10)], 200, 160))
    cut = Model([line((100, 10), (100, 150), 10), line((10, 80), (92, 80), 10), line((108, 80), (190, 80), 10)], 200, 160)
    assert "split" in reasons(cut, D)
    doc = Doctor(D)
    m, ink, cur, rep = JC.run(cut, D, doc, ink_of, doc.soft(ink_of(cut)), 10.0)
    assert len(m.paths) == 2 and "split" not in reasons(m, D), rep


if __name__ == '__main__':
    test_clean_tee_passes_and_is_left_alone(); print('ok clean tee passes')
    test_tee_end_short_of_the_centerline_is_snapped_onto_it(); print('ok tee snapped')
    test_hub_with_scattered_ends_meets_in_one_point(); print('ok hub meets')
    test_corner_drawn_as_two_strokes_becomes_one_stroke(); print('ok corner merged')
    test_cut_stroke_through_a_crossing_is_rejoined(); print('ok cut rejoined')
