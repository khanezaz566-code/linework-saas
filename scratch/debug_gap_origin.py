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
from linework import structfix as SF

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
opts.fresh = True
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D_sm = T.ink_map(small)

br = T.refined_branches(D_sm)
chains, W0 = CH.build_chains(br)
mod = FIT.initial_model(chains, D_sm, sigma=opts.sigma * 1.0 * 0.6, err=0.3)

doc = Doctor(D_sm, sens=opts.sens)
state = dict(model=mod, ink=ink_of(mod), cur=doc.soft(ink_of(mod)))

def check(tag):
    m = state["model"]
    p0 = m.paths[0]
    # find path with end near (65, 265)
    candidates = []
    for i, p in enumerate(m.paths):
        d0 = np.linalg.norm(p.A[0] - np.array([65, 265]))
        d1 = np.linalg.norm(p.A[-1] - np.array([65, 265]))
        if min(d0, d1) < 15:
            candidates.append((i, d0, d1, p.A[0] if d0 < d1 else p.A[-1]))
    print(f"[{tag}] paths near bottom-left corner:")
    for i, d0, d1, pt in candidates:
        p = m.paths[i]
        print(f"   P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")
        if d0 < d1:
            print(f"       near end0: A[0]={p.A[0].round(2)} Hout[0]={p.Hout[0].round(2)} A[1]={p.A[1].round(2)}")
        else:
            print(f"       near end1: A[-2]={p.A[-2].round(2)} Hin[-1]={p.Hin[-1].round(2)} A[-1]={p.A[-1].round(2)}")
    if len(candidates) >= 2:
        gap = np.linalg.norm(candidates[0][3] - candidates[1][3])
        print(f"   GAP between candidates: {gap:.3f} px")

check("Initial")

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
    check(f"After Doctor R{rnd+1} dedupe")

    # Global gradient fit
    new, _ = E.execute(state["model"], dict(op="refine_all", kw=dict(iters=22, taus=(1.0, 0.5, 0.35))), D_sm)
    s2 = doc.soft(ink_of(new))
    if s2 <= state["cur"] + 0.0:
        state.update(model=new, ink=ink_of(new), cur=s2)
    check(f"After Doctor R{rnd+1} gradient fit")

    # Cosmetic commands
    rep = doc.diagnose(state["model"], state["ink"])
    for cmd in Doctor.cosmetic_commands(rep):
        try:
            new, _ = E.execute(state["model"], cmd, D_sm)
            s2 = doc.soft(ink_of(new))
            if s2 <= state["cur"] + 2.0:
                state.update(model=new, ink=ink_of(new), cur=s2)
        except Exception:
            pass
    check(f"After Doctor R{rnd+1} cosmetic")

m6, ink6, cur6, sx = SF.run_structure_engine(state["model"], D_sm, doc, ink_of, state["cur"], W0, time_ok=lambda: True)
state.update(model=m6, ink=ink6, cur=cur6)
check("After Structfix")
