"""Linework SaaS backend (FastAPI). Engines live in ../linework; this file only does jobs + HTTP."""
from __future__ import annotations
import io, json, os, sys, time, uuid, shutil, threading, zipfile, re, urllib.parse, multiprocessing as mp

# One math thread per worker process: N workers x N BLAS threads oversubscribes the CPU and makes every icon slower.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path as FsPath

import cv2, numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = FsPath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from linework.pipeline import Options, process_sheet, load_gray, PRESETS  # noqa: E402
from linework.model import Model  # noqa: E402
from linework.render import render_gray, backend_name  # noqa: E402
from linework.trace import ink_map  # noqa: E402
from linework.audit import audit as audit_paths  # noqa: E402
from server import worker  # noqa: E402

DATA = FsPath(os.environ.get("LINEWORK_DATA", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 15 * 1024 * 1024
MAX_SIDE = 5000
MAX_ICONS = 96
KEEP_SECONDS = 24 * 3600

app = FastAPI(title="Linework", version="0.1.0")
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_CTX = mp.get_context("fork") if hasattr(os, "fork") else mp.get_context("spawn")
_Q = _CTX.Queue()
_POOL = None


def pool():
    global _POOL
    if _POOL is None:
        n = max(1, int(os.environ.get("LINEWORK_WORKERS", os.cpu_count() or 2)))
        _POOL = ProcessPoolExecutor(max_workers=n, mp_context=_CTX, initializer=worker.init, initargs=(_Q,))
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
            if j.get("status") in ("queued", "splitting", "running"):
                j["status"] = "cancelled"
                j["cancelled"] = True
                j.setdefault("events", []).append(dict(engine="doctor", msg="Job cancelled by user", t=0, n=len(j.get("events", []))))
        reset_pool()


def cancel_job_by_id(job_id: str):
    with _LOCK:
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
        job = JOBS.get(ev.get("job"))
        if job is None or job.get("cancelled") or job.get("status") == "cancelled":
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
    job["icons"][k].update(status="done", stage="done", metrics=met, iou=met["iou"])
    job["version"] += 1


def _set_pass(job_id, d, jobs, order):
    from linework import setlevel as SL
    from linework.pipeline import second_pass_options
    job = JOBS.get(job_id)
    if job is None or job.get("cancelled") or job.get("status") == "cancelled":
        return
    ok = [k for k, _, _ in jobs if job["icons"][k].get("metrics")]
    mets = {k: job["icons"][k]["metrics"] for k in ok}
    offs = {k: off for k, _, off in jobs}
    crops = {k: c for k, c, _ in jobs}
    weak = SL.weak_icons([mets[k] for k in ok])
    weak = [ok[i] for i in weak]
    if weak:
        job["events"].append(dict(engine="doctor", msg=f"Set check: {len(weak)} icon(s) are weaker than the rest of the set, giving them a longer second pass", t=0, n=len(job["events"])))
        o2 = second_pass_options(Options(**job["options"]))
        futs = {pool().submit(worker.run_icon, (job_id, k, crops[k], offs[k], o2)): k for k in weak}
        for fut in as_completed(futs):
            k = futs[fut]
            try:
                _, off, mj, met = fut.result()
            except Exception:
                continue
            if SL.better(mets[k], met):
                _store_icon(job, d, k, mj, off, met)
                mets[k] = met
    models = [Model.from_json((d / f"icon_local_{k}.json").read_text()) for k in ok]
    new, rep = SL.harmonize_widths(models, [crops[k] for k in ok])
    for k, m0, m1 in zip(ok, models, new):
        if m1 is not m0:
            _store_icon(job, d, k, m1.to_json(), offs[k], mets[k])
    job["set_pass"] = dict(weak=weak, widths_changed=rep["changed"], classes=rep["classes"])
    _finish_composite(job_id)


def _run_job(job_id):
    job = JOBS.get(job_id)
    if job is None or job.get("cancelled") or job.get("status") == "cancelled":
        return
    d = _jobdir(job_id)
    try:
        job["status"] = "splitting"
        gray = cv2.imread(str(d / "original.png"), 0)
        opts = Options(**job["options"])
        W, H, jobs = process_sheet(gray, opts)
        if job.get("cancelled") or job.get("status") == "cancelled":
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
        futs = {}
        p = pool()
        for k, crop, off in order:
            if job.get("cancelled") or job.get("status") == "cancelled":
                break
            job["icons"][k]["status"] = "running"
            futs[p.submit(worker.run_icon, (job_id, k, crop, off, job["options"]))] = k
        for fut in as_completed(futs):
            if job.get("cancelled") or job.get("status") == "cancelled":
                break
            k = futs[fut]
            ic = job["icons"][k]
            try:
                _, off, mj, met = fut.result()
            except Exception as e:  # keep the job alive if one icon fails
                if job.get("cancelled") or job.get("status") == "cancelled":
                    break
                ic.update(status="error", error=str(e))
                continue
            _store_icon(job, d, k, mj, off, met)
            job["done"] += 1
            _finish_composite(job_id)
        if job.get("cancelled") or job.get("status") == "cancelled":
            job["status"] = "cancelled"
            return
        try:  # set-level pass: make the icons one set (shared stroke widths) and give clearly weaker icons a longer second try
            _set_pass(job_id, d, jobs, order)
        except Exception as e:
            job["events"].append(dict(engine="doctor", msg=f"Set-level pass skipped: {e}", t=0, n=len(job["events"])))
        if job.get("cancelled") or job.get("status") == "cancelled":
            job["status"] = "cancelled"
            return
        job["status"] = "done"
        job["seconds"] = round(time.time() - job["created"], 1)
        (d / "job.json").write_text(json.dumps({k: v for k, v in job.items() if k != "events"}))
    except Exception as e:
        if not (job.get("cancelled") or job.get("status") == "cancelled"):
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
    cancel_all_jobs()
    cleared = LS.clear()
    return dict(ok=True, message="Cache cleared, all active jobs cancelled, and worker pool reset", cleared=cleared)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str):
    cancel_job_by_id(job_id)
    return dict(ok=True, job=job_id, status="cancelled")


@app.post("/api/jobs/cancel-all")
def cancel_all_endpoint():
    cancel_all_jobs()
    return dict(ok=True, status="all_cancelled")


@app.get("/api/health")
def health():
    return dict(ok=True, renderer=backend_name(), workers=os.cpu_count(), presets=list(PRESETS))


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    quality: str = Form("standard"),
    clean: float = Form(0.5),          # 0 = pixel match first, 1 = cleanest paths first
    target: float = Form(99.5),
    fresh: bool = Form(True),
):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (15 MB max)")
    gray = _decode_upload(data, file.filename or "")
    return _start(gray, file.filename or "upload", quality, clean, target, fresh=fresh)


def _start(gray, name, quality, clean, target, fresh: bool = True):
    _sweep_old()
    cancel_all_jobs()
    if quality not in PRESETS:
        quality = "standard"
    job_id = uuid.uuid4().hex[:12]
    d = _jobdir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "original.png"), gray)
    clean = float(np.clip(clean, 0, 1))
    opts = dict(quality=quality, target_iou=float(np.clip(target, 90, 99.9)) / 100, dedupe_tol=0.0005 + 0.006 * clean, fresh=bool(fresh))
    job = dict(
        id=job_id, name=name, status="queued", options=opts, created=time.time(), icons=[], events=[],
        width=int(gray.shape[1]), height=int(gray.shape[0]), version=0, done=0, iou=None,
    )
    JOBS[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return dict(id=job_id)


@app.post("/api/samples/{name}")
def sample(name: str, quality: str = "standard", fresh: bool = True):
    fn = ROOT / "samples" / f"{name}.png"
    if not fn.exists() or not name.replace("-", "").isalnum():
        raise HTTPException(404)
    gray = cv2.imread(str(fn), 0)
    return _start(gray, name, quality, 0.5, 99.5, fresh=fresh)


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


app.mount("/static", StaticFiles(directory=ROOT / "server" / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "server" / "static" / "index.html")
