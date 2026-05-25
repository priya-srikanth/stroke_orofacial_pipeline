"""V4 (per_bin curves) + V5 (per_epoch boxplots) phenotype-pooled figure emitters.

Phase 9.1 Tasks 1-2. Consumes Phase 9 scalar stats results CSVs at
``pipeline_outputs/stats/results/recovery/{per_bin,per_epoch}/<endpoint>.csv``
for the 35 LMM-run scalar endpoints pinned at Task 0.5
(``configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml``).

Q-locks:
- Q-lock 1 — 4-tier ``AnimalInfo.recovery_phenotype`` grouping (n=1 tiers render
  as single-animal traces with explicit ``n=1`` annotation).
- Q-lock 2 — V4/V5 = all 35 scalar (non-spatial) LMM-run endpoints.
- Q-lock 5 — outputs under
  ``pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/``.
- Q-lock 6 — parameterized ``--endpoint-list`` runner; ``spatial_*`` slugs
  skipped at runner level (V4/V5 scalar-only).
- Q-lock 9 — preview-then-full task structure (Tasks 1a/1b/1c and 2a/2b/2c).

Business logic lands in Tasks 1-2; this module is a Phase 9.1 Task 0 stub.
"""
