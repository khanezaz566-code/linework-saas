import json, cv2
from pathlib import Path

d = Path('data/aca01e4ff5aa')
j = json.loads((d / 'job.json').read_text('utf-8'))
orig = cv2.imread(str(d / 'original.png'), 0)

for ic in j['icons']:
    k = ic['k']
    x0, y0, x1, y1 = ic['box']
    crop = orig[y0:y1, x0:x1]
    cv2.imwrite(f'scratch/marine_icon_{k}.png', crop)
    print(f"Icon {k}: box={ic['box']} size={x1-x0}x{y1-y0}")
