import os
os.environ["LINEWORK_MEMORY"] = "0"
import sys, numpy as np
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, '.')
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
from linework import joints as J
from linework import finisher as FN


def make_line(p0, p1, w=8.0):
    """Helper: create a line path."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    mid1 = p0 + (p1 - p0) / 3.0
    mid2 = p0 + (p1 - p0) * 2.0 / 3.0
    return Path([p0, p1], [p0, mid2], [mid1, p1], w)


def test_single_join_100_percent():
    """Single join should be 100% exact."""
    p1 = make_line([10, 50], [100, 50], w=8.0)
    p2 = make_line([100, 50], [150, 150], w=8.0)
    
    m = Model([p1, p2], 200, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    cur = doc.soft(D)
    
    # Run with batch mode enabled
    m2, ink2, soft2, rep = J.run_join_engine(m, D, doc, ink_of, cur, 8.0, batch_mode=True)
    
    # Check report
    assert rep["batch_mode"] == True, "Batch mode not enabled"
    assert len(rep["unresolved"]) == 0, f"Unresolved joints: {rep['unresolved']}"
    
    # Verify all joints are clean
    joints = J.find_joints(m2)
    for j in joints:
        bad = J.check_joint(m2, j)
        assert len(bad) == 0, f"Joint has errors: {bad}"
    
    print("✓ Single join test passed")


def test_two_joins_100_percent():
    """Two sequential joins should be 100% exact."""
    p1 = make_line([10, 50], [100, 50], w=8.0)
    p2 = make_line([100, 50], [150, 150], w=8.0)
    p3 = make_line([150, 150], [200, 50], w=8.0)
    
    m = Model([p1, p2, p3], 250, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    cur = doc.soft(D)
    
    m2, ink2, soft2, rep = J.run_join_engine(m, D, doc, ink_of, cur, 8.0, batch_mode=True)
    
    assert len(rep["unresolved"]) == 0, f"Unresolved joints: {rep['unresolved']}"
    
    joints = J.find_joints(m2)
    for j in joints:
        bad = J.check_joint(m2, j)
        assert len(bad) == 0, f"Joint has errors: {bad}"
    
    print("✓ Two joins test passed")


def test_four_joins_100_percent():
    """Four joins together (your problem case) should achieve 100%."""
    # Create a path with 5 endpoints (4 joins)
    segments = [
        ([10, 100], [50, 100]),
        ([50, 100], [100, 50]),
        ([100, 50], [150, 100]),
        ([150, 100], [200, 50]),
    ]
    
    paths = [make_line(p0, p1, w=8.0) for p0, p1 in segments]
    
    m = Model(paths, 250, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    cur = doc.soft(D)
    
    m2, ink2, soft2, rep = J.run_join_engine(m, D, doc, ink_of, cur, 8.0, batch_mode=True)
    
    # This is the critical test
    assert len(rep["unresolved"]) == 0, f"Unresolved joints (THIS IS YOUR BUG): {rep['unresolved']}"
    assert rep["drift"] < 0.5, f"Too much drift: {rep['drift']}"
    
    joints = J.find_joints(m2)
    print(f"  Found {len(joints)} joints, {len(rep['unresolved'])} unresolved")
    print(f"  Softness: {soft2:.4f}, Drift: {rep['drift']:.4f}")
    
    for j in joints:
        bad = J.check_joint(m2, j)
        assert len(bad) == 0, f"Joint {j.kind} at ({j.xy[0]:.1f}, {j.xy[1]:.1f}) has errors: {bad}"
    
    print("✓ Four joins test passed (100% match achieved!)")


def test_batch_mode_off():
    """Test that batch_mode=False still works (backward compatibility)."""
    p1 = make_line([10, 50], [100, 50], w=8.0)
    p2 = make_line([100, 50], [150, 150], w=8.0)
    
    m = Model([p1, p2], 200, 200)
    D = ink_of(m).astype(np.float32)
    doc = Doctor(D)
    cur = doc.soft(D)
    
    m2, ink2, soft2, rep = J.run_join_engine(m, D, doc, ink_of, cur, 8.0, batch_mode=False)
    
    assert rep["batch_mode"] == False, "Batch mode should be disabled"
    print("✓ Backward compatibility test passed")


if __name__ == "__main__":
    try:
        test_single_join_100_percent()
        test_two_joins_100_percent()
        test_four_joins_100_percent()
        test_batch_mode_off()
        print("\n✅ ALL BATCH JOIN FIX TESTS PASSED!")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
