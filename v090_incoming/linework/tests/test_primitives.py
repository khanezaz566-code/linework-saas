import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.geom import fit_curve
from linework import finisher as FN, rings as RG, focus as FC


def test_wobbly_box_becomes_exact_lines_and_arcs():
    rng = np.random.RandomState(1)
    pts = []
    for x in np.linspace(40, 200, 160): pts.append((x, 40))
    for y in np.linspace(40, 120, 80): pts.append((200, y))
    for x in np.linspace(200, 40, 160): pts.append((x, 120))
    for y in np.linspace(120, 40, 80): pts.append((40, y))
    P = np.array(pts, float) + rng.normal(0, 0.3, (len(pts), 2))
    p = Path.from_segs(fit_curve(np.vstack([P, P[:1]]), 0.8, 0.45), 8, closed=True)
    q = FN.prim_refit(p)
    assert q is not None and len(q.A) <= len(p.A)
    # every side is exactly axis-parallel now
    segs = q.segs()
    straight = [s for s in segs if np.allclose(s[0], s[3], atol=1e-6) is False]
    assert any(abs(s[0][0] - s[3][0]) < 0.05 or abs(s[0][1] - s[3][1]) < 0.05 for s in straight)


def test_free_form_curve_is_left_alone():
    t = np.linspace(0, 1, 300)
    P = np.c_[40 + 300 * t, 100 + 40 * np.sin(6 * t) * np.cos(11 * t)]
    p = Path.from_segs(fit_curve(P, 0.8, 0.45), 8)
    assert FN.prim_refit(p) is None or len(FN.prim_refit(p).A) < 40


def test_hidden_ring_yields_visible_arcs_only():
    D = np.zeros((120, 120), np.float32)
    cv2.circle(D, (60, 60), 30, 1.0, 8)
    cv2.rectangle(D, (50, 80), (70, 118), 0.0, -1)  # something erased the bottom of the ring
    ring = dict(cx=60.5, cy=60.5, a=30, b=30, th=0, r=30, w=8)
    arcs = RG.ring_arcs(ring, D)
    assert arcs and all(not a.closed for a in arcs)


def test_focus_weights_mark_thin_gaps():
    D = np.zeros((100, 100), np.float32)
    D[:, 20:40] = 1; D[:, 44:64] = 1  # 4 px gap between two bars
    W = FC.weights(D, w=20)
    assert W[50, 42] > 1.5 and W[50, 80] == 1.0
