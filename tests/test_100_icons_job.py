"""Test harness for full 100-icon sheet vectorization.
Runs all 100 icons end-to-end through linework pipeline, tracks metrics,
identifies defects/outliers, and verifies fidelity.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
import cv2
import numpy as np

from linework.pipeline import process_sheet, process_icon, Options

def run_100_icons_test():
    sheet_path = Path("tests/sheet_100_icons.png")
    assert sheet_path.exists(), f"Missing {sheet_path}"

    gray = cv2.imread(str(sheet_path), cv2.IMREAD_GRAYSCALE)
    assert gray is not None, "Failed to read sheet image"
    H, W = gray.shape
    print(f"Loaded sheet: {W}x{H}px")

    t_split0 = time.time()
    W_s, H_s, jobs = process_sheet(gray, Options(fresh=True))
    t_split = time.time() - t_split0
    print(f"Sheet splitting completed in {t_split:.3f}s: Found {len(jobs)} icons")
    assert len(jobs) == 100, f"Expected exactly 100 icons, but found {len(jobs)}"

    results = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    t_start_all = time.time()
    opts = Options(fresh=True, memory=False, quality="standard", joins=True, decision=True)

    print("\nStarting end-to-end vectorization across all 100 icons (4 workers)...", flush=True)
    print(f"{'Idx':<4} | {'Box':<22} | {'IoU (%)':<8} | {'Hard':<6} | {'Paths':<6} | {'Nodes':<6} | {'Time (s)':<8} | Status", flush=True)
    print("-" * 80, flush=True)

    def process_single(item):
        k, crop, off = item
        t0 = time.time()
        try:
            res = process_icon(crop, opts, name=f"icon_{k}")
            dur = time.time() - t0
            met = res.get("metrics") or {}
            iou = float(met.get("iou", 0.0)) * 100.0
            hard = int(met.get("hard", 0))
            m = res.get("model")
            paths = len(m.paths) if m else 0
            nodes = sum(len(p.A) for p in m.paths) if m else 0

            status = "PASS"
            if iou < 97.0 or hard > 45:
                status = "WARN"
            if iou < 94.0 or hard > 80:
                status = "FAIL"

            entry = {
                "k": k,
                "off": [int(off[0]), int(off[1])],
                "shape": [int(crop.shape[1]), int(crop.shape[0])],
                "iou": round(iou, 2),
                "hard": hard,
                "paths": paths,
                "nodes": nodes,
                "dur": round(dur, 3),
                "status": status,
                "metrics": met,
            }
            print(f"{k:<4} | {str(off):<22} | {iou:>7.2f}% | {hard:>6} | {paths:>6} | {nodes:>6} | {dur:>7.3f}s | {status}", flush=True)
            return entry
        except Exception as e:
            dur = time.time() - t0
            entry = {
                "k": k,
                "off": [int(off[0]), int(off[1])],
                "shape": [int(crop.shape[1]), int(crop.shape[0])],
                "error": str(e),
                "dur": round(dur, 3),
                "status": "CRASH",
            }
            print(f"{k:<4} | {str(off):<22} | ERROR: {e} ({dur:.3f}s)", flush=True)
            return entry

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(process_single, j): j[0] for j in jobs}
        for fut in as_completed(futs):
            results.append(fut.result())

    results.sort(key=lambda r: r["k"])

    total_time = time.time() - t_start_all
    ious = [r["iou"] for r in results if "iou" in r]
    hards = [r["hard"] for r in results if "hard" in r]
    durs = [r["dur"] for r in results]

    avg_iou = float(np.mean(ious)) if ious else 0.0
    min_iou = float(np.min(ious)) if ious else 0.0
    max_hard = int(np.max(hards)) if hards else 0
    avg_dur = float(np.mean(durs)) if durs else 0.0

    print("\n" + "=" * 80)
    print("100-ICON SYSTEM TEST SUMMARY:")
    print(f"Total icons processed:  {len(results)}/100")
    print(f"Average IoU Fidelity:   {avg_iou:.2f}%")
    print(f"Minimum IoU Fidelity:   {min_iou:.2f}%")
    print(f"Maximum Hard Error:     {max_hard}")
    print(f"Average Process Time:   {avg_dur:.3f}s / icon")
    print(f"Total Elapsed Time:     {total_time:.2f}s")
    print("=" * 80)

    # Save detailed JSON summary
    summary = {
        "total": len(results),
        "avg_iou": round(avg_iou, 2),
        "min_iou": round(min_iou, 2),
        "max_hard": max_hard,
        "avg_dur": round(avg_dur, 3),
        "total_time": round(total_time, 2),
        "results": results,
    }
    Path("tests/test_100_icons_results.json").write_text(json.dumps(summary, indent=2))
    print("Saved test results to tests/test_100_icons_results.json")

    # Filter out warnings / fails
    problematic = [r for r in results if r.get("status") in ("WARN", "FAIL", "CRASH")]
    if problematic:
        print(f"\nIdentified {len(problematic)} problematic icon(s):")
        for p in problematic:
            print(f"  Icon #{p['k']}: IoU={p.get('iou')}%, Hard={p.get('hard')}, Status={p['status']}, Error={p.get('error')}")
    else:
        print("\nAll 100 icons PASSED with outstanding fidelity!")

    return summary

if __name__ == "__main__":
    run_100_icons_test()
