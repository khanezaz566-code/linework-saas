"""Structural audit of an output SVG: duplicate / near-coincident centerlines, kinks, node counts."""
from __future__ import annotations
import re
import numpy as np
from scipy.spatial import cKDTree
from .model import Path
from .geom import resample


def parse_svg_paths(svg: str):
    out = []
    for d, w in re.findall(r'<path d="([^"]+)" stroke-width="([\d.]+)"', svg):
        closed = d.strip().endswith("Z")
        nums = np.array([float(x) for x in re.findall(r"-?\d+\.?\d*", d)]).reshape(-1, 2)
        A, Hi, Ho = [nums[0]], [nums[0]], []
        i = 1
        while i + 2 < len(nums) + 0 and i < len(nums):
            Ho.append(nums[i]); Hi.append(nums[i + 1]); A.append(nums[i + 2]); i += 3
        Ho.append(A[-1])
        out.append(Path(A, Hi, Ho, float(w), closed=closed))
    return out


def audit(paths, near=0.35, min_run=0.8):
    """Return list of (i, j, run_length_px) where path i runs alongside path j closer than near*w."""
    flats = [resample(p.flat(), 1.0) for p in paths]
    trees = [cKDTree(f) for f in flats]
    found = []
    for i, p in enumerate(paths):
        for j in range(len(paths)):
            if i == j:
                continue
            w = min(paths[i].w, paths[j].w)
            d, _ = trees[j].query(flats[i])
            close = d < near * w
            run = best = 0
            for c in close:
                run = run + 1 if c else 0
                best = max(best, run)
            if best >= min_run * w:
                found.append((i, j, best))
    # symmetric pairs reported once
    seen, res = set(), []
    for i, j, r in found:
        k = (min(i, j), max(i, j))
        if k not in seen:
            seen.add(k)
            res.append((i, j, r))
    return res


def kinks(paths, lo=6, hi=30):
    n = 0
    for p in paths:
        for k in range(1, len(p.A) - 1):
            a, b = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na > 1e-6 and nb > 1e-6:
                ang = np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1)))
                n += lo < ang < hi
    return n
