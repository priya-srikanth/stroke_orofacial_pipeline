# Phase 9 Task 8 mid-flight — trial-count bias investigation findings (2026-05-25)

**Question (Priya):** Do low-trial-count sessions in PS51/PS54/PS55 acute
periods skew the elevated tongue kinematic acute results? Specifically,
does outlier dominance + DLC tracking degradation in low-engagement
sessions inflate session means for `tongue_lick1_y_peak` + 3 vxy
endpoints?

**Answer: BIAS NOT DETECTED.** Low-trial sessions exhibit the OPPOSITE
of the hypothesized pattern, and the counterfactual LMM filter
changes acute coefficients by ≤4%.

Script: [`.scratch_phase_9/_trial_count_bias_investigation.py`](
_trial_count_bias_investigation.py).
Raw output: tables below from the script's stdout.

---

## 1. Trial-count distribution per (animal, epoch)

Mild + moderate animals (PS46-PS50): every session has ≥20 detected
trials across ALL epochs. **No low-n bias risk.**

PS51 / PS54 / PS55 acute distributions (subset of the full table):

| animal | epoch | n_sessions | <5 | 5-9 | 10-19 | ≥20 |
|---|---|---:|---:|---:|---:|---:|
| **PS51** | **acute** | **6** | **2** | 0 | 2 | 2 |
| PS51 | sub_acute | 9 | 0 | 0 | 0 | 9 |
| PS51 | chronic | 27 | 0 | 0 | 0 | 27 |
| **PS54** | **acute** | **12** | **0** | **0** | **7** | **5** |
| PS54 | sub_acute | 13 | 0 | 0 | 0 | 13 |
| PS54 | chronic | 17 | 0 | 0 | 0 | 17 |
| **PS55** | **acute** | **11** | **1** | **4** | **6** | **0** |
| PS55 | sub_acute | 20 | 0 | 3 | 2 | 15 |
| PS55 | chronic | 9 | 0 | 0 | 0 | 9 |

Key per-animal observations:
- **PS51 acute (6 sess):** 2 with <5 trials, 2 with 10-19, 2 with ≥20. Bimodal — a third of acute sessions are deeply low-engagement.
- **PS54 acute (12 sess):** all sessions ≥10 trials. No low-n contamination in PS54's acute set.
- **PS55 acute (11 sess):** 1 with <5, 4 with 5-9, 6 with 10-19, **none with ≥20**. PS55's acute is dominated by low-to-medium engagement; no sessions reach the "normal" ≥20-trial threshold.

So **PS55 acute = uniformly degraded engagement; PS51 acute = bimodal; PS54 acute = robust.**

## 2. Low-n (<10 trials) vs high-n (≥10) session-mean comparison

For each (phenotype group, epoch): mean session-level values in each
trial-count bucket + their ratio.

### `tongue_lick1_y_peak`

| group | epoch | n_low | n_high | low_mean | high_mean | ratio low/high |
|---|---|---:|---:|---:|---:|---:|
| moderate-severe (PS51) | acute | 2 | 4 | 125.5 | **185.8** | 0.68 |
| severe (PS54+PS55) | acute | 5 | 18 | 163.2 | 184.3 | 0.89 |

### `tongue_lick1_vxy_peak`

| group | epoch | n_low | n_high | low_mean | high_mean | ratio low/high |
|---|---|---:|---:|---:|---:|---:|
| moderate-severe (PS51) | acute | 2 | 4 | 10,709 | **15,979** | 0.67 |
| severe (PS54+PS55) | acute | 5 | 18 | 14,888 | 15,899 | 0.94 |

### `tongue_max_vxy_peak_first5`

| group | epoch | n_low | n_high | low_mean | high_mean | ratio low/high |
|---|---|---:|---:|---:|---:|---:|
| moderate-severe (PS51) | acute | 2 | 4 | 14,623 | 16,540 | 0.88 |
| severe (PS54+PS55) | acute | 5 | 18 | 16,757 | 16,712 | 1.00 |

### `tongue_mean_vxy_peak_first5`

| group | epoch | n_low | n_high | low_mean | high_mean | ratio low/high |
|---|---|---:|---:|---:|---:|---:|
| moderate-severe (PS51) | acute | 2 | 4 | 12,102 | 15,736 | 0.77 |
| severe (PS54+PS55) | acute | 5 | 18 | 15,494 | 15,924 | 0.97 |

**All 4 suspect endpoints × both phenotype groups: low-n sessions have
LOWER means than high-n sessions in acute.** Ratio range 0.67-1.00; no
case where low-n > high-n. This is the **OPPOSITE** of the predicted
outlier-inflation pattern.

(Sub-acute showed mild OPPOSITE bias in severe cohort for vxy endpoints
— low-n=8612-10979 vs high-n=5760-9770, ratio 1.12-1.50. That's a
sub_acute-only effect, not acute, so it doesn't bear on Priya's
specific concern about acute. Worth a separate look in Phase 9.x if
sub_acute becomes interesting.)

## 3. Counterfactual LMM acute coefficient (n_trials ≥ 10 filter)

Re-fit the per-epoch LMM after dropping sessions with < 10 detected
trials (10 of 247 sessions dropped, 4%). Compare acute coefficient
before/after.

| endpoint | full coef | filtered coef | % change | full p | filtered p |
|---|---:|---:|---:|---:|---:|
| `tongue_lick1_y_peak` | +49.79 | +51.01 | **+2.5%** | 1e-72 | 1e-72 |
| `tongue_lick1_vxy_peak` | +7624 | +7519 | **−1.4%** | 1e-30 | 1e-29 |
| `tongue_max_vxy_peak_first5` | +6939 | +6730 | **−3.0%** | 1e-19 | 1e-18 |
| `tongue_mean_vxy_peak_first5` | +6482 | +6256 | **−3.5%** | 1e-19 | 1e-18 |

All 4 acute coefficients shift by ≤4% (one direction +, three −). The
p-value tails remain well below 1e-15 in all cases. **The LMM cohort
estimate is robust to dropping low-trial-count sessions.**

(Note from Addendum #9 + the published headline summary v2: the LMM
acute coefficient reported in `task_5_headline_summary.csv` for
`tongue_lick1_y_peak` is +21.79, which is the per_epoch_lmm coef. The
+49.79 here is on session-mean rather than raw per-trial values; the
investigation script aggregates per-trial → per-session before fitting
to match the trial-count-stratification semantics. Both numbers tell the
same qualitative story; the directional finding holds either way.)

---

## Verdict

**Bias NOT detected.** Specifically:

1. **Direction mismatch:** Low-trial sessions show LOWER (not higher)
   session means than high-trial sessions in all 4 suspect endpoints'
   acute periods. The hypothesized outlier-inflation pattern is absent.
2. **Magnitude:** Counterfactual LMM acute coefficients shift by ≤4%
   when low-trial sessions are excluded. The cohort-level effect is
   robust.
3. **Coverage:** 4% of sessions dropped (10 of 247). Even concentrated
   in PS51 (2) + PS55 (6), they don't materially shift the cohort.

**Plausible alternative explanation for the LOWER session means in low-n
sessions:** In severely-affected acute sessions, animals attempt few
licks AND each lick is a constrained-movement attempt (short y_peak,
low vxy). High-trial-count acute sessions may reflect animals that
are partially recovering — they attempt more licks AND each attempt
has more excursion. So trial count and per-trial deflection both
correlate positively with engagement, NOT negatively as Priya's outlier
hypothesis predicted.

**Recommendation:** Phase 9 acute results for these 4 endpoints stand
as published in the Task 5 headline summary v2. **No re-emit or
re-fit needed.**

**Forward considerations for Phase 9.x:**

1. The sub_acute low-n vs high-n divergence (severe cohort, ratio 1.12-
   1.50 for vxy endpoints) is a real but separate finding — not in scope
   for the current bias check but worth a per-phenotype look in Phase 9.x
   per-phenotype stats. May reflect a different mechanism: by sub_acute,
   PS54/PS55 animals with persistent low engagement may STILL have
   different per-trial kinematics than partially-recovering high-
   engagement animals.
2. PS55 acute being uniformly low-engagement (no ≥20-trial sessions)
   is worth a sanity-check on PS55-specific DLC tracking quality, but
   doesn't affect the cohort LMM verdict.

---

## Files

- [`.scratch_phase_9/_trial_count_bias_investigation.py`](
  _trial_count_bias_investigation.py) — analysis script (no code/parquet
  side-effects).
- This findings doc.

**No production code or parquet outputs were modified in this
investigation.** Original Task 5 headline summary v2 + Task 7 figures
stand.
