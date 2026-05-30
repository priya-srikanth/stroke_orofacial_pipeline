# Fix proposal — phase-aligned tongue substrate bypasses v7 cleaning

**Status:** proposal only. No code was changed in this read-only diagnostic
session (`chore/trajectory-artifact-qc`). This documents the root cause and
remediation options for Priya to scope.

---

## 1. The bug

The Q13c v2 phase-aligned tongue **trajectories** and the Q13b scalar
**endpoints** are built from `TongueVisualBundle.df_trials.{y_snip, x_snip}`.
Those snippets are sliced from the **interpolated** trace, and their peaks come
from the legacy `_slope_detect_lick_peaks` detector:

- `_build_tongue_pertrial_core` ([tongue_pertrial.py:3307-3310](../../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L3307-L3310)):
  ```python
  tongue_df, tongue_meta = _load_tongue_centered_trace(manifest, resolver)  # interpolated_trace
  x_final = tongue_df["x_final"].to_numpy(...)
  y_final = tongue_df["y_final"].to_numpy(...)
  ```
- `_load_tongue_centered_trace` reads `resolver.interpolated_trace`
  ([tongue_pertrial.py:1687-1705](../../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L1687-L1705)) — the **pre-clean** 7a.2 trace.
- `y_snip`/`x_snip` are sliced from this `y_final`/`x_final`
  ([_build_visual_bundle_per_trial, tongue_pertrial.py:3004-3009](../../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L3004-L3009)).

Meanwhile the Phase 7e v7 pipeline (preclean → detect_v2 → gates F/D/E/M)
runs **in parallel** and its cleaned output is consumed **only** by the
`cleaned_traces` / `lick_events` parquet writers
([tongue_pertrial.py:1383-1397](../../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L1383-L1397)). It never reaches the phase-aligned substrate.

**Net effect:** the trajectory/endpoint figures plot protrusions that the v7
gates *rejected* (baseline-filled to 0 in the cleaned trace; absent from the
v7-gated `lick_events`).

### Two contributing mechanisms

1. **No preclean on the figure path.** The v7 preclean shape-gate is what
   rejects these protrusions before detection. The legacy detector has no
   preclean — it runs straight on the interpolated trace.
2. **Detection smoothing fabricates the rise.** The legacy detector smooths y
   over `smooth_ms_detect_y = 12 ms` (3 frames) before `np.gradient`
   ([_detector.py:214-221](../../src/stroke_orofacial/dlc_kinematics/_detector.py#L214-L221)). A single-frame
   baseline-fill→protrusion **step** is smeared into a multi-frame ramp that
   satisfies the `rise_min_n = 4` check on a *fabricated* rise.

### Third affected consumer — the `<10` session filter

`DlcSessionFilter(min_trials_with_detected_lick=10)` counts
`tongue.n_licks_family.n_licks` — the **same** legacy/interpolated path. For
PS51 contra (R): `n_trials_with_detected_lick = 19 ≥ 10` → **kept**. On
v7-gated counts, R ≈ 1 → would be **discarded**. So the filter offers no
protection and inherits the defect.

## 2. Evidence (this probe)

Acute, contra (= mouse-R) trials, by phenotype:

| phenotype | n trials | v7-rejected (interp-only) | acute-jump |
|---|---|---|---|
| moderate-severe (PS51) | 12 | **11 (92%)** | **12 (100%)** |
| severe (PS54+PS55) | 127 | **120 (94%)** | **113 (89%)** |
| mild (ref) | 200 | 1 (0.5%) | 4 (2%) |
| moderate (ref) | 178 | 3 (2%) | 9 (5%) |

The suspect cells are ~92–94% built on v7-rejected protrusions; the reference
is <2%. Per-trial detail in `trial_classification.csv`; visuals in
`trial_grid_*` and `provenance_by_phenotype.svg`.

## 3. Remediation options

### Option A — fix provenance (PRIMARY, recommended)

Make the phase-aligned substrate consume the **v7-cleaned** trace + **v7-gated**
peaks instead of the interpolated trace + legacy detector. The v7 path already
correctly rejects these artifacts (it rejected 11/12 / 120/127), so this needs
no detection retuning.

- Sketch: in `_build_tongue_pertrial_core`, source `x_final`/`y_final` (and the
  per-trial peak set the bundle exposes) from the v7 cleaned trace /
  `v7_trial_results` rather than the raw interpolated `tongue_df`. Equivalently,
  rebuild `y_snip`/`x_snip` from `cleaned_traces` and take peaks from
  `lick_events`.
- **Blast radius — large.** This substrate feeds *every* Q13/Q13b/Q13c
  phenotype-pooled output (all phenotypes × sides × epochs × signals: angle,
  x, y; trajectories + scalar endpoints + their stats), not just the two
  suspect cells. Healthy-animal cells will change little (<2% rejected); severe
  cells change a lot. Re-render + re-stat everything downstream and re-parity.
- The `<10` session filter should also count **v7-gated** licks
  (`lick_events`), not `n_licks_family.n_licks`, so it actually discards
  sessions whose real (v7-kept) lick count is sub-threshold.

### Option B — detection-smoothing (SECONDARY, optional hardening)

Set `smooth_ms_detect_y = 0` (or detect on an unsmoothed signal) so a 1-frame
jump fails `rise_min_n = 4`. **Caveat:** raw DLC is jittery; unsmoothed slope
detection risks single-frame **noise** false-positives — trading one artifact
class for another. Not a substitute for Option A; only consider if a
post-provenance-fix artifact survives.

### Option C — detect-then-smooth-for-kinematics (the velocity question)

Decouple detection signal from measurement signal: detect on the cleanest
signal (existence + timing), then compute velocity / peak-y / angle on an
appropriately smoothed signal *within validated lick windows*. The config
already separates `smooth_ms_detect_y` (detection) from `smooth_ms_vel`
(velocity), so velocity smoothing can stay while detection smoothing changes.
Velocity in particular **needs** smoothing (differentiation amplifies noise).

## 4. Recommendation

Do **Option A first**, re-render the Q13/Q13b/Q13c outputs, and re-examine
whether any artifact survives **before** touching detection knobs (Option B).
Keep velocity/kinematics smoothing (Option C) — it's correct and orthogonal.
Validate with this probe re-run: suspect-cell v7-rejected% should drop to ~0
(because the substrate would *be* the v7-kept set).
