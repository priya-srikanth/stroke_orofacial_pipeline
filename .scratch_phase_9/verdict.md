# Phase 9 — Task 8 verification verdict (2026-05-25)

Per the kickoff Task 8 spec: 4 quantitative gates + 2 Priya-scientific-review
eyeball gates. CC owns gates 1-4; Priya owns gates 5-6. **STOP-and-report
follows this document.**

CC verification run via [`.scratch_phase_9/_task_8_verification.py`](_task_8_verification.py);
raw output cached at [`.scratch_phase_9/_task_8_results.json`](_task_8_results.json).

---

## Gate 1 — Methodology sanity (CC analysis)

For each axis, 2-3 confirmatory endpoints checked against expected sign +
significance. Confirms the runner machinery returns scientifically-coherent
effects with the right direction. Hand-pick set is CC's own (not Priya's
yet — see Priya-review section below).

| axis | endpoint | observed effect | q (BH-FDR) | expected sign | verdict |
|---|---|---:|---|---:|---|
| pre_post | `first_lick_accuracy_all` | **−0.437** | 1.87e-02 | − | ✓ OK |
| pre_post | `num_correct_licks_per_trial` | **−11.3** | 1.87e-02 | − | ✓ OK |
| pre_post | `tongue_lick1_t_peak_ms` | **+72.8 ms** | 1.87e-02 | + | ✓ OK |
| recovery | `first_lick_accuracy_all` (slope) | +0.0123 | 5.69e-39 | + | ✓ OK |
| recovery | `num_incorrect_licks_per_trial` (slope) | +0.0455 | 6.47e-18 | − | **REVIEW** |
| recovery | `tongue_lick1_y_peak` (slope) | −0.561 | 1.61e-88 | − | ✓ OK |
| ipsi_contra | `tongue_lick1_x_at_ypeak` | +35.0 | 1.56e-02 | + | ✓ OK |
| ipsi_contra | `tongue_lick1_angle_at_ypeak` | +3.59 | 1.56e-02 | + | ✓ OK |

**Pass: 7 / 8.**

**1 REVIEW** — `num_incorrect_licks_per_trial` recovery slope is **positive**
(incorrect licks INCREASE over time post-stroke), opposite to CC's naive
expectation (recovery → fewer mistakes). Scientifically plausible explanation:
post-stroke licking activity recovers in general, and recovered licking
includes both correct AND incorrect attempts in approximately the recovery-
proportional rate. Confirm with Priya whether this is the expected scientific
direction — the q-value is highly significant (q=6.5e-18) either way, just
the sign interpretation needs sanity-check.

## Gate 2 — Internal consistency (Wilcoxon vs paired t-test)

Same per-animal pre/post pairs run through both `scipy.stats.wilcoxon`
(production runner) and `scipy.stats.ttest_rel` (legacy comparison). Agreement
at α=0.05 expected when the per-animal-diff distribution is approximately
normal.

| endpoint | Wilcoxon p | t-test p | verdict |
|---|---:|---:|---|
| `first_lick_accuracy_all` | 7.81e-03 | 8.42e-04 | ✓ AGREE |
| `num_correct_licks_per_trial` | 7.81e-03 | 4.36e-03 | ✓ AGREE |
| `tongue_lick1_y_peak` | 0.641 | 0.386 | ✓ AGREE (both NS, opposite-sign anims pull median diff toward 0) |
| `tongue_lick1_t_peak_ms` | 7.81e-03 | 0.0562 | **DIVERGE** (Wilcoxon sig, t-test borderline NS) |
| `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all` | 2.34e-02 | 4.88e-02 | ✓ AGREE (both sig) |

**Agree at α=0.05: 4 / 5.**

**1 DIVERGE** — `tongue_lick1_t_peak_ms` Wilcoxon p=0.0078 (sig); t-test
p=0.056 (borderline NS). The endpoint has a heavy-tailed per-animal-diff
distribution (one animal's +500 ms diff vs others' +100 ms range), which is
exactly the case where Wilcoxon's non-parametric framing dominates the
t-test's normality assumption. Both tests detect the effect in the same
direction; the t-test's power loss is the expected behavior at n=8.
Decision: **Wilcoxon remains canonical** (per kickoff §4); divergence is
expected, not a bug.

## Gate 3 — Permutation reproducibility (CC analysis)

Seeded re-run of `paired_permutation_null` with `random_state=42` twice +
`random_state=99` once. Reproducibility property: same seed → identical
output; different seed → different output; downstream p-value via
`permutation_p_value` exactly identical when null array is identical.

```
Same seed (42) → identical null arrays:    True
Different seed (99) → null array differs:  True
Same-seed p_values match exactly:          True  (both = 0.0010)
```

**Verdict: ✓ PASS.** Reproducibility guarantee from Task 3d holds; no RNG
contamination in the production permutation primitive. Future Task 9.x
analyses that pre-register p-values at a specific seed can be exactly
re-derived.

## Gate 4 — Cohort pool vs leave-one-out sensitivity (Cohen's d > 0.3)

For each of the 12 confirmatory `pre_post` endpoints: compute per-animal
paired diffs, then leave-one-animal-out the cohort mean, and report the
max |Cohen's d| of the LOO shift (using the LOO-subset SD as the denominator).
Threshold: 0.3 (medium effect).

| endpoint | pooled diff | max |Cohen's d| | drop animal | flag |
|---|---:|---:|---|---|
| **`latency_hist`** | **+0.087** | **−0.373** | **PS51** | **FLAG** |
| `tongue_lick2_x_at_ypeak` | +21.82 | −0.292 | PS51 | OK |
| `tongue_lick1_angle_at_ypeak` | +1.84 | −0.286 | PS54 | OK |
| `tongue_lick1_x_at_ypeak` | +17.18 | −0.277 | PS54 | OK |
| `num_incorrect_licks_per_trial` | −0.136 | −0.253 | PS55 | OK |
| `tongue_lick1_y_peak` | +16.48 | −0.244 | PS50 | OK |
| `tongue_lick2_angle_at_ypeak` | +2.35 | −0.240 | PS51 | OK |
| `tongue_lick1_t_peak_ms` | +370.3 | +0.230 | PS55 | OK |
| `tongue_first_peak_t_ms` | +626.2 | +0.206 | PS55 | OK |
| `num_correct_licks_per_trial` | −9.54 | +0.200 | PS47 | OK |
| `tongue_median_vxy_peak_per_trial` | +3164 | +0.190 | PS51 | OK |
| `first_lick_accuracy_all` | −0.473 | −0.188 | PS54 | OK |

**Flagged: 1 / 12 confirmatory pre_post endpoints.**

`latency_hist` is sensitive to dropping PS51 (moderate-severe phenotype):
dropping it shifts the cohort mean by 0.37 SD. The endpoint is a
vector_per_session (KS test on flat per-trial schema per Task 4
implementation note #1) — its per-animal aggregate is mean lick latency per
session, which is much more variable for moderate-severe animals like PS51.
Surface this for Priya scientific review: **does it warrant a phenotype-
stratified analysis at Phase 9.x, or does pooled-cohort interpretation
remain robust?** The pooled effect is small (+0.087 s ≈ +87 ms mean
latency increase) and the LOO-d sign indicates PS51 amplifies rather than
dominates the effect.

---

## Gate 5 — Stats summary figure eyeball (Priya review)

CC produced 76 figures across `pipeline_outputs/stats/figures/` per Task 7
close. Visually highest-impact for paper headlines:

- `headlines/<endpoint>/v3_per_epoch_boxplot.{svg,png}` — the 7 kinematic
  headlines with q_holm asterisk annotations. Sign-flip behavior of
  `tongue_lick1_y_peak` (acute +21.79 / sub_acute −12.16 / chronic −6.45)
  is visible in both V2 (per_bin cohort mean) and V3 (per_epoch boxplot
  medians).
- `headlines/<endpoint>/v1_per_session_recovery.{svg,png}` — cohort scatter
  + LMM fit. Severe-phenotype bimodal recovery is visible as wide CI
  ribbon for late-cohort animals.
- `forest_plots/forest_recovery_pre_vs_*.{svg,png}` — known scale
  limitation (per_epoch_lmm rows share `metric=epoch_coef`, so ms-shift
  endpoints crowd out spatial-scalar endpoints). Top entries (tongue ms
  shifts) still readable.

**Priya verdict line — fill in one of:**

- [ ] **PASS** — figures match scientific expectations; Task 9 PR opens.
- [ ] **ITERATE** — specific issue (note below); CC fixes + re-render; new
      verdict round.
- [ ] **FAIL** — fundamental finding requires Phase 9 scope revision.

**Priya notes:**

```
(Priya fills in here)
```

## Gate 6 — `recovery_trajectories` plot family eyeball (Priya review)

Per-mouse `recovery_trajectories.<endpoint>.{svg,png}` outputs landed at
`pipeline_outputs/spout_behavior/spout_behavior_figures/<animal>/` for the
15-endpoint default list (Task 6 + notebook 15 toggle). Sample-confirmed
PS47 (mild), PS51 (moderate-severe), PS54 (severe) for
`first_lick_accuracy_all` during Task 6 close.

**Priya verdict line — fill in one of:**

- [ ] **PASS** — recovery_trajectories family ready for paper figure tier.
- [ ] **ITERATE** — note below.
- [ ] **FAIL** — re-think the cohort-overlay design (e.g. switch to
      per-phenotype panels).

**Priya notes:**

```
(Priya fills in here)
```

---

## Summary

| gate | owner | result |
|---|---|---|
| 1. Methodology sanity | CC | 7/8 pass + 1 REVIEW (`num_incorrect_licks_per_trial` sign) |
| 2. Internal consistency | CC | 4/5 agree + 1 DIVERGE (expected; `tongue_lick1_t_peak_ms` heavy-tailed → Wilcoxon vs t-test) |
| 3. Permutation reproducibility | CC | ✓ PASS |
| 4. Sensitivity LOO | CC | 1/12 flag (`latency_hist`, PS51-drop |d|=0.37) |
| 5. Stats summary figure eyeball | Priya | pending |
| 6. recovery_trajectories eyeball | Priya | pending |

**Items requiring Priya adjudication before Task 9:**

1. `num_incorrect_licks_per_trial` recovery sign — is positive slope (more
   incorrect licks over time) the scientifically-expected pattern, or does
   CC's naive sign expectation reflect the right scientific frame?
2. `latency_hist` PS51-sensitivity — accept cohort-pooled interpretation
   for Phase 9, defer phenotype-stratified follow-up to Phase 9.x, OR
   re-stratify Phase 9.1 with PS51 isolation flag.
3. Gates 5 + 6 figure eyeballs.

**HARD STOP** awaiting Priya scientific review.

---

## Forward pointers locked in this gate

- The 1 flagged sensitivity finding (`latency_hist`) becomes a candidate
  for Phase 9.x-spatial-stats per-phenotype analysis (moderate-pool n=2
  with PS46 + PS51 per Priya 2026-05-25 expanded scope).
- The 1 DIVERGE consistency finding (`tongue_lick1_t_peak_ms`) is documented
  but does not require action — Wilcoxon was already the canonical kickoff
  choice; the t-test comparison was the audit, not a candidate replacement.

This verdict.md file lands in Task 9's docs commit per the Phase 8a.10
`eb0cd5a` post-hoc convention.
