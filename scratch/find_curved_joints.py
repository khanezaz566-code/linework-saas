import json, os, glob
import cv2
import numpy as np

# Let's inspect the rendered SVG or result.svg of recent jobs
for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    jdir = f'data/{jid}'
    print(f"=== Job {jid} ===")
    for k in range(10):
        jp = f'{jdir}/icon_{k}.json'
        if not os.path.exists(jp): continue
        with open(jp) as f:
            d = json.load(f)
        for i, p in enumerate(d['paths']):
            A = np.array(p['A'])
            Hin = np.array(p['Hin'])
            Hout = np.array(p['Hout'])
            # Check if there are curved handles on straight lines
            for idx in range(len(A)):
                din = np.linalg.norm(A[idx] - Hin[idx])
                dout = np.linalg.norm(A[idx] - Hout[idx])
                if din > 1.0 or dout > 1.0:
                    pass
