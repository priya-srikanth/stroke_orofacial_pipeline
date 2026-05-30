# Chore: Phenotype-Pooled Whisker + Nose Spatial Analysis Kickoff

**Status:** LOCKED v1 + Addendum #1 + Addendum #2 (2026-05-30).
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

---

## Addendum #1 — Scope expansion: four reference points + bilateral-part drift (2026-05-30)

**ALL OTHER LOCKS UNCHANGED** except where noted. Expands the chore from 2 bodyparts (whisker, nose) to **four reference points** and resolves centering, the W-2 render convention, and the bilateral-drift design per Priya direction 2026-05-30. The doc title ("Whisker + Nose") is now under-inclusive; the chore covers whisker, nose, spout, and eye.

### A1.1 — Reference points (4)

| # | Entity | Centering frame | Landmarks → distribution | Side split | Role |
|---|---|---|---|---|---|
| 1 | whisker | `eye_midpoint` | union of `L/R_whiskers_1/2/3` (3 per side) | ipsi/contra | primary |
| 2 | nose | `eye_midpoint` | single `nose` | ipsi/contra | primary |
| 3 | spout | `spout_midpoint` | union of `L_spout` + `R_spout` (both pooled) | none | exploratory / descriptive |
| 4 | eye | `eye_midpoint` | union of `L_eye` + `R_eye` (both pooled) | none | exploratory / descriptive |

### A1.2 — Centering (RESOLVED)

- **Whisker + nose: `eye_midpoint`** (Priya 2026-05-30: "I meant eye_midpoint centered"). Supersedes the scope-expansion's "raw spout-centered frame" wording. Consistent with jaw, the analogous facial landmark (eye-centered per Q12 Addendum #3). For the record: the scope-expansion's justification "Q12 tongue + jaw heatmaps are spout-centered" is imprecise — Q12 locks tongue=`spout_midpoint` but jaw=`eye_midpoint`; `eye_midpoint` for the new facial bodyparts aligns with jaw, not tongue.
- **Spout (#3): `spout_midpoint`-centered. Eye (#4): `eye_midpoint`-centered** (Priya 2026-05-30: "eye should be eye_centered, and spout should be spout_centered").

### A1.3 — Bilateral-part drift (#3, #4) — RESOLVED

- "Bilateral part drift, not midpoint drift" (Priya 2026-05-30): analyze the bilateral fiducial PARTS (spout L/R, eye L/R), **not** their collapsed midpoint.
- "Treat the combination of both parts as one distribution" (Priya 2026-05-30): pool BOTH bilateral landmarks into ONE distribution per part — compare {both eyes} vs {both eyes}, {both spouts} vs {both spouts}, **not one side at a time**. No side split.
- Methodology = the standard **Q12-A per-animal pre-pool normalization** applied to these pooled distributions: each post-epoch pooled distribution is differenced against the animal's own pre-stroke pooled distribution; phenotype-pooled mean. The per-session W-2 against the pre-pool **is** the "session-to-session drift relative to baseline" the scope expansion described — **no separate baseline-mean subtraction step is introduced.**
- **Self-centered-frame note:** because eye is analyzed in eye-centered frame and spout in spout-centered frame, the bilateral parts sit ~symmetric about origin by construction; the post-vs-pre signal is expected to be **small** — a fiducial self-consistency / camera-stability check. This is the intended exploratory read (descriptive only; not used for hypothesis testing).

### A1.4 — Multi-whisker aggregation (RESOLVED)

Union of all 3 whisker landmarks per side into one per-side distribution (Priya approved 2026-05-30). All 6 landmarks track comparably on the PS46 pilot session (median likelihood 0.90–0.93, >99.6% above lik 0.6), so no landmark dominates the union with noise. Each frame contributes 3 position samples per side, each independently likelihood-gated.

### A1.5 — W-2 per-session family: line+jitter+dots (NOT box plots)

- Render convention: **line + per-session jittered dots**, inherited from the unification chore's Stage 2 box→line+jitter migration. **Extend the existing renderer `src/stroke_orofacial/figures/phenotype_wasserstein_recovery_boxplot.py`** (already migrated by the unification chore) with bodypart parameterization. Do NOT re-introduce box plots for any new reference point (would create visual asymmetry with the existing tongue + jaw W-2 figures).
- The `wasserstein_boxplots/` directory name is a legacy semantic carryover (Q12a "per-session W-2 distribution") and remains the canonical path. Don't rename; emit line+jitter+dots into it.

### A1.6 — Figure count (REVISED): 36 SVGs

| Reference point | sides | × families | × scopes | SVGs |
|---|---|---|---|---|
| whisker | 2 (ipsi/contra) | 3 | 2 | 12 |
| nose | 2 (ipsi/contra) | 3 | 2 | 12 |
| spout | 1 (no split) | 3 | 2 | 6 |
| eye | 1 (no split) | 3 | 2 | 6 |
| **TOTAL** | | | | **36** (+ CSV siblings) |

Families: `proportion_diff_heatmaps`, `wasserstein_recovery`, `wasserstein_boxplots`. Scopes: `4_tier` + `3_tier`.

### A1.7 — Output paths

- whisker/nose: `stats/figures/phenotype_pooled/<family>/<scope>/v2/{whisker,nose}_{ipsi,contra}_*.svg`
- spout/eye: `stats/figures/phenotype_pooled/<family>/<scope>/v2/{spout,eye}_*.svg` (no side suffix)
- Stats CSVs mirror at `stats/results/phenotype_pooled/<family>/<scope>/v2/...`
- File-stem decision: `spout_`/`eye_` (the analyzed pooled part) rather than `spout_midpoint_`/`eye_midpoint_` (which name only the centering frame). Flagged for confirmation at the Stage 1 STOP gate.

### A1.8 — Cohort note

All 8 cohort animals are `stroke_laterality: "L"` → the right-stroke spatial x-bin sign-flip inherited from Q14/unification never fires for this cohort; ipsi/contra recoding applies uniformly (L=ipsi, R=contra). 0 sham animals (matches the Q14 finding).

---

## Addendum #2 — Per-bodypart split semantics + whisker presentation + raw-pooling reuse (2026-05-30)

**ALL OTHER LOCKS UNCHANGED** except where noted. Refines A1.1 / A1.3 / A1.6 per Priya direction 2026-05-30 ("I'd like to plot all whiskers together, but we can run statistics differently for L and R (or … subplots); Nose should be different still for ipsi and contra trials; Spout and eye … for all trials"). Reuses the existing Pattern A pooled-bodypart compute path rather than building new union logic.

### A2.1 — Split semantics (REFINED)

| bodypart | analysis unit(s) | split axis | frames pooled |
|---|---|---|---|
| whisker | **L-pool** (`L_whiskers_1/2/3`), **R-pool** (`R_whiskers_1/2/3`) — separate stats | **anatomical** | all trials (both cue sides) |
| nose | nose @ ipsi-trials, nose @ contra-trials | **cue / trial** side | the cue side |
| spout | `L_spout` + `R_spout` pooled into one | **none** | all trials (both cue sides) |
| eye | `L_eye` + `R_eye` pooled into one | **none** | all trials (both cue sides) |

- **Whisker:** "plot all whiskers together, run statistics differently for L and R" → pool the 3 landmarks per **anatomical** side into a per-side distribution; compute proportion_diff + W-2 **separately** for the L-pool and R-pool; **present L and R together** (L/R subplots in one combined figure per family). Anatomical (not cue) split chosen because ipsi/contra whisker recovery is the signal of interest and pooling all 6 would average it away. Frames pooled across both cue-side tone windows (the anatomical landmark side, not the cue, is the split axis).
- **Nose:** "different still for ipsi and contra trials" → split by **cue/trial side** (the only 2-way split available for a single midline landmark), recoded ipsi/contra. Mirrors the existing tongue/jaw L/R convention.
- **Spout, eye:** "for all trials" → pool both bilateral landmarks into one distribution AND pool across both cue sides; no split. Exploratory / descriptive only. NOTE (A1.3 self-centered-frame): spout in spout-centered frame and eye in eye-centered frame sit in a ~±20px band (config grids `[-100,100]/[-20,20]` and `[-160,160]/[-20,20]`), so the post-vs-pre signal is expected to be small — a fiducial self-consistency / camera-stability check.

### A2.2 — Reuse existing Pattern A pooled path (NEW)

The phenotype-pooled compute reuses `dlc_spatial.render_on_demand._aggregate_for_dates_pooled_bodyparts` (the existing "pool N bodyparts cell-wise into one pseudo-bp histogram" path that already backs the per-animal combined whisker heatmaps), with two adaptations:

1. **Raw path:** thread `use_v7_cleaned=False` (cleaned-traces parquets do not exist for whisker/nose/spout/eye — path A). The legacy pooled fn implicitly uses the `use_v7_cleaned=True` default; an additive param is required so the new bodyparts read raw DLC.
2. **Explicit shared grid:** pass an explicit shared bin grid so all pooled landmarks histogram on identical bins — whisker `[-200,200]/[50,360]` (the Q37 unified bilateral range on `L_whiskers_1`), spout `[-100,100]/[-20,20]`, eye `[-160,160]/[-20,20]`, nose `[-100,95]/[100,330]`. This fixes the legacy per-bp-extent approximation in `_aggregate_for_dates_pooled_bodyparts` (it labels the cell-wise sum with the *first* bp's extent while computing each bp on its own config grid). spout/eye L-R already share extents; whisker per-landmark extents differ, so the explicit grid is load-bearing for whisker correctness. nbins = 80×80; all four families have `x_range: null`.

### A2.3 — Figure count (REVISED): 30 SVGs

| Reference point | figures/family | × families | × scopes | SVGs |
|---|---|---|---|---|
| whisker | 1 (L/R subplots together) | 3 | 2 | 6 |
| nose | 2 (ipsi/contra trials) | 3 | 2 | 12 |
| spout | 1 (no split) | 3 | 2 | 6 |
| eye | 1 (no split) | 3 | 2 | 6 |
| **TOTAL** | | | | **30** |

Supersedes A1.6's 36-SVG count (whisker drops 12→6 by presenting L/R together in one figure instead of two per-side files). The whisker heatmap sub-presentation (all-6-pooled into one map vs L/R subplots) and exact file counts are confirmable at the Stage 4 PS46 pilot; whisker = 6 either way.

### A2.4 — Output path stems (REFINED)

- whisker: `<family>/<scope>/v2/whisker_*.svg` (one combined L/R figure; no per-side suffix on the file — the two sides are subplots within).
- nose: `<family>/<scope>/v2/nose_{ipsi,contra}_*.svg`.
- spout/eye: `<family>/<scope>/v2/{spout,eye}_*.svg`.
