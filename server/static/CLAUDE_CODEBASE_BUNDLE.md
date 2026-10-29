# Linework SaaS - Complete Source Code Bundle for Claude

This document contains the complete source code of the Linework centerline vectorization SaaS platform.



================================================================================
# FILE: README.md
================================================================================

# Linework

Raster icon sheet in, clean single-centerline SVG out. Three backend engines loop until the result matches:

- **Edit** – fits Bezier centerlines, merges duplicate/double lines, smooths kinks (gradient optimiser).
- **Output** – renders the SVG (resvg).
- **Doctor** – compares the render with your image, sends fix commands back to Edit; every fix is re-rendered and rejected if it makes the match worse.

## Run
    pip install -r requirements.txt
    python run.py            # http://localhost:8000   (PORT=9000 python run.py to change)
or `docker build -t linework . && docker run -p 8000:8000 linework`

## Use
Open the page, drop any icon sheet (PNG/JPG/WebP, one icon or many), pick Fast / Standard / Precise.
Watch the engines live, click an icon to zoom, switch Vector / Original / Overlay / Diff,
restyle (colour, weight, background) live, then download SVG or a ZIP of per-icon SVGs.

Note: 100% pixel-identical is not reachable from a blurry JPG; expect ~97-99%. The Doctor aims for 99.5% and stops when no fix improves the match.
Tests: `python tests/test_topology.py; python tests/test_rings.py; python tests/test_budget.py; python tests/test_repair.py`. See CHANGELOG.md. To merge this update into an older copy, give ANTIGRAVITY_PROMPT.md to your coding agent.

## Memory and set consistency (0.6.0)
Results are remembered in `data/lessons` (set `LINEWORK_MEMORY=0` to switch off, `LINEWORK_DATA=<dir>` to move it). `python -m linework.lessons` prints which defect kinds keep coming back; the server serves it at `/api/lessons`.
After all icons of a sheet are done the set pass unifies stroke widths and re-runs clearly weaker icons.

## Join engine (0.7.0)
Every joint (T / L / Y) is checked on its own and failing ones are repaired with the pen / line / arc / shape / unite tools; see `linework/joints.py` and `CHANGELOG.md`. `python tools/outline_view.py result.svg out.png` shows centrelines and marks hooks and nubs.



================================================================================
# FILE: requirements.txt
================================================================================

numpy>=1.26
scipy>=1.11
scikit-image>=0.22
opencv-python-headless>=4.8
resvg-py>=0.1.5
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
pillow>=10.0
threadpoolctl>=3.2



================================================================================
# FILE: run.py
================================================================================

"""Start the Linework server:  python run.py  (then open http://localhost:8000)"""
import os, sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    uvicorn.run("server.app:app", host=os.environ.get("HOST", "0.0.0.0"), port=port, log_level="info")



================================================================================
# FILE: run_sheet.py
================================================================================

import os
os.environ.setdefault('LINEWORK_MEMORY', '0')
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
import sys, time, json, cv2, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from multiprocessing import Pool
from linework.pipeline import *
from linework.model import Model
import linework.render as R

SRC = sys.argv[1]
Q = sys.argv[2] if len(sys.argv) > 2 else 'standard'
OUT = sys.argv[3] if len(sys.argv) > 3 else '/tmp/sheet'
if os.path.dirname(OUT):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

def work(a):
    k, crop, off = a
    r = process_icon(crop, Options(quality=Q), name=f'icon{k+1}')
    return k, off, r['model'].to_json(), r['metrics']

def work2(a):
    k, crop, off, o2 = a
    r = process_icon(crop, Options(**o2), name=f'icon{k+1}')
    return k, off, r['model'].to_json(), r['metrics']

if __name__ == '__main__':
    g = cv2.imread(SRC, 0)
    t = time.time()
    W, H, jobs = process_sheet(g, Options(quality=Q))
    with Pool(2) as p:
        res = p.map(work, jobs)
    from linework import setlevel as SL
    res = sorted(res, key=lambda t: t[0])
    weak = SL.weak_icons([t[3] for t in res])
    if weak:
        o2 = second_pass_options(Options(quality=Q))
        t2 = time.time()
        with Pool(2) as p:
            r2 = p.map(work2, [(jobs[k][0], jobs[k][1], jobs[k][2], o2) for k in weak])
        for new in r2:
            k = new[0]
            old = [t for t in res if t[0] == k][0]
            print('SECOND PASS icon', k+1, '%.4f -> %.4f' % (old[3]['iou'], new[3]['iou']), 'kept new' if SL.better(old[3], new[3]) else 'kept old')
            if SL.better(old[3], new[3]):
                res[res.index(old)] = new
        print('second pass took', round(time.time() - t2), 's')
    mods = [Model.from_json(t[2]) for t in res]
    mods, rep = SL.harmonize_widths(mods, [jobs[t[0]][1] for t in res])
    print('SET widths: icons changed', rep['changed'], 'classes', rep['classes'])
    res = [(t[0], t[1], m.to_json(), t[3]) for t, m in zip(res, mods)]
    allm = Model([], W, H)
    for k, off, mj, met in sorted(res):
        m = Model.from_json(mj)
        m.translate(*off)
        allm.paths += m.paths
        jn = met.get('joins', {})
        jn_tuple = (jn.get('total'), jn.get('clean_first'), sum((jn.get('fixed') or {}).values()), len(jn.get('unresolved', [])))
        sx = met.get('structure', {})
        sx_counts = dict(__import__('collections').Counter(x.get('how') for x in sx.get('sites', []) if x.get('fixed')))
        sx_tuple = (sx.get('found', 0), sx.get('fixed', 0), len(sx.get('unresolved', [])))
        print(k+1, 'IoU %.4f (init %.4f) paths %d nodes %d  %ss' % (
            met['iou'], met['iou_initial'], met['paths'], met['nodes'], met['seconds']
        ), met['issues'], 'JOIN', jn_tuple, 'STRUCT', sx_tuple, sx_counts, 'FIN', __import__('collections').Counter((x['kind'], x['fixed']) for x in met.get('finisher', {}).get('sites', [])))
    svg = allm.svg()
    open(OUT + '.svg', 'w').write(svg)
    img = R.render_gray(svg, W, H)
    cv2.imwrite(OUT + '.png', img)
    a = cv2.imread(SRC, 0)
    from linework.trace import ink_map
    D = ink_map(a)
    b = img < 128
    ref = D > 0.5
    print('SHEET IoU', (b & ref).sum() / (b | ref).sum(), 'time', round(time.time() - t))
    d = np.full(ref.shape + (3,), 255, np.uint8)
    d[ref & b] = (190, 190, 190)
    d[ref & ~b] = (0, 0, 255)
    d[~ref & b] = (255, 0, 0)
    cv2.imwrite(OUT + '_diff.png', d)



================================================================================
# FILE: server/app.py
================================================================================

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
    target: float = Form(98.5),
    fresh: bool = Form(False),
):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (15 MB max)")
    gray = _decode_upload(data, file.filename or "")
    return _start(gray, file.filename or "upload", quality, clean, target, fresh=fresh)


def _start(gray, name, quality, clean, target, fresh: bool = False):
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
def sample(name: str, quality: str = "standard", fresh: bool = False):
    fn = ROOT / "samples" / f"{name}.png"
    if not fn.exists() or not name.replace("-", "").isalnum():
        raise HTTPException(404)
    gray = cv2.imread(str(fn), 0)
    return _start(gray, name, quality, 0.5, 98.5, fresh=fresh)


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



================================================================================
# FILE: server/worker.py
================================================================================

"""Process-pool worker: runs the Edit/Output/Doctor loop for one icon and streams engine events."""
import os, sys
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linework.pipeline import Options, process_icon

_Q = None


def init(q):
    global _Q
    _Q = q
    try:  # forked workers inherit already-initialised thread pools, so limit them explicitly too
        import cv2
        cv2.setNumThreads(1)
    except Exception:
        pass
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except Exception:
        pass


def run_icon(args):
    job_id, k, crop, off, opts = args
    name = f"icon{k + 1}"

    def emit(**kw):
        if _Q is not None:
            kw.update(job=job_id, k=k)
            _Q.put(kw)

    r = process_icon(crop, Options(**opts), emit=emit, name=name)
    return k, off, r["model"].to_json(), r["metrics"]



================================================================================
# FILE: server/static/index.html
================================================================================

<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linework AI — Redraw · Vector · Perfect</title>
<meta name="description" content="Turn raster line art and icons into clean single-centerline SVGs with luxury AI-powered precision.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2305080c'/%3E%3Cpath d='M8 24 L16 8 L24 24 M11 19 L21 19' fill='none' stroke='%2300f5a0' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/style.css">
</head>
<body class="luxury-theme">
<div class="app-layout">

  <!-- ================= Left Navigation Sidebar ================= -->
  <aside class="sidebar" id="sidebar">
    <div class="brand-zone">
      <a class="brand" href="/" aria-label="Linework AI home">
        <div class="brand-glyph">
          <svg viewBox="0 0 32 32" width="24" height="24">
            <defs>
              <linearGradient id="glyphGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00ffd5"/>
                <stop offset="100%" stop-color="#00e599"/>
              </linearGradient>
            </defs>
            <path d="M7 25 L16 7 L25 25 M10 20 L22 20" fill="none" stroke="url(#glyphGrad)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-title">Linework AI</span>
          <span class="brand-sub">Redraw · Vector · Perfect</span>
        </div>
      </a>
    </div>

    <nav class="nav-menu" aria-label="Main Navigation">
      <a href="/" class="nav-item" id="navHome" title="Home">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <span>Home</span>
      </a>
      <a href="#redraw" class="nav-item active" id="navRedraw" title="Redraw Workspace">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>
        <span>Redraw</span>
      </a>
      <a href="#projects" class="nav-item" id="navProjects" title="My Projects">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
        <span>My Projects</span>
      </a>
      <a href="#templates" class="nav-item" id="navTemplates" title="Templates">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
        <span>Templates</span>
      </a>
      <a href="#settings" class="nav-item" id="navSettings" title="Settings">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
        <span>Settings</span>
      </a>
    </nav>

    <!-- Bottom Promo / Mission Card -->
    <div class="sidebar-promo">
      <div class="promo-icon">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#00f5a0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
      </div>
      <div class="promo-title">Turn Your Line Art into Perfect Vectors</div>
      <div class="promo-desc">Fast. Accurate. Beautiful.</div>
      <div class="promo-waves"></div>
    </div>
  </aside>

  <!-- ================= Main Body Area ================= -->
  <div class="main-column">

    <!-- Top App Header -->
    <header class="app-header">
      <div class="header-left">
        <button class="icon-btn back-btn" id="newJob" title="Return to new upload" aria-label="Return to upload">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </button>
        <div class="project-info">
          <div class="project-title-row">
            <span class="project-title" id="jobName">Minimal Black Outline UI Icon Set</span>
            <span class="edit-icon" title="Project name"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg></span>
          </div>
          <div class="project-sub" id="jobMeta">6 icons · 1024 × 1024</div>
        </div>
      </div>

      <div class="header-right">
        <button class="status-pill" id="btnClearCacheDirect" title="Clear all stored icon cache & memory" style="cursor:pointer; background:rgba(255,80,80,0.08); border:1px solid rgba(255,80,80,0.25);">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#ff6b6b" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/></svg>
          <span class="status-text" style="color:#ff6b6b;">Clear Cache</span>
        </button>
        <button class="status-pill" id="btnLessons" title="View AI Lessons & Defect Memory" style="cursor:pointer; background:rgba(0,245,160,0.08); border:1px solid rgba(0,245,160,0.25);">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--accent)" stroke-width="2.2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          <span class="status-text" style="color:var(--accent);">AI Memory</span>
        </button>
        <span class="status-pill" id="health">
          <span class="status-dot"></span>
          <span class="status-text">AI Engine Online</span>
        </span>
        <button class="icon-btn" title="Settings" aria-label="Settings">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
        <div class="user-avatar" title="User profile">EK</div>
      </div>
    </header>

    <!-- Global Progress Bar Indicator -->
    <div class="global-progress" id="prog"><i class="prog-bar-fill"></i></div>

    <main class="content-scroll">

      <!-- ============ Landing / Upload View ============ -->
      <section id="landing" class="landing-view">
        <div class="landing-grid">

          <!-- Left Column: Upload Hero & Dropzone -->
          <div class="landing-main">
            <div class="section-heading">
              <div class="heading-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#00f5a0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>
              </div>
              <div>
                <h2>Upload Your Line Art</h2>
                <p>Drop your image here or click to browse. We'll turn it into clean, scalable vectors with perfect precision.</p>
              </div>
            </div>

            <!-- Luxury Glass Dropzone -->
            <div class="card dropzone-card">
              <label class="drop-zone" id="drop" tabindex="0">
                <input id="file" type="file" accept="image/png,image/jpeg,image/webp,image/bmp,image/svg+xml,.svg,.zip" hidden>
                <div class="drop-cloud-icon">
                  <svg viewBox="0 0 24 24" width="46" height="46" fill="none" stroke="#00f5a0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/>
                    <path d="M12 12v9"/>
                    <path d="m16 16-4-4-4 4"/>
                  </svg>
                </div>
                <div class="drop-primary-text">Drag &amp; Drop Your Image Here</div>
                <div class="drop-secondary-text">or click to browse</div>
                <div class="format-badges">
                  <span class="fmt-label">Supported formats:</span>
                  <span class="fmt-tag">PNG</span>
                  <span class="fmt-tag">JPG</span>
                  <span class="fmt-tag">SVG</span>
                  <span class="fmt-tag">WEBP</span>
                  <span class="fmt-tag">BMP</span>
                </div>
              </label>

              <!-- Upload Configuration Options -->
              <div class="upload-options">
                <div class="opt-group">
                  <div class="opt-header">
                    <span>Quality Mode</span>
                    <span class="opt-badge">AI Precision</span>
                  </div>
                  <div class="seg quality-seg" id="quality" role="radiogroup">
                    <button type="button" data-v="fast" role="radio">Fast</button>
                    <button type="button" data-v="standard" role="radio" class="on">Standard</button>
                    <button type="button" data-v="precise" role="radio">Precise</button>
                  </div>
                </div>

                <div class="opt-group grow">
                  <div class="opt-header">
                    <span>Path Optimization</span>
                    <span class="opt-val" id="cleanHint">Balanced</span>
                  </div>
                  <div class="range-wrap">
                    <span class="range-min">Exact match</span>
                    <input id="clean" type="range" min="0" max="1" step="0.05" value="0.5">
                    <span class="range-max">Cleanest paths</span>
                  </div>
                </div>

                <div class="opt-group">
                  <div class="opt-header">
                    <span>Cache Mode</span>
                    <span class="opt-badge" id="freshBadge" style="color:var(--accent);">Fresh (No Cache)</span>
                  </div>
                  <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:12.5px; color:var(--text-main); margin-top:8px; user-select:none;">
                    <input id="freshRun" type="checkbox" checked style="cursor:pointer; width:16px; height:16px; accent-color:var(--accent);">
                    <span>Bypass Cache (Force fresh run)</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Samples Selector -->
            <div class="samples-row">
              <span class="samples-label">or try a sample:</span>
              <button class="sample-chip" data-sample="home-icons">
                <span class="chip-dot"></span>
                <b>Home &amp; living</b>
                <em>12 icons</em>
              </button>
              <button class="sample-chip" data-sample="basic-set">
                <span class="chip-dot"></span>
                <b>Basic UI set</b>
                <em>6 icons</em>
              </button>
            </div>

            <!-- Lower Capabilities & Features Cards -->
            <div class="capabilities-grid">
              <div class="cap-card">
                <div class="cap-icon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#00f5a0" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg></div>
                <div class="cap-body">
                  <b>Smart Path Detection</b>
                  <span>Identifies and traces clean vector centerlines.</span>
                </div>
              </div>
              <div class="cap-card">
                <div class="cap-icon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#00f5a0" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
                <div class="cap-body">
                  <b>Node Optimization</b>
                  <span>Removes extra nodes and smooths curvature kinks.</span>
                </div>
              </div>
              <div class="cap-card">
                <div class="cap-icon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#00f5a0" stroke-width="2"><rect width="8" height="8" x="3" y="3" rx="2"/><path d="m7 11 4-4 4 4"/><rect width="8" height="8" x="13" y="13" rx="2"/></svg></div>
                <div class="cap-body">
                  <b>Duplicate Centerlines</b>
                  <span>Detects and removes double lines &amp; overlaps.</span>
                </div>
              </div>
              <div class="cap-card">
                <div class="cap-icon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#00f5a0" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></div>
                <div class="cap-body">
                  <b>High Precision Output</b>
                  <span>Doctor engine verifies every change against your image.</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Info & Stats Showcase -->
          <div class="landing-aside">
            <div class="card showcase-card">
              <div class="showcase-glow"></div>
              <div class="showcase-art">
                <svg viewBox="0 0 120 120" width="80" height="80">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(0,229,153,0.15)" stroke-width="1.5" stroke-dasharray="4 4"/>
                  <circle cx="60" cy="60" r="36" fill="none" stroke="rgba(0,255,213,0.3)" stroke-width="1.5"/>
                  <path d="M60 22 L72 50 L60 85 L48 50 Z" fill="rgba(0,229,153,0.08)" stroke="#00f5a0" stroke-width="2" stroke-linejoin="round"/>
                  <circle cx="60" cy="50" r="4" fill="#00ffd5"/>
                  <circle cx="48" cy="50" r="3" fill="#00e599"/>
                  <circle cx="72" cy="50" r="3" fill="#00e599"/>
                </svg>
              </div>
              <h3>From Line Art to Vector</h3>
              <p>Our AI analyzes your image, detects paths, removes imperfections and creates a clean, editable vector file.</p>
              
              <ul class="feature-bullets">
                <li><span class="f-dot"></span><b>Perfect for Icons</b> — Keep your icons sharp &amp; clean</li>
                <li><span class="f-dot"></span><b>Ideal for Logos</b> — Professional quality results</li>
                <li><span class="f-dot"></span><b>Works with Any Line Art</b> — Hand-drawn, sketch, or simple outlines</li>
              </ul>

              <!-- AI Engine Specs -->
              <div class="specs-block">
                <div class="spec-header">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#00f5a0" stroke-width="2"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                  <span>AI Redraw Engine</span>
                </div>
                <div class="spec-metrics">
                  <div class="sm-item">
                    <span class="sm-val">&lt; 5s</span>
                    <span class="sm-lbl">Avg. time</span>
                  </div>
                  <div class="sm-item">
                    <span class="sm-val">99.8%</span>
                    <span class="sm-lbl">Accuracy</span>
                  </div>
                  <div class="sm-item">
                    <span class="sm-val">24/7</span>
                    <span class="sm-lbl">Available</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- ============ Redraw Workspace View ============ -->
      <section id="work" class="work-view" hidden>
        
        <!-- Workspace Main Grid (Canvas on Left, Engine & Metrics on Right) -->
        <div class="workspace-grid">

          <!-- Left Column: Main Canvas & Tools -->
          <div class="canvas-column">

            <!-- Canvas Top Toolbar -->
            <div class="canvas-topbar">
              <div class="view-switcher seg" id="view" role="tablist">
                <button data-v="original" role="tab">Original</button>
                <button data-v="vector" role="tab" class="on">Vector</button>
                <button data-v="overlay" role="tab">Overlay</button>
                <button data-v="diff" role="tab">Diff</button>
              </div>

              <!-- Dedicated Artboard Background Switcher (White / Grid / Dark) -->
              <div class="artboard-switcher seg" id="artboardSwitcher">
                <span class="ab-label">Artboard</span>
                <button type="button" class="ab-btn on" data-bg="#ffffff" title="Crisp White Artboard (Black Strokes)">
                  <i class="ab-dot white"></i><span>White</span>
                </button>
                <button type="button" class="ab-btn" data-bg="grid" title="Transparent Checkerboard Grid">
                  <i class="ab-dot grid"></i><span>Transparent</span>
                </button>
                <button type="button" class="ab-btn" data-bg="#0c131d" title="Dark Artboard (Glowing White/Neon Strokes)">
                  <i class="ab-dot dark"></i><span>Black</span>
                </button>
              </div>

              <div class="topbar-right">
                <div class="tool-strip">
                  <button class="tool-btn active" title="Pointer select tool"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 3 7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/></svg></button>
                  <button class="tool-btn" title="Path editor"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 19 7-7 3 3-7 7-3-3z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg></button>
                  <button class="tool-btn" title="Nodes view"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><line x1="8.5" y1="8.5" x2="15.5" y2="15.5"/></svg></button>
                </div>
              </div>
            </div>

            <!-- Stage & Canvas Frame -->
            <div class="stage-frame">
              <!-- Artboard Floating Indicator -->
              <div class="artboard-indicator" id="artboardIndicator">
                <span class="ab-tag">ARTBOARD</span>
                <span class="ab-size" id="artboardDims">-- × -- px</span>
              </div>

              <div class="stage" id="stage">
                <!-- Checkered Canvas Canvas Wrapper -->
                <div class="canvas ab-white" id="canvas">
                  <img id="imgOrig" alt="Original raster image">
                  <div id="vec"></div>
                  <img id="imgDiff" alt="Diff image">
                  <div id="focus" class="focus" hidden></div>
                </div>

                <!-- Laser Scanning Beam Overlay (Processing Animation) -->
                <div class="scan-beam" id="scanBeam"></div>
                <!-- Node Points Grid Overlay (Processing Animation) -->
                <div class="node-grid-overlay" id="nodeOverlay"></div>

                <!-- Canvas Legend for Diff Mode -->
                <div class="legend" id="legend" hidden>
                  <span><i style="background:#22c55e"></i>match</span>
                  <span><i style="background:#ef4444"></i>missing</span>
                  <span><i style="background:#3b82f6"></i>extra</span>
                </div>
              </div>

              <!-- Canvas Bottom Floating Control Strip -->
              <div class="canvas-footer-bar">
                <div class="footer-status-pill" id="canvasStatusPill">
                  <span class="pulse-dot"></span>
                  <span class="status-msg" id="canvasStatusMsg">Ready</span>
                  <div class="mini-prog-track" id="miniProgTrack"><div class="mini-prog-fill" id="miniProgFill"></div></div>
                </div>
                
                <div class="footer-counters">
                  <span class="counter-badge" id="canvasPathsCount"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Paths <b id="countPathsVal">--</b></span>
                  <span class="counter-badge" id="canvasNodesCount"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="12" cy="12" r="2"/></svg> Nodes <b id="countNodesVal">--</b></span>
                </div>

                <div class="zoom-cluster">
                  <button id="zout" class="zoom-btn" aria-label="Zoom out">−</button>
                  <button id="zfit" class="zoom-btn zoom-fit">Fit</button>
                  <button id="zin" class="zoom-btn" aria-label="Zoom in">+</button>
                </div>
              </div>
            </div>

            <div class="summary" id="summary" hidden></div>

          </div>

          <!-- Right Column: AI Processing, Stages & Metrics -->
          <div class="sidebar-column">

            <!-- AI Engine Processing Status Card -->
            <div class="card status-panel" id="processingCard">
              <div class="status-card-top">
                <div class="radar-wrap" id="radarWrap">
                  <div class="radar-pulse"></div>
                  <div class="radar-ring"></div>
                  <div class="radar-core">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#00ffd5" stroke-width="2.5" stroke-linecap="round"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3z"/></svg>
                  </div>
                </div>
                <div class="status-card-text">
                  <h3 class="status-title" id="procTitle">Processing...</h3>
                  <p class="status-sub" id="procSub">AI is analyzing and redrawing your image into clean vector paths.</p>
                </div>
              </div>

              <!-- Main Percentage Progress Bar -->
              <div class="progress-section">
                <div class="prog-track">
                  <div class="prog-fill" id="procBarFill" style="width: 4%;"></div>
                </div>
                <div class="prog-meta">
                  <span class="prog-label">Overall Progress</span>
                  <span class="prog-percent" id="procPercent">0%</span>
                </div>
                <div class="proc-cancel-wrap">
                  <button type="button" class="btn-cancel-job" id="btnCancelJob" title="Cancel current redraw process">
                    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M18 6 6 18M6 6l12 12"/></svg>
                    <span>Cancel Redraw</span>
                  </button>
                </div>
              </div>

              <!-- Processing Stages Checklist -->
              <div class="stages-list">
                <div class="stage-row" id="stageImageAnalysis" data-stage="split">
                  <span class="stage-state-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg></span>
                  <div class="stage-info">
                    <div class="stage-name">Image Analysis</div>
                    <div class="stage-desc">Detecting shapes and details...</div>
                  </div>
                  <span class="stage-time" id="timeAnalysis">0.8s</span>
                </div>

                <div class="stage-row" id="stagePathTracing" data-stage="trace">
                  <span class="stage-state-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg></span>
                  <div class="stage-info">
                    <div class="stage-name">Path Tracing</div>
                    <div class="stage-desc">Creating vector paths...</div>
                  </div>
                  <span class="stage-time" id="timeTracing">--</span>
                </div>

                <div class="stage-row" id="stageCurveOpt" data-stage="edit">
                  <span class="stage-state-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg></span>
                  <div class="stage-info">
                    <div class="stage-name">Curve Optimization</div>
                    <div class="stage-desc">Smoothing and refining curves...</div>
                  </div>
                  <span class="stage-time" id="timeCurve">--</span>
                </div>

                <div class="stage-row" id="stageOutputGen" data-stage="output">
                  <span class="stage-state-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg></span>
                  <div class="stage-info">
                    <div class="stage-name">Output Generation</div>
                    <div class="stage-desc">Finalizing vector file...</div>
                  </div>
                  <span class="stage-time" id="timeOutput">--</span>
                </div>
              </div>

              <!-- Processing Metrics 2x2 Grid -->
              <div class="metrics-grid">
                <div class="metric-tile">
                  <div class="tile-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#00f5a0" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div>
                  <div class="tile-body">
                    <span class="tile-label">Processing Time</span>
                    <b class="tile-val" id="metricTime">0.0s</b>
                  </div>
                </div>

                <div class="metric-tile">
                  <div class="tile-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#00ffd5" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
                  <div class="tile-body">
                    <span class="tile-label">Total Paths</span>
                    <b class="tile-val" id="metricPaths">--</b>
                  </div>
                </div>

                <div class="metric-tile">
                  <div class="tile-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#00e599" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><line x1="8.5" y1="8.5" x2="15.5" y2="15.5"/></svg></div>
                  <div class="tile-body">
                    <span class="tile-label">Total Nodes</span>
                    <b class="tile-val" id="metricNodes">--</b>
                  </div>
                </div>

                <div class="metric-tile">
                  <div class="tile-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#38bdf8" stroke-width="2"><rect width="8" height="8" x="3" y="3" rx="2"/><rect width="8" height="8" x="13" y="13" rx="2"/></svg></div>
                  <div class="tile-body">
                    <span class="tile-label">Duplicate Centerlines</span>
                    <b class="tile-val" id="metricDupes">0</b>
                  </div>
                </div>
              </div>

            </div>

            <!-- Style & Export Accordion / Panel -->
            <div class="card panel" id="stylePanel">
              <div class="panel-header">
                <h3>Restyle &amp; Settings <span class="badge-live">Live</span></h3>
              </div>
              <div class="panel-body">
                <label class="param-row">
                  <span>Stroke colour</span>
                  <input type="color" id="stroke" value="#111111">
                </label>
                <label class="param-row">
                  <span>Stroke weight <b id="scaleV">100%</b></span>
                  <input type="range" id="scale" min="0.5" max="1.6" step="0.02" value="1">
                </label>
                <label class="param-row">
                  <span>Background</span>
                  <select id="bg">
                    <option value="#ffffff">White</option>
                    <option value="none" selected>Transparent</option>
                    <option value="#0b0b0c">Dark</option>
                  </select>
                </label>
              </div>
            </div>

            <!-- Export Buttons Panel -->
            <div class="card panel" id="exportPanel">
              <div class="panel-header">
                <h3>Export Vector Output</h3>
              </div>
              <div class="panel-body">
                <div class="export-btns-list">
                  <button class="btn template-action-btn" id="btnSendToTemplate">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.3"><rect width="18" height="18" x="3" y="3" rx="3"/><path d="M9 3v18M3 9h6M14 9h7M14 15h7"/></svg>
                    <span>Send to Template Studio</span>
                  </button>
                  <a class="btn primary-action-btn" id="dlSvg" href="#">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>Download Sheet SVG</span>
                  </a>
                  <a class="btn secondary-action-btn" id="dlEps" href="#" title="Download Clean Centerlines as PostScript EPS">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h4M8 17h6"/></svg>
                    <span>Download Sheet EPS</span>
                  </a>
                  <a class="btn secondary-action-btn" id="dlZip" href="#">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
                    <span>All Icons (.ZIP)</span>
                  </a>
                  <button class="btn secondary-action-btn" id="copy">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    <span>Copy SVG</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Engine Activity Drawer -->
            <details class="card panel log-drawer" id="logBox">
              <summary class="log-summary">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                <span>Engine Activity Log</span>
                <span class="count-pill" id="iconCount"></span>
              </summary>
              <div class="engines-pills" id="engines" hidden>
                <div class="eng" data-e="edit"><i></i><b>Edit</b><em></em></div>
                <div class="eng" data-e="output"><i></i><b>Output</b><em></em></div>
                <div class="eng" data-e="doctor"><i></i><b>Doctor</b><em></em></div>
              </div>
              <ol class="log-entries" id="log"></ol>
            </details>

          </div>

        </div>

        <!-- ================= Bottom Section: Icon Match Results & Comparison ================= -->
        <div class="bottom-analysis-row">
          
          <!-- Left: Icon Match Results Cards -->
          <div class="card icon-results-card">
            <div class="results-header">
              <div class="target-glyph">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#00f5a0" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
              </div>
              <div class="results-title-group">
                <h3>Icon Match Results</h3>
                <span class="results-sub" id="matchSubText">Detected icons · Calculating match...</span>
              </div>
            </div>

            <!-- Scrollable list of icon cards -->
            <div class="icon-cards-carousel" id="icons">
              <!-- Dynamically populated icon cards -->
            </div>
          </div>

          <!-- Right: Selected Icon Comparison (Original -> Vector) -->
          <div class="card comparison-card" id="comparisonCard">
            <div class="comp-box">
              <div class="comp-label">Original</div>
              <div class="comp-preview-frame" id="compOrigFrame">
                <img id="compOrigImg" alt="Original icon crop" src="">
              </div>
            </div>

            <div class="comp-arrow">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#00f5a0" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </div>

            <div class="comp-box active-vector-box">
              <div class="comp-label">Vector</div>
              <span class="match-badge" id="compMatchBadge">98.1% Match</span>
              <div class="comp-preview-frame" id="compVecFrame">
                <img id="compVecImg" alt="Vector icon preview" src="">
              </div>
            </div>
          </div>

        </div>

      </section>

      <!-- ============ Template Studio View ============ -->
      <section id="templateStudio" class="template-studio-view" hidden>
        
        <!-- Top Toolbar -->
        <div class="template-topbar">
          <div class="topbar-left">
            <button class="btn secondary-action-btn back-btn" id="btnBackToWork">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m15 18-6-6 6-6"/></svg>
              <span>Back to Redraw</span>
            </button>
            <div class="template-title-group">
              <h2>Presentation Template Studio</h2>
              <span class="template-sub" id="tplMetaSub">Merged Vector Artboard · Left Info + Right Vector Icons</span>
            </div>
          </div>

          <div class="topbar-right">
            <a class="btn primary-action-btn" id="btnDlTemplateSvg" href="#" download="presentation.svg">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Download SVG</span>
            </a>
            <a class="btn primary-action-btn eps-btn" id="btnDlTemplateEps" href="#" download="presentation.eps">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h4M8 17h6"/></svg>
              <span>Download EPS</span>
            </a>
            <a class="btn secondary-action-btn" id="btnDlTemplateZip" href="#">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
              <span>All Assets (.ZIP)</span>
            </a>
          </div>
        </div>

        <!-- Studio Main Workspace Grid -->
        <div class="template-grid">

          <!-- Left Controls Column -->
          <div class="template-controls-sidebar">

            <!-- Presets Section -->
            <div class="card panel tpl-panel">
              <div class="panel-header">
                <h3>Style Presets</h3>
                <span class="badge-live">1-Click</span>
              </div>
              <div class="panel-body">
                <div class="preset-cards-grid" id="presetList">
                  <!-- Populated dynamically with swatches -->
                </div>
              </div>
            </div>

            <!-- Set Info & Metadata Section -->
            <div class="card panel tpl-panel">
              <div class="panel-header">
                <h3>Icon Set Details</h3>
              </div>
              <div class="panel-body">
                <label class="param-row text-input-row">
                  <span>Title</span>
                  <input type="text" id="tplTitle" value="Minimal Vector Line Icons" placeholder="e.g. Essential UI Icons">
                </label>
                <label class="param-row text-input-row">
                  <span>Category / Subtitle</span>
                  <input type="text" id="tplSubtitle" value="Clean Centerline Vector Icon Collection" placeholder="e.g. UI & Mobile App Collection">
                </label>
                <label class="param-row text-input-row">
                  <span>Grid Spec</span>
                  <input type="text" id="tplGrid" value="64 × 64 px Grid" placeholder="e.g. 64x64 px">
                </label>
                <label class="param-row text-input-row">
                  <span>Author / Brand</span>
                  <input type="text" id="tplAuthor" value="Linework AI Precision Engine" placeholder="Your Brand or Name">
                </label>
              </div>
            </div>

            <!-- Custom Colors / Custom Preset Section -->
            <div class="card panel tpl-panel">
              <div class="panel-header">
                <h3>Custom Colors</h3>
                <span class="opt-val" id="customColorHint">Live Edit</span>
              </div>
              <div class="panel-body">
                <label class="param-row">
                  <span>Artboard Background</span>
                  <input type="color" id="tplBgColor" value="#090d14">
                </label>
                <label class="param-row">
                  <span>Left Info Card</span>
                  <input type="color" id="tplPanelBgColor" value="#121824">
                </label>
                <label class="param-row">
                  <span>Brand &amp; Accent</span>
                  <input type="color" id="tplAccentColor" value="#00f5a0">
                </label>
                <label class="param-row">
                  <span>Heading &amp; Text</span>
                  <input type="color" id="tplTextColor" value="#ffffff">
                </label>
                <label class="param-row">
                  <span>Icon Stroke Color</span>
                  <input type="color" id="tplStrokeColor" value="#00f5a0">
                </label>
                <label class="param-row">
                  <span>Stroke Weight <b id="tplScaleVal">100%</b></span>
                  <input type="range" id="tplStrokeScale" min="0.5" max="2.0" step="0.05" value="1.0">
                </label>
              </div>
            </div>

            <!-- Layout & Display Options -->
            <div class="card panel tpl-panel">
              <div class="panel-header">
                <h3>Artboard Layout</h3>
              </div>
              <div class="panel-body">
                <div class="seg tpl-layout-seg" id="tplLayoutSeg">
                  <button type="button" data-v="landscape" class="on">Landscape (16:10)</button>
                  <button type="button" data-v="square">Square (1:1)</button>
                </div>
                <label class="checkbox-row" style="margin-top:12px; display:flex; align-items:center; gap:8px; font-size:12.5px; cursor:pointer;">
                  <input type="checkbox" id="tplShowGrid" checked style="accent-color:var(--accent);">
                  <span>Show background dot grid</span>
                </label>
              </div>
            </div>

          </div>

          <!-- Right Preview Column -->
          <div class="template-preview-column">
            <div class="stage-frame template-stage-frame">
              <div class="artboard-indicator">
                <span class="ab-tag">PRESENTATION ARTBOARD</span>
                <span class="ab-size" id="tplDimsBadge">1600 × 1000 px · SVG &amp; EPS Merged</span>
              </div>

              <!-- Main scrollable / zoomable preview canvas -->
              <div class="template-stage" id="templateStage">
                <div class="template-artboard-container" id="templateSvgContainer">
                  <!-- The merged SVG renders here live -->
                </div>
              </div>

              <!-- Bottom zoom strip -->
              <div class="canvas-footer-bar">
                <div class="footer-status-pill">
                  <span class="pulse-dot"></span>
                  <span>Merged Template: Left Info Card + Right Traced Vector Icons</span>
                </div>
                <div class="zoom-cluster">
                  <button id="tplZout" class="zoom-btn">−</button>
                  <button id="tplZfit" class="zoom-btn zoom-fit">Fit</button>
                  <button id="tplZin" class="zoom-btn">+</button>
                </div>
              </div>
            </div>
          </div>

        </div>

      </section>

    </main>

  </div>

</div>

<!-- AI Lessons Modal -->
<div class="modal-backdrop" id="lessonsModal" style="display:none;">
  <div class="modal-card">
    <div class="modal-header">
      <h3>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--accent)" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        What Keeps Going Wrong (AI Lessons & Defect Census)
      </h3>
      <div style="display:flex; align-items:center; gap:10px;">
        <button class="btn" id="btnClearLessons" style="background:rgba(255,80,80,0.12); border:1px solid rgba(255,80,80,0.3); color:#ff6b6b; padding:5px 10px; font-size:12px; border-radius:6px; cursor:pointer; display:flex; align-items:center; gap:5px;">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          Clear Cache
        </button>
        <button class="icon-btn" id="closeLessonsModal" title="Close" style="color:var(--text-muted); font-size:16px;">✕</button>
      </div>
    </div>
    <div class="modal-body" id="lessonsContent">
      <div style="text-align:center; padding:30px; color:var(--text-dim);">Loading memory data...</div>
    </div>
  </div>
</div>

<!-- Notification Toast -->
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<!-- Application Script -->
<script src="/static/app.js"></script>
</body>
</html>



================================================================================
# FILE: server/static/style.css
================================================================================

/* ==========================================================================
   Linework AI — Luxury SaaS Design System & Motion Graphics
   ========================================================================== */

:root {
  --bg-darkest: #05080c;
  --bg-darker: #070c12;
  --bg-dark: #0a111a;
  --bg-panel: rgba(12, 19, 29, 0.76);
  --bg-panel-solid: #0d1521;
  --bg-card: rgba(15, 24, 37, 0.68);
  --bg-card-hover: rgba(19, 31, 48, 0.85);
  
  --line-dim: rgba(255, 255, 255, 0.06);
  --line-subtle: rgba(0, 229, 153, 0.12);
  --line-glow: rgba(0, 245, 160, 0.35);
  --line-bright: rgba(0, 255, 213, 0.6);

  --accent: #00f5a0;
  --accent-mint: #00ffd5;
  --accent-teal: #0d9488;
  --accent-cyan: #38bdf8;
  --accent-gradient: linear-gradient(135deg, #00ffd5 0%, #00f5a0 50%, #00d287 100%);
  --accent-glow: 0 0 24px rgba(0, 245, 160, 0.22);
  --accent-glow-strong: 0 0 35px rgba(0, 245, 160, 0.45);

  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --text-dark: #334155;

  --ok: #22c55e;
  --warn: #f59e0b;
  --bad: #ef4444;

  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;

  --font-sans: "Plus Jakarta Sans", Inter, system-ui, -apple-system, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, monospace;
}

*, *::before, *::after {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100vh;
  max-height: 100vh;
  background: var(--bg-darkest);
  color: var(--text-main);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow: hidden;
}

button, input, select {
  font-family: inherit;
  color: inherit;
}

[hidden] {
  display: none !important;
}

/* ================= Layout Structure ================= */

.app-layout {
  display: flex;
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: radial-gradient(circle at 18% 12%, rgba(0, 255, 213, 0.04) 0%, transparent 45%),
              radial-gradient(circle at 82% 80%, rgba(0, 229, 153, 0.03) 0%, transparent 50%),
              var(--bg-darkest);
}

/* ================= Sidebar Navigation ================= */

.sidebar {
  width: 230px;
  flex-shrink: 0;
  background: rgba(8, 13, 20, 0.88);
  backdrop-filter: blur(24px);
  border-right: 1px solid var(--line-dim);
  display: flex;
  flex-direction: column;
  padding: 18px 14px;
  position: relative;
  height: 100vh;
  z-index: 30;
  overflow-y: auto;
  scrollbar-width: thin;
}

.brand-zone {
  margin-bottom: 28px;
  padding-left: 6px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: var(--text-main);
}

.brand-glyph {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(0, 255, 213, 0.15), rgba(0, 229, 153, 0.05));
  border: 1px solid var(--line-subtle);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.18);
  display: grid;
  place-items: center;
  transition: transform 0.25s, box-shadow 0.25s;
}

.brand:hover .brand-glyph {
  transform: scale(1.04);
  box-shadow: 0 0 24px rgba(0, 245, 160, 0.35);
}

.brand-title {
  display: block;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #ffffff;
}

.brand-sub {
  display: block;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--text-dim);
  text-transform: uppercase;
  margin-top: 1px;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 500;
  border: 1px solid transparent;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-item svg {
  color: var(--text-dim);
  transition: color 0.2s, transform 0.2s;
}

.nav-item:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.03);
}

.nav-item:hover svg {
  color: var(--accent);
  transform: translateX(1px);
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(0, 245, 160, 0.14) 0%, rgba(0, 255, 213, 0.04) 100%);
  border-color: var(--line-subtle);
  color: #ffffff;
  box-shadow: 0 0 20px rgba(0, 245, 160, 0.12);
}

.nav-item.active svg {
  color: var(--accent);
}

.sidebar-promo {
  position: relative;
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(14, 25, 38, 0.8), rgba(8, 14, 22, 0.95));
  border: 1px solid rgba(0, 229, 153, 0.16);
  padding: 18px 16px;
  overflow: hidden;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
}

.sidebar-promo::before {
  content: "";
  position: absolute;
  top: -30%;
  left: -20%;
  width: 140%;
  height: 140%;
  background: radial-gradient(circle, rgba(0, 245, 160, 0.12) 0%, transparent 60%);
  pointer-events: none;
}

.promo-icon {
  margin-bottom: 10px;
}

.promo-title {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  color: #ffffff;
  margin-bottom: 4px;
}

.promo-desc {
  font-size: 11px;
  color: var(--accent);
  font-weight: 500;
}

/* ================= Main Column Area ================= */

.main-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
}

/* App Header */
.app-header {
  height: 52px;
  min-height: 52px;
  flex-shrink: 0;
  padding: 0 20px;
  background: rgba(8, 13, 20, 0.75);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--line-dim);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  position: relative;
  z-index: 25;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line-dim);
  color: var(--text-muted);
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: rgba(0, 245, 160, 0.08);
  border-color: var(--line-subtle);
  color: #ffffff;
}

.project-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.project-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-title {
  font-size: 14.5px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}

.edit-icon {
  color: var(--text-dim);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.project-sub {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: rgba(0, 245, 160, 0.06);
  border: 1px solid rgba(0, 245, 160, 0.2);
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.1);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
  animation: pulseDot 2s infinite ease-in-out;
}

@keyframes pulseDot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.6; }
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00f5a0, #00ffd5);
  color: #05080c;
  font-weight: 700;
  font-size: 13px;
  display: grid;
  place-items: center;
  box-shadow: 0 0 12px rgba(0, 245, 160, 0.3);
  cursor: pointer;
}

/* Global Progress Line */
.global-progress {
  height: 2px;
  min-height: 2px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.04);
  position: relative;
  overflow: hidden;
  z-index: 24;
}

.prog-bar-fill {
  display: block;
  height: 100%;
  width: 0;
  background: var(--accent-gradient);
  box-shadow: 0 0 10px var(--accent);
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.global-progress.done .prog-bar-fill {
  background: #22c55e;
  box-shadow: 0 0 10px #22c55e;
}

/* Main Scrollable Canvas / View Area */
.content-scroll {
  flex: 1;
  min-height: 0;
  padding: 8px 16px 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Common Card Style */
.card {
  background: var(--bg-panel);
  backdrop-filter: blur(20px);
  border: 1px solid var(--line-subtle);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 36px -8px rgba(0, 0, 0, 0.6);
  position: relative;
}

/* ================= Landing / Upload Screen ================= */

.landing-view {
  max-width: 1320px;
  margin: 0 auto;
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 8px 8px 30px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 245, 160, 0.2) transparent;
}

.landing-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.heading-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: rgba(0, 245, 160, 0.08);
  border: 1px solid var(--line-subtle);
  display: grid;
  place-items: center;
  box-shadow: 0 0 20px rgba(0, 245, 160, 0.15);
}

.section-heading h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  color: #ffffff;
}

.section-heading p {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-muted);
}

/* Luxury Dropzone */
.dropzone-card {
  padding: 20px;
  margin-bottom: 20px;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  border: 1.5px dashed rgba(0, 245, 160, 0.28);
  border-radius: var(--radius-md);
  background: radial-gradient(circle at center, rgba(0, 245, 160, 0.04) 0%, transparent 70%);
  cursor: pointer;
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
}

.drop-zone:hover, .drop-zone:focus-visible, .drop-zone.over {
  border-color: var(--accent);
  background: radial-gradient(circle at center, rgba(0, 245, 160, 0.09) 0%, transparent 70%);
  box-shadow: 0 0 35px rgba(0, 245, 160, 0.15) inset;
  outline: none;
}

.drop-cloud-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 245, 160, 0.16) 0%, rgba(0, 229, 153, 0.02) 70%);
  display: grid;
  place-items: center;
  margin-bottom: 16px;
  box-shadow: 0 0 25px rgba(0, 245, 160, 0.2);
  transition: transform 0.3s;
}

.drop-zone:hover .drop-cloud-icon {
  transform: translateY(-3px) scale(1.05);
}

.drop-primary-text {
  font-size: 17px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 4px;
}

.drop-secondary-text {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.format-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.fmt-label {
  font-size: 11.5px;
  color: var(--text-dim);
}

.fmt-tag {
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line-dim);
  border-radius: 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-muted);
}

/* Upload Options Row */
.upload-options {
  display: flex;
  align-items: flex-end;
  gap: 28px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line-dim);
  flex-wrap: wrap;
}

.opt-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.opt-group.grow {
  flex: 1;
  min-width: 260px;
}

.opt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.opt-badge {
  font-size: 10.5px;
  color: var(--accent);
  background: rgba(0, 245, 160, 0.1);
  padding: 2px 7px;
  border-radius: 4px;
}

.opt-val {
  font-size: 11px;
  color: var(--accent-mint);
  font-weight: 600;
}

/* Segmented Control */
.seg {
  display: inline-flex;
  background: rgba(5, 8, 12, 0.7);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 3px;
}

.seg button {
  border: 0;
  background: transparent;
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}

.seg button:hover {
  color: #ffffff;
}

.seg button.on {
  background: linear-gradient(135deg, rgba(0, 245, 160, 0.22) 0%, rgba(0, 255, 213, 0.1) 100%);
  color: #ffffff;
  border: 1px solid rgba(0, 245, 160, 0.35);
  box-shadow: 0 0 14px rgba(0, 245, 160, 0.2);
}

/* Range Slider */
.range-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-dim);
}

.range-wrap input[type=range] {
  flex: 1;
  height: 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  outline: none;
  -webkit-appearance: none;
}

.range-wrap input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid var(--accent);
  box-shadow: 0 0 10px var(--accent);
  cursor: pointer;
}

/* Samples Selector */
.samples-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.samples-label {
  font-size: 13px;
  color: var(--text-dim);
}

.sample-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(14, 22, 32, 0.7);
  border: 1px solid var(--line-subtle);
  border-radius: 9999px;
  color: var(--text-main);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
}

.sample-chip em {
  font-style: normal;
  color: var(--text-dim);
  font-size: 11.5px;
}

.sample-chip:hover {
  border-color: var(--accent);
  background: rgba(0, 245, 160, 0.08);
  box-shadow: 0 0 15px rgba(0, 245, 160, 0.15);
}

/* Capabilities Grid */
.capabilities-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.cap-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: rgba(12, 19, 29, 0.6);
  border: 1px solid var(--line-dim);
}

.cap-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: rgba(0, 245, 160, 0.08);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.cap-body b {
  display: block;
  font-size: 13px;
  color: #ffffff;
  margin-bottom: 2px;
}

.cap-body span {
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.4;
}

/* Showcase Card in Landing */
.showcase-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.showcase-glow {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 245, 160, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

.showcase-art {
  display: grid;
  place-items: center;
  margin-bottom: 16px;
}

.showcase-card h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 6px;
  color: #ffffff;
}

.showcase-card p {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0 0 18px;
  line-height: 1.5;
}

.feature-bullets {
  list-style: none;
  padding: 0;
  margin: 0 0 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature-bullets li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.feature-bullets .f-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}

.feature-bullets b {
  color: #ffffff;
}

.specs-block {
  padding-top: 16px;
  border-top: 1px solid var(--line-dim);
}

.spec-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 12px;
}

.spec-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.sm-item {
  background: rgba(5, 8, 12, 0.6);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-sm);
  padding: 8px 6px;
  text-align: center;
}

.sm-val {
  display: block;
  font-size: 13px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
}

.sm-lbl {
  font-size: 10px;
  color: var(--text-dim);
}

/* ================= Workspace Layout ================= */

.work-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 8px;
  overflow: hidden;
}

.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 10px;
  align-items: stretch;
}

/* Canvas Column */
.canvas-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 6px;
}

.canvas-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-shrink: 0;
}

/* Dedicated Artboard Switcher */
.artboard-switcher {
  display: inline-flex;
  align-items: center;
  background: rgba(8, 13, 20, 0.85);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-md);
  padding: 3px 4px;
  gap: 3px;
}

.ab-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  padding: 0 6px 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 5px 11px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}

.ab-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.04);
}

.ab-btn.on {
  background: linear-gradient(135deg, rgba(0, 245, 160, 0.22) 0%, rgba(0, 255, 213, 0.1) 100%);
  color: #ffffff;
  border: 1px solid rgba(0, 245, 160, 0.35);
  box-shadow: 0 0 12px rgba(0, 245, 160, 0.2);
}

.ab-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.3);
  display: inline-block;
  flex-shrink: 0;
}

.ab-dot.white {
  background: #ffffff;
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.9);
}

.ab-dot.grid {
  background: conic-gradient(#fff 90deg, #94a3b8 90deg 180deg, #fff 180deg 270deg, #94a3b8 270deg);
  border-color: rgba(255, 255, 255, 0.4);
}

.ab-dot.dark {
  background: #090e17;
  border-color: rgba(0, 245, 160, 0.6);
  box-shadow: 0 0 4px rgba(0, 245, 160, 0.4);
}

/* Floating Artboard Indicator */
.artboard-indicator {
  position: absolute;
  top: 14px;
  left: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  background: rgba(8, 13, 20, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid var(--line-subtle);
  border-radius: 6px;
  font-size: 11px;
  color: var(--text-dim);
  pointer-events: none;
  z-index: 14;
}

.ab-tag {
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 0.06em;
  font-size: 9.5px;
}

.ab-size {
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 600;
}

.tool-strip {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(8, 13, 20, 0.7);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-md);
  padding: 3px;
}

.tool-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 0;
  color: var(--text-dim);
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.04);
}

.tool-btn.active {
  background: rgba(0, 245, 160, 0.15);
  color: var(--accent);
  box-shadow: 0 0 10px rgba(0, 245, 160, 0.2);
}

/* Stage Frame & Surface */
.stage-frame {
  position: relative;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: #06090e;
  border: 1px solid var(--line-subtle);
  box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(0, 229, 153, 0.06);
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.stage {
  position: relative;
  flex: 1;
  height: 100%;
  min-height: 180px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  background-color: #070c12;
  /* Premium Dark Checkered Background */
  background-image:
    linear-gradient(45deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255, 255, 255, 0.02) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255, 255, 255, 0.02) 75%);
  background-size: 24px 24px;
  background-position: 0 0, 0 12px, 12px -12px, -12px 0px;
}

.stage.drag {
  cursor: grabbing;
}

.canvas {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  will-change: transform;
  background: #ffffff;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  transition: background-color 0.25s, box-shadow 0.25s;
}

/* ⚪ White Artboard (Default for crisp black vector lines) */
.canvas.ab-white {
  background: #ffffff !important;
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.3) !important;
}

/* 🏁 Transparent Checkerboard Grid */
.canvas.ab-grid, .canvas.nobg {
  background-color: #f8fafc !important;
  background-image:
    linear-gradient(45deg, #cbd5e1 25%, transparent 25%),
    linear-gradient(-45deg, #cbd5e1 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #cbd5e1 75%),
    linear-gradient(-45deg, transparent 75%, #cbd5e1 75%) !important;
  background-size: 20px 20px !important;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px !important;
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.8), 0 0 0 1.5px rgba(0, 245, 160, 0.45) !important;
}

/* ⬛ Dark / Black Artboard (with glowing white / neon vector lines) */
.canvas.ab-dark, .canvas.dark {
  background: #090e17 !important;
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.9), 0 0 0 1.5px rgba(0, 245, 160, 0.4), 0 0 35px rgba(0, 245, 160, 0.18) !important;
}

.canvas.ab-dark #vec svg {
  filter: drop-shadow(0 0 1.5px rgba(0, 255, 213, 0.4));
}

.summary {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 12px;
  padding: 6px 14px;
  background: rgba(12, 19, 29, 0.85);
  backdrop-filter: blur(16px);
  border: 1px solid var(--line-subtle);
  border-radius: var(--radius-md);
  margin-top: 4px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.summary div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: center;
}

.summary span.k {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.summary b {
  font-size: 15px;
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 700;
}

.canvas img, .canvas #vec {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
  user-select: none;
}

#vec svg {
  width: 100%;
  height: 100%;
  display: block;
}

.focus {
  position: absolute;
  border: 2px solid var(--accent);
  border-radius: 6px;
  box-shadow: 0 0 18px rgba(0, 245, 160, 0.5), inset 0 0 12px rgba(0, 245, 160, 0.15);
  pointer-events: none;
  transition: left 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              top 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.25s ease;
  z-index: 12;
}

/* ================= Processing Animations: Scanning Beam & Nodes ================= */

.scan-beam {
  position: absolute;
  top: 0;
  left: -40%;
  width: 25%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.05) 50%, rgba(0, 255, 179, 0.25) 85%, #00ffd5 100%);
  filter: drop-shadow(0 0 16px #00ffd5);
  transform: skewX(-16deg);
  pointer-events: none;
  opacity: 0;
  z-index: 10;
  transition: opacity 0.4s;
}

.stage.processing .scan-beam {
  opacity: 1;
  animation: scanSweep 3.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

@keyframes scanSweep {
  0% { left: -35%; }
  50% { left: 110%; }
  100% { left: -35%; }
}

.node-grid-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: radial-gradient(circle, rgba(0, 229, 255, 0.22) 1.5px, transparent 1.5px);
  background-size: 32px 32px;
  opacity: 0;
  transition: opacity 0.4s;
  z-index: 9;
}

.stage.processing .node-grid-overlay {
  opacity: 0.65;
  animation: nodeGlow 2.5s ease-in-out infinite alternate;
}

@keyframes nodeGlow {
  0% { opacity: 0.25; }
  100% { opacity: 0.75; filter: drop-shadow(0 0 4px #00ffd5); }
}

/* Canvas Legend */
.legend {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: flex;
  gap: 14px;
  background: rgba(8, 13, 20, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid var(--line-subtle);
  border-radius: var(--radius-md);
  padding: 6px 12px;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-muted);
  z-index: 12;
}

.legend i {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 6px;
}

/* Canvas Bottom Floating Footer Bar */
.canvas-footer-bar {
  padding: 6px 14px;
  background: rgba(8, 13, 20, 0.88);
  backdrop-filter: blur(16px);
  border-top: 1px solid var(--line-dim);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  position: relative;
  z-index: 15;
  flex-shrink: 0;
}

.footer-status-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-muted);
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}

.mini-prog-track {
  width: 70px;
  height: 3px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.mini-prog-fill {
  height: 100%;
  width: 0%;
  background: var(--accent-gradient);
  transition: width 0.3s;
}

.footer-counters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.counter-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line-dim);
  font-size: 11.5px;
  color: var(--text-dim);
}

.counter-badge b {
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 600;
}

.zoom-cluster {
  display: flex;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.zoom-btn {
  border: 0;
  background: transparent;
  padding: 5px 10px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.zoom-btn:hover {
  background: rgba(0, 245, 160, 0.1);
  color: #ffffff;
}

.zoom-fit {
  border-left: 1px solid var(--line-dim);
  border-right: 1px solid var(--line-dim);
  font-size: 11.5px;
}

/* ================= Right Sidebar: Status, Stages & Metrics ================= */

.sidebar-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 245, 160, 0.25) transparent;
}

.sidebar-column::-webkit-scrollbar {
  width: 4px;
}

.sidebar-column::-webkit-scrollbar-thumb {
  background: rgba(0, 245, 160, 0.25);
  border-radius: 9999px;
}

/* AI Engine Processing Card */
.status-panel {
  padding: 12px 14px;
}

.status-card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

/* AI Hologram Radar Ring Animation */
.radar-wrap {
  position: relative;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.radar-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1.5px dashed rgba(0, 245, 160, 0.45);
  animation: radarSpin 12s linear infinite;
}

.radar-core {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 245, 160, 0.22), rgba(12, 19, 29, 0.95));
  border: 1px solid rgba(0, 245, 160, 0.65);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.35);
  display: grid;
  place-items: center;
}

.radar-pulse {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1px solid rgba(0, 245, 160, 0.4);
  animation: radarWave 2.2s ease-out infinite;
}

@keyframes radarSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes radarWave {
  0% { transform: scale(0.85); opacity: 0.8; }
  100% { transform: scale(1.4); opacity: 0; }
}

.status-title {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 2px;
}

.status-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.35;
}

/* Percentage Bar in Processing Card */
.progress-section {
  margin-bottom: 10px;
}

.prog-track {
  height: 6px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.05);
  overflow: hidden;
  margin-bottom: 6px;
}

.prog-fill {
  height: 100%;
  background: var(--accent-gradient);
  border-radius: 9999px;
  box-shadow: 0 0 12px rgba(0, 245, 160, 0.5);
  transition: width 0.4s ease;
}

.prog-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
}

.prog-label {
  color: var(--text-dim);
}

.prog-percent {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--accent-mint);
  font-size: 12.5px;
}

/* Stages Checklist */
.stages-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-dim);
}

.stage-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.2s;
}

.stage-state-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-dim);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.stage-state-icon svg {
  width: 11px;
  height: 11px;
}

.stage-row.done .stage-state-icon {
  background: rgba(34, 197, 94, 0.16);
  color: #22c55e;
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.3);
}

.stage-row.active .stage-state-icon {
  background: rgba(0, 245, 160, 0.16);
  color: var(--accent);
  box-shadow: 0 0 12px rgba(0, 245, 160, 0.4);
  animation: spinnerRotate 1.5s linear infinite;
}

@keyframes spinnerRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stage-info {
  flex: 1;
  min-width: 0;
}

.stage-name {
  font-size: 11.5px;
  font-weight: 600;
  color: #ffffff;
}

.stage-desc {
  font-size: 10px;
  color: var(--text-dim);
}

.stage-time {
  font-size: 10.5px;
  font-family: var(--font-mono);
  color: var(--text-dim);
  font-weight: 500;
}

/* 2x2 Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.metric-tile {
  background: rgba(5, 8, 12, 0.65);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: border-color 0.2s;
}

.metric-tile:hover {
  border-color: var(--line-subtle);
}

.tile-icon {
  width: 24px;
  height: 24px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.03);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.tile-icon svg {
  width: 13px;
  height: 13px;
}

.tile-label {
  display: block;
  font-size: 9.5px;
  color: var(--text-dim);
  line-height: 1.15;
  margin-bottom: 1px;
}

.tile-val {
  display: block;
  font-size: 13.5px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
  letter-spacing: -0.02em;
}

/* Style & Export Panels */
.panel {
  padding: 10px 12px;
}

.panel-header {
  margin-bottom: 8px;
}

.panel-header h3 {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.badge-live {
  font-size: 9.5px;
  color: var(--accent);
  background: rgba(0, 245, 160, 0.12);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.param-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.param-row span b {
  color: var(--accent-mint);
  font-family: var(--font-mono);
  margin-left: 6px;
}

input[type=color] {
  width: 100%;
  height: 30px;
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-sm);
  background: rgba(5, 8, 12, 0.7);
  padding: 2px;
  cursor: pointer;
}

select {
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-sm);
  background: rgba(5, 8, 12, 0.7);
  padding: 6px 8px;
  color: #ffffff;
  cursor: pointer;
}

/* Export Buttons */
.export-btns-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 12.5px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
}

.primary-action-btn {
  background: linear-gradient(135deg, #00ffd5 0%, #00f5a0 60%, #00d287 100%);
  color: #05080c;
  box-shadow: 0 0 20px rgba(0, 245, 160, 0.25);
}

.primary-action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 28px rgba(0, 245, 160, 0.45);
}

.secondary-action-btn {
  background: rgba(255, 255, 255, 0.03);
  border-color: var(--line-dim);
  color: #ffffff;
}

.secondary-action-btn:hover {
  background: rgba(0, 245, 160, 0.08);
  border-color: var(--line-subtle);
  color: var(--accent);
}

.btn.disabled {
  opacity: 0.35;
  pointer-events: none;
}

/* Activity Log Drawer */
.log-drawer {
  padding: 12px 16px;
}

.log-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  cursor: pointer;
  list-style: none;
}

.log-summary::-webkit-details-marker {
  display: none;
}

.count-pill {
  margin-left: auto;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--accent);
}

.log-entries {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  max-height: 180px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 11px;
}

.log-entries li {
  padding: 4px 6px;
  border-radius: 4px;
  display: flex;
  gap: 8px;
  color: var(--text-muted);
}

.log-entries li:nth-child(odd) {
  background: rgba(255, 255, 255, 0.02);
}

.log-entries s {
  text-decoration: none;
  font-weight: 600;
  width: 44px;
}

.log-entries s.edit { color: var(--accent); }
.log-entries s.output { color: #f59e0b; }
.log-entries s.doctor { color: #22c55e; }
.log-entries s.trace, .log-entries s.split { color: var(--text-dim); }

/* ================= Bottom Section: Icon Match Results & Comparison ================= */

.bottom-analysis-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 10px;
  align-items: stretch;
  height: 128px;
  min-height: 128px;
  max-height: 128px;
  flex-shrink: 0;
}

/* Icon Match Results Card */
.icon-results-card {
  padding: 8px 12px 6px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  height: 100%;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  flex-shrink: 0;
}

.target-glyph {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: rgba(0, 245, 160, 0.08);
  border: 1px solid var(--line-subtle);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: 0 0 10px rgba(0, 245, 160, 0.15);
}

.target-glyph svg {
  width: 14px;
  height: 14px;
}

.results-title-group h3 {
  margin: 0;
  font-size: 12.5px;
  font-weight: 700;
  color: #ffffff;
  line-height: 1.2;
}

.results-sub {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.2;
}

/* Scrollable Icon Cards Carousel */
.icon-cards-carousel {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 2px 6px;
  flex: 1;
  min-height: 0;
  align-items: center;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 245, 160, 0.25) transparent;
}

.icon-cards-carousel::-webkit-scrollbar {
  height: 4px;
}

.icon-cards-carousel::-webkit-scrollbar-thumb {
  background: rgba(0, 245, 160, 0.25);
  border-radius: 9999px;
}

/* Individual Icon Card (Compact, High-Precision Widget) */
.ic {
  position: relative;
  flex: 0 0 100px;
  width: 100px;
  height: 72px;
  background: rgba(8, 14, 22, 0.75);
  border: 1px solid var(--line-subtle);
  border-radius: var(--radius-sm);
  padding: 4px 6px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
}

.ic:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 245, 160, 0.45);
  background: rgba(12, 20, 32, 0.9);
  box-shadow: 0 6px 16px -3px rgba(0, 245, 160, 0.2);
}

.ic.sel {
  border-color: var(--accent);
  background: linear-gradient(135deg, rgba(0, 245, 160, 0.16) 0%, rgba(8, 14, 22, 0.95) 100%);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.35);
}

.ic-thumb-wrap {
  width: 38px;
  height: 38px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line-dim);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.ic img {
  width: 30px;
  height: 30px;
  object-fit: contain;
  filter: drop-shadow(0 0 2px rgba(255, 255, 255, 0.8));
}

/* Circular SVG Match Gauge on Card */
.gauge-cluster {
  position: relative;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.gauge-svg {
  width: 36px;
  height: 36px;
  transform: rotate(-90deg);
}

.gauge-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.08);
  stroke-width: 3;
}

.gauge-bar {
  fill: none;
  stroke: #00f5a0;
  stroke-width: 3.2;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.6s ease;
  filter: drop-shadow(0 0 3px #00f5a0);
}

.gauge-text {
  position: absolute;
  font-family: var(--font-mono);
  font-size: 8px;
  font-weight: 700;
  color: #ffffff;
}

.gauge-label {
  display: none;
}

/* Running & Shimmer State on Icon Cards */
.ic.run::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 20%, rgba(0, 245, 160, 0.25) 50%, transparent 80%);
  background-size: 200% 100%;
  animation: cardShimmer 1.5s linear infinite;
  pointer-events: none;
}

@keyframes cardShimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* ================= Side-by-Side Comparison Card ================= */

.comparison-card {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.comp-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  min-width: 0;
}

.comp-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 4px;
}

.comp-preview-frame {
  width: 100%;
  height: 74px;
  border-radius: var(--radius-sm);
  background: rgba(5, 8, 12, 0.75);
  border: 1px solid var(--line-dim);
  display: grid;
  place-items: center;
  overflow: hidden;
  position: relative;
}

.comp-preview-frame img {
  max-width: 85%;
  max-height: 85%;
  object-fit: contain;
}

.active-vector-box .comp-preview-frame {
  border-color: rgba(0, 245, 160, 0.35);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.15) inset;
}

.comp-arrow {
  color: var(--accent);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  margin-top: 10px;
}

.comp-arrow svg {
  width: 16px;
  height: 16px;
}

.match-badge {
  position: absolute;
  top: -2px;
  right: 0;
  background: rgba(0, 245, 160, 0.16);
  border: 1px solid rgba(0, 245, 160, 0.4);
  color: var(--accent);
  font-size: 9.5px;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 9999px;
  box-shadow: 0 0 10px rgba(0, 245, 160, 0.2);
}

/* Toast Message */
.toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translate(-50%, 20px);
  background: rgba(14, 22, 34, 0.95);
  backdrop-filter: blur(16px);
  border: 1px solid var(--line-glow);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.7), 0 0 20px rgba(0, 245, 160, 0.25);
  color: #ffffff;
  padding: 11px 22px;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  font-weight: 500;
  opacity: 0;
  pointer-events: none;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
}

.toast.show {
  opacity: 1;
  transform: translate(-50%, 0);
}

.toast.err {
  background: rgba(35, 12, 16, 0.96);
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.7), 0 0 20px rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

/* ================= Responsive Queries ================= */

@media (max-width: 1200px) {
  .landing-grid {
    grid-template-columns: 1fr;
  }
  .workspace-grid {
    grid-template-columns: 1fr;
  }
  .bottom-analysis-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .sidebar {
    width: 68px;
    padding: 20px 10px;
  }
  .brand-text, .nav-item span, .sidebar-promo {
    display: none;
  }
  .nav-item {
    justify-content: center;
    padding: 10px;
  }
  .app-header {
    padding: 0 16px;
  }
  .content-scroll {
    padding: 16px;
  }
  .capabilities-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* AI Lessons / Defect Census Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(3, 6, 10, 0.78);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.modal-card {
  background: var(--bg-card);
  border: 1px solid var(--line-mid);
  border-radius: 16px;
  width: 100%;
  max-width: 680px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(0, 245, 160, 0.08);
  overflow: hidden;
  animation: modalPop 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modalPop {
  from { opacity: 0; transform: scale(0.96) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--line-dim);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  font-size: 13px;
  color: var(--text-muted);
}
.lessons-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: 12px;
  margin-top: 12px;
}
.lessons-table th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--line-dim);
  font-weight: 600;
}
.lessons-table td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  color: #fff;
}
.lessons-table tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}
.lessons-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.badge-ok { background: rgba(0, 245, 160, 0.15); color: var(--accent); }
.badge-warn { background: rgba(255, 179, 0, 0.15); color: #ffb300; }
.badge-skip { background: rgba(255, 77, 77, 0.15); color: #ff4d4d; }

/* ==========================================================================
   Template Studio Styles (Presentation Artboard)
   ========================================================================== */

.template-action-btn {
  background: linear-gradient(135deg, #00f5a0 0%, #00d2ff 100%) !important;
  color: #051410 !important;
  font-weight: 700 !important;
  border: none !important;
  box-shadow: 0 4px 18px rgba(0, 245, 160, 0.3) !important;
  transition: all var(--transition-fast) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  cursor: pointer;
}

.template-action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 24px rgba(0, 245, 160, 0.45) !important;
}

.eps-btn {
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  border: none !important;
  box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.eps-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 22px rgba(139, 92, 246, 0.45) !important;
}

.template-studio-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 12px;
  overflow: hidden;
}

.template-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 16px;
  background: rgba(13, 19, 29, 0.85);
  border: 1px solid var(--line-dim);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(16px);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.template-title-group h2 {
  font-size: 17px;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  line-height: 1.2;
}

.template-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 370px minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
}

.template-controls-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 4px;
  min-height: 0;
}

.tpl-panel {
  background: rgba(13, 19, 29, 0.65) !important;
  border: 1px solid var(--line-dim) !important;
  border-radius: var(--radius-lg) !important;
}

.preset-cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.preset-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line-dim);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  user-select: none;
}

.preset-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.2);
}

.preset-card.active {
  background: rgba(0, 245, 160, 0.08);
  border-color: var(--accent);
  box-shadow: 0 0 16px rgba(0, 245, 160, 0.2);
}

.preset-card-name {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 7px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preset-swatches {
  display: flex;
  align-items: center;
  gap: 5px;
}

.swatch-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
}

.text-input-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.text-input-row input[type="text"] {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--line-dim);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #ffffff;
  width: 100%;
  font-family: inherit;
  transition: all var(--transition-fast);
}

.text-input-row input[type="text"]:focus {
  border-color: var(--accent);
  outline: none;
  box-shadow: 0 0 10px rgba(0, 245, 160, 0.25);
}

.template-preview-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.template-stage-frame {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.template-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  padding: 24px;
  position: relative;
  background: radial-gradient(circle at center, rgba(16, 24, 38, 0.7) 0%, rgba(6, 9, 14, 0.98) 100%);
}

.template-artboard-container {
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  overflow: hidden;
  max-width: 96%;
  max-height: 94%;
  transition: transform 0.15s ease-out;
  transform-origin: center center;
}

.template-artboard-container svg {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  border-radius: 16px;
}

/* Cancel Redraw Button */
.proc-cancel-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
.btn-cancel-job {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #ff6b6b;
  font-size: 11.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-cancel-job:hover {
  background: rgba(239, 68, 68, 0.22);
  border-color: rgba(239, 68, 68, 0.6);
  color: #fff;
  transform: translateY(-1px);
}



================================================================================
# FILE: server/static/app.js
================================================================================

(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const S = {
    job: null,
    since: 0,
    version: -1,
    view: 'vector',
    sel: null,
    W: 0,
    H: 0,
    tf: { x: 0, y: 0, k: 1 },
    timer: null,
    quality: 'standard',
    icons: [],
    done: false,
    logN: 0,
    editCount: 0,
    startTime: 0,
    stageTimes: { split: 0, trace: 0, edit: 0, output: 0 }
  };

  // ---------------------------------------------------------------- helpers
  const toast = (msg, err) => {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast show' + (err ? ' err' : '');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => t.className = 'toast', 3400);
  };

  const api = (p, o) => fetch(p, o).then(async r => {
    if (!r.ok) {
      let m = r.statusText;
      try { m = (await r.json()).detail || m; } catch {}
      throw new Error(m);
    }
    return r;
  });

  const fmt = n => (n != null ? (n * 100).toFixed(1) + '%' : '--');

  // Health check
  fetch('/api/health')
    .then(r => r.json())
    .then(h => {
      const p = $('#health');
      if (!p) return;
      p.className = 'status-pill ok';
      const txt = $('.status-text', p) || p.lastElementChild;
      if (txt) txt.textContent = `AI Engine Online · ${h.renderer}`;
    })
    .catch(() => {
      const p = $('#health');
      if (!p) return;
      p.className = 'status-pill bad';
      const txt = $('.status-text', p) || p.lastElementChild;
      if (txt) txt.textContent = 'Engine Offline';
    });

  // ---------------------------------------------------------------- options
  const qEl = $('#quality');
  if (qEl) {
    qEl.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      S.quality = b.dataset.v;
      $$('#quality button').forEach(x => x.classList.toggle('on', x === b));
    });
  }

  const hint = () => {
    const cleanEl = $('#clean');
    if (!cleanEl) return;
    const v = +cleanEl.value;
    const h = $('#cleanHint');
    if (h) h.textContent = v < 0.2 ? 'Exact match' : v > 0.8 ? 'Cleanest paths' : 'Balanced';
  };
  const cleanInput = $('#clean');
  if (cleanInput) cleanInput.addEventListener('input', hint);

  // ---------------------------------------------------------------- upload & samples
  const drop = $('#drop'), file = $('#file');
  if (drop && file) {
    drop.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        file.click();
      }
    });
    file.addEventListener('change', () => file.files[0] && upload(file.files[0]));
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault();
      drop.classList.add('over');
    }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault();
      drop.classList.remove('over');
    }));
    drop.addEventListener('drop', e => {
      const f = e.dataTransfer.files[0];
      if (f) upload(f);
    });
  }

  window.addEventListener('paste', e => {
    const it = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/'));
    if (it && !S.job) upload(it.getAsFile());
  });

  $$('[data-sample]').forEach(b => b.addEventListener('click', async () => {
    try {
      const isFresh = $('#freshRun') && $('#freshRun').checked ? '&fresh=true' : '';
      const r = await api(`/api/samples/${b.dataset.sample}?quality=${S.quality}${isFresh}`, { method: 'POST' });
      begin((await r.json()).id, b.dataset.sample);
    } catch (e) {
      toast(e.message, 1);
    }
  }));

  async function upload(f) {
    const fd = new FormData();
    fd.append('file', f);
    fd.append('quality', S.quality);
    const cVal = $('#clean') ? $('#clean').value : '0.5';
    fd.append('clean', cVal);
    const isFresh = $('#freshRun') ? $('#freshRun').checked : true;
    fd.append('fresh', isFresh ? 'true' : 'false');
    try {
      const r = await api('/api/jobs', { method: 'POST', body: fd });
      begin((await r.json()).id, f.name || 'Pasted Line Art');
    } catch (e) {
      toast(e.message, 1);
    }
    if (file) file.value = '';
  }

  // ---------------------------------------------------------------- workspace lifecycle
  function begin(id, name) {
    Object.assign(S, {
      job: id,
      since: 0,
      version: -1,
      done: false,
      sel: null,
      icons: [],
      logN: 0,
      editCount: 0,
      startTime: Date.now(),
      stageTimes: { split: 0, trace: 0, edit: 0, output: 0 }
    });

    $('#landing').hidden = true;
    $('#work').hidden = false;
    $('#jobName').textContent = name;
    const meta = $('#jobMeta');
    if (meta) meta.textContent = 'Analyzing image...';

    const log = $('#log'); if (log) log.innerHTML = '';
    const icons = $('#icons'); if (icons) icons.innerHTML = '';
    const summary = $('#summary'); if (summary) summary.hidden = true;

    // Reset progress and indicators
    $('#prog').classList.remove('done');
    $('#prog i').style.width = '3%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = '3%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = '3%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = '3%';

    // Start live processing animation on canvas
    const stg = $('#stage');
    if (stg) stg.classList.add('processing');

    const pTitle = $('#procTitle'); if (pTitle) pTitle.textContent = 'Processing...';
    const pSub = $('#procSub'); if (pSub) pSub.textContent = 'AI is analyzing and redrawing your image into clean vector paths.';
    const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Analyzing raster image...';

    // Reset stages
    resetStages();

    // Reset metrics
    updateMetricsUI(0, '--', '--', 0);

    $$('.eng').forEach(e => {
      e.className = 'eng';
      const em = $('em', e); if (em) em.textContent = '';
    });
    ['dlSvg', 'dlZip', 'copy', 'dlEps', 'btnSendToTemplate'].forEach(i => {
      const el = $('#' + i);
      if (el) el.classList.add('disabled');
    });

    $('#vec').innerHTML = '';
    $('#imgDiff').removeAttribute('src');

    const o = $('#imgOrig');
    o.onload = () => {
      S.W = o.naturalWidth;
      S.H = o.naturalHeight;
      sizeCanvas();
      fit();
      const dims = $('#artboardDims');
      if (dims && S.W && S.H) dims.textContent = `${S.W} × ${S.H} px`;
      if (meta && S.icons.length) {
        meta.textContent = `${S.icons.length} icons · ${S.W} × ${S.H}`;
      } else if (meta) {
        meta.textContent = `${S.W} × ${S.H} px`;
      }
    };
    o.src = `/api/jobs/${id}/original.png`;

    setArtboardBg('#ffffff');
    setView('vector');
    clearTimeout(S.timer);
    poll();
  }

  function cancelCurrentJob() {
    clearTimeout(S.timer);
    if (S.job) {
      api('/api/jobs/' + S.job + '/cancel', { method: 'POST' }).catch(() => {});
      S.job = null;
    }
    $('#work').hidden = true;
    const tplSt = $('#templateStudio'); if (tplSt) tplSt.hidden = true;
    $('#landing').hidden = false;
    const stg = $('#stage');
    if (stg) stg.classList.remove('processing');
  }

  $('#newJob').addEventListener('click', cancelCurrentJob);

  const navHome = $('#navHome');
  if (navHome) {
    navHome.addEventListener('click', e => {
      e.preventDefault();
      cancelCurrentJob();
    });
  }

  async function poll() {
    if (!S.job) return;
    const id = S.job;
    try {
      const j = await (await api(`/api/jobs/${id}?since=${S.since}`)).json();
      if (id !== S.job) return;
      S.since = j.next;
      ingest(j);
      if (j.status === 'cancelled') {
        toast('Job was cancelled', 0);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Cancelled';
        return;
      }
      if (j.status === 'error') {
        toast(j.error || 'Job failed', 1);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Processing error';
        return;
      }
      if (j.status === 'done') {
        finish(j);
        return;
      }
    } catch (e) {
      /* transient network poll */
    }
    S.timer = setTimeout(poll, 650);
  }

  // ---------------------------------------------------------------- state -> UI
  const ENGINE = { trace: 'edit', split: 'edit', edit: 'edit', output: 'output', doctor: 'doctor' };

  function resetStages() {
    ['stageImageAnalysis', 'stagePathTracing', 'stageCurveOpt', 'stageOutputGen'].forEach(id => {
      const row = $('#' + id);
      if (row) row.className = 'stage-row';
    });
    setStageTime('timeAnalysis', '0.0s');
    setStageTime('timeTracing', '--');
    setStageTime('timeCurve', '--');
    setStageTime('timeOutput', '--');
  }

  function setStageTime(id, val) {
    const el = $('#' + id);
    if (el) el.textContent = val;
  }

  function ingest(j) {
    S.icons = j.icons || [];
    const total = S.icons.length, done = S.icons.filter(i => i.status === 'done').length;
    const pct = total ? Math.min(100, Math.max(4, Math.round((done / total) * 100))) : 4;

    // Progress updates
    const progI = $('#prog i'); if (progI) progI.style.width = pct + '%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = pct + '%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = pct + '%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = pct + '%';

    const iconCount = $('#iconCount');
    if (iconCount) iconCount.textContent = total ? `${done}/${total} icons` : '';

    if (j.width && !S.W) {
      S.W = j.width;
      S.H = j.height;
    }
    const meta = $('#jobMeta');
    if (meta && total && S.W) {
      meta.textContent = `${total} icons · ${S.W} × ${S.H}`;
    }

    // Engine events & real stage mapping
    const log = $('#log');
    let last = null;
    for (const e of j.events || []) {
      last = e;
      const eng = ENGINE[e.engine] || 'edit';
      if (eng === 'edit' && e.engine === 'edit') S.editCount++;

      // Real stage tracking
      const nowS = (Date.now() - S.startTime) / 1000;
      if (e.engine === 'split') {
        setStageActive('stageImageAnalysis');
        setStageTime('timeAnalysis', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'trace') {
        setStageDone('stageImageAnalysis');
        setStageActive('stagePathTracing');
        setStageTime('timeTracing', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'edit') {
        setStageDone('stageImageAnalysis');
        setStageDone('stagePathTracing');
        setStageActive('stageCurveOpt');
        setStageTime('timeCurve', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'output' || e.engine === 'doctor') {
        setStageDone('stageCurveOpt');
        setStageActive('stageOutputGen');
        setStageTime('timeOutput', (e.t || nowS).toFixed(1) + 's');
      }

      if (log && S.logN++ < 400) {
        const li = document.createElement('li');
        li.innerHTML = `<s>${e.engine}</s><span>${e.msg}</span>`;
        log.appendChild(li);
      }
    }

    if (log) log.scrollTop = log.scrollHeight;

    // Status message
    const cMsg = $('#canvasStatusMsg');
    if (cMsg && last) {
      if (last.engine === 'trace') cMsg.textContent = 'Tracing centerline paths...';
      else if (last.engine === 'edit') cMsg.textContent = 'Optimizing Bezier curves & smoothing...';
      else if (last.engine === 'output') cMsg.textContent = 'Rendering vector output...';
      else if (last.engine === 'doctor') cMsg.textContent = 'Verifying match with raster image...';
    }

    // Live intermediate metrics
    const ms = S.icons.map(i => i.metrics).filter(Boolean);
    const paths = ms.reduce((a, m) => a + (m.paths || 0), 0);
    const nodes = ms.reduce((a, m) => a + (m.nodes || 0), 0);
    const elapsed = (Date.now() - S.startTime) / 1000;
    updateMetricsUI(elapsed, paths || '--', nodes || '--', (j.audit && j.audit.coincident) || 0);

    renderIcons(j);

    if (j.version !== S.version && j.version > 0) {
      S.version = j.version;
      loadSvg();
    }
  }

  function setStageActive(id) {
    const el = $('#' + id);
    if (el && !el.classList.contains('done')) {
      el.className = 'stage-row active';
    }
  }

  function setStageDone(id) {
    const el = $('#' + id);
    if (el) el.className = 'stage-row done';
  }

  function updateMetricsUI(sec, paths, nodes, dupes) {
    const mTime = $('#metricTime'); if (mTime) mTime.textContent = (sec > 0 ? sec.toFixed(1) + 's' : '0.0s');
    const mPaths = $('#metricPaths'); if (mPaths) mPaths.textContent = paths;
    const mNodes = $('#metricNodes'); if (mNodes) mNodes.textContent = nodes;
    const mDupes = $('#metricDupes'); if (mDupes) mDupes.textContent = dupes;

    const cPaths = $('#countPathsVal'); if (cPaths) cPaths.textContent = paths;
    const cNodes = $('#countNodesVal'); if (cNodes) cNodes.textContent = nodes;
  }

  // ---------------------------------------------------------------- Icon-by-Icon Match Cards
  function renderIcons(j) {
    const box = $('#icons');
    if (!box) return;

    const total = j.icons.length;
    const subText = $('#matchSubText');
    if (subText && total) {
      const avg = j.iou != null ? fmt(j.iou) : '--';
      subText.textContent = `${total} icons · Average Match ${avg}`;
    }

    j.icons.forEach(ic => {
      let el = box.children[ic.k];
      const done = ic.status === 'done';
      const pctVal = done ? ic.iou : (ic.live_iou || 0);
      const pctStr = pctVal ? fmt(pctVal) : '…';
      
      // Circumference for r=18: 2 * PI * 18 = 113.097
      const circ = 113.1;
      const offset = pctVal ? (circ * (1 - Math.min(1, Math.max(0, pctVal)))).toFixed(1) : circ;

      if (!el) {
        el = document.createElement('div');
        el.className = 'ic';
        el.dataset.k = ic.k;
        el.innerHTML = `
          <div class="ic-thumb-wrap">
            <img alt="icon-${ic.k + 1}">
          </div>
          <div class="gauge-cluster">
            <svg class="gauge-svg" viewBox="0 0 44 44">
              <circle class="gauge-bg" cx="22" cy="22" r="18" />
              <circle class="gauge-bar" cx="22" cy="22" r="18" stroke-dasharray="${circ}" stroke-dashoffset="${offset}" />
            </svg>
            <span class="gauge-text">${pctStr}</span>
          </div>
          <span class="gauge-label">Match</span>
        `;
        el.addEventListener('click', () => selectIcon(ic.k));
        box.appendChild(el);
      } else {
        const bar = $('.gauge-bar', el);
        if (bar) bar.style.strokeDashoffset = offset;
        const txt = $('.gauge-text', el);
        if (txt) txt.textContent = pctStr;
      }

      el.classList.toggle('run', !done && ic.status !== 'error');
      el.classList.toggle('err', ic.status === 'error');
      if (S.sel === ic.k) el.classList.add('sel');
      const fin = ic.metrics && ic.metrics.finisher;
      const isMem = ic.metrics && ic.metrics.from_memory;
      if (isMem) {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · (⚡ Re-used from memory cache)`;
      } else if (fin && fin.found > 0) {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · Fresh run · Finisher polished ${fin.fixed}/${fin.found} sites`;
      } else {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · Fresh run`;
      }

      const img = $('img', el);
      if (done && img && !img.dataset.ok) {
        img.dataset.ok = 1;
        let n = 0;
        const load = () => { img.src = `/api/jobs/${S.job}/icons/${ic.k}.svg?r=${n}`; };
        img.onerror = () => { if (n++ < 5) setTimeout(load, 500 * n); };
        load();
      }
    });

    // Dynamic focus tracking during live processing:
    // Follow the icon that is CURRENTLY being worked on.
    if (!S.done && j.icons.length > 0) {
      const activeIcon = j.icons.find(i => i.status === 'running') ||
                         j.icons.find(i => i.status !== 'done') ||
                         j.icons[0];
      if (activeIcon && activeIcon.box) {
        trackActiveIcon(activeIcon.k);
      }
    } else if (S.done && S.sel !== null && j.icons[S.sel]) {
      updateComparison(S.sel);
    }
  }

  // ---------------------------------------------------------------- Dynamic Active Icon Tracking
  function trackActiveIcon(k) {
    const ic = S.icons[k];
    if (!ic || !ic.box) return;

    // Highlight card in bottom carousel
    $$('.ic').forEach(x => x.classList.toggle('sel', +x.dataset.k === k));

    // Smoothly glide the green focus box over the actively processed icon
    const f = $('#focus');
    if (f) {
      f.hidden = false;
      const b = ic.box;
      Object.assign(f.style, {
        left: b[0] + 'px',
        top: b[1] + 'px',
        width: (b[2] - b[0]) + 'px',
        height: (b[3] - b[1]) + 'px'
      });
    }

    updateComparison(k);
  }

  // ---------------------------------------------------------------- Manual Selection & Comparison View
  function selectIcon(k) {
    const ic = S.icons[k];
    if (!ic) return;

    // If user clicks the already selected card, toggle it off and show full clean artboard!
    if (S.sel === k) {
      clearFocus();
      fit();
      return;
    }

    S.sel = k;
    $$('.ic').forEach(x => x.classList.toggle('sel', +x.dataset.k === k));

    const f = $('#focus');
    const b = ic.box;
    if (f && b) {
      f.hidden = false;
      Object.assign(f.style, {
        left: b[0] + 'px',
        top: b[1] + 'px',
        width: (b[2] - b[0]) + 'px',
        height: (b[3] - b[1]) + 'px'
      });
    }

    updateComparison(k);
  }

  function updateComparison(k) {
    const ic = S.icons[k];
    if (!ic) return;

    // Vector SVG preview
    const vecImg = $('#compVecImg');
    if (vecImg) {
      vecImg.src = `/api/jobs/${S.job}/icons/${k}.svg?v=${S.version}`;
    }

    // Match badge
    const badge = $('#compMatchBadge');
    if (badge) {
      const p = ic.iou != null ? ic.iou : ic.live_iou;
      const fin = ic.metrics && ic.metrics.finisher;
      let txt = p != null ? `${fmt(p)} Match` : 'Processing...';
      if (fin && fin.found > 0) {
        txt += ` · ✨ Finisher: ${fin.fixed}/${fin.found} sites`;
      }
      badge.textContent = txt;
    }

    // Crop original icon image client-side onto in-memory canvas
    const origImg = $('#imgOrig');
    const compOrig = $('#compOrigImg');
    if (origImg && compOrig && ic.box && origImg.naturalWidth) {
      try {
        const [x0, y0, x1, y1] = ic.box;
        const bw = Math.max(1, x1 - x0);
        const bh = Math.max(1, y1 - y0);
        const c = document.createElement('canvas');
        c.width = bw;
        c.height = bh;
        const ctx = c.getContext('2d');
        ctx.drawImage(origImg, x0, y0, bw, bh, 0, 0, bw, bh);
        compOrig.src = c.toDataURL();
      } catch (e) {
        compOrig.src = `/api/jobs/${S.job}/original.png`;
      }
    }
  }

  function clearFocus() {
    S.sel = null;
    const f = $('#focus');
    if (f) f.hidden = true;
    $$('.ic').forEach(x => x.classList.remove('sel'));
  }

  // ---------------------------------------------------------------- Finish Completion
  function finish(j) {
    S.done = true;

    // Stop scanning beam
    const stg = $('#stage');
    if (stg) stg.classList.remove('processing');

    // 1. Immediately remove the focus box so the entire artboard is clean!
    clearFocus();

    // 2. Fit the entire artboard so all icons are crisp and in view!
    fit();

    // 3. Ensure the artboard is pure white with black vector lines!
    setArtboardBg('#ffffff');

    // 4. Update the bottom comparison preview card with the first icon, without putting any box on the artboard
    if (j.icons.length > 0) {
      updateComparison(0);
    }

    // Global progress & Processing Card
    $('#prog').classList.add('done');
    $('#prog i').style.width = '100%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = '100%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = '100%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = '100%';

    const pTitle = $('#procTitle');
    if (pTitle) pTitle.textContent = `Completed (${fmt(j.iou)} Match)`;
    const pSub = $('#procSub');
    if (pSub) pSub.textContent = `All ${j.icons.length} icons optimized into clean single-centerline vector paths.`;
    const cMsg = $('#canvasStatusMsg');
    if (cMsg) cMsg.textContent = 'Vector redraw complete';

    // Mark all stages done
    ['stageImageAnalysis', 'stagePathTracing', 'stageCurveOpt', 'stageOutputGen'].forEach(setStageDone);

    // Compute metrics
    const ms = j.icons.map(i => i.metrics).filter(Boolean);
    const paths = ms.reduce((a, m) => a + (m.paths || 0), 0);
    const nodes = ms.reduce((a, m) => a + (m.nodes || 0), 0);
    const dupes = (j.audit && j.audit.coincident) || 0;
    const sec = j.seconds || ((Date.now() - S.startTime) / 1000);

    updateMetricsUI(sec, paths, nodes, dupes);

    // Summary container
    const s = $('#summary');
    if (s) {
      s.hidden = false;
      const gaps = (j.audit && j.audit.gaps) || 0;
      const notches = (j.audit && j.audit.notches) || 0;
      const restored = (j.audit && j.audit.restored) || 0;
      const stray = (j.audit && j.audit.stray) || 0;
      const finFixed = (j.audit && j.audit.finisher_fixed) || 0;
      const finFound = (j.audit && j.audit.finisher_found) || 0;
      const stats = [
        ['Average Match', fmt(j.iou)],
        ['Total Icons', j.icons.length],
        ['Total Paths', paths],
        ['Total Nodes', nodes],
        ['Duplicate Centerlines', dupes],
        ['Open gaps', gaps],
        ['Notches', notches]
      ];
      if (restored > 0) stats.push(['Restored Chunks', restored]);
      if (stray > 0) stats.push(['Stray Removed', stray]);
      if (finFixed > 0 || finFound > 0) stats.push(['Finisher Engine', `${finFixed}/${finFound} sites fixed`]);
      const jTotal = (j.audit && j.audit.joints) || 0;
      const jRepaired = (j.audit && j.audit.joints_repaired) || 0;
      const jReview = (j.audit && j.audit.joints_review) || 0;
      if (jTotal > 0 || jRepaired > 0 || jReview > 0) {
        stats.push(['Join Engine', `${jTotal} joints / ${jRepaired} repaired / ${jReview} for review`]);
      }
      const sFound = (j.audit && j.audit.structure_found) || 0;
      const sFixed = (j.audit && j.audit.structure_fixed) || 0;
      const sReview = (j.audit && j.audit.structure_review) || 0;
      if (sFound > 0 || sFixed > 0 || sReview > 0) {
        stats.push(['Structure Engine', `${sFixed}/${sFound} sites fixed / ${sReview} for review`]);
      }

      if (j.set_pass) {
        if (j.set_pass.widths_changed > 0) stats.push(['Set Widths Harmonized', `${j.set_pass.widths_changed} icons`]);
        if (j.set_pass.weak && j.set_pass.weak.length > 0) stats.push(['Set Second Pass', `${j.set_pass.weak.length} weak icon(s)`]);
      }
      stats.push(['Processing Time', sec.toFixed(1) + 's']);
      s.innerHTML = stats.map(([k, v]) => `<div><span class="k">${k}</span><b>${v}</b></div>`).join('');
    }

    const imgDiff = $('#imgDiff');
    if (imgDiff) imgDiff.src = `/api/jobs/${S.job}/diff.png?v=${S.version}`;

    updateLinks();
    ['dlSvg', 'dlZip', 'copy', 'dlEps', 'btnSendToTemplate'].forEach(i => {
      const el = $('#' + i);
      if (el) el.classList.remove('disabled');
    });

    loadSvg();
    if (S.sel !== null) updateComparison(S.sel);
  }

  function renderUnresolvedJointsOverlay(svgEl, job) {
    if (!svgEl || !job || !job.icons) return;
    const oldOverlay = svgEl.querySelector('#unresolvedJointsOverlay');
    if (oldOverlay) oldOverlay.remove();

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = 'unresolvedJointsOverlay';
    g.setAttribute('class', 'unresolved-joints-layer');

    let count = 0;
    job.icons.forEach(ic => {
      const offX = (ic.box && ic.box[0]) || 0;
      const offY = (ic.box && ic.box[1]) || 0;
      const jn = ic.metrics && ic.metrics.joins;
      if (jn && jn.unresolved && jn.unresolved.length) {
        jn.unresolved.forEach(u => {
          const cx = offX + u.x;
          const cy = offY + u.y;
          const r = Math.max(7, (u.w || 8) * 0.9);
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', cx.toFixed(2));
          circle.setAttribute('cy', cy.toFixed(2));
          circle.setAttribute('r', r.toFixed(2));
          circle.setAttribute('fill', 'rgba(255, 0, 85, 0.15)');
          circle.setAttribute('stroke', '#ff0055');
          circle.setAttribute('stroke-width', '2');
          circle.setAttribute('stroke-dasharray', '4,3');

          const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
          title.textContent = `Unresolved joint: ${(u.reasons || []).join(', ')} at (${cx.toFixed(1)}, ${cy.toFixed(1)})`;
          circle.appendChild(title);

          g.appendChild(circle);
          count++;
        });
      }
      const sx = ic.metrics && ic.metrics.structure;
      if (sx && sx.unresolved && sx.unresolved.length) {
        sx.unresolved.forEach(u => {
          const cx = offX + u.x;
          const cy = offY + u.y;
          const r = Math.max(9, 12);
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', cx.toFixed(2));
          circle.setAttribute('cy', cy.toFixed(2));
          circle.setAttribute('r', r.toFixed(2));
          circle.setAttribute('fill', 'rgba(255, 120, 0, 0.15)');
          circle.setAttribute('stroke', '#ff7700');
          circle.setAttribute('stroke-width', '2');
          circle.setAttribute('stroke-dasharray', '3,3');

          const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
          title.textContent = `Unresolved structure: ${u.kind} (severity ${u.severity ? u.severity.toFixed(2) : '?'}) at (${cx.toFixed(1)}, ${cy.toFixed(1)})`;
          circle.appendChild(title);

          g.appendChild(circle);
          count++;
        });
      }
    });

    if (count > 0) {
      svgEl.appendChild(g);
    }
  }

  // ---------------------------------------------------------------- vector layer + live styling
  async function loadSvg() {
    const id = S.job;
    try {
      const t = await (await api(`/api/jobs/${id}/result.svg?bg=none&v=${S.version}`)).text();
      if (id !== S.job) return;
      const vec = $('#vec');
      if (vec) {
        vec.innerHTML = t;
        $$('#vec path').forEach(p => p.dataset.w = p.getAttribute('stroke-width'));
        applyStyle();
        if (S.jobData) renderUnresolvedJointsOverlay($('#vec svg'), S.jobData);
      }
    } catch (e) {}
  }

  // ---------------------------------------------------------------- Artboard background controller
  let currentArtboardBg = '#ffffff';

  function setArtboardBg(bg) {
    currentArtboardBg = bg;

    // Update active state in topbar buttons
    $$('#artboardSwitcher .ab-btn').forEach(b => {
      b.classList.toggle('on', b.dataset.bg === bg);
    });

    // Update select element in sidebar
    const bgSelect = $('#bg');
    if (bgSelect) {
      if (bg === '#ffffff') bgSelect.value = '#ffffff';
      else if (bg === 'grid' || bg === 'none') bgSelect.value = 'none';
      else if (bg === '#0c131d' || bg === '#0b0b0c') bgSelect.value = '#0b0b0c';
    }

    const c = $('#canvas');
    if (c) {
      c.classList.remove('ab-white', 'ab-grid', 'ab-dark', 'nobg', 'dark');
      if (bg === '#ffffff') {
        c.classList.add('ab-white');
      } else if (bg === 'grid' || bg === 'none') {
        c.classList.add('ab-grid');
      } else {
        c.classList.add('ab-dark');
      }
    }

    // Auto-contrast stroke color so lines are 100% visible!
    const strokeEl = $('#stroke');
    if (bg === '#0c131d' || bg === '#0b0b0c') {
      if (strokeEl && (strokeEl.value === '#111111' || strokeEl.value === '#000000')) {
        strokeEl.value = '#ffffff';
      }
    } else {
      if (strokeEl && strokeEl.value === '#ffffff') {
        strokeEl.value = '#111111';
      }
    }

    applyStyle();
  }

  const abSwitcher = $('#artboardSwitcher');
  if (abSwitcher) {
    abSwitcher.addEventListener('click', e => {
      const b = e.target.closest('.ab-btn');
      if (b && b.dataset.bg) {
        setArtboardBg(b.dataset.bg);
      }
    });
  }

  function applyStyle() {
    const sc = $('#scale') ? +$('#scale').value : 1;
    const isDark = currentArtboardBg === '#0c131d' || currentArtboardBg === '#0b0b0c';
    const defaultCol = isDark ? '#ffffff' : '#111111';
    const col = S.view === 'overlay' ? '#ef4444' : ($('#stroke') ? $('#stroke').value : defaultCol);
    const scaleV = $('#scaleV'); if (scaleV) scaleV.textContent = Math.round(sc * 100) + '%';

    const g = $('#vec g');
    if (g) g.setAttribute('stroke', col);
    $$('#vec path').forEach(p => {
      if (p.dataset.w) p.setAttribute('stroke-width', (+p.dataset.w * sc).toFixed(2));
    });

    const c = $('#canvas');
    if (c) {
      c.classList.remove('ab-white', 'ab-grid', 'ab-dark', 'nobg', 'dark');
      if (currentArtboardBg === '#ffffff') c.classList.add('ab-white');
      else if (currentArtboardBg === 'grid' || currentArtboardBg === 'none') c.classList.add('ab-grid');
      else c.classList.add('ab-dark');
    }

    updateLinks();
  }

  ['stroke', 'scale', 'bg'].forEach(i => {
    const el = $('#' + i);
    if (el) el.addEventListener('input', applyStyle);
  });

  function qs(extra = '') {
    const strk = $('#stroke') ? $('#stroke').value : '#111111';
    const sc = $('#scale') ? $('#scale').value : '1';
    let bg = 'none';
    if (currentArtboardBg === '#ffffff') bg = '#ffffff';
    else if (currentArtboardBg === '#0c131d' || currentArtboardBg === '#0b0b0c') bg = '#0b0b0c';
    return `stroke=${encodeURIComponent(strk)}&scale=${sc}&bg=${encodeURIComponent(bg)}${extra}`;
  }

  function updateLinks() {
    if (!S.job) return;
    const dlSvg = $('#dlSvg');
    if (dlSvg) dlSvg.href = `/api/jobs/${S.job}/result.svg?${qs('&download=1')}`;

    const dlEps = $('#dlEps');
    if (dlEps) dlEps.href = `/api/jobs/${S.job}/result.eps?${qs('&download=1')}`;

    const dlZip = $('#dlZip');
    const strk = $('#stroke') ? $('#stroke').value : '#111111';
    const sc = $('#scale') ? $('#scale').value : '1';
    if (dlZip) dlZip.href = `/api/jobs/${S.job}/download.zip?stroke=${encodeURIComponent(strk)}&scale=${sc}`;
  }

  const copyBtn = $('#copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        const t = await (await api(`/api/jobs/${S.job}/result.svg?${qs()}`)).text();
        await navigator.clipboard.writeText(t);
        toast('SVG copied to clipboard');
      } catch (e) {
        toast('Copy failed', 1);
      }
    });
  }

  // ---------------------------------------------------------------- views
  function setView(v) {
    S.view = v;
    $$('#view button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
    const o = $('#imgOrig'), d = $('#imgDiff'), vec = $('#vec');
    if (o) {
      o.style.display = (v === 'original' || v === 'overlay') ? 'block' : 'none';
      o.style.opacity = v === 'overlay' ? '0.5' : '1';
      o.style.filter = v === 'overlay' ? 'grayscale(1)' : 'none';
    }
    if (vec) vec.style.display = (v === 'vector' || v === 'overlay') ? 'block' : 'none';
    if (d) d.style.display = v === 'diff' ? 'block' : 'none';
    const leg = $('#legend'); if (leg) leg.hidden = v !== 'diff';
    applyStyle();
  }

  const vBox = $('#view');
  if (vBox) {
    vBox.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (b && b.dataset.v) setView(b.dataset.v);
    });
  }

  // ---------------------------------------------------------------- pan / zoom
  const stage = $('#stage'), canvas = $('#canvas');
  function sizeCanvas() {
    if (canvas && S.W && S.H) {
      canvas.style.width = S.W + 'px';
      canvas.style.height = S.H + 'px';
    }
  }

  function paint() {
    if (canvas) {
      canvas.style.transform = `translate(${S.tf.x}px,${S.tf.y}px) scale(${S.tf.k})`;
    }
  }

  function fit(box) {
    if (!stage || !S.W) return;
    const r = stage.getBoundingClientRect();
    const b = box || [0, 0, S.W, S.H];
    const bw = b[2] - b[0], bh = b[3] - b[1];
    const pad = box ? 0.76 : 0.94;
    const k = Math.min(r.width / bw, r.height / bh) * pad;
    S.tf = {
      k,
      x: (r.width - bw * k) / 2 - b[0] * k,
      y: (r.height - bh * k) / 2 - b[1] * k
    };
    paint();
  }

  function zoomAt(f, cx, cy) {
    const k = Math.min(Math.max(S.tf.k * f, 0.05), 40);
    const r = k / S.tf.k;
    S.tf.x = cx - (cx - S.tf.x) * r;
    S.tf.y = cy - (cy - S.tf.y) * r;
    S.tf.k = k;
    paint();
  }

  if (stage) {
    stage.addEventListener('wheel', e => {
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0016)), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });

    let drag = null;
    stage.addEventListener('pointerdown', e => {
      if (e.target.closest('.zoom-cluster')) return;
      drag = { x: e.clientX, y: e.clientY, tx: S.tf.x, ty: S.tf.y };
      stage.classList.add('drag');
      stage.setPointerCapture(e.pointerId);
    });

    stage.addEventListener('pointermove', e => {
      if (!drag) return;
      S.tf.x = drag.tx + e.clientX - drag.x;
      S.tf.y = drag.ty + e.clientY - drag.y;
      paint();
    });

    stage.addEventListener('pointerup', () => {
      drag = null;
      stage.classList.remove('drag');
    });

    stage.addEventListener('dblclick', () => {
      clearFocus();
      fit();
    });
  }

  const zIn = $('#zin');
  if (zIn) zIn.onclick = () => {
    if (!stage) return;
    const r = stage.getBoundingClientRect();
    zoomAt(1.35, r.width / 2, r.height / 2);
  };

  const zOut = $('#zout');
  if (zOut) zOut.onclick = () => {
    if (!stage) return;
    const r = stage.getBoundingClientRect();
    zoomAt(1 / 1.35, r.width / 2, r.height / 2);
  };

  const zFit = $('#zfit');
  if (zFit) zFit.onclick = () => {
    clearFocus();
    fit();
  };

  window.addEventListener('resize', () => S.job && fit());

  if (window.ResizeObserver && stage) {
    let roTimer = null;
    const ro = new ResizeObserver(() => {
      if (S.job && S.W && !S.sel) {
        clearTimeout(roTimer);
        roTimer = setTimeout(() => fit(), 30);
      }
    });
    ro.observe(stage);
  }

  // Fresh Run checkbox listener
  const freshRun = $('#freshRun');
  const freshBadge = $('#freshBadge');
  if (freshRun && freshBadge) {
    freshRun.addEventListener('change', () => {
      freshBadge.textContent = freshRun.checked ? 'Fresh (No Cache)' : 'Memory Active';
      freshBadge.style.color = freshRun.checked ? 'var(--accent)' : 'var(--text-dim)';
    });
  }

  // AI Lessons Modal & Cache Clearing
  const btnLessons = $('#btnLessons');
  const lessonsModal = $('#lessonsModal');
  const closeLessonsModal = $('#closeLessonsModal');
  const lessonsContent = $('#lessonsContent');

  async function loadLessonsModal() {
    if (!lessonsContent) return;
    lessonsContent.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-dim);">Loading memory data...</div>';
    try {
      const res = await fetch('/api/lessons');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      
      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <div><b>Memory Corpus:</b> ${data.icons} unique icons tracked</div>
          <div><b>Skipped Passes:</b> ${data.skipped && data.skipped.length ? data.skipped.map(s => `<span class="lessons-badge badge-skip">${s}</span>`).join(' ') : 'None'}</div>
        </div>
        <div style="font-weight:600; color:#fff; margin-bottom:6px;">Finisher Pass Performance (Found vs Fixed):</div>
        <table class="lessons-table">
          <thead>
            <tr>
              <th>Pass Name</th>
              <th>Found</th>
              <th>Fixed</th>
              <th>Success Rate</th>
            </tr>
          </thead>
          <tbody>
      `;
      const passes = data.passes || {};
      const sortedPasses = Object.entries(passes).sort((a, b) => b[1].found - a[1].found);
      for (const [name, counts] of sortedPasses) {
        const rate = counts.found > 0 ? ((counts.fixed / counts.found) * 100).toFixed(1) + '%' : '0%';
        const badgeClass = counts.fixed > 0 ? 'badge-ok' : (counts.found > 100 ? 'badge-skip' : 'badge-warn');
        html += `
          <tr>
            <td><b>${name}</b></td>
            <td>${counts.found}</td>
            <td>${counts.fixed}</td>
            <td><span class="lessons-badge ${badgeClass}">${rate}</span></td>
          </tr>
        `;
      }
      html += `
          </tbody>
        </table>
      `;
      if (data.remaining_issues) {
        html += `
          <div style="margin-top:20px; font-weight:600; color:#fff; margin-bottom:6px;">Remaining Defect Census across set runs:</div>
          <div style="display:flex; flex-wrap:wrap; gap:10px; font-family:var(--font-mono); font-size:12px;">
        `;
        for (const [k, v] of Object.entries(data.remaining_issues)) {
          if (v > 0) {
            html += `<div style="background:rgba(255,255,255,0.04); padding:6px 12px; border-radius:6px; border:1px solid var(--line-dim);"><span>${k}:</span> <b style="color:#fff;">${v}</b></div>`;
          }
        }
        html += `</div>`;
      }
      lessonsContent.innerHTML = html;
    } catch (err) {
      lessonsContent.innerHTML = `<div style="color:#ff4d4d; padding:20px;">Failed to load lessons: ${err.message}</div>`;
    }
  }

  async function clearCacheAction() {
    try {
      if (S.job) {
        clearTimeout(S.timer);
        api('/api/jobs/' + S.job + '/cancel', { method: 'POST' }).catch(() => {});
        S.job = null;
      }
      const r = await api('/api/cache/clear', { method: 'POST' });
      const res = await r.json();
      const count = res.cleared ? res.cleared.best_count : 0;
      toast(`Cache cleared & engine reset! All running jobs stopped.`, 0);
      const stg = $('#stage'); if (stg) stg.classList.remove('processing');
      const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Engine reset & ready';
      if (lessonsModal && lessonsModal.style.display !== 'none') {
        loadLessonsModal();
      }
    } catch (e) {
      toast('Failed to clear cache: ' + e.message, 1);
    }
  }

  
  const btnCancelJob = $('#btnCancelJob');
  if (btnCancelJob) {
    btnCancelJob.addEventListener('click', async () => {
      if (S.job) {
        clearTimeout(S.timer);
        try {
          await api('/api/jobs/' + S.job + '/cancel', { method: 'POST' });
        } catch {}
        S.job = null;
        toast('Processing cancelled by user', 0);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Cancelled';
        $('#landing').hidden = false;
        $('#work').hidden = true;
      }
    });
  }

  const btnClearCacheDirect = $('#btnClearCacheDirect');
  if (btnClearCacheDirect) {
    btnClearCacheDirect.addEventListener('click', clearCacheAction);
  }
  const btnClearLessons = $('#btnClearLessons');
  if (btnClearLessons) {
    btnClearLessons.addEventListener('click', clearCacheAction);
  }

  if (btnLessons && lessonsModal) {
    btnLessons.onclick = async () => {
      lessonsModal.style.display = 'flex';
      loadLessonsModal();
    };

    if (closeLessonsModal) {
      closeLessonsModal.onclick = () => {
        lessonsModal.style.display = 'none';
      };
    }
    lessonsModal.onclick = e => {
      if (e.target === lessonsModal) lessonsModal.style.display = 'none';
    };
  }

  // ================================================================
  // Presentation Template Studio Logic
  // ================================================================
  const TEMPLATE_PRESETS = {
    obsidian: {
      name: 'Obsidian Dark',
      bg: '#090d14', panel_bg: '#121824', accent: '#00f5a0',
      title_color: '#ffffff', text_color: '#ffffff', icon_stroke: '#00f5a0'
    },
    minimal: {
      name: 'Minimalist Studio',
      bg: '#f8fafc', panel_bg: '#ffffff', accent: '#0284c7',
      title_color: '#0f172a', text_color: '#0f172a', icon_stroke: '#0f172a'
    },
    cyber: {
      name: 'Cyber Neon',
      bg: '#0a0a16', panel_bg: '#131326', accent: '#f43f5e',
      title_color: '#ffffff', text_color: '#ffffff', icon_stroke: '#38bdf8'
    },
    gold: {
      name: 'Luxury Gold',
      bg: '#121110', panel_bg: '#1c1a17', accent: '#d4af37',
      title_color: '#fef3c7', text_color: '#fef3c7', icon_stroke: '#d4af37'
    },
    cream: {
      name: 'Pastel Cream',
      bg: '#faf7f2', panel_bg: '#ffffff', accent: '#e11d48',
      title_color: '#292524', text_color: '#292524', icon_stroke: '#292524'
    },
    blueprint: {
      name: 'Blueprint Tech',
      bg: '#0a192f', panel_bg: '#112240', accent: '#38bdf8',
      title_color: '#f8fafc', text_color: '#f8fafc', icon_stroke: '#38bdf8'
    }
  };

  S.template = {
    preset: 'obsidian',
    layout: 'landscape',
    zoom: 1.0
  };

  function renderPresetCards() {
    const box = $('#presetList');
    if (!box) return;
    box.innerHTML = '';
    for (const [key, p] of Object.entries(TEMPLATE_PRESETS)) {
      const el = document.createElement('div');
      el.className = 'preset-card' + (S.template.preset === key ? ' active' : '');
      el.dataset.p = key;
      el.innerHTML = `
        <div class="preset-card-name">${p.name}</div>
        <div class="preset-swatches">
          <span class="swatch-dot" style="background:${p.bg}" title="Background"></span>
          <span class="swatch-dot" style="background:${p.panel_bg}" title="Card"></span>
          <span class="swatch-dot" style="background:${p.accent}" title="Accent"></span>
          <span class="swatch-dot" style="background:${p.icon_stroke}" title="Stroke"></span>
        </div>
      `;
      el.onclick = () => selectPreset(key);
      box.appendChild(el);
    }
  }

  function selectPreset(key) {
    const p = TEMPLATE_PRESETS[key];
    if (!p) return;
    S.template.preset = key;
    $$('#presetList .preset-card').forEach(c => c.classList.toggle('active', c.dataset.p === key));
    const hint = $('#customColorHint');
    if (hint) hint.textContent = p.name;

    if ($('#tplBgColor')) $('#tplBgColor').value = p.bg;
    if ($('#tplPanelBgColor')) $('#tplPanelBgColor').value = p.panel_bg;
    if ($('#tplAccentColor')) $('#tplAccentColor').value = p.accent;
    if ($('#tplTextColor')) $('#tplTextColor').value = p.title_color;
    if ($('#tplStrokeColor')) $('#tplStrokeColor').value = p.icon_stroke;

    scheduleTemplateUpdate();
  }

  let tplUpdateTimer = null;
  function scheduleTemplateUpdate() {
    clearTimeout(tplUpdateTimer);
    tplUpdateTimer = setTimeout(updateTemplatePreview, 80);
  }

  function formatTitle(rawName) {
    if (!rawName) return 'Minimal Vector Line Icons';
    let clean = rawName.replace(/\.[^/.]+$/, '').replace(/[-_]+/g, ' ');
    clean = clean.replace(/\b\w/g, c => c.toUpperCase());
    if (!clean.toLowerCase().includes('icon')) clean += ' Icons';
    return clean;
  }

  function openTemplateStudio() {
    if (!S.job) return;
    $('#work').hidden = true;
    $('#templateStudio').hidden = false;

    // Auto-populate title if empty or default
    const titleInput = $('#tplTitle');
    if (titleInput && (!titleInput.value || titleInput.value === 'Minimal Vector Line Icons')) {
      titleInput.value = formatTitle(S.name);
    }

    renderPresetCards();
    updateTemplatePreview();
  }

  function closeTemplateStudio() {
    $('#templateStudio').hidden = true;
    $('#work').hidden = false;
    fit();
  }

  async function updateTemplatePreview() {
    if (!S.job) return;
    const title = $('#tplTitle') ? $('#tplTitle').value : 'Minimal Vector Line Icons';
    const subtitle = $('#tplSubtitle') ? $('#tplSubtitle').value : 'Clean Centerline Vector Icon Collection';
    const grid = $('#tplGrid') ? $('#tplGrid').value : '64 × 64 px Grid';
    const author = $('#tplAuthor') ? $('#tplAuthor').value : 'Linework AI Precision Engine';
    const bg = $('#tplBgColor') ? $('#tplBgColor').value : '#090d14';
    const panelBg = $('#tplPanelBgColor') ? $('#tplPanelBgColor').value : '#121824';
    const accent = $('#tplAccentColor') ? $('#tplAccentColor').value : '#00f5a0';
    const stroke = $('#tplStrokeColor') ? $('#tplStrokeColor').value : '#00f5a0';
    const scale = $('#tplStrokeScale') ? $('#tplStrokeScale').value : '1.0';
    const layout = S.template.layout || 'landscape';

    const params = new URLSearchParams({
      preset: S.template.preset || 'obsidian',
      title: title,
      subtitle: subtitle,
      grid_size: grid,
      author: author,
      layout: layout,
      stroke: stroke,
      scale: scale,
      bg: bg,
      panel_bg: panelBg,
      accent: accent,
    });

    // Update download links
    const dlSvg = $('#btnDlTemplateSvg');
    if (dlSvg) dlSvg.href = `/api/jobs/${S.job}/template.svg?${params.toString()}&download=1`;

    const dlEps = $('#btnDlTemplateEps');
    if (dlEps) dlEps.href = `/api/jobs/${S.job}/template.eps?${params.toString()}&download=1`;

    const dlZip = $('#btnDlTemplateZip');
    if (dlZip) dlZip.href = `/api/jobs/${S.job}/download.zip?stroke=${encodeURIComponent(stroke)}&scale=${scale}`;

    // Update dims indicator
    const dimsBadge = $('#tplDimsBadge');
    if (dimsBadge) {
      dimsBadge.textContent = (layout === 'square' ? '1200 × 1200 px' : '1600 × 1000 px') + ' · SVG & EPS Merged';
    }

    try {
      const res = await api(`/api/jobs/${S.job}/template.svg?${params.toString()}`);
      if (res.ok) {
        const svgContent = await res.text();
        const container = $('#templateSvgContainer');
        if (container) {
          container.innerHTML = svgContent;
        }
      }
    } catch (e) {
      console.error('Failed to load template preview:', e);
    }
  }

  // Setup template listeners
  const btnSendToTemplate = $('#btnSendToTemplate');
  if (btnSendToTemplate) {
    btnSendToTemplate.addEventListener('click', () => {
      if (!S.job) {
        toast('Please load an icon sheet first', 1);
        return;
      }
      openTemplateStudio();
    });
  }

  const btnBackToWork = $('#btnBackToWork');
  if (btnBackToWork) {
    btnBackToWork.addEventListener('click', closeTemplateStudio);
  }

  // Text inputs live preview
  ['tplTitle', 'tplSubtitle', 'tplGrid', 'tplAuthor'].forEach(id => {
    const el = $('#' + id);
    if (el) el.addEventListener('input', scheduleTemplateUpdate);
  });

  // Color inputs live preview
  ['tplBgColor', 'tplPanelBgColor', 'tplAccentColor', 'tplTextColor', 'tplStrokeColor'].forEach(id => {
    const el = $('#' + id);
    if (el) {
      el.addEventListener('input', () => {
        $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
        const hint = $('#customColorHint');
        if (hint) hint.textContent = 'Custom Preset';
        scheduleTemplateUpdate();
      });
    }
  });

  // Stroke scale slider
  const tplScale = $('#tplStrokeScale');
  const tplScaleVal = $('#tplScaleVal');
  if (tplScale && tplScaleVal) {
    tplScale.addEventListener('input', () => {
      tplScaleVal.textContent = Math.round(tplScale.value * 100) + '%';
      scheduleTemplateUpdate();
    });
  }

  // Layout switcher
  $$('#tplLayoutSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplLayoutSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.layout = b.dataset.v;
      scheduleTemplateUpdate();
    });
  });

  // Zoom controls for template studio
  let tplZoom = 1.0;
  function setTemplateZoom(z) {
    tplZoom = Math.min(Math.max(z, 0.4), 2.5);
    const container = $('#templateSvgContainer');
    if (container) {
      container.style.transform = `scale(${tplZoom})`;
    }
  }

  const tplZin = $('#tplZin');
  if (tplZin) tplZin.onclick = () => setTemplateZoom(tplZoom * 1.2);
  const tplZout = $('#tplZout');
  if (tplZout) tplZout.onclick = () => setTemplateZoom(tplZoom / 1.2);
  const tplZfit = $('#tplZfit');
  if (tplZfit) tplZfit.onclick = () => setTemplateZoom(1.0);

  hint();
})();



================================================================================
# FILE: linework/__init__.py
================================================================================

"""Linework: raster line-art -> clean single-stroke centerline SVG, verified by an Edit/Output/Doctor loop."""
__version__ = "0.9.4"



================================================================================
# FILE: linework/model.py
================================================================================

"""Vector model: a list of stroked Bezier paths (anchors + in/out handles), serialisable to SVG/JSON."""
from __future__ import annotations
import copy, json
import numpy as np
from .geom import bez


class Path:
    __slots__ = ("A", "Hin", "Hout", "w", "join", "ml", "closed")

    def __init__(self, A, Hin, Hout, w, join="round", ml=4.0, closed=False):
        self.A = np.asarray(A, float)
        self.Hin = np.asarray(Hin, float)
        self.Hout = np.asarray(Hout, float)
        self.w = float(w)
        self.join = join
        self.ml = float(ml)
        self.closed = bool(closed)

    @staticmethod
    def from_segs(segs, w, closed=False, join="round"):
        S = np.array(segs, float)
        A = np.vstack([S[:, 0], S[-1:, 3]])
        Ho = np.vstack([S[:, 1], S[-1:, 3]])
        Hi = np.vstack([S[:1, 0], S[:, 2]])
        if closed:
            A[-1] = A[0]
            Ho[-1] = Ho[0]
            Hi[0] = Hi[-1]
        return Path(A, Hi, Ho, w, join, 4.0, closed)

    def segs(self):
        return [np.array([self.A[i], self.Hout[i], self.Hin[i + 1], self.A[i + 1]]) for i in range(len(self.A) - 1)]

    def flat(self, step=1.0):
        pts = []
        for c in self.segs():
            L = np.linalg.norm(c[3] - c[0]) + np.linalg.norm(c[1] - c[0]) + np.linalg.norm(c[2] - c[1]) + np.linalg.norm(c[3] - c[2])
            n = max(6, int(L / step / 1.4))
            q = bez(c, np.linspace(0, 1, n))
            pts.append(q if not pts else q[1:])
        return np.vstack(pts)

    def d(self):
        s = self.segs()
        d = "M%.2f,%.2f" % tuple(s[0][0])
        for c in s:
            d += "C%.2f,%.2f %.2f,%.2f %.2f,%.2f" % (*c[1], *c[2], *c[3])
        return d + ("Z" if self.closed else "")

    def length(self):
        f = self.flat()
        return float(np.linalg.norm(np.diff(f, axis=0), axis=1).sum())

    def copy(self):
        return Path(self.A.copy(), self.Hin.copy(), self.Hout.copy(), self.w, self.join, self.ml, self.closed)

    def to_dict(self):
        return dict(A=self.A.tolist(), Hin=self.Hin.tolist(), Hout=self.Hout.tolist(), w=self.w, join=self.join, ml=self.ml, closed=self.closed)

    @staticmethod
    def from_dict(q):
        return Path(q["A"], q["Hin"], q["Hout"], q["w"], q.get("join", "round"), q.get("ml", 4.0), q.get("closed", False))


class Model:
    def __init__(self, paths=None, width=0, height=0):
        self.paths: list[Path] = paths or []
        self.width = width
        self.height = height

    def copy(self):
        return Model([p.copy() for p in self.paths], self.width, self.height)

    def scaled(self, k, width=None, height=None):
        """New model with every coordinate and stroke width multiplied by k (SVG pixel-edge coords scale exactly)."""
        out = self.copy()
        for p in out.paths:
            p.A, p.Hin, p.Hout = p.A * k, p.Hin * k, p.Hout * k
            p.w *= k
        out.width = width if width is not None else int(round(self.width * k))
        out.height = height if height is not None else int(round(self.height * k))
        return out

    def translate(self, dx, dy):
        for p in self.paths:
            for a in (p.A, p.Hin, p.Hout):
                a += [dx, dy]
        return self

    def svg(self, background="#ffffff", stroke="#000000", cap="round", stroke_scale=1.0, pretty=False, viewbox=None):
        w, h = self.width, self.height
        vb = viewbox or (0, 0, w, h)
        body = []
        for p in self.paths:
            body.append(
                '<path d="%s" stroke-width="%.2f" stroke-linejoin="%s"%s/>'
                % (p.d(), p.w * stroke_scale, p.join, (' stroke-miterlimit="%g"' % p.ml) if p.join == "miter" else "")
            )
        bg = '<rect width="100%%" height="100%%" fill="%s"/>' % background if background else ""
        sep = "\n  " if pretty else ""
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" width="%g" height="%g">%s%s'
            '<g fill="none" stroke="%s" stroke-linecap="%s">%s%s</g>%s</svg>'
            % (vb[0], vb[1], vb[2], vb[3], vb[2], vb[3], sep, bg, stroke, cap, sep, sep.join(body), "\n" if pretty else "")
        )

    def to_json(self):
        return json.dumps(dict(width=self.width, height=self.height, paths=[p.to_dict() for p in self.paths]))

    @staticmethod
    def from_svg(svg: str):
        """Read back an SVG written by `Model.svg()` (M / C / Z paths with per-path stroke-width)."""
        import re
        num = lambda t: [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", t)]
        head = re.search(r'viewBox="([^"]+)"', svg)
        vb = num(head.group(1)) if head else [0, 0, 0, 0]
        paths = []
        for d, w in re.findall(r'<path d="([^"]+)" stroke-width="([\d.]+)"', svg):
            toks = re.findall(r"[MCZ][^MCZ]*", d)
            p0 = num(toks[0])[:2]
            A, Hi, Ho = [p0], [p0], []
            for t in toks[1:]:
                if t[0] == "C":
                    v = num(t)
                    for k in range(0, len(v) - 5, 6):
                        Ho.append(v[k:k + 2]); Hi.append(v[k + 2:k + 4]); A.append(v[k + 4:k + 6])
            if not Ho:
                continue
            Ho.append(A[-1])
            jm = re.search(r'<path d="%s"[^>]*stroke-linejoin="(\w+)"' % re.escape(d), svg)
            paths.append(Path(A, Hi, Ho, float(w), jm.group(1) if jm else "round", 4.0, toks[-1].startswith("Z")))
        return Model(paths, int(vb[2]), int(vb[3]))

    @staticmethod
    def from_json(s):
        q = json.loads(s)
        return Model([Path.from_dict(p) for p in q["paths"]], q["width"], q["height"])



================================================================================
# FILE: linework/geom.py
================================================================================

"""Curve geometry helpers: Bezier evaluation, Schneider curve fitting, resampling, corner detection."""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d


def bez(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return mt**3 * c[0] + 3 * mt**2 * t * c[1] + 3 * mt * t**2 * c[2] + t**3 * c[3]


def _d1(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return 3 * mt**2 * (c[1] - c[0]) + 6 * mt * t * (c[2] - c[1]) + 3 * t**2 * (c[3] - c[2])


def _d2(c, t):
    t = np.asarray(t, float)[:, None]
    mt = 1 - t
    return 6 * mt * (c[2] - 2 * c[1] + c[0]) + 6 * t * (c[3] - 2 * c[2] + c[1])


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v * 0


def arclen(p):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]


def resample(p, step=1.0):
    p = np.asarray(p, float)
    d = arclen(p)
    if d[-1] < 1e-9:
        return p[:2] if len(p) >= 2 else np.vstack([p, p])
    n = max(2, int(d[-1] / step) + 1)
    s = np.linspace(0, d[-1], n)
    return np.c_[np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]


# ---------------------------------------------------------------- Schneider fit
def _chord(p):
    d = arclen(p)
    return d / d[-1] if d[-1] > 0 else d


def _gen(p, u, t1, t2):
    A1 = (3 * (1 - u) ** 2 * u)[:, None] * t1
    A2 = (3 * (1 - u) * u**2)[:, None] * t2
    C = np.array([[np.sum(A1 * A1), np.sum(A1 * A2)], [np.sum(A1 * A2), np.sum(A2 * A2)]])
    b0, b3 = p[0], p[-1]
    tmp = p - (((1 - u) ** 3 + 3 * (1 - u) ** 2 * u)[:, None] * b0 + ((3 * (1 - u) * u**2) + u**3)[:, None] * b3)
    X = np.array([np.sum(A1 * tmp), np.sum(A2 * tmp)])
    det = C[0, 0] * C[1, 1] - C[0, 1] ** 2
    seg = np.linalg.norm(b3 - b0)
    if abs(det) > 1e-12:
        a1 = (X[0] * C[1, 1] - X[1] * C[0, 1]) / det
        a2 = (C[0, 0] * X[1] - C[0, 1] * X[0]) / det
    else:
        a1 = a2 = 0
    if a1 < 1e-6 * seg or a2 < 1e-6 * seg:
        a1 = a2 = seg / 3
    return np.array([b0, b0 + t1 * a1, b3 + t2 * a2, b3])


def _reparam(c, p, u):
    for _ in range(3):
        d = bez(c, u) - p
        d1 = _d1(c, u)
        d2 = _d2(c, u)
        num = np.sum(d * d1, 1)
        den = np.sum(d1 * d1, 1) + np.sum(d * d2, 1)
        den = np.where(abs(den) < 1e-12, 1e-12, den)
        u = np.clip(u - num / den, 0, 1)
    return u


def _fitcubic(p, t1, t2, err, depth=0):
    if len(p) == 2:
        d = np.linalg.norm(p[1] - p[0]) / 3
        return [np.array([p[0], p[0] + t1 * d, p[1] + t2 * d, p[1]])]
    u = _chord(p)
    c = _gen(p, u, t1, t2)
    i = 0
    for it in range(6):
        e = np.sum((bez(c, u) - p) ** 2, 1)
        i = int(np.argmax(e))
        if e[i] < err**2:
            return [c]
        if it == 5:
            break
        u = _reparam(c, p, u)
        c = _gen(p, u, t1, t2)
    i = max(1, min(len(p) - 2, i))
    tc = unit(p[i - 1] - p[i + 1])
    if depth > 40:
        return [c]
    return _fitcubic(p[: i + 1], t1, tc, err, depth + 1) + _fitcubic(p[i:], -tc, t2, err, depth + 1)


def fitpath(p, err=0.3):
    """Fit a chain of cubic Beziers (list of 4x2 arrays) to polyline p."""
    p = np.asarray(p, float)
    if len(p) < 2:
        return []
    k = min(6, len(p) - 1)
    t1 = unit(p[min(k, len(p) - 1)] - p[0])
    t2 = unit(p[max(-k - 1, -len(p))] - p[-1])
    return _fitcubic(p, t1, t2, err)


def smooth(q, sigma):
    """Gaussian-smooth a polyline while pinning both endpoints."""
    if len(q) <= 8 or sigma <= 0:
        return q
    m = min(int(3 * sigma) + 1, len(q) - 1)
    ext = np.vstack([2 * q[0] - q[1 : m + 1][::-1], q, 2 * q[-1] - q[-m - 1 : -1][::-1]])
    sm = gaussian_filter1d(ext, sigma, axis=0, mode="nearest")[m : m + len(q)]
    sm[0] = q[0]
    sm[-1] = q[-1]
    return sm


def corners(p, win=7, ang=40):
    """Indices of local turning-angle maxima above `ang` degrees (window +-win samples)."""
    n = len(p)
    th = np.zeros(n)
    for i in range(win, n - win):
        a = p[i] - p[i - win]
        b = p[i + win] - p[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-6 or nb < 1e-6:
            continue
        th[i] = np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1)))
    res = []
    for i in range(win, n - win):
        if th[i] > ang and th[i] >= th[max(0, i - win) : i + win + 1].max():
            if not res or i - res[-1] > win:
                res.append(i)
    return res


def fit_curve(q, sigma=1.5, err=0.3):
    """Smooth + fit, splitting at sharp corners so they stay sharp."""
    cs = corners(q, 7, 35) if len(q) > 16 else []
    cuts = [0] + cs + [len(q) - 1]
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 1:
            continue
        out += fitpath(smooth(q[a : b + 1], sigma), err)
    return out


def linefit(q):
    c = q.mean(0)
    _, _, vt = np.linalg.svd(q - c)
    d = vt[0]
    res = np.abs((q - c) @ np.array([-d[1], d[0]])).max()
    return c, d, res


def line_inter(c1, d1, c2, d2):
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-6:
        return None
    t = np.linalg.solve(A, c2 - c1)
    return c1 + d1 * t[0]


def hermite(A1, d1, A2, d2):
    L = np.linalg.norm(A2 - A1)
    n = max(2, int(L) + 1)
    c = np.array([A1, A1 + d1 * L / 3, A2 + d2 * L / 3, A2])
    return bez(c, np.linspace(0, 1, n))



================================================================================
# FILE: linework/trace.py
================================================================================

"""Raster -> skeleton graph -> edge-centred branches with measured stroke width."""
from __future__ import annotations
import numpy as np, cv2
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates, gaussian_filter1d
from skimage.morphology import skeletonize
from .geom import resample, arclen, unit

_K = np.ones((3, 3))
_K[1, 1] = 0


def ink_map(gray: np.ndarray) -> np.ndarray:
    """Normalised ink coverage in [0,1] (1 = ink). Handles dark-on-light and light-on-dark."""
    g = gray.astype(np.float32)
    border = np.r_[g[0], g[-1], g[:, 0], g[:, -1]]
    if np.median(border) < 128:
        g = 255 - g
    t, _ = cv2.threshold(g.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark, light = g[g <= t], g[g > t]
    lo = float(np.median(dark)) if dark.size else 0.0
    hi = float(np.median(light)) if light.size else 255.0
    if hi - lo < 30:
        lo, hi = 0.0, 255.0
    return np.clip((hi - g) / (hi - lo), 0, 1).astype(np.float32)


# ---------------------------------------------------------------- skeleton
def _prune(sk, L, H, W):
    sk = sk.copy()
    for _ in range(3):
        nb = ndi.convolve(sk.astype(int), _K, mode="constant") * sk
        ends = np.argwhere((nb == 1) & sk)
        changed = False
        for e in ends:
            path = [tuple(e)]
            cur = tuple(e)
            prev = None
            ns = []
            while True:
                y, x = cur
                ns = [
                    (y + dy, x + dx)
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]
                    and (y + dy, x + dx) != prev and (y + dy, x + dx) not in path
                ]
                if len(ns) != 1:
                    break
                prev = cur
                cur = ns[0]
                path.append(cur)
                if len(path) > L:
                    break
            if len(path) <= L and len(ns) >= 2:
                for p in path[:-1]:
                    sk[p] = False
                changed = True
        sk = skeletonize(sk)
        if not changed:
            break
    return sk


def skeleton_branches(D: np.ndarray, S: int = 2, prune: int | None = None):
    """Return list of branches: dict(pts (N,2) x/y in source pixel-index coords, sj, ej)."""
    up = cv2.resize(D, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
    mask = up > 0.5
    sk = skeletonize(mask)
    H, W = sk.shape
    dt = ndi.distance_transform_edt(mask)
    v = dt[sk]
    w_up = float(2 * np.median(v)) if v.size else (10.0 * S)
    prune_eff = prune if prune is not None else max(7 * S, int(round(1.2 * w_up)))
    sk = _prune(sk, prune_eff, H, W)
    nb = ndi.convolve(sk.astype(int), _K, mode="constant") * sk
    junc = (nb >= 3) & sk
    jl, nj = ndi.label(junc, structure=np.ones((3, 3)))
    ends = (nb == 1) & sk
    off = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]

    def nbrs(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in off if 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]]

    visited = np.zeros_like(sk)
    branches = []
    _cm = ndi.center_of_mass(np.ones(jl.shape, np.uint8), jl, list(range(1, nj + 1))) if nj else []
    jcent = {i: np.array(_cm[i - 1]) for i in range(1, nj + 1)}

    def trace(start, first):
        path = [start, first]
        visited[start] = True
        prev, cur = start, first
        while True:
            if jl[cur] > 0 and cur != start:
                return path, jl[cur]
            visited[cur] = True
            ns = [n for n in nbrs(cur) if n != prev and n not in path[-4:]]
            ns2 = [n for n in ns if not visited[n] or jl[n] > 0]
            if not ns2:
                return path, 0
            ns2.sort(key=lambda n: abs(n[0] - cur[0]) + abs(n[1] - cur[1]))
            prev, cur = cur, ns2[0]
            path.append(cur)

    starts = [(tuple(p), 0) for p in np.argwhere(ends)]
    for p in map(tuple, np.argwhere(junc)):
        for n in nbrs(p):
            if jl[n] == 0:
                starts.append((p, int(jl[p])))
    for p, sj in starts:
        if sj == 0:
            if visited[p]:
                continue
            ns = nbrs(p)
            if not ns:
                continue
            path, ej = trace(p, ns[0])
            branches.append((path, 0, int(ej)))
        else:
            for n in nbrs(p):
                if jl[n] == 0 and not visited[n]:
                    path, ej = trace(p, n)
                    branches.append((path, sj, int(ej)))
    rem = sk & ~visited & (jl == 0)
    lab, nl = ndi.label(rem, structure=np.ones((3, 3)))
    for i in range(1, nl + 1):
        pts = np.argwhere(lab == i)
        if len(pts) < 20:
            continue
        p = tuple(pts[0])
        path = [p]
        cur = p
        seen = {p}
        while True:
            ns = [n for n in nbrs(cur) if n not in seen]
            if not ns:
                break
            ns.sort(key=lambda n: abs(n[0] - cur[0]) + abs(n[1] - cur[1]))
            cur = ns[0]
            seen.add(cur)
            path.append(cur)
        branches.append((path, -1, -1))

    def conv(rc):  # (row,col) at S-scale -> (x,y) source pixel-index coords
        a = np.asarray(rc, float)[:, ::-1]
        return (a + 0.5) / S - 0.5

    out = []
    for path, sj, ej in branches:
        pts = conv(path)
        if sj > 0:
            pts = np.vstack([conv([jcent[sj]])[0:1], pts])
        if ej > 0:
            pts = np.vstack([pts, conv([jcent[ej]])[0:1]])
        out.append(dict(pts=pts, sj=int(sj), ej=int(ej)))
    return out


# ---------------------------------------------------------------- edge centring
def _profile(D, P, N, R, step=0.25):
    t = np.arange(-R, R + step, step)
    X = P[:, 0, None] + N[:, 0, None] * t[None]
    Y = P[:, 1, None] + N[:, 1, None] * t[None]
    return t, map_coordinates(D, [Y, X], order=1, mode="nearest")


def _edges(t, v):
    """Sub-pixel 50 % crossings on both sides of each profile's centre (vectorised)."""
    n, m = v.shape
    c = m // 2
    L = np.full(n, np.nan)
    R = np.full(n, np.nan)
    if m < 5:
        return L, R
    dt = t[1] - t[0]
    below = v < 0.5
    inside = v[:, c] >= 0.5
    seg = below[:, c + 1 : m - 1]  # candidate crossing j = c+1 .. m-2
    has = seg.any(1) & inside
    j = c + 1 + seg.argmax(1)
    i = np.nonzero(has)[0]
    if len(i):
        a, b = v[i, j[i] - 1], v[i, j[i]]
        f = np.where(a != b, (a - 0.5) / np.where(a != b, a - b, 1), 0)
        R[i] = t[j[i] - 1] + f * dt
    segl = below[:, 1:c]  # j = 1 .. c-1, want the nearest one to the centre
    hasl = (segl.any(1) if segl.shape[1] else np.zeros(n, bool)) & inside
    jl = 1 + (segl.shape[1] - 1 - segl[:, ::-1].argmax(1)) if segl.shape[1] else np.zeros(n, int)
    i = np.nonzero(hasl)[0]
    if len(i):
        a, b = v[i, jl[i] + 1], v[i, jl[i]]
        f = np.where(a != b, (a - 0.5) / np.where(a != b, a - b, 1), 0)
        L[i] = t[jl[i] + 1] - f * dt
    return L, R


def _tang(P):
    T = np.gradient(gaussian_filter1d(P, 3, axis=0, mode="nearest"), axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    return T


def refine_branch(D, P, its=3, R=None, wmax=40.0, w_icon=None):
    """Shift samples to the centre between the two 50%-ink edges; return (P, per-sample width)."""
    P = P.copy()
    W = np.full(len(P), np.nan)
    R = R or 22
    for _ in range(its):
        T = _tang(P)
        N = np.c_[-T[:, 1], T[:, 0]]
        t, v = _profile(D, P, N, R)
        L, Rr = _edges(t, v)
        ok = ~np.isnan(L) & ~np.isnan(Rr)
        w = Rr - L
        ok &= (w > 0) & (w < wmax)
        if ok.sum() >= 4:
            w_ref = float(np.percentile(w[ok], 40))
            if w_icon is not None and w_icon > 0 and len(P) < 2.2 * w_icon:
                w_ref = min(w_ref, 1.22 * w_icon)
            ok &= (w <= 1.32 * w_ref) & (np.abs(L + Rr) <= 0.45 * w_ref)
        elif w_icon is not None and w_icon > 0:
            ok &= (w <= 1.35 * w_icon) & (np.abs(L + Rr) <= 0.45 * w_icon)
        off = np.where(ok, (L + Rr) / 2, 0)
        if ok.sum() > 3:
            num = gaussian_filter1d(np.where(ok, off, 0), 2.5, mode="nearest")
            den = np.maximum(gaussian_filter1d(ok.astype(float), 2.5, mode="nearest"), 1e-3)
            offs = np.where(ok, num / den, 0)
            P = P + N * offs[:, None]
        W = np.where(ok, w, np.nan)
    return P, W


def extend_end(D, P, which, r):
    """Move a free endpoint to (stroke tip - r along tangent) so round caps land exactly on the tip."""
    p = P[0] if which == 0 else P[-1]
    q = P[min(8, len(P) - 1)] if which == 0 else P[-1 - min(8, len(P) - 1)]
    d = unit(p - q)
    ts = np.arange(-4, r + 8, 0.25)
    pts = p[None] + d[None] * ts[:, None]
    v = map_coordinates(D, [pts[:, 1], pts[:, 0]], order=1, mode="nearest")
    k = np.where(v < 0.5)[0]
    k = k[k > np.argmax(ts >= 0)] if len(k) else k
    if not len(k):
        return p
    j = k[0]
    a, b = v[j - 1], v[j]
    tip = ts[j - 1] + ((a - 0.5) / (a - b) if a != b else 0) * 0.25
    return p + d * (tip - r)


def march_acute_end(D, P2, w_prof, rw, end_idx):
    """If end_idx (0 or 1) of P2 has a sharp skeleton hook inside a wide junction zone (w_prof > 1.35*rw),
    march from the last clean single-stroke sample along the unobstructed outer ink edge at distance 0.5*rw
    until reaching the single-stroke width of the through-branch."""
    pts = P2 if end_idx == 0 else P2[::-1]
    wp = w_prof if end_idx == 0 else w_prof[::-1]
    n = len(pts)
    if n < max(16, int(2.4 * rw)):
        return P2, False
    clean_mask = np.isfinite(wp) & (wp >= 0.70 * rw) & (wp <= 1.20 * rw)
    clean_idx = np.nonzero(clean_mask)[0]
    if not len(clean_idx):
        return P2, False
    k_clean = int(clean_idx[0])
    if not (max(3, int(0.45 * rw)) <= k_clean <= int(1.65 * rw)):
        return P2, False
    if not np.isfinite(wp[:k_clean]).any() or float(np.nanmax(wp[:k_clean])) < 1.55 * rw:
        return P2, False
    k_back = min(n - 1, k_clean + max(6, int(0.95 * rw)))
    if k_back <= k_clean + 2:
        return P2, False
    cur_pt = pts[k_clean].copy()
    cur_dir = unit(pts[k_clean] - pts[k_back])
    v_stub = pts[0] - pts[k_clean]
    if np.linalg.norm(v_stub) < 0.35 * rw:
        return P2, False
    u_stub = unit(v_stub)
    hook_deg = float(np.degrees(np.arccos(np.clip(u_stub @ cur_dir, -1.0, 1.0))))
    if hook_deg < 28.0:
        return P2, False

    N_dir = np.array([-cur_dir[1], cur_dir[0]])
    stub_side = 1 if (v_stub @ N_dir) >= 0 else -1
    traced = [cur_pt.copy()]
    reached = False
    for step in range(int(2.8 * rw)):
        cand = cur_pt + cur_dir * 1.0
        N_dir = np.array([-cur_dir[1], cur_dir[0]])
        t, v = _profile(D, cand[None, :], N_dir[None, :], 22)
        L, Rr = _edges(t, v)
        l_val, r_val = float(L[0]), float(Rr[0])
        if stub_side > 0:
            if not np.isfinite(l_val):
                break
            off_n = l_val + 0.5 * rw
        else:
            if not np.isfinite(r_val):
                break
            off_n = r_val - 0.5 * rw
        if abs(off_n) > 0.45 * rw:
            break
        next_pt = cand + N_dir * off_n
        w_tot = r_val - l_val if (np.isfinite(l_val) and np.isfinite(r_val)) else 99.0
        cur_dir = unit(0.65 * cur_dir + 0.35 * unit(next_pt - cur_pt))
        cur_pt = next_pt
        traced.append(cur_pt.copy())
        if step >= 3 and w_tot <= 1.08 * rw:
            reached = True
            break
    if not reached or len(traced) < 4:
        return P2, False
    new_pts = np.vstack([np.array(traced[::-1]), pts[k_clean + 1:]])
    return (new_pts if end_idx == 0 else new_pts[::-1]), True


def de_flare_branch(P0, P2, L, Rr, N, rw):
    """Where a branch widens on ONE side (1.08*rw < w <= 1.95*rw) because a second stroke merges into it at a shallow angle,
    lock the branch to its unflared ink edge instead of drifting into the merging stroke."""
    w = Rr - L
    flared = np.isfinite(w) & (w > 1.08 * rw) & (w <= 1.95 * rw)
    if not flared.any():
        return P2
    P_out = P2.copy()
    dL = np.abs(L + 0.5 * rw)
    dR = np.abs(Rr - 0.5 * rw)
    use_L = flared & (dL <= 0.15 * rw) & (dR > 0.22 * rw)
    use_R = flared & (dR <= 0.15 * rw) & (dL > 0.22 * rw)
    if use_L.any():
        P_out[use_L] = P0[use_L] + N[use_L] * (L[use_L] + 0.5 * rw)[:, None]
    if use_R.any():
        P_out[use_R] = P0[use_R] + N[use_R] * (Rr[use_R] - 0.5 * rw)[:, None]
    return P_out


def refined_branches(D, S=2):
    """Full tracing stage -> list of dict(pts, w, sj, ej), coords in source pixel-index space."""
    mask = D > 0.5
    if not mask.any():
        return []
    dt = ndi.distance_transform_edt(mask)
    br_raw = skeleton_branches(D, S)
    d_vals = []
    H, W_im = D.shape
    for b in br_raw:
        pts = b["pts"]
        if len(pts) >= 4:
            xs = np.clip(np.round(pts[:, 0]).astype(int), 0, W_im - 1)
            ys = np.clip(np.round(pts[:, 1]).astype(int), 0, H - 1)
            d_vals.append(2.0 * dt[ys, xs])
    w_icon = float(np.percentile(np.concatenate(d_vals), 45)) if d_vals else None

    # Precompute which junctions have a nearly-collinear through-pair (dot < -0.90)
    j_dirs = {}
    for idx_b, b in enumerate(br_raw):
        pts_b = b["pts"]
        if len(pts_b) < 8:
            continue
        if b["sj"] > 0:
            d0 = unit(pts_b[min(len(pts_b) - 1, 24)] - pts_b[min(len(pts_b) - 1, 4)])
            j_dirs.setdefault(b["sj"], []).append((idx_b, d0))
        if b["ej"] > 0:
            d1 = unit(pts_b[max(0, len(pts_b) - 25)] - pts_b[max(0, len(pts_b) - 5)])
            j_dirs.setdefault(b["ej"], []).append((idx_b, d1))
    through_juncs = {}
    for jid, items in j_dirs.items():
        if len(items) >= 3:
            best_pair = None
            best_dot = 1.0
            for a_i in range(len(items)):
                for b_i in range(a_i + 1, len(items)):
                    if items[a_i][0] == items[b_i][0]:
                        continue
                    dt_val = float(items[a_i][1] @ items[b_i][1])
                    if dt_val < best_dot:
                        best_dot = dt_val
                        best_pair = {items[a_i][0], items[b_i][0]}
            if best_dot < -0.90 and best_pair is not None:
                through_juncs[jid] = best_pair

    detached_juncs = set()
    out = []
    for idx_b, b in enumerate(br_raw):
        P = resample(b["pts"], 1.0)
        if len(P) < 4:
            continue
        P2, W = refine_branch(D, P, w_icon=w_icon)
        w = float(np.nanmedian(W)) if np.isfinite(W).any() else (w_icon or 0.0)
        if w <= 0:
            continue
        sj, ej = b["sj"], b["ej"]
        if sj == 0:
            P2[0] = extend_end(D, P2, 0, w / 2)
        if ej == 0:
            P2[-1] = extend_end(D, P2, 1, w / 2)

        if len(P) >= max(14, int(2.2 * w)) and len(P) == len(P2):
            T = _tang(P)
            N = np.c_[-T[:, 1], T[:, 0]]
            t, v = _profile(D, P, N, 22)
            L, Rr = _edges(t, v)
            w_prof = Rr - L

            # 1. Check for a merged double-width run near either end
            wide = np.isfinite(w_prof) & (w_prof >= 1.38 * w) & (w_prof <= 2.35 * w)
            best_run = (0, 0, 0)
            j = 0
            while j < len(wide):
                if not wide[j]:
                    j += 1
                    continue
                m = j
                while m < len(wide) and wide[m]:
                    m += 1
                if m - j > best_run[0]:
                    best_run = (m - j, j, m)
                j = m
            rlen, j0, j1 = best_run
            if rlen >= max(12, int(2.0 * w)) and float(np.nanmax(w_prof[j0:j1])) >= 1.62 * w:
                off_L = gaussian_filter1d(np.where(np.isfinite(L), L + 0.5 * w, 0.0), 2.0, mode="nearest")
                off_R = gaussian_filter1d(np.where(np.isfinite(Rr), Rr - 0.5 * w, 0.0), 2.0, mode="nearest")
                pL = P + N * off_L[:, None]
                pR = P + N * off_R[:, None]

                def straight_dev(pts):
                    ch = pts[-1] - pts[0]
                    cl = float(np.linalg.norm(ch))
                    if cl < 1e-6:
                        return 0.0
                    u = ch / cl
                    return float(np.abs((pts[:, 0] - pts[0, 0]) * u[1] - (pts[:, 1] - pts[0, 1]) * u[0]).max())

                if j0 <= int(0.9 * w) and len(P) - j1 >= int(1.5 * w):
                    ks = min(len(P) - 1, j1 + int(0.4 * w))
                    dev_L = straight_dev(pL[max(2, j0):j1])
                    dev_R = straight_dev(pR[max(2, j0):j1])
                    if min(dev_L, dev_R) <= 0.12 * w and max(dev_L, dev_R) >= 0.25 * w:
                        alpha = np.linspace(1.0, 0.0, ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[0:1], pL[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pR[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        else:
                            wall_pts = np.vstack([P2[0:1], pR[1:ks], P2[ks:ks+1]])
                            curve_pts = np.vstack([alpha * pL[:ks] + (1.0 - alpha) * P2[:ks], P2[ks:]])
                        out.append(dict(pts=curve_pts, w=w, sj=-2, ej=ej))
                        out.append(dict(pts=wall_pts, w=w, sj=sj, ej=-2))
                        continue
                elif len(P) - j1 <= int(0.9 * w) and j0 >= int(1.5 * w):
                    ks = max(0, j0 - int(0.4 * w))
                    dev_L = straight_dev(pL[j0:min(len(P) - 2, j1)])
                    dev_R = straight_dev(pR[j0:min(len(P) - 2, j1)])
                    if min(dev_L, dev_R) <= 0.12 * w and max(dev_L, dev_R) >= 0.25 * w:
                        alpha = np.linspace(0.0, 1.0, len(P) - ks)[:, None]
                        if dev_L < dev_R:
                            wall_pts = np.vstack([P2[ks:ks+1], pL[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pR[ks:]])
                        else:
                            wall_pts = np.vstack([P2[ks:ks+1], pR[ks+1:-1], P2[-1:]])
                            curve_pts = np.vstack([P2[:ks], (1.0 - alpha) * P2[ks:] + alpha * pL[ks:]])
                        out.append(dict(pts=curve_pts, w=w, sj=sj, ej=-2))
                        out.append(dict(pts=wall_pts, w=w, sj=-2, ej=ej))
                        continue

            # 2. Check for acute/tangential junction hook at either end (only when joining a collinear through-pair)
            if sj in through_juncs and idx_b not in through_juncs[sj]:
                P2, ok0 = march_acute_end(D, P2, w_prof, w, 0)
                if ok0:
                    detached_juncs.add(sj)
                    sj = -2
            if ej in through_juncs and idx_b not in through_juncs[ej] and len(P2) == len(w_prof):
                P2, ok1 = march_acute_end(D, P2, w_prof, w, 1)
                if ok1:
                    detached_juncs.add(ej)
                    ej = -2

        out.append(dict(pts=P2, w=w, sj=sj, ej=ej))

    # For any through-junction where the 3rd acute branch was detached, remove the junction centroid pull and one-sided flare on the remaining 2 collinear branches
    for jid in detached_juncs:
        rem = [(i, 0 if b["sj"] == jid else 1) for i, b in enumerate(out) if b["sj"] == jid or b["ej"] == jid]
        if len(rem) == 2:
            for i_o, _ in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                if len(pts_o) >= 8:
                    T_o = _tang(pts_o)
                    N_o = np.c_[-T_o[:, 1], T_o[:, 0]]
                    t_o, v_o = _profile(D, pts_o, N_o, 22)
                    L_o, Rr_o = _edges(t_o, v_o)
                    out[i_o]["pts"] = de_flare_branch(pts_o, pts_o, L_o, Rr_o, N_o, rw_o)
            projs = []
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"]
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    anchor = pts_o[kp]
                    far = pts_o[min(len(pts_o) - 1, kp + max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[0] - anchor))
                else:
                    anchor = pts_o[-1 - kp]
                    far = pts_o[max(0, len(pts_o) - 1 - kp - max(4, int(round(0.8 * rw_o))))]
                    u_dir = unit(anchor - far)
                    dist = float(np.linalg.norm(pts_o[-1] - anchor))
                projs.append(anchor + u_dir * dist)
            mid_j = 0.5 * (projs[0] + projs[1])
            for i_o, e_o in rem:
                pts_o = out[i_o]["pts"].copy()
                rw_o = out[i_o]["w"]
                kp = min(len(pts_o) - 3, max(3, int(round(0.95 * rw_o))))
                if e_o == 0:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[kp]
                else:
                    for s_i in range(kp):
                        a_t = s_i / float(kp)
                        pts_o[-1 - s_i] = (1.0 - a_t) * mid_j + a_t * pts_o[-1 - kp]
                out[i_o]["pts"] = pts_o
    return out



================================================================================
# FILE: linework/doctor.py
================================================================================

"""Doctor engine: compares the rendered vector with the source and issues repair commands.

Checks
  * mismatch regions      concentrated render-vs-source error (soft ink difference, box-filtered)
  * redundant paths       a path whose ink is entirely covered by other paths (duplicate centerline)
  * duplicate tails/runs  stretches of a path lying inside other paths' ink for > ~1 stroke width
  * kinks                 anchors that are almost, but not quite, smooth (tangent break 6-30 deg)
  * rings                 closed paths that are exact ellipses but stored as free-form curves
  * simplify / line snap  needless nodes, nearly-straight segments
"""
from __future__ import annotations
import numpy as np, cv2
from .geom import resample
from .model import Model
from .render import render_gray
from .fitting import draw_stroke
from . import edit as E
from . import topology as T


def ink_of(model: Model):
    g = render_gray(model.svg(), model.width, model.height)
    return (255 - g.astype(np.float32)) / 255


class Doctor:
    def __init__(self, D, sens=6.0, kink_lo=6.0, kink_hi=30.0):
        self.D = np.asarray(D, float)
        self.ref = D > 0.5
        self.sens = sens
        self.kink_lo, self.kink_hi = kink_lo, kink_hi
        self.area = float(self.ref.sum())

    # ---- metrics
    def soft(self, ink):
        return float(np.abs(np.asarray(ink, float) - self.D).sum())

    def iou(self, ink):
        b = ink > 0.5
        return float((b & self.ref).sum() / max((b | self.ref).sum(), 1))

    def regions(self, ink, win=9, merge_d=24):
        m = np.abs(ink - self.D)
        s = cv2.boxFilter(m, -1, (win, win), normalize=False)
        pk = (s >= self.sens).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(pk)
        regs = []
        for i in range(1, n):
            x, y, w, h, _a = st[i]
            regs.append([x - 4, y - 4, x + w + 4, y + h + 4, float(s[lab == i].max())])
        out = []
        for r in sorted(regs, key=lambda r: -r[4]):
            for o in out:
                if r[0] < o[2] + merge_d and r[2] > o[0] - merge_d and r[1] < o[3] + merge_d and r[3] > o[1] - merge_d:
                    o[0], o[1] = min(o[0], r[0]), min(o[1], r[1])
                    o[2], o[3] = max(o[2], r[2]), max(o[3], r[3])
                    o[4] = max(o[4], r[4])
                    break
            else:
                out.append(r)
        return out

    # ---- structural checks
    def _coverage(self, model):
        H, W = self.D.shape
        covs, flats = [], []
        for p in model.paths:
            f = resample(p.flat(), 1.0)
            im = np.zeros((H, W), np.uint8)
            draw_stroke(im, f, p.w, p.join == "miter", 0, 0, p.ml, 1)
            covs.append(im > 0)
            flats.append(f)
        return covs, flats

    def redundancy(self, model):
        from scipy.spatial import cKDTree
        covs, flats = self._coverage(model)
        if not covs:
            return [], []
        count = np.sum(covs, axis=0)
        red, tails = [], []
        for i, (c, f) in enumerate(zip(covs, flats)):
            w = model.paths[i].w
            excl = c & (count == 1)
            ek = cv2.dilate(excl.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            if excl.sum() < max(4, 0.01 * c.sum()):
                red.append(i)
                continue
            other_entries = [(m, flats[m]) for m in range(len(flats)) if m != i and m not in red and len(flats[m]) > 0]
            if other_entries:
                tree_other = cKDTree(np.vstack([fm for _, fm in other_entries]))
                tree_owners = np.concatenate([[m] * len(fm) for m, fm in other_entries])
            else:
                tree_other = None
                tree_owners = None
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, ek.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, ek.shape[0] - 1)
            has = ek[ys, xs]
            k = 0
            while k < len(has):
                if has[k]:
                    k += 1
                    continue
                j = k
                while j < len(has) and not has[j]:
                    j += 1
                # Only true tails at stroke endpoints should ever be cut; interior spans are junctions/crossings
                if (k <= 3 or j >= len(has) - 3) and j - k >= max(0.9 * w, 8):
                    if tree_other is not None:
                        d_cl, idx_cl = tree_other.query(f[k:j])
                        if float(np.median(d_cl)) > 0.32 * w:
                            k = j
                            continue
                        tail_pts = f[k:j]
                        if len(tail_pts) >= 2:
                            v_tail = tail_pts[-1] - tail_pts[0] if (j >= len(has) - 3) else (tail_pts[0] - tail_pts[-1])
                            lv = np.linalg.norm(v_tail)
                            if lv > 1e-4:
                                t_tail = v_tail / lv
                                m_other = int(np.bincount(tree_owners[idx_cl]).argmax())
                                fm = flats[m_other]
                                if len(fm) >= 2:
                                    k_oth = int(np.argmin(np.linalg.norm(fm - tail_pts[len(tail_pts) // 2], axis=1)))
                                    lo_o = max(0, k_oth - 4)
                                    hi_o = min(len(fm) - 1, k_oth + 4)
                                    v_oth = fm[hi_o] - fm[lo_o]
                                    if np.linalg.norm(v_oth) > 1e-4:
                                        t_oth = v_oth / np.linalg.norm(v_oth)
                                        if abs(float(t_tail @ t_oth)) < 0.88:
                                            k = j
                                            continue
                    tails.append((i, k, j - 1))
                k = j
        return red, tails

    def kinks(self, model):
        out = []
        for i, p in enumerate(model.paths):
            for k in range(1, len(p.A) - 1):
                din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a < 1e-6 or b < 1e-6:
                    continue
                ang = np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1)))
                if self.kink_lo < ang < self.kink_hi:
                    out.append((i, k, float(ang)))
        return out

    def rings(self, model):
        out = []
        for i, p in enumerate(model.paths):
            if not p.closed or len(p.segs()) == 4:
                continue
            r = E.fit_ellipse(p.flat())
            if r and r[1] < 0.9:
                out.append(i)
            elif E.robust_ellipse(p.flat(), p.w):
                out.append(i)
        return out

    def snaps(self, model):
        out = []
        for i, p in enumerate(model.paths):
            for c in p.segs():
                ch = c[3] - c[0]
                L = np.linalg.norm(ch)
                if L < 6:
                    continue
                n = np.array([-ch[1], ch[0]]) / L
                dev = max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n))
                off = abs(np.linalg.norm(c[1] - c[0]) - L / 3) + abs(np.linalg.norm(c[2] - c[3]) - L / 3)
                if dev * 0.75 < max(0.35, 0.05 * p.w) and (dev > 1e-3 or off > 0.2):
                    out.append(i)
                    break
        return out

    def sharp_paths(self, model):
        """Paths that contain a deliberate sharp corner and are still round-joined (try miter)."""
        out = []
        for i, p in enumerate(model.paths):
            if p.join != "round":
                continue
            found = False
            for k in range(1, len(p.A) - 1):
                din, dout = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a < 1e-6 or b < 1e-6:
                    continue
                if np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1))) >= 25:
                    out.append(i)
                    found = True
                    break
            if not found and p.closed and len(p.A) >= 3:
                din, dout = p.A[0] - p.Hin[0], p.Hout[0] - p.A[0]
                a, b = np.linalg.norm(din), np.linalg.norm(dout)
                if a >= 1e-6 and b >= 1e-6:
                    if np.degrees(np.arccos(np.clip(din @ dout / (a * b), -1, 1))) >= 25:
                        out.append(i)
        return out

    # ---- full diagnosis
    def diagnose(self, model, ink=None, first_round=False):
        ink = ink_of(model) if ink is None else ink
        red, tails = self.redundancy(model)
        rep = dict(
            iou=self.iou(ink),
            soft=self.soft(ink),
            soft_norm=self.soft(ink) / max(self.area, 1),
            regions=self.regions(ink),
            redundant=red,
            tails=tails,
            kinks=self.kinks(model),
            rings=self.rings(model),
            snaps=self.snaps(model),
            simplify=[i for i, p in enumerate(model.paths) if len(p.segs()) > 3] if first_round else [],
            sharp=self.sharp_paths(model),
            gaps=T.find_gaps(model),
            notches=T.find_notches(model),
            spurs=T.find_spurs(model),
        )
        rep["issues"] = (
            len(rep["regions"]) + len(red) + len(tails) + len(rep["kinks"]) + len(rep["rings"]) + len(rep["snaps"]) + len(rep["simplify"])
            + len(rep["gaps"]) + len(rep["notches"]) + len(rep["spurs"])
        )
        return rep

    @staticmethod
    def commands(rep, max_regions=6):
        """Ordered repair commands. Structural removals go last-index-first so indices stay valid."""
        cmds = []
        for i in sorted(rep["redundant"], reverse=True):
            cmds.append(dict(op="remove_path", path=i, tol=4.0))
        for (i, a, b) in sorted(rep["tails"], key=lambda t: (-t[0], -t[1])):
            if i not in rep["redundant"]:
                cmds.append(dict(op="cut", path=i, a=a, b=b, tol=4.0))
        return cmds

    @staticmethod
    def cosmetic_commands(rep):
        cmds = []
        for (i, e) in sorted(rep["spurs"], key=lambda t: (-t[0], -t[1])):
            cmds.append(dict(op="trim_tail", path=i, end=e, tol=1.0))
        for i in rep["notches"]:
            cmds.append(dict(op="merge_nodes", path=i, tol=1.0))
        for i in rep["rings"]:
            cmds.append(dict(op="circle", path=i, robust=True, tol=1.0))
        for (i, k, ang) in rep["kinks"]:
            cmds.append(dict(op="smooth_anchor", path=i, anchor=k, tol=1.0))
        for i in rep["snaps"]:
            cmds.append(dict(op="line_snap", path=i, tol=1.0))
        for i in rep["simplify"]:
            cmds.append(dict(op="simplify", path=i, err=0.45, tol=1.0))
        for i in rep["sharp"]:
            cmds.append(dict(op="join", path=i, join="miter", tol=2.0))
        if rep["gaps"]:
            cmds.append(dict(op="weld", path=-1, tol=1.0))
        return cmds

    @staticmethod
    def region_commands(rep, max_regions=6):
        regs = sorted(rep["regions"], key=lambda r: -r[4])[:max_regions]
        return [dict(op="refine_region", box=[int(r[0]), int(r[1]), int(r[2]), int(r[3])], tol=-0.5) for r in regs]



================================================================================
# FILE: linework/rings.py
================================================================================

"""Exact circles. Mechanical / icon art is full of rings (hubs, bearings, pins). A skeleton trace breaks a ring wherever
another stroke touches it, and the pieces drift out of round.  Here the rings are found in the *image* (Hough on the
skeleton, then least-squares refinement, then an ink-support test), added as exact closed circles, and the old pieces
that lie on top of them are cut away so every stroke simply ends on the ring.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from skimage.transform import hough_circle, hough_circle_peaks
from .geom import resample
from .model import Model, Path
from . import edit as E


def _kasa(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x * x + y * y
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    r2 = c[2] + c[0] ** 2 + c[1] ** 2
    return float(c[0]), float(c[1]), float(np.sqrt(max(r2, 1e-6)))


def _profile_width(D, cx, cy, r, w, n=72):
    offs = np.arange(-2.5 * w, 2.5 * w + 1e-6, 0.25)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r + offs[None, :]
    xs, ys = cx + rr * np.cos(ang)[:, None], cy + rr * np.sin(ang)[:, None]
    v = ndi.map_coordinates(D, [ys, xs], order=1, mode="constant", cval=0.0)
    mid = len(offs) // 2
    widths, support = [], 0
    for row in v:
        if row[mid] < 0.5:
            continue
        support += 1
        a = b = mid
        while a > 0 and row[a - 1] >= 0.5:
            a -= 1
        while b < len(row) - 1 and row[b + 1] >= 0.5:
            b += 1
        widths.append((b - a + 1) * 0.25)
    if not widths:
        return None, 0.0
    return float(np.median(widths)), support / n


def _fit_ellipse_pts(P, cx, cy, r, w):
    """Least-squares ellipse (cv2.fitEllipse) on skeleton points near the circle; returns (cx, cy, a, b, theta) or None."""
    import cv2
    d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    tol = max(2.0, 0.25 * w, 0.03 * r)
    sel = np.abs(d - r) < tol
    if sel.sum() < 12:
        return None
    pts = P[sel]
    e = None
    for _ in range(3):
        if len(pts) < 8:
            return None
        (ex, ey), (MA, ma), ang = cv2.fitEllipse(pts.astype(np.float32))
        a, b, th = MA / 2, ma / 2, np.radians(ang)
        if min(a, b) < 2:
            return None
        e = (ex, ey, a, b, th)
        A, Hi, Ho = E.ellipse_beziers(np.array([ex, ey]), a, b, th)
        flat = Path(A, Hi, Ho, 1.0, closed=True).flat(0.5)
        from scipy.spatial import cKDTree
        dd = cKDTree(flat).query(P)[0]
        pts = P[dd < tol]
    return e


def detect_rings(D, w, min_support=0.93, max_rings=80):
    """Circles and ellipses found in the image. Returns dicts in SVG coordinates (pixel-edge convention)."""
    mask = D > 0.5
    if mask.sum() < 30:
        return []
    sk = skeletonize(mask)
    skd = ndi.binary_dilation(sk, iterations=1)  # tolerate the skeleton wobbling near junctions
    dt = ndi.distance_transform_edt(mask)
    H, W = D.shape
    rmax = int(min(H, W) / 2)
    rmin = 3
    cand = []
    hs = 2 if rmax > 40 else 1  # coarse grid for big icons: Hough cost grows with (pixels x radii)
    if hs > 1:
        import cv2
        skh = cv2.resize(skd.astype(np.uint8), (W // hs, H // hs), interpolation=cv2.INTER_AREA) > 0
    else:
        skh = skd
    rh = int(min(skh.shape) / 2)
    radii_all = np.arange(max(2, rmin // hs), max(rh, 3))
    radii_all = radii_all[:: (1 if rh <= 60 else 2)]
    for i in range(0, len(radii_all), 6):
        radii = radii_all[i:i + 6]
        acc = hough_circle(skh, radii, normalize=True)
        a, xs, ys, rs = hough_circle_peaks(acc, radii, min_xdistance=2, min_ydistance=2, threshold=0.3, total_num_peaks=40)
        cand += [(aa, xx * hs, yy * hs, rr * hs) for aa, xx, yy, rr in zip(a, xs, ys, rs)]
    cand.sort(key=lambda t: -t[0])
    ys_, xs_ = np.nonzero(sk)
    P = np.c_[xs_, ys_].astype(float)
    out = []
    for a, cx, cy, r in cand:
        cx, cy, r = float(cx), float(cy), float(r)
        for _ in range(3):  # least-squares circle refinement on skeleton points close to the circle
            d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
            sel = np.abs(d - r) < max(2.0, 0.25 * w)
            if sel.sum() < 12:
                break
            cx, cy, r = _kasa(P[sel])
        if r < rmin or r > rmax * 1.1:
            continue
        e = _fit_ellipse_pts(P, cx, cy, r, w)
        if e is None:
            continue
        ex, ey, ea, eb, th = e
        if max(ea, eb) > rmax * 1.2 or max(ea, eb) / max(min(ea, eb), 1e-6) > 1.6:
            continue
        # support + width measured along the fitted centreline
        A, Hi, Ho = E.ellipse_beziers(np.array([ex, ey]), ea, eb, th)
        flat = Path(A, Hi, Ho, 1.0, closed=True).flat(1.0)
        xi = np.clip(np.round(flat[:, 0]).astype(int), 0, W - 1)
        yi = np.clip(np.round(flat[:, 1]).astype(int), 0, H - 1)
        sup = float((D[yi, xi] > 0.5).mean())
        if sup < min_support:
            continue
        ww = float(2 * np.median(dt[yi, xi]))
        if not (0.45 * w <= ww <= 1.8 * w):
            continue
        rr = (ea + eb) / 2
        if any(np.hypot(ex - o["cx"] + 0.5, ey - o["cy"] + 0.5) < 3.0 and abs(rr - o["r"]) < 0.7 * w for o in out):
            continue
        if abs(ea - eb) / max(ea, eb) < 0.015:  # a true circle: keep it exactly round
            ea = eb = rr
        out.append(dict(cx=ex + 0.5, cy=ey + 0.5, a=ea, b=eb, th=th, r=rr, w=ww, support=sup))
        if len(out) >= max_rings:
            break
    return out


def _ring_path(ring):
    A, Hi, Ho = E.ellipse_beziers(np.array([ring["cx"], ring["cy"]]), ring["a"], ring["b"], ring["th"])
    return Path(A, Hi, Ho, ring["w"], closed=True)


def apply_ring(model: Model, ring, clear=0.9):
    """Add the exact ring and cut every older stroke back to its centerline, snapping spoke ends onto the ring."""
    from scipy.spatial import cKDTree
    from . import joints as JN
    rp = _ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]
    cx, cy = ring["cx"], ring["cy"]

    # Refine ring width and center/radius from tangential model segments that lie on this ring
    on_ring_pts = []
    on_ring_ws = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            continue
        d = tree.query(f)[0]
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))
        w_m = max(w, p.w)
        sel = (d < 0.65 * w_m) & (rad_dot < 0.45)
        if sel.sum() >= 6:
            on_ring_pts.append(f[sel])
            on_ring_ws.append((p.w, float(sel.sum())))
    if on_ring_ws:
        w_new = float(sum(pw * lw for pw, lw in on_ring_ws) / sum(lw for _, lw in on_ring_ws))
        ring = dict(ring, w=w_new)
    if on_ring_pts:
        pts_all = np.vstack(on_ring_pts)
        if len(pts_all) >= 16 and abs(ring["a"] - ring["b"]) / max(ring["a"], ring["b"], 1e-6) < 0.02:
            cx_k, cy_k, r_k = _kasa(pts_all)
            if abs(r_k - ring["r"]) < 0.35 * w and np.hypot(cx_k - cx, cy_k - cy) < 0.35 * w:
                ring = dict(ring, cx=cx_k, cy=cy_k, a=r_k, b=r_k, r=r_k)
                cx, cy = cx_k, cy_k

    rp = _ring_path(ring)
    rp_flat = rp.flat(0.25)
    tree = cKDTree(rp_flat)
    w = ring["w"]

    paths = []
    for p in model.paths:
        f = resample(p.flat(), 1.0)
        if len(f) < 4:
            paths.append(p)
            continue
        d, idx = tree.query(f)
        w_m = max(w, p.w)
        if not (d < 0.75 * w_m).any():
            paths.append(p)
            continue
        tang = np.gradient(f, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        r_hat = f - np.array([cx, cy])
        r_hat /= np.linalg.norm(r_hat, axis=1, keepdims=True) + 1e-9
        rad_dot = np.abs((tang * r_hat).sum(1))

        bad = (d < 0.35 * w_m) | ((d < 0.75 * w_m) & (rad_dot < 0.48))
        if not bad.any():
            paths.append(p)
            continue
        if bad.mean() >= 0.82:
            continue
        n_f = len(f)
        lim = max(3, int(round(0.85 * w_m)))
        if not p.closed and not bad[min(lim, n_f):max(min(lim, n_f), n_f - lim)].any():
            q = p.copy()
            if bad[:min(lim, n_f)].any() or d[0] <= 0.65 * w_m:
                JN._set_end(q, 0, rp_flat[int(idx[0])])
            if bad[max(0, n_f - lim):].any() or d[-1] <= 0.65 * w_m:
                JN._set_end(q, 1, rp_flat[int(idx[-1])])
            paths.append(q)
            continue
        if p.closed:
            k = int(np.argmax(bad))
            f, d, bad = np.roll(f, -k, axis=0), np.roll(d, -k), np.roll(bad, -k)
        j = 0
        while j < len(f):
            if bad[j]:
                j += 1
                continue
            k = j
            while k < len(f) and not bad[k]:
                k += 1
            seg = f[j:k]
            if len(seg) >= 4 and (float(d[j:k].max()) >= 0.80 * w_m or (j == 0 and k == len(f))):
                if j > 0:
                    v0 = seg[0] - seg[min(len(seg) - 1, 4)]
                    n0 = float(np.linalg.norm(v0))
                    pt0 = seg[0] + (v0 / n0) * float(d[j]) if n0 > 1e-6 else seg[0]
                    snap0 = rp_flat[int(tree.query(pt0)[1])]
                    seg = np.vstack([[snap0], seg])
                if k < len(f):
                    v1 = seg[-1] - seg[max(0, len(seg) - 5)]
                    n1 = float(np.linalg.norm(v1))
                    pt1 = seg[-1] + (v1 / n1) * float(d[k - 1]) if n1 > 1e-6 else seg[-1]
                    snap1 = rp_flat[int(tree.query(pt1)[1])]
                    seg = np.vstack([seg, [snap1]])
                q = E._refit(seg, p)
                if q:
                    if j > 0:
                        JN._set_end(q, 0, seg[0])
                    if k < len(f):
                        JN._set_end(q, 1, seg[-1])
                    paths.append(q)
            j = k
    paths.append(rp)
    return Model(paths, model.width, model.height)



================================================================================
# FILE: linework/chains.py
================================================================================

"""Junction-aware assembly: trimmed branches -> long continuous centerline chains.

Branches are cut back by ~one stroke width around every junction (the skeleton is distorted there),
then re-linked: collinear ends become one smooth through-stroke, T-stems are extended to the
through-stroke's centreline, and corners/Y-joins meet at the intersection of their end tangents.
"""
from __future__ import annotations
import numpy as np
from .geom import resample, unit, hermite, line_inter


def global_width(branches):
    ws = np.array([b["w"] for b in branches])
    lens = np.array([len(b["pts"]) for b in branches], float)
    m = float(np.median(ws))
    sel = (ws > 0.85 * m) & (ws < 1.15 * m)
    W0 = float(np.average(ws[sel], weights=lens[sel])) if sel.any() else m
    return W0


def build_chains(branches, snap_width=True):
    br = [dict(b) for b in branches]
    for b in br:
        b["pts"] = resample(np.asarray(b["pts"], float), 1.0)
    if not br:
        return [], 0.0
    W0 = global_width(br)
    tol = max(1.3, 0.08 * W0)

    def oriented(b, e):  # points ordered far -> junction end
        return b["pts"] if e == 1 else b["pts"][::-1]

    def end_info(b, e, T, has_free_tip=False):
        q = oriented(b, e)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q[::-1], axis=0), axis=1))]
        n = len(q)
        v_ch = q[-1] - q[0]
        lv_ch = float(np.linalg.norm(v_ch))
        arch_dev = float(np.max(np.abs((q - q[0]) @ (np.array([-v_ch[1], v_ch[0]]) / lv_ch)))) if lv_ch > 1e-3 else 0.0
        if b["sj"] not in (0, -1) and b["ej"] not in (0, -1) and L[-1] < 4.2 * T and arch_dev >= 0.18 * T and n >= 5:
            k = max(n - 3, 2)
            d = unit(q[k] - q[max(k - 5, 0)])
            return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q, is_arch=True)
        if has_free_tip and L[-1] > 1.8 * T and n >= 12:
            k_near = n - 1 - int(np.searchsorted(L, 0.25 * T))
            k_mid  = n - 1 - int(np.searchsorted(L, 0.65 * T))
            k_far  = n - 1 - int(np.searchsorted(L, min(2.2 * T, 0.9 * L[-1])))
            k_near = min(n - 2, max(k_near, k_mid + 2))
            if k_near > k_mid > k_far >= 0:
                d_near = unit(q[k_near] - q[k_mid])
                d_far  = unit(q[k_mid] - q[k_far])
                d_tip  = unit(q[-1] - q[k_near])
                k_vfar = n - 1 - int(np.searchsorted(L, min(2.8 * T, 0.95 * L[-1])))
                straight_before = (k_far > k_vfar + 1) and (d_far @ unit(q[k_far] - q[k_vfar]) > np.cos(np.radians(8)))
                if not straight_before and (d_near @ d_far < np.cos(np.radians(32)) and d_tip @ d_near >= np.cos(np.radians(22))):
                    k = max(n - 1 - int(np.searchsorted(L, 0.35 * T)), 2)
                    return dict(A=q[k].copy(), d=d_near, kept=q[: k + 1], full=q)
        T_eff = min(T, 0.45 * L[-1]) if L[-1] < 2.2 * T else T
        k = n - 1 - int(np.searchsorted(L, T_eff))
        k = max(k, 2)
        step = max(8, int(round(1.35 * T)))
        lo = max(k - step, 0)
        d = unit(q[k] - q[lo]) if k > lo else unit(q[-1] - q[0])
        k_neck = min(n - 2, max(k + 3, n - 1 - int(np.searchsorted(L, 0.35 * T_eff))))
        if L[-1] >= 2.2 * T and k_neck > k and lo >= max(6, step // 2):
            d_prev = unit(q[lo] - q[max(lo - step, 0)])
            d_neck = unit(q[k_neck] - q[k])
            cr_prev = d_prev[0] * d[1] - d_prev[1] * d[0]
            cr_neck = d[0] * d_neck[1] - d[1] * d_neck[0]
            if d_prev @ d < np.cos(np.radians(14)) and d_neck @ d < np.cos(np.radians(14)) and cr_prev * cr_neck > 0:
                return dict(A=q[k_neck].copy(), d=d_neck, kept=q[: k_neck + 1], full=q, is_curve=True)
        return dict(A=q[k].copy(), d=d, kept=q[: k + 1], full=q)

    def is_free_tip(idx):
        b = br[idx]
        return (b["sj"] == 0 or b["ej"] == 0) and len(b["pts"]) < 3.2 * W0

    def is_short_bridge(idx):
        b = br[idx]
        return b["sj"] > 0 and b["ej"] > 0 and len(b["pts"]) < 2.0 * W0

    # Cluster multi-way star/crossing junctions that split into micro-junctions with collinear outer spokes
    raw_ends = {}
    for i, b in enumerate(br):
        if b["sj"] > 0:
            raw_ends.setdefault(b["sj"], []).append((i, 0))
        if b["ej"] > 0:
            raw_ends.setdefault(b["ej"], []).append((i, 1))
    raw_info = {}
    j_xy = {}
    for j, l in raw_ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        j_xy[j] = np.mean([oriented(br[i], e)[-1] for i, e in l], axis=0)
        for (i, e) in l:
            raw_info[(i, e)] = end_info(br[i], e, w)

    par_j = {}
    def find_j(j):
        while par_j.get(j, j) != j:
            par_j[j] = par_j.get(par_j[j], par_j[j])
            j = par_j[j]
        return j

    def has_collinear_cross(j0, j1, skip_ib=-1):
        out0 = [(i, e) for (i, e) in raw_ends.get(j0, []) if i != skip_ib and len(br[i]["pts"]) > 1.5 * W0]
        out1 = [(i, e) for (i, e) in raw_ends.get(j1, []) if i != skip_ib and len(br[i]["pts"]) > 1.5 * W0]
        for a in out0:
            for c in out1:
                if a[0] != c[0]:
                    ta, tc = raw_info[a]["d"], raw_info[c]["d"]
                    ang = np.degrees(np.arccos(np.clip(-ta @ tc, -1, 1)))
                    if ang < 22.0:
                        v = raw_info[c]["A"] - raw_info[a]["A"]
                        nv = np.linalg.norm(v)
                        if nv > 1e-3:
                            u = v / nv
                            ang_c = max(np.degrees(np.arccos(np.clip(ta @ u, -1, 1))), np.degrees(np.arccos(np.clip((-tc) @ u, -1, 1))))
                            if ang_c < 22.0:
                                return True
        return False

    skip_bridges = set()
    cross_j = set()
    j_keys = sorted(raw_ends.keys())
    for a_idx in range(len(j_keys)):
        for b_idx in range(a_idx + 1, len(j_keys)):
            j0, j1 = j_keys[a_idx], j_keys[b_idx]
            w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends[j0] + raw_ends[j1]]))
            if float(np.linalg.norm(j_xy[j0] - j_xy[j1])) <= 1.2 * max(W0, w_b) and has_collinear_cross(j0, j1):
                par_j[find_j(j0)] = find_j(j1)
                cross_j.add(j0)
                cross_j.add(j1)

    for ib, b in enumerate(br):
        j0, j1 = b["sj"], b["ej"]
        if j0 <= 0 or j1 <= 0 or j0 == j1:
            continue
        L_b = len(b["pts"])
        w_b = float(np.mean([br[i]["w"] for i, _ in raw_ends.get(j0, []) + raw_ends.get(j1, [])])) if (j0 in raw_ends and j1 in raw_ends) else W0
        if L_b <= 1.25 * max(W0, w_b) and (has_collinear_cross(j0, j1, ib) or find_j(j0) == find_j(j1) or (L_b <= 0.85 * max(W0, w_b) and (j0 in cross_j or j1 in cross_j))):
            par_j[find_j(j0)] = find_j(j1)
            skip_bridges.add(ib)
    for ib, b in enumerate(br):
        if b["sj"] > 0 and b["ej"] > 0 and find_j(b["sj"]) == find_j(b["ej"]) and len(b["pts"]) <= 2.0 * W0:
            skip_bridges.add(ib)

    ends = {}
    for i, b in enumerate(br):
        if i in skip_bridges:
            continue
        if b["sj"] > 0:
            ends.setdefault(find_j(b["sj"]), []).append((i, 0))
        if b["ej"] > 0:
            ends.setdefault(find_j(b["ej"]), []).append((i, 1))
    info, link, ext = {}, {}, {}
    for j, l in ends.items():
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        T = 1.0 * w
        has_ft = any(br[i]["sj"] == 0 or br[i]["ej"] == 0 for i, _ in l)
        for (i, e) in l:
            info[(i, e)] = end_info(br[i], e, T, has_free_tip=has_ft)

    stair_junc = {}
    bridge_cands = []
    for ib, b in enumerate(br):
        if ib in skip_bridges or not is_short_bridge(ib):
            continue
        j0, j1 = find_j(b["sj"]), find_j(b["ej"])
        if j0 == j1 or len(ends.get(j0, [])) != 3 or len(ends.get(j1, [])) != 3:
            continue
        tips0 = [(i, e) for (i, e) in ends[j0] if i != ib and is_free_tip(i)]
        tips1 = [(i, e) for (i, e) in ends[j1] if i != ib and is_free_tip(i)]
        for a in tips0:
            for c in tips1:
                ta, tc = info[a]["d"], info[c]["d"]
                ang_tips = np.degrees(np.arccos(np.clip(-ta @ tc, -1, 1)))
                if ang_tips > 25:
                    continue
                tb0, tb1 = info[(ib, 0)]["d"], info[(ib, 1)]["d"]
                a0 = np.degrees(np.arccos(np.clip(-ta @ tb0, -1, 1)))
                a1 = np.degrees(np.arccos(np.clip(-tc @ tb1, -1, 1)))
                if max(a0, a1) < 55:
                    bridge_cands.append((a0 + a1 + ang_tips, j0, a, (ib, 0), j1, c, (ib, 1)))
    used_j = set()
    for score, j0, a, b0, j1, c, b1 in sorted(bridge_cands):
        if j0 in used_j or j1 in used_j:
            continue
        used_j.add(j0)
        used_j.add(j1)
        skip_bridges.add(b0[0])
        T1, T2 = info[a]["kept"][0].copy(), info[c]["kept"][0].copy()
        if np.linalg.norm(T2 - T1) < 3.8 * W0 and np.linalg.norm(T2 - T1) > 1e-3:
            u_bar = unit(T2 - T1)
            for tip in (a, c):
                br[tip[0]]["pts"] = T1 + ((br[tip[0]]["pts"] - T1) @ u_bar)[:, None] * u_bar[None, :]
                info[tip]["kept"] = T1 + ((info[tip]["kept"] - T1) @ u_bar)[:, None] * u_bar[None, :]
                info[tip]["A"] = info[tip]["kept"][-1].copy()
        A1, A2 = info[a]["A"], info[c]["A"]
        n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
        pts = np.linspace(A1, A2, n_pts)
        link[a] = (c, pts)
        link[c] = (a, pts[::-1])
        for jx, used_tip in ((j0, a), (j1, c)):
            w_j = float(np.mean([br[i]["w"] for i, _ in ends[jx]]))
            thr = np.vstack([info[a]["kept"], pts, info[c]["kept"][::-1]])
            for o in ends[jx]:
                if o == used_tip or o[0] == b0[0]:
                    continue
                Ao, do = info[o]["A"], info[o]["d"]
                ts = np.arange(0, 4 * w_j, 0.5)
                ray = Ao[None] + do[None] * ts[:, None]
                dist = np.array([np.min(np.linalg.norm(thr - r, axis=1)) for r in ray])
                ext[o] = Ao + do * ts[int(np.argmin(dist))]
    for j0, l in ends.items():
        if j0 in used_j or len(l) != 3:
            continue
        tips0 = [(i, e) for (i, e) in l if is_free_tip(i)]
        if len(tips0) != 1:
            continue
        a = tips0[0]
        others = [(i, e) for (i, e) in l if (i, e) != a]
        free_br = []
        claimed_br = 0
        for i, e in others:
            other_j = find_j(br[i]["ej"] if e == 0 else br[i]["sj"])
            if other_j in used_j:
                claimed_br += 1
            elif is_short_bridge(i):
                ang = np.degrees(np.arccos(np.clip(-info[a]["d"] @ info[(i, e)]["d"], -1, 1)))
                if ang < 55:
                    free_br.append((ang, (i, e)))
        if claimed_br >= 1 and len(free_br) == 1:
            used_j.add(j0)
            stair_junc[j0] = (a, free_br[0][1])
    for ib, b in enumerate(br):
        if is_short_bridge(ib) and find_j(b["sj"]) in used_j and find_j(b["ej"]) in used_j:
            skip_bridges.add(ib)
            for e in (0, 1):
                ext.pop((ib, e), None)
    for j0, l in ends.items():
        if j0 in used_j or len(l) != 3:
            continue
        spurs = [(i, e) for (i, e) in l if (br[i]["sj"] == 0 or br[i]["ej"] == 0) and len(br[i]["pts"]) <= 2.4 * W0]
        if len(spurs) != 1:
            continue
        spur = spurs[0]
        others = [(i, e) for (i, e) in l if (i, e) != spur]
        if len(others) != 2:
            continue
        L_spur_pts = len(br[spur[0]]["pts"])
        a, b = others[0], others[1]
        if others[0][0] == others[1][0]:
            used_j.add(j0)
            skip_bridges.add(spur[0])
            A1, A2 = info[a]["A"], info[b]["A"]
            n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
            pts = np.linspace(A1, A2, n_pts)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
            continue
        if min(len(br[others[0][0]]["pts"]), len(br[others[1][0]]["pts"])) <= 1.3 * L_spur_pts:
            continue
        J_pt = info[spur]["full"][-1]
        T_tip = info[spur]["kept"][0]
        u_spur = unit(T_tip - J_pt) if np.linalg.norm(T_tip - J_pt) > 1e-3 else -info[spur]["d"]
        d1, d2 = info[a]["d"], info[b]["d"]
        cr1 = d1[0] * u_spur[1] - d1[1] * u_spur[0]
        cr2 = d2[0] * u_spur[1] - d2[1] * u_spur[0]
        if d1 @ d2 < -0.65 and L_spur_pts <= 2.2 * W0:
            used_j.add(j0)
            skip_bridges.add(spur[0])
            A1, A2 = info[a]["A"], info[b]["A"]
            n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
            pts = np.linspace(A1, A2, n_pts)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
            continue
        if (
            d1 @ u_spur > np.cos(np.radians(58))
            and d2 @ u_spur > np.cos(np.radians(58))
            and cr1 * cr2 < 0
            and unit(d1 + d2) @ u_spur > np.cos(np.radians(26))
        ):
            used_j.add(j0)
            skip_bridges.add(spur[0])
            A1, A2 = info[a]["A"], info[b]["A"]
            C = line_inter(A1, d1, A2, d2) if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-3 else None
            L_spur = float(np.linalg.norm(T_tip - J_pt))
            w_j = float(np.mean([br[i]["w"] for i, _ in l]))
            if C is not None and (C - A1) @ d1 > 0 and (C - A2) @ d2 > 0:
                proj = float((C - J_pt) @ u_spur)
                max_proj = L_spur + 0.25 * w_j
                V = (J_pt + max_proj * u_spur) if proj > max_proj else (T_tip.copy() if proj < 0.75 * L_spur else C)
            else:
                V = T_tip.copy()
            ext[a] = V
            ext[b] = V

    for j, l in ends.items():
        if j in used_j and j not in stair_junc:
            continue
        w = float(np.mean([br[i]["w"] for i, _ in l]))
        if j in stair_junc:
            a, b = stair_junc[j]
            pair_cands = [(0.0, a, b)]
            allow_staircase = True
        else:
            pair_cands = []
            for x in range(len(l)):
                for y in range(x + 1, len(l)):
                    a, b = l[x], l[y]
                    if a[0] == b[0]:
                        continue
                    if len(l) >= 3 and info[a].get("is_arch") and info[b].get("is_arch"):
                        continue
                    ta, tb = info[a]["d"], info[b]["d"]
                    ang = np.degrees(np.arccos(np.clip(-ta @ tb, -1, 1)))
                    v = info[b]["A"] - info[a]["A"]
                    nv = np.linalg.norm(v)
                    short_stem = min(len(br[a[0]]["pts"]), len(br[b[0]]["pts"])) < 1.2 * w
                    if nv > 0.25 * w and not short_stem:
                        u = v / nv
                        ang_c = max(
                            np.degrees(np.arccos(np.clip(ta @ u, -1, 1))),
                            np.degrees(np.arccos(np.clip((-tb) @ u, -1, 1))),
                        )
                        eff_ang = max(ang, 0.85 * ang_c)
                    else:
                        eff_ang = ang
                    pair_cands.append((eff_ang, a, b))
            pair_cands.sort(key=lambda t: t[0])
            allow_staircase = False
        if len(l) == 2 and pair_cands:
            ang, a, b = pair_cands[0]
            A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
            if ang < 28:
                pts = hermite(A1, d1, A2, d2)
            else:
                C = line_inter(A1, d1, A2, d2) if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-3 else None
                cen = np.mean([info[a]["full"][-1], info[b]["full"][-1]], axis=0)
                if C is not None and np.linalg.norm(C - cen) < 3 * w and (C - A1) @ d1 > -2 and (C - A2) @ d2 > -2:
                    n1 = max(2, int(np.linalg.norm(C - A1)) + 1)
                    n2 = max(2, int(np.linalg.norm(A2 - C)) + 1)
                    pts = np.vstack([np.linspace(A1, C, n1), np.linspace(C, A2, n2)[1:]])
                else:
                    pts = hermite(A1, d1, A2, d2)
            link[a] = (b, pts)
            link[b] = (a, pts[::-1])
        elif len(l) >= 3 and pair_cands and (pair_cands[0][0] < 28 or allow_staircase):
            used = set()
            linked_pairs = []
            for eff_ang, a, b in pair_cands:
                if eff_ang >= 28.0 and not (allow_staircase and not linked_pairs):
                    break
                if a in used or b in used:
                    continue
                used.add(a)
                used.add(b)
                linked_pairs.append((eff_ang, a, b))
                if allow_staircase:
                    break
            thr_list = []
            for eff_ang, a, b in linked_pairs:
                A1, d1, A2, d2 = info[a]["A"], info[a]["d"], info[b]["A"], info[b]["d"]
                if len(linked_pairs) >= 2 and eff_ang < 15.0:
                    n_pts = max(2, int(np.linalg.norm(A2 - A1)) + 1)
                    pts = np.linspace(A1, A2, n_pts)
                else:
                    pts = hermite(A1, d1, A2, d2)
                link[a] = (b, pts)
                link[b] = (a, pts[::-1])
                thr_list.append(np.vstack([info[a]["kept"][-int(2 * w):], pts, info[b]["kept"][-int(2 * w):][::-1]]))
            thr = np.vstack(thr_list)
            for o in l:
                if o in used:
                    continue
                A, d = info[o]["A"], info[o]["d"]
                ts = np.arange(0, 4 * w, 0.5)
                ray = A[None] + d[None] * ts[:, None]
                dist = np.array([np.min(np.linalg.norm(thr - r, axis=1)) for r in ray])
                ext[o] = A + d * ts[int(np.argmin(dist))]
        else:
            cen = np.mean([info[o]["full"][-1] for o in l], axis=0)
            if any(info[o].get("is_arch") or info[o].get("is_curve") for o in l):
                C = cen
            else:
                M = np.zeros((2, 2))
                v = np.zeros(2)
                for o in l:
                    d = info[o]["d"]
                    Pm = np.eye(2) - np.outer(d, d)
                    M += Pm
                    v += Pm @ info[o]["A"]
                try:
                    C = np.linalg.solve(M, v)
                except Exception:
                    C = cen
                if np.linalg.norm(C - cen) > 0.65 * w or any((C - info[o]["A"]) @ info[o]["d"] < 0 for o in l):
                    C = cen
            for o in l:
                ext[o] = C

    nb = len(br)

    def body(i, e_start):
        pts = br[i]["pts"]
        lo, hi = 0, len(pts) - 1
        if (i, 0) in info:
            lo = int(np.argmin(np.linalg.norm(pts - info[(i, 0)]["A"], axis=1)))
        if (i, 1) in info:
            hi = int(np.argmin(np.linalg.norm(pts - info[(i, 1)]["A"], axis=1)))
        q = pts[lo : hi + 1] if hi > lo else pts[lo : lo + 2]
        return q if e_start == 0 else q[::-1]

    def ext_pts(key, toward_junction):
        A, E = info[key]["A"], ext[key]
        n = max(2, int(np.linalg.norm(E - A)) + 1)
        seg = np.linspace(A, E, n)
        return seg[1:] if toward_junction else seg[::-1][:-1]

    seen = set(skip_bridges)
    final, widths = [], []

    def build(i, es):
        parts, cur, e, wsum, wn = [], i, es, 0.0, 0
        if (cur, e) in info and (cur, e) in ext:
            parts.append(ext_pts((cur, e), False))
        while True:
            seen.add(cur)
            q = body(cur, e)
            parts.append(q)
            wsum += br[cur]["w"] * len(q)
            wn += len(q)
            te = 1 - e
            key = (cur, te)
            if key in link:
                (j, e2), bp = link[key]
                parts.append(bp[1:-1] if len(bp) > 2 else bp[:0])
                if j in seen:
                    break
                cur, e = j, e2
                continue
            if key in info and key in ext:
                parts.append(ext_pts(key, True))
            break
        return np.vstack(parts), wsum / max(wn, 1)

    for i in range(nb):
        if i in seen:
            continue
        for es in (0, 1):
            if (i, es) not in link:
                P, w = build(i, es)
                final.append(P)
                widths.append(w)
                break
    for i in range(nb):
        if i not in seen:
            P, w = build(i, 0)
            final.append(P)
            widths.append(w)
    out = []
    for P, w in zip(final, widths):
        if snap_width and abs(w - W0) < tol:
            w = W0
        out.append(dict(pts=resample(P, 1.0), w=float(w)))
    return out, W0



================================================================================
# FILE: linework/fitting.py
================================================================================

"""Initial model construction: chain polylines -> smooth Bezier paths with reconstructed sharp corners."""
from __future__ import annotations
import numpy as np, cv2
from .geom import resample, corners, linefit, line_inter, smooth, fit_curve
from .model import Model, Path

SS = 4


def draw_stroke(im, pts, w, miter, x0, y0, ml=8.0, ss=SS):
    """Rasterise a polyline stroke (round caps, round or miter joins) into `im` (uint8, scale ss)."""
    P = (pts - [x0, y0]) * ss
    r = w * ss / 2
    for a, b in zip(P[:-1], P[1:]):
        d = b - a
        n = np.linalg.norm(d)
        if n < 1e-6:
            continue
        d = d / n
        nn = np.array([-d[1], d[0]]) * r
        cv2.fillPoly(im, [np.round(np.array([a + nn, b + nn, b - nn, a - nn]) * 16).astype(np.int32)], 1, shift=4)
    for e in (P[0], P[-1]):
        cv2.circle(im, tuple(np.round(e).astype(int)), int(round(r)), 1, -1)
    for j in range(1, len(P) - 1):
        a, c, b = P[j - 1], P[j], P[j + 1]
        d1, d2 = c - a, b - c
        n1, n2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        d1, d2 = d1 / n1, d2 / n2
        cr = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cr) < 0.017 and d1 @ d2 > 0:
            continue
        if not miter:
            cv2.circle(im, tuple(np.round(c).astype(int)), int(round(r)), 1, -1)
            continue
        sg = -1 if cr > 0 else 1
        n1v = np.array([-d1[1], d1[0]]) * sg * r
        n2v = np.array([-d2[1], d2[0]]) * sg * r
        bis = n1v + n2v
        bl = np.linalg.norm(bis)
        if bl < 1e-6:
            continue
        ch = (bl / 2) / r
        mt = c + bis / bl * (r / ch) if ch > 1 / ml else None
        poly = [c, c + n1v, c + n2v] if mt is None else [c, c + n1v, mt, c + n2v]
        cv2.fillPoly(im, [np.round(np.array(poly) * 16).astype(np.int32)], 1, shift=4)


class CornerSolver:
    """Chooses, per detected corner, the best of {keep skeleton corner, extended/mitred corner}
    by rasterising candidates against the source ink map."""

    def __init__(self, D):
        self.D = D

    def local_cost(self, cands, w, center, rad):
        H, W = self.D.shape
        x0 = max(int(center[0] - rad), 0)
        y0 = max(int(center[1] - rad), 0)
        n = int(2 * rad)
        crop = self.D[y0 : y0 + n, x0 : x0 + n]
        if crop.size == 0:
            return [0] * len(cands)
        ref = cv2.resize(crop, None, fx=SS, fy=SS, interpolation=cv2.INTER_CUBIC) > 0.5
        rs = []
        for pts, miter in cands:
            im = np.zeros(ref.shape, np.uint8)
            draw_stroke(im, pts, w, miter, x0, y0)
            rs.append(im > 0)
        U = np.zeros(ref.shape, np.uint8)
        for r in rs:
            U |= r.astype(np.uint8)
        U = cv2.dilate(U, np.ones((SS * 4 + 1,) * 2, np.uint8)) > 0
        return [int(((r ^ ref) & U).sum()) for r in rs]

    def pieces(self, p, w):
        r = w / 2
        cs = corners(p, win=7, ang=35)
        out, cur = [], 0
        for i in cs:
            k = int(round(r * 1.1))
            a, b = i - k, i + k
            if b + 3 >= len(p) or a < 1:
                continue
            if a - 3 < cur:
                # corners packed closer than a stroke width (fine gear teeth): too tight to solve, but still keep them sharp
                if i - cur > 3:
                    out.append(("curve", p[cur : i + 1]))
                    cur = i
                continue
            ctx = int(3 * r)
            base = p[max(0, i - ctx) : i + ctx + 1]
            Cs = []
            if a - 14 >= cur and b + 14 < len(p):
                c1, d1, r1 = linefit(p[a - 14 : a])
                c2, d2, r2 = linefit(p[b : b + 14])
                if r1 < 0.5 and r2 < 0.5:
                    if d1 @ (p[a] - p[a - 14]) < 0:
                        d1 = -d1
                    if d2 @ (p[b + 13] - p[b]) < 0:
                        d2 = -d2
                    if np.degrees(np.arccos(np.clip(d1 @ d2, -1, 1))) >= 30:
                        C = line_inter(c1, d1, c2, d2)
                        if C is not None and np.linalg.norm(C - p[i]) < 3 * r:
                            for al in (0.4, 0.7, 1.0, 1.15):
                                Cs.append(p[i] + al * (C - p[i]))
            m = (p[i - 7] + p[i + 7]) / 2
            u = p[i] - m
            nu = np.linalg.norm(u)
            if nu > 1e-6:
                u = u / nu
                for s in (0, 1.5, 3.0, 5.0):
                    Cs.append(p[i] + u * s)
            cands = [(base, False), (base, True)]
            meta = [None, None]
            vin_base = p[i] - p[a]
            vout_base = p[b] - p[i]
            l_in_b, l_out_b = np.linalg.norm(vin_base), np.linalg.norm(vout_base)
            base_turn = float((vin_base / max(l_in_b, 1e-6)) @ (vout_base / max(l_out_b, 1e-6)))

            for C in Cs:
                v_in = C - p[a]
                v_out = p[b] - C
                l_in, l_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
                if l_in > 1e-3 and l_out > 1e-3:
                    cos_turn = float((v_in / l_in) @ (v_out / l_out))
                    if (cos_turn < -0.3 and base_turn > -0.2) or (cos_turn < base_turn - 0.35):
                        continue
                line = np.vstack([p[max(0, i - ctx) : a + 1], C, p[b : i + ctx + 1]])
                for mi in (False, True):
                    cands.append((line, mi))
                    meta.append((C, mi))
            costs = self.local_cost(cands, w, p[i], 4 * r)
            j = int(np.argmin(costs))
            if costs[j] >= min(costs[0], costs[1]) - 4:
                continue
            C, mi = meta[j]
            out.append(("curve", p[cur : a + 1]))
            n1 = max(2, int(np.linalg.norm(C - p[a])))
            out.append(("line", np.linspace(p[a], C, n1 + 1)))
            n2 = max(2, int(np.linalg.norm(p[b] - C)))
            out.append(("line", np.linspace(C, p[b], n2 + 1)))
            cur = b
        out.append(("curve", p[cur:]))
        return out


def initial_model(chains, D, sigma=2.0, err=0.3, dw=0.1) -> Model:
    """chains: list of dict(pts in source pixel-index coords, w). Returns Model in svg coords."""
    solver = CornerSolver(D)
    paths = []
    for c in chains:
        p = resample(np.asarray(c["pts"], float) + 0.5, 1.0)
        if len(p) < 4:
            continue
        closed = (
            len(p) >= max(12, int(2.6 * c["w"]))
            and np.linalg.norm(p[0] - p[-1]) < 0.6 * c["w"]
            and np.linalg.norm(p - p[0], axis=1).max() >= 0.75 * c["w"]
        )
        if closed:
            p[-1] = p[0]
        segs = []
        for kind, q in solver.pieces(p, c["w"]):
            if len(q) < 2:
                continue
            if kind == "curve":
                segs += fit_curve(q, sigma, err)
            else:
                segs.append(np.array([q[0], q[0] + (q[-1] - q[0]) / 3, q[0] + 2 * (q[-1] - q[0]) / 3, q[-1]]))
        if not segs:
            continue
        paths.append(Path.from_segs(segs, c["w"] + dw, closed=closed))
    H, W = D.shape
    return Model(paths, W, H)


def add_dots(model: Model, D, min_frac=0.25):
    """Compact ink blobs left uncovered by the traced strokes (dots, i-dots, noses) become zero-length round-capped strokes."""
    import cv2 as _cv2
    from .render import render_gray
    g = render_gray(model.svg(), model.width, model.height) if model.paths else np.full(D.shape, 255, np.uint8)
    covered_raw = (g < 128).astype(np.uint8)
    covered = _cv2.dilate(covered_raw, np.ones((3, 3), np.uint8))
    src_mask = (D > 0.5).astype(np.uint8)
    _, src_lab, src_st, _ = _cv2.connectedComponentsWithStats(src_mask)
    resid = src_mask & (1 - covered)
    n, lab, st, ce = _cv2.connectedComponentsWithStats(resid)
    ws = [p.w for p in model.paths] or [8.0]
    w0 = float(np.median(ws))
    added = 0
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a < min_frac * np.pi * (w0 / 2) ** 2 or max(bw, bh) > 1.8 * w0 or a < 0.5 * bw * bh:
            continue
        # Never add a fake dot on an uncovered corner tip of a large connected stroke component
        cy_i, cx_i = int(round(ce[i][1])), int(round(ce[i][0]))
        if 0 <= cy_i < src_lab.shape[0] and 0 <= cx_i < src_lab.shape[1]:
            sl = src_lab[cy_i, cx_i]
            if sl > 0 and src_st[sl, _cv2.CC_STAT_AREA] > 3.5 * w0 * w0:
                continue
        c = ce[i] + 0.5
        diam = float(2 * np.sqrt(a / np.pi))
        A = np.array([c, c + [0.05, 0.0]])
        model.paths.append(Path(A, A.copy(), A.copy(), max(diam, 2.0)))
        added += 1
    return added



================================================================================
# FILE: linework/joints.py
================================================================================

"""Join engine: every joint is built carefully, then a Join Checker inspects each joint on its own; a joint that fails is repaired with one of
three tools (named after the vector-editor tools they imitate) and re-checked.  Only a joint that passes (or at least fails fewer checks) is kept,
and every repair is also verified against the source (match must not get worse, no new gap / notch / spur).

Joint = a place where strokes meet:  T (a stroke ends on another stroke), L/Y (several strokes end at the same point), X (crossing, not repaired).

Join Checker (per joint)
  touch   every stroke end lies exactly on the centreline it joins (T) / on the common point (L)         tol  0.5 px + 4 % w
  hook    no end bends or jogs away from its own straight stroke in its last 1.4 w
  nub     no round cap sticks out of the stroke it ends in
  ink     no lump (render-only ink) and no hole (source-only ink) within 2 w of the joint
  nodes   no two anchors of one stroke closer than 0.4 px at the joint

Tools
  pen      Add / Delete / Convert anchor:  add an anchor on the through-stroke at the joint, put the end exactly on it, delete duplicate anchors,
           make a 2-stroke corner one stroke with a corner node
  line     Line / Arc tool: replace the last 1.4 w of an end by a straight run (line) or by a run that keeps the stroke's tangent (arc), ending on the joint;
           for L joints the ends meet in the intersection of their own directions
  shape    Shape Builder: re-trace the source inside the joint region, replace the strokes lying inside it, weld
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from scipy.spatial import cKDTree
from .model import Model, Path
from .geom import unit
from . import finisher as FN
from . import topology as T


@dataclass
class Joint:
    kind: str
    xy: np.ndarray
    ends: list = field(default_factory=list)  # [(path, end)]
    through: list = field(default_factory=list)  # [path]
    w: float = 10.0


# ------------------------------------------------------------------ find
def find_joints(m: Model):
    ends = [(i, e, (p.A[0] if e == 0 else p.A[-1]), p.w) for i, p in enumerate(m.paths) if not p.closed and len(p.A) >= 2 for e in (0, 1)]
    if not ends:
        return []
    pts, own = [], []
    for j, p in enumerate(m.paths):
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    P = np.vstack(pts)
    own = np.array(own)
    tree = cKDTree(P)
    n = len(ends)
    E = np.array([x[2] for x in ends])
    wmax = max(x[3] for x in ends)

    def _out_tangent(i, e):
        p = m.paths[i]
        if len(p.A) < 2:
            return np.array([1.0, 0.0])
        v = (p.A[0] - p.Hout[0]) if e == 0 else (p.A[-1] - p.Hin[-1])
        if np.linalg.norm(v) < 1e-5:
            v = (p.A[0] - p.A[1]) if e == 0 else (p.A[-1] - p.A[-2])
        nv = np.linalg.norm(v)
        return v / nv if nv > 1e-5 else np.array([1.0, 0.0])

    tangs = [_out_tangent(x[0], x[1]) for x in ends]

    def is_interior(j_path, pt, w_ref):
        qp = m.paths[j_path]
        if qp.closed:
            return True
        return min(float(np.linalg.norm(pt - qp.A[0])), float(np.linalg.norm(pt - qp.A[-1]))) > 0.65 * min(w_ref, qp.w)

    on_thr = [False] * n
    for k, (pi, pe, pt, pw) in enumerate(ends):
        idxs = tree.query_ball_point(pt, 0.30 * pw)
        if any(own[q] != pi and is_interior(int(own[q]), pt, pw) for q in idxs):
            on_thr[k] = True

    par = list(range(n))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a, b in cKDTree(E).query_pairs(0.85 * wmax):
        if ends[a][0] == ends[b][0]:
            continue
        cos_t = tangs[a] @ tangs[b]
        den = abs(tangs[a][0] * tangs[b][1] - tangs[a][1] * tangs[b][0])
        if cos_t > 0.65 and den < 0.15:
            continue
        d_ab = float(np.linalg.norm(E[a] - E[b]))
        w_min = min(ends[a][3], ends[b][3])
        w_max = max(ends[a][3], ends[b][3])
        if w_max > 1.8 * w_min:
            continue
        limit = 0.30 * w_min if (on_thr[a] and on_thr[b]) else 0.85 * w_min
        if d_ab <= limit:
            par[f(a)] = f(b)

    groups = {}
    for k in range(n):
        groups.setdefault(f(k), []).append(k)
    out = []
    for g in groups.values():
        members = [(ends[k][0], ends[k][1]) for k in g]
        pts_g = np.array([ends[k][2] for k in g])
        mids = pts_g.mean(axis=0)
        w = float(np.mean([ends[k][3] for k in g]))
        mem_paths = {i for i, _ in members}
        thr = set()
        if len(g) >= 2:
            for q_idx in tree.query_ball_point(mids, 0.45 * w):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and is_interior(j_path, mids, w) and _nearest_on(m.paths[j_path], mids)[1] <= 0.35 * min(w, m.paths[j_path].w):
                    thr.add(j_path)
        else:
            k = g[0]
            pt, pw = ends[k][2], ends[k][3]
            for q_idx in tree.query_ball_point(pt, 0.45 * pw):
                j_path = int(own[q_idx])
                if j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, pt, pw):
                    if _nearest_on(m.paths[j_path], pt)[1] <= 0.35 * min(pw, m.paths[j_path].w):
                        thr.add(j_path)
            if not thr:
                s_steps = np.arange(-0.55 * pw, 0.85 * pw, 0.25)
                ray = pt[None, :] + s_steps[:, None] * tangs[k][None, :]
                d_ray, idx_ray = tree.query(ray)
                order = np.argsort(np.abs(s_steps))
                for m_idx in order:
                    dr, ir = float(d_ray[m_idx]), int(idx_ray[m_idx])
                    j_path = int(own[ir])
                    if dr <= 0.25 * min(pw, m.paths[j_path].w) and j_path not in mem_paths and pw <= 1.8 * m.paths[j_path].w and is_interior(j_path, P[ir], pw):
                        thr.add(j_path)
                        break
        if len(g) >= 3 and not thr:
            out.append(Joint("Y", mids, members, sorted(mem_paths), w))
        elif len(g) >= 2 and not thr:
            out.append(Joint("L", mids, members, [], w))
        elif thr:
            out.append(Joint("T" if len(g) == 1 else "Y", mids, members, sorted(thr), w))
    return out


# ------------------------------------------------------------------ small vector-editor operations
def _end_pt(p: Path, e):
    return p.A[0] if e == 0 else p.A[-1]


def _set_end(p: Path, e, X):
    X = np.asarray(X, float)
    if e == 0:
        if len(p.A) > 2 and np.linalg.norm(p.A[1] - p.A[0]) < 1.2 * p.w:
            v_next = p.A[1] - p.A[2]
            if np.linalg.norm(p.A[1] - X) < 0.45 * p.w or (np.linalg.norm(v_next) > 1e-4 and (X - p.A[1]) @ v_next < 0):
                p.A = p.A[1:]
                p.Hin = p.Hin[1:]
                p.Hout = p.Hout[1:]
        seg0 = np.array([p.A[0], p.Hout[0], p.Hin[1], p.A[1]])
        was_str = FN._straight(seg0, 1.0)
        d = X - p.A[0]
        p.A[0] = X.copy()
        p.Hin[0] = X.copy()
        if was_str or np.linalg.norm(p.Hout[0] - p.A[0]) < 0.2 * p.w or (len(p.A) >= 2 and np.linalg.norm(p.Hout[0] - (p.A[0] + (p.A[1] - p.A[0]) / 3.0)) < 0.35 * p.w):
            v = p.A[1] - p.A[0]
            p.Hout[0] = p.A[0] + v / 3.0
            p.Hin[1] = p.A[0] + 2.0 * v / 3.0
        else:
            p.Hout[0] += d
    else:
        if len(p.A) > 2 and np.linalg.norm(p.A[-1] - p.A[-2]) < 1.2 * p.w:
            v_prev = p.A[-2] - p.A[-3]
            if np.linalg.norm(p.A[-2] - X) < 0.45 * p.w or (np.linalg.norm(v_prev) > 1e-4 and (X - p.A[-2]) @ v_prev < 0):
                p.A = p.A[:-1]
                p.Hin = p.Hin[:-1]
                p.Hout = p.Hout[:-1]
        seg_last = np.array([p.A[-2], p.Hout[-2], p.Hin[-1], p.A[-1]])
        was_str = FN._straight(seg_last, 1.0)
        d = X - p.A[-1]
        p.A[-1] = X.copy()
        p.Hout[-1] = X.copy()
        if was_str or np.linalg.norm(p.Hin[-1] - p.A[-1]) < 0.2 * p.w or (len(p.A) >= 2 and np.linalg.norm(p.Hin[-1] - (p.A[-1] - (p.A[-1] - p.A[-2]) / 3.0)) < 0.35 * p.w):
            v = p.A[-1] - p.A[-2]
            p.Hout[-2] = p.A[-2] + v / 3.0
            p.Hin[-1] = p.A[-2] + 2.0 * v / 3.0
        else:
            p.Hin[-1] += d


def _nearest_on(p: Path, X):
    f = p.flat(0.25)
    k = int(np.argmin(np.linalg.norm(f - X, axis=1)))
    return f[k], float(np.linalg.norm(f[k] - X))


def insert_anchor(p: Path, X, snap=0.6):
    """Add Anchor Point tool: put an anchor on stroke p at the point nearest X (shape unchanged). Returns the anchor index."""
    best = None
    for k, c in enumerate(p.segs()):
        t = np.linspace(0, 1, 60)
        mt = 1 - t
        Q = (mt**3)[:, None] * c[0] + (3 * mt**2 * t)[:, None] * c[1] + (3 * mt * t**2)[:, None] * c[2] + (t**3)[:, None] * c[3]
        d = np.linalg.norm(Q - X, axis=1)
        j = int(np.argmin(d))
        if best is None or d[j] < best[0]:
            best = (d[j], k, float(t[j]), Q[j])
    _, k, t, Pt = best
    c = p.segs()[k]
    dt = 1.0 / 60
    for _ in range(4):  # refine the parameter: the 60-sample grid alone puts the anchor up to ~1 px off
        tt = np.clip(np.linspace(t - dt, t + dt, 21), 0, 1)
        mt = 1 - tt
        Q = (mt**3)[:, None] * c[0] + (3 * mt**2 * tt)[:, None] * c[1] + (3 * mt * tt**2)[:, None] * c[2] + (tt**3)[:, None] * c[3]
        j = int(np.argmin(np.linalg.norm(Q - X, axis=1)))
        t, Pt, dt = float(tt[j]), Q[j], dt / 5
    for idx in (k, k + 1):  # already (almost) an anchor?
        if np.linalg.norm(p.A[idx] - Pt) < snap:
            return idx
    c = p.segs()[k]
    a, b, cc, d = c
    ab, bc, cd = a + (b - a) * t, b + (cc - b) * t, cc + (d - cc) * t
    abc, bcd = ab + (bc - ab) * t, bc + (cd - bc) * t
    P = abc + (bcd - abc) * t
    p.A = np.insert(p.A, k + 1, P, axis=0)
    p.Hin = np.insert(p.Hin, k + 1, abc, axis=0)
    p.Hout = np.insert(p.Hout, k + 1, bcd, axis=0)
    p.Hout[k] = ab
    p.Hin[k + 2] = cd
    return k + 1


def delete_duplicate_anchors(p: Path, tol=0.4):
    """Delete Anchor Point tool: drop an anchor that sits within tol of its neighbour."""
    eff_tol = max(tol, 0.22 * p.w if p.w > 0 else tol)
    keep = [0]
    for k in range(1, len(p.A)):
        if np.linalg.norm(p.A[k] - p.A[keep[-1]]) < eff_tol and k < len(p.A) - 1:
            continue
        keep.append(k)
    if p.closed and len(keep) > 3 and np.linalg.norm(p.A[keep[-1]] - p.A[0]) < eff_tol:
        keep.pop()
        keep.append(len(p.A) - 1)
    if len(keep) == len(p.A) or len(keep) < 2:
        res = p
    else:
        res = Path(p.A[keep], p.Hin[keep], p.Hout[keep], p.w, p.join, p.ml, p.closed)
    from .topology import prune_apex_overshoot
    return prune_apex_overshoot(res)


# ------------------------------------------------------------------ Join Checker
def check_joint(m: Model, J: Joint, extra=None, missing=None):
    """Returns the list of failed checks (empty = the joint is clean)."""
    bad = []
    w = J.w
    tol = max(0.35, 0.03 * w)
    mem = {i for i, _ in J.ends}
    ext_thr = [j for j in J.through if j not in mem]
    # touch
    if J.kind in ("T", "Y") and ext_thr:
        for (i, e) in J.ends:
            end = _end_pt(m.paths[i], e)
            dmin = min(_nearest_on(m.paths[j], end)[1] for j in ext_thr)
            if dmin > tol:
                bad.append("touch")
                break
    else:
        pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
        if np.linalg.norm(pts - pts.mean(0), axis=1).max() > tol:
            bad.append("touch")
    # hook / nub
    for (i, e) in J.ends:
        p = m.paths[i]
        g = FN.end_geometry(p, e)
        if g is not None:
            c, t, ang, end_pt, dev = g
            is_hook = (ang >= 20.0 and dev >= max(1.0, 0.15 * p.w)) or (ang >= 35.0) or (dev >= 0.25 * p.w)
            if is_hook and FN._straight_before_end(p, e, t):
                bad.append("hook")
                break
    for (i, e) in J.ends:
        p = m.paths[i]
        a, b = FN._end_info(p, e)
        if FN._protrusion(m, i, a, p.w, b) > 0.18 * p.w:
            bad.append("nub")
            break
    # ink around the joint
    if extra is not None:
        r = int(1.2 * w)
        x0, y0 = int(max(J.xy[0] - r, 0)), int(max(J.xy[1] - r, 0))
        x1, y1 = int(min(J.xy[0] + r + 1, extra.shape[1])), int(min(J.xy[1] + r + 1, extra.shape[0]))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        circ = (xx - J.xy[0])**2 + (yy - J.xy[1])**2 <= (1.1 * w)**2
        if extra[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("lump")
        if missing[y0:y1, x0:x1][circ].sum() > 0.35 * w * w:
            bad.append("hole")
    # duplicate nodes
    for i in {i for i, _ in J.ends}:
        A = m.paths[i].A
        if len(A) > 2 and (np.linalg.norm(np.diff(A, axis=0), axis=1) < 0.4).any():
            bad.append("nodes")
            break
    return bad


def _ink_maps(ink, D):
    return ((ink > 0.5) & (D < 0.3)).astype(np.float32), ((ink < 0.5) & (D > 0.5)).astype(np.float32)


# ------------------------------------------------------------------ tools
def tool_pen(m: Model, J: Joint, merge_l=True):
    m = m.copy()
    mem = {i for i, _ in J.ends}
    ext_thr = [j for j in J.through if j not in mem]
    if J.kind in ("T", "Y") and ext_thr:
        for (i, e) in J.ends:
            if i >= len(m.paths):
                continue
            p = m.paths[i]
            end = _end_pt(p, e)
            g = FN.end_geometry(p, e)
            t = g[1] if g is not None else None
            best = None
            for j in ext_thr:
                if j >= len(m.paths) or j == i:
                    continue
                q = m.paths[j]
                X_cand, d_cand = _nearest_on(q, end)
                if t is not None and (d_cand > 0.15 * min(p.w, q.w) or FN._straight_before_end(p, e, t)):
                    s_steps = np.arange(-0.85 * J.w, min(1.8 * J.w, 20.0), 0.25)
                    ray = end[None, :] + s_steps[:, None] * t[None, :]
                    f = q.flat(0.25)
                    tree_q = cKDTree(f)
                    d_ray, idx_ray = tree_q.query(ray)
                    min_idx = int(np.argmin(d_ray))
                    if d_ray[min_idx] < 0.35 * min(p.w, q.w):
                        X_ray = f[idx_ray[min_idx]]
                        if float(np.linalg.norm(X_ray - end)) <= 1.25 * J.w:
                            X_cand = X_ray
                            d_cand = float(np.linalg.norm(X_cand - end))
                if best is None or d_cand < best[2]:
                    best = (j, X_cand, d_cand)
            if best is None or best[2] > 1.5 * J.w:
                continue
            j, X, d = best
            q = m.paths[j]
            if q.closed and len(q.A) == 4 and np.linalg.norm((q.A[0] + q.A[2]) - (q.A[1] + q.A[3])) < 0.25:
                X, _ = _nearest_on(q, X)
            else:
                k = insert_anchor(q, X)
                X = q.A[k].copy()
            _set_end(p, e, X)
    else:
        if len(J.ends) == 2 and J.ends[0][0] != J.ends[1][0]:
            (i1, e1), (i2, e2) = J.ends[0], J.ends[1]
            g1 = FN.end_geometry(m.paths[i1], e1)
            g2 = FN.end_geometry(m.paths[i2], e2)
            c1, t1 = (g1[0], g1[1]) if g1 is not None else (_end_pt(m.paths[i1], e1), _local_end_dir(m.paths[i1], e1))
            c2, t2 = (g2[0], g2[1]) if g2 is not None else (_end_pt(m.paths[i2], e2), _local_end_dir(m.paths[i2], e2))
            X = None
            den = _cr2(t1, t2)
            if abs(den) >= 0.15:
                s1 = _cr2(c2 - c1, t2) / den
                X = c1 + s1 * t1
            mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends], axis=0)
            if X is None or np.linalg.norm(X - mid) > 1.2 * J.w:
                X = mid
            for (i, e) in J.ends:
                _set_end(m.paths[i], e, X)
            if merge_l:
                m = FN.merge_corners(m, [(J.ends[0][0], J.ends[0][1], J.ends[1][0], J.ends[1][1])])
        else:
            mid = np.mean([_end_pt(m.paths[i], e) for i, e in J.ends if i < len(m.paths)], axis=0)
            for (i, e) in J.ends:
                if i < len(m.paths):
                    _set_end(m.paths[i], e, mid)
    for i in {i for i, _ in J.ends if i < len(m.paths)}:
        m.paths[i] = delete_duplicate_anchors(m.paths[i], tol=0.25)
    return m


def lock_joints(m: Model) -> Model:
    """Lock all detected joint endpoints to 0.00 px on their through-stroke or shared vertex without deleting paths."""
    m = m.copy()
    for _ in range(2):
        js = find_joints(m)
        changed = False
        for J in js:
            if J.kind == "X":
                continue
            mem = {i for i, _ in J.ends}
            ext_thr = [j for j in J.through if j not in mem]
            if J.kind in ("T", "Y") and ext_thr:
                need = any(min(_nearest_on(m.paths[j], _end_pt(m.paths[i], e))[1] for j in ext_thr) > 0.015 for i, e in J.ends)
            else:
                pts = np.array([_end_pt(m.paths[i], e) for i, e in J.ends])
                need = float(np.linalg.norm(pts - pts.mean(0), axis=1).max()) > 0.015
            if need:
                m = tool_pen(m, J, merge_l=False)
                changed = True
        if not changed:
            break
    return m


def tool_line(m: Model, J: Joint, arc=False):
    cand = m
    if J.kind in ("T", "Y"):
        changed = False
        for (i, e) in J.ends:
            c = FN.fix_end(cand, i, e, smooth=arc)
            if c is None:
                end = _end_pt(cand.paths[i], e)
                best_X = None
                for j in J.through:
                    if j < len(cand.paths) and j != i:
                        pt_on_q, d = _nearest_on(cand.paths[j], end)
                        if best_X is None or d < best_X[1]:
                            best_X = (pt_on_q, d)
                target = best_X[0] if best_X is not None and best_X[1] <= 2.2 * J.w else None
                c = FN.fix_end(cand, i, e, target=target, smooth=arc)
            if c is not None:
                cand = c
                changed = True
        return cand if changed else None
    # L: intersection of the two reference rays
    geo = [(i, e, FN.end_geometry(cand.paths[i], e)) for i, e in J.ends]
    if len(geo) != 2 or any(g is None for _, _, g in geo):
        return None
    (i1, e1, g1), (i2, e2, g2) = geo
    c1, t1, c2, t2 = g1[0], g1[1], g2[0], g2[1]
    den = _cr2(t1, t2)
    if abs(den) < 0.15:  # nearly parallel
        return None
    s1 = _cr2(c2 - c1, t2) / den
    X = c1 + s1 * t1
    if np.linalg.norm(X - J.xy) > 2.0 * J.w:
        return None
    changed = False
    for (i, e, _) in geo:
        c = FN.fix_end(cand, i, e, target=X, smooth=arc)
        if c is not None:
            cand = c
            changed = True
    return cand if changed else None


def _cr2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def _local_end_dir(p: Path, e: int):
    f = p.flat(0.5)
    if e == 0:
        f = f[::-1]
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
    fr = f[::-1]
    k0 = min(int(np.searchsorted(cum, 0.2 * p.w)), len(fr) - 1)
    k1 = min(int(np.searchsorted(cum, min(1.1 * p.w, 0.45 * float(cum[-1])))), len(fr) - 1)
    if k1 <= k0:
        return unit(f[-1] - f[max(0, len(f) - 2)])
    return unit(fr[k0] - fr[k1])


def smooth_continuation_pairs(m: Model, J: Joint, D):
    """Find pairs of ends meeting at joint J that form a smooth continuation (collinear, curved bar, or circular arc)
    and should be united by Shape Builder into one continuous through-stroke."""
    from .rings import _kasa
    cands = []
    ends = J.ends
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            j, ej = ends[y]
            if i >= len(m.paths) or j >= len(m.paths) or i == j:
                continue
            P, Q = m.paths[i], m.paths[j]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            a = _end_pt(P, ei)
            b = _end_pt(Q, ej)
            dist = float(np.linalg.norm(b - a))
            w = max(wa, wb)
            if dist > 2.5 * w:
                continue
            LP, LQ = P.length(), Q.length()
            f_all = np.vstack([P.flat(1.0), Q.flat(1.0)])
            on_circle = False
            if len(f_all) >= 12:
                cx, cy, r = _kasa(f_all)
                if 1.5 * w <= r <= 50.0 * w and (LP + LQ) >= 1.15 * r:
                    rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r)
                    if float(np.percentile(rad_err, 95)) <= 0.22 * w and float(rad_err.max()) <= 0.35 * w:
                        on_circle = True
            ga = FN.end_geometry(P, ei)
            gb = FN.end_geometry(Q, ej)
            ta = ga[1] if ga is not None else unit(a - (P.A[1] if ei == 0 else P.A[-2]))
            tb = gb[1] if gb is not None else unit(b - (Q.A[1] if ej == 0 else Q.A[-2]))
            ta_loc = _local_end_dir(P, ei)
            tb_loc = _local_end_dir(Q, ej)
            dot = float(ta @ tb)
            dot_loc = float(ta_loc @ tb_loc)
            if not on_circle:
                if dot > -0.85 or dot_loc > -0.82:
                    continue
            else:
                if dot > -0.25 and dot_loc > -0.45:
                    continue
            n = max(3, int(dist))
            pts = a + (b - a) * np.linspace(0, 1, n)[:, None]
            xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
            if float((D[ys, xs] > 0.5).mean()) >= 0.78:
                cands.append((0 if on_circle else 1, dist, i, ei, j, ej, min(dot, dot_loc)))
    if not cands:
        return []
    cands.sort(key=lambda t: (t[0], t[1], t[6]))
    best = cands[0]
    return [(best[2], best[3], best[4], best[5])]


def corner_continuation_pairs(m: Model, J: Joint, D):
    """Find pairs of ends meeting at multi-way joint J that form a corner (roughly 90 deg)
    and should be united by Shape Builder into one continuous corner stroke."""
    ends = J.ends
    if len(ends) < 3:
        return []
    best_pair = None
    best_score = 999.0
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei = ends[x]
            k, ek = ends[y]
            if i >= len(m.paths) or k >= len(m.paths) or i == k:
                continue
            P, Q = m.paths[i], m.paths[k]
            wa, wb = P.w, Q.w
            if abs(wa - wb) > 0.25 * max(wa, wb):
                continue
            w = max(wa, wb)
            if P.length() < 2.5 * w or Q.length() < 2.5 * w:
                continue
            gP = FN.end_geometry(P, ei)
            gQ = FN.end_geometry(Q, ek)
            cP, tP = (gP[0], gP[1]) if gP is not None else (P.A[0 if ei == 0 else -1], _local_end_dir(P, ei))
            cQ, tQ = (gQ[0], gQ[1]) if gQ is not None else (Q.A[0 if ek == 0 else -1], _local_end_dir(Q, ek))
            cr = float(tP[0] * tQ[1] - tP[1] * tQ[0])
            if abs(cr) < 0.40:
                continue
            sP = float((cQ - cP)[0] * tQ[1] - (cQ - cP)[1] * tQ[0]) / cr
            sQ = float((cQ - cP)[0] * tP[1] - (cQ - cP)[1] * tP[0]) / cr
            if sP < -0.2 * w or sQ < -0.2 * w:
                continue
            Xc = cP + sP * tP
            dist_j = float(np.linalg.norm(Xc - J.xy))
            if dist_j > 1.35 * w:
                continue
            dot = float(tP @ tQ)
            if abs(dot) < 0.65:
                score = abs(dot) + 0.5 * (dist_j / w)
                if score < best_score:
                    best_score = score
                    best_pair = (i, ei, k, ek, Xc)
    if best_pair is not None:
        return [best_pair]
    return []


def tool_unite(m: Model, J: Joint, D):
    """Shape Builder, unite: two strokes that are really one stroke cut by the joint (a ring in two arcs, a line cut by a crossing,
    or a curved bar) become one stroke; what is left of the joint is then an ordinary T."""
    pairs = [p for p in FN.collinear_pairs(m, D) if (p[0], p[1]) in J.ends and (p[2], p[3]) in J.ends]
    if not pairs:
        pairs = smooth_continuation_pairs(m, J, D)
    if pairs:
        return FN.join_pairs(m, pairs)
    if len(J.ends) >= 3:
        cp = corner_continuation_pairs(m, J, D)
        if cp:
            return FN.merge_corners(m, cp, joint_ends=J.ends, D=D)
    return None


def tool_shape(m: Model, J: Joint, D):
    r = 2.2 * J.w
    box = [int(J.xy[0] - r), int(J.xy[1] - r), int(J.xy[0] + r), int(J.xy[1] + r)]
    return FN._redraw_region(m, D, box, J.w, margin=0)


# ------------------------------------------------------------------ engine
def run_join_engine(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_fail=30):  # noqa: C901
    """Returns (model, ink, soft, report)."""
    st = dict(model=model, ink=ink_of(model))
    st["cur"] = doctor.soft(st["ink"])
    start = st["cur"]
    st["topo"] = FN._topo(model)
    cap = 0.006 * max(doctor.area, 1)
    rep = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)

    def tol():
        return max(4.0, 0.003 * max(doctor.area, 1), 0.006 * st["cur"])

    def nearest(m, xy, rad):
        js = find_joints(m)
        if not js:
            return None
        d = [np.linalg.norm(j.xy - xy) for j in js]
        k = int(np.argmin(d))
        return js[k] if d[k] <= rad else None

    def try_accept(cand, J, before):
        if cand is None:
            return False
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 > st["cur"] + tol() or (s2 - start) > cap:
            return False
        t2 = FN._topo(cand)
        if t2 > st["topo"]:
            return False
        J2 = nearest(cand, J.xy, 1.5 * J.w)
        ex, mi = _ink_maps(ink2, D)
        after = [] if J2 is None else check_joint(cand, J2, ex, mi)
        struct_keys = {"touch", "hook", "nub", "nodes"}
        s_before = set(before) & struct_keys
        s_after = set(after) & struct_keys
        improved_structural = (len(s_after) < len(s_before)) and not (s_after - s_before)
        simplified_joint = J2 is not None and (len(J2.ends) < len(J.ends) or (J.kind == "Y" and J2.kind == "T")) and not (set(after) - set(before))
        if len(after) < len(before) or improved_structural or simplified_joint:
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
            return True
        return False

    # stage 0: unite any stroke cut at a multi-end joint so it becomes a continuous through-stroke before locking T-stems
    for J in [j for j in find_joints(st["model"]) if len(j.ends) >= 2]:
        if not time_ok():
            break
        J_cur = nearest(st["model"], J.xy, 1.5 * J.w)
        if J_cur is None or len(J_cur.ends) < 2:
            continue
        cand_u = tool_unite(st["model"], J_cur, D)
        if cand_u is not None:
            ink_u = ink_of(cand_u)
            s_u = doctor.soft(ink_u)
            tol_u = max(tol(), 0.0045 * max(doctor.area, 1))
            if s_u <= st["cur"] + tol_u and (s_u - start) <= cap and FN._topo(cand_u) <= st["topo"]:
                st.update(model=cand_u, ink=ink_u, cur=s_u, topo=FN._topo(cand_u))
                rep["fixed"]["unite"] += 1

    # stage 1: build every joint carefully (ends exactly on the centreline they join) - fast batch first
    ex, mi = _ink_maps(st["ink"], D)
    joints = find_joints(st["model"])
    rep["total"] = len(joints)
    need = [J for J in joints if J.kind != "X" and "touch" in check_joint(st["model"], J)]
    if need:
        cand = st["model"]
        for J in need:
            cand = tool_pen(cand, J) if cand is st["model"] else _apply_pen_again(cand, J)
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        if s2 <= st["cur"] + tol() and FN._topo(cand) <= st["topo"]:
            st.update(model=cand, ink=ink2, cur=s2, topo=FN._topo(cand))
            rep["built"] = len(need)
        else:
            cand2 = lock_joints(st["model"])
            ink2 = ink_of(cand2)
            s2 = doctor.soft(ink2)
            if s2 <= st["cur"] + tol():
                st.update(model=cand2, ink=ink2, cur=s2, topo=FN._topo(cand2))
                rep["built"] = len(need)
    # stage 2: check every joint, repair the ones that fail
    joints = find_joints(st["model"])
    ex, mi = _ink_maps(st["ink"], D)
    fails = []
    for J in joints:
        bad = check_joint(st["model"], J, ex, mi)
        if not bad:
            rep["clean_first"] += 1
        else:
            fails.append((len(bad), J.xy.copy(), J.w, bad))
    fails.sort(key=lambda t: -t[0])
    for _, xy, jw, _ in fails[:max_fail]:
        if not time_ok():
            break
        ex, mi = _ink_maps(st["ink"], D)
        J = nearest(st["model"], xy, 1.5 * jw)
        if J is None:
            continue
        before = check_joint(st["model"], J, ex, mi)
        if not before:
            continue
        done = False
        for name, fn in (("unite", lambda: tool_unite(st["model"], J, D)), ("pen", lambda: tool_pen(st["model"], J)), ("line", lambda: tool_line(st["model"], J)),
                         ("arc", lambda: tool_line(st["model"], J, arc=True)), ("shape", lambda: tool_shape(st["model"], J, D))):
            if not time_ok():
                break
            try:
                cand = fn()
            except Exception:
                cand = None
            if try_accept(cand, J, before):
                rep["fixed"][name] += 1
                done = True
                break
        if not done:
            ex, mi = _ink_maps(st["ink"], D)
            J = nearest(st["model"], xy, 1.5 * jw)
            rep["unresolved"].append(dict(x=float(xy[0]), y=float(xy[1]), reasons=before))
    # Final geometric lock so no joint ends up with a residual sub-pixel gap or overshoot
    cand_lock = lock_joints(st["model"])
    ink_lock = ink_of(cand_lock)
    s_lock = doctor.soft(ink_lock)
    if s_lock <= st["cur"] + tol():
        st.update(model=cand_lock, ink=ink_lock, cur=s_lock)
    rep["drift"] = float(st["cur"] - start)
    return st["model"], st["ink"], st["cur"], rep


def _apply_pen_again(m, J):
    """Pen tool on a model that has already been changed by earlier joints of this batch: re-find the joint near J and apply."""
    js = find_joints(m)
    if not js:
        return m
    k = int(np.argmin([np.linalg.norm(j.xy - J.xy) for j in js]))
    return tool_pen(m, js[k]) if np.linalg.norm(js[k].xy - J.xy) <= 1.5 * J.w else m



================================================================================
# FILE: linework/finisher.py
================================================================================

"""Finisher engine: the last engine of the loop.  It runs once every icon is on the canvas and inspects each icon on its own,
looking for the 3-4 small places where a machine drawing still gives itself away, and fixes each one so the result reads as
hand-made vector art.

Sites it looks for (each is located, fixed, and the fix is verified by a re-render):
  handles   a segment whose handles point backwards or are far longer than the segment (loops, bulges, overshoots)  -> redraw path
  density   far more nodes than the shape needs (wobble)                                                          -> simplify
  align     near-vertical / near-horizontal straight strokes that are off-axis by a hair, edges of the same shape
            that are 0.3-1 px apart                                                                                -> exact axis, shared coordinate
  widths    strokes of one icon that differ by a few percent in width                                             -> one width per weight class
  specks    tiny leftovers shorter than a stroke width                                                          -> remove
  hotspots  places where render and source still disagree                                                         -> re-fit harder, then re-draw locally
A fix is kept only if the match to the source does not get worse (beyond a tiny cosmetic tolerance), no new gap / notch / spur
appears, and the total cosmetic drift is capped.  So the Finisher can polish, but it cannot damage the match.
"""
from __future__ import annotations
import time
import numpy as np, cv2
from .model import Model, Path
from .geom import resample, fit_curve, bez, unit, line_inter
from . import edit as E
from . import topology as T


def _topo(m):
    return len(T.find_gaps(m)) + len(T.find_notches(m)) + len(T.find_spurs(m))


# ------------------------------------------------------------------ detectors
def bad_handle_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed and len(p.segs()) >= 4:
            continue  # exact rings are handled elsewhere
        for k, c in enumerate(p.segs()):
            v = c[3] - c[0]
            L = np.linalg.norm(v)
            if L < 3:
                continue
            u = v / L
            h0, h1 = c[1] - c[0], c[3] - c[2]
            if (h0 @ u < -0.6 and np.linalg.norm(h0) > 1.5) or (h1 @ u < -0.6 and np.linalg.norm(h1) > 1.5) or \
               np.linalg.norm(h0) > 1.6 * L + 2 or np.linalg.norm(h1) > 1.6 * L + 2:
                out.append((i, c[0] + v / 2))
                break
    return out


def dense_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        n = len(p.segs())
        if n >= 4 and n > p.length() / (4.0 * p.w) + 1:
            out.append((i, p.A[len(p.A) // 2]))
    return out


def speck_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        L = p.length()
        if (0.3 * p.w < L < 1.5 * p.w and not p.closed) or (p.closed and L < 1.5 * p.w):
            out.append((i, p.A.mean(0)))
        elif L <= 0.3 * p.w and not p.closed:
            tree, _, _ = _others_tree(m, i)
            if tree is not None and tree.query(p.A.mean(0))[0] < 0.6 * p.w:
                out.append((i, p.A.mean(0)))
    return out


def hairline_paths(m: Model, frac=0.4):
    """Paths far thinner than the icon's strokes: JPEG shadows / faint grey that were traced as a hair-thin line."""
    ws = [(p.w, p.length()) for p in m.paths if p.length() > 3 * p.w]
    if len(ws) < 3:
        return []
    med = float(np.median([w for w, _ in ws]))
    return [(i, p.A.mean(0)) for i, p in enumerate(m.paths) if p.w < frac * med and p.length() > 0]


def wobbly_straights(m: Model, dev_frac=0.12, min_len=1.8):
    """Open paths that are really one straight stroke (every point within dev_frac*w of the chord) but carry extra nodes / bends."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        f = p.flat(1.0)
        v = f[-1] - f[0]
        L = np.linalg.norm(v)
        if L < min_len * p.w:
            continue
        n = np.array([-v[1], v[0]]) / L
        devs = np.abs((f - f[0]) @ n)
        dev = float(devs.max())
        proj = (f - f[0]) @ (v / L)
        dx, dy = abs(v[0]), abs(v[1])
        is_axis_aligned = (min(dx, dy) <= 0.25 * p.w) and (max(dx, dy) >= 4.0 * p.w)
        is_local_bulge = L >= 4.5 * p.w and len(p.A) >= 4 and (devs <= 0.15 * p.w).mean() >= 0.55
        short_dev = 0.38 if len(p.A) == 3 else 0.22
        eff_dev = max(0.5, ((1.5 if is_axis_aligned else 0.42) if (is_axis_aligned or is_local_bulge) else (max(dev_frac, short_dev) if L < 3.5 * p.w and len(p.A) >= 3 else dev_frac)) * p.w)
        if dev <= eff_dev and proj.min() > -0.5 * p.w and proj.max() < L + 0.5 * p.w:
            segs = p.segs()
            exact = len(segs) == 1 and _straight(segs[0], 0.05)
            if not exact:
                out.append((i, f[len(f) // 2]))
    return out


def z_fold_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 3:
            continue
        A = p.A
        for k in range(len(A) - 2):
            v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.60:
                out.append((i, A[k + 1].copy()))
                break
    return out


def fix_z_fold_cands(m: Model, i: int):
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return []
    cands = []
    A, Hin, Hout = p.A.copy(), p.Hin.copy(), p.Hout.copy()
    if len(A) == 3:
        for drop in (1, 0, 2):
            keep = [j for j in range(3) if j != drop]
            a, b = A[keep[0]].copy(), A[keep[1]].copy()
            q = Path([a, b], [a, a + (b - a) * 2.0 / 3.0], [a + (b - a) / 3.0, b], p.w, p.join, p.ml, False)
            m1 = m.copy()
            m1.paths[i] = q
            cands.append(m1)
        return cands
    for k in range(len(A) - 2):
        v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
        L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.60:
            if k + 3 < len(A):
                v3 = A[k + 3] - A[k + 2]
                L3 = float(np.linalg.norm(v3))
                if L3 > 1e-3 and (v2 / L2) @ (v3 / L3) < -0.60:
                    # Candidate 1: split Z-fold into the two overlapping strokes (preserving curved handles on k+2 -> k+3)
                    idx2 = list(range(k + 3, len(A)))
                    idx1_base = list(range(0, k + 1)) + [k + 2, k + 3]
                    A1_b, Hi1_b, Ho1_b = A[idx1_base].copy(), Hin[idx1_base].copy(), Hout[idx1_base].copy()
                    d0 = A1_b[k + 1] - A1_b[k]
                    Ho1_b[k] = A1_b[k] + d0 / 3.0
                    Hi1_b[k + 1] = A1_b[k] + 2.0 * d0 / 3.0
                    Ho1_b[-1] = A1_b[-1].copy()
                    p1_base = Path(A1_b, Hi1_b, Ho1_b, p.w, p.join, p.ml, False)
                    for merge_k in (True, False):
                        if merge_k and k >= 1 and np.linalg.norm(A[k + 2] - A[k]) <= 0.85 * p.w:
                            idx1 = list(range(0, k)) + [k + 2, k + 3]
                            A1, Hi1, Ho1 = A[idx1].copy(), Hin[idx1].copy(), Hout[idx1].copy()
                            Hi1[k] = Hin[k].copy()
                            Ho1[-1] = A1[-1].copy()
                            p1 = Path(A1, Hi1, Ho1, p.w, p.join, p.ml, False)
                        elif not merge_k:
                            p1 = p1_base.copy()
                        else:
                            continue
                        u_wall = unit(A[-1] - A[k + 3]) if len(A) > k + 4 and np.linalg.norm(A[-1] - A[k + 3]) > 1e-3 else unit(A[k + 3] - A[k + 1])
                        n_wall = np.array([-u_wall[1], u_wall[0]])
                        f1 = p1.flat(0.25)
                        rel = f1 - A[k + 3]
                        behind = (rel @ u_wall) < -0.5 * p.w
                        if behind.any():
                            sub = f1[behind]
                            lat_d = np.abs((sub - A[k + 3]) @ n_wall)
                            P0_wall = sub[int(np.argmin(lat_d))].copy()
                        else:
                            proj_back = float((A[k] - A[k + 1]) @ u_wall)
                            P0_wall = A[k + 1] + min(proj_back, -0.2 * p.w) * u_wall if proj_back < 0 else A[k + 1].copy()
                        # If the wall from P0_wall through A[idx2] is colinear, collapse redundant middle node A[k+3]
                        if len(idx2) == 2 and abs(float((A[idx2[-1]] - P0_wall) @ n_wall)) <= 0.15 * p.w:
                            A2 = np.vstack([[P0_wall], [A[idx2[-1]]]])
                            d2 = A2[1] - A2[0]
                            Hi2 = np.vstack([[P0_wall], [P0_wall + 2.0 * d2 / 3.0]])
                            Ho2 = np.vstack([[P0_wall + d2 / 3.0], [A2[1]]])
                        else:
                            A2 = np.vstack([[P0_wall], A[idx2]])
                            Hi2 = np.vstack([[P0_wall], Hin[idx2]])
                            Ho2 = np.vstack([[P0_wall + (A2[1] - P0_wall) / 3.0], Hout[idx2]])
                            Hi2[1] = P0_wall + 2.0 * (A2[1] - P0_wall) / 3.0
                        p2 = Path(A2, Hi2, Ho2, p.w, p.join, p.ml, False)
                        # Snap p1's end onto p2 so T.find_gaps sees 0 gap at both ends
                        f2 = p2.flat(0.25)
                        end1 = f2[int(np.argmin(np.linalg.norm(f2 - p1.A[-1], axis=1)))].copy()
                        d_end = end1 - p1.A[-1]
                        p1.A[-1] = end1
                        p1.Hin[-1] = p1.Hin[-1] + d_end
                        p1.Hout[-1] = end1.copy()
                        m_split = m.copy()
                        m_split.paths[i] = p1
                        m_split.paths.append(p2)
                        cands.append(m_split)
            # Candidate 2: drop only spike k+1 (preserving handles on k+2 -> k+3)
            for drop_set in ((k + 1,), (k + 2,), (k + 1, k + 2)):
                keep = [j for j in range(len(A)) if j not in drop_set and j < len(A)]
                if len(keep) < 2:
                    continue
                Ak, Hik, Hok = A[keep].copy(), Hin[keep].copy(), Hout[keep].copy()
                if k < len(Ak) - 1:
                    d = Ak[k + 1] - Ak[k]
                    Hok[k] = Ak[k] + d / 3.0
                    Hik[k + 1] = Ak[k] + 2.0 * d / 3.0
                m1 = m.copy()
                m1.paths[i] = Path(Ak, Hik, Hok, p.w, p.join, p.ml, False)
                cands.append(m1)
            break
    cands.append(fix_z_fold(m, i))
    return cands


def fix_z_fold(m: Model, i: int):
    m = m.copy()
    p = m.paths[i]
    if p.closed or len(p.A) < 4:
        return m
    A, Hin, Hout = p.A.copy(), p.Hin.copy(), p.Hout.copy()
    changed = True
    while changed and len(A) >= 4:
        changed = False
        for k in range(len(A) - 2):
            v1, v2 = A[k + 1] - A[k], A[k + 2] - A[k + 1]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 > 1e-3 and L2 > 1e-3 and (v1 / L1) @ (v2 / L2) < -0.65:
                if k + 3 < len(A):
                    v3 = A[k + 3] - A[k + 2]
                    L3 = float(np.linalg.norm(v3))
                    if L3 > 1e-3 and (v2 / L2) @ (v3 / L3) < -0.65:
                        keep = [j for j in range(len(A)) if j not in (k + 1, k + 2)]
                    else:
                        keep = [j for j in range(len(A)) if j != k + 1]
                else:
                    keep = [j for j in range(len(A)) if j != k + 1]
                A, Hin, Hout = A[keep], Hin[keep], Hout[keep]
                if k < len(A) - 1:
                    d = A[k + 1] - A[k]
                    Hout[k] = A[k] + d / 3.0
                    Hin[k + 1] = A[k] + 2.0 * d / 3.0
                changed = True
                break
    m.paths[i] = Path(A, Hin, Hout, p.w, p.join, p.ml, False)
    return m


def make_straight(m: Model, i):
    m = m.copy()
    p = m.paths[i]
    a, b = p.A[0].copy(), p.A[-1].copy()
    q = Path([a, b], [a, a + (b - a) * 2 / 3], [a + (b - a) / 3, b], p.w, p.join, p.ml, False)
    m.paths[i] = q
    return m


def _reversed(p: Path):
    return Path(p.A[::-1].copy(), p.Hout[::-1].copy(), p.Hin[::-1].copy(), p.w, p.join, p.ml, False)


def _cr(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def _others_tree(m: Model, skip):
    from scipy.spatial import cKDTree
    pts, own = [], []
    for j, p in enumerate(m.paths):
        if j == skip:
            continue
        f = p.flat(0.5)
        pts.append(f)
        own += [j] * len(f)
    if not pts:
        return None, None, None
    P = np.vstack(pts)
    return cKDTree(P), P, np.array(own)


def _end_frame(p: Path, e: int):
    """Oriented flat polyline (end last) and the cumulative arc length measured from the END backwards."""
    f = resample(p.flat(), 0.5)
    if e == 0:
        f = f[::-1]
    back = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]  # back[k] = arc length from end to f[::-1][k]
    return f, back


def end_geometry(p: Path, e: int):
    """(cut point c at 1.4 w from the end, reference direction t pointing to the end, hook angle in degrees, end point, dev).
    The reference direction is measured on the stretch 1.4-3.6 w from the end, i.e. outside the zone where junction artefacts live;
    the hook angle compares it with the direction of the last 0.9 w."""
    f, back = _end_frame(p, e)
    fr = f[::-1]
    if back[-1] < 2.0 * p.w:
        return None
    sel = (back >= 1.2 * p.w) & (back <= min(float(back[-1]), 3.6 * p.w))
    if sel.sum() < 4:
        sel = (back >= 0.8 * p.w) & (back <= float(back[-1]))
        if sel.sum() < 4:
            return None
    seg = fr[sel]
    c = fr[min(int(np.searchsorted(back, min(1.4 * p.w, 0.45 * float(back[-1])))), len(fr) - 1)]
    # PCA direction of the reference stretch, oriented from far to near the end
    u, sv, vt = np.linalg.svd(seg - seg.mean(0), full_matrices=False)
    t = vt[0]
    if t @ (seg[0] - seg[-1]) < 0:  # seg[0] is nearest the end
        t = -t
    t = t / np.linalg.norm(t)
    k = np.searchsorted(back, 0.9 * p.w)
    te = fr[0] - fr[min(k, len(fr) - 1)]
    n = np.linalg.norm(te)
    ang = 0.0 if n < 1e-6 else float(np.degrees(np.arccos(np.clip((te / n) @ t, -1, 1))))
    dev = abs(float((fr[0] - c)[0] * t[1] - (fr[0] - c)[1] * t[0]))  # sideways offset of the end from the stroke's own straight line
    return c, t, ang, fr[0], dev


def _straight_before_end(p: Path, e: int, t, tol_deg=7.0):
    """True when the stroke runs straight into its end (direction of the stretch 3.6-6 w from the end equals the reference direction),
    so a bend in the last 1.4 w is an artefact, not a curve."""
    f, back = _end_frame(p, e)
    fr = f[::-1]
    body = fr[(back >= 1.4 * p.w) & (back <= min(float(back[-1]), 6.0 * p.w))]
    if len(body) >= 4:
        chord = body[-1] - body[0]
        clen = float(np.linalg.norm(chord))
        if clen > 1e-6:
            u_ch = chord / clen
            perp = np.abs((body[:, 0] - body[0, 0]) * u_ch[1] - (body[:, 1] - body[0, 1]) * u_ch[0])
            if float(perp.max()) > max(0.65, 0.08 * p.w):
                return False
    sel = (back >= 3.6 * p.w) & (back <= 6.0 * p.w)
    if sel.sum() < 4:
        sel = (back >= 1.8 * p.w) & (back <= float(back[-1]))
        if sel.sum() < 4:
            return False
    seg = fr[sel]
    u, sv, vt = np.linalg.svd(seg - seg.mean(0), full_matrices=False)
    d = vt[0]
    return abs(float(d @ t)) >= np.cos(np.radians(tol_deg))


def end_hooks(m: Model, min_angle=12.0):
    """Open-path ends whose last stretch bends away from a stroke that is straight up to there (hooks, curls, jogs at joints)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            g = end_geometry(p, e)
            if g is not None and (g[2] >= min_angle or g[4] >= max(0.8, 0.12 * p.w)) and _straight_before_end(p, e, g[1]):
                out.append((max(g[2], 90.0 * g[4] / max(p.w, 1e-6)), i, e, g[3]))
    return sorted(out, key=lambda t: -t[0])


def fix_end(m: Model, i, e, reach=4.5, target=None, smooth=False):
    """Replace the last 1.4 w of path i's end e by a straight run along the stroke's own direction, ending ON the centerline of the stroke it
    joins (or, for a free end, at the same distance as before). Returns the new model or None."""
    p = m.paths[i]
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(p)
        cand = fix_end(m_rev, i, 1, reach=reach, target=target, smooth=smooth)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
    g = end_geometry(p, e)
    if g is None:
        return None
    c, t, ang, end, dev = g
    tree, P, own = _others_tree(m, i)
    X = None if target is None else np.asarray(target, float)
    if X is None and tree is not None:
        s = np.arange(0.2 * p.w, reach * p.w, 0.4)
        ray = c + s[:, None] * t
        d, k = tree.query(ray)
        j = int(np.argmin(d))
        if d[j] < 0.6 * p.w:
            X = P[k[j]].copy()
    if X is None:
        if ang < 12.0 and dev < max(0.8, 0.12 * p.w):
            return None
        X = c + t * max(1.0 * p.w, float(np.linalg.norm(end - c)))
    cand = move_end(m, i, e, 1.4 * p.w)
    if cand is None:
        return None
    q = cand.paths[i]
    cut = q.A[-1]
    v = X - cut
    L = np.linalg.norm(v)
    if L < 0.3 or np.degrees(np.arccos(np.clip((v / L) @ t, -1, 1))) > 30.0:
        return None
    u = v / L
    hin = np.linalg.norm(q.Hin[-1] - cut)
    if smooth:  # arc-like run: leave along the stroke's own tangent and arrive along it
        q.Hin[-1] = cut - t * hin
        q.Hout[-1] = cut + t * (L / 3)
        q.A = np.vstack([q.A, X])
        q.Hin = np.vstack([q.Hin, X - t * (L / 3)])
        q.Hout = np.vstack([q.Hout, X])
        return cand
    q.Hin[-1] = cut - u * hin  # keep the stroke smooth (G1) where the straight run starts
    q.Hout[-1] = cut + v / 3
    q.A = np.vstack([q.A, X])
    q.Hin = np.vstack([q.Hin, X - v / 3])
    q.Hout = np.vstack([q.Hout, X])
    return cand


def collinear_pairs(m: Model, D, ang=15.0, reach=2.6):
    """Open paths that were cut where another stroke crosses them: facing endpoints <= reach*w apart, pointing at each other,
    joined by source ink.  Returns [(i, end_i, j, end_j)] with each endpoint used once."""
    ends = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            h = p.Hout[0] if e == 0 else p.Hin[-1]
            t = a - h
            g = end_geometry(p, e)
            if g is not None:  # direction of the stroke itself, measured outside the zone where junction artefacts live
                t = g[1]
            if np.linalg.norm(t) < 1e-6:
                f = p.flat(1.0)
                t = f[0] - f[min(len(f) - 1, 6)] if e == 0 else f[-1] - f[max(0, len(f) - 7)]
            ends.append((i, e, a, t / max(np.linalg.norm(t), 1e-9), p.w, g[0] if g is not None else a))
    c = np.cos(np.radians(ang))
    cands = []
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei, a, ta, wa, ca = ends[x]
            j, ej, b, tb, wb, cb = ends[y]
            if i == j or abs(wa - wb) > 0.2 * max(wa, wb):
                continue
            if abs(_cr(cb - ca, ta)) > 0.6 * max(wa, wb):  # the other piece must lie on this piece's own line
                continue
            v = b - a
            d = np.linalg.norm(v)
            if d > reach * max(wa, wb):
                continue
            vc = cb - ca
            u = vc / np.linalg.norm(vc) if np.linalg.norm(vc) > 0.5 else v / max(d, 1e-9)  # direction between the cut points (outside the hook zone)
            if ta @ u < c or tb @ (-u) < c:
                continue
            n = max(3, int(d))
            pts = a + v * np.linspace(0, 1, n)[:, None]
            xs = np.clip(pts[:, 0].astype(int), 0, D.shape[1] - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, D.shape[0] - 1)
            if (D[ys, xs] > 0.5).mean() < 0.9:
                continue
            cands.append((d, i, ei, j, ej))
    used, out = set(), []
    for d, i, ei, j, ej in sorted(cands):
        if (i, ei) in used or (j, ej) in used:
            continue
        used.add((i, ei))
        used.add((j, ej))
        out.append((i, ei, j, ej))
    return out


def _cut_if_hooked(p: Path, e: int):
    """Cut the last 1.4 w off end e when that end is bent / jogged away from its own stroke (see end_geometry)."""
    g = end_geometry(p, e)
    if g is None or not (g[2] >= 12.0 or g[4] >= max(0.8, 0.12 * p.w)):
        return p
    if not _straight_before_end(p, e, g[1]):
        return p
    mm = move_end(Model([p], 0, 0), 0, e, 1.4 * p.w)
    return p if mm is None else mm.paths[0]


def _clean_seam(p: Path) -> Path:
    A, Hin, Hout = list(p.A), list(p.Hin), list(p.Hout)
    changed = True
    while changed and len(A) > 2:
        changed = False
        for k in range(len(A) - 1):
            if np.linalg.norm(A[k + 1] - A[k]) < 0.25 * p.w:
                A.pop(k)
                Hin.pop(k)
                Hout.pop(k)
                changed = True
                break
    return Path(np.array(A), np.array(Hin), np.array(Hout), p.w, p.join, p.ml, p.closed)

def join_pairs(m: Model, pairs):
    from .rings import _kasa
    m = m.copy()
    dead = set()
    for (i, ei, j, ej) in pairs:
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)  # P ends at the cut
        Q = Q if ej == 0 else _reversed(Q)  # Q starts at the cut
        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)
        f_p, f_q = P.flat(1.0), Q.flat(1.0)
        f_all = np.vstack([f_p, f_q])
        if len(f_all) >= 12:
            cx, cy, r = _kasa(f_all)
            if 1.5 * w_merged <= r <= 50.0 * w_merged and (LP + LQ) >= 1.15 * r:
                rad_err = np.abs(np.hypot(f_all[:, 0] - cx, f_all[:, 1] - cy) - r)
                if float(np.percentile(rad_err, 95)) <= 0.22 * w_merged and float(rad_err.max()) <= 0.35 * w_merged:
                    if np.linalg.norm(f_all[0] - f_all[-1]) <= 1.8 * w_merged and (LP + LQ) >= 5.0 * r:
                        A, Hin, Hout = E.ellipse_beziers(np.array([cx, cy]), r, r, 0.0)
                        m.paths[i] = Path(A, Hin, Hout, w_merged, P.join, P.ml, True)
                        dead.add(j)
                        continue
                    else:
                        th_a = float(np.arctan2(f_p[-1, 1] - cy, f_p[-1, 0] - cx))
                        th_b = float(np.arctan2(f_q[0, 1] - cy, f_q[0, 0] - cx))
                        dth = (th_b - th_a + np.pi) % (2 * np.pi) - np.pi
                        n_bridge = max(2, int(abs(dth) * r / 2.0))
                        ths = th_a + np.linspace(0.0, dth, n_bridge)[1:-1]
                        bridge = np.c_[cx + r * np.cos(ths), cy + r * np.sin(ths)] if len(ths) else np.zeros((0, 2))
                        f_comb = np.vstack([f_p, bridge, f_q])
                        ang = np.arctan2(f_comb[:, 1] - cy, f_comb[:, 0] - cx)
                        f_proj = np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang)]
                        f_proj[0], f_proj[-1] = f_p[0], f_q[-1]
                        q_arc = E._refit(f_proj, P, sigma=0.5, err=0.22)
                        if q_arc is not None:
                            q_arc.w = w_merged
                            m.paths[i] = q_arc
                            dead.add(j)
                            continue
        P = _cut_if_hooked(P, 1)
        Q = _reversed(_cut_if_hooked(_reversed(Q), 1))
        a, b = P.A[-1], Q.A[0]
        if np.linalg.norm(b - a) < 1.0:
            mid = 0.5 * (a + b)
            A = np.vstack([P.A[:-1], [mid], Q.A[1:]])
            Hin = np.vstack([P.Hin[:-1], [P.Hin[-1] + (mid - a)], Q.Hin[1:]])
            Hout = np.vstack([P.Hout[:-1], [Q.Hout[0] + (mid - b)], Q.Hout[1:]])
        else:
            A = np.vstack([P.A, Q.A])
            Hin = np.vstack([P.Hin, Q.Hin])
            Hout = np.vstack([P.Hout, Q.Hout])
            Hout[len(P.A) - 1] = a + (b - a) / 3
            Hin[len(P.A)] = a + 2 * (b - a) / 3
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.22 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            closed = True
        m.paths[i] = _clean_seam(Path(A, Hin, Hout, w_merged, P.join, P.ml, closed))
        dead.add(j)
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m
def _end_info(p: Path, e: int, back=2.0):
    """(end point, a point `back` stroke widths behind it along the path) for end e of an open path."""
    f = p.flat(0.5)
    if e == 0:
        f = f[::-1]
    a = f[-1]
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
    k = int(np.searchsorted(cum, back * p.w))
    return a, f[::-1][min(k, len(f) - 1)]


def _protrusion(m: Model, i, a, w_i, b=None):
    """How far (px) a round cap of width w_i at `a` sticks out of the stroke it ends in or has crossed.
    Covers (1) a cap inside stroke j that pokes through j's far edge, and (2) a stub: the path crossed j's centerline
    (a and `b`, a point further back on the path, lie on opposite sides) and its end overshoots j's far edge."""
    tree, P, own = _others_tree(m, i)
    if tree is None:
        return 0.0
    d, k = tree.query(a)
    if d > w_i * 2.2:
        return 0.0
    j = own[k]
    rj = m.paths[j].w / 2
    out = max(0.0, w_i / 2 + d - rj) if d < rj else 0.0
    if b is not None:
        kk = [x for x in (k - 1, k + 1) if 0 <= x < len(P) and own[x] == j]
        if kk:
            tau = P[max(kk)] - P[min(kk)]
            if np.linalg.norm(tau) > 1e-9:
                sa = _cr(a - P[k], tau) / np.linalg.norm(tau)
                db, kb = tree.query(b)
                if own[kb] == j and db < w_i * 3:
                    kb2 = [x for x in (kb - 1, kb + 1) if 0 <= x < len(P) and own[x] == j]
                    if kb2:
                        tb = P[max(kb2)] - P[min(kb2)]
                        if np.linalg.norm(tb) > 1e-9:
                            sb = _cr(b - P[kb], tb) / np.linalg.norm(tb)
                            if sa * sb < 0 and abs(sa) > 0.15 * w_i and abs(sb) > 0.15 * w_i:
                                out = max(out, w_i / 2 + d - rj)
    return out


def cap_hits(m: Model, frac=0.1):
    """Round caps / stubs that stick out of the stroke they end in or cross (the small nubs and overshoots at junctions)."""
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        for e in (0, 1):
            a, b = _end_info(p, e)
            pr = _protrusion(m, i, a, p.w, b)
            if pr > frac * p.w:
                out.append((pr / p.w, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])


def find_penetrating_stubs(m: Model, D):
    """Detect open strokes that have crossed another stroke or entered a closed loop and continue past it
    into white/empty space. Returns [(i, e, cut_distance, end_xy, crossing_path_j)]."""
    hits = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        w = p.w
        tree, P, own = _others_tree(m, i)
        if tree is None:
            continue
        for e in (0, 1):
            f = p.flat(0.5)
            if e == 0:
                f = f[::-1]
            a = f[-1]
            cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(f[::-1], axis=0), axis=1))]
            max_k = int(np.searchsorted(cum, 3.2 * w))
            if max_k < 4:
                continue
            pts = f[::-1][:max_k]
            ds, idxs = tree.query(pts)
            for step_k in range(3, len(ds)):
                dist_to_other = ds[step_k]
                j = own[idxs[step_k]]
                if dist_to_other < 0.40 * w:
                    s = float(cum[step_k])
                    if s >= 0.55 * w:
                        test_pts = f[::-1][:step_k]
                        xs = np.clip(test_pts[:, 0].astype(int), 0, D.shape[1] - 1)
                        ys = np.clip(test_pts[:, 1].astype(int), 0, D.shape[0] - 1)
                        has_hole = float((D[ys, xs] < 0.45).mean()) >= 0.20
                        is_closed = m.paths[j].closed
                        if has_hole or is_closed:
                            hits.append((i, e, s, a.copy(), j))
                            break
    return hits


def _split_last(c, length):
    """Cut `length` px off the end of Bezier c (4,2): returns the shortened Bezier, or None if the segment is too short."""
    t = np.linspace(0, 1, 40)
    mt = 1 - t
    P = (mt**3)[:, None] * c[0] + (3 * mt**2 * t)[:, None] * c[1] + (3 * mt * t**2)[:, None] * c[2] + (t**3)[:, None] * c[3]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    L = seg.sum()
    if L < length + 1.5:
        return None
    cum = np.r_[0, np.cumsum(seg)]
    s = float(np.interp(L - length, cum, t))
    a, b, cc, d = c
    ab, bc, cd = a + (b - a) * s, b + (cc - b) * s, cc + (d - cc) * s
    abc, bcd = ab + (bc - ab) * s, bc + (cd - bc) * s
    return np.array([a, ab, abc, abc + (bcd - abc) * s])


def move_end(m: Model, i, e, delta):
    """delta > 0 retracts the end of path i by that many px along the path; delta < 0 extends it along its end tangent."""
    if e == 0:
        m_rev = m.copy()
        m_rev.paths[i] = _reversed(m.paths[i])
        cand = move_end(m_rev, i, 1, delta)
        if cand is not None:
            cand.paths[i] = _reversed(cand.paths[i])
        return cand
    m = m.copy()
    p = m.paths[i]
    if delta > 0:
        rest = delta
        while True:  # a short last segment is dropped entirely and the remainder is taken off the one before
            c = p.segs()[-1]
            c2 = _split_last(c, rest)
            if c2 is not None:
                break
            if len(p.A) <= 2:
                return None
            tt = np.linspace(0, 1, 30)
            pts = np.array([(1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u * u * c[2] + u**3 * c[3] for u in tt])
            rest -= float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
            p = Path(p.A[:-1], p.Hin[:-1], np.vstack([p.Hout[:-2], p.A[-2:-1]]), p.w, p.join, p.ml, False)
            if rest <= 0.5:
                m.paths[i] = p
                return m
        p.A[-1] = c2[3]
        p.Hin[-1] = c2[2]
        p.Hout[-2] = c2[1]
    else:
        t = p.A[-1] - p.Hin[-1]
        n = np.linalg.norm(t)
        if n < 1e-6:
            return None
        v = t / n * (-delta)
        p.A[-1] = p.A[-1] + v
        p.Hin[-1] = p.Hin[-1] + v
    m.paths[i] = p
    return m


def best_end_move(m: Model, i, e, w):
    """Pick the retract/extend amount that leaves the least cap sticking out; returns (model, new_protrusion) or None."""
    p = m.paths[i]
    a0, b0 = _end_info(p, e)
    base = _protrusion(m, i, a0, p.w, b0)
    best = None
    for dl in (-0.5, -0.3, -0.15, 0.15, 0.3, 0.5, 0.75, 1.0, 1.25, 1.6):
        cand = move_end(m, i, e, dl * p.w)
        if cand is None:
            continue
        q = cand.paths[i]
        a1, b1 = _end_info(q, 1)
        pr = _protrusion(cand, i, a1, q.w, b1)
        if pr < base - 0.05 * p.w and (best is None or pr < best[1] - 1e-6 or (abs(pr - best[1]) < 1e-6 and abs(dl) < best[2])):
            best = (cand, pr, abs(dl))
    return None if best is None else (best[0], best[1])


def _make_arc_path(cx, cy, r, t0, t1, w, join="round", ml=4.0):
    c = np.array([cx, cy], float)
    span = float(t1 - t0)
    n = max(1, int(np.ceil(abs(span) / (np.pi / 2) - 1e-9)))
    step = span / n
    segs = []
    for k in range(n):
        a0, a1 = t0 + k * step, t0 + (k + 1) * step
        P0 = c + r * np.array([np.cos(a0), np.sin(a0)])
        P3 = c + r * np.array([np.cos(a1), np.sin(a1)])
        h = 4.0 / 3.0 * np.tan(step / 4.0) * r
        P1 = P0 + h * np.array([-np.sin(a0), np.cos(a0)])
        P2 = P3 - h * np.array([-np.sin(a1), np.cos(a1)])
        segs.append([P0, P1, P2, P3])
    q = Path.from_segs(segs, w, closed=False, join=join)
    q.ml = ml
    return q


def robust_arc_fit(p: Path, tol_frac=0.12):
    """Return candidate exact circular-arc replacements for open path p, tolerating up to 2.2*w junction noise at ends."""
    from .rings import _kasa
    f = resample(p.flat(), 1.0)
    if len(f) < 12:
        return []
    tol = max(0.7, tol_frac * p.w)
    cands = []
    max_trim = min(int(round(2.2 * p.w)), len(f) // 4)
    for t_start in (0, int(round(0.8 * p.w)), int(round(1.5 * p.w)), max_trim):
        for t_end in (0, int(round(0.8 * p.w)), int(round(1.5 * p.w)), max_trim):
            sub = f[t_start : len(f) - t_end] if t_end > 0 else f[t_start:]
            if len(sub) < max(10, int(0.65 * len(f))):
                continue
            cx, cy, r = _kasa(sub)
            if not (1.2 * p.w < r < 60 * p.w):
                continue
            c = np.array([cx, cy])
            dist_sub = np.linalg.norm(sub - c, axis=1)
            dev_sub = float(np.abs(dist_sub - r).max())
            if dev_sub > tol:
                continue
            ang_all = np.unwrap(np.arctan2(f[:, 1] - cy, f[:, 0] - cx))
            ang_sub = ang_all[t_start : len(f) - t_end] if t_end > 0 else ang_all[t_start:]
            span_sub = float(ang_sub[-1] - ang_sub[0])
            if abs(span_sub) < (0.6 if (t_start == 0 and t_end == 0) else 1.8) or abs(span_sub) > 6.0:
                continue
            d_sub = np.diff(ang_sub)
            if (np.sign(d_sub) == np.sign(span_sub)).mean() < 0.95:
                continue
            span_all = float(ang_all[-1] - ang_all[0])
            if np.sign(span_all) == np.sign(span_sub) and 0.6 <= abs(span_all) <= 6.1:
                q_full = _make_arc_path(cx, cy, r, ang_all[0], ang_all[-1], p.w, p.join, p.ml)
                if not (t_start == 0 and t_end == 0 and dev_sub < 0.12 and len(p.segs()) <= len(q_full.segs())):
                    cands.append((t_start + t_end + dev_sub, q_full))
            if t_start > 0 or t_end > 0:
                q_sub = _make_arc_path(cx, cy, r, ang_sub[0], ang_sub[-1], p.w, p.join, p.ml)
                cands.append((t_start + t_end + dev_sub + 5.0, q_sub))
    cands.sort(key=lambda x: x[0])
    return [q for _, q in cands[:4]]


def arc_fit(p: Path, tol_frac=0.1):
    """If open path p is (nearly) one circular arc, return the exact-arc replacement Path, else None."""
    from .rings import _kasa
    f = resample(p.flat(), 1.0)
    if len(f) < 8:
        return None
    cx, cy, r = _kasa(f)
    c = np.array([cx, cy])
    dist = np.linalg.norm(f - c, axis=1)
    if np.abs(dist - r).max() <= max(0.6, tol_frac * p.w) and (1.2 * p.w < r < 60 * p.w):
        ang = np.unwrap(np.arctan2(f[:, 1] - cy, f[:, 0] - cx))
        d = np.diff(ang)
        span = float(ang[-1] - ang[0])
        if 0.6 <= abs(span) <= 5.8 and (np.sign(d) == np.sign(span)).mean() >= 0.95:
            q = _make_arc_path(cx, cy, r, ang[0], ang[-1], p.w, p.join, p.ml)
            g = resample(q.flat(), 1.0)
            cur = resample(p.flat(), 1.0)
            k = min(len(g), len(cur))
            if np.abs(np.linalg.norm(g[:k] - c, axis=1) - r).max() > 0.1 and np.abs(dist - r).max() < 0.12:
                return None
            return q
    cands = robust_arc_fit(p, tol_frac=max(tol_frac, 0.12))
    return cands[0] if cands else None


def arc_paths(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        q = arc_fit(p)
        if q is not None:
            out.append((i, p.A[len(p.A) // 2], q))
    return out


def _straight(c, tol=0.6):
    v = c[3] - c[0]
    L = np.linalg.norm(v)
    if L < (1.5 if tol <= 0.1 else 8):
        return False
    n = np.array([-v[1], v[0]]) / L
    return max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n)) * 0.75 < tol


def _from_segs_exact(segs, w, closed=False, join="round", ml=4.0):
    q = Path.from_segs(segs, w, closed=closed, join=join)
    q.ml = ml
    return q


def excess_ends(m: Model, ink, D, frac=0.1):
    """Open-path ends with ink in the render that the source does not have around them (thick tips, lumps).
    Returns [(excess_px, path, end, xy)] sorted by excess."""
    extra = ((ink > 0.5) & (D < 0.3)).astype(np.float32)
    H, W = extra.shape
    out = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        tree, P, _ = _others_tree(m, i)
        r = int(max(3, 1.4 * p.w))
        for e in (0, 1):
            a = p.A[0] if e == 0 else p.A[-1]
            iy, ix = int(round(a[1])), int(round(a[0]))
            if 0 <= iy < H and 0 <= ix < W and D[iy, ix] > 0.45:
                if tree is not None and float(tree.query(a)[0]) <= 0.45 * p.w:
                    continue
            x0, x1 = int(max(a[0] - r, 0)), int(min(a[0] + r + 1, W))
            y0, y1 = int(max(a[1] - r, 0)), int(min(a[1] + r + 1, H))
            if x1 <= x0 or y1 <= y0:
                continue
            ex = float(extra[y0:y1, x0:x1].sum())
            if ex >= frac * p.w * p.w:
                out.append((ex, i, e, a.copy()))
    return sorted(out, key=lambda t: -t[0])


def corner_pairs(m: Model, tol=1.2):
    """Two open paths that simply end at the same point (a corner drawn as two strokes with two overlapping round caps)
    and nothing else touches that point -> [(i, end_i, j, end_j)]."""
    ends = []
    for i, p in enumerate(m.paths):
        if p.closed:
            continue
        ends += [(i, 0, p.A[0], p.w), (i, 1, p.A[-1], p.w)]
    out, used = [], set()
    w_med = float(np.median([p.w for p in m.paths])) if m.paths else 10.0
    eff_tol = max(tol, 0.40 * w_med)
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            i, ei, a, wa = ends[x]
            j, ej, b, wb = ends[y]
            if i == j or (i, ei) in used or (j, ej) in used:
                continue
            pair_tol = max(eff_tol, 0.40 * min(wa, wb))
            if np.linalg.norm(a - b) > pair_tol or abs(wa - wb) > 0.2 * max(wa, wb):
                continue
            mid = (a + b) / 2
            third = False
            for k, q in enumerate(m.paths):
                if k in (i, j):
                    continue
                f = q.flat(1.0)
                if np.linalg.norm(f - mid, axis=1).min() < 0.7 * max(wa, wb):
                    third = True
                    break
            if third:
                continue
            used.add((i, ei))
            used.add((j, ej))
            out.append((i, ei, j, ej))
    return out


def merge_corners(m: Model, pairs, joint_ends=None, D=None):
    """One stroke with a corner node instead of two strokes with two overlapping caps (the join is then drawn once, cleanly)."""
    m = m.copy()
    dead = set()
    for item in pairs:
        i, ei, j, ej = item[:4]
        Xc_override = item[4] if len(item) > 4 else None
        if i in dead or j in dead:
            continue
        P, Q = m.paths[i], m.paths[j]
        P = P if ei == 1 else _reversed(P)
        Q = Q if ej == 0 else _reversed(Q)
        mid = (P.A[-1] + Q.A[0]) / 2
        w_max = max(P.w, Q.w)
        gP = end_geometry(P, 1)
        gQ = end_geometry(Q, 0)
        from . import joints as J_mod
        tP = gP[1] if gP is not None else J_mod._local_end_dir(P, 1)
        tQ = gQ[1] if gQ is not None else J_mod._local_end_dir(Q, 0)
        # Attempt ray intersection of incoming straight rays
        X_corner = Xc_override
        if X_corner is None:
            if gP is not None and gQ is not None:
                cP, tP_g = gP[0], gP[1]
                cQ, tQ_g = gQ[0], gQ[1]
                den = float(tP_g[0] * tQ_g[1] - tP_g[1] * tQ_g[0])
                if abs(den) >= 0.15:
                    sP = float((cQ - cP)[0] * tQ_g[1] - (cQ - cP)[1] * tQ_g[0]) / den
                    Xc = cP + sP * tP_g
                    if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                        X_corner = Xc
        if X_corner is None:
            fP, fQ = P.flat(0.5), Q.flat(0.5)
            kP = min(len(fP) - 1, max(3, int(round(1.0 * P.w))))
            kQ = min(len(fQ) - 1, max(3, int(round(1.0 * Q.w))))
            tP_f = unit(fP[-1] - fP[-1 - kP]) if len(fP) > kP else unit(P.A[-1] - P.A[0])
            tQ_f = unit(fQ[kQ] - fQ[0]) if len(fQ) > kQ else unit(Q.A[-1] - Q.A[0])
            den = float(tP_f[0] * tQ_f[1] - tP_f[1] * tQ_f[0])
            if abs(den) >= 0.15:
                sP = float((Q.A[0] - P.A[-1])[0] * tQ_f[1] - (Q.A[0] - P.A[-1])[1] * tQ_f[0]) / den
                Xc = P.A[-1] + sP * tP_f
                if np.linalg.norm(Xc - mid) <= 1.25 * w_max:
                    X_corner = Xc
        corner_pt = mid if X_corner is None else X_corner

        # Check if corner is round (fillet in raster ink)
        is_round = False
        if D is not None and X_corner is not None:
            ix = int(np.clip(round(corner_pt[0]), 0, D.shape[1] - 1))
            iy = int(np.clip(round(corner_pt[1]), 0, D.shape[0] - 1))
            bisect = tP + tQ
            nb = float(np.linalg.norm(bisect))
            if nb > 1e-4:
                u_out = bisect / nb
                tx = int(np.clip(round(corner_pt[0] + 0.25 * w_max * u_out[0]), 0, D.shape[1] - 1))
                ty = int(np.clip(round(corner_pt[1] + 0.25 * w_max * u_out[1]), 0, D.shape[0] - 1))
                if D[ty, tx] < 0.40 or D[iy, ix] < 0.70:
                    is_round = True
            elif D[iy, ix] < 0.70:
                is_round = True

        LP, LQ = max(P.length(), 1e-3), max(Q.length(), 1e-3)
        w_merged = (P.w * LP + Q.w * LQ) / (LP + LQ)

        if is_round and X_corner is not None:
            R = min(1.2 * w_merged, 0.45 * min(LP, LQ))
            kappa = 0.55228475 * R
            P_start = corner_pt - R * tP
            P_end = corner_pt - R * tQ
            P_mod, Q_mod = P.copy(), Q.copy()
            if len(P_mod.A) > 2 and np.linalg.norm(P_mod.A[-2] - P_start) < 0.45 * w_merged:
                P_mod.A = P_mod.A[:-1]
                P_mod.Hin = P_mod.Hin[:-1]
                P_mod.Hout = P_mod.Hout[:-1]
            if len(Q_mod.A) > 2 and np.linalg.norm(Q_mod.A[1] - P_end) < 0.45 * w_merged:
                Q_mod.A = Q_mod.A[1:]
                Q_mod.Hin = Q_mod.Hin[1:]
                Q_mod.Hout = Q_mod.Hout[1:]
            P_mod.A[-1] = P_start.copy()
            P_mod.Hin[-1] = P_start - tP * (w_merged / 3.0)
            P_mod.Hout[-1] = P_start + tP * kappa
            Q_mod.A[0] = P_end.copy()
            Q_mod.Hin[0] = P_end + tQ * kappa
            Q_mod.Hout[0] = P_end - tQ * (w_merged / 3.0)
            A = np.vstack([P_mod.A, Q_mod.A])
            Hin = np.vstack([P_mod.Hin, Q_mod.Hin])
            Hout = np.vstack([P_mod.Hout, Q_mod.Hout])
        else:
            dP, dQ = corner_pt - P.A[-1], corner_pt - Q.A[0]
            A = np.vstack([P.A, Q.A[1:]])
            Hin = np.vstack([P.Hin, Q.Hin[1:]])
            Hout = np.vstack([P.Hout[:-1], Q.Hout])
            idx = len(P.A) - 1
            A[idx] = corner_pt
            Hin[idx] = P.Hin[-1] + dP
            Hout[idx] = Q.Hout[0] + dQ
            # Straighten incoming/outgoing handles if straight into corner
            if idx >= 1:
                segP = np.array([A[idx - 1], Hout[idx - 1], Hin[idx], A[idx]])
                if _straight(segP, 0.4) or (gP is not None and _straight_before_end(P, 1, gP[1])):
                    vP = A[idx] - A[idx - 1]
                    Hout[idx - 1] = A[idx - 1] + vP / 3.0
                    Hin[idx] = A[idx] - vP / 3.0
            if idx + 1 < len(A):
                segQ = np.array([A[idx], Hout[idx], Hin[idx + 1], A[idx + 1]])
                if _straight(segQ, 0.4) or (gQ is not None and _straight_before_end(Q, 0, gQ[1])):
                    vQ = A[idx + 1] - A[idx]
                    Hout[idx] = A[idx] + vQ / 3.0
                    Hin[idx + 1] = A[idx + 1] - vQ / 3.0

        join_type = "round" if is_round else ("miter" if (P.join == "miter" or Q.join == "miter") else P.join)
        ml_val = max(P.ml, Q.ml)
        closed = False
        if np.linalg.norm(A[0] - A[-1]) <= max(1.5, 0.25 * w_merged) and (LP + LQ) >= 3.5 * w_merged and len(A) >= 4:
            A[-1] = A[0].copy()
            Hin[0] = Hin[-1].copy()
            Hout[-1] = Hout[0].copy()
            closed = True
        if is_round:
            m.paths[i] = Path(A, Hin, Hout, w_merged, join_type, ml_val, closed)
        else:
            m.paths[i] = _clean_seam(Path(A, Hin, Hout, w_merged, join_type, ml_val, closed))
        dead.add(j)
    if joint_ends and pairs:
        merged_i = pairs[0][0]
        p_merged = m.paths[merged_i]
        for (k_idx, e_k) in joint_ends:
            if k_idx in dead or k_idx == merged_i or k_idx >= len(m.paths):
                continue
            pk = m.paths[k_idx]
            end_pt = pk.A[0 if e_k == 0 else -1]
            f = p_merged.flat(0.25)
            k_near = int(np.argmin(np.linalg.norm(f - end_pt, axis=1)))
            pt_on, d_on = f[k_near], float(np.linalg.norm(f[k_near] - end_pt))
            if d_on <= 1.5 * p_merged.w:
                from . import joints as J_mod
                J_mod._set_end(pk, e_k, pt_on)
                ak = J_mod.insert_anchor(p_merged, pt_on)
                J_mod._set_end(pk, e_k, p_merged.A[ak])
    m.paths = [p for k, p in enumerate(m.paths) if k not in dead]
    return m


def _rotate_closed_to_turn(p: Path) -> Path:
    if not p.closed or len(p.A) <= 5:
        return p
    segs = p.segs()
    n = len(segs)
    best_k, best_turn = 0, -1.0
    for k in range(n):
        s_prev = segs[(k - 1) % n]
        s_curr = segs[k]
        d_in = unit(s_prev[3] - s_prev[0])
        d_out = unit(s_curr[3] - s_curr[0])
        turn = 1.0 - float(d_in @ d_out)
        if turn > best_turn:
            best_turn = turn
            best_k = k
    if best_k == 0 or best_turn < 0.005:
        return p
    new_segs = segs[best_k:] + segs[:best_k]
    return _from_segs_exact(new_segs, p.w, closed=True, join=p.join, ml=p.ml)


def _collapse_pass(p: Path, max_dev: float, ang_deg: float, snap_line: bool = False) -> Path:
    q = _rotate_closed_to_turn(p) if p.closed else p
    segs = q.segs()
    n = len(segs)
    if n < 2:
        return p
    cos_lim = np.cos(np.radians(ang_deg))
    cos_short = np.cos(np.radians(max(ang_deg, 18.0)))

    def fit_run(k0, k1):
        A0 = segs[k0][0]
        A1 = segs[k1 - 1][3]
        v = A1 - A0
        L = float(np.linalg.norm(v))
        if L < max(4.0, 0.9 * q.w):
            return None
        u = v / L
        n_vec = np.array([-u[1], u[0]])
        all_pts, weights = [], []
        for k in range(k0, k1):
            c = segs[k]
            sv = c[3] - c[0]
            sL = float(np.linalg.norm(sv))
            if sL > 1e-4:
                su = sv / sL
                lim = cos_lim if sL >= 0.7 * q.w else cos_short
                if su @ u < lim:
                    return None
            pts = bez(c, np.linspace(0, 1, 9))
            dev = np.abs((pts - A0) @ n_vec).max()
            if dev > max_dev:
                return None
            proj = (pts - A0) @ u
            if np.any(np.diff(proj) < -0.25):
                return None
            all_pts.append(pts)
            weights.append(np.full(len(pts), max(sL, 1.0)))
        if not snap_line:
            return A0.copy(), A1.copy()
        P = np.vstack(all_pts)
        W = np.concatenate(weights)
        W /= W.sum()
        mean = (P * W[:, None]).sum(0)
        _, _, vt = np.linalg.svd((P - mean) * np.sqrt(W[:, None]))
        d = vt[0]
        if d @ u < 0:
            d = -d
        if abs(d[1]) < np.sin(np.radians(1.5)):
            d = np.array([np.sign(d[0]), 0.0])
        elif abs(d[0]) < np.sin(np.radians(1.5)):
            d = np.array([0.0, np.sign(d[1])])
        P0 = mean + ((A0 - mean) @ d) * d
        P1 = mean + ((A1 - mean) @ d) * d
        return P0, P1

    new_segs, is_merged = [], []
    i = 0
    changed = False
    while i < n:
        best_j = i + 1
        best_end = None
        for j in range(i + 2, n + 1):
            res = fit_run(i, j)
            if res is not None:
                best_j = j
                best_end = res
        if best_j > i + 1:
            P0, P1 = best_end
            new_segs.append(np.array([P0, P0 + (P1 - P0) / 3.0, P0 + 2.0 * (P1 - P0) / 3.0, P1]))
            is_merged.append(True)
            i = best_j
            changed = True
        else:
            new_segs.append(segs[i].copy())
            is_merged.append(False)
            i += 1
    if not changed:
        return p
    m_len = len(new_segs)
    for k in range(m_len if q.closed else m_len - 1):
        k_next = (k + 1) % m_len
        s1, s2 = new_segs[k], new_segs[k_next]
        if np.linalg.norm(s1[3] - s2[0]) > 1e-4:
            d1 = unit(s1[3] - s1[0])
            d2 = unit(s2[3] - s2[0])
            C = line_inter(s1[0], d1, s2[0], d2) if (is_merged[k] and is_merged[k_next]) else None
            if C is not None and np.linalg.norm(C - s1[3]) < 0.5 * q.w:
                pt = C
            else:
                pt = s1[3] if is_merged[k] and not is_merged[k_next] else (s2[0] if is_merged[k_next] else 0.5 * (s1[3] + s2[0]))
            s1[3] = pt.copy()
            s2[0] = pt.copy()
            if is_merged[k]:
                s1[1] = s1[0] + (s1[3] - s1[0]) / 3.0
                s1[2] = s1[0] + 2.0 * (s1[3] - s1[0]) / 3.0
            if is_merged[k_next]:
                s2[1] = s2[0] + (s2[3] - s2[0]) / 3.0
                s2[2] = s2[0] + 2.0 * (s2[3] - s2[0]) / 3.0
    return _from_segs_exact(new_segs, q.w, closed=q.closed, join=q.join, ml=q.ml)


def collapse_straight_runs(p: Path):
    q = _collapse_pass(p, max_dev=0.22, ang_deg=3.5, snap_line=False)
    q2 = _collapse_pass(q, max_dev=max(0.5, 0.11 * p.w), ang_deg=12.0, snap_line=True)
    return q2, q


def _fit_single_cubic(pts, t0=None, t1=None):
    from scipy.spatial import cKDTree
    P0, P3 = pts[0].copy(), pts[-1].copy()
    seg_d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    L = float(seg_d.sum())
    if L < 1e-4:
        return None, 1e9
    u = np.r_[0.0, np.cumsum(seg_d) / L]
    for _ in range(2):
        mt = 1.0 - u
        b0 = mt ** 3
        b1 = 3 * (mt ** 2) * u
        b2 = 3 * mt * (u ** 2)
        b3 = u ** 3
        rhs = pts - b0[:, None] * P0 - b3[:, None] * P3
        if t0 is not None and t1 is not None:
            M = np.zeros((2, 2))
            v = np.zeros(2)
            c1 = b1[:, None] * t0[None, :]
            c2 = -b2[:, None] * t1[None, :]
            M[0, 0] = (c1 * c1).sum()
            M[0, 1] = M[1, 0] = (c1 * c2).sum()
            M[1, 1] = (c2 * c2).sum()
            v[0] = (c1 * rhs).sum()
            v[1] = (c2 * rhs).sum()
            try:
                a1, a2 = np.linalg.solve(M + 1e-9 * np.eye(2), v)
            except Exception:
                a1 = a2 = L / 3.0
            a1 = float(np.clip(a1, 0.05 * L, 0.85 * L))
            a2 = float(np.clip(a2, 0.05 * L, 0.85 * L))
            P1 = P0 + a1 * t0
            P2 = P3 - a2 * t1
        else:
            A_mat = np.c_[b1, b2]
            sol, *_ = np.linalg.lstsq(A_mat, rhs, rcond=None)
            P1, P2 = sol[0], sol[1]
        c = np.array([P0, P1, P2, P3])
        Q = bez(c, u)
        Qp = 3 * ((1 - u)[:, None] ** 2 * (P1 - P0) + 2 * (1 - u)[:, None] * u[:, None] * (P2 - P1) + (u[:, None] ** 2) * (P3 - P2))
        num = ((Q - pts) * Qp).sum(1)
        den = (Qp * Qp).sum(1) + 1e-9
        u = np.clip(u - num / den, 0.0, 1.0)
    c = np.array([P0, P1, P2, P3])
    dense = bez(c, np.linspace(0, 1, max(24, int(L))))
    err = float(cKDTree(dense).query(pts)[0].max())
    return c, err


def simplify_path_segments(st, pi: int, doctor, ink_of, start_s: float, drift_cap: float, sites: list, skip=()):
    """Collapse redundant anchors in st['model'].paths[pi]: collinear straight pairs and G1-smooth single-cubic pairs."""
    if "density" in skip or pi >= len(st["model"].paths):
        return
    m = st["model"]
    p0 = _rotate_closed_to_turn(m.paths[pi]) if m.paths[pi].closed else m.paths[pi]
    if p0 is not m.paths[pi]:
        m = m.copy()
        m.paths[pi] = p0
        st["model"] = m

    tried_bad = set()
    while True:
        m = st["model"]
        p = m.paths[pi]
        segs = p.segs()
        n = len(segs)
        if n < 2:
            break
        max_dev_str = max(0.65, 0.12 * p.w)
        cos_lim = np.cos(np.radians(14.0))
        cos_short = np.cos(np.radians(22.0))
        num_pairs = n if p.closed else n - 1
        best = None
        for k in range(num_pairs):
            k2 = (k + 1) % n
            s1, s2 = segs[k], segs[k2]
            A0, AM, A1 = s1[0], s1[3], s2[3]
            key = (round(float(AM[0]), 1), round(float(AM[1]), 1), n)
            if key in tried_bad:
                continue
            v = A1 - A0
            L = float(np.linalg.norm(v))
            if L < max(3.5, 0.6 * p.w):
                continue
            u = v / L
            n_vec = np.array([-u[1], u[0]])
            v1, v2 = s1[3] - s1[0], s2[3] - s2[0]
            L1, L2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            if L1 < 1e-4 or L2 < 1e-4:
                continue
            pts1 = bez(s1, np.linspace(0, 1, 13))
            pts2 = bez(s2, np.linspace(0, 1, 13))
            pts = np.vstack([pts1, pts2[1:]])
            dev_str = float(np.abs((pts - A0) @ n_vec).max())
            lim1 = cos_lim if L1 >= 0.7 * p.w else cos_short
            lim2 = cos_lim if L2 >= 0.7 * p.w else cos_short

            cands_seg = []
            if (v1 / L1) @ u >= lim1 and (v2 / L2) @ u >= lim2 and dev_str <= max_dev_str and not np.any(np.diff((pts - A0) @ u) < -0.2):
                cands_seg.append((dev_str, np.array([A0, A0 + v / 3.0, A0 + 2.0 * v / 3.0, A1])))
            tin = unit(s1[3] - s1[2]) if np.linalg.norm(s1[3] - s1[2]) > 0.2 else v1 / L1
            tout = unit(s2[1] - s2[0]) if np.linalg.norm(s2[1] - s2[0]) > 0.2 else v2 / L2
            if tin @ tout >= np.cos(np.radians(18.0)) and (v1 / L1) @ (v2 / L2) >= np.cos(np.radians(38.0)):
                t0 = unit(s1[1] - s1[0]) if np.linalg.norm(s1[1] - s1[0]) > 0.2 else v1 / L1
                t1 = unit(s2[3] - s2[2]) if np.linalg.norm(s2[3] - s2[2]) > 0.2 else v2 / L2
                c_fit, err_c = _fit_single_cubic(pts, t0, t1)
                if c_fit is not None and err_c <= max(0.35, 0.04 * p.w):
                    cands_seg.append((err_c + 0.05, c_fit))
            if cands_seg:
                score = min(c[0] for c in cands_seg)
                if best is None or score < best[0]:
                    best = (score, k, k2, key, AM.copy(), [c[1] for c in cands_seg])
        if best is None:
            break
        score, k, k2, key, AM, seg_list = best
        accepted = False
        for merged_seg in seg_list:
            if k2 > k:
                new_segs = segs[:k] + [merged_seg] + segs[k2 + 1:]
            else:
                new_segs = [merged_seg] + segs[1:k]
            q_cand = _from_segs_exact(new_segs, p.w, closed=p.closed, join=p.join, ml=p.ml)
            cand_m = m.copy()
            cand_m.paths[pi] = q_cand
            ink2 = ink_of(cand_m)
            s_new = doctor.soft(ink2)
            t2 = _topo(cand_m)
            tol = max(3.5, 0.005 * st["cur"]) if score < 0.22 else max(2.0, 0.003 * st["cur"])
            if s_new <= st["cur"] + tol and t2 <= st["topo"] and (s_new - start_s) <= drift_cap:
                st.update(model=cand_m, ink=ink2, cur=s_new, topo=t2)
                sites.append(dict(kind="density", x=float(AM[0]), y=float(AM[1]), fixed=True))
                accepted = True
                break
        if not accepted:
            tried_bad.add(key)


# ------------------------------------------------------------------ fixers
def redraw_path(m: Model, i):
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 0.75)
    segs = fit_curve(f, 0.8, 0.45)
    if segs:
        q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
        q.ml = p.ml
        m.paths[i] = q
    return m


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def u(self, a, b):
        self.p[self.f(a)] = self.f(b)


def align_groups(m: Model, ang=2.5, par_tol=1.0, max_shift=1.5):
    """Returns a list of (axis, [(path, anchor)...], new_coordinate) alignments (not applied)."""
    nodes = []
    for i, p in enumerate(m.paths):
        n = len(p.A) - (1 if p.closed else 0)
        for k in range(n):
            nodes.append((i, k, p.A[k]))
    if not nodes:
        return []
    xy = np.array([n[2] for n in nodes])
    idx = {(n[0], n[1]): j for j, n in enumerate(nodes)}
    ufx, ufy = _UF(len(nodes)), _UF(len(nodes))
    from scipy.spatial import cKDTree
    for a, b in cKDTree(xy).query_pairs(0.8):
        ufx.u(a, b)
        ufy.u(a, b)
    vx, vy = [], []  # nodes taking part in vertical / horizontal straight strokes
    sa = np.sin(np.radians(ang))
    for i, p in enumerate(m.paths):
        for k, c in enumerate(p.segs()):
            if not _straight(c):
                continue
            k1 = (k + 1) % (len(p.A) - 1) if p.closed else k + 1
            a, b = idx[(i, k)], idx[(i, k1)]
            v = c[3] - c[0]
            L = np.linalg.norm(v)
            if abs(v[0]) < sa * L:
                ufx.u(a, b)
                vx += [a, b]
            elif abs(v[1]) < sa * L:
                ufy.u(a, b)
                vy += [a, b]
    out = []
    for axis, uf, vs in ((0, ufx, vx), (1, ufy, vy)):
        # parallel strokes of the same shape: cluster group means that are within par_tol
        groups = {}
        for j in set(vs):
            groups.setdefault(uf.f(j), []).append(j)
        means = sorted((np.mean([xy[j][axis] for j in g]), r) for r, g in groups.items())
        for (m0, r0), (m1, r1) in zip(means, means[1:]):
            if m1 - m0 <= par_tol:
                uf.u(r0, r1)
        allg = {}
        for j in range(len(nodes)):
            allg.setdefault(uf.f(j), []).append(j)
        for r, g in allg.items():
            if len(g) < 2:
                continue
            vals = np.array([xy[j][axis] for j in g])
            new = float(vals.mean())
            if np.abs(vals - new).max() < 0.02 or np.abs(vals - new).max() > max_shift:
                continue
            if not any(j in set(vs) for j in g):
                continue
            out.append((axis, [(nodes[j][0], nodes[j][1]) for j in g], new))
    return out


def apply_align(m: Model, groups):
    m = m.copy()
    for axis, members, new in groups:
        for (i, k) in members:
            p = m.paths[i]
            d = new - p.A[k][axis]
            for arr in (p.A, p.Hin, p.Hout):
                arr[k][axis] += d
            if p.closed and k == 0:
                for arr in (p.A, p.Hin, p.Hout):
                    arr[-1][axis] = arr[0][axis]
    for i in {g[0] for grp in groups for g in grp[1]}:
        p = m.paths[i]
        for k, c in enumerate(p.segs()):
            if _straight(c, 1.2):
                v = c[3] - c[0]
                p.Hout[k] = c[0] + v / 3
                p.Hin[k + 1] = c[0] + 2 * v / 3
    return m


def width_plan(m: Model, ratio=1.22, max_dev=0.4, anchor=None):
    """Cluster stroke widths into weight classes (long paths only) and return {path: class width} for paths that are off by 3-40 %."""
    items = [(p.w, p.length(), i) for i, p in enumerate(m.paths) if p.length() > 3 * p.w]
    if len(items) < 2:
        return {}
    items.sort()
    cl, cur = [], [items[0]]
    for it in items[1:]:
        if it[0] / cur[0][0] <= ratio:
            cur.append(it)
        else:
            cl.append(cur)
            cur = [it]
    cl.append(cur)
    centers = []
    for c in cl:
        w = np.array([t[0] for t in c])
        L = np.array([t[1] for t in c])
        o = np.argsort(w)
        cw = np.cumsum(L[o])
        centers.append(float(w[o][np.searchsorted(cw, cw[-1] / 2)]))
    if anchor:  # the set-wide stroke width wins over this icon's own estimate when they are close
        jn = int(np.argmin([abs(anchor - c) for c in centers]))
        if abs(anchor - centers[jn]) / anchor < 0.2:
            centers[jn] = float(anchor)
    plan = {}
    for i, p in enumerate(m.paths):
        j = int(np.argmin([abs(p.w - c) for c in centers]))
        dev = abs(p.w - centers[j]) / centers[j]
        if 0.03 < dev <= max_dev:
            plan[i] = centers[j]
    return plan


# ------------------------------------------------------------------ engine
def finish(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_hot=4, set_w=None, skip=()):
    """Returns (model, ink, soft, report) where report = dict(sites=[...], found=int, fixed=int, drift=float)."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    start = cur
    topo = _topo(model)
    drift_cap = 0.006 * max(doctor.area, 1)
    sites = []
    st = dict(model=model, ink=ink, cur=cur, topo=topo)

    def tol_for(cur_):
        return max(2.0, 0.003 * cur_)

    def attempt(cand, kind, xy, tol=None, improve=False):
        """verify `cand`; returns True when kept."""
        if cand is None or kind in skip:
            return False
        ink2 = ink_of(cand)
        s2 = doctor.soft(ink2)
        lim = st["cur"] - 0.5 if improve else st["cur"] + (tol_for(st["cur"]) if tol is None else tol)
        ok = s2 <= lim and (s2 - start) <= drift_cap
        t2 = _topo(cand) if ok else st["topo"]  # topology is the slow check: only for candidates that already pass on match
        ok = ok and t2 <= st["topo"]
        if not ok and s2 <= lim and (s2 - start) <= drift_cap and t2 > st["topo"]:
            cw = T.weld_all(cand)
            tw = _topo(cw)
            if tw <= st["topo"]:
                ink_w = ink_of(cw)
                sw = doctor.soft(ink_w)
                if sw <= lim and (sw - start) <= drift_cap:
                    cand, ink2, s2, t2, ok = cw, ink_w, sw, tw, True
        sites.append(dict(kind=kind, x=float(xy[0]), y=float(xy[1]), fixed=bool(ok)))
        if ok:
            st.update(model=cand, ink=ink2, cur=s2, topo=t2)
        return ok

    # 0. hair-thin traces of faint grey (never real strokes)
    for i, xy in sorted(hairline_paths(st["model"]), key=lambda t: -t[0]):
        if i < len(st["model"].paths):
            p = st["model"].paths[i]
            attempt(E.remove_path(st["model"], i), "hairline", xy, tol=0.6 * p.w * p.length())
    # 0c. hooks / jogs at the ends of strokes: straight run along the stroke's own direction, ending on the centerline it joins
    done_h = 0
    for ang, i, e, xy in end_hooks(st["model"])[:40]:
        if not time_ok() or done_h >= 40:
            break
        if i < len(st["model"].paths):
            cand = fix_end(st["model"], i, e)
            if cand is not None:
                attempt(cand, "ends", xy)
                done_h += 1
    # 0a. strokes that were cut where another stroke crosses them -> one continuous stroke
    for _ in range(3):
        if not time_ok():
            break
        pairs = collinear_pairs(st["model"], D)
        if not pairs:
            break
        mid = np.mean([st["model"].paths[p[0]].A[0 if p[1] == 0 else -1] for p in pairs], axis=0)
        if attempt(join_pairs(st["model"], pairs), "join", mid):
            continue
        sites.pop()
        any_ok = False
        for pr in pairs[:20]:
            if not time_ok():
                break
            n_ = len(st["model"].paths)
            if max(pr[0], pr[2]) < n_:
                if attempt(join_pairs(st["model"], [pr]), "join", st["model"].paths[pr[0]].A[0 if pr[1] == 0 else -1]):
                    any_ok = True
        if not any_ok:
            break
    # 0b. wobbly strokes that are really one straight line
    for i, xy in wobbly_straights(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(make_straight(st["model"], i), "straighten", xy, tol=max(3.5, 0.006 * st["cur"]))
    # 0c. Z-folds / switchbacks
    for i, xy in z_fold_paths(st["model"]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            for zcand in fix_z_fold_cands(st["model"], i):
                if attempt(zcand, "handles", xy, tol=max(12.0, 0.02 * st["cur"])):
                    break
                sites.pop()
    # 1. handles that loop / overshoot
    for i, xy in sorted(bad_handle_paths(st["model"]), key=lambda t: -t[0]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(redraw_path(st["model"], i), "handles", xy)
    # 1b. apex overshoots and crevice tongues
    for i in range(len(st["model"].paths)):
        if i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        p_pruned = T.prune_apex_overshoot(p)
        if len(p_pruned.A) < len(p.A):
            cand = st["model"].copy()
            cand.paths[i] = p_pruned
            xy = p.A[len(p.A) // 2].copy()
            if not attempt(cand, "density", xy):
                sites.pop()
    # 2. needless nodes
    for i, xy in sorted(dense_paths(st["model"]), key=lambda t: -t[0]):
        if not time_ok():
            break
        if i < len(st["model"].paths):
            attempt(E.simplify(st["model"], i, 0.7), "density", xy)
    # 3. alignment of straight strokes: all at once, else one group at a time
    groups = align_groups(st["model"])
    if groups:
        c0 = np.mean([st["model"].paths[g[1][0][0]].A[g[1][0][1]] for g in groups], axis=0)
        n0 = len(sites)
        if not attempt(apply_align(st["model"], groups), "align", c0):
            sites.pop()
            for g in groups[:16]:
                if not time_ok():
                    break
                p = st["model"].paths[g[1][0][0]]
                attempt(apply_align(st["model"], [g]), "align", p.A[g[1][0][1]])
    # 4. widths
    plan = width_plan(st["model"], anchor=set_w) if "widths" not in skip else {}
    if plan:
        cand = st["model"].copy()
        for i, wv in plan.items():
            cand.paths[i].w = wv
        mid = np.mean([st["model"].paths[i].A.mean(0) for i in plan], axis=0)
        if not attempt(cand, "widths", mid):
            sites.pop()
            for i, wv in list(plan.items())[:12]:
                if not time_ok():
                    break
                c1 = st["model"].copy()
                c1.paths[i].w = wv
                attempt(c1, "widths", st["model"].paths[i].A.mean(0))
    # 4b. caps that stick out of the stroke they end in (nubs at junctions)
    done = 0
    for pr, i, e, xy in cap_hits(st["model"])[:40]:
        if not time_ok() or done >= 30:
            break
        if i >= len(st["model"].paths):
            continue
        mv = best_end_move(st["model"], i, e, w)
        if mv is not None:
            if not attempt(mv[0], "caps", xy):
                sites.pop()
                attempt(T.weld_all(mv[0]), "caps", xy)
            done += 1
        # the moved path may have been re-oriented; later hits are re-detected below
    # 4b2. penetrating stubs: open strokes that cross another stroke and overshoot past it
    for i, e, dl, xy, j in find_penetrating_stubs(st["model"], D)[:25]:
        if not time_ok():
            break
        if i >= len(st["model"].paths):
            continue
        cand = move_end(st["model"], i, e, dl)
        if cand is not None:
            attempt(cand, "caps", xy, improve=True)
    # 4d. thick tips / lumps: ends with excess ink around them are pulled back by whatever amount helps most (verified)
    for ex, i, e, xy in excess_ends(st["model"], st["ink"], D)[:20]:
        if not time_ok():
            break
        if i >= len(st["model"].paths):
            continue
        wi = st["model"].paths[i].w
        best = None
        for dl in (0.5, 0.9, 1.4):
            cand = move_end(st["model"], i, e, dl * wi)
            if cand is None:
                continue
            s2 = doctor.soft(ink_of(cand))
            if best is None or s2 < best[0]:
                best = (s2, cand)
            elif s2 > best[0]:
                break  # getting worse the further we pull back
        if best is not None and best[0] < st["cur"] - 0.5:
            attempt(best[1], "tips", xy, improve=True)
    # 4e. corners drawn as two strokes -> one stroke with a corner node
    cp = corner_pairs(st["model"])
    if cp:
        c1 = merge_corners(st["model"], cp, D=D)
        if not attempt(c1, "corners", st["model"].paths[cp[0][0]].A[0]):
            sites.pop()
            for pr in cp[:15]:
                if not time_ok():
                    break
                if max(pr[0], pr[2]) < len(st["model"].paths):
                    attempt(merge_corners(st["model"], [pr], D=D), "corners", st["model"].paths[pr[0]].A[0])
    # 4c. round shapes: wobbly circular arcs / near-circles become exact circles and arcs
    for i in range(len(st["model"].paths)):
        if not time_ok() or i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        if p.closed:
            continue
        q0 = arc_fit(p)
        cands_arc = ([q0] if q0 is not None else []) + [q for q in robust_arc_fit(p) if q0 is None or len(q.A) != len(q0.A) or not np.allclose(q.A, q0.A, atol=0.1)]
        if cands_arc:
            xy = p.A[len(p.A) // 2].copy()
            accepted_arc = False
            for q in cands_arc[:4]:
                c1 = st["model"].copy()
                c1.paths[i] = q
                if attempt(c1, "arcs", xy, tol=max(3.0, 0.01 * st["cur"])):
                    accepted_arc = True
                    break
                sites.pop()
            if not accepted_arc:
                sites.append(dict(kind="arcs", x=float(xy[0]), y=float(xy[1]), fixed=False))
    for i, p in enumerate(list(st["model"].paths)):
        if i < len(st["model"].paths) and p.closed and len(p.segs()) >= 3:
            c1 = E.circle(st["model"], i, max_dev=max(0.9, 0.12 * p.w), robust=True)
            q = c1.paths[i]
            if len(q.segs()) == 4 and (len(p.segs()) != 4 or not np.allclose(q.A, p.A, atol=0.05)):
                attempt(c1, "circles", p.A.mean(0), tol=max(3.0, 0.01 * st["cur"], 0.025 * p.length()))
    # 4d. collapse multi-node straight runs and redundant intermediate nodes on straight/smooth segments
    for i in range(len(st["model"].paths)):
        if i >= len(st["model"].paths):
            break
        p = st["model"].paths[i]
        if p.closed and len(p.segs()) == 4 and E.fit_ellipse(p.flat()) is not None:
            continue
        q2, q1 = collapse_straight_runs(p)
        for q_cand in (q2, q1):
            if len(q_cand.A) < len(st["model"].paths[i].A):
                cand = st["model"].copy()
                cand.paths[i] = q_cand
                xy = p.A[len(p.A) // 2].copy()
                if attempt(cand, "density", xy):
                    break
                sites.pop()
        if time_ok():
            simplify_path_segments(st, i, doctor, ink_of, start, drift_cap, sites, skip=skip)
    # 5. specks
    for i, xy in sorted(speck_paths(st["model"]), key=lambda t: -t[0]):
        if i < len(st["model"].paths):
            attempt(E.remove_path(st["model"], i), "specks", xy, tol=0.6 * w)
    # 6. hot spots: re-fit harder, then redraw locally
    regs = sorted(doctor.regions(st["ink"], win=9), key=lambda r: -r[4])[:max_hot]
    for r in regs:
        if not time_ok():
            break
        xy = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        box = [int(r[0]), int(r[1]), int(r[2]), int(r[3])]
        before = st["cur"]
        if attempt(E.refine_region(st["model"], D, box, taus=(0.8, 0.5, 0.35, 0.28), iters=60), "hotspots", xy, improve=True):
            continue
        sites.pop()
        cand = _redraw_region(st["model"], D, box, w)
        if not attempt(cand, "hotspots", xy, improve=True):
            pass
    # 7. final junction Z-fold & straightness polish
    for i, xy in z_fold_paths(st["model"]):
        if i < len(st["model"].paths):
            for zcand in fix_z_fold_cands(st["model"], i):
                if attempt(zcand, "handles", xy, tol=max(12.0, 0.025 * st["cur"])):
                    break
                sites.pop()
    for i, xy in wobbly_straights(st["model"]):
        if i < len(st["model"].paths):
            attempt(make_straight(st["model"], i), "straighten", xy, tol=max(12.0, 0.025 * st["cur"]))
    st["model"] = T.prune_all_apexes(st["model"])
    found = len(sites)
    fixed = sum(s["fixed"] for s in sites)
    return st["model"], st["ink"], st["cur"], dict(sites=sites, found=found, fixed=fixed, drift=float(st["cur"] - start))


def _redraw_region(m: Model, D, box, w, margin=None):
    """Replace the paths that lie (almost) entirely inside `box` by a fresh trace of the source ink inside it."""
    from .trace import refined_branches
    from .chains import build_chains
    from .fitting import initial_model
    margin = int(1.2 * w) if margin is None else margin
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    inside = []
    for i, p in enumerate(m.paths):
        f = p.flat(2.0)
        ok = (f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)
        if ok.mean() > 0.9:
            inside.append(i)
    if not inside:
        return None
    mask = np.zeros(D.shape, np.float32)
    mask[max(y0, 0):y1, max(x0, 0):x1] = 1
    Dc = (D * mask).astype(np.float32)
    br = refined_branches(Dc)
    if not br:
        return None
    chains, _ = build_chains(br)
    nm = initial_model(chains, Dc, sigma=2.0)
    if not nm.paths:
        return None
    keep = [p for i, p in enumerate(m.paths) if i not in set(inside)]
    out = Model(keep + nm.paths, m.width, m.height)
    return T.weld_all(out)



================================================================================
# FILE: linework/joincheck.py
================================================================================

"""Join Checker engine.

Flow (after the Finisher):  find every join  ->  check each join on its own  ->  all PASS: output unchanged
                                                                             ->  some FAIL: Repair Toolbox, then check again.

A join is one of
  T  an end that lands on another stroke           (pass: end lies ON that stroke's centerline)
  L  two ends that meet in one point (a corner)    (pass: they are ONE stroke with a corner node - merged)
  Y  three or more ends that meet (hub / star)     (pass: all ends meet in one common point)
  X  a straight stroke cut where another crosses   (pass: it is one continuous stroke - joined)
and every join must additionally have no hook / jog, no nub (cap poking out) and no lump / hole of ink compared with the source.

The Repair Toolbox mirrors the three Illustrator tool groups:
  shape_builder  merge / trim overlaps and extra ink            (merge_corners, tip retract, nub tuck)
  line_arc       rebuild a segment as an exact line or arc      (fix_end, join_pairs, make straight, arc_fit)
  pen            node surgery: move / add / delete anchors      (snap_end, junction_snap, cut hook + re-anchor)
Every candidate is verified: global match to the source must not get worse, topology must not get worse and the number of
failing joins must go down.  Nothing is ever kept that the check cannot confirm.
"""
from __future__ import annotations
import numpy as np
from .model import Model, Path
from . import finisher as FN
from . import edit as E
from . import topology as T

# tolerances (fractions of the stroke width w)
ON_CENTER = 0.15
CLUSTER = 0.9
REACH = 1.6
Y_SPREAD = 0.25
INK_FRAC = 0.75

REASONS = ("off_center", "corner_split", "y_spread", "split", "hook", "nub", "lump", "hole")
# which tool groups are tried (in order) for a reason
PLAN = {
    "off_center": ("pen", "line_arc", "shape_builder"),
    "hook": ("shape_builder", "pen", "line_arc"),
    "split": ("line_arc", "shape_builder"),
    "corner_split": ("shape_builder",),
    "y_spread": ("shape_builder", "pen", "line_arc"),
    "lump": ("shape_builder", "pen"),
    "nub": ("shape_builder", "pen"),
    "hole": ("pen", "line_arc"),
}


# ------------------------------------------------------------------ geometry helpers
def _ends(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        out += [(i, 0, p.A[0].copy(), p.w), (i, 1, p.A[-1].copy(), p.w)]
    return out


def _dir(p: Path, e: int):
    """Unit direction of the stroke pointing OUT of end e (measured outside the junction zone when possible)."""
    g = FN.end_geometry(p, e)
    if g is not None:
        return g[1] / max(np.linalg.norm(g[1]), 1e-9)
    f = p.flat(1.0)
    t = f[0] - f[min(len(f) - 1, 6)] if e == 0 else f[-1] - f[max(0, len(f) - 7)]
    return t / max(np.linalg.norm(t), 1e-9)


class _Trees:
    def __init__(self, m):
        self.m, self.c = m, {}

    def get(self, skip):
        if skip not in self.c:
            self.c[skip] = FN._others_tree(self.m, skip)
        return self.c[skip]


def snap_end(m: Model, i, e, X):
    """Pen tool: move the end anchor of path i to X (its handle travels with it)."""
    m = m.copy()
    p = m.paths[i]
    q = p if e == 1 else FN._reversed(p)
    v = np.asarray(X, float) - q.A[-1]
    q.A[-1] = q.A[-1] + v
    q.Hin[-1] = q.Hin[-1] + v
    m.paths[i] = q if e == 1 else FN._reversed(q)
    return m


def common_point(ends_pts, dirs):
    """Least-squares point closest to the lines through each end along its direction (None when the lines are parallel)."""
    A = np.zeros((2, 2))
    b = np.zeros(2)
    for a, t in zip(ends_pts, dirs):
        M = np.eye(2) - np.outer(t, t)
        A += M
        b += M @ a
    if abs(np.linalg.det(A)) < 1e-3:
        return None
    return np.linalg.solve(A, b)


def junction_snap(m: Model, ends, max_move=REACH):
    """Pen tool: move all given ends (i, e) to their common intersection point. Returns the model or None."""
    pts = [m.paths[i].A[0 if e == 0 else -1] for i, e in ends]
    w = max(m.paths[i].w for i, e in ends)
    X = common_point(pts, [_dir(m.paths[i], e) for i, e in ends])
    cen = np.mean(pts, axis=0)
    if X is None or np.linalg.norm(X - cen) > max_move * w:
        X = cen
    for a in pts:
        if np.linalg.norm(X - a) > max_move * w:
            return None
    out = m
    for i, e in ends:
        out = snap_end(out, i, e, X)
    return out


# ------------------------------------------------------------------ find + check
def inspect(m: Model, D, ink):
    """All joins of the model with their check result: [dict(kind, x, y, ends, reasons, w, target)]. reasons == [] means PASS."""
    ends = _ends(m)
    n = len(ends)
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for a in range(n):
        for b in range(a + 1, n):
            ia, _, pa, wa = ends[a]
            ib, _, pb, wb = ends[b]
            if ia != ib and np.linalg.norm(pa - pb) <= CLUSTER * max(wa, wb) and abs(wa - wb) <= 0.35 * max(wa, wb):
                par[find(a)] = find(b)
    groups = {}
    for k in range(n):
        groups.setdefault(find(k), []).append(k)

    trees = _Trees(m)
    joints = []

    def through(c, skip_paths, w):
        for j, q in enumerate(m.paths):
            if j in skip_paths:
                continue
            f = q.flat(1.0)
            if np.linalg.norm(f - c, axis=1).min() < 0.7 * w:
                return True
        return False

    singles = []
    for g in groups.values():
        if len(g) == 1:
            singles.append(g[0])
            continue
        pts = np.array([ends[k][2] for k in g])
        c = pts.mean(0)
        w = max(ends[k][3] for k in g)
        if through(c, {ends[k][0] for k in g}, w):
            singles += g
            continue
        es = [(ends[k][0], ends[k][1]) for k in g]
        kind = "L" if len(g) == 2 else "Y"
        reasons = []
        spread = float(np.linalg.norm(pts - c, axis=1).max())
        if kind == "L":
            reasons.append("corner_split")
        elif spread > Y_SPREAD * w:
            reasons.append("y_spread")
        joints.append(dict(kind=kind, x=float(c[0]), y=float(c[1]), ends=es, reasons=reasons, w=float(w), target=None))
    for k in singles:
        i, e, a, w = ends[k]
        tree, P, own = trees.get(i)
        if tree is None:
            continue
        d, kk = tree.query(a)
        if d > REACH * w:
            continue
        X = P[kk].copy()
        if d > 0.5 * w:
            v = (X - a) / max(d, 1e-9)
            if float(_dir(m.paths[i], e) @ v) < 0.5:  # not pointing at it: a free end close to another stroke
                continue
        reasons = ["off_center"] if d > ON_CENTER * w + 0.2 else []
        joints.append(dict(kind="T", x=float(a[0]), y=float(a[1]), ends=[(i, e)], reasons=reasons, w=float(w), target=X))
    # collinear pieces of one straight stroke that were left cut at a crossing
    for (i, ei, j, ej) in FN.collinear_pairs(m, D):
        a = m.paths[i].A[0 if ei == 0 else -1]
        b = m.paths[j].A[0 if ej == 0 else -1]
        c = 0.5 * (a + b)
        joints.append(dict(kind="X", x=float(c[0]), y=float(c[1]), ends=[(i, ei), (j, ej)], reasons=["split"],
                           w=float(max(m.paths[i].w, m.paths[j].w)), target=None))
    hk = {(i, e) for _, i, e, _ in FN.end_hooks(m)}
    nb = {(i, e) for _, i, e, _ in FN.cap_hits(m)}
    H, W = ink.shape
    for jn in joints:
        for es in jn["ends"]:
            if es in hk and "hook" not in jn["reasons"]:
                jn["reasons"].append("hook")
            if es in nb and "nub" not in jn["reasons"]:
                jn["reasons"].append("nub")
        if jn["kind"] != "X":
            r = int(max(3, 1.5 * jn["w"]))
            x0, x1 = int(max(jn["x"] - r, 0)), int(min(jn["x"] + r + 1, W))
            y0, y1 = int(max(jn["y"] - r, 0)), int(min(jn["y"] + r + 1, H))
            if x1 > x0 and y1 > y0:
                extra = float(((ink[y0:y1, x0:x1] > 0.5) & (D[y0:y1, x0:x1] < 0.3)).sum())
                miss = float(((ink[y0:y1, x0:x1] < 0.5) & (D[y0:y1, x0:x1] > 0.7)).sum())
                if extra > INK_FRAC * jn["w"] ** 2:
                    jn["reasons"].append("lump")
                if miss > INK_FRAC * jn["w"] ** 2:
                    jn["reasons"].append("hole")
    return joints


def bad_count(joints):
    return sum(len(j["reasons"]) for j in joints)


# ------------------------------------------------------------------ Repair Toolbox
def _refine_on_line(P, own, k, a, t):
    """Exact point where the ray a + s t meets the centerline polyline near sample k (the samples are 0.5 px apart, so snapping to a
    sample alone would be off by a fraction of a pixel). Falls back to the sample itself."""
    best, bd = P[k].copy(), 1e18
    for kk in (k - 1, k):
        if kk < 0 or kk + 1 >= len(P) or own[kk] != own[k] or own[kk + 1] != own[k]:
            continue
        b0, b1 = P[kk], P[kk + 1]
        d = b1 - b0
        den = t[1] * d[0] - t[0] * d[1]
        if abs(den) < 1e-9:
            continue
        v = b0 - a
        u = (t[0] * v[1] - t[1] * v[0]) / den  # position along the segment
        if -1e-6 <= u <= 1 + 1e-6:
            X = b0 + u * d
            if np.linalg.norm(X - P[k]) < bd:
                best, bd = X, np.linalg.norm(X - P[k])
    return best


def _ray_target(m, i, e, w, trees):
    """Where the stroke's own straight direction meets the centerline it joins (falls back to the nearest point)."""
    p = m.paths[i]
    tree, P, own = trees.get(i)
    if tree is None:
        return None
    a = p.A[0 if e == 0 else -1]
    t = _dir(p, e)
    s = np.arange(-1.0 * w, REACH * w, 0.25)
    d, k = tree.query(a + s[:, None] * t)
    j = int(np.argmin(d))
    if d[j] < 0.5 * w:
        return _refine_on_line(P, own, int(k[j]), a, t)
    d0, k0 = tree.query(a)
    return P[k0].copy() if d0 <= REACH * w else None


def tool_pen(m, jn, reason, D=None):
    out, trees = [], _Trees(m)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "corner_split"):
        c = junction_snap(m, jn["ends"])
        if c is not None:
            out.append(c)
    if jn["kind"] == "T" and reason in ("off_center", "hole", "lump", "nub"):
        i, e = jn["ends"][0]
        X = _ray_target(m, i, e, m.paths[i].w, trees)
        if X is not None:
            out.append(snap_end(m, i, e, X))
    if reason == "hook":
        for i, e in jn["ends"]:
            cut = FN.move_end(m, i, e, 1.4 * m.paths[i].w)
            if cut is not None:
                out.append(cut)
                if jn["target"] is not None:
                    out.append(snap_end(cut, i, e, jn["target"]))
    if reason in ("lump", "nub") and jn["kind"] in ("L", "Y"):  # delete the last anchor stub of every end at the join
        c = m
        for i, e in jn["ends"]:
            r = FN.move_end(c, i, e, 0.5 * c.paths[i].w)
            c = r if r is not None else c
        if c is not m:
            out.append(c)
    return out


def tool_line_arc(m, jn, reason, D=None):
    out = []
    if reason in ("hook", "off_center", "hole"):
        for i, e in jn["ends"]:
            c = FN.fix_end(m, i, e)
            if c is not None:
                out.append(c)
    if reason == "split" and jn["kind"] == "X":
        (i, ei), (j, ej) = jn["ends"]
        out.append(FN.join_pairs(m, [(i, ei, j, ej)]))
        if D is not None:
            all_pairs = FN.collinear_pairs(m, D)
            if len(all_pairs) > 1:
                out.append(FN.join_pairs(m, all_pairs))
    for i, e in jn["ends"]:  # rebuild the whole stroke as an exact line / exact arc, then it is re-checked
        p = m.paths[i]
        f = p.flat(1.0)
        a, b = f[0], f[-1]
        L = np.linalg.norm(b - a)
        if L > 2 * p.w:
            dev = np.abs((f[:, 0] - a[0]) * (b[1] - a[1]) - (f[:, 1] - a[1]) * (b[0] - a[0])).max() / L
            if dev <= 0.35 * p.w and len(p.A) > 2:
                out.append(FN.make_straight(m, i))
        q = FN.arc_fit(p)
        if q is not None:
            c = m.copy()
            c.paths[i] = q
            out.append(c)
    return out


def tool_shape_builder(m, jn, reason, D=None):
    out = []
    if reason == "corner_split" and jn["kind"] == "L":
        (i, ei), (j, ej) = jn["ends"]
        out.append(FN.merge_corners(m, [(i, ei, j, ej)]))
        c = junction_snap(m, jn["ends"])
        if c is not None:
            out.append(FN.merge_corners(c, [(i, ei, j, ej)]))
    if jn["kind"] in ("Y", "L"):
        ends = jn["ends"]
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        out.append(FN.merge_corners(m, [(ia, ea, ib, eb)]))
    if reason in ("off_center", "y_spread", "nub"):  # a stub shorter than ~2.5 w that is one of the join's ends: delete it (Shape Builder: delete region)
        for i in sorted({i for i, e in jn["ends"]}, reverse=True):
            if m.paths[i].length() < 2.5 * m.paths[i].w:
                out.append(E.remove_path(m, i))
    if reason == "hook":
        for i, e in jn["ends"]:
            p = m.paths[i]
            if len(p.A) > 2:
                p_drop = p.copy()
                if e == 0:
                    p_drop.A = p.A[1:].copy(); p_drop.Hin = p.Hin[1:].copy(); p_drop.Hout = p.Hout[1:].copy()
                else:
                    p_drop.A = p.A[:-1].copy(); p_drop.Hin = p.Hin[:-1].copy(); p_drop.Hout = p.Hout[:-1].copy()
                c = m.copy()
                c.paths[i] = p_drop
                out.append(c)
                pt = p_drop.A[0 if e == 0 else -1]
                for j, q in enumerate(m.paths):
                    if j != i and not q.closed:
                        for ej in (0, 1):
                            q_pt = q.A[0 if ej == 0 else -1]
                            if np.linalg.norm(pt - q_pt) <= 1.5 * max(p.w, q.w):
                                mid = 0.5 * (pt + q_pt)
                                c_snap = c.copy()
                                if e == 0:
                                    c_snap.paths[i].A[0] = mid; c_snap.paths[i].Hin[0] = mid; c_snap.paths[i].Hout[0] = mid
                                else:
                                    c_snap.paths[i].A[-1] = mid; c_snap.paths[i].Hin[-1] = mid; c_snap.paths[i].Hout[-1] = mid
                                if ej == 0:
                                    c_snap.paths[j].A[0] = mid; c_snap.paths[j].Hin[0] = mid; c_snap.paths[j].Hout[0] = mid
                                else:
                                    c_snap.paths[j].A[-1] = mid; c_snap.paths[j].Hin[-1] = mid; c_snap.paths[j].Hout[-1] = mid
                                out.append(FN.merge_corners(c_snap, [(i, e, j, ej)]))
    if jn["kind"] in ("X", "Y"):
        ends = jn["ends"]
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    out.append(FN.join_pairs(m, [(ia, ea, ib, eb)]))
    if reason == "lump":
        for i, e in jn["ends"]:
            for f in (0.5, 0.9, 1.4):
                c = FN.move_end(m, i, e, f * m.paths[i].w)
                if c is not None:
                    out.append(c)
    if reason == "nub":
        for i, e in jn["ends"]:
            r = FN.best_end_move(m, i, e, m.paths[i].w)
            if r is not None:
                out.append(r[0])
            for f in (0.5, 1.0, 1.5, 2.0):
                c = FN.move_end(m, i, e, f * m.paths[i].w)
                if c is not None:
                    out.append(c)
    if jn["kind"] in ("Y", "L") and reason in ("y_spread", "nub", "corner_split"):
        ends = jn["ends"]
        pairs_to_merge = []
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                ia, ea = ends[a]
                ib, eb = ends[b]
                if ia != ib:
                    pa = m.paths[ia].A[0 if ea == 0 else -1]
                    pb = m.paths[ib].A[0 if eb == 0 else -1]
                    if np.linalg.norm(pa - pb) <= 1.5:
                        pairs_to_merge.append((ia, ea, ib, eb))
        if len(pairs_to_merge) > 1:
            try:
                out.append(FN.merge_corners(m, pairs_to_merge))
            except Exception:
                pass
    return out


TOOLS = dict(shape_builder=tool_shape_builder, line_arc=tool_line_arc, pen=tool_pen)


# ------------------------------------------------------------------ driver
def run(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_rounds=6, max_tries=60, skip=()):
    """Returns (model, ink, soft, report). report = dict(joints, bad_before, bad_after, fixed, items=[...], rounds)."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    start = cur
    topo0 = FN._topo(model)
    joints = inspect(model, D, ink)
    drift_cap = max(0.025 * max(doctor.area, 1), 1.5 * len(joints) * (w ** 2))
    rep = dict(joints=len(joints), bad_before=bad_count(joints), bad_after=bad_count(joints), fixed=0, tries=0, rounds=0, items=[])
    tries = 0
    given_up = set()  # joins no tool could improve (keyed by rounded position)
    for rnd in range(max_rounds):
        rep["rounds"] = rnd + 1
        progress = False
        while time_ok() and tries < max_tries:
            todo = [j for j in joints if j["reasons"] and (round(j["x"]), round(j["y"])) not in given_up]
            if not todo:
                break
            # structural joins first (cut strokes, corners, hubs), then ends landing on a stroke: snapping the ends of a cut stroke
            # onto the crossing centerline would otherwise hide that it is still two pieces
            j0 = min(todo, key=lambda j: ("XLYT".index(j["kind"]), -len(j["reasons"])))
            base_bad = bad_count(joints)
            done = None
            for reason in list(j0["reasons"]):
                if reason in ("nub", "lump", "hole") and j0["kind"] in ("L", "Y") and ("corner_split" in j0["reasons"] or "y_spread" in j0["reasons"]):
                    continue  # at a corner / hub the structural fix (merge, common point) removes these; trimming first only makes it worse
                for tool in PLAN.get(reason, ()):
                    if tool in skip:
                        continue
                    best = None
                    for cand in TOOLS[tool](model, j0, reason, D=D):
                        if cand is None:
                            continue
                        tries += 1
                        ink2 = ink_of(cand)
                        s2 = doctor.soft(ink2)
                        t2 = FN._topo(cand)
                        if t2 > topo0:  # same weld fallback as the Finisher: a cut / merge may open a hairline gap
                            cw = T.weld_all(cand)
                            if FN._topo(cw) <= topo0:
                                cand = cw
                                ink2 = ink_of(cand)
                                s2 = doctor.soft(ink2)
                                t2 = FN._topo(cand)
                        if t2 > topo0:
                            continue
                        allow = (1.8 if j0["kind"] == "X" else 1.0) * j0["w"] ** 2
                        if s2 > cur + max(2.0, 0.003 * cur, allow) or (s2 - start) > drift_cap:
                            continue
                        jn2 = inspect(cand, D, ink2)
                        b2 = bad_count(jn2)
                        is_better = (b2 < base_bad) or (b2 <= base_bad and (len(cand.paths) < len(model.paths) or t2 < topo0))
                        if is_better:
                            key = (b2, t2, len(cand.paths), s2)
                            if best is None or key < best[0]:
                                best = (key, cand, ink2, s2, jn2)
                    if best is not None:
                        done = (tool, reason, best)
                        break
                if done:
                    break
            rep["items"].append(dict(kind=j0["kind"], x=j0["x"], y=j0["y"], reasons=list(j0["reasons"]), fixed=done is not None,
                                     tool=done[0] if done else None))
            if done:
                _, _, (key, cand, ink2, s2, jn2) = done
                model, ink, cur, joints = cand, ink2, s2, jn2
                topo0 = min(topo0, FN._topo(model))
                rep["fixed"] += 1
                progress = True
            else:
                given_up.add((round(j0["x"]), round(j0["y"])))
        if not progress:
            break
    rep["tries"] = tries
    rep["bad_after"] = bad_count(joints)
    rep["failing"] = [dict(kind=j["kind"], x=j["x"], y=j["y"], reasons=j["reasons"]) for j in joints if j["reasons"]]
    return model, ink, cur, rep



================================================================================
# FILE: linework/pipeline.py
================================================================================

"""Orchestration: image -> icons -> (trace -> chains -> fit) -> Edit/Output/Doctor loop -> SVG."""
from __future__ import annotations
import time, json
from dataclasses import dataclass, asdict, field
import numpy as np, cv2

from .trace import ink_map, refined_branches
from .chains import build_chains
from .fitting import initial_model, add_dots
from .doctor import Doctor, ink_of
from .model import Model
from . import edit as E
from . import rings as RG
from . import repair as RP
from . import finisher as FN
from . import structfix as SF
from . import structure as ST
from . import joints as JN
from . import lessons as LS
from .split import find_icons, crop_icon, estimate_width

PRESETS = {
    "fast": dict(max_rounds=0, time_budget=25, region_edits=0, iters=18, taus=(1.0, 0.45)),
    "standard": dict(max_rounds=2, time_budget=90, region_edits=4, iters=22, taus=(1.0, 0.5, 0.35)),
    "precise": dict(max_rounds=5, time_budget=240, region_edits=8, iters=45, taus=(1.2, 0.8, 0.5, 0.34)),
}


@dataclass
class Options:
    quality: str = "standard"
    target_iou: float = 0.995
    sens: float = 6.0
    merge: float = 1.15
    sigma: float = 2.0
    max_rounds: int | None = None
    time_budget: float | None = None
    region_edits: int | None = None
    repair: bool = True  # final safety net for missing / stray pieces
    max_stroke: float = 14.0  # sources with thicker strokes (big / hi-res sheets) are processed at norm_stroke and scaled back
    norm_stroke: float = 10.0
    memory: bool = True  # remember best results / lessons between runs (linework/lessons.py)
    fresh: bool = False  # do not re-use a stored result for the same icon (still never return something worse than the stored best)
    set_stroke: float = 0.0  # stroke width of the whole set (set by process_sheet); the Finisher snaps close widths to it
    structure: bool = True  # Structure engine: compare centre-line skeletons of source and render, repair lumps / wobble / fused strokes (linework/structfix.py)
    joins: bool = True  # Join engine: build every joint, check it, repair failures with the pen / line / arc / shape tools (linework/joints.py)
    finish: bool = True  # Finisher engine: per-icon inspection of the last few machine-made spots
    rings: bool = True  # detect exact circles in the image and snap strokes onto them
    trace_good: float = 0.968  # stop trying trace settings once the first render matches this well
    trace_ok: float = 0.93  # ... or at least this well (then the optimiser does the rest; saves ~10 s per dense icon)
    superres: int | None = None  # trace at k-times resolution (auto: thin strokes get 2-3x)
    dedupe_tol: float = 0.0025  # fraction of ink area we will sacrifice to remove a duplicate centerline

    def resolved(self):
        p = dict(PRESETS.get(self.quality, PRESETS["standard"]))
        for k in ("max_rounds", "time_budget", "region_edits"):
            if getattr(self, k) is not None:
                p[k] = getattr(self, k)
        return p


def _noop(**k):
    pass


def _key(model, cmd):
    """Geometry-based identity of a command so a rejected ('waived') fix is not retried forever."""
    op = cmd["op"]
    if op == "refine_region":
        b = cmd["box"]
        return (op, round(b[0] / 12), round(b[1] / 12), round(b[2] / 12), round(b[3] / 12))
    if op == "weld":
        return (op,)
    i = cmd.get("path")
    if i is None or i < 0 or i >= len(model.paths):
        return (op,)
    p = model.paths[i]
    j = cmd.get("anchor", 0)
    if j is None or j >= len(p.A):
        return (op, i)
    a = p.A[j]
    return (op, round(float(a[0])), round(float(a[1])), len(p.A), cmd.get("end"))


def process_icon(gray, opts: Options = None, emit=_noop, name="icon"):
    """gray: uint8 crop of ONE icon. Runs the Edit -> Output -> Doctor loop. Returns dict(model, svg, metrics).
    * A source whose stroke is wider than opts.max_stroke is shrunk to opts.norm_stroke, processed and scaled back (the vector is resolution independent).
    * Memory (linework/lessons.py): the best result ever made for this exact icon is the floor; same version = instant re-use."""
    from . import __version__
    opts = opts or Options()
    use_mem = opts.memory and LS.enabled()
    key = LS.crop_key(gray, opts.quality, opts.set_stroke) if use_mem else None
    prev = LS.best_get(key) if use_mem else None
    if prev and prev.get("version") == __version__ and not opts.fresh:
        m = Model.from_json(prev["model"])
        emit(engine="doctor", msg="Re-used the stored result for this icon (same version)", icon=name, iou=prev["metrics"].get("iou"), final=True)
        met = dict(prev["metrics"], from_memory=True)
        return dict(model=m, svg=m.svg(), metrics=met)
    r = _process_icon_scaled(gray, opts, emit, name)
    if use_mem:
        LS.log_icon(name, r["metrics"], __version__)
        if not opts.fresh and prev and prev["score"] > LS.quality_score(r["metrics"]) + 0.0005:
            m = Model.from_json(prev["model"])
            emit(engine="doctor", msg=f"Stored result from an earlier run is better ({prev['metrics'].get('iou', 0)*100:.2f}% vs {r['metrics']['iou']*100:.2f}%): kept it", icon=name, iou=prev["metrics"].get("iou"), final=True)
            return dict(model=m, svg=m.svg(), metrics=dict(prev["metrics"], from_memory=True))
        LS.best_put(key, r["model"].to_json(), r["metrics"], __version__)
    return r


def _process_icon_scaled(gray, opts, emit, name):
    w0 = estimate_width(ink_map(gray))
    if w0 <= opts.max_stroke:
        return _process_icon(gray, opts, emit, name, set_w=(opts.set_stroke or None))
    k = opts.norm_stroke / w0
    H, W = gray.shape
    small = cv2.resize(gray, (max(8, int(round(W * k))), max(8, int(round(H * k)))), interpolation=cv2.INTER_AREA)
    emit(engine="trace", msg=f"High-resolution source (stroke {w0:.0f}px): working at {k:.2f}x, result scaled back", icon=name)
    r = _process_icon(small, opts, emit, name, set_w=(opts.set_stroke * k if opts.set_stroke else None))
    m = r["model"].scaled(W / small.shape[1], width=W, height=H)
    D = ink_map(gray)
    doc = Doctor(D)
    iou = doc.iou(ink_of(m))  # at the full source resolution: stricter (a 1 px shift of a 45 px stroke counts), kept as iou_full
    r["metrics"].update(iou_full=iou, scale=float(k), stroke_width=float(r["metrics"].get("stroke_width", 0) * W / small.shape[1]))
    return dict(model=m, svg=m.svg(), metrics=r["metrics"])


def _process_icon(gray, opts: Options = None, emit=_noop, name="icon", set_w=None):
    opts = opts or Options()
    cfg = opts.resolved()
    t0 = time.time()
    D = ink_map(gray)
    H, W = D.shape
    ev = lambda engine, msg, **kw: emit(engine=engine, msg=msg, icon=name, t=round(time.time() - t0, 2), **kw)
    # Budget = CPU time actually spent on this icon (not wall-clock), so quality does not depend on how busy the machine is,
    # how many icons run in parallel, or where in the queue this icon sits.  Complex icons get a larger budget (set below).
    c0 = time.process_time()
    bud = [float(cfg["time_budget"])]
    left = lambda: min(bud[0] - (time.process_time() - c0), 10.0 * bud[0] - (time.time() - t0))  # 2nd term: hang guard only

    ev("trace", "Tracing skeleton and centring strokes on their edges")
    w_est = estimate_width(D)
    doctor = Doctor(D, sens=opts.sens)

    def trace_with(s, sf):
        """Skeleton -> chains -> fitted curves at s-times resolution, scaled back to source pixels."""
        Du = ink_map(cv2.resize(gray, (W * s, H * s), interpolation=cv2.INTER_CUBIC)) if s > 1 else D
        br = refined_branches(Du)
        if not br:
            return None
        chains, W0 = build_chains(br)
        m = initial_model(chains, Du, sigma=opts.sigma * s * sf, err=0.3 * s)
        if s > 1:
            m = m.scaled(1.0 / s, W, H)
            W0 = W0 / s
        return m, W0, len(br), len(chains)

    # No single trace setting suits every icon (e.g. 3x resolution rescues fine gear teeth but can break a spring), so try a few
    # and keep the one whose first render matches the source best; stop as soon as one is good enough.
    if opts.superres:
        cands = [(opts.superres, 0.6 if opts.superres > 1 else 1.0)]
    elif w_est < 8:
        cands = [(3, 0.6), (2, 0.6), (3, 0.35)]
    elif w_est < 14:
        cands = [(2, 0.6), (3, 0.6), (1, 0.6)]
    else:
        cands = [(1, 0.6), (2, 0.6), (1, 1.0)]
    wb = int(min(30, round(w_est)))
    if not opts.superres and opts.memory and not opts.fresh:
        cands = LS.trace_order(wb, cands)
    best = None
    for ci, (s, sf) in enumerate(cands):
        t = trace_with(s, sf)
        if t is None:
            continue
        iou_c = doctor.iou(ink_of(t[0]))
        if best is None or iou_c > best[0]:
            best = (iou_c, s, sf, t)
        if iou_c >= opts.trace_good:
            break
        # another trace is only worth its time when this one is clearly poor (the optimiser evens out small differences)
        if best[0] >= opts.trace_ok:
            break
    if best is None:
        return dict(model=Model([], W, H), svg=Model([], W, H).svg(), metrics=dict(iou=0, error="no ink"))
    _, s, sf, (model, W0, nbr, nch) = best
    if opts.memory and not opts.superres:
        LS.trace_record(wb, (s, sf))
    if len(cands) > 1 and ci > 0:
        ev("trace", f"Tried {ci + 1} trace settings, kept {s}x resolution (first render {best[0]*100:.1f}% match)")
    nd = add_dots(model, D)
    if nd:
        ev("trace", f"{nd} dot(s) detected and added as round-capped points")
    c0 = time.process_time()  # the Edit budget starts after tracing
    bud[0] = float(cfg["time_budget"]) * float(np.clip(sum(q.length() for q in model.paths) / 2500.0, 1.0, 3.0))
    ink = ink_of(model)
    cur = doctor.soft(ink)
    iou0 = doctor.iou(ink)
    ev("trace", f"{nbr} skeleton branches -> {nch} centerline chains, stroke width {W0:.1f}px")
    ev("output", f"Initial render: {iou0*100:.2f}% match", iou=iou0)
    waived = set()
    state = dict(model=model, ink=ink, cur=cur)

    def run(cmd):
        key = _key(state["model"], cmd)
        try:
            new, _ = E.execute(state["model"], cmd, D)
        except (IndexError, KeyError, ValueError):
            waived.add(key)  # stale command (model changed since it was issued)
            return False
        ink2 = ink_of(new)
        s2 = doctor.soft(ink2)
        tol = cmd.get("tol", 0.0)
        if cmd["op"] in ("remove_path", "cut"):
            tol = max(tol, opts.dedupe_tol * doctor.area)
        elif cmd["op"] in ("join", "cap"):
            tol = max(tol, 0.025 * state["cur"], 25.0)
        elif cmd["op"] in ("smooth_anchor", "simplify", "line_snap", "circle", "weld", "merge_nodes", "trim_tail"):
            tol = max(tol, 0.004 * state["cur"], 2.0)
        ok = s2 <= state["cur"] + tol
        if ok:
            state.update(model=new, ink=ink2, cur=s2)
        else:
            waived.add(key)
        return ok

    gap_waived = set()

    def _gkey(a):
        return (a[1], a[2], int(round(a[5][0] / 4)), int(round(a[5][1] / 4)))

    def do_weld():
        """Close junction gaps one at a time; a gap that is also open in the source image is left alone."""
        from . import topology as T
        acts = [a for a in T._plan(state["model"]) if _gkey(a) not in gap_waived]
        n = 0
        for a in acts:
            new = state["model"].copy()
            T._move_end(new.paths[a[1]], a[2], a[5])
            if a[4] is not None:
                T._move_end(new.paths[a[3]], a[4], a[5])
            ink2 = ink_of(new)
            s2 = doctor.soft(ink2)
            if s2 <= state["cur"] + max(2.0, 0.0015 * state["cur"]):
                state.update(model=new, ink=ink2, cur=s2)
                n += 1
            else:
                gap_waived.add(_gkey(a))
        return n, len(acts) - n

    def open_gaps(rep):
        return [a for a in rep["gaps"] if _gkey(a) not in gap_waived]

    def open_all(rep):
        """Hide issues the Doctor already tried to fix and had rejected (they are real features of the source)."""
        rep["gaps"] = open_gaps(rep)
        mod = state["model"]
        rep["notches"] = [i for i in rep["notches"] if _key(mod, dict(op="merge_nodes", path=i)) not in waived]
        rep["spurs"] = [(i, e) for (i, e) in rep["spurs"] if _key(mod, dict(op="trim_tail", path=i, end=e)) not in waived]
        return rep

    def pending(cmds):
        return [c for c in cmds if _key(state["model"], c) not in waived]

    def adopt_rings():
        """Exact circles from the image; each one is kept only if the re-render does not get worse."""
        found = RG.detect_rings(D, w_est)
        ok_n = 0
        for ring in sorted(found, key=lambda r: -r["r"]):
            if left() <= 0:
                break
            if ring["r"] < 0.8 * w_est:
                continue
            new = RG.apply_ring(state["model"], ring)
            ink2 = ink_of(new)
            s2 = doctor.soft(ink2)
            tol_ring = max(1.0, 0.0005 * state["cur"])
            if ring.get("support", 0.0) >= 0.96 and len(new.paths) <= len(state["model"].paths):
                tol_ring = max(tol_ring, min(115.0, 0.0038 * doctor.area))
            if s2 <= state["cur"] + tol_ring:
                state.update(model=new, ink=ink2, cur=s2)
                ok_n += 1
        return len(found), ok_n

    if opts.rings:
        nf, na = adopt_rings()
        if nf:
            ev("edit", f"Circles: {nf} found in the image, {na} snapped to exact rings (re-rendered, kept only if no worse)", iou=doctor.iou(state["ink"]))

    rounds = 0
    stall = 0
    for rnd in range(cfg["max_rounds"] + 1):
        iou_round_start = doctor.iou(state["ink"])
        rep = doctor.diagnose(state["model"], state["ink"], first_round=(rnd == 0))
        ev("doctor", f"Round {rnd + 1}: {rep['iou']*100:.2f}% match. Found {len(rep['redundant']) + len(rep['tails'])} duplicate centerlines, "
           f"{len(rep['kinks'])} kinks, {len(rep['rings'])} ring(s), {len(rep['regions'])} mismatch regions", iou=rep["iou"], round=rnd + 1, issues=rep["issues"])
        before = state["cur"]
        # (a) duplicate centerlines
        done, ok_n, bad_n = set(), 0, 0
        for cmd in pending(Doctor.commands(rep)):
            if cmd["path"] in done or cmd["path"] >= len(state["model"].paths):
                continue
            done.add(cmd["path"])
            ok = run(cmd)
            ok_n += ok
            bad_n += not ok
        if ok_n or bad_n:
            ev("edit", f"Duplicate centerlines: {ok_n} removed, {bad_n} kept (Doctor: removal would lose ink)")
        # (b) global gradient fit of every control point and width
        if rnd == 0 or cfg["max_rounds"] > 0:
            if left() > 0:
                it, tau = cfg["iters"], cfg["taus"]
                if rnd >= 1:  # warm start from the previous round: only the sharp stages, fewer iterations
                    it, tau = max(12, int(it * 0.6)), tau[-2:]
                ok = run(dict(op="refine_all", kw=dict(iters=it, taus=tau), tol=0.0))
                ev("edit", "Gradient fit of all control points + widths " + ("accepted" if ok else "rejected"), iou=doctor.iou(state["ink"]))
        # (c) cosmetic repairs
        rep = doctor.diagnose(state["model"], state["ink"], first_round=(rnd == 0))
        ap = rj = 0
        open_all(rep)
        for cmd in pending(Doctor.cosmetic_commands(rep)):
            if cmd["op"] == "weld":
                a_, r_ = do_weld()
                ap += a_
                rj += r_
                continue
            if cmd["path"] >= len(state["model"].paths):
                continue
            ok = run(cmd)
            ap += ok
            rj += not ok
        if ap or rj:
            ev("edit", f"Rings, kinks, straight lines, node count: {ap} applied, {rj} rejected by Doctor")
        ev("output", f"Rendered: {doctor.iou(state['ink'])*100:.2f}% match", iou=doctor.iou(state["ink"]))
        rounds = rnd + 1
        # (d) local re-fits where the Doctor still sees mismatch
        if cfg["region_edits"] and left() > 0:
            rep = doctor.diagnose(state["model"], state["ink"])
            ap = rj = 0
            for cmd in pending(Doctor.region_commands(rep, cfg["region_edits"])):
                if left() <= 0:
                    break
                ok = run(cmd)
                ap += ok
                rj += not ok
            if ap or rj:
                ev("edit", f"Local re-fit of {ap + rj} mismatch regions: {ap} accepted, {rj} rejected", iou=doctor.iou(state["ink"]))
        gain = doctor.iou(state["ink"]) - iou_round_start
        if state["cur"] > before * 0.995 or (rnd >= 1 and gain < 0.0025):
            stall += 1
        else:
            stall = 0
        if cfg["max_rounds"] == 0 or stall >= 1 or left() <= 0:
            break
        rep = doctor.diagnose(state["model"], state["ink"])
        if rep["issues"] == 0 or (doctor.iou(state["ink"]) >= opts.target_iou and not (rep["redundant"] or rep["tails"])):
            break

    model, ink = state["model"], state["ink"]
    # final guard: never ship a duplicate centerline
    for cmd in pending(Doctor.commands(doctor.diagnose(model, ink))):
        if cmd["path"] < len(state["model"].paths):
            run(cmd)
    # safety net: big missing pieces are traced and added, big stray pieces removed (each verified by a re-render)
    nm = nr = 0
    if opts.repair and left() > -1e9:
        m2, ink2, cur2, nm, nr = RP.repair(state["model"], D, ink_of, doctor.soft, state["cur"], W0)
        if nm or nr:
            state.update(model=m2, ink=ink2, cur=cur2)
            ev("doctor", f"Safety net: {nm} missing piece(s) restored, {nr} stray piece(s) removed", iou=doctor.iou(ink2))
    # Structure engine: skeleton of the render vs skeleton of the source; lumps, wobble, fused or displaced strokes are snapped / smoothed / re-traced
    sx = dict(before=0.0, after=0.0, found=0, fixed=0, sites=[], unresolved=[])
    if opts.structure:
        sc0 = time.process_time()
        scap = max(6.0, 0.2 * bud[0])
        m6, ink6, cur6, sx = SF.run_structure_engine(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - sc0 < scap,
                                                    memory_skip=(LS.skip_kinds() if opts.memory else ()))
        if sx["fixed"]:
            state.update(model=m6, ink=ink6, cur=cur6)
        ev("doctor", f"Structure check: score {sx['before']:.2f} -> {sx['after']:.2f}, {sx['fixed']}/{sx['found']} site(s) repaired, {len(sx['unresolved'])} left for review", iou=doctor.iou(state["ink"]))
    # Finisher: inspect this icon on its own and fix the few places that still look machine-made (each fix verified)
    fin = dict(found=0, fixed=0, sites=[])
    if opts.finish:
        fc0 = time.process_time()
        fcap = max(8.0, 0.25 * bud[0])
        m3, ink3, cur3, fin = FN.finish(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - fc0 < fcap,
                                       set_w=set_w, skip=(LS.skip_kinds() if opts.memory else ()))
        if fin["fixed"]:
            state.update(model=m3, ink=ink3, cur=cur3)
        ev("doctor", f"Finisher: {fin['found']} site(s) inspected, {fin['fixed']} fixed", iou=doctor.iou(state["ink"]))
    # Join engine: every joint is checked on its own; failing joints are repaired with the pen / line / arc / shape tools and re-checked
    jn = dict(total=0, clean_first=0, fixed=dict(unite=0, pen=0, line=0, arc=0, shape=0), unresolved=[], built=0)
    if opts.joins:
        jc0 = time.process_time()
        jcap = max(6.0, 0.2 * bud[0])
        m5, ink5, cur5, jn = JN.run_join_engine(state["model"], D, doctor, ink_of, state["cur"], W0, time_ok=lambda: time.process_time() - jc0 < jcap)
        state.update(model=m5, ink=ink5, cur=cur5)
        nf = sum(jn["fixed"].values())
        ev("doctor", f"Join check: {jn['total']} joint(s), {jn['clean_first']} clean at first look, {jn['built']} built, {nf} repaired, {len(jn['unresolved'])} left for review", iou=doctor.iou(state["ink"]))
    # final topology guard: refits above can reopen junctions, so weld/merge/trim once more
    for _ in range(2):
        rep = doctor.diagnose(state["model"], state["ink"])
        open_all(rep)
        cmds = [c for c in Doctor.cosmetic_commands(rep) if c["op"] in ("trim_tail", "merge_nodes", "weld")]
        n = 0
        for cmd in pending(cmds):
            if cmd["op"] == "weld":
                n += do_weld()[0]
            elif cmd["path"] < len(state["model"].paths):
                n += run(cmd)
        if not n:
            break
    if opts.joins:
        m_lock = JN.lock_joints(state["model"])
        ink_lock = ink_of(m_lock)
        s_lock = doctor.soft(ink_lock)
        if s_lock <= state["cur"] + max(4.0, 0.003 * max(doctor.area, 1), 0.006 * state["cur"]):
            state.update(model=m_lock, ink=ink_lock, cur=s_lock)
    model, ink = state["model"], state["ink"]
    rep = doctor.diagnose(model, ink)
    open_all(rep)
    iou = doctor.iou(ink)
    ev("doctor", f"Final: {iou*100:.2f}% match, {len(model.paths)} paths, {sum(len(p.A) for p in model.paths)} nodes", iou=iou, final=True)
    metrics = dict(
        iou=iou, iou_initial=iou0, soft_norm=rep["soft_norm"], paths=len(model.paths), nodes=int(sum(len(p.A) for p in model.paths)),
        stroke_width=float(W0), rounds=rounds, seconds=round(time.time() - t0, 2),
        issues=dict(duplicates=len(rep["redundant"]) + len(rep["tails"]), kinks=len(rep["kinks"]), regions=len(rep["regions"]),
                    gaps=len(rep["gaps"]), notches=len(rep["notches"]), spurs=len(rep["spurs"]), restored=nm, stray=nr),
        finisher=dict(found=fin['found'], fixed=fin['fixed'], sites=fin['sites']),
        structure=dict(before=sx['before'], after=sx['after'], found=sx['found'], fixed=sx['fixed'], unresolved=sx['unresolved']),
        joins=dict(total=jn['total'], clean_first=jn['clean_first'], built=jn['built'], fixed=jn['fixed'], unresolved=jn['unresolved']),
    )
    return dict(model=model, svg=model.svg(), metrics=metrics)


def load_gray(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise ValueError("Unsupported image")
    if im.ndim == 3 and im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        rgb = im[:, :, :3].astype(np.float32) * a + 255 * (1 - a)
        im = rgb.astype(np.uint8)
    if im.ndim == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return im


def process_sheet(gray, opts: Options = None, emit=_noop, worker=None):
    """Process every icon in a sheet. `worker(crop, opts, name)` can be supplied to run icons in parallel."""
    opts = opts or Options()
    D = ink_map(gray)
    w, icons, lab = find_icons(D, merge=opts.merge)
    H, W = gray.shape
    bg = int(np.median(np.r_[gray[0], gray[-1], gray[:, 0], gray[:, -1]]))
    emit(engine="split", msg=f"Found {len(icons)} icon(s), stroke ≈ {w:.1f}px", icons=[ic["box"] for ic in icons], width=w)
    jobs = []
    for k, ic in enumerate(icons):
        crop, off = crop_icon(gray, lab, ic, pad=int(max(2 * w, 14)), bg=bg)
        jobs.append((k, crop, off))
    return W, H, jobs


def second_pass_options(opts: Options) -> dict:
    """Options (as a dict) for the longer second pass that weak icons get: more rounds, more budget, more trace settings tried, no stored result re-use."""
    d = asdict(opts)
    cfg = opts.resolved()
    d.update(fresh=True, max_rounds=max(cfg["max_rounds"], 4), time_budget=cfg["time_budget"] * 2.2, region_edits=max(cfg["region_edits"], 6),
             trace_good=0.985, trace_ok=0.965)
    return d



================================================================================
# FILE: linework/edit.py
================================================================================

"""Edit engine: executes commands issued by the Doctor on a Model and returns a *new* Model.

Commands (dicts):
  remove_path   {path}                      drop a redundant path
  cut           {path, a, b}                drop samples a..b of a path (1px resampled) and refit the rest
  smooth_anchor {path, anchor}              make a near-smooth joint truly G1
  circle        {path}                      replace a ring by an exact ellipse
  simplify      {path, err}                 refit with fewer nodes (keeps sharp corners)
  line_snap     {path}                      straighten segments that are straight within tolerance
  refine_all    {}                          gradient optimiser over every path (control points + widths)
  refine_region {box}                       gradient optimiser restricted to the paths/pixels around a box
  weld          {}                          close junction gaps (corner intersection / T snap)
  merge_nodes   {path}                      collapse micro-segment staircases at corners
  trim_tail     {path, end}                 drop a short curled spur at a stroke end
  join          {path, join}                switch a path between round and miter joins
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.spatial import cKDTree
from .geom import resample, unit, fit_curve, corners, bez, arclen
from .model import Model, Path
from . import opt
from . import topology as T


# ------------------------------------------------------------------ simple structural commands
def remove_path(m: Model, i):
    m = m.copy()
    del m.paths[i]
    return m


def _refit(poly, base: Path, sigma=1.2, err=0.3):
    segs = fit_curve(poly, sigma, err)
    if not segs:
        return None
    p = Path.from_segs(segs, base.w, closed=False, join=base.join)
    p.ml = base.ml
    return p


def cut(m: Model, i, a, b):
    """Remove flat samples [a,b] of path i (1px resampled); keep the pieces that are long enough."""
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 1.0)
    a, b = max(0, int(a)), min(len(f) - 1, int(b))
    pieces = []
    if p.closed:
        g = np.vstack([f[b:], f[: a + 1]]) if a > b else np.vstack([f[b:-1], f[: a + 1]])
        pieces = [g]
    else:
        if a > 2:
            pieces.append(f[: a + 1])
        if len(f) - 1 - b > 2:
            pieces.append(f[b:])
    new = []
    for q in pieces:
        if len(q) >= 4:
            r = _refit(q, p)
            if r:
                new.append(r)
    m.paths[i : i + 1] = new
    return m


def smooth_anchor(m: Model, i, k):
    m = m.copy()
    p = m.paths[i]
    a = p.A[k]
    din, dout = a - p.Hin[k], p.Hout[k] - a
    ln, lo = np.linalg.norm(din), np.linalg.norm(dout)
    if ln < 1e-6 or lo < 1e-6:
        return m
    u = unit(unit(din) + unit(dout))
    p.Hin[k] = a - u * ln
    p.Hout[k] = a + u * lo
    if p.closed and k == 0:
        p.Hin[-1] = p.Hin[0]
        p.Hout[-1] = p.Hout[0]
    return m


def simplify(m: Model, i, err=0.45):
    m = m.copy()
    p = m.paths[i]
    f = resample(p.flat(), 0.75)
    segs = fit_curve(f, 0.8, err)
    if not segs or len(segs) >= len(p.segs()):
        return m
    q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
    q.ml = p.ml
    m.paths[i] = q
    return m


def line_snap(m: Model, i, tol=None):
    m = m.copy()
    p = m.paths[i]
    tol = max(0.35, 0.05 * p.w) if tol is None else tol
    for k, c in enumerate(p.segs()):
        ch = c[3] - c[0]
        L = np.linalg.norm(ch)
        if L < 6:
            continue
        n = np.array([-ch[1], ch[0]]) / L
        dev = max(abs((c[1] - c[0]) @ n), abs((c[2] - c[0]) @ n))
        if dev * 0.75 < tol:  # Bezier max deviation ~ 3/4 of control offset
            p.Hout[k] = c[0] + ch / 3
            p.Hin[k + 1] = c[0] + 2 * ch / 3
    return m


def ellipse_beziers(c, a, b, theta):
    k = 0.5522847498
    ct, st = np.cos(theta), np.sin(theta)
    R = np.array([[ct, -st], [st, ct]])
    base = [(a, 0), (0, b), (-a, 0), (0, -b)]
    tan = [(0, k * b), (-k * a, 0), (0, -k * b), (k * a, 0)]
    A = [c + R @ np.array(p) for p in base] + [c + R @ np.array(base[0])]
    Ho = [A[i] + R @ np.array(tan[i]) for i in range(4)] + [A[4]]
    Hi = [A[0]] + [A[i + 1] - R @ np.array(tan[(i + 1) % 4]) for i in range(4)]
    return np.array(A), np.array(Hi), np.array(Ho)


def fit_ellipse(flat):
    if len(flat) < 8:
        return None
    (cx, cy), (MA, ma), ang = cv2.fitEllipse(flat.astype(np.float32))
    a, b, th = MA / 2, ma / 2, np.radians(ang)
    A, Hi, Ho = ellipse_beziers(np.array([cx, cy]), a, b, th)
    ell = Path(A, Hi, Ho, 1.0, closed=True)
    dev = cKDTree(ell.flat(0.5)).query(flat)[0]
    return ell, float(dev.max()), float(dev.mean())


def robust_ellipse(flat, w, inlier_frac=0.7, iters=5):
    """Ellipse fitted only to the points that agree with it (a ring touched by another stroke gets pulled out of shape by
    the touching part; the rest of the ring still defines the true circle). Returns (Path, inlier_fraction, max_inlier_dev)."""
    if len(flat) < 12:
        return None
    pts = flat
    thr = max(1.5, 0.25 * w)
    for _ in range(iters):
        if len(pts) < 8:
            return None
        (cx, cy), (MA, ma), ang = cv2.fitEllipse(pts.astype(np.float32))
        if min(MA, ma) < 2:
            return None
        A, Hi, Ho = ellipse_beziers(np.array([cx, cy]), MA / 2, ma / 2, np.radians(ang))
        ell = Path(A, Hi, Ho, 1.0, closed=True)
        tree = cKDTree(ell.flat(0.5))
        d = tree.query(flat)[0]
        keep = flat[d < thr]
        if len(keep) == len(pts):
            break
        pts = keep
    frac = float((d < thr).mean())
    return (ell, frac, float(d[d < thr].max())) if frac >= inlier_frac else None


def circle(m: Model, i, max_dev=0.9, robust=False):
    m = m.copy()
    p = m.paths[i]
    r = fit_ellipse(p.flat())
    if robust and (r is None or r[1] > max_dev):
        rr = robust_ellipse(p.flat(), p.w)
        r = (rr[0], rr[2]) if rr else None
        lim = max(max_dev, 1.5, 0.25 * p.w)
    else:
        lim = max_dev
    if r is None or r[1] > lim:
        return m
    ell = r[0]
    ell.w, ell.join = p.w, p.join
    m.paths[i] = ell
    return m


# ------------------------------------------------------------------ gradient optimiser (see opt.py)
def _is_exact_ring(p: Path) -> bool:
    return bool(p.closed and len(p.A) == 4 and np.linalg.norm((p.A[0] + p.A[2]) - (p.A[1] + p.A[3])) < 0.25)


def refine_all(m: Model, D, **kw):
    if kw.get("free") is None:
        non_rings = [i for i, p in enumerate(m.paths) if not _is_exact_ring(p)]
        if 0 < len(non_rings) < len(m.paths):
            kw = dict(kw, free=non_rings)
    return opt.refine(m, D, **kw)


def refine_region(m: Model, D, box, margin=12, **kw):
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    free = []
    for i, p in enumerate(m.paths):
        if _is_exact_ring(p):
            continue
        f = p.flat(2.0)
        if (f[:, 0] > x0 - p.w).any() and (f[:, 0] < x1 + p.w).any():
            inside = (f[:, 0] > x0 - p.w) & (f[:, 0] < x1 + p.w) & (f[:, 1] > y0 - p.w) & (f[:, 1] < y1 + p.w)
            if inside.any():
                free.append(i)
    if not free:
        return m
    kw.setdefault("taus", (0.6, 0.38, 0.3))
    kw.setdefault("iters", 40)
    return opt.refine(m, D, free=free, window=(x0, y0, x1, y1), **kw)


def set_join(m: Model, i, join, ml=10.0):
    m = m.copy()
    m.paths[i].join = join
    m.paths[i].ml = ml
    return m


# ------------------------------------------------------------------ dispatcher
def execute(m: Model, cmd: dict, D=None):
    """Run one command. Returns (new_model, info)."""
    op = cmd["op"]
    if op == "remove_path":
        return remove_path(m, cmd["path"]), None
    if op == "cut":
        return cut(m, cmd["path"], cmd["a"], cmd["b"]), None
    if op == "smooth_anchor":
        return smooth_anchor(m, cmd["path"], cmd["anchor"]), None
    if op == "circle":
        return circle(m, cmd["path"], robust=cmd.get("robust", False)), None
    if op == "simplify":
        return simplify(m, cmd["path"], cmd.get("err", 0.45)), None
    if op == "line_snap":
        return line_snap(m, cmd["path"]), None
    if op == "refine_all":
        return refine_all(m, D, **cmd.get("kw", {})), None
    if op == "refine_region":
        return refine_region(m, D, cmd["box"], **cmd.get("kw", {})), None
    if op == "weld":
        return T.weld_all(m), None
    if op == "merge_nodes":
        return T.merge_nodes(m, cmd["path"]), None
    if op == "trim_tail":
        return T.trim_tail(m, cmd["path"], cmd["end"]), None
    if op == "join":
        return set_join(m, cmd["path"], cmd["join"]), None
    raise ValueError(op)



================================================================================
# FILE: linework/repair.py
================================================================================

"""Safety net: find big pieces of the source that are missing from the render (or big pieces of render that are not in the
source) and repair them.  Run after the Edit/Doctor loop; every repair is verified by a full re-render and kept only if the
mismatch gets smaller.
"""
from __future__ import annotations
import numpy as np, cv2
from .model import Model
from .geom import resample
from .trace import refined_branches
from .chains import build_chains
from .fitting import initial_model


def _chunks(mask, w, min_area):
    """Connected blobs of `mask` that are fat enough to be real strokes (thin edge slivers are removed by an opening)."""
    k = int(max(3, round(0.45 * w)))
    k += (k + 1) % 2
    op = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(op, connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= min_area:
            out.append(lab == i)
    return out


def missing_chunks(D, ink, w):
    return _chunks((D > 0.5) & (ink < 0.5), w, max(1.0 * w * w, 30))


def extra_chunks(D, ink, w):
    return _chunks((ink > 0.5) & (D < 0.3), w, max(1.0 * w * w, 30))


def trace_missing(D, comp, w):
    """Trace only the source ink inside (a dilated copy of) one missing blob; returns new Paths (source pixel coords)."""
    reg = cv2.dilate(comp.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.6 * w) | 1, int(1.6 * w) | 1))) > 0
    Dc = np.where(reg, D, 0).astype(np.float32)
    br = refined_branches(Dc)
    if not br:
        return []
    chains, _ = build_chains(br)
    m = initial_model(chains, Dc, sigma=2.0)
    return m.paths


def repair(model: Model, D, ink_of, soft, state_cur, w, max_items=8):
    """Returns (model, ink, soft, n_added, n_removed). `ink_of(model)` renders; `soft(ink)` is the Doctor's mismatch."""
    cur = state_cur
    ink = ink_of(model)
    added = removed = 0
    for comp in missing_chunks(D, ink, w)[:max_items]:
        new_paths = trace_missing(D, comp, w)
        if not new_paths:
            continue
        cand = Model(model.paths + new_paths, model.width, model.height)
        ink2 = ink_of(cand)
        s2 = soft(ink2)
        if s2 < cur - 0.5:
            model, ink, cur = cand, ink2, s2
            added += 1
    for comp in extra_chunks(D, ink, w)[:max_items]:
        dil = cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        hits = []
        for i, p in enumerate(model.paths):
            f = resample(p.flat(), 1.0)
            xs = np.clip(np.round(f[:, 0] - 0.5).astype(int), 0, dil.shape[1] - 1)
            ys = np.clip(np.round(f[:, 1] - 0.5).astype(int), 0, dil.shape[0] - 1)
            share = float(dil[ys, xs].mean())
            if share > 0.5:
                hits.append(i)
        for i in sorted(hits, reverse=True):
            cand = Model([p for j, p in enumerate(model.paths) if j != i], model.width, model.height)
            ink2 = ink_of(cand)
            s2 = soft(ink2)
            if s2 < cur - 0.5:
                model, ink, cur = cand, ink2, s2
                removed += 1
                break
    return model, ink, cur, added, removed



================================================================================
# FILE: linework/split.py
================================================================================

"""Split an icon sheet into individual icons (connected clusters of ink)."""
from __future__ import annotations
import numpy as np, cv2
from skimage.morphology import skeletonize
from scipy import ndimage as ndi


def estimate_width(D):
    mask = D > 0.5
    if mask.sum() < 50:
        return 8.0
    sk = skeletonize(mask)
    dt = ndi.distance_transform_edt(mask)
    v = dt[sk]
    if v.size == 0:
        return 8.0
    return float(2 * np.median(v))


def find_icons(D, merge=1.15, min_area_w2=6.0):
    """Return (w_est, list of dict(box=(x0,y0,x1,y1), label_mask_fn)) in reading order."""
    mask = (D > 0.5).astype(np.uint8)
    w = estimate_width(D)
    k = int(max(3, round(2 * merge * w)))
    k += (k + 1) % 2
    dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(dil)
    icons = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        ink = int((mask[lab == i]).sum())
        if ink < min_area_w2 * w * w * 0.5:
            continue
        icons.append(dict(id=i, box=[int(x), int(y), int(x + bw), int(y + bh)], ink=ink))
    # an icon sitting entirely inside another icon's box (e.g. the X on a cushion) belongs to it
    def inside(a, b, tol=4):
        return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol
    keep = []
    for ic in sorted(icons, key=lambda c: -((c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]))):
        host = next((h for h in keep if inside(ic["box"], h["box"])), None)
        if host is not None:
            lab[lab == ic["id"]] = host["id"]
            host["ink"] += ic["ink"]
        else:
            keep.append(ic)
    icons = keep
    # reading order: cluster rows by vertical centre
    if icons:
        hs = np.median([ic["box"][3] - ic["box"][1] for ic in icons])
        icons.sort(key=lambda ic: ((ic["box"][1] + ic["box"][3]) / 2))
        rows, cur = [], [icons[0]]
        for ic in icons[1:]:
            cy = (ic["box"][1] + ic["box"][3]) / 2
            if abs(cy - np.mean([(c["box"][1] + c["box"][3]) / 2 for c in cur])) < 0.5 * hs:
                cur.append(ic)
            else:
                rows.append(cur)
                cur = [ic]
        rows.append(cur)
        icons = [ic for r in rows for ic in sorted(r, key=lambda c: c["box"][0])]
    return w, icons, lab


def crop_icon(gray, lab, ic, pad, bg):
    H, W = gray.shape
    x0, y0, x1, y1 = ic["box"]
    X0, Y0, X1, Y1 = max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, W), min(y1 + pad, H)
    g = gray[Y0:Y1, X0:X1].copy()
    own = (lab[Y0:Y1, X0:X1] == ic["id"])
    # keep only this icon's cluster (dilated slightly to preserve anti-aliased edges)
    own = cv2.dilate(own.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    g[~own] = bg
    # extra white margin so strokes at the crop border are not clipped
    g = cv2.copyMakeBorder(g, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=int(bg))
    return g, (X0 - 6, Y0 - 6)



================================================================================
# FILE: linework/structfix.py
================================================================================

"""Structure engine: finds places where the render's centre line differs from the source's (structure.compare) and tries stronger,
region-level repairs than the Finisher's local touches.  Every candidate is kept only if
  * the structure score (total severity, in stroke widths) goes down,
  * the soft mismatch does not get worse beyond a small tolerance,
  * the topology (gaps / notches / spurs) does not get worse.
Repairs, in order of strength, per site:
  snap     points of nearby strokes are pulled onto the source's centre line, then the displacement is smoothed   (lumps, jogs, displaced strokes)
  smooth   the nearby stroke is low-pass filtered along its length                                                  (wobble that follows a noisy source)
  retrace  the strokes inside the region are replaced by a fresh trace of the source                                (anything snap / smooth cannot save)
  width    the nearby stroke gets the source's local width                                                          (thick / thin sites)
Escalation: sites that survive all four are reported in `unresolved` so that the pipeline / UI / lessons can show and remember them.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from .model import Model, Path
from .geom import resample, fit_curve
from . import structure as ST
from . import topology as T
from . import finisher as FN


def _near_paths(m: Model, box, w, grow=1.5):
    x0, y0, x1, y1 = box[0] - grow * w, box[1] - grow * w, box[2] + grow * w, box[3] + grow * w
    out = []
    for i, p in enumerate(m.paths):
        f = p.flat(2.0)
        if ((f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)).any():
            out.append(i)
    return out


def _refit(p: Path, pts):
    segs = fit_curve(pts, 0.8, 0.45)
    if not segs:
        return None
    q = Path.from_segs(segs, p.w, closed=p.closed, join=p.join)
    q.ml = p.ml
    return q


def _smooth_field(delta, weight, sigma, closed):
    mode = "wrap" if closed else "nearest"
    d = gaussian_filter1d(delta * weight[:, None], sigma, axis=0, mode=mode)
    wt = gaussian_filter1d(weight, sigma, mode=mode)
    return d / np.maximum(wt, 1e-6)[:, None] * np.clip(wt * 1.0, 0, 1)[:, None]


def _edit_path(p: Path, box, w, src_tree, src_pts, mode):
    f = resample(p.flat(), 0.75)
    if len(f) < 8:
        return None
    x0, y0, x1, y1 = box[0] - 1.5 * w, box[1] - 1.5 * w, box[2] + 1.5 * w, box[3] + 1.5 * w
    inb = ((f[:, 0] > x0) & (f[:, 0] < x1) & (f[:, 1] > y0) & (f[:, 1] < y1)).astype(np.float64)
    if inb.sum() < 3:
        return None
    sig = max(1.0, (1.5 if mode == "snap" else 3.0) * w / 0.75)
    if mode == "snap":
        d, idx = src_tree.query(f)
        tgt = src_pts[idx]
        delta = np.where((d < 1.0 * w)[:, None], tgt - f, 0.0)
        delta = _smooth_field(delta, np.where(d < 1.0 * w, 1.0, 0.0) * inb + 1e-3, sig * 0.5, p.closed)
        g = f + delta * inb[:, None]
    else:
        sm = gaussian_filter1d(f, sig, axis=0, mode="wrap" if p.closed else "nearest")
        g = f + (sm - f) * gaussian_filter1d(inb, 2.0, mode="nearest")[:, None]
    if not p.closed:  # open stroke: keep its end points where they are
        g[0], g[-1] = f[0], f[-1]
    return _refit(p, g)


def _offset_path(p: Path, d):
    """Parallel copy of p, `d` px to the left of its direction of travel (closed or open)."""
    f = resample(p.flat(), 0.75)
    if len(f) < 8:
        return None
    t = np.gradient(f, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    n = np.c_[-t[:, 1], t[:, 0]]
    g = f + n * d
    q = _refit(p, g)
    return q


def double_candidates(m: Model, w, ratio=1.35):
    """Strokes much wider than the set stroke width are fused double lines: one candidate per path, replaced by two parallel strokes of width w."""
    out = []
    for i, p in enumerate(m.paths):
        if p.w > ratio * w and p.length() > 2.5 * w:
            d = (p.w - w) / 2.0
            a, b = _offset_path(p, d), _offset_path(p, -d)
            if a is None or b is None:
                continue
            a.w = b.w = float(w)
            m2 = m.copy()
            m2.paths[i] = a
            m2.paths.append(b)
            out.append((i, m2, 0.6 * w * p.length()))
    return out


def wobble_candidates(m: Model, w, sig=2.5, lo=0.05, hi=0.45):
    """Strokes whose centre line oscillates around its own smooth version (several sign changes, small amplitude): smooth them."""
    out = []
    for i, p in enumerate(m.paths):
        L = p.length()
        if L < 5 * w:
            continue
        f = resample(p.flat(), 0.75)
        if len(f) < 16:
            continue
        sm = gaussian_filter1d(f, sig * w / 0.75, axis=0, mode="wrap" if p.closed else "nearest")
        e = f - sm
        t = np.gradient(sm, axis=0)
        t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        lat = e[:, 0] * -t[:, 1] + e[:, 1] * t[:, 0]
        core = lat[int(2 * sig * w / 0.75): len(lat) - int(2 * sig * w / 0.75)] if not p.closed else lat
        if len(core) < 8:
            continue
        rms = float(np.sqrt((core ** 2).mean())) / w
        sgn = np.sign(core[np.abs(core) > 0.02 * w])
        zc = int((np.diff(sgn) != 0).sum()) if len(sgn) > 1 else 0
        if lo <= rms <= hi and zc >= max(4, int(L / (10 * w) * 4)):
            g = sm.copy()
            if not p.closed:
                k = int(2 * sig * w / 0.75)
                ramp = np.clip(np.arange(len(f)) / max(k, 1), 0, 1) * np.clip((len(f) - 1 - np.arange(len(f))) / max(k, 1), 0, 1)
                g = f + (sm - f) * ramp[:, None]
                g[0], g[-1] = f[0], f[-1]
            q = _refit(p, g)
            if q is not None:
                m2 = m.copy()
                m2.paths[i] = q
                out.append((i, m2, rms * w * L * 2.0))
    return out


def run_structure_engine(model: Model, D, doctor, ink_of, cur, w, time_ok=lambda: True, max_sites=8, memory_skip=()):
    """Returns (model, ink, soft, report) where report = dict(before, after, sites=[...], fixed, unresolved=[...])."""
    ink = ink_of(model)
    cur = doctor.soft(ink)
    res = ST.compare(D, ink, w)
    before = res["score"]
    st = dict(model=model, ink=ink, cur=cur, score=before, topo=FN._topo(model))
    start_soft = cur
    drift_cap = 0.008 * max(doctor.area, 1)
    sites, fixed = [], 0
    src_pts = ST.skeleton_points(D > 0.5, 2, prune_w=max(4, 0.7 * w * 2))
    src_tree = cKDTree(src_pts) if len(src_pts) else None
    tol = lambda c: max(3.0, 0.005 * c)
    # intent checks that do not depend on the source being right: fused double lines, wobbling centre lines
    intent = []
    for kind, fn in (("fused", double_candidates), ("wobble", wobble_candidates)):
        for i, c0, allow in fn(st["model"], w):
            if not time_ok():
                break
            if kind in memory_skip:
                continue
            cur_m = st["model"]
            c = c0 if len(cur_m.paths) == len(c0.paths) - (1 if kind == "fused" else 0) else None
            if c is None:
                continue
            ink2 = ink_of(c)
            s2 = doctor.soft(ink2)
            if s2 > st["cur"] + allow + tol(st["cur"]) or (s2 - start_soft) > drift_cap + allow:
                continue
            t2 = FN._topo(c)
            if t2 > st["topo"]:
                continue
            st.update(model=c, ink=ink2, cur=s2, topo=t2)
            fixed += 1
            intent.append(dict(kind=kind, x=float(c.paths[i].A[0][0]), y=float(c.paths[i].A[0][1]), severity=0.0, fixed=True, how=kind))
            if kind == "fused":
                break  # path indices changed; the next pass of the pipeline will pick the others up
    sites.extend(intent)
    st["score"] = ST.compare(D, st["ink"], w)["score"] if intent else st["score"]
    tried = 0
    queue = list(res["sites"][:max_sites])
    for s in queue:
        if not time_ok() or src_tree is None:
            break
        if tried >= max_sites:
            break
        tried += 1
        box = s["box"]
        near = _near_paths(st["model"], box, w)
        if not near or len(near) > 6:
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=False, how="none"))
            continue
        cands = []
        if s["kind"] in ("thick", "thin"):
            # local width correction (single stroke dominating the site only)
            if len(near) == 1:
                i = near[0]
                for fac in ((0.88, 0.8) if s["kind"] == "thick" else (1.12, 1.25)):
                    m2 = st["model"].copy()
                    m2.paths[i].w = float(m2.paths[i].w * fac)
                    cands.append(("width", m2))
        else:
            for how in ("snap", "smooth"):
                m2 = st["model"].copy()
                okc = False
                for i in near:
                    q = _edit_path(m2.paths[i], box, w, src_tree, src_pts, how)
                    if q is not None:
                        m2.paths[i] = q
                        okc = True
                if okc:
                    cands.append((how, m2))
            rt = FN._redraw_region(st["model"], D, box, w)
            if rt is not None:
                cands.append(("retrace", rt))
        best = None
        for how, c in cands:
            if not time_ok():
                break
            ink2 = ink_of(c)
            s2 = doctor.soft(ink2)
            if s2 > st["cur"] + tol(st["cur"]) or (s2 - start_soft) > drift_cap:
                continue
            sc = ST.compare(D, ink2, w)["score"]
            gain = st["score"] - sc
            if gain < max(0.05, 0.1 * s["severity"]):
                continue
            t2 = FN._topo(c)
            if t2 > st["topo"]:
                continue
            if best is None or gain > best[0]:
                best = (gain, how, c, ink2, s2, sc, t2)
        if best and best[1] not in memory_skip:
            _, how, c, ink2, s2, sc, t2 = best
            st.update(model=c, ink=ink2, cur=s2, score=sc, topo=t2)
            fixed += 1
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=True, how=how))
        else:
            sites.append(dict(kind=s["kind"], x=s["x"], y=s["y"], severity=s["severity"], fixed=False, how="none"))
    rep = dict(before=float(before), after=float(st["score"]), found=len(res["sites"]), fixed=fixed, sites=sites,
               unresolved=[dict(kind=x["kind"], x=x["x"], y=x["y"], severity=x["severity"]) for x in sites if not x["fixed"]])
    return st["model"], st["ink"], st["cur"], rep



================================================================================
# FILE: linework/structure.py
================================================================================

"""Structure check: does the render have the same centre-line skeleton as the source?

The Doctor's pixel overlap (IoU / soft mismatch) cannot see most of what people call "small defects": a lump where two strokes merge, a jog, a wobble,
a doubled outline that fused into one thick stroke.  They move the *centre line* by 0.3-1.5 stroke widths over a stretch of 1-3 stroke widths, which
costs only a few pixels of overlap.  Here both images are reduced to the same kind of skeleton and compared point by point:

  render-off   a skeleton point of the RENDER that is far from every skeleton point of the SOURCE   (lump, jog, hook, extra or displaced stroke)
  source-off   a skeleton point of the SOURCE that is far from the RENDER skeleton                    (missing / fused / displaced stroke)

Sites are connected clusters of such points, sorted by severity; `score` is the total severity in stroke widths (0 = same skeleton).
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
from .trace import _prune


def skeleton_points(mask, S=2, prune_w=None):
    """Skeleton (pruned of short spurs) of a boolean mask as (n,2) x/y points in source pixel coordinates."""
    up = cv2.resize(mask.astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST) > 0
    sk = skeletonize(up)
    H, W = sk.shape
    sk = _prune(sk, int(prune_w if prune_w else 7 * S), H, W)
    ys, xs = np.nonzero(sk)
    return np.c_[xs + 0.5, ys + 0.5] / S


def _radius_at(mask, pts):
    from scipy import ndimage as ndi
    dt = ndi.distance_transform_edt(mask)
    q = np.clip(pts.astype(int), 0, [mask.shape[1] - 1, mask.shape[0] - 1])
    return dt[q[:, 1], q[:, 0]]


def compare(D, ink, w, thr=0.12, thick_thr=0.15, min_len=0.8, S=2):
    """Returns dict(score, sites=[dict(kind, x, y, size, severity, box)]) for source ink map D and render ink map `ink`.
    kinds: render-off / source-off (centre line displaced) and thick / thin (render stroke thicker / thinner than the source at the same place)."""
    src = skeleton_points(D > 0.5, S, prune_w=max(4, 0.7 * w * S))
    ren = skeleton_points(ink > 0.5, S, prune_w=max(4, 0.7 * w * S))
    if len(src) == 0 or len(ren) == 0:
        return dict(score=0.0, sites=[])
    ts, tr = cKDTree(src), cKDTree(ren)
    d_ren, i_ren = ts.query(ren)  # render points -> source skeleton
    d_src = tr.query(src)[0]
    r_ren = _radius_at(ink > 0.5, ren)
    r_srcm = _radius_at(D > 0.5, src)[i_ren]  # source radius at the nearest source skeleton point
    dr = (r_ren - r_srcm) / w  # >0: render thicker
    near = d_ren <= 0.5 * w  # thickness is only comparable where the skeletons agree on the position
    sites = []
    H, W = D.shape
    for kind, pts, d in (("render-off", ren, d_ren), ("source-off", src, d_src), ("thick", ren, np.where(near & (dr > thick_thr), (dr - thick_thr) * w + thr * w, 0.0)),
                         ("thin", ren, np.where(near & (dr < -thick_thr), (-dr - thick_thr) * w + thr * w, 0.0))):
        bad = d > thr * w
        if not bad.any():
            continue
        mk = np.zeros((H, W), np.uint8)
        q = np.clip(pts[bad].astype(int), 0, [W - 1, H - 1])
        mk[q[:, 1], q[:, 0]] = 1
        k = int(max(3, 0.6 * w)) | 1
        n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.dilate(mk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))))
        pl = lab[np.clip(pts[bad][:, 1].astype(int), 0, H - 1), np.clip(pts[bad][:, 0].astype(int), 0, W - 1)]
        dd = d[bad]
        for c in range(1, n):
            sel = pl == c
            if sel.sum() < 2:
                continue
            length = sel.sum() / S  # skeleton pixels at S x resolution ~ length in source px
            if length < min_len * w:
                continue
            sev = float(((dd[sel] - thr * w) / w).clip(0).sum() / S)
            x, y, bw, bh, _ = st[c]
            sites.append(dict(kind=kind, x=float(cen[c][0]), y=float(cen[c][1]), size=float(length / w), severity=sev,
                              box=[int(x), int(y), int(x + bw), int(y + bh)]))
    sites.sort(key=lambda s: -s["severity"])
    return dict(score=float(sum(s["severity"] for s in sites)), sites=sites)



================================================================================
# FILE: linework/template.py
================================================================================

"""Presentation Template Engine: Combines icon set metadata + redrawn vector icon sheet into a professional presentation artboard.

Outputs:
  - High-resolution SVG presentation template
  - Encapsulated PostScript (EPS 3.0) presentation template
  - Standalone EPS for the icon sheet
"""
from __future__ import annotations
import math, re
from typing import Any
from .model import Model

PRESETS: dict[str, dict[str, Any]] = {
    "obsidian": {
        "id": "obsidian",
        "name": "Obsidian Dark",
        "bg": "#090d14",
        "panel_bg": "#121824",
        "panel_border": "#00f5a0",
        "panel_border_alpha": 0.25,
        "accent": "#00f5a0",
        "title_color": "#ffffff",
        "subtitle_color": "#94a3b8",
        "badge_bg": "#00f5a0",
        "badge_bg_alpha": 0.12,
        "badge_text": "#00f5a0",
        "icon_stroke": "#00f5a0",
        "card_bg": "#0d131d",
        "card_border": "#1e293b",
        "text_dim": "#64748b",
        "dot_grid": "rgba(255,255,255,0.06)",
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimalist Studio",
        "bg": "#f8fafc",
        "panel_bg": "#ffffff",
        "panel_border": "#0284c7",
        "panel_border_alpha": 0.2,
        "accent": "#0284c7",
        "title_color": "#0f172a",
        "subtitle_color": "#64748b",
        "badge_bg": "#0284c7",
        "badge_bg_alpha": 0.1,
        "badge_text": "#0284c7",
        "icon_stroke": "#0f172a",
        "card_bg": "#ffffff",
        "card_border": "#e2e8f0",
        "text_dim": "#94a3b8",
        "dot_grid": "rgba(0,0,0,0.04)",
    },
    "cyber": {
        "id": "cyber",
        "name": "Cyber Neon",
        "bg": "#0a0a16",
        "panel_bg": "#131326",
        "panel_border": "#f43f5e",
        "panel_border_alpha": 0.35,
        "accent": "#f43f5e",
        "title_color": "#ffffff",
        "subtitle_color": "#c4b5fd",
        "badge_bg": "#f43f5e",
        "badge_bg_alpha": 0.15,
        "badge_text": "#fb7185",
        "icon_stroke": "#38bdf8",
        "card_bg": "#0f1022",
        "card_border": "#27274a",
        "text_dim": "#71717a",
        "dot_grid": "rgba(168,85,247,0.08)",
    },
    "gold": {
        "id": "gold",
        "name": "Luxury Gold",
        "bg": "#121110",
        "panel_bg": "#1c1a17",
        "panel_border": "#d4af37",
        "panel_border_alpha": 0.3,
        "accent": "#d4af37",
        "title_color": "#fef3c7",
        "subtitle_color": "#a8a29e",
        "badge_bg": "#d4af37",
        "badge_bg_alpha": 0.15,
        "badge_text": "#facc15",
        "icon_stroke": "#d4af37",
        "card_bg": "#161412",
        "card_border": "#2d2822",
        "text_dim": "#78716c",
        "dot_grid": "rgba(212,175,55,0.06)",
    },
    "cream": {
        "id": "cream",
        "name": "Pastel Cream",
        "bg": "#faf7f2",
        "panel_bg": "#ffffff",
        "panel_border": "#e11d48",
        "panel_border_alpha": 0.2,
        "accent": "#e11d48",
        "title_color": "#292524",
        "subtitle_color": "#78716c",
        "badge_bg": "#e11d48",
        "badge_bg_alpha": 0.1,
        "badge_text": "#be123c",
        "icon_stroke": "#292524",
        "card_bg": "#ffffff",
        "card_border": "#e7e5e4",
        "text_dim": "#a8a29e",
        "dot_grid": "rgba(0,0,0,0.03)",
    },
    "blueprint": {
        "id": "blueprint",
        "name": "Blueprint Tech",
        "bg": "#0a192f",
        "panel_bg": "#112240",
        "panel_border": "#38bdf8",
        "panel_border_alpha": 0.3,
        "accent": "#38bdf8",
        "title_color": "#f8fafc",
        "subtitle_color": "#8892b0",
        "badge_bg": "#38bdf8",
        "badge_bg_alpha": 0.15,
        "badge_text": "#38bdf8",
        "icon_stroke": "#38bdf8",
        "card_bg": "#0d1b2a",
        "card_border": "#1e3a5f",
        "text_dim": "#64748b",
        "dot_grid": "rgba(56,189,248,0.1)",
    },
}


def hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    """Convert hex string (e.g. '#00f5a0' or '00f5a0') to 0.0-1.0 RGB tuple."""
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b)
    except Exception:
        return (0.0, 0.0, 0.0)


def sanitize_text(text: str) -> str:
    """Escape text for XML/SVG safety."""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def escape_ps_text(text: str) -> str:
    """Escape text for PostScript string literal (inside parentheses)."""
    t = str(text or "")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def resolve_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(cfg or {})
    preset_key = cfg.get("preset", "obsidian")
    base = dict(PRESETS.get(preset_key, PRESETS["obsidian"]))
    
    # Overwrite with any custom color or style overrides
    for k in (
        "bg", "panel_bg", "panel_border", "accent", "title_color",
        "subtitle_color", "badge_bg", "badge_text", "icon_stroke", "card_bg"
    ):
        if cfg.get(k):
            base[k] = cfg[k]

    base["title"] = cfg.get("title") or "Minimal Vector Line Icons"
    base["subtitle"] = cfg.get("subtitle") or "Clean Centerline Vector Icon Collection"
    base["icon_count"] = int(cfg.get("icon_count") or 12)
    base["grid_size"] = cfg.get("grid_size") or "64 × 64 px"
    base["author"] = cfg.get("author") or "Linework AI Precision Engine"
    base["stroke_scale"] = float(cfg.get("stroke_scale") or 1.0)
    base["layout"] = cfg.get("layout") or "landscape"  # "landscape" (1600x1000) or "square" (1200x1200)
    base["show_grid"] = cfg.get("show_grid", True)
    base["show_badges"] = cfg.get("show_badges", True)
    return base


def build_template_svg(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate high-resolution SVG presentation artboard with Left Metadata Card and Right Traced Icon Sheet."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count = len(icons_meta) if icons_meta else c["icon_count"]
    
    if c["layout"] == "square":
        W, H = 1200, 1200
        left_w = 380
        left_x = 40
        right_x = 445
        right_w = 715
    else:  # landscape 1600 x 1000 (standard Dribbble/Behance/Marketplace presentation)
        W, H = 1600, 1000
        left_w = 460
        left_x = 60
        right_x = 550
        right_w = 990

    top_y = 60
    content_h = H - 120

    # Calculate scale and translation for the Model on the right side
    mW, mH = max(1, model.width), max(1, model.height)
    avail_w = right_w - 80
    avail_h = content_h - 80
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = right_x + 40 + (avail_w - target_w) / 2
    off_y = top_y + 40 + (avail_h - target_h) / 2

    # Render model paths with custom stroke color and scale
    stroke_color = c["icon_stroke"]
    stroke_scale = c["stroke_scale"]
    
    path_elems = []
    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        d = p.d()
        path_elems.append(
            f'<path d="{d}" stroke="{stroke_color}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )
    paths_svg = "\n      ".join(path_elems)

    # Decorative dots grid pattern
    dots_svg = ""
    if c.get("show_grid"):
        dots_svg = f"""
    <defs>
      <pattern id="dotPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.5" fill="{c['dot_grid']}"/>
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#dotPattern)"/>
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&amp;family=JetBrains+Mono:wght@500;700&amp;display=swap');
    text {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }}
    .mono {{ font-family: 'JetBrains Mono', monospace; }}
  </style>

  <!-- Background Canvas -->
  <rect width="{W}" height="{H}" fill="{c['bg']}"/>
  {dots_svg}

  <!-- ================= LEFT SECTION: PRESENTATION METADATA & SPECS ================= -->
  <g id="leftTemplateSection">
    <!-- Panel Backdrop Card -->
    <rect x="{left_x}" y="{top_y}" width="{left_w}" height="{content_h}" rx="24" 
          fill="{c['panel_bg']}" stroke="{c['panel_border']}" stroke-width="1.5" stroke-opacity="{c.get('panel_border_alpha', 0.25)}"/>

    <!-- Category Pill Badge -->
    <rect x="{left_x + 36}" y="{top_y + 36}" width="165" height="30" rx="8" 
          fill="{c['badge_bg']}" fill-opacity="{c.get('badge_bg_alpha', 0.15)}"/>
    <text x="{left_x + 48}" y="{top_y + 56}" font-size="11" font-weight="700" letter-spacing="1" fill="{c['badge_text']}" class="mono">
      VECTOR ICON SET
    </text>

    <!-- Main Title -->
    <text x="{left_x + 36}" y="{top_y + 112}" font-size="28" font-weight="800" fill="{c['title_color']}" letter-spacing="-0.5">
      {sanitize_text(c['title'])}
    </text>

    <!-- Subtitle / Description -->
    <text x="{left_x + 36}" y="{top_y + 144}" font-size="14" font-weight="500" fill="{c['subtitle_color']}">
      {sanitize_text(c['subtitle'])}
    </text>

    <!-- Highlight Spec: Live Editable Stroke Badge -->
    <g transform="translate({left_x + 36}, {top_y + 175})">
      <rect width="{left_w - 72}" height="56" rx="14" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <circle cx="28" cy="28" r="14" fill="{c['accent']}" fill-opacity="0.15"/>
      <path d="M22 28l4 4 8-8" stroke="{c['accent']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      <text x="52" y="24" font-size="13" font-weight="700" fill="{c['title_color']}">100% Vector &amp; Editable Stroke</text>
      <text x="52" y="42" font-size="11" font-weight="500" fill="{c['text_dim']}">Single centerline paths · Infinite scale</text>
    </g>

    <!-- 2x2 Specifications Mini Grid -->
    <g transform="translate({left_x + 36}, {top_y + 250})">
      <!-- Stat 1: Icon Count -->
      <rect x="0" y="0" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="16" y="28" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">COUNT</text>
      <text x="16" y="52" font-size="20" font-weight="800" fill="{c['title_color']}">{count} Icons</text>

      <!-- Stat 2: Grid Size -->
      <rect x="{(left_w - 86) / 2 + 14}" y="0" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="{(left_w - 86) / 2 + 30}" y="28" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">GRID</text>
      <text x="{(left_w - 86) / 2 + 30}" y="52" font-size="18" font-weight="800" fill="{c['title_color']}">{sanitize_text(c['grid_size'])}</text>

      <!-- Stat 3: Formats -->
      <rect x="0" y="80" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="16" y="108" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">FORMAT</text>
      <text x="16" y="132" font-size="16" font-weight="800" fill="{c['title_color']}">SVG · EPS</text>

      <!-- Stat 4: Precision -->
      <rect x="{(left_w - 86) / 2 + 14}" y="80" width="{(left_w - 86) / 2}" height="68" rx="12" fill="{c['card_bg']}" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="{(left_w - 86) / 2 + 30}" y="108" font-size="11" font-weight="600" fill="{c['text_dim']}" class="mono">QUALITY</text>
      <text x="{(left_w - 86) / 2 + 30}" y="132" font-size="16" font-weight="800" fill="{c['accent']}">Clean Joints</text>
    </g>

    <!-- Features Checklist -->
    <g transform="translate({left_x + 36}, {top_y + 420})">
      <text x="0" y="15" font-size="12" font-weight="700" letter-spacing="1" fill="{c['text_dim']}" class="mono">KEY FEATURES</text>

      <!-- Item 1 -->
      <circle cx="8" cy="45" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 45l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="49" font-size="13" font-weight="600" fill="{c['title_color']}">Clean Centerline Strokes</text>

      <!-- Item 2 -->
      <circle cx="8" cy="77" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 77l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="81" font-size="13" font-weight="600" fill="{c['title_color']}">Perfect Circular Arcs &amp; Welded Corners</text>

      <!-- Item 3 -->
      <circle cx="8" cy="109" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 109l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="113" font-size="13" font-weight="600" fill="{c['title_color']}">Zero Stray Nodes or Overlapping Ink</text>

      <!-- Item 4 -->
      <circle cx="8" cy="141" r="7" fill="{c['accent']}" fill-opacity="0.18"/>
      <path d="M5 141l2 2 4-4" stroke="{c['accent']}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <text x="26" y="145" font-size="13" font-weight="600" fill="{c['title_color']}">Fully Scalable to Any Dimension</text>
    </g>

    <!-- Author & License Footer Tag -->
    <g transform="translate({left_x + 36}, {top_y + content_h - 45})">
      <line x1="0" y1="-15" x2="{left_w - 72}" y2="-15" stroke="{c['card_border']}" stroke-width="1"/>
      <text x="0" y="8" font-size="12" font-weight="600" fill="{c['text_dim']}">
        {sanitize_text(c['author'])}
      </text>
      <text x="{left_w - 72}" y="8" text-anchor="end" font-size="11" font-weight="700" fill="{c['accent']}" class="mono">
        PREMIUM ASSET
      </text>
    </g>
  </g>

  <!-- ================= RIGHT SECTION: TRACED VECTOR ICON SHEET ================= -->
  <g id="rightIconSheetSection">
    <!-- Icon Artboard Framing Container -->
    <rect x="{right_x}" y="{top_y}" width="{right_w}" height="{content_h}" rx="24" 
          fill="{c['card_bg']}" stroke="{c['panel_border']}" stroke-width="1.5" stroke-opacity="{c.get('panel_border_alpha', 0.25)}"/>

    <!-- Corner Alignment Marks -->
    <path d="M{right_x + 20} {top_y + 35} L{right_x + 20} {top_y + 20} L{right_x + 35} {top_y + 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + right_w - 20} {top_y + 35} L{right_x + right_w - 20} {top_y + 20} L{right_x + right_w - 35} {top_y + 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + 20} {top_y + content_h - 35} L{right_x + 20} {top_y + content_h - 20} L{right_x + 35} {top_y + content_h - 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>
    <path d="M{right_x + right_w - 20} {top_y + content_h - 35} L{right_x + right_w - 20} {top_y + content_h - 20} L{right_x + right_w - 35} {top_y + content_h - 20}" stroke="{c['text_dim']}" stroke-width="1" fill="none"/>

    <!-- Scaled & Centered Vector Centerline Icons -->
    <g transform="translate({off_x:.2f}, {off_y:.2f})">
      {paths_svg}
    </g>
  </g>

</svg>"""
    return svg


def build_template_eps(model: Model, icons_meta: list[dict] | None = None, config: dict | None = None) -> str:
    """Generate professional Adobe-standard Encapsulated PostScript (EPS 3.0) presentation template."""
    c = resolve_config(config)
    icons_meta = icons_meta or []
    count = len(icons_meta) if icons_meta else c["icon_count"]

    if c["layout"] == "square":
        W, H = 1200, 1200
        left_w = 380
        left_x = 40
        right_x = 445
        right_w = 715
    else:
        W, H = 1600, 1000
        left_w = 460
        left_x = 60
        right_x = 550
        right_w = 990

    top_y = 60
    content_h = H - 120

    # Model positioning
    mW, mH = max(1, model.width), max(1, model.height)
    avail_w = right_w - 80
    avail_h = content_h - 80
    scale = min(avail_w / mW, avail_h / mH)
    target_w = mW * scale
    target_h = mH * scale
    off_x = right_x + 40 + (avail_w - target_w) / 2
    off_y = top_y + 40 + (avail_h - target_h) / 2

    # Color values
    bg_r, bg_g, bg_b = hex_to_rgb(c["bg"])
    pbg_r, pbg_g, pbg_b = hex_to_rgb(c["panel_bg"])
    acc_r, acc_g, acc_b = hex_to_rgb(c["accent"])
    tit_r, tit_g, tit_b = hex_to_rgb(c["title_color"])
    sub_r, sub_g, sub_b = hex_to_rgb(c["subtitle_color"])
    cbg_r, cbg_g, cbg_b = hex_to_rgb(c["card_bg"])
    stk_r, stk_g, stk_b = hex_to_rgb(c["icon_stroke"])
    dim_r, dim_g, dim_b = hex_to_rgb(c["text_dim"])
    stroke_scale = c["stroke_scale"]

    # Build PostScript code
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Presentation Engine",
        f"%%Title: {escape_ps_text(c['title'])}",
        f"%%BoundingBox: 0 0 {W} {H}",
        f"%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%Pages: 1",
        "%%EndComments",
        "",
        "% Helper macros",
        "/M { moveto } bind def",
        "/L { lineto } bind def",
        "/C { curveto } bind def",
        "/CP { closepath } bind def",
        "/S { stroke } bind def",
        "/F { fill } bind def",
        "/RGB { setrgbcolor } bind def",
        "/LW { setlinewidth } bind def",
        "/LC { setlinecap } bind def",
        "/LJ { setlinejoin } bind def",
        "",
        "% Rounded rectangle: x y w h r roundrect",
        "/roundrect {",
        "  /r exch def /h exch def /w exch def /y exch def /x exch def",
        "  newpath",
        "  x r add y M",
        "  x w add y x w add y h add r arcto 4 {pop} repeat",
        "  x w add y h add x y h add r arcto 4 {pop} repeat",
        "  x y h add x y r arcto 4 {pop} repeat",
        "  x y x w add y r arcto 4 {pop} repeat",
        "  CP",
        "} bind def",
        "",
        "% Transform origin to top-left (SVG coordinate alignment)",
        f"0 {H} translate",
        "1 -1 scale",
        "",
        "% Background",
        f"{bg_r:.3f} {bg_g:.3f} {bg_b:.3f} RGB",
        f"0 0 {W} {H} rectfill",
        "",
        "% Left Panel Backdrop",
        f"{left_x} {top_y} {left_w} {content_h} 24 roundrect",
        f"{pbg_r:.3f} {pbg_g:.3f} {pbg_b:.3f} RGB F",
        f"{left_x} {top_y} {left_w} {content_h} 24 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1.5 LW 1 LC 1 LJ S",
        "",
        "% Right Framing Container",
        f"{right_x} {top_y} {right_w} {content_h} 24 roundrect",
        f"{cbg_r:.3f} {cbg_g:.3f} {cbg_b:.3f} RGB F",
        f"{right_x} {top_y} {right_w} {content_h} 24 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1.5 LW 1 LC 1 LJ S",
        "",
        "% Left Panel Text & Typography",
        "% Note: font rendering with scale 1 -1 needs inverted font matrix to read correctly",
        "/drawText {",
        "  gsave",
        "  1 -1 scale",
        "  moveto show",
        "  grestore",
        "} bind def",
        "",
        "% Category badge",
        f"{left_x + 36} {top_y + 36} 165 30 8 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1 LW S",
        f"/Helvetica-Bold findfont 11 scalefont setfont",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB",
        f"({escape_ps_text('VECTOR ICON SET')}) {left_x + 48} {- (top_y + 56)} drawText",
        "",
        "% Title",
        f"/Helvetica-Bold findfont 26 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text(c['title'])}) {left_x + 36} {- (top_y + 112)} drawText",
        "",
        "% Subtitle",
        f"/Helvetica findfont 13 scalefont setfont",
        f"{sub_r:.3f} {sub_g:.3f} {sub_b:.3f} RGB",
        f"({escape_ps_text(c['subtitle'])}) {left_x + 36} {- (top_y + 144)} drawText",
        "",
        "% Editable badge container",
        f"{left_x + 36} {top_y + 175} {left_w - 72} 56 12 roundrect",
        f"{cbg_r:.3f} {cbg_g:.3f} {cbg_b:.3f} RGB F",
        f"{left_x + 36} {top_y + 175} {left_w - 72} 56 12 roundrect",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB 1 LW S",
        f"/Helvetica-Bold findfont 13 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text('100% Vector & Editable Stroke')}) {left_x + 56} {- (top_y + 200)} drawText",
        f"/Helvetica findfont 11 scalefont setfont",
        f"{dim_r:.3f} {dim_g:.3f} {dim_b:.3f} RGB",
        f"({escape_ps_text('Clean single centerlines')}) {left_x + 56} {- (top_y + 218)} drawText",
        "",
        "% Specifications block",
        f"/Helvetica-Bold findfont 16 scalefont setfont",
        f"{tit_r:.3f} {tit_g:.3f} {tit_b:.3f} RGB",
        f"({escape_ps_text(str(count) + ' Icons  |  Grid: ' + str(c.get('grid_size', '64x64')) + '  |  SVG + EPS')}) {left_x + 36} {- (top_y + 280)} drawText",
        "",
        "% Features List",
        f"/Helvetica-Bold findfont 12 scalefont setfont",
        f"{acc_r:.3f} {acc_g:.3f} {acc_b:.3f} RGB",
        f"({escape_ps_text('[v] Clean Single Centerlines')}) {left_x + 36} {- (top_y + 340)} drawText",
        f"({escape_ps_text('[v] Perfect Circular Arcs & Welded Corners')}) {left_x + 36} {- (top_y + 372)} drawText",
        f"({escape_ps_text('[v] Zero Stray Nodes or Overlaps')}) {left_x + 36} {- (top_y + 404)} drawText",
        f"({escape_ps_text('[v] Fully Scalable to Any Dimension')}) {left_x + 36} {- (top_y + 436)} drawText",
        "",
        "% Footer",
        f"/Helvetica findfont 12 scalefont setfont",
        f"{dim_r:.3f} {dim_g:.3f} {dim_b:.3f} RGB",
        f"({escape_ps_text(c['author'])}) {left_x + 36} {- (top_y + content_h - 45)} drawText",
        "",
        "% ================= RIGHT SECTION: VECTOR ICON PATHS =================",
        "gsave",
        f"{off_x:.3f} {off_y:.3f} translate",
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
        "1 LC 1 LJ",
    ]

    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale * scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        for i, seg in enumerate(p.segs()):
            p0, p1, p2, p3 = seg
            if i == 0:
                lines.append(f"{p0[0]:.2f} {p0[1]:.2f} M")
            lines.append(f"{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.extend([
        "grestore",
        "",
        "%%EOF"
    ])
    return "\n".join(lines)


def build_model_eps(model: Model, stroke_color: str = "#000000", stroke_scale: float = 1.0, bg: str | None = None) -> str:
    """Generate standalone EPS for just the clean icon sheet without template framing."""
    W, H = max(1, model.width), max(1, model.height)
    stk_r, stk_g, stk_b = hex_to_rgb(stroke_color)

    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Linework AI Clean Vector Engine",
        f"%%BoundingBox: 0 0 {W} {H}",
        f"%%HiResBoundingBox: 0 0 {float(W)} {float(H)}",
        "%%Pages: 1",
        "%%EndComments",
        "",
        "/M { moveto } bind def",
        "/L { lineto } bind def",
        "/C { curveto } bind def",
        "/CP { closepath } bind def",
        "/S { stroke } bind def",
        "/F { fill } bind def",
        "/RGB { setrgbcolor } bind def",
        "/LW { setlinewidth } bind def",
        "/LC { setlinecap } bind def",
        "/LJ { setlinejoin } bind def",
        "",
        f"0 {H} translate",
        "1 -1 scale",
    ]

    if bg and bg.lower() not in ("none", "transparent"):
        bgr, bgg, bgb = hex_to_rgb(bg)
        lines.extend([
            f"{bgr:.3f} {bgg:.3f} {bgb:.3f} RGB",
            f"0 0 {W} {H} rectfill",
        ])

    lines.extend([
        f"{stk_r:.3f} {stk_g:.3f} {stk_b:.3f} RGB",
        "1 LC 1 LJ",
    ])

    for p in model.paths:
        sw = max(0.5, p.w * stroke_scale)
        lines.append(f"{sw:.2f} LW")
        lines.append("newpath")
        for i, seg in enumerate(p.segs()):
            p0, p1, p2, p3 = seg
            if i == 0:
                lines.append(f"{p0[0]:.2f} {p0[1]:.2f} M")
            lines.append(f"{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f} C")
        if p.closed:
            lines.append("CP")
        lines.append("S")

    lines.append("%%EOF")
    return "\n".join(lines)



================================================================================
# FILE: linework/topology.py
================================================================================

"""Topology repair: junction gaps, micro-segment notches and corner spurs.

These are the defects a vector editor shows as two separate paths that nearly meet, a tiny staircase at a
corner, or a little curl at the end of a stroke.  Detectors feed the Doctor; the repair functions are Edit commands.
"""
from __future__ import annotations
import numpy as np
from .geom import unit
from .model import Model, Path


def _end(p: Path, e):
    """(point, outward unit tangent) of open end e (0 = start, 1 = end)."""
    if e == 0:
        a, h, nb = p.A[0], p.Hout[0], p.A[1]
        d = a - h
        if np.linalg.norm(d) < 1e-6:
            d = a - nb
    else:
        a, h, nb = p.A[-1], p.Hin[-1], p.A[-2]
        d = a - h
        if np.linalg.norm(d) < 1e-6:
            d = a - nb
    return a.copy(), unit(d)


def _move_end(p: Path, e, target):
    if e == 0:
        d = target - p.A[0]
        p.A[0] = target
        p.Hout[0] = p.Hout[0] + d
        p.Hin[0] = p.Hin[0] + d
    else:
        d = target - p.A[-1]
        p.A[-1] = target
        p.Hin[-1] = p.Hin[-1] + d
        p.Hout[-1] = p.Hout[-1] + d


def _ends(m: Model):
    out = []
    for i, p in enumerate(m.paths):
        if p.closed or len(p.A) < 2:
            continue
        for e in (0, 1):
            pt, t = _end(p, e)
            out.append((i, e, pt, t))
    return out


def _plan(m: Model, r_end=1.0, r_t=0.7, min_gap=0.35):
    """Return list of (kind, i, e, j, e2_or_None, target, gap) weld actions without applying them."""
    ends = _ends(m)
    polys = [p.flat(1.0) for p in m.paths]
    acts, used = [], set()
    pairs = []
    for a in range(len(ends)):
        for b in range(a + 1, len(ends)):
            i, e, p1, _ = ends[a]
            j, f, p2, _ = ends[b]
            d = float(np.linalg.norm(p1 - p2))
            w = max(m.paths[i].w, m.paths[j].w)
            if d <= r_end * w and (i != j):
                pairs.append((d, a, b))
    for d, a, b in sorted(pairs):
        if a in used or b in used:
            continue
        i, e, p1, t1 = ends[a]
        j, f, p2, t2 = ends[b]
        cross_tol = max(0.6, 0.08 * w)
        if d > min_gap and any(
            k != i and k != j and len(polys[k]) > 0
            and float(np.min(np.linalg.norm(polys[k] - p1, axis=1))) <= cross_tol
            and float(np.min(np.linalg.norm(polys[k] - p2, axis=1))) <= cross_tol
            for k in range(len(polys))
        ):
            continue
        w = max(m.paths[i].w, m.paths[j].w)
        cr = t1[0] * t2[1] - t1[1] * t2[0]
        target = (p1 + p2) / 2
        if abs(cr) > 0.25:  # a real corner: meet at the intersection of the two stroke axes
            s = np.linalg.solve(np.array([[t1[0], -t2[0]], [t1[1], -t2[1]]]), p2 - p1)
            if -0.9 * w <= s[0] <= 1.2 * w and -0.9 * w <= s[1] <= 1.2 * w:
                target = p1 + s[0] * t1
        gap = float(np.linalg.norm(p1 - target) + np.linalg.norm(p2 - target))
        if gap > min_gap:
            acts.append(("corner", i, e, j, f, target, gap))
        used.update((a, b))
    # T-junctions: free ends that stop short of (or inside) another stroke
    for a, (i, e, p1, t1) in enumerate(ends):
        if a in used:
            continue
        w = m.paths[i].w
        best = None
        for j, f in enumerate(polys):
            if j == i:
                continue
            dd = np.linalg.norm(f - p1, axis=1)
            k = int(dd.argmin())
            if dd[k] <= r_t * w and (best is None or dd[k] < best[0]):
                best = (float(dd[k]), j, f[k])
        if best and best[0] > min_gap:
            acts.append(("tee", i, e, best[1], None, best[2], best[0]))
    return acts


def find_gaps(m: Model, **kw):
    """Number of unwelded junctions (the Doctor flags these)."""
    return _plan(m, **kw)


def weld_all(m: Model, **kw):
    m = m.copy()
    for kind, i, e, j, f, target, gap in _plan(m, **kw):
        _move_end(m.paths[i], e, target)
        if f is not None:
            _move_end(m.paths[j], f, target)
    return m


def _turn(p: Path, k: int) -> float:
    """Signed turning angle (deg) at anchor k."""
    n = len(p.A)
    if n < 3:
        return 0.0
    if p.closed:
        N = n - 1
        if N < 2:
            return 0.0
        k_mod = k % N
        din = p.A[k_mod] - p.Hin[k_mod]
        if np.linalg.norm(din) < 1e-6:
            prev_idx = (k_mod - 1) % N
            din = p.A[k_mod] - p.A[prev_idx]
        dout = p.Hout[k_mod] - p.A[k_mod]
        if np.linalg.norm(dout) < 1e-6:
            next_idx = (k_mod + 1) % N
            dout = p.A[next_idx] - p.A[k_mod]
    else:
        k_clamped = max(0, min(n - 1, k))
        din = p.A[k_clamped] - p.Hin[k_clamped]
        if np.linalg.norm(din) < 1e-6:
            prev_idx = max(0, k_clamped - 1)
            din = p.A[k_clamped] - p.A[prev_idx]
            if np.linalg.norm(din) < 1e-6 and k_clamped + 1 < n:
                din = p.A[k_clamped + 1] - p.A[k_clamped]
        dout = p.Hout[k_clamped] - p.A[k_clamped]
        if np.linalg.norm(dout) < 1e-6:
            next_idx = min(n - 1, k_clamped + 1)
            dout = p.A[next_idx] - p.A[k_clamped]
            if np.linalg.norm(dout) < 1e-6 and k_clamped - 1 >= 0:
                dout = p.A[k_clamped] - p.A[k_clamped - 1]

    norm_in = float(np.linalg.norm(din))
    norm_out = float(np.linalg.norm(dout))
    if norm_in < 1e-6 or norm_out < 1e-6:
        return 0.0
    a, b = din / norm_in, dout / norm_out
    return float(np.degrees(np.arctan2(a[0] * b[1] - a[1] * b[0], a @ b)))


def _is_step(p: Path, k: int, frac: float) -> bool:
    """Tiny segment k->k+1 that is a corner chamfer or a zig-zag step rather than part of a smooth curve."""
    n = len(p.A)
    if n < 2:
        return False
    if p.closed:
        N = n - 1
        if N < 3:
            return False
        k0 = k % N
        k1 = (k + 1) % N
    else:
        if k + 1 >= n:
            return False
        k0 = k
        k1 = k + 1
    if np.linalg.norm(p.A[k1] - p.A[k0]) >= frac * p.w:
        return False
    t1, t2 = _turn(p, k0), _turn(p, k1)
    if t1 * t2 < 0:
        return min(abs(t1), abs(t2)) > 15.0
    return abs(t1) > 25.0 and abs(t2) > 25.0 and abs(t1 + t2) > 50.0


def merge_nodes(m: Model, i, frac=0.85):
    """Collapse chamfer/zig-zag steps at a corner into one clean anchor."""
    m = m.copy()
    p = m.paths[i]
    changed = True
    while changed and len(p.A) > (4 if p.closed else 3):
        changed = False
        limit = len(p.A) - 1 if p.closed else len(p.A) - 2
        for k in range(0 if p.closed else 1, limit):
            if not _is_step(p, k, frac):
                continue
            k_prev = (k - 1) % (len(p.A) - 1) if p.closed else k - 1
            k_next = (k + 2) % (len(p.A) - 1) if p.closed else k + 2
            M = (p.A[k] + p.A[k + 1]) / 2
            tin = unit(p.A[k] - p.Hin[k]) if np.linalg.norm(p.A[k] - p.Hin[k]) > 1e-6 else unit(p.A[k] - p.A[k_prev])
            tout = unit(p.Hout[k + 1] - p.A[k + 1]) if np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]) > 1e-6 else unit(p.A[k_next] - p.A[k + 1])
            P = M
            cr = tin[0] * tout[1] - tin[1] * tout[0]
            if abs(cr) > 0.2:
                try:
                    s = np.linalg.solve(np.array([[tin[0], -tout[0]], [tin[1], -tout[1]]]), p.A[k + 1] - p.A[k])
                    cand = p.A[k] + s[0] * tin
                    if np.linalg.norm(cand - M) < 0.8 * p.w:
                        P = cand
                except Exception:
                    pass
            lin = max(np.linalg.norm(p.A[k] - p.Hin[k]), 1.0)
            lout = max(np.linalg.norm(p.Hout[k + 1] - p.A[k + 1]), 1.0)
            if not p.closed:
                p.A = np.vstack([p.A[:k], P, p.A[k + 2:]])
                p.Hin = np.vstack([p.Hin[:k], P - tin * lin, p.Hin[k + 2:]])
                p.Hout = np.vstack([p.Hout[:k], P + tout * lout, p.Hout[k + 2:]])
            else:
                p.A = np.delete(p.A, k + 1, axis=0)
                p.Hin = np.delete(p.Hin, k + 1, axis=0)
                p.Hout = np.delete(p.Hout, k + 1, axis=0)
                p.A[k] = P
                p.Hin[k] = P - tin * lin
                p.Hout[k] = P + tout * lout
                p.A[-1] = p.A[0]
                p.Hin[-1] = p.Hin[0]
                p.Hout[-1] = p.Hout[0]
            changed = True
            break
    return m


def find_notches(m: Model, frac=0.85):
    out = []
    for i, p in enumerate(m.paths):
        min_n = 5 if p.closed else 4
        if len(p.A) < min_n:
            continue
        limit = len(p.A) - 1 if p.closed else len(p.A) - 2
        start_k = 0 if p.closed else 1
        if any(_is_step(p, k, frac) for k in range(start_k, limit)):
            out.append(i)
    return out


def _spur(p: Path, e, frac=0.9, ang=35.0):
    n = len(p.A)
    if p.closed or n < 3:
        return False
    if e == 0:
        a, b, c = p.A[0], p.A[1], p.A[2]
    else:
        a, b, c = p.A[-1], p.A[-2], p.A[-3]
    s1, s2 = a - b, b - c
    if np.linalg.norm(s1) >= frac * p.w or np.linalg.norm(s2) < 1e-6:
        return False
    cosv = float(unit(s1) @ unit(s2))
    return np.degrees(np.arccos(np.clip(cosv, -1, 1))) > ang


def _is_junction_end(m: Model, i: int, e: int) -> bool:
    p = m.paths[i]
    if p.closed or len(p.A) < 3:
        return False
    a = p.A[0] if e == 0 else p.A[-1]
    b = p.A[1] if e == 0 else p.A[-2]
    d_a, d_b = np.inf, np.inf
    for j, q in enumerate(m.paths):
        if j == i:
            continue
        f = q.flat(1.0)
        da = float(np.linalg.norm(f - a, axis=1).min())
        db = float(np.linalg.norm(f - b, axis=1).min())
        if da < d_a:
            d_a = da
        if db < d_b:
            d_b = db
    if d_a <= 0.25 * p.w:
        return True
    return d_a <= 0.55 * p.w and d_b > max(0.45 * p.w, d_a + 0.15 * p.w)


def find_spurs(m: Model):
    return [(i, e) for i, p in enumerate(m.paths) for e in (0, 1) if _spur(p, e) and not _is_junction_end(m, i, e)]


def trim_tail(m: Model, i, e):
    m = m.copy()
    p = m.paths[i]
    if not _spur(p, e) or _is_junction_end(m, i, e):
        return m
    if e == 0:
        p.A, p.Hin, p.Hout = p.A[1:], p.Hin[1:], p.Hout[1:]
        p.Hin[0] = p.A[0]
    else:
        p.A, p.Hin, p.Hout = p.A[:-1], p.Hin[:-1], p.Hout[:-1]
        p.Hout[-1] = p.A[-1]
    return m


def prune_apex_overshoot(p: Path) -> Path:
    """Drop false overshoot tongues at acute V-apexes / crevices / notches where medial axis
    doubles back by > 115 deg within < 0.45 * w."""
    n = len(p.A)
    if n < 4:
        return p
    w = p.w
    A = p.A.copy()
    Hin = p.Hin.copy()
    Hout = p.Hout.copy()

    changed = True
    while changed and len(A) >= (5 if p.closed else 4):
        changed = False
        N = len(A) - 1 if p.closed else len(A)
        for k in range(N):
            prev_idx = (k - 1) % N if p.closed else k - 1
            next_idx = (k + 1) % N if p.closed else k + 1
            if not p.closed and (prev_idx < 0 or next_idx >= len(A)):
                continue
            v_in = A[k] - A[prev_idx]
            v_out = A[next_idx] - A[k]
            l_in = float(np.linalg.norm(v_in))
            l_out = float(np.linalg.norm(v_out))
            if l_in < 1e-4 or l_out < 1e-4:
                continue
            u_in = v_in / l_in
            u_out = v_out / l_out
            cos_turn = float(u_in @ u_out)

            # Double back by > 115 degrees with short segment (< 0.45 * w)
            if cos_turn < -0.40 and (l_in < 0.45 * w or l_out < 0.45 * w):
                p_prev = A[prev_idx]
                p_next = A[next_idx]
                chord = p_next - p_prev
                L_chord = float(np.linalg.norm(chord))
                if L_chord > 1e-4:
                    if (Hout[prev_idx] - p_prev) @ (A[k] - p_prev) > 0:
                        Hout[prev_idx] = p_prev + (chord / 3.0)
                    if (Hin[next_idx] - p_next) @ (A[k] - p_next) > 0:
                        Hin[next_idx] = p_next - (chord / 3.0)

                A = np.delete(A, k, axis=0)
                Hin = np.delete(Hin, k, axis=0)
                Hout = np.delete(Hout, k, axis=0)
                if p.closed:
                    if k == 0 or k == N:
                        A[-1] = A[0]
                        Hin[-1] = Hin[0]
                        Hout[-1] = Hout[0]
                changed = True
                break

    # Drop adjacent duplicate anchors closer than max(0.4, 0.22 * w)
    N = len(A) - 1 if p.closed else len(A)
    keep = [0]
    for k in range(1, N):
        if np.linalg.norm(A[k] - A[keep[-1]]) < max(0.4, 0.22 * w):
            continue
        keep.append(k)
    if p.closed:
        if np.linalg.norm(A[keep[-1]] - A[0]) < max(0.4, 0.22 * w) and len(keep) > 3:
            keep.pop()
        keep.append(len(A) - 1)
    else:
        if (len(A) - 1) not in keep:
            keep.append(len(A) - 1)

    if len(keep) != len(A):
        A = A[keep]
        Hin = Hin[keep]
        Hout = Hout[keep]
        if p.closed:
            A[-1] = A[0]
            Hin[-1] = Hin[0]
            Hout[-1] = Hout[0]

    return Path(A, Hin, Hout, p.w, p.join, p.ml, p.closed)


def prune_all_apexes(m: Model) -> Model:
    """Apply prune_apex_overshoot to all paths in the model."""
    m = m.copy()
    for i in range(len(m.paths)):
        m.paths[i] = prune_apex_overshoot(m.paths[i])
    return m



================================================================================
# FILE: linework/opt.py
================================================================================

"""Gradient-based Edit core: fits Bezier control points + stroke widths to the source ink map.

Soft coverage of every path:  c = sigmoid((w/2 - dist(pixel, path)) / tau),  union = max over paths.
Loss = sum (union - ink)^2 + weak priors.  Analytic gradients through the point-to-polyline distance,
optimised with L-BFGS over tau = coarse -> fine, so edges snap to sub-pixel accuracy.
"""
from __future__ import annotations
import numpy as np, cv2
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from .model import Model, Path


def _ctrl(p: Path):
    n = len(p.A) - 1
    C = np.zeros((3 * n + 1, 2))
    C[0] = p.A[0]
    for i in range(n):
        C[3 * i + 1] = p.Hout[i]
        C[3 * i + 2] = p.Hin[i + 1]
        C[3 * i + 3] = p.A[i + 1]
    return C


def _unctrl(p: Path, C):
    n = len(p.A) - 1
    if p.closed:
        C = C.copy()
        C[-1] = C[0]
    p.A[0] = C[0]
    for i in range(n):
        p.Hout[i] = C[3 * i + 1]
        p.Hin[i + 1] = C[3 * i + 2]
        p.A[i + 1] = C[3 * i + 3]
    if p.closed:
        p.Hin[0] = p.Hin[-1]
        p.Hout[-1] = p.Hout[0]


def _sample_matrix(C, step=0.9):
    """Dense matrix M (nS x nC): samples = M @ C."""
    n = (len(C) - 1) // 3
    rows, blocks = [], []
    for i in range(n):
        c = C[3 * i : 3 * i + 4]
        L = sum(np.linalg.norm(c[k + 1] - c[k]) for k in range(3))
        k = max(4, int(np.ceil(L / step)))
        t = np.linspace(0, 1, k + 1)
        if i < n - 1:
            t = t[:-1]
        mt = 1 - t
        B = np.stack([mt**3, 3 * mt**2 * t, 3 * mt * t**2, t**3], 1)
        blocks.append((i, B))
    nS = sum(len(B) for _, B in blocks)
    M = np.zeros((nS, len(C)))
    r = 0
    for i, B in blocks:
        M[r : r + len(B), 3 * i : 3 * i + 4] = B
        r += len(B)
    return M


def _poly_dist(X, S):
    """Distance from points X (m,2) to polyline S (nS,2); returns d, seg index, t."""
    tree = cKDTree(S)
    _, j = tree.query(X)
    nS = len(S)
    best_d = np.full(len(X), np.inf)
    best_s = np.zeros(len(X), int)
    best_t = np.zeros(len(X))
    for off in (-1, 0):
        s = np.clip(j + off, 0, nS - 2)
        a, b = S[s], S[s + 1]
        ab = b - a
        den = np.maximum((ab * ab).sum(1), 1e-12)
        t = np.clip(((X - a) * ab).sum(1) / den, 0, 1)
        q = a + ab * t[:, None]
        d = np.hypot(X[:, 0] - q[:, 0], X[:, 1] - q[:, 1])
        m = d < best_d
        best_d = np.where(m, d, best_d)
        best_s = np.where(m, s, best_s)
        best_t = np.where(m, t, best_t)
    return best_d, best_s, best_t


def refine(model: Model, D: np.ndarray, free=None, window=None, taus=(1.0, 0.6, 0.38), iters=30,
           lam_pos=0.02, lam_w=0.05, fit_width=True, wtarget=None, mu_g1=300.0, g1_deg=30.0):
    """Return a refined copy of `model`. `free`: indices of paths to optimise (default all);
    `window`: (x0,y0,x1,y1) restricting the loss region."""
    m = model.copy()
    H, W = D.shape
    x0, y0, x1, y1 = (0, 0, W, H) if window is None else (max(int(window[0]), 0), max(int(window[1]), 0), min(int(window[2]), W), min(int(window[3]), H))
    if x1 - x0 < 3 or y1 - y0 < 3:
        return m
    free = list(range(len(m.paths))) if free is None else [i for i in free if 0 <= i < len(m.paths)]
    if not free:
        return m
    Dw = D[y0:y1, x0:x1]
    wh = (y1 - y0, x1 - x0)
    C0 = {i: _ctrl(m.paths[i]) for i in free}
    w0 = {i: m.paths[i].w for i in free}
    fixed = [i for i in range(len(m.paths)) if i not in free]

    for stage, tau in enumerate(taus):
        # pixel sets per free path (band around current polyline)
        Ms, idxs, pix = {}, {}, {}
        for i in free:
            p = m.paths[i]
            Ms[i] = _sample_matrix(_ctrl(p))
            S = Ms[i] @ _ctrl(p)
            mk = np.zeros(wh, np.uint8)
            q = np.round((S - [x0, y0]) * 16).astype(np.int32)
            cv2.polylines(mk, [q], False, 1, thickness=int(p.w + 6 + 6 * tau), lineType=cv2.LINE_8, shift=4)
            ii = np.flatnonzero(mk.ravel())
            idxs[i] = ii
            yy, xx = np.divmod(ii, wh[1])
            pix[i] = np.stack([xx + x0 + 0.5, yy + y0 + 0.5], 1)
        # constant coverage from fixed paths
        base = np.zeros(wh, np.float32)
        for i in fixed:
            p = m.paths[i]
            S = p.flat(0.7)
            mk = np.zeros(wh, np.uint8)
            q = np.round((S - [x0, y0]) * 16).astype(np.int32)
            cv2.polylines(mk, [q], False, 1, thickness=int(p.w + 6 + 6 * tau), lineType=cv2.LINE_8, shift=4)
            ii = np.flatnonzero(mk.ravel())
            yy, xx = np.divmod(ii, wh[1])
            X = np.stack([xx + x0 + 0.5, yy + y0 + 0.5], 1)
            d, _, _ = _poly_dist(X, S)
            c = 1 / (1 + np.exp(-(p.w / 2 - d) / tau))
            bf = base.ravel()
            bf[ii] = np.maximum(bf[ii], c)
        joints, seg_ref = {}, {}
        for i in free:
            C = _ctrl(m.paths[i])
            n = (len(C) - 1) // 3
            v0 = C0[i][3::3] - C0[i][0:-3:3]
            L0 = np.linalg.norm(v0, axis=1)
            u0 = v0 / np.maximum(L0, 1e-6)[:, None]
            n0 = np.stack([-u0[:, 1], u0[:, 0]], 1)
            ho0 = C0[i][1::3] - C0[i][0:-3:3]
            hi0 = C0[i][3::3] - C0[i][2::3]
            seg_ref[i] = (u0, n0, L0, ho0, hi0)
            ks = []
            rng = range(0 if m.paths[i].closed else 1, n if m.paths[i].closed else n)
            for k in rng:
                a = C[3 * k]
                hin = C[3 * k - 1] if k > 0 else C[-2]
                hout = C[3 * k + 1]
                p, q = a - hin, hout - a
                np_, nq = np.linalg.norm(p), np.linalg.norm(q)
                if np_ < 1e-6 or nq < 1e-6:
                    continue
                if np.degrees(np.arccos(np.clip(p @ q / (np_ * nq), -1, 1))) < g1_deg:
                    ks.append(k)
            joints[i] = np.array(ks, int)
        union_idx = np.unique(np.concatenate([idxs[i] for i in free]))
        sizes = [(len(C0[i]) * 2) for i in free]
        offs = np.r_[0, np.cumsum(sizes)]
        nw = len(free) if fit_width else 0
        th0 = np.concatenate([_ctrl(m.paths[i]).ravel() for i in free] + ([[m.paths[i].w for i in free]] if fit_width else []))
        thref = np.concatenate([C0[i].ravel() for i in free] + ([[w0[i] for i in free]] if fit_width else []))
        if wtarget is None:
            wt = np.array([w0[i] for i in free])
        else:
            wt = np.full(len(free), wtarget)

        def unpack(th):
            Cs = {i: th[offs[k] : offs[k + 1]].reshape(-1, 2) for k, i in enumerate(free)}
            ws = th[offs[-1] :] if fit_width else np.array([m.paths[i].w for i in free])
            return Cs, ws

        def f(th):
            Cs, ws = unpack(th)
            cov = base.ravel().copy()
            owner = np.full(cov.shape, -1, np.int16)
            store = {}
            for k, i in enumerate(free):
                C = Cs[i].copy()
                if m.paths[i].closed:
                    C[-1] = C[0]
                S = Ms[i] @ C
                d, s, t = _poly_dist(pix[i], S)
                r = ws[k] / 2
                c = 1 / (1 + np.exp(-(r - d) / tau))
                ii = idxs[i]
                upd = c > cov[ii]
                cov[ii[upd]] = c[upd]
                owner[ii[upd]] = k
                store[k] = (S, d, s, t, c, upd)
            diff = cov[union_idx] - Dw.ravel()[union_idx]
            loss = float((diff**2).sum())
            gfull = np.zeros(cov.shape)
            gfull[union_idx] = 2 * diff
            g = np.zeros_like(th)
            for k, i in enumerate(free):
                S, d, s, t, c, upd = store[k]
                ii = idxs[i]
                own = upd & (owner[ii] == k)
                if not own.any():
                    continue
                gc = gfull[ii][own]
                cc = c[own]
                sg = cc * (1 - cc) / tau
                gd = -gc * sg
                if fit_width:
                    g[offs[-1] + k] += float((gc * sg).sum()) * 0.5
                X = pix[i][own]
                dd = d[own]
                ss = s[own]
                tt = t[own]
                q = S[ss] * (1 - tt)[:, None] + S[ss + 1] * tt[:, None]
                e = (q - X) / np.maximum(dd, 1e-6)[:, None]
                ge = gd[:, None] * e
                nS_ = len(S)
                w0_, w1_ = (1 - tt)[:, None], tt[:, None]
                gS = np.empty_like(S)
                for ax in (0, 1):  # scatter-add with bincount (much faster than np.add.at)
                    gS[:, ax] = (np.bincount(ss, ge[:, ax] * w0_[:, 0], nS_) + np.bincount(ss + 1, ge[:, ax] * w1_[:, 0], nS_ + 1)[:nS_])
                gC = Ms[i].T @ gS
                if m.paths[i].closed:
                    gC[0] += gC[-1]
                    gC[-1] = 0
                g[offs[k] : offs[k + 1]] += gC.ravel()
            # G1 continuity at joints that are smooth in the current model
            for k, i in enumerate(free):
                ks = joints[i]
                if not len(ks) or mu_g1 <= 0:
                    continue
                C = Cs[i]
                ia = 3 * ks
                ih = np.where(ks > 0, 3 * ks - 1, len(C) - 2)
                io = 3 * ks + 1
                p = C[ia] - C[ih]
                q = C[io] - C[ia]
                npn = np.maximum(np.linalg.norm(p, axis=1), 1e-3)
                nqn = np.maximum(np.linalg.norm(q, axis=1), 1e-3)
                cr = p[:, 0] * q[:, 1] - p[:, 1] * q[:, 0]
                sn = cr / (npn * nqn)
                loss += mu_g1 * float((sn**2).sum())
                dc = (2 * mu_g1 * sn / (npn * nqn))[:, None]
                dp = np.stack([q[:, 1], -q[:, 0]], 1)
                dq = np.stack([-p[:, 1], p[:, 0]], 1)
                gk = np.zeros_like(C)
                np.add.at(gk, ia, dc * (dp - dq))
                np.add.at(gk, ih, dc * (-dp))
                np.add.at(gk, io, dc * dq)
                if m.paths[i].closed:
                    gk[0] += gk[-1]
                    gk[-1] = 0
                g[offs[k] : offs[k + 1]] += gk.ravel()
            # Chord & handle anti-fold barrier (prevents segments/handles from reversing into Z-folds or swinging sideways)
            for k, i in enumerate(free):
                C = Cs[i]
                u0, n0, L0, ho0, hi0 = seg_ref[i]
                if not len(L0):
                    continue
                v = C[3::3] - C[0:-3:3]
                proj = (v * u0).sum(1)
                viol = 0.45 * L0 - proj
                h_out = C[1::3] - C[0:-3:3]
                h_in = C[3::3] - C[2::3]
                v_out = 0.08 * L0 - (h_out * u0).sum(1)
                v_in = 0.08 * L0 - (h_in * u0).sum(1)
                dho = h_out - ho0
                dhi = h_in - hi0
                lim_n = np.maximum(1.2, 0.12 * L0)
                lim_u = np.maximum(2.0, 0.25 * L0)
                no_s = (dho * n0).sum(1)
                ni_s = (dhi * n0).sum(1)
                uo_s = (dho * u0).sum(1)
                ui_s = (dhi * u0).sum(1)
                vo_n = np.abs(no_s) - lim_n
                vi_n = np.abs(ni_s) - lim_n
                vo_u = np.abs(uo_s) - lim_u
                vi_u = np.abs(ui_s) - lim_u
                if (viol > 0).any() or (v_out > 0).any() or (v_in > 0).any() or (vo_n > 0).any() or (vi_n > 0).any() or (vo_u > 0).any() or (vi_u > 0).any():
                    gk = np.zeros_like(C)
                    if (viol > 0).any():
                        m_v = viol > 0
                        loss += 250.0 * float((viol[m_v] ** 2).sum())
                        gv = -500.0 * viol[m_v, None] * u0[m_v]
                        idx_s = np.flatnonzero(m_v)
                        np.add.at(gk, 3 * idx_s + 3, gv)
                        np.add.at(gk, 3 * idx_s, -gv)
                    if (v_out > 0).any():
                        m_o = v_out > 0
                        loss += 150.0 * float((v_out[m_o] ** 2).sum())
                        go = -300.0 * v_out[m_o, None] * u0[m_o]
                        idx_o = np.flatnonzero(m_o)
                        np.add.at(gk, 3 * idx_o + 1, go)
                        np.add.at(gk, 3 * idx_o, -go)
                    if (v_in > 0).any():
                        m_i = v_in > 0
                        loss += 150.0 * float((v_in[m_i] ** 2).sum())
                        gi = -300.0 * v_in[m_i, None] * u0[m_i]
                        idx_i = np.flatnonzero(m_i)
                        np.add.at(gk, 3 * idx_i + 3, gi)
                        np.add.at(gk, 3 * idx_i + 2, -gi)
                    for m_mask, val, sgn, vec, idx_h, idx_a, sign_h in (
                        (vo_n > 0, vo_n, np.sign(no_s), n0, 1, 0, 1.0),
                        (vi_n > 0, vi_n, np.sign(ni_s), n0, 2, 3, -1.0),
                        (vo_u > 0, vo_u, np.sign(uo_s), u0, 1, 0, 1.0),
                        (vi_u > 0, vi_u, np.sign(ui_s), u0, 2, 3, -1.0),
                    ):
                        if m_mask.any():
                            loss += 120.0 * float((val[m_mask] ** 2).sum())
                            gh = 240.0 * (val[m_mask] * sgn[m_mask])[:, None] * vec[m_mask] * sign_h
                            idx_m = np.flatnonzero(m_mask)
                            np.add.at(gk, 3 * idx_m + idx_h, gh)
                            np.add.at(gk, 3 * idx_m + idx_a, -gh)
                    if m.paths[i].closed:
                        gk[0] += gk[-1]
                        gk[-1] = 0
                    g[offs[k] : offs[k + 1]] += gk.ravel()
            # priors
            dth = th - thref
            pos_part = dth[: offs[-1]]
            loss += lam_pos * float((pos_part**2).sum())
            g[: offs[-1]] += 2 * lam_pos * pos_part
            if fit_width:
                dw = th[offs[-1] :] - wt
                loss += lam_w * float((dw**2).sum())
                g[offs[-1] :] += 2 * lam_w * dw
            return loss, g

        nctrl = len(th0) - nw
        bnds = [(None, None)] * nctrl + [(max(1.0, 0.5 * w0[i]), 2.0 * w0[i]) for i in free] if fit_width else None
        res = minimize(f, th0, jac=True, method="L-BFGS-B", bounds=bnds, options=dict(maxiter=iters, maxcor=12, ftol=2e-6, gtol=1e-6))
        Cs, ws = unpack(res.x)
        for k, i in enumerate(free):
            p = m.paths[i]
            _unctrl(p, Cs[i])
            if fit_width:
                p.w = float(ws[k])
    return m



================================================================================
# FILE: linework/lessons.py
================================================================================

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
    sx_kinds = {}
    sx = metrics.get("structure") or {}
    for s in sx.get("sites", []):
        k = sx_kinds.setdefault(s.get("kind", "unknown"), [0, 0])
        k[0] += 1
        k[1] += int(bool(s.get("fixed")))
    jn = metrics.get("joins") or {}
    line = json.dumps(dict(ts=int(time.time()), version=version, name=name, iou=round(metrics.get("iou", 0), 4), issues=metrics.get("issues", {}),
                           finisher=kinds, seconds=metrics.get("seconds"),
                           structure=dict(before=sx.get("before", 0.0), after=sx.get("after", 0.0), found=sx.get("found", 0), fixed=sx.get("fixed", 0),
                                          kinds=sx_kinds,
                                          unresolved=[u.get("kind") for u in sx.get("unresolved", [])]),
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
    st = dict(found=0, fixed=0, kinds={}, unresolved={})
    for r in rows:
        jr = r.get("joins") or {}
        jt["total"] += jr.get("total", 0)
        jt["clean"] += jr.get("clean", 0)
        jt["fixed"] += jr.get("fixed", 0)
        for rs in jr.get("unresolved", []):
            for x in (rs or []):
                jt["unresolved"][x] = jt["unresolved"].get(x, 0) + 1
        sr = r.get("structure") or {}
        st["found"] += sr.get("found", 0)
        st["fixed"] += sr.get("fixed", 0)
        for k, (n, f) in (sr.get("kinds") or {}).items():
            entry = st["kinds"].setdefault(k, dict(found=0, fixed=0))
            entry["found"] += n
            entry["fixed"] += f
        for u in sr.get("unresolved", []):
            st["unresolved"][u] = st["unresolved"].get(u, 0) + 1
        for k, (n, f) in (r.get("finisher") or {}).items():
            p = passes.setdefault(k, dict(found=0, fixed=0))
            p["found"] += n
            p["fixed"] += f
        for k, v in (r.get("issues") or {}).items():
            issues[k] = issues.get(k, 0) + int(v or 0)
    return dict(icons=len(rows), passes=passes, remaining_issues=issues, skipped=sorted(skip_kinds()), trace=_stats().get("trace", {}), joints=jt, structure=st)


def clear():
    """Clear all remembered best models, defect logs, and trace statistics."""
    global _skip_cache
    _skip_cache = (0.0, set())
    best_dir = os.path.join(_dir(), "best")
    cleared = dict(best_count=0, log_cleared=False, stats_cleared=False)
    if os.path.exists(best_dir):
        for fname in os.listdir(best_dir):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(best_dir, fname))
                    cleared["best_count"] += 1
                except Exception:
                    pass
    log_path = os.path.join(_dir(), "log.jsonl")
    if os.path.exists(log_path):
        try:
            with open(log_path, "w") as f:
                f.write("")
            cleared["log_cleared"] = True
        except Exception:
            pass
    stats_path = os.path.join(_dir(), "stats.json")
    try:
        _atomic_write(stats_path, json.dumps({}))
        cleared["stats_cleared"] = True
    except Exception:
        pass
    d = _dir()
    for fname in os.listdir(d):
        if fname.endswith(".tmp"):
            try:
                os.remove(os.path.join(d, fname))
            except Exception:
                pass
    return cleared


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))



================================================================================
# FILE: linework/setlevel.py
================================================================================

"""Set-level consistency: an icon set must look like ONE set, from the first icon to the last.

* harmonize_widths: stroke widths are clustered over the WHOLE set (not icon by icon) and every icon is snapped to the shared weight classes
  (each change verified against that icon's source: kept only if the match does not get worse).
* weak_icons / better: icons that came out clearly worse than the rest of the set get a second, longer pass; the better result wins.
"""
from __future__ import annotations
import numpy as np
from .model import Model
from .doctor import Doctor, ink_of
from .trace import ink_map
from . import finisher as FN
from . import lessons as LS


def harmonize_widths(models, crops, max_dev=0.4):
    """models/crops: parallel lists (crop-local models, uint8 crops). Returns (new_models, report)."""
    allp, own = [], []
    for k, m in enumerate(models):
        for p in m.paths:
            allp.append(p)
            own.append(k)
    if len(allp) < 2:
        return models, dict(changed=0, classes=[])
    big = Model(allp, 0, 0)
    plan = FN.width_plan(big, max_dev=max_dev)
    # class centres actually used
    centers = sorted({round(w, 2) for w in plan.values()})
    per = {}
    for gi, w in plan.items():
        per.setdefault(own[gi], []).append((gi, w))
    # index of each global path inside its own model
    local, cnt = {}, {}
    for gi, k in enumerate(own):
        local[gi] = cnt.get(k, 0)
        cnt[k] = local[gi] + 1
    out, changed = list(models), 0
    for k, items in per.items():
        m = models[k]
        D = ink_map(crops[k])
        doc = Doctor(D)
        cur = doc.soft(ink_of(m))
        topo0 = FN._topo(m)
        for dev in (max_dev, 0.12):
            cand = m.copy()
            n = 0
            for gi, w in items:
                p = cand.paths[local[gi]]
                if abs(p.w - w) / w <= dev and abs(p.w - w) > 1e-6:
                    p.w = w
                    n += 1
            if not n:
                continue
            s2 = doc.soft(ink_of(cand))
            if s2 <= cur + max(2.0, 0.003 * cur) and FN._topo(cand) <= topo0:
                out[k] = cand
                changed += 1
                break
    return out, dict(changed=changed, classes=centers)


def weak_icons(mets, max_n=3, floor=0.955, rel=0.02):
    """Indices (into mets) of icons clearly worse than the rest of the set."""
    sc = [LS.quality_score(m) if m else None for m in mets]
    ok = [s for s in sc if s is not None]
    if len(ok) < 3:
        return []
    med = float(np.median(ok))
    weak = [(s, k) for k, s in enumerate(sc) if s is not None and (s < med - rel or (mets[k].get("iou", 1) < floor))]
    return [k for _, k in sorted(weak)[:max_n]]


def better(old_metrics, new_metrics):
    return LS.quality_score(new_metrics) > LS.quality_score(old_metrics) + 1e-4



================================================================================
# FILE: linework/audit.py
================================================================================

"""Structural audit of an output SVG: duplicate / near-coincident centerlines, kinks, node counts."""
from __future__ import annotations
import re
import numpy as np
from scipy.spatial import cKDTree
from .model import Path
from .geom import resample


def parse_svg_paths(svg: str):
    out = []
    for d, w in re.findall(r'<path d="([^"]+)" stroke-width="([\d.]+)"', svg):
        closed = d.strip().endswith("Z")
        nums = np.array([float(x) for x in re.findall(r"-?\d+\.?\d*", d)]).reshape(-1, 2)
        A, Hi, Ho = [nums[0]], [nums[0]], []
        i = 1
        while i + 2 < len(nums) + 0 and i < len(nums):
            Ho.append(nums[i]); Hi.append(nums[i + 1]); A.append(nums[i + 2]); i += 3
        Ho.append(A[-1])
        out.append(Path(A, Hi, Ho, float(w), closed=closed))
    return out


def audit(paths, near=0.35, min_run=0.8):
    """Return list of (i, j, run_length_px) where path i runs alongside path j closer than near*w."""
    flats = [resample(p.flat(), 1.0) for p in paths]
    trees = [cKDTree(f) for f in flats]
    found = []
    for i, p in enumerate(paths):
        for j in range(len(paths)):
            if i == j:
                continue
            w = min(paths[i].w, paths[j].w)
            d, _ = trees[j].query(flats[i])
            close = d < near * w
            run = best = 0
            for c in close:
                run = run + 1 if c else 0
                best = max(best, run)
            if best >= min_run * w:
                found.append((i, j, best))
    # symmetric pairs reported once
    seen, res = set(), []
    for i, j, r in found:
        k = (min(i, j), max(i, j))
        if k not in seen:
            seen.add(k)
            res.append((i, j, r))
    return res


def kinks(paths, lo=6, hi=30):
    n = 0
    for p in paths:
        for k in range(1, len(p.A) - 1):
            a, b = p.A[k] - p.Hin[k], p.Hout[k] - p.A[k]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na > 1e-6 and nb > 1e-6:
                ang = np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1)))
                n += lo < ang < hi
    return n



================================================================================
# FILE: linework/render.py
================================================================================

"""Output engine: SVG -> grayscale raster. Uses resvg (fast, exact AA); falls back to cairosvg / Chromium."""
from __future__ import annotations
import io, os, tempfile
import numpy as np, cv2

_BACKEND = None


def _pick():
    global _BACKEND
    if _BACKEND:
        return _BACKEND
    try:
        import resvg_py  # noqa
        _BACKEND = "resvg"
    except Exception:
        try:
            import cairosvg  # noqa
            _BACKEND = "cairosvg"
        except Exception:
            _BACKEND = "playwright"
    return _BACKEND


def backend_name():
    return _pick()


def render_gray(svg: str, width: int, height: int) -> np.ndarray:
    """Render an SVG string (white background rect expected) to a uint8 grayscale array (height, width)."""
    b = _pick()
    if b == "resvg":
        import resvg_py
        data = bytes(resvg_py.svg_to_bytes(svg_string=svg))
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    elif b == "cairosvg":
        import cairosvg
        data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    else:
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as td:
            fn = os.path.join(td, "a.svg")
            open(fn, "w").write(svg)
            with sync_playwright() as p:
                br = p.chromium.launch()
                pg = br.new_page(viewport={"width": width, "height": height})
                pg.goto("file://" + fn)
                pg.screenshot(path=os.path.join(td, "a.png"))
                br.close()
            im = cv2.imread(os.path.join(td, "a.png"), cv2.IMREAD_UNCHANGED)
    if im.ndim == 3 and im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        rgb = im[:, :, :3].astype(np.float32) * a + 255 * (1 - a)
        g = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    elif im.ndim == 3:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    else:
        g = im
    if g.shape != (height, width):
        g = cv2.resize(g, (width, height), interpolation=cv2.INTER_AREA)
    return g

