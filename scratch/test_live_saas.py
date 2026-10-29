import urllib.request, json, time, io

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\samples\basic-set.png', 'rb') as f:
    img_data = f.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = io.BytesIO()
body.write(f'--{boundary}\r\n'.encode())
body.write(b'Content-Disposition: form-data; name="file"; filename="basic-set.png"\r\n')
body.write(b'Content-Type: image/png\r\n\r\n')
body.write(img_data)
body.write(f'\r\n--{boundary}\r\n'.encode())
body.write(b'Content-Disposition: form-data; name="quality"\r\n\r\n')
body.write(b'fast\r\n')
body.write(f'--{boundary}--\r\n'.encode())
data = body.getvalue()

req = urllib.request.Request('http://127.0.0.1:8000/api/jobs', data=data, headers={
    'Content-Type': f'multipart/form-data; boundary={boundary}'
})
res = urllib.request.urlopen(req)
job_info = json.loads(res.read().decode())
job_id = job_info['id']
print('Job created:', job_id)

for _ in range(40):
    time.sleep(1)
    req2 = urllib.request.urlopen(f'http://127.0.0.1:8000/api/jobs/{job_id}')
    j = json.loads(req2.read().decode())
    if j.get('status') == 'done':
        print('Job done! Audit:', j.get('audit'))
        req_tpl = urllib.request.urlopen(f'http://127.0.0.1:8000/api/jobs/{job_id}/template.svg?preset=cyber')
        svg = req_tpl.read().decode()
        print('Template SVG length:', len(svg), 'contains preset cyber:', 'cyber' in svg.lower() or '#00f5a0' in svg.lower())
        break
    elif j.get('status') == 'error':
        print('Job error:', j.get('error'))
        break
