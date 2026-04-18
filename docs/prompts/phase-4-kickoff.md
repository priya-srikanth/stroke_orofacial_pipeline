# Phase 4 Kickoff — DLC I/O + Centering

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-4-kickoff.md` and follow the instructions in full.

---

## Context

Phase 4 per `docs/DESIGN.md` §7: port the DeepLabCut output loading, filtering,
centering, and parquet-writing pipeline into `src/stroke_orofacial/dlc_io/` +
`notebooks/10_dlc_build_parquets.ipynb`. Phase 4 is **I/O + centering only for
whole-session parquets**; the reward-aligned / trial-windowed variants are
Phase 6 scope.

Consumes: DLC inference H5/CSV outputs at
`/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/{animal}/` (read-only)
and `AlignmentResult` from Phase 3 (if coordinate transforms need session
timing).

Produces: centered parquet files at
`/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/dlc_analysis/` on
MICROSCOPE.

Parity: existing centered parquets already exist on MICROSCOPE (from the
legacy pipeline's runs). Match their schemas exactly and diff on a sample
session before closing.

## Before anything else

Re-read these in full and confirm in one sentence that the data-safety and
git constraints are internalized:

- `CLAUDE.md` — full file. Pay particular attention to the new "Phase plan
  requirements" section (dead code identification step — this is the first
  phase where it applies).
- `docs/DESIGN.md` §3 (repo layout), §5 (notebook → module migration map —
  note the Phase 4 entry for `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`
  and related), §7 Phase 4, §7 Phase 6 (to understand where reward-alignment
  logic will later plug in).
- `docs/MIGRATION_LOG.md` Phases 0-3 (so you know what exists and can build
  on it, especially Phase 3's `SessionManifest` fields and `AlignmentResult`).
- `docs/DECISIONS.md` — project-wide decisions.
- `configs/paths.yaml` — note the existing `dlc_output` derived path and the
  structure of per-animal DLC outputs (Phase 1 established the convention).

## Branch setup

```bash
# Sync local main
git checkout main
git pull origin main

# Verify hook active in this clone
git config --get core.hooksPath   # must print: .githooks

# Create the branch off current main
git checkout -b phase-4-dlc-io

# Confirm
git branch --show-current          # must print: phase-4-dlc-io
```

All commits on `phase-4-dlc-io`. Before every commit, run
`git branch --show-current` and stop if it isn't `phase-4-dlc-io`.
The pre-commit hook will also refuse direct main commits.

## Plan mode — satisfy CLAUDE.md "Phase plan requirements"

Produce a plan in plan mode that includes all five required elements:

1. **Legacy file disambiguation** (3-tier rule) — inspect
   `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp/` (upstream) AND
   `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` (Priya fork)
   for all DLC-related notebooks and helpers. Also inspect
   `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` where Priya's DLC
   notebooks live. The plausibly-canonical Phase 4 source is
   `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` but confirm
   via Rule 1 (latest date). Note any older dated versions, `_v0`/`_mod`
   variants, `playground_*` notebooks, or undated sibling notebooks.
2. **Dead code identification** — NEW REQUIREMENT (per CLAUDE.md). For the
   canonical legacy notebook(s) and helpers:
   - Walk each notebook cell-by-cell, each `.py` file function-by-function.
   - Classify each as *Production* / *Exploratory* / *Deprecated* / *Ambiguous*.
   - Only *Production* items get ported.
   - Report the classification as a table in the plan.
   - *Ambiguous* items must STOP-and-ask Priya before the plan is finalized.
3. **Sub-phase breakdown** with per-file line estimates and dependency order.
4. **Parity strategy** — the existing centered parquets on MICROSCOPE are
   the reference. Which parquet(s) to compare against, which columns, what
   tolerances. Propose reading one existing parquet and diffing column-by-column.
5. **Hardcoded constants** — list anything (likelihood thresholds, centering
   reference points, body-part name lists, column name conventions, NaN
   handling policy, etc.) that should move to `configs/defaults.yaml`.

Wait for my explicit approval before writing any files.

## Expected scope (to seed plan mode, not prescriptive)

Likely shape of the ported modules:

- `src/stroke_orofacial/dlc_io/loaders.py` — load DLC H5/CSV → tidy DataFrame
  with columns `[frame_idx, bodypart, x, y, likelihood]`. Likelihood gating
  (drop low-confidence rows or replace with NaN per config). Support both
  `_filtered.h5` and `_filtered.csv` source formats (matching Phase 1's
  `SessionManifest.dlc_h5_files` and `.dlc_csv_files`).
- `src/stroke_orofacial/dlc_io/centering.py` — coordinate-frame transforms
  expressed as enums or functions: `center_on_nose()`, `center_on_spout_midpoint()`,
  `center_on_eyes_midpoint()`. Each takes the per-frame reference landmark(s)
  from the tidy DataFrame and returns a new DataFrame with re-origined
  `x_centered`, `y_centered` columns (plus retained raw `x`, `y` for
  traceability).
- `src/stroke_orofacial/dlc_io/parquet.py` — write/read the centered
  parquet format. Match the existing parquet schema exactly (column names,
  dtypes, multi-index structure if any). Include metadata columns for
  `session_id`, `centering_method`, `session_time_s` (from alignment).
- `notebooks/10_dlc_build_parquets.ipynb` — thin orchestrator with USER
  INPUTS cell (animal list, date range, centering method, overwrite mode).
- Overwrite protection (`"skip"` / `"prompt"` / `"force"`) matching Phase 2's
  convention, default `"skip"`. Per-session `params.json` at
  `pipeline_outputs_v2/dlc_analysis/params/{animal}/{YYYYMMDD}.json`.
- `SessionManifest` integration — `AlignmentResult` should be loadable by the
  orchestrator so each parquet can carry a `session_time_s` column. If the
  orchestrator doesn't need alignment for Phase 4's centering (centering is
  typically spatial-only, not time-aligned), mark this as deferred to Phase 6
  explicitly in the plan.

These are seeds for thinking, not a spec. The plan's sub-phases and file
layout should come from Claude Code's analysis of the canonical legacy
sources, not from this list.

## Constraints

- No modifications outside `~/Github/stroke_orofacial_pipeline/` except writes
  to `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/dlc_analysis/`.
- Both legacy repos (`facerhythm_stroke_biomarker_exp` and
  `facerhythm_stroke_biomarker_exp_Priya`) remain read-only.
- DLC inference outputs at `O2_analysis/{animal}/` are read-only.
- Camera data at `.../Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera/`
  is read-only (not expected to be needed in Phase 4 but noting for
  completeness).
- `session_processing3/` is read-only.
- `alignment_templates/` on MICROSCOPE is read-only.
- Existing centered parquets from the legacy pipeline (wherever they live on
  MICROSCOPE) are read-only references for parity checking — never
  overwritten.
- Pre-commit hook must not be bypassed with `--no-verify` without explicit
  Priya approval.
- Before every commit, `git branch --show-current` must print
  `phase-4-dlc-io`.

## Exit criteria

- Plan approved by Priya, then sub-phases executed with per-sub-phase commits.
- Parity check passes on at least one real session (PS46/20250307 is a good
  default since it's been used in Phases 2-3; use a different session if the
  parquet doesn't exist for that one).
- `SessionManifest.build_manifest()` compatible with (or extended for) DLC
  parquet outputs, if applicable.
- Tests pass, lint clean.
- `docs/MIGRATION_LOG.md` Phase 4 entry documents all sub-phases, legacy
  disambiguation, dead-code classification results, intentional behavior
  differences, and parity results.
- `docs/DECISIONS.md` gets new entries for any cross-cutting decisions made
  during Phase 4 execution.
- Pause after parity check (before tests+MIGRATION_LOG sub-phase) for Priya's
  mid-phase review, then again at the end before pushing for PR.

If anything in the design or the legacy sources is ambiguous, STOP and ask
Priya before writing code. Ambiguity in Phase 4 is expensive because the
parquet schema becomes the contract for every DLC analysis downstream.
