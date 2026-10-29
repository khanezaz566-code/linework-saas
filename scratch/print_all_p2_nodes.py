import sys, os
sys.path.insert(0, os.path.abspath('.'))
import cv2, numpy as np, json
from linework.model import Path

data0 = json.load(open('scratch/m0_current.json'))
p2 = Path.from_dict(data0['paths'][2])
print("p2 has nodes count:", len(p2.A))
for i in range(len(p2.A)):
    print(f"Node {i}: A={np.round(p2.A[i], 1)}, Hin={np.round(p2.Hin[i], 1)}, Hout={np.round(p2.Hout[i], 1)}")
