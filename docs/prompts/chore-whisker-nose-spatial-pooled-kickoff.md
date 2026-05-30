# Chore: Phenotype-Pooled Whisker + Nose Spatial Analysis Kickoff

**Status:** LOCKED v1 (2026-05-29).
**Branch:** `chore/whisker-nose-spatial-pooled`
**Merge tag (on close):** `vChore-whisker-nose-spatial-pooled`
**Depends on (DISCHARGED 2026-05-29):** `chore/dlc-pooled-phenotype-unification` — MERGED + TAGGED `vChore-dlc-pooled-phenotype-unification`. Inherits the plot-convention helper module (`figures/_line_with_jitter_dots.py`), the path normalization (`<family>/<scope>/v2/`), the ipsi/contra recoding helper, the line+jitter+dots convention, and the mean+SEM session-pooled aggregation methodology with 2-line aggregation-method subtitle footer.

**Parallel session note:** CC #4 trajectory artifact QC may be running concurrently in a separate worktree (`stroke_orofacial_pipeline-trajectory-qc`). Different write paths (this chore writes to `stats/figures/phenotype_pooled/proportion_diff_heatmaps/<scope>/v2/whisker_*` + `nose_*`; CC #4 writes only to `stats/sensitivity/trajectory_qc/`). Standard editable-install collision discipline applies.

---

## Summary

Extends Q-lock 12's phenotype-pooled spatial analysis methodology to TWO additional bodyparts: **whisker** + **nose**. Uses raw DLC tracking (no cleanup pipeline — quick path A). Generates the same three figure families as Q12 (proportion-diff heatmaps + W-2 recovery curves + per-session W-2 boxplots) under the unified plot + path conventions established by `chore/dlc-pooled-phenotype-unification`.

Net-new outputs (no legacy variants for these bodyparts), so NO `no_filter/` subdir needed — files land directly at `<family>/<scope>/v2/<bodypart>_<side>_<...>.svg`, sibling to the tongue + jaw files the unification chore emitted.

---

## Scope IN

- Spatial substrate validation: confirm whisker + nose are tracked by DLC in the existing per-frame data + their landmarks are reachable via the `dlc_spatial/pixel_bins.py` pipeline.
- Per-animal histogram + per-epoch proportion_diff computation for whisker + nose. Reuses Q12's `phenotype_pooled_proportion_diff.py` module (extends it with bodypart parameterization).
- W-2 recovery curve + per-session W-2 boxplot computation for whisker + nose. Reuses Q12's W-2 stats infrastructure.
- Cohort emit on the 8-animal Q-lock 13b cohort (PS46-PS55).
- Ipsi/contra coding with spatial x-bin sign-flip for right-stroke animals (inherits `ipsi_contra_recoding.py` from Q14).
- Output paths: extend the unification chore's `<family>/<scope>/v2/` structure with new bodypart files.

## Scope OUT

- Cleanup pipelines for whisker + nose (v7/v3.4 analogs) — quick path A explicitly skips this. Raw DLC tracking is the data substrate.
- Per-animal individual whisker/nose heatmaps — out of scope (Phase 7c.2 spatial pipeline already renders these per-animal; this chore is the cross-animal phenotype-pooled extension).
- Phase-aligned trajectory or scalar endpoint analyses for whisker/nose — out of scope (Q13/Q13b/Q13c apply to tongue only; analogs for whisker/nose are separate future tickets).
- Statistical inference upgrades beyond Q12's stats package — out of scope.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| `chore/dlc-pooled-phenotype-unification` merged + tagged | Verify in Stage 0 | CC |
| DLC tracks whisker + nose landmarks per frame | Verify in Stage 0 | CC |
| `figures/_line_with_jitter_dots.py` from unification Stage 1 reachable | Verify in Stage 0 | CC |
| `cohort_filters/ipsi_contra_recoding.py` (or wherever Q14 actually shipped it) reachable | DISCHARGED via Q14 | — |
| `dlc_spatial/pixel_bins.py` + `render_on_demand.py` proportion_diff functions reachable | DISCHARGED | — |

## Locked design decisions

**Inherits from Q-lock 12 (UNCHANGED):**
- Cmap: custom `_PROPORTION_DIFF_CMAP` (blue → light-grey midpoint → red).
- No-data mask: `set_bad("white")` with white panel facecolor; mask only `(H_pre == 0) & (H_post == 0)` cells.
- `shared_vmax` = data-driven cohort-wide 99th percentile of `|D_pooled|` across all rendered panels.
- No magnitude floor (only source-data mask).
- 4-tier (F-P-1) + 3-tier (mod-severe collapsed into moderate) cohort variants.
- 4×3 grid layout per (bodypart, side) figure: 4 (or 3) phenotypes × 3 post-epochs (acute / sub_acute / chronic) + Pre column per Q12 Addendum #7 = 4×4 (or 3×4).
- Within-animal baseline normalization (Q12-A): per-animal post-vs-pre diff computed BEFORE phenotype-pooling.
- W-2 recovery curves + per-session W-2 boxplots in the new line+jitter+dots convention from unification chore.

**Inherits from unification chore:**
- Output path structure: `<family>/<scope>/v2/<files>`.
- Plot convention: line + per-session jitter dots overlay for W-2 plots.
- Ipsi/contra coding with spatial x-bin sign-flip for right-stroke animals.
- Sham animal exclusion from ipsi/contra figures.

**Bodypart-specific (NEW):**
- Bodyparts: `whisker` + `nose`. Per-DLC bodypart name verified in Stage 0.
- For whisker: if multiple whisker landmarks are tracked (e.g., individual whiskers per side), aggregate into a single per-side whisker spatial distribution. CC decides aggregation method in Stage 0 (likely union of all whisker landmark positions per frame) and surfaces for approval before computing distributions.
- For nose: single landmark typically; use as-is.
- Cohort: 8-animal Q-lock 13b cohort.

**Output paths:**
- Heatmaps: `stats/figures/phenotype_pooled/proportion_diff_heatmaps/<scope>/v2/{whisker,nose}_{ipsi,contra}_proportion_diff.svg`
- W-2 recovery: `stats/figures/phenotype_pooled/wasserstein_recovery/<scope>/v2/{whisker,nose}_{ipsi,contra}_recovery.svg`
- W-2 boxplots: `stats/figures/phenotype_pooled/wasserstein_boxplots/<scope>/v2/{whisker,nose}_{ipsi,contra}_boxplots.svg`
- Stats CSVs: `stats/results/phenotype_pooled/<family>/<scope>/v2/{whisker,nose}_<...>.csv` (mirror tree)
- Total new files: 2 bodyparts × 2 sides × 3 figure families × 2 scopes (4-tier + 3-tier) = **24 SVGs** + CSV siblings.

**Per-phase pilot STOP gates** (GR7 per-invocation approval each):
- Before Stage 4 cohort emit launch.
- Before Stage 4 PS46 pilot → 7-animal fanout.
- Before Stage 5 phase close.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification + bodypart audit | CC | Confirm unification merged + tagged; verify whisker + nose are in DLC's tracked landmark set; identify the canonical bodypart names + landmark count per side (e.g., "whisker_1_L", "whisker_2_L", ... or single "whisker_L"); decide aggregation if multi-landmark. Editable-install pointer check. Post Stage 0 report including: bodypart-name enumeration, multi-landmark aggregation proposal, sanity-spot-check spatial bin grid for one sample (PS46, one session) showing per-frame whisker+nose data is reachable. |
| 1 | Extend Q12's proportion_diff module for whisker + nose | CC | Add bodypart parameterization to `figures/phenotype_pooled_proportion_diff.py` (or sibling). Pure function extension; existing tongue + jaw behavior unchanged. Tests: known-input/known-output regression on a 2-animal × 2-epoch synthetic fixture for whisker + nose. |
| 2 | Extend Q12's W-2 modules for whisker + nose | CC | Same pattern for `figures/phenotype_wasserstein_recovery.py` + `figures/phenotype_wasserstein_recovery_boxplot.py`. Reuse the line+jitter+dots primitive from unification's `_line_with_jitter_dots.py`. Tests: snapshot tests + structural assertions. |
| 3 | Cohort emit script | CC | `scripts/chore_whisker_nose_spatial/emit_cohort.py --bodyparts {whisker,nose,both} --families {proportion_diff,wasserstein_recovery,wasserstein_boxplots,all} --cohort_scope {4_tier,3_tier,both} --overwrite={force,skip,prompt}`. Per-emit manifest CSV. STOP-and-ask per GR7 before launch. |
| 4 | Cohort emit on 8-animal cohort | CC | Pilot on PS46 first. Report: wall-time + spatial-distribution sanity check (3 random PS46 sessions show finite whisker + nose mass) + figure spot-check (1 SVG per family per bodypart). STOP-and-ask before 7-animal fanout. |
| 5 | Phase close + merge tag `vChore-whisker-nose-spatial-pooled` | Cowork | MIGRATION_LOG entry. DECISIONS entry covering: (a) raw-DLC path-A choice rationale; (b) multi-whisker landmark aggregation lock from Stage 0; (c) v2 path inheritance from unification chore. Forward-pointer to potential follow-up (whisker/nose cleanup pipeline if raw-data signal looks artifact-contaminated). |

---

## Forward-pointers

- **Cleanup pipelines for whisker + nose** (path B from the original whisker/nose scoping conversation) — only if this chore reveals raw-data artifact contamination that compromises the science. Otherwise skipped indefinitely.
- **Phase-aligned trajectory + scalar endpoint analyses for whisker + nose** — analogs of Q13 / Q13b / Q13c. Separate tickets if scientifically motivated.
- **Per-animal individual whisker/nose heatmaps under v2 path conventions** — Phase 7c.2 per-animal pipeline currently renders these; could be migrated to `<family>/<scope>/v2/per_animal/` conventions in a future small chore.

## References

- **`chore/dlc-pooled-phenotype-unification`** — provides line+jitter+dots plot convention + path structure + ipsi/contra recoding inheritance.
- **Q-lock 12 (PR #153 / 154 / 155)** — proportion-diff heatmaps + W-2 methodology being extended to new bodyparts.
- **Q-lock 14** — `ipsi_contra_recoding.py` helper origin.
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe; 3-tier collapse via Q-lock 12 Addendum #4).
- **`dlc_spatial/pixel_bins.py`** — canonical spatial bin infrastructure.
- **`dlc_spatial/render_on_demand.py`** — proportion_diff + spatial render primitives.
