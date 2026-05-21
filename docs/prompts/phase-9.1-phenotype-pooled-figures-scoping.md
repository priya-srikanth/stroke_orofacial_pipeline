# Phase 9.1 — Phenotype-Pooled Pre-Stroke-Normalized Figures — SCOPING DOCUMENT

> **⚠️ THIS IS A SCOPING DOC.** Drafted 2026-05-15 by Cowork during Phase 7c.2 in-flight period after Priya's forward-thinking message. Most design decisions LOCKED by Priya in the originating discussion; remaining open questions are flagged inline with **OPEN-Q:**. PS47 scaffold work follows this scoping; cohort-pooled emit happens after Phase 7c.2 close.

---

## 1. Goals + scope

Phase 9.1 emits **phenotype-pooled, pre-stroke-baseline-normalized** versions of the per-animal descriptive figures already produced by Phase 7c.2 + Phase 7a kinematics. The pooled plots highlight stroke-recovery dynamics by phenotype severity, with per-animal baseline variance removed via per-animal pre-stroke subtraction.

**Primary deliverable:** new figure directory `pipeline_outputs/dlc_kinematics/phenotype_pooled/<figure_family>/<phenotype>/...` containing per-phenotype pooled plots for each figure family.

**Out of scope:**
- Statistical tests (Phase 9.2 stats — descriptive figures precede stats).
- Aesthetic-tier polish for paper figures (pub-figures phase).
- New endpoint computation (uses existing Phase 7c.2 + 7a outputs as-is).
- Stats-summary plots like forest plots / recovery curves with p-values (Phase 9.2).

---

## 2. Phenotype groupings (LOCKED Priya 2026-05-15)

| Phenotype | Animals | n |
|---|---|---|
| Mild | PS47, PS48, PS49, PS50 | 4 |
| Mod-severe | PS46, PS51 | 2 |
| Severe | PS54, PS55 | 2 |

PS55 confirmed in all analyses. The 4/2/2 sizes are small — pooled figures show per-session points (multiple per animal) for within-phenotype density, plus phenotype-level summary; the small n caveat is unavoidable but mitigated by per-session multiplicity.

**Encoding:** add `phenotype: mild | mod-severe | severe` field to `configs/animals.yaml` per-animal entry. Reads via `get_animal(animal).phenotype` in pooling scripts.

---

## 3. Pooling approach (LOCKED Priya 2026-05-15)

**Multiple per-session points per animal** in pooled analyses, NOT "per-animal mean then pool." Each animal contributes as many points as it has sessions; phenotype-pool aggregates across all sessions across all animals in the phenotype.

**Why:** small per-animal session counts means per-animal means lose data; per-session multiplicity preserves within-animal variance + handles different per-animal session timings honestly. Visualization shows per-session points scattered + phenotype-level summary.

**Visualization style:**
- **Per-phenotype separate panels** (3 panels per figure, one per mild / mod-severe / severe). Direct cross-phenotype comparison via panel adjacency. Default layout: 1×3 row or 3×1 column depending on figure family.
- **Per-session points visible:** scatter / faint individual lines per session within phenotype.
- **Phenotype-level summary:** mean (or median) + SEM (or IQR) band overlaid.
- **Per-animal color or marker** within a panel so reader can identify which session belongs to which animal (small categorical palette per phenotype; 4 colors mild, 2 each mod-severe + severe).

---

## 4. Per-animal pre-stroke baseline normalization (Options LOCKED per figure family)

For each (animal, trial_type) compute baseline from pre-stroke sessions (`rel_day <= 0`), then normalize per-session post-stroke data. Per-figure-family normalization choice:

| Figure family | Normalization option | Reasoning |
|---|---|---|
| mean_sem (time-course) | **Option B** (per-time-point subtractive) OR **Option C** (per-time-point z-score) | Time-course has natural temporal structure; per-time-point matters. C if cross-animal scale dominates B's signal. Priya: pick B for default; C as sanity check. |
| Phase plots (velocity-vs-position etc., parametric in time) | **Option B or C** (per-time-point subtractive in 2D phase-space) | Phase plots are time-course in 2D; subtract pre-stroke trajectory at corresponding time-point. |
| tongue_angle (distribution-level) | **Option A** (aggregate baseline subtraction) OR diverging-cmap difference histogram | Distribution-level; scalar baseline. Diverging cmap mirrors Phase 7c.2 spatial proportion-diff if visual consistency wanted. |
| Tongue metrics (scalar per-trial endpoints) | **Per-animal subtractive** (each trial's metric − animal's pre-stroke mean of that metric) | Standard delta-from-baseline. Plotted as scatter / violin per phenotype × time-bin. |
| Proportion-diff (Phase 7c.2 spatial heatmaps) | Already pre-stroke-normalized; phenotype-pool = animal-wise average of H_diff arrays | Existing Phase 7c.2 output is per-bin Δ proportion vs all-pre-stroke. Pool by averaging across animals in phenotype. |
| UOT displacement (Phase 7c.2 mass_change + arrows) | Already pre-stroke-normalized; phenotype-pool = animal-wise average of mass_change + mean OT cost across phenotype | Existing Phase 7c.2 output. Per-bin mean of mass_change; arrows averaged per bin if uniform-grid (mean direction + magnitude per bin). |

**Option B vs C tie-break (TODO during scaffold work on PS47):**

- B (subtractive): preserves units; readable as "how much did post change from baseline."
- C (z-score): unitless; emphasizes pre-stroke trial-to-trial variance as noise scale; better if absolute units vary wildly across animals.

CC + Priya iterate on PS47 scaffold to pick B vs C visually, OR emit BOTH and pick post-hoc.

---

## 5. The binning challenge — combining 2d-cohort and 7d-cohort animals in one phenotype

**The problem:** Mod-severe = PS46 (2-day bin cadence) + PS51 (7-day bin cadence). Pooled time-course plots need a common time axis. Current Phase 7c.2 binned outputs use the per-animal singleton bin_size (Q23) — PS46 emits 2d bins; PS51 emits 7d bins. Their bin boundaries don't align; their session-count-per-bin densities differ; you can't directly average a "days 0-2" PS46 bin with a "days 0-7" PS51 bin.

**Options for handling this:**

### Option (a) — Continuous `rel_day` axis with smoothing

Don't bin pooled data at all. Plot every per-session point at its actual `rel_day` value on a continuous x-axis. Phenotype-level summary via local smoothing (LOESS, rolling mean, kernel regression). Handles per-animal cadence differences transparently.

**Pros:** Most honest about timing; no information loss from binning; works across any cadence mix.
**Cons:** Plots can look noisy with small n; smoothing parameters (kernel width, bandwidth) become a tuning knob; readers don't get "this is the 7-day-post-stroke effect" type statements as easily.

### Option (b) — Re-bin everyone to a common bin size

Force all animals into a common bin grid for pooled analyses. E.g., re-bin PS51's 7d cadence to 14d (multiples of 7d) while re-binning PS46's 2d to 14d — common 14d grid both can be averaged onto. Or pick 7d as the common grid (PS46 collapses 2d → 7d via re-aggregation).

**Pros:** Familiar binned-plot style; direct cross-phenotype comparability via shared x-bins.
**Cons:** Loses PS46's 2d temporal resolution; arbitrary choice of common bin size; need to re-aggregate per-animal sessions into the new bins.

### Option (c) — Phenotype-specific bin grids (separate axes)

Each phenotype uses its OWN appropriate bin grid for the time axis; cross-phenotype comparison is by panel, not by overlay. PS46-bin animals use 2d bins; PS51-bin animals use 7d bins; severe (PS54+PS55) uses 7d bins. Mod-severe is the only mixed-cadence phenotype; for it, pick one of (a) or (b).

**Pros:** Each phenotype's panel uses its natural cadence; no information loss.
**Cons:** Cross-phenotype time-axis is no longer numerically aligned; comparisons are qualitative (panel-by-panel).

### Option (d) — Define new common bin grid by post-stroke time epochs

Define semantic time-epochs that span all animals: acute (rel_day 1-3), subacute (4-14), chronic (15-42), late (43+). Each per-session point assigned to its epoch. Phenotype-pool = aggregate within (phenotype, epoch). Plotted as 4 bins per panel with per-animal points in each.

**Pros:** Common semantic axis across all animals + phenotypes; meaningful scientific grouping.
**Cons:** Coarser resolution than the underlying per-animal binning; epoch boundaries need scientific justification.

**My recommendation:** Option (a) **for time-course plots (mean_sem, tongue metrics continuous version)** + Option (d) **for phase plots (recovery-phase-stratified panels per §6.2)**. Continuous + smoothed for trajectories (where time-axis precision matters); epoch bins for the phase-plot variant where epoch IS the panel axis.

**OPEN-Q 1 (RESOLVED Priya 2026-05-15):** Option (a) continuous rel_day + smoothing locked tentatively; may iterate after PS47 scaffold review.

**OPEN-Q 2 (RESOLVED via OPEN-Q 5 hybrid scheme):** Epoch boundaries locked as acute 1-3 / subacute 4-14 / chronic 15-42 / late 43+. Aligns with the OPEN-Q 5 bin-granularity transition at day 14 (2d→7d).

**OPEN-Q 5 (RESOLVED Priya 2026-05-15):** Hybrid bin scheme — 2d bins for first 14 days post-stroke; 7d bins thereafter. Applies to all per-epoch bin-aggregating plots across all animals (corrected understanding: PS51, PS54, PS55 have dense first-2-week session data; their `bin_days = 7` config is the DEFAULT cross-session aggregate granularity, NOT a session-cadence spec, so the 2d-bin region works for all phenotypes).

---

## 6. Figure family inventory + per-family plan

### 6.1 mean_sem time-course (Phase 7a.6 output)

**Source:** `pipeline_outputs/dlc_kinematics/mean_sem/<bodypart>/<center_mode>/<trial_group>/<plot_family>/<animal>/` time-course traces.

**Normalization:** Option B per-time-point subtractive. For each (animal, trial_type, time-point t): delta(t) = post_mean(t) − pre_mean(t).

**Pooled plot:** 3 panels (one per phenotype). X-axis: time relative to tone or other alignment event. Y-axis: delta from pre-stroke baseline. Per-session traces faint in animal-color; per-phenotype mean + SEM band bold. Continuous `rel_day` color overlay OR Option-(d) epoch faceting (additional dimension).

**Per-phenotype per-trial-type fanout:** L trials + R trials separate panels (or trial-group as a 3rd column dimension in the panel grid).

### 6.2 Phase plots (recovery-phase-stratified panel views — LOCKED Priya 2026-05-15)

**NOT 2D state-space trajectories.** "Phase" here means stroke recovery phase (acute / subacute / chronic / late) as a STRATIFICATION axis. Phase plots take the same underlying data as the continuous time-course figures (§6.1 mean_sem, §6.4 tongue metrics) and replicate them in a per-recovery-phase panel layout.

**Source:** Same as mean_sem / tongue metrics / tongue_angle — no new data computation. Phase plots are a presentational re-layout.

**Epoch boundaries (LOCKED — aligned with hybrid bin scheme from OPEN-Q 5):**

| Epoch | rel_day range | Bin granularity (per OPEN-Q 5 hybrid scheme) |
|---|---|---|
| Acute | 1-3 | 2d bins |
| Subacute | 4-14 | 2d bins |
| Chronic | 15-42 | 7d bins |
| Late | 43+ | 7d bins |

Boundary at day 14 aligns with the bin-granularity transition (2d→7d) per OPEN-Q 5.

**Pooled plot:** for each figure family that supports phase-stratification (mean_sem, tongue metrics, tongue_angle), emit 4 figures (one per epoch) × 3 phenotype panels each. Each panel shows the same metric as the continuous time-course version but restricted to data within that epoch window. Pre-stroke baseline subtraction (Option B/C per family) applied identically; phenotype pooling identically.

Alternative: 4 epochs × 3 phenotypes = 12-panel grid per figure (3 rows × 4 cols). CC iterates with Priya during PS47 scaffold to pick 4-separate-figures vs 12-panel-grid layout based on readability.

**Phase plots are an ADDITIONAL figure family layered on top of the continuous time-course figures** — they don't replace mean_sem / tongue metric / tongue_angle continuous figures, just add an alternative phase-stratified view of the same data.

### 6.3 tongue_angle (Phase 7a.4 cross-session output)

**Source:** `pipeline_outputs/dlc_kinematics/tongue_angle/within_session/<animal>/...` + `cross_session/<animal>/...` distributions.

**Normalization:** Option A aggregate baseline subtraction (scalar per animal). For each post-stroke session: delta_angle = post_angle_distribution − pre_angle_average.

Alternative: diverging-cmap "delta histogram" mirroring Phase 7c.2 proportion_diff convention.

**Pooled plot:** 3 panels per phenotype. X-axis: tongue angle. Y-axis: count or proportion. Pre-stroke distribution + post-stroke distribution overlaid; difference curve as third trace. OR diverging-cmap difference histogram below.

### 6.4 Tongue metrics (per-trial scalar endpoints)

**Source:** `pipeline_outputs/dlc_kinematics/per_trial/tongue/<animal>/<date>.json` (post-Phase-7d) OR `dlc_kinematics/endpoints/<animal>/<date>.json` (current pre-7d).

**Suggested metric inventory (Priya 2026-05-15):**
- max excursion 1st lick (presumably tongue position peak)
- max excursion 2nd lick
- max abs x excursion 1st lick
- max abs x excursion 2nd lick
- max velocity (1st lick? 2nd lick? Per-lick overall?)

**OPEN-Q 4:** Full metric list — Priya enumerates. Probably ~10-20 scalars total. CC's Task 1 generates the full inventory from the per_trial JSON schema.

**Normalization:** Per-trial delta = per-trial metric − per-animal pre-stroke mean of that metric. Optionally z-score if scales vary.

**Pooled plot:** 3 panels per phenotype, one metric per figure (or grid of metrics in one figure). Y-axis: delta from per-animal pre-stroke mean. X-axis: rel_day (Option (a) continuous) or epoch (Option (d)). Per-session points scatter; phenotype mean+SEM bold.

### 6.5 Proportion difference (Phase 7c.2 spatial heatmaps)

**Source:** Per-bin H_diff arrays computed on-demand from Phase 7c.2 centered parquets per family entry + bin_size + trial_group.

**Already pre-stroke-normalized.** Phenotype-pool = animal-wise average of H_diff across animals within phenotype, per bin.

**Pooled plot:** 3 panels per phenotype × original per-bin grid layout (Q36). Diverging cmap unchanged from Phase 7c.2 (red=increased, blue=decreased, grey-at-zero midpoint, white-for-no-data per Q25/Q43.B). Q42 percentile-95 vmax applied at pooled scale (across all bins in (phenotype, family, scope, bin_size, trial_group)).

**Mod-severe pooling caveat:** PS46 (2d bins) and PS51 (7d bins) bin grids don't align. Either Option (c) per-bin_size separate panels OR re-aggregate per Option (b) common-bin-size. Per Option (a) doesn't apply here since proportion_diff is inherently binned.

### 6.6 UOT displacement (Phase 7c.2 mass_change + arrows)

**Source:** Per-bin mass_change + arrow plans computed on-demand from Phase 7c.2.

**Already pre-stroke-normalized.** Phenotype-pool = animal-wise average of mass_change per bin + mean OT cost across animals.

**Pooled plot:** 3 panels per phenotype × per-bin grid layout. mass_change diverging cmap unchanged. Arrows: per-bin mean direction + magnitude averaged across animals' arrows for that bin.

**Mod-severe binning:** same bin alignment issue as proportion_diff. Same resolution options.

---

## 7. Task breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch | (none) | 0 | <5 min |
| Task 1 — Endpoint + figure-family inventory | `.scratch_phase_9.1/figure_inventory.md` + tongue metric list (per OPEN-Q 4) | 0 | 1-2 hr + Priya review |
| Task 2 — Per-animal baseline computation helper | `phase_9_1/baseline.py` (per-animal pre-stroke baseline computation, Options A/B/C all supported) | 2 | half day |
| Task 3 — PS47 scaffold (one figure family at a time) | render code per family, iterate visually with Priya | 3-5 | 1-2 weeks (Priya bandwidth-dependent) |
| Task 4 — Cohort pooled emit | all phenotypes × all families × per-family normalization | 1-2 | 2-4 hr cohort compute |
| Task 5 — Verification + Priya sign-off | `.scratch_phase_9.1/verdict.md` | 0 | 1-2 days (Priya review) |
| Task 6 — DECISIONS + MIGRATION_LOG | 2 docs files | 1 | 30-60 min |

**Estimated total: ~10-15 commits, ~2-3 weeks CC wall time (Priya-review-bound, not compute-bound).**

---

## 8. Dependencies + ordering

**Hard prerequisites:**
- Phase 7c.2 closed (compute-on-demand spatial figure infrastructure + canonical post-fix kinematics outputs).
- Phase 7d closed (per_frame/per_trial path conventions stable before scaffold code targets them).

**Soft prerequisites:**
- F-P-7 alignment-templates closed (so the new pipeline is self-sufficient).

**Could happen concurrently:**
- Phase 9.2 stats kickoff drafting (Phase 9.2 consumes the per-animal-baseline-normalized arrays that Phase 9.1 produces; partial parallelization possible).

**Phase 9.1 precedes Phase 9.2 stats** — descriptive figures inform what stats are scientifically interesting before pre-registration.

---

## 9. Remaining open questions

**RESOLVED Priya 2026-05-15:**

- **OPEN-Q 1:** Continuous rel_day + smoothing (Option a); may iterate after PS47 scaffold review.
- **OPEN-Q 2:** Epoch boundaries acute 1-3 / subacute 4-14 / chronic 15-42 / late 43+ (resolved via OPEN-Q 5 hybrid scheme).
- **OPEN-Q 3:** DISSOLVED — "phase plots" = recovery-phase-stratified panels per §6.2, NOT 2D state-space trajectories. No phase-plane pairs to enumerate.
- **OPEN-Q 4:** CC enumerates from per_trial JSON schema during Task 1.
- **OPEN-Q 5:** Hybrid bin scheme — 2d bins for first 14d post-stroke, 7d bins thereafter, all animals. PS51/PS54/PS55 dense first-2-week data confirmed.

**REMAINING (tactical, deferred to scaffold iteration with PS47 outputs):**

- **OPEN-Q 6:** Pre-stroke baseline computation — include ALL pre-stroke sessions per animal, or restrict to recent pre-stroke (e.g., last 5 sessions before stroke)? Recent-only is more conservative; all-pre-stroke gives more statistical power.
- **OPEN-Q 7:** Outlier handling in pre-stroke pool — robust statistics (median, IQR) vs parametric (mean, SD)? Affects Option A (baseline statistic) + Option C (scale).
- **OPEN-Q 8:** Mean_sem normalization B vs C — default B, optional C? Or emit both for direct comparison?
- **OPEN-Q 9:** Per-animal color/marker palette — Suggested: cycle Phase 7c.2 whiskers Q39 categorical palette (red/orange/yellow/blue/cyan/purple) within each phenotype panel.
- **OPEN-Q 10:** Output path structure — Suggested: `pipeline_outputs/dlc_kinematics/phenotype_pooled/<figure_family>/<phenotype>/<plot_specifier>.svg`. CC's call.

---

## 10. Next steps

1. Priya answers the OPEN-Qs (especially Q1, Q2, Q4, Q5).
2. CC + Cowork begin Task 2 — per-animal baseline computation helper. Implementation works on PS47 once `bs2o2pohl` outputs are available.
3. Task 3 PS47 scaffold iterates with Priya visual review for one figure family at a time:
   - Iteration order: mean_sem (most-developed normalization story) → tongue metrics (scalar; simpler) → tongue_angle (distribution; conceptually new) → proportion_diff + UOT (already-normalized; phenotype-pooling validation) → phase plots (newest; depends on per_frame data).
4. After PS47 scaffold acceptance, Task 4 cohort-pooled emit.
5. Phase 9.1 close → Phase 9.2 stats kickoff drafting starts (using Phase 9.1's per-animal-baseline-normalized arrays as primary input).

---

## 11. References

- Phase 9 stats scoping: `docs/prompts/phase-9-stats-scoping.md` (Phase 9.1 is its descriptive-figures precursor).
- Phase 7c.2 kickoff: spatial proportion_diff + UOT outputs that Phase 9.1 phenotype-pools.
- Phase 7a kinematics outputs: mean_sem, tongue_angle, per_trial endpoints.
- `configs/animals.yaml`: cohort definition + per-animal `stroke_side` + new `phenotype` field.
- Memory: `project_eye_midpoint_convention.md` (relevant if phase plots use eye-centered coordinates).
