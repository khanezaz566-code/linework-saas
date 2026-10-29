import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework.doctor import Doctor, ink_of
from linework import edit as E
from linework import rings as RG
from linework import finisher as FN
from linework import joints as JN
from linework import structfix as SF

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
D = T.ink_map(crop)
w0 = estimate_width(D)
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
print(f"w0={w0:.1f}, k={k:.3f}, small shape={small.shape}")

# Now let's trace `small`
D_sm = T.ink_map(small)
w_est = estimate_width(D_sm)
print(f"w_est on small: {w_est:.2f}")

br = T.refined_branches(D_sm)
chains, W0 = CH.build_chains(br)
mod = FIT.initial_model(chains, D_sm, sigma=opts.sigma * 1.0 * 0.6, err=0.3)
print(f"\nInitial model: {len(mod.paths)} paths, W0={W0:.2f}")

def dump_paths(stage, m):
    print(f"\n=== {stage} ===")
    for i, p in enumerate(m.paths):
        print(f"  P{i}: len={len(p.A)} start={p.A[0].round(1)} Hin0={p.Hin[0].round(1)} Hout0={p.Hout[0].round(1)} | end={p.A[-1].round(1)} Hin1={p.Hin[-1].round(1)} Hout1={p.Hout[-1].round(1)}")

dump_paths("Initial", mod)

# Rings
doc = Doctor(D_sm, sens=opts.sens)
found = RG.detect_rings(D_sm, w_est)
print(f"Rings found: {len(found)}")

# Doctor round 1 & 2
state = dict(model=mod, ink=ink_of(mod), cur=doc.soft(ink_of(mod)))
for rnd in range(2):
    rep = doc.diagnose(state["model"], state["ink"])
    for cmd in Doctor.commands(rep):
        try:
            new, _ = E.execute(state["model"], cmd, D_sm)
            s2 = doc.soft(ink_of(new))
            if s2 <= state["cur"] + 2.0:
                state.update(model=new, ink=ink_of(new), cur=s2)
        except Exception:
            pass
    # cosmetic
    rep = doc.diagnose(state["model"], state["ink"])
    for cmd in Doctor.cosmetic_commands(rep):
        try:
            new, _ = E.execute(state["model"], cmd, D_sm)
            s2 = doc.soft(ink_of(new))
            if s2 <= state["cur"] + 2.0:
                state.update(model=new, ink=ink_of(new), cur=s2)
        except Exception:
            pass
dump_paths("After Doctor", state["model"])

# Structure engine
m6, ink6, cur6, sx = SF.run_structure_engine(state["model"], D_sm, doc, ink_of, state["cur"], W0, time_ok=lambda: True)
state.update(model=m6, ink=ink6, cur=cur6)
dump_paths("After Structfix", state["model"])

# Finisher
m3, ink3, cur3, fin = FN.finish(state["model"], D_sm, doc, ink_of, state["cur"], W0, time_ok=lambda: True)
state.update(model=m3, ink=ink3, cur=cur3)
dump_paths("After Finisher", state["model"])

# Joints
m5, ink5, cur5, jn = JN.run_join_engine(state["model"], D_sm, doc, ink_of, state["cur"], W0, time_ok=lambda: True)
state.update(model=m5, ink=ink5, cur=cur5)
dump_paths("After Joints", state["model"])
print("Joints rep:", jn)
