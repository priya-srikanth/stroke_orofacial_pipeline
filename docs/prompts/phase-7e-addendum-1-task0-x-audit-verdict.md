# Phase 7e Kickoff Addendum #1 — Task 0 X-coordinate audit verdict + scope expansion

**Date:** 2026-05-25 evening (post PR #132 merge).
**Branch:** `phase/7e-dlc-tongue-preclean-v7` at HEAD `b5bf664` (= post-merge `origin/main`).
**Scope:** Locks Task 0 (X-coordinate audit) verdict + expands Phase 7e scope to a trace-level x pre-clean + an early-window M-gate relaxation. Both items were originally open in the kickoff and either fully or partially deferred. Both are now in-scope for the Phase 7e module port.

This addendum **supersedes** the kickoff "Open question — X-coordinate interpolation review" section's option enumeration and updates Decisions 1, 2, 3, 6 of the 2026-05-25 Phase 7e drafted section in `docs/DECISIONS.md`.

---

## Task 0 verdict: `x-audit-flag`

The audit script `.scratch_phase_7e/audit_x_imputation.py` ran on 89 trials (80 from `inv_p3b_cohort_validation` seed=20260525 + 9 canonical hard from `inv_p3a` SINGLES). Two `E_spline_impute` events fired total:

- PS51 26R: small y correction (121→126), Δx=0.00 px / Δangle=0.00° — no bias
- **PS54 46L** (canonical "E-impute case"): y outlier 211 → impute 121 correctly drops the y spike; production reports `peak_x = −13.79 px`; audit's outlier-excluded local PCHIP gives `x = +55.70 px` — **|Δx| = 69.49 px / |Δangle| = 7.75°**, far beyond Q4 thresholds (5 px / 2°)

This single material event is enough to lock the verdict. The DLC outlier corrupts both x and y simultaneously; v7 correctly drops the y spike but the reported `peak_x` carries the PCHIP-tainted x because Phase 7a.2's PCHIP anchored on the outlier.

**Visual review** (`.scratch_phase_7e/visualize_x_imputation.py` rendering `.scratch_phase_7e/x_imputation_figures/x_impute_canonical_*.png` for the 9 canonical hard trials in `part3a_policy_v7_unified_preclean/` style + new x-panel) surfaced four additional concerns that expanded the original "x_imputed field at E_spline_impute events only" fix shape into a broader trace-level x pre-clean:

1. **Raw DLC |x| outliers** beyond biological plausibility — initially observed at |x|>75 on PS47 33L lick peaks; threshold subsequently loosened to **|x|>110 px** per Priya visual review (real x values up to ~100 px observed during normal protrusion).
2. **PS54 25L wiped-cluster x convention** — when y-side pre-clean wipes a cluster to y=0, x at those frames should also snap to baseline x0 (symmetric with the y=0 convention). Without this rule the raw x value (often −95 at the artifact frame) leaks into the cleaned trace.
3. **PS54 51L first detected peak** — at the kept-lick peak frame, raw x = −2 sits inside a stable surrounding raw cluster at +30 to +50. The hard |x|>110 rule misses it (|−2|<110), the y-side pre-clean misses it (cluster shape passes Rule A), and the immediate-neighbor midpoint check misses it (neighbors are themselves PCHIP-fill). A joint x+y rule using nearest-raw-flanks with a direction-toward-x0 check catches it.
4. **PS54 76L first lick** — early-M relaxation needed: production M-gate (80 ms inter-lick interval) drops the first lick at ~280 ms when it's within 80 ms of a second peak. First-lick coordinates + angle are critical for downstream analyses; a relaxed M-gate of 60 ms inside the first 250 ms post-tone preserves the lick.

## Locked algorithmic refinements (5 rules + 1 M-gate change)

**Decision 6 (formerly "Lick angle uses imputed y; x-coordinate handling pending Phase 7e Task 0 audit") — RESOLVED.** Lick angle consumes the post-pre-clean x_final at `new_peak_frame` (no `x_imputed` field needed; trace-level cleaning is canonical).

### Rule 1 — x = x0 at all y-side baseline-fill frames

When `is_baseline_fill=True` (Phase 7a.2 stage-5 fill OR y-side pre-clean wipe), x is set to x0. x0 is derived per-session as `median(x_final[is_baseline_fill_orig])` (Phase 7a.2's stage-5 convention, typically 0.0 in spout-centered frame but session-specific).

Symmetric with the existing `y=0` baseline-fill convention. Catches PS54 25L: cluster at ~1230 ms with raw (y=210, x=−95) gets y-side wiped → without Rule 1 the raw x=−95 leaks into cleaned trace.

### Rule 2 — Drop y-wiped frames from x's PCHIP anchor set

When re-interpolating x at PCHIP-fill frames, exclude frames where the y-side pre-clean wiped the y. Mirrors the y-side handling of artifact-anchored interpolation segments. Catches PS54 46L: outlier at (y=211, x=−42) has |x|<110, so Rule 4 alone wouldn't flag the x at frame 140; but the y-side wipes that frame; Rule 2 drops it from the x anchor set; the surrounding raw x (+50 to +60) becomes the only anchor influencing the PCHIP at the new peak frame 138 → cleaned `peak_x ≈ +55` matching the surrounding raw evidence.

### Rule 3 — |x| > 110 px hard wipe

Raw frames with |x| > X_ABS_MAX_PX (110.0) are flagged as biological outliers. Wiped frames + ±X_PCHIP_EXTEND_MS (40 ms) into adjacent `is_intp` frames (PCHIP-extend, mirrors y-side `PRECLEAN_PCHIP_EXTEND_MS`). All wiped frames PCHIP-interpolated through the outlier-excluded anchor set.

**Cohort canonical count:** 0 hits across all 9 trials. The hard rule is a defensive bound; the workhorse is Rule 4.

### Rule 4 — Joint x+y short-burst wipe (direction-aware nearest-raw-flank rule)

For each raw frame `i`:
- Find the **nearest RAW flank** to the left (skip `is_intp`/`is_base` frames up to `max_flank_distance` = 5 frames each direction)
- Find the **nearest RAW flank** to the right (same)
- Require: `|x[i] − x_left| > X_FRAME_JUMP_THR_PX` (30 px) AND `|x[i] − x_right| > 30 px` (deviation from both flanks)
- Require: `|x[i] − x0| < min(|x_left − x0|, |x_right − x0|)` (direction toward x0 — distinguishes real protrusion from DLC default-back-to-zero)

If all three hold, flag the frame for joint x+y wipe. At flagged frames, x is re-PCHIP-interpolated through the outlier-excluded anchors (NOT snapped to x0 — burst sits inside an otherwise-real lick cluster, snapping would create discontinuity).

**Symmetry note:** Rule 4 catches frames where the production code's joint x+y outlier should ALSO wipe y (set is_baseline_fill=True, y=0). The visualization audit only shows the x-side effect; the production port should propagate the flag into y-side state so the detector re-runs on the joint-cleaned y trace (likely producing a different peak or skipping the lick entirely at that location).

**Discriminator validated:**
- PS54 51L first peak (x=−2, flanks +48/+30): |−2|<min(48,30) → flagged ✓
- PS54 76L first lick (x=+90, flanks +50/+50): |+90|>50 → NOT flagged (real protrusion preserved) ✓
- PS54 24L 1700ms peak (x=+95, flanks +90/+90): deviation only 5 < 30 → NOT flagged ✓
- PS47 33L active-licking troughs (x=+10, flanks at similar low x in wide trough): deviation < 30 → NOT flagged ✓

**Cohort canonical count:** 1 hit total (the PS54 51L target).

### Rule 5 — Early-M relaxation

`M_MIN_INTERVAL_MS` relaxed from 80 → **60 ms** for peak pairs where both peaks have `t_ms < M_EARLY_WIN_MS` (250 ms). Outside the early window the global 80 ms threshold stays (Decision 2 unchanged).

**Rationale (Priya 2026-05-25):** first-lick coordinates + angle are critical for downstream analyses. The general 80 ms M-gate threshold is correct for removing late-trial wobbles, but is too strict near tone onset where close-paired real licks can occur. Implemented as an early-window-aware threshold inside `gate_M` (production port); the visualization audit uses a post-process rescue function (`relax_m_gate_early_window`) on the existing v7 decisions.

**Cohort canonical count:** 1 rescue (PS54 76L first lick — the targeted case).

## Rejected peaks — convention NOT to wipe

Discussed and ruled out for Phase 7e: wiping y/x at frames associated with F/D/E/M-rejected peaks. Reasoning:

1. Defining the wipe window is genuinely ambiguous per rejection type (F could over-wipe wide-flat real licks; D's missing-context side has no boundary; E peak frame only is known; M peaks share a lick cluster).
2. Downstream metrics already handle this via Decision 5 (tongue_velocity gated to kept-lick windows only) and the per-row `lick_events/` parquet (canonical kept-lick source).
3. The only consumer that would see un-wiped rejected-peak shapes is anyone reading `cleaned_traces/` directly — and the canonical source of "which licks count" is `lick_events/`, not the trace shape.

**Convention added to Decision 3:** "`cleaned_traces/` shows the y/x signal after PRE-CLEAN wipes (artifact clusters + frame outliers + PCHIP-extend + bracketed-interp + x-side Rules 1-4). Post-detection gate rejections (F/D/E/M) are NOT reflected in `cleaned_traces/`; consumers determine kept licks from `lick_events/`."

## Updated YAML scaffold (under `dlc_kinematics.tongue_pertrial`)

Additions to the kickoff Task 1 scaffold:

```yaml
preclean:
  # ... existing y-side keys unchanged ...
  # NEW: x-side pre-clean keys (Rules 1-4)
  x_abs_max_px: 110.0           # Rule 3 hard bound on |x|
  x_pchip_extend_ms: 40.0       # Rule 3 PCHIP-extend (reuses y's value)
  x_jump_thr_px: 30.0           # Rule 4 deviation from both flanks
  x_flank_max_distance: 5       # Rule 4 max frames to scan for nearest raw flank
  # x0 is derived per-session from median(x_final[is_baseline_fill_orig]); no key.
gates:
  # ... existing F/D/E/M keys unchanged ...
  m_early_interval_ms: 60.0     # Rule 5 relaxed M-gate threshold
  m_early_win_ms: 250.0         # Rule 5 early-window cutoff
```

No new keys for x_imputed schema (per Decision 6 RESOLVED — no field needed).

## Updates to existing kickoff Decisions

- **Decision 1 (v7 algorithm locked at scratch state):** Amend to "v7 algorithm locked at scratch state PLUS Addendum #1 refinements (5 rules + early-M relaxation) per Task 0 visual review".
- **Decision 2 (M-gate 80ms trade-off):** Amend to add "Inside the first 250 ms post-tone, the threshold is relaxed to 60 ms (Rule 5) to preserve first-lick coordinates which are critical for downstream analyses".
- **Decision 3 (cleaned_traces stays at y=0 at wiped frames):** Amend to add the rejected-peak convention note above; also note that x at wiped frames goes to x0 (Rule 1) symmetric with y=0.
- **Decision 6 (lick angle x-coordinate handling pending Task 0):** RESOLVED — lick_angle consumes post-pre-clean `x_final[new_peak_frame]` directly. No x_imputed field needed; trace-level cleaning subsumes the per-peak fix.

## Implementation notes for Task 1+

- Joint x+y rule (Rule 4) should run AFTER y-side pre-clean (so `is_base_clean` is available) and BEFORE the detector. When Rule 4 fires at a frame, the production port should ALSO wipe y at that frame (PCHIP-interp + set `is_base_clean=True`) so the detector sees the cleaned trace.
- Early-M relaxation (Rule 5) should be integrated INTO `gate_M` (early-window-aware threshold) rather than as a post-process. The visualization audit's post-process form was for refactor speed only.
- The 4-tunable joint-rule (jump_thr_px, max_flank_distance, x_abs_max_px, x_pchip_extend_ms) values are locked at the cohort-of-9 calibration; first cohort re-emit post-merge may surface edge cases warranting re-tune. Out-of-scope for Phase 7e.

## Known accepted residuals

- PS47 33L active-licking troughs: a few frames have raw x slightly displaced from the surrounding cluster, but the direction check (x not closer to x0 than flanks) correctly skips them. If a re-tune is needed post-merge, the simplest knob is the jump threshold.
- Other rejected peaks (F/D/E/M) do not propagate trace wipes per the "rejected peaks NOT wiped" convention above.

---

## Mid-phase correction (Task 5b, 2026-05-26)

**Decision 6 partial reversal — per-peak `new_peak_x` reintroduced into the excise mechanism.**

The Task 1 scaffolding chose "option (a)" — drop the `x` input from `parabolic_excise` / `spline_excise` and read x from `cleaned_traces` at the imputed peak frame. Reasoning at the time: trace-level x pre-clean (Rules 1-4) would catch all relevant x outliers, so per-peak `x_imputed` would be redundant.

**This was wrong.** Verified during Task 5 wiring on PS54 46L (the canonical E_spline_impute case):

- The actual raw DLC outlier sits at frame 141 with `is_intp=True` neighbors on the left (5 frames in a row), so Rule 4 (which scans for nearest RAW flanks within ±5 frames) can't find a left raw flank → Rule 4 abstains.
- The y-side cluster classifier (Step 1a) keeps the cluster as `keep_real` (cluster has rise + fall structure with low y), so the outlier survives pre-clean.
- Rule 2 (drop y-wiped frames from x anchors) only kicks in IF the y-side wipes the frame — which it doesn't for 46L.
- Gate E catches the outlier via z-score AFTER detection, but by that point the x at the imputed peak frame is the Phase 7a.2 PCHIP value — anchored on the outlier itself. Production reports `peak_x = −13.79` instead of the audit-derived `+55.70`.

**Task 5b correction:** reintroduce `new_peak_x` to the parabolic/spline excise return shape, computed via the same audit `local_pchip_x` mechanism — wide PCHIP anchors (±`spline_anchor_win_ms` = 160 ms) with a ±`x_outlier_excise_ms` window around `outlier_peak_frame_local` excluded from the anchor set. The new `gates.x_outlier_excise_ms` (default 8 ms) is added to the YAML; separate from `spline_excise_radius_ms` so x and y excise widths can be tuned independently if needed.

**Signature change.** `parabolic_excise` / `spline_excise` now take `x` as input (in addition to `y`) and return `new_peak_x` in their dict. `LickEventRecord.x` for imputed licks reads `parabolic_excise(...)['new_peak_x']` (or `spline_excise(...)['new_peak_x']` if parabolic returned None); for non-imputed licks, reads `cleaned_x[new_peak_frame]` per Rule 1-4 (unchanged).

**Numeric verification.** On PS54 46L (the smoking-gun case):
- Audit `local_pchip_x`: +55.6991 px
- Production `new_peak_x` post-Task-5b: +55.6991 px (byte-equal, |Δ| = 0.0)
- Angle bias drop: from 7.75° (pre-Task-5b production) to 0.00° (post-Task-5b production vs audit) — full correction delivered

**Open from Task 5b** (deferred to morning review): PS51 26R can't be gate-tested under Task 5's lmax-only scope. Scratch finds the 26R impute peak via `detect_bounded_fall` (4 of 6 peaks have `src=bounded`); detect_bounded_fall isn't ported into production yet (deferred per Task 5 commit message). The Task 5b code is verified correct on 46L; 26R verification requires bounded-fall port (Task 5c?) before the cohort-wide parity check at Task 8.

**Implication for Decision 6 (Task 9 close):** the single DECISIONS entry captures the full arc — verdict (x-audit-flag, 1/89 events), option (b) lock from Addendum #1, mid-Task-5 correction restoring option (b) after the Task 1 lapse, ±8 ms excision rule, byte-equal verification on 46L. Phrase as a single resolved decision.
