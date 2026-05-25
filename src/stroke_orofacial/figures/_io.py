"""Phase 9.1 parquet loaders + cohort-pool helpers (cross-family internals).

Module-private (``_io``) — loader / pooler helpers consumed by ``phenotype_pooled``,
``phenotype_pooled_spatial``, ``latency_hist_cdf``, and ``ipsi_shift`` runners.
Centralizes the shared "load stats result CSV" + "phenotype-pool aggregate"
patterns so each per-family runner stays a thin orchestrator.

Read-only contract — Phase 9.1 consumes Phase 9 outputs (per Phase 9 close /
kickoff §"Out of scope"); writes go exclusively to
``pipeline_outputs/phase_9_1_figures/...`` via ``PathResolver``.

Expected helpers (lands in Tasks 1-5):

- Scalar V4/V5 stats results CSV loader:
  ``pipeline_outputs/stats/results/recovery/per_{bin,epoch}/<endpoint>.csv``.
- Spatial stats results CSV loader:
  ``pipeline_outputs/stats/results/recovery/per_bin/spatial_<metric>_<family>_<combo>.csv``.
- Phase 9 stats input parquet loader:
  ``pipeline_outputs/stats/inputs/<endpoint>/<animal>.parquet`` (latency_hist
  + ipsi-shift families consume per-trial rows; ``epoch_label`` column
  populated per Phase 9 Addendum #6 per-animal boundaries).
- Phenotype-pool aggregator: groups rows by 4-tier
  ``AnimalInfo.recovery_phenotype`` (Q-lock 1) with per-session equal-weight
  (per Phase 9 Addendum #6 — NOT "per-animal mean then pool").
- Endpoint-list YAML loader from ``configs/phase_9_1_endpoint_lists/``
  (Q-lock 6).

Q-locks:
- Q-lock 1 — cohort phenotype map via ``stats.recovery_epochs.cohort_phenotype_summary``.
- Q-lock 2 / 3 / 7 / 8 — endpoint-list YAMLs pin canonical inventories at Task 0.5.
- Q-lock 6 — endpoint-list YAML schema is the parameterization surface.

Business logic lands in Tasks 1-5; this module is a Phase 9.1 Task 0 stub.
"""
