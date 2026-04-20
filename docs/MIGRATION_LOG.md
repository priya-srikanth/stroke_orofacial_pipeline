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

## Phase 4.5-lite — Eye-midpoint centering defaults + Phase 5 x_range + axis-limit fix

**Date:** 2026-04-20

**Scope-reduction finding at session start:** the kickoff
(`docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`) proposed
~150-200 lines across 5 sub-phases. Two of those are already satisfied by
Phase 4:
- **§4.5a** (add `eye_midpoint` branch to `compute_center`): already present
  in [src/stroke_orofacial/dlc_io/centering.py:104-112](../src/stroke_orofacial/dlc_io/centering.py#L104-L112);
  test at [tests/test_dlc_centering.py:49-54](../tests/test_dlc_centering.py#L49-L54).
- **§4.5c** (regenerate centered parquets): Phase 4 built all three modes
  cohort-wide; hashes (`c23dc714` / `2a6efb6a` / `b13af51c`) preserved.
  Per 2026-04-20 Priya decision: hash-verify instead of rebuild.

**Scope-expansion finding mid-session:** while investigating axis limits,
discovered a pre-existing bug in Phase 5: `plot_heatmap` / `build_histogram` /
`build_stats_grid` used hardcoded default `x_limits=(-200, 200)` /
`y_limits=(50, 550)` and never consumed `per_center_mode.xlim/ylim` from
config. Evidence: the sole existing Phase 5 output
`stroke_orofacial_pipeline_outputs/dlc_analysis/spatial_whole_session/nose_nose/PS46/heatmap_20250307.png`
is **entirely blank** (defaults are un-centered-pixel ranges; data is
centered at ~0). DECISIONS 2026-04-18 had stipulated per-(bodypart, center_mode)
axis limits but the code never actually read them. Priya approved expanding
Phase 4.5-lite scope to fix this bug + add `x_range` pre-histogram filter
support simultaneously.

### Sub-phase 4.5-A — Per-bodypart `center_mode` defaults in `configs/defaults.yaml`

Added `center_mode` key under every `dlc_spatial.bodyparts.{bp}` block (13 total):
- `tongue` → `spout_midpoint` (anatomically spout-anchored)
- `jaw`, `nose`, all 6 whiskers → `eye_midpoint` (sweep winner)
- `L_eye`, `R_eye`, `L_spout`, `R_spout` → their own fiducial regime
  (null-baseline control for Phase 9 significance testing)

Fiducial bodypart blocks (`L_eye`, `R_eye`, `L_spout`, `R_spout`) are new;
they contain `likelihood_threshold: 0.80` and `center_mode` only. No
`cmap` / `per_center_mode` since no heatmaps are generated for fiducials
today; downstream code tolerates the missing keys via `.get()` fallbacks.

The top-level `dlc_centering.default_mode: "nose"` is retained as ultimate
fallback; a comment marks per-bodypart defaults as the primary source.

### Sub-phase 4.5-B — `default_center_mode()` accessor

Added to [src/stroke_orofacial/config_loader.py](../src/stroke_orofacial/config_loader.py):
resolution order is `dlc_spatial.bodyparts.{bp}.center_mode` →
`dlc_centering.default_mode`. Validates against `CenterMode` enum; raises
`ValueError` on unknown mode, `KeyError` when nothing configured.

### Sub-phase 4.5-C — `TestDefaultCenterMode` in `tests/test_config_loader.py`

Six test cases: movement bodyparts, fiducials, fallback path, unknown
bodypart, empty-config KeyError, invalid-mode ValueError. All pass against
the real `configs/defaults.yaml`.

### Sub-phase 4.5-D — Notebook 12 stale `CENTER_MODES` fix

[notebooks/12_dlc_spatial_reward_aligned.ipynb](../notebooks/12_dlc_spatial_reward_aligned.ipynb):
added `"eye_midpoint"` to `CENTER_MODES`. Previously `["nose", "spout_midpoint"]`
— omission predates the sweep; no DECISIONS entry ever explained it.

### Sub-phase 4.5-E — Cohort-wide parquet hash baseline

[scripts/hash_centered_parquets.py](../scripts/hash_centered_parquets.py)
walks `{pipeline_outputs}/dlc_analysis/centered_{mode}/{animal}/*.parquet`
for all 8 animals × all 3 modes, computes SHA-256 content hashes plus the
`_param_sig` from the filename, and verifies Phase 4 parity.

Baseline as of 2026-04-20 (only PS46/20250307 exists on disk; other 7
animals not yet built):

| Animal | Date | Mode | param_sig | content_sha256[:12] | Size (MB) |
|--------|------|------|-----------|---------------------|-----------|
| PS46 | 20250307 | nose | c23dc714 | 7eac88e4e80d | 110.5 |
| PS46 | 20250307 | spout_midpoint | 2a6efb6a | c2b24d3db76f | 109.6 |
| PS46 | 20250307 | eye_midpoint | b13af51c | e87d7a93e26e | 110.1 |

All three `_param_sig` values match Phase 4 baseline → 4.5-lite config
change is parquet-neutral.

### Sub-phase 4.5-F — Axis-limit investigation

`notebooks/experiments/phase_4.5_lite_axis_limits.ipynb` pools the alignment-sweep
cache histograms (8 animals × all sessions × all bodyparts) into production
centered space (shift by `-ref_midpoint` per animal) and derives per-(bodypart,
center_mode) xlim / ylim from the pooled marginal distributions.

**Priya-approved strategy (2026-04-20):** `q00001_9999 + 40% symmetric pad,
rounded to nearest 5 px, clamped to legacy x-filter where applicable`.
Rationale: q001_999 + 20% pad was tested first and clipped density edges;
wider quantile + more padding frame density with comfortable margin without
including clear outliers.

**Legacy x-filter values** (verified from legacy notebooks this session):
- `jaw`:    `X_MIN, X_MAX = -80, 80` (from `20251117_DLC_analysis_jaw.ipynb`)
- `tongue`: `X_MIN, X_MAX = -175, 175` (from `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`)

**Final approved limits** (cohort-pooled, applied to `configs/defaults.yaml`
under `dlc_spatial.bodyparts.{bp}.per_center_mode`):

| bodypart | center_mode | xlim | ylim | x_range (pre-filter) |
|---|---|---|---|---|
| jaw | eye_midpoint | [-80, 80] | [195, 520] | [-80, 80] |
| nose | eye_midpoint | [-100, 95] | [100, 330] | — |
| L_whiskers_1 | eye_midpoint | [15, 135] | [55, 250] | — |
| L_whiskers_2 | eye_midpoint | [15, 165] | [145, 355] | — |
| L_whiskers_3 | eye_midpoint | [60, 165] | [75, 270] | — |
| R_whiskers_1 | eye_midpoint | [-140, -15] | [70, 235] | — |
| R_whiskers_2 | eye_midpoint | [-165, 0] | [155, 350] | — |
| R_whiskers_3 | eye_midpoint | [-185, -40] | [95, 265] | — |
| tongue | spout_midpoint | [-175, 175] | [-235, 225] | [-175, 175] |

Pre-existing `nose` and `jaw` `eye_midpoint` limits were single-session
estimates (PS46/20250307 + 25% margin, DECISIONS 2026-04-18) — superseded
by the cohort-pooled values.

### Sub-phase 4.5-G — Phase 5 plumbing fix + `x_range` support

**Bug fix.** [src/stroke_orofacial/dlc_spatial/pixel_bins.py](../src/stroke_orofacial/dlc_spatial/pixel_bins.py)
and [src/stroke_orofacial/dlc_spatial/heatmaps.py](../src/stroke_orofacial/dlc_spatial/heatmaps.py):
added `center_mode` kwarg to `build_histogram`, `build_stats_grid`, and
`plot_heatmap`. When provided, these functions now read
`config.bodyparts.{bp}.per_center_mode.{mode}` for xlim, ylim, and (new)
`x_range`. Explicit kwargs still override. Added `_get_per_center_mode_params`
helper for consistent lookup across the module.

**`x_range` pre-histogram filter.** `config.bodyparts.{bp}.per_center_mode.{mode}.x_range`
is now plumbed through `get_masked_xy` (which already supported `x_range`).
The Phase 6 `reward_aligned.py` hack that injected `apply_x_range` / `x_range`
into the top-level config was removed; it now uses the new `x_range` kwarg
on `build_histogram` directly. Phase 6 reward-aligned `x_range` (under
`dlc_spatial_reward_aligned.bodyparts.{bp}.x_range`) takes precedence over
Phase 5 `per_center_mode.x_range` when both are set — preserving Phase 6
behavior.

**Y-axis inversion.** `plot_heatmap` now calls `ax.invert_yaxis()` so
rendered plots match camera-video convention (higher y = lower on screen).
Existing Phase 5 blank output did not reflect y orientation at all; new
output does.

**Deprecated top-level x_range.** `config.apply_x_range` / `config.x_range`
still consulted as fallback but marked deprecated in the config comment.

**New tests.**
- `tests/test_pixel_bins.py::TestGetPerCenterModeParams` (5 cases).
- `tests/test_pixel_bins.py::TestBuildHistogramCenterMode` (4 cases).
- `tests/test_pixel_bins.py::TestBuildStatsGridCenterMode` (1 case).
- `tests/test_heatmaps.py::TestPlotHeatmapCenterMode` (2 cases).

**Phase 5 output regeneration required.** The single existing Phase 5 PNG
(nose_nose/PS46/20250307, blank under the bug) re-renders correctly after
the fix. Verified by a one-shot re-render script; produces a non-blank
heatmap with density at (0, 0) inside `[-150, 150]` × `[-120, 130]` limits.
Next cohort-wide Phase 5 run (when Priya re-executes notebook 11) will
supersede all existing `*_nose.png` outputs. **Existing on-disk PNGs are
NOT parity-equivalent under the new code** — this is the intentional bug
fix, not a regression.

### Sub-phase 4.5-H — Notebook 11 wire-up

[notebooks/11_dlc_spatial_whole_session.ipynb](../notebooks/11_dlc_spatial_whole_session.ipynb)
passes `center_mode=center_mode` to both `plot_heatmap` and `build_stats_grid`.
One-line-per-call change. Tongue-offset concern for the future all-bodyparts
overlay (DECISIONS 2026-04-18 "all bodyparts overlay heatmap design") is
untouched; deferred to Phase 5.x as noted.

### Sub-phase 4.5-I — Investigation notebook + outputs

[notebooks/experiments/phase_4.5_lite_axis_limits.ipynb](../notebooks/experiments/phase_4.5_lite_axis_limits.ipynb)
captures the full pooling + comparison + proposal pipeline. Outputs at
[notebooks/experiments/outputs/phase_4.5_lite_axis_limits/](../notebooks/experiments/outputs/phase_4.5_lite_axis_limits/):
- `approved_{bp}_{center_mode}.png` (9 files): pooled heatmap with the
  approved xlim/ylim rectangle overlay.
- `cropping_comparison_{bp}.png` (9 files): 5-panel side-by-side showing
  different quantile/pad strategies.
- `pooled_candidates_{bp}.png` (9 files): pooled heatmap with all
  candidate rectangle overlays.
- `filter_impact_{jaw,tongue}.png` (2 files): unfiltered vs `x_range`-filtered.
- `candidate_limits_table.csv`, `proposed_limits_final.csv`: tabular outputs.

### Intentional behavior differences vs. pre-4.5-lite

1. **Phase 5 heatmap bug fix.** Pre-4.5-lite Phase 5 heatmaps used hardcoded
   `x_limits=(-200, 200)` / `y_limits=(50, 550)` which for centered data
   produces blank plots. Post-4.5-lite heatmaps consume per-(bodypart,
   center_mode) limits from config. Existing nose_nose/PS46 Phase 5 PNG
   on disk is blank and will be replaced by a correct non-blank plot on
   next notebook 11 run.
2. **Y-axis inversion.** `plot_heatmap` output flipped to camera-video
   convention (higher y = lower on plot).
3. **`x_range` filter now active for jaw and tongue.** Phase 5 whole-session
   heatmaps for jaw (under eye_midpoint) and tongue (under spout_midpoint)
   will drop DLC mis-detections outside `[-80, 80]` / `[-175, 175]`
   respectively. Phase 6 reward-aligned `tongue.x_range` (under
   `dlc_spatial_reward_aligned`, `[-150, 150]`) takes precedence when set.
4. **Per-bodypart default `center_mode`** exposes sweep-experiment winners
   as metadata. Downstream consumers (Phase 9) read via
   `config_loader.default_center_mode()`; Phase 5/6 notebooks continue
   iterating their own `CENTER_MODES` lists (no behavior change there).

### What is NOT changed

- `compute_center()`, `apply_centering()`, `_median_from_lik()` untouched.
- Existing centered parquet outputs (PS46/20250307 all 3 modes) byte-identical.
- Phase 4 hash baseline preserved (`c23dc714` / `2a6efb6a` / `b13af51c`).
- `docs/DESIGN.md`: no edit.
- `docs/DECISIONS.md`: 2026-04-19 Phase 4.5-lite entry already correctly
  described the intended implementation.

### Cross-references

- DECISIONS 2026-04-19 "Phase 4.5-lite decision: eye-midpoint centering,
  no similarity/rigid transform" (the green-light).
- DECISIONS 2026-04-18 "Plot axis limits must be per-(bodypart, center_mode)"
  (the principle; this phase finally makes the code consume those limits).
- Sweep experiment at `notebooks/experiments/cross_session_alignment_sweep.ipynb`
  + outputs at `notebooks/experiments/outputs/alignment_sweep/` (the data).
- Legacy x-filter values verified in
  `//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/20251117_DLC_analysis_jaw.ipynb`
  (jaw ±80) and `.../20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`
  (tongue ±175).

### Exit criteria met

- [x] 219 pytest pass + 28 skipped (adds 14 new tests: 6 config_loader, 6
  pixel_bins, 2 heatmaps).
- [x] `ruff check` clean on all changed files.
- [x] `scripts/hash_centered_parquets.py` exits 0; Phase 4 param_sig hashes
  preserved.
- [x] PS46/20250307 re-render proves Phase 5 bug fix produces non-blank output.
- [x] Investigation notebook executes end-to-end and emits the final
  proposal CSV matching the applied config values.
- [x] Fiducial bodypart blocks present and loadable.
- [x] Notebook 12 CENTER_MODES includes eye_midpoint.

### Deferred / noted for follow-up

- **All-bodyparts overlay tongue-offset**: future Phase 5.x (DECISIONS
  2026-04-18) must handle tongue in spout-centered frame being offset
  from jaw/nose/whiskers in eye-centered frame when co-plotting. Candidate
  solutions (translate tongue by cohort-mean `spout_mid - eye_mid`, render
  tongue in its own panel, or re-center tongue on eye_midpoint for overlay)
  to be decided when that phase starts.
- **Cohort-wide Phase 5 re-run**: required after Gate 2 for any future
  Phase 5 outputs. Existing `nose_nose/PS46/heatmap_20250307.png` is the
  only Phase 5 PNG on disk and is blank under the bug; delete or overwrite.
- **Fiducial `per_center_mode` blocks**: left null since no Phase 5/6
  heatmaps for fiducials. Phase 9 null-baseline stats read fiducials from
  raw parquets directly, not from heatmap outputs.
- **Phase 6 reward-aligned code path re-test**: the reward_aligned.py
  refactor removed a config-injection hack. `test_reward_aligned.py`
  passed (5 tests; 2 skipped for missing data). Live-data re-run on PS46
  recommended once Priya re-executes notebook 12.
- **Image-boundary clamping for per-(bodypart, center_mode) axis limits**
  (2026-04-20 review): the approved `q00001_9999 + 40% pad` limits are
  clamped to legacy x-filter ranges where applicable (`jaw [-80, 80]`,
  `tongue [-175, 175]`) but not to the raw image frame. For some
  bodyparts (notably tongue `ylim=[-235, 225]` under spout_midpoint),
  the +40% pad extends into centered-frame regions that map past the
  image edge for some sessions — rendered as harmless white space but
  technically not a region where data could exist. Fix options (park for
  future Phase 5.x polish mini-phase):
  - (A) Add image dims to `configs/defaults.yaml` and clamp at plot time
    using per-session midpoint offsets.
  - (B) Cohort-conservative fixed clamp derived from min-across-sessions
    of `(image_edge − session_midpoint)`.
  - (C) Manual per-bodypart `ylim` override in config for the 1-3
    affected combinations (simplest).
  Priya (2026-04-20) elected to defer to Phase 5.x polish and will decide
  between option C (manual override) and option A at that time.

### Post-merge validation (2026-04-20, post-PR-#33-merge)

Both follow-ups from the "Deferred / noted" block above executed on branch
`phase-4.5-lite-post-merge-validation` (off main at `685d3f7`) to confirm
nothing regressed after the Gate 2 API refactor.

**Followup 1 — Cohort-wide Phase 5 re-run.** Deleted the single pre-fix
blank PNG at `spatial_whole_session/nose_nose/PS46/heatmap_20250307.png`
and executed `notebooks/11_dlc_spatial_whole_session.ipynb` via
`jupyter nbconvert --execute --inplace`. Parquets for the other 7 animals
and other PS46 dates are not yet built (confirmed by Phase 4.5-E hash
script), so the effective re-run scope was PS46/20250307 × 3 bodyparts
(nose/jaw/tongue) × 3 center_modes (nose/spout_midpoint/eye_midpoint) =
9 `(bodypart, center_mode)` combinations, producing 9 PNGs + 9
`stats_grid` NPZs. All 18 outputs non-blank; the previously-blank
`nose_nose/PS46` re-rendered as a correct nose-centered density at
`(0, 0)` within `xlim=[-150, 150]`, `ylim=[-120, 130]`, camera-view
y-inversion applied. Full re-run baseline:

| combination | file | sha256[:12] | size (KB) |
|---|---|---|---|
| jaw_eye_midpoint | PS46/heatmap_20250307.png | 7f7d855214bf | 53.9 |
| jaw_eye_midpoint | PS46/stats_grid_20250307.npz | 3e866674fe56 | 2.7 |
| jaw_nose | PS46/heatmap_20250307.png | 38bf72585eb2 | 44.6 |
| jaw_nose | PS46/stats_grid_20250307.npz | 4956a43d3d46 | 2.9 |
| jaw_spout_midpoint | PS46/heatmap_20250307.png | 15394b0028f5 | 45.9 |
| jaw_spout_midpoint | PS46/stats_grid_20250307.npz | 93f9e39f12d8 | 2.9 |
| nose_eye_midpoint | PS46/heatmap_20250307.png | 24834e920388 | 48.4 |
| nose_eye_midpoint | PS46/stats_grid_20250307.npz | 79edfe96d17e | 2.4 |
| nose_nose | PS46/heatmap_20250307.png | 5caf3a348f9c | 42.9 |
| nose_nose | PS46/stats_grid_20250307.npz | 76f953ea8f8f | 2.4 |
| nose_spout_midpoint | PS46/heatmap_20250307.png | 633c25a7ad1e | 46.9 |
| nose_spout_midpoint | PS46/stats_grid_20250307.npz | 62ec7c54f97d | 2.4 |
| tongue_eye_midpoint | PS46/heatmap_20250307.png | b0d99b3a11de | 49.3 |
| tongue_eye_midpoint | PS46/stats_grid_20250307.npz | 4838328575d3 | 6.0 |
| tongue_nose | PS46/heatmap_20250307.png | 99d5d55ecc6d | 49.5 |
| tongue_nose | PS46/stats_grid_20250307.npz | 500e3682ee9c | 6.0 |
| tongue_spout_midpoint | PS46/heatmap_20250307.png | 6c156a7947b5 | 52.8 |
| tongue_spout_midpoint | PS46/stats_grid_20250307.npz | 83dd84f530ed | 3.6 |

No regressions observed. The previously-good `nose_nose` PNG was blank
under the pre-4.5-lite bug (not truly good), so the regression-detection
logic ("any combination that was good and is now broken") had no broken
referents to check against.

**Followup 2 — Phase 6 reward_aligned live-data re-test.** Called
`build_reward_aligned_analysis` directly on PS46/20250307 with
`window_ms=(-500, 5000)`, `trial_group="all"` (96 rewards, 132,096
selected frames) for the two reference combinations in Phase 6 §6d, and
compared histogram counts to the recorded baselines:

| combination | center_mode | counts (post-4.5-lite) | baseline (Phase 6 §6d) | status |
|---|---|---|---|---|
| tongue | nose | 54,159 | 54,159 | MATCH |
| nose   | nose | 132,053 | 132,053 | MATCH |
| tongue | spout_midpoint | 54,159 | — | recorded as new baseline |

All rewards / selected_frame counts also match (96 / 132,096).
Histogram-bin fill percentages differ across center_modes because the
per-(bodypart, center_mode) `xlim` / `ylim` / `x_range` are different
frames, but total counts are invariant under the API refactor — exactly
as expected for a pure plumbing change.

Additionally smoke-tested `notebooks/12_dlc_spatial_reward_aligned.ipynb`
via `jupyter nbconvert --execute --inplace`. Exit 0, 54 new Phase 6
reward-aligned PNGs on disk (3 bodyparts × 3 center_modes × 2 windows ×
3 trial_groups).

**Conclusion.** Gate 2 API refactor preserved Phase 6 behavior at the
histogram level; the pre-existing Phase 5 blank-PNG bug is fixed; no
regressions. All "Deferred / noted" items from the main Phase 4.5-lite
entry are now closed except the Phase 5.x all-bodyparts overlay
(still future scope) and the fiducial `per_center_mode` blocks (still
intentionally null).

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

---

## Phase 13 — Env unification + bnpm vendoring

**Dates:** 2026-04-19 (env unification) → 2026-04-20 (bnpm vendoring).

**What was done:**

### Sub-phase 13a: Unified environment.yml
- Replaced the `environment-mac.yml` (`frsb`) + `environment-windows.yml`
  (`deeplabcut` placeholder) pair with a single `environment.yml` creating
  the `stroke_orofacial` env (Python 3.11, conda-forge primary).
- Runs PARALLEL to existing envs — `frsb` (Mac) and `deeplabcut` (Windows)
  are not touched; `deeplabcut` remains the DLC training / O2 inference /
  Keypoint-MoSeq env.
- Dep scope derived from a full import audit of `src/`, `tests/`,
  `notebooks/`, and every legacy notebook under
  `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`.
- Dropped (unused anywhere): `opencv-contrib-python`, `tqdm`.
- Added (in-flight ports reference them): `patsy`, `pot`, `scicomap`,
  `nbconvert`.
- Pinned the HDF5 stack to avoid silent ABI skew on Windows:
  `hdf5=1.14.*`, `pytables=3.10.*`, `h5py` unpinned (conda-forge resolves
  it), `pywavesurfer` installed post-env-create via
  `pip install pywavesurfer --no-deps` (its wheel pins `h5py==3.8.0` and
  would otherwise downgrade conda h5py to a PyPI wheel with its own
  hdf5.dll, colliding with pytables' conda hdf5.dll).
- `pyproject.toml` `[project.dependencies]` brought into agreement with
  `environment.yml` so `pip install -e .` produces an equivalent install.
- See docs/DECISIONS.md "2026-04-19 Phase 13 env unification" for the
  full channel / pin / exclusion rationale.
- On Windows, `conda env create -f environment.yml` defaults the env
  prefix to the per-user `C:\Users\<user>\.conda\envs\` rather than
  `C:\ProgramData\anaconda3\envs\` when the latter is write-locked to
  non-admin shells. This matches where `deeplabcut` already lives on
  Priya's Windows box and is user-writable (avoids perms-driven rebuild
  failures). Initial rebuild-from-scratch attempt against the
  ProgramData install hit `EnvironmentNotWritableError` and required an
  admin-shell `conda env remove` before the per-user rebuild succeeded
  cleanly.

### Sub-phase 13b: Vendor 4 bnpm helpers, drop bnpm / torch
- After 13a, pytest couldn't collect on Windows: `import bnpm.indexing`
  failed with `OSError: [WinError 127]` on `torch\lib\shm.dll` plus
  `OMP: Error #15: Initializing libomp.dll, but found libiomp5md.dll
  already initialized`. Root cause: bnpm unconditionally imports torch at
  module load, and PyPI torch 2.11.0 on Windows bundles Intel OpenMP
  (libiomp5md.dll) clashing with conda-forge MKL's LLVM OpenMP (libomp.dll).
- Usage audit showed the repo uses exactly four bnpm helpers, all pure
  numpy: `bnpm.indexing.{idx2bool, widen_bool_sparse, set_short_bool_to_low}`
  and `bnpm.timeSeries.simple_smooth`.
- Vendored all four into
  `src/stroke_orofacial/_utils/bool_indexing.py` under bnpm's MIT license
  (© 2021 RichieHakim; license text reproduced in the module docstring).
  `gaussian_smooth_1d` is a faithful 1-D reconstruction of
  `simple_smooth` using the same kernel formula from
  `bnpm.math_functions.gaussian` (`x = linspace(-5σ, 5σ, 7σ samples)`,
  `kernel = (1/(√2π σ)) exp(-0.5 (x/σ)²)`) with edge-normalized
  `np.convolve` (``mode='same'``).
- Updated `bouts.py` (10 callsites) and `wavesurfer_io.py` (1 callsite)
  to import from `stroke_orofacial._utils.bool_indexing`.
- Dropped `bnpm[core]` from both `environment.yml` and `pyproject.toml`.
  Also dropped `numba`, `llvmlite`, `cmake` from `environment.yml` —
  those were only in the env to dodge the `bnpm[core]` pip source-build
  path on Intel Mac.
- Added `tests/test_vendored_bool_indexing.py` with a mixed-strategy
  validation suite (see "Intentional behavior differences" below for why):
    * `idx2bool` (3 tests) and `gaussian_smooth_1d` (2 tests) are strict
      ports of bnpm 0.6.0; parity-tested against live bnpm via
      `pytest.importorskip("bnpm.indexing")` / `importorskip(
      "bnpm.timeSeries")`. Skip cleanly in the new (bnpm-less) env; run
      on any machine that still has bnpm installed (e.g. Priya's Mac
      `frsb` env, where all 5 pass).
    * `widen_bool_sparse` (3 tests) and `set_short_bool_to_low` (3 tests)
      intentionally diverge from bnpm 0.6.0 to fix two upstream bugs
      (described below); tested against hand-rolled expected outputs
      plus an independent Python-loop / `itertools.groupby` reference
      implementation. These tests are bnpm-free and always run.
- See docs/DECISIONS.md "2026-04-20 Phase 13 vendor bnpm" for the full
  decision trail.

**Intentional behavior differences vs. legacy:**

1. **`bnpm` is no longer a runtime dependency.** The four helpers we used
   are vendored; torch, numba, llvmlite, and cmake (all previously
   carried transitively via bnpm or as belt-and-suspenders for its
   source build) drop out. All legacy notebook code paths that imported
   torch ran inside the `deeplabcut` env, which is untouched.

2. **Two vendored helpers intentionally diverge from upstream bnpm 0.6.0
   (bug fixes, not parity).** Discovered while writing the parity tests;
   kept because they preserve *caller intent* (what `bouts.py` documents
   it wants) rather than upstream behavior. Concretely:
   - `widen_bool_sparse`: upstream iterates over **rising AND falling**
     edges of each True run and widens each edge by
     `[edge - n_before, edge + n_after + 1]`. Because the falling edge
     lives one position past the run's last True, the trailing side of
     every run overshoots by an extra `n_after + 1` samples relative to
     a "widen every True index" semantic. Vendored version widens every
     True index by `[i - n_before, i + n_after + 1]` (symmetric,
     idempotent).
   - `set_short_bool_to_low`: upstream hand-patches edge runs and
     appends `out.size - 1` (rather than `out.size`) as the closing
     falling-edge index for a trailing-True run. This **under-counts
     trailing runs by 1**, so e.g. a length-1 trailing True gets length
     `0` and is never flagged as short. Vendored version uses a
     padded-array diff that measures every run correctly.
   Strict ports (`idx2bool`, `gaussian_smooth_1d`) remain byte-/kernel-
   for-byte equivalent to bnpm 0.6.0.

3. **Measured drift vs. frozen session_processing3 baselines**
   (PS46/20250307, 3,610,000 samples per array, `tests/test_bouts.py`
   pipeline against `session_processing3/*.npz`):

   | Array             | Differing | Fraction  | Max run | First idx | Direction            |
   | ----------------- | --------- | --------- | ------- | --------- | -------------------- |
   | running_bouts     | 0         | 0         | —       | —         | identical            |
   | lick_bool_bad     | 2         | 5.54e-7   | 2       | 2727859   | ref=True → new=False |
   | quiet_bool        | 51        | 1.41e-5   | 1       | 50558     | ref=False → new=True |
   | peri_reward_bool  | 0         | 0         | —       | —         | identical            |

   Only the two arrays produced by code paths that call
   `widen_bool_sparse` / `set_short_bool_to_low` move. Running_bouts
   and peri_reward_bool (which do not use these helpers for any
   semantically-divergent case) are bit-identical to the legacy output.
   The 51 quiet_bool flips are isolated singletons scattered across the
   session — consistent with the upstream edge-run undercount bug firing
   once per short trailing True in the quiet-detection chain.

4. **Scope of affected downstream artifacts.** These bool masks are
   terminal outputs: no module under `src/stroke_orofacial/` reads
   them as input. The only writers are
   `src/stroke_orofacial/spout_behavior/session_processing.py`, which
   emits them into `stroke_orofacial_pipeline_outputs/spout_behavior/
   {grooming_bouts,quiet_bouts,peri_reward_periods}/{ANIMAL}/
   {YYYYMMDD}.npz`. The legacy `session_processing3/` outputs remain
   untouched (source data per CLAUDE.md); new outputs going forward use
   the corrected semantics. No Phase 3 / 4 / 5 / 6 artifact depends on
   these masks as input, so no regeneration cascade.

5. **Integration-test tolerances — two unrelated effects, un-lumped.**
   - `tests/test_timebase.py` `rtol` bumped `1e-10` → `1e-8` on the
     sample-index mapping. This is **numpy/scipy LAPACK drift**, not
     vendoring: `np.polyfit` + `scipy.interpolate.interp1d` in the
     alignment path produce ~1e-10 rel diff under the new env's LAPACK
     backend (numpy 1.24 → 2.4, scipy 1.15 → 1.17) relative to the
     frozen alignment template. Unrelated to the vendored helpers.
   - `tests/test_bouts.py` + `tests/test_session_processing.py` bool
     arrays now use a `bool_near_equal` helper (`max_frac=1e-4`). This
     is the **measured drift from the vendored bug fixes** (table in
     point 3 above). The tolerance sits ~7x above the worst observed
     mismatch (51/3.61M = 1.41e-5) to leave headroom for other sessions
     with similar shape but different run structures. It is not LAPACK
     jitter — the whole bouts pipeline runs at a hard-coded `Fs=1000.0`
     and never touches `polyfit` / `interp1d`.

6. **`pywavesurfer` moved from pyproject `dependencies` to manual
   post-env-create `pip install --no-deps`.** Env-migration collateral,
   not a vendoring effect: its wheel pins `h5py==3.8.0`, which pip
   would otherwise try to build from source on Python 3.11 (no matching
   wheel on PyPI), taking numpy's source build with it and failing on
   clang. The `--no-deps` policy was already documented in
   `environment.yml`; `pyproject.toml` just hadn't been updated to
   match.

7. **`wavesurfer_io.py` `float(Fs_in)` → `float(np.asarray(Fs_in).item())`.**
   Env-migration collateral: numpy 2.x removed implicit scalar coercion
   of 1-element ndarrays; pywavesurfer returns `AcquisitionSampleRate`
   as shape `(1,)`.

**Exit criteria:**
- [x] `conda env create -f environment.yml` succeeds on Mac.
- [x] `conda env create -f environment.yml` succeeds on Windows.
- [x] `pip install -e .` succeeds in the new env on both platforms.
- [x] `pip install pywavesurfer --no-deps` completes cleanly.
- [x] `pytest tests/` passes in the new env on Mac (223 passed / 6 skipped
  / 0 failures — 6 tests skip because `frsb` is the parity machine and the
  rest run and pass; when run inside `frsb` itself with bnpm still present,
  all 229 pass including the strict-port parity tests that use
  `pytest.importorskip`).
- [x] `pytest tests/` passes in the new env on Windows (201 passed /
  28 skipped / 0 failures — 22 pre-existing integration/real-data gates
  skip because no real data is mounted on Windows; 6 `pytest.importorskip(
  "bnpm.*")` strict-port parity gates skip cleanly because bnpm isn't
  installed in the new env; 5 divergent-port tests run and pass against
  their hand-rolled references; no torch DLL errors).
- [x] `environment-mac.yml` + `environment-windows.yml` stubs `git rm`-ed.
- [x] PR #31 merged to main as `d031486` and tagged
  `v0.7-phase-13-env-unification` (annotated, pushed). Feature branch
  `phase-13-env-unification` preserved on origin per CLAUDE.md §8.

## Phase 8a.7 — Per-session JSON writer + schema (criteria stubbed)

**Date:** 2026-04-20.

**What was done:**

- New module `src/stroke_orofacial/spout_behavior/endpoints_writer.py`
  defining `write_session_endpoints_json()` plus the
  `lick_bouts_to_endpoint_result()` adapter and three module-level
  constants: `SCHEMA_VERSION = "2.0.0"`,
  `CANONICAL_ENDPOINT_NAMES` (10-name frozenset), and two sentinel dicts
  (`CRITERIA_NOT_YET_COMPUTED_SENTINEL`,
  `INTER_SESSION_REQUIRES_COHORT_SENTINEL`).
- Schema 2.0.0 has three top-level blocks — `metadata`, `endpoints`,
  `criteria` — plus a top-level `schema_version` string. Every
  endpoint slot and every criteria slot is always present; absent
  computations land as explicit sentinel objects rather than `null` or
  missing keys, so downstream consumers (8a.7.5, 8a.8) can assert
  presence at the schema level.
- Caller passes the full 10-key `endpoints` dict; the writer validates
  strictly (missing or unknown keys → `ValueError`). Each value may be
  an `EndpointResult` (computed) or a sentinel dict (e.g.
  `INTER_SESSION_REQUIRES_COHORT_SENTINEL` for the per-animal
  cross-session metric, which is computed at the cohort-aggregation
  stage in a future phase). The four criteria sentinels are
  constructed internally from
  `criteria_slugs.all_new_slugs(defaults)` — caller does not pass
  them.
- `lick_bouts_to_endpoint_result()` adapts the
  `find_lick_bouts() → list[LickBout]` primitive into the uniform
  `EndpointResult` shape the writer expects. Bouts are binned into
  trials by `start_idx ∈ [reward_idx + window_seconds[0]*Fs,
  reward_idx + window_seconds[1]*Fs)` (half-open, matches
  `build_per_trial_records`'s window semantics). `per_session_aggregate`
  reports `n_bouts`, `mean_n_licks`, `mean_within_bout_ili_s`,
  `mean_bout_duration_s`, and `std_bouts_per_trial`;
  `per_trial_array` carries per-trial bout counts so downstream
  consumers can recompute alternative summary stats without re-running
  the primitive.
- NPZ provenance hashes are SHA-256 hex of full file bytes
  (`hashlib.sha256(path.read_bytes()).hexdigest()`); Phase 2 NPZs are
  small enough that one-shot reads are fine.
- Atomic write mirrors the
  `tempfile.TemporaryDirectory` + `Path.replace` idiom in
  `dlc_io/parquet.py:47-75` — temp file lands in the final output's
  parent directory so the rename is atomic on the same filesystem.
- 15 tests in `tests/test_endpoints_writer.py` cover schema
  round-trip, top-level / metadata / endpoints block shapes, criteria
  sentinel pattern (explicit assertion that values are the sentinel
  dict, never `None`), inter-session sentinel passthrough, hash
  determinism, hash-changes-on-byte-mutation, schema version,
  no-partial-on-exception atomic semantics, strict missing/unknown
  key validation, NaN preservation through `json.dumps(allow_nan=True)`,
  and the lick-bout adapter's empty-input + trial-binning behavior.

**Intentional behavior differences vs. legacy:**

1. **Schema 2.0.0 is a clean break from legacy
   `behavior_report_PS.py:report.json`.** Per the kickoff scoping
   decision Q6 (2026-04-20), the new writer emits to a parallel
   `spout_endpoints.json` file and the legacy `report.json`
   pathway stays byte-stable. The two files coexist; consumers choose
   per their needs. There is no parity test in 8a.7 — the schemas are
   structurally incompatible by design.

   Naming-wise, the kickoff originally called the new artifact
   `spout_endpoints_v2.json` and gave the config block / API kwargs the
   `_v2` suffix to disambiguate from the legacy `report.json`. In 8a.7
   we dropped the `_v2` everywhere — the new outputs land in their own
   tree (`pipeline_outputs/spout_behavior/endpoints/...`), the new
   config block lives under its own namespace
   (`spout_behavior.endpoints:` in `defaults.yaml`), and the new API
   kwarg (`endpoints_params=`) doesn't collide with anything legacy.
   Renamed in this PR: the `endpoints_v2:` block in `defaults.yaml`
   (now `endpoints:`); every `endpoints_v2_params=` callsite in 8a.2–
   8a.6 modules and tests (now `endpoints_params=`); the `V2_PARAMS`
   test fixture name (now `ENDPOINTS_PARAMS`); the docstring path
   examples in `criteria_slugs.py` and `endpoints_writer.py`. Frozen
   archaeology / kickoff docs under `docs/PHASE_8A_*.md` and
   `docs/prompts/phase-8a-*.md` retain the original `_v2` references
   as historical decision-trail context.

2. **Two endpoint slots ship as sentinels in 8a.7.** All four
   `criteria` values land as
   `{"status": "not_yet_computed", "port_scheduled_for": "8a.7.5"}`
   because C1–C4 production computation is not yet ported (verified by
   greps for `criteria_(1|2|3|4)|criteria_training_pass|...` returning
   only the `criteria_slugs.py` slug-bijection helpers and a docstring
   note in `endpoints_per_trial.py`). `inter_session_persistence`
   lands as `{"status": "requires_cohort_aggregation",
   "computed_at": "cohort_aggregation_stage"}` because it's a
   per-animal cross-session metric and the per-session writer stays a
   pure function of per-session inputs. Both sentinels are explicit
   dict objects, never `null` and never absent.

**Exit criteria:**
- [x] `pytest tests/test_endpoints_writer.py -v` → 15 passed.
- [x] `pytest -q` → 335 passed / 28 skipped (320 baseline + 15 new).
- [x] `ruff check src/stroke_orofacial/spout_behavior/endpoints_writer.py
  tests/test_endpoints_writer.py` → clean.
- [x] All four criteria slugs and the inter_session_persistence slot
  emit explicit sentinel dicts (not `null`) — verified by tests.
- [x] Implemented on feature branch `phase-8a-part3-json-writer` off
  main; pre-commit hook in `.githooks/pre-commit` blocks accidental
  commits to main per CLAUDE.md §1.8.

**Deferred to 8a.7.5:**
- Port C3 (per-trial first-correct-lick-present), C4 (per-trial
  correct/incorrect lick-count thresholds), C2 (per-session per-side
  C3∩C4 pass-fraction aggregator), C1 (multi-session C2 training-pass
  over consecutive sessions).
- Replace the four `criteria` sentinel dicts with computed values.
- Parity tests for C3/C4 per-trial booleans against legacy
  `behavior_report_PS.py:455-551` on PS46/20250307 (byte-identical for
  booleans, `1e-12` rtol for the C2/C1 boolean-count aggregates).

---

## Phase 8a.7.5 — Criteria hierarchy port (C3, C4, C2 computed; C1 stays cohort-aggregation sentinel)

**Date:** 2026-04-20.

**What was done:**

- New module `src/stroke_orofacial/spout_behavior/criteria.py` (~330
  lines incl. docstrings) ports the per-trial and per-session-per-side
  legacy pass-criteria from
  `docs/legacy_snippets/behavior_report_PS_455_551.py` (verbatim excerpt
  of `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/analysis/behavior_report/behavior_report_PS.py:385-565`)
  into pure-function compute entry points:
  - `compute_c3_first_correct_lick_present(trials, *, defaults)` — per-trial
    boolean; passes iff at least one correct-side (rewarded) lick falls in the
    C3 window (`[0, 2.0]` s post-reward).
  - `compute_c4_correct_lick_count_threshold(trials, *, defaults)` —
    per-trial boolean; passes iff `n_correct ≥ num_licks_correct_min` AND
    `n_incorrect ≤ num_licks_incorrect_max` in the C4 window (`[0, 2.5]` s).
    Fail-loud `ValueError` when a caller passes TrialRecords built with a
    narrower window than C4 requires.
  - `compute_c2_session_trial_pass_fraction_above_threshold(c3_block,
    c4_block, *, defaults)` — per-session per-side boolean + NaN-preserving
    fraction; passes iff the fraction of C3∩C4-passing trials meets
    `fraction_pass` (0.6 default). Zero-trial sides emit `NaN` fraction and
    `False` pass, matching legacy semantics.
  - `build_criteria_block(trials, *, defaults)` — single entry point
    returning the 3-key dict the writer's `criteria` parameter accepts
    (C3, C4, C2). C1 stays writer-owned.
- Per-side output shape:
  `{"per_side_per_trial_pass": {"L": [bool, ...], "R": [bool, ...]}}` for
  C3/C4; `{"per_side_pass", "per_side_fraction", "per_side_n_trials"}` for
  C2. Per-side lists preserve reward-index chronological order within side —
  byte-identical to the legacy iteration convention thanks to the stable sort
  in `build_per_trial_records`.
- `endpoints_writer.py` now takes a required `criteria: dict` parameter
  (3 caller-supplied slugs). The writer fills
  `criteria_training_pass_consecutive_sessions` (C1) internally with the
  existing `INTER_SESSION_REQUIRES_COHORT_SENTINEL`, aligning C1's sentinel
  vocabulary with `inter_session_persistence` per DECISIONS.md 2026-04-20
  §"8a.7.5 split from 8a.7". The 8a.7 `CRITERIA_NOT_YET_COMPUTED_SENTINEL`
  constant is retired (no longer emitted). Two new module-level constants —
  `CALLER_SUPPLIED_CRITERIA_SLUGS` (frozenset of 3) and
  `COHORT_AGGREGATED_CRITERIA_SLUG` (C1) — make the caller/writer split
  explicit. `metadata.phase` string bumped from `"8a.7"` to `"8a.7.5"` so
  artifacts are self-describing.
- New validator `_validate_criteria_keys` enforces: missing / unknown / extra
  keys raise `ValueError`; supplying the C1 slug in `criteria` raises
  explicitly (caller cannot override the writer-owned sentinel slot).
- `tests/test_criteria.py` (20 tests, ~460 lines) covers:
  - Synthetic unit tests for C3 (empty trials, correct-side lick in/out of
    window, half-open boundary, per-side chronological ordering), C4 (exact
    count threshold, one-below, incorrect-lick rejection, narrower-TrialRecord
    `ValueError`, config snapshot), C2 (empty sides, zero-trial side with
    other-side pass, fraction at/below threshold, C34 intersection).
  - Inline-reference parity — a numpy re-implementation of the legacy
    snippet's algorithm run on a hand-built 12-trial synthetic session,
    asserted dict-equal to the production `build_criteria_block` output.
    Covers boundary-inclusive / exclusive timing, single-side sessions, and
    empty sessions.
  - **Real-data parity on PS46/20250307** via the MICROSCOPE wavesurfer
    mount (Windows `\\research.files.med.harvard.edu\...\wavesurfer` or Mac
    `/Volumes/Neurobio/MICROSCOPE/Priya/.../wavesurfer`). Runs Phase-2
    `find_licks_and_rewards` → `build_per_trial_records(window=(0, 2.5))` →
    `build_criteria_block` → compares byte-identical with the inline
    reference re-run on the same raw `(lick_L, lick_R, reward_L, reward_R)`
    arrays. Skips gracefully when the mount is unreachable (mirrors
    `tests/test_bouts.py` integration-test convention).
- `tests/test_endpoints_writer.py` (21 tests) updates:
  - `writer_kwargs` fixture now carries a valid 3-slug `criteria` dict.
  - `test_metadata_block_complete` bumped to assert `phase == "8a.7.5"`.
  - `TestSentinels::test_criteria_block_sentinel_pattern` **replaced** with
    a new `TestCriteriaComputed` class asserting (a) caller-supplied C3/C4/C2
    blocks serialize byte-identical, (b) C1 is auto-filled with the cohort
    sentinel, and (c) all 4 criteria slugs are present. `test_inter_session_sentinel_passthrough` remains.
  - New `TestCriteriaValidation` class covers missing / unknown / C1-override
    / empty-dict rejection paths.
- Boundary-semantics audit: the legacy `bnpm.indexing.find_idx_within_eps`
  uses the same half-open `[v - eps[0], v + eps[1])` convention as the
  existing `_find_idx_within_eps` port at
  `src/stroke_orofacial/spout_behavior/bouts.py:236-254` and as
  `build_per_trial_records`. At integer Fs (1000 Hz), `int(round(w*Fs)) ==
  int(w*Fs)`, so the port introduces no boundary divergence from the
  snippet. Confirmed by the real-data PS46/20250307 parity test.

**Intentional behavior differences vs. legacy:**

1. **C1 stays a per-session-JSON sentinel.** The legacy
   `behavior_report_PS.py:549-551` computes C1 (training-pass over the last
   `num_consecutive_pass` sessions) inline after C2. In the consolidated
   pipeline, C1 is a multi-session quantity and is computed by a future
   cohort-aggregation stage that tracks which per-session JSONs it depends
   on. The per-session writer auto-emits the
   `{"status": "requires_cohort_aggregation", "computed_at": "cohort_aggregation_stage"}`
   sentinel for the C1 slot. This preserves the "JSON = pure function of
   this session's data" provenance contract (see DECISIONS.md 2026-04-20
   §"8a.7.5 split from 8a.7" for the full rationale).
2. **Per-side chronological list shape replaces the legacy per-trial-index
   dict shape.** Legacy emits
   `criteria_3[date][side][idx_reward] -> bool`; the new JSON emits
   `{"per_side_per_trial_pass": {"L": [bool, ...], "R": [bool, ...]}}` —
   semantically equivalent (same ordering, same booleans), more JSON-natural
   (no stringified integer keys), and byte-identical under the parity test.
3. **TrialRecord window contract.** The C4 compute function rejects any
   TrialRecord whose `window_seconds` is narrower than C4's window (legacy
   default `[0, 2.5]`). The legacy snippet never hit this condition because
   its input was always the raw `lick_idx[date][f"Lick_{side}"]` array (full
   session), not a pre-sliced trial buffer; the new code has pre-sliced
   buffers and fails loud rather than silently truncating — consistent with
   the Phase 13 vendoring policy.

No legacy-function bugs surfaced that required a Phase-13-style divergence.
The real-data PS46/20250307 parity passes byte-identical, so no DECISIONS.md
divergence-rationale entry is needed for this sub-phase.

**Exit criteria:**
- [x] `pytest tests/test_criteria.py -v` → 20 passed (includes the real-data
  PS46/20250307 parity test).
- [x] `pytest tests/test_endpoints_writer.py -v` → 21 passed.
- [x] `pytest -q` → 361 passed / 28 skipped (was 335 passed / 28 skipped
  after 8a.7; +26 new tests = +20 criteria + +6 writer).
- [x] `ruff check src/stroke_orofacial/spout_behavior/criteria.py
  src/stroke_orofacial/spout_behavior/endpoints_writer.py
  tests/test_criteria.py tests/test_endpoints_writer.py` → clean.
- [x] Per-trial C3 and C4 per-side boolean lists byte-identical to the legacy
  snippet's algorithm on PS46/20250307 (verified by
  `TestRealDataParityPS46_20250307`).
- [x] C2 per-session-per-side booleans byte-identical; per-side fractions
  exact-equal (integer-count ratios — no float tolerance needed).
- [x] C1 slot emitted as `requires_cohort_aggregation` sentinel, not
  caller-override-able.
- [x] Implemented on feature branch `phase-8a-part4-criteria-hierarchy`.

**Post-merge appendix (2026-04-20) — external bnpm parity finding:**

After PR #42 merged, an independent external-bnpm parity sweep (Mac-local
scratch script running the inline reference with bnpm 0.6.0's
`find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1
session each) found one Category 2 divergence at **PS50/20250324 trial
k=40, L side**. Reproducer: reward_idx = 3,422,003; C4 window (0, 2.5) s;
L licks in the window are [3,422,497, 3,422,906, 3,423,057, 3,423,239,
3,423,436]; window right edge 3,424,503 > last lick 3,423,436.
Root cause is an upstream bug in **bnpm 0.6.0 `find_idx_within_eps`**:
`np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr) = 26`
when the right edge is past every element, and the upstream implementation
clamps to `len(arr) - 1 = 25`, which excludes `arr[25]` — the final lick.
Production (`criteria.py:_sub_window_counts` using
`(licks >= lo) & (licks < hi)` on pre-windowed `TrialRecord.licks_*_indices_in_window`)
is correct and includes all 5 licks, so PS50's C4 L-side trial k=40
correctly passes. The PS46/20250307 parity that sub-phase 8a.7.5 gated on
remains byte-identical — this finding does not affect the sub-phase's exit
criteria. **Verdict:** intentional divergence from upstream bnpm under the
Phase 13 vendoring pattern (production untouched, correct; upstream wrong).
Captured as a new bullet under DECISIONS.md 2026-04-20 "Phase 8a
architecture" entry and guarded by
`tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`.
PS51/20250502 re-run skipped (not needed for triage). Upstream bnpm issue
filing is deferred / optional. **Forward obligation:** the same clamp bug
exists in the private `_find_idx_within_eps` port at
`src/stroke_orofacial/spout_behavior/bouts.py:236-256` (peri-reward mask
caller); it does not affect criteria.py (which never calls it), but a
Phase-13-pattern fix-PR will follow the Phase 5/6 indexing-module refactor
(`_find_idx_within_eps` → `_utils/indexing.py`) and must land before Phase
5/6 code writes begin so Phase 5/6 does not consume the buggy helper.

---

## Phase 5/6-prep — Factor `_find_idx_within_eps` into shared `_utils/indexing.py`

**Date:** 2026-04-20.

**What was done:**
- Created new package-private module
  `src/stroke_orofacial/_utils/indexing.py` (~35 lines incl. docstring) as
  the home for sorted-array / integer-index utilities that complement the
  boolean-mask helpers already in
  `src/stroke_orofacial/_utils/bool_indexing.py`. Module split is by return
  type (bool mask vs. integer index array), not provenance.
- Moved `_find_idx_within_eps` verbatim from
  `src/stroke_orofacial/spout_behavior/bouts.py:236-256` into the new
  module. The function keeps its underscore prefix (still package-private)
  and its original docstring; implementation is byte-identical to the prior
  location — no behavior change in this refactor.
- Updated `bouts.py` to import `_find_idx_within_eps` from
  `stroke_orofacial._utils.indexing`. Two caller sites inside `bouts.py`
  (`find_peri_reward_periods`, `_make_peri_event_bool`) unchanged.

**Motivation:** Phase 5/6 (reward-aligned kinematics / DLC peri-reward
windows, including 8-s-post-reward windows used in later analyses) will
need the same sorted-array index helper without cross-importing from
`spout_behavior`. This preparatory refactor ahead of Phase 5/6 kickoff
keeps the Phase 5/6 PR focused on peri-reward extraction logic rather than
entangling it with a cross-module import change.

**Intentional behavior differences vs. legacy:** None. Pure move + import
rewrite; byte-identical parity expected against the prior `bouts.py`
callers.

**Forward obligation — clamp-bug fix before Phase 5/6 kickoff:** The
post-merge external bnpm 0.6.0 parity check documented in the DECISIONS
2026-04-20 "Phase 8a architecture" entry under the "External bnpm parity
finding — Phase-13-pattern intentional divergence from upstream bnpm 0.6.0
(post-merge of 8a.7.5)" bullet identified a `len(arr) - 1` right-edge
clamp bug inherited from the upstream `bnpm.indexing.find_idx_within_eps`
that this helper faithfully ports. The current refactor deliberately
preserves the bug (no behavior change in this PR — easier review). A
separate follow-up PR must land the clamp-bug fix **before** any Phase
5/6 implementation PRs begin, so Phase 5/6 peri-reward extraction does not
consume the buggy helper. That fix is a behavior change; its parity
implications will be re-verified against `tests/test_session_processing.py`
baselines under the Phase 13b `max_frac=1e-4` boolean-tolerance policy. A
regression guard for the "last lick inside sub-window with right edge past
it" primitive path already landed in
`tests/test_criteria.py::TestClampBugRegressionGuards` via the docs+test
PR on `docs/8a.7.5-external-bnpm-parity-findings`.

**Exit criteria:**
- [ ] `pytest tests/test_bouts.py -v` byte-identical pass.
- [ ] `pytest tests/test_session_processing.py -v` byte-identical pass.
- [ ] `ruff check src/stroke_orofacial/_utils/indexing.py
  src/stroke_orofacial/spout_behavior/bouts.py tests/test_bouts.py
  tests/test_session_processing.py` clean.
- [ ] Implemented on feature branch `prep-indexing-module-for-phase-5-6`
  cut from `main`.

---

## Clamp-fix for `_utils/indexing.py:_find_idx_within_eps` — right-edge clamp removed

**Date:** 2026-04-20.

**What was done:**
- Removed the two `il = min(max(0, il), len(arr) - 1)` and
  `ir = min(max(0, ir), len(arr) - 1)` clamp lines from
  `_find_idx_within_eps` in `src/stroke_orofacial/_utils/indexing.py`.
  `np.searchsorted` returns values in `[0, len(arr)]` and `np.arange(il,
  ir)` handles both endpoints at `len(arr)` correctly: the empty-range
  case (window entirely past `arr[-1]`) yields `np.arange(n, n) == []`
  and the overhanging-window case yields the full tail
  `np.arange(il, n)` that includes `arr[-1]`.
- Expanded the module-level docstring with a new
  "Intentional divergence from upstream bnpm 0.6.0 — right-edge clamp
  bug" section explaining the bug, the production reproducer
  (PS50/20250324 trial k=40), and the cross-reference to the regression
  guards in `tests/test_criteria.py::TestClampBugRegressionGuards` and
  the new mirror-in-minimum tests in `tests/test_indexing.py`.
- Expanded the `_find_idx_within_eps` docstring with a
  "Right-edge (no-clamp) semantics" note describing the
  `np.searchsorted(..., side="left") == len(arr)` path and a
  "Lower-bound subtlety (latent, not fixed here)" note flagging the
  `side="right"` strict-greater-than behavior at the lower bound as an
  out-of-scope follow-up (see below).
- Added `tests/test_indexing.py` (~210 lines) mirroring the
  divergent-port test pattern from `tests/test_vendored_bool_indexing.py`:
  hand-rolled clamp-bug regressions
  (`TestClampBugRegression::test_ps50_trial_40_reproducer` plus a
  synthetic minimal case and a "right edge exactly at last element"
  sanity check confirming the un-clamped path still excludes the
  boundary value), edge cases (empty arr, empty vals, window
  before/after arr, single-element arr inside / past-end, multi-val
  concatenation), and random-input parity (500 sorted-int arr × 50 vals
  × four `eps` variants, plus a construction that forces the right edge
  past `arr[-1]` on every trial) against an independent numpy-mask
  reference `_reference_find_idx_within_eps` using
  `(arr > lo) & (arr < hi)` — matches the open-at-lower / strict-below-
  upper convention and has no clamp, so it is always correct at the
  right edge.

**Motivation:** Closes the forward obligation set in the immediately-
preceding "Phase 5/6-prep" entry above and in the DECISIONS.md 2026-04-20
"External bnpm parity finding — Phase-13-pattern intentional divergence
from upstream bnpm 0.6.0 (post-merge of 8a.7.5)" bullet. Phase 5/6
peri-reward extraction (8-s-post-reward windows over kinematic and DLC
streams) routinely hits the overhanging-window path near session-end
licks; consuming the un-fixed helper would carry the
`arr[-1]`-dropping bug into reward-aligned downstream analyses. Landing
the fix on a separate PR (rather than folding it into the Phase 5/6-prep
move) keeps the diff scoped and reviewable: the move PR is byte-
identical, this PR is the behavior change.

**Intentional behavior differences vs. legacy:**
- vs. legacy `bouts.py:236-256` (pre-Phase 5/6-prep) and vs. upstream
  `bnpm.indexing.find_idx_within_eps` 0.6.0: when
  `v + eps[1] > arr[-1]` for some `v` in `vals`, the returned index
  array now includes `len(arr) - 1` (i.e., `arr[-1]`) where previously
  it was clamped out. The PS50/20250324 trial k=40 reward path is the
  canonical reproducer: pre-fix returned 4 indices (`[0, 1, 2, 3]`),
  post-fix returns 5 (`[0, 1, 2, 3, 4]`).
- All other paths (window strictly before arr, window strictly after
  arr's end, window strictly inside arr, empty arr, empty vals,
  multi-val concatenation, lower-bound `side="right"` strict-greater
  semantics) are byte-identical to the pre-fix implementation. The
  random-parity tests in `TestRandomParity::test_random_inputs_match_reference`
  cover these paths and pass against the same numpy-mask reference both
  before and after the change — the only diverging path is the
  right-edge overhang, which is exactly the targeted fix.

**Measured parity drift vs. `session_processing3` baselines:**
- _PS46/20250307 (frozen baseline animal-session, no licks at the
  right-edge overhang path):_ **Zero drift.**
  `tests/test_session_processing.py::TestIntegrationParity::test_parity[20250307]`
  passes byte-identical against the `session_processing3` baseline
  post-fix — no tolerance fallback needed (pass predates the Phase 13b
  `max_frac=1e-4` allowance). Confirmed 2026-04-20 on Mac
  (`fix/indexing-find-idx-within-eps-clamp-bug` @ pre-commit tree), full
  impact-set run: 58/58 pass, 4 unrelated pre-existing pywavesurfer
  file-version warnings. This matches the pre-fix prediction that PS46's
  lick array does not exhibit the overhanging-window pattern (no licks
  beyond the last reward's post-window), so the code path being altered
  is never taken on this session.
- _PS50/20250324 (right-edge overhang animal-session, trial k=40 path):_
  Drift expected and intentional — `per_side_per_trial_pass["L"]`
  flips from `[False]` to `[True]` for this trial, propagating to the
  C2 fraction-pass count and the C4 lick-count threshold. Already
  guarded by
  `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`
  via the prior docs+test PR.

**Exit criteria:**
- [ ] `pytest tests/test_indexing.py -v` — all tests pass (new file).
- [ ] `pytest tests/test_criteria.py -v` — all tests pass, including
  the pre-existing `TestClampBugRegressionGuards`.
- [ ] `pytest tests/test_bouts.py -v` — pass; only behavior change
  affects the right-edge overhang path which the bouts caller does not
  exercise on existing fixtures (verify byte-identical).
- [ ] `pytest tests/test_session_processing.py -v` — pass under the
  Phase 13b `max_frac=1e-4` boolean tolerance policy, with measured
  drift recorded in this entry.
- [ ] `ruff check src/stroke_orofacial/_utils/indexing.py
  tests/test_indexing.py` clean.
- [ ] Implemented on feature branch
  `fix/indexing-find-idx-within-eps-clamp-bug` cut from `main` (post
  Phase 5/6-prep merge, commit 92b5d88).

**Out-of-scope follow-ups (deliberately not in this PR):**
- The `side="right"` lower-bound semantics enforce strict
  `arr[i] > v - eps[0]` rather than the half-open
  `[v - eps[0], v + eps[1])` window the upstream docstring implies.
  This is a latent docstring/code mismatch inherited from upstream
  bnpm; it only matters when an `arr` element exactly equals
  `v - eps[0]` (rare in production lick/reward index arrays). Flagged
  in the function docstring; investigation deferred. If a later phase
  needs the half-open convention, the fix is a one-line
  `side="right"` → `side="left"` swap at the lower bound, plus
  expanded `TestClampBugRegression` coverage and a parity re-run.
- Optional upstream bnpm issue filing for the right-edge clamp bug
  remains deferred / Priya's call.
