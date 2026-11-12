import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.diag_join_problems import run
idx = int(sys.argv[1]); jq = int(sys.argv[2])
r = run((idx, jq))
r.pop("unres", None)
print(json.dumps(r))
