import os
os.environ["LINEWORK_MEMORY"] = "0"
import sys, time
sys.path.insert(0, '.')
import numpy as np, cv2
from server.app import _start, cancel_job_by_id, cancel_all_jobs, clear_cache, JOBS, _POOL, pool


def test_job_cancellation():
    """Starting a job and cancelling it should stop the job and terminate workers."""
    # Create a dummy image
    img = np.full((120, 120), 255, np.uint8)
    cv2.circle(img, (60, 60), 40, 0, 4)
    
    r = _start(img, "test_cancel", "fast", 0.5, 98.5, fresh=True)
    job_id = r["id"]
    job = JOBS[job_id]
    assert job["status"] in ("queued", "splitting", "running")
    
    # Cancel the job
    cancel_job_by_id(job_id)
    assert job["status"] == "cancelled"
    assert job.get("cancelled") is True
    print("PASS: test_job_cancellation")


def test_clear_cache_stops_active_jobs():
    """Clearing cache must cancel active jobs and reset worker pool."""
    img = np.full((120, 120), 255, np.uint8)
    cv2.circle(img, (60, 60), 40, 0, 4)
    
    r = _start(img, "test_clear_cache", "fast", 0.5, 98.5, fresh=True)
    job_id = r["id"]
    job = JOBS[job_id]
    
    res = clear_cache()
    assert res["ok"] is True
    assert job["status"] == "cancelled"
    assert job.get("cancelled") is True
    print("PASS: test_clear_cache_stops_active_jobs")


def test_new_job_cancels_previous_job():
    """Starting a new job automatically cancels any active previous job."""
    img = np.full((120, 120), 255, np.uint8)
    cv2.circle(img, (60, 60), 40, 0, 4)
    
    r1 = _start(img, "job_1", "fast", 0.5, 98.5, fresh=True)
    j1 = JOBS[r1["id"]]
    
    r2 = _start(img, "job_2", "fast", 0.5, 98.5, fresh=True)
    j2 = JOBS[r2["id"]]
    
    assert j1["status"] == "cancelled"
    assert j1.get("cancelled") is True
    assert j2["status"] in ("queued", "splitting", "running")
    cancel_all_jobs()
    print("PASS: test_new_job_cancels_previous_job")


if __name__ == "__main__":
    test_job_cancellation()
    test_clear_cache_stops_active_jobs()
    test_new_job_cancels_previous_job()
    print("\nALL CANCELLATION & CACHE TESTS PASSED!")
