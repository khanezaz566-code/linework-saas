import os, sys
os.environ['LINEWORK_MEMORY'] = '0'
sys.path.insert(0, os.path.abspath('.'))

from linework import joints as JN
from linework.doctor import Doctor, ink_of
from linework.trace import ink_map
import tools.junction_bench as jb
from linework.pipeline import Options, process_icon

g = jb.spool()
r = process_icon(g, Options(finish=False, joins=False), name='spool')
m = r['model']
D = ink_map(g)
doc = Doctor(D)
cur = doc.soft(ink_of(m))

print(f"Initial soft mismatch: {cur:.2f}, ink area: {doc.area}")
print(f"0.003 * doc.area = {0.003 * doc.area:.2f}")

# Let's test run_join_engine
m_out, ink_out, cur_out, rep = JN.run_join_engine(m, D, doc, ink_of, cur, 10.0)
print(f"Default run_join_engine: total={rep['total']}, clean_first={rep['clean_first']}, built={rep['built']}, fixed={rep['fixed']}, unresolved={len(rep['unresolved'])}")

# Now let's test with tol based on 0.003 * doc.area
# monkey patch tol in joints
def new_run_join_engine(model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_fail=30):
    st = dict(model=model, ink=ink_of(model))
    st["cur"] = doctor.soft(st["ink"])
    start = st["cur"]
    st["topo"] = JN.FN._topo(model)
    cap = 0.006 * max(doctor.area, 1)
    rep = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)

    # 0.3% of ink area, min 4.0 px
    area_tol = max(4.0, 0.003 * max(doctor.area, 1))
    def tol():
        return area_tol

    def nearest(m, xy, rad):
        js = JN.find_joints(m)
        if not js: return None
        import numpy as np
        d = [np.linalg.norm(j.xy - xy) for j in js]
        k = int(np.argmin(d))
        return js[k] if d[k] <= rad else None

    def try_accept(cand, J, before):
        if cand is None: return False
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 > st["cur"] + tol() or (s2 - start) > cap:
            return False
        t2 = JN.FN._topo(cand)
        if t2 > st["topo"]:
            return False
        J2 = nearest(cand, J.xy, 1.5 * J.w)
        ex, mi = JN._ink_maps(ink2, D)
        after = [] if J2 is None else JN.check_joint(cand, J2, ex, mi)
        if len(after) < len(before):
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
            return True
        return False

    # stage 1: build joints one by one (or batch if clean)
    ex, mi = JN._ink_maps(st["ink"], D)
    joints = JN.find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in JN.check_joint(st["model"], J)]
    for J in need:
        cand = JN.tool_pen(st["model"], J)
        if cand is not None:
            ink2 = ink_of(cand)
            s2 = doctor.soft(ink2)
            if s2 <= st["cur"] + tol() and JN.FN._topo(cand) <= st["topo"]:
                st.update(model=cand, ink=ink2, cur=s2, topo=JN.FN._topo(cand))
                rep["built"] += 1

    # stage 2: repair remaining failures
    joints = JN.find_joints(st["model"])
    ex, mi = JN._ink_maps(st["ink"], D)
    fails = []
    for J in joints:
        bad = JN.check_joint(st["model"], J, ex, mi)
        if not bad:
            rep["clean_first"] += 1
        else:
            fails.append((len(bad), J.xy.copy(), J.w, bad))
    fails.sort(key=lambda t: -t[0])
    for _, xy, jw, _ in fails[:max_fail]:
        if not time_ok(): break
        ex, mi = JN._ink_maps(st["ink"], D)
        J = nearest(st["model"], xy, 1.5 * jw)
        if J is None: continue
        before = JN.check_joint(st["model"], J, ex, mi)
        if not before: continue
        done = False
        for name, fn in (("unite", lambda: JN.tool_unite(st["model"], J, D)),
                         ("pen", lambda: JN.tool_pen(st["model"], J)),
                         ("line", lambda: JN.tool_line(st["model"], J)),
                         ("arc", lambda: JN.tool_line(st["model"], J, arc=True)),
                         ("shape", lambda: JN.tool_shape(st["model"], J, D))):
            if not time_ok(): break
            try: cand = fn()
            except Exception: cand = None
            if try_accept(cand, J, before):
                rep["fixed"][name] += 1
                done = True
                break
        if not done:
            rep["unresolved"].append(dict(x=float(xy[0]), y=float(xy[1]), reasons=before))
    rep["drift"] = float(st["cur"] - start)
    return st["model"], st["ink"], st["cur"], rep

m2, ink2, cur2, rep2 = new_run_join_engine(m, D, doc, ink_of, cur, 10.0)
print(f"NEW run_join_engine: total={rep2['total']}, clean_first={rep2['clean_first']}, built={rep2['built']}, fixed={rep2['fixed']}, unresolved={len(rep2['unresolved'])}")
print(f"New match IoU: {doc.iou(ink2)*100:.2f}% (was {doc.iou(ink_of(m))*100:.2f}%)")
