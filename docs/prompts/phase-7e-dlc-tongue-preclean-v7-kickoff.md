# Phase 7e Kickoff — DLC Tongue Pre-clean + v7 Detector Migration to Production

**Branch:** `phase/7e-dlc-tongue-preclean-v7` off latest `origin/main` (post-Phase-9.1 work or current main HEAD at session start; verify with `git rev-parse origin/main` and `git tag --list | tail -3`).
**Tag on phase-close merge:** `v7e-dlc-tongue-preclean-v7`.
**Prerequisites:** conda env `stroke_orofacial` active; CC has read `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py` (the v7 reference implementation, 980 lines), `.scratch_phase_9_1/inv_p3b_cohort_validation.py` (the cohort validation harness), `.scratch_phase_9_1/dlc_tongue_quality_investigation/part3b_cohort_validation_v7/part3b_stats.csv` (80-trial validation outcomes); MICROSCOPE mount available (R/W for new `cleaned_traces/` and `lick_events/` output trees); memory entries `feedback_iterative_addenda_pattern.md` + any captured during the Phase 7e investigation.
**Estimated scope:** ~10 files touched, ~12-18 commits, ~7-10 days CC wall-time (excluding cohort re-emit + downstream stats regeneration which is a separate sub-task gated on Priya per-invocation approval per CLAUDE.md Ground Rule 7).

---

## Context

A multi-week iterative investigation in `.scratch_phase_9_1/` (Priya 2026-05-23 through 2026-05-25, conducted as a CC sandbox refinement loop) produced a substantially improved DLC tongue pre-clean + detector pipeline ("v7") that:

1. **Pre-cleans interpolated tongue traces** to eliminate artifact clusters (fixture mis-labels, plateau drift, single-frame DLC spikes, PCHIP-anchored-on-outlier interpolation segments) **before** the lick detector runs.
2. **Replaces the legacy argmax-in-window slope detector** with `scipy.signal.find_peaks` local-maxima detection augmented by the existing bounded-fall and legacy slope detectors with 50ms cross-detector dedupe (find_peaks wins on overlap).
3. **Adds post-detection gates** F (within-peak raw std), D (left/right low context), E (z-vs-peers outlier with parabolic/PCHIP imputation), and M (confidence-based 80ms inter-lick interval).
4. **Surfaces per-trial-per-lick records** for downstream analyses.

Validation outcomes against 9 canonical "hard" trials + 80 cohort-sampled trials are captured at `.scratch_phase_9_1/dlc_tongue_quality_investigation/part3b_cohort_validation_v7/`. Priya scientific review (2026-05-25 session) iteratively refined the algorithm and signed off on the current scratch state — including documented edge-case limitations (M-gate 58L-style high-Y-vs-confidence trade-off; F-gate wide-flat-top edge case).

This phase **migrates the v7 algorithm from scratch into production** under `src/stroke_orofacial/dlc_kinematics/` with full test coverage, configs-yaml externalization, and downstream metric updates. The cohort re-emit (which overwrites materialized parquets and triggers downstream stats regeneration) is **out of scope for this kickoff** and will be a per-invocation approved follow-up after merge.

---

## Reference: v7 algorithm anatomy

Source of truth: `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`. Annotated walk-through:

### Stage 1 — Pre-clean (`preclean_trace`)

Input: y_final, x_final, is_interp_fill, is_baseline_fill from Phase 7a.2 v5p3 interpolated_traces parquet.

**Step 1a — Cluster classifier.** Each contiguous raw cluster (~is_intp & ~is_base) is labeled:
- `keep_low` if `cluster_max < HIGH_THR (130)`.
- `keep_real` if (Rule A) `cluster_min < SHAPE_LOW (80)` OR `cluster_range > SHAPE_RANGE (50)`, OR (Rule B) immediate-neighbor connectivity (`raw_mask[i-1]` or `raw_mask[j]`) AND a non-base low neighbor (`~is_base & y < HIGH_THR`) in ±100ms.
- `artifact_narrow` if high (`cluster_max >= HIGH_THR`) AND fails both Rule A and Rule B.
- `artifact_flat` (belt-and-suspenders): `n >= 20` AND `range < 3` AND `median > 30` (long flat plateau, regardless of A/B).
- **Override `artifact_isolated_short`**: short clusters (`n <= 3`) with high y AND no other raw cluster within ±20ms (catches single-frame DLC spikes that PCHIP interpolation "connected" to distant context).

**Step 1b — Frame-level intra-cluster outlier.** For each frame in a kept cluster, compare to local median (±20ms raw). If `|y - local_median| > 100`, wipe single frame (catches single-frame y=160 spike at end of real descending cluster, e.g., 24L ~1224ms).

**Step 1c — Wipe.** For each artifact-labeled cluster OR frame outlier, set `y=0`, `is_baseline_fill=True`.

**Step 1d — PCHIP-extend wipe.** When an artifact cluster or frame outlier is wiped, also wipe immediately-adjacent `is_intp` PCHIP frames within ±40ms. These were originally interpolated using the now-wiped outlier as an anchor; their y values are tainted.

**Step 1e — Bracketed-interp wipe.** Wipe any `is_intp` run whose left AND right boundary frame is wiped/baseline-fill (removes leftover interp segments between two wiped clusters, e.g., 34L plateau gaps).

### Stage 2 — Detection (`detect_local_maxima` + existing legacy + bounded)

Runs three detectors on the cleaned trace:
1. **`detect_local_maxima`** (NEW) — `scipy.signal.find_peaks` with `distance=50ms`, `height=min_peak_y_abs`. Each local max is validated by `consec_rise >= rise_min_n` AND (`consec_fall >= fall_min_n` OR immediate baseline retraction).
2. **`detect_bounded_fall`** (EXISTING) — slope walker with `MAX_FALL_SEARCH_MS=52` bound + implicit fall on baseline retraction.
3. **`_slope_detect_lick_peaks`** (LEGACY) — original argmax-in-window slope detector.

Cross-detector dedupe: peaks within `DEDUPE_RADIUS=50ms` of each other are merged; processing order is `lmax → bounded → legacy` (find_peaks wins on overlap because its local-max location is most accurate).

### Stage 3 — Post-detection gates

Applied per peak in time order:
- **Gate F** (within-peak raw std): if `std(raw y in ±20ms) < 1.0`, reject as `F_raw_flat` (catches plateau-shaped "peaks").
- **Gate D** (left/right low context): both sides within ±150ms must have either a raw frame with `y < D_Y_THR (130)` OR baseline-fill (rise/fall structure). Rejected as `D_left` or `D_right`.
- **Gate E** (outlier vs peers — runs ONLY for the first un-promoted peak): compute z-score vs MAD-robust trial-peer-median; if `z > 3.0` AND `likelihood < 0.85`, attempt **`parabolic_excise`** (quadratic fit to ±60ms anchors with concave-down vertex) — falls back to **`spline_excise`** (PCHIP through ±160ms anchors, max in ±20ms). Imputed `new_peak_y` and `new_peak_frame` replace the original peak; sets `imputed=True`.

### Stage 4 — M-gate (NEW, confidence-based inter-lick interval)

For each pair of consecutive KEPT peaks within `M_MIN_INTERVAL_MS=80`:
- Compute confidence = `#raw_frames_in_±20ms × mean_likelihood_of_those_frames`.
- Drop the LOWER-confidence peak (higher-Y tiebreaker if confidences are equal).
- Iterate until no more close-pair conflicts.

**Known limitation:** when a wobble has higher confidence than the real lick (PS47 54R, PS48 58L 312ms cases), M drops the real high-Y peak. Priya 2026-05-25 chose this trade-off (`M_MIN_INTERVAL_MS=80`) to prioritize removing erroneous wobble licks over preserving rare close-pair real peaks.

### Stage 5 — Output (NEW per-trial-per-lick records)

Each kept peak emits a row with: `animal, date, trial, side, lick_idx, t_ms, y, x, y_original (NaN if not imputed), rise_start_ms, fall_end_ms, imputed (bool), source ('lmax'|'bounded'|'legacy'), confidence, likelihood`.

---

## Scope + non-goals

**In scope:**
- Port v7 algorithm into production module `src/stroke_orofacial/dlc_kinematics/preclean.py` + `detector_v2.py` + `gates.py`.
- Externalize all v7 constants into `configs/defaults.yaml` under `dlc_kinematics.tongue_pertrial.preclean` and `.detector_v2`.
- New PathResolver methods: `cleaned_trace(bodypart, animal, date)` and `lick_events(bodypart, animal, date)`.
- New output parquets: `pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/<date>.parquet` (same schema as `interpolated_traces/` with `is_baseline_fill` updated to reflect pre-clean wipes) and `pipeline_outputs/dlc_kinematics/lick_events/tongue/<animal>/<date>.parquet` (per-trial-per-lick schema).
- Wire into `tongue_pertrial.py` behind a config flag `use_v7_pipeline: true` (default ON for new runs; legacy path preserved behind the flag for backward compat per Priya 2026-05-25).
- Update downstream metric computations:
  - **Tongue velocity** — restrict computation to KEPT-lick rise→fall windows only; mask `is_baseline_fill=True` frames; skip frames associated with rejected peaks.
  - **Lick angle** — use imputed y when `E_spline_impute` fires (already aligned with reported peak_y); audit whether x_final at imputed peak frame is sensible (PCHIP interp of x; flag if it materially affects angle).
- Unit tests: `tests/dlc_kinematics/test_preclean.py` (small synthetic traces for each gate), `tests/dlc_kinematics/test_detector_v2.py` (find_peaks rise/fall validation).
- Integration test: fixture-based end-to-end on the 9 canonical hard trials with byte-equal (or close-to-byte-equal) parity vs. scratch v7 PNG outputs (compare reported peak counts + per-peak t/y).
- Parity validation harness: a thin script that re-runs the scratch v7 on the 9 canonical + 80 cohort sample trials, compares against the new production code's output, and flags any per-trial deltas (peak count, per-peak t/y/imputed flag).

**Out of scope (for this phase):**
- **Cohort re-emit of `cleaned_traces/`, `lick_events/`, and updated `endpoints/` parquets across all 248+ sessions.** This is a destructive op (overwrites materialized DLC kinematics endpoints) and requires explicit per-invocation Priya approval per CLAUDE.md Ground Rule 7. Plan and execute as a follow-up after Phase 7e PR merge.
- **Downstream stats regeneration** (Phase 9 stats inputs re-materialization + per-axis re-runs). Gated on cohort re-emit completion.
- **Jaw interpolation revisit.** v7 architecture generalizes (cluster classifier + frame outliers + PCHIP-extend + find_peaks + gates), but params are tongue-specific (HIGH_THR=130, SHAPE_LOW=80, etc.). Defer jaw work to a separate Phase 7f or post-paper investigation; see "Outstanding follow-on" below.
- **X-coordinate review (see below).** Possibly worth a brief audit during 7e but not a blocker.
- **F-gate refinement for wide-flat lick tops** (PS48 58L 1924ms case).
- **M-gate non-greedy global selection** for 3-peak clusters within 150ms (PS47 54R case).

---

## ⚠️ Open question — X-coordinate interpolation review

**Note from Priya 2026-05-25.** During the v7 investigation, the conversation surfaced that the v7 algorithm focuses entirely on y-coordinate cleanup (vertical tongue extension). The x-coordinate is treated as "along for the ride":
- Pre-clean wipes set `y=0` but do NOT touch `x_final`.
- `parabolic_excise` and `spline_excise` interpolate y only; the reported `peak_x` is just `x_final[new_peak_frame]` (whatever PCHIP interp produced for x at that frame).
- Lick angle (atan2 of x relative to baseline) consumes `peak_x` as-is.

**Potential concern.** If DLC outliers tend to corrupt x and y simultaneously (same bad frame → both wrong), then the lick-angle metric uses the corrupted x even though we imputed y. This could systematically bias angle measurements at imputed lick peaks (especially for `E_spline_impute` cases). It's not clear yet how often this happens or how large the bias is.

**Recommended Phase 7e Task 0:** brief audit of x at imputed peaks across the 80-trial cohort sample:
- For each `E_spline_impute` decision, compare x at the original outlier frame vs. x at the new_peak_frame (often nearby).
- Compare PCHIP-interpolated x at new_peak_frame vs. PCHIP-interpolated x value the new_peak_frame would have if the outlier hadn't anchored the interpolation.
- If the deltas are small (< 5 px typical, < 2° angle), no action needed; document.
- If deltas are material, decide: (a) also wipe x at PCHIP-extend frames (analogous to y treatment), (b) provide an `x_imputed` field in lick_events parquet and let downstream choose, or (c) re-interpolate x via spline across the wiped window.

**Memory:** save as `project_phase_7e_x_interpolation_review_open.md` after Task 0 verdict so it doesn't get lost.

---

## Task breakdown

**Task 0 — X-coordinate audit + Phase 7e branch setup (0.5d).**
- `git checkout -b phase/7e-dlc-tongue-preclean-v7`.
- Write a one-off audit script `.scratch_phase_7e/audit_x_imputation.py` running the scratch v7 on the 80-trial sample + extracting x deltas at imputed peaks; save histogram + summary CSV.
- Report verdict to Priya: x-audit-clean (no action) OR x-audit-flag (recommend action).
- Lock the verdict in an addendum to this kickoff before proceeding to Task 1.

**Task 1 — Module scaffolding + config externalization (1d).**
- Create `src/stroke_orofacial/dlc_kinematics/preclean.py` skeleton (empty function signatures matching scratch + docstrings).
- Create `src/stroke_orofacial/dlc_kinematics/detector_v2.py` skeleton.
- Create `src/stroke_orofacial/dlc_kinematics/gates.py` skeleton (or inline in detector_v2.py — decide at this task).
- Add YAML section to `configs/defaults.yaml`:
  ```yaml
  dlc_kinematics:
    tongue_pertrial:
      preclean:
        high_thr_px: 130.0
        shape_low_thr_px: 80.0
        shape_range_thr_px: 50.0
        nbrhd_radius_ms: 100.0
        isolated_max_n: 3
        isolated_radius_ms: 20.0
        frame_jump_thr_px: 100.0
        frame_radius_ms: 20.0
        pchip_extend_ms: 40.0
        flat_min_len: 20
        flat_max_range_px: 3.0
        flat_min_y_px: 30.0
      detector_v2:
        lm_min_distance_ms: 50.0
        dedupe_radius_ms: 50.0
        max_fall_search_ms: 52.0
      gates:
        f_wp_win_ms: 20.0
        f_wp_std_thr: 1.0
        f_k_min_raw: 3
        d_win_ms: 150.0
        d_y_thr_px: 130.0
        e_z_thr: 3.0
        e_lik_override: 0.85
        e_k_min_peers: 4
        m_min_interval_ms: 80.0
        m_conf_radius_ms: 20.0
        spline_excise_radius_ms: 8.0
        spline_anchor_win_ms: 160.0
        spline_local_max_win_ms: 20.0
        spline_min_anchors: 4
        parabolic_tight_radius_ms: 60.0
        parabolic_min_anchors: 5
      use_v7_pipeline: true
  ```
- Update `src/stroke_orofacial/config_loader.py` if schema validation needs new keys.

**Task 2 — Port `preclean_trace` (1.5d).**
- Verbatim port of scratch lines 165-310 (function body + helpers). Add type hints + docstrings. Each step (cluster classify, frame outliers, wipe, PCHIP-extend, bracketed-interp) becomes a named helper for testability.
- Unit tests: synthetic traces for each gate (intra-cluster Rule A; non-base Rule B; isolated-short override; frame-outlier; PCHIP-extend; bracketed-interp).

**Task 3 — Port `detect_local_maxima` + dedupe (1.5d).**
- Verbatim port of scratch lines ~430-550. Add `rise_start_frame` and `fall_end_frame` fields to the returned per-peak record (legacy detector has these; bounded does too — find_peaks needs new code to delineate). These feed the per-lick parquet and tongue_velocity gating.
- Cross-detector dedupe helper takes a list of `LickPeaks`-like objects + radius and emits the merged list with provenance.
- Unit tests: synthetic two-peak waveforms (verify both detected); single-wide-peak (verify ONE detected); peak with rise but no fall (verify accepted via baseline-retraction fallback).

**Task 4 — Port gates F/D/E/M + imputation (2d).**
- Verbatim port of `gate_F`, `gate_D`, `gate_E`, `parabolic_excise`, `spline_excise` + M-gate loop. Co-locate in `gates.py`.
- Unit tests for each gate: F (plateau peak rejected); D (no-left-context rejected); E (outlier z>3 triggers spline); parabolic vertex correct on synthetic parabola; spline imputation falls back gracefully when anchors too few; M-gate drops correct peak in confidence ties.

**Task 5 — Wire into `tongue_pertrial.py` (1d).**
- Add `use_v7_pipeline` branch at the start of the per-trial peak-detection loop. When True: run preclean → detector_v2 → gates → M → emit cleaned_trace + lick_events parquets + endpoints JSON. When False: legacy path unchanged.
- New PathResolver methods + path stamps.

**Task 6 — Per-trial-per-lick parquet writer (0.5d).**
- New atomic writer in `_writers.py` (analogous to existing `_write_endpoints_json_atomic`).
- Schema fields per "Stage 5" above.
- File-level parquet metadata: `feature_extraction_version="v7e.0"`, `interpolation_version="v5p3"`, `algorithm_version="v7"`, etc.

**Task 7 — Downstream metric updates (1.5d).**
- `tongue_velocity` (find call site; likely in `_angle.py` or new `_velocity.py`): mask `is_baseline_fill=True` AND restrict to per-lick rise→fall windows from lick_events parquet.
- `lick_angle` (likely `_angle.py`): consume imputed y; if Task 0 verdict was x-audit-flag, also consume `x_imputed`.

**Task 8 — Parity validation harness + 9-canonical fixture test (1d).**
- `tests/dlc_kinematics/test_v7_parity.py`: load each of 9 canonical trials (PS54 24L/46L/35L/51L/35R/34L/25L/76L + PS47 33L) via fixture parquets (copy into `tests/fixtures/v7_canonical/`); run production v7 pipeline; assert detected/kept/wiped counts match `inv_p3a_step2j` outputs byte-for-byte (within float tolerance for peak y).
- `tests/dlc_kinematics/test_v7_cohort_parity.py` (slower): run on the 80-trial cohort sample; assert per-trial peak-count delta == 0.

**Task 9 — Migration log + DECISIONS + PR (0.5d).**
- `docs/MIGRATION_LOG.md` entry under Phase 7e.
- `docs/DECISIONS.md` entries: (a) v7 algorithm locked at scratch state; (b) M=80 confidence trade-off; (c) downstream velocity gating on kept licks; (d) per-trial-per-lick parquet as new canonical output; (e) x-coordinate review verdict (from Task 0); (f) cohort re-emit scope locked out of phase.
- Tag `v7e-dlc-tongue-preclean-v7` on merge commit.

---

## Parity strategy

Two layers:

1. **Algorithmic parity vs. scratch v7.** The production code MUST emit byte-equal peak counts + per-peak t/y/imputed_flag against `inv_p3a_step2j_unified_preclean.py` on the 9-trial fixture set. Any deviation requires either an intentional change documented in DECISIONS (with Priya sign-off) or a bug fix. Task 8 enforces this.

2. **No-op verification on legacy path.** With `use_v7_pipeline: false`, the existing `tongue_pertrial.py` test suite (1417+ tests in current main) MUST pass unchanged. Ensures backward compat for any consumer that hasn't migrated.

---

## Hardcoded constants — all moved to YAML

Per Phase 7e Task 1, every numeric constant in the scratch reference (HIGH_THR, SHAPE_LOW, SHAPE_RANGE, ISOLATED_MAX_N, FRAME_JUMP_THR, PCHIP_EXTEND_MS, F_WP_STD_THR, D_Y_THR, E_Z_THR, M_MIN_INTERVAL_MS, etc.) lands in `configs/defaults.yaml` under `dlc_kinematics.tongue_pertrial.{preclean, detector_v2, gates}`. No magic numbers in the ported `.py` files; all reads go through `load_defaults()`.

---

## Known limitations — documented and accepted

1. **M-gate confidence-vs-Y trade-off** (PS47 54R, PS48 58L 312ms): when a wobble has higher raw-DLC density than a real high-Y peak within 80ms, M drops the real peak. Priya 2026-05-25 chose this over the alternative (Y-tiebreaker drops 51L real first lick because 51L wobble is higher-Y).
2. **F-gate wide-flat-top edge case** (PS48 58L 1924ms): real wide lick tops with std < 1.0 px in raw frames get rejected as plateau artifacts. Hard to fix without shape-based discrimination (parabolic vs. triangular vs. flat).
3. **76L ~150ms early isolated cluster sacrificed** by intra-cluster + neighbor rules. Priya 2026-05-25 accepted this trade-off.
4. **PS47 33L drops 14 vs legacy 15** — one unexplained gap; not a v7 regression vs. v6 but never fully diagnosed. Likely downstream detector quirk in a single-detector pass.

---

## Outstanding follow-ons (post Phase 7e)

- **Cohort re-emit** of cleaned_traces, lick_events, and updated endpoints across the 248+ session cohort. Requires per-invocation Priya approval per CLAUDE.md Ground Rule 7. Estimate: ~7-14 hr wall-time (similar to Phase 7c.2 cohort scope).
- **Downstream Phase 9 stats re-materialization** following cohort re-emit. Several stats axes (per-trial tongue kinematics, recovery trajectories) depend on the endpoint JSON contents.
- **Jaw interpolation revisit** (Phase 7f?) — apply the v7 architecture (cluster classifier + frame outliers + PCHIP-extend + find_peaks + gates) to jaw with re-tuned params. Priya 2026-05-25 deferred this until after tongue v7 production lands.
- **F-gate shape-based refinement** — distinguish wide-real-lick-tops from plateau-drift-wobbles using local curvature (2nd derivative) or quadratic-fit goodness.
- **M-gate non-greedy global selection** — when 3+ peaks cluster within 150ms, current greedy pairwise comparison may drop the wrong peak. Global optimization (maximize total confidence subject to ≥80ms spacing) would fix this but adds complexity.
- **X-coordinate interpolation review** — outcome from Task 0 (verdict either no-action or action-needed).

---

## Files to read at session start

Required:
1. `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py` — the v7 reference implementation. ~980 lines. Annotated by stage matching this kickoff's "v7 algorithm anatomy" section.
2. `.scratch_phase_9_1/inv_p3b_cohort_validation.py` — the validation harness pattern to reuse for Task 8.
3. `.scratch_phase_9_1/dlc_tongue_quality_investigation/part3b_cohort_validation_v7/part3b_stats.csv` — the 80-trial validation outcomes.
4. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` — the production module to wire v7 into.
5. `src/stroke_orofacial/dlc_kinematics/_detector.py` — the legacy detector v7 will run alongside (and eventually deprecate).
6. `configs/defaults.yaml` — the config file to extend.

Optional / context:
7. Any of the 35 outlier figures at `.scratch_phase_9_1/dlc_tongue_quality_investigation/part3b_cohort_validation_v7/v7_*.png` to ground visual intuition.
8. `docs/DECISIONS.md` recent entries from 2026-05-25 (Phase 7e investigation summary).

---

## Estimated commit shape

| # | Title | Files | Lines |
|---|---|---|---|
| 1 | Phase 7e branch setup + Task 0 audit harness | `.scratch_phase_7e/audit_x_imputation.py` | +200 |
| 2 | Externalize v7 constants in defaults.yaml | `configs/defaults.yaml` | +50 |
| 3 | Module scaffolding (preclean.py, detector_v2.py, gates.py) | 3 new | +150 |
| 4 | Port preclean_trace + helpers | `preclean.py` | +400 |
| 5 | Test preclean (synthetic gates) | `tests/dlc_kinematics/test_preclean.py` | +300 |
| 6 | Port detect_local_maxima + dedupe + rise/fall delineation | `detector_v2.py` | +250 |
| 7 | Test detector_v2 (synthetic peaks) | `tests/dlc_kinematics/test_detector_v2.py` | +200 |
| 8 | Port gates F/D/E/M + imputation | `gates.py` | +400 |
| 9 | Test gates (synthetic) | `tests/dlc_kinematics/test_gates.py` | +300 |
| 10 | New PathResolver methods + new parquet writers | `paths.py`, `_writers.py` | +150 |
| 11 | Wire v7 into tongue_pertrial (feature flag) | `tongue_pertrial.py` | +100 |
| 12 | Downstream metrics: velocity gating + angle imputation | `_angle.py` (or new `_velocity.py`) | +150 |
| 13 | 9-canonical-trial parity fixture + test | `tests/fixtures/v7_canonical/`, `test_v7_parity.py` | +500 |
| 14 | 80-trial cohort parity test | `test_v7_cohort_parity.py` | +200 |
| 15 | DECISIONS + MIGRATION_LOG | docs | +200 |
| 16 | Phase 7e close PR + tag | (PR text) | — |

Total: ~3500 lines added, ~10 files touched in `src/`, ~5 test files added.

---

## Q-lock / Open question backlog (for in-phase iteration)

- **Q1.** Should `cleaned_traces/` parquets carry both `y_final` (pre-clean WIPED) AND `y_final_original` (pre-clean input)? Priya 2026-05-25 chose write-to-disk; whether to also preserve the pre-cleaned y in the same parquet is open. Default: NO (avoid storage bloat; the interpolated_traces parquet still has the original).
- **Q2.** Should `lick_events/` parquet include rejected (keep=False) peaks for downstream diagnostic use, or only kept peaks? Default: KEPT ONLY (downstream consumers want canonical lick list). Diagnostic per-trial figures can re-run the full pipeline if needed.
- **Q3.** Backward-compat: should the new `endpoints/` JSON include a `algorithm_version: "v7"` field so consumers can detect v7 outputs? YES — `feature_extraction_version` bumped to `v7e.0`.
- **Q4.** Task 0 x-audit: what threshold counts as "material delta"? Default: > 5 px x-delta OR > 2° angle delta at the imputed peak. Document in addendum.

---

**Session warm-start prompt (paste into fresh CC session as first message):**

> Starting Phase 7e — DLC tongue pre-clean + v7 detector migration to production. Read `docs/prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md` first; reference implementation at `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py` (980 lines, full v7 algorithm). Branch `phase/7e-dlc-tongue-preclean-v7` off latest origin/main. Start with Task 0 (X-coordinate audit) — write the audit script, run on the 80-trial sample, report verdict. Pause before Task 1 (module scaffolding) so I can review the x-audit verdict and confirm the in-phase scope.
