import os, sys, tempfile, numpy as np, cv2
os.environ["LINEWORK_DATA"] = tempfile.mkdtemp()
os.environ["LINEWORK_MEMORY"] = "1"
sys.path.insert(0, '.')
from linework import lessons as LS, setlevel as SL
from linework.pipeline import Options, process_icon
from linework.model import Model, Path


def icon():
    g = np.full((200, 200), 255, np.uint8)
    cv2.rectangle(g, (30, 30), (170, 170), 0, 9, cv2.LINE_AA)
    cv2.circle(g, (100, 100), 30, 0, 9, cv2.LINE_AA)
    return g


def test_same_icon_is_reused_and_floor_holds():
    g = icon()
    r1 = process_icon(g, Options(quality="fast"), name="a")
    r2 = process_icon(g, Options(quality="fast"), name="a")
    assert r2["metrics"].get("from_memory") and abs(r2["metrics"]["iou"] - r1["metrics"]["iou"]) < 1e-9
    # a stored result that is better than a fresh run is never replaced by a worse one
    key = LS.crop_key(g, "fast", 0.0)
    prev = LS.best_get(key)
    LS.best_put(key, prev["model"], dict(prev["metrics"], iou=0.999), "0.0.0")  # pretend an older, better run
    r3 = process_icon(g, Options(quality="fast"), name="a")
    assert r3["metrics"]["iou"] >= 0.999 - 1e-9, r3["metrics"]["iou"]


def test_log_summary_and_skip():
    process_icon(icon(), Options(quality='fast', fresh=True), name='b')
    s = LS.summary()
    assert s["icons"] >= 1 and "passes" in s


def test_weak_icon_detection():
    mets = [dict(iou=0.98, issues={}), dict(iou=0.981, issues={}), dict(iou=0.97, issues={}), dict(iou=0.93, issues={})]
    assert SL.weak_icons(mets) == [3]
    assert SL.weak_icons(mets[:2]) == []


def test_set_widths_are_unified():
    def ln(x, w):
        a, b = np.array([x, 20.]), np.array([x, 120.])
        return Path([a, b], [a, a + (b - a) * 2 / 3], [a + (b - a) / 3, b], w)
    ga = np.full((140, 100), 255, np.uint8)
    gb = ga.copy()
    from linework.doctor import ink_of
    ga = (255 * (1 - ink_of(Model([ln(30.5, 10.1)], 100, 140)))).astype(np.uint8)
    gb = (255 * (1 - ink_of(Model([ln(70.5, 10.1)], 100, 140)))).astype(np.uint8)
    A = Model([ln(30.5, 10.3)], 100, 140)
    B = Model([ln(70.5, 9.9)], 100, 140)
    out, rep = SL.harmonize_widths([A, B], [ga, gb])
    assert abs(out[0].paths[0].w - out[1].paths[0].w) < 1e-6, rep
