"""Phase 9.1 panel-grid + ipsi/contra side-split layout helpers.

Module-private (``_layout``) — matplotlib layout primitives shared across the
phenotype-pooled / spatial / latency_hist / ipsi-shift families. Keeps each
per-family runner focused on data assembly + per-panel rendering; cross-family
panel arrangement lives here.

Expected helpers (lands in Tasks 1-5):

- Per-phenotype panel grid: arranges 4-tier panels (mild / moderate /
  moderate-severe / severe) per Q-lock 1, supporting both
  ``single_4panel`` (one figure) and ``four_separate`` (four figures) layouts
  selected per family at Task 0.5 / Task Nb review.
- Ipsi/contra side-split: side-by-side ipsi + contra panels per phenotype
  (Q-lock 8 trajectory families). Side-axis labels via
  ``AnimalInfo.mouse_side_to_ipsi_contra`` (Q-lock 4); caption caveat sentence
  applied per figure.
- n-label annotation helper (kickoff §"Phenotype-grouping conventions"
  Critical Caveat 1) — every figure must show n per phenotype tier
  prominently; n=1 tiers get explicit "single-animal trace" annotation.
- y=0 reference-line helper for Q-lock 8 delta-from-baseline panels.

Q-locks:
- Q-lock 1 — panel grid domain is the 4-tier phenotype set.
- Q-lock 4 — side labels via ``mouse_side_to_ipsi_contra`` + caption caveat.
- Q-lock 7 / 8 — layout enum (``four_separate`` vs ``single_4panel``) selected
  per family.

Business logic lands in Tasks 1-5; this module is a Phase 9.1 Task 0 stub.
"""
