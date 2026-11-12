"""Fused-disc detector: finds the pin-1 style discs fused to strokes, never invents one on plain strokes / squares / rings."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2, numpy as np
from linework.trace import ink_map, find_fused_discs
from linework.split import estimate_width


def _detect(img):
    D = ink_map(img)
    return find_fused_discs(D, estimate_width(D))


def test_disc_fused_to_a_corner_is_found():
    c = np.full((240, 240), 255, np.uint8)
    cv2.rectangle(c, (40, 40), (200, 200), 0, 10, cv2.LINE_AA)
    cv2.circle(c, (58, 58), 15, 0, -1, cv2.LINE_AA)   # solid pin-1 disc fused to the inner corner
    d = _detect(c)
    assert len(d) == 1, d
    cx, cy, R = d[0]
    assert abs(cx - 58) < 2.5 and abs(cy - 58) < 2.5 and abs(R - 15) < 2.5, d


def test_lollipop_and_node_discs():
    c = np.full((240, 240), 255, np.uint8)
    cv2.line(c, (30, 120), (210, 120), 0, 8, cv2.LINE_AA)
    cv2.circle(c, (120, 120), 17, 0, -1, cv2.LINE_AA)
    assert len(_detect(c)) == 1


def test_plain_strokes_rings_squares_have_no_false_discs():
    c = np.full((240, 240), 255, np.uint8)
    cv2.rectangle(c, (40, 40), (200, 200), 0, 10, cv2.LINE_AA)
    cv2.line(c, (40, 120), (200, 120), 0, 10, cv2.LINE_AA)     # +-junctions
    cv2.line(c, (120, 40), (120, 200), 0, 10, cv2.LINE_AA)
    cv2.circle(c, (120, 120), 50, 0, 10, cv2.LINE_AA)           # ring
    assert _detect(c) == []
    s = np.full((240, 240), 255, np.uint8)
    cv2.rectangle(s, (60, 60), (95, 95), 0, -1)                  # small solid square block fused to a bar
    cv2.line(s, (30, 78), (210, 78), 0, 10)
    assert _detect(s) == []


def test_no_disc_on_the_heavy_join_drawers():
    from tests.make_heavy_joins_sheet import HEAVY_JOIN_DRAWERS
    from tests.more_complex_drawers import MORE_COMPLEX_DRAWERS
    hits = {}
    for d in HEAVY_JOIN_DRAWERS + MORE_COMPLEX_DRAWERS:
        c = np.full((200, 200), 255, np.uint8)
        d(c, 100, 100, sw=6, seed=13)
        n = len(_detect(c))
        if n:
            hits[d.__name__] = n
    print("drawers with fused discs:", hits)
    assert hits  # A/B quality of these detections lives in tests/ab_fused_discs.py


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
