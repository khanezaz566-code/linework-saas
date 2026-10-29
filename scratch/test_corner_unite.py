import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.abspath('.'))

from scratch.trace_cuff_defect import small, opts, Du
from linework.pipeline import _process_icon
from linework.model import Model, Path
from linework.doctor import Doctor, ink_of
import linework.joints as J
import linework.finisher as FN

def find_corner_continuation_pairs(m: Model, J_joint: J.Joint, D):
    """Find a corner pair among the ends of multi-branch joint J that forms a clean corner."""
    ends = J_joint.ends
    if len(ends) < 3:
        return []
    
    best_pair = None
    best_score = 999.0
    
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            j, ej = ends[y]
            if i >= len(m.paths) or j >= len(m.paths) or i == j:
                continue
            P, Q = m.paths[i], m.paths[j]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            w = max(wa, wb)
            
            # End geometry: point and inward direction (pointing away from end into stroke)
            gP = FN.end_geometry(P, ei)
            gQ = FN.end_geometry(Q, ej)
            cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei==0 else -1], J._local_end_dir(P, ei))
            cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ej==0 else -1], J._local_end_dir(Q, ej))
            
            # Corner condition: cross product >= 0.5 (angle not collinear)
            cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
            if abs(cr) < 0.40:
                continue
            
            # Ray intersection
            # Ray P: cP + sP * tP; Ray Q: cQ + sQ * tQ
            # We want ray entering end P and ray entering end Q to meet:
            # Note: tP and tQ from end_geometry point OUTWARD from the end (away from stroke),
            # or INWARD? Let's check FN.end_geometry:
            # Let's verify direction:
            den = cr
            sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / den
            Xc = cP + sP * tP
            
            d_mid = float(np.linalg.norm(Xc - J_joint.xy))
            if d_mid > 1.25 * w:
                continue
            
            # Score by how close to 90 degrees (dot product close to 0)
            dot = float(tP @ tQ)
            score = abs(dot)  # 0.0 is perfect 90 degree corner
            
            if score < best_score:
                best_score = score
                best_pair = (i, ei, j, ej)
                
    if best_pair is not None and best_score < 0.65: # within ~40-140 degrees
        return [best_pair]
    return []

# Test on Icon 0
print("Testing on Icon 0...")
res0 = _process_icon(small, opts, emit=lambda **k: None, name='ic0')
m0 = res0['model']
js0 = J.find_joints(m0)
print(f"Found {len(js0)} joints in Icon 0")
for idx, j in enumerate(js0):
    cp = find_corner_continuation_pairs(m0, j, Du)
    if cp:
        print(f"Joint {idx} at {np.round(j.xy, 1)} has corner pair: {cp}")
        m_fixed = FN.merge_corners(m0, cp)
        # Lock T-stem
        m_fixed = J.lock_joints(m_fixed)
        
        img_orig = (ink_of(m0) * 255).astype(np.uint8)
        img_fixed = (ink_of(m_fixed) * 255).astype(np.uint8)
        c1 = cv2.resize(img_orig[95:135, 70:110], (200, 200), interpolation=cv2.INTER_NEAREST)
        c2 = cv2.resize(img_fixed[95:135, 70:110], (200, 200), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite('scratch/test_cuff_fixed0.png', np.hstack([c1, c2]))
        print("Saved test_cuff_fixed0.png!")
