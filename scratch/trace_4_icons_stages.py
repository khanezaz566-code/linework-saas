import sys, os, cv2, numpy as np
sys.path.insert(0, os.getcwd())
from linework import pipeline as P, edit as E

gray = cv2.imread("data/e6c0d92fb976/original.png", 0)
W, H, jobs = P.process_sheet(gray)
crop3 = jobs[3][1]

orig_exec = E.execute
def trace_exec(model, cmd, D):
    new, res = orig_exec(model, cmd, D)
    # Check if W or SW endpoints moved apart
    for name, pt in [("N", [236.5, 128.0]), ("W", [124.4, 236.1]), ("SW", [160.9, 313.1]), ("NW", [179.9, 179.7])]:
        old_pts = [p.A[e] for p in model.paths if not p.closed for e in (0, -1) if np.linalg.norm(p.A[e] - pt) < 16]
        new_pts = [p.A[e] for p in new.paths if not p.closed for e in (0, -1) if np.linalg.norm(p.A[e] - pt) < 16]
        if len(old_pts) >= 2 and len(new_pts) >= 2:
            d_old = np.linalg.norm(old_pts[0] - old_pts[1])
            d_new = np.linalg.norm(new_pts[0] - new_pts[1])
            if abs(d_new - d_old) > 0.5:
                print(f"  cmd={cmd['op']} ({cmd.get('path')}) moved {name}: gap {d_old:.2f} -> {d_new:.2f}, new_pts={[x.round(1).tolist() for x in new_pts]}")
    return new, res

E.execute = trace_exec
P.process_icon(crop3, P.Options(quality="standard", memory=False, fresh=True), name="icon_3")
