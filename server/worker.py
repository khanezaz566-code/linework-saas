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
