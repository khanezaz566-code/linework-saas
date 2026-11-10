"""Doctor engine: compares the rendered vector with the source and issues repair commands.

Checks
  * mismatch regions      concentrated render-vs-source error (soft ink difference, box-filtered)
  * redundant paths       a path whose ink is entirely covered by other paths (duplicate centerline)
  * duplicate tails/runs  stretches of a path lying inside other paths' ink for > ~1 stroke width
  * kinks                 anchors that are almost, but not quite, smooth (tangent break 6-30 deg)
  * rings                 closed paths that are exact ellipses but stored as free-form curves
  * simplify / line snap  needless nodes, nearly-straight segments
"""
from __future__ import annotations
import numpy as np, cv2
from scipy import ndimage as ndi
from .geom import resample
from .model import Model
from .render import render_gray
from .fitting import draw_stroke
from . import edit as E
from . import topology as T


def ink_of(model: Model):
    g = render_gray(model.svg(), model.width, model.height)
    return (255 - g.astype(np.float32)) / 255


class Doctor:
    def __init__(self, D, sens=6.0, kink_lo=6.0, kink_hi=30.0):
        self.D = np.asarray(D, float)
        self.ref = self.D > 0.5
        self.dS = ndi.distance_transform_edt(~self.ref)
        self.sens = sens
        self.kink_lo, self.kink_hi = kink_lo, kink_hi
        self.area = float(self.ref.sum())

    # ---- metrics
    def soft(self, ink):
        return float(np.abs(np.asarray(ink, float) - self.D).sum())

    def iou(self, ink):
        b = ink > 0.5
        union = int((b | self.ref).sum())
        if union <= 0:
            return 1.0
        diff = int((b ^ self.ref).sum())
        if diff == 0:
            return 1.0
        b_dil = cv2.dilate(b.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        miss = int((self.ref & ~b_dil).sum())
        extra = int((b & (self.dS > 1.05)).sum())
        hard = miss + extra
        fuzz = max(0, diff - hard)
        return float(max(0.0, (union - (hard + 0.08 * fuzz)) / union))

    def regions(self, ink, win=9, merge_d=24):
        m = np.abs(ink - self.D)
        s = cv2.boxFilter(m, -1, (win, win), normalize=False)
        pk = (s >= self.sens).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(pk)
        regs = []
        for i in range(1, n):
            x, y, w, h, _a = st[i]
            regs.append([x - 4, y - 4, x + w + 4, y + h + 4, float(s[lab == i].max())])
        out = []
        for r in sorted(regs, key=lambda r: -r[4]):
            for o in out:
                if r[0] < o[2] + merge_d and r[2] > o[0] - merge_d and r[1] < o[3] + merge_d and r[3] > o[1] - merge_d:
                    o[0], o[1] = min(o[0], r[0]), min(o[1], r[1])
                    o[2], o[3] = max(o[2], r[2]), max(o[3], r[3])
                    o[4] = max(o[4], r[4])
                    break
            else:
                out.append(r)
        return out

    # ---- structural checks
    def _coverage(self, model):
        H, W = self.D.shape
        covs, flats = [], []
        for p in model.paths:
            f = resample(p.flat(), 1.0)
            im = np.zeros((H, W), np.uint8)
            draw_stroke(im, f, p.w, p.join == "miter", 0, 0, p.ml, 1)
            covs.append(im > 0)
            flats.append(f)
        return covs, flats

    def redundancy(self, model):
        from scipy.spatial import cKDTree
        covs, flats = self._coverage(model)
        if not covs:
            return [], []
        count = np.sum(covs, axis=0)
        red, tails = [], []
        # Pre-build KDTree of other paths to check true centerline-to-centerline duplication
        all_flats = [f for f in flats]
        for i, (c, f) in enumerate(zip(covs, flats)):
            w = model.paths[i].w
            excl = c & (count == 1)
            other_entries = [(m, all_flats[m]) for m in range(len(all_flats)) if m != i and len(all_flats[m]) > 0]
            if not other_entries:
                continue
            tree_other = cKDTree(np.vstack([fm for _, fm in other_entries]))
            tree_owners = np.concatenate([[m] * len(fm) for m, fm in other_entries])
            # A stroke is ONLY redundant if virtually all of its rendered ink is covered by other strokes
            # AND its centerline lies right on top of another stroke (< 0.16 * w)
            if excl.sum() < max(4, int(0.015 * c.sum())):
                d_cl, _ = tree_other.query(f)
                median_cl_dist = float(np.median(d_cl))
                frac_coincident = float((d_cl < 0.20 * w).mean())
                if frac_coincident >= 0.85 and median_cl_dist <= 0.16 * w:
                    red.append(i)
                    continue
            ek = cv2.dilate(excl.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, ek.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, ek.shape[0] - 1)
            has = ek[ys, xs]
            k = 0
            while k < len(has):
                if has[k]:
                    k += 1
                    continue
                j = k
                while j < len(has) and not has[j]:
                    j += 1
                # Only true tails at stroke endpoints should ever be cut; interior spans are junctions/crossings
                if (k <= 3 or j >= len(has) - 3) and j - k >= max(0.9 * w, 8):
                    d_sub, idx_cl = tree_other.query(f[k:j])
                    if float(np.median(d_sub)) > 0.28 * w:
                        k = j
                        continue
                    tail_pts = f[k:j]
                    if len(tail_pts) >= 2:
                        v_tail = tail_pts[-1] - tail_pts[0] if (j >= len(has) - 3) else (tail_pts[0] - tail_pts[-1])
                        lv = np.linalg.norm(v_tail)
                        if lv > 1e-4:
                            t_tail = v_tail / lv
                            m_other = int(np.bincount(tree_owners[idx_cl]).argmax())
                            f_oth = all_flats[m_other]
                            if len(f_oth) >= 2:
                                _, idx_near = cKDTree(f_oth).query(tail_pts)
                                idx_near = np.clip(idx_near, 0, len(f_oth) - 2)
                                v_oth = f_oth[idx_near + 1] - f_oth[idx_near]
                                t_oth = v_oth / np.maximum(np.linalg.norm(v_oth, axis=1, keepdims=True), 1e-6)
                                cos_align = np.abs(np.sum(t_tail[None, :] * t_oth, axis=1))
                                if float(np.mean(cos_align > 0.88)) < 0.65:
                                    k = j
                                    continue
                    tails.append((i, 0 if k <= 3 else 1, j - k))
                k = j
        return red, tails

    def kinks(self, model):
        out = []
        for i, p in enumerate(model.paths):
            for k in range(1, len(p.A) - 1):
                din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a < 1e-6 or b < 1e-6:
                    continue
                ang = np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1)))
                if self.kink_lo < ang < self.kink_hi:
                    out.append((i, k, float(ang)))
        return out

    def rings(self, model):
        out = []
        for i, p in enumerate(model.paths):
            if not p.closed or len(p.segs()) == 4:
                continue
            r = E.fit_ellipse(p.flat())
            if r and r[1] < 0.9:
                out.append(i)
            elif E.robust_ellipse(p.flat(), p.w):
                out.append(i)
        return out

    def snaps(self, model):
        out = []
        for i, p in enumerate(model.paths):
            for c in p.segs():
                ch = c[3] - c[0]
                L = np.linalg.norm(ch)
                if L < 6:
                    continue
                n = np.array([-ch[1], ch[0]]) / L
                dev = max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n))
                off = abs(np.linalg.norm(c[1] - c[0]) - L / 3) + abs(np.linalg.norm(c[2] - c[3]) - L / 3)
                if dev * 0.75 < max(0.35, 0.05 * p.w) and (dev > 1e-3 or off > 0.2):
                    out.append(i)
                    break
        return out

    def sharp_paths(self, model):
        """Paths that contain a deliberate sharp corner and are still round-joined (try miter)."""
        out = []
        for i, p in enumerate(model.paths):
            if p.join != "round":
                continue
            found = False
            for k in range(1, len(p.A) - 1):
                din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a < 1e-6 or b < 1e-6:
                    continue
                if np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1))) >= 25:
                    out.append(i)
                    found = True
                    break
            if not found and p.closed and len(p.A) >= 3:
                din, dout = p.A[0] - p.Hin[0], p.Hout[0] - p.A[0]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a >= 1e-6 and b >= 1e-6:
                    if np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1))) >= 25:
                        out.append(i)
        return out

    # ---- full diagnosis
    def diagnose(self, model, ink=None, first_round=False):
        ink = ink_of(model) if ink is None else ink
        red, tails = self.redundancy(model)
        rep = dict(
            iou=self.iou(ink),
            soft=self.soft(ink),
            soft_norm=self.soft(ink) / max(self.area, 1),
            regions=self.regions(ink),
            redundant=red,
            tails=tails,
            kinks=self.kinks(model),
            rings=self.rings(model),
            snaps=self.snaps(model),
            simplify=[i for i, p in enumerate(model.paths) if len(p.segs()) > 3] if first_round else [],
            sharp=self.sharp_paths(model),
            gaps=T.find_gaps(model),
            notches=T.find_notches(model),
            spurs=T.find_spurs(model),
        )
        rep["issues"] = (
            len(rep["regions"]) + len(red) + len(tails) + len(rep["kinks"]) + len(rep["rings"]) + len(rep["snaps"]) + len(rep["simplify"])
            + len(rep["gaps"]) + len(rep["notches"]) + len(rep["spurs"])
        )
        return rep

    @staticmethod
    def commands(rep, max_regions=6):
        """Ordered repair commands. Structural removals go last-index-first so indices stay valid."""
        cmds = []
        for i in sorted(rep["redundant"], reverse=True):
            cmds.append(dict(op="remove_path", path=i, tol=4.0))
        for (i, a, b) in sorted(rep["tails"], key=lambda t: (-t[0], -t[1])):
            if i not in rep["redundant"]:
                cmds.append(dict(op="cut", path=i, a=a, b=b, tol=4.0))
        return cmds

    @staticmethod
    def cosmetic_commands(rep):
        cmds = []
        for (i, e) in sorted(rep["spurs"], key=lambda t: (-t[0], -t[1])):
            cmds.append(dict(op="trim_tail", path=i, end=e, tol=1.0))
        for i in rep["notches"]:
            cmds.append(dict(op="merge_nodes", path=i, tol=1.0))
        for i in rep["rings"]:
            cmds.append(dict(op="circle", path=i, robust=True, tol=1.0))
        for (i, k, ang) in rep["kinks"]:
            cmds.append(dict(op="smooth_anchor", path=i, anchor=k, tol=1.0))
        for i in rep["snaps"]:
            cmds.append(dict(op="line_snap", path=i, tol=1.0))
        for i in rep["simplify"]:
            cmds.append(dict(op="simplify", path=i, err=0.45, tol=1.0))
        for i in rep["sharp"]:
            cmds.append(dict(op="join", path=i, join="miter", tol=2.0))
        if rep["gaps"]:
            cmds.append(dict(op="weld", path=-1, tol=1.0))
        return cmds

    @staticmethod
    def region_commands(rep, max_regions=6):
        regs = sorted(rep["regions"], key=lambda r: -r[4])[:max_regions]
        return [dict(op="refine_region", box=[int(r[0]), int(r[1]), int(r[2]), int(r[3])], tol=-0.5) for r in regs]
