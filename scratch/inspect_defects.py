import sys, os, glob, json
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from linework import pipeline as P, joints as JN, finisher as FN
from linework.model import Model

for job_id in ["ea3cb3bb04a7", "c471730969a4", "d2db65924830", "17e5cda6510e", "b8dd3fd916fd", "e73efd7893c3", "12da127f9cac"]:
    job_dir = os.path.join("data", job_id)
    if not os.path.exists(job_dir):
        continue
    icon_files = sorted(glob.glob(os.path.join(job_dir, "icon_[0-9]*.json")))
    print(f"=== Job {job_id}: {len(icon_files)} icons ===")
    for ipath in icon_files:
        name = os.path.basename(ipath)
        with open(ipath, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        if isinstance(data, dict) and "model" in data:
            m_str = data["model"] if isinstance(data["model"], str) else json.dumps(data["model"])
        else:
            m_str = raw
        m = Model.from_json(m_str)
        js = JN.find_joints(m)
        bad_touch = []
        bad_hooks = []
        for J in js:
            if J.kind in ("T", "Y"):
                for (i, e) in J.ends:
                    end = JN._end_pt(m.paths[i], e)
                    others = [j for j in J.through if j != i] or J.through
                    if others:
                        dmin = min(JN._nearest_on(m.paths[j], end)[1] for j in others)
                        if dmin > 0.05:
                            bad_touch.append((J.kind, round(dmin, 2), (round(end[0], 1), round(end[1], 1))))
                    g = FN.end_geometry(m.paths[i], e)
                    if g is not None and (g[2] > 12.0 or g[4] > 0.8):
                        bad_hooks.append((i, e, round(g[2], 1), round(g[4], 2)))
            elif J.kind == "L":
                pts = np.array([JN._end_pt(m.paths[i], e) for i, e in J.ends])
                dmax = float(np.linalg.norm(pts - pts.mean(0), axis=1).max())
                if dmax > 0.05:
                    bad_touch.append(("L", round(dmax, 2), (round(J.xy[0], 1), round(J.xy[1], 1))))
        short_segs = []
        for pi, p in enumerate(m.paths):
            segs = p.segs()
            for si, c in enumerate(segs):
                L = float(np.linalg.norm(c[3] - c[0]))
                if L < 0.8 * p.w and len(segs) > 1:
                    short_segs.append((pi, si, round(L, 2)))
        if bad_touch or bad_hooks or short_segs:
            print(f"  {name}: paths={len(m.paths)}, joints={len(js)}, off_touch={bad_touch[:5]}, hooks={bad_hooks[:4]}, short_segs={len(short_segs)}")
