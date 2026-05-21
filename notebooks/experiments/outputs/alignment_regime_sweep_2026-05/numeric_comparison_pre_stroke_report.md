# Pre-stroke-only numeric alignment-regime comparison

Re-run of the Q72 per-bin numeric comparison restricted to pre-stroke bins only (`bin_end_rel_day <= 0`). All other dimensions identical to Q72.

Generated: 2026-05-21T16:14:16
Wall time: 21.7 min
Detailed rows: 4,368
Cross-animal rows: 1,248
Winner-summary rows: 312

## 1. Cohort-wide per-bodypart winners (pre-stroke bins only)

| bodypart | winning_regime | Pearson | margin_vs_2nd |
|---|---|---|---|
| tongue | spout_centered | 0.9137 | +0.1192 |
| jaw | eye_centered | 0.8585 | +0.0261 |
| nose | eye_centered | 0.8196 | +0.0408 |
| L_whiskers_1 | eye_centered | 0.7370 | +0.0041 |
| L_whiskers_2 | eye_centered | 0.8565 | +0.0279 |
| L_whiskers_3 | eye_centered | 0.7772 | +0.0012 |
| R_whiskers_1 | eye_centered | 0.7679 | +0.0409 |
| R_whiskers_2 | eye_centered | 0.8405 | +0.0304 |
| R_whiskers_3 | eye_centered | 0.7862 | +0.0378 |
| L_eye | eye_affine | 0.9219 | +0.1229 |
| R_eye | eye_affine | 0.7998 | +0.0914 |
| L_spout | spout_centered | 0.9022 | +0.8141 |
| R_spout | spout_centered | 0.9072 | +0.7495 |

## 2. Comparison vs Q72 all-bins

| bodypart | pre-stroke winner | pre Pearson | all-bins winner | all Pearson | agreement |
|---|---|---|---|---|---|
| tongue | spout_centered | 0.9137 | spout_centered | 0.8410 | ✓ |
| jaw | eye_centered | 0.8585 | eye_centered | 0.8479 | ✓ |
| nose | eye_centered | 0.8196 | eye_centered | 0.8130 | ✓ |
| L_whiskers_1 | eye_centered | 0.7370 | eye_centered | 0.7665 | ✓ |
| L_whiskers_2 | eye_centered | 0.8565 | eye_centered | 0.8447 | ✓ |
| L_whiskers_3 | eye_centered | 0.7772 | eye_centered | 0.7748 | ✓ |
| R_whiskers_1 | eye_centered | 0.7679 | eye_centered | 0.7691 | ✓ |
| R_whiskers_2 | eye_centered | 0.8405 | eye_centered | 0.8321 | ✓ |
| R_whiskers_3 | eye_centered | 0.7862 | eye_centered | 0.7915 | ✓ |
| L_eye | eye_affine | 0.9219 | eye_affine | 0.8773 | ✓ |
| R_eye | eye_affine | 0.7998 | eye_affine | 0.7893 | ✓ |
| L_spout | spout_centered | 0.9022 | spout_centered | 0.8596 | ✓ |
| R_spout | spout_centered | 0.9072 | spout_centered | 0.8274 | ✓ |

**13 of 13 bodyparts agree** on cohort-wide winning regime between pre-stroke-only and all-bins.

## 3. Per-phenotype stratification (pre-stroke only)

| phenotype | bodypart | winning_regime | mean Pearson |
|---|---|---|---|
| mild | tongue | spout_centered | 0.8922 |
| mild | jaw | eye_centered | 0.8440 |
| mild | nose | eye_centered | 0.8147 |
| mild | L_whiskers_1 | eye_affine | 0.7183 |
| mild | L_whiskers_2 | eye_centered | 0.8368 |
| mild | L_whiskers_3 | eye_affine | 0.8209 |
| mild | R_whiskers_1 | eye_centered | 0.7300 |
| mild | R_whiskers_2 | eye_centered | 0.8235 |
| mild | R_whiskers_3 | eye_centered | 0.7851 |
| mild | L_eye | eye_affine | 0.9238 |
| mild | R_eye | eye_affine | 0.7517 |
| mild | L_spout | spout_centered | 0.8889 |
| mild | R_spout | spout_centered | 0.9617 |
| mod-severe | tongue | spout_centered | 0.9512 |
| mod-severe | jaw | eye_centered | 0.9232 |
| mod-severe | nose | eye_centered | 0.8368 |
| mod-severe | L_whiskers_1 | eye_centered | 0.8427 |
| mod-severe | L_whiskers_2 | eye_centered | 0.9330 |
| mod-severe | L_whiskers_3 | eye_centered | 0.7886 |
| mod-severe | R_whiskers_1 | eye_rigid | 0.8818 |
| mod-severe | R_whiskers_2 | eye_centered | 0.9027 |
| mod-severe | R_whiskers_3 | eye_centered | 0.7885 |
| mod-severe | L_eye | eye_affine | 0.9561 |
| mod-severe | R_eye | eye_affine | 0.8945 |
| mod-severe | L_spout | spout_centered | 0.8576 |
| mod-severe | R_spout | spout_centered | 0.7330 |
| severe | tongue | spout_centered | 0.9315 |
| severe | jaw | eye_centered | 0.8211 |
| severe | nose | eye_rigid | 0.8339 |
| severe | L_whiskers_1 | eye_rigid | 0.7529 |
| severe | L_whiskers_2 | eye_rigid | 0.8218 |
| severe | L_whiskers_3 | eye_rigid | 0.7551 |
| severe | R_whiskers_1 | eye_affine | 0.7721 |
| severe | R_whiskers_2 | eye_centered | 0.8138 |
| severe | R_whiskers_3 | eye_rigid | 0.7939 |
| severe | L_eye | eye_affine | 0.8737 |
| severe | R_eye | eye_affine | 0.8260 |
| severe | L_spout | spout_centered | 0.9978 |
| severe | R_spout | spout_centered | 0.9611 |

### 3a. Severe-tongue spotlight

| regime | severe-tongue pre-stroke mean Pearson |
|---|---|
| spout_centered | 0.9315 |
| eye_centered | 0.8539 |
| eye_rigid | 0.8010 |
| eye_affine | 0.7935 |

Severe-cohort tongue pre-stroke winner: **spout_centered**.

**Hypothesis confirmed.** Pre-stroke severe-cohort tongue prefers spout_centered (matches mild/mod-severe + cohort-wide). The all-bins severe-tongue → eye_centered shift is therefore a post-stroke phenotype effect — NOT a question about correct centering choice. Phase 9.1 phenotype-pooled tongue analysis can keep spout_centered for cohort consistency; the post-stroke tongue-tracking degradation in severe animals is itself a feature to characterize.


## 4. Cross-animal heterogeneity (pre-stroke bins)

| bodypart | scope | tg | bin | pearson_winner | eye_cent | spout | affine | rigid | margin |
|---|---|---|---|---|---|---|---|---|---|
| L_eye | tone_aligned | L | -3..-2 | eye_affine | 0 | 0 | 4 | 1 | +0.2773 |
| L_eye | whole_session | all | -3..-2 | eye_affine | 0 | 0 | 5 | 0 | +0.2895 |
| R_eye | tone_aligned | L | -1..0 | eye_affine | 0 | 0 | 4 | 1 | +0.0123 |
| L_eye | tone_aligned | all | -3..-2 | eye_affine | 0 | 0 | 4 | 1 | +0.2594 |
| R_eye | whole_session | all | -1..0 | eye_affine | 0 | 0 | 5 | 0 | +0.0677 |
| R_eye | tone_aligned | R | -1..0 | eye_affine | 0 | 0 | 3 | 2 | +0.0150 |
| R_eye | tone_aligned | all | -1..0 | eye_affine | 0 | 0 | 4 | 1 | +0.0127 |
| R_eye | tone_aligned | R | -3..-2 | eye_affine | 1 | 0 | 4 | 0 | +0.1603 |
| R_eye | tone_aligned | L | -5..-4 | eye_affine | 0 | 0 | 4 | 0 | +0.0919 |
| L_whiskers_3 | whole_session | all | -3..-2 | eye_affine | 1 | 0 | 3 | 1 | +0.0470 |
| L_eye | whole_session | all | -1..0 | eye_affine | 1 | 0 | 2 | 2 | +0.0494 |
| jaw | whole_session | all | -3..-2 | eye_centered | 1 | 1 | 2 | 1 | +0.0121 |
| jaw | tone_aligned | all | -3..-2 | eye_centered | 1 | 1 | 1 | 2 | +0.0200 |
| R_eye | tone_aligned | R | -5..-4 | eye_affine | 0 | 0 | 4 | 0 | +0.1080 |
| R_whiskers_2 | tone_aligned | L | -1..0 | eye_centered | 1 | 0 | 2 | 2 | +0.0590 |
| L_whiskers_2 | whole_session | all | -5..-4 | eye_affine | 0 | 0 | 4 | 0 | +0.0313 |
| L_whiskers_2 | whole_session | all | -3..-2 | eye_centered | 1 | 1 | 0 | 3 | +0.0129 |
| L_whiskers_3 | tone_aligned | L | -3..-2 | eye_affine | 1 | 0 | 2 | 2 | +0.0536 |
| R_whiskers_2 | whole_session | all | -3..-2 | eye_centered | 1 | 0 | 2 | 2 | +0.0476 |
| R_whiskers_3 | tone_aligned | R | -5..-4 | eye_affine | 0 | 0 | 3 | 1 | +0.0150 |

### Q72-vs-pre-stroke heterogeneity check
The Q72 all-bins report flagged jaw bins 3..4 / 5..6 / 13..14 + L_whiskers_1 bin 3..4 as having animals preferring eye_affine or eye_rigid over the cohort-wide eye_centered winner. Those bins are POST-stroke and therefore absent from this pre-stroke report. The list above shows whether any pre-stroke bins show similar heterogeneity — if absent, the Q72 heterogeneity is a post-stroke-specific signal.
