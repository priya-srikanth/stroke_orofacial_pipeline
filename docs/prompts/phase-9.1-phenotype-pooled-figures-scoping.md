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

> **AMENDMENT 2026-05-25 (scoping locks ahead of kickoff drafting).** Four scoping questions locked during pre-kickoff planning conversation (Priya, 2026-05-25). These supersede the OPEN-Q defaults in §9 and update §1 primary deliverables + §6 figure inventory + §7 task table:
>
> - **Phenotype grouping (new lock):** **4-tier retained** (mild / moderate / moderate-severe / severe), faithful to `AnimalInfo.recovery_phenotype`. Phase 9.x's 3-tier `moderate-pool` grouping is NOT adopted for 9.1; the n=1 moderate and moderate-severe tiers render as single-animal descriptive traces (per §2 caveat). Rationale: 9.1 is figure work where descriptive single-animal traces are publishable; 9.x is stats work where pooled n≥2 is required for LMM convergence.
> - **V4/V5 figure scope (OPEN-Q 3):** **All ~20 confirmatory primary scalars** (NOT just the 7 headline kinematics). Every endpoint in the confirmatory family from Phase 9 gets V4 + V5 phenotype-pooled figures. ~40 figures total (20 endpoints × V4/V5). Headlines remain prominent in composites at Task 5. **SUPERSEDED by Amendment 2026-05-25 (b) below — see expanded exploratory-scalar scope.**
> - **Spatial scope (OPEN-Q 4):** **Wasserstein-all-scopes (12 figures).** Emit Wasserstein at all 4 scope/trial_group combos × 4 families ≈ 12 (some duplicates per family). UOT + JS divergence supplementary figures DEFERRED — re-evaluate after paper-figure review whether they add narrative value. Narrows from the 48-figure full grid in original scoping draft. **SUPERSEDED by Amendment 2026-05-25 (b) below — UOT + JS un-deferred.**
> - **Ipsi/contra labeling (OPEN-Q 5):** **Relabel axes ipsi/contra directly + caption caveat for cohort uniformity.** All per-side figure axes/legends show 'ipsi' and 'contra' directly. Each figure caption notes "All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R" for future R-stroke-cohort reproducibility.
>
> Two OPEN-Qs remain unlocked and defer to within-phase iteration: palette finalization (OPEN-Q 1, Task 4) and composite figure inventory (OPEN-Q 2, Task 5).

> **AMENDMENT 2026-05-25 (b) — Exploratory-figure scope expansion + parameterized runner.** Three scoping decisions taken during plan-mode review of CC's kickoff-drafting plan (Priya, 2026-05-25). Supersedes the V4/V5 scope (OPEN-Q 3) and spatial scope (OPEN-Q 4) locks from Amendment 2026-05-25 above. Rationale: Priya wants comprehensive exploratory-figure coverage to visualize how non-confirmatory endpoints behave, not just paper-headline figures.
>
> - **V4/V5 figure scope (revises OPEN-Q 3):** **ALL Phase 9 LMM-run scalar endpoints** (disk-verified count: **35** endpoints per `ls pipeline_outputs/stats/results/recovery/per_epoch/ | wc -l` excluding spatial + `_all.csv` aggregates; see Phase 9.1 kickoff §V4/V5 inventory for canonical list). Includes all confirmatory + non-confirmatory scalars: per-trial tongue + jaw kinematics, session-aggregate behavioral, derived velocity headlines, etc. **~70 V4/V5 figures total (35 × 2)**. Confirmatory + headline subsets get featured placement in Task 5 composites; the broader exploratory inventory is supplementary / data-exploration material. *(Original estimate "~80-100 endpoints / ~160-200 figures" REVISED DOWNWARD per disk audit during kickoff drafting 2026-05-25.)*
> - **Spatial scope (revises OPEN-Q 4):** **All 3 distributional metrics × all 4 scope/trial_group combos × 4 families = 48 phenotype-pooled spatial figures.** Wasserstein (16) + UOT cost (16) + JS divergence (16). UOT + JS supplementary figures NO LONGER deferred. Wasserstein at scope=tone_aligned/all (Addendum #3 HEADLINE METRIC) still gets prominent placement in composites; UOT + JS provide cross-metric corroboration in supplementary. *(Note: 2 orphan bare-slug spatial parquets [`spatial_wasserstein_jaw_eye_midpoint`, `spatial_wasserstein_tongue_spout_midpoint`] survive on disk from pre-Addendum-7 emit; Phase 9.1 Task 0.5 excludes them from emit.)*
> - **Parameterized figure runner (new lock):** Figure runner accepts an `--endpoint-list <path>` CLI flag and defaults to the expanded Phase 9.1 endpoint set (config file or sentinel value). Future exploratory emit (e.g., new endpoint families post-9.1, scope narrowing for paper-figure subset) becomes a single-command rerun against a different endpoint-list file. ~0.5 day design uplift; pays off if scope shifts during paper-figure review or 9.x. Same flag/pattern applies to both V4/V5 runners and the phenotype-pooled-spatial runner.
>
> **Updated estimated scope (disk-verified):** ~70 V4/V5 + 48 spatial ≈ **~118 figures total** (vs. 46 in the prior amendment). Per-figure code is unchanged (Phase 9.1 is consumer + visualization); the scale-up is loop iterations, not new algorithms. Wall-time estimate ~10-14 days CC (driven by figure-style iteration cost + verification time across the broader inventory, not by figure-count scaling).
>
> **Excluded from V4/V5 by design:** `latency_hist` is confirmatory but is a `vector_per_session` endpoint without LMM treatment (KS-bridge methodology per Phase 9 Addendum #4) — it has no `recovery/per_epoch/` stats result CSV. **NEW LOCK 2026-05-25 (b) follow-up (Priya):** Phase 9.1 adds a separate phenotype-pooled CDF/histogram figure family for `latency_hist`. Methodology: pool per-trial first-correct-lick latencies across animals within each phenotype tier × epoch; emit phenotype-pooled CDFs (one trace per epoch within each phenotype panel) consuming the existing `stats/inputs/latency_hist/<animal>.parquet` rows. Estimated figure count: 1-4 figures (final layout determined at Task 0.5 review — single 4-panel composite vs. one figure per phenotype). No new stats methodology needed; KS-bridge from Addendum #4 already provides cross-epoch p-values for caption annotations. Same `--endpoint-list` parameterized runner per Q-lock 6 applies. Total figure count revised: ~118 + 1-4 latency_hist ≈ **~120 figures**.

> **NEW LOCK 2026-05-25 (b) second follow-up (Priya) — tongue ipsi-shift figure families.** Phase 9.1 adds two new figure families specifically to visualize whether tongue position/orientation shows a consistent ipsi-side shift after stroke (memory finding #6: direction-sensitive endpoints x/angle show ipsi-contra asymmetry; amplitude endpoints y don't). Both families plot on **tone-aligned trial time** as the x-axis (seconds post-tone) and use the existing 4-tier phenotype grouping per Q-lock 1 with epoch traces (pre / acute / sub_acute / chronic). Ipsi/contra side-split per Q-lock 4 (axes labeled directly + caption caveat for cohort-uniformity).
>
> **Baseline normalization (LOCKED — delta-from-baseline at every tone-aligned time bin):** Y-axis values are **delta** (post − pre-stroke baseline), NOT raw tongue angle / x. This is per-bin trajectory subtraction (not Addendum #6's per-trial scalar subtraction):
> - **Per-animal baseline trajectory:** computed from PRE-stroke sessions only, separately for each trial side (ipsi-trials baseline = mean over pre-stroke mouse-L trials per animal; contra-trials baseline = mean over pre-stroke mouse-R trials per animal — since all 8 cohort animals are L-stroke, mouse-L = ipsi, mouse-R = contra).
> - **Per-session delta trajectory:** for any session (pre or post-stroke) in any animal, compute the session's mean trajectory(t) across trials of the given side, then subtract that animal's pre-stroke side-matched baseline trajectory(t) at each tone-aligned time bin. The result is a per-session delta(t) trajectory.
> - **Pooling:** delta(t) trajectories from all sessions within (phenotype, epoch, side) get pooled to produce the cohort-level mean ± SEM delta trace for that cell.
> - **Pre-epoch trace REQUIRED as a baseline-noise reference (LOCKED):** Pre-stroke is plotted as a full epoch trace alongside acute / sub_acute / chronic — NOT omitted or implicitly assumed zero. Each pre-stroke session's delta trajectory is ≈0 with session-to-session fluctuations around 0 driven by intrinsic baseline variability (between-session trial composition, animal day-to-day state, etc.).
> - **Scientific role of the pre trace:** the thin per-session overlay (two-layer rendering, see below) for the pre epoch reveals the natural session-to-session variability "band" around zero. This visually communicates what "no change" looks like — and any post-stroke epoch trace that stays within the pre band is consistent with noise, while traces that exceed the pre band are evidence of a real stroke-induced shift. Reading the magnitude of post-stroke deltas against the pre band is the key visual comparison.
> - **Caption convention:** y-axis label reads "delta tongue angle (deg, baseline-subtracted)" or "delta tongue x (px, baseline-subtracted)" — the y=0 reference line should be drawn explicitly in each panel.
>
> *(2026-05-25 amendment: Originally drafted as 3 families; Family 8.1 [cohort/phenotype-pooled phase-aligned angle, NOT side-split] DROPPED per Priya — redundant with side-split Family 8.1 [angle, lick1/lick2/median] below.)*
>
> **Time-binning convention (LOCKED, applies to both families):** Match the existing tongue_angle / mean_sem plot convention used elsewhere in the codebase. Phase 9.1 figure code reuses the existing trajectory-plotting machinery (whatever bin width + post-tone window are already coded for tone-aligned tongue_angle / x trajectory plots — likely under `src/stroke_orofacial/dlc_kinematics/` or downstream rendering scripts). CC discovers the convention from the existing plotting code at Task 0.5 and inherits it. No new binning OPEN-Q.
>
> **Family 8.1 — Tongue angle at lick 1 + lick 2 + per-trial median (ipsi/contra side-split):**
> - **X-axis:** tone-aligned trial time (sec post-tone), binned per existing convention. **Y-axis:** tongue angle (deg), baseline-normalized.
> - **3 endpoint sub-families:** `tongue_lick1_angle_at_ypeak` (one (lick1_t_peak_ms, lick1_angle) point per trial), `tongue_lick2_angle_at_ypeak` (same for lick 2), `tongue_median_angle_at_peak_velocity` (one (median_peak_t_ms, median_angle) point per trial via median across licks).
> - **Trace:** mean ± SEM across trials pooled into tone-aligned time bins within (phenotype, epoch, trial side).
> - **Layout:** **side-by-side panels per phenotype** — ipsi panel + contra panel — with multiple epoch traces in each. Panels labeled "ipsi" and "contra" with caption caveat for cohort-uniformity per Q-lock 4 (all 8 cohort animals L-stroke).
> - **Figure count:** 3 endpoint sub-families × (4 phenotype × 2 side panels = 8 panels) ≈ 3 figures.
>
> **Family 8.2 — Tone-aligned tongue x trajectory (ipsi/contra side-split):**
> - **X-axis:** tone-aligned trial time (sec post-tone), binned per existing convention. **Y-axis:** baseline-normalized raw tongue x position (continuous per-frame DLC trajectory, NOT x at Y-peak / NOT x at peak velocity per Priya 2026-05-25 clarification).
> - **Trace:** mean ± SEM tongue x(t) trajectory pooled across trials within (phenotype, epoch, trial side). Per-frame DLC tongue x data aligned to tone onset.
> - **Layout:** side-by-side ipsi/contra panels per phenotype with multi-epoch traces (same as Family 8.1).
> - **Data source:** continuous DLC tongue x time-series data (CC finds canonical source during kickoff amendment — likely from `pipeline_outputs/dlc_kinematics/<animal>/...` per-trial tongue x arrays; this is NOT in `stats/inputs/` but IS what the existing tongue_x mean_sem trajectory plots consume). Reuse the existing trajectory plotting machinery + add phenotype-pool + ipsi/contra split wrappers.
> - **Figure count:** 1 figure (4 phenotype × 2 side panels = 8 panels packed in one composite) or 4 figures (one per phenotype) — locked at Task 0.5.
> - **Scientific framing:** most direct visual test of the ipsi-shift hypothesis. If tongue preferentially shifts toward the ipsi side after stroke, contra-trial panels show a sustained ipsi-ward x offset post-tone (where the animal is "trying" to lick contra but the deficit pulls tongue position ipsi). Likely paper-narrative figure for memory finding #6.
>
> **Q-lock 8 packaging:** Both families share the same x-axis (tone-aligned trial time per existing binning) and reuse existing trajectory-plotting machinery wherever possible (NOT new mean_sem code). The Phase 9.1 lift is adding phenotype-pool + ipsi/contra split wrappers around existing plotting primitives.
>
> **Rendering style (LOCKED, applies to both Q-lock 8 families):** Each epoch trace within a panel is rendered as a TWO-LAYER overlay:
> - **Background layer:** thin transparent (low-alpha, suggest α≈0.2-0.3) per-session traces, one line per (animal, session) contributing to that epoch's pool, rendered in the same color as the epoch trace. Allows visual inspection of session-to-session consistency and reveals whether the pooled mean is driven by all sessions vs. by outliers.
> - **Foreground layer:** prominent mean ± SEM trace for the epoch (solid line at higher alpha + SEM band), rendered on top of the per-session traces in the same color.
> - **Per-session trace definition:** for Family 8.1 (per-lick angle), a session trace is that session's tone-aligned time-binned mean angle trajectory across all licks in the session (one bin-value per time bin). For Family 8.2 (continuous x trajectory), a session trace is that session's mean x(t) trajectory across trials in the session.
> - **Caveat:** session-trace overlay is for visualization only; underlying stats remain at the LMM-on-session-level granularity per Phase 9 Addendum #6.
> - **Open extension consideration:** the same two-layer rendering style may be desirable for V4 (per_bin phenotype-pooled recovery curves) and/or V5 (per_epoch boxplots) — for V4, "session trace" would be per-animal trajectory; for V5, individual session-points already render via boxplot whiskers/scatter. Defer V4/V5 extension to Task 1-2 scaffold review (Priya can request retroactive application if the Q-lock 8 style reads cleanly).
>
> **Total figure count revised:** ~120 + ~4-7 ipsi-shift figures (3 family-8.1 + 1-4 family-8.2, depending on phenotype-packing layout decisions at Task 0.5) ≈ **~124-127 figures**.
>
> **Q-C dedup (from CC plan-mode review) RETAINED:** confirmatory Wasserstein endpoints emit ONLY as phenotype-pooled-spatial figures (Task 3), NOT also as V4/V5 (Tasks 1-2). Same de-dup applies to UOT + JS — they go in spatial-figure pipeline, not V4/V5. V4/V5 is **scalar-only** (`value` column from kinematic + behavioral parquets); spatial-figure pipeline handles Wasserstein/UOT/JS distance metrics from spatial parquets.

---

## 1. Goals + scope

Phase 9.1 produces the cross-animal phenotype-pooled figure tier of the Phase 9 paper-figure system, plus pub-quality polish. It consumes Phase 9's already-materialized inputs + stats results; it does NOT re-implement materialization or per-animal stats.

**Primary deliverables (per 2026-05-25 amendment locks):**
1. **V4 + V5 figure grid** per Addendum #8 for **all ~20 confirmatory primary scalar endpoints** (OPEN-Q 3 LOCKED). ~40 figures total.
   - V4: per_bin phenotype-pooled — one panel per endpoint; multiple traces (one per phenotype tier); bin_midpoint_rel_day vs cohort mean ± SEM within phenotype.
   - V5: per_epoch phenotype-pooled — one panel per endpoint; boxplots grouped by (phenotype × epoch).
   - 7 headline kinematics (per Addendum #8) get featured placement in Task 5 composites; remaining ~13 confirmatory scalars provide supporting figure inventory.
2. **Phenotype-pooled spatial figures** for the **Wasserstein-all-scopes set (~12 figures: 4 families × 3-4 scope/trial_group combos)** (OPEN-Q 4 LOCKED). UOT + JS divergence supplementary figures DEFERRED pending paper-figure review. Wasserstein at scope=tone_aligned/all (Addendum #3 HEADLINE METRIC) gets prominent placement in composites.
3. **Pub-quality polish** per Addendum #1 (C):
   - Typography (consistent font sizes; readable in 2-column journal layout)
   - Color-palette harmonization (consistent phenotype colors via 4-tier scheme; OPEN-Q 1 finalizes palette at Task 4)
   - Multi-panel composite figures for the paper
   - **ipsi/contra labeling: relabel axes/legends ipsi/contra directly + figure-caption caveat** "All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R" (OPEN-Q 5 LOCKED)

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

- **OPEN-Q 1 (still open, defers to Task 4):** Phenotype palette choice — sequential (severity ordering) vs categorical (4 distinct colors). Suggestion: ColorBrewer YlOrRd 4-step (light yellow = mild → dark red = severe) for severity-ordering clarity. Priya finalizes during Task 4 scaffold review.
- **OPEN-Q 2 (still open, defers to Task 5):** Composite figure inventory — Priya enumerates which V4/V5/spatial panels combine into which paper figures. Defer to Task 5 review.
- **OPEN-Q 3 — LOCKED 2026-05-25 (b):** V4/V5 figure scope = **ALL Phase 9 LMM-run scalar endpoints (~80-100)**. Supersedes the prior 2026-05-25 "~20 confirmatory only" lock — expanded to comprehensive exploratory-scalar coverage per Priya's "visualize what these look like" framing. ~160-200 V4/V5 figures. Confirmatory subset still featured in composites at Task 5.
- **OPEN-Q 4 — LOCKED 2026-05-25 (b):** Phenotype-pooled spatial figure scope = **all 3 distributional metrics × all 4 scope/trial_group combos × 4 families = 48 figures** (Wasserstein 16 + UOT 16 + JS 16). Supersedes the prior 2026-05-25 "Wasserstein-only-12-figures" lock — UOT + JS un-deferred. Wasserstein at tone_aligned/all (HEADLINE) still featured in composites; UOT + JS provide cross-metric corroboration.
- **OPEN-Q 5 — LOCKED 2026-05-25:** Ipsi/contra axis convention = **relabel axes ipsi/contra directly + figure-caption caveat for cohort uniformity** ("All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R").

**New lock 2026-05-25 (phenotype grouping):** Phase 9.1 retains **4-tier grouping** (mild / moderate / moderate-severe / severe) faithful to `AnimalInfo.recovery_phenotype`. Phase 9.x's 3-tier `moderate-pool` (PS46+PS51) is NOT adopted in 9.1; the n=1 tiers render as single-animal descriptive traces per §2 caveat.

**New lock 2026-05-25 (b) (parameterized runner):** Figure runner accepts `--endpoint-list <path>` CLI flag and defaults to the expanded Phase 9.1 endpoint set. Future exploratory emit becomes a single-command rerun against a different endpoint list. Applies to both V4/V5 and phenotype-pooled-spatial runners.

**Q-C dedup retained:** V4/V5 is scalar-only (`value` column from kinematic + behavioral parquets); spatial-figure pipeline handles Wasserstein/UOT/JS metrics from spatial parquets. Confirmatory Wasserstein endpoints do NOT double-emit.

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
