import os; os.environ["LINEWORK_MEMORY"] = "0"
"""Quality must not depend on machine load or queue position: the Edit budget is CPU time, not wall-clock."""
import sys, time, numpy as np, cv2
sys.path.insert(0, '.')
import linework.pipeline as P


def icon():
    g = np.full((200, 200), 255, np.uint8)
    cv2.circle(g, (100, 100), 60, 0, 8, cv2.LINE_AA)
    cv2.line(g, (40, 40), (160, 160), 0, 8, cv2.LINE_AA)
    return g


def test_same_result_when_wall_clock_is_slow():
    a = P.process_icon(icon(), P.Options(quality="standard"), name="a")["metrics"]
    real = time.time
    tick = [0.0]

    def slow():
        tick[0] += 3.0  # pretend the machine is crawling: every clock read costs 3 "seconds" of wall time
        return real() + tick[0]

    P.time.time = slow
    try:
        b = P.process_icon(icon(), P.Options(quality="standard"), name="b")["metrics"]
    finally:
        P.time.time = real
    assert abs(a["iou"] - b["iou"]) < 1e-9 and a["paths"] == b["paths"] and a["nodes"] == b["nodes"]

if __name__ == "__main__":
    test_same_result_when_wall_clock_is_slow(); print("ok")
