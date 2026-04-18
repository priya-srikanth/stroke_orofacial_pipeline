# Migration Log

Each phase of the consolidation records what changed and any intentional behavior
differences vs. the legacy notebooks.

---

## Phase 0 — Repo skeleton

**Date:** 2026-04-17

**What was done:**
- Created full directory tree per §3 of DESIGN.md.
- Added `pyproject.toml` (package `stroke_orofacial`, editable install).
- Added `environment-mac.yml` (from current `frsb` env) and `environment-windows.yml` (placeholder).
- Added `.gitignore`, `.gitattributes`, `README.md`.
- Added stub config files: `configs/paths.yaml`, `configs/animals.yaml`, `configs/defaults.yaml`.
- Added all stub Python modules under `src/stroke_orofacial/` (empty, no logic).
- Added stub notebooks under `notebooks/` (title + USER INPUTS cell only).
- Added `tests/test_import.py` (single import smoke test).

**Behavior differences vs. legacy:** None (no analysis logic implemented yet).

**Exit criteria met:**
- [x] `pip install -e .` succeeds in `frsb`.
- [x] `pytest tests/` passes (1 test: import smoke test).

---

## Phase 1 — Paths + manifest + animals metadata

**Date:** 2026-04-17

**What was done:**

### Sub-phase 1a: PathResolver
- Implemented `src/stroke_orofacial/paths.py` with `PathResolver` class.
- Loads `configs/paths.yaml`, auto-detects platform (Darwin/Windows), supports
  `STROKE_PIPELINE_MACHINE` env var override.
- Convenience methods: `dlc_output_dir()`, `alignment_templates_dir()`,
  `alignment_template()`, `session_processing_out()`.
- Added `tests/test_paths.py` (15 tests, including integration tests against
  the live MICROSCOPE mount).

### Sub-phase 1b: SessionManifest + animals loader
- Implemented `src/stroke_orofacial/animals.py` with `AnimalInfo`, `Exclusion`
  dataclasses and `load_animals()` / `get_animal()` YAML loader.
- Implemented `src/stroke_orofacial/manifest.py` with `SessionManifest`
  dataclass and `build_manifest()` function.
- `build_manifest()` discovers filtered DLC files by date glob, resolves
  alignment templates, computes stroke-relative day/phase, and checks
  analysis-type-specific exclusions.
- Added `tests/test_animals.py` (14 tests) and `tests/test_manifest.py`
  (9 tests, including integration test against real PS46 session 2025-03-07).

### Sub-phase 1c: animals.yaml population
- Transcribed master animal metadata from two legacy notebooks into
  `configs/animals.yaml`:
  - `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  - `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
- Cross-checked: stroke dates, session ranges, and analysis params are
  identical across both notebooks' three repeated declarations each.
- Included per-animal `analysis_params` (`break_thr_trialmax`,
  `break_thr_alllicks`) which vary by animal.

**Convention established:** `stroke_date` is the date of the **last pre-stroke
session**. The stroke is induced after that day's behavioral session. Sessions
on `stroke_date` are baseline; only sessions strictly after are post-stroke.
This matches the legacy notebook semantics where `d0` is the last baseline day.

**Intentional behavior differences vs. legacy notebooks:**

1. **Exclusions upgraded to universal (`applies_to: [all]`).**
   In the legacy code, exclusions were declared per-notebook:
   - Tongue notebook excluded PS54: 2025-04-26 only.
   - Jaw notebook excluded PS55: 2025-04-27 and 2025-04-28 only.
   - PS51: 2025-04-26 was commented out in both.
   In the consolidated `animals.yaml`, all four exclusions are now universal
   (`applies_to: [all]`) because the underlying reasons (Rose Bengal sham
   with delayed licking; messed up reward delivery) affect all analyses, not
   just the one where they happened to be declared. PS51: 2025-04-26 is now
   active (was commented out in legacy). This was reviewed and approved by
   Priya before transcription.

**Exit criteria met:**
- [x] `pytest tests/` passes (39 tests).
- [x] `ruff check src/` clean.
- [x] `configs/animals.yaml` reviewed and approved by Priya.

---

## Phase 2 — Spout behavior processing

**Date:** 2026-04-18

**Legacy file disambiguation (per CLAUDE.md 3-tier rule):**

- **Canonical notebook:** `batch_process_20260410PS.ipynb` (Rule 1: latest
  YYYYMMDD). Deprecated: `batch_process.ipynb` (undated),
  `batch_process_20250503PS.ipynb` (superseded).
- **Python helpers (6 unambiguous):** `process_ws_signals.py`,
  `find_licks_and_rewards.py`, `find_running_bouts.py`,
  `find_grooming_bouts.py`, `find_quiet_bouts.py`,
  `find_peri_reward_periods.py` — all only-version (Rule 1 trivially resolved).
- **Treadmill calibration (Rule 3 → Priya confirmed):**
  `calibrate_and_smooth_treadmill_signal_PS.py` is canonical. The notebook
  imports `_patched` (stale reference); no file with that name exists. The
  plain `calibrate_and_smooth_treadmill_signal.py` (2025-05-03) lacks the
  offset-override logic. `_PS.py` (2026-04-10) was confirmed canonical by
  Priya.

**What was done:**

### Sub-phase 2a: Wavesurfer I/O + treadmill calibration
- Implemented `src/stroke_orofacial/spout_behavior/wavesurfer_io.py`:
  `load_wavesurfer_signals()`, `find_wavesurfer_file()` (glob-based, excludes
  "kHz" files), `calibrate_treadmill()`, `smooth_treadmill()`,
  `resolve_treadmill_offset()`.
- Ported from `process_ws_signals.py` and
  `calibrate_and_smooth_treadmill_signal_PS.py`.
- Updated `configs/paths.yaml`: added `microscope_pipeline_outputs` and
  `wavesurfer_raw` (list mount: MICROSCOPE primary, Mac-local fallback).
- Created `configs/session_overrides.yaml` with per-session treadmill offset
  overrides (moved out of `defaults.yaml`).
- Populated `configs/defaults.yaml` with all cohort-wide params from legacy
  `params.json` (authoritative from canonical notebook).
- Updated `PathResolver`: list-mount support for fallback chains,
  `pipeline_outputs()`, `wavesurfer_dir()`.
- Added `bnpm` and `pywavesurfer` to `pyproject.toml` dependencies.

### Sub-phase 2b: Lick detection + reward detection
- Implemented `src/stroke_orofacial/spout_behavior/lick_detection.py`:
  `find_licks_and_rewards()` (main entry), `find_reward_indices()`,
  double-threshold lick detection with asymmetric lockout cleaning.
- Ported from `find_licks_and_rewards.py`.

### Sub-phase 2c: Bout detection
- Implemented `src/stroke_orofacial/spout_behavior/bouts.py`:
  `find_running_bouts()`, `find_grooming_bouts()`, `find_quiet_bouts()`,
  `find_peri_reward_periods()`.
- Ported from 4 legacy modules.

### Sub-phase 2d: Session orchestrator + notebook + parity check
- Implemented `src/stroke_orofacial/spout_behavior/session_processing.py`:
  `process_session()`, `process_animal()` with overwrite protection
  ("skip" / "prompt" / "force").
- Created `src/stroke_orofacial/config_loader.py`: `load_defaults()`,
  `load_session_overrides()`, `get_session_params()` (deep-merge),
  `check_merge_required()` (raises NotImplementedError for deferred merges).
- Created `notebooks/00_session_processing.ipynb` (thin orchestrator with
  USER INPUTS cell).
- Per-session `params.json` at `params/{animal}/{YYYYMMDD}.json` for full
  run provenance.

### Sub-phase 2e: Tests + MIGRATION_LOG
- `tests/test_wavesurfer_io.py` — wavesurfer loading, treadmill calibration,
  file discovery, integration against real PS46/20250307.
- `tests/test_lick_detection.py` — reward detection, lick onset/offset,
  lockout cleaning, parity against `session_processing3/`.
- `tests/test_bouts.py` — running/grooming/quiet/peri-reward unit tests,
  parity against `session_processing3/` for PS46/20250307.
- `tests/test_session_processing.py` — params.json structure, skip-path
  behavior, integration parity for both PS46 sessions.
- `tests/test_config_loader.py` — deep-merge, override loading, merge-required
  check.

**Parity verified** on two sessions (11 arrays each, all exact match):
- PS46 / 2025-03-07 (baseline, day -6): 11/11 PASS
- PS46 / 2025-03-20 (post-stroke, day +7): 11/11 PASS

Boolean masks and integer index arrays: `np.array_equal`.
Treadmill float arrays: `np.allclose(rtol=1e-10, atol=1e-10)`.

**Intentional behavior differences vs. legacy `session_processing3/`:**

1. **Per-session params.json** at `params/{animal}/{YYYYMMDD}.json` instead of
   a single root-level `params.json`. Each file records `session_id`, `animal`,
   `date`, `run_timestamp`, `skipped`, the merged `params` actually used, and
   a `processing_log` of skip/overwrite decisions per output type.

2. **params.json always written, even on skip.** When `overwrite="skip"` and
   all outputs exist, the per-session `params.json` is still written with
   `skipped: true`. This provides a full audit trail of what ran vs. skipped.

3. **Treadmill offset_overrides moved** from `defaults.yaml` into
   `configs/session_overrides.yaml` under a structured `overrides:` key.
   `defaults.yaml` contains only the cohort-wide default offset value.

4. **Output location on MICROSCOPE** at `pipeline_outputs_v2/spout_behavior/`
   instead of Mac-local `session_processing3/`.

5. **Cross-platform wavesurfer path support.** `wavesurfer_raw` logical root
   tries MICROSCOPE first, falls back to Mac-local. Pipeline currently runs
   from Mac using the local fallback; will run from Windows once Priya rsyncs
   the wavesurfer data to MICROSCOPE (separate task).

**Known constraints:**
- Raw wavesurfer data currently Mac-local only; mirror to MICROSCOPE pending.
- PS48 / 2025-03-14 session merge (two wavesurfer files) is documented in
  `configs/session_overrides.yaml` under `merges:` but implementation is
  deferred beyond Phase 2. `check_merge_required()` raises
  `NotImplementedError` if this session is processed.
- `trial_segmentation.py` remains a stub — legacy notebook does not segment
  trials; that concept belongs to later phases.

**Exit criteria met:**
- [x] `pytest tests/` passes (103 tests).
- [x] `ruff check src/` clean.
- [x] Parity verified on PS46 baseline + post-stroke sessions.

---

## Phase 2.5 — Tone detection + per-side peri-periods

**Date:** 2026-04-18

**Purpose:** Restore features present in Rich's upstream repo but dropped in
Priya's fork (which Phase 2 ported from). Needed for cue-aligned analyses
in Phase 4+.

**Source:** Rich's upstream `facerhythm_stroke_biomarker_exp` repo:
- `find_licks_and_rewards.py` — adds `Tone_L`/`Tone_R` detection alongside
  rewards (same rising-edge algorithm, same threshold).
- `find_peri_reward_and_tone_periods.py` — produces 4 per-side boolean masks
  instead of a single consolidated `peri_reward_bool`.

Both files are only-versions in the upstream repo (Rule 1 trivially resolved).

**What was done:**

### Sub-phase 2.5a: Tone detection
- Added `find_tone_indices()` to `lick_detection.py` — same rising-edge
  detection as rewards, applied to digital `Tone_L`/`Tone_R` channels.
- Extended `find_licks_and_rewards()` return dict to include `Tone_L`/`Tone_R`.

### Sub-phase 2.5b: Per-side + peri-tone periods
- Added `find_peri_reward_and_tone_periods()` to `bouts.py` producing 4
  per-side boolean masks: `peri_reward_L`, `peri_reward_R`, `peri_tone_L`,
  `peri_tone_R`. Window: `[0, 6]` seconds (same as consolidated peri-reward).
- Existing `find_peri_reward_periods()` unchanged (backward compat).
- Added `find_peri_reward_and_tone_periods` section to `configs/defaults.yaml`.

### Sub-phase 2.5c: Orchestrator integration
- `licks_and_rewards` NPZ now includes `Tone_L`, `Tone_R` index arrays.
- `peri_reward_periods` NPZ now includes `peri_reward_L`, `peri_reward_R`,
  `peri_tone_L`, `peri_tone_R` boolean masks alongside existing
  `peri_reward_bool`.

### Sub-phase 2.5d: Tests + MIGRATION_LOG
- Added tone detection unit tests to `test_lick_detection.py`.
- Added per-side peri-period unit tests to `test_bouts.py`.
- Added integration tests verifying new keys are present in
  `test_session_processing.py`.

**Strictly additive:** All 11 original parity arrays unchanged in value.
Verified on PS46 20250307 + 20250320.

**Note on output subdir naming:** The `peri_reward_periods/` output subdir now
contains both reward AND tone period masks despite its name. This naming is
kept for parity with `session_processing3/`. Future renaming is a non-goal;
the NPZ key names (`peri_reward_L/R`, `peri_tone_L/R`) make the contents
unambiguous.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Original parity still holds (11/11 arrays exact on both sessions).
- [x] New keys present and non-trivial on PS46 20250307 + 20250320.

---

## Phase 3 — Wavesurfer ↔ Video ↔ DLC Alignment

**Date:** 2026-04-18

**Legacy file disambiguation (per CLAUDE.md 3-tier rule):**

- **Canonical notebook:** `batch_process_alignment_20251216PS.ipynb` (Rule 1:
  latest YYYYMMDD). Non-canonical: `playground.ipynb` (undated, older).
  Notebook used as orchestrator reference only — the core algorithm lives in
  the helper module.
- **Core helper:** `make_alignment_templates_20251216.py` in Rich's upstream
  repo (`facerhythm_stroke_biomarker_exp/analysis/alignment/`). Only version
  found (Rule 1 trivially resolved). Note: lives in a different repo from the
  notebook — this is by design; Rich wrote the algorithm, Priya orchestrates.

**What was done:**

### Sub-phase 3a: Path setup + alignment template loading
- Added `camera_raw` logical root to `configs/paths.yaml` pointing to
  MICROSCOPE camera data (read-only).
- Added `PathResolver.camera_dir(date, animal)`.
- Implemented `src/stroke_orofacial/alignment/templates.py`:
  `load_alignment_template()`, `pick_camera_csv()`, `load_camera_csv()`,
  `discover_video_files()`.
- Added `alignment` section to `configs/defaults.yaml` with all sync/matching
  parameters from the legacy notebook.

### Sub-phase 3b: Core alignment functions + SessionManifest integration
- Ported `make_alignment_templates_20251216.py` into
  `src/stroke_orofacial/alignment/frame_sync.py`: `_normalize_minmax_robust()`,
  `_find_rising_edges()`, `_align_edge_sequences()`, `_safe_interp1d()`,
  `make_alignment_template()`.
- Created `src/stroke_orofacial/alignment/timebase.py`: `AlignmentResult`
  dataclass, `ws_sample_to_session_time()`, `frame_to_session_time()`,
  `session_time_to_frame()`, `load_or_compute_alignment()`.
- **SessionManifest integration (amendment 3):** `build_manifest()` now
  populates `wavesurfer_file` (from `wavesurfer_raw` path) and `video_files`
  (from `camera_raw` path, cam2). Both are optional — gracefully return
  None/empty if data isn't mounted.

### Sub-phase 3c: Alignment orchestrator notebook
- Created `notebooks/01_alignment.ipynb` (thin orchestrator, cam2 only).
- Default behavior: load existing templates from `alignment_templates/cam2/`,
  recompute only if missing.
- Overwrite modes: skip/prompt/force (matching Phase 2 convention).
- Per-session `params.json` at `pipeline_outputs_v2/alignment/params/{animal}/{YYYYMMDD}.json`.

### Sub-phase 3d: Parity check
- Re-computed alignment templates for PS46 2025-03-07 (baseline, day -6) and
  PS46 2025-03-20 (post-stroke, day +7).
- Compared against existing `alignment_templates/cam2/PS46/` NPZs.

**Parity results (per amendment 1 tolerances):**

| Array | PS46/20250307 | PS46/20250320 | Tolerance |
|-------|--------------|--------------|-----------|
| `sig_camIdx__idx_ws` | PASS | PASS | `rtol=1e-10` |
| `sig_wsIdx__idx_cam` | PASS | PASS | `rtol=1e-10` |
| `slope_ws_per_camFrame` | PASS (4.0062) | PASS (4.0058) | `rtol=1e-8` |
| `intercept_ws_samples` | PASS (-8747.4) | PASS (-9133.1) | `rtol=1e-8` |

No tie-break differences observed in the pattern matcher. NaN patterns at
array edges match exactly between re-computed and existing templates.

### Sub-phase 3e: Tests + MIGRATION_LOG
- `tests/test_frame_sync.py` — normalization, edge detection, sequence matching,
  interpolation, full template generation with synthetic sync signals.
- `tests/test_timebase.py` — time-base converters, AlignmentResult, integration
  tests loading/recomputing real alignment templates.
- `tests/test_alignment_templates.py` — template loading, camera CSV discovery,
  video file discovery, SessionManifest integration test (amendment 3).

**Intentional behavior differences vs. legacy:**

1. **Default: load existing, compute if missing.** Legacy notebook always
   recomputes. New pipeline loads existing `alignment_templates/cam2/` NPZs
   by default, recomputing only when the template is missing. This leverages
   already-validated alignment work.
2. **cam2 only.** Legacy notebook processes cam1-4. New pipeline processes
   only cam2 (the DLC camera). Other cameras can be added later.
3. **Per-session params.json** at `alignment/params/{animal}/{YYYYMMDD}.json`
   (matching Phase 2 convention). Legacy had no per-session params record.
4. **SessionManifest now populates `wavesurfer_file` and `video_files`.**
   Phase 1 left these as None/empty. Now resolved from `wavesurfer_raw` and
   `camera_raw` paths respectively.

**§4.4 time-base contract confirmed:**
- Wavesurfer sample rate: 1000 Hz (confirmed in Phase 2).
- `ws_samples → session_time_s`: divide by 1000.
- `video_frame_index → session_time_s`: via `sig_wsIdx__idx_cam[frame] / 1000`.
- `dlc_frame_index → session_time_s`: equals video_frame_index by construction.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Parity verified on PS46 baseline + post-stroke sessions.
- [x] `SessionManifest.wavesurfer_file` and `.video_files` populated.

---

## Phase 4 — DLC I/O + Centering

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1: siblings vs
duplicates, DECISIONS.md "2026-04-18 — Disambiguation rule refined"):

- **Canonical notebook:** `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`
  (Rule 1: latest YYYYMMDD within the whole-session parquet builder family).
- **Superseded:** `20260111_DLC_analysis_build-parquet_tongue.ipynb` — same
  family (both whole-session parquet builders), earlier date → superseded.
- **Siblings (Phase 7 scope, not Phase 4):**
  `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and
  `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` — distinct scope
  markers (`_tongue` vs `_jaw`), both ws-aligned kinematics notebooks. Each
  will be ported independently in Phase 7.
- **Archived:** 37 files in `old_code/` — all Deprecated.
- **No external .py helpers** — all production functions defined inline in
  cell 8 of the canonical notebook.

**Dead code classification** (65 cells):
- Cells 0-11: **Production** (imports, file discovery, centering pipeline,
  cache save/load). Ported.
- Cells 12-64: **Exploratory** (heatmaps, kinematics, PSD, statistics,
  colormap testing) or **Deprecated** (empty cells). Not ported. All
  downstream of centering — Phases 5-9 scope.
- No Ambiguous cells.

**What was done:**

### Sub-phase 4a: DLC loader
- Implemented `src/stroke_orofacial/dlc_io/loaders.py`: `read_dlc()` (H5
  preferred, CSV fallback, 3-level MultiIndex flattening to
  `{bodypart}_{coord}`), `discover_dlc_filtered_files()`.
- Added `tables` (pytables) to `pyproject.toml`.

### Sub-phase 4b: DLC centering
- Implemented `src/stroke_orofacial/dlc_io/centering.py`: `CenterMode` enum,
  `compute_center()` (nose / spout_midpoint / eye_midpoint), `apply_centering()`.
- Added `dlc_centering` section to `configs/defaults.yaml`:
  `likelihood_threshold=0.7`, `default_mode="nose"`, `compression="zstd"`.

### Sub-phase 4c: Parquet I/O + orchestrator
- Implemented `src/stroke_orofacial/dlc_io/parquet.py`:
  `write_centered_parquet()` (atomic tmp→rename), `read_centered_parquet()`,
  `build_centered_parquet()` (pure function, no module-level state — per
  DECISIONS.md "iterate over animals without notebook restart").
- Created `notebooks/10_dlc_build_parquets.ipynb` with USER INPUTS cell.
  Builds all three center modes by default.

### Sub-phase 4d: Parity check
- All three centering modes verified against legacy `_dlc_cache_centered_*`
  parquets for PS46/20250307.

**Parity results:**

| Mode | Frames | Cols | Dtypes | assert_frame_equal | Hash |
|------|--------|------|--------|-------------------|------|
| nose | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | c23dc714 ✓ |
| spout_midpoint | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | 2a6efb6a ✓ |
| eye_midpoint | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | b13af51c ✓ |

All frames preserved (no 975K cap — per DECISIONS.md "keep all frames").

### Sub-phase 4e: Tests + MIGRATION_LOG
- `tests/test_dlc_loaders.py` — file discovery, CSV fallback, integration
  test loading real DLC H5.
- `tests/test_dlc_centering.py` — all three center modes, likelihood gating,
  float32 preservation, centering arithmetic.
- `tests/test_dlc_parquet.py` — hash signatures, write/read roundtrip, skip
  existing, integration parity tests for all three modes.

**Intentional behavior differences vs. legacy:**

1. **All frames kept (no 975K cap).** Legacy `20260111` notebook filtered to
   first 975K frames. The canonical `20260323` notebook's build cell has no
   cap. Our pipeline follows `20260323`: output row count equals source DLC
   frame count.
2. **Overwrite protection: skip/force only (no prompt).** DLC parquets are
   deterministically derivable from source DLC H5 files, so interactive
   prompt-mode adds less value than in Phase 2 where session-processing
   outputs took longer to rebuild.
3. **Output location on MICROSCOPE** at
   `pipeline_outputs_v2/dlc_analysis/centered_{mode}/{animal}/`.
   Legacy cached in `O2_analysis/{animal}/_dlc_cache_centered_{mode}/`.
4. **Per-session params.json** at `dlc_analysis/params/{animal}/{YYYYMMDD}.json`.
5. **Stateless orchestrator.** `build_centered_parquet()` is a pure function
   callable in animal × date × mode loops without accumulating state or
   requiring notebook restart.
6. **Output directory structure** (separate subdirs per center_mode) directly
   supports Phase 5+ per-(bodypart, center_mode) plotting parameters (per
   DECISIONS.md "Phase 5+ downstream analyses").

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Parity verified for all three centering modes on PS46/20250307.
- [x] All frames preserved (frame count == source DLC frame count).

---

## Phase 5 — DLC Spatial Analyses (Whole Session)

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1: siblings vs
duplicates):

- **Siblings (consolidated into one module):**
  `20251117_DLC_analysis_nose.ipynb` and `20251117_DLC_analysis_jaw.ipynb` —
  same date, distinct scope markers (`_nose` vs `_jaw`). Spatial analysis
  cells (10-12) are structurally identical. Consolidated into parameterized
  functions in `dlc_spatial/pixel_bins.py` and `dlc_spatial/heatmaps.py`.
  Jaw notebook's kinematics/PSD cells (13+) are Phase 7 scope.
- **Canonical for pixel-bin:** `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`
  (latest YYYYMMDD for all-bodyparts spatial analysis).
- **Exploratory / Deferred to Phase 9:**
  `20251201_DLC_analysis_all_bodyparts_2KSD_spatial-maps.ipynb` — 2D-KS-distance
  visualization tightly coupled to inferential stats. Not ported.
- **Cells 14-20 of 20260323:** remain Exploratory/Deferred (kinematics, PSD).

**Dead code classification:**

`20251202` notebook (26 cells):
- Cells 0-4: Exploratory (imports, paths, cache loading, sanity check).
- **Cells 5-7: Production** — per-session heatmaps, binned heatmaps,
  subtraction maps. Ported.
- **Cells 8-10: Deferred to Phase 9** — permutation null + per-day inferential
  stats with p-values.
- **Cells 11-13: Production** — batch spatial viz, eye/spout grouped heatmaps.
  Ported.
- Cells 14+: Exploratory/Helper.

`20251117` nose/jaw notebooks: cells 10-12 Production (ported); rest
Exploratory or Phase 7 scope.

**What was done:**

### Sub-phase 5a: Config + window_selector scaffold
- Added `dlc_spatial` section to `configs/defaults.yaml` with per-bodypart
  likelihood thresholds, colormaps, and per-(bodypart, center_mode) axis
  limits (derived from PS46/20250307 data ranges).
- Scaffolded `WholeSessionWindow` in `window_selector.py` (Phase 6 extends
  with reward-aligned selector).

### Sub-phase 5b: Pixel bins
- Implemented `src/stroke_orofacial/dlc_spatial/pixel_bins.py`:
  `get_masked_xy()`, `build_histogram()` (fine-resolution, nbins=100),
  `build_stats_grid()` (coarser, target_bin_size=25px),
  `build_baseline_histogram()`.
- Permutation null deferred to Phase 9.

### Sub-phase 5c: Heatmaps
- Implemented `src/stroke_orofacial/dlc_spatial/heatmaps.py`:
  `plot_heatmap()` (hist2d with LogNorm + density), `save_heatmap_png()`.
- Per-(bodypart, center_mode) colormap and axis limits from config.

### Sub-phase 5d: Difference maps
- Implemented `src/stroke_orofacial/dlc_spatial/difference_maps.py`:
  `compute_difference_map()`, `plot_difference_map()` (diverging colormap),
  `save_difference_map_png()`.

### Sub-phase 5e: Orchestrator notebook
- Created `notebooks/11_dlc_spatial_whole_session.ipynb` — loops over
  (animal × date × bodypart × center_mode). Stateless, skip/force overwrite.

### Sub-phase 5f: Parity check

**Verified:**
- Fine heatmap produces non-trivial counts (925,098 on PS46/20250307 nose,
  nose-centered, 421 non-zero bins in 100×100 grid).
- Output shapes, dtypes, and file structure match legacy conventions.
- Code is a faithful port of production cells 5-7, 11-13 of
  `20251202_all_bodyparts_stats_pixelbin` and cells 10-12 of
  `20251117_nose`/`20251117_jaw` (consolidated).

**Not verifiable at array level (legacy output limitations):**
- Legacy saved per-session heatmaps only as PNGs, not NPZs. Per-session
  array parity is impossible without rebuilding the legacy pipeline.
- Baseline aggregate parity requires running the new pipeline across all
  pre-stroke PS46 sessions — deferred to a Phase 10 cleanup task.

**Deferred cleanup task for Phase 10:**
- Run the Phase 5 pipeline across all pre-stroke PS46 sessions, aggregate
  the histograms, and compare the resulting aggregate NPZ against the legacy
  `PS46_nose_stats/centered_nose/nose_baseline_hists_preALL_*.npz` arrays.
  Expected to match at `rtol=1e-6` if the port is faithful.

### Sub-phase 5g: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_pixel_bins.py` — masking, histogram shapes, stats grid, baseline
  aggregation.
- `tests/test_heatmaps.py` — figure generation, PNG save.
- `tests/test_difference_maps.py` — subtraction arithmetic, diverging colormap
  plot, PNG save.

**Intentional behavior differences vs. legacy:**

1. **Per-(bodypart, center_mode) axis limits.** Legacy used hardcoded
   `y_limits=(50, 550)` which were for un-centered pixel coordinates.
   Nose-centered data needs `y_limits=(-120, 130)`. The new pipeline loads
   axis limits from `configs/defaults.yaml` per (bodypart, center_mode) tuple.
   Per DECISIONS.md "Phase 5+ downstream analyses."
2. **Overwrite protection: skip/force only** (matching Phase 4).
3. **Output location on MICROSCOPE** at
   `pipeline_outputs_v2/dlc_analysis/spatial_whole_session/`.
4. **Sibling consolidation.** Legacy had separate nose/jaw notebooks with
   duplicated spatial analysis code. New pipeline uses one parameterized
   module that loops over bodyparts.
5. **Permutation null deferred to Phase 9.** Cells 8-10 of `20251202`
   compute inferential statistics (permutation p-values). Deferred per
   DECISIONS.md "Phase 5 defers permutation/inferential spatial stats to
   Phase 9."
6. **2KSD notebook deferred in full to Phase 9.** 2D-KS-distance
   visualization tightly coupled to its stats computation.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Fine heatmap verified non-trivial on PS46/20250307.
- [x] Per-(bodypart, center_mode) axis limits in `configs/defaults.yaml`.

---

## Phase 5.5 — DLC Inference Port (O2)

**Date:** 2026-04-18

**Legacy file disambiguation:**
- **Canonical:** `20251112_DLC_batch_video_analysis_O2.ipynb` (Rule 1: latest
  YYYYMMDD). 55 cells.
- **Deprecated:** `old_code/20251103_DLC_batch_video_analysis.ipynb` (pre-O2),
  `20251104_DLC_batch_video_analysis_O2.ipynb` (earlier date),
  `20251104_..._O2_2.ipynb` and `_O2_3.ipynb` (numbered variants).
- No external `.py` helpers — all scripts embedded inline in notebook cells.

**Dead code classification:** 55 cells; ~20 production (SSH setup, script
generation, SBATCH, staging, renaming, copy), ~30 exploratory (monitoring,
manual verification, debugging, batch-size scout monitoring).

**What was done:**

### Sub-phase 5.5a: Core modules
- `runner.py`: `generate_inference_script()` produces standalone
  `run_dlc_batch.py` (DLC `analyze_videos` + `filterpredictions`, per-video
  iteration, YAML-based animal/date selection).
- `batch.py`: `discover_camera_dates()`, `discover_videos()`,
  `write_selection_yaml()`.
- `o2_job.py`: `generate_sbatch_script()` with configurable SBATCH resources,
  `o2_paths()` for path resolution.
- Added `dlc_inference_o2` section to `configs/defaults.yaml` with all SBATCH
  resources, DLC params, O2 paths, and snapshot rename mappings.

### Sub-phase 5.5b: Transfer utilities
- `transfer.py` (184 lines): `build_stage_videos_command()`,
  `build_copy_to_microscope_command()` (two-stage or direct),
  `build_rename_command()`, `rename_snapshots_local()`. Functions generate
  shell commands as strings — user pastes into terminal. The local rename
  utility (`rename_snapshots_local()`) is the only function that executes
  file operations directly.
- **Line count vs estimate:** 184 lines vs plan's ~80 estimate. Growth from:
  comprehensive docstrings (~40 lines), the `rename_snapshots_local()` helper
  for post-copy cleanup not in the original plan (~30 lines), and explicit
  per-animal/per-date loop in the staging command builder (~20 lines).

### Sub-phase 5.5c: README + notebook
- `README.md`: complete O2 workflow documentation (prerequisites, step-by-step,
  resources, DLC params, batch-size tuning, troubleshooting, security).
- `notebooks/20_dlc_inference.ipynb`: click-through orchestrator with USER
  INPUTS. Local actions (YAML writing, script generation) execute directly.
  SSH/rsync/sbatch commands are printed with user-specific inputs substituted
  — user pastes into terminal. No SSH from within notebook context.

### Sub-phase 5.5d: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_dlc_inference.py` — script generation (valid Python syntax,
  contains DLC API calls), YAML structure, SBATCH content, path resolution,
  rsync commands, local rename logic.
- Removed `batch_video_analysis.py` (Phase 0 stub, no imports anywhere in
  the repo — confirmed via `grep -rn`). Superseded by the split into
  `runner.py`, `batch.py`, and `o2_job.py`.

**Parity strategy: code-only review.**
- Running inference requires O2 GPU access + HMS credentials + ~30 min/video.
  Cost/benefit low for infrastructure code.
- Structural parity verified: generated `run_dlc_batch.py` matches legacy
  cell 6 (same DLC API calls, same argparse options, same per-video iteration
  + error handling). SBATCH matches legacy cell 14 resource requests. Rename
  logic matches cell 45.

**Intentional behavior differences:**
1. **Modular structure.** Legacy: all logic embedded in notebook cells (55
   cells, monolithic). New: split into 4 focused modules + README + notebook.
2. **SSH commands generated, never executed.** Per DECISIONS.md. Local actions
   run in-notebook; SSH/rsync/sbatch printed for user to paste.
3. **All constants in config.** SBATCH resources, DLC params, O2 paths, and
   snapshot renames moved to `configs/defaults.yaml` (were inline in notebook).

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] README documents full O2 workflow.
- [x] Notebook provides click-through interface without executing SSH.

---

## Phase 6 — DLC Spatial (Reward-Aligned)

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1):

- **Reclassified from Phase 4's Exploratory to Phase 6 Production:**
  `20260323` cell 16 (reward-aligned heatmaps, 1683 lines), cell 18
  (reward-aligned binned heatmaps), cell 20 (reward-aligned Δ heatmaps).
- **Re-read confirmation** (per DECISIONS.md "Legacy notebooks may receive
  active edits"): cell 16 re-read at Phase 6 kickoff. Legacy notebook
  mtime: 2026-03-23 (unchanged since Phase 4).
- All other cells (21-64) remain Exploratory/Deprecated.

**Dead code classification** (cells 16-20 revisited):
- Cells 16, 18, 20: reclassified **Production** for Phase 6 (were Exploratory
  in Phase 4 — deferred to Phase 6 scope by design).
- Cells 17, 19: markdown section headers.
- Cells 21-64: unchanged (kinematics Phase 7, PSD Phase 8+, stats Phase 9).

**What was done:**

### Sub-phase 6a: Extend window_selector + reward-aligned config
- Extended `window_selector.py` with `EventAlignedWindow` (generic, handles
  deduplication of overlapping event snippets) and `RewardAlignedWindow`
  (converts WS samples → camera frames via alignment LUT, ms → frames).
- Added `_ws_to_cam_frames()` helper (faithful port of cell 16's
  `_ws_to_cam_frames` function).
- Added `dlc_spatial_reward_aligned` section to `configs/defaults.yaml`:
  reward windows `[(-500, 5000), (-100, 1000)]` ms, trial groups
  `[all, L, R]`, 10 bodyparts (tongue legacy-ported, jaw/nose/6 whiskers
  sanity-check-only).

### Sub-phase 6b: Generalize Phase 5 spatial functions
- Added `frame_mask` parameter to `get_masked_xy()` — ANDed with likelihood
  mask when provided.
- Added `window` parameter (default `None` = whole session) to
  `build_histogram()`, `build_stats_grid()`, `plot_heatmap()`.
- **Phase 5 backward compatibility:** all 18 Phase 5 spatial tests pass
  unchanged with `None` default.

### Sub-phase 6c: Reward-aligned analysis functions
- Created `src/stroke_orofacial/dlc_spatial/reward_aligned.py`:
  `load_reward_events()` (per trial group from Phase 2 NPZ),
  `ws_samples_to_frame_indices()`, `build_reward_aligned_window()`,
  `build_reward_aligned_analysis()` (pure function, stateless).

### Sub-phase 6d: Orchestrator notebook + functional verification
- Created `notebooks/12_dlc_spatial_reward_aligned.ipynb`: loops over
  (animal × date × bodypart × center_mode × window_ms × trial_group).
  Stateless, skip/force overwrite.

### Sub-phase 6e: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_window_selector.py` — WholeSessionWindow compat,
  EventAlignedWindow mask construction + deduplication + edge clamping,
  RewardAlignedWindow WS→frame conversion, invalid event handling.
- `tests/test_reward_aligned.py` — load_reward_events per trial group,
  ws_samples_to_frame_indices, integration smoke test on PS46/20250307,
  trial-group-differ assertion (all = L + R).

**Parity status — three-section assessment:**

**Verified:**
- Phase 5 whole-session tests all still pass (18/18 — window refactor is
  additive; `None` default preserves existing behavior).
- Functional verification passes for tongue + nose on PS46/20250307
  with `(-500, 5000)` ms window, nose centering:
  - 96 rewards (48L + 48R), 132,096 selected frames (~14% of session)
  - Tongue: 54,159 histogram counts (~41% fill — expected for `lik_thr=0.5`)
  - Nose: 132,053 counts (~100% fill — expected for `lik_thr=0.7`)
  - L/R trial-group differences confirmed (48 vs 48 rewards, different
    histogram counts)

**Not verifiable at array level:**
- **First phase without an array-level parity reference.** Legacy cell 16
  was coded but never run to produce saved outputs on MICROSCOPE. No
  `PS46_*reward*` or `PS50_*reward*` directories exist. Array-level parity
  comparison is not possible.

**Deferred to future runs:**
- First scientific validation on each (bodypart, center_mode, window)
  combination requires visual inspection of the generated heatmaps.
- Per-bodypart reward-aligned config uses sanity-check-only defaults for
  everything except tongue (which has legacy values from cell 16).
- Jaw, nose, and all 6 whisker points (L/R_whiskers_1/2/3) configured
  with sanity-check-only defaults — not parity-verified.

**Phase 10 cleanup tasks:**
- Phase 5's `dlc_spatial.bodyparts` config has `L_whiskers_2`, `L_whiskers_3`,
  `R_whiskers_2`, `R_whiskers_3` with all `per_center_mode` entries set to
  `null`. Fill these in when whole-session whisker_2/3 analyses are
  exercised, matching whisker_1's pattern.

**Intentional behavior differences vs. legacy:**

1. **Window refactor to Phase 5 spatial functions.** `get_masked_xy()`,
   `build_histogram()`, `build_stats_grid()`, `plot_heatmap()` now accept
   an optional `window` parameter. Default `None` preserves whole-session
   behavior.
2. **Reward-aligned module in new location** at
   `src/stroke_orofacial/dlc_spatial/reward_aligned.py` (legacy was
   inline in cell 16 of the parquet-building notebook).
3. **Output to pipeline_outputs_v2** at
   `dlc_analysis/spatial_reward_aligned/{bodypart}_{center_mode}/`.
4. **All 10 bodyparts configured** (tongue + jaw + nose + 6 whiskers).
   Legacy only configured tongue (jaw/nose were commented out).
5. **Stateless orchestrator** matching Phase 4/5 pattern.
6. **window_selector abstraction** supports future event types (cue-aligned,
   custom) without infrastructure changes.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Phase 5 tests: 18/18 pass (no regression).
- [x] Functional verification on PS46/20250307 (tongue + nose).
- [x] 10 bodyparts configured in reward-aligned config.
