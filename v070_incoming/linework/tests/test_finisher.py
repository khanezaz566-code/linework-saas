import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.trace import ink_map
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import finisher as FN


def line(a, b, w):
    a, b = np.array(a, float), np.array(b, float)
    return Path([a, b], [a, a + (b - a) / 3 * 2], [a + (b - a) / 3, b], w)


def src(m):
    return (ink_of(m)).astype(np.float32)


def test_axis_and_width_are_cleaned_without_hurting_match():
    # a "hand drawn" square whose sides are off-axis by a hair and whose widths differ by 6 %
    ideal = Model([line((40, 40), (40, 200), 10), line((120, 40), (120, 200), 10), line((40, 40), (120, 40), 10)], 200, 240)
    D = src(ideal)
    messy = Model([line((40.4, 40), (40, 200), 10.6), line((119.5, 40), (120.3, 200), 9.4), line((40, 40.3), (120, 40), 10)], 200, 240)
    doc = Doctor(D)
    s0 = doc.soft(ink_of(messy))
    m, ink, cur, rep = FN.finish(messy, D, doc, ink_of, s0, 10.0)
    assert cur <= s0 + 1.0, (s0, cur)
    ws = [p.w for p in m.paths]
    assert max(ws) - min(ws) < 1e-6, ws
    p = m.paths[0]
    assert abs(p.A[0][0] - p.A[1][0]) < 1e-6, p.A
    assert rep["fixed"] >= 2


def test_bad_handles_are_detected():
    a, b = np.array([20., 20.]), np.array([100., 20.])
    p = Path([a, b], [a, b + [40, 30]], [a - [30, 0], b], 8)  # loops back / overshoots
    assert FN.bad_handle_paths(Model([p], 120, 60))


def test_hairline_and_wobbly_straight():
    from linework.finisher import hairline_paths, wobbly_straights, make_straight
    a, b = np.array([20., 20.]), np.array([20., 120.])
    mid = (a + b) / 2 + [0.6, 0]
    wob = Path([a, mid, b], [a, mid - [0, 10], mid + [0, 10]][:3], [a + [0, 10], mid + [0, 10], b], 10)
    ok = [line((60, 20), (60, 120), 10), line((90, 20), (90, 120), 10), line((120, 20), (120, 120), 10)]
    hair = line((10, 150), (150, 150), 2.0)
    m = Model(ok + [wob, hair], 170, 170)
    assert [i for i, _ in hairline_paths(m)] == [4]
    assert 3 in [i for i, _ in wobbly_straights(m)]
    assert len(make_straight(m, 3).paths[3].A) == 2


def test_cut_stroke_is_joined():
    from linework.finisher import collinear_pairs, join_pairs
    D = np.zeros((160, 160), np.float32)
    cv2.line(D, (80, 10), (80, 150), 1, 10)
    cv2.line(D, (20, 80), (140, 80), 1, 10)
    top, bot = line((80, 10), (80, 72), 10), line((81, 88), (81, 150), 10)
    m = Model([top, bot, line((20, 80), (140, 80), 10)], 160, 160)
    pr = collinear_pairs(m, D)
    assert len(pr) == 1
    j = join_pairs(m, pr)
    assert len(j.paths) == 2 and j.paths[0].length() > 135


def test_cap_nub_is_tucked():
    from linework.finisher import cap_hits, best_end_move
    m = Model([line((10, 50), (150, 50), 10), line((80, 10), (80, 53), 10)], 160, 100)
    assert cap_hits(m)
    cand, pr = best_end_move(m, 1, 1, 10)
    assert pr < 0.5 and not cap_hits(cand)


def test_overshoot_stub_is_cut_back_only_if_source_agrees():
    from linework.finisher import cap_hits, best_end_move
    # a coil bar that crosses the vertical side and overshoots it by 0.8 w
    side, bar = line((60, 10), (60, 150), 10), line((20, 80), (72, 80), 10)
    m = Model([side, bar], 120, 160)
    hits = cap_hits(m)
    assert hits and hits[0][1] == 1, hits
    cand, pr = best_end_move(m, 1, 1, 10)
    assert pr < 0.2 * 10 and not cap_hits(cand)
    # Finisher keeps the cut when the source is flush, rejects it when the source has the stub
    from linework.finisher import finish
    flush = Model([side, line((20, 80), (60, 80), 10)], 120, 160)
    D = src(flush)
    doc = Doctor(D)
    m1, _, c1, rep = finish(m, D, doc, ink_of, doc.soft(ink_of(m)), 10.0)
    assert any(s["kind"] == "caps" and s["fixed"] for s in rep["sites"]), rep["sites"]
    D2 = src(m)
    doc2 = Doctor(D2)
    m2, _, c2, rep2 = finish(m, D2, doc2, ink_of, doc2.soft(ink_of(m)), 10.0)
    assert not any(s["kind"] == "caps" and s["fixed"] for s in rep2["sites"]), rep2["sites"]


def test_wobbly_arc_becomes_exact_and_is_kept_when_source_agrees():
    from linework.finisher import arc_paths
    rng = np.random.default_rng(1)
    c, r = np.array([100., 100.]), 60.0
    th = np.linspace(0.3, 2.6, 60)
    pts = c + (r + rng.normal(0, 0.25, len(th)))[:, None] * np.c_[np.cos(th), np.sin(th)]
    from linework.geom import fit_curve
    segs = fit_curve(pts, 0.8, 0.3)
    p = Path.from_segs(segs, 8.0)
    m = Model([p], 200, 200)
    hit = arc_paths(m)
    assert hit, "wobbly arc not detected"
    q = hit[0][2].flat(0.5)
    assert np.abs(np.linalg.norm(q - np.array([100., 100.]), axis=1) - 60).max() < 0.6
    # ideal source = the exact arc
    ideal = Model([hit[0][2]], 200, 200)
    D = src(ideal); doc = Doctor(D)
    m2, _, cur, rep = FN.finish(m, D, doc, ink_of, doc.soft(ink_of(m)), 8.0)
    assert any(s["kind"] == "arcs" and s["fixed"] for s in rep["sites"]), rep["sites"]


def test_thick_tip_is_pulled_back_and_corner_is_merged():
    from linework.finisher import excess_ends, corner_pairs, merge_corners
    import math
    apex = np.array([100., 40.])
    a = apex + 90 * np.array([math.sin(math.radians(15)), math.cos(math.radians(15))])
    b = apex + 90 * np.array([-math.sin(math.radians(15)), math.cos(math.radians(15))])
    ideal = Model([line(a, apex, 10), line(apex, b, 10)], 200, 160)
    D = src(ideal)
    doc = Doctor(D)
    # corner drawn as two strokes -> one stroke
    pr = corner_pairs(ideal)
    assert len(pr) == 1
    one = merge_corners(ideal, pr)
    assert len(one.paths) == 1 and len(one.paths[0].A) == 3
    assert doc.soft(ink_of(one)) <= doc.soft(ink_of(ideal)) + 5
    # one arm overshoots the apex by 8 px -> thick/long tip
    over = Model([line(a, apex + 8 * (apex - a) / np.linalg.norm(apex - a), 10), line(apex, b, 10)], 200, 160)
    assert excess_ends(over, ink_of(over), D)
    m2, _, cur, rep = FN.finish(over, D, doc, ink_of, doc.soft(ink_of(over)), 10.0)
    assert cur < doc.soft(ink_of(over)) * 0.6, (doc.soft(ink_of(over)), cur, rep["sites"])


def test_hooked_branch_end_is_straightened_onto_the_centerline():
    from linework.finisher import end_hooks, fix_end
    main = line((20, 100), (200, 100), 10)
    # a vertical branch whose last 14 px curl sideways before touching the main stroke
    a = np.array([110., 10.]); b = np.array([110., 100.])
    seg1 = [a, np.array([110., 38.]), np.array([110., 62.]), np.array([110., 86.])]
    seg2 = [np.array([110., 86.]), np.array([110., 92.]), np.array([117., 93.]), np.array([117., 100.])]
    hooked = Path.from_segs([seg1, seg2], 10.0)
    m = Model([main, hooked], 220, 140)
    assert end_hooks(m), "hook not detected"
    ideal = Model([main, line(a, b, 10)], 220, 140)
    D = src(ideal); doc = Doctor(D)
    s0 = doc.soft(ink_of(m))
    cand = fix_end(m, 1, 1)
    assert cand is not None
    assert doc.soft(ink_of(cand)) < s0 * 0.6, (s0, doc.soft(ink_of(cand)))
    assert not end_hooks(cand)


def test_cut_stroke_with_hooked_ends_is_joined_through_a_crossing():
    from linework.finisher import collinear_pairs, join_pairs
    D = np.zeros((160, 200), np.float32)
    cv2.line(D, (100, 10), (100, 150), 1, 10)
    cv2.line(D, (10, 80), (190, 80), 1, 10)
    bar = line((100, 10), (100, 150), 10)
    # left piece ends with a 6 px jog before the bar, right piece starts with one
    L = Path.from_segs([[np.array([10., 80.]), np.array([40., 80.]), np.array([70., 80.]), np.array([86., 80.])],
                        [np.array([86., 80.]), np.array([91., 80.]), np.array([93., 85.]), np.array([96., 86.])]], 10.0)
    R = Path.from_segs([[np.array([104., 74.]), np.array([107., 75.]), np.array([109., 80.]), np.array([114., 80.])],
                        [np.array([114., 80.]), np.array([140., 80.]), np.array([165., 80.]), np.array([190., 80.])]], 10.0)
    m = Model([bar, L, R], 200, 160)
    pr = collinear_pairs(m, D)
    assert pr, "pieces of one line were not paired"
    j = join_pairs(m, pr)
    assert len(j.paths) == 2
    ys = j.paths[1].flat(1.0)[:, 1]
    assert np.abs(ys - 80).max() < 2.5, ys.min()
