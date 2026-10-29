import json, os, glob
import numpy as np

for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    print(f"\n=================== JOB {jid} ===================")
    for k in range(10):
        jp = f'data/{jid}/icon_{k}.json'
        if not os.path.exists(jp): continue
        with open(jp) as f:
            d = json.load(f)
        # Find all branch endpoints
        ends = []
        for pi, p in enumerate(d['paths']):
            A = np.array(p['A'])
            if not p['closed']:
                ends.append((pi, 0, A[0]))
                ends.append((pi, len(A)-1, A[-1]))
            else:
                for ai, a in enumerate(A):
                    ends.append((pi, ai, a))
        
        # Check clusters of endpoints
        for i in range(len(ends)):
            p1, e1, a1 = ends[i]
            for j in range(i+1, len(ends)):
                p2, e2, a2 = ends[j]
                if p1 == p2: continue
                dist = np.linalg.norm(a1 - a2)
                if dist < 2.0:
                    # found meeting point!
                    # check if a 3rd path meets here
                    for m in range(j+1, len(ends)):
                        p3, e3, a3 = ends[m]
                        if p3 in (p1, p2): continue
                        if np.linalg.norm(a1 - a3) < 2.0:
                            print(f"Job {jid} Icon {k}: 3-way meeting at {a1.round(1)}: paths ({p1}, {p2}, {p3})")
