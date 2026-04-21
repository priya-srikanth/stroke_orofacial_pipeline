# Classification: 20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb

Companion to `docs/phase-7/notebook-structure-pixelbin.md`. Produced during
Phase 7 sub-phase 7.0b for the dead-code classification requirement in
CLAUDE.md §"Phase plan requirements." Same format as
`docs/phase-7/classification-tongue.md`,
`docs/phase-7/classification-jaw.md`, and
`docs/phase-7/classification-whiskers.md`.

Source: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`
(349 KB, 26 cells: 14 code, 12 markdown).

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
  into `outputs/pixelbin_dump_prod.txt` for a second pass. Every
  Ambiguous entry below has since been resolved.

For every **Production** cell, port-surface extraction records:
**algorithm (1 sentence) → inputs → outputs → sub-phase owner → port
approach**.

## Scope scoping — this is not a Phase 7 notebook

This notebook is the **Phase 5 pixel-bin spatial-occupancy canonical**,
*not* a Phase 7 DLC kinematics notebook. Its content divides cleanly
across phases already decided by the record:

* Phase 5/6 (descriptive spatial maps) — already ported in part
  (`dlc_spatial/pixel_bins.py`, `heatmaps.py`, `difference_maps.py`) and
  partly scheduled as Phase 5.x mini
  (`plot_all_bodyparts_heatmap`, per DECISIONS.md 2026-04-18 "Phase 5
  all-bodyparts overlay heatmap design").
* Phase 9 (inferential spatial stats) — JS divergence, balanced +
  unbalanced Wasserstein, and OT displacement-field visualization. Per
  DECISIONS.md 2026-04-18 "Phase 5 defers permutation/inferential
  spatial stats to Phase 9," none of the inferential-metrics cells ship
  in Phase 5 or Phase 7. They wait for Phase 9.

**Zero cells in this notebook are Phase-7 port targets.** The
Production cells flagged below all have out-of-Phase-7 owners (Phase
5.x mini or Phase 9); their inclusion in this doc is so the sub-phase
breakdown in the Phase 7 kickoff correctly records "nothing from
pixelbin lands in 7a–7f," not so that 7a–7f picks them up.

The category labels below (Production / Deprecated / Exploratory)
therefore describe the cell's role within *its own* scheduled phase,
not Phase 7 specifically. A cell labeled Production(Phase 5.x) is
Production *for Phase 5.x*; Phase 7 still does not port it.

## Summary

| Label                                    | Code cells | Indices                              |
|------------------------------------------|------------|--------------------------------------|
| Production(Phase 5, already ported)       | 2          | 6, 8                                 |
| Production(Phase 5.x mini, not yet ported)| 3          | 11, 13, 15                           |
| Production(Phase 9, deferred)             | 3          | 19, 21, 25                           |
| Deprecated                                | 2          | 16, 17                               |
| Exploratory                               | 4          | 1, 3, 4, 23                          |
| Ambiguous                                 | 0          | (resolved)                           |

Cross-check against the sub-phase breakdown in
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`:

| Sub-phase | Owned cells (pixelbin notebook)                                 |
|-----------|------------------------------------------------------------------|
| 7a        | —                                                                |
| 7b        | —                                                                |
| 7c        | —                                                                |
| 7d        | — (no PSD content in this notebook; 7d ports from tongue/jaw)    |
| 7e        | —                                                                |
| Data repair (pre-7a) | —                                                     |

**Pixelbin contributes nothing to Phase 7.** Its content was folded
into Phase 5 during the pixel-bin audit (already ported: cells 6, 8)
and into the DECISIONS-scheduled Phase 5.x mini (cells 11, 13, 15) and
Phase 9 (cells 19, 21, 25).

---

## Cell-by-cell classification

### Cell 0 — markdown
Header: `# Import packages`. Not classified.

### Cell 1 — code (29 lines) — Exploratory
Top-of-notebook imports: `os`, `sys`, `pandas`, `numpy`, `matplotlib`,
`scipy.signal.welch/spectrogram`, optional `scicomap`, plus an
`get_afmhot_like()` colormap-fallback helper. The `scipy.signal`
imports and the scicomap helper are inherited from the tongue/whisker
notebook template but **are not used anywhere in this notebook** —
pixelbin is pure 2-D occupancy analysis with no PSD content. No port.

### Cell 2 — markdown
Header: `# Load files and appoint labels`. Not classified.

### Cell 3 — code (63 lines) — Exploratory
DLC file discovery from `folder_path` with optional
`*filtered_5s/86s.{csv|h5}` variants. Hard-coded
`folder_path = "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46"`;
`fs = 250` (consistent with the canonical tongue/jaw notebooks and
Phase 4 acquisition — not the `fs = 150` bug from the whisker
notebook). Superseded by `PathResolver` + `SessionManifest` +
`animals.yaml` discovery in Phase 6.7. No port.

### Cell 4 — code (47 lines) — Exploratory
Builds `{basename: "ANIMAL M/D"}` label map with a
`video2_YYYY-MM-DD` regex. Hard-coded `animal = "PS46"`. Fully
superseded by `SessionManifest` (`animal`, `session_date`,
`session_key`, `display_label`). No port.

### Cell 5 — markdown
Header: `# Load parquet files`. Not classified.

### Cell 6 — code (108 lines) — Production(Phase 5, already ported)
**Algorithm (1 sentence):** Signature-gated parquet-cache loader —
given `CENTER_MODE` and `CENTER_LIK_THR`, computes the expected
MD5-derived 8-char signature, globs
`<basename>.intermediate.<sig>.parquet` files under
`<folder_path>/_dlc_cache_centered_<CENTER_MODE>/`, picks matching /
override / newest files, and populates
`intermediate_data_frames[full_csv_path] -> DataFrame`.

**Inputs:** `folder_path`, `CENTER_MODE ∈ {"nose", "spout_midpoint",
"eye_midpoint"}`, `CENTER_LIK_THR` (default 0.7), optional
`SIGNATURE_OVERRIDE`, `REQUIRE_EXPECTED_SIG`, and
`MAX_FRAMES_PER_VIDEO` cap.

**Outputs:** in-memory `intermediate_data_frames` dict keyed by full
CSV path; no files written.

**Sub-phase owner:** Already owned by Phase 4.5
(`dlc_centering/cache.py`) and consumed via
`PathResolver.centered_parquet_path(mode, lk_thr)` in Phase 5/6. This
loader is the cell-level historical reference that produced the cache
the pipeline now reads.

**Port approach:** Already ported — no action. The notebook-level
loader stays in the notebook for backward-compat but is no longer
canonical. Phase 7 notebooks read parquet via
`stroke_orofacial.io.load_centered_parquet(session_manifest)`.

### Cell 7 — markdown
Header: `## Sanity check, verify centering`. Not classified.

### Cell 8 — code (103 lines) — Production(Phase 5, already ported)
**Algorithm (1 sentence):** Per-session masked-vs-unmasked median
check for the centering anchor — prints unmasked and
likelihood-masked medians for the anchor bodyparts
(`nose` / `L_spout+R_spout` midpoint / `L_eye+R_eye` midpoint,
depending on `CENTER_MODE`), confirming the masked anchor median is
`≈ (0, 0)` within `TOL = 1e-6`.

**Inputs:** `intermediate_data_frames`, `CENTER_MODE`,
`CENTER_LIK_THR`.

**Outputs:** stdout-only per-session report; no files written.

**Sub-phase owner:** Already owned by Phase 4.5
(`dlc_centering/verify.py`) and surfaced in Phase 5 output as a
per-session `centering_check.json` alongside the cached parquet.

**Port approach:** Already ported — no action.

### Cell 9 — markdown
Header: `# Heatmaps`. Not classified.

### Cell 10 — markdown
Header: `## Heatmap by counts vs proportion, by date`. Not classified.

### Cell 11 — code (186 lines) — Production(Phase 5.x mini, not yet ported)
**Algorithm (1 sentence):** Per-session 2-D histogram (`hist2d`, 100
bins, density=True, `LogNorm`) overlaying **9 bodyparts on one axis**
(`nose`, `jaw`, `tongue`, `L_whiskers_{1,2,3}`, `R_whiskers_{1,2,3}`),
each with its own colormap from `PART_CONFIG` and its own stacked
horizontal colorbar on the right.

**Inputs:** `intermediate_data_frames`, per-bodypart likelihood
thresholds (`NOSE_LIKE_THR=0.80`, `JAW_LIKE_THR=0.80`,
`TONGUE_LIKE_THR=0.70`, `WHISKER_LIKE_THR=0.80`), `NBINS = 100`,
optional `APPLY_X_RANGE` + `X_MIN/X_MAX = (−200, 200)`, fixed
`x_limits = (−200, 200)` and `y_limits = (50, 550)`, per-bodypart
colormaps (`gist_ncar`, `gnuplot2`, `jet`, `plasma`, `inferno`,
`viridis`; L/R whiskers share cmaps).

**Outputs:** one PNG per session at
`<folder_path>/<animal>_bodyparts_whisker_heatmap_centered_<CENTER_MODE>/bodyparts_whisker_heatmap_centered_<label>.png`
(200 DPI).

**Sub-phase owner:** Phase 5.x mini
(`plot_all_bodyparts_heatmap(df, config, include_landmarks=False)`),
already scoped in DECISIONS.md 2026-04-18 "Phase 5 all-bodyparts
overlay heatmap design." Out of Phase 7 scope.

**Port approach:** In the future Phase 5.x mini-phase kickoff
(`docs/prompts/phase-5.x-all-bodyparts-heatmap-kickoff.md`, to be
written), add `plot_all_bodyparts_heatmap()` to
`src/stroke_orofacial/dlc_spatial/heatmaps.py` as a thin wrapper that
iterates `config["dlc_spatial"]["bodyparts"]` (nose, jaw, tongue, 6
whiskers), calls the existing per-bodypart `build_histogram()` per
part, and overlays them with per-part cmaps from
`config["dlc_spatial"]["bodyparts"].{bp}.overlay_cmap`. The
multi-bodypart overlay is the **analytical primitive Priya wants
preserved as a QC / cross-bodypart comparison view**; do not drop it.
Not a Phase 7 port. **When this mini ships, the whisker notebook's
cells 14 / 16 / 18 become directly superseded** (they are the
whisker-notebook siblings of this canonical pattern; see
Reconciliation §1 below).

### Cell 12 — markdown
Header: `## Binned heatmaps by counts vs proportion`. Not classified.

### Cell 13 — code (535 lines) — Production(Phase 5.x mini, not yet ported)
**Algorithm (1 sentence):** Session grouping by `rel_day` bins (sweep
over `bin_width_days ∈ {3, 5, 7}` days), per-bin **session-averaged
counts** or **pooled proportion** histogram per bodypart, overlaid
across all 9 bodyparts on one axis with per-part stacked colorbars and
optional global-vmax normalization.

**Inputs:** `intermediate_data_frames`, `stroke_date_str`,
`bin_width_days`, `nbins_xy = (100, 100)`, `hist_mode ∈ {"counts",
"proportion"}`, `NORMALIZE_TO_TOTAL` flag (True → all-frames
denominator, False → filtered-rows denominator),
`USE_FIRST_ALLOWED_DATE` + `first_allowed_date_str`,
per-bodypart likelihood thresholds, `APPLY_X_RANGE + X_MIN/X_MAX`,
hard-coded `x_limits = (−200, 200)`, `y_limits = (50, 550)`,
`LogNorm` / `PowerNorm` / `Normalize` knobs (`NORM_MODE`,
`VMIN_LOG_PROP = 1e-6`, `VMIN_LOG_COUNTS = 10`, `GAMMA = 0.5`,
`vmax_percentile = 99`).

**Outputs:** one PNG per (bin × norm-mode) combination under
`<folder_path>/<animal>_bodyparts_whisker_heatmap_bins/centered_<CENTER_MODE>/<prop_all|prop_filt|counts>/<filter-tag>_bins<W>_nx100_ny100/`
(200 DPI).

Important convention: **rel_day = 0 is mapped to −1** (`return -1 if
delta == 0 else delta`), so the stroke day groups with pre-stroke
sessions. This convention differs from cells 16/17/19 below, which
use `rel_day = 0` unmapped. When this ships in Phase 5.x, the
convention must be reconciled against the Phase 6.7 `rel_day =
(session_date - stroke_date).days` standard used everywhere else in
the pipeline; the legacy `stroke→−1` remap should NOT be ported.

**Sub-phase owner:** Phase 5.x mini
(`plot_all_bodyparts_heatmap_binned()`), same
DECISIONS.md 2026-04-18 scope. Out of Phase 7 scope.

**Port approach:** In the Phase 5.x mini, add
`plot_all_bodyparts_heatmap_binned(manifest_group, config,
bin_width_days)` to `dlc_spatial/heatmaps.py` that takes a list of
SessionManifests (one cohort-mouse), groups by rel_day bin
(`bin_width_days` from config), calls per-bodypart `build_histogram()`
per session and averages/pools per bin, then overlays. Drop the
`stroke→−1` remap (rel_day 0 stays at 0). Keep the `SWEEPS` concept
as a convenience iterator over (`bin_width_days`, `hist_mode`,
`NORMALIZE_TO_TOTAL`) triples. `fixed_vmax`, `vmax_percentile`, and
NORM_MODE choices migrate into `config["dlc_spatial"]["overlay"]`.
Not a Phase 7 port.

### Cell 14 — markdown
Header: `## Subtracted proportion heatmaps`. Not classified.

### Cell 15 — code (715 lines) — Production(Phase 5.x mini, not yet ported)
**Algorithm (1 sentence):** Δ multi-bodypart proportion heatmaps vs a
pre-stroke baseline — pools sessions with `rel_day ≤ 0` into a
`baseline_proportion` histogram per bodypart, then for each post-stroke
`rel_day` bin subtracts the baseline bin-by-bin and renders the Δ
with a diverging cmap (`seismic` / `bwr` / `RdBu_r`), all 9 bodyparts
overlaid on one axis.

**Inputs:** same as cell 13 plus a `diff_cmap` + symmetric vmax
(`vmax_percentile` on `|Δ|`), same `stroke→−1` remap convention.

**Outputs:** one PNG per (post-stroke bin × normalization)
combination under
`<folder_path>/<animal>_bodyparts_whisker_heatmap_diff/centered_<CENTER_MODE>/.../`.

**Sub-phase owner:** Phase 5.x mini
(`plot_all_bodyparts_difference_heatmap_binned()`), same DECISIONS.md
2026-04-18 scope. Phase 5 already has per-bodypart
`difference_maps.compute_difference_map()` +
`plot_difference_map()`; the Phase 5.x mini adds the multi-bodypart
overlay wrapper on top. Out of Phase 7 scope.

**Port approach:** In the Phase 5.x mini, build
`plot_all_bodyparts_difference_heatmap_binned()` as a thin wrapper
that calls `difference_maps.compute_difference_map()` per bodypart
(baseline pooled from manifest-selected pre-stroke sessions,
per-post-stroke-bin histogram built by cell 13's binning helper) and
renders all 9 with a shared diverging cmap and symmetric vmax. Not a
Phase 7 port.

### Cell 16 — code (1278 lines) — Deprecated
Header banner: `# 12/1/25 first date filter` + `# ============== HYBRID
== JS & Wasserstein (multi-normalization, multi-bodypart) ==============`.
Computes Jensen–Shannon divergence + balanced Wasserstein + unbalanced
Wasserstein (with `ot.unbalanced.sinkhorn_unbalanced`) across 6
bodypart groups (`tongue`, `jaw`, `nose`, pooled `whiskers`, pooled
`spouts`, pooled `eyes`) at `TARGET_BIN_SIZE_X/Y = 25 px`,
`UNB_REG = 0.1`, `UNB_REG_M = 1000`, `W_OCC_PENALTY_FACTOR = 20`,
stroke date `2025-04-30` (PS54-55), first-date filter
`2025-03-07`.

**Why Deprecated:** Directly superseded by Cell 19, which carries the
**USE ME Percentile-based ranges** markdown marker (Cell 18). Cells
16 and 17 are mouse-specific hyperparameter branches of the same
analysis (16 targets PS54-55, 17 targets PS51); the canonical,
Priya-marked version is Cell 19, which pools percentile-based
histogram ranges and uses `TARGET_BIN_SIZE = 10 px`, `UNB_REG = 0.02`,
`UNB_REG_M = 10`, `W_OCC_PENALTY_FACTOR = 2` — different enough that
this is a deliberate supersession, not a config-only divergence.

### Cell 17 — code (1391 lines) — Deprecated
Same header comment as Cell 16 but for PS51 (`stroke_date =
2025-04-29`, `TARGET_BIN_SIZE = 10`, `UNB_REG = 0.02`, `UNB_REG_M =
1`, `W_OCC_PENALTY_FACTOR = 2`, first-date filter `None`). Sibling of
Cell 16; same supersession by Cell 19.

### Cell 18 — markdown
Header: `# USE ME Percentile-based ranges`. Not classified. Flags
Cell 19 as canonical.

### Cell 19 — code (1293 lines) — Production(Phase 9, deferred)
**Algorithm (1 sentence):** Multi-metric cohort-wise occupancy
divergence — for each of 6 bodypart groups, builds a
`TARGET_BIN_SIZE = 10 px` stats grid per session with percentile-based
(`PERC_LOW=0.5`, `PERC_HIGH=99.5`, `X/Y_PADDING=30`) histogram
ranges pooled across sessions, pools pre-stroke sessions into a
baseline, then computes for every session **five metrics vs
baseline**: JS divergence (conditional + full), balanced Wasserstein
(conditional + full with
`W_OCC_PENALTY_FACTOR`-based "no-part" bin), and unbalanced Wasserstein
with mass-destroy + mass-create cost decomposition (via
`ot.unbalanced.sinkhorn_unbalanced`, `UNB_REG = 0.02`, `UNB_REG_M =
10`).

**Inputs:** same parquet-loaded `intermediate_data_frames`,
`BODYPART_CONFIG` (6 groups — tongue / jaw / nose / whiskers / spouts
/ eyes; whiskers and spouts and eyes are pooled across left+right),
`TARGET_BIN_SIZE_X/Y = 10`, percentile + padding knobs, `UNB_REG`,
`UNB_REG_M`, `W_OCC_PENALTY_FACTOR = 2`, per-bodypart likelihood
thresholds. No `FIRST_DATE` filter (None).

**Outputs (persisted):** per-bodypart
`<folder_path>/<animal>_<part>_stats/centered_<CENTER_MODE>/`
containing:
* baseline NPZ: per-bodypart pre-stroke-pooled stats grid + baseline
  histograms (`P_pre_cond`, `P_pre_full`, etc.).
* metrics CSV: one row per (rel_day, bodypart), columns
  `{js_cond, js_full, wasserstein_cond, wasserstein_full,
  wasserstein_unbalanced_total, uot_transport_cost,
  uot_mass_destroy, uot_mass_create}`, both raw and z-scored vs the
  pre-stroke distribution.
* per-metric PNGs: 10 figures per bodypart in `<stats_folder>/`
  named `<part>_{metric}_vs_day_sizeOcc_{pre_tag}_{filt_tag}_nx*_ny*<_raw|_Z>.png`.
* summary grids: one grid per (metric × raw/z) at
  `<folder_path>/<animal>_allBodyparts_stats_summary/centered_<CENTER_MODE>/ALLPARTS_{metric}{suffix}_grid_{pre_tag}_bin10x10px.png`.

**Sub-phase owner:** **Phase 9 (deferred)**, per DECISIONS.md
2026-04-18 "Phase 5 defers permutation/inferential spatial stats to
Phase 9." Out of Phase 7 scope.

**Port approach:** Not ported in Phase 5, Phase 6, or Phase 7. In
Phase 9, lift the port surface into a new module
`src/stroke_orofacial/dlc_spatial_stats/` (sibling of `dlc_spatial`)
with:
* `metrics/js.py` — `js_divergence(P, Q)`, plus full/conditional
  variants that take the `P_pre_full` / `P_pre_cond` baselines from
  `pixel_bins.build_baseline_histogram()`.
* `metrics/wasserstein.py` — balanced (`ot.emd2`) + unbalanced
  (`ot.unbalanced.sinkhorn_unbalanced` with decomposition into
  transport + mass-destroy + mass-create) + full-with-occupancy-bin
  variant.
* `metrics/aggregate.py` — per-session metric CSV writer + z-score
  against the pre-stroke metric distribution.
* `plots/metric_vs_day.py` — per-bodypart + summary-grid figures.
* Per-run config comes from `configs/defaults.yaml` under
  `dlc_spatial_stats.pixel_bins` (percentile + padding + bin size +
  UOT hyperparameters + W_occupancy penalty).
* Permutation null: use the Phase 9 permutation framework (see
  DECISIONS.md 2026-04-18) to produce `p_{metric}` alongside each
  metric; do not compute here at port time.

### Cell 20 — markdown
Header: `# USE ME: Plot JS, OT displacement maps`. Not classified.
Flags Cell 21 as canonical.

### Cell 21 — code (652 lines) — Production(Phase 9, deferred)
**Algorithm (1 sentence):** Spatial visualization driver that reads
the per-bodypart baseline NPZ + metrics CSV produced by Cell 19 and,
per bodypart × rel_day, computes the unbalanced OT transport plan to
produce: Δ-occupancy map (SVG), JS contribution map (SVG), UOT
mass-destroy + mass-create maps (SVG), and the UOT displacement field
(arrows showing where mass moved) as both SVG + PNG; finally
assembles a single ALL-BODYPARTS × ALL-DAYS displacement-grid SVG.

**Inputs:** `BODYPART_CONFIG` + `accumulate_hist_part` from Cell 19,
baseline NPZ + metrics CSVs on disk, `UNB_REG = 0.02`, `UNB_REG_M =
10`, `MIN_MASS = 1e-4`, arrow-styling knobs (`ARROW_LW_MIN/MAX`,
`ARROW_ALPHA_MIN/MAX`).

**Outputs (persisted):**
* `<animal>_<part>_stats/centered_<CENTER_MODE>/visualizations/<part>_rel<NNN>_{delta_occupancy|js_contrib|UOT_destroy|UOT_create|UOT_displacement}.{svg|png}`
* `<animal>_allBodyparts_stats_summary/centered_<CENTER_MODE>/<animal>_ALLPARTS_UOTdisplacementField_grid_centered_<CENTER_MODE>.svg`.

**Sub-phase owner:** Phase 9 (visualization layer on top of Cell 19).
Out of Phase 7 scope.

**Port approach:** In Phase 9, ship as
`dlc_spatial_stats/plots/displacement_field.py` that reads the baseline
NPZ + metrics CSV emitted by `metrics/aggregate.py`, recomputes the OT
plan per (session, bodypart), and writes the 5-map set + the
all-parts grid. Arrow-styling knobs move to
`configs/defaults.yaml` under `dlc_spatial_stats.displacement_field`.

### Cell 22 — markdown
Header: `# Eye & spout heatmap checks`. Not classified.

### Cell 23 — code (222 lines) — Exploratory
Per-session 2-D histogram on a 50-bin grid of the pooled
`L_spout + R_spout` distribution (`cool` cmap) and the pooled
`L_eye + R_eye` distribution (`cividis` cmap), saved as
`<animal>_{spout|eye}_heatmap/centered_<CENTER_MODE>/{spouts|eyes}_heatmap_centered_<label>.png`
(200 DPI). Raw counts only (no log norm, no baseline comparison).

**Why Exploratory:** This is a sanity-check that eyes and spouts
behave as expected after centering (eyes ≈ constant position,
spouts ≈ stable anchors). It produces no analytical endpoint and no
downstream consumer. The centering already has a sanity check (Cell
8); this one adds a spatial-distribution view as a secondary
confirmation. If Priya wants a permanent QC artifact, it can ride on
top of the Phase 4.5 `centering_check.json` output, but that's not
required — not ported.

### Cell 24 — markdown
Header: `# Wasserstein conditional OT displacement maps`. Not
classified.

### Cell 25 — code (691 lines) — Production(Phase 9, deferred)
**Algorithm (1 sentence):** Balanced (conditional) Wasserstein
displacement fields — for each (session, bodypart), takes
`P_pre_cond` + `P_sess_cond` conditional distributions from Cell 19's
baseline NPZ + stats grids, runs `ot.sinkhorn` to compute the
balanced transport plan, and renders the displacement arrows (per-day
PNG + SVG) plus an all-bodyparts-×-all-days summary grid SVG.

**Inputs:** `root_path`, `CENTER_MODE`, baseline NPZ + stats-grid
outputs from Cell 19; arrow styling identical to Cell 21 for visual
parity.

**Outputs (persisted):** per (bodypart, rel_day)
`<animal>_<part>_stats/centered_<CENTER_MODE>/visualizations/<part>_rel<NNN>_CONDWASS_displacementField.{svg|png}`;
summary grid
`<animal>_allBodyparts_stats_summary/centered_<CENTER_MODE>/<animal>_ALLPARTS_CONDWASS_displacementField_grid_centered_<CENTER_MODE>.svg`.

**Sub-phase owner:** Phase 9 — the balanced-OT sibling of Cell 21's
unbalanced-OT displacement. Ships alongside Cell 21 in
`dlc_spatial_stats/plots/displacement_field.py`. Out of Phase 7 scope.

**Port approach:** In Phase 9, add a `balanced=True` toggle to
`displacement_field.render()` (or two sibling functions
`render_balanced_displacement()` / `render_unbalanced_displacement()`)
sharing the arrow-styling helpers. Both consume the same baseline
NPZ + metrics CSV.

---

## Hardcoded constants inventory

This notebook contains constants already promoted elsewhere (via
prior classifications) plus a small number of Phase 9 inferential
knobs that will not be promoted in Phase 7. Listed for completeness.

| Constant                              | Cells            | Legacy value                         | New home                                                        |
|---------------------------------------|------------------|--------------------------------------|-----------------------------------------------------------------|
| `fs` (sampling frequency)              | 3                | `250` (✓ correct)                    | Already in `configs/defaults.yaml.dlc_kinematics.fs_hz = 250`   |
| `CENTER_MODE` / `CENTER_LIK_THR`       | 6                | per-run strings / `0.7`              | Already owned by `dlc_centering` config                         |
| `NOSE_LIKE_THR`                        | 11, 13, 15, 16, 17, 19, 23 | `0.80`                    | `dlc_kinematics.nose.lk_thr` (see nose classification — pending) |
| `JAW_LIKE_THR`                         | 11, 13, 15, 16, 17, 19     | `0.80`                    | Already in `dlc_kinematics.jaw.lk_thr`                          |
| `TONGUE_LIKE_THR`                      | 11, 13, 15, 16, 17, 19     | `0.70`                    | Already in `dlc_kinematics.tongue.lk_thr`                       |
| `WHISKER_LIKE_THR`                     | 11, 13, 15, 16, 17, 19     | `0.80`                    | Already in `dlc_kinematics.whiskers.lk_thr` (whisker class.)    |
| `SPOUT_LIKE_THR` / `EYE_LIKE_THR`      | 16, 17, 19, 23             | `0.80` each                | `dlc_kinematics.landmarks.{spout,eye}.lk_thr` (new, Phase 9)    |
| `APPLY_X_RANGE`, `X_MIN/MAX`            | 11, 13, 15, 16, 17, 19, 23 | `True`, `(−200, 200)`      | Already in `dlc_spatial.pixel_bins` hist-range config           |
| Per-bodypart overlay cmaps             | 11, 13           | `gist_ncar / gnuplot2 / jet / plasma / inferno / viridis` | `dlc_spatial.overlay.cmaps.{bp}` (Phase 5.x mini)                |
| Δ diverging cmap                       | 15               | `seismic` / `bwr` / `RdBu_r`          | `dlc_spatial.overlay.diff_cmap` (Phase 5.x mini)                 |
| Heatmap axis limits                    | 11, 13, 15       | `x=(−200,200)`, `y=(50,550)` (manual) | Reuse existing per-`(bodypart, center_mode)` limits in `dlc_spatial.bodyparts.*.per_center_mode.*` — prefer this over the hand-coded fallback |
| Heatmap `NBINS`                        | 11, 23           | `100`, `50`                          | Already in `dlc_spatial.heatmap_nbins = 100` (cell 23's 50 is a QC-only downsample; not promoted) |
| `TARGET_BIN_SIZE_X/Y` (stats grid)     | 16, 17, 19       | `25` (cell 16) / `10` (cells 17, 19) | `dlc_spatial_stats.pixel_bins.target_bin_size = 10` (Phase 9 — canonical from cell 19) |
| Percentile range (`PERC_LOW/HIGH`)     | 19               | `0.5` / `99.5`                       | `dlc_spatial_stats.pixel_bins.{perc_low, perc_high}`            |
| `X_PADDING`, `Y_PADDING` (hist range)  | 19               | `30` / `30`                          | `dlc_spatial_stats.pixel_bins.{x_padding, y_padding}`           |
| `UNB_REG`, `UNB_REG_M`                  | 16, 17, 19       | `0.1 / 1000` (16), `0.02 / 1` (17), `0.02 / 10` (19) | `dlc_spatial_stats.wasserstein.{reg, reg_m}` using cell 19 values |
| `W_OCC_PENALTY_FACTOR`                 | 16, 17, 19       | `20` (16), `2` (17, 19)              | `dlc_spatial_stats.wasserstein.occupancy_penalty_factor = 2`    |
| `MIN_MASS`, `EPS`                       | 21               | `1e-4`, `1e-8`                        | `dlc_spatial_stats.displacement_field.{min_mass, eps}`           |
| Arrow styling (`ARROW_LW_MIN/MAX`, `ARROW_ALPHA_MIN/MAX`) | 21 | `0.1 / 3.0`, `0.9 / 0.9`            | `dlc_spatial_stats.displacement_field.arrow.*`                 |
| `stroke_date_str` per-mouse            | 13, 16, 17, 19   | hard-coded per mouse                 | Already in `configs/animals.yaml.animals.{PS*}.stroke_date`     |
| `FIRST_DATE_STR` / `first_allowed_date_str` | 13, 16, 17, 19 | per-mouse strings                    | Already in `configs/animals.yaml.animals.{PS*}.first_allowed_date` (per-animal baseline cutoff) |

None of the constants above get promoted *in Phase 7* — they belong
to Phase 5.x mini (overlay config) or Phase 9 (inferential stats
config). Phase 7's config changes stay tongue + jaw + whisker + nose
kinematics only.

---

## Reconciliation with prior classifications

### 1. Whisker cells 14 / 16 / 18 vs pixelbin cells 11 / 13 / 15

The whisker classification labeled whisker-notebook cells 14 / 16 /
18 (the multi-bodypart overlay heatmaps) as **Exploratory** with the
rationale "the per-bodypart versions already in Phase 5/6 are
strictly cleaner — the multi-bodypart-on-one-figure overlay variant is
an exploratory visualization." That framing was incomplete.

The pixelbin notebook is the **canonical source** for the multi-bodypart
overlay pattern. Pixelbin cells 11 / 13 / 15 (per-session, binned,
and Δ multi-bodypart overlays) are Production for the scheduled
Phase 5.x mini per DECISIONS.md 2026-04-18. Whisker cells 14 / 16 /
18 implement variants of the same pattern but on an earlier config
surface (whisker-only likelihood thresholds plus the 6 whisker
bodyparts only, versus pixelbin's full 9-bodypart set).

**Net reconciliation:** whisker cells 14 / 16 / 18 are effectively
**Deprecated-by-pixelbin-cells-11/13/15** — the Phase 5.x mini port
ingests the pixelbin versions as canonical, not the whisker-notebook
variants. The "Exploratory" label in `classification-whiskers.md`
§"Cells 14 / 16 / 18" stays because those cells are not ported by
either Phase 7 or Phase 5.x, but the label rationale should be
understood as "subsumed by the pixelbin canonical Phase 5.x port,"
not "not worth porting anywhere." No edit to
`classification-whiskers.md` is required; this note documents the
reconciliation.

### 2. `dlc_spatial/` docstring cell-number discrepancy

The docstrings in `src/stroke_orofacial/dlc_spatial/heatmaps.py`
(cell 5 of pixelbin), `pixel_bins.py` (cells 5-7, 11-13 of pixelbin),
and `difference_maps.py` (cell 7 of pixelbin) reference cell numbers
that do **not** match the current `notebook-structure-pixelbin.md`
extract. In the current extract:

* Cell 5 is a markdown header (`# Load parquet files`)
* Cell 7 is a markdown header (`## Sanity check, verify centering`)
* Cell 11 is the per-session multi-bodypart overlay
* Cell 13 is the binned multi-bodypart overlay

Mapping the docstring refs to current numbering:

| Docstring ref        | Likely current cell | Reason                                                                 |
|----------------------|---------------------|------------------------------------------------------------------------|
| "cell 5"              | Cell 6 (loader)     | Loader body; off-by-one for the "Load parquet files" markdown header.   |
| "cells 5-7"           | Cells 6, 8 (+ 11?)   | Loader + sanity check (+ possibly the first heatmap).                   |
| "cells 11-13"         | Cells 11, 13        | Per-session + binned multi-bodypart overlays (with their md headers).   |
| "cell 7" (diff_maps)  | Cell 15             | Δ multi-bodypart overlay (the heatmap-subtraction cell).                 |

The discrepancy comes from the `dlc_spatial/` docstrings being
written against a pre-split / pre-extract cell numbering (probably
code-cells-only, or against an older notebook copy). **This is a
follow-up documentation cleanup**, not a Phase 7 port target — opening a
small PR in a Phase 5/6 housekeeping commit to update the docstrings
against the current `notebook-structure-pixelbin.md` numbering would
be a 20-minute fix.

Recorded in this classification so 7a–7f authors reading the
`dlc_spatial/` modules don't chase the wrong cell numbers.

### 3. `rel_day` remap convention

Cell 13 uses `return -1 if delta == 0 else delta` — i.e., the stroke
day groups with pre-stroke sessions as `rel_day = −1`. Cells 16 / 17
/ 19 use the straight `(d - stroke_date).days` with stroke day →
`rel_day = 0`. The canonical Phase 6.7 convention
(`SessionManifest.rel_day = (session_date - stroke_date).days`) keeps
stroke day at 0.

When the Phase 5.x mini ships, **drop the `stroke→−1` remap** —
align on the Phase 6.7 canonical `rel_day = 0 at stroke`. Flagged
here so the remap isn't accidentally re-ported.

---

## Next Cowork turn

Classification of the nose notebook
(`20251117_DLC_analysis_nose.ipynb`, 17 cells, 9 code) under
`docs/phase-7/classification-nose.md`, same format. Per the nose
notebook name + the `dlc_spatial/heatmaps.py` module docstring
("ported from cells 10-11 of `20251117_DLC_analysis_nose.ipynb` and
`20251117_DLC_analysis_jaw.ipynb` (siblings, consolidated into one
parameterized module)"), nose is expected to have **substantial
overlap with the jaw notebook** (both were sibling Phase 5 sources
for the per-bodypart heatmap module) and **little new Phase 7
surface area**. Classification should note which cells are already
ported via the jaw/nose consolidation vs. which represent nose-specific
kinematics endpoints (likely Exploratory under this rubric — the Q6
list from the kickoff doc does not include nose-specific kinematic
endpoints beyond the per-bodypart PSD aggregates deferred to 7d).
