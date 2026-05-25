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

## 2026-05-25 — Task 0 start (branch `phase/9.1-figures`)

**Branch cut.** `phase/9.1-figures` branched from `main` HEAD `81f89c9` (post Phase 9.1 kickoff merge PR #130 `81f89c9`; the kickoff body's expected base SHA `29eb078` was Phase 9 close — `main` advanced past it during the kickoff PR merge, which is the explicit fallback in kickoff §"Task 0 — Setup + branch verification" ("If `git rev-parse main` does NOT match `29eb078`, branch off the new tip regardless").

**Warm-start verifications:**

- `git status` clean post `git pull origin main`. Tag audit: `v9-stats-behavioral` present; no `v9.1` tag yet (correct — tags land only at phase close).
- Conda env smoke (`conda run -n stroke_orofacial python -c "import stroke_orofacial"`): OK; module resolves to repo-tree `src/stroke_orofacial/__init__.py`.
- `pytest --collect-only`: **1743 tests collected in 1.52s**, no import errors.
- `ruff check .`: **67 pre-existing errors on `main`** (16 E402 + 15 F541 + 10 F821 + 8 E702 + 6 F401 + 6 F841 + 4 invalid-syntax + 1 E731 + 1 E741). NOT introduced by Task 0; the working tree was clean against main when audit ran. Two `Access is denied` warnings on `.pytest_tmp_*/` dirs are environmental (Windows ACL on harness-created tmp dirs). The kickoff §"Pre-commit checks" comment "pre-existing clean baseline" overstates current state — flagged for Priya. Investigation deferred (out of Task 0 scope).

**Phase 9 disk-state audit (pre-Task-0.5 sanity sweep against kickoff Q-lock counts):**

| Anchor | Kickoff expectation | Disk reality | Status |
|---|---|---|---|
| Q-lock 2 — `pipeline_outputs/stats/results/recovery/per_epoch/` non-spatial, non-`_all.csv` | 35 LMM-run scalar endpoints | **35** | MATCHES |
| Q-lock 3 — `pipeline_outputs/stats/results/recovery/per_epoch/spatial_*` | 48 spatial endpoints | **48** | MATCHES |
| Q-lock 3 — `pipeline_outputs/stats/inputs/spatial_*` input dirs | 48 spatial + 2 orphan bare slugs (Wasserstein only per kickoff §"Task 0.5") | **52 total → 48 canonical + 4 orphan bare slugs** | MINOR DISCREPANCY (see below) |
| Q-lock 7 — `pipeline_outputs/stats/inputs/latency_hist/<animal>.parquet` | 8 animals | **8 (PS46-50, PS51, PS54, PS55)** | MATCHES |

**Orphan bare-slug count discrepancy (4, not 2).** Kickoff line 565 mentions only `spatial_wasserstein_jaw_eye_midpoint` and `spatial_wasserstein_tongue_spout_midpoint` as Addendum-7 rename artifacts. Disk audit shows **4** orphan bare-slug dirs:

1. `spatial_wasserstein_jaw_eye_midpoint`
2. `spatial_wasserstein_tongue_spout_midpoint`
3. `spatial_uot_cost_tongue_spout_midpoint`
4. `spatial_js_divergence_tongue_spout_midpoint`

Task 0.5 endpoint-list YAML construction must exclude all 4 (not just 2). Net canonical = 52 − 4 = 48 ✓ (matches Q-lock 3 count). Flag for Priya: kickoff body exclusion list at line 565 needs an addendum to add the UOT + JS orphans.

**Figure module scaffold (per launch prompt's 7-stub structure; deviates from kickoff §"Module organization" 6-file plan):**

Existing `src/stroke_orofacial/figures/` from Phase 0 skeleton (`d874dde`) contains 5 placeholder files (`__init__.py` + `behavior_plots.py` + `kinematic_plots.py` + `spatial_plots.py` + `style.py`) — each a 1-line docstring; zero importers in the repo. **Preserved untouched per CLAUDE.md "don't refactor beyond what task requires"**; Phase 0 stubs and Phase 9.1 stubs coexist in the same dir under different names.

Phase 9.1 stubs added by Task 0 (matching the launch prompt's "one file per concern" pattern modeled on `src/stroke_orofacial/stats/`):

1. `phenotype_pooled.py` — V4/V5 base + parameterized runner (Tasks 1-2; Q-locks 2 + 5 + 6 + 9).
2. `phenotype_pooled_spatial.py` — 48-figure W/UOT/JS spatial emitter (Task 3; Q-locks 3 + 5 + 6 + 9; Q-C dedup retained).
3. `latency_hist_cdf.py` — empirical-CDF family (Task 4; Q-lock 7 + 9; layout choice locked at Task 0.5/4b review).
4. `ipsi_shift.py` — Q-lock 8 Family 8.1 (angle) + 8.2 (x trajectory); reuses `dlc_kinematics.mean_sem_visual.build_mean_sem_cohort` + `dlc_kinematics.tongue_angle_cohort._plot_tone_aligned_*` primitives (no new trajectory code).
5. `palette.py` — 4-tier phenotype palette + ipsi/contra style; OPEN-Q 1 placeholder until Task 6 review.
6. `_io.py` — module-private parquet loaders + phenotype-pool helpers (per-session equal-weight per Phase 9 Addendum #6).
7. `_layout.py` — module-private panel-grid + ipsi/contra side-split + n-label + y=0 reference helpers.

Each stub is docstring-only (no business logic; that lands in Tasks 1-5).

**Test stubs (per launch prompt's `tests/figures/` subdir directive):**

Existing repo convention is flat `tests/test_*.py` (no per-package subdirs). The kickoff body §"Module organization" lists flat `tests/test_figures_*.py`. Launch prompt directs `tests/figures/test_*.py` subdir. **Deviation from kickoff + existing convention**; honoring launch prompt's explicit directive. `pyproject.toml` `[tool.pytest.ini_options]` `testpaths = ["tests"]` autodiscovers subdirs — no config change needed.

5 test stubs created mirroring the 5 public src modules (skipping `_io`/`_layout`; those test transitively via the emit modules):

1. `tests/figures/__init__.py` (empty).
2. `tests/figures/test_phenotype_pooled.py` (docstring only).
3. `tests/figures/test_phenotype_pooled_spatial.py` (docstring only).
4. `tests/figures/test_latency_hist_cdf.py` (docstring only).
5. `tests/figures/test_ipsi_shift.py` (docstring only).
6. `tests/figures/test_palette.py` (docstring only).

Post-scaffold `pytest --collect-only` re-run: **1743 tests collected** (unchanged from baseline) — confirms the stubs contribute zero collected tests and don't break collection.

**Q-lock 9 reminder.** No `pipeline_outputs/` writes in Task 0. First write happens at Task 1a preview emit (single phenotype tier; default moderate-severe / PS51 per kickoff §"Q-lock 9").

**Next:** STOP at end of Task 0 per launch-prompt instruction. Priya reviews scaffold + tooling state before authorizing Task 1a (V4 moderate-severe preview emit).

---

## 2026-05-25 — Task 1a V4 preview emit complete (branch `phase/9.1-figures`)

**Preview-tier override per Q-lock 9 (locked in launch prompt):** all 4
phenotype tiers × 5 representative endpoints (vs the Q-lock 9 default of
single-tier × full inventory). Rationale: V4 is inherently multi-phenotype
(traces colored per tier per panel); restricting preview to one tier
collapses every panel to a single trace and exercises none of the
cross-phenotype palette + multi-trace + SEM-band rendering that Task 1b
must review.

**5 preview endpoints (rationale per launch prompt):**

- `first_lick_accuracy_all` — Phase 9 confirmatory; pre_vs_chronic NS = full
  recovery (memory finding #3). Tests palette readability when traces
  converge.
- `num_correct_licks_per_trial` — Phase 9 confirmatory; behavioral count
  recovery. Tests palette on integer-valued endpoint.
- `tongue_lick1_y_peak` — Phase 9 confirmatory; bimodal-uniform sign-flip
  across all 8 animals (memory finding #4). Tests how
  acute-overshoot/sub_acute-undershoot shows up in phenotype-pooled
  traces.
- `tongue_lick1_angle_at_ypeak` — Phase 9 confirmatory; persistent chronic
  deficit (q_holm < 1e-80). Tests palette + SEM rendering on large
  effect sizes.
- `tongue_lick1_x_at_ypeak` — Phase 9 confirmatory; ipsi-contra-meaningful
  (memory finding #6). Tests whether V4's side-pooled phenotype view
  obscures the ipsi-shift signal that Q-lock 8 figures will surface
  explicitly.

**Implementation summary:**

- `src/stroke_orofacial/figures/phenotype_pooled.py` — V4 runner +
  module-level CLI (`python -m stroke_orofacial.figures.phenotype_pooled`).
  Flags: `--endpoint-list`, `--phenotype-tiers`, `--output-dir`,
  `--overwrite {skip,force}`, `--dpi`. `spatial_*` slugs auto-skip per Q-C
  dedup (logged + counted as missing/no-data).
- `src/stroke_orofacial/figures/_io.py` — endpoint-list loader (`#`
  comments + blanks tolerated), 8-animal cohort + phenotype-tier loader,
  stats input parquet loader (drops sentinel + NaN rows), per-animal-bin
  aggregator, phenotype-pooled mean ± SEM aggregator. `_bin_rel_day`
  mirrors `stats.figures._bin_rel_day` (Phase 9 V2) for x-axis parity
  with the LMM fits; `_bin_midpoint_rel_day` returns the true bin center
  so mixed-cadence animals (PS46-50 bin_days=2 vs PS51/54/55 bin_days=7)
  align natively on a phenotype-shared midpoint grid (within-tier
  bin_days is uniform per the cohort table).
- `src/stroke_orofacial/figures/_layout.py` — `phenotype_panel` decorates
  (stroke-onset crimson dashed line at x=0.5 matching V2; y=0 gray
  reference; xlabel/ylabel/title); `phenotype_legend` reorders to
  canonical mild→severe with per-tier n-label suffix ("(n=1,
  single-animal trace)" for the n=1 tiers per Critical Caveat 1).
- `src/stroke_orofacial/figures/palette.py` — YlOrRd[4] hex map +
  `figure_caption_caveat()` (Q-lock 4 sentence).
- `tests/figures/test_phenotype_pooled.py` — 8 tests covering CLI parse,
  bin index, bin midpoint, endpoint-list parsing. **All 8 PASS** in 0.09s.

**Stats result row counts per preview endpoint (cohort = 8 animals):**

| endpoint                          | grain                | rows/animal | total |
|---|---|---|---|
| `first_lick_accuracy_all`         | per-session           | 42 (PS46)   | 512   |
| `num_correct_licks_per_trial`     | per-session           | 42 (PS46)   | 512   |
| `tongue_lick1_y_peak`             | per-trial             | 2019 (PS46) | 24023 |
| `tongue_lick1_angle_at_ypeak`     | per-trial             | 2019 (PS46) | 24023 |
| `tongue_lick1_x_at_ypeak`         | per-trial             | 2019 (PS46) | 24023 |

All 5 endpoints have 8/8 cohort animals on disk; epoch_label populated for
all 4 epochs (pre, acute, sub_acute, chronic); cohort_bin_size=2 for PS46
(consistent with `bin_days=2`). NO data-audit issues.

**10 emitted files:**

```
pipeline_outputs/phase_9_1_figures/phenotype_pooled/
├── first_lick_accuracy_all/
│   ├── v4_per_bin_phenotype_pooled.svg    (49,838 B)
│   └── v4_per_bin_phenotype_pooled.png    (87,063 B)
├── num_correct_licks_per_trial/
│   ├── v4_per_bin_phenotype_pooled.svg
│   └── v4_per_bin_phenotype_pooled.png
├── tongue_lick1_y_peak/
│   ├── v4_per_bin_phenotype_pooled.svg
│   └── v4_per_bin_phenotype_pooled.png
├── tongue_lick1_angle_at_ypeak/
│   ├── v4_per_bin_phenotype_pooled.svg
│   └── v4_per_bin_phenotype_pooled.png
└── tongue_lick1_x_at_ypeak/
    ├── v4_per_bin_phenotype_pooled.svg
    └── v4_per_bin_phenotype_pooled.png
```

Wall-time: ~1.2s for all 5 endpoints (cohort load + 5 emits).

**Style defaults locked in code (Task 1b review targets):**

- **Palette:** ColorBrewer YlOrRd[4] — mild `#ffffb2`, moderate `#fecc5c`,
  moderate-severe `#fd8d3c`, severe `#e31a1c`. OPEN-Q 1 placeholder.
- **Line:** `marker="o"`, `linewidth=2.0`, `markersize=4.0`, `zorder=3`.
- **SEM band:** `alpha=0.25`, `linewidth=0`, `zorder=2`, same color as
  trace. n=1 tiers (moderate, moderate-severe) emit ONLY a line (no
  fill_between).
- **Stroke onset:** crimson dashed line at x=0.5 (between bin_idx=0
  baseline-included and bin_idx=1 first-post-stroke), matching Phase 9
  V2 convention.
- **Reference lines:** y=0 in light gray (0.85) at zorder=0.
- **Legend:** `loc="best"`, `fontsize=8`, `framealpha=0.85`, ordered
  mild→severe with n suffix.
- **Figure size:** `(7.5, 4.0)` inches; SVG vector + PNG at 150 DPI.

**Spot-check (visual sanity, PNG inspection):**

- `first_lick_accuracy_all`: mild stable ~0.9 across pre+post; severe deep
  deficit to ~0 acute, gradual recovery to ~0.65 chronic — matches memory
  finding #3 (severe persistent deficit; mild full recovery).
- `tongue_lick1_y_peak`: severe ACUTE OVERSHOOT to ~185 (vs pre ~125),
  then sub_acute/chronic UNDERSHOOT to ~80 — matches memory finding #4
  bimodal-uniform sign-flip. Moderate-severe (PS51) shows similar
  acute-overshoot then partial recovery. Mild stable around 130.
- Mild's palette color (`#ffffb2` light yellow) IS hard to see on white
  background — predicted OPEN-Q 1 issue; Priya may select a different
  palette at Task 1b.
- Single-animal traces (moderate, moderate-severe) render as lines
  without ribbons — visually distinct from pooled tiers, makes the n=1
  caveat visible at a glance.

**Tooling pre-commit checks (kickoff addendum 2026-05-25):**

- `ruff check src/stroke_orofacial/figures/ tests/figures/` → **All checks
  passed!** (scoped per the kickoff addendum landed this session — see
  next bullet).
- `pytest tests/figures/test_phenotype_pooled.py` → 8 passed in 0.09s.
- The 67 pre-existing ruff errors on `main` are out of Phase 9.1 scope
  per the kickoff addendum; deferred to a separate future chore PR.

**Kickoff doc addendum (2026-05-25, Cowork unstaged → landed this commit):**

`docs/prompts/phase-9.1-phenotype-pooled-figures-kickoff.md` §"Pre-commit
checks" updated to replace `ruff check .` (which was wrong — Task 0
audit found 67 pre-existing errors) with the scoped
`ruff check src/stroke_orofacial/figures/ tests/figures/`. New Phase 9.1
rule: new code under these two trees MUST be ruff-clean; the 67
pre-existing errors are out of Phase 9.1 scope. Bundling the addendum
into this Task 1a commit per Cowork instruction.

**Next:** STOP at end of Task 1a per Q-lock 9. Priya reviews palette +
line widths + SEM-band alpha + axis labels + caption + retroactive
two-layer-rendering ask (OPEN-Q 3) before Task 1c full V4 emit across all
35 scalar endpoints. Style decisions at Task 1b also propagate to V5
(Task 2c) + spatial (Task 3c) + latency_hist (Task 4c) + ipsi-shift
(Task 5c).

---

## 2026-05-25 — Task 1a v2 re-emit (branch `phase/9.1-figures`)

Two scope adjustments from Priya's Task 1a v1 review supersede the original
launch-prompt:

1. **V4 must be side-split**, not cohort-side-pooled. My v1 launch-prompt
   instructed "plot SIDE-POOLED traces" with ipsi/contra deferred to Q-lock 8;
   that was wrong per the kickoff scoping doc §6.1 citing Phase 9 Addendum #8
   (H). Re-emit V4 with side-by-side ipsi + contra panels.
2. **V5 reviewed alongside V4**, not deferred to Task 2. Task 2 (separate V5
   emit) is SUBSUMED into Task 1; review locks both figure types at once.

Both locked as **Q-lock 10** in a fresh kickoff doc addendum (lands in this
commit at `docs/prompts/phase-9.1-phenotype-pooled-figures-kickoff.md`
§"Pre-commit checks" — immediately after the existing 2026-05-25 ruff-baseline
addendum).

### Palette adjustment (OPEN-Q 1 partial resolution)

`#ffffb2` → `#fed976` for mild. Priya 2026-05-25 v1 review: pale yellow
unreadable on white. New value is ColorBrewer YlOrRd 6-step [2] — still
yellow-dominant but visible. YlOrRd severity gradient preserved.
Remaining palette decisions defer to Task 6 pub-polish.

### Side-column audit (5 preview endpoints)

ALL 5 endpoints have `side` column present + populated; NONE degrade to
single-panel cohort-pooled. Per-(phenotype, side) row counts from the raw
stats input parquets:

| Endpoint | total rows | L rows | R rows |
|---|---|---|---|
| `first_lick_accuracy_all` | 512 | 256 | 256 |
| `num_correct_licks_per_trial` | 512 | 256 | 256 |
| `tongue_lick1_y_peak` | 19,729 | 10,307 | 9,422 |
| `tongue_lick1_angle_at_ypeak` | 19,729 | 10,307 | 9,422 |
| `tongue_lick1_x_at_ypeak` | 19,729 | 10,307 | 9,422 |

(Per-trial endpoints have slight L/R imbalance from per-trial side stratification;
session endpoints have exact L/R parity from per-session-per-side rows.)

Phenotype × side cells (e.g., `tongue_lick1_y_peak`):

| phenotype_tier | L | R |
|---|---|---|
| mild       | 3988 | 3946 |
| moderate   | 1014 |  926 |
| moderate-severe | 2035 | 1918 |
| severe     | 3270 | 2632 |

Every (phenotype × side) cell is well-populated. SEM bands meaningful for
mild (n=4) + severe (n=2); moderate + moderate-severe render as single-animal
lines per Critical Caveat 1.

### Implementation summary

- **`palette.py`** — `_YLORRD_4["mild"]` shifted to `#fed976`; comment updated
  to note the YlOrRd 6-step [2] substitution per Priya 2026-05-25 review.
- **`_io.py`** — added `endpoint_has_side(df)` (Q-lock 10(c) audit), extended
  `per_animal_bin_means` + `phenotype_pooled_per_bin` with `by_side: bool`
  kwarg, added `attach_phenotype_column(df, animals)` + `per_session_within_epoch`
  for V5 per-session-within-epoch aggregation (Phase 9 Addendum #6 grain).
  Renamed degenerate `per_animal_bin_means` sort key (`bin_x` removed; was
  dead from earlier _io edit).
- **`_layout.py`** — added `phenotype_side_split_panels()` (returns
  `(fig, ipsi_ax, contra_ax)` with shared y-axis + ipsi/contra panel titles),
  `cohort_pooled_panel()` (single-panel fallback), `apply_side_split_suptitle`
  (figure suptitle + footer caveat sentence). Extended `phenotype_panel`
  with `set_title: bool` (so side-split callers keep panel titles) +
  `draw_stroke_onset: bool` (V5 boxplots don't need the x=0.5 dashed line).
- **`phenotype_pooled.py`** — V4 refactored to side-split with cohort-pooled
  fallback; V5 emit_v5_per_endpoint added with same side-split + fallback
  pattern. CLI `--figure-types` flag added (default `v4,v5`); main loop
  iterates both figure types per endpoint.

### V5 boxplot styling defaults locked in code (Task 1b review targets)

- **Layout:** epochs along x at positions 0..3 (pre/acute/sub_acute/chronic);
  4 phenotype boxes per epoch position, offset by `{mild: −0.30, moderate:
  −0.10, moderate-severe: +0.10, severe: +0.30}`.
- **Box width:** `_V5_BOX_WIDTH = 0.18`.
- **Fill:** patch artist, `set_facecolor(palette_color)`, `alpha=0.55`.
- **Edge/whisker/cap:** palette color, `linewidth=1.0`.
- **Median:** dark gray (`color="0.15"`), `linewidth=1.5` (for contrast on
  light box fills).
- **Outliers:** `marker="o"`, `markersize=3.0`, hollow (`markerfacecolor=
  "none"`), edge color = palette color, `alpha=0.5`.
- **Whiskers:** matplotlib default 1.5×IQR; `showfliers=True`.
- **xlim:** `(-0.6, n_epochs - 0.4)` to give room for the leftmost +
  rightmost phenotype offsets.

### Tests

`tests/figures/test_phenotype_pooled.py` extended from 8 → **16 tests**.
New tests cover the `--figure-types` CLI flag (valid + invalid + default),
`endpoint_has_side` (all 4 fallback states: populated, only-L, absent, all-NaN,
empty). **All 16 PASS** in 0.08s.

### Files emitted (5 endpoints × 2 figure types × 2 formats = 20)

Wall-time: ~5s end-to-end for the 5 endpoints × V4 + V5.

```
pipeline_outputs/phase_9_1_figures/phenotype_pooled/
├── first_lick_accuracy_all/
│   ├── v4_per_bin_phenotype_pooled.{svg,png}
│   └── v5_per_epoch_phenotype_pooled.{svg,png}
├── num_correct_licks_per_trial/    [v4 + v5]
├── tongue_lick1_y_peak/            [v4 + v5]
├── tongue_lick1_angle_at_ypeak/    [v4 + v5]
└── tongue_lick1_x_at_ypeak/        [v4 + v5]
```

### Spot-check (visual sanity)

- `tongue_lick1_x_at_ypeak` V4: **memory finding #6 (ipsi-shift) clearly
  visible.** ipsi panel shows severe (red) deep deficit around rel_day ~10
  to ~−15, then recovery to ~+30 chronic; contra panel shows moderate-severe
  (PS51, orange) post-stroke contra values stay around −10 across all
  post-stroke bins — exactly the "tongue prefers ipsi side after stroke"
  hypothesis the Q-lock 8 figures will surface explicitly.
- `tongue_lick1_y_peak` V5: **memory finding #4 (bimodal sign-flip)
  unambiguous.** Severe acute boxplot at ~185 (vs pre ~115); sub_acute drops
  to ~80; chronic ~85. Same shape on both ipsi + contra. Mild stable
  ~115-145 across all epochs.
- `first_lick_accuracy_all` V4: severe ipsi/contra deficits to 0.0 acute
  with gradual recovery; mild stable; consistent with memory finding #3.
- Mild palette (`#fed976`) is now visible — readable against the white
  background and against the SEM-band fill.

### Tooling

- `ruff check src/stroke_orofacial/figures/ tests/figures/` → **All checks
  passed!**
- `pytest tests/figures/test_phenotype_pooled.py` → 16 pass in 0.08s.
- Kickoff doc Q-lock 10 addendum landed (immediately after the existing
  2026-05-25 ruff-baseline addendum); palette change bundled per launch-prompt
  instruction.

### Next

STOP at end of Task 1a v2 per Q-lock 9. Priya's Task 1b scaffold review now
covers BOTH V4 + V5 together — palette + box styling + side-split layout +
caption convention + legend placement + retroactive two-layer rendering
(OPEN-Q 3). Decisions locked at 1b propagate to spatial (Task 3) +
latency_hist (Task 4) + ipsi-shift (Task 5) before their full emits.

---

## 2026-05-25 — Task 1a v3 V5 style revision (branch `phase/9.1-figures`)

Priya 2026-05-25 Task 1a v2 review: V5 boxplots replaced with
delta-from-baseline line plot + faded per-session scatter underlay.
Conceptually parallel to Q-lock 8 Family 8.1's two-layer rendering, but
with epoch as categorical x-axis. V4 unchanged from v2; this is V5 only.

Locked as **Q-lock 11** in a fresh kickoff doc addendum (immediately after
the Q-lock 10 addendum landed in v2).

### V5 pipeline (Q-lock 11)

```
load_stats_inputs(endpoint)
    ↓ rows: animal × date × trial × side × value × epoch_label × ...
attach_phenotype_column(animals)
    ↓ + phenotype_tier
per_animal_side_baseline(by_side=has_side)        ← pre-epoch mean per (animal, side)
per_session_within_epoch(by_side=has_side)        ← rows: (animal, date, side, epoch_label, value)
apply_baseline_delta(per_session, baseline)       ← + delta_value = value − baseline_mean
phenotype_pooled_per_epoch_delta(by_side)         ← rows: (phenotype, side, epoch_label, mean, sem, n_sessions)
```

Foreground: 4 phenotype lines connecting cohort-mean delta across the 4
epoch positions with SEM error bars (`linewidth=2.0`, `markersize=5.0`,
`capsize=3.5`, palette color, `zorder=3`).

Background: per-(animal, session) scatter dots at jittered x-positions
(`±0.15` epoch units; deterministic seed = 42 for reproducibility).
Marker: `o`, `s=12.0`, `alpha=0.25`, facecolor=palette color,
edgecolor=none, `zorder=1`.

y=0 reference line drawn by `phenotype_panel` at `zorder=0`. xticks at the
4 epoch positions; xlim `(-0.5, 3.5)` to give margin for the leftmost +
rightmost jitter bands.

### Implementation summary

- **`_io.py`** — added `per_animal_side_baseline(df, by_side=...)`,
  `apply_baseline_delta(sessions, baseline, by_side=...)`,
  `phenotype_pooled_per_epoch_delta(sessions_with_delta, by_side=...)`.
  All three composable with the existing `per_session_within_epoch`
  pipeline. Baseline computed from `epoch_label == "pre"` rows; sessions
  whose (animal, side) lack a pre-epoch baseline are dropped from delta
  computation (logged as missing in notes if any endpoint surfaces this;
  current 5 preview endpoints all have full pre-epoch coverage).
- **`_layout.py`** — added `jittered_x_positions(n_points, epoch_idx, *,
  width=0.15, seed=42)` using `np.random.default_rng(seed)`. Fixed seed
  per-call so the scatter pattern is identical across emits (important
  for SVG diff readability at PR review). Empty-input path returns `[]`.
- **`phenotype_pooled.py`** — `emit_v5_per_endpoint` refactored to follow
  the Q-lock 11 pipeline above; `_draw_v5_boxplots` replaced with
  `_draw_v5_delta_line_with_scatter`. y-axis label now
  `"delta <endpoint> (baseline-subtracted)"`. Removed the `_V5_BOX_WIDTH`,
  `_V5_PHENOTYPE_OFFSETS` constants; replaced with `_V5_JITTER_WIDTH = 0.15`.

### V5 styling defaults locked in code (Task 1b review targets, replaces v2 boxplot styling)

- **Layout:** 4 epoch x-positions (0..3 = pre, acute, sub_acute, chronic);
  lines walk through each epoch center (no horizontal offset between
  phenotype lines — overlap mitigated by color + SEM bars).
- **Line:** `marker="o"`, `markersize=5.0`, `linewidth=2.0`, `capsize=3.5`,
  palette color, `zorder=3`.
- **SEM error bars:** vertical bars on each line at each epoch position;
  same color as line; matplotlib `errorbar` default cap style.
- **Scatter underlay:** `marker="o"`, `s=12.0`, `alpha=0.25`,
  `facecolor=palette_color`, `edgecolor="none"`, `zorder=1`. One dot per
  (animal, session) row.
- **Jitter:** deterministic, seeded (42), uniform ±0.15 epoch widths
  around each epoch center. Same emit reproduces the same scatter.
- **xlim:** `(-0.5, 3.5)` so jitter at epoch 0 + epoch 3 has margin.
- **y=0 reference:** light gray `"0.85"`, `linewidth=0.8`, `zorder=0` —
  drawn by `phenotype_panel` (shared with V4).
- **Y-axis label:** `"delta <endpoint_slug> (baseline-subtracted)"`.

### Tests

`tests/figures/test_phenotype_pooled.py` extended from 16 → **23 tests**.
New tests:

- `test_per_animal_side_baseline_by_side` — baseline = mean of pre rows per
  (animal, side); acute/chronic rows excluded.
- `test_per_animal_side_baseline_no_side` — pools across sides when
  `by_side=False`.
- `test_apply_baseline_delta` — delta = value − baseline mean.
- `test_apply_baseline_delta_drops_unmatched` — sessions whose (animal,
  side) has no baseline row are dropped (won't render).
- `test_jittered_x_positions_within_bounds` — all positions inside
  `±width` of epoch_idx.
- `test_jittered_x_positions_deterministic` — same seed → same positions.
- `test_jittered_x_positions_empty` — `n_points=0` returns `[]`.

All 23 PASS in 0.13s. Existing 16 tests unchanged.

### Re-emit (5 endpoints × V5 × {svg,png} = 10 files)

Wall-time ~3s end-to-end. Used `--figure-types v5` to narrow emit to V5
only (V4 figures from v2 stand untouched).

Per-endpoint spot-check verdicts:

| endpoint | pre line | pre scatter | acute pattern | sub_acute/chronic | scatter density | SEM visible? |
|---|---|---|---|---|---|---|
| `first_lick_accuracy_all` | at 0 ✓ | tight ±0.1 ✓ | severe ipsi −0.7 / contra −0.8 | recovery toward 0 (matches mem #3) | balanced | yes |
| `num_correct_licks_per_trial` | at 0 ✓ | tight ±2 ✓ | severe ipsi −15 / contra −18 | partial recovery | balanced | yes |
| `tongue_lick1_y_peak` | at 0 ✓ | tight ±5 ✓ | severe acute OVERSHOOT +65/+75 | sub_acute SIGN-FLIP to −40/−15; chronic stays negative | balanced (some clustering at acute high values) | yes |
| `tongue_lick1_angle_at_ypeak` | at 0 ✓ | balanced | persistent deficit pattern | matches q_holm < 1e-80 expectation | balanced | yes |
| `tongue_lick1_x_at_ypeak` | at 0 ✓ | balanced | side-asymmetric (ipsi-shift) | persistent contra deficit | balanced | yes |

Memory finding #4 (bimodal sign-flip on `tongue_lick1_y_peak`) is UNAMBIGUOUS in V5 — acute peaks at +65/+75 delta, sub_acute crosses zero to −40/−15. Memory finding #3 (full recovery for `first_lick_accuracy_all`) visible — chronic line returns toward 0.

### Tooling

- `ruff check src/stroke_orofacial/figures/ tests/figures/` → **All checks
  passed!**
- `pytest tests/figures/test_phenotype_pooled.py` → 23 pass in 0.13s.

### Next

STOP at end of Task 1a v3 per Q-lock 9. Priya's Task 1b scaffold review
now covers V4 from v2 + V5 from v3 together. Style decisions at 1b
propagate to spatial (Task 3) + latency_hist (Task 4) + ipsi-shift
(Task 5) before their full emits.

---

## 2026-05-25 — Task 1a v4 palette + label cleanup (branch `phase/9.1-figures`)

Priya 2026-05-25 Task 1a v3 review surfaced two stylistic refinements:

1. **Palette compression:** mild `#fed976` + moderate `#fecc5c` too close
   (both pale yellow-orange; tier distinction unclear). Severe red
   `#e31a1c` could be deeper for stronger end-of-gradient visual.
2. **Y-axis labels too long:** "delta X (baseline-subtracted)" suffix
   should move to a figure-level subheading; y-axis itself should carry
   the short form ("delta X (unit)").

No new kickoff Q-lock — both changes are stylistic refinements within
the existing Q-locks 6 + 11. No DLC detection-rate filter touched (that
work lives on `investigation/dlc-tongue-quality-severe-acute` and lands
separately).

### Change A — palette spread (YlOrRd 9-step indices [2, 4, 6, 7])

| tier             | v3 hex     | v4 hex     | YlOrRd 9-step index |
|------------------|------------|------------|---------------------|
| mild             | `#fed976`  | `#fed976`  | [2] (unchanged)     |
| moderate         | `#fecc5c`  | `#fd8d3c`  | [4] (+2)            |
| moderate-severe  | `#fd8d3c`  | `#e31a1c`  | [6] (+2)            |
| severe           | `#e31a1c`  | `#bd0026`  | [7] (+1, deeper)    |

Source: ColorBrewer YlOrRd 9-step
`['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026']`.

Spreads mild/moderate clearly apart (now pale yellow vs clear orange)
while deepening severe to a richer red.

### Change B — short y-axis labels + two-line suptitle

`ENDPOINT_DISPLAY_NAMES` dict in `_layout.py` maps each endpoint slug to
`(display_name, short_y_label)`:

| slug                              | display_name                          | short_y_label         |
|-----------------------------------|---------------------------------------|-----------------------|
| `first_lick_accuracy_all`         | First-lick accuracy (all trials)      | delta accuracy        |
| `num_correct_licks_per_trial`     | Correct licks per trial               | delta licks / trial   |
| `tongue_lick1_y_peak`             | Tongue lick-1 Y peak                  | delta y peak (px)     |
| `tongue_lick1_angle_at_ypeak`     | Tongue lick-1 angle at Y-peak         | delta angle (deg)     |
| `tongue_lick1_x_at_ypeak`         | Tongue lick-1 X at Y-peak             | delta x (px)          |

Fallback: `(slug, "delta value")` for endpoints not yet in the dict.
Priya iterates on the broader 35-endpoint dict at Task 1b / Task 1c.

`apply_figure_suptitle(fig, display_name, baseline_subtracted)` lays out
the suptitle as:
- Line 1 (bold, size 12): `display_name`
- Line 2 (italic, gray rgb 0.4, size 8): `"baseline-subtracted"` —
  only when ``baseline_subtracted=True``.

Wired in:
- **V4 calls `apply_figure_suptitle(..., baseline_subtracted=False)`** —
  V4 plots cohort per-bin recovery curves of raw `value`, not delta.
  Subheading omitted; y-axis label still uses dict's short_y_label.
- **V5 calls `apply_figure_suptitle(..., baseline_subtracted=True)`** —
  V5 IS delta-from-baseline per Q-lock 11; italic subheading shows.

`apply_side_split_suptitle` refactored to delegate to
`apply_figure_suptitle` (so the side-split + cohort-pooled paths share
the same suptitle styling); cohort-uniformity caveat sentence at the
bottom of the figure preserved.

### V4 y-axis "delta X" semantic mismatch — Task 1b clarification needed

The dict labels (e.g., "delta y peak (px)") are V5-flavored —
they're scientifically accurate for V5 (which IS baseline-subtracted)
but **not literally accurate for V4** (which plots raw values per
bin midpoint, with magnitudes in the original units, not centered at 0).

Implementing per launch-prompt: both V4 + V5 use the same dict's
short_y_label, so V4 y-axis says "delta y peak (px)" even though V4's
numeric range is e.g. 50-200 px (raw), not ±50 px (delta).

**Task 1b question for Priya:** is this intentional (V4 will become
delta-from-baseline in Task 1a v5+), or should the dict expose two
separate y-labels (raw vs delta) so V4 drops the "delta " prefix? Inline
comment in `_layout.py` ENDPOINT_DISPLAY_NAMES flags this.

### Implementation summary

- **`palette.py`** — `_YLORRD_4` updated to the 9-step [2, 4, 6, 7]
  indices; multi-line comment block above the dict explains the
  re-spacing rationale + cites the YlOrRd 9-step palette source.
- **`_layout.py`** — added `ENDPOINT_DISPLAY_NAMES` dict (5 preview
  endpoints + fallback), `get_endpoint_labels(slug)`,
  `apply_figure_suptitle(fig, display_name, *, baseline_subtracted)`.
  Refactored `apply_side_split_suptitle` to delegate to
  `apply_figure_suptitle` and add the cohort caveat footer.
- **`phenotype_pooled.py`** — V4 + V5 side-split + cohort-pooled
  builders all call `get_endpoint_labels` for ylabel + suptitle's
  `display_name`. `set_title=False` on per-axes calls (the figure
  suptitle owns the title now). V4 passes `baseline_subtracted=False`;
  V5 passes `True`.

### Tests

`tests/figures/test_phenotype_pooled.py` extended from 23 → **26
tests**. New tests:

- `test_get_endpoint_labels_known_endpoint` — known slug returns
  ("Tongue lick-1 Y peak", "delta y peak (px)").
- `test_get_endpoint_labels_fallback` — unknown slug returns
  (slug, "delta value").
- `test_endpoint_display_names_has_all_5_preview_endpoints` — dict
  covers the 5 Task 1a preview endpoints.

All 26 PASS in 0.13s.

### Re-emit (5 endpoints × V4 + V5 × {svg, png} = 20 files)

Wall-time ~5s end-to-end. Used `--figure-types v4,v5` to re-emit both.

### Spot-check verdicts

- **Palette spread:** mild yellow vs moderate orange now clearly
  distinguishable (no longer "two shades of pale yellow"). Severe
  `#bd0026` deeper than moderate-severe `#e31a1c` — end-of-gradient
  visual pop achieved.
- **Suptitle layout:** two-line format renders cleanly on
  `first_lick_accuracy_all`, `num_correct_licks_per_trial`,
  `tongue_lick1_y_peak`, `tongue_lick1_angle_at_ypeak`,
  `tongue_lick1_x_at_ypeak`. For shorter display names (e.g.,
  "Tongue lick-1 Y peak") the italic subheading sits very close to
  the bold line — Priya may want to bump the gap from `y=0.94 → 0.91`
  at Task 1b if separation looks too tight.
- **V4 vs V5 distinction:** V4 figures show ONLY the bold suptitle
  (no italic subheading); V5 figures show both. Correct per
  `baseline_subtracted` flag.
- **Y-axis labels:** short form rendered correctly (e.g., "delta
  accuracy", "delta licks / trial", "delta y peak (px)"). No
  parenthetical "(baseline-subtracted)" suffix on y-axis.

### Tooling

- `ruff check src/stroke_orofacial/figures/ tests/figures/` → **All checks
  passed!**
- `pytest tests/figures/test_phenotype_pooled.py` → 26 pass in 0.13s.

### Next

STOP at end of Task 1a v4 per Q-lock 9. Priya's Task 1b scaffold review
covers V4 (v2 + v4 palette/label polish) + V5 (v3 delta + v4 palette/label
polish) together. After Task 1b signoff: Task 1c full-cohort emit
(35 endpoints × V4 + V5 = 70 figures).

Task 1a v5 (FUTURE) will land after the parallel session's DLC
detection-rate filter ships — that's separate scope.

---

## 2026-05-25 — Task 1a v5 style polish (branch `phase/9.1-figures`)

Priya 2026-05-25 Task 1a v4 review surfaced five small style refinements.
None affect data semantics or Q-locks; all live within existing
`figures/` module surface.

### Change A — per-phenotype marker shapes

`PHENOTYPE_MARKERS` dict + `phenotype_marker(tier)` helper added to
`palette.py`. Each tier now has a distinct silhouette in addition to
color, so the figures stay legible for color-blind readers + grayscale
prints.

| tier             | marker | glyph |
|------------------|--------|-------|
| mild             | `"o"`  | circle |
| moderate         | `"s"`  | square |
| moderate-severe  | `"^"`  | triangle up |
| severe           | `"D"`  | diamond |

Applied to V4 line markers (every per_bin data point), V5 foreground
line markers (mean ± SEM at each epoch), AND V5 scatter underlay
(faded per-(animal, session) dots — same shape per tier, smaller +
α=0.25). The matplotlib legend automatically reflects the new shapes via
the line2D `marker` kwarg.

**Scatter-shape decision:** kept per-phenotype scatter shapes (not
fallback-to-circles). The scatter rendering shows mixed silhouettes
without dominating the foreground line — diamonds are slightly visually
heavier than circles at the same `s=12.0` but still readable; the
α=0.25 transparency keeps the underlay sufficiently de-emphasized.

### Change B — suptitle / subheading spacing

`apply_figure_suptitle` updated:
- Title at `y=0.99` (was `y=0.98`).
- Subheading at `y=0.93` (was `y=0.94`).
- Net gap widened from 0.04 → 0.06.

New helper `apply_top_room(fig, top=0.86)` replaces plain
`fig.tight_layout()` in every V4 + V5 builder; reserves the top 14% of
figure height via `tight_layout(rect=[0, 0, 1, 0.86])` so subplots don't
crowd the suptitle. Spot-check on `tongue_lick1_y_peak` V5 confirms the
italic "baseline-subtracted" text now sits clearly below the bold
"Tongue lick-1 Y peak" title with no visual overlap (~36px of
breathing room between bold-bottom and italic-top at default DPI).

### Change C — y-axis label capitalization

`ENDPOINT_DISPLAY_NAMES` dict entries updated:

| slug | new short_y_label |
|---|---|
| `first_lick_accuracy_all` | `"Delta accuracy"` |
| `num_correct_licks_per_trial` | `"Delta licks / trial"` |
| `tongue_lick1_y_peak` | `"Delta Y peak (px)"` |
| `tongue_lick1_angle_at_ypeak` | `"Delta angle (deg)"` |
| `tongue_lick1_x_at_ypeak` | `"Delta X (px)"` |

Fallback updated to `"Delta value"` (capital D). Unit suffixes (`px`,
`deg`) stay lowercase per standard unit conventions.

### Change D — x-tick label relabel + capitalization

`EPOCH_DISPLAY_LABELS` dict + `get_epoch_display(epoch_label)` added to
`_layout.py`. Maps raw `epoch_label` values used in stats input parquets
to publication-ready labels at V5 x-tick render time:

| `epoch_label` (data) | display (figures) |
|---|---|
| `pre` | `Pre-stroke` |
| `acute` | `Acute` |
| `sub_acute` | `Subacute` |
| `chronic` | `Chronic` |

Wired in `_draw_v5_delta_line_with_scatter` — `ax.set_xticklabels(...)`
now calls `get_epoch_display` per epoch. Underlying parquet data is
unchanged (still uses raw `pre`/`acute`/`sub_acute`/`chronic` for stats
consistency).

**No x-tick rotation applied** — "Pre-stroke" + "Subacute" fit at default
0° rotation on the 12×4 inch figure without truncation or adjacent-label
collision. If a future Task 1b/1c iteration needs rotation (e.g.
narrower figure size or longer labels), bump
`ax.tick_params(axis='x', rotation=15)` in `_draw_v5_delta_line_with_scatter`.

### Change E — panel title capitalization

`phenotype_side_split_panels()` panel titles updated:
- `"ipsi (mouse-L)"` → `"Ipsi (mouse-L)"`
- `"contra (mouse-R)"` → `"Contra (mouse-R)"`

Mouse-side designations (`mouse-L`/`mouse-R`) stay lowercase per technical
convention.

### Implementation summary

- **`palette.py`** — `PHENOTYPE_MARKERS` dict + `phenotype_marker()`
  helper.
- **`_layout.py`** — `EPOCH_DISPLAY_LABELS` + `get_epoch_display`;
  `apply_top_room(fig, top=0.86)` for tight_layout-with-top-rect;
  `apply_figure_suptitle` spacing tuned (y=0.99/0.93);
  `phenotype_side_split_panels` capitalized titles;
  `ENDPOINT_DISPLAY_NAMES` capitalized + fallback updated.
- **`phenotype_pooled.py`** — V4 `_draw_v4_traces` uses
  `phenotype_marker(tier)` + `markersize=5.0`; V5
  `_draw_v5_delta_line_with_scatter` uses per-tier marker for both
  scatter underlay AND errorbar foreground (`markersize=6.0`); V5
  x-tick labels go through `get_epoch_display`; all 4 builder funcs
  swap `fig.tight_layout()` → `_layout.apply_top_room(fig)`.

### Tests

`tests/figures/test_phenotype_pooled.py` extended from 26 → **30 tests**
(+4 new + 2 updated):

- `test_endpoint_display_names_capitalized` — every entry's y-label
  starts with `"Delta"` (capital D); X/Y axis names capitalized.
- `test_phenotype_marker_returns_distinct_shapes` — 4 distinct markers
  in canonical order (o, s, ^, D).
- `test_phenotype_marker_unknown_raises` — unknown tier raises KeyError.
- `test_get_epoch_display_mapping` — 4 known epochs + fallback for
  unknown.
- Updated `test_get_endpoint_labels_known_endpoint` + `_fallback` for
  new capitalization.

All 30 PASS in 0.15s.

### Re-emit (5 endpoints × V4 + V5 × {svg, png} = 20 files)

Used `--figure-types v4,v5 --overwrite force`. Wall-time ~5s end-to-end.

### Spot-check verdicts

- **Suptitle/subheading no overlap** (y=0.99/0.93, top=0.86): bold
  title + italic "baseline-subtracted" subheading clearly separated on
  every V5 figure including the previously-tight "Tongue lick-1 Y peak"
  case.
- **Distinct marker shapes visible:** legend on every figure shows 4
  distinct silhouettes (○ □ △ ◇). Foreground line markers in V5 + every
  data point in V4 carry the per-tier shape.
- **Epoch x-tick labels:** "Pre-stroke" / "Acute" / "Subacute" /
  "Chronic" render correctly without truncation. No tick rotation
  applied.
- **Panel titles:** "Ipsi (mouse-L)" / "Contra (mouse-R)" capitalized.
- **V5 scatter underlay:** per-tier shapes preserved through the
  background layer. Visual density manageable; foreground line + SEM
  still dominate.

### Tooling

- `ruff check src/stroke_orofacial/figures/ tests/figures/` → **All checks
  passed!**
- `pytest tests/figures/test_phenotype_pooled.py` → 30 pass in 0.15s.

### Next

STOP at end of Task 1a v5 per Q-lock 9. Priya's Task 1b scaffold review
now covers the fully-polished V4 (v2 base + v4 labels + v5 markers/casing)
+ V5 (v3 delta + v4 labels + v5 spacing/markers/casing) together. After
Task 1b signoff: Task 1c full-cohort emit (35 endpoints × V4 + V5 = ~70
figures).

The DLC investigation Part 3a (on
`investigation/dlc-tongue-quality-severe-acute`) is in flight; when
that work ships a refined interpolation / lick-detector policy + a
re-materialization of the relevant stats inputs, Task 1a v6 (future)
will re-emit consuming the refined data. Style locks at v5 transfer
unchanged to v6.






