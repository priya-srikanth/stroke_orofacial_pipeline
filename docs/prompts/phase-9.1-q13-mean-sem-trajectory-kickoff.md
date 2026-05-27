# Phase 9.1 Q-lock 13 — Phase-Aligned Mean+SEM Trajectory Kickoff

**Status:** LOCKED v1 (2026-05-27).
**Branch:** `phase/9.1-q13-mean-sem-trajectory`
**Merge tag (on close):** `v9.1-q13-mean-sem-trajectory`
**Depends on:**
- Q-lock 13b close — provides the `build_first_lick_centered_phase_rows` substrate extended with `x_centered` column (Stage 1 of Q-lock 13b). Q-lock 13 cannot start implementation until 13b merges to `main`.
- Q-lock 15 marker convention — applied to figure dir + filename + footer.

---

## Summary

Phase-aligned mean+SEM trajectory figures for tongue. Phenotype-stratified (per F-P-1) × epoch-binned (per `assign_epoch_label`). Renders the same first-lick-centered phase substrate that Q-lock 13b consumed for scalar endpoints, but as time-series-of-bin trajectories rather than per-trial scalars.

Sibling phase to Q-lock 13b: shares substrate, different deliverable shape (trajectories vs. scalars).

---

## Signals + variants — 4 endpoints, 2 variants, 2 sides = 8 figures

| Signal | Variant | Definition |
|---|---|---|
| angle | raw | `angle_deg` per phase bin (substrate column) |
| angle | delta-from-baseline | `angle_deg − animal_pre_stroke_mean(angle_deg | same phase_bin)` |
| x | raw | `x_centered` per phase bin (substrate column, post Q-lock 13b Stage 1) |
| x | delta-from-baseline | `x_centered − animal_pre_stroke_mean(x_centered | same phase_bin)` |

**Baseline convention:** per-animal pre-stroke mean per phase bin, NOT cohort-aggregate baseline.

Concretely: for each (animal, phase_bin, signal), compute the mean of `signal` across ALL pre-stroke trials (epoch_label = `pre`) for that animal at that phase_bin. Subtract from every (animal, post_epoch, side, trial, phase_bin) cell. Then aggregate across animals within phenotype as usual for the delta-variant figures.

This is the analog of Q-lock 12's within-animal baseline normalization (Q12-A); rationale identical (per-animal baseline spatial pattern varies; cohort-aggregate baseline conflates per-animal variation into the delta signal).

## Scope IN

- Per-animal pre-stroke baseline computation for both signals (one helper, returns DataFrame keyed by (animal, phase_bin, signal)).
- Per (phenotype × epoch × side × phase_bin × signal × variant) mean + SEM aggregator (extends Q-lock 13b's `stats/aggregators.py` module).
- Figure renderer — 8 figures, each a 4 × 4 grid (4 phenotypes × 4 epochs: pre/acute/sub_acute/chronic). Phase on x-axis [0, 1]; signal on y-axis.
- Per-panel trace color = phenotype's YlOrRd 4-tier shade (matches PR #144 V4/V5 cohort palette).
- Per-panel SEM-shaded band (±1 SEM around mean trace).
- Per-panel pre-stroke baseline overlay on post-epoch panels (dashed grey trace, computed as cross-animal mean of per-animal pre-stroke trajectories within phenotype).
- Per-panel sample size annotation: `n=N trials` top-right corner.
- Cohort emit on 8-animal Q-lock 13b cohort (PS46/47/48/49/50/51/54/55), tongue only.

## Scope OUT

- Median+IQR variant — defer to future ticket if Priya wants a non-parametric trajectory variant.
- Successful-trials-filter variant — Priya noted "we may also later apply the successful trials filter to these" (forward-pointer; not in v1 scope).
- Jaw or other bodyparts — separate ticket.
- Cue-aligned variants — Q-lock 14 scope.
- Multi-lick variants (first_2_licks, all_licks) — Q-lock 13b's multi-lick forward-pointer applies here too.
- Significance overlays (per-bin t-test results) — defer.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Q-lock 13b close (substrate extended with `x_centered`) | IN FLIGHT (Stage 5 PS46 re-pilot pending) | Q-lock 13b CC |
| Q-lock 8 phenotype-pooled aggregator pattern | confirmed reusable in 13b Stage 0 | — |
| `stats/aggregators.py` module | created in 13b Stage 2 | — |

## Locked design decisions

**Q13-A (signals + variants):** 4 endpoints — raw angle + delta angle + raw x + delta x. Delta = per-animal pre-stroke baseline subtraction per phase_bin.

**Q13-B (aggregator):** mean + SEM (parametric). Rationale: per-bin averages across many trials within phenotype × epoch, so the bin-level distribution is already smoothed; mean+SEM is more readable + standard for trajectory figures than median+IQR.

**Q13-C (layout):** one figure per (signal, variant, side) — 8 figures total. Each figure = 4×4 grid (phenotype rows × epoch columns).

**Q13-D (color convention):** per-panel trace color = phenotype's YlOrRd 4-tier shade (mild = lightest, severe = darkest, matches PR #144 V4/V5 convention). All 4 epoch panels in a phenotype row share the same color; epoch differentiation comes from column position.

**Q13-E (baseline overlay):** YES — dashed grey trace on every post-epoch panel showing the cross-animal mean of per-animal pre-stroke trajectories within that phenotype. Makes the "how much did the trajectory change" question visually answerable per panel.

**Q13-F (sample size annotation):** YES, always. `n=N trials` top-right of each panel, small font.

**Q13-G (cohort):** 8-animal Q-lock 13b cohort, tongue only.

**Q13-H (output paths, Q-lock 15 marker convention):**
- Directory: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_cleaned_trace/phase_aligned_trajectories/`
- Filenames:
  - `angle_raw_<side>_mean_sem_cleaned_trace.svg`
  - `angle_delta_<side>_mean_sem_cleaned_trace.svg`
  - `x_raw_<side>_mean_sem_cleaned_trace.svg`
  - `x_delta_<side>_mean_sem_cleaned_trace.svg`
- Footer (figure subtitle): `Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)`
- Count: 8 figures (2 signals × 2 variants × 2 sides)

**Q13-I (Stage 5 cohort emit gate):** STOP-and-ask per GR7 before cohort emit. Same overwrite-once-then-force pattern as Q-lock 13b.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm Q-lock 13b merged + tagged; confirm `x_centered` column present in substrate output; confirm `stats/aggregators.py` from 13b Stage 2 is reusable |
| 1 | Per-animal pre-stroke baseline computation helper | CC | New helper in `stats/aggregators.py` (or sibling). Returns DataFrame keyed by (animal, phase_bin, signal). Tests: known-input/known-output regression + handling of animals with no pre-stroke sessions |
| 2 | Per-(phenotype × epoch × side × phase_bin × signal × variant) mean+SEM aggregator | CC | Extends 13b's `stats/aggregators.py`. Tests: phenotype assignment + aggregation shape correctness |
| 3 | Figure renderer (8 figures) | CC | New module `figures/phase_aligned_trajectories.py`. Per-panel trace + SEM shading + baseline overlay (post-epoch panels only) + sample size annotation. YlOrRd palette reuse from PR #144 |
| 4 | Cohort emit script | CC | `scripts/phase_9_1_q13/emit_cohort.py --overwrite={force,skip,prompt}`. Confirm-once-then-force pattern matching 13b's `emit_cohort.py`. **STOP HERE before launch — per-invocation Priya approval per GR7.** |
| 5 | Cohort emit on 8-animal cohort | CC | Pilot on PS46 first (smallest cohort), JSON sanity + wall-time report, then 7-animal fanout if pilot passes. Manifest CSV at end |
| 6 | Phase close + merge tag `v9.1-q13-mean-sem-trajectory` | Cowork | Standard tag-on-merge per CLAUDE.md GR8 |

---

## Forward-pointers

- **Successful-trials-filter variant** — Priya noted "we may also later apply the successful trials filter to these." Separate Q-lock once trial-success criterion is locked.
- **Median+IQR variant** — non-parametric trajectory rendering.
- **Multi-lick variants** (`first_2_licks`, `all_licks`).
- **Jaw analog** — gated on jaw phase-trajectory substrate (not yet built; same forward-pointer as Q-lock 13b).
- **Per-bin significance overlay** — bin-level paired t-test results stippled on panels.

## References

- **Q-lock 13b** — phase-aligned tongue ENDPOINT stats (sibling phase; provides substrate via `build_first_lick_centered_phase_rows` extended with `x_centered`).
- **Q-lock 15** — `cleaned_trace` three-layer marker convention.
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe).
- **PR #144** — Phase 9.1 Task 1c V4/V5 cohort figures (YlOrRd 4-tier palette source).
- **`stats/aggregators.py`** — created in Q-lock 13b Stage 2; this phase extends it.
- **`build_first_lick_centered_phase_rows`** — phase-extraction substrate (now emits `x_centered` post-13b Stage 1).
