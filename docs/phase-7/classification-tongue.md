# Classification: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb

Companion to `docs/phase-7/notebook-structure-tongue.md`. Produced during Phase
7 sub-phase 7.0b for the dead-code classification requirement in CLAUDE.md
§"Phase plan requirements."

Source: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
(404 MB, 90 cells: 50 code, 40 markdown).

## Labels

Per CLAUDE.md:

* **Production** — the cell's output feeds a downstream module or one of
  Priya's final analysis outputs. These are the cells the new repo ports.
* **Exploratory** — data inspection, debugging, one-off troubleshooting,
  plot-only cells, and commented-out historical code. Not ported as a
  unit; specific utilities inside may be lifted selectively.
* **Deprecated** — an older version superseded by another cell later in
  the same notebook or by another canonical notebook.
* **Ambiguous** — the 5-line preview was not enough to resolve, and the
  full source was pulled into `/tmp/tongue_dump_prod.txt` for a second
  pass. Every Ambiguous entry below has since been resolved; none remain
  blocking.

For every **Production** cell, port-surface extraction records: **algorithm
(1 sentence) → inputs → outputs → sub-phase owner → port approach**.

## Summary

| Label        | Code cells | Indices                                                                                          |
|--------------|------------|--------------------------------------------------------------------------------------------------|
| Production   | 13         | 13, 16, 17, 19, 23, 33, 36, 39, 42, 50, 62, 64, 53 (scope-flagged)                               |
| Exploratory  | 32         | 1, 3, 5, 7, 9, 11, 14, 15, 21, 25, 27, 29, 31, 34, 37, 40, 43, 45, 47, 48, 55, 58, 66, 70, 72, 74, 77, 79, 81, 83, 84, 86 |
| Deprecated   | 3          | 67, 88, 89                                                                                       |
| Out-of-scope | 2          | 57, 59 (Production, but Phase 8b territory — not ported in Phase 7)                              |
| Ambiguous    | 0          | (all resolved during port-surface extraction pass)                                               |

Cross-check against the sub-phase breakdown in
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`:

| Sub-phase | Owned cells (tongue notebook)                  |
|-----------|------------------------------------------------|
| 7a        | 23 (v5p3 interpolation)                        |
| 7b        | 33, 36, 39, 42, 50 (+53 pending scope call)    |
| 7c        | — (whisker + jaw + nose not covered here)      |
| 7d        | 62, 64 (PSD / spectrogram)                     |
| 7e        | (ships as the reward-aligned windowing layer)  |
| Data repair (pre-7a, one-off or resolver-level) | 13, 16, 17, 19 |
| Phase 8b (out-of-Phase-7 scope) | 57, 59                          |

## One scope question before 7b opens — RESOLVED

**Cell 53 — tongue-jaw mismatch trial classifier.** Not in the locked Q6
endpoint list, but it is a first-class analytical output in the canonical
tongue notebook (emits `df_trials_candidates` CSV per mouse).

**Decision (2026-04-21, Priya): option (b) — port in 7c.** The
cross-bodypart coupling sits naturally in the jaw-kinematics module;
7c consumes both Cell 22 (jaw) NPZs and tongue Cell 23 NPZs and emits
`df_trials_candidates.csv`. See the §Cell 53 port-surface block below
for the detailed port plan. 7b ordering is unchanged — 7b ships the
tongue-only endpoint list first; 7c picks up the cross-bodypart
classifier after 7b's tongue NPZs are available.

---

## Per-cell classification

Code cells only; markdown cells are navigation headers and are noted
inline for context.

### Cell 1 — code (15 lines) — **Exploratory**

Imports (pandas, numpy, matplotlib, os, sys). Not port-worthy as a unit;
the specific imports inform `stroke_orofacial.dlc.*` module preludes but
ship on a per-module basis.

### Cell 3 — code (63 lines) — **Exploratory**

Path folder setup. All path logic in the new repo goes through
`PathResolver` (Phase 6.7) + `configs/animals.yaml`; hardcoded UNC paths
like `r"\\research.files.med.harvard.edu\..."` in this cell are exactly
the kind of thing the `PathResolver` was built to replace. Not ported.

### Cell 5 — code (47 lines) — **Exploratory**

Per-session custom label assignment. Superseded by
`configs/animals.yaml` + `stroke_orofacial.animals.load_animals()`. Not
ported.

### Cell 7 — code (107 lines) — **Exploratory**

Parquet cache loader. Already covered by Phase 4 (centered-parquet
writer) + Phase 4.5-lite (`centered_spout_midpoint`/`centered_eye_midpoint`
consumers). Not ported.

### Cell 9 — code (58 lines) — **Exploratory**

Sanity check ("SANITY CHECK: tongue medians per session (DLC h5-loaded)").
QC-only; does not feed a downstream output.

### Cell 11 — code (117 lines) — **Exploratory**

Verification of temporal-alignment mapping against parquet-loaded DLC.
QC; Phase 3 already owns the alignment canonical.

### Cell 13 — code (88 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-video-per-session merge: when one behavioral session
was split across multiple `video2_*` acquisitions (hardcoded example:
PS48 cam2 2025-03-14), concatenate the parquet-loaded DLC dataframes in
timestamp order and replace the two entries with one merged entry.
**Inputs.** `intermediate_data_frames` dict (keyed by UNC path to the
filtered H5 source).
**Outputs.** Mutates `intermediate_data_frames` in-place — no persisted
output from this cell itself; the merged dataframe is what downstream
cells consume.
**Sub-phase owner.** Not a sub-phase per se; should land in the
`PathResolver` + parquet loader layer (Phase 4 extension) as a "multi-
video session" concept: when a (mouse, date, cam) resolves to more than
one video file on disk, the loader merges on timestamp order.
**Port approach.** Re-implement inside the parquet loader's discovery
helper. The timestamp-parse regexes (`re_video`, `re_date`, `re_ts`) are
lift-and-adapt candidates. The PS48 2025-03-14 hardcode goes away — the
merge triggers whenever N > 1 videos share (mouse, date, cam).

### Cell 14 — code (23 lines) — **Exploratory**

"If misaligned, trim parquet based on alignment template." One-off
repair specific to an anomalous session (the KEY literal pointing at
PS48 is commented out — looks like a scratch buffer for a specific
debugging run). Not a general-purpose operation; shouldn't port.

### Cell 15 — code (51 lines) — **Exploratory**

"Trim alignment template to match DLC dataframe length" with a hardcoded
PS55 2025-05-02 KEY. Same one-off repair pattern as Cell 14. Not ported.

### Cell 16 — code (161 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-session alignment-template merge: concatenate
`cam_to_ws`/`ws_to_cam` frame-to-sample index maps across two alignment
NPZs that belong to the same (mouse, date, cam) but got stored
separately.
**Inputs.** `ALIGN_TEMPLATE_ROOT/<cam>/<mouse>/<date>.npz` × N.
**Outputs.** `np.savez_compressed` to a merged alignment NPZ at the same
`<mouse>/<date>.npz` path (overwrites, CLAUDE.md rule 4 applies —
re-emit is a conscious data-repair op, not a routine overwrite).
**Sub-phase owner.** Phase 3 extension (alignment). Not Phase 7.
**Port approach.** Implement as a helper in
`stroke_orofacial.alignment` alongside the existing single-video-per-
session writer; tests should cover both the single-video and merged-
video paths. Strongly recommend deferring this to a post-Phase-7 gap fix
unless a specific session in the current animal cohort is blocked by it
— ask Priya to confirm which sessions (if any) need this path.

### Cell 17 — code (221 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-session `licks_and_rewards` NPZ merge. Same
multi-video pattern as Cell 16 but for Phase 2 outputs: concatenates the
reward/lick timing arrays.
**Inputs.** Phase 2 `licks_and_rewards/<mouse>/<date>.npz` × N.
**Outputs.** `np.savez_compressed` to merged NPZ at the canonical
single-session path.
**Sub-phase owner.** Phase 2 extension, NOT Phase 7.
**Port approach.** Implement alongside Cell 16's alignment merger in a
unified multi-video session-repair module. If a current-cohort session
is affected, this becomes a pre-7a gate; otherwise it can slip behind
Phase 7. Same ask to Priya as Cell 16.

### Cell 19 — code (177 lines) — **Production** → Phase 3 extension

**Algorithm.** "Build GLOBAL temporal-alignment cache (cam→ws, ws→cam,
Fs, absolute times)." Constructs a session-level temporal-alignment
dictionary unifying per-frame camera timestamps, the wavesurfer sample
indices, the derived Fs, and absolute datetime for each frame.
**Inputs.** Phase 3 alignment template NPZs + wavesurfer `.h5` (for
sample-rate) + per-frame camera timestamp CSVs.
**Outputs.** `np.savez_compressed` at
`O2_analysis/.../<mouse>/<date>.npz` (cache).
**Sub-phase owner.** Phase 3 extension (NOT Phase 7). The existing
`stroke_orofacial.alignment.*` writers produce the per-session
cam↔ws mapping; this cell wraps them with an absolute-time enrichment
layer.
**Port approach.** Consume the existing Phase 3 outputs and add the
absolute-time-per-frame computation as a thin enrichment helper in
`stroke_orofacial.alignment.temporal_cache`. Blocked on whether any of
Phase 7's endpoint cells actually consume the enriched cache — if they
only use the frame-level cam↔ws mapping (which Phase 3 already
provides), Cell 19's enrichment is not a Phase 7 prerequisite.
Recommend: audit during 7a-design whether the enriched cache is
consumed downstream, and if not, defer to a standalone post-Phase-7 fix.

### Cell 21 — code (185 lines) — **Exploratory**

"Smoke test: temporal alignment cache ↔ lick files ↔ parquet frame
counts." QC-only.

### Cell 23 — code (763 lines) — **Production** → **7a (interpolation)**

**Algorithm.** v5p3 tongue interpolation, 7 named intermediate stages:
raw → xrange → thr → drop → interp → interp_filled → final.

1. **xrange** — drop points outside `median(X) ± X_RANGE_PM` (150 px
   default); X-range source is the `lk`-thresholded points.
2. **thr** — drop points where `likelihood < LK_THR` (default 0.5).
3. **drop** — drop "isolated hi-lk" points (no hi-lk neighbor within
   `±neighbor_ms` / `N_NEIGH` samples) — these are likely DLC false
   positives.
4. **interp** — fill NaN gaps up to `max_gap_ms` (56 ms default) with
   PCHIP interpolation using ≥ `INTERP_N_SIDE` context points each side.
   `REQUIRE_BRACKETED_BY_HILK=True` means gaps are only filled when the
   surrounding context is from hi-lk samples.
5. **interp_filled** — `_fill_nan_with(arr, X0/Y0)`: long unfilled gaps
   get baseline-substituted.
6. **final** — subtract baseline: `x_final = x - X0`, `y_final = y - Y0`.

Baseline computation (stages 5 + 6): in the current run configuration
both Y0 and X0 are **forced to hardcoded constants** (`Y0_FORCED_VALUE
= -110.0`, `X0_FORCED_VALUE = 0.0`; `FORCE_Y0 = FORCE_X0 = True`). The
data-driven percentile-based estimation path is cold.

**Inputs.**
* Phase 4 centered parquet (`CENTER_MODE = "centered_spout_midpoint"`)
* Phase 2 `licks_and_rewards/{mouse}/{date}.npz`
* Phase 3 `alignment_templates/{cam}/{mouse}/{date}.npz`

**Outputs.**
* Per-session NPZ at `O2_analysis/{mouse}/{mouse}_tongue_kinematics/processed_interpolated_data/{CENTER_MODE}/{mouse}_{date}_{cam}_tongue_interp_{VERSION_TAG}.npz`
  with keys: `x_raw, y_raw, lk_raw, x_xrange, y_xrange, x_thr, y_thr,
  x_drop, y_drop, x_interp, y_interp, x_interp_filled, y_interp_filled,
  x_final, y_final, X0, Y0, fps, n_frames, reward_centers_cam,
  baseline_stage, ...` (full key audit due in 7a-design).
* Per-animal summary CSV at
  `{mouse}_tongue_interp_summary_{VERSION_TAG}.csv` +
  `tongue_kinematics_processed_interpolated_summary_{VERSION_TAG}_{CENTER_MODE}.csv`.

**Sub-phase owner.** 7a (and the single largest sub-phase; this cell is
75% of the 7a scope).

**Port approach.** **7a-design brief must review and decide on improvements
before 7a-impl — this is the key non-blind-port call from the 2026-04-21
scope discussion.** Specific open questions:

* Whether the 7-stage intermediate-array output is worth keeping (vs. a
  single `(x_final, y_final)` output plus a single QC bundle). The
  stages are useful for debugging but inflate NPZ size.
* Whether the PCHIP-vs-linear toggle should stay a config knob or
  default to PCHIP with no fallback (`INTERP_METHOD = "pchip"` in
  practice).
* Whether the `FORCE_Y0`/`FORCE_X0` paths stay first-class (in which
  case we drop the unused data-driven percentile code) or whether the
  data-driven baseline path is worth preserving as an option.
* Whether X-range source should move from `"lk"` to `"finite"` (current
  default `"lk"` has a bootstrap dependency on the thresholding that
  happens in the next stage).

Parity target: the legacy NPZs at
`O2_analysis/PS{NN}/PS{NN}_tongue_kinematics/processed_interpolated_data/centered_spout_midpoint/PS{NN}_{YYYYMMDD}_cam2_tongue_interp_v5p3.npz`
for ≥ 3 sessions per animal. Atol 1e-6 on `x_final`/`y_final` if no
algorithmic change; documented deltas allowed where the design brief
approves.

### Cell 25 — code (303 lines) — **Exploratory**

Fractional-session plotting (downsample a session to e.g. 10% and plot
the X/Y traces). QC/figure only; not port-worthy.

### Cell 27 — code (271 lines) — **Exploratory**

Example per-session XY trace plot (`LineCollection`-based time-colored
trajectory). Figure only.

### Cell 29 — code (179 lines) — **Exploratory**

"Plot interpolation steps" — visualizes the intermediate stages from
Cell 23. QC/figure only.

### Cell 31 — code (722 lines) — **Exploratory** (with 8b-relevant binning utilities)

**Algorithm.** Loads Cell 23's interpolation NPZs, computes per-session
mean/SEM of X(t) and Y(t) snippets around reward centers, bins sessions
into rel-day bins (post-stroke), and produces overlay figures.

**Why Exploratory despite real data layer.** Writes `savefig` only; no
CSV/NPZ output. The per-session mean/SEM it computes on the fly is a
plot-glue convenience, not a persisted analytical output. The rel-day
binning (`compute_binned`, `_make_rel_day_bins`, `_assign_to_bin`) is
8b-relevant — the same binning logic will be needed for longitudinal
recovery curves — but should be re-expressed cleanly in Phase 8b, not
ported from this plotting cell.

**Not ported in Phase 7.** Keep as reference.

### Cell 33 — code (795 lines) — **Production** → **7b (first-lick metrics)**

**Algorithm.** Per-trial sequential detection of lick1 and lick2 peaks
using the dY/dt method: within `DETECT_WIN_MS = (70, 2000)` ms
post-reward, find the first rise (slope ≥ `SLOPE_THR_PX_PER_S = 250`
px/s) that sustains for ≥ `RISE_MIN_MS = 16` ms, turnover, and fall for
≥ `FALL_MIN_MS = 16` ms; require peak Y amplitude ≥ `MIN_PEAK_Y_ABS = 20`
px; then search after `PEAK_PAD_MS = 52` ms for lick2. `STRICT_NO_FALLBACK
= True` → any step failure returns NaN for that trial.

Per-session aggregates: mean ± SEM of (peak Y, peak X, time-to-peak)
across trials, split by L vs R reward.

**Inputs.** Cell 23 interpolation NPZs
(`USE_SRC = "final"` → uses the baseline-subtracted `x_final`/`y_final`).

**Outputs (CSV).**
* Per-trial: `{mouse}_{cam}_lick1lick2_pertrial_{INTERP_VERSION}.csv`
* Per-session mean±SEM: `{mouse}_{cam}_lick1lick2_persession_meanSEM_{INTERP_VERSION}.csv`
  (written into BOTH `lick_metrics/firstlick_metrics/` and
  `lick_metrics/secondlick_metrics/` dirs — same file, two parents).

**Sub-phase owner.** 7b.

**Port approach.** This is the shared first-lick detection scaffolding
that the monolithic 7b PR carries. Every tongue endpoint in the locked
Q6 list (first-lick amplitude, time-to-first-lick, peak X/Y, angle at
first lick, velocity) depends on this detector. Implement as
`stroke_orofacial.dlc.tongue_kinematics.detect_lick_peaks_dydt(trace,
reward_centers, fps, **params)` returning a per-trial record array;
endpoint functions consume the record array.

Hardcoded constants to promote to `configs/defaults.yaml` under a new
`dlc_kinematics.first_lick_detector:` section:
`slope_thr_px_per_s: 250.0`, `rise_min_ms: 16.0`, `fall_min_ms: 16.0`,
`min_peak_y_abs: 20.0`, `peak_pad_ms: 52.0`, `detect_win_ms: [70, 2000]`,
`strict_no_fallback: true`, `min_detected_trials_to_plot: 10`.

Skip the dual-write to firstlick/secondlick dirs in the port — emit one
canonical location per the figure-type-first output layout.

### Cell 34 — code (314 lines) — **Exploratory**

"Trial viewer: plot selected reward-aligned trials (v5) with detected
lick1 + lick2 dots." QC viewer on top of Cell 33's detector. Not ported.

### Cell 36 — code (1020 lines) — **Production** → **7b (peak velocity)**

**Algorithm.** Same skeleton as Cell 33 (multi-animal loop, dY/dt
detection, per-session mean±SEM) but the metric is peak velocity of
each of the first N licks. Parameters are re-declared in-cell; peak
velocity is defined as `max(|dy/dt|)` within each lick's detected
peak window.

**Inputs.** Cell 23 NPZs.

**Outputs (CSV + NPZ).**
* Per-trial CSV
* Per-session CSV
* Per-animal NPZ cache (`np.savez_compressed` at line 3870 — stacks trial
  peak-velocity arrays for downstream re-use)

**Sub-phase owner.** 7b.

**Port approach.** Share the detector from Cell 33; add a
`peak_velocity_first_n_licks` endpoint function. The `N` knob in the
legacy cell (first 5 licks) should be a config default; the Q6 scope
locks to the first lick as primary and "peak velocity over time
trial-aligned" as secondary — we emit both per-lick-index peak
velocities and the trial-aligned velocity trace.

### Cell 37 — code (408 lines) — **Exploratory**

Trial viewer with peak-velocity dots. QC; not ported.

### Cell 39 — code (1144 lines) — **Production** → **7b (licks per trial per side)**

**Algorithm.** Counts all dY/dt-detected lick peaks within a reward-
aligned window (0–8000 ms default per the Q6 locked scope) and
classifies each detected peak as L vs R by comparing peak-time X to
`X_LEFT_THR_PX`/`X_RIGHT_THR_PX` thresholds (DLC-visual side assignment,
NOT contact-based). Per-trial count, per-session mean±SEM.

**Inputs.** Cell 23 NPZs.

**Outputs (CSV + NPZ).**
* Per-trial CSV, per-session CSV, per-animal NPZ cache.

**Sub-phase owner.** 7b.

**Port approach.** Same detector-share pattern. The `X_LEFT_THR_PX`/
`X_RIGHT_THR_PX` constants need a configs/defaults.yaml entry and a
7a-design clarification: these are pixel thresholds in the
centered-spout-midpoint frame, so they're approximately ±|spout offset|.

**L/R convention alert.** This endpoint emits side-labeled counts. Per
task #17, the new writer emits L/R in **mouse** frame (with
`wavesurfer_sides_match_mouse_sides` + `side_convention_version`
scalars stamped in the output). The legacy CSV is wavesurfer-frame; the
port must translate at emit time via the Phase 6.8 boundary-layer
helpers.

### Cell 40 — code (378 lines) — **Exploratory**

"Trial viewer: reward-aligned trials with ALL detected lick-peak dots
(dy/dt detector)." QC viewer; not ported.

### Cell 42 — code (827 lines) — **Production** → **7b (lick rate / bout ILI)**

**Algorithm.** Reward-aligned licking summaries using within-bout ILI
rate. Computes two per-trial time series binned over the reward-aligned
window:

* `active_frac` = fraction of trials with ≥1 bout-ILI sample in bin
* `p_lick` = fraction of trials with ≥1 detected lick peak in bin

Per-session and binned (rel-day) traces.

**Inputs.** Cell 23 NPZs.

**Outputs (CSV).**
* Per-session traces CSV
* Binned traces CSV

No NPZ cache.

**Sub-phase owner.** 7b.

**Port approach.** Implement as `lick_rate_active_frac()` and
`lick_rate_p_lick()` endpoint functions sharing the detector with
Cells 33/36/39. The bout-ILI logic is new surface area — needs a
dedicated unit test in 7b.

### Cell 43 — code (314 lines) — **Deprecated** (near-duplicate of Cell 34)

Trial viewer duplicate of Cell 34 (same docstring preamble, same detector
logic). The notebook has two copies; only one needs to exist. Not ported.

### Cell 45 — code (672 lines) — **Exploratory**

Per-session mean XY lick trajectory (L vs R) across-session overlay
plots with multiple peri-reward windows. Savefig only. The mean-XY-
trajectory data layer is valuable but is computed on the fly from
Cell 23 NPZs for the plot; the canonical per-session mean XY trajectory
should be a separate 7b endpoint that persists to CSV/NPZ, which this
cell does not do.

**Note.** The Q6-locked scope does NOT currently include a canonical
"per-session mean XY trajectory" endpoint; traces are assumed to come
from a cross-session aggregation in Phase 8b. Confirm during 7b-impl
whether to add a per-session mean-XY-trajectory NPZ emit as part of 7b
or defer it entirely to 8b.

### Cell 47 — code (762 lines) — **Exploratory**

"BINNED-MEAN session mean XY lick trajectory (R-left, L-right)" video
overlay. Figure/animation only.

### Cell 48 — code (805 lines) — **Exploratory**

"WITH FRAME TIMESTAMPS" variant of Cell 47. Figure/animation only.

### Cell 50 — code (1592 lines) — **Production** → **7b (tongue angle + phase)**

**Algorithm.** "Exploratory tongue angle / lick-phase analysis"
(inline-header misnomer — the cell writes canonical per-session CSVs,
not exploratory output). Computes:

* Tongue angle at first lick's peak (atan2 of X,Y deviations from
  baseline).
* Tongue angle during full lick cycle (phase-wrapped trace over each
  detected bout).
* Per-lick phase angle time series.

**Inputs.** Cell 23 NPZs + Cell 33 detector (first-lick peak times).

**Outputs (CSV).**
* `{mouse}_{date}_{cam}_anglePhase_meta.csv`
* `{mouse}_{date}_{cam}_anglePhase_bouts.csv`
* `{mouse}_{date}_{cam}_anglePhase_phaseRows.csv`
* (and an in-between CSV via `to_csv(..., errors="ignore")` — audit in
  port).

**Sub-phase owner.** 7b (angle at first lick = locked Q6 core; angle
during lick cycle = locked Q6 core).

**Port approach.** Implement as `tongue_angle_at_first_lick()` +
`tongue_angle_during_lick_cycle()` in
`stroke_orofacial.dlc.tongue_kinematics`. The phase-wrapping math is
self-contained; the bouts/phaseRows CSVs need schema documentation in
7b-impl. Large cell (1592 lines) but most of that is plotting glue;
the actual angle math is likely < 200 lines.

### Cell 53 — code (605 lines) — **Production** — assigned to **7c**

**Algorithm.** "Candidate trial classifier: few/no tongue licks + jaw
movement." Flags trials where tongue-detector output reports 0–N detected
licks but the jaw DLC trace shows Y-movement above a threshold — i.e.
trials where the mouse moved its jaw but didn't extend its tongue.

**Inputs.** Cell 23 tongue NPZ + the analogous jaw interpolated NPZ from
the canonical jaw notebook (20260416 Cell 22).

**Outputs.** Per-mouse `df_trials_candidates.csv`.

**Sub-phase owner — 7c (jaw-kinematics module).** Resolved 2026-04-21
(Priya, option b). The cross-bodypart coupling sits naturally in the
jaw module; tongue endpoints in 7b don't consume jaw data anywhere else,
so the cleaner layering is: 7b ships tongue-only endpoints including
the Cell 23 tongue NPZ, 7c ships jaw endpoints including the Cell 22
jaw NPZ, and 7c additionally consumes 7b's tongue Cell 23 output to
emit the mismatch classifier. Dep order is 7b → 7c — no reshuffle
needed.

**Port approach.** New function
`classify_tongue_jaw_mismatch_trials()` in
`stroke_orofacial.dlc.jaw_kinematics` (or a thin sibling module
`tongue_jaw_joint.py` that imports from both `tongue_kinematics` and
`jaw_kinematics`). Accepts the per-trial tongue-detector output array
and per-trial jaw Y-displacement array, and a threshold manifest
(`max_licks`, `jaw_y_thresh`). Emits a per-trial boolean
`is_mismatch_candidate` and writes `df_trials_candidates.csv` per
mouse under `stroke_orofacial_pipeline_outputs/dlc_analysis/7c/`.
The 605-line cell is mostly plotting + interactive scrubbing; the
classifier logic itself is likely < 80 lines.

### Cell 55 — code (1295 lines) — **Exploratory**

"Multi-mouse trial viewer + within-session grids + cross-session
overlays" for the Cell 53 candidate trials. QC viewer on top of Cell 53
output; not ported.

### Cell 57 — code (791 lines) — **Production** (out of Phase 7 scope) → **Phase 8b**

**Algorithm.** Baseline-normalized, epoch-based, side-specific,
per-animal + pooled statistics on the Cell 33 / Cell 39 / Cell 42
per-trial and per-session outputs. Emits longitudinal summary CSVs.

**Inputs.** The 7b per-trial/per-session CSVs from Cells 33, 39, 42.

**Outputs (CSV).** `df_all.to_csv(p)` + two
`df_results.to_csv(...)` (full and epoch-masked variants).

**Sub-phase owner.** **Phase 8b** (longitudinal recovery curves + cross-
session aggregations). NOT ported in Phase 7.

**Port approach.** Defer. Phase 7 emits per-session trial-aligned
outputs; Phase 8b consumes them and re-implements these aggregations
cleanly against the new 7b schema.

### Cell 58 — code (248 lines) — **Exploratory**

USER KNOBS block + OUT_ROOT for the statistics layer (Cell 57).
Config-only cell; absorbed into configs/defaults.yaml in the 8b port.

### Cell 59 — code (685 lines) — **Production** (out of Phase 7 scope) → **Phase 8b**

**Algorithm.** Per-SESSION inference + L/R overlay figures (baseline-
normalized within mouse × side using epoch="baseline"). Emits per-
session inference result CSV + overlay figures.

**Sub-phase owner.** **Phase 8b** or downstream visualization layer.
Not ported in Phase 7.

### Cell 62 — code (179 lines) — **Production** → **7d (tongue X PSD)**

**Algorithm.** Per-session Power Spectral Density + spectrogram on the
`tongue_x` trace (whole-session, not trial-aligned). Uses `scipy.signal.welch`
for PSD, `scipy.signal.spectrogram` for the spectrogram.

**Inputs.** Raw or filtered tongue X trace (audit in 7d which stage).

**Outputs (PNG figures only — no CSV/NPZ).**
`{save_folder}/tongue_x_PSD_{label}.png`, `tongue_x_spect_{label}.png`,
`tongue_x_combined_{label}.png`.

**Sub-phase owner.** 7d.

**Port approach.** Implement as
`stroke_orofacial.dlc.face_dynamics.compute_psd(trace, fs)` returning
`(frequencies, power)` plus a separate plot function. Persist the PSD
`(frequencies, power)` arrays to an NPZ — the legacy cell persists
only PNGs, which is a gap to close in the port.

### Cell 64 — code (136 lines) — **Production** → **7d (tongue Y PSD)**

Same as Cell 62 but for `tongue_y`. Same port approach.

### Cells 66, 70, 72, 74, 77, 79, 81, 83, 84, 86, 88 — **Exploratory** / **Deprecated**

Plot-variant cells for PSD visualization: broken-Y-axis, combined X+Y,
overlay across days, log-axis variants, pre-vs-post-stroke overlays,
colormap testing. All savefig-only; none emit analytical output. The
canonical PSD compute is in Cells 62 + 64; these are figure experiments.

**Cell 67 (2L)** — commented-out `print` statement. **Deprecated.**

**Cell 88 (68L)** — "Testing different colormaps." Explicit scratch.
**Deprecated.**

**Cell 83 (149L)** — Hardcoded list of pre-stroke vs post-stroke video
filenames for PS46. Superseded by `animals.yaml` + `stroke_date`.
**Exploratory** (no output; feeds the PSD pre-vs-post overlay cells).

### Cell 89 — code (0 lines) — **Deprecated** (empty trailing cell)

---

## Hardcoded constants to promote to `configs/defaults.yaml`

Consolidated from the Production cells above. New section:
`dlc_kinematics.tongue:`.

| Constant                                | Current value                   | Source cell | Destination                              |
|-----------------------------------------|---------------------------------|-------------|------------------------------------------|
| FPS                                     | 250.0                           | 23          | `dlc_kinematics.common.fps`              |
| LK_THR                                  | 0.5                             | 23          | `dlc_kinematics.interpolation.lk_thr`    |
| X_RANGE_PM                              | 150.0                           | 23          | `dlc_kinematics.interpolation.x_range_pm`|
| X_RANGE_MEDIAN_SOURCE                   | "lk"                            | 23          | `dlc_kinematics.interpolation.x_range_median_source` |
| neighbor_ms                             | 16.0                            | 23          | `dlc_kinematics.interpolation.isolated_hi_lk_neighbor_ms` |
| N_NEIGH                                 | 2                               | 23          | `dlc_kinematics.interpolation.isolated_hi_lk_n_neigh` |
| max_gap_ms                              | 56.0                            | 23          | `dlc_kinematics.interpolation.max_gap_ms`|
| INTERP_METHOD                           | "pchip"                         | 23          | `dlc_kinematics.interpolation.method`    |
| INTERP_N_SIDE                           | 6                               | 23          | `dlc_kinematics.interpolation.n_context_each_side` |
| INTERP_MIN_TOTAL_CONTEXT                | 6                               | 23          | `dlc_kinematics.interpolation.min_total_context` |
| BASELINE_POST_WIN_MS                    | (0, 5000.0)                     | 23          | `dlc_kinematics.interpolation.baseline_post_win_ms` |
| FORCE_Y0 / Y0_FORCED_VALUE              | True / -110.0                   | 23          | `dlc_kinematics.interpolation.y0_{force,forced_value}` |
| FORCE_X0 / X0_FORCED_VALUE              | True / 0.0                      | 23          | `dlc_kinematics.interpolation.x0_{force,forced_value}` |
| BASELINE_Y_LK_THR                       | 0.7                             | 23          | `dlc_kinematics.interpolation.baseline_y_lk_thr` |
| BASELINE_Y0_PERCENTILE                  | 1.0                             | 23          | `dlc_kinematics.interpolation.baseline_y0_percentile` |
| BASELINE_X_LK_THR                       | 0.4                             | 23          | `dlc_kinematics.interpolation.baseline_x_lk_thr` |
| BASELINE_X0_FROM_Y_PERCENTILE           | 25.0                            | 23          | `dlc_kinematics.interpolation.baseline_x0_from_y_percentile` |
| VERSION_TAG                             | "v5p3"                          | 23          | stamped into output NPZ (not a knob)     |
| DETECT_WIN_MS                           | (70, 2000)                      | 33, 36, 39  | `dlc_kinematics.first_lick_detector.detect_win_ms` |
| SLOPE_THR_PX_PER_S                      | 250.0                           | 33, 36, 39  | `dlc_kinematics.first_lick_detector.slope_thr_px_per_s` |
| RISE_MIN_MS                             | 16.0                            | 33, 36, 39  | `dlc_kinematics.first_lick_detector.rise_min_ms` |
| FALL_MIN_MS                             | 16.0                            | 33, 36, 39  | `dlc_kinematics.first_lick_detector.fall_min_ms` |
| MIN_PEAK_Y_ABS                          | 20.0                            | 33, 36, 39  | `dlc_kinematics.first_lick_detector.min_peak_y_abs` |
| PEAK_PAD_MS                             | 52.0                            | 33, 36, 39  | `dlc_kinematics.first_lick_detector.peak_pad_ms` |
| STRICT_NO_FALLBACK                      | True                            | 33, 36, 39  | `dlc_kinematics.first_lick_detector.strict_no_fallback` |
| MIN_DETECTED_TRIALS_TO_PLOT             | 10                              | 33, 36, 39  | `dlc_kinematics.first_lick_detector.min_detected_trials_to_plot` |
| PLOT_WIN_MS                             | (-200, 2500)                    | 33, 36, 39  | `dlc_kinematics.common.plot_win_ms`      |
| reward-aligned window (0, 8000) ms      | Q6-locked                       | 39, 42      | `dlc_kinematics.common.reward_window_ms` (already covered by Phase 6 `window_selector`) |
| X_LEFT_THR_PX / X_RIGHT_THR_PX          | (to-be-audited)                 | 39, 40      | `dlc_kinematics.side_classifier.{left,right}_thr_px` |

PSD / spectrogram parameters (welch defaults + spectrogram window/NFFT)
are per-call in Cells 62/64; audit during 7d-impl for any non-default
values.

---

## Next

Cell 53 scope question resolved (2026-04-21, option b → 7c; see
DECISIONS.md entry). All five Phase-7 reference notebooks classified
under `docs/phase-7/`. 7.0b shipped as PR #60 (commit `2f34aad`), tagged
`v7.0b-cell-classification`. Next Phase-7 sub-phase (7a-design brief,
`docs/phase-7/interpolation-strategy.md`) is blocked on the Phase 5/6
`trial_group` translation mini-PR
(`v6.8a-phase-5-6-trial-group-translation`), per task #7 and
`docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7.
