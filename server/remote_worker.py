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
# Key: worker_url -> {"last_ping": float, "specs": dict, "active": int, "capacity": int, "failures": int, "total_dispatched": int, "last_dispatched": float}
ACTIVE_NODES = {}
_LOCK = threading.Lock()
_CV = threading.Condition(_LOCK)


def register_worker_node(url: str, secret: str, specs: dict = None) -> bool:
    if secret != WORKER_SECRET:
        return False
    url = url.rstrip("/")
    specs = specs or {}
    capacity = int(specs.get("capacity", specs.get("cpus", 2)) or 2)
    # Cap per-node concurrency between 1 and 4 for optimal CPU performance
    capacity = max(1, min(capacity, 4))
    
    with _CV:
        curr_active = ACTIVE_NODES.get(url, {}).get("active", 0)
        curr_total = ACTIVE_NODES.get(url, {}).get("total_dispatched", 0)
        curr_last = ACTIVE_NODES.get(url, {}).get("last_dispatched", 0.0)
        ACTIVE_NODES[url] = {
            "last_ping": time.time(),
            "specs": specs,
            "capacity": capacity,
            "active": curr_active,
            "total_dispatched": curr_total,
            "last_dispatched": curr_last,
            "failures": 0  # reset failures on register/heartbeat
        }
        _CV.notify_all()
    return True


def get_active_nodes_count() -> int:
    now = time.time()
    with _LOCK:
        alive = [u for u, d in ACTIVE_NODES.items() if now - d["last_ping"] <= 90]
        return len(alive)


def get_total_capacity() -> int:
    now = time.time()
    with _LOCK:
        return sum(d.get("capacity", 2) for u, d in ACTIVE_NODES.items() if now - d["last_ping"] <= 90)


def get_best_worker_url() -> str:
    now = time.time()
    with _LOCK:
        dead_nodes = []
        best_url = None
        min_active = 999999
        for url, data in list(ACTIVE_NODES.items()):
            if now - data["last_ping"] > 90:
                dead_nodes.append(url)
                continue
            if data["active"] < min_active:
                min_active = data["active"]
                best_url = url
        for dead in dead_nodes:
            ACTIVE_NODES.pop(dead, None)
    return best_url


def acquire_worker(timeout: float = 35.0) -> str:
    """Acquire a worker node that has available capacity (active < capacity).
    Uses strict Fair Round-Robin load balancing so all connected Colab nodes share work equally.
    Returns worker_url, or None if no remote workers are available.
    """
    deadline = time.time() + timeout
    with _CV:
        while True:
            now = time.time()
            # Clean up dead nodes (no heartbeat for >90s)
            dead_nodes = [u for u, d in list(ACTIVE_NODES.items()) if now - d["last_ping"] > 90]
            for u in dead_nodes:
                ACTIVE_NODES.pop(u, None)

            if not ACTIVE_NODES:
                return None  # No remote workers available, caller falls back to local

            # Find all workers with available capacity
            candidates = []
            for url, data in ACTIVE_NODES.items():
                cap = data.get("capacity", 2)
                if data["active"] < cap:
                    # Sort key: 1) active load, 2) total tasks dispatched, 3) timestamp of last dispatch
                    candidates.append((
                        data["active"],
                        data.get("total_dispatched", 0),
                        data.get("last_dispatched", 0.0),
                        url
                    ))

            if candidates:
                candidates.sort()
                best_url = candidates[0][3]
                ACTIVE_NODES[best_url]["active"] += 1
                ACTIVE_NODES[best_url]["total_dispatched"] = ACTIVE_NODES[best_url].get("total_dispatched", 0) + 1
                ACTIVE_NODES[best_url]["last_dispatched"] = now
                return best_url

            # All workers are at max capacity; wait for a slot to free up
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            _CV.wait(timeout=min(remaining, 5.0))


def release_worker(url: str, failed: bool = False):
    """Release a worker slot. Increment failures on error, evicting only on 3 consecutive errors."""
    if not url:
        return
    with _CV:
        if url in ACTIVE_NODES:
            ACTIVE_NODES[url]["active"] = max(0, ACTIVE_NODES[url]["active"] - 1)
            if failed:
                ACTIVE_NODES[url]["failures"] = ACTIVE_NODES[url].get("failures", 0) + 1
                if ACTIVE_NODES[url]["failures"] >= 6:
                    print(f"[Remote Worker] Evicting worker {url} after 6 consecutive failures")
                    ACTIVE_NODES.pop(url, None)
            else:
                ACTIVE_NODES[url]["failures"] = 0
        _CV.notify_all()


def dispatch_to_remote_worker(worker_url: str, endpoint: str, payload: dict, timeout: int = 70):
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
    return get_active_nodes_count() > 0
