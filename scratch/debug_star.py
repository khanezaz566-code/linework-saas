import sys, os
sys.path.insert(0, ".")
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import star
from linework.pipeline import process_icon, Options
from linework import joincheck as JC
from linework import finisher as FN
from linework.trace import ink_map
from linework.doctor import Doctor
from linework.render import render_gray
from linework.model import Model

g = star()
r = process_icon(g, Options(finish=True, joincheck=False), name="star")
m = r["model"]
D = ink_map(g)
doc = Doctor(D)
def ink_of(mod):
    return render_gray(mod.svg(), g.shape[1], g.shape[0]) < 128

cur = doc.soft(ink_of(m))
joints = JC.inspect(m, D, ink_of(m))
print(f"Pre-JC joints: {len(joints)}, bad: {JC.bad_count(joints)}")
for j in joints:
    if j["reasons"]:
        print("  ", j["kind"], f"({j['x']:.1f}, {j['y']:.1f})", "reasons:", j["reasons"], "ends:", j["ends"])

m_after, ink_after, cur_after, rep = JC.run(m, D, doc, ink_of, cur, r["metrics"]["stroke_width"])
print("\nJC Report:", rep["bad_before"], "->", rep["bad_after"], "fixed:", rep["fixed"])
print("Failing joins:")
for f in rep["failing"]:
    print("  FAIL:", f["kind"], f"({f['x']:.1f}, {f['y']:.1f})", f["reasons"])
