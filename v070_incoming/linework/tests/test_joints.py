import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import joints as J


def line(a, b, w=10.0):
    a, b = np.array(a, float), np.array(b, float)
    return Path([a, b], [a, a + (b - a) * 2 / 3], [a + (b - a) / 3, b], w)


def src(m):
    return ink_of(m).astype(np.float32)


def run(model, ideal):
    D = src(ideal)
    doc = Doctor(D)
    cur = doc.soft(ink_of(model))
    m, ink, c, rep = J.run_join_engine(model, D, doc, ink_of, cur, 10.0)
    return m, c, cur, rep, doc, D


def test_clean_t_and_l_joints_have_no_failures_and_are_untouched():
    ideal = Model([line((20, 100), (200, 100)), line((110, 10), (110, 100)), line((30, 20), (80, 60)), line((80, 60), (120, 40))], 220, 140)
    js = J.find_joints(ideal)
    assert js
    for j in js:
        assert not J.check_joint(ideal, j), (j.kind, J.check_joint(ideal, j))


def test_off_center_hooked_t_branch_is_repaired():
    main = line((20, 100), (200, 100))
    a = np.array([110., 10.])
    seg1 = [a, np.array([110., 38.]), np.array([110., 62.]), np.array([110., 86.])]
    seg2 = [np.array([110., 86.]), np.array([110., 92.]), np.array([117., 93.]), np.array([117., 100.])]
    hooked = Path.from_segs([seg1, seg2], 10.0)
    model = Model([main, hooked], 220, 140)
    ideal = Model([main, line((110, 10), (110, 100))], 220, 140)
    js = J.find_joints(model)
    assert any(J.check_joint(model, j) for j in js)
    m, c, cur, rep, doc, D = run(model, ideal)
    assert c < 0.6 * cur, (cur, c, rep)
    assert not any(J.check_joint(m, j) for j in J.find_joints(m)), rep
    assert sum(rep["fixed"].values()) >= 1


def test_split_corner_with_gap_becomes_one_clean_corner():
    a, apex, b = np.array([30., 120.]), np.array([100., 40.]), np.array([170., 120.])
    ideal = Model([line(a, apex), line(apex, b)], 200, 160)
    model = Model([line(a, apex + [0, 4]), line(apex + [3, 1], b)], 200, 160)  # ends 3-4 px off the apex, not coincident
    m, c, cur, rep, doc, D = run(model, ideal)
    assert c <= cur + 1.0
    assert not any(J.check_joint(m, j) for j in J.find_joints(m)), rep


def test_pen_tools():
    p = line((0, 0), (100, 0)).copy()
    k = J.insert_anchor(p, (50, 0))
    assert len(p.A) == 3 and abs(p.A[k][0] - 50) < 0.6
    assert np.abs(p.flat(0.5)[:, 1]).max() < 1e-6
    q = Path([[0, 0], [0.1, 0], [50, 0], [100, 0]], [[0, 0]] * 4, [[0, 0]] * 4, 10.0)
    assert len(J.delete_duplicate_anchors(q).A) == 3
