import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import knot, star, spool
from linework.pipeline import Options, process_icon
from linework.joints import find_joints, check_joint, _ink_maps
from linework.render import render_gray
from linework.trace import ink_map

def inspect(name, fn):
    g = fn()
    D = ink_map(g)
    r = process_icon(g, Options(), name=name)
    m = r['model']
    ink = render_gray(m.svg(), g.shape[1], g.shape[0]) < 128
    ex, mi = _ink_maps(ink, D)
    joints = find_joints(m)
    print(f"=== {name} ({len(joints)} joints) ===")
    for idx, J in enumerate(joints):
        bad = check_joint(m, J, ex, mi)
        if bad:
            print(f"  Joint #{idx} kind={J.kind} xy=({J.xy[0]:.1f},{J.xy[1]:.1f}) ends={J.ends} through={J.through} bad={bad}")
            for (i, e) in J.ends:
                end_p = m.paths[i].A[0] if e == 0 else m.paths[i].A[-1]
                others = [j for j in J.through if j != i] or J.through
                if others:
                    from linework.joints import _nearest_on
                    dists = [_nearest_on(m.paths[j], end_p)[1] for j in others]
                    print(f"    end ({i},{e}) at ({end_p[0]:.2f},{end_p[1]:.2f}) min dist to through: {min(dists):.3f}")

inspect("knot", knot)
inspect("star", star)
inspect("spool", spool)
