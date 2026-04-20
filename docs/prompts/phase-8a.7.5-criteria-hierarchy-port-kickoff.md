# Phase 8a.7.5 Kickoff — Criteria Hierarchy Port (C3, C4, C2)

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` and follow the instructions in full.

---

## Context

Phase 8a sub-phases 8a.1 through 8a.7 are complete and merged to main. At the
end of 8a.7, the per-session JSON writer (`spout_endpoints.json`) emits
sentinel objects for all four criteria slugs established in 8a.1:

- `criteria_first_correct_lick_present` (C3, legacy `criteria_3`)
- `criteria_correct_lick_count_threshold` (C4, legacy `criteria_4`)
- `criteria_session_trial_pass_fraction_above_threshold` (C2, legacy `criteria_2`)
- `criteria_training_pass_consecutive_sessions` (C1, legacy `criteria_1`)

This sub-phase ports the **three per-session-computable criteria** into real
computed values (C3, C4, C2) and leaves C1 as a sentinel.

**Rationale for splitting C1 out:** C1 is a multi-session aggregation
(training-pass over consecutive sessions). Computing multi-session values
inside a per-session JSON breaks the "JSON = function of this session's data"
provenance contract and creates silent staleness whenever any upstream
session's data changes. This is the same architectural issue as
`inter_session_persistence` — multi-session quantities belong in a dedicated
cohort-aggregation layer (future phase) that explicitly tracks which
per-session JSONs it depends on, so upstream changes trigger visible rebuilds
rather than silently producing stale values.

C1's sentinel in the JSON writer should match the pattern established for
`inter_session_persistence`:

```json
{"status": "requires_cohort_aggregation", "computed_at": "cohort_aggregation_stage"}
```

If the current C1 sentinel from 8a.7 uses a different status string, align it
as part of this sub-phase.

## Before anything else

Re-read:

- `CLAUDE.md` — all rules apply.
- `docs/prompts/phase-8a-spout-recovery-trajectories-kickoff.md` — parent
  Phase 8a kickoff.
- `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` — archaeology reference,
  especially §1 (criteria ground-truth definitions).
- `docs/DECISIONS.md` — recent 2026-04-19 Q1–Q10 scoping entry; any 8a.7
  decisions that landed post-8a.7 merge.
- `behavior_report_PS.py:455–551` (read-only legacy reference) for the
  C3/C4 per-trial computation.
- `src/stroke_orofacial/spout_behavior/criteria_slugs.py` — established
  slug map + validator.
- `src/stroke_orofacial/spout_behavior/endpoints_writer.py` — existing
  sentinel emission point for criteria block.
- `src/stroke_orofacial/spout_behavior/endpoints_per_trial.py` —
  TrialRecord contract from 8a.3.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath   # should print: .githooks
git checkout -b phase-8a-part4-criteria-hierarchy
git branch --show-current           # must print: phase-8a-part4-criteria-hierarchy
```

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements.
Expected shape:

1. **Legacy file disambiguation** — confirm `behavior_report_PS.py` is the
   canonical source and that no sibling files (e.g. `_v0`, `_old`, alternate
   dated versions) exist in either legacy repo. Report the check.
2. **Dead code identification** — walk `behavior_report_PS.py:455–551`
   function-by-function or block-by-block. Classify each as production,
   exploratory, or deprecated per CLAUDE.md conventions. Only production
   items get ported.
3. **Sub-phase breakdown** with per-file line estimates:
   - `src/stroke_orofacial/spout_behavior/criteria.py` (new module) — or
     extension of an existing module; argue for one. Recommend new module
     for scope separation — criteria computation is conceptually distinct
     from the slug map (string mapping) and from the endpoint primitives
     (trial/session metrics). ~100 lines for C3, C4, C2 compute functions.
   - `src/stroke_orofacial/spout_behavior/endpoints_writer.py` — integration
     edits replacing C3/C4/C2 sentinel dicts with real computed values;
     verify C1 sentinel status string matches the
     `inter_session_persistence` pattern. ~20 lines modified.
   - `tests/test_criteria.py` (new) — synthetic-fixture tests for C3/C4/C2
     computation + parity test against legacy on PS46/20250307. ~150 lines.
   - `tests/test_endpoints_writer.py` — tests asserting criteria block now
     contains real values for C3/C4/C2 and sentinel for C1. ~30 lines added.
4. **Parity strategy** —
   - Per-trial C3 and C4 boolean arrays byte-identical vs legacy
     `behavior_report_PS.py:455–551` on PS46/20250307 reference session.
   - C2 per-session-per-side aggregate byte-identical (boolean counts, no
     floating-point tolerance needed).
   - Fixture: reuse the existing PS46/20250307 TrialRecord pipeline fixture
     from 8a.3 tests.
   - If the legacy function produces different outputs than a faithful
     re-implementation of its documented intent (i.e., a bug in the legacy
     function), **STOP and report**. Do not silently diverge. Follow the
     same "preserve caller intent, fix the bug in the new code, document
     the divergence + rationale in MIGRATION_LOG" pattern used in Phase 13
     for the bnpm vendored helpers (`widen_bool_sparse`,
     `set_short_bool_to_low`).
5. **Hardcoded constants** — none new. C3 window `(0, 2.0)` seconds and
   C4 window `(0, 2.5)` seconds already in `configs/defaults.yaml` under
   the `spout_behavior.endpoints` block (line range per 8a.1). Correct-lick
   definition uses `reward_side` as the ground-truth correct side (per
   archaeology §1).

The plan must pause for Priya's explicit approval before any files are written.

## Exit criteria

- Per-trial C3 and C4 boolean arrays byte-identical vs legacy on
  PS46/20250307 reference session.
- C2 per-session-per-side aggregate byte-identical vs legacy.
- C1 sentinel unchanged in computation terms but status-string aligned
  with `inter_session_persistence` pattern if not already.
- JSON writer tests updated to assert criteria block contains computed
  values for C3/C4/C2 and sentinel for C1.
- All pre-existing tests pass.
- `ruff check` clean on all 8a.7.5-touched files.
- `docs/MIGRATION_LOG.md` Phase 8a.7.5 entry summarizes the port, any
  legacy-function bugs discovered, their resolution, and the scope
  decision (why C1 stays sentinel).
- `docs/DECISIONS.md` entry if any non-obvious judgment calls were made
  (e.g., legacy bug fix + divergence rationale).
- PR merged to main.

## Constraints

- Strictly additive + sentinel replacement. No behavior change to any
  existing endpoint or writer field outside the criteria block.
- C1 explicitly not ported in this sub-phase. If tempted to "just compute
  C1 too since we already have C2 per-session values" — STOP and re-read
  the Context rationale. The provenance contract matters more than
  computational convenience.
- No mid-phase pause required. Scope is small and self-contained; single
  plan-approval checkpoint before code writes.
- If the legacy C3/C4 computation reveals a bug that makes byte-identical
  parity impossible, apply the Phase 13 vendoring policy: preserve caller
  intent, fix the bug in the new code, document the divergence + rationale
  in MIGRATION_LOG, and assess downstream impact (does any other module
  depend on the buggy semantics?).

If the port reveals that the legacy computation has a dependency not
currently in `TrialRecord` (e.g. a cue-side signal or a pre-trial state
field that wasn't needed by 8a.2–8a.6), STOP and ask. Do not silently
expand TrialRecord's schema mid-port.
