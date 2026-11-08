"""Google Colab / Kaggle High-Performance AI Worker for Linework AI
Runs on Google Colab (12.7 GB RAM, Intel Xeon CPU, GPU)
Exposes a Cloudflare tunnel and registers with your master Linework SaaS server on Render.
"""
import os
import sys
import time
import json
import base64
import threading
import subprocess
import re
import urllib.request
from pathlib import Path

# Set single thread per BLAS to maximize multi-icon throughput
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from linework.pipeline import Options, process_icon, process_sheet
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Linework AI High-Performance Compute Worker")

WORKER_SECRET = os.environ.get("LINEWORK_WORKER_SECRET", "linework_super_secret_2026")
MASTER_URL = os.environ.get("MASTER_SERVER_URL", "https://linework-saas.onrender.com").rstrip("/")

@app.get("/health")
def health():
    return {
        "ok": True,
        "type": "colab_high_ram",
        "cpu_count": os.cpu_count(),
        "time": time.time()
    }

@app.post("/process_icon")
async def process_icon_endpoint(request: Request):
    secret = request.headers.get("X-Worker-Secret")
    if secret != WORKER_SECRET:
        raise HTTPException(401, "Invalid worker secret")
        
    payload = await request.json()
    crop_b64 = payload.get("crop_b64")
    opts_dict = payload.get("options", {})
    off = payload.get("off", [0, 0])
    
    # Decode image
    img_bytes = base64.b64decode(crop_b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    crop = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    
    opts = Options(**opts_dict)
    
    # Process icon at full Colab speed
    start_t = time.time()
    try:
        from linework.pipeline import _process_single_crop
        # If pipeline has run_icon or process_icon
        from linework.pipeline import process_icon
        mj, metrics = process_icon(crop, opts)
        elapsed = time.time() - start_t
        
        # Serialize model joints and metrics
        return {
            "ok": True,
            "elapsed": round(elapsed, 3),
            "svg": mj.to_svg(opts.target_iou) if hasattr(mj, "to_svg") else "",
            "metrics": {
                "iou": getattr(metrics, "iou", None),
                "nodes": getattr(metrics, "nodes", None),
                "score": getattr(metrics, "score", None)
            }
        }
    except Exception as e:
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def start_tunnel_and_register(local_port=5000):
    print("[+] Checking for cloudflared...")
    # In Colab, cloudflared can be downloaded via apt or direct curl
    cf_path = Path("/usr/local/bin/cloudflared")
    if not cf_path.exists():
        cf_path = ROOT / "cloudflared"
    if not cf_path.exists():
        cf_path = ROOT / "cloudflared.exe"

    if not cf_path.exists():
        print("[+] Downloading cloudflared binary for Linux...")
        try:
            subprocess.run([
                "curl", "-L", "--output", "/usr/local/bin/cloudflared",
                "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
            ], check=True)
            subprocess.run(["chmod", "+x", "/usr/local/bin/cloudflared"], check=True)
            cf_path = Path("/usr/local/bin/cloudflared")
        except Exception as e:
            print("[-] Failed to download cloudflared:", e)
            return

    print(f"[+] Starting Cloudflare Tunnel on port {local_port}...")
    cmd = [str(cf_path), "tunnel", "--url", f"http://127.0.0.1:{local_port}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    
    tunnel_url = None
    for line in iter(proc.stdout.readline, ""):
        match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            break
            
    if not tunnel_url:
        print("[-] Could not obtain tunnel URL.")
        return

    print("\n" + "=" * 65)
    print(f"  🎉 GOOGLE COLAB WORKER ACTIVE!")
    print(f"  Tunnel URL: {tunnel_url}")
    print(f"  Connecting to Master: {MASTER_URL}")
    print("=" * 65 + "\n")

    # Heartbeat loop registering with master Render server
    def heartbeat():
        while True:
            try:
                reg_payload = json.dumps({
                    "url": tunnel_url,
                    "secret": WORKER_SECRET,
                    "specs": {
                        "ram": "12.7GB+",
                        "type": "Google Colab Super Worker",
                        "cpus": os.cpu_count()
                    }
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    f"{MASTER_URL}/api/worker/register",
                    data=reg_payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception as e:
                # Master will accept when endpoint is live
                pass
            time.sleep(30)

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()

def main():
    port = int(os.environ.get("WORKER_PORT", 5000))
    t = threading.Thread(target=start_tunnel_and_register, args=(port,), daemon=True)
    t.start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    main()
