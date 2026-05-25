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
   to `fit_paired_pre_post_wilcoxon`.**
   **VESTIGIAL under Addendum #9 (Priya 2026-05-24) — no longer reachable
   from cohort data; preserved as safety net.** Addendum #9 (B) flipped
   `apply_additive_baseline` default to `False` for all endpoint types
   (was True for non-spatial under Addendum #6 D). The Task 5 cohort
   emit uses the False default, so the singular-matrix path no longer
   fires on the 2-epoch case. Path kept in source as a forward-compat
   safety net for genuinely-degenerate inputs (single-observation-per-
   animal etc.) but the redirect-to-Wilcoxon advice is no longer needed
   for the current cohort. Test `test_per_epoch_lmm_2epoch_no_singular
   _matrix_raw` (Addendum #9 F) verifies the 2-epoch case now produces
   an identifiable LMM on raw values.

3. **`fit_per_epoch_lmm.statistic = -log10(min_p)` across non-reference
   epoch coefficients.**
   **VESTIGIAL under Addendum #10 (Priya 2026-05-25).** Headline summary
   v2 surfaces each pre-vs-each-post-epoch comparison as a separate
   row (`comparison ∈ {pre_vs_acute, pre_vs_sub_acute, pre_vs_chronic}`)
   with `details["per_epoch"][epoch]["coef"]` as the effect size and
   `["p_value"]` as the raw p-value — per-coefficient extraction, not
   a collapsed min-p summary. The min-p still lives in
   `FitResult.statistic` of `fit_per_epoch_lmm` for code-readers; the
   headline summary v2 + Phase 9.1 V5 boxplot renderers read the
   per-epoch dict, not statistic. Min-p remains as a forward-compat
   scalar for any caller that wants a single "strongest effect"
   summary without iterating the dict. Locked default; no further
   revisit planned.

---

## Task 5 close fixup — Addendum #8 vxy endpoint materialization (2026-05-25)

The 3 Addendum #8 derived endpoints (`tongue_lick1_vxy_peak`,
`tongue_max_vxy_peak_first5`, `tongue_mean_vxy_peak_first5`) were
added AFTER Task 2 Commit A's cohort materialization, so only PS46
(from Commit C smoke) had parquets on disk through Task 5 close.
Headline summary CSV rows for those endpoints showed `insufficient_data`
status across all 3 axes.

**Fixup (parallel to Task 6 start):** re-ran `materialize_inputs.py
--endpoints tongue_lick1_vxy_peak tongue_max_vxy_peak_first5
tongue_mean_vxy_peak_first5 --animals PS47-PS55` to emit the 21 missing
parquets (3 endpoints × 7 animals = 21). Verified 8/8 animals per
endpoint on disk post-emit. Re-ran the full axis sweep + headline
summary; the 9 vxy rows (3 endpoints × 3 axes-in-scope) now show
`status="ok"` with computed effect sizes + bootstrap CIs.

Cohort totals unchanged (105 headline rows; 14 Bonferroni passes) —
none of the 3 vxy endpoints are `is_confirmatory=true` but all 3 are
`n_permutations_override=100000` priority. Their `recovery` axis
fits produced p_value=0 (very strong slope) but with the standard
Wilcoxon p_value reported as 0 (not NaN — visible in summary CSV).

---

## Task 6 implementation notes (2026-05-25)

1. **`plot_recovery_trajectories_with_fit` adds `cohort_points` kwarg** for
   per-mouse visual-gate panels. The new function takes `points` (driving
   scatter + animal-mean line) and an optional `cohort_points` (driving
   the bootstrap CI ribbon). Per-mouse panels pass cohort-wide points
   for the ribbon while displaying only the focal animal's points; cohort
   plots pass `points` alone (and the wrapper uses them for both).
   Bootstrap requires ≥3 animals to be informative — single-animal
   `points` would otherwise produce a degenerate ribbon.

2. **CI ribbon clipped to per-animal x-range.** The cohort bootstrap
   spans all cohort post-stroke days (e.g. PS54/PS55 extend to ~70 days
   post); per-mouse panels for PS46-50 (mild, ~14 days post) would
   otherwise show a meaningless extrapolated ribbon. The renderer
   clips the ribbon to the per-animal `points` x-range while keeping
   the LMM fit line at the same range.

3. **`_parse_recovery_fit_details` handles `nan` literals.** statsmodels
   serializes degenerate AIC/SE values as bare `nan` in the str(dict)
   repr stored in `_all.csv` `details` column. `ast.literal_eval`
   rejects `nan`/`inf` literals; the parser substitutes them with
   `None` before parsing. Same fix mirrored in
   `build_task_5_headline_summary.py`. Documented in both modules.

4. **`render_recovery_trajectories` per-mouse pattern.** Loads cohort-
   wide parquets from `stats/inputs/<slug>/*.parquet` to build
   cohort_points for the ribbon (~50-200 points/animal × 8 animals);
   reads the cohort recovery LMM result CSV at
   `stats/results/recovery/per_session/<slug>.csv` for slope +
   intercept. Output path:
   `spout_behavior_figures/<animal>/recovery_trajectories.<slug>.{svg,png}`
   — endpoint slug embedded in the filename so multiple endpoints
   coexist per animal.

5. **Phase 8a.10 forward-pointer discharge.** Phase 8a.10's kickoff
   listed `recovery_trajectories` as a forward-pointer plot family
   that needed Phase 9 stats fits before it could land. Task 6
   discharges that pointer. The `DECISIONS.md` entry happens at Task 9
   close per Phase 8a.10 `eb0cd5a` post-hoc convention; the discharge
   is logged here as a forward-pointer-close pre-cursor.

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
   per_bin for spatial (value_type=scalar_per_animal_time).
   **RESOLVED under Addendum #10 (Priya 2026-05-25).** Headline
   summary v2 now applies BH-FDR within `(axis, comparison)` family
   at the confirmatory granularity per value_type — not at every
   granularity. The per-axis result CSVs (`run_stats_axis.py` output)
   still emit at every granularity (no change there); the headline
   summary builder is the layer that picks the canonical granularity
   per value_type. The original v1 "Bonferroni-at-every-granularity"
   behavior was dropped from v2; the original v1 file was overwritten
   in place per Addendum #10 (E) (no downstream consumers depended
   on v1).

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

## Forward pointers for future phases

- **Phase 9.x-nonlinear-recovery-fit** (scoping doc at
  [docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md](../docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md))
  — captures the Task 6 finding that the cohort linear LMM doesn't
  fit severe-phenotype bimodal recovery (PS54/PS55 step-change at
  sub_acute→chronic boundary).
  **SCOPE EXPANDED 2026-05-25 (Priya).** Combined per-phenotype stats
  (all 4 axes, 3-tier grouping per Priya: mild n=4 /
  moderate-pool n=2 [PS46 + PS51 pooled] / severe n=2) + per-animal
  nonlinear recovery fits. ~10-15 days CC. Phase 9 stays cohort-only
  at close; Phase 9.x is the per-phenotype layer. At Task 9 close,
  the scoping doc lands alongside the kickoff-addenda commit (per
  Phase 8a.10 `eb0cd5a` post-hoc convention; same docs commit as
  the Phase 9 addenda).

---

## Task 7 implementation notes (2026-05-25)

1. **V1/V2/V3 design per Addendum #8 + Addendum #10 q-value plumbing.**
   `src/stroke_orofacial/stats/figures.py` (+~580 LOC) implements
   `plot_v1_per_session_recovery` (scatter + cohort LMM fit + bootstrap
   CI ribbon via Task 6's `plot_recovery_trajectories_with_fit`),
   `plot_v2_per_bin_recovery` (per-side L/R lines + cohort mean/SEM),
   and `plot_v3_per_epoch_boxplot` (side-by-side L/R boxes per epoch
   with `q_within_endpoint_holm`-driven asterisk annotations: `***`
   for q<0.001, `**` <0.01, `*` <0.05, `ns` otherwise).

2. **Forest plot scale limitation.** Forest plots for axes with
   per-coefficient comparisons (recovery pre_vs_*) span ~5 orders of
   magnitude in effect size — tongue_lick1_t_peak_ms (+195 ms shift)
   crowds out spatial Wasserstein deltas at ~0.001. The metric-split
   subplot (one panel per `effect_size_metric`) doesn't help because
   all per_epoch_lmm rows share metric=`epoch_coef`. Acceptable for
   the headline-finding visualization (top entries are visible); a
   log-or-normalized forest plot is a Phase 9.1 figure-tier polish
   concern. Documented limitation, not a runner bug.

3. **3 confirmatory endpoints fully recover by chronic** (bonferroni_passed=False
   for pre_vs_chronic):
   - `first_lick_accuracy_all` (q_holm=0.88, coef=+0.004) — strong
     recovery to baseline
   - `tongue_median_vxy_peak_per_trial` (q_holm=0.67, coef=+14.5) —
     velocity returns to baseline range
   - `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
     (q_holm=0.0505, coef=+0.0014) — **borderline**; just barely NS
     at α=0.05. Worth flagging as "marginally recovered" in the
     paper narrative.
   The remaining 12 confirmatory endpoints have persistent chronic
   deficits — tongue kinematics dominate (lick1/lick2 angle, x_at_ypeak,
   t_peak_ms all show q_holm < 10⁻⁸⁰).

4. **tongue_lick1_y_peak sign-flip across epochs is uniform across
   animals** per V3 boxplot inspection. acute coef=+21.79 → sub_acute
   −12.16 → chronic −6.45. Pre baseline ~120 ms; acute jumps to
   ~140-150 (both L + R); sub_acute drops to ~100 (below pre);
   chronic stays at ~100-115 (still below pre). Bimodal trajectory
   visible in V2 per_bin (cohort-overlay). All 8 animals show the
   same pattern qualitatively. Featured in Task 8 verdict per Cowork
   directive.

5. **Output tree summary (76 figures × 2 formats = 152 files):**
   - `pipeline_outputs/stats/figures/headlines/<endpoint>/` —
     21 figures (7 headlines × V1/V2/V3)
   - `pipeline_outputs/stats/figures/per_animal/<endpoint>/` —
     48 figures (16 confirmatory × {recovery_curve,
     paired_diff_pre_post, paired_diff_ipsi_contra})
   - `pipeline_outputs/stats/figures/forest_plots/` —
     7 figures (one per (axis, comparison) family with confirmatory rows)

---

## Reconciliation / open

*Items needing Priya adjudication at Task 9 close.*

- ~~(Task 3 deviation #3, `fit_per_epoch_lmm.statistic = -log10(min_p)`)~~
  **RESOLVED under Addendum #10** — headline summary v2 reads
  per-coefficient details rather than the min-p summary scalar.
  Min-p stays in FitResult.statistic as a forward-compat scalar.
  Flagged VESTIGIAL above.

- (Task 4 implementation note #1, `latency_hist` flat per-trial
  schema) Confirm at Task 9 close that the runner-level KS bridge is
  the preferred resolution, OR re-emit `latency_hist` with a true
  `value_vector` column. The current bridge works correctly +
  produces the expected KS p-values, but lives at the runner layer
  rather than the parquet layer.

- ~~(Task 4 implementation note #2, Bonferroni granularity policy)~~
  **RESOLVED under Addendum #10** — headline summary v2 applies
  BH-FDR within `(axis, comparison)` at the confirmatory granularity
  per value_type. Per-axis result CSVs unchanged.

- (Addendum #9, 2026-05-24) Adopted: `fit_per_epoch_lmm` runs on
  RAW values; LMM random intercept absorbs between-animal baseline
  shifts. Plot-time additive normalization deferred to Task 7
  figure render code per Addendum #9 (D). Task 3 deviation #2
  flagged VESTIGIAL above.

- (Addendum #10, 2026-05-25) Adopted: headline summary v2 surfaces
  per-coefficient pre-vs-each-epoch comparisons as separate rows;
  Bonferroni-Holm sequential correction within each endpoint's 3
  comparisons; cross-endpoint BH-FDR within (axis, comparison)
  family. Builder script: `scripts/phase_9_stats/
  build_task_5_headline_summary.py`. Verified row count = 306
  (vs Addendum #10 estimate 180-220; my count is higher because
  the inventory has more endpoints with all 4 axes-in-scope than
  the estimate accounted for — math: 71 endpoints × (1.5 non-
  recovery axes + 4 recovery rows) ≈ 320 expected).
