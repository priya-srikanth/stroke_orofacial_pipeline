# Classification: 20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb

Companion to `docs/phase-7/notebook-structure-jaw.md`. Produced during Phase
7 sub-phase 7.0b for the dead-code classification requirement in CLAUDE.md
§"Phase plan requirements." Same format as
`docs/phase-7/classification-tongue.md`.

Source: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
(434 MB, 45 cells: 25 code, 20 markdown).

## Labels

Per CLAUDE.md:

* **Production** — the cell's output feeds a downstream module or one of
  Priya's final analysis outputs. These are the cells the new repo ports.
* **Exploratory** — data inspection, debugging, one-off troubleshooting,
  plot-only cells, and commented-out historical code. Not ported as a
  unit; specific utilities inside may be lifted selectively.
* **Deprecated** — an older version superseded by another cell later in
  the same notebook or by another canonical notebook.
* **Ambiguous** — preview not sufficient to resolve; full source pulled
  into `outputs/jaw_dump_prod.txt` for a second pass. Every Ambiguous
  entry below has since been resolved.

For every **Production** cell, port-surface extraction records:
**algorithm (1 sentence) → inputs → outputs → sub-phase owner → port
approach**.

## Summary

| Label        | Code cells | Indices                                                             |
|--------------|------------|---------------------------------------------------------------------|
| Production   | 6          | 13, 15, 16, 18, 22, 43                                              |
| Exploratory  | 15         | 1, 3, 5, 7, 9, 11, 14, 20, 24, 26, 28, 30, 32, 34, 39               |
| Deprecated   | 4          | 37, 41, 42, 44                                                      |
| Ambiguous    | 0          | (all resolved during port-surface extraction pass)                  |

Cross-check against the sub-phase breakdown in
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`:

| Sub-phase | Owned cells (jaw notebook)                            |
|-----------|-------------------------------------------------------|
| 7a        | 22 (jaw v5p3 interpolation — sibling of tongue cell 23) |
| 7b        | — (tongue only)                                       |
| 7c        | — (the jaw-specific per-trial endpoints from the Q6 locked list are NEW surface area; nothing ports from this notebook) |
| 7d        | 43 (jaw X/Y PSD, 10-minute window, broken-Y-axis plot) |
| 7e        | (reward-aligned windowing layer — ships alongside 7b) |
| Data repair (pre-7a, one-off or resolver-level) | 13, 15, 16, 18 |

### Important scope finding for 7c

**This notebook does NOT contain any jaw-specific per-trial kinematic
endpoint computations.** There is no jaw analog of tongue cells 33
(first-lick detector), 36 (peak velocity), 39 (licks-per-trial), 42
(lick-rate / bout ILI), or 50 (tongue angle + phase). The only jaw
Production output in this notebook is the interpolated-trace NPZ from
Cell 22. Cell 43 is a PSD figure.

That means **7c (jaw kinematics endpoints) is NEW surface area** — the
Q6-locked jaw endpoints (jaw opening amplitude, inter-lick jaw
excursion, etc.) must be implemented from scratch in 7c-impl against the
Cell 22 NPZs, not blind-ported from existing code. 7c-design should
therefore be wider-scoped than 7b-design (which was constrained to the
existing tongue-endpoint cells).

Cells 30/32/34 produce per-session binned/unbinned mean-XY figures on
the jaw interpolated trace, but no persisted analytical output — the
per-session mean-XY data would need to be re-derived in 7c-impl from
the Cell 22 NPZs.

The **tongue-jaw mismatch trial classifier** (tongue Cell 53) is
assigned to 7c (resolved 2026-04-21 by Priya, option b). 7c consumes
both Cell 22 (jaw) NPZs and tongue Cell 23 NPZs and emits per-mouse
`df_trials_candidates.csv`. See the tongue classification §Cell 53
port-surface block for the detailed port plan.

---

## Per-cell classification

Code cells only; markdown cells are navigation headers and are noted
inline for context.

### Cell 1 — code (15 lines) — **Exploratory**

Imports (pandas, numpy, matplotlib, os, sys). Not port-worthy as a unit;
the specific imports inform `stroke_orofacial.dlc.*` module preludes but
ship on a per-module basis.

### Cell 3 — code (63 lines) — **Exploratory**

Path folder setup with a hardcoded UNC path
(`r"\\research.files.med.harvard.edu\...\PS55"`). All path logic in the
new repo goes through `PathResolver` + `configs/animals.yaml`. Not
ported.

### Cell 5 — code (47 lines) — **Exploratory**

Per-session label assignment (`animal = "PS55"` hardcoded + regex
extraction of date from `video2_YYYY-MM-DD...` filenames). Superseded
by `configs/animals.yaml` + `stroke_orofacial.animals.load_animals()`.
Not ported.

### Cell 7 — code (107 lines) — **Exploratory**

Parquet cache loader with `CENTER_MODE = "eye_midpoint"` (note: jaw
notebook uses `eye_midpoint`, tongue uses `spout_midpoint` — cohort/
bodypart-specific center mode is a config dimension already covered by
Phase 4.5-lite). Not ported.

### Cell 9 — code (58 lines) — **Exploratory**

"SANITY CHECK: jaw medians per session (DLC h5-loaded)". QC-only.

### Cell 11 — code (117 lines) — **Exploratory**

"Verify temporal alignment mapping against parquet-loaded DLC". QC on
top of Phase 3 alignment canonical. Not ported.

### Cell 13 — code (88 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-video-per-session merge for a hardcoded session
(PS48 cam2 2025-03-14): locate the two split `intermediate_data_frames`
entries by parsing filenames (`re_video`, `re_date`, `re_ts`),
concatenate them in timestamp order, and collapse to a single key.

**Inputs.** `intermediate_data_frames` dict.

**Outputs.** In-place mutation of `intermediate_data_frames`; no
persisted output.

**Sub-phase owner.** Not a sub-phase; same content as tongue Cell 13.
Belongs in the `PathResolver` + parquet-loader layer (Phase 4
extension): when a (mouse, date, cam) resolves to more than one video
file on disk, the loader concatenates on timestamp order.

**Port approach.** Implement once in the loader — tongue Cell 13 and
jaw Cell 13 are the same mechanism applied to different DLC columns.
The PS48 2025-03-14 hardcode drops out; the merge triggers whenever
N > 1 videos share (mouse, date, cam).

### Cell 14 — code (20 lines) — **Exploratory**

"PS48 20250317 Trim parquet based on alignment template." One-off
repair keyed to a hardcoded `KEY` UNC path pointing at a specific PS48
session. Same exploratory pattern as tongue Cell 14. Not ported.

### Cell 15 — code (161 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-session alignment-template merge: concatenate
`sig_wsIdx__idx_cam`, `sig_camIdx__idx_ws`, `sig_camTimes__idx_cam`,
`sig_wsTimes__idx_ws` across two `<date>a.npz` / `<date>b.npz`
templates for the same (mouse, date, cam). Shifts B's indices by
`ws_offset = n_ws_A` / `cam_offset = n_cam_A`, stitches time axes using
`dt_cam` inferred from the median diff and `dt_ws = 1/Fs`, asserts
monotonic time after merge.

**Inputs.** `ALIGN_TEMPLATE_ROOT/<cam>/<mouse>/<date>{a,b}.npz`.

**Outputs.** `np.savez_compressed` to merged alignment NPZ at
`ALIGN_TEMPLATE_ROOT/<cam>/<mouse>/<date>.npz` (overwrites when
`OVERWRITE=True`; rule-4 overwrite is a conscious data-repair op).
Metadata stamped: `merged_from_A`, `merged_from_B`,
`ws_offset_samples`, `cam_offset_frames`.

**Sub-phase owner.** Phase 3 extension (alignment). NOT Phase 7.

**Port approach.** Same surface as tongue Cell 16 — implement once in
`stroke_orofacial.alignment` alongside the existing single-video
writer. The jaw notebook's version has additional sanity checks
(monotonic-time assertions, `dt_cam` inference) that are a strict
superset of the tongue version; use this one as the reference.

### Cell 16 — code (221 lines) — **Production** → data repair (pre-7a)

**Algorithm.** Multi-session `licks_and_rewards` NPZ merge: globs
`<DATE>{a,b}.npz` (or `<DATE>T...npz`) in
`session_processing3/licks_and_rewards/<mouse>/`, concatenates numeric
1D arrays, detects "looks like frame indices" arrays heuristically and
offsets them by `cam_frame_offset_for_B = n_cam_A`, stamps merge
metadata. Heuristic is important: the cell auto-infers `n_cam_A` from
any of `cam_times`, `sig_camTimes__idx_cam`, `t_cam`, `frame_times_s`,
`camTimes`, `n_frames`, `n_cam`, or the largest timeseries-like 1D
array (fallback).

**Inputs.** Two `<DATE>*.npz` files in `session_processing3/licks_and_rewards/<mouse>/`.

**Outputs.** `np.savez_compressed` to merged NPZ at
`session_processing3/licks_and_rewards/<mouse>/<DATE>.npz`.

**Sub-phase owner.** Phase 2 extension, NOT Phase 7.

**Port approach.** Same surface as tongue Cell 17; ship once in a
unified multi-video session-repair module. The heuristics for
"frame-index array" vs "timeseries array" are the only non-trivial bit
and should get a unit test against both real and synthetic sessions.

### Cell 18 — code (177 lines) — **Production** → Phase 3 extension

**Algorithm.** "Build GLOBAL temporal-alignment cache (cam→ws, ws→cam,
Fs, absolute times)." Enumerates `intermediate_data_frames`, parses
(mouse, cam, date_yyyymmdd) from each `_filtered.h5` basename,
collapses duplicates to prefer `_filtered.h5` over `.h5`, loads the
per-session alignment template, sanity-checks frame-count consistency
(`len(sig_wsIdx__idx_cam) == n_frames_parquet`), and writes out a
per-session temporal-alignment cache NPZ under
`TEMP_ALIGN_ROOT/<cam>/<mouse>/<DATE>.npz` with the full `sig_*`
mappings + metadata (mouse, cam, date, source_template,
parquet_key/basename/is_filtered).

**Inputs.** Phase 3 alignment templates + `intermediate_data_frames`.

**Outputs.** `np.savez_compressed` at
`O2_analysis/temporal_alignment/<cam>/<mouse>/<DATE>.npz`.

**Sub-phase owner.** Phase 3 extension (same as tongue Cell 19). NOT
Phase 7.

**Port approach.** Consume existing Phase 3 single-session writer;
wrap with this bulk-enumeration + sanity-check driver in
`stroke_orofacial.alignment.temporal_cache.build_all()`. The
parquet-frame-count sanity check is the distinguishing assertion —
it catches cases where the DLC dataframe was trimmed by Cell 14 but
the alignment template wasn't, or vice versa.

**Note on Phase 7 prerequisite status.** The enriched cache's
absolute-time-per-frame layer is not consumed by any jaw 7a/7c endpoint
cell in this notebook (none exists). The cache content that IS
consumed — the `sig_*` mappings themselves — is already produced by
Phase 3. So Cell 18 is not a strict 7a gate; defer to a standalone
post-Phase-7 Phase 3 extension unless a specific 7c endpoint ends up
needing absolute timestamps.

### Cell 20 — code (185 lines) — **Exploratory**

"Smoke test: temporal alignment cache ↔ lick files ↔ parquet frame
counts." QC-only.

### Cell 22 — code (755 lines) — **Production** → **7a (interpolation)**

**Algorithm.** v5p3 jaw interpolation, 7 named intermediate stages:
raw → xrange → thr → drop → interp → interp_filled → final. Same
skeleton as tongue Cell 23.

1. **xrange** — drop points outside `median(X) ± X_RANGE_PM` (**75 px
   for jaw**, versus 150 px for tongue); X-range source is the
   `lk`-thresholded points.
2. **thr** — drop points where `likelihood < LK_THR` (0.5).
3. **drop** — drop "isolated hi-lk" points (no hi-lk neighbor within
   `±neighbor_ms` / `N_NEIGH` samples). **`N_NEIGH = 3` for jaw**,
   versus 2 for tongue — jaw is a bigger body part and benefits from
   stricter isolation rejection.
4. **interp** — fill NaN gaps up to `max_gap_ms` (**120 ms for jaw**,
   versus 56 ms for tongue — jaw signal is a slower-varying envelope
   and can tolerate longer gaps). PCHIP with ≥ 6 context points/side,
   `REQUIRE_BRACKETED_BY_HILK=True`, `INTERP_FALLBACK="linear"`.
5. **interp_filled** — `_fill_nan_with(arr, X0/Y0)`: long unfilled
   gaps get baseline-substituted.
6. **final** — subtract baseline: `x_final = x - X0`,
   `y_final = y - Y0`.

Baseline computation: in the current run configuration both Y0 and X0
are **forced to hardcoded constants** (`FORCE_Y0 = FORCE_X0 = True`)
with cohort-dependent values documented in-cell:

* PS46-50: `Y0 = 310, X0 = 0`
* PS51, PS54: `Y0 = 290, X0 = 12` (tongue cohort)
* PS55: `Y0 = 290, X0 = 0`

The data-driven percentile path exists but is cold under the current
`FORCE_*=True` configuration. Reward centers are **L/R-flipped at
load time** (`ws_reward_mouseL = lk["Reward_R"]`,
`ws_reward_mouseR = lk["Reward_L"]`) — this is the legacy
wavesurfer→mouse-frame translation and must be routed through the
Phase 6.8 boundary-layer helpers in the port (see the L/R convention
alert on tongue Cell 39).

Source columns: `jaw_x`, `jaw_y`, `jaw_likelihood` — the same function
scaffolding works for any single bodypart by parametrizing the column
names. Shared algorithmic surface with tongue Cell 23 — confirmed by
side-by-side diff: identical `interp_small_gaps_method`, identical
`_build_reward_aligned_pool_mask`, identical `_fill_nan_with`,
identical `compute_session_x_range`, identical control flow through
the 7 stages.

**Inputs.**
* Phase 4 centered parquet (`CENTER_MODE = "centered_eye_midpoint"` for
  jaw, vs `"centered_spout_midpoint"` for tongue — the spout reference
  is correct for tongue but jaw uses the eye midpoint)
* Phase 2 `licks_and_rewards/{mouse}/{date}.npz`
* Phase 3 `alignment_templates/{cam}/{mouse}/{date}.npz`

**Outputs.**
* Per-session NPZ at `O2_analysis/{mouse}/{mouse}_jaw_kinematics/processed_interpolated_data/{CENTER_MODE}/{mouse}_{date}_{cam}_jaw_interp_{VERSION_TAG}.npz`
  with keys: `x_raw, y_raw, lk_raw, x_xrange, y_xrange, x_thr, y_thr,
  x_drop, y_drop, x_interp, y_interp, x_interp_filled, y_interp_filled,
  x_final, y_final, X0, Y0, fps, n_frames, reward_centers_cam,
  baseline_stage, ...` (full key audit due in 7a-design).
* Per-animal summary CSV at
  `{mouse}_jaw_interp_summary_{VERSION_TAG}.csv`.
* Combined summary CSV at
  `jaw_kinematics_processed_interpolated_summary_{VERSION_TAG}_{CENTER_MODE}.csv`.

**Sub-phase owner.** 7a. Same function surface as tongue Cell 23 —
this motivates the 7a-design decision to **implement a
bodypart-parametric interpolation entrypoint** rather than two parallel
modules. Candidate API:
```python
interpolate_bodypart(
    df: pd.DataFrame,
    bodypart: str,           # "tongue" or "jaw" — picks x/y/lk cols
    center_mode: str,        # "centered_spout_midpoint" or "centered_eye_midpoint"
    params: InterpolationParams,
    aln: AlignmentCache,
    rewards: LicksAndRewards,
) -> InterpolationResult
```
with `InterpolationParams` carrying the 18+ knobs (LK_THR, X_RANGE_PM,
baseline_*_lk_thr, baseline_*_percentile, Y0/X0 force+value, etc.).

**Port approach.** Same 7a-design open questions as tongue Cell 23
(7-stage NPZ vs single-final NPZ, PCHIP-as-default, FORCE_Y0/X0 paths,
X-range source `"lk"` vs `"finite"`). Additional jaw-specific
questions:

* The cohort-dependent Y0/X0 values (PS46-50: 310/0; PS51-54: 290/12;
  PS55: 290/0) must move to `configs/animals.yaml` as per-mouse or
  per-cohort `baseline_y0` / `baseline_x0` fields, NOT stay as
  comments in source. This is a strict correctness requirement —
  without it the port will silently use PS55's baselines for all
  mice.
* The jaw uses `CENTER_MODE = "centered_eye_midpoint"` while tongue
  uses `"centered_spout_midpoint"`. Centering choice is
  bodypart-specific; move to a per-bodypart config field
  `dlc_kinematics.<bodypart>.center_mode`.
* The `EXCLUDE_DATES` dict (e.g. `"PS55": ["20250427", "20250428"]`)
  should go into `configs/animals.yaml` as per-mouse
  `exclude_dates:` list, not stay in the notebook.
* `X_RANGE_PM=75` for jaw vs `X_RANGE_PM=150` for tongue is expected
  (jaw has a smaller natural range). Confirms bodypart-parametric
  defaults.
* `neighbor_ms=16, N_NEIGH=3` for jaw vs `neighbor_ms=16, N_NEIGH=2`
  for tongue is a real tuning difference; preserve in
  `configs/defaults.yaml` under `dlc_kinematics.jaw.interpolation:`
  alongside the tongue section.
* `max_gap_ms=120` for jaw vs `56` for tongue is another real tuning
  difference; same config location.

**Parity target.** Legacy NPZs at
`O2_analysis/PS{NN}/PS{NN}_jaw_kinematics/processed_interpolated_data/centered_eye_midpoint/PS{NN}_{YYYYMMDD}_cam2_jaw_interp_v5p3.npz`
for ≥ 3 sessions per animal across the PS46-55 cohort (to catch the
cohort-dependent Y0/X0 baseline correctly). Atol 1e-6 on
`x_final`/`y_final` if no algorithmic change; documented deltas
allowed where the design brief approves.

### Cell 24 — code (303 lines) — **Exploratory**

Fractional-session plotting (downsample a session to e.g. 10% and plot
the X/Y traces). QC/figure only.

### Cell 26 — code (271 lines) — **Exploratory**

Example per-session jaw XY trace plot (`LineCollection`-based
time-colored trajectory). Figure only.

### Cell 28 — code (178 lines) — **Exploratory**

"Plot interpolation steps" — visualizes the intermediate stages from
Cell 22. QC/figure only.

### Cell 30 — code (722 lines) — **Exploratory** (with 8b-relevant binning utilities)

**Algorithm.** Loads Cell 22's interpolation NPZs, computes per-session
mean/SEM of X(t) and Y(t) snippets around reward centers, bins sessions
into rel-day bins (post-stroke), produces per-session 2x2 overlay
figures + across-session overlays + binned overlays. Multi-mouse +
multi-window + multi-bin-size.

**Why Exploratory despite real data layer.** Writes `savefig` only; no
CSV/NPZ output. The per-session mean/SEM it computes on the fly is
plot-glue, not a persisted analytical output. Same pattern as tongue
Cell 31.

**Note for 7c.** The rel-day binning utilities (`_make_rel_day_bins`,
`_assign_to_bin`, `_color_for_bin`, `compute_binned`) are 8b-relevant
— same binning logic as tongue Cell 31. Re-express cleanly in Phase 8b,
not ported from this plotting cell. **However:** if 7c ends up needing
a persisted per-session mean jaw-XY-trajectory NPZ output (not
currently in the Q6 locked list but a natural 7c candidate), the
on-the-fly mean-SEM computation here is a reference implementation.

**Not ported in Phase 7.** Keep as reference.

### Cell 32 — code (736 lines) — **Exploratory**

"Across-session overlays: per-session mean XY lick trajectory
(L-trials vs R-trials)." Multi-mouse + multi-window + multi-bin
configuration, but savefig-only. Same pattern as tongue Cell 45. Not
ported.

### Cell 34 — code (868 lines) — **Exploratory**

Video variant of Cell 32 — binned-mean session mean XY lick trajectory
animations. Savefig + video output (matplotlib animation). Same
pattern as tongue Cells 47/48. Not ported.

### Cell 37 — code (719 lines) — **Deprecated**

Under markdown Cell 35 ("# OLD - Jaw-Tongue session comparisons") and
Cell 36 ("## Jaw and Tongue XY mean ± SEM plot and video"). The "OLD"
header signals these are superseded; Cells 37/39 are kept in the
notebook for historical reference but are explicit scratch. Not ported.

### Cell 39 — code (320 lines) — **Exploratory**

Trial viewer: Jaw vs Tongue per-trial row plots (capless per-trial
scale bars). QC viewer on top of Cells 22 + tongue Cell 23 NPZs.
Under the same "# OLD" section marker as Cell 37. Figure only; not
ported.

### Cell 41 — code (555 lines) — **Deprecated**

**Finding.** This cell is a **near-duplicate of tongue Cell 57**
("trial-level stats + plotting; cluster-robust OLS + MixedLM")
operating on **tongue** endpoint CSVs
(`{mouse}_{cam}_firstlick_pertrial_dydt_v5.csv`,
`{mouse}_{cam}_peakvel_pertrial_first5_dydt_v5.csv`) with
`_mouse_base(mouse) = OUT_ROOT / mouse / f"{mouse}_jaw_kinematics" / f"{CENTER_MODE}"`
— the `_jaw_kinematics` in the path is a bug/leftover: the files being
loaded are tongue endpoints that live under `_tongue_kinematics`, not
`_jaw_kinematics`. This cell likely doesn't even execute correctly as-
is; it appears to be a copy-paste from the tongue notebook kept for
reference.

**Sub-phase owner.** Would be Phase 8b if it were canonical, but the
canonical version is tongue Cell 57. Not ported.

### Cell 42 — code (385 lines) — **Deprecated**

Same relationship to tongue Cell 59 as Cell 41 has to tongue Cell 57 —
near-duplicate of the per-session L/R overlay statistical inference,
operating on tongue endpoint CSVs with the wrong
`_jaw_kinematics` directory path. Not ported; Phase 8b uses tongue
Cell 59 as the canonical reference.

### Cell 43 — code (222 lines) — **Production** → **7d (jaw PSD)**

**Algorithm.** Per-session Power Spectral Density on the `jaw_x` and
`jaw_y` traces (whole-session, first 10 min). Uses
`scipy.signal.welch` (default params) for PSD, broken-Y-axis
semilogy plotting for dynamic-range presentation (break at
`10^-1.5` for jaw X, `10^-0.5` for jaw Y). Generates three 2-column
figures: pre-stroke overlay, post-stroke overlay, combined
pre+post overlay. Pre/post membership is keyed by filename against
`pre_stroke_labels` and `post_stroke_labels` dicts that must be
defined upstream.

**Inputs.** `intermediate_data_frames[file]['jaw_x']` / `['jaw_y']`
traces, first `10 * 60 * fs` frames.

**Outputs (PNG figures only — no CSV/NPZ).**
`{folder_path}/{folder_path.name}_PSD_overlay_10min/psd_plot_pre_stroke.png`,
`psd_plot_post_stroke.png`, `psd_plot_combined.png`.

**Sub-phase owner.** 7d.

**Port approach.** Same as tongue Cells 62/64 — implement
`stroke_orofacial.dlc.face_dynamics.compute_psd(trace, fs)` returning
`(frequencies, power)` plus a separate plot function. **Persist the
PSD `(frequencies, power)` arrays to an NPZ per bodypart per session**
— the legacy cell persists only PNGs, same gap as tongue 62/64.

**Sampling-rate bug to flag.** The cell ends with `fs = 150` and
then calls `overlay_psd_plots(..., fs=150, ...)`. The rest of the
notebook (including Cell 22's interpolation and Cell 3's config)
uses `fs = 250`. The correct jaw camera rate is 250 Hz (same as
tongue); using 150 Hz in the PSD call produces incorrect frequency
axes (scaled by 150/250 = 0.6). **The port must use `fs = 250`** and
drop the `fs = 150` literal. Confirm with Priya during 7d-design
whether this was intentional (e.g. a downsampled pre-filtered trace)
or a bug — my strong read is that it's a bug.

**L/R plotting asymmetry.** The legacy cell uses `pre_stroke_labels`
and `post_stroke_labels` as filename-keyed dicts defined upstream by
hardcoded labels. Port should drive pre/post partitioning from
`stroke_date` in `configs/animals.yaml` + the session date, not from
manually-maintained label dicts.

### Cell 44 — code (0 lines) — **Deprecated** (empty trailing cell)

---

## Hardcoded constants to promote to `configs/defaults.yaml`

Consolidated from the Production cells above. New section:
`dlc_kinematics.jaw:` (parallel to the `dlc_kinematics.tongue:` section
added from the tongue classification).

| Constant                                | Current value (jaw)     | Source cell | Destination                              |
|-----------------------------------------|-------------------------|-------------|------------------------------------------|
| FPS                                     | 250.0                   | 22          | `dlc_kinematics.common.fps`              |
| LK_THR                                  | 0.5                     | 22          | `dlc_kinematics.jaw.interpolation.lk_thr`|
| X_RANGE_MODE                            | "median_pm"             | 22          | `dlc_kinematics.jaw.interpolation.x_range_mode` |
| X_RANGE_PM                              | **75.0** (tongue: 150)  | 22          | `dlc_kinematics.jaw.interpolation.x_range_pm`|
| X_RANGE_FIXED                           | (-150.0, 150.0)         | 22          | `dlc_kinematics.jaw.interpolation.x_range_fixed` |
| X_RANGE_MEDIAN_SOURCE                   | "lk"                    | 22          | `dlc_kinematics.jaw.interpolation.x_range_median_source` |
| neighbor_ms                             | 16.0                    | 22          | `dlc_kinematics.jaw.interpolation.isolated_hi_lk_neighbor_ms` |
| N_NEIGH                                 | **3** (tongue: 2)       | 22          | `dlc_kinematics.jaw.interpolation.isolated_hi_lk_n_neigh` |
| DO_INTERP                               | True                    | 22          | `dlc_kinematics.jaw.interpolation.enable`|
| max_gap_ms                              | **120.0** (tongue: 56)  | 22          | `dlc_kinematics.jaw.interpolation.max_gap_ms`|
| REQUIRE_BRACKETED_BY_HILK               | True                    | 22          | `dlc_kinematics.jaw.interpolation.require_bracketed_by_hi_lk` |
| INTERP_METHOD                           | "pchip"                 | 22          | `dlc_kinematics.jaw.interpolation.method`|
| INTERP_N_SIDE                           | 6                       | 22          | `dlc_kinematics.jaw.interpolation.n_context_each_side` |
| INTERP_MIN_TOTAL_CONTEXT                | 6                       | 22          | `dlc_kinematics.jaw.interpolation.min_total_context` |
| INTERP_FALLBACK                         | "linear"                | 22          | `dlc_kinematics.jaw.interpolation.fallback_method` |
| BASELINE_POST_WIN_MS                    | (0, 5000.0)             | 22          | `dlc_kinematics.jaw.interpolation.baseline_post_win_ms` |
| BASELINE_SOURCE_STAGE                   | "drop"                  | 22          | `dlc_kinematics.jaw.interpolation.baseline_source_stage` |
| BASELINE_REQUIRE_FINITE_X               | True                    | 22          | `dlc_kinematics.jaw.interpolation.baseline_require_finite_x` |
| FORCE_Y0                                | True                    | 22          | `dlc_kinematics.jaw.interpolation.y0_force` |
| Y0_FORCED_VALUE                         | cohort-dep. (PS46-50: 310; PS51-55: 290) | 22 | **`animals.yaml` per-mouse or per-cohort `jaw_baseline_y0`** (NOT defaults.yaml — this is mouse-specific) |
| BASELINE_Y_LK_THR                       | **0.8** (tongue: 0.7)   | 22          | `dlc_kinematics.jaw.interpolation.baseline_y_lk_thr` |
| BASELINE_Y0_PERCENTILE                  | 1.0                     | 22          | `dlc_kinematics.jaw.interpolation.baseline_y0_percentile` |
| FORCE_X0                                | True                    | 22          | `dlc_kinematics.jaw.interpolation.x0_force` |
| X0_FORCED_VALUE                         | cohort-dep. (PS46-50: 0; PS51/54: 12; PS55: 0) | 22 | **`animals.yaml` per-mouse `jaw_baseline_x0`** |
| BASELINE_X_LK_THR                       | **0.8** (tongue: 0.4)   | 22          | `dlc_kinematics.jaw.interpolation.baseline_x_lk_thr` |
| BASELINE_X0_FROM_Y_PERCENTILE           | **5** (tongue: 25.0)    | 22          | `dlc_kinematics.jaw.interpolation.baseline_x0_from_y_percentile` |
| CENTER_MODE                             | "centered_eye_midpoint" (tongue: "centered_spout_midpoint") | 22 | `dlc_kinematics.jaw.center_mode` |
| VERSION_TAG                             | "v5p3"                  | 22          | stamped into output NPZ (not a knob)     |
| CAM                                     | "cam2"                  | 22          | `dlc_kinematics.common.default_cam`      |
| EXCLUDE_DATES                           | `{"PS55": ["20250427", "20250428"]}` | 22 | **`animals.yaml` per-mouse `exclude_dates:` list** (NOT defaults.yaml — this is mouse-specific) |
| PSD frames_to_use                       | `10 * 60 * fs` (10 min) | 43          | `dlc_kinematics.psd.window_seconds: 600` |
| PSD break_val_x                         | `10^-1.5`               | 43          | `dlc_kinematics.psd.jaw_x_break_power`   |
| PSD break_val_y                         | `10^-0.5`               | 43          | `dlc_kinematics.psd.jaw_y_break_power`   |
| PSD fs (buggy literal, should be 250)   | 150 (bug)               | 43          | use `dlc_kinematics.common.fps` in port  |

**Bodyparts that share config with this section.** The interpolation
sub-schema is bodypart-parametric; the clean form in `defaults.yaml`
is:

```yaml
dlc_kinematics:
  common:
    fps: 250.0
    default_cam: cam2
  interpolation_template: &interp_template
    # shared knobs (interp method, isolated-hi-lk detector, etc.)
    lk_thr: 0.5
    method: pchip
    n_context_each_side: 6
    min_total_context: 6
    fallback_method: linear
    baseline_post_win_ms: [0.0, 5000.0]
    baseline_source_stage: drop
    baseline_require_finite_x: true
  tongue:
    <<: *interp_template
    center_mode: centered_spout_midpoint
    interpolation:
      <<: *interp_template
      x_range_pm: 150.0
      isolated_hi_lk_n_neigh: 2
      max_gap_ms: 56.0
      baseline_y_lk_thr: 0.7
      baseline_x_lk_thr: 0.4
      baseline_x0_from_y_percentile: 25.0
  jaw:
    <<: *interp_template
    center_mode: centered_eye_midpoint
    interpolation:
      <<: *interp_template
      x_range_pm: 75.0
      isolated_hi_lk_n_neigh: 3
      max_gap_ms: 120.0
      baseline_y_lk_thr: 0.8
      baseline_x_lk_thr: 0.8
      baseline_x0_from_y_percentile: 5
```

— this is sketch-level; 7a-design will finalize.

---

## Next

Next Cowork turn: classification of the whiskers notebook
(`old_code/20251111_DLC_analysis_whiskers.ipynb`, 67 cells) under
`docs/phase-7/classification-whiskers.md`, same format. Whiskers is
the largest non-tongue notebook and will likely reveal more
Production surface area than jaw did (per Q6 whisker-specific
endpoints include mean whisking amplitude, whisking asymmetry, and
per-whisker setpoint/retraction traces).
