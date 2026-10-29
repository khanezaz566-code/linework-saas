import json, sys
sys.path.insert(0, ".")
from linework.model import Model
from linework import finisher as FN
from linework import joincheck as JC
from tools.junction_bench import knot
from linework.trace import ink_map
from linework.doctor import Doctor
from linework.render import render_gray
import linework.topology as T

g = knot()
D = ink_map(g)
doc = Doctor(D)
def ink_of(mod):
    return render_gray(mod.svg(), g.shape[1], g.shape[0]) < 128

m = Model.from_json(json.load(open('scratch/knot_m0.json')))
cur = doc.soft(ink_of(m))
start = cur
w_est = 10.0
joints = JC.inspect(m, D, ink_of(m))
drift_cap = max(0.025 * max(doc.area, 1), 1.2 * len(joints) * (w_est ** 2))
topo0 = FN._topo(m)
print(f"Start bad: {JC.bad_count(joints)}, topo0: {topo0}")

given_up = set()
for rnd in range(6):
    progress = False
    while True:
        todo = [j for j in joints if j["reasons"] and (round(j["x"]), round(j["y"])) not in given_up]
        if not todo:
            break
        j0 = min(todo, key=lambda j: ("XLYT".index(j["kind"]), -len(j["reasons"])))
        base_bad = JC.bad_count(joints)
        done = None
        reasons_list = list(j0["reasons"])
        print(f"\nProcessing {j0['kind']} at ({j0['x']:.1f}, {j0['y']:.1f}) reasons={reasons_list}")
        for reason in reasons_list:
            for tool in JC.PLAN.get(reason, ()):
                for cand in JC.TOOLS[tool](m, j0, reason):
                    if cand is None:
                        continue
                    ink2 = ink_of(cand)
                    s2 = doc.soft(ink2)
                    t2 = FN._topo(cand)
                    if t2 > topo0:
                        cw = T.weld_all(cand)
                        if FN._topo(cw) <= topo0:
                            cand, ink2, s2, t2 = cw, ink_of(cw), doc.soft(ink_of(cw)), FN._topo(cw)
                    allow = (1.8 if j0["kind"] == "X" else 1.0) * j0["w"] ** 2
                    jn2 = JC.inspect(cand, D, ink2)
                    b2 = JC.bad_count(jn2)
                    reject_reason = None
                    if t2 > topo0:
                        reject_reason = f"topo {t2} > {topo0}"
                    elif s2 > cur + max(2.0, 0.003 * cur, allow):
                        reject_reason = f"soft diff {s2-cur:.1f} > allow {allow:.1f}"
                    elif (s2 - start) > drift_cap:
                        reject_reason = f"drift {s2-start:.1f} > {drift_cap:.1f}"
                    elif not ((b2 < base_bad) or (b2 <= base_bad and (len(cand.paths) < len(m.paths) or t2 < topo0))):
                        reject_reason = f"bad not better: {b2} vs {base_bad}"
                    
                    if reject_reason:
                        print(f"    Tool {tool} reject: {reject_reason}")
                    else:
                        print(f"    Tool {tool} ACCEPTED! b2={b2} < {base_bad}")
                        done = (tool, reason, cand, ink2, s2, jn2)
                        break
                if done:
                    break
            if done:
                break
        if done:
            _, _, m, ink, cur, joints = done
            topo0 = min(topo0, FN._topo(m))
            progress = True
            print(f"  --> Progress! New bad count: {JC.bad_count(joints)}, new topo: {topo0}")
        else:
            print(f"  --> FAILED to fix {j0['kind']} at ({j0['x']:.1f}, {j0['y']:.1f})")
            given_up.add((round(j0['x']), round(j0['y'])))
    if not progress:
        break

print(f"\nFINAL BAD: {JC.bad_count(joints)}")
for j in joints:
    if j['reasons']:
        print("  FAILING:", j['kind'], f"({j['x']:.1f}, {j['y']:.1f})", j['reasons'], "ends:", j['ends'], "target:", j.get('target'))
        i, e = j['ends'][0]
        p = m.paths[i]
        print("  Path info:", f"p{i} len={len(p.A)} length={p.length():.1f} w={p.w:.1f} end_pt={p.A[0 if e==0 else -1]}")
        r = int(max(3, 1.5 * j["w"]))
        H, W = D.shape
        x0, x1 = int(max(j["x"] - r, 0)), int(min(j["x"] + r + 1, W))
        y0, y1 = int(max(j["y"] - r, 0)), int(min(j["y"] + r + 1, H))
        ink_cur = ink_of(m)
        miss = float(((ink_cur[y0:y1, x0:x1] < 0.5) & (D[y0:y1, x0:x1] > 0.7)).sum())
        print(f"  Missing ink in window: {miss:.1f} vs threshold {JC.INK_FRAC * j['w']**2:.1f}")

