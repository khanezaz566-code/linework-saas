import cv2, json, sys
sys.path.insert(0, '.')
from linework.pipeline import Options
from linework.doctor import Doctor, ink_of
from linework.fitting import initial_model
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains

crop = cv2.imread('scratch/icon_crop_5.png', 0)
D = ink_map(crop)
branches = refined_branches(D)
chains, w_est = build_chains(branches, 10.0)
m0 = initial_model(chains, D)
doc = Doctor(D)
rep = doc.diagnose(m0, ink_of(m0))
print("Diagnose m0 kinks:")
for k in rep['kinks']:
    print(" ", k)
