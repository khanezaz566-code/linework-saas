# Prompt for Antigravity — merge Linework v0.7.0 ("Join engine") into my existing project

Copy everything below the line into Antigravity. The zip is cumulative (v0.4 speed + safety net, v0.5.x Finisher, v0.6.x one set + memory + joints, v0.7.0 Join engine); if my project is older, merge all of it.

---

You are working on my local project **Linework** (Python 3.11+, FastAPI backend, vanilla-JS frontend): raster icon sheet in, clean single-centerline SVG out, via Edit / Output / Doctor engines (`linework/pipeline.py`), a Finisher engine, and now a **Join engine**. I give you `linework-v0.7.0.zip`. **Merge it into my project without losing my local changes, then verify.** Keep the public API; do not rewrite files from scratch.
Note: `linework/joints.py` and the `target=` / `smooth=` parameters of `finisher.fix_end` were already in the working folder when this zip was built (not written in this chat); the zip contains the reviewed and fixed version — keep the zip's version.

## 1. What I need (my concept)
Every joint is first **built carefully**. Then a **Join Checker** inspects every joint; if the answer is *true* the output goes on, if it is *false* **three tools** (named after the Illustrator tools I use: **Shape Builder**, **Line Segment / Arc**, **Pen with Add / Delete / Convert Anchor**) repair the joint, the Checker looks again, and only then a smooth output is produced.

## 2. What is in v0.7.0
* `linework/joints.py`
  * `find_joints(model)` -> `Joint(kind T | L | Y, xy, ends, through, w)`: T = a stroke ends on another stroke, L = two ends meet, Y = 3+ ends (e.g. a ring in two arcs + a spoke; each end must touch one of the OTHER strokes of the cluster).
  * `check_joint(model, J, extra, missing)` -> list of failed checks: `touch` (end exactly on the centreline it joins; tol 0.5 px + 4 % w), `hook` (end bends/jogs away from its own straight stroke, `finisher.end_geometry`), `nub` (cap sticks out, `finisher._protrusion`), `lump` / `hole` (render-only / source-only ink within 2 w of the joint), `nodes` (duplicate anchors).
  * Tools: `tool_unite` (Shape Builder: pieces of one stroke cut by the joint -> one stroke), `tool_pen` (insert anchor on the through-stroke, put the end exactly on it, delete duplicate anchors, 2-stroke corner -> one stroke; `insert_anchor` now refines t), `tool_line(arc=False/True)` (straight / tangent-keeping run to the joint; L joints meet where their own directions intersect), `tool_shape` (re-trace the source inside the joint region and weld).
  * `run_join_engine(model, D, doctor, ink_of, cur, w, time_ok)` -> `(model, ink, soft, report)`; report = `total, clean_first, built, fixed{unite,pen,line,arc,shape}, unresolved[{x,y,reasons}], drift`.
  * A repair is kept only if (a) the joint fails fewer checks, (b) the match to the source does not get worse by more than `max(2, 0.3 %)` and total drift < 0.6 % of the ink area, (c) no new gap / notch / spur. **Never loosen these.**
* `linework/pipeline.py`: `Options.joins=True`; after the Finisher: `run_join_engine(...)` with its own CPU allowance `max(6, 0.2 * budget)`; `metrics.joins = {total, clean_first, built, fixed, unresolved}`.
* `server/app.py`: `job.audit` gets `joints, joints_clean, joints_repaired, joints_review`.
* `linework/lessons.py`: the log line and `summary()` count joints (`/api/lessons`).
* `tools/junction_bench.py` (7 clean-vector icons incl. ECG, jar, pen; prints join stats) and `tools/outline_view.py` (outline view, blue centrelines, red = hook, orange = nub).
* `tests/test_joints.py` (clean joints untouched, hooked off-centre T repaired, split corner with gap repaired, pen tools).

## 3. Merge procedure
1. Branch / backup. 2. Add `linework/joints.py`, `tests/test_joints.py`; 3-way merge `pipeline.py`, `finisher.py`, `lessons.py`, `server/app.py`, `run_sheet.py`, `tools/*`, `CHANGELOG.md`, `README.md`, `__init__.py` (0.7.0).
3. Run every test file (`test_topology, test_rings, test_budget, test_repair, test_finisher, test_lessons, test_joints`): all functions pass.
4. `python tools/junction_bench.py out/jb run` (expect: ECG no unresolved joint; hub fewer unresolved than before; no icon below 97 %).
5. `python run_sheet.py <sheet> standard out/run`: expect the same match as before the merge (±0.2 points), a `JOIN (total, clean, repaired, unresolved)` tuple per icon, and a few percent more time. Reference (12 icons, 8000 px, 2 cores): ~4.8 min, 96.6 %, 410 joints / 30 repaired / 80 for review.
6. UI (please add): show `joints / repaired / for review` in the summary bar from `job.audit`, and draw a red ring at every `metrics.joins.unresolved` (x, y are icon-crop pixels, add the icon offset) so I can look at them.

## 4. Open work, in priority order (please do these next, each with a test)
1. **Junction-aware fitting** (the real fix instead of repairing afterwards): in `skeleton_branches` / `chains` keep the junction node of every branch; fit each branch's last 1.4 w as a straight run along its own direction ending exactly on the node / on the through-stroke; in `opt.refine` give endpoints that belong to one joint ONE shared variable so a joint can never come apart while the optimiser runs.
2. **Unresolved `touch` joints** (most of the 80): look at 10 of them with `tools/outline_view.py`; if the source really has the end 1-3 px off the other centreline the check is too strict (relax `tol`), otherwise add a tool step that moves the whole END ANCHOR + handle (not only the anchor) and re-fits the last segment.
3. **Arc-aware `unite`**: `collinear_pairs` only joins straight continuations; add a version that unites two arcs lying on the same circle (ring in two arcs).
4. **`lump` / `hole` at spool-like icons** (many parallel strokes meeting a bar): try `tool_shape` with a smaller box or `refine_region`.
5. Send me the marked PNG + source crop for any joint that is still wrong; I add it to the bench.

## 5. Rules
* Every edit is verified against the source by a re-render; never improve a score by changing the comparison.
* CPU-time budgets only (no wall-clock decisions). Memory (`lessons`) may only raise the floor of a result.
* Report back: files changed, test output, per-icon `JOIN` tuples and match before/after, bench output, and any deviation.
