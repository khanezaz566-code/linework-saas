"""Linework SaaS backend (FastAPI). Engines live in ../linework; this file only does jobs + HTTP."""
from __future__ import annotations
import io, json, os, sys, time, uuid, shutil, threading, zipfile, re, urllib.parse, base64, multiprocessing as mp

# One math thread per worker process: N workers x N BLAS threads oversubscribes the CPU and makes every icon slower.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
import gc
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path as FsPath

import cv2, numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body, Request
from fastapi.responses import FileResponse, Response, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = FsPath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from linework.pipeline import Options, process_sheet, load_gray, PRESETS  # noqa: E402
from linework.model import Model  # noqa: E402
from linework.render import render_gray, backend_name  # noqa: E402
from linework.trace import ink_map  # noqa: E402
from linework.audit import audit as audit_paths  # noqa: E402
from server import worker  # noqa: E402
from server import db
from server import remote_worker  # noqa: E402

DATA = FsPath(os.environ.get("LINEWORK_DATA", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 15 * 1024 * 1024
is_cloud = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
MAX_SIDE = 5000
MAX_ICONS = 96
KEEP_SECONDS = 24 * 3600

app = FastAPI(title="Linework", version="0.1.0")

@app.middleware("http")
async def disable_static_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/") or path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_CTX = mp.get_context("fork") if hasattr(os, "fork") else mp.get_context("spawn")
_Q = _CTX.Queue()
_POOL = None

def get_current_user(request: Request):
    """Extract authenticated user from Bearer Authorization header, cookie, or query param."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("lw_token")
    if not token:
        token = request.query_params.get("token")
    if not token:
        return None
    return db.get_user_from_token(token)


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required. Please create an account or sign in.")
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user



CANCELLED_JOBS: set[str] = set()


def is_job_cancelled(job_id: str) -> bool:
    if job_id in CANCELLED_JOBS:
        return True
    j = JOBS.get(job_id)
    if j is not None and (j.get("cancelled") or j.get("status") == "cancelled"):
        CANCELLED_JOBS.add(job_id)
        return True
    return False


def pool():
    global _POOL
    if _POOL is not None:
        if getattr(_POOL, "_broken", False) or getattr(_POOL, "_shutdown_thread", False):
            reset_pool()
    if _POOL is None:
        # 16 worker threads so multi-node remote Colabs can be dispatched concurrently
        # Local execution is strictly capped to 1 by _LOCAL_SEMAPHORE to prevent any OOM on Render
        worker.init(_Q)
        _POOL = ThreadPoolExecutor(max_workers=16)
    return _POOL


def reset_pool():
    global _POOL
    if _POOL is not None:
        try:
            procs = list(getattr(_POOL, "_processes", {}).values())
            for p in procs:
                try:
                    if p.is_alive():
                        p.terminate()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            _POOL.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        _POOL = None


def cancel_all_jobs():
    with _LOCK:
        for jid, j in list(JOBS.items()):
            CANCELLED_JOBS.add(jid)
            if j.get("status") in ("queued", "splitting", "running"):
                j["status"] = "cancelled"
                j["cancelled"] = True
                j.setdefault("events", []).append(dict(engine="doctor", msg="Job cancelled by user", t=0, n=len(j.get("events", []))))
        reset_pool()


def cancel_user_jobs(user_id: int):
    """Cancel only the specific user's previous active jobs without affecting other users."""
    with _LOCK:
        for jid, j in list(JOBS.items()):
            if j.get("user_id") == user_id and j.get("status") in ("queued", "splitting", "running"):
                CANCELLED_JOBS.add(jid)
                j["status"] = "cancelled"
                j["cancelled"] = True
                j.setdefault("events", []).append(dict(engine="doctor", msg="Replaced by new upload", t=0, n=len(j.get("events", []))))


def cancel_job_by_id(job_id: str):
    with _LOCK:
        CANCELLED_JOBS.add(job_id)
        j = JOBS.get(job_id)
        if j and j.get("status") in ("queued", "splitting", "running"):
            j["status"] = "cancelled"
            j["cancelled"] = True
            j.setdefault("events", []).append(dict(engine="doctor", msg="Job cancelled by user", t=0, n=len(j.get("events", []))))
        running = any(other.get("status") in ("queued", "splitting", "running") for other in JOBS.values())
        if not running:
            reset_pool()


def _drain():
    while True:
        try:
            ev = _Q.get()
        except Exception:
            return
        jid = ev.get("job")
        if not jid or is_job_cancelled(jid):
            continue
        job = JOBS.get(jid)
        if job is None:
            continue
        ev.pop("job", None)
        ev["n"] = len(job["events"])
        job["events"].append(ev)
        k = ev.get("k")
        if k is not None and 0 <= k < len(job["icons"]):
            ic = job["icons"][k]
            if "iou" in ev:
                ic["live_iou"] = round(float(ev["iou"]), 4)
            ic["stage"] = ev["engine"]


threading.Thread(target=_drain, daemon=True).start()


# --------------------------------------------------------------------------- helpers
def _attachment_disposition(name: str, suffix: str) -> str:
    stem = FsPath(name).stem
    ascii_stem = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', stem).strip('_') or "linework"
    encoded = urllib.parse.quote(f"{stem}{suffix}")
    return f'attachment; filename="{ascii_stem}{suffix}"; filename*=UTF-8\'\'{encoded}'


def _jobdir(job_id):
    if not job_id.isalnum():
        raise HTTPException(404)
    return DATA / job_id


def _get(job_id):
    job = JOBS.get(job_id)
    if job is None:
        p = _jobdir(job_id) / "job.json"
        if p.exists():
            try:
                job = json.loads(p.read_text("utf-8"))
                job.setdefault("events", [])
                JOBS[job_id] = job
            except Exception:
                pass
    if job is None:
        raise HTTPException(404, "Unknown job")
    return job


def _sweep_old():
    now = time.time()
    for d in list(DATA.iterdir()):
        try:
            if d.is_dir() and d.name != "lessons" and now - d.stat().st_mtime > KEEP_SECONDS:
                shutil.rmtree(d, ignore_errors=True)
                JOBS.pop(d.name, None)
        except Exception:
            pass


def _decode_upload(data: bytes, filename: str) -> np.ndarray:
    if data.startswith(b"PK\x03\x04") or filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                candidates = [n for n in names if n in ("sheet.svg", "original.png", "result.png")]
                if not candidates:
                    candidates = [n for n in names if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")) and not n.startswith("__MACOSX")]
                if candidates:
                    return _decode_upload(z.read(candidates[0]), candidates[0])
        except Exception:
            pass

    is_raster = (
        data.startswith(b"\x89PNG\r\n\x1a\n") or
        data.startswith(b"\xff\xd8\xff") or
        (data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP") or
        data.startswith(b"GIF8") or
        data.startswith(b"BM")
    )

    if not is_raster:
        clean_head = data.lstrip(b"\xef\xbb\xbf \t\r\n")[:50]
        if filename.lower().endswith(".svg") or clean_head.startswith((b"<?xml", b"<svg", b"<!DOCTYPE svg")):
            try:
                import resvg_py
                svg_str = data.decode("utf-8", "ignore").lstrip("\ufeff")
                data = bytes(resvg_py.svg_to_bytes(svg_string=svg_str, width=2400, background="white"))
            except Exception as e:
                try:
                    return load_gray(data)
                except Exception:
                    raise HTTPException(400, f"Could not render SVG: {e}")

    try:
        g = load_gray(data)
    except Exception as e:
        raise HTTPException(400, f"Unsupported or corrupted image: {e}")

    h, w = g.shape
    if max(h, w) > MAX_SIDE:
        s = MAX_SIDE / max(h, w)
        g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if min(g.shape) < 24:
        raise HTTPException(400, "Image is too small")
    return g


def _tight_svg(model: Model, stroke="#000000", scale=1.0, bg=None):
    xs, ys = [], []
    for p in model.paths:
        f = p.flat(2.0)
        xs += [f[:, 0].min() - p.w * scale / 2, f[:, 0].max() + p.w * scale / 2]
        ys += [f[:, 1].min() - p.w * scale / 2, f[:, 1].max() + p.w * scale / 2]
    if not xs:
        return model.svg(background=bg)
    m = 2
    vb = (min(xs) - m, min(ys) - m, max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m)
    return model.svg(background=bg, stroke=stroke, stroke_scale=scale, viewbox=vb, pretty=True)


def _compose(job_id, upto=None):
    job = _get(job_id)
    W, H = job["width"], job["height"]
    allm = Model([], W, H)
    for ic in job["icons"]:
        fn = _jobdir(job_id) / f"icon_{ic['k']}.json"
        if ic["status"] == "done" and fn.exists():
            allm.paths += Model.from_json(fn.read_text()).paths
    return allm


def _finish_composite(job_id):
    job = _get(job_id)
    d = _jobdir(job_id)
    allm = _compose(job_id)
    (d / "result.svg").write_text(allm.svg(pretty=True))
    img = render_gray(allm.svg(), allm.width, allm.height)
    cv2.imwrite(str(d / "result.png"), img)
    gray = cv2.imread(str(d / "original.png"), 0)
    ref = ink_map(gray) > 0.5
    b = img < 128
    job["iou"] = float((b & ref).sum() / max((b | ref).sum(), 1))
    dm = np.full(ref.shape + (3,), 255, np.uint8)
    dm[ref & b] = (200, 200, 200)
    dm[ref & ~b] = (60, 60, 235)
    dm[~ref & b] = (235, 120, 60)
    cv2.imwrite(str(d / "diff.png"), dm)
    a = audit_paths(allm.paths, min_run=1.2)
    iss = [ic["metrics"]["issues"] for ic in job["icons"] if ic.get("metrics")]
    fin_fixed = sum(ic.get("metrics", {}).get("finisher", {}).get("fixed", 0) for ic in job["icons"])
    fin_found = sum(ic.get("metrics", {}).get("finisher", {}).get("found", 0) for ic in job["icons"])
    sp = job.get("set_pass", {})
    jn = [ic["metrics"].get("joins") or {} for ic in job["icons"] if ic.get("metrics")]
    sx = [ic["metrics"].get("structure") or {} for ic in job["icons"] if ic.get("metrics")]
    job["audit"] = dict(coincident=len(a), gaps=sum(i.get("gaps", 0) for i in iss),
                        notches=sum(i.get("notches", 0) + i.get("spurs", 0) for i in iss),
                        restored=sum(i.get("restored", 0) for i in iss),
                        stray=sum(i.get("stray", 0) for i in iss),
                        finisher_fixed=fin_fixed,
                        finisher_found=fin_found,
                        set_widths=sp.get("widths_changed", 0),
                        weak_rerun=len(sp.get("weak", [])),
                        joints=sum(j.get("total", 0) for j in jn),
                        joints_clean=sum(j.get("clean_first", 0) for j in jn),
                        joints_repaired=sum(sum((j.get("fixed") or {}).values()) for j in jn),
                        joints_review=sum(len(j.get("unresolved", [])) for j in jn),
                        structure_found=sum(s.get("found", 0) for s in sx),
                        structure_fixed=sum(s.get("fixed", 0) for s in sx),
                        structure_review=sum(len(s.get("unresolved", [])) for s in sx))


def _store_icon(job, d, k, mj, off, met):
    m = Model.from_json(mj)
    (d / f"icon_local_{k}.json").write_text(mj)
    (d / f"icon_{k}.svg").write_text(_tight_svg(m))
    m.translate(*off)
    (d / f"icon_{k}.json").write_text(m.to_json())
    drep = met.get("decision")
    if drep:
        try:
            (d / f"icon_decision_{k}.json").write_text(json.dumps(drep))
        except Exception:
            pass
    clean = bool(met.get("clean", True))
    needs_review = bool(met.get("needs_review", not clean))
    iou = float(met.get("iou", 0.0))
    hard = int(met.get("hard", drep.get("after", {}).get("hard", 0) if drep else 0))
    structural_match = float(met.get("structural_match", 1.0))
    job["icons"][k].update(
        status="done",
        stage="done",
        metrics=met,
        iou=iou,
        match=iou,
        clean=clean,
        needs_review=needs_review,
        structural_match=structural_match,
        hard=hard,
        decision=drep
    )
    job["version"] += 1


def _set_pass(job_id, d, jobs, order):
    from linework import setlevel as SL
    from linework.pipeline import Options
    job = JOBS.get(job_id)
    if job is None or is_job_cancelled(job_id):
        return
    ok = [k for k, _, _ in jobs if job["icons"][k].get("metrics")]
    mets = {k: job["icons"][k]["metrics"] for k in ok}
    offs = {k: off for k, _, off in jobs}
    crops = {k: c for k, c, _ in jobs}
    weak = SL.weak_icons([mets[k] for k in ok])
    weak = [ok[i] for i in weak]
    if weak:
        job["events"].append(dict(engine="doctor", msg=f"Set check: {len(weak)} icon(s) need escalation / second pass", t=0, n=len(job["events"])))
        base_opts = Options(**job["options"])
        sheet_budget = max(90.0, len(jobs) * 20.0)
        deadline = time.time() + sheet_budget
        for k in weak:
            if time.time() > deadline or is_job_cancelled(job_id):
                break
            cur_m = Model.from_json((d / f"icon_local_{k}.json").read_text())
            cur_met = mets[k]
            m_esc, met_esc = SL.escalate_weak_icon(
                crops[k], offs[k], base_opts, cur_m, cur_met,
                emit=lambda **kw: job["events"].append(dict(kw, job=job_id, k=k, t=0, n=len(job["events"]))),
                name=f"icon{k+1}",
                sheet_deadline=deadline
            )
            if SL.result_key(m_esc, met_esc) < SL.result_key(cur_m, cur_met):
                _store_icon(job, d, k, m_esc.to_json(), offs[k], met_esc)
                mets[k] = met_esc
    models = [Model.from_json((d / f"icon_local_{k}.json").read_text()) for k in ok]
    new, rep = SL.harmonize_widths(models, [crops[k] for k in ok])
    for k, m0, m1 in zip(ok, models, new):
        if m1 is not m0:
            _store_icon(job, d, k, m1.to_json(), offs[k], mets[k])
    job["set_pass"] = dict(weak=weak, widths_changed=rep["changed"], classes=rep["classes"])
    _finish_composite(job_id)


_LOCAL_SEMAPHORE = threading.Semaphore(1)

def _dispatch_single_icon(args):
    job_id, k, crop, off, opts = args
    if remote_worker.has_active_remote_worker():
        node_url = remote_worker.acquire_worker(timeout=120.0)
        if node_url:
            try:
                _, enc = cv2.imencode(".png", crop)
                crop_b64 = base64.b64encode(enc.tobytes()).decode("utf-8")
                payload = {
                    "job_id": job_id,
                    "k": k,
                    "off": [int(off[0]), int(off[1])],
                    "crop_b64": crop_b64,
                    "options": opts
                }
                res = remote_worker.dispatch_to_remote_worker(node_url, "/process_icon", payload, timeout=180)
                if res and res.get("ok"):
                    remote_worker.release_worker(node_url, failed=False)
                    return k, off, res["model_json"], res["metrics"]
                else:
                    remote_worker.release_worker(node_url, failed=True)
            except Exception as e:
                print(f"[Remote Dispatch Error on {node_url}] {e}")
                remote_worker.release_worker(node_url, failed=True)
                # Seamless fallback to local worker below

    # Strictly throttled to 1 concurrent task on Render to prevent OOM
    with _LOCAL_SEMAPHORE:
        return worker.run_icon(args)


def _run_job(job_id):
    job = JOBS.get(job_id)
    if job is None or is_job_cancelled(job_id):
        return
    d = _jobdir(job_id)
    try:
        job["status"] = "splitting"
        gray = cv2.imread(str(d / "original.png"), 0)
        opts = Options(**job["options"])
        W, H, jobs = process_sheet(gray, opts)
        if is_job_cancelled(job_id):
            job["status"] = "cancelled"
            return
        if len(jobs) > MAX_ICONS:
            raise RuntimeError(f"Too many icons ({len(jobs)}); limit is {MAX_ICONS}")
        job["width"], job["height"] = W, H
        job["icons"] = [
            dict(k=k, box=[int(off[0]), int(off[1]), int(off[0] + c.shape[1]), int(off[1] + c.shape[0])], status="queued", stage="queued")
            for k, c, off in jobs
        ]
        job["status"] = "running"
        job["events"].append(dict(engine="split", msg=f"Found {len(jobs)} icon(s)", t=0, n=len(job["events"])))
        order = sorted(jobs, key=lambda j: -j[1].size)
        crop_map = {k: c for k, c, off in jobs}
        off_map = {k: off for k, c, off in jobs}

        futs = {}
        p = pool()
        for k, crop, off in order:
            if is_job_cancelled(job_id):
                break
            job["icons"][k]["status"] = "running"
            try:
                futs[p.submit(_dispatch_single_icon, (job_id, k, crop, off, job["options"]))] = k
            except Exception:
                reset_pool()
                p = pool()
                try:
                    futs[p.submit(_dispatch_single_icon, (job_id, k, crop, off, job["options"]))] = k
                except Exception:
                    k_r, off_r, mj_r, met_r = _dispatch_single_icon((job_id, k, crop, off, job["options"]))
                    _store_icon(job, d, k_r, mj_r, off_r, met_r)
                    job["done"] += 1
        for fut in as_completed(futs):
            if is_job_cancelled(job_id):
                break
            k = futs[fut]
            ic = job["icons"][k]
            try:
                _, off, mj, met = fut.result()
            except Exception as e:
                if is_job_cancelled(job_id) or str(e) == "Cancelled":
                    break
                reset_pool()
                try:
                    k_r, off_r, mj_r, met_r = _dispatch_single_icon((job_id, k, crop_map[k], off_map[k], job["options"]))
                    _store_icon(job, d, k_r, mj_r, off_r, met_r)
                    job["done"] += 1
                    _finish_composite(job_id)
                    continue
                except Exception as e2:
                    ic.update(status="error", error=str(e2))
                    continue
            _store_icon(job, d, k, mj, off, met)
            job["done"] += 1
            _finish_composite(job_id)
        if is_job_cancelled(job_id):
            job["status"] = "cancelled"
            return

        try:  # set-level pass & composite
            _set_pass(job_id, d, jobs, order)
        except Exception as e:
            job["events"].append(dict(engine="doctor", msg=f"Set-level pass skipped: {e}", t=0, n=len(job["events"])))
            _finish_composite(job_id)
        if is_job_cancelled(job_id):
            job["status"] = "cancelled"
            return
        job["status"] = "done"
        gc.collect()
        job["seconds"] = round(time.time() - job["created"], 1)
        (d / "job.json").write_text(json.dumps({k: v for k, v in job.items() if k != "events"}))
    except Exception as e:
        if not is_job_cancelled(job_id):
            job["status"] = "error"
            job["error"] = str(e)


# --------------------------------------------------------------------------- API
@app.get("/api/lessons")
def lessons():
    from linework import lessons as LS
    return LS.summary()


@app.post("/api/lessons/clear")
@app.delete("/api/lessons")
@app.post("/api/cache/clear")
def clear_cache():
    from linework import lessons as LS
    cleared = LS.clear()
    return dict(ok=True, message="Cache cleared and lessons reset", cleared=cleared)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str):
    cancel_job_by_id(job_id)
    return dict(ok=True, job=job_id, status="cancelled")


@app.post("/api/jobs/cancel-all")
def cancel_all_endpoint():
    cancel_all_jobs()
    return dict(ok=True, status="all_cancelled")


@app.post("/api/worker/register")
async def register_worker(request: Request):
    body = await request.json()
    url = body.get("url")
    secret = body.get("secret")
    specs = body.get("specs", {})
    if not url or not secret:
        raise HTTPException(400, "Missing url or secret")
    ok = remote_worker.register_worker_node(url, secret, specs)
    if not ok:
        raise HTTPException(401, "Invalid secret")
    return {"ok": True, "registered": url}


@app.get("/api/worker/bundle.zip")
def worker_bundle(secret: str = Query(...)):
    if secret != remote_worker.WORKER_SECRET:
        raise HTTPException(401, "Invalid secret")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        lw_dir = ROOT / "linework"
        for f in lw_dir.glob("**/*"):
            if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                arcname = str(f.relative_to(ROOT)).replace("\\", "/")
                z.write(f, arcname)
        cw_file = ROOT / "colab_worker.py"
        if cw_file.exists():
            z.write(cw_file, "colab_worker.py")
        req_file = ROOT / "requirements.txt"
        if req_file.exists():
            z.write(req_file, "requirements.txt")
    buf.seek(0)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="linework-worker.zip"'}
    )


@app.get("/api/worker/status")
def worker_status():
    best = remote_worker.get_best_worker_url()
    return {
        "hybrid_active": best is not None,
        "active_worker": best,
        "active_nodes_count": remote_worker.get_active_nodes_count(),
        "total_capacity": remote_worker.get_total_capacity(),
        "nodes": list(remote_worker.ACTIVE_NODES.keys())
    }


@app.get("/api/health")
def health():
    return dict(
        ok=True,
        renderer=backend_name(),
        workers=os.cpu_count(),
        presets=list(PRESETS),
        hybrid_worker=remote_worker.has_active_remote_worker(),
        hybrid_nodes_count=remote_worker.get_active_nodes_count(),
        cluster_capacity=remote_worker.get_total_capacity()
    )


@app.post("/api/jobs")
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    quality: str = Form("standard"),
    clean: float = Form(0.5),          # 0 = pixel match first, 1 = cleanest paths first
    target: float = Form(99.5),
    fresh: bool = Form(True),
):
    user = require_user(request)
    can_proc, reason = db.can_user_process_sheet(user["id"])
    if not can_proc:
        raise HTTPException(403, reason)
    db.increment_sheet_usage(user["id"])
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (15 MB max)")
    gray = _decode_upload(data, file.filename or "")
    return _start(gray, file.filename or "upload", quality, clean, target, fresh=fresh, user_id=user["id"])


def _start(gray, name, quality, clean, target, fresh: bool = True, user_id: int = None):
    _sweep_old()
    # Concurrency safe: do not cancel active jobs on new upload; allow simultaneous multi-user and multi-tab workflows
    if quality not in PRESETS:
        quality = "standard"
    job_id = uuid.uuid4().hex[:12]
    d = _jobdir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "original.png"), gray)
    clean = float(np.clip(clean, 0, 1))
    opts = dict(quality=quality, target_iou=float(np.clip(target, 90, 99.9)) / 100, dedupe_tol=0.0005 + 0.006 * clean, fresh=bool(fresh))
    job = dict(
        id=job_id, user_id=user_id, name=name, status="queued", options=opts, created=time.time(), icons=[], events=[],
        width=int(gray.shape[1]), height=int(gray.shape[0]), version=0, done=0, iou=None,
    )
    JOBS[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return dict(id=job_id)


@app.post("/api/samples/{name}")
def sample(name: str, request: Request, quality: str = "standard", fresh: bool = True):
    user = require_user(request)
    can_proc, reason = db.can_user_process_sheet(user["id"])
    if not can_proc:
        raise HTTPException(403, reason)
    db.increment_sheet_usage(user["id"])
    fn = ROOT / "samples" / f"{name}.png"
    if not fn.exists() or not name.replace("-", "").isalnum():
        raise HTTPException(404)
    gray = cv2.imread(str(fn), 0)
    return _start(gray, name, quality, 0.5, 99.5, fresh=fresh, user_id=user["id"])


@app.get("/api/jobs/{job_id}")
def job_state(job_id: str, since: int = 0):
    j = _get(job_id)
    out = {k: v for k, v in j.items() if k != "events"}
    out["events"] = j["events"][since:]
    out["next"] = len(j["events"])
    out["elapsed"] = round(time.time() - j["created"], 1) if j["status"] != "done" else j.get("seconds")
    return JSONResponse(out)


@app.get("/api/jobs/{job_id}/original.png")
def original(job_id: str):
    return FileResponse(_jobdir(job_id) / "original.png", media_type="image/png")


@app.get("/api/jobs/{job_id}/diff.png")
def diff(job_id: str, v: int = 0):
    fn = _jobdir(job_id) / "diff.png"
    if not fn.exists():
        raise HTTPException(404)
    return FileResponse(fn, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/result.png")
def result_png(job_id: str):
    fn = _jobdir(job_id) / "result.png"
    if not fn.exists():
        raise HTTPException(404)
    return FileResponse(fn, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/result.svg")
def result_svg(job_id: str, stroke: str = "#000000", scale: float = 1.0, bg: str = "#ffffff", download: int = 0, v: int = 0):
    job = _get(job_id)
    m = _compose(job_id)
    if not m.paths:
        raise HTTPException(404, "No finished icons yet")
    bgv = None if bg in ("none", "transparent") else bg
    svg = m.svg(background=bgv, stroke=stroke, stroke_scale=float(np.clip(scale, 0.2, 4)), pretty=True)
    headers = {"Cache-Control": "no-store"}
    if download:
        headers["Content-Disposition"] = _attachment_disposition(job["name"], "-linework.svg")
    return Response(svg, media_type="image/svg+xml", headers=headers)


@app.get("/api/jobs/{job_id}/icons/{k}.svg")
def icon_svg(job_id: str, k: int, stroke: str = "#000000", scale: float = 1.0, download: int = 0):
    fn = _jobdir(job_id) / f"icon_local_{k}.json"
    if not fn.exists():
        raise HTTPException(404)
    m = Model.from_json(fn.read_text())
    svg = _tight_svg(m, stroke=stroke, scale=float(np.clip(scale, 0.2, 4)))
    headers = {"Content-Disposition": f'attachment; filename="icon-{int(k) + 1:02d}.svg"'} if download else {}
    return Response(svg, media_type="image/svg+xml", headers=headers)


@app.get("/api/jobs/{job_id}/icons/{k}/decision")
def icon_decision(job_id: str, k: int):
    j = _get(job_id)
    if k < 0 or k >= len(j["icons"]):
        raise HTTPException(404, "Icon index out of range")
    dec = j["icons"][k].get("decision")
    if not dec:
        fn = _jobdir(job_id) / f"icon_decision_{k}.json"
        if fn.exists():
            try:
                dec = json.loads(fn.read_text())
            except Exception:
                pass
    if not dec:
        raise HTTPException(404, "Decision report not available for this icon")
    return JSONResponse(dec)


@app.get("/api/jobs/{job_id}/icons/{k}/diff.png")
def icon_diff_png(job_id: str, k: int):
    j = _get(job_id)
    if k < 0 or k >= len(j["icons"]):
        raise HTTPException(404, "Icon not found")
    d = _jobdir(job_id)
    local_fn = d / f"icon_local_{k}.json"
    if not local_fn.exists():
        raise HTTPException(404, "Icon vector not found")
    m = Model.from_json(local_fn.read_text())
    crop = _icon_crop(job_id, k)
    if crop is None:
        raise HTTPException(404, "Icon crop not found")
    D = ink_map(crop)
    S = D > 0.5
    img = render_gray(m.svg(), m.width, m.height)
    R = img < 128
    dm = np.full(S.shape + (3,), 255, np.uint8)
    dm[S & R] = (200, 200, 200)       # matching ink: grey
    dm[S & ~R] = (60, 60, 235)        # source only (missing): red in BGR
    dm[~S & R] = (40, 140, 255)       # render only (extra): orange in BGR
    ok, buf = cv2.imencode(".png", dm)
    return Response(buf.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"})




def _icon_crop(job_id, k):
    """The exact crop (and its offset in the sheet) the engine works on for icon k; cached next to the job."""
    job = _get(job_id)
    d = _jobdir(job_id)
    icons = job.get("icons", [])
    if k < 0 or k >= len(icons):
        raise HTTPException(404, f"Icon {k} not found in job")
    cache, offf = d / f"icon_crop_{k}.png", d / f"icon_crop_{k}.json"
    if cache.exists() and offf.exists():
        c = cv2.imread(str(cache), 0)
        if c is not None:
            return c, tuple(json.loads(offf.read_text()))
    orig_path = d / "original.png"
    if not orig_path.exists():
        raise HTTPException(404, "Original sheet image not found")
    gray = cv2.imread(str(orig_path), 0)
    opts = Options(**job.get("options", {}))
    _, _, jobs = process_sheet(gray, opts)
    if k < len(jobs):
        _, crop, off = jobs[k]
    else:
        b = icons[k]["box"]
        crop = gray[b[1]:b[3], b[0]:b[2]]
        off = (b[0], b[1])
    cv2.imwrite(str(cache), crop)
    offf.write_text(json.dumps([int(off[0]), int(off[1])]))
    return crop, (int(off[0]), int(off[1]))


@app.get("/api/jobs/{job_id}/icons/{k}/crop.png")
def icon_crop_png(job_id: str, k: int):
    c, _ = _icon_crop(job_id, k)
    ok, buf = cv2.imencode(".png", c)
    if not ok:
        raise HTTPException(500, "encode failed")
    return Response(buf.tobytes(), media_type="image/png")


@app.post("/api/jobs/{job_id}/icons/{k}/regenerate")
def regenerate_icon_endpoint(job_id: str, k: int, payload: dict = Body(None)):
    """Regenerate one icon. With `regions` ([[x0,y0,x1,y1], ...] in crop pixels) only those marked places are
    repaired (Mark & Fix); without, the whole icon gets the deep join/missing-element pass."""
    from linework.pipeline import regenerate_icon_deep
    from linework.focusfix import focus_fix
    from linework.doctor import ink_of as _ink_of
    job = _get(job_id)
    d = _jobdir(job_id)
    opts = Options(**job.get("options", {}))
    crop, off = _icon_crop(job_id, k)
    local_fn = d / f"icon_local_{k}.json"
    old_model = Model.from_json(local_fn.read_text()) if local_fn.exists() else None
    payload = payload or {}
    regions = []
    for r in (payload.get("regions") or [])[:12]:
        try:
            x0, y0, x1, y1 = [float(v) for v in r]
        except Exception:
            continue
        if x1 - x0 >= 2 and y1 - y0 >= 2:
            regions.append((x0, y0, x1, y1))
    prev_status = job["icons"][k].get("status", "done")
    job["icons"][k]["status"] = "running"
    job["icons"][k]["stage"] = "doctor"
    try:
        if regions and old_model is not None:
            try:
                res = focus_fix(crop, old_model, regions, opts, deep=bool(payload.get("deep")),
                                old_metrics=job["icons"][k].get("metrics"))
            except ValueError as e:
                raise HTTPException(400, str(e))
            report = res["report"]
        else:
            res = regenerate_icon_deep(crop, old_model=old_model, opts=opts)
            diff = float(np.abs(_ink_of(old_model) - _ink_of(res["model"])).sum()) if old_model is not None else 1e9
            changed = diff > 12.0
            report = dict(
                changed=changed, regions=0, actions=[], deep=True,
                note=("Whole icon re-solved." if changed else
                      "The full regenerate found nothing better than the current vector (it never replaces it with something worse). "
                      "Use Mark & Fix and draw a box around the exact place that looks wrong."),
            )
    except Exception:
        job["icons"][k]["status"] = prev_status
        raise
    _store_icon(job, d, k, res["model"].to_json(), off, res["metrics"])
    _finish_composite(job_id)
    (d / "job.json").write_text(json.dumps({key: val for key, val in job.items() if key != "events"}))
    return dict(
        ok=True,
        k=k,
        icon=job["icons"][k],
        iou=job.get("iou"),
        version=job.get("version"),
        audit=job.get("audit"),
        report=report,
    )


@app.get("/api/template/presets")
def template_presets():
    from linework.template import PRESETS
    return PRESETS


@app.get("/api/jobs/{job_id}/template.svg")
def job_template_svg(
    job_id: str,
    preset: str = "obsidian",
    title: str = "Minimal Vector Line Icons",
    subtitle: str = "Clean Centerline Vector Icon Collection",
    grid_size: str = "64 × 64 px",
    author: str = "Linework AI Precision Engine",
    layout: str = "landscape",
    stroke: str = "",
    scale: float = 1.0,
    bg: str = "",
    panel_bg: str = "",
    accent: str = "",
    download: int = 0,
):
    from linework.template import build_template_svg
    job = _get(job_id)
    m = _compose(job_id)
    if not m.paths:
        raise HTTPException(404, "No finished icons yet")
    cfg = dict(
        preset=preset, title=title, subtitle=subtitle, grid_size=grid_size,
        author=author, layout=layout, stroke_scale=float(scale)
    )
    if stroke: cfg["icon_stroke"] = stroke
    if bg: cfg["bg"] = bg
    if panel_bg: cfg["panel_bg"] = panel_bg
    if accent: cfg["accent"] = accent
    
    svg = build_template_svg(m, job.get("icons", []), cfg)
    headers = {"Cache-Control": "no-store"}
    if download:
        headers["Content-Disposition"] = _attachment_disposition(job["name"], "-presentation.svg")
    return Response(svg, media_type="image/svg+xml", headers=headers)


@app.get("/api/jobs/{job_id}/template.eps")
def job_template_eps(
    job_id: str,
    preset: str = "obsidian",
    title: str = "Minimal Vector Line Icons",
    subtitle: str = "Clean Centerline Vector Icon Collection",
    grid_size: str = "64 × 64 px",
    author: str = "Linework AI Precision Engine",
    layout: str = "landscape",
    stroke: str = "",
    scale: float = 1.0,
    bg: str = "",
    panel_bg: str = "",
    accent: str = "",
    download: int = 0,
):
    from linework.template import build_template_eps
    job = _get(job_id)
    m = _compose(job_id)
    if not m.paths:
        raise HTTPException(404, "No finished icons yet")
    cfg = dict(
        preset=preset, title=title, subtitle=subtitle, grid_size=grid_size,
        author=author, layout=layout, stroke_scale=float(scale)
    )
    if stroke: cfg["icon_stroke"] = stroke
    if bg: cfg["bg"] = bg
    if panel_bg: cfg["panel_bg"] = panel_bg
    if accent: cfg["accent"] = accent

    eps = build_template_eps(m, job.get("icons", []), cfg)
    headers = {"Cache-Control": "no-store"}
    if download:
        headers["Content-Disposition"] = _attachment_disposition(job["name"], "-presentation.eps")
    return Response(eps, media_type="application/postscript", headers=headers)


@app.get("/api/jobs/{job_id}/result.eps")
def result_eps(job_id: str, stroke: str = "#000000", scale: float = 1.0, bg: str = "none", download: int = 0):
    from linework.template import build_model_eps
    job = _get(job_id)
    m = _compose(job_id)
    if not m.paths:
        raise HTTPException(404, "No finished icons yet")
    eps = build_model_eps(m, stroke_color=stroke, stroke_scale=float(scale), bg=(None if bg in ("none", "transparent") else bg))
    headers = {"Cache-Control": "no-store"}
    if download:
        headers["Content-Disposition"] = _attachment_disposition(job["name"], "-linework.eps")
    return Response(eps, media_type="application/postscript", headers=headers)


@app.get("/api/jobs/{job_id}/icons/{k}.eps")
def icon_eps(job_id: str, k: int, stroke: str = "#000000", scale: float = 1.0, download: int = 0):
    from linework.template import build_model_eps
    fn = _jobdir(job_id) / f"icon_local_{k}.json"
    if not fn.exists():
        raise HTTPException(404)
    m = Model.from_json(fn.read_text())
    eps = build_model_eps(m, stroke_color=stroke, stroke_scale=float(scale))
    headers = {"Content-Disposition": f'attachment; filename="icon-{int(k) + 1:02d}.eps"'} if download else {}
    return Response(eps, media_type="application/postscript", headers=headers)


@app.get("/api/jobs/{job_id}/download.zip")
def download_zip(job_id: str, stroke: str = "#000000", scale: float = 1.0):
    from linework.template import build_model_eps, build_template_svg, build_template_eps
    job = _get(job_id)
    buf = io.BytesIO()
    comp = _compose(job_id)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("sheet.svg", comp.svg(background="#ffffff", stroke=stroke, stroke_scale=scale, pretty=True))
        z.writestr("sheet.eps", build_model_eps(comp, stroke_color=stroke, stroke_scale=scale))
        try:
            z.writestr("presentation-template.svg", build_template_svg(comp, job.get("icons", [])))
            z.writestr("presentation-template.eps", build_template_eps(comp, job.get("icons", [])))
        except Exception:
            pass
        for ic in job["icons"]:
            fn = _jobdir(job_id) / f"icon_local_{ic['k']}.json"
            if ic["status"] == "done" and fn.exists():
                ic_m = Model.from_json(fn.read_text())
                z.writestr(f"icons/icon-{ic['k'] + 1:02d}.svg", _tight_svg(ic_m, stroke=stroke, scale=scale))
                z.writestr(f"icons/icon-{ic['k'] + 1:02d}.eps", build_model_eps(ic_m, stroke_color=stroke, stroke_scale=scale))
        report = [dict(icon=ic["k"] + 1, **ic.get("metrics", {})) for ic in job["icons"]]
        z.writestr("report.json", json.dumps(dict(match=job.get("iou"), icons=report), indent=2))
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": _attachment_disposition(job["name"], "-linework.zip")})


@app.get("/bg-studio")
@app.get("/bgstudio")
def bg_studio_redirect():
    return RedirectResponse(url="/#bgstudio")



# ===========================================================================
# Auth & User Management Endpoints
# ===========================================================================

@app.post("/api/auth/register")
async def api_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    name = body.get("name")
    phone = body.get("phone")
    whatsapp = body.get("whatsapp") or phone
    password = body.get("password")
    
    user, err = db.register_user(name, phone, whatsapp, password)
    if err:
        raise HTTPException(400, err)
    
    token = db.create_session(user["id"])
    response = JSONResponse({
        "ok": True,
        "token": token,
        "user": db.get_user_quota_info(user),
        "message": "Account created successfully! 3 Free Icon Sets and 10 Backgrounds activated."
    })
    response.set_cookie("lw_token", token, max_age=30*86400, httponly=False, samesite="lax")
    return response


@app.post("/api/auth/login")
async def api_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    identifier = body.get("phone") or body.get("identifier") or body.get("username")
    password = body.get("password")
    
    user, err = db.authenticate_user(identifier, password)
    if err:
        raise HTTPException(401, err)
    
    token = db.create_session(user["id"])
    response = JSONResponse({
        "ok": True,
        "token": token,
        "user": db.get_user_quota_info(user)
    })
    response.set_cookie("lw_token", token, max_age=30*86400, httponly=False, samesite="lax")
    return response



@app.get("/api/auth/ping")
@app.post("/api/auth/ping")
def api_auth_ping(request: Request):
    user = get_current_user(request)
    if not user:
        return {"ok": False, "logged_in": False}
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip() or request.cookies.get("lw_token")
    db.update_user_heartbeat(user["id"], token=token)
    return {
        "ok": True,
        "logged_in": True,
        "user_id": user["id"],
        "user": db.get_user_quota_info(user)
    }

@app.get("/api/auth/me")
def api_me(request: Request):
    user = get_current_user(request)
    if not user:
        return {"logged_in": False, "user": None}
    return {
        "logged_in": True,
        "user": db.get_user_quota_info(user)
    }


@app.post("/api/auth/logout")
def api_logout(request: Request):
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("lw_token")
    if token:
        db.delete_session(token)
    response = JSONResponse({"ok": True, "message": "Logged out successfully"})
    response.delete_cookie("lw_token")
    return response


@app.get("/api/user/quota")
def api_user_quota(request: Request):
    user = require_user(request)
    return db.get_user_quota_info(user)


@app.post("/api/bgstudio/use")
def api_bgstudio_use(request: Request):
    user = require_user(request)
    can_process, reason = db.can_user_process_bg(user["id"])
    if not can_process:
        raise HTTPException(403, reason)
    db.increment_bg_usage(user["id"])
    # Fetch updated user object
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip() or request.cookies.get("lw_token")
    updated = db.get_user_from_token(token)
    return {
        "ok": True,
        "quota": db.get_user_quota_info(updated or user)
    }


# ===========================================================================
# Payment Endpoints (bKash Send Money)
# ===========================================================================

@app.post("/api/payments/submit")
async def api_payment_submit(
    request: Request,
    plan_selected: str = Form(...),
    amount: int = Form(...),
    phone: str = Form(...),
    trx_id: str = Form(...),
    screenshot: UploadFile = File(None)
):
    user = require_user(request)
    screenshot_bytes = None
    ext = ".png"
    if screenshot and screenshot.filename:
        screenshot_bytes = await screenshot.read()
        if len(screenshot_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "Screenshot file size too large (max 10MB)")
        ext = FsPath(screenshot.filename).suffix or ".png"
    
    pay_id = db.submit_payment_request(
        user_id=user["id"],
        plan_selected=plan_selected,
        amount=amount,
        phone=phone,
        trx_id=trx_id,
        screenshot_bytes=screenshot_bytes,
        ext=ext
    )
    return {
        "ok": True,
        "payment_id": pay_id,
        "message": "Payment submission received! Your subscription will be activated upon admin verification. Emergency support: 01794590310."
    }


@app.get("/api/payments/my")
def api_my_payments(request: Request):
    user = require_user(request)
    with db.get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC", (user["id"],))
        return [dict(r) for r in cur.fetchall()]


# ===========================================================================
# Admin Portal & Controller Endpoints
# ===========================================================================

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/api/admin/stats")
def api_admin_stats(request: Request):
    require_admin(request)
    return JSONResponse(db.get_admin_stats(), headers=NO_CACHE_HEADERS)



@app.get("/api/admin/users")
def api_admin_users(request: Request, q: str = Query(None), filter: str = Query(None)):
    require_admin(request)
    return JSONResponse(db.list_users(search=q, filter_type=filter), headers=NO_CACHE_HEADERS)


@app.post("/api/admin/users/{user_id}/access")
async def api_admin_grant_access(user_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    plan = body.get("plan", "free")
    try:
        days = int(body.get("days", 30))
    except Exception:
        days = 30
    role = body.get("role", "user")
    status = body.get("status", "active")
    reset_quota = bool(body.get("reset_quota", False))
    sheets_used = body.get("sheets_used")
    bg_used = body.get("bg_used")
    
    ok = db.grant_user_access(
        user_id=user_id,
        plan=plan,
        days=days,
        role=role,
        status=status,
        reset_quota=reset_quota,
        sheets_used=sheets_used,
        bg_used=bg_used
    )
    if not ok:
        raise HTTPException(404, f"Customer #{user_id} not found in database. The user list may have refreshed.")
    return {"ok": True, "message": f"Access granted successfully for user #{user_id}"}



@app.post("/api/admin/users/{user_id}/plan")
async def api_admin_update_plan(user_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    plan = body.get("plan", "free")
    days = int(body.get("days", 30))
    reset_quota = bool(body.get("reset_quota", False))
    db.update_user_plan(user_id, plan=plan, pro_days=days, reset_quota=reset_quota)
    return {"ok": True, "message": f"User #{user_id} plan updated to {plan}"}


@app.post("/api/admin/users/{user_id}/status")
async def api_admin_update_status(user_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    status = body.get("status", "active")
    db.update_user_status(user_id, status=status)
    return {"ok": True, "message": f"User #{user_id} status updated to {status}"}


@app.delete("/api/admin/users/{user_id}")
def api_admin_delete_user(user_id: int, request: Request):
    require_admin(request)
    db.delete_user(user_id)
    return {"ok": True, "message": f"User #{user_id} deleted"}


@app.get("/api/admin/payments")
def api_admin_payments(request: Request, status: str = Query("all")):
    require_admin(request)
    return JSONResponse(db.list_payments(status_filter=status), headers=NO_CACHE_HEADERS)


@app.post("/api/admin/payments/{payment_id}/review")
async def api_admin_review_payment(payment_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    approve = bool(body.get("approve", True))
    notes = body.get("notes", "")
    ok, res = db.review_payment(payment_id, approve=approve, notes=notes)
    if not ok:
        raise HTTPException(404, res)
    return {"ok": True, "status": res}


@app.get("/api/admin/payments/{payment_id}/proof")
def api_admin_proof(payment_id: int, request: Request):
    require_admin(request)
    with db.get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT screenshot_path FROM payments WHERE id = ?", (payment_id,))
        row = cur.fetchone()
        if not row or not row["screenshot_path"]:
            raise HTTPException(404, "No screenshot found")
        img_path = db.UPLOAD_DIR / row["screenshot_path"]
        if not img_path.exists():
            raise HTTPException(404, "Image file not found on disk")
        return FileResponse(img_path)


@app.get("/admin")
@app.get("/admin.html")
def admin_portal():
    return FileResponse(ROOT / "server" / "static" / "admin.html", headers=NO_CACHE_HEADERS)


app.mount("/static", StaticFiles(directory=ROOT / "server" / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "server" / "static" / "index.html", headers=NO_CACHE_HEADERS)
