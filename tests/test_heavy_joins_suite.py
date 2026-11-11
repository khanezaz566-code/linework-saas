"""Massive Test Harness for Heavy-Join Icon Sheets.
Tests multiple sheets (36 icons each) with complex joins and multi-line intersections.
Measures IoU fidelity, hard error pixels, join topology, and identifies bugs.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import cv2
import numpy as np

from linework.pipeline import process_sheet, process_icon, Options
from tests.make_heavy_joins_sheet import make_sheet, HEAVY_JOIN_DRAWERS

def run_suite(start_sheet=0, num_sheets=5, max_workers=4):
    opts = Options(fresh=True, memory=False, quality="standard", joins=True, decision=True)
    all_results = []
    defects = []
    t_global0 = time.time()

    print(f"=== Starting Heavy-Join Suite: Sheets {start_sheet} to {start_sheet + num_sheets - 1} ({num_sheets * 36} icons) ===", flush=True)

    for s_idx in range(start_sheet, start_sheet + num_sheets):
        t_s0 = time.time()
        canvas = make_sheet(s_idx)
        W_s, H_s, jobs = process_sheet(canvas, Options(fresh=True))
        t_split = time.time() - t_s0

        if len(jobs) != 36:
            defects.append({
                "type": "SPLIT_COUNT_MISMATCH",
                "sheet": s_idx,
                "expected": 36,
                "found": len(jobs)
            })
            print(f"[Sheet {s_idx}] SPLIT ERROR: Expected 36 icons, got {len(jobs)} in {t_split:.3f}s", flush=True)
        else:
            print(f"[Sheet {s_idx}] Split 36 icons in {t_split:.3f}s", flush=True)

        def _eval_icon(item):
            k, crop, off = item
            drawer_idx = (k + s_idx * 7) % len(HEAVY_JOIN_DRAWERS)
            drawer_name = HEAVY_JOIN_DRAWERS[drawer_idx].__name__
            t0 = time.time()
            try:
                res = process_icon(crop, opts, name=f"s{s_idx}_icon_{k}")
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
                    "sheet": s_idx,
                    "k": k,
                    "drawer": drawer_name,
                    "iou": round(iou, 2),
                    "hard": hard,
                    "paths": paths,
                    "nodes": nodes,
                    "dur": round(dur, 3),
                    "status": status,
                    "metrics": met,
                }
                print(f"  [Sheet {s_idx} #{k:2d}] {drawer_name:<24}: IoU={iou:6.2f}%, hard={hard:3d}, {dur:.2f}s [{status}]", flush=True)
                return entry
            except Exception as e:
                dur = time.time() - t0
                entry = {
                    "sheet": s_idx,
                    "k": k,
                    "drawer": drawer_name,
                    "error": str(e),
                    "dur": round(dur, 3),
                    "status": "CRASH",
                }
                print(f"  [Sheet {s_idx} #{k:2d}] {drawer_name:<24}: CRASH {e}", flush=True)
                return entry

        sheet_entries = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(_eval_icon, j): j[0] for j in jobs}
            for fut in as_completed(futs):
                sheet_entries.append(fut.result())

        sheet_entries.sort(key=lambda x: x["k"])
        all_results.extend(sheet_entries)

        s_ious = [e["iou"] for e in sheet_entries if "iou" in e]
        s_avg_iou = float(np.mean(s_ious)) if s_ious else 0.0
        s_min_iou = float(np.min(s_ious)) if s_ious else 0.0
        s_dur = time.time() - t_s0
        print(f"[Sheet {s_idx} Done] Avg IoU: {s_avg_iou:.2f}%, Min IoU: {s_min_iou:.2f}%, Total time: {s_dur:.2f}s\n", flush=True)

    t_total = time.time() - t_global0
    ious = [r["iou"] for r in all_results if "iou" in r]
    avg_iou = float(np.mean(ious)) if ious else 0.0
    min_iou = float(np.min(ious)) if ious else 0.0
    crashes = [r for r in all_results if r.get("status") == "CRASH"]
    fails = [r for r in all_results if r.get("status") == "FAIL"]
    warns = [r for r in all_results if r.get("status") == "WARN"]

    print("=" * 80, flush=True)
    print("HEAVY-JOIN SUITE COMPLETE:", flush=True)
    print(f"Total Icons Tested: {len(all_results)} across {num_sheets} sheets", flush=True)
    print(f"Average IoU Fidelity: {avg_iou:.2f}%", flush=True)
    print(f"Minimum IoU Fidelity: {min_iou:.2f}%", flush=True)
    print(f"Crashes: {len(crashes)} | Fails: {len(fails)} | Warns: {len(warns)}", flush=True)
    print(f"Total Time: {t_total:.2f}s ({t_total/len(all_results):.3f}s / icon)", flush=True)
    print("=" * 80, flush=True)

    summary = {
        "sheets": num_sheets,
        "total_icons": len(all_results),
        "avg_iou": round(avg_iou, 2),
        "min_iou": round(min_iou, 2),
        "crashes": crashes,
        "fails": fails,
        "warns": warns,
        "results": all_results,
    }
    out_file = Path(f"tests/heavy_joins_summary_{start_sheet}_{start_sheet + num_sheets}.json")
    out_file.write_text(json.dumps(summary, indent=2))
    return summary

if __name__ == "__main__":
    import sys
    n_sheets = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    run_suite(0, n_sheets, max_workers=6)
