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

## Reconciliation / open

*Items needing Priya adjudication at Task 9 close. Currently empty — no
adjudication-required residuals from Task 2 close. Will accumulate during
Task 3-8 implementation work.*

(none at Task 2 close)
