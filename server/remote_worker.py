"""Hybrid Remote Compute Worker Manager for Linework AI
Supports BOTH:
  1. Zero-Tunnel Outbound Pull Workers (GitHub Actions, Colab, Kaggle, Local PC) — 100% stable, no cloudflared needed!
  2. Direct Push Workers (Hugging Face Spaces, VPS, or Cloudflare Tunnel nodes)
Persists active node registry to disk so cluster state survives restarts.
"""
import os
import time
import json
import uuid
import urllib.request
import urllib.error
import threading
from pathlib import Path

WORKER_SECRET = os.environ.get("LINEWORK_WORKER_SECRET", "linework_super_secret_2026")
NODE_TTL_SECONDS = 180  # 3-minute heartbeat window for rock-solid cluster stability

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
NODES_FILE = DATA_DIR / "worker_nodes.json"

# Key: worker_url_or_id -> {"last_ping": float, "specs": dict, "active": int, "capacity": int, "failures": int, "total_dispatched": int, "last_dispatched": float, "mode": "pull"|"push"}
ACTIVE_NODES = {}
_LOCK = threading.Lock()
_CV = threading.Condition(_LOCK)

# Zero-Tunnel Pull Queue structures
# _PULL_QUEUE: list of {"task_id": str, "payload": dict, "created": float}
_PULL_QUEUE = []
# _INFLIGHT_TASKS: task_id -> {"event": threading.Event, "result": dict | None, "worker_id": str | None, "created": float}
_INFLIGHT_TASKS = {}


def _load_persisted_nodes():
    try:
        if NODES_FILE.exists():
            raw = json.loads(NODES_FILE.read_text("utf-8"))
            now = time.time()
            with _LOCK:
                for u, d in raw.items():
                    if isinstance(d, dict) and now - d.get("last_ping", 0) <= NODE_TTL_SECONDS:
                        d["active"] = 0
                        ACTIVE_NODES[u] = d
    except Exception:
        pass


def _save_persisted_nodes_locked():
    try:
        now = time.time()
        alive = {u: d for u, d in ACTIVE_NODES.items() if now - d.get("last_ping", 0) <= NODE_TTL_SECONDS}
        NODES_FILE.write_text(json.dumps(alive), "utf-8")
    except Exception:
        pass


_load_persisted_nodes()


def _prune_dead_locked(now: float = None):
    if now is None:
        now = time.time()
    dead = [u for u, d in list(ACTIVE_NODES.items()) if now - d.get("last_ping", 0) > NODE_TTL_SECONDS]
    for u in dead:
        ACTIVE_NODES.pop(u, None)
    if dead:
        _save_persisted_nodes_locked()


def register_worker_node(url: str, secret: str, specs: dict = None) -> bool:
    if secret != WORKER_SECRET:
        return False
    url = url.strip().rstrip("/")
    specs = specs or {}
    capacity = int(specs.get("capacity", specs.get("cpus", 4)) or 4)
    capacity = max(1, min(capacity, 8))
    mode = "pull" if url.startswith("pull://") or specs.get("mode") == "pull" else "push"

    now = time.time()
    with _CV:
        prev = ACTIVE_NODES.get(url, {})
        ACTIVE_NODES[url] = {
            "last_ping": now,
            "specs": specs,
            "capacity": capacity,
            "active": prev.get("active", 0),
            "total_dispatched": prev.get("total_dispatched", 0),
            "last_dispatched": prev.get("last_dispatched", 0.0),
            "failures": 0,
            "mode": mode,
        }
        _prune_dead_locked(now)
        _save_persisted_nodes_locked()
        _CV.notify_all()
    return True


def get_active_nodes_count() -> int:
    now = time.time()
    with _LOCK:
        _prune_dead_locked(now)
        return len(ACTIVE_NODES)


def get_total_capacity() -> int:
    now = time.time()
    with _LOCK:
        _prune_dead_locked(now)
        return sum(d.get("capacity", 4) for d in ACTIVE_NODES.values())


def get_best_worker_url() -> str:
    now = time.time()
    with _LOCK:
        _prune_dead_locked(now)
        best_url = None
        min_active = 999999
        for url, data in ACTIVE_NODES.items():
            if data["active"] < min_active:
                min_active = data["active"]
                best_url = url
        return best_url


def has_active_remote_worker() -> bool:
    return get_active_nodes_count() > 0


def has_active_pull_worker() -> bool:
    now = time.time()
    with _LOCK:
        _prune_dead_locked(now)
        return any(d.get("mode") == "pull" or u.startswith("pull://") for u, d in ACTIVE_NODES.items())


def acquire_worker(timeout: float = 35.0) -> str:
    """Acquire a worker node that has available capacity (active < capacity).
    Fair Round-Robin across all connected nodes.
    """
    deadline = time.time() + timeout
    with _CV:
        while True:
            now = time.time()
            _prune_dead_locked(now)
            if not ACTIVE_NODES:
                return None

            candidates = []
            for url, data in ACTIVE_NODES.items():
                cap = data.get("capacity", 4)
                if data["active"] < cap:
                    # Prefer pull workers first since they never have tunnel DNS errors
                    is_push = 0 if (data.get("mode") == "pull" or url.startswith("pull://")) else 1
                    candidates.append((
                        is_push,
                        data["active"],
                        data.get("total_dispatched", 0),
                        data.get("last_dispatched", 0.0),
                        url
                    ))

            if candidates:
                candidates.sort()
                best_url = candidates[0][4]
                ACTIVE_NODES[best_url]["active"] += 1
                ACTIVE_NODES[best_url]["total_dispatched"] = ACTIVE_NODES[best_url].get("total_dispatched", 0) + 1
                ACTIVE_NODES[best_url]["last_dispatched"] = now
                return best_url

            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            _CV.wait(timeout=min(remaining, 3.0))


def release_worker(url: str, failed: bool = False):
    if not url:
        return
    with _CV:
        if url in ACTIVE_NODES:
            ACTIVE_NODES[url]["active"] = max(0, ACTIVE_NODES[url]["active"] - 1)
            if failed:
                ACTIVE_NODES[url]["failures"] = ACTIVE_NODES[url].get("failures", 0) + 1
                # Pull workers don't get evicted on transient errors; push tunnels get evicted after 8 errors
                max_fail = 20 if url.startswith("pull://") else 8
                if ACTIVE_NODES[url]["failures"] >= max_fail:
                    print(f"[Remote Worker] Evicting worker {url} after {max_fail} consecutive failures")
                    ACTIVE_NODES.pop(url, None)
                    _save_persisted_nodes_locked()
            else:
                ACTIVE_NODES[url]["failures"] = 0
                ACTIVE_NODES[url]["last_ping"] = time.time()
        _CV.notify_all()


def dispatch_via_pull_queue(payload: dict, timeout: float = 55.0) -> dict:
    """Enqueue an icon task for any Zero-Tunnel Pull Worker and wait for its completion."""
    task_id = uuid.uuid4().hex[:16]
    ev = threading.Event()
    now = time.time()
    entry = {
        "event": ev,
        "result": None,
        "worker_id": None,
        "created": now,
    }
    with _CV:
        _INFLIGHT_TASKS[task_id] = entry
        _PULL_QUEUE.append({
            "task_id": task_id,
            "payload": payload,
            "created": now,
        })
        _CV.notify_all()

    try:
        finished = ev.wait(timeout=timeout)
        if not finished:
            return {"ok": False, "error": "Pull queue task timed out"}
        return entry.get("result") or {"ok": False, "error": "Empty pull result"}
    finally:
        with _CV:
            _INFLIGHT_TASKS.pop(task_id, None)
            _PULL_QUEUE[:] = [t for t in _PULL_QUEUE if t["task_id"] != task_id]


def pull_pending_task(worker_id: str, secret: str, specs: dict = None, wait_timeout: float = 20.0) -> dict:
    """Called by remote workers via POST /api/worker/pull.
    Automatically updates worker heartbeat and blocks up to wait_timeout seconds for a task.
    """
    if secret != WORKER_SECRET:
        return {"ok": False, "error": "unauthorized"}

    register_worker_node(worker_id, secret, specs)
    deadline = time.time() + wait_timeout

    with _CV:
        while True:
            now = time.time()
            # Discard stale queued tasks older than 60s
            _PULL_QUEUE[:] = [t for t in _PULL_QUEUE if now - t["created"] < 60.0 and t["task_id"] in _INFLIGHT_TASKS]

            if _PULL_QUEUE:
                task = _PULL_QUEUE.pop(0)
                tid = task["task_id"]
                if tid in _INFLIGHT_TASKS:
                    _INFLIGHT_TASKS[tid]["worker_id"] = worker_id
                if worker_id in ACTIVE_NODES:
                    ACTIVE_NODES[worker_id]["last_ping"] = now
                    ACTIVE_NODES[worker_id]["last_dispatched"] = now
                return {
                    "ok": True,
                    "has_task": True,
                    "task_id": tid,
                    "payload": task["payload"],
                }

            remaining = deadline - time.time()
            if remaining <= 0:
                if worker_id in ACTIVE_NODES:
                    ACTIVE_NODES[worker_id]["last_ping"] = time.time()
                return {"ok": True, "has_task": False}
            _CV.wait(timeout=min(remaining, 4.0))


def complete_pulled_task(task_id: str, worker_id: str, secret: str, result: dict) -> bool:
    """Called by remote workers via POST /api/worker/complete when an icon finishes."""
    if secret != WORKER_SECRET:
        return False
    now = time.time()
    with _CV:
        if worker_id and worker_id in ACTIVE_NODES:
            ACTIVE_NODES[worker_id]["last_ping"] = now
        entry = _INFLIGHT_TASKS.get(task_id)
        if not entry:
            return False
        entry["result"] = result
        entry["event"].set()
        _CV.notify_all()
        return True


def dispatch_to_remote_worker(worker_url: str, endpoint: str, payload: dict, timeout: int = 65):
    """Dispatches either via Zero-Tunnel Pull Queue (for pull:// nodes) or HTTP POST (for push nodes, with pull fallback)."""
    if worker_url.startswith("pull://") or ACTIVE_NODES.get(worker_url, {}).get("mode") == "pull":
        return dispatch_via_pull_queue(payload, timeout=timeout)

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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as push_err:
        # If a push tunnel DNS drops while pull workers are online, seamlessly rescue via pull queue!
        if has_active_pull_worker():
            return dispatch_via_pull_queue(payload, timeout=max(20, timeout - 10))
        raise push_err


def reset_worker_queue():
    with _CV:
        _PULL_QUEUE.clear()
        for entry in _INFLIGHT_TASKS.values():
            entry["result"] = {"ok": False, "error": "Queue reset by admin"}
            entry["event"].set()
        _INFLIGHT_TASKS.clear()
        for d in ACTIVE_NODES.values():
            d["active"] = 0
            d["failures"] = 0
        _CV.notify_all()


def get_cluster_operations_detail() -> dict:
    now = time.time()
    with _LOCK:
        _prune_dead_locked(now)
        nodes_detail = []
        for url, d in sorted(ACTIVE_NODES.items(), key=lambda x: x[1].get("last_ping", 0), reverse=True):
            specs = d.get("specs") or {}
            age_s = max(0, int(round(now - d.get("last_ping", now))))
            nodes_detail.append({
                "id": url,
                "mode": d.get("mode", "pull" if url.startswith("pull://") else "push"),
                "type": specs.get("type", "Super-Cluster Node"),
                "cpus": int(specs.get("cpus", d.get("capacity", 4)) or 4),
                "ram": specs.get("ram", "16GB"),
                "capacity": int(d.get("capacity", 4)),
                "active": int(d.get("active", 0)),
                "total_dispatched": int(d.get("total_dispatched", 0)),
                "failures": int(d.get("failures", 0)),
                "last_ping_ago_s": age_s,
                "healthy": age_s <= NODE_TTL_SECONDS,
            })
        return {
            "active_nodes_count": len(nodes_detail),
            "total_capacity": sum(n["capacity"] for n in nodes_detail),
            "active_tasks": sum(n["active"] for n in nodes_detail),
            "total_completed": sum(n["total_dispatched"] for n in nodes_detail),
            "pull_queue_depth": len(_PULL_QUEUE),
            "inflight_tasks": len(_INFLIGHT_TASKS),
            "nodes": nodes_detail,
        }
