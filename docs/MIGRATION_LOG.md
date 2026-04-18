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

**What was done:**

### Sub-phase 2a: Wavesurfer I/O + treadmill calibration
- Implemented `src/stroke_orofacial/spout_behavior/wavesurfer_io.py`:
  `load_wavesurfer_signals()`, `find_wavesurfer_file()`, `calibrate_treadmill()`,
  `smooth_treadmill()`, `resolve_treadmill_offset()`.
- Ported from `process_ws_signals.py` (only version) and
  `calibrate_and_smooth_treadmill_signal_PS.py` (confirmed canonical by Priya;
  Rule 3 resolved).
- Added `configs/paths.yaml`: `microscope_pipeline_outputs`,
  `wavesurfer_raw` (list mount: MICROSCOPE primary, Mac-local fallback).
- Added `configs/session_overrides.yaml` with per-session treadmill offset
  overrides (moved from `defaults.yaml`).
- Added `configs/defaults.yaml` with all cohort-wide params from legacy
  `params.json`.
- Updated `PathResolver`: list-mount support, `pipeline_outputs()`,
  `wavesurfer_dir()`.
- Added `bnpm` and `pywavesurfer` to `pyproject.toml` dependencies.

### Sub-phase 2b: Lick detection + reward detection
- Implemented `src/stroke_orofacial/spout_behavior/lick_detection.py`:
  `find_licks_and_rewards()` (main entry), `find_reward_indices()`,
  double-threshold lick detection with lockout cleaning.
- Ported from `find_licks_and_rewards.py` (only version).
- Parity verified: PS46/20250307 lick and reward indices match
  `session_processing3/` exactly.

### Sub-phase 2c: Bout detection
- Implemented `src/stroke_orofacial/spout_behavior/bouts.py`:
  `find_running_bouts()`, `find_grooming_bouts()`, `find_quiet_bouts()`,
  `find_peri_reward_periods()`.
- Ported from 4 legacy modules (all only-version, Rule 1 trivially resolved).
- Parity verified: all 5 bout/treadmill outputs match `session_processing3/`
  for PS46/20250307.

### Sub-phase 2d: Session orchestrator + notebook + parity check
- Implemented `src/stroke_orofacial/spout_behavior/session_processing.py`:
  `process_session()`, `process_animal()`.
- Created `src/stroke_orofacial/config_loader.py`: `load_defaults()`,
  `load_session_overrides()`, `get_session_params()` (deep-merge),
  `check_merge_required()`.
- Created `notebooks/00_session_processing.ipynb` (thin orchestrator).
- Overwrite protection: "skip" (default), "prompt", "force" modes.
- Outputs written to `pipeline_outputs_v2/spout_behavior/` on MICROSCOPE.

**Parity verified** on two sessions (11 arrays each, all exact):
- PS46 / 2025-03-07 (baseline, day -6): 11/11 PASS
- PS46 / 2025-03-20 (post-stroke, day +7): 11/11 PASS

**Intentional behavior differences vs. legacy `session_processing3/`:**

1. **Per-session params.json** instead of root-level.
   Legacy `session_processing3/` has a single `params.json` at the root.
   The new pipeline writes per-session files at
   `params/{animal}/{YYYYMMDD}.json`, each containing:
   - `session_id`, `animal`, `date`, `run_timestamp`
   - `skipped` (bool)
   - `params` (the merged defaults + session_overrides actually used)
   - `processing_log` (skip/overwrite decisions per output type)

2. **params.json always written, even on skip.**
   When `overwrite="skip"` and all outputs already exist, the per-session
   `params.json` is still written with `skipped: true` and the log of which
   outputs were skipped. This provides a complete audit trail of what ran,
   what was skipped, and when.

3. **Per-session overrides via `session_overrides.yaml`** instead of inline
   `offset_overrides` dict. Treadmill offset overrides for PS51/PS54/PS55
   now live in `configs/session_overrides.yaml` under a structured
   `overrides:` key, not inside `defaults.yaml`.

4. **Output location moved to MICROSCOPE** server at
   `pipeline_outputs_v2/spout_behavior/` instead of Mac-local
   `session_processing3/`.

5. **Cross-platform wavesurfer path support.** `wavesurfer_raw` logical root
   tries MICROSCOPE first, falls back to Mac-local. Pipeline currently runs
   from Mac using the local fallback; will run from Windows once Priya rsyncs
   the wavesurfer data to MICROSCOPE (separate task).

**Exit criteria met:**
- [x] `pytest tests/` passes (88 tests).
- [x] `ruff check src/` clean.
- [x] Parity verified on PS46 baseline + post-stroke sessions.
