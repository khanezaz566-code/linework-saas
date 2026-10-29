import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, cv2
import numpy as np

from linework import trace as T
from linework import chains as CH
from linework import fitting as FIT
from linework.pipeline import Options, _process_icon

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]

ink = T.ink_map(crop)
br = T.refined_branches(ink)
chains, W0 = CH.build_chains(br)

m_init = FIT.initial_model(chains, ink)
print(f"\n3. initial_model: {len(m_init.paths)} paths")
for i, p in enumerate(m_init.paths):
    print(f"   path {i}: closed={p.closed} len={len(p.A)} start={p.A[0].round(1)} end={p.A[-1].round(1)}")
    for ki in range(len(p.A)):
        print(f"      anchor {ki}: A={p.A[ki].round(1)} Hin={p.Hin[ki].round(1)} Hout={p.Hout[ki].round(1)}")
