import json
from pathlib import Path

j = json.loads(Path('data/aca01e4ff5aa/job.json').read_text('utf-8'))
for ic in j['icons']:
    k = ic['k']
    met = ic.get('metrics', {})
    jn = met.get('joins', {})
    st = met.get('structure', {})
    fin = met.get('finisher', {})
    print(f"Icon {k}: IoU={ic.get('iou', 0)*100:.2f}% | paths={met.get('paths')} nodes={met.get('nodes')} | joins total={jn.get('total')} clean={jn.get('clean_first')} fixed={sum((jn.get('fixed') or {}).values())} unres={len(jn.get('unresolved', []))} | struct found={st.get('found')} fixed={st.get('fixed')} unres={len(st.get('unresolved', []))}")
