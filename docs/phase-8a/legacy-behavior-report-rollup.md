# Phase 8a.9 Legacy Behavior-Report Rollup

**Date:** 2026-04-22.
**Scope:** docs-only close-out for the legacy behavior-report walkthrough required by Audit Item 10 Q9.
**Evidence base:** `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`.

This rollup indexes the Phase 8a behavior-report archaeology after the
8a.1-8a.7.5 implementation chain. It does not supersede the full archaeology
document; it is the compact handoff surface for future Phase 8a.8 visualization,
Phase 8a.9 maintenance, and Phase 9 stats work.

No legacy repository was reopened for this rollup. The source evidence remains
the read-only archaeology pass already captured in
`docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`.

---

## Canonical Sources

Use these legacy files as the canonical stroke-behavior references:

- `analysis/behavior_report/behavior_report_PS.py` - endpoint computation,
  criteria hierarchy, per-session `report.json`, and per-animal longitudinal
  plots.
- `analysis/behavior_report/summary_PS.py` - per-metric multi-animal summary
  grids.
- `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb` -
  current entry-point notebook and parameter wiring.

Rich's upstream pre-stroke `analysis/behavior_report/behavior_report.py` is
superseded by Priya's stroke-aware `behavior_report_PS.py` and is not a port
target.

---

## Q9 Endpoint Rollup

| Q9 endpoint | Legacy status | Consolidated status |
|---|---|---|
| `within_session_learning_curve` | No legacy implementation | Implemented as a greenfield Phase 8a endpoint primitive in `endpoints_within_session.py`; visualization remains Phase 8a.8. |
| `within_session_change` | No legacy implementation | Implemented as a greenfield Phase 8a endpoint primitive in `endpoints_within_session.py`; visualization remains Phase 8a.8. |
| `first_lick_latency` | Full match to A10 `latency_to_first_correct_lick_s` | Re-packaged as `first_lick_latency_per_trial` in `endpoints_per_trial.py`, preserving per-trial latency structure for downstream summaries. |
| `directional_lick_accuracy` | Partial: legacy A7/A9 have correct/incorrect lick counts, but not the Q9 per-trial-type fraction view | Implemented as `directional_lick_accuracy_per_session` in `endpoints_per_trial.py`, extending the legacy ingredients into the requested split/fraction endpoint. |
| `switch_cost` | No direct legacy implementation; distinct from legacy A12 lick-direction switching | Implemented as `switch_cost_per_session` in `endpoints_per_trial.py`, using trial-to-trial reward-side transitions. |
| `latency_variability` | Partial: legacy A10 computes latency standard deviation as a byproduct | Implemented as `latency_variability_per_session` in `endpoints_per_trial.py`, promoting variability to a first-class endpoint. |
| `lick_bout_structure` | No direct legacy implementation; running-bout logic was only a template | Implemented via `lick_bouts.py` plus the writer adapter in `endpoints_writer.py`. |
| `inter_session_persistence` | No legacy implementation | Scaffolded in `endpoints_cross_session.py`; per-session JSON keeps the slot as a cohort-aggregation sentinel by design. |

The Q9 walkthrough found no stale endpoint computation inside
`behavior_report_PS.py` that should be discarded. The one deprecated file-level
candidate is Rich's original `behavior_report.py`, which is superseded and not
ported.

---

## Criteria Hierarchy Status

The numeric legacy criteria names were renamed in Phase 8a to descriptive slugs:

| Legacy key | Consolidated slug | Status |
|---|---|---|
| `criteria_1` | `criteria_training_pass_consecutive_sessions` | C1 remains a cohort-aggregation sentinel in per-session JSON. |
| `criteria_2` | `criteria_session_trial_pass_fraction_above_threshold` | Computed in 8a.7.5. |
| `criteria_3` | `criteria_first_correct_lick_present` | Computed in 8a.7.5. |
| `criteria_4` | `criteria_correct_lick_count_threshold` | Computed in 8a.7.5. |

C1 intentionally stays out of the per-session writer because it depends on the
last N sessions for an animal. Computing it inside a per-session JSON would
break the provenance contract that the file is a pure function of one session's
inputs. A future cohort layer computes C1 alongside other cross-session
quantities.

---

## Additional Endpoint Disposition

The archaeology surfaced four worth-keeping items beyond the original Q9 list:

- `tone_trial_count_per_session` (Phase 8a.10.1 Q-C rename 2026-05-14;
  was `reward_trial_count_per_session`) - promoted as a Phase 8a
  engagement extra in `endpoints_engagement.py`. Counts trial-cue
  exposures (tone events presented), not rewards earned — under
  Case-2 universal the legacy `Reward_*` channel was the tone-cue
  channel, so the original "reward trial count" name was a misnomer.
- `inter_trial_interval_distribution` - promoted as a Phase 8a engagement extra
  in `endpoints_engagement.py`, with summary statistics stored rather than raw
  ITI arrays.
- Legacy A11 `late_lickiness` - recorded as recovery-relevant legacy behavior;
  not a Phase 7 or DLC task.
- Legacy A12 `lick_switch_rate` - recorded as recovery-relevant legacy behavior
  distinct from Q9 `switch_cost`; not a Phase 7 or DLC task.

These remain in the spout-behavior / Phase 8a domain. They do not expand Phase
7 kinematic scope.

---

## Non-Goals

- No phenotype classification in Phase 8a.8 or 8a.9. Phase 8a only supplies
  visualization hooks; true phenotype classification belongs to Phase 9.1.
- No DLC endpoint work. DLC kinematic recovery trajectories are Phase 8b and
  depend on Phase 7.
- No source-data modification and no legacy-repo edits.
- No Python API, schema, notebook, config, or output-contract change in this
  docs-only rollup.

---

## Follow-Up Docket

Keep these queued for future scoped PRs:

- Phase 8a.8 recovery-trajectory visualization implementation.
- Phase 5.5 polish.
- Cohort-wide Phase 5 re-run.
- Phase 6 reward-aligned live-data retest.
- PS48 2025-03-14 multi-half handling, as a separate I/O-facing mini-phase or
  coordinated Phase 7 prerequisite because it can affect DLC loading.

Closed 2026-04-22: `scripts/parity_external_bnpm.py` remains an ignored
scratch-only probe rather than a permanent repo script. The durable record is
the DECISIONS/MIGRATION_LOG narrative plus the committed clamp-bug regression
tests.
