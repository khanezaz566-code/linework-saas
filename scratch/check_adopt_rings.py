import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, rings as RG
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains
from linework.fitting import initial_model
from linework.doctor import Doctor
from linework.pipeline import ink_of
from linework.split import estimate_width

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)

for idx in [0, 2]:
    k, crop, off = jobs[idx]
    D = ink_map(crop)
    w_est = estimate_width(D)
    doc = Doctor(D)
    br = refined_branches(D)
    chs, W0 = build_chains(br)
    m0 = initial_model(chs, D, sigma=1.2, err=0.3)
    cur = doc.soft(ink_of(m0))
    found = RG.detect_rings(D, w_est)
    print(f"=== ICON {idx} (cur={cur:.1f}, area={doc.area}) ===")
    for ring in sorted(found, key=lambda r: -r["r"]):
        new = RG.apply_ring(m0, ring)
        s2 = doc.soft(ink_of(new))
        print(f"  ring r={ring['r']:.2f}, cx={ring['cx']:.1f}, cy={ring['cy']:.1f}, w={ring['w']:.2f}, sup={ring['support']:.3f} -> s2={s2:.1f} (diff={s2 - cur:+.1f})")
