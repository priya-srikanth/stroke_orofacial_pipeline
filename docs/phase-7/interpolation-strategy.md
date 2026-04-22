# Phase 7a — Interpolation design brief

**Branch:** `phase-7-dlc-kinematics`.
**Status:** Draft for Cowork review with Priya (2026-04-22).
**Unblocks:** 7a-impl (`src/stroke_orofacial/dlc_kinematics/interpolation.py`).

This brief resolves the four open knobs flagged in
[docs/phase-7/classification-tongue.md:242–257](classification-tongue.md#cell-23)
plus the jaw-specific additions flagged in
[docs/phase-7/classification-jaw.md:322–349](classification-jaw.md#cell-22).
Once Priya signs off on the decisions below, 7a-impl proceeds. **No code
is written from this brief until it is signed off.**

---

## 1. Scope

Port the legacy v5p3 interpolation logic from
- tongue notebook Cell 23 (763 lines), and
- jaw notebook Cell 22 (755 lines)

into a single bodypart-parametric module
`src/stroke_orofacial/dlc_kinematics/interpolation.py` emitting

```
pipeline_outputs_v2/dlc_analysis/interpolated_traces/{bodypart}/{animal}/{date}.parquet
```

The tongue and jaw cells share **identical algorithmic skeleton** (same
`interp_small_gaps_method`, `_build_reward_aligned_pool_mask`,
`_fill_nan_with`, `compute_session_x_range`, identical 7-stage control
flow). They differ only in bodypart-parametric constants (X_RANGE_PM,
N_NEIGH, max_gap_ms, center_mode) and per-cohort baseline Y0/X0 values.
One module, two callers.

**Downstream consumers of 7a output:** 7b (tongue endpoints), 7c (jaw
endpoints + mismatch classifier), 7d (whisker — reads as a reference for
the output parquet schema, does not read tongue/jaw parquets directly),
7e (face-velocity PCs — reads jaw + nose interpolated traces if we decide
they feed the velocity tensor), 7f (PSD — reads tongue/jaw/whisker).

**Prerequisite data-repair cells** (tongue 13/16/17/19 and jaw
13/15/16/18) remain deferred to 7-pre, which will land only if a 7a
parity run actually fails on a multi-video or multi-alignment session.

---

## 2. Decisions on the four open knobs

For each knob, this brief proposes a resolution and a rationale. Priya
flags agree / disagree / discuss for each.

### Knob 1 — 7-stage intermediate arrays vs single `(x_final, y_final)` output

**Legacy shape:** each interp NPZ carries 15 arrays — the raw, xrange,
thr, drop, interp, interp_filled, and final versions of both x and y,
plus `X0`, `Y0`, `fps`, `n_frames`, `reward_centers_cam`,
`baseline_stage`. NPZ size per session: ~5–15 MB.

**Usage pattern:** the intermediate stages are consumed ONLY by the
"plot interpolation steps" QC cells (tongue Cell 29, jaw Cell 28 — both
Exploratory). The *analytical* downstream consumers (tongue Cells 33,
36, 39, 42, 50 and jaw endpoint sub-phases) read only
`x_final`/`y_final`.

**Proposal — split emit.** Emit two artifacts per (bodypart, animal,
date):

1. **Canonical parquet** (the thing downstream phases consume):
   ```
   interpolated_traces/{bodypart}/{animal}/{date}.parquet
   ```
   Schema: one row per camera frame. Columns:
   `frame_idx` (int), `x_final` (float), `y_final` (float),
   `likelihood_raw` (float), `is_interp_fill` (bool — true when the
   frame was NaN-filled by PCHIP), `is_baseline_fill` (bool — true when
   the frame was `_fill_nan_with(X0)`-filled). Plus file-level metadata
   attributes: `X0`, `Y0`, `fps`, `n_frames`, `center_mode`,
   `interpolation_version`, `wavesurfer_sides_match_mouse_sides`,
   `side_convention_version`.

2. **Optional QC NPZ** (only when `emit_qc_bundle=True`):
   ```
   interpolated_traces/{bodypart}/{animal}/{date}.qc.npz
   ```
   Contains the intermediate stages (xrange, thr, drop, interp,
   interp_filled) for the rare debugging sessions where the analyst
   wants to inspect which stage dropped a given frame. Skipped by
   default.

**Rationale.** Parquet is the analytical primitive the rest of the
pipeline uses (Phase 4 centered parquets, Phase 6 reward-aligned
outputs). NPZs are fine for legacy but columnar parquet lets downstream
consumers read just `x_final`/`y_final` without decompressing the full
bundle, cuts per-session on-disk size by ~75% (single stage vs 7), and
makes the schema self-documenting. The `is_interp_fill` /
`is_baseline_fill` columns preserve the "which stage produced this
sample" provenance that makes the 7-stage NPZ useful, at much lower
cost than emitting all intermediate arrays.

**Parity implication.** Legacy parity script loads
`x_final`/`y_final` from legacy NPZ; our parquet exposes the same two
columns. `atol=1e-6` comparison is a direct parquet-column-vs-NPZ-key
read on both sides.

> **Priya's call:** Confirm split emit (parquet canonical + optional
> QC NPZ) vs. the alternative "emit the full 7-stage parquet with all
> intermediate columns always" or "single-column final-only parquet,
> drop intermediates entirely."

### Knob 2 — PCHIP default vs PCHIP-with-linear-fallback

**Legacy default:** `INTERP_METHOD = "pchip"` with
`INTERP_FALLBACK = "linear"`. The linear-fallback path fires only when
the PCHIP interpolator raises (e.g., insufficient bracketing context).
The classification says PCHIP-vs-linear should be a config knob.

**Proposal — keep PCHIP as default, keep the linear fallback, do not
expose as user-editable runtime knob.** The fallback exists for
numerical robustness on degenerate gaps (fewer than 2 hi-lk context
points on one side); swapping the default to linear would silently
degrade smoothness for every session. Putting the knob under a buried
`params["interpolation"]["method"]` is fine — the concern is that
`defaults.yaml` not surface it as a prominent knob that might tempt
future edits.

**Proposal in defaults.yaml:**

```yaml
dlc_kinematics:
  interpolation:
    method: pchip            # do not change without DECISIONS entry
    fallback: linear         # do not change without DECISIONS entry
```

**Parity implication.** No algorithmic change vs legacy.

> **Priya's call:** Confirm PCHIP-default-with-linear-fallback, both
> exposed only in `defaults.yaml` under an explicit "do not change
> without DECISIONS entry" comment. Or make `method` an impl-time
> constant in the module source, not a config knob at all.

### Knob 3 — FORCE_Y0/FORCE_X0 paths: drop data-driven percentile code?

**Legacy state:** both `FORCE_Y0` and `FORCE_X0` are `True` in every
current run. The data-driven percentile-based baseline estimation path
exists (`baseline_y_lk_thr`, `baseline_y_percentile`, etc. — roughly
40 lines) but is cold — no current analysis uses it.

**Proposal — preserve the data-driven path as an option, default to
forced.** The data-driven path was the original (pre-v5p3) baseline
computation. It matters for sessions where the hardcoded cohort-specific
Y0 is wrong (e.g., camera reposition; future animals not in the PS46–55
cohort). Dropping it now would require re-deriving it if a new cohort
arrives. Cost to keep: 40 lines inside a clearly-named branch; negligible
maintenance.

**Proposal in defaults.yaml:**

```yaml
dlc_kinematics:
  <bodypart>:
    baseline:
      force: true                   # set false to use data-driven path
      # when force: true —
      y0: null                      # required; fail loudly if null
      x0: null                      # required; fail loudly if null
      # when force: false —
      y0_lk_thr: 0.95
      y0_percentile: 5.0
      x0_lk_thr: 0.95
      x0_percentile: 50.0
```

Baseline values themselves move to `configs/animals.yaml` per the jaw
notebook's strict-correctness concern (next section).

**Parity implication.** No change vs legacy; parity runs use the
forced path with the cohort-specific Y0/X0 from `animals.yaml`.

> **Priya's call:** Keep-as-option vs. drop-entirely. If keep, confirm
> the config layout above.

### Knob 4 — X-range source: `"lk"` vs `"finite"`

**Legacy default:** X-range source is `"lk"`, which means the
X_RANGE_PM filter uses `median(X[lk > LK_THR]) ± X_RANGE_PM`. This
creates a bootstrap dependency: the median is computed on samples that
pass the likelihood threshold, but the threshold is also what Stage 2
("thr") uses to drop points — Stage 1 ("xrange") is depending on the
output of Stage 2's criterion.

**Alternative:** X-range source `"finite"` uses
`median(X[np.isfinite(X)])`. This decouples Stage 1 from Stage 2 —
Stage 1 drops X-outliers based on *all* non-NaN samples; Stage 2 then
drops by likelihood independently.

**Proposal — keep `"lk"` default, parity-verify, then revisit in a
post-7a DECISIONS entry.** Switching to `"finite"` would change the
numerical output (slightly different median → slightly different xrange
rejection → slightly different downstream). Parity against legacy NPZs
requires `"lk"`. If the post-7a scientific review shows the bootstrap
dependency is causing false rejections in specific sessions, switch to
`"finite"` as an explicit DECISIONS-logged scope change, not a silent
port-time refactor.

**Parity implication.** `"lk"` preserves byte-equivalence with legacy;
`"finite"` would require re-baselining parity targets from scratch.

> **Priya's call:** Keep `"lk"` for port parity, or switch to
> `"finite"` at port time (and re-baseline parity). Recommend the
> former.

---

## 3. Jaw-specific additions (from classification-jaw.md)

### 3.1 Per-cohort baseline Y0/X0 → `configs/animals.yaml`

**Strict correctness requirement.** The legacy jaw cell has:

```
PS46-50:  Y0 = 310, X0 = 0
PS51, PS54:  Y0 = 290, X0 = 12  # tongue cohort, reused for jaw
PS55:  Y0 = 290, X0 = 0
```

as in-cell comments. The notebook's active branch uses `PS55`'s values
for **every** mouse. This is a latent bug — the notebook's current
"production" output for PS46-50 and PS51/PS54 is computed with PS55's
baselines.

**Proposal.** Add per-mouse `kinematics_baselines:` block to
`configs/animals.yaml`:

```yaml
PS46:
  # ... existing fields ...
  kinematics_baselines:
    jaw:
      y0: 310.0
      x0: 0.0
    tongue:
      y0: -110.0
      x0: 0.0
```

Load into `AnimalInfo.kinematics_baselines: dict[str, dict[str, float]]`.
The interpolation module reads the per-mouse baseline; if missing, raises
with an explicit error naming the missing `(animal, bodypart)` pair.

**This is a deliberate scope-in for 7a-impl** — we are fixing a latent
correctness issue at port time, not propagating the bug. Log this
divergence explicitly in MIGRATION_LOG with the legacy-output diff
numbers for PS46-50 and PS51/PS54 (the mice whose jaw legacy NPZs used
the wrong baseline).

> **Priya's call:** Confirm the per-mouse config layout + the
> fix-at-port scope-in. The alternative is preserving the buggy
> PS55-for-everyone behavior for byte-parity, then filing a
> post-port follow-up to fix it — strictly worse, but strictly closer
> to legacy parity.

### 3.2 `EXCLUDE_DATES` dict → `configs/animals.yaml`

Legacy jaw cell has:

```python
EXCLUDE_DATES = {"PS55": ["20250427", "20250428"]}
```

`AnimalInfo.exclusions` already exists. Add these two entries as
`exclusions` with `applies_to: ["jaw"]` so the interpolation module
skips them via `animal_info.is_excluded(session_date, "jaw")`.

**Proposal.** Add to `configs/animals.yaml` under PS55:

```yaml
PS55:
  exclusions:
    - date: 2025-04-27
      reason: "jaw DLC quality too low for interpolation (legacy EXCLUDE_DATES)"
      applies_to: [jaw]
    - date: 2025-04-28
      reason: "jaw DLC quality too low for interpolation (legacy EXCLUDE_DATES)"
      applies_to: [jaw]
```

> **Priya's call:** Confirm port + verify the exclusion reason. If
> there are similar implicit exclusions anywhere in tongue Cell 23,
> flag them now so we catch them together.

### 3.3 Bodypart-parametric constants under `dlc_kinematics.<bodypart>:`

```yaml
dlc_kinematics:
  tongue:
    center_mode: centered_spout_midpoint
    interpolation:
      x_range_pm: 150.0
      lk_thr: 0.5
      n_neigh: 2
      neighbor_ms: 16.0
      max_gap_ms: 56.0
      interp_n_side: 6
      require_bracketed_by_hilk: true
  jaw:
    center_mode: centered_eye_midpoint
    interpolation:
      x_range_pm: 75.0
      lk_thr: 0.5
      n_neigh: 3
      neighbor_ms: 16.0
      max_gap_ms: 120.0
      interp_n_side: 6
      require_bracketed_by_hilk: true
```

> **Priya's call:** Confirm the default values (lifted verbatim from
> legacy).

---

## 4. Module API

`src/stroke_orofacial/dlc_kinematics/interpolation.py`:

```python
from __future__ import annotations
from pathlib import Path
from typing import Literal
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver

def build_interpolated_trace(
    manifest: SessionManifest,
    bodypart: Literal["tongue", "jaw"],
    resolver: PathResolver,
    params: dict | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    emit_qc_bundle: bool = False,
) -> Path | None:
    """Build per-frame interpolated trace for one bodypart in one session.

    Writes:
      interpolated_traces/{bodypart}/{animal}/{date}.parquet     (always)
      interpolated_traces/{bodypart}/{animal}/{date}.qc.npz      (if emit_qc_bundle)

    Returns the parquet Path (or None if skip and parquet exists).
    """
```

Inside the module:

```python
def _interpolate_bodypart_core(
    df: pd.DataFrame,
    bodypart: str,
    center_mode: str,
    params: dict,
    reward_centers_cam: np.ndarray,
) -> InterpolationResult:
    """Stage-by-stage v5p3 interpolation; no I/O.

    Pure function for testing — takes a DataFrame, returns an
    InterpolationResult with all 7 stages + metadata.
    """
```

`InterpolationResult` is a dataclass carrying the 7 stages (for QC emit),
the final `(x_final, y_final)`, the two `is_*_fill` boolean masks, and
metadata (X0, Y0, fps, n_frames, interpolation_version,
center_mode).

**Convenience wrapper** for (animal, date) callers:

```python
def build_interpolated_trace_by_animal_date(
    animal: str,
    date: datetime.date,
    bodypart: Literal["tongue", "jaw"],
    resolver: PathResolver,
    **kwargs,
) -> Path | None:
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info, analysis_type="kinematics")
    return build_interpolated_trace(manifest, bodypart, resolver, **kwargs)
```

---

## 5. Side-convention handling

The legacy cells apply the L↔R flip at **load** time (`lk["Reward_R"]`
used as mouse-L, etc.). Our port follows the Phase 6.8 boundary-layer
convention: internal arithmetic stays on wavesurfer frame; the flip
happens at emit.

**In practice for 7a:** the interpolated-trace parquet carries
*bodypart* data (`x_final`, `y_final`) which is **not side-labeled**.
The only side-sensitive metadata is `reward_centers_cam`, which is
per-reward-event (each event has a wavesurfer-frame `side` ∈ {L, R}).

Option A: don't store per-reward side on the interpolated-trace parquet
(keep the parquet pure-bodypart; push side-label stamping to the
per-trial endpoint modules in 7b/7c).

Option B: include a separate `reward_events` sub-table in the parquet
(either as a Parquet multi-level or as a sibling NPZ) with per-event
`frame_cam`, `side_mouse` (already translated via `to_mouse_frame()`),
`wavesurfer_sides_match_mouse_sides`, `side_convention_version`.

**Proposal — Option A.** Keep the interpolated-trace parquet
pure-bodypart. Per-reward side labels live where they are actually
consumed (7b/7c per-trial endpoints read reward events fresh from
Phase 2 `licks_and_rewards/{animal}/{date}.npz` and apply the
boundary-layer translation at emit). Keeps 7a's contract simple and
avoids duplicating reward-event data across parquets.

> **Priya's call:** A vs B. Recommend A.

---

## 6. Parity strategy

**Targets.** Legacy NPZs at
```
{MICROSCOPE}/O2_analysis/PS{NN}/PS{NN}_tongue_kinematics/processed_interpolated_data/centered_spout_midpoint/PS{NN}_{YYYYMMDD}_cam2_tongue_interp_v5p3.npz
{MICROSCOPE}/O2_analysis/PS{NN}/PS{NN}_jaw_kinematics/processed_interpolated_data/centered_eye_midpoint/PS{NN}_{YYYYMMDD}_cam2_jaw_interp_v5p3.npz
```

**Parity set.** `PS46 {20250307, 20250310, 20250313}`,
`PS54 {20250506, 20250509, 20250512}`, and
`PS55 {20250501, 20250504, 20250507}` — nine sessions chosen to span
baseline + post-stroke across three mice representing the three
cohort-baseline groups (PS46-50, PS51/PS54, PS55).

**Tolerances.**
- `x_final`, `y_final` — `atol=1e-6` element-wise
- `X0`, `Y0` — exact match
- `fps`, `n_frames` — exact match

**Expected mismatch — deliberate divergence.** The jaw-baseline fix
(§3.1) makes PS46-50 and PS51/PS54 numerically differ from legacy.
Parity script for those mice compares **the fixed baselines' output
against a re-derivation of what the legacy NPZ would have been with the
correct baseline** (i.e., `x_final_legacy + (Y0_legacy - Y0_correct)`
for the jaw Y trace — the baseline subtraction is linear, so
we can analytically back out the legacy-with-bug values). This lets us
parity-check every mouse, with the jaw-baseline fix being the only
permitted numerical difference.

**Parity script location.**
`tests/scripts/parity_phase7a_interpolation.py PS46 20250307 tongue`.
Invoked as part of 7a-impl sign-off, not as a pytest fixture (real-data
reads from MICROSCOPE mount).

> **Priya's call:** Confirm the nine-session parity set. Swap in
> different sessions if there's a session you want prioritized (e.g.,
> one with a known occlusion-heavy trial).

---

## 7. Hardcoded constants — complete list for `configs/defaults.yaml`

Assuming decisions above confirmed, the `dlc_kinematics:` section
produced by 7a is:

```yaml
dlc_kinematics:
  interpolation_version: v5p3
  interpolation_method: pchip
  interpolation_fallback: linear
  tongue:
    center_mode: centered_spout_midpoint
    interpolation:
      x_range_pm: 150.0
      x_range_source: lk        # keep "lk" for port parity; see Knob 4
      lk_thr: 0.5
      n_neigh: 2
      neighbor_ms: 16.0
      max_gap_ms: 56.0
      interp_n_side: 6
      require_bracketed_by_hilk: true
    baseline:
      force: true
      y0_lk_thr: 0.95
      y0_percentile: 5.0
      x0_lk_thr: 0.95
      x0_percentile: 50.0
  jaw:
    center_mode: centered_eye_midpoint
    interpolation:
      x_range_pm: 75.0
      x_range_source: lk
      lk_thr: 0.5
      n_neigh: 3
      neighbor_ms: 16.0
      max_gap_ms: 120.0
      interp_n_side: 6
      require_bracketed_by_hilk: true
    baseline:
      force: true
      y0_lk_thr: 0.95
      y0_percentile: 5.0
      x0_lk_thr: 0.95
      x0_percentile: 50.0
```

Per-mouse Y0/X0 go to `configs/animals.yaml` under each animal's
`kinematics_baselines:` block (§3.1).

---

## 8. Testing strategy

Unit tests (pure-function, no I/O, use synthetic DataFrames):

- `test_stage_xrange_drops_outliers` — verify X_RANGE_PM filter removes
  expected samples, preserves others.
- `test_stage_thr_drops_low_likelihood` — likelihood mask correctness.
- `test_stage_drop_isolated_hilk` — isolated-point rejection with
  neighbor-count edge cases (0, 1, N, N-1 hi-lk neighbors).
- `test_stage_interp_fills_short_gaps` — PCHIP fills gap below
  `max_gap_ms`, leaves gap above untouched.
- `test_stage_interp_preserves_long_gaps` — gaps > max_gap_ms remain NaN.
- `test_stage_interp_filled_baseline_substitution` — NaN after interp
  gets `X0`/`Y0` substituted.
- `test_stage_final_baseline_subtraction` — `x_final = x - X0`,
  `y_final = y - Y0`.
- `test_bodypart_dispatch_tongue` — module reads the right x/y/likelihood
  columns for tongue.
- `test_bodypart_dispatch_jaw` — same for jaw, with different defaults.
- `test_force_baseline_from_animal_info` — loads Y0/X0 from
  `AnimalInfo.kinematics_baselines`, raises on missing.
- `test_excluded_session_returns_none` — interpolation respects
  `AnimalInfo.is_excluded(date, bodypart)`.
- `test_parquet_schema` — emitted parquet has the 5 expected columns +
  the 6 expected file-level attributes.
- `test_overwrite_skip_respects_existing` — `overwrite="skip"` returns
  existing path; `overwrite="force"` overwrites.
- `test_emit_qc_bundle_emits_npz` — `emit_qc_bundle=True` writes the
  companion `.qc.npz` with all 7 stages.

Integration tests (read real MICROSCOPE data if available):

- `test_integration_ps46_20250307_tongue` — build interpolated trace,
  spot-check `x_final`/`y_final` statistics (median, std, NaN count)
  against legacy-derived expected values.
- `test_integration_ps46_20250307_jaw` — same for jaw.

All tests use `PathResolver(output_root=tmp_path)`.

---

## 9. Acceptance criteria for 7a-impl

- Module `src/stroke_orofacial/dlc_kinematics/interpolation.py` passes
  all unit tests.
- Nine-session parity script passes (§6).
- `configs/defaults.yaml` has the `dlc_kinematics:` section (§7).
- `configs/animals.yaml` has `kinematics_baselines:` populated for
  PS46–PS55.
- `AnimalInfo` loads `kinematics_baselines` and `exclusions` with
  `applies_to: [jaw]`.
- Ruff clean.
- MIGRATION_LOG entry + DECISIONS entry on the 4 knobs + jaw-baseline
  fix.

---

## 10. Open questions for Priya

1. Knob 1 — split emit (parquet canonical + optional QC NPZ) vs
   alternatives?
2. Knob 2 — PCHIP/linear fallback config layout?
3. Knob 3 — keep or drop data-driven percentile baseline path?
4. Knob 4 — keep `"lk"` X-range source for parity, or switch to
   `"finite"` at port time?
5. §3.1 — per-mouse jaw baseline fix-at-port vs preserve-legacy-bug?
6. §3.2 — confirm PS55 2025-04-27 and 2025-04-28 jaw exclusions?
7. §5 — interpolated-trace parquet pure-bodypart (Option A) vs
   side-aware (Option B)?
8. §6 — nine-session parity set OK as chosen?
