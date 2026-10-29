# Changelog

## 0.8.0 — Structure engine (why small fixes did not show, and the bigger answer)
- Root cause found: the Doctor/Finisher/Join verifier compares the render with the SOURCE pixels. A lump, a wobble or a fused double outline costs only a few pixels of overlap, and when the source itself is wobbly or fused, the render copies it at 99 % match. Local repairs were therefore either "invisible" to the check or rejected as "not an improvement".
- `linework/structure.py`: skeleton of source vs skeleton of render (render-off / source-off / thick / thin sites, severity in stroke widths).
- `linework/structfix.py` (runs after the Join engine, option `structure=True`):
  * intent checks that do not trust the source: **fused** (stroke far wider than the set width -> two parallel strokes), **wobble** (centre line oscillating around its own smooth version -> low-pass smoothed, ends fixed);
  * per structure site: **snap** to the source centre line + smooth, **smooth**, **retrace** of the region, local **width** fix;
  * every candidate kept only if soft match stays inside an explicit allowance, topology does not get worse and the structure score drops.
- `metrics.structure = {before, after, found, fixed, unresolved}`; unresolved sites are meant for UI red rings and for `lessons`.
- Tests: `tests/test_structfix.py` (3). Earlier suites unchanged.
- Known: the structure score is measured against the source, so deliberately smoothing a wobbly source RAISES it; use `fixed`/`unresolved`, not `after`, to judge wobble repairs. Junction-aware fitting (shared node variables) is still open.

## 0.7.0 — Join engine (Join Builder -> Join Checker -> pen / line / arc / shape / unite tools)
New `linework/joints.py`, wired into `process_icon` after the Finisher (`Options.joins=True`, own CPU allowance = 20 % of the icon budget, >= 6 s).
* **Joints** found per icon: `T` (a stroke ends on another), `L` (two ends meet), `Y` (3+ ends, e.g. a ring in two arcs plus a spoke).
* **Join Checker** (per joint, pass/fail with reasons): `touch` (every end exactly on the centreline it joins, tol 0.5 px + 4 % w), `hook`, `nub`, `lump` / `hole` (render-only / source-only ink within 2 w), `nodes` (duplicate anchors).
* **Tools** (named after the editor tools): `unite` (Shape Builder: pieces of one stroke cut by the joint become one), `pen` (Add / Delete anchor: anchor on the through-stroke, end placed exactly on it, duplicate anchors removed, two-stroke corner -> one stroke),
  `line` (Line Segment: straight run to the joint, L joints meet in the intersection of their own directions), `arc` (same, keeps the tangent), `shape` (re-trace the source inside the joint region).
* A repair is kept only when the joint fails fewer checks AND the match to the source does not get worse AND no new gap / notch / spur; joints that still fail are listed in `metrics.joins.unresolved` with x, y and reasons (for a review mark in the UI).
* `insert_anchor` now refines its parameter (was up to ~1 px off). `fix_end(target=, smooth=)` is used by the line / arc tools. Server audit: `joints`, `joints_clean`, `joints_repaired`, `joints_review`. `lessons` log/summary count joints.
Measured, 12-icon baby sheet: 410 joints, 238 clean at first look, 30 repaired, 80 left for review (mostly 'touch' within 1-3 px that the source itself does not support); match 96.6 % unchanged; ~4.8 min on 2 cores.
Synthetic bench (7 clean-vector icons): ECG all 5 joints clean after repair; hub 7 -> 5 unresolved; tests in `tests/test_joints.py`.
Roadmap (not done): junction-aware FITTING (shared node variables inside `opt.refine` so a joint can never drift apart while the optimiser runs, and branches fitted up to a node instead of repaired afterwards).

## 0.6.2 — clean joints, as in the reference screenshot (branch ends ON the other stroke's centreline, no hooks / jogs)
* Finisher pass `ends`: an open stroke that runs straight into its end but bends / jogs in the last ~1.4 stroke widths (the skeleton artefact at junctions) gets that stretch replaced by a straight run along its own
  direction, ending exactly on the centreline of the stroke it joins (free ends: same length as before). `end_geometry`, `end_hooks`, `fix_end`.
* `move_end` can now cut more than one segment (a short last segment is dropped, the remainder is taken off the previous one).
* `join` (strokes cut by a crossing stroke become one) now measures the stroke direction outside the hook zone, requires the other piece to lie on the same line, and cuts hooked ends before joining; it runs after `ends`.
* `tools/outline_view.py result.svg out.png [zoom]`: outline view with blue centrelines, red rings on hooks, orange rings on nubs, plus a text list with positions.
* `tools/junction_bench.py` now has 7 icons (adds ECG, jar neck, pen) and prints the hook count before / after the Finisher.
Measured, baby sheet: hooks 36 -> 29, crib joins accepted 1 -> 4, match unchanged (96.6 %). The synthetic bench has almost no hooks even before the Finisher (clean sources), so the pen / jar / ECG joints of the screenshots come from artefacts of real antialiased sources that I could not reproduce.

## 0.6.1 — careful joints
Finisher passes `tips` and `corners`; `attempt` checks topology only after the match check passes (the slow `find_gaps` was ~45 % of the Finisher).
* `tips`: ends that have render-only ink around them (thick tips, lumps) are pulled back by 0.5 / 0.9 / 1.4 stroke widths, whichever lowers the mismatch most (max 20 ends per icon, verified).
* `corners`: a corner drawn as two strokes with two overlapping round caps (exactly two ends meet, nothing else touches) becomes ONE stroke with a corner node, so the join is drawn once, cleanly.
* `tools/junction_bench.py`: four clean-vector icons (hub+spokes, star+bar, spool, knot) as a junction test bench; result diffs show extra ink (blue) / missing ink (red).
Measured: spool bench 97.41 -> 97.68 %, other bench icons unchanged; baby sheet 96.6 % unchanged (tips accepted 6x, corners 1x); a 12-icon 8000 px sheet now takes ~5.9 min on 2 cores incl. second pass (was ~4.4 min before 0.5.x passes were added).
Not reproduced here: the lumps from the screenshots appear on sources I do not have; the bench shows no lump > 3 px on clean sources.

## 0.6.0 — one set, and a memory
**Round shapes** (Finisher `arcs`, `circles`): an open path that is really one circular arc is rebuilt as an exact arc (<= 90 deg Bezier pieces, ends kept); a closed near-circle becomes an exact circle.
Verified like every Finisher fix, with a slightly larger tolerance (1 % of the mismatch) because "round" is a design goal and AI-drawn source circles are never perfect.
**Set-level consistency** (`linework/setlevel.py`): after all icons are done, stroke widths are clustered over the WHOLE set and each icon is snapped to the shared weight classes (verified per icon against its source);
icons clearly weaker than the rest of the set (below median - 2 points or < 95.5 %, at most 3) get a longer second pass (`pipeline.second_pass_options`) and the better result wins. Done in `run_sheet.py` and in the server (`_set_pass`, `job["set_pass"]`).
**Memory** (`linework/lessons.py`, switch off with `LINEWORK_MEMORY=0`, folder `data/lessons` or `LINEWORK_DATA`):
* best-so-far per source icon: a later run — even after a code update — can never return a result that scores worse than the stored one; same version + same icon = instant re-use (`Options.fresh=True` forces a new run, the floor still applies);
* the trace setting that won most often for a stroke width is tried first next time;
* every icon is logged (match, remaining issues, per Finisher pass found/fixed); passes tried >= 150 times with < 1 % success are skipped; `GET /api/lessons` / `python -m linework.lessons` show what keeps going wrong.
Tests: `tests/test_lessons.py`, arcs test in `tests/test_finisher.py`. All tests set `LINEWORK_MEMORY=0`.
Measured (baby sheet, 12 icons): sheet 96.6 % unchanged; second pass on the weakest icon 94.58 -> 94.72 %; width classes 3; ~4.4 min + ~35 s second pass on 2 cores.
Honest limits: memory is bookkeeping (monotonic results, speed, a defect census), it does not make the optimiser smarter by itself.

## 0.5.3 — overshoot stubs (coil / bar ends that stick out past the stroke they cross)
`caps` pass now also catches *stubs*: an open path whose end has crossed another stroke's centerline and pokes through its far edge (spring coil bars ending in round nubs on the side rails).
Detection uses the end point and a point 2 stroke widths behind it (opposite sides of the other stroke's centerline). The end is retracted / extended to the position that leaves the least outside,
first as a plain move, then (if the verifier objects) with a weld. If the source really has the stub (verified by re-render) the stub is kept.
Baby sheet: 64 -> 26 protruding caps/stubs, match unchanged (96.6 %). Test: `test_overshoot_stub_is_cut_back_only_if_source_agrees`.

## 0.5.2 — junction nubs ("lumps where one line is joined to another")
Finisher pass `caps`: a round cap that ends inside another stroke but sticks out through its far edge (a small nub / lump at a T- or arc junction) is moved along its own tangent
(retract by cutting the last Bezier with de Casteljau, or extend) to the amount that leaves the least cap outside; each move is verified by re-render like every other Finisher fix.
`Model.from_svg()` reads a Linework SVG back into a model (to inspect any delivered SVG). New helpers: `cap_hits`, `best_end_move`, `move_end`.
Measured on the 12-icon baby sheet: 64 protruding caps -> 28, match unchanged (96.6 % full-res). The rest were rejected by the verifier or have no better position.

## 0.5.1 — high-resolution sheets, three more Finisher passes (found on a real 12-icon baby-items sheet, 8000x4465 px)
* `process_icon` now normalises resolution: a source whose stroke is wider than `Options.max_stroke` (14 px) is shrunk to `norm_stroke` (10 px), processed,
  and the vector is scaled back (`Model.scaled`). The 8000 px sheet did not finish in 10 min before; now 12 icons take ~4 min on 2 cores.
  `metrics.iou` is measured at the working scale (comparable between sheets); `metrics.iou_full` is the stricter full-resolution value.
* Finisher: `hairline` (hair-thin traces of faint JPEG grey are removed), `straighten` (an open path that is really one straight stroke but has extra nodes / bends becomes one line),
  `join` (strokes cut where another stroke crosses them are joined into one, then straightened).
* Measured, baby sheet (working-scale IoU): 95.5-98.3 % per icon, sheet 96.6 % at full resolution; defects removed: stroller axle hairline, crib bar wobble (11 straightened).
* Known: the long diagonal mattress lines of the crib icon are still slightly wavy (cut into pieces at every bar; only 1 join was accepted) — next target.

## 0.5.0 — Finisher engine (the last engine, per-icon inspection)
New `linework/finisher.py`, `Options.finish=True`. After the Edit/Doctor loop and the safety net, each icon is inspected on its own and the
few spots that still look machine-made are fixed: looping/backward handles (redraw), needless nodes (simplify), near-vertical/horizontal
strokes that are off-axis and edges 0.3-1 px apart (exact axis + shared coordinate), strokes of the same weight that differ by a few % in
width (one width per weight class), tiny specks, and remaining mismatch hot spots (harder re-fit, then local re-draw).
Every fix is verified by re-render: kept only if the match does not get worse (tiny cosmetic tolerance, total drift capped), and no new
gap/notch/spur appears. Own CPU allowance (25 % of the icon budget, >= 8 s). Metrics: `finisher = {found, fixed, sites:[{kind,x,y,fixed}]}`.
Measured: home sheet 97.97 % in 136 s (0.4.0: 98.03 %, 121 s) — the small difference is the cosmetic drift the Finisher is allowed.
Tests: `tests/test_finisher.py`.

## 0.4.0 — faster, and a safety net
**Speed (same or better match, ~2-3x less CPU):**
- `trace.py`: `_edges()` vectorised (Python loop -> numpy; verified identical on 300 random batches), `center_of_mass` called once for all junctions.
- `pipeline.py`: the trace setting is chosen from the stroke width (`w_est < 8`, `< 14`, else), and a second/third trace is only tried when the first
  render matches < 93 % (`Options.trace_ok`); before, up to 5 full traces ran for every dense icon.
- `opt.py`: scatter-add with `np.bincount` instead of `np.add.at`, `hypot` instead of `np.linalg.norm` (results identical to 1e-8, ~18 % faster).
- Standard preset: `iters=22, taus=(1.0, 0.5, 0.35)` (same quality as 30 iterations), warm-start rounds stop when a round gains < 0.25 points.
- Measured on a 2-core box, 12-icon sheet: 4 min 23 s (was ~10 min); 10-icon home sheet 2 min (was 6); 12-icon mechanical sheet 5 min 20 s (was 9 min 18 s).
**Safety net (`repair.py`, `Options.repair=True`):** after the loop, big pieces of the source that are missing from the render are traced and added,
and big pieces of the render that are not in the source are removed; each repair is re-rendered and kept only if the mismatch shrinks. Metrics gain `restored` / `stray`.
**Match:** 12-icon industrial sheet 98.96 %, home sheet 98.03 % (was 97.77), mechanical sheet 95.46 % (was 95.50).
Tests: `tests/test_repair.py`.

## 0.3.1 — same quality for every icon in a big set
- **Cause found:** each icon's Edit/Doctor budget was *wall-clock* seconds, and the server ran one worker per CPU core with several
  math threads each. On a busy or many-core machine the icons that ran while the CPU was crowded (the big, complex ones are queued
  first) used up their budget before the optimiser / ring-fit / junction-weld finished, so quality varied with load and queue position.
- **Fix:** the budget is now **CPU time actually spent on that icon** (`time.process_time()`), so results no longer depend on load,
  worker count, or position in the queue; complex icons get a bigger budget (x1 to x3, from total stroke length). A wall-clock
  hang-guard (10x budget) remains only to stop a stuck icon.
- Math libraries are limited to one thread per worker (`OMP/OPENBLAS/MKL_NUM_THREADS=1`, `cv2.setNumThreads(1)`, `threadpoolctl`),
  which removes CPU oversubscription and makes parallel sheets faster.
- Test: `tests/test_budget.py`. Measured: one chain icon alone vs. under 4 busy CPUs -> identical (0.95847, 97 paths, 517 nodes).

## 0.3.0 — complex / dense icons
- **Super-resolution tracing**: thin strokes (< 10 px) are traced at 2-3x resolution (skeleton + curve fit), then scaled back; Edit/Doctor still work at source resolution. Gear-chain / screw / sprocket icons: +8 to +11 match points.
- **Exact rings** (`rings.py`): circles and ellipses are found in the *image* (Hough on the skeleton, least-squares refinement, ink-support test), added as exact closed paths; older broken arcs on top of them are cut back to the ring edge. Every ring is kept only if the re-render is no worse.
- Dense corners (closer than a stroke width) are kept sharp instead of being smoothed away.
- Fixed: the gradient optimiser could drive a stroke width negative (now bounded to 0.5x-2x of its start value).
- Fixed: stale Edit commands waived instead of crashing; icons nested inside another icon's box merged.
- Tests: `tests/test_rings.py`.

## 0.2.0
- New `topology.py`: junction welding, notch/staircase merging, spur trimming (Doctor detects, Edit repairs, every change re-rendered and verified).
- Wobbly near-straight segments are straightened with a width-relative tolerance.
- Fixed: Standard/Precise crash on complex icons (stale Edit commands now waived instead of raising).
- Fixed: icons nested inside another icon's box (cushion X) are no longer split off.
- Doctor target match is now 99.5 %; the loop stops on target, stall or time budget.
- UI summary: "Open gaps" and "Notches".

## 0.1.0
- First release: Edit / Output / Doctor engines, FastAPI backend, minimalist frontend.
