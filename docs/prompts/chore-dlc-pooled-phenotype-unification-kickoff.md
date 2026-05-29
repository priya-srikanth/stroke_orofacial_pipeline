# Chore: DLC Pooled-Phenotype Unification Kickoff

**Status:** LOCKED v1 (2026-05-29).
**Branch:** `chore/dlc-pooled-phenotype-unification`
**Merge tag (on close):** `vChore-dlc-pooled-phenotype-unification`
**Depends on (BOTH DISCHARGED 2026-05-29):**
- Filter chore-PR — MERGED via PR #158, TAGGED `vChore-dlc-session-and-trial-filtering`. Provides `pipeline_outputs/stats/inputs/filtered_v1/<slug>/<animal>.parquet` materialized inputs + `DlcSessionFilter`/`DlcTrialFilter` classes.
- Q-lock 14 Part 1 — MERGED via PR #159, TAGGED `v9.1-q14-spout-behavior-and-ipsi-contra`. Provides (a) the `cohort_filters/ipsi_contra_recoding.py` helper module (`cue_side_to_ipsi_contra`, `signed_value_to_ipsi_contra`, sham handling, stroke_side lookup) and (b) the canonical "line plot with per-session dots + jitter" plotting convention shipped by Q14's spout-behavior renderer.

**No parallel CC sessions active at launch** — the shared conda env should be in a known state. Editable-install collision discipline still applies if any sibling work spins up mid-chore.

---

## Summary

Retroactive re-emit of all Q-lock 12 / 13 / 13b / 13c phenotype-pooled outputs (figures + stats CSVs) under three changes simultaneously:

1. **Filtered inputs:** read from `stats/inputs/filtered_v1/` instead of the unfiltered tree (per-metric-family TrialFilter applied).
2. **Ipsi/contra recoding:** lesion-side-relative coordinates instead of LEFT/RIGHT (per Q-lock 14 recoding helper).
3. **New plot convention:** line plots with per-session dots + jitter overlay, replacing any box-plot family members. Matches the canonical convention Q-lock 14 spout-behavior figures ship.

Output structure: each existing canonical path gets a parallel `v2/` subtree (`<existing-path>/v2/<scope>/...`). Original L/R-coded box-plot outputs retained for audit/comparison; future cleanup chore drops them once v2 is reviewed.

---

## Scope IN

**Q-lock 12 re-emit:**
- Proportion-diff heatmaps under filtered_v1 + ipsi/contra. Heatmaps STAY heatmaps (different figure family); apply filter + recoding + sign-flip for right-stroke animals to spatial x-bin coords before phenotype-pooling.
- W-2 recovery curves under filtered_v1 + ipsi/contra + new line+jitter convention.
- W-2 per-session boxplots → MIGRATED to new line+jitter convention (this is the box-plot → line+dots+jitter replacement).

**Q-lock 13 + Q-lock 13c re-emit:**
- Phase-aligned mean+SEM trajectory figures (angle + x + y) under filtered_v1 + ipsi/contra + new line+jitter convention overlay. Sign-flip for right-stroke animals on angle + x (y is symmetric, no flip).
- Stats CSV re-materialization to the v2/ subtree.

**Q-lock 13b re-emit:**
- Phase-aligned scalar endpoint stats + figures under filtered_v1 + ipsi/contra + new line+jitter convention. Sign-flip for right-stroke animals on signed scalars.

**Shared plot-convention helper module:**
- New module `src/stroke_orofacial/figures/_line_with_jitter_dots.py` (or sibling location). Extracts the line + dots + jitter primitives Q14's spout-behavior renderer uses, makes them callable from Q12/Q13/Q13b/Q13c renderers. Single source of truth for the convention.

## Scope OUT

- Q-lock 14 spout-behavior figures — already use the canonical convention; no re-emit needed.
- Per-session, per-trial, per-animal DLC outputs (Phase 7a.6 family) — these are audit/inspection views; not re-emitted.
- Statistical inference upgrades (LMM, cluster permutation, etc.) — out of scope; stats methodology unchanged, only inputs + figures change.
- New endpoints — out of scope; existing per-trial endpoints inherited from filtered_v1 inputs.
- Spatial heatmap legend / cmap convention changes beyond the existing Q12 Addenda — out of scope.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Filter chore-PR merged + tagged | Verify in Stage 0 | CC |
| Q-lock 14 merged + tagged (`v9.1-q14-spout-behavior-and-ipsi-contra` or `v9.1-q14-spout-behavior-recovery` per descope) | Verify in Stage 0 | CC |
| `ipsi_contra_recoding.py` helper module reachable | DISCHARGED via Q14 | — |
| `filtered_v1/<slug>/<animal>.parquet` inputs on disk | DISCHARGED via filter chore-PR | — |
| Q14 spout-behavior renderer's line+jitter+dots primitive identified | Stage 0 task | CC |

## Locked design decisions

**Output path convention (REVISED 2026-05-29 per Priya):**

Symmetric `<family>/<scope>/{no_filter, v2}/<files>` structure across all phenotype-pooled outputs. Legacy outputs migrate into `no_filter/` subdirs; new v2 outputs land in `v2/` siblings.

```
stats/figures/phenotype_pooled/
├── proportion_diff_heatmaps/         (Q12)
│   ├── 4_tier/
│   │   ├── no_filter/<legacy SVGs migrated here>
│   │   └── v2/<new: filtered + ipsi/contra + line+jitter>
│   └── 3_tier/{no_filter, v2}
├── phase_aligned_trajectories/       (Q13 + Q13c)
│   ├── 4_tier/
│   │   ├── no_filter/
│   │   │   ├── <main SVGs>
│   │   │   ├── null_calibration/<files>
│   │   │   └── sd_band/<files>
│   │   └── v2/{<main>, null_calibration/, sd_band/}
│   └── 3_tier/{no_filter, v2}
├── phase_aligned_endpoint_stats/     (Q13b)
│   ├── 4_tier/{no_filter, v2}
│   └── 3_tier/{no_filter, v2}
└── spout_behavior_recovery/          (Q14 — no_filter NOT used)
    ├── 4_tier/<files>
    └── 3_tier/<files>
```

**Key structural rules:**
- DLC families (Q12, Q13, Q13c, Q13b): get `no_filter/` + `v2/` siblings within each scope — legacy unfiltered outputs get migrated into `no_filter/`, new v2 emits land in `v2/`.
- Q14 spout-behavior: NO `no_filter/` subdir. Spout-behavior metrics don't apply the DLC filter by design (different cohort enumeration), so there's no filtered counterpart to compare against. Q14 structure stays at `<scope>/<files>`.
- Nested subdirs (`null_calibration/`, `sd_band/`) preserved recursively inside `no_filter/` and `v2/`.
- Same scheme applied to `stats/results/phenotype_pooled/<family>/...` parallel tree.
- Naming: `4_tier` and `3_tier` uniformly (replaces existing `3_phenotype/` subdirs).

**Convention marker stamping:** unchanged from earlier draft.

**Convention marker stamping:**
- Every figure subtitle footer: `Source: filtered_v1 + ipsi/contra coding + line+jitter convention (chore vChore-dlc-pooled-phenotype-unification)`
- Every stats CSV: `provenance` column with value `"v2_filtered_v1_ipsi_contra"` (so downstream consumers can verify they're reading the right tree)

**Filter scope inherited from filter chore-PR:**
- SessionFilter: `min_trials_with_detected_lick = 10`
- TrialFilter per-metric-family:
  - lick1 / phase-aligned / X/Y peak scalars / angles → `min_licks_per_trial = 1`
  - ILI summary → 3
  - first-5-lick velocity → 5

**Ipsi/contra recoding inherited from Q14:**
- Per-animal `stroke_side` from `configs/animals.yaml`
- Contra direction = POSITIVE (sign-flip values for right-stroke animals)
- Sham animals excluded from ipsi/contra figures

**Plot convention (line + jitter dots):**
- Phenotype-pooled cell = line + ±SEM band (existing convention)
- Per-session contributing values = small dots overlaid on the line, X-jittered to avoid overlap
- Each dot = one session; dot color matches phenotype palette (YlOrRd 4-tier or 3-tier)
- Single-animal cells flagged with hashed background / marker per Q12 Addendum #7 spec

**Per-phase pilot STOP gates** (GR7 per-invocation approval each):
- Before Stage 2 Q12 re-emit launch
- Before Stage 2 PS46 pilot → 7-animal fanout
- Before Stage 3 Q13 + Q13c re-emit launch
- Before Stage 3 PS46 pilot → 7-animal fanout
- Before Stage 4 Q13b re-emit launch
- Before Stage 4 PS46 pilot → 7-animal fanout
- Before Stage 5 phase close

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm filter chore-PR + Q14 both merged + tagged. Verify `ipsi_contra_recoding.py` reachable. Verify `filtered_v1/` inputs exist on disk for PS46 (sanity-spot-check 3 sessions). Locate Q14's spout-behavior renderer line+jitter+dots primitive; assess whether it's already factored into a shareable helper or needs extraction in Stage 1. Editable-install pointer check. Post Stage 0 report. |
| 1 | Plot-convention shared helper | CC | If Q14 didn't already extract the primitive: new module `src/stroke_orofacial/figures/_line_with_jitter_dots.py`. Pure functions: `render_line_with_jitter_dots(ax, x, y_per_session_lists, phenotype_color, jitter_width, ...)`. Tests: snapshot test on rendered axes structure + per-session-dot count assertion. If Q14 already shipped it, skip this stage. |
| 1.5 | Path normalization for existing phenotype-pooled outputs | CC | **GR7 STOP-and-ask before launch.** Pure file-move operation (no re-render). For DLC families (proportion_diff_heatmaps, phase_aligned_trajectories, phase_aligned_endpoint_stats): move existing outputs at `<family>/<scope-implied-or-named>/...` → `<family>/<scope>/no_filter/<files>`. For Q14 spout_behavior_recovery: move `<slug>/<files>` → `<slug>/4_tier/<files>` and `3_phenotype/<slug>/<files>` → `<slug>/3_tier/<files>` (no `no_filter/` subdir — see structural rules above). Recursively preserve nested subdirs (`null_calibration/`, `sd_band/`, `headlines/`). Same operation on the `stats/results/phenotype_pooled/<family>/...` parallel tree. Emit migration manifest CSV at `pipeline_outputs/stats/sensitivity/dlc_pooled_phenotype_path_normalization_manifest.csv` (one row per move: src → dst + size + size_check_passed). After completion: verify `find <existing-paths>` shows no SVGs at the old (pre-normalized) levels — all have been moved into the appropriate sub-subdirs. |
| 2 | Q-lock 12 re-emit | CC | Heatmaps re-emit under filtered_v1 + ipsi/contra (spatial x-bin sign-flip for right-stroke animals). W-2 recovery curves + per-session boxplots → migrated to line+jitter convention. Output: `stats/figures/phenotype_pooled_{proportion_diff,wasserstein_recovery,wasserstein_boxplots}/v2/...`. STOP before launch + fanout per GR7. |
| 3 | Q-lock 13 + Q-lock 13c re-emit | CC | Phase-aligned mean+SEM trajectory figures (angle + x + y) under filtered_v1 + ipsi/contra + new convention. Sign-flip on angle + x for right-stroke animals; y passes through. Output: `stats/figures/phenotype_pooled/phase_aligned_trajectories/v2/...`. STOP per GR7. |
| 4 | Q-lock 13b re-emit | CC | Phase-aligned scalar endpoint stats under filtered_v1 + ipsi/contra + new convention. Sign-flip on signed scalars. Output: `stats/figures/phenotype_pooled/phase_aligned_endpoint_stats/v2/...` + stats CSVs to results parallel. STOP per GR7. |
| 5 | Phase close | Cowork | MIGRATION_LOG entry documenting the unified v2 lineage (filtered_v1 + ipsi/contra + line+jitter convention). DECISIONS entry for v2 path convention. Tag-on-merge `vChore-dlc-pooled-phenotype-unification`. Forward-pointer for the cleanup chore that drops the legacy L/R box-plot trees. |

---

## Forward-pointers

- **Cleanup chore: drop legacy L/R-coded box-plot outputs** — after Priya reviews v2 outputs and confirms they match expectations, follow-up chore-PR `rm -rf` the original L/R subtrees + box-plot artifacts. Saves disk; eliminates dual-source confusion. GR7 approval required at execute time.
- **Statistical inference upgrades** — applying the Q-lock 13 6-test stats package to spout-behavior + ipsi/contra-coded DLC metrics. Separate Q-lock if needed.
- **Per-bin (finer epoch resolution) variant of recovery curves** — current scope uses 4 discrete epoch labels; could extend to per-rel-day-bin in a future ticket.
- **Epoch boundary formalization** — separate methodology chore (per the 2026-05-29 conversation about objectively determining epoch boundaries via piecewise linear regression with constrained slopes).

## References

- **Filter chore-PR** — provides filtered_v1 inputs + filter classes.
- **Q-lock 14** — provides ipsi/contra recoding helper + canonical line+jitter+dots plot convention.
- **Q-lock 12 / 12a / 12b** — the proportion-diff heatmaps + W-2 outputs being re-emitted.
- **Q-lock 13** — the angle + x trajectory outputs being re-emitted.
- **Q-lock 13b** — the phase-aligned scalar endpoint outputs being re-emitted.
- **Q-lock 13c** — the y trajectory outputs being re-emitted.
- **Q-lock 15** — `cleaned_trace` three-layer marker convention (inherited unchanged; v2 subtree is added INSIDE the existing cleaned_trace marker tree).
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe; 3-tier collapse via Q-lock 12 Addendum #4).
