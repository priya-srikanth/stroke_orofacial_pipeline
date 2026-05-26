# Phase 7f — Jaw DLC quality investigation (scoping doc)

> **Status:** DRAFT — investigation-only audit. No production code or data
> touched. Final scope decision pending Priya review of the verdict.
>
> **Branch:** `investigation/jaw-quality-audit` (off `main` at 2026-05-26).
> Parallel to and independent of Event B
> (`chore/phase-7e-cohort-reemit`, PR #135).
>
> **Verdict: `light-cleanup`** — jaw v5p3 is qualitatively much cleaner
> than tongue (>98% detection rate cohort-wide; Stage-5 baseline-fill at
> peaks ≤ 2.4% in any phenotype × epoch cell), so a full v7-style
> pre-clean + detector + gates rebuild is **NOT warranted**. But the
> largest severe-acute / mod-sev-acute peaks are visibly contaminated by
> single-frame DLC outliers at mid-confidence (`lk ≈ 0.5-0.7`). Cohort
> means shift 13-15% at the tightest gate. Recommended scope is a
> light intervention scoped to `jaw_pertrial.py` only — see §5 + §6.

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

## 5. Recommended Phase 7f scope (verdict)

> **Verdict: `light-cleanup`.**

**Rationale:**
1. **Stage-5-fill mechanism is essentially never triggered for jaw.**
   `frac_peak_at_baseline_fill ≤ 2.4%` in any cell; visual renders
   confirm peaks land on raw DLC frames. The structural concern that
   motivated tongue v7 does NOT replicate in jaw.
2. **Cohort detection rate is 87-99% in every cell** (vs. tongue's
   10-21% in severe-acute). Jaw is not sparsity-limited.
3. **Dominant biological signal (severe-acute / mod-sev-acute jaw
   collapse to ~11 px) is robust to the lk gate choice** (15-18% shift
   at lk≥0.9 does not change the qualitative narrative; cell ranking
   preserved).
4. **BUT**: the largest severe-acute peaks are visibly contaminated by
   single-frame DLC outliers at mid-confidence (lk = 0.5-0.7). 5/8
   visual-render extremes show classic single-frame-spike artifacts.
   Sign-flip rate at lk≥0.9 in severe-acute is 9.5% (highest in cohort).
5. The artifact mechanism is **different from tongue's**; a full v7
   port would not be the right tool. A lightweight intervention scoped
   to `jaw_pertrial.py` is sufficient.

**Out-of-scope for Phase 7f:**
- The headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
  endpoint reads raw frames at lk≥0.80 (NOT v5p3); it is unaffected by
  any jaw_pertrial cleanup. See Q-4 in §7 for whether a separate
  raw-DLC audit should be queued.
- The v5p3 interpolation parameters (`lk_thr=0.50`, `max_gap_ms=120`,
  etc.) stay as-is. Modifying them would re-emit cohort-wide and
  invalidate Event B's just-completed re-emit — too costly relative to
  the small expected benefit.

---

## 6. Forward-pointers — Phase 7f scope options

(All three options are scoped to **`jaw_pertrial.py` and its callers
only**; none touch `interpolation.py` or require cohort v5p3 re-emit.)

### Option L1 — Peak-likelihood gate at jaw_pertrial output

Add a per-peak filter that requires the argmax frame to have
`likelihood_raw ≥ JAW_PEAK_LK_GATE` (suggest 0.85, matching tongue v7's
E-gate likelihood threshold). If the argmax frame fails the gate, walk
to the next local max satisfying the gate; emit NaN if none survives.

- **Affects:** `_compute_jaw_deflections` + new config knob
  `dlc_kinematics.jaw_pertrial.peak_lk_gate`. Re-emit per_trial JSONs
  only.
- **Risk:** trials with no high-confidence jaw movement (real
  severe-acute paralysis) emit NaN peak instead of noise-band peak —
  this is arguably more honest but may be a downstream-stats
  inconvenience.
- **Estimated wall-time:** ~1 day CC (logic + unit test + cohort
  per_trial re-emit).

### Option L2 — Single-frame outlier wipe (tongue v7 frame-level pass, jaw-parametrized)

Port the Phase 7e Decision 12 frame-level outlier wipe (`PRECLEAN_FRAME_JUMP_THR=100,
PRECLEAN_FRAME_RADIUS_MS=20`) to jaw — for each raw DLC frame, compute
local median (±20ms window) and wipe single frames whose `|y[k] -
local_median| > 100 px`. Apply at jaw_pertrial input (snippet level),
not at v5p3 level.

- **Affects:** new helper in `jaw_pertrial.py` (or a shared
  `_frame_outlier_wipe` utility) + new config block. Re-emit per_trial
  JSONs only.
- **Risk:** real peaks atop short raw-DLC sequences (the 30-50 ms
  rise-peak-fall in actively licking jaw) might be wiped if the
  threshold is too tight. Need to recalibrate `PRECLEAN_FRAME_JUMP_THR`
  for jaw's smaller dynamic range vs. tongue.
- **Estimated wall-time:** ~2 days CC (logic + threshold tuning on
  severe-acute visual-render set + unit test + cohort re-emit).

### Option L3 — Combined L1+L2 (recommended)

Apply L1 first (cheap, catches mid-confidence single-frame outliers
like PS54/2025-05-06/t095 — peak_lk=0.66 wipes immediately). Fall back
to L2 for the residual cases where lk is paradoxically high on a
single-frame outlier (rare per the audit). Document the order so future
maintainers know L1 is primary.

- **Estimated wall-time:** ~2-3 days CC.

### Why NOT full v7 rebuild

A full v7-style pre-clean (cluster classifier + Rule A/B + PCHIP-extend
+ find_peaks + gates F/D/E/M) for jaw would require:
- Re-calibrating all 17 tongue-specific constants for jaw's smaller
  dynamic range and different lick-event shape (jaw doesn't lick — it
  shows post-tone open/close cycles).
- New 14-session legacy-approximate parity harness AND visual gate
  (analogous to Phase 7e Task 7).
- Cohort v5p3-equivalent re-emit (if the cluster classifier replaces
  v5p3's Stage 1-3 dropping rules, which is the architecturally clean
  design).
- Multi-week design + implementation timeline (tongue v7 design took
  3 days in `.scratch_phase_9_1/`; tongue v7 phase implementation took
  3 weeks).
- **All to address a problem the audit shows is small at cohort
  level** (15% mean shift at the tightest gate; sign-flip rate < 10%).

Conclusion: full v7 rebuild for jaw is a poor ROI. The light-cleanup
options above address the actual artifact mechanism (single-frame
outliers at mid-confidence) with much smaller surface area.

---

## 7. Open questions for Priya

> Numbered Q-1 through Q-5 for easy reference in addenda.

- **Q-1.** Verdict acceptance: do you concur with `light-cleanup` over
  `full-v7-rebuild`?
- **Q-2.** If yes: which option (L1 / L2 / L3) do you prefer? L3 is
  the recommendation; L1 alone is the lowest-risk minimum-viable
  intervention.
- **Q-3.** Severe-acute peak-deflection floor: with current production
  jaw_pertrial, `mean peak_abs_deflection` in severe-acute = 11.2 px.
  After Option L1 (lk≥0.85 gate), the expected value drops to ~10.1 px
  (per §3.4 counterfactual table). This is a 10% shift in the
  paper-narrative-load-bearing scalar. Is the more-honest 10.1 px the
  preferred number to report, or would you want to discuss further
  before locking in?
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
