# Phase 3 Kickoff — Wavesurfer ↔ Video ↔ DLC Alignment

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-3-kickoff.md` and follow the instructions in full.

---

## Context

Port the alignment pipeline from legacy `batch_process_alignment_20251216PS.ipynb`
and its helper `make_alignment_templates_20251216.py` (which lives only in the
upstream legacy repo) into `src/stroke_orofacial/alignment/` plus
`notebooks/02_alignment.ipynb`. Outputs go to
`pipeline_outputs_v2/alignment/` on MICROSCOPE.

A detailed five-sub-phase plan (3a-3e) was drafted and approved during Phase 3
planning before the Phase 2.5 interlude. Execute that plan as written, with the
three amendments below.

## Before anything else

Re-read these files and confirm in one sentence that the data-safety and git
constraints are internalized:

- `CLAUDE.md` — full file (note the updated rule 2 covering both legacy repos,
  rule 8 with the pre-commit-hook requirement, and the
  disambiguation-policy section).
- `docs/DESIGN.md` §3 (repo layout), §4.4 (time-base / alignment contract),
  §7 Phase 3.
- `docs/MIGRATION_LOG.md` — Phases 0-2.5 (so you know what already exists and
  can build on it).
- `docs/DECISIONS.md` — project-wide decisions.

## Branch setup

The `phase-3-alignment` branch was created earlier but is stale (points at the
Phase 2 merge, before Phase 2.5 and the branch-protection hooks). Recreate
fresh off the current `main`:

```bash
# On main, sync
git checkout main
git pull origin main

# Verify the branch-protection hook is active in this clone
git config --get core.hooksPath   # must print: .githooks

# Delete the stale branch (nothing on it to lose)
git branch -d phase-3-alignment 2>/dev/null || git branch -D phase-3-alignment

# Create the new branch off current main
git checkout -b phase-3-alignment

# Confirm
git branch --show-current          # must print: phase-3-alignment
```

All subsequent commits MUST land on `phase-3-alignment`. Before each commit,
run `git branch --show-current` and stop if it isn't `phase-3-alignment`.
The pre-commit hook will refuse direct commits to `main` regardless, but the
check is a belt-and-suspenders discipline.

## Three amendments to the approved plan

1. **Parity tolerance for affine fit.** On sub-phase 3d, compare slope and
   intercept values with `np.allclose(rtol=1e-8, atol=0)` — looser than the
   `rtol=1e-10` applied to interpolated float arrays. This allows for
   tie-break differences in the pattern matcher without rejecting a correct
   port. Any mismatch on `idxCam_edges` / `idxWS_edges` (the matched-edge
   integer arrays) must be investigated and documented in `MIGRATION_LOG.md`,
   not silently accepted.

2. **Per-session `params.json` convention matches Phase 2.** Write a per-session
   params record at
   `pipeline_outputs_v2/alignment/params/{animal}/{YYYYMMDD}.json`.
   Contents mirror Phase 2d's: `session_id`, `animal`, `date`,
   `run_timestamp`, `skipped` flag, merged `params` actually used, and
   `processing_log` of skip/overwrite decisions. Write even when the session
   is skipped. No root-level cohort `params.json`.

3. **`SessionManifest` integration.** Phase 1 left
   `SessionManifest.wavesurfer_file` and `.video_files` as `None`/`[]`
   pending Phase 2/3 work. As part of sub-phase 3b or 3c, populate these
   fields from the alignment flow: `wavesurfer_file` from the wavesurfer_raw
   directory (same logic used by Phase 2's `find_wavesurfer_file()`),
   `video_files` from `camera_raw/{YYYYMMDD}/{animal}/video*.avi`. Add a test
   that `build_manifest("PS46", date(2025, 3, 7))` returns a `SessionManifest`
   with both fields populated (non-empty, resolving to real files).

## Execution — follow the approved plan

Sub-phases (from the previously approved plan):

- **3a:** Path setup + alignment template loading. Adds `camera_raw` logical
  root, `PathResolver.camera_dir()`, `load_alignment_template()`,
  `pick_camera_csv()`.
- **3b:** Core alignment functions. `frame_sync.py` (edge detection, sequence
  matching, affine fit). `timebase.py` (converters + `AlignmentResult`
  dataclass).
- **3c:** Session orchestrator + `notebooks/02_alignment.ipynb` (cam2 only).
  Include the overwrite modes (`"skip"`/`"prompt"`/`"force"`) from Phase 2,
  default `"skip"`. Default strategy: load existing template if present,
  recompute only if missing.
- **3d:** Parity check. Recompute alignment templates on PS46 2025-03-07
  (baseline, day -6) AND PS46 2025-03-20 (post-stroke, day +7). Compare
  against the existing `alignment_templates/cam2/PS46/` NPZs. Tolerances per
  amendment 1.
- **3e:** Tests + MIGRATION_LOG. Include the `SessionManifest` integration
  test from amendment 3.

Commit each sub-phase separately on `phase-3-alignment`. Pause after 3d
(parity check) for Priya's review before proceeding to 3e.

## Update `docs/DECISIONS.md` as part of sub-phase 3e

Append two entries (one per decision made during Phase 3):

- **Branch-protection pre-commit hook installed (2026-04-18).** Context: an
  accidental batch of commits to `main` during Phase 2.5 execution prompted
  this. Decision: `.githooks/pre-commit` refuses commits on `main`/`master`;
  `scripts/setup-hooks.sh` activates via `core.hooksPath`. Enforced at
  `CLAUDE.md` rule 8. Layer 1 (GitHub branch protection) is unavailable on
  private-free-tier accounts; layers 2 (local hook) and 3 (CLAUDE.md Claude
  Code instruction) are the active defense.

- **Phase 3 parity tolerance (this phase).** Float interpolated arrays use
  `rtol=1e-10`; affine fit slope/intercept use `rtol=1e-8` to allow for
  pattern-matcher tie-break differences without rejecting correct ports.

If any other cross-cutting decisions arise during execution, add entries
there rather than burying them in commit messages alone.

## Constraints (reiterated)

- No modifications outside `~/Github/stroke_orofacial_pipeline/` except writes
  to `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/alignment/` on
  MICROSCOPE.
- Both legacy repos
  (`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp` and
   `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya`) are
  read-only.
- Camera data at
  `/Volumes/Neurobio/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera/`
  is read-only — applies to both `.avi` video files and `timestamp*.csv`
  companions.
- `alignment_templates/` on MICROSCOPE is read-only.
- `session_processing3/` is read-only.
- Never bypass the pre-commit hook with `--no-verify` without Priya's
  explicit, documented approval.
- Before every commit, `git branch --show-current` must print
  `phase-3-alignment`.

## Exit criteria for this session

- Sub-phases 3a through 3d committed on `phase-3-alignment`.
- Parity check passes on the two specified PS46 sessions per amendment 1.
- `SessionManifest` populates `wavesurfer_file` and `video_files` per
  amendment 3.
- Report the parity results to Priya in a short summary and pause before
  3e. Do not push to origin, do not open a PR yet.

If anything in the plan or the amendments is unclear, stop and ask Priya
before writing code.
