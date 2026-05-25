# Phase 9.1 — Phenotype-Pooled Figures + Pub-Polish — SCOPING DOCUMENT

> **⚠️ MAJOR AMENDMENT 2026-05-23.** Original scoping draft was written 2026-05-15 during Phase 7c.2 in-flight, BEFORE Phase 9 was drafted or any of its 8 addenda landed. The original scope ("phenotype-pooled descriptive figures with bespoke per-animal baseline normalization") has been largely absorbed into Phase 9 itself, with Phase 9.1 now specifically owning the cross-animal phenotype-pooled figure tier (V4/V5 of Addendum #8's grid) plus phenotype-pooled spatial figures (Addendum #1) plus pub-quality polish (typography, palettes, composites, ipsi/contra labeling).
>
> This document is a complete rewrite reflecting post-Addendum-8 scope. Major changes vs. the 2026-05-15 draft:
>
> - **Phenotype groupings updated** to 4-tier (mild / moderate / moderate-severe / severe) matching the `AnimalInfo.recovery_phenotype` Phase 9 Task 1.5 stamping.
> - **Per-animal baseline normalization** is now Phase 9 Task 4 stats-runner work (Addendum #6: per-session within epoch + additive normalization). Phase 9.1 consumes the already-normalized values; doesn't re-implement.
> - **Binning scheme** uses per-animal `AnimalInfo.bin_days` (PS46-50 = 2d; PS51-55 = 7d) AND Phase 9's per_epoch granularity (from per-animal `AnimalInfo.epoch_boundaries`). The cohort-uniform "hybrid 2d/7d" scheme proposed in the 2026-05-15 draft is OBSOLETE.
> - **V4 + V5 figure grid** for the 7 headline kinematic endpoints (per Addendum #8) is Phase 9.1's primary new deliverable.
> - **Phenotype-pooled spatial figures** (per Addendum #1's deferred figure tiers; now per Addendum #7's 48 cross-scope spatial endpoints) are Phase 9.1's secondary new deliverable.
> - **Pub-polish work** (typography, multi-panel composites, ipsi/contra labeling) per Addendum #1 (C) is Phase 9.1's tertiary deliverable.
> - **Phase 9.2 references** are obsolete (no separate 9.2; what was 9.2 is now Phase 9 Tasks 3-5).

---

## 1. Goals + scope

Phase 9.1 produces the cross-animal phenotype-pooled figure tier of the Phase 9 paper-figure system, plus pub-quality polish. It consumes Phase 9's already-materialized inputs + stats results; it does NOT re-implement materialization or per-animal stats.

**Primary deliverables:**
1. **V4 + V5 figure grid** per Addendum #8 for the 7 headline kinematic endpoints (and optionally any other primary scalar endpoints flagged for phenotype-pooled visualization):
   - V4: per_bin phenotype-pooled — one panel per endpoint; multiple traces (one per phenotype tier); bin_midpoint_rel_day vs cohort mean ± SEM within phenotype.
   - V5: per_epoch phenotype-pooled — one panel per endpoint; boxplots grouped by (phenotype × epoch).
2. **Phenotype-pooled spatial figures** per Addendum #1's deferred figure tiers + Addendum #7's 48 cross-scope spatial endpoints — recovery curves of Wasserstein-2 (headline), UOT cost (supplementary), JS divergence (supplementary) at per_bin granularity, pooled across animals within each phenotype tier.
3. **Pub-quality polish** per Addendum #1 (C):
   - Typography (consistent font sizes; readable in 2-column journal layout)
   - Color-palette harmonization (consistent phenotype colors; ipsi/contra mapping)
   - Multi-panel composite figures for the paper
   - ipsi/contra labeling per `AnimalInfo.mouse_side_to_ipsi_contra()` (all 8 current cohort animals are L-stroke → mouse-L = ipsi, mouse-R = contra)

**Out of scope:**
- Statistical tests (Phase 9 produces all stats results CSVs at `pipeline_outputs/stats/results/<axis>/<granularity>/<endpoint>.csv`; Phase 9.1 consumes them).
- New endpoint computation (uses Phase 9-materialized parquets at `pipeline_outputs/stats/inputs/<slug>/<animal>.parquet`).
- Per-animal figures (V1/V2/V3 per Addendum #8) — those land in Phase 9 Task 7.
- New scientific axes or comparisons (Phase 9's 4 axes × multi-granularity dispatch covers what's tested).

---

## 2. Phenotype groupings (LOCKED per Phase 9 Task 1.5 stamping, 2026-05-23)

Per `configs/animals.yaml` `recovery_phenotype` field stamped during Phase 9 Task 1.5:

| Phenotype | Animals | n | Per-animal epoch_boundaries (acute_max / subacute_max / chronic_min) |
|---|---|---|---|
| Mild | PS47, PS48, PS49, PS50 | 4 | 1 / 4 / 5 |
| Moderate | PS46 | 1 | 5 / 8 / 9 |
| Moderate-severe | PS51 | 1 | 6 / 30 / 31 |
| Severe | PS54, PS55 | 2 | PS54: 17 / 39 / 40; PS55: 17 / 49 / 50 |

**Critical caveat:** moderate (n=1) and moderate-severe (n=1) phenotypes have single-animal cohorts. Phenotype-pooled figures for these tiers render as single-animal traces with explicit n=1 annotations — no SEM band, no cross-animal averaging. The mild (n=4) and severe (n=2) tiers carry meaningful pooled statistics. Phase 9.1 figures must show n labels per tier prominently.

**PS54 vs PS55 epoch boundary divergence** — both are "severe" phenotype but have different boundaries (PS55 sub_acute and chronic shifted +10 days due to higher laser power 5.0 mW vs 3.0 mW). Phenotype-pooled epoch comparisons must respect per-animal boundaries; the `epoch_label` column in stats inputs parquets handles this correctly via Phase 9's `assign_epoch_label(rel_day, animal_info)`.

---

## 3. Inputs — what Phase 9.1 consumes from Phase 9

**Materialized parquets** (Phase 9 Task 2 outputs):
- `pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet` — 656+ parquets covering all primary endpoints (scalar/vector/spatial) × all 8 cohort animals.
- Schema: 11 standard columns + (for spatial endpoints) 4 spatial-specific columns (granularity, rel_day_anchor, n_sessions_aggregated, n_frames_aggregated).
- `epoch_label` column populated for every row per Phase 9 Addendum #6 (per-animal boundaries, not cohort-uniform).

**Stats results** (Phase 9 Task 4-5 outputs):
- `pipeline_outputs/stats/results/<axis>/<granularity>/<endpoint>.csv` — per-(axis, granularity, endpoint) FitResult rows.
- Granularity subdirectories: `per_session/`, `per_bin/`, `per_epoch/`.
- Axes: `pre_post/`, `recovery/`, `ipsi_contra/`, `trial_group/`.
- `_all.csv` master per axis aggregates across granularities.

**Per-animal recovery_phenotype + epoch_boundaries** loadable via `from stroke_orofacial.animals import load_animals; animals = load_animals(); animals['PS46'].recovery_phenotype, animals['PS46'].epoch_boundaries`.

**stats/recovery_epochs.py helpers** (Phase 9 Task 3b):
- `cohort_phenotype_summary(animals)` → `{phenotype: [animal_ids]}` mapping.
- `assign_epoch_label(rel_day, animal_info)` for any post-hoc epoch labeling.
- `assign_epoch_labels_to_inputs_df(df, animals_map)` batch helper.

---

## 4. Pooling approach (LOCKED per Phase 9 Addendum #6 conventions)

Per-animal baseline normalization happens at Phase 9 Task 4 (not Phase 9.1):
- Baseline = mean of pre-stroke (rel_day ≤ 0) `value` rows per animal.
- Normalized value = raw value − per_animal_baseline_mean (additive normalization per Addendum #6).
- Applied at stats-runner time; not stored in parquet.

Phase 9.1 figures:
- For V4 (per_bin phenotype-pooled): consume per_bin stats results CSV → multiple traces per panel (one per phenotype tier) showing bin_midpoint_rel_day vs cohort mean ± SEM within phenotype.
- For V5 (per_epoch phenotype-pooled): consume per_epoch stats results CSV → boxplots grouped by (phenotype × epoch).

**Multiple per-session points per animal** in pooled figures (NOT "per-animal mean then pool"). Each animal's sessions are individual data points in the underlying parquet; phenotype-pool aggregation in the stats runner uses per-animal weights only when explicitly opted in (default: equal-weight per session).

**Visualization style:**
- **Per-phenotype color coding** (consistent palette across all V4/V5 figures): mild = blue, moderate = green, moderate-severe = orange, severe = red (placeholder; finalize during scaffold review).
- **n labels prominent** per phenotype tier; moderate (n=1) and moderate-severe (n=1) get explicit "single-animal trace" annotation.
- **Per-animal marker style** within each phenotype color for within-tier identification (matters for severe's n=2 case especially: distinguishing PS54 vs PS55 trajectories).

---

## 5. Binning scheme — per-animal `bin_days` + per_epoch from Phase 9

The binning question (single most consequential design call in the 2026-05-15 draft, which proposed a hybrid 2d/7d cohort-uniform scheme) is now resolved by Phase 9's architecture:

**Per_bin granularity** uses per-animal `AnimalInfo.bin_days` (PS46-50 = 2d; PS51-55 = 7d). Each per_bin row in the stats results CSV is one (animal, bin_midpoint_rel_day) data point. Phenotype-pooling across mixed-cadence animals (e.g., moderate-severe pool has only PS51 = 7d) is automatic via the bin_midpoint_rel_day x-axis.

**Per_epoch granularity** uses per-animal `AnimalInfo.epoch_boundaries` (4 distinct schemas across the cohort per §2 table). Phenotype-pooling within an epoch label is straightforward — each animal's per_epoch row in stats results contributes one data point per phenotype-pool aggregation.

**Cross-bin cadence mixing** (the original §5 concern):
- For severe phenotype (PS54 + PS55): both have bin_days=7 but different chronic_min (40 vs 50). Per_bin aggregation aligns on bin_midpoint; per_epoch aggregation aligns on epoch_label. No additional handling needed.
- For mild phenotype (PS47-50): all have bin_days=2 + identical epoch boundaries (1/4/5). Cleanest pool.
- For moderate-severe (PS51 alone) and moderate (PS46 alone): no cross-animal averaging; single-animal traces only.

**The 2026-05-15 draft's hybrid 2d/7d cohort-uniform scheme is OBSOLETE.** Phase 9 uses per-animal `bin_days` + per-animal `epoch_boundaries`, both stamped by Priya at Task 1.5.

---

## 6. Figure family inventory + per-family plan

### 6.1 V4 — per_bin phenotype-pooled recovery curves (7 headline kinematic endpoints)

**Source:** `pipeline_outputs/stats/results/recovery/per_bin/<endpoint>.csv` for the 7 headline kinematic endpoints from Addendum #8:
- `tongue_lick1_y_peak`, `tongue_lick1_t_peak_ms`, `tongue_lick1_x_at_ypeak`, `tongue_lick2_x_at_ypeak`, `tongue_lick1_vxy_peak`, `tongue_max_vxy_peak_first5`, `tongue_mean_vxy_peak_first5`.

**Plot:** one panel per endpoint; multiple traces (one per phenotype tier); bin_midpoint_rel_day on x-axis vs phenotype-mean ± SEM of normalized value on y-axis. L/R sides as overlaid colors within phenotype lines (per Addendum #8 (H) default).

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint>/v4_per_bin_phenotype_pooled.svg` + `.png`.

### 6.2 V5 — per_epoch phenotype-pooled boxplots (7 headline kinematic endpoints)

**Source:** `pipeline_outputs/stats/results/recovery/per_epoch/<endpoint>.csv` for the 7 headline kinematics.

**Plot:** one panel per endpoint; boxplots grouped by (phenotype × epoch). Phenotype on x-axis, boxplot per epoch within each phenotype group.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint>/v5_per_epoch_phenotype_pooled.svg` + `.png`.

### 6.3 Phenotype-pooled spatial recovery curves (12 family-metric combos × 4 scope/trial_group)

**Source:** `pipeline_outputs/stats/inputs/spatial_<metric>_<family>_<combo>/<animal>.parquet` (48 endpoints per Addendum #7) → phenotype-pool at per_bin granularity.

**Plot:** for each (family_entry, metric, scope+trial_group) = 4 family × 3 metric × 4 combo = 48 figures. Each figure: one panel; multiple traces (one per phenotype tier); bin_midpoint_rel_day vs cohort mean Wasserstein/UOT/JS within phenotype.

**Headline emphasis:** Wasserstein at scope=tone_aligned/all (the Addendum #3 HEADLINE METRIC) gets prominent placement in the curated figure set. Other 47 combos are supplementary.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/<family>/<metric>/<combo>.svg` + `.png`.

### 6.4 Pub-quality polish

**Scope:** typography + palette harmonization + multi-panel composite figures + ipsi/contra labeling.

- **Typography:** consistent font sizes across all V4/V5/spatial-phenotype-pooled figures; readable in 2-column journal layout (~3.5 inch panel width); axis labels with units; legend placement standardized.
- **Palette:** finalize phenotype colors (suggested: ColorBrewer sequential for severity ordering OR distinct categorical for clarity). Apply across all figures uniformly.
- **Composites:** multi-panel paper figures combining specific V4 + V5 + spatial panels per Priya's paper narrative. E.g., "Figure 3: cross-modality tongue recovery" might combine V4 of `tongue_lick1_y_peak` + V4 of `spatial_wasserstein_tongue_spout_midpoint_tone_aligned_all` + V5 of both.
- **ipsi/contra labeling:** per `AnimalInfo.mouse_side_to_ipsi_contra()` helper. All 8 current cohort animals are L-stroke → mouse-L = ipsi, mouse-R = contra. Side labels in figure legends/axis labels.

**Output:** `pipeline_outputs/phase_9_1_figures/composites/<composite_name>.svg` + `.png` + final-paper-asset variants.

---

## 7. Task breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch (off post-Phase-9-close main) | (none) | 0 | <5 min |
| Task 1 — V4 phenotype-pooled curves (7 headline kinematic) | `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint>/v4_*.svg` × 7 | 1-2 | 1-2 days |
| Task 2 — V5 phenotype-pooled boxplots (7 headline kinematic) | `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint>/v5_*.svg` × 7 | 1 | 1 day |
| Task 3 — Phenotype-pooled spatial recovery curves (48 spatial endpoints) | `pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/...` × 48 | 1-2 | 1-2 days |
| Task 4 — Pub-quality polish: typography + palette + ipsi/contra labels | Style module + applied to all figures | 2 | 2 days |
| Task 5 — Composite figures per Priya paper narrative | `pipeline_outputs/phase_9_1_figures/composites/...` | 1-2 | 1-2 days |
| Task 6 — Verification + Priya scientific review | `.scratch_phase_9_1/verdict.md` | 0 | 1-3 days (Priya bandwidth) |
| Task 7 — DECISIONS + MIGRATION_LOG + PR | 2 docs files + PR | 1 | 30-60 min |

**Estimated total: ~7-10 commits, ~5-7 days CC wall time (excluding Priya review).**

Substantially smaller than the 2026-05-15 draft's 2-3 weeks estimate because most compute is now in Phase 9 (per-animal baselines, stats results, per-axis tests). Phase 9.1 is consumer + visualization + polish.

---

## 8. Dependencies + ordering

**Hard prerequisites:**
- **Phase 9 closed** (all 9 Tasks; Task 9 close + PR merged). Phase 9.1 reads from Phase 9's `pipeline_outputs/stats/inputs/` + `pipeline_outputs/stats/results/`.

**Soft prerequisites (for full paper-quality polish):**
- Phenotype color palette agreed with Priya before Task 4 to avoid rework.
- Composite figure layouts agreed with Priya before Task 5 (paper narrative-driven).

**Could happen concurrently:**
- Pub-figures phase (if Priya wants explicit paper-figure phase distinct from 9.1 polish) — likely overlap; 9.1's pub-polish IS the pub-figures work.

**Phase 9.1 → no downstream phase blocked.** Phase 9.1 close is effectively phase-end for the consolidation; what remains is paper writing + figure-specific polish that happens out-of-pipeline.

---

## 9. Open scoping questions

- **OPEN-Q 1:** Phenotype palette choice — sequential (severity ordering) vs categorical (4 distinct colors). Suggestion: ColorBrewer YlOrRd 4-step (light yellow = mild → dark red = severe) for severity-ordering clarity. Priya finalizes during Task 4.
- **OPEN-Q 2:** Composite figure inventory — Priya enumerates which V4/V5/spatial panels combine into which paper figures. Defer to Task 5 review.
- **OPEN-Q 3:** V4/V5 figure scope — only the 7 headline kinematic endpoints (per Addendum #8), or extend to all primary scalar endpoints? Default per Addendum #8: just the 7 headlines; other primaries get V1/V2 in Phase 9 only.
- **OPEN-Q 4:** Phenotype-pooled spatial figure scope — all 48 combos, or only the 4 Wasserstein headlines (tone_aligned/all per Addendum #3 HEADLINE)? Default: all 48 emitted, but composite figures feature only headlines.
- **OPEN-Q 5:** ipsi/contra figure axis convention — show mouse-L/R on axes with ipsi/contra annotation, or relabel axes ipsi/contra directly? Affects every figure with per-side data.

---

## 10. Next steps

1. **Phase 9 closes** (Task 9 close + PR merged). Phase 9.1 cannot start until Phase 9 outputs are on main.
2. Phase 9.1 Task 0 — branch off post-Phase-9-close main.
3. Phase 9.1 Tasks 1-2 — V4 + V5 for 7 headline kinematics. Iterate on layout with Priya per-figure-family.
4. Phase 9.1 Task 3 — phenotype-pooled spatial. Headline Wasserstein at tone_aligned/all first; expand to full 48 once layout settled.
5. Phase 9.1 Tasks 4-5 — pub polish + composites. Iterate with Priya on paper narrative.
6. Phase 9.1 Tasks 6-7 — verification + close.

---

## 11. References

- **Phase 9 kickoff:** `docs/prompts/phase-9-stats-kickoff.md` (with all 8 addenda; the source of truth for what Phase 9 produces).
- **Phase 9 inventory:** `.scratch_phase_9/endpoint_inventory.csv` (115 rows; tells Phase 9.1 what stats results to expect).
- **`configs/animals.yaml`:** per-animal `recovery_phenotype` + `epoch_boundaries` + `bin_days` + `stroke_laterality` — all stamped at Phase 9 Task 1.5.
- **`stats/recovery_epochs.py`:** `cohort_phenotype_summary` + `assign_epoch_label` helpers Phase 9.1 may invoke.
- **`AnimalInfo.mouse_side_to_ipsi_contra()`:** Phase 8a.10 scaffolding for ipsi/contra labeling.
- **Memory `project_eye_midpoint_convention.md`:** relevant if any figures use eye-centered coordinates.
- **Memory `feedback_iterative_addenda_pattern.md`:** Phase 9.1 may need its own addenda during scaffold review.
