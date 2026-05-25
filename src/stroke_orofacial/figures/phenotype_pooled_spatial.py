"""Phenotype-pooled spatial recovery curves: Wasserstein + UOT cost + JS divergence.

Phase 9.1 Task 3. Consumes Phase 9 spatial stats results CSVs at
``pipeline_outputs/stats/results/recovery/per_bin/spatial_<metric>_<family>_<combo>.csv``
for the 48 endpoints pinned at Task 0.5
(``configs/phase_9_1_endpoint_lists/phenotype_pooled_spatial_endpoints.yaml``):
3 metrics × 4 scope/trial_group combos × 4 bodypart families.

Q-locks:
- Q-lock 3 — 48 phenotype-pooled spatial figures (16 W + 16 UOT + 16 JS); the
  4 confirmatory ``wasserstein × tone_aligned_all`` endpoints feature in Task 7
  composites.
- Q-lock 5 — outputs under
  ``pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/<family>/<metric>/<combo>.{svg,png}``.
- Q-lock 6 — parameterized ``--endpoint-list`` runner; Q-C dedup retained
  (distance metrics route HERE, not through V4/V5).
- Q-lock 9 — Tasks 3a/3b/3c preview-then-full triplet.

Business logic lands in Task 3; this module is a Phase 9.1 Task 0 stub.
"""
