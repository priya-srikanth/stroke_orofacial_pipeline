# Chore: DLC Session + Trial Filtering Kickoff

**Status:** LOCKED v1 + Addendum #2 (2026-05-29) -- Stages 1-5 + downstream stats wiring complete; filtered_v1 figures deferred to chore/dlc-pooled-phenotype-unification; Stage 6 phase-close pending (Cowork).
**Branch:** `chore/dlc-session-and-trial-filtering`
**Merge tag (on close):** `vChore-dlc-session-and-trial-filtering`
**Depends on:**
- Sensitivity probe PR #157 merged (provides script + validated CSVs at `pipeline_outputs/stats/sensitivity/`).
- Q-lock 13c merged + tagged `v9.1-q13c-tongue-y-trajectory` (provides the trajectory + scalar phase outputs the filter applies to).
- Q-lock 12 / 12a / 12b merged + tagged (unaffected by this chore — explicitly EXCLUDED from filter scope; see §Scope OUT).

---

## Summary

Extends `cohort_filters.SessionFilter` and introduces a new `cohort_filters.TrialFilter` class with per-metric-family configuration. Applies both filters to the DLC tongue trajectory + scalar phenotype-pooled outputs (Q-lock 13 / 13b / 13c), emitting filtered variants alongside the existing unfiltered outputs in a `filtered_v1/` subdir. Spatial analyses (Q-lock 12 heatmaps + W-2) are explicitly UNFILTERED — the "no-licking" phenotype is a meaningful spatial signal that filtering would erase. Spout behavior analyses are also UNFILTERED — they use the existing spout-side cohort enumeration as their quality criterion.

---

## Scope IN

- **SessionFilter v2:** extend with AND/OR combine logic + nullable per-criterion thresholds (so `min_kept_licks: null` disables that criterion). Existing Q-lock 12a SessionFilter API surface is preserved; new behaviors are additive.
- **TrialFilter:** new class in `src/stroke_orofacial/cohort_filters.py`. Same API shape as SessionFilter (`__init__` takes thresholds, `.filter(df_trials)` returns filtered DataFrame, `.report()` returns counts dict).
- **Per-metric-family TrialFilter thresholds** via config override pattern in `configs/defaults.yaml`.
- **Wire both filters into the aggregator stage** of Q-lock 13 / 13b / 13c stats pipelines (filter raw input before aggregation, not post-hoc on aggregated values).
- **Variant subdir emit:** filtered outputs land at `<scope>/filtered_v1/` alongside the existing unfiltered outputs. Preserves comparison; both variants coexist in the trees.
- **Manifest CSVs at every emit layer:** SessionFilter manifest + TrialFilter manifest + phenotype-pool sentinel report.
- **Phenotype-pool sentinel handling:** cells with `n_sessions_kept = 0` emit `NaN + n_animals = 0 + sentinel_reason = "all_sessions_filtered"`. Otherwise cell computes normally even at `n_sessions_kept = 1`.
- **Verify / create `tongue_lick1_velocity_peak`** scalar endpoint: if it doesn't already exist as a first-lick-only variant in `tongue.phase_aligned_endpoints` (or sibling block), add it alongside the existing first-5-lick velocity scalars. Stage 1 task.
- **Cohort re-emit** for Q-lock 13 / 13b / 13c phenotype-pooled outputs with filters applied. Pilot on PS46 first.

## Scope OUT

- **Q-lock 12 proportion-diff heatmaps + W-2 recovery curves + Q12a per-session W-2 boxplots:** UNFILTERED by design. Spatial data per-frame is meaningful regardless of lick count; filtering would erase the "no-licking" severity signal that heatmaps are designed to detect.
- **Spout behavior phenotype-pooled analyses** (latency_hist_cdf, behavior_report, visual_gate): UNFILTERED. They use the existing spout-side cohort enumeration as their quality criterion; DLC filter is not applicable.
- **Per-session, per-trial, per-animal DLC outputs** (Phase 7a.6 mean_video / mean_trace / binned_overlays / per-animal kinematic_plots): NOT re-emitted. Audit-value of these views depends on seeing all sessions/trials including the noisy ones; filtering would hide the very thing they exist to expose.
- **Jaw bodypart:** filter is tongue-only by design. Tongue-jaw mismatch shows the two don't always align; filtering jaw on tongue-detection criteria is incoherent.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Sensitivity probe PR #157 merged | gating Action 2 (Priya) | Cowork |
| Q-lock 13c merged + tagged | DISCHARGED | — |
| Q-lock 12a `SessionFilter` reusable | DISCHARGED | — |
| `tongue_lick1_velocity_peak` scalar endpoint | Verify in Stage 0; create in Stage 1 if missing | CC |

## Locked design decisions

**SessionFilter v2 — extends Q-lock 12a:**
- `min_trials_with_detected_lick: 10` (default on; primary criterion validated by sensitivity probe)
- `min_kept_licks: null` (default off; secondary criterion, settable for future experiments)
- `combine: and` (used only when both criteria are non-null; AND is conservative default)
- `lick_window: tone_aligned` (locks the lick-counting window)
- `lick_provenance: v7_kept` (DLC tongue-kinematics detected lick per `n_licks_family.n_licks`; explicitly distinct from `cohort_filters`' NPZ spout-lick definition — CC must use the DLC definition, not the spout-lick one)
- `apply_to_bodyparts: [tongue]` (jaw excluded by design)

**TrialFilter per-metric-family (locked from probe results):**

```yaml
stats:
  trial_filter:
    dlc_tongue_trajectory_metrics:
      defaults:
        min_licks_per_trial: 1            # first-lick / phase-aligned / X/Y scalar default
      overrides:
        first_5_lick_velocity:
          min_licks_per_trial: 5
        ili_summary:
          min_licks_per_trial: 3
        # lick2_derived: NO entry (lick2 code already requires >=2 licks intrinsically)
        # spatial: explicit null at the SessionFilter level — TrialFilter doesn't apply
```

**Cell-level sentinel (corrected from earlier draft):**
- `(phenotype_4tier × epoch_label × side)` cell with `n_sessions_kept = 0` → sentinel row: `value = NaN, n_sessions = 0, n_unique_animals_contributing = 0, sentinel_reason = "all_sessions_filtered"`.
- Cells with `n_sessions_kept >= 1` compute normally (single-session cells still produce stats, just with no spread).
- 16/32 cells in the existing cohort are single-animal (intrinsic cohort constraint: PS46 alone = moderate, PS51 alone = mod-severe). NOT filter-induced. CC should add a one-line note in the per-cell output: when `n_unique_animals_contributing = 1`, flag as `single_animal_cell = True` for downstream-consumer awareness.

**Session with 0 trials post-TrialFilter:** counted as "not kept" — can't form a per-session statistic from 0 trials. This rolls up into the SessionFilter manifest's exclusion count.

**Variant subdir layout:**
- Unfiltered (existing) at `<scope>/...` — DO NOT touch
- Filtered (new) at `<scope>/filtered_v1/...` — mirrors the same internal subtree structure (figures + null_calib + sd_band + stats CSVs all under filtered_v1/)

**Output paths (Q-lock 15 marker convention preserved):**
- Q-lock 13 / 13c trajectory figures filtered: `stats/figures/phenotype_pooled/phase_aligned_trajectories/filtered_v1/<scope>/<signal>_<variant>_<side>_mean_sem_cleaned_trace.svg`
- Q-lock 13 / 13c trajectory stats CSVs filtered: `stats/results/phenotype_pooled/phase_aligned_trajectories/filtered_v1/<scope>/<test>.csv`
- Q-lock 13b scalar endpoint figures + CSVs filtered: analogous `<existing-path>/filtered_v1/...` mirror.

**Stage 5 cohort emit gate:** STOP-and-ask per GR7 before cohort emit. Same confirm-once-then-force pattern as Q-lock 13 / 12 / 13c.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm PR #157 + Q-lock 13c merged + tagged. Confirm `cohort_filters.SessionFilter` (Q12a) location. Verify whether `tongue_lick1_velocity_peak` first-lick scalar exists; if not, plan Stage 1 creation. Editable-install pointer check (per parallel-CC discipline). |
| 1 | SessionFilter v2 + TrialFilter class | CC | Extend SessionFilter with AND/OR + nullable criteria; new TrialFilter class. Both expose `.filter(df) -> filtered_df` + `.report() -> dict`. Tests: unit tests for combine logic, edge cases (all-zero counts, all-included), nullable criterion handling. |
| 2 | Add `tongue_lick1_velocity_peak` IF MISSING | CC | First-lick peak velocity scalar. Compute from same v7-kept-lick list as the existing first-5-lick variants. Add as new column in `tongue.phase_aligned_endpoints` block. Tests: known-input/known-output. (Skip if Stage 0 verifies it already exists.) |
| 3 | Config additions + downstream consumer audit | CC | `configs/defaults.yaml` `stats.session_filter.*` + `stats.trial_filter.*` blocks per the locked spec. Grep all aggregators in `stats/aggregators.py` + `stats/runners.py` to identify the filter-application sites. Update each to consume the per-metric-family filter config. Tests: integration test on a 2-animal synthetic fixture verifying the right filter is applied per metric. |
| 4 | Filtered-variant emit drivers | CC | Update Q-lock 13 / 13b / 13c emit drivers to also emit `filtered_v1/` variants. Each driver gets a `--filter-variant={none,filtered_v1}` flag (default `none` for backward compat; chore-PR's cohort emit uses `filtered_v1`). Manifest CSV at each emit layer (SessionFilter manifest, TrialFilter manifest, phenotype-pool sentinel report). |
| 5 | Cohort emit on 8-animal cohort | CC | Pilot on PS46 first. Report wall-time + filter manifest contents + spot-check that 3 phenotype-pooled cells have expected `n_sessions_kept` (cross-reference against the sensitivity probe's `combined_filter_summary.csv`). STOP HERE before 7-animal fanout per GR7. |
| 6 | Phase close + merge tag | Cowork | MIGRATION_LOG entry capturing the filter design + interpretation locks (v7-kept = DLC-detected; 0-trials-post-TrialFilter session not kept; spatial UNFILTERED; spout behavior UNFILTERED). DECISIONS entry with the per-metric-family override pattern. Tag-on-merge: `vChore-dlc-session-and-trial-filtering`. |

---

## Forward-pointers

- **Successful-trials filter variant** (kickoff scope-out across Q-lock 13 / 13c): this chore-PR's TrialFilter IS the substrate. Future ticket can add additional criteria to TrialFilter (e.g., lick-window coverage, trial-completion flag).
- **Jaw bodypart filtering:** out of scope here. If/when jaw analyses surface a divergent need (e.g., different lick-count-based criterion), separate ticket with its own threshold lock.
- **Drop unfiltered tree after filtered-v1 validated:** follow-up cleanup chore once Priya confirms filtered_v1 outputs match expectations. Reduces tree volume.
- **Filtered W-2 / heatmap variant:** if Priya later wants a parallel filtered variant of the spatial analyses for sensitivity comparison, separate ticket. NOT in scope here per the no-licking-severity-signal argument.

## References

- **Sensitivity probe PR #157** — threshold validation, interpretation locks.
- **Q-lock 12a Addendum #6** — `cohort_filters.SessionFilter` introduction (the v1 substrate this chore extends).
- **Q-lock 13 / 13b / 13c** — the trajectory + scalar phenotype-pooled outputs the filter applies to.
- **Q-lock 12 (NOT extended here)** — proportion-diff heatmaps + W-2 stay UNFILTERED by design.
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe; 3-tier collapse via Q-lock 12 Addendum #4).
- **`[[project_phase_9_1_q12_durable_architecture]]`** — SessionFilter origin + `stats/figures/phenotype_pooled/` canonical home.

---

## Addendum #1 — Filter architecture: separate DlcSessionFilter class (2026-05-29)

CC's Stage 0 verification revealed that the v1 SessionFilter reads NPZ spout-licks
(via `compute_session_lick_stats`) while the v2 filter must read DLC tongue-kinematics
licks (`n_licks_family.n_licks` from per-trial tongue JSONs). These are different
data sources, not different thresholds on the same source.

Original kickoff wording said "extend SessionFilter v2... new behaviors additive."
Revised per CC's design fork — extending the v1 class to handle two divergent
data-source readers is the classic Single Responsibility violation. Adopting
separate classes instead.

**ALL OTHER LOCKS UNCHANGED.**

### Revised filter architecture

- **`cohort_filters.SessionFilter` (v1):** UNCHANGED. Reads NPZ spout-licks. Sole
  v1 consumer (`scripts/phase_9_1_q12/emit_cohort.py`) continues to call it.
  Zero touch.

- **`cohort_filters.DlcSessionFilter` (new):** Separate class. Reads per-trial
  tongue JSONs via the v7-kept lick provenance (`n_licks_family.n_licks`).
  API mirrors v1 shape: `__init__(thresholds, combine_rule, lick_window,
  lick_provenance, apply_to_bodyparts)`, `.is_pass_through()`, `.check()`,
  `.filter(df_sessions) -> filtered_df + filter_result`, `.report() -> dict`.
  Used by Q-lock 13 / 13b / 13c filtered emit drivers.

- **`cohort_filters.DlcTrialFilter` (new):** Net-new symmetric class. Per-metric-
  family per-trial filtering on DLC v7-kept lick counts. Same API shape as
  `DlcSessionFilter` but operates on per-trial rows.

### Revised config namespace

- `stats.session_filter.*` — v1 namespace UNCHANGED (Q12a SessionFilter config).
- `stats.dlc_session_filter.*` — new namespace for `DlcSessionFilter` config.
- `stats.dlc_trial_filter.*` — new namespace for `DlcTrialFilter` config.

The originally-drafted `stats.session_filter.dlc_tongue_metrics` key is
SUPERSEDED — moved to `stats.dlc_session_filter.dlc_tongue_trajectory_metrics`.

### Why separate class, not extension

1. Different data sources (NPZ spout vs DLC tongue JSON) — fundamentally divergent
   readers, not just thresholds.
2. v1 SessionFilter untouched = zero regression risk for Q-lock 12 / 12a / 12b
   consumers (shipped and stable).
3. Single-responsibility per class.
4. Future filter types (spout-behavior-specific, jaw-specific, etc.) follow the
   same pattern cleanly.
5. Names make intent obvious at call sites: `DlcSessionFilter` says "for DLC
   metrics; don't use on spout-behavior data."

### Stage 1 scope (refined)

Stage 1 work shape:
- Add `DlcSessionFilter` class to `cohort_filters.py`.
- Add `DlcTrialFilter` class to `cohort_filters.py`.
- Add new v7-kept session/trial stats helpers (reads per-trial tongue JSON).
- Add `load_dlc_filter_spec_from_defaults()` for the new config namespace.
- Tests: unit tests for new classes (combine logic, edge cases, nullable
  criteria, 0-trial-post-filter session-not-kept roll-up).
- v1 SessionFilter literally untouched; Q12 emit_cohort.py untouched.

This stays within the 5-file refactor threshold for Stage 1 (cohort_filters.py
+ tests). Stages 3–4 add configs + wire into aggregators/runners/drivers, which
is the cross-file work the chore as a whole entails.

---

## Addendum #2 — Pipeline-B re-target + Option-I filtered_v1 design (2026-05-29)

**ALL OTHER LOCKS UNCHANGED** except where this Addendum supersedes the
original "13b figure pipeline" wording.

### Re-target to Pipeline B (the materialize/runners per-trial stats family)

CC's Stage 0/3 work surfaced that the first-lick velocity endpoint the kickoff
Stage 2 told us to "create" — and its whole sibling family — **already exist**
in the Phase 9 Task 2/3 per-trial stats pipeline (`materialize_inputs.py` +
`runners.py`): `tongue_lick1_vy_peak`, `tongue_lick1_vxy_peak`,
`tongue_max_vy_peak_first5`, `tongue_max_vxy_peak_first5`,
`tongue_mean_vxy_peak_first5`, `tongue_lick1_y_peak`, `tongue_lick1_x_at_ypeak`,
etc. (`tongue_lick1_vy_peak` = `vy_peaks_bylick[0]`; parity-verified byte-equal
to a candidate re-derivation over 1150 trials / 12 sessions, 0 mismatches).

Consequence: **no new scalar emission is needed** — Stage 2 ("create
`tongue_lick1_velocity_peak`") is moot. The chore re-targets from the Q-lock
13b phase-aligned figure aggregators (Pipeline A) to **Pipeline B**, applying
the DLC session/trial filter at materialize time. The interim Pipeline-A
filtering transform + duplicate lick1 loader were reverted (commit `cb1a29f`).

### Option-I design: filtered_v1 inputs at materialize time

`materialize_inputs.py --filter-variant filtered_v1` emits session/trial-
filtered TONGUE per-trial endpoints to
`stats/inputs/filtered_v1/<slug>/<animal>.parquet`, **alongside** the unfiltered
tree (never overwriting it). `runners.py` / `run_stats_axis.py` /
`build_task_*` then read `filtered_v1` via the same `--filter-variant` switch
with no logic change. Filter composition: Stage A SessionFilter
(`min_trials_with_detected_lick=10`), Stage B per-metric-family TrialFilter
(default 1; `first_5_lick_velocity` 5; `ili_summary` 3), Stage C 0-trial-post-
filter session rollup (`trial_filter_emptied_session`). SessionFilter +
TrialFilter manifests land under `filtered_v1/_manifests/`.

### Tongue-only FDR-family lock

Non-tongue endpoints have no `filtered_v1` input, so each filtered
`(axis, granularity)` BH-FDR family is **tongue-only by construction** — the
headline kinematics (vy/vxy peaks + first-5 reductions + peak-y / x-at-peak-y /
lick1/lick2 angle endpoints) correct together under one BH-FDR family, per the
2026-05-29 Priya lock ("phenotype-pooled lick1 velocity stats fold into the
other per-trial stats as regards FDR correction").

### Figures deferred (pre-unification snapshots)

The `stats/figures/filtered_v1/headlines/` figures emitted by this chore are
**pre-unification snapshots** in the OLD convention (boxplots, raw L/R coding).
Canonical filtered figures land via the sibling
`chore/dlc-pooled-phenotype-unification` PR under a `v2/` subtree, which layers
three changes on these durable stats inputs: filtered_v1 inputs (this PR) +
ipsi/contra recoding (Q-lock 14 helper) + the new line+jitter+dots plot
convention (Q-lock 14 canonical). **This chore-PR ships stats inputs + headline
summary only**; figures are not a durable deliverable here.
