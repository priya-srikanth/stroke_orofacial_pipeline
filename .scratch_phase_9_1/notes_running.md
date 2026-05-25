# Phase 9.1 — running close-state notes

CC's free-form audit-trail companion file; paralleling `.scratch_phase_9/notes_running.md` (Phase 9). Used during Phase 9.1 execution to capture mid-flight observations, deviation explanations, decision provenance — anything that aids Task 7's DECISIONS + MIGRATION_LOG write-up at close.

Distinct from `.scratch_phase_9_1/verdict.md` (Priya's gate-5 verdict output at Task 6).

---

## 2026-05-25 — Phase 9.1 kickoff drafted (branch `phase/9.1-kickoff-draft`)

**Branch base:** `phase/9.1-kickoff-draft` cut off `main` HEAD `29eb078` (Phase 9 close merge for PR #129).

**Commits on branch so far:**
1. `3390146` — `docs(phase-9.1): land 2026-05-25 + 2026-05-25 (b) scoping amendments`. Lands both amendment blocks from the working tree (which Cowork wrote 2026-05-25 but did not commit; Phase 9 close PR shipped the pre-amendment scoping doc). Diff sanity-check passed before commit per plan Comment 1.
2. (this commit) — `docs(phase-9.1): add kickoff doc + scratch companion`. Adds `docs/prompts/phase-9.1-phenotype-pooled-figures-kickoff.md` + this notes file.

**Scope locked in kickoff Q-locks:**
- Q-lock 1 — 4-tier phenotype grouping (mild=4 / moderate=1 / moderate-severe=1 / severe=2).
- Q-lock 2 — V4/V5 = 35 disk-verified scalar LMM-run endpoints (~70 figures).
- Q-lock 3 — Spatial = 48 figures (16 Wasserstein + 16 UOT + 16 JS).
- Q-lock 4 — Ipsi/contra direct relabel + caption caveat.
- Q-lock 5 — Output tree `pipeline_outputs/phase_9_1_figures/{phenotype_pooled,phenotype_pooled_spatial,composites}/`.
- Q-lock 6 — `--endpoint-list` parameterized runner; W/UOT/JS dedup retained (V4/V5 scalar-only).

**Findings from drafting that future CC should know:**

- **Endpoint count discrepancy (kickoff §"Disk-verified counts").** (b) amendment estimated "~80-100 LMM-run scalar endpoints" → actual disk count is 35 in `pipeline_outputs/stats/results/recovery/per_epoch/` (after excluding `spatial_*` and `_all.csv`). Kickoff anchors on the disk-verified 35; the (b) amendment's "~160-200 V4/V5 figures" estimate is correspondingly ~70 figures.
- **2 orphan bare-slug spatial parquets to exclude at Task 0.5.** `spatial_wasserstein_jaw_eye_midpoint` and `spatial_wasserstein_tongue_spout_midpoint` are pre-Addendum-7-rename artifacts (per Phase 9 kickoff Addendum #7 (C)(1) the rename was supposed to be applied; these survived). Exclude from `phenotype_pooled_spatial_endpoints.yaml`.
- **PathResolver platform mapping.** Kickoff body uses canonical `pipeline_outputs/...` paths; on Windows the resolver maps to `M:\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\...`. No doc-text changes needed.
- **`latency_hist` is NOT in V4/V5 scope.** `latency_hist` is a `vector_per_session` endpoint that uses the KS-bridge test per Phase 9 Decision 1; it doesn't get LMM treatment, so it doesn't appear in `recovery/per_epoch/`. Q-lock 2 ("ALL LMM-run scalar endpoints") therefore excludes it. If Priya wants `latency_hist` in V4/V5 anyway, it requires a separate runner branch handling the KS-bridge schema — flag at Task 0.5 review.

**Plan-mode review trail:**
- Plan file: `C:\Users\sabatini\.claude\plans\buzzing-wobbling-simon.md`.
- Three plan-mode questions answered by Priya (Q-A bundle / Q-B 19-endpoint→superseded-by-(b)-amendment / Q-C dedup).
- 8 review comments from Priya folded into the kickoff:
  1. Comment 1 — diff sanity-check before commit 1 (executed; passed).
  2. Comment 2 — Q-C dedup explicit in §"Inputs catalog" + §"V4/V5 endpoint inventory".
  3. Comment 3 — Task 5 composites pull from BOTH source families (V4/V5 + spatial).
  4. Comment 4 — figure module location `src/stroke_orofacial/figures/phenotype_pooled.py` (new top-level subtree).
  5. Comment 5 — Q-A/B/C vs Q1-Q6 disambiguation in §Q-locks header.
  6. Comment 6 — branch-base HEAD verification (`git rev-parse main` match; use new tip if main advances).
  7. Comment 7 — pre-commit hook reminder + no `--no-verify` bypass.
  8. Comment 8 — this notes file (separate from verdict.md).

**Open questions deferred to within-phase iteration:**
- OPEN-Q 1 (Task 4): phenotype palette finalization (default ColorBrewer YlOrRd).
- OPEN-Q 2 (Task 5): composite figure inventory.

**Next session:** Phase 9.1 Task 0 — `git checkout -b phase/9.1-figures` off post-Phase-9-close main; environment smoke; seed this notes file with first Task 0.5 audit entry.

---
