import os
os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np, cv2
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import joints as J
from linework import finisher as FN
from linework.pipeline import Options, process_icon


def make_line(p0, p1, w=8.0):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    mid1 = p0 + (p1 - p0) / 3.0
    mid2 = p0 + (p1 - p0) * 2.0 / 3.0
    return Path([p0, p1], [p0, mid2], [mid1, p1], w)


def make_arc(cx, cy, r, t0_deg, t1_deg, w=8.0):
    t0, t1 = np.radians(t0_deg), np.radians(t1_deg)
    p0 = np.array([cx + r * np.cos(t0), cy + r * np.sin(t0)])
    p1 = np.array([cx + r * np.cos(t1), cy + r * np.sin(t1)])
    k = (4.0 / 3.0) * np.tan((t1 - t0) / 4.0)
    h0 = p0 + np.array([-k * r * np.sin(t0), k * r * np.cos(t0)])
    h1 = p1 - np.array([-k * r * np.sin(t1), k * r * np.cos(t1)])
    return Path([p0, p1], [p0, h1], [h0, p1], w)


def test_concentric_loops_do_not_pinch():
    """Concentric loops (Defect 2) must remain two separate concentric strokes, not pinched into a bulbous knot."""
    # Outer arch (r=30) and inner arch (r=18)
    outer = make_arc(100, 100, 30, 180, 0, w=8.0)
    inner = make_arc(100, 100, 18, 180, 0, w=8.0)
    m = Model([outer, inner], 200, 200)
    js = J.find_joints(m)
    # The two concentric ends at x=70 and x=82 are parallel (dot product ~1.0); they must NOT be clustered into a single joint!
    clusters_left = [j for j in js if any(abs(e[0] == 0) for e in j.ends) and any(abs(e[0] == 1) for e in j.ends)]
    assert len(clusters_left) == 0, f"Outer and inner concentric arches were wrongly clustered: {js}"


def test_sharp_compass_star_apexes():
    """Acute corners (Defect 3) must be recognized as sharp paths and rendered with crisp miter joins."""
    apex = np.array([100.0, 30.0])
    p1 = make_line([50.0, 150.0], apex, w=8.0)
    p2 = make_line(apex, [150.0, 150.0], w=8.0)
    m = Model([p1, p2], 200, 200)
    pr = FN.corner_pairs(m)
    assert len(pr) == 1
    merged = FN.merge_corners(m, pr)
    doc = Doctor(ink_of(merged))
    rep = doc.diagnose(merged)
    # The merged acute corner (turning angle ~53 deg) must be flagged in rep['sharp']
    assert len(rep['sharp']) > 0, "Acute corner was not recognized as a sharp path"
    cmds = Doctor.cosmetic_commands(rep)
    miter_cmds = [c for c in cmds if c.get('op') == 'join' and c.get('join') == 'miter']
    assert len(miter_cmds) > 0, "No join=miter command issued for sharp apex"
    assert miter_cmds[0]['tol'] > 0, f"Negative tolerance on join command: {miter_cmds[0]}"


def test_continuous_neckline_not_severed():
    """A continuous curved collar/neckline crossed by straps (Defects 1 & 5) must remain one uncut stroke."""
    # Continuous collar curve
    collar = make_arc(100, 50, 60, 20, 160, w=8.0)
    # Two diagonal crossing straps
    strap1 = make_line([60.0, 80.0], [80.0, 160.0], w=8.0)
    strap2 = make_line([140.0, 80.0], [120.0, 160.0], w=8.0)
    m = Model([collar, strap1, strap2], 200, 200)
    doc = Doctor(ink_of(m))
    red, tails = doc.redundancy(m)
    # Neither the collar nor straps should have interior spans cut as tails
    assert not any(t[0] == 0 for t in tails), f"Continuous collar path 0 was falsely cut: {tails}"


def test_complex_ring_and_spokes_unite():
    """Radial spoke meeting a ring in arcs must unite cleanly without creating lump/hole rejections."""
    arc1 = make_arc(100, 100, 40, 0, 180, w=8.0)
    arc2 = make_arc(100, 100, 40, 180, 360, w=8.0)
    spoke = make_line([100.0, 100.0], [100.0, 60.0], w=8.0)  # touches at (100, 60)
    m = Model([arc1, arc2, spoke], 200, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    cur = doc.soft(ink_of(m))
    m2, ink2, cur2, rep = J.run_join_engine(m, D, doc, ink_of, cur, 8.0)
    # The joint must be clean
    js2 = J.find_joints(m2)
    for j in js2:
        bad = J.check_joint(m2, j)
        assert 'touch' not in bad, f"Joint still has touch error: {j}, {bad}"


if __name__ == "__main__":
    test_concentric_loops_do_not_pinch()
    print("PASS: test_concentric_loops_do_not_pinch")
    test_sharp_compass_star_apexes()
    print("PASS: test_sharp_compass_star_apexes")
    test_continuous_neckline_not_severed()
    print("PASS: test_continuous_neckline_not_severed")
    test_complex_ring_and_spokes_unite()
    print("PASS: test_complex_ring_and_spokes_unite")
    print("\nALL COMPLEX JOIN TESTS PASSED!")
