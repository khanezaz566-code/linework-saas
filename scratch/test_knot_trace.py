import os, sys
sys.path.insert(0, '.')
os.environ["LINEWORK_MEMORY"] = "0"
from tools.junction_bench import knot
from linework.pipeline import Options, process_icon
from linework import joints as JT

g = knot()
# Run with tracing
r = process_icon(g, Options(), name='knot')
jn = r['metrics'].get('joins', {})
print("Knot joins report:", jn, flush=True)
