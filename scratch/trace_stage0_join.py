import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width
from linework.trace import ink_map
import linework.joints as J
import linework.finisher as FN

job = json.load(open('data/b95d5c14c7a9/job.json'))
orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
opts = Options(**job['options'])
opts.fresh = True

box = job['icons'][0]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(ink_map(crop))
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)

# Run pipeline up to joints engine and see what happens at Joint 2
orig_run_join_engine = J.run_join_engine
def trace_join_engine(model, D, doctor, ink_of, cur, w, **kwargs):
    print("Inside run_join_engine:")
    st = dict(model=model, ink=ink_of(model))
    st["cur"] = doctor.soft(st["ink"])
    start = st["cur"]
    st["topo"] = FN._topo(model)
    cap = 0.006 * max(doctor.area, 1)
    tol = lambda: max(4.0, 0.003 * max(doctor.area, 1), 0.006 * st["cur"])
    
    def nearest(m, xy, rad):
        js = J.find_joints(m)
        if not js: return None
        d = [np.linalg.norm(j.xy - xy) for j in js]
        k = int(np.argmin(d))
        return js[k] if d[k] <= rad else None

    joints = [j for j in J.find_joints(st["model"]) if len(j.ends) >= 2]
    print(f"Total multi-end joints: {len(joints)}")
    for j_i, J_item in enumerate(joints):
        J_cur = nearest(st["model"], J_item.xy, 1.5 * J_item.w)
        if J_cur is None or len(J_cur.ends) < 2:
            print(f"Joint {j_i} at {np.round(J_item.xy, 1)} skipped: J_cur is None or <2 ends")
            continue
        print(f"\nProcessing joint {j_i} at {np.round(J_cur.xy, 1)}, ends={J_cur.ends}")
        cand_u = J.tool_unite(st["model"], J_cur, D)
        if cand_u is None:
            print(f"  tool_unite returned None")
        else:
            s_u = doctor.soft(ink_of(cand_u))
            t_u = FN._topo(cand_u)
            print(f"  tool_unite returned cand: soft={s_u:.2f} (cur+tol={st['cur']+tol():.2f}), topo={t_u} (cur_topo={st['topo']})")
            if s_u <= st["cur"] + tol() and (s_u - start) <= cap and t_u <= st["topo"]:
                st.update(model=cand_u, ink=ink_of(cand_u), cur=s_u, topo=t_u)
                print(f"  ACCEPTED!")
            else:
                print(f"  REJECTED! Reason: soft ok? {s_u <= st['cur']+tol()}, cap ok? {s_u-start <= cap}, topo ok? {t_u <= st['topo']}")
    return orig_run_join_engine(model, D, doctor, ink_of, cur, w, **kwargs)

J.run_join_engine = trace_join_engine
_process_icon(small, opts, emit=lambda **k: None, name='ic0')
