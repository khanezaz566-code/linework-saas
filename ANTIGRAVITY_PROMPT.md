# Prompt for Antigravity — merge Linework v0.6.2 ("one set + memory + careful joints + clean joints") into my existing project

Copy everything below the line into Antigravity. This zip is cumulative (v0.4.0 speed + safety net, v0.5.x Finisher engine, hi-res sheets, stubs). If an older version is in my project, merge all of it; section 3 lists every file.

---

You are working on my local project **Linework** (Python 3.11+, FastAPI backend, vanilla-JS frontend): raster icon sheet in, clean single-centerline SVG out, via Edit / Output / Doctor engines orchestrated by `linework/pipeline.py`, plus a last Finisher engine. I am giving you `linework-v0.6.2.zip`. **Merge it into my project without losing my local changes, then verify.** Do not rewrite files from scratch; keep the public API.

## 1. What I need
1. **The whole icon set must be top-notch, first icon to last.** In a 12-icon set the last icons come out visibly worse (wobbly round shapes, nubs). Round shapes must be truly round, and the icons must look like one set (same stroke weight).
2. **The SaaS must remember its mistakes.** When I run a new icon set, the problems it produced before must not come back; it should know which problems keep occurring.

## 2. What is in v0.6.0
* `linework/finisher.py`: new passes `arcs` (open path that is one circular arc -> exact arc, `arc_fit`, `arc_paths`), `circles` (closed near-circle -> exact circle via `edit.circle(robust=True)`), `caps` (stubs that cross another stroke and poke through: `_protrusion`, `cap_hits`, `best_end_move`), `hairline`, `straighten`, `join`; `finish(..., set_w=None, skip=())`; `width_plan(..., anchor=None)`. Every fix is verified by re-render (arcs/circles get a tolerance of 1 % of the mismatch because "round" is a design goal).
* `linework/setlevel.py` (NEW): `harmonize_widths(models, crops)` clusters widths over the whole set and snaps each icon (verified per icon), `weak_icons(mets)`, `better(old, new)`.
* `linework/lessons.py` (NEW): memory in `data/lessons` (`LINEWORK_MEMORY=0` off, `LINEWORK_DATA` to move): best-so-far per icon (never return worse than the stored best; same version = instant re-use), trace-setting winners per stroke width, `log.jsonl` defect census, `skip_kinds()` (Finisher passes tried >= 150 times with < 1 % success are skipped), `summary()`, `python -m linework.lessons`.
* `linework/pipeline.py`: `Options.memory/fresh/set_stroke`; `process_icon` = memory wrapper -> `_process_icon_scaled` (hi-res normalisation) -> `_process_icon`; trace candidates ordered by `LS.trace_order`, winner recorded; `second_pass_options(opts)`; Finisher called with `skip=`.
* `server/app.py`: `_store_icon`, `_set_pass` (weak icons get a second pass through the pool, then `harmonize_widths`; result in `job["set_pass"]`), `GET /api/lessons`.
* `run_sheet.py`: prints `SECOND PASS ...` and `SET widths ...`; sets `LINEWORK_MEMORY=0` by default for benchmarking.
* Tests: `tests/test_lessons.py` (+ arcs, stub tests in `test_finisher.py`); every test file sets `LINEWORK_MEMORY=0` first.

## 2e. Added in v0.6.1 — joints (lumps / extra ink where two lines meet)
Seen in the UI: star tips with a fat dot, spokes meeting a hub as a polygon-like blob, thin dark wedges next to a bar, a dark blob inside a knot loop — in every case there is MORE ink at a joint than in the source.
* `finisher.excess_ends(model, ink, D)`: path ends with render-only ink around them; pass `tips` pulls the end back (0.5/0.9/1.4 w, best by mismatch, verified).
* `finisher.corner_pairs` / `merge_corners`: two strokes that merely end at the same point (two overlapping round caps) -> one stroke with a corner node; pass `corners`.
* `attempt()` now checks topology only after the match check passes (big speed-up).
* `tools/junction_bench.py <outdir> [tag]`: clean-vector junction test bench (the drawing is the source). Run it before and after your merge; expect spool ~97.7 %, star/hub/knot ~98 %, no blue blob > 3 px.
* If lumps are still visible in my real sheets after the merge: for each, report `metrics.finisher.sites` entries near it (x, y are icon-crop pixels) and the source crop; most likely cause is a path that is correct as a centerline but too wide there (consider a per-path local width fit) or a 3-way junction whose three ends do not meet in one point (add a `junction_snap` that moves all ends to their common intersection).

## 2f. Added in v0.6.2 — clean joints (the reference is the Illustrator outline screenshot: the branch's centreline ends exactly ON the other stroke's centreline, the main stroke runs through unbroken)
Defects seen in outline view: (a) a small hook / curl / jog at the end of a branch where it meets another stroke (pen icon, jar neck), (b) pointed peaks (ECG) that end in a blob, (c) pieces of one straight line that do not line up across a crossing (crib mattress line).
* `finisher.end_geometry / end_hooks / fix_end` + pass `ends`: replace the last 1.4 w of a stroke that is straight before it with a straight run along its own direction ending on the joined centreline. `move_end` handles several segments.
* `collinear_pairs` / `join_pairs` use the direction outside the hook zone, require the same line (lateral offset < 0.6 w), cut hooked ends, and run after `ends`.
* `tools/outline_view.py result.svg out.png 1.0` draws exactly the outline view of the screenshots and marks hooks (red) and nubs (orange); use it on my real results to find joints that are still not clean, then send me the marked PNG + source crop.
* Acceptance: on my 12-icon sheet, `python tools/outline_view.py` should list far fewer `hook` lines than before the merge (reference: 36 -> 29 on the baby sheet, more on my sets); match must not drop > 0.2 points.
* Open: peaks / valleys of polylines (ECG) — check whether the blob is a round join of a corner anchor (correct) or two overlapping caps (`corners` pass should merge those); and 3-way junctions whose three ends do not meet at one point (add a `junction_snap`).

## 3. Merge procedure
1. Branch/backup. 2. Add the new files (`finisher.py`, `setlevel.py`, `lessons.py`, tests); 3-way merge `pipeline.py`, `server/app.py`, `run_sheet.py`, `model.py` (`Model.from_svg`), `CHANGELOG.md`, `README.md`, `__init__.py` (version 0.6.0). Keep my own edits. Add `data/` to `.gitignore`.
3. `python tests/test_*.py` style: every test function must pass (`test_topology, test_rings, test_budget, test_repair, test_finisher, test_lessons`).
4. `python run_sheet.py <sheet> standard out/run` and compare with `Options(finish=False)`: match must not fall > 0.2 points; every icon `duplicates 0`, `gaps 0`. Reference (2 cores, 12-icon baby sheet 8000 px): ~4.4 min, 96.6 % at full resolution, one icon second pass, width classes unified.
5. Run the server on a sheet twice: the second run must be instant ("Re-used the stored result") and `GET /api/lessons` must show per-pass found/fixed counts.
6. UI (optional): show `job.set_pass` (weak icons re-run, widths unified) in the summary bar and the `/api/lessons` table in a small "What keeps going wrong" panel.

## 4. Rules
* Never remove verification of an edit by re-render; never improve a score by changing the comparison.
* Memory may only ever *raise* the floor of a result; do not cache across different presets (the key includes the preset).
* Results must not depend on wall clock or load (CPU-time budgets stay).

## 5. Still open (report back if you see it)
* Wobbly circles/arcs that the verifier rejects (about half in my tests): inspect `metrics.finisher.sites` where `kind` is `arcs`/`circles` and `fixed` is false; if the source circle is really round, loosen the tolerance for that icon; if not, the rejection is correct.
* Hairpin tips at folded outlines (thumb overlap) and coil bars (spring): next passes are a mitred acute tip and re-fitting short parallel bars as equally spaced straight bars.
* Please send me the SVG + source for any icon where a lump, a kink or a missing piece is still visible; I add it to the test set.

When finished, report: files changed, test output, per-icon metrics and total time for my sheet before/after, `/api/lessons` output, and any deviation.
