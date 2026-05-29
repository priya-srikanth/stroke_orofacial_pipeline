# Migration Log

Each phase of the consolidation records what changed and any intentional behavior
differences vs. the legacy notebooks.

---

## Phase 9.1 Q-lock 14 — Phenotype-pooled spout-behavior recovery (Part 1) + ipsi/contra split-key hardening

**Date:** 2026-05-29
**Tag on merge:** `v9.1-q14-spout-behavior-and-ipsi-contra` (applied post-merge)
**Branch:** `phase/9.1-q14-spout-behavior-and-ipsi-contra`
**Kickoff:** [`docs/prompts/phase-9.1-q14-phenotype-pooled-spout-behavior-kickoff.md`](prompts/phase-9.1-q14-phenotype-pooled-spout-behavior-kickoff.md) (LOCKED v1 + **Addendum #1** re-scope)

**What shipped (Part 1 only — Part 2 deferred, see DECISIONS):**

Four genuinely net-new phenotype-pooled spout-behavior recovery metrics, plus a split-key hardening that makes the V4/V5 phenotype-pooled renderer pool + side-split on lesion-relative **ipsi/contra** coordinates rather than rig-frame L/R, plus a **3-tier phenotype-collapse** variant for the V4/V5 renderer.

The kickoff's original framing (9 metrics × 36 figures, a new recoding module, a parallel `ipsi_contra/` subtree, full Q12/13/13b/13c re-emit) collapsed substantially after the **Stage 0 audit** found: (a) all 8 cohort animals are `stroke_laterality="L"` — so ipsi/contra is a relabel today, no sign-flips fire; (b) 5 of the 9 metrics already existed as phenotype-pooled figures; (c) the recoding map already existed as `AnimalInfo.mouse_side_to_ipsi_contra`, already wired into the Phase 9 materializer's `ipsi_contra` column. Addendum #1 records the full re-scope.

**Net-new metrics:**
- **#6 `accuracy_difference_index`** — `(n_correct − n_incorrect)/(n_correct + n_incorrect)` per cue side; [−1,+1]; NaN on empty denominator.
- **#7 `licks_per_bout`** — median lick-bout size (Phase 8a.2 `find_lick_bouts`: ≤300 ms ILI, ≥2 licks) within each cue side's trials.
- **#8 `d_prime`, #9 `criterion_c`** — session-level SDT for first-lick contra-discrimination: `H = P(first lick contra | contra-cued)`, `FA = P(... | ipsi-cued)`, `d' = z(H)−z(FA)`, `c = −(z(H)+z(FA))/2`. Positive c = bias toward ipsi (predicted post-stroke direction). Extreme-only edge correction (0→0.5/N, 1→(N−0.5)/N).

**Stages (one commit each):**
- **Stage 1** (`68c151e`) — `src/stroke_orofacial/ipsi_contra_recoding.py`: `cue_side_to_ipsi_contra` + net-new `signed_value_to_ipsi_contra` (NaN-safe, self-inverse) + `is_sham` forward hook. Delegates the categorical map to the pre-existing `AnimalInfo.mouse_side_to_ipsi_contra` (single source of truth). 27 tests.
- **Stage 2** (`a7d8584`) — `spout_behavior/endpoints_q14.py` (#6,#7) + `spout_behavior/sdt.py` (#8,#9). 21 tests.
- **Stage 3** (`33f5da9`) — Phase 9 materializer wiring. #6/#7 emit per-(date, side) via the existing `_materialize_scalar_per_session` (gets the `ipsi_contra` column for free). #8/#9 are session-level → new `_materialize_scalar_per_session_global` emits one row per date with `side="global"` → renderer single-panel (Class B). +4 rows in `endpoint_inventory.csv`. Verified read-only on real PS46 data.
- **Stage 4** (`cdccd42`) — split-key hardening. Six `_io` pooling fns gained a backward-compatible `side_col="side"` param (default preserves legacy behavior, so Q13b `phase_aligned_endpoint_stats` is untouched); `phenotype_pooled.py` opts into `side_col="ipsi_contra"`. **Byte-identical regression verified** on the all-L cohort (re-rendered first_lick_accuracy_all + tongue_n_licks + jaw_peak_pos_deflection × V4/V5; date-stripped SVG SHA256 identical).
- **3-tier feature** (`698ed8f`) — `--remap-phenotypes 3tier` merges moderate-severe → moderate (matching the Q12/Q13 `PHENOTYPE_REMAP_3TIER` convention), routing output to a `3_phenotype/` subdir. Previously the V4/V5 renderer only *filtered* tiers; this adds the kickoff Q14-D 3-tier collapse.

**Cohort numbers (on-disk, gitignored pipeline_outputs/):**
- **32** input parquets materialized (8 animals × 4 endpoints), 0 errors.
- **8** new-metric figures at 4-tier (4 metrics × V4/V5) at the canonical `stats/figures/phenotype_pooled/<slug>/`.
- **84** figures at 3-tier (42 scalar endpoints × V4/V5) under `stats/figures/phenotype_pooled/3_phenotype/`, **additive** — the 4-tier figures are untouched.

**Intentional behavior notes:**
- ipsi/contra is a **relabel** on the current all-L cohort (no sign-flips fire). The code is correct-by-construction the moment a right-stroke animal joins.
- d'/c no-response (no-lick) trials **stay in the H/FA denominator** — the literal reading of the kickoff "P(… | contra-cued trial)" conditioning set.

**Forward-pointers:**
- **Part 2 (Q12 / 13 / 13b / 13c + DLC spatial ipsi/contra re-emit) DEFERRED** — a relabel-only no-op on the all-L cohort; revisit when right-stroke animals join the cohort (DECISIONS 2026-05-29).
- **Path-structure normalization (4_tier / 3_tier scope subdirs uniformly, 3_phenotype/ → 3_tier/ rename) deferred to chore/dlc-pooled-phenotype-unification. Q14 figures shipped at current paths; will be moved during that chore's Stage 1.5.**
- 3-tier collapse now lives in the V4/V5 renderer; this phase emitted 3-tier variants for the existing 4-tier-only scalar figures (spout + DLC) into `3_phenotype/`.

**Files modified this PR:**
- `src/stroke_orofacial/ipsi_contra_recoding.py` (NEW)
- `src/stroke_orofacial/spout_behavior/endpoints_q14.py` (NEW)
- `src/stroke_orofacial/spout_behavior/sdt.py` (NEW)
- `src/stroke_orofacial/figures/_io.py` (side_col param on 6 pooling fns)
- `src/stroke_orofacial/figures/phenotype_pooled.py` (ipsi_contra split-key + 3-tier collapse)
- `scripts/phase_9_stats/materialize_inputs.py` (4-endpoint wiring + global-side materializer)
- `.scratch_phase_9/endpoint_inventory.csv` (+4 rows)
- `tests/test_ipsi_contra_recoding.py`, `tests/test_sdt.py`, `tests/test_endpoints_q14.py` (NEW); `tests/test_materialize_inputs.py`, `tests/figures/test_phenotype_pooled.py` (extended)
- `docs/prompts/phase-9.1-q14-phenotype-pooled-spout-behavior-kickoff.md` + `docs/prompts/phase-9.1-q14-addendum-1-stage0-rescope.md` (NEW)
- `docs/MIGRATION_LOG.md` + `docs/DECISIONS.md` (this entry)

---

## Phase 9.1 Q-lock 13c — Tongue Y trajectory extension + stats/results split

**Date:** 2026-05-29
**Tag on merge:** `v9.1-q13c-tongue-y-trajectory`
**Branch:** `phase/9.1-q13c-tongue-y-trajectory`
**Kickoff:** [`docs/prompts/phase-9.1-q13c-tongue-y-trajectory-kickoff.md`](prompts/phase-9.1-q13c-tongue-y-trajectory-kickoff.md) (LOCKED v1 + Addendum #2)

**What shipped:**

Extension of Q-lock 13's phase-aligned mean+SEM trajectory pipeline to a third signal: **`y_centered`** (tongue Y position in spout-midpoint frame = protrusion / amplitude axis). Completes the 2D tongue trajectory story alongside angle (direction) + x (lateral excursion). 99% of the framework is inherited from Q-lock 13 — same 6-test stats package, same 4-scope null-calibration scaffolding, same per-panel YlOrRd phenotype palette, same baseline overlay convention, same output tree.

Plus Addendum #2 — numerical stats CSVs split from the figures tree to a parallel `stats/results/` tree, matching the project-wide convention (`stats/figures/` = SVG/PNG, `stats/results/` = CSVs).

**Cohort numbers:**

- **231 sessions** re-emitted with the new 5-slug per-trial endpoints JSON schema (21 PS46 + 210 PS47-55, ~6.2 s/session × 22 min wall-time fanout).
- **12 figures per canonical 4-tier scope** (4 angle + 4 x + 4 y) at the canonical figures-tree root, plus the SD-band/sd_band/ + null_calibration/ + 3_phenotype/ mirrors.
- **48 CSVs migrated** figures-tree → results-tree (12 root + 12 null_calibration/ + 12 3_phenotype/ + 12 3_phenotype/null_calibration/) per Addendum #2 Q13c-K. Post-migration cohort emits write CSVs to results-tree directly via the new Addendum #2 code-surface split.

**Pipeline stages delivered (per kickoff):**

- **Stage 0** — Prereq verification. Q-lock 13 + 13b tags confirmed on origin; `dlc_centered_spout_midpoint_parquet` y column confirmed; substrate + aggregator + 6-test stats hierarchy + null-calibration scaffolding reachable; pytest --collect-only clean.
- **Stage 1** — Substrate y_snip thread (commit `cc77cee`). Mirrors Q-lock 13b Addendum #2 D2's x_snip threading for y at 5 substrate sites: `_CENTERED_PHASE_ROW_COLUMNS` + `_empty_centered_phase_rows_df` + `_centered_phase_rows_from_peaks` signature + `_trial_arrays` 4-tuple return + 4 helper call sites + the `build_first_n_licks_centered_phase_rows` inline render. Plus two new y scalar endpoints injected into the per-trial JSON `tongue.phase_aligned_endpoints` block: `peak_y_px` (analog of A) and `signed_y_at_max_abs_phase_0_075_px` (analog of C). Q13b's 3-slug schema → 5-slug schema. Backward-compat: legacy bundles without `y_snip` degrade to NaN gracefully.
- **Stage 2** — `y_centered` added to `TRAJECTORY_SIGNALS` (commit `c58f567`). Every downstream consumer takes `signals=TRAJECTORY_SIGNALS` by default — `compute_per_animal_phase_bin_baseline`, `apply_phase_bin_baseline_delta`, `aggregate_phenotype_pooled_phase_bin_mean_sem`, `compute_per_animal_trajectory_scalar`, `compute_per_trial_trajectory_scalar`, `compute_per_session_trajectory_scalar`, `densify_phase_rows_via_interp`, and the 6 `compute_trajectory_*` stats helpers — so the single tuple extension propagates y through the entire pipeline. Per kickoff Stage 2 "probably one parameter; no new module" — confirmed.
- **Stage 3** — Figure renderer extension (commit `9e54e6e`). `SIGNAL_DISPLAY_NAMES["y_centered"] = "Tongue y (spout-midpoint frame, px)"`; `emit_phase_aligned_trajectory_figures` default `signals` switched from hardcoded `("angle_deg", "x_centered")` to `TRAJECTORY_SIGNALS` (single source of truth). 8 → 12 figure count per scope (4 new y figures).
- **Stage 4** — Stats compute + null calibration on y. Reused Q-lock 13 cohort emit script (`scripts/phase_9_1_q13/emit_cohort.py --null-calibration`) on the 8-animal cohort with TRAJECTORY_SIGNALS now including y. Verified the 6-test stats hierarchy holds on the y signal under H0:

  | Test | angle_deg | x_centered | **y_centered** | Verdict |
  |---|---|---|---|---|
  | Paired Wilcoxon (animal n) | 0.0% (0/6) | 0.0% (0/6) | **0.0% (0/6)** | conservative ✅ |
  | MWU per-session | 0.0% (0/24) | 0.0% (0/24) | **0.0% (0/24)** | conservative ✅ |
  | **MWU per-trial** | 45.8% (11/24) | 45.8% (11/24) | **62.5% (15/24)** | **INVALID — y even worse than angle/x** |
  | LMM per-session | 0.0% (0/6) | 0.0% (0/6) | **0.0% (0/6)** | conservative (target ~5%; BH-FDR floor at small N) |
  | Cluster permutation | 0.0% (0/12) | 0.0% (0/23) | **0.0% (0/39)** | conservative ✅ |

  Q-lock 13c-I hierarchy lock (LMM > cluster perm > session MWU > trial-MWU-descriptive-only) transfers cleanly to y. Y has more cluster-perm clusters detected pre-BH-FDR than angle/x — possibly a forward-pointer signal if cluster-level false-discovery becomes a concern at higher post-epoch counts. 21.3 min wall-time.
- **Stage 5** — Cohort emit on 8-animal cohort.
  - **5a PS46 pilot:** 21 OK + 10 SKIP (secondary-spout) + 0 FAIL via [`scripts/phase_7e/reemit_tongue_pertrial_cohort.py --animal PS46`](../scripts/phase_7e/reemit_tongue_pertrial_cohort.py). ~2.2 min wall-time. **12/12 byte-equality** on 3-session × 4-artifact spot check (per_frame, licking_dynamics, cleaned_traces, lick_events parquets all byte-identical to pre-Stage-1). **3/3 JSON sanity:** all 5 endpoint slugs present, slug list lengths == n_trials, 100% finite y endpoint values.
  - **5c 7-animal fanout:** 210 new_OK (PS47-PS55) + 121 SKIP + 0 FAIL in ~22 min via the same script without `--animal`. **21/21 sample sessions PASS** JSON sanity across 7 animals (3 samples × 7 = 21). Per-session NaN rate on y endpoints 0-3%, matching angle/x NaN policy (trials whose lick-1 peak frame didn't land in the synthetic-ILI window).
  - **Canonical 4-tier real-data cohort emit:** 21.9 min, cohort_rows=1,351,800; 12 figures (4 angle + 4 x + 4 y) at the canonical figures-tree root; 14 CSVs at results-tree root per Addendum #2 split.
  - **Canonical 3-tier real-data cohort emit:** 22.0 min; 12 figures at `3_phenotype/` subdir; 12 CSVs at results-tree `3_phenotype/` subdir.
- **Stage 6** — Phase close (this entry).

**Addendum #2 — stats/results vs stats/figures tree split (commit `7a9512e`):**

Q-lock 13 emitted both numerical CSVs AND figure SVGs to `stats/figures/phenotype_pooled/phase_aligned_trajectories/`, mixing them. Addendum #2 (2026-05-29) separates them per the project-wide convention.

- **New constant:** `RESULTS_SUBDIR = "stats/results/phenotype_pooled/phase_aligned_trajectories"` in `figures/phase_aligned_trajectories.py`.
- **Migration:** `scripts/phase_9_1_q13c/migrate_phase_aligned_csvs_to_results.py` moved 48 CSVs (12 root + 12 null_calibration/ + 12 3_phenotype/ + 12 3_phenotype/null_calibration/) from figures-tree → results-tree, preserving relative subpath structure. Migration manifest CSV at `<results-tree-root>/migration_manifest.csv` with (src, dst, size_bytes, sha256) per row. Refuses to run if any destination exists; supports `--dry-run`. Per CLAUDE.md GR7 destructive-ops policy: ran once under Priya per-invocation approval.
- **Code-surface split:**
  - `run_stats_and_figures(..., results_dir=None)` parameter added; CSV writes (9 calls — pooled, baseline, 3 scalars, 5 stats families) route to `results_dir`; figures stay at `output_dir`.
  - New `_derive_results_dir(output_dir, results_dir, resolver)` helper: explicit `results_dir` wins; otherwise swap `"stats/figures/"` → `"stats/results/"` in `output_dir` preserving 3_phenotype/null_calibration/ subdir suffixes; resolver fallback for completely-custom output_dirs.
  - `main()` `--results-dir` CLI flag; 3-tier + null-calibration subdir routing applied in parallel to output_dir and results_dir.
  - Walk manifest (`stage4_walk_manifest.csv`) routes to results-tree (was in figures tree pre-Addendum-#2).
  - `rerender_from_pooled_csv.py`: reads pooled CSV from `results_dir` (csv_dir = res_base_dir / 3_phenotype/ when --3tier); writes figures to figures_dir.

**Output paths (post-Addendum-#2 split):**

```
pipeline_outputs/stats/
├── figures/phenotype_pooled/phase_aligned_trajectories/
│   ├── <signal>_<variant>_<side>_mean_sem_cleaned_trace.svg  × 12
│   ├── sd_band/                                              × 12 SD-band variants
│   ├── null_calibration/                                     × 12 null-cal SVGs
│   └── 3_phenotype/                                          × 12 3-tier SVGs
│       ├── sd_band/                                          × 12
│       └── null_calibration/                                 × 12
└── results/phenotype_pooled/phase_aligned_trajectories/
    ├── phenotype_pooled_phase_bin_mean_sem.csv
    ├── per_animal_phase_bin_baseline.csv
    ├── per_{animal,session,trial}_trajectory_scalar.csv
    ├── trajectory_paired_wilcoxon_bh_fdr.csv
    ├── trajectory_mwu_per_{session,trial}_bh_fdr.csv
    ├── trajectory_lmm_per_session_bh_fdr.csv
    ├── trajectory_cluster_permutation_bh_fdr.csv
    ├── trajectory_{pre,effect}_bootstrap_ci.csv
    ├── stage4_walk_manifest.csv
    ├── migration_manifest.csv
    ├── null_calibration/                                     × same 14 CSVs (no walk manifest)
    └── 3_phenotype/                                          × 14 CSVs
        └── null_calibration/                                 × 14 CSVs
```

**Files added/modified:**

- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (extended — y_snip threaded through `_centered_phase_rows_from_peaks` + `_trial_arrays` + `build_first_lick_centered_phase_rows` + `build_first_n_licks_centered_phase_rows` + `build_all_licks_centered_phase_rows`)
- `src/stroke_orofacial/dlc_kinematics/tongue_phase_aligned_endpoints.py` (extended — endpoints D `peak_y_px` + E `signed_y_at_max_abs_phase_0_075_px` added; JSON schema lock updated; `align_endpoints_to_trial_order` backward-compat for pre-13c DataFrames)
- `src/stroke_orofacial/stats/aggregators.py` (`TRAJECTORY_SIGNALS` gained `"y_centered"`)
- `src/stroke_orofacial/figures/phase_aligned_trajectories.py` (`SIGNAL_DISPLAY_NAMES["y_centered"]` added; emit default switched to `TRAJECTORY_SIGNALS`; `RESULTS_SUBDIR` constant added)
- `scripts/phase_9_1_q13/emit_cohort.py` (results_dir parameter + `_derive_results_dir` helper + `--results-dir` CLI flag + 3-tier/null-cal results_dir routing)
- `scripts/phase_9_1_q13/rerender_from_pooled_csv.py` (reads pooled CSV from results_dir)
- `scripts/phase_9_1_q13c/migrate_phase_aligned_csvs_to_results.py` (NEW — Addendum #2 Q13c-K migration script)
- `tests/test_tongue_pertrial.py` (schema-locked test updated to 5-slug `phase_aligned_endpoints`)
- `tests/test_tongue_phase_aligned_endpoints.py` (extended +20 tests: D + E endpoint classes, bundle integration, substrate y_centered column parity, alignment helper legacy compat)
- `tests/test_stats_aggregators.py` (fixtures extended with y_centered + y_centered_delta columns; existing count assertions updated 2-signal → 3-signal; new `TestYSignalInTrajectorySignals` +5 regression tests including 2-animal × 2-epoch y fixture)
- `tests/test_phase_aligned_trajectories.py` (fixture extended with y_centered signal; existing 8-figures-emit count → 12-figures; new `TestYCenteredTrajectoryFigure` +4 tests + new `TestFiguresResultsTreeSplit` +4 tests for the Addendum #2 split)

**Test suite:** 2124+ passing across the broader surface (29 new tests added this phase: +13 endpoint, +5 y aggregator, +4 y figure, +4 results-tree split, +3 substrate parity).

**Divergences from kickoff:**

- **Output paths (Q13c-H REVISED by Addendum #2):** original Q13c-H lock said figures + CSVs both land at `stats/figures/phenotype_pooled/phase_aligned_trajectories/`. Addendum #2 split them — CSVs now under `stats/results/phenotype_pooled/phase_aligned_trajectories/`. Figures paths unchanged.
- **Filename convention:** kickoff Q13c-H specified `y_raw_<side>_mean_sem_cleaned_trace.svg` (no `y_centered_` prefix). Q13's de-facto convention uses the full signal column name (`angle_deg_raw_L_...`, `x_centered_raw_L_...`); Q13c followed that convention for consistency (`y_centered_raw_<side>_mean_sem_cleaned_trace.svg`).
- **Q13c Stage 2 trajectory emit "held" mid-phase per Priya 2026-05-29 redirect:** Stage 4 ran with `--null-calibration` only; canonical (real-data) trajectory emit deferred to a separate step after Addendum #2 code-surface split landed. Once split landed, both canonical 4-tier + 3-tier emits ran (44 min combined) producing the 24 canonical y figures (12 root + 12 3_phenotype/) at split-correct paths.

**Forward-pointers carried out of Q-lock 13c:**

- **Cluster permutation false-discovery floor on y** — y has more clusters detected pre-BH-FDR than angle/x (39 vs 23 vs 12). BH-FDR knocks all down to 0 under H0 at current cohort N. If post-epoch count grows (e.g., per-week binning instead of pre/acute/sub_acute/chronic), y is the canary for cluster-level false-discovery surfacing.
- **Median+IQR trajectory variant for y** — inherits Q-lock 13's forward-pointer; non-parametric variant.
- **Per-bin significance overlay on y figures** — cluster perm + bootstrap CI both produce per-bin info; render-time enhancement.
- **Successful-trials-filter variant** — kickoff scope-out for Q-lock 13 + 13c.
- **Multi-lick variants for y trajectory** (`first_2_licks`, `all_licks`).
- **Jaw analog** — gated on jaw phase-trajectory substrate (not yet built).
- **Q13c y scalar endpoint stats** — Stage 1 emitted `peak_y_px` + `signed_y_at_max_abs_phase_0_075_px` into the per-trial JSON, but `PHASE_ALIGNED_ENDPOINT_SLUGS` in `stats/aggregators.py` was intentionally NOT extended to include them (Q13c is the trajectory ticket, not a y scalar endpoint stats ticket). A sibling Q13c-scalars ticket could surface y scalar endpoint Wilcoxon/MWU/LMM stats analogous to Q13b's angle/x scalar stats pipeline.

---

## Phase 9.1 Q-lock 13 — Phase-aligned mean+SEM tongue trajectory figures + stats

**Date:** 2026-05-28
**Tag on merge:** `v9.1-q13-mean-sem-trajectory`
**Branch:** `phase/9.1-q13-mean-sem-trajectory`
**Kickoff:** [`docs/prompts/phase-9.1-q13-mean-sem-trajectory-kickoff.md`](prompts/phase-9.1-q13-mean-sem-trajectory-kickoff.md)

**What shipped:**

Eight phase-aligned trajectory figures per scope (2 signals × 2 variants × 2 sides), backed by a full stats package operating on the densified centered-phase substrate. Sibling phase to Q-lock 13b — shares the `build_first_lick_centered_phase_rows` substrate but answers a different question: trajectory-shape (this phase) vs. scalar endpoints (13b).

| Signal | Variant | Output filename slug |
|---|---|---|
| `angle_deg` | raw | `angle_deg_raw_<side>_mean_<sem\|sd>_cleaned_trace.svg` |
| `angle_deg` | Δ from per-animal pre baseline | `angle_deg_delta_<side>_mean_<sem\|sd>_cleaned_trace.svg` |
| `x_centered` | raw | `x_centered_raw_<side>_mean_<sem\|sd>_cleaned_trace.svg` |
| `x_centered` | Δ from per-animal pre baseline | `x_centered_delta_<side>_mean_<sem\|sd>_cleaned_trace.svg` |

Each figure = 4×4 grid (phenotype rows × pre/acute/sub_acute/chronic epoch columns). Per-panel trace color = phenotype YlOrRd shade. SEM canonical; SD variant in `sd_band/` subdir. Shared Y-axis across L+R figures within each (signal × variant) pair. Display window phase ∈ [0.05, 0.95] (edge-bin coverage clip; pooled CSV retains full [0, 1]).

**Pipeline stages delivered:**

- **Stage 1** — Per-animal phase-bin baseline (Q13 lock + 13.1 per-side correction): `compute_per_animal_phase_bin_baseline(phase_rows_long, signals)` returns per-(animal, side, phase_bin, signal) baseline mean from `epoch_label == "pre"` rows. Per-trial-frame-mean grain matches Stage 2's aggregation unit, guaranteeing delta-variant pre column flat at 0 by construction.
- **Stage 2** — Phenotype-pooled mean+SEM+SD aggregator: `aggregate_phenotype_pooled_phase_bin_mean_sem` per (phenotype × epoch × side × phase_bin × signal × variant). Two-pass: per-trial frame-mean (Pass 1) → cross-trial pool with `mean`, `sem = sd/√n`, `sd = std(ddof=1)`, `n_trials`, `n_sessions`, `n_animals` (Pass 2). NaN-aware. SD column added 13.4.
- **Stage 3** — Figure renderer (`figures/phase_aligned_trajectories.py`): 4×4 panel grid; per-panel mean line + ±1 (SEM or SD) band; pre-stroke baseline overlay on post panels; "n=N trials" annotation top-right; SEM/SD tag in suptitle; source-data subtitle (variant-aware); Q-lock 15 cleaned_trace footer; phase display window clip; shared Y across L/R.
- **Stage 4** — Cohort emit script (`scripts/phase_9_1_q13/emit_cohort.py`): walk_cohort → attach_metadata → densify (13.2) → Stage 1 → Stage 2 → emit SEM canonical + SD sd_band/ → all stats. CLI flags: `--remap-phenotypes={none,3tier}`, `--null-calibration`.
- **Stage 5** — Cohort emit on 8-animal cohort (PS46–PS50, PS51, PS54, PS55). 230 OK + 1 SKIP_EMPTY of 231 sessions across 4 scopes (4-tier real, 3-tier real, 4-tier null-calib, 3-tier null-calib). ~25–30 min wall-time per scope.
- **Stage 6.x sub-phases (in-PR follow-ons per Priya iterative review):**
  - **13.1** — Stage 1 per-side baseline keying + per-trial grain correction (delta pre column flat at machine epsilon).
  - **13.2** — Per-trial linear interp at bin centers (`densify_phase_rows_via_interp`) — removes cross-animal-pool jaggedness from ILI-lattice mismatch.
  - **13.3** — Phase display window clip + shared Y across phenotype rows.
  - **13.4** — SD error band alongside SEM (`sd_band/` subdir); 3-phenotype variant (`--remap-phenotypes 3tier`).
  - **13.5** — Default error band SEM (canonical) + SD sd_band/. Per-trial + per-session trajectory scalars + unpaired Mann-Whitney U tests at both grains. Self-describing SEM/SD label in title + filename.
  - **13.6** — LMM (per-session, `scalar ~ epoch + (1|animal)`), Maris-Oostenveld cluster permutation, animal-level bootstrap CI on pre trajectory, null-calibration mode (random pre-split).
  - **13.7** — Animal-level bootstrap CI on the (post − pre) effect trajectory.
  - **13.8** — Shared Y-axis across L+R figures within each (signal × variant) pair.

**Cohort numbers:**

- 231 sessions × 4 emit scopes = 924 session-runs
- Densified substrate: ~1,351,800 rows / scope (vs ~799,347 frame-grained pre-13.2)
- Pooled CSV: 6,752–9,088 rows depending on scope
- Stats CSVs: 6 per scope (Wilcoxon paired, MWU session, MWU trial, LMM, cluster permutation, bootstrap pre + bootstrap effect) × 4 scopes = 24 CSVs total
- 8 SEM SVGs + 8 SD SVGs per scope × 4 scopes = 64 SVGs total

**Stats — null-calibration verified:**

| Test | Real 4-tier | Real 3-tier | Null 4-tier | Null 3-tier | Verdict |
|---|---|---|---|---|---|
| Wilcoxon (animal n) | 0/24 | 0/18 | 0/12 | 0/9 | Calibrated, floor-limited at n=2/4 |
| MWU (session n) | 39/48 | 27/36 | 0/48 | 0/36 | Conservative, usable |
| MWU (trial n) | 42/48 | 30/36 | **22/48 (46%)** | **14/36 (39%)** | **BROKEN** — pseudo-replication |
| **LMM (animal-RE)** | 20/24 | 30/36 | 0/24 | **2/36 (5.5%)** | Calibrated — primary inferential ✅ |
| **Cluster permutation** | 82/145 | 55/112 | 0/66 | 0/72 | Calibrated, bin-localized ✅ |
| **Bootstrap effect CI** (excludes 0) | 5596/6816 (82%, inflated by n=1) | **3032/5136 (59%)** | — | — | 3-tier trustworthy ✅ |

**Recommended paper reporting hierarchy:**
1. Primary inferential: **LMM (3-tier)** — 30/36 cells reject after accounting for per-animal baseline.
2. Phase-axis localization: **cluster permutation (3-tier)** — 55/112 clusters with concentrated effect.
3. Magnitude visualization: **bootstrap effect CI (3-tier)** — per-bin (post − pre) median + 95% band, 59% of bins exclude 0.
4. Supplementary: MWU at session grain (conservative confirmation).
5. **Do not report MWU at trial grain** — broken under H0 (39–46% false-positive rate).

**Divergences from kickoff:**

- Stage 1 — kickoff said baseline keyed by (animal, phase_bin, signal); 13.1 correction added side: (animal, **side**, phase_bin, signal). Required to make delta pre column flat (per-side angle/x sign conventions differ).
- Stage 1 — kickoff said baseline computed per-frame; 13.1 correction switched to per-trial-frame-mean grain (matches Stage 2 pooling unit).
- Stage 2 — kickoff said SEM only; 13.4 added SD column for the alternative band variant. SD eventually became the alternative; SEM remained canonical default.
- Stage 3 — kickoff filename `<signal>_<variant>_<side>_mean_sem_cleaned_trace.svg`. 13.5b added the band slug so SD figures don't claim "mean_sem". New filenames: `<signal>_<variant>_<side>_<mean_sem|mean_sd>_cleaned_trace.svg`.
- Output dir — kickoff said `pipeline_outputs/phase_9_1_figures/...`. Q-lock 13b had already corrected this to `stats/figures/phenotype_pooled/phase_aligned_endpoints/`; Q-lock 13 mirrors at `stats/figures/phenotype_pooled/phase_aligned_trajectories/`.
- 3-phenotype variant + null calibration + LMM + cluster permutation + bootstrap CI — all in-PR follow-on additions beyond the original kickoff scope per Priya iterative direction.

**Files added/modified:**

- `src/stroke_orofacial/stats/aggregators.py` (extended — Stage 1 baseline + delta, Stage 2 mean+SEM+SD, per-trial/per-session/per-animal scalar helpers, densify_phase_rows_via_interp, relabel_pre_for_null_calibration)
- `src/stroke_orofacial/figures/phase_aligned_trajectories.py` (NEW — renderer, compute_trajectory_wilcoxon_stats, compute_trajectory_mwu_stats, compute_trajectory_lmm_stats, compute_trajectory_cluster_permutation_stats, compute_trajectory_bootstrap_pre_ci, compute_trajectory_bootstrap_effect_ci)
- `scripts/phase_9_1_q13/emit_cohort.py` (NEW — driver with --remap-phenotypes + --null-calibration)
- `scripts/phase_9_1_q13/rerender_from_pooled_csv.py` (NEW — fast figure-only iteration from pooled CSV)
- `tests/test_stats_aggregators.py` (extended +50 tests across 13.1/13.2/13.5/13.6)
- `tests/test_phase_aligned_trajectories.py` (NEW +47 tests across 13.3/13.4/13.5/13.5b/13.6/13.7/13.8)

**Test suite:** 121+ passing across the Q-13 surface (aggregators 74/74, trajectories 47/47).

**Forward-pointers:**

- **Additional trajectory-summary scalars** (peak-cycle phase position, AUC of |signal|, per-phase-range mean for early/mid/late phase). Not implemented — peak amplitude is already covered by Q-13b's three scalar endpoints; adding more derived scalars would be redundant with the cluster permutation + bootstrap effect CI which already provide bin-level shape info.
- **Median+IQR trajectory variant** — Q13-B locked mean+SEM/SD; non-parametric variant deferred.
- **Per-bin significance overlay** on figures — cluster permutation + bootstrap effect CI both produce per-bin significance; rendering these onto the trajectory figures as stippled bands or asterisks is a render-time enhancement.
- **Successful-trials-filter variant** — kickoff scope-out.
- **Multi-lick variants** (`first_2_licks`, `all_licks`).
- **Jaw analog** — gated on jaw phase-trajectory substrate.

---

## Phase 9.1 Q-lock 12 — Phenotype-pooled proportion-diff heatmaps + W-2 recovery curves

**Date:** 2026-05-28
**Tag on merge:** `v9.1-q12-proportion-diff-heatmaps`
**Branch:** `phase/9.1-q12-proportion-diff-heatmaps`
**Kickoff:** [`docs/prompts/phase-9.1-q12-proportion-diff-heatmaps-kickoff.md`](prompts/phase-9.1-q12-proportion-diff-heatmaps-kickoff.md) (Addenda #1-5)

**What shipped:**

Phenotype-pooled spatial heatmaps of P(post_epoch) − P(pre) tongue + jaw position by (x, y) bin, computed per-animal-baseline-normalized then phenotype-averaged. Plus a companion W-2 (Wasserstein-2) pre-stroke-normalized recovery curve per (bodypart, side), pooled across animals within phenotype.

Two phenotype-pooling variants, both emitted in parallel for every (bodypart, side):
- **4-tier** (canonical YAML labels): `mild`, `moderate`, `moderate-severe`, `severe`. Mod-severe is a singleton (PS51).
- **3-tier** (merged): `moderate-severe` merged into `moderate` (n=2 moderate pool: PS46 + PS51). Output to `3_phenotype/` subdir.

Total emitted: **16 SVGs** (4 heatmap + 4 W-2 per variant × 2 variants) + 4 audit/manifest CSVs.

**Pipeline stages delivered:**

- **Stage 1** — Per-animal within-baseline proportion-diff math. New module `src/stroke_orofacial/stats/spatial_proportion_diff.py`:
  - `compute_proportion_diff_within(H_pre, n_total_pre, H_post, n_total_post) → D` — pure-math layer with Q17 (Phase 7c.2 Addendum #16) total-in-window-frame denominator and Q12-E `(H_pre==0)&(H_post==0)` no-data NaN mask (no Q12-K magnitude floor).
  - `split_post_dates_by_epoch(animal_info, post_dates)` — bins dates into acute / sub_acute / chronic per `EpochBoundaries`; transitional-gap dates silently dropped.
  - `compute_per_animal_pre_pool` + `compute_per_animal_per_epoch_diff` — orchestrators that call the existing `dlc_spatial.render_on_demand.compute_animal_aggregated_histogram` with the right `trial_group` (Q12-F L/R split) and post-date subset (per epoch).
  - Q12-A within-animal baseline lock: each animal's per-epoch H_post is differenced against ITS OWN pre-pool, NOT a cohort-aggregate baseline.
  - Q12-B bodypart × center_mode lock (per Addendum #3): tongue uses `spout_midpoint`, jaw uses `eye_midpoint`.
- **Stage 2** — Phenotype-pooled spatial aggregator. Extended `stats/aggregators.py` with `aggregate_phenotype_pooled_spatial_diff(per_animal_records, animals)` — NaN-aware mean (`np.nanmean` along the animal axis) producing one record per (phenotype, side, bodypart, post_epoch) with `D_mean`, `n_contributing_animals_per_cell`, `contributing_animals`, per-animal trial counts, and `extent`. Shape/extent mismatches across animals raise.
- **Stage 3** — Heatmap figure renderer. New module `src/stroke_orofacial/figures/phenotype_pooled_proportion_diff.py`:
  - `compute_cohort_shared_vmax(pooled_records) → float` per Addendum #1 Q12-D: 99th percentile of `|D̄|` across ALL panels in all 4 figures. Replaces the original kickoff's `±0.1` fixed range (empirical probe showed `|D|` p99 in 0.001–0.006 range; fixed `±0.1` would have rendered everything uniformly light-grey).
  - `render_phenotype_pooled_proportion_diff_figure(bodypart, side, pooled_records, shared_vmax, phenotype_order)` — `phenotype_order` kwarg added per Addendum #4 to support 3-tier variant. Re-uses legacy `dlc_spatial.render_on_demand._render_proportion_diff_panel` for the per-panel draw, which inherits the Phase 7c.2 Addendum #19/#21/#24 custom cmap (blue→`#d0d0d0`→red) and `set_bad("white")` no-data mask (Addendum #1 Q12-D/E rejected the kickoff's RdBu + grey mask).
  - `emit_phenotype_pooled_proportion_diff_figures` orchestrator with confirm-once-then-force overwrite semantics matching Q-lock 13b's `emit_phase_aligned_endpoint_figures`.
- **Stage 4/5** — Cohort emit driver `scripts/phase_9_1_q12/emit_cohort.py`:
  - Per-animal compute loop (per Stage 1) → 96 records (8 animals × 4 bp/side × 3 epochs) for the 8-animal Q-lock 13b cohort.
  - `--remap-phenotypes={none, 3tier}` flag (Addendum #4) applies `dataclasses.replace` on the animals map to merge moderate-severe into moderate.
  - Per-animal audit manifest CSV with `wall_time_s`, `n_sessions`, `n_trials`, `n_total_frames`, `abs_d_p99`, `w2`.
- **Addendum #5 — W-2 recovery curves** (extends the same pipeline):
  - New module `src/stroke_orofacial/stats/spatial_wasserstein.py`: `compute_wasserstein2_2d(H_pre, H_post, extent) → float`. Each histogram renormalized to sum=1 (isolating spatial-shape comparison from the Q17 tracking-rate composite); squared-Euclidean cost matrix on bin centers in pixel units; exact balanced LP via `ot.emd2` on the union-support nonzero-bin subset; W-2 = `sqrt(emd2)`.
  - Aggregator `aggregate_phenotype_pooled_wasserstein` (in `stats/aggregators.py`): mean ± SEM across phenotype animals (n=1 tiers report `sem=nan`).
  - Figure module `src/stroke_orofacial/figures/phenotype_wasserstein_recovery.py`: one SVG per (bodypart, side) showing W-2 vs post_epoch, lines colored per phenotype, ±SEM error bars, per-animal scatter underlay (α=0.4) at phenotype-jitter offsets.
  - Emit driver extended to compute W-2 alongside D in the per-animal loop and emit 4 W-2 SVGs per variant alongside the 4 heatmap SVGs.

**Output paths** (Q12-J Addendum #2 alignment with q13b's `stats/figures/phenotype_pooled/` tree):

```
pipeline_outputs/stats/figures/phenotype_pooled/
├── proportion_diff_heatmaps/                     # 4-tier (8 SVGs: heatmaps + audit)
│   ├── <bp>_<side>_proportion_diff_cleaned_trace.svg     × 4
│   ├── emit_manifest.csv
│   ├── q12_per_animal_manifest.csv
│   └── 3_phenotype/                              # 3-tier (Addendum #4)
│       ├── <bp>_<side>_proportion_diff_cleaned_trace.svg × 4
│       ├── emit_manifest.csv
│       └── q12_per_animal_manifest.csv
└── wasserstein_recovery/                         # 4-tier (Addendum #5)
    ├── <bp>_<side>_wasserstein_recovery_cleaned_trace.svg × 4
    ├── w2_emit_manifest.csv
    └── 3_phenotype/                              # 3-tier
        ├── <bp>_<side>_wasserstein_recovery_cleaned_trace.svg × 4
        └── w2_emit_manifest.csv
```

**Stage 5 cohort emit results:**

| Variant | n_records | n_pooled | shared_vmax | wall_time | figures |
|---|---|---|---|---|---|
| 4-tier (no W-2 first pass, Stage 5) | 96 | 48 | 0.00373 | 1502 s | 4 heatmaps |
| 3-tier heatmap-only (Stage 5b) | 96 | 36 | 0.00340 | 1970 s | 4 heatmaps |
| 4-tier with W-2 (Stage 5c) | 96 | 48 | 0.00373 | 1917 s | 4 heatmaps + 4 W-2 |
| 3-tier with W-2 (Stage 5c) | 96 | 36 | 0.00340 | 1916 s | 4 heatmaps + 4 W-2 |

8/8 animals × 12 (bp × side × epoch) cells = 96 records per variant, 0 FAIL, 0 SKIP, 0 EMPTY_POOL/EMPTY_EPOCH on every run. Sparse-session WARNINGs surfaced for PS55 acute tongue (severe phenotype, motor deficit → sparse spout_midpoint tracking) but all sparse sessions still contributed valid bins.

**Tests:** 78 new unit tests across Q-lock 12 modules:
- 19 in `tests/test_spatial_proportion_diff.py` (pure-math D + epoch-split + 2-animal within-baseline independence fixture)
- 13 in `tests/test_aggregators_spatial.py` (NaN-aware mean, phenotype bucketing, shape/extent error paths)
- 19 in `tests/test_phenotype_pooled_proportion_diff.py` (vmax computation, figure structure, overwrite semantics, 3-tier `phenotype_order` kwarg)
- 17 in `tests/test_spatial_wasserstein.py` (W-2 pure math: identical→0, deltas→distance, diagonal→`sqrt(dx²+dy²)`, renormalization independence; phenotype-pool aggregator)
- 10 in `tests/test_phenotype_wasserstein_recovery.py` (4-tier vs 3-tier legend, suptitle, per-animal scatter floor count, emit driver)

Full suite passes 1990+ tests after merge (was 1991 before Q12; net +78).

**Intentional behavior differences vs. legacy:**

- Within-animal baseline (Q12-A) — NOT cohort-aggregate baseline. The legacy `_compute_proportion_diff` in `dlc_spatial/render_on_demand.py` already operates per-animal; Q-lock 12 keeps this semantic at the phenotype-pooling layer (each animal's D is fully isolated before phenotype averaging).
- Tongue centering = `spout_midpoint` (Addendum #3) — biologically meaningful for reach-to-spout licking analysis; legacy 7c.2 cohort emits both `tongue_spout_midpoint` and `tongue_eye_midpoint` separately as production families.
- Cmap inherited from legacy (Phase 7c.2 Addendum #19/#21/#24): custom blue→`#d0d0d0`→red diverging cmap with `set_bad("white")` for NaN/no-data cells. Addendum #1 rejected the kickoff's literal `RdBu + grey mask` in favor of this convention.
- Data-driven cohort-wide `shared_vmax` (Addendum #1 Q12-D): NOT the kickoff's `±0.1` fixed range. Empirical probe showed actual phenotype-pooled `|D|` p99 is in the 0.001–0.006 range; `±0.1` would have saturated nothing and rendered everything uniform light-grey.
- W-2 method (Addendum #5): exact POT `ot.emd2` on squared-Euclidean cost; renormalize to sum=1 first (decouples from Q17 tracking-rate ratio); reduced to nonzero-support union to keep LP tractable on 80×80 grids.

---

## Phase 9.1 Q-lock 13b — Phase-aligned tongue endpoint stats

**Date:** 2026-05-27
**Tag on merge:** `v9.1-q13b-phase-aligned-endpoint-stats`
**Branch:** `phase/9.1-q13b-phase-aligned-endpoint-stats`
**Kickoff:** [`docs/prompts/phase-9.1-q13b-phase-aligned-endpoint-stats-kickoff.md`](prompts/phase-9.1-q13b-phase-aligned-endpoint-stats-kickoff.md) (Addenda #1 + #2)

**What shipped:**

Three scalar tongue endpoints per (trial, side) derived from the first-lick-centered phase trajectory (`build_first_lick_centered_phase_rows`, `ili_source="synthetic_only"`), plus phenotype-pooled stats and 12 figures:

| ID | Endpoint | Definition |
|---|---|---|
| A | `peak_angle_deg` | Tongue angle at `phase = 0.5` (lick-1 peak time) |
| B | `signed_angle_at_max_abs_phase_0_075_deg` | Signed `angle_deg` at `argmax(\|angle_deg\|)` over `phase ∈ [0, 0.75]` |
| C | `signed_x_at_max_abs_phase_0_075_px` | Signed `x_centered` at `argmax(\|x_centered\|)` over `phase ∈ [0, 0.75]` |

Endpoints B + C use the "selection by magnitude, reported value signed" convention (Addendum #1 Q6 refinement for C; extended to B per Priya 2026-05-27 direction — positive vs negative tongue angle is meaningful).

**Pipeline stages delivered:**

- **Stage 1** — Per-trial endpoint emitter: new `tongue.phase_aligned_endpoints` JSON block on the existing per-trial tongue endpoints JSON. Substrate extension: `x_snip` threaded through `_trial_arrays` + `_centered_phase_rows_from_peaks` → new `x_centered` column on centered-phase rows. `pre_stroke_median_ili_ms` threaded through `build_tongue_pertrial` (was latent bug — only the bundle-only wrapper injected it; driver path never did).
- **Stage 2** — Per-session aggregator: `median ± IQR ± n_trials` per (animal, date, side, endpoint). New module `stats/aggregators.py`.
- **Stage 3** — Phenotype-pooled aggregator: `median ± IQR ± n_sessions ± n_animals` per (phenotype, epoch, side, endpoint). Baseline-delta computation: per-animal pre-stroke mean subtracted from session medians.
- **Stage 4** — Stats compute: 72-test Wilcoxon signed-rank (paired pre-vs-each-post-epoch, `aggregator="median"`) × single BH-FDR family. NaN-aware for n=1 phenotype tiers (moderate=PS46, mod-severe=PS51). Figure renderer: epoch-binned boxplots with session-level jitter dots, Q-lock 15 marker convention.
- **Stage 5** — Cohort emit: 231 sessions re-emitted across 8 animals (PS46–PS50, PS51, PS54, PS55) via `scripts/phase_9_1_q13b/emit_cohort.py --overwrite force`. Parquets byte-identical (sha256 verified on 4 spot-checks); only JSONs gained the new block. 12 figures (6 raw + 6 Δ baseline-normalized) + 4 CSVs at `pipeline_outputs/stats/figures/phenotype_pooled/phase_aligned_endpoints/`.

**Cohort numbers:**

- 231 sessions re-emitted (21+21+21+22+19+46+38+43)
- 56,325 long-form endpoint rows (finite per-trial values)
- 1,374 per-session aggregates
- 72 Wilcoxon tests (4 phenotypes × 3 endpoints × 2 sides × 3 post_epochs)
- 12 figures (6 raw + 6 delta)

**Addendum #2 divergence locks (Stage 0 findings):**

- D1 — Per-trial storage is JSON (not parquet as kickoff said). `tongue.phase_aligned_endpoints` block added to existing `per_trial/tongue/<animal>/<date>.json`.
- D2 — `x_centered` = raw `x_snip` from `dlc_centered_spout_midpoint_parquet` (no eye-relative re-centering — would conflate eye offset with laterality).
- D3 — Epoch axis = `epoch_label` (Pre/Acute/Subacute/Chronic), NOT `rel_day_bin`. Test count corrected from 24 → 72. Cross-phenotype within-epoch dropped (needs unpaired test class — forward-pointer).
- D4 — Aggregator helpers land in `stats/aggregators.py` (not `figures/_io.py` which is figure-private + mean-based).

**Files added/modified:**

- `src/stroke_orofacial/dlc_kinematics/tongue_phase_aligned_endpoints.py` (NEW)
- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (substrate extension + ILI threading fix)
- `src/stroke_orofacial/dlc_kinematics/__init__.py` (exports)
- `src/stroke_orofacial/stats/aggregators.py` (NEW)
- `src/stroke_orofacial/stats/__init__.py` (exports)
- `src/stroke_orofacial/figures/phase_aligned_endpoint_stats.py` (NEW)
- `scripts/phase_9_1_q13b/emit_cohort.py` (NEW)
- `tests/test_tongue_phase_aligned_endpoints.py` (29 tests, NEW)
- `tests/test_stats_aggregators.py` (22 tests, NEW)
- `tests/test_phase_aligned_endpoint_stats.py` (12 tests, NEW)
- `tests/test_tongue_pertrial.py` (schema-lock test extended)

**Test suite:** 1878+ passing (63 new tests across 3 new test files + 1 extended).

**Forward-pointers:**

- Cross-phenotype within-epoch comparison (Mann-Whitney U or mixed-effects with phenotype fixed effect) — out of scope, needs unpaired test.
- Minimum-trials-per-session filter (`--min-trials` CLI arg or config constant) — architecture supports it at the aggregator layer, not yet wired.

---

## Phase 0 — Repo skeleton

**Date:** 2026-04-17

**What was done:**
- Created full directory tree per §3 of DESIGN.md.
- Added `pyproject.toml` (package `stroke_orofacial`, editable install).
- Added `environment-mac.yml` (from current `frsb` env) and `environment-windows.yml` (placeholder).
- Added `.gitignore`, `.gitattributes`, `README.md`.
- Added stub config files: `configs/paths.yaml`, `configs/animals.yaml`, `configs/defaults.yaml`.
- Added all stub Python modules under `src/stroke_orofacial/` (empty, no logic).
- Added stub notebooks under `notebooks/` (title + USER INPUTS cell only).
- Added `tests/test_import.py` (single import smoke test).

**Behavior differences vs. legacy:** None (no analysis logic implemented yet).

**Exit criteria met:**
- [x] `pip install -e .` succeeds in `frsb`.
- [x] `pytest tests/` passes (1 test: import smoke test).

---

## Phase 1 — Paths + manifest + animals metadata

**Date:** 2026-04-17

**What was done:**

### Sub-phase 1a: PathResolver
- Implemented `src/stroke_orofacial/paths.py` with `PathResolver` class.
- Loads `configs/paths.yaml`, auto-detects platform (Darwin/Windows), supports
  `STROKE_PIPELINE_MACHINE` env var override.
- Convenience methods: `dlc_output_dir()`, `alignment_templates_dir()`,
  `alignment_template()`, `session_processing_out()`.
- Added `tests/test_paths.py` (15 tests, including integration tests against
  the live MICROSCOPE mount).

### Sub-phase 1b: SessionManifest + animals loader
- Implemented `src/stroke_orofacial/animals.py` with `AnimalInfo`, `Exclusion`
  dataclasses and `load_animals()` / `get_animal()` YAML loader.
- Implemented `src/stroke_orofacial/manifest.py` with `SessionManifest`
  dataclass and `build_manifest()` function.
- `build_manifest()` discovers filtered DLC files by date glob, resolves
  alignment templates, computes stroke-relative day/phase, and checks
  analysis-type-specific exclusions.
- Added `tests/test_animals.py` (14 tests) and `tests/test_manifest.py`
  (9 tests, including integration test against real PS46 session 2025-03-07).

### Sub-phase 1c: animals.yaml population
- Transcribed master animal metadata from two legacy notebooks into
  `configs/animals.yaml`:
  - `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  - `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
- Cross-checked: stroke dates, session ranges, and analysis params are
  identical across both notebooks' three repeated declarations each.
- Included per-animal `analysis_params` (`break_thr_trialmax`,
  `break_thr_alllicks`) which vary by animal.

**Convention established:** `stroke_date` is the date of the **last pre-stroke
session**. The stroke is induced after that day's behavioral session. Sessions
on `stroke_date` are baseline; only sessions strictly after are post-stroke.
This matches the legacy notebook semantics where `d0` is the last baseline day.

**Intentional behavior differences vs. legacy notebooks:**

1. **Exclusions upgraded to universal (`applies_to: [all]`).**
   In the legacy code, exclusions were declared per-notebook:
   - Tongue notebook excluded PS54: 2025-04-26 only.
   - Jaw notebook excluded PS55: 2025-04-27 and 2025-04-28 only.
   - PS51: 2025-04-26 was commented out in both.
   In the consolidated `animals.yaml`, all four exclusions are now universal
   (`applies_to: [all]`) because the underlying reasons (Rose Bengal sham
   with delayed licking; messed up reward delivery) affect all analyses, not
   just the one where they happened to be declared. PS51: 2025-04-26 is now
   active (was commented out in legacy). This was reviewed and approved by
   Priya before transcription.

**Exit criteria met:**
- [x] `pytest tests/` passes (39 tests).
- [x] `ruff check src/` clean.
- [x] `configs/animals.yaml` reviewed and approved by Priya.

---

## Phase 2 — Spout behavior processing

**Date:** 2026-04-18

**Legacy file disambiguation (per CLAUDE.md 3-tier rule):**

- **Canonical notebook:** `batch_process_20260410PS.ipynb` (Rule 1: latest
  YYYYMMDD). Deprecated: `batch_process.ipynb` (undated),
  `batch_process_20250503PS.ipynb` (superseded).
- **Python helpers (6 unambiguous):** `process_ws_signals.py`,
  `find_licks_and_rewards.py`, `find_running_bouts.py`,
  `find_grooming_bouts.py`, `find_quiet_bouts.py`,
  `find_peri_reward_periods.py` — all only-version (Rule 1 trivially resolved).
- **Treadmill calibration (Rule 3 → Priya confirmed):**
  `calibrate_and_smooth_treadmill_signal_PS.py` is canonical. The notebook
  imports `_patched` (stale reference); no file with that name exists. The
  plain `calibrate_and_smooth_treadmill_signal.py` (2025-05-03) lacks the
  offset-override logic. `_PS.py` (2026-04-10) was confirmed canonical by
  Priya.

**What was done:**

### Sub-phase 2a: Wavesurfer I/O + treadmill calibration
- Implemented `src/stroke_orofacial/spout_behavior/wavesurfer_io.py`:
  `load_wavesurfer_signals()`, `find_wavesurfer_file()` (glob-based, excludes
  "kHz" files), `calibrate_treadmill()`, `smooth_treadmill()`,
  `resolve_treadmill_offset()`.
- Ported from `process_ws_signals.py` and
  `calibrate_and_smooth_treadmill_signal_PS.py`.
- Updated `configs/paths.yaml`: added `microscope_pipeline_outputs` and
  `wavesurfer_raw` (list mount: MICROSCOPE primary, Mac-local fallback).
- Created `configs/session_overrides.yaml` with per-session treadmill offset
  overrides (moved out of `defaults.yaml`).
- Populated `configs/defaults.yaml` with all cohort-wide params from legacy
  `params.json` (authoritative from canonical notebook).
- Updated `PathResolver`: list-mount support for fallback chains,
  `pipeline_outputs()`, `wavesurfer_dir()`.
- Added `bnpm` and `pywavesurfer` to `pyproject.toml` dependencies.

### Sub-phase 2b: Lick detection + reward detection
- Implemented `src/stroke_orofacial/spout_behavior/lick_detection.py`:
  `find_licks_and_rewards()` (main entry), `find_reward_indices()`,
  double-threshold lick detection with asymmetric lockout cleaning.
- Ported from `find_licks_and_rewards.py`.

### Sub-phase 2c: Bout detection
- Implemented `src/stroke_orofacial/spout_behavior/bouts.py`:
  `find_running_bouts()`, `find_grooming_bouts()`, `find_quiet_bouts()`,
  `find_peri_reward_periods()`.
- Ported from 4 legacy modules.

### Sub-phase 2d: Session orchestrator + notebook + parity check
- Implemented `src/stroke_orofacial/spout_behavior/session_processing.py`:
  `process_session()`, `process_animal()` with overwrite protection
  ("skip" / "prompt" / "force").
- Created `src/stroke_orofacial/config_loader.py`: `load_defaults()`,
  `load_session_overrides()`, `get_session_params()` (deep-merge),
  `check_merge_required()` (raises NotImplementedError for deferred merges).
- Created `notebooks/00_session_processing.ipynb` (thin orchestrator with
  USER INPUTS cell).
- Per-session `params.json` at `params/{animal}/{YYYYMMDD}.json` for full
  run provenance.

### Sub-phase 2e: Tests + MIGRATION_LOG
- `tests/test_wavesurfer_io.py` — wavesurfer loading, treadmill calibration,
  file discovery, integration against real PS46/20250307.
- `tests/test_lick_detection.py` — reward detection, lick onset/offset,
  lockout cleaning, parity against `session_processing3/`.
- `tests/test_bouts.py` — running/grooming/quiet/peri-reward unit tests,
  parity against `session_processing3/` for PS46/20250307.
- `tests/test_session_processing.py` — params.json structure, skip-path
  behavior, integration parity for both PS46 sessions.
- `tests/test_config_loader.py` — deep-merge, override loading, merge-required
  check.

**Parity verified** on two sessions (11 arrays each, all exact match):
- PS46 / 2025-03-07 (baseline, day -6): 11/11 PASS
- PS46 / 2025-03-20 (post-stroke, day +7): 11/11 PASS

Boolean masks and integer index arrays: `np.array_equal`.
Treadmill float arrays: `np.allclose(rtol=1e-10, atol=1e-10)`.

**Intentional behavior differences vs. legacy `session_processing3/`:**

1. **Per-session params.json** at `params/{animal}/{YYYYMMDD}.json` instead of
   a single root-level `params.json`. Each file records `session_id`, `animal`,
   `date`, `run_timestamp`, `skipped`, the merged `params` actually used, and
   a `processing_log` of skip/overwrite decisions per output type.

2. **params.json always written, even on skip.** When `overwrite="skip"` and
   all outputs exist, the per-session `params.json` is still written with
   `skipped: true`. This provides a full audit trail of what ran vs. skipped.

3. **Treadmill offset_overrides moved** from `defaults.yaml` into
   `configs/session_overrides.yaml` under a structured `overrides:` key.
   `defaults.yaml` contains only the cohort-wide default offset value.

4. **Output location on MICROSCOPE** at `pipeline_outputs_v2/spout_behavior/`
   instead of Mac-local `session_processing3/`.

5. **Cross-platform wavesurfer path support.** `wavesurfer_raw` logical root
   tries MICROSCOPE first, falls back to Mac-local. Pipeline currently runs
   from Mac using the local fallback; will run from Windows once Priya rsyncs
   the wavesurfer data to MICROSCOPE (separate task).

**Known constraints:**
- Raw wavesurfer data currently Mac-local only; mirror to MICROSCOPE pending.
- PS48 / 2025-03-14 session merge (two wavesurfer files) is documented in
  `configs/session_overrides.yaml` under `merges:` but implementation is
  deferred beyond Phase 2. `check_merge_required()` raises
  `NotImplementedError` if this session is processed.
- `trial_segmentation.py` remains a stub — legacy notebook does not segment
  trials; that concept belongs to later phases.

**Exit criteria met:**
- [x] `pytest tests/` passes (103 tests).
- [x] `ruff check src/` clean.
- [x] Parity verified on PS46 baseline + post-stroke sessions.

---

## Phase 2.5 — Tone detection + per-side peri-periods

**Date:** 2026-04-18

**Purpose:** Restore features present in Rich's upstream repo but dropped in
Priya's fork (which Phase 2 ported from). Needed for cue-aligned analyses
in Phase 4+.

**Source:** Rich's upstream `facerhythm_stroke_biomarker_exp` repo:
- `find_licks_and_rewards.py` — adds `Tone_L`/`Tone_R` detection alongside
  rewards (same rising-edge algorithm, same threshold).
- `find_peri_reward_and_tone_periods.py` — produces 4 per-side boolean masks
  instead of a single consolidated `peri_reward_bool`.

Both files are only-versions in the upstream repo (Rule 1 trivially resolved).

**What was done:**

### Sub-phase 2.5a: Tone detection
- Added `find_tone_indices()` to `lick_detection.py` — same rising-edge
  detection as rewards, applied to digital `Tone_L`/`Tone_R` channels.
- Extended `find_licks_and_rewards()` return dict to include `Tone_L`/`Tone_R`.

### Sub-phase 2.5b: Per-side + peri-tone periods
- Added `find_peri_reward_and_tone_periods()` to `bouts.py` producing 4
  per-side boolean masks: `peri_reward_L`, `peri_reward_R`, `peri_tone_L`,
  `peri_tone_R`. Window: `[0, 6]` seconds (same as consolidated peri-reward).
- Existing `find_peri_reward_periods()` unchanged (backward compat).
- Added `find_peri_reward_and_tone_periods` section to `configs/defaults.yaml`.

### Sub-phase 2.5c: Orchestrator integration
- `licks_and_rewards` NPZ now includes `Tone_L`, `Tone_R` index arrays.
- `peri_reward_periods` NPZ now includes `peri_reward_L`, `peri_reward_R`,
  `peri_tone_L`, `peri_tone_R` boolean masks alongside existing
  `peri_reward_bool`.

### Sub-phase 2.5d: Tests + MIGRATION_LOG
- Added tone detection unit tests to `test_lick_detection.py`.
- Added per-side peri-period unit tests to `test_bouts.py`.
- Added integration tests verifying new keys are present in
  `test_session_processing.py`.

**Strictly additive:** All 11 original parity arrays unchanged in value.
Verified on PS46 20250307 + 20250320.

**Note on output subdir naming:** The `peri_reward_periods/` output subdir now
contains both reward AND tone period masks despite its name. This naming is
kept for parity with `session_processing3/`. Future renaming is a non-goal;
the NPZ key names (`peri_reward_L/R`, `peri_tone_L/R`) make the contents
unambiguous.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Original parity still holds (11/11 arrays exact on both sessions).
- [x] New keys present and non-trivial on PS46 20250307 + 20250320.

---

## Phase 3 — Wavesurfer ↔ Video ↔ DLC Alignment

**Date:** 2026-04-18

**Legacy file disambiguation (per CLAUDE.md 3-tier rule):**

- **Canonical notebook:** `batch_process_alignment_20251216PS.ipynb` (Rule 1:
  latest YYYYMMDD). Non-canonical: `playground.ipynb` (undated, older).
  Notebook used as orchestrator reference only — the core algorithm lives in
  the helper module.
- **Core helper:** `make_alignment_templates_20251216.py` in Rich's upstream
  repo (`facerhythm_stroke_biomarker_exp/analysis/alignment/`). Only version
  found (Rule 1 trivially resolved). Note: lives in a different repo from the
  notebook — this is by design; Rich wrote the algorithm, Priya orchestrates.

**What was done:**

### Sub-phase 3a: Path setup + alignment template loading
- Added `camera_raw` logical root to `configs/paths.yaml` pointing to
  MICROSCOPE camera data (read-only).
- Added `PathResolver.camera_dir(date, animal)`.
- Implemented `src/stroke_orofacial/alignment/templates.py`:
  `load_alignment_template()`, `pick_camera_csv()`, `load_camera_csv()`,
  `discover_video_files()`.
- Added `alignment` section to `configs/defaults.yaml` with all sync/matching
  parameters from the legacy notebook.

### Sub-phase 3b: Core alignment functions + SessionManifest integration
- Ported `make_alignment_templates_20251216.py` into
  `src/stroke_orofacial/alignment/frame_sync.py`: `_normalize_minmax_robust()`,
  `_find_rising_edges()`, `_align_edge_sequences()`, `_safe_interp1d()`,
  `make_alignment_template()`.
- Created `src/stroke_orofacial/alignment/timebase.py`: `AlignmentResult`
  dataclass, `ws_sample_to_session_time()`, `frame_to_session_time()`,
  `session_time_to_frame()`, `load_or_compute_alignment()`.
- **SessionManifest integration (amendment 3):** `build_manifest()` now
  populates `wavesurfer_file` (from `wavesurfer_raw` path) and `video_files`
  (from `camera_raw` path, cam2). Both are optional — gracefully return
  None/empty if data isn't mounted.

### Sub-phase 3c: Alignment orchestrator notebook
- Created `notebooks/02_alignment.ipynb` (thin orchestrator, cam2 only).
- Default behavior: load existing templates from `alignment_templates/cam2/`,
  recompute only if missing.
- Overwrite modes: skip/prompt/force (matching Phase 2 convention).
- Per-session `params.json` at `pipeline_outputs_v2/alignment/params/{animal}/{YYYYMMDD}.json`.

### Sub-phase 3d: Parity check
- Re-computed alignment templates for PS46 2025-03-07 (baseline, day -6) and
  PS46 2025-03-20 (post-stroke, day +7).
- Compared against existing `alignment_templates/cam2/PS46/` NPZs.

**Parity results (per amendment 1 tolerances):**

| Array | PS46/20250307 | PS46/20250320 | Tolerance |
|-------|--------------|--------------|-----------|
| `sig_camIdx__idx_ws` | PASS | PASS | `rtol=1e-10` |
| `sig_wsIdx__idx_cam` | PASS | PASS | `rtol=1e-10` |
| `slope_ws_per_camFrame` | PASS (4.0062) | PASS (4.0058) | `rtol=1e-8` |
| `intercept_ws_samples` | PASS (-8747.4) | PASS (-9133.1) | `rtol=1e-8` |

No tie-break differences observed in the pattern matcher. NaN patterns at
array edges match exactly between re-computed and existing templates.

### Sub-phase 3e: Tests + MIGRATION_LOG
- `tests/test_frame_sync.py` — normalization, edge detection, sequence matching,
  interpolation, full template generation with synthetic sync signals.
- `tests/test_timebase.py` — time-base converters, AlignmentResult, integration
  tests loading/recomputing real alignment templates.
- `tests/test_alignment_templates.py` — template loading, camera CSV discovery,
  video file discovery, SessionManifest integration test (amendment 3).

**Intentional behavior differences vs. legacy:**

1. **Default: load existing, compute if missing.** Legacy notebook always
   recomputes. New pipeline loads existing `alignment_templates/cam2/` NPZs
   by default, recomputing only when the template is missing. This leverages
   already-validated alignment work.
2. **cam2 only.** Legacy notebook processes cam1-4. New pipeline processes
   only cam2 (the DLC camera). Other cameras can be added later.
3. **Per-session params.json** at `alignment/params/{animal}/{YYYYMMDD}.json`
   (matching Phase 2 convention). Legacy had no per-session params record.
4. **SessionManifest now populates `wavesurfer_file` and `video_files`.**
   Phase 1 left these as None/empty. Now resolved from `wavesurfer_raw` and
   `camera_raw` paths respectively.

**§4.4 time-base contract confirmed:**
- Wavesurfer sample rate: 1000 Hz (confirmed in Phase 2).
- `ws_samples → session_time_s`: divide by 1000.
- `video_frame_index → session_time_s`: via `sig_wsIdx__idx_cam[frame] / 1000`.
- `dlc_frame_index → session_time_s`: equals video_frame_index by construction.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Parity verified on PS46 baseline + post-stroke sessions.
- [x] `SessionManifest.wavesurfer_file` and `.video_files` populated.

---

## Phase 4 — DLC I/O + Centering

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1: siblings vs
duplicates, DECISIONS.md "2026-04-18 — Disambiguation rule refined"):

- **Canonical notebook:** `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`
  (Rule 1: latest YYYYMMDD within the whole-session parquet builder family).
- **Superseded:** `20260111_DLC_analysis_build-parquet_tongue.ipynb` — same
  family (both whole-session parquet builders), earlier date → superseded.
- **Siblings (Phase 7 scope, not Phase 4):**
  `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and
  `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` — distinct scope
  markers (`_tongue` vs `_jaw`), both ws-aligned kinematics notebooks. Each
  will be ported independently in Phase 7.
- **Archived:** 37 files in `old_code/` — all Deprecated.
- **No external .py helpers** — all production functions defined inline in
  cell 8 of the canonical notebook.

**Dead code classification** (65 cells):
- Cells 0-11: **Production** (imports, file discovery, centering pipeline,
  cache save/load). Ported.
- Cells 12-64: **Exploratory** (heatmaps, kinematics, PSD, statistics,
  colormap testing) or **Deprecated** (empty cells). Not ported. All
  downstream of centering — Phases 5-9 scope.
- No Ambiguous cells.

**What was done:**

### Sub-phase 4a: DLC loader
- Implemented `src/stroke_orofacial/dlc_io/loaders.py`: `read_dlc()` (H5
  preferred, CSV fallback, 3-level MultiIndex flattening to
  `{bodypart}_{coord}`), `discover_dlc_filtered_files()`.
- Added `tables` (pytables) to `pyproject.toml`.

### Sub-phase 4b: DLC centering
- Implemented `src/stroke_orofacial/dlc_io/centering.py`: `CenterMode` enum,
  `compute_center()` (nose / spout_midpoint / eye_midpoint), `apply_centering()`.
- Added `dlc_centering` section to `configs/defaults.yaml`:
  `likelihood_threshold=0.7`, `default_mode="nose"`, `compression="zstd"`.

### Sub-phase 4c: Parquet I/O + orchestrator
- Implemented `src/stroke_orofacial/dlc_io/parquet.py`:
  `write_centered_parquet()` (atomic tmp→rename), `read_centered_parquet()`,
  `build_centered_parquet()` (pure function, no module-level state — per
  DECISIONS.md "iterate over animals without notebook restart").
- Created `notebooks/11_dlc_build_parquets.ipynb` with USER INPUTS cell.
  Builds all three center modes by default.

### Sub-phase 4d: Parity check
- All three centering modes verified against legacy `_dlc_cache_centered_*`
  parquets for PS46/20250307.

**Parity results:**

| Mode | Frames | Cols | Dtypes | assert_frame_equal | Hash |
|------|--------|------|--------|-------------------|------|
| nose | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | c23dc714 ✓ |
| spout_midpoint | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | 2a6efb6a ✓ |
| eye_midpoint | 931,834 = src = legacy | 39 | float32 | PASS (atol=1e-6) | b13af51c ✓ |

All frames preserved (no 975K cap — per DECISIONS.md "keep all frames").

### Sub-phase 4e: Tests + MIGRATION_LOG
- `tests/test_dlc_loaders.py` — file discovery, CSV fallback, integration
  test loading real DLC H5.
- `tests/test_dlc_centering.py` — all three center modes, likelihood gating,
  float32 preservation, centering arithmetic.
- `tests/test_dlc_parquet.py` — hash signatures, write/read roundtrip, skip
  existing, integration parity tests for all three modes.

**Intentional behavior differences vs. legacy:**

1. **All frames kept (no 975K cap).** Legacy `20260111` notebook filtered to
   first 975K frames. The canonical `20260323` notebook's build cell has no
   cap. Our pipeline follows `20260323`: output row count equals source DLC
   frame count.
2. **Overwrite protection: skip/force only (no prompt).** DLC parquets are
   deterministically derivable from source DLC H5 files, so interactive
   prompt-mode adds less value than in Phase 2 where session-processing
   outputs took longer to rebuild.
3. **Output location on MICROSCOPE** at
   `pipeline_outputs_v2/dlc_analysis/centered_{mode}/{animal}/`.
   Legacy cached in `O2_analysis/{animal}/_dlc_cache_centered_{mode}/`.
4. **Per-session params.json** at `dlc_analysis/params/{animal}/{YYYYMMDD}.json`.
5. **Stateless orchestrator.** `build_centered_parquet()` is a pure function
   callable in animal × date × mode loops without accumulating state or
   requiring notebook restart.
6. **Output directory structure** (separate subdirs per center_mode) directly
   supports Phase 5+ per-(bodypart, center_mode) plotting parameters (per
   DECISIONS.md "Phase 5+ downstream analyses").

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Parity verified for all three centering modes on PS46/20250307.
- [x] All frames preserved (frame count == source DLC frame count).

---

## Phase 4.5-lite — Eye-midpoint centering defaults + Phase 5 x_range + axis-limit fix

**Date:** 2026-04-20

**Scope-reduction finding at session start:** the kickoff
(`docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`) proposed
~150-200 lines across 5 sub-phases. Two of those are already satisfied by
Phase 4:
- **§4.5a** (add `eye_midpoint` branch to `compute_center`): already present
  in [src/stroke_orofacial/dlc_io/centering.py:104-112](../src/stroke_orofacial/dlc_io/centering.py#L104-L112);
  test at [tests/test_dlc_centering.py:49-54](../tests/test_dlc_centering.py#L49-L54).
- **§4.5c** (regenerate centered parquets): Phase 4 built all three modes
  cohort-wide; hashes (`c23dc714` / `2a6efb6a` / `b13af51c`) preserved.
  Per 2026-04-20 Priya decision: hash-verify instead of rebuild.

**Scope-expansion finding mid-session:** while investigating axis limits,
discovered a pre-existing bug in Phase 5: `plot_heatmap` / `build_histogram` /
`build_stats_grid` used hardcoded default `x_limits=(-200, 200)` /
`y_limits=(50, 550)` and never consumed `per_center_mode.xlim/ylim` from
config. Evidence: the sole existing Phase 5 output
`stroke_orofacial_pipeline_outputs/dlc_analysis/spatial_whole_session/nose_nose/PS46/heatmap_20250307.png`
is **entirely blank** (defaults are un-centered-pixel ranges; data is
centered at ~0). DECISIONS 2026-04-18 had stipulated per-(bodypart, center_mode)
axis limits but the code never actually read them. Priya approved expanding
Phase 4.5-lite scope to fix this bug + add `x_range` pre-histogram filter
support simultaneously.

### Sub-phase 4.5-A — Per-bodypart `center_mode` defaults in `configs/defaults.yaml`

Added `center_mode` key under every `dlc_spatial.bodyparts.{bp}` block (13 total):
- `tongue` → `spout_midpoint` (anatomically spout-anchored)
- `jaw`, `nose`, all 6 whiskers → `eye_midpoint` (sweep winner)
- `L_eye`, `R_eye`, `L_spout`, `R_spout` → their own fiducial regime
  (null-baseline control for Phase 9 significance testing)

Fiducial bodypart blocks (`L_eye`, `R_eye`, `L_spout`, `R_spout`) are new;
they contain `likelihood_threshold: 0.80` and `center_mode` only. No
`cmap` / `per_center_mode` since no heatmaps are generated for fiducials
today; downstream code tolerates the missing keys via `.get()` fallbacks.

The top-level `dlc_centering.default_mode: "nose"` is retained as ultimate
fallback; a comment marks per-bodypart defaults as the primary source.

### Sub-phase 4.5-B — `default_center_mode()` accessor

Added to [src/stroke_orofacial/config_loader.py](../src/stroke_orofacial/config_loader.py):
resolution order is `dlc_spatial.bodyparts.{bp}.center_mode` →
`dlc_centering.default_mode`. Validates against `CenterMode` enum; raises
`ValueError` on unknown mode, `KeyError` when nothing configured.

### Sub-phase 4.5-C — `TestDefaultCenterMode` in `tests/test_config_loader.py`

Six test cases: movement bodyparts, fiducials, fallback path, unknown
bodypart, empty-config KeyError, invalid-mode ValueError. All pass against
the real `configs/defaults.yaml`.

### Sub-phase 4.5-D — Notebook 12 stale `CENTER_MODES` fix

[notebooks/12_dlc_spatial_reward_aligned.ipynb](../notebooks/12_dlc_spatial_reward_aligned.ipynb):
added `"eye_midpoint"` to `CENTER_MODES`. Previously `["nose", "spout_midpoint"]`
— omission predates the sweep; no DECISIONS entry ever explained it.

### Sub-phase 4.5-E — Cohort-wide parquet hash baseline

[scripts/hash_centered_parquets.py](../scripts/hash_centered_parquets.py)
walks `{pipeline_outputs}/dlc_analysis/centered_{mode}/{animal}/*.parquet`
for all 8 animals × all 3 modes, computes SHA-256 content hashes plus the
`_param_sig` from the filename, and verifies Phase 4 parity.

Baseline as of 2026-04-20 (only PS46/20250307 exists on disk; other 7
animals not yet built):

| Animal | Date | Mode | param_sig | content_sha256[:12] | Size (MB) |
|--------|------|------|-----------|---------------------|-----------|
| PS46 | 20250307 | nose | c23dc714 | 7eac88e4e80d | 110.5 |
| PS46 | 20250307 | spout_midpoint | 2a6efb6a | c2b24d3db76f | 109.6 |
| PS46 | 20250307 | eye_midpoint | b13af51c | e87d7a93e26e | 110.1 |

All three `_param_sig` values match Phase 4 baseline → 4.5-lite config
change is parquet-neutral.

### Sub-phase 4.5-F — Axis-limit investigation

`notebooks/experiments/phase_4.5_lite_axis_limits.ipynb` pools the alignment-sweep
cache histograms (8 animals × all sessions × all bodyparts) into production
centered space (shift by `-ref_midpoint` per animal) and derives per-(bodypart,
center_mode) xlim / ylim from the pooled marginal distributions.

**Priya-approved strategy (2026-04-20):** `q00001_9999 + 40% symmetric pad,
rounded to nearest 5 px, clamped to legacy x-filter where applicable`.
Rationale: q001_999 + 20% pad was tested first and clipped density edges;
wider quantile + more padding frame density with comfortable margin without
including clear outliers.

**Legacy x-filter values** (verified from legacy notebooks this session):
- `jaw`:    `X_MIN, X_MAX = -80, 80` (from `20251117_DLC_analysis_jaw.ipynb`)
- `tongue`: `X_MIN, X_MAX = -175, 175` (from `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`)

**Final approved limits** (cohort-pooled, applied to `configs/defaults.yaml`
under `dlc_spatial.bodyparts.{bp}.per_center_mode`):

| bodypart | center_mode | xlim | ylim | x_range (pre-filter) |
|---|---|---|---|---|
| jaw | eye_midpoint | [-80, 80] | [195, 520] | [-80, 80] |
| nose | eye_midpoint | [-100, 95] | [100, 330] | — |
| L_whiskers_1 | eye_midpoint | [15, 135] | [55, 250] | — |
| L_whiskers_2 | eye_midpoint | [15, 165] | [145, 355] | — |
| L_whiskers_3 | eye_midpoint | [60, 165] | [75, 270] | — |
| R_whiskers_1 | eye_midpoint | [-140, -15] | [70, 235] | — |
| R_whiskers_2 | eye_midpoint | [-165, 0] | [155, 350] | — |
| R_whiskers_3 | eye_midpoint | [-185, -40] | [95, 265] | — |
| tongue | spout_midpoint | [-175, 175] | [-235, 225] | [-175, 175] |

Pre-existing `nose` and `jaw` `eye_midpoint` limits were single-session
estimates (PS46/20250307 + 25% margin, DECISIONS 2026-04-18) — superseded
by the cohort-pooled values.

### Sub-phase 4.5-G — Phase 5 plumbing fix + `x_range` support

**Bug fix.** [src/stroke_orofacial/dlc_spatial/pixel_bins.py](../src/stroke_orofacial/dlc_spatial/pixel_bins.py)
and [src/stroke_orofacial/dlc_spatial/heatmaps.py](../src/stroke_orofacial/dlc_spatial/heatmaps.py):
added `center_mode` kwarg to `build_histogram`, `build_stats_grid`, and
`plot_heatmap`. When provided, these functions now read
`config.bodyparts.{bp}.per_center_mode.{mode}` for xlim, ylim, and (new)
`x_range`. Explicit kwargs still override. Added `_get_per_center_mode_params`
helper for consistent lookup across the module.

**`x_range` pre-histogram filter.** `config.bodyparts.{bp}.per_center_mode.{mode}.x_range`
is now plumbed through `get_masked_xy` (which already supported `x_range`).
The Phase 6 `reward_aligned.py` hack that injected `apply_x_range` / `x_range`
into the top-level config was removed; it now uses the new `x_range` kwarg
on `build_histogram` directly. Phase 6 reward-aligned `x_range` (under
`dlc_spatial_reward_aligned.bodyparts.{bp}.x_range`) takes precedence over
Phase 5 `per_center_mode.x_range` when both are set — preserving Phase 6
behavior.

**Y-axis inversion.** `plot_heatmap` now calls `ax.invert_yaxis()` so
rendered plots match camera-video convention (higher y = lower on screen).
Existing Phase 5 blank output did not reflect y orientation at all; new
output does.

**Deprecated top-level x_range.** `config.apply_x_range` / `config.x_range`
still consulted as fallback but marked deprecated in the config comment.

**New tests.**
- `tests/test_pixel_bins.py::TestGetPerCenterModeParams` (5 cases).
- `tests/test_pixel_bins.py::TestBuildHistogramCenterMode` (4 cases).
- `tests/test_pixel_bins.py::TestBuildStatsGridCenterMode` (1 case).
- `tests/test_heatmaps.py::TestPlotHeatmapCenterMode` (2 cases).

**Phase 5 output regeneration required.** The single existing Phase 5 PNG
(nose_nose/PS46/20250307, blank under the bug) re-renders correctly after
the fix. Verified by a one-shot re-render script; produces a non-blank
heatmap with density at (0, 0) inside `[-150, 150]` × `[-120, 130]` limits.
Next cohort-wide Phase 5 run (when Priya re-executes notebook 11) will
supersede all existing `*_nose.png` outputs. **Existing on-disk PNGs are
NOT parity-equivalent under the new code** — this is the intentional bug
fix, not a regression.

### Sub-phase 4.5-H — Notebook 11 wire-up

[notebooks/11_dlc_spatial_whole_session.ipynb](../notebooks/11_dlc_spatial_whole_session.ipynb)
passes `center_mode=center_mode` to both `plot_heatmap` and `build_stats_grid`.
One-line-per-call change. Tongue-offset concern for the future all-bodyparts
overlay (DECISIONS 2026-04-18 "all bodyparts overlay heatmap design") is
untouched; deferred to Phase 5.x as noted.

### Sub-phase 4.5-I — Investigation notebook + outputs

[notebooks/experiments/phase_4.5_lite_axis_limits.ipynb](../notebooks/experiments/phase_4.5_lite_axis_limits.ipynb)
captures the full pooling + comparison + proposal pipeline. Outputs at
[notebooks/experiments/outputs/phase_4.5_lite_axis_limits/](../notebooks/experiments/outputs/phase_4.5_lite_axis_limits/):
- `approved_{bp}_{center_mode}.png` (9 files): pooled heatmap with the
  approved xlim/ylim rectangle overlay.
- `cropping_comparison_{bp}.png` (9 files): 5-panel side-by-side showing
  different quantile/pad strategies.
- `pooled_candidates_{bp}.png` (9 files): pooled heatmap with all
  candidate rectangle overlays.
- `filter_impact_{jaw,tongue}.png` (2 files): unfiltered vs `x_range`-filtered.
- `candidate_limits_table.csv`, `proposed_limits_final.csv`: tabular outputs.

### Intentional behavior differences vs. pre-4.5-lite

1. **Phase 5 heatmap bug fix.** Pre-4.5-lite Phase 5 heatmaps used hardcoded
   `x_limits=(-200, 200)` / `y_limits=(50, 550)` which for centered data
   produces blank plots. Post-4.5-lite heatmaps consume per-(bodypart,
   center_mode) limits from config. Existing nose_nose/PS46 Phase 5 PNG
   on disk is blank and will be replaced by a correct non-blank plot on
   next notebook 11 run.
2. **Y-axis inversion.** `plot_heatmap` output flipped to camera-video
   convention (higher y = lower on plot).
3. **`x_range` filter now active for jaw and tongue.** Phase 5 whole-session
   heatmaps for jaw (under eye_midpoint) and tongue (under spout_midpoint)
   will drop DLC mis-detections outside `[-80, 80]` / `[-175, 175]`
   respectively. Phase 6 reward-aligned `tongue.x_range` (under
   `dlc_spatial_reward_aligned`, `[-150, 150]`) takes precedence when set.
4. **Per-bodypart default `center_mode`** exposes sweep-experiment winners
   as metadata. Downstream consumers (Phase 9) read via
   `config_loader.default_center_mode()`; Phase 5/6 notebooks continue
   iterating their own `CENTER_MODES` lists (no behavior change there).

### What is NOT changed

- `compute_center()`, `apply_centering()`, `_median_from_lik()` untouched.
- Existing centered parquet outputs (PS46/20250307 all 3 modes) byte-identical.
- Phase 4 hash baseline preserved (`c23dc714` / `2a6efb6a` / `b13af51c`).
- `docs/DESIGN.md`: no edit.
- `docs/DECISIONS.md`: 2026-04-19 Phase 4.5-lite entry already correctly
  described the intended implementation.

### Cross-references

- DECISIONS 2026-04-19 "Phase 4.5-lite decision: eye-midpoint centering,
  no similarity/rigid transform" (the green-light).
- DECISIONS 2026-04-18 "Plot axis limits must be per-(bodypart, center_mode)"
  (the principle; this phase finally makes the code consume those limits).
- Sweep experiment at `notebooks/experiments/cross_session_alignment_sweep.ipynb`
  + outputs at `notebooks/experiments/outputs/alignment_sweep/` (the data).
- Legacy x-filter values verified in
  `//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/20251117_DLC_analysis_jaw.ipynb`
  (jaw ±80) and `.../20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`
  (tongue ±175).

### Exit criteria met

- [x] 219 pytest pass + 28 skipped (adds 14 new tests: 6 config_loader, 6
  pixel_bins, 2 heatmaps).
- [x] `ruff check` clean on all changed files.
- [x] `scripts/hash_centered_parquets.py` exits 0; Phase 4 param_sig hashes
  preserved.
- [x] PS46/20250307 re-render proves Phase 5 bug fix produces non-blank output.
- [x] Investigation notebook executes end-to-end and emits the final
  proposal CSV matching the applied config values.
- [x] Fiducial bodypart blocks present and loadable.
- [x] Notebook 12 CENTER_MODES includes eye_midpoint.

### Deferred / noted for follow-up

- **All-bodyparts overlay tongue-offset**: future Phase 5.x (DECISIONS
  2026-04-18) must handle tongue in spout-centered frame being offset
  from jaw/nose/whiskers in eye-centered frame when co-plotting. Candidate
  solutions (translate tongue by cohort-mean `spout_mid - eye_mid`, render
  tongue in its own panel, or re-center tongue on eye_midpoint for overlay)
  to be decided when that phase starts.
- **Cohort-wide Phase 5 re-run**: required after Gate 2 for any future
  Phase 5 outputs. Existing `nose_nose/PS46/heatmap_20250307.png` is the
  only Phase 5 PNG on disk and is blank under the bug; delete or overwrite.
- **Fiducial `per_center_mode` blocks**: left null since no Phase 5/6
  heatmaps for fiducials. Phase 9 null-baseline stats read fiducials from
  raw parquets directly, not from heatmap outputs.
- **Phase 6 reward-aligned code path re-test**: the reward_aligned.py
  refactor removed a config-injection hack. `test_reward_aligned.py`
  passed (5 tests; 2 skipped for missing data). Live-data re-run on PS46
  recommended once Priya re-executes notebook 12.
- **Image-boundary clamping for per-(bodypart, center_mode) axis limits**
  (2026-04-20 review): the approved `q00001_9999 + 40% pad` limits are
  clamped to legacy x-filter ranges where applicable (`jaw [-80, 80]`,
  `tongue [-175, 175]`) but not to the raw image frame. For some
  bodyparts (notably tongue `ylim=[-235, 225]` under spout_midpoint),
  the +40% pad extends into centered-frame regions that map past the
  image edge for some sessions — rendered as harmless white space but
  technically not a region where data could exist. Fix options (park for
  future Phase 5.x polish mini-phase):
  - (A) Add image dims to `configs/defaults.yaml` and clamp at plot time
    using per-session midpoint offsets.
  - (B) Cohort-conservative fixed clamp derived from min-across-sessions
    of `(image_edge − session_midpoint)`.
  - (C) Manual per-bodypart `ylim` override in config for the 1-3
    affected combinations (simplest).
  Priya (2026-04-20) elected to defer to Phase 5.x polish and will decide
  between option C (manual override) and option A at that time.

### Post-merge validation (2026-04-20, post-PR-#33-merge)

Both follow-ups from the "Deferred / noted" block above executed on branch
`phase-4.5-lite-post-merge-validation` (off main at `685d3f7`) to confirm
nothing regressed after the Gate 2 API refactor.

**Followup 1 — Cohort-wide Phase 5 re-run.** Deleted the single pre-fix
blank PNG at `spatial_whole_session/nose_nose/PS46/heatmap_20250307.png`
and executed `notebooks/11_dlc_spatial_whole_session.ipynb` via
`jupyter nbconvert --execute --inplace`. Parquets for the other 7 animals
and other PS46 dates are not yet built (confirmed by Phase 4.5-E hash
script), so the effective re-run scope was PS46/20250307 × 3 bodyparts
(nose/jaw/tongue) × 3 center_modes (nose/spout_midpoint/eye_midpoint) =
9 `(bodypart, center_mode)` combinations, producing 9 PNGs + 9
`stats_grid` NPZs. All 18 outputs non-blank; the previously-blank
`nose_nose/PS46` re-rendered as a correct nose-centered density at
`(0, 0)` within `xlim=[-150, 150]`, `ylim=[-120, 130]`, camera-view
y-inversion applied. Full re-run baseline:

| combination | file | sha256[:12] | size (KB) |
|---|---|---|---|
| jaw_eye_midpoint | PS46/heatmap_20250307.png | 7f7d855214bf | 53.9 |
| jaw_eye_midpoint | PS46/stats_grid_20250307.npz | 3e866674fe56 | 2.7 |
| jaw_nose | PS46/heatmap_20250307.png | 38bf72585eb2 | 44.6 |
| jaw_nose | PS46/stats_grid_20250307.npz | 4956a43d3d46 | 2.9 |
| jaw_spout_midpoint | PS46/heatmap_20250307.png | 15394b0028f5 | 45.9 |
| jaw_spout_midpoint | PS46/stats_grid_20250307.npz | 93f9e39f12d8 | 2.9 |
| nose_eye_midpoint | PS46/heatmap_20250307.png | 24834e920388 | 48.4 |
| nose_eye_midpoint | PS46/stats_grid_20250307.npz | 79edfe96d17e | 2.4 |
| nose_nose | PS46/heatmap_20250307.png | 5caf3a348f9c | 42.9 |
| nose_nose | PS46/stats_grid_20250307.npz | 76f953ea8f8f | 2.4 |
| nose_spout_midpoint | PS46/heatmap_20250307.png | 633c25a7ad1e | 46.9 |
| nose_spout_midpoint | PS46/stats_grid_20250307.npz | 62ec7c54f97d | 2.4 |
| tongue_eye_midpoint | PS46/heatmap_20250307.png | b0d99b3a11de | 49.3 |
| tongue_eye_midpoint | PS46/stats_grid_20250307.npz | 4838328575d3 | 6.0 |
| tongue_nose | PS46/heatmap_20250307.png | 99d5d55ecc6d | 49.5 |
| tongue_nose | PS46/stats_grid_20250307.npz | 500e3682ee9c | 6.0 |
| tongue_spout_midpoint | PS46/heatmap_20250307.png | 6c156a7947b5 | 52.8 |
| tongue_spout_midpoint | PS46/stats_grid_20250307.npz | 83dd84f530ed | 3.6 |

No regressions observed. The previously-good `nose_nose` PNG was blank
under the pre-4.5-lite bug (not truly good), so the regression-detection
logic ("any combination that was good and is now broken") had no broken
referents to check against.

**Followup 2 — Phase 6 reward_aligned live-data re-test.** Called
`build_reward_aligned_analysis` directly on PS46/20250307 with
`window_ms=(-500, 5000)`, `trial_group="all"` (96 rewards, 132,096
selected frames) for the two reference combinations in Phase 6 §6d, and
compared histogram counts to the recorded baselines:

| combination | center_mode | counts (post-4.5-lite) | baseline (Phase 6 §6d) | status |
|---|---|---|---|---|
| tongue | nose | 54,159 | 54,159 | MATCH |
| nose   | nose | 132,053 | 132,053 | MATCH |
| tongue | spout_midpoint | 54,159 | — | recorded as new baseline |

All rewards / selected_frame counts also match (96 / 132,096).
Histogram-bin fill percentages differ across center_modes because the
per-(bodypart, center_mode) `xlim` / `ylim` / `x_range` are different
frames, but total counts are invariant under the API refactor — exactly
as expected for a pure plumbing change.

Additionally smoke-tested `notebooks/12_dlc_spatial_reward_aligned.ipynb`
via `jupyter nbconvert --execute --inplace`. Exit 0, 54 new Phase 6
reward-aligned PNGs on disk (3 bodyparts × 3 center_modes × 2 windows ×
3 trial_groups).

**Conclusion.** Gate 2 API refactor preserved Phase 6 behavior at the
histogram level; the pre-existing Phase 5 blank-PNG bug is fixed; no
regressions. All "Deferred / noted" items from the main Phase 4.5-lite
entry are now closed except the Phase 5.x all-bodyparts overlay
(still future scope) and the fiducial `per_center_mode` blocks (still
intentionally null).

---

## Phase 5 — DLC Spatial Analyses (Whole Session)

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1: siblings vs
duplicates):

- **Siblings (consolidated into one module):**
  `20251117_DLC_analysis_nose.ipynb` and `20251117_DLC_analysis_jaw.ipynb` —
  same date, distinct scope markers (`_nose` vs `_jaw`). Spatial analysis
  cells (10-12) are structurally identical. Consolidated into parameterized
  functions in `dlc_spatial/pixel_bins.py` and `dlc_spatial/heatmaps.py`.
  Jaw notebook's kinematics/PSD cells (13+) are Phase 7 scope.
- **Canonical for pixel-bin:** `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`
  (latest YYYYMMDD for all-bodyparts spatial analysis).
- **Exploratory / Deferred to Phase 9:**
  `20251201_DLC_analysis_all_bodyparts_2KSD_spatial-maps.ipynb` — 2D-KS-distance
  visualization tightly coupled to inferential stats. Not ported.
- **Cells 14-20 of 20260323:** remain Exploratory/Deferred (kinematics, PSD).

**Dead code classification:**

`20251202` notebook (26 cells):
- Cells 0-4: Exploratory (imports, paths, cache loading, sanity check).
- **Cells 5-7: Production** — per-session heatmaps, binned heatmaps,
  subtraction maps. Ported.
- **Cells 8-10: Deferred to Phase 9** — permutation null + per-day inferential
  stats with p-values.
- **Cells 11-13: Production** — batch spatial viz, eye/spout grouped heatmaps.
  Ported.
- Cells 14+: Exploratory/Helper.

`20251117` nose/jaw notebooks: cells 10-12 Production (ported); rest
Exploratory or Phase 7 scope.

**What was done:**

### Sub-phase 5a: Config + window_selector scaffold
- Added `dlc_spatial` section to `configs/defaults.yaml` with per-bodypart
  likelihood thresholds, colormaps, and per-(bodypart, center_mode) axis
  limits (derived from PS46/20250307 data ranges).
- Scaffolded `WholeSessionWindow` in `window_selector.py` (Phase 6 extends
  with reward-aligned selector).

### Sub-phase 5b: Pixel bins
- Implemented `src/stroke_orofacial/dlc_spatial/pixel_bins.py`:
  `get_masked_xy()`, `build_histogram()` (fine-resolution, nbins=100),
  `build_stats_grid()` (coarser, target_bin_size=25px),
  `build_baseline_histogram()`.
- Permutation null deferred to Phase 9.

### Sub-phase 5c: Heatmaps
- Implemented `src/stroke_orofacial/dlc_spatial/heatmaps.py`:
  `plot_heatmap()` (hist2d with LogNorm + density), `save_heatmap_png()`.
- Per-(bodypart, center_mode) colormap and axis limits from config.

### Sub-phase 5d: Difference maps
- Implemented `src/stroke_orofacial/dlc_spatial/difference_maps.py`:
  `compute_difference_map()`, `plot_difference_map()` (diverging colormap),
  `save_difference_map_png()`.

### Sub-phase 5e: Orchestrator notebook
- Created `notebooks/11_dlc_spatial_whole_session.ipynb` — loops over
  (animal × date × bodypart × center_mode). Stateless, skip/force overwrite.

### Sub-phase 5f: Parity check

**Verified:**
- Fine heatmap produces non-trivial counts (925,098 on PS46/20250307 nose,
  nose-centered, 421 non-zero bins in 100×100 grid).
- Output shapes, dtypes, and file structure match legacy conventions.
- Code is a faithful port of production cells 5-7, 11-13 of
  `20251202_all_bodyparts_stats_pixelbin` and cells 10-12 of
  `20251117_nose`/`20251117_jaw` (consolidated).

**Not verifiable at array level (legacy output limitations):**
- Legacy saved per-session heatmaps only as PNGs, not NPZs. Per-session
  array parity is impossible without rebuilding the legacy pipeline.
- Baseline aggregate parity requires running the new pipeline across all
  pre-stroke PS46 sessions — deferred to a Phase 10 cleanup task.

**Deferred cleanup task for Phase 10:**
- Run the Phase 5 pipeline across all pre-stroke PS46 sessions, aggregate
  the histograms, and compare the resulting aggregate NPZ against the legacy
  `PS46_nose_stats/centered_nose/nose_baseline_hists_preALL_*.npz` arrays.
  Expected to match at `rtol=1e-6` if the port is faithful.

### Sub-phase 5g: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_pixel_bins.py` — masking, histogram shapes, stats grid, baseline
  aggregation.
- `tests/test_heatmaps.py` — figure generation, PNG save.
- `tests/test_difference_maps.py` — subtraction arithmetic, diverging colormap
  plot, PNG save.

**Intentional behavior differences vs. legacy:**

1. **Per-(bodypart, center_mode) axis limits.** Legacy used hardcoded
   `y_limits=(50, 550)` which were for un-centered pixel coordinates.
   Nose-centered data needs `y_limits=(-120, 130)`. The new pipeline loads
   axis limits from `configs/defaults.yaml` per (bodypart, center_mode) tuple.
   Per DECISIONS.md "Phase 5+ downstream analyses."
2. **Overwrite protection: skip/force only** (matching Phase 4).
3. **Output location on MICROSCOPE** at
   `pipeline_outputs_v2/dlc_analysis/spatial_whole_session/`.
4. **Sibling consolidation.** Legacy had separate nose/jaw notebooks with
   duplicated spatial analysis code. New pipeline uses one parameterized
   module that loops over bodyparts.
5. **Permutation null deferred to Phase 9.** Cells 8-10 of `20251202`
   compute inferential statistics (permutation p-values). Deferred per
   DECISIONS.md "Phase 5 defers permutation/inferential spatial stats to
   Phase 9."
6. **2KSD notebook deferred in full to Phase 9.** 2D-KS-distance
   visualization tightly coupled to its stats computation.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Fine heatmap verified non-trivial on PS46/20250307.
- [x] Per-(bodypart, center_mode) axis limits in `configs/defaults.yaml`.

---

## Phase 5.5 — DLC Inference Port (O2)

**Date:** 2026-04-18

**Legacy file disambiguation:**
- **Canonical:** `20251112_DLC_batch_video_analysis_O2.ipynb` (Rule 1: latest
  YYYYMMDD). 55 cells.
- **Deprecated:** `old_code/20251103_DLC_batch_video_analysis.ipynb` (pre-O2),
  `20251104_DLC_batch_video_analysis_O2.ipynb` (earlier date),
  `20251104_..._O2_2.ipynb` and `_O2_3.ipynb` (numbered variants).
- No external `.py` helpers — all scripts embedded inline in notebook cells.

**Dead code classification:** 55 cells; ~20 production (SSH setup, script
generation, SBATCH, staging, renaming, copy), ~30 exploratory (monitoring,
manual verification, debugging, batch-size scout monitoring).

**What was done:**

### Sub-phase 5.5a: Core modules
- `runner.py`: `generate_inference_script()` produces standalone
  `run_dlc_batch.py` (DLC `analyze_videos` + `filterpredictions`, per-video
  iteration, YAML-based animal/date selection).
- `batch.py`: `discover_camera_dates()`, `discover_videos()`,
  `write_selection_yaml()`.
- `o2_job.py`: `generate_sbatch_script()` with configurable SBATCH resources,
  `o2_paths()` for path resolution.
- Added `dlc_inference_o2` section to `configs/defaults.yaml` with all SBATCH
  resources, DLC params, O2 paths, and snapshot rename mappings.

### Sub-phase 5.5b: Transfer utilities
- `transfer.py` (184 lines): `build_stage_videos_command()`,
  `build_copy_to_microscope_command()` (two-stage or direct),
  `build_rename_command()`, `rename_snapshots_local()`. Functions generate
  shell commands as strings — user pastes into terminal. The local rename
  utility (`rename_snapshots_local()`) is the only function that executes
  file operations directly.
- **Line count vs estimate:** 184 lines vs plan's ~80 estimate. Growth from:
  comprehensive docstrings (~40 lines), the `rename_snapshots_local()` helper
  for post-copy cleanup not in the original plan (~30 lines), and explicit
  per-animal/per-date loop in the staging command builder (~20 lines).

### Sub-phase 5.5c: README + notebook
- `README.md`: complete O2 workflow documentation (prerequisites, step-by-step,
  resources, DLC params, batch-size tuning, troubleshooting, security).
- `notebooks/10_dlc_inference.ipynb`: click-through orchestrator with USER
  INPUTS. Local actions (YAML writing, script generation) execute directly.
  SSH/rsync/sbatch commands are printed with user-specific inputs substituted
  — user pastes into terminal. No SSH from within notebook context.

### Sub-phase 5.5d: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_dlc_inference.py` — script generation (valid Python syntax,
  contains DLC API calls), YAML structure, SBATCH content, path resolution,
  rsync commands, local rename logic.
- Removed `batch_video_analysis.py` (Phase 0 stub, no imports anywhere in
  the repo — confirmed via `grep -rn`). Superseded by the split into
  `runner.py`, `batch.py`, and `o2_job.py`.

**Parity strategy: code-only review.**
- Running inference requires O2 GPU access + HMS credentials + ~30 min/video.
  Cost/benefit low for infrastructure code.
- Structural parity verified: generated `run_dlc_batch.py` matches legacy
  cell 6 (same DLC API calls, same argparse options, same per-video iteration
  + error handling). SBATCH matches legacy cell 14 resource requests. Rename
  logic matches cell 45.

**Intentional behavior differences:**
1. **Modular structure.** Legacy: all logic embedded in notebook cells (55
   cells, monolithic). New: split into 4 focused modules + README + notebook.
2. **SSH commands generated, never executed.** Per DECISIONS.md. Local actions
   run in-notebook; SSH/rsync/sbatch printed for user to paste.
3. **All constants in config.** SBATCH resources, DLC params, O2 paths, and
   snapshot renames moved to `configs/defaults.yaml` (were inline in notebook).

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] README documents full O2 workflow.
- [x] Notebook provides click-through interface without executing SSH.

---

## Phase 6 — DLC Spatial (Reward-Aligned)

**Date:** 2026-04-18

**Legacy file disambiguation** (per refined CLAUDE.md rule 1):

- **Reclassified from Phase 4's Exploratory to Phase 6 Production:**
  `20260323` cell 16 (reward-aligned heatmaps, 1683 lines), cell 18
  (reward-aligned binned heatmaps), cell 20 (reward-aligned Δ heatmaps).
- **Re-read confirmation** (per DECISIONS.md "Legacy notebooks may receive
  active edits"): cell 16 re-read at Phase 6 kickoff. Legacy notebook
  mtime: 2026-03-23 (unchanged since Phase 4).
- All other cells (21-64) remain Exploratory/Deprecated.

**Dead code classification** (cells 16-20 revisited):
- Cells 16, 18, 20: reclassified **Production** for Phase 6 (were Exploratory
  in Phase 4 — deferred to Phase 6 scope by design).
- Cells 17, 19: markdown section headers.
- Cells 21-64: unchanged (kinematics Phase 7, PSD Phase 8+, stats Phase 9).

**What was done:**

### Sub-phase 6a: Extend window_selector + reward-aligned config
- Extended `window_selector.py` with `EventAlignedWindow` (generic, handles
  deduplication of overlapping event snippets) and `RewardAlignedWindow`
  (converts WS samples → camera frames via alignment LUT, ms → frames).
- Added `_ws_to_cam_frames()` helper (faithful port of cell 16's
  `_ws_to_cam_frames` function).
- Added `dlc_spatial_reward_aligned` section to `configs/defaults.yaml`:
  reward windows `[(-500, 5000), (-100, 1000)]` ms, trial groups
  `[all, L, R]`, 10 bodyparts (tongue legacy-ported, jaw/nose/6 whiskers
  sanity-check-only).

### Sub-phase 6b: Generalize Phase 5 spatial functions
- Added `frame_mask` parameter to `get_masked_xy()` — ANDed with likelihood
  mask when provided.
- Added `window` parameter (default `None` = whole session) to
  `build_histogram()`, `build_stats_grid()`, `plot_heatmap()`.
- **Phase 5 backward compatibility:** all 18 Phase 5 spatial tests pass
  unchanged with `None` default.

### Sub-phase 6c: Reward-aligned analysis functions
- Created `src/stroke_orofacial/dlc_spatial/reward_aligned.py`:
  `load_reward_events()` (per trial group from Phase 2 NPZ),
  `ws_samples_to_frame_indices()`, `build_reward_aligned_window()`,
  `build_reward_aligned_analysis()` (pure function, stateless).

### Sub-phase 6d: Orchestrator notebook + functional verification
- Created `notebooks/12_dlc_spatial_reward_aligned.ipynb`: loops over
  (animal × date × bodypart × center_mode × window_ms × trial_group).
  Stateless, skip/force overwrite.

### Sub-phase 6e: Tests + MIGRATION_LOG + DECISIONS.md
- `tests/test_window_selector.py` — WholeSessionWindow compat,
  EventAlignedWindow mask construction + deduplication + edge clamping,
  RewardAlignedWindow WS→frame conversion, invalid event handling.
- `tests/test_reward_aligned.py` — load_reward_events per trial group,
  ws_samples_to_frame_indices, integration smoke test on PS46/20250307,
  trial-group-differ assertion (all = L + R).

**Parity status — three-section assessment:**

**Verified:**
- Phase 5 whole-session tests all still pass (18/18 — window refactor is
  additive; `None` default preserves existing behavior).
- Functional verification passes for tongue + nose on PS46/20250307
  with `(-500, 5000)` ms window, nose centering:
  - 96 rewards (48L + 48R), 132,096 selected frames (~14% of session)
  - Tongue: 54,159 histogram counts (~41% fill — expected for `lik_thr=0.5`)
  - Nose: 132,053 counts (~100% fill — expected for `lik_thr=0.7`)
  - L/R trial-group differences confirmed (48 vs 48 rewards, different
    histogram counts)

**Not verifiable at array level:**
- **First phase without an array-level parity reference.** Legacy cell 16
  was coded but never run to produce saved outputs on MICROSCOPE. No
  `PS46_*reward*` or `PS50_*reward*` directories exist. Array-level parity
  comparison is not possible.

**Deferred to future runs:**
- First scientific validation on each (bodypart, center_mode, window)
  combination requires visual inspection of the generated heatmaps.
- Per-bodypart reward-aligned config uses sanity-check-only defaults for
  everything except tongue (which has legacy values from cell 16).
- Jaw, nose, and all 6 whisker points (L/R_whiskers_1/2/3) configured
  with sanity-check-only defaults — not parity-verified.

**Phase 10 cleanup tasks:**
- Phase 5's `dlc_spatial.bodyparts` config has `L_whiskers_2`, `L_whiskers_3`,
  `R_whiskers_2`, `R_whiskers_3` with all `per_center_mode` entries set to
  `null`. Fill these in when whole-session whisker_2/3 analyses are
  exercised, matching whisker_1's pattern.

**Intentional behavior differences vs. legacy:**

1. **Window refactor to Phase 5 spatial functions.** `get_masked_xy()`,
   `build_histogram()`, `build_stats_grid()`, `plot_heatmap()` now accept
   an optional `window` parameter. Default `None` preserves whole-session
   behavior.
2. **Reward-aligned module in new location** at
   `src/stroke_orofacial/dlc_spatial/reward_aligned.py` (legacy was
   inline in cell 16 of the parquet-building notebook).
3. **Output to pipeline_outputs_v2** at
   `dlc_analysis/spatial_reward_aligned/{bodypart}_{center_mode}/`.
4. **All 10 bodyparts configured** (tongue + jaw + nose + 6 whiskers).
   Legacy only configured tongue (jaw/nose were commented out).
5. **Stateless orchestrator** matching Phase 4/5 pattern.
6. **window_selector abstraction** supports future event types (cue-aligned,
   custom) without infrastructure changes.

**Exit criteria met:**
- [x] `pytest tests/` passes.
- [x] `ruff check src/` clean.
- [x] Phase 5 tests: 18/18 pass (no regression).
- [x] Functional verification on PS46/20250307 (tongue + nose).
- [x] 10 bodyparts configured in reward-aligned config.

---

## Phase 13 — Env unification + bnpm vendoring

**Dates:** 2026-04-19 (env unification) → 2026-04-20 (bnpm vendoring).

**What was done:**

### Sub-phase 13a: Unified environment.yml
- Replaced the `environment-mac.yml` (`frsb`) + `environment-windows.yml`
  (`deeplabcut` placeholder) pair with a single `environment.yml` creating
  the `stroke_orofacial` env (Python 3.11, conda-forge primary).
- Runs PARALLEL to existing envs — `frsb` (Mac) and `deeplabcut` (Windows)
  are not touched; `deeplabcut` remains the DLC training / O2 inference /
  Keypoint-MoSeq env.
- Dep scope derived from a full import audit of `src/`, `tests/`,
  `notebooks/`, and every legacy notebook under
  `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`.
- Dropped (unused anywhere): `opencv-contrib-python`, `tqdm`.
- Added (in-flight ports reference them): `patsy`, `pot`, `scicomap`,
  `nbconvert`.
- Pinned the HDF5 stack to avoid silent ABI skew on Windows:
  `hdf5=1.14.*`, `pytables=3.10.*`, `h5py` unpinned (conda-forge resolves
  it), `pywavesurfer` installed post-env-create via
  `pip install pywavesurfer --no-deps` (its wheel pins `h5py==3.8.0` and
  would otherwise downgrade conda h5py to a PyPI wheel with its own
  hdf5.dll, colliding with pytables' conda hdf5.dll).
- `pyproject.toml` `[project.dependencies]` brought into agreement with
  `environment.yml` so `pip install -e .` produces an equivalent install.
- See docs/DECISIONS.md "2026-04-19 Phase 13 env unification" for the
  full channel / pin / exclusion rationale.
- On Windows, `conda env create -f environment.yml` defaults the env
  prefix to the per-user `C:\Users\<user>\.conda\envs\` rather than
  `C:\ProgramData\anaconda3\envs\` when the latter is write-locked to
  non-admin shells. This matches where `deeplabcut` already lives on
  Priya's Windows box and is user-writable (avoids perms-driven rebuild
  failures). Initial rebuild-from-scratch attempt against the
  ProgramData install hit `EnvironmentNotWritableError` and required an
  admin-shell `conda env remove` before the per-user rebuild succeeded
  cleanly.

### Sub-phase 13b: Vendor 4 bnpm helpers, drop bnpm / torch
- After 13a, pytest couldn't collect on Windows: `import bnpm.indexing`
  failed with `OSError: [WinError 127]` on `torch\lib\shm.dll` plus
  `OMP: Error #15: Initializing libomp.dll, but found libiomp5md.dll
  already initialized`. Root cause: bnpm unconditionally imports torch at
  module load, and PyPI torch 2.11.0 on Windows bundles Intel OpenMP
  (libiomp5md.dll) clashing with conda-forge MKL's LLVM OpenMP (libomp.dll).
- Usage audit showed the repo uses exactly four bnpm helpers, all pure
  numpy: `bnpm.indexing.{idx2bool, widen_bool_sparse, set_short_bool_to_low}`
  and `bnpm.timeSeries.simple_smooth`.
- Vendored all four into
  `src/stroke_orofacial/_utils/bool_indexing.py` under bnpm's MIT license
  (© 2021 RichieHakim; license text reproduced in the module docstring).
  `gaussian_smooth_1d` is a faithful 1-D reconstruction of
  `simple_smooth` using the same kernel formula from
  `bnpm.math_functions.gaussian` (`x = linspace(-5σ, 5σ, 7σ samples)`,
  `kernel = (1/(√2π σ)) exp(-0.5 (x/σ)²)`) with edge-normalized
  `np.convolve` (``mode='same'``).
- Updated `bouts.py` (10 callsites) and `wavesurfer_io.py` (1 callsite)
  to import from `stroke_orofacial._utils.bool_indexing`.
- Dropped `bnpm[core]` from both `environment.yml` and `pyproject.toml`.
  Also dropped `numba`, `llvmlite`, `cmake` from `environment.yml` —
  those were only in the env to dodge the `bnpm[core]` pip source-build
  path on Intel Mac.
- Added `tests/test_vendored_bool_indexing.py` with a mixed-strategy
  validation suite (see "Intentional behavior differences" below for why):
    * `idx2bool` (3 tests) and `gaussian_smooth_1d` (2 tests) are strict
      ports of bnpm 0.6.0; parity-tested against live bnpm via
      `pytest.importorskip("bnpm.indexing")` / `importorskip(
      "bnpm.timeSeries")`. Skip cleanly in the new (bnpm-less) env; run
      on any machine that still has bnpm installed (e.g. Priya's Mac
      `frsb` env, where all 5 pass).
    * `widen_bool_sparse` (3 tests) and `set_short_bool_to_low` (3 tests)
      intentionally diverge from bnpm 0.6.0 to fix two upstream bugs
      (described below); tested against hand-rolled expected outputs
      plus an independent Python-loop / `itertools.groupby` reference
      implementation. These tests are bnpm-free and always run.
- See docs/DECISIONS.md "2026-04-20 Phase 13 vendor bnpm" for the full
  decision trail.

**Intentional behavior differences vs. legacy:**

1. **`bnpm` is no longer a runtime dependency.** The four helpers we used
   are vendored; torch, numba, llvmlite, and cmake (all previously
   carried transitively via bnpm or as belt-and-suspenders for its
   source build) drop out. All legacy notebook code paths that imported
   torch ran inside the `deeplabcut` env, which is untouched.

2. **Two vendored helpers intentionally diverge from upstream bnpm 0.6.0
   (bug fixes, not parity).** Discovered while writing the parity tests;
   kept because they preserve *caller intent* (what `bouts.py` documents
   it wants) rather than upstream behavior. Concretely:
   - `widen_bool_sparse`: upstream iterates over **rising AND falling**
     edges of each True run and widens each edge by
     `[edge - n_before, edge + n_after + 1]`. Because the falling edge
     lives one position past the run's last True, the trailing side of
     every run overshoots by an extra `n_after + 1` samples relative to
     a "widen every True index" semantic. Vendored version widens every
     True index by `[i - n_before, i + n_after + 1]` (symmetric,
     idempotent).
   - `set_short_bool_to_low`: upstream hand-patches edge runs and
     appends `out.size - 1` (rather than `out.size`) as the closing
     falling-edge index for a trailing-True run. This **under-counts
     trailing runs by 1**, so e.g. a length-1 trailing True gets length
     `0` and is never flagged as short. Vendored version uses a
     padded-array diff that measures every run correctly.
   Strict ports (`idx2bool`, `gaussian_smooth_1d`) remain byte-/kernel-
   for-byte equivalent to bnpm 0.6.0.

3. **Measured drift vs. frozen session_processing3 baselines**
   (PS46/20250307, 3,610,000 samples per array, `tests/test_bouts.py`
   pipeline against `session_processing3/*.npz`):

   | Array             | Differing | Fraction  | Max run | First idx | Direction            |
   | ----------------- | --------- | --------- | ------- | --------- | -------------------- |
   | running_bouts     | 0         | 0         | —       | —         | identical            |
   | lick_bool_bad     | 2         | 5.54e-7   | 2       | 2727859   | ref=True → new=False |
   | quiet_bool        | 51        | 1.41e-5   | 1       | 50558     | ref=False → new=True |
   | peri_reward_bool  | 0         | 0         | —       | —         | identical            |

   Only the two arrays produced by code paths that call
   `widen_bool_sparse` / `set_short_bool_to_low` move. Running_bouts
   and peri_reward_bool (which do not use these helpers for any
   semantically-divergent case) are bit-identical to the legacy output.
   The 51 quiet_bool flips are isolated singletons scattered across the
   session — consistent with the upstream edge-run undercount bug firing
   once per short trailing True in the quiet-detection chain.

4. **Scope of affected downstream artifacts.** These bool masks are
   terminal outputs: no module under `src/stroke_orofacial/` reads
   them as input. The only writers are
   `src/stroke_orofacial/spout_behavior/session_processing.py`, which
   emits them into `stroke_orofacial_pipeline_outputs/spout_behavior/
   {grooming_bouts,quiet_bouts,peri_reward_periods}/{ANIMAL}/
   {YYYYMMDD}.npz`. The legacy `session_processing3/` outputs remain
   untouched (source data per CLAUDE.md); new outputs going forward use
   the corrected semantics. No Phase 3 / 4 / 5 / 6 artifact depends on
   these masks as input, so no regeneration cascade.

5. **Integration-test tolerances — two unrelated effects, un-lumped.**
   - `tests/test_timebase.py` `rtol` bumped `1e-10` → `1e-8` on the
     sample-index mapping. This is **numpy/scipy LAPACK drift**, not
     vendoring: `np.polyfit` + `scipy.interpolate.interp1d` in the
     alignment path produce ~1e-10 rel diff under the new env's LAPACK
     backend (numpy 1.24 → 2.4, scipy 1.15 → 1.17) relative to the
     frozen alignment template. Unrelated to the vendored helpers.
   - `tests/test_bouts.py` + `tests/test_session_processing.py` bool
     arrays now use a `bool_near_equal` helper (`max_frac=1e-4`). This
     is the **measured drift from the vendored bug fixes** (table in
     point 3 above). The tolerance sits ~7x above the worst observed
     mismatch (51/3.61M = 1.41e-5) to leave headroom for other sessions
     with similar shape but different run structures. It is not LAPACK
     jitter — the whole bouts pipeline runs at a hard-coded `Fs=1000.0`
     and never touches `polyfit` / `interp1d`.

6. **`pywavesurfer` moved from pyproject `dependencies` to manual
   post-env-create `pip install --no-deps`.** Env-migration collateral,
   not a vendoring effect: its wheel pins `h5py==3.8.0`, which pip
   would otherwise try to build from source on Python 3.11 (no matching
   wheel on PyPI), taking numpy's source build with it and failing on
   clang. The `--no-deps` policy was already documented in
   `environment.yml`; `pyproject.toml` just hadn't been updated to
   match.

7. **`wavesurfer_io.py` `float(Fs_in)` → `float(np.asarray(Fs_in).item())`.**
   Env-migration collateral: numpy 2.x removed implicit scalar coercion
   of 1-element ndarrays; pywavesurfer returns `AcquisitionSampleRate`
   as shape `(1,)`.

**Exit criteria:**
- [x] `conda env create -f environment.yml` succeeds on Mac.
- [x] `conda env create -f environment.yml` succeeds on Windows.
- [x] `pip install -e .` succeeds in the new env on both platforms.
- [x] `pip install pywavesurfer --no-deps` completes cleanly.
- [x] `pytest tests/` passes in the new env on Mac (223 passed / 6 skipped
  / 0 failures — 6 tests skip because `frsb` is the parity machine and the
  rest run and pass; when run inside `frsb` itself with bnpm still present,
  all 229 pass including the strict-port parity tests that use
  `pytest.importorskip`).
- [x] `pytest tests/` passes in the new env on Windows (201 passed /
  28 skipped / 0 failures — 22 pre-existing integration/real-data gates
  skip because no real data is mounted on Windows; 6 `pytest.importorskip(
  "bnpm.*")` strict-port parity gates skip cleanly because bnpm isn't
  installed in the new env; 5 divergent-port tests run and pass against
  their hand-rolled references; no torch DLL errors).
- [x] `environment-mac.yml` + `environment-windows.yml` stubs `git rm`-ed.
- [x] PR #31 merged to main as `d031486` and tagged
  `v0.7-phase-13-env-unification` (annotated, pushed). Feature branch
  `phase-13-env-unification` preserved on origin per CLAUDE.md §8.

## Phase 8a.7 — Per-session JSON writer + schema (criteria stubbed)

**Date:** 2026-04-20.

**What was done:**

- New module `src/stroke_orofacial/spout_behavior/endpoints_writer.py`
  defining `write_session_endpoints_json()` plus the
  `lick_bouts_to_endpoint_result()` adapter and three module-level
  constants: `SCHEMA_VERSION = "2.0.0"`,
  `CANONICAL_ENDPOINT_NAMES` (10-name frozenset), and two sentinel dicts
  (`CRITERIA_NOT_YET_COMPUTED_SENTINEL`,
  `INTER_SESSION_REQUIRES_COHORT_SENTINEL`).
- Schema 2.0.0 has three top-level blocks — `metadata`, `endpoints`,
  `criteria` — plus a top-level `schema_version` string. Every
  endpoint slot and every criteria slot is always present; absent
  computations land as explicit sentinel objects rather than `null` or
  missing keys, so downstream consumers (8a.7.5, 8a.8) can assert
  presence at the schema level.
- Caller passes the full 10-key `endpoints` dict; the writer validates
  strictly (missing or unknown keys → `ValueError`). Each value may be
  an `EndpointResult` (computed) or a sentinel dict (e.g.
  `INTER_SESSION_REQUIRES_COHORT_SENTINEL` for the per-animal
  cross-session metric, which is computed at the cohort-aggregation
  stage in a future phase). The four criteria sentinels are
  constructed internally from
  `criteria_slugs.all_new_slugs(defaults)` — caller does not pass
  them.
- `lick_bouts_to_endpoint_result()` adapts the
  `find_lick_bouts() → list[LickBout]` primitive into the uniform
  `EndpointResult` shape the writer expects. Bouts are binned into
  trials by `start_idx ∈ [reward_idx + window_seconds[0]*Fs,
  reward_idx + window_seconds[1]*Fs)` (half-open, matches
  `build_per_trial_records`'s window semantics). `per_session_aggregate`
  reports `n_bouts`, `mean_n_licks`, `mean_within_bout_ili_s`,
  `mean_bout_duration_s`, and `std_bouts_per_trial`;
  `per_trial_array` carries per-trial bout counts so downstream
  consumers can recompute alternative summary stats without re-running
  the primitive.
- NPZ provenance hashes are SHA-256 hex of full file bytes
  (`hashlib.sha256(path.read_bytes()).hexdigest()`); Phase 2 NPZs are
  small enough that one-shot reads are fine.
- Atomic write mirrors the
  `tempfile.TemporaryDirectory` + `Path.replace` idiom in
  `dlc_io/parquet.py:47-75` — temp file lands in the final output's
  parent directory so the rename is atomic on the same filesystem.
- 15 tests in `tests/test_endpoints_writer.py` cover schema
  round-trip, top-level / metadata / endpoints block shapes, criteria
  sentinel pattern (explicit assertion that values are the sentinel
  dict, never `None`), inter-session sentinel passthrough, hash
  determinism, hash-changes-on-byte-mutation, schema version,
  no-partial-on-exception atomic semantics, strict missing/unknown
  key validation, NaN preservation through `json.dumps(allow_nan=True)`,
  and the lick-bout adapter's empty-input + trial-binning behavior.

**Intentional behavior differences vs. legacy:**

1. **Schema 2.0.0 is a clean break from legacy
   `behavior_report_PS.py:report.json`.** Per the kickoff scoping
   decision Q6 (2026-04-20), the new writer emits to a parallel
   `spout_endpoints.json` file and the legacy `report.json`
   pathway stays byte-stable. The two files coexist; consumers choose
   per their needs. There is no parity test in 8a.7 — the schemas are
   structurally incompatible by design.

   Naming-wise, the kickoff originally called the new artifact
   `spout_endpoints_v2.json` and gave the config block / API kwargs the
   `_v2` suffix to disambiguate from the legacy `report.json`. In 8a.7
   we dropped the `_v2` everywhere — the new outputs land in their own
   tree (`pipeline_outputs/spout_behavior/endpoints/...`), the new
   config block lives under its own namespace
   (`spout_behavior.endpoints:` in `defaults.yaml`), and the new API
   kwarg (`endpoints_params=`) doesn't collide with anything legacy.
   Renamed in this PR: the `endpoints_v2:` block in `defaults.yaml`
   (now `endpoints:`); every `endpoints_v2_params=` callsite in 8a.2–
   8a.6 modules and tests (now `endpoints_params=`); the `V2_PARAMS`
   test fixture name (now `ENDPOINTS_PARAMS`); the docstring path
   examples in `criteria_slugs.py` and `endpoints_writer.py`. Frozen
   archaeology / kickoff docs under `docs/PHASE_8A_*.md` and
   `docs/prompts/phase-8a-*.md` retain the original `_v2` references
   as historical decision-trail context.

2. **Two endpoint slots ship as sentinels in 8a.7.** All four
   `criteria` values land as
   `{"status": "not_yet_computed", "port_scheduled_for": "8a.7.5"}`
   because C1–C4 production computation is not yet ported (verified by
   greps for `criteria_(1|2|3|4)|criteria_training_pass|...` returning
   only the `criteria_slugs.py` slug-bijection helpers and a docstring
   note in `endpoints_per_trial.py`). `inter_session_persistence`
   lands as `{"status": "requires_cohort_aggregation",
   "computed_at": "cohort_aggregation_stage"}` because it's a
   per-animal cross-session metric and the per-session writer stays a
   pure function of per-session inputs. Both sentinels are explicit
   dict objects, never `null` and never absent.

**Exit criteria:**
- [x] `pytest tests/test_endpoints_writer.py -v` → 15 passed.
- [x] `pytest -q` → 335 passed / 28 skipped (320 baseline + 15 new).
- [x] `ruff check src/stroke_orofacial/spout_behavior/endpoints_writer.py
  tests/test_endpoints_writer.py` → clean.
- [x] All four criteria slugs and the inter_session_persistence slot
  emit explicit sentinel dicts (not `null`) — verified by tests.
- [x] Implemented on feature branch `phase-8a-part3-json-writer` off
  main; pre-commit hook in `.githooks/pre-commit` blocks accidental
  commits to main per CLAUDE.md §1.8.

**Deferred to 8a.7.5:**
- Port C3 (per-trial first-correct-lick-present), C4 (per-trial
  correct/incorrect lick-count thresholds), C2 (per-session per-side
  C3∩C4 pass-fraction aggregator), C1 (multi-session C2 training-pass
  over consecutive sessions).
- Replace the four `criteria` sentinel dicts with computed values.
- Parity tests for C3/C4 per-trial booleans against legacy
  `behavior_report_PS.py:455-551` on PS46/20250307 (byte-identical for
  booleans, `1e-12` rtol for the C2/C1 boolean-count aggregates).

---

## Phase 8a.7.5 — Criteria hierarchy port (C3, C4, C2 computed; C1 stays cohort-aggregation sentinel)

**Date:** 2026-04-20.

**What was done:**

- New module `src/stroke_orofacial/spout_behavior/criteria.py` (~330
  lines incl. docstrings) ports the per-trial and per-session-per-side
  legacy pass-criteria from
  `docs/legacy_snippets/behavior_report_PS_455_551.py` (verbatim excerpt
  of `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/analysis/behavior_report/behavior_report_PS.py:385-565`)
  into pure-function compute entry points:
  - `compute_c3_first_correct_lick_present(trials, *, defaults)` — per-trial
    boolean; passes iff at least one correct-side (rewarded) lick falls in the
    C3 window (`[0, 2.0]` s post-reward).
  - `compute_c4_correct_lick_count_threshold(trials, *, defaults)` —
    per-trial boolean; passes iff `n_correct ≥ num_licks_correct_min` AND
    `n_incorrect ≤ num_licks_incorrect_max` in the C4 window (`[0, 2.5]` s).
    Fail-loud `ValueError` when a caller passes TrialRecords built with a
    narrower window than C4 requires.
  - `compute_c2_session_trial_pass_fraction_above_threshold(c3_block,
    c4_block, *, defaults)` — per-session per-side boolean + NaN-preserving
    fraction; passes iff the fraction of C3∩C4-passing trials meets
    `fraction_pass` (0.6 default). Zero-trial sides emit `NaN` fraction and
    `False` pass, matching legacy semantics.
  - `build_criteria_block(trials, *, defaults)` — single entry point
    returning the 3-key dict the writer's `criteria` parameter accepts
    (C3, C4, C2). C1 stays writer-owned.
- Per-side output shape:
  `{"per_side_per_trial_pass": {"L": [bool, ...], "R": [bool, ...]}}` for
  C3/C4; `{"per_side_pass", "per_side_fraction", "per_side_n_trials"}` for
  C2. Per-side lists preserve reward-index chronological order within side —
  byte-identical to the legacy iteration convention thanks to the stable sort
  in `build_per_trial_records`.
- `endpoints_writer.py` now takes a required `criteria: dict` parameter
  (3 caller-supplied slugs). The writer fills
  `criteria_training_pass_consecutive_sessions` (C1) internally with the
  existing `INTER_SESSION_REQUIRES_COHORT_SENTINEL`, aligning C1's sentinel
  vocabulary with `inter_session_persistence` per DECISIONS.md 2026-04-20
  §"8a.7.5 split from 8a.7". The 8a.7 `CRITERIA_NOT_YET_COMPUTED_SENTINEL`
  constant is retired (no longer emitted). Two new module-level constants —
  `CALLER_SUPPLIED_CRITERIA_SLUGS` (frozenset of 3) and
  `COHORT_AGGREGATED_CRITERIA_SLUG` (C1) — make the caller/writer split
  explicit. `metadata.phase` string bumped from `"8a.7"` to `"8a.7.5"` so
  artifacts are self-describing.
- New validator `_validate_criteria_keys` enforces: missing / unknown / extra
  keys raise `ValueError`; supplying the C1 slug in `criteria` raises
  explicitly (caller cannot override the writer-owned sentinel slot).
- `tests/test_criteria.py` (20 tests, ~460 lines) covers:
  - Synthetic unit tests for C3 (empty trials, correct-side lick in/out of
    window, half-open boundary, per-side chronological ordering), C4 (exact
    count threshold, one-below, incorrect-lick rejection, narrower-TrialRecord
    `ValueError`, config snapshot), C2 (empty sides, zero-trial side with
    other-side pass, fraction at/below threshold, C34 intersection).
  - Inline-reference parity — a numpy re-implementation of the legacy
    snippet's algorithm run on a hand-built 12-trial synthetic session,
    asserted dict-equal to the production `build_criteria_block` output.
    Covers boundary-inclusive / exclusive timing, single-side sessions, and
    empty sessions.
  - **Real-data parity on PS46/20250307** via the MICROSCOPE wavesurfer
    mount (Windows `\\research.files.med.harvard.edu\...\wavesurfer` or Mac
    `/Volumes/Neurobio/MICROSCOPE/Priya/.../wavesurfer`). Runs Phase-2
    `find_licks_and_rewards` → `build_per_trial_records(window=(0, 2.5))` →
    `build_criteria_block` → compares byte-identical with the inline
    reference re-run on the same raw `(lick_L, lick_R, reward_L, reward_R)`
    arrays. Skips gracefully when the mount is unreachable (mirrors
    `tests/test_bouts.py` integration-test convention).
- `tests/test_endpoints_writer.py` (21 tests) updates:
  - `writer_kwargs` fixture now carries a valid 3-slug `criteria` dict.
  - `test_metadata_block_complete` bumped to assert `phase == "8a.7.5"`.
  - `TestSentinels::test_criteria_block_sentinel_pattern` **replaced** with
    a new `TestCriteriaComputed` class asserting (a) caller-supplied C3/C4/C2
    blocks serialize byte-identical, (b) C1 is auto-filled with the cohort
    sentinel, and (c) all 4 criteria slugs are present. `test_inter_session_sentinel_passthrough` remains.
  - New `TestCriteriaValidation` class covers missing / unknown / C1-override
    / empty-dict rejection paths.
- Boundary-semantics audit: the legacy `bnpm.indexing.find_idx_within_eps`
  uses the same half-open `[v - eps[0], v + eps[1])` convention as the
  existing `_find_idx_within_eps` port at
  `src/stroke_orofacial/spout_behavior/bouts.py:236-254` and as
  `build_per_trial_records`. At integer Fs (1000 Hz), `int(round(w*Fs)) ==
  int(w*Fs)`, so the port introduces no boundary divergence from the
  snippet. Confirmed by the real-data PS46/20250307 parity test.

**Intentional behavior differences vs. legacy:**

1. **C1 stays a per-session-JSON sentinel.** The legacy
   `behavior_report_PS.py:549-551` computes C1 (training-pass over the last
   `num_consecutive_pass` sessions) inline after C2. In the consolidated
   pipeline, C1 is a multi-session quantity and is computed by a future
   cohort-aggregation stage that tracks which per-session JSONs it depends
   on. The per-session writer auto-emits the
   `{"status": "requires_cohort_aggregation", "computed_at": "cohort_aggregation_stage"}`
   sentinel for the C1 slot. This preserves the "JSON = pure function of
   this session's data" provenance contract (see DECISIONS.md 2026-04-20
   §"8a.7.5 split from 8a.7" for the full rationale).
2. **Per-side chronological list shape replaces the legacy per-trial-index
   dict shape.** Legacy emits
   `criteria_3[date][side][idx_reward] -> bool`; the new JSON emits
   `{"per_side_per_trial_pass": {"L": [bool, ...], "R": [bool, ...]}}` —
   semantically equivalent (same ordering, same booleans), more JSON-natural
   (no stringified integer keys), and byte-identical under the parity test.
3. **TrialRecord window contract.** The C4 compute function rejects any
   TrialRecord whose `window_seconds` is narrower than C4's window (legacy
   default `[0, 2.5]`). The legacy snippet never hit this condition because
   its input was always the raw `lick_idx[date][f"Lick_{side}"]` array (full
   session), not a pre-sliced trial buffer; the new code has pre-sliced
   buffers and fails loud rather than silently truncating — consistent with
   the Phase 13 vendoring policy.

No legacy-function bugs surfaced that required a Phase-13-style divergence.
The real-data PS46/20250307 parity passes byte-identical, so no DECISIONS.md
divergence-rationale entry is needed for this sub-phase.

**Exit criteria:**
- [x] `pytest tests/test_criteria.py -v` → 20 passed (includes the real-data
  PS46/20250307 parity test).
- [x] `pytest tests/test_endpoints_writer.py -v` → 21 passed.
- [x] `pytest -q` → 361 passed / 28 skipped (was 335 passed / 28 skipped
  after 8a.7; +26 new tests = +20 criteria + +6 writer).
- [x] `ruff check src/stroke_orofacial/spout_behavior/criteria.py
  src/stroke_orofacial/spout_behavior/endpoints_writer.py
  tests/test_criteria.py tests/test_endpoints_writer.py` → clean.
- [x] Per-trial C3 and C4 per-side boolean lists byte-identical to the legacy
  snippet's algorithm on PS46/20250307 (verified by
  `TestRealDataParityPS46_20250307`).
- [x] C2 per-session-per-side booleans byte-identical; per-side fractions
  exact-equal (integer-count ratios — no float tolerance needed).
- [x] C1 slot emitted as `requires_cohort_aggregation` sentinel, not
  caller-override-able.
- [x] Implemented on feature branch `phase-8a-part4-criteria-hierarchy`.

**Post-merge appendix (2026-04-20) — external bnpm parity finding:**

After PR #42 merged, an independent external-bnpm parity sweep (Mac-local
scratch script running the inline reference with bnpm 0.6.0's
`find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1
session each) found one Category 2 divergence at **PS50/20250324 trial
k=40, L side**. Reproducer: reward_idx = 3,422,003; C4 window (0, 2.5) s;
L licks in the window are [3,422,497, 3,422,906, 3,423,057, 3,423,239,
3,423,436]; window right edge 3,424,503 > last lick 3,423,436.
Root cause is an upstream bug in **bnpm 0.6.0 `find_idx_within_eps`**:
`np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr) = 26`
when the right edge is past every element, and the upstream implementation
clamps to `len(arr) - 1 = 25`, which excludes `arr[25]` — the final lick.
Production (`criteria.py:_sub_window_counts` using
`(licks >= lo) & (licks < hi)` on pre-windowed `TrialRecord.licks_*_indices_in_window`)
is correct and includes all 5 licks, so PS50's C4 L-side trial k=40
correctly passes. The PS46/20250307 parity that sub-phase 8a.7.5 gated on
remains byte-identical — this finding does not affect the sub-phase's exit
criteria. **Verdict:** intentional divergence from upstream bnpm under the
Phase 13 vendoring pattern (production untouched, correct; upstream wrong).
Captured as a new bullet under DECISIONS.md 2026-04-20 "Phase 8a
architecture" entry and guarded by
`tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`.
PS51/20250502 re-run skipped (not needed for triage). Upstream bnpm issue
filing is deferred / optional. **Forward obligation:** the same clamp bug
exists in the private `_find_idx_within_eps` port at
`src/stroke_orofacial/spout_behavior/bouts.py:236-256` (peri-reward mask
caller); it does not affect criteria.py (which never calls it), but a
Phase-13-pattern fix-PR will follow the Phase 5/6 indexing-module refactor
(`_find_idx_within_eps` → `_utils/indexing.py`) and must land before Phase
5/6 code writes begin so Phase 5/6 does not consume the buggy helper.

---

## Phase 8a.8 — Recovery-trajectory visualization helpers

**Date:** 2026-04-22.

**What was done:**
- Added `src/stroke_orofacial/spout_behavior/recovery_trajectories.py` as the
  Phase 8a.8 data-assembly and plotting layer for per-session
  `spout_endpoints.json` payloads.
- Implemented endpoint JSON discovery/loading, scalar metric extraction via
  dot paths (for example `per_session_aggregate.mean_s`), trajectory-point
  assembly with an `animal -> group` visualization hook, cohort mean+SEM
  summaries by day-relative-to-stroke, and Matplotlib figure save helpers.
- Added `tests/test_recovery_trajectories.py` with synthetic coverage for
  nested metric extraction, side-aware aggregate extraction, sentinel handling,
  group assignment, missing-day skipping, cohort SEM, JSON discovery/loading,
  and representative cohort plot/save behavior when Matplotlib is importable.

**Intentional behavior differences vs. legacy:**
- Legacy `summary_PS.py` tiled per-animal plots into per-metric grids but did
  not implement cohort mean+SEM recovery curves or phenotype-group hooks.
  Phase 8a.8 adds those as consolidated-pipeline visualization helpers.
- Phenotype classification is still out of scope. The only Phase 8a.8 surface
  is a caller-provided grouping function, defaulting to `"all"` for every
  animal; Phase 9.1 supplies real phenotype labels later.

**Scope guard:** No DLC, Phase 7, notebook, config, schema, source-data, or
legacy-repo edits. The new module consumes existing Phase 8a endpoint JSON
payloads and leaves endpoint computation unchanged.

**Validation:**
- [x] `ruff check src/stroke_orofacial/spout_behavior/recovery_trajectories.py tests/test_recovery_trajectories.py`
  — clean under `conda run -n stroke_orofacial`.
- [x] `python -c "import numpy; import matplotlib"` under
  `conda run -n stroke_orofacial` — imports cleanly (`numpy 2.4.3`,
  `matplotlib 3.10.8`). An earlier direct invocation of
  `C:\Users\sabatini\.conda\envs\stroke_orofacial\python.exe` failed because it
  bypassed conda activation / DLL path setup; that was an invocation issue, not
  a missing NumPy install.
- [x] `pytest tests/test_recovery_trajectories.py -q --basetemp=C:/Users/sabatini/pytest_tmp_phase8a8_conda_verify`
  under `conda run -n stroke_orofacial` — 8 passed in 0.79s.
- [x] `pytest --collect-only -q --basetemp=C:/Users/sabatini/pytest_tmp_collect_phase8a8_verify`
  under `conda run -n stroke_orofacial` — 506 tests collected in 1.13s.

---

## Phase 8a.9 — Legacy behavior-report rollup (docs-only)

**Date:** 2026-04-22.

**What was done:**
- Added `docs/phase-8a/legacy-behavior-report-rollup.md` as the compact
  close-out index for the legacy behavior-report walkthrough required by Audit
  Item 10 Q9.
- Linked the rollup from `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`, while
  leaving that archaeology document as the detailed evidence base.
- Recorded canonical sources (`behavior_report_PS.py`, `summary_PS.py`,
  `batch_process_behavior_report_20260116PS.ipynb`), the superseded
  non-target (`behavior_report.py`), Q9 endpoint dispositions, criteria
  hierarchy status, and explicit non-goals.

**Intentional behavior differences vs. legacy:** None. Documentation-only
rollup; no source code, schema, notebook, config, output, or source-data changes.

**Scope guard:** The rollup keeps Phase 8a.8 visualization, Phase 5.5 polish,
external-bnpm script disposition, cohort Phase 5/6 retests, and PS48 multi-half
handling on the docket. PS48 multi-half handling remains separate because it
touches shared I/O and can affect Phase 7 DLC loading.

**Exit criteria:**
- [x] Rollup points to `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` as the evidence
  base.
- [x] No DECISIONS.md entry added; no new project decision was made.
- [x] Docs-only validation via `git diff --check` and targeted `rg` searches.

---

## Phase 5/6-prep — Factor `_find_idx_within_eps` into shared `_utils/indexing.py`

**Date:** 2026-04-20.

**What was done:**
- Created new package-private module
  `src/stroke_orofacial/_utils/indexing.py` (~35 lines incl. docstring) as
  the home for sorted-array / integer-index utilities that complement the
  boolean-mask helpers already in
  `src/stroke_orofacial/_utils/bool_indexing.py`. Module split is by return
  type (bool mask vs. integer index array), not provenance.
- Moved `_find_idx_within_eps` verbatim from
  `src/stroke_orofacial/spout_behavior/bouts.py:236-256` into the new
  module. The function keeps its underscore prefix (still package-private)
  and its original docstring; implementation is byte-identical to the prior
  location — no behavior change in this refactor.
- Updated `bouts.py` to import `_find_idx_within_eps` from
  `stroke_orofacial._utils.indexing`. Two caller sites inside `bouts.py`
  (`find_peri_reward_periods`, `_make_peri_event_bool`) unchanged.

**Motivation:** Phase 5/6 (reward-aligned kinematics / DLC peri-reward
windows, including 8-s-post-reward windows used in later analyses) will
need the same sorted-array index helper without cross-importing from
`spout_behavior`. This preparatory refactor ahead of Phase 5/6 kickoff
keeps the Phase 5/6 PR focused on peri-reward extraction logic rather than
entangling it with a cross-module import change.

**Intentional behavior differences vs. legacy:** None. Pure move + import
rewrite; byte-identical parity expected against the prior `bouts.py`
callers.

**Forward obligation — clamp-bug fix before Phase 5/6 kickoff:** The
post-merge external bnpm 0.6.0 parity check documented in the DECISIONS
2026-04-20 "Phase 8a architecture" entry under the "External bnpm parity
finding — Phase-13-pattern intentional divergence from upstream bnpm 0.6.0
(post-merge of 8a.7.5)" bullet identified a `len(arr) - 1` right-edge
clamp bug inherited from the upstream `bnpm.indexing.find_idx_within_eps`
that this helper faithfully ports. The current refactor deliberately
preserves the bug (no behavior change in this PR — easier review). A
separate follow-up PR must land the clamp-bug fix **before** any Phase
5/6 implementation PRs begin, so Phase 5/6 peri-reward extraction does not
consume the buggy helper. That fix is a behavior change; its parity
implications will be re-verified against `tests/test_session_processing.py`
baselines under the Phase 13b `max_frac=1e-4` boolean-tolerance policy. A
regression guard for the "last lick inside sub-window with right edge past
it" primitive path already landed in
`tests/test_criteria.py::TestClampBugRegressionGuards` via the docs+test
PR on `docs/8a.7.5-external-bnpm-parity-findings`. **Closure (2026-04-20):**
clamp-fix landed via PR #46 on branch `fix/indexing-find-idx-within-eps-clamp-bug`
— production `_find_idx_within_eps` no longer clamps the upper bound, mirror-
in-minimum regression tests live at `tests/test_indexing.py`, and the full
post-merge details are captured in the "Clamp-fix for
`_utils/indexing.py:_find_idx_within_eps`" entry below. Forward obligation
discharged; Phase 5/6 kickoff is unblocked.

**Exit criteria:**
- [ ] `pytest tests/test_bouts.py -v` byte-identical pass.
- [ ] `pytest tests/test_session_processing.py -v` byte-identical pass.
- [ ] `ruff check src/stroke_orofacial/_utils/indexing.py
  src/stroke_orofacial/spout_behavior/bouts.py tests/test_bouts.py
  tests/test_session_processing.py` clean.
- [ ] Implemented on feature branch `prep-indexing-module-for-phase-5-6`
  cut from `main`.

---

## Clamp-fix for `_utils/indexing.py:_find_idx_within_eps` — right-edge clamp removed

**Date:** 2026-04-20.

**What was done:**
- Removed the two `il = min(max(0, il), len(arr) - 1)` and
  `ir = min(max(0, ir), len(arr) - 1)` clamp lines from
  `_find_idx_within_eps` in `src/stroke_orofacial/_utils/indexing.py`.
  `np.searchsorted` returns values in `[0, len(arr)]` and `np.arange(il,
  ir)` handles both endpoints at `len(arr)` correctly: the empty-range
  case (window entirely past `arr[-1]`) yields `np.arange(n, n) == []`
  and the overhanging-window case yields the full tail
  `np.arange(il, n)` that includes `arr[-1]`.
- Expanded the module-level docstring with a new
  "Intentional divergence from upstream bnpm 0.6.0 — right-edge clamp
  bug" section explaining the bug, the production reproducer
  (PS50/20250324 trial k=40), and the cross-reference to the regression
  guards in `tests/test_criteria.py::TestClampBugRegressionGuards` and
  the new mirror-in-minimum tests in `tests/test_indexing.py`.
- Expanded the `_find_idx_within_eps` docstring with a
  "Right-edge (no-clamp) semantics" note describing the
  `np.searchsorted(..., side="left") == len(arr)` path and a
  "Lower-bound subtlety (latent, not fixed here)" note flagging the
  `side="right"` strict-greater-than behavior at the lower bound as an
  out-of-scope follow-up (see below).
- Added `tests/test_indexing.py` (~210 lines) mirroring the
  divergent-port test pattern from `tests/test_vendored_bool_indexing.py`:
  hand-rolled clamp-bug regressions
  (`TestClampBugRegression::test_ps50_trial_40_reproducer` plus a
  synthetic minimal case and a "right edge exactly at last element"
  sanity check confirming the un-clamped path still excludes the
  boundary value), edge cases (empty arr, empty vals, window
  before/after arr, single-element arr inside / past-end, multi-val
  concatenation), and random-input parity (500 sorted-int arr × 50 vals
  × four `eps` variants, plus a construction that forces the right edge
  past `arr[-1]` on every trial) against an independent numpy-mask
  reference `_reference_find_idx_within_eps` using
  `(arr > lo) & (arr < hi)` — matches the open-at-lower / strict-below-
  upper convention and has no clamp, so it is always correct at the
  right edge.

**Motivation:** Closes the forward obligation set in the immediately-
preceding "Phase 5/6-prep" entry above and in the DECISIONS.md 2026-04-20
"External bnpm parity finding — Phase-13-pattern intentional divergence
from upstream bnpm 0.6.0 (post-merge of 8a.7.5)" bullet. Phase 5/6
peri-reward extraction (8-s-post-reward windows over kinematic and DLC
streams) routinely hits the overhanging-window path near session-end
licks; consuming the un-fixed helper would carry the
`arr[-1]`-dropping bug into reward-aligned downstream analyses. Landing
the fix on a separate PR (rather than folding it into the Phase 5/6-prep
move) keeps the diff scoped and reviewable: the move PR is byte-
identical, this PR is the behavior change.

**Intentional behavior differences vs. legacy:**
- vs. legacy `bouts.py:236-256` (pre-Phase 5/6-prep) and vs. upstream
  `bnpm.indexing.find_idx_within_eps` 0.6.0: when
  `v + eps[1] > arr[-1]` for some `v` in `vals`, the returned index
  array now includes `len(arr) - 1` (i.e., `arr[-1]`) where previously
  it was clamped out. The PS50/20250324 trial k=40 reward path is the
  canonical reproducer: pre-fix returned 4 indices (`[0, 1, 2, 3]`),
  post-fix returns 5 (`[0, 1, 2, 3, 4]`).
- All other paths (window strictly before arr, window strictly after
  arr's end, window strictly inside arr, empty arr, empty vals,
  multi-val concatenation, lower-bound `side="right"` strict-greater
  semantics) are byte-identical to the pre-fix implementation. The
  random-parity tests in `TestRandomParity::test_random_inputs_match_reference`
  cover these paths and pass against the same numpy-mask reference both
  before and after the change — the only diverging path is the
  right-edge overhang, which is exactly the targeted fix.

**Measured parity drift vs. `session_processing3` baselines:**
- _PS46/20250307 (frozen baseline animal-session, no licks at the
  right-edge overhang path):_ **Zero drift.**
  `tests/test_session_processing.py::TestIntegrationParity::test_parity[20250307]`
  passes byte-identical against the `session_processing3` baseline
  post-fix — no tolerance fallback needed (pass predates the Phase 13b
  `max_frac=1e-4` allowance). Confirmed 2026-04-20 on Mac
  (`fix/indexing-find-idx-within-eps-clamp-bug` @ pre-commit tree), full
  impact-set run: 58/58 pass, 4 unrelated pre-existing pywavesurfer
  file-version warnings. This matches the pre-fix prediction that PS46's
  lick array does not exhibit the overhanging-window pattern (no licks
  beyond the last reward's post-window), so the code path being altered
  is never taken on this session.
- _PS50/20250324 (right-edge overhang animal-session, trial k=40 path):_
  Drift expected and intentional — `per_side_per_trial_pass["L"]`
  flips from `[False]` to `[True]` for this trial, propagating to the
  C2 fraction-pass count and the C4 lick-count threshold. Already
  guarded by
  `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`
  via the prior docs+test PR.

**Exit criteria:**
- [ ] `pytest tests/test_indexing.py -v` — all tests pass (new file).
- [ ] `pytest tests/test_criteria.py -v` — all tests pass, including
  the pre-existing `TestClampBugRegressionGuards`.
- [ ] `pytest tests/test_bouts.py -v` — pass; only behavior change
  affects the right-edge overhang path which the bouts caller does not
  exercise on existing fixtures (verify byte-identical).
- [ ] `pytest tests/test_session_processing.py -v` — pass under the
  Phase 13b `max_frac=1e-4` boolean tolerance policy, with measured
  drift recorded in this entry.
- [ ] `ruff check src/stroke_orofacial/_utils/indexing.py
  tests/test_indexing.py` clean.
- [ ] Implemented on feature branch
  `fix/indexing-find-idx-within-eps-clamp-bug` cut from `main` (post
  Phase 5/6-prep merge, commit 92b5d88).

**Out-of-scope follow-ups (deliberately not in this PR):**
- The `side="right"` lower-bound semantics enforce strict
  `arr[i] > v - eps[0]` rather than the half-open
  `[v - eps[0], v + eps[1])` window the upstream docstring implies.
  This is a latent docstring/code mismatch inherited from upstream
  bnpm; it only matters when an `arr` element exactly equals
  `v - eps[0]` (rare in production lick/reward index arrays). Flagged
  in the function docstring; investigation deferred. If a later phase
  needs the half-open convention, the fix is a one-line
  `side="right"` → `side="left"` swap at the lower bound, plus
  expanded `TestClampBugRegression` coverage and a parity re-run.
- Optional upstream bnpm issue filing for the right-edge clamp bug
  remains deferred / Priya's call.

---

## Phase 6.7 — SessionManifest consolidation refactor

**Date:** 2026-04-20.

**Branch:** `phase-6.7-session-manifest-refactor` (commits `ee64ca3`,
`276148b`, `d2e89c1`, `0126156`, `0ce63d1`, `<this commit>`).

**Pre-refactor pytest baseline (Windows):** 374 passed / 28 skipped /
0 failed. **Post-refactor:** 385 passed / 34 skipped / 0 failed (+11
passes, +6 skips — all from new tests added in 6.7a–d; net behavior
preserved).

**Scope:** Wire the existing `SessionManifest` (Phase 1, DESIGN.md §4.2)
in as the primary input contract for every phase orchestrator, closing
the mid-consolidation audit's "SessionManifest is dead code" observation.
Strictly a refactor — no analysis behavior changes. All Phase 2/3/4
parity guarantees preserved.

Two small orthogonal additions surfaced by the audit are folded in:
- `load_centered_fresh(h5_path, center_mode, likelihood_threshold=0.7)`
  in `src/stroke_orofacial/dlc_io/centering.py` — exploration escape
  hatch alongside the parquet-based pathway. Returns a
  centered DataFrame matching the parquet schema *without* writing to
  disk, so callers can sweep `likelihood_threshold` interactively for
  centering-reference picking. `likelihood_threshold` is exposed as an
  explicit per-call parameter (per Priya 2026-04-20) so different
  thresholds can be explored without rewriting the on-disk parquet
  cache. Resolves the Phase 6.7 plan §3 "exploration escape hatch"
  scope item.
- `save_heatmap_npz(df, bodypart, config, path, *, center_mode,
  nbins=100, ...)` in `src/stroke_orofacial/dlc_spatial/heatmaps.py`
  — saves the fine-grid histogram array as `heatmap_{date}.npz`
  alongside the existing `heatmap_{date}.png` so future figure tweaks
  (different colormaps, axis limits, normalization) and Phase 9
  fine-resolution spatial stats can re-render from disk without
  recomputing from parquet. Wraps `pixel_bins.build_histogram()` (which
  already returns the dict shape we need); does not refactor
  `plot_heatmap` since `build_histogram` is the cleaner integration
  point. NPZ resolution is configurable via `nbins` (default 100
  matches the existing PNG-producing histogram resolution, so adding
  NPZs alongside existing PNGs leaves the PNG content unchanged).
  Resolves DECISIONS.md "2026-04-19 Save fine-grid heatmap NPZ".

### Sub-phase summaries

#### 6.7a — Phase 2 orchestrator (commit `ee64ca3`)

- `process_session(manifest, resolver, ...)` is now primary; reads
  `manifest.wavesurfer_file` instead of re-discovering via
  `resolver.wavesurfer_dir + find_wavesurfer_file`.
- `process_session_by_animal_date(animal, date, resolver, ...)` is the
  new convenience wrapper.
- `process_animal()` rewritten as a thin loop over the wrapper —
  preserves its public surface.
- Notebook `00_session_processing.ipynb` grew from 4 → 5 cells: new
  cell 3 builds `manifests = [(animal, date, manifest), ...]` so the
  per-session discovery is visible in notebook state; cell 4 iterates
  and calls `process_session(manifest, resolver, ...)`.
- New tests: `TestIntegrationProcessSessionWithManifest` (manifest-first
  integration on real data); `TestProcessSessionRaisesOnMissingWavesurfer`
  (unit guard).

#### 6.7a-fix — Symmetric DLC discovery in `build_manifest()` (commit `276148b`)

Architectural bug surfaced during 6.7a's mid-phase review: `build_manifest()`
treated DLC as REQUIRED (raising `FileNotFoundError` on missing DLC dir
or empty filtered-file glob) while wavesurfer and video were OPTIONAL
(try/except → None / []). The asymmetry blocked two first-class
workflows:
  (a) Phase 2 spout behavior on sessions where video recording failed
      but wavesurfer is still clean.
  (b) Behavior analysis on newly-collected sessions before DLC inference
      has been run.

**Fix:** discover DLC the same way as wavesurfer/video — present-or-empty,
no raise. The "I need DLC to proceed" assertion belongs in each
DLC-consuming orchestrator, not in manifest construction. Test contract
updated accordingly: `test_missing_dlc_dir_raises` /
`test_no_dlc_files_raises` rewritten to `*_yields_empty_lists` variants.

#### 6.7b — Phase 3 alignment (commit `d2e89c1`)

- `load_or_compute_alignment(manifest, resolver, params, ...)` is now
  primary. Reads `manifest.wavesurfer_file`,
  `manifest.video_files[0].parent` for cam2 CSV discovery, and
  `manifest.alignment_template` for the existing-template path. Falls
  back to `resolver.alignment_template(animal, date, cam=cam_name)` for
  cam_idx != 2 (manifest only tracks cam2's template).
- `load_or_compute_alignment_by_animal_date(...)` wrapper added.
- **Phase 3 is DLC-agnostic by design** (per Priya 2026-04-20 strict
  input-dependency decision): alignment relates wavesurfer samples to
  camera frames, and camera frames exist whether or not DLC inference
  has run. No DLC guard here — the first DLC guard fires in 6.7c.
- Notebook `02_alignment.ipynb` grew from 4 → 5 cells: new cell 3
  builds manifests (surfaces alignment_template / wavesurfer / video
  discovery); cell 4 iterates and calls
  `load_or_compute_alignment(manifest, ...)`.
- Tests updated: `TestIntegrationAlignment` rerouted through wrapper;
  `TestIntegrationAlignmentWithManifest` (load + force_recompute via
  manifest) and `TestLoadOrComputeAlignmentRaisesOnMissingWavesurfer`
  (unit guard) added.

#### 6.7c — Phase 4 parquet builder + `load_centered_fresh` (commit `0126156`)

- `build_centered_parquet(manifest, center_mode, resolver, params, ...)`
  is now primary. Reads `manifest.dlc_h5_files` directly (drops the
  `discover_dlc_filtered_files` call).
- **Phase 4 is the FIRST DLC-required orchestrator.** Raises
  `FileNotFoundError` at the top if `manifest.dlc_h5_files` is empty,
  with a clear session-scoped message ("Phase 4 parquet building
  requires DLC. Either provide a manifest with DLC files, or run DLC
  inference first.").
- `build_centered_parquet_by_animal_date(...)` wrapper added.
- New `load_centered_fresh()` helper (described above).
- Notebook `11_dlc_build_parquets.ipynb` grew from 4 → 5 cells:
  manifest-build cell with up-front DLC-availability count.
- Tests: `TestBuildCenteredParquetWithManifest` (Mac-gated integration
  — also closes the existing test-coverage gap that there was no test
  exercising `build_centered_parquet` end-to-end);
  `TestBuildCenteredParquetRaisesOnEmptyDlc` (unit guard);
  `TestLoadCenteredFresh` (3 unit tests for the new helper).

#### 6.7d — Phase 5/6 spatial + `save_heatmap_npz` (commit `0ce63d1`)

- `build_reward_aligned_analysis(manifest, bodypart, center_mode,
  trial_group, window_ms, resolver, spatial_config, reward_config)` is
  now primary. Uses `manifest.dlc_h5_files[0]` for parquet locating and
  `manifest.alignment_template` (cam2) for the alignment LUT.
- Phase 6 is DLC-required (same guard pattern as Phase 4).
- `build_reward_aligned_analysis_by_animal_date(...)` wrapper added.
- Phase 5/6 spatial functions (`pixel_bins.build_histogram`,
  `heatmaps.plot_heatmap`, etc.) operate on already-loaded parquets and
  don't need the manifest — only the orchestrator notebooks build
  manifests and use them to locate parquets.
- New `save_heatmap_npz()` helper (described above).
- Notebook `11_dlc_spatial_whole_session.ipynb` grew from 4 → 5 cells:
  manifest-build cell + `HEATMAP_NBINS = 100` USER INPUT + writes the
  fine-grid NPZ alongside the existing PNG via `save_heatmap_npz`.
- Notebook `12_dlc_spatial_reward_aligned.ipynb` grew from 4 → 5 cells:
  manifest-build cell + `HEATMAP_NBINS` USER INPUT (reserved for future
  per-call overrides; reward-aligned analyses currently use the
  `dlc_spatial_reward_aligned.default_nbins` from config).
- Tests: `TestIntegrationRewardAligned` rerouted through wrapper;
  `TestIntegrationRewardAlignedWithManifest` (manifest-first
  integration);
  `TestBuildRewardAlignedAnalysisRaisesOnEmptyDlc` (unit guard);
  `TestSaveHeatmapNpz` (4 unit tests including parity guard against
  `build_histogram`).

#### 6.7e — Docs (this commit)

- This MIGRATION_LOG entry.
- DECISIONS.md entry closing the mid-consolidation audit's
  "SessionManifest is dead code" observation, plus a one-line note
  that `load_centered_fresh()` complements parquets as an exploration
  escape hatch.

### Refactor pattern (applied consistently)

Every orchestrator follows the same shape:

```python
# Primary signature — takes manifest
def fn(manifest: SessionManifest, resolver: PathResolver, *, ...): ...

# Convenience wrapper — builds manifest from (animal, date)
def fn_by_animal_date(animal, date, resolver, *, ...):
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info)
    return fn(manifest, resolver, ...)
```

Notebooks build the manifest in a new visible cell so the session
picture is in the notebook state rather than hidden inside the
orchestrator. Each of the five notebooks grew from 4 → 5 cells.

### Parity status

- **Test-suite parity:** 374/28/0 → 385/34/0. The +11 passes are unit
  tests added across 6.7a–d (3+1+4+4+1 across the sub-phases minus the
  2 raise-asserting manifest tests rewritten as empty-list-asserting,
  but with new replacements running) covering the new manifest-first
  signatures, the new helpers, and the DLC-required guards. The +6
  skips are Mac-only integration tests. Zero existing passing tests
  flipped to failing or skipping.
- **Phase 2 byte-level (NPZ) parity:**
  `tests/test_session_processing.py::TestIntegrationParity` passes on
  Mac (skipped on Windows). PS46/20250307 + PS46/20250320 bouts NPZ
  comparisons unchanged.
- **Phase 3 array parity:** Spot-check on PS46/20250307 via the
  manifest-first path produces slope=4.006195, intercept=-8747.4 — matches
  this log's Phase 3 entry (lines 330–331) verbatim. Recompute matches
  loaded at rtol=1e-8.
- **Phase 4 parquet hash parity:** Spot-check on PS46/20250307 via the
  manifest-first path produces hashes `c23dc714` (nose) and `2a6efb6a`
  (spout_midpoint) — matches this log's Phase 4 entry (lines 430–432)
  verbatim. `eye_midpoint` hash `b13af51c` preserved by construction
  (the `_param_sig` function is unchanged).
  `tests/test_dlc_parquet.py::TestIntegrationParity` integration test
  unchanged; new
  `TestBuildCenteredParquetWithManifest::test_skip_path_via_manifest`
  asserts the c23dc714-named parquet is returned via the manifest-first
  signature.
- **Phase 5 fine-heatmap parity:** Spot-check via `save_heatmap_npz` on
  PS46/20250307 nose, nose-centered: H_counts.sum() = 925,098 — matches
  this log's Phase 5 entry (line 891) verbatim.
- **Phase 6 reward-aligned parity:** Spot-check on PS46/20250307 tongue
  via the manifest-first path: 96 rewards, 132,096 selected frames,
  histogram H_counts = 54,159 — matches this log's Phase 6 entry (line
  1094) verbatim.
- **Phase 5/6/8a tests untouched:** `tests/test_criteria.py`,
  `tests/test_endpoints_writer.py`, `tests/test_indexing.py`,
  `tests/test_pixel_bins.py`, `tests/test_difference_maps.py`,
  `tests/test_window_selector.py` not modified
  (verified by `git diff main -- tests/test_*` excluding the four
  test files this phase touched: test_session_processing.py,
  test_manifest.py, test_timebase.py, test_dlc_parquet.py,
  test_dlc_centering.py, test_reward_aligned.py, test_heatmaps.py).
- **Ruff `src/`:** clean throughout.

### Intentional behavior differences vs. legacy

1. **`build_manifest()` no longer raises on missing DLC** (per 6.7a-fix
   above). Two callsite paths formerly relying on the raise to short-
   circuit must now check `manifest.dlc_h5_files` themselves; only
   DLC-consuming orchestrators do so (Phase 4 + Phase 6 guard added).
   The two affected `tests/test_manifest.py` tests rewritten from
   `*_raises` to `*_yields_empty_lists`.
2. **All Phase 2/3/4/6 orchestrator primary signatures changed**
   (manifest-first). Existing notebook code calling them with
   `(animal, date, ...)` would break; the `*_by_animal_date` wrappers
   preserve that ergonomic for callers that prefer it. `process_animal`
   rewritten internally to use `process_session_by_animal_date`;
   public surface unchanged.
3. **Notebook orchestrators all build manifests in a visible cell**
   (new cell 3 in each of the five notebooks). Prior notebook code
   passed `(animal, date)` directly; the manifest pattern is more
   inspectable but the orchestration semantics are identical.
4. **New `heatmap_{date}.npz` artifacts written by Notebook 11**
   alongside the existing PNGs. PNG content unchanged (same nbins=100
   default). Resolves DECISIONS.md 2026-04-19 fine-grid NPZ ask. The
   NPZ is additive: existing `heatmap_{date}.png` paths remain
   byte-identical to pre-6.7d outputs.

### Exit criteria

- [x] `pytest -q` 385 passed / 34 skipped / 0 failed (Windows; baseline
  was 374/28/0).
- [x] `ruff check src/` clean.
- [x] Phase 4 parquet hashes (c23dc714 / 2a6efb6a / b13af51c) preserved
  through the manifest-first path; verified via spot-check.
- [x] Phase 3 alignment slope/intercept for PS46/20250307 unchanged at
  rtol=1e-8.
- [x] Phase 5 fine-heatmap H_counts.sum() = 925,098 unchanged
  (PS46/20250307 nose, nose-centered).
- [x] Phase 6 reward-aligned counts (96 rewards, 132,096 selected
  frames, tongue H_counts=54,159) unchanged.
- [x] Phase 5/6/8a test files (`tests/test_criteria.py`,
  `tests/test_endpoints_writer.py`, `tests/test_indexing.py`,
  `tests/test_pixel_bins.py`, `tests/test_difference_maps.py`,
  `tests/test_window_selector.py`) not modified.
- [x] DECISIONS.md entry closing "SessionManifest is dead code"
  observation + `load_centered_fresh()` escape-hatch note.

### Out-of-scope follow-ups (deliberately not in this phase)

- **Per-bodypart centering thresholds** (eg nose 0.7, eyes 0.5, spouts
  0.9 instead of cohort-wide 0.7). Per Priya 2026-04-20: keep all
  centering at 0.7 for now; threshold-flexibility work is separately
  tracked as a follow-on if the cohort grows past PS46–PS55.
- **Per-call-site likelihood thresholds at every analysis point** for
  whole-session spatial / reward-aligned / kinematics. Partially
  available today via existing config dicts; formalizing as explicit
  per-call kwargs across all spatial / kinematic functions is a
  separate refactor.
- **`process_session` exclusion-handling integration with
  `manifest.excluded`.** Currently `process_session` does not act on
  `manifest.excluded`; callers pre-filter. Adding a skip-if-excluded
  short-circuit would change behavior on dates currently being
  processed despite an exclusion, which is out of scope for this
  refactor.

---

## Task #17 — Wavesurfer L/R ↔ mouse-frame boundary-layer translation

**Date:** 2026-04-21.

**What was done:**
- Established the project-wide convention that **every output artifact
  (NPZ, JSON, parquet) is emitted in the mouse frame** with two
  metadata scalars declaring the rig convention, while **internal
  pipeline arithmetic stays on the wavesurfer frame** to preserve
  Phase 3/4/5/6 parity baselines. Five-commit PR:
  - **Commit 1 — schema.** New `wavesurfer_sides_match_mouse_sides:
    bool = False` field on `AnimalInfo`. All 8 animals in
    `configs/animals.yaml` (PS46–PS55) get explicit
    `wavesurfer_sides_match_mouse_sides: false` (fail-conservative,
    current cohort is mirrored). `load_animals()` parses with `.get()`
    default False and rejects non-bool values to catch yaml-typo'd
    `"false"` strings at load time. `SessionManifest` gains the same
    field, populated from `AnimalInfo` in `build_manifest()` so every
    orchestrator has it without re-loading the animals config.
  - **Commit 2 — helper module.** New
    `src/stroke_orofacial/lr_convention.py` with `to_mouse_frame(side,
    wavesurfer_matches)` (returns unchanged when matched, flips L↔R
    when mirrored; rejects anything other than exact `"L"`/`"R"`) and
    `stamp_side_convention(payload, wavesurfer_matches, version=1)`
    (adds two scalar keys in-place; rejects non-bool flag, non-int
    version, bool-as-version, and collisions on either scalar).
    `SIDE_CONVENTION_VERSION = 1` is the initial scheme; bumps on any
    change to the scheme itself.
  - **Commit 3 — apply at emitters.** Wired translation + stamp into:
    - `src/stroke_orofacial/spout_behavior/session_processing.py`:
      new `_translate_side_keys` renames `*_L`/`*_R` suffixed NPZ keys
      to mouse frame; new `_save_npz_with_side_convention` wraps
      `np.savez` with translation + stamp. All 7 Phase 2 NPZs now carry
      the convention scalars; the three L/R-carrying ones
      (`wavesurfer_signals_processed`, `licks_and_rewards`,
      `peri_reward_periods`) get key translation.
    - `src/stroke_orofacial/spout_behavior/endpoints_writer.py`:
      `write_session_endpoints_json` gains required
      `wavesurfer_sides_match_mouse_sides` kwarg. Three new helpers
      (`_translate_per_side_dict`,
      `_translate_criteria_block_to_mouse_frame`,
      `_translate_endpoints_block_to_mouse_frame`) walk the criteria
      block's four per-side dicts (`per_side_per_trial_pass`,
      `per_side_pass`, `per_side_fraction`, `per_side_n_trials`) and
      the endpoints block's `per_trial_type_split` dicts and flip L↔R
      keys for flipped-rig animals. The metadata block is stamped
      with the convention scalars via `stamp_side_convention`.
  - **Commit 4 — regression guards.** 14 new tests across two
    classes: `tests/test_session_processing.py::TestSideConventionAtEmit`
    (7 tests, direct unit tests of `_translate_side_keys` +
    `_save_npz_with_side_convention`; parametrized matched/mirrored
    stamp presence; foundational emit-invariant pin) and
    `tests/test_endpoints_writer.py::TestSideConventionAtEmit`
    (5 tests: matched-rig key preservation, flipped-rig key swaps in
    criteria + endpoints, parametrized metadata-stamp assertion, C1
    sentinel pass-through on flipped rig).
  - **Commit 5 — docs + runbook.** New DESIGN.md §14 "CONVENTIONS"
    establishing the project-wide rule; new
    `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`; this
    MIGRATION_LOG entry.

**Parity strategy:**
- Internal pipeline arithmetic untouched → Phase 3/4/5/6 parity against
  the `session_processing3` baselines stays byte-identical in the
  *array values*. Only the NPZ *key names* change at emit.
- Test-side `_unflip_new_to_wavesurfer_frame` helper in
  `tests/test_session_processing.py::TestIntegrationParity` un-flips
  the emitted mouse-frame labels back to wavesurfer frame before
  comparing against `session_processing3`. Verified on PS46/20250307
  + PS46/20250320: all 6 compared arrays (Treadmill_smoothed,
  Lick_L/R, Reward_L/R, running/grooming/quiet/peri_reward bools)
  match the baseline to existing tolerances (equal / allclose /
  bool_near_equal max_frac=1e-4). The un-flip helper is test-side
  only — production readers consume mouse-frame labels as canonical.
- Phase 8a.7.5 `spout_endpoints.json`: no pre-existing parity fixture
  (schema is a clean break from legacy `report.json` per 8a.7
  scoping decision Q6), so commit-3 parity is guarded by the
  commit-4 regression tests which pin specific L/R dict values
  through both matched and flipped paths.
- Full suite: 454 → 482 passed (+28 from task #17: 4 animals +
  31 lr_convention + 7 session-processing guards + 5 endpoints-writer
  guards − 19 pre-existing reframings such as writer_kwargs fixture
  edits). 6 integration tests skip when MICROSCOPE mount / legacy
  baselines aren't available (unchanged).

**Intentional behavior differences vs. legacy:**
1. **Post-task-#17 NPZs and JSONs carry mouse-frame L/R labels** —
   every consumer loading `licks_and_rewards.npz` and reading
   `Lick_L` now gets mouse-L lick indices (on the current PS46–PS55
   cohort, this is what wavesurfer recorded under `Lick_R`). Legacy
   `session_processing3` artifacts are wavesurfer-frame and
   unchanged; the consolidated output directory tree
   (`stroke_orofacial_pipeline_outputs/spout_behavior/`) is now
   mouse-frame. The two coexist; consumers choose based on which
   tree they read from.
2. **Every consolidated output artifact carries two convention
   scalars** (`wavesurfer_sides_match_mouse_sides`,
   `side_convention_version`). Legacy artifacts do not. Readers
   should gate on the version: version 1 is the current scheme;
   absent scalars means pre-task-#17 artifacts that must be
   interpreted as wavesurfer frame.
3. **The legacy `behavior_report_PS.py` plot-label flip** (via
   `fn_flip_lr`) was a display-only flip that left stored data in
   wavesurfer frame. The new convention is the strict opposite —
   stored data is mouse-frame and plots can use the label directly.
   Ports of legacy kinematics notebooks (Phase 7) should load from
   consolidated NPZs rather than wavesurfer directly, and skip the
   ad-hoc per-notebook flips (cell 25 in `20260203_..._tongue.ipynb`,
   cells 22/24 in `20260416_..._jaw.ipynb`).

**Deferred (documented in the runbook):**
- `src/stroke_orofacial/dlc_spatial/heatmaps.py::save_heatmap_npz`:
  the heatmap NPZ payload has no L/R keys; the only L/R surface is
  the reward-aligned `trial_group` filename/directory slug
  (`reward_L_trials` / `reward_R_trials`), which is set by the caller
  (notebook 12). Threading the convention flag through the notebook
  orchestrator to translate `trial_group` at the path layer is a
  follow-up PR per the runbook.
- `src/stroke_orofacial/dlc_spatial/reward_aligned.py::trial_group`
  semantics: currently interpreted as wavesurfer frame. Flipping to
  mouse frame is caller-visible and gated on the notebook-12 /
  heatmap-path follow-up.

**Exit criteria:**
- [x] `pytest tests/ -q` → all pass, no regressions (454 passed, 6
  skipped pre-task-#17; post-task-#17 adds 28 new tests).
- [x] `ruff check` clean on all touched files.
- [x] Integration parity on PS46/20250307 + PS46/20250320 via the
  un-flip helper: byte-identical against `session_processing3`.
- [x] Matched-rig and flipped-rig paths both exercised by
  regression guards in commit 4.
- [x] DESIGN.md §14 documents the convention.
- [x] Runbook at `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
  captures the re-emit procedure and the Phase 5/6 follow-up gate.
- [x] Implemented on feature branch `feat/wavesurfer-side-convention`
  cut from `main` at `0ff6fd9`.

---

## Task #17 follow-up — Phase 2 re-emit across PS46–PS55

**Date:** 2026-04-21.

**Scope:** Executed `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
§1–§4 + §7 on the Windows clone against the MICROSCOPE SMB mount.

**Phase 2 re-emit:** 257 sessions emitted across all 8 cohort animals
(PS46–PS55) via the manifest-first `process_session(manifest, resolver,
overwrite="force")` path (post-6.7a). 138 sessions skipped (no
wavesurfer file present on MICROSCOPE — raw wavesurfer mirror from
Mac-local is still pending per the Phase 2 entry's "Known constraints"
bullet). 0 errors. Total artifact count: 1799 NPZs (257 × 7 types).

| Animal | Sessions emitted | NPZs (×7 types) |
|--------|-----------------:|----------------:|
| PS46 | 21 | 147 |
| PS47 | 21 | 147 |
| PS48 | 20 | 140 |
| PS49 | 22 | 154 |
| PS50 | 19 | 133 |
| PS51 | 52 | 364 |
| PS54 | 52 | 364 |
| PS55 | 50 | 350 |
| **TOTAL** | **257** | **1799** |

**Stamp verification:** every emitted NPZ (1799/1799) carries both
`wavesurfer_sides_match_mouse_sides` (False, matches cohort yaml) and
`side_convention_version=1`.

**Label-flip verification:** of the 2 pre-re-emit PS46 sessions in the
backup, only PS46/20250320 was actually pre-task-#17 (no stamps;
`run_timestamp` 2026-04-17). Re-emit correctly flipped L↔R across all
3 side-keyed NPZ types (`wavesurfer_signals_processed`,
`licks_and_rewards`, `peri_reward_periods`): 8/8 L/R pairs, all
non-trivial (counts e.g. `Lick_L`: 1200 → 756, `Lick_R`: 756 → 1200).
PS46/20250307's backup was already post-task-#17 (stamps present;
`run_timestamp` 2026-04-21T06:17:15 — predates the re-emit), so the
re-emit produced byte-identical output. See the hygiene note below for
why the 20250307 artifact was already post-task-#17 pre-re-emit.

**§5 (Phase 8a.7.5 JSON re-emit) — no-op, not executed:** no
production cohort orchestrator currently calls
`write_session_endpoints_json()` — the writer + criteria are unit-
tested only (`tests/test_endpoints_writer.py`, `tests/test_criteria.py`).
`stroke_orofacial_pipeline_outputs/spout_behavior/endpoints/` does
not exist on MICROSCOPE; there is no cohort of 8a.7.5 JSONs on disk to
re-emit. Matches the Phase 8a.7.5 "no pre-existing parity fixture"
callout earlier in this log. Cohort emit is deferred to a future phase;
no action taken on the re-emit runbook §5 this pass.

**Backup scope:** narrowed to the `spout_behavior/` subtree (16 files,
0.397 GB) rather than the runbook's literal full-tree copy. Backed up
to the sibling `stroke_orofacial_pipeline_outputs/spout_behavior.pre-task17.bak/`
following the runbook's `.pre-task17.bak` naming. Phase 4 parquets
(`dlc_analysis/centered_*/`), Phase 3 alignment templates
(`alignment/cam2/`), and all Phase 5/6 outputs
(`dlc_analysis/spatial_*/`) were untouched by the re-emit so backing
them up adds no recovery value for this operation — rationale recorded
for review.

**§7 (Phase 5/6 deferral) verified:** `dlc_analysis/spatial_whole_session/`
(18 files, max mtime 2026-04-20T09:38:13) and
`dlc_analysis/spatial_reward_aligned/` (54 files, max mtime
2026-04-20T09:41:57) are both strictly pre-re-emit. Re-emit ran on
2026-04-21 and did not touch either tree. Heatmap NPZ convention-flip
deferral per runbook §7 remains tracked as a Phase-7-blocking follow-up.

**Known-benign drift on `Treadmill_smoothed`:** comparing the
post-task-#17 PS46/20250307 backup to the re-emit of the same session
shows max abs diff 1.78e-14, max rel diff 4.17e-9 on the
`Treadmill_smoothed` float64 array (3,610,000 samples; 3,153,308
elements differ by 1–2 ULP, 456,692 exactly equal).
`np.allclose(rtol=1e-10, atol=1e-10)` passes. This is threaded-scipy
filter-order reordering between consecutive runs on the same Windows
host — well inside the integration-parity tolerance
(`TestIntegrationParity` uses `rtol=1e-10, atol=1e-10` for allclose
arrays). Not a regression.

**Hygiene finding triggered by the PS46/20250307 timestamp anomaly:**
two Mac-gated integration test cases write to the real
`stroke_orofacial_pipeline_outputs/spout_behavior/` tree (rather than
`tmp_path`) via `overwrite="force"`:

- [tests/test_session_processing.py:152-173](../tests/test_session_processing.py#L152-L173)
  `TestIntegrationProcessSession.test_process_and_params_json_written`
  — `process_session_by_animal_date("PS46", 2025-03-07, resolver,
  overwrite="force")` emits the PS46/20250307 artifacts into the
  production output path. On a Mac with MICROSCOPE mounted, running
  `pytest` on this branch after task #17 merged is sufficient to
  re-emit 20250307 with mouse-frame labels — which is exactly what
  happened to the pre-re-emit backup observed at
  `run_timestamp 2026-04-21T06:17:15`.
- [tests/test_session_processing.py:175-198](../tests/test_session_processing.py#L175-L198)
  `TestIntegrationProcessSession.test_skip_path_writes_params_json` —
  same pattern; runs once with force, once with skip, same target
  session + real output path.

This is a test-hygiene smell (integration test mutating the real
production output tree instead of a scratch path) flagged for a
separate cleanup pass; no fix in this entry. Other integration tests
(`TestIntegrationParity` in `test_dlc_parquet.py`,
`TestIntegrationRewardAligned` in `test_reward_aligned.py`) reference
the real output dir for reads only — not a concern.

**`pytest -q` post-re-emit:** 439 passed / 34 skipped / 0 failed / 1
pre-existing warning (Windows). Matches the same counts observed
pre-re-emit on this branch; the re-emit does not affect test
collection or results. Mac-side count differs due to Mac-gated
integration tests skipping on Windows — the 482-passed count recorded
in the task-#17 entry above reflects the Mac baseline.

**No source data modified, no Phase 5/6 outputs modified, no commits
created during re-emit.** Re-emit wrote only to the gitignored
`stroke_orofacial_pipeline_outputs/` tree plus the one-shot
`spout_behavior.pre-task17.bak/` sibling backup.

---

## Phase 6.8a — Phase 5/6 mouse-frame trial_group translation + reward-aligned NPZ writer

**Date:** 2026-04-21.

**Scope:** Closes the Phase 5/6 deferral from Task #17 (runbook §7).
Three coupled changes in one mini-PR (target tag
`v6.8a-phase-5-6-trial-group-translation`):

1. **`load_reward_events` stamp verification.** Reads the
   `side_convention_version` + `wavesurfer_sides_match_mouse_sides`
   scalars stamped on Phase 2 NPZs by Task #17's re-emit and raises
   `ValueError` if the stamp is absent (pre-re-emit file), the version
   drifts, or a caller-supplied flag disagrees with the stamp. After
   this phase, `trial_group="L"` unambiguously means *mouse*-left
   reward trials — a stale pre-re-emit NPZ errors out instead of
   silently swapping L/R on the mirrored rig.
2. **`build_reward_aligned_analysis` flag plumbing.** New
   `wavesurfer_sides_match_mouse_sides` kwarg forwards into
   `load_reward_events` and is echoed on the return dict so the
   downstream writer can stamp without re-lookup. The
   `_by_animal_date` wrapper auto-populates it from
   `AnimalInfo.wavesurfer_sides_match_mouse_sides`; an explicit kwarg
   still wins (used by tests exercising the stamp-mismatch path).
3. **New `save_reward_aligned_npz(result, path)` writer + notebook 12
   adoption.** The canonical reward-aligned notebook (cell 16 of
   `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`) only
   emitted PNGs — no legacy array-level reference existed. Notebook 12
   now emits an NPZ alongside the PNG, carrying `H_counts`,
   `H_proportion`, edges, axis limits, `trial_group`, `window_ms`,
   `n_rewards`, `n_selected_frames`, `bodypart`, `center_mode`, plus
   the two convention scalars. `dlc_spatial/heatmaps.py::save_heatmap_npz`
   also gains optional stamping kwargs (`wavesurfer_sides_match_mouse_sides`,
   `trial_group`, `window_ms`) so Phase 5 whole-session callers can
   adopt the convention non-invasively.

**Rationale for also adding NPZ writing (option A):** Phase 6 had
no legacy array-level parity fixture — cell 16 of the canonical
reward-aligned notebook was never run to produce saved outputs on
MICROSCOPE pre-consolidation (verified 2026-04-21: no
`dlc_analysis/spatial_reward_aligned/*.npz` existed before this PR;
Phase 2 NPZs in `spout_behavior/` were the only reward-keyed artifacts
on disk). This made pre-vs-post drift programmatically unmeasurable.
Writing NPZs within this PR restores that capability, turning drift
into an explicit post-re-emit health-report check rather than a
latent divergence visible only by re-rendering PNGs.

**What didn't change:**
- `lr_convention.py` — untouched; the Phase 6.8 helpers
  (`stamp_side_convention`, `SIDE_CONVENTION_VERSION`) remain
  authoritative.
- PNG content — notebook 12's heatmap PNGs are byte-identical to
  pre-6.8a output for a given session (we only added the NPZ
  alongside; no colormap / axis / binning changes).
- Internal pipeline arithmetic — `trial_group` is routed through
  `load_reward_events` against Phase 2 NPZs that are already
  mouse-frame post-Task-#17, so nothing new is flipped here.

**Test coverage added (tests all new; existing tests retained unchanged):**

- `tests/test_reward_aligned.py`:
  - `TestLoadRewardEvents` (4 pre-existing tests) — fixtures updated
    to stamp NPZs with `stamp_side_convention` so they continue to
    exercise the happy path under the new stamp requirement.
  - `TestLoadRewardEventsStamp` (6 new tests) — one per rejection
    branch: unstamped NPZ, missing match-key, version mismatch,
    caller-flag mismatch, caller-flag-matches happy path, caller-flag-
    None skips cross-check.
- `tests/test_dlc_spatial_side_convention.py` (new file, ~10 tests):
  - `TestSaveRewardAlignedNpz` — schema roundtrip, stamp-matches-flag
    (parametrized True/False), within-PR flag-swap byte-divergence
    symmetry, None-histogram rejection, non-bool-flag rejection,
    parent-dir creation, str-path acceptance.
  - `TestBuildRewardAlignedAnalysisFlagPlumbing` — the primary entry
    point echoes the caller's flag on the return dict (parametrized
    True/False; mocks parquet read + alignment load).
  - `TestBuildRewardAlignedAnalysisByAnimalDate` — wrapper auto-
    populates from `AnimalInfo` (parametrized True/False) and an
    explicit kwarg overrides AnimalInfo (used by mismatch tests).

**Post-merge health report:** `scripts/phase_6_8a_first_run_health_report.py`
walks the emitted tree and asserts, per NPZ, that the stamp is
present and matches `configs/animals.yaml`; and per (animal, date,
bodypart, center_mode, window) bundle that `n_rewards[all] ==
n_rewards[L] + n_rewards[R]` + that metadata is consistent across
L/R/all siblings. Exit 0 = healthy, 1 = at least one failure, 2 = no
NPZs found. Run this once after Priya executes notebook 12 under the
new convention.

**Runbook update:** `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
§7 marked RESOLVED (this PR is what §7 called for); new §8 documents
the first-time Phase 6 NPZ emit procedure (notebook 12 under
`OVERWRITE="force"` then the health-report script). Existing §4
procedure for Phase 2 re-emit is unchanged.

**PR / tag:** merged via PR #62 (squash); tagged
`v6.8a-phase-5-6-trial-group-translation` on the merge commit. Feature
branch preserved on origin per CLAUDE.md §8.

---

## Task #20 — Test-hygiene sweep: integration tests must not write to production output paths

**Date:** 2026-04-21.

**Context:**
The task #17 Phase 2 re-emit (above) surfaced a test-hygiene smell: a
fresh `pytest` run on the Mac against the task-#17 branch had already
re-emitted `stroke_orofacial_pipeline_outputs/spout_behavior/PS46/20250307/`
with mouse-frame labels before the re-emit runbook was executed. Tracing
the timestamp anomaly (pre-re-emit backup's `run_timestamp 2026-04-21T06:17:15`)
pointed at two integration tests in `tests/test_session_processing.py`
that called `process_session_by_animal_date(..., overwrite="force")`
with the default `PathResolver`, which resolves `pipeline_outputs()`
to the real on-disk output tree. A broader sweep during the sweep
itself found two additional offenders that had been added during Phase
6.7a work — four total.

**What was done (one atomic PR on branch `fix/test-hygiene-task-20`,
merged as PR #57, commit `0d18a2b`):**

- **Commit 1 — `feat(paths): add output_root kwarg to PathResolver`
  (`e992433`).** New keyword-only `output_root: Path | str | None = None`
  argument on `PathResolver.__init__`. When supplied,
  `pipeline_outputs(subdir)` returns `output_root / subdir` instead of
  resolving via `root("microscope_pipeline_outputs")`. This is the
  only method that reaches `microscope_pipeline_outputs` (grep
  verified), so the override is surgical — no risk of an unguarded
  writer slipping through. Default behavior is unchanged for every
  existing caller.

- **Commit 2 — `fix(test-hygiene): redirect Phase 2 integration tests
  off production output paths` (`2c4176a`).** Four offenders, all in
  `tests/test_session_processing.py`, switched from the default
  resolver to `PathResolver(output_root=tmp_path)`:
  - `TestIntegrationProcessSession.test_process_and_params_json_written`
  - `TestIntegrationProcessSession.test_skip_path_writes_params_json`
  - `TestProcessSessionWithManifest.test_process_session_with_manifest`
  - `TestProcessSessionEmptyDlc.test_process_session_succeeds_with_empty_dlc`

  Each now writes to the per-test pytest `tmp_path` fixture (auto-
  cleaned by pytest), so repeated test runs cannot mutate the real
  production output tree.

- **Commit 3 — `docs(testing): codify "tests must not write to
  production output paths" (task #20)` (`f1bda6f`).** New
  `docs/testing-conventions.md` documents the rule and the
  `PathResolver(output_root=tmp_path)` pattern. `CLAUDE.md` Repo
  Conventions section links to it. Future contributors (human or
  agent) adding integration tests now have the rule in a durable
  location rather than only in review-cycle memory.

**Verification (before merge):**
- Mac-side hash check before and after the fixed test run on the
  `spout_behavior/` tree: mtime and SHA-256 of every file
  byte-identical; the redirected tests write to `tmp_path` only, not
  the real output tree.
- Full-suite pytest on the PR branch: 469 pass / 6 skip / 0 fail on
  Mac (the 6 skips are Mac-gated Priya integration tests that require
  additional MICROSCOPE paths). `tests/test_session_processing.py`
  alone: 20/20.

**Intentional behavior differences vs. legacy:** None. The redirection
changes where test output is written, not what is computed. Production
writers and their callers are unchanged.

**Notes:**
- `tests/test_dlc_parquet.py::TestIntegrationParity` and
  `tests/test_reward_aligned.py::TestIntegrationRewardAligned` were
  spot-checked during the sweep and confirmed to reference the real
  output dir for reads only (no `overwrite="force"` writes). Not
  modified.
- The `PathResolver.output_root` kwarg is intended for test-fixture
  use only. Production callers should never pass it — the real output
  tree is the canonical landing spot for pipeline artifacts and its
  location is controlled by `configs/paths.yaml`.

---

## Phase 7.0b — Cell-by-cell dead-code classification for Phase-7 reference notebooks

**Date:** 2026-04-21. Merged as PR #60 (commit `2f34aad`), tagged
`v7.0b-cell-classification`.

**What was done:**

Cell-by-cell dead-code classification — option-(b) depth, i.e. label +
port-surface extraction — for all five Phase-7 reference notebooks, per
CLAUDE.md §"Phase plan requirements" item (2). Every candidate cell is
labeled **Production / Exploratory / Deprecated / Ambiguous**; every
Production cell additionally carries algorithm, inputs, outputs,
sub-phase owner, and port approach.

Documents added under `docs/phase-7/`:
- `classification-tongue.md` (59 cells; Q6 tongue-endpoint surface)
- `classification-jaw.md` (45 cells; 7c jaw-kinematics surface)
- `classification-whiskers.md` (whisker-kinematics surface)
- `classification-pixelbin.md` (canonical multi-bodypart heatmap module;
  sibling of per-bodypart heatmap cells in nose/jaw)
- `classification-nose.md` (zero Phase-7 port targets — all Production
  cells are already ported under Phase 4.5 or 5, or scheduled under
  Phase 5.x mini)

No source code changes.

**Scope findings:**

- **Nose has zero Phase-7 port targets.** 9 code cells split: Production
  already-ported under Phase 4.5 (cells 6, 8); Production already-ported
  under Phase 5 with minor gap notes (cells 11, 15); Production scheduled
  for Phase 5.x mini (cell 13); Exploratory (cells 1, 3, 4, 16). Zero
  Deprecated, zero Ambiguous. No interpolation, per-trial endpoint, PSD,
  trial-window, or lick-merge cells in this notebook.
- **Pixelbin subsumes per-bodypart heatmaps.** Nose cells 11/13/15 map
  1:1 to pixelbin cells 11/13/15 as single-bodypart variants of the
  multi-bodypart overlay canonical; the Phase 5.x mini's
  `plot_all_bodyparts_heatmap_binned(bodyparts=["nose"])` subsumes them.
- **Tongue cell 53 scope resolved.** The tongue-jaw mismatch trial
  classifier (not in the Q6 locked endpoint list but a first-class
  analytical output in the canonical tongue notebook) is assigned to
  7c (jaw-kinematics). Recorded in DECISIONS.md
  (2026-04-21 — Tongue cell 53 scope → 7c jaw-kinematics).

**Follow-ups logged (tracked on the TaskList, not in this PR):**

- Docstring cleanup: `dlc_spatial/difference_maps.py` ("cell 12" → cell
  15 reference, off by 3) and `dlc_spatial/heatmaps.py` ("cells 10-11
  of jaw.ipynb" reference doesn't match current jaw extract).
- Phase 5.x mini cell-11 gap: `hist_mode="counts"`, `NORMALIZE_TO_TOTAL`,
  `NORM_MODE ∈ {power, linear}` enhancements for
  `dlc_spatial/heatmaps.py`.
- Phase 5.x mini cell-15 gap: `PRE_BASE_REL_RANGE` config knob for
  baseline-window selection.
- Per-mouse nose axis knobs (`x_trim_each_side`, `y_min_override`,
  `y_max_offset`) to move into `configs/animals.yaml`.

**Unblocks:** Phase 7a-design brief
(`docs/phase-7/interpolation-strategy.md`), which remains blocked on the
Phase 5/6 `trial_group` translation mini-PR
(`v6.8a-phase-5-6-trial-group-translation`) per task #7. That mini-PR is
the documented §7 follow-up of
`docs/runbooks/reemit-phase-5-6-after-lr-fix.md` — `save_heatmap_npz`
and `build_reward_aligned_histograms` get a
`wavesurfer_sides_match_mouse_sides` parameter so reward-aligned
`trial_group` slugs translate to mouse frame at emit time.

**Intentional behavior differences vs. legacy notebooks:** None —
docs-only.

**Exit criteria met:**
- [x] All 5 notebook classifications present under `docs/phase-7/`.
- [x] Every Production cell carries algorithm / inputs / outputs /
      sub-phase owner / port approach.
- [x] Tongue cell 53 scope question resolved (→ 7c).
- [x] PR #60 merged to main, tagged `v7.0b-cell-classification`, feature
      branch preserved on origin.

---

## Phase 6.8a.1 — Distinct FileNotFoundError on prerequisite miss in `build_reward_aligned_analysis`

**Date:** 2026-04-21.

**Context:** Phase 6.8a's first cohort re-emit surfaced a diagnostic
mystery: Windows Claude Code's runner reported 264 DLC-carrying
manifests × 54 (bodypart, center_mode, window) combinations =
14,256 potential reward-aligned builds, but only 1 call succeeded. The
existing code swallowed four distinct prerequisite-miss conditions
behind a single `FileNotFoundError` whose message pointed at whichever
path the OS happened to stat first — a centered-parquet miss, a licks
NPZ miss, an alignment-template miss, and an empty-DLC-files condition
all surfaced as indistinguishable "file not found" errors with no way
to tell which upstream stage had not yet emitted. Priya surfaced this
during the 14,202-failure triage: "the error text doesn't say what was
missing."

**Root cause:** `src/stroke_orofacial/dlc_spatial/reward_aligned.py::
build_reward_aligned_analysis` had three silent `return None` branches
(centered parquet missing, licks NPZ missing, alignment template
missing) plus one `raise FileNotFoundError` for empty `dlc_h5_files`
plus one `return None` for zero rewards of a given `trial_group`. All
three silent-return paths collapsed into the same "data not ready yet"
signal at the caller, and the one raise-path surfaced with a generic
OS-level message once a later `np.load()` hit a missing upstream file.
Callers could not distinguish "Phase 4 hasn't centered this session
yet" from "Phase 2 didn't emit licks" from "alignment templates never
built" from "this trial_group has no rewards."

**What was done:** Converted three of the four prerequisite-miss paths
from silent `return None` to explicit `raise FileNotFoundError` with
artefact-specific messages naming (a) the missing artefact, (b) the
upstream phase that should have produced it, (c) the script to run to
produce it. Kept the zero-rewards path as `return None` — that is a
valid-but-empty data condition, not a missing-prerequisite condition.
Docstring `Returns` + `Raises` blocks updated to reflect the new
contract. New test class `TestBuildRewardAlignedAnalysisRaisesOnMissingPrerequisites`
in `tests/test_reward_aligned.py` (scoped to the centered-parquet
path; licks + alignment paths left uncovered by scope decision —
identical shape, adding them would triple fixture complexity for
marginal coverage gain).

**What stayed the same:**
- Zero-rewards path still returns `None` (distinct from a missing-
  prerequisite condition — tested trial_group had no rewards this
  session, legitimately-empty data).
- Callers that already catch `FileNotFoundError` (notebook 12 runner,
  health-report script) get richer error messages without code
  changes — they were catching the generic exception anyway.
- No array outputs changed; this is a pure error-message refactor.

**Intentional behavior differences vs. legacy notebooks:** None — the
legacy reward-aligned notebook (cell 16 of `20260323_DLC_build-parquet_
reward-aligned_tongue_jaw.ipynb`) has no equivalent orchestrator; it
raises naked Python errors at whichever line first touches a missing
file. The new distinct-error pattern is a repo-level improvement with
no legacy reference to diverge from.

**Verification:**
- Full pytest green on Mac (no new failures; 1 new test passing).
- `pytest --collect-only` clean — no silent collection failures.
- `ruff check` clean.
- Cross-platform merge path: PR opened on Mac (PR #64, squash-merged
  as commit `00ab3b7`); tag `v6.8a.1-distinct-prereq-errors`
  annotated on the squash-merge commit (`a1844b1`) and pushed to
  origin. Feature branch preserved per CLAUDE.md §8.

**Sequencing note:** PR #64 was merged ahead of Windows's in-progress
Phase 6.8a cohort emit so the emit would carry the distinct-error
contract. Windows CC's notebook 12 runner picked up the fix via a
`git merge origin/main` before the Phase 6.8a emit step (Step 0 of
`docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §8 prompt). This is
an intentional Path B (PR-before-emit) over Path A (emit-then-PR):
the 14,202-failure triage *is* the thing this PR was meant to make
diagnosable, so running the cohort with the old misleading-error
contract would have wasted the diagnostic opportunity.

**PR / tag:** merged via PR #64 (squash, `00ab3b7`); tagged
`v6.8a.1-distinct-prereq-errors` on the squash-merge commit
(`a1844b1`). Feature branch preserved on origin.

**Cohort first emit (2026-04-21, PS46–PS55):** Windows Claude Code ran
notebook 12 under `OVERWRITE="force"` on `feat/phase-6-8a-first-emit-
runner` after merging `origin/main` (picking up the v6.8a.1 distinct-
error fix before the emit). Results:

- **Emit totals:** 13,821 NPZs written across 256 distinct (animal,
  date) pairs (PS46: 21, PS47: 21, PS48: 20, PS49: 22, PS50: 19,
  PS51: 51, PS54: 52, PS55: 50). `n_err = 7,509` during emit — these
  are the distinct-FileNotFoundError-caught prerequisite misses the
  v6.8a.1 contract was designed to surface (per-category breakdown —
  centered-parquet vs. licks-NPZ vs. alignment-template vs. empty-
  DLC-files — to be extracted from the emit log in a follow-up).
- **Per-NPZ health check:** 13,821 / 13,821 pass — every emitted NPZ
  carries a valid side-convention stamp matching `configs/animals.yaml`.
- **Per-bundle health check:** 4,605 / 4,608 bundle-level checks pass
  (99.93%). Three failures, all benign-confirmed: PS51/20250430/tongue
  × {eye_midpoint, nose, spout_midpoint} × `−100to1000ms` window,
  each missing the R `trial_group` NPZ. Sibling `−500to5000ms` R
  bundles for the same session pass, so R-rewards exist on that
  session — the tight `−100to1000ms` window simply has zero
  qualifying tongue frames (DLC likelihood below threshold on every
  R-trial inside that ±post-reward span). `build_histogram` returns
  None, notebook 12's save loop falls through the guard at
  `notebooks/12_dlc_spatial_reward_aligned.ipynb:166` (`if result is
  None or result["histogram"] is None`), no NPZ is written. Data
  condition, not a code bug.
- **Notebook-log-diagnostic gap surfaced by the 3 PS51 failures:**
  notebook 12's save-loop guard conflates two legitimate "skip this
  bundle" conditions — `result is None` (zero rewards for trial_group)
  vs. `result["histogram"] is None` (zero qualifying frames after
  likelihood filtering). Both collapse into a single `n_err++;
  continue` with no emit-log distinction. Splitting into two counters
  + a per-condition warning lands as its own follow-up PR
  (target tag `v6.8a.3-notebook-12-skip-diagnostic`) after the
  v6.8a.2 runner-branch PR merges.
- **Task-runner exit-code masking gap surfaced during the gate
  review:** the Windows CC task-notification "exit 0" was misleading
  — the health-report script actually exited non-zero (conda surfaced
  `execute(125)`), but the wrapper's `| tail -80` pipeline absorbed
  the non-zero status. Fix: `set -o pipefail` in the task wrapper
  (or PIPESTATUS-based capture before tailing). Rolls into the same
  v6.8a.3 follow-up.

**PR / tag:** merged via PR #64 (squash, `00ab3b7`); tagged
`v6.8a.1-distinct-prereq-errors` on the squash-merge commit
(`a1844b1`). Feature branch preserved on origin.

---

## Phase 6.8a.3 — Notebook 12 save-loop skip-diagnostic split + task-runner pipefail

**Date:** 2026-04-22.

**Context:** The 2026-04-21 Phase 6.8a cohort first emit surfaced two
diagnostic gaps that were out of scope for v6.8a.1 (distinct-prereq-
errors) and v6.8a.2 (unattended runners), and were carved out as their
own small follow-up:

1. **Notebook 12's save-loop guard conflated two legitimately-empty
   skip conditions into a single `n_err` bucket.** After v6.8a.1
   converted three of the four `build_reward_aligned_analysis`
   prerequisite-miss paths to distinct `FileNotFoundError`s, two
   `return None` paths remained: (a) zero rewards for the requested
   `trial_group` (valid-but-empty data), and (b) `build_histogram`
   returning `None` because no DLC frames in the requested window
   survived the likelihood threshold. The notebook's save loop
   collapsed both into one `n_err++; continue` with no way to tell
   them apart from the emit log. This was the specific condition that
   made the 3 PS51/20250430 tongue R-side bundle failures hard to
   triage — the notebook said "3 errors" when the actual condition
   was "zero qualifying frames, no-op skip."
2. **Task-runner `| tail -80` pipeline masked non-zero exit codes.**
   The Windows ad-hoc task-runner wrapper piped
   `phase_6_8a_first_run_health_report.py`'s stdout through
   `tail -80` to cap the notification payload. Without `set -o
   pipefail`, bash reports the LAST pipeline stage's exit — and
   `tail` almost always returns 0 — so non-zero health-report exits
   (including conda's `execute(125)`) silently surfaced as "task
   completed successfully."

**Root cause:**

1. `notebooks/12_dlc_spatial_reward_aligned.ipynb` reward-loop cell
   (around line 166 of the cell source) had:

   ```python
   if result is None or result["histogram"] is None:
       n_err += 1
       continue
   ```

   The two conditions are semantically distinct:
   - `result is None` — `build_reward_aligned_analysis` returned
     `None`, the post-v6.8a.1 meaning of which is exactly "zero
     rewards for this trial_group" (all other prerequisite-miss paths
     raise).
   - `result["histogram"] is None` — `build_histogram` inside
     `build_reward_aligned_analysis` returned `None` because the
     likelihood-filtered frame count inside the reward-aligned window
     was zero.

   Both are valid-but-empty data conditions, neither is an error, and
   both should be observable in the emit log without re-reading the
   code.

2. `scripts/run_notebook_12_first_emit.py` mirrored the same save
   loop with the same collapsed guard.

3. The task-runner wrapper was not committed to the repo — it lived
   ad-hoc on the Windows machine. Without `set -o pipefail`, any
   pipeline step that tee'd / tailed / grep'd the health-report's
   output absorbed its exit status.

**What was done:**

1. **Notebook 12 save-loop split.** The guard in the reward-loop cell
   now reads:

   ```python
   if result is None:
       # zero rewards for this trial_group — legitimately-empty data,
       # not an error
       logging.info(f"skip_no_rewards {animal}/{date}/{bodypart}/"
                    f"{center_mode}/{trial_group}/{window_tag}")
       n_skip_no_rewards += 1
       continue
   if result["histogram"] is None:
       # zero qualifying DLC frames in the window (likelihood below
       # threshold on every candidate frame)
       logging.info(f"skip_no_frames {animal}/{date}/{bodypart}/"
                    f"{center_mode}/{trial_group}/{window_tag}")
       n_skip_no_frames += 1
       continue
   ```

   Counter initialization at the top of the `trial_group` loop gained
   `n_skip_no_rewards` and `n_skip_no_frames`. The per-(bodypart,
   center_mode, trial_group, window) summary `print` now surfaces all
   five counters:

   ```
   {tag}: ok=… skip=… skip_no_rewards=… skip_no_frames=… err=…
   ```

2. **Runner-script mirror.** `scripts/run_notebook_12_first_emit.py`
   picked up the identical split (same counter names, same log lines,
   same summary format). The health-report script
   (`scripts/phase_6_8a_first_run_health_report.py`) walks the on-
   disk NPZ tree directly — it does not parse the runner's stdout —
   so there was no parser contract to preserve.

3. **Committed task-runner wrapper.** Added
   `scripts/task_runner_wrapper.sh` as the canonical reference
   wrapper for the Phase 6.8a runner + health-report chain, with
   `set -euo pipefail` at the top and a docstring explaining the
   2026-04-21 exit-code masking context. Future Windows Task
   Scheduler / ad-hoc invocations should source this wrapper (or
   copy its `set -o pipefail` prologue into their own scripts) to
   avoid the same masking bug.

4. **Runbook §8.4 refresh.** `docs/runbooks/reemit-phase-5-6-after-
   lr-fix.md` §8.4 previously read "counts four distinct failure
   modes into one `n_err` bucket. Only the first mode emits a log
   warning; the other three `return None` silently…" — which was
   doubly stale (three of four became `FileNotFoundError` in
   v6.8a.1, and the remaining two got split counters in v6.8a.3).
   Rewritten to describe the current 6-bucket layout (3 distinct
   `FileNotFoundError` types + `n_skip_no_rewards` +
   `n_skip_no_frames` + catch-all `Exception` → `n_err`) with an
   example of the new summary print output. The "a follow-up
   refactor will…" sentence at the bottom was removed (this PR is
   the refactor).

5. **Unit tests.** New `tests/test_notebook_runners.py` (+189 lines,
   3 new tests) exercises the runner-script save loop with mocked
   `build_reward_aligned_analysis` returning each of the three
   outcomes (`None`, `{"histogram": None}`, `{"histogram": …valid…}`)
   and asserts the right counter increments + the matching log
   lines, without touching disk.

**What stayed the same:**

- No NPZ output shape or content changed — the split is pure
  diagnostic refactoring at the caller. The same bundles that got
  an emit before get an emit now; the same bundles that were
  silently skipped before are still silently skipped (they just
  now carry distinct counter + log evidence of *why*).
- The health-report script contract is unchanged (on-disk NPZ
  walk, no stdout coupling to the runner).
- Tag on merge follows the v6.8a.1 / v6.8a.2 pattern —
  `v6.8a.3-notebook-12-skip-diagnostic` on the PR #68 merge commit.

**Intentional behavior differences vs. legacy notebooks:** None.
There is no legacy equivalent of the `trial_group` save loop; the
counter split is a repo-level diagnostic improvement.

**Scope surprises (noted in the Windows CC report):**

1. **Task-runner wrapper did not exist on disk as a committed file.**
   The 2026-04-21 cohort-emit wrapper that surfaced the exit-code
   masking was ad-hoc / interactive — nothing under `~/`,
   `Documents/`, or anywhere under `/c/Users/sabatini/` matched the
   health-report script invocation in any `.sh` / `.bat` / `.ps1`.
   Windows CC wrote `scripts/task_runner_wrapper.sh` from scratch
   as the canonical committed reference with the pipefail fix baked
   in, so the bug context lives in the repo going forward. Any
   existing Windows Task Scheduler or ad-hoc invocation must still
   apply `set -o pipefail` manually (or source the wrapper).
2. **Health-report script needed no parser extension.**
   `phase_6_8a_first_run_health_report.py` reads the on-disk NPZ
   tree, not the runner's stdout or counts, so the runner counter-
   name change has no effect on the health-report contract.
3. **Notebook diff larger than expected (tooling artefact, not
   behavior).** The `NotebookEdit` tool re-serialized the reward-
   loop cell's `source` from a line-array to a single JSON string
   and normalized escaped `\u2014` → literal `—` across several
   other cells. Semantically identical JSON; pytest + PS51 emit
   verification confirm behavior is correct. Flagged in the PR
   body.

**Verification:**

- **Full pytest (post-change):** 464 passed / 34 skipped / 0 failed
  (+3 new tests in `test_notebook_runners.py` vs. the post-v6.8a.2
  baseline). `ruff check` clean on touched files.
- **PS51/20250430 reproducer (the known benign-skip case from the
  2026-04-21 cohort first emit):** ran the runner under
  `--animals PS51 --dates 20250430 --bodyparts tongue --center-modes
  eye_midpoint --trial-groups R --reward-windows-ms=-100,1000
  --overwrite skip --verbose`. Emit log:

  ```
  INFO: skip_no_frames PS51/20250430/tongue/eye_midpoint/R/-100to1000ms
    tongue/eye_midpoint/trials-R/-100to1000ms: ok=0 skip=0 skip_no_rewards=0 skip_no_frames=1 err=0
  Totals: ok=0 skip=0 skip_no_rewards=0 skip_no_frames=1 err=0
  ```

  Exactly as predicted — the single bundle that `build_histogram`
  couldn't fill is now surfaced as `skip_no_frames=1`, not as a
  fake `err=1`.
- **Branch-setup verification.** Tag `v6.8a.2-unattended-runners`
  peeled to `1f1b202`; base `HEAD` at branch-cut was
  `ca01c052`; commits between tag and branch-cut were 2 (both
  docs-only: `ca01c05` session-state refresh + `201923e` cohort-
  first-emit results). No code drift between the tag and the
  branch base.

**PR / tag:** merged via PR #68
(https://github.com/priya-srikanth/stroke_orofacial_pipeline/pull/68)
as merge commit `5b20dd5` (feature-branch commit `19c3664`);
tagged `v6.8a.3-notebook-12-skip-diagnostic` on the merge commit
(`5b20dd5`) and pushed to origin. Feature branch
`fix/notebook-12-skip-diagnostic-and-pipefail` preserved on origin.

**Forward follow-ups:** None. The diagnostic-gap carve-out from the
2026-04-21 cohort first emit is now fully discharged — every path
through the notebook 12 / runner save loop carries a distinct
counter + log line, and the task-runner wrapper's exit-code
contract is canonical in the repo. The next cohort emit run
(whenever Phase 5/6 requires it) will be readable in the emit log
without re-reading the code.

---

## 2026-04-20 — Task #18 — AnimalInfo cohort metadata (sex, date_of_birth, genotype, stroke_laser_power_mW) *(retroactive entry added 2026-04-22)*

**Scope.** Implementation of the Audit-10 Q7 decision from
2026-04-19: add cohort metadata fields to the `AnimalInfo`
schema and populate them for every animal in
`configs/animals.yaml`. Originally scoped as "sex + date_of_birth";
expanded at implementation to include `genotype` and
`stroke_laser_power_mW` at the same moment, since both were
already in Priya's direct cohort records and both are the same
kind of never-changing cohort-level property any downstream
covariate analysis will want.

**Why this is a retroactive entry.** The work landed
2026-04-20 but the `MIGRATION_LOG.md` entry was missed at the
time. Caught during the 2026-04-22 state-doc bookkeeping pass,
which also noticed that `docs/COWORK_SESSION_STATE.md` still
listed task #18 as unstarted in its Pending queue and
Next-phase candidates list. The three-way docs fix (this
entry + DECISIONS.md Q7 closure stamp + state-doc sync) lands
together on the 2026-04-22 docs-only PR
`docs/workflow-refresh-plus-task-18-closure`.

**Source data.** Priya's direct cohort records. Not derived
from any instrument output; not available in the legacy
notebooks' `ANIMALS` dict (which carried only `stroke_date`,
session range, exclusions, and analysis thresholds).

**Schema change.** `src/stroke_orofacial/animals.py`
`AnimalInfo` dataclass gained four optional fields (order as
declared):

- `sex: Literal["M", "F"] | None = None`
- `date_of_birth: datetime.date | None = None`
- `genotype: str | None = None`
- `stroke_laser_power_mW: float | None = None`

All four default to `None` for backward compatibility with any
callsite that constructs `AnimalInfo` without cohort metadata
(notably the `from_dict` / YAML loader path itself when a
partial animal entry is supplied, and any test fixture that
predates this change).

**Loader change.** The YAML loader at lines 243–276 of
`src/stroke_orofacial/animals.py` gained per-field parsing +
validation:

- `sex` parsed as string, validated against `{"M", "F"}` with a
  raise-on-invalid path (prevents silent typos like `"male"` or
  `"f"` from being accepted).
- `date_of_birth` parsed via the same `_parse_date` helper
  already used for `stroke_date` (accepts `YYYY-MM-DD` or
  `YYYYMMDD` string, or a `datetime.date` object if PyYAML has
  already parsed it natively).
- `genotype` parsed as free-form string (no enum — the cohort
  has two values: `"C57BL/6J"` and `"C57BL/6J (negative
  littermate)"` — the latter annotating a breeding-scheme
  negative result rather than a base-strain difference; see
  `configs/animals.yaml` header).
- `stroke_laser_power_mW` parsed as float.

A missing key parses to `None` rather than raising — a
pragmatic choice so partial test fixtures don't break, and so
the `wavesurfer_sides_match_mouse_sides` task #17 migration
didn't have to simultaneously retrofit every animal's
cohort-metadata fields on day one. All 8 PS46–PS55 cohort
animals are populated with all four fields as of 2026-04-20.

**New helpers.** `AnimalInfo.age_at_date(session_date)` (method,
lines 170–179) returns an `int | None` — the number of days
between `date_of_birth` and the given `session_date`; `None` if
`date_of_birth` is unset. `AnimalInfo.age_at_stroke()` (method,
lines 181–186) is a thin wrapper that calls `age_at_date` with
`self.stroke_date`. The two-method split lets future covariate
analyses compute per-session age (not just age-at-stroke) from
the same code path.

**Config population.** `configs/animals.yaml` updated with all
four fields on all 8 PS46–PS55 animals (PS46, PS47, PS48, PS49,
PS50, PS51, PS54, PS55). Per-animal values (from Priya's
records):

| Animal | Sex | DOB          | Genotype                             | Laser power (mW) |
|--------|-----|--------------|--------------------------------------|------------------|
| PS46   | F   | 2024-12-03   | C57BL/6J                             | 2.2              |
| PS47   | F   | 2024-12-03   | C57BL/6J                             | 2.2              |
| PS48   | F   | 2024-12-03   | C57BL/6J                             | 2.2              |
| PS49   | F   | 2024-12-12   | C57BL/6J (negative littermate)       | 2.5              |
| PS50   | F   | 2024-12-12   | C57BL/6J (negative littermate)       | 2.5              |
| PS51   | M   | 2025-01-23   | C57BL/6J                             | 3.0              |
| PS54   | M   | 2025-01-23   | C57BL/6J                             | 3.0              |
| PS55   | M   | 2025-01-23   | C57BL/6J                             | 5.0              |

Cohort ages at stroke range **95–101 days** (~14 weeks —
standard adult-mouse age). Documented in the
`configs/animals.yaml` header comment so future readers
don't have to re-derive. The two "negative littermate"
annotations (PS49, PS50) refer to a breeding-scheme negative
result — both animals are on the C57BL/6J base line and
both received stroke induction; the note is preserved as
provenance, not as a biological-difference flag.

**Downstream reach.** No downstream callers required
modification — `AnimalInfo` consumers either already accept
`None` for unknown fields (every construction path pre-dates
cohort-metadata) or simply don't access the new fields yet.
Phase 9a/9.1/9b stats work (still unshipped as of this entry)
will pick them up directly from the loader.

**Ground-rule compliance.**

- `CLAUDE.md` rule 1 — **no source data modified.** The
  per-animal YAML entries are configuration, not source data
  in the CLAUDE.md sense (which names raw wavesurfer `.h5`,
  raw Flea3 AVI + timestamp CSV, DLC inference output, DLC
  training project, alignment templates, and existing
  processed behavior outputs).
- `CLAUDE.md` rule 8 — work landed as a feature branch, not
  direct-to-main.

**Tests.** `tests/test_animals.py` gained coverage for:

- Loading an animal with all four cohort-metadata fields
  present — verifies correct parsing + correct types.
- Loading an animal with all four fields absent — verifies
  `None` defaults (backward-compat for partial test fixtures).
- Invalid `sex` value raises (not silently accepted).
- `age_at_stroke()` returns an `int` when both DOB and
  stroke_date are present, and `None` when either is missing.
- `age_at_date(session_date)` correctness for a couple of
  reference dates on a known DOB.

**Verification.** Full pytest suite green on both Mac and
Windows after the change (count per the then-current session
baseline); ruff clean on touched files.

**Forward follow-ups.**

- Phase 9a/9.1/9b — cohort-metadata fields are now available
  as stats covariates. No retrofit to existing 9a test-bench
  work; new endpoints pick them up.
- No additional `animals.yaml` population work pending — the
  PS46–PS55 cohort is fully populated.
- If the cohort ever expands beyond PS46–PS55, the schema
  supports the additional animals by construction; no further
  migration required.

---

## Phase 7-pre — `AnimalInfo.exclusions.applies_to` schema extension

**Date:** 2026-04-22. Companion to the Phase 7a interpolation design
brief (`docs/phase-7/interpolation-strategy.md` §3.2), which flagged
the namespace-collision risk of mixing bodypart strings (`tongue`)
with phase tags (`dlc`, `spout_behavior`) in a flat `applies_to`
list. Ships before 7a-impl to unblock the PS51 2025-05-17 DLC-only
exclusion that 7a parity needs.

**What changed.**

`Exclusion.applies(analysis_context)` now uses **dotted hierarchical
prefix-match** semantics:

- An exclusion with `applies_to: [dlc]` matches any
  `analysis_context` starting with `"dlc"` or `"dlc.*"` (e.g.,
  `"dlc.spatial"`, `"dlc.kinematics.tongue"`).
- `applies_to: [dlc.kinematics.tongue]` matches only
  `"dlc.kinematics.tongue"` — not `"dlc.kinematics.jaw"` (sibling)
  or `"dlc.kinematics"` (tag is longer than context).
- Segment boundary is strict: `[dlc]` matches `dlc` and `dlc.*`
  but NOT `dlc_spatial` (underscore) or `dlcx` (no boundary).
- `analysis_context=None` never matches (callers must pass an
  explicit context).

`AnimalInfo.is_excluded(session_date, analysis_context)` parameter
renamed from `analysis_type`. `build_manifest()` likewise renamed;
threaded through all four existing convenience-wrapper call sites:

- `spout_behavior.session_processing.process_session_by_animal_date` →
  `analysis_context="spout_behavior"`
- `alignment.timebase.load_or_compute_alignment_by_animal_date` →
  `analysis_context="alignment"`
- `dlc_io.parquet.build_centered_parquet_by_animal_date` →
  `analysis_context="dlc.io"`
- `dlc_spatial.reward_aligned.build_reward_aligned_analysis_by_animal_date` →
  `analysis_context="dlc.spatial"`

**Canonical `analysis_context` taxonomy:**
```
spout_behavior       # Phase 2
alignment            # Phase 3 (wavesurfer↔camera index mapping)
dlc.io               # Phase 4 (centered parquet)
dlc.spatial          # Phase 5/6
dlc.kinematics.{tongue,jaw,whisker,face_velocity,psd}   # Phase 7
```

**YAML loader validation.** The legacy `applies_to: [all]` sentinel
is **rejected at load time** with a migration-guidance error message.
`applies_to` is now required (no default) and must be a non-empty
list of strings. Scalar strings (`applies_to: "dlc"`) are normalized
to single-element lists for YAML ergonomics.

**Config migration — `configs/animals.yaml`.** All four pre-existing
exclusions migrated from `[all]` to explicit top-level tags. One new
exclusion added per the 7a brief's audit:

| Animal | Date | Before | After | Reason |
|---|---|---|---|---|
| PS51 | 2025-04-26 | `[all]` | `[dlc, spout_behavior]` | Rose Bengal sham, delayed licking |
| PS51 | **2025-05-17** | *(new)* | `[dlc, alignment]` | Missing camera data |
| PS54 | 2025-04-26 | `[all]` | `[dlc, spout_behavior]` | Rose Bengal sham, delayed licking |
| PS55 | 2025-04-27 | `[all]` | `[dlc, spout_behavior]` | Rose Bengal sham, delayed licking |
| PS55 | 2025-04-28 | `[all]` | `[dlc, spout_behavior]` | Experimenter error, inaccurate reward delivery |

PS51 2025-05-17 is scoped to `[dlc, alignment]` rather than
`[dlc]` alone because the wavesurfer↔camera alignment template
builder also requires camera timestamp CSVs; a session with no
camera data breaks both DLC and alignment even though
spout-behavior-only analyses still work off the wavesurfer file.

**Intentional behavior differences vs legacy.**

1. **`analysis_context=None` no longer matches `[all]` exclusions.**
   Previously `is_excluded(date, None)` returned `True` for any
   `[all]`-scoped exclusion because the legacy wildcard path took
   the short-circuit before checking `analysis_type`. After 7-pre
   there is no `[all]` sentinel — callers must pass an explicit
   context to trigger exclusion checks. In practice this didn't
   fire anywhere: all four pre-7-pre `build_manifest()` call sites
   dropped the parameter, so `excluded` was always `False` on the
   emitted manifests regardless. Threading `analysis_context`
   through all four call sites activates the previously-dormant
   exclusion path.
2. **Rose Bengal sham exclusions no longer block `alignment`.** Under
   `[all]`, all four pre-existing exclusions would have fired for
   any caller that actually passed a context. Under
   `[dlc, spout_behavior]` those exclusions no longer apply to
   `analysis_context="alignment"`. Rationale: the alignment
   template itself (wavesurfer↔camera index map) is a mechanical
   product of the acquired timestamps; the mouse's behavior-quality
   issues don't corrupt the mapping. Downstream DLC/spout analyses
   that consume the template are the ones that legitimately need
   to skip these sessions.

**Namespace-collision resolution.** The brief flagged three candidate
schemas (rename+split, nested struct, namespaced tags). Phase 7-pre
picked **namespaced tags** (Option 3) because it scales cleanly to
future dimensions (e.g., a `trial_group.*` axis) without a schema
migration, and avoids the empty-list ambiguity of AND-combined
phase/bodypart lists.

**Tests.**

- `tests/test_animals.py` — `TestExclusionApplies` (7 tests:
  exact, one-level prefix, multi-level prefix, sibling-no-match,
  segment-boundary-strict, None-context, multiple-tags-any-match);
  `TestExclusionLoaderValidation` (5 tests: `[all]` rejected,
  missing `applies_to` rejected, empty list rejected, non-list
  rejected, string normalized). Renamed
  `TestAnimalInfoMethods.test_is_excluded_universal` →
  `test_is_excluded_top_level_scope` and
  `test_is_excluded_analysis_specific` →
  `test_is_excluded_bodypart_specific` with updated assertions.
- `tests/test_manifest.py` — renamed `test_excluded_session` →
  `test_excluded_session_top_level_scope` and updated
  `test_analysis_specific_exclusion` with dotted-tag scopes.

Full suite: 482 passed, 34 skipped, 0 failed. Ruff clean.

**Ground-rule compliance.**

- `CLAUDE.md` rule 1 — no source data modified. Only code +
  configs + docs.
- `CLAUDE.md` rule 8 — feature branch `phase-7-pre-exclusions-schema`
  off main; merge commit preserved.

**Forward follow-ups.** None. 7a-impl now consumes the new schema
directly (its per-animal kinematics baselines live alongside
exclusions in `animals.yaml`).

---

## Phase 7a design brief — interpolation-strategy lock-in (docs-only)

**Date:** 2026-04-22. PR #74 merge commit, tagged `v7a-design-brief`.
No source / configs / notebooks / outputs changed — docs-only.

**What this entry is.** A trace-line pointing at the canonical
design document for Phase 7a. Phase 7 implementation PRs will
cite the brief and its §10 resolution list.

**What landed.** `docs/phase-7/interpolation-strategy.md` — a
design brief for the v5p3 interpolation pipeline that produces
continuous tongue/jaw traces from DLC outputs (the first in-scope
piece of Phase 7 DLC kinematics). Specifies:

- §1 — port scope: the 7-stage v5p3 algorithm
  (`xrange → thr → drop → interp → interp_filled → final`) from
  tongue notebook Cell 23 + jaw notebook Cell 22.
- §2 — 8 knob decisions, including:
  - **Knob 1** split emit: canonical parquet + optional QC NPZ.
  - **Knob 3** percentile semantics: `Y0` = lowest n'th
    percentile of the trial-aligned pool; `X0` = median of `X`
    within the `Y`-percentile subset.
  - **Knob 5** output shape: Option A — pure-bodypart parquet
    (no trial-grouped variants at this layer).
- §3.1 — per-animal per-bodypart baselines in
  `configs/animals.yaml`. **Faithful port** of Priya's manual
  per-run X0/Y0 editing against the legacy notebook; legacy
  MICROSCOPE outputs are correct under this manual protocol.
  Seed from `X0`/`Y0` keys in the legacy NPZs.
- §3.2 — exclusion-scoping namespace-collision risk; escalated
  to the Phase 7-pre schema extension above (new
  `analysis_context` taxonomy + dotted-hierarchical prefix-match).
- §5 — pure-bodypart parquet schema.
- §6 — **parity-session set**: 9 primary + 3 low-licking
  stress-test + 2 late-post-stroke = 14 sessions required before
  any 7a implementation PR opens. See the 2026-04-22 DECISIONS
  "Parity-gate principle" entry for the policy this enforces.
- §10 — **canonical resolution list** for all 8 knobs (kept
  separate from the earlier narrative-flow "Open Questions"
  section, which §10 supersedes).

**How the brief was produced.** CC drafted; Cowork reviewed in
two passes — 11 edits round 1 addressing baseline-framing +
namespace collision + output path; 5 more edits round 2 cleaning
up stale references after the Knob 3 rewrite. Priya signed off
on the §10 resolutions before the brief merged.

**PRs in the 2026-04-22 close-out sequence** (context for future
readers reconstructing the commit graph):
- PR #73 — Phase 8a.8 recovery-trajectory visualization helpers
  (tag `v8a.8-spout-recovery-trajectories`).
- PR #74 — this brief (tag `v7a-design-brief`).
- PR #75 — Phase 7-pre exclusions schema extension (tag
  `v7-pre-exclusions-schema`). See the "Phase 7-pre" entry above
  for that work.

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified. CLAUDE.md rule 8 — merged on feature branch, tag
pushed. Docs-only; no parity needed.

**Forward follow-ups.** Phase 7a implementation (next phase) must:

1. Honor every §10 resolution.
2. Seed `configs/animals.yaml` per-animal per-bodypart baselines
   from legacy NPZ `X0`/`Y0` keys on MICROSCOPE.
3. Produce a per-stage drift table in its own MIGRATION_LOG entry
   per the 2026-04-22 parity-gate principle decision.

---

## Phase 7a.0 — Legacy-cell vendoring + baseline-seed probe + scipy pilot

**Date:** 2026-04-22. PR #79 merged (landed on `main`). **Intentionally
untagged** — 7a.0 is a probe/scaffold phase inside the 7a design-brief →
7a implementation boundary; per the Cowork paste-in amendment that
drove Task 1–3, phase-close tagging resumes at 7a.1. No source data
modified; no pipeline code paths changed. Every deliverable lives
under `docs/` or `tests/scripts/` and is consumed by 7a.1 / 7a.2
rather than by the runtime pipeline.

**What this entry is.** A retrospective trace-line covering the PR #79
scope — the Cowork-drafted / CC-executed three-task amendment
(scipy pilot, seed-table scope filter, DECISIONS entry) layered on
the original legacy-probe kickoff (legacy-cell disambiguation and
vendoring + unfiltered baseline-seed probe). PR #79 is the combined
merge; this entry documents it as a single close.

**What landed.**

1. **Legacy-cell vendoring.** Canonical notebooks identified per
   CLAUDE.md §"Legacy code version disambiguation" 3-tier rule:
   - Tongue: `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
     (Priya-named canonical, mtime 2026-04-20). Other tongue
     notebooks are SIBLINGS with distinct scope markers
     (`build-parquet`, `reward-aligned`), not dated-supersession
     candidates.
   - Jaw: `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
     (Priya-named canonical, mtime 2026-04-17). The 2025-11-17
     `DLC_analysis_jaw.ipynb` is superseded (older mtime + narrower
     scope). The `reward-aligned` sibling has distinct scope.
   - Vendored cells (byte-identical captures with SHA256 provenance
     headers) at `docs/legacy_snippets/`:
     - `tongue_cell23_interp_v5p3.py` — Cell[23], 763 lines, SHA256
       `41f54f0d04371622e3838f93785e8c051d506109cf448215b7ffdc203f9067b3`.
     - `jaw_cell22_interp_v5p3.py` — Cell[22], 755 lines, SHA256
       `a9277879546b901bbe7860c4a21df7091abc4d34bae1fe6450290f2c10fcf438`.

2. **Baseline-seed probe.** NPZ enumeration under
   `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\`
   for all 8 animals (PS46, PS47, PS48, PS49, PS50, PS51, PS54,
   PS55 — PS52 and PS53 never existed in this project) × 2
   bodyparts (tongue, jaw) = 16 combos. Unfiltered probe across
   every NPZ on disk yielded **14 STABLE / 2 NEEDS_HUMAN_DECISION /
   0 INSUFFICIENT**. The two NHD combos were PS49 tongue and PS50
   tongue, both showing a Y0 spread of -110 / -100 across their
   on-disk NPZ sets.

3. **Scope-filtered re-analysis** (added by the Cowork amendment,
   Task 2). Restricted the probe to the in-scope session range per
   animal as defined by `configs/animals.yaml sessions.{start, end}`.
   The PS49 and PS50 tongue Y0 spreads collapsed under the filter:
   - PS49 tongue: 3 out-of-scope NPZs excluded (20250307, 20250308,
     20250309 — all Y0=-100, pre-scope); 22 in-scope sessions all
     at Y0=-110.
   - PS50 tongue: 10 out-of-scope NPZs excluded (20250307 through
     20250317 excluding 20250314 — all Y0=-100, pre-scope); 19
     in-scope sessions all at Y0=-110.
   - Verified the no-scope-change invariant on every STABLE combo:
     no STABLE combo's scope-filtered X0/Y0 differs from its
     unfiltered median. The scope filter resolves the two NHD
     combos without perturbing any previously-STABLE combo.
   - **Revised verdict roll-up: 16 STABLE / 0 NEEDS_HUMAN_DECISION /
     0 INSUFFICIENT.** Authoritative seed values for
     `configs/animals.yaml kinematics_baselines:` (consumed by
     Phase 7a.1 Task 1):

     | Animal | tongue.y0 | tongue.x0 | jaw.y0 | jaw.x0 |
     |---|---|---|---|---|
     | PS46 | -110.0 | 0.0 | 310.0 | 0.0 |
     | PS47 | -110.0 | 0.0 | 310.0 | 0.0 |
     | PS48 | -110.0 | 0.0 | 310.0 | 0.0 |
     | PS49 | -110.0 | 0.0 | 310.0 | 0.0 |
     | PS50 | -110.0 | 0.0 | 310.0 | 0.0 |
     | PS51 | -110.0 | 0.0 | 290.0 | 12.0 |
     | PS54 | -110.0 | 0.0 | 290.0 | 12.0 |
     | PS55 | -110.0 | 0.0 | 290.0 | 0.0 |

4. **scipy-version pilot** (Cowork amendment, Task 1). Reproduced
   the legacy v5p3 PCHIP call under both scipy 1.15.1 (legacy-era,
   from Priya's local `deeplabcut` conda env) and scipy 1.17.1
   (consolidated `stroke_orofacial` env) on PS46/20250307 tongue
   (STABLE, in-scope, 931,834 frames). **Bit-for-bit identical** on
   all 914,012 common non-NaN frames (x and y both `max|Δ| = 0.0`);
   NaN boundaries agree exactly (17,822 leading/trailing positions
   each). **Verdict: Option A — no scipy pin, no tolerance widening.**
   Phase 7a.1 parity will run under the consolidated env's scipy
   1.17.1 with `atol=1e-6` per `interpolation-strategy.md` §6
   default tolerance. Caveat: single-session pilot isolating stage
   4 (`interp`) only; a second-session stress pilot (PS51/20250430,
   high-NaN session per §6) is deferred to Phase 7a.1 per the
   2026-04-22 DECISIONS entry.

5. **DECISIONS grouped entry** (Cowork amendment, Task 3).
   2026-04-22 entry logged two decisions:
   - **Parity-scope principle** — parity comparisons for Phase 7a
     (and all future DLC-kinematics phases) are restricted to the
     in-scope session set defined by `configs/animals.yaml
     sessions.{start, end}`. Out-of-scope legacy NPZs are pre-
     narrowing pipeline artifacts and are not parity targets.
   - **scipy Option A** — no pin, `atol=1e-6` on PCHIP outputs
     under consolidated-env scipy 1.17.1. Stress pilot on
     PS51/20250430 deferred to 7a.1 before opening the 7a
     implementation PR.

**Artifacts landed in the repo.**
- `docs/legacy_snippets/tongue_cell23_interp_v5p3.py` (vendored).
- `docs/legacy_snippets/jaw_cell22_interp_v5p3.py` (vendored).
- `docs/phase-7/baseline-seed-table.md` — full 16-combo probe table,
  per-session appendix, scope-filtered re-analysis, seed values for
  7a.2.
- `docs/phase-7/scipy-pilot-results.md` — pilot methodology, diff
  summary, Option A recommendation, caveats.
- `tests/scripts/scipy_version_pilot.py` — pilot runner reused by
  7a.1 for the PS51/20250430 stress pilot.
- `docs/prompts/phase-7a.0-legacy-probe-kickoff.md` — the kickoff
  prompt Cowork drafted / CC executed (preserved for audit trail).

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified (MICROSCOPE NPZs read-only). Rule 2 — no legacy-repo
edits (canonical cells vendored as byte-identical captures with
SHA256 provenance). Rule 8 — merged on feature branch; **tag
intentionally omitted** per paste-in constraint, phase-close tagging
resumes at 7a.1.

**Forward follow-ups for Phase 7a.1** (docs/prompts/phase-7a.1-kickoff.md):

1. Seed `configs/animals.yaml kinematics_baselines:` from the 8-row
   seed table above; extend `AnimalInfo` with a
   `kinematics_baselines: dict[str, dict[str, float]]` field and a
   `get_kinematics_baseline(bodypart)` accessor.
2. Stand up the 14-session parity harness at
   `tests/scripts/parity_phase7a_interpolation.py` with the full
   scope-filter + legacy-NPZ loader + stubbed consolidated loader
   (implementation lands in 7a.2).
3. Run the PS51/20250430 scipy stress pilot; attach result to the
   2026-04-22 DECISIONS entry as a second-session confirmation of
   Option A, or flip to atol=1e-4 + drift-log if the stress session
   surfaces version-dependent divergence.

---

## Phase 7a.1 — `kinematics_baselines` seed + parity-harness scaffold + scipy stress pilot

**Date:** 2026-04-22
**PR:** #81 (merged 2026-04-22 as merge-commit `98e6ccd`)
**Tag on merge:** `v7a.1-kinematics-baselines-parity-scaffold`
**Branch:** `phase/7a.1-kinematics-baselines-parity-scaffold`

**Scope.** The three smallest unblocked pieces between the 7a.0 close
(PR #79) and the 7a.2 interpolation.py implementation, bundled into one
PR so that 7a.2 becomes the single focused PR that writes module code.
Per the 7a.1 kickoff (`docs/prompts/phase-7a.1-kickoff.md`, committed as
commit 1 of this branch), the three pieces are (A) `kinematics_baselines`
seed + loader, (B) parity-harness scaffold with stubbed consolidated
reader, (C) second-session scipy stress pilot confirming 7a.0 Option A.

**What landed.**

1. **`configs/animals.yaml` kinematics_baselines seed.** Added a
   `kinematics_baselines:` block to every animal (PS46–PS55, 8 animals)
   with `tongue.{x0, y0}` and `jaw.{x0, y0}`, seeded from the PR #79
   scope-filtered re-analysis (16 STABLE / 0 NHD / 0 INSUFFICIENT).
   - Tongue uniform across cohort at (x0=0.0, y0=-110.0).
   - Jaw splits into three groups: PS46–PS50 at (0, 310);
     PS51/PS54 at (12, 290); PS55 at (0, 290).
   - Per-animal block documented with a dedicated header comment
     block pointing at the seed-table and the loader/accessor in
     `src/stroke_orofacial/animals.py`.

2. **`AnimalInfo` loader extension.** Added
   `kinematics_baselines: dict[str, dict[str, float]]` field to the
   dataclass, a `get_kinematics_baseline(bodypart)` accessor, and a
   `_parse_kinematics_baselines()` strict validator in
   `load_animals()` that fails loud on: missing block, missing bodypart
   (tongue/jaw are both required), unknown bodypart keys (typo guard),
   missing `x0`/`y0` inside a bodypart, non-numeric values, or bools
   sneaking in as ints. Intentional: future animals must explicitly
   declare baselines so `interpolation.py` never silently runs with a
   cross-contaminated `(X0, Y0)` from another animal. The validator is
   invoked as the *last* kwarg of the `AnimalInfo()` constructor so
   exclusion-related validation errors (via `_parse_exclusions`) keep
   firing first, preserving existing test behavior without fixture
   changes to those failure-path tests.

3. **8 new tests in `TestKinematicsBaselines`.** Full-cohort
   parse, tongue-uniform invariant, jaw three-group invariant,
   missing-block / missing-bodypart / unknown-bodypart / missing-x0
   raises, KeyError on unknown-bodypart accessor. Existing
   "successful load" fixtures (`animals_yaml` shared fixture and the
   three standalone tmp_path yamls that load successfully) updated
   with `kinematics_baselines` blocks so they parse cleanly under the
   new strict loader.

4. **14-session parity harness scaffold.**
   `tests/scripts/parity_phase7a_interpolation.py` — scope filter
   against `animals.yaml sessions.{start, end}` per animal,
   legacy-NPZ loader for `x_final / y_final / X0 / Y0 / fps /
   n_frames` from MICROSCOPE, atol=1e-6 element-wise comparator per
   7a.0 Option A, scalar-metadata strict-equality check. Sessions =
   9 primary + 3 stress + 2 late-post-stroke per
   `interpolation-strategy.md` §6 (28 comparisons across both
   bodyparts). Consolidated-side `_load_consolidated_trace()` is a
   stub that raises `NotImplementedError` by design — 7a.2 replaces
   it with a real parquet read. Exit codes: 0 pass / 1 fail / 2 stub
   / 3 MICROSCOPE unreachable / 4 scope drop-all. Stub wins over
   skip_missing in the cascade so the 7a.1 smoke returns 2 even with
   real data gaps.

   Smoke outcomes: `--animal PS46 --date 20250307 --bodypart tongue`
   → exit 2 (1 stub); `--sessions auto` → exit 2,
   `by_status = {'stub': 26, 'skip_missing': 2}`. The 2 skip_missing
   are PS54/20250512 tongue + jaw — legacy NPZs genuinely absent on
   MICROSCOPE (real data gap, cohort-acquisition intermittency; same
   pattern appears for other PS51/54/55 days and is expected per
   Priya 2026-04-22 sign-off).

5. **Second-session scipy stress pilot — PS51/20250430 tongue.**
   Ran `tests/scripts/scipy_version_pilot.py` under both
   `sop_scipy_pilot` (scipy 1.15.1) and `stroke_orofacial` (scipy
   1.17.1) on a high-NaN-fraction session (99.88% NaN-in x/y vs.
   89.47% on pilot #1's PS46/20250307). Result: **max|Δ| = 0.0 on
   both x and y across 906,310 common non-NaN frames; NaN masks
   identical** (44,523 boundary NaNs per axis on both envs).
   Option A (no pin, no widening, `atol=1e-6` under consolidated
   scipy 1.17.1) validated on both a low-NaN baseline and a
   high-NaN stress session. DECISIONS 2026-04-22 "scipy version
   handling" caveat 1 (single-session pilot) resolved; new
   `Update 2026-04-22 (Phase 7a.1)` sub-bullet added under that
   caveat pointing at the new
   `docs/phase-7/scipy-pilot-results.md` §"Second-session stress
   pilot" section.

**Commits on this branch** (five, plus a sixth for this MIGRATION_LOG
entry):

1. `docs(prompts): Phase 7a.1 kickoff` — kickoff doc committed in-branch
   for provenance.
2. `feat(animals): kinematics_baselines schema + per-animal seed from
   PR #79 probe` — tasks 1a–1e.
3. `feat(tests/scripts): Phase 7a parity harness scaffold (stub until
   7a.2)` — task 2.
4. `docs(phase-7a.1): second-session scipy stress pilot confirms
   Option A` — task 3.
5. `docs(migration-log): Phase 7a.1 entry` — this task.

**Parity / tests / ruff.**

- Full pytest: 490 passed, 34 skipped (no regressions).
- `tests/test_animals.py`: 42 passed (34 existing + 8 new).
- Ruff: clean on all touched `.py` files (configs/animals.yaml
  excluded — ruff does not parse YAML).
- Parity harness smoke: single-session exit 2; `--sessions auto`
  exit 2.

**Behavior differences vs. legacy notebooks.** None. The
`kinematics_baselines` YAML values match the `X0`/`Y0` that legacy
NPZs were computed with under the in-scope session range — this is
the faithful-port path per `interpolation-strategy.md` §3.1
"faithful port, not a bug fix".

**Intentional convention.** `kinematics_baselines` is REQUIRED for
every animal at load time — no silent default. Rationale: future
animals joining the cohort must explicitly declare their baselines
so `interpolation.py` never silently runs with a cross-contaminated
baseline from another animal. The strict loader is the enforcement
mechanism.

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified (MICROSCOPE NPZs read-only via `np.load`). Rule 2 — no
legacy-repo edits. Rule 8 — feature branch; tag
`v7a.1-kinematics-baselines-parity-scaffold` to be applied by Priya
on the merge commit. Tests + ruff green.

**Prep-PR context.** Before this branch opened, a separate PR (#80
— `docs/pre-7a1-state-refresh`, merged 2026-04-22) landed two
end-of-day housekeeping docs that had accumulated unstaged on
`main`'s working tree after PR #79: the
`docs/COWORK_SESSION_STATE.md` refresh and the retrospective
`Phase 7a.0 — Legacy-cell vendoring + baseline-seed probe + scipy
pilot` MIGRATION_LOG entry (immediately above this one). PR #80 is
why Phase 7a.0 has a retrospective MIGRATION_LOG entry even though
7a.0's original PR #79 did not include one. No content overlap:
PR #80 covers 7a.0, this entry covers 7a.1.

**Forward follow-ups for Phase 7a.2.**

1. Port the 7-stage v5p3 interpolation algorithm (`xrange → thr →
   drop → interp → interp_filled → final`) from
   `docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py`
   into `src/stroke_orofacial/dlc_kinematics/interpolation.py`.
   Consume `AnimalInfo.get_kinematics_baseline(bodypart)` for the
   per-animal (x0, y0) baseline.
2. Replace `_load_consolidated_trace` stub in
   `tests/scripts/parity_phase7a_interpolation.py` with the real
   parquet reader; run the 14-session parity set under scipy 1.17.1
   with `atol=1e-6`; expected outcome per the two-session scipy
   pilots is bit-for-bit identity on non-NaN frames and identical
   NaN masks.
3. Add `dlc_kinematics:` block to `configs/defaults.yaml` for
   bodypart-parametric constants (likelihood thresholds,
   max-gap-ms, per-stage knobs per `interpolation-strategy.md` §7).
4. Decide how to handle the PS54/20250512-style MICROSCOPE gaps in
   the 14-session set: swap for a neighbor date (e.g. 20250511 or
   20250514), accept the 2/28 skip_missing as steady state, or add
   explicit `exclusions:` entries with a reason annotation. No
   action required in 7a.1 — the harness already tolerates these.

---

## Phase 7a.2 — `interpolation.py` v5p3 port + 14-session cohort parity

**Date:** 2026-04-24
**PR:** #<FILL> (landing 2026-04-24)
**Tag on merge:** `v7a.2-interpolation-impl`
**Branch:** `phase/7a.2-interpolation-impl`

**Scope.** The v5p3 7-stage interpolation pipeline ported from
`docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py` into
`src/stroke_orofacial/dlc_kinematics/interpolation.py`. Delivers the
single piece of code that blocked Phases 7b–7f: a bodypart-parametric
pure-function core wrapped by the session-level writer, emitting a
canonical 7-column parquet + optional 7-stage QC NPZ sidecar. Cohort-
wide parity run confirms **bit-for-bit identity** against legacy v5p3
NPZs on every reachable in-scope session at `atol=1e-6`.

**What landed.**

1. **`configs/defaults.yaml` `dlc_kinematics:` block.** Bodypart-
   parametric constants per `interpolation-strategy.md` §7 (tongue:
   x_range_pm=150, lk_thr=0.5, n_neigh=2, max_gap_ms=56; jaw: 75 / 0.5
   / 3 / 120). Top-level `interpolation_method=pchip` /
   `interpolation_fallback=linear` with a "DO NOT CHANGE without
   DECISIONS entry" header comment per Knob 2. Inserted between
   `dlc_spatial_reward_aligned:` and `wavesurfer:` so DLC analysis
   configs stay co-located.

2. **`PathResolver.interpolated_trace(bodypart, animal, date, *, variant)`
   helper.** Returns
   `<outputs>/dlc_analysis/interpolated_traces/<bodypart>/<animal>/
   <YYYYMMDD>.{parquet|qc.npz}`. Mirrors `pipeline_outputs()`'s
   `output_root` override for tests. 3 new unit tests.

3. **`src/stroke_orofacial/dlc_kinematics/interpolation.py`.** 887-line
   module:
   - `InterpolationResult` dataclass (32 fields — 7 stages × 2 dims +
     fill masks + fill_method int8 enum + X0/Y0 + X0_data/Y0_data +
     fps/n_frames + bodypart/animal/date + center_mode +
     baseline_stage + wavesurfer_sides_match_mouse_sides +
     reward_centers_cam).
   - Stage helpers transcribed byte-for-byte from the vendored cells:
     `_stage_xrange`, `_stage_thr`, `_stage_drop`,
     `_interp_small_gaps`, `_fill_nan_with`,
     `_build_reward_aligned_pool_mask`.
   - Baseline helpers: `_compute_baseline_forced` (reads
     `AnimalInfo.kinematics_baselines`); `_compute_baseline_data_driven`
     (simplified single-pool per strategy §7; DIVERGES from legacy
     separate-pool semantics — intentional, documented in the
     2026-04-24 DECISIONS entry).
   - Data loaders: `_load_centered_df` (Phase 4.5-lite centered
     parquet); `_load_reward_centers_cam` (Phase 2 licks NPZ + cam2
     alignment template, v6.8 mouse-frame).
   - Pure-function core: `_interpolate_bodypart_core` (no I/O).
   - Writers: `_write_parquet` (7 columns + 9 metadata keys per
     §2c locked schema, snappy compression); `_write_qc_npz`
     (intermediate arrays + X0_data/Y0_data diagnostic scalars).
   - Public API: `build_interpolated_trace(manifest, bodypart,
     resolver, params, *, overwrite, emit_qc_bundle, animal_info) ->
     Path | None`; `build_interpolated_trace_by_animal_date(animal,
     date, bodypart, resolver, **kwargs)` convenience wrapper.
   - Exclusion check via
     `AnimalInfo.is_excluded(date, analysis_context=f"dlc.kinematics.{bodypart}")`
     per Phase 7-pre prefix-match schema.

4. **14 §8 unit tests + 7 review-adjustment extras.**
   `tests/test_dlc_interpolation.py` — 7 new test *functions* beyond
   §8, but `test_stage_drop_isolated_hilk` is parametrized over 4
   neighbor counts so pytest counts 24 new test *runs*. All
   MICROSCOPE-free: synthetic arrays, synthetic centered parquets
   under `tmp_path`, synthetic Phase 2 licks NPZ with v6.8 stamp,
   synthetic alignment template.

5. **Parity harness wire-in.** `_load_consolidated_trace` stub in
   `tests/scripts/parity_phase7a_interpolation.py` replaced with the
   real parquet reader (reads x_final/y_final + 9 file-metadata keys
   including the v6.8 side-convention stamp pair).

6. **`scripts/phase_7a/emit_parity_sessions.py`.** Durable pre-emit
   helper (promoted from `scratch/phase-7a2-probe/` on 2026-04-24 per
   Priya's Task-5 directive) that drives
   `build_interpolated_trace_by_animal_date` across the 14 × 2 parity
   set before the harness runs. Needed because the harness only reads;
   it does not emit. Re-usable for any post-7a.2 kinematics-algorithm
   parity re-run under the 2026-04-22 parity-gate principle.

7. **DECISIONS entry 2026-04-24** codifying Knobs 1–4, §5 Option A,
   §3.1 baseline encoding, Task 2 fixup Items 1 + 4 (data-driven
   single-pool semantics; 9-key parquet metadata with X0_data/Y0_data
   routed to the QC NPZ sidecar).

8. **`interpolation-strategy.md` §2 amendment** — QC NPZ sidecar spec
   extended to include the diagnostic `X0_data`, `Y0_data` scalars per
   Task 2 fixup Item 4.

**Parity verification.**

Cohort-wide parity at `atol=1e-6` under consolidated-env scipy 1.17.1
(Option A per 2026-04-22 DECISIONS). Pre-flight exclusion sanity check:
0 collisions between the 14 × 2 parity entries and
`dlc` / `dlc.kinematics.{tongue,jaw}` exclusions in `animals.yaml`.

Per-session 14-session run (`by_status = {'pass': 26, 'skip_missing': 2}`,
exit 0):

| animal | date | bodypart | status | max\|Δ\|x | max\|Δ\|y | common | nan_L | nan_C |
|---|---|---|---|---|---|---|---|---|
| PS46 | 2025-03-07 | both | pass | 0.000e+00 | 0.000e+00 | 931,834 | 0 | 0 |
| PS46 | 2025-03-10 | both | pass | 0.000e+00 | 0.000e+00 | 907,882 | 0 | 0 |
| PS46 | 2025-03-13 | both | pass | 0.000e+00 | 0.000e+00 | 931,471 | 0 | 0 |
| PS54 | 2025-05-06 | both | pass | 0.000e+00 | 0.000e+00 | 906,555 | 0 | 0 |
| PS54 | 2025-05-09 | both | pass | 0.000e+00 | 0.000e+00 | 905,269 | 0 | 0 |
| PS54 | 2025-05-12 | both | **skip_missing** | — | — | — | — | — |
| PS55 | 2025-05-01 | both | pass | 0.000e+00 | 0.000e+00 | 908,419 | 0 | 0 |
| PS55 | 2025-05-04 | both | pass | 0.000e+00 | 0.000e+00 | 906,367 | 0 | 0 |
| PS55 | 2025-05-07 | both | pass | 0.000e+00 | 0.000e+00 | 904,710 | 0 | 0 |
| PS51 | 2025-04-30 | both | pass | 0.000e+00 | 0.000e+00 | 950,833 | 0 | 0 |
| PS54 | 2025-05-01 | both | pass | 0.000e+00 | 0.000e+00 | 904,368 | 0 | 0 |
| PS55 | 2025-05-02 | both | pass | 0.000e+00 | 0.000e+00 | 908,111 | 0 | 0 |
| PS54 | 2025-06-07 | both | pass | 0.000e+00 | 0.000e+00 | 908,252 | 0 | 0 |
| PS55 | 2025-06-07 | both | pass | 0.000e+00 | 0.000e+00 | 905,983 | 0 | 0 |

PS54/20250512 skip is symmetric: legacy NPZ absent AND consolidated DLC
h5 absent (cohort acquisition intermittency, confirmed 2026-04-22).

**PS50/20250319 integration smoke** (non-parity — PS50 has zero entries
in the 14-session parity set). Swapped from the kickoff's PS50/20250306
because that date predates PS50's `sessions.start = 2025-03-19` so no
Phase 4.5-lite centered parquet exists for it. Both bodyparts returned
bit-identical max|Δ|x = max|Δ|y = 0.000e+00 vs legacy NPZ on 976,222
frames; parquet + QC NPZ sidecar both emitted; strict schema check
(7 cols + 9 metadata keys) passed.

**Commits on this branch** (seven, in order):

1. `docs(prompts): Phase 7a.2 kickoff` — kickoff doc committed in-branch.
2. `feat(config,paths): dlc_kinematics defaults + interpolated_trace()
   resolver` — Task 1.
3. `feat(dlc_kinematics): v5p3 interpolation.py port (7-stage
   tongue+jaw)` — Task 2 initial.
4. `fix(dlc_kinematics): align parquet metadata to strategy §2c +
   docstring refresh` — Task 2 fixup per 2026-04-24 review.
5. `test(dlc_interpolation): 14 §8 unit tests + 10 review-adjustment
   extras` — Task 3 (7 new test functions, 24 new test runs due to
   parametrization).
6. `feat(parity): wire Phase 7a harness to real consolidated parquet
   reader` — Task 4.
7. `docs(phase-7a.2): DECISIONS + interpolation-strategy §2 amendment
   + MIGRATION_LOG + emit-parity-sessions script promotion` — Task 5
   (this entry).

**Test + ruff state.**

- Full pytest: **517 passed, 34 skipped** (no regressions; +24 new
  test runs from Task 3).
- Ruff clean on all touched `.py` files.
- Parity harness `--sessions auto` exit code 0; by_status per above.
- Pre-emit sweep (`scripts/phase_7a/emit_parity_sessions.py`):
  26 OK, 2 skip_missing, 0 fail.

**Behavior differences vs. legacy notebooks.**

- Split emit replaces the 7-stage monolithic NPZ (Knob 1). Legacy NPZ
  on MICROSCOPE stays read-only; consolidated writes parquet + optional
  QC NPZ under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/interpolated_traces/`.
- `X0` / `Y0` read from `AnimalInfo.get_kinematics_baseline(bodypart)`
  (seeded PR #81) instead of top-of-notebook literal constants.
  Faithful port — the literals were per-animal-edited at run time in
  the legacy workflow; the seeded baselines match the ones actually
  used for the legacy NPZs.
- `applies_to` namespaced-tag exclusion schema means the PS51
  2025-05-17 (`[dlc, alignment]`) and 2025-04-26
  (`[dlc, spout_behavior]`) exclusions correctly skip DLC kinematics
  runs without blocking spout behavior. None of these dates intersect
  the 14-session parity set (verified preflight — 0 collisions).
- Data-driven baseline path (`baseline.force=false`) uses a unified
  single Y-pool instead of legacy's separate Y0/X0 pools — see
  2026-04-24 DECISIONS "Data-driven-baseline pool unification"
  sub-entry. Invisible to the parity set since all 8 animals run
  under `force=true` with seeded per-animal baselines.
- Otherwise bit-equivalent on the 14-session parity set at
  `atol=1e-6` — actually exact-equal / max|Δ|=0.0 on 26 of 26
  reachable in-scope sessions × both bodyparts.

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data modified
(legacy NPZs and DLC h5 read-only). Rule 2 — no legacy-repo edits.
Rule 6 — new outputs live under
`stroke_orofacial_pipeline_outputs/dlc_analysis/interpolated_traces/`.
Rule 8 — feature branch; tag pushed post-merge.

**Forward follow-ups for Phase 7b / 7c / 7e / 7f.** Per-trial endpoint
modules read the interpolated-trace parquet via
`resolver.interpolated_trace(bodypart, animal, date)` and the
reward-events sub-table from Phase 2 `licks_and_rewards/...npz`. Side
labels (L/R) are applied at 7b/7c emit via the Phase 6.8 boundary-layer
translator per §5 Option A. Any future kinematics-algorithm change
(parity-gate principle, 2026-04-22 DECISIONS) re-validates via
`scripts/phase_7a/emit_parity_sessions.py` followed by
`tests/scripts/parity_phase7a_interpolation.py --sessions auto`.

---

## Phase 7a.3 V3 — tongue per-trial features (lick1/lick2, per-lick velocity, n_licks family, licking dynamics traces + reductions, tongue angle)

**Date:** 2026-04-29
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.3-tongue-pertrial-features`
**Branch:** `phase/7a.3-tongue-pertrial-features` (renamed from V1
`phase/7a.3-kinematic-features-tongue-jaw` 2026-04-25 post-audit)

**Scope.** Tongue per-trial scalars (Cells 33, 36, 39, 42 per-trial
reductions) and per-frame tongue angle + Cell 50 own-bout scalars +
per-session × side licking-dynamics time-binned traces, all ported from
the canonical tongue notebook
(`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).
First downstream phase consuming the 7a.2 tongue interpolated_traces
parquets. Jaw deferred to Phase 7a.3-jaw (separate phase, distinct
design).

**What landed.**

1. Vendored cells in
   [`docs/legacy_snippets/tongue_pertrial_features.py`](legacy_snippets/tongue_pertrial_features.py)
   (5,428 lines / 207,862 B). Per-cell SHA256s + canonical-notebook
   SHA256 in the file's provenance header. Commit `0b78128`.
2. [`configs/defaults.yaml`](../configs/defaults.yaml)
   `dlc_kinematics.tongue_pertrial:` block. Knob families:
   per-metric windows, `detector` (incl. C5.5
   `accept_peaks_without_fall_run`), `detector_per_cell` (5 cells × per-
   cell knob overrides for legacy_approximate parity, C5.2/C5.4/C5.5),
   `bout`, `bout_per_cell` (5 cells), `bout_mode` (per-metric
   `all`/`first_bout`/`first_multi_bout`), `direction_thresholds`,
   `n_licks_categorical`, `n_licks_binning`, `licking_dynamics`,
   `angle` (incl. `spout_frame_origin_tol_px=2.0`),
   `session_inclusion`, `phase`, `feature_extraction_version="v7a.3"`,
   `interpolation_version="v5p3"`.
3. [`configs/animals.yaml`](../configs/animals.yaml) — NO change
   (cohort-uniform algorithm; per-animal entries in legacy `MOUSE_SPECS`
   are session-filter scope or plot-only knobs, neither relevant to the
   V3 schema).
4. Four `PathResolver` resolver helpers
   ([`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)):
   `tongue_pertrial_angle_parquet`,
   `tongue_pertrial_licking_dynamics_traces_parquet`,
   `tongue_pertrial_endpoints_json` (output, `%Y%m%d`), and
   `dlc_centered_spout_midpoint_parquet` (input glob
   `video2_{YYYY-MM-DD}T*.parquet` with exactly-one-match assertion).
5. Module split (4 files, post-Task-3 split for review-ability):
   - [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py)
     (main): public API (`build_tongue_pertrial`,
     `build_tongue_pertrial_by_animal_date`, `TonguePertrialResult`,
     `TrialEvent`), loaders + 7-step eye-midpoint resolver with C5.6
     likelihood-filtered spout-frame sanity check,
     `_extract_trial_slice`, Cells 33/36/39/42 extractors, per-cell
     knob helpers, `_derive_trial_events_from_spout_behavior`
     (Task 5.0 auto-derive reusing 7a.2's `load_reward_events` +
     `ws_samples_to_frame_indices` + alignment template — zero new
     alignment code), driver core.
   - [`src/stroke_orofacial/dlc_kinematics/_detector.py`](../src/stroke_orofacial/dlc_kinematics/_detector.py):
     unified slope detector (post-C5.1 fixes + C5.5 knob),
     `_LickPeaks`, `_first_run_from`, `_build_bouts`,
     `_filter_peaks_by_bout_mode`, `_moving_avg_nan`.
   - [`src/stroke_orofacial/dlc_kinematics/_angle.py`](../src/stroke_orofacial/dlc_kinematics/_angle.py):
     Cell 50 angle math + NaN-aware gaussian smoothing + per-trial
     scalar sampling + own-bout scalars (incl. Q9
     `n_licks_in_first_multi_bout`) + session-inclusion evaluator.
   - [`src/stroke_orofacial/dlc_kinematics/_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py):
     three atomic writers (parquet × 2 + JSON, temp + os.replace) +
     `_jsonify`.
6. 52 unit tests in
   [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
   (37 cell extractors + driver/schema, 6 trial-events auto-derive,
   3 slope-detector port-bug fixes, 4 per-cell knob overrides, 1
   likelihood-filtered sanity check, 1 accept-no-fall knob).
7. Parity harness
   [`tests/scripts/parity_phase7a3_tongue_pertrial.py`](../tests/scripts/parity_phase7a3_tongue_pertrial.py)
   (default + legacy_approximate modes, 14-session). `_HarnessResolver`
   wrapper routes 7a.3 OUTPUT methods to a temp dir while delegating
   INPUT reads (interpolated_trace, centered_spout_midpoint, licks NPZ,
   alignment template) to a canonical PathResolver. Per-trial re-keying
   handles Option α chronological-across-sides ↔ legacy per-side
   `trial_index`.

**Cohort numerical parity (14-session, legacy_approximate, atol=1e-6).**

| Cell | Pass | Fail | max\|Δ\| range (pass) | max\|Δ\| range (fail) | Notes |
|---|---:|---:|---|---|---|
| 33 | 13/13 | 0 | 0 to 5.7e-14 | — | bit-identical cohort-wide |
| 36 | 13/13 | 0 | 0 to 1.8e-12 | — | bit-identical cohort-wide |
| 39 | 9/13 | 4 | 0 (where pass) | 1.0 (4 sessions) | CSV-stale residual, accepted |
| 42 | 1/13 | 12 | 0 (PS55/2025-05-07 only) | 0.018 to 3.001 | drift, accepted |

`by_status` overall: `{'pass': 1, 'fail': 12, 'skip_missing': 1}`.
PS54/2025-05-12 inherits 7a.1/7a.2 `skip_missing` pattern (legacy NPZs
absent on MICROSCOPE, accepted by Priya 2026-04-22). PS55/2025-05-07 is
the only full pass — Cell 33/36/39/42 all bit-identical. The "fail"
overall count is misleading per the per-cell breakdown — Cells 33+36
are bit-identical cohort-wide; Cells 39+42 carry documented residuals.

**Cell 39 + Cell 42 CSV-stale residual (accepted 2026-04-29 per Priya).**
4 sessions (PS46/2025-03-07, 03-10, 03-13; PS54/2025-06-07) show exactly
Δ=1 lick on `n_licks` for ~2 trials each (~2% of trials cohort-wide).
Direct execution of the vendored Cell 39 `_lick_peaks_from_y_dydt` on
those trials produces peak counts bit-identical to the consolidated
output but disagrees with the saved legacy CSV by 1 peak per trial.
**Saved CSVs were emitted by an older legacy-code revision than what was
vendored.** Consolidated → vendored is the load-bearing parity.
Regenerating the CSVs from the vendored code is out of 7a.3 scope.

**Cell 42 small-drift band (accepted 2026-04-29 per Priya).** 8 of 13
sessions where Cells 33/36/39 are bit-identical have Cell 42 traces
differ by 0.018-0.033 Hz on ~10 Hz lick-rate signals (0.2% relative,
well below any meaningful threshold). Likely numerical-precision
sensitivity in `np.histogram` bin-edge inclusion or smoothing kernel
arithmetic at sub-frame peak positions.

**Acceptance.**
- Default-mode cohort emit (Task 5c): 13/14 sessions, 39/42 files
  emitted under
  `pipeline_outputs/dlc_kinematics/{features/tongue,licking_dynamics/traces,endpoints}/`.
  PS54/2025-05-12 = `skip_missing` (data gap inheriting 7a.1/7a.2).
- legacy_approximate cohort parity (Task 5d): Cell 33 + Cell 36
  bit-identical cohort-wide; Cell 39 + Cell 42 within accepted residual
  bands per above.
- Full pytest suite: 574 passed, 34 skipped, 0 failed.
- Ruff: clean across the 4 module files + harness + tests.

**Behavior differences vs. legacy notebooks.**

- **V1 → V2 → V3 rescoping** (audit-driven; V1 promised wrong scalars,
  V2 fixed scope, V3 expanded for Cell 39 richer set + Cell 42 dual
  emission + Cell 50 production status + unified detector with V3-NEW
  knobs).
- **Output split**: per-frame angle parquet + per-session × side
  traces parquet + per-trial JSON. Legacy emits monolithic per-cell
  CSV/NPZ.
- **`eye_midpoint` = session-wide median** (was implicit in legacy).
- **Reference frame translation explicit** (`eye_in_spout_frame` baked
  into parquet metadata).
- **Cell 50 promoted from "exploratory" to production** (per Priya
  2026-04-25).
- **Per-cell windows shifted from legacy** on Cells 33/39/42/50;
  default-mode cohort NOT byte-identical to legacy by design. Wrapper-
  mode (legacy_approximate) restores legacy windows.
- **`bout_max_ili_ms = 300` unified** (Cell 42 legacy was 400). Per-cell
  `bout_per_cell.cell42` override in legacy_approximate restores 400.
- **`tongue_angle_pass: bool[n_trials]` dropped** — no legacy precedent.
  Replaced with `session_inclusion` 4-bool block.
- **Cell 39 enriched output** (direction tally + categorical + bins).
- **Cell 42 day-binned traces NOT ported** (deferred follow-up).
- **`n_licks_in_first_multi_bout`** is a NEW per-trial Cell 50 own-bout
  scalar (Q9, 2026-04-28) — not present in legacy.
- **Three detector port-bug fixes (C5.1)** to faithfully replicate
  legacy Cell 33's strict semantics: NaN-walking turnover, next-lick
  start = end_idx + 1 (post-fall-run-end), strict-no-fall-run rejection.
  Surfaced by the Task 5b smoke parity diagnostic.
- **Per-cell detector + bout knob overrides (C5.2/C5.4/C5.5)** for
  legacy_approximate parity. Legacy had per-cell-different
  `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES_PER_LICK`,
  `DO_SMOOTH_Y_FOR_DETECTION`, `bout.max_ili_ms`, and
  `accept_peaks_without_fall_run` semantics that a single global knob
  set can't represent.
- **C5.6 likelihood-filtered spout-frame sanity check.** PS55/2025-05-02
  has bimodal degraded R_spout DLC tracking (92% of frames are low-lik
  drift); the unfiltered median crashes the Task 1.5 sanity check at
  +67 px. The C5.6 fix uses likelihood ≥ 0.7 (matching the upstream
  centering algorithm's quality bar) so all 13 emit-eligible sessions
  pass the sanity check.
- **Otherwise** within `atol=1e-6` (or bit-identical) on Cells
  33/36/39/42 in legacy_approximate mode (cohort-wide for 33+36;
  residuals on 39+42 documented above). Cell 50 visual gate against
  legacy figures **DEFERRED** to a follow-up phase per kickoff §5b.7
  acceptance carve-out.

**Ground-rule compliance** (CLAUDE.md).

- Rule 1 (no source data modification): verified. Task 1.5 + cohort
  emit reads MICROSCOPE upstream parquets read-only. Outputs land in
  NEW `dlc_kinematics/` subtree under
  `stroke_orofacial_pipeline_outputs/`.
- Rule 2 (no legacy-repo edits): verified. All work in this consolidated
  repo only.
- Rule 6 (new outputs in fresh paths): verified.
  `dlc_kinematics/{features/tongue,licking_dynamics/traces,endpoints,
  figures_qc}/` are all new directories not previously in the
  pipeline_outputs tree.
- Rule 8 (git discipline): verified. 11 feature-branch commits
  (V1 + V2 + vendor + 9 implementation), no force-push, V1 + V2 +
  vendor commits preserved as paper trail in branch history.

**Forward follow-ups (post-7a.3 PR merge).**

- **Phase 7a.3-jaw** with jaw-specific design.
- **Future face-velocity / PSD / mismatch-classifier phases** consume
  the 7a.3 V3 outputs.
- **Cell 42 day-binned traces** + per-trial pass-mask
  (`tongue_angle_pass`) available as follow-up phases (deferred from V3
  scope per Priya).
- **Cell 50 visual gate** (5 plot families per session, side-by-side
  compare against legacy `angle_phase_exploratory` PNGs).
- **Regenerate stale legacy CSVs** from the vendored code (would close
  Cell 39 + Cell 42 residuals at exact parity if it ever becomes a
  real problem).
- **Factor `licks_npz(animal, date)` into PathResolver** (currently
  duplicated inline at 7a.2 + 7a.3; deferred per Priya 2026-04-28).
- **Per-frame eye-midpoint emit** (resolver currently computes
  session-wide median internally; downstream phases that want
  per-frame values would need to re-derive).


## Phase 7a.4 — Cell 50 visual gate + Cell 42 day-binned cross-session traces

**Date:** 2026-04-30
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.4-tongue-visual-and-day-binned`
**Branch:** `phase/7a.4-tongue-visual-and-day-binned`

**Scope.** Two carve-outs deferred from Phase 7a.3 V3:
(1) Cell 50 visual gate — render the 5 plot families per session and
side-by-side compare against legacy `angle_phase_exploratory/` PNGs from
MICROSCOPE; (2) Cell 42 day-binned cross-session aggregator — emit
per-animal per-`rel_day_bin` parquet aggregating the 7a.3 V3 per-session
licking-dynamics traces, gated by per-animal `bin_days`. Both consume
7a.3 V3's locked outputs without modifying its core modules.

**What landed.**

1. [`configs/animals.yaml`](../configs/animals.yaml) — per-animal
   `bin_days` field. PS46-50 → 2; PS51/PS54/PS55 → 7.
   `AnimalInfo.bin_days: int = 1` default with positive-int validation
   (rejects bools — Python's bool-is-int subclass).
2. [`configs/defaults.yaml`](../configs/defaults.yaml)
   `dlc_kinematics.tongue_pertrial.day_binned:` 3-key sub-block +
   sibling `dlc_kinematics.tongue_visual:` block (bundle windows,
   render-mode selectors, render-time aggregation filters, figure
   layout, 5 plot-family enable/tweak knobs, side colours,
   comparison-grid layout).
3. [`src/stroke_orofacial/dlc_kinematics/_day_binned.py`](../src/stroke_orofacial/dlc_kinematics/_day_binned.py)
   — Cell 42 day-binned aggregator (~544 lines). Per-animal × per-
   `rel_day_bin` wide-form parquet. Aggregation function `np.nanmean`
   across sessions; SEM = `nanstd(ddof=1) / sqrt(n_support)` per cell;
   per-metric `*_n_support_sessions` tracking. Legacy `f"{lo}..{hi}"`
   rel-day-bin label format preserved (literal `..` in filenames —
   NTFS-legal). Atomic writer (pyarrow snappy + temp + os.replace +
   bytes-encoded metadata) vendored locally to keep
   [`_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py)
   untouched. 11 file-level metadata keys (animal, rel_day_bin_label,
   bin_days, stroke_date, n_sessions, sessions_iso_dates [JSON],
   aggregation_function, feature_extraction_version,
   interpolation_version, day_binned_version, emit_sem,
   emit_n_support_sessions). `DAY_BINNED_VERSION = "v7a.4"`. Convenience
   wrapper `aggregate_licking_dynamics_day_binned_by_animal` derives the
   session list from existing per-session parquets.
4. [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py)
   — additive bundle helper (Task 3.5). `_PertrialCoreResult` private
   frozen dataclass wraps both `TonguePertrialResult` (existing emit-set
   pieces) and a new public `TongueVisualBundle` frozen dataclass
   (`df_trials`, `df_bouts`, `df_phase`, `angle_per_frame`, `metadata`).
   New public `build_tongue_visual_bundle` + `_by_animal_date` wrapper.
   Same compute path as `build_tongue_pertrial`; bundle DataFrames are
   net-new compute (~400 lines: `_bout_time_bounds_ms`,
   `_assign_phase_peak_to_peak_shifted`, `_build_visual_bundle_per_trial`)
   that reuses 7a.3 primitives but keeps the array snippets / per-bout
   rows / per-frame phase rows that 7a.3 V3's emit path discards.
   `_build_tongue_pertrial_core` refactored to return
   `_PertrialCoreResult`; `build_tongue_pertrial` consumes
   `core.tongue_pertrial`; `build_tongue_visual_bundle` consumes
   `core.visual_bundle`. File 1376 → 1928 lines (+552).
5. [`src/stroke_orofacial/dlc_kinematics/tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py)
   — Cell 50 rendering module (~947 lines). `matplotlib.use("Agg")`
   forced at module load (headless cohort runs). `render_tongue_qc_figures`
   driver: 6 PNGs per session (Family 1 per-side × 2 + Families 2-5 × 1).
   `render_comparison_grid` driver: 2-col side-by-side (legacy |
   consolidated) per family; placeholder pane on legacy-not-found.
   `render_for_manifest` Task 5 hook. 5 plot-family helpers ported from
   legacy Cell 50 vendor lines 4474-4753: `_plot_per_trial_qc_traces`
   (per-side stacked Y + angle, bout shading, peak markers),
   `_plot_first_peak_aligned`, `_plot_reward_aligned`,
   `_plot_phase_aligned_angle`, `_plot_xy_by_phase`. Atomic-ish save
   (temp `.tmp.png` + os.replace; `format="png"` passed explicitly).
6. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
   — three new resolvers:
   `tongue_pertrial_licking_dynamics_day_binned_parquet(animal, label)`
   (eager parent mkdir; literal `..` in filename),
   `tongue_visual_qc_dir(animal, date)`,
   `tongue_visual_comparison_dir(animal, date)`.
7. [`src/stroke_orofacial/dlc_kinematics/__init__.py`](../src/stroke_orofacial/dlc_kinematics/__init__.py)
   — exports `DAY_BINNED_VERSION`, `DayBinnedResult`,
   `TongueVisualBundle`, `aggregate_licking_dynamics_day_binned`,
   `aggregate_licking_dynamics_day_binned_by_animal`,
   `build_tongue_visual_bundle`, `build_tongue_visual_bundle_by_animal_date`,
   `render_tongue_qc_figures`, `render_comparison_grid`.
8. 36+ new tests:
   [`tests/test_day_binned.py`](../tests/test_day_binned.py) (18 —
   rel-day-bin label algorithm × 7, aggregator × 5, driver I/O × 2,
   overwrite × 2, schema guards × 2);
   [`tests/test_tongue_visual.py`](../tests/test_tongue_visual.py) (13
   — driver × 5, family helpers × 5, comparison grid × 3); 5 new
   TestVisualBundle tests in
   [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
   (shape, bit-identical metadata + angle_per_frame to emit set,
   does-not-write-files, default params, frozen dataclass) + 3 C5.5/C5.6
   regression tests; 4 new TestPhase7a4Paths tests in
   [`tests/test_paths.py`](../tests/test_paths.py); 5 new TestBinDays
   tests in [`tests/test_animals.py`](../tests/test_animals.py).
9. Two new harness scripts:
   [`tests/scripts/parity_phase7a4_day_binned.py`](../tests/scripts/parity_phase7a4_day_binned.py)
   (~546 lines, reuses 7a.3 V3 primitives via sys.path import; `--mode
   {default, legacy_approximate}` + `--animals auto` + `--atol 1e-6`;
   per-cell mean / SEM-with-ddof-transform / n_support_sessions
   comparator; hard-fail thresholds 1.0 Hz / 0.1 prob);
   [`tests/scripts/parity_phase7a4_visual_gate.py`](../tests/scripts/parity_phase7a4_visual_gate.py)
   (~231 lines, builds bundle + renders 6 consolidated PNGs + 6
   comparison grids per session; reports per-grid file size +
   per-family legacy-match count).
10. [`docs/DECISIONS.md`](DECISIONS.md) Phase 7a.4 entry above the 7a.3
    V3 entry — codifies the 12 design decisions, visual-gate pass
    criterion (semantic match), day-binned schema, `bin_days`
    placement, additive-helper rationale.

**Behavior differences vs legacy notebooks.**

- **Visual gate accepted** with documented lick-count delta in the
  phase-aligned plot annotations (downstream visual reflection of
  7a.3 V3 Cell 39 CSV-stale residual + Cell 42 numerical-precision
  band; both already accepted in 7a.3 V3 cohort parity, NOT a new
  finding).
- **Day-binned cohort parity vs legacy CSV deferred** — structural
  blocker on session-set mismatch (15 consolidated sessions vs ~120
  legacy). Algorithmic correctness instead established via the 18
  unit tests + chain composition with locked 7a.3 V3 input. See
  DECISIONS Decision 3.
- **SEM ddof convention change in day-binned** (ddof=1 unbiased,
  divided by sqrt(n_support)) vs legacy (ddof=0, divided by
  sqrt(n_total)). Parity harness applies inverse transform
  `SEM_legacy = SEM_cons * sqrt((n_support - 1) / n_total)`. Plot-time
  family 4 uses ddof=0 to preserve legacy visual fidelity.
- **Metric rename** `ili_within_bout_rate_per_t` (7a.3 V3 input
  column) → `bout_rate_mean_hz` (day-binned output base name).
  Other 3 metrics keep 7a.3 V3 names.
- **Per-metric `*_n_support_sessions`** tracking (each metric tracks
  its own NaN pattern; legacy precedent).

**Test counts.**

- Full pytest before 7a.4: 609 collected, 575 passed, 34 skipped, 0
  failed (post-7a.3 V3 merge baseline).
- Full pytest after 7a.4 (post-C5.6): **658 collected, 623 passed, 35
  skipped, 0 failed**. Net +49 / +48 / +1.
- New tests by file: test_day_binned.py 18; test_tongue_visual.py 13;
  TestVisualBundle in test_tongue_pertrial.py 5 + 3 C5.5/C5.6
  regressions; test_paths.py +4; test_animals.py +5. Total +48
  passed + 1 new skip (`test_visual_bundle_peaks_in_df_phase_land_at_0_5`
  conditionally skips on synthetic fixtures with no multi-lick bouts).

**Commit chain (10 commits since main).**

```
8a30c20  docs(_detector): clarify peak_indices yseg-local convention (C5.6)
857cf6f  fix(tongue_visual): phase shift + QC angle-subplot dot offset (C5.5)
b8023d2  feat(parity): tongue pertrial day-binned + visual gate harnesses
3d3207b  feat(dlc_kinematics): tongue_visual rendering module
a6c09e2  feat(tongue_pertrial): build_tongue_visual_bundle additive helper
ab4e6ae  feat(dlc_kinematics): _day_binned cross-session traces aggregator
a30564e  feat(config+paths): bin_days + day_binned/tongue_visual schemas + 3 resolvers
b48e313  chore: ignore .scratch_*/ working-area directories
4d49322  docs(phase-7a.4): kickoff + state-doc refresh post-7a.3 merge
<this>   docs(phase-7a.4): DECISIONS + MIGRATION_LOG entries
```

**Ground-rule compliance (CLAUDE.md).**

- **Rule 1** (no source data modified): verified. Read-only access to
  legacy `*_dayBinnedTraces_*.csv` from MICROSCOPE; read-only access
  to legacy `angle_phase_exploratory/*.png` for comparison grids.
- **Rule 2** (no legacy-repo edits): verified. All work in this repo.
- **Rule 6** (new outputs in fresh paths): verified. New trees:
  `dlc_kinematics/figures_qc/tongue/`,
  `dlc_kinematics/figures_qc/tongue_comparison/`,
  `dlc_kinematics/licking_dynamics/day_binned/`. None overlap existing
  pipeline_outputs subtrees.
- **Rule 8** (git discipline): verified. 10 feature-branch commits, no
  force-push, V1 + V2 + vendor commits preserved as paper trail in
  branch history.

**Forward follow-ups (post-7a.4 PR merge).**

- **Cohort-wide 7a.2/7a.3 upstream re-emit** + day-binned cohort
  parity re-run vs legacy CSV (~120 sessions across 8 animals;
  expected residual band 0.018-0.05 Hz matching 7a.3 V3 Cell 42).
- **Cross-session overlay plot families** (`_plot_overlay_grid_all_sessions`
  + `_plot_overlay_grid_binned` from vendor lines 4826-5096) — per-mouse
  not per-session; out of 7a.4 scope.
- **Phase 7a.3-jaw visual gate** — extends the same machinery once
  jaw per-trial features land.
- **`licks_npz(animal, date)` PathResolver factor-out** from 7a.3
  (carryover follow-up).
- **NaN-walking captured-fixture regression test** (7a.3 V3 test gap
  dropped in C5.1; 7a.4 didn't naturally surface a fixture candidate).


## Phase 7a.3-jaw — audit confirms no per-trial features in jaw notebook (Outcome A)

**Date:** 2026-05-01
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.3-jaw-audit-no-pertrial-features`
**Branch:** `phase/7a.3-jaw`

**Scope.** Audit-only formal investigation of whether the canonical
jaw notebook contains per-trial features analogous to the tongue
per-trial work that 7a.3 V3 ported. The 2026-04-25 V2 audit (during
7a.3 V3 scoping) reported incidentally that the jaw notebook has no
such features. This phase confirms that finding rigorously via a
comprehensive cell-level audit. **Outcome A — confirmed empty.**

**What landed.**

1. Comprehensive cell-level classification of all 25 code cells in the
   canonical jaw notebook
   (`\\research...\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`,
   SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`,
   434 MB, 7,293 code lines).
2. [`docs/DECISIONS.md`](DECISIONS.md) Phase 7a.3-jaw entry (10
   numbered decisions) codifying audit findings, V2 finding
   confirmation, Cell 41/42 disposition, Cell 43 PSD note, Outcome A
   acceptance, forward follow-ups.
3. This MIGRATION_LOG entry.

No code changes. No new tests. No new configs. No parity harness.
The audit alone is the deliverable.

**Per-cell classification summary.**

| Class | Count | Cells |
|---|---:|---|
| infrastructure (load / merge / one-off fixup) | 9 | 1, 3, 5, 7, 13, 14, 15, 16, 18 |
| exploratory (in-memory plots, no save) | 6 | 9, 11, 20, 24, 26, 28 |
| production (already ported in 7a.2) | 1 | 22 (jaw v5p3 interpolation) |
| production-viz (PNG figures) | 6 | 30, 32, 34, 37, 39, 43 |
| broken (V2 finding confirmed) | 2 | 41, 42 |
| empty | 1 | 44 |

**Behavior differences vs legacy.** None — no code shipped. The phase
formalizes the V2 incidental audit's finding that the jaw notebook
has no per-trial features in the form 7a.3 V3 ported for tongue.

**Cells 41/42 disposition.** Confirmed broken (V2 finding airtight
per 3 pieces of evidence: path mismatch — `_mouse_base()` returns
`{mouse}_jaw_kinematics/{CENTER_MODE}/` while real on-disk path is
`{mouse}_tongue_kinematics/kinematics_figures/{CENTER_MODE}/lick_metrics/...`;
filename version mismatch — `_dydt_v5.csv` lookup target vs real
`_v5p3.csv` files; missing files — `find` confirms zero `*pertrial*`
files anywhere under `PS46_jaw_kinematics/`). Not portable as-written;
would need to be REWRITTEN from tongue's per-trial pipeline (which is
already shipped) — that's a green-field design phase, not a port.

**Cell 43 PSD.** Deferred to future face-rhythmicity QC /
`docs/phase-7/interpolation-strategy.md` §7 face-velocity / PSD phase.
Out of 7a.3-jaw scope per the audit-first charter.

**Test counts.** Full pytest unchanged from 7a.4 baseline:
**623 passed / 35 skipped / 0 failed**. No new tests; no existing
tests touched.

**Commit chain (3 commits since main).**

```
<Task 2.A SHA>  docs(phase-7a.3-jaw): DECISIONS + MIGRATION_LOG entries (audit-only close, Outcome A)
9ff597d         docs(phase-7a.3-jaw): kickoff + state-doc refresh post-7a.4 merge
```

(Task 0 = the kickoff commit Priya made; Task 2.A = this commit;
Task 3.A = PR open with no additional commit.)

**Ground-rule compliance (CLAUDE.md).**

- **Rule 1** (no source data modified): verified. Jaw notebook stays
  read-only on MICROSCOPE; audit reads only.
- **Rule 2** (no legacy-repo edits): verified.
- **Rule 6** (new outputs in fresh paths): N/A — no new outputs
  emitted by this phase.
- **Rule 8** (git discipline): verified. 2 feature-branch commits,
  no force-push.

**Forward follow-ups (post-7a.3-jaw PR merge).**

- **Phase 7a.x-jaw-pertrial-design** (green-field) — only if jaw
  per-trial features become a research need. Distinct from porting
  legacy work (which 7a.3-jaw confirmed is absent for jaw). Would
  require: scientific design (what jaw motions matter biologically),
  detector tuning (slope detector tuned for jaw kinematics ≠ tongue
  protrusion), synthetic-only validation (no legacy reference).
- **Cell 43 PSD port** to a future face-rhythmicity QC / strategy
  §7 face-velocity / PSD phase if downstream demands it.
- **Cohort-wide 7a.2/7a.3 upstream re-emit** (carries forward from
  7a.4 deferred follow-ups, unaffected by this phase).


## Phase 7a.5-mismatch — tongue-jaw mismatch trial classifier + jaw per-trial features (Outcome B hybrid B1.5)

**Date:** 2026-05-01
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.5-tongue-jaw-mismatch`
**Branch:** `phase/7a.5-mismatch`

**Scope.** Tongue-jaw mismatch trial classifier + 4 plot families
(within-session individual + 4×2 overlay grid; cross-session overlay +
day-binned) + jaw per-trial scalars (8 fields, extracted from Cell 53
inline-detection logic). Audit-first phase that became a substantial
port (Outcome B) with hybrid B1.5 sub-variant (two modules, single
phase, single PR + tag).

**What landed.**

1. [`docs/legacy_snippets/tongue_jaw_mismatch.py`](legacy_snippets/tongue_jaw_mismatch.py)
   — vendored byte-identical canonical tongue notebook cells 51-55
   (1903 source lines: 3 markdown headers + 2 code cells; cell 53
   classifier 605 lines, cell 55 plotter 1295 lines). Per-cell SHA256s
   recorded in the header per the 7a.0 / 7a.3 vendor pattern. Raw
   docstring (`r"""..."""`) supersedes legacy `tongue_pertrial_features.py`
   plain-string convention — fixes the `\\research...\` UNC path
   `\N`-escape ruff error in this new file (unrelated cleanup of an
   inherited issue).
2. [`configs/defaults.yaml`](../configs/defaults.yaml)
   `dlc_kinematics.jaw_pertrial:` (8 keys) +
   `dlc_kinematics.tongue_jaw_mismatch:` (~45 keys after C6.2 layout
   spec landed). Knob-set captures: jaw baseline / detect window;
   threshold sd-multiplier + px floor + sustained-density rule;
   tongue-detector knobs LOCAL to mismatch (no MIN_FINITE filter,
   smoothing off, accept-no-fall — Cells-36/39/42-style permissive,
   per Decision 9 in DECISIONS.md); 4 plot families with
   legacy-verbatim figsize / DPI / hspace / wspace / colorbar rect /
   tight_layout rect / mean±SEM percentile-cap / faint trial overlay
   alpha+linewidth / per-row shared-Y / sort-by-side knobs.
3. [`src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py)
   — 556 lines. Public reusable building block mirroring
   `tongue_pertrial.py` at smaller scale. 8 per-trial scalars +
   metadata. `JawPertrialResult` frozen dataclass. Public API:
   `build_jaw_pertrial(manifest, resolver, trial_events, ...)` +
   `build_jaw_pertrial_by_animal_date(...)` convenience wrapper.
   Trial-events auto-derive via 7a.3 V3's
   `_derive_trial_events_from_spout_behavior` (private cross-module
   import — matches 7a.4 `_day_binned.py` precedent). Atomic JSON
   write via shared `_writers._write_endpoints_json_atomic`.
4. [`src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`](../src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py)
   — 1078 lines. Classifier `classify_tongue_jaw_mismatch(...)` +
   convenience wrapper `_by_animal_date(...)` emits per-session
   candidate-trials parquet (~21 cols + 28 file-level metadata keys;
   schema deviation from legacy 37-col CSV per DECISIONS Decision 8).
   Auto-builds upstream `jaw_pertrial` JSON via `overwrite="skip"` if
   missing. Tongue lick-count via Cell 33 `_slope_detect_lick_peaks`
   primitive with mismatch-LOCAL knobs (`_build_tongue_detector_params`).
   4 plot family helpers: `_plot_individual_trials_2col` (legacy
   verbatim layout 18 × max(12, 1.8 × n_rows) at DPI=200),
   `_plot_session_overlay_grid_4x2` (4 rows × 2 cols, mean±SEM rows
   with faint trial overlays per legacy `FAINT_TRIAL_*` constants),
   `_plot_cross_session_overlay`, `_plot_cross_session_binned`
   (per-mouse, day-binned via `animal_info.bin_days` from
   `configs/animals.yaml` per the 7a.4 day-binned precedent). Atomic
   savers vendored locally to keep `_writers.py` untouched.
   `matplotlib.use("Agg")` forced at module load (headless cohort
   runs).
5. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
   — 4 new resolvers:
   `jaw_pertrial_endpoints_json(animal, date)` (eager parent mkdir),
   `tongue_jaw_mismatch_candidate_trials_parquet(animal, date)`
   (eager parent mkdir),
   `tongue_jaw_mismatch_qc_dir(animal, date)` (no eager mkdir —
   directory resolver, 7a.4 convention),
   `tongue_jaw_mismatch_cross_session_dir(animal)` (no eager mkdir;
   per-mouse only, no date dimension).
6. [`src/stroke_orofacial/dlc_kinematics/__init__.py`](../src/stroke_orofacial/dlc_kinematics/__init__.py)
   — 6 new public exports: `JAW_PERTRIAL_VERSION`,
   `TONGUE_JAW_MISMATCH_VERSION`, `JawPertrialResult`,
   `TongueJawMismatchResult`, `build_jaw_pertrial`,
   `build_jaw_pertrial_by_animal_date`, `classify_tongue_jaw_mismatch`,
   `classify_tongue_jaw_mismatch_by_animal_date`,
   `render_within_session_figures`, `render_cross_session_figures`.
7. **40 net new unit tests:**
   [`tests/test_jaw_pertrial.py`](../tests/test_jaw_pertrial.py)
   (12 — helpers × 7 covering baseline / deflections / threshold-pick /
   sustained-density; driver × 3 covering JSON schema + overwrite +
   degenerate-baseline; edge cases × 2);
   [`tests/test_tongue_jaw_mismatch.py`](../tests/test_tongue_jaw_mismatch.py)
   (28 — predicate truth-table × 3, schema/edges × 4, plot-family
   smoke × 4, visual-fidelity pins × 14 covering C6.1-C6.2-C6.3 fixes,
   module edges × 3); plus
   [`tests/test_paths.py`](../tests/test_paths.py)
   `TestPhase7a5Paths` (4 tests for the 4 new resolvers including
   round-trip mkdir checks for directory resolvers).
8. [`tests/scripts/parity_phase7a5_mismatch.py`](../tests/scripts/parity_phase7a5_mismatch.py)
   — 687-line numerical parity harness. CLI `--mode {default,
   legacy_approximate} --sessions {auto, cohort} --atol 1e-6
   --emit-root <path> --animals <list>`. Reuses 7a.3 V3's
   `PARITY_SESSIONS_14` scope + `MICROSCOPE_ROOT` constant.
   Per-mouse aggregation of per-session parquets to compare against
   legacy per-mouse CSV. Column-rename map handled via per-pair `kind`
   field (atol / exact_int / exact_bool / exact_str / skip).
   Trial-indexing convention auto-detect (`_compare_trial_indexing_convention`)
   robust to α / β. Cohort sanity check
   `legacy.jaw_thresh_abs == 4 × legacy.jaw_baseline_sd` per animal.
9. [`tests/scripts/parity_phase7a5_visual_gate.py`](../tests/scripts/parity_phase7a5_visual_gate.py)
   — 361-line visual-gate runner. Renders consolidated within-session
   PNGs + cross-session PNGs + comparison grids legacy | consolidated
   per family. Aspect-aware compare-grid figsize + LANCZOS resampling
   (C6.2 fix to the squished-tall-image issue traced to compare-grid
   PIL resample, not the consolidated render itself).
10. [`docs/DECISIONS.md`](DECISIONS.md) Phase 7a.5-mismatch entry above
    the 7a.3-jaw entry — codifies the 18 decisions + scope + scientific
    rationale + visual fix highlights + forward follow-ups.
11. This MIGRATION_LOG entry.

**Behavior differences vs legacy notebooks.**

- **Schema deviations** per DECISIONS Decision 8: 21 per-row + 28
  metadata vs legacy 37 per-row; `n_licks_in_window` →
  `n_licks_in_quiet_win`; `jaw_thresh_abs` semantics swap +
  categorical `jaw_thresh_px_used`; reward-frame consolidation;
  NPZ provenance dropped.
- **β / α trial-indexing reconciled** at parity-time on
  `(date, side, reward_frame_idx)` join key (DECISIONS Decision 11).
- **Per-session emit cadence** (modern parquet) vs legacy per-mouse
  aggregated CSV. Per-mouse aggregation reconstructed at parity time.
- **Mean±SEM auto-scale percentile bounds skip trial concatenation
  when `show_trial_overlays=False`** (DECISIONS Decision 15) — the
  one bounded modern deviation from legacy
  `_limits_from_rows`-includes-trial-data-unconditionally semantics.
  Both branches pinned by regression tests.
- **`accept_peaks_without_fall_run=True`** in mismatch tongue detector
  matches Cell 53's actual permissive behavior, NOT the legacy
  `STRICT_NO_FALLBACK` constant which the detector function does not
  enforce (DECISIONS Decision 9).
- **`jaw_direction_mode` hardcoded to `"above_or_below"`** (cohort
  default; per-mouse override infrastructure dropped per DECISIONS
  Decision 6e — YAGNI).

**Parity result (legacy_approximate, 14-session, atol=1e-6).**

- 8 animals: **3 pass + 1 fail + 4 skip_no_legacy**.
- Cohort `max|Δ|` per atol column: **1.42e-14** worst case (round-off
  only, well below atol=1e-6). 1259/1260 atol cells bit-clean.
- 1 fail = PS46/2025-03-07 single-row `n_licks_in_quiet_win`
  off-by-one (1/289 PS46 in-scope rows = 0.35%; 1/1260 cohort rows =
  0.08%). Does NOT propagate to `quiet_tongue_pass`, `jaw_pass_qc`,
  or `candidate_no_lick_with_jaw_move`. Boundary-case integer
  residual; not a bug. (DECISIONS Decision 10.)
- 4 skip_no_legacy = PS47/48/49/50 — out of 14-session scope (full-
  cohort parity awaits the deferred upstream re-emit listed in the
  Forward follow-ups).
- All booleans bit-identical including the load-bearing
  `candidate_no_lick_with_jaw_move`.
- `legacy.jaw_thresh_abs == 4 × legacy.jaw_baseline_sd` cohort sanity:
  100.00% match across 1260 in-scope rows.

**Visual gate verdict: PASS** (Priya 2026-04-30 → 2026-05-01).

- 5 sessions × within-session families + 2 mice × cross-session
  families; all `legacy match 2/2` per session/per-mouse.
- Visual fidelity iterated through 3 rounds (C6.1 → C6.2 → C6.3,
  10 fixes total). Final approval after C6.3 mean+SEM trial-overlay
  inclusion fix.
- Scientific finding: candidate-rate progression PS46 baseline
  **0.0%** → PS55 d+2 **61.9%** → PS55 d+38 **52.5%** — the
  dissociation phenotype manifests in the data, not just a port
  artifact (DECISIONS Decision 5).

**Cohort emit (under `<outputs>/dlc_kinematics/tongue_jaw_mismatch/`
on MICROSCOPE).**

- 13 candidate-trials parquets (14 in-scope sessions − 1 PS54/2025-05-12
  `skip_missing` known data gap).
- 26 within-session figures (13 sessions × 2 plot families:
  individualTrials2col + sessionOverlayGrid4x2).
- 8 cross-session figures (4 mice × 2 plot families:
  crossSessionOverlay2x2 + crossSessionBinned2x2_bins{N}).
- 14 comparison grids (5 sessions × 2 within-session + 2 mice × 2
  cross-session). Aspect-aware figsize + LANCZOS resampling per C6.2.

**Test counts.**

- Full pytest before 7a.5: 658 collected, 623 passed, 35 skipped, 0
  failed (post-7a.4 baseline).
- Full pytest after 7a.5 (post-C6.3): **702 collected, 667 passed, 35
  skipped, 0 failed**. Net +44 / +44 / 0.
- New tests by file: `test_jaw_pertrial.py` 12;
  `test_tongue_jaw_mismatch.py` 28; `test_paths.py` +4
  (`TestPhase7a5Paths`). Total +44 passed.

**Commit chain (10 commits since main, post-7a.3-jaw merge).**

```
<this>     docs(phase-7a.5-mismatch): DECISIONS + MIGRATION_LOG entries
f316d31    fix(tongue_jaw_mismatch): mean+SEM auto-scale includes trial overlays when shown (7a.5 C6.3)
763778b    fix(tongue_jaw_mismatch): visual rendering round 2 — axis labels, mean+SEM per-row + trial overlays + subtitles, individual-trials spacing (7a.5 C6.2)
9f2aa37    fix(tongue_jaw_mismatch): visual rendering — Y-axis offset + sort-by-side + shared-Y + colorbar (7a.5 C6.1)
2431200    feat(parity): Phase 7a.5 mismatch parity harness + visual gate runner (7a.5)
134d458    feat(dlc_kinematics): tongue_jaw_mismatch — classifier + 4 plot families (7a.5)
95c6b64    feat(dlc_kinematics): jaw_pertrial module — per-trial jaw scalars from Cell 53 inline logic (7a.5)
e78e989    feat(config+paths): jaw_pertrial + tongue_jaw_mismatch schemas + 4 resolvers (7a.5)
4d34a8f    docs(legacy_snippets): vendor tongue-jaw mismatch cells 51-55 (7a.5)
32dcc85    docs(phase-7a.5-mismatch): kickoff extension — Tasks 2-8 specs (Outcome B hybrid B1.5)
f46e78c    docs(phase-7a.5-mismatch): kickoff + state-doc refresh post-7a.3-jaw merge
```

(Task 0 = `f46e78c` kickoff committed by Priya; Task 1 = audit only,
no commit; Task 0' = `32dcc85` kickoff extension after Task 1
STOP-and-report locked Outcome B + Tasks 2-8; Tasks 2-8 = remaining
commits in order.)

**Ground-rule compliance (CLAUDE.md).**

- **Rule 1** (no source data modified): verified. Tongue notebook
  stays read-only on MICROSCOPE; legacy CSVs + PNGs read-only.
- **Rule 2** (no legacy-repo edits): verified. All work in this repo.
- **Rule 6** (new outputs in fresh paths): verified. New trees:
  `dlc_kinematics/jaw_pertrial/endpoints/`,
  `dlc_kinematics/tongue_jaw_mismatch/{candidate_trials, figures_qc,
  cross_session, comparison_grids}/`. None overlap existing
  pipeline_outputs subtrees.
- **Rule 8** (git discipline): verified. 10 feature-branch commits,
  no force-push. C6.1 + C6.2 + C6.3 visual-iteration commits all
  preserved as paper trail in branch history (rather than
  rebased away).

**Forward follow-ups (post-7a.5-mismatch PR merge).**

- **Phase 7a.6** — tongue + jaw mean/SEM visual gate (Priya picked
  as next).
- **Phase 7a.7** — DLC heatmaps (3 independent legacy sources).
- **Phase 7a.8** — new reward-aligned heatmaps visual QC.
- **Phase 8a.10** — spout behavior visual gate.
- **Phase 9 stats plots** forward-pointer (deferred to statistics
  phase).
- **Phase 7a.x-jaw-pertrial-greenfield** — green-field jaw per-trial
  design, only if research demands beyond the 8 scalars Cell 53
  inline-extracted (DECISIONS Decision 3).
- **Cell 43 PSD port** (deferred from 7a.3-jaw — fold into 7a.6 or
  own follow-up depending on scope).
- **Cohort-wide 7a.2/7a.3 upstream re-emit** + full-cohort parity on
  PS47-50 (deferred from 7a.4; carries forward; structural blocker
  for the 4 `skip_no_legacy` animals).
- **Stale `figures_qc/comparison_grids/...` PNGs** from the C6.1
  path-bug remain on MICROSCOPE; can be pruned by Priya at her
  discretion (harmless leftovers; correct C6.2+ grids land at
  `comparison_grids/{animal}/{date}/...`).

---

## Phase 7a.6 — Mean/SEM visual gate (tongue + jaw, bodypart-parametric)

**Date:** 2026-05-03
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.6-mean-sem`
**Branch:** `phase/7a.6-mean-sem`

**Scope.** Port the `## Per session and combined mean/SEM plots`
section from both legacy notebooks (canonical tongue cells 31, 45,
47, 48; canonical jaw cells 30, 32, 34) into a single bodypart-
parametric module. 7 production cells × ~3,873 source lines collapse
to ~3,400 LOC of consolidated module. Closes the last 7a.x kinematics
port outstanding on the Q2 2026 roadmap.

**What landed.**

1. [`src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py)
   — net-new ~3,400L module. Single bodypart-parametric implementation
   of all 6 plot families (`individual_sessions`, `trial_overlays`,
   `session_overlays`, `binned_overlays`, `mean_trace`, `mean_video`)
   plus 2 composite wrappers (`build_mean_sem_by_animal_date` for
   per-(animal, date) emit and `build_mean_sem_cohort` for per-animal
   emit). `MEAN_SEM_VISUAL_VERSION = "v7a.6"`.

2. [`docs/legacy_snippets/tongue_mean_sem_section.py`](legacy_snippets/tongue_mean_sem_section.py)
   and [`docs/legacy_snippets/jaw_mean_sem_section.py`](legacy_snippets/jaw_mean_sem_section.py)
   — vendored byte-identical canonical-cell sources per the 7a.0 / 7a.3
   / 7a.5 vendor pattern. Tongue cells 31 + 45 + 47 + 48; jaw cells
   30 + 32 + 34. Cell-boundary delimiter comments make each cell
   greppable. Per-cell SHA256s in the file headers.

3. [`configs/defaults.yaml`](../configs/defaults.yaml)
   — new `dlc_kinematics.mean_sem_visual:` block. Top-level shared
   knobs (figure width / height, mean+SEM percentile cap, faint trial
   overlay alpha+linewidth, time smoothing window) + per-bodypart
   override sub-blocks (`tongue:` and `jaw:` for divergent values
   like figure width and centering mode). Mean-trace sub-block under
   that for the multi-bin layout (`legend_right_fraction`,
   `legend_anchor_x`, `legend_anchor_y`, `panel_wspace`,
   `symmetric_pad_frac`). Mean-video sub-block (`video_format: mp4`,
   `anim_fps: 60`, `anim_speed: 0.125`, `tail_ms`, `video_dpi`,
   `save_both_modes: true`, `with_frame_timestamps: true` per Q5,
   `mean_video_windows_subset: [[100, 1000]]` per C7.7).

4. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
   — net-new resolver `mean_sem_visual_dir(bodypart, *, center_mode,
   reward_pre_ms, reward_post_ms, plot_family, animal)` returning
   `<outputs>/dlc_kinematics/mean_sem/{bodypart}/{center_mode}/
   rewardAligned_{pre}pre-{post}post/{plot_family}/{animal}/`. No
   eager mkdir (directory resolver, 7a.4 convention). Lowercase
   `tongue` / `jaw` per Q6; per-window subdirs per Q7.

5. [`tests/test_mean_sem_visual.py`](../tests/test_mean_sem_visual.py)
   — 118 unit tests covering: 6 plot family smoke tests at the
   public-API level (Q2 bodypart-parametric coverage); multi-bin
   `bin_sizes_days` resolution (Q4); `with_frame_timestamps` both
   branches (Q5); lowercase tongue path policy (Q6); per-window subdir
   layout (Q7); `_resolve_animation_writer` raise-vs-fallback truth
   table (C7.5); `_should_render_mean_video_for_window` predicate +
   `_resolve_mean_video_windows` precedence (C7.7);
   `TestC7{1,2,3,4}*` visual-fidelity pins for the 8 visual-gate
   atomic-fix commits.

6. [`tests/scripts/parity_phase7a6_mean_sem.py`](../tests/scripts/parity_phase7a6_mean_sem.py)
   — Phase-7a.6 parity harness, doubles as a cohort-emit runner. CLI
   flags: `--mode {default, legacy_approximate}`, `--bodyparts`,
   `--windows`, `--animals`, `--sessions`, `--emit-root`,
   `--report-path`, `--skip-mean-video`, `--skip-cohort-emit`,
   `--atol`, `--allow-gif-fallback` (C7.5), `--mean-video-windows`
   (C7.7). Emits a markdown parity report with per-(animal, bodypart,
   window) family file counts + ffmpeg fallback counts + deterministic-
   re-run results + per-(animal, date, bodypart) legacy NPZ comparison.

7. [`notebooks/12_dlc_kinematics_tongue.ipynb`](../notebooks/12_dlc_kinematics_tongue.ipynb)
   — 11 cells, full tongue pipeline (Phase 7a.2 → 7a.3 V3 → 7a.4 →
   7a.5 → 7a.6 per-session → 7a.6 cohort → summary). USER INPUTS
   surfaces 5 Phase 7a.6 knobs: `WINDOWS_MS`, `MEAN_VIDEO_WINDOWS_SUBSET`,
   `ALLOW_GIF_FALLBACK`, `INCLUDE_MEAN_VIDEO`, `BIN_SIZES_DAYS`.
   Smoke-tested on PS46 + 2025-03-07: PASS in 17.4 s.

8. [`notebooks/13_dlc_kinematics_jaw.ipynb`](../notebooks/13_dlc_kinematics_jaw.ipynb)
   — 9 cells, full jaw pipeline (7a.2 → 7a.5 jaw_pertrial → 7a.6
   per-session → 7a.6 cohort → summary). Same USER INPUTS knob set
   as nb13. No 7a.3 V3 / 7a.4 / mismatch cells (tongue-only).
   Smoke-tested on PS46 + 2025-03-07: PASS in 7.8 s.

9. [`environment.yml`](../environment.yml)
   — added `ffmpeg` to Core runtime deps (2026-05-02, C7.6 commit).
   Removed from the "Deliberately NOT included" excluded block at the
   end of the file. Conda-forge ffmpeg 8.1 backs matplotlib's
   `FFMpegWriter` for `mean_video` MP4 emission. **This phase makes
   ffmpeg a hard runtime requirement** for the mean_video family;
   `conda env update -n stroke_orofacial -f environment.yml` brings
   existing envs in line.

**Behavior diffs vs. legacy.**

- **Lowercase `tongue` directory** (Q6). Legacy cell 31 wrote to
  `mouse_Tongue_kinematics/` with capital T alongside `mouse_tongue_kinematics/`
  with lowercase t — the consolidated tree uses lowercase only,
  matching the 7a.3 V3 / 7a.4 convention.
- **Per-window subdirs** (Q7). Legacy tongue cell 31 wrote to a single
  flat `_tongue_kinematics/` directory regardless of window, allowing
  silent overwrite when both 100-1000ms and 500-5000ms ran for the
  same animal. Consolidated tree adopts jaw's
  `rewardAligned_{pre}pre-{post}post/...` per-window subdir layout
  uniformly.
- **mean_video consolidation** (Q5). Legacy tongue had two cells
  (cell 47 basic, cell 48 with frame timestamps); consolidated module
  has one entry point with `with_frame_timestamps: bool = True`
  default kwarg matching the jaw cell 34 + tongue cell 48 behavior.
- **Multi-bin tongue mean_trace** (Q4 + jaw cell 32 promotion).
  `bin_sizes_days: int | Sequence[int] | None` accepted on both
  bodyparts; tongue legacy cell 45 was single-bin only.
- **Cam-view L/R subplot ordering** (C7.2). All 4 two-panel L/R XY
  plots use cam-view (R-trials on figure left, L-trials on figure
  right) — matches tongue cell 45 + all 3 mean_video cells; jaw cell
  32 mean_trace's opposite order is overridden as a deliberate
  inconsistency-correction.
- **mean_video MP4 fallback semantics** (C7.5). Legacy emitted MP4
  via FFMpegWriter unconditionally and crashed if ffmpeg was missing.
  Consolidated module raises `RuntimeError` on missing ffmpeg by
  default (`allow_gif_fallback=False`); opt-in `True` activates the
  PillowWriter-based GIF degrade for dev/CI environments.

**Skipped legacy code (Q4 deliberate exclusions).**

- Tongue exploratory cells 34, 37, 40, 43 — `plt.show()`-only viewers
  with no saved outputs (~1,414L). Confirmed by Task 1 audit walk
  through every cell. Not ported.
- Tongue cell 43 PSD analysis — deferred to a future Phase 7a.x-PSD
  that bundles tongue 60-86 + jaw 43 + face PSD together (Q3).

**Parity scope + verdict.**

- Standing 14-session envelope from 7a.2 / 7a.3 / 7a.4 / 7a.5
  (PS46 × 3, PS51 × 1, PS54 × 4, PS55 × 5, plus PS47/48/49/50 with
  no eligible sessions in the canonical scope per `PARITY_SESSIONS_14`).
  PS54 / 2025-05-12 carries `skip_missing` (known data gap inheriting
  the 7a.1 / 7a.2 pattern).
- **Numerical parity (default mode):** 26/26 NPZ comparisons at Δ=0
  on `x_final` / `y_final` + reward indices, across all 14 sessions
  × both bodyparts. Bit-stable across all 8 C7.x atomic-fix commits.
- **Approximate parity (legacy_approximate mode):** atol=1e-6 PASS
  on per-frame x/y comparison across the same scope.
- **Determinism:** 16/16 (animal × bodypart × window) cohorts return
  `det=PASS` (max|Δ|=0 on re-run) on every parity run from C7.5
  onward.

**Visual gate verdict.** PASS Priya 2026-05-02 / 2026-05-03 across all
8 atomic-fix iterations (C7.1 through C7.8). Worst-case session
(PS51 2025-04-29 + 2025-04-30 — large bin count + tracks extending
into the L-subplot left margin) verified clean on the static PNG
mean_xy_overlays family and on the mean_video frame layout
(cumulative + dot modes, 100-1000ms window). PS46 / 2025-03-13 cohort
spot-check verified clean on tongue + jaw at the 100-1000ms window
across all 6 plot families.

**Sub-phase commits on the branch.** 11 commits total:
- `f316d31` (kickoff doc) `88d9df1` (state-doc refresh) — pre-Tasks-2-9.
- Tasks 2 (vendor), 3 (config + paths + tests scaffold), 4 (module
  ports C4.1 master + C4.2 mean_trace + C4.3 mean_video), 5 (test
  expansion), 6 (parity harness + cohort run), 7.1-7.8 (visual-gate
  iterations), 8 (notebooks 13 + 14).

**Notes for downstream phases.**

- `build_mean_sem_cohort` is the public composite the cohort-aggregation
  phase (Phase 7b) should call when it needs the per-animal cohort
  family outputs without re-implementing the per-window iteration.
- The C7.7 `mean_video_windows_subset` config knob ships with
  `[[100, 1000]]` as the project default; long-window mean_videos
  are NOT emitted by the production cohort run. Override at the CLI
  with `--mean-video-windows 100,1000:500,5000` if a future analysis
  needs both, or set the empty list / unset the key in defaults.yaml
  for "no gating" behavior.
- ffmpeg is now a hard runtime dep — fresh laptops setting up the
  env should run `conda env update -n stroke_orofacial -f environment.yml`
  before running notebooks 13/14.

---

## Phase 7a.4-orientation-fix — `xy_by_phase` cam-view L/R subplot flip

**Date:** 2026-05-03

**What was done:**

- Flipped `_plot_xy_by_phase` (Family 5) in
  `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` from legacy
  ordering (L-trials on figure left, R-trials on figure right) to
  cam-view ordering (R-trials on figure left, L-trials on figure
  right) via the explicit `side_to_ax = {"R": axes[0], "L": axes[1]}`
  mapping. Mirrors the 7a.6 C7.2 convention in
  `mean_sem_visual._plot_mean_xy_overlays`. ~10-line surgical change
  to one helper function; the remainder of `tongue_visual.py` is
  untouched, and the legacy pre-flip patch (the 4 other plot
  families, the comparison-grid renderer, the QC dir resolver) is
  bit-identical to Phase 7a.4.
- Added orientation pin test
  `test_xy_by_phase_uses_cam_view_subplot_ordering` in
  `tests/test_tongue_visual.py` — asserts
  `"R trials" in fig.axes[0].get_title()` and
  `"L trials" in fig.axes[1].get_title()` against the synthetic
  bundle. Locks the convention against silent regression.
- Refreshed comment on existing
  `test_xy_by_phase_returns_nonempty_figure` from "2 panels (L, R)"
  to "cam-view: R-trials on figure left, L-trials on figure right
  per Phase 7a.4-orientation-fix" so the full file reads
  consistently.
- Added DECISIONS 2026-05-03 entry codifying the cam-view convention
  + cross-reference to the 7a.6 C7.2 precedent + explicit note about
  the deliberate L/R divergence in
  `xy_by_phase_comparison.png` after the flip.

**Behavior differences vs. legacy:**

- `xy_by_phase.png` for every session emitted under
  `<pipeline_outputs>/dlc_kinematics/figures_qc/tongue/{animal}/
  {YYYYMMDD}/` will display R-trials on figure left and L-trials on
  figure right. Legacy notebook output (saved on MICROSCOPE under
  `*_anglePhase_XYphase_*.png`) remains L-trials on figure left;
  this is a *deliberate* divergence reflecting the cam-view
  convention adopted in 7a.6 C7.2. See DECISIONS 2026-05-03 entry
  for rationale.
- The consolidated-vs-legacy comparison grid
  (`xy_by_phase_comparison.png` under
  `figures_qc/tongue_comparison/{animal}/{YYYYMMDD}/`) will show
  panes with opposite L/R orientation by design; the comparison
  grid renderer (`render_comparison_grid`) is unchanged and tiles
  the two PNGs as-is.
- No numerical change. All data arrays (`x_geom`, `y_geom`, `phase`),
  colorbar, axis limits, and styling knobs are identical to 7a.4.
  Only the subplot indexing differs.
- Notebook 14 (`13_dlc_kinematics_jaw.ipynb`) is unaffected — the
  jaw notebook has no `_plot_xy_by_phase` analog (per the
  7a.3-jaw audit, jaw kinematics enters the visual pipeline only at
  the 7a.6 bodypart-parametric mean/SEM module). The flip applies
  to notebook 13 (`12_dlc_kinematics_tongue.ipynb`) only.

**Exit criteria met:**

- [x] `pytest tests/test_tongue_visual.py` green including the new
  orientation pin test.
- [x] Visual gate verdict PASS (Priya 2026-05-03) on
  PS50/2025-03-19 against legacy MICROSCOPE
  `*_anglePhase_XYphase_*.png`.
- [x] DECISIONS 2026-05-03 entry codifies the convention + cites
  7a.6 C7.2 precedent.

**Closes:** task #41 (cam-view flip follow-up surfaced 2026-05-02
during Phase 7a.6 close-out).

**Tag:** `v7a.4-orientation-fix-cam-view-flip` on the merge commit.

---

## Phase 7a.4-paths-cleanup — `figures_qc/` retirement + comparison-grid renderer deletion + tongue-jaw mismatch cross-session wired into notebook 13

**Date:** 2026-05-03

**What was done:**

1. **Three resolver renames** in `src/stroke_orofacial/paths.py`,
   retiring the `figures_qc/` subtree:
   - `tongue_visual_qc_dir(animal, date)` → `tongue_angle_dir(animal, date)`,
     path `dlc_kinematics/figures_qc/tongue/...` →
     `dlc_kinematics/tongue_angle/...`
   - `tongue_visual_comparison_dir(animal, date)` — **DELETED**
     entirely (no callers remain after #2).
   - `tongue_jaw_mismatch_qc_dir(animal, date)` →
     `tongue_jaw_mismatch_within_session_dir(animal, date)`, path
     `tongue_jaw_mismatch/figures_qc/...` →
     `tongue_jaw_mismatch/within_session/...` (symmetric with the
     existing `cross_session/` sibling).

   Resolvers carry docstring history notes citing the
   2026-05-03 DECISIONS entry.
2. **Comparison-grid renderer + helpers deleted** from
   `tongue_visual.py`: `render_comparison_grid` function +
   `_resolve_legacy_png_path` + `_save_comparison_grid` helpers +
   `_LEGACY_SUFFIX` dict + `mpimg` import (no remaining users).
   Removed `render_comparison_grid` re-export from
   `src/stroke_orofacial/dlc_kinematics/__init__.py` (both
   `from ... import` line and `__all__` entry). Module docstring
   carries history note pointing at git tag
   `v7a.4-tongue-visual-and-day-binned` for future re-derivation
   if needed.
3. **Tongue-jaw mismatch within-session call-site updates** in
   `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`:
   `qc_dir` local var renamed → `within_session_dir`; resolver call
   updated to `tongue_jaw_mismatch_within_session_dir`; module-
   header docstring path example updated. The per-trial
   `jaw_pass_qc` boolean field is unaffected (domain vocabulary,
   not a directory name).
4. **Test updates** in `tests/test_paths.py` (renamed two tests +
   updated path assertions + refreshed class docstrings) and
   `tests/test_tongue_visual.py` (deleted `TestComparisonGrid`
   class + 3 tests; removed `render_comparison_grid` import).
5. **Visual-gate parity scripts deprecated.** Created
   `tests/scripts/_deprecated/README.md` documenting the rationale
   + frozen-artifact status. The scripts themselves
   (`parity_phase7a4_visual_gate.py`,
   `parity_phase7a5_visual_gate.py`) are moved via `git mv` from
   the CC terminal during the close-out sequence (sandbox-git
   boundary blocks me from running `git mv` directly).
6. **Tongue-jaw mismatch cross-session wired into notebook 13.**
   Updated `notebooks/12_dlc_kinematics_tongue.ipynb`:
   - Cell 1 USER INPUTS: added `INCLUDE_CROSS_SESSION_MISMATCH = True`
     gate + `OVERWRITE_CROSS_SESSION = None` per-cell overwrite
     override (None = inherit global `OVERWRITE`; "force" =
     regenerate cross-session without re-running per-session loops).
   - Cell 2 imports: added `render_cross_session_figures` to the
     `tongue_jaw_mismatch` import block.
   - New cell 8 (per-mouse cross-session loop): iterates `ANIMALS`,
     calls `render_cross_session_figures(animal, resolver,
     overwrite=overwrite_cs)`, prints `ok/skip/err` summary with
     resolved overwrite mode visible. Renders 2 PNGs per mouse:
     `{animal}_crossSessionOverlay2x2_jawBaselineSub.png` and
     `{animal}_crossSessionBinned2x2_bins{N}_jawBaselineSub.png`
     (where N comes from `animal_info.bin_days` in
     `configs/animals.yaml`). Pre-stroke = grey, post-stroke =
     plasma colormap by relative day; day-binning convention
     matches 7a.5 cross-session + 7a.6 mean/SEM cross-session
     precedents.
   - Notebook now has 12 cells (was 11).
7. **Mover script for existing on-disk PNGs** at
   `scripts/phase_7a/move_figures_qc_to_new_layout.py`. Idempotent;
   `--dry-run` default + `--execute` flag; refuses to clobber
   existing destinations; prunes empty parent dirs after moves.
   Handles three trees: (a) `figures_qc/tongue/` →
   `tongue_angle/`, (b) `tongue_jaw_mismatch/figures_qc/` →
   `tongue_jaw_mismatch/within_session/`, (c) typed-confirm DELETE
   of `figures_qc/tongue_comparison/` (gateable via
   `--keep-comparison`).
8. **Forward-pointer kickoff doc** at
   `docs/prompts/phase-7a.4-cross-session-angle-kickoff.md` (~250
   lines) for a queued follow-up phase covering net-new cross-
   session aggregations of the tongue angle/phase families plus
   the per-session split of `phase_aligned_angle` into
   1st_lick/all_licks modes. Audit-first pattern; three outcome
   branches A/B/C; locks at Task 1.

**Behavior differences vs. legacy:**

- **Output paths for tongue angle PNGs and tongue-jaw mismatch
  within-session PNGs have moved.** Existing emitted PNGs at the
  old `figures_qc/...` locations remain untouched on disk
  (pre-cleanup runs); the mover script (#7 above) handles
  relocation. Future runs of `render_tongue_qc_figures` and
  `render_within_session_figures` write to the new paths.
- **`tongue_visual_comparison_dir` resolver no longer exists.**
  Code attempting to call it will fail with `AttributeError`. The
  comparison-grid renderer that consumed it is also deleted.
- **No numerical change anywhere.** All algorithm code, data
  arrays, file-level metadata, parquet schemas, and per-trial
  scalar values are bit-identical to 7a.6. This phase is purely
  layout / naming / dead-code-removal.
- **Notebook 13 cross-session mismatch loop is new** but uses
  unchanged `render_cross_session_figures` (already shipped in
  7a.5 / PR #88). Because the renderer was previously code-
  complete + tested but never invoked from any notebook, the new
  cross-session PNGs at
  `dlc_kinematics/tongue_jaw_mismatch/cross_session/{animal}/`
  are net-new production output streams.

**Exit criteria met:**

- [x] `pytest tests/test_paths.py tests/test_tongue_visual.py
  tests/test_tongue_jaw_mismatch.py -v` green (Priya 2026-05-03,
  including the new orientation pin test from PR #93).
- [x] Cross-session mismatch smoke run on PS46 via notebook 13
  (Priya iterating with `OVERWRITE_CROSS_SESSION = "force"`).
- [x] No live code references to deleted resolvers / renderers /
  exports. Only docstring history notes remain (deliberate).
- [x] DECISIONS 2026-05-03 entry codifies all 6 decisions enacted.

**Closes:**
- Implicit `figures_qc/` naming-debt item carried since 7a.4 → 7a.6.
- Cross-session-mismatch-not-wired-into-notebook-13 integration
  oversight from 7a.5.

**Forward-pointer queued:** Phase 7a.4-cross-session-angle (kickoff
doc landed in this phase at
`docs/prompts/phase-7a.4-cross-session-angle-kickoff.md`).

**Mover-script execution note.** The mover at
`scripts/phase_7a/move_figures_qc_to_new_layout.py` has NOT been
run as part of this phase merge. Existing `figures_qc/...` PNGs on
MICROSCOPE remain at the old paths; future renderer runs write to
the new paths. Run the mover (`python
scripts/phase_7a/move_figures_qc_to_new_layout.py --execute`) at a
convenient time post-merge to relocate historical artifacts and
unify the tree.

**Tag:** `v7a.4-paths-cleanup` on the merge commit.

---

## Phase 7a.4-paths-cleanup — `figures_qc/` retirement + comparison-grid renderer deletion + tongue-jaw mismatch cross-session wired into notebook 13

**Date:** 2026-05-03

**What was done:**

1. **Three resolver renames** in `src/stroke_orofacial/paths.py`,
   retiring the `figures_qc/` subtree:
   - `tongue_visual_qc_dir(animal, date)` → `tongue_angle_dir(animal, date)`,
     path `dlc_kinematics/figures_qc/tongue/...` →
     `dlc_kinematics/tongue_angle/...`
   - `tongue_visual_comparison_dir(animal, date)` — **DELETED**
     entirely (no callers remain after #2).
   - `tongue_jaw_mismatch_qc_dir(animal, date)` →
     `tongue_jaw_mismatch_within_session_dir(animal, date)`, path
     `tongue_jaw_mismatch/figures_qc/...` →
     `tongue_jaw_mismatch/within_session/...` (symmetric with the
     existing `cross_session/` sibling).

   Resolvers carry docstring history notes citing the
   2026-05-03 DECISIONS entry.
2. **Comparison-grid renderer + helpers deleted** from
   `tongue_visual.py`: `render_comparison_grid` function +
   `_resolve_legacy_png_path` + `_save_comparison_grid` helpers +
   `_LEGACY_SUFFIX` dict + `mpimg` import (no remaining users).
   Removed `render_comparison_grid` re-export from
   `src/stroke_orofacial/dlc_kinematics/__init__.py` (both
   `from ... import` line and `__all__` entry). Module docstring
   carries history note pointing at git tag
   `v7a.4-tongue-visual-and-day-binned` for future re-derivation
   if needed.
3. **Tongue-jaw mismatch within-session call-site updates** in
   `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`:
   `qc_dir` local var renamed → `within_session_dir`; resolver call
   updated to `tongue_jaw_mismatch_within_session_dir`; module-
   header docstring path example updated. The per-trial
   `jaw_pass_qc` boolean field is unaffected (domain vocabulary,
   not a directory name).
4. **Test updates** in `tests/test_paths.py` (renamed two tests +
   updated path assertions + refreshed class docstrings) and
   `tests/test_tongue_visual.py` (deleted `TestComparisonGrid`
   class + 3 tests; removed `render_comparison_grid` import).
5. **Visual-gate parity scripts deprecated.** Created
   `tests/scripts/_deprecated/README.md` documenting the rationale
   + frozen-artifact status. The scripts themselves
   (`parity_phase7a4_visual_gate.py`,
   `parity_phase7a5_visual_gate.py`) are moved via `git mv` from
   the CC terminal during the close-out sequence (sandbox-git
   boundary blocks me from running `git mv` directly).
6. **Tongue-jaw mismatch cross-session wired into notebook 13.**
   Updated `notebooks/12_dlc_kinematics_tongue.ipynb`:
   - Cell 1 USER INPUTS: added `INCLUDE_CROSS_SESSION_MISMATCH = True`
     gate + `OVERWRITE_CROSS_SESSION = None` per-cell overwrite
     override (None = inherit global `OVERWRITE`; "force" =
     regenerate cross-session without re-running per-session loops).
   - Cell 2 imports: added `render_cross_session_figures` to the
     `tongue_jaw_mismatch` import block.
   - New cell 8 (per-mouse cross-session loop): iterates `ANIMALS`,
     calls `render_cross_session_figures(animal, resolver,
     overwrite=overwrite_cs)`, prints `ok/skip/err` summary with
     resolved overwrite mode visible. Renders 2 PNGs per mouse:
     `{animal}_crossSessionOverlay2x2_jawBaselineSub.png` and
     `{animal}_crossSessionBinned2x2_bins{N}_jawBaselineSub.png`
     (where N comes from `animal_info.bin_days` in
     `configs/animals.yaml`). Pre-stroke = grey, post-stroke =
     plasma colormap by relative day; day-binning convention
     matches 7a.5 cross-session + 7a.6 mean/SEM cross-session
     precedents.
   - Notebook now has 12 cells (was 11).
7. **Mover script for existing on-disk PNGs** at
   `scripts/phase_7a/move_figures_qc_to_new_layout.py`. Idempotent;
   `--dry-run` default + `--execute` flag; refuses to clobber
   existing destinations; prunes empty parent dirs after moves.
   Handles three trees: (a) `figures_qc/tongue/` →
   `tongue_angle/`, (b) `tongue_jaw_mismatch/figures_qc/` →
   `tongue_jaw_mismatch/within_session/`, (c) typed-confirm DELETE
   of `figures_qc/tongue_comparison/` (gateable via
   `--keep-comparison`).
8. **Forward-pointer kickoff doc** at
   `docs/prompts/phase-7a.4-cross-session-angle-kickoff.md` (~250
   lines) for a queued follow-up phase covering net-new cross-
   session aggregations of the tongue angle/phase families plus
   the per-session split of `phase_aligned_angle` into
   1st_lick/all_licks modes. Audit-first pattern; three outcome
   branches A/B/C; locks at Task 1.

**Behavior differences vs. legacy:**

- **Output paths for tongue angle PNGs and tongue-jaw mismatch
  within-session PNGs have moved.** Existing emitted PNGs at the
  old `figures_qc/...` locations remain untouched on disk
  (pre-cleanup runs); the mover script (#7 above) handles
  relocation. Future runs of `render_tongue_qc_figures` and
  `render_within_session_figures` write to the new paths.
- **`tongue_visual_comparison_dir` resolver no longer exists.**
  Code attempting to call it will fail with `AttributeError`. The
  comparison-grid renderer that consumed it is also deleted.
- **No numerical change anywhere.** All algorithm code, data
  arrays, file-level metadata, parquet schemas, and per-trial
  scalar values are bit-identical to 7a.6. This phase is purely
  layout / naming / dead-code-removal.
- **Notebook 13 cross-session mismatch loop is new** but uses
  unchanged `render_cross_session_figures` (already shipped in
  7a.5 / PR #88). Because the renderer was previously code-
  complete + tested but never invoked from any notebook, the new
  cross-session PNGs at
  `dlc_kinematics/tongue_jaw_mismatch/cross_session/{animal}/`
  are net-new production output streams.

**Exit criteria met:**

- [x] `pytest tests/test_paths.py tests/test_tongue_visual.py
  tests/test_tongue_jaw_mismatch.py -v` green (Priya 2026-05-03,
  including the new orientation pin test from PR #93).
- [x] Cross-session mismatch smoke run on PS46 via notebook 13
  (Priya iterating with `OVERWRITE_CROSS_SESSION = "force"`).
- [x] No live code references to deleted resolvers / renderers /
  exports. Only docstring history notes remain (deliberate).
- [x] DECISIONS 2026-05-03 entry codifies all 6 decisions enacted
  + cites 7a.6 (mean_sem path layout), 7a.5 (cross-session
  precedent), and PR #93 (orientation flip) precedents.

**Closes:**
- Implicit `figures_qc/` naming-debt item carried since 7a.4 → 7a.6.
- Cross-session-mismatch-not-wired-into-notebook-13 integration
  oversight from 7a.5.

**Forward-pointer queued:** Phase 7a.4-cross-session-angle (kickoff
doc landed in this phase at
`docs/prompts/phase-7a.4-cross-session-angle-kickoff.md`).

**Mover-script execution note.** The mover at
`scripts/phase_7a/move_figures_qc_to_new_layout.py` has NOT been
run as part of this phase merge. Existing `figures_qc/...` PNGs on
MICROSCOPE remain at the old paths; future renderer runs write to
the new paths. Run the mover (`python
scripts/phase_7a/move_figures_qc_to_new_layout.py --execute`) at a
convenient time post-merge to relocate historical artifacts and
unify the tree.

**Tag:** `v7a.4-paths-cleanup` on the merge commit.

---

## Phase 7a.4-paths-cleanup — `figures_qc/` retirement + comparison-grid renderer deletion + tongue-jaw mismatch cross-session wired into notebook 13

**Date:** 2026-05-03

**What was done:**

1. **Three resolver renames** in `src/stroke_orofacial/paths.py`,
   retiring the `figures_qc/` subtree:
   - `tongue_visual_qc_dir(animal, date)` → `tongue_angle_dir(animal, date)`,
     path `dlc_kinematics/figures_qc/tongue/...` →
     `dlc_kinematics/tongue_angle/...`
   - `tongue_visual_comparison_dir(animal, date)` — **DELETED**
     entirely (no callers remain after #2).
   - `tongue_jaw_mismatch_qc_dir(animal, date)` →
     `tongue_jaw_mismatch_within_session_dir(animal, date)`, path
     `tongue_jaw_mismatch/figures_qc/...` →
     `tongue_jaw_mismatch/within_session/...` (symmetric with the
     existing `cross_session/` sibling).

   Resolvers carry docstring history notes citing the
   2026-05-03 DECISIONS entry.
2. **Comparison-grid renderer + helpers deleted** from
   `tongue_visual.py`: `render_comparison_grid` function +
   `_resolve_legacy_png_path` + `_save_comparison_grid` helpers +
   `_LEGACY_SUFFIX` dict + `mpimg` import (no remaining users).
   Removed `render_comparison_grid` re-export from
   `src/stroke_orofacial/dlc_kinematics/__init__.py` (both
   `from ... import` line and `__all__` entry). Module docstring
   carries history note pointing at git tag
   `v7a.4-tongue-visual-and-day-binned` for future re-derivation
   if needed.
3. **Tongue-jaw mismatch within-session call-site updates** in
   `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`:
   `qc_dir` local var renamed → `within_session_dir`; resolver call
   updated to `tongue_jaw_mismatch_within_session_dir`; module-
   header docstring path example updated. The per-trial
   `jaw_pass_qc` boolean field is unaffected (domain vocabulary,
   not a directory name).
4. **Test updates** in `tests/test_paths.py` (renamed two tests +
   updated path assertions + refreshed class docstrings) and
   `tests/test_tongue_visual.py` (deleted `TestComparisonGrid`
   class + 3 tests; removed `render_comparison_grid` import).
5. **Visual-gate parity scripts deprecated.** Created
   `tests/scripts/_deprecated/README.md` documenting the rationale
   + frozen-artifact status. The scripts themselves
   (`parity_phase7a4_visual_gate.py`,
   `parity_phase7a5_visual_gate.py`) are moved via `git mv` from
   the CC terminal during the close-out sequence (sandbox-git
   boundary blocks me from running `git mv` directly).
6. **Tongue-jaw mismatch cross-session wired into notebook 13.**
   Updated `notebooks/12_dlc_kinematics_tongue.ipynb`:
   - Cell 1 USER INPUTS: added `INCLUDE_CROSS_SESSION_MISMATCH = True`
     gate + `OVERWRITE_CROSS_SESSION = None` per-cell overwrite
     override (None = inherit global `OVERWRITE`; "force" =
     regenerate cross-session without re-running per-session loops).
   - Cell 2 imports: added `render_cross_session_figures` to the
     `tongue_jaw_mismatch` import block.
   - New cell 8 (per-mouse cross-session loop): iterates `ANIMALS`,
     calls `render_cross_session_figures(animal, resolver,
     overwrite=overwrite_cs)`, prints `ok/skip/err` summary with
     resolved overwrite mode visible. Renders 2 PNGs per mouse:
     `{animal}_crossSessionOverlay2x2_jawBaselineSub.png` and
     `{animal}_crossSessionBinned2x2_bins{N}_jawBaselineSub.png`
     (where N comes from `animal_info.bin_days` in
     `configs/animals.yaml`). Pre-stroke = grey, post-stroke =
     plasma colormap by relative day; day-binning convention
     matches 7a.5 cross-session + 7a.6 mean/SEM cross-session
     precedents.
   - Notebook now has 12 cells (was 11).
7. **Mover script for existing on-disk PNGs** at
   `scripts/phase_7a/move_figures_qc_to_new_layout.py`. Idempotent;
   `--dry-run` default + `--execute` flag; refuses to clobber
   existing destinations; prunes empty parent dirs after moves.
   Handles three trees: (a) `figures_qc/tongue/` →
   `tongue_angle/`, (b) `tongue_jaw_mismatch/figures_qc/` →
   `tongue_jaw_mismatch/within_session/`, (c) typed-confirm DELETE
   of `figures_qc/tongue_comparison/` (gateable via
   `--keep-comparison`).
8. **Forward-pointer kickoff doc** at
   `docs/prompts/phase-7a.4-cross-session-angle-kickoff.md` (~250
   lines) for a queued follow-up phase covering net-new cross-
   session aggregations of the tongue angle/phase families plus
   the per-session split of `phase_aligned_angle` into
   1st_lick/all_licks modes. Audit-first pattern; three outcome
   branches A/B/C; locks at Task 1.

**Behavior differences vs. legacy:**

- **Output paths for tongue angle PNGs and tongue-jaw mismatch
  within-session PNGs have moved.** Existing emitted PNGs at the
  old `figures_qc/...` locations remain untouched on disk
  (pre-cleanup runs); the mover script (#7 above) handles
  relocation. Future runs of `render_tongue_qc_figures` and
  `render_within_session_figures` write to the new paths.
- **`tongue_visual_comparison_dir` resolver no longer exists.**
  Code attempting to call it will fail with `AttributeError`. The
  comparison-grid renderer that consumed it is also deleted.
- **No numerical change anywhere.** All algorithm code, data
  arrays, file-level metadata, parquet schemas, and per-trial
  scalar values are bit-identical to 7a.6. This phase is purely
  layout / naming / dead-code-removal.
- **Notebook 13 cross-session mismatch loop is new** but uses
  unchanged `render_cross_session_figures` (already shipped in
  7a.5 / PR #88). Because the renderer was previously code-
  complete + tested but never invoked from any notebook, the new
  cross-session PNGs at
  `dlc_kinematics/tongue_jaw_mismatch/cross_session/{animal}/`
  are net-new production output streams.

**Exit criteria met:**

- [x] `pytest tests/test_paths.py tests/test_tongue_visual.py
  tests/test_tongue_jaw_mismatch.py -v` green (Priya 2026-05-03,
  including the new orientation pin test from PR #93).
- [x] Cross-session mismatch smoke run on PS46 via notebook 13
  (Priya iterating with `OVERWRITE_CROSS_SESSION = "force"`).
- [x] No live code references to deleted resolvers / renderers /
  exports. Only docstring history notes remain (deliberate).
- [x] DECISIONS 2026-05-03 entry codifies all 6 decisions enacted.

**Closes:**
- Implicit `figures_qc/` naming-debt item carried since 7a.4 → 7a.6.
- Cross-session-mismatch-not-wired-into-notebook-13 integration
  oversight from 7a.5.

**Forward-pointer queued:** Phase 7a.4-cross-session-angle (kickoff
doc landed in this phase at
`docs/prompts/phase-7a.4-cross-session-angle-kickoff.md`).

**Mover-script execution note.** The mover at
`scripts/phase_7a/move_figures_qc_to_new_layout.py` has NOT been
run as part of this phase merge. Existing `figures_qc/...` PNGs on
MICROSCOPE remain at the old paths; future renderer runs write to
the new paths. Run the mover (`python
scripts/phase_7a/move_figures_qc_to_new_layout.py --execute`) at a
convenient time post-merge to relocate historical artifacts and
unify the tree.

**Tag:** `v7a.4-paths-cleanup` on the merge commit.

---

## Phase 7a.4-cross-session-angle — per-mouse cross-session aggregations of tongue angle/phase plot families + centered-on-peak phase convention + per-animal pre-stroke median ILI + d0=pre-stroke project-wide convention update

**Date:** 2026-05-04

**Legacy file disambiguation:** Net-new design phase; no legacy
counterpart in either reference notebook. The kickoff doc
(`docs/prompts/phase-7a.4-cross-session-angle-kickoff.md`,
landed in PR #94 / 7a.4-paths-cleanup) audit confirmed Outcome B
(substantial new design) per the standard 3-tier rule.

**What was done:**

1. **New module `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py`**
   (~1,886 LOC) housing per-mouse cross-session aggregations of
   the 6 tongue-angle plot families × 2 sub-variants
   (`session_overlays`, `binned_overlays`) = 12 PNGs per mouse,
   emitted to `dlc_kinematics/tongue_angle/cross_session/{animal}/`.
   Top-level composite driver `build_tongue_angle_cohort(animal,
   resolver, ...)` builds the cohort aggregates ONCE per animal
   (single per-session walk; one bundle build per session) and
   dispatches to all 4 family drivers via the `cohort=` kwarg —
   ~75% per-session walk savings vs. per-family driver calls.

2. **Per-session `phase_aligned_angle` split into 3 mode-suffixed
   PNGs** — `_1st_lick.png`, `_all_licks.png`,
   `_first_2_licks.png` (N from `phase_aligned_first_n_peaks`
   config, default 2). Bare `phase_aligned_angle.png` filename
   retired. `_first_vs_second_peak_scatter.png` family added per
   Addendum #11 Part B. Per-session emit count: 6 → 9 PNGs.

3. **Centered-on-peak phase convention** for `_1st_lick` and
   `_all_licks`. Each peak's cycle =
   `(peak_t - ILI/2, peak_t + ILI/2)`; phase in `[0, 1]` with
   peak at 0.5 by construction. Three new public helpers in
   `tongue_pertrial.py`:
   `build_first_lick_centered_phase_rows`,
   `build_all_licks_centered_phase_rows`,
   `build_first_n_licks_centered_phase_rows`. Shared core
   `_centered_phase_rows_from_peaks` iterates (peak_t, ILI)
   pairs.

4. **`ili_source` enum on the centered-phase helpers** with three
   modes:
   - `"real_only"`: legacy multi-bout-only (peaks without forward
     neighbour DROPPED).
   - `"hybrid"`: real ILI when available, synthetic median
     fallback for isolated / last-peak.
   - `"synthetic_only"` (DEFAULT, locked Addendum #15 after the
     3-way comparison verdict): every peak's cycle width = the
     synthetic median.

5. **Per-animal pre-stroke median multi-bout ILI** computed via
   `compute_pre_stroke_median_ili_ms` (cached in
   `_PRE_STROKE_MEDIAN_ILI_CACHE`); plumbed end-to-end as
   `bundle.metadata["pre_stroke_median_ili_ms"]` populated by
   `build_tongue_visual_bundle_by_animal_date`. Recursion guard:
   the median walker calls the lower-level
   `build_tongue_visual_bundle` with `pre_stroke_median_ili_ms=NaN`
   to avoid recursive cohort-scalar computation.
   `scripts/phase_7a/emit_cohort_for_pre_stroke_median.py` walked
   all 8 animals × all session dates with `overwrite="skip"`
   (45 minutes; 256 ok / 134 skip_missing / 5 skip_excluded) so
   every animal has the upstream parquet/JSON set required for
   the median to compute. Final per-animal medians (post-#17
   d0=pre filter):

   ```
   PS46:180  PS47:164  PS48:176  PS49:180  PS50:164
   PS51:160  PS54:156  PS55:168
   ```

6. **Per-cycle line segment rendering for multi-cycle plots**
   (Addendum #16). Each cycle drawn as an independent Line2D +
   fill_between; no line connecting cycle boundaries. Cycle-
   boundary axvlines lowered to `alpha=0.2` (faint eye-guide).
   Single-cycle plots unaffected.

7. **`reward_aligned` consumes `angle_snip` directly** (Addendum
   #8). Per-session and cross-session both read raw per-frame
   angle (populated for every frame in `plot_win_ms`) instead of
   the bout-windowed `angle_<mode>_snip` arrays. Bundle widening:
   `plot_win_ms` left edge `0 → -180` ms (Addendum #4); display
   clipping to `[-180, 1000]` via the new
   `reward_aligned_display_window_ms` config knob.
   `dlc_kinematics.tongue_visual.modes.time_summary` is now
   INTENTIONALLY UNUSED (documentation-only default
   `"all_bouts"`).

8. **Output path restructure** (Addendum #17 item 5):
   - `dlc_kinematics/tongue_angle/{animal}/{date}/...` →
     `dlc_kinematics/tongue_angle/within_session/{animal}/{date}/...`
   - `dlc_kinematics/tongue_angle_cohort/{animal}/...` →
     `dlc_kinematics/tongue_angle/cross_session/{animal}/...`

   Resolver renames in `paths.py`:
   `tongue_angle_dir → tongue_angle_within_session_dir`;
   `tongue_angle_cohort_dir → tongue_angle_cross_session_dir`.
   Mirrors the `tongue_jaw_mismatch/{within_session,
   cross_session}/` layout (Phase 7a.4-paths-cleanup,
   2026-05-03).

9. **`d0 = pre-stroke` project-wide convention update**
   (Addendum #17 item 1). Pre-stroke filter changed from
   `rel_day < 0` to `rel_day <= 0` in
   `compute_pre_stroke_median_ili_ms`. Pre-stroke binning anchored
   to d0 (last pre-stroke bin = `(-(B-1), 0)`); aligns with the
   legacy `_day_binned._compute_rel_day_bin_label` convention.

10. **Cohort plot conventions** (Addendum #17 items 3 + 4):
    - Cam-view L/R subplot ordering throughout
      (`side_to_ax = {"R": axes[0], "L": axes[1]}`).
    - Shared right-margin legend
      (`subplots_adjust(right=0.80)`); no per-axis legends.
      `session_overlays`: grey Patch (pre-stroke d≤0) + vertical
      plasma colorbar (post-stroke). `binned_overlays`: textual
      figure-level legend, one entry per bin.
    - Lowered line/SEM alphas: knobs renamed
      `line_alpha → alpha_mean`, `sem_fill_alpha → alpha_sem`;
      `session_overlays` 0.85→0.50 + 0.10→0.05;
      `binned_overlays` 0.85→0.70 + 0.20→0.10.

11. **Notebook 13 wire-up.** New cell 9 per-mouse loop calling
    `build_tongue_angle_cohort` mirrors the cell 8 cross-session
    mismatch shape (locked symmetry with 7a.4-paths-cleanup).
    Cell 1 USER INPUTS gain `INCLUDE_TONGUE_ANGLE_COHORT = True`
    + `OVERWRITE_TONGUE_ANGLE_COHORT = None`. Cell 2 imports gain
    `build_tongue_angle_cohort`. Notebook now has 13 cells
    (was 12).

12. **One-shot mover script** at
    `scripts/phase_7a/move_tongue_angle_to_subdirs.py` (idempotent,
    `--dry-run` default, `--execute` flag) for relocating existing
    on-disk PNGs to the new `within_session/` + `cross_session/`
    layout. Same pattern as the 7a.4-paths-cleanup mover. NOT
    executed as part of this phase merge.

13. **Incidental polish** (Addendum #7 / commit `21448cc`):
    trimmed the `(candidates: X/Y)` parenthetical from the
    tongue-jaw mismatch non-candidate panel subtitle to match the
    candidate panel's terse convention. Cross-session subtitle
    format unaffected.

14. **Eye-midpoint convention LOCKED to per-eye-median-then-midpoint**
    (Addendum #18, docs-only — no code change). Investigation into
    a 6° (legacy) vs. 4° (consolidated) peak-angle discrepancy
    traced to a divergence between legacy
    `_estimate_session_eye_midpoint`
    (`docs/legacy_snippets/tongue_pertrial_features.py:4171`,
    per-frame midpoint THEN `nanmedian` across frames in the
    both-eyes default path) and consolidated
    `_compute_eye_in_spout_frame`
    (`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:1635-1641`,
    per-eye median THEN midpoint, uniform across both default and
    one-eye-only fallback paths). Locked decision: keep
    consolidated default — per-eye median is more robust to
    per-frame head-pose noise. See DECISIONS 2026-05-04 entry
    Decision 15 for the full rationale.

**Behavior differences vs. legacy:**

- **`d0` is now treated as pre-stroke project-wide.** The legacy
  notebook's loose convention sometimes filtered `rel_day < 0`
  for "pre-stroke" — now uniformly `rel_day <= 0`. Numerical
  effect on per-animal pre-stroke median ILI is minor (max drift
  PS51 156 → 160 ms, 2.6%); tight clustering preserved across
  all 8 animals.
- **Per-session phase plot count: 6 → 9 PNGs** (3 mode-suffixed
  phase variants + first_vs_second_peak_scatter family added).
  Existing `phase_aligned_angle.png` filename retired; callers
  consuming the bare path will break.
- **Centered-on-peak phase convention diverges from the legacy
  peak-to-peak-shifted convention** for `_1st_lick` and
  `_all_licks`. Bundle's `df_phase` still carries the legacy
  shifted column for any external consumer; no production
  renderer reads it after Addendum #10.
- **Cross-session reward_aligned reads `angle_snip` directly**
  (no bout-mode dispatch). Per-session reward_aligned changed
  to match. The `time_summary` config knob is documentation-only
  now.
- **Cohort `binned_overlays` use a single pre-stroke bin** by
  pre-`d0`-update logic; under #17 the pre-stroke pool now
  includes `rel_day == 0`. Post-stroke bins follow
  `animal_info.bin_days` (PS46-50: 2; PS51/54/55: 7).
- **No numerical change to existing per-session scalar parquets
  or jaw-mismatch outputs.** All changes scoped to: tongue-
  angle cohort module (new), centered-phase helpers (new),
  reward_aligned data source (new column read), pre-stroke
  median (new helper).
- **Tongue-angle values systematically differ from legacy by
  ~1-3° at peaks** (Addendum #18). The consolidated
  `_compute_eye_in_spout_frame` uses per-eye-median-then-midpoint
  uniformly; legacy `_estimate_session_eye_midpoint` used
  per-frame-midpoint-then-median in its both-eyes default path.
  Magnitude depends on per-session head-pose stability; the
  consolidated convention is locked as the canonical
  implementation (DECISIONS 2026-05-04 Decision 15). Any
  cross-cohort analysis comparing consolidated to legacy outputs
  must account for this systematic offset.

**Visual gate verdict.** Priya PASS 2026-05-04 on the full 36-PNG
cohort: 12 PNGs × 3 mice (PS46, PS50, PS55) emitted in 8.8 min via
the composite driver path. Per-session intermediate gates also
PASSED (all 9 per-session PNG variants on PS46/2025-03-07,
PS50/2025-03-19, PS55/2025-06-07).

**Exit criteria met:**

- [x] `pytest tests/` green: 868 passed, 38 skipped on the final
  cohort-merge baseline (vs. ~810 baseline before phase start).
- [x] Visual gate PASS on the full 36-PNG cohort.
- [x] Per-animal pre-stroke median ILI computed for all 8 animals
  via the cohort-wide upstream emit (Addendum #13).
- [x] DECISIONS 2026-05-04 entry consolidates Addenda #1-#17 +
  cross-session sub-commits #2-#7 into one PR-close record.

**Mover-script execution note.** The mover at
`scripts/phase_7a/move_tongue_angle_to_subdirs.py` has NOT been
run as part of this phase merge. Any existing on-disk PNGs at the
old `tongue_angle/{animal}/{date}/` and
`tongue_angle_cohort/{animal}/` paths remain untouched on disk;
future renderer runs write to the new
`within_session/` + `cross_session/` paths. Run the mover
(`python scripts/phase_7a/move_tongue_angle_to_subdirs.py
--execute`) at a convenient time post-merge to unify the tree.

**Tag:** `v7a.4-cross-session-angle` on the merge commit.

---

## Phase 7-pre-multi-half — PS48 2025-03-14 multi-half acquisition port (Architecture X + three-layer write-guard)

**Date:** 2026-05-12
**PR:** #99
**Tag on merge:** `v7-pre-multi-half`
**Branch:** `phase/7-pre-multi-half`

**Scope.** Port the PS48 2025-03-14 multi-half acquisition (one logical session split across two acquisition halves because the recording was paused and resumed) into the consolidated pipeline. Dual deliverable: (a) Architecture X — three coordinated merge functions for the licks NPZ / alignment template / centered DLC parquet artifact layers, faithful ports of canonical tongue notebook cells 13 / 16 / 17; (b) three-layer write-guard system shipped after a 2026-05-05 test-fixture incident overwrote three legacy MICROSCOPE alignment templates with synthetic toy data. Pattern A only (1 session in scope); Pattern B closer-spout sessions deferred to a future Phase 7-pre-secondary-spout per Decision 4 of the DECISIONS phase-close entry.

**What landed.**

1. [`src/stroke_orofacial/spout_behavior/multi_half_merge.py`](../src/stroke_orofacial/spout_behavior/multi_half_merge.py) — net-new module (~880L) with the three Architecture X merge functions:
   - `merge_licks_and_rewards(per_half_npz_paths, output_path, *, index_space, ...)` — cell 17 port with new `index_space: Literal["cam_frame", "ws_sample"]` parameter. cam_frame default preserves legacy behavior; ws_sample applies the semantically correct offset (`n_samples_A`) to half-B and emits the new provenance schema (drops misnomer `merged_n_cam_*`, `cam_frame_offset_for_B`, vestigial `allow_pickle`; adds `merged_n_samples_A/B`, `ws_sample_offset_for_B`). Side-convention stamps validated + carried forward.
   - `merge_alignment_templates(per_half_npz_paths, output_path)` — cell 16 port. Concatenates `sig_wsIdx__idx_cam` / `sig_camIdx__idx_ws` / `sig_camTimes__idx_cam` / `sig_wsTimes__idx_ws` with cumulative offsets + time-axis shifts. Monotonicity check raises (legacy printed).
   - `merge_centered_parquet(per_half_parquet_paths, output_path, *, compression)` — cell 13 port. `pd.concat(axis=0, ignore_index=True)` with column-set + order parity check.
   - Generalized helpers: `_infer_n_count` (renamed from `_infer_n_cam`, adds `fallback_min_size` param), `_looks_like_index_array` (renamed from `_looks_like_frame_indices`), `_validate_side_convention_stamps` (new).

2. [`src/stroke_orofacial/manifest.py`](../src/stroke_orofacial/manifest.py) — `HalfSpec` dataclass (id, ws_subdir, cam_subdir, file_timestamp, wavesurfer_file, dlc_h5_file) + `halves: list[HalfSpec] | None` field on `SessionManifest` + `MultiHalfNotDeclaredError` raised by `build_manifest()` when `n_dlc >= n_dlc_min=2` for an (animal, date) pair NOT covered by a `multi_half_sessions:` entry.

3. [`src/stroke_orofacial/spout_behavior/session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py) — `process_session_multi_half` per-half loop. Per-half licks NPZs emit under `pipeline_outputs/spout_behavior/licks_and_rewards/{animal}/{date}{halves_concat_label}/{date}{half_id}.npz`.

4. [`src/stroke_orofacial/alignment/timebase.py`](../src/stroke_orofacial/alignment/timebase.py) — `compute_and_merge_alignment_multi_half` orchestrator + `_compute_per_half_alignment_template` per-half compute. Routes ALL writes through `_new` resolvers; calls `assert_safe_write_path` inline before each `np.savez_compressed` (defense in depth).

5. [`src/stroke_orofacial/dlc_io/parquet.py`](../src/stroke_orofacial/dlc_io/parquet.py) — `_build_centered_parquet_multi_half` per-half loop. Per-half centered parquets emit under `pipeline_outputs/dlc_analysis/centered_{mode}/{animal}/{date}{halves_concat_label}/{video2_...}.intermediate.{sig}.parquet`.

6. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — resolver split (Layer 1 write-guard): `alignment_template_legacy_read` (read-only, routes through `microscope_server`) + `alignment_template_new` (write, routes through `pipeline_outputs("dlc_analysis")`) + `alignment_template_per_half_new` (write, per-half subdir layout). Existing `alignment_template()` removed — the writable-legacy-path API endpoint is deleted entirely.

7. [`src/stroke_orofacial/_writeguard.py`](../src/stroke_orofacial/_writeguard.py) — net-new module (Layer 2 write-guard). `assert_safe_write_path(path) -> None` raises `WriteGuardError` when `path` resolves under a known-legacy MICROSCOPE / Mac source-data root.

8. [`tests/conftest.py`](../tests/conftest.py) — autouse session fixture (Layer 3 write-guard) monkey-patches `np.savez`, `np.savez_compressed`, `pd.DataFrame.to_parquet`, `Path.write_text`, `Path.write_bytes`, `Path.replace` to call `assert_safe_write_path` on the destination before delegating.

9. [`configs/defaults.yaml`](../configs/defaults.yaml) — new `multi_half:` block (cam_count_keys, cam_count_int_keys, scan_signals.n_dlc_min).

10. [`configs/session_overrides.yaml`](../configs/session_overrides.yaml) — `multi_half_sessions:` registry with PS48 20250314 entry (halves = a + b with ws_subdir + cam_subdir + file_timestamp).

11. [`scripts/phase_7_pre/scan_multi_half.py`](../scripts/phase_7_pre/scan_multi_half.py) — cohort-wide read-only Pattern A scan (Task 7). Emitted `docs/phase-7-pre/multi_half_scan_results.md` and per-(animal, date) YAML stubs.

12. [`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`](../scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py) — one-off cam2-scoped restore CLI invoked 2026-05-09 to regenerate the three corrupted alignment templates. Documented exception to the writeguard system; not on any pipeline path.

13. [`tests/test_multi_half_merge.py`](../tests/test_multi_half_merge.py) — 87 tests covering: `TestInferNCount` (cam-mode + ws-mode tier-1/2/3 walk-through, ws-mode Tier-3 disable), `TestLooksLikeIndexArray` (10 heuristic edge-cases), `TestShiftFrameIndices`, `TestLicksAndRewardsMerge` (13 tests — cam_frame default + N=2 + N=3 + provenance schema + index-space-default + invalid-index-space-raises), **`TestLicksAndRewardsMergeWsSample`** (10 tests — offset applied, no-overlap, total-count, Tone forward, stamp validation + carry-forward, mismatch raises, missing-key raises, provenance schema, n_samples inference failure, ws_count_int_keys kwarg override), `TestAlignmentTemplateMerge` (N=2 offset semantics + N=2 time-axis continuity + N=2 legacy provenance + N=3 extension + Fs mismatch raises + missing REQ_KEY raises + non-monotonic camTimes raises + NaN preserved), `TestCenteredParquetMerge` (N=2 + N=3 + column mismatch raises + column-order mismatch raises + compression kwarg), `TestComputeAndMergeAlignmentMultiHalf` (3 tests — pre-existing per-half skip + Decision 3 subdir layout + force_recompute).

14. [`tests/test_writeguard.py`](../tests/test_writeguard.py) — 36 tests for `_writeguard.py` module coverage (Windows UNC + Mac POSIX deny-list, `pipeline_outputs` allowed, edge cases like `..` resolution).

15. [`tests/test_conftest_guard.py`](../tests/test_conftest_guard.py) — 13 sentinel tests pinning the autouse fixture (every patched API targeted at a canonical legacy UNC path asserts `WriteGuardError`; companion tests confirm `tmp_path` writes pass through).

16. [`tests/test_paths.py`](../tests/test_paths.py) — `_legacy_read` + `_new` resolver tests including `test_alignment_template_new_honors_output_root` regression guard (the test that would have caught the 2026-05-05 incident class).

17. [`tests/integration/test_multi_half_integration.py`](../tests/integration/test_multi_half_integration.py) — end-to-end 2-half + 3-half integration on synthetic NPZ + parquet fixtures exercising all three merge functions together.

18. [`tests/scripts/parity_phase7_pre_multi_half.py`](../tests/scripts/parity_phase7_pre_multi_half.py) — net-new 3-layer live parity gate harness (~1,150L). Layer 1 (licks NPZ structural + offset-correctness with side-aware count parity via `lr_convention.to_mouse_frame`), Layer 2 (alignment template `atol=1e-12` + numeric provenance exact + path-string INFO), Layer 3 (centered parquets `atol=1e-12` byte-equal + merged row count consistency). Skip-no-legacy semantics per layer.

19. [`.githooks/pre-push`](../.githooks/pre-push) — pre-push smoke gate added 2026-05-09 (origin: separate 2026-05-05 timebase.py corruption incident). Runs `python -c "import stroke_orofacial"` + `pytest --collect-only -q` on `phase/*` and `main` branches.

20. [`docs/legacy_snippets/multi_half_merge/`](legacy_snippets/multi_half_merge/) — byte-identical vendored cells 13 / 14 / 15 / 16 / 17 from the canonical tongue notebook (SHA256 `ed12c54...`) with per-cell SHA256s in headers.

21. [`docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv`](phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv) — pre-run on-disk state for the restore audit trail.

22. DECISIONS entry + this MIGRATION_LOG entry + COWORK_SESSION_STATE refresh.

**Task 9 parity verdict (2026-05-12 live run on MICROSCOPE).** All 3 layers PASS, exit code 0:

| Layer | Status | Detail |
|---|---|---|
| 1 — licks NPZ | PASS | 6 structural checks green; INFO surfacing convention decision + 2 path-string divergences (resolver-split expected) |
| 2 — alignment template | PASS | `atol=1e-12` on all 4 sig_* arrays (~1.15M ws-samples × 286,628 cam-frames); numeric provenance exact; 2 INFO path lines |
| 3 — centered parquets | PASS | `atol=1e-12` across 39 cols × 1,148,512 rows × 2 halves (~44M cell comparisons); merged row count consistent |

Verdict log archived at `.scratch_phase_7_pre/parity_run_20260512T093103.log`.

**Task 5R restore outcome (2026-05-09 14:27 UTC, layered Tier A/B/C PASS).** Three corrupted alignment templates regenerated within ±0.005% of pre-incident sizes (`cam2/PS48/20250314.npz` +0.0031%; per-halves -0.0004% each). Tier A relaxed to ±0.1% PASS / ±5% WARN to accommodate documented scipy 1.15.1 → 1.17.1 drift in Y0 retune (Phase 7a.0 baseline-seed-probe finding).

**Intentional behavior differences vs. legacy.**

- **Licks NPZ merged schema** (Decision 6 of DECISIONS entry): ws_sample mode applies offset = `n_samples_A` to half-B event-index arrays. Legacy cell-17 had no offset (emergent heuristic side-effect: `_looks_like_frame_indices` returned False on WS-sample arrays because max values >> n_cam_hint+5, falling through to events-concat without offset). New merged NPZ has half-A and half-B on a unified monotone-partitioned timeline; legacy had them in overlapping ranges with no separator. Provenance schema: drops `merged_n_cam_A/B` (misnomers), `cam_frame_offset_for_B` (never applied), `allow_pickle` (vestigial); adds `merged_n_samples_A/B`, `ws_sample_offset_for_B`. Carries `Tone_*` forward (legacy dropped them). Validates + carries side-convention stamps.
- **Alignment-template monotonicity check** raises instead of printing (cell 16 printed; this port follows the kickoff Task 1 "no silent failures" rule).
- **Side-convention stamps** present on every emitted licks NPZ (per `stroke_orofacial.lr_convention.stamp_side_convention` from Phase 6.8 task #17). Layer 1 parity comparator reads the stamp + translates side labels via `lr_convention.to_mouse_frame` when comparing counts against the pre-stamp legacy NPZ.

**Exit criteria met:**

- [x] `pytest tests/` green: 1024 passed, 38 skipped on the final cohort-merge baseline (vs. 868/38 at Phase 7a.4-cross-session-angle close; net +156 from the 7a.6 → 7-pre-multi-half arc).
- [x] Task 9 parity gate cleared all 3 layers at `atol=1e-12` (Layers 2/3) and structural + offset-correctness (Layer 1) on PS48 20250314.
- [x] All 3 corrupted alignment templates restored within ±0.005% of pre-incident sizes; structural Tier B + Tier C checks PASS; cam{1,3,4} per-halves at 2026-01-11 mtimes unchanged.
- [x] DECISIONS 2026-05-12 entry consolidates the three working-draft entries (2026-04-21 aspirational + two 2026-05-09 working drafts) into one phase-close record with explicit supersession notes.
- [x] Pattern B compatibility commitments documented forward (Decision 5) — session-id schema, `multi_half_sessions:` merge-intent-only constraint, defensive-check Pattern-B branch, Phase 2/3/4 manifest-opaque output separation.

**Forward-pointers queued for future phases:**

1. **Production wiring of `merge_licks_and_rewards`** into `process_session_multi_half`. The Layer 1 parity gate invokes the merge function directly (deferred from Task 4 per its commit message). Small follow-up commit on a fresh branch; trivial scope.
2. **Phase 7-pre-secondary-spout** — Pattern B closer-spout 2nd acquisition handling for the 19 PS51/PS54/PS55 sessions. Scope estimate ~mid-size comparable to this phase. Honors the four compatibility commitments from DECISIONS Decision 5.
3. **`bnpm` dependency rationalization** — restore script needs bnpm in the active env; current path relies on `frsb` env or one-off `pip install`. Either vendor more bnpm or add it as an optional install.
4. **Orphan cam{1,3,4}/PS48/20250314{a,b}.npz housekeeping** — six 2026-01-11 INTACT files at parent level. Out of scope; cam2 is canonical for the pipeline. Future cohort housekeeping decision: move into `20250314ab/` subdirs for symmetry, or leave.

**Tag:** `v7-pre-multi-half` on the merge commit.

---

### Forward-pointer resolved: wire `merge_licks_and_rewards` into `process_session` multi-half

**Date:** 2026-05-12
**Branch:** `feat/wire-merge-licks-and-rewards-into-process-session-multi-half`

Resolves forward-pointer #1 from the Phase 7-pre-multi-half entry above. The Task 9 parity harness invoked `merge_licks_and_rewards` directly after per-half processing; production `_process_session_multi_half` now does so itself. After the per-half loop, the per-half `licks_and_rewards` NPZs are merged into the parent-level `{date}.npz` via `merge_licks_and_rewards(per_half_paths, merged_path, index_space="ws_sample")` — half-B event indices shift by `n_samples_A` so the merged timeline is unified. Single-half code path unchanged (no merge invoked when `manifest.halves is None`). +1 unit test (`TestMergeWiring::test_merged_licks_npz_written_alongside_per_half`) verifies per-half + merged NPZs on disk with offset semantics. Sibling Phase 3 / Phase 4 merges remain out of scope; no tag.

---

## Phase 7-pre-secondary-spout — Pattern B closer-spout 2nd-acquisition handling for PS51/PS54/PS55 (19 sessions, Outcome A)

**Date:** 2026-05-12
**PR:** #105 (merge-commit `29324eb`)
**Tag on merge:** `v7-pre-secondary-spout`
**Branch:** `phase/7-pre-secondary-spout`

**Scope.** Wire the 19 Pattern B sessions across PS51/PS54/PS55 (where the second acquisition was run with closer-positioned water spouts) through Phase 2 (spout-behavior) + Phase 3 (alignment) as **separate logical sessions** per the four compatibility commitments locked by [Phase 7-pre-multi-half DECISIONS Decision 5](DECISIONS.md). Pre-PR, the `{DATE}b` half was silently dropped by single-half discovery; this phase implements `secondary_spout_sessions:` registry + `session_suffix` field threading + per-suffix driver iteration so both halves produce their own outputs. Task 1 audit returned **Outcome A — infrastructure-only**: legacy notebooks (`playground_analyze_behavior_report_PS20250610.ipynb` + `batch_process_behavior_report_20260116PS.ipynb`) omit `*b` dates from `include_dates`, so no bare-vs-b comparison code exists to port. Phase 4 (DLC) is forward-pointer-only.

**What landed.**

1. [`configs/session_overrides.yaml`](../configs/session_overrides.yaml) — new `secondary_spout_sessions:` block; 19 entries across PS51 (2) / PS54 (11) / PS55 (6); PS55/2025-04-24 carries `bare_ws_subdir_override: "20250424a"` for the asymmetric WS layout (richer per-session shape locked by Task 1 audit; legacy `include_dates` evidence ruled out implicit `{DATE}` → `{DATE}a` fallback rule).

2. [`src/stroke_orofacial/manifest.py`](../src/stroke_orofacial/manifest.py) — `SessionManifest.session_suffix: str | None = None` field; `build_manifest()` gains `session_suffix: str | None = None` kwarg + consumes `secondary_spout_sessions:` entry for bare/b WS+cam subdir override resolution; Pattern-B branch in `MultiHalfNotDeclaredError` defensive check (suppresses when registry covers `(animal, date)`); `iter_session_suffixes()` helper (returns `[None]` for non-Pattern-B / Pattern A, `[None, "b"]` for Pattern B); `load_secondary_spout_sessions()` + `get_secondary_spout_entry()` registry loaders + `OverlappingRegistryError` exception class + `_multi_half_date_str_as_iso()` private date-format reconciliation helper; `build_manifest`'s alignment-template discovery now threads `session_suffix` into `alignment_template_legacy_read` (Task 5.3 audit finding).

3. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `wavesurfer_dir` + `camera_dir` gain `subdir_override: str | None = None` kwarg (mutually exclusive with `half_subdir` — Pattern A vs Pattern B caller-intent at the same call site is a category error; raises `ValueError` if both passed); 10 per-session output resolvers gain `session_suffix: str | None = None` kwarg (filename construction appends suffix); `alignment_template_per_half_new` deliberately UNCHANGED — Pattern A multi-half-only resolver; passing `session_suffix=` raises `TypeError` (regression-pinned).

4. [`src/stroke_orofacial/spout_behavior/session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py) — `process_session_by_animal_date` + `process_animal` now iterate `iter_session_suffixes` and return `dict[str | None, dict[str, Path]]` / `list[dict[str | None, dict[str, Path]]]`. Partial-failure tolerance: per-suffix failure logs WARNING and continues; if ALL suffixes fail, re-raises the FIRST `FileNotFoundError`. `process_session`'s single-half branch uses caller-side `date_str_suffixed = date_str + (manifest.session_suffix or "")` for `_output_path` + `_save_session_params` calls (the **module-level free function path-suffix pattern**, parallel to Task 3c's resolver-kwarg pattern). `_save_session_params` reads `manifest.session_id` (Task 3d), so provenance JSONs carry the suffix.

5. [`src/stroke_orofacial/alignment/timebase.py`](../src/stroke_orofacial/alignment/timebase.py) — `load_or_compute_alignment_by_animal_date` iterates `iter_session_suffixes`, returns `dict[str | None, AlignmentResult]`, same partial-failure pattern (catches `(FileNotFoundError, RuntimeError)`). 3 cache-discovery / cam_dir-fallback sites inside `load_or_compute_alignment` threaded with `manifest.session_suffix` per the Task 5.1 audit. `load_or_compute_alignment` primary manifest-first entry SIGNATURE UNCHANGED — the parity harness at `tests/scripts/parity_phase7_pre_multi_half.py` (locked out of scope) continues to import + call this resolver cleanly.

6. [`tests/test_secondary_spout_registry.py`](../tests/test_secondary_spout_registry.py) — 25 tests covering registry loader, `iter_session_suffixes`, mutual-exclusion validation, override-key allowlist + typo detection, default-convention vs explicit-override semantics.

7. [`tests/test_manifest.py`](../tests/test_manifest.py) — `TestSessionSuffixField` (dataclass-level) + `TestBuildManifestSessionSuffix` (kwarg threading + Pattern-B defensive check + `session_suffix`-without-registry-entry guard; ~10 new tests on top of existing).

8. [`tests/test_paths.py`](../tests/test_paths.py) — `subdir_override` kwarg tests for `wavesurfer_dir` / `camera_dir` (fallback + mutual-exclusion) + per-resolver `session_suffix` tests for 10 output resolvers (suffix=None preserves pre-PR; suffix="b" appends "b") + `alignment_template_per_half_new_rejects_session_suffix` Pattern-A-boundary guard + `{wavesurfer_dir,camera_dir}_rejects_session_suffix` guards (13 new tests).

9. [`tests/test_session_processing.py`](../tests/test_session_processing.py) — 3 existing tests updated for the new `dict[str | None, dict[str, Path]]` return shape; new `test_session_id_inherits_suffix` (Task 3d regression guard).

10. [`tests/test_session_processing_secondary_spout.py`](../tests/test_session_processing_secondary_spout.py) — 10 tests covering Phase 2 driver per-suffix iteration + partial-failure (bare-missing / b-missing / both-missing) + PS55/2025-04-24 `bare_ws_subdir_override` consumption + Pattern A regression + provenance JSON session_id-suffix + lazy-load `overrides_config`.

11. [`tests/test_timebase.py`](../tests/test_timebase.py) — 2 existing integration tests updated for new return shape.

12. [`tests/test_timebase_secondary_spout.py`](../tests/test_timebase_secondary_spout.py) — 10 tests covering Phase 3 driver per-suffix iteration + cache-discovery `session_suffix` propagation (b-half cache hits its own NPZ, NOT the bare half's) + partial-failure + Pattern A unchanged + lazy-load.

13. [`tests/test_manifest_multi_half.py`](../tests/test_manifest_multi_half.py) — `_make_resolver_for_layout._ws_dir` / `_cam_dir` / `_alignment_template_legacy_read` fixture side_effects updated to accept the new `subdir_override` / `session_suffix` kwargs (mirroring the real resolver signatures). Without this fixture update, the Task 3b build_manifest changes broke the 15 multi-half tests at the resolver-mock boundary.

14. [`tests/test_parity_harness_secondary_spout.py`](../tests/test_parity_harness_secondary_spout.py) — 15 synthetic-fixture unit tests for the Layer 1 byte-identity comparator helpers (`_is_params_json`, `_is_bare_half_path`, `_compare_bare_half_byte_identity`). Catches comparator bugs without needing MICROSCOPE.

15. [`tests/scripts/parity_phase7_pre_secondary_spout.py`](../tests/scripts/parity_phase7_pre_secondary_spout.py) — 3-layer live parity harness (~870 lines). Forensic log + `_ForensicLog` tee-writer + exit-code-driven verdict + CLI argparse + per-layer skip semantics. Mirrors the multi-half harness structure.

16. DECISIONS 2026-05-12 entry (this commit, the entry above this MIGRATION_LOG section) + this MIGRATION_LOG entry + COWORK_SESSION_STATE refresh (Task 9).

**Task 6 parity verdict (live MICROSCOPE run 2026-05-12 16:40, re-run after Task 6e bug fixes).**

| Layer | Status | Detail |
|---|---|---|
| 1 — bare-half byte-identity | PASS | 18/19 sessions byte-equal vs Task 0.5 baselines (excluding `params/*.json` per Task 0.5 finding); **1 SPECIAL: PS55/2025-04-24** bare half now succeeds via `bare_ws_subdir_override` (expected divergence — baseline errored on missing `20250424` dir; post-PR resolves to `20250424a` per the registry entry). |
| 2 — b-half structural validation | PASS | 19/19 sessions × 8 files each (7 NPZs + 1 `params.json`); all required keys present, dtypes correct, Fs + side-convention stamps inherit from bare half, `session_id` ends in `b`. |
| 3 — defensive-check synthetic | PASS | 5/5 scenarios green (Pattern A iter_suffixes → [None]; Pattern B → [None, "b"]; overlapping registry raises; Pattern B suppresses defensive check; non-Pattern-B unchanged). |

Verdict log archived at `.scratch_phase_7_pre/parity_run_secondary_spout_rerun_20260512T164049.log` (gitignored — log is a runtime artifact). First-run log with the surfaced harness bugs preserved at `.scratch_phase_7_pre/parity_run_secondary_spout_full_20260512T163347.log` for reference.

**Task 0.5 chore-PR (#104) precondition.** Pre-PR baseline SHA256s for the 19 cohort sessions were captured against `main` HEAD `fe91569` (the kickoff PR #103 merge commit) BEFORE this feature branch existed. Baseline JSON at [`tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json`](../tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json). The baseline records 18 successful sessions + 1 errored (PS55/2025-04-24 — bare `{DATE}` dir not discovered pre-PR; this phase's `bare_ws_subdir_override` brings it into scope). `params/*.json` files are non-deterministic across runs (`run_timestamp` field); Layer 1 comparator excludes them.

**Intentional behavior differences vs pre-PR `main`.**

- **The b half of every Pattern B `(animal, date)` now flows through Phase 2 + Phase 3** instead of being discarded. No legacy artifact for the b half exists for comparison; Layer 2 structural validation only.
- **PS55/2025-04-24 bare half now succeeds** (was erroring on `main` pre-PR per Task 0.5 baseline). The `bare_ws_subdir_override: "20250424a"` registry entry brings the asymmetric WS subdir (`20250424a` for WS, `20250424` for cam — empirically confirmed by Task 1 audit's directory listing) into scope without an implicit fallback rule.
- **`process_session_by_animal_date` return shape changed** from `dict[str, Path]` to `dict[str | None, dict[str, Path]]`. Non-Pattern-B sessions return single-entry `{None: {...}}`. Decision validated by zero-callers audit on `process_animal` and update of 3 known test callers + 1 script caller (Task 0.5 baseline script; consumes only side effects, not return value).
- **`load_or_compute_alignment_by_animal_date` return shape changed** similarly to `dict[str | None, AlignmentResult]`. 2 existing integration tests in `test_timebase.py` updated.

**Exit criteria met.**

- [x] Task 6 Layer 1 byte-identity: 18 PASS + 1 SPECIAL (expected divergence) + 0 FAIL on the 19-session cohort.
- [x] Task 6 Layer 2 structural validation: 19/19 PASS (every b half emits 7 NPZs + 1 provenance JSON; structural checks green).
- [x] Task 6 Layer 3 synthetic: 5/5 scenarios PASS.
- [x] Full pytest suite green: **1164 passed, 38 skipped** (was 1091 passed at Phase 7-pre-multi-half-closeout-polish baseline; net +73 from this phase's new tests + the 7-pre-secondary-spout-baselines chore that landed Task 0.5).
- [x] DECISIONS 2026-05-12 entry (above) + this MIGRATION_LOG entry + state-doc refresh (Task 9).
- [x] Pattern A regression verified across multi_half_merge / writeguard / conftest_guard / integration/test_multi_half_integration / test_session_processing_multi_half — **152/152 PASS** through every sub-task.

**Forward-pointers queued for future phases.**

1. **Phase 7-pre-secondary-spout-compare-DLC.** Lands after Priya DLC-infers the 19 b-half cam dirs. Wires Phase 4 (centered parquet) to produce b-half outputs per the same `session_suffix="b"` convention; ports bare-vs-b DLC cross-session comparison analyses (the kinematics-side counterpart to the spout-behavior comparison folded into Phase 8a.10 — see forward-pointer #3 below). Blocked on out-of-band DLC inference.
2. **DLC-side path resolver fields deferred.** [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) lines 756 / 760 / 766 (`dlc_centered_spout_midpoint_parquet` glob) + [`src/stroke_orofacial/dlc_io/parquet.py`](../src/stroke_orofacial/dlc_io/parquet.py) lines 294 / 377 (provenance write) — DLC handling is forward-pointer-only per the kickoff allowlist. Pattern A's `halves_concat_label` continues to work unchanged.
3. **Bare-vs-b spout-behavior comparison — folded into Phase 8a.10 scope per Priya 2026-05-12.** Per-(animal, date) pairing of standard-distance bare half vs closer-spout b half licking outcomes across the 19 Pattern B sessions. Lands when Phase 8a.10 is picked up; Phase 8a.10's Next-phase-candidates entry in [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) updated to reflect the expanded scope (see Task 9 commit). Rationale (per DECISIONS 2026-05-12 Phase 7-pre-secondary-spout entry, Findings #3): 8a.10's existing scope already touches the spout-behavior visualization surface; consolidating reduces phase fragmentation; the DLC-side comparison stays a separate forward-pointer (above #1) because it's blocked on DLC b-half inference.
4. **Weak candidates investigation.** PS51/2025-04-29 + PS54/2025-05-08 (n_ws=1, n_cam=2, n_dlc=1) — out of scope for the Pattern B registry (neither half is a complete pair). Worth flagging for Priya's future investigation as a data-state question (b-cam-dir-only suggests experimenter restart or misnomered directory).
5. **`bnpm` dep + orphan cam{1,3,4}/PS48/20250314{a,b}.npz housekeeping** — carried forward from 7-pre-multi-half. Still pending; orthogonal to this phase.
6. **One-time cohort-wide re-emit.** Phase 2 + Phase 3 now produce b-half outputs for the 19 Pattern B sessions, but the canonical `pipeline_outputs/` tree still lacks them. The cohort-emit runners need a re-run to populate the b-half paths. Decision: bundle as a manual post-merge step in Task 9's PR description, OR carve out as a separate small chore-PR mirroring the Task 0.5 baseline-capture pattern. Pick at Task 9 time.

**Tag:** `v7-pre-secondary-spout` on the merge commit.

---

## Phase 8a.10 — Spout-behavior visual gate + spout-close-vs-standard cohort comparison

**Date:** 2026-05-13 (visual sign-off) → 2026-05-14 (merged + tagged)
**PR:** #113 (merge-commit `46a237e`)
**Tag on merge:** `v8a.10-spout-visual-gate`
**Branch:** `phase/8a.10-spout-visual-gate`

**Scope.** Two sub-deliverables in one PR. **Sub-deliverable A** ports the legacy `analysis/behavior_report/` per-mouse visualizations — 11 canonical plot families × 8 animals (Q1 Option 2 SCOPE LOCK 2026-05-13; 7 deferred families queued as Phase 9+ forward-pointer). Outcome A faithful-port with 8 intentional deviations from legacy (SIDE_COLORS mouse-frame palette inversion, raster_dot_alpha=0.6, criteria_34 overlay removed, zorder layering, supxlabel, raster_xticks=[0,5], thinner reward marker, longitudinal_xtick_fontsize=6). **Sub-deliverable B** implements the bare-vs-b comparison forwarded from Phase 7-pre-secondary-spout (DECISIONS 2026-05-12, Finding #3) — Cohort B = 14 post-stroke sessions across PS51/PS54/PS55 (filter `rel_day >= 2`); cohort-only design (no per-session paired panels per Addendum #1) with two cohort-renderer outputs per animal: 4-row × 2-col story strip (`<animal>_summary.{svg,png}`) + 2×2 per-trial pooled scatter (`<animal>_per_trial.{svg,png}`). Sub-B underwent 9 visual-iteration rounds (Addenda #1–#8 documented post-hoc in commit `eb0cd5a`).

Sub-deliverable B reshaped mid-phase from 5-endpoint per-session-and-cohort to 3-endpoint cohort-only (per Addendum #1).

**What landed.** ~10 source files, 3 config blocks, 4 tests files, 1 notebook, 3 docs. Detailed file inventory:

1. [`src/stroke_orofacial/spout_behavior/visual_gate.py`](../src/stroke_orofacial/spout_behavior/visual_gate.py) — Sub-A core (~1,900 lines). 11 render functions (`render_criteria_performance`, `render_accuracy_firstCorrectLick`, `render_accuracy_firstCorrectLickAll`, `render_lickRate_bySession`, `render_latency_bySession`, `render_numLicks_bySession_{correct,all,correct_and_incorrect}`, `render_lick_raster`, `render_lickiness_bySession`, `render_switchiness_bySession`), Cohort A iteration helpers (`iter_cohort_a_sessions` with on-disk filter + Pattern A multi-half augmentation), `SessionPlotData` dataclass + `load_session_plot_data` (extended with `half_suffix` kwarg in Sub-B), `LongitudinalAxis` + `compute_longitudinal_axis` + `apply_longitudinal_axis`, shared compute helpers, `save_visual_gate_figure`, `SIDE_COLORS` mouse-frame palette.

2. [`src/stroke_orofacial/spout_behavior/cohort_summary.py`](../src/stroke_orofacial/spout_behavior/cohort_summary.py) — Sub-A tiler. `make_summary_figures(animals, resolver, *, plot_families=None, align_to_stroke=True, ...)`. Reads per-mouse PNGs; emits cohort tile-grids at `spout_behavior/spout_behavior_figures/summary/`; `lick_raster` auto-skipped (too dense for tiling).

3. [`src/stroke_orofacial/spout_behavior/spout_close_vs_std.py`](../src/stroke_orofacial/spout_behavior/spout_close_vs_std.py) — Sub-B core (renamed from `bare_vs_b.py` via pure-rename commit `b79a7c5` per Addendum #3 Tweak 1). `SessionPairData` dataclass; `iter_cohort_b_session_keys` + `iter_cohort_b_sessions` (rel_day filter via `COHORT_B_REL_DAY_MIN=2`); two cohort renderers (`render_animal_summary_spout_close_vs_std` 4×2 story strip + `render_animal_per_trial_spout_close_vs_std` 2×2 per-trial scatter); typography knobs threaded from `spout_close_vs_std:` config block.

4. [`src/stroke_orofacial/animals.py`](../src/stroke_orofacial/animals.py) — `AnimalInfo.stroke_laterality: Literal["L", "R"] = "L"` field + `mouse_side_to_ipsi_contra(mouse_side)` helper; loader validation rejects values outside `{"L", "R"}`. Scaffolding for the future pub-figures phase consumer.

5. [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `PathResolver.spout_behavior_figures_dir(animal)` (Sub-A per-mouse output dir); `spout_behavior_figures_summary_dir()` (cohort tile-grid dir); `spout_close_vs_std_dir(animal=None)` (Sub-B output dir; `animal=None` returns `cohort/` subdir per Addendum #1).

6. [`configs/defaults.yaml`](../configs/defaults.yaml) — three new YAML blocks:
   - `visual_gate:` — palette, accuracy/latency/lickrate/numlicks y-bounds, raster styling (`raster_xlim`, `raster_dot_size`, `raster_dot_alpha`, `raster_dot_correct_color`, `raster_dot_incorrect_color`, `raster_dot_correct_zorder`, `raster_dot_incorrect_zorder`, `raster_reward_marker_color`, `raster_reward_marker_alpha`, `raster_reward_marker_linewidth`, `raster_xticks=[0, 5]`, `raster_xlabel_fontsize`), longitudinal-axis styling (`xtick_fontsize=5`, `longitudinal_xtick_fontsize=6`, `stroke_linewidth`, `stroke_vline_*`), figsize defaults, cohort-summary tiler defaults (`summary_default_plots`, `summary_skip_plots`, `summary_figsize_per_cell`, `summary_dpi`).
   - `spout_close_vs_std:` — cohort-renderer-specific typography (`panel_title_fontsize=14`, `raster_xtick_fontsize=11`, `raster_xlabel_fontsize=13`, `raster_xlabel_labelpad=2`, `raster_day_label_fontsize=7`, `licking_xtick_fontsize=12`, `spout_distance_xlabel_fontsize=13`, `raster_xticks=[0,1,2,3,4,5]`, `raster_ytick_fontsize=8`, `raster_ylabel_fontsize=13`, `raster_ylabel_labelpad=20`, `raster_half_label_fontsize=11`).
   - `behavior_report:` — cohort-wide criteria + window params (window_around_rewards, criteria_3.window, criteria_4.window + num_licks_correct_min + num_licks_incorrect_max). Mirrors legacy `batch_process_behavior_report_20260116PS.ipynb` cell-3 params dict.

7. [`configs/animals.yaml`](../configs/animals.yaml) — `stroke_laterality: "L"` populated for all 8 active animals (Round 2.8 scaffolding); PS51/PS54/PS55 `sessions.start` bumped to 2025-04-21 (commit `6070266`) to drop pre-cohort-launch acquisition days.

8. [`tests/test_visual_gate.py`](../tests/test_visual_gate.py) — 165 tests covering Sub-A. Per-family renderer pins, Cohort A iteration semantics, side-convention inversion, raster polish pins (alpha, zorder, xticks, labelpad, reward marker linewidth), longitudinal-axis helper, longitudinal_xtick_fontsize plumbing, save_visual_gate_figure.

9. [`tests/test_spout_close_vs_std.py`](../tests/test_spout_close_vs_std.py) — 44 tests + 1 skip covering Sub-B. CG-B1 (registry filter, animals subset, n_dlc=0 handling, dataclass shape, path resolver), CG-B3 summary renderer (denominator semantics, 4×2 layout, raster polish), per-trial renderer (2×2 layout, dot fill convention, pooled per-trial counts), and one polish-pin class per addendum (`TestCgB3R2Polish`, `TestCgB3R3Polish`, `TestCgB3R4Polish`, `TestCgB3R5Polish`, `TestRenderAnimalPerTrial`).

10. [`tests/test_animals.py`](../tests/test_animals.py) — `TestStrokeLaterality` class (6 tests covering default `"L"`, explicit `"R"`, invalid-value `ValueError`, helper method behavior, real YAML load).

11. [`notebooks/01_spout_behavior_figures.ipynb`](../notebooks/01_spout_behavior_figures.ipynb) — orchestrator. USER INPUTS: `ANIMALS` (Sub-A cohort), `OVERWRITE`, `INCLUDE_PER_MOUSE_RENDERS`, `INCLUDE_COHORT_SUMMARY`, `PLOT_FAMILIES` (None = all 11), `ALIGN_TO_STROKE`, plus Sub-B INPUTS (`ANIMALS_SPOUT_CLOSE_VS_STD`, `CLEAN_ORPHANED_PER_SESSION_OUTPUTS`, `INCLUDE_SPOUT_CLOSE_VS_STD`). Renders Sub-A per-mouse (11 families × N animals) + Sub-A cohort tile-grids + Sub-B summary + Sub-B per_trial in a single execution.

12. [`docs/DECISIONS.md`](DECISIONS.md) — 2026-05-13 entry (this commit's sibling): 9 decisions covering module structure (Decision 1), Outcome A verdict + cohort scope (Decision 2), 8 intentional deviations (Decision 3), Phase 9 stats forward-pointer (Decision 4), bare-vs-b scope-replacement context (Decision 5 — pointer to Decision 8), Task 0.5 cohort gaps (Decision 6), per-family verdict table (Decision 7), Sub-B scope replacement (Decision 8 — Addendum #1), per-trial renderer (Decision 9 — Addendum #8).

13. [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — refreshed at phase close.

14. [`docs/prompts/phase-8a.10-kickoff.md`](prompts/phase-8a.10-kickoff.md) — canonical execution spec. Addenda #1–#8 captured post-hoc in commit `eb0cd5a` (kickoff doc edits = Priya's authorship; committed separately at phase close).

**Sub-deliverable A verdict (per-family, 8 animals × 11 families).** All 88 (animal, family) cells visually PASS as of 2026-05-13 cohort sign-off. The `lick_raster` family went through 9 polish rounds (Task 3 Rounds 2.5–2.8 across commits `a19d00b`, `d0843f9`, `d2f80f7`, `5c3d25b`) to converge on the final form: 2×N panel grid, mouse-frame ylabel, `raster_dot_alpha=0.6`, `zorder=2/3` layering, `fig.supxlabel("Time (s)")`, thin reward marker, explicit xticks `[0, 5]`, criteria_34 overlay removed. The other 10 families ported cleanly with no per-family C-rounds.

**Sub-deliverable B verdict (per-animal, 3 animals).** All 6 cohort summary files + 6 per-trial files PASS as of 2026-05-13 sign-off after the 9-round Addendum #1–#8 visual-iteration loop. PS51 (1 post-stroke session, 2 dots per Standard/Close pair per panel), PS54 (10 post-stroke sessions, densest cohort, 3.0 MB SVG), PS55 (3 post-stroke sessions, the pilot). Scientific message — "excursion limitation relieved by proximity" — confirmed via Addendum #1 PS55 scientific-message check: L-side accuracy 0.098 (Standard) → 0.611 (Close) = 6× improvement; mean correct licks/trial 0.60 → 5.22 = 8.7× improvement.

**Intentional behavior differences vs legacy.**

- **`SIDE_COLORS` mouse-frame palette inversion** (legacy `{"L": "mediumvioletred", "R": "dodgerblue"}` → new `{"L": "dodgerblue", "R": "mediumvioletred"}`). Legacy operated in WS-frame internally + `fn_flip_lr()` at output; Phase 6.8 established mouse-frame as the boundary convention. Cite DECISIONS Decision 3 (1).
- **`raster_dot_alpha=0.6`** (legacy 1.0). Mitigates WS↔mouse-frame label-side layering asymmetry in the lick raster (a real consequence of CG-1's mouse-frame ylabel convention; documented in `.scratch_phase_8a_10/ps51_lick_raster_d45_diagnostic.md`). DECISIONS Decision 3 (2).
- **`criteria_34` pass/fail horizontal-bar overlay REMOVED** (legacy plotted per-trial green-pass / red-fail bars on the raster). Eliminates row-level color clutter; the longitudinal `criteria_performance` family carries the same information cleanly. DECISIONS Decision 3 (3).
- **Lick-raster `zorder=2/3` layering** (legacy used insertion-order). Incorrect (magenta) dots drawn on top of correct (green) so errors are always visible regardless of subplot. DECISIONS Decision 3 (4).
- **`fig.supxlabel("Time (s)")` lick raster** (legacy emitted per-axis xlabel × N_sessions). Single bottom-centered label. DECISIONS Decision 3 (5).
- **`raster_xticks=[0, 5]`** (legacy auto-locator produced `[-1, 0, 1, 2, 3, 4, 5]` for the same xlim). Two endpoint ticks. Paired with `raster_reward_marker_linewidth=0.5` (legacy default ~1.5) and `xtick_fontsize=5` (legacy ~10) so the "0" tick label doesn't visually merge into the reward marker bar. DECISIONS Decision 3 (6).
- **`longitudinal_xtick_fontsize=6`** (legacy ~10). Resolves d+31/d+32 day-label overlap on dense Cohort A cohorts like PS54 (64 sessions in 85 days). DECISIONS Decision 3 (7).
- **`AnimalInfo.stroke_laterality` field + `mouse_side_to_ipsi_contra()` helper** added (no legacy equivalent). Pure-additive scaffolding for the future pub-figures phase. All 8 current animals are `stroke_laterality="L"`; helper inverts mouse-side → ipsi/contra mapping naturally for future R-stroke animals. DECISIONS Decision 3 (8).
- **Sub-deliverable B** has no faithful-port baseline (no legacy bare-vs-b comparison code per Phase 7-pre-secondary-spout's Outcome A audit). Each visual decision (4-row layout, mouse-side palette + Standard/Close fill convention, half labels outside spine, per-session "0" y-tick markers, day labels horizontal on right spine) locked through the Addendum #1-#8 visual-iteration rounds. DECISIONS Decision 8 + 9.

**Exit criteria met.**

- [x] Sub-A verdict: 88/88 (animal, family) cells visually PASS.
- [x] Sub-B verdict: 12/12 cohort output files (6 summary + 6 per_trial) visually PASS for all 3 animals.
- [x] Full pytest suite green for the touched modules: **262 passed, 1 skipped** (53 animals + 165 visual_gate + 44 spout_close_vs_std).
- [x] ruff clean on all touched source + test files.
- [x] DECISIONS 2026-05-13 entry (above this MIGRATION_LOG section) + this MIGRATION_LOG entry + COWORK_SESSION_STATE refresh.
- [x] Cohort-wide re-render executed before close: 8 animals × 11 Sub-A families (88 SVG+PNG pairs) + Sub-A cohort tile-grids (10 SVG+PNG) + Sub-B summary (3 × {svg, png}) + Sub-B per_trial (3 × {svg, png}) all on disk at `pipeline_outputs/spout_behavior/spout_behavior_figures/`.

**Visual-iteration timeline (mapped to Addenda).**

| Round | Date | Addendum | Commit | Scope |
|---|---|---|---|---|
| Sub-A initial | 2026-05-13 | — | b55c7b8 → 64bd1ea (CG-1 through CG-6) | 11 plot families + cohort tiler + orchestrator notebook. |
| Sub-A Task 3 R2 | 2026-05-13 | — | 382606c, 147fdbb | PS55 dual-h5 fix, YAML cohort iterator, output dir restructure (`visual_gate/` → `spout_behavior_figures/`). |
| Sub-A R2.5 (audit) | 2026-05-13 | — | (no commit; verdict A in `.scratch_phase_8a_10/ps51_lick_raster_d45_diagnostic.md`) | PS51 d+45+ lick raster R-trial occlusion audit. |
| Sub-A R2.6 | 2026-05-13 | — | a19d00b | raster_dot_alpha=0.6 + criteria_34 overlay removed. |
| Sub-A R2.7 | 2026-05-13 | — | d0843f9 | zorder + supxlabel + smaller xticks + thinner reward marker + longitudinal_xtick_fontsize. |
| Sub-A R2.8 | 2026-05-13 | — | d2f80f7 + 5c3d25b + 6070266 | raster_xticks=[0,5] + xtick_fontsize=5; stroke_laterality scaffolding; baseline-date bump. |
| Cohort A full re-render | 2026-05-13 | — | (no commit; render-only) | 8 animals × 11 families = 88 PASS. |
| Sub-B CG-B1 | 2026-05-13 | — | dd0e0a8 | bare_vs_b shared infrastructure. |
| Sub-B CG-B2 (superseded) | 2026-05-13 | — | d757294 | Per-session paired panels (5 endpoints); preserved in git history. |
| Sub-B CG-B3 R1 | 2026-05-13 | #1 | 055ef53 | Scope replacement → cohort-only 3-endpoint design. |
| Sub-B CG-B3 R2 | 2026-05-13 | #2 | 5fc9a1b | Standard/Close labels + per-condition palette + raster session dividers + shared y-lims. |
| Sub-B CG-B3 R3 | 2026-05-13 | #3 | b79a7c5 + a1de5cd | Rename + per-mouse-side palette + 4-row split + day labels + darker dividers + typography. |
| Sub-B CG-B3 R4 | 2026-05-13 | #4 | 227052b | Typography + label-rotation polish. |
| Sub-B CG-B3 R5 | 2026-05-13 | #5 | db829b6 | Raster xticks/centering/y-axis overhaul + expand to all 3 animals. |
| Sub-B CG-B3 R7 | 2026-05-13 | #7 | 294d10d | Per-session "0" y-tick markers (supersedes R5 cumulative form). |
| Sub-B R7 follow-on (Addendum #6 retroactively applied) | 2026-05-13 | #6 | e3b5b15 | Day labels horizontal + smaller raster yticks + Trials label labelpad. |
| Sub-B per-trial renderer | 2026-05-13 | #8 | 02be4b0 | Companion 2×2 per-trial pooled scatter. |
| Cohort B full re-render | 2026-05-13 | — | (no commit; render-only) | All 3 animals × {summary, per_trial} = 12 PASS. |
| Phase close — kickoff addenda + audit cleanup | 2026-05-13 | — | eb0cd5a | Post-hoc Addenda #1-#8 prose committed; `.audit_inspect_licks_npz.py` moved to scratch. |

**Forward-pointers queued for future phases.**

1. **Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit.** `Reward_{L,R}` NPZ channels carry tone-cue indices (not reward indices) cohort-wide per a separately diagnosed labeling swap. Renderer code is faithful — the Row 4 raster's "reward marker" line currently marks tone onset, not reward delivery. Lick-raster reads correctly regardless because tone + reward fire simultaneously at trial start (Pavlovian; same-sample chronological-order check from `.scratch_phase_8a_10/ps51_d45_diag.py`). Semantic labels will retroactively match data after 8a.10.1's re-emit + re-render.
2. **126-session YAML-cohort gap chore-PR.** DECISIONS Decision 6: Cohort A `configs/animals.yaml` `sessions.start`/`end` vs legacy `report.json[latency_bySession]` keys diverge across 126 sessions cohort-wide. Most gap-sessions are pre-cohort-launch acquisition (low scientific signal). Queue as a separate chore-PR.
3. **Phase 9 stats.** Frequentist/Bayesian model selection + multiple-comparison correction + effect-size machinery. Blocks `playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 + `behavior_report_PS.py::compute_stats_p_values_*`. 5 trimmed Sub-A plot families also queued.
4. **Phase 7-pre-secondary-spout-compare-DLC.** DLC inference on Pattern B b halves (Phase 7-pre-secondary-spout DECISIONS Finding #1-#2). Blocked on Priya running DLC out-of-band. When unblocked, Sub-B output dir can grow a parallel `dlc_compare/` subdir.
5. **Pub-figures phase.** Consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` (Decision 3 deviation #8 scaffolding). Ipsi/contra labels on per-mouse plots.
6. **CG-B2 per-session paired-panel renderers (preserved in git history at `d757294`).** Superseded by CG-B3 R1's cohort-only design (Decision 8). If a future phase needs per-session per-endpoint visualizations, the CG-B2 implementation can be cherry-picked back from history.

**Tag:** `v8a.10-spout-visual-gate` on the merge commit.

---

## Phase 8a.10.1 — Cohort-wide Tone↔Reward channel-label swap fix at wavesurfer read time

**Date:** 2026-05-14

**Branch / tag.** Branch `phase/8a.10.1-tone-reward-swap-fix` opened 2026-05-14 off `main` at `5cc1a9e` (PR #115 docs-kickoff merge). Tag-on-merge `v8a.10.1-tone-reward-swap-fix`; merge SHA + PR# recoverable post-merge via `git rev-list -n 1 v8a.10.1-tone-reward-swap-fix` and `gh pr list --search 'v8a.10.1'`.

**Kickoff:** [`docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md`](prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md). Addenda #1-#3 captured inline (Path Y format).

**Sibling DECISIONS entry:** 2026-05-14 (10 decisions; see Decisions 1-10 above this MIGRATION_LOG section).

### Context

Phase 8a.10 Sub-B Row 4 raster surfaced semantic mislabeling cohort-wide: the raw `.h5` files' "Reward_*" channel actually carries ~200 ms tone TTLs (cue onset), while "Tone_*" carries ~26 ms reward solenoid pulses. The labels were inverted at acquisition (pre-existing; not a regression). Phase 8a.10.1 fixes the labeling at the wavesurfer read boundary so downstream symbols reference scientifically-correct events.

Because tone + reward fire synchronously at trial start on bilateral-reward sessions (Pavlovian), the swap is invariant at the test-vector level on 200 of 276 cohort sessions; the remaining 76 sessions carry ≥1 withhold trial where the reward solenoid does not fire, and these sessions show predicted denominator changes in accuracy renders + baseline-pool growth in DLC consumer plots.

### What landed

**Source (8 changed source modules + 1 new test module):**

- [`src/stroke_orofacial/spout_behavior/wavesurfer_io.py`](../src/stroke_orofacial/spout_behavior/wavesurfer_io.py) — Commit A. Channel-name → array-key mapping reads under `tone_reward_swap_enabled: true` gate (`configs/defaults.yaml`). When the flag is true, "Reward_*" loads into the tone slot and "Tone_*" loads into the reward slot. Flag-false branch preserves legacy mislabel for byte-identity regression tests + emergency rollback.
- [`src/stroke_orofacial/spout_behavior/trial_segmentation.py`](../src/stroke_orofacial/spout_behavior/trial_segmentation.py) — Commit B. `TrialRecord` switches to two-anchor model: `tone_idx: int` (always present, the cue temporal anchor) + `reward_idx: int | None` (optional outcome; `None` for withhold trials). `reward_side` field renamed to `tone_side` (side is determined at cue presentation, not at reward delivery).
- [`src/stroke_orofacial/spout_behavior/criteria.py`](../src/stroke_orofacial/spout_behavior/criteria.py), [`endpoints_engagement.py`](../src/stroke_orofacial/spout_behavior/endpoints_engagement.py), [`endpoints_per_trial.py`](../src/stroke_orofacial/spout_behavior/endpoints_per_trial.py), [`endpoints_writer.py`](../src/stroke_orofacial/spout_behavior/endpoints_writer.py), [`session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py), [`visual_gate.py`](../src/stroke_orofacial/spout_behavior/visual_gate.py), [`spout_close_vs_std.py`](../src/stroke_orofacial/spout_behavior/spout_close_vs_std.py), [`criteria_slugs.py`](../src/stroke_orofacial/spout_behavior/criteria_slugs.py) — Commit B (Q-C Case-2 renames). Function/method renames: `tone_trial_count_per_session()` replaces `reward_trial_count_per_session()`; `_TONE_REWARD_PAIRING_WINDOW_MS` constant replaces `_REWARD_TONE_PAIRING_WINDOW_MS` (docstring polish in commit `8db285c`); `SessionPlotData.tones_idx` replaces `SessionPlotData.rewards_idx`.
- [`src/stroke_orofacial/dlc_spatial/reward_aligned.py`](../src/stroke_orofacial/dlc_spatial/reward_aligned.py) — Commit B (X1-β source). `load_reward_events` → `load_tone_events` rename. NPZ-key reads swap `Reward_<side> → Tone_<side>`. Local variable `reward_ws` + module name `reward_aligned.py` kept as-is; their cleanup is Phase 7b-light per DECISIONS Decision 6.
- [`src/stroke_orofacial/dlc_kinematics/interpolation.py`](../src/stroke_orofacial/dlc_kinematics/interpolation.py), [`tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py), [`mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py) — Commit B (X1-β indirect callers). 3 sites updated to call `load_tone_events` in place of `load_reward_events`.

**Config:**

- [`configs/defaults.yaml`](../configs/defaults.yaml):
  - New: `tone_reward_swap_enabled: true` opt-in flag (top-level).
  - Renamed: `behavior_report.window_around_rewards` → `behavior_report.window_around_tones` (Commit E partial-rename — only the production-consumed knob).
  - New: `visual_gate.lick_count_integer_yticks: true`; `spout_close_vs_std.cohort_dot_size: 80`, `cohort_ytick_fontsize: 11`, `cohort_ylabel_fontsize: 13`, `lick_count_integer_yticks: true` (Task 4 follow-on figure cosmetics).

**Tests (1417 pass; 14 test files touched; new test module + 13 sync'd):**

- [`tests/test_wavesurfer_io.py`](../tests/test_wavesurfer_io.py) — **NEW** 196 lines. Pins both `tone_reward_swap_enabled` flag values + channel-name → array-key mapping invariants + multi-channel correctness on a synthetic .h5 fixture.
- Test sync (Commit C) across 13 test files for Q-A.β / Q-B.α / Q-C / X1-β: [`test_criteria.py`](../tests/test_criteria.py), [`test_endpoints_per_trial.py`](../tests/test_endpoints_per_trial.py), [`test_endpoints_engagement.py`](../tests/test_endpoints_engagement.py), [`test_trial_segmentation.py`](../tests/test_trial_segmentation.py), [`test_visual_gate.py`](../tests/test_visual_gate.py), [`test_spout_close_vs_std.py`](../tests/test_spout_close_vs_std.py), [`test_reward_aligned.py`](../tests/test_reward_aligned.py), [`test_dlc_spatial_side_convention.py`](../tests/test_dlc_spatial_side_convention.py), [`test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py), [`test_dlc_interpolation.py`](../tests/test_dlc_interpolation.py), [`test_endpoints_writer.py`](../tests/test_endpoints_writer.py), [`test_endpoints_within_session.py`](../tests/test_endpoints_within_session.py), [`test_recovery_trajectories.py`](../tests/test_recovery_trajectories.py).

**Scripts (5 new under `scripts/phase_8a_10_1/`):**

- [`scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py`](../scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py) — 276-session driver for Task 2 Phase 2 re-emit. Pre/post sha256 capture, per-session error handling, manifest output.
- [`scripts/phase_8a_10_1/reemit_manifest.csv`](../scripts/phase_8a_10_1/reemit_manifest.csv) — 276 rows × `(animal, date, half_suffix, status, pre_fix_sha256, post_fix_sha256, wall_time_sec)`. Tally: **276 OK / 0 ERROR / 200 byte-identical / 76 differing**.
- [`scripts/phase_8a_10_1/audit_stale_npzs.py`](../scripts/phase_8a_10_1/audit_stale_npzs.py) + [`delete_stale_npzs.py`](../scripts/phase_8a_10_1/delete_stale_npzs.py) + [`deletion_manifest.json`](../scripts/phase_8a_10_1/deletion_manifest.json) — Commit F cleanup harness. 512 orphan NPZs (14.5 GB) removed from `pipeline_outputs/spout_behavior/` outside the canonical 276-session cohort scope. Manifest is 7189 lines (one entry per deleted file with rel-path + size).
- [`scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py`](../scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py) + [`rerender_manifest.csv`](../scripts/phase_8a_10_1/rerender_manifest.csv) — Task 4 driver + 405-row manifest. 404 figures re-rendered across 3 families (Sub-A `visual_gate.py` per-mouse plots, Sub-A `cohort_summary.py` tile-grids, Sub-B `spout_close_vs_std.py` summary + per-trial), on post-fix Phase 2 NPZs.

**Docs:**

- [`docs/DECISIONS.md`](DECISIONS.md) — 2026-05-14 top entry (this commit's sibling): 10 decisions (Decisions 1-10) covering fix location + gate flag (Decision 1), Q4.B cohort scope = 276 sessions (Decision 2), Option α in-place overwrite (Decision 3), Q1.A reversal + F-P-7 surfaced (Decision 4), Q2.A 404-figure re-render (Decision 5), Q3.B deferral to Phase 7b-light (Decision 6), Case-2 universal rename verdict (Decision 7), peri_reward partial-rename E.C (Decision 8), 512-NPZ stale cleanup (Decision 9), 4-stage verification gate (Decision 10).
- [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — refreshed at phase close.
- [`docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md`](prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md) — canonical execution spec + Addenda #1-#3 captured inline (Path Y format).
- [`docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`](PHASE_8A_LEGACY_ENDPOINT_MAPPING.md), [`docs/SCIENTIFIC_ENDPOINTS.md`](SCIENTIFIC_ENDPOINTS.md), [`docs/phase-8a/legacy-behavior-report-rollup.md`](phase-8a/legacy-behavior-report-rollup.md) — minor terminology updates following Q-C renames.

### Commit-by-commit timeline

| # | SHA | Commit | Scope |
|---|---|---|---|
| 1 | `b86acfa` | fix(phase-8a.10.1 commit-A): swap Tone↔Reward channels at wavesurfer read time | The load-bearing change. `wavesurfer_io.py` channel-name mapping under `tone_reward_swap_enabled: true` gate. |
| 2 | `f4f96f8` | refactor(phase-8a.10.1 commit-B): consumer renames per Q-A.β / Q-B.α / Q-C / X1-β | Two-anchor TrialRecord (Q-A.β), `reward_side` → `tone_side` (Q-B.α), function/dataclass renames (Q-C Case-2), DLC X1-β source + 3 indirect callers. |
| 3 | `5e6259b` | test(phase-8a.10.1 commit-C): test sync per Q-A.β / Q-B.α / Q-C / X1-β | 13 test files updated + new `test_wavesurfer_io.py` (196 lines). pytest 1417 pass. |
| 4 | `ce9ab85` | docs(phase-8a.10.1 commit-D): post-tone / tone-anchored docstring polish | Docstring narrative + scientific-endpoints doc terminology alignment. |
| 5 | `8db285c` | docs(phase-8a.10.1): clarify _TONE_REWARD_PAIRING_WINDOW_MS rationale | Constant docstring clarifies tone-anchored pairing semantics. |
| 6 | `ece0fb8` | chore(phase-8a.10.1 task-2): Phase 2 cohort-wide re-emit post-swap-fix (276 NPZs) | Driver script + 276-row manifest committed; NPZs re-emitted in place (Option α). PS55/2025-06-06 dual-h5 handled via `DUAL_H5_HACK_SESSIONS`. |
| 7 | `54a203a` | refactor(phase-8a.10.1 commit-E): rename behavior_report.window_around_rewards → window_around_tones | Commit E partial-rename per Pass-2 peri_reward audit (E.C-partial); the one production-consumed knob in the peri_reward family. |
| 8 | `267b5d3` | chore(phase-8a.10.1 commit-F): cleanup 512 stale pre-fix Phase-2 NPZs outside canonical cohort scope | 512 orphan NPZs / 14.5 GB removed from `pipeline_outputs/spout_behavior/`. Driver + audit + deletion manifest committed. |
| 9 | `e912eb2` | refactor(phase-8a.10.1 commit-G): figure legends — "mouse L/R" + "Reward L/R" → "Tone L/R" (trial-cue side semantic) | Figure-legend rename across visual_gate + spout_close_vs_std; aligns visible labels with tone-cue side semantic. |
| 10 | `758155a` | fix(phase-8a.10.1 commit-H): absDate longitudinal xtick rotation 45° to prevent leftmost-label clipping | `apply_longitudinal_axis` xtick rotation 45° + `ha="right"`; `bbox_inches="tight"` on `save_visual_gate_figure`. |
| 11 | `61db775` | chore(phase-8a.10.1 task-4): Phase 8a.10 figure re-render on post-fix data (404 figures across 3 families) | 404-figure driver + 405-row manifest; all 3 visualization families re-rendered on post-fix Phase 2 NPZs. |
| 12 | `037a8bc` | fix(phase-8a.10.1): increase cohort dot size in spout_close_vs_std summary + per_trial figures | Sub-B cohort dot size bump (16 → 80) per Priya's eyeball verdict. |
| 13 | `b7f171b` | feat(phase-8a.10.1): spout_close_vs_std — y-axis typography bump + add Rows 3-4 (fraction trials with ≥1 correct/incorrect lick) + integer y-ticks on lick-count rows | Task 4 follow-on Changes 1+2+3: y-axis fontsize knobs threaded; Sub-B per_trial extended from 2×2 → 4×2 with new Rows 3-4 fraction-of-trials renderers; `MaxNLocator(integer=True)` on all lick-count rows gated by `lick_count_integer_yticks`. |
| 14 | (this commit) | docs(phase-8a.10.1): DECISIONS Decision 1-10 + MIGRATION_LOG entry + state-doc refresh | Phase-close docs commit (Tasks 6 + 7). |

### Verification — 4-stage gate (all PASS)

1. **Task 0.5 — Pulse-width audit (pre-fix).** All 271 raw .h5 files across the cohort measured. Cohort-wide channel-label inversion confirmed: `"Reward_*"` carries ~200 ms TTLs (tone duration); `"Tone_*"` carries ~26 ms solenoid pulses (reward duration). One-directional swap, no animal-specific exceptions.
2. **Task 3 — Sample-comparison + downstream-shift sanity (post-fix re-emit).** Four sub-checks:
   - Check 1: Bit-perfect swap on PS46/2025-03-07 (pre-fix `Tone_L` array byte-identical to post-fix `Reward_L` and vice-versa).
   - Check 2: Post-fix pulse-width re-check (now `"Tone_*"` carries ~200 ms, `"Reward_*"` carries ~26 ms).
   - Check 3: Per-session count diff `count(Tone_L) − count(Reward_L)` across all 276 NPZs (= 0 on bilateral sessions, = withhold_L count on withhold sessions).
   - Check 4: Withhold-count diagnostic. 76 of 276 sessions carry ≥1 withhold; PS55/2025-04-28 R-side withhold sanity-checked via supplementary tmp twin-emit. Result: PASS — Δ=0 on synchronous-event majority, predicted-magnitude shifts on withhold sessions.
3. **Task 4 — Visual verdict on 404 figures (post-fix re-render).** All 3 visualization families (Sub-A `visual_gate.py`, Sub-A `cohort_summary.py`, Sub-B `spout_close_vs_std.py`) eyeball-verified PASS across all 8 cohort animals.
4. **Task 4.5 — DLC cascade-safety spot-check (Addendum #2).** Exercised the 4 X1-β indirect callers + `build_reward_aligned_analysis` on 3 representative sessions:
   - PS46/2025-03-07 (bilateral baseline): baseline pool unchanged (96 = 48 + 48). ✓
   - PS54/2025-05-03 (high-withhold watch-item): baseline pool grew by exactly 86 events (= 45 L-withholds + 41 R-withholds). ✓
   - PS48/2025-03-14 (Pattern A multi-half partial): 2 of 5 X1-β sites runnable; 3 fail on pre-existing upstream Phase 7a gaps unrelated to the swap fix (tongue interp parquet missing, `dlc_h5_files` empty in manifest). Result: PASS.

All 4 gates PASS. No hot-fix required; no Q3.B revoke / Phase 7b cascading required during the phase.

### Intentional behavior differences vs legacy

- **Two-anchor `TrialRecord` model (Q-A.β).** Legacy used a single `reward_idx` anchor that conflated cue onset and outcome. New: `tone_idx: int` (always present, cue temporal anchor) + `reward_idx: int | None` (optional outcome; `None` for withhold trials). Withhold trials now appear in trial-record streams; pre-fix code silently dropped them at the `reward_idx is None` filter. DECISIONS Decision 7.
- **`reward_side` → `tone_side` field rename (Q-B.α).** Side is determined at cue presentation, not at reward delivery. Renamed cohort-wide (TrialRecord, downstream consumers). DECISIONS Decision 7.
- **`Sub-B per_trial` figure extended from 2×2 → 4×2 layout.** Task 4 follow-on Change 2 (commit `b7f171b`). New Rows 3-4 render fraction-of-trials-with-≥1-{correct,incorrect}-lick per session. No legacy equivalent — pure-additive scientific message. y ∈ [0, 1.05]. DECISIONS Decision 5.
- **Integer y-tick locator on lick-count rows.** Task 4 follow-on Change 3 (commit `b7f171b`). `MaxNLocator(integer=True)` gated by `lick_count_integer_yticks: true` flag. Applied to Sub-A `numLicks_bySession_*` renderers + Sub-B summary Rows 2-3 + Sub-B per_trial Rows 1-2. Legacy used matplotlib's default float ticks producing 1.5, 2.5, etc. on integer count data.
- **Figure-legend "Tone L/R" semantic (Commit G).** Replaces legacy "mouse L/R" + "Reward L/R" labels. Aligns visible legend with the tone-cue temporal anchor semantics. DECISIONS Decision 5.
- **absDate longitudinal xtick rotation 45° + ha="right" (Commit H).** Prevents leftmost-label clipping on absDate-mode renders. Legacy used horizontal ticks. `bbox_inches="tight"` on figure save complements the rotation.
- **`peri_reward_periods/` directory name kept as-is (Decision 8 E.B.1).** Stored-but-unused on disk; renaming would invalidate every existing on-disk file path without functional benefit. The semantic mismatch is documented; cleanup is F-P-1.
- **`reward_aligned.py` module name + local-variable `reward_ws` kept as-is.** Q3.B Phase 7b-light deferral. The X1-β surgical rename touches only the function call boundary (`load_reward_events` → `load_tone_events`); deeper local-variable + module-name + comment narrative cleanup is queued for Phase 7b-light.

### Forward-pointers queued for future phases

(See DECISIONS 2026-05-14 entry "Findings carried forward" for full prose; numbering aligned with that entry.)

- **F-P-1** — `peri_reward_periods/*.npz` stored-but-unused; future cleanup candidate (wire into consumer or delete emit step).
- **F-P-2** — PS46-bilateral-reward parity tests survive byte-identical; future withhold-session parity tests will diverge by design (require withhold-bearing test fixture).
- **F-P-4** — PS48/2025-03-14 Pattern A multi-half infrastructure gaps unrelated to swap fix (missing tongue interp parquet; empty `dlc_h5_files`). Phase 7b-light fodder.
- **F-P-5** — Phase 7-pre-multi-half-dlc: Pattern A DLC merge wiring (Priya's legacy code handles PS48 in the interim).
- **F-P-6** — 111-session YAML-cohort gap chore (superset of Phase 8a.10 Decision 6's 126-session chore).
- **F-P-7** — Phase 7-pre-alignment-templates: dedicated mini-phase for cohort-wide alignment template emit into the new pipeline tree + consumer cutover from `alignment_template_legacy_read()` to `alignment_template_new()`. Estimated ~6-12 commits. Surfaced by Task 5 pre-flight audit; structurally independent of the swap fix.

### Exit criteria met

- [x] All 4 verification gates PASS (Task 0.5 + Task 3 4-check + Task 4 visual + Task 4.5 DLC cascade).
- [x] 276/276 Phase 2 NPZ re-emit OK; 0 errors; 200 byte-identical / 76 differing as predicted.
- [x] 404/404 figures re-rendered + eyeball-verified PASS.
- [x] 512 stale NPZs cleaned; on-disk == canonical-cohort invariant established.
- [x] pytest 1417 pass (including new `test_wavesurfer_io.py` and 13 sync'd test files).
- [x] ruff clean on all touched source + test files.
- [x] DECISIONS 2026-05-14 entry + this MIGRATION_LOG entry + COWORK_SESSION_STATE refresh.

**Tag:** `v8a.10.1-tone-reward-swap-fix` on the merge commit.

---

## Chore — YAML cohort-gap policy lock (F-P-6 discharge)

**Date:** 2026-05-14
**Tag on merge:** `vchore-yaml-cohort-gap-closure` (if Priya confirms at PR-merge)
**Branch:** `chore/yaml-cohort-gap-closure`

**Scope.** Discharge F-P-6 (111-session — actually 69 unique-date — YAML-cohort gap chore, forward-pointer from Phase 8a.10.1 close). Re-scoped mid-chore via kickoff Addendum #1: original kickoff framed the chore as per-session inclusion adjudication; correct framing per Phase 8a.10 Decision 6 path (b) is policy lock + audit-trail documentation, no YAML semantic edits.

**What landed.** Three commits on `chore/yaml-cohort-gap-closure`:

1. `docs(yaml-cohort-gap kickoff)`: kickoff doc + Addendum #1 (re-scope override).
2. `chore(yaml-cohort-gap)`: [`configs/animals.yaml`](../configs/animals.yaml) header comment block (cohort-boundary policy) + 8 per-animal inline `sessions:` comments. No semantic changes.
3. `docs(yaml-cohort-gap)`: [`docs/DECISIONS.md`](DECISIONS.md) entry (this chore's close record) + this `MIGRATION_LOG` entry.

**Sessions adjudicated.** 69 unique-date gaps across PS46-PS55 (Cohort A) + 0 gaps for Cohort B (`secondary_spout_sessions:` registry confirmed complete by CC's Task 1 audit). All 69 documented as out-of-scope-by-design; YAML ranges unchanged. Per-animal gap counts: PS46=10, PS47=9, PS48=9, PS49=12, PS50=20, PS51=3, PS54=3, PS55=3. The 111-figure from F-P-6 inherited the legacy `report.json` key-count (suffixed `a`/`b` halves counted as separate keys); the 69-figure is per-(animal, date) and matches the consolidated pipeline session abstraction.

**Intentional behavior differences vs legacy.** None. Pipeline behavior is unchanged (no YAML semantic edits). Legacy `report.json` remains a historical reference; YAML stays the authoritative cohort definition. The new breadcrumb comments are documentation-only.

**Exit criteria met.**

- [x] Task 1 diff audit produced [.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md](../.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md) + `gap_audit_raw.json` (uncommitted audit-trail).
- [x] Task 3 YAML edits comment-only (verified by `git diff configs/animals.yaml`; only `+` lines).
- [x] Task 4 diff re-verification confirms unchanged 69-session gap count post-edit ([.scratch_chore_yaml_cohort_gap/post_close_verification.md](../.scratch_chore_yaml_cohort_gap/post_close_verification.md), uncommitted).
- [x] `pytest -q tests/test_animals.py` → 53 passed (YAML load tests unchanged).
- [x] `load_animals()` returns 8 animals with `session_start` / `session_end` unchanged for each.
- [x] DECISIONS 2026-05-14 chore entry + this MIGRATION_LOG entry.

**Forward-pointers queued.** None from this chore. Phase 7b-light is the next item per memory `project_phase_7b_light_ordering.md`.

**Tag:** `vchore-yaml-cohort-gap-closure` on the merge commit (Priya confirms at PR-merge; if declined, log as untagged chore).

---

## Phase 7b-light — DLC source narrative cleanup (Case-2 module + var + docstring rename + bifurcation rule)

**Date:** 2026-05-15
**Tag on merge:** `v7b-light-dlc-narrative-cleanup`
**Branch:** `phase/7b-light-dlc-narrative-cleanup`

**Scope.** Case-2-discriminating source-side narrative rename across `dlc_spatial/` + `dlc_kinematics/` + tests + `configs/defaults.yaml` + `notebooks/12_*` + `scripts/`. Completes the Q3.B-deferred narrative cleanup from Phase 8a.10.1's X1-β surgical fold-in. Bifurcated via kickoff [Addendum #1](prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md): source-side identifiers + docstrings + YAML internal keys RENAME this phase; on-disk-layout-affecting strings (output subdir paths, NPZ schema keys, window-dir tokens, family-name tokens, CLI flag spellings, figure filename suffixes) PRESERVE for Phase 7c-dlc-cohort-reemit. Task 5 spot-check scope narrowed via [Addendum #2](prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md): 3-session spec → 1 session (PS46/2025-03-07) per operational PathResolver constraint + leverage of Phase 8a.10.1 Task 4.5's prior PS54 verdict + PS48 deferral to F-P-5.

**What landed.** 12 commits on `phase/7b-light-dlc-narrative-cleanup`:

| # | SHA | Scope |
|---|-----|-------|
| 1 | `71020b7` | docs(kickoff): kickoff doc + Addendum #1 |
| 2 | `14c407e` | refactor(module): `dlc_spatial.reward_aligned` → `dlc_spatial.tone_aligned` + 8 importer path updates |
| 3 | `3035ff6` | refactor(stub): delete `dlc_kinematics/reward_aligned.py` (1-line stub, 0 importers) |
| 4 | `f184de2` | refactor(notebook): rename notebook 12 + script docstring reference |
| 5 | `425d257` | refactor(C5): Case-2 sweep in `dlc_spatial/{tone_aligned, window_selector}.py` + 6 consumer files (class rename, function/param/var renames, narrative; on-disk strings preserved) |
| 6 | `eb67f0b` | refactor(C6): Case-2 sweep in `dlc_kinematics/{interpolation, jaw_pertrial, _angle}.py` (function renames `_load_tone_centers_cam`, `_build_tone_aligned_pool_mask`; `reward_centers_cam` + `reward_frame_idx` fields PRESERVED) |
| 7 | `9b87956` | refactor(C7): Case-2 sweep in `dlc_kinematics/{tongue_pertrial, tongue_jaw_mismatch}.py` (`_REWARD_COLOR` → `_TONE_COLOR`; narrative renames) |
| 8 | `2656480` | refactor(C8): Case-2 sweep in `dlc_kinematics/{tongue_visual, tongue_angle_cohort, __init__}.py` + public-API rename `build_reward_aligned_cohort` → `build_tone_aligned_cohort` (single commit) |
| 9 | `bed29fb` | refactor(C9): `mean_sem_visual.py` + `paths.py` lockstep (`reward_pre_ms`/`reward_post_ms` param pair rename across ~12 functions + 4 test/parity files) |
| 10 | `c1a7efc` | refactor(C10): `configs/defaults.yaml` YAML key renames (`dlc_spatial_reward_aligned:` → `dlc_spatial_tone_aligned:`; `reward_aligned_display_window_ms:` → `tone_aligned_display_window_ms:`) + lockstep source-access updates across 10 files |
| 11 | `407e194` | test(Task 4): rename `test_reward_aligned.py` → `test_tone_aligned.py` + internal class/helper identifier sync across 4 affected test files |
| 12 | `374af69` | chore(ruff cleanup): auto-fix 17 pre-existing ruff errors in DLC subtree (F401 unused imports + F541 f-string-without-placeholders + F821 missing `from typing import Any`) |

**Source-side renames (RENAMED per Addendum #1 bifurcation):**

- Functions: `build_reward_aligned_*` family (4), `save_reward_aligned_npz`, `_load_reward_centers_cam`, `_build_reward_aligned_pool_mask`, `_extract_reward_aligned`, `_plot_reward_aligned`, `_plot_reward_aligned_session_overlays`, `_plot_reward_aligned_binned_overlays`, `build_reward_aligned_cohort` (public API).
- Class: `RewardAlignedWindow` → `ToneAlignedWindow`.
- Parameters: `reward_ws_samples`, `reward_config`, `reward_centers_float`, `reward_pre_ms` / `reward_post_ms` (paths.py + mean_sem_visual.py ~12 function pair).
- Constants: `_REWARD_COLOR` → `_TONE_COLOR`.
- YAML keys: `dlc_spatial_reward_aligned:`, `reward_aligned_display_window_ms:` (Q7 hard rename).
- Module + test + notebook file renames: 3 + 1 stub deletion (see commit table).

**On-disk-affecting strings (PRESERVED per Addendum #1; deferred to Phase 7c):**

- NPZ schema keys: `"n_rewards"`, `"reward_centers_cam"`, `reward_frame_idx` (DataFrame col).
- Output subdir literals: `spatial_reward_aligned/...`.
- Window-dir token: `rewardAligned_<n>pre-<n>post` (`paths.py` f-string).
- Family-name token: `"reward_aligned"` (string used as `_family_paths()` subdir + config sub-key under `tongue_visual.plot_families`).
- CLI flag: `--reward-windows-ms`.
- Figure filename suffixes: `mouseLrewards`, `mouseRrewards`.
- Figure-content strings: plot titles + `_LEGACY_XLABEL` value + result-dict display narrative.
- Legacy NPZ-key + filename citations inside comment narrative.

**Sessions spot-checked.** 1 of 3 originally specified (PS46/2025-03-07; PS54 + PS48 deferred per Decision 5).

**Spot-check verdict (PS46/2025-03-07): PASS.**

| Output | sha256 prefix | Verdict |
|--------|--------------|---------|
| `interpolated_traces/tongue/PS46/20250307.parquet` | `1f44f78ff106…` | BYTE_EQUAL with production |
| `interpolated_traces/jaw/PS46/20250307.parquet` | `e7d68496cb00…` | BYTE_EQUAL with production |
| `spatial_reward_aligned/tongue_nose/trials-all_-500to5000ms/PS46/heatmap_20250307.npz` | `03499b98a918…` | BYTE_EQUAL with production |

`n_rewards = 96` (48 L + 48 R) — matches Phase 8a.10.1 Task 4.5's PS46 baseline-pool prediction exactly. Eyeball verdict PASS by construction (Addendum #1 PRESERVED all figure-content strings → byte-equal inputs through unchanged matplotlib pipeline → byte-equal figures). Verdict deliverable: [`.scratch_phase_7b_light/spot_check_verdict.md`](../.scratch_phase_7b_light/spot_check_verdict.md).

**Intentional behavior differences vs legacy.** None at the data level — phase is pure source-side narrative cleanup. Legacy outputs are not a valid baseline post-Phase-8a.10.1 (legacy carries the Tone↔Reward swap-buggy Phase 2 NPZs). The phase's verdict is byte-equality between pre-rename and post-rename source states on the same post-8a.10.1 Phase 2 inputs.

**Exit criteria met.**

- [x] `pytest -q` (full unfiltered, including integration) PASSES at 1417 passed, 39 skipped, 0 failed — matches the post-Phase-8a.10.1 baseline exactly.
- [x] `ruff check src/ tests/` → "All checks passed!" (17 pre-existing errors cleaned in commit `374af69`).
- [x] Forward public-API import `from stroke_orofacial.dlc_kinematics import build_tone_aligned_cohort` succeeds; reverse import (`build_reward_aligned_cohort`) raises `ImportError`.
- [x] PS46/2025-03-07 spot-check PASS on 3 byte-equal outputs (Phase 7a.2 tongue + jaw + Phase 6 spatial heatmap).
- [x] DECISIONS 2026-05-15 entry (8 decisions) + this MIGRATION_LOG entry.

**Forward-pointers queued.**

- **Phase 7c-dlc-cohort-reemit (new — primary forward-pointer).** Cohort-wide DLC kinematics + spatial re-emit on post-8a.10.1 Phase 2 NPZs. Resolves Addendum #1's on-disk-string deferrals + provides cohort-wide byte-equality verdict. Folds in Phase 7a.7 (DLC heatmaps visual gate) as a sub-task. Blocks Phase 9 + pub-figures.
- **Phase 7-pre-alignment-templates (F-P-7 from Phase 8a.10.1 close).** Cohort-wide alignment template emit + consumer cutover.
- **Phase 7-pre-multi-half-dlc (F-P-5 from Phase 8a.10.1 close).** Pattern A DLC merge wiring; also discharges PS48 spot-check deferral from this phase's Decision 5.
- **Phase 9 stats.** Blocked on 7c.
- **Phase 7-pre-secondary-spout-compare-DLC.** Blocked on b-half DLC inference.
- **Pub-figures phase.** Blocked on 7c.

**Tag:** `v7b-light-dlc-narrative-cleanup` on the merge commit.

---

## Phase 7c.1 — Source-side on-disk-string renames (Addendum #1 deferrals from 7b-light) + 3-session pilot re-emit

**Date:** 2026-05-15
**Tag on merge:** `v7c.1-dlc-source-rename-and-pilot`
**Branch:** `phase/7c.1-dlc-source-rename-and-pilot`

**Scope.** Inverts Phase 7b-light's PRESERVED on-disk-string set (output subdir paths, NPZ schema keys, window-dir tokens, dataclass-field-with-on-disk-surface, family-name tokens, CLI flag spellings, figure filename suffixes, skip-counter narrative, notebook cell IDs, result-dict display narrative) — exactly the strings 7b-light deferred are the strings 7c.1 renames. Bifurcated via kickoff [Addendum #1](prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md): pilot scope locked to full per-session DLC pipeline (Categories A spatial + B interpolation + C per-trial features + D tongue angle figures + D-supplement tongue-jaw mismatch + D-supplement-2 jaw pertrial endpoints). Finding-A re-interpretation of PS54 verdict captured in [Addendum #2](prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md) (Phase 8a.10.1 Task 4.5 wrote to production paths, so legacy PS54 outputs are already post-fix; cohort-archeology implications for Phase 7c.2).

**What landed.** 10 commits on `phase/7c.1-dlc-source-rename-and-pilot`:

| # | SHA | Scope |
|---|-----|-------|
| 1 | `27c30bf` | docs(kickoff): kickoff doc with Q1-Q7 scoping decisions + bifurcation-rule inversion plan |
| 2 | `a06d99b` | refactor(C1): `dlc_spatial/` on-disk strings — Cat E family-name token + Cat G figure filename suffixes + Cat H figure titles (Cat A subdir literal pending C5) |
| 3 | `d975194` | refactor(C2): `dlc_kinematics/` on-disk strings — Cat C NPZ schema key + Cat B2 window-selector label + Cat D1/D2 dataclass fields |
| 4 | `0830567` | refactor(C3): `paths.py` `mean_sem_visual_dir()` Cat B1 window-dir token + docstring narrative + 13-hit test path-assertion lockstep |
| 5 | `533d53f` | refactor(C4): `configs/defaults.yaml` Cat E YAML sub-key rename + Cat F CLI flag chain lockstep (`--tone-windows-ms` + auto-derived attribute + local var + notebook constant) |
| 6 | `90b8bfc` | refactor(C5): notebook 12 + `scripts/run_notebook_12_first_emit.py` — Cat A subdir literal + Cat J notebook cell ID + Cat K result-dict + Cat F4 consumer + Cat I skip-counter + markdown narrative |
| 7 | `d55a847` | chore(C6): `scripts/phase_6_8a_first_run_health_report.py` inline-comment breadcrumb per Open Q §5.1 (PRESERVE; retires in Phase 7c.2 Task 5) |
| 8 | `17b1bf9` | test(Task 3): pilot driver Round 1 (Categories A + B only) |
| 9 | `7c354ff` | test(Task 3): pilot driver Round 2 rewrite + kickoff Addenda #1 + #2 (full A-D + D-supplements scope per Addendum #1) |
| 10 | _this commit_ | docs(close): DECISIONS + MIGRATION_LOG entries |

**Source-side renamed strings (inverted from 7b-light PRESERVED list):**

- **Cat A** — output subdir literal `spatial_reward_aligned` → `spatial_tone_aligned` (notebook 12 + script + tone_aligned.py docstring).
- **Cat B1 / B2** — window-dir tokens `rewardAligned_<N>pre-<M>post` (paths.py f-string) + `reward_<N>_<M>ms` label (window_selector.py).
- **Cat C** — NPZ schema key `n_rewards` → `n_tones` (tone_aligned.py NPZ writer).
- **Cat D1 / D2** — dataclass fields `InterpolationResult.reward_centers_cam` → `tone_centers_cam` (NPZ key) + `TrialEvent.reward_frame_idx` → `tone_frame_idx` (DataFrame column).
- **Cat E** — family-name token `"reward_aligned"` → `"tone_aligned"` (`_family_paths()` subdir + YAML sub-key under `tongue_visual.plot_families`).
- **Cat F1-F4** — CLI flag `--reward-windows-ms` → `--tone-windows-ms` + auto-derived attribute + local var + notebook constant `TONE_WINDOWS_MS`.
- **Cat G / H** — figure filename suffixes `mouseLrewards`/`mouseRrewards` → `mouseLtones`/`mouseRtones` + paired figure titles.
- **Cat I** — skip-counter log keys + counter vars (`n_skip_no_rewards` → `n_skip_no_tones`).
- **Cat J** — notebook cell ID `reward-loop` → `tone-loop` (notebook 12).
- **Cat K** — result-dict display narrative `f"rewards=..."` → `f"tones=..."`.

**Audit Open Questions resolved as proposed.** §5.1 PRESERVE `scripts/phase_6_8a_first_run_health_report.py` with inline-comment breadcrumb (retires alongside legacy tree in Phase 7c.2 Task 5); §5.2 RENAME `reward_windows_ms` → `tone_windows_ms` in lockstep with Cat F; §5.3 SKIP `_deprecated/` test file. STOP-and-report acceptance PASS — 0 AMBIGUOUS.

**Sessions piloted.** 3 of 3 per Q1.A — PS46/2025-03-07 (bilateral, swap-fix-invariant baseline) + PS54/2025-05-03 (withhold-bearing post-stroke) + PS50/2025-03-25 (post-tone-change regime sanity).

**Pilot verdict (Round 2, full A-D + D-supplements scope per Addendum #1): PASS.**

| Axis | Verdict |
|------|---------|
| PS46 Cat A byte-equality (modulo `n_rewards` → `n_tones` rename) | PASS — 54/54 heatmap NPZs byte-equal |
| PS46 Cat B interpolated_traces (sha256 anchor) | PASS — matches 7b-light Task 5 anchors |
| PS54 delta sanity (re-interpreted per Finding A) | PASS — uniform delta=+0 across 54 configs; legacy already post-fix |
| PS50 Cat A light sanity | PASS — 54/54 outputs, `n_tones` range 48-96, 0 anomalies |
| Cat B/C/D/D-supp/D-supp-2 execution on all 3 sessions | PASS — 61 outputs/session × 3 = 183 outputs total; manifest status=OK |

Verdict deliverable at [`.scratch_phase_7c1/pilot_verdict.md`](../.scratch_phase_7c1/pilot_verdict.md). Per-session manifest at [`.scratch_phase_7c1/pilot_manifest.csv`](../.scratch_phase_7c1/pilot_manifest.csv).

**Wall-time data for Phase 7c.2 budgeting.** Mean ~73 s/session = ~1.2 min/session for the full per-session DLC pipeline. Extrapolation across ~352 sessions: ~7-14 hr realistic cohort budget. Cross-session aggregates (Category E) are NOT in the per-session cost; they add a one-time cohort-completion compute pass on top. Tractable as a single 7c.2 phase; overnight runs sufficient.

**Finding A (PS54 verdict re-interpretation).** Kickoff Q1.A expected PS54 to show `+86 trial-event delta` vs legacy `spatial_reward_aligned/`; empirically observed `+0 delta uniformly` across all 54 configs. Cause: legacy PS54 outputs on MICROSCOPE are already post-Phase-8a.10.1-swap-fix (most plausibly written by Task 4.5 itself during the X1-β cascade-safety spot-check). Conclusion identical: rename is data-layer no-op. Implication for Phase 7c.2: mixed cohort state on legacy paths — Task 4.5 sessions are post-fix already; ~352 other sessions are genuinely pre-fix. 7c.2 verification design must accommodate both, with per-session classification recommended (cheap mtime check on legacy `heatmap_*.npz` files; Task 4.5 writes have mtime around the Phase 8a.10.1 close date 2026-05-14).

**Intentional behavior differences vs legacy.** None at the data level — phase is on-disk-string rename + pilot re-emit on the same post-Phase-8a.10.1 Phase 2 NPZs. New on-disk paths (`spatial_tone_aligned/`, `toneAligned_*`, `n_tones`, `tone_centers_cam`, `tone_frame_idx`, etc.) carry byte-identical content to the legacy paths' equivalents modulo the key/column renames.

**Exit criteria met.**

- [x] `pytest -q` (full unfiltered) PASSES at 1417 passed, 39 skipped, 0 failed — matches the post-Phase-7b-light baseline exactly.
- [x] All on-disk-string renames in lockstep across source + config + tests + notebook + scripts; no broken references.
- [x] Pilot verdict PASS on all 3 sessions across full A-D + D-supplements scope (183 outputs total; manifest `status=OK`).
- [x] DECISIONS 2026-05-15 entry (8 decisions) + this MIGRATION_LOG entry.

**Forward-pointers queued.**

- **Phase 7c.2-dlc-cohort-completion (primary forward-pointer).** Cohort-wide DLC kinematics + spatial re-emit on the renamed source for ~352 remaining sessions (Cohort A + Cohort B). Folds in Phase 7a.7 (DLC heatmaps visual gate) as a sub-task. Legacy-path cleanup (delete `spatial_reward_aligned/` etc. + retire `scripts/phase_6_8a_first_run_health_report.py`) in 7c.2 Task 5 after cohort verification PASSes. Phase 7c.2 Task 1 audit should add per-session legacy-state classification per Finding A. Blocks Phase 9 + pub-figures. Cohort budget: ~7-14 hr operational compute per Decision 8.
- **Phase 7-pre-alignment-templates (F-P-7).** Cohort-wide alignment template emit + consumer cutover; lands before or after Phase 7c.2.
- **Phase 7-pre-multi-half-dlc (F-P-5).** PS48 Pattern A merge wiring; Task 1 audit should classify PS48's per-site legacy state per Finding A's F-P-4 implication.
- **Phase 9 stats.** Blocked on Phase 7c.2.
- **Phase 7-pre-secondary-spout-compare-DLC.** Blocked on b-half DLC inference.
- **Pub-figures phase.** Blocked on Phase 7c.2.

**Tag:** `v7c.1-dlc-source-rename-and-pilot` on the merge commit.

---

## Phase 7c.2 close — Cohort-wide DLC kinematics + spatial re-emit + compute-on-demand spatial architecture + F-P-5 bundled + 2.15 GB legacy cleanup

**Tag:** `v7c.2-dlc-cohort-completion` (applied to merge commit on main).
**Branch:** `phase/7c.2-dlc-cohort-completion`.
**Kickoff:** [`docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md`](prompts/phase-7c.2-dlc-cohort-completion-kickoff.md) (59 addenda).
**DECISIONS entry:** 2026-05-21 (Decisions 1-27).

**What shipped:**

- Phase D cohort re-emit: 8 animals × {266 .. 686} individual_session + 28 each of binned_sessions / proportion_differences / unbalanced_ot SVGs = **4,144 SVGs total** at canonical paths under `pipeline_outputs/dlc_kinematics/{tone_aligned_heatmaps,whole_session_heatmaps}/`. Manifest at `.scratch_phase_7c2/cohort_heatmaps_manifest.csv` (8 canonical OK rows post Task 7.C collapse). Cohort runtime 23.4 hr (84,246s).
- Compute-on-demand spatial figure architecture (Q2.B / Addendum #3 Interpretation 1): cached Phase 6 NPZ tree eliminated; Phase 4 centered parquets are canonical whole-session spatial data; tone-aligned + whole-session heatmaps fold into Task 5 compute-on-demand wrappers (`src/stroke_orofacial/dlc_spatial/render_on_demand.py`).
- F-P-5 SessionManifest Pattern A wiring fix + PS48/2025-03-14 production force-emit (Task 2). Forward-pointer F-P-5 discharged in-phase.
- 7 family entries (Q10.C / Addendum #13): `tongue_spout_midpoint`, `tongue_eye_midpoint`, `jaw_eye_midpoint`, `nose_eye_midpoint`, `whiskers_eye_midpoint` (Pattern B 6-layer), `spout_spout_midpoint` (Pattern B 2-layer reference), `eye_eye_midpoint` (Pattern B 2-layer reference).
- Q67 YAML-driven cohort enumeration refactor (Addendum #57; in-phase forward-pointer discharge): new helper `stroke_orofacial.cohort_enumeration.yaml_driven_session_dates()` + refactor of 3 cohort drivers + 13 tests (8 parity-vs-Phase-D + 5 unit). Forward-pointer `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` discharged.
- Q68 retire legacy `scripts/phase_6_8a_first_run_health_report.py` (Addendum #57; per Phase 7c.1 audit §5.1). `task_runner_wrapper.sh` trimmed; cosmetic next-step references in `run_notebook_10/12` cleaned up.
- Q5.G + Q41 + CLAUDE.md Rule 7 one-time cleanup + manifest reset; **~2.15 GB legacy artifacts removed** across 9 cleanup categories (Cat 1 NPZ tree 2.03 GB / 27,642 files + Cat 9 mean_sem legacy 121 MB / 200 files + de-minimis Cats 2/4/5/8 cleared in initial pass; Cats 3/7 auto-pass; Cat 6 DROPPED per investigation — predicate would have deleted ~1,400 files of canonical Phase 7a.4 output).
- 27 DECISIONS entries documenting all locked iterative design choices + 5 new decisions (23-27) recording Task 7 outcomes, Q67/Q68 discharge, Q70/Q71 alignment-regime side-experiment, and Q51 cohort skip audit.

**Behavior changes vs prior phases:**

- Pattern B render uses legacy convention end-to-end per Q55 (alpha=1.0, transparent NaN via `cmap.set_bad((1,1,1,0))`, no magnitude-floor masking, plasma/inferno/viridis cmap-per-layer for whiskers 1/2/3). Q55 supersedes earlier Q39/Q47/Q30/Q53 speculative iterations. Q56 short labels (L_w1..R_w3). Q58 Pattern B PD layered overlay (w1=RdBu, w2=PuOr, w3=BrBG). Q59 per-bp extent for Pattern B PD. Q60 grid-summary row spacing (h_pad=0.3, hspace=0.4). Q61 Pattern B UOT layered overlay.
- PD plots use diverging red-blue cmap (red=increased, blue=decreased per Q25) + Q43.B no-data mask only (no magnitude-floor masking).
- UOT per-bin layout collapsed to 2 panels (`mass_change` + arrows) per Q33; Pattern B UOT layered per Q61.
- All grid-summary SVGs use Q60 row spacing.
- Per-animal singleton `bin_sizes_days` (Q23 / Addendum #22): PS46-50 emit bin2d only; PS51/54/55 emit bin7d only.
- Q17 H_proportion normalization with total-frame denominator universal.
- Q19/Q49 WS-bounded restriction on whole_session scope; new `_ws_cam_frame_bounds()` in `render_on_demand.py`.
- Q62 likelihood threshold experiment (0.80→0.70) accepted; Q63 cohort pass-rate audit + sparse warning (`_SPARSE_FRAME_WARN_THRESHOLD = 0.05`) added.

**Forward-pointers queued post-merge:**

- **Phase 7d-dlc-kinematics-naming-hygiene** (kickoff drafted): granularity-first layout migration for `dlc_kinematics/features/`.
- **Phase 7-pre-alignment-templates F-P-7** (kickoff drafted): cohort-wide alignment template emit + consumer cutover.
- **Phase 9 stats** (scoping drafted).
- **Phase 9.1 phenotype-pooled figures** (scoping drafted).
- **Pub-figures phase.**
- **Possible Q70/Q71 alignment-mode follow-on** depending on the in-progress side-experiment outcomes (`.scratch_phase_7c2_alignment_test/`). **Discharged 2026-05-21 via the alignment-regime archive PR #121 + Decision 26 amendment — see entry below.**

**Discharged in-phase:** F-P-5 (SessionManifest Pattern A wiring); cohort-enumeration YAML-driven refactor (was queued at Addendum #5 as a post-7c.2 chore-PR, promoted to in-phase via Q67 because Cat 1 cleanup depended on it).

**Tag:** `v7c.2-dlc-cohort-completion` on the merge commit.

---

## Phase 7c.2 follow-up — Alignment-regime side-experiment archive + Decision 26 amendment

**Date:** 2026-05-21

**Tag:** `v7c.2-alignment-regime-archive` (applied to merge commit on main).
**Branch:** `experiment/alignment-regime-sweep-2026-05-archive`.
**PR:** #121.
**Status:** Closes the Phase 7c.2 forward-pointer "Possible Q70/Q71 alignment-mode follow-on" above.

**What shipped:**

- **206 SVGs relocated** from `.scratch_phase_7c2_alignment_test/svg_comparison/` → `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/svg_comparison/<animal>/`. Breakdown: 14 Q64 IS-style 4-regime per-bp comparison SVGs + 144 Q70 tone_aligned PD-comparison SVGs (6 family entries × 8 animals × 3 trial_groups) + 48 Q71 whole_session PD-comparison SVGs (6 family entries × 8 animals × 1 trial_group). Cmap-direction bug fixed at Q70+Q71 launch — `[(0.0, blue), (0.5, grey), (1.0, red)]` matching Q25 canonical `_PROPORTION_DIFF_CMAP`.
- **Q72 + Q72-pre-stroke per-bin numeric aggregation CSVs** at the new tree: `per_bin_numeric_comparison.csv` (16,432 rows, all-bins) + `per_bin_numeric_comparison_pre_stroke.csv` (4,368 rows) + cross-animal + winner-summary variants of each + 2 markdown reports.
- **Per-animal cohort overview PNGs (4)** mirroring the 2026-04-19 sweep's `00_metric_overview_*.png` layout: `00_metric_overview_{pearson,js_divergence}_{pre_stroke,all_bins}.png`. Direct comparators to `notebooks/experiments/outputs/alignment_sweep/00_metric_overview_*.png` from the 2026-04-19 sweep (Decision 2026-04-19). Per-(animal, regime, bodypart) pairwise pooling across all pre-stroke or all-sessions session pairs. Histogram-edge logic ported from 2026-04-19 sweep cell 8 verbatim per Q13 audit-first ground rule.
- **`per_animal_metrics_{pre_stroke,all_bins}.csv`** (416 rows each: 8 animals × 13 bodyparts × 4 regimes) — companion numeric tables to the overview PNGs.
- **6 source scripts relocated** to `notebooks/experiments/` (sibling to `cross_session_alignment_sweep.ipynb`): `alignment_modes.py` (eye_affine + eye_rigid scratch implementations — do NOT ship to production; preserved as experimental-record companion to the eye_centered + spout_centered production code at `src/stroke_orofacial/dlc_io/centering.py`), `q64_lightweight.py`, `q65_pd_comparison.py`, `per_bin_numeric_comparison.py`, `per_bin_numeric_comparison_pre_stroke.py`, `per_animal_overview_figures.py`.
- **`summary.txt`** at the new tree: cohort + methodology + output-file index, cross-references to the 2026-04-19 baseline + DECISIONS Decision 26 + Phase 7c.2 kickoff Addenda #54-59.
- **Decision 26 amendment** landed in `docs/DECISIONS.md` lines 246-266 (separate docs-only follow-up PR, not bundled here): four findings from the pre-stroke re-analysis with net production impact = zero. See DECISIONS entry for full table.

**Scratch tree retained:** `.scratch_phase_7c2_alignment_test/centered_parquets/` (large, regenerable from production DLC outputs); `__pycache__/`; `_inspect_sweep_notebook.py` (528 B helper). Nothing Decision-26-loadbearing remains in scratch.

**Behavior changes vs production:** None. eye_affine + eye_rigid centering regimes remain non-production per Decision 2026-04-19; `alignment_modes.py` is experimental-record only. Phase 4.5-lite per-bodypart `center_mode` defaults at `configs/defaults.yaml` `dlc_spatial.bodyparts.*.center_mode` unchanged.

**Repo growth:** ~159 MB committed under `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/` + ~50 KB at `notebooks/experiments/*.py`. Acceptable for experimental-record tier given the precedent of the 2026-04-19 sweep folder also living under `notebooks/experiments/outputs/`.

**Cross-references:**

- **DECISIONS Decision 26 + amendment:** `docs/DECISIONS.md` lines 234-266.
- **Baseline:** `notebooks/experiments/outputs/alignment_sweep/` (2026-04-19 sweep; Decision 2026-04-19 enforcement clause).
- **Kickoff Addenda:** Phase 7c.2 Addenda #54 (Q64), #55 (Q65), #56 (Q66), #58 (Q70), #59 (Q71).

---

## Phase 7d close — dlc_kinematics/ granularity-first naming hygiene + PathResolver-bypass sweep

**Date:** 2026-05-22

**Tag:** `v7d-dlc-kinematics-naming-hygiene` (applied to merge commit on main).
**Branch:** `phase/7d-dlc-kinematics-naming-hygiene`.
**Kickoff:** [`docs/prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md`](prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md) (4 addenda).
**DECISIONS entry:** 2026-05-22 (Decisions 1-8).

**What shipped:**

- **`dlc_kinematics/` granularity-first layout migration.** Three on-disk paths renamed per Addendum #1 Option A lock (method names preserved; only path strings inside resolver method bodies change):
  - `dlc_kinematics/features/tongue/` → `dlc_kinematics/per_frame/tongue/` (257 parquets).
  - `dlc_kinematics/endpoints/` → `dlc_kinematics/per_trial/tongue/` (257 JSONs).
  - `dlc_kinematics/jaw_pertrial/endpoints/` → `dlc_kinematics/per_trial/jaw/` (248 JSONs).
  - **762 files moved total**, byte-identical migration verified via per-file sha256 (empty diff on the sorted hash-column comparison). Snapshot files at `.scratch_phase_7d/pre_migration_hashes.txt` + `post_migration_hashes.txt` (gitignored).
- **Final `dlc_kinematics/` tree** (post-migration): `per_frame/`, `per_trial/`, plus unchanged `licking_dynamics/`, `mean_sem/`, `tone_aligned_heatmaps/`, `tongue_angle/`, `tongue_jaw_mismatch/`, `whole_session_heatmaps/`. Old `features/` + `jaw_pertrial/` parent dirs removed via `rmdir` (non-recursive, safe).
- **6 new PathResolver methods + 9 new unit tests** across Phase 7d Tasks 2 + 6:
  - Task 2 (Addendum #2 / Option A.2): `tongue_pertrial_endpoints_dir(animal)` — discharges 2 pre-existing PathResolver-bypass call sites (`tongue_pertrial.py:966-969`, `tongue_angle_cohort.py:397-400`) that the Task 1 audit surfaced.
  - Task 6 (Addendum #4 / Sweep-A): `dlc_centered_parquet_dir(center_mode, animal)`, `spout_licks_and_rewards_npz(animal, date, *, session_suffix)`, `interpolated_trace_dir(bodypart, animal)`, `tongue_jaw_mismatch_candidate_trials_dir(animal)`, `spatial_tone_aligned_npz(...)`. Discharged 17 audit findings + 1 audit-missed parquet.py:213 site + 2 audit-missed `spout_close_vs_std.py:212-213` sites via the `session_suffix=` extension.
- **PathResolver-bypass sweep (Addendum #3 promotion).** Original audit catalog at [`.scratch_phase_7d/bypass_sweep_audit.md`](../.scratch_phase_7d/bypass_sweep_audit.md). 17 findings → all discharged in-phase per Sweep-A lock. Step-5 re-grep verification: 0 unresolved findings outside `paths.py` + `_writeguard.py` for the strict 5 audit patterns, except finding #14 (intentional Type L per Addendum #4).
- **Finding #14 — Type L (visual_gate.py:217-218).** `_resolve_session_npz_path` parametric routing helper kept as inline `sp_root / output_type / animal`. PathResolver covers the tree-root via the local `sp_root = pipeline_outputs("spout_behavior")` capture at line 223; per-output_type routing logic stays in-helper. Explanatory comment landed at the construction site.
- **Writeguard Pattern 2 — Type N/A.** `_writeguard.py` deny-list (12 hardcoded absolute path strings) is declarative configuration data, the writeguard's source of truth analogous to `paths.py`. Excluded alongside `paths.py` from future bypass-sweep methodology.
- **4 additional Type-L routing helpers documented (post-audit re-grep surfacing).** `session_processing.py:_output_path` + `_per_half_output_path` + `_params_json_path` + `dlc_io/parquet.py:_save_dlc_session_params` — all private helpers taking `output_root` as a function parameter; routing logic stays in-helper. Analogous to finding #14; no fix needed.

**Behavior changes vs prior phases:**

- **Pure on-disk-layout change for the 3 migrated paths.** No semantic data change; sha256-verified byte-identical migration. Existing analyses that read these paths via PathResolver are transparently routed to the new locations (method names preserved per Addendum #1 Option A).
- **2 latent bugs in `tongue_pertrial.py:compute_pre_stroke_median_ili_ms` and `tongue_angle_cohort.py:_enumerate_session_dates` fixed.** These manually globbed the old `dlc_kinematics/endpoints/` directory and would have silently returned NaN / empty list after the Task 4 mv. Both now use `resolver.tongue_pertrial_endpoints_dir(animal)`.

**Forward-pointers queued post-merge:**

- **Future bypass-sweep methodology:** the 4 Type-L routing helpers documented above are not a Phase-7d-bug; they ARE the routing layer (output_root parameter + parametric output_type + literal subdir). If a future phase wants to fully eliminate captured-root + parametric-subdir patterns, that's a follow-on chore. Documented for traceability.

**Test count:** 1502 baseline → 1512 collected (1466+ passed + 39 skipped). 10 new tests added across Tasks 2, 6a-6f. Zero regressions.

**Acceptance criteria (kickoff base text + Addendum #3 5th axis):**

1. Test suite passes at post-7c.2 baseline + new tests (1512 collected; full suite green).
2. Data migration byte-identical (sha256 verified, empty diff on sorted hash column).
3. New paths populated; old paths empty (`features/` + `jaw_pertrial/` removed via `rmdir`).
4. PathResolver methods return new paths (`tongue_pertrial_angle_parquet` → `per_frame/tongue/`, etc.).
5. PathResolver-bypass sweep complete: 17 audit findings discharged + 3 audit-missed sites discharged + 5 Type-L cases documented + step-5 re-grep returns 0 Pattern-1 findings outside `paths.py` + `_writeguard.py`.

**Tag:** `v7d-dlc-kinematics-naming-hygiene` on the merge commit. Tag message: "Phase 7d: dlc_kinematics granularity-first naming hygiene + PathResolver-bypass sweep — per_frame/ + per_trial/<bodypart>/ layout + bypass surface discharged".

---

## Phase 7-pre-alignment-templates — Cohort-wide alignment template emit + consumer cutover (F-P-7)

**Date:** 2026-05-22

**Tag:** `v7-pre-alignment-templates` (applied to merge commit on main).
**Branch:** `phase/7-pre-alignment-templates`.
**Kickoff:** [`docs/prompts/phase-7-pre-alignment-templates-kickoff.md`](prompts/phase-7-pre-alignment-templates-kickoff.md) (3 addenda).
**DECISIONS entry:** 2026-05-22 (Decisions 1-8 + forward-pointers).
**Verdict doc:** [`.scratch_phase_7_pre_aligntmpl/verdict.md`](../.scratch_phase_7_pre_aligntmpl/verdict.md) (5 axes, all verified).

**What landed (~11 commits on `phase/7-pre-alignment-templates`):**

- **Doc commits (4):** Addendum #1 warm-start state refresh; Addendum #2 Task 1 post-execution refinements (L4 SKIP_NO_INPUT + L5 analysis_context=alignment); Addendum #3 Task 2+3 post-execution refinements (L6 SKIP threshold + L7 outliers + L8 parity tolerance + L9 in-phase PS55/2025-06-06 fix); Addendum #3 L7+L9 update (Task 3.5 Hypothesis C + schema A1 lock).
- **Cohort emit drivers (commit `4c1c0b4`):** `scripts/phase_7_pre_aligntmpl/emit_cohort.py` + `parity_validate.py`.
- **`alignment_template_for_reading()` PathResolver method (commit `42580e5`):** new canonical read entry with prefer-new + fallback-legacy semantics; 3 unit tests.
- **`wavesurfer_file_overrides:` schema (commits `363cf0c` + `cbb20a3`):** new top-level section in `configs/session_overrides.yaml`; plumbing through `find_wavesurfer_file` (new optional `preferred_filename=` kwarg) + `manifest.py` (new `load_wavesurfer_file_overrides` + `get_wavesurfer_file_override` helpers); 5 new tests; PS55/2025-06-06 entry pinning `stroke_0002.h5`.
- **8 consumer call-site cutovers (commit `deb8603`):** Addendum #1 S2's 7 sites + 1 audit-missed at `timebase.py:259` (Decision 7); 4 mock-fixture updates.
- **Test fixture follow-up (commit `ede86bb`):** `test_derive_trial_events_raises_on_missing_alignment_template` signature + monkeypatch update.
- **Parity_validate refinements (commit `f0b4dc3`):** rtol=1e-5, atol=1e-6, equal_nan=True default + `allow_pickle` legacy-quirk filter.

**Outputs.** 280 alignment templates emitted to `pipeline_outputs/dlc_analysis/alignment_templates/cam2/`:

- PS46: 21 NPZs (21 OK single_half)
- PS47: 21 NPZs (21 OK single_half)
- PS48: 23 NPZs (20 OK single_half + 1 multi_half_A × 3 NPZs)
- PS49: 22 NPZs
- PS50: 19 NPZs
- PS51: 53 NPZs (51 single_half + 2 b-half)
- PS54: 63 NPZs (52 single_half + 11 b-half)
- PS55: 58 NPZs (51 single_half + 6 b-half + 1 PS55/2025-06-06 from Task 3.6D post-fix)

Sum: 21 + 21 + 23 + 22 + 19 + 53 + 63 + 58 = **280** ✓. New tree is now authoritative; consumers use `alignment_template_for_reading()` (prefer-new + fallback-legacy).

**Behavior diff vs legacy:**

- 275/278 emitted sessions differ from legacy at scipy 1.15→1.17 drift magnitude (scientifically equivalent under `assert_allclose(rtol=1e-5, atol=1e-6, equal_nan=True)`).
- PS55/2025-05-02 NPZ has shape `(908112,)` vs legacy `(908111,)` due to legacy CSV-loader trailing-row-drop bug (Decision 4); new pipeline is more correct.
- PS48/2025-03-14 multi-half template merged from per-half templates via `compute_and_merge_alignment_multi_half` (legacy had single template; new produces merged-from-halves).
- **Consumer outputs BIT-IDENTICAL pre/post cutover** (Decision 6 integer-rounding firewall). 5-session functional-equivalence spot-check (`functional_equivalence_magnitudes.md`): all `TIER_2_DISCRETE_IDENTICAL` with `max_abs = max_rel = 0.000e+00`. Phase 9 readiness unconditional.

**Forward-pointers from this phase:**

- **F-P-5 (Phase 7-pre-multi-half-dlc):** DISCHARGED in Phase 7c.2 Task 2 (not this phase). Documented for completeness per Addendum #1 S1.
- **Cohort-enumeration-YAML-driven forward-pointer:** CO-DISCHARGED via this phase's emit driver (Decision 2 — the YAML-driven enumeration IS the recommended pattern).
- **Phase 9 stats:** NEXT per Phase 7c.2 Decision 23 ordering lock.
- **Phase 9.1 phenotype-pooled figures:** queued post-Phase-9.
- **Pub-figures phase:** queued post-Phase-9.1.

**Tag:** `v7-pre-alignment-templates` on the merge commit. Tag message: "Phase 7-pre-alignment-templates: F-P-7 cohort emit + 8-site consumer cutover from legacy tree + wavesurfer_file_overrides schema + integer-rounding firewall finding".

---

## Chore — Tongue-jaw-mismatch comparison_grids/ subtree deletion (audit PR #127 follow-up)

**Date:** 2026-05-25
**Tag on merge:** none (chore-PR per F-P-6 convention)
**Branch:** `chore/cleanup-tongue-jaw-mismatch-comparison-grids`

**Scope.** Discharge the single LEGACY-CANDIDATE identified by audit PR #127 (`chore/audit-stale-output-dirs`): `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/comparison_grids/` (20.0 MB). Leftover from a Phase 7a.6 cohort_run iteration when the parity runner emitted into `pipeline_outputs/`; current `tests/scripts/parity_phase7a6_visual_gate.py` writes to `.scratch_7a6/cohort_run/comparison_grids/` by default. No `src/` or active-notebook reference for the `pipeline_outputs/` subtree.

**What landed.** Single commit on `chore/cleanup-tongue-jaw-mismatch-comparison-grids`:

1. `rm -rf` of the on-disk subtree after per-invocation Priya approval ("go ahead", 2026-05-25).
2. [`docs/DECISIONS.md`](DECISIONS.md) entry (2026-05-25).
3. This MIGRATION_LOG entry.

**Tree deleted** (size from audit report's pre-`rm` `du`):

- `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/comparison_grids/` — 20.0 MB

Pre-`rm` `du -sh` re-verification: 20.0 MB ✓ (matches audit report baseline at PR #127). Post-`rm` re-verification: `PATH_NOT_FOUND`. Sibling subtrees verified intact (`candidate_trials/`, `cross_session/`, `within_session/`).

**Intentional behavior differences vs legacy.** None. The deleted subtree was not consumed by any active source path. `tests/scripts/parity_phase7a6_visual_gate.py` retains its `.scratch_7a6/cohort_run/comparison_grids/` default emit target.

**Total reclaimable to date** (Phase 7c.2 PR #126 + this chore): ~160 MB across 4 dirs.

**Forward-pointers queued.** None.

**Tag:** none (chore-PR per F-P-6 pattern).

---

## Chore — Stale Phase 7c.2 spatial output trees deletion + notebooks 11/12 deprecation

**Date:** 2026-05-23
**Tag on merge:** none (chore-PR per F-P-6 convention)
**Branch:** `chore/cleanup-stale-spatial-output-trees`

**Scope.** Discharge the Phase 7c.2 Task 7 residual (kickoff lines 531/597) that did not eliminate three `pipeline_outputs/dlc_analysis/spatial_*/` trees totaling ~140 MB. None of these are Phase 9 inputs — Phase 9 consumes `dlc_analysis/centered_*/` parquets via `render_on_demand.compute_animal_aggregated_histogram`. The deleted trees are pure dead state from the per-session-NPZ-cache era that Phase 7c.2 Addendum #3 Q2.B (Interpretation 1) replaced with compute-on-demand histograms.

**What landed.** Single commit on `chore/cleanup-stale-spatial-output-trees`:

1. `git mv notebooks/11_dlc_spatial_whole_session.ipynb notebooks/_deprecated/` + `git mv notebooks/12_dlc_spatial_tone_aligned.ipynb notebooks/_deprecated/`, each with a deprecation-header markdown cell prepended at index 0.
2. [`docs/DECISIONS.md`](DECISIONS.md) entry (2026-05-23 chore close record).
3. This MIGRATION_LOG entry.
4. `rm -rf` of three on-disk trees after per-invocation Priya approval (per CLAUDE.md Ground Rule 7).

**Trees deleted** (sizes from `.scratch_phase_9/spatial_dir_disposition.txt` immediately pre-deletion):

- `pipeline_outputs/dlc_analysis/spatial_tone_aligned/` — 136 M
- `pipeline_outputs/dlc_analysis/spatial_visual_gate/`  — 3.4 M
- `pipeline_outputs/dlc_analysis/spatial_whole_session/` — 560 K
- **Total:** ~140 MB reclaimed.

**Preserved as dormant.** `paths.py:spatial_tone_aligned_npz` resolver method + `dlc_spatial.tone_aligned.py` `emit_cache=False` parameter remain in-place. Both are documented as inspection-only opt-in utilities; the Phase 7c.2 production driver never sets `emit_cache=True`. Cheap to keep; potential future use.

**Intentional behavior differences vs legacy.** None. The deleted trees were not consumed by any active Phase ≥ 7c.2 code path. Phase 9 spatial materialization is unaffected (verified via parallel cohort emit run on `phase/9-stats` during this chore).

**Exit criteria met.**

- [ ] Notebook moves staged as `R` renames in `git status` (verified pre-commit).
- [ ] DECISIONS 2026-05-23 entry + this MIGRATION_LOG entry land in the same commit as the notebook moves.
- [ ] Re-`du -sh` immediately pre-`rm -rf` matches the original disposition file (defensive check; abort if sizes drifted).
- [ ] Per-invocation Priya approval obtained for each `rm -rf`.
- [ ] Post-`rm` re-verification: three target dirs report "No such file or directory" or 0 bytes.

**Forward-pointers queued.** None.

**Tag:** none (chore-PR per F-P-6 pattern).

---

## Phase 9 — Behavioral statistical analyses on consolidated outputs

**Date:** 2026-05-25
**Tag on merge:** `v9-stats-behavioral`
**Branch:** `phase/9-stats`
**Kickoff:** [`docs/prompts/phase-9-stats-kickoff.md`](prompts/phase-9-stats-kickoff.md) (**11 addenda**)
**Scoping docs queued for follow-on phases:**
- [`docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`](prompts/phase-9.1-phenotype-pooled-figures-scoping.md) (Phase 9.1 — V4/V5 + pub-polish; ~5-7 days CC)
- [`docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md`](prompts/phase-9.x-nonlinear-recovery-fit-scoping.md) (Phase 9.x — per-phenotype stats + per-animal nonlinear fits; ~10-15 days CC)

**DECISIONS entry:** 2026-05-25 (8 sub-decisions covering architecture, methodology, deviations, headline findings).
**Verdict doc:** [`.scratch_phase_9/verdict.md`](../.scratch_phase_9/verdict.md) (Task 8 verification gates; 4 CC-owned + 2 Priya-eyeball).
**Trial-count bias investigation:** [`.scratch_phase_9/_trial_count_bias_findings.md`](../.scratch_phase_9/_trial_count_bias_findings.md) (Addendum #11; NO BIAS CONFIRMED).
**Running close-state notes:** [`.scratch_phase_9/notes_running.md`](../.scratch_phase_9/notes_running.md).

**Scope.** Behavioral statistical analyses on the consolidated Phase 7c.2 spatial + Phase 7a kinematics + Phase 8a.10 spout-behavior outputs. Materializes a per-endpoint long-format parquet tree under `pipeline_outputs/stats/inputs/`; runs per-axis hypothesis tests with multi-granularity dispatch; emits a structured result tree + headline summary CSV + figure family. Discharges the Phase 8a.10 `recovery_trajectories` plot-family forward-pointer.

**What landed.** ~30 commits on `phase/9-stats`:

**Stats module (Task 3, commit `17650e6`).** 5 modules + 115 tests under `src/stroke_orofacial/stats/`:
- `recovery_epochs.py` — `assign_epoch_label` + `cohort_phenotype_summary`
- `normalization.py` — `per_animal_baseline_stats`, `difference_from_baseline` (additive Task 4 LMM input), `zscore_to_baseline`, `ratio_to_baseline`, `log1p_transform`, `rank_within_animal`
- `multiple_comparisons.py` — `benjamini_hochberg_fdr`, `bonferroni_correct`, `bonferroni_holm_within_endpoint` (Addendum #10), `apply_correction_to_results_df`
- `permutation.py` — `paired_permutation_null`, `unpaired_permutation_null`, `permutation_p_value`, `bootstrap_ci` (BCa)
- `models.py` — `FitResult` + 7 fit_* model wrappers (`fit_paired_pre_post_wilcoxon`, `fit_ipsi_contra_wilcoxon`, `fit_trial_group_friedman`, `fit_pre_post_ks_distribution_shape`, `fit_recovery_mixedlm`, `fit_per_epoch_lmm`)

**Per-axis runners (Task 4, commit `e608fe2`).** `src/stroke_orofacial/stats/runners.py` + `scripts/phase_9_stats/run_stats_axis.py`. 4 axes (`pre_post`, `recovery`, `ipsi_contra`, `trial_group`) × 3 granularities (`per_session`, `per_bin`, `per_epoch`) dispatch. Result tree: `pipeline_outputs/stats/results/<axis>/per_<granularity>/<endpoint>.csv` + `_all.csv` concat. **456 fits × 465 CSV files** at cohort emit; BH-FDR within (axis, comparison) family + Bonferroni within confirmatory subset.

**Cohort spatial emit (Task 2, commits `dcf4458` → `45383e8` → `5723b04`).** 384 spatial parquets (3 metrics × 4 families × 4 scope/trial_group combos × 8 animals) emitted serial at `n_jobs=1` in **23.9 hr** (parallel attempts at `n_jobs=4` showed 1.1× speedup due to SMB I/O contention). 651-row unified materialize manifest with `materializer_pass` provenance column.

**Headline summary CSV (Task 5 + Addendum #10, commit `bb5d09f`).** `.scratch_phase_9/task_5_headline_summary.csv`:
- v1: 105 rows (initial single-summary per per_epoch endpoint)
- **v2: 306 rows** (per-coefficient pre-vs-each-epoch extraction; canonical Phase 9 deliverable)

Per-(axis × comparison) confirmatory significance at v2:
- `recovery` × `pre_vs_acute`: 15/15 Bonferroni-pass
- `recovery` × `pre_vs_sub_acute`: 15/15
- `recovery` × `pre_vs_chronic`: 12/15
- `recovery` × `continuous_rel_day_slope`: 11/11
- `recovery` × `continuous_bin_midpoint_slope` (spatial): 4/4
- `ipsi_contra` × `collapsed_post`: 6/10
- `pre_post` × `collapsed_post`: 5/12

**Recovery-axis dominance:** 13/14 Bonferroni-pass — the headline result of Phase 9. Pattern is "transient deficit recovers" — pre_post collapsed-post weak, per-epoch strong.

**recovery_trajectories plot family (Task 6, commit `682cefd`).** `src/stroke_orofacial/spout_behavior/recovery_trajectories.py::plot_recovery_trajectories_with_fit` + `visual_gate.py::render_recovery_trajectories` + `notebooks/01_spout_behavior_figures.ipynb` `INCLUDE_RECOVERY_TRAJECTORIES` toggle. Per-mouse scatter + cohort LMM fit + bootstrap CI ribbon (clipped to per-animal x-range). Discharges Phase 8a.10 forward-pointer.

**Task 7 figure family (commit `19c507b`).** `src/stroke_orofacial/stats/figures.py` + `scripts/phase_9_stats/build_task_7_figures.py`. **76 figures × 2 formats = 152 files** at `pipeline_outputs/stats/figures/`:
- `headlines/<endpoint>/` — V1 per_session scatter + LMM, V2 per_bin mean/SEM, V3 per_epoch boxplot with Bonferroni-Holm asterisk annotations (21 figures for 7 headline kinematics)
- `per_animal/<endpoint>/` — recovery_curve + paired_diff distributions per axis (48 figures for 16 confirmatory)
- `forest_plots/` — one per (axis, comparison) family (7 figures)

**Verification (Task 8, commit `783fa05`).** 4 CC-owned gates + 2 Priya-eyeball gates. All 4 CC gates PASS (7/8 methodology sanity + 4/5 internal consistency + permutation reproducibility + 1/12 LOO flag at `latency_hist` deferred to Phase 9.x). Priya signed off Gate 5 + Gate 6 PASS 2026-05-25.

**Trial-count bias investigation (Task 8 mid-flight, commit `329c4ce`; Addendum #11).** Hypothesis tested 2026-05-25 (Priya methodological concern): tongue acute coefficients may be inflated by low-n-trial sessions in PS51/PS54/PS55 acute. **Verdict: BIAS NOT CONFIRMED.** Direction was OPPOSITE the predicted pattern (low-n acute sessions had LOWER, not higher, session means). Counterfactual LMM at n_min=10 filter shifted acute coefficients by ≤4%. Alternative mechanism documented: engagement-correlated trial count + excursion. **Strengthens** recovery-dynamics interpretation. No production change.

**Outputs.**

| deliverable | path | count / size |
|---|---|---|
| Stats inputs parquets | `pipeline_outputs/stats/inputs/<endpoint>/<animal>.parquet` | 651 parquets, ~9 MB |
| Stats results CSVs | `pipeline_outputs/stats/results/<axis>/per_<gran>/<endpoint>.csv` + `_all.csv` | 465 CSVs |
| Stats figures | `pipeline_outputs/stats/figures/{headlines,per_animal,forest_plots}/` | 76 figures × 2 formats |
| recovery_trajectories per-mouse | `pipeline_outputs/spout_behavior/spout_behavior_figures/<animal>/recovery_trajectories.<endpoint>.{svg,png}` | per-mouse × 15 default endpoints |
| Headline summary CSV | `.scratch_phase_9/task_5_headline_summary.csv` | 306 rows (v2) |
| Manifest | `.scratch_phase_9/materialize_manifest_full.csv` | 651 rows |

**Intentional behavior differences vs legacy.** This is a new analysis tier with no legacy counterpart — `behavior_report_PS.py` style analyses produced per-animal figures + raw stats tables but no consolidated multi-axis hypothesis-test sweep. Phase 9's output tree is the new canonical reference; legacy outputs preserved on disk for archival comparison.

**Behavior diff caveats.**
- `lickRate_byTrial` (24,793 rows) vs tongue per-trial (24,023 rows) — 770 row diff from different trial-inclusion sources. Documented in Decision 6.
- `lick_switch_rate` "to" semantics flip vs initial Commit A "from" semantics — matches legacy `render_switchiness_bySession` destination convention.
- `latency_hist` flat-per-trial schema (Commit B emit choice) vs Addendum #4 `vector_per_session` spec — runner bridge in `runners._ks_on_flat_per_trial` (Task 4 deviation #2).

**Forward-pointers carried out of Phase 9.**

- **Phase 9.1** — V4/V5 phenotype-pooled figures + phenotype-pooled spatial + pub-polish. Scoping at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`. ~5-7 days CC.
- **Phase 9.x** — Per-phenotype stats + per-animal nonlinear recovery fits (combined per Priya 2026-05-25 expanded scope). Scoping at `docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md`. 3-tier grouping: mild=4 / moderate-pool=2 (PS46+PS51) / severe=2. §7.5 sub_acute vxy + PS55-DLC-QC pointers from trial-count investigation. ~10-15 days CC.
- **Pub-figures phase** (speculative) — paper-quality polish phase blocked on Phase 9 + 9.1.

**Discharged in-phase.**
- Phase 8a.10 `recovery_trajectories` plot family (Task 6).
- Cohort-enumeration YAML-driven forward-pointer (co-discharged via Phase 9's use of canonical YAML-driven pattern throughout).

**Tag:** `v9-stats-behavioral` on the merge commit. Tag message: "Phase 9: behavioral statistical analyses on Phase 7c.2 + 7a kinematics + 8a.10 spout-behavior outputs".

---

## Phase 7e close — DLC tongue pre-clean + v7 detector pipeline migrated to production

**Date:** 2026-05-26

**Tag:** `v7e-dlc-tongue-preclean-v7` (applied to merge commit on main).
**Branch:** `phase/7e-dlc-tongue-preclean-v7`.
**Kickoff:** [`docs/prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md`](prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md) + [Addendum #1](prompts/phase-7e-addendum-1-task0-x-audit-verdict.md).
**DECISIONS entry:** 2026-05-26 (Decisions 1-6) supersedes 2026-05-25 drafted-state Decisions 1, 2, 3, 6 (amended per Addendum #1) and confirms Decision 14 scope shipped. 2026-05-25 drafted entry preserved as historical record.

**What shipped:**

- **3 new private modules** under `src/stroke_orofacial/dlc_kinematics/` (~1,610 lines total): `_preclean.py` (646 lines — cluster classifier Rules A/B + isolated-short override + frame-level outlier + PCHIP-extend + bracketed-interp + x-side Rules 1-4), `_detector_v2.py` (368 lines — find_peaks local-maxima detector + cross-detector dedupe), `_gates.py` (598 lines — F/D/E/M gates + parabolic_excise + spline_excise + early-M relaxation). Underscore-prefix signals internal API per DECISIONS 2026-05-26 Decision 6.
- **3 new private support files**: `_detector.py` extended with parameterized `_slope_detect_lick_peaks(mode="bounded"|"legacy")` per DECISIONS 2026-05-26 Decision 3 (avoids re-porting `detect_bounded_fall` from scratch); `_writers.py` (151 lines) extends existing writer pattern with `_write_cleaned_traces_atomic` + `_write_lick_events_atomic`; `LickEventRecord` dataclass per DECISIONS 2026-05-26 Decision 5.
- **2 new PathResolver methods**: `cleaned_trace(bodypart, animal, date)` + `lick_events(bodypart, animal, date)` in `src/stroke_orofacial/paths.py:497-560` returning `pipeline_outputs/dlc_kinematics/cleaned_traces/<bodypart>/<animal>/<date>.parquet` and `.../lick_events/<bodypart>/<animal>/<date>.parquet`.
- **37 new YAML keys** in `configs/defaults.yaml` under `dlc_kinematics.tongue_pertrial.{preclean, detector_v2, gates}` + `use_v7_pipeline: true` top-level flag. Every numeric constant from the scratch reference + Addendum #1 refinements externalized; no magic numbers in source per kickoff Hardcoded constants section.
- **2 new parquet outputs**:
  - `pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/<date>.parquet` — same schema as `interpolated_traces/` (y_final, x_final, is_interp_fill, is_baseline_fill) with `is_baseline_fill` updated to reflect pre-clean wipes per DECISIONS 2026-05-25 Decision 3. File-level metadata: `algorithm_version="v7"`, `feature_extraction_version="v7e.0"`, `interpolation_version="v5p3"`.
  - `pipeline_outputs/dlc_kinematics/lick_events/tongue/<animal>/<date>.parquet` — per-trial-per-lick schema: `animal, date, trial, side, lick_idx, t_ms, y, x, y_original, rise_start_ms, fall_end_ms, imputed, source, confidence, likelihood, peak_angle_deg, max_velocity_y_px_per_s`. Last two columns per DECISIONS 2026-05-26 Decision 5 (Task 7 metric updates folded into the lick_events schema rather than separate files).
- **Addendum #1 x-side Rules 1-5** all shipped: x snaps to x0 at baseline-fill (Rule 1); y-wiped frames excluded from x's PCHIP anchor set (Rule 2); `|x|>110 px` hard wipe (Rule 3); joint x+y short-burst wipe with direction-aware nearest-raw-flank rule (Rule 4); early-window M-gate relaxation 80→60 ms for peaks in `t_ms<250 ms` (Rule 5). Decision 6 from 2026-05-25 RESOLVED via DECISIONS 2026-05-26 Decisions 1 + 2.
- **80 new unit tests** under `tests/`: `test_preclean.py` (628 lines, 32 tests covering cluster classifier Rules A/B/isolated-short, frame outlier, PCHIP-extend, bracketed-interp, x-side Rules 1-4), `test_detector_v2.py` (444 lines, 16 tests covering find_peaks rise/fall validation + cross-detector dedupe), `test_gates.py` (526 lines, 23 tests covering F/D/E/M gates + parabolic/spline excise + early-M relaxation). 1 new fixture-based parity test (`test_v7_parity.py`, auto-skipped pending fixture population by a CC follow-up commit on this branch).
- **Parity validation harness** at `.scratch_phase_7e/parity_v7_canonical.py` (gitignored scratch — runs against real MICROSCOPE data). On the 9 canonical hard trials: 6 exact PASS + 3 EXPECTED-PER-ADDENDUM-1 + 0 TRUE FAIL per DECISIONS 2026-05-26 Decision 4.
- **CI-portable fixture-based parity test scaffolding** at `tests/test_v7_parity.py` + `.scratch_phase_7e/gen_v7_canonical_fixtures.py` + `tests/fixtures/v7_canonical/README.md`. Test auto-skips when fixtures absent; CC follow-up commit runs generator + populates fixtures (~15-40 MB across 4 unique canonical-9 sessions) + un-skips test.

**Numeric verification (smoking-gun cases):**

- PS54 46L (canonical E-impute) — production `new_peak_x = +55.6991` = audit `+55.6991` (byte-equal); |Δangle| 7.75° → 0.0° (full correction delivered per DECISIONS 2026-05-26 Decision 2).
- PS51 26R (cross-detector verification after Task 5c three-detector restore) — production `new_peak_x = −38.2752` = audit `−38.2752` (byte-equal); confirms `_slope_detect_lick_peaks(mode="bounded")` parameterization preserves the bounded-fall detection behavior end-to-end.

**Behavior changes vs prior phases:**

- **Mean v7 detected-lick counts run 1-10 licks LOWER per trial than legacy** across the 80-trial cohort sample (PS48 -9.6, PS46 -4.6, PS47 -3.4, others 0.2 to 2.9). The delta is largely v7 correctly rejecting plateau-drift wobbles + late-trial fixture artifacts that legacy was counting as licks. A few real-lick drops exist as documented edge cases (M-gate confidence trade-off on 58L-style close pairs; F-gate on wide-flat lick tops). Per kickoff "Known limitations — documented and accepted".
- **`use_v7_pipeline: true` default ON** for new tongue_pertrial runs. Legacy path preserved behind the flag for backward compat; opt-out is per-invocation `use_v7_pipeline: false` in `configs/session_overrides.yaml`.
- **No cohort re-emit in this phase.** Materialized cohort-wide v7 outputs (cleaned_traces, lick_events, updated endpoints) gated on per-invocation Priya approval per CLAUDE.md Ground Rule 7. Per DECISIONS 2025-05-25 Decision 7 (deferred out of phase).

**Forward-pointers carried out of this phase:**

- **Cohort re-emit (~7-14 hr wall-time).** Per-invocation Priya approval per CLAUDE.md Ground Rule 7. Blocks Phase 9.1 + Phase 9 stats re-materialization. Co-trigger with the Phase 9.1 bundled finding #4 revision (per the Phase 9.1 / Phase 7e merge-dependency memory note).
- **80-trial cohort parity test** (`tests/test_v7_cohort_parity.py`). Deferred to follow-up chore PR per Priya 2026-05-26 AskUserQuestion answer. Fixture footprint ~40-100 MB across 8 sessions — needs design discussion on git-lfs vs. inline vs. MICROSCOPE-marker before landing.
- **Fixture-based 9-canonical-trial test** un-skip + fixture population on this branch. CC follow-up commit (`.scratch_phase_7e/gen_v7_canonical_fixtures.py` regeneration command in `tests/fixtures/v7_canonical/README.md`).
- **Phase 7f — jaw interpolation revisit** (DECISIONS 2025-05-25 Decision 8). v7 architecture generalizes (cluster classifier + frame outliers + PCHIP-extend + find_peaks + gates) but params are tongue-specific. Deferred until after Phase 7e tongue migration lands + downstream effects are validated.
- **F-gate refinement for wide-flat lick tops** (PS48 58L 1924 ms case). Hard to fix without shape-based discrimination (parabolic vs. triangular vs. flat). Documented limitation; no immediate fix queued.
- **M-gate non-greedy global selection** for 3-peak clusters within 150 ms (PS47 54R case). Documented limitation; current confidence-greedy approach is the accepted trade-off per DECISIONS 2025-05-25 Decision 2.
- **PS47 33L drops 14 vs legacy 15** — one unexplained gap; not a v7 regression vs. v6 but never fully diagnosed. Likely downstream detector quirk in a single-detector pass. Documented residual; no immediate diagnosis queued.

**Test count:** 1702 baseline → 1782 passing / 40 skipped / 0 fail (+80 new tests). `pytest --collect-only` passes with no collection errors.

**Acceptance criteria (kickoff Task 9 + Addendum #1 footer):**

1. Test suite passes at post-Phase-9.1-kickoff-draft baseline + 80 new tests (1782 passing, full suite green).
2. Numeric gate on PS54 46L + PS51 26R byte-equal vs audit (Δx=0.0, Δangle=0.0° both cases).
3. 9-canonical-trial parity harness: 6 exact PASS + 3 EXPECTED-PER-ADDENDUM-1 (rule-annotated) + 0 TRUE FAIL.
4. Addendum #1 Rules 1-5 shipped + Decision 14 three-detector scope shipped.
5. No files modified outside scope: `src/stroke_orofacial/dlc_kinematics/{_preclean,_detector,_detector_v2,_gates,tongue_pertrial,_writers}.py`, `src/stroke_orofacial/paths.py`, `configs/defaults.yaml`, `tests/`, `docs/prompts/phase-7e-addendum-1-task0-x-audit-verdict.md` (Task 5b footer), `docs/DECISIONS.md` (close-out section), `docs/MIGRATION_LOG.md` (this entry).
6. No destructive ops on `pipeline_outputs/`. No new branches. No force-push.

**Tag:** `v7e-dlc-tongue-preclean-v7` on the merge commit. Tag message: "Phase 7e: DLC tongue pre-clean + v7 detector pipeline migrated to production — find_peaks + bounded + legacy three-detector scope + Addendum #1 5 trace-level x rules + early-M relaxation".

---

## Chore — Phase 7e cohort re-emit (Event B) + Phase 7e.1 + Phase 7e.2

**Date:** 2026-05-26

**Tags applied during the chore sequence:** `v7e.1-legacy-endpoint-v7-routing` (PR #137 merge commit), `v7e.2-velocity-v7-routing` (PR #140 merge commit). This chore PR itself is untagged per CLAUDE.md tag rule (docs/data refresh, not a phase close).

**Branch:** `chore/phase-7e-cohort-reemit`.

**Kickoff:** [`docs/prompts/chore-phase-7e-cohort-reemit-kickoff.md`](prompts/chore-phase-7e-cohort-reemit-kickoff.md) + Addenda #1 (secondary-spout exclusion + output path doc fix), #2 (Stages 4/5/5b scope expansion + 9-PNG bundle override), #3 (Stage 6 stale-output audit + adjudication).

**DECISIONS entry:** 2026-05-26 Chore close — Phase 7e cohort re-emit (Decisions 1-7).

**What shipped (cohort-wide data refresh across ~6 dependent on-disk trees):**

- **Phase 7e.1 source code fix** (separate PR #137, merged + tagged before chore close): `_extract_lick1_lick2` accepts optional `v7_trial_result` kwarg; when present, lick1/lick2 emit consumes `kept_licks` (post v7 gate stack F/D/E/M) instead of raw legacy slope-detector output on pre-v7-preclean trace. Legacy path (`v7_trial_result=None`) preserved for backwards compat. +4 unit tests in `tests/test_tongue_pertrial.py`.

- **Phase 7e.2 source code fix** (separate PR #140, merged + tagged before chore close): `_extract_peak_velocity_first5` analogous routing — accepts `v7_trial_result` kwarg, when present derives per-lick vy/vxy peak from `y_clean`/`x_clean` with `is_baseline_fill_clean` NaN-masking inside `[rise_start_frame, fall_end_frame]` window. Mirrors v7's `max_velocity_y_px_per_s` per-kept-lick computation that already lived in the lick_events parquet writer. Required adding `rise_start_frame` + `fall_end_frame` to in-memory `kept_licks` dict (NOT in lick_events parquet schema — writer enumerates columns explicitly). +4 unit tests.

- **Stage 1 — Cohort tongue per-trial re-emit:** `scripts/phase_7e/reemit_tongue_pertrial_cohort.py`. 352 planned sessions (375 raw YAML - 24 secondary-spout via (b) pre-filter + 1 reconciliation rounding); 231 OK + 121 SKIP + 0 FAIL via (b) defensive YAML pre-filter + (c) runtime `interpolated_trace.exists()` check. Per-session mean 5.97 s post-7e.2; total wall ~23 min. Three Stage-1 re-runs total: pre-7e.1 baseline, post-7e.1 (revealed 12 zero_kept_licks_session sessions in PS51/PS54/PS55 May 2025 acute), post-7e.2 (confirms stable). Five per-session outputs per OK session: per_frame angle parquet, licking_dynamics traces parquet, per_trial endpoints JSON, cleaned_traces parquet (v7), lick_events parquet (v7).

- **Stage 2 — Phase 9 stats inputs re-materialize:** `scripts/phase_9_stats/materialize_inputs.py --endpoints tongue_*`. 23 tongue endpoints × 8 animals = 184 parquets re-emitted, 0 errors.

- **Stage 3 — Phase 9 stats runner re-emit:** `scripts/phase_9_stats/run_stats_axis.py --axis all --granularity all --endpoints tongue_*`. 23 endpoints × 3 in-scope axes (pre_post + recovery + ipsi_contra; trial_group correctly out-of-scope per inventory) × 3 granularities = 213 CSVs / 204 fits.

- **Stage 4 — Tongue mean+SEM cohort:** `scripts/phase_7e/reemit_tongue_mean_sem_cohort.py` (NEW, tongue-only wrapper around `build_mean_sem_cohort`). 8/8 animals OK, 6h 24m wall (ffmpeg MP4 encoding is the bottleneck; ~3-4 min/MP4 × multiple per (animal, window, mode)). 22 paths/animal = 176 total. `include_mean_video=True`.

- **Stage 4b — individual_sessions + trial_overlays:** `scripts/phase_7e/reemit_tongue_mean_sem_extras_cohort.py` (NEW). 8 animals × 2 stages × 2 windows = 32 OK / 0 FAIL, ~25 min. Re-emits the sibling mean_sem families that Stage 4's `build_mean_sem_cohort` doesn't cover.

- **Stage 5b — tongue_angle PNG bundle:** `scripts/phase_7e/reemit_tongue_followons_cohort.py` (NEW). Within-session (`render_tongue_qc_figures`): 231 OK + 144 SKIP, ~2,100 PNGs (~9/OK session). Cross-session (`build_tongue_angle_cohort`): 8 OK / 96 PNGs (12/animal). ~45 min total.

- **Stage 5c — Phase 9 stats figures:** `scripts/phase_9_stats/build_task_7_figures.py --mode all`. 76 figures × 2 formats = 152 files (21 headlines + 48 per-animal + 7 forest plots). Output at `pipeline_outputs/stats/figures/`.

- **Stage 6.4 destructive cleanup:** `scripts/phase_7e/stage6_4_delete_stale_per_trial_jsons.py --execute`. 26 stale per_trial JSONs surgically deleted (17 secondary-spout Pattern B + 9 out-of-cohort PS51/PS54/PS55 × 2025-04-16/17/18 Q1.C-excluded). 3 per-animal sidecars written at `dlc_kinematics/per_trial/tongue/{PS51,PS54,PS55}/_SKIPPED_NO_DLC_INPUT.md`. Post-delete verification: 0 stale remain. Companion-state row appended to `.scratch_chore_phase_7e_reemit/cohort_manifest.csv` (audit-trail-only; resume-on-relaunch ignores `status=DELETED`).

**Verification gates verdict:**

- **(a) Per-session smoke:** PASS for all 231 OK rows across all 3 Stage-1 re-runs. Gate (a) was relaxed mid-chore to treat `zero_kept_licks_session` (schema-intact but all-null lick1_y_peak) as OK-with-anomaly-note, after PS55/2025-05-07 case revealed the original gate conflated schema-broken with biology-empty.
- **(b) Cohort-level smoke:** PASS. 352 planned = 231 OK + 121 SKIP cohort-wide; deduped manifest matches.
- **(c) Per-endpoint row counts:** byte-equal pre vs post Event B (24,023 rows/endpoint × 23 tongue endpoints cohort-wide). Expected — schema row count = trials emitted; trials unchanged.
- **(d) PS54 acute lick1_y_peak distribution:** MATERIAL DOWNSHIFT confirmed post-Phase-7e.1. n=245→26, mean 188.70→110.87 px, median 201.71→112.85 (Δ−88.86). 89% of severe-acute "licks" were artifact peaks rejected by v7 gate stack.
- **(d)-extended (velocity endpoints):** DRAMATIC 8-37× downshift post-Phase-7e.2. Pre-7e.2 PS54 acute mean velocities 15-17 thousand px/s (biologically impossible, ~5 m/s movement, artifactual gradients across baseline-fill boundaries); post-7e.2 200-2,700 px/s (physiologically plausible).
- **(e) Stale-output audit comprehensiveness:** PASS. `.scratch_chore_phase_7e_reemit/stale_output_audit.md` covers every tongue-relevant subtree under `pipeline_outputs/`; 0 unclassified subtrees; 0 uncovered write sites; 1 notebook flagged for Cowork re-execution (`01_spout_behavior_figures.ipynb`).
- **(f) Adjudication closure:** PASS. Stage 6.4 destructive cleanup executed per per-invocation Priya approval. interpolated_traces classified (b) NOT-A-CONSUMER. phase_9_1_figures reclassified (d) IN-FLIGHT pending phase/9.1-figures branch merge.

**Behavior differences vs. legacy:**

- Severe-acute lick1_y_peak distribution shifts from artifactual ~188 px overshoot to ~111 px (aligned with mild + moderate-phenotype baselines). Paper-final cohort numbers from this chore supersede pre-Event-B values.
- Severe-acute velocity endpoint magnitudes shift 6-37× downward to biologically plausible ranges. Pre-7e.2 paper velocity numbers were artifact-dominated.
- Per-trial endpoints + downstream figures for the 121 SKIP sessions (no upstream DLC inference) remain absent on disk. 3 per-animal `_SKIPPED_NO_DLC_INPUT.md` sidecars document the exclusion classes.

**Forward-pointers carried out of chore:**

- **F-P-1 — v7-spatial-impact-audit follow-on chore PR** (per DECISIONS 2026-05-26 Decision 7): 3-session × 4-scope × 2-render audit of spatial heatmaps for v7 artifact-impact. Out-of-scope here; separate chore PR.
- **Stage 5 (tongue-jaw mismatch re-emit) — EXECUTION HOLD** lifted only after Phase 7f jaw audit/work completes. Mismatch detector consumes jaw interpolated traces which are being revised on `investigation/jaw-quality-audit` branch.
- **Phase 9.1 figures phenotype_pooled re-emit** — happens automatically when `phase/9.1-figures` branch Task 1c full-cohort emit runs against the v7-routed stats inputs this chore just refreshed.

**Files modified this chore PR:**

- `scripts/phase_7e/reemit_tongue_pertrial_cohort.py` (NEW; Stage 1 driver, 354 lines after Addendum #1 + smoke-gate-relax patch)
- `scripts/phase_7e/reemit_tongue_mean_sem_cohort.py` (NEW; Stage 4 driver)
- `scripts/phase_7e/reemit_tongue_mean_sem_extras_cohort.py` (NEW; Stage 4b driver)
- `scripts/phase_7e/reemit_tongue_followons_cohort.py` (NEW; Stage 5b driver)
- `scripts/phase_7e/stage6_4_delete_stale_per_trial_jsons.py` (NEW; Stage 6.4 surgical-delete script)
- `docs/prompts/chore-phase-7e-cohort-reemit-kickoff.md` (NEW; kickoff doc + Addenda #1/#2/#3)
- `docs/DECISIONS.md` (this chore's close entry)
- `docs/MIGRATION_LOG.md` (this entry)
- `.scratch_phase_9/materialize_manifest.csv` (Stage 2 manifest update, gitignored otherwise but pre-existing tracked file)

**On-disk outputs touched (data refresh, not in PR diff per gitignored pipeline_outputs/):**

- `pipeline_outputs/dlc_kinematics/per_trial/tongue/<animal>/*.json` — 231 re-emitted, 26 deleted, 3 sidecar READMEs added
- `pipeline_outputs/dlc_kinematics/per_frame/tongue/<animal>/*.parquet` — 231 re-emitted (byte-equal post-7e.2)
- `pipeline_outputs/dlc_kinematics/licking_dynamics/traces/<animal>/*.parquet` — 231 re-emitted (byte-equal)
- `pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/*.parquet` — 231 re-emitted (byte-equal post-7e.2)
- `pipeline_outputs/dlc_kinematics/lick_events/tongue/<animal>/*.parquet` — 231 re-emitted (byte-equal post-7e.2)
- `pipeline_outputs/dlc_kinematics/mean_sem/tongue/...` — 176 paths (Stage 4) + 32 stage-runs × ~21-49 PNGs (Stage 4b) re-emitted
- `pipeline_outputs/dlc_kinematics/tongue_angle/{within_session,cross_session}/...` — ~2,200 PNGs re-emitted
- `pipeline_outputs/stats/{inputs,results,figures}/tongue_*/...` — 184 input parquets + 213 result CSVs + 152 figure files

**Acceptance criteria:**

1. Gate (d) PS54 acute lick1_y_peak distribution shifts toward mild + moderate-phenotype baselines ✓ (Δmean=−77.83 px)
2. Gate (d)-extended velocity endpoints shift to biologically plausible ranges ✓ (8-37× downshift)
3. Phase 9 stats inputs + results re-emitted from v7-routed per_trial JSONs ✓ (231 OK animal-date pairs)
4. Mean+SEM + tongue_angle + stats figures re-rendered consistently across the cohort ✓
5. Stage 6 audit covers every tongue-relevant subtree + adjudicates 0 uncovered write sites ✓
6. Phase 9.1 ↔ Phase 7e Event B dependency DISCHARGED ✓ (Task 1c unblocks)
7. Per CLAUDE.md Ground Rule 7: no per-cycle `rm -rf`; destructive cleanup executed surgically with companion-state reset ✓
8. Per CLAUDE.md Ground Rule 8: branch verification before every commit; force-push only against explicit per-invocation Priya approval with lease guard ✓

**No tag** (chore PR, not a phase close).

