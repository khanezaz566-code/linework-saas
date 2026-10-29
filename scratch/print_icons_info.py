import json

j = json.loads(open('data/aca01e4ff5aa/job.json').read())
for ic in j['icons']:
    k = ic['k']
    box = ic['box']
    m = ic['metrics']
    print(f"Icon {k}: box={box} paths={m['paths']} nodes={m['nodes']}")
