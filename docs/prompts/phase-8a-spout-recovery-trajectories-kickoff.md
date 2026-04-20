# Phase 8a Kickoff — Spout-Only Recovery Trajectories

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code to invoke:

> Read `docs/prompts/phase-8a-spout-recovery-trajectories-kickoff.md` and follow the instructions in full.

---

## Context

Phase 8a is the spout-only recovery-trajectory mini-phase — the mid-experiment scientific deliverable that produces longitudinal-by-day-relative-to-stroke plots of spout-behavior endpoints across the 8-animal cohort (PS46/47/48/49/50/51/54/55). Strictly DLC-independent; consumes only Phase 2 (spout behavior) and Phase 2.5 (running/grooming/quiet) outputs.

This phase combines four threads from the 2026-04-19 audit closure (DECISIONS.md "Audit Item 10" entry):

- **Q9** — implement 8 new spout endpoints: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`.
- **Q9 follow-up** — systematic walkthrough of legacy `facerhythm_stroke_biomarker_exp_Priya` spout-behavior code to (a) match each of the 8 to existing implementations where possible, (b) surface additional worth-keeping endpoints, (c) explicitly discard stale / redundant ones.
- **Q2** — finalize descriptive slug names for the legacy `criteria_1/2/3/4` (placeholder names from DECISIONS.md don't match the actual formulas; better-grounded proposals are in the archaeology doc).
- **Q3** — build recovery-phenotype visualization hooks (faceting / coloring infrastructure) into Phase 8a's plotting layer, even though phenotype *classification* is deferred to a separate Phase 9.1.

The legacy archaeology has already been done (by Cowork on 2026-04-20) and lives at `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`. That doc is the evidence base for this kickoff and **must be read before plan mode**. It maps each Q9 endpoint to its legacy status (full / partial / none), gives ground-truth definitions for `criteria_1/2/3/4`, inventories the current `report.json` schema, characterizes the existing longitudinal-aggregation infrastructure, and surfaces 7 open scoping questions that need Priya's call at plan-mode time.

**Topline from the archaeology:** 6 of 8 Q9 endpoints are fully greenfield, 1 is a full match (`first_lick_latency` ↔ A10), 1 is a partial match needing extension (`directional_lick_accuracy`), `criteria_1/2/3/4` are hierarchical (C3+C4 → C2 → C1), no stale code to discard, longitudinal infrastructure is mature (per-animal stroke-relative day axis + per-metric multi-animal grids both already exist in `summary_PS.py`), no recovery-phenotype hooks exist (build fresh).

## Before anything else

Re-read in this order:

- `CLAUDE.md` — all rules apply.
- `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` — the archaeology / evidence base for this kickoff. Sections §1 (criteria definitions + slug proposals), §2 (per-endpoint mapping), §5 (current `report.json` schema), §6 (longitudinal infrastructure), §8 (open scoping questions) are essential.
- `docs/SCIENTIFIC_ENDPOINTS.md` — the 26-endpoint Q1–Q10 inventory; treat the Q1–Q10 section at the bottom as historical (superseded by the 2026-04-19 DECISIONS entry), but the catalog itself remains current.
- `docs/DECISIONS.md` — the 2026-04-19 "Audit Item 10" grouped entry (Q9 endpoint list, Q2 rename intent, Q3 phenotype-viz timing) and the 2026-04-18 entry "Phase 8 split into 8a (spout behavior) + 8b (DLC behavior)" entry.
- `docs/DESIGN.md` §7 Phase 8a entry, and §9 phenotype-stratification framework.
- `docs/MIGRATION_LOG.md` Phase 2 + 2.5 entries — Phase 8a consumes their outputs and follows their per-animal-loop pattern.
- `src/stroke_orofacial/spout_behavior/` — the existing module layout (`bouts.py`, `wavesurfer_io.py`, etc.) you'll add to.
- `configs/defaults.yaml` — existing `spout_behavior` block; new Phase 8a parameters get added here.
- `configs/animals.yaml` — cohort metadata; `stroke_date` per animal drives day-relative-to-stroke labeling. Will likely need `sex` + `date_of_birth` fields (task #18) for downstream covariates, but that's a separate task — do not block on it for Phase 8a.
- Legacy code (read-only, do NOT modify): `analysis/behavior_report/behavior_report_PS.py`, `analysis/behavior_report/summary_PS.py`, `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb`. These are the canonical implementations referenced throughout `PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath   # should print: .githooks
git checkout -b phase-8a-spout-recovery-trajectories
git branch --show-current           # must print: phase-8a-spout-recovery-trajectories
```

## Scoping decisions to lock at plan-mode time

Phase 8a has 7 open scoping questions surfaced by the archaeology. These must be resolved with Priya at the start of plan mode, BEFORE the sub-phase breakdown is finalized. Present them as a checklist and request her decision on each:

1. **Slug renames for `criteria_1/2/3/4`.** Default proposal (from `PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` §1):
   - `criteria_1` → `criteria_training_pass_consecutive_sessions`
   - `criteria_2` → `criteria_session_trial_pass_fraction_above_threshold`
   - `criteria_3` → `criteria_first_correct_lick_present`
   - `criteria_4` → `criteria_correct_lick_count_threshold`

   Priya may shorten or rename. Lock final names before any code is written.
2. **`directional_lick_accuracy` reporting form.** Default proposal: per-(L-reward-trial, R-reward-trial) split with both per-trial counts AND per-session aggregate fractions. Confirm or override.
3. **`lick_bout_structure` parameters.** Default proposal: max-ILI = 250 ms, min-licks-per-bout = 2, report mean bout count per session + mean bout duration + mean within-bout ILI. Priya may adjust thresholds or expand the reported fields.
4. **`late_lickiness` window configurability.** Default proposal: keep the existing legacy 8–60 s hard-coded behavior for now; flag as parameterizable in a future polish phase. Priya may instead promote it to a `configs/defaults.yaml` parameter immediately.
5. **Recovery phenotype prototype.** Default proposal: Phase 8a does NOT compute phenotype classification — that's strictly Phase 9.1. Phase 8a builds the viz hooks (default group = single "all"). Priya may instead want a quick prototype clustering for intermediate use during data collection.
6. **Output schema versioning.** Default proposal: write Phase 8a outputs to a parallel `spout_endpoints_v2.json` per session, leaving the legacy `report.json` byte-stable. Priya may instead want to extend `report.json` in place.
7. **Cohort discovery.** Default proposal: auto-discover animals from `configs/animals.yaml` (filtered to those with at least one session in the Phase 2 output directory). Priya may want a pinned list for reproducibility.

Each decision becomes a one-line entry in the plan and a corresponding line in the eventual MIGRATION_LOG entry.

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements.

### 1. Legacy file disambiguation

Already done in `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` §9. Canonical files: `behavior_report_PS.py`, `summary_PS.py`, `batch_process_behavior_report_20260116PS.ipynb`. Rich's `behavior_report.py` is fully superseded and not a port candidate. Note the disambiguation as resolved; no STOP-and-ask needed unless re-walking the legacy turns up a file the archaeology missed.

### 2. Dead code identification

Already done in `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` §4. No stale / discard candidates found in `behavior_report_PS.py`. List this as "no dead code identified in legacy port targets" and proceed.

### 3. Sub-phase breakdown

Suggested decomposition (Claude Code may refine in plan mode):

- **8a.1 — Slug-rename foundation** (~50 lines src + ~50 lines tests). Establish the new slug names for `criteria_1/2/3/4` in the consolidated repo's spout-behavior schema (NOT in legacy — never modify legacy). Add to `configs/defaults.yaml` `spout_behavior.criteria_slug_map` mapping legacy → new names. Write tests that confirm: (a) the mapping is bijective, (b) the new names are valid Python identifiers, (c) the mapping is stable across `defaults.yaml` reloads.
- **8a.2 — Lick-bout detector** (~100 lines src + ~80 lines tests). New module `src/stroke_orofacial/spout_behavior/lick_bouts.py`. Pattern: port from `find_running_bouts.py` (legacy). Inputs: lick sample-index array + Fs + `max_ili_ms` + `min_bout_licks`. Outputs: list of `LickBout(start_idx, end_idx, n_licks, mean_ili_s)` records. Synthetic-data tests covering: empty input, single-lick (below min), exactly-min-licks bout, multi-bout sequence with gaps at threshold boundaries.
- **8a.3 — Per-trial endpoint primitives** (~200 lines src + ~150 lines tests). Extend per-trial computation in a new module `src/stroke_orofacial/spout_behavior/endpoints_per_trial.py`. Implement: `directional_lick_accuracy_per_session()` (Q9 #6 — per-(L-trial, R-trial) split + fractions); `switch_cost_per_session()` (Q9 #5 — condition trial-N performance on trial-(N-1) reward side); `latency_variability_per_session()` (Q9 #8 — std + CV + IQR of first-lick-latency per session); `first_lick_latency_per_trial()` (Q9 #7 — re-package A10 to expose per-trial array). All take a per-session per-trial dataframe (built from Phase 2 outputs) and return per-session scalars or per-trial-type scalars.
- **8a.4 — Within-session endpoints** (~120 lines src + ~80 lines tests). New module `src/stroke_orofacial/spout_behavior/endpoints_within_session.py`. Implement: `within_session_learning_curve()` (Q9 #1 — bin trials by ordinal position, compute metric per bin, fit early-vs-late slope); `within_session_change()` (Q9 #4 — neutral-named per-trial-index trend slope on any per-trial metric).
- **8a.5 — Cross-session endpoint** (~60 lines src + ~50 lines tests). New module `src/stroke_orofacial/spout_behavior/endpoints_cross_session.py`. Implement: `inter_session_persistence()` (Q9 #2 — lag-1 autocorrelation of any per-session metric across an animal's session sequence; configurable lag).
- **8a.6 — Engagement extras** (~40 lines src + ~30 lines tests). Two endpoints surfaced by the archaeology that aren't in the original Q9 list but are cheap to add and scientifically valuable: `reward_trial_count_per_session()` (per-side trial counts — engagement metric) and OPTIONAL `inter_trial_interval_distribution()` (mean / median / std of consecutive-reward gaps per side). Decision on optional one comes from scoping decision Q4 above.
- **8a.7 — Output schema + per-session JSON writer** (~80 lines src + ~50 lines tests). New module `src/stroke_orofacial/spout_behavior/report_writer.py`. Define the Phase 8a per-session output dict schema combining: (a) renamed criteria booleans (8a.1 slug map applied), (b) all 8 Q9 endpoints (per-session aggregate views), (c) per-trial arrays where preserved (`first_lick_latency`, `directional_lick_accuracy`), (d) the engagement extras from 8a.6, (e) the existing A1–A12 endpoints re-emitted under their new slug names where renamed (no information loss vs legacy `report.json`). Per scoping decision Q6, write to `spout_endpoints_v2.json` per session by default.
- **8a.8 — Cohort recovery-trajectory plotting** (~250 lines src + ~80 lines tests + new notebook). New module `src/stroke_orofacial/spout_behavior/recovery_trajectories.py`. Functions: per-metric per-animal trajectory line (reuses `summary_PS.py`-style stroke-relative day axis); per-metric cohort-mean ± SEM band overlay; per-metric per-phenotype-grouped facet panels (default group = single "all" — Phase 9.1 plugs in by overriding the grouping function). Build the corresponding orchestration notebook at `notebooks/30_phase8a_spout_recovery_trajectories.ipynb` with USER INPUTS cell at top, follows the established notebook convention. Output figures land under `stroke_orofacial_pipeline_outputs/spout_behavior/recovery_trajectories/{endpoint}/{animal_or_cohort}.{png,svg}` (figure-type-first per Audit Item 9 layout — see #17 Phase 6.75 for the full reorg pattern; if 6.75 hasn't landed yet at Phase 8a execution time, write to the legacy layout and let 6.75 migrate).
- **8a.9 — Docs + tests + plot-walkthrough validation** (~100 lines docs + full test pass). Write the Phase 8a entry in `docs/MIGRATION_LOG.md` documenting: the 8 Q9 endpoints + their legacy status from the archaeology, the 4 criteria slug renames with the legacy→new mapping table, the 2 engagement-extra endpoints, the new output-JSON schema name, the cohort plotting layout, the phenotype-viz hook design. Add a DECISIONS.md entry closing out the Q2 slug rename and the Q3 viz-hook design as concrete decisions. Run `pytest` end-to-end (must pass), `ruff check` (must be clean). For the legacy-port endpoints (`first_lick_latency`, `directional_lick_accuracy` extension, the renamed criteria), include a parity-walkthrough section in the MIGRATION_LOG: pick PS46/20250307 (the workhorse session for parity), produce the Phase 8a per-session output, compare endpoint-by-endpoint against the legacy `report.json` from the existing `session_processing3/` cache, document expected vs unexpected differences (renames change keys; computations should match values).

Total: ~1000 lines src + ~600 lines tests + ~250 lines notebook + ~100 lines docs. Substantially bigger than 4.5-lite or 6.7. Plan-mode pause is mandatory; expect Priya to refine the sub-phase boundaries (likely fold 8a.4+8a.5+8a.6 if she wants tighter chunking, or split 8a.8 into per-animal-only first then add cohort-level if she wants an early review checkpoint).

### 4. Parity strategy

- **Full pytest suite passes before and after.** Phase 8a is mostly additive; existing tests should be unaffected.
- **Renamed-criteria parity.** For PS46/20250307 (the parity workhorse), the renamed `criteria_first_correct_lick_present` (was `criteria_3`) per-trial boolean array must equal the legacy `criteria_3` array byte-for-byte. Same for the other three criteria. This is a rename, not a recomputation — values must be identical.
- **`first_lick_latency` parity.** For PS46/20250307, the per-trial latency array under the new schema must equal the legacy `latency_bySession[date][side]` array within float-precision tolerance (the computations are pure division of integer index differences by integer Fs — exact equality is expected, but allow `1e-12` rtol for cross-platform float-summation jitter).
- **Existing per-session aggregate (A1–A12) continuity.** For each renamed legacy endpoint that Phase 8a re-emits, the per-session aggregate (mean / std / count) must equal the legacy `report.json` value within `1e-9` rtol. Document any discovered drift in MIGRATION_LOG.
- **No parity check for greenfield endpoints** — `within_session_*`, `inter_session_*`, `switch_cost`, `lick_bout_structure`, `latency_variability`, `directional_lick_accuracy` (extension), engagement extras: these have no legacy reference. Validation is via unit tests on synthetic fixtures + visual sanity check on PS46 trajectories during 8a.8.
- **Plot walkthrough validation.** During 8a.9, regenerate (with the new code) the legacy plots that A1–A12 contributed to (e.g., `criteria_performance` per-animal trajectory, `latency_bySession` per-animal trajectory) and compare visually side-by-side with the legacy `summary_PS.py` outputs for the same animal × date range. Any visible discrepancy = STOP and investigate.

### 5. Hardcoded constants

Likely-new constants to externalize into `configs/defaults.yaml` `spout_behavior.endpoints_v2` block (do NOT inline in source):

- `lick_bouts.max_ili_ms` (default per scoping decision Q3, ~250 ms)
- `lick_bouts.min_bout_licks` (default 2)
- `within_session_learning_curve.n_bins` (default 5? Decide at plan time)
- `within_session_change.detrend_method` (linear / loess / Theil-Sen — decide)
- `inter_session_persistence.lag` (default 1)
- `switch_cost.same_side_baseline_definition` (immediately-prior-trial vs N-back average)
- `late_lick_count_per_session.window_seconds_start` and `window_seconds_end` (defaults 8 and 60, matching legacy A11; promotion from hardcoded → config per scoping decision Q4)

The criteria thresholds (`fraction_pass`, `num_licks_correct_min`, `num_licks_incorrect_max`, `window`) are already in `configs/defaults.yaml` `spout_behavior.criteria` from earlier phases. Use those, do not duplicate.

## Implementation pattern — endpoint primitives

To keep the new endpoint modules consistent and testable, every per-session endpoint function should follow this signature shape:

```python
def <endpoint_name>_per_session(
    trials_df: pd.DataFrame,         # per-trial dataframe for ONE session (cols: trial_idx, reward_side, lick_indices, ...)
    *,
    config: SpoutEndpointsConfig,    # dataclass loaded from configs/defaults.yaml's spout_behavior.endpoints_v2 block
) -> EndpointResult:
    """Compute <endpoint> for a single session.

    Returns
    -------
    EndpointResult
        Has fields: per_session_aggregate (scalar or dict), per_trial_array (optional),
        per_trial_type_split (optional), provenance (config-snapshot for reproducibility).

    Notes
    -----
    Pure function: no I/O, no plotting, no global state. Caller (`report_writer.py`)
    handles JSON serialization. Caller (`recovery_trajectories.py`) handles plotting.
    """
    ...
```

This separation keeps endpoint computation independently testable from report-writing and from plotting. It also makes Phase 9 (stats) work straightforward — stats functions consume `EndpointResult` arrays across sessions.

For the cohort-trajectory plotting layer in 8a.8, the phenotype-grouping hook should look like:

```python
def plot_cohort_recovery_trajectory(
    endpoint_results: dict[Animal, dict[date, EndpointResult]],
    *,
    metric_extractor: Callable[[EndpointResult], float],
    grouping_function: Callable[[Animal], str] = lambda a: "all",  # default = single group
    align_to_stroke: bool = True,
) -> Figure:
    """One figure per metric. Grouping function maps animal → phenotype label.

    With the default grouping_function, all 8 animals land in one "all" group
    and the figure is a single panel with N=8 trajectories + cohort mean ± SEM.
    Phase 9.1 overrides grouping_function to map animal → fast/slow/non-recoverer
    and the figure becomes a 1×3 facet grid (one panel per phenotype) with
    per-phenotype mean ± SEM bands.
    """
    ...
```

The default-group fallback means Phase 8a's plots are immediately useful without phenotype labels, AND Phase 9.1 wires into the same plotting code by changing one parameter rather than retrofitting the layout.

## Exit criteria

- All pre-existing tests still pass (~218+ before Phase 8a; expect ~700+ after, given the new test suite).
- New unit tests for all 8 Q9 endpoints + 2 engagement extras pass on synthetic fixtures.
- New parity tests for the 4 renamed criteria (byte-identical boolean arrays vs legacy `report.json` for PS46/20250307) pass.
- New parity test for `first_lick_latency` per-trial array (vs legacy A10) within `1e-12` rtol passes.
- New parity tests for the renamed legacy aggregates (vs legacy `report.json` per-session means/stds) within `1e-9` rtol pass.
- `notebooks/30_phase8a_spout_recovery_trajectories.ipynb` runs end-to-end via `jupyter nbconvert --execute --inplace` against the 8-animal cohort, produces all per-animal and cohort-level figures.
- Per-session `spout_endpoints_v2.json` written for every (animal × session) covered by Phase 2 outputs.
- `ruff check` clean.
- `docs/MIGRATION_LOG.md` Phase 8a entry includes: the legacy-archaeology summary (already in `PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`, can cross-reference), the criteria-rename mapping table, the new endpoint list with one-line scientific definitions, the output-JSON schema documentation, the cohort plot layout, the phenotype-viz hook design, the parity-walkthrough section comparing PS46/20250307 against legacy.
- `docs/DECISIONS.md` entry closing out Q2 (slug rename — actual final names locked) and Q3 (Phase 8a viz-hook design — describe the grouping-function pattern).
- PR description includes: list of the 8 Q9 endpoints + status (greenfield / extension / re-package), the 4 criteria renames table, a small pre/post visual comparison for one per-animal A1–A12 trajectory (proves nothing visual broke).

## Constraints

- **Strictly additive in the source tree.** No changes to existing endpoint computations under `src/stroke_orofacial/spout_behavior/` from Phases 2 / 2.5. The renamed-criteria slugs apply to the new Phase 8a output schema only; the legacy `report.json` stays byte-stable (per scoping decision Q6 default).
- **Never modify legacy code.** The archaeology is read-only; anything found in `facerhythm_stroke_biomarker_exp_Priya/` or `facerhythm_stroke_biomarker_exp/` stays untouched. If a port reveals a legacy bug, document it in MIGRATION_LOG and ask Priya before fixing it (the bnpm vendoring precedent — bugs over upstream → fix with explicit documentation, but only after Priya signs off, not silently).
- **DLC-independent.** This phase uses Phase 2 + 2.5 outputs only. Do not touch `dlc_io/`, `dlc_spatial/`, or any DLC-derived data even if a tempting cross-reference suggests itself. DLC kinematic recovery trajectories are Phase 8b, separate, blocked on Phase 7.
- **Phenotype classification stays out.** The viz layer must support phenotype faceting via the `grouping_function` parameter, but no clustering / classification algorithm runs in Phase 8a. That's Phase 9.1.
- **Output paths.** If Phase 6.75 (output reorg, task #17) has merged before Phase 8a executes, use the figure-type-first layout established there. If not, write to the legacy layout and let 6.75 migrate. Do not pre-emptively reorganize.
- **One mid-phase checkpoint recommended.** After 8a.7 (per-session JSON writer) is done — i.e., end-to-end pipeline running for a single animal × session, all 8 endpoints computing, JSON writing — pause for Priya's review of the output schema before building 8a.8 (cohort plotting). This catches schema decisions that affect plotting before plotting is built.

If the implementation reveals an endpoint is more ambiguous than the Q9 spec captures (e.g., `within_session_learning_curve` could be defined as early-vs-late mean difference OR as a within-session linear-trend slope — both are reasonable), STOP and ask. Pick a default in the proposal but flag the alternative explicitly so Priya can override.
