import sys, os
sys.path.insert(0, ".")
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import star
from linework.pipeline import process_icon, Options

r = process_icon(star(), Options(), name="star")
m = r["model"]
print(f"Star final paths: {len(m.paths)}")
for i, p in enumerate(m.paths):
    print(f"Path {i}: closed={p.closed}, len={len(p.A)}, length={p.length():.1f}, w={p.w:.1f}")
    print(f"   start={p.A[0]}, end={p.A[-1]}")
jc = r["metrics"]["joins"]
print("Failing joins:")
for f in jc["failing"]:
    print("  ", f)
