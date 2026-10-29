import numpy as np
import tests.test_finisher as tf
from linework.finisher import excess_ends, corner_pairs, merge_corners
import linework.finisher as FN
from linework.doctor import Doctor, ink_of
from linework.model import Model

apex = np.array([100., 40.])
import math
a = apex + 90 * np.array([math.sin(math.radians(15)), math.cos(math.radians(15))])
b = apex + 90 * np.array([-math.sin(math.radians(15)), math.cos(math.radians(15))])
ideal = Model([tf.line(a, apex, 10), tf.line(apex, b, 10)], 200, 160)
D = tf.src(ideal)
doc = Doctor(D)

over = Model([tf.line(a, apex + 8 * (apex - a) / np.linalg.norm(apex - a), 10), tf.line(apex, b, 10)], 200, 160)
ink = ink_of(over)

for i, p in enumerate(over.paths):
    tree, P, _ = FN._others_tree(over, i)
    for e in (0, 1):
        pt = p.A[0] if e == 0 else p.A[-1]
        iy, ix = int(round(pt[1])), int(round(pt[0]))
        d_src = D[iy, ix] if 0 <= iy < D.shape[0] and 0 <= ix < D.shape[1] else 0.0
        d_other = float(tree.query(pt)[0]) if tree is not None else 999.0
        print(f"over path {i} end {e}: pt={pt}, D={d_src:.2f}, dist_other={d_other:.2f}")

print("Testing test_thick_tip_is_pulled_back_and_corner_is_merged:")
tf.test_thick_tip_is_pulled_back_and_corner_is_merged()
print("PASS test_thick_tip!")
