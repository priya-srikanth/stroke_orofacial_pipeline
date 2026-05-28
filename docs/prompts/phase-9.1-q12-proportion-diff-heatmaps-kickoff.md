# Phase 9.1 Q-lock 12 — Phenotype-Pooled Proportion-Diff Heatmaps Kickoff

**Status:** LOCKED v1 + Addendum #1-7 (2026-05-27 → 2026-05-28).
**Branch:** `phase/9.1-q12-proportion-diff-heatmaps`
**Merge tag (on close):** `v9.1-q12-proportion-diff-heatmaps`
**Depends on:**
- Phase 7e.4 close — provides v7-cleaned-trace spatial substrate. DISCHARGED at `8f2d193` with tag `v7e.4-spatial-cleaned-traces-routing`.
- Q-lock 15 marker convention — applied to figure dir + filename + footer.

---

## Summary

Phenotype-pooled spatial heatmaps of P(post_epoch) − P(pre) tongue + jaw position by (x, y) bin, computed per-animal-baseline-normalized then phenotype-averaged.

Tongue + jaw, split L/R, all three post-epochs (acute / sub_acute / chronic). 4 figures total (2 bodyparts × 2 sides), each a 4 × 3 grid (4 phenotypes × 3 post-epochs).

The stub module `src/stroke_orofacial/figures/phenotype_pooled_spatial.py` (from PR #144 Task 0) is the wiring target; runtime code added here.

---

## Endpoint definition

For each (animal, side, bodypart, post_epoch, bin), compute:

```
proportion_diff(animal, side, bodypart, post_epoch, bin) =
    P(bin | animal, side, bodypart, post_epoch)
    − P(bin | animal, side, bodypart, pre)
```

Where `P(bin | ...)` = fraction of all (frame-level) bodypart-position samples falling into `bin` within the (animal, side, bodypart, epoch) group.

Then aggregate within phenotype:

```
proportion_diff(phenotype, side, bodypart, post_epoch, bin) =
    mean over (animals in phenotype) of proportion_diff(animal, side, bodypart, post_epoch, bin)
```

**Critical lock (Q12-A):** baseline normalization is **per-animal pre-stroke**, NOT cohort-aggregate. Each animal's post-epoch heatmap is differenced against ITS OWN pre-stroke heatmap; phenotype-pooling is the average of these per-animal diff maps. Cohort-aggregate baseline would conflate per-animal variation in baseline spatial pattern into the diff signal.

## Scope IN

- Per-animal pre-stroke histogram computation (one per (animal, side, bodypart)) reusing existing spatial bin grid.
- Per-animal per-post-epoch histogram + per-bin proportion_diff computation.
- Phenotype-pooled aggregator (mean across animals within phenotype).
- 4-figure renderer (2 bodyparts × 2 sides), each a 4 × 3 grid of heatmap panels.
- Diverging RdBu colormap, fixed range ±0.1 (conditional on existing-figure range verification — see Q12-D below).
- No-data masking: only `(H_pre == 0) & (H_post == 0)` cells masked grey.
- Cohort emit on 8-animal Q-lock 13b cohort (PS46/47/48/49/50/51/54/55).

## Scope OUT

- Whole-session vs. tone_aligned variants — Phase 7c.2 chore-PR's whole_session vs. tone_aligned comparison is a separate scope.
- Significance overlays (stippling on cells with |diff| above threshold) — defer to future Q-lock if needed.
- Per-animal individual heatmaps (this is phenotype-pooled only).
- Tongue+jaw bodyparts beyond v7-cleaned-trace tongue + Phase 7f-cleaned jaw — other bodyparts out of scope.
- Cue-aligned variants — Q-lock 14.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Phase 7e.4 close (v7-cleaned spatial substrate) | DISCHARGED at `8f2d193` | — |
| Phase 7f close (jaw v3.4-cleaned substrate) | DISCHARGED (per memory `[[project_phase_9_1_phase_7e_merge_dependency]]`) | — |
| Existing spatial bin grid from `phenotype_pooled_spatial.py` stub | confirmed present | — |
| Q-lock 13b close (provides `stats/aggregators.py` module to extend) | IN FLIGHT (Stage 5 PS46 re-pilot) | Q-lock 13b CC |

## Locked design decisions

**Q12-A (epoch pair convention):** all three post-epochs (`acute - pre`, `sub_acute - pre`, `chronic - pre`). **Within-animal baseline normalization** — each animal's diff is computed against ITS OWN pre-stroke histogram before phenotype-pooling. NOT cohort-aggregate baseline.

**Q12-B (bodyparts):** tongue + jaw both. Tongue from v7-cleaned-trace path (Phase 7e + 7e.4); jaw from v3.4-cleaned path (Phase 7f).

**Q12-C (bin grid):** reuse the existing spatial-pipeline bins from `figures/phenotype_pooled_spatial.py` stub (inherited from PR #144 Task 0 scaffolding). NO new bin convention.

**Q12-D (color scale, CONDITIONAL):** diverging RdBu, fixed range ±0.1. **Conditional verification:** CC must inspect existing proportion_diff heatmaps in `pipeline_outputs/dlc_analysis/.../proportion_diff*` (Phase 7c.2-era cohort emits) during Stage 0 to confirm ±0.1 captures the typical value range. If most values cluster <±0.05 or many exceed ±0.1, CC surfaces a range-revision request BEFORE Stage 5 cohort emit. No silent picking.

**Q12-E (no-data masking):** mask only `(H_pre == 0) & (H_post == 0)` (true no-data, both epochs). Per memory `[[feedback-diverging-cmap-no-data-vs-no-change-distinction]]`: diverging cmap midpoint grey = real "no change" signal; conflating no-data with no-change via magnitude floors loses that signal.

**Q12-F (sides):** split L/R (Q-lock 10 convention).

**Q12-G (layout):** per (bodypart, side) figure = 4 figures total. Each figure = 4 × 3 grid (4 phenotypes × 3 post-epochs).

**Q12-H (significance overlay):** none in v1. Defer to future Q-lock if Priya wants per-cell significance markers.

**Q12-I (cohort):** 8-animal Q-lock 13b cohort.

**Q12-J (output paths, Q-lock 15 marker convention):**
- Directory: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_cleaned_trace/proportion_diff_heatmaps/`
- Filename: `<bodypart>_<side>_proportion_diff_cleaned_trace.svg`
- Footer (figure subtitle): `Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)` (tongue) / `Phase 7e + Phase 7e.4 + Phase 7f` (jaw)
- Count: 4 figures (2 bodyparts × 2 sides)

**Q12-K (mass filter):** NO magnitude floor. Use only the (H_pre==0)&(H_post==0) source-data mask from Q12-E. Per the diverging-cmap memory: magnitude floors appropriate for single-signed cmaps (Q29 UOT mass_floor) but NOT for diverging proportion_diff.

**Q12-L (Stage 5 gate):** STOP-and-ask per GR7 before cohort emit. Same confirm-once-then-force pattern as Q-lock 13b.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm Phase 7e.4 + 7f closure (already verified at `8f2d193`); confirm `phenotype_pooled_spatial.py` stub bin grid; confirm Q-lock 13b's `stats/aggregators.py` reusable. **Critical:** inspect existing proportion_diff heatmaps in `pipeline_outputs/dlc_analysis/.../proportion_diff*` to verify ±0.1 color range is reasonable (per Q12-D conditional lock). Post Stage 0 report. |
| 1 | Per-animal histogram + per-epoch proportion_diff computation | CC | New module `stats/spatial_proportion_diff.py` (or extend existing). Reuses spatial bins from `phenotype_pooled_spatial.py`. Tests: known-input/known-output regression on a 2-animal × 2-epoch synthetic fixture |
| 2 | Phenotype-pooled aggregator (mean across animals within phenotype) | CC | Extends 13b's `stats/aggregators.py` with a spatial variant. Tests: phenotype assignment + aggregation shape correctness |
| 3 | Figure renderer (4 figures) | CC | Wires the `phenotype_pooled_spatial.py` stub. RdBu diverging cmap, fixed range ±0.1, no-data mask, 4×3 grid layout, per-panel sample size annotation (n=N animals in phenotype + n=N pre / post trials per animal). Tests: snapshot test on rendered figure structure |
| 4 | Cohort emit script | CC | `scripts/phase_9_1_q12/emit_cohort.py --overwrite={force,skip,prompt}`. Confirm-once-then-force pattern matching 13b. **STOP HERE before launch — per-invocation Priya approval per GR7.** |
| 5 | Cohort emit on 8-animal cohort | CC | Pilot on PS46 first, JSON/figure sanity + wall-time report, then 7-animal fanout if pilot passes. Manifest CSV at end |
| 6 | Phase close + merge tag `v9.1-q12-proportion-diff-heatmaps` | Cowork | Standard tag-on-merge per CLAUDE.md GR8 |

---

## Forward-pointers

- **Significance overlay** — per-cell paired test (Wilcoxon or permutation) with stippling.
- **Whole-session vs. tone-aligned variants** — Phase 7c.2 chore-PR's audit comparison; separate ticket.
- **Per-animal individual heatmaps** — for diagnostic / supplementary review.
- **Cue-aligned variant** — Q-lock 14.

## References

- **PR #144 Task 0** — `figures/phenotype_pooled_spatial.py` stub scaffolding (wiring target).
- **Q-lock 13b** — provides `stats/aggregators.py` module (extended in Stage 2).
- **Q-lock 15** — `cleaned_trace` three-layer marker convention.
- **Phase 7e + Phase 7e.4** — v7-cleaned-trace tongue substrate.
- **Phase 7f** — v3.4-cleaned jaw substrate.
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe).
- **Memory: `[[feedback-diverging-cmap-no-data-vs-no-change-distinction]]`** — Q12-E + Q12-K rationale.

---

## Addendum #1 — Stage 0 findings + locks revised (2026-05-27)

**ALL OTHER LOCKS UNCHANGED.** Three locks revised per CC's Stage 0 prereq verification report.

### Q12-C — REVISED: new module, NOT existing stub

Original Q12-C said "reuse the existing spatial-pipeline bins from `figures/phenotype_pooled_spatial.py` stub." That stub is actually wired for Phase 9.1 Task 3 (Wasserstein/UOT/JS recovery curves), NOT for proportion-diff heatmaps. Leave that stub reserved for Task 3.

**Revised lock:**
- New module: `src/stroke_orofacial/figures/phenotype_pooled_proportion_diff.py`.
- Reuse primitives from `src/stroke_orofacial/dlc_spatial/pixel_bins.py` (`build_histogram`, `build_stats_grid`, `build_baseline_histogram`) and `src/stroke_orofacial/dlc_spatial/render_on_demand.py` (`_compute_proportion_diff`, `_compute_proportion_diff_for_bin`, `_render_proportion_diff_panel`).
- Reuse the existing canonical spatial bin grid (100-bin fine grid + 25 px coarse grid) from `pixel_bins.py`. No new bin convention.

### Q12-D — REVISED: legacy cmap convention + data-driven shared_vmax

Original Q12-D said "RdBu diverging cmap, fixed range ±0.1." Two problems surfaced in Stage 0:

1. Legacy Phase 7c.2 proportion_diff render code uses a custom cmap (`_PROPORTION_DIFF_CMAP` in `render_on_demand.py`) — blue → `#d0d0d0` light-grey midpoint → red. Per Phase 7c.2 Addenda #20/#22/#25 rationale: the light-grey midpoint visually distinguishes no-change real signal from white no-data cells.
2. Empirical probe on PS46 + PS47 cohort data: `|proportion_diff|` p99 ranges 0.00053–0.00595 across all (animal × bodypart × epoch) samples; max = 0.01457 (PS46 jaw acute outlier). Phenotype-pooling will dampen further. ±0.1 fixed range would render figures uniformly light-grey.

**Revised lock:**
- Cmap: custom `_PROPORTION_DIFF_CMAP` from `render_on_demand.py` (legacy convention). NOT `RdBu`.
- Range: **data-driven cohort-wide `shared_vmax`** = `np.percentile(|all_rendered_phenotype_diff_values|, 99)`, computed ONCE across all 4 figures × 4×3 panels. Applied as `TwoSlopeNorm(vcenter=0, vmin=-shared_vmax, vmax=+shared_vmax)` to every panel.
- Print the resulting `shared_vmax` value in each figure's footer for audit clarity: `Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4); shared_vmax = ±{value}`.

### Q12-E — REVISED: white no-data mask (legacy)

Original Q12-E said "mask only `(H_pre==0)&(H_post==0)` cells, mask color grey." Legacy uses `set_bad("white")` with white panel facecolor — the SAME goal (no-data vs. no-change distinction) achieved more elegantly via the legacy custom-cmap light-grey midpoint.

**Revised lock:**
- No-data condition: still `(H_pre==0) & (H_post==0)` (source-data mask, NO magnitude floor).
- Mask color: `set_bad("white")` + white panel facecolor (legacy convention).
- The blue→light-grey→red cmap's midpoint handles near-zero real signal; white reserved for true no-data.

### Q12-K — UNCHANGED (no magnitude floor; Q12-E source-data mask only)

### Stage 0 verification — DISCHARGED for color-range concern

The Q12-D color-range conditional verification asked in Stage 0 is discharged via this Addendum: ±0.1 is rejected; data-driven shared_vmax is the new lock.

---

**Q-lock 12 LOCKED at v1 + Addendum #1.** Stage 1 unblocked.

---

## Addendum #2 — Q12-J output path aligned with Q-lock 13b convention (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** One lock revised: Q12-J output directory.

### Q12-J — REVISED: align with q13b's `stats/figures/phenotype_pooled/` tree

Original Q12-J (kickoff v1) said:
- Directory: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_cleaned_trace/proportion_diff_heatmaps/`
- Filename: `<bodypart>_<side>_proportion_diff_cleaned_trace.svg`

The `phase_9_1_figures/phenotype_pooled_cleaned_trace/` tree was deprecated 2026-05-27 when Q-lock 13b moved its phase-aligned endpoint figures to `pipeline_outputs/stats/figures/phenotype_pooled/phase_aligned_endpoints/` (see `figures/phase_aligned_endpoint_stats.py:53-58`: "Output directory corrected per Priya 2026-05-27: figures land under stats/figures/phenotype_pooled/ matching the existing V4/V5 phenotype-pooled figure tree"). The Q-lock 12 kickoff was authored on the same day but referenced the older path before the q13b relocation propagated.

**Revised lock:**
- Directory: `pipeline_outputs/stats/figures/phenotype_pooled/proportion_diff_heatmaps/`
- Filename: `<bodypart>_<side>_proportion_diff_cleaned_trace.svg` (unchanged)
- Footer (figure subtitle): unchanged
- Count: 4 figures (unchanged)

The Q-lock 15 three-layer marker convention is preserved: the `cleaned_trace` marker remains in the filename + footer subtitle. The directory drops its redundant `phenotype_pooled_cleaned_trace/` marker (the `cleaned_trace` marker is supplied by the filename per the q13b precedent).


---

## Addendum #3 — Q12-B tongue centering specified as spout_midpoint (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** One lock refined: Q12-B tongue centering.

### Q12-B — REFINED: tongue uses spout_midpoint, jaw stays eye_midpoint

Original Q12-B (kickoff v1) said: "tongue + jaw both. Tongue from v7-cleaned-trace path (Phase 7e + 7e.4); jaw from v3.4-cleaned path (Phase 7f)." It did not specify which tongue centering convention to use.

Two tongue centerings exist in production (`config_loader.py:179-211` `EXPECTED_TONE_ALIGNED_FAMILIES`):
- `tongue_spout_midpoint` — tongue position relative to the spout target.
- `tongue_eye_midpoint` — tongue position in head-frame, sharing the eye-centered frame with jaw.

Per Priya 2026-05-28 Stage 5 pilot review, the biologically meaningful centering for tongue under licking analysis is `spout_midpoint` — it directly answers "does the tongue reach the spout?" and surfaces reach-to-spout shifts post-stroke that head-frame coordinates would average out.

**Refined lock:**
- Tongue: `center_mode="spout_midpoint"`
- Jaw: `center_mode="eye_midpoint"` (jaw's only canonical centering)

Both pull from the same v7-cleaned-trace (tongue) / v3.4-cleaned-trace (jaw) substrates; only the spatial centering differs.

### Pilot regenerated

The PS46-only pilot run on 2026-05-28 04:04 used the pre-Addendum-#3 eye-centered tongue. Those 2 tongue SVGs (`tongue_L_*`, `tongue_R_*`) are stale on disk; the full 8-animal cohort re-emit launched immediately after this addendum will overwrite them with the spout-centered tongue figures (and produce phenotype-pooled jaw figures across all 4 phenotypes for the first time).


---

## Addendum #4 — 3-phenotype variant (merge moderate-severe → moderate) (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** New scope: add a parallel 3-phenotype rendering of the same data, alongside the canonical 4-tier figures.

### Motivation

The 4-tier YAML phenotype labels (`mild`, `moderate`, `moderate-severe`, `severe`) include `moderate-severe` as a single-animal tier (PS51 only). With one animal per phenotype-pool, the moderate-severe row is technically a phenotype-pool of N=1 — informative but high-variance. Pooling PS51 with PS46 (moderate) gives a more robust "intermediate-severity" pool (n=2) at the cost of losing the fine-grained tier distinction.

Both views are scientifically meaningful; this addendum produces both alongside, with NEITHER replacing the other.

### Scope

- **NEW**: 3-phenotype variant rendering. Same data, same Stage 1/2/3 pipeline; ONLY change is the phenotype label remap applied before Stage 2 aggregation.
- Remap: `moderate-severe` → `moderate`. (Mild and severe unchanged.)
- 3-tier ``phenotype_order = ("mild", "moderate", "severe")``.
- Per-figure grid becomes 3×3 (3 phenotype rows × 3 post-epoch columns) instead of 4×3.

### Output path

- 4-tier (unchanged): `pipeline_outputs/stats/figures/phenotype_pooled/proportion_diff_heatmaps/`
- **3-tier NEW**: `pipeline_outputs/stats/figures/phenotype_pooled/proportion_diff_heatmaps/3_phenotype/`
- Filenames + footer subtitle: unchanged across both variants (the directory carries the marker).

### Implementation

`scripts/phase_9_1_q12/emit_cohort.py` gains `--remap-phenotypes={none,3tier}` (default `none`). When `3tier`, the driver:
- Applies the remap to the `animals_map` via `dataclasses.replace` (per-animal `recovery_phenotype` override).
- Passes `phenotype_order=("mild", "moderate", "severe")` to the Stage 3 renderer.
- Writes outputs to the `3_phenotype/` subdir.

`figures/phenotype_pooled_proportion_diff.py` gains a `phenotype_order` kwarg on both `render_phenotype_pooled_proportion_diff_figure` and `emit_phenotype_pooled_proportion_diff_figures`, defaulting to the canonical 4-tier `PHENOTYPE_ORDER`. The renderer reads the kwarg to size the grid (`nrows = len(phenotype_order)`) and to iterate phenotype rows.

### Stage 5b — 3-tier cohort re-emit

Same 8-animal cohort, full re-emit with `--remap-phenotypes 3tier --overwrite force`. 4-tier figures are NOT regenerated (they live in the parent directory and Stage 5 already emitted them at 04:37).


---

## Addendum #5 — W-2 recovery curves (pre-stroke normalized) (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** New deliverable: pre-stroke-normalized Wasserstein-2 recovery line plots alongside the heatmaps. Same per-animal pre-pool + per-(animal, post_epoch) histograms from Stage 1; an additional scalar statistic per (animal × side × bp × post_epoch).

### Q12-M (NEW): Wasserstein-2 recovery curves

For each (animal, side, bodypart, post_epoch), compute the W-2 distance between ``P(bin | animal, post_epoch)`` and ``P(bin | animal, pre)``:

- Renormalize each histogram to sum to 1 (isolating the spatial-shape comparison from the Q17 tracking-rate composite).
- Cost matrix ``C[i, j] = ||c_i - c_j||²`` (squared Euclidean) on bin centers in pixel units.
- Solve the **exact** balanced LP via :func:`ot.emd2` (POT library) per Priya 2026-05-28 direction for statistical credibility. Reduced to the union-support nonzero-bin subset to keep the LP tractable for 80×80 grids.
- W-2 = ``sqrt(emd2(P_pre, P_post, C))`` — units of pixels.

Phenotype-pooled aggregator: **mean ± SEM** across animals within phenotype. ``n=1`` phenotype tiers report ``sem=nan``; the line plot draws the marker with no error bar.

### Figure spec

One plot per (bodypart, side) = **4 SVGs** per variant, sibling to the heatmaps:
- 4-tier: ``stats/figures/phenotype_pooled/wasserstein_recovery/<bp>_<side>_wasserstein_recovery_cleaned_trace.svg``
- 3-tier: ``stats/figures/phenotype_pooled/wasserstein_recovery/3_phenotype/...``

Layout:
- X axis: 3 post-epochs (acute / sub_acute / chronic).
- Y axis: W-2 distance (pixel units).
- One line per phenotype tier, colored per :data:`stroke_orofacial.figures.palette.PHENOTYPE_ORDER`; markers with capsize=4 ±SEM error bars.
- **Per-animal scatter underlay**: one semi-transparent dot per (animal × epoch) value at the phenotype's jitter offset, colored per phenotype (α=0.4). Per Priya 2026-05-28 direction.
- Legend with per-phenotype display names. Footer carries the bodypart-specific source-marker subtitle.

### Implementation

New modules:
- ``src/stroke_orofacial/stats/spatial_wasserstein.py`` — pure-math W-2 + per-animal wrapper.
- ``src/stroke_orofacial/figures/phenotype_wasserstein_recovery.py`` — figure renderer + emit driver.

Existing modules extended:
- ``stats/aggregators.py`` — ``aggregate_phenotype_pooled_wasserstein`` (mean ± SEM aggregator).
- ``stats/spatial_proportion_diff.py`` — ``compute_per_animal_per_epoch_diff`` now also returns ``H_post_counts`` (so the W-2 step reuses the histogram without re-calling ``compute_animal_aggregated_histogram``).
- ``scripts/phase_9_1_q12/emit_cohort.py`` — computes W-2 alongside D in the per-animal loop; aggregates + emits 4 W-2 SVGs after the heatmap emit. ``q12_per_animal_manifest.csv`` gains a ``w2`` column.

Tests (78 passing across Q12):
- W-2 pure math: identical → 0, two deltas → distance, diagonal separation → sqrt(d_x² + d_y²), renormalization independence, shape-mismatch + empty-histogram error paths.
- Phenotype-pool aggregator: mean + SEM math, n=1 → NaN SEM, NaN-w2 records dropped, separate-phenotype pools, error paths.
- Figure renderer: 4-tier vs 3-tier legend, xtick labels, suptitle, per-animal scatter floor count, error paths.
- Emit driver: 4 SVG emit, manifest CSV columns, prompt-overwrite raises.

### Stage 5d (W-2 emit)

Same launch pattern as Stage 5: ``--remap-phenotypes`` flag controls 4-tier vs 3-tier; both variants are emitted in a single driver invocation per run.


---

## Addendum #6 — Per-session W-2 boxplots + session filter architecture (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** Q-lock 12 main phase merged at PR #153. This follow-up branch `phase/9.1-q12a-w2-recovery-boxplots` refines the Addendum #5 W-2 line plots into per-session boxplots, and adds a reusable session-filter architecture.

### Q12-M revised: per-session W-2 as the unit of pooling

Original Addendum #5 pooled at the per-(animal, epoch) granularity (one W-2 scalar per animal × epoch; 24 dots per plot for 8 animals × 3 epochs). Per Priya 2026-05-28 direction following the q13b convention, switch to per-session granularity:

- One W-2 scalar per (animal, date, side, bodypart) — each session's H_post differenced against the animal's pre-pool.
- Per-session values plot as the unit; phenotype-pool implicitly via box per (phenotype, epoch).
- Pre-epoch sessions: each pre session's W-2 against the FULL pre-pool that includes the session ("naive" lock; small bias toward 0 acceptable as a noise-floor reference; leave-one-out alternative deferred).

### Q12-G revised: boxplot layout (q13b shape)

Original Addendum #5 used a line plot with per-phenotype lateral marker offsets (which Priya correctly flagged as visually implying different epoch times for different phenotypes). Switch to side-by-side boxplots within epoch groups — the standard convention for "different groups at the same x".

- X axis: 4 epoch groups (Pre, Acute, Subacute, Chronic).
- Per epoch group: 4 boxplots side-by-side (3 in 3-tier variant), one per phenotype, colored per palette.
- Per-session jittered scatter overlaid on each box.
- Legend top-left (q13b convention).

### Q12-N (NEW): reusable session filter architecture

New module `src/stroke_orofacial/cohort_filters.py` provides a declarative session-filter spec for cohort drivers. Used initially by Q-lock 12a W-2 boxplots; reusable as-is by every future Q-lock 12+ figure or stats analysis.

API:
- `SessionLickStats` dataclass: per-session lick counts derived from the Phase 2 NPZ.
- `SessionFilter` dataclass: declarative threshold spec (`min_licks_total`, `min_licks_per_side`, `min_trials_with_licks_per_side`). All fields optional; AND semantic. Pass-through filter when all fields are None.
- `compute_session_lick_stats(animal, date, resolver)` → `SessionLickStats | None`.
- `apply_session_filter(animal, dates, resolver, spec)` → `SessionFilterResult` with `kept_dates`, `dropped=[(date, reason), ...]`, `stats_by_date`.
- `load_filter_spec_from_defaults()` reads `configs/defaults.yaml` `cohort_filters.default` block.

"Trials with licks" definition (locked Q12-N): a tone counts when at least one same-side lick falls in the post-tone `(0, 8000)` ms window (Q-lock 12 tone-aligned convention).

Default thresholds in `configs/defaults.yaml` ship as pass-through (all `null`) so no existing consumer is affected unless it opts in. Per-emit overrides via `scripts/phase_9_1_q12/emit_cohort.py --session-filter-config <yaml>`.

### Outputs

- Boxplot SVGs overwrite the Addendum #5 line-plot SVGs at the same Q12-J path (`stats/figures/phenotype_pooled/wasserstein_recovery/...`). The line-plot renderer module is retained for callers that prefer it but the emit driver switches to boxplot.
- New per-session W-2 long-form CSV `q12a_per_session_w2.csv` alongside the existing per-animal audit manifest, so downstream stats can re-aggregate per-session values without re-running the W-2 compute.

### Stage 5d (Q-lock 12a) — re-emit

Same 8-animal cohort, full re-emit of W-2 figures for both phenotype variants. Heatmaps unchanged from the Q-lock 12 main-phase emit at 2026-05-28 04:37 / 08:56.


---

## Addendum #7 — Heatmap Pre column (baseline noise floor) (2026-05-28)

**ALL OTHER LOCKS UNCHANGED.** Heatmap layout extended to include a Pre column alongside the 3 post-epoch columns; Pre cell shows the per-animal Pre-self proportion-diff phenotype-pooled the same way the post cells are. Implemented on follow-up branch `phase/9.1-q12b-heatmap-pre-panel`.

### Q12-G revised — layout 4×4 (or 3×4 for 3-tier)

- Rows: phenotypes (mild / moderate / mod-severe / severe in 4-tier; mild / moderate / severe in 3-tier).
- Columns: epochs in `EPOCH_ORDER = ("pre",) + POST_EPOCHS` = Pre / Acute / Subacute / Chronic.
- Pre column displays the per-animal Pre-self proportion-diff (Q12-O) phenotype-averaged, giving readers a direct visual baseline-noise reference at the same per-animal granularity as the post panels.

### Q12-O (NEW): Pre-self proportion-diff

`compute_per_animal_pre_self_diff(animal, bp, side, pre_pool, resolver, pre_dates)`:

- For each pre session: compute `D_i = P(session_i) − P(pre_pool)` (the existing `compute_proportion_diff_within` math).
- Average D arrays across the animal's pre sessions: `D̄_pre_self = nanmean_i(D_i)`.
- Per Q-lock 12a Addendum #6 "naive" lock (inherited): each pre session is INCLUDED in its own reference pool. Bias toward 0 is proportional to `1/n_pre_sessions` and consistent across animals, making the resulting D̄ a calibrated "no-shift" reference at the same per-animal averaging depth as the post-epoch panels. Leave-one-out alternative deferred.
- Phenotype-pooled via the existing Stage 2 `aggregate_phenotype_pooled_spatial_diff` (no special-case; emits a record with `post_epoch="pre"`).

### Cohort-wide `shared_vmax` calibration

Empirical PS46 pilot: per-animal Pre-self `|D|.p99` ranges from ~1e-5 (tongue/jaw L) to ~1e-19 (sparse-coverage R) — three to fifteen orders of magnitude smaller than post-epoch `|D|.p99` (~1e-3). The Pre column will visually render as essentially uniform mid-gray (the "no change" cmap midpoint per Q12-D Addendum #1) — exactly the intended noise-floor signal. `shared_vmax = p99(|D̄|)` across ALL panels (including Pre) stays dominated by the post values; no recalibration needed.

### Implementation

New function: `stroke_orofacial.stats.spatial_proportion_diff.compute_per_animal_pre_self_diff`.

Renderer: `EPOCH_ORDER` constant in `figures/phenotype_pooled_proportion_diff.py`; the renderer iterates `EPOCH_ORDER` (4 cols) instead of `POST_EPOCHS` (3 cols). `EPOCH_DISPLAY_NAMES["pre"] = "Pre"` added.

Emit driver: after the per-(animal, side, bp) pre-pool computation, compute pre-self-diff and add it to the per-animal records list with `post_epoch="pre"`. The audit CSV gains a row per (animal, side, bp) with `epoch="pre_self_diff"`.

### Stage 5e — cohort re-emit

Same 8-animal cohort, full re-emit of heatmaps (now with Pre column) for both phenotype variants. W-2 boxplots from Q12a unchanged.

