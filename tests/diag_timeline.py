import sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from linework.pipeline import process_icon, Options
from tests.diag_join_problems import make

idx = int(sys.argv[1]); jq = int(sys.argv[2])
img, name = make(idx, jq or None)
t0 = time.time(); c0 = time.process_time()
def emit(**kw):
    msg = kw.get("msg", "")
    print(f"[{time.time()-t0:6.1f}s wall {time.process_time()-c0:6.1f}s cpu] {kw.get('engine','')}: {msg[:110]}", flush=True)
r = process_icon(img, Options(fresh=True, memory=False, quality="standard", joins=True, decision=True), emit=emit, name=name)
print("total", round(time.time() - t0, 1), "iou", r["metrics"]["iou"], "joins", r["metrics"]["joins"]["total"])
