# Project Decisions Log

Project-wide decisions that affect design, architecture, or workflow. Distinct
from per-phase migration notes in `MIGRATION_LOG.md` (which document *what* was
ported) — this file records *why* choices were made, so future readers (human
or agent) can understand intent without re-deriving it.

Entries are reverse-chronological (newest at top). Format:

- **Date — Short title.**
- *Context:* What prompted the decision.
- *Decision:* What was chosen.
- *Rationale:* Why.
- *Enforced at:* Code or docs where the decision lives.

---

## 2026-05-01 — Phase 7a.3-jaw audit confirms no per-trial features in jaw notebook (Outcome A — confirmed empty)

**Context.** Phase 7a.3 V3 merged 2026-04-29 with the per-trial-features
work scoped to the tongue bodypart only. The 2026-04-25 V2 audit
(during 7a.3 V3 scoping) reported incidentally that the canonical jaw
notebook contains no per-trial features in the form 7a.3 V3 ported for
tongue — specifically, Cell 41 was flagged as a copy-paste of tongue
code against jaw-non-existent files. That finding was incidental
to scoping 7a.3 V3, not a formal audit. Phase 7a.3-jaw is the formal
audit that confirms or refutes it.

**Decisions enacted.**

1. **Phase 7a.3-jaw scope.** Audit-first formal investigation of
   whether the canonical jaw notebook contains per-trial features
   worth porting (parallel to 7a.3 V3's tongue per-trial work).
   Locked Task 1 (audit) only at kickoff time; Tasks 2-N depended on
   audit outcome. Outcome resolved at Task 1 STOP-and-report.

2. **Audit provenance.** Canonical:
   `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`.
   SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`,
   434 MB (mostly embedded plot outputs from per-session figures × the
   8-animal cohort), 45 cells (25 code at 7,293 lines + 20 markdown).
   3-tier disambiguation: latest-dated within jaw family;
   `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` is a
   sibling-different-scope (parquet build, not pertrial);
   `20251117_DLC_analysis_jaw.ipynb` is an older variant superseded by
   the date-priority rule. The canonical SHA matches the SHA cited in
   the 7a.3 V3 MIGRATION_LOG ("jaw notebook (SHA256
   `7BE0EEE0...49E95DF`)") — confirms same source the V2 incidental
   audit looked at, no drift.

3. **Per-cell classification.** 9 infrastructure (load / merge /
   one-off fixup) — Cells 1, 3, 5, 7, 13, 14, 15, 16, 18; 6 exploratory
   (in-memory plots, no save) — Cells 9, 11, 20, 24, 26, 28; 1
   production-already-ported (Cell 22 = 7a.2 jaw v5p3 interpolation);
   6 production-viz (PNG figures saved to disk) — Cells 30, 32, 34,
   37, 39, 43; 2 broken (Cells 41, 42 — see Decision 5); 1 empty
   (Cell 44).

4. **Per-trial feature inventory: EMPTY.** Zero matches across 7,293
   code lines for tongue-side extraction signatures
   (`_first_run_from`, `rise_mask`, `slope_thr`, `np.gradient`,
   `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES`, `RISE_MIN`/`FALL_MIN`,
   `bout_max_ili`, `MIN_LICKS_IN_BOUT`, `n_phase_bins`,
   `phase_peak_to_peak_shifted`, `arctan2`/`angle_signed`,
   `find_peaks`, `argmax`+`lick`, `lick1_y_peak`,
   `tongue_angle_pass`). No per-trial scalar emit anywhere in the
   notebook — no NPZ, CSV, or parquet writers carrying per-trial
   shapes. The only data-emit sinks are: alignment-fixup NPZs
   (Cells 15-18, infrastructure), Cell 22's interpolation outputs
   (already in 7a.2), and PNG figures from Cells 30/32/34/37/39/43
   (visualization only).

5. **Cell 41/42 V2 incidental finding fully confirmed.** Three
   independent pieces of evidence:
   (a) `_mouse_base()` returns
       `{mouse}_jaw_kinematics/{CENTER_MODE}/` directly while the real
       on-disk path is
       `{mouse}_tongue_kinematics/kinematics_figures/{CENTER_MODE}/lick_metrics/...`
       — path structure mismatch.
   (b) Filename pattern is `_dydt_v5.csv` while real tongue files are
       `_v5p3.csv`; no `_v5` files exist anywhere on jaw or tongue
       side (verified via `find` over PS46's
       `O2_analysis/PS46/`).
   (c) `find` confirmed zero `*pertrial*` files anywhere under
       `PS46_jaw_kinematics/`. Tongue side has many.
   The METRICS list (`t_peak_ms`, `y_peak`, `x_at_ypeak`,
   `vy_trialmax`, `vxy_trialmax`) matches tongue Cell 33 + Cell 36
   outputs exactly — proves these are tongue metric names with the
   `tongue→jaw` token swap pointing at non-existent files. Cells 41/42
   are not portable as-written.

6. **Tongue analog comparison.** Cells 33/36/39/42/50 (the 5 tongue
   per-trial cells 7a.3 V3 ported) have **NO jaw analog**: 5/5 absent.
   The jaw notebook's analytical scope stops at per-frame interpolation
   (Cell 22 → 7a.2) + per-session plotting (Cells 30/32/34/37/39/43).
   The interpolation-trace parquet schemas are bit-identical between
   bodyparts (7-column shape: `frame_idx`, `x_final`, `y_final`,
   `likelihood_raw`, `is_interp_fill`, `is_baseline_fill`,
   `fill_method`); only `Y0` (jaw `310.0` vs tongue `-110.0`) and
   `center_mode` (jaw `centered_eye_midpoint` vs tongue
   `centered_spout_midpoint`) differ — 7a.2 lock holds.

7. **Cell 43 PSD note (out of 7a.3-jaw scope).** Cell 43 is the only
   jaw-unique production output: `scipy.signal.welch` PSD on the first
   10 minutes of `jaw_x` and `jaw_y` per session, plotted with broken
   Y-axis (75/25 vertical split), saved as PNG. Per-session
   frequency-domain QC, not per-trial behavior. Deferred to a future
   face-rhythmicity QC phase or `docs/phase-7/interpolation-strategy.md`
   §7 face-velocity / PSD phase if downstream demands it. Out of
   7a.3-jaw scope per the audit-first charter.

8. **Outcome A acceptance.** Phase closes as a small docs PR (~3
   commits total: kickoff + DECISIONS + MIGRATION_LOG + PR-prep). No
   code changes. No new tests. No new configs. No parity harness.
   The audit alone is the deliverable. Confirms the V2 incidental
   finding rigorously enough to close the open question durably.

9. **Forward implication — jaw per-trial features as future work.**
   The canonical jaw notebook carries per-trial-stats stubs (Cells
   41/42) but lacks the per-trial-EXTRACTION cells that would feed
   them. If the experimental intent is "we want jaw per-trial
   behavior features analogous to tongue," that's a separate
   green-field design phase: scientific question (what jaw motions
   matter biologically — chewing dynamics? jaw protrusion-velocity
   for non-licking behaviors? jaw-tongue coordination?), detector
   design (slope detector tuned for jaw kinematics ≠ tongue
   protrusion kinematics), parity (synthetic-only since no legacy
   reference exists). Tracked here as a forward-pointer; not a
   7a.3-jaw concern.

10. **Tag.** `v7a.3-jaw-audit-no-pertrial-features` — descriptive of
    both the deliverable (audit) and the finding (no per-trial
    features). Priya's call to apply post-merge per CLAUDE.md ground
    rule 8.

**Enforced at.**

- [`docs/prompts/phase-7a.3-jaw-kickoff.md`](prompts/phase-7a.3-jaw-kickoff.md)
  — phase plan codifying the audit-first scope + Outcome A/B/C
  branches.
- This DECISIONS entry — codifies the audit findings durably.
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) Phase 7a.3-jaw entry —
  what landed (audit only).
- No code, no config, no test changes. The audit is the deliverable;
  there is no enforcement surface to point at beyond the docs.

**Forward follow-ups (post-7a.3-jaw PR merge).**

- **Phase 7a.x-jaw-pertrial-design** (green-field) — only if jaw
  per-trial features become a research need. Separate scientific +
  engineering design discussion. Distinct from "port the existing
  legacy jaw work" (which is what 7a.3-jaw was chartered for and
  found nothing to port).
- **Cell 43 PSD port** to a future face-rhythmicity QC / strategy
  §7 face-velocity / PSD phase if downstream demands it.
- **Cohort-wide 7a.2/7a.3 upstream re-emit** (carries forward from
  7a.4 deferred follow-ups, unaffected by this phase).

---

## 2026-04-30 — Phase 7a.4 Cell 50 visual gate + Cell 42 day-binned cross-session traces (closes 7a.3 V3 carve-outs)

**Context.** Phase 7a.3 V3 merged 2026-04-29 with two carve-outs deferred:
(1) the Cell 50 visual gate (legacy `angle_phase_exploratory/` figure
comparison was scoped out — 7a.3 V3 acceptance was unit-test correctness
+ schema lock); (2) the Cell 42 `*_dayBinnedTraces_*.csv` cross-session
aggregator (per-session traces shipped in 7a.3 V3 but day-binning over
per-animal `bin_days` was deferred). Phase 7a.4 closed both. Two new
plotting / aggregator paths consume 7a.3 V3's locked outputs without
modifying its core modules.

**Decisions enacted.**

1. **Phase 7a.4 scope.** Bundle the two 7a.3 V3 carve-outs into a single
   PR for review economy. No new bodypart work, no Phase 7a.3-jaw, no
   algorithm changes to 7a.3 V3 modules. Both carve-outs consume locked
   inputs; visual gate is rendering only, day-binner is a post-emit
   aggregator.

2. **Cell 50 visual gate ACCEPTED.** Per-frame angle parquet + per-trial
   endpoints JSON + Task 4 unit tests on synthetic geometry stand as
   algorithmic acceptance for 7a.3 V3 Cell 50. Visual fidelity verified
   in 7a.4 via 24 comparison grids across 4 sessions
   (PS50/2025-03-19 + PS46/{2025-03-07, 2025-03-10, 2025-03-13}). All
   6/6 legacy-PNG matches per session. Priya's eyeball verdict: PASS,
   with documented minor lick-count delta in the phase-aligned plot
   annotations — downstream visual reflection of CSV-stale (Cell 39)
   and Cell 42 numerical-precision residuals already accepted in 7a.3 V3
   cohort parity, NOT a new finding.

3. **Day-binned acceptance via algorithmic correctness path
   (Option 2 from Task 5d STOP-and-report).** Cohort-vs-legacy CSV
   parity has a structural blocker: consolidated 7a.2/7a.3 emit covers
   15 sessions across 8 animals (the 14-session parity cohort);
   legacy aggregates over ~120 sessions (all per-animal NPZs).
   `max|Δ|_n_support_sessions = 6` cohort-wide is the smoking gun.
   Cell-by-cell mean parity is arithmetically not achievable at the
   current upstream emit scope (`bout_rate_mean_hz` happens to be
   bit-identical because legacy + consolidated NaN-mask the same
   support-zero bins; the other 3 metrics drift by aggregation
   arithmetic over different session sets). Algorithmic correctness
   instead established via:
   (a) 18 unit tests on synthetic input
       ([`tests/test_day_binned.py`](../tests/test_day_binned.py));
   (b) chain composition with locked 7a.3 V3 input — the 7a.3 V3 cohort
       parity already validated the per-session traces parquet
       bit-identical in `legacy_approximate` mode; the day-binner is
       a deterministic `np.nanmean` aggregation on top.
   Cohort-wide upstream re-emit deferred as a publication-grade
   follow-up (forward note below).

4. **Bundle helper additive pattern.** `TongueVisualBundle` +
   `build_tongue_visual_bundle` added to
   [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py).
   Bit-identical compute path to `build_tongue_pertrial`; verified via
   14-session parity-harness re-run matching the V3 cohort by_status
   exactly (Cells 33+36 max\|Δ\| ≤ 5.7e-14 / 1.8e-12; Cells 39+42 same
   residual bands; same `{pass:1, fail:12, skip_missing:1}`). Net-new
   compute (~400 lines for `_bout_time_bounds_ms`,
   `_assign_phase_peak_to_peak_shifted`, `_build_visual_bundle_per_trial`)
   reuses 7a.3 primitives — same algorithm, just keeps array outputs
   (`y_snip`, `angle_snip`, per-bout/per-peak rows, per-frame phase rows)
   that 7a.3 V3's emit path discards. **Constraint relaxation
   2026-04-29**: additive public helpers on 7a.3 V3 modules are allowed
   if they expose existing in-memory products without algorithm changes.
   Codified in the 7a.4 kickoff Constraints section.

5. **Phase convention.** `phase=0` at tongue emergence (start of
   protrusion), `phase=0.5` at maximal tongue protrusion (the detected
   peak), `phase=1` at tongue return (end of protrusion). Implemented
   in `_assign_phase_peak_to_peak_shifted` — peak frames map to
   `phase ≈ 0.5`. Verified by regression test
   `test_phase_assignment_places_peaks_at_0_5_not_at_boundary` in
   [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
   `TestVisualBundle`.

6. **C5.5 port-bug fixes (phase shift + QC angle-subplot dot offset).**
   Both bugs surfaced by Priya's eyeball verdict on the visual gate.
   Both traced to a single docstring inaccuracy in the 7a.3 V3
   `_LickPeaks` dataclass: `peak_indices` is yseg-local (relative to the
   detect-window subset `yseg = y_t[i_lo:i_hi+1]`) but the docstring
   claimed it indexes into the trial slice. The 7a.3 V3 emit-set never
   tripped this because Cells 33/36/39/42 only consume `peak_times_ms`
   and `peak_y` (which are pre-offset via `tseg = t_ms[i_lo:i_hi+1]` /
   `yseg` indexing). The 7a.4 bundle helper was the first consumer to
   use `peak_indices` directly, so the off-by-`i_lo` propagated into
   the phase array and the per-peak `peak_angle_deg` lookup.
   Fixed at the call site in C5.5 by adding
   `detect_lo_offset = i_lo` to `peak_indices` before consumption;
   docstring corrected in C5.6 to prevent future consumers from
   falling into the same trap. Demonstrates the value of the visual-
   gate tier in the test pyramid — unit tests + parity harness +
   visual gate caught different bug classes (the visual gate caught
   both port bugs that the unit tests + parity harness missed).

7. **SEM convention split.**
   [`_day_binned.py`](../src/stroke_orofacial/dlc_kinematics/_day_binned.py)
   aggregator emits `ddof=1` (unbiased estimator, divided by
   `sqrt(n_support)` per cell) — correct convention for downstream
   analytical consumers. `_plot_phase_aligned_angle` in
   [`tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py)
   uses `ddof=0` (legacy Cell 50 convention; ensures visual fidelity
   vs the saved legacy figures). Different conventions for different
   contexts; both correct. The day-binned parity harness applies the
   inverse transform `SEM_legacy(ddof=0) = SEM_cons(ddof=1) *
   sqrt((n_support - 1) / n_total)` for legacy comparison.

8. **Vendored atomic writer in `_day_binned.py`.** 4-line helper
   duplicating the pattern from
   [`_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py).
   Deliberate trade-off — keeps 7a.3 V3's `_writers.py` untouched per
   the algorithm-lock constraint. Post-7a.4 cleanup opportunity:
   factor into a shared `_io_helpers.py` if a third consumer surfaces.

9. **Per-metric `*_n_support_sessions`.** Each of the 4 day-binned
   output metrics (`lick_rate_per_t`, `bout_rate_mean_hz`,
   `p_lick_per_t`, `p_within_bout_per_t`) tracks its own
   NaN-pattern-aware support count — legacy precedent
   (`ili_within_bout_rate_per_t` is NaN-masked at session level where
   the `MIN_TRIALS_PER_BIN<3` filter triggers, while the other 3
   metrics have full support across most timebins).

10. **Metric rename in day-binned schema.**
    `ili_within_bout_rate_per_t` (7a.3 V3 per-session traces parquet
    column) → `bout_rate_mean_hz` (day-binned output base name). More
    descriptive in the day-binned context where the per-session
    `_per_t` suffix becomes ambiguous after cross-session aggregation.
    Other 3 metrics keep their 7a.3 V3 names for traceability.

11. **`bin_days` per-animal placement.**
    [`configs/animals.yaml`](../configs/animals.yaml) (NOT
    `configs/defaults.yaml`) since it's per-animal data. PS46-50 → 2;
    PS51/PS54/PS55 → 7. PS47/PS48/PS49 inherit the cohort default;
    PS52/PS53 don't exist in the cohort (vendored `MOUSE_SPECS`
    confirmed 8 animals only). `AnimalInfo.bin_days: int = 1` default
    is fail-conservative for any future animal joining the cohort
    without an explicit declaration.

12. **Cross-session overlay families deferred.** Legacy emits
    additional plot families beyond the 5 ported (`_plot_overlay_grid_all_sessions`
    + `_plot_overlay_grid_binned` in vendor lines 4826-5096). Per-mouse,
    not per-session. Out of 7a.4 scope per kickoff §"Phase 7a.4 scope".
    Available for a follow-up visual-extension phase if downstream
    demands.

**Enforced at.**

- [`docs/prompts/phase-7a.4-kickoff.md`](prompts/phase-7a.4-kickoff.md)
  — phase plan + constraint codification.
- [`configs/animals.yaml`](../configs/animals.yaml) `bin_days:` field +
  loader validation in
  [`src/stroke_orofacial/animals.py`](../src/stroke_orofacial/animals.py).
- [`configs/defaults.yaml`](../configs/defaults.yaml)
  `dlc_kinematics.tongue_pertrial.day_binned:` + sibling
  `dlc_kinematics.tongue_visual:` blocks.
- [`src/stroke_orofacial/dlc_kinematics/_day_binned.py`](../src/stroke_orofacial/dlc_kinematics/_day_binned.py)
  + [`tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py)
  + additive helpers in
  [`tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py).
- 36+ new tests across
  [`tests/test_day_binned.py`](../tests/test_day_binned.py) (18),
  [`tests/test_tongue_visual.py`](../tests/test_tongue_visual.py) (13),
  + 5 new TestVisualBundle tests in
  [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py).

**Forward follow-ups (post-7a.4 PR merge).**

- **Cohort-wide 7a.2/7a.3 upstream re-emit** + day-binned cohort
  parity re-run vs legacy CSV (~120 sessions across 8 animals;
  expected residual band 0.018-0.05 Hz matching 7a.3 V3 Cell 42).
- **Cross-session overlay plot families** — the 2 deferred legacy
  plot families that aggregate per-mouse not per-session.
- **Phase 7a.3-jaw visual gate** — extends the same machinery once
  jaw per-trial features land.
- **`licks_npz(animal, date)` PathResolver factor-out** from 7a.3
  (carryover follow-up).
- **NaN-walking captured-fixture regression test** (the 7a.3 V3 test
  gap dropped in C5.1; 7a.4 didn't naturally surface a fixture
  candidate).

---

## 2026-04-29 — Phase 7a.3 V3 tongue per-trial features (post-vendor design lock + cohort parity)

**Context.** Phase 7a.3 V1 (kickoff `41304c6`, 2026-04-24) was scoped wrong;
audit on 2026-04-25 caught it pre-code. V2 (kickoff `1f3f7ff`, 2026-04-25)
rewrote against actual legacy and vendored Cells 33/36/39/42/50 from the
canonical tongue notebook (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
SHA256 `ED12C54C...DABDB643`) into [`docs/legacy_snippets/tongue_pertrial_features.py`](legacy_snippets/tongue_pertrial_features.py)
(commit `0b78128`, 5,428 lines). The V2-vendor STOP-and-report
(2026-04-28) surfaced 7 design-mismatch findings — per-cell detector
knob differences, per-cell window differences, Cell 50 eye-midpoint
resolution path, Cell 42 dual-output schema, Cell 39 richer metric set,
Cell 50 per-trial scalars defined as new V3 features, no `tongue_angle_pass`
in legacy. V3 (this entry) resolved every one.

V1 + V2 + vendor commits are preserved in branch history — they are the
paper trail of how the design was sharpened. V3 is what shipped.

**Decisions enacted.**

1. **Branch + tag rename.** V1 `phase/7a.3-kinematic-features-tongue-jaw`
   → `phase/7a.3-tongue-pertrial-features` (2026-04-25 post-audit).
   Tag plan `v7a.3-tongue-pertrial-features` (Priya tags on merge per
   CLAUDE.md).

2. **Tongue-only scope.** Jaw per-trial features deferred to a future
   Phase 7a.3-jaw with its own design discussion. The jaw notebook
   (SHA256 `7BE0EEE0...49E95DF`) Cell 41 was a copy-paste of tongue
   code against files the jaw notebook never produces.

3. **Three output products** (replaces V2's two).
   - Per-frame angle parquet at
     `<outputs>/dlc_kinematics/features/tongue/<animal>/<YYYYMMDD>.parquet`
     (2 cols: `frame_idx` int64, `angle_deg_smoothed` float64; 10
     file-level metadata keys: animal, date, fps, n_frames, center_mode,
     eye_in_spout_frame_x/y, smoothing_gaussian_sigma_ms,
     angle_sign_flip, feature_extraction_version, interpolation_version).
   - Per-session × side licking-dynamics traces parquet at
     `<outputs>/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet`
     (6 cols: timebin_ms, side, lick_rate_per_t,
     ili_within_bout_rate_per_t, p_lick_per_t, p_within_bout_per_t;
     17 file-level metadata keys).
   - Per-trial endpoints JSON at
     `<outputs>/dlc_kinematics/endpoints/<animal>/<YYYYMMDD>.json`
     (`schema_version="v7a.3"`, top-level `trial_indices` + `sides`
     parallel lists, 6 sub-blocks under `tongue.*`, top-level
     `session_inclusion`).
   - Output paths use `%Y%m%d` (matches 7a.2 `interpolated_trace`).
     Input centered_spout_midpoint glob uses `date.isoformat()`
     (matches the upstream filename's hyphenated YYYY-MM-DD
     convention).

4. **Eye_midpoint = session-wide MEDIAN** of per-frame eye_midpoint
   from the consolidated centered_spout_midpoint parquet. Resolution
   algorithm: `EYE_LIK_THR=0.70`, `MIN_VALID_EYE_FRAMES=100`,
   `0.5*(median(L_eye)+median(R_eye))`, `ALLOW_ONE_EYE_FALLBACK=True`.
   No translation step (input parquet is already in spout-centered
   frame; verified empirically by Task 1.5 sanity check below).

5. **Spout-frame sanity check on load** (Task 1.5 finding 2026-04-28;
   refined C5.6 2026-04-29 after Task 5c cohort emit). The input
   parquet has no `center_mode` / `spout_x_raw` / `spout_y_raw`
   metadata, so verify empirically: assert
   `|0.5 * (median(L_spout) + median(R_spout))| <= 2.0 px` on both x
   and y. **C5.6:** filter L/R spout values by likelihood ≥ 0.7
   (matches the upstream centering algorithm's quality bar at
   [`src/stroke_orofacial/dlc_io/centering.py:_median_from_lik`](../src/stroke_orofacial/dlc_io/centering.py)).
   Without the filter, sessions with bimodal degraded R_spout DLC
   tracking (e.g. PS55/2025-05-02: 92% of frames are low-lik and
   drifted to L_spout's image x ≈ 472, pulling the median to +67 px)
   would erroneously fail the check despite the centering being
   correctly applied. Fail loud rather than silently emit angles in
   the wrong frame.

6. **Tongue angle math** (Cell 50 vendored):
   `degrees(atan2(cross(B, A_t), dot(B, A_t)))` with
   `A_t = tongue_centered(t) − eye_in_spout_frame`,
   `B = −eye_in_spout_frame`. `ANGLE_SIGN_FLIP = −1.0` baked INSIDE
   atan2 (legacy convention; do not move outside). Smoothed gaussian
   σ = 8 ms AFTER atan2 via NaN-aware `_gaussian_smooth_nan`
   (`gaussian_filter1d(mode="nearest")` with `num/den` finite-mask
   normalisation).

7. **Tongue trace input** = `x_final, y_final` from the canonical
   7a.2 interpolated_traces parquet (option 50d).

8. **Unified slope detector across all 5 cells** with per-cell knob
   overrides via `detector_per_cell:` + `bout_per_cell:` blocks
   (C5.2). The shared detector reads the base `detector:` and `bout:`
   knobs, then a `_per_cell_detector(params, cell_key)` /
   `_per_cell_bout(params, cell_key)` helper applies a shallow merge
   of any per-cell overrides on top. Default mode has empty per-cell
   dicts → no behavior change vs the V3 design intent. Legacy_approximate
   mode uses the per-cell mechanism to recover bit-identical legacy
   semantics that a single global knob set can't represent (legacy
   had per-cell-different `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES_PER_LICK`,
   `DO_SMOOTH_Y_FOR_DETECTION`, `bout.max_ili_ms`, and
   `accept_peaks_without_fall_run` semantics).

9. **Three detector port-bug fixes** (C5.1) surfaced by Task 5b smoke
   parity:
   - **Turnover loop NaN-walking + boundary** (legacy
     `tongue_cell33.py:326`): `while k < L and (not isfinite(dy[k])
     or dy[k] > 0)`. Pre-fix used `while k < L − 1 and (isfinite(dy[k])
     and dy[k] > 0)` — wrong on NaN dy and off-by-one on the L
     boundary.
   - **Next-lick start = `end_idx + 1`** (post-fall-run-end), not
     `i_peak + 1`. Pre-fix could re-detect a phantom peak inside the
     first peak's fall edge.
   - **STRICT_NO_FALLBACK rejects peaks with no fall run** (Cell 33
     legacy). Pre-fix accepted such peaks; the new
     `accept_peaks_without_fall_run` knob (default False = Cell 33
     strict / V3 design intent; per-cell override True for Cells
     36/39/42 in `legacy_approximate`) controls this branch (C5.5).

10. **Per-cell windows are locked** (V3): Cells 33/36 narrow `[70, 3000]`;
    Cells 39/42/50 wider `[70, 8000]` detect / `[70, 5000]` apply;
    Cell 39 binning `[70, 5070]` for clean 1-s bins. Wrapper-mode
    (legacy_approximate) restores legacy windows.

11. **Bout config** (V3): `bout.max_ili_ms = 300` unified (legacy Cell
    42 was 400 — restored via per-cell `bout_per_cell.cell42` override
    in legacy_approximate). `bout.min_ili_ms = 80`,
    `bout.min_licks_in_bout_for_ili = 3`,
    `bout.single_bout_win_ms = [-120, 200]`. Three bout modes
    (`all`, `first_bout`, `first_multi_bout`) declared per metric in
    `defaults.yaml.bout_mode:`.

12. **Cell 39 enriched output** (V3): `n_licks`, `n_left`, `n_right`,
    `n_other` (using `±5.0 px` direction thresholds, surfaced as YAML
    knobs), `lick_ge10`, `n_licks_per_bin: int[5]`.

13. **Cell 42 dual emission (option 42c)**: per-session × side
    time-binned traces parquet PLUS per-trial reductions
    (`bout_count`, `mean_within_bout_ili_ms`, `lick_rate_hz`) in the
    JSON. Day-binned traces NOT ported (deferred).

14. **Cell 50 promoted to production** despite the legacy author's
    "exploratory" filename label (Priya 2026-04-25).

15. **Cell 50 per-trial scalars are NEW V3 features** (no direct
    legacy parity): `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak`
    (Cell 33 timestamps), `angle_at_peak_velocity_bylick (n_trials, 5)`
    (Cell 36 timestamps), `angle_max_signed_per_lick (n_trials, 5)`.
    Validated by unit tests + visual gate. No
    `tongue_angle_pass: bool[n_trials]` emitted.

16. **`n_licks_in_first_multi_bout` per-trial scalar** (Q9 2026-04-28)
    is a Cell 50 own-bout-scalar emission (NOT a Cell 42 reduction).
    Realigned post-Task-3 (commit `2dd5128`). Feeds session-inclusion
    `n_phase_licks` aggregation
    (`sum(n_licks_in_first_multi_bout)` across trials).

17. **Session-level inclusion thresholds** (replaces V1/V2's
    per-trial `tongue_angle_pass` mask): four legacy thresholds as
    YAML knobs (`min_time_trials_per_session=0`,
    `min_firstpeak_trials_per_session=5`,
    `min_phase_licks_per_session=15`,
    `min_phase_trials_per_session=5`), four booleans in JSON
    `session_inclusion` block.

18. **Trial events auto-derived** from upstream pipeline products
    (Task 5.0). Re-uses 7a.2's path resolution + `load_reward_events`
    + `ws_samples_to_frame_indices` public helpers. NO new alignment
    code — the auto-derive helper is a thin orchestration of existing
    battle-tested infrastructure. Mouse-frame side coords already
    applied by Phase 6.8 boundary at the licks_and_rewards NPZ emit;
    7a.3 reads them verbatim. `trial_index` is chronological-across-sides
    (Option α 2026-04-28); per-side parity re-keying is the parity
    harness's job.

19. **Smoke target.** PS50 / 2025-03-19. 96 trials auto-derived
    end-to-end on the smoke session.

20. **Parity strategy.** legacy_approximate mode wraps the V3 detector
    with legacy-faithful per-cell knob overrides (windows + per-cell
    `MIN_PEAK_Y_ABS` / `MIN_FINITE_SAMPLES_PER_LICK` /
    `DO_SMOOTH_Y_FOR_DETECTION` / `accept_peaks_without_fall_run` /
    `bout.max_ili_ms`) and compares against legacy CSV/NPZ at
    `atol=1e-6` on the 14-session cohort. Default mode emits to the
    canonical pipeline_outputs tree as cohort deliverables. The parity
    harness uses Option O1 (temp `output_root` for the
    legacy_approximate emit) so the canonical default-mode outputs
    aren't clobbered. The harness reads inputs from MICROSCOPE via a
    `_HarnessResolver` wrapper (delegates everything to a canonical
    PathResolver except the three tongue_pertrial output methods,
    which route to temp).

21. **Cell 50 visual gate DEFERRED** (kickoff §5b.7 + Priya's 5d.A
    sign-off). Per-frame angle parquet emit-confirmation + Task 4 unit
    tests on synthetic geometry stand as Cell 50's acceptance criteria
    for this PR. Side-by-side comparison against
    `O2_analysis/PS46/PS46_tongue_kinematics/kinematics_figures/
    centered_spout_midpoint/angle_phase_exploratory/` legacy figures
    is a follow-up phase.

**Parity verification (legacy_approximate, atol=1e-6, 14-session cohort).**

| Cell | Pass | Fail | Verdict |
|---|---:|---:|---|
| 33 | 13/13 | 0 | bit-identical cohort-wide (max\|Δ\| 0 to 5.7e-14) |
| 36 | 13/13 | 0 | bit-identical cohort-wide (max\|Δ\| 0 to 1.8e-12) |
| 39 | 9/13 | 4 | CSV-stale residual, accepted (see below) |
| 42 | 1/13 | 12 | CSV-stale propagation (4) + small drift (8), accepted (see below) |

PS54/2025-05-12: `skip_missing` (known data gap inheriting 7a.1/7a.2
pattern; same session was skip_missing in both prior phases by Priya
2026-04-22 sign-off). 13 sessions in scope numerically.

**Cell 39 + Cell 42 residual: CSV-vs-vendored-code stale, accepted
(2026-04-29).** Direct execution of the vendored Cell 39
`_lick_peaks_from_y_dydt` function on the residual sessions produces
peak counts bit-identical to the consolidated module's output but
disagrees with the saved legacy CSV by exactly 1 peak per affected trial
(~2 trials per session, ~2% of trials cohort-wide). The saved CSVs were
emitted by an older legacy-code revision than what was vendored;
consolidated → vendored is the load-bearing parity. The discrepancy is
irreducible at the consolidated module level and would require
regenerating the CSVs from the vendored code (out of 7a.3 scope).

**Cell 42 small-drift band (0.018-0.033 Hz on ~10 Hz lick-rate traces)
accepted (2026-04-29).** Cohort-wide on 8 sessions where Cell 33/36/39
are bit-identical but Cell 42 traces differ by ≤0.04 Hz — 0.2% relative,
well below any meaningful threshold for a per-bin trace metric. Likely
numerical-precision sensitivity in `np.histogram` bin-edge inclusion or
smoothing kernel arithmetic at sub-frame peak positions.

**Enforced at.**

- [`configs/defaults.yaml`](../configs/defaults.yaml)
  `dlc_kinematics.tongue_pertrial:` block (windows + detector +
  detector_per_cell + bout + bout_per_cell + bout_mode +
  direction_thresholds + n_licks_categorical + n_licks_binning +
  licking_dynamics + angle + session_inclusion + phase + version
  stamps).
- [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py)
  (main): public API, dataclasses, loaders + 7-step eye-midpoint
  resolver with C5.6 likelihood-filtered spout-frame sanity check,
  `_extract_trial_slice`, Cells 33/36/39/42 extractors,
  `_derive_trial_events_from_spout_behavior`, driver core.
- [`src/stroke_orofacial/dlc_kinematics/_detector.py`](../src/stroke_orofacial/dlc_kinematics/_detector.py):
  unified slope detector (post-C5.1 fixes), `_LickPeaks`,
  `_first_run_from`, `_build_bouts`, `_filter_peaks_by_bout_mode`,
  with `accept_peaks_without_fall_run` knob (C5.5).
- [`src/stroke_orofacial/dlc_kinematics/_angle.py`](../src/stroke_orofacial/dlc_kinematics/_angle.py):
  Cell 50 angle math + NaN-aware gaussian smoothing + per-trial scalar
  sampling + own-bout scalars (incl. Q9
  `n_licks_in_first_multi_bout`) + session-inclusion evaluator.
- [`src/stroke_orofacial/dlc_kinematics/_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py):
  three atomic writers (parquet × 2 + JSON, temp + os.replace) +
  `_jsonify`.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
  +4 resolver helpers (3 output, 1 input glob).
- [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
  52 tests (37 cell extractors + driver/schema, 6 trial-events
  auto-derive, 3 slope-detector port-bug fixes, 4 per-cell knob
  overrides, 1 likelihood-filtered sanity check, 1 accept-no-fall
  knob).
- [`tests/scripts/parity_phase7a3_tongue_pertrial.py`](../tests/scripts/parity_phase7a3_tongue_pertrial.py)
  scope filter, `_HarnessResolver`, 4 legacy readers, 4 comparators,
  per-trial re-keying (Option α ↔ legacy per-side), argparse +
  by_status summary print.

**Forward implications.**

- **Phase 7a.3-jaw** mirrors this structure with jaw-specific design.
- **Future face-velocity / PSD / mismatch-classifier phases** consume
  the 7a.3 V3 outputs (per-frame angle parquet + per-session traces
  parquet + per-trial endpoints JSON).
- **Available follow-up tasks (post-7a.3 PR merge):**
  - **Cell 42 day-binned cross-session traces** (deferred from V3 §3a).
  - **Cell 50 visual gate** (rendering the 5 plot families per session
    + side-by-side compare against legacy `angle_phase_exploratory`
    figures).
  - **Regenerate stale legacy CSVs** from the vendored code (would
    close the Cell 39 + Cell 42 residual at exact parity, but requires
    running the legacy notebook with write access — out of 7a.3
    scope).
  - **Factor `licks_npz(animal, date)` into PathResolver** (currently
    7a.2 + 7a.3 both hardcode the same path inline; deferred per Priya
    2026-04-28).
  - **Per-frame eye-midpoint emit** (currently the resolver computes
    session-wide median internally; downstream phases that want
    per-frame eye_midpoint would need to re-derive).

---

## 2026-04-24 — Phase 7a.2 interpolation port + Knob resolutions codified

**Context.** Phase 7a.2 ported the v5p3 7-stage interpolation pipeline
(tongue Cell 23 + jaw Cell 22, vendored at `docs/legacy_snippets/`) into
`src/stroke_orofacial/dlc_kinematics/interpolation.py`. The 8 knob
decisions from `docs/phase-7/interpolation-strategy.md` §10 — previously
locked in prose only — are now executed in code + config. This entry
records them as the standing architectural baseline for all future
edits to the DLC kinematics interpolation.

**Decisions enacted (strategy §10 knobs, now code-enforced).**

1. **Knob 1 — split emit.** Canonical parquet (7 columns per frame +
   9 file-level metadata keys) + optional `.qc.npz` sidecar (7-stage
   intermediate arrays + diagnostic scalars). Parquet is what
   downstream phases (7b, 7c, 7e, 7f) consume; QC NPZ is opt-in via
   `build_interpolated_trace(..., emit_qc_bundle=True)`.
2. **Knob 2 — PCHIP with linear fallback.** Interpolation method is
   not a runtime-tunable knob — exposed in `configs/defaults.yaml` as
   `dlc_kinematics.interpolation_method: pchip` /
   `interpolation_fallback: linear` with an explicit "do not change
   without DECISIONS entry" comment.
3. **Knob 3 — forced baseline default; data-driven path preserved.**
   `baseline.force: true` in `configs/defaults.yaml` for both
   bodyparts; per-animal `(X0, Y0)` read via
   `AnimalInfo.get_kinematics_baseline(bodypart)` (seeded in PR #81 /
   Phase 7a.1 from the PR #79 baseline probe).
4. **Knob 4 — `x_range_source="lk"` for port parity.** Preserves
   bit-identity against legacy NPZs. Revisiting to `"finite"` is a
   post-7a scope change; the forward exit ramp is documented in
   `interpolation-strategy.md` §2.
5. **§5 Option A — pure-bodypart parquet.** No per-reward side labels
   in the interpolated-trace parquet. Side labels enter downstream at
   7b/7c per-trial endpoint modules that re-read reward events from
   Phase 2 `licks_and_rewards/{animal}/{date}.npz` and apply the
   boundary-layer L↔R translation at emit (per v6.8 convention).
6. **§3.1 — per-animal `(X0, Y0)` in `configs/animals.yaml`.**
   Faithful port of the legacy manual-editing protocol, NOT a bug fix;
   legacy `O2_analysis/PS*/...` NPZs carry the actually-used baselines
   for each run. Cohort-wide values seeded in PR #81 (16 STABLE combos
   under the scope-filtered re-analysis).

**Data-driven-baseline pool unification (Task 2 fixup Item 1).**

- *Context:* The vendored cells used *separate* `(lk_thr, percentile)`
  pools for Y0 and X0 baselines (tongue: `BASELINE_Y_LK_THR=0.7`,
  `BASELINE_Y0_PERCENTILE=1.0` vs. `BASELINE_X_LK_THR=0.4`,
  `BASELINE_X0_FROM_Y_PERCENTILE=25.0`; jaw similarly diverges).
  Strategy §7 + the Phase 7a.2 kickoff consolidate these into one
  pool: Y0 = median of Y over the lowest-`y0_percentile`th Y subset
  under the hi-lk mask; X0 = median of X over the SAME subset.
- *Decision:* Under `baseline.force=false` the consolidated module
  uses the unified single-pool semantics, intentionally diverging
  from the legacy separate-pool semantics.
- *Rationale:* Fewer knobs; matches the simpler `interpolation-
  strategy.md` §7 contract; parity against the legacy 14-session set
  is gated on `force=true` (cohort default for all 8 animals per PR
  #81's seed), so the divergence is invisible in the parity-critical
  regime. Verified 2026-04-24: 26/26 reachable parity sessions return
  bit-identical max|Δ|x=max|Δ|y=0 under `force=true`.
- *Forward commitment:* If a future session genuinely requires
  `force=false` (no seeded baseline, or a baseline-retune need), two
  options: (a) reintroduce the split-pool option with a
  `baseline.y_lk_thr` / `baseline.x_lk_thr` + matching percentiles
  schema, or (b) document the per-session divergence and run with the
  unified-pool estimates. Default: (a), land behind a new DECISIONS
  entry at that time.

**Parquet file-level metadata set locked to 9 keys (Task 2 fixup Item 4).**

- *Context:* Kickoff §2c sketched 10 metadata keys (X0, Y0, fps,
  n_frames, center_mode, baseline_stage, interpolation_version,
  bodypart, animal, date). On review the `bodypart`, `animal`, `date`
  trio were dropped — they are already encoded in the parquet path
  (`interpolated_traces/<bodypart>/<animal>/<YYYYMMDD>.parquet`) and
  duplicating them as metadata is redundant. The v6.8 side-convention
  stamp pair (`wavesurfer_sides_match_mouse_sides`,
  `side_convention_version`) was added so consumers can identify the
  side-frame convention under which the parquet was written.
- *Decision:* Parquet file-level metadata is exactly the 9-key set:
  `X0`, `Y0`, `fps`, `n_frames`, `center_mode`, `baseline_stage`,
  `interpolation_version`, `wavesurfer_sides_match_mouse_sides`,
  `side_convention_version`. The diagnostic scalars `X0_data`,
  `Y0_data` (data-driven baseline estimates computed unconditionally
  when `emit_qc_bundle=True`) live in the `.qc.npz` sidecar, not in
  parquet metadata.
- *Rationale:* Lean canonical schema; the sidecar is the extensible
  slot for future diagnostics. `test_parquet_schema` asserts strict
  equality on both the 7-column set and the 9-metadata-key set so
  any future accidental schema drift gets caught immediately.

**Parity verification.** 14-session parity set at `atol=1e-6` under
consolidated-env scipy 1.17.1 (Option A per 2026-04-22 DECISIONS):
`by_status = {pass: 26, skip_missing: 2}`. Every pass session returns
max|Δ|x = max|Δ|y = 0.000e+00 with zero NaN-boundary divergence. The
2 skip_missing are PS54/20250512 × {tongue, jaw} — known MICROSCOPE
gap carried over from Phase 7a.1 (legacy NPZ absent AND consolidated
DLC h5 absent; symmetric absence routes to skip_missing on both
sides, not fail). Reinforces pilot #1 (PS46/20250307, max|Δ|=0) and
pilot #2 (PS51/20250430, max|Δ|=0) findings.

**Enforced at.**
- `configs/defaults.yaml dlc_kinematics:` block.
- `configs/animals.yaml kinematics_baselines:` block (per animal).
- `src/stroke_orofacial/dlc_kinematics/interpolation.py` module.
- `tests/scripts/parity_phase7a_interpolation.py` harness.
- `tests/test_dlc_interpolation.py` (14 §8 unit tests +
  review-adjustment extras; strict-equality schema check).
- `scripts/phase_7a/emit_parity_sessions.py` (durable pre-emit
  helper for future parity re-runs).

**Forward implication for 7b / 7c / 7e / 7f.** Per-trial endpoint
modules consume
`interpolated_traces/{bodypart}/{animal}/{date}.parquet`. Any future
edit to the 7-stage pipeline that changes `x_final` / `y_final` by
more than `atol=1e-6` on any in-scope session requires a DECISIONS
entry documenting the drift and re-running the 14-session parity
(via `scripts/phase_7a/emit_parity_sessions.py` +
`tests/scripts/parity_phase7a_interpolation.py --sessions auto`).

**Applies to:** Phase 7a.2 and every downstream DLC-kinematics phase
that reads the interpolated-trace parquet.

---

## 2026-04-22 — Phase 7a.0 follow-ups: parity-scope principle + scipy version handling

Two decisions landing together as Phase 7a.0 wraps, both driven by
PR #79's baseline-seed probe and scipy-version pilot findings.

### Parity-scope principle (standing rule, all phases)

- *Context:* The Phase 7a.0 baseline-seed probe on PR #79
  enumerated every NPZ on disk under
  `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/` and flagged
  PS49 tongue and PS50 tongue as NEEDS_HUMAN_DECISION because X0/Y0
  differed across sessions. Priya clarified that the out-of-scope
  NPZs (3 sessions for PS49, 10 for PS50, all at Y0=-100) are
  leftovers from an earlier wider-scope pipeline run, superseded by
  her narrowing of `configs/animals.yaml sessions.{start, end}`
  (2026-04-17 transcription). Under the in-scope filter, both
  combos are STABLE at Y0=-110 and match PS46–PS48 tongue from day
  one. The general question this surfaced: when consolidated-pipeline
  outputs are compared against legacy artifacts on disk, should
  out-of-scope artifacts be parity targets?
- *Decision:* **Parity comparisons against legacy outputs are
  restricted to sessions within `configs/animals.yaml
  sessions.{start, end}` per animal.** Legacy outputs from dates
  outside that range are not parity targets; any parity harness
  must load the per-animal scope and skip out-of-scope candidates
  silently (not as a warning — the point is that out-of-scope
  artifacts are not expected to parity).
- *Rationale:*
  - Priya's analysis scope has narrowed per-animal over time (e.g.,
    PS49 `sessions.start` moved from 2025-03-07 to 2025-03-10;
    PS50 from 2025-03-07 to 2025-03-19). Legacy NPZs, parquets,
    etc. from pre-narrowing runs may carry preliminary parameters
    (different Y0 baselines, different exclusion rules) that are no
    longer authoritative. Parity-comparing against those artifacts
    would either force the consolidated pipeline to reproduce
    obsolete behavior or generate spurious parity failures. Neither
    is acceptable.
  - The rule retroactively no-ops for phases 3/4/5/6 — their
    parity sets were already chosen from in-scope sessions by
    convention. Making it explicit as a standing rule prevents
    accidental cross-scope comparisons in phases 7a/7b/7c and
    beyond.
  - A silent skip is safer than a warning: a warning invites
    "fix the warning" edits that turn into accidental re-baselining
    of the legacy artifacts. The correct behavior is "that NPZ is
    not a target; do not try." Making it silent encodes that.
- *Example — PR #79 scope-filtered re-analysis.* The baseline-seed
  probe's two NHD verdicts collapse to STABLE under scope filter.
  22 in-scope PS49 tongue sessions all at Y0=-110; 19 in-scope PS50
  tongue sessions all at Y0=-110. The 13 out-of-scope NPZs
  (Y0=-100) are pre-narrowing artifacts and are excluded from
  parity. No `animals.yaml` schema change needed. See
  `docs/phase-7/baseline-seed-table.md` "Scope-filtered
  re-analysis" section for the full per-session detail.
- *Applies to:* all phases. Retroactive in spirit (no-op for
  phases 3/4/5/6). Forward-applicable to 7a.1 (parity harness),
  7a.2 (`animals.yaml` seeding), 7b, 7c, and all subsequent work
  that compares new outputs against legacy artifacts on
  `O2_analysis/` or `session_processing3/`.
- *Enforced at:*
  - `docs/phase-7/baseline-seed-table.md` — "Scope-filtered
    re-analysis" section documents the first application.
  - Future parity harness scripts must load
    `configs/animals.yaml` `sessions.{start, end}` per animal and
    skip legacy NPZ candidates whose session date is out-of-range.
    The 7a.1 parity harness is the first code-level instance.
  - Deliberately NOT auto-enforced programmatically — this is a
    workflow/discipline rule. A future refactor could add a
    `PathResolver.is_in_scope(animal, date)` helper if the rule
    gets applied repeatedly, but that's 7a.1+ territory.

### scipy version handling for Phase 7a parity (and downstream numerical-reproducibility checks)

- *Context:* `docs/phase-7/interpolation-strategy.md` §6 specified
  `atol=1e-6` for the 14-session parity harness but flagged PCHIP
  as implementation-dependent across scipy versions (cubic-Hermite
  constructor bugfixes have landed historically). The legacy-era
  scipy is 1.15.1 (Priya's local `deeplabcut` conda env, confirmed
  2026-04-22); the consolidated `stroke_orofacial` env is at 1.17.1.
  Unanswered question: does minor-version drift between 1.15.1 and
  1.17.1 perturb PCHIP output enough to require pinning the parity
  env (or widening the tolerance)?
- *Pilot:* `docs/phase-7/scipy-pilot-results.md`
  (`tests/scripts/scipy_version_pilot.py`) measured PCHIP
  interpolation-output drift between scipy 1.15.1 and 1.17.1 on
  PS46/20250307 tongue (a STABLE, in-scope session, 931,834 frames,
  914,012 common non-NaN after PCHIP). Measurements:
  `max|Δ| = 0.0` on both x and y; `p99|Δ| = 0.0` on both;
  `n_exact_equal / n_common = 914,012 / 914,012` on both. NaN
  boundaries identical (17,822 leading/trailing on each side in
  both envs). **Bit-for-bit identical PCHIP output on this session
  between the two scipy versions.**
- *Decision:* **Option A — no pin, no widening.** Run Phase 7a.1
  parity under the consolidated `stroke_orofacial` env's scipy
  1.17.1 with `atol=1e-6` per `interpolation-strategy.md` §6. The
  scipy 1.15.1 → 1.17.1 upgrade path is confirmed non-perturbing
  for the PCHIP call used in the v5p3 interpolation pipeline. No
  pinned parity env, no DECISIONS-logged tolerance widening, no
  scope change to 7a.1 on the scipy-version axis.
- *Rationale:*
  - The pilot's result isn't just "below 1e-6" — it's exactly
    0 on every common non-NaN frame. Option A's precondition
    (max|Δ| < 1e-6) is met in the strongest possible form.
  - Pinning a separate parity env would add ongoing maintenance
    cost (a second conda env to keep running, a version assertion
    in the harness header) for no measurable parity benefit here.
  - Widening `atol` beyond the brief's `1e-6` default would relax
    parity further than the measurement supports. The
    conservative-margin argument under bullet 2 of the three-bullet
    tree (widen to 1e-4 if drift is in the 1e-6..1e-4 range) does
    not apply here.
- *Caveats (for 7a.1 + future phases):*
  - Single-session pilot. Per Priya's 2026-04-22 sign-off, a
    second-session stress pilot (suggested PS51/20250430, high-NaN
    per `interpolation-strategy.md` §6 stress set) is deferred to
    7a.1 — not required for this DECISIONS entry but should land
    alongside the 7a.1 parity harness as a second datapoint.
    - **Update 2026-04-22 (Phase 7a.1):** Second-session stress pilot
      on PS51/20250430 tongue run as part of 7a.1. Result: max|Δ|=0.0
      on both x and y across 906,310 common non-NaN frames; NaN masks
      identical (44,523 boundary NaNs per axis on both scipy versions).
      Session stress profile: 99.88% NaN-in x/y (vs. 89.47% on pilot
      #1 PS46/20250307). Caveat 1 is resolved; Option A now validated
      on both a low-NaN session (PS46/20250307) and a high-NaN stress
      session (PS51/20250430). No further scipy pilots required for 7a.
      Full results: `docs/phase-7/scipy-pilot-results.md` §"Second-
      session stress pilot — PS51/20250430 tongue".
  - Pilot tests PCHIP only (stage 4 of the 7-stage pipeline).
    Full 7-stage parity against the 14-session set is still the
    gating 7a.1 acceptance criterion per the parity-gate principle
    (2026-04-22 entry below) — pilot does not supersede it.
  - Future phases that touch scipy.interpolate, scipy.signal, or
    scipy.stats across version boundaries should re-run an
    analogous pilot before locking a tolerance. The template
    lives at `tests/scripts/scipy_version_pilot.py` and is
    bodypart-agnostic at the PCHIP level.
- *Applies to:* Phase 7a.1 (interpolation parity harness, `atol=1e-6`
  decision), and any future parity gate that touches scipy routines
  where cross-version drift might matter.
- *Enforced at:*
  - `docs/phase-7/scipy-pilot-results.md` — measurements + Option A
    recommendation.
  - `tests/scripts/scipy_version_pilot.py` — reusable pilot template.
  - Phase 7a.1 implementation PR (future) cites this entry and
    runs the 14-session parity harness under scipy 1.17.1 with
    `atol=1e-6`.

---

## 2026-04-22 — Phase 7-pre: dotted-hierarchical namespaced-tag schema for `AnimalInfo.exclusions.applies_to`

- *Context:* The Phase 7a interpolation design brief
  (`docs/phase-7/interpolation-strategy.md` §3.2) surfaced a namespace-
  collision problem in the existing `applies_to` flat-list schema. The
  legacy design used `applies_to: [all]` as a universal sentinel;
  Phase 7a wanted to scope exclusions by bodypart (e.g., "PS51 tongue
  but not jaw") and also by phase (e.g., "skip DLC paths but keep
  spout_behavior analysis"). Mixing bodypart strings (`tongue`) with
  phase tags (`dlc`, `spout_behavior`) in the same flat list creates
  an ambiguity: does `applies_to: [dlc, tongue]` mean "DLC AND tongue"
  (both-must-match, cross-axis) or "DLC OR tongue" (any-match,
  same-axis)? The brief flagged three candidate resolutions: (1)
  rename+split into two fields (`phases`, `bodyparts`); (2) nested
  struct (`applies_to: {phases: [...], bodyparts: [...]}`); (3)
  namespaced tags with hierarchical prefix-match (`dlc.kinematics.tongue`).
  Priya also flagged a new PS51 2025-05-17 exclusion (missing camera
  data → DLC+alignment break but spout_behavior still works) that
  cannot be expressed under `[all]` and is needed for 7a parity.
- *Decision:* **Namespaced tags with dotted-hierarchical prefix-match
  (Option 3).** The canonical `analysis_context` taxonomy:
  `spout_behavior`, `alignment`, `dlc.io`, `dlc.spatial`,
  `dlc.kinematics.{tongue,jaw,whisker,face_velocity,psd}`. An
  exclusion with `applies_to: [dlc]` matches any
  `analysis_context` that starts with `dlc` or `dlc.*`; an exclusion
  with `applies_to: [dlc.kinematics.tongue]` matches only that one
  context. Segment boundary is strict (`[dlc]` does NOT match
  `dlc_spatial` or `dlcx`). The legacy `applies_to: [all]` sentinel
  is rejected at YAML load time with a migration-guidance error;
  `applies_to` is now required and must be a non-empty list.
  `is_excluded(date, analysis_context=None)` never matches when
  context is `None` — callers must pass an explicit context. All
  four pre-existing `[all]` exclusions migrated to
  `[dlc, spout_behavior]`; PS51 2025-05-17 added as
  `[dlc, alignment]`.
- *Rationale:*
  - **Option 3 scales without migration.** Adding a future axis
    (e.g., `trial_group.rewarded`, `trial_group.unrewarded`) is a
    new leaf in the tag tree, not a schema change. Options 1 and 2
    would require adding a new top-level field for every new axis
    and re-auditing every existing exclusion.
  - **No empty-list ambiguity.** Under Option 1's split fields,
    `phases: []` + `bodyparts: [tongue]` has to mean "all phases"
    or "no phases" — either choice is surprising at the call site.
    Under Option 3, there's no empty-list state: the tag either
    matches a prefix or it doesn't.
  - **Migration cost is bounded and discharged.** The four legacy
    `[all]` exclusions each mapped to exactly one new tag set
    (`[dlc, spout_behavior]` — the Rose Bengal sham + experimenter-
    error cases that break mouse behavior but leave
    wavesurfer↔camera alignment templates intact). Any future
    cross-axis exclusion gets expressed as a list of tags, e.g.
    `[dlc.kinematics.tongue, dlc.kinematics.jaw]` — OR semantics
    within the list, which matches natural-language reading.
  - **Explicit-context requirement activates a previously dormant
    path.** All four pre-existing `build_manifest()` call sites
    were dropping the `analysis_type` parameter, so exclusions
    were effectively no-ops on emitted manifests. The rename to
    `analysis_context` + threading it through all four call sites
    activates the feature — documented as intentional-behavior-
    difference #1 in the MIGRATION_LOG entry.
- *Enforced at:*
  - `src/stroke_orofacial/animals.py` — `Exclusion.applies()`
    implements prefix-match; YAML loader rejects `[all]` and empty
    lists; `AnimalInfo.is_excluded()` parameter renamed to
    `analysis_context`.
  - `src/stroke_orofacial/session.py` — `build_manifest()` accepts
    and threads `analysis_context`.
  - Four wrappers that pass the context explicitly:
    `spout_behavior.session_processing.process_session_by_animal_date`
    (`spout_behavior`),
    `alignment.timebase.load_or_compute_alignment_by_animal_date`
    (`alignment`),
    `dlc_io.parquet.build_centered_parquet_by_animal_date` (`dlc.io`),
    `dlc_spatial.reward_aligned.build_reward_aligned_analysis_by_animal_date`
    (`dlc.spatial`).
  - `configs/animals.yaml` — 4 legacy exclusions migrated; 1 new
    exclusion (PS51 2025-05-17).
  - `docs/MIGRATION_LOG.md` — "Phase 7-pre — `AnimalInfo.exclusions.applies_to`
    schema extension" (2026-04-22).
  - `docs/DESIGN.md` §14.2 — dotted-tag exclusions convention
    (prefix-match semantics, taxonomy).
  - Tag `v7-pre-exclusions-schema` on PR #75 merge commit.

---

## 2026-04-22 — Phase 7a interpolation design brief locked; §10 is the canonical resolution list

- *Context:* Phase 7 DLC kinematics was unblocked by Phase 6.8 (L/R
  convention) + Phase 6.8a (trial_group translation). The first
  in-scope piece is the interpolation algorithm that produces
  continuous tongue/jaw traces from DLC outputs (occlusion
  handling). Priya's existing legacy notebooks
  (`20260203_..._tongue.ipynb`, `20260416_..._jaw.ipynb`) implement
  a 7-stage v5p3 algorithm with 8 open design choices (knobs 1–8
  in the Phase 7 kickoff prompt). CC drafted a design brief
  (`docs/phase-7/interpolation-strategy.md`) and Cowork reviewed
  it across two passes (11 edits round 1, 5 more edits round 2),
  closing all 8 open questions.
- *Decision:* **Lock the design brief as the authoritative spec
  for 7a implementation.** The §10 "Resolutions" section at the
  end of the brief is the canonical source for all 8 knob
  decisions — not the earlier "Open Questions" section (kept for
  narrative flow but superseded). Key decisions:
  - **Knob 1 (emit shape):** split emit — canonical parquet
    (pure-bodypart, per-trial OR whole-session) + optional
    `.qc.npz` sidecar with stage-by-stage diagnostics.
  - **Knob 3 (percentile semantics):** `Y0` is the lowest
    n'th-percentile of the trial-aligned pool; `X0` is the median
    of `X` values within the `Y`-percentile subset (not a
    separate percentile on X).
  - **Knob 5 (output format):** Option A — pure-bodypart parquet
    (no trial-grouped variants at this layer; trial-grouping
    happens downstream in Phase 7b/8b/9b consumers).
  - **§3.1 (baselines):** per-animal per-bodypart baselines in
    `configs/animals.yaml`. Faithful port of Priya's manual
    per-run X0/Y0 editing against the legacy notebook — legacy
    MICROSCOPE outputs are correct under this manual protocol.
    Seed from `X0`/`Y0` keys in the legacy NPZs.
  - **§3.2 (exclusion scoping):** escalated to Phase 7-pre
    mini-PR (see entry above) — the flat-list `applies_to`
    couldn't express bodypart-scoped exclusions without a schema
    change.
- *Rationale:*
  - Faithful-port framing (not "latent-bug fix"): legacy
    production outputs on MICROSCOPE are correct under the
    manual-editing protocol; per-animal per-bodypart baselines in
    animals.yaml reproduce that protocol without Priya having to
    re-edit cells per run.
  - Split-emit preserves parquet as the canonical downstream
    contract (matches Phase 4 DLC I/O) while keeping QC NPZ
    available for debugging without bloating the primary output.
  - Option A on §5 keeps the per-bodypart file structure orthogonal
    to trial grouping — downstream Phase 7b / 8b / 9b code can
    compose trial-grouping independently. Mixing them at the 7a
    layer would push trial-group definitions upstream of the
    kinematics extraction and make per-session reruns harder.
- *Enforced at:*
  - `docs/phase-7/interpolation-strategy.md` §10 — canonical
    resolution list (8 knobs closed).
  - `docs/phase-7/interpolation-strategy.md` §2, §3.1, §3.2, §5,
    §6 — updated sections per the two review passes.
  - `docs/MIGRATION_LOG.md` — Phase 7a design brief entry
    (2026-04-22).
  - Tag `v7a-design-brief` on PR #74 merge commit.
  - Phase 7a implementation PR (future) must cite §10 and honor
    every resolution there.

---

## 2026-04-22 — Parity-gate principle: no kinematics algorithm lands without MICROSCOPE parity verification

- *Context:* After the 7a design brief merged (PR #74) and the
  Phase 7-pre schema extension merged (PR #75), there was an
  opportunity to take a "thin slice" of the 7a algorithm — the
  percentile-threshold-and-drop preamble (stages 1–3 of the
  7-stage v5p3 pipeline) — on a short feature branch without
  MICROSCOPE access, just to land runnable scaffolding. Cowork
  flagged and Priya agreed that thin-slicing without a parity
  check against Priya's legacy NPZ X0/Y0 keys creates a
  maintenance hazard: any drift in the stage-1–3 intermediate
  values against the legacy-notebook computation would either be
  silently absorbed into later stages or surface as a
  whack-a-mole divergence when stages 4–7 are added. The
  Phase-13 precedent (strict port + drift quantification against
  `session_processing3/` baselines) has been the project's
  consistent pattern for every phase with a legacy reference.
- *Decision:* **Algorithm ports that have a legacy reference do
  not land on main until per-stage parity against MICROSCOPE
  baselines has been measured and documented in MIGRATION_LOG.**
  For 7a specifically: the 9 primary + 3 stress-test + 2
  late-post-stroke parity sessions listed in
  `docs/phase-7/interpolation-strategy.md` §6 must be evaluated
  before the implementation PR opens. Intermediate stages are
  validated in-process (e.g., parquet column-level or NPZ
  key-level compare against the legacy output); a drift table
  lives in the migration entry. Docs-only PRs (design briefs,
  kickoff prompts, taxonomy extensions) do NOT fall under this
  rule — they have no algorithmic content to drift against.
- *Rationale:*
  - Drift found at stage 7 is cheaper to triage if stages 1–6
    are each known-clean against the legacy. Drift surfacing
    only at the end of a 7-stage pipeline is extremely hard to
    localize without per-stage parity anchors.
  - Thin-slicing breaks this auditability: if stages 1–3 land
    first without parity, later stages that depend on their
    outputs can't be verified independently of whatever drift
    was absorbed into the early stages. The per-stage parity
    model only works if it's adopted from the first commit.
  - The existing Phase-13-pattern precedent (vendored helpers +
    intentional-divergence documentation + regression guards
    per divergence) is the standing convention for every port
    with a legacy reference; this principle makes it explicit
    for Phase 7a's specific shape.
  - No development-velocity cost for this wrap: MICROSCOPE is
    already required for baseline-seeding per §3.1, so the
    parity data is obtainable at the same moment the animals.yaml
    seeding happens. The rule does not require a second trip.
- *Enforced at:*
  - `docs/phase-7/interpolation-strategy.md` §6 — parity-session
    list (9 primary + 3 stress-test + 2 post-stroke) is the
    parity scope for 7a.
  - `docs/prompts/phase-7-dlc-kinematics-kickoff.md` — Phase 7
    implementation PR must include a per-stage drift table in
    its MIGRATION_LOG entry.
  - Generalizes to any future kinematics / DLC / spout port with
    a legacy notebook or `session_processing3` reference.
    Deliberately NOT auto-enforced in code; this is a
    workflow/discipline rule that lives in the PR review + the
    migration-log template.

---

## 2026-04-22 — Cowork returns to Priya's Windows machine; two-tool workflow collapses to same-host

- *Context:* On 2026-04-19 Cowork-on-Windows was declared permanently
  unavailable after an extensive troubleshooting session (Hyper-V enabled,
  Windows 11 Enterprise, Max subscription, Claude Desktop current, full
  reinstall with cache wipe) failed to produce a Cowork tab in the Windows
  desktop app — diagnosed as an account-level feature flag or
  staged-rollout gate Anthropic controlled server-side. The permanent
  workflow was locked in as Mac Cowork + Windows Claude Code in VSCode,
  with file handoffs gated on a Mac-commit-and-push + Windows-pull
  roundtrip. On 2026-04-22 the Cowork tab appeared on Priya's Windows
  machine without any local change on her end (no support ticket filed,
  no reinstall, no settings change) — the server-side gate cleared.
- *Decision:* **Same-machine on Windows is the new default workflow.**
  Cowork and Claude Code now run on the same host; Cowork's Linux sandbox
  mounts the Windows repo tree directly. The advisor/executor division of
  labor stays the same (Cowork plans / drafts / refreshes docs; CC
  executes tests, runs conda work, does MICROSCOPE I/O, runs all git
  state-changing commands), but the file-handoff layer collapses: files
  Cowork writes to the repo are immediately visible to CC-in-VSCode on
  disk with no commit-push-pull roundtrip. Mac Cowork is retained as a
  secondary option for any ad-hoc Mac-specific task, but is no longer the
  required primary channel.
- *Rationale:*
  - The 2026-04-19 disposition explicitly said "would require a support
    ticket to resolve, deferred indefinitely" — the fix came with no
    ticket, so there's no post-hoc "what unblocked it?" signal to chase.
    The situation to note for future incident recovery is purely that
    server-side flags can flip without notice; re-check the basics
    (Hyper-V still running, Claude Desktop current, cache clean) first
    if the tab ever disappears again, but don't assume a local
    misconfiguration.
  - Eliminating the Mac-commit-and-push roundtrip removes a non-trivial
    source of doc-state drift (e.g., the 2026-04-21 "cohort-first-emit-
    results docs lagging behind PR #65" scenario that forced a retroactive
    no-tag PR #66 to reconcile).
  - Same-machine does NOT eliminate the advisor/executor division: Cowork
    still lacks the conda env, cannot touch MICROSCOPE UNC paths
    (project-instructions warning), and cannot auth to GitHub. CC retains
    all three. The boundary shifts from "different physical machine" to
    "different sandbox on the same machine" — see the next entry for the
    hard rule that makes this safe.
- *Enforced at:* `docs/COWORK_SESSION_STATE.md` — "Cowork-on-Windows
  status" section flipped NOT AVAILABLE → AVAILABLE with the 2026-04-19
  troubleshooting preserved as recovery history; "Two-tool workflow"
  section rewritten as "Two-tool workflow (same-machine on Windows since
  2026-04-22)" with the new responsibilities and the handoff pattern
  documented. The 2026-04-19 entry below that declared Cowork-on-Windows
  permanent-deferred is now superseded by this entry.

---

## 2026-04-22 — Sandbox-git boundary rule (Cowork does not run state-changing git ops on cross-OS-mounted repos)

- *Context:* Same-machine Cowork on Windows mounts the Windows repo tree
  into a Linux sandbox for read/write. On 2026-04-22 a `git fetch --all
  --tags` run from inside the sandbox failed partway through (no GitHub
  credentials present in the sandbox, as expected) and left `.git/HEAD`
  on disk truncated to `ref: refs/heads/docs/` (missing the branch-name
  suffix). Subsequent `git branch --show-current` from CC's Windows
  terminal failed with `fatal: Failed to resolve HEAD as a valid ref`.
  Root-cause hypothesis: cross-OS filesystem sync between the Linux
  sandbox and the Windows disk did not handle the partial write cleanly
  when the fetch process was terminated mid-operation. The failure is
  plausible enough (network-ish error without a `fatal: ...` — could
  easily be treated as benign and followed by another command) that it
  won't always be obvious the tree is broken until the next read.
- *Decision:* **Cowork does not run state-changing git operations from
  the Linux sandbox on the cross-OS-mounted Windows repo.** The hard
  rule list: no `git fetch`, `git pull`, `git checkout <branch>`,
  `git merge`, `git rebase`, `git reset`, `git gc`, or any other command
  that writes to `.git/`. All git state-changing work routes through
  CC's Windows terminal (GitHub Desktop credential store handles auth
  via the Windows file system directly, without the cross-OS sync
  layer). Read-only git inspection from the sandbox (`git status`,
  `git log`, `git diff`, `git branch --show-current` on an intact ref)
  remains fine.
- *Rationale:*
  - Sandbox has no GitHub credentials by design, so any network-touching
    git op will fail — but the failure mode is "partial write to
    `.git/`", not "no change", because git writes speculatively before
    verifying auth. The corruption class of bug is inherent to the
    partial-write-plus-cross-OS-sync combination, not a one-off glitch.
  - Recovery is cheap and deterministic (one-line
    `git symbolic-ref HEAD refs/heads/<branch>` from CC's Windows
    terminal restores HEAD with no data loss) — but the only reliable
    way to catch the corruption is to not cause it in the first place.
    The rule eliminates the class without adding real friction: CC is
    already the canonical git-operator per the advisor/executor split.
  - The "read-only is safe" carve-out preserves Cowork's ability to
    answer "what branch am I on / what's the diff / what's in the log"
    questions without a CC handoff, which would otherwise be a
    significant regression from pre-2026-04-22.
- *Enforced at:* `docs/COWORK_SESSION_STATE.md` — "Two-tool workflow"
  section states the rule explicitly with the 2026-04-22 incident as
  the worked example; "Known gotchas" section has a dedicated
  "Sandbox git ops can corrupt `.git/HEAD` on cross-OS-mounted repos"
  bullet with the recovery one-liner. No `.git/`-level write-block is
  enforced programmatically — this is a workflow rule, not a
  filesystem-enforced invariant. Re-evaluate if a future Cowork release
  supplies the sandbox with host credentials or eliminates the cross-OS
  sync layer.

---

## 2026-04-22 — Audit Item 10 Q7 closure stamp (AnimalInfo cohort metadata shipped 2026-04-20)

- *Context:* The 2026-04-19 audit-closure DECISIONS entry (Q1–Q10) locked
  Q7 as "Add both `sex` and `date_of_birth` fields to `AnimalInfo` and
  `configs/animals.yaml`" with a forward obligation but no closure stamp.
  The work shipped 2026-04-20 — visible in `configs/animals.yaml` (header
  dated 2026-04-20 citing this decision; all 8 PS46–PS55 animals
  populated with `sex`, `date_of_birth`, `genotype`, `stroke_laser_power_mW`)
  and in `src/stroke_orofacial/animals.py` (`AnimalInfo` dataclass fields
  + YAML loader parsing + validation + `age_at_stroke` helper) — but the
  `docs/MIGRATION_LOG.md` entry for it was missed, and the
  `docs/COWORK_SESSION_STATE.md` Pending queue and Next-phase candidates
  list still carried task #18 as unstarted. This closure stamp + the
  retroactive 2026-04-20 MIGRATION_LOG entry land together in the
  2026-04-22 docs-only bookkeeping PR.
- *Decision:* **Q7 resolved as scoped, with implementation scope expanded
  to include genotype + stroke_laser_power_mW alongside the originally-
  scoped sex + date_of_birth.** The `AnimalInfo` dataclass now carries
  four optional cohort-metadata fields:
  `sex: Literal["M", "F"] | None`,
  `date_of_birth: datetime.date | None`,
  `genotype: str | None`,
  `stroke_laser_power_mW: float | None`. All four are populated for the
  PS46–PS55 cohort. The `age_at_stroke` helper derives age-in-days from
  `date_of_birth` + `stroke_date` when both are present. Downstream
  covariate use (Phase 9a/9.1/9b stats) picks up these fields directly
  from the config; no retrofit of downstream callers is required beyond
  reading them through the loader.
- *Rationale:*
  - Adding the two unscoped fields (genotype, stroke_laser_power_mW) at
    the same moment costs almost nothing and saves a second schema
    migration later. Both are cohort-level properties that any covariate
    analysis will eventually want, and both were already available in
    Priya's direct cohort records.
  - The PS46–PS55 cohort ages at stroke range 95–101 days (~14 weeks,
    standard adult-mouse age) — documented in the
    `configs/animals.yaml` header so future readers don't have to
    re-derive. Two animals (PS49, PS50) are annotated as "C57BL/6J
    (negative littermate)" per the 2026-04-20 population pass — refers
    to breeding-scheme negative result, not a base-strain difference.
- *Enforced at:*
  - `configs/animals.yaml` — all 8 PS46–PS55 animals carry all four
    fields + `wavesurfer_sides_match_mouse_sides`. Header comment dated
    2026-04-20 cites this audit resolution.
  - `src/stroke_orofacial/animals.py` — `AnimalInfo` dataclass field
    defs (lines 130–133), YAML loader with per-field parsing + validation
    (lines 243–276), `age_at_date(session_date)` / `age_at_stroke()`
    helpers (lines 170–186).
  - `docs/MIGRATION_LOG.md` — retroactive 2026-04-20 entry added in the
    same 2026-04-22 docs PR that lands this closure stamp.
  - `docs/COWORK_SESSION_STATE.md` — task #18 removed from Pending queue
    and Next-phase candidates list; surfaced as "shipped 2026-04-20" in
    the Completed-since-last-refresh section + 2026-04-22 maintenance
    log entry.

---

## 2026-04-21 — PS48 2025-03-14 multi-session handling (merge two acquisition halves into one analysis session)

- *Context:* Priya flagged during the Phase 6.8a diagnostic post-mortem
  that PS48 2025-03-14 was split across two acquisitions within one
  behavior day. The session has two sets of Flea3 videos, two sets of
  per-frame-timestamp CSVs, and two sets of Wavesurfer `.h5` files —
  one set per acquisition half. The legacy DLC analysis code merges the
  two halves into one logical session for downstream analysis. The new
  consolidated pipeline does not yet handle this case. PS48 2025-03-14
  is known; additional multi-half sessions may exist in the cohort and
  should be audited opportunistically.

- *Decision:* **Multi-half support ports into the new pipeline at
  two load-boundaries.**
  1. **Phase 2 (spout behavior) — wavesurfer I/O in
     `src/stroke_orofacial/wavesurfer_io.py`.** `read_wavesurfer_h5`
     (or a new thin wrapper) must accept *either* a single path *or*
     an ordered list of paths, concatenate per-sweep samples in
     acquisition-time order, and expose a single merged timebase +
     merged channel arrays to downstream Phase 2 consumers.
     Per-sweep metadata (`Fs`, sweep boundaries, acquisition UTC
     timestamps) preserved so `SessionManifest` can carry provenance.
     Config + discovery layer: `SessionManifest` construction must
     enumerate all `.h5` files for a given animal+date and sort them
     by the acquisition UTC timestamp encoded in the filename.
  2. **Phase 4+ (DLC) — parquet I/O in `src/stroke_orofacial/dlc_io/
     parquet.py` (centered parquet builder) and any upstream DLC H5
     reader.** Same shape: accept ordered list of per-half DLC H5s +
     ordered list of per-half timestamp CSVs, concatenate frame rows
     in acquisition-time order, preserve per-half provenance in
     parquet-column metadata. Downstream reward-aligned / heatmap
     callers see one logical session.

- *Rationale:*
  - Legacy code already does this merge — without it we cannot
    reproduce known-good outputs on PS48 2025-03-14.
  - Merging at load time (Phase 2 wavesurfer I/O + Phase 4+ DLC I/O)
    is the shallowest intervention — everything downstream stays
    single-session-shaped.
  - Ordered lists (not globs) make the merge deterministic and
    testable with synthetic two-half fixtures.
  - Per-half provenance preserved in metadata lets cohort-level
    auditors confirm which halves contributed to a given output.
  - Out-of-scope alternatives considered: (a) process halves
    independently + merge at endpoint level — rejected, breaks the
    whole-session-endpoint contract in Phase 8a; (b) manual
    concatenation script run once before pipeline — rejected, not
    reproducible from source data.

- *Enforced at:*
  - **To be coded.** Tracked as a TaskList entry opened 2026-04-21.
  - `CLAUDE.md` rule 1 still applies — the per-half raw files remain
    read-only source data; merging happens in-memory at load time,
    no merged artefacts written back to source paths.
  - `configs/session_overrides.yaml` may gain a `multi_half_sessions`
    registry (PS48 20250314 explicit listing) so discovery doesn't
    depend on accidental filename-sort behavior.

- *Immediate action:* None — noted now so the Phase 2 wavesurfer-I/O
  refactor (if any) and the Phase 4+ DLC-I/O port (Phase 7 or a
  dedicated mini-phase) both pick this up. Cohort-scan pass over the
  other 7 animals deferred until the first multi-half fixture lands.

---

## 2026-04-21 — Phase 6.8a.1 distinct prerequisite errors in `build_reward_aligned_analysis`

- *Context:* Phase 6.8a's first cohort re-emit surfaced 14,202
  reward-aligned-build failures out of 14,256 attempts (264
  DLC-carrying manifests × 54 combos). All failures collapsed into a
  single indistinguishable "FileNotFoundError" because
  `build_reward_aligned_analysis` had three silent `return None`
  paths (centered parquet missing, licks NPZ missing, alignment
  template missing) and one raise-path (empty DLC H5 list). Callers
  could not distinguish "Phase 4 hasn't centered this session yet"
  from "Phase 2 didn't emit licks" from "alignment template never
  built" from "this trial_group has no rewards."

- *Decision:* **Convert three of the four prerequisite-miss paths
  from silent `return None` to explicit
  `raise FileNotFoundError(<artefact-specific message>)`.** Kept the
  zero-rewards-for-trial_group path as `return None` (valid-but-empty
  data condition, not a missing-prerequisite condition). Each raise
  names the missing artefact, the upstream phase, and the script that
  would produce it. Docstring `Raises` + `Returns` blocks updated to
  reflect the new contract.

- *Rationale:*
  - Silent `return None` on prerequisite miss made diagnostic impossible
    at cohort scale (14,202 failures all indistinguishable).
  - The only callers (`notebook 12` runner and `phase_6_8a_first_run_
    health_report.py`) already catch `FileNotFoundError` — richer
    messages flow through without code changes.
  - Zero-rewards-for-trial_group is a legitimately-empty data
    condition (PS48 2025-03-14 has sessions where only one spout was
    rewarded), distinct from a missing-prerequisite condition; it
    stays `return None`.
  - Diagnostic-value-vs-emit-latency trade-off: PR'd and merged ahead
    of Windows's in-progress cohort emit (Path B) so the cohort runs
    under the distinct-error contract. Running under the old contract
    would have burned the diagnostic opportunity the fix was designed
    for.

- *Enforced at:*
  - `src/stroke_orofacial/dlc_spatial/reward_aligned.py::
    build_reward_aligned_analysis` (3 raise paths with
    artefact-specific messages; 1 `return None` retained for
    zero-rewards).
  - `tests/test_reward_aligned.py::
    TestBuildRewardAlignedAnalysisRaisesOnMissingPrerequisites`
    (scoped to centered-parquet path).
  - `docs/MIGRATION_LOG.md` Phase 6.8a.1 entry.

---

## 2026-04-21 — Tongue cell 53 (tongue-jaw mismatch classifier) scope → 7c jaw-kinematics

- *Context:* The canonical tongue notebook
  (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`) cell 53
  implements a "candidate trial classifier: few/no tongue licks + jaw
  movement" that emits per-mouse `df_trials_candidates.csv`. It is not
  in the Q6 locked endpoint list but is a first-class analytical output
  in the notebook. Three scope options surfaced during 7.0b
  classification: (a) add it to 7b as a tongue-jaw joint endpoint, (b)
  defer to 7c and ship as a jaw-initiated mismatch endpoint, or (c) log
  as an out-of-Phase-7 backlog sideband.

- *Decision:* **Option (b) — port in 7c (jaw-kinematics module).** The
  cross-bodypart classifier lives in a new function
  `classify_tongue_jaw_mismatch_trials()` (likely in
  `stroke_orofacial.dlc.jaw_kinematics` or a thin sibling
  `tongue_jaw_joint.py`), consuming tongue Cell 23 NPZs + jaw Cell 22
  NPZs and emitting per-mouse `df_trials_candidates.csv` under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/7c/`. Dep order stays
  7b → 7c (no reshuffle); 7b ships tongue-only endpoints including the
  tongue NPZ, 7c picks up the cross-bodypart classifier after 7b's
  tongue Cell 23 output is available.

- *Rationale:* (a) **Cleanest dependency direction.** Tongue endpoints
  elsewhere in 7b don't consume jaw data, so keeping 7b tongue-only
  preserves a clean module-per-bodypart shape. The one cross-bodypart
  analysis lives in the downstream (jaw) module, which naturally
  already depends on tongue-side outputs through the existing
  SessionManifest wiring. (b) **Matches where the biological logic
  lives.** The classifier's core question ("did the jaw move without a
  tongue extension?") is jaw-initiated — the jaw Y-threshold is the
  primary discriminator, tongue lick-count is the gating condition. (c)
  **Avoids reshuffling 7b ↔ 7c.** Option (a) would have forced 7b to
  wait on jaw NPZs from 7c-impl, collapsing the natural 7b-first
  ordering. Option (c) would strand the classifier in backlog
  indefinitely despite its first-class status in the canonical
  notebook.

- *Enforced at:* `docs/phase-7/classification-tongue.md` §Cell 53
  port-surface block ("Sub-phase owner — 7c"). `docs/phase-7/classification-jaw.md`
  §top-level summary (tongue-jaw mismatch listed as 7c input).
  `docs/phase-7/classification-nose.md` cross-notebook Phase-7-summary
  table (7c row). Implementation lands in the Phase 7c port PR
  (forthcoming). 605 source lines in cell 53; plotting/scrubbing UI is
  most of it — the classifier logic itself is expected to be < 80
  lines.

---

## 2026-04-21 — Phase 6.8a: Phase 5/6 trial_group mouse-frame translation + heatmap NPZ writer

- *Context:* Phase 6.8 (task #17) landed the wavesurfer↔mouse-frame
  boundary-layer translation for Phase 2 NPZs and Phase 8a JSONs but
  explicitly deferred Phase 5/6 (`dlc_spatial` heatmaps + reward-aligned
  heatmaps) to a follow-up — documented in
  `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7. The reward-aligned
  analysis in `dlc_spatial/reward_aligned.py` accepted a `trial_group`
  argument (`"all"` / `"L"` / `"R"`) whose frame of reference was
  ambiguous post-task-#17: the Phase 2 NPZ it reads now carries
  mouse-frame `Reward_L`/`Reward_R` keys, so `trial_group="L"` silently
  shifted from experimenter-L to mouse-L — but nothing in the pipeline
  asserted that the upstream NPZ was actually in mouse frame, nor
  stamped the resulting Phase 6 output. Phase 7 (DLC kinematics) cannot
  start on top of mixed-convention heatmap outputs.
  An additional wrinkle discovered during design: Phase 6 never
  emitted NPZs — cell 16 of the canonical reward-aligned notebook
  only produced PNGs. Without an array-level output there was no way
  to programmatically verify drift after the convention flip.

- *Decision:* **Extend the boundary-layer pattern to Phase 5/6 in this
  single PR, AND add NPZ writing to Phase 6 so drift is measurable.**
  Three coupled changes:
  (1) `load_reward_events` requires the Phase 2 stamp to be present
  (raises ValueError on pre-re-emit NPZs), verifies the version matches
  :data:`SIDE_CONVENTION_VERSION`, and if the caller passes
  `wavesurfer_sides_match_mouse_sides` cross-checks it against the
  stamped value. `trial_group` is re-documented as mouse-frame.
  (2) `build_reward_aligned_analysis` gains a
  `wavesurfer_sides_match_mouse_sides` kwarg that forwards into
  `load_reward_events` and is echoed on the return dict. The
  `_by_animal_date` wrapper auto-populates it from `AnimalInfo` when
  None. (3) New writer
  `dlc_spatial.reward_aligned.save_reward_aligned_npz(result, path)`
  serializes the full histogram payload — `H_counts`, `H_proportion`,
  edges, axis limits, `trial_group`, `window_ms`, `n_rewards`,
  `n_selected_frames`, `bodypart`, `center_mode` — stamped via
  `stamp_side_convention`. Notebook 12 calls the helper alongside the
  existing PNG save. `save_heatmap_npz` also gains optional stamping
  kwargs for Phase 5 (whole-session) callers that want to stamp going
  forward.

- *Rationale:* (a) **Fail-loud on pre-re-emit upstream.** The
  task-#17 re-emit of Phase 2 NPZs produced mouse-frame outputs, but
  a stale local checkout would still hold wavesurfer-frame NPZs.
  Silently reading those as mouse-frame would swap L and R on every
  PS46–PS55 session (flag default is False = mirrored rig). Raising
  at `load_reward_events` means the first Phase 6 run after a stale
  checkout errors out immediately rather than producing plausible-
  looking but mis-labeled heatmaps. (b) **Stamp-matches-yaml
  cross-check catches a specific foot-gun:** editing
  `configs/animals.yaml` after an NPZ was written. Without the check,
  the next Phase 6 run would read the stale NPZ under the new flag
  interpretation. (c) **NPZ alongside PNG unlocks drift
  diagnostics and Phase 9 stats.** Phase 6 had no legacy array-level
  reference (cell 16 was never run to save outputs on MICROSCOPE
  pre-consolidation), so "parity against legacy" is not available
  as a parity strategy. Writing NPZs within this PR makes future
  drift measurable programmatically — the post-merge health-report
  script (`scripts/phase_6_8a_first_run_health_report.py`) runs
  n_rewards[all]=L+R, stamp, and H_counts sanity checks across the
  whole output tree. (d) **`save_reward_aligned_npz` not
  `save_heatmap_npz`.** Reward-aligned outputs carry more metadata
  (trial_group, window_ms, n_rewards) than whole-session heatmaps;
  a bespoke writer is cleaner than overloading `save_heatmap_npz`
  with Phase-6-only kwargs. `save_heatmap_npz` still gains optional
  stamping so Phase 5 can adopt the same convention non-invasively.

- *Enforced at:* `src/stroke_orofacial/dlc_spatial/reward_aligned.py`
  (`load_reward_events` stamp verification, `build_reward_aligned_analysis`
  flag forwarding + return-dict field, `_by_animal_date` auto-populate,
  new `save_reward_aligned_npz`). `src/stroke_orofacial/dlc_spatial/heatmaps.py`
  (`save_heatmap_npz` optional stamp kwargs). `notebooks/12_dlc_spatial_reward_aligned.ipynb`
  (cell 2 import swap, cell 4 calls `save_reward_aligned_npz` alongside
  PNG save; passes `wavesurfer_sides_match_mouse_sides` from
  `AnimalInfo`). `tests/test_reward_aligned.py::TestLoadRewardEventsStamp`
  (6 tests: unstamped / missing-match / version-mismatch / flag-mismatch
  / flag-matches / flag-None rejection & happy paths) + stamped fixtures
  in `TestLoadRewardEvents`. `tests/test_dlc_spatial_side_convention.py`
  (schema roundtrip, stamp-matches-flag parametrized, flag-swap
  byte-divergence, None-histogram rejection, non-bool-flag rejection,
  parent-dir creation, str-path acceptance; plus `build_reward_aligned_analysis`
  flag-echo parametrized and `_by_animal_date` auto-populate + explicit
  override). `scripts/phase_6_8a_first_run_health_report.py` (post-
  re-emit health check). `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
  §7 RESOLVED + new §8 Phase 6 re-emit procedure.

---

## 2026-04-21 — Wavesurfer L/R ↔ mouse-frame boundary-layer translation (task #17, Phase 6.8)

- *Context:* Wavesurfer channel labels `L`/`R` are experimenter-facing
  (the physical spout positions from the experimenter's viewpoint) and
  are flipped relative to the mouse's own perspective on the current
  PS46–PS55 cohort. Legacy handling was inconsistent: the tongue/jaw
  kinematics notebooks (`20260203_..._tongue.ipynb` cell 25,
  `20260416_..._jaw.ipynb` cells 22 & 24) applied a data-level flip at
  load time so all downstream code saw mouse-frame labels, while
  `behavior_report_PS.py` kept data in wavesurfer frame and flipped
  labels only at plot time via `fn_flip_lr`. Our consolidated ports of
  Phases 2 (spout_behavior) and 5/6 (dlc_spatial) inherited the
  behavior_report convention — wavesurfer-frame throughout with no
  translation at emit, and no schema annotation on emitted JSON/NPZ.
  Continuing into Phase 7 (DLC kinematics) without resolving this would
  have forced a retroactive rename sweep across every per-side output
  file and figure label once the convention was settled; choosing
  between the two legacy patterns was the blocker.

- *Decision:* **Boundary-layer translation, NOT flip-at-load.** Internal
  pipeline arithmetic stays on the wavesurfer frame; every output
  boundary (NPZ, JSON, parquet `side` columns, figure labels, output
  filenames) translates to the mouse frame and stamps two scalars —
  `wavesurfer_sides_match_mouse_sides: bool` (per-animal, from
  `animals.yaml`) and `side_convention_version: int` (currently 1). A
  new per-animal `wavesurfer_sides_match_mouse_sides` field is
  added to `AnimalInfo` with default `False` (fail-conservative for
  the current cohort; future animals with corrected wiring set `True`).
  Translation + stamping is provided by
  `src/stroke_orofacial/lr_convention.py::to_mouse_frame(side,
  wavesurfer_matches)` and `stamp_side_convention(payload, flag,
  version)`, applied at the Phase 2 NPZ emit layer and the Phase 8a
  per-session JSON writer. Phase 5/6 heatmap NPZ reward-aligned
  `trial_group` slug translation is deferred to a follow-up PR tracked
  in `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7.

- *Rationale:* (a) **Preserves Phase 3/4/5/6 numerical parity** against
  the `session_processing3` baselines byte-identically — only output
  key names change, never array values. A flip-at-load would have
  rewritten every internal buffer and broken parity tests requiring
  per-phase re-verification. (b) **Single source of truth per
  artifact.** Every file emitted post-task-#17 can be interpreted
  without external context: `wavesurfer_sides_match_mouse_sides=False`
  + `side_convention_version=1` stamps tell a reader exactly what a
  `Lick_L` key means. Absent stamps means pre-task-#17 (wavesurfer
  frame). (c) **Cheap incrementality.** Phase 7 ports can now write
  outputs in mouse frame from day one without inheriting either
  legacy pattern; the convention is not renegotiated per sub-phase.
  (d) **Fail-conservative default.** Setting the yaml default `False`
  (not `True`) means a new animal added without the flag defaults to
  the current cohort's behavior (mirrored); an animal with corrected
  wiring must be explicitly opted-in via yaml, which is the safer
  failure mode than a silent over-flip on a new rig.

- *Enforced at:* `src/stroke_orofacial/lr_convention.py` (helpers +
  `SIDE_CONVENTION_VERSION = 1`). `src/stroke_orofacial/paths.py` and
  `configs/animals.yaml` (per-animal flag on PS46–PS55; all `false`).
  `src/stroke_orofacial/manifest.py` (`SessionManifest` carries the
  flag through to orchestrators). `src/stroke_orofacial/spout_behavior/session_processing.py`
  (`_translate_side_keys`, `_save_npz_with_side_convention` at every
  Phase 2 NPZ emit). `src/stroke_orofacial/spout_behavior/endpoints_writer.py`
  (`write_session_endpoints_json` translates per-side criteria/endpoint
  dict keys and stamps the metadata block). `tests/test_session_processing.py::TestSideConventionAtEmit`
  (7 tests) + `tests/test_endpoints_writer.py::TestSideConventionAtEmit`
  (5 tests) + `tests/test_lr_convention.py` (31 tests). `docs/DESIGN.md`
  §14 (new "CONVENTIONS" section — the canonical rule). `docs/MIGRATION_LOG.md`
  "Task #17" entry (implementation + Phase 2 re-emit of 1799 NPZs
  across 257 sessions for PS46–PS55). `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
  (deferred Phase 5/6 trial_group translation). Merged as PR #54
  (commit `d7c1571`), re-emit logged via PR #55 (commit `38b1781`),
  tagged `v6.8-wavesurfer-side-convention`.

---

## 2026-04-21 — Phase-close tag convention: tag every phase-close merge (Path A)

- *Context:* The original CLAUDE.md §8 bullet said "tags per phase" but
  did not specify which merges are "phase-close" vs atomic fix-ups vs
  dotted sub-phases. By 2026-04-20 we had accumulated a mix of tag
  formats (`v0.8-phase-4.5-lite-eye-midpoint` legacy-style;
  `v8a.7.5-criteria-hierarchy-port` new-style) and inconsistent
  coverage (Phase 8a.1 through 8a.7 merged without tags while 8a.7.5
  got one). With task #17 closing via PR #54 and tasks #20 / #8 queued
  behind it, the ambiguity forced a decision before more merges
  accumulated.

- *Decision: **Path A — tag every phase-close PR, including dotted
  sub-phases and letter-suffix atomic fixes.*** Format: `v{phase}-{slug}`
  where `{phase}` is the full dotted-or-lettered phase identifier
  (e.g. `6.7`, `6.7a`, `6.8`, `7`, `7.1`, `8a.7.5`) and `{slug}` is a
  hyphen-separated summary (don't repeat `phase-N` — the version prefix
  already encodes it). Tag message: `Phase {phase}: {short summary}`,
  one line where possible. Push the tag immediately after the merge so
  origin has the reference. Legacy `v0.X-phase-N-slug` tags
  (`v0.1-phase-1-foundations` through `v0.8-phase-4.5-lite-eye-midpoint`)
  are preserved as-is — they are permanent references in history and
  must not be renamed.

- *Rationale:* Priya asked "what is the actual utility of the tag?"
  and we enumerated four: (1) **named checkout** — `git checkout
  v6.7-session-manifest-refactor` is cheaper to type and remember than
  the merge SHA; (2) **diff anchor** — `git diff v6.7...v6.8` reads as
  intent ("what changed from SessionManifest refactor to L/R fix")
  rather than as raw commit range; (3) **branch-survival
  redundancy** — even if a feature branch is one day pruned, the tag
  keeps the merge commit permanently reachable; (4) **narrative
  boundary** — a phase-close tag is the atomic unit of "work that
  passed review together," which is the granularity users most often
  want to roll back to or reference. All four utilities benefit from
  per-phase-close coverage rather than "milestone" coverage; skipping
  sub-phases produced exactly the 8a.7 / 8a.7.5 inconsistency that
  motivated the question. Path B ("tag only round-numbered phases")
  was rejected because the atomic unit of review in this repo is the
  PR, and PRs map to sub-phases much more often than to round phases.

- *Enforced at:* `CLAUDE.md` §8 Git discipline (three bullets: format,
  message, push-immediately sequence). Observed as of 2026-04-21: tags
  `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`,
  `v8a.7-spout-endpoints-json-writer`, `v8a.7.5-criteria-hierarchy-port`
  all follow the new convention.

---

## 2026-04-20 — Phase 6.7 closes "SessionManifest is dead code" + makes `build_manifest()` symmetric across discoverable inputs

- *Context:* The mid-consolidation audit (2026-04-19) flagged that
  `SessionManifest` (Phase 1, DESIGN.md §4.2 — designed as the "single
  source of truth for what belongs to a session") was implemented but
  never consumed by any production orchestrator. Phases 2/3/4/6 each
  took `(animal, date, resolver)` and re-discovered their own files,
  duplicating discovery logic across phases and leaving the manifest
  effectively dead. A second issue surfaced during 6.7a's mid-phase
  review: `build_manifest()` was asymmetric — wavesurfer and video were
  optional (try/except → None / []), but DLC was required (raised
  `FileNotFoundError` on missing dir or empty filtered-file glob). This
  blocked Phase 2 spout-behavior processing on (a) sessions where video
  recording failed but wavesurfer is clean, and (b) newly-collected
  sessions before DLC inference has been run.

- *Decision (in three parts):*
  - **Wire `SessionManifest` in as the primary input contract for every
    phase orchestrator.** Each orchestrator gains a manifest-first
    primary signature `fn(manifest, resolver, ...)` plus a
    `fn_by_animal_date(animal, date, resolver, ...)` convenience
    wrapper that builds the manifest internally. Notebooks build the
    manifest in a new visible cell so the per-session discovery
    (wavesurfer / video / DLC / alignment template) is in notebook
    state rather than hidden inside the orchestrator. Done across
    Phase 2 (`process_session`), Phase 3 (`load_or_compute_alignment`),
    Phase 4 (`build_centered_parquet`), and Phase 6
    (`build_reward_aligned_analysis`). Phase 5 spatial functions
    operate on already-loaded parquets and don't need the manifest —
    only the Phase 5 orchestrator notebook builds manifests.
  - **Make `build_manifest()` symmetric across all discoverable
    inputs.** DLC is now discovered the same way as wavesurfer and
    video — present-or-empty, no raise. The "I need DLC to proceed"
    assertion is pushed into each DLC-consuming orchestrator (Phase 4
    parquet builder, Phase 6 reward-aligned analysis) at the top of
    its primary function, with a clear session-scoped error message.
    Phase 2 (DLC-free by design) does not add the guard. Phase 3
    alignment is also DLC-agnostic (it relates wavesurfer to camera
    frames; camera frames exist whether or not DLC has been run) and
    does not add the guard either — the first DLC guard fires in
    Phase 4. Strict input-dependency: each phase guards only what it
    actually reads.
  - **Two small orthogonal additions** surfaced by the audit are
    folded in as part of the refactor since they are scope-coupled to
    the manifest-first APIs:
    - `load_centered_fresh(h5_path, center_mode, likelihood_threshold)`
      in `src/stroke_orofacial/dlc_io/centering.py` — exploration
      escape hatch alongside the parquet-based pathway. Returns a
      centered DataFrame matching the parquet schema *without* writing
      to disk, so callers can sweep `likelihood_threshold`
      interactively for centering-reference picking. Complements the
      parquet cache; does not replace it.
    - `save_heatmap_npz(...)` in
      `src/stroke_orofacial/dlc_spatial/heatmaps.py` — writes the
      fine-grid histogram array as `heatmap_{date}.npz` alongside the
      existing PNG. Resolves the deferred 2026-04-19 fine-grid NPZ ask.

- *Rationale:* (a) Honest about what each phase consumes — the manifest
  abstraction fits the real use cases rather than forcing them. (b) The
  asymmetric DLC handling was an architectural bug, not a design
  limitation: the wrapper for Phase 2 inherited the DLC-required
  failure mode in 6.7a, blocking real workflows; the fix was to make
  manifest construction total and push the requirement check into the
  consuming phase. (c) Manifest-first orchestrators have a single
  consistent shape that's easy to learn and easy to wrap. (d) Notebook
  visibility: building the manifest in a cell makes the per-session
  picture inspectable mid-run rather than hidden inside per-phase
  discovery functions. (e) `load_centered_fresh()` and
  `save_heatmap_npz()` were called for in the Phase 6.7 kickoff
  scope; folding them in alongside the manifest-first signature
  changes amortizes one PR-review pass over both.

- *Enforced at:*
  - `src/stroke_orofacial/manifest.py` — `build_manifest()` lenient
    DLC discovery (post-6.7a-fix).
  - `src/stroke_orofacial/spout_behavior/session_processing.py`,
    `src/stroke_orofacial/alignment/timebase.py`,
    `src/stroke_orofacial/dlc_io/parquet.py`,
    `src/stroke_orofacial/dlc_spatial/reward_aligned.py` — manifest-
    first primary signatures + `*_by_animal_date` wrappers.
  - `src/stroke_orofacial/dlc_io/centering.py` —
    `load_centered_fresh()`.
  - `src/stroke_orofacial/dlc_spatial/heatmaps.py` —
    `save_heatmap_npz()`.
  - Notebooks `00_session_processing.ipynb`, `01_alignment.ipynb`,
    `10_dlc_build_parquets.ipynb`,
    `11_dlc_spatial_whole_session.ipynb`,
    `12_dlc_spatial_reward_aligned.ipynb` — each grew from 4 → 5 cells
    with a manifest-build cell.
  - `tests/test_manifest.py` — `test_missing_dlc_dir_raises` /
    `test_no_dlc_files_raises` rewritten to `*_yields_empty_lists`
    variants enforcing the new contract.
  - DLC-required guards in `build_centered_parquet` and
    `build_reward_aligned_analysis` cover-tested by
    `TestBuildCenteredParquetRaisesOnEmptyDlc` and
    `TestBuildRewardAlignedAnalysisRaisesOnEmptyDlc`.
  - `docs/MIGRATION_LOG.md` Phase 6.7 entry — full per-sub-phase
    summary, parity verification, and out-of-scope follow-ups.
  - Branch `phase-6.7-session-manifest-refactor`; commits `ee64ca3`,
    `276148b`, `d2e89c1`, `0126156`, `0ce63d1`, plus this docs commit.

---

## 2026-04-20 — Phase 8a architecture (criteria slugs, sub-phasing, schema 2.0.0, 8a.7.5 split, legacy-snippets pattern)

- *Context:* Phase 8a (spout-only recovery trajectories) was sequenced as a mid-experiment deliverable after the Audit Item 10 Q1–Q10 resolutions. Execution spanned seven sub-phases (8a.1 through 8a.7) over 2026-04-20, plus the pending 8a.7.5 criteria hierarchy port. Several cross-cutting decisions made during that span were not individually captured — this entry bundles them for future readers.
- *Decisions (grouped):*
  - **Criteria slug finalization (fulfills Audit Item 10 Q2).** The Q2 working-proposal slugs were wrong — they described guesses about what the criteria compute. Final slugs describe the actual legacy-computation semantics (from `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` §1):
    - `criteria_first_correct_lick_present` (C3, legacy `criteria_3`): per-trial boolean — was there a first correct-side lick within the C3 window after reward.
    - `criteria_correct_lick_count_threshold` (C4, legacy `criteria_4`): per-trial boolean — enough correct-side licks AND few enough incorrect-side licks within the C4 window.
    - `criteria_session_trial_pass_fraction_above_threshold` (C2, legacy `criteria_2`): per-session-per-side boolean — fraction of trials passing C3 ∩ C4 ≥ threshold.
    - `criteria_training_pass_consecutive_sessions` (C1, legacy `criteria_1`): multi-session boolean — C2[L] AND C2[R] True on the last N consecutive sessions.
    Slug map and bijective validator live in `src/stroke_orofacial/spout_behavior/criteria_slugs.py` (Phase 8a.1). Legacy → new and new → legacy lookups both raise on unknown keys.
  - **Phase 8a sub-phasing.** Eight sub-phases, each a separate feature branch + PR:
    - **8a.1** (merged) — criteria slug foundation (slug map, validator, rename hardcoded constants block from `criteria_1/2/3/4` to descriptive slugs in `configs/defaults.yaml`).
    - **8a.2** (merged) — lick-bout detector (`find_lick_bouts`, `LickBout` dataclass, integration against vendored `_utils/bool_indexing.py`).
    - **8a.3** (merged) — per-trial endpoint primitives + shared contracts (`TrialRecord`, `EndpointResult`, `build_per_trial_records`).
    - **8a.4** (merged) — within-session trend endpoints (`within_session_learning_curve`, `within_session_change`).
    - **8a.5** (merged) — inter-session persistence endpoint scaffold (per-session side; cross-session aggregation deferred to cohort layer).
    - **8a.6** (merged) — engagement-extras endpoints (`switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`).
    - **8a.7** (merged) — per-session JSON writer + schema 2.0.0 with criteria emitted as sentinels (D5–D8, below).
    - **8a.7.5** (in flight) — criteria hierarchy port: compute C3, C4, C2 as real values (replacing the 8a.7 sentinels). C1 intentionally stays a sentinel; see "8a.7.5 split" below.
    - **8a.8** (planned, no kickoff prompt yet) — recovery-trajectory visualization + phenotype-classification prototype.
    - **8a.9** (planned, scope TBD) — close-out / legacy behavior-report walkthrough rollup + any Audit Item 10 Q9 scope items that surface mid-port.
  - **Schema 2.0.0 design (8a.7, D5–D8).**
    - Three top-level blocks: `metadata` (session identity, source NPZ SHA-256 hashes, endpoints/criteria params, schema_version), `endpoints` (10 canonical slots), `criteria` (4 canonical slots). Plus a top-level `schema_version` string.
    - **Every slot is always present.** Absent computations land as explicit sentinel dicts, never `null` or missing keys. Two sentinel kinds: `{"status": "not_yet_computed", "port_scheduled_for": "<subphase>"}` for deferred ports (used for C3/C4/C2 in 8a.7, replaced in 8a.7.5) and `{"status": "requires_cohort_aggregation", "computed_at": "cohort_aggregation_stage"}` for quantities that are not per-session functions (used for C1 and for `inter_session_persistence`).
    - **Strict validation.** Caller passes the full 10-key `endpoints` dict; missing or unknown keys raise `ValueError`. Criteria sentinels are constructed internally from the slug map — caller does not pass them. This forces the caller to express intent rather than silently drop.
    - **Atomic write** via `tempfile.TemporaryDirectory` + `Path.replace` in the output's parent directory (same filesystem, same idiom as `dlc_io/parquet.py`).
    - **Provenance via SHA-256** of source NPZ bytes. One-shot reads are fine at Phase 2 NPZ sizes.
    - **Parallel to legacy `report.json`.** The new writer emits a separate `spout_endpoints.json`; the legacy `behavior_report_PS.py:report.json` pathway is not touched. No parity test exists at the file level — the schemas are structurally incompatible by design. Parity lives at the individual-endpoint computation level (inside `tests/test_*.py`), not at the file-shape level.
  - **8a.7.5 split from 8a.7 (provenance contract).** The original 8a.7 scope included computing all four criteria values. This was split: 8a.7 ships the writer + schema + three per-session-computable criteria slots as sentinels + C1 as a cohort-aggregation sentinel; 8a.7.5 ports C3/C4/C2 into real values; **C1 stays a sentinel permanently in the per-session JSON and is computed later in a dedicated cohort-aggregation stage.** Rationale: the per-session JSON's value is that it's a pure function of per-session inputs — rerunning the writer on a session produces byte-identical output iff the inputs are byte-identical. Embedding a multi-session value (C1 spans `num_consecutive_pass` sessions) breaks this contract: any upstream session's data change would silently invalidate C1 in every post-affected JSON without rewriting those JSONs. The same issue affects `inter_session_persistence` (already sentinel) — and both will be computed together in a future cohort layer that explicitly tracks which per-session JSONs it depends on, so upstream changes trigger visible rebuilds rather than silent staleness. This is the same architectural principle we use in Phase 5/6 where reward-aligned aggregates live separately from per-session spatial outputs.
  - **`_v2` suffix dropped (naming hygiene, 2026-04-20 mid-8a.7).** The 8a.7 kickoff originally named the new artifact `spout_endpoints_v2.json` and suffixed the config block (`endpoints_v2:`) and API kwargs (`endpoints_v2_params=`) to disambiguate from the legacy `report.json`. Dropped everywhere in the live codebase (new outputs land in their own tree; no collisions). Retained in frozen archaeology / kickoff docs under `docs/PHASE_8A_*.md` and `docs/prompts/phase-8a-*.md` as historical decision-trail context — those docs are snapshots of the state at the moment they were written.
  - **Legacy-snippets pattern (new, introduced 2026-04-20).** Read-only snippets of canonical legacy source files may be committed into `docs/legacy_snippets/` under CLAUDE.md §1–§3 compliance (the legacy file itself is not touched; the snippet is new material in this repo). Each snippet must carry a provenance header documenting: source path, line range captured, mod-time-based disambiguation result, and CLAUDE.md compliance rationale. Triggered by the 8a.7.5 workflow where Windows Claude Code couldn't reach the Mac-local legacy Github clone; the snippet commits the exact excerpt needed for byte-identical parity so the port is self-contained in-repo. First instance: `docs/legacy_snippets/behavior_report_PS_455_551.py` covering lines 385-565 of `behavior_report_PS.py` (C3/C4/C34/C2/C1 computation + `fn_convert_window_to_samples`, `fn_flip_lr` helpers). Files in this directory carry `# ruff: noqa` + `# fmt: off` so ruff and formatters do not flag the verbatim legacy code.
  - **External bnpm parity finding — Phase-13-pattern intentional divergence from upstream bnpm 0.6.0 (post-merge of 8a.7.5).** After PR #42 merged, an independent parity sweep (Mac-local scratch script running the inline C3/C4/C2 reference algorithm with bnpm 0.6.0's `find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1 session each) found one Category 2 divergence at PS50/20250324 trial k=40, L side. Root cause: bnpm 0.6.0's `find_idx_within_eps` has a `len(arr) - 1` clamp bug at the right edge — `np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr)` when the window right edge extends past every element of the session-wide array, and upstream then clamps to `len(arr) - 1`, dropping the final lick. Production (`criteria.py:_sub_window_counts` uses `(licks >= lo) & (licks < hi)` on pre-windowed `TrialRecord.licks_*_indices_in_window`) is correct. **Decision:** treat as an intentional divergence from upstream bnpm per the Phase 13 vendoring pattern — production stays untouched; documentation surfaces the divergence in `docs/MIGRATION_LOG.md` Phase 8a.7.5 post-merge appendix; a synthetic regression guard lives at `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`; upstream bnpm issue filing with RichieHakim is deferred (optional, Priya's call). **Forward obligation:** the same clamp bug exists in the private `_find_idx_within_eps` port at `src/stroke_orofacial/spout_behavior/bouts.py:236-256` (peri-reward mask caller; not called by criteria.py). A follow-up fix-PR will land the corrected helper after the Phase 5/6 indexing-module refactor (`_find_idx_within_eps` → `_utils/indexing.py`) and must land before Phase 5/6 code writes begin so Phase 5/6 does not consume the buggy helper. PS51/20250502 re-run skipped (not needed for triage). **Closure (2026-04-20):** the indexing-module refactor landed as PR #45 (squash commit `92b5d88`), and the clamp-fix landed as PR #46 — production `_utils/indexing.py:_find_idx_within_eps` no longer clamps the upper bound, `tests/test_indexing.py` is the mirror-in-minimum regression coverage, and the forward obligation is discharged. Phase 5/6 kickoff is unblocked.
- *Rationale:*
  - **Slug finalization now (not at phase start) was correct.** The Q2 entry deliberately deferred slug naming to 8a kickoff because the legacy formulas had to be re-read to name them honestly. The working proposals in the Q2 entry (`criteria_total_licks`, `criteria_directional_accuracy`, etc.) turned out to be wrong guesses; the actual slugs describe the actual computation.
  - **Sub-phasing kept PRs reviewable.** Seven (soon eight-plus) sub-phase PRs are tractable to review individually; a single 8a mega-PR would have been unreviewable.
  - **Schema 2.0.0 strictness.** Every "silent drop" mode in past phases has cost debugging time. Forcing explicit sentinels + strict key validation means absent computations are always detected at write time, not at downstream read time.
  - **8a.7.5 split over "just compute C1 too."** The temptation to compute C1 inside the per-session writer since C2 per-session values are available there is real — it would be ~5 lines. Resisting it was the right call: once one multi-session quantity leaks into a per-session file, the provenance contract is broken for every downstream consumer, and the silent-staleness failure mode is genuinely hard to detect.
  - **`_v2` suffix drop.** The `_v2` suffix was defensive in the kickoff draft stage; by implementation time it was noise. Removing it before any consumer started reading `spout_endpoints.json` was cheaper than carrying the suffix forward.
  - **Legacy snippets over "grant Windows access to the legacy clone."** The legacy repos are Mac-local Github clones, not on MICROSCOPE, so no server-access fix was available. Copying files to MICROSCOPE was rejected (data-discipline concerns + staleness risk). Committing a targeted excerpt with a provenance header keeps the parity reference inside the consolidation repo where it's version-controlled and reviewable, at the cost of ~120 lines of in-repo duplication.
  - **External bnpm parity → intentional Phase-13-pattern divergence.** Three options were considered once the PS50/20250324 Category 2 divergence was traced to upstream bnpm's clamp bug: (A) monkeypatch or vendor a fixed `find_idx_within_eps` into the consolidated codebase *now* and leave `criteria.py` as-is; (B) change `criteria.py` to match upstream's buggy behavior so external-bnpm parity is byte-identical; (C) document the divergence + add a regression guard, and defer the upstream helper's clamp fix to its own PR once `_find_idx_within_eps` is factored into `_utils/indexing.py`. Option (B) was rejected immediately (the value of consolidation is to make the pipeline *more* correct, not less — the Phase 13 vendoring policy already establishes that preserving buggy upstream behavior byte-for-byte is a non-goal). Option (A) was rejected because `criteria.py` does not call `_find_idx_within_eps` at all — it uses the numpy mask directly on pre-windowed `TrialRecord` licks — so vendoring now would be a no-op for the sub-phase and conflate two PR scopes. Option (C) was chosen: it keeps the 8a.7.5 sub-phase cleanly closed (production already correct); the fix-PR for the `bouts.py` port of the same helper lives in its own scope with its own parity verification against `tests/test_session_processing.py` baselines + the Phase 13b `max_frac=1e-4` tolerance; and the regression guard ensures any future refactor that reintroduces a searchsorted-with-clamp pattern fails loud rather than silently mis-counting.
- *Enforced at:* `src/stroke_orofacial/spout_behavior/criteria_slugs.py` (slug map + validator). `src/stroke_orofacial/spout_behavior/endpoints_writer.py` (`SCHEMA_VERSION = "2.0.0"`, `CANONICAL_ENDPOINT_NAMES`, two sentinel dicts, strict key validation). `configs/defaults.yaml` `spout_behavior.endpoints:` and `spout_behavior.criteria:` blocks. `tests/test_criteria_slugs.py`, `tests/test_endpoints_writer.py`, `tests/test_endpoints_per_trial.py` (+ the 8a.2/8a.4/8a.5/8a.6 test files). `docs/MIGRATION_LOG.md` Phase 8a.7 entry (and Phase 8a.7.5 entry post-merge appendix for the external bnpm parity finding, Phase 5/6-prep entry for the indexing-module refactor, and Clamp-fix entry for the right-edge clamp removal). `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` (kickoff for the criteria port). `docs/legacy_snippets/behavior_report_PS_455_551.py` (first instance of the legacy-snippets pattern). `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it` (regression guard for the external-bnpm-parity clamp-bug path). `src/stroke_orofacial/_utils/indexing.py` (vendored `_find_idx_within_eps` with the clamp removed). `tests/test_indexing.py` (mirror-in-minimum regression guards for the private port: PS50/20250324 reproducer + edge cases + random-input parity vs. independent numpy-mask oracle).

---

## 2026-04-20 — Phase 13 vendor bnpm (drop `bnpm[core]` + torch; vendor 4 pure-numpy helpers)

- *Context:* Phase 13's unified `environment.yml` kept `bnpm[core]` because two modules in `spout_behavior/` call four small helpers from it (`bnpm.indexing.idx2bool`, `bnpm.indexing.widen_bool_sparse`, `bnpm.indexing.set_short_bool_to_low`, and `bnpm.timeSeries.simple_smooth`). After the HDF5 stack was stabilized on Windows, pytest still couldn't collect because `import bnpm.indexing` hit `OSError: [WinError 127] The specified procedure could not be found` on `torch\lib\shm.dll`. Root cause: bnpm unconditionally imports `torch` at module load (both `bnpm/indexing.py` and `bnpm/timeSeries.py` do `import torch` at the top), and the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` (Intel OpenMP) that clashes with conda-forge MKL's `libomp.dll` (LLVM OpenMP). The same env on Mac (torch 2.2.2 from PyPI) runs fine — it's a Windows-only wheel-packaging / MSVC-runtime issue. `OMP: Error #15: Initializing libomp.dll, but found libiomp5md.dll already initialized` was observed on the bad import. No clean conda-only torch build unblocks this without another round of env tweaking.
- *Decision:* Drop `bnpm` (and thereby torch / numba / llvmlite / cmake) from the unified env entirely. Vendor the four used helpers into `src/stroke_orofacial/_utils/bool_indexing.py` under bnpm's MIT license (© 2021 RichieHakim), with the license text reproduced in the module docstring and attribution in the `pyproject.toml` / `environment.yml` comments. The vendored helpers are pure numpy — no torch, no numba — so they compile nowhere, link to nothing, and work identically on Mac and Windows. The upstream reference for all four is **bnpm 0.6.0** (the version installed in Priya's Mac `frsb` env at the time of vendoring). Two of the four (`idx2bool`, `gaussian_smooth_1d`) are strict ports of 0.6.0. The other two (`widen_bool_sparse`, `set_short_bool_to_low`) **intentionally diverge from 0.6.0 to fix two upstream bugs discovered while writing the parity tests** — see "Intentional bug fixes" below. Add `tests/test_vendored_bool_indexing.py` with a mixed strategy: strict ports are parity-tested against live bnpm via `pytest.importorskip`; divergent ports are tested against hand-rolled expected outputs plus an independent reference implementation (Python-loop / `itertools.groupby`). On machines with bnpm installed (Priya's Mac `frsb` env), all 11 tests pass. On the new env (no bnpm), the 5 strict-port tests skip cleanly and the 6 divergent-port tests run and pass.
- *Intentional bug fixes over upstream bnpm 0.6.0:*
  - `widen_bool_sparse`: upstream detects rising **and** falling edges of each True run via diff and widens each edge by `[edge - n_before, edge + n_after + 1]`. Because a falling edge lives one position past the run's last True, the trailing side of every run overshoots by an extra `n_after + 1` samples — an asymmetric, hard-to-reason-about expansion that does not match what callers (`bouts.py`) document as "widen each True run by n_before before / n_after after". Vendored version widens every True index by `[i - n_before, i + n_after + 1]` (symmetric, idempotent, matches the documented caller intent).
  - `set_short_bool_to_low`: upstream hand-patches edge runs and appends `out.size - 1` (rather than `out.size`) as the closing falling-edge index for a trailing-True run. This **under-counts trailing runs by 1**, so e.g. `b = [..., True]` with `n = 2` never flags the length-1 trailing run as short. Vendored version uses a padded-array diff that measures every run's length correctly.
- *Rationale:*
  - **Eliminates the Windows-torch failure mode at the root.** The only reason torch was in the env closure at all was that bnpm imports it. Once bnpm is gone, there is no torch dependency anywhere in `src/` / `tests/` / `notebooks/`, and the whole MKL/OMP collision class of bugs can't occur. **This is the primary reason to vendor.**
  - **Proportional vendoring.** Four helpers totalling ~60 lines of pure numpy, with MIT permission to redistribute. That is a much cheaper long-term carrying cost than running a conda-only torch install, a platform-specific env, or an import-time monkeypatch. Each vendored helper carries a docstring pointer back to the bnpm function it came from, so the provenance is traceable and future bnpm bumps can be manually mirrored if wanted.
  - **The bug fixes are a separable "while we're here" argument.** They were not the reason to vendor — Windows-torch was. But once parity tests were being written, two bugs surfaced that cause `bouts.py` to produce surprising output relative to what its own docstrings promise. Preserving buggy upstream behavior byte-for-byte (option: match upstream exactly, propagate the bugs) was rejected: the value of vendoring is to make the pipeline more reliable and more reasonable to reason about, not less. Fixing the two bugs preserves **caller intent**. Measured drift from the legacy `session_processing3` baselines on PS46/20250307 is small and bounded (2 samples on `lick_bool_bad`, 51 on `quiet_bool`, 0 elsewhere — out of 3,610,000 per array; see `docs/MIGRATION_LOG.md` Phase 13b "Intentional behavior differences vs. legacy" for the full table and scope analysis).
  - **Env slimming as a side benefit.** Dropping bnpm also lets us drop `numba`, `llvmlite`, and `cmake`, which were only in `environment.yml` to avoid source-building `llvmlite` during the `bnpm[core]` pip install on Intel Mac + Python 3.11. This shrinks the env materially and removes one more C-extension ABI dimension (numba's LLVM version) from the platform matrix.
  - **Mixed-strategy test suite is robust.** For strict ports: `pytest.importorskip` means the test is never a blocker in the bnpm-less env but is still exercised whenever anyone runs the suite on a machine with bnpm. For divergent ports: hand-rolled expected outputs + an independent reference implementation means the test runs everywhere and validates the specific corrected behavior, not incidental equality with whatever upstream version happens to be installed.
  - **License compliance.** bnpm is MIT-licensed, which explicitly permits redistribution with attribution and modification. The repo is a private / internal research codebase, but the copyright notice is preserved in the vendored module docstring regardless. The two divergent helpers note their modifications in their own docstrings (MIT does not require this, but it keeps provenance honest).
- *Enforced at:* `src/stroke_orofacial/_utils/bool_indexing.py` (vendored module with MIT attribution; two divergent helpers carry per-function docstrings describing the upstream bug and the vendored fix). `src/stroke_orofacial/_utils/__init__.py` (marks utils as internal API). `src/stroke_orofacial/spout_behavior/bouts.py` and `src/stroke_orofacial/spout_behavior/wavesurfer_io.py` (imports rewritten, 11 callsites updated). `tests/test_vendored_bool_indexing.py` (mixed-strategy coverage: 5 strict-port parity tests against live bnpm via `importorskip`; 6 hand-rolled tests for the divergent helpers). `tests/test_bouts.py` + `tests/test_session_processing.py` (integration-test bool-array tolerances relaxed to `max_frac=1e-4` via a `_assert_bool_near_equal` helper, absorbing the measured 2-51 sample drift from the bug fixes; see MIGRATION_LOG Phase 13b point 5 for why this is un-lumped from the unrelated LAPACK-drift rtol change in `tests/test_timebase.py`). `pyproject.toml` (dropped `bnpm[core]`, dropped `pywavesurfer` from `dependencies` — install via `pip install pywavesurfer --no-deps` post-env-create — amended Phase 13 comment). `environment.yml` (dropped `bnpm[core]`, `numba`, `cmake`; expanded "Deliberately NOT included" trailer). Migration-log Phase 13 entry records the vendoring and the bug fixes as part of closing the phase.

---

## 2026-04-19 — Phase 13 env unification (single `stroke_orofacial` conda env for Mac + Windows)

- *Context:* Legacy setup used two different conda envs for the same analysis work: `frsb` on Mac (Python 3.11, pip-installed deps) and `deeplabcut` on Windows (Python 3.10, heavy DLC/CUDA/PyTorch/ffmpeg stack). Env-name drift created friction across the permanent Cowork-on-Mac + Claude-Code-on-Windows workflow; per-session prompts had to branch on platform. Additionally, pyproject.toml declared runtime deps (`opencv-contrib-python`, `tqdm`) that were never imported anywhere, and was missing three deps that legacy DLC-analysis notebooks on MICROSCOPE actually use (`scicomap`, `patsy`, `pot`).
- *Decision:*
  - **One unified `environment.yml`** replaces the `environment-mac.yml` / `environment-windows.yml` pair. New env name is `stroke_orofacial`.
  - **Runs PARALLEL to existing envs.** The `frsb` (Mac) and especially the `deeplabcut` (Windows) envs are not touched; `deeplabcut` remains the correct env for DLC training/inference and for the `keypoint_moseq` analysis thread. This means rollback is a single `conda activate frsb` or `conda activate deeplabcut` away if anything breaks.
  - **Python 3.11** (matches `requires-python = ">=3.11"` in pyproject.toml; was 3.10 on Windows `deeplabcut`).
  - **Channels:** `conda-forge` primary, `defaults` fallback. Previously `defaults`-only with everything pip-installed; conda-forge gives faster resolves on Windows for the jupyter stack.
  - **Dep scope derived from a full import audit** of `src/`, `tests/`, `notebooks/`, AND every notebook under `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`. Every package in the env traces to at least one real import or is a transitive pin (`h5py`) / in-flight port prerequisite. Full matrix of what was added / kept / dropped:
    - **Actively imported (kept):** numpy, pandas, pyarrow, scipy, matplotlib, pyyaml, pytables (pip name `tables`), h5py, pywavesurfer, `bnpm[core]`. Dev: pytest, ruff, ipykernel, jupyter, nbconvert.
    - **Reserved for Phase 5/7/9 (kept):** statsmodels, scikit-learn, seaborn, patsy, pot. All five are imported by one or more legacy DLC analysis notebooks on MICROSCOPE that are scheduled for port in #10 / #11 / #12b / #12c / #12d.
    - **Added this phase:** `patsy` (R-style formulas for statsmodels; imported by the locked Q6 re-read notebooks `20260203_tongue` + `20260416_jaw`), `pot` aka POT (Python Optimal Transport — Wasserstein distance for pixel-bin distribution comparison; imported by 3 legacy DLC stats notebooks), `scicomap` (scientific colormaps; imported by 6 legacy DLC spatial notebooks, pip-only as not on conda-forge), `nbconvert` (for the `jupyter nbconvert --execute --inplace` CI pattern that Phase 4.5-lite's sweep established).
    - **Dropped:** `opencv-contrib-python` (no imports in src/, tests/, notebooks/, and the one MICROSCOPE notebook that imported `cv2` is the legacy O2 batch script, already consolidated into `dlc_inference_o2/`), `tqdm` (no imports anywhere).
    - **Explicitly not included (belongs in `deeplabcut` env):** deeplabcut, pytorch, torchvision, cudatoolkit, tensorflow, ffmpeg, dlclibrary, keras, cv2, paramiko, scp. All of these are imported ONLY by `src/stroke_orofacial/dlc_inference_o2/runner.py` (which runs on O2 inside `deeplabcut`) and by the legacy `20251112_DLC_batch_video_analysis_O2.ipynb` whose functionality is now consolidated into the pipeline's `dlc_inference_o2/` submodule.
    - **Explicitly not included (out-of-scope for v1):** jax, jax_moseq, keypoint_moseq. These appear only in `20260209_keypoint_moseq*.ipynb`. Keypoint-MoSeq is not part of any v1 phase or Q1–Q10 audit decision. If it becomes a v2 deliverable, it should live in its own env to avoid dragging JAX into the core analysis env.
  - **`bnpm[core]` extra** explicitly used in both environment.yml and pyproject.toml per https://pypi.org/project/bnpm/. Plain `bnpm` pulls in heavy optional deps we don't use; the `[core]` extra is the minimum install that covers `bnpm.indexing` and `bnpm.timeSeries` (the only two subpackages imported by `spout_behavior/`).
  - **`pyproject.toml` deps brought into agreement** with environment.yml so `pip install -e .` produces an equivalent install.
- *Rationale:*
  - Env-name parity across the two-laptop workflow eliminates a recurring source of paste-in-prompt bugs where paths and activate commands had to branch by platform.
  - Running PARALLEL to existing envs (vs. in-place upgrade) makes the transition fully reversible and preserves `deeplabcut` for its still-valid uses (DLC training, O2 inference, Keypoint-MoSeq).
  - Dropping two unused heavy deps (opencv-contrib-python ≈ 40 MB, tqdm) keeps the env lean.
  - Adding the three MICROSCOPE-notebook deps (scicomap, patsy, pot) now avoids blocking on env bumps when Phase 5/7/9 ports land.
  - Excluding the entire DLC/CUDA/PyTorch/ffmpeg stack — which is what made `deeplabcut` a slow, conflict-prone install — is the biggest win: the new env should install in minutes, not hours, and is free of GPU driver / CUDA version entanglements.
- *Enforced at:* `environment.yml` (new, unified). `pyproject.toml` `[project.dependencies]` in agreement. `environment-mac.yml` and `environment-windows.yml` reduced to deprecation stubs pointing at `environment.yml`; to be `git rm`-ed once both platforms have verified the new env installs cleanly. Migration-log entry for Phase 13 will close out this work once both platforms are verified.

---

## 2026-04-19 — Audit Item 10 (scientific endpoint inventory) — Q1–Q10 resolutions

- *Context:* Mid-consolidation audit Item 10 inventoried 26 scientific endpoints across 6 categories (A–F) from the two legacy repos (`facerhythm_stroke_biomarker_exp`, `facerhythm_stroke_biomarker_exp_Priya`), written up in `docs/SCIENTIFIC_ENDPOINTS.md`. Ten open questions (Q1–Q10) at the bottom of that doc needed Priya's call before the audit branch could merge. Each Q is resolved below.
- *Decision (grouped, one per Q):*
  - **Q1 — DTW alignment vs linear transform canonicality.** Keep linear (current Phase 3) canonical. DTW notebook's downstream output (`playground_dtw_20251202PS.ipynb`) is actually *strictly worse* than Phase 3: the notebook computes DTW edge matches but then collapses to a linear transform fit from only the first/last matched anchors. Phase 3 already does better — DTW-style `_align_edge_sequences` followed by `np.polyfit(cam_edge_idx, ws_edge_idx, deg=1)` over **all** matched edge pairs (see `src/stroke_orofacial/alignment/frame_sync.py` lines 195–274). Additionally: DTW as written does NOT solve mid-session frame drops (no piecewise-linear transform exists in any legacy code). True drop correction is flagged as future work pending QC evidence. **Carve-out:** port the one valuable diagnostic from the DTW notebook — cell 22's per-edge-shift plot — as a QC figure rolled into Phase 5.5 polish (task #16). If that plot ever surfaces a session with clear mid-session breakpoints, open a ticket for piecewise-linear fit then.
  - **Q2 — Criteria renaming.** Rename `criteria_1/2/3/4` to descriptive slugs. Log the rename intent here; finalize exact slug names at Phase 8a kickoff (task #10) when spout-behavior scope is concrete and the criteria are being actively wired into recovery-trajectory outputs. Current working proposals (subject to Phase 8a finalization): something like `criteria_total_licks`, `criteria_directional_accuracy`, `criteria_reward_rate`, `criteria_latency` — to be confirmed against the actual legacy formulas.
  - **Q3 — Recovery-phenotype stratification timing.** Split: *visualization* (recovery-curve plots colored / faceted by phenotype) lands in Phase 8a; *classification* (the algorithm that assigns each animal to fast / slow / non-recoverer) is a standalone **new Phase 9.1**, sequenced between 9a and 9b. This mirrors the 8a/8b spout-vs-DLC dependency split: 9a runs spout-behavior stats *unstratified* first (establishes the framework), 9.1 then fits phenotype classes on 9a outputs, and 9b runs DLC kinematic stats with phenotype as a covariate available.
  - **Q4 — Quiet-period endpoint scope.** Reserve for FaceRhythm (v2, post-v1). `quiet_period_batch_playground.ipynb` computes a quiet-bool mask (`speed<5mm/s` AND not grooming AND no licks/rewards ±1s AND duration≥3s) but the mask has no downstream endpoint consumer in the current pipeline. Keeping it out of v1 avoids scope creep on a feature without a clear user.
  - **Q5 — FaceRhythm TCA scope.** Placeholder stub reserved in Phase 11+ slot. Do not build now. Task will be created when Phase 10 (cross-animal stats) is done and v2 planning begins.
  - **Q6 — Kinematic endpoint design for Phase 7.** **Scope = 6 core + 4 secondary + face-velocity PCs 1–3 + PSD on tongue/jaw/whisker.** The 6 core endpoints (tongue protrusion amplitude, tongue velocity, jaw opening amplitude, jaw velocity, whisker protraction frequency, whisker mean angle) and the 4 secondary (W1 mean baseline whisker angle, W2 whisker angle RMS, W3 whisker protraction event counts, F1 face-velocity PC1 power / N1 nose deflection RMS) are locked. Face-velocity PCs 1, 2, and 3 all included; PC1 interpretation is itself a discussion topic Priya wants to work on with Cowork during Phase 7 implementation. PSD computed on tongue, jaw, and whisker angle traces. **Granularity = both** per-trial (for reward-aligned stats) and whole-session (for phenotype/state summaries). **HARD prerequisite:** Phase 7 must use the *interpolated continuous kinematic traces* (which already exist in Priya's legacy code for tongue and jaw, where video occlusions make raw traces have gaps) — this interpolation must be carried forward into the new consolidated pipeline, not re-derived from raw DLC. **Re-read assignment for Phase 7 kickoff:** the two MICROSCOPE `code/` folder notebooks `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` contain multiple existing kinematic analyses to build on (statistics need work, PSD section is outdated and should be rewritten — not ported).
  - **Q7 — Sex + age in cohort metadata.** Add both `sex` and `date_of_birth` fields to `AnimalInfo` and `configs/animals.yaml`. DOB allows age-at-session and age-at-stroke to be computed as covariates. **Cohort classification = mixed** (not separated into sex-stratified cohorts up front — handled as a covariate in Phase 9 stats, like DOB). New task created for the schema addition.
  - **Q8 — Stats integration timing.** Split Phase 9 into **9a (spout stats framework + spout endpoints)** → **9.1 (phenotype classification)** → **9b (DLC kinematic stats)**, mirroring the Phase 8a/8b data-dependency split. 9a establishes the stats framework on the simpler spout endpoints (no DLC prerequisite), 9.1 fits phenotype classes on 9a outputs, 9b then applies the now-validated framework to the richer DLC kinematic endpoints from Phase 7 with phenotype as an available covariate.
  - **Q9 — New spout behavior endpoints.** Add 8 new endpoints to the spout pipeline: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change` (deliberately neutral naming; *not* `fatigue` which pre-judges direction), `switch_cost`, `directional_lick_accuracy` (number + fraction of licks on correct vs incorrect side per session, separately for L and R trials — replaces the originally-proposed `perseverative_lick_fraction` whose naming was too pejorative), `first_lick_latency`, and `latency_variability`. **Follow-up work:** Many of these (or close variants) already exist somewhere in `facerhythm_stroke_biomarker_exp_Priya`'s spout analysis pipeline. Phase 8a kickoff must include a systematic walkthrough of the legacy behavior-report code to (a) match each of the 8 to an existing implementation where possible, (b) surface others worth keeping that we haven't listed here, (c) explicitly discard any that are stale / redundant / unused.
  - **Q10 — Gap prioritization.** No separate prioritization needed — the derived ordering already matches the task queue. All 6 gaps listed in `docs/SCIENTIFIC_ENDPOINTS.md`'s "Gaps" section auto-resolve as follows: DLC kinematics gap → Phase 7 (task #11); recovery-phenotype gap → Phase 8a viz + Phase 9.1 classification; stats framework gap → Phase 9a / 9b; cohort metadata gap (sex/DOB) → new schema task; FaceRhythm quiet-period gap → deferred to v2 per Q4; FaceRhythm TCA gap → deferred to Phase 11+ per Q5. Task queue order stays as-is.
- *Rationale:*
  - **Q1:** Phase 3's implementation objectively dominates the DTW notebook's end output. The QC plot carve-out is ~20 lines and gives us the one-off diagnostic value without muddying canonicality.
  - **Q2–Q3 deferral to kickoff:** Slug names and stratification UI are easier to finalize when concrete outputs are being laid out in-phase than in the abstract now.
  - **Q4–Q5:** Both features lack a clear v1 user; pushing them to v2 / Phase 11+ keeps v1 scope honest.
  - **Q6:** Biggest single expansion in Phase 7 scope. Locked early so the phase prompt can be structured around concrete deliverables. Interpolated-trace prerequisite is non-negotiable — tongue/jaw raw DLC traces have occlusion gaps that would contaminate velocity/PSD computation if not addressed.
  - **Q7:** Adding both fields is cheap and prevents retrofitting later. Covariate (not cohort-split) handling matches how age, weight, etc. are normally handled in mouse behavior studies.
  - **Q8:** 9a/9.1/9b cleanly decouples spout-stats infrastructure development from DLC-stats development, and phenotype classification from either. Same pattern as 8a/8b worked well.
  - **Q9:** 8 new endpoints is a lot; the follow-up walkthrough of legacy behavior code is the gatekeeper that prevents us from duplicating implementations and also surfaces additional endpoints we'd otherwise miss. Naming changes (`within_session_change` not `fatigue`; `directional_lick_accuracy` not `perseverative_lick_fraction`) reflect Priya's preference for non-loaded terminology.
  - **Q10:** The gaps section in SCIENTIFIC_ENDPOINTS.md was a listing of what was missing from the legacy repos; the current task queue was built with those same gaps in mind, so no re-prioritization needed.
- *Enforced at:* Phase 7 kickoff (task #11) will include the locked Q6 scope + interpolated-trace prerequisite + re-read of the `20260203` and `20260416` DLC notebooks. Phase 8a kickoff (task #10) will include the 8 Q9 endpoints + legacy behavior-report walkthrough + Q2 slug finalization + Q3 phenotype-viz design. New Phase 9.1 task (phenotype classification, between 9a and 9b). New task for `AnimalInfo` / `animals.yaml` sex + DOB field addition. New task for `facerhythm_tca` Phase 11+ stub (v2 planning). The Q1 per-edge-shift QC plot rolls into the existing Phase 5.5 polish task (#16). `docs/SCIENTIFIC_ENDPOINTS.md`'s Q1–Q10 section is superseded by this DECISIONS entry and can be considered historical from now on.

---

## 2026-04-19 — Audit Item 9 (SVG outputs + output reorganization) — lighter split, reorg between 6.7 and 6.8

- *Context:* Audit Item 9 addressed two concerns: (a) no SVG outputs anywhere, only PNGs — inconvenient for publication-figure assembly; (b) current output layout is phase-then-bodypart-then-animal, which mixes output types and makes walking `dlc_analysis/` to gather "all heatmaps" or "all difference maps" awkward.
- *Decision:*
  - **Keep the existing top-level split** by data-collection type: `spout_behavior/` and `dlc_analysis/` stay as top-level directories. Do NOT introduce a top-level `figures/` vs `intermediates/` split.
  - **Reorganize within each tree to be figure-type-first** so publication-assembly workflows can walk e.g. `dlc_analysis/heatmaps/` or `dlc_analysis/difference_maps/` directly. Proposed `dlc_analysis/` structure:
    ```
    dlc_analysis/
    ├── heatmaps/
    │   ├── whole_session/{bodypart}_{center_mode}/{animal}/{date}.{png,svg}
    │   └── reward_aligned/{bodypart}_{center_mode}/{window}/{trial_group}/{animal}/{date}.{png,svg}
    ├── difference_maps/
    │   ├── whole_session/...
    │   └── reward_aligned/...
    ├── heatmap_npz/{bodypart}_{center_mode}/{animal}/{date}.npz    (fine-grid arrays, per Item 6.4)
    ├── centered_parquets/{center_mode}/{animal}/*.parquet
    └── trajectories/ (future Phase 7)
    ```
    Analogous figure-type-first organization within `spout_behavior/` as Phase 8a adds recovery-curve outputs there.
  - **Add SVG alongside PNG for new outputs going forward.** Do NOT retroactively re-execute pipelines to produce SVG siblings for existing PNGs. When a specific figure is needed for publication, re-run just that notebook cell selectively.
  - **SVG infrastructure is a Phase 5.5 polish concern** (task #16): add `save_figure(fig, path_no_ext, formats=("png", "svg"), dpi=200, rasterize_images=True)` unified helper; refactor existing `save_heatmap_png` + inline `savefig` callsites; heavy pixel content (heatmaps) uses `rasterized=True` to keep SVG file sizes manageable while leaving axes/annotations vector-editable.
  - **Directory reorganization is a standalone mini-phase** ("Phase 6.75 — Output reorganization"), sequenced between Phase 6.7 (SessionManifest refactor, byte-parity required at old paths) and Phase 6.8 (full heatmap/binned/Δ × session/reward-aligned matrix). Writes `git mv` migration script to move existing outputs in place, evolves `PathResolver` API (adds `figures_dir(kind)` / `intermediates_dir(kind)` semantic helpers while keeping the `pipeline_outputs(subdir)` fallback), updates ~5 notebooks, updates MIGRATION_LOG.
- *Rationale:* Priya prefers the data-collection-type top-level split because `spout_behavior` and `dlc_analysis` come from genuinely different instruments / workflows — collapsing them into a single tree would obscure that boundary and complicate Phase 8a's DLC-independent workflow. Figure-type-first sub-structure gives publication-assembly the walkability advantage of the `figures/` split without losing the instrument boundary. Sequencing reorg between 6.7 and 6.8 preserves 6.7's byte-parity requirements and lets 6.8 land at final paths. Not regenerating SVGs retroactively avoids a multi-hour re-execution of Phase 4–6 pipelines on the full cohort for a speculative future publication need.
- *Enforced at:* Task #16 (Phase 5.5 polish) extended to include the `save_figure` helper + SVG addition. New task #17 (Phase 6.75 output reorganization) with dependency chain `#9 (Phase 6.7) → #17 → #14 (Phase 6.8)`. Legacy `pipeline_outputs(subdir)` API remains during and after transition as a deprecated fallback.

## 2026-04-19 — Audit Item 8 (DLC inference / SSH workflow) — current design sound, five polish items batched

- *Context:* Audit Item 8 reviewed `src/stroke_orofacial/dlc_inference_o2/` (runner, batch, o2_job, transfer + README), `notebooks/20_dlc_inference.ipynb`, and `tests/test_dlc_inference.py`. The core architectural decision (Python generates shell-command strings; user pastes into terminal; never SSH from Python; never handle passwords) is already captured in the 2026-04-18 DECISIONS entry and is the right approach given HMS O2's DUO 2FA requirement.
- *Decision:* No architectural changes. Five polish items (8.1–8.5) batched into a new "Phase 5.5 polish" mini-PR (task #16) — all README / notebook / small-helper additions, no behavior change. Item 8.6 (split `configs/defaults.yaml` infrastructure section from analysis section) rolls into task #13 (env unification). No new task dependencies.
- *Rationale:* The command-generation-not-execution pattern works as-is; the polish items are all UX improvements (status helper, recovery docs, SSH setup walkthrough, ControlMaster tip, auto-rename on copy) rather than correctness fixes. Bundling them as one polish PR avoids creating 5 micro-tasks.
- *Enforced at:* Task #16 polish PR, when executed. No code or docs change from this decision itself — just the task queue entry.

## 2026-04-19 — Audit Item 7 (Phase 6 reward-aligned DLC) — seven findings, resolution distributed

- *Context:* Mid-consolidation audit Item 7 reviewed the Phase 6 reward-aligned DLC implementation (`src/stroke_orofacial/dlc_spatial/reward_aligned.py`, `configs/defaults.yaml` `dlc_spatial_reward_aligned` block, `notebooks/12_dlc_spatial_reward_aligned.ipynb`, `tests/test_reward_aligned.py`, MIGRATION_LOG Phase 6 entry). Seven sub-items identified across correctness / integration / consistency / polish.
- *Decision:* Distribute resolution across existing and new work items rather than creating one mega-phase:
  - **Into Phase 6.7 (SessionManifest refactor, task #9):** 7.1 (notebook 12 to honor Phase 4.5-lite per-bodypart `center_mode` defaults once that lands); 7.3 (centering likelihood threshold pulled from Phase 4 config, not hardcoded; session-date enumeration from SessionManifest rather than naive day-range); 7.4 (refactor notebook 12 to use `plot_heatmap` from `heatmaps.py` + add `DISPLAY_INLINE` toggle to USER INPUTS for quick in-notebook visual inspection during development); 7.5 (save fine-grid histogram NPZ alongside PNG for Phase 6 outputs, extending the same pattern from Item 6.4 already planned in 6.7d).
  - **New Phase 6.8 (task #14):** 7.2 — port legacy cells 18 (reward-aligned binned heatmaps) and 20 (reward-aligned Δ heatmaps) from `20260323` to complete the full analytical matrix {whole-session, reward-aligned} × {heatmap, binned, difference-map}. The matrix is what Priya wants scientifically; most primitives already exist (Phase 5's `pixel_bins` and `difference_maps`, Phase 6's `window_selector`), so the port is largely verification + wiring + notebook orchestration. Sequenced after 6.7 so SessionManifest is in place.
  - **New dedicated task (task #15):** unified 7.6 + 7.7 — implement the currently-placeholder `share_xy_within_mouse` config flag as a real feature (axis limits shared across all sessions for one (animal, bodypart, center_mode) combination so heatmaps are visually comparable across days), add per-(regime, center_mode) axis-limit blocks for reward-aligned (Phase 6 currently reuses Phase 5's whole-session limits — may crop peri-reward distributions), add percentile-based auto-scale fallback (e.g., 2nd–98th of pooled per-animal data). Sequenced after 6.8 so the axis infrastructure has the full matrix of outputs to apply to. Also serves Phase 9's need for consistent comparative axes across pre-vs-post.
  - **Deferred** (tracked elsewhere): Phase 6 output directory reorg → Item 9; cohort extension beyond PS46 → task #11 (Phase 7); SessionManifest integration → Phase 6.7; integration-test path hardcoding (Mac-only) → testing-cleanup mini-phase, low urgency; parity-status progression tracking (sanity-check-only → visually-verified → array-parity) → Phase 10.
- *Rationale:* Phase 6.7 stays a pure refactor in spirit but absorbs the small Phase 6 improvements that are architecturally coupled to its changes. A separate Phase 6.8 keeps the (larger) port-plus-matrix-completion work as its own mini-phase with its own scope and tests. Axis-sharing is an infrastructure concern that benefits both Phase 5 and 6, so it's a standalone task. This structure maps cleanly onto what's actually coupled to what in the code, without bloating any single phase.
- *Enforced at:* Phase 6.7 kickoff (`docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`) will be amended to include 7.1/7.3/7.4/7.5 when that phase starts. New Phase 6.8 kickoff to be authored when that phase starts. Task #15 — axis-sharing — has no kickoff yet (will get one when scheduled). Legacy cells 18 and 20 are now formally Phase 6.8 scope, not Phase 6 scope — MIGRATION_LOG Phase 6 entry's "reclassified to Production" statement about those cells is superseded by this decision.

## 2026-04-19 — Phase 4.5-lite decision: eye-midpoint centering, no similarity/rigid transform

- *Context:* `notebooks/experiments/cross_session_alignment_sweep.ipynb` tested four alignment regimes (`eye_affine` similarity transform, `eye_rigid` rotation+translation, `eye_centered` translation-only to eye midpoint, `spout_centered` translation-only to spout midpoint) across 8 animals × 13 bodyparts (9 movement bodyparts + 4 fiducials as sanity checks) × all session dates in each animal's recording range. Each (animal, bodypart, regime) was scored by mean pairwise Pearson r and mean pairwise Jensen-Shannon divergence of normalized 2D histograms across all session pairs.
- *Decision:* Build **Phase 4.5-lite**: add `eye_midpoint` as a supported `center_mode` in `src/stroke_orofacial/dlc_io/centering.py` and set per-bodypart defaults in `configs/defaults.yaml` — `tongue` stays on `spout_midpoint` (unchanged), `jaw` / `nose` / all 6 whiskers switch to `eye_midpoint`. **Do NOT implement `eye_affine` (similarity) or `eye_rigid` (rotation-only) transforms in production.** The observation originally captured as "Phase 4.5 proposed, pending experimental validation" (2026-04-18) is closed with this entry.
- *Rationale:*
  - *Cohort-wide result:* `eye_centered` wins 8 of 9 movement bodyparts on both Pearson r and JS divergence. Only `tongue` preferred `spout_centered` — which makes anatomical sense, since the tongue's spatial distribution is defined relative to the spouts. `eye_affine` consistently underperformed `eye_centered` for every movement bodypart.
  - *Why the similarity transform loses:* with 4 free parameters exactly fit to 4 constraints (the two eye-fiducial coordinates), per-session noise in the eye medians passes straight through into scale / θ / tx / ty and is amplified *proportionally* into every bodypart's warped coordinates — disproportionately bodyparts far from the rotation center (whiskers at 100–200 px get 2–8 px of spurious warping per session from ~5 px of per-session eye-median noise). Eye-centered has no such amplification: per-session noise adds once to the translation and scales linearly with distance, not proportionally.
  - *Why rigid also loses / ties:* with 3 free parameters and 4 constraints, rigid is overdetermined and has 1 residual DoF, which allows some noise averaging. But for 2 fiducials separated by ~257 px with ~5 px each of noise, the rotation estimate has ~1.1° noise, which at r = 150 px adds ~2.9 px of spurious warping — comparable to the real rotation signal (typical rotation std 0.2–0.6°, i.e., 0.5–1.6 px of real drift at the same radius). *Observed cohort-wide result (8 animals × 9 movement bodyparts):* `eye_rigid` scores below `eye_centered` on 8 of 9 bodyparts. Cohort-mean-of-means Pearson r: `eye_centered` = 0.669, `eye_rigid` = 0.647, `eye_affine` = 0.607, `spout_centered` = 0.542 (dragged down by poor performance on whiskers, which it's not anchored to). `eye_rigid` lies consistently between `eye_affine` (worst) and `eye_centered` (best) but closer to `eye_centered` — confirming that the noise-amplification effect is real but ~2× milder for rigid (3 params) than for affine (4 params), yet still not worth the added code complexity.
  - *Fiducial sanity checks (confirmed on 4 bodyparts × 4 regimes × 8 animals):*
    - `L_eye` / `R_eye` under `eye_affine` — cohort-mean Pearson 0.89 / 0.83, JS ≈ 0.10–0.15 bits. Near-zero residual as required by the exact 2-point fit; small nonzero residual is numerical precision of the chained transform steps. Confirms sweep implementation is correct.
    - `L_eye` / `R_eye` under `eye_rigid` — cohort-mean Pearson ~0.51 / 0.46, JS ~0.43–0.47 bits. Residual is the eye-separation variance across sessions (rigid can't rescale).
    - `L_eye` / `R_eye` under `eye_centered` — cohort-mean Pearson ~0.44 / 0.40, JS ~0.48–0.53 bits. Residual is full individual-eye variability; only the midpoint is aligned.
    - `L_spout` / `R_spout` under `spout_centered` — cohort-mean Pearson ~0.64 / 0.62, JS ~0.32–0.34 bits. Spouts are physical hardware and more stable across sessions than eye fiducials (which depend on DLC detection + head pose); spout-centered residuals are correspondingly smaller than eye-centered residuals for their own fiducials.
    - Under mismatched regimes (eyes under spout_centered, spouts under eye_centered): pairwise Pearson r collapses to ~0.05–0.10 — fiducials drift nearly independently relative to each other across sessions, confirming eye-rig and spout-rig are effectively independent reference frames.
  - *Null-baseline thresholds for Phase 9 significance testing:* under each centering regime, the fiducial bodypart's cross-session pairwise Pearson r sets a "this could still be noise" lower bound. Eye-centered analyses: ~0.44 (eye-fiducial floor). Spout-centered analyses: ~0.64 (spout-fiducial floor). Any movement bodypart showing pairwise Pearson meaningfully above its regime's fiducial floor is above the null and safe to compare statistically; anything at or below is indistinguishable from fiducial noise.
  - *Observed but not-correctable drift:* PS54 shows a systematic ~6% scale decrease over 60 post-stroke days. No centering regime corrects this (eye_affine's similarity overfits to noise; rigid can't rescale; translation-only modes don't address scale). Flagged as Phase 10 limitation — long-range pre-to-post spatial comparisons on that animal should account for a few-pixel systematic shift in apparent bodypart positions.
- *Enforced at:* `src/stroke_orofacial/dlc_io/centering.py` (new `eye_midpoint` branch), `configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.center_mode` (per-bodypart defaults), `tests/test_dlc_centering.py` (new test), and the sweep notebook + outputs preserved under `notebooks/experiments/outputs/alignment_sweep/` as the experimental record. Full Phase 4.5-lite execution plan at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`.

## 2026-04-18 — Phase 6 establishes window_selector abstraction for all future event-aligned analyses

- *Context:* Reward-aligned spatial analyses (Phase 6) are the first event-aligned work in the pipeline. The abstraction needs to be general enough for future event types (cue-aligned via tone events from Phase 2.5, custom event windows for Phase 7 kinematics) without requiring infrastructure changes.
- *Decision:* `WindowSelector` abstract base class in `dlc_spatial/window_selector.py` with `select_frames(df) -> bool_mask`. Concrete implementations: `WholeSessionWindow` (Phase 5, all frames), `EventAlignedWindow` (generic, any event array + pre/post window with deduplication), `RewardAlignedWindow` (reward events from WS samples → camera frames via alignment). Future phases add `CueAlignedWindow` (tone events from Phase 2.5) or custom selectors. All Phase 5 spatial functions (`build_histogram`, `build_stats_grid`, `plot_heatmap`) accept an optional `window` parameter; `None` default preserves whole-session behavior.
- *Rationale:* Clean separation between window selection (which frames to include) and spatial analysis (what to compute on those frames). Future phases extend by adding new `WindowSelector` subclasses, not by modifying existing analysis functions.
- *Enforced at:* `src/stroke_orofacial/dlc_spatial/window_selector.py`, Phase 5 spatial functions' `window` parameter.

## 2026-04-18 — DLC inference notebook generates SSH/rsync/sbatch commands but never executes them

- *Context:* Phase 5.5's inference workflow requires SSH to O2 and rsync of large video/output files. Executing these from the notebook would require password/credential handling inside the automation layer.
- *Decision:* Local actions (YAML generation, script writing, post-copy file rename) execute directly in the notebook. SSH/rsync/sbatch commands are generated as strings with user-specific inputs substituted and printed for the user to paste into their own Terminal. No SSH connection is made from within the notebook or any Python module.
- *Rationale:* Keeps secrets out of the automation layer entirely. User retains manual control over when SSH connections are made. Matches the password-handling rules in DECISIONS.md "DLC inference port scheduled as dedicated mini-phase."
- *Enforced at:* `notebooks/20_dlc_inference.ipynb`, `src/stroke_orofacial/dlc_inference_o2/transfer.py`.

## 2026-04-18 — Plot axis limits must be per-(bodypart, center_mode)

- *Context:* Phase 5 parity check revealed the legacy `y_limits=(50, 550)` were for un-centered pixel coordinates. Nose-centered data needs `y_limits=(-120, 130)`. The legacy code implicitly assumed un-centered input. Using legacy limits on centered data produced empty heatmaps (0 counts in the visible range).
- *Decision:* The `dlc_spatial` config in `configs/defaults.yaml` uses per-(bodypart, center_mode) axis limits under `bodyparts.{bp}.per_center_mode.{mode}.{xlim,ylim}`. For each combination, explicit limits are set rather than inheriting a single default. Limits set to `null` for untested combinations will be filled in when Phase 6+ exercises those paths.
- *Rationale:* Centered-data plots need different axis ranges than un-centered-data plots; conflating them produces cropped or mis-scaled figures. First real surfacing of the DECISIONS.md "Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters" prediction.
- *Enforced at:* `configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}`.

## 2026-04-18 — Phase 5 defers permutation/inferential spatial stats to Phase 9

- *Context:* The `20251202_all_bodyparts_stats_pixelbin` notebook (cells 8-10) computes permutation nulls and per-day occupancy significance. The `20251201_2KSD_spatial-maps` notebook computes 2D-KS-distance and energy distance with significance tests. Both produce inferential results (p-values).
- *Decision:* Phase 5 produces descriptive spatial maps only (histograms, heatmaps, difference maps, baseline aggregates). All inferential statistics on spatial maps — permutation p-values, KS/energy distance, any other significance testing — are deferred to Phase 9. This includes the 2KSD notebook's visualization, which is tightly coupled to its stats computation.
- *Rationale:* Keeps Phase 5 boundary clean at descriptive analyses. Phase 9 becomes the single home for all inferential spatial-maps stats.
- *Enforced at:* Phase 5 plan (cells 8-10 of `20251202` classified "Deferred to Phase 9"); `docs/MIGRATION_LOG.md` Phase 5 entry.

## 2026-04-18 — Phase 5 fine-grid heatmap arrays saved alongside PNGs

- *Context:* Phase 5 currently saves the coarse stats grid (`stats_grid_{date}.npz`) for occupancy statistics and saves the fine heatmap visualization as `heatmap_{date}.png` only. The fine 100-bin histogram array is computed during rendering but then discarded.
- *Decision:* Save the fine-grid heatmap histogram array as `heatmap_{date}.npz` alongside the PNG. Keys: `H_counts`, `H_proportion`, `xedges`, `yedges`, `x_limits`, `y_limits`, `nbins`. Rolled into Phase 6.7's sub-phase 6.7d scope.
- *Rationale:* (a) Future figure generation may want to tweak colormap, axis limits, or normalization without recomputing from parquet. (b) Phase 9 fine-resolution spatial stats (KS distance, energy distance) may need the fine grid as input. Saving now avoids repeat computation.
- *Enforced at:* `src/stroke_orofacial/dlc_spatial/heatmaps.py` (new save helper), updated in sub-phase 6.7d per `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`.

## 2026-04-18 — Phase 5 all-bodyparts overlay heatmap design

- *Context:* Priya wants a single-figure overlay of all bodypart heatmaps (each with its own colormap) for cross-bodypart comparison. L and R paired bodyparts (e.g., L_whiskers_1 + R_whiskers_1) share colormaps. Legacy 20251202 notebook implements this in the `_all_bodyparts_` cells.
- *Decision:* Add `plot_all_bodyparts_heatmap(df, config, include_landmarks=False)` to `dlc_spatial/heatmaps.py` as a future Phase 5.x mini-phase (not part of 6.7 refactor). Renders tongue, jaw, nose, and whiskers on one axis with per-bodypart colormaps; L/R pairs share cmaps. `include_landmarks=True` optionally adds medial_edge_L_eye, medial_edge_R_eye, L_spout, R_spout for QC / alignment verification. Default behavior excludes landmarks. Output: `spatial_whole_session/all_bodyparts_{center_mode}/{animal}/heatmap_{date}.png` + `heatmap_{date}.npz` (per-bodypart arrays stacked).
- *Rationale:* Single-figure overlays are the legacy standard for across-bodypart comparison; faithful port + the fine-grid save requirement make this a natural Phase 5.x mini-phase after audit closes.
- *Enforced at:* Future `docs/prompts/phase-5.x-all-bodyparts-heatmap-kickoff.md` (to be written when scheduling that mini-phase).

## 2026-04-18 — Phase 4.5 (eye-based affine cross-session alignment) proposed, pending experimental validation

- *Context:* Current pipeline aligns sessions via midpoint centering (nose, spout midpoint, eye midpoint), which handles translation but not rotation, scale drift, or lateral/vertical camera displacement across sessions. Cross-session difference maps may show false "changes" from camera drift rather than biology. Priya specifically requested NOT to use nose as a fiducial (resting nose location may shift post-stroke). L and R medial eye edges are stable post-stroke and work as fiducials.
- *Decision:* Run an experimental notebook first (`notebooks/experiments/eye_affine_alignment_exploration.ipynb`) on PS46 baseline sessions to compare midpoint-centering vs eye-based similarity transform (translation + rotation + scale, two-fiducial). If the experiment shows meaningful reduction in cross-session landmark variance AND cleaner difference maps, implement as `Phase 4.5 — Optional Affine Cross-Session Alignment` mini-phase. Canonical reference frame: baseline-averaged median eye positions per animal. Store per-session 4-parameter transform as JSON; Phase 5/6 analyses optionally apply the transform before histogramming.
- *Rationale:* Session-to-session spatial comparability matters for cross-day analyses; affine alignment is a principled way to remove camera-mount drift. Excluding nose as a fiducial preserves the ability to detect post-stroke nose-position changes as biology, not artifact. Starting with an experimental notebook avoids building infrastructure before validating the hypothesis.
- *Enforced at:* `notebooks/experiments/eye_affine_alignment_exploration.ipynb` (this commit); `docs/prompts/phase-4.5-affine-alignment-kickoff.md` to be written after experimental validation.

## 2026-04-18 — Phase 8 split into 8a (spout behavior) + 8b (DLC behavior), with 8a moved ahead of Phase 7

- *Context:* Mid-experiment, Priya needs spout-behavior figures (first-lick accuracy, latencies, lick rates over sessions) to decide when behavior has plateaued and stroke induction is appropriate. These decisions depend only on wavesurfer data, not on DLC kinematics or spatial maps. The original Phase 8 ("Behavior report") was a single phase scheduled after Phase 7 (DLC kinematics), which would block mid-experiment figures until DLC work unrelated to the decision is complete.
- *Decision:* Split Phase 8 into two phases along the DLC-dependency line. **Phase 8a** (spout behavior report) consumes only Phase 2 + 2.5 outputs and is moved ahead of Phase 7 in the build sequence so spout-behavior figures are available immediately after the data pipeline completes. **Phase 8b** (DLC behavior report) consumes Phases 4-7 outputs plus 8a, and runs after Phase 7. Output directories split: `behavior_report/spout/` and `behavior_report/dlc/`.
- *Rationale:* Scientific work happens in parallel with consolidation; waiting on DLC-derived figures to get spout-derived figures blocks experimental decisions. Splitting by data-dependency makes the graph explicit and unblocks mid-experiment usage. The split also means 8a can be re-run cheaply after any new data-collection session (it's just wavesurfer → figures, no heavy video processing).
- *Enforced at:* `docs/DESIGN.md` §7 Phase 8a and Phase 8b entries; `stroke_orofacial_pipeline_outputs/behavior_report/{spout,dlc}/` subdirs; future Phase 8a and Phase 8b kickoff prompts in `docs/prompts/`.

## 2026-04-18 — End-to-end output audits scheduled at two points

- *Context:* Priya will want to walk through every analysis output and figure produced by the consolidated pipeline for one animal (PS46 as the exemplar), to identify gaps against her scientific needs, excesses, and desired edits. The DESIGN.md Phase 10 ("Cleanup & docs") as originally written is technical-cleanup-only and doesn't cover a scientific end-to-end walkthrough.
- *Decision:* Two audits, not one:
  - **Mid-consolidation audit** scheduled for right after Phase 6 merges. Covers Phases 2–6 + 5.5 outputs (spout behavior, alignment, DLC I/O, whole-session spatial, reward-aligned spatial, DLC inference). Done in Cowork, not Claude Code — requires back-and-forth review, not code edits. Outcomes feed into the kickoff prompts for Phases 7, 8, 9 so any gaps surfaced get designed into those phases rather than discovered post-hoc.
  - **Full end-to-end audit at Phase 10.** All phases built; every output and figure for PS46 enumerated and reviewed. Gaps become either pre-v0.1.0 fixes or post-v0.1.0 backlog items.
- *Rationale:* Technical cleanup (Phase 10 as originally written) doesn't verify scientific completeness. An explicit walkthrough against research needs catches missing analyses or outputs that code-level review wouldn't surface. Doing one audit mid-consolidation also means later phases are shaped by knowledge of the full current output space, not assumptions.
- *Enforced at:* `docs/DESIGN.md` §7 Phase 10 (to be updated to reflect this broader scope); mid-consolidation audit invoked directly in Cowork after Phase 6 closeout.

## 2026-04-18 — Legacy notebooks may receive active edits; re-read at each phase kickoff

- *Context:* Priya is actively working on some legacy notebooks (notably `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` for tongue kinematic and statistical analyses) in parallel with consolidation. These edits continue during the migration, meaning the "canonical" content of a notebook at Phase N kickoff may differ from its content at a later phase's kickoff.
- *Decision:* At each phase kickoff, Claude Code must re-read the current version of every legacy notebook or helper it will port or reference. Do not rely on cached findings from earlier phases. If a notebook that has already been ported (Phases 2, 2.5, 3, 4, 5, 5.5) receives a substantive update with new production code, address it via one of: (a) a Phase 10 cleanup task documented in MIGRATION_LOG, (b) a dedicated mini-phase patterned after Phase 2.5 or 5.5, or (c) a targeted follow-up PR against the affected module. MIGRATION_LOG phase entries should capture a legacy-file fingerprint (mtime or line-count) per ported source so drift can be detected in future phases.
- *Rationale:* Priya's ongoing scientific iteration shouldn't silently diverge from the consolidated pipeline. Capturing updates as they emerge keeps the new codebase current. This applies especially to tongue/jaw kinematics notebooks (Phase 7), behavior-report files (Phase 8), and stats code (Phase 9) — all under active scientific refinement.
- *Enforced at:* Every future phase kickoff prompt in `docs/prompts/phase-*-kickoff.md` includes an explicit "re-read current legacy file" instruction. Phase 7 kickoff specifically flags `20260203_..._tongue.ipynb` as actively-edited as of 2026-04-18.

## 2026-04-18 — DLC inference port scheduled as dedicated mini-phase

- *Context:* `20251112_DLC_batch_video_analysis_O2.ipynb` runs DLC inference on the HMS O2 GPU cluster and copies outputs to MICROSCOPE. The design doc §3 already anticipates this lives in `src/stroke_orofacial/dlc_inference_o2/` as a standalone tool, but §7 didn't include an explicit phase for porting it. Priya wants it ported and cleaned up.
- *Decision:* Add a dedicated DLC-inference port as a mini-phase after Phase 5 and before Phase 6. Scope: port the canonical notebook into `src/stroke_orofacial/dlc_inference_o2/`, apply the full Phase plan requirements (disambiguation + dead code + hardcoded constants), write a README documenting the O2 workflow. Parity verification optional — if a small test video + O2 rerun is feasible, do it; otherwise rely on code review + functional test on a short clip.
- *Rationale:* DLC inference is infrastructure that doesn't block the analysis-pipeline phases (existing DLC outputs on MICROSCOPE are what Phases 4-7 consume). Porting it as a discrete mini-phase avoids interrupting the analysis-phase momentum. Placing it between Phase 5 and Phase 6 means the consolidated repo contains the inference tool before reward-aligned spatial analyses are added.
- *Password/SSH handling:* Strongly recommend SSH key auth to O2 (one-time setup via `ssh-keygen` + `ssh-copy-id`). If not set up, use interactive password entry per SSH command — password goes to stdin, not Claude Code's context. Never pass passwords via `sshpass -p`, environment variables, or any persistent store. Claude Code does not persist secrets across sessions.
- *Enforced at:* Future `docs/prompts/phase-5.5-dlc-inference-kickoff.md` (to be written after Phase 5 completes); design doc §7 to be updated with the new phase.

## 2026-04-18 — Keypoint-MoSeq deferred past v1 consolidation

- *Context:* `20260209_keypoint_moseq_parquet.ipynb` and `20260209_keypoint_moseq.ipynb` implement unsupervised pose-sequence segmentation using keypoint-MoSeq. This is a different analysis paradigm from the spatial/kinematic work in the current phases and was not included in the original design doc §7.
- *Decision:* Deferred past v1 consolidation. Treat similarly to FaceRhythm — scaffold a sibling module only if/when we get to it. Not out-of-scope forever; just not scheduled into v1.
- *Rationale:* V1 consolidation is already substantial. Adding keypoint-MoSeq would expand scope without clear blocking dependency. Can be added as a new phase when Priya has bandwidth to integrate.
- *Enforced at:* `docs/DECISIONS.md` "Deferred to later phases" section.

---

## 2026-04-18 — Disambiguation rule refined: siblings vs duplicates

- *Context:* The original CLAUDE.md rule 1 said "latest YYYYMMDD wins" without distinguishing between dated versions of the same file (true supersession) and files with distinct scope markers like `_tongue` vs `_jaw` (siblings that both need porting). Phase 4 planning surfaced the risk that `20260203_..._tongue.ipynb` and `20260416_..._jaw.ipynb` could be silently treated as old+new of the same thing, losing the tongue notebook entirely.
- *Decision:* Refine rule 1 — date-based supersession applies only within a family of files doing the same thing. Files with distinct scope markers (bodypart name, analysis type, phase tag) are siblings; each may need independent porting. When in doubt, trigger rule 3 (STOP-and-ask).
- *Rationale:* Prevents silently dropping sibling files with unique capabilities that happen to have older dates.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" rule 1.

## 2026-04-18 — Phase 4 orchestrator: iterate over animals without notebook restart

- *Context:* The legacy DLC parquet-building notebook accumulated state (loaded parquets in memory, globals) so moving to the next animal required clearing + restarting the notebook. Priya wants the new pipeline to loop over animals and dates cleanly.
- *Decision:* Phase 4's orchestrator exposes a pure function `build_centered_parquet(animal, date, center_mode, resolver) -> Path` callable in a loop without accumulating module-level state. The notebook orchestrates via an animal × date × center_mode loop. All three center modes (NOSE, SPOUT_MIDPOINT, EYE_MIDPOINT) are built by default; USER INPUTS cell can restrict to a subset. Matches the Phase 2 `process_animal()` pattern.
- *Rationale:* Removes a major friction point from downstream analyses; makes cohort-wide processing a single notebook run.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` orchestrator (Phase 4c), `notebooks/10_dlc_build_parquets.ipynb`.

## 2026-04-18 — Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters

- *Context:* Plotting parameters for heatmaps, proportion-difference maps, unbalanced-OT maps and related analyses (axis scales, filter ranges, baseline values) vary by both bodypart and centering mode in the legacy notebooks. Priya's usage: spout-midpoint centering for tongue analyses; eye-midpoint for jaw and whisker analyses; nose-centering for other uses.
- *Decision:* When Phase 5+ phases port downstream analyses, per-(bodypart, center_mode) plotting parameters must be extracted from the legacy notebooks into `configs/defaults.yaml` (or an analysis-specific config) rather than coalesced into a single default set. Each analysis function accepts `bodypart` and `center_mode` and looks up the appropriate parameters.
- *Rationale:* Silently averaging or picking one bodypart's parameters would produce wrong plots (e.g., tongue-appropriate axis limits applied to jaw analyses would clip or stretch).
- *Enforced at:* Phase 5+ plan requirements, to be captured in each downstream-analysis phase's kickoff prompt.

## 2026-04-18 — Phase 4 decision: keep all frames (no 975K cap)

- *Context:* The old tongue-only parquet-building notebook (`20260111_DLC_analysis_build-parquet_tongue.ipynb`) filtered DLC outputs to the first 975,000 frames. The newer notebook (`20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`) keeps all frames.
- *Decision:* Phase 4 ports from 20260323. The new pipeline keeps all frames in the output parquet (output row count = source DLC frame count). Phase 4d parity check includes an assertion that the new parquet's row count equals the source frame count AND matches the legacy parquet's row count (to catch hidden caps).
- *Rationale:* The 975K cap was a limitation of the older notebook, not a desired behavior. Keeping all frames is necessary for any analysis that spans the full session.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` Phase 4 implementation; `tests/test_dlc_parquet.py` parity check; MIGRATION_LOG Phase 4 entry.

---

## 2026-04-18 — Phase plan requirements: dead code identification step

- *Context:* Porting legacy notebooks risks carrying over exploratory/debugging cells, deprecated code branches, and commented-out historical artifacts. Without explicit classification, dead code silently enters the consolidated repo.
- *Decision:* Every phase plan must include a dead-code identification step. Each cell (notebook) or function/block (.py) in the legacy source is classified as *Production*, *Exploratory*, *Deprecated*, or *Ambiguous*. Only *Production* items get ported. *Exploratory*/*Deprecated* are listed as non-ports. *Ambiguous* triggers STOP-and-ask.
- *Rationale:* Prevents scope creep and ensures Priya can review the classification before any code is written. Applies from Phase 4 onward (Phases 2-3 predated this requirement).
- *Enforced at:* `CLAUDE.md` "Phase plan requirements" section.

## 2026-04-18 — Phase 3 parity tolerance: rtol=1e-8 for affine fit

- *Context:* Alignment template parity checking compares re-computed templates against existing `alignment_templates/` NPZs. The edge-sequence pattern matcher uses a sliding-window L-p norm that can break ties differently depending on floating-point evaluation order, potentially producing slightly different matched-edge sets.
- *Decision:* Interpolated float arrays (`sig_camIdx__idx_ws`, `sig_wsIdx__idx_cam`) use `rtol=1e-10`. Affine fit scalars (`slope_ws_per_camFrame`, `intercept_ws_samples`) use `rtol=1e-8` to absorb minor tie-break variations. Integer edge arrays (`idxCam_edges`, `idxWS_edges`) are not compared directly (they're input to the fit, not output). Any mismatch on `matched_camEdge_i`/`matched_wsEdge_i` must be investigated and documented, not silently accepted.
- *Rationale:* Avoids false parity failures from tie-break non-determinism while still catching real algorithmic bugs.
- *Enforced at:* `tests/test_timebase.py`, `docs/MIGRATION_LOG.md` Phase 3 entry.

## 2026-04-18 — Branch-protection pre-commit hook installed

- *Context:* During Phase 2.5 execution, a batch of commits accidentally landed directly on `main` instead of the intended feature branch. The error was caught but required a manual fix (Priya created the branch retroactively and reset `main`).
- *Decision:* `.githooks/pre-commit` refuses commits on `main`/`master`. `scripts/setup-hooks.sh` activates via `git config core.hooksPath .githooks`. Enforced at `CLAUDE.md` rule 8 ("before every `git commit`, run `git branch --show-current` and confirm you are NOT on `main`").
- *Rationale:* Layer 1 (GitHub branch protection) is unavailable on private-free-tier accounts. Layers 2 (local pre-commit hook) and 3 (CLAUDE.md instruction to Claude Code) are the active defense. Belt-and-suspenders: Claude Code checks the branch before committing, and the hook blocks it if the check is missed.
- *Enforced at:* `.githooks/pre-commit`, `scripts/setup-hooks.sh`, `CLAUDE.md` rule 8.

## 2026-04-18 — Workflow: phase kickoff prompts as files; running decisions log

- *Context:* Copy-pasting long multi-paragraph kickoff prompts from Cowork into Claude Code is friction. No product-level integration exists between the two.
- *Decision:* For each phase or sub-phase, Cowork writes the full kickoff prompt to `docs/prompts/phase-N-*.md`. Priya pastes a one-liner to Claude Code ("Read `docs/prompts/<file>` and follow the instructions."). Prompts are committed to git as a permanent audit trail of what Claude Code was instructed to do. Cross-cutting decisions recorded here in `DECISIONS.md`.
- *Rationale:* Reduces pasting, creates a reproducible record, keeps `MIGRATION_LOG.md` focused on per-phase implementation.
- *Enforced at:* `docs/prompts/README.md`, `docs/DECISIONS.md` (this file).

## 2026-04-18 — Tone events + per-side peri-periods restored (Phase 2.5)

- *Context:* Phase 2 ported from Priya's fork of the legacy repo, which had dropped tone detection (Tone_L / Tone_R rising edges) and per-side peri-reward masks that exist in Rich's upstream repo. Phase 4+ cue-aligned analyses require tone timing.
- *Decision:* Add Phase 2.5 as a strictly additive gap-fill. Extend `lick_detection.py` to detect tones; extend `bouts.py` with per-side peri-reward and peri-tone masks. New keys added to existing NPZ outputs; no existing key changes value.
- *Rationale:* Proper tone capture is more robust than post-hoc L/R inference from reward side (which breaks on omitted trials, licking errors, and tone-reward delay).
- *Enforced at:* `src/stroke_orofacial/spout_behavior/lick_detection.py`, `bouts.py`, `configs/defaults.yaml`, `docs/MIGRATION_LOG.md` Phase 2.5 entry.

## 2026-04-18 — Both legacy repos are read-only references

- *Context:* Cross-repo diff revealed that some legacy helpers (e.g., `make_alignment_templates_20251216.py`) live only in Rich's upstream repo `facerhythm_stroke_biomarker_exp`, not in Priya's fork `facerhythm_stroke_biomarker_exp_Priya`. The original `CLAUDE.md` rule 2 only protected the Priya fork.
- *Decision:* Both legacy repos are read-only references. Neither may be modified.
- *Rationale:* Upstream helpers are genuinely needed for some phases (Phase 3 alignment, potentially later). Making read-only status explicit prevents any ambiguity.
- *Enforced at:* `CLAUDE.md` ground rule 2.

## 2026-04-17 — Per-session `params.json` with "always write" policy

- *Context:* Phase 2's initial design wrote one cohort-level `params.json` at output root, overwritten per session. This lost per-session params provenance and didn't record skip decisions.
- *Decision:* Write one `params.json` per session at `{output_root}/params/{animal}/{YYYYMMDD}.json`. Include session_id, animal, date, run_timestamp, skipped flag, merged params used, processing_log. Write even when the session is skipped (records full audit trail).
- *Rationale:* Reproducibility — we want to always be able to reconstruct exactly what params were used for any session, and whether a given run processed or skipped it.
- *Enforced at:* `src/stroke_orofacial/spout_behavior/session_processing.py`, MIGRATION_LOG Phase 2d.

## 2026-04-17 — Overwrite protection default is "skip"

- *Context:* Re-running the pipeline over the full cohort risks silently overwriting hours of processed outputs if the user isn't careful.
- *Decision:* Three modes — `"skip"` (default; if output NPZ exists, skip and log), `"prompt"` (interactive per-file y/N/all/quit), `"force"` (explicit opt-in). Notebook default is `"skip"`.
- *Rationale:* Accidents cost hours of reprocessing. Opt-in to overwrite is the safer default.
- *Enforced at:* `process_session()` / `process_animal()` in `session_processing.py`.

## 2026-04-17 — Output location: MICROSCOPE, not Mac local

- *Context:* Legacy outputs lived at Mac-local `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/`. Priya works from both Mac and Windows workstations.
- *Decision:* New pipeline outputs go to `/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/` (Mac SMB mount) or the equivalent UNC path (Windows). Layout under the root: `spout_behavior/`, `alignment/`, `dlc_analysis/`, `stats/`. Legacy `session_processing3/` is read-only and untouched.
- *Rationale:* Single source of truth across both workstations. Server backup. No local duplicates to keep in sync.
- *Enforced at:* `configs/paths.yaml` (`microscope_pipeline_outputs` logical root), `PathResolver.pipeline_outputs()`.

## 2026-04-17 — Cross-platform `wavesurfer_raw` with fallback chain

- *Context:* Raw wavesurfer `.h5` files lived only on Priya's Mac local disk. Pipeline needed to run from Windows too.
- *Decision:* `paths.yaml` declares `wavesurfer_raw` as a list-mount on Mac — tries MICROSCOPE first, falls back to Mac-local. Single UNC path on Windows. `PathResolver.root()` supports list mounts by returning the first existing path. Wavesurfer raw data is mirrored to MICROSCOPE (one-time rsync 2026-04-18).
- *Rationale:* Cross-platform capability without forcing data duplication management on the user.
- *Enforced at:* `configs/paths.yaml`, `PathResolver.root()`.

## 2026-04-17 — `stroke_date` = last pre-stroke session date

- *Context:* Legacy notebooks use `stroke_date` to refer to the last pre-stroke session date; stroke is induced after that session. Early in Phase 1, the implementation treated `stroke_date` as the first post-stroke day, which would mis-classify every baseline session on that date.
- *Decision:* `stroke_date` is the date of the last pre-stroke session. `AnimalInfo.phase(session_date)` returns `"baseline"` for `session_date <= stroke_date`, `"post_stroke"` otherwise. `day_relative_to_stroke` = `(session_date - stroke_date).days` (day 0 = last baseline; day 1+ = post-stroke).
- *Rationale:* Matches legacy notebook semantics and Priya's lab-notebook convention. Avoids contaminating post-stroke analyses with baseline data from the stroke day.
- *Enforced at:* `src/stroke_orofacial/animals.py`, tests.

## 2026-04-17 — Exclusion semantics: `applies_to: [all]` for the current cohort

- *Context:* Legacy notebooks declared exclusions per-analysis (`[tongue]` in the tongue notebook, `[jaw]` in the jaw notebook). Priya reviewed the underlying reasons (Rose Bengal sham sessions, reward-delivery failures) and determined they invalidate all analyses, not just the one the exclusion was originally declared under.
- *Decision:* All existing exclusions in `animals.yaml` use `applies_to: [all]`. Schema supports per-analysis exclusions (`applies_to: [tongue]`, etc.) if a future exclusion is analysis-specific.
- *Rationale:* Reasons driving the current exclusions are universal.
- *Enforced at:* `configs/animals.yaml`, `AnimalInfo.is_excluded()`.

## 2026-04-17 — Legacy code version disambiguation (3-tier rule)

- *Context:* Legacy repos contain multiple dated copies of the same notebook and `_v0` / `_mod` suffixed helper files. Silent selection could anoint the wrong version.
- *Decision:* 3-tier rule — (1) Latest `YYYYMMDD` in filename wins; (2) if undated, pick the candidate whose output has the most recent mtime in downstream output dirs; (3) if still ambiguous, STOP and ask Priya.
- *Rationale:* Deterministic, auditable, refuses to guess.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" section.

## 2026-04-17 — Git discipline: feature branches preserved, tags per phase

- *Context:* Risk of losing work through `git branch -D`, `git reset --hard`, or force-push during an active multi-phase refactor.
- *Decision:* Every change on a feature branch off `main`. PR-merge to main. Never force-push. Never `branch -D`. After PR-merge, feature branches kept on origin as permanent references. Each phase gets a tag `vX.Y-phase-N-short-name` on its merge commit. Destructive git operations require explicit Priya approval each time.
- *Rationale:* Hours of work safe from a single bad command.
- *Enforced at:* `CLAUDE.md` ground rule 8.

## Deferred to later phases

The following decisions are **deliberately deferred** — recorded here so they don't get lost:

- **Recovery phenotype classification scheme** — §6.3 of `docs/DESIGN.md`. Will be a data-driven classification (rule-based, changepoint, HMM, or hybrid) to be chosen in Phase 9 after per-animal trajectories are visible across canonical endpoints.
- **Session-merge implementation** — PS48 2025-03-14 combines two wavesurfer files. Logged in `configs/session_overrides.yaml` under `merges:`; `check_merge_required()` raises `NotImplementedError` if encountered. Implementation deferred until a second merge-case arises or Priya needs to re-process PS48.
- **Wavesurfer QC figure generation** — legacy pipeline produced `wavesurfer_figures/` for visual QC. Deferred to Phase 8 (behavior report) which will build a unified figures layer.
- **FaceRhythm module** — scoped out of v1 consolidation entirely. Will be added in a later phase as a sibling module to `spout_behavior/`, `alignment/`, etc.
