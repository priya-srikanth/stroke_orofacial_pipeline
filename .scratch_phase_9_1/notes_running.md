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

## 2026-05-25 (b) follow-up — Q-lock 7 latency_hist phenotype-pooled CDF family

Priya added one additional figure family during plan-mode review iteration. Lands as Q-lock 7 in the kickoff (commit `1d62f13`); precedent scoping-doc reconciliation patch in commit `0967a83`.

**Why this Q-lock exists:**
`latency_hist` is confirmatory per Phase 9 Addendum #4 KS-bridge but uses `value_type=vector_per_session` — Phase 9's `runners._ks_on_flat_per_trial` bridge handles its flat-per-trial schema, and `pre_post/per_session/latency_hist.csv` carries the KS-statistic + p-values. There is NO `recovery/per_epoch/latency_hist.csv` because LMM was never applied. Q-lock 2 ("ALL Phase 9 LMM-run scalar endpoints") therefore excludes `latency_hist` by definition. Q-lock 7 fixes this by adding a dedicated figure family.

**What Phase 9.1 does for latency_hist:**
- Pool per-trial latencies across animals within (phenotype × epoch).
- Compute empirical CDF per (phenotype, epoch) cell.
- One trace per epoch within each phenotype panel.
- Annotate panels with existing KS-bridge p-values (no new stats).

**Open question carried forward to Task 0.5 review:**

> **Layout decision (figure count: 1 vs 4):**
> - (a) `four_separate` — 4 figures, one per phenotype tier; 4 traces per figure (one per epoch).
> - (b) `single_4panel` — 1 figure, 4 panels (one per phenotype); 4 traces per panel.
>
> Kickoff defaults to (b) but the choice is Priya's at Task 0.5 scaffold review. Default rationale: cross-phenotype comparison at a glance is easier; matches the V5 boxplot convention of "one figure per endpoint" not "one figure per phenotype tier."

**Inputs for Task 0.5 audit (latency_hist-specific):**
- Confirm `pipeline_outputs/stats/inputs/latency_hist/<animal>.parquet` exists for all 8 animals.
- Confirm `pipeline_outputs/stats/results/<axis>/per_session/latency_hist.csv` location (`pre_post` per kickoff §"Q-lock 7"; verify on disk during audit).
- Inspect row-counts per (animal, phenotype, epoch) cell to confirm CDF pooling is meaningful (n=1 phenotype tiers will have small per-cell n; the n=1 single-animal CDF is still descriptively useful).

**Total figure count revised:**
- 70 V4/V5 (35 endpoints × 2 variants) + 48 spatial + 1-4 latency_hist ≈ **~120 figures**.
- Plus composites at Task 5 (count TBD by Priya).

**Commit chain on branch:**
1. `3390146` — scoping doc 2026-05-25 amendments landed.
2. `14bbdcd` — kickoff doc + initial notes_running.
3. `0967a83` — chore: scoping-doc disk-verified count reconciliation + NEW LOCK Q-lock 7 source.
4. `1d62f13` — kickoff: Q-lock 7 added; deliverables, tasks, totals updated.
5. `02ff76c` — notes_running: Q-lock 7 entry + Task 0.5 layout question.

---

## 2026-05-25 (b) second follow-up — Q-lock 8 tongue ipsi-shift figure families

Scoping doc lock landed in commit `08c6bae`; kickoff body landed in commit `73aae59`. Two new figure families targeting memory finding #6 (direction-sensitive tongue endpoints x/angle show ipsi-contra asymmetry post-stroke).

**Source-of-truth pointer:** scoping doc, "NEW LOCK 2026-05-25 (b) second follow-up (Priya) — tongue ipsi-shift figure families" paragraph (added in commit `08c6bae`). Kickoff body §"Q-lock 8 — Tongue ipsi-shift figure families" (commit `73aae59`).

**Two families:**
- **Family 8.1** — Delta tongue angle at lick1 + lick2 + per-trial median (3 endpoint sub-families: `tongue_lick1_angle_at_ypeak`, `tongue_lick2_angle_at_ypeak`, `tongue_median_angle_at_peak_velocity`); ipsi/contra side-split; ~3 figures.
- **Family 8.2** — Delta tone-aligned tongue x trajectory (continuous per-frame DLC, NOT x at Y-peak / NOT x at peak velocity per Priya clarification); ipsi/contra side-split; 1-4 figures.

**Locked design elements (apply to both 8.1 and 8.2):**
- Baseline normalization = per-bin trajectory subtraction (NOT Addendum #6 per-trial scalar subtraction). Per-animal pre-stroke side-matched baseline trajectory; per-session delta(t) = session_mean(t) − baseline(t); phenotype-pool across sessions within (phenotype, epoch, side).
- Pre-epoch trace REQUIRED as noise-floor reference (NOT omitted). Thin per-session overlay for pre reveals natural session-to-session variability around zero; primary visual comparison the figures support.
- Two-layer rendering: thin alpha-transparent per-session delta trajectories background (α≈0.2-0.3) + prominent mean ± SEM delta trace foreground; y=0 reference line explicit.

**Tongue angle endpoints get DUAL treatment** (V4/V5 + Q-lock 8 Family 8.1) — NOT a dedup violation per kickoff §"V4/V5 endpoint inventory" callout. Same parquet data, different axes (rel_day vs tone-aligned trial time) + different framing (recovery curve vs per-bin trajectory).

**Open extension** (OPEN-Q 3, deferred to Task 1b / Task 2b scaffold review): retroactive two-layer rendering for V4 (per-animal trajectories underneath phenotype mean) and/or V5. Priya can request at Task 1b/2b if the Q-lock 8 style reads cleanly during Task 5b.

---

## 2026-05-25 (b) third follow-up — Q-lock 9 preview-then-full emit pattern

Scoping doc lock landed in commit `82a4653`; kickoff body landed in commit `73aae59` (combined with Q-lock 8).

**Source-of-truth pointer:** scoping doc, "New lock 2026-05-25 (b) third follow-up — preview-then-full emit pattern (Q-lock 9)" paragraph. Kickoff body §"Q-lock 9 — Preview-then-full emit pattern" (commit `73aae59`).

**Pattern:** every figure-emit task in §9 Tasks splits into 3 steps:
- **Step Na (preview):** single phenotype tier (default moderate-severe = PS51 alone, n=1). Wall-time ~10-20% of full-cohort.
- **Step Nb (scaffold review gate):** Priya iterates on style. Changes propagate to all other families before their Nc. Wall-time = Priya bandwidth.
- **Step Nc (full):** all phenotype tiers regenerated with locked Step Nb style. No retroactive restyling.

**Preview tier override:** CC may propose mild (n=4) cross-session stress test or severe (n=2) small-n pooled stress test if moderate-severe is a poor fit for the family being previewed. Surface in the Step Na commit message.

**Wall-time impact:** total Phase 9.1 wall-time bumped ~10-14 days → ~13-17 days CC. Total commits: 9-12 → 12-16. Figure count: ~120 → ~124-127.

---

## 2026-05-25 — Task 0.5 trajectory-plotting discovery (Family 8.2 loader)

**Result: FOUND.** Existing canonical code is in the consolidated repo. Phase 9.1 Family 8.2 reuses + wraps these; NO new trajectory infrastructure required.

**Trajectory data source:**
- `pipeline_outputs/dlc_analysis/interpolated_traces/<bodypart>/<animal>/<YYYYMMDD>.parquet` — Phase 7a.2 interpolated_traces output. For Family 8.2 (tongue x trajectory): `bodypart = "tongue"`, columns include `x_final`, `y_final`, plus `fps`, `n_frames`. Same parquet already consumed by `dlc_kinematics.tongue_pertrial`, `dlc_kinematics.tongue_jaw_mismatch`, `dlc_kinematics.mean_sem_visual`.

**Existing loader / aligner to reuse:**
- `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py::build_mean_sem_cohort(bodypart, animal, resolver, ...)` — produces tone-aligned mean ± SEM trajectory per (bodypart, animal). Family 8.2 wraps this with phenotype-pool + ipsi/contra split + delta-from-baseline subtraction.

**Existing rendering primitives to reuse:**
- `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py::_plot_tone_aligned_session_overlays(...)` — thin per-session overlay rendering (the two-layer background layer).
- `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py::_plot_tone_aligned_binned_overlays(...)` — foreground mean ± SEM binned rendering.

**Per-lick peak-time primitive (Family 8.1):**
- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py::tongue_lick_t_peaks_bylick` — per-lick peak times for placing (peak_t_ms, peak_angle) points at tone-aligned bins.

**Binning convention:**
- `configs/defaults.yaml::dlc_kinematics.mean_sem_visual.*` — post-tone window + bin width already defined for tone-aligned tongue trajectory plotting. Phase 9.1 inherits; no new binning OPEN-Q.

**L/R → ipsi/contra translation:**
- `AnimalInfo.mouse_side_to_ipsi_contra(side, stroke_laterality)` (Phase 8a.10 scaffolding).

**Implication for Phase 9.1 execution:** Family 8.2's `phenotype_pooled_ipsi_shift.py` is a *thin wrapper* — phenotype-pool + ipsi/contra split + baseline subtraction layered atop already-tested trajectory primitives. NOT a new trajectory subsystem.

---

## Commit chain on branch (updated)

1. `3390146` — scoping doc 2026-05-25 amendments landed.
2. `14bbdcd` — kickoff doc + initial notes_running.
3. `0967a83` — chore: scoping-doc disk-verified count reconciliation + NEW LOCK Q-lock 7 source.
4. `1d62f13` — kickoff: Q-lock 7 added.
5. `02ff76c` — notes_running: Q-lock 7 entry.
6. `08c6bae` — chore: scoping doc Q-lock 8 (tongue ipsi-shift families).
7. `82a4653` — chore: scoping doc Q-lock 9 (preview-then-full emit pattern).
8. `73aae59` — kickoff: Q-locks 8 + 9 + task-table preview-then-full restructure (renames Task 3b/3c → Task 4/5, Task 4 → 6, Task 5 → 7, Task 6 → 8, Task 7 → 9).
9. (this commit) — notes_running: Q-locks 8 + 9 entries + Task 0.5 trajectory-plotting discovery.

---


