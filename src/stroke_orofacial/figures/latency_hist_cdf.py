"""Phenotype-pooled ``latency_hist`` empirical-CDF figure family.

Phase 9.1 Task 4. ``latency_hist`` is confirmatory under Phase 9 Addendum #4
KS-bridge but is ``value_type=vector_per_session`` — no ``recovery/per_epoch/``
LMM result CSV exists, so it sits outside V4/V5 scope (Q-lock 2) and gets a
dedicated phenotype-pooled CDF runner here.

Source: ``pipeline_outputs/stats/inputs/latency_hist/<animal>.parquet`` (one
row per trial; per-trial first-correct-lick latency in ``value``). KS-bridge
p-values for caption annotation come from
``pipeline_outputs/stats/results/<axis>/per_session/latency_hist.csv`` (exact
axis confirmed at Task 0.5).

Q-locks:
- Q-lock 1 — 4-tier phenotype grouping (n=1 single-animal CDFs rendered
  descriptively).
- Q-lock 5 — outputs under
  ``pipeline_outputs/stats/figures/phenotype_pooled_latency_hist/...``.
- Q-lock 6 — parameterized ``--endpoint-list`` + ``--layout`` runner.
- Q-lock 7 — emit one of two layouts (locked at Task 0.5 review):
  (a) ``four_separate`` — 4 figures, one per phenotype × 4 epoch traces each;
  (b) ``single_4panel`` — 1 figure, 4 panels (one per phenotype) × 4 epoch
      traces per panel. Default = (b) until Task 0.5 locks.
- Q-lock 9 — Tasks 4a/4b/4c preview-then-full triplet.

Business logic lands in Task 4; this module is a Phase 9.1 Task 0 stub.
"""
