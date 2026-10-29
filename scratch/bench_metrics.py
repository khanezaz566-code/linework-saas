import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import ICONS
from linework.pipeline import Options, process_icon

for n, f in ICONS.items():
    g = f()
    r = process_icon(g, Options(), name=n)
    jn = r['metrics'].get('joins', {})
    total = jn.get('total', 0)
    clean = jn.get('clean_first', 0)
    repaired = sum((jn.get('fixed') or {}).values())
    unresolved = len(jn.get('unresolved', []))
    unres_reasons = [u.get('reasons') for u in jn.get('unresolved', [])]
    print(f"{n:6s}: iou={r['metrics']['iou']*100:.2f}% | total={total} clean={clean} repaired={repaired} unresolved={unresolved} | reasons={unres_reasons}", flush=True)
