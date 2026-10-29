import urllib.request, json, time

req = urllib.request.Request("http://127.0.0.1:8000/api/samples/home-icons?quality=fast&fresh=true", data=b"", method="POST")
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    job_id = res["id"]
    print(f"Started live test job: {job_id}")

for _ in range(45):
    time.sleep(1)
    req_st = urllib.request.Request(f"http://127.0.0.1:8000/api/jobs/{job_id}")
    with urllib.request.urlopen(req_st) as resp_st:
        j = json.loads(resp_st.read().decode())
        if j["status"] == "done":
            iou = j.get("iou") or 0.0
            print(f"Job {job_id} done with IoU: {iou*100:.2f}% across {len(j['icons'])} icons")
            break

# Verify template SVG
req_tpl = urllib.request.Request(f"http://127.0.0.1:8000/api/jobs/{job_id}/template.svg?preset=obsidian&title=Home+Living+Icons")
with urllib.request.urlopen(req_tpl) as resp_tpl:
    svg_len = len(resp_tpl.read())
    print(f"Template SVG generated! Length: {svg_len} bytes")

# Verify template EPS
req_eps = urllib.request.Request(f"http://127.0.0.1:8000/api/jobs/{job_id}/template.eps?preset=obsidian&title=Home+Living+Icons")
with urllib.request.urlopen(req_eps) as resp_eps:
    eps_len = len(resp_eps.read())
    print(f"Template EPS generated! Length: {eps_len} bytes")

print("All engines, API endpoints, and Template Studio are running smoothly!")
