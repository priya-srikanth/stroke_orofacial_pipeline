# Phase 9 — Running Notes for Task 9 DECISIONS Write-Up

Seed material for the Task 9 close DECISIONS entry. Categorization (which
DECISIONS entry each item belongs in) deferred to Task 9 close — this dump
is structurally split by source (architectural-from-kickoff vs operational-
from-execution-session) but the split is loose; some items belong in both.

---

## Architectural / scope decisions (mostly from kickoff + 8 addenda)

*Best-effort reconstruction from session knowledge + kickoff state at the
time of Task 2 close. Priya may want to add items I missed.*

1. **Cohort scope locked: 8 animals (PS46-PS50 mild/moderate cohort + PS51
   moderate-severe + PS54/PS55 severe).** PS52/PS53 excluded as out-of-cohort
   per F-P-6. Phenotype distribution: {mild: 4, moderate: 1, moderate-severe:
   1, severe: 2}. Encoded in `configs/animals.yaml` per Task 1.5 stamping.

2. **Parquet schema lock: 15 columns** (11 standard + 4 spatial-specific per
   Addendum #5 (C)): `animal, date, rel_day, trial_idx, side, ipsi_contra,
   endpoint_slug, value, is_sentinel, cohort_bin_size, epoch_label,
   granularity, rel_day_anchor, n_sessions_aggregated,
   n_frames_aggregated`.

3. **Addendum #1: spatial endpoints as W2 + UOT + JS × 4 families** (tongue/
   jaw/nose/whiskers, each centered on its anatomically-appropriate
   midpoint). 12 base slugs pre-Addendum-7.

4. **Addendum #2: three temporal granularities** — `per_session`, `per_bin`,
   `per_epoch`. Later revised by Addendum #6 (see item 7).

5. **Addendum #3: W2 is the headline spatial metric.** UOT + JS retained as
   companion metrics for figures/tables but W2 drives the primary
   stroke-severity scalar.

6. **Addendum #4: latency_hist as `vector_per_session`** (1 vector per
   session, not 1 scalar per session). KS test at runtime to compare
   distributions across days/epochs/animals. New `fit_pre_post_ks_distribution
   _shape` model in Task 3 stats/models.py.

7. **Addendum #6 (revises #5): `per_epoch` is a Task 4 RUNTIME view, NOT an
   emit-time granularity.** Filter `per_session` rows by `epoch_label` at
   load time + apply additive baseline normalization. The materializer emits
   only `per_session` + `per_bin`; `per_epoch` is derived. Saves disk + keeps
   the emit invariant (one parquet per slug × animal).

8. **Addendum #6 (D): pre-stroke baseline computed via leave-one-out** —
   pre-pool histogram minus the focal pre-session's histogram, for the
   `per_session` granularity on pre-stroke dates. Avoids leakage in
   pre-vs-pre comparisons.

9. **Addendum #6 (additive normalization, NOT multiplicative):** `value -
   baseline_mean_per_animal` is the canonical baseline-correction for Task 4
   mixed-effects models. Multiplicative (ratio) normalization is a separate
   helper (`ratio_to_baseline`) but not the default for LMMs — additive
   keeps the residual on the same scale across animals.

10. **Addendum #7: 4-combo scope+trial_group expansion.** 12 spatial slugs →
    48 slugs via cross-product with `{tone_aligned_all, tone_aligned_L,
    tone_aligned_R, whole_session}`. Existing 12 slugs renamed with
    `_tone_aligned_all` suffix; 36 new slugs land via cohort emit.

11. **Addendum #8: 3 new vxy derived endpoints + `mean_first5` reducer.**
    `tongue_lick1_vxy_peak`, `tongue_max_vxy_peak_first5`,
    `tongue_mean_vxy_peak_first5` — extends per-trial reducers from
    `{first, max_first5, median}` to include `mean_first5`.

12. **UOT parameters locked to Phase 7c.2 `_compute_unbalanced_ot_plan`**
    values: `reg=0.02, reg_m=10.0, stopThr=1e-6, numItermax=500`. Spatial
    scalars in `stats/inputs/` are commensurate with the Phase 7c.2 figure
    tree at the same parameter set.

13. **Wasserstein numItermax bumped 1M → 10M** at Commit C v3 per Priya
    2026-05-23 carry-from-v2 approval to chase "numItermax reached" warnings
    on borderline-similar distributions. POT default is 100k; 10M is well
    beyond convergence-rate concerns for 80×80 histograms.

14. **Whiskers multi-bodypart aggregation = SUM-of-counts ("tip ensemble"
    interpretation).** 6 whisker bodypart histograms summed BEFORE OT
    compute, yielding 1 scalar per `(animal, granularity, anchor)`. Distinct
    from Phase 7c.2 rendering which iterates 6 bps and emits 1 panel each.

15. **Histogram resolution = 80×80 nbins** (matches Phase 7c.2 figure-tree
    rendering at `configs/defaults.yaml::dlc_spatial_tone_aligned.
    default_nbins`). Spatial scalars at this resolution are comparable to the
    Phase 7c.2 panels.

16. **EpochBoundaries dataclass + RecoveryPhenotype Literal locked** in
    `src/stroke_orofacial/animals.py` (Task 1.5). Frozen + validated. PS54
    vs PS55 boundary divergence (chronic_min=39 vs 49) preserved to guard
    Phase 9.1 phenotype-pooling consumers from assuming identical boundaries
    within tier.

---

## Operational / execution decisions (mostly from CC's session work)

1. **`lick_switch_rate` "from" → "to" semantics flip** approved at Commit A
   close; landed at `5e78807`. Matches `render_switchiness_bySession`
   color-by-destination convention. `side='L' → R→L count` (switches TO L);
   `side='R' → L→R count` (switches TO R).

2. **Per-worker centered-parquet cache attempt** (commit `77cf97c`)
   **reverted** (`b74f909`) — measured 3.3× regression in single-combo
   smoke (132s baseline → 436s with cache), 0 cache hits within combo for
   single-bp families. Cache addressed wrong layer.

3. **Per-combo progress prints preserved** (`82ae27e`) as standalone commit
   after cache revert. `_emit_one_family_for_animal` now logs `starting` +
   `done in Xs` per combo so cohort emits aren't blind for 15+ min stretches.

4. **Cache-experiment root-cause finding:** the n_jobs=4 calibration stall
   that triggered the cache work was **SMB concurrent-bandwidth contention**
   between sibling workers, NOT within-worker redundancy across combos.
   Per-worker caching can't fix concurrent contention. Future parallelization
   should target the SMB layer (local mirror, parallel readahead) not the
   per-worker dataframe layer.

5. **Stale Phase 7c.2 spatial output trees deleted via chore PR #126** —
   `spatial_tone_aligned/` (136 M), `spatial_visual_gate/` (3.4 M),
   `spatial_whole_session/` (560 K). ~140 MB reclaimed. Notebooks 11/12
   moved to `notebooks/_deprecated/` with deprecation header cells.
   PR merged 2026-05-24 at merge commit `b16188c`.

6. **`paths.py:spatial_tone_aligned_npz` + `tone_aligned.py emit_cache`
   PRESERVED as dormant** per chore PR #126. Inspection-only opt-in
   utilities; the Phase 7c.2 production driver never sets `emit_cache=True`.
   Cheap to keep; potential future use.

7. **Cohort spatial emit at n_jobs=1 serial completed in 23.9 hr** (85972 s
   total wall, 2026-05-23 to 2026-05-24). PS51-55 (severe/moderate-severe)
   drove the tail at ~2-5× the per-combo wall of PS46-50 (mild) due to
   ~3× the post-stroke session count from longer chronic-min boundaries.

8. **Commit C v1 orphan parquets annotated (Path B), not deleted**, per
   CLAUDE.md Rule 7 anti-pattern guidance (multiple destructive invocations
   within a single session). 3 PS46-tongue parquets at pre-Addendum-7 slug
   names tagged `materializer_pass=commit_c_v1_orphan_superseded_by_addendum
   _7_rename` in the aggregate manifest. ~30 KB disk cost; manifest-level
   discharge avoids compounding the day's 3-`rm -rf` count from PR #126.

9. **Aggregate manifest = 651 rows total** at Task 2 close (not 656 as
   estimated). Commit A's 256 already includes the 8 lick_switch_rate rows
   that the flip re-emit supersedes; net is 248 (Commit A non-LSR) + 8
   (Commit B latency_hist) + 384 (Commit C v3 spatial) + 8 (LSR flip) + 3
   (orphan annotations) = 651.

10. **Kickoff doc + 8 addenda land in one docs commit at Task 9 close** per
    the Phase 8a.10 `eb0cd5a` post-hoc convention. They are NOT bundled into
    source commits as they accumulate. Phase-9.1 scoping doc has a parallel
    Cowork edit queued for the same docs commit (per the parallel chore
    work for V4/V5 phenotype-pooled scope expansion).

11. **Phase-9.1 scope expanded back from "pub-polish only"** to include
    V4/V5 phenotype-pooled figures + phenotype-pooled spatial per Addendum
    #8. `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` needs
    update; Cowork may handle pre-Task-9, else CC at Task 9 docs commit.

12. **PS54 spot-check verdict (Task 2 close, Priya-approved):** 15-col
    schema correct, 51 per_session + 10 per_bin = 61 rows per spatial
    parquet, epoch counts correct for PS54 boundaries (17/39/40), pre-stroke
    at noise floor ~6e-4 (tone_aligned/all) / ~4e-4 (whole_session), acute
    elevation ~33× (tone_aligned/all) / ~12× (whole_session), clean per-bin
    recovery decay through sub_acute/chronic.

---

## Task 3 implementation deviations from kickoff/addenda spec (2026-05-24)

Each deviation is also documented in the relevant source-file docstring
(canonical for code-readers); these entries are the canonical seed for
the Task 9 DECISIONS write-up (canonical for future-Priya / future-Cowork
explaining WHY the choice was made).

1. **`fit_trial_group_friedman` 2-group case: explicit
   `status="insufficient_data"` + redirect to `fit_ipsi_contra_wilcoxon`.**
   scipy's `friedmanchisquare` requires ≥ 3 samples. For 2-group endpoints
   (e.g. `lick_switch_rate` with side ∈ {L, R}) the function returns a NaN
   FitResult tagged `reason="friedman_requires_3_or_more_groups"` rather
   than silently degrading to a paired Wilcoxon equivalent. **Auditability
   over silent fallback** — silent fallbacks make multi-comparison results
   harder to audit; the explicit redirect points callers at the right tool
   for the right test.

2. **`fit_per_epoch_lmm` 2-epoch + `apply_additive_baseline=True` =
   `SingularError`; surfaced as `status="convergence_failed"` + redirect
   to `fit_paired_pre_post_wilcoxon`.** With baseline subtraction applied
   AND only 2 epoch levels (pre + 1 post), the reference-level rows become
   exactly zero-mean per animal → random intercept variance unidentifiable
   → statsmodels MixedLM raises SingularError. Caught + surfaced as a
   NaN FitResult. **Forward-compatibility safety net** — not an active
   concern for the current 8-animal cohort which has 3+ post-epoch levels,
   but the case will arise if a future analyst splits to a 2-epoch design.
   3+ epoch case works correctly (verified by
   `test_additive_baseline_normalization_recovers_known_shift` recovering
   the known acute + chronic shifts within 0.3 absolute tolerance).

3. **`fit_per_epoch_lmm.statistic = -log10(min_p)` across non-reference
   epoch coefficients.** Kickoff + Addendum #6 didn't specify a summary
   statistic for the multi-coefficient LMM. Picked `-log10(min_p)` to
   give each FitResult a single FDR-comparable scalar interpretable as
   "strongest per-epoch effect, on a tail-visible scale". The
   unsummarized per-coefficient `{coef, se, p_value}` dict is in
   `details["per_epoch"]` for downstream consumers that want the full
   set. **Chosen for FDR-comparability across endpoints.** Alternative
   Wald chi-square omnibus available via statsmodels but adds a single
   "any difference" p-value rather than localizing to a specific epoch
   — the min-p approach inherits the "most-significant-epoch" localization
   for free. Revisitable as an Addendum if scientific framing shifts
   toward omnibus testing for the LMM tier.

---

## Task 4 implementation notes (2026-05-24)

1. **`latency_hist` parquet uses flat per-trial schema, not
   `value_vector` per-row vectors.** Addendum #4 spec said
   ``vector_per_session`` emits a per-session vector; the Phase 9
   Commit B implementation chose to emit one row per trial with a
   scalar `value` column instead (matches the rest of the parquet
   convention). The Task 4 runner bridges the gap via
   `runners._ks_on_flat_per_trial` — pools scalar `value` across
   pre/post rows + calls `scipy.stats.ks_2samp` directly. The
   `model_name` is preserved as `"pre_post_ks_distribution_shape"` so
   downstream consumers see a uniform model identifier;
   `details["schema"] = "flat_per_trial"` flags the bridge for
   audit. Documented in `runners.run_pre_post` + tested.

2. **Confirmatory granularity dispatch encoded in driver, not inventory.**
   Per Addendum #5 (E) defaults: per_session for non-spatial,
   per_bin for spatial (value_type=scalar_per_animal_time). Currently
   the driver writes BH-FDR for ALL family rows + Bonferroni for the
   confirmatory subset at EVERY granularity. A future tightening
   could restrict Bonferroni emission to the per-value-type
   confirmatory granularity only; for now the more-permissive
   "emit at every granularity, caller filters" is the simpler MVP.

3. **`trial_group` axis is largely a no-op for the current inventory.**
   Only 2 endpoints have `trial_group` in `comparison_axes_in_scope`,
   both `scalar_per_session_trial_group` value_type. After Friedman's
   ≥3-group requirement (Task 3 deviation #1), the runner skips them
   if their `side` column carries only `{L, R}`. No CSVs emitted for
   `trial_group/*`. Surfaced here as a "not used in current cohort"
   note, not a deviation.

---

## Forward pointer — Task 5 headline summary CSV (Priya 2026-05-24 directive)

At Task 5 close (cohort run finalization), CC writes
``.scratch_phase_9/task_5_headline_summary.csv`` for Priya's
intermediate spot-check BEFORE Task 6 figure work starts.

**Scope.** One row per (endpoint, axis) pair, restricted to endpoints
where EITHER `is_confirmatory=true` OR `n_permutations_override=100000`
(the "headline + priority" set per Addenda #2/#3/#8). At each
endpoint's default confirmatory granularity per value_type:

- scalar_per_session → per_session
- scalar_per_trial → per_session (mean-across-trials)
- vector_per_session → per_session (KS via Addendum #4)
- scalar_per_animal_time (spatial) → per_bin

**Columns.** endpoint_slug, category, is_confirmatory, n_permutations,
axis, granularity, effect_size (signed), effect_size_metric,
p_value, q_value_within_axis_granularity_family (BH-FDR),
bonferroni_passed (bool for confirmatory only; null otherwise),
n_animals, n_observations, ci_lower, ci_upper (bootstrap CI),
status (FitResult.status).

**Sort.** category → axis → abs(effect_size) DESC. Eyeball-friendly.

**Purpose.** ~70-100 rows for Priya to verify effect directions +
magnitudes vs expectation for headline + priority endpoints, BEFORE
Task 6/7 figure work consumes ~6-8 CC-days. Catches direction errors
or unexpected magnitudes early when re-running cohort is cheap
(~1-2 hr).

---

## Reconciliation / open

*Items needing Priya adjudication at Task 9 close.*

- (Task 3 deviation #3, `fit_per_epoch_lmm.statistic = -log10(min_p)`)
  Confirm at Task 9 close that the min-p summary statistic is the
  preferred scientific framing, OR direct switch to Wald chi-square.
  Locked default for now; revisitable.

- (Task 4 implementation note #1, `latency_hist` flat per-trial
  schema) Confirm at Task 9 close that the runner-level KS bridge is
  the preferred resolution, OR re-emit `latency_hist` with a true
  `value_vector` column. The current bridge works correctly +
  produces the expected KS p-values, but lives at the runner layer
  rather than the parquet layer.

- (Task 4 implementation note #2, Bonferroni granularity policy)
  Confirm at Task 9 close that Bonferroni-at-every-granularity is
  acceptable, OR tighten to confirmatory-granularity-only emission.
