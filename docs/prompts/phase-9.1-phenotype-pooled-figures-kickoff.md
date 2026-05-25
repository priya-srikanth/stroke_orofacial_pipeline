# Phase 9.1 Kickoff — Phenotype-Pooled Figures + Pub-Polish on Phase 9 Stats Outputs

**Branch:** `phase/9.1-kickoff-draft` off latest `origin/main` (post-Phase-9-close; current main HEAD `29eb078`, tag `v9-stats-behavioral`).
**Tag on phase-close merge:** `v9.1-phenotype-pooled-figures`.
**Prerequisites:** Phase 9 closed (PR #129 merged 2026-05-25); conda env `stroke_orofacial` active; CC has read `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` (with 2026-05-23 + 2026-05-25 + 2026-05-25 (b) amendments) and Phase 9 kickoff Addenda #7/#8/#10; memory entries `feedback_iterative_addenda_pattern.md` (mid-phase re-spec etiquette) + `feedback_audit_legacy_before_speculating_on_render_params.md` (port legacy verbatim before iterating layout).
**Estimated scope:** 12-16 commits, **~13-17 days CC wall-time** (excluding Priya scientific review). Driven by ~124-127 figure inventory (70 V4/V5 scalar + 48 spatial + 1-4 latency_hist CDFs + 4-7 tongue ipsi-shift trajectories) × figure-style iteration + verification + Q-lock 9 preview-then-full emit pattern. Uplift over the prior 10-14d estimate reflects (a) scaffold-review iteration cost on the new Q-lock 8 two-layer trajectory family and (b) the per-family preview cycle (each emit task adds a small single-tier preview + Priya review gate before full-cohort emit).

**This kickoff supersedes `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md` for execution.** Where the two conflict, this kickoff wins; the scoping doc remains as the historical planning record (with both 2026-05-25 amendments now committed at `3390146`).

---

## Context

Phase 9.1 is the second phase in the consolidation that CONSUMES consolidated outputs rather than producing them (Phase 9 was the first). Phase 9 materialized stats inputs + ran cohort hypothesis tests + emitted per-animal figures (V1/V2/V3 grid per Addendum #8). Phase 9.1 takes that output and produces:

1. The **cross-animal phenotype-pooled figure tier** (V4 per_bin curves + V5 per_epoch boxplots) for every Phase 9 LMM-run scalar endpoint.
2. **Phenotype-pooled spatial recovery curves** for all 48 (3 metrics × 4 scope/trial_group combos × 4 families) spatial endpoints.
3. **Phenotype-pooled `latency_hist` CDF family (1-4 figures)** — separate runner pooling per-trial first-correct-lick latencies across animals within each phenotype tier × epoch. `latency_hist` is confirmatory but uses KS-bridge methodology (Phase 9 Addendum #4), not LMM, so it's outside V4/V5 scope per Q-lock 2 and gets its own figure family per Q-lock 7.
4. **Tongue ipsi-shift figure families (Q-lock 8; 4-7 figures)** — two new families targeting memory finding #6 (direction-sensitive tongue endpoints x/angle show ipsi-contra asymmetry; amplitude endpoints y don't). Family 8.1 = tongue angle at lick1 + lick2 + per-trial median (3 angle endpoint sub-families), ipsi/contra side-split (~3 figures). Family 8.2 = continuous tone-aligned tongue x trajectory, ipsi/contra side-split (1-4 figures). Both use delta-from-baseline normalization (per-bin trajectory subtraction, NOT Addendum #6 per-trial scalar subtraction), two-layer rendering (thin per-session traces + foreground mean ± SEM), and a pre-epoch trace as noise-floor reference.
5. **Preview-then-full emit pattern (Q-lock 9; process meta-lock)** — every figure-emit task in Phase 9.1 (V4, V5, spatial, latency_hist CDF, ipsi-shift) splits into a 3-step preview → review-gate → full triplet. Preview = single phenotype tier (default moderate-severe = PS51 alone, n=1); review-gate = Priya iterates on style; full = all-tiers regenerated with locked style. Polish (Task 6) + composites (Task 7) gate on completion of all Step Nc full emits.
6. **Pub-quality polish:** typography + palette harmonization + multi-panel composites + ipsi/contra labeling per `AnimalInfo.mouse_side_to_ipsi_contra()`.

The 2026-05-25 (b) amendment expanded V4/V5 + spatial scope significantly vs. the original 2026-05-25 locks (which restricted V4/V5 to ~20 confirmatory and spatial to Wasserstein-only). Priya's rationale: visualize how non-confirmatory endpoints behave across phenotype tiers, not just paper-headline figures. The broader inventory is supplementary / data-exploration material; headline subsets feature prominently in Task 7 composites.

**Out of scope:**
- New statistical tests (Phase 9 produced all stats results CSVs at `pipeline_outputs/stats/results/<axis>/<granularity>/<endpoint>.csv`; Phase 9.1 consumes them).
- New endpoint computation (Phase 9.1 consumes Phase 9-materialized parquets).
- Per-animal figures (V1/V2/V3 per Addendum #8 — Phase 9 Task 7 ships those).
- New scientific axes or comparisons.

**Discharges:** None — Phase 9.1 is downstream-only; no forward-pointers from prior phases land here. Phase 9's `recovery_trajectories` forward-pointer was already discharged at Phase 9 Task 6.

---

## Q-locks (locked decisions; not re-litigatable during execution)

Q-locks Q1-Q9 below were locked during 2026-05-25 amendments (original + (b) + (b)-follow-up + (b)-second-follow-up + (b)-third-follow-up) + plan-mode review (Q-A/B/C + 8 review comments). They are NOT re-litigatable during Phase 9.1 execution. Re-spec lands as numbered Addenda per `feedback_iterative_addenda_pattern.md`. Q-A/Q-B/Q-C below are plan-mode inputs (not execution locks) — included here for traceability.

### Q-A — Amendment-commit strategy (plan-mode input)

Bundle. Both 2026-05-25 amendments land as commit 1 on `phase/9.1-kickoff-draft` (commit `3390146`); kickoff lands as commit 2. Commit 1 was preceded by a `git diff` sanity-check verifying the diff is exactly the amendment blocks + §1 deliverables update + §9 OPEN-Q LOCKED edits — no whitespace churn, no truncation.

### Q-B — V4/V5 endpoint scope (plan-mode input → Q-lock 2)

ALL Phase 9 LMM-run scalar endpoints, per disk audit of `pipeline_outputs/stats/results/recovery/per_epoch/`: **35 scalar (non-spatial) endpoints**. The (b) amendment's "~80-100 endpoints" estimate is an overcount; disk-verified count anchors execution.

### Q-C — Wasserstein/UOT/JS dedup (plan-mode input → Q-lock 6)

All 3 spatial distance metrics (Wasserstein-2, UOT cost, JS divergence) route to the phenotype-pooled-spatial runner (Task 3), NOT the V4/V5 runner (Tasks 1-2). V4/V5 is **scalar-only** (consumes `value` column from kinematic + behavioral parquets); the spatial-figure pipeline handles distance metrics from spatial parquets.

### Q-lock 1 — Phenotype grouping = 4-tier

Phase 9.1 retains 4-tier `AnimalInfo.recovery_phenotype` (mild=4 / moderate=1 / moderate-severe=1 / severe=2). Phase 9.x's 3-tier `moderate-pool` (PS46+PS51) is NOT adopted in 9.1; n=1 moderate + moderate-severe tiers render as single-animal descriptive traces with explicit "n=1" annotations.

**Rationale:** 9.1 is figure work where descriptive single-animal traces are publishable; 9.x is stats work where pooled n≥2 is required for LMM convergence. Different scopes → different grouping conventions.

### Q-lock 2 — V4/V5 scope = ALL LMM-run scalar endpoints (35 disk-verified)

V4 (per_bin phenotype-pooled curves) + V5 (per_epoch phenotype-pooled boxplots) emit for all 35 scalar (non-spatial) endpoints in `pipeline_outputs/stats/results/recovery/per_epoch/`. ~70 V4/V5 figures total.

Final canonical endpoint list pinned at Task 0.5 via committed YAML config at `configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml`. Wasserstein/UOT/JS spatial endpoints EXCLUDED per Q-lock 6 dedup.

### Q-lock 3 — Phenotype-pooled spatial scope = 48 figures

All 3 distributional metrics × all 4 scope/trial_group combos × 4 bodypart families. 16 Wasserstein + 16 UOT + 16 JS = 48 phenotype-pooled spatial figures. UOT + JS un-deferred per (b) amendment.

Wasserstein at scope=`tone_aligned/all` (Addendum #3 HEADLINE METRIC) features prominently in Task 7 composites; UOT + JS provide cross-metric corroboration in supplementary inventory.

Final canonical endpoint list pinned at Task 0.5 via `configs/phase_9_1_endpoint_lists/phenotype_pooled_spatial_endpoints.yaml`.

### Q-lock 4 — Ipsi/contra labeling = relabel directly + caption caveat

All per-side figure axes/legends show 'ipsi' and 'contra' directly (via `AnimalInfo.mouse_side_to_ipsi_contra()`). Each figure caption notes: *"All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R."* Single caveat sentence per caption — not crammed into in-axis legend.

### Q-lock 5 — Output path tree

New top-level subtree under `pipeline_outputs/`:

```
pipeline_outputs/phase_9_1_figures/
  phenotype_pooled/
    <endpoint_slug>/
      v4_per_bin_phenotype_pooled.{svg,png}
      v5_per_epoch_phenotype_pooled.{svg,png}
  phenotype_pooled_spatial/
    <family>/<metric>/<combo>.{svg,png}
  composites/
    <composite_name>.{svg,png}
```

### Q-lock 6 — Parameterized figure runner

Both V4/V5 and phenotype-pooled-spatial runners accept `--endpoint-list <path>` CLI flag, defaulting to the committed Phase 9.1 endpoint set. Future exploratory emit (post-9.1 endpoint families, paper-figure narrowing, 9.x reuse) becomes a single-command rerun against a different endpoint-list file.

Q-C dedup RETAINED: V4/V5 is scalar-only; spatial-figure pipeline handles distance metrics. No double-emit of confirmatory Wasserstein endpoints.

### Q-lock 7 — `latency_hist` phenotype-pooled CDF figure family

Per NEW LOCK 2026-05-25 (b) follow-up. `latency_hist` is confirmatory per Phase 9 Addendum #4 (KS-bridge methodology) but is `value_type=vector_per_session` and has NO `recovery/per_epoch/` LMM result CSV — therefore excluded from V4/V5 scope per Q-lock 2. Phase 9.1 emits a separate phenotype-pooled CDF figure family for it.

- **Endpoint:** `latency_hist` — confirmatory per Phase 9 Addendum #4.
- **Source data:** `pipeline_outputs/stats/inputs/latency_hist/<animal>.parquet` (one row per trial; per-trial first-correct-lick latency in `value` column).
- **Pooling:** per-trial latencies pooled across animals **within each phenotype tier × epoch** (4-tier grouping per Q-lock 1; epoch from `epoch_label` column populated by Phase 9 `assign_epoch_label`).
- **Figure type:** phenotype-pooled empirical CDFs. One trace per epoch (`pre` / `acute` / `sub_acute` / `chronic`) within each phenotype panel; x-axis = latency (s or ms TBD at Task 0.5); y-axis = empirical CDF (0..1).
- **Layout (1-4 figures; finalized at Task 0.5 review):**
   - (a) **One figure per phenotype tier × 4 traces = 4 figures** — easier inspection of within-phenotype epoch progression; 4 separate SVG/PNGs at `pipeline_outputs/phase_9_1_figures/phenotype_pooled_latency_hist/<phenotype>.{svg,png}`.
   - (b) **Single 4-panel composite (one panel per phenotype) = 1 figure** — easier cross-phenotype comparison at a glance; one SVG/PNG at `pipeline_outputs/phase_9_1_figures/phenotype_pooled_latency_hist/all_phenotypes_4panel.{svg,png}`.
- **Stats:** no new stats methodology. Existing KS-bridge p-values from `pipeline_outputs/stats/results/pre_post/per_session/latency_hist.csv` (or `pipeline_outputs/stats/results/recovery/<granularity>/latency_hist.csv` if Phase 9 emitted there) feed figure caption annotations. Task 0.5 audits the actual result-CSV location during list-pinning.
- **Runner:** same parameterized `--endpoint-list` flag pattern per Q-lock 6 (separate endpoint-list YAML at `configs/phase_9_1_endpoint_lists/phenotype_pooled_latency_hist_endpoints.yaml`).
- **Figure count:** 1-4 figures (locked at Task 0.5 review). Total Phase 9.1 figure inventory revised: ~118 + 1-4 latency_hist ≈ **~120 figures** (further revised under Q-lock 8 below).

### Q-lock 8 — Tongue ipsi-shift figure families (2 sub-families with delta-from-baseline + two-layer rendering + pre-epoch noise reference)

Per NEW LOCK 2026-05-25 (b) second follow-up. Two new figure families targeting memory finding #6: tongue direction-sensitive endpoints (x, angle) show ipsi-contra asymmetry post-stroke while amplitude endpoints (y) do not. Both families render the same scientific question — "does post-stroke tongue position shift toward the ipsi side?" — at two complementary granularities (per-lick angle scalars vs. continuous per-frame x trajectory).

**Shared spec across both Q-lock 8 families:**

- **X-axis:** tone-aligned trial time (sec post-tone), binned per existing tongue_angle / mean_sem plot convention. Phase 9.1 reuses the existing trajectory-plotting machinery (see "Existing-code reuse" below); no new binning OPEN-Q.
- **4-tier phenotype grouping** per Q-lock 1; n=1 tiers render as single-animal traces.
- **Ipsi/contra side-split** per Q-lock 4 — axes labeled "ipsi" / "contra" directly + figure-caption cohort-uniformity caveat ("All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R").
- **Layout:** side-by-side ipsi panel + contra panel per phenotype tier, with multi-epoch traces (pre / acute / sub_acute / chronic) overlaid in each panel.

**Baseline normalization (LOCKED — delta-from-baseline at every tone-aligned time bin):**

Y-axis values are **delta** (post − pre-stroke baseline), NOT raw tongue angle / x. This is per-bin trajectory subtraction (distinct from Addendum #6's per-trial scalar subtraction at the LMM-input layer).

- **Per-animal baseline trajectory:** computed from PRE-stroke sessions only, separately for each trial side:
  - `ipsi_baseline_trajectory(t)` = mean over pre-stroke mouse-L trials per animal.
  - `contra_baseline_trajectory(t)` = mean over pre-stroke mouse-R trials per animal.
  - (All 8 cohort animals are L-stroke under the current cohort regime, so mouse-L = ipsi, mouse-R = contra. Caption caveat covers cohort-uniformity.)
- **Per-session delta trajectory:** for any session (pre or post-stroke) in any animal, compute `session_mean_trajectory(t)` across trials of the given side, then subtract that animal's pre-stroke side-matched baseline trajectory(t) at each tone-aligned time bin. Result is per-session delta(t) trajectory.
- **Pooling:** delta(t) trajectories from all sessions within (phenotype, epoch, side) pool to produce the cohort-level mean ± SEM delta trace for that cell.
- **Pre-epoch sanity:** per-session pre-epoch deltas should hover ≈0 by construction (a session's own contribution to its baseline is non-zero only via leave-one-session-out semantics, which is NOT applied here — pre sessions subtract from the same animal's full pre-stroke pool; modest residual variance is expected and is the noise-floor reference, see next bullet).

**Pre-epoch trace REQUIRED as noise-floor reference (LOCKED):**

Pre-stroke is plotted as a full epoch trace alongside acute / sub_acute / chronic — NOT omitted or implicitly assumed zero. The thin per-session overlay (two-layer rendering, see below) for the pre epoch reveals the natural session-to-session variability band around zero. Post-stroke epoch traces that stay within the pre band are consistent with noise; traces that exceed the pre band are evidence of a real stroke-induced shift. **Reading the magnitude of post-stroke deltas against the pre band is the primary visual comparison the figures support.**

- y-axis label: `"delta tongue angle (deg, baseline-subtracted)"` (Family 8.1) or `"delta tongue x (px, baseline-subtracted)"` (Family 8.2).
- y=0 reference line drawn explicitly in each panel.

**Two-layer rendering (LOCKED, applies to both families):**

Each epoch trace within a panel is a two-layer overlay:

- **Background layer:** thin alpha-transparent per-session delta trajectories (suggest α≈0.2-0.3), one line per (animal, session) contributing to that epoch's pool, rendered in the same color as the foreground epoch trace. Allows visual inspection of session-to-session consistency; reveals whether the pooled mean is driven by all sessions or by outliers.
- **Foreground layer:** prominent mean ± SEM delta trace for the epoch (solid line at higher alpha + SEM band), rendered on top of the per-session traces in the same color.
- **Per-session trace definition:** for Family 8.1 (per-lick angle), a session trace is that session's tone-aligned time-binned mean angle trajectory across all licks in the session. For Family 8.2 (continuous x trajectory), a session trace is that session's mean x(t) trajectory across trials.
- **Caveat:** session-trace overlay is for visualization only; underlying stats remain at LMM-on-session-level granularity per Phase 9 Addendum #6.

**Family 8.1 — Delta tongue angle at lick1 + lick2 + per-trial median, ipsi/contra side-split:**

- **Y-axis:** baseline-subtracted tongue angle (deg).
- **3 endpoint sub-families:**
  1. `tongue_lick1_angle_at_ypeak` — first-lick peak angle.
  2. `tongue_lick2_angle_at_ypeak` — second-lick peak angle.
  3. `tongue_median_angle_at_peak_velocity` — per-trial median across licks.
- **Source data:** `pipeline_outputs/stats/inputs/<endpoint>/<animal>.parquet` for the per-trial scalar values + corresponding per-lick peak-time data (e.g., `tongue_lick_t_peaks_bylick` vector) so each (peak_t_ms, angle) point can be placed at its tone-aligned bin. Per-trial peak-time + angle paired per detected lick.
- **Figure count:** 3 figures (3 endpoint sub-families × 4 phenotype × 2 side panels = 24 panels packed as 3 figures, one per endpoint).
- **Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/angle/<endpoint_slug>.{svg,png}`.

**Family 8.2 — Delta tone-aligned tongue x trajectory (per-frame continuous), ipsi/contra side-split:**

- **Y-axis:** baseline-subtracted raw tongue x position (px) at every tone-aligned time bin (continuous per-frame DLC trajectory; NOT `x_at_ypeak` / NOT `x_at_peak_velocity` per Priya 2026-05-25 clarification).
- **Source data:** canonical continuous DLC tongue x time-series at `pipeline_outputs/dlc_analysis/interpolated_traces/tongue/<animal>/<YYYYMMDD>.parquet` (Phase 7a.2 interpolated_traces output; `x_final` column + `fps` + `n_frames`). Same loader already consumed by `dlc_kinematics.tongue_pertrial`, `dlc_kinematics.tongue_jaw_mismatch`, and `dlc_kinematics.mean_sem_visual`. Tone-alignment per existing tongue_angle_cohort convention.
- **Figure count:** 1-4 figures (4 phenotype × 2 side panels = 8 panels packed in one composite, OR one figure per phenotype). Layout locked at Task 0.5.
- **Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/x_trajectory/{all_phenotypes_4panel|<phenotype>}.{svg,png}`.
- **Scientific framing:** most direct visual test of the ipsi-shift hypothesis. If tongue preferentially shifts toward the ipsi side post-stroke, contra-trial panels show a sustained ipsi-ward x offset post-tone (animal "trying" to lick contra but the deficit pulls position ipsi). Likely paper-narrative figure for memory finding #6.

**Existing-code reuse (LOCKED — Phase 9.1 does NOT add new mean_sem code):**

- **Trajectory loader / aligner:** `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py::build_mean_sem_cohort(bodypart, animal, ...)` already produces tone-aligned mean ± SEM trajectories from `interpolated_traces/<bodypart>/<animal>/<date>.parquet` rows. Family 8.2 wraps this with phenotype-pool + ipsi/contra split + delta-from-baseline subtraction; does NOT re-implement.
- **Per-session + binned overlay rendering:** `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py::_plot_tone_aligned_session_overlays` and `_plot_tone_aligned_binned_overlays` already implement the two-layer thin-session-traces + foreground-mean-SEM rendering style. Phase 9.1 reuses these primitives; does NOT re-author them.
- **Time-binning convention:** inherited from `tongue_angle_cohort` (post-tone window + bin width currently in `configs/defaults.yaml` `dlc_kinematics.mean_sem_visual.*`). No new binning OPEN-Q.

**Open extension (NOT a Q-lock; OPEN-Q 3, defers to Task 1b / Task 2b scaffold review):**

The same two-layer rendering style may be desirable retroactively for V4 (per_bin phenotype-pooled recovery curves) and/or V5 (per_epoch boxplots). For V4, "session trace" → per-animal trajectory; for V5, individual session-points already render via boxplot whiskers/scatter. Defer the V4/V5 extension question to Task 1b / Task 2b scaffold review; Priya can request retroactive application if the Q-lock 8 style reads cleanly during Task 5b.

**Total figure count revised:** ~120 + 3 family-8.1 + 1-4 family-8.2 ≈ **~124-127 figures**.

### Q-lock 9 — Preview-then-full emit pattern (process meta-lock)

Per NEW LOCK 2026-05-25 (b) third follow-up. Every figure-emit task (V4, V5, phenotype-pooled spatial, latency_hist CDF, Q-lock 8 ipsi-shift) splits into a 3-step preview → review-gate → full triplet. The pattern protects against per-family style drift and ~124-figure-scale retroactive restyling.

**Step 1 — Preview emit (single phenotype tier):**
- Generate the full figure family for ONE phenotype tier only.
- **Default preview tier: moderate-severe (PS51, n=1)** — reveals the n=1 single-animal-trace caveat annotation behavior AND has enough sessions per epoch to stress-test the two-layer per-session overlay rendering (Q-lock 8 family).
- **Preview tier override:** CC may propose a different tier at task-start when moderate-severe is a poor stress-test for the family. Examples:
  - **mild (n=4)** — cross-session stress test for palette / line-density decisions (4 animals × multiple sessions per epoch).
  - **severe (n=2)** — pooled-but-small-n stress test for SEM-band rendering on minimum-n pooled phenotype.
- Override proposal lands in the task's first commit; default = moderate-severe unless flagged.
- Wall-time: ~10-20% of full-cohort wall-time per family.

**Step 2 — Priya scaffold review gate:**
- Priya iterates on plotting style: colors, alpha, line thickness, axis labels, panel arrangement, legend placement, caption framing, ipsi/contra label visibility.
- Style changes propagate to ALL figure families before Step 3 — no per-family style drift.
- Style locked at gate close; further changes during Step 3 require an Addendum.

**Step 3 — Full cohort emit:**
- Regenerate the figure family across all phenotype tiers / endpoints with the locked Step 2 style.
- No retroactive restyling of ~124+ figures (the whole point of the preview gate).
- Wall-time scales linearly with figure count per family.

**Polish-task gating:** Task 6 (typography + palette + ipsi/contra labels) and Task 7 (composites) only run AFTER all figure-family Step Nc full emits complete. The preview cycle locks per-family rendering BEFORE cross-family harmonization. Task 6 still owns the cross-family polish pass (e.g., final palette + journal typography sweep across the entire ~124-figure tree) but does NOT re-litigate any decision locked in a Step Nb gate.

**Task-table impact:** every figure task in §Tasks below splits into `Task <N>a` (preview) + `Task <N>b` (Priya review-gate) + `Task <N>c` (full emit). Review-gate wall-time is Priya-bandwidth-bound (not counted in CC wall-time estimates).

---

## Phenotype-grouping conventions

Per `configs/animals.yaml` `recovery_phenotype` field stamped during Phase 9 Task 1.5:

| Phenotype | Animals | n | epoch_boundaries (acute_max / subacute_max / chronic_min) |
|---|---|---|---|
| Mild | PS47, PS48, PS49, PS50 | 4 | 1 / 4 / 5 (uniform across cohort) |
| Moderate | PS46 | 1 | 5 / 8 / 9 |
| Moderate-severe | PS51 | 1 | 6 / 30 / 31 |
| Severe | PS54, PS55 | 2 | PS54: 17 / 39 / 40; PS55: 17 / 49 / 50 |

**Critical caveats:**

1. **n=1 tiers** (moderate, moderate-severe) render as single-animal traces with explicit "n=1 single-animal trace" annotation — no SEM band, no cross-animal averaging. Mild (n=4) and severe (n=2) carry meaningful pooled statistics. Every Phase 9.1 figure must show n labels per phenotype tier prominently.
2. **PS54 vs PS55 epoch boundary divergence** — both severe but PS55 sub_acute + chronic shifted +10 days (PS55 received higher laser power 5.0 mW vs PS54 3.0 mW). Phenotype-pooled epoch comparisons respect per-animal boundaries via the `epoch_label` column in stats input parquets (populated by Phase 9's `assign_epoch_label(rel_day, animal_info)` at materialize time).
3. **Per-animal marker style** within each phenotype color helps distinguish within-tier animals (especially severe's n=2: PS54 vs PS55 trajectories).

---

## Inputs catalog — what Phase 9.1 consumes from Phase 9

### Stats input parquets (Phase 9 Task 2)

- **Scalar endpoints (V4/V5 source):** `pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet` for 35 scalar (non-spatial) endpoints × 8 cohort animals = ~280 parquets.
- **Spatial endpoints (Task 3 source):** `pipeline_outputs/stats/inputs/spatial_<metric>_<family>_<combo>/<animal>.parquet` for 48 spatial endpoints × 8 animals = ~384 parquets.
- **Schema:** 11 standard columns + (spatial) 4 spatial-specific columns (granularity, rel_day_anchor, n_sessions_aggregated, n_frames_aggregated). `epoch_label` column populated per Phase 9 Addendum #6 (per-animal boundaries).

### Stats results CSVs (Phase 9 Task 4-5)

- `pipeline_outputs/stats/results/<axis>/per_<granularity>/<endpoint>.csv` — per-(axis, granularity, endpoint) FitResult rows.
- Axes: `pre_post`, `recovery`, `ipsi_contra`, `trial_group`.
- Granularities: `per_session`, `per_bin`, `per_epoch`.
- `_all.csv` master per axis aggregates across granularities.
- Total: 465 CSVs (per MIGRATION_LOG Phase 9 entry).

### Routing — Q-lock 6 dedup made explicit

**V4/V5 runner (Tasks 1-2) consumes:** scalar endpoint stats results CSVs only.

**Spatial-figure runner (Task 3) consumes:** the 48 `spatial_<metric>_<family>_<combo>` endpoint stats results CSVs.

**Critical:** confirmatory `spatial_wasserstein_*_tone_aligned_all` stats results CSVs (4 endpoints; Bonferroni-pass per Phase 9 Addendum #10 headline summary) are consumed by Task 3 only. They are NOT consumed by Tasks 1-2 per Q-lock 6 dedup. Same applies to UOT + JS spatial endpoints — all distance metrics route through the spatial pipeline. A downstream CC session adding new endpoints to either runner must respect this dedup.

### Helpers (Phase 9 Task 3b + Phase 8a.10)

```python
from stroke_orofacial.stats.recovery_epochs import (
    cohort_phenotype_summary,           # → {phenotype: [animal_ids]}
    assign_epoch_label,                  # per-row epoch from rel_day + AnimalInfo
    assign_epoch_labels_to_inputs_df,   # batch helper
)
from stroke_orofacial.animals import load_animals
animals = load_animals()
animals["PS46"].recovery_phenotype       # → "moderate"
animals["PS46"].epoch_boundaries          # → EpochBoundaries(5, 8, 9)
animals["PS46"].mouse_side_to_ipsi_contra("L")  # → "ipsi" (L-stroke cohort)
```

---

## Binning + epoch conventions

**Per_bin granularity** uses per-animal `AnimalInfo.bin_days`:
- PS46-50: `bin_days = 2`
- PS51-55: `bin_days = 7`

Each per_bin row in stats results = one (animal, bin_midpoint_rel_day) data point. Phenotype-pool across mixed-cadence animals is automatic via the `bin_midpoint_rel_day` x-axis.

**Per_epoch granularity** uses per-animal `AnimalInfo.epoch_boundaries` (4 distinct schemas across cohort per the phenotype table). Pool within epoch_label; each animal contributes one data point per (epoch_label, phenotype-pool) cell.

**Phenotype-pool composition by tier:**
- **Mild (n=4):** PS47, PS48, PS49, PS50 — all `bin_days=2`, identical epoch boundaries (1/4/5). Cleanest pool.
- **Moderate (n=1):** PS46 — single-animal trace.
- **Moderate-severe (n=1):** PS51 — single-animal trace.
- **Severe (n=2):** PS54, PS55 — both `bin_days=7` but different chronic_min (40 vs 50). Per_bin aligns on bin_midpoint; per_epoch aligns on epoch_label.

---

## V4/V5 endpoint inventory (Q-lock 2)

35 disk-verified scalar LMM-run endpoints, enumerated from `pipeline_outputs/stats/results/recovery/per_epoch/`. Final canonical list pinned at Task 0.5 as `configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml`.

### Tongue per-trial kinematics (23)

| # | endpoint_slug | family | Phase 9 confirmatory? | Phase 9 Addendum #8 headline? |
|---|---|---|---|---|
| 1 | tongue_first_peak_t_ms | tongue per-trial | ✓ | — |
| 2 | tongue_lick1_angle_at_ypeak | tongue per-trial | ✓ | — |
| 3 | tongue_lick1_t_peak_ms | tongue per-trial | ✓ | ✓ #2 |
| 4 | tongue_lick1_vxy_peak | tongue per-trial | — | ✓ #5 |
| 5 | tongue_lick1_vy_peak | tongue per-trial | — | — |
| 6 | tongue_lick1_x_at_ypeak | tongue per-trial | ✓ | ✓ #3 |
| 7 | tongue_lick1_y_peak | tongue per-trial | ✓ | ✓ #1 |
| 8 | tongue_lick2_angle_at_ypeak | tongue per-trial | ✓ | — |
| 9 | tongue_lick2_t_peak_ms | tongue per-trial | — | — |
| 10 | tongue_lick2_x_at_ypeak | tongue per-trial | ✓ | ✓ #4 |
| 11 | tongue_lick2_y_peak | tongue per-trial | — | — |
| 12 | tongue_lick_rate_hz | tongue per-trial | — | — |
| 13 | tongue_max_vxy_peak_first5 | tongue per-trial (derived) | — | ✓ #6 |
| 14 | tongue_max_vy_peak_first5 | tongue per-trial (derived) | — | — |
| 15 | tongue_mean_vxy_peak_first5 | tongue per-trial (derived) | — | ✓ #7 |
| 16 | tongue_mean_within_bout_ili_ms | tongue per-trial | — | — |
| 17 | tongue_median_angle_at_peak_velocity | tongue per-trial | — | — |
| 18 | tongue_median_angle_max_signed_per_lick | tongue per-trial | — | — |
| 19 | tongue_median_vxy_peak_per_trial | tongue per-trial (derived) | ✓ | — |
| 20 | tongue_median_vy_peak_per_trial | tongue per-trial (derived) | — | — |
| 21 | tongue_n_left | tongue per-trial | — | — |
| 22 | tongue_n_licks | tongue per-trial | — | — |
| 23 | tongue_n_right | tongue per-trial | — | — |

### Jaw per-trial kinematics (3)

| # | endpoint_slug | family |
|---|---|---|
| 24 | jaw_n_frames_over_thresh | jaw per-trial |
| 25 | jaw_peak_pos_deflection | jaw per-trial |
| 26 | jaw_peak_selected_deflection | jaw per-trial |

### Tongue-jaw mismatch (1)

| # | endpoint_slug | family |
|---|---|---|
| 27 | mismatch_candidate_no_lick_with_jaw_move | tongue-jaw mismatch |

### Session-aggregate behavioral (8)

| # | endpoint_slug | category | Phase 9 confirmatory? |
|---|---|---|---|
| 28 | first_lick_accuracy_all | Category A session-aggregate | ✓ |
| 29 | late_lickiness | Category A session-aggregate | — |
| 30 | latency_to_first_correct_lick_s | Category A session-aggregate | — |
| 31 | lickRate_byTrial | Category A session-aggregate | — |
| 32 | lick_switch_rate | Category A session-aggregate | — |
| 33 | num_all_licks_per_trial | Category A session-aggregate | — |
| 34 | num_correct_licks_per_trial | Category A session-aggregate | ✓ |
| 35 | num_incorrect_licks_per_trial | Category A session-aggregate | ✓ |

**Total: 35 V4/V5 endpoints × (V4 + V5) = 70 figures.**

### Q-lock 6 + Q-lock 7 + Q-lock 8 dedup callouts (V4/V5 inventory)

**Spatial distance metrics (Q-lock 6):** The confirmatory Wasserstein endpoints (`spatial_wasserstein_{jaw_eye_midpoint, nose_eye_midpoint, tongue_spout_midpoint, whiskers_eye_midpoint}_tone_aligned_all`) are **NOT in this V4/V5 inventory**. They appear only in §"Phenotype-pooled spatial inventory" below, and their figures emit only to `pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/<family>/wasserstein/tone_aligned_all.{svg,png}`. Same applies to all UOT + JS spatial endpoints.

**`latency_hist` (Q-lock 7):** `latency_hist` is confirmatory per Phase 9 Addendum #4 but is **NOT in this V4/V5 inventory** — it's a `vector_per_session` KS-bridge endpoint with no `recovery/per_epoch/` LMM result CSV. It gets its own phenotype-pooled CDF family per Q-lock 7 (Task 4 emit; `pipeline_outputs/phase_9_1_figures/phenotype_pooled_latency_hist/...`).

**Tongue angle endpoints — dual treatment (Q-lock 8):** The 3 tongue angle endpoints — `tongue_lick1_angle_at_ypeak` (row 2), `tongue_lick2_angle_at_ypeak` (row 8), `tongue_median_angle_at_peak_velocity` (row 17) — DO appear in this V4/V5 inventory (scalar V4 per_bin curve + V5 per_epoch boxplot) AND ALSO appear in Q-lock 8 Family 8.1 as ipsi-shift trajectory figures over tone-aligned time. **This is not a dedup violation** — V4/V5 plots the per-trial scalar value vs. rel_day; Q-lock 8 Family 8.1 plots the per-trial scalar value vs. tone-aligned trial time, side-split, baseline-subtracted. Different axes, different scientific framings; same underlying parquet data. Figure runner must emit both without double-skipping the angle endpoints in either pipeline.

### Phase 9 headline overlap (per Addendum #8)

4 of the 7 Phase 9 Addendum #8 headlines are confirmatory and in V4/V5 (rows 3, 6, 7, 10); 3 are headlines but non-confirmatory new vxy endpoints (rows 4, 13, 15). All 7 get V4/V5 treatment in Phase 9.1. Headlines feature in Task 7 composites alongside the 4 confirmatory Wasserstein endpoints from the spatial family.

---

## Phenotype-pooled spatial endpoint inventory (Q-lock 3)

48 phenotype-pooled spatial figures = 3 metrics × 4 scope/trial_group combos × 4 bodypart families. Final canonical list pinned at Task 0.5 as `configs/phase_9_1_endpoint_lists/phenotype_pooled_spatial_endpoints.yaml`.

**Metrics (3):**
- `wasserstein` — Wasserstein-2 distance. HEADLINE per Phase 9 Addendum #3.
- `uot_cost` — Unbalanced Optimal Transport cost.
- `js_divergence` — Jensen-Shannon divergence.

**Scope/trial_group combos (4):**
- `tone_aligned_all` — overall tone-anticipation distribution (HEADLINE per Addendum #3).
- `tone_aligned_L` — L-tone anticipation.
- `tone_aligned_R` — R-tone anticipation.
- `whole_session` — background session distribution (no trial_group).

**Bodypart families (4):**
- `jaw_eye_midpoint`
- `nose_eye_midpoint`
- `tongue_spout_midpoint`
- `whiskers_eye_midpoint`

### Headline emphasis (Wasserstein × tone_aligned_all, 4 figures)

| family | endpoint_slug | Phase 9 q_holm (per_bin slope) |
|---|---|---|
| jaw_eye_midpoint | spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all | 9e-15 (Bonferroni-pass) |
| nose_eye_midpoint | spatial_wasserstein_nose_eye_midpoint_tone_aligned_all | 3e-7 (Bonferroni-pass) |
| tongue_spout_midpoint | spatial_wasserstein_tongue_spout_midpoint_tone_aligned_all | 0.058 (borderline, FDR-only) |
| whiskers_eye_midpoint | spatial_wasserstein_whiskers_eye_midpoint_tone_aligned_all | 0.006 (FDR-pass, Bonferroni-fail) |

These 4 figures get featured placement in Task 7 composites alongside the V4/V5 headlines. The other 44 spatial figures (UOT + JS + cross-scope Wasserstein variants) provide cross-metric corroboration / supplementary inventory.

### Output path layout (Q-lock 5)

```
pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/
  jaw_eye_midpoint/
    wasserstein/{tone_aligned_all,tone_aligned_L,tone_aligned_R,whole_session}.{svg,png}
    uot_cost/{tone_aligned_all,...}.{svg,png}
    js_divergence/{tone_aligned_all,...}.{svg,png}
  nose_eye_midpoint/
    ... (same structure)
  tongue_spout_midpoint/
    ...
  whiskers_eye_midpoint/
    ...
```

---

## Tongue ipsi-shift inventory (Q-lock 8)

Two families × 4-7 figures total. Final canonical lists pinned at Task 0.5 as `configs/phase_9_1_endpoint_lists/{phenotype_pooled_ipsi_shift_angle,phenotype_pooled_ipsi_shift_x_trajectory}_endpoints.yaml`.

### Family 8.1 — Delta tongue angle (3 endpoint sub-families)

| # | endpoint_slug | scalar source (V4/V5 also consumes) | per-lick timing source |
|---|---|---|---|
| 1 | `tongue_lick1_angle_at_ypeak` | `pipeline_outputs/stats/inputs/tongue_lick1_angle_at_ypeak/<animal>.parquet` | `tongue_lick_t_peaks_bylick[0]` per trial |
| 2 | `tongue_lick2_angle_at_ypeak` | `pipeline_outputs/stats/inputs/tongue_lick2_angle_at_ypeak/<animal>.parquet` | `tongue_lick_t_peaks_bylick[1]` per trial |
| 3 | `tongue_median_angle_at_peak_velocity` | `pipeline_outputs/stats/inputs/tongue_median_angle_at_peak_velocity/<animal>.parquet` | per-trial median peak time (median across licks) |

Each endpoint emit = 1 figure × 4 phenotype × 2 sides (ipsi/contra) = 8 panels per figure × 3 figures = 24 panels.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/angle/<endpoint_slug>.{svg,png}` (3 figures).

### Family 8.2 — Delta tongue x trajectory (continuous per-frame)

| Endpoint | Data source | Loader to reuse |
|---|---|---|
| Continuous tone-aligned tongue x trajectory | `pipeline_outputs/dlc_analysis/interpolated_traces/tongue/<animal>/<YYYYMMDD>.parquet` (Phase 7a.2 interpolated_traces; `x_final` + `fps` + `n_frames`) | `dlc_kinematics.mean_sem_visual.build_mean_sem_cohort` (already produces tone-aligned mean ± SEM per (bodypart, animal); Phase 9.1 wraps with phenotype-pool + ipsi/contra split + baseline subtraction) |

**Output (Layout TBD at Task 0.5):**
- Composite layout: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/x_trajectory/all_phenotypes_4panel.{svg,png}` (1 figure × 8 panels).
- Per-phenotype layout: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/x_trajectory/<phenotype>.{svg,png}` (4 figures × 2 panels each).

### Reused existing-code primitives

| Need | Existing module / function |
|---|---|
| Per-bodypart tone-aligned mean ± SEM cohort | `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py::build_mean_sem_cohort` |
| Per-session thin-overlay rendering | `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py::_plot_tone_aligned_session_overlays` |
| Binned mean ± SEM foreground rendering | `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py::_plot_tone_aligned_binned_overlays` |
| Time-binning convention (post-tone window + bin width) | `configs/defaults.yaml::dlc_kinematics.mean_sem_visual.*` |
| Per-trial peak-time vector (Family 8.1) | `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (existing `tongue_lick_t_peaks_bylick` primitive) |
| L/R → ipsi/contra translation | `AnimalInfo.mouse_side_to_ipsi_contra()` (Phase 8a.10) |

---

## Pooling approach (LOCKED per Phase 9 Addendum #6)

**Per-animal baseline normalization** happens at Phase 9 Task 4 stats-runner time, not Phase 9.1:
- Baseline = mean of pre-stroke (rel_day ≤ 0) `value` rows per animal.
- Normalized value = raw value − per_animal_baseline_mean (additive normalization per Addendum #6, relocated to plot-time per Addendum #9).
- Phase 9.1 figures consume the already-normalized values via the stats results CSVs.

**Phase 9.1 figures:**
- **V4 (per_bin phenotype-pooled):** consume per_bin stats results CSV → multiple traces per panel (one per phenotype tier) showing `bin_midpoint_rel_day` vs cohort mean ± SEM within phenotype.
- **V5 (per_epoch phenotype-pooled):** consume per_epoch stats results CSV → boxplots grouped by (phenotype × epoch).

**Multiple per-session points per animal** in pooled figures (NOT "per-animal mean then pool"). Each animal's sessions are individual data points in the underlying parquet; phenotype-pool aggregation uses per-session equal-weight by default.

**Visualization style** (placeholder palette; finalize at Task 6 per OPEN-Q 1):
- Per-phenotype color coding: mild = blue / moderate = green / moderate-severe = orange / severe = red (placeholder).
- n labels prominent per tier; n=1 tiers get explicit "single-animal trace" annotation.
- Per-animal marker style within each phenotype color.

---

## Module organization (per Comment 4)

New top-level `figures/` subtree under `src/stroke_orofacial/`:

```
src/stroke_orofacial/figures/
  __init__.py
  phenotype_pooled.py                  # V4/V5 emit functions (Task 1-2)
  phenotype_pooled_spatial.py          # 48-figure spatial emit (Task 3)
  phenotype_pooled_latency_hist.py     # Q-lock 7 CDF family (Task 4)
  phenotype_pooled_ipsi_shift.py       # Q-lock 8 angle + x trajectory families (Task 5)
  pub_polish.py                         # typography + palette + ipsi/contra style module (Task 6)
  composites.py                         # multi-panel composite assembly (Task 7)
```

Driver scripts under `scripts/phase_9_1_figures/` (parallels Phase 9's `scripts/phase_9_stats/`):

```
scripts/phase_9_1_figures/
  __init__.py
  build_v4_v5_phenotype_pooled.py        # CLI driver for Tasks 1-2; --endpoint-list flag
  build_phenotype_pooled_spatial.py       # CLI driver for Task 3; --endpoint-list flag
  build_phenotype_pooled_latency_hist.py   # CLI driver for Task 4; --endpoint-list + --layout flags
  build_phenotype_pooled_ipsi_shift.py     # CLI driver for Task 5; --endpoint-list + --layout flags
  build_composites.py                      # CLI driver for Task 7
```

Tests under `tests/`:
```
tests/test_figures_phenotype_pooled.py
tests/test_figures_phenotype_pooled_spatial.py
tests/test_figures_phenotype_pooled_latency_hist.py
tests/test_figures_phenotype_pooled_ipsi_shift.py
tests/test_figures_pub_polish.py
tests/test_figures_composites.py
```

Endpoint-list config files:
```
configs/phase_9_1_endpoint_lists/
  v4_v5_scalar_endpoints.yaml                              # 35 endpoints (Q-lock 2; Task 0.5)
  phenotype_pooled_spatial_endpoints.yaml                   # 48 endpoints (Q-lock 3; Task 0.5)
  phenotype_pooled_latency_hist_endpoints.yaml              # 1 endpoint (Q-lock 7; Task 0.5)
  phenotype_pooled_ipsi_shift_angle_endpoints.yaml          # 3 endpoints (Q-lock 8 Family 8.1; Task 0.5)
  phenotype_pooled_ipsi_shift_x_trajectory_endpoints.yaml   # 1 endpoint (Q-lock 8 Family 8.2; Task 0.5)
```

---

## Tasks

### Task 0 — Setup + branch verification

Per Comment 6, immediately before branching, verify the base SHA:

```bash
git fetch origin
git checkout main
git pull origin main
git rev-parse main                        # expect 29eb078 (Phase 9 close merge)
git checkout -b phase/9.1-kickoff-draft   # OR phase/9.1-figures if main has advanced
conda activate stroke_orofacial
which python                              # must print a path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"       # must succeed
pytest --collect-only                     # must complete without import errors
```

If `git rev-parse main` does NOT match `29eb078`, branch off the new tip regardless (the goal is "post-Phase-9-close main"). Surface the divergence in Task 0 commit message.

**Companion notes file** (per Comment 8): seed `.scratch_phase_9_1/notes_running.md` paralleling Phase 9's `.scratch_phase_9/notes_running.md`. CC writes free-form audit-trail entries here throughout the phase. Distinct from `.scratch_phase_9_1/verdict.md` (Priya's gate output at Task 8).

### Task 0.5 — Pin endpoint lists (STOP-and-report)

Disk audit + commit canonical endpoint lists:

```bash
ls pipeline_outputs/stats/results/recovery/per_epoch/ | \
  grep -v "^spatial_" | grep -v "^_all\.csv$" | \
  sed 's/\.csv$//' | sort > /tmp/v4_v5_audit.txt
# Expect 35 endpoints per disk audit at kickoff drafting.

ls pipeline_outputs/stats/inputs/ | grep "^spatial_" | \
  awk '{print}' | sort > /tmp/spatial_audit.txt
# Expect 48 (16 W + 16 UOT + 16 JS) plus 2 orphan bare slugs to exclude.
```

CC writes both YAML configs:
- `configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml` — 35 endpoints with category metadata.
- `configs/phase_9_1_endpoint_lists/phenotype_pooled_spatial_endpoints.yaml` — 48 endpoints structured by (metric × scope × family).

**STOP-and-report.** Post both YAMLs to Priya for sign-off. If disk audit count diverges from kickoff body's 35/48 expectations, surface immediately. Task 1 onward proceeds against the stamped YAML lists.

Excludes the 2 orphan bare slugs (`spatial_wasserstein_jaw_eye_midpoint`, `spatial_wasserstein_tongue_spout_midpoint`) — pre-Addendum-7 rename artifacts; canonical slugs are scope+trial_group suffixed.

> **Q-lock 9 task structure (applies to Tasks 1, 2, 3, 4, 5):** Each figure-emit task below is a 3-step triplet — `Na` preview (single phenotype tier; default moderate-severe) → `Nb` Priya scaffold review gate → `Nc` full cohort emit. Style changes locked at any `Nb` propagate to all other families before their `Nc`. Tasks 6 (polish) + 7 (composites) gate on completion of all `Nc` full emits.

### Task 1 — V4 phenotype-pooled per_bin curves (~35 figures total at Step 1c)

Implement `src/stroke_orofacial/figures/phenotype_pooled.py::emit_v4_per_endpoint(endpoint_slug, resolver, phenotype_filter=None, ...)`.

**Per-endpoint plot:** one panel; multiple traces (one per phenotype tier from `cohort_phenotype_summary(animals)`); x-axis = `bin_midpoint_rel_day` (per-animal `bin_days` resolved at trace assembly); y-axis = cohort mean ± SEM within phenotype.

**Driver:** `scripts/phase_9_1_figures/build_v4_v5_phenotype_pooled.py --variant v4 --endpoint-list configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml [--phenotype-filter <tier>]`.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/v4_per_bin_phenotype_pooled.{svg,png}`.

**Tests:** `tests/test_figures_phenotype_pooled.py` — fixture-based; uses `PathResolver(output_root=tmp_path)` per CLAUDE.md Repo Convention §7.

**Per Comment 2 dedup:** the V4 runner explicitly skips any endpoint_slug starting with `spatial_` if Priya accidentally adds one to the V4/V5 endpoint list. Log + skip; do not double-emit.

#### Task 1a — V4 preview (single phenotype tier)
- Per Q-lock 9, preview tier default = moderate-severe (PS51, n=1). CC may propose mild (n=4) or severe (n=2) override at task-start with rationale.
- Emit V4 figures for all ~35 scalar endpoints × 1 preview tier.
- Wall time: **~0.3 day**.

#### Task 1b — V4 scaffold review gate (Priya)
- Priya iterates on V4 style (colors, alpha, line thickness, axis labels, panel layout, n-label visibility).
- Style decisions propagate to V5 (Task 2c) + spatial (Task 3c) + latency_hist (Task 4c) + ipsi-shift (Task 5c) before their full emits.
- Wall time: Priya bandwidth (not counted in CC budget).

#### Task 1c — V4 full cohort emit
- Regenerate V4 across all 4 phenotype tiers with locked Step 1b style.
- Wall time: **~1.5 days**.

### Task 2 — V5 phenotype-pooled per_epoch boxplots (~35 figures total at Step 2c)

Same endpoints as Task 1; different plot style. `emit_v5_per_endpoint(endpoint_slug, ..., phenotype_filter=None)`.

**Per-endpoint plot:** one panel; boxplots grouped by (phenotype × epoch). Phenotype on x-axis; boxplot per epoch within each phenotype group.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/v5_per_epoch_phenotype_pooled.{svg,png}`.

#### Task 2a — V5 preview
- Same preview tier as Task 1a (default moderate-severe; respects any Task 1a override).
- Wall time: **~0.3 day**.

#### Task 2b — V5 scaffold review gate (Priya)
- Wall time: Priya bandwidth.

#### Task 2c — V5 full cohort emit
- Wall time: **~0.7 day**.

### Task 3 — Phenotype-pooled spatial recovery curves (48 figures total at Step 3c)

Implement `src/stroke_orofacial/figures/phenotype_pooled_spatial.py::emit_spatial_per_combo(family, metric, combo, resolver, phenotype_filter=None, ...)`.

**Per-figure plot:** one panel; multiple traces (one per phenotype tier); x-axis = `bin_midpoint_rel_day`; y-axis = phenotype-pooled metric value.

**Driver:** `scripts/phase_9_1_figures/build_phenotype_pooled_spatial.py --endpoint-list configs/phase_9_1_endpoint_lists/phenotype_pooled_spatial_endpoints.yaml [--phenotype-filter <tier>]`.

**Output:** `pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/<family>/<metric>/<combo>.{svg,png}`.

#### Task 3a — Spatial preview
- Wall time: **~0.2 day**.

#### Task 3b — Spatial scaffold review gate (Priya)
- Wall time: Priya bandwidth.

#### Task 3c — Spatial full cohort emit
- Wall time: **~1 day**.

### Task 4 — `latency_hist` phenotype-pooled CDF family (1-4 figures total at Step 4c, per Q-lock 7)

Implement `src/stroke_orofacial/figures/phenotype_pooled_latency_hist.py::emit_phenotype_pooled_latency_cdfs(resolver, layout="four_separate" | "single_4panel", phenotype_filter=None, ...)`.

**Per-figure plot:** phenotype-pooled empirical CDFs. Layout choice locked at Task 0.5 review:
- **Layout (a) `four_separate`** — one figure per phenotype tier; 4 traces (one per epoch) within each.
- **Layout (b) `single_4panel`** — single figure with 4 panels (one panel per phenotype); 4 traces (one per epoch) per panel.

Defaults to (b) until Task 0.5 locks the choice.

**Source:** `pipeline_outputs/stats/inputs/latency_hist/<animal>.parquet`. Pool per-trial latencies across animals within (phenotype × epoch); compute empirical CDF per (phenotype, epoch) cell; one trace per epoch per phenotype panel.

**KS-bridge p-value annotation:** consume `pipeline_outputs/stats/results/<axis>/<granularity>/latency_hist.csv` (location confirmed at Task 0.5). Annotate each phenotype panel with the pre-vs-{acute,sub_acute,chronic} KS-test p-values.

**Driver:** `scripts/phase_9_1_figures/build_phenotype_pooled_latency_hist.py --endpoint-list configs/phase_9_1_endpoint_lists/phenotype_pooled_latency_hist_endpoints.yaml --layout {four_separate,single_4panel} [--phenotype-filter <tier>]`.

**Output:**
- Layout (a): `pipeline_outputs/phase_9_1_figures/phenotype_pooled_latency_hist/{mild,moderate,moderate_severe,severe}.{svg,png}` (4 figures).
- Layout (b): `pipeline_outputs/phase_9_1_figures/phenotype_pooled_latency_hist/all_phenotypes_4panel.{svg,png}` (1 figure).

**Tests:** `tests/test_figures_phenotype_pooled_latency_hist.py` — fixture-based; uses `PathResolver(output_root=tmp_path)`.

#### Task 4a — latency_hist preview
- For layout (b) single 4-panel, preview = single phenotype tier panel (other 3 stubbed). For layout (a) 4-separate, preview = 1 of 4 phenotype figures.
- Wall time: **~0.15 day**.

#### Task 4b — latency_hist scaffold review gate (Priya)
- Layout (a) vs (b) decision also locks here if Task 0.5 deferred.
- Wall time: Priya bandwidth.

#### Task 4c — latency_hist full cohort emit
- Wall time: **~0.35 day** (small data shape; no new stats).

### Task 5 — Tongue ipsi-shift figure families (Q-lock 8; 4-7 figures total at Step 5c)

Implement `src/stroke_orofacial/figures/phenotype_pooled_ipsi_shift.py` with two emit functions, one per family. **Wraps existing primitives** from `dlc_kinematics.mean_sem_visual` + `dlc_kinematics.tongue_angle_cohort` — does NOT re-implement trajectory loading, tone-alignment, time-binning, or per-session-overlay rendering.

**Family 8.1 emit — Delta tongue angle (3 endpoints, ~3 figures):**

```python
emit_phenotype_pooled_ipsi_shift_angle(
    endpoint_slug,                # one of 3 angle endpoints
    resolver,
    animals,                       # for phenotype lookup + ipsi/contra translation
    baseline_window="pre_stroke",  # rel_day <= 0
    phenotype_filter=None,         # None = all tiers; for Q-lock 9 Step 5a preview
    ...
) -> Path  # outputs phenotype_pooled_ipsi_shift/angle/<endpoint_slug>.{svg,png}
```

Per-endpoint figure: 8-panel grid (4 phenotype × 2 sides {ipsi, contra}); each panel has 4 epoch traces (pre/acute/sub_acute/chronic), two-layer rendered (thin per-session traces + foreground mean ± SEM); y=0 reference; baseline-subtracted delta angle on y-axis.

**Family 8.2 emit — Delta tongue x trajectory (1 endpoint, 1-4 figures):**

```python
emit_phenotype_pooled_ipsi_shift_x_trajectory(
    resolver,
    animals,
    layout="single_4panel" | "four_separate",  # locked at Task 0.5
    baseline_window="pre_stroke",
    phenotype_filter=None,
    ...
) -> Path  # outputs phenotype_pooled_ipsi_shift/x_trajectory/...
```

Defaults to `single_4panel` until Task 0.5 locks the choice. Per-figure: 8 panels (4 phenotype × 2 sides) for composite layout, OR 2 panels (1 phenotype × 2 sides) for per-phenotype layout.

**Baseline computation (shared helper):**

```python
def compute_per_animal_side_matched_baseline(
    animal: str,
    bodypart: str,                 # "tongue" for Family 8.2; per-lick angle for Family 8.1
    side: Literal["L", "R"],       # mouse-frame; translated to ipsi/contra per AnimalInfo
    resolver,
    animals,
) -> NDArray:  # baseline_trajectory(t) at tone-aligned time bins
    """Mean over pre-stroke (rel_day <= 0) sessions × trials of given side."""
```

Per-session deltas computed at emit time; phenotype-pool across (animal, session) within (phenotype, epoch, side).

**Driver:** `scripts/phase_9_1_figures/build_phenotype_pooled_ipsi_shift.py --family {8.1,8.2} --endpoint-list configs/phase_9_1_endpoint_lists/phenotype_pooled_ipsi_shift_<family>_endpoints.yaml [--layout {single_4panel,four_separate}] [--phenotype-filter <tier>]`.

**Output:**
- Family 8.1: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/angle/<endpoint_slug>.{svg,png}` (3 figures).
- Family 8.2: `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/x_trajectory/...` (1-4 figures by layout).

**Existing-code reuse (mandatory):**
- `dlc_kinematics.mean_sem_visual.build_mean_sem_cohort(bodypart, animal, ...)` for tone-aligned mean ± SEM trajectory loading.
- `dlc_kinematics.tongue_angle_cohort._plot_tone_aligned_session_overlays(...)` for thin per-session overlay rendering.
- `dlc_kinematics.tongue_angle_cohort._plot_tone_aligned_binned_overlays(...)` for foreground mean ± SEM rendering.
- `dlc_kinematics.tongue_pertrial` `tongue_lick_t_peaks_bylick` primitive for per-lick peak-time data (Family 8.1).
- `AnimalInfo.mouse_side_to_ipsi_contra(side, stroke_laterality)` for axis labeling.
- `configs/defaults.yaml::dlc_kinematics.mean_sem_visual.*` for time-binning convention.

**Tests:** `tests/test_figures_phenotype_pooled_ipsi_shift.py` — fixture-based; uses `PathResolver(output_root=tmp_path)`. Asserts (a) pre-epoch trace exists in every panel; (b) y=0 reference line drawn; (c) baseline subtraction produces ≈0 pre-epoch mean within numerical tolerance; (d) two-layer rendering writes both per-session and binned-overlay objects to the figure.

**Q-lock 9 preview-tier suggestion:** for Family 8.2 (continuous x trajectory), the moderate-severe (n=1, PS51) preview tier is appropriate per Q-lock 9 default — stress-tests single-animal-trace rendering of two-layer overlays. For Family 8.1 (angle endpoints), CC may propose mild (n=4) instead at task-start to stress-test cross-session two-layer rendering at higher pooled-n; surface in Task 5a commit message.

#### Task 5a — Ipsi-shift preview
- Both Family 8.1 + 8.2 at single phenotype tier (or split families into different preview tiers if CC argues for it).
- Wall time: **~0.4 day**.

#### Task 5b — Ipsi-shift scaffold review gate (Priya)
- Priya iterates on two-layer rendering (alpha, line thickness, color), baseline-subtraction sanity check (verify pre-epoch deltas ≈0), layout choice for Family 8.2.
- Wall time: Priya bandwidth.

#### Task 5c — Ipsi-shift full cohort emit
- Wall time: **~1.6 days** (2 families × full cohort emit + iteration cost).

### Task 6 — Pub-quality polish

`src/stroke_orofacial/figures/pub_polish.py` — module with:
- `apply_journal_typography(fig, panel_width_inches=3.5)` — consistent font sizes; 2-column journal layout sizing.
- `phenotype_palette()` — returns `{phenotype: rgb_or_hex}` mapping (default ColorBrewer YlOrRd 4-step; finalized via OPEN-Q 1 at scaffold review).
- `apply_ipsi_contra_labels(ax, animals_map)` — per-side axis/legend relabeling per `AnimalInfo.mouse_side_to_ipsi_contra()`.
- `figure_caption_caveat()` — returns the canonical cohort-uniformity caveat sentence (Q-lock 4).

**Gate per Q-lock 9:** Task 6 only runs after all Step Nc full emits complete (Tasks 1c, 2c, 3c, 4c, 5c). Cross-family palette + typography pass applied to all ~124-127 figures. Task 6 does NOT re-litigate decisions locked in any Step Nb gate.

OPEN-Q 1 (palette) resolves at this stage.

### Task 7 — Composite figures per Priya paper narrative

`src/stroke_orofacial/figures/composites.py::build_composite(source_panels, layout_spec)`.

**Per Comment 3:** Task 7 composites pull from BOTH source figure families:
1. V4/V5 family at `pipeline_outputs/phase_9_1_figures/phenotype_pooled/` — for the 4 confirmatory kinematic + 3 non-confirmatory vxy headlines + any other endpoint Priya features.
2. Phenotype-pooled spatial family at `pipeline_outputs/phase_9_1_figures/phenotype_pooled_spatial/` — for the 4 confirmatory Wasserstein-at-tone_aligned_all headlines.
3. Q-lock 8 ipsi-shift family at `pipeline_outputs/phase_9_1_figures/phenotype_pooled_ipsi_shift/` — Family 8.2 (continuous x trajectory) is a likely paper-narrative figure per memory finding #6.

**Scaffold must not hardcode a single source dir.** Composite spec format accepts panel references like `phenotype_pooled/<endpoint>/v4_*.svg` OR `phenotype_pooled_spatial/<family>/wasserstein/tone_aligned_all.svg` OR `phenotype_pooled_ipsi_shift/x_trajectory/<...>.svg`.

OPEN-Q 2 (composite inventory) resolves here. Priya enumerates which panels combine into which paper figures during Task 7 scaffold review.

**Output:** `pipeline_outputs/phase_9_1_figures/composites/<composite_name>.{svg,png}` + final-paper-asset variants.

### Task 8 — Verification + Priya scientific review

Visual gate across the ~124-127 figure inventory (70 V4/V5 + 48 spatial + 1-4 latency_hist CDFs + 4-7 ipsi-shift trajectories, minus composites which Priya signs off panel-by-panel at Task 7).

CC-owned automated checks:
1. All ~124-127 figures exist at expected paths.
2. Each figure has both `.svg` and `.png` variants.
3. SVG files are non-empty + parseable XML.
4. Phenotype-tier n-labels appear in every figure metadata or title.
5. Q-lock 8 figures: pre-epoch trace present in every panel; y=0 reference line rendered.

Priya-owned visual gate:
1. Sample audit of 10-20 figures spanning phenotype tiers + endpoints + spatial metrics + ipsi-shift families; sign off on style, palette, ipsi/contra labeling correctness, two-layer rendering, n-label readability.

**Output:** `.scratch_phase_9_1/verdict.md` — CC writes gate-1 through gate-5 PASS/FAIL; Priya writes gate-6 verdict. Phase 9.1 closes only after Priya's gate-6 PASS.

### Task 9 — DECISIONS + MIGRATION_LOG + close PR + tag

1. `docs/DECISIONS.md` entry (top of file) — Phase 9.1 architecture + methodology decisions.
2. `docs/MIGRATION_LOG.md` entry — Phase 9.1 deliverables + behavior-diffs vs legacy (likely none — no legacy counterpart for phenotype-pooled figure work).
3. Open PR `phase/9.1-figures → main`. Standard CLAUDE.md PR template.
4. After merge: tag the merge commit `v9.1-phenotype-pooled-figures` per ground rule 8. Tag message: `Phase 9.1: phenotype-pooled figures + pub-polish on Phase 9 stats outputs`.
5. Verify tag pushed: `git ls-remote --tags origin | grep v9.1`.

---

## Pre-commit checks (per Comment 7)

Standard pattern, mirroring Phase 9 kickoff:

```bash
git branch --show-current   # must NOT be main or master
                            # pre-commit hook at .githooks/pre-commit enforces this
                            # DO NOT bypass with --no-verify per ground rule 8
conda run -n stroke_orofacial pytest --collect-only
conda run -n stroke_orofacial pytest tests/test_figures_*.py  # if any figure module touched
conda run -n stroke_orofacial ruff check .                     # pre-existing clean baseline
```

If pre-commit hook fixes blocks a commit, investigate root cause; do not bypass.

---

## PR + merge + tag

Standard sequence:

```bash
# After Task 9 close commit:
gh pr create --title "Phase 9.1: phenotype-pooled figures + pub-polish" \
  --body "$(cat <<'EOF'
## Summary
- V4 + V5 phenotype-pooled figures for all 35 LMM-run scalar endpoints (~70 figures).
- 48 phenotype-pooled spatial figures (3 metrics × 4 scope/trial_group × 4 families).
- 1-4 phenotype-pooled `latency_hist` CDF figures (per Q-lock 7 KS-bridge family).
- 4-7 tongue ipsi-shift figures (per Q-lock 8 — Family 8.1 angle × 3, Family 8.2 x trajectory × 1-4) with delta-from-baseline normalization + two-layer rendering + pre-epoch noise reference.
- Pub-polish: typography + palette + ipsi/contra labeling + composites.

## Test plan
- [ ] All ~124-127 figures exist at expected paths + have SVG + PNG variants.
- [ ] Phenotype-tier n-labels visible on every figure.
- [ ] Priya visual gate-5 PASS in `.scratch_phase_9_1/verdict.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# After merge:
git checkout main && git pull
git tag -a v9.1-phenotype-pooled-figures <merge-sha> \
  -m "Phase 9.1: phenotype-pooled figures + pub-polish on Phase 9 stats outputs"
git push origin v9.1-phenotype-pooled-figures
git tag --list | tail -3  # confirm
```

---

## Forward-pointers carried out of Phase 9.1

- **Pub-figures phase (speculative)** — paper-quality polish phase blocked on Phase 9 + 9.1. Possible future kickoff once paper narrative is locked.
- **Phase 9.x** — per-phenotype stats + per-animal nonlinear recovery fits (3-tier moderate-pool grouping, ORTHOGONAL scope vs 9.1 — different statistical method, not different figures). Scoping at `docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md`.
- **Composite figure paper-narrative iteration** — if paper layout shifts post-close, the Q-lock 6 `--endpoint-list` flag enables single-command rerun against a narrowed endpoint set.

---

## References

- **Scoping doc:** [`docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`](phase-9.1-phenotype-pooled-figures-scoping.md) — with 2026-05-23 + 2026-05-25 + 2026-05-25 (b) amendments. Both 2026-05-25 amendments landed as commit `3390146` on this branch.
- **Phase 9 kickoff:** [`docs/prompts/phase-9-stats-kickoff.md`](phase-9-stats-kickoff.md) — 11 addenda; source of truth for what Phase 9 produces.
- **Phase 9.x scoping:** [`docs/prompts/phase-9.x-nonlinear-recovery-fit-scoping.md`](phase-9.x-nonlinear-recovery-fit-scoping.md) — divergent 3-tier convention.
- **Phase 9 Addendum #4** (KS-bridge for `latency_hist` `vector_per_session` endpoint; Q-lock 7 source): Phase 9 kickoff lines 784-863.
- **Phase 9 Addendum #7** (cross-scope spatial inventory): Phase 9 kickoff lines 1113-1216.
- **Phase 9 Addendum #8** (V1-V5 grid + 7 headlines): Phase 9 kickoff lines 1218-1312.
- **Phase 9 Addendum #10** (per-coefficient headline summary v2): Phase 9 kickoff lines 1422-1527.
- **Canonical confirmatory family CSV:** [`.scratch_phase_9/task_5_headline_summary.csv`](../../.scratch_phase_9/task_5_headline_summary.csv) — 306 rows (v2); 16 unique confirmatory endpoints.
- **Phase 9 DECISIONS:** [`docs/DECISIONS.md`](../DECISIONS.md) 2026-05-25 entry (8 sub-decisions).
- **Phase 9 MIGRATION_LOG:** [`docs/MIGRATION_LOG.md`](../MIGRATION_LOG.md) lines 6406-6492.
- **`AnimalInfo.mouse_side_to_ipsi_contra()`:** Phase 8a.10 scaffolding for ipsi/contra labeling.
- **`configs/animals.yaml`:** per-animal `recovery_phenotype` + `epoch_boundaries` + `bin_days` + `stroke_laterality`.
- **`src/stroke_orofacial/stats/recovery_epochs.py`:** `cohort_phenotype_summary`, `assign_epoch_label`.

---

## Open scoping questions (defer to within-phase iteration)

- **OPEN-Q 1 (Task 6 scaffold review):** Phenotype palette choice — sequential (severity ordering) vs categorical (4 distinct colors). Suggestion: ColorBrewer YlOrRd 4-step (light yellow = mild → dark red = severe) for severity-ordering clarity. Priya finalizes during Task 6 scaffold review.
- **OPEN-Q 2 (Task 7 scaffold review):** Composite figure inventory — Priya enumerates which V4/V5/spatial/ipsi-shift panels combine into which paper figures.
- **OPEN-Q 3 (Task 1b / Task 2b scaffold review):** Retroactive two-layer rendering for V4 (per_bin) and/or V5 (per_epoch). Q-lock 8 locks two-layer rendering for ipsi-shift only; the V4/V5 extension is deferred. For V4, "session trace" → per-animal trajectory; for V5, individual session-points already render via boxplot whiskers/scatter. Priya can request retroactive application at Task 1b / Task 2b if the Q-lock 8 style reads cleanly during Task 5b.

Both OPEN-Qs are scaffold-review questions, not blockers. Phase 9.1 work can proceed past Task 0 without them resolved; they pin in their respective tasks.

---

## Out of scope (re-emphasized)

Phase 9.1 does NOT:

- Run new statistical tests (Phase 9 owns).
- Compute new endpoint values (Phase 9 + upstream phases own).
- Emit per-animal V1/V2/V3 figures (Phase 9 Task 7 owns).
- Introduce new scientific axes or comparisons.
- Touch `pipeline_outputs/stats/{inputs,results}/` — those are read-only for Phase 9.1.

Phase 9.1 is consumer + visualization + polish only.
