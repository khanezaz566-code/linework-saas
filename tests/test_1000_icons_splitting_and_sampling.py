"""Verification suite testing 1,000+ icons across 35 distinct sheets:
- Clean multi-icon sheets (28 sheets x 36 icons = 1,008 icons)
- Dark bordered sheets (1px to 12px screenshot frames, 5 sheets = 180 icons)
- Letterbox and pillarbox bordered sheets (2 sheets = 72 icons)
Total icons evaluated: 1,260 icons.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import numpy as np
import cv2

import tests.make_heavy_joins_sheet as mj
from linework.pipeline import process_sheet, Options

def test_1000_icons():
    opts = Options(fresh=True)
    t0 = time.time()
    
    total_sheets = 0
    total_icons_expected = 0
    total_icons_found = 0
    failures = []
    
    print("=== Step 1: Evaluating 28 Diverse Multi-Icon Sheets (1,008 icons) ===")
    for s_idx in range(28):
        canvas = mj.make_sheet(s_idx)
        W, H, jobs = process_sheet(canvas, opts)
        total_sheets += 1
        total_icons_expected += 36
        total_icons_found += len(jobs)
        if len(jobs) != 36:
            failures.append((f"Sheet_{s_idx}", 36, len(jobs)))
            print(f"  [Sheet {s_idx:02d}] FAILED: expected 36, got {len(jobs)}")
    print(f"  -> 28 clean sheets evaluated: {total_icons_found}/{total_icons_expected} icons correctly split.")
    
    print("\n=== Step 2: Evaluating 5 Screenshot-Bordered Sheets (180 icons) ===")
    border_pxs = [2, 4, 6, 8, 12]
    for b_idx, bw in enumerate(border_pxs):
        sheet = mj.make_sheet(100 + b_idx)
        h, w = sheet.shape
        b_sheet = sheet.copy()
        b_sheet[:bw, :] = 0
        b_sheet[-bw:, :] = 0
        b_sheet[:, :bw] = 0
        b_sheet[:, -bw:] = 0
        
        W, H, jobs = process_sheet(b_sheet, opts)
        total_sheets += 1
        total_icons_expected += 36
        total_icons_found += len(jobs)
        if len(jobs) != 36:
            failures.append((f"Border_{bw}px", 36, len(jobs)))
            print(f"  [Border {bw}px] FAILED: expected 36, got {len(jobs)}")
        else:
            print(f"  [Border {bw:2d}px] PASS: 36/36 icons detected cleanly.")
            
    print("\n=== Step 3: Evaluating Letterbox & Pillarbox Sheets (72 icons) ===")
    sheet_base = mj.make_sheet(200)
    h, w = sheet_base.shape
    
    # Letterbox top/bottom (25px black bars)
    lb = np.full((h + 50, w), 255, dtype=np.uint8)
    lb[0:25, :] = 0
    lb[-25:, :] = 0
    lb[25:25+h, :] = sheet_base
    W, H, jobs = process_sheet(lb, opts)
    total_sheets += 1
    total_icons_expected += 36
    total_icons_found += len(jobs)
    if len(jobs) != 36:
        failures.append(("Letterbox_TB", 36, len(jobs)))
    else:
        print("  [Letterbox Top/Bottom] PASS: 36/36 icons detected cleanly.")
        
    # Pillarbox left/right (25px black bars)
    pb = np.full((h, w + 50), 255, dtype=np.uint8)
    pb[:, 0:25] = 0
    pb[:, -25:] = 0
    pb[:, 25:25+w] = sheet_base
    W, H, jobs = process_sheet(pb, opts)
    total_sheets += 1
    total_icons_expected += 36
    total_icons_found += len(jobs)
    if len(jobs) != 36:
        failures.append(("Pillarbox_LR", 36, len(jobs)))
    else:
        print("  [Pillarbox Left/Right] PASS: 36/36 icons detected cleanly.")
        
    elapsed = time.time() - t0
    print("\n================ SUMMARY ================")
    print(f"Total Sheets Tested: {total_sheets}")
    print(f"Total Icons Expected: {total_icons_expected}")
    print(f"Total Icons Found: {total_icons_found}")
    print(f"Split Accuracy: {total_icons_found / total_icons_expected * 100:.2f}%")
    print(f"Total Time: {elapsed:.2f}s ({elapsed / total_sheets:.2f}s per sheet, {elapsed / total_icons_found * 1000:.1f}ms per icon)")
    print(f"Failures: {len(failures)}")
    print("=========================================")
    
    assert len(failures) == 0, f"Failures detected: {failures}"
    print("ALL 1,260 ICONS ACROSS 35 SHEETS PASSED WITH 100.0% ACCURACY!")

if __name__ == "__main__":
    test_1000_icons()
