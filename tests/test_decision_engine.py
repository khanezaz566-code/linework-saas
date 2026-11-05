import os; os.environ["LINEWORK_MEMORY"] = "0"
import sys, unittest
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linework.model import Model, Path
from linework.render import render_gray
from linework import decision as DC
from linework.pipeline import Options, process_icon
from linework import setlevel as SL


def make_synthetic():
    W, H = 250, 200
    p_rect_ideal = Path(
        A=[[30, 30], [90, 30], [90, 90], [30, 90], [30, 30]],
        Hin=[[30, 30], [70, 30], [90, 70], [50, 90], [30, 70]],
        Hout=[[50, 30], [90, 50], [70, 90], [30, 70], [30, 30]],
        w=6.0, join="miter", ml=4.0, closed=True
    )
    r = 25.0
    cx, cy = 160.0, 60.0
    k = 4.0 * (np.sqrt(2.0) - 1.0) / 3.0 * r
    p_circ_ideal = Path(
        A=[[cx + r, cy], [cx, cy + r], [cx - r, cy], [cx, cy - r], [cx + r, cy]],
        Hin=[[cx + r, cy - k], [cx + k, cy + r], [cx - r, cy + k], [cx - k, cy - r], [cx + r, cy - k]],
        Hout=[[cx + r, cy + k], [cx - k, cy + r], [cx - r, cy - k], [cx + k, cy - r], [cx + r, cy + k]],
        w=6.0, join="round", closed=True
    )
    p_arrow_ideal = Path(
        A=[[95, 120], [125, 160], [155, 120]],
        Hin=[[95, 120], [105, 133.3], [145, 146.7]],
        Hout=[[105, 133.3], [145, 146.7], [155, 120]],
        w=6.0, join="miter", ml=8.0, closed=False
    )
    m_ideal = Model([p_rect_ideal, p_circ_ideal, p_arrow_ideal], W, H)
    g_ideal = render_gray(m_ideal.svg(), W, H)
    D = (255 - g_ideal.astype(np.float32)) / 255.0
    
    A_rect = np.array([[30.0, 29.5], [90.0, 30.5], [90.0, 90.0], [30.0, 90.0], [30.0, 29.5]])
    Hin_rect = np.array([[30.0, 29.5], [70.0, 30.5], [90.6, 70.0], [50.0, 90.6], [29.4, 70.0]])
    Hout_rect = np.array([[50.0, 29.5], [90.6, 50.0], [70.0, 90.6], [29.4, 70.0], [30.0, 29.5]])
    p_rect_defected = Path(A_rect, Hin_rect, Hout_rect, 6.0, join="round", ml=4.0, closed=True)
    
    A_circ = np.array([[cx + r, cy], [cx, cy + r], [cx - r, cy], [cx, cy - r], [cx + r, cy]])
    Hin_circ = np.array([[cx + r + 0.3, cy - k], [cx + k, cy + r + 0.3], [cx - r - 0.3, cy + k], [cx - k, cy - r - 0.3], [cx + r + 0.3, cy - k]])
    Hout_circ = np.array([[cx + r + 0.3, cy + k], [cx - k, cy + r + 0.3], [cx - r - 0.3, cy - k], [cx + k, cy - r - 0.3], [cx + r + 0.3, cy + k]])
    p_circ_defected = Path(A_circ, Hin_circ, Hout_circ, 6.0, join="round", closed=True)
    
    p_arrow_defected = Path(
        A=[[95, 120], [125, 160], [155, 120]],
        Hin=[[95, 120], [105, 133.3], [145, 146.7]],
        Hout=[[105, 133.3], [145, 146.7], [155, 120]],
        w=6.0, join="round", ml=4.0, closed=False
    )
    m_defected = Model([p_rect_defected, p_circ_defected, p_arrow_defected], W, H)
    return m_defected, D


class TestDecisionEngine(unittest.TestCase):
    def test_unit_synthetic(self):
        """Test 1: decide_best on synthetic icon must produce hard <= 3 and open == 0."""
        m_in, D = make_synthetic()
        m_out, rep = DC.decide_best(m_in, D, time_budget=30)
        after = rep["after"]
        self.assertLessEqual(after["hard"], 3, f"Expected hard <= 3, got {after['hard']}")
        self.assertEqual(rep["open"], 0, f"Expected open == 0, got {rep['open']}")

    def test_gate_escalation(self):
        """Test 4: Corrupt one icon's model, verify sheet gate escalates, keeps best, flags review, outputs valid SVG."""
        W, H = 200, 200
        p1 = Path(A=[[30, 30], [170, 30], [170, 170], [30, 170], [30, 30]],
                  Hin=[[30, 30], [30, 30], [170, 30], [170, 170], [30, 170]],
                  Hout=[[170, 30], [170, 170], [30, 170], [30, 30], [30, 30]],
                  w=8.0, join="miter", closed=True)
        p2 = Path(A=[[60, 60], [140, 140]],
                  Hin=[[60, 60], [100, 100]],
                  Hout=[[100, 100], [140, 140]],
                  w=6.0, join="round", closed=False)
        orig_model = Model([p1, p2], W, H)
        g = render_gray(orig_model.svg(), W, H)
        crop = g
        opts = Options(quality="fast", fresh=True, memory=False)
        
        corrupted_model = Model([p2], W, H)
        corrupted_metrics = {
            "clean": False,
            "needs_review": True,
            "hard": 500,
            "open": 2,
            "iou": 0.40,
            "decision": {
                "after": {"hard": 500, "iou": 0.40},
                "open": 2,
                "open_findings": [{"kind": "miss", "sev": 500, "why": "missing outer rect"}]
            }
        }
        
        m_esc, met_esc = SL.escalate_weak_icon(
            crop, (0, 0), opts,
            corrupted_model, corrupted_metrics,
            name="test_icon"
        )
        self.assertLess(SL.result_key(m_esc, met_esc), SL.result_key(corrupted_model, corrupted_metrics))
        self.assertGreaterEqual(len(m_esc.paths), 1)
        
        allm = Model([], W, H)
        allm.paths.extend(m_esc.paths)
        svg = allm.svg()
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertGreater(len(svg), 50)


if __name__ == '__main__':
    unittest.main()
