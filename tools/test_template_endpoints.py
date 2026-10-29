import urllib.request, json, time

# 1. Test Presets API
req = urllib.request.Request('http://127.0.0.1:8000/api/template/presets')
with urllib.request.urlopen(req) as resp:
    presets = json.loads(resp.read().decode())
    print("Presets API ok:", list(presets.keys()))

# 2. Run a job
req2 = urllib.request.Request('http://127.0.0.1:8000/api/samples/basic-set?quality=fast&fresh=true', data=b'', method='POST')
with urllib.request.urlopen(req2) as resp2:
    res = json.loads(resp2.read().decode())
    job_id = res['id']
    print("Started job:", job_id)

for _ in range(40):
    time.sleep(1)
    req_status = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}')
    with urllib.request.urlopen(req_status) as resp_st:
        j = json.loads(resp_st.read().decode())
        if j['status'] == 'done':
            print("Job finished! Icons:", len(j['icons']))
            break

# 3. Test template.svg endpoint
req_tpl_svg = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}/template.svg?preset=cyber&title=Neon+Icons')
with urllib.request.urlopen(req_tpl_svg) as resp_svg:
    svg_data = resp_svg.read().decode()
    assert '<svg' in svg_data and '</svg>' in svg_data
    print("Template SVG endpoint ok! Length:", len(svg_data))

# 4. Test template.eps endpoint
req_tpl_eps = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}/template.eps?preset=gold&title=Gold+Icons&download=1')
with urllib.request.urlopen(req_tpl_eps) as resp_eps:
    eps_data = resp_eps.read().decode()
    assert '%!PS-Adobe-3.0' in eps_data
    print("Template EPS endpoint ok! Length:", len(eps_data))

# 5. Test result.eps endpoint
req_res_eps = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}/result.eps?download=1')
with urllib.request.urlopen(req_res_eps) as resp_reps:
    reps_data = resp_reps.read().decode()
    assert '%!PS-Adobe-3.0' in reps_data
    print("Result sheet EPS endpoint ok! Length:", len(reps_data))

# 6. Test download.zip endpoint containing EPS & Template
import zipfile, io
req_zip = urllib.request.Request(f'http://127.0.0.1:8000/api/jobs/{job_id}/download.zip')
with urllib.request.urlopen(req_zip) as resp_zip:
    zip_bytes = resp_zip.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        print("Zip entries:", names)
        assert 'sheet.svg' in names
        assert 'sheet.eps' in names
        assert 'presentation-template.svg' in names
        assert 'presentation-template.eps' in names
print("All endpoints verified successfully!")
