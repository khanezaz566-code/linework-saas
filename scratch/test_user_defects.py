import os, sys, cv2
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
from linework.pipeline import Options, process_icon

for i in range(1, 6):
    fn = f"samples/defect_icon_{i}.png"
    if not os.path.exists(fn):
        continue
    g = cv2.imread(fn, cv2.IMREAD_GRAYSCALE)
    r = process_icon(g, Options(), name=f"defect_{i}")
    m = r['model']
    jn = r['metrics'].get('joins', {})
    total = jn.get('total', 0)
    clean = jn.get('clean_first', 0)
    repaired = sum((jn.get('fixed') or {}).values())
    unresolved = len(jn.get('unresolved', []))
    print(f"defect_icon_{i}: IoU={r['metrics']['iou']*100:.2f}% | paths={len(m.paths)} | joins total={total} clean={clean} repaired={repaired} unresolved={unresolved}", flush=True)
