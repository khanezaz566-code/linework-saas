"""High-Performance Multi-Core AI Worker for Linework AI
Works on:
  1. Hugging Face Spaces (16 GB RAM, 2 vCPU - 24/7 Permanent, No Credit Card)
  2. Kaggle Notebooks (30 GB RAM, 4 vCPU)
  3. Google Colab (12.7 GB RAM, 2 vCPU)
  4. Any Local PC / Laptop (4-16 CPU Cores)
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
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from linework.pipeline import Options, process_icon
from fastapi import FastAPI, HTTPException, Header, Body
import uvicorn

app = FastAPI(title="Linework AI Multi-Core Compute Worker")
MAX_WORKERS = max(2, min(4, os.cpu_count() or 2))
_EXEC_POOL = None
_POOL_LOCK = threading.Lock()

WORKER_SECRET = os.environ.get("LINEWORK_WORKER_SECRET", "linework_super_secret_2026")
MASTER_URL = os.environ.get("MASTER_SERVER_URL", "https://linework-saas.onrender.com").rstrip("/")


def _get_pool():
    global _EXEC_POOL
    with _POOL_LOCK:
        if _EXEC_POOL is None:
            _EXEC_POOL = ProcessPoolExecutor(max_workers=MAX_WORKERS)
        return _EXEC_POOL


def _solve_icon_in_subprocess(crop_bytes: bytes, opts_dict: dict, k: int):
    for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[_v] = "1"
    try:
        cv2.setNumThreads(1)
    except Exception:
        pass
    nparr = np.frombuffer(crop_bytes, np.uint8)
    crop = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    opts = Options(**opts_dict)
    if hasattr(opts, "decision_budget") and (opts.decision_budget is None or opts.decision_budget > 4.0):
        opts.decision_budget = 4.0
    r = process_icon(crop, opts, name=f"icon{k + 1}")
    return {
        "model_json": r["model"].to_json(),
        "metrics": r["metrics"],
        "clean": r["clean"]
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "type": "multi_core_worker",
        "cpu_count": os.cpu_count(),
        "workers": MAX_WORKERS,
        "time": time.time()
    }


@app.post("/process_icon")
def process_icon_endpoint(
    payload: dict = Body(...),
    x_worker_secret: str = Header(None)
):
    if x_worker_secret != WORKER_SECRET:
        raise HTTPException(401, "Invalid worker secret")

    crop_b64 = payload.get("crop_b64")
    opts_dict = payload.get("options", {})
    off = payload.get("off", [0, 0])
    k = payload.get("k", 0)

    img_bytes = base64.b64decode(crop_b64)
    start_t = time.time()
    try:
        fut = _get_pool().submit(_solve_icon_in_subprocess, img_bytes, opts_dict, k)
        res = fut.result(timeout=55)
        elapsed = time.time() - start_t
        iou_pct = round(res["metrics"]["iou"] * 100, 2)
        print(f"  [⚡ Worker Node] Icon #{k+1} finished in {round(elapsed, 2)}s | IoU: {iou_pct}% | Clean: {res['clean']}")
        return {
            "ok": True,
            "elapsed": round(elapsed, 3),
            "k": k,
            "off": off,
            "model_json": res["model_json"],
            "metrics": res["metrics"]
        }
    except Exception as e:
        import traceback
        print(f"  [!] Error processing icon #{k+1}: {e}")
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def start_tunnel_and_register(local_port=5000):
    # If running on Hugging Face Spaces or direct public URL, no cloudflared tunnel needed!
    direct_url = os.environ.get("SELF_WORKER_URL", "").strip().rstrip("/")
    if not direct_url and os.environ.get("SPACE_HOST"):
        direct_url = f"https://{os.environ['SPACE_HOST']}".rstrip("/")

    active_url = [direct_url if direct_url else None]

    def _ensure_tunnel():
        if direct_url:
            return
        print("[+] Checking for cloudflared...")
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

        while True:
            print(f"[+] Starting Cloudflare Tunnel on port {local_port}...")
            cmd = [str(cf_path), "tunnel", "--url", f"http://127.0.0.1:{local_port}"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in iter(proc.stdout.readline, ""):
                match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
                if match:
                    active_url[0] = match.group(0)
                    print("\n" + "=" * 65)
                    print(f"  🎉 MULTI-CORE SUPER-WORKER ACTIVE & READY ({MAX_WORKERS} Parallel Cores)!")
                    print(f"  🔗 Worker URL: {active_url[0]}")
                    print(f"  🛰️ Connected to Master: {MASTER_URL}")
                    print("=" * 65 + "\n")
            proc.wait()
            print("[!] Cloudflare tunnel exited; auto-restarting in 3 seconds...")
            time.sleep(3)

    if not direct_url:
        threading.Thread(target=_ensure_tunnel, daemon=True).start()

    def heartbeat():
        while True:
            url = active_url[0]
            if url:
                try:
                    reg_payload = json.dumps({
                        "url": url,
                        "secret": WORKER_SECRET,
                        "specs": {
                            "ram": "16GB+",
                            "type": "Multi-Core Super Worker",
                            "cpus": os.cpu_count() or 2,
                            "capacity": MAX_WORKERS
                        }
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"{MASTER_URL}/api/worker/register",
                        data=reg_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=10):
                        pass
                except Exception:
                    pass
            time.sleep(20)

    threading.Thread(target=heartbeat, daemon=True).start()


def main():
    port = int(os.environ.get("WORKER_PORT", os.environ.get("PORT", 5000)))
    t = threading.Thread(target=start_tunnel_and_register, args=(port,), daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
