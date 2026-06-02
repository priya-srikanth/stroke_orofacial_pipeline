# Chore kickoff — comprehensive stats suite for ALL phenotype-pooled endpoints

**Status:** LOCKED spec (Priya, 2026-06-01). Not yet implemented.
**Motivation:** the `phase_aligned_endpoints` (q13b) stats currently carry ONLY a
per-ANIMAL paired Wilcoxon (n=1–4 animals/phenotype → p-floor 0.5, structurally
non-significant), so they don't reflect the visually-clear effects. The
*trajectories* already have the full powered suite; the endpoints (and the other
pooled families) need to be brought up to it, on the pre-stroke-normalized metric
at session grain.

## Goal
For EVERY endpoint behind a figure in `stats/figures/phenotype_pooled/`, compute
a consistent stats suite on the **pre-stroke-baseline-normalized Δ** metric, and
collect it into ONE spreadsheet per scope at
`stats/results/phenotype_pooled/<3_tier|4_tier>/` (the consolidated-layout
request, 2026-06-01).

## Comparison structure (Priya 2026-06-01)
Every test is a **post-epoch vs pre** contrast: **acute vs pre, sub_acute vs pre,
chronic vs pre** — 3 contrasts per cell — run for **BOTH scopes (3_tier AND
4_tier)**. `pre` is always the reference. BH-FDR applied within family per scope.

**Split by trial CUE side** (Tone_L vs Tone_R): the `side` dimension is the trial's
cued spout (already the per-trial `side` column for the DLC endpoints; relabeled
ipsi/contra on the all-L cohort). So each cell is also split by cue side.
**Exception:** metrics that are inherently cross-cue (d′, criterion_c — SDT pools
hits on one cue + false alarms on the other per session) cannot split by cue side;
either add a per-cue-side conditional variant or keep them cross-cue and flag it.

## The suite (per Priya, 2026-06-01)
Per (phenotype × side × endpoint × post_epoch ∈ {acute, sub_acute, chronic}) cell,
for each scope ∈ {3_tier, 4_tier}:

1. **Per-animal paired Wilcoxon** — pre vs post, per-animal aggregate (the
   existing conservative test; keep for continuity).
2. **Session-wise Mann-Whitney U** — unpaired, per-SESSION grain (raw n; pseudo-
   replication caveat noted in output).
3. **LMM** — `value ~ epoch + (1|animal)`, per-SESSION grain (animal random
   effect; the rigorous powered test).
4. **Bootstrap effect-CI** — resampling unit = **SESSIONS** (Priya 2026-06-01:
   resample sessions with replacement), 95% CI of the post−pre Δ + `excludes_zero`
   flag. (The existing trajectory bootstrap resamples ANIMALS — move the unit to
   sessions for power, matching the session-grain direction.)
5. **Cluster permutation** — TRAJECTORIES ONLY (clusters across phase bins).
   N/A for scalar endpoints (no phase dimension).

**Skipped:** per-trial MWU (Priya's call).

All tests on the **Δ-from-pre-stroke-baseline** value (`difference_from_baseline`
per (animal, side, endpoint)); BH-FDR within family.

## Scope — every pooled family
- **phase_aligned_endpoints** (peak_angle_deg, signed_angle_at_max_abs,
  signed_x_at_max_abs) — scalar suite (1–4).
- **phase_aligned_endpoints_all_licks** (I) — scalar suite, per-lick grain.
- **phase_aligned_trajectories** + **_all_licks** — full suite incl. cluster
  permutation (already present for first-lick; verify all-licks).
- **per-endpoint SCALARS** (the V4/V5 `tongue_*`, `jaw_*`, and **spout-behavior**:
  `d_prime`, `criterion_c`, `first_lick_accuracy_all`, `num_*_licks_per_trial`,
  etc.) — scalar suite (1–4). Priya explicitly wants d′ + first-lick-accuracy.
- **wasserstein_recovery** + **normalized_wasserstein_recovery** — scalar suite
  (1–4) on the per-session W-2 (already persisted as
  `wasserstein_recovery_per_session.csv`).

## Existing machinery to reuse (do NOT reinvent)
- `stroke_orofacial.stats.models`: `fit_paired_pre_post_wilcoxon`,
  `fit_per_epoch_lmm` (+ the MWU used by `compute_trajectory_mwu_stats`).
- `figures/phase_aligned_trajectories.py`: `compute_trajectory_{wilcoxon,mwu,lmm}_stats`,
  `compute_trajectory_bootstrap_{pre,effect}_ci` — TEMPLATES for the per-bin
  versions; the scalar engine iterates over endpoints instead of phase_bins.
- `stats/normalization.py`: `difference_from_baseline` (the Δ metric),
  `per_animal_baseline_stats`.
- Per-session inputs: scalar parquets (`stats/inputs/<ep>/`), the q13b per-session
  endpoint long-form, the wasserstein per-session CSV.

## Deliverable layout
`stats/results/phenotype_pooled/<scope>/pooled_phenotype_stats.csv` (or a small
set of sheets, e.g. one per test if a single wide sheet is unwieldy):
rows = family × endpoint × side × post_epoch;
columns = wilcoxon_{stat,p,p_fdr}, mwu_session_{p,p_fdr}, lmm_{coef,p,p_fdr},
boot_effect_{median,ci_lo,ci_hi,excludes_zero}, n_sessions, n_animals, status.

## Phasing (suggested)
1. **Scalar stats engine** in `src/.../stats/` (the 4 scalar tests on Δ, BH-FDR),
   unit-tested against the existing trajectory functions for a shared endpoint.
2. **Session-resampled bootstrap** (hierarchical) helper.
3. **Driver** that runs the engine over every pooled family + writes the per-scope
   consolidated sheet.
4. **Wire** into q13b (replace/augment the per-animal-only stats) + add a spatial +
   per-endpoint-scalar pass.
5. Spot-check: severe / mod-severe cells that are visually clear should now show
   significant LMM / session-MWU / bootstrap-excludes-zero.

## Resolved at spec time
- **Bootstrap resampling unit = sessions** (resample sessions with replacement).

## Open question for Priya at kickoff
- Single wide consolidated sheet vs one sheet per test under `<scope>/`?
