import sys, os, json
sys.path.insert(0, ".")
os.environ["LINEWORK_MEMORY"] = "0"
import numpy as np
from linework.model import Model, Path
from linework import finisher as FN
from linework import joincheck as JC
from linework import topology as T
from tools.junction_bench import ICONS
from linework.pipeline import process_icon, Options

# 1. Update _is_junction_end in topology
orig_is_junc = T._is_junction_end
def new_is_junction_end(m: Model, i: int, e: int) -> bool:
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return False
    a = p.A[0] if e == 0 else p.A[-1]
    b = p.A[1] if e == 0 else p.A[-2]
    d_a, d_b = np.inf, np.inf
    for j, q in enumerate(m.paths):
        if j == i:
            continue
        f = q.flat(1.0)
        da = float(np.linalg.norm(f - a, axis=1).min())
        db = float(np.linalg.norm(f - b, axis=1).min())
        if da < d_a:
            d_a = da
        if db < d_b:
            d_b = db
    if d_a <= 0.25 * p.w:  # clearly touching another stroke
        return True
    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)
T._is_junction_end = new_is_junction_end

# 2. Update merge_corners with clean seam and length-weighted stroke width
def clean_path(p):
    A, Hin, Hout = list(p.A), list(p.Hin), list(p.Hout)
    changed = True
    while changed and len(A) > 2:
        changed = False
        for k in range(len(A) - 1):
            if np.linalg.norm(A[k+1] - A[k]) < 0.25 * p.w:
                A.pop(k)
                Hin.pop(k)
                Hout.pop(k)
                changed = True
                break
    return Path(np.array(A), np.array(Hin), np.array(Hout), p.w, p.join, p.ml, p.closed)

def clean_merge_corners(m: Model, pairs):
    m = m.copy()
    dead = set()
    for (i, ei, j, ej) in pairs:
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else FN._reversed(P)
        Q = Q if ej == 0 else FN._reversed(Q)
        mid = (P.A[-1] + Q.A[0]) / 2
        dP, dQ = mid - P.A[-1], mid - Q.A[0]
        A = np.vstack([P.A, Q.A[1:]])
        Hin = np.vstack([P.Hin, Q.Hin[1:]])
        Hout = np.vstack([P.Hout[:-1], Q.Hout])
        A[len(P.A) - 1] = mid
        Hin[len(P.A) - 1] = P.Hin[-1] + dP
        Hout[len(P.A) - 1] = Q.Hout[0] + dQ
        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        merged = Path(A, Hin, Hout, w_merged, P.join, P.ml, False)
        m.paths[i] = clean_path(merged)
        dead.add(j)
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m
FN.merge_corners = clean_merge_corners

# 3. Update joincheck constants
JC.INK_FRAC = 0.75

# 4. Enhance tool_shape_builder for nub and y_spread in joincheck
orig_tool_sb = JC.tool_shape_builder
def enhanced_tool_shape_builder(m, jn, reason):
    out = orig_tool_sb(m, jn, reason)
    if reason == "nub":
        for i, e in jn["ends"]:
            w = m.paths[i].w
            for dist in (0.5 * w, 1.0 * w, 1.5 * w, 2.0 * w, 2.5 * w, 3.0 * w, 3.5 * w):
                cand = FN.move_end(m, i, e, dist)
                if cand is not None:
                    out.append(cand)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "nub", "corner_split"):
        # try merging all close pairs simultaneously
        ends = jn["ends"]
        pairs_to_merge = []
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        pairs_to_merge.append((ia, ea, ib, eb))
        if len(pairs_to_merge) > 1:
            try:
                cand = clean_merge_corners(m, pairs_to_merge)
                out.append(cand)
            except Exception:
                pass
    return out
JC.tool_shape_builder = enhanced_tool_shape_builder
JC.TOOLS["shape_builder"] = enhanced_tool_shape_builder

# 5. Enhance driver run in joincheck with proper drift_cap and weld fallback
orig_run = JC.run
def enhanced_run(model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_rounds=6, max_tries=60, skip=()):
    ink = ink_of(model)
    cur = doctor.soft(ink)
    start = cur
    topo0 = FN._topo(model)
    joints = JC.inspect(model, D, ink)
    rep = dict(joints=len(joints), bad_before=JC.bad_count(joints), bad_after=JC.bad_count(joints), fixed=0, tries=0, rounds=0, items=[])
    tries = 0
    drift_cap = max(0.025 * max(doctor.area, 1), 1.5 * len(joints) * (w ** 2))
    given_up = set()
    for rnd in range(max_rounds):
        rep["rounds"] = rnd + 1
        progress = False
        while time_ok() and tries < max_tries:
            todo = [j for j in joints if j["reasons"] and (round(j["x"]), round(j["y"])) not in given_up]
            if not todo:
                break
            j0 = min(todo, key=lambda j: ("XLYT".index(j["kind"]), -len(j["reasons"])))
            base_bad = JC.bad_count(joints)
            done = None
            for reason in list(j0["reasons"]):
                if reason in ("nub", "lump", "hole") and j0["kind"] in ("L", "Y") and ("corner_split" in j0["reasons"] or "y_spread" in j0["reasons"]):
                    continue
                for tool in JC.PLAN.get(reason, ()):
                    if tool in skip:
                        continue
                    best = None
                    for cand in JC.TOOLS[tool](model, j0, reason):
                        if cand is None:
                            continue
                        tries += 1
                        ink2 = ink_of(cand)
                        s2 = doctor.soft(ink2)
                        t2 = FN._topo(cand)
                        if t2 > topo0:
                            cw = T.weld_all(cand)
                            if FN._topo(cw) <= topo0:
                                cand = cw
                                ink2 = ink_of(cand)
                                s2 = doctor.soft(ink2)
                                t2 = FN._topo(cand)
                        if t2 > topo0:
                            continue
                        allow = 1.0 * j0["w"] ** 2
                        if s2 > cur + max(2.0, 0.003 * cur, allow) or (s2 - start) > drift_cap:
                            continue
                        jn2 = JC.inspect(cand, D, ink2)
                        b2 = JC.bad_count(jn2)
                        is_better = (b2 < base_bad) or (b2 <= base_bad and (len(cand.paths) < len(model.paths) or t2 < topo0))
                        if is_better:
                            key = (b2, t2, len(cand.paths), s2)
                            if best is None or key < best[0]:
                                best = (key, cand, ink2, s2, jn2)
                    if best is not None:
                        done = (tool, reason, best)
                        break
                if done:
                    break
            rep["items"].append(dict(kind=j0["kind"], x=j0["x"], y=j0["y"], reasons=list(j0["reasons"]), fixed=done is not None,
                                     tool=done[0] if done else None))
            if done:
                _, _, (key, cand, ink2, s2, jn2) = done
                model, ink, cur, joints = cand, ink2, s2, jn2
                topo0 = min(topo0, FN._topo(model))
                rep["fixed"] += 1
                progress = True
            else:
                given_up.add((round(j0["x"]), round(j0["y"])))
        if not progress:
            break
    rep["tries"] = tries
    rep["bad_after"] = JC.bad_count(joints)
    rep["failing"] = [dict(kind=j["kind"], x=j["x"], y=j["y"], reasons=j["reasons"]) for j in joints if j["reasons"]]
    return model, ink, cur, rep
JC.run = enhanced_run

if __name__ == "__main__":
    print("=== Running on Benchmark Icons ===", flush=True)
    for name in ["hub", "star", "spool", "knot", "ecg", "jar", "pen"]:
        f = ICONS[name]
        g = f()
        r = process_icon(g, Options(), name=name)
        jc = r["metrics"]["joins"]
        failing = [(f["kind"], round(f["x"], 1), round(f["y"], 1), f["reasons"]) for f in jc["failing"]]
        print(f"{name:6s}: joints={jc['joints']}, bad {jc['bad_before']} -> {jc['bad_after']}, fixed={jc['fixed']}, FAILING={failing}", flush=True)
