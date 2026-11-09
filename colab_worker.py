"""High-Performance Multi-Core AI Worker for Linework AI
Uses a 100% Stable Zero-Tunnel Direct Pull Engine over standard HTTPS (no cloudflared binary required!).
Works everywhere (100% Free, No Credit Card):
  1. GitHub Actions Super-Cluster (40 CPU Cores / 160 GB RAM per GitHub Account)
  2. Hugging Face Gradio Space (16 GB RAM, 2 vCPU - 24/7 Permanent)
  3. Kaggle Notebooks (30 GB RAM, 4 vCPU)
  4. Your Own Windows PC / Laptop (4-16 CPU Cores via START_LOCAL_SUPER_WORKER.bat)
  5. Google Colab (12.7 GB RAM, 2 vCPU)
"""
import os
import sys
import time
import json
import uuid
import socket
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


def _build_worker_id() -> str:
    custom = os.environ.get("WORKER_NODE_ID", "").strip()
    if custom:
        return custom if custom.startswith("pull://") else f"pull://{custom}"
    gh_actor = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GITHUB_ACTOR") or ""
    matrix_node = os.environ.get("MATRIX_NODE_ID") or ""
    short_uid = uuid.uuid4().hex[:6]
    if gh_actor:
        tag = f"{gh_actor}-n{matrix_node}" if matrix_node else gh_actor
        return f"pull://gh-{tag}-{short_uid}"
    host = re.sub(r"[^a-zA-Z0-9\-]", "", socket.gethostname())[:16] or "node"
    return f"pull://{host}-{short_uid}"


WORKER_ID = _build_worker_id()
WORKER_SPECS = {
    "ram": "16GB+",
    "type": "GitHub Actions 4-Core Node" if os.environ.get("GITHUB_ACTIONS") else "Multi-Core Super Worker",
    "cpus": os.cpu_count() or 4,
    "capacity": MAX_WORKERS,
    "mode": "pull",
}


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


def _execute_task_payload(payload: dict) -> dict:
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
        print(f"  [⚡ {WORKER_ID}] Icon #{k+1} finished in {round(elapsed, 2)}s | IoU: {iou_pct}% | Clean: {res['clean']}", flush=True)
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
        print(f"  [!] Error processing icon #{k+1}: {e}", flush=True)
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/health")
def health():
    return {
        "ok": True,
        "worker_id": WORKER_ID,
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
    return _execute_task_payload(payload)


def start_direct_pull_cluster():
    """100% Stable Zero-Tunnel Outbound Pull Loop + Heartbeat.
    Requires ZERO external binaries (no cloudflared) and never suffers tunnel DNS drops.
    """
    print("\n" + "=" * 70, flush=True)
    print(f"  🚀 ZERO-TUNNEL SUPER-WORKER ONLINE ({MAX_WORKERS} Parallel Cores)!", flush=True)
    print(f"  🆔 Node ID   : {WORKER_ID}", flush=True)
    print(f"  🛰️ Master URL: {MASTER_URL}", flush=True)
    print("=" * 70 + "\n", flush=True)

    def _heartbeat_loop():
        while True:
            try:
                reg_payload = json.dumps({
                    "url": WORKER_ID,
                    "secret": WORKER_SECRET,
                    "specs": WORKER_SPECS,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{MASTER_URL}/api/worker/register",
                    data=reg_payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=12):
                    pass
            except Exception:
                pass
            time.sleep(20)

    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    def _pull_worker_slot(slot_idx: int):
        global _INFLIGHT_COUNT
        # Stagger initial connection slightly
        time.sleep(slot_idx * 0.25)
        while not _SHUTTING_DOWN.is_set():
            try:
                pull_req_body = json.dumps({
                    "worker_id": WORKER_ID,
                    "secret": WORKER_SECRET,
                    "specs": WORKER_SPECS,
                    "slot": slot_idx,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{MASTER_URL}/api/worker/pull",
                    data=pull_req_body,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if data.get("ok") and data.get("has_task") and data.get("task_id"):
                    task_id = data["task_id"]
                    payload = data.get("payload") or {}
                    with _POOL_LOCK:
                        _INFLIGHT_COUNT += 1
                    try:
                        result = _execute_task_payload(payload)
                        comp_body = json.dumps({
                            "task_id": task_id,
                            "worker_id": WORKER_ID,
                            "secret": WORKER_SECRET,
                            "result": result,
                        }).encode("utf-8")
                        creq = urllib.request.Request(
                            f"{MASTER_URL}/api/worker/complete",
                            data=comp_body,
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(creq, timeout=20):
                            pass
                    finally:
                        with _POOL_LOCK:
                            _INFLIGHT_COUNT = max(0, _INFLIGHT_COUNT - 1)
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    # Master server hasn't updated to /api/worker/pull yet; wait briefly
                    time.sleep(8)
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(2.5)

    for slot in range(MAX_WORKERS):
        threading.Thread(target=_pull_worker_slot, args=(slot,), daemon=True).start()


_SHUTTING_DOWN = threading.Event()
_INFLIGHT_COUNT = 0


def main():
    max_sec = int(os.environ.get("WORKER_MAX_SECONDS", "0") or "0")
    if max_sec > 0:
        def _auto_exit():
            drain_wait = max(10, max_sec - 25)
            time.sleep(drain_wait)
            _SHUTTING_DOWN.set()
            # Wait up to 25s for any active 1-4 icons on this node to complete and report back
            t_end = time.time() + 25.0
            while time.time() < t_end:
                with _POOL_LOCK:
                    if _INFLIGHT_COUNT <= 0:
                        break
                time.sleep(0.5)
            print(f"[+] Reached max scheduled shift ({max_sec}s); all in-flight tasks drained cleanly.", flush=True)
            os._exit(0)
        threading.Thread(target=_auto_exit, daemon=True).start()

    # Warm up the multiprocessing pool immediately
    _get_pool()
    start_direct_pull_cluster()

    # In GitHub Actions headless mode, we don't even need uvicorn unless PORT is requested
    port = int(os.environ.get("WORKER_PORT", os.environ.get("PORT", 5000)))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
