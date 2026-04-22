# scipy 1.15.1 vs 1.17.1 PCHIP pilot — Phase 7a.0

**Generated 2026-04-22, extends PR #79.**

## Session probed

PS46 / 20250307 / tongue (STABLE combo per
[`baseline-seed-table.md`](baseline-seed-table.md), in-scope per PS46
`sessions.start = 2025-03-07`).

- NPZ: `O2_analysis/PS46/PS46_tongue_kinematics/.../PS46_20250307_cam2_tongue_interp_v5p3.npz`
- `n_frames`: 931,834
- NaN-in `x_drop` (post-likelihood-drop, pre-PCHIP): 833,739 (89.47%)
- NaN-in `y_drop` (post-likelihood-drop, pre-PCHIP): 833,739 (89.47%)
- NaN-out `x_interp` (post-PCHIP, both envs): 17,822 (1.91%)
- NaN-out `y_interp` (post-PCHIP, both envs): 17,822 (1.91%)

The residual 17,822 NaN positions after PCHIP are leading / trailing
frames outside the bracketing of any anchor (PCHIP with
`extrapolate=False`). Both scipy versions produce identical NaN
boundaries — no version-dependent extrapolation behavior is
exercised.

## Diff summary

All diffs computed on the 914,012-frame common non-NaN region.

| Dim | max\|Δ\| | median\|Δ\| | p99\|Δ\| | p99.9\|Δ\| | n_exact_equal | n < 1e-6 | n < 1e-4 |
|---|---|---|---|---|---|---|---|
| x | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 914,012 | 914,012 | 914,012 |
| y | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 914,012 | 914,012 | 914,012 |

NaN-boundary deltas:
- NaN only in 1.15.1 output (x / y): 0 / 0
- NaN only in 1.17.1 output (x / y): 0 / 0

**Bit-for-bit identical.** Every non-NaN frame in the PCHIP output
matches exactly between scipy 1.15.1 and 1.17.1 on this session;
every NaN-boundary frame matches too.

## Interpretation

Per the paste-in's three-bullet tree:

- If `max|Δ| < 1e-6` on both dims: parity under mixed scipy is safe
  at `atol=1e-6`. No pin needed. Recommend: run 7a.1 parity under
  1.17.1 with `atol=1e-6`.
- If `1e-6 ≤ max|Δ| < 1e-4` on either dim: widen to `atol=1e-4`,
  DECISIONS entry documenting the drift.
- If `max|Δ| ≥ 1e-4` on either dim: pin env to scipy 1.15.1 for
  parity-only validation.

The pilot lands well inside the strongest regime of bullet 1 —
`max|Δ| = 0.0`, not merely below the 1e-6 threshold.

## Recommendation (filled after running)

**Option A — no pin, no widening.** Run Phase 7a.1 parity under the
consolidated `stroke_orofacial` env's scipy 1.17.1 with `atol=1e-6`
per `interpolation-strategy.md` §6's default tolerance. The scipy
1.15.1 → 1.17.1 upgrade path is confirmed non-perturbing for the
PCHIP call used in the v5p3 interpolation pipeline: 914,012 of
914,012 common non-NaN frames are bit-for-bit identical on both x and
y; NaN boundaries (17,822 leading/trailing positions each) agree
exactly. No DECISIONS-logged scope change required on the
scipy-version axis for 7a.

This recommendation is the input to the Task 3 DECISIONS entry's
"scipy version handling" sub-section.

## Caveats

- **Single-session pilot.** Generalizing to the full cohort: PCHIP is
  a local, anchor-driven interpolator — the numerical behavior on any
  given session is determined by its (idx_nonan, val_nonan) support.
  No scipy 1.15.1 → 1.17.1 PCHIP-constructor changes landed between
  those releases per scipy's release notes, consistent with the
  bit-identical result here. But the pilot should be re-run on a
  stress-test session (higher NaN fraction) before 7a.1 opens PR, if
  only to add a second-session datapoint to the DECISIONS entry.
  Suggested stress session: PS51 / 20250430 (per
  `interpolation-strategy.md` §6 stress-test set — little-to-no
  licking, expected high NaN fraction).
- **Pilot isolates the PCHIP call only.** The 7a interpolation
  pipeline has 7 stages (xrange → thr → drop → interp → interp_filled
  → final). Pilot tests stage 4 (`interp`) only. Full 7a.1 parity
  exercises the complete pipeline; scipy-version drift could
  theoretically compound across stages if a later stage's
  numerical sensitivity differs. The final tolerance choice is still
  validated against the 14-session parity harness in 7a.1, not
  against this pilot alone.
- **Pilot uses a simplified PCHIP wrapper** (`pchip_fill` in
  `tests/scripts/scipy_version_pilot.py`) that approximates the
  legacy `_stage_interp`: fits PCHIP on all non-NaN anchors and
  evaluates at all NaN indices, with `extrapolate=False` and a
  linear fallback. It does NOT reproduce the legacy's per-gap
  bracketing logic (e.g., `REQUIRE_BRACKETED_BY_HILK`,
  `max_gap_ms` gap-drop), which live in later stages. That is
  intentional — isolating PCHIP itself is what we want to measure.
  Those stages are pure numpy and version-insensitive.
