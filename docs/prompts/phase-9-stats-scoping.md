# Phase 9 — Statistical Analyses on Phase 7c.2 + Kinematics Outputs — SCOPING DOCUMENT

> **⚠️ THIS IS A SCOPING DOC, NOT A KICKOFF.** Drafted 2026-05-15 by Cowork during the Phase 7c.2 in-flight period for forward planning. Open scoping questions are flagged inline with **OPEN-Q:**; Priya fills these in to drive a follow-on kickoff draft. The kickoff itself happens AFTER Phase 7c.2 close (and probably after Phase 7d + F-P-7 close too, since Phase 9 wants the canonical output tree).
>
> **Intended next step:** Priya reviews + answers the OPEN-Qs → Cowork drafts the actual Phase 9 kickoff (`docs/prompts/phase-9-stats-kickoff.md`) based on the answers.

---

## 1. Goals + scope

Phase 9 is the statistical-inference layer of the consolidated pipeline. Phase 7c.2 + Phase 7a kinematics produce per-session/per-trial/per-animal arrays of derived quantities; Phase 9 asks **whether those quantities differ in scientifically-meaningful ways** between conditions (pre-stroke vs post-stroke, L vs R hemisphere/trial, recovery time-course, cohort-level effects, etc.).

**Primary deliverable:** a directory of `.csv` / `.parquet` files under `pipeline_outputs/stats/` summarizing test statistics + p-values + effect sizes + (optionally) bootstrap/permutation distributions for every (endpoint, comparison) pair. Plus a directory of stats-summary figures showing the headline results — distinct from Phase 7c.2's exploratory heatmaps; these are quantitative summary plots (forest plots, recovery curves with CIs, etc.).

**Out of scope (these belong to other phases):**
- Single-trial visualizations (Phase 7c.2's `tone_aligned_heatmaps/` etc.).
- Aesthetic-tier polish for paper figures (pub-figures phase).
- New behavioral endpoint computation (Phase 7a / kinematics-feature-engineering phases are upstream).
- Causal inference / mechanistic modeling (out of scope for this pipeline).

---

## 2. Inputs from upstream phases

| Source | Path | Granularity | Useful for |
|---|---|---|---|
| Per-frame DLC | `dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet` (post-Phase-7d) | per-frame | Time-resolved kinematic trajectories, derived per-frame quantities (tongue angle, velocity, etc.). |
| Per-trial endpoints | `dlc_kinematics/per_trial/{tongue,jaw}/<animal>/<date>.json` (post-Phase-7d) | per-trial | Scalar features per trial (lick1_t_peak_ms, lick amplitudes, latencies, etc.) — primary input to most statistical tests. |
| Tongue angle | `dlc_kinematics/tongue_angle/within_session/...` + `cross_session/...` | per-session + per-bin | Angle distribution metrics, peak angle, angular variance. |
| Tongue/jaw mismatch | `dlc_kinematics/tongue_jaw_mismatch/{candidate_trials,within_session,cross_session}/...` | per-trial (candidates) + per-session | Cross-bodypart coordination metric. |
| Mean/SEM cohort | `dlc_kinematics/mean_sem/<bodypart>/<center_mode>/<trial_group>/<plot_family>/<animal>/...` | per-(animal, bin, plot_family) | Group-level mean trajectories — useful for visualizing stats results overlaid on observed means. |
| Licking dynamics | `dlc_kinematics/licking_dynamics/traces/...` + `day_binned/...` | per-trial events + per-bin aggregates | Lick rate, lick rhythm, post-stroke recovery in lick patterns. |
| Spatial heatmaps | `dlc_kinematics/tone_aligned_heatmaps/...` + `whole_session_heatmaps/...` (Phase 7c.2 SVGs + likely accompanying NPZ if we resurrect cached data) | per-session + per-bin spatial histograms | Spatial-distribution tests; OT-based distribution comparisons. |
| Phase 7c.2 proportion-diff arrays | (compute-on-demand from centered parquets) | per-bin | Quantitative spatial-shift summaries. |
| Phase 7c.2 UOT outputs | (compute-on-demand) | per-bin | Mass-transport magnitudes; OT cost as a single-number spatial-shift metric. |
| Animal metadata | `configs/animals.yaml` | per-animal | Stroke side, stroke date, cohort membership, baseline pool definition (rel_day ≤ 0). |

**OPEN-Q 1:** Should Phase 9 read from these output files DIRECTLY, or should we materialize an intermediate `pipeline_outputs/stats/inputs/` tree of pre-aggregated parquets (one row per (animal, date, trial, endpoint))? Materialized intermediate is cleaner for test code but adds disk + emit time. Direct read is simpler but each test re-aggregates from many small files.

---

## 3. Comparison axes

The scientific question structure determines which comparisons matter. Standard axes:

### 3.1 Pre-stroke vs post-stroke
- **H0:** endpoint distribution doesn't change after stroke.
- **Pairing:** within-animal (each animal has its own pre and post pools). Random-effects model handles cross-animal variability.
- **Effect direction:** typically interested in BOTH directions (impairment in some endpoints, compensation in others).

### 3.2 Recovery time-course
- **H0:** post-stroke endpoint stays at acute-injury level (no recovery).
- **Model:** regression of endpoint vs rel_day (days since stroke), restricted to post-stroke sessions (rel_day > 0). Random intercept per animal.
- **Effect direction:** typically expect partial recovery (slope toward pre-stroke baseline).

### 3.3 L vs R asymmetry
- **H0:** symmetric performance on L vs R trials.
- **Pairing:** within-session (each session has both L and R trials in bilateral protocols).
- **Effect direction:** expect L/R asymmetry to grow post-stroke (impaired contralateral-to-stroke side).
- **OPEN-Q 2:** Which animals are unilateral stroke vs bilateral? `configs/animals.yaml` should encode `stroke_side: L | R | bilateral` (or equivalent). If not present, this is upstream metadata that Phase 9 needs to assume or derive.

### 3.4 Trial-group effects (all/L/R bias for tone-aligned)
- This is more about behavioral bias (animal preference) than asymmetry per se.
- **H0:** equal performance on all/L/R-anticipated trials.

### 3.5 Spatial-distribution tests (per-bin or distribution-level)
- **H0:** spatial distribution unchanged post-stroke.
- **Options:**
  - **Per-bin tests:** test pre vs post proportion at every spatial bin; massive multiple-comparisons problem (100×100 = 10,000 tests per family entry per scope).
  - **Distribution-level tests:** single test per (animal, family_entry, scope) comparing pre vs post distributions. Earth Mover's distance / OT cost as test statistic; permutation null.
- **OPEN-Q 3:** which level (per-bin or distribution-level)? Per-bin gives spatial localization of changes; distribution-level gives a cleaner statistical narrative. Likely BOTH have value for different paper figures.

### 3.6 Cohort-level: 2-day vs 7-day bin animals
- PS46-50 have 2-day session cadence; PS51-54 have 7-day cadence.
- **OPEN-Q 4:** Pool these for cohort-wide effects, or analyze separately? Pooling assumes the two cohorts are comparable; separate analyses preserve cohort-specific stroke recovery dynamics if they differ.

---

## 4. Test methodology

### 4.1 Parametric vs nonparametric vs permutation

**Default for paired pre-post:** Wilcoxon signed-rank test on within-animal-paired endpoint values. Robust to non-Gaussianity. Permutation alternative if Wilcoxon assumptions are concerning.

**Default for regression (recovery time-course):** linear mixed-effects model (`statsmodels.formula.api.mixedlm`) with random intercept per animal. Endpoint ~ days_since_stroke + (1 | animal). Bootstrap confidence intervals.

**Default for spatial distribution-level:** Earth Mover's distance / 1D-marginalized projections + permutation null over pre vs post labels.

**OPEN-Q 5:** Standardize on one default per comparison axis, or run multiple methods and report sensitivity?

### 4.2 Multiple comparisons

| Comparison set | Family size | Suggested correction |
|---|---|---|
| Per-endpoint pre-post test across endpoints | ~10-30 endpoints | Benjamini-Hochberg FDR at 0.05 |
| Per-bin spatial tests | ~10,000 bins | BH-FDR; voxel-level + cluster-level corrections (cf. fMRI) |
| Per-animal recovery slopes | ~9 animals | None (per-animal slope is a primary readout, not a hypothesis-test grid) |
| Per-(family_entry, scope) distribution-level tests | ~14 (7 families × 2 scopes) | BH-FDR; or Bonferroni if family-wise control desired |

**OPEN-Q 6:** Which tests are CONFIRMATORY (pre-registered, family-wise control) vs EXPLORATORY (FDR-controlled)? Affects how the paper writes up results.

### 4.3 Effect sizes

Report Cohen's d (or analog) alongside p-values. For OT-cost distribution-level tests, report the raw OT cost + bootstrap CI as the effect size.

### 4.4 Bootstrap / permutation infrastructure

For tests where parametric inference is questionable, use permutation-based null distributions. Standardized infrastructure:

```python
def permutation_null(endpoint_values, group_labels, n_permutations=10_000):
    """Generate null distribution of test statistic under permuted group labels."""
    null_stats = []
    for _ in range(n_permutations):
        permuted = np.random.permutation(group_labels)
        null_stats.append(test_stat(endpoint_values, permuted))
    return np.array(null_stats)
```

**OPEN-Q 7:** n_permutations default (10k? 100k? 1M)? Bigger = more p-value precision at low p but longer compute.

---

## 5. Software + dependencies

| Need | Library |
|---|---|
| Mixed-effects models | `statsmodels.formula.api.mixedlm`, `pymer4` (for lme4-style models) |
| Wilcoxon / Mann-Whitney / KS | `scipy.stats` |
| Permutation tests | custom (numpy) |
| Effect sizes | `statsmodels.stats.power` or custom |
| Earth Mover's distance | `POT` (already in pipeline for Phase 7c.2 UOT) |
| Multiple comparisons | `statsmodels.stats.multitest` (BH, Bonferroni) |
| Bootstrap CIs | `scipy.stats.bootstrap` or custom |

**OPEN-Q 8:** Any Bayesian methods desired (e.g., BEST for paired comparisons, hierarchical Bayesian models for cohort)? `pymc` would be the standard library. Adds complexity if so.

---

## 6. Phase structure (proposed)

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch | (none) | 0 | <5 min |
| Task 1 — Endpoint inventory + selection | `.scratch_phase_9/endpoint_inventory.csv` cataloging every analyzable endpoint; **Priya selects PRIMARY set** | 0 | 1-2 hr + Priya review |
| Task 2 — Stats input materialization (if OPEN-Q 1 → materialize) | Aggregated parquets at `pipeline_outputs/stats/inputs/<endpoint>/<animal>.parquet` | 2-3 | 1-2 days |
| Task 3 — Comparison-axis test code | Test functions for each comparison axis (§3) | 3-5 | 3-5 days |
| Task 4 — Cohort-wide test run | `pipeline_outputs/stats/results/<axis>/<endpoint>.csv` | 1-2 | 1-2 hr cohort compute |
| Task 5 — Stats summary figures | Forest plots, recovery curves, distribution-level summaries | 2-3 | 2-3 days |
| Task 6 — Verification / sanity gate | `.scratch_phase_9/verdict.md` + Priya scientific review | 0 | 1-3 days (Priya bandwidth) |
| Task 7 — DECISIONS + MIGRATION_LOG | 2 docs files | 1 | 30-60 min |

**Estimated total: ~15-25 commits, ~2-3 weeks CC wall time** (excluding Priya scientific review time). Genuinely a large phase.

**OPEN-Q 9:** Split into sub-phases (e.g., Phase 9.1 endpoint-set + pre-post tests; Phase 9.2 recovery + L/R; Phase 9.3 spatial-distribution tests)? Smaller pieces ship faster + give Priya feedback at each step.

---

## 7. Dependencies + ordering

**Hard prerequisites:**
- Phase 7c.2 closed (canonical post-fix output tree).
- Phase 7d closed (naming-hygiene; otherwise the per-frame/per-trial path lookups change mid-phase).
- F-P-7 alignment-templates closed (otherwise stats code depends on the legacy tree being available, which is brittle).

**Soft prerequisites:**
- Cohort enumeration YAML-driven refactor (since Phase 9 wants YAML-driven enumeration too; bundling vs separate phase decision).

**Could-happen-concurrently:**
- Pub-figures phase polish on Phase 7c.2 outputs.

---

## 8. Open scoping questions (full list — Priya to fill in)

**OPEN-Q 1:** Direct-read vs materialized intermediate tree at `pipeline_outputs/stats/inputs/`?

**OPEN-Q 2:** Where does `stroke_side` metadata live (per-animal: L / R / bilateral)?

**OPEN-Q 3:** Spatial tests at per-bin granularity, distribution-level, or both?

**OPEN-Q 4:** Pool 2-day-bin cohort (PS46-50) and 7-day-bin cohort (PS51-54), or analyze separately?

**OPEN-Q 5:** Standardize on one default test method per comparison axis, or run multiple methods + report sensitivity?

**OPEN-Q 6:** Which tests are CONFIRMATORY (pre-registered, family-wise control) vs EXPLORATORY (FDR-controlled)?

**OPEN-Q 7:** Permutation n_permutations default? (10k, 100k, 1M, or per-test depending on expected p-value range)

**OPEN-Q 8:** Bayesian methods desired (BEST, hierarchical models)?

**OPEN-Q 9:** Split Phase 9 into sub-phases (9.1/9.2/9.3) or run as one large phase?

**OPEN-Q 10:** What endpoints are PRIMARY for the paper? Suggested list to start the Task 1 inventory:
- lick1_t_peak_ms (latency to first lick)
- lick rate post-tone
- tongue angle peak / mean / variance
- jaw amplitude peak
- L vs R first-lick latency
- tongue-jaw mismatch rate
- Spatial proportion shift OT cost (Phase 7c.2 UOT cost as scalar)
- Recovery slope per endpoint
- ... (Priya adds + prioritizes)

**OPEN-Q 11:** Stats publication strategy — what figures + tables does the paper need? Affects which results are headline vs supplementary.

**OPEN-Q 12:** Cross-validation / holdout for any classifier-based approaches? Or is this purely descriptive stats?

---

## 9. References

- Phase 7c.2 kickoff for compute-on-demand spatial figure architecture: `docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md`.
- Phase 7d kickoff for naming-hygiene that affects per-frame/per-trial paths: `docs/prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md`.
- F-P-7 kickoff for alignment-templates dependency: `docs/prompts/phase-7-pre-alignment-templates-kickoff.md`.
- Memory `project_dlc_kinematics_features_naming_cleanup_forward_pointer.md` for the granularity-first layout that Phase 9 reads from.
- `configs/animals.yaml` for cohort definition + per-animal metadata.
- POT library docs for OT cost computation (already in pipeline for Phase 7c.2).
- statsmodels docs for mixed-effects models.

---

## 10. Next steps

1. Priya reviews this scoping doc + answers the 12 OPEN-Qs (inline edits or a separate response document).
2. Cowork drafts the actual Phase 9 kickoff (`phase-9-stats-kickoff.md`) based on the answers.
3. Kickoff specifies endpoint list, test methods, materialization choice, sub-phase split, dependencies.
4. CC executes per kickoff.
