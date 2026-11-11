"""100 Ultra-Complex Icon Benchmark Suite.
Tests 100 distinct complex geometric icons across 56 unique topologies
with varying stroke widths (4-7px), rotations, and high-density junction stress.
Records IoU fidelity, hard error counts, execution time, and detects defects.
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

from linework.pipeline import process_icon, Options
from tests.make_heavy_joins_sheet import HEAVY_JOIN_DRAWERS
from tests.more_complex_drawers import MORE_COMPLEX_DRAWERS

ALL_COMPLEX_DRAWERS = HEAVY_JOIN_DRAWERS + MORE_COMPLEX_DRAWERS  # 36 + 20 = 56 drawers

def generate_complex_icon(idx: int) -> tuple[np.ndarray, str, int]:
    """Generate icon idx (0..99) with varied parameters."""
    drawer_idx = (idx * 3 + (idx // 56)) % len(ALL_COMPLEX_DRAWERS)
    drawer = ALL_COMPLEX_DRAWERS[drawer_idx]
    
    # Stroke width varies between 4, 5, 6, 7
    sw_choices = [4, 5, 6, 6, 5, 7, 5, 6]
    sw = sw_choices[idx % len(sw_choices)]
    
    canvas = np.full((200, 200), 255, dtype=np.uint8)
    drawer(canvas, 100, 100, sw=sw, seed=idx * 7 + 13)
    return canvas, drawer.__name__, sw

def run_100_suite(max_workers=4, output_json="tests/suite_100_results.json"):
    opts = Options(fresh=True, memory=False, quality="standard", joins=True, decision=True)
    results = []
    t_global0 = time.time()
    
    print(f"=== Starting 100 Ultra-Complex Benchmark Suite ({len(ALL_COMPLEX_DRAWERS)} base drawers, 100 instances) ===", flush=True)
    
    # Pre-generate 100 icons
    icons = []
    for i in range(100):
        img, name, sw = generate_complex_icon(i)
        icons.append((i, img, name, sw))
    
    def _eval(item):
        i, img, name, sw = item
        t0 = time.time()
        try:
            res = process_icon(img, opts, name=f"icon_{i:03d}_{name}")
            dur = time.time() - t0
            met = res.get("metrics") or {}
            iou = float(met.get("iou", 0.0)) * 100.0
            hard = int(met.get("hard", 0))
            m = res.get("model")
            paths = len(m.paths) if m else 0
            nodes = sum(len(p.A) for p in m.paths) if m else 0
            
            status = "PASS"
            if iou < 97.0 or hard > 50:
                status = "WARN"
            if iou < 94.0 or hard > 85:
                status = "FAIL"
                
            entry = {
                "idx": i,
                "drawer": name,
                "sw": sw,
                "iou": round(iou, 2),
                "hard": hard,
                "paths": paths,
                "nodes": nodes,
                "dur": round(dur, 3),
                "status": status,
            }
            print(f"  [#{i:02d}] {name:<26} (sw={sw}): IoU={iou:6.2f}%, hard={hard:3d}, {dur:.2f}s [{status}]", flush=True)
            return entry
        except Exception as e:
            dur = time.time() - t0
            entry = {
                "idx": i,
                "drawer": name,
                "sw": sw,
                "error": str(e),
                "dur": round(dur, 3),
                "status": "CRASH",
            }
            print(f"  [#{i:02d}] {name:<26} (sw={sw}): CRASH {e}", flush=True)
            return entry

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_eval, item): item[0] for item in icons}
        for fut in as_completed(futs):
            results.append(fut.result())
            
    results.sort(key=lambda x: x["idx"])
    total_dur = time.time() - t_global0
    
    valid = [r for r in results if r["status"] != "CRASH"]
    avg_iou = np.mean([r["iou"] for r in valid]) if valid else 0.0
    min_iou = np.min([r["iou"] for r in valid]) if valid else 0.0
    crashes = sum(1 for r in results if r["status"] == "CRASH")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    passes = sum(1 for r in results if r["status"] == "PASS")
    
    summary = {
        "total": len(results),
        "passes": passes,
        "warns": warns,
        "fails": fails,
        "crashes": crashes,
        "avg_iou": round(float(avg_iou), 2),
        "min_iou": round(float(min_iou), 2),
        "total_time": round(total_dur, 2),
        "results": results
    }
    
    with open(output_json, "w") as f:
        json.dump(summary, f, indent=2)
        
    print("\n" + "=" * 80)
    print("100 ULTRA-COMPLEX BENCHMARK SUITE COMPLETE:")
    print(f"Total Icons Tested: {len(results)}")
    print(f"Pass Rate: {passes}/{len(results)} ({passes/len(results)*100:.1f}%)")
    print(f"Average IoU Fidelity: {avg_iou:.2f}%")
    print(f"Minimum IoU Fidelity: {min_iou:.2f}%")
    print(f"Crashes: {crashes} | Fails: {fails} | Warns: {warns}")
    print(f"Total Time: {total_dur:.2f}s ({total_dur/len(results):.3f}s / icon)")
    print("=" * 80 + "\n")
    return summary

if __name__ == "__main__":
    run_100_suite(max_workers=4)
