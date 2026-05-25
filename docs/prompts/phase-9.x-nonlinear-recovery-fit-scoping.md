# Phase 9.x — Per-phenotype Stats + Per-animal Nonlinear Recovery Fits — SCOPING DOCUMENT

> **⚠️ SCOPING DOC, NOT KICKOFF.** Originally drafted 2026-05-24 as "nonlinear recovery fits" only. **Scope expanded 2026-05-25** to also include per-phenotype stratification of Phase 9's primary statistical tests (all 4 axes × per-phenotype-tier). Phase 9.x runs after Phase 9 closes; Phase 9.1 V4/V5 phenotype-pooled figures may run before or in parallel. Naming is provisional — final phase number assigned when work begins.

---

## 1. Two motivations for one combined phase

**(1.A) Per-phenotype statistical stratification.** Phase 9 (per Addendum #5) explicitly locked all primary tests at cohort level: one `fit_recovery_mixedlm` slope across all 8 animals; one `fit_per_epoch_lmm` coefficient per epoch averaged across all 8 animals; one cohort-level paired Wilcoxon for pre_post and ipsi_contra axes. This was the right call for Phase 9 given cohort size (n=8), but cohort-level results average over distinct phenotype dynamics:
- Mild animals (PS47-50, n=4): minimal deficits; cohort-level recovery slope is diluted by their near-zero contribution
- Severe animals (PS54, PS55, n=2): deep acute deficits + step-change recovery; cohort-level slope averages this dramatically with mild
- Moderate (PS46) + Moderate-severe (PS51): single-animal cases that get folded into the cohort average

**Phase 9.x stratifies stats by phenotype tier** so the paper can report per-phenotype recovery dynamics with phenotype-specific effect sizes + p-values, complementing Phase 9's cohort-level results.

**(1.B) Per-animal nonlinear recovery fits.** Phase 9 Task 6 visual gate (2026-05-24) surfaced a linear-LMM-vs-bimodal-recovery mismatch for severe-phenotype animals. The cohort `fit_recovery_mixedlm` uses a linear-in-rel_day slope; severe animals show step-change recovery (deep acute → chronic plateau) that doesn't fit the linear form. Specifically:
- PS54: `first_lick_accuracy_all` drops from ~0.9 pre-stroke to ~0 acute (rel_day 1-17), then plateaus at ~0.5 sub_acute/chronic (rel_day 18-70). A linear-in-rel_day fit extrapolates ABOVE PS54's chronic data because the linear slope can't represent the step.
- PS55: similar pattern with the additional +10d shift in epoch boundaries; same linear-fit limitation.

Phase 9.x adds **per-animal nonlinear fits** (exponential decay, piecewise linear, sigmoidal) for endpoints + animals where recovery shape is meaningfully non-linear, complementing the per-phenotype stratified linear LMMs from (1.A).

The two motivations are unified by a common theme: **per-phenotype + per-animal recovery dynamics that the cohort-level Phase 9 stats can't capture.**

## 2. Goals + scope

**Primary deliverables:**
1. **Per-phenotype stratified statistical tests** across all 4 Phase 9 axes (`pre_post`, `recovery`, `ipsi_contra`, `trial_group`), at appropriate granularities, using the 3-tier phenotype grouping locked in §3 below.
2. **Per-animal nonlinear recovery fits** (exponential decay, piecewise linear, sigmoidal) for endpoints where Phase 9 linear-LMM-vs-empirical-pattern mismatch is evident.
3. Per-phenotype + per-animal results tables + visualization figures complementing Phase 9 + 9.1 outputs.

**Out of scope:**
- New endpoints (uses Phase 9 stats inputs as-is).
- Re-running cohort-level Phase 9 tests (those stay as-is; Phase 9.x results are additive).
- Aesthetic-tier polish for paper figures (pub-figures phase).

## 3. Per-phenotype tier grouping — 3 tiers (LOCKED Priya 2026-05-25)

Per-phenotype stratification uses a 3-tier grouping that pools moderate + moderate-severe to ensure paired-test viability:

| Phenotype tier | Animals | n_animals | Per-phenotype LMM data points (avg sessions/animal × n) |
|---|---|---|---|
| Mild | PS47, PS48, PS49, PS50 | 4 | ~50-100 (4 animals × ~13-25 sessions each) |
| Moderate-pool | PS46, PS51 | 2 | ~40-80 (2 animals × ~20-40 sessions each) |
| Severe | PS54, PS55 | 2 | ~100+ (2 animals × ~50+ sessions each) |

**Rationale for pooling moderate + moderate-severe:** Both PS46 (moderate) and PS51 (moderate-severe) have clear deficits + recovery patterns; pooling them gives n=2 for paired tests rather than n=1 + n=1 separately, enabling cohort-level inference within the pooled tier. Paper narrative frames the pool as "intermediate severity" or "moderate-pool" and notes that PS46 vs PS51 differ in specific recovery dynamics (sub-pool description in figure legends).

**n_animals caveat by tier:**
- Mild (n=4): proper cross-animal inference; effect coefficients generalize to "mild phenotype animals"
- Moderate-pool (n=2): cross-animal inference but with only 2 animals; results described as "average across the 2 moderate-pool animals (PS46, PS51)"
- Severe (n=2): same — "average across the 2 severe animals (PS54, PS55)"

Per-session data within epoch (per Addendum #6) provides ~20-100 data points per (phenotype, epoch) combination — well beyond the minimum for LMM convergence even with n_animals=2. The LMM is statistically valid for all tiers; what differs is the **scope of cross-animal generalization** in paper claims.

## 4. Per-phenotype axis × granularity coverage

All 4 Phase 9 axes get per-phenotype stratification. Each (axis, granularity) pair currently emits cohort-level results; Phase 9.x adds 3 per-phenotype results per (axis, granularity) at the confirmatory granularity per value_type.

| Axis | Test (cohort-level in Phase 9) | Per-phenotype extension in Phase 9.x |
|---|---|---|
| `pre_post` | Paired Wilcoxon on per-animal mean diffs | Per-phenotype: paired Wilcoxon within each tier (mild n=4 pairs; moderate-pool n=2 pairs; severe n=2 pairs). Mild gives proper inference; n=2 tiers are underpowered but reportable with caveat. |
| `recovery` | `fit_recovery_mixedlm` (continuous rel_day) | Per-phenotype: `fit_recovery_mixedlm(..., phenotype_filter=tier)`. Each tier gets its own slope + CI + p-value. Heavier per-session data ensures LMM convergence. |
| `recovery/per_epoch` | `fit_per_epoch_lmm` (categorical epoch_label) | Per-phenotype: same LMM with `phenotype_filter`. Each tier gets per-coefficient pre_vs_acute / pre_vs_sub_acute / pre_vs_chronic results. |
| `ipsi_contra` | Paired Wilcoxon on (L_mean - R_mean) within-animal | Per-phenotype: same Wilcoxon within tier. Mild n=4 viable; n=2 tiers underpowered. |
| `trial_group` | Friedman | Per-phenotype: Friedman within tier (currently a no-op due to inventory only having 2-group endpoints; may remain empty). |

## 5. Per-animal nonlinear fits — likely fit classes

For endpoints + animals where per-phenotype linear LMM fit is visibly poor (per Phase 9.1 V4/V5 figure visual gate):

| Class | Equation | Best for |
|---|---|---|
| **Exponential decay** | `y(t) = baseline - amplitude * (1 - exp(-t/tau))` | Smooth recovery (moderate-pool) |
| **Piecewise linear / step** | 2-segment linear with knee point, OR step function at known epoch boundary | Bimodal step-change (severe) |
| **Sigmoidal (logistic)** | `y(t) = baseline + amplitude / (1 + exp(-(t-t50)/k))` | S-shaped recovery |

Fit class selected per (animal, endpoint) via AIC/BIC OR pre-picked per phenotype based on visual inspection. Phase 9.x kickoff (drafted post-9.1) finalizes the model-selection methodology.

## 6. Result structure

**Phase 9 result tree** (current, cohort-level):
```
pipeline_outputs/stats/results/<axis>/<granularity>/<endpoint>.csv
```

**Phase 9.x adds** a parallel per-phenotype tree:
```
pipeline_outputs/stats/results/<axis>/<granularity>/per_phenotype/<phenotype>/<endpoint>.csv
```
plus a per-animal nonlinear-fit tree:
```
pipeline_outputs/stats/results/recovery_fits/per_animal/<animal>/<endpoint>.csv
pipeline_outputs/stats/results/recovery_fits/per_phenotype/<phenotype>/<endpoint>.csv
```

**Headline summary v3** (Phase 9.x extension of Addendum #10's v2): adds `phenotype` column with values `cohort` / `mild` / `moderate_pool` / `severe`. Cohort row stays (existing pattern); per-phenotype rows added. Row count grows from ~306 (v2) to ~900-1200 (v3, 4× per-row from phenotype dimension).

## 7. Dependencies + ordering

**Hard prerequisites:**
- Phase 9 closed (provides canonical cohort-level stats results tree + materialized inputs).

**Soft prerequisites:**
- Phase 9.1 closed OR in progress (V4/V5 phenotype-pooled figures provide visual gate for which fit classes are appropriate per phenotype).

**Phase 9.x runs AFTER Phase 9 closes**, parallel-or-sequential with Phase 9.1. Estimated ordering: Phase 9 → Phase 9.1 → Phase 9.x. If Phase 9.1 reveals a fit-class need that Phase 9.x should prioritize, Phase 9.1 visual gate informs Phase 9.x kickoff scope.

## 7.5. Sub-investigations carried forward from Phase 9 (added 2026-05-25)

These items surfaced during Phase 9 Task 8 verification (investigation at `.scratch_phase_9/_trial_count_bias_investigation.py` + findings at `.scratch_phase_9/_trial_count_bias_findings.md`) but are out-of-scope for Phase 9 close. They warrant focused investigation in Phase 9.x where per-phenotype stratification provides the right analytical framework:

**(7.5.a) Sub_acute low-n vs high-n vxy divergence in severe cohort.** Investigation found that for severe-phenotype animals, low-n-trial sub_acute sessions show HIGHER vxy values than high-n-trial sub_acute sessions (ratios 1.12-1.50). This is opposite the acute pattern (where engagement and excursion correlated positively). Hypothesis: by sub_acute, persistent-low-engagement animals (those still recovering slowly) may have systematically different per-trial kinematics than partially-recovered high-engagement animals. Per-phenotype Phase 9.x with sub-phenotype splits on engagement level would reveal whether this is a real bifurcation within severe phenotype OR an artifact of the small severe cohort (n=2).

**(7.5.b) PS55 acute uniformly low-engagement.** PS55 has NO acute sessions with ≥20 trials (compared to PS54 with 5 such sessions). Could reflect deeper behavioral deficit (PS55 received higher laser power: 5.0 mW vs PS54's 3.0 mW) OR DLC tracking quality degradation specifically in PS55 acute sessions (animal positioning, occlusion, lighting). Per-animal DLC tracking QC pass on PS55 acute sessions warranted before Phase 9.x — verify the low engagement is behaviorally real, not a tracking artifact. If tracking artifact, may affect PS55's contribution to cohort + severe-phenotype Phase 9.x results.

## 8. Open scoping questions

**Per-phenotype stats (1.A) questions:**
- **OPEN-Q 1:** Per-phenotype within-endpoint Bonferroni-Holm correction — apply across the 3 tiers (mild / moderate_pool / severe) for each endpoint × axis × comparison, OR rely on cross-phenotype BH-FDR within (axis, comparison, phenotype) family? Both are defensible; the choice affects how the paper reports per-phenotype significance.
- **OPEN-Q 2:** Cohort row in headline summary v3 — keep as separate row (current) or annotate per-phenotype rows with cohort context (e.g., "phenotype=severe, cohort_effect_size=X")?

**Per-animal nonlinear fits (1.B) questions:**
- **OPEN-Q 3:** Per-animal nonlinear fits vs per-phenotype nonlinear LMM vs both? Per-animal more flexible; per-phenotype more conservative + interpretable.
- **OPEN-Q 4:** Which fit class default (exponential / sigmoidal / piecewise / mixture)? Default by phenotype tier?
- **OPEN-Q 5:** Model selection — AIC/BIC across fit classes per animal, or pre-pick fit class per phenotype based on visual inspection?
- **OPEN-Q 6:** Confidence intervals on fit parameters via bootstrap or analytical? Bootstrap heavy for ~70 endpoints × 8 animals × nonlinear fits.

**Output + interpretation questions:**
- **OPEN-Q 7:** Output: per-animal fit parameters (CSV) + per-animal fit-curve visualizations? Per-phenotype fit-comparison figures?
- **OPEN-Q 8:** Paper narrative framing — "Phase 9 cohort + Phase 9.x per-phenotype" as parallel reporting tiers, OR "Phase 9.x per-phenotype as the primary headline; Phase 9 cohort as supplementary"?

## 9. Likely deliverables

- `src/stroke_orofacial/stats/runners.py` extensions: `phenotype_filter` parameter on existing axis runners.
- `src/stroke_orofacial/stats/recovery_fits.py` (NEW) with fit functions for nonlinear classes.
- `scripts/phase_9_x/` driver scripts for per-phenotype emit + nonlinear fit emit.
- Per-phenotype result CSVs (~3-4× expansion of Phase 9's result tree).
- Headline summary v3 with phenotype dimension.
- Per-animal + per-phenotype nonlinear fit parameter CSVs.
- Figure tier extension: per-phenotype recovery curves with linear OR nonlinear fit overlays.
- DECISIONS + MIGRATION_LOG entries.

## 10. Estimated scope

Combined per-phenotype stats + per-animal nonlinear fits:
- Per-phenotype stats extension (per-runner phenotype_filter + cohort-emit re-run + headline summary v3): ~3-5 days CC
- Per-animal nonlinear fits (recovery_fits.py + per-animal driver + visualization): ~5-7 days CC
- Combined: **~10-15 commits, ~7-10 days CC wall time** once OPEN-Qs are resolved.

Priya scientific review bandwidth is the typical bottleneck.

## 11. References

- **Phase 9 kickoff:** `docs/prompts/phase-9-stats-kickoff.md` (provides cohort-level stats Phase 9.x complements).
- **Phase 9 Addendum #5:** locks Phase 9 at cohort level; Phase 9.x is the explicit phenotype-stratified extension.
- **Phase 9 Addendum #6:** per-session-within-epoch data structure; enables per-phenotype LMM convergence even with n_animals=2.
- **Phase 9 Addendum #10:** headline summary v2 per-coefficient extraction; Phase 9.x v3 extends with phenotype dimension.
- **Phase 9.1 scoping:** `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` (empirical recovery patterns that motivate nonlinear fits + per-phenotype stats).
- **Task 6 visual gate observation:** PS54 + PS55 bimodal step-change recovery visible in `pipeline_outputs/spout_behavior/spout_behavior_figures/PS54/recovery_trajectories.first_lick_accuracy_all.svg` (rendered 2026-05-24).
- **Stroke recovery literature:** exponential decay models standard in clinical stroke; piecewise/step models more common in animal-model literature with discrete intervention timepoints.

---

## 12. Next steps

1. Phase 9 closes (cohort-level stats final).
2. Phase 9.1 closes or progresses (V4/V5 phenotype-pooled figures provide visual gate).
3. Priya reviews this scoping doc; answers OPEN-Qs 1-8.
4. Cowork drafts Phase 9.x kickoff once OPEN-Qs are resolved.
5. CC implements per kickoff: per-phenotype stats extension first (faster, simpler), per-animal nonlinear fits second.
6. Pub-figures phase consumes Phase 9.x outputs alongside Phase 9 + 9.1 deliverables.
