"""Vector model: a list of stroked Bezier paths (anchors + in/out handles), serialisable to SVG/JSON."""
from __future__ import annotations
import copy, json
import numpy as np
from .geom import bez


class Path:
    __slots__ = ("A", "Hin", "Hout", "w", "join", "ml", "closed")

    def __init__(self, A, Hin, Hout, w, join="round", ml=4.0, closed=False):
        self.A = np.asarray(A, float)
        self.Hin = np.asarray(Hin, float)
        self.Hout = np.asarray(Hout, float)
        self.w = float(w)
        self.join = join
        self.ml = float(ml)
        self.closed = bool(closed)

    @staticmethod
    def from_segs(segs, w, closed=False, join="round"):
        S = np.array(segs, float)
        A = np.vstack([S[:, 0], S[-1:, 3]])
        Ho = np.vstack([S[:, 1], S[-1:, 3]])
        Hi = np.vstack([S[:1, 0], S[:, 2]])
        if closed:
            A[-1] = A[0]
            Ho[-1] = Ho[0]
            Hi[0] = Hi[-1]
        return Path(A, Hi, Ho, w, join, 4.0, closed)

    def segs(self):
        return [np.array([self.A[i], self.Hout[i], self.Hin[i + 1], self.A[i + 1]]) for i in range(len(self.A) - 1)]

    def flat(self, step=1.0):
        pts = []
        for c in self.segs():
            L = np.linalg.norm(c[3] - c[0]) + np.linalg.norm(c[1] - c[0]) + np.linalg.norm(c[2] - c[1]) + np.linalg.norm(c[3] - c[2])
            n = max(6, int(L / step / 1.4))
            q = bez(c, np.linspace(0, 1, n))
            pts.append(q if not pts else q[1:])
        return np.vstack(pts)

    def d(self):
        s = self.segs()
        d = "M%.2f,%.2f" % tuple(s[0][0])
        for c in s:
            d += "C%.2f,%.2f %.2f,%.2f %.2f,%.2f" % (*c[1], *c[2], *c[3])
        return d + ("Z" if self.closed else "")

    def length(self):
        f = self.flat()
        return float(np.linalg.norm(np.diff(f, axis=0), axis=1).sum())

    def copy(self):
        return Path(self.A.copy(), self.Hin.copy(), self.Hout.copy(), self.w, self.join, self.ml, self.closed)

    def to_dict(self):
        return dict(A=self.A.tolist(), Hin=self.Hin.tolist(), Hout=self.Hout.tolist(), w=self.w, join=self.join, ml=self.ml, closed=self.closed)

    @staticmethod
    def from_dict(q):
        return Path(q["A"], q["Hin"], q["Hout"], q["w"], q.get("join", "round"), q.get("ml", 4.0), q.get("closed", False))


class Model:
    def __init__(self, paths=None, width=0, height=0):
        self.paths: list[Path] = paths or []
        self.width = width
        self.height = height

    def copy(self):
        return Model([p.copy() for p in self.paths], self.width, self.height)

    def scaled(self, k, width=None, height=None):
        """New model with every coordinate and stroke width multiplied by k (SVG pixel-edge coords scale exactly)."""
        out = self.copy()
        for p in out.paths:
            p.A, p.Hin, p.Hout = p.A * k, p.Hin * k, p.Hout * k
            p.w *= k
        out.width = width if width is not None else int(round(self.width * k))
        out.height = height if height is not None else int(round(self.height * k))
        return out

    def translate(self, dx, dy):
        for p in self.paths:
            for a in (p.A, p.Hin, p.Hout):
                a += [dx, dy]
        return self

    def svg(self, background="#ffffff", stroke="#000000", cap="round", stroke_scale=1.0, pretty=False, viewbox=None):
        w, h = self.width, self.height
        vb = viewbox or (0, 0, w, h)
        body = []
        for p in self.paths:
            body.append(
                '<path d="%s" stroke-width="%.2f" stroke-linejoin="%s"%s/>'
                % (p.d(), p.w * stroke_scale, p.join, (' stroke-miterlimit="%g"' % p.ml) if p.join == "miter" else "")
            )
        bg = '<rect width="100%%" height="100%%" fill="%s"/>' % background if background else ""
        sep = "\n  " if pretty else ""
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" width="%g" height="%g">%s%s'
            '<g fill="none" stroke="%s" stroke-linecap="%s">%s%s</g>%s</svg>'
            % (vb[0], vb[1], vb[2], vb[3], vb[2], vb[3], sep, bg, stroke, cap, sep, sep.join(body), "\n" if pretty else "")
        )

    def to_json(self):
        return json.dumps(dict(width=self.width, height=self.height, paths=[p.to_dict() for p in self.paths]))

    @staticmethod
    def from_svg(svg: str):
        """Read back an SVG written by `Model.svg()` (M / C / Z paths with per-path stroke-width)."""
        import re
        num = lambda t: [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", t)]
        head = re.search(r'viewBox="([^"]+)"', svg)
        vb = num(head.group(1)) if head else [0, 0, 0, 0]
        paths = []
        for d, w in re.findall(r'<path d="([^"]+)" stroke-width="([\d.]+)"', svg):
            toks = re.findall(r"[MCZ][^MCZ]*", d)
            p0 = num(toks[0])[:2]
            A, Hi, Ho = [p0], [p0], []
            for t in toks[1:]:
                if t[0] == "C":
                    v = num(t)
                    for k in range(0, len(v) - 5, 6):
                        Ho.append(v[k:k + 2]); Hi.append(v[k + 2:k + 4]); A.append(v[k + 4:k + 6])
            if not Ho:
                continue
            Ho.append(A[-1])
            jm = re.search(r'<path d="%s"[^>]*stroke-linejoin="(\w+)"' % re.escape(d), svg)
            paths.append(Path(A, Hi, Ho, float(w), jm.group(1) if jm else "round", 4.0, toks[-1].startswith("Z")))
        return Model(paths, int(vb[2]), int(vb[3]))

    @staticmethod
    def from_json(s):
        q = json.loads(s)
        return Model([Path.from_dict(p) for p in q["paths"]], q["width"], q["height"])
