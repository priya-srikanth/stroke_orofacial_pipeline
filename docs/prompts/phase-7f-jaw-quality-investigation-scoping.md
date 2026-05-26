# Phase 7f — Jaw DLC quality investigation (scoping doc)

> **Status:** DRAFT — investigation-only audit. No production code or data
> touched. Final scope decision pending Priya review of the verdict.
>
> **Branch:** `investigation/jaw-quality-audit` (off `main` at 2026-05-26).
> Parallel to and independent of Event B
> (`chore/phase-7e-cohort-reemit`, PR #135).
>
> **Initial verdict (SUPERSEDED by 2026-05-26 amendment below):**
> `light-cleanup` scoped to `jaw_pertrial.py` only. Kept for context;
> see Addendum #1 immediately below for the revised verdict.

> **AMENDMENT 2026-05-26 (Priya visual review of renders).** Priya
> reviewed two renders and corrected my initial framing — the artifact
> mechanism is **broader than single-frame outliers**:
>
> - **PS54 / 2025-05-01 / t013 R** (peak 138 px, lk=0.72): the period
>   from ~0 to ~1200 ms contains multiple **clusters** of high-y raw
>   DLC (reaching 100-150 px) interleaved with wide Stage-5 baseline-
>   fill bands (red). Likelihood during those clusters is mostly < 0.5.
>   Real continuous jaw tracking starts only at ~1300 ms. **This IS the
>   structural analog of tongue v7's PCHIP-anchored-spike-against-
>   Stage-5-zeros pattern.**
> - **PS54 / 2025-05-06 / t095 L** (peak 125 px, lk=0.66): single-frame
>   outlier on otherwise-resting trace — the simpler case I had
>   documented in §4.
>
> **Three new rules to scope into Phase 7f** (revises §5 + §6):
>
> 1. **Hard physical-ceiling rule:** jaw `y_final ≤ ~75 px` above
>    baseline is a reasonable physiological maximum. Anything above is
>    artifact. Threshold needs calibration on the audit cohort — TBD as
>    part of Phase 7f Task 1.
> 2. **Within-trial outlier rules analogous to tongue v7:** port the
>    cluster classifier (Rule A intra-cluster shape + Rule B non-base
>    neighbor + isolated-short override, per Phase 7e Decisions 9, 11)
>    AND the frame-level outlier wipe (Decision 12) AND PCHIP-extend
>    wipe (Decision 13). Constants need jaw-specific calibration.
> 3. **Interpolation gap-filling tuning may be needed.** Jaw's
>    `max_gap_ms = 120` (vs. tongue's 56) is more lenient — allowing
>    PCHIP to bridge larger gaps that may anchor artifact clusters.
>
> **Revised verdict:** between `light-cleanup-plus` (Option A: all
> logic inside `jaw_pertrial.py`, no v5p3 re-emit, ~3-5 days CC) and
> `bodypart-parametric v7 port` (Option B: full v5p3 integration with
> jaw-specific constants + cohort v5p3 re-emit, ~2-3 weeks CC).
> Architecture picked at kickoff. The audit confirms the cleanup is
> needed; the architecture choice is the open scoping question, not
> whether to do it.
>
> **Cohort-level context (unchanged):** jaw v5p3 is cleaner than tongue
> cohort-wide (87-99% detection rate vs. tongue's 10-21%; baseline-fill
> at peaks ≤ 2.4% in any cell). Dominant biological signal
> (severe-acute / mod-sev-acute collapse to ~11 px) is robust to
> lk-gate choice (cell ranking preserved). The per-trial extreme tail
> is where the cluster + frame artifacts hide — cohort means understate
> the contamination.

> **AMENDMENT 2026-05-26 #3 (interpolation audit findings).** Scoping
> audit #2 (jaw v5p3 interpolation quality, 1.9 M gap records across
> 8-animal × 2-bodypart cohort, full results §3.7) produced a
> **surprising finding that revises Addendum #1 point 3 (interpolation
> gap-fill tuning)**:
>
> - **Median jaw PCHIP gap = 8 ms cohort-wide** (p90 ≤ 68 ms in every
>   phenotype × epoch cell). ≤ 1.9% of PCHIP fills bridge gaps near
>   the 120 ms cap.
> - **Median severe-acute trial has ZERO gap-fills inside detect
>   window.** Mild-acute (active licking) has 12.4 gap fills per
>   trial on average. **Active-licking sessions, not severe-acute, are
>   what would be affected by a tighter cap.**
> - **For the 8 severe-acute artifact trials**: 5/8 have substantial
>   baseline-fill (5-41% of detect window) — but those frames are
>   already at Stage 5 (gaps > 120 ms; PCHIP couldn't bridge them).
>   The artifact PEAK is on a raw DLC frame ADJACENT to the
>   baseline-fill band, not on a gap-fill frame.
>
> **Net effect on §6 Option B scope:** the v5p3 `max_gap_ms` parameter
> review is **no longer recommended as a primary lever** for the
> cleanup. Tightening to e.g. 60 ms would flip 26% of currently-PCHIP
> frames to baseline-fill, but those flips would mostly land in
> mild/moderate active-licking trials (where short PCHIP fills bridge
> real lick onsets/offsets). That's counterproductive.
>
> **The v5p3 re-emit Priya locked in Addendum #2 still happens** — but
> the v5p3 changes should target different parameters (candidates for
> kickoff): lk_thr tightening (currently 0.50; consider 0.70-0.85),
> n_neigh tightening (currently 3 frames in ±16 ms; consider 5),
> and/or a new Stage-3 cluster-likelihood filter (drop raw clusters
> with mean lk < threshold). `max_gap_ms` stays at 120 ms or modestly
> tightens to ~90 ms (which would flip < 8% of PCHIP frames).
>
> Addendum #2's cluster-classifier-without-shape-rule design + hard
> Y-ceiling are **unchanged** by this finding; those still apply at
> the jaw_pertrial layer.

> **AMENDMENT 2026-05-26 #2 (Priya — cluster-classifier scope + v5p3
> re-emit lock).** Two corrections to Addendum #1:
>
> 1. **Drop tongue v7 Rule A (intra-cluster shape gate) for jaw.**
>    Tongue's Rule A (Phase 7e Decision 9) keeps clusters where
>    `cluster_min < 80 OR cluster_range > 50` — it KEEPS only clusters
>    that span baseline-to-peak (real lick shape) and WIPES clusters
>    flat at high y (plateau artifact). This does NOT translate to
>    jaw: **real jaw trajectories can look "flat" at sustained high-y
>    postures**, so a shape-based filter would falsely wipe real jaw
>    activity. Phase 7f must invent a jaw-appropriate cluster
>    discriminator. Candidate criteria for kickoff exploration:
>    - **Cluster contiguity / duration:** real jaw movement is
>      contiguous (PS54 t013 from ~1300 ms onwards); artifact clusters
>      are short and surrounded by Stage-5 baseline-fill bands within
>      the same trial.
>    - **Mean / median likelihood within the cluster:** real jaw
>      activity sustains `lk > 0.85`; artifact clusters tend toward
>      `lk = 0.3-0.5`. Cluster-mean-lk gate may be a better
>      discriminator than per-frame lk gates.
>    - **Hard Y-ceiling + frame-level outlier wipe** (Rules 1 and 3
>      from Addendum #1) port cleanly and are NOT affected by this
>      revision.
>    - **Isolated-short override** (Phase 7e Decision 11) likely still
>      applies — short isolated clusters surrounded by long baseline-
>      fill are artifacts in both tongue and jaw, regardless of shape.
> 2. **Jaw v5p3 re-emit is desired.** Priya 2026-05-26 explicitly
>    wants a cohort jaw v5p3 re-emit after the cleanup. This **locks
>    Option B (`bodypart-parametric v7 port` with cohort v5p3
>    re-emit) as the chosen architecture**, NOT Option A. Option A's
>    "all logic inside `jaw_pertrial.py`, no v5p3 re-emit" framing is
>    now obsolete; treat it as a fallback only if Option B is
>    infeasible. Phase 7f kickoff scope expands to include v5p3
>    `max_gap_ms` review + per-bodypart preclean constants.
>
> **Net effect on §5 verdict:** scope firmly in the bodypart-
> parametric v7 port tier (Option B). Cluster classifier needs a
> jaw-specific rule set, NOT a direct tongue port. Wall-time stays
> ~2-3 weeks CC; the cluster-discriminator design phase may add 1-3
> days at the front for empirical exploration on the audit
> visual-render set. Q-1 in §7 is now answered (Option B locked);
> Q-2 + Q-3 still open.

---

## 1. Context + motivation

Phase 7e (merged 2026-05-26 at `027f063`, tag `v7e-dlc-tongue-preclean-v7`)
introduced the v7 pre-clean + detector + gates pipeline for tongue
kinematics. Phase 7e DECISIONS 2026-05-25 Decision 8 explicitly deferred
the jaw analog: *"The v7 architecture … generalizes to jaw kinematics
but all parameters … are tongue-specific. Priya 2026-05-25 deferred jaw
work until after Phase 7e tongue migration lands in production and
downstream effects are validated."*

Tongue is now landed; the cohort re-emit + downstream stats
regeneration is in flight via Event B
(`chore/phase-7e-cohort-reemit`, PR #135) on a separate session.

**Why jaw matters.** Memory finding #7 records that the jaw spatial
Wasserstein endpoint `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
carries the strongest confirmatory signal in the Phase 9 cohort
(`q ≈ 9e-15`). The recovery_trajectories endpoint list in
[`notebooks/15_spout_behavior_visual_gate.ipynb`](../../notebooks/15_spout_behavior_visual_gate.ipynb)
treats it as a paper-figure-grade scalar. If the jaw v5p3 trace or its
downstream peak-deflection scalars have artifactual patterns analogous
to tongue's PCHIP-anchored-spike-against-Stage-5-baseline-fill, the
paper narrative around jaw movement may need to be revised. This audit
is a read-only scoping exercise to establish whether the concern is
real.

**Critical scope split.** Two distinct jaw data products consume
different upstream:

| Consumer | Upstream | Lk gate | Stage-5 fill applies? |
| --- | --- | --- | --- |
| `dlc_spatial.heatmaps` → `spatial_wasserstein_jaw_*` | raw DLC frames | `0.80` | **no** (frames below gate are dropped, not filled) |
| `jaw_pertrial.py` (8 scalars) → `tongue_jaw_mismatch.candidate_no_lick_with_jaw_move` | v5p3 `y_final` interpolated trace | `0.50` (Stage 2) | **yes** (Stage 5 fills with `Y0 = resting jaw position`) |

→ **The headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
endpoint is NOT directly affected by a hypothetical v5p3 cleanup** —
it consumes the lk≥0.80 raw-frame heatmap. Any Phase 7f cleanup
scope therefore targets the `jaw_pertrial` scalar family + the
mismatch classifier's `jaw_pass_qc` gate, NOT the headline Wasserstein.

---

## 2. Jaw pipeline (read-only audit findings)

Production jaw pipeline (per
[src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py](../../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py)
+ [interpolation.py](../../src/stroke_orofacial/dlc_kinematics/interpolation.py)):

1. **Stage 1-3 (raw → drop):** X-range filter (±75 px around midline,
   `lk` source), likelihood threshold (`lk_thr = 0.50`), isolated-hi-lk
   neighbor filter (`n_neigh = 3`, `neighbor_ms = 16`).
2. **Stage 4 (short-gap fill):** PCHIP (fallback linear) for gaps
   ≤ `max_gap_ms = 120` (vs. tongue's 56 ms — jaw is allowed twice the
   gap width).
3. **Stage 5 (baseline fill):** all remaining NaNs filled with the
   forced baseline `(X0, Y0)` from `animals.yaml kinematics_baselines`.
   These frames are stamped `is_baseline_fill = True` + `fill_method = 3`.
4. **Stage 6 (subtract baseline):** final per-frame `y_final = y - Y0`
   (so resting-position frames have `y_final ≈ 0`).
5. **jaw_pertrial:** per-trial scalars consume `y_final` directly. No
   pre-clean, no detector, no gates. Single quantity = `argmax(|y_final -
   baseline_mean|)` inside `[0, 5000] ms`.

**Key contrast vs. tongue.** Tongue's lick artifacts (the v7
motivation) arose because (a) tongue ranges from `y ≈ 0` at rest to
`y ≈ 200` at peak licking — a large dynamic range; (b) DLC sparsity was
10-21% in the severe-acute phenotype, meaning peaks would frequently
fall on PCHIP-anchored frames adjacent to Stage-5-baseline-fill troughs.
Jaw has both a smaller dynamic range AND a dramatically higher detection
rate (see §3.3 below).

---

## 3. Audit findings

> All numbers below are from
> [`.scratch_phase_7f_scoping/audit_results/`](../../.scratch_phase_7f_scoping/audit_results/).
> Audit script:
> [`.scratch_phase_7f_scoping/audit_jaw_quality.py`](../../.scratch_phase_7f_scoping/audit_jaw_quality.py).
> Run date: 2026-05-26. Cohort: 8 primary-cohort animals; Pattern B
> (secondary-spout) sessions excluded per Event B Addendum #1.

### 3.1 Cohort coverage

**231 sessions × 22,363 trials** processed. Phenotype × epoch breakdown
at
[`by_phenotype_epoch.csv`](../../.scratch_phase_7f_scoping/audit_results/by_phenotype_epoch.csv).

### 3.2 (a) Likelihood-at-peak distribution

For each per-trial argmax-|defl| peak frame, the audit reads the raw
DLC likelihood at that exact frame. Headline figure:
[`lk_at_peak_hist.png`](../../.scratch_phase_7f_scoping/audit_results/lk_at_peak_hist.png).

| phenotype / epoch | n_trials | median lk@peak | frac lk<0.5 | frac lk<0.85 |
| --- | --- | --- | --- | --- |
| mild / pre        | 2581 | 0.840 | 0.001 | 0.520 |
| mild / acute      | 408  | 0.801 | 0.000 | 0.635 |
| mild / sub_acute  | 1144 | 0.814 | 0.001 | 0.594 |
| mild / chronic    | 3856 | 0.832 | 0.002 | 0.542 |
| moderate / acute  | 479  | 0.837 | 0.000 | 0.524 |
| mod-sev / acute   | 384  | 0.857 | 0.005 | 0.469 |
| **severe / acute** | **2316** | **0.875** | **0.013** | **0.405** |
| severe / sub_acute | 2833 | 0.790 | 0.003 | 0.572 |
| severe / chronic  | 1672 | 0.688 | 0.001 | 0.733 |
| severe / pre      | 1056 | 0.840 | 0.024 | 0.516 |

**Interpretation.** Median lk-at-peak is **above 0.69 in every cell**
and above 0.80 in 14/16 cells. `frac lk<0.5` is bounded by 2.4% in any
cell. **No phenotype × epoch cell shows tongue-like low-confidence peak
contamination at the cohort level.**

### 3.3 (b) Detection rate / sparsity

Fraction of detect-window (`[0, 5000] ms`) frames with raw
`likelihood_raw > 0.5` AND fraction `is_baseline_fill = True`.

| phenotype / epoch | mean frac raw above prod | mean frac baseline-fill | mean frac interp-fill |
| --- | --- | --- | --- |
| mild / acute      | **0.945** | 0.001 | 0.057 |
| mild / pre        | 0.938 | 0.001 | 0.063 |
| mild / sub_acute  | 0.943 | 0.002 | 0.057 |
| mild / chronic    | 0.938 | 0.002 | 0.062 |
| moderate / acute  | 0.868 | 0.016 | 0.118 |
| moderate / pre    | 0.883 | 0.002 | 0.116 |
| mod-sev / acute   | **0.996** | 0.002 | 0.003 |
| mod-sev / chronic | 0.961 | 0.005 | 0.036 |
| **severe / acute** | **0.986** | 0.005 | 0.010 |
| severe / pre      | 0.898 | 0.017 | 0.090 |
| severe / sub_acute | 0.942 | 0.002 | 0.058 |
| severe / chronic  | 0.935 | 0.000 | 0.067 |

**Headline:** detection rate is **87-99% across every phenotype × epoch
cell**. Compare to tongue Part 1 which reported 10-21% in
severe-acute. **Jaw has roughly 5-10x more raw DLC frames than tongue
in the same epoch.** Baseline-fill within the detect window averages
≤ 1.7% in every cell. This is the dominant qualitative finding — jaw is
not subject to the structural sparsity problem that motivated tongue v7.

### 3.4 (c) Counterfactual likelihood-gate analysis

At lk gates `{0.5, 0.7, 0.85, 0.9}`, peaks were recomputed by masking
all frames below the gate (no spline / parabolic imputation — the
audit just reports the surviving local maximum). Full table:
[`counterfactual_means.csv`](../../.scratch_phase_7f_scoping/audit_results/counterfactual_means.csv).

Mean `|peak deflection|` (px) by gate for the load-bearing cells:

| phenotype / epoch | prod | lk≥0.5 | lk≥0.7 | lk≥0.85 | lk≥0.9 | Δ@lk≥0.9 |
| --- | --- | --- | --- | --- | --- | --- |
| mild / acute      | 100.4 | 100.4 | 96.1 | 94.3 | 93.0 | **−7%** |
| moderate / acute  | 89.1  | 89.1  | 85.9 | 84.0 | 83.5 | **−6%** |
| mod-sev / acute   | 11.34 | 11.34 | 10.96 | 10.08 | 9.35 | **−18%** |
| **severe / acute** | **11.20** | 11.20 | 10.76 | 10.08 | **9.54** | **−15%** |
| severe / chronic  | 74.8 | 74.8 | 69.7 | 64.8 | 62.3 | **−17%** |
| severe / pre      | 101.2 | 101.2 | 96.0 | 91.9 | 91.0 | **−10%** |

**Interpretation.** The dominant biological signal — severe-acute and
mod-sev-acute jaw deflection collapse to ~11 px (one order of magnitude
below all other phenotype × epoch cells) — is **robust to the lk gate
choice**. At lk≥0.9 (vs. prod), the cohort mean drops by 6-18%; the
ranking of cells is preserved.

The 13-15% drops in severe-acute and severe-chronic suggest the cohort
means carry a small per-cell contamination from low-confidence frames,
but this does not change the qualitative narrative (severe-acute jaw is
~10x smaller than severe-pre / mild epochs).

### 3.5 Sign-flip analysis (per-trial robustness)

For each gate, fraction of trials whose argmax-|defl| **changes
sign** when low-confidence frames are masked. Full table:
[`sign_flip_flags.csv`](../../.scratch_phase_7f_scoping/audit_results/sign_flip_flags.csv).

| gate     | severe / acute | mod-sev / acute | mild / acute |
| ---      | --- | --- | --- |
| lk ≥ 0.5 | 0.001 | 0.000 | 0.000 |
| lk ≥ 0.7 | 0.022 | 0.029 | 0.010 |
| lk ≥ 0.85 | 0.065 | 0.091 | 0.007 |
| lk ≥ 0.9 | **0.095** | **0.136** | 0.015 |

**Interpretation.** Sign flip rates at the tightest gate are **highest
in the two phenotype × epoch cells with the smallest cohort-mean
deflection** (severe-acute, mod-sev-acute, both ~11 px). This is
consistent with the mean-deflection floor sitting in the
single-frame-outlier noise band — at ~11 px the difference between
"max positive" and "max negative" deflection is small, so any
single-frame outlier flips the sign. In cells with larger mean
deflection (mild epochs ≥ 90 px), sign flips are essentially absent.

### 3.6 (d) Stage-5-baseline-fill prevalence at peaks

For the trial argmax-|defl| peak frame: was that frame
`is_baseline_fill = True` (Stage-5 forced fill)? Full table:
[`stage5_fill_prevalence.csv`](../../.scratch_phase_7f_scoping/audit_results/stage5_fill_prevalence.csv).

| phenotype / epoch | frac peak at baseline-fill | mean frac detect-win baseline-fill | max frac detect-win baseline-fill |
| --- | --- | --- | --- |
| mild / acute      | 0.000 | 0.001 | 0.071 |
| mild / chronic    | 0.000 | 0.002 | 0.416 |
| mod-sev / acute   | 0.005 | 0.002 | 0.369 |
| severe / acute    | **0.014** | 0.005 | 0.679 |
| severe / pre      | **0.024** | 0.017 | 0.624 |
| severe / sub_acute | 0.002 | 0.002 | 0.680 |
| severe / chronic  | 0.001 | 0.000 | 0.157 |

**Interpretation.** Peak-at-baseline-fill is bounded by **2.4% in any
cell** (severe-pre worst case); 1.4% in severe-acute. **The Stage-5
forced-fill mechanism that produced tongue's PCHIP-anchored-spike
artifacts is essentially never invoked at the jaw argmax peak.**
Cohort-wide, mean baseline-fill within the detect window is < 2% in
every cell.

The non-zero `max frac detect-win baseline-fill` values (e.g., 0.68 in
some severe-acute trials) confirm that occasional sessions experience
extended baseline-fill stretches; but these are individual trials, not
a cohort pattern, and they do not coincide with the argmax peak in the
vast majority of cases.

### 3.7 Interpolation gap-fill characteristics (audit #2)

Phase 7f scoping audit #2 (run 2026-05-26) characterized the Stage-4
PCHIP-fallback-linear gap-fill mechanism. Audit script:
[`.scratch_phase_7f_scoping/audit_jaw_interpolation.py`](../../.scratch_phase_7f_scoping/audit_jaw_interpolation.py).
1.9 M gap records across 8-animal × 2-bodypart cohort
(jaw + tongue reference). Outputs at
[`.scratch_phase_7f_scoping/audit_results/interpolation/`](../../.scratch_phase_7f_scoping/audit_results/interpolation/).

**(a) PCHIP gap-length distribution.** Across all phenotype × epoch
cells, jaw PCHIP/LINEAR fills are dominated by short gaps:

| cell | median PCHIP gap (ms) | p90 PCHIP gap (ms) | max PCHIP gap (ms) | frac PCHIP gaps near cap (> 96 ms) |
| --- | --- | --- | --- | --- |
| jaw mild / acute      |  8 | 52 | 120 | 0.9% |
| jaw moderate / acute  | 16 | 68 | 120 | 1.9% |
| jaw mod-sev / acute   |  8 | 32 | 120 | 1.4% |
| jaw **severe / acute** |  8 | 48 | 120 | **1.6%** |
| jaw severe / chronic  |  8 | 52 | 120 | 0.5% |
| jaw severe / pre      |  8 | 52 | 120 | 1.2% |
| tongue **severe / acute** |  8 | 32 |  56 | **3.8%** |
| tongue mild / chronic |  8 | 48 |  56 | 10.6% |

Headline: **median jaw PCHIP gap = 8 ms cohort-wide**; ≤ 2% of jaw
PCHIP fills bridge gaps near the 120 ms cap. Tongue's PCHIP
distribution is qualitatively similar — most fills short, with a small
tail at the cap. Tongue's cap-tail fraction is higher in % because the
56 ms cap clips a wider real distribution; tongue at 120 ms would
likely also see only ~1-3% at the new cap.

**(b) Counterfactual max_gap_ms.** If the jaw v5p3 cap were tightened,
fraction of currently-PCHIP-filled frames that would flip to
Stage-5 baseline-fill:

| tightened cap (ms) | n gaps flipped | n frames flipped | frac of PCHIP frames flipped |
| --- | --- | --- | --- |
|  30 | 204 860 | 2 737 177 | **66.3%** |
|  60 |  53 530 | 1 064 465 | **25.8%** |
|  90 |  12 189 |   316 022 |  **7.7%** |
| 120 (prod) | 0 | 0 | 0% |

Tightening to tongue's 56 ms would flip ~26% of currently-PCHIP
frames. **But these are mostly in active-licking sessions
(mild/moderate epochs), not severe-acute** — see (c) below.

**(c) Per-trial gap structure inside detect window.** Distribution of
the maximum gap-fill duration inside `[0, 5000]` ms across trials:

| cell | n_trials | mean n_gaps in detect | p50 max_gap (ms) | p90 max_gap (ms) | mean frac PCHIP | mean frac baseline |
| --- | --- | --- | --- | --- | --- | --- |
| mild / acute       |  408 | 12.4 | 56 |  92 | 5.7% | 0.1% |
| moderate / acute   |  479 | 15.7 | 76 | 112 | 11.8% | 1.6% |
| mod-sev / acute    |  384 |  1.1 |  0 |  16 |  0.3% | 0.2% |
| **severe / acute** | 2316 |  3.1 | **0** | 68 |  1.0% | 0.5% |
| severe / sub_acute | 2833 | 13.2 | 60 |  92 | 5.8% | 0.2% |
| severe / chronic   | 1672 | 16.3 | 56 |  84 | 6.7% | 0.0% |
| severe / pre       | 1056 | 24.7 | 68 | 158 | 9.0% | 1.7% |

**Surprising finding:** **the median severe-acute trial has ZERO gap
fills in its detect window.** Severe-acute mice are mostly
not-licking (the dominant biological signal), so DLC has nothing
moving to lose track of — long contiguous raw-DLC stretches dominate.
The artifacts live in the **upper tail** of the severe-acute
distribution.

By contrast, **mild-acute (active licking)** has 12.4 gap fills per
trial on average, with p50 max_gap = 56 ms — the active licking causes
DLC tracking blips at lick onsets/offsets. Tightening
`max_gap_ms` would primarily affect THESE active-licking trials, not
the severe-acute artifact cases.

**(d) Per-artifact-trial gap context.** For the 8 hand-picked
severe-acute renders (full table:
[`artifact_trial_gap_table.csv`](../../.scratch_phase_7f_scoping/audit_results/interpolation/artifact_trial_gap_table.csv)):

| trial | n_gaps | max_gap_ms | frac PCHIP | frac baseline | artifact mechanism |
| --- | --- | --- | --- | --- | --- |
| PS55 / 5-14 / t033 L | 36 | 428 | **18.9%** | **41.2%** | Real licking + long baseline-fill bands between licks; low-lk peaks at the licking events |
| PS54 / 5-01 / t013 R | 14 | 428 | 5.0% | 16.1% | High-y cluster from 0-1200ms bracketed by baseline-fill; real licking starts ~1300ms |
| PS54 / 5-05 / t010 L | 18 | 292 | 2.6% | 21.3% | Mixed |
| **PS54 / 5-06 / t095 L** | **11** | **52** | 3.6% | **0.0%** | **Pure single-frame outlier on raw DLC; NO gap-fill involvement** |
| PS55 / 5-06 / t002 L | 21 | 488 | 6.0% | 26.7% | Real licking + baseline-fill bands |
| PS55 / 5-09 / t021 L | 12 |  84 | 6.7% |  0.0% | Mid-confidence single-frame; small gaps |
| PS54 / 5-09 / t006 L | 30 | 156 | **14.9%** | 6.1% | Heavy gap activity (active session) |
| PS55 / 5-17 / t003 R | 19 |  40 | 5.6% |  0.0% | High-lk real movement; small gaps |

**Key takeaway:** **the largest-|defl| artifact peaks ARE adjacent to
baseline-fill bands** (6/8 trials have non-zero baseline-fill in
detect window; 5/8 have substantial baseline-fill > 5%), but the
artifact PEAK itself is on a raw DLC frame, NOT on a gap-fill frame.
**The baseline-fill bands are gaps THAT EXCEEDED the 120 ms cap** —
they already fell through to Stage 5. Tightening max_gap_ms wouldn't
change them (they're already baseline-filled). The PCHIP fills that
WOULD have flipped are the short ones (< 120 ms) that bridge real
licking onsets/offsets in active-licking trials.

**Conclusion:** **v5p3 `max_gap_ms` tightening has limited leverage on
the jaw artifact problem.** The artifact mechanism is at the raw-DLC
level (mid-confidence frames with outlier y at the edges of
baseline-fill bands), not at the gap-fill level. Tightening would
mostly affect active-licking sessions (mild/moderate epochs) where
short PCHIP fills bridge real movement transients — likely
counterproductive.

---

## 4. Visual verdict — 8 hand-picked severe-acute trials

Renders at
[`.scratch_phase_7f_scoping/visual_renders/`](../../.scratch_phase_7f_scoping/visual_renders/).
Selection: top-4 (per-animal) `peak_abs_deflection` across severe-acute
(`phenotype = severe`, `epoch = acute`) trials — 8 trials total (PS54 + PS55).
Each render shows the v5p3 `y_final` trace (raw-kept frames black,
interp-filled grey, baseline-filled red ×) plus per-frame
`likelihood_raw` (top + bottom panels respectively).
Selected-trial table at
[`chosen_trials.csv`](../../.scratch_phase_7f_scoping/visual_renders/chosen_trials.csv).

| trial | peak |defl| | peak_lk | peak_is_baseline_fill | peak |defl| at lk≥0.9 | pattern |
| --- | --- | --- | --- | --- | --- |
| PS55 / 2025-05-14 / t033 L | 183.4 | 0.57 | False | 77.9 | Real licking trace with multiple peaks; absolute peak at lk=0.57. |
| PS54 / 2025-05-01 / t013 R | 138.3 | 0.72 | False | 36.4 | Mid-confidence peak; big counterfactual drop. |
| PS54 / 2025-05-05 / t010 L | 129.4 | 0.56 | False | 45.9 | Mid-confidence peak; big counterfactual drop. |
| **PS54 / 2025-05-06 / t095 L** | **125.1** | 0.66 | False | **8.7** | **Single-frame outlier** on otherwise resting trace at y≈−15; classic DLC misdetection. |
| PS55 / 2025-05-06 / t002 L | 123.4 | 0.50 | False | 25.3 | Borderline-lk peak; big counterfactual drop. |
| PS55 / 2025-05-09 / t021 L | 119.1 | 0.56 | False | 31.0 | Mid-confidence peak; big counterfactual drop. |
| PS54 / 2025-05-09 / t006 L | 114.3 | 0.57 | False | 106.3 | Real movement — lk=0.57 frame is on a structurally supported peak; counterfactual barely changes. |
| PS55 / 2025-05-17 / t003 R |  88.1 | 0.91 | False | 88.1 | Clean high-confidence peak; counterfactual unchanged. |

**Key observation:** **none of the 8 chosen peaks fell on baseline-fill
or interp-fill frames.** All peaks landed on raw DLC frames. This
**rules out the analogous PCHIP-anchored-spike-against-Stage-5-zeros
artifact mechanism that motivated tongue v7.**

**Different artifact mechanism for jaw:** 5/8 of the largest
severe-acute peaks are **single mid-confidence raw DLC frames** with
outlier y values, on otherwise resting traces. The most extreme case
(PS54 / 2025-05-06 / t095 L) is a single-frame 125 px spike at lk=0.66
on a trace that otherwise sits steady at y≈−15. Counterfactual at
lk≥0.9 drops it to 8.7 px (93% drop). 3/8 are robust real movements
(small counterfactual drop). This is a **different artifact pattern**
than tongue's; the v7 cluster classifier / PCHIP-extend wipe pipeline
is calibrated for a structural pattern that jaw does NOT exhibit.

---

## 5. Recommended Phase 7f scope (verdict, REVISED per amendment)

> **Verdict:** between `light-cleanup-plus` (Option A) and
> `bodypart-parametric v7 port` (Option B). Architecture picked at
> kickoff. Scope substantively larger than the initial single-frame
> framing.

**Rationale:**

1. **Cluster-level artifact pattern IS present** (per Priya's review
   of PS54 / 2025-05-01 / t013 R): high-y raw DLC clusters reaching
   100-150 px bracketed by Stage-5 baseline-fill bands with lk < 0.5.
   **This IS the structural analog of tongue v7's PCHIP-anchored-spike-
   against-Stage-5-zeros mechanism.**
2. **Single-frame outlier pattern is also present** (PS54 t095): mid-
   confidence single-frame spikes on otherwise-resting traces.
3. **Cohort-level metrics understate per-trial contamination.** The
   ≤ 2.4% baseline-fill-at-peak aggregate hides the distribution tail
   where cluster + frame artifacts produce the largest |defl| values.
4. **A hard Y-ceiling rule (~75 px above baseline)** is a simple,
   high-SNR gate. Calibrate from per-animal `y99` of lk≥0.85 raw DLC.
5. **The v7 architecture DOES apply to jaw** — the architecture is
   right; the constants need jaw-specific recalibration.

**Out-of-scope for Phase 7f (unchanged):**
- The headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
  endpoint reads raw frames at lk≥0.80 (NOT v5p3); unaffected by any
  jaw_pertrial / jaw-v5p3 cleanup. See Q-4 in §7.

**Re-classified in-scope per amendment:**
- v5p3 `max_gap_ms = 120` (vs. tongue's 56) may need tightening. If
  so, cohort jaw v5p3 re-emit is required — this is the architecture
  choice distinguishing Option A from Option B in §6.

---

## 6. Forward-pointers — Phase 7f scope options (REVISED per amendment)

Two architecture choices below; Priya picks at kickoff. The audit
confirms cleanup is needed; the architecture choice is the open
scoping question.

### Option A — `light-cleanup-plus`: all logic inside `jaw_pertrial.py`

Add the new rules at the jaw_pertrial input snippet level — after
reading the v5p3 trace but before `_compute_jaw_deflections`. The v5p3
parquets stay untouched; no cohort v5p3 re-emit.

Required rules (apply in order):
1. **Hard Y-ceiling wipe:** any frame with
   `y_final - baseline_mean > Y_CEILING_PX` (~75 px per Priya
   2026-05-26; calibrate on per-animal `y99` of lk≥0.85 raw DLC) is set
   to NaN. Single threshold, no per-cluster logic.
2. **Cluster classifier** (port of Phase 7e Decisions 9 + 11): for
   contiguous runs of `y > HIGH_THR` AND `fill_method == 0` (raw DLC
   kept):
   - **artifact_intra_cluster** if intra-cluster shape flat
     (`cluster_range < SHAPE_RANGE_THR_JAW` AND
     `cluster_min > SHAPE_LOW_THR_JAW`).
   - **artifact_isolated_short** if `n ≤ ISOLATED_MAX_N` AND no other
     raw cluster within `±ISOLATED_RADIUS_MS`.
   - **kept** otherwise.
3. **Frame-level outlier wipe** (port of Decision 12): within each
   kept cluster, wipe single frames where
   `|y[k] - local_median(±20ms)| > FRAME_JUMP_THR_JAW`.
4. **PCHIP-extend wipe** (port of Decision 13): after wiping a cluster
   or frame, also wipe adjacent `is_interp_fill` frames within
   `±PCHIP_EXTEND_MS` until a non-interp anchor is reached.
5. **Peak-likelihood gate:** when picking
   `argmax(|y_clean - baseline_mean|)`, require
   `likelihood_raw ≥ PEAK_LK_GATE` (suggest 0.85).

- **Affects:** new module
  `src/stroke_orofacial/dlc_kinematics/_jaw_preclean.py` consumed by
  `jaw_pertrial.py` (OR a shared bodypart-parametric helper in
  `_preclean.py` for tongue/jaw sharing). Re-emit per_trial JSONs only
  (not v5p3 parquets).
- **Risk:** cluster predicates depend on `fill_method` — if v5p3 mis-
  classified a fragment as PCHIP-fill, this option can't recover it.
  Audit suggests this is rare for jaw (PCHIP-fill rate < 12% in all
  cells).
- **Estimated wall-time:** **3-5 days CC** (port + 5+ new constants
  calibrated + unit tests + cohort per_trial re-emit + visual-gate
  parity on the 8 severe-acute renders + tongue_jaw_mismatch
  candidate-rate parity check).

### Option B — `bodypart-parametric v7 port`: full v5p3 integration

Port the v7 architecture into bodypart-parametric form
(`_preclean.py`, `_detector_v2.py`, `_gates.py` accept `bodypart` and
load constants from `configs/defaults.yaml dlc_kinematics.<bp>.preclean.*`).
Tune `max_gap_ms` at v5p3 level (currently 120 ms for jaw — Priya
flagged this may be too lenient). Cohort jaw v5p3 re-emit.

- **Affects:** all 3 v7 modules become bodypart-parametric (tongue +
  jaw first-class). `interpolation.py` jaw branch gets a new
  `max_gap_ms` value. Both v5p3 jaw parquets AND per_trial JSONs
  re-emit cohort-wide.
- **Risk:** v5p3 re-emit invalidates downstream stats — Phase 9 axis
  results consuming jaw_pertrial scalars need re-run. Event B's
  just-completed re-emit is unaffected (tongue-specific) but Phase 9
  cohort outputs are.
- **Estimated wall-time:** **2-3 weeks CC** (tongue v7's algorithm
  design took 3 days in `.scratch_phase_9_1/`; tongue v7's production
  phase took ~3 weeks). Jaw inherits the architecture but needs its
  own calibration + parity harness.

### Recommended option

**Option A (`light-cleanup-plus`)** unless Priya specifically wants
v5p3 `max_gap_ms` tuning to land now. Rationale:
- All needed input columns (`fill_method`, `likelihood_raw`,
  `is_baseline_fill`) are preserved in the v5p3 parquet — Option A can
  reach the artifacts via post-v5p3 filtering.
- No cohort v5p3 re-emit → no invalidation of Event B or upstream
  stats inputs derived from v5p3 traces.
- Easier iteration on constants during kickoff.
- Option B remains a future forward-pointer if Priya later wants to
  share preclean logic with tongue (re-running tongue under bodypart-
  parametric form is a no-op when tongue-specific constants are
  preserved).

---

## 7. Open questions for Priya

> Numbered Q-1 through Q-5 for easy reference in addenda.

- **Q-1 (REVISED).** Architecture pick: **Option A
  (`light-cleanup-plus`, all logic inside `jaw_pertrial.py`)** vs.
  **Option B (`bodypart-parametric v7 port`, full v5p3 integration)**?
  Recommendation: A unless you want v5p3 `max_gap_ms` tuning to land
  now rather than later.
- **Q-2 (NEW per amendment).** Y-ceiling threshold: ~75 px above
  baseline is the suggested anchor. Should Phase 7f calibrate from
  per-animal `y99` of lk≥0.85 raw DLC, or pick a cohort-uniform value?
- **Q-3 (REVISED).** Severe-acute peak-deflection floor: current prod
  `mean peak_abs_deflection` = 11.2 px. After the full Option A
  pipeline (Y-ceiling + cluster + frame + PCHIP-extend + lk-gate), the
  drop will likely be larger than the initial 10% lk-gate-only
  estimate, since several severe-acute trials have current peaks
  > 100 px that are clearly artifactual (PS54 t013/t095). Comfortable
  with the headline floor potentially dropping to ~5-9 px, or want
  Phase 7f to include a sensitivity analysis before locking?
- **Q-4.** Headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
  reads raw frames at lk≥0.80 — outside v5p3, outside this audit.
  Should we queue a separate forward-pointer to audit that pipeline's
  quality (analogous to this one but for raw-DLC inputs to spatial
  heatmaps)? Memory finding #7 marks it as the strongest jaw signal,
  so independent quality verification before publication may be
  prudent.
- **Q-5.** The `tongue_jaw_mismatch.candidate_no_lick_with_jaw_move`
  classifier consumes `jaw_pass_qc` (boolean: ≥ 5/8 frames within any
  rolling 8-frame window have `|defl| > max(4 SD, 4 px)`). After L1/L2
  the threshold-test inputs change. Should Phase 7f's success-gate
  include a `jaw_pass_qc` candidate-rate parity check (the
  candidate_no_lick_with_jaw_move count per session shouldn't shift by
  more than X%), or is the per-session scalar parity check sufficient?

---

## 8. Reference artifacts

- Audit script: [`.scratch_phase_7f_scoping/audit_jaw_quality.py`](../../.scratch_phase_7f_scoping/audit_jaw_quality.py) — 8 animals × 231 sessions × 22,363 trials.
- Visual renderer: [`.scratch_phase_7f_scoping/render_severe_acute_jaw_traces.py`](../../.scratch_phase_7f_scoping/render_severe_acute_jaw_traces.py).
- Audit aggregate outputs: [`.scratch_phase_7f_scoping/audit_results/`](../../.scratch_phase_7f_scoping/audit_results/) (8 CSVs + 2 PNGs).
- Visual renders: [`.scratch_phase_7f_scoping/visual_renders/`](../../.scratch_phase_7f_scoping/visual_renders/) (8 PNGs + chosen_trials.csv).
- Tongue investigation template: `.scratch_phase_9_1/dlc_tongue_quality_investigation/`.
- Phase 7e DECISIONS (jaw deferral): `docs/DECISIONS.md` 2026-05-25 Decision 8.
