import argparse, json, sys, time
import cv2, numpy as np
from .pipeline import Options, process_icon, process_sheet, load_gray
from .model import Model


def main():
    ap = argparse.ArgumentParser(prog="linework", description="Raster line-art -> centerline SVG")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="out.svg")
    ap.add_argument("-q", "--quality", default="standard", choices=["fast", "standard", "precise"])
    a = ap.parse_args()
    g = load_gray(open(a.input, "rb").read())
    opts = Options(quality=a.quality)
    W, H, jobs = process_sheet(g, opts, emit=lambda **k: print(k.get("msg")))
    allp = Model([], W, H)
    for k, crop, off in jobs:
        r = process_icon(crop, opts, emit=lambda **kw: print(f"[{kw['icon']}] {kw['engine']}: {kw['msg']}"), name=f"icon{k+1}")
        allp.paths += r["model"].translate(*off).paths
    open(a.output, "w").write(allp.svg(pretty=True))
    print("wrote", a.output)


if __name__ == "__main__":
    main()
