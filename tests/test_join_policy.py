import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import joinpolicy as JP, edit as E


def poly(pts, w, join="round", ml=4.0):
    pts = [np.array(p, float) for p in pts]
    segs = [np.array([a, a + (b - a) / 3, a + (b - a) * 2 / 3, b]) for a, b in zip(pts[:-1], pts[1:])]
    p = Path.from_segs(segs, w, join=join)
    p.ml = ml
    return p


def V(angle_deg, w, join, ml):
    h = np.radians(angle_deg / 2)
    L = 60.0
    apex = np.array([50.0, 20.0])
    a = apex + L * np.array([-np.sin(h), np.cos(h)])
    b = apex + L * np.array([np.sin(h), np.cos(h)])
    return Model([poly([a, apex, b], w, join, ml)], 100, 100)


def test_roundtrip_keeps_join_and_miterlimit():
    m = Model([poly([(10, 10), (40, 10), (40, 40)], 6, "miter", 1.5),
               poly([(10, 50), (40, 50), (40, 80)], 6, "round"),
               poly([(50, 10), (80, 10), (80, 40)], 6, "bevel"),
               poly([(50, 50), (80, 50), (80, 80)], 6, "miter", 10.0)], 100, 100)
    s = m.svg()
    m2 = Model.from_svg(s)
    assert [p.join for p in m2.paths] == ["miter", "round", "bevel", "miter"]
    assert [p.ml for p in m2.paths if p.join == "miter"] == [1.5, 10.0]
    assert m2.svg() == s


def test_spike_is_removed_at_acute_joint():
    # source = round-joined 30 degree V; model starts with the old behaviour (miter, limit 10 -> long spike)
    D = ink_of(V(30, 6, "round", 4.0)).astype(np.float32)
    bad = V(30, 6, "miter", 10.0)
    doc = Doctor(D)
    before = doc.soft(ink_of(bad))
    m = E.execute(bad, dict(op="join", path=0, join="miter"), D)[0]
    after = doc.soft(ink_of(m))
    assert m.paths[0].join != "miter" or m.paths[0].ml <= 2.0, (m.paths[0].join, m.paths[0].ml)
    assert after < before * 0.5, (before, after)


def test_miter_kept_when_source_is_mitred():
    D = ink_of(V(90, 6, "miter", 4.0)).astype(np.float32)
    start = V(90, 6, "round", 4.0)
    m = JP.choose_join(start, 0, D)
    assert m.paths[0].join == "miter", m.paths[0].join


def test_clean_joint_is_left_alone():
    D = ink_of(V(90, 6, "round", 4.0)).astype(np.float32)
    m0 = V(90, 6, "round", 4.0)
    assert JP.choose_join(m0, 0, D) is m0


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("ok", k)
