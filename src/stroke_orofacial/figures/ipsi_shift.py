"""Tongue ipsi-shift figure families (Q-lock 8) — delta-from-baseline trajectories.

Phase 9.1 Task 5. Targets memory finding #6 (post-stroke tongue direction-
sensitive endpoints x/angle show ipsi-contra asymmetry; amplitude endpoint y
does not). Two families render the same scientific question at complementary
granularities.

- **Family 8.1** — delta tongue angle, 3 endpoint sub-families
  (``tongue_lick1_angle_at_ypeak``, ``tongue_lick2_angle_at_ypeak``,
  ``tongue_median_angle_at_peak_velocity``); ipsi/contra side-split; ~3 figures
  at ``pipeline_outputs/stats/figures/phenotype_pooled_ipsi_shift/angle/``.
- **Family 8.2** — continuous tone-aligned tongue x trajectory (per-frame DLC,
  NOT x-at-ypeak); ipsi/contra side-split; 1-4 figures (layout locked at
  Task 0.5) at ``pipeline_outputs/stats/figures/phenotype_pooled_ipsi_shift/x_trajectory/``.
  Likely paper-narrative figure.

Existing-code reuse (mandatory per Q-lock 8 — Phase 9.1 does NOT re-author
trajectory loading or mean ± SEM rendering):

- ``dlc_kinematics.mean_sem_visual.build_mean_sem_cohort`` for tone-aligned
  mean ± SEM trajectory loading from
  ``pipeline_outputs/dlc_analysis/interpolated_traces/<bp>/<animal>/<date>.parquet``.
- ``dlc_kinematics.tongue_angle_cohort._plot_tone_aligned_session_overlays`` for
  thin per-session background overlay rendering.
- ``dlc_kinematics.tongue_angle_cohort._plot_tone_aligned_binned_overlays`` for
  foreground mean ± SEM binned rendering.
- ``dlc_kinematics.tongue_pertrial`` ``tongue_lick_t_peaks_bylick`` primitive
  for per-lick peak-time data (Family 8.1).
- ``AnimalInfo.mouse_side_to_ipsi_contra`` for axis labeling (Q-lock 4).
- ``configs/defaults.yaml::dlc_kinematics.mean_sem_visual.*`` for time-binning.

Locked design elements (Q-lock 8, both families):

- Delta-from-baseline normalization at every tone-aligned bin (per-bin
  trajectory subtraction; distinct from Phase 9 Addendum #6 per-trial scalar
  subtraction). Per-animal pre-stroke side-matched baseline trajectory →
  per-session delta(t) → phenotype-pool within (phenotype, epoch, side).
- Pre-epoch trace REQUIRED as noise-floor reference in every panel; y=0
  reference line drawn explicitly.
- Two-layer rendering: thin α≈0.2-0.3 per-session delta traces
  (background) + prominent mean ± SEM (foreground), per epoch within panel.
- Layout per phenotype: side-by-side ipsi panel + contra panel × 4 epoch
  traces overlaid in each.

Q-locks:
- Q-lock 1 — 4-tier phenotype grouping.
- Q-lock 4 — ipsi/contra axis relabeling per AnimalInfo + caption caveat.
- Q-lock 5 — outputs under ``phenotype_pooled_ipsi_shift/{angle,x_trajectory}/``.
- Q-lock 6 — parameterized ``--endpoint-list`` + ``--family`` + ``--layout`` runner.
- Q-lock 8 — this family's design lock.
- Q-lock 9 — Tasks 5a/5b/5c preview-then-full triplet.

Business logic lands in Task 5; this module is a Phase 9.1 Task 0 stub.
"""
