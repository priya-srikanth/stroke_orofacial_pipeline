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
