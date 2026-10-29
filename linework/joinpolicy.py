"""Join policy: choose round / bevel / miter (and the miter limit) per path from the SOURCE, judged on the real render.

Why this exists (v0.9.0)
  * `edit.set_join` used to force miter with limit 10 and `pipeline.run` accepted it with a tolerance of
    max(2.5 % of the whole icon mismatch, 25 px).  At an acute corner (bubble tail, arrow head, folded corner)
    a miter spike or a fat blob costs only a few pixels, so it was accepted.
  * Now every candidate is rendered with the real output renderer, judged in a window around each corner of the path,
    and any ink that sticks out beyond the source ("spike") is punished 3x.  A change is kept only if the window gets
    strictly better and the whole icon does not get worse.
"""
from __future__ import annotations
import numpy as np, cv2
from .model import Model
from .render import render_gray

CANDIDATES = (("round", 4.0), ("bevel", 4.0), ("miter", 1.5), ("miter", 2.0), ("miter", 3.0), ("miter", 4.0))
MIN_TURN = 20.0   # degrees; smaller turns have no visible join
SPIKE_W = 3.0     # render-only ink beyond the source counts this much more than ordinary mismatch


def _ink(model: Model):
    g = render_gray(model.svg(), model.width, model.height)
    return (255 - g.astype(np.float32)) / 255


def corner_points(p, min_turn=MIN_TURN):
    """Anchor positions where the path turns by >= min_turn degrees (handles are used, so smooth anchors are skipped)."""
    out = []
    n = len(p.A)
    idx = list(range(1, n - 1))
    if p.closed and n >= 3:
        idx.append(0)
    for k in idx:
        din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
        a, b = np.linalg.norm(din), np.linalg.norm(dout)
        if a < 1e-6 or b < 1e-6:
            continue
        if np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1))) >= min_turn:
            out.append(p.A[k].copy())
    return out


def _windows(p, shape):
    H, W = shape
    r = 1.5 * p.w + 3
    return [(max(int(c[0] - r), 0), max(int(c[1] - r), 0), min(int(c[0] + r) + 1, W), min(int(c[1] + r) + 1, H)) for c in corner_points(p)]


def window_cost(ink, D, Dbig, wins):
    """mismatch + SPIKE_W * render-only ink that lies outside the (1 px dilated) source, summed over the windows."""
    tot = 0.0
    for (x0, y0, x1, y1) in wins:
        a, d, db = ink[y0:y1, x0:x1], D[y0:y1, x0:x1], Dbig[y0:y1, x0:x1]
        tot += float(np.abs(a - d).sum()) + SPIKE_W * float(np.clip(a - db, 0, 1).sum())
    return tot


def _dilated(D):
    return cv2.dilate((np.asarray(D) > 0.5).astype(np.float32), np.ones((3, 3), np.uint8))


def choose_join(m: Model, i: int, D, margin=0.5) -> Model:
    """Best (join, miterlimit) for path i. Returns `m` unchanged when nothing is strictly better."""
    p = m.paths[i]
    wins = _windows(p, D.shape)
    if not wins:
        return m
    D = np.asarray(D, np.float32)
    Dbig = _dilated(D)
    best, best_c = None, window_cost(_ink(m), D, Dbig, wins) - margin
    for join, ml in CANDIDATES:
        if join == p.join and (join != "miter" or abs(ml - p.ml) < 1e-9):
            continue
        t = m.copy()
        t.paths[i].join, t.paths[i].ml = join, ml
        c = window_cost(_ink(t), D, Dbig, wins)
        if c < best_c:
            best, best_c = t, c
    return best if best is not None else m


def spike_guard(model: Model, D, doctor, ink_of, cur, time_ok=lambda: True):
    """Final pass: re-judge the join of every path that has a corner. Returns (model, ink, cur, n_changed)."""
    m, ink, n = model, None, 0
    for i in range(len(m.paths)):
        if not time_ok():
            break
        if not corner_points(m.paths[i]):
            continue
        new = choose_join(m, i, D)
        if new is m:
            continue
        ink2 = ink_of(new)
        s2 = doctor.soft(ink2)
        if s2 <= cur + 0.5:
            m, ink, cur, n = new, ink2, s2, n + 1
    return m, (ink if ink is not None else ink_of(m)), cur, n
