"""Hybrid Remote Compute Worker Manager for Linework AI
Allows high-power external workers (e.g., Google Colab, Kaggle, Home GPU/CPU)
to dynamically register and process vectorization tasks in parallel.
If no remote worker is connected, seamlessly falls back to local processing.
"""
import os
import time
import json
import urllib.request
import urllib.error
import threading

WORKER_SECRET = os.environ.get("LINEWORK_WORKER_SECRET", "linework_super_secret_2026")

# In-memory registry of active remote compute nodes
# Key: worker_url -> {"last_ping": float, "specs": dict, "active": int}
ACTIVE_NODES = {}
_LOCK = threading.Lock()

def register_worker_node(url: str, secret: str, specs: dict = None) -> bool:
    if secret != WORKER_SECRET:
        return False
    url = url.rstrip("/")
    with _LOCK:
        ACTIVE_NODES[url] = {
            "last_ping": time.time(),
            "specs": specs or {},
            "active": 0
        }
    return True

def get_best_worker_url() -> str:
    now = time.time()
    best_url = None
    min_active = 999999
    
    with _LOCK:
        dead_nodes = []
        for url, data in list(ACTIVE_NODES.items()):
            # Node considered dead if no ping in last 90 seconds
            if now - data["last_ping"] > 90:
                dead_nodes.append(url)
                continue
            if data["active"] < min_active:
                min_active = data["active"]
                best_url = url
                
        for dead in dead_nodes:
            ACTIVE_NODES.pop(dead, None)
            
    return best_url

def dispatch_to_remote_worker(worker_url: str, endpoint: str, payload: dict, timeout: int = 30):
    url = f"{worker_url}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Worker-Secret": WORKER_SECRET
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def has_active_remote_worker() -> bool:
    return get_best_worker_url() is not None
