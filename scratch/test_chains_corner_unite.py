import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.trace import ink_map, refined_branches
from linework.chains import build_chains, global_width, resample, unit, line_inter
from linework.fitting import initial_model
from linework.doctor import Doctor, ink_of
from linework.pipeline import Options, _process_icon
from linework.split import estimate_width

# Let's inspect what happens if we patch chains.build_chains
import linework.chains as CH

orig_build_chains = CH.build_chains

def test_on_icon0():
    job = json.load(open('data/b95d5c14c7a9/job.json'))
    orig = cv2.imread('data/b95d5c14c7a9/original.png', 0)
    opts = Options(**job['options'])
    opts.fresh = True
    box = job['icons'][0]['box']
    crop = orig[box[1]:box[3], box[0]:box[2]]
    w0 = estimate_width(ink_map(crop))
    k = opts.norm_stroke / w0
    H, W = crop.shape
    small0 = cv2.resize(crop, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
    D = ink_map(small0)
    br = refined_branches(D)
    chains, W0 = build_chains(br)
    m = initial_model(chains, D, sigma=opts.sigma * 1.0, err=0.3)
    print("Default initial_model paths:", len(m.paths))
    img = (ink_of(m) * 255).astype(np.uint8)
    cv2.imwrite('scratch/chains_initial_orig.png', cv2.resize(img[95:130, 70:105], (200, 200), interpolation=cv2.INTER_NEAREST))

test_on_icon0()
