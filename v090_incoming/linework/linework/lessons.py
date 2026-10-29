"""Lessons: what Linework remembers between runs, so the same mistake is not made twice.

Four things are remembered (all in a small folder, default <project>/data/lessons, override with LINEWORK_DATA; LINEWORK_MEMORY=0 switches it off):
  best/<key>.json   the best result ever produced for a given source icon (key = hash of the pixels + preset).  A later run, even after a code update,
                    can never return something that scores worse: the stored result is the floor.  Same version + same icon = instant re-use.
  stats.json        which trace setting won for which stroke width -> the winner is tried first next time (saves a whole trace).
  log.jsonl         one line per icon: match, remaining issues, and for every Finisher pass how many sites it found / fixed.
  (derived)         passes that have been tried >= 150 times and almost never succeed (< 1 %) are skipped; summary() lists the recurring problems.
It is bookkeeping, not magic: it makes results monotonic per icon, faster over time, and shows which kinds of defect keep coming back.
"""
from __future__ import annotations
import os, json, time, hashlib, tempfile
import numpy as np

try:
    import fcntl
except Exception:  # Windows
    fcntl = None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def enabled():
    return os.environ.get("LINEWORK_MEMORY", "1") != "0"


def _dir(sub=""):
    d = os.path.join(os.environ.get("LINEWORK_DATA") or os.path.join(_ROOT, "data", "lessons"), sub)
    os.makedirs(d, exist_ok=True)
    return d


def crop_key(gray, quality, set_stroke=0.0):
    h = hashlib.sha1(np.ascontiguousarray(gray).tobytes())
    h.update(f"{gray.shape}|{quality}|{round(float(set_stroke or 0), 1)}".encode())
    return h.hexdigest()[:24]


def quality_score(m):
    """Single number for 'how good is this result': match minus a penalty per visible defect."""
    i = m.get("issues", {}) or {}
    pen = 0.0008 * (i.get("gaps", 0) + i.get("notches", 0) + i.get("spurs", 0) + i.get("duplicates", 0)) + 0.0003 * i.get("kinks", 0) + 0.0003 * i.get("regions", 0)
    return float(m.get("iou", 0.0)) - pen


def _atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


# ---- best-so-far
def best_get(key):
    try:
        with open(os.path.join(_dir("best"), key + ".json")) as f:
            return json.load(f)
    except Exception:
        return None


def best_put(key, model_json, metrics, version):
    try:
        slim = {k: v for k, v in metrics.items() if k != "finisher"}
        _atomic_write(os.path.join(_dir("best"), key + ".json"), json.dumps(dict(version=version, score=quality_score(metrics), model=model_json, metrics=slim)))
    except Exception:
        pass


# ---- stats (read-modify-write under a lock)
def _stats_update(fn):
    path = os.path.join(_dir(), "stats.json")
    lock = open(os.path.join(_dir(), "stats.lock"), "a")
    try:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path) as f:
                st = json.load(f)
        except Exception:
            st = {}
        fn(st)
        _atomic_write(path, json.dumps(st))
    finally:
        try:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_UN)
        finally:
            lock.close()


def _stats():
    try:
        with open(os.path.join(_dir(), "stats.json")) as f:
            return json.load(f)
    except Exception:
        return {}


def trace_order(bucket, cands):
    """Put the trace setting that has won most often for this stroke-width bucket first (only when the evidence is clear)."""
    if not enabled():
        return cands
    w = _stats().get("trace", {}).get(str(bucket), {})
    tot = sum(w.values())
    if tot < 5:
        return cands
    best = max(w, key=w.get)
    if w[best] / tot < 0.6:
        return cands
    s, sf = best.split(",")
    top = (int(s), float(sf))
    if top not in cands:
        return cands
    return [top] + [c for c in cands if c != top]


def trace_record(bucket, cand):
    if not enabled():
        return
    key = f"{cand[0]},{cand[1]}"

    def f(st):
        t = st.setdefault("trace", {}).setdefault(str(bucket), {})
        t[key] = t.get(key, 0) + 1

    try:
        _stats_update(f)
    except Exception:
        pass


# ---- defect log
def log_icon(name, metrics, version):
    if not enabled():
        return
    kinds = {}
    for s in (metrics.get("finisher") or {}).get("sites", []):
        k = kinds.setdefault(s["kind"], [0, 0])
        k[0] += 1
        k[1] += int(s["fixed"])
    jn = metrics.get("joins") or {}
    line = json.dumps(dict(ts=int(time.time()), version=version, name=name, iou=round(metrics.get("iou", 0), 4), issues=metrics.get("issues", {}),
                           finisher=kinds, seconds=metrics.get("seconds"),
                           joins=dict(total=jn.get("total", 0), clean=jn.get("clean_first", 0), fixed=sum((jn.get("fixed") or {}).values()),
                                      unresolved=[u.get("reasons") for u in jn.get("unresolved", [])])))
    try:
        with open(os.path.join(_dir(), "log.jsonl"), "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_log(limit=3000):
    try:
        with open(os.path.join(_dir(), "log.jsonl")) as f:
            lines = f.readlines()[-limit:]
        return [json.loads(x) for x in lines if x.strip()]
    except Exception:
        return []


_skip_cache = (0.0, set())


def skip_kinds(min_tries=150, max_rate=0.01):
    global _skip_cache
    if not enabled():
        return set()
    if time.time() - _skip_cache[0] < 60:
        return _skip_cache[1]
    tot = {}
    for r in _read_log():
        for k, (n, f) in (r.get("finisher") or {}).items():
            t = tot.setdefault(k, [0, 0])
            t[0] += n
            t[1] += f
    sk = {k for k, (n, f) in tot.items() if n >= min_tries and f / n < max_rate}
    _skip_cache = (time.time(), sk)
    return sk


def summary():
    """What keeps going wrong: per Finisher pass sites found / fixed, remaining issue counts, icons seen."""
    rows = _read_log()
    passes, issues = {}, {}
    jt = dict(total=0, clean=0, fixed=0, unresolved={})
    for r in rows:
        jr = r.get("joins") or {}
        jt["total"] += jr.get("total", 0)
        jt["clean"] += jr.get("clean", 0)
        jt["fixed"] += jr.get("fixed", 0)
        for rs in jr.get("unresolved", []):
            for x in (rs or []):
                jt["unresolved"][x] = jt["unresolved"].get(x, 0) + 1
        for k, (n, f) in (r.get("finisher") or {}).items():
            p = passes.setdefault(k, dict(found=0, fixed=0))
            p["found"] += n
            p["fixed"] += f
        for k, v in (r.get("issues") or {}).items():
            issues[k] = issues.get(k, 0) + int(v or 0)
    return dict(icons=len(rows), joins=jt, passes=passes, remaining_issues=issues, skipped=sorted(skip_kinds()), trace=_stats().get("trace", {}))


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
