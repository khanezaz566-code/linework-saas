import json, os, glob

jid = '0a2b06637601'
for k in range(10):
    svg_p = f'data/{jid}/icon_{k}.svg'
    if os.path.exists(svg_p):
        with open(svg_p) as f:
            txt = f.read()
        print(f"=== {jid} icon {k} ===")
        print(txt)
