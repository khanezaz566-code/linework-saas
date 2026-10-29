import sys, os, time
sys.path.insert(0, ".")
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import ICONS
from linework.pipeline import process_icon, Options

for n, f in ICONS.items():
    t0 = time.time()
    g = f()
    r = process_icon(g, Options(), name=n)
    dt = time.time() - t0
    jc = r['metrics']['joins']
    failing = [(f['kind'], round(f['x'], 1), round(f['y'], 1), f['reasons']) for f in jc['failing']]
    print(f"{n:6s} ({dt:.2f}s): joints={jc['joints']}, bad {jc['bad_before']} -> {jc['bad_after']}, fixed {jc['fixed']}, FAILING={failing}", flush=True)
