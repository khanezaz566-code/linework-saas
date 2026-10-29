import sys, os, json
sys.path.insert(0, ".")
from tools.junction_bench import knot
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.render import render_gray
from linework.model import Model
from linework import finisher as FN
from linework import joincheck as JC
import cv2

g = knot()
D = ink_map(g)
doc = Doctor(D)
def ink_of(mod):
    return render_gray(mod.svg(), g.shape[1], g.shape[0]) < 128

CACHE = "scratch/knot_m0.json"
if os.path.exists(CACHE):
    m0 = Model.from_json(json.load(open(CACHE)))
else:
    Du = ink_map(cv2.resize(g, (g.shape[1] * 2, g.shape[0] * 2), interpolation=cv2.INTER_CUBIC))
    br = refined_branches(Du)
    chains, W0 = build_chains(br)
    m0 = initial_model(chains, Du, sigma=0.6 * 2, err=0.3 * 2).scaled(0.5, g.shape[1], g.shape[0])
    m0, _, _, _ = FN.finish(m0, D, doc, ink_of, doc.soft(ink_of(m0)), 10.0)
    with open(CACHE, "w") as f:
        json.dump(m0.to_json(), f)

print(f"Loaded knot m0 with {len(m0.paths)} paths")
cur = doc.soft(ink_of(m0))
m_after, ink_after, cur_after, rep = JC.run(m0, D, doc, ink_of, cur, 10.0)
print('JC Report:', rep['bad_before'], '->', rep['bad_after'], 'fixed:', rep['fixed'])
for item in rep['items']:
    print('  item:', item)
print('Failing:')
for f in rep['failing']:
    print('  fail:', f)
