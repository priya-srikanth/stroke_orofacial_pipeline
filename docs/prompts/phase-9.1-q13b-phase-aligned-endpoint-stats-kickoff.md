# Phase 9.1 Q-lock 13b — Phase-Aligned Tongue Endpoint Stats Kickoff

**Status:** LOCKED (Addendum #1, 2026-05-27).
**Branch:** `phase/9.1-q13b-phase-aligned-endpoint-stats`
**Merge tag (on close):** `v9.1-q13b-phase-aligned-endpoint-stats`
**Depends on:**
- Phase 7e.4 close — PR #148 Stage 5 burn IN FLIGHT (~2 hr ETA from launch); Q-lock 13b unblocks the moment 7e.4 lands on `main`.
- Q-lock 8 close — supplies phenotype-pooled aggregator pattern (status check during Stage 0).

---

## Summary

Q-lock 13b delivers phenotype-pooled per-trial **stats + figures** for three scalar tongue endpoints derived from phase-aligned trajectories of the first lick. Sits beside Q-lock 13 (mean+SEM trajectory rendering — separate ticket) and adds the scalar-stat layer Priya wants for cross-phenotype + cross-epoch comparisons.

---

## Endpoints

| ID | Endpoint | Definition | Status |
|---|---|---|---|
| A | `peak_angle_deg` | Tongue angle at `phase = 0.5` (lick-1 peak time) | **EXISTS** — `dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet` |
| B | `max_abs_angle_phase_0_075_deg` | `max(abs(angle_deg))` over `phase ∈ [0, 0.75]` | **NEW** — emit alongside existing per-trial features |
| C | `max_abs_x_phase_0_075_px` | `max(abs(x_centered))` over `phase ∈ [0, 0.75]` | **NEW** — `center_mode` + signed-vs-unsigned per Q6 below |

**Phase definition:** `phase = (t − (peak_t − ILI/2)) / ILI` ∈ [0, 1], so `phase = 0.5` = lick-1 peak time, `phase ∈ [0, 0.75]` = ascent + peak + ~half the descent.

---

## Scope IN

- New per-trial endpoint emitter for **B + C** — lands as new columns on the existing per-trial tongue features parquet **OR** as a sibling parquet (see **Q2**).
- Per-session aggregator: `median ± IQR ± n` per (animal, date, side, endpoint).
- Phenotype-pooled aggregator per (phenotype × epoch × side × endpoint), reusing the Q-lock 8 phenotype-aggregator pattern.
  - Phenotype map (per F-P-1): **mild** = PS47/48/49/50 · **moderate** = PS46 · **mod-severe** = PS51 · **severe** = PS54/55.
  - Epochs: existing `rel_day_bin` labels.
- Stats comparison:
  - Pre vs post per phenotype.
  - Cross-phenotype within epoch.
  - Test = **Q3**.
- Figures per Q-lock 15 marker convention:
  - **Directory:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_cleaned_trace/phase_aligned_endpoints/`
  - **Filename:** `<endpoint>_<side>_cleaned_trace.svg`
  - **Footer (figure subtitle):** `Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)`
  - **Count:** 3 endpoints × 2 sides = **6 figures**.

---

## Scope OUT

- Q-lock 13 mean+SEM trajectory rendering — separate ticket; this is endpoint stats only.
- Multi-lick variants (`first_2_licks`, `all_licks`) — start with `first_lick` only.
- Jaw or other bodyparts — tongue only in Q-lock 13b.

---

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Phase 7e.4 close (PR #148 Stage 5 burn) | IN FLIGHT (~2 hr ETA from launch) | Phase 7e.4 CC |
| Q-lock 8 close (phenotype-pooled aggregator pattern available) | Verify in Stage 0 | Cowork |
| Phase-extraction substrate `tongue_pertrial.build_first_lick_centered_phase_rows()` | EXISTS — reuse, no new extraction code | — |

---

## Q-locks for Priya

> **Cowork records Priya's answers as Addendum #1, "ALL OTHER LOCKS UNCHANGED" footer per `[[feedback-iterative-addenda-pattern]]`.**

### Q1 — ILI source for phase normalization
- (a) `synthetic_only` — production default per Phase 7a.4 Addendum #15
- (b) `hybrid` — real ILI when available, synthetic fallback
- (c) `real_only`

**Default proposal:** (a). Defection to (b)/(c) requires Cowork to surface impact on (animal, date) cells where real ILI is missing or sparse.

### Q2 — Endpoint B + C storage
- (a) Extend the existing per-trial tongue parquet schema with 2 new columns
- (b) Sibling parquet at a new resolver path (e.g. `resolver.tongue_per_trial_phase_endpoints_parquet(...)`)

**Default proposal:** (a). Keeps the per-trial tongue schema as one row-per-trial unit; avoids a 1:1 join in every downstream consumer.

### Q3 — Stats test
- (a) Paired t-test (parametric, normality assumed)
- (b) Wilcoxon signed-rank, paired (non-parametric, robust to outliers)
- (c) Mixed-effects model (random intercept per animal, fixed effects per epoch × phenotype)

**Default proposal:** (b). Non-parametric, robust to per-trial outliers, no normality assumption. (c) is the long-term right answer for proper cross-animal pooling but adds complexity Q-lock 13b doesn't yet need; can be the upgrade in a future ticket.

### Q4 — Side handling
- (a) Split L/R as separate figures (matches Q-lock 10 convention)
- (b) Pool L+R

**Default proposal:** (a). Q-lock 10's V4/V5 split-by-side convention is the project-wide precedent for laterality-aware endpoints.

### Q5 — Multiple-comparisons correction
Test count: 3 endpoints × 2 sides × 4 phenotype-pairs = **24 tests**.
- (a) Bonferroni (conservative)
- (b) Benjamini-Hochberg FDR
- (c) None — mark raw p, no correction

**Default proposal:** (b) BH-FDR. Exploratory phenotype-pooled analysis at N=24; Bonferroni is overconservative, BH-FDR is the standard for this analysis-size class.

### Q6 — Endpoint C `x` convention
- (a) Signed `x_centered` (preserves laterality direction)
- (b) `abs(x_centered)` (collapses direction, pure magnitude)
- (c) BOTH — emit `max_abs_x_phase_0_075_px` AND `signed_extremum_x_phase_0_075_px` so downstream stats pick

**Default proposal:** (c). Small extra column cost, preserves both interpretations for stats + future figures.

### Q7 — Cohort scope
- (a) Tongue + jaw families (matches Phase 7e.4 cohort)
- (b) Tongue-only

**Default proposal:** (b). Q-lock 13b is tongue-only by definition — jaw has no phase-aligned trajectory convention yet.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | Cowork | Confirm Phase 7e.4 merged + tagged; confirm Q-lock 8 aggregator pattern available; verify `build_first_lick_centered_phase_rows()` reachable |
| 1 | Per-trial endpoint B + C emitter (extends `tongue_pertrial`) | CC | Reuses `build_first_lick_centered_phase_rows()` substrate; per Q1 (ILI source) + Q2 (storage location) |
| 2 | Per-session aggregator (`median ± IQR ± n` per animal × date × side × endpoint) | CC | Helper in `stroke_orofacial/stats/aggregators.py` (or wherever Q-lock 8 landed equivalent) |
| 3 | Phenotype-pooled aggregator | CC | Reuse Q-lock 8 pattern; phenotype map per F-P-1 |
| 4 | Stats compute + figure renderer | CC | Per Q3 (test) + Q5 (correction) + Q4 (side handling) + Q-lock 15 marker convention |
| 5 | Cohort emit on the 8-animal cohort | CC | 6 figures total; phenotype-pooled CSVs alongside; per-write `overwrite="prompt"` per GR7 |
| 6 | Phase close + merge tag `v9.1-q13b-phase-aligned-endpoint-stats` | Cowork | Standard tag-on-merge pattern per CLAUDE.md GR8 |

---

## Pre-work (this kickoff)

This kickoff is a **DRAFT**. Workflow:

1. **Cowork** opens a draft PR with this doc only.
2. **STOP** for Priya inputs on Q1–Q7.
3. Once Q1–Q7 are locked → Cowork records as **Addendum #1** (focused, "ALL OTHER LOCKS UNCHANGED" footer per `[[feedback-iterative-addenda-pattern]]`).
4. Cowork drafts the CC kickoff prompt + opens the Phase 9.1 Q-lock 13b implementation branch.

---

## Forward-pointers

- **Q-lock 13** (mean+SEM trajectory rendering) — separate ticket; Q-lock 13b consumes the same phase-aligned substrate but produces scalar-stat outputs instead of trajectory plots.
- **Q-lock 13b multi-lick variants** (`first_2_licks`, `all_licks`) — separate ticket after first-lick variant lands.
- **Jaw phase-aligned endpoint analog** — separate ticket once jaw phase-trajectory convention is defined; gated on jaw phase-extraction substrate not yet built.

---

## References

- **Phase 7a.4 Addendum #15** — ILI `synthetic_only` production lock (relevant to Q1).
- **Q-lock 8** — phenotype-pooled aggregator pattern (Stage 3 reuse target).
- **Q-lock 10** — V4/V5 split-by-side convention (Q4 precedent).
- **Q-lock 15** — `cleaned_trace` three-layer marker convention (directory + filename + footer).
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe).
- **Phase 7e.4** — production wiring fix for v7 cleaned-trace consumption (upstream gate).
- **`tongue_pertrial.build_first_lick_centered_phase_rows()`** — phase-extraction substrate (Stage 1 reuse target).

---

## Addendum #1 — Q1–Q7 locked (2026-05-27)

**Status flip:** DRAFT → LOCKED. All seven Q-lock answers below. **ALL OTHER LOCKS UNCHANGED.**

### Q1 — ILI source for phase normalization

**LOCKED:** `synthetic_only` (option a, the default proposal).

Verified by inspection of `tongue_pertrial.build_first_lick_centered_phase_rows()` (signature at `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:404`): the phase-extraction substrate already defaults to `synthetic_only` per Phase 7a.4 Addendum #15 — Mode 3 won the 3-way PS46/PS50/PS55 visual gate. Q-lock 13b inherits this without change.

Concrete meaning for endpoints A/B/C: per-trial phase axis uses `synthetic_ili_ms = bundle.metadata["pre_stroke_median_ili_ms"]` (the animal's own pre-stroke baseline median ILI). Same cycle width for every trial of a given animal across every session, so the phase axis is mechanically comparable across trials and the remaining variance in binned angle/x traces is biological shape variation, not a cadence-mixing confound.

### Q2 — Endpoint B + C storage

**LOCKED:** (a) Extend the existing per-trial tongue features parquet schema with new columns. Matches the style of other Phase 9 per-trial endpoints — keeps row-per-trial unit, no 1:1 join in downstream consumers.

### Q3 — Stats test

**LOCKED:** (b) Wilcoxon signed-rank, paired.

Q3 (test) and Q5 (multiple-comparisons correction) are orthogonal. The project already pairs Wilcoxon with BH-FDR in production: `fit_paired_pre_post_wilcoxon` in `src/stroke_orofacial/stats/models.py` is exactly the analogous Phase 9 pre/post per-animal test, and it bundles with BH-FDR via `multiple_comparisons.py`. Q-lock 13b uses the same combo for consistency.

Upgrade path documented but not adopted here: mixed-effects (option c) is the long-term right answer for proper cross-animal pooling that accounts for per-animal trial-count imbalance. The existing `fit_recovery_mixedlm` is the precedent for that pattern. Q-lock 13b defers it — Wilcoxon is the minimum-complexity test that matches existing Phase 9 conventions for the pre-vs-post comparison.

### Q4 — Side handling

**LOCKED:** (a) split L/R as separate figures. Matches Q-lock 10 V4/V5 convention.

### Q5 — Multiple-comparisons correction

**LOCKED:** (b) Benjamini-Hochberg FDR. Matches project default (`bh_fdr` in `src/stroke_orofacial/stats/multiple_comparisons.py`).

FDR family for Q-lock 13b: 3 endpoints × 2 sides × 4 phenotype-pairs = 24 tests. Applied as one BH-FDR family per the standard project convention. If downstream review wants a different family slicing (e.g. per-side FDR-family), surface as a future addendum.

### Q6 — Endpoint C `x` convention (REFINED from kickoff proposal)

**LOCKED:** Single endpoint, **signed value at the argmax of the absolute value.**

Endpoint C definition (replaces the kickoff's `max_abs_x_phase_0_075_px`):
signed_x_at_max_abs_phase_0_075_px =
x_centered[ argmax_t( | x_centered(t) | )  for t ∈ phase[0, 0.75] ]

Per-trial semantic: scan the phase window `[0, 0.75]`, find the time-point with the largest absolute `x_centered`, then report the **signed** `x_centered` value at that time-point. Selection criterion uses magnitude (catches the most-extreme excursion regardless of direction); reported/plotted value is signed (preserves laterality direction in figures and downstream stats).

Updated endpoint table (supersedes the kickoff doc's Endpoints section):

| ID | Endpoint | Definition |
|---|---|---|
| A | `peak_angle_deg` | Tongue angle at `phase = 0.5` (lick-1 peak time) |
| B | `max_abs_angle_phase_0_075_deg` | `max(abs(angle_deg))` over `phase ∈ [0, 0.75]` |
| C | `signed_x_at_max_abs_phase_0_075_px` | `x_centered[argmax(|x_centered|)]` over `phase ∈ [0, 0.75]` |

Figure count unchanged: 3 endpoints × 2 sides = **6 figures**.

### Q7 — Cohort scope

**LOCKED:** (b) Tongue-only. Jaw has no phase-aligned trajectory convention yet; queued as the forward-pointer already stated in the kickoff.

---

### Stage 0 prereq verification — updated

Cowork's Stage 0 pre-implementation check now includes:

1. `build_first_lick_centered_phase_rows()` still defaults to `ili_source="synthetic_only"` (regression check).
2. `fit_paired_pre_post_wilcoxon` is reachable from `stroke_orofacial.stats.models`.
3. `benjamini_hochberg_fdr` (or `correct_pvalues(..., method="bh_fdr")`) is reachable from `stroke_orofacial.stats.multiple_comparisons`.
4. Q-lock 8 phenotype-pooled aggregator pattern is reachable and documented (status confirmed independently before Stage 3 implementation).

### Unblock signal

Q-lock 13b is ready for CC kickoff-prompt drafting (Stages 1–6) the moment Phase 7e.4 lands on `main`. Cowork drafts the CC prompt after PR #148 merges + `v7e.4-…` tag is pushed.

---

## Addendum #2 — Stage 0 divergence resolutions (2026-05-27)

**Status:** LOCKED. Implementation-time corrections to four Addendum-#1 / kickoff-body items that CC surfaced during Stage 0 read-through. **ALL OTHER LOCKS UNCHANGED.**

### D1 — Per-trial storage (corrects Addendum #1 Q2 wording)

**LOCKED:** Endpoints A + B + C all land in the existing per-trial tongue endpoints JSON at `dlc_kinematics/per_trial/tongue/<animal>/<date>.json`, under a new top-level block `tongue.phase_aligned_endpoints` (alongside the existing `tongue.cell50_own_bout_scalars`).

**Background.** Addendum #1 Q2 LOCKED option (a) as "Extend the existing per-trial tongue features parquet schema with new columns." The kickoff body's Endpoints table claimed endpoint A `peak_angle_deg` lives at `dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet`. Stage 0 verification revealed:

- The actual per-frame parquet schema is `{frame_idx, angle_deg_smoothed}` only — no `peak_angle_deg`.
- `peak_angle_deg` lives per-LICK at `dlc_kinematics/lick_events/tongue/<animal>/<date>.parquet`, NOT per-trial.
- The canonical per-trial tongue artifact is `dlc_kinematics/per_trial/tongue/<animal>/<date>.json` (JSON, not parquet) — see `tongue_pertrial_endpoints_json` in `paths.py`, `tongue.cell50_own_bout_scalars` block in `tongue_pertrial.py`.
- No per-trial tongue parquet exists.

The spirit of Q2(a) ("extend existing per-trial artifact; no sibling") is satisfied by the JSON-extension pattern. Q2(b) (sibling parquet) is rejected as originally intended.

**Endpoint A re-emit.** The kickoff erroneously treated endpoint A as already-emitted at per-trial grain. It is not — `peak_angle_deg` is per-lick. Stage 1 re-emits A into the same `tongue.phase_aligned_endpoints` JSON block as B + C, all computed from the same `build_first_lick_centered_phase_rows()` substrate. Downstream aggregator consumes one per-trial block carrying all three endpoints.

**Schema of the new `tongue.phase_aligned_endpoints` block.** Three parallel lists, indexed by trial × side (same shape as `cell50_own_bout_scalars`):

- `peak_angle_deg`: tongue angle at `phase = 0.5` (lick-1 peak time).
- `max_abs_angle_phase_0_075_deg`: `max(abs(angle_deg))` over `phase ∈ [0, 0.75]`.
- `signed_x_at_max_abs_phase_0_075_px`: `x_centered[argmax(|x_centered|)]` over `phase ∈ [0, 0.75]` (selection by magnitude, reported value signed).

### D2 — Substrate extension for `x_centered`

**LOCKED:** Thread `x_snip` through the centered-phase substrate; emit `x_centered` column equal to raw `x_snip` (NO additional subtraction).

CC's proposed approach (a) + (b) is adopted:

- (a) Add `"x_snip": x_snip.copy()` to the `trial_row` dict in `_build_visual_bundle_per_trial` so `df_trials` exposes per-trial x arrays. In-memory bundle field only; no on-disk schema change.
- (b) Extend `_centered_phase_rows_from_peaks` + `_trial_arrays` + `build_first_lick_centered_phase_rows` to thread `x_snip` through and emit an `x_centered` column on the returned phase-rows DataFrame.

CC's proposed (c) (subtract `eye_in_spout_frame_x`) is **REJECTED**. Reason: `x_snip` is read from `dlc_centered_spout_midpoint_parquet` via `_load_consolidated_eye_landmarks` (`tongue_pertrial.py:1608`-`1624`), and the per-frame angle metadata at `tongue_pertrial.py:3452` confirms `"center_mode": "centered_spout_midpoint"`. The x values are already in spout-midpoint frame (x = 0 ↔ tongue aligned with spout midline) — which IS the project's canonical centered coordinate for tongue laterality.

Subtracting `eye_in_spout_frame_x` would conflate eye position offset with tongue laterality and break the science question ("how far laterally did the tongue go relative to the lick target"). The column name `x_centered` in this context refers to its spout-midpoint origin, not an eye-relative re-centering.

### D3 — Epoch axis + test count (corrects kickoff Stage 3 + Q5 wording)

**LOCKED:** Epoch axis is `epoch_label ∈ {pre, acute, sub_acute, chronic}` (assigned by `stroke_orofacial.stats.recovery_epochs.assign_epoch_label`), NOT `rel_day_bin`. Wilcoxon scope is pre-vs-each-post-epoch per phenotype × endpoint × side.

**Test-count arithmetic.** The kickoff's "3 endpoints × 2 sides × 4 phenotype-pairs = 24 tests" reflected under-specified "4 phenotype-pairs" wording. The actual test grid:

`3 endpoints × 2 sides × 4 phenotypes × 3 post_epochs = 72 tests`

— one BH-FDR family, NaN-aware. The `correct_pvalues(..., method="bh_fdr")` wrapper (`apply_correction_to_results_df` in `stats/multiple_comparisons.py`) excludes NaN p-values from the rank-based adjustment and reinserts them as NaN, so n=1 phenotypes participating in the family is safe.

**Aggregator flip.** `fit_paired_pre_post_wilcoxon(..., aggregator="median")` matches Q-lock 13b's median+IQR aggregation convention. The function already exposes the `median` choice — no signature change needed.

**Cross-phenotype within-epoch comparison dropped from this ticket.** Cross-phenotype is unpaired (different animals across phenotypes); paired Wilcoxon is the wrong test class. Deferred to a future ticket — candidate tests are Mann-Whitney U (per-side per-epoch) or a mixed-effects model with phenotype as a fixed effect. Documented as forward-pointer below.

**Known limitations (carry into the manifest / stats CSV).**

- `moderate` (PS46, n=1) and `moderate-severe` (PS51, n=1) phenotypes will every Wilcoxon they participate in return `status="insufficient_data"` + NaN p-value — paired Wilcoxon requires n ≥ 2 paired animals. The NaN-aware BH-FDR correction handles these correctly. Included in the FDR family anyway so results-table provenance is uniform.

### D4 — Aggregator helper module location

**LOCKED:** Stage 2 + Stage 3 helpers (median+IQR per-session + phenotype-pooled median+IQR) land at `src/stroke_orofacial/stats/aggregators.py` (new module).

The Q-lock 8 analog at `src/stroke_orofacial/figures/_io.py` is figure-private and mean-based. Q-lock 13b's helpers are stats-grain (consumed by `fit_paired_pre_post_wilcoxon`) and median-based — fresh module is the right structural call. Patterns reused from `figures/_io.py` (load_cohort_animals semantics, phenotype_map shape) are reimplemented in `stats/aggregators.py` (or imported from `stats/recovery_epochs.cohort_phenotype_summary` + `animals.load_animals` where they already live in stats-grain).

### Forward-pointers added by Addendum #2

- **Q-lock 13b cross-phenotype within-epoch test.** Unpaired test for cross-phenotype comparisons (Mann-Whitney U per-side per-epoch, or mixed-effects with phenotype fixed effect). Out of Q-lock 13b scope; future ticket.

### Stage 0 prereq verification — Addendum #2 outcome

Stage 0 verification ran 2026-05-27 and resolved all four divergences in this addendum. CC proceeds directly to Stage 1 implementation under the locks in Addenda #1 + #2.


