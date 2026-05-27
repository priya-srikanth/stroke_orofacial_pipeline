# Phase 7f — Jaw DLC quality investigation (scoping doc)

> **Status:** DRAFT — investigation-only audit. No production code or data
> touched. Final scope decision pending Priya review of the verdict.
>
> **Branch:** `investigation/jaw-quality-audit` (off `main` at 2026-05-26).
> Parallel to and independent of Event B
> (`chore/phase-7e-cohort-reemit`, PR #135).
>
> **Initial verdict (SUPERSEDED by 2026-05-26 amendment below):**
> `light-cleanup` scoped to `jaw_pertrial.py` only. Kept for context;
> see Addendum #1 immediately below for the revised verdict.

> **AMENDMENT 2026-05-26 (Priya visual review of renders).** Priya
> reviewed two renders and corrected my initial framing — the artifact
> mechanism is **broader than single-frame outliers**:
>
> - **PS54 / 2025-05-01 / t013 R** (peak 138 px, lk=0.72): the period
>   from ~0 to ~1200 ms contains multiple **clusters** of high-y raw
>   DLC (reaching 100-150 px) interleaved with wide Stage-5 baseline-
>   fill bands (red). Likelihood during those clusters is mostly < 0.5.
>   Real continuous jaw tracking starts only at ~1300 ms. **This IS the
>   structural analog of tongue v7's PCHIP-anchored-spike-against-
>   Stage-5-zeros pattern.**
> - **PS54 / 2025-05-06 / t095 L** (peak 125 px, lk=0.66): single-frame
>   outlier on otherwise-resting trace — the simpler case I had
>   documented in §4.
>
> **Three new rules to scope into Phase 7f** (revises §5 + §6):
>
> 1. **Hard physical-ceiling rule:** jaw `y_final ≤ ~75 px` above
>    baseline is a reasonable physiological maximum. Anything above is
>    artifact. Threshold needs calibration on the audit cohort — TBD as
>    part of Phase 7f Task 1.
> 2. **Within-trial outlier rules analogous to tongue v7:** port the
>    cluster classifier (Rule A intra-cluster shape + Rule B non-base
>    neighbor + isolated-short override, per Phase 7e Decisions 9, 11)
>    AND the frame-level outlier wipe (Decision 12) AND PCHIP-extend
>    wipe (Decision 13). Constants need jaw-specific calibration.
> 3. **Interpolation gap-filling tuning may be needed.** Jaw's
>    `max_gap_ms = 120` (vs. tongue's 56) is more lenient — allowing
>    PCHIP to bridge larger gaps that may anchor artifact clusters.
>
> **Revised verdict:** between `light-cleanup-plus` (Option A: all
> logic inside `jaw_pertrial.py`, no v5p3 re-emit, ~3-5 days CC) and
> `bodypart-parametric v7 port` (Option B: full v5p3 integration with
> jaw-specific constants + cohort v5p3 re-emit, ~2-3 weeks CC).
> Architecture picked at kickoff. The audit confirms the cleanup is
> needed; the architecture choice is the open scoping question, not
> whether to do it.
>
> **Cohort-level context (unchanged):** jaw v5p3 is cleaner than tongue
> cohort-wide (87-99% detection rate vs. tongue's 10-21%; baseline-fill
> at peaks ≤ 2.4% in any cell). Dominant biological signal
> (severe-acute / mod-sev-acute collapse to ~11 px) is robust to
> lk-gate choice (cell ranking preserved). The per-trial extreme tail
> is where the cluster + frame artifacts hide — cohort means understate
> the contamination.

> **AMENDMENT 2026-05-26 #12 (v3.4 re-emit Step 1 complete — cleaned_traces
> written for 8-animal cohort).** Per Priya 2026-05-26 ("proceed with full
> re-emit"), Step 1 of Phase 7f Option B has been executed on the
> investigation branch:
>
> - **231 sessions × 8 animals re-emitted in 8.3 min** (0 failures, 144
>   skipped — secondary-spout sessions + missing v5p3 source parquets).
> - **Output path:** `dlc_kinematics/cleaned_traces/jaw/<animal>/<YYYYMMDD>.parquet`
>   on MICROSCOPE — uses tongue's `resolver.cleaned_trace("jaw", ...)`
>   path resolver method.
> - **Schema:** v5p3-compatible drop-in (`frame_idx`, `x_final`,
>   `y_final`, `likelihood_raw`, `is_interp_fill`, `is_baseline_fill`,
>   `fill_method`) — downstream consumers swap parquet path; no schema
>   migration needed.
> - **Cleanup behavior:** re-PCHIP (NOT tongue's wipe-to-y=0 — jaw is
>   anatomically present between licks; re-PCHIP is semantically correct).
>   Both x and y re-PCHIP'd from the SAME surviving anchor index set
>   (co-temporally consistent (x, y) pairs).
> - **Metadata:** preserved all v5p3 keys + added `cleanup_version="v3.4"`
>   and `cleanup_constants_json` (the full constant block as JSON).
>
> **Parity validation** (re-emit cleaned parquet vs audit's
> `per_trial_cleanup_v3p4.parquet`):
>
> - 22,363 total trials checked
> - 713 mismatches (3.19% of trials with |diff| > 0.01 px)
> - Cohort-wide median |diff| = 1.16 px, p90 = 7.3 px, max = 51 px
> - **Severe-acute (paper narrative)**: 20/2316 mismatches (0.86%);
>   median 2.25 px, max 22.6 px — load-bearing cell preserved
> - 54 qc flips cohort-wide (0.24% of trials)
>
> **Root cause** (not a re-emit bug): the audit computed `baseline_mean`
> from the ORIGINAL v5p3 trace; the cleaned parquet's `baseline_mean`
> is what `jaw_pertrial` will compute from the cleaned trace — slightly
> shifted toward 0 if R1/R2/R3 wiped any frames in the [-500, 0]ms
> baseline window. **The re-emit's numbers are production-correct**
> (what jaw_pertrial will see). Audit numbers were a forward-projection
> approximation. Mismatches concentrated in mild/moderate cells where
> the cleanup wipes more frames; severe-acute barely affected.
>
> **Step 1 artifacts** (in scratch, gitignored):
> - `.scratch_phase_7f_scoping/reemit_jaw_clean_traces.py` (production re-emit script)
> - `.scratch_phase_7f_scoping/validate_reemit_parity.py` (parity validator)
> - `.scratch_phase_7f_scoping/reemit_full_cohort.log`
> - `.scratch_phase_7f_scoping/reemit_parity_mismatches.csv`
>
> **Step 1 production artifacts** (on MICROSCOPE):
> `pipeline_outputs/dlc_kinematics/cleaned_traces/jaw/{PS46-50,PS51,PS54,PS55}/<YYYYMMDD>.parquet`
> — 231 files.
>
> **Next: Steps 2-6 (separate Phase 7f phase branch + kickoff doc):**
> 1. Step 2 — re-emit jaw_pertrial scalars reading from cleaned_traces
> 2. Step 3 — re-emit `tongue_jaw_mismatch` (consumes new `jaw_pass_qc`)
> 3. Step 4 — re-emit mean/SEM jaw cross-session traces + videos
> 4. Step 5 — re-materialize Phase 9 stats inputs + results for jaw
>    endpoints (axis 1 jaw_peak_* family; recovery LMM)
> 5. Step 6 — re-render figures (V4/V5, recovery_trajectories,
>    mismatch candidate-rate plots)
>
> Each step touches production code and stats. Steps 2-6 should land
> on `phase/7f-jaw-cleanup-cohort-reemit` (off main) with a proper
> kickoff doc, not piled onto the investigation branch.

> **AMENDMENT 2026-05-26 #11 (v3.4: add R1-x bidirectional ceiling at
> ±40 px from baseline_mean_x).** Per Priya 2026-05-26 ("can we add a
> filter for x values > 40 px above/below baseline?"), v3.4 = v3.3 +
> a symmetric R1-x rule: `|x_final − baseline_mean_x| > 40 → wipe`
> (raw frames only).
>
> Cohort impact (v3.3 → v3.4):
> - severe-acute clean mean 10.85 → 10.92 (+0.07 px — paper-narrative
>   signal unchanged)
> - mild/chronic clean mean 101.81 → 101.47 (−0.34 px)
> - severe/chronic clean mean 73.81 → 72.74 (−1.07 px)
> - severe/sub_acute clean mean 62.20 → 61.57 (−0.63 px)
> - max pass_qc flip rate 2.8% (moderate/pre) — same as v3.3
> - R1-x wipe rates: 0.01% (severe-acute) to 2.0% (mod-sev/chronic)
>
> Per-trial verification:
> - **Pre-stroke (8 trials):** 1/8 affected (PS50 mild_median 102.5 →
>   98.96; pass_qc preserved). 7/8 unchanged from v3.3.
> - **Severe-acute (8 trials):** essentially unchanged from v3.3.
>
> **Locked design for Phase 7f Option B kickoff:**
> ```
> Y_CEILING_PX = 125  (positive-side only)
> X_CEILING_PX = 40   (bidirectional)
> ISOLATED_MAX_N = 5
> ISOLATED_RADIUS_MS = 30
> FRAME_JUMP_THR_PX = 70
> FRAME_OUTLIER_LOCAL_MEDIAN_MS = 20
> MAX_GAP_MS_PCHIP = 120  (jaw v5p3 default)
> ```
>
> R1-x is bidirectional (symmetric ± from baseline_mean_x) since
> jaw x deviates both positive and negative. R1-y stays positive-only
> (negative deflection is physiological closing). Cross-cluster R3
> still operates on y only (per audit findings: R3-x adds < 0.005%
> additional wipes cohort-wide and provides no visible benefit on
> any of the 16 inspected trials).

> **AMENDMENT 2026-05-26 #10 (Y_CEILING locked at 125 — v3.3 cohort
> + pre-stroke + severe-acute verification).** Priya 2026-05-26 ("from
> the healthy trials I'm convinced we should loosen the max to 125").
> v3.3 = v3.2 with `Y_CEILING_PX = 125` (all other constants unchanged).
> Full results in §3.13.
>
> **Headline results:**
> - **Cohort means drop 1-5% across all cells** (vs. 20-30% in v3.2).
> - **Severe-acute mean 11.2 → 10.92 (−2.5%)** — paper-narrative signal
>   preserved.
> - **Pre-stroke median trials unchanged** (peaks ≤ 125 survive intact);
>   top trials clipped 30-70 px (vs. 60-90 px in v3.2).
> - **PS49 mild_top real licking preserved** — no more bulk wipes
>   dropping to y=0; only the 200 px outlier spike at t=3404ms wiped.
> - **PS54 t095 single-frame outlier still caught** — R1 fires on the
>   125.1 px spike (deflection 139.6 > 125 ceiling).
> - **PS54 t013 R `pass_qc` flipped back to True** — higher ceiling
>   preserves supra-threshold frames in the real-movement region.
> - `jaw_pass_qc` worst flip 2.7% in moderate/pre (down from 5.3%).
>
> **Locked design for Phase 7f Option B kickoff:**
> - `Y_CEILING_PX = 125`
> - `ISOLATED_MAX_N = 5`
> - `ISOLATED_RADIUS_MS = 30`
> - `FRAME_JUMP_THR_PX = 70`
> - `FRAME_OUTLIER_LOCAL_MEDIAN_MS = 20`
> - `MAX_GAP_MS_PCHIP = 120` (jaw v5p3 default unchanged)
> - Pre-Stage-4 application order (R1 + R3 + R2 + re-PCHIP).
> - Cross-cluster R3 (K=11 nearest raw frames via `median_filter`).
>
> **No remaining open knobs.** v3.3 is the locked design for Phase 7f
> Task 1 production implementation.

> **AMENDMENT 2026-05-26 #9 (pre-stroke healthy-licking verification —
> Y-ceiling=80 too tight, must raise).** Per Priya 2026-05-26 ("could
> we check some pre-stroke sessions too?"), 8 pre-stroke trials rendered
> under v3.2 (top-peak + median-peak per phenotype). Full results in
> §3.12. Headline:
>
> - **`jaw_pass_qc` preserved on ALL 8 pre-stroke trials** — mismatch
>   classifier is safe.
> - **Real licking peaks in healthy mice reach 110-200 px**, well above
>   the Y_CEILING=80. Top-peak trials get clipped 30-90 px.
> - **Long high-amplitude licking bursts drop to baseline (y=0)** for
>   entire stretches (e.g., PS49 t7 ~500-700ms; PS50 t81 ~2700-3000ms)
>   — R1 wipes consecutive frames + gaps > 120ms fall to Stage 5.
> - **PCHIP overshoot leaks above the Y-ceiling** in PS46 moderate_top
>   (clean peak 117.9 px, above the 73 px ceiling) because surrounding
>   anchors are near-ceiling and PCHIP overshoots between them.
>
> **Verdict: v3.2 with Y_CEILING=80 is structurally too tight for
> healthy mice.** Phase 7f Task 1 must raise the Y-ceiling and/or use
> a per-phenotype value. Updated recommendation (§3.12):
> - Drop **option (i) "keep 80"** — pre-stroke confirms this wipes real
>   movement.
> - **Lead candidate: Y_CEILING = 200 px global** (preserves healthy
>   peaks up to ~200 px).
> - **Sensitivity comparison: per-phenotype** (e.g., severe 100, others
>   200) — most honest but adds complexity.
>
> Suggested Phase 7f Task 1 first iteration: 200 global + per-phenotype
> sensitivity sweep. Decision deferred to kickoff.

> **AMENDMENT 2026-05-26 #8 (cleanup v3.2 — cross-cluster R3 closes a
> coverage gap).** Priya 2026-05-26 visual review of v3 spotted a
> single-frame low-y outlier at t=184ms in PS54 / 5-01 / t013 R (y=-36
> surrounded by raw at y≈38). v3.1 (threshold 80→70) didn't catch it
> because the outlier sits in a coverage gap of v3's rule set: R1
> Y-ceiling is positive-side only, R2 isolated-short requires no nearby
> raw cluster (this outlier has one 8ms away), R3's within-cluster
> median skips single-frame clusters. Threshold tightening alone
> doesn't help.
>
> **v3.2 fix:** Changed R3 from "within-cluster rolling median" to
> "K-nearest raw-frame median" — for each raw frame, the local median
> is computed over the K=11 nearest raw frames REGARDLESS of cluster
> identity. In dense regions equivalent to the original ±20ms time
> window; in sparse regions bridges cluster boundaries to catch
> single-frame outliers between baseline-fill bands. Vectorized via
> `scipy.ndimage.median_filter` on the raw-frame array.
>
> **Result:** R3 fires on the PS54 t013 R outlier (deviation 74 px,
> above threshold 70). Cohort impact tiny: severe-acute mean 10.85 →
> 10.82 (−0.3%); no over-wiping on any of the 8 severe-acute visual
> renders; `pass_qc` rates identical to v3 cohort-wide.
>
> **v3.2 is the locked design for Phase 7f Option B kickoff.**
> Constants: Y_CEILING=80, ISOLATED_MAX_N=5, ISOLATED_RADIUS_MS=30,
> FRAME_JUMP_THR_PX=70, FRAME_OUTLIER_LOCAL_MEDIAN_MS=20,
> MAX_GAP_MS_PCHIP=120. The cross-cluster R3 definition is the only
> architectural delta from v3.

> **AMENDMENT 2026-05-26 #7 (cleanup v3 — order-of-ops fix validated).**
> Scoping audit #5 (v3, §3.10) implemented Addendum #6's pre-Stage-4
> design: same rules as v2 (R1 Y-ceiling=80, R2 isolated-short, R3
> frame-outlier wipe) but applied to RAW DLC frames (fill_method == 0)
> BEFORE the PCHIP gap-fill. Then re-PCHIP-interpolates from the
> cleaned anchor set; gaps > 120ms fall to baseline.
>
> **Decisive result: v2's "clean peak at lk=0.05" PCHIP-bridge bug is
> fixed.** Across all 8 severe-acute visual-render trials, v3's clean
> peak now lands on a real raw DLC frame with `lk ≥ 0.5`:
>
> - PS54 / 5-05 / t010 L: v2 clean_peak lk=**0.05** → v3 clean_peak
>   lk=**0.51** (51.7 px at t=4004 ms, real licking region).
> - PS54 / 5-01 / t013 R: v2 lk=0.34 → v3 lk=**0.51** (57.9 px).
> - PS55 / 5-14 / t033 L: v2 lk=0.81 → v3 lk=**0.92** (62.1 px).
> - PS54 / 5-06 / t095 L (single-frame outlier): both v2 and v3 land
>   at 9.7 px / lk=0.81 (correctly wiped by R1 in both).
>
> **Cohort metrics nearly identical to v2** (same rules, just earlier
> in the pipeline):
> - Severe-acute cohort mean: prod 11.2 → clean 10.85 (−3.2%) —
>   paper-narrative signal preserved exactly.
> - jaw_pass_qc rates preserved cohort-wide; worst flip is 5.3% in
>   moderate/pre. Severe-acute flip is 0.04%.
> - Mild cells still drop 23-26% in cohort mean due to Y-ceiling=80
>   clipping real licking peaks — same Y-ceiling design question as v2.
>
> **Architecture verdict locked: v3 is the right design for Phase 7f
> Option B (bodypart-parametric v7 port + cohort v5p3 re-emit).**
> Production implementation should insert the new pre-clean as a new
> Stage 3.5 in `src/stroke_orofacial/dlc_kinematics/interpolation.py`,
> with constants in `configs/defaults.yaml dlc_kinematics.jaw.preclean.*`.
>
> Remaining open knob: **Y-ceiling threshold + handling of real
> licking peaks > 80 px in healthy mice**. Four options (i)/(ii)/(iii)/(iv)
> documented at the end of §3.10. Phase 7f Task 1 should empirically
> calibrate via per-phenotype `y99` sweep on lk≥0.85 raw DLC +
> sensitivity analysis on `candidate_no_lick_with_jaw_move` rate.

> **AMENDMENT 2026-05-26 #6 (order-of-ops pivot — Priya).** Priya
> 2026-05-26 (post v2 audit visual review): "Seems like we're
> interpolating BEFORE applying our exclusion filters. Like tongue,
> we should probably exclude based on likelihood and value (above our
> ceiling of 80), outlier, etc, THEN interpolate."
>
> **Diagnostic evidence**: PS54 / 2025-05-05 / trial 10 / side L
> visual render showed `clean_peak` at `lk = 0.05`. The frame's raw
> DLC likelihood was 0.05 — well below v5p3's Stage 2 `lk_thr = 0.5`
> gate, so it was DROPPED as raw and PCHIP-interpolated at Stage 4.
> The "peak" my v2 cleanup picked was actually a PCHIP-bridge value,
> NOT a real DLC frame. The post-v5p3 cleanup framework cannot see
> this — by the time it operates on `y_final`, the trace has been
> smoothed by interpolation across the artifact gap.
>
> **Pivot:** the exclusion rules need to live at the RAW DLC level,
> BETWEEN Stage 3 (drop low-lk + isolated-hi-lk) and Stage 4
> (PCHIP gap-fill). This matches tongue v7's architecture exactly
> (pre-clean lives in Stages 1-3, not post-Stage-5). My audits #3
> and #4 were post-v5p3 simulations — informative for catching the
> Y-ceiling=75-vs-80 calibration and the cluster-mean-lk over-wiping,
> but **fundamentally the wrong order of operations** for production.
>
> **Concretely: Phase 7f Option B (bodypart-parametric v7 port +
> v5p3 re-emit) is the only design that gets this right.** Option A
> (post-v5p3 cleanup inside jaw_pertrial) is now formally obsolete:
> a post-Stage-5 patch CANNOT see what was dropped at Stage 2 +
> bridged at Stage 4.
>
> **Audit #5 (v3 design — pending)**: re-implement v5p3 in the audit
> script with the new pre-clean rules inserted between Stages 3 and
> 4. Constants from Addendum #5 (R1 Y-ceiling=80, R2 isolated-short,
> R3 frame-outlier wipe, R4 PCHIP-extend) carry over, but applied to
> raw DLC (`{bodypart}_x`, `{bodypart}_y`, `{bodypart}_likelihood`)
> rather than `y_final`. Then re-run Stage 4-6 and compute
> jaw_pertrial scalars on the result.

> **AMENDMENT 2026-05-26 #5 (cleanup v2 — likelihood-free design,
> Y-ceiling=80, frame-outlier wipe works).** Per Priya 2026-05-26
> (a) "we should keep likelihood threshold at 0.5", (b) "loosen max to
> 80", and visual confirmation that v1's cluster-mean-lk gate wiped
> ~99% of real movement in active-licking trials — scoping audit #4
> (v2, §3.9) dropped the cluster-mean-lk gate and applied a
> likelihood-free rule set (R1 Y-ceiling=80, R2 isolated-short cluster,
> R3 frame-outlier wipe via `scipy.ndimage.median_filter`, R4
> PCHIP-extend). Also tracks `jaw_pass_qc` (the mismatch classifier
> input) per-trial.
>
> **Results:**
>
> - **R3 frame-outlier wipe correctly catches single-frame spikes**:
>   PS54 / 5-06 / t095 L (single-frame outlier) goes 125 → 9.7 px,
>   R3 fires on the 1 outlier frame, qc preserved as True. Aggregate
>   wipe stats round to ~0% because R3 fires on truly rare events,
>   not because R3 is broken.
> - **v2 preserves the trace much better than v1**: PS55 / 5-14 /
>   t033 L (active licking + Stage-5-fill bands) keeps 525 raw frames
>   in v2 vs. 5 in v1. **No bulk wipes of real movement.**
> - **`jaw_pass_qc` rates essentially preserved cohort-wide**:
>   severe-acute 0.675 → 0.674 (0.1% flip); worst cell is moderate /
>   pre at 5.5% flip. **The mismatch-classifier dissociation
>   narrative is stable** — `candidate_no_lick_with_jaw_move` count
>   shifts by ≤ 5.5% in any cell.
> - **Severe-acute / mod-sev-acute essentially unchanged**: prod 11.2
>   → clean 10.9 px (no biological-signal change).
> - **BUT Y-ceiling = 80 still clips real licking peaks in healthy
>   cells**. Mild cells drop 23-26% in cohort mean (clean median
>   clamps at ~79 px in every mild cell — exactly at the ceiling).
>   Per-trial PS55 / 5-14 / t033 L collapsed 183 → 78 px because real
>   licking peaks were clipped at 80.
>
> **Open design question for Phase 7f kickoff**: is the mild-cell
> cohort shift acceptable (could be capturing genuine artifact
> contamination of healthy peaks), OR should Y-ceiling be raised
> (150-200 px), or made per-phenotype, or replaced with an
> `lk >= 0.5` per-frame requirement at peak-picking?
>
> Phase 7f Task 1 should empirically calibrate Y-ceiling via a
> per-phenotype `y99` sweep on lk≥0.85 high-confidence raw DLC, with
> sensitivity analysis on `candidate_no_lick_with_jaw_move` rate.

> **AMENDMENT 2026-05-26 #4 (cleanup-simulation audit — Y-ceiling
> recalibration needed).** Scoping audit #3 (22,363 trials,
> §3.8) applied the candidate cleanup
> (`Y_ceiling = 75 px` + `cluster_mean_lk ≥ 0.85`) and revealed:
>
> - **Severe-acute cohort mean barely moves** (11.2 → 10.9 px, −3%).
>   13% of severe-acute trials have their peak wiped to NaN
>   entirely; the surviving 87% still average ~11 px — the paper-
>   narrative biological signal is preserved.
> - **Sign-flip rate at severe-acute drops 9.5% → 4.1%** (clear
>   improvement over prod audit #1).
> - **PS54 / 5-06 / t095 L (single-frame outlier) is correctly
>   wiped**: 125 px → 9.7 px after cleanup. ✓
> - **BUT mild epochs drop 27-31% in cohort mean** because real jaw
>   licking peaks in healthy mice reach 100-180 px, exceeding the
>   75 px ceiling. The cleanup median peak_abs_clean clamps to
>   ~74.9 px in every mild cell — exactly at the ceiling. Real
>   movement is being wiped along with artifacts.
> - **PS55 / 5-14 / t033 L (active licking with multiple real
>   peaks) collapses from 183 px to 71 px** — real licking peaks
>   wiped indiscriminately with artifact peaks.
> - **Single-frame outliers below 75 px escape cleanup** (PS54 /
>   5-01 / t013 R: cleanup picked a 72.8 px peak with `lk = 0.34`
>   inside the artifact-cluster region; Rule 2's `cluster_len ≥ 2`
>   guard excluded this single-frame mid-lk spike).
>
> **Revised guidance for Phase 7f kickoff:**
>
> 1. **Y_ceiling = 75 is too tight** — needs recalibration. Three
>    options:
>    - **Option (i)**: Remove Y-ceiling entirely; rely on cluster-LK
>      + frame-outlier rules alone.
>    - **Option (ii)**: Raise to ~200 px (well above healthy active-
>      licking peaks; only catches extreme outliers).
>    - **Option (iii)**: Per-phenotype Y-ceiling (e.g., 75 for
>      severe, 250 for mild). More invasive; requires phenotype
>      lookup in jaw_pertrial.
> 2. **Cluster-mean-lk gate at 0.85 is doing useful work** —
>    catches the cluster artifacts in severe-acute (40.9% wipe
>    rate in mod-sev-acute, 27.8% in severe-acute). Keep.
> 3. **Add Rule 3: frame-level outlier wipe** (tongue v7
>    Decision 12 analog): single frames where
>    `|y - local_median ±20ms| > FRAME_JUMP_THR_JAW` (calibrate;
>    suggest 80-100 px). Catches PS54 t095-style single-frame spikes
>    that Rule 2's length ≥ 2 guard excludes.
>
> The cleanup ARCHITECTURE (cluster-LK + Y-ceiling + frame-outlier)
> is correct per Addenda #2 and #4. The constants need an iteration
> in Phase 7f Task 1 (likely with a visual-gate review on the
> 8 severe-acute renders + a healthy-baseline sanity check on the
> mild-acute / mild-pre cohort means).

> **AMENDMENT 2026-05-26 #3 (interpolation audit findings).** Scoping
> audit #2 (jaw v5p3 interpolation quality, 1.9 M gap records across
> 8-animal × 2-bodypart cohort, full results §3.7) produced a
> **surprising finding that revises Addendum #1 point 3 (interpolation
> gap-fill tuning)**:
>
> - **Median jaw PCHIP gap = 8 ms cohort-wide** (p90 ≤ 68 ms in every
>   phenotype × epoch cell). ≤ 1.9% of PCHIP fills bridge gaps near
>   the 120 ms cap.
> - **Median severe-acute trial has ZERO gap-fills inside detect
>   window.** Mild-acute (active licking) has 12.4 gap fills per
>   trial on average. **Active-licking sessions, not severe-acute, are
>   what would be affected by a tighter cap.**
> - **For the 8 severe-acute artifact trials**: 5/8 have substantial
>   baseline-fill (5-41% of detect window) — but those frames are
>   already at Stage 5 (gaps > 120 ms; PCHIP couldn't bridge them).
>   The artifact PEAK is on a raw DLC frame ADJACENT to the
>   baseline-fill band, not on a gap-fill frame.
>
> **Net effect on §6 Option B scope:** the v5p3 `max_gap_ms` parameter
> review is **no longer recommended as a primary lever** for the
> cleanup. Tightening to e.g. 60 ms would flip 26% of currently-PCHIP
> frames to baseline-fill, but those flips would mostly land in
> mild/moderate active-licking trials (where short PCHIP fills bridge
> real lick onsets/offsets). That's counterproductive.
>
> **The v5p3 re-emit Priya locked in Addendum #2 still happens** — but
> the v5p3 changes should target different parameters (candidates for
> kickoff): lk_thr tightening (currently 0.50; consider 0.70-0.85),
> n_neigh tightening (currently 3 frames in ±16 ms; consider 5),
> and/or a new Stage-3 cluster-likelihood filter (drop raw clusters
> with mean lk < threshold). `max_gap_ms` stays at 120 ms or modestly
> tightens to ~90 ms (which would flip < 8% of PCHIP frames).
>
> Addendum #2's cluster-classifier-without-shape-rule design + hard
> Y-ceiling are **unchanged** by this finding; those still apply at
> the jaw_pertrial layer.

> **AMENDMENT 2026-05-26 #2 (Priya — cluster-classifier scope + v5p3
> re-emit lock).** Two corrections to Addendum #1:
>
> 1. **Drop tongue v7 Rule A (intra-cluster shape gate) for jaw.**
>    Tongue's Rule A (Phase 7e Decision 9) keeps clusters where
>    `cluster_min < 80 OR cluster_range > 50` — it KEEPS only clusters
>    that span baseline-to-peak (real lick shape) and WIPES clusters
>    flat at high y (plateau artifact). This does NOT translate to
>    jaw: **real jaw trajectories can look "flat" at sustained high-y
>    postures**, so a shape-based filter would falsely wipe real jaw
>    activity. Phase 7f must invent a jaw-appropriate cluster
>    discriminator. Candidate criteria for kickoff exploration:
>    - **Cluster contiguity / duration:** real jaw movement is
>      contiguous (PS54 t013 from ~1300 ms onwards); artifact clusters
>      are short and surrounded by Stage-5 baseline-fill bands within
>      the same trial.
>    - **Mean / median likelihood within the cluster:** real jaw
>      activity sustains `lk > 0.85`; artifact clusters tend toward
>      `lk = 0.3-0.5`. Cluster-mean-lk gate may be a better
>      discriminator than per-frame lk gates.
>    - **Hard Y-ceiling + frame-level outlier wipe** (Rules 1 and 3
>      from Addendum #1) port cleanly and are NOT affected by this
>      revision.
>    - **Isolated-short override** (Phase 7e Decision 11) likely still
>      applies — short isolated clusters surrounded by long baseline-
>      fill are artifacts in both tongue and jaw, regardless of shape.
> 2. **Jaw v5p3 re-emit is desired.** Priya 2026-05-26 explicitly
>    wants a cohort jaw v5p3 re-emit after the cleanup. This **locks
>    Option B (`bodypart-parametric v7 port` with cohort v5p3
>    re-emit) as the chosen architecture**, NOT Option A. Option A's
>    "all logic inside `jaw_pertrial.py`, no v5p3 re-emit" framing is
>    now obsolete; treat it as a fallback only if Option B is
>    infeasible. Phase 7f kickoff scope expands to include v5p3
>    `max_gap_ms` review + per-bodypart preclean constants.
>
> **Net effect on §5 verdict:** scope firmly in the bodypart-
> parametric v7 port tier (Option B). Cluster classifier needs a
> jaw-specific rule set, NOT a direct tongue port. Wall-time stays
> ~2-3 weeks CC; the cluster-discriminator design phase may add 1-3
> days at the front for empirical exploration on the audit
> visual-render set. Q-1 in §7 is now answered (Option B locked);
> Q-2 + Q-3 still open.

---

## 1. Context + motivation

Phase 7e (merged 2026-05-26 at `027f063`, tag `v7e-dlc-tongue-preclean-v7`)
introduced the v7 pre-clean + detector + gates pipeline for tongue
kinematics. Phase 7e DECISIONS 2026-05-25 Decision 8 explicitly deferred
the jaw analog: *"The v7 architecture … generalizes to jaw kinematics
but all parameters … are tongue-specific. Priya 2026-05-25 deferred jaw
work until after Phase 7e tongue migration lands in production and
downstream effects are validated."*

Tongue is now landed; the cohort re-emit + downstream stats
regeneration is in flight via Event B
(`chore/phase-7e-cohort-reemit`, PR #135) on a separate session.

**Why jaw matters.** Memory finding #7 records that the jaw spatial
Wasserstein endpoint `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
carries the strongest confirmatory signal in the Phase 9 cohort
(`q ≈ 9e-15`). The recovery_trajectories endpoint list in
[`notebooks/01_spout_behavior_figures.ipynb`](../../notebooks/01_spout_behavior_figures.ipynb)
treats it as a paper-figure-grade scalar. If the jaw v5p3 trace or its
downstream peak-deflection scalars have artifactual patterns analogous
to tongue's PCHIP-anchored-spike-against-Stage-5-baseline-fill, the
paper narrative around jaw movement may need to be revised. This audit
is a read-only scoping exercise to establish whether the concern is
real.

**Critical scope split.** Two distinct jaw data products consume
different upstream:

| Consumer | Upstream | Lk gate | Stage-5 fill applies? |
| --- | --- | --- | --- |
| `dlc_spatial.heatmaps` → `spatial_wasserstein_jaw_*` | raw DLC frames | `0.80` | **no** (frames below gate are dropped, not filled) |
| `jaw_pertrial.py` (8 scalars) → `tongue_jaw_mismatch.candidate_no_lick_with_jaw_move` | v5p3 `y_final` interpolated trace | `0.50` (Stage 2) | **yes** (Stage 5 fills with `Y0 = resting jaw position`) |

→ **The headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
endpoint is NOT directly affected by a hypothetical v5p3 cleanup** —
it consumes the lk≥0.80 raw-frame heatmap. Any Phase 7f cleanup
scope therefore targets the `jaw_pertrial` scalar family + the
mismatch classifier's `jaw_pass_qc` gate, NOT the headline Wasserstein.

---

## 2. Jaw pipeline (read-only audit findings)

Production jaw pipeline (per
[src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py](../../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py)
+ [interpolation.py](../../src/stroke_orofacial/dlc_kinematics/interpolation.py)):

1. **Stage 1-3 (raw → drop):** X-range filter (±75 px around midline,
   `lk` source), likelihood threshold (`lk_thr = 0.50`), isolated-hi-lk
   neighbor filter (`n_neigh = 3`, `neighbor_ms = 16`).
2. **Stage 4 (short-gap fill):** PCHIP (fallback linear) for gaps
   ≤ `max_gap_ms = 120` (vs. tongue's 56 ms — jaw is allowed twice the
   gap width).
3. **Stage 5 (baseline fill):** all remaining NaNs filled with the
   forced baseline `(X0, Y0)` from `animals.yaml kinematics_baselines`.
   These frames are stamped `is_baseline_fill = True` + `fill_method = 3`.
4. **Stage 6 (subtract baseline):** final per-frame `y_final = y - Y0`
   (so resting-position frames have `y_final ≈ 0`).
5. **jaw_pertrial:** per-trial scalars consume `y_final` directly. No
   pre-clean, no detector, no gates. Single quantity = `argmax(|y_final -
   baseline_mean|)` inside `[0, 5000] ms`.

**Key contrast vs. tongue.** Tongue's lick artifacts (the v7
motivation) arose because (a) tongue ranges from `y ≈ 0` at rest to
`y ≈ 200` at peak licking — a large dynamic range; (b) DLC sparsity was
10-21% in the severe-acute phenotype, meaning peaks would frequently
fall on PCHIP-anchored frames adjacent to Stage-5-baseline-fill troughs.
Jaw has both a smaller dynamic range AND a dramatically higher detection
rate (see §3.3 below).

---

## 3. Audit findings

> All numbers below are from
> [`.scratch_phase_7f_scoping/audit_results/`](../../.scratch_phase_7f_scoping/audit_results/).
> Audit script:
> [`.scratch_phase_7f_scoping/audit_jaw_quality.py`](../../.scratch_phase_7f_scoping/audit_jaw_quality.py).
> Run date: 2026-05-26. Cohort: 8 primary-cohort animals; Pattern B
> (secondary-spout) sessions excluded per Event B Addendum #1.

### 3.1 Cohort coverage

**231 sessions × 22,363 trials** processed. Phenotype × epoch breakdown
at
[`by_phenotype_epoch.csv`](../../.scratch_phase_7f_scoping/audit_results/by_phenotype_epoch.csv).

### 3.2 (a) Likelihood-at-peak distribution

For each per-trial argmax-|defl| peak frame, the audit reads the raw
DLC likelihood at that exact frame. Headline figure:
[`lk_at_peak_hist.png`](../../.scratch_phase_7f_scoping/audit_results/lk_at_peak_hist.png).

| phenotype / epoch | n_trials | median lk@peak | frac lk<0.5 | frac lk<0.85 |
| --- | --- | --- | --- | --- |
| mild / pre        | 2581 | 0.840 | 0.001 | 0.520 |
| mild / acute      | 408  | 0.801 | 0.000 | 0.635 |
| mild / sub_acute  | 1144 | 0.814 | 0.001 | 0.594 |
| mild / chronic    | 3856 | 0.832 | 0.002 | 0.542 |
| moderate / acute  | 479  | 0.837 | 0.000 | 0.524 |
| mod-sev / acute   | 384  | 0.857 | 0.005 | 0.469 |
| **severe / acute** | **2316** | **0.875** | **0.013** | **0.405** |
| severe / sub_acute | 2833 | 0.790 | 0.003 | 0.572 |
| severe / chronic  | 1672 | 0.688 | 0.001 | 0.733 |
| severe / pre      | 1056 | 0.840 | 0.024 | 0.516 |

**Interpretation.** Median lk-at-peak is **above 0.69 in every cell**
and above 0.80 in 14/16 cells. `frac lk<0.5` is bounded by 2.4% in any
cell. **No phenotype × epoch cell shows tongue-like low-confidence peak
contamination at the cohort level.**

### 3.3 (b) Detection rate / sparsity

Fraction of detect-window (`[0, 5000] ms`) frames with raw
`likelihood_raw > 0.5` AND fraction `is_baseline_fill = True`.

| phenotype / epoch | mean frac raw above prod | mean frac baseline-fill | mean frac interp-fill |
| --- | --- | --- | --- |
| mild / acute      | **0.945** | 0.001 | 0.057 |
| mild / pre        | 0.938 | 0.001 | 0.063 |
| mild / sub_acute  | 0.943 | 0.002 | 0.057 |
| mild / chronic    | 0.938 | 0.002 | 0.062 |
| moderate / acute  | 0.868 | 0.016 | 0.118 |
| moderate / pre    | 0.883 | 0.002 | 0.116 |
| mod-sev / acute   | **0.996** | 0.002 | 0.003 |
| mod-sev / chronic | 0.961 | 0.005 | 0.036 |
| **severe / acute** | **0.986** | 0.005 | 0.010 |
| severe / pre      | 0.898 | 0.017 | 0.090 |
| severe / sub_acute | 0.942 | 0.002 | 0.058 |
| severe / chronic  | 0.935 | 0.000 | 0.067 |

**Headline:** detection rate is **87-99% across every phenotype × epoch
cell**. Compare to tongue Part 1 which reported 10-21% in
severe-acute. **Jaw has roughly 5-10x more raw DLC frames than tongue
in the same epoch.** Baseline-fill within the detect window averages
≤ 1.7% in every cell. This is the dominant qualitative finding — jaw is
not subject to the structural sparsity problem that motivated tongue v7.

### 3.4 (c) Counterfactual likelihood-gate analysis

At lk gates `{0.5, 0.7, 0.85, 0.9}`, peaks were recomputed by masking
all frames below the gate (no spline / parabolic imputation — the
audit just reports the surviving local maximum). Full table:
[`counterfactual_means.csv`](../../.scratch_phase_7f_scoping/audit_results/counterfactual_means.csv).

Mean `|peak deflection|` (px) by gate for the load-bearing cells:

| phenotype / epoch | prod | lk≥0.5 | lk≥0.7 | lk≥0.85 | lk≥0.9 | Δ@lk≥0.9 |
| --- | --- | --- | --- | --- | --- | --- |
| mild / acute      | 100.4 | 100.4 | 96.1 | 94.3 | 93.0 | **−7%** |
| moderate / acute  | 89.1  | 89.1  | 85.9 | 84.0 | 83.5 | **−6%** |
| mod-sev / acute   | 11.34 | 11.34 | 10.96 | 10.08 | 9.35 | **−18%** |
| **severe / acute** | **11.20** | 11.20 | 10.76 | 10.08 | **9.54** | **−15%** |
| severe / chronic  | 74.8 | 74.8 | 69.7 | 64.8 | 62.3 | **−17%** |
| severe / pre      | 101.2 | 101.2 | 96.0 | 91.9 | 91.0 | **−10%** |

**Interpretation.** The dominant biological signal — severe-acute and
mod-sev-acute jaw deflection collapse to ~11 px (one order of magnitude
below all other phenotype × epoch cells) — is **robust to the lk gate
choice**. At lk≥0.9 (vs. prod), the cohort mean drops by 6-18%; the
ranking of cells is preserved.

The 13-15% drops in severe-acute and severe-chronic suggest the cohort
means carry a small per-cell contamination from low-confidence frames,
but this does not change the qualitative narrative (severe-acute jaw is
~10x smaller than severe-pre / mild epochs).

### 3.5 Sign-flip analysis (per-trial robustness)

For each gate, fraction of trials whose argmax-|defl| **changes
sign** when low-confidence frames are masked. Full table:
[`sign_flip_flags.csv`](../../.scratch_phase_7f_scoping/audit_results/sign_flip_flags.csv).

| gate     | severe / acute | mod-sev / acute | mild / acute |
| ---      | --- | --- | --- |
| lk ≥ 0.5 | 0.001 | 0.000 | 0.000 |
| lk ≥ 0.7 | 0.022 | 0.029 | 0.010 |
| lk ≥ 0.85 | 0.065 | 0.091 | 0.007 |
| lk ≥ 0.9 | **0.095** | **0.136** | 0.015 |

**Interpretation.** Sign flip rates at the tightest gate are **highest
in the two phenotype × epoch cells with the smallest cohort-mean
deflection** (severe-acute, mod-sev-acute, both ~11 px). This is
consistent with the mean-deflection floor sitting in the
single-frame-outlier noise band — at ~11 px the difference between
"max positive" and "max negative" deflection is small, so any
single-frame outlier flips the sign. In cells with larger mean
deflection (mild epochs ≥ 90 px), sign flips are essentially absent.

### 3.6 (d) Stage-5-baseline-fill prevalence at peaks

For the trial argmax-|defl| peak frame: was that frame
`is_baseline_fill = True` (Stage-5 forced fill)? Full table:
[`stage5_fill_prevalence.csv`](../../.scratch_phase_7f_scoping/audit_results/stage5_fill_prevalence.csv).

| phenotype / epoch | frac peak at baseline-fill | mean frac detect-win baseline-fill | max frac detect-win baseline-fill |
| --- | --- | --- | --- |
| mild / acute      | 0.000 | 0.001 | 0.071 |
| mild / chronic    | 0.000 | 0.002 | 0.416 |
| mod-sev / acute   | 0.005 | 0.002 | 0.369 |
| severe / acute    | **0.014** | 0.005 | 0.679 |
| severe / pre      | **0.024** | 0.017 | 0.624 |
| severe / sub_acute | 0.002 | 0.002 | 0.680 |
| severe / chronic  | 0.001 | 0.000 | 0.157 |

**Interpretation.** Peak-at-baseline-fill is bounded by **2.4% in any
cell** (severe-pre worst case); 1.4% in severe-acute. **The Stage-5
forced-fill mechanism that produced tongue's PCHIP-anchored-spike
artifacts is essentially never invoked at the jaw argmax peak.**
Cohort-wide, mean baseline-fill within the detect window is < 2% in
every cell.

The non-zero `max frac detect-win baseline-fill` values (e.g., 0.68 in
some severe-acute trials) confirm that occasional sessions experience
extended baseline-fill stretches; but these are individual trials, not
a cohort pattern, and they do not coincide with the argmax peak in the
vast majority of cases.

### 3.7 Interpolation gap-fill characteristics (audit #2)

Phase 7f scoping audit #2 (run 2026-05-26) characterized the Stage-4
PCHIP-fallback-linear gap-fill mechanism. Audit script:
[`.scratch_phase_7f_scoping/audit_jaw_interpolation.py`](../../.scratch_phase_7f_scoping/audit_jaw_interpolation.py).
1.9 M gap records across 8-animal × 2-bodypart cohort
(jaw + tongue reference). Outputs at
[`.scratch_phase_7f_scoping/audit_results/interpolation/`](../../.scratch_phase_7f_scoping/audit_results/interpolation/).

**(a) PCHIP gap-length distribution.** Across all phenotype × epoch
cells, jaw PCHIP/LINEAR fills are dominated by short gaps:

| cell | median PCHIP gap (ms) | p90 PCHIP gap (ms) | max PCHIP gap (ms) | frac PCHIP gaps near cap (> 96 ms) |
| --- | --- | --- | --- | --- |
| jaw mild / acute      |  8 | 52 | 120 | 0.9% |
| jaw moderate / acute  | 16 | 68 | 120 | 1.9% |
| jaw mod-sev / acute   |  8 | 32 | 120 | 1.4% |
| jaw **severe / acute** |  8 | 48 | 120 | **1.6%** |
| jaw severe / chronic  |  8 | 52 | 120 | 0.5% |
| jaw severe / pre      |  8 | 52 | 120 | 1.2% |
| tongue **severe / acute** |  8 | 32 |  56 | **3.8%** |
| tongue mild / chronic |  8 | 48 |  56 | 10.6% |

Headline: **median jaw PCHIP gap = 8 ms cohort-wide**; ≤ 2% of jaw
PCHIP fills bridge gaps near the 120 ms cap. Tongue's PCHIP
distribution is qualitatively similar — most fills short, with a small
tail at the cap. Tongue's cap-tail fraction is higher in % because the
56 ms cap clips a wider real distribution; tongue at 120 ms would
likely also see only ~1-3% at the new cap.

**(b) Counterfactual max_gap_ms.** If the jaw v5p3 cap were tightened,
fraction of currently-PCHIP-filled frames that would flip to
Stage-5 baseline-fill:

| tightened cap (ms) | n gaps flipped | n frames flipped | frac of PCHIP frames flipped |
| --- | --- | --- | --- |
|  30 | 204 860 | 2 737 177 | **66.3%** |
|  60 |  53 530 | 1 064 465 | **25.8%** |
|  90 |  12 189 |   316 022 |  **7.7%** |
| 120 (prod) | 0 | 0 | 0% |

Tightening to tongue's 56 ms would flip ~26% of currently-PCHIP
frames. **But these are mostly in active-licking sessions
(mild/moderate epochs), not severe-acute** — see (c) below.

**(c) Per-trial gap structure inside detect window.** Distribution of
the maximum gap-fill duration inside `[0, 5000]` ms across trials:

| cell | n_trials | mean n_gaps in detect | p50 max_gap (ms) | p90 max_gap (ms) | mean frac PCHIP | mean frac baseline |
| --- | --- | --- | --- | --- | --- | --- |
| mild / acute       |  408 | 12.4 | 56 |  92 | 5.7% | 0.1% |
| moderate / acute   |  479 | 15.7 | 76 | 112 | 11.8% | 1.6% |
| mod-sev / acute    |  384 |  1.1 |  0 |  16 |  0.3% | 0.2% |
| **severe / acute** | 2316 |  3.1 | **0** | 68 |  1.0% | 0.5% |
| severe / sub_acute | 2833 | 13.2 | 60 |  92 | 5.8% | 0.2% |
| severe / chronic   | 1672 | 16.3 | 56 |  84 | 6.7% | 0.0% |
| severe / pre       | 1056 | 24.7 | 68 | 158 | 9.0% | 1.7% |

**Surprising finding:** **the median severe-acute trial has ZERO gap
fills in its detect window.** Severe-acute mice are mostly
not-licking (the dominant biological signal), so DLC has nothing
moving to lose track of — long contiguous raw-DLC stretches dominate.
The artifacts live in the **upper tail** of the severe-acute
distribution.

By contrast, **mild-acute (active licking)** has 12.4 gap fills per
trial on average, with p50 max_gap = 56 ms — the active licking causes
DLC tracking blips at lick onsets/offsets. Tightening
`max_gap_ms` would primarily affect THESE active-licking trials, not
the severe-acute artifact cases.

**(d) Per-artifact-trial gap context.** For the 8 hand-picked
severe-acute renders (full table:
[`artifact_trial_gap_table.csv`](../../.scratch_phase_7f_scoping/audit_results/interpolation/artifact_trial_gap_table.csv)):

| trial | n_gaps | max_gap_ms | frac PCHIP | frac baseline | artifact mechanism |
| --- | --- | --- | --- | --- | --- |
| PS55 / 5-14 / t033 L | 36 | 428 | **18.9%** | **41.2%** | Real licking + long baseline-fill bands between licks; low-lk peaks at the licking events |
| PS54 / 5-01 / t013 R | 14 | 428 | 5.0% | 16.1% | High-y cluster from 0-1200ms bracketed by baseline-fill; real licking starts ~1300ms |
| PS54 / 5-05 / t010 L | 18 | 292 | 2.6% | 21.3% | Mixed |
| **PS54 / 5-06 / t095 L** | **11** | **52** | 3.6% | **0.0%** | **Pure single-frame outlier on raw DLC; NO gap-fill involvement** |
| PS55 / 5-06 / t002 L | 21 | 488 | 6.0% | 26.7% | Real licking + baseline-fill bands |
| PS55 / 5-09 / t021 L | 12 |  84 | 6.7% |  0.0% | Mid-confidence single-frame; small gaps |
| PS54 / 5-09 / t006 L | 30 | 156 | **14.9%** | 6.1% | Heavy gap activity (active session) |
| PS55 / 5-17 / t003 R | 19 |  40 | 5.6% |  0.0% | High-lk real movement; small gaps |

**Key takeaway:** **the largest-|defl| artifact peaks ARE adjacent to
baseline-fill bands** (6/8 trials have non-zero baseline-fill in
detect window; 5/8 have substantial baseline-fill > 5%), but the
artifact PEAK itself is on a raw DLC frame, NOT on a gap-fill frame.
**The baseline-fill bands are gaps THAT EXCEEDED the 120 ms cap** —
they already fell through to Stage 5. Tightening max_gap_ms wouldn't
change them (they're already baseline-filled). The PCHIP fills that
WOULD have flipped are the short ones (< 120 ms) that bridge real
licking onsets/offsets in active-licking trials.

**Conclusion:** **v5p3 `max_gap_ms` tightening has limited leverage on
the jaw artifact problem.** The artifact mechanism is at the raw-DLC
level (mid-confidence frames with outlier y at the edges of
baseline-fill bands), not at the gap-fill level. Tightening would
mostly affect active-licking sessions (mild/moderate epochs) where
short PCHIP fills bridge real movement transients — likely
counterproductive.

### 3.8 Cleanup simulation (Y-ceiling + cluster-mean-lk filter)

Phase 7f scoping audit #3 (run 2026-05-26) applied a candidate
post-v5p3 cleanup in-memory and recomputed the per-trial peak
metrics. Audit script:
[`.scratch_phase_7f_scoping/audit_jaw_cleanup_sim.py`](../../.scratch_phase_7f_scoping/audit_jaw_cleanup_sim.py).
22,363 trials across 8-animal cohort. Outputs at
[`.scratch_phase_7f_scoping/audit_results/cleanup_sim/`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim/)
+ visual renders at
[`.scratch_phase_7f_scoping/visual_renders_cleanup/`](../../.scratch_phase_7f_scoping/visual_renders_cleanup/).

**Cleanup rules applied:**
1. **Y-ceiling (Rule 1):** any frame with
   `(y_final − baseline_mean) > 75 px` → wiped to NaN (positive side
   only; negative jaw deflections are physiological).
2. **Cluster-mean-lk (Rule 2):** for each contiguous raw cluster
   (`fill_method == 0`) of length ≥ 2, if `mean(likelihood_raw) <
   0.85`, wipe the whole cluster to NaN.

After cleanup: `argmax(|y_clean − baseline_mean|)` over detect window;
wiped frames are NaN and excluded from argmax.

**Cohort means (full table:
[`by_phenotype_epoch_cleanup.csv`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim/by_phenotype_epoch_cleanup.csv);
visual:
[`cohort_mean_delta_bar.png`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim/cohort_mean_delta_bar.png)):**

| cell | prod mean | clean mean | Δ | wipe Y | wipe LK | peak→NaN rate |
| --- | --- | --- | --- | --- | --- | --- |
| mild / pre        | 102.6 | 74.2 | **−28%** | 21.9% | 7.7% | 0.04% |
| mild / acute      | 100.4 | 73.2 | **−27%** | 17.6% | 9.9% | 0.0% |
| mild / chronic    | 105.8 | 73.9 | **−30%** | 22.4% | 7.3% | 0.0% |
| moderate / acute  | 89.1 | 66.4 | **−25%** | 16.0% | 4.8% | 0.0% |
| **mod-sev / acute** | **11.3** | **10.2** | **−10%** | 0.0% | **40.9%** | **19.8%** |
| mod-sev / pre     | 106.4 | 74.5 | −30% | 24.3% | 6.1% | 0.0% |
| **severe / acute** | **11.2** | **10.9** | **−3%** | 0.01% | **27.8%** | **13.0%** |
| severe / chronic  | 74.8 | 64.3 | −14% | 1.7% | 10.0% | 0.06% |
| severe / pre      | 101.2 | 72.5 | −28% | 15.2% | 28.1% | 0.28% |
| severe / sub_acute | 65.6 | 54.1 | −18% | 2.5% | 11.2% | 0.92% |

**Sign-flip rates** (peak signed prod vs cleanup): severe-acute **drops
from 9.5% (lk≥0.9 counterfactual in audit #1) to 4.1% (cleanup)**.
Mod-sev acute drops from 13.6% to 7.1%. Improvement.

**Two failure modes visible:**

**(F1) Y-ceiling = 75 is TOO TIGHT for healthy/active-licking sessions.**
Mild epochs drop 27-31% in cohort mean because **real licking peaks
exceed 75 px in healthy mice**. The cleanup `median peak_abs_clean`
clamps to ~74.9 in every mild cell — exactly at the ceiling. Per
`audit #1` the prod median was 102-106 px. The Y-ceiling is wiping
real movement, not artifact. **Recommend raising Y-ceiling
substantially (≥ 200 px, or per-phenotype) OR removing entirely +
relying on cluster-LK + a frame-level outlier rule.**

**(F2) Single-frame outliers below Y-ceiling escape cleanup.** Rule 2
excludes clusters of length 1 (by design — single frames don't have
intra-cluster mean lk). A single-frame outlier with `y_final = 60` and
`lk = 0.5` passes both rules. Visible in PS54 / 2025-05-01 / t013 R:
the cleanup picked a 72.8 px peak at `t = 476 ms` with `lk = 0.34`,
inside the artifact-cluster region — the cleanup couldn't reach it
because the Y-ceiling didn't fire AND the surrounding cluster wasn't
contiguous-and-low-LK enough. **Recommend adding a frame-level
outlier wipe (tongue v7 Decision 12 analog: `|y - local_median ±20ms|
> threshold`) as Rule 3.**

**Per-trial visual renders** ([`visual_renders_cleanup/*.png`](../../.scratch_phase_7f_scoping/visual_renders_cleanup/)):

| trial | prod |defl| | clean |defl| | verdict |
| --- | --- | --- | --- |
| PS54 / 5-06 / t095 L (single-frame outlier) | 125 | **9.7** | **Cleanup works** — wipes the spike, finds reasonable post-spike peak |
| PS55 / 5-14 / t033 L (active licking + bands) | 183 | 71.2 | **Real licking peaks wiped** — Y-ceiling too tight |
| PS54 / 5-01 / t013 R (cluster artifact) | 138 | 72.8 | **Partial** — wipes the worst spike but lands on still-suspect 72.8 frame |

**Conclusion:** the cleanup architecture (cluster classifier +
likelihood-based filter + per-frame rules) is the right direction.
**The specific constants need recalibration**: `Y_CEILING = 75 px` is
too tight; `cluster_lk gate = 0.85` is doing useful work; need to add
a frame-level outlier rule (Rule 3) for single-frame mid-confidence
spikes. Recalibration candidates for kickoff: Y-ceiling ≥ 200 px (or
per-phenotype, or removed), frame-jump threshold ~80-100 px from
local median over ±20-30 ms.

### 3.9 Cleanup simulation v2 (likelihood-free, per Priya direction)

Phase 7f scoping audit #4 (run 2026-05-26) dropped the cluster-mean-lk
gate per Priya 2026-05-26 ("we should keep likelihood threshold at 0.5"
+ visual review of v1 wiping ~99% of real movement). Replaced with
likelihood-free rules ported from tongue v7 (jaw-recalibrated). Audit
script:
[`.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v2.py`](../../.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v2.py).
22,363 trials. Outputs at
[`.scratch_phase_7f_scoping/audit_results/cleanup_sim_v2/`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v2/)
+ renders at
[`.scratch_phase_7f_scoping/visual_renders_cleanup_v2/`](../../.scratch_phase_7f_scoping/visual_renders_cleanup_v2/).

**Cleanup rules applied (v2):**
1. **R1 Y-ceiling = 80 px** (relaxed from v1's 75 per Priya direction).
2. **R2 Isolated-short cluster wipe**: raw clusters of length ≤ 5
   frames AND no other raw cluster within ±30 ms → wipe.
3. **R3 Frame-level outlier wipe**: within each kept raw cluster,
   frames where `|y - rolling_median(±20ms)| > 80 px` → wipe.
   Vectorized via `scipy.ndimage.median_filter`.
4. **R4 PCHIP-extend wipe**: adjacent `is_interp_fill` frames within
   ±40 ms of any wiped frame → wipe.

**NO cluster-mean-lk filter.** Production v5p3 Stage 2 `lk_thr=0.5`
gate stays as-is per Priya 2026-05-26.

Also tracks **`jaw_pass_qc` (the mismatch classifier input)** per-trial
in addition to peak metrics.

**Cohort means (full table:
[`by_phenotype_epoch_cleanup_v2.csv`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v2/by_phenotype_epoch_cleanup_v2.csv); plot:
[`cohort_mean_delta_bar_v2.png`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v2/cohort_mean_delta_bar_v2.png)):**

| cell | prod peak | clean peak | Δ peak | prod pass_qc | clean pass_qc | Δ pass_qc | any wipe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mild / pre        | 102.6 | 78.8 | **−23%** | 0.915 | 0.906 | −0.9% | 17.6% |
| mild / acute      | 100.4 | 77.6 | **−23%** | 0.892 | 0.887 | −0.5% | 14.4% |
| mild / chronic    | 105.8 | 78.5 | **−26%** | 0.913 | 0.899 | −1.4% | 18.3% |
| mild / sub_acute  | 106.7 | 78.4 | **−26%** | 0.907 | 0.894 | −1.3% | 17.1% |
| moderate / acute  | 89.1 | 69.9 | **−21%** | 0.843 | 0.825 | −1.9% | 13.4% |
| moderate / pre    | 87.9 | 73.3 | **−17%** | 0.608 | 0.553 | **−5.5%** | 8.0% |
| **mod-sev / acute** | **11.3** | **11.3** | **−0.5%** | 0.823 | 0.823 | 0.0% | 0.01% |
| mod-sev / pre     | 106.4 | 79.4 | **−25%** | 0.977 | 0.974 | −0.3% | 19.9% |
| mod-sev / chronic | 94.7 | 75.7 | **−20%** | 0.853 | 0.840 | −1.3% | 7.4% |
| **severe / acute** | **11.2** | **10.9** | **−2%** | 0.675 | 0.674 | −0.1% | 0.05% |
| severe / pre      | 101.2 | 76.8 | **−24%** | 0.774 | 0.745 | −2.8% | 12.9% |
| severe / chronic  | 74.8 | 67.0 | **−10%** | 0.798 | 0.776 | −2.2% | 1.0% |
| severe / sub_acute | 65.6 | 56.2 | **−14%** | 0.799 | 0.782 | −1.7% | 1.6% |

**Wipe-by-rule breakdown** (mean per-trial detect-window fraction; full table:
[`wipe_prevalence_v2.csv`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v2/wipe_prevalence_v2.csv)):

- **R1 Y-ceiling**: 0.01% (severe-acute) → 19.9% (mod-sev-pre). Does
  ALL of the wiping work in mild/moderate cells.
- **R2 isolated-short**: 0.001-0.001%. Fires rarely — jaw v5p3 has
  high detection rate so isolated short clusters bracketed by long
  baseline-fill are uncommon.
- **R3 frame-outlier**: 0.0% to ~0.0001%. Fires extremely rarely at
  cohort level — but **WHEN it fires, it nails the right frames**
  (per the visual renders below).
- **R4 PCHIP-extend**: 0.0001-0.3%. Follows R1/R2/R3 wipes.

**Per-artifact-trial visual results** (full set:
[`visual_renders_cleanup_v2/*.png`](../../.scratch_phase_7f_scoping/visual_renders_cleanup_v2/)):

| trial | prod |defl|, qc | clean |defl|, qc | fired | verdict |
| --- | --- | --- | --- | --- |
| **PS54 / 5-06 / t095 L** (single-frame outlier) | 125 / qc=True | **9.7 / qc=True** | **R3 n=1** | **Cleanup works perfectly** — R3 nails the single-frame spike, rest of trace preserved (1454 raw kept) |
| PS55 / 5-14 / t033 L (active licking + bands) | 183 / qc=True | 77.9 / qc=True | R1 n=10, R2 n=20, R4 n=50 | **Real licking peaks clipped at Y-ceiling 80**; trace preserved (525 raw kept), qc unchanged |
| PS54 / 5-01 / t013 R (cluster artifact) | 138 / qc=True | 80.0 / **qc=False** | R1 n=18, R2 n=4 | **Cluster peaks clipped at ceiling**; post-1300ms real movement preserved (1106 raw kept); **but qc flipped to False** |
| PS55 / 5-17 / t003 R (clean real movement) | 88 / qc=True | clean preserved | minimal | **No mistreatment** of clean high-confidence trials |

**Conclusion (v2 vs v1):**

- **R3 frame-outlier wipe correctly catches single-frame spikes** (PS54
  t095: 125 → 9.7 px, R3 fires on 1 frame). Aggregate stats round to
  near-zero because they're truly rare events, but the rule IS doing
  its job per trial.
- **v2 preserves the trace MUCH better than v1** (e.g., PS55 t033 L:
  525 raw kept in v2 vs. 5 in v1).
- **`jaw_pass_qc` rates are essentially preserved cohort-wide**: max
  flip rate is 5.5% (moderate / pre); severe-acute is 0.1%. The
  mismatch-classifier input is stable — `candidate_no_lick_with_jaw_move`
  scientific dissociation evidence is preserved.
- **BUT: Y-ceiling = 80 still clips real licking in healthy/active
  cells.** Mild cells drop 23-26% in cohort mean. The clean median
  clamps to ~79 px in every mild cell — exactly at the ceiling.
- **Severe-acute / mod-sev-acute essentially unchanged**: prod 11.2 →
  11.3 px (no biological signal change).

**Remaining design question**: is the mild/moderate cohort-mean shift
(real licking peaks > 80 wiped) acceptable, OR should the Y-ceiling
be raised further (e.g., 150-200 px) to preserve those peaks? Trade-off:
raising the ceiling preserves real movement but lets some cluster
artifacts (PS54 t013 R-style pre-1300ms high-y clusters) survive into
the peak. Per the audit, R2/R3 don't catch those cluster artifacts
on their own (R2 fired only 4 frames on PS54 t013 R) — the Y-ceiling
is doing the heavy lifting there.

Options for Phase 7f kickoff:
- **(i)** Keep Y-ceiling at 80, accept the mild-cell shift (the shift
  may be capturing genuine artifact contamination of healthy peaks).
- **(ii)** Raise Y-ceiling to 150-200, weaken cluster-artifact capture.
- **(iii)** Per-phenotype Y-ceiling (80 for severe, 200 for mild) —
  requires phenotype lookup in jaw_pertrial.
- **(iv)** Add an `lk > 0.5` per-frame requirement at the peak-picking
  stage (Priya 2026-05-26 suggested this may come back) — gates the
  surviving max-deflection frame on the v5p3 lk being ≥ 0.5. Would
  need to also gate on PCHIP/baseline-fill frames being skipped.

### 3.10 Cleanup simulation v3 (pre-Stage-4, order-of-ops fix)

Phase 7f scoping audit #5 (run 2026-05-26) per Addendum #6 pivot:
exclusion rules applied at the RAW DLC level BETWEEN v5p3 Stage 3
(drop low-lk + isolated-hi-lk) and Stage 4 (PCHIP gap-fill). v3 then
re-PCHIP-interpolates from the cleaned raw set, so the resulting trace
bridges only across surviving anchors — never through wiped artifact
frames. Audit script:
[`.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v3.py`](../../.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v3.py).
22,363 trials. Outputs at
[`.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3/`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3/)
+ renders at
[`.scratch_phase_7f_scoping/visual_renders_cleanup_v3/`](../../.scratch_phase_7f_scoping/visual_renders_cleanup_v3/).

**Cleanup rules applied (v3, identical to v2 but at pre-Stage-4):**

1. **R1 Y-ceiling = 80 px** above baseline_mean (applied to raw frames).
2. **R3 Frame-level outlier wipe** on raw clusters (|y - rolling_median ±20 ms| > 80 px).
3. **R2 Isolated-short cluster wipe** (raw clusters ≤ 5 frames, no other raw cluster within ±30 ms).
4. **Re-PCHIP interpolation** over the surviving anchor set; gaps > 120 ms (jaw v5p3 `max_gap_ms`) fall to baseline-fill.

**Cohort means (full table:
[`by_phenotype_epoch_cleanup_v3.csv`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3/by_phenotype_epoch_cleanup_v3.csv);
plot:
[`cohort_mean_delta_bar_v3.png`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3/cohort_mean_delta_bar_v3.png)):**

| cell | prod peak | clean peak | Δ peak | prod pass_qc | clean pass_qc | Δ pass_qc | any wipe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mild / pre        | 102.6 | 79.4 | **−23%** | 0.915 | 0.908 | −0.7% | 15.2% |
| mild / acute      | 100.4 | 77.3 | **−23%** | 0.892 | 0.892 | 0.0% | 13.6% |
| mild / chronic    | 105.8 | 79.0 | **−25%** | 0.913 | 0.887 | −2.6% | 16.1% |
| mild / sub_acute  | 106.7 | 78.5 | **−26%** | 0.907 | 0.888 | −1.9% | 15.8% |
| moderate / acute  | 89.1 | 68.2 | **−23%** | 0.843 | 0.795 | −4.8% | 8.0% |
| moderate / pre    | 87.9 | 78.5 | **−11%** | 0.608 | 0.555 | **−5.3%** | 0.2% |
| **mod-sev / acute** | **11.3** | **11.2** | **−1.2%** | 0.823 | 0.823 | 0.0% | <0.01% |
| mod-sev / pre     | 106.4 | 79.1 | **−26%** | 0.977 | 0.971 | −0.7% | 19.7% |
| mod-sev / chronic | 94.7 | 74.8 | **−21%** | 0.853 | 0.830 | −2.3% | 7.5% |
| **severe / acute** | **11.2** | **10.85** | **−3.2%** | 0.675 | 0.674 | 0.0% | 0.02% |
| severe / pre      | 101.2 | 77.7 | **−23%** | 0.774 | 0.736 | −3.8% | 12.1% |
| severe / chronic  | 74.8 | 66.0 | **−12%** | 0.798 | 0.766 | −3.2% | 0.6% |
| severe / sub_acute | 65.6 | 55.1 | **−16%** | 0.799 | 0.774 | −2.5% | 1.2% |

**v3 vs v2: the order-of-ops fix is decisive for the per-trial
artifact problem.**

| trial | v2 clean (lk) | **v3 clean (lk)** | difference |
| --- | --- | --- | --- |
| PS54 / 5-05 / t010 L | 78.9 px (lk=**0.05**, PCHIP-bridge) | **51.7 px (lk=0.51, real raw frame)** | v3 anchors on real DLC |
| PS54 / 5-01 / t013 R | 80.0 px (lk=0.34) | **57.9 px (lk=0.51)** | v3 lands on real lick |
| PS55 / 5-14 / t033 L | 77.9 px (lk=0.81) | **62.1 px (lk=0.92)** | v3 finds higher-confidence peak |
| PS54 / 5-06 / t095 L | 9.7 px (lk=0.81) | **9.7 px (lk=0.81)** | unchanged (single-frame wipe was correct in both) |

**Across all 8 visual-render trials, v3's clean peak now lands on a
real raw DLC frame with `lk ≥ 0.5`** — directly resolving the
"clean peak at lk=0.05" diagnostic Priya flagged after v2.

**Cohort-level observations (v3):**

- **Severe-acute essentially unchanged**: prod 11.2 → clean 10.85
  (−3.2%). Paper-narrative biological signal preserved exactly.
- **`jaw_pass_qc` rates very well preserved**: worst flip is
  moderate/pre at 5.3% (same cell as v2). Severe-acute 0.04%,
  severe/pre 3.8%, severe/chronic 3.2%, severe/sub_acute 2.5%.
  Mismatch-classifier dissociation narrative stable.
- **R1 Y-ceiling=80 still clips real licking peaks** in mild/healthy
  cells. Mild cohort means drop 23-26% — same pattern as v2.
  Per-frame R3 frame-outlier and R2 isolated-short fire VERY rarely
  cohort-wide (<0.1%), as in v2 — they're catching truly rare events.
- **No PCHIP-bridge "fake peaks" remain**: this is the v2→v3 win.

**Conclusion:** v3 is the correct architecture for Phase 7f Option B
(bodypart-parametric v7 port + cohort v5p3 re-emit). The remaining
design choice is the **Y-ceiling threshold + handling of healthy
high-amplitude peaks > 80 px**:

- **(i) Keep Y-ceiling = 80** (accept mild-cell cohort shift; the
  shift may capture genuine artifact contamination of healthy peaks).
- **(ii) Raise to 150-200 px** (preserves real licking in mild cells
  but lets some pre-1300ms cluster artifacts survive).
- **(iii) Per-phenotype ceiling** (80 for severe, 200 for mild).
- **(iv) Add v5p3 lk_thr=0.5 per-frame gate at peak-picking** (Priya
  suggested this may come back). Wouldn't change the bulk of the
  cleanup but would gate the surviving peak frame on lk≥0.5 directly.

The order-of-ops fix is robust; the Y-ceiling calibration is the only
remaining open knob. Phase 7f Task 1 should empirically calibrate via
a per-phenotype `y99` sweep on lk≥0.85 raw DLC + sensitivity analysis
on `candidate_no_lick_with_jaw_move` rate.

### 3.13 v3.3 — Y_CEILING raised to 125 (Priya 2026-05-26 lock)

Per Priya 2026-05-26 ("from the healthy trials I'm convinced we
should loosen the max to 125"), v3.3 is v3.2 with `Y_CEILING_PX`
raised from 80 to 125. All other constants unchanged. Audit script:
[`audit_jaw_cleanup_sim_v3p3.py`](../../.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v3p3.py).
Outputs at
[`.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3p3/`](../../.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3p3/);
severe-acute renders at
[`visual_renders_cleanup_v3p3/`](../../.scratch_phase_7f_scoping/visual_renders_cleanup_v3p3/);
pre-stroke renders at
[`visual_renders_pre_stroke_v3p3/`](../../.scratch_phase_7f_scoping/visual_renders_pre_stroke_v3p3/).

**Cohort means — major recovery from v3.2:**

| cell | prod | v3.2 clean | **v3.3 clean** | v3.3 Δ |
| --- | --- | --- | --- | --- |
| mild / pre        | 102.6 | 79.4 | **100.1** | **−2.4%** |
| mild / acute      | 100.4 | 77.3 | **96.9**  | **−3.4%** |
| mild / chronic    | 105.8 | 79.0 | **101.8** | **−3.7%** |
| mild / sub_acute  | 106.7 | 78.5 | **101.9** | **−4.5%** |
| moderate / acute  | 89.1  | 68.2 | **86.8**  | **−2.6%** |
| moderate / pre    | 87.9  | 78.5 | **83.7**  | **−4.7%** |
| **mod-sev / acute** | **11.3** | **11.2** | **11.3**  | **0.0%** |
| mod-sev / pre     | 106.4 | 79.4 | **103.6** | **−2.6%** |
| mod-sev / chronic | 94.7  | 75.7 | **90.8**  | **−4.2%** |
| **severe / acute** | **11.2** | **10.85** | **10.92** | **−2.5%** |
| severe / pre      | 101.2 | 76.8 | **96.3**  | **−4.8%** |
| severe / chronic  | 74.8  | 67.0 | **73.8**  | **−1.3%** |
| severe / sub_acute | 65.6  | 56.2 | **62.2**  | **−5.1%** |

Cohort means now drop **1-5% across all cells** (vs. 20-30% in v3.2).
Severe-acute paper-narrative effectively unchanged (11.2 → 10.92).

**`jaw_pass_qc` flip rates** also dropped: worst is 2.7% in moderate/pre
(down from 5.3% in v3.2). Severe-acute 0.0% flip.

**Wipe rates by rule** (mean per-trial detect-window fraction):
- R1 Y-ceiling: 0.0-0.6% per cell (down from 0-25% in v3.2)
- R2 isolated-short: 0.0-0.07% (unchanged)
- R3 frame-outlier: <0.0001% (unchanged — still catches rare outliers)

**Pre-stroke verification under v3.3** (same 8 trials as §3.12):

| trial | prod |defl| | v3.2 clean | **v3.3 clean** | qc |
| --- | --- | --- | --- | --- | --- |
| PS49 / mild_top | 180.7 | 88.7 | **107.9** | ✓ |
| PS50 / mild_median | 102.5 | 73.1 | **102.5 (unchanged)** | ✓ |
| PS46 / moderate_top | 176.2 | 117.9 | **139.8** | ✓ |
| PS46 / moderate_median | 82.7 | 82.7 | **82.7 (unchanged)** | ✓ |
| PS51 / mod-sev_top | 169.1 | 76.8 | **110.0** | ✓ |
| PS51 / mod-sev_median | 104.7 | 82.1 | **104.7 (unchanged)** | ✓ |
| PS54 / severe_top (pre-stroke) | 168.7 | 90.8 | **111.0** | ✓ |
| PS55 / severe_median (pre-stroke) | 102.1 | 84.8 | **102.1 (unchanged)** | ✓ |

**All median trials unchanged** (peaks below 125). Top trials clipped
30-70 px (vs. 60-90 px in v3.2). PS49 mild_top render shows the
qualitative difference: real licking activity at 100-130 px from
t=200-1000ms is now PRESERVED (vs. v3.2 which dropped large stretches
to y=0). The 200 px spike at t=3404ms is correctly wiped as the only
obvious artifact in that trial.

**Severe-acute renders under v3.3:**

| trial | v3.2 |defl|/lk/qc | **v3.3 |defl|/lk/qc** |
| --- | --- | --- |
| PS54 / 5-01 / t013 R | 57.9 / 0.51 / **False** | **111.7 / 0.54 / True** (qc preserved!) |
| PS54 / 5-06 / t095 L (single-frame outlier) | 9.7 / 0.81 / True | **9.7 / 0.81 / True (unchanged)** |
| PS55 / 5-14 / t033 L (active licking) | 62.1 / 0.92 / True | (preserved similar) |

PS54 t013 R `pass_qc` flips back to True under v3.3 — the higher
ceiling lets enough supra-threshold frames survive in the
post-1300ms real-movement region. PS54 t095 single-frame outlier
still correctly wiped (R1 fires on the 125.1 px spike since deflection
= 139.6 > 125 ceiling).

**Verdict: v3.3 (`Y_CEILING_PX = 125`) is the locked design for Phase
7f Option B kickoff.** All v2-era pre-clean rules carry over (R1 + R2
+ R3 + R4 + re-PCHIP-interpolation at pre-Stage-4 stage). Constants:
- `Y_CEILING_PX = 125` (Priya 2026-05-26 lock)
- `ISOLATED_MAX_N = 5`
- `ISOLATED_RADIUS_MS = 30`
- `FRAME_JUMP_THR_PX = 70`
- `FRAME_OUTLIER_LOCAL_MEDIAN_MS = 20`
- `MAX_GAP_MS_PCHIP = 120` (jaw v5p3 default unchanged)

### 3.12 Pre-stroke (healthy) verification under v3.2

Per Priya 2026-05-26: "could we check some pre-stroke sessions too?"
The original 8-trial visual set was severe-acute only. To verify v3.2
doesn't break healthy licking, 8 pre-stroke trials (2 per phenotype:
top-peak_abs and median-peak_abs) were rendered under v3.2 cleanup.
Renders at
[`.scratch_phase_7f_scoping/visual_renders_pre_stroke_v3p2/`](../../.scratch_phase_7f_scoping/visual_renders_pre_stroke_v3p2/).

| trial | prod |defl| | clean |defl| | qc preserved? |
| --- | --- | --- | --- | --- |
| PS49 / 3-10 / t7 R **mild_top** | 180.7 | 88.7 | ✓ |
| PS50 / 3-19 / t81 L **mild_median** | 102.5 | 73.1 | ✓ |
| PS46 / 3-12 / t0 R **moderate_top** | 176.2 | 117.9 | ✓ |
| PS46 / 3-07 / t90 L **moderate_median** | 82.7 | 82.7 (unchanged) | ✓ |
| PS51 / 4-27 / t53 R **mod-sev_top** | 169.1 | 76.8 | ✓ |
| PS51 / 4-29 / t55 L **mod-sev_median** | 104.7 | 82.1 | ✓ |
| PS54 / 4-21 / t46 L **severe_top** (pre-stroke) | 168.7 | 90.8 | ✓ |
| PS55 / 4-26 / t89 R **severe_median** (pre-stroke) | 102.1 | 84.8 | ✓ |

**Findings:**

- **`jaw_pass_qc` preserved on ALL 8 pre-stroke trials** — the
  mismatch-classifier input survives the cleanup for healthy mice.
- **Real licking peaks in healthy mice reach 110-200 px**, well above
  the Y-ceiling=80. Top-peak trials get clipped 30-90 px.
- **In long high-amplitude licking bursts, the cleanup trace drops to
  baseline (y=0) for entire stretches** — visible in PS49 t007
  (~500-700 ms zero stretch) and PS50 t081 (~2700-3000 ms zero stretch).
  This is R1 wiping consecutive frames + R4 PCHIP-extend wiping
  adjacent interp frames; gaps > 120 ms then fall to Stage 5 baseline.
- **PCHIP overshoot is "leaky" at the Y-ceiling**: PS46 moderate_top
  cleanup peak landed at 117.9 px even though Y-ceiling is 73 (baseline=−7,
  ceiling at +80). The peak is on a PCHIP-bridge value that
  overshoots the ceiling because surrounding kept anchors are near
  the ceiling. The Y-ceiling is enforced on RAW frames only; the
  re-PCHIP-interpolation can produce post-cleanup values above the
  ceiling.

**Conclusion:** v3.2 with Y_CEILING=80 is **structurally too tight for
healthy mice**. The cleanup doesn't break `pass_qc` (mismatch
classifier is safe), but it materially distorts healthy peak amplitudes
and drops entire licking bursts to baseline. **Phase 7f Task 1 must
raise the Y-ceiling and/or use a per-phenotype value**.

Updated recommendation for the Y-ceiling open knob:
- **(i) Keep Y_CEILING=80** — **NO**, pre-stroke renders confirm this
  wipes real movement aggressively.
- **(ii) Raise to 150-200 px** — preserves healthy licking (peaks reach
  180-200 px in mild_top, so 200 ceiling preserves all). Risk: some
  severe-acute pre-1300ms cluster artifacts at 100-150 px (e.g., PS54
  t013 R) would survive. R2 + R3 still catch most of those because
  they're embedded in low-confidence baseline-fill-bracketed contexts.
- **(iii) Per-phenotype ceiling** — e.g., 80 for severe/mod-sev, 200
  for mild/moderate. Requires phenotype lookup in jaw_pertrial. Most
  honest but adds complexity.
- **(iv) Drop Y-ceiling entirely** — rely on R2 + R3 alone. Audit
  showed R3 catches outliers cohort-wide; R2 catches isolated-short
  clusters. May miss some long-duration cluster artifacts that R2
  doesn't recognize as "isolated".

Suggested Phase 7f Task 1 first iteration: **Y_CEILING = 200 px**
(global) + Y_CEILING_GROUPS={severe: 100, others: 200} as a
sensitivity comparison.

### 3.11 Frame-outlier R3 refinement (v3.1 + v3.2)

Priya 2026-05-26 visual review of v3 spotted a residual artifact in
PS54 / 5-01 / t013 R: a clear low-y outlier at t=184ms (y=-36, lk=0.54,
surrounded by raw frames at y≈38). The cluster-mean threshold and
isolated-short rule both missed it.

**v3.1 (FRAME_JUMP_THR_PX 80 → 70):** simple threshold tightening.
Result: **no change** in cohort means or visual render. Diagnostic
([`.scratch_phase_7f_scoping/_find_outlier_PS54_t013.py`](../../.scratch_phase_7f_scoping/_find_outlier_PS54_t013.py))
revealed the cause — the outlier is a **single-frame raw cluster**
with another raw cluster only 8ms away, falling into a coverage gap:
- R1 doesn't fire (negative deflection, ceiling is positive-side only)
- R2 doesn't fire (another raw cluster within ±30ms violates "isolated")
- R3 doesn't fire (cluster length < 3 guard, plus within-cluster median
  is degenerate for single-frame clusters)

So no amount of threshold tightening on the v3.1 architecture catches
this. The fix is structural, not numeric.

**v3.2 — cross-cluster R3.** Changed R3 from "within-cluster
rolling median" to "K-nearest raw-frame median" via
`scipy.ndimage.median_filter` on the raw-frame index array. For each
raw frame, the local median is computed over the K=11 (W=5 each side)
nearest raw frames regardless of cluster identity. In dense regions
this is equivalent to the original ±20ms time window; in sparse regions
it bridges cluster boundaries and catches single-frame outliers between
baseline-fill bands. Audit script:
[`audit_jaw_cleanup_sim_v3p2.py`](../../.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v3p2.py).

**Result:** R3 fires on the PS54 t013 R outlier (frame 213464, y=-36)
— deviation from local raw-neighbor median (~38) is ~74 px, above
threshold 70. Visible as the red `R3 frame-outlier (n=1)` marker at
y≈-35 in the v3.2 render.

**Cohort sanity:** R3 firing rate increased slightly from v3 (still
< 0.001% in all cells), severe-acute cohort mean 10.85 → 10.82
(−0.3%). `pass_qc` rates identical to v3 cohort-wide. **No
over-wiping detected on any of the 8 severe-acute visual renders.**

**Net v3 → v3.2:** the order-of-ops fix from v3 remains the decisive
architectural change. v3.2 closes one residual coverage gap with a
small refinement to R3's neighbor definition. Constants unchanged
from v3 (Y_CEILING=80, ISOLATED_MAX_N=5, ISOLATED_RADIUS_MS=30,
FRAME_JUMP_THR_PX=70, FRAME_OUTLIER_LOCAL_MEDIAN_MS=20, MAX_GAP_MS_PCHIP=120).

---

## 4. Visual verdict — 8 hand-picked severe-acute trials

Renders at
[`.scratch_phase_7f_scoping/visual_renders/`](../../.scratch_phase_7f_scoping/visual_renders/).
Selection: top-4 (per-animal) `peak_abs_deflection` across severe-acute
(`phenotype = severe`, `epoch = acute`) trials — 8 trials total (PS54 + PS55).
Each render shows the v5p3 `y_final` trace (raw-kept frames black,
interp-filled grey, baseline-filled red ×) plus per-frame
`likelihood_raw` (top + bottom panels respectively).
Selected-trial table at
[`chosen_trials.csv`](../../.scratch_phase_7f_scoping/visual_renders/chosen_trials.csv).

| trial | peak |defl| | peak_lk | peak_is_baseline_fill | peak |defl| at lk≥0.9 | pattern |
| --- | --- | --- | --- | --- | --- |
| PS55 / 2025-05-14 / t033 L | 183.4 | 0.57 | False | 77.9 | Real licking trace with multiple peaks; absolute peak at lk=0.57. |
| PS54 / 2025-05-01 / t013 R | 138.3 | 0.72 | False | 36.4 | Mid-confidence peak; big counterfactual drop. |
| PS54 / 2025-05-05 / t010 L | 129.4 | 0.56 | False | 45.9 | Mid-confidence peak; big counterfactual drop. |
| **PS54 / 2025-05-06 / t095 L** | **125.1** | 0.66 | False | **8.7** | **Single-frame outlier** on otherwise resting trace at y≈−15; classic DLC misdetection. |
| PS55 / 2025-05-06 / t002 L | 123.4 | 0.50 | False | 25.3 | Borderline-lk peak; big counterfactual drop. |
| PS55 / 2025-05-09 / t021 L | 119.1 | 0.56 | False | 31.0 | Mid-confidence peak; big counterfactual drop. |
| PS54 / 2025-05-09 / t006 L | 114.3 | 0.57 | False | 106.3 | Real movement — lk=0.57 frame is on a structurally supported peak; counterfactual barely changes. |
| PS55 / 2025-05-17 / t003 R |  88.1 | 0.91 | False | 88.1 | Clean high-confidence peak; counterfactual unchanged. |

**Key observation:** **none of the 8 chosen peaks fell on baseline-fill
or interp-fill frames.** All peaks landed on raw DLC frames. This
**rules out the analogous PCHIP-anchored-spike-against-Stage-5-zeros
artifact mechanism that motivated tongue v7.**

**Different artifact mechanism for jaw:** 5/8 of the largest
severe-acute peaks are **single mid-confidence raw DLC frames** with
outlier y values, on otherwise resting traces. The most extreme case
(PS54 / 2025-05-06 / t095 L) is a single-frame 125 px spike at lk=0.66
on a trace that otherwise sits steady at y≈−15. Counterfactual at
lk≥0.9 drops it to 8.7 px (93% drop). 3/8 are robust real movements
(small counterfactual drop). This is a **different artifact pattern**
than tongue's; the v7 cluster classifier / PCHIP-extend wipe pipeline
is calibrated for a structural pattern that jaw does NOT exhibit.

---

## 5. Recommended Phase 7f scope (verdict, REVISED per amendment)

> **Verdict:** between `light-cleanup-plus` (Option A) and
> `bodypart-parametric v7 port` (Option B). Architecture picked at
> kickoff. Scope substantively larger than the initial single-frame
> framing.

**Rationale:**

1. **Cluster-level artifact pattern IS present** (per Priya's review
   of PS54 / 2025-05-01 / t013 R): high-y raw DLC clusters reaching
   100-150 px bracketed by Stage-5 baseline-fill bands with lk < 0.5.
   **This IS the structural analog of tongue v7's PCHIP-anchored-spike-
   against-Stage-5-zeros mechanism.**
2. **Single-frame outlier pattern is also present** (PS54 t095): mid-
   confidence single-frame spikes on otherwise-resting traces.
3. **Cohort-level metrics understate per-trial contamination.** The
   ≤ 2.4% baseline-fill-at-peak aggregate hides the distribution tail
   where cluster + frame artifacts produce the largest |defl| values.
4. **A hard Y-ceiling rule (~75 px above baseline)** is a simple,
   high-SNR gate. Calibrate from per-animal `y99` of lk≥0.85 raw DLC.
5. **The v7 architecture DOES apply to jaw** — the architecture is
   right; the constants need jaw-specific recalibration.

**Out-of-scope for Phase 7f (unchanged):**
- The headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
  endpoint reads raw frames at lk≥0.80 (NOT v5p3); unaffected by any
  jaw_pertrial / jaw-v5p3 cleanup. See Q-4 in §7.

**Re-classified in-scope per amendment:**
- v5p3 `max_gap_ms = 120` (vs. tongue's 56) may need tightening. If
  so, cohort jaw v5p3 re-emit is required — this is the architecture
  choice distinguishing Option A from Option B in §6.

---

## 6. Forward-pointers — Phase 7f scope options (REVISED per amendment)

Two architecture choices below; Priya picks at kickoff. The audit
confirms cleanup is needed; the architecture choice is the open
scoping question.

### Option A — `light-cleanup-plus`: all logic inside `jaw_pertrial.py`

Add the new rules at the jaw_pertrial input snippet level — after
reading the v5p3 trace but before `_compute_jaw_deflections`. The v5p3
parquets stay untouched; no cohort v5p3 re-emit.

Required rules (apply in order):
1. **Hard Y-ceiling wipe:** any frame with
   `y_final - baseline_mean > Y_CEILING_PX` (~75 px per Priya
   2026-05-26; calibrate on per-animal `y99` of lk≥0.85 raw DLC) is set
   to NaN. Single threshold, no per-cluster logic.
2. **Cluster classifier** (port of Phase 7e Decisions 9 + 11): for
   contiguous runs of `y > HIGH_THR` AND `fill_method == 0` (raw DLC
   kept):
   - **artifact_intra_cluster** if intra-cluster shape flat
     (`cluster_range < SHAPE_RANGE_THR_JAW` AND
     `cluster_min > SHAPE_LOW_THR_JAW`).
   - **artifact_isolated_short** if `n ≤ ISOLATED_MAX_N` AND no other
     raw cluster within `±ISOLATED_RADIUS_MS`.
   - **kept** otherwise.
3. **Frame-level outlier wipe** (port of Decision 12): within each
   kept cluster, wipe single frames where
   `|y[k] - local_median(±20ms)| > FRAME_JUMP_THR_JAW`.
4. **PCHIP-extend wipe** (port of Decision 13): after wiping a cluster
   or frame, also wipe adjacent `is_interp_fill` frames within
   `±PCHIP_EXTEND_MS` until a non-interp anchor is reached.
5. **Peak-likelihood gate:** when picking
   `argmax(|y_clean - baseline_mean|)`, require
   `likelihood_raw ≥ PEAK_LK_GATE` (suggest 0.85).

- **Affects:** new module
  `src/stroke_orofacial/dlc_kinematics/_jaw_preclean.py` consumed by
  `jaw_pertrial.py` (OR a shared bodypart-parametric helper in
  `_preclean.py` for tongue/jaw sharing). Re-emit per_trial JSONs only
  (not v5p3 parquets).
- **Risk:** cluster predicates depend on `fill_method` — if v5p3 mis-
  classified a fragment as PCHIP-fill, this option can't recover it.
  Audit suggests this is rare for jaw (PCHIP-fill rate < 12% in all
  cells).
- **Estimated wall-time:** **3-5 days CC** (port + 5+ new constants
  calibrated + unit tests + cohort per_trial re-emit + visual-gate
  parity on the 8 severe-acute renders + tongue_jaw_mismatch
  candidate-rate parity check).

### Option B — `bodypart-parametric v7 port`: full v5p3 integration

Port the v7 architecture into bodypart-parametric form
(`_preclean.py`, `_detector_v2.py`, `_gates.py` accept `bodypart` and
load constants from `configs/defaults.yaml dlc_kinematics.<bp>.preclean.*`).
Tune `max_gap_ms` at v5p3 level (currently 120 ms for jaw — Priya
flagged this may be too lenient). Cohort jaw v5p3 re-emit.

- **Affects:** all 3 v7 modules become bodypart-parametric (tongue +
  jaw first-class). `interpolation.py` jaw branch gets a new
  `max_gap_ms` value. Both v5p3 jaw parquets AND per_trial JSONs
  re-emit cohort-wide.
- **Risk:** v5p3 re-emit invalidates downstream stats — Phase 9 axis
  results consuming jaw_pertrial scalars need re-run. Event B's
  just-completed re-emit is unaffected (tongue-specific) but Phase 9
  cohort outputs are.
- **Estimated wall-time:** **2-3 weeks CC** (tongue v7's algorithm
  design took 3 days in `.scratch_phase_9_1/`; tongue v7's production
  phase took ~3 weeks). Jaw inherits the architecture but needs its
  own calibration + parity harness.

### Recommended option

**Option A (`light-cleanup-plus`)** unless Priya specifically wants
v5p3 `max_gap_ms` tuning to land now. Rationale:
- All needed input columns (`fill_method`, `likelihood_raw`,
  `is_baseline_fill`) are preserved in the v5p3 parquet — Option A can
  reach the artifacts via post-v5p3 filtering.
- No cohort v5p3 re-emit → no invalidation of Event B or upstream
  stats inputs derived from v5p3 traces.
- Easier iteration on constants during kickoff.
- Option B remains a future forward-pointer if Priya later wants to
  share preclean logic with tongue (re-running tongue under bodypart-
  parametric form is a no-op when tongue-specific constants are
  preserved).

---

## 7. Open questions for Priya

> Numbered Q-1 through Q-5 for easy reference in addenda.

- **Q-1 (REVISED).** Architecture pick: **Option A
  (`light-cleanup-plus`, all logic inside `jaw_pertrial.py`)** vs.
  **Option B (`bodypart-parametric v7 port`, full v5p3 integration)**?
  Recommendation: A unless you want v5p3 `max_gap_ms` tuning to land
  now rather than later.
- **Q-2 (NEW per amendment).** Y-ceiling threshold: ~75 px above
  baseline is the suggested anchor. Should Phase 7f calibrate from
  per-animal `y99` of lk≥0.85 raw DLC, or pick a cohort-uniform value?
- **Q-3 (REVISED).** Severe-acute peak-deflection floor: current prod
  `mean peak_abs_deflection` = 11.2 px. After the full Option A
  pipeline (Y-ceiling + cluster + frame + PCHIP-extend + lk-gate), the
  drop will likely be larger than the initial 10% lk-gate-only
  estimate, since several severe-acute trials have current peaks
  > 100 px that are clearly artifactual (PS54 t013/t095). Comfortable
  with the headline floor potentially dropping to ~5-9 px, or want
  Phase 7f to include a sensitivity analysis before locking?
- **Q-4.** Headline `spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all`
  reads raw frames at lk≥0.80 — outside v5p3, outside this audit.
  Should we queue a separate forward-pointer to audit that pipeline's
  quality (analogous to this one but for raw-DLC inputs to spatial
  heatmaps)? Memory finding #7 marks it as the strongest jaw signal,
  so independent quality verification before publication may be
  prudent.
- **Q-5.** The `tongue_jaw_mismatch.candidate_no_lick_with_jaw_move`
  classifier consumes `jaw_pass_qc` (boolean: ≥ 5/8 frames within any
  rolling 8-frame window have `|defl| > max(4 SD, 4 px)`). After L1/L2
  the threshold-test inputs change. Should Phase 7f's success-gate
  include a `jaw_pass_qc` candidate-rate parity check (the
  candidate_no_lick_with_jaw_move count per session shouldn't shift by
  more than X%), or is the per-session scalar parity check sufficient?

---

## 8. Reference artifacts

- Audit script: [`.scratch_phase_7f_scoping/audit_jaw_quality.py`](../../.scratch_phase_7f_scoping/audit_jaw_quality.py) — 8 animals × 231 sessions × 22,363 trials.
- Visual renderer: [`.scratch_phase_7f_scoping/render_severe_acute_jaw_traces.py`](../../.scratch_phase_7f_scoping/render_severe_acute_jaw_traces.py).
- Audit aggregate outputs: [`.scratch_phase_7f_scoping/audit_results/`](../../.scratch_phase_7f_scoping/audit_results/) (8 CSVs + 2 PNGs).
- Visual renders: [`.scratch_phase_7f_scoping/visual_renders/`](../../.scratch_phase_7f_scoping/visual_renders/) (8 PNGs + chosen_trials.csv).
- Tongue investigation template: `.scratch_phase_9_1/dlc_tongue_quality_investigation/`.
- Phase 7e DECISIONS (jaw deferral): `docs/DECISIONS.md` 2026-05-25 Decision 8.
