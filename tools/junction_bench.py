"""Junction test bench: four icons drawn from clean vectors (hub with spokes, star with crossing bar, spool, knot).
The drawing IS the source, so every blob / lump / missing piece in the result is our own error."""
import cv2,numpy as np
S=4  # supersample for clean antialiasing
def canvas(w=320,h=320):return np.full((h*S,w*S),255,np.uint8)
def pl(g,pts,t=10,closed=False):
    cv2.polylines(g,[np.round(np.array(pts)*S).astype(np.int32)],closed,0,int(t*S),cv2.LINE_8)
    for p in pts:cv2.circle(g,tuple(np.round(np.array(p)*S).astype(int)),int(t*S/2),0,-1)  # round joins/caps
def ell(g,c,a,b,ang=0,s=0,e=360,t=10):
    cv2.ellipse(g,tuple(np.round(np.array(c)*S).astype(int)),(int(a*S),int(b*S)),ang,s,e,0,int(t*S),cv2.LINE_8)
def fin(g):return cv2.resize(g,(g.shape[1]//S,g.shape[0]//S),interpolation=cv2.INTER_AREA)
def hub():
    g=canvas();ell(g,(160,160),110,110);ell(g,(160,160),22,22)
    for k in range(8):
        a=k*np.pi/4+0.2;pl(g,[(160+24*np.cos(a),160+24*np.sin(a)),(160+108*np.cos(a),160+108*np.sin(a))])
    return fin(g)
def star():
    g=canvas();ell(g,(160,170),130,130,s=180,e=360)
    c=np.array([160,175]);pts=[]
    for k in range(10):
        r=95 if k%2==0 else 35;a=-np.pi/2+k*np.pi/5;pts.append(c+r*np.array([np.cos(a),np.sin(a)]))
    pl(g,pts,closed=True);ell(g,(160,175),12,12)
    pl(g,[(60,190),(260,190)])
    return fin(g)
def spool():
    g=canvas()
    for k in range(8):
        x=90+k*17;pl(g,[(x+22,70),(x-10,250)])
    pl(g,[(80,60),(250,60)]);pl(g,[(60,260),(230,260)]);pl(g,[(250,60),(250,270)]);pl(g,[(228,60),(214,252)])
    return fin(g)
def knot():
    g=canvas()
    pl(g,[(90,40),(90,280)]);pl(g,[(230,40),(230,280)])
    t=np.linspace(0,2*np.pi,200);x=160+95*np.sin(t);y=160+55*np.sin(2*t)
    pl(g,list(zip(x,y)),closed=True)
    x2=160+95*np.sin(t);y2=160+55*np.sin(2*t)+22
    pl(g,list(zip(x2,y2)),closed=True)
    return fin(g)

def ecg():
    g = canvas()
    pl(g, [(20, 150), (80, 150), (100, 100), (120, 190), (150, 40), (178, 250), (205, 100), (222, 150), (300, 150)])
    return fin(g)


def jar():
    g = canvas()
    pl(g, [(60, 110), (60, 60), (80, 40), (240, 40), (260, 60), (260, 110), (60, 110)])
    for x in (100, 140, 180, 220):
        pl(g, [(x, 48), (x, 110)])
    pl(g, [(75, 110), (75, 135), (60, 158)]); pl(g, [(245, 110), (245, 135), (260, 158)]); pl(g, [(75, 135), (245, 135)])
    pl(g, [(60, 158), (60, 290)]); pl(g, [(260, 158), (260, 290)])
    return fin(g)


def pen():
    g = canvas()
    pl(g, [(60, 260), (60, 215), (120, 150), (250, 20)]); pl(g, [(100, 285), (170, 215), (290, 95)])
    pl(g, [(120, 150), (170, 215)]); pl(g, [(130, 130), (225, 230)])
    return fin(g)


ICONS = dict(hub=hub, star=star, spool=spool, knot=knot, ecg=ecg, jar=jar, pen=pen)

if __name__ == "__main__":
    # usage: python tools/junction_bench.py <out_dir> [tag]
    import os, sys, collections
    os.environ.setdefault("LINEWORK_MEMORY", "0")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from linework.pipeline import Options, process_icon
    from linework.trace import ink_map
    from linework.render import render_gray
    out = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else "run"
    os.makedirs(out, exist_ok=True)
    for n, f in ICONS.items():
        g = f()  # clean vector drawing = the source; any extra ink in the result is our own error
        from linework import finisher as FN
        r0 = process_icon(g, Options(finish=False), name=n)
        r = process_icon(g, Options(), name=n)
        m = r["model"]
        print("   hooks (ends bent away from a straight stroke): before Finisher", len(FN.end_hooks(r0["model"])), "-> after", len(FN.end_hooks(m)))
        D = ink_map(g)
        ink = render_gray(m.svg(), g.shape[1], g.shape[0]) < 128
        ref = D > 0.5
        extra, miss = ink & ~ref, ref & ~ink
        cnt = collections.Counter((s["kind"], s["fixed"]) for s in r["metrics"]["finisher"]["sites"])
        jn = r["metrics"].get("joins", {})
        print("   joins: total", jn.get("total"), "clean at first look", jn.get("clean_first"), "repaired", sum((jn.get("fixed") or {}).values()), "unresolved", [u["reasons"] for u in jn.get("unresolved", [])])
        print(n, "match %.4f" % r["metrics"]["iou"], "extra ink px", int(extra.sum()), "missing px", int(miss.sum()), "paths", len(m.paths), dict(cnt))
        d = np.full(ref.shape + (3,), 255, np.uint8)
        d[ref & ink] = (200, 200, 200); d[miss] = (0, 0, 255); d[extra] = (255, 0, 0)  # grey ok, red missing, blue extra (BGR)
        cv2.imwrite(os.path.join(out, f"{tag}_{n}_diff.png"), cv2.resize(d, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
        im = cv2.cvtColor(cv2.resize(render_gray(m.svg(), g.shape[1], g.shape[0]), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), cv2.COLOR_GRAY2BGR)
        for p in m.paths:  # centrelines in blue, like the outline view of a vector editor
            cv2.polylines(im, [np.round(p.flat(0.5) * 2).astype(np.int32)], p.closed, (255, 80, 0), 1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(out, f"{tag}_{n}.png"), im)
