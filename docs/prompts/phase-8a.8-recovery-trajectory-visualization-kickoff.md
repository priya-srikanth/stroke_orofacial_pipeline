# Phase 8a.8 Kickoff — Recovery-Trajectory Visualization + Phenotype Prototype

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
for execution:

> Read `docs/prompts/phase-8a.8-recovery-trajectory-visualization-kickoff.md` and follow the instructions in full.

---

## Context

Phase 8a.7.5 (criteria hierarchy port) is complete and merged. Phase 8a.8 is the
first user-facing recovery-visualization stage for spout endpoints and should be
run as a **parallel workflow** while Phase 7 DLC kinematics is in progress.

Scope for this sub-phase is:

1. Build per-animal and cohort-level recovery trajectory visualizations for the
   Phase 8a endpoint set.
2. Add a phenotype-grouping prototype hook (visualization-only) that can later
   be wired to Phase 9.1 classification outputs.
3. Allow small helper-computation additions when required to support robust
   plotting/provenance (e.g., reusable aggregation helpers), without expanding
   into new endpoint-definition work.

This kickoff is intentionally structured to integrate with the current
Cowork+Claude same-machine Windows workflow and to avoid conflicts with active
Phase 7 implementation work.

## Before anything else

Re-read these in full before plan mode:

- `CLAUDE.md` (all rules; especially data safety + git discipline + plan-mode
  requirements).
- `docs/COWORK_SESSION_STATE.md` (current state, active task list, and
  operational workflow constraints).
- `docs/DECISIONS.md` entries for 2026-04-19 Q1–Q10 and 2026-04-22 workflow
  boundary rules.
- `docs/MIGRATION_LOG.md` entries for Phase 8a.7 and 8a.7.5.
- `docs/prompts/phase-8a-spout-recovery-trajectories-kickoff.md`
  (parent Phase 8a structure).
- `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` (legacy endpoint inventory +
  parity framing).
- `docs/prompts/phase-7-dlc-kinematics-kickoff.md` (to avoid cross-phase
  collisions; do not edit Phase 7 files in this sub-phase).

Confirm in one sentence that all of the above were re-read and that this branch
will remain isolated from Phase 7 paths.

## Environment activation

Run before any `pytest`, `ruff`, `python`, or notebook execution:

```bash
conda activate stroke_orofacial
which python
python -c "import stroke_orofacial"
pytest --collect-only -q
```

If activation fails, use `conda run -n stroke_orofacial <command>`.

## Workflow + permissions/access constraints (must follow)

- Claude Code (Windows) is the executor for conda/python/notebook/test runs,
  MICROSCOPE path access, and all git state-changing operations.
- Cowork can draft docs/plans but must not run state-changing git operations on
  the cross-OS-mounted repo (sandbox-git boundary rule).
- No source-data modification (raw wavesurfer/camera/DLC outputs remain
  read-only).
- No legacy-repo edits.

## Branching and conflict-avoidance rules

This sub-phase is intentionally parallel to active Phase 7 work.

1. Start from latest `main` and use a dedicated branch for this work only:

```bash
git checkout main
git pull origin main
git config --get core.hooksPath
git checkout -b phase-8a.8-recovery-trajectory-visualization
git branch --show-current
```

2. **File-touch allowlist for this branch**
   - Allowed: `src/stroke_orofacial/spout_behavior/**`,
     `notebooks/02a_spout_behavior_report.ipynb` (only if needed),
     `docs/**` for Phase 8a.8 docs.
   - Disallowed: `docs/phase-7/**`, `docs/prompts/phase-7-*`,
     `src/stroke_orofacial/dlc_*`, `notebooks/13_*`, `notebooks/14_*`.

3. Keep PR scope narrow (8a.8 only). If a needed change touches shared
   cross-phase infrastructure, stop and request split planning before editing.

## Plan requirements (per CLAUDE.md)

Plan mode is mandatory. Include all required elements:

1. Legacy disambiguation references used for visualization behavior and naming.
2. Dead-code identification for any legacy visualization blocks consulted.
3. Sub-phase breakdown with file-level estimates.
4. Validation/parity strategy (legacy-congruent plots for existing endpoints,
   deterministic checks for helper-computation outputs).
5. Hardcoded constants extraction into `configs/defaults.yaml` when applicable.

Pause for Priya approval before writing files.

## Implementation boundaries

### In scope

- Recovery trajectories for existing Phase 8a endpoint outputs:
  - per-animal day-relative-to-stroke trajectories;
  - cohort overlays (mean ± SEM/CI);
  - side-aware variants where endpoint semantics require it.
- Visualization-only phenotype prototype support:
  - grouping hook interface (default `"all"`);
  - optional mock grouping for plot QA;
  - no true classifier implementation.
- Small helper computations that directly support plotting correctness,
  reproducibility, and testability.

### Out of scope

- New DLC endpoint work (Phase 7 / 8b / 9b domain).
- True phenotype classification algorithm (Phase 9.1 domain).
- Refactors outside spout behavior / 8a visualization paths.

## Validation checklist

At minimum:

- `pytest --collect-only -q` succeeds before and after edits.
- Targeted tests for new helper computations and plot-data assembly pass.
- Existing Phase 8a-related tests remain green.
- `ruff check` clean on touched files.
- One representative cohort plot generation run completes end-to-end.
- MIGRATION_LOG and SESSION_STATE updates are included in the same PR.

## Required documentation updates in this sub-phase

1. `docs/MIGRATION_LOG.md` — add a Phase 8a.8 entry documenting scope,
   outputs, tests, and any intentional behavior differences.
2. `docs/COWORK_SESSION_STATE.md` — refresh current state / active-task list
   to reflect 8a.8 kickoff and branch-isolation rule with Phase 7 in flight.
3. `docs/DECISIONS.md` — add an entry only if non-obvious judgment calls are
   made (e.g., visualization contract decisions that future phases must honor).

## Commit and merge plan for parallel workflows

Use a two-PR strategy if needed to avoid blocking:

- **PR A (docs-only kickoff + workflow sync)** — this prompt + session-state
  refresh (+ decisions/log touchups if needed). Merge anytime.
- **PR B (8a.8 implementation)** — code/tests/notebook/docs for 8a.8 only.

Rules:
- Rebase/merge from `main` before opening PR B.
- Do not pull Phase 7 feature-branch commits into PR B.
- Keep feature branches preserved on origin after merge.

## Exit criteria

- Approved plan executed within 8a.8 scope.
- No overlap with active Phase 7 implementation files.
- Recovery-trajectory visualization outputs generated and sanity-checked.
- Tests and lint pass on touched scope.
- Required docs updated (`MIGRATION_LOG`, `COWORK_SESSION_STATE`, optional
  `DECISIONS` when warranted).
- PR merged cleanly without interfering with Phase 7 commit flow.

If any required edit appears to overlap active Phase 7 files or shared
cross-phase contracts, STOP and ask Priya before proceeding.
