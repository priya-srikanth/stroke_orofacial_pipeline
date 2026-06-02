# Statistics Pipeline Design

Rationale and implementation details for the cross-animal statistics pipeline.

## Output layout — filter-variant wrapper convention

As of CC #9 (commit `16d1518`, 2026-06-01), both the results tree and the
figures tree share the same top-level **filter-variant wrappers**:

```
pipeline_outputs/stats/
├── results/
│   ├── filtered_v1/        # DLC filter applied (SessionFilter + per-metric TrialFilter)
│   ├── no_filter/          # unfiltered; renamed from results/none/ in 16d1518
│   └── phenotype_pooled/   # pooled outputs that consume across filter variants
└── figures/
    ├── filtered_v1/
    ├── no_filter/          # subsumes the old loose figures/{forest_plots, headlines, per_animal}/ siblings
    └── phenotype_pooled/
```

**Why a single wrapper convention:**
- Single canonical name for the unfiltered variant across results + figures +
  driver flags (no `none` vs `no_filter` mismatch). Driver flags accept
  `--filter-variant {filtered_v1, no_filter, phenotype_pooled}`; the value
  resolves directly to a subdir name on both sides.
- Symmetric `results/<variant>/` ↔ `figures/<variant>/` makes the producer-
  to-figure path inspectable by directory walk.
- `phenotype_pooled` as a peer wrapper at the same level (not nested under
  each filter) preserves the pooled outputs' "consume across filter variants"
  semantics — the pooled stats sheet reads `filtered_v1` inputs to match v3
  figures (DECISIONS 2026-06-01 entry), but the pooled tree lives at the same
  level as the variant trees it draws from.

**Source of truth:** `figures/_layout.py` holds the filter-variant constants
(`FILTERED_V1`, `FILTERED_V3` / `FILTERED_V3_NA_MASKED` for the figure-side
subtype-of-`filtered_v1` names, `NO_FILTER`) + the layout-derivation helpers
(`classify_scalar`, `pooled_scalar_endpoint_dir`). Both the pooled-scalar
writer (`figures/phenotype_pooled.py`) and the migration tool
(`scripts/chore_dlc_pooled_phenotype/path_normalization.py`) import these
names — single source of truth, no parallel string constants in producer
scripts.

## Filter-variant semantics

- **`filtered_v1`** — Phase 9 DLC filter: `DlcSessionFilter(min_trials_with_detected_lick=10)` + per-metric `DlcTrialFilter`. Drops sessions with too few detected licks; drops trials failing per-metric QC. After the CC #6 substrate routing fix, the session filter counts v7-cleaned `n_licks` (not interpolated/legacy) — see DECISIONS 2026-05-30 "SessionFilter effective-threshold tightening via v7-cleaned n_licks." The 5 lick-count endpoints zero-fill no-usable-lick sessions in `v3`; the prior NA-masked rendering is preserved as the `v3_na_masked` subtype (DECISIONS 2026-06-01).
- **`no_filter`** — pre-filter materialization. All sessions + all trials that pass the upstream substrate-existence guards (cleaned-trace + lick-events parquets exist on disk).
- **`phenotype_pooled`** — outputs that aggregate across animals into phenotype × epoch × side cells. Q12 spatial, Q13b phase-aligned endpoints, Q13/Q13c phase-aligned trajectories, scalar V4/V5 figures, Wasserstein recovery (absolute + normalized), consolidated pooled-phenotype stats sheet (MWU-session headline + `headline_sig` annotation channel for q13b + deck).

## Producer-side conventions

- **Per-bodypart producers** writing to a shared family directory use **chore-namespaced subdirs** to avoid clobbering. Reference: Wasserstein per-session output (DECISIONS 2026-06-01 "Wasserstein per-session producers de-collided via chore-namespaced subdirs"):
  - `q12_v2_emit.py` writes `wasserstein_recovery/<scope>/v2/tongue_jaw/`
  - `chore_whisker_nose_spatial/emit_cohort.py` writes `wasserstein_recovery/<scope>/v2/whisker_nose/`
  - The pooled-stats loader uses a recursive glob across both subdirs, then `drop_duplicates` on `(session_id, bodypart, side, phenotype, epoch, scope)` to handle cross-scope duplication (DECISIONS 2026-06-01 "Wasserstein loader `drop_duplicates`").
- **No raw/interpolated DLC for kinematic analysis** where a cleaned alternative exists. Tongue analyses consume the v7-cleaned trace (Phase 7e); jaw analyses consume the v3.4-cleaned trace (reconstructed in CC #9 stage 0b). Non-lick spatial bodyparts (whisker / nose / spout / eye) stay on raw DLC — accepted divergence (DECISIONS 2026-06-01) because no cleanup pipeline exists for those four bodyparts.
- **Every plotted figure persists its plotted data to a sidecar** (Priya directive 2026-06-01). For pooled families, this is the `per_session.csv` that lives alongside the figure's `mean_sem.csv` — see e.g. the normalized W-2 `per_session` write added in commit `27b421e`.

## Inferential test hierarchy

Locked across Q13 / Q13b / Q13c and the pooled-phenotype stats sheet (see
`memory/project_phase_9_1_unification_canonical_conventions.md`):

1. **LMM (primary)** — `fit_recovery_mixedlm` over per-animal × per-epoch values. **Non-estimable at the project's cohort size** (2-4 animals/phenotype after the 3-tier collapse) → dropped for the pooled sheet; available where cohort permits.
2. **Cluster permutation (secondary)** — used for trajectory families where appropriate.
3. **Session MWU (tertiary)** — Mann-Whitney on per-session means. **Headline test for the pooled-phenotype stats sheet** (DECISIONS 2026-06-01 "Pooled-phenotype stats: MWU-session headline"). The sheet exposes `headline_sig` (and `headline_and_bootstrap_sig` with `--n-boot 5000`) for downstream annotation.
4. **Trial-grain MWU is EXPLICITLY EXCLUDED** — 39-46% type-I error under H0 per Q13 null-calibration. Not a valid inferential tool in this framework.

BH-FDR correction is applied per family. See
`stats/multiple_comparisons.py` (`benjamini_hochberg_fdr`).

## On-figure significance annotation

`headline_sig` from the consolidated sheet (`build_pooled_phenotype_stats.py`)
drives both:

- **q13b panel top-band markers** — marker placed above the data area per
  (phenotype × epoch × side) cell crossing the headline threshold (no
  in-traces overlay).
- **Per-scalar deck slides** — a per-(phenotype × epoch × side) significance
  grid panel rendered beside each scalar's V4/V5 figure
  (`build_stats_figure_deck.py`).

Pipeline order: pooled-stats sheet → q13b → deck (DECISIONS 2026-06-01 "Deck
on-slide significance panels"). Reverse order produces stale or empty
annotations.

## Pipeline driver entry points

| Script | Role | Key output dirs |
|---|---|---|
| `scripts/phase_9_stats/materialize_inputs.py` | Pull per-trial / per-session features into stats input parquets | `results/<variant>/inputs/` |
| `scripts/phase_9_stats/run_stats_axis.py` | Run axis-testing stats per scalar family | `results/<variant>/<family>/` |
| `scripts/phase_9_stats/build_task_5_headline_summary.py` | Headline summary table | `results/<variant>/task_5/` |
| `scripts/phase_9_stats/build_task_7_figures.py` | Headline + per-animal + forest figures | `figures/<variant>/{task_7, …}` |
| `scripts/chore_dlc_pooled_phenotype/q12_v2_emit.py` | Q12 spatial (proportion-diff + W-2) | `phenotype_pooled/{proportion_diff_heatmaps, wasserstein_recovery}/…/tongue_jaw/` |
| `scripts/chore_dlc_pooled_phenotype/q13b_v2_emit.py` | Q13b phase-aligned endpoints | `phenotype_pooled/phase_aligned_endpoints/…/` |
| `scripts/chore_dlc_pooled_phenotype/q13_traj_v2_emit.py` | Q13 / Q13c phase-aligned trajectories | `phenotype_pooled/phase_aligned_trajectories/…/` |
| `figures/phenotype_pooled.py` (V4/V5) | Per-scalar phenotype-pooled figures | `phenotype_pooled/<endpoint>/<scope>/<subtype>/` |
| `scripts/phase_9_1_q13/build_pooled_phenotype_stats.py` | Consolidated MWU sheet (`--n-boot 5000`) | `phenotype_pooled/_stats/` |
| `scripts/phase_9_1_q13/build_stats_figure_deck.py` | 209-slide deck with on-slide significance grids | `phenotype_pooled/_deck/` |
| `scripts/chore_whisker_nose_spatial/emit_cohort.py` | Spatial for whisker / nose / spout / eye | `phenotype_pooled/wasserstein_recovery/…/whisker_nose/` |

## Open follow-ups

- Remaining `stats/` folder structure cleanup items — see memory
  `project_stats_folder_cleanup_backlog.md`. Not blocking CC #9 close.
- `all-licks` endpoints (sibling family from CC #9 §C) rebuild per-session
  bundles on-the-fly twice (filtered + no_filter) — cache the bundle build
  if re-run becomes frequent.
- `endpoint_inventory.csv` lives in the gitignored `.scratch_phase_9/` —
  promote to a committed config so endpoint registration is reproducible.
