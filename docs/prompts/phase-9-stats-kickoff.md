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

3. **Notebook integration:** add a `INCLUDE_RECOVERY_TRAJECTORIES = True` knob in `notebooks/15_spout_behavior_visual_gate.ipynb` USER INPUTS cell. Re-render cohort.

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
