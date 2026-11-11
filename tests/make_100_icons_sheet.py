"""Script to generate a 100-icon monoline presentation sheet (10x10 grid).
Creates 100 unique, realistic icons covering UI, commerce, devices, media, tools, navigation, and security.
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
import cv2

def create_100_icons_sheet(output_path: str = "tests/sheet_100_icons.png"):
    ROWS, COLS = 10, 10
    CELL_W, CELL_H = 180, 180
    PAD = 40
    W = COLS * CELL_W + 2 * PAD
    H = ROWS * CELL_H + 2 * PAD
    SW = 6

    # White canvas
    canvas = np.full((H, W), 255, dtype=np.uint8)

    def pt(cx, cy, dx, dy):
        return (int(round(cx + dx)), int(round(cy + dy)))

    def line(pts, closed=False):
        for i in range(len(pts) - (0 if closed else 1)):
            p0 = pts[i]
            p1 = pts[(i + 1) % len(pts)]
            cv2.line(canvas, p0, p1, 0, SW, cv2.LINE_AA)

    def circle(cx, cy, r):
        cv2.circle(canvas, (int(round(cx)), int(round(cy))), int(round(r)), 0, SW, cv2.LINE_AA)

    def arc(cx, cy, r, a0, a1):
        cv2.ellipse(canvas, (int(round(cx)), int(round(cy))), (int(round(r)), int(round(r))), 0, a0, a1, 0, SW, cv2.LINE_AA)

    def rrect(x0, y0, x1, y1, r):
        r = min(r, abs(x1 - x0) // 2, abs(y1 - y0) // 2)
        cv2.line(canvas, (x0 + r, y0), (x1 - r, y0), 0, SW, cv2.LINE_AA)
        cv2.line(canvas, (x1, y0 + r), (x1, y1 - r), 0, SW, cv2.LINE_AA)
        cv2.line(canvas, (x1 - r, y1), (x0 + r, y1), 0, SW, cv2.LINE_AA)
        cv2.line(canvas, (x0, y1 - r), (x0, y0 + r), 0, SW, cv2.LINE_AA)
        cv2.ellipse(canvas, (x0 + r, y0 + r), (r, r), 0, 180, 270, 0, SW, cv2.LINE_AA)
        cv2.ellipse(canvas, (x1 - r, y0 + r), (r, r), 0, 270, 360, 0, SW, cv2.LINE_AA)
        cv2.ellipse(canvas, (x1 - r, y1 - r), (r, r), 0, 0, 90, 0, SW, cv2.LINE_AA)
        cv2.ellipse(canvas, (x0 + r, y1 - r), (r, r), 0, 90, 180, 0, SW, cv2.LINE_AA)

    for idx in range(100):
        r_idx = idx // COLS
        c_idx = idx % COLS
        cx = PAD + c_idx * CELL_W + CELL_W // 2
        cy = PAD + r_idx * CELL_H + CELL_H // 2

        # Draw icon based on index
        if idx == 0:  # 1. Home
            line([pt(cx, cy, -45, 0), pt(cx, cy, 0, -42), pt(cx, cy, 45, 0)])
            line([pt(cx, cy, -34, -7), pt(cx, cy, -34, 42), pt(cx, cy, 34, 42), pt(cx, cy, 34, -7)])
            line([pt(cx, cy, -11, 42), pt(cx, cy, -11, 15), pt(cx, cy, 11, 15), pt(cx, cy, 11, 42)])
        elif idx == 1:  # 2. Search
            circle(cx - 8, cy - 8, 30)
            line([pt(cx, cy, 14, 14), pt(cx, cy, 42, 42)])
        elif idx == 2:  # 3. User
            circle(cx, cy - 20, 20)
            arc(cx, cy + 52, 42, 195, 345)
        elif idx == 3:  # 4. Users
            circle(cx - 15, cy - 18, 16)
            arc(cx - 15, cy + 44, 34, 200, 340)
            circle(cx + 18, cy - 18, 13)
            arc(cx + 18, cy + 44, 28, 260, 340)
        elif idx == 4:  # 5. Heart
            # Polygons/curves
            pts = []
            for t_deg in range(0, 360, 6):
                t = math.radians(t_deg)
                x = 16 * (math.sin(t) ** 3)
                y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
                pts.append(pt(cx, cy, x * 2.2, y * 2.2 - 5))
            line(pts, closed=True)
        elif idx == 5:  # 6. Star
            pts = []
            for i in range(10):
                r = 42 if i % 2 == 0 else 18
                ang = math.radians(-90 + i * 36)
                pts.append(pt(cx, cy, r * math.cos(ang), r * math.sin(ang)))
            line(pts, closed=True)
        elif idx == 6:  # 7. Mail
            rrect(cx - 45, cy - 30, cx + 45, cy + 30, 8)
            line([pt(cx, cy, -44, -24), pt(cx, cy, 0, 8), pt(cx, cy, 44, -24)])
        elif idx == 7:  # 8. Bell
            arc(cx, cy - 5, 26, 180, 360)
            line([pt(cx, cy, -26, -5), pt(cx, cy, -35, 25), pt(cx, cy, 35, 25), pt(cx, cy, 26, -5)])
            circle(cx, cy + 32, 6)
        elif idx == 8:  # 9. Lock
            rrect(cx - 32, cy - 8, cx + 32, cy + 40, 6)
            arc(cx, cy - 8, 20, 180, 360)
            circle(cx, cy + 12, 5)
            line([pt(cx, cy, 0, 17), pt(cx, cy, 0, 26)])
        elif idx == 9:  # 10. Key
            circle(cx - 20, cy, 18)
            line([pt(cx, cy, -2, 0), pt(cx, cy, 42, 0)])
            line([pt(cx, cy, 28, 0), pt(cx, cy, 28, 14)])
            line([pt(cx, cy, 38, 0), pt(cx, cy, 38, 10)])
        elif idx == 10:  # 11. Settings Gear
            circle(cx, cy, 22)
            for a in range(0, 360, 45):
                rad = math.radians(a)
                line([pt(cx, cy, 22 * math.cos(rad), 22 * math.sin(rad)),
                      pt(cx, cy, 36 * math.cos(rad), 36 * math.sin(rad))])
        elif idx == 11:  # 12. Compass
            circle(cx, cy, 38)
            line([pt(cx, cy, 0, -28), pt(cx, cy, 10, 0), pt(cx, cy, 0, 28), pt(cx, cy, -10, 0)], closed=True)
        elif idx == 12:  # 13. Globe
            circle(cx, cy, 38)
            line([pt(cx, cy, -38, 0), pt(cx, cy, 38, 0)])
            cv2.ellipse(canvas, (cx, cy), (18, 38), 0, 0, 360, 0, SW, cv2.LINE_AA)
        elif idx == 13:  # 14. Menu Hamburger
            line([pt(cx, cy, -34, -20), pt(cx, cy, 34, -20)])
            line([pt(cx, cy, -34, 0), pt(cx, cy, 34, 0)])
            line([pt(cx, cy, -34, 20), pt(cx, cy, 34, 20)])
        elif idx == 14:  # 15. Grid
            for dx in (-24, 0, 24):
                for dy in (-24, 0, 24):
                    circle(cx + dx, cy + dy, 4)
        elif idx == 15:  # 16. Sliders
            for dx in (-26, 0, 26):
                line([pt(cx, cy, dx, -35), pt(cx, cy, dx, 35)])
            circle(cx - 26, cy - 12, 7)
            circle(cx, cy + 14, 7)
            circle(cx + 26, cy - 4, 7)
        elif idx == 16:  # 17. Power
            arc(cx, cy + 4, 32, 130, 410)
            line([pt(cx, cy, 0, -34), pt(cx, cy, 0, -2)])
        elif idx == 17:  # 18. Pin
            circle(cx, cy - 12, 18)
            line([pt(cx, cy, -12, 0), pt(cx, cy, 0, 42), pt(cx, cy, 12, 0)])
            circle(cx, cy - 12, 6)
        elif idx == 18:  # 19. Bookmark
            line([pt(cx, cy, -25, -40), pt(cx, cy, 25, -40), pt(cx, cy, 25, 40), pt(cx, cy, 0, 18), pt(cx, cy, -25, 40)], closed=True)
        elif idx == 19:  # 20. Tag
            line([pt(cx, cy, -36, 12), pt(cx, cy, -12, 36), pt(cx, cy, 36, -12), pt(cx, cy, 36, -36), pt(cx, cy, 12, -36)], closed=True)
            circle(cx + 20, cy - 20, 5)
        elif idx == 20:  # 21. Trash
            line([pt(cx, cy, -40, -25), pt(cx, cy, 40, -25)])
            line([pt(cx, cy, -15, -25), pt(cx, cy, -15, -34), pt(cx, cy, 15, -34), pt(cx, cy, 15, -25)])
            line([pt(cx, cy, -30, -25), pt(cx, cy, -24, 38), pt(cx, cy, 24, 38), pt(cx, cy, 30, -25)])
            line([pt(cx, cy, -10, -15), pt(cx, cy, -8, 28)])
            line([pt(cx, cy, 10, -15), pt(cx, cy, 8, 28)])
        elif idx == 21:  # 22. Edit Pencil
            line([pt(cx, cy, -32, 32), pt(cx, cy, -14, 36), pt(cx, cy, 28, -6), pt(cx, cy, 10, -24), pt(cx, cy, -32, 18)], closed=True)
            line([pt(cx, cy, -32, 32), pt(cx, cy, -22, 22)])
        elif idx == 22:  # 23. Copy
            rrect(cx - 30, cy - 15, cx + 18, cy + 38, 5)
            line([pt(cx, cy, -18, -15), pt(cx, cy, -18, -35), pt(cx, cy, 32, -35), pt(cx, cy, 32, 18), pt(cx, cy, 18, 18)])
        elif idx == 23:  # 24. Scissors
            circle(cx - 24, cy + 22, 12)
            circle(cx + 24, cy + 22, 12)
            line([pt(cx, cy, -16, 12), pt(cx, cy, 30, -34)])
            line([pt(cx, cy, 16, 12), pt(cx, cy, -30, -34)])
        elif idx == 24:  # 25. Share
            circle(cx - 24, cy, 10)
            circle(cx + 24, cy - 22, 10)
            circle(cx + 24, cy + 22, 10)
            line([pt(cx, cy, -15, -4), pt(cx, cy, 15, -18)])
            line([pt(cx, cy, -15, 4), pt(cx, cy, 15, 18)])
        elif idx == 25:  # 26. Download
            line([pt(cx, cy, 0, -35), pt(cx, cy, 0, 16)])
            line([pt(cx, cy, -18, -2), pt(cx, cy, 0, 16), pt(cx, cy, 18, -2)])
            line([pt(cx, cy, -35, 16), pt(cx, cy, -35, 36), pt(cx, cy, 35, 36), pt(cx, cy, 35, 16)])
        elif idx == 26:  # 27. Upload
            line([pt(cx, cy, 0, 16), pt(cx, cy, 0, -35)])
            line([pt(cx, cy, -18, -17), pt(cx, cy, 0, -35), pt(cx, cy, 18, -17)])
            line([pt(cx, cy, -35, 16), pt(cx, cy, -35, 36), pt(cx, cy, 35, 36), pt(cx, cy, 35, 16)])
        elif idx == 27:  # 28. External Link
            line([pt(cx, cy, 5, -34), pt(cx, cy, -34, -34), pt(cx, cy, -34, 34), pt(cx, cy, 34, 34), pt(cx, cy, 34, -5)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 34, -34)])
            line([pt(cx, cy, 16, -34), pt(cx, cy, 34, -34), pt(cx, cy, 34, -16)])
        elif idx == 28:  # 29. Eye
            arc(cx, cy + 24, 46, 210, 330)
            arc(cx, cy - 24, 46, 30, 150)
            circle(cx, cy, 12)
        elif idx == 29:  # 30. Eye Off
            arc(cx, cy + 24, 46, 210, 330)
            arc(cx, cy - 24, 46, 30, 150)
            circle(cx, cy, 12)
            line([pt(cx, cy, -38, -32), pt(cx, cy, 38, 32)])
        elif idx == 30:  # 31. Help Circle
            circle(cx, cy, 38)
            arc(cx, cy - 14, 12, 180, 360)
            line([pt(cx, cy, 12, -14), pt(cx, cy, 0, 0), pt(cx, cy, 0, 12)])
            circle(cx, cy + 24, 2)
        elif idx == 31:  # 32. Info Circle
            circle(cx, cy, 38)
            line([pt(cx, cy, 0, -6), pt(cx, cy, 0, 20)])
            line([pt(cx, cy, -8, -6), pt(cx, cy, 0, -6)])
            circle(cx, cy - 18, 3)
        elif idx == 32:  # 33. Alert Triangle
            line([pt(cx, cy, -38, 32), pt(cx, cy, 0, -36), pt(cx, cy, 38, 32)], closed=True)
            line([pt(cx, cy, 0, -14), pt(cx, cy, 0, 10)])
            circle(cx, cy + 22, 3)
        elif idx == 33:  # 34. Check Circle
            circle(cx, cy, 38)
            line([pt(cx, cy, -18, 0), pt(cx, cy, -4, 14), pt(cx, cy, 20, -12)])
        elif idx == 34:  # 35. Close Cross
            line([pt(cx, cy, -26, -26), pt(cx, cy, 26, 26)])
            line([pt(cx, cy, 26, -26), pt(cx, cy, -26, 26)])
        elif idx == 35:  # 36. Plus Circle
            circle(cx, cy, 38)
            line([pt(cx, cy, -20, 0), pt(cx, cy, 20, 0)])
            line([pt(cx, cy, 0, -20), pt(cx, cy, 0, 20)])
        elif idx == 36:  # 37. Minus Circle
            circle(cx, cy, 38)
            line([pt(cx, cy, -20, 0), pt(cx, cy, 20, 0)])
        elif idx == 37:  # 38. Arrow Up
            line([pt(cx, cy, 0, 32), pt(cx, cy, 0, -32)])
            line([pt(cx, cy, -22, -10), pt(cx, cy, 0, -32), pt(cx, cy, 22, -10)])
        elif idx == 38:  # 39. Arrow Down
            line([pt(cx, cy, 0, -32), pt(cx, cy, 0, 32)])
            line([pt(cx, cy, -22, 10), pt(cx, cy, 0, 32), pt(cx, cy, 22, 10)])
        elif idx == 39:  # 40. Arrow Left
            line([pt(cx, cy, 32, 0), pt(cx, cy, -32, 0)])
            line([pt(cx, cy, -10, -22), pt(cx, cy, -32, 0), pt(cx, cy, -10, 22)])
        elif idx == 40:  # 41. Arrow Right
            line([pt(cx, cy, -32, 0), pt(cx, cy, 32, 0)])
            line([pt(cx, cy, 10, -22), pt(cx, cy, 32, 0), pt(cx, cy, 10, 22)])
        elif idx == 41:  # 42. Refresh
            arc(cx, cy, 30, 30, 200)
            line([pt(cx, cy, -32, 5), pt(cx, cy, -30, -10), pt(cx, cy, -16, -4)])
            arc(cx, cy, 30, 210, 380)
            line([pt(cx, cy, 32, -5), pt(cx, cy, 30, 10), pt(cx, cy, 16, 4)])
        elif idx == 42:  # 43. Repeat
            line([pt(cx, cy, -32, -10), pt(cx, cy, -32, -22), pt(cx, cy, 26, -22)])
            line([pt(cx, cy, 14, -32), pt(cx, cy, 26, -22), pt(cx, cy, 14, -12)])
            line([pt(cx, cy, 32, 10), pt(cx, cy, 32, 22), pt(cx, cy, -26, 22)])
            line([pt(cx, cy, -14, 12), pt(cx, cy, -26, 22), pt(cx, cy, -14, 32)])
        elif idx == 43:  # 44. Shuffle
            line([pt(cx, cy, -32, -20), pt(cx, cy, -10, -20), pt(cx, cy, 10, 20), pt(cx, cy, 32, 20)])
            line([pt(cx, cy, 22, 10), pt(cx, cy, 32, 20), pt(cx, cy, 22, 30)])
            line([pt(cx, cy, -32, 20), pt(cx, cy, -10, 20), pt(cx, cy, 10, -20), pt(cx, cy, 32, -20)])
            line([pt(cx, cy, 22, -30), pt(cx, cy, 32, -20), pt(cx, cy, 22, -10)])
        elif idx == 44:  # 45. Chat Bubble
            rrect(cx - 36, cy - 30, cx + 36, cy + 20, 8)
            line([pt(cx, cy, -20, 20), pt(cx, cy, -30, 38), pt(cx, cy, -2, 20)])
        elif idx == 45:  # 46. Message Dots
            rrect(cx - 36, cy - 30, cx + 36, cy + 20, 8)
            line([pt(cx, cy, -20, 20), pt(cx, cy, -30, 38), pt(cx, cy, -2, 20)])
            circle(cx - 16, cy - 5, 4)
            circle(cx, cy - 5, 4)
            circle(cx + 16, cy - 5, 4)
        elif idx == 46:  # 47. Phone
            rrect(cx - 30, cy - 30, cx - 14, cy - 8, 4)
            rrect(cx + 14, cy + 8, cx + 30, cy + 30, 4)
            arc(cx, cy, 34, 20, 160)
        elif idx == 47:  # 48. Video Camera
            rrect(cx - 38, cy - 24, cx + 14, cy + 24, 6)
            line([pt(cx, cy, 14, -8), pt(cx, cy, 38, -24), pt(cx, cy, 38, 24), pt(cx, cy, 14, 8)], closed=True)
        elif idx == 48:  # 49. Microphone
            rrect(cx - 14, cy - 34, cx + 14, cy + 6, 12)
            arc(cx, cy - 4, 24, 0, 180)
            line([pt(cx, cy, 0, 20), pt(cx, cy, 0, 38)])
            line([pt(cx, cy, -18, 38), pt(cx, cy, 18, 38)])
        elif idx == 49:  # 50. Megaphone
            line([pt(cx, cy, -34, -12), pt(cx, cy, 12, -30), pt(cx, cy, 12, 30), pt(cx, cy, -34, 12)], closed=True)
            line([pt(cx, cy, -12, 17), pt(cx, cy, -12, 38), pt(cx, cy, -2, 38), pt(cx, cy, -2, 22)])
            arc(cx + 12, cy, 18, -40, 40)
            arc(cx + 12, cy, 28, -45, 45)
        elif idx == 50:  # 51. Send Paper Plane
            line([pt(cx, cy, -34, 30), pt(cx, cy, -14, -30), pt(cx, cy, 38, -34), pt(cx, cy, 8, 38)], closed=True)
            line([pt(cx, cy, 38, -34), pt(cx, cy, -4, 10)])
        elif idx == 51:  # 52. At Sign
            circle(cx, cy, 16)
            arc(cx, cy, 34, 45, 340)
            line([pt(cx, cy, 16, 0), pt(cx, cy, 16, 16)])
            arc(cx + 8, cy + 16, 8, 0, 180)
        elif idx == 52:  # 53. Hashtag
            line([pt(cx, cy, -34, -12), pt(cx, cy, 34, -12)])
            line([pt(cx, cy, -34, 12), pt(cx, cy, 34, 12)])
            line([pt(cx, cy, -10, -34), pt(cx, cy, -18, 34)])
            line([pt(cx, cy, 18, -34), pt(cx, cy, 10, 34)])
        elif idx == 53:  # 54. Thumbs Up
            line([pt(cx, cy, -34, -5), pt(cx, cy, -34, 32), pt(cx, cy, -14, 32), pt(cx, cy, -14, -5)], closed=True)
            line([pt(cx, cy, -14, 8), pt(cx, cy, 26, 8), pt(cx, cy, 34, -6), pt(cx, cy, 18, -6), pt(cx, cy, 18, -32), pt(cx, cy, 4, -32), pt(cx, cy, -14, -5)])
        elif idx == 54:  # 55. Flag
            line([pt(cx, cy, -30, -38), pt(cx, cy, -30, 38)])
            line([pt(cx, cy, -30, -36), pt(cx, cy, 28, -20), pt(cx, cy, -30, -4)])
        elif idx == 55:  # 56. Gift
            rrect(cx - 32, cy - 12, cx + 32, cy + 34, 4)
            rrect(cx - 36, cy - 24, cx + 36, cy - 12, 3)
            line([pt(cx, cy, 0, -24), pt(cx, cy, 0, 34)])
            arc(cx - 14, cy - 32, 12, 120, 360)
            arc(cx + 14, cy - 32, 12, 180, 420)
        elif idx == 56:  # 57. Award Badge
            circle(cx, cy - 8, 26)
            line([pt(cx, cy, -16, 14), pt(cx, cy, -26, 38), pt(cx, cy, -6, 30), pt(cx, cy, 0, 18)])
            line([pt(cx, cy, 16, 14), pt(cx, cy, 26, 38), pt(cx, cy, 6, 30), pt(cx, cy, 0, 18)])
        elif idx == 57:  # 58. Music Note
            circle(cx - 20, cy + 18, 10)
            circle(cx + 18, cy + 8, 10)
            line([pt(cx, cy, -10, 18), pt(cx, cy, -10, -26), pt(cx, cy, 28, -36), pt(cx, cy, 28, 8)])
            line([pt(cx, cy, -10, -14), pt(cx, cy, 28, -24)])
        elif idx == 58:  # 59. Headphones
            arc(cx, cy - 6, 34, 180, 360)
            rrect(cx - 38, cy - 6, cx - 24, cy + 26, 6)
            rrect(cx + 24, cy - 6, cx + 38, cy + 26, 6)
        elif idx == 59:  # 60. Camera
            rrect(cx - 40, cy - 22, cx + 40, cy + 30, 8)
            line([pt(cx, cy, -18, -22), pt(cx, cy, -12, -34), pt(cx, cy, 12, -34), pt(cx, cy, 18, -22)])
            circle(cx, cy + 4, 16)
        elif idx == 60:  # 61. Image Photo
            rrect(cx - 38, cy - 30, cx + 38, cy + 30, 6)
            circle(cx - 18, cy - 10, 6)
            line([pt(cx, cy, -38, 14), pt(cx, cy, -14, -6), pt(cx, cy, 10, 14), pt(cx, cy, 22, 6), pt(cx, cy, 38, 20)])
        elif idx == 61:  # 62. Play
            line([pt(cx, cy, -22, -30), pt(cx, cy, 30, 0), pt(cx, cy, -22, 30)], closed=True)
        elif idx == 62:  # 63. Pause
            line([pt(cx, cy, -12, -28), pt(cx, cy, -12, 28)])
            line([pt(cx, cy, 12, -28), pt(cx, cy, 12, 28)])
        elif idx == 63:  # 64. Stop
            rrect(cx - 26, cy - 26, cx + 26, cy + 26, 4)
        elif idx == 64:  # 65. Volume High
            line([pt(cx, cy, -34, -14), pt(cx, cy, -18, -14), pt(cx, cy, 2, -28), pt(cx, cy, 2, 28), pt(cx, cy, -18, 14), pt(cx, cy, -34, 14)], closed=True)
            arc(cx + 2, cy, 16, -45, 45)
            arc(cx + 2, cy, 28, -50, 50)
        elif idx == 65:  # 66. Volume Mute
            line([pt(cx, cy, -34, -14), pt(cx, cy, -18, -14), pt(cx, cy, 2, -28), pt(cx, cy, 2, 28), pt(cx, cy, -18, 14), pt(cx, cy, -34, 14)], closed=True)
            line([pt(cx, cy, 18, -10), pt(cx, cy, 34, 10)])
            line([pt(cx, cy, 34, -10), pt(cx, cy, 18, 10)])
        elif idx == 66:  # 67. Monitor
            rrect(cx - 42, cy - 34, cx + 42, cy + 18, 6)
            line([pt(cx, cy, 0, 18), pt(cx, cy, 0, 36)])
            line([pt(cx, cy, -20, 36), pt(cx, cy, 20, 36)])
        elif idx == 67:  # 68. Laptop
            rrect(cx - 36, cy - 30, cx + 36, cy + 14, 4)
            line([pt(cx, cy, -44, 26), pt(cx, cy, 44, 26)])
            line([pt(cx, cy, -36, 14), pt(cx, cy, -44, 26)])
            line([pt(cx, cy, 36, 14), pt(cx, cy, 44, 26)])
        elif idx == 68:  # 69. Smartphone
            rrect(cx - 24, cy - 40, cx + 24, cy + 40, 8)
            line([pt(cx, cy, -8, -32), pt(cx, cy, 8, -32)])
            circle(cx, cy + 30, 4)
        elif idx == 69:  # 70. Watch
            rrect(cx - 24, cy - 24, cx + 24, cy + 24, 8)
            line([pt(cx, cy, -14, -24), pt(cx, cy, -14, -40), pt(cx, cy, 14, -40), pt(cx, cy, 14, -24)])
            line([pt(cx, cy, -14, 24), pt(cx, cy, -14, 40), pt(cx, cy, 14, 40), pt(cx, cy, 14, 24)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 0, -12)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 8, 4)])
        elif idx == 70:  # 71. Battery Full
            rrect(cx - 36, cy - 20, cx + 30, cy + 20, 5)
            line([pt(cx, cy, 30, -8), pt(cx, cy, 35, -8), pt(cx, cy, 35, 8), pt(cx, cy, 30, 8)])
            line([pt(cx, cy, -24, -12), pt(cx, cy, -24, 12)])
            line([pt(cx, cy, -10, -12), pt(cx, cy, -10, 12)])
            line([pt(cx, cy, 4, -12), pt(cx, cy, 4, 12)])
            line([pt(cx, cy, 18, -12), pt(cx, cy, 18, 12)])
        elif idx == 71:  # 72. Charging Bolt
            line([pt(cx, cy, 6, -38), pt(cx, cy, -22, 2), pt(cx, cy, 2, 2), pt(cx, cy, -6, 38), pt(cx, cy, 22, -2), pt(cx, cy, -2, -2)], closed=True)
        elif idx == 72:  # 73. WiFi
            circle(cx, cy + 28, 4)
            arc(cx, cy + 28, 22, 215, 325)
            arc(cx, cy + 28, 40, 220, 320)
            arc(cx, cy + 28, 58, 225, 315)
        elif idx == 73:  # 74. Bluetooth
            line([pt(cx, cy, 0, -35), pt(cx, cy, 0, 35)])
            line([pt(cx, cy, -20, -18), pt(cx, cy, 18, 16), pt(cx, cy, 0, 32)])
            line([pt(cx, cy, -20, 18), pt(cx, cy, 18, -16), pt(cx, cy, 0, -32)])
        elif idx == 74:  # 75. Radio Tower
            line([pt(cx, cy, 0, -34), pt(cx, cy, -24, 38)])
            line([pt(cx, cy, 0, -34), pt(cx, cy, 24, 38)])
            line([pt(cx, cy, -12, 4), pt(cx, cy, 12, 4)])
            line([pt(cx, cy, -18, 22), pt(cx, cy, 18, 22)])
            circle(cx, cy - 34, 4)
            arc(cx, cy - 34, 18, 220, 320)
            arc(cx, cy - 34, 30, 225, 315)
        elif idx == 75:  # 76. Server
            for y_off in (-24, 0, 24):
                rrect(cx - 38, cy + y_off - 10, cx + 38, cy + y_off + 10, 5)
                circle(cx + 26, cy + y_off, 3)
                circle(cx + 16, cy + y_off, 3)
        elif idx == 76:  # 77. Database
            cv2.ellipse(canvas, (cx, cy - 22), (34, 12), 0, 0, 360, 0, SW, cv2.LINE_AA)
            line([pt(cx, cy, -34, -22), pt(cx, cy, -34, 22)])
            line([pt(cx, cy, 34, -22), pt(cx, cy, 34, 22)])
            arc(cx, cy, 34, 0, 180)
            arc(cx, cy + 22, 34, 0, 180)
        elif idx == 77:  # 78. Cloud
            arc(cx - 18, cy + 4, 18, 120, 280)
            arc(cx + 6, cy - 8, 24, 190, 360)
            arc(cx + 24, cy + 8, 14, 270, 420)
            line([pt(cx, cy, -26, 18), pt(cx, cy, 34, 18)])
        elif idx == 78:  # 79. CPU Chip
            rrect(cx - 26, cy - 26, cx + 26, cy + 26, 4)
            rrect(cx - 14, cy - 14, cx + 14, cy + 14, 2)
            for d_pin in (-16, 0, 16):
                line([pt(cx, cy, d_pin, -26), pt(cx, cy, d_pin, -36)])
                line([pt(cx, cy, d_pin, 26), pt(cx, cy, d_pin, 36)])
                line([pt(cx, cy, -26, d_pin), pt(cx, cy, -36, d_pin)])
                line([pt(cx, cy, 26, d_pin), pt(cx, cy, 36, d_pin)])
        elif idx == 79:  # 80. Keypad / Intercom
            rrect(cx - 38, cy - 42, cx + 38, cy + 42, 8)
            for ky in (-22, 0, 22):
                for kx in (-20, 0, 20):
                    rrect(cx + kx - 6, cy + ky - 6, cx + kx + 6, cy + ky + 6, 2)
        elif idx == 80:  # 81. Terminal
            rrect(cx - 40, cy - 30, cx + 40, cy + 30, 6)
            line([pt(cx, cy, -26, -12), pt(cx, cy, -14, 0), pt(cx, cy, -26, 12)])
            line([pt(cx, cy, -6, 12), pt(cx, cy, 14, 12)])
        elif idx == 81:  # 82. Bug
            cv2.ellipse(canvas, (cx, cy), (18, 26), 0, 0, 360, 0, SW, cv2.LINE_AA)
            line([pt(cx, cy, 0, -26), pt(cx, cy, 0, 26)])
            line([pt(cx, cy, -18, -10), pt(cx, cy, -34, -20)])
            line([pt(cx, cy, 18, -10), pt(cx, cy, 34, -20)])
            line([pt(cx, cy, -18, 5), pt(cx, cy, -36, 5)])
            line([pt(cx, cy, 18, 5), pt(cx, cy, 36, 5)])
            line([pt(cx, cy, -18, 18), pt(cx, cy, -34, 30)])
            line([pt(cx, cy, 18, 18), pt(cx, cy, 34, 30)])
        elif idx == 82:  # 83. Git Branch
            line([pt(cx, cy, -18, -20), pt(cx, cy, -18, 20)])
            line([pt(cx, cy, -18, 6), pt(cx, cy, 18, -10)])
            circle(cx - 18, cy - 28, 8)
            circle(cx - 18, cy + 28, 8)
            circle(cx + 18, cy - 18, 8)
        elif idx == 83:  # 84. Shopping Cart
            line([pt(cx, cy, -38, -28), pt(cx, cy, -26, -28), pt(cx, cy, -12, 14), pt(cx, cy, 26, 14), pt(cx, cy, 36, -14), pt(cx, cy, -20, -14)])
            circle(cx - 8, cy + 26, 6)
            circle(cx + 20, cy + 26, 6)
        elif idx == 84:  # 85. Shopping Bag
            rrect(cx - 28, cy - 16, cx + 28, cy + 36, 6)
            arc(cx, cy - 16, 16, 180, 360)
        elif idx == 85:  # 86. Credit Card
            rrect(cx - 40, cy - 26, cx + 40, cy + 26, 6)
            line([pt(cx, cy, -40, -10), pt(cx, cy, 40, -10)])
            rrect(cx - 30, cy + 4, cx - 14, cy + 16, 2)
        elif idx == 86:  # 87. Wallet
            rrect(cx - 38, cy - 24, cx + 38, cy + 24, 6)
            arc(cx + 14, cy, 14, -90, 90)
            circle(cx + 24, cy, 3)
        elif idx == 87:  # 88. Dollar Coin
            circle(cx, cy, 38)
            line([pt(cx, cy, 0, -24), pt(cx, cy, 0, 24)])
            arc(cx, cy - 8, 10, 90, 270)
            arc(cx, cy + 8, 10, 270, 450)
        elif idx == 88:  # 89. Receipt
            pts = [pt(cx, cy, -28, -36), pt(cx, cy, 28, -36), pt(cx, cy, 28, 36)]
            # zigzag bottom
            for zx in (20, 10, 0, -10, -20):
                pts.append(pt(cx, cy, zx + 4, 30))
                pts.append(pt(cx, cy, zx - 4, 36))
            pts.append(pt(cx, cy, -28, 36))
            line(pts, closed=True)
            line([pt(cx, cy, -18, -20), pt(cx, cy, 18, -20)])
            line([pt(cx, cy, -18, -8), pt(cx, cy, 18, -8)])
            line([pt(cx, cy, -18, 4), pt(cx, cy, 4, 4)])
        elif idx == 89:  # 90. Bar Chart
            line([pt(cx, cy, -36, -34), pt(cx, cy, -36, 34), pt(cx, cy, 36, 34)])
            line([pt(cx, cy, -24, 34), pt(cx, cy, -24, 8)])
            line([pt(cx, cy, -8, 34), pt(cx, cy, -8, -12)])
            line([pt(cx, cy, 8, 34), pt(cx, cy, 8, 18)])
            line([pt(cx, cy, 24, 34), pt(cx, cy, 24, -26)])
        elif idx == 90:  # 91. Line Graph
            line([pt(cx, cy, -36, -34), pt(cx, cy, -36, 34), pt(cx, cy, 36, 34)])
            line([pt(cx, cy, -30, 20), pt(cx, cy, -12, -4), pt(cx, cy, 8, 12), pt(cx, cy, 28, -22)])
            circle(cx - 30, cy + 20, 3)
            circle(cx - 12, cy - 4, 3)
            circle(cx + 8, cy + 12, 3)
            circle(cx + 28, cy - 22, 3)
        elif idx == 91:  # 92. Pie Chart
            circle(cx, cy, 36)
            line([pt(cx, cy, 0, 0), pt(cx, cy, 0, -36)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 36, 0)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, -26, 26)])
        elif idx == 92:  # 93. Target Bullseye
            circle(cx, cy, 38)
            circle(cx, cy, 24)
            circle(cx, cy, 10)
        elif idx == 93:  # 94. Briefcase
            rrect(cx - 38, cy - 18, cx + 38, cy + 32, 6)
            line([pt(cx, cy, -16, -18), pt(cx, cy, -16, -30), pt(cx, cy, 16, -30), pt(cx, cy, 16, -18)])
            line([pt(cx, cy, -38, 2), pt(cx, cy, 38, 2)])
            rrect(cx - 8, cy - 2, cx + 8, cy + 10, 2)
        elif idx == 94:  # 95. Calendar
            rrect(cx - 36, cy - 24, cx + 36, cy + 36, 6)
            line([pt(cx, cy, -36, -8), pt(cx, cy, 36, -8)])
            line([pt(cx, cy, -18, -34), pt(cx, cy, -18, -18)])
            line([pt(cx, cy, 18, -34), pt(cx, cy, 18, -18)])
            for dx in (-16, 0, 16):
                for dy in (6, 20):
                    circle(cx + dx, cy + dy, 2)
        elif idx == 95:  # 96. Clock
            circle(cx, cy, 38)
            line([pt(cx, cy, 0, 0), pt(cx, cy, 0, -20)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 16, 0)])
            circle(cx, cy, 4)
        elif idx == 96:  # 97. Shield Security
            line([pt(cx, cy, -34, -32), pt(cx, cy, 34, -32), pt(cx, cy, 34, 4), pt(cx, cy, 0, 38), pt(cx, cy, -34, 4)], closed=True)
            line([pt(cx, cy, -14, 2), pt(cx, cy, -4, 14), pt(cx, cy, 18, -8)])
        elif idx == 97:  # 98. Delivery Truck
            rrect(cx - 38, cy - 18, cx + 10, cy + 22, 4)
            line([pt(cx, cy, 10, -4), pt(cx, cy, 26, -4), pt(cx, cy, 36, 8), pt(cx, cy, 36, 22), pt(cx, cy, 10, 22)])
            circle(cx - 18, cy + 24, 8)
            circle(cx + 22, cy + 24, 8)
        elif idx == 98:  # 99. Package Box
            # Isometric box
            line([pt(cx, cy, 0, -36), pt(cx, cy, 32, -18), pt(cx, cy, 32, 18), pt(cx, cy, 0, 36), pt(cx, cy, -32, 18), pt(cx, cy, -32, -18)], closed=True)
            line([pt(cx, cy, 0, 0), pt(cx, cy, 0, 36)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, 32, -18)])
            line([pt(cx, cy, 0, 0), pt(cx, cy, -32, -18)])
        elif idx == 99:  # 100. Sun & Moon
            circle(cx - 8, cy, 24)
            # crescent
            arc(cx + 12, cy, 24, 70, 290)
            arc(cx + 22, cy, 20, 110, 250)
            # rays on sun side
            for a in (135, 180, 225):
                rad = math.radians(a)
                line([pt(cx - 8, cy, 28 * math.cos(rad), 28 * math.sin(rad)),
                      pt(cx - 8, cy, 38 * math.cos(rad), 38 * math.sin(rad))])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, canvas)
    print(f"Generated 100-icon presentation sheet successfully: {output_path} ({W}x{H})")
    return output_path

if __name__ == "__main__":
    create_100_icons_sheet()
