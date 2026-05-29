# Phase 9.1 Q-lock 14 — Phenotype-Pooled Spout Behavior Recovery + Ipsi/Contra Unification

**Status:** LOCKED v1 (2026-05-29).
**Branch:** `phase/9.1-q14-spout-behavior-and-ipsi-contra`
**Merge tag (on close):** `v9.1-q14-spout-behavior-and-ipsi-contra`
**Depends on:**
- Q-lock 12 / 12a / 12b merged + tagged — provides the phenotype-pooled aggregator + YlOrRd palette + epoch_label vocabulary + 3-tier collapse convention.
- Q-lock 13 / 13b / 13c merged + tagged — provides the per-animal pre-stroke baseline helper (delta-from-baseline pattern reused here).
- `configs/animals.yaml` carries per-animal `stroke_side` metadata (CONFIRMED present).

NOT dependent on `chore/dlc-session-and-trial-filtering` — spout behavior metrics are UNFILTERED by design (use existing spout-side cohort enumeration as their quality criterion). The DLC filter chore-PR can land before or after this PR; no merge ordering required.

**Scope:** this PR bundles two interlocking deliverables:
1. **Q-lock 14 proper** — 9 phenotype-pooled spout-behavior recovery metrics (new content).
2. **Retroactive ipsi/contra recoding** of Q-lock 12 / 13 / 13b / 13c phenotype-pooled figures + stats CSVs. The trial-side dimension across the entire Phase 9.1 phenotype-pooled tree is migrated from LEFT/RIGHT (presented-spout) to IPSI/CONTRA (lesion-relative) coordinates. This is the right scientific convention for a stroke study and prevents cross-animal pooling artifacts from washing out the lesion-induced asymmetry signal.

---

## Summary

**Part 1 — Q-lock 14 proper:** Phenotype-pooled recovery figures for 9 spout-behavior metrics, side-stratified by **ipsi/contra cued-side** (NOT left/right — see Recoding Convention section). Each Class A figure shows phenotype-pooled mean ± SEM recovery curves across all 4 epochs (pre / acute / sub_acute / chronic), with 4 (or 3) phenotype lines per panel and 2 panels per figure (ipsi-cued | contra-cued). Class B figures (d', c) use 1×1 layout (session-pooled, not side-stratified).

Two variants per metric: **raw** (absolute value) and **delta-from-baseline** (per-animal pre-stroke baseline subtraction, analog to Q-lock 13's delta methodology).

Two cohort variants: **4-tier** (mild/moderate/mod-severe/severe per F-P-1) and **3-tier** (mod-severe collapsed into moderate per Q-lock 12 Addendum #4).

Total Q14 figure count: 9 metrics × 2 variants × 2 cohort scopes = **36 SVGs** (28 Class-A for metrics 1–7 + 8 Class-B for d' + c).

**Part 2 — Retroactive ipsi/contra recoding:** Re-emit all Phase 9.1 phenotype-pooled figures + stats CSVs under ipsi/contra coding. Affected phases:
- **Q-lock 12** — proportion-diff heatmaps, W-2 recovery curves, W-2 boxplots (per-side variants)
- **Q-lock 13** — phase-aligned mean+SEM angle + x trajectory figures (8 figures × 4 scopes)
- **Q-lock 13b** — phase-aligned scalar endpoint stats + figures (per-side variants)
- **Q-lock 13c** — phase-aligned mean+SEM angle + x + y trajectory figures (12 figures × 4 scopes)

Re-emit retains the existing `<old-path>/` tree for audit/comparison and writes the recoded variant under a parallel `<old-path>/ipsi_contra/` subtree. After Priya review, a follow-up cleanup chore may drop the old L/R tree.

---

## Stroke-side recoding convention

**New module:** `src/stroke_orofacial/cohort_filters/ipsi_contra_recoding.py` (or sibling location). Lands as Stage 1 — single source of truth for all per-animal trial-side and signed-value recoding.

**Per-animal `stroke_side` lookup:** read from `configs/animals.yaml`. Values ∈ `{"left", "right", "sham"}` (CC must confirm vocabulary in Stage 0).

**Cue-side recoding (categorical trial side → ipsi/contra):**

```python
def cue_side_to_ipsi_contra(cue_side: str, stroke_side: str) -> str:
    """L/R cue side → ipsi/contra cue side, per animal."""
    if stroke_side == "sham":
        raise ValueError("sham animals have no ipsi/contra reference")
    return "ipsi" if cue_side == stroke_side else "contra"
```

- Right-stroke animal: L-cued → contra-cued, R-cued → ipsi-cued
- Left-stroke animal: L-cued → ipsi-cued, R-cued → contra-cued

**Signed value recoding (for spatial / lateralization-sensitive metrics):**

```python
def signed_value_to_ipsi_contra(value: float, stroke_side: str) -> float:
    """Sign-flip for right-stroke animals so 'contra direction = positive' across cohort."""
    if stroke_side == "sham":
        raise ValueError("sham animals have no ipsi/contra reference")
    if stroke_side == "right":
        return -value
    return value
```

**Sign convention (locked):** contra direction = POSITIVE in ipsi/contra coordinates. For right-stroke animals (where contra = left = negative-x in spout-midpoint frame), values get sign-flipped before phenotype-pooling. For left-stroke animals, values pass through unchanged.

This applies to:
- `x_centered` (Q-lock 13 / 13c spatial trajectory data)
- `angle_deg` (Q-lock 13 / 13c — signed angle, indicates direction)
- `signed_x_at_max_abs_phase_0_075_px` (Q-lock 13b scalar)
- `signed_angle_at_max_abs_phase_0_075_deg` (Q-lock 13b scalar)
- proportion-diff heatmap x-bins (Q-lock 12 — x-axis flips for right-stroke animals before pooling)

Does NOT apply to:
- `y_centered` (Q-lock 13c — symmetric, no laterality)
- magnitude-only metrics (latency, counts, etc.)
- per-frame mass (Q-lock 12 y-axis)

**Sham animal handling:** CC must verify in Stage 0 whether any of the 8-animal cohort (PS46/47/48/49/50/51/54/55) are sham. If any are sham, they are EXCLUDED from all ipsi/contra-coded figures + stats. They remain in the (unchanged) L/R-coded outputs for reference but do not contribute to the ipsi/contra phenotype-pool.

**Stroke-side distribution audit (Stage 0):** report the count of left-stroke vs right-stroke (vs sham) animals in the cohort. If the distribution is heavily skewed (e.g., 7 of 8 right-stroke + 1 left-stroke), flag for Priya — the lone-side animal carries disproportionate weight under ipsi/contra pooling and may warrant a different analysis treatment.

---

## Metrics — 9 endpoints

| # | Metric | Per-session aggregator | Stratification |
|---|---|---|---|
| 1 | `fraction_accurate_first_lick` | `n_trials_with_accurate_first_lick / n_trials_total` per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 2 | `total_licks` | sum of v7-kept lick count across all trials per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 3 | `correct_licks` | count of licks on the cued-side (= correct side) within the lick window per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 4 | `incorrect_licks` | count of licks on the non-cued-side per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 5 | `lick_latency_ms` | median first-lick latency across trials per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 6 | `accuracy_difference_index` | `(n_correct_licks − n_incorrect_licks) / (n_correct_licks + n_incorrect_licks)` per (session, ipsi_contra_cue); bounded [−1, +1]; +1 = perfectly accurate within that trial side, −1 = perfectly inverted, 0 = no within-side preference. NOT a Signal Detection Theory metric — see metrics #8 + #9 for d' + c. | per ipsi/contra-cued (1×2 layout) |
| 7 | `licks_per_bout` | median licks-per-bout across all bouts in the session per (session, ipsi_contra_cue) | per ipsi/contra-cued (1×2 layout) |
| 8 | `d_prime` | Signal Detection Theory d' for first-lick side discrimination, pooled across cue sides per session. **In ipsi/contra coding:** `d' = z(H) − z(FA)` where H = P(first lick on CONTRA spout \| contra-cued trial), FA = P(first lick on CONTRA spout \| ipsi-cued trial). z() = inverse standard normal CDF. Unbounded; typically 0 (chance) to ~5 (perfect). | session-level (1×1 layout) |
| 9 | `criterion_c` | Signal Detection Theory criterion c for response bias. **In ipsi/contra coding:** `c = −(z(H) + z(FA))/2` with H + FA as defined for d'. Sign convention emerges naturally: **positive c = bias TOWARD ipsi side (away from contra responses)**, which is the predicted post-stroke lateralization direction. Negative c = bias toward contra (uncommon, would indicate unusual compensation). | session-level (1×1 layout) |

**Per-ipsi/contra-cue scoping** (metrics 1–7): every metric computed within trials of one cued side (ipsi or contra), separately. A session contributes TWO values per metric (one for ipsi-cued, one for contra-cued).

**Pooled scoping** (metrics 8 + 9, d' + c): computed across BOTH cue sides per session because SDT framework requires both target-present (contra-cued) and target-absent (ipsi-cued) trials to estimate H and FA. d' + c are ONE value each per session, not stratified by cue side.

**Why these three metric layers (#6 + #8 + #9):**
- `accuracy_difference_index` (per-cue-side, Class A) captures the side-asymmetry story directly via the panel split. Reading the ipsi-panel vs contra-panel mismatch visually = reading the lesion-induced lateralization.
- `d_prime` (session-level, Class B) captures the overall discrimination story: "can the animal tell ipsi-cued from contra-cued trials at all, post- vs. pre-stroke?" Standard neuroscience SDT discrimination metric.
- `criterion_c` (session-level, Class B) captures the bias direction as a scalar: positive c = ipsi-biased (predicted post-stroke direction), negative c = contra-biased. Pairs with d' as the standard SDT report.

Together they tell a complete behavioral story without conflating sensitivity and bias, with scalar metrics suitable for tables and statistical inference.

**Stage 0 verification task:** confirm each metric is computable from existing `spout_behavior/` outputs. For any metric whose aggregator doesn't already exist as a per-session value, Stage 1 adds it. For d' + c specifically: verify that per-trial first-lick side is available with cue-side annotation (need both pieces, after ipsi/contra recoding, to compute H and FA).

**d'/c numerical edge cases (Stage 2 must handle):**
- H = 0 or FA = 0 → z(0) = −∞: use the standard log-linear correction (replace 0/N with 0.5/N before z-transform).
- H = 1 or FA = 1 → z(1) = +∞: replace N/N with (N − 0.5)/N.
- Session with zero ipsi-cued OR zero contra-cued trials → d' + c undefined: emit NaN + sentinel reason `"missing_cue_side"`.
- Sham animals → excluded entirely from d'/c computation (no ipsi/contra reference).

---

## Layout

Two layout classes depending on the metric's stratification:

**Class A — side-stratified metrics (#1–7):** 1 row × 2 columns (ipsi-cued | contra-cued).

**Class B — pooled metrics (#8 d', #9 c):** 1 row × 1 column (single panel showing the session-pooled recovery curve).

### Class A layout (metrics 1–7)

**Per figure** (one row × two columns):

```
┌─────────────────────────────────────┐
│  metric: <signal>   variant: <raw|delta>   cohort: <4tier|3tier>   │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐                       │
│  │ IPSI-CUED TRIALS │   │ CONTRA-CUED TRIALS│                      │
│  │                  │   │                  │                       │
│  │  4 phenotype     │   │  4 phenotype     │                       │
│  │  lines           │   │  lines           │                       │
│  │  mean ± SEM band │   │  mean ± SEM band │                       │
│  │                  │   │                  │                       │
│  │ x: pre|acute|    │   │ x: pre|acute|    │                       │
│  │    sub_a|chronic │   │    sub_a|chronic │                       │
│  │ y: metric value  │   │ y: metric value  │                       │
│  └──────────────────┘   └──────────────────┘                       │
│                                                                     │
│  Footer: Source: spout-behavior cohort emit (Phase 8a.10)          │
└─────────────────────────────────────────────────────────────────────┘
```

- **Phenotype lines:** color per phenotype's YlOrRd shade (matches PR #144 + Q12/Q13/Q13c convention). 4 lines for 4-tier, 3 lines for 3-tier.
- **Pre epoch column:** included per Q-lock 12 Addendum #7 convention — gives visual baseline noise floor. Pre-stroke trajectories are flat-ish; post-epoch trajectories show recovery story.
- **Sample size annotation:** small `n_sessions = N, n_animals = M` per panel.
- **Per-phenotype shading:** mean ± SEM band centered on the phenotype's line. SEM = SE across sessions in the (phenotype, epoch, side) cell.

### Class B layout (metrics 8–9 — d' + c)

**Per figure** (one row × one column):

```
┌─────────────────────────────────────┐
│  metric: <d_prime|criterion_c>   variant: <raw|delta>   cohort: <4tier|3tier>  │
│                                                                                 │
│  ┌──────────────────────────────────┐                                          │
│  │ POOLED ACROSS BOTH CUE SIDES     │                                          │
│  │                                  │                                          │
│  │  4 (or 3) phenotype lines        │                                          │
│  │  mean ± SEM band                 │                                          │
│  │                                  │                                          │
│  │ x: pre|acute|sub_a|chronic       │                                          │
│  │ y: d_prime  OR  criterion_c      │                                          │
│  └──────────────────────────────────┘                                          │
│                                                                                 │
│  Footer: Source: spout-behavior cohort emit (Phase 8a.10) — ipsi/contra coding │
│          (d' + c computed per session from H=P(lick contra|contra-cued),       │
│           FA=P(lick contra|ipsi-cued); positive c = bias toward ipsi)          │
└────────────────────────────────────────────────────────────────────────────────┘
```

Same phenotype palette + epoch ticks + sample-size annotation. Cell-level data point is one d' (or c) value per session (computed from H and FA pooled across both cue sides).

---

## Variants

**Variant 1: `raw`** — absolute metric value per (session, trial_side). Phenotype-pooled mean ± SEM across sessions within (phenotype, epoch, trial_side).

**Variant 2: `delta-from-baseline`** — per-animal pre-stroke baseline subtraction.
- Per animal: `baseline_<metric>(animal, trial_side) = mean of <metric> across pre-stroke sessions of (animal, trial_side)`.
- Per session × post-epoch: `delta_<metric>(animal, session, trial_side) = <metric> − baseline_<metric>(animal, trial_side)`.
- Phenotype-pool the deltas as usual (mean ± SEM across sessions).

Mirrors Q-lock 13's per-animal-baseline subtraction methodology. Delta is **subtraction**, not ratio — matches Q-lock 13 / 13c convention.

For pre-epoch panels in the delta variant: pre-stroke deltas are computed as `pre_session_metric − animal_pre_baseline` (the deviation of an individual pre-stroke session from the animal's overall pre-stroke mean). This gives the visual baseline noise floor — informative for judging whether post-epoch deltas exceed natural pre-stroke variability.

---

## Scope IN

**Part 1 — Q-lock 14 (new content):**
- Per-session computation of all 9 metrics from existing `spout_behavior/` substrate (Stage 2 verifies + adds anything missing).
- Per-animal pre-stroke baseline helper (extends Q-lock 13's baseline aggregator — same shape, applied to spout-behavior metrics).
- Phenotype-pooled aggregator (extends `stats/aggregators.py`).
- Figure renderer (new module `figures/phenotype_pooled_spout_behavior_recovery.py`).
- d' + c SDT computation helper with log-linear correction for edge cases.
- Cohort emit on the 8-animal Q-lock 13b cohort (PS46/47/48/49/50/51/54/55).
- Output paths under `stats/figures/phenotype_pooled/spout_behavior_recovery/` + `stats/results/phenotype_pooled/spout_behavior_recovery/` (ipsi/contra-coded from the start; no L/R variant for Q14).

**Part 2 — Retroactive ipsi/contra recoding:**
- New module `cohort_filters/ipsi_contra_recoding.py` (or sibling location) — single source of truth for `cue_side_to_ipsi_contra` + `signed_value_to_ipsi_contra`.
- Re-emit Q-lock 12 proportion-diff heatmaps under ipsi/contra coding (tongue + jaw × ipsi + contra; spatial x-bin flipping for right-stroke animals).
- Re-emit Q-lock 12 W-2 recovery curves + per-session W-2 boxplots under ipsi/contra.
- Re-emit Q-lock 13 phase-aligned mean+SEM angle + x trajectory figures under ipsi/contra (with signed-value sign-flipping for right-stroke animals: applied to angle_deg + x_centered).
- Re-emit Q-lock 13b phase-aligned scalar endpoint stats (signed scalars: `signed_x_at_max_abs_phase_0_075_px` + `signed_angle_at_max_abs_phase_0_075_deg` + `peak_angle_deg`) under ipsi/contra.
- Re-emit Q-lock 13c phase-aligned mean+SEM angle + x + y trajectory figures under ipsi/contra. Y (`y_centered`) is symmetric so NO sign flip applied for y; angle + x are flipped as for Q13.
- Retained L/R-coded outputs at original paths for audit/comparison; ipsi/contra-coded outputs land at `<original-path>/ipsi_contra/<scope>/...` parallel subtree.

## Scope OUT

- Statistical inference (Wilcoxon, MWU, LMM, cluster permutation, bootstrap CI). v1 = mean + SEM rendering only. If inference is wanted, separate Q-lock follow-up that applies the Q-lock 13 6-test stats package to these metrics.
- DLC-derived metrics — out of scope; Q-lock 13 / 13b / 13c handles those.
- Successful-trials-filter variant or other DLC-side filtering — explicitly NOT applied; spout-behavior uses its own cohort enumeration.
- Per-animal individual trajectories overlaid in background (would aid interpretation of single-animal phenotype cells but increases visual complexity; defer to follow-up Addendum if useful).
- Treadmill activity — out of v1 scope; could be added as 8th metric in a follow-up if scientifically central.
- Cue-aligned variants (originally scoped as Q-lock 14 cue-aligned — superseded by THIS Q-lock 14 spout-behavior; cue-aligned moves to a future Q-lock if still wanted).

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Q-lock 13 + 13b + 13c merged + tagged | DISCHARGED | — |
| Q-lock 12 / 12a / 12b merged + tagged | DISCHARGED | — |
| Spout-behavior cohort enumeration is the existing 8-animal Q-lock 13b cohort | Verify in Stage 0 | CC |
| Per-animal pre-stroke baseline helper (from Q-lock 13/13c) is reusable for non-trajectory metrics | Verify + extend if needed in Stage 0 | CC |

## Locked design decisions

**Q14-A (metrics):** 8 metrics as defined above. Metrics 1–7 side-stratified by trial-presentation side (Class A layout); metric 8 (`d_prime`) pooled across trial sides at the session level (Class B layout).

**Q14-B (variants):** raw + delta-from-baseline. Delta = subtraction (per-animal pre-stroke baseline). Matches Q-lock 13 convention.

**Q14-C (layout):** TWO layout classes.
- **Class A (metrics 1–7):** 1 row × 2 columns (left-cued | right-cued). 4 (or 3) phenotype lines per panel with mean ± SEM bands. 4 epoch ticks on x-axis (pre, acute, sub_acute, chronic).
- **Class B (metric 8 — d'):** 1 row × 1 column (single panel, pooled across trial sides per session). 4 (or 3) phenotype lines + mean ± SEM bands. 4 epoch ticks on x-axis.

The two layout classes share palette, epoch grammar, and sample-size annotation conventions; they differ only in panel count.

**Q14-D (cohort scopes):** 4-tier (F-P-1) AND 3-tier (Q-lock 12 Addendum #4 collapse). Both rendered.

**Q14-E (palette):** YlOrRd 4-tier (or 3-tier) for phenotypes. Matches PR #144 + Q-lock 12/13/13c.

**Q14-F (cohort):** 8-animal Q-lock 13b cohort, unfiltered (no DLC SessionFilter or TrialFilter). Uses existing spout-behavior cohort enumeration.

**Q14-G (sample size annotation):** `n_sessions = N, n_animals = M` per panel (small font, top-right).

**Q14-H (output paths, Q-lock 12 Addendum #2 path convention preserved):**
- Figures: `pipeline_outputs/stats/figures/phenotype_pooled/spout_behavior_recovery/<cohort_scope>/<metric>_<variant>_recovery.svg`
- Stats CSVs: `pipeline_outputs/stats/results/phenotype_pooled/spout_behavior_recovery/<cohort_scope>/<metric>_<variant>.csv`
- `<cohort_scope>` ∈ `{4_tier, 3_tier}`
- `<variant>` ∈ `{raw, delta}`
- Footer (figure subtitle): `Source: spout-behavior cohort emit (Phase 8a.10) — phenotype-pooled <cohort_scope> scope`

**Q14-I (phenotype-pool sentinel):** cell with `n_sessions_kept = 0` → sentinel row (`mean = NaN, sem = NaN, n_sessions = 0, n_unique_animals_contributing = 0, sentinel_reason = "no_sessions"`). Otherwise compute normally. Spout-behavior side does NOT filter sessions, so sentinel triggers are rare — only when an entire (animal, side) combination is missing data (e.g., a session never had right-side trials).

**Q14-J (Stage 5 cohort emit gate):** STOP-and-ask per GR7 before cohort emit. Spout-behavior reads are fast (~seconds per session), so pilot may be unnecessary — but follow project convention (PS46 pilot first, then 7-animal fanout on approval).

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm Q-lock 12 + 13 + 13b + 13c merged + tagged. Verify `configs/animals.yaml` carries `stroke_side` per animal — report distribution (n_left_stroke, n_right_stroke, n_sham) across the 8-animal cohort. Read `spout_behavior/` modules to verify each of the 9 metrics is computable. Identify any gaps. Editable-install pointer check. Post Stage 0 report with: (a) stroke-side distribution + sham flag, (b) metric-availability matrix (✅/❌ per metric × substrate function), (c) enumeration of existing Q12/Q13/Q13b/Q13c phenotype-pooled outputs that need retroactive re-emit (count of figures + CSVs per phase). |
| 1 | Ipsi/contra recoding helper module | CC | New module `src/stroke_orofacial/cohort_filters/ipsi_contra_recoding.py` (or sibling). Pure functions: `cue_side_to_ipsi_contra(cue_side, stroke_side)`, `signed_value_to_ipsi_contra(value, stroke_side)`, `stroke_side_lookup(animal)` reading from animals.yaml, `is_sham(animal)` predicate. Sign convention locked: contra direction = POSITIVE. Tests: all 4 combinations (cue × stroke_side); sign-flip for right-stroke animals; ValueError on sham input; round-trip identity check (recode + un-recode = original). |
| 2 | Per-session Q14 metric computation + SDT helper | CC | For Q14 metrics 1–7, ensure per-(session, ipsi_contra_cue) values exist. Add any missing aggregators (likely `accuracy_difference_index`). For metrics 8–9 (d' + c): add SDT helper that takes per-trial first-lick side + ipsi/contra cue side, computes H + FA with log-linear correction for edge cases (H/FA = 0 → 0.5/N; H/FA = 1 → (N−0.5)/N), and returns `(d_prime, criterion_c, status)`. Status ∈ {`ok`, `missing_cue_side`, `sham_animal`}. Tests: known-input/known-output regression on synthetic per-trial fixtures. |
| 3 | Per-animal pre-stroke baseline + phenotype-pooled aggregator (Q14) | CC | Extend Q-lock 13's per-animal baseline helper to operate on these 9 spout-behavior metrics. Extend `stats/aggregators.py` with spout-behavior phenotype-pooled support. Sham animals excluded from ipsi/contra-coded aggregation. Tests: phenotype assignment + aggregation shape + 3-tier collapse + sham exclusion. |
| 4 | Q14 figure renderer (36 figures) | CC | New module `src/stroke_orofacial/figures/phenotype_pooled_spout_behavior_recovery.py`. Class A layout: 1×2 (ipsi-cued | contra-cued) for metrics 1–7. Class B layout: 1×1 (session-pooled) for metrics 8–9. Phenotype YlOrRd palette via `figures/palette.py`. Tests: snapshot test on rendered figure structure + axes/title/subtitle/legend content. |
| 5 | Q14 cohort emit script | CC | `scripts/phase_9_1_q14/emit_cohort.py --cohort_scope={4_tier,3_tier,both} --variants={raw,delta,both} --overwrite={force,skip,prompt}`. Confirm-once-then-force pattern matching Q-lock 13c. Per-emit manifest CSV. **STOP HERE before LAUNCH** — per-invocation Priya approval per GR7. |
| 6 | Q14 cohort emit on 8-animal cohort | CC | Pilot on PS46 first. Report: wall-time, manifest contents, figure sanity check. If pilot passes, surface for approval before 7-animal fanout. |
| 7 | Retroactive recoding: Q-lock 12 re-emit | CC | Re-emit Q-lock 12 proportion-diff heatmaps + W-2 recovery curves + W-2 boxplots under ipsi/contra coding. Apply spatial x-bin flipping for right-stroke animals before phenotype-pooling. Output paths: `<existing-q12-path>/ipsi_contra/...` parallel subtree. STOP-and-ask before LAUNCH per GR7. Pilot on PS46 first. |
| 8 | Retroactive recoding: Q-lock 13 + 13c re-emit | CC | Re-emit Q-lock 13 + 13c phase-aligned mean+SEM trajectory figures (angle + x + y) under ipsi/contra coding. Apply signed-value sign-flip for right-stroke animals to angle_deg + x_centered. Y is symmetric — no sign flip applied. Output paths: `<existing-q13-or-q13c-path>/ipsi_contra/...` parallel subtree. STOP-and-ask before LAUNCH per GR7. Pilot on PS46 first. |
| 9 | Retroactive recoding: Q-lock 13b re-emit | CC | Re-emit Q-lock 13b phase-aligned scalar endpoint stats under ipsi/contra. Apply sign-flip to `signed_x_at_max_abs_phase_0_075_px` + `signed_angle_at_max_abs_phase_0_075_deg` + `peak_angle_deg` for right-stroke animals. Output paths: `<existing-q13b-path>/ipsi_contra/...` parallel subtree. STOP-and-ask before LAUNCH per GR7. Pilot on PS46 first. |
| 10 | Phase close + merge tag `v9.1-q14-spout-behavior-and-ipsi-contra` | Cowork | Comprehensive MIGRATION_LOG entry documenting both Q14 new content + Part 2 retro recoding methodology. DECISIONS entries for: (a) ipsi/contra coding convention (contra = positive); (b) sham-animal exclusion from ipsi/contra figures; (c) c sign emergence from ipsi/contra coding (positive = ipsi-bias). Tag-on-merge per GR8. |

---

## Forward-pointers

- **Cleanup chore: drop the legacy L/R-coded outputs** — after Priya reviews the ipsi/contra-coded outputs and confirms they match expectations, a follow-up chore-PR can `rm -rf` the original L/R subtrees, leaving only the ipsi/contra-coded canonical versions. Saves disk + eliminates dual-source confusion. GR7 approval required at execute time.
- **Statistical inference applied to these metrics** — apply the Q-lock 13 6-test stats package (paired Wilcoxon / MWU session / MWU trial / LMM / cluster permutation / bootstrap CI) to spout-behavior phenotype-pooled cells.
- **Treadmill activity recovery curves** — 10th metric if scientifically central.
- **Per-animal individual trajectories overlaid** — visual addendum for single-animal phenotype cells (PS46 alone in moderate, PS51 alone in mod-severe).
- **Per-bin (finer epoch resolution) variant** — current locks use the 4 discrete epoch labels; could extend to per-rel-day-bin for higher-resolution recovery curves.
- **Cue-aligned variants** — originally scoped as Q-lock 14 (now this Q-lock 14 is spout-behavior + ipsi/contra unification). Cue-aligned can become Q-lock 15-onwards if still wanted.

## References

- **Q-lock 13 + 13c** — per-animal pre-stroke baseline subtraction methodology (delta variant pattern reused here).
- **Q-lock 12 Addendum #2** — `stats/figures/phenotype_pooled/` canonical figure home + `stats/results/phenotype_pooled/` canonical results home.
- **Q-lock 12 Addendum #4** — 3-tier phenotype collapse (mod-severe → moderate). Inherited.
- **Q-lock 12 Addendum #7** — Pre column in heatmaps for baseline noise floor; visual convention adopted for the pre epoch column in recovery curves.
- **Phase 8a.10** — spout-behavior cohort visual gate (per-animal figures the phenotype-pooled view here aggregates from).
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe).
- **PR #144** — YlOrRd 4-tier palette source.
- **`src/stroke_orofacial/spout_behavior/`** — substrate modules for metric computation (visual_gate, criteria, lick_detection, bouts, lick_bouts, recovery_trajectories).
