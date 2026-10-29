import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
import numpy as np
from tools.junction_bench import knot
from linework.pipeline import Options, process_icon
import linework.joints as JT
import linework.finisher as FN

def debug_try_accept(cand, J, before, orig_try, st, doctor, D, ink_of, start):
    ink2 = ink_of(cand)
    s2 = doctor.soft(ink2)
    def tol(): return max(4.0, 0.003 * max(doctor.area, 1), 0.006 * st["cur"])
    t2 = FN._topo(cand)
    J2 = JT.nearest(cand, J.xy, 1.5 * J.w) if hasattr(JT, 'nearest') else None
    ex, mi = JT._ink_maps(ink2, D)
    after = [] if J2 is None else JT.check_joint(cand, J2, ex, mi)
    print(f"DEBUG try_accept J={J.kind} at {J.xy[:2]}: before={before} after={after} s2={s2:.1f} cur={st['cur']:.1f} tol={tol():.1f} t2={t2} st_topo={st['topo']}")

# Run knot directly
g = knot()
r = process_icon(g, Options(), name='knot')
print("KNOT DONE, unresolved:", len(r['metrics']['joins']['unresolved']), flush=True)
