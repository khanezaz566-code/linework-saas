import urllib.request, json, time

req = urllib.request.Request('http://127.0.0.1:8000/api/samples/basic-set?quality=fast&fresh=true', data=b'', method='POST')
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    job_id = res['id']
    print('Started job:', job_id)

for _ in range(40):
    time.sleep(1)
    req2 = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}')
    with urllib.request.urlopen(req2) as resp2:
        j = json.loads(resp2.read().decode())
        print(f"Status: {j['status']}, done: {j.get('done')}/{len(j.get('icons', []))}")
        if j['status'] == 'done':
            print('Job completed! IOU:', j.get('iou'))
            for ic in j['icons']:
                print(f"Icon {ic['k']}: iou={ic.get('iou')}, from_mem={ic.get('metrics', {}).get('from_memory', False)}")
            break
