import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np
sys.path.insert(0, '.')
from linework.model import Path, Model
from linework import topology as T


def line(a, b, w=15):
    a, b = np.array(a, float), np.array(b, float)
    return Path([a, b], [a, b - (b - a) / 3], [a + (b - a) / 3, b], w)


def test_corner_gap_is_welded():
    m = Model([line((10, 200), (10, 20)), line((22, 14), (200, 14))], 300, 300)  # L corner, ends ~12px apart
    assert len(T.find_gaps(m)) == 1
    w = T.weld_all(m)
    a, b = w.paths[0].A[-1], w.paths[1].A[0]
    assert np.linalg.norm(a - b) < 1e-6 and abs(a[0] - 10) < 1 and abs(a[1] - 14) < 1  # meets at the axis intersection
    assert not T.find_gaps(w)


def test_tee_gap_is_snapped():
    m = Model([line((0, 50), (200, 50)), line((100, 200), (100, 58))], 300, 300)
    w = T.weld_all(m)
    assert abs(w.paths[1].A[-1][1] - 50) < 0.5


def test_chamfer_step_is_merged():
    A = [(0, 100), (50, 50), (56, 47), (60, 47), (66, 50), (116, 100)]  # flat tiny step at the apex
    A = np.array(A, float)
    p = Path(A, A.copy(), A.copy(), 15)
    m = Model([p], 200, 200)
    assert T.find_notches(m) == [0]
    out = T.merge_nodes(m, 0)
    assert len(out.paths[0].A) < 6 and not T.find_notches(out)


def test_curl_is_trimmed():
    A = np.array([(0, 0), (100, 0), (104, 6)], float)
    p = Path(A, A.copy(), A.copy(), 15)
    m = Model([p], 200, 200)
    assert T.find_spurs(m) == [(0, 1)]
    assert len(T.trim_tail(m, 0, 1).paths[0].A) == 2

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
