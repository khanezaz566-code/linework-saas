import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np

from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework.doctor import Doctor
from linework import edit as E
from linework import rings as RG
from linework import structfix as SF
from linework import finisher as FN
from linework import joints as JN
from linework import topology as Topo
from linework.pipeline import Options

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
ink = T.ink_map(crop)

br = T.refined_branches(ink)
chains, W0 = CH.build_chains(br)
mod = FIT.initial_model(chains, ink)

def print_corner(stage, m):
    print(f"\n=== Stage: {stage} ===")
    for i, p in enumerate(m.paths):
        # find path near (124, 480)
        dist0 = np.linalg.norm(p.A[0] - np.array([124, 480]))
        dist1 = np.linalg.norm(p.A[-1] - np.array([124, 480]))
        if dist0 < 60 or dist1 < 60:
            print(f"  path {i}: len={len(p.A)} start={p.A[0].round(2)} (Hout={p.Hout[0].round(2)}) | end={p.A[-1].round(2)} (Hin={p.Hin[-1].round(2)})")

print_corner("0. initial_model", mod)

# Rings
mod = RG.apply_rings(mod, ink)
print_corner("1. apply_rings", mod)

# Structfix
mod, sf_rep = SF.fix_structure(mod, ink)
print_corner("2. fix_structure", mod)

# Doctor / edit rounds
opts = Options(**job['options'])
for r in range(2):
    rep = Doctor.diagnose(mod, ink, sens=opts.sens)
    cmds = Doctor.commands(rep)
    mod = E.refine_all(mod, cmds)
    print_corner(f"3.{r} doctor refine", mod)

# Finisher
mod, fin_rep = FN.finish_model(mod, ink)
print_corner("4. finish_model", mod)

# Joints
mod = JN.snap_junctions(mod)
print_corner("5. snap_junctions", mod)
mod, jn_rep = JN.repair_model_joints(mod, ink)
print_corner("6. repair_model_joints", mod)

# Final topology guard
rep = Doctor.diagnose(mod, ink, sens=opts.sens)
cmds = [c for c in Doctor.cosmetic_commands(rep) if c["op"] in ("trim_tail", "merge_nodes", "weld")]
mod = E.refine_all(mod, cmds)
print_corner("7. final cosmetic refine", mod)
