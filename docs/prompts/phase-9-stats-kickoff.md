# Phase 9 Kickoff — Statistical Analyses on Phase 7c.2 + Kinematics + Spout Behavior Outputs (Behavioral Stats Scope)

**Branch:** `phase/9-stats` off latest `origin/main` (post-Phase-7d + post-F-P-7 close; current main HEAD `2d33043`, tag `v7-pre-alignment-templates`).
**Tag on phase-close merge:** `v9-stats-behavioral`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 7c.2 + Phase 7d + F-P-7 closed (all done as of 2026-05-22); CC has read `docs/prompts/phase-9-stats-scoping.md` (the prior scoping pass) and `docs/SCIENTIFIC_ENDPOINTS.md` (Audit Item 10 endpoint catalog) and the memory entries `project_phase_7c3_whole_session_and_npz_schema_forward_pointers.md` (compute-on-demand spatial), `project_eye_midpoint_convention.md`, and `feedback_iterative_addenda_pattern.md` (mid-phase re-spec etiquette).
**Estimated scope:** medium-to-large. Stats stub fill-in + endpoint inventory + comparison-axis test code + cohort run + summary figures + deferred per-mouse plot family wiring. ~12-18 commits, ~7-12 days CC wall time (excluding Priya scientific review).

**This kickoff supersedes `docs/prompts/phase-9-stats-scoping.md`** for execution. Where the two conflict, this kickoff wins; the scoping doc remains as historical record of the planning pass.

---

## Context

Phase 9 is the first phase in the consolidation that CONSUMES consolidated outputs rather than producing them. Phase 7c.2 + Phase 7a kinematics + Phase 8a.10 spout-behavior endpoints are all in canonical form on main. Phase 9 asks **whether the quantities those phases compute differ in scientifically-meaningful ways** between conditions.

**Scope narrowing (Q-lock vs scoping-doc OPEN-Q 9):** Phase 9 (this kickoff) covers **BEHAVIORAL STATS ONLY** — pre vs post-stroke, recovery time-course, L vs R asymmetry, trial-group effects on scalar endpoints. **Spatial-distribution stats** (per-bin or distribution-level OT-cost tests over centered parquets) are deferred to a future **Phase 9.x-spatial-stats** kickoff. Rationale: behavioral stats have a clear-headed methodology + an existing endpoint catalog (`docs/SCIENTIFIC_ENDPOINTS.md`); spatial stats need design discussion on cluster-corrections, OT cost calibration, baseline-bin selection, etc. Splitting gives Priya a clean review boundary at Phase 9 close before committing spatial methodology. The Phase 9.1 phenotype-pooled figures phase (scoping at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`) is downstream of both.

**Primary deliverable:**
1. `src/stroke_orofacial/stats/` — five existing module stubs filled with implementations (`models.py`, `multiple_comparisons.py`, `normalization.py`, `permutation.py`, `recovery_epochs.py`).
2. `pipeline_outputs/stats/` — materialized intermediate inputs parquet tree + per-axis results CSVs + summary figures.
3. Wired-in `recovery_trajectories` per-mouse plot family — discharges Phase 8a.10 forward-pointer for this family.
4. Tests + DECISIONS + MIGRATION_LOG.

---

## Locks from scoping-doc OPEN-Qs

All 12 OPEN-Qs from `docs/prompts/phase-9-stats-scoping.md` are resolved below. Any re-spec lands as a numbered Addendum per `feedback_iterative_addenda_pattern.md`.

**OPEN-Q 1 (direct-read vs materialize) — LOCK: MATERIALIZE.** Write a `pipeline_outputs/stats/inputs/` tree of pre-aggregated parquets, one row per (animal, date, trial, endpoint). Schema columns: `animal`, `date`, `rel_day`, `trial_idx`, `side` (L/R/all/global), `endpoint_slug`, `value`, `is_sentinel` (bool, captures Phase 8a.7.5 schema 2.0.0 sentinel handling), `cohort_bin_size` (2 or 7, from `configs/animals.yaml` `bin_days`). One parquet per `(endpoint_slug, animal)`. Rationale: cleaner test code; stable downstream interface for Phase 9.1 + pub-figures + Phase 10 audit; ~hundreds of MB at most (not a disk concern); decouples test logic from raw output-tree layout.

**OPEN-Q 2 (`stroke_side` metadata) — RESOLVED: use `AnimalInfo.stroke_laterality`** added in Phase 8a.10 (`configs/animals.yaml`, all 8 cohort animals currently `"L"`). Per-trial L/R semantics already correctly mouse-frame via `lr_convention.to_mouse_frame`. The ipsi/contra translation helper `mouse_side_to_ipsi_contra(side, stroke_laterality)` is on `AnimalInfo`. **§3.3 implication:** because all 8 current cohort animals are L-stroke, the "L vs R asymmetry" axis is currently a one-regime "ipsi vs contra" comparison. Test code must use `stroke_laterality` to label sides as ipsi/contra in output CSVs but cannot empirically test "stroke-side asymmetry varies with stroke-side" until the cohort grows. Frame results in ipsi/contra terms; document the single-regime caveat in DECISIONS.

**OPEN-Q 3 (spatial per-bin vs distribution-level) — DEFERRED.** Spatial stats land in Phase 9.x-spatial-stats (separate kickoff). Phase 9 ships zero spatial-stats code. Endpoint inventory (Task 1) tags spatial endpoints as `STATUS=deferred_phase_9x` but does not test them.

**OPEN-Q 4 (pool 2-day vs 7-day cohorts) — LOCK: POOL with `cohort_bin_size` as fixed effect.** Cohort bin size (2 vs 7) is a fixed effect in the mixedlm: `endpoint ~ rel_day + cohort_bin_size + (1 | animal)`. For paired pre-post tests, pool the within-animal pairs across cohorts (Wilcoxon is rank-based and robust to cohort-level scale differences). Sensitivity addenda: per-cohort stratified analysis output as a separate CSV (`results_by_cohort_bin_size.csv`), flagged in Task 6 verification if any endpoint shows pooled-vs-stratified divergence > Cohen's d 0.3.

**OPEN-Q 5 (one default per axis vs sensitivity) — LOCK: ONE DEFAULT, opt-in sensitivity.** Defaults:
- Paired pre-post: Wilcoxon signed-rank (`scipy.stats.wilcoxon`) on within-animal-paired endpoint values.
- Recovery time-course: linear mixed-effects (`statsmodels.formula.api.mixedlm`) with random intercept per animal; bootstrap CIs (n=10k, BCa).
- L vs R asymmetry: within-animal Wilcoxon signed-rank on (L_value - R_value) differences per session, aggregated to per-animal means.
- Trial-group effects (all/L/R bias): Friedman test (`scipy.stats.friedmanchisquare`) on within-session paired groups; post-hoc Wilcoxon with BH-FDR.

Sensitivity analyses (t-test alternatives, robust regression, etc.) are gated behind `--sensitivity` CLI flag; off by default.

**OPEN-Q 6 (confirmatory vs exploratory) — LOCK: FDR-EXPLORATORY DEFAULT.** All tests are exploratory + BH-FDR-corrected at q=0.05 within comparison family by default. Per-endpoint CONFIRMATORY tagging is captured in the endpoint inventory CSV (Task 1) — Priya stamps `is_confirmatory: bool` per row; CONFIRMATORY-tagged endpoints additionally get Bonferroni family-wise control reported alongside FDR. This means no pre-registration commitment is implied by Phase 9; the inventory becomes the pre-registration artifact if/when Priya wants one later.

**OPEN-Q 7 (n_permutations) — LOCK: 10k default.** CLI knob `--n-permutations` accepts higher for headline tests; per-test override available via endpoint-inventory column `n_permutations_override: int | null` (Priya stamps; default null = 10k).

**OPEN-Q 8 (Bayesian methods) — LOCK: NO.** Frequentist-only in Phase 9. `pymc` is out of scope. Bayesian methods (BEST, hierarchical Bayes) deferred to a possible future Phase 9.y if the paper needs them.

**OPEN-Q 9 (split into sub-phases) — LOCK: SPLIT.** Phase 9 = behavioral stats (this kickoff). Phase 9.x-spatial-stats = future kickoff for spatial-distribution tests over centered parquets. Phase 9.1 phenotype-pooled figures = already-drafted separate phase consuming Phase 9 outputs.

**OPEN-Q 10 (primary endpoints) — LOCK: Task 1 audit + Priya stamping.** CC enumerates every analyzable endpoint from `docs/SCIENTIFIC_ENDPOINTS.md` Category A (26 endpoints catalog) + Phase 8a.10 ported set (11 plot families) + Phase 8a.10 deferred set (5 trimmed plot families + `recovery_trajectories`). Output `.scratch_phase_9/endpoint_inventory.csv` columns: `endpoint_slug`, `category`, `legacy_source`, `consolidated_source`, `is_primary: bool`, `is_confirmatory: bool`, `n_permutations_override: int | null`, `comparison_axes_in_scope: list[str]`, `notes`. **STOP-and-report after Task 1** for Priya stamping; Task 2 onward proceeds against the stamped CSV.

**OPEN-Q 11 (publication strategy) — LOCK: OUT OF SCOPE.** Priya owns. Phase 9 produces results-as-data; paper-figure organization is a separate concern.

**OPEN-Q 12 (cross-validation / classifier work) — LOCK: NO.** Phase 9 is purely descriptive inferential stats. No classifier work.

---

## Recovery-trajectories cross-module organization (Option C lock — Cowork verdict 2026-05-23)

Three layers + a code-split per Option C from Cowork warm-start verdict 2026-05-23:

| Layer | Module | Owns | Phase |
|---|---|---|---|
| Descriptive trajectories | `spout_behavior/recovery_trajectories.py` | `discover_endpoint_jsons`, `load_endpoint_payload`, `extract_endpoint_metric`, `build_trajectory_points`, `summarize_cohort`, `plot_recovery_trajectories` (descriptive only — scatter + cohort mean ± SEM) | Phase 8a.8 (on main) |
| Inferential fit | `stats/models.py` | `fit_recovery_mixedlm(points, group_by="animal") → FitResult` (this kickoff) | Phase 9 |
| Trajectory + fit visualization | `spout_behavior/recovery_trajectories.py` | `plot_recovery_trajectories_with_fit(points, fit_result, ...)` (this kickoff) | Phase 9 extends Phase 8a.8 |
| Phenotype + epoch labels | `stats/recovery_epochs.py` | Phenotype classification (mild/moderate/severe based on acute-window endpoint values) + epoch assignment (pre/acute/sub-acute/chronic time windows) | Phase 9 (foundational for Phase 9.1) |

`fit_recovery_mixedlm` does the math; `plot_recovery_trajectories_with_fit` takes the precomputed `FitResult` and overlays it. The Phase 8a.10-deferred per-mouse `recovery_trajectories` plot family wires up as:

```python
points = build_trajectory_points(...)
fit = fit_recovery_mixedlm(points)
fig = plot_recovery_trajectories_with_fit(points, fit, ...)
```

No FitResult parquet materialization required for this path (the FitResult is threaded directly), but `pipeline_outputs/stats/results/recovery/` does emit a CSV row per (endpoint, group) for downstream Phase 9.1 + pub-figures consumers.

`stats/recovery_epochs.py` (phenotype + epoch assignment) is **scaffolding** — Phase 9 implements the classification + assignment but Phase 9.1 is the primary consumer. Phase 9 uses epoch labels in stats output CSVs (so pre/post/acute/chronic windows are addressable downstream) but does not stratify tests by phenotype (the cohort is too small: 9 animals, all L-stroke).

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Not applicable as a port. `docs/SCIENTIFIC_ENDPOINTS.md` Audit Item 10 already cataloged the 26 legacy endpoints with canonical source pointers. Task 1 audit reads that catalog and the Phase 8a.10 ported/deferred sets — no legacy disambiguation needed at the source level.

Legacy stats code in the legacy repos (`playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 + `behavior_report_PS::compute_stats_p_values_*`) is **NOT being ported.** Phase 9 is net-new statistical machinery using current best-practice methods (mixed-effects, FDR, permutation null). Legacy paired t-test cells are reference-only for endpoint-set determination, not for methodology.

### Dead code identification

The five `stats/` stubs on main are scaffolding to be filled, not dead code:
- `models.py` — fill with mixedlm + bootstrap CI + Wilcoxon wrappers.
- `multiple_comparisons.py` — fill with BH-FDR + Bonferroni helpers (thin wrappers around `statsmodels.stats.multitest`).
- `normalization.py` — fill with z-score / ratio / difference / log1p / rank baseline normalizers.
- `permutation.py` — fill with paired and unpaired permutation null + p-value computation.
- `recovery_epochs.py` — fill with phenotype classifier + epoch-label assignment.

Each existing docstring-only `__init__.py` and per-module file becomes ~150-400 lines on Task 3 close.

### Sub-phase breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch | (none) | 0 | <5 min |
| Task 1 — Endpoint inventory + per-animal epoch-boundary stamping (STOP-and-report) | `.scratch_phase_9/endpoint_inventory.csv` (CC writes, Priya stamps) + `.scratch_phase_9/proposed_epoch_boundaries.yaml` (CC drafts, Priya edits) | 1 | 2-3 hr CC + Priya review |
| Task 1.5 — `AnimalInfo.epoch_boundaries` schema extension + stamped YAML lands | `src/stroke_orofacial/animals.py` schema bump + `configs/animals.yaml` per-animal blocks + 8-10 schema tests | 1 | 2-3 hr |
| Task 2 — Stats inputs materialization | `pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet` tree + emit driver script | 2-3 | 1-2 days |
| Task 3 — Stats module fill-in (5 modules) | `src/stroke_orofacial/stats/*.py` filled + per-module tests | 4-6 | 3-5 days |
| Task 4 — Per-axis test runners | `pipeline_outputs/stats/results/<axis>/<endpoint_slug>.csv` for each of 4 axes (pre-post, recovery, L-R/ipsi-contra, trial-group) | 2-3 | 2-3 days |
| Task 5 — Cohort-wide test run | All inventory PRIMARY endpoints × all in-scope axes → results CSVs | 1 | 30-60 min cohort compute |
| Task 6 — Per-mouse `recovery_trajectories` plot family wire-up (discharge Phase 8a.10 forward-pointer) | Plot family added to per-mouse plot grid via `plot_recovery_trajectories_with_fit` | 1-2 | 1-2 days |
| Task 7 — Stats summary figures | Forest plots, recovery curves with CIs, distribution summaries — `pipeline_outputs/stats/figures/` | 2-3 | 2-3 days |
| Task 8 — Verification / sanity gate (STOP-and-report) | `.scratch_phase_9/verdict.md` + Priya scientific review | 0 | 1-3 days (Priya bandwidth) |
| Task 9 — DECISIONS + MIGRATION_LOG + PR | 2 docs files + PR open | 1 | 30-60 min |

**Estimated total: ~14-20 commits, ~10-15 days CC wall time** (excluding Priya scientific review time).

### Parity strategy

No legacy parity gate is meaningful for Phase 9 — legacy paired t-test code is being replaced by best-practice methodology, not faithfully ported. Verification is instead:

1. **Methodology sanity:** for each of the 4 comparison axes, hand-pick 2-3 endpoints where Priya has prior intuition about the expected direction + rough magnitude (e.g., `criteria_3_pass_fraction` drops post-stroke); confirm Phase 9 tests recover the expected direction. Documented in Task 8 verdict.
2. **Internal consistency:** the same endpoint tested via Phase 9 default method should give numerically-similar (within 0.1 effect-size units) results to the legacy paired t-test on the same data subset, for endpoints where the legacy test is methodologically defensible (i.e., not the spatial endpoints). Task 8 spot-checks 3-5 endpoints this way.
3. **Permutation-null reproducibility:** fixing `random_state` reproduces the same null distribution byte-equally. Unit test in `test_permutation.py`.

### Hardcoded constants

All cohort-uniform thresholds + defaults move into `configs/defaults.yaml` under a new `stats:` top-level key:

```yaml
stats:
  fdr_q: 0.05
  bonferroni_alpha: 0.05
  n_permutations_default: 10_000
  bootstrap_n: 10_000
  bootstrap_ci_method: "BCa"
  mixedlm_re_formula: "1"  # random intercept only by default
  mixedlm_groups: "animal"
  rel_day_pre_stroke_max: 0  # rel_day <= 0 is pre-stroke pool (cohort-uniform; pre-stroke is anatomically defined)
  rel_day_post_stroke_min: 1  # rel_day >= 1 is post-stroke pool (cohort-uniform)
```

**Acute / sub-acute / chronic boundaries are PER-ANIMAL, not cohort-uniform** — see `epoch_boundaries` schema extension below.

Per-cohort `bin_days` already in `configs/animals.yaml` per `AnimalInfo.bin_days` (Phase 7a.4 day-binned).

### `AnimalInfo.epoch_boundaries` + `recovery_phenotype` schema extensions (Phase 9 lock, 2026-05-23)

Two per-animal experimenter-judgment fields land. The `recovery_phenotype` field already exists in `configs/animals.yaml` (currently null on all 8 animals); the loader extends to validate against a 4-tier enum. The `epoch_boundaries` field is new.

```python
RecoveryPhenotype = Literal["mild", "moderate", "moderate-severe", "severe"]

@dataclass(frozen=True)
class EpochBoundaries:
    """Per-animal recovery-epoch day boundaries.

    Reflects experimenter judgment of each animal's recovery trajectory.
    All values are days-relative-to-stroke (rel_day = 1 is the first
    post-stroke day; pre-stroke is rel_day <= 0). Each epoch's bounds
    are inclusive.

    Schema:
        acute     = [1, acute_max_rel_day]
        sub_acute = [acute_max_rel_day + 1, subacute_max_rel_day]
        chronic   = [chronic_min_rel_day, +inf)

    Constraints:
        acute_max_rel_day >= 1
        subacute_max_rel_day >= acute_max_rel_day + 1
        chronic_min_rel_day >= subacute_max_rel_day + 1

    `chronic_min_rel_day` may be larger than `subacute_max_rel_day + 1`
    when the experimenter wants a transitional gap that isn't
    categorized — `assign_epoch_label` returns None for rel_day in
    (subacute_max_rel_day, chronic_min_rel_day) exclusive. Animals that
    never reach chronic (plateau before recovery) get
    `chronic_min_rel_day` set to a sentinel beyond max(rel_day) in their
    dataset (e.g. 9999), which yields epoch_label="sub_acute" for all
    post-stroke sessions.

    Note on data-availability gaps: gaps in rel_day caused by missing
    sessions (e.g. no recorded data on rel_day 18-19 for severe animals)
    are NOT encoded in the boundary schema — sub-acute simply begins at
    acute_max+1 regardless of whether sessions exist on that day. The
    schema represents epoch INTENT; per-session epoch_label assignment
    happens at materialization (Task 2) using only days where sessions
    actually exist.

    Locked per Phase 9 kickoff 2026-05-23 design discussion. Stamped
    manually by Priya in configs/animals.yaml (Task 1 STOP-and-report
    gate). Data-derived alternatives explicitly rejected in favor of
    explicit-judgment auditability (Option 1 vs Options 2/3 of the
    2026-05-23 discussion).
    """
    acute_max_rel_day: int
    subacute_max_rel_day: int
    chronic_min_rel_day: int
```

YAML shape (all 8 cohort animals stamped 2026-05-23 in `configs/animals.yaml`):

```yaml
# Mild (PS47, PS48, PS49, PS50)
recovery_phenotype: "mild"
epoch_boundaries:
  acute_max_rel_day: 1     # acute = rel_day 1
  subacute_max_rel_day: 4  # sub-acute = rel_day 2..4
  chronic_min_rel_day: 5   # chronic = rel_day >= 5

# Moderate (PS46)
recovery_phenotype: "moderate"
epoch_boundaries:
  acute_max_rel_day: 5     # acute = rel_day 1..5
  subacute_max_rel_day: 8  # sub-acute = rel_day 6..8
  chronic_min_rel_day: 9   # chronic = rel_day >= 9

# Moderate-severe (PS51)
recovery_phenotype: "moderate-severe"
epoch_boundaries:
  acute_max_rel_day: 6      # acute = rel_day 1..6
  subacute_max_rel_day: 30  # sub-acute = rel_day 7..30
  chronic_min_rel_day: 31   # chronic = rel_day >= 31

# Severe — PS54 (laser 3.0 mW)
recovery_phenotype: "severe"
epoch_boundaries:
  acute_max_rel_day: 17     # acute = rel_day 1..17
  subacute_max_rel_day: 39  # sub-acute = rel_day 18..39 (no recorded sessions d18-19)
  chronic_min_rel_day: 40   # chronic = rel_day >= 40

# Severe — PS55 (laser 5.0 mW; longer recovery → boundaries shifted +10d vs PS54)
recovery_phenotype: "severe"
epoch_boundaries:
  acute_max_rel_day: 17     # acute = rel_day 1..17
  subacute_max_rel_day: 49  # sub-acute = rel_day 18..49 (data range d20-49)
  chronic_min_rel_day: 50   # chronic = rel_day >= 50
```

**Note on shared phenotype, divergent boundaries:** PS54 and PS55 carry the same `recovery_phenotype = "severe"` but different `epoch_boundaries` — phenotype labels are categorical clinical judgments; epoch boundaries reflect the actual recovery timeline observed per animal. Phase 9.1 phenotype-pooled figures that group by phenotype must NOT assume identical epoch boundaries within a phenotype tier.

**The stamped YAML is already on the branch (committed 2026-05-23 by Cowork in this kickoff session).** Task 1 Part B's "CC drafts + Priya edits" sub-step is consequently a NO-OP for this phase — the stamping happened during kickoff drafting. CC's job in Task 1.5 is to extend the schema + add the validator + write tests, then verify the existing stamped YAML round-trips through the loader. The Task 1 STOP-and-report gate retains the endpoint-inventory stamping (Part A) but the epoch-boundary stamping (Part B) is pre-completed.

Phenotype distribution in the current cohort: mild=4 (PS47, PS48, PS49, PS50); moderate=1 (PS46); moderate-severe=1 (PS51); severe=2 (PS54, PS55). This distribution influences Phase 9.1 phenotype-pooled figures design — with n=4 in the largest group and n=1 in two of four groups, phenotype-stratified inferential tests are not in Phase 9 scope (consistent with the existing kickoff lock that Phase 9 doesn't stratify by phenotype).

---

## Tasks

### Task 0 — Setup + branch

```bash
git fetch origin
git checkout main
git pull
git checkout -b phase/9-stats
conda activate stroke_orofacial
which python                            # must print a path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"     # must succeed
pytest --collect-only                   # must complete without errors
```

### Task 1 — Endpoint inventory + per-animal epoch-boundary stamping (STOP-and-report)

This task gates Task 2 on TWO Priya-stamping artifacts: the endpoint inventory CSV AND the per-animal `epoch_boundaries` blocks in `configs/animals.yaml`. CC drafts both; Priya stamps both; Task 2 proceeds against the stamped artifacts.

**Part A — Endpoint inventory.** CC writes `.scratch_phase_9/endpoint_inventory.csv` enumerating every analyzable endpoint:

**Sources to walk:**
1. `docs/SCIENTIFIC_ENDPOINTS.md` Category A (26 endpoints) — primary source.
2. Phase 8a.10 ported set (11 plot families) — from `src/stroke_orofacial/spout_behavior/visual_gate.py`.
3. Phase 8a.10 deferred set (5 trimmed plot families + `recovery_trajectories`) — from Phase 8a.10 forward-pointer in `docs/MIGRATION_LOG.md`.
4. Phase 7a kinematics per-trial endpoints — `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` + `jaw_pertrial.py` (read `EndpointResult` dataclass field names).
5. Phase 7a tongue-jaw mismatch endpoints — `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`.

**Inventory CSV columns** (CC fills all except `is_primary`, `is_confirmatory`, `n_permutations_override`, `comparison_axes_in_scope` which Priya stamps):

| Column | Type | Source |
|---|---|---|
| `endpoint_slug` | str | Canonical slug per `criteria_slugs.py` or analogous |
| `category` | str | Category A/B/C from `SCIENTIFIC_ENDPOINTS.md`, or "kinematics-tongue", "kinematics-jaw", "tongue_jaw_mismatch", "recovery" |
| `legacy_source` | str | e.g. `behavior_report_PS.py:455–480` |
| `consolidated_source` | str | e.g. `spout_behavior/endpoints_within_session.py::compute_criteria_3` |
| `materialized_path_template` | str | e.g. `stats/inputs/criteria_3_pass_fraction/<animal>.parquet` |
| `value_type` | enum | `scalar_per_session`, `scalar_per_trial`, `vector_per_trial`, etc. |
| `is_primary` | bool | **Priya stamps** |
| `is_confirmatory` | bool | **Priya stamps** |
| `n_permutations_override` | int | null | **Priya stamps** (default null = use config) |
| `comparison_axes_in_scope` | comma-sep str | **Priya stamps**; subset of {`pre_post`, `recovery`, `ipsi_contra`, `trial_group`} |
| `notes` | str | CC observations + flags for Priya |

**Part B — Per-animal epoch-boundary + recovery_phenotype stamping.** **PRE-COMPLETED 2026-05-23 by Cowork in `configs/animals.yaml`** (see schema section above for cohort distribution). CC's Task 1 has no Part B drafting work — the stamped values are already on the branch. Task 1.5 picks up the schema + validator + tests work; loader is verified to round-trip the existing stamped YAML.

**STOP-and-report.** Post the endpoint inventory CSV to Priya — she stamps `is_primary`, `is_confirmatory`, `n_permutations_override`, `comparison_axes_in_scope` per row. Task 2 proceeds against the stamped inventory.

### Task 1.5 — `AnimalInfo.epoch_boundaries` + `recovery_phenotype` schema extensions

One focused commit:

1. **Schema bump** in `src/stroke_orofacial/animals.py`:
   - Add `EpochBoundaries` frozen dataclass per the "Hardcoded constants" section above.
   - Add `epoch_boundaries: EpochBoundaries` field to `AnimalInfo` — REQUIRED (no default).
   - Tighten `recovery_phenotype` field type from `str | None` to `RecoveryPhenotype | None` where `RecoveryPhenotype = Literal["mild", "moderate", "moderate-severe", "severe"]`. Field remains optional in the dataclass for forward compatibility with future cohort animals where the phenotype hasn't been stamped yet, but the loader RAISES on a non-null value that isn't in the enum.
2. **Loader update** in `src/stroke_orofacial/config_loader.py`:
   - Parse the `epoch_boundaries` YAML block; validate `chronic_min_rel_day > subacute_max_rel_day ≥ acute_max_rel_day + 1 ≥ 2` (equivalently: acute_max ≥ 1 AND each next bound is strictly larger).
   - Validate `recovery_phenotype ∈ {None, "mild", "moderate", "moderate-severe", "severe"}`.
   - Raise `ConfigValidationError` on violation.
3. **Tests** in `tests/test_animals.py`:
   - Schema-roundtrip for all 8 current cohort animals (loader reads the stamped YAML, produces the expected `EpochBoundaries` + `recovery_phenotype` values per the schema-section reference table).
   - Validation-violation cases: `acute_max_rel_day = 0`, `subacute_max < acute_max`, `chronic_min ≤ subacute_max`, `recovery_phenotype = "wild"` (typo).
   - Phenotype distribution sanity test: cohort has exactly {mild: 4, moderate: 1, moderate-severe: 1, severe: 2}.

The stamped YAML is already on the branch (2026-05-23 by Cowork); this task is the schema-side of that landing.

Per CLAUDE.md Ground Rule 8 (pre-commit branch check), verify `git branch --show-current` shows `phase/9-stats` before commit.

**STOP-and-report** if any stamped value fails the new validator on first import — could indicate a YAML typo that Cowork's 2026-05-23 edit introduced.

### Task 2 — Stats inputs materialization

Write a driver script `scripts/phase_9_stats/materialize_inputs.py` that walks the stamped inventory and, for each `is_primary=True` endpoint, emits a per-(endpoint, animal) parquet at `pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet`.

**Schema** (one row per (animal, date, trial_idx, side) tuple):
- `animal: str` (e.g. `"PS46"`)
- `date: date32` (session date)
- `rel_day: int` (days since stroke per `AnimalInfo.stroke_date`)
- `trial_idx: int | null` (null for session-aggregate endpoints)
- `side: enum` (`"L"`, `"R"`, `"all"`, `"global"`; mouse-frame per `lr_convention.to_mouse_frame`)
- `ipsi_contra: enum` (`"ipsi"`, `"contra"`, `"all"`, `"global"`; computed via `mouse_side_to_ipsi_contra(side, stroke_laterality)`)
- `endpoint_slug: str`
- `value: float64 | null` (null for sentinel cases per Phase 8a.7.5 schema 2.0.0)
- `is_sentinel: bool` (true if sentinel-coded missing per schema 2.0.0)
- `cohort_bin_size: int` (2 or 7 from `AnimalInfo.bin_days`)
- `epoch_label: enum | null` (`"pre"`, `"acute"`, `"sub_acute"`, `"chronic"`; computed via `stats.recovery_epochs.assign_epoch_label(rel_day)`; null if not yet implemented — Task 3 chains)

Per CLAUDE.md Rule 6, writes go to `pipeline_outputs/stats/inputs/` (a NEW output directory).

**Manifest:** `.scratch_phase_9/materialize_manifest.csv` columns `endpoint_slug, animal, status, n_rows, n_sentinel, output_path, wall_time_s`. Resumable.

**Expected cohort scale:** ~30 PRIMARY endpoints × 8 animals = ~240 parquets, ~10k-100k rows each → ~100-500 MB total tree.

### Task 3 — Stats module fill-in

Five modules to implement. Each gets its own commit + per-module test file.

**Task 3a — `stats/normalization.py`** (1 commit, ~150 lines + tests):
```python
def zscore_to_baseline(values: ArrayLike, baseline_mean: float, baseline_std: float) -> NDArray:
    ...
def ratio_to_baseline(values: ArrayLike, baseline_mean: float) -> NDArray:
    ...
def difference_from_baseline(values: ArrayLike, baseline_mean: float) -> NDArray:
    ...
def log1p_transform(values: ArrayLike) -> NDArray:
    ...
def rank_within_animal(per_animal_values: Mapping[str, ArrayLike]) -> dict[str, NDArray]:
    ...
def per_animal_baseline_stats(
    points: Iterable[TrajectoryPoint],
    pre_stroke_filter: Callable[[TrajectoryPoint], bool] | None = None,
) -> dict[str, dict[Literal["mean", "std", "median", "iqr"], float]]:
    """Return per-animal baseline (rel_day <= rel_day_pre_stroke_max) statistics."""
```

**Task 3b — `stats/recovery_epochs.py`** (1 commit, ~120 lines + tests). The schema extension itself landed in Task 1.5; this task implements the epoch-label consumer. **No data-derived phenotype classifier is implemented** — `recovery_phenotype` is experimenter-stamped in `configs/animals.yaml` (loaded via `AnimalInfo.recovery_phenotype`); Phase 9 + 9.1 consumers read the stamped value rather than computing one.

```python
def assign_epoch_label(
    rel_day: int, animal_info: AnimalInfo
) -> Literal["pre", "acute", "sub_acute", "chronic"] | None:
    """Per-row epoch label from rel_day + per-animal boundaries.

    Returns 'pre' for rel_day <= 0 (cohort-uniform pre-stroke threshold
    from defaults.yaml stats.rel_day_pre_stroke_max).

    Returns None for rel_day in the optional transitional gap between
    subacute_max_rel_day and chronic_min_rel_day (exclusive on both
    ends) when the experimenter has stamped a gap. For the current
    2026-05-23 cohort, no animal has such a gap — all transitions are
    immediate (chronic_min_rel_day == subacute_max_rel_day + 1).
    """

def assign_epoch_labels_to_inputs_df(
    inputs_df: pd.DataFrame, animals: Mapping[str, AnimalInfo]
) -> pd.DataFrame:
    """Add epoch_label column to a stats inputs DataFrame in one pass.

    Joins on `animal` column to pick the right per-animal
    EpochBoundaries before applying assign_epoch_label per row.
    """

def cohort_phenotype_summary(
    animals: Mapping[str, AnimalInfo],
) -> dict[Literal["mild", "moderate", "moderate-severe", "severe"], list[str]]:
    """Return {phenotype: [animal_ids]} from stamped AnimalInfo.recovery_phenotype.

    Used by Phase 9.1 phenotype-pooled figures. Phase 9 does NOT
    stratify its primary tests by phenotype (cohort too small: mild=4,
    moderate=1, moderate-severe=1, severe=2 as of 2026-05-23).
    """
```

**Task 3c — `stats/multiple_comparisons.py`** (1 commit, ~120 lines + tests):
```python
def benjamini_hochberg_fdr(
    p_values: ArrayLike, q: float = 0.05
) -> tuple[NDArray, NDArray]:
    """Return (reject: bool array, q_values: float array)."""

def bonferroni_correct(p_values: ArrayLike, alpha: float = 0.05) -> tuple[NDArray, NDArray]:
    """Return (reject: bool array, adjusted_alpha: float)."""

def apply_correction_to_results_df(
    df: pd.DataFrame,
    p_col: str = "p_value",
    family_col: str = "comparison_axis",
    method: Literal["bh_fdr", "bonferroni"] = "bh_fdr",
    q: float = 0.05,
) -> pd.DataFrame:
    """Apply correction WITHIN each family_col group; add q_value + reject columns."""
```

**Task 3d — `stats/permutation.py`** (1 commit, ~200 lines + tests):
```python
def paired_permutation_null(
    paired_diffs: ArrayLike,
    n_permutations: int = 10_000,
    random_state: int | None = None,
    test_statistic: Callable[[ArrayLike], float] = np.mean,
) -> NDArray:
    """Null distribution for paired permutation test (sign-flip permutation)."""

def unpaired_permutation_null(
    group_a: ArrayLike,
    group_b: ArrayLike,
    n_permutations: int = 10_000,
    random_state: int | None = None,
    test_statistic: Callable[[ArrayLike, ArrayLike], float] = lambda a, b: np.mean(a) - np.mean(b),
) -> NDArray:
    """Null distribution via label permutation."""

def permutation_p_value(
    observed_stat: float, null_distribution: ArrayLike, *, tail: Literal["two", "left", "right"] = "two"
) -> float:
    """One- or two-tailed p-value from observed statistic + null distribution."""

def bootstrap_ci(
    values: ArrayLike,
    statistic: Callable[[ArrayLike], float] = np.mean,
    *,
    n_bootstrap: int = 10_000,
    ci: float = 0.95,
    method: Literal["BCa", "percentile"] = "BCa",
    random_state: int | None = None,
) -> tuple[float, float]:
    """Bias-corrected accelerated bootstrap CI."""
```

**Task 3e — `stats/models.py`** (1-2 commits, ~400 lines + tests):
```python
@dataclass(frozen=True)
class FitResult:
    """Standardized result container for any Phase 9 fit (mixedlm, wilcoxon, etc.)."""
    endpoint_slug: str
    comparison_axis: str  # "pre_post" | "recovery" | "ipsi_contra" | "trial_group"
    n_observations: int
    n_animals: int
    test_statistic: float
    p_value: float
    p_value_method: str  # "asymptotic" | "permutation" | "bootstrap"
    effect_size: float
    effect_size_metric: str  # "cohens_d" | "slope" | "log_odds" | ...
    ci_lower: float
    ci_upper: float
    ci_method: str
    extra: dict[str, Any]  # method-specific extras (e.g. mixedlm full fit summary)

def fit_paired_pre_post_wilcoxon(
    inputs_df: pd.DataFrame,
    endpoint_slug: str,
    *,
    pre_post_col: str = "epoch_label",
    pre_label: str = "pre",
    post_label: Literal["acute", "sub_acute", "chronic"] | str = "acute",
    bootstrap_ci: bool = True,
) -> FitResult: ...

def fit_recovery_mixedlm(
    inputs_df: pd.DataFrame,
    endpoint_slug: str,
    *,
    rel_day_min: int = 1,  # post-stroke only
    re_formula: str = "1",  # random intercept; "1 + rel_day" for random slope
    include_cohort_fixed_effect: bool = True,
    bootstrap_ci: bool = True,
) -> FitResult: ...

def fit_ipsi_contra_wilcoxon(
    inputs_df: pd.DataFrame,
    endpoint_slug: str,
    *,
    aggregate_to_animal_mean: bool = True,
    bootstrap_ci: bool = True,
) -> FitResult: ...

def fit_trial_group_friedman(
    inputs_df: pd.DataFrame,
    endpoint_slug: str,
    *,
    trial_group_levels: tuple[str, ...] = ("all", "L", "R"),
    posthoc_wilcoxon: bool = True,
) -> FitResult: ...
```

All four fitters return a `FitResult`; serialization to CSV rows is via `results_df_row()` helper.

**Test plan per module:** unit tests with synthetic data where ground-truth is known (e.g. paired Wilcoxon on data with known shift; mixedlm on data with known slope; permutation null with `random_state` reproducibility check).

### Task 4 — Per-axis test runners

For each of the 4 in-scope comparison axes, write a per-axis runner in `scripts/phase_9_stats/run_axis_<axis>.py`:

- `run_axis_pre_post.py`: walks PRIMARY inventory with `pre_post` in `comparison_axes_in_scope`; calls `fit_paired_pre_post_wilcoxon` for each; emits `pipeline_outputs/stats/results/pre_post/<endpoint_slug>.csv` and a master `pipeline_outputs/stats/results/pre_post/_all.csv`.
- `run_axis_recovery.py`: same shape; calls `fit_recovery_mixedlm`; emits `pipeline_outputs/stats/results/recovery/`.
- `run_axis_ipsi_contra.py`: calls `fit_ipsi_contra_wilcoxon`; emits `pipeline_outputs/stats/results/ipsi_contra/`. Document in DECISIONS the single-stroke-laterality caveat (all 8 animals L-stroke).
- `run_axis_trial_group.py`: calls `fit_trial_group_friedman`; emits `pipeline_outputs/stats/results/trial_group/`.

Each runner applies multiple-comparisons correction WITHIN the axis before writing the master CSV.

### Task 5 — Cohort-wide test run

Driver: `scripts/phase_9_stats/run_all_axes.py` invokes all 4 axis runners sequentially against the full PRIMARY inventory. Per-run wall-time estimate logged. STOP-and-report on any axis-runner failure.

### Task 6 — `recovery_trajectories` per-mouse plot family wire-up

Discharges Phase 8a.10 forward-pointer for the `recovery_trajectories` plot family.

1. **Extend `spout_behavior/recovery_trajectories.py`** with `plot_recovery_trajectories_with_fit(points, fit_result, *, ax=None, **plot_kwargs) -> Figure`. Overlays the FitResult's predicted mean (with bootstrap CI ribbon) on the existing scatter + mean/SEM plot.

2. **Wire into `spout_behavior/visual_gate.py`** as a new per-mouse plot family `recovery_trajectories`. The Phase 8a.10 cohort-summary tile-grid (`spout_behavior/cohort_summary.py`) gains a corresponding tile. Per-mouse panel grid loops over PRIMARY endpoints with `recovery` in `comparison_axes_in_scope`.

3. **Notebook integration:** add a `INCLUDE_RECOVERY_TRAJECTORIES = True` knob in `notebooks/01_spout_behavior_figures.ipynb` USER INPUTS cell. Re-render cohort.

4. **Visual gate verdict:** Priya eyeballs the cohort tile-grid + 1-2 per-mouse panels; verdict captured in Task 8 `verdict.md`.

### Task 7 — Stats summary figures

Land in a new module `src/stroke_orofacial/figures/stats_summary.py`. Three figure families:

1. **Forest plot per axis** — y-axis = endpoint, x-axis = effect size with 95% CI. One figure per comparison axis.
2. **Recovery curves with CIs** — per primary endpoint, mean recovery trajectory with bootstrap CI ribbon, overlaid on per-animal scatter.
3. **Pre-post distribution summary** — per primary endpoint, paired-difference distribution with Wilcoxon p-value annotation.

All figures write to `pipeline_outputs/stats/figures/`. Save both `.svg` (vector) and `.png` (raster, dpi=200) per existing convention.

### Task 8 — Verification / sanity gate (STOP-and-report)

CC writes `.scratch_phase_9/verdict.md` covering:

- **Methodology sanity** for 2-3 endpoints per axis (Priya hand-picks; expected directions confirmed).
- **Internal consistency** spot-check vs legacy paired t-test for 3-5 endpoints where methodologically defensible.
- **Permutation reproducibility** unit-test result from Task 3d.
- **Cohort pool vs per-cohort-bin-size sensitivity** check: any endpoint with pooled-vs-stratified divergence > Cohen's d 0.3.
- **Stats summary figure eyeball** — Priya reviews; verdict line PASS / iterate / FAIL.
- **`recovery_trajectories` plot family eyeball** — Priya reviews; verdict.

**STOP-and-report.** Priya scientific review required before Task 9.

### Task 9 — DECISIONS + MIGRATION_LOG + PR

1. **DECISIONS entry** dated 2026-MM-DD covering: 12 OPEN-Q locks (this kickoff), Option C recovery-organization lock, **per-animal `epoch_boundaries` lock (Option 1 of 2026-05-23 discussion — manual YAML stamping over data-derived alternatives)**, single-stroke-laterality caveat, FDR-exploratory default, cohort-pool-with-fixed-effect lock, any in-phase deviations.
2. **MIGRATION_LOG entry** Phase 9 covering deliverables + forward-pointers (Phase 9.x-spatial-stats, Phase 9.1 phenotype-pooled figures, any deferred items).
3. **PR open** against `main`; title `Phase 9: behavioral statistical analyses on consolidated outputs`; body summarizes deliverables + lock list + open follow-on phases.

---

## Pre-commit checks

Per CLAUDE.md Git discipline + tag rules:

```bash
git branch --show-current               # confirm "phase/9-stats", NOT "main"
pytest -x                               # full suite must pass
ruff check src/ tests/                  # clean
```

Pre-commit hook in `.githooks/pre-commit` already enforces non-main branch.

---

## PR + merge + tag

After Task 9 PR opens:

1. Priya reviews + merges via GitHub UI.
2. Capture merge SHA: `gh pr view <N> --json mergeCommit -q .mergeCommit.oid`.
3. Tag the merge commit:
   ```bash
   git fetch origin
   git tag -a v9-stats-behavioral <merge-sha> -m "Phase 9: behavioral statistical analyses on Phase 7c.2 + 7a kinematics + 8a.10 spout-behavior endpoints"
   git push origin v9-stats-behavioral
   ```
4. Feature branch left intact on origin per CLAUDE.md.

---

## Forward-pointers carried out of Phase 9

To be confirmed at Task 9 close; expected:

1. **Phase 9.x-spatial-stats** — per-bin and/or distribution-level statistical tests over Phase 7c.2 centered parquets (compute-on-demand via `dlc_spatial/render_on_demand.py`). Methodology design needed: cluster-corrections (voxel + cluster-level a la fMRI), OT-cost calibration vs permutation null, baseline-bin selection. Decision 26 amendment findings 3 + 4 (per-phenotype baseline whisker/nose preferences for `eye_rigid`/`eye_affine`; post-stroke jaw / L_whiskers_1 bins 3..4 / 5..6 / 13..14 heterogeneity) are candidate inquiries for this phase.
2. **Phase 9.1 phenotype-pooled figures** — scoping at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`; consumes `stats/recovery_epochs.classify_phenotype` outputs from this phase + per-phenotype-pooled visualizations.
3. **Phase 9.y-bayesian** (speculative) — if the paper needs Bayesian methods (BEST, hierarchical models) for headline tests. Not committed.
4. **Stats inventory becomes a pre-registration artifact** — if/when Priya decides to pre-register, the stamped `endpoint_inventory.csv` `is_confirmatory` column becomes the pre-registration commitment. No action required from Phase 9; just available.
5. **Pub-figures phase** — blocked on Phase 9 + 9.1; consumer of `stats/figures/` summary plots.

---

## References

- `docs/prompts/phase-9-stats-scoping.md` — prior scoping pass (superseded by this kickoff).
- `docs/SCIENTIFIC_ENDPOINTS.md` — Audit Item 10 endpoint catalog.
- `docs/prompts/phase-7-pre-alignment-templates-kickoff.md` — F-P-7 kickoff (Task 0 git-workflow pattern; STOP-and-report cadence).
- `docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md` — 7c.2 kickoff (compute-on-demand spatial architecture; Decision 26 amendment text).
- `src/stroke_orofacial/spout_behavior/recovery_trajectories.py` — Phase 8a.8 descriptive layer that Task 6 extends.
- `src/stroke_orofacial/stats/` — five stubs filled by Task 3.
- `configs/animals.yaml` — `stroke_laterality` + `bin_days` per animal.
- `configs/defaults.yaml` — gains `stats:` top-level key (Task 0 / kickoff prereq; create if missing).
- `feedback_iterative_addenda_pattern.md` — Addendum #N etiquette for mid-phase re-spec.
- `feedback_scratch_path_validation_not_production_state.md` — Tasks 2 + 5 must write to `pipeline_outputs/stats/`, NOT to `.scratch_phase_9/`.
- `feedback_check_main_state_before_assuming_branch.md` — Task 0 includes git-state verification.

---

**Kickoff drafted 2026-05-23 by Cowork during warm-start verification of the post-Phase-7d / post-F-P-7 state. Supersedes `docs/prompts/phase-9-stats-scoping.md` for execution. Re-specs via numbered Addenda per `feedback_iterative_addenda_pattern.md`.**

---

## Addendum #1 — Spatial scalar endpoints + phenotype-pooled + recovery-epoch-pooled figure tiers (Priya scope expansion 2026-05-23)

**Re-spec triggered by Priya 2026-05-23** during endpoint-inventory stamping discussion. Two scope expansions land together:

**(A) Spatial scalar endpoints + figure curation.** The kickoff §1 originally deferred ALL spatial-distribution stats to Phase 9.x-spatial-stats. Revised: a scalar-summary spatial layer lands in Phase 9. Specifically:

- **4 new tested endpoints** added to `.scratch_phase_9/endpoint_inventory.csv`:
  - `spatial_uot_cost_tongue_spout_midpoint`
  - `spatial_uot_cost_jaw_eye_midpoint`
  - `spatial_uot_cost_nose_eye_midpoint`
  - `spatial_uot_cost_whiskers_eye_midpoint`

  All four are `scalar_per_animal_bin`, `is_primary=true`, `n_permutations_override=100000` (priority tier — Priya highlighted these for headline framing), `comparison_axes_in_scope=recovery` (mixedlm on rel_day; pre_post axis not applicable since pre IS the baseline pool by UOT-cost construction).

- **Materialization (Task 2 expansion):** for each (animal, bin, family_entry), the Task 2 driver loads the pre-pool + post-bin centered parquets via `dlc_spatial/render_on_demand.py` (existing compute-on-demand framework from Phase 7c.2), computes the unbalanced OT cost via POT library (already in `environment.yml` per Phase 7c.2 dep), and emits the scalar to `stats/inputs/spatial_uot_cost_<family_entry>/<animal>.parquet`. No new dlc_spatial code needed — POT is consumed inside the materialization driver.

- **Figure curation (Task 7 expansion):** Task 7 also produces a curated headline spatial-figures subset that points at existing Phase 7c.2 cohort-emit SVGs for the 4 family entries × 2 plot types (`proportion_differences`, `unbalanced_ot`) × scope `tone_aligned` = 8 figure categories per animal, plus phenotype-pooled and epoch-pooled aggregates per (B) below. No new spatial figures are generated from scratch; the 7c.2 SVGs are linked into the Phase 9 figure tree via symlinks or a curation manifest.

- **What stays in Phase 9.x-spatial-stats:** per-bin (voxel-level) and cluster-corrected spatial tests; comprehensive spatial endpoint inventory beyond the 4 highlighted family entries; non-recovery-axis spatial tests; per-trial-group split (all/L/R fanout) for spatial scalars if needed.

**(B) Phenotype-pooled + recovery-epoch-pooled figure tiers (Task 7 expansion).** The kickoff originally locked Phase 9 as per-animal-figures-only, with phenotype-pooled deferred to Phase 9.1 and recovery-epoch-pooled not explicitly allocated. Revised: Phase 9 Task 7 now produces THREE figure tiers:

1. **Per-animal** (original scope): each primary endpoint × each comparison axis renders a per-animal figure (forest plot, recovery curve with CI, paired-difference distribution).

2. **Phenotype-pooled** (NEW): mean ± SEM across animals within each `recovery_phenotype` tier (mild/moderate/moderate-severe/severe). For primary endpoints with `comparison_axes_in_scope` including `recovery`, produce phenotype-pooled recovery curves (one curve per phenotype tier; n labels per tier). For pre-post and ipsi-contra axes, produce phenotype-stratified forest plots. With current cohort distribution (mild=4, moderate=1, moderate-severe=1, severe=2), the moderate and moderate-severe tiers have n=1 and won't carry SEM — render as single-animal traces with explicit n=1 labels. The mild (n=4) and severe (n=2) tiers carry meaningful pooled statistics.

3. **Recovery-epoch-pooled** (NEW): mean ± SEM across animals × sessions WITHIN each epoch (pre / acute / sub_acute / chronic). Epoch labels come from per-row `epoch_label` column added in Task 2 materialization (per-animal boundaries from `AnimalInfo.epoch_boundaries`). For each primary endpoint, render bar/point summaries per epoch with within-animal and across-animal n labels. Optionally faceted by phenotype tier.

- **Implementation hooks:**
  - `src/stroke_orofacial/stats/recovery_epochs.py` gains `phenotype_pooled_summary(inputs_df, endpoint_slug, animals)` and `epoch_pooled_summary(inputs_df, endpoint_slug, animals, by_phenotype: bool = False)` helpers — both return summary DataFrames suitable for figure rendering.
  - `src/stroke_orofacial/figures/stats_summary.py` gains a `pooled_summaries/` figure family with corresponding render functions.
  - `pipeline_outputs/stats/figures/` gains parallel subtree `pooled/{phenotype,epoch}/<endpoint_slug>.svg/png`.

**(C) Phase 9.1 re-scope (consequential).** With phenotype-pooled and epoch-pooled figures absorbed into Phase 9, Phase 9.1 reduces to pub-quality polish only — typography, color-palette harmonization, multi-panel composite figures for the paper, ipsi/contra labeling per `mouse_side_to_ipsi_contra`. Update `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` at Phase 9 close (Task 9 DECISIONS entry references the absorption).

**Updated task estimates** (was: ~14-20 commits, ~10-15 days CC wall time):

| Task | Was | Now |
|---|---|---|
| Task 0 | <5 min | unchanged |
| Task 1 | 2-3 hr CC + Priya review | unchanged (no spatial endpoints in original CSV; Addendum-added 4 rows are spec'd in the addendum directly, no further stamping needed) |
| Task 1.5 | 2-3 hr | unchanged |
| Task 2 | 1-2 days | 2-3 days (+1 day for spatial UOT computation) |
| Task 3 | 3-5 days | unchanged |
| Task 4 | 2-3 days | unchanged |
| Task 5 | 30-60 min compute | 1-2 hr compute (+ spatial UOT pass) |
| Task 6 | 1-2 days | unchanged |
| Task 7 | 2-3 days | 5-7 days (+ phenotype-pooled tier + epoch-pooled tier + spatial figure curation) |
| Task 8 | 1-3 days Priya | 2-4 days Priya (more figures to review) |
| Task 9 | 30-60 min | 1 hr (DECISIONS entry covers Addendum #1 expansions) |

**Updated total estimate: ~18-25 commits, ~16-25 days CC wall time.**

**Lock changes from kickoff body:**
- **§1 "Out of scope" → revised:** spatial-distribution stats partially in scope (scalar UOT cost for 4 highlighted family entries); per-bin and cluster-corrected spatial tests STILL deferred to Phase 9.x.
- **§3.5 spatial-distribution tests (referenced from scoping doc) → revised:** distribution-level OT-cost tests for the 4 highlighted family entries ARE in Phase 9 scope (recovery axis only); per-bin tests deferred.
- **§6 Phase structure proposed table → revised:** Task estimates per the table above.
- **§7 dependencies → revised:** Phase 9.1 dependencies on Phase 9 outputs grow (pooled figure data is upstream of pub-polish).

**Lock changes for inventory CSV:**
- 4 new rows appended for `spatial_uot_cost_<family_entry>` endpoints (see CSV).
- Existing endpoint rows (Cat A + tongue + jaw + mismatch + Phase 8a.10 deferred): UNCHANGED.

**ALL OTHER LOCKS FROM KICKOFF BODY UNCHANGED.** 12 OPEN-Q locks; Option C recovery-organization; per-animal epoch_boundaries; 4-tier recovery_phenotype enum; FDR-exploratory default (no Bonferroni); single-stroke-laterality caveat; cohort-pool-with-fixed-effect; defensive choices in Task 1.5 (ConfigValidationError(ValueError), bool-as-int rejection); SUPERSEDED rename for the Task 1 Part B draft; iterative-addenda re-spec etiquette.

---

## Addendum #2 — Additional spatial distribution-distance scalars (Wasserstein-2 + Jensen-Shannon divergence)

**Re-spec triggered by Priya 2026-05-23** during inventory finalization: legacy DLC analysis code (per Priya recollection; CC to confirm specific notebook/cell during Task 2) computed both Wasserstein distance and Jensen-Shannon divergence between pre vs post spatial distributions. Phase 7c.2's alignment-regime side-experiment (archived at `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`) ALSO computed JS divergence as a cross-regime comparison metric — script `notebooks/experiments/per_animal_overview_figures.py` is a reference implementation in-tree.

**(A) 8 additional spatial scalar endpoints** appended to `.scratch_phase_9/endpoint_inventory.csv`, parallel to the 4 UOT cost endpoints from Addendum #1:

- `spatial_wasserstein_tongue_spout_midpoint`
- `spatial_wasserstein_jaw_eye_midpoint`
- `spatial_wasserstein_nose_eye_midpoint`
- `spatial_wasserstein_whiskers_eye_midpoint`
- `spatial_js_divergence_tongue_spout_midpoint`
- `spatial_js_divergence_jaw_eye_midpoint`
- `spatial_js_divergence_nose_eye_midpoint`
- `spatial_js_divergence_whiskers_eye_midpoint`

All 8: `value_type=scalar_per_animal_bin`, `is_primary=true`, `n_permutations_override=100000` (priority tier — same as UOT cost), `comparison_axes_in_scope=recovery` (mixedlm only; pre IS the baseline pool by construction).

**(B) Implementation in Task 2 driver.** The 8 new scalars share the same data-loading pattern as the UOT cost scalars (load pre-pool + post-bin centered parquets via `dlc_spatial/render_on_demand.py`), differ in the metric computation:

- **Wasserstein-2 (balanced OT):** normalize both 2D histograms to probability distributions (divide by total mass); compute 2D Wasserstein-2 distance via `POT` library (`ot.emd2` with squared-Euclidean cost matrix on grid coordinates). Requires `POT` (already in `environment.yml` per Phase 7c.2). Single function call ~O(n^3) where n = grid cell count; ~50ms per (animal, bin, family_entry) typical for 100×100 grid.
- **Jensen-Shannon divergence (information-theoretic):** normalize both 2D histograms; compute JS via `scipy.spatial.distance.jensenshannon` on flattened histograms (equivalently, `0.5 * (KL(p || m) + KL(q || m))` where `m = 0.5 * (p + q)`). Bounded `[0, log(2)]`; symmetric. Reference implementation pattern in `notebooks/experiments/per_animal_overview_figures.py`.

**(C) Why three metrics and not one.** UOT, Wasserstein, and JS each measure spatial-distribution change with different sensitivities and assumptions:

- **UOT cost** (Addendum #1): unbalanced; doesn't require pre/post to normalize identically; sensitive to mass changes AND location changes.
- **Wasserstein-2** (this addendum): balanced; isolates location/shape change after normalization; canonical OT metric used widely in spatial-statistics literature.
- **JS divergence** (this addendum): information-theoretic; bounded; symmetric; sensitive to distribution-shape mismatch independent of metric structure; legacy paper-figure tradition per Priya.

Cross-validation: if all three metrics converge on the same conclusion (e.g., "tongue spatial distribution drifts during chronic recovery"), the conclusion is robust to metric choice. If they diverge, the divergence is itself scientifically informative (e.g., "mass change without location shift" suggests UOT > Wasserstein).

**(D) Task estimates.** Adds ~+0.5 day to Task 2 (3 metrics × 4 family entries × ~352 sessions × ~10s per metric per session ≈ ~12 hr wall-time, with parallel-safe per-(animal, bin) computation). Statistical machinery (mixedlm on recovery axis) is unchanged; same `fit_recovery_mixedlm` consumer in Task 4. Figure curation (Task 7) gains nothing new — the 8 new scalars are inferential only, no new figures from them directly. Decision summary figures may surface them via forest plots.

**Lock changes for inventory CSV:**
- 8 new rows appended (4 Wasserstein + 4 JS divergence). Total spatial endpoints: 12 (4 UOT cost + 4 Wasserstein + 4 JS divergence).
- All other CSV rows: UNCHANGED.

**Updated total estimate:** ~18-25 commits, ~16-25 days CC wall time (Addendum #2 adds ~+0.5 day to Task 2 only; rounds to same range).

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDUM #1 UNCHANGED.**

---

## Addendum #3 — Wasserstein-2 is the HEADLINE spatial metric (refines Addendum #2's "three-equal-metrics" framing)

**Re-spec triggered by Priya 2026-05-23**: Wasserstein-2 was the canonical spatial-distance metric used in legacy paper analyses. Addendum #2's framing treated UOT cost, Wasserstein-2, and JS divergence as three equally-weighted spatial metrics tested in parallel for cross-validation. Refined: **Wasserstein-2 is the HEADLINE; UOT cost + JS divergence are supplementary robustness checks.**

**(A) CSV note updates.** Each of the 4 `spatial_wasserstein_<family_entry>` rows in `.scratch_phase_9/endpoint_inventory.csv` gets its notes field updated to lead with `HEADLINE SPATIAL METRIC per Priya 2026-05-23 (Addendum #3)`. UOT and JS rows remain marked as "PRIORITY" but their notes no longer claim parity with Wasserstein.

**(B) Task 7 figure curation implications (this is the substantive change):**

- **Headline panel** for each family entry (tongue/jaw/nose/whiskers): Wasserstein-2 recovery curve + per-animal scatter. One headline panel per family entry × per figure tier (per-animal / phenotype-pooled / recovery-epoch-pooled) = 4 × 3 = 12 headline panels.
- **Supplementary panels:** UOT cost + JS divergence recovery curves in a stacked supplementary layout per family entry. Same three figure tiers (per-animal / phenotype-pooled / recovery-epoch-pooled).
- **Decision summary narrative:** Task 8 verdict leads with Wasserstein results ("Wasserstein-2 distance to pre-stroke baseline shows X recovery trajectory in tongue spatial distribution; UOT cost and JS divergence corroborate / qualify as follows..."). UOT and JS are robustness rather than independent findings.

**(C) Statistical-test treatment unchanged.** All three spatial metrics are still tested via `fit_recovery_mixedlm` on the recovery axis, FDR-corrected within the spatial-metrics family (12 endpoints = 4 family entries × 3 metrics). The "headline vs supplementary" distinction is presentation-only — UOT and JS still appear in results CSVs and forest plots, just not in the headline figure slot.

**(D) Paper-narrative implication.** If Wasserstein-2 shows an effect that UOT or JS doesn't (or vice versa), the divergence is itself reportable as a methodological observation — but the paper's headline number for spatial change is the Wasserstein-2 value. Cross-metric convergence remains the robustness story.

**Lock changes for inventory CSV:**
- 4 `spatial_wasserstein_<family_entry>` rows: notes updated to flag HEADLINE METRIC.
- 4 `spatial_uot_cost_<family_entry>` rows: notes can stay as-is (already flagged PRIORITY); they don't need re-marking as "supplementary" — that's a Task 7 presentation concern, not an inventory-schema concern.
- 4 `spatial_js_divergence_<family_entry>` rows: same as UOT.

**Lock changes for kickoff body:**
- Task 7 spec for spatial figures: Wasserstein in headline slot; UOT + JS in supplementary. Implementation note for `figures/stats_summary.py` rendering.

**Task estimates:** unchanged. Same metric computations + same figure tiers; only the layout within Task 7 figure rendering shifts.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2 UNCHANGED.**

---

## Addendum #4 — Kolmogorov-Smirnov distribution-shape test for vector_per_session endpoints

**Re-spec triggered by Priya 2026-05-23**: `latency_hist` (vector_per_session) was stamped `is_primary=true` + `is_confirmatory=true` in the inventory, but the kickoff body's default test toolkit (Wilcoxon for paired pre-post; mixedlm for recovery; Wilcoxon-on-paired-diffs for ipsi/contra; Friedman for trial_group) doesn't handle distribution-shape endpoints. This addendum adds the missing methodology.

**(A) Test choice: two-sample Kolmogorov-Smirnov.** Standard distribution-shape comparison; well-understood in the neuroscience literature; tests the maximum vertical distance between empirical CDFs of pre-stroke and post-stroke latency distributions. Alternatives considered + rejected for default:

- Anderson-Darling — more powerful especially for tail differences, but less common in neuroscience papers; harder to explain in figure legends.
- Cramér-von Mises — intermediate sensitivity; less standard.
- Mann-Whitney U — tests rank/location, not full distribution shape (would miss bimodality changes).
- 1D Wasserstein — already implemented in spatial-metric family; would be consistent but reframes the test as "distance" rather than "is-it-different".

KS is the default for `value_type=vector_per_session` endpoints. The other tests above are available via opt-in `--test-method` CLI override per endpoint if needed.

**(B) Paired-cohort framework.** `scipy.stats.ks_2samp` is unpaired (assumes independent samples). For paired within-animal data (each animal contributes both a pre-stroke distribution and a post-stroke distribution), pool naive-wise would discard the within-animal pairing. The framework Phase 9 uses:

1. **Per-animal KS:** for each animal, run `ks_2samp(pre_latencies, post_latencies)` → one KS statistic D_i and one p-value p_i per animal.
2. **Cohort-level p-value:** Fisher's combined p-value across animals via `scipy.stats.combine_pvalues(p_values, method="fisher")`. Yields the cohort meta-p.
3. **Effect size:** the cohort-mean KS statistic across animals (mean of D_i for i in animals). Report bootstrap CI on this mean.
4. **Confidence interval:** bootstrap on the per-animal KS statistics (resample animals with replacement, n_bootstrap=10k, BCa method per the existing `stats.permutation.bootstrap_ci`).
5. **Pre-stroke pool definition:** per the kickoff's `rel_day_pre_stroke_max: 0` lock, pre = rel_day ≤ 0; post = rel_day ≥ 1. For chronic comparison, post can be restricted to the chronic epoch per `AnimalInfo.epoch_boundaries.chronic_min_rel_day`.

**(C) Implementation hooks in `stats/models.py`** (extends Task 3e):

```python
def fit_pre_post_ks_distribution_shape(
    inputs_df: pd.DataFrame,
    endpoint_slug: str,
    *,
    pre_post_col: str = "epoch_label",
    pre_label: str = "pre",
    post_label: Literal["acute", "sub_acute", "chronic"] | str = "chronic",
    bootstrap_ci: bool = True,
    random_state: int | None = None,
) -> FitResult:
    """KS two-sample distribution-shape test, paired across animals via Fisher's combined p.

    Per-animal scipy.stats.ks_2samp; cohort meta-p via combine_pvalues(method='fisher');
    effect size = cohort mean KS statistic D; bootstrap CI on D.

    Returns FitResult with:
        test_statistic = cohort mean per-animal KS statistic D
        p_value = Fisher's combined p across animals
        p_value_method = "fisher_combined_per_animal_ks"
        effect_size = same as test_statistic (the D mean)
        effect_size_metric = "ks_statistic_mean"
        ci_lower, ci_upper = BCa bootstrap on per-animal D
        extra = {
            "per_animal_ks_statistic": dict[animal_id, float],
            "per_animal_p_value": dict[animal_id, float],
            "combined_method": "fisher",
        }
    """
```

**(D) Test routing in Task 4 per-axis runner.** `scripts/phase_9_stats/run_axis_pre_post.py` extends to dispatch by `value_type`:

```python
if value_type == "vector_per_session":
    result = fit_pre_post_ks_distribution_shape(...)
elif value_type in ("scalar_per_session", "scalar_per_trial"):
    result = fit_paired_pre_post_wilcoxon(...)
else:
    raise NotImplementedError(f"No pre_post test defined for {value_type}")
```

Same dispatch shape extends to other axes; for `vector_per_session` with `axes_in_scope` only including `pre_post` (the latency_hist current stamping), only the pre_post axis runner produces a FitResult. If you later want KS-style tests on recovery or ipsi_contra axes, file an Addendum.

**(E) latency_hist row stamping (CSV updated 2026-05-23).** Row 16 already updated: `is_primary=true`, `is_confirmatory=true`, `n_permutations_override=100000`, `comparison_axes_in_scope=pre_post`. Notes reference this addendum.

**Task estimates:**
- Task 2: unchanged (latency_hist materialization is reading per-trial latencies from `endpoints_per_trial.py::_first_correct_lick_latency_s` into a parquet column — already in scope).
- Task 3e: +0.5 day for `fit_pre_post_ks_distribution_shape` + unit tests (synthetic-distribution sanity).
- Task 4: +0.5 day for `value_type` dispatch in run_axis_pre_post.

**Updated total estimate:** ~18-25 commits, ~17-26 days CC wall time (Addendum #4 adds ~+1 day; rounds to same range).

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3 UNCHANGED.**

---

## Addendum #5 — Multi-granularity emit + stats runner (per_session / per_bin / per_epoch / per_trial)

**Re-spec triggered by Priya 2026-05-23** during Commit A close: "i am going to want epoch-based stats and potentially plotting. i want to preserve ability to compare with LMM across days (no binning?), versus across bins versus across epochs."

Phase 9 runs stats at three temporal granularities for every primary endpoint, enabling cross-granularity comparison of LMM results. Spatial endpoints (Wasserstein/UOT/JS) require parallel materialization at all three granularities because the metric over aggregated histograms ≠ aggregation of per-session metrics; non-spatial endpoints get free granularity expansion at Task 4 runtime.

**(A) Granularity taxonomy.**

| Granularity | Time unit | Aggregation | LMM predictor | Applicable to |
|---|---|---|---|---|
| `per_trial` | one row per (animal, date, trial_idx, side) | none | rel_day + session random effect | scalar_per_trial endpoints only |
| `per_session` | one row per (animal, date, side) | mean across trials in session (for per-trial endpoints); raw value (for per-session endpoints) | rel_day (continuous) | all endpoints |
| `per_bin` | one row per (animal, bin_midpoint_rel_day, side) | mean across sessions in bin per `AnimalInfo.bin_days` | bin_midpoint_rel_day (continuous, smoother) | all endpoints |
| `per_epoch` | one row per (animal, epoch_label, side) | mean across sessions in epoch per `AnimalInfo.epoch_boundaries` | epoch_label (categorical: pre / acute / sub_acute / chronic) | all endpoints |

**(B) Materialization changes.**

*Non-spatial endpoints (Commit A already emitted):* NO materialization change. The per-session/per-trial parquet has the `rel_day` column; Task 4 stats runner does the bin/epoch aggregation at runtime. Existing 256 parquets at `pipeline_outputs/stats/inputs/` stay as-is.

*Spatial endpoints (Commit C — not yet built):* parallel materialization at three granularities. For each (animal, family, metric):
- Compute pre-pool histogram once (rel_day ≤ 0 dates pooled).
- `per_session` granularity: for each post-stroke date d, compute that single-date histogram → metric vs pre-pool → 1 row per date.
- `per_bin` granularity: for each post-stroke bin (anchored on rel_day=0, width = `AnimalInfo.bin_days`), aggregate dates' histograms → metric vs pre-pool → 1 row per bin.
- `per_epoch` granularity: for each post-stroke epoch (acute/sub_acute/chronic per `AnimalInfo.epoch_boundaries`), aggregate dates' histograms → metric vs pre-pool → 1 row per epoch.

This means spatial parquets gain new schema columns and emit ~3-5× more rows per (animal, family, metric).

*Latency_hist (vector_per_session, Commit B):* NO materialization change. The per-session vector parquet is sufficient; Task 4 KS runner pools latency vectors across sessions within bin/epoch at runtime for the per_bin and per_epoch granularities.

**(C) Spatial parquet schema additions (Commit C only).** Four new columns beyond the standard 11-column schema:

```python
"granularity": Literal["per_session", "per_bin", "per_epoch"],
"rel_day_anchor": Int64,   # date's rel_day / bin midpoint / per-animal mean rel_day in epoch
"n_sessions_aggregated": Int64,  # 1 for per_session; N for per_bin; M for per_epoch
"n_frames_aggregated": Int64,    # total frames in the aggregated post-histogram
```

Per-animal mean rel_day in epoch: for `per_epoch` granularity, `rel_day_anchor = mean(rel_days of observed post-stroke sessions in this epoch for this animal)`. Different animals have different epoch-anchor rel_days; this anchors the LMM continuous predictor for cross-animal pooling.

**(D) Inventory CSV update.** The 12 spatial endpoint rows' `value_type` field flips `scalar_per_animal_bin → scalar_per_animal_time` (applied 2026-05-23). "Time" reflects the multi-granularity nature (session/bin/epoch).

**(E) Task 4 stats runner expansion.** Result tree gains a granularity layer:

```
pipeline_outputs/stats/results/
  pre_post/
    per_session/<endpoint_slug>.csv
    per_bin/<endpoint_slug>.csv
    per_epoch/<endpoint_slug>.csv
    _all.csv  (cross-granularity master per endpoint)
  recovery/
    per_session/<endpoint_slug>.csv
    per_bin/<endpoint_slug>.csv
    per_epoch/<endpoint_slug>.csv
    _all.csv
  ipsi_contra/  [same shape]
  trial_group/  [same shape]
```

Per-axis runners dispatch by granularity:
- `per_session`: load parquet, group by (animal, date, side), aggregate value (mean across trials if scalar_per_trial), run axis test.
- `per_bin`: group by (animal, bin_midpoint_rel_day, side), aggregate value, run axis test.
- `per_epoch`: group by (animal, epoch_label, side), aggregate value, run axis test.

For `scalar_per_trial` endpoints (24 of 46 primaries), add a `per_trial/` subdirectory with LMM at full trial granularity (random intercepts on both animal AND session).

**(F) Confirmatory granularity choice per endpoint type.** Pre-registration applies to the HYPOTHESIS, not the granularity — so each `is_confirmatory=true` endpoint picks ONE granularity as the headline confirmatory test (gets Bonferroni alongside FDR). Other granularities are sensitivity analyses (FDR within their own granularity-axis family but not added to the confirmatory family-wise correction).

Default confirmatory granularity by `value_type`:
- `scalar_per_session`: **per_session** (matches legacy paper paired-t conventions)
- `scalar_per_trial`: **per_session** (mean-across-trials per session is the natural aggregate; per_trial LMM is sensitivity)
- `vector_per_session` (latency_hist): **per_session** (KS at session-level is the natural test)
- `scalar_per_animal_time` (spatial): **per_bin** (matches the original kickoff/Addendum #1-3 lock; per_session/per_epoch are sensitivity)

If you want different defaults per endpoint, override via a new `confirmatory_granularity` column in the inventory CSV. For now the default applies uniformly.

**(G) Task 7 figure tier expansion.** Each primary endpoint's figure block gains a cross-granularity comparison panel showing the LMM effect sizes at per_session / per_bin / per_epoch side-by-side (forest plot row). The phenotype-pooled and recovery-epoch-pooled figure tiers (Addendum #1) intersect with this:

- Per-animal tier × multi-granularity: 3-panel comparison per endpoint (or 4-panel for scalar_per_trial)
- Phenotype-pooled tier: pick one granularity per tier — recommended `per_bin` (smooth, plottable trajectory)
- Recovery-epoch-pooled tier: collapses to `per_epoch` granularity by definition

Specific tier × granularity assignments deferred to Task 7 implementation — flag any choice changes as a small addendum at Task 7 close.

**(H) Materialization implications for Commit C.**

For each spatial endpoint (12 endpoints) × each animal (8) × three granularities = 288 emit groups total (but emitted as one parquet per (animal, family, metric) with multiple rows for the three granularities, so still 96 parquets, just denser).

Per-animal compute cost per family entry:
- 1 pre-pool aggregation (re-used across all granularities and metrics)
- N per-session post-histograms (N = ~10-30 post-stroke sessions per animal)
- ~5-10 per-bin post-histograms (depending on bin_days and post-stroke duration)
- 3 per-epoch post-histograms (acute, sub_acute, chronic)
- Per-emit: 3 metrics computed (Wasserstein-2 / UOT / JS)

Wall-time estimate: ~10-15 min per family entry × 4 family entries × 8 animals ≈ ~6-10 hours total for Commit C. Parallel-safe across (animal, family); typical single-machine.

**(I) Task estimates revised.**

| Task | Was (post-Addendum-4) | Now (post-Addendum-5) |
|---|---|---|
| Commit B (latency_hist materialize) | ~5 min compute | unchanged at materialize; Task 4 KS gains 3-granularity dispatch |
| Commit C (spatial materialize) | ~2 days + ~30 min compute | ~3-4 days + ~6-10 hr compute (parallel-granularity histogram aggregation) |
| Task 3e (`stats/models.py` fit functions) | 3-5 days | unchanged (functions don't change; runner-side dispatch adds granularity) |
| Task 4 (per-axis runners) | 2-3 days | 4-5 days (granularity dispatch + aggregation + per-granularity CSV emit + _all.csv master) |
| Task 7 (figures) | 6-8 days | 7-9 days (cross-granularity comparison figures + tier × granularity grid) |

**Updated total: ~20-32 days CC wall time (was 17-26).** +3-6 days for multi-granularity.

**Lock changes for inventory CSV:**
- 12 spatial endpoint rows: `value_type` updated `scalar_per_animal_bin → scalar_per_animal_time` (applied 2026-05-23).
- All other rows: unchanged.

**Lock changes for kickoff body:**
- Task 2 schema (§Hardcoded constants): non-spatial schema unchanged; spatial schema gains 4 columns per (C) above.
- Task 4 result tree: per-granularity subdirectories per (E) above.
- Task 7 figure tiers: cross-granularity comparison per (G) above.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3, #4 UNCHANGED.**

---

## Addendum #6 — Corrected per_epoch semantics: per-session within epoch + additive normalization to per-animal baseline

**Re-spec triggered by Priya 2026-05-23** clarifying intent of "epoch-based stats" — Addendum #5's per_epoch lock as "aggregate sessions in epoch to one mean per animal" was wrong. Corrected: per_epoch keeps **per-session granularity within the epoch** (each session is one data point, tagged with `epoch_label`), with values normalized to the animal's pre-stroke baseline via additive subtraction (`value - per_animal_baseline_mean`).

Statistically more powerful (preserves within-animal session variance) and simpler to implement (per_epoch becomes a filter + normalize view on per_session data, not a separate aggregation pass).

**(A) Per_epoch semantics — corrected.**

| | Addendum #5 lock (WRONG) | Addendum #6 lock (correct) |
|---|---|---|
| Data points per (animal, epoch) | 1 (aggregated mean) | N (one per session in epoch) |
| Normalization | none | additive: `value − per_animal_baseline_mean` |
| Test | ANOVA/LMM on 4 means per animal | LMM(`value_normalized ~ epoch_label + (1\|animal)`) on per-session data |
| Power | low (1 datum per animal-epoch) | high (preserves session-level variance) |
| Materialization | separate per_epoch emit | NO separate emit — derived from per_session at Task 4 runtime |

**(B) Normalization.** Per-animal additive baseline (`stats/normalization.py::difference_from_baseline`):

```
value_normalized = value − baseline_per_animal_mean
baseline_per_animal_mean = mean(value where epoch_label == "pre" for this animal)
```

Applied at Task 4 stats runner (not materialization-time) — keeps emit data raw, allows alternative normalizations (z-score, ratio, log1p) via opt-in without re-emit.

For NON-SPATIAL endpoints: baseline is computed directly from `value` column rows where `epoch_label == "pre"` per animal.

For SPATIAL endpoints (Wasserstein/UOT/JS): baseline is the noise floor — mean Wasserstein across pre-stroke sessions using leave-one-out pre-pool (i.e., each pre-stroke session's Wasserstein is computed vs `pre_pool_excluding_self`). This captures the typical Wasserstein magnitude that pre-stroke variability alone produces, against which post-stroke values are normalized.

**(C) Spatial materialization simplified (Commit C scope change).** Addendum #5's per_epoch aggregated-histogram emit (3rd emit pass per family per metric) is DROPPED. Commit C now emits:

1. **per_session granularity** for ALL sessions (pre + post-stroke):
   - Pre-stroke session value: Wasserstein/UOT/JS via leave-one-out (session histogram vs pre_pool_excluding_self).
   - Post-stroke session value: Wasserstein/UOT/JS vs full pre-pool.
   - One row per (animal, date, family, metric). `granularity="per_session"`, `epoch_label` populated.
2. **per_bin granularity** for post-stroke bins (per `AnimalInfo.bin_days`):
   - Aggregated bin histogram vs full pre-pool.
   - One row per (animal, bin_midpoint_rel_day, family, metric). `granularity="per_bin"`.
   - No pre-stroke per_bin emit (the pre-pool IS the pre baseline for spatial; no per-bin breakdown of it).

per_epoch analysis at Task 4 = filter per_session rows to `epoch_label != "pre"` + apply additive baseline normalization. No emit needed.

**(D) Implementation hooks (Commit C revision).**

```python
# Pre-stroke baseline computation (NEW; per family/animal/metric)
def compute_spatial_baseline_leave_one_out(
    pre_stroke_dates: list[date],
    animal: str,
    family_entry: str,
    metric_fn: Callable,
    *,
    resolver: PathResolver,
) -> list[float]:
    """One Wasserstein/UOT/JS value per pre-stroke session via leave-one-out."""
    baselines = []
    for date in pre_stroke_dates:
        pre_pool_minus = [d for d in pre_stroke_dates if d != date]
        H_session = compute_animal_aggregated_histogram(animal, [date], ...)[0]
        H_pre_minus = compute_animal_aggregated_histogram(animal, pre_pool_minus, ...)[0]
        baselines.append(metric_fn(H_session, H_pre_minus))
    return baselines
```

Compute cost: ~15 pre-stroke sessions × 4 families × 3 metrics × 8 animals × ~50ms ≈ ~70 sec total. Negligible.

**(E) Task 4 stats runner: per_epoch axis.**

```python
def run_axis_per_epoch(inputs_df: pd.DataFrame, endpoint_slug: str, animals: Mapping[str, AnimalInfo]):
    # Compute per-animal baseline from pre-stroke rows
    baselines = per_animal_baseline_stats(inputs_df, pre_filter=lambda r: r.epoch_label == "pre")

    # Filter to post-stroke epochs (drop pre rows)
    post_df = inputs_df[inputs_df.epoch_label.isin(["acute", "sub_acute", "chronic"])].copy()

    # Apply additive normalization
    post_df["value_normalized"] = post_df.apply(
        lambda r: r.value - baselines[r.animal]["mean"], axis=1
    )

    # LMM with epoch_label as categorical predictor, animal random intercept
    result = fit_per_epoch_lmm(
        post_df,
        formula="value_normalized ~ epoch_label",
        groups="animal",
        endpoint_slug=endpoint_slug,
    )
    return result
```

The corresponding fit function `fit_per_epoch_lmm` lands in `stats/models.py` (extends Task 3e).

**(F) Per_bin and per_session: unchanged from Addendum #5 except for baseline-row inclusion.**

- per_bin: aggregated mean across sessions in bin; one row per (animal, bin); LMM with bin_midpoint as continuous predictor + random intercept. Unchanged.
- per_session: each session is one data point; LMM with rel_day as continuous predictor + random intercept. Unchanged from materialization shape. **But:** for spatial endpoints, per_session emit now includes pre-stroke rows (leave-one-out baseline) where Addendum #5 emitted post-stroke only.

For per_bin (and per_session) LMM tests, normalization is optional — the random intercept handles per-animal baseline shifts. Task 4 can run both raw and normalized variants; default = raw for per_bin/per_session, normalized for per_epoch.

**(G) Task estimates revised.**

| | Addendum #5 | Addendum #6 |
|---|---|---|
| Commit C wall-time | ~3-4 days + ~6-10 hr compute | ~3 days + ~5-8 hr compute (-1 emit pass per family) |
| Task 4 per_epoch runner | aggregate-then-test | filter-then-normalize-then-test (simpler) |
| Net | — | ~−0.5 day |

**Total: ~19-31 days CC wall time (was 20-32).** Roughly same range; net simplification of the spatial materializer plus a slightly more complex Task 4 per_epoch helper.

**(H) Result tree (per Addendum #5) unchanged.** Still:
```
pipeline_outputs/stats/results/<axis>/<granularity>/<endpoint_slug>.csv
```
With per_session / per_bin / per_epoch subdirectories per axis. The internal computation differs per (G) above but the output structure is identical.

**(I) Lock changes for inventory CSV:** none. The 12 spatial rows' `value_type=scalar_per_animal_time` (Addendum #5) is unchanged. The semantics in Addendum #6 just clarify what "time" means at each granularity (per-session/per-bin granularity emitted; per-epoch is runtime view).

**Lock changes for kickoff body:**
- Task 2 schema for spatial (Addendum #5 §C): `granularity` column has 2 emit-time values (`per_session`, `per_bin`), not 3. per_epoch is a runtime axis.
- Task 4 result tree per_epoch runner: filter + normalize logic per (E) above.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3, #4, #5 UNCHANGED.**

---

## Addendum #7 — Cross-scope/trial-group spatial endpoints (4× expansion of spatial inventory)

**Re-spec triggered by Priya 2026-05-23** during Commit C close: existing spatial endpoints run the recovery-axis test (pre pool vs post bin Wasserstein/UOT/JS) at only `scope=tone_aligned, trial_group=all`. Extended to run the same recovery-axis test at FOUR scope+trial_group slices per family per metric, yielding scientifically distinct questions per slice.

**(A) Four scope+trial_group slices per (family, metric).**

| Slice | Scientific question |
|---|---|
| `whole_session` | "Did the background-session spatial distribution shift after stroke?" — captures non-task-related motor changes (whisking when not anticipating reward, jaw resting position drift, etc.) |
| `tone_aligned/all` (existing) | "Did the overall tone-anticipation spatial distribution shift?" — current default; canonical pre/post test |
| `tone_aligned/L` (NEW) | "Did L-tone-anticipation spatial distribution shift specifically?" — reveals lateralized deficit on L-anticipation trials |
| `tone_aligned/R` (NEW) | "Did R-tone-anticipation spatial distribution shift specifically?" — same on R side |

Each is its own scalar comparing pre vs post WITHIN that scope+trial_group slice; same time-axis test as existing spatial endpoints, just at three additional slice cuts.

**(B) Inventory expansion: 12 → 48 spatial endpoints.**

| Was (post-Addenda #1-6) | Now (post-Addendum #7) |
|---|---|
| 12 spatial slugs (4 families × 3 metrics × 1 slice) | 48 spatial slugs (4 families × 3 metrics × 4 slices) |
| Slug example: `spatial_wasserstein_tongue_spout_midpoint` | Slug example: `spatial_wasserstein_tongue_spout_midpoint_tone_aligned_all` |

Naming convention: `spatial_<metric>_<family>_<scope_trial_group>`. Scope+trial_group suffixes:
- `_tone_aligned_all` (existing 12 endpoints renamed for clarity)
- `_tone_aligned_L` (NEW)
- `_tone_aligned_R` (NEW)
- `_whole_session` (NEW; no trial_group suffix since trial_group is not meaningful for whole_session scope)

**(C) Inventory CSV changes.**

1. **Rename 12 existing rows**: append `_tone_aligned_all` to `endpoint_slug` AND to `materialized_path_template`. All other column values (is_primary, is_confirmatory, n_permutations_override, comparison_axes_in_scope, notes) PRESERVED unchanged — including the HEADLINE METRIC notes on the 4 Wasserstein rows from Addendum #3 and the existing TRUE/TRUE stamping from Priya's Excel pass.

2. **Add 36 new rows**: 4 families × 3 metrics × 3 new slices.

   Stamping defaults per Priya 2026-05-23 (Option C lock):
   - `is_primary: true` (all 36 new endpoints are primary tested)
   - `is_confirmatory: false` (Option C — only existing 12 tone_aligned/all endpoints retain confirmatory; new 36 are FDR-exploratory)
   - `n_permutations_override: 100000` (priority pattern; matches existing spatial)
   - `comparison_axes_in_scope: recovery` (same axis as existing spatial)
   - `value_type: scalar_per_animal_time` (same as existing)

**(D) Compute path (Commit C v3).**

For each (animal, family) pair (32 pairs total): compute_animal_aggregated_histogram is called 4× per time anchor (once per scope+trial_group slice). Then metric compute (W_2 / UOT / JS) runs against pre-pool 4× per time anchor.

For pre-stroke baseline (leave-one-out per Addendum #6): 4× leave-one-out passes per pre-stroke session (one per scope+trial_group).

**Histogram compute scales 4× vs Commit C v2.** Metric compute (POT/scipy) is fast relative to histogram aggregation.

**(E) Wall-time + parallelization (Priya Option B 2026-05-23 lock).**

| | Commit C v2 (current) | Commit C v3 (post-Addendum-7) |
|---|---|---|
| Single-threaded cohort emit | 5-8 hr | 20-32 hr |
| Parallelized across (animal × family) — 32 worker processes | n/a | 3-5 hr |

CC implements multi-process parallelization for Commit C v3 via Python's `concurrent.futures.ProcessPoolExecutor` (or `multiprocessing.Pool`) over the (animal, family) work units. Each worker is independent — separate file outputs, no shared mutable state. Resume-safe via `--skip-existing` per existing convention. Adds ~1 hr CC dev time for the parallel driver wrapper + small tests on a 2-worker subset.

**(F) Implementation hooks for Commit C v3.**

```python
SCOPE_TRIAL_GROUP_COMBOS = [
    ("tone_aligned", "all"),   # existing
    ("tone_aligned", "L"),     # NEW
    ("tone_aligned", "R"),     # NEW
    ("whole_session", None),   # NEW — trial_group=None per render_on_demand.py whole_session convention
]

# Per (animal, family) worker:
for scope, trial_group in SCOPE_TRIAL_GROUP_COMBOS:
    slug_suffix = f"{scope}_{trial_group}" if trial_group else scope
    # Compute pre-pool histogram (this scope+trial_group) once
    H_pre = compute_animal_aggregated_histogram(
        animal, pre_stroke_dates, bodypart, center_mode, resolver,
        trial_group=trial_group, scope=scope,
    )[0]
    # ... per_session emits + per_bin emits + metric compute per Addendum #5+#6
```

CC will need to check whether `compute_animal_aggregated_histogram` already accepts a `scope` kwarg, or if scope is implicit in the function signature (i.e., the existing function defaults to tone_aligned and a sibling function handles whole_session). Surface findings during Commit C v3 implementation.

**(G) Task estimates.**

| Task | Was (post-Addendum-6) | Now (post-Addendum-7) |
|---|---|---|
| Commit C wall-time | ~3 days + ~5-8 hr compute | ~3.5 days + ~3-5 hr compute (parallel) |
| Task 4 per-axis runners | 4-5 days | unchanged (more endpoints = more iterations but same code path) |
| Task 7 figures | 7-9 days | 7-9 days (figure layouts already designed to handle 4× spatial endpoint count via subpanel grouping per scope+trial_group) |

**Updated total: ~19-31 days CC wall time (was 19-31).** Roughly unchanged — parallelization offsets the 4× compute; CC dev time +1 hr for the parallel driver is rounding.

**(H) Lock changes for inventory CSV (applied 2026-05-23).**

- 12 spatial rows renamed: `<slug> → <slug>_tone_aligned_all` (slug + path columns only; all stamping preserved).
- 36 new rows appended per stamping defaults in (C) above.
- All other rows: unchanged.

**Lock changes for kickoff body:**
- Spatial endpoint count throughout text: 12 → 48 (8x for animal-level emit).
- Commit C scope: parallel implementation per (E) above.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3, #4, #5, #6 UNCHANGED.**

---

## Addendum #8 — Headline kinematic endpoints + V1-V5 figure grid + partial revert of Addendum #1 Phase 9.1 absorption

**Re-spec triggered by Priya 2026-05-23**: explicit 5-variant figure grid for the 7 headline kinematic endpoints, with cross-animal phenotype-pooled tiers (V4/V5) split off into Phase 9.1. Partial reversal of Addendum #1 (C) — phenotype-pooled figures move back to Phase 9.1; Phase 9 retains per-animal figures only.

**(A) Three new derived inventory rows** added 2026-05-23 (CSV rows 66-68):
- `tongue_lick1_vxy_peak` — first-lick 2D-velocity peak (`vxy_peaks_bylick[0]`)
- `tongue_max_vxy_peak_first5` — max 2D-velocity peak across first 5 licks
- `tongue_mean_vxy_peak_first5` — mean 2D-velocity peak across first 5 licks (different reduction from existing `tongue_median_vxy_peak_per_trial` at row 63)

All three: `value_type=scalar_per_trial`, `is_primary=true`, `is_confirmatory=false`, `n_permutations_override=100000` (priority pattern), `comparison_axes_in_scope=pre_post;recovery;ipsi_contra`. Materialization via Task 2 driver from existing `tongue_pertrial.py peak_velocity_per_lick.vxy_peaks_bylick` vector primitive — no dlc_kinematics source changes.

**(B) Headline kinematic endpoint set (7 endpoints).** Per Priya 2026-05-23 explicit priority for Phase 9 paper-figure spine:

| # | Endpoint slug | What it measures |
|---|---|---|
| 1 | `tongue_lick1_y_peak` | Peak tongue Y (px) — protrusion amplitude at first lick |
| 2 | `tongue_lick1_t_peak_ms` | Time to first peak (ms) — sub-second latency analogue |
| 3 | `tongue_lick1_x_at_ypeak` | First-lick tongue X at Y-peak — direction-of-protrusion |
| 4 | `tongue_lick2_x_at_ypeak` | Second-lick tongue X at Y-peak |
| 5 | `tongue_lick1_vxy_peak` (NEW) | Peak 2D-velocity, first lick |
| 6 | `tongue_max_vxy_peak_first5` (NEW) | Peak 2D-velocity, max across first 5 licks |
| 7 | `tongue_mean_vxy_peak_first5` (NEW) | Mean 2D-velocity, mean across first 5 licks |

These 7 endpoints get the explicit V1-V5 figure grid treatment per (D)+(E) below. Other primary scalar endpoints get the standard Task 7 figure pipeline (forest plots + recovery curves + paired-difference distributions per kickoff body).

**(C) Plot type clarification.** V1-V5 are SCALAR-value plots (one point per trial showing the scalar endpoint value at that trial's rel_day) — NOT time-series trajectory plots (signal vs frame-time within a trial). Time-series trajectories deferred entirely (not in Phase 9 or 9.1 scope).

**(D) V1-V5 figure grid (per headline kinematic endpoint).**

| Variant | Granularity | Pooling | Plot style | Phase |
|---|---|---|---|---|
| **V1** | per_session | per-animal | Per-animal panel × scatter of every trial's scalar value vs rel_day, with LMM fit + bootstrap CI ribbon overlay. L/R sides as overlaid colors. | **Phase 9 Task 7** |
| **V2** | per_bin | per-animal | Per-animal panel × bin_midpoint_rel_day vs aggregated mean ± SEM (errorbar or shaded band). Line connects bin points. L/R sides as overlaid colors. | **Phase 9 Task 7** |
| **V3** | per_epoch | per-animal | Per-animal panel × boxplot per epoch (pre / acute / sub_acute / chronic) with normalized values per Addendum #6 (value − per_animal_baseline_mean). L/R sides as side-by-side boxes or 2 subpanels. | **Phase 9 Task 7** |
| **V4** | per_bin | phenotype-pooled | One panel × multiple traces (one per phenotype tier: mild / moderate / moderate-severe / severe); bin_midpoint_rel_day vs cohort mean ± SEM within phenotype tier. | **Phase 9.1** |
| **V5** | per_epoch | phenotype-pooled | One panel × boxplots grouped by (phenotype × epoch). Phenotype on x-axis, boxplot per epoch within each phenotype group. | **Phase 9.1** |

**5 figures per headline endpoint × 7 headline endpoints = 35 figures (split V1-V3 in Phase 9 = 21 figures; V4-V5 in Phase 9.1 = 14 figures).**

For ALL OTHER primary scalar endpoints (~38 endpoints excluding spatial), Task 7 produces V1+V2 (recovery curves at two granularities; standard recovery story); V3-V5 produced only on request via CLI flag. Keeps figure count manageable while preserving the headline-vs-supplementary distinction.

**(E) Phase 9.1 scope EXPANDED — partial reversal of Addendum #1 (C).**

Per Addendum #1 (C) lock: "Phase 9.1 reduces to pub-quality polish only — typography, color-palette harmonization, multi-panel composite figures for the paper, ipsi/contra labeling per `mouse_side_to_ipsi_contra`."

Per Addendum #8 (E) revision: Phase 9.1 is **partially un-reduced**. New Phase 9.1 scope:
- **Inherits pub-polish work** from Addendum #1 (C): typography, palette, composites, ipsi/contra labeling.
- **PLUS** produces V4 + V5 figures for the 7 headline kinematic endpoints (14 figures) and for any other primary scalar endpoints flagged for phenotype-pooled visualization.
- **PLUS** produces phenotype-pooled spatial figures (Wasserstein/UOT/JS) per the existing inventory (`scalar_per_animal_time`, 48 spatial endpoints): if/where phenotype-pooled spatial recovery curves are desired.

Phase 9 Task 7's phenotype-pooled tier (originally added in Addendum #1 (B) point 2) is REMOVED from Phase 9 and re-deferred to Phase 9.1.

**(F) Figure output paths.**

Phase 9 Task 7 (per-animal V1/V2/V3):
```
pipeline_outputs/stats/figures/per_animal/<endpoint_slug>/
  v1_per_session_recovery.svg/png
  v2_per_bin_recovery.svg/png
  v3_per_epoch_boxplot.svg/png
```

Phase 9.1 (phenotype-pooled V4/V5):
```
pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/
  v4_per_bin_phenotype_pooled.svg/png
  v5_per_epoch_phenotype_pooled.svg/png
```

**(G) Task estimates revised.**

| | Pre-Addendum-8 | Post-Addendum-8 |
|---|---|---|
| Phase 9 Task 7 | 7-9 days (with phenotype-pooled absorbed) | 5-6 days (per-animal V1/V2/V3 only; phenotype-pooled moved out) |
| Phase 9.1 | small (pub-polish only) | 5-7 days (V4+V5 figures + phenotype-pooled spatial + pub-polish) |
| Phase 9 total | 19-31 days CC | 17-28 days CC (Task 7 shrunk) |
| Phase 9.1 total | 1-2 days | 5-7 days |
| **Combined 9 + 9.1** | **20-33 days** | **22-35 days** |

Net +2 days for the V1-V5 grid expansion. Phase 9 closes slightly sooner; Phase 9.1 grows substantially.

**(H) Side handling default.** L and R sides overlaid as color-coded series on the same axes (matches Phase 7a convention — `SIDE_COLORS` mouse-frame palette, cam-view subplot ordering when 2-panel is used). For V3/V5 epoch boxplots, sides can be (a) side-by-side boxes within each epoch group, or (b) 2 subpanels per epoch — CC chooses per-figure based on legibility.

**Lock changes for inventory CSV (applied 2026-05-23):**
- 3 new derived rows appended (rows 66-68 per CSV); all stamped per (A) above.
- All other rows unchanged.

**Lock changes for kickoff body:**
- Task 7 figure spec for headline kinematic endpoints: V1-V5 grid per (D) above.
- Task 7 phenotype-pooled tier: REMOVED from Phase 9; moved to Phase 9.1.
- Phase 9.1 scoping: expanded per (E) above — update `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` accordingly at Phase 9 close.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1 (modulo phenotype-pooled relocation per (E) above), #2, #3, #4, #5, #6, #7 UNCHANGED.**

---

## Addendum #9 — Separate test-time vs plot-time normalization for fit_per_epoch_lmm (revises Addendum #6 D-F)

**Re-spec triggered by Priya 2026-05-24** during Task 4 close review, after CC's Task 3 deviation #2 surfaced a singular matrix in `fit_per_epoch_lmm` when only 2 epoch levels are present + additive baseline normalization applied. Investigating the root cause revealed that Addendum #6 had conflated **plot normalization** (essential for figure y-axis interpretability) with **test normalization** (which doesn't actually buy statistical power because the LMM's random intercept already absorbs between-animal baseline shifts).

**(A) The conflation in Addendum #6 — clarified.**

Addendum #6 (D)-(F) specified `value_normalized = value − per_animal_baseline_mean` applied at Task 4 stats-runner time, with the LMM running on the normalized values. The intent was twofold but only one purpose actually held up:

| Purpose | Does additive normalization help? |
|---|---|
| Plot y-axis interpretability ("deviation from baseline" framing) | **Yes** — critical for visualizing recovery vs baseline |
| Statistical power for the per_epoch LMM | **No** — `mixedlm(value ~ epoch_label + (1\|animal))` already handles between-animal baseline shifts via the `(1\|animal)` random intercept term. Pre-subtracting baseline doesn't add power; it just rescales the data and creates the per-animal-pre-mean=0 pin that triggers the singular matrix when pre is kept as the LMM reference category |

The singular matrix in CC's Task 3 deviation #2 is the symptom of using normalization at the wrong layer — the LMM doesn't need it and it conflicts with the random intercept identifiability when pre rows are kept as reference.

**(B) Lock: `fit_per_epoch_lmm` runs on RAW values; no additive normalization at test time.**

Updated default: `fit_per_epoch_lmm(..., apply_additive_baseline=False)` for ALL endpoint types (was: True for non-spatial per Addendum #6 D). The LMM formula and structure:

```python
mixedlm(
    formula="value ~ epoch_label",   # NOT value_normalized
    data=inputs_df,                  # ALL epochs: pre + acute + sub_acute + chronic
    groups="animal",
    re_formula="1",                  # random intercept per animal
).fit()
```

- All epoch rows included (pre + post-stroke); pre is the default reference category
- Random intercept `(1|animal)` absorbs between-animal baseline shifts automatically
- Each post-epoch coefficient directly tests "this epoch differs from pre by X units"
- Cross-epoch comparisons (e.g., acute vs chronic) via linear contrasts on the fitted coefficients

**Spatial endpoints continue to use raw values** per Addendum #6 (D) leave-one-out pre-stroke baseline construction — no change there. This addendum aligns NON-SPATIAL endpoint handling with the spatial pattern.

**(C) Scientific interpretation — pre vs post is directly testable in the per_epoch LMM.**

The per_epoch axis was the right place to test pre-vs-each-post-epoch comparisons; Addendum #6's normalization framing had inadvertently broken this by forcing the singular matrix. Under Addendum #9:

| Axis | Test | Question answered |
|---|---|---|
| pre_post (`fit_paired_pre_post_wilcoxon`) | Paired Wilcoxon on per-animal pre-pool vs post-pool means | "Is there a stroke effect at all?" (collapses all post-stroke epochs) |
| per_epoch (`fit_per_epoch_lmm` revised) | LMM coefficient for each post-epoch vs pre reference | "How did the stroke effect evolve? Did acute differ from pre? Did sub_acute differ from pre? Did chronic differ from pre?" |

These are complementary; both stay in Phase 9 scope. The per_epoch LMM now properly addresses the recovery-trajectory question (pre → acute → sub_acute → chronic) at the categorical-predictor level.

**(D) Plot-time normalization spec — preserved per Addendum #6's original intent, just relocated.**

Additive baseline normalization for figure y-axes still happens — just at FIGURE RENDER TIME (Task 7 V3 + Phase 9.1 V5), not at TEST TIME:

```python
# In Task 7 V3 / Phase 9.1 V5 figure rendering code:
def render_per_epoch_figure(inputs_df, animal_info, endpoint_slug):
    baselines = per_animal_baseline_stats(
        inputs_df, pre_filter=lambda r: r.epoch_label == "pre"
    )
    inputs_df["value_normalized"] = inputs_df.apply(
        lambda r: r.value - baselines[r.animal]["mean"], axis=1
    )
    # Plot value_normalized on y-axis grouped by epoch_label, etc.
```

Figures show "deviation from baseline" on the y-axis (per Addendum #6's plotting intent); stats CSVs report raw-scale LMM coefficients (which is what the LMM actually computed).

**(E) Task 3 deviation #2 status — vestigial under Addendum #9.**

CC's Task 3 deviation #2 (`fit_per_epoch_lmm` returns `status="convergence_failed"` + `error="Singular matrix"` for 2-epoch + additive-baseline cases) becomes a vestigial safety net under Addendum #9. The 2-epoch case no longer hits singular matrix on raw values:
- 2 epoch levels (e.g., pre + chronic only) on raw values → identifiable LMM → normal coefficient + p-value output
- Convergence-failed status path remains as a forward-compatibility net for genuinely-degenerate inputs (single-observation-per-animal, etc.) but should not trigger on the current cohort's normal-shaped data

Update Task 3 deviation #2 entry in `notes_running.md` to flag as "VESTIGIAL under Addendum #9 — no longer reachable from cohort data; preserved as safety net."

**(F) Implementation impact (modest CC revision in Task 5 setup).**

CC's `fit_per_epoch_lmm` and `run_per_epoch` need ~20 lines of revision before Task 5 cohort emit:

1. Change `apply_additive_baseline` default to `False` for all endpoint types in `fit_per_epoch_lmm`. Keep the parameter (still callable with `True` for legacy/inspection use or for future plot-time-at-test-time framing if desired).
2. In `run_per_epoch`, remove the `apply_additive_baseline=True` override for non-spatial endpoints — pass nothing (relies on new False default).
3. Add a 3-test sub-suite verifying the LMM correctly identifies per-coefficient effects for known synthetic shifts: (a) 4-epoch case (pre + acute + sub_acute + chronic) with known acute shift of 5 units recovers coefficient ≈ 5.0 ± 0.3; (b) 2-epoch case (pre + chronic) with known shift of 3 units recovers coefficient ≈ 3.0 ± 0.3 WITHOUT singular matrix; (c) zero-shift case (no real effect) yields p_value > 0.5.

**(G) Per_epoch axis re-emit at Task 5.**

CC's Task 4 close report shows per_epoch CSVs already written from the smoke run:
- pre_post/per_epoch: 37 CSVs
- recovery/per_epoch: 84 CSVs
- ipsi_contra/per_epoch: 34 CSVs

**Only `recovery/per_epoch` (84 CSVs) needs re-emit** under Addendum #9 — that's the only axis that uses `fit_per_epoch_lmm`. The `pre_post/per_epoch` runner uses `fit_paired_pre_post_wilcoxon` (not affected). The `ipsi_contra/per_epoch` runner uses `fit_ipsi_contra_wilcoxon` (not affected).

Re-emit happens as part of normal Task 5 cohort emit — no separate ad-hoc re-run needed. Task 5 produces the canonical final emit across all axes × all granularities; Addendum #9-revised `fit_per_epoch_lmm` is what runs for `recovery/per_epoch`.

**(H) Updated Task estimates.**

Negligible delta:
- Task 5 setup: +30 min CC for the `fit_per_epoch_lmm` revision + 3 new tests
- Task 5 cohort emit wall time: unchanged (same number of fits; just different math per-fit)

**Lock changes for kickoff body:**
- Addendum #6 (D)-(F) per_epoch LMM normalization: SUPERSEDED — see Addendum #9 (B)-(C) for the corrected spec.
- Addendum #6 (G) per_epoch axis runner pseudocode: REVISED — `fit_per_epoch_lmm` runs on raw values; baseline subtraction moves to figure-render time.
- Task 3 deviation #2 (singular matrix path): vestigial; flagged in `notes_running.md`.

**Lock changes for inventory CSV:** none.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3, #4, #5, #6 (modulo (D)-(G) corrections per (B)-(C) above), #7, #8 UNCHANGED.**

---

## Addendum #10 — Per-coefficient pre-vs-each-post-epoch comparisons + within-endpoint Bonferroni-Holm correction

**Re-spec triggered by Priya 2026-05-24** during Task 5 headline-summary spot-check. The headline summary's current `per_epoch` rows present `statistic = -log10(min_p across non-reference epoch coefficients)` per Task 3 deviation #3, surfacing only the single most-significant epoch effect per endpoint. This hides the per-comparison structure that's most scientifically actionable: pre-vs-acute, pre-vs-sub_acute, pre-vs-chronic as DISTINCT tests with directional effect sizes. Addendum #10 extracts these per-coefficient results from `fit_per_epoch_lmm` details and surfaces them as separate headline summary rows with within-endpoint Bonferroni-Holm correction.

**(A) The current gap (clarified).**

`fit_per_epoch_lmm` runs an LMM with `epoch_label` as categorical predictor + random intercept per animal, with pre as the default reference category. The fitted model produces:

- `coef[acute]` = "acute differs from pre by X units" with its own p-value
- `coef[sub_acute]` = "sub_acute differs from pre by Y units" with its own p-value
- `coef[chronic]` = "chronic differs from pre by Z units" with its own p-value

These per-coefficient p-values ARE the pre-vs-each-post-epoch tests that the recovery story needs. They're written to `pipeline_outputs/stats/results/recovery/per_epoch/<endpoint>.csv` under the `details["per_epoch"]` JSON-serialized column. But the headline summary CSV's per-endpoint summary collapses them to `-log10(min_p)` per Task 3 deviation #3, losing the per-comparison detail.

For SPATIAL endpoints (`scalar_per_animal_time`), the same per-coefficient detail lives in `recovery/per_epoch/spatial_*.csv` (because spatial endpoints with `comparison_axes_in_scope=recovery` dispatch across all 3 granularities including per_epoch). But the headline summary uses `per_bin` for spatial per Addendum #5 (F), so spatial's pre-vs-each-epoch results don't surface at all in the headline summary.

**(B) Lock: headline summary v2 surfaces per-coefficient pre-vs-each-epoch rows.**

The headline summary CSV regenerates with a new column structure:

| Old (v1) | New (v2) |
|---|---|
| 1 row per (endpoint, axis) at default confirmatory granularity | 1 row per (endpoint, axis, **comparison**) at default confirmatory granularity |
| `axis` column with values: `pre_post`, `recovery`, `ipsi_contra`, `trial_group` | `axis` column SAME values; ADDS `comparison` column |
| `comparison` column does NOT exist | `comparison` column: `collapsed_post` (for axis=pre_post / ipsi_contra / trial_group), `pre_vs_acute` / `pre_vs_sub_acute` / `pre_vs_chronic` (for axis=recovery using per_epoch granularity extraction); for recovery axis at per_session or per_bin: comparison=`continuous_rel_day_slope` or `continuous_bin_midpoint_slope` |
| `q_value_within_axis_granularity_family` | RENAMED `q_within_axis_comparison_family_bh` (BH-FDR within (axis, comparison) family across all confirmatory endpoints) |
| `bonferroni_passed` | UNCHANGED for non-per-epoch rows; for per-epoch rows: ADDS `q_within_endpoint_holm` (Bonferroni-Holm within endpoint across 3 epoch comparisons); `bonferroni_passed` for per-epoch rows = `q_within_endpoint_holm < 0.05` (sequential correction) |

**For each (endpoint × axis=recovery) row in v1 that used per_epoch summary**, v2 emits **3 rows** (one per post-epoch comparison) instead of 1.

Spatial endpoints (`scalar_per_animal_time`) gain a parallel set of per-epoch rows (extracted from `recovery/per_epoch/spatial_*.csv`) alongside the existing per_bin slope row. So each spatial endpoint emits 4 rows in v2: 1 continuous slope (per_bin) + 3 pre-vs-each-epoch (per_epoch). Per_bin slope row retains `comparison=continuous_bin_midpoint_slope`.

Non-spatial scalar endpoints (Cat A, kinematic per-trial, etc.) similarly emit per-comparison rows for any axis where per_epoch granularity is computed and surfaces per-coefficient pre-vs-each-epoch detail. Practical impact: most non-spatial endpoints gain 3 rows in `axis=recovery, comparison=pre_vs_*` series replacing the previous 1 summary row.

**Estimated v2 row count:** 105 (v1) → ~180-220 rows (v2).

**(C) Within-endpoint Bonferroni-Holm correction (NEW).**

For each endpoint × axis where 3 pre-vs-each-epoch comparisons are produced (acute, sub_acute, chronic), apply Bonferroni-Holm sequential correction within the endpoint:

```python
def bonferroni_holm_per_endpoint(p_values_dict: dict[str, float]) -> dict[str, float]:
    """Bonferroni-Holm sequential correction for 3 epoch comparisons per endpoint.

    Input: {pre_vs_acute: p1, pre_vs_sub_acute: p2, pre_vs_chronic: p3}
    Output: {pre_vs_acute: q1, ...} with Holm-adjusted q-values.
    """
    sorted_items = sorted(p_values_dict.items(), key=lambda kv: kv[1])
    n = len(sorted_items)
    q = {}
    prev_q = 0.0
    for rank, (comp, p) in enumerate(sorted_items, start=1):
        q_raw = p * (n - rank + 1)
        q_clipped = min(1.0, max(prev_q, q_raw))
        q[comp] = q_clipped
        prev_q = q_clipped
    return q
```

Result: each per-epoch row in v2 gets a `q_within_endpoint_holm` value. `bonferroni_passed` for these rows uses this q-value (< 0.05) instead of the cross-endpoint Bonferroni.

The cross-endpoint correction (`q_within_axis_comparison_family_bh`, BH-FDR across confirmatory endpoints in same axis × comparison) ALSO applies independently. So per-epoch rows have BOTH:
- `q_within_endpoint_holm` (3-way within-endpoint Holm correction; standard for "3 related comparisons within one test")
- `q_within_axis_comparison_family_bh` (cross-endpoint FDR within confirmatory family)

`bonferroni_passed` is the **more stringent** of the two: `(q_within_endpoint_holm < 0.05) AND (q_within_axis_comparison_family_bh < 0.05)` for confirmatory rows. For exploratory rows (non-confirmatory): just `(q_within_endpoint_holm < 0.05)`. This dual correction is intentionally conservative — pre-registered confirmatory endpoints need to clear both within-endpoint multiple comparisons AND cross-endpoint multiple comparisons.

**(D) Implementation — small headline-summary-only refactor.**

No re-running of tests, LMM math, or per-axis result CSVs. The underlying data already exists on disk in `recovery/per_epoch/<endpoint>.csv` under `details["per_epoch"]`. Addendum #10 is a presentational refactor of the headline summary builder:

1. Headline summary builder script (`scripts/phase_9_stats/build_headline_summary.py`) gains a new code path that, for endpoints where per_epoch granularity is in scope:
   - Read `recovery/per_epoch/<endpoint>.csv`
   - Parse `details["per_epoch"]` JSON column → dict of per-coefficient (effect, p, ci_lower, ci_upper)
   - Emit 3 rows per endpoint (one per post-epoch comparison)
   - Apply Bonferroni-Holm within-endpoint
2. Apply BH-FDR within (axis, comparison) family across confirmatory endpoints (existing per-axis logic; just adds `comparison` to the grouping key).
3. Replace v1 headline summary CSV with v2.

Estimated CC work: ~1-2 hr (presentational refactor of the existing builder script). No new tests on the LMM side; one new test on Bonferroni-Holm correctness using a known-input case.

**(E) Backward compatibility.**

V1 headline summary CSV is ~24 hr old, no downstream consumers depend on it (Phase 9 Task 6/7 haven't started; Phase 9.1 doesn't exist yet). V2 simply replaces v1. The legacy v1 file gets overwritten in place; commit message clearly notes the schema bump from v1 to v2.

**(F) Phase 9.1 V5 figures benefit from this.**

The V5 phenotype-pooled epoch boxplots in Phase 9.1 (per Addendum #8) visually display pre-vs-each-epoch comparisons. Addendum #10's per-coefficient extraction is the data structure Phase 9.1 V5 renderers consume — each boxplot's annotation can show the per-comparison p-value + q-value pair without re-running the LMM at render time. Locks the data-flow contract between Task 4 stats results and Phase 9.1 V5 figures.

**(G) Lock changes for kickoff body.**

- Task 3 deviation #3 (`fit_per_epoch_lmm.statistic = -log10(min_p)`): NOW VESTIGIAL under Addendum #10. The min-p summary still exists in the FitResult.statistic field, but the headline summary v2 doesn't use it; per-coefficient details surface as separate rows. Update `notes_running.md` to flag deviation #3 as vestigial.
- Task 4 deviation #2 (Bonferroni emission scope, currently within (axis, granularity) family): RESOLVED under Addendum #10. New scope: within (axis, comparison) family at the confirmatory granularity per value_type. `comparison` is the new grouping dimension.
- Headline summary CSV schema (Step 3 of original Task 5 spec): SUPERSEDED by Addendum #10 (B) spec. ~180-220 rows with the new comparison column.

**(H) Task estimates.**

Negligible delta:
- Task 5 fixup: +1-2 hr CC for headline summary v2 builder + ~30 min for the Bonferroni-Holm test. Can land alongside vxy materialization fixup OR as a sequential commit before Task 6 completes.

**Lock changes for inventory CSV:** none.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1, #2, #3, #4, #5, #6 (modulo (D)-(G) corrections per #9 (B)-(C)), #7, #8, #9 UNCHANGED.**

---

## Addendum #11 — Trial-count bias investigation: NOT confirmed (doc-only addendum)

**Investigation triggered by Priya 2026-05-25** during Task 8 verification: hypothesized that elevated tongue kinematic acute coefficients (tongue_lick1_y_peak +21.79 px; vxy peak endpoints) in PS51/PS54/PS55 acute periods might be inflated by low-n-trial sessions with outlier-dominated session means.

**Investigation conducted at** `.scratch_phase_9/_trial_count_bias_investigation.py` (commit 329c4ce). Detailed findings at `.scratch_phase_9/_trial_count_bias_findings.md`.

**Verdict: BIAS NOT CONFIRMED.** Three results contradict the outlier-inflation hypothesis:

1. **Direction is opposite the prediction.** Low-n acute sessions (< 10 detected trials) had LOWER per-session means than high-n acute sessions, not higher. Ratios low/high for the 4 suspect endpoints: 0.67-1.00 (PS51) and 0.89-1.00 (severe PS54+PS55 pool). Every cell ≤ 1.00.

2. **Counterfactual LMM coefficient changes ≤ 4%** at n_min=10 trial-count filter. Dropping 10 of 247 sessions (4% of data, concentrated in PS51 + PS55) shifts the acute LMM coefficient by at most 3.5% in any of the 4 suspect endpoints. p-values remain < 1e-15 in all cases. The acute effect is robust to the filter.

3. **Alternative mechanism is more scientifically coherent.** Investigation found that trial count and per-trial excursion both correlate POSITIVELY with engagement during acute. Low-n acute sessions reflect animals making few + constrained attempts (short y_peak, low vxy); high-n acute sessions reflect animals already partially recovering (more attempts AND more excursion per attempt). This is "engagement-correlated kinematics" rather than "outlier dominance" — strengthens the recovery-dynamics interpretation of the Phase 9 cohort results.

**(A) Production impact: NONE.** No source code changes; no parquet re-emit; no headline summary regeneration; no Task 7 figure re-render. The Phase 9 Task 5 cohort emit + Addendum #10 v2 headline summary are the canonical Phase 9 results.

**(B) Paper interpretation:** the tongue_lick1_y_peak +21.79 px acute coefficient + sign-flip pattern (acute overshoot → sub_acute undershoot → chronic persistent undershoot) is REAL physiological signal, uniform across all 8 animals per Task 7 V3 visual gate, and ROBUST to trial-count filtering per this investigation. Strong headline material for the recovery-trajectory story.

**(C) Forward pointers carried to Phase 9.x** (per Phase 9.x scoping doc §7.5 added 2026-05-25):
- (a) Sub_acute low-n vs high-n vxy divergence in severe cohort (ratios 1.12-1.50; OPPOSITE direction from acute) — warrants per-phenotype investigation in Phase 9.x
- (b) PS55 acute uniformly low-engagement (no ≥20-trial sessions; vs PS54 with 5 such sessions) — DLC tracking quality sanity-check warranted before Phase 9.x

**(D) Methodology citation in paper methods:** "We tested for trial-count bias in cohort-level recovery results by comparing per-session means in low-n (<10 detected trials) vs high-n (≥10 detected trials) sessions and by computing counterfactual LMM coefficients under a trial-count filter (n_min ∈ {5, 10, 20}). Low-n sessions had lower per-session means than high-n sessions (opposite the outlier-inflation prediction); counterfactual LMM coefficients changed by ≤4%. Cohort acute results are robust to trial-count filtering."

**(E) Lock changes:** none. This addendum documents an investigation and its negative result. No code, parquet, or schema changes.

**(F) Notes log entry:** Task 8 trial-count-bias investigation = RESOLVED, alternative engagement-correlated mechanism documented in Phase 9.x scoping doc §7.5. Carried to Phase 9 DECISIONS at Task 9 close.

**ALL OTHER LOCKS FROM KICKOFF BODY AND ADDENDA #1-#10 UNCHANGED.**

---
