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
from linework import finisher as FN

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
w0 = estimate_width(T.ink_map(crop))
opts = Options(**job['options'])
k = opts.norm_stroke / w0
H, W = crop.shape
small = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
D_sm = T.ink_map(small)

br = T.refined_branches(D_sm)
chains, W0 = CH.build_chains(br)
mod = FIT.initial_model(chains, D_sm, sigma=opts.sigma * 1.0 * 0.6, err=0.3)

# Let's inspect FN.fix_end on Path 0 end 1 and Path 4 end 1
m_fix0 = FN.fix_end(mod, 0, 1)
print("fix_end(mod, 0, 1) result:", "None" if m_fix0 is None else f"len={len(m_fix0.paths[0].A)}")
if m_fix0 is not None:
    print("   old p0 end:", mod.paths[0].A[-1].round(2))
    print("   new p0 end:", m_fix0.paths[0].A[-1].round(2))
    print("   new p0 Hin[-1]:", m_fix0.paths[0].Hin[-1].round(2))

m_fix4 = FN.fix_end(mod, 4, 1)
print("fix_end(mod, 4, 1) result:", "None" if m_fix4 is None else f"len={len(m_fix4.paths[4].A)}")
if m_fix4 is not None:
    print("   old p4 end:", mod.paths[4].A[-1].round(2))
    print("   new p4 end:", m_fix4.paths[4].A[-1].round(2))
    print("   new p4 Hin[-1]:", m_fix4.paths[4].Hin[-1].round(2))
