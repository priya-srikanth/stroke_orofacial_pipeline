# Per-bin numeric alignment-regime comparison (Q70/Q71 follow-up)

Generated: 2026-05-21T15:25:13
Wall time: 26.1 min
Detailed rows: 16,432
Cross-animal rows: 4,576
Winner-summary rows: 1,144

## Methodology recap

For each (animal, bodypart, scope, trial_group, rel_day_bin, regime), the per-session spatial histograms (under the scope-appropriate frame filter × regime transform × likelihood-filter) are pooled across the bin's sessions. Within-bin pairwise Pearson r + JS divergence quantify cross-session stability under that regime; diff-vs-baseline (proportion-normalized) quantifies the bin's distributional shift from pre-stroke. Cross-animal aggregation produces mean Pearson + mean rank across the 4 regimes.

## Cohort-wide per-bodypart winners (pooled across all bins)

| bodypart | regime | mean Pearson | mean JS | mean rank | n_rows |
|---|---|---|---|---|---|
| tongue | spout_centered | 0.8410 | 0.1335 | 1.81 | 316 |
| tongue | eye_centered | 0.7772 | 0.1604 | 2.34 | 316 |
| tongue | eye_rigid | 0.7360 | 0.1826 | 2.77 | 316 |
| tongue | eye_affine | 0.7316 | 0.1878 | 3.08 | 316 |
| jaw | eye_centered | 0.8479 | 0.0976 | 1.91 | 316 |
| jaw | eye_rigid | 0.8275 | 0.1095 | 2.27 | 316 |
| jaw | eye_affine | 0.7840 | 0.1339 | 2.68 | 316 |
| jaw | spout_centered | 0.7027 | 0.1850 | 3.14 | 316 |
| nose | eye_centered | 0.8130 | 0.1177 | 1.75 | 316 |
| nose | eye_rigid | 0.7704 | 0.1409 | 2.22 | 316 |
| nose | eye_affine | 0.7354 | 0.1635 | 2.63 | 316 |
| nose | spout_centered | 0.5950 | 0.2496 | 3.39 | 316 |
| L_whiskers_1 | eye_centered | 0.7665 | 0.1550 | 1.92 | 316 |
| L_whiskers_1 | eye_rigid | 0.7392 | 0.1734 | 2.31 | 316 |
| L_whiskers_1 | eye_affine | 0.7202 | 0.1900 | 2.32 | 316 |
| L_whiskers_1 | spout_centered | 0.4953 | 0.3657 | 3.45 | 316 |
| L_whiskers_2 | eye_centered | 0.8447 | 0.1042 | 1.98 | 316 |
| L_whiskers_2 | eye_rigid | 0.8273 | 0.1158 | 2.25 | 316 |
| L_whiskers_2 | eye_affine | 0.7690 | 0.1588 | 2.47 | 316 |
| L_whiskers_2 | spout_centered | 0.6093 | 0.2826 | 3.29 | 316 |
| L_whiskers_3 | eye_centered | 0.7748 | 0.1517 | 2.09 | 316 |
| L_whiskers_3 | eye_rigid | 0.7648 | 0.1600 | 2.25 | 316 |
| L_whiskers_3 | eye_affine | 0.7297 | 0.1912 | 2.31 | 316 |
| L_whiskers_3 | spout_centered | 0.5268 | 0.3496 | 3.35 | 316 |
| R_whiskers_1 | eye_centered | 0.7691 | 0.1498 | 1.89 | 316 |
| R_whiskers_1 | eye_rigid | 0.7393 | 0.1730 | 2.17 | 316 |
| R_whiskers_1 | eye_affine | 0.6872 | 0.2154 | 2.50 | 316 |
| R_whiskers_1 | spout_centered | 0.4735 | 0.3969 | 3.44 | 316 |
| R_whiskers_2 | eye_centered | 0.8321 | 0.1124 | 1.83 | 316 |
| R_whiskers_2 | eye_rigid | 0.8039 | 0.1307 | 2.26 | 316 |
| R_whiskers_2 | eye_affine | 0.7419 | 0.1757 | 2.65 | 316 |
| R_whiskers_2 | spout_centered | 0.5923 | 0.2960 | 3.27 | 316 |
| R_whiskers_3 | eye_centered | 0.7915 | 0.1446 | 1.85 | 316 |
| R_whiskers_3 | eye_rigid | 0.7603 | 0.1655 | 2.19 | 316 |
| R_whiskers_3 | eye_affine | 0.6969 | 0.2173 | 2.65 | 316 |
| R_whiskers_3 | spout_centered | 0.5122 | 0.3740 | 3.31 | 316 |
| L_eye | eye_affine | 0.8773 | 0.1107 | 1.30 | 316 |
| L_eye | eye_rigid | 0.7060 | 0.2417 | 2.18 | 316 |
| L_eye | eye_centered | 0.6565 | 0.2779 | 2.60 | 316 |
| L_eye | spout_centered | 0.1254 | 0.8108 | 3.91 | 316 |
| R_eye | eye_affine | 0.7893 | 0.1732 | 1.27 | 316 |
| R_eye | eye_rigid | 0.6239 | 0.3076 | 2.19 | 316 |
| R_eye | eye_centered | 0.5612 | 0.3559 | 2.74 | 316 |
| R_eye | spout_centered | 0.1025 | 0.8475 | 3.81 | 316 |
| L_spout | spout_centered | 0.8596 | 0.1326 | 1.01 | 316 |
| L_spout | eye_centered | 0.0984 | 0.8667 | 2.74 | 316 |
| L_spout | eye_rigid | 0.0845 | 0.8835 | 3.10 | 316 |
| L_spout | eye_affine | 0.0657 | 0.9091 | 3.15 | 316 |
| R_spout | spout_centered | 0.8274 | 0.1565 | 1.04 | 316 |
| R_spout | eye_rigid | 0.1250 | 0.8520 | 2.85 | 316 |
| R_spout | eye_centered | 0.0886 | 0.8771 | 2.75 | 316 |
| R_spout | eye_affine | 0.0733 | 0.9044 | 3.37 | 316 |

## Cohort-wide per-bodypart winning regime (Pearson)

| bodypart | winning_regime | Pearson | margin_vs_2nd |
|---|---|---|---|
| tongue | spout_centered | 0.8410 | +0.0638 |
| jaw | eye_centered | 0.8479 | +0.0204 |
| nose | eye_centered | 0.8130 | +0.0427 |
| L_whiskers_1 | eye_centered | 0.7665 | +0.0274 |
| L_whiskers_2 | eye_centered | 0.8447 | +0.0174 |
| L_whiskers_3 | eye_centered | 0.7748 | +0.0100 |
| R_whiskers_1 | eye_centered | 0.7691 | +0.0299 |
| R_whiskers_2 | eye_centered | 0.8321 | +0.0282 |
| R_whiskers_3 | eye_centered | 0.7915 | +0.0312 |
| L_eye | eye_affine | 0.8773 | +0.1714 |
| R_eye | eye_affine | 0.7893 | +0.1653 |
| L_spout | spout_centered | 0.8596 | +0.7612 |
| R_spout | spout_centered | 0.8274 | +0.7024 |

## Time-course: regime preference pre vs post stroke

| bodypart | epoch | winning_regime | mean Pearson |
|---|---|---|---|
| tongue | pre | spout_centered | 0.9137 |
| tongue | post | spout_centered | 0.8147 |
| jaw | pre | eye_centered | 0.8585 |
| jaw | post | eye_centered | 0.8441 |
| nose | pre | eye_centered | 0.8196 |
| nose | post | eye_centered | 0.8107 |
| L_whiskers_1 | pre | eye_centered | 0.7370 |
| L_whiskers_1 | post | eye_centered | 0.7772 |
| L_whiskers_2 | pre | eye_centered | 0.8565 |
| L_whiskers_2 | post | eye_centered | 0.8404 |
| L_whiskers_3 | pre | eye_centered | 0.7772 |
| L_whiskers_3 | post | eye_centered | 0.7740 |
| R_whiskers_1 | pre | eye_centered | 0.7679 |
| R_whiskers_1 | post | eye_centered | 0.7696 |
| R_whiskers_2 | pre | eye_centered | 0.8405 |
| R_whiskers_2 | post | eye_centered | 0.8290 |
| R_whiskers_3 | pre | eye_centered | 0.7862 |
| R_whiskers_3 | post | eye_centered | 0.7934 |
| L_eye | pre | eye_affine | 0.9219 |
| L_eye | post | eye_affine | 0.8612 |
| R_eye | pre | eye_affine | 0.7998 |
| R_eye | post | eye_affine | 0.7854 |
| L_spout | pre | spout_centered | 0.9022 |
| L_spout | post | spout_centered | 0.8441 |
| R_spout | pre | spout_centered | 0.9072 |
| R_spout | post | spout_centered | 0.7986 |

## Per-bodypart regime SHIFT (pre vs post winner difference)

(no bodypart shifts winning regime between pre and post)

## Phenotype stratification (post-stroke only)

| phenotype | bodypart | winning_regime | mean Pearson |
|---|---|---|---|
| mild | tongue | spout_centered | 0.9151 |
| mild | jaw | eye_centered | 0.8663 |
| mild | nose | eye_centered | 0.8432 |
| mild | L_whiskers_1 | eye_centered | 0.8202 |
| mild | L_whiskers_2 | eye_centered | 0.8939 |
| mild | L_whiskers_3 | eye_centered | 0.8428 |
| mild | R_whiskers_1 | eye_centered | 0.7852 |
| mild | R_whiskers_2 | eye_centered | 0.8613 |
| mild | R_whiskers_3 | eye_centered | 0.8142 |
| mild | L_eye | eye_affine | 0.9157 |
| mild | R_eye | eye_affine | 0.7873 |
| mild | L_spout | spout_centered | 0.8272 |
| mild | R_spout | spout_centered | 0.8323 |
| mod-severe | tongue | spout_centered | 0.8567 |
| mod-severe | jaw | eye_centered | 0.8762 |
| mod-severe | nose | eye_centered | 0.8299 |
| mod-severe | L_whiskers_1 | eye_centered | 0.8277 |
| mod-severe | L_whiskers_2 | eye_centered | 0.8667 |
| mod-severe | L_whiskers_3 | eye_affine | 0.8269 |
| mod-severe | R_whiskers_1 | eye_centered | 0.8158 |
| mod-severe | R_whiskers_2 | eye_centered | 0.8598 |
| mod-severe | R_whiskers_3 | eye_centered | 0.8460 |
| mod-severe | L_eye | eye_affine | 0.9023 |
| mod-severe | R_eye | eye_affine | 0.8774 |
| mod-severe | L_spout | spout_centered | 0.8483 |
| mod-severe | R_spout | spout_centered | 0.7905 |
| severe | tongue | eye_centered | 0.6074 |
| severe | jaw | eye_centered | 0.7764 |
| severe | nose | eye_centered | 0.7377 |
| severe | L_whiskers_1 | eye_centered | 0.6574 |
| severe | L_whiskers_2 | eye_centered | 0.7252 |
| severe | L_whiskers_3 | eye_centered | 0.6265 |
| severe | R_whiskers_1 | eye_centered | 0.6999 |
| severe | R_whiskers_2 | eye_centered | 0.7455 |
| severe | R_whiskers_3 | eye_centered | 0.7089 |
| severe | L_eye | eye_affine | 0.7306 |
| severe | R_eye | eye_affine | 0.6961 |
| severe | L_spout | spout_centered | 0.8689 |
| severe | R_spout | spout_centered | 0.7493 |

## Cross-animal heterogeneity flags (post-stroke bins)

(bp, bin) combinations where the regime winner is NOT cohort-uniform — i.e., n_animals_winning is split between regimes. Top 20 by max-split.

| bodypart | scope | tg | bin | pearson_winner | eye_cent | spout | affine | rigid | margin |
|---|---|---|---|---|---|---|---|---|---|
| L_eye | tone_aligned | R | 13..14 | eye_affine | 0 | 0 | 4 | 1 | +0.1440 |
| jaw | whole_session | all | 3..4 | eye_rigid | 0 | 0 | 3 | 2 | +0.0466 |
| L_eye | tone_aligned | R | 5..6 | eye_affine | 0 | 0 | 4 | 1 | +0.2761 |
| L_eye | tone_aligned | R | 7..8 | eye_affine | 0 | 0 | 5 | 0 | +0.2092 |
| L_eye | tone_aligned | all | 11..12 | eye_affine | 0 | 0 | 5 | 0 | +0.0744 |
| R_whiskers_2 | whole_session | all | 7..8 | eye_centered | 0 | 0 | 3 | 2 | +0.0067 |
| L_eye | tone_aligned | all | 5..6 | eye_affine | 0 | 0 | 4 | 1 | +0.2745 |
| jaw | tone_aligned | all | 13..14 | eye_rigid | 0 | 0 | 1 | 4 | +0.0166 |
| L_eye | tone_aligned | all | 13..14 | eye_affine | 0 | 0 | 4 | 1 | +0.1348 |
| jaw | tone_aligned | R | 5..6 | eye_rigid | 0 | 0 | 2 | 3 | +0.0046 |
| jaw | tone_aligned | R | 13..14 | eye_rigid | 0 | 0 | 1 | 4 | +0.0307 |
| jaw | tone_aligned | all | 3..4 | eye_rigid | 0 | 0 | 3 | 2 | +0.0330 |
| L_eye | whole_session | all | 13..14 | eye_affine | 0 | 0 | 5 | 0 | +0.1858 |
| L_eye | tone_aligned | all | 7..8 | eye_affine | 0 | 0 | 4 | 1 | +0.2069 |
| L_eye | whole_session | all | 11..12 | eye_affine | 0 | 0 | 5 | 0 | +0.0639 |
| L_whiskers_2 | whole_session | all | 5..6 | eye_affine | 0 | 0 | 4 | 1 | +0.0353 |
| L_whiskers_1 | tone_aligned | L | 3..4 | eye_rigid | 0 | 0 | 4 | 1 | +0.0241 |
| L_eye | tone_aligned | L | 13..14 | eye_affine | 0 | 0 | 5 | 0 | +0.1234 |
| L_eye | tone_aligned | L | 11..12 | eye_affine | 0 | 0 | 5 | 0 | +0.0896 |
| L_whiskers_1 | whole_session | all | 5..6 | eye_affine | 0 | 0 | 3 | 2 | +0.0152 |

## Scale-drift signature: PS51/PS54/PS55 vs PS46-PS50

| bodypart | cohort | winning_regime | mean Pearson |
|---|---|---|---|
| tongue | PS46-50 (dense) | spout_centered | 0.9123 |
| tongue | PS51/54/55 (sparse) | spout_centered | 0.6763 |
| jaw | PS46-50 (dense) | eye_centered | 0.8785 |
| jaw | PS51/54/55 (sparse) | eye_centered | 0.7953 |
| nose | PS46-50 (dense) | eye_centered | 0.8501 |
| nose | PS51/54/55 (sparse) | eye_centered | 0.7548 |
| L_whiskers_1 | PS46-50 (dense) | eye_centered | 0.8320 |
| L_whiskers_1 | PS51/54/55 (sparse) | eye_centered | 0.6997 |
| L_whiskers_2 | PS46-50 (dense) | eye_centered | 0.8976 |
| L_whiskers_2 | PS51/54/55 (sparse) | eye_centered | 0.7592 |
| L_whiskers_3 | PS46-50 (dense) | eye_centered | 0.8453 |
| L_whiskers_3 | PS51/54/55 (sparse) | eye_centered | 0.6730 |
| R_whiskers_1 | PS46-50 (dense) | eye_centered | 0.8050 |
| R_whiskers_1 | PS51/54/55 (sparse) | eye_centered | 0.7194 |
| R_whiskers_2 | PS46-50 (dense) | eye_centered | 0.8734 |
| R_whiskers_2 | PS51/54/55 (sparse) | eye_centered | 0.7661 |
| R_whiskers_3 | PS46-50 (dense) | eye_centered | 0.8318 |
| R_whiskers_3 | PS51/54/55 (sparse) | eye_centered | 0.7389 |
| L_eye | PS46-50 (dense) | eye_affine | 0.9235 |
| L_eye | PS51/54/55 (sparse) | eye_affine | 0.7729 |
| R_eye | PS46-50 (dense) | eye_affine | 0.8114 |
| R_eye | PS51/54/55 (sparse) | eye_affine | 0.7487 |
| L_spout | PS46-50 (dense) | spout_centered | 0.8314 |
| L_spout | PS51/54/55 (sparse) | spout_centered | 0.8622 |
| R_spout | PS46-50 (dense) | spout_centered | 0.8154 |
| R_spout | PS51/54/55 (sparse) | spout_centered | 0.7748 |

## Convergence with 2026-04-19 cohort-wide sweep

The 2026-04-19 sweep at `notebooks/experiments/outputs/alignment_sweep/summary.txt` computed cohort-wide regime preferences pooled across ALL post-stroke sessions (no per-bin granularity). The cohort-wide-winners table above (pooled across all bins, all 8 animals) is the direct per-bin extension's analog. Compare the regime winner and margin per bodypart; agreement suggests the per-bin metric is a refinement, not a contradiction.
