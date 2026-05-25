"""4-tier phenotype palette + cross-family style harmonization helpers.

Phase 9.1 Task 6 (pub-polish). OPEN-Q 1 placeholder — final palette choice
(severity-ordering sequential vs categorical) locked at Task 6 scaffold review.
Kickoff default = ColorBrewer YlOrRd 4-step
(light yellow = mild → dark red = severe), giving an at-a-glance severity
ordering across all ~124-127 Phase 9.1 figures.

Q-lock 9 gate: Task 6 only applies AFTER every figure-emit task's Step Nc full
emit completes (Tasks 1c, 2c, 3c, 4c, 5c) — cross-family pass, no re-litigation
of decisions locked in any Nb gate.

Q-locks:
- Q-lock 1 — palette domain is exactly
  ``{mild, moderate, moderate-severe, severe}``.
- Q-lock 4 — ipsi/contra labeling helpers live here for the cross-family
  ``apply_ipsi_contra_labels`` style + ``figure_caption_caveat`` sentence
  (kickoff §"Module organization" placed these in ``pub_polish.py``; Phase 9.1
  Task 0 scaffold colocates the palette + side-label utilities here).

OPEN-Qs:
- OPEN-Q 1 (Task 6 scaffold review) — final palette choice; YlOrRd 4-step is
  the placeholder.
- OPEN-Q 3 (Tasks 1b / 2b scaffold review) — retroactive two-layer rendering
  for V4 / V5; if approved, palette + alpha conventions live here too.

Business logic lands in Task 6; this module is a Phase 9.1 Task 0 stub.
"""
