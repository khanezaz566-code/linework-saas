import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np
from linework.pipeline import Options, _process_icon_scaled, _process_icon
from linework.split import estimate_width
from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework.doctor import Doctor, ink_of
from linework import edit as E
from linework import finisher as FN
from linework import joints as JN
from linework import structfix as SF

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

# Let's run _process_icon on small with an emit logger to see what steps run
logs = []
def my_emit(engine, msg, **kw):
    logs.append((engine, msg, kw))

res = _process_icon(small, opts, emit=my_emit, name="icon_5_small")
m_res = res["model"]

print("Processed small result paths:", len(m_res.paths))
for i, p in enumerate(m_res.paths):
    print(f"P{i}: len={len(p.A)} start={p.A[0].round(2)} end={p.A[-1].round(2)}")

print("\n--- Finisher & Joints logs ---")
for eng, msg, kw in logs:
    if eng in ("Finisher", "doctor", "edit", "trace") and any(w in msg.lower() for w in ["joint", "finish", "corner", "unite", "round"]):
        print(f"[{eng}] {msg}")
