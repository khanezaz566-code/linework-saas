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

# R1
rep = doc.diagnose(state["model"], state["ink"])
for cmd in Doctor.commands(rep):
    new, _ = E.execute(state["model"], cmd, D_sm)
    state.update(model=new, ink=ink_of(new), cur=doc.soft(ink_of(new)))
new, _ = E.execute(state["model"], dict(op="refine_all", kw=dict(iters=22, taus=(1.0, 0.5, 0.35))), D_sm)
state.update(model=new, ink=ink_of(new), cur=doc.soft(ink_of(new)))
rep = doc.diagnose(state["model"], state["ink"])
for cmd in Doctor.cosmetic_commands(rep):
    new, _ = E.execute(state["model"], cmd, D_sm)
    state.update(model=new, ink=ink_of(new), cur=doc.soft(ink_of(new)))

# Now check Doctor diagnose at start of R2:
rep2 = doc.diagnose(state["model"], state["ink"])
print("R2 rep['redundant']:", rep2["redundant"])
print("R2 rep['tails']:", rep2["tails"])
print("R2 commands:", Doctor.commands(rep2))
