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
