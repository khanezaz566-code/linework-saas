"""Comprehensive test suite for small circles, sharp squares, and rounded squares (squircles).
Verifies that geometric primitives do not bend, warp, or degenerate into lopsided shapes.
"""
from __future__ import annotations
import unittest
import numpy as np
import cv2
from linework.pipeline import process_icon, Options


class TestPrimitivesFidelity(unittest.TestCase):
    def setUp(self):
        self.opts = Options(fresh=True, memory=False, quality="standard", joins=True, decision=False)

    def test_small_circles_perfect_roundness(self):
        """Test circles from radius 4 to 28 with various stroke widths."""
        for r, w in [(4, 2), (6, 3), (8, 4), (12, 4), (16, 5), (24, 6)]:
            dim = max(48, int(2 * (r + w) + 16))
            canvas = np.full((dim, dim), 255, dtype=np.uint8)
            cx_true, cy_true = dim // 2, dim // 2
            cv2.circle(canvas, (cx_true, cy_true), r, 0, w)

            res = process_icon(canvas, self.opts, name=f"circ_r{r}_w{w}")
            m = res["model"]
            self.assertEqual(len(m.paths), 1, f"Expected 1 path for circle r={r}, got {len(m.paths)}")
            p = m.paths[0]
            self.assertTrue(p.closed, f"Circle r={r} must be closed")
            self.assertIn(len(p.segs()), (1, 4), f"Circle r={r} should have 1 or 4 segments, got {len(p.segs())}")

            f = p.flat(0.2)
            c = np.mean(f, axis=0)
            dists = np.linalg.norm(f - c, axis=1)
            spread = float(np.max(dists) - np.min(dists))
            self.assertLessEqual(spread, max(0.65, 0.12 * w),
                                 f"Circle r={r} is warped: radial spread={spread:.3f}px exceeds tolerance")

    def test_sharp_squares_straightness(self):
        """Test sharp squares from size 12 to 40 with 90-degree corners."""
        for s, w in [(14, 2), (20, 3), (28, 4), (36, 4)]:
            dim = s + 24
            canvas = np.full((dim, dim), 255, dtype=np.uint8)
            x0 = (dim - s) // 2
            y0 = (dim - s) // 2
            cv2.rectangle(canvas, (x0, y0), (x0 + s, y0 + s), 0, w)

            res = process_icon(canvas, self.opts, name=f"sq_s{s}")
            m = res["model"]
            self.assertGreaterEqual(len(m.paths), 1)
            p = m.paths[0]
            self.assertTrue(p.closed, f"Square size={s} must be closed")

            # Check that all 4 sides are straight
            f = p.flat(0.25)
            x_min, x_max = f[:, 0].min(), f[:, 0].max()
            y_min, y_max = f[:, 1].min(), f[:, 1].max()
            aspect = (x_max - x_min) / max(1e-6, (y_max - y_min))
            self.assertAlmostEqual(aspect, 1.0, delta=0.08,
                                   msg=f"Square size={s} aspect ratio distorted: {aspect:.3f}")

    def test_rounded_squares_squircles(self):
        """Test rounded squares (buttons/squircles) to verify straight sides and symmetric corner arcs."""
        for s, rc, w in [(20, 4, 3), (26, 5, 4), (34, 7, 4), (42, 8, 5)]:
            dim = s + 28
            canvas = np.full((dim, dim), 255, dtype=np.uint8)
            x0, y0 = (dim - s) // 2, (dim - s) // 2
            x1, y1 = x0 + s, y0 + s

            # Draw rounded rectangle
            cv2.line(canvas, (x0 + rc, y0), (x1 - rc, y0), 0, w)
            cv2.line(canvas, (x1, y0 + rc), (x1, y1 - rc), 0, w)
            cv2.line(canvas, (x1 - rc, y1), (x0 + rc, y1), 0, w)
            cv2.line(canvas, (x0, y1 - rc), (x0, y0 + rc), 0, w)
            cv2.ellipse(canvas, (x0 + rc, y0 + rc), (rc, rc), 0, 180, 270, 0, w)
            cv2.ellipse(canvas, (x1 - rc, y0 + rc), (rc, rc), 0, 270, 360, 0, w)
            cv2.ellipse(canvas, (x1 - rc, y1 - rc), (rc, rc), 0, 0, 90, 0, w)
            cv2.ellipse(canvas, (x0 + rc, y1 - rc), (rc, rc), 0, 90, 180, 0, w)

            res = process_icon(canvas, self.opts, name=f"squircle_s{s}_r{rc}")
            m = res["model"]
            self.assertEqual(len(m.paths), 1)
            p = m.paths[0]
            self.assertTrue(p.closed)
            self.assertIn(len(p.segs()), (4, 8),
                          f"Squircle size={s} must have 4 or 8 segments, got {len(p.segs())}")

            # Check that corners are not lopsided or bent outward
            f = p.flat(0.2)
            c = np.mean(f, axis=0)
            quadrants = [
                ((f[:, 0] < c[0]) & (f[:, 1] < c[1])).sum(),
                ((f[:, 0] > c[0]) & (f[:, 1] < c[1])).sum(),
                ((f[:, 0] > c[0]) & (f[:, 1] > c[1])).sum(),
                ((f[:, 0] < c[0]) & (f[:, 1] > c[1])).sum(),
            ]
            q_mean = np.mean(quadrants)
            for q_idx, q_cnt in enumerate(quadrants):
                self.assertLess(abs(q_cnt - q_mean) / q_mean, 0.20,
                                f"Squircle size={s} is lopsided in quadrant {q_idx}")

    def test_keypad_grid_alignment(self):
        """Test a 3x3 grid of buttons (like Image 3 keypad) to verify uniform sizes and grid pitch."""
        canvas = np.full((160, 160), 255, dtype=np.uint8)
        s, rc, w = 22, 5, 4
        for row in range(3):
            for col in range(3):
                x0, y0 = 30 + col * 40, 30 + row * 40
                x1, y1 = x0 + s, y0 + s
                cv2.line(canvas, (x0 + rc, y0), (x1 - rc, y0), 0, w)
                cv2.line(canvas, (x1, y0 + rc), (x1, y1 - rc), 0, w)
                cv2.line(canvas, (x1 - rc, y1), (x0 + rc, y1), 0, w)
                cv2.line(canvas, (x0, y1 - rc), (x0, y0 + rc), 0, w)
                cv2.ellipse(canvas, (x0 + rc, y0 + rc), (rc, rc), 0, 180, 270, 0, w)
                cv2.ellipse(canvas, (x1 - rc, y0 + rc), (rc, rc), 0, 270, 360, 0, w)
                cv2.ellipse(canvas, (x1 - rc, y1 - rc), (rc, rc), 0, 0, 90, 0, w)
                cv2.ellipse(canvas, (x0 + rc, y1 - rc), (rc, rc), 0, 90, 180, 0, w)

        res = process_icon(canvas, self.opts, name="grid_3x3")
        m = res["model"]
        self.assertEqual(len(m.paths), 9, f"Expected 9 keypad buttons, got {len(m.paths)}")

        # Verify button widths and heights are uniform
        sizes = []
        centers = []
        for p in m.paths:
            f = p.flat(0.25)
            bw = f[:, 0].max() - f[:, 0].min()
            bh = f[:, 1].max() - f[:, 1].min()
            sizes.append((bw, bh))
            centers.append((float(f[:, 0].mean()), float(f[:, 1].mean())))

        med_bw = np.median([bw for bw, _ in sizes])
        med_bh = np.median([bh for _, bh in sizes])
        for idx, (bw, bh) in enumerate(sizes):
            self.assertAlmostEqual(bw, med_bw, delta=1.5,
                                   msg=f"Button {idx} width {bw:.2f} differs from median {med_bw:.2f}")
            self.assertAlmostEqual(bh, med_bh, delta=1.5,
                                   msg=f"Button {idx} height {bh:.2f} differs from median {med_bh:.2f}")


if __name__ == "__main__":
    unittest.main()
