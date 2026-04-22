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
stroke_orofacial_pipeline_outputs/dlc_analysis/interpolated_traces/{bodypart}/{animal}/{date}.parquet
```

The tongue and jaw cells share **identical algorithmic skeleton** (same
`interp_small_gaps_method`, `_build_reward_aligned_pool_mask`,
`_fill_nan_with`, `compute_session_x_range`, identical 7-stage control
flow). They differ only in bodypart-parametric constants (X_RANGE_PM,
N_NEIGH, max_gap_ms, center_mode) and per-animal, per-bodypart baseline Y0/X0 values.
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
   the frame was `_fill_nan_with(X0)`-filled), `fill_method`
   (categorical small-int enum: `0=none, 1=pchip, 2=linear, 3=baseline`
   — supports QC like "how often did the linear fallback fire?" without
   reading the companion QC NPZ). Plus file-level metadata attributes:
   `X0`, `Y0`, `fps`, `n_frames`, `center_mode`, `baseline_stage`
   (legacy NPZ carries this — preserved for provenance),
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
forced.** The data-driven path matters for sessions where the
per-animal hardcoded Y0 is wrong (e.g., camera reposition; future
animals). Dropping it now would require re-deriving it if a new cohort
arrives. Cost to keep: 40 lines inside a clearly-named branch;
negligible maintenance.

**Legacy percentile semantics (corrected 2026-04-22 by Priya).** The
data-driven path has one primary percentile (on Y) and a *derived* X
baseline:

- `Y0` (when `force: false`) = the lowest *n*'th percentile of Y
  values drawn from a **trial-aligned sample pool** (not all frames).
  Two parameters: the percentile itself (e.g. 5.0) and the likelihood
  threshold that gates inclusion in the trial-aligned pool.
- `X0` (when `force: false`) is NOT an independent percentile. It is
  the **median of X values among the samples selected by the Y
  percentile filter** — a conditional median, where the conditioning
  set is whichever rows ended up in the bottom Y-percentile bucket.

Config layout reflecting this:

```yaml
dlc_kinematics:
  <bodypart>:
    baseline:
      force: true                   # set false to use data-driven path
      # when force: false —
      y0_lk_thr: 0.95                    # likelihood gate for trial-aligned pool
      y0_percentile: 5.0                  # lowest n'th percentile of Y in pool
      x0: "median_of_y_percentile_subset" # explicit: X0 is median-X of the Y-percentile samples, no independent percentile
```

The `x0_lk_thr` / `x0_percentile` keys from earlier drafts of this
brief are removed — they don't correspond to legacy behavior. The
module function's docstring must spell out the "conditional median"
semantics explicitly so future readers don't misread this as an
independent X percentile estimator.

Per-animal forced baselines themselves move to `configs/animals.yaml`
per §3.1 below.

**Parity implication.** No change vs legacy; parity runs use the
forced path with per-animal Y0/X0 from `animals.yaml`.

> **Priya's call:** Keep-as-option vs. drop-entirely. If keep, confirm
> the corrected percentile-semantics config layout above.

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

### 3.1 Per-animal, per-bodypart baselines → `configs/animals.yaml`

**Reframe (2026-04-22 Priya Cowork).** This is a **faithful port**, not
a bug fix. The legacy jaw notebook's final-saved state carries PS55's
X0/Y0 values, but the legacy production outputs on
`{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS{NN}/` were generated by
Priya manually editing X0/Y0 between per-animal runs. Each saved NPZ
was computed with the correct per-animal baseline; the notebook's
final state just shows the last animal run (PS55). The port's job is
to encode those per-animal values into `configs/animals.yaml` so
future runs are reproducible without manual per-run editing. No
legacy-output divergence; no MIGRATION_LOG "deliberate divergence"
entry needed.

**Per-animal, per-bodypart values.** Tongue and jaw carry different
Y0/X0 per animal. Derivation approach for CC: each legacy NPZ at
`{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS{NN}/PS{NN}_{bodypart}_kinematics/processed_interpolated_data/{center_mode}/PS{NN}_{YYYYMMDD}_cam2_{bodypart}_interp_v5p3.npz`
carries its own `X0` / `Y0` keys recording the baselines actually used
for that run. Read one representative NPZ per (animal, bodypart),
extract `X0` and `Y0`, seed `configs/animals.yaml`. If a value is
missing or ambiguous (e.g., the per-animal X0/Y0 differs across
sessions for the same bodypart, suggesting Priya retuned mid-cohort),
**STOP and ask** before proceeding.

**Config layout.**

```yaml
PS46:
  # ... existing fields ...
  kinematics_baselines:
    tongue:
      y0: <seed from O2_analysis PS46 tongue NPZ>
      x0: <seed from O2_analysis PS46 tongue NPZ>
    jaw:
      y0: <seed from O2_analysis PS46 jaw NPZ>
      x0: <seed from O2_analysis PS46 jaw NPZ>
```

Load into `AnimalInfo.kinematics_baselines: dict[str, dict[str, float]]`.
The interpolation module reads the per-animal baseline for the requested
bodypart; if missing, raises with an explicit error naming the
`(animal, bodypart)` pair.

**DECISIONS entry (no MIGRATION_LOG divergence entry).** Record:
"Per-animal, per-bodypart kinematics baselines (`X0`/`Y0`) encoded in
`configs/animals.yaml` `kinematics_baselines:` block, replacing
in-notebook manual editing. Rationale: reproducibility without manual
per-run edits. Per-animal values derived by Priya via plot-inspection
tuning, targeting per-trial baselines close to zero while preserving
cross-session position changes. Faithful port of legacy
`O2_analysis/` outputs."

> **Priya's call:** Confirm the seed-from-legacy-NPZ approach. If any
> per-animal baselines are not recorded in the legacy NPZs (e.g., the
> data-repair sessions where the legacy run was aborted mid-edit),
> call them out now so CC can STOP-and-ask early.

### 3.2 `AnimalInfo.exclusions` schema extension — scope: Phase 7-pre, not 7a

**Cross-phase schema change.** Extend `AnimalInfo.exclusions` to carry
an `applies_to: [dlc | spout_behavior | ...]` list on each exclusion
entry, so sessions can be marked excluded from DLC analyses without
also excluding them from spout behavior (or vice versa). The current
`applies_to` field takes bodypart strings like `"tongue"` / `"jaw"` —
this extension broadens the vocabulary to also include instrument /
phase tags (`dlc`, `spout_behavior`) so one exclusion entry can
cleanly scope to a whole analysis pipeline.

**Scope this as its own mini-PR (Phase 7-pre)** before 7a-impl starts.
Touches: `AnimalInfo` loader, `is_excluded()` signature + all call
sites in `src/stroke_orofacial/spout_behavior/`, `configs/animals.yaml`
(backfill existing exclusions with explicit `applies_to`).

**Exclusions to add once schema lands:**

- PS51 2025-05-17 — `applies_to: [dlc]`
  reason: missing camera data
- PS51 2025-04-26 — `applies_to: [dlc, spout_behavior]`
  reason: sham rose bengal administration caused delayed licking
- PS54 2025-04-26 — `applies_to: [dlc, spout_behavior]`
  reason: sham rose bengal administration caused delayed licking
- PS55 2025-04-27 — `applies_to: [dlc, spout_behavior]`
  reason: sham rose bengal administration caused delayed licking
- PS55 2025-04-28 — `applies_to: [dlc, spout_behavior]`
  reason: experimenter error caused inaccurate reward delivery

**Pre-schema task.** Audit existing `AnimalInfo.exclusions` call sites
+ `configs/animals.yaml` entries. Backfill existing exclusions with
explicit `applies_to` (likely most are `[spout_behavior]` historically;
verify per-entry). **Silent default-flip is not acceptable** — any
existing exclusion whose current behavior would change under the new
schema must be migrated with an explicit `applies_to` marker preserving
its current effective scope.

**Sweep tongue Cell 23** + any other DLC-bodypart notebooks for
implicit date-skipping patterns beyond the jaw `EXCLUDE_DATES` dict
(e.g., `if (mouse, date) in SKIP_SET: continue`, hardcoded KEY literal
guards). Report findings before schema design finalizes so the
7-pre PR captures every implicit exclusion in one sweep rather than
surfacing them one-at-a-time during 7a/7b/7c impl.

**Design concern for 7-pre (do not decide here — surface to the 7-pre
implementer).** Broadening `applies_to` to mix bodypart strings
(`tongue`, `jaw`) with instrument/phase tags (`dlc`,
`spout_behavior`) in a single flat list creates a namespace-collision
ambiguity: what does `applies_to: [tongue, dlc]` mean — exclude the
tongue DLC pipeline only, or exclude all tongue analysis AND all DLC
analysis? The current `is_excluded(session_date, analysis_type)`
signature takes a single string, which papers over the ambiguity at
check time but makes the configured intent unclear. The 7-pre PR
should choose one of three clean shapes and document the rationale:

1. **Rename + split:** two separate lists,
   `applies_to_phases: [dlc, spout_behavior]` +
   `applies_to_bodyparts: [tongue, jaw]`, AND-combined at check time.
2. **Nested structure:**
   `applies_to: {phases: [dlc], bodyparts: [tongue]}` — single field,
   two sub-keys.
3. **Namespaced tags:** flat list with dotted keys,
   `applies_to: [dlc.tongue, dlc.jaw, spout_behavior]` — semantically
   unambiguous, single field.

Each option carries migration cost (the existing `applies_to: ["all"]`
/ `applies_to: ["tongue"]` entries need translation). The 7-pre PR's
design phase decides; this brief only flags the collision risk so the
7-pre implementer doesn't walk into it mid-coding.

### 3.3 Bodypart-parametric constants under `dlc_kinematics.<bodypart>:`

Bodypart-parametric interpolation constants (`X_RANGE_PM`, `LK_THR`,
`N_NEIGH`, `neighbor_ms`, `max_gap_ms`, `interp_n_side`,
`require_bracketed_by_hilk`, `x_range_source`, `center_mode`) configured
under `dlc_kinematics.<bodypart>.interpolation` — **full YAML in §7**
(the authoritative single source of truth for the `dlc_kinematics:`
config section).

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
{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS{NN}/PS{NN}_{bodypart}_kinematics/processed_interpolated_data/{center_mode}/PS{NN}_{YYYYMMDD}_cam2_{bodypart}_interp_v5p3.npz
```

with `{center_mode}` ∈ {`centered_spout_midpoint` for tongue,
`centered_eye_midpoint` for jaw} and `{bodypart}` ∈ {`tongue`, `jaw`}.
Each legacy NPZ additionally carries its own `X0` / `Y0` keys — this
is the authoritative seed for per-animal baselines in
`configs/animals.yaml` (§3.1).

**Parity set (14 sessions).** Chosen to span baseline + post-stroke
across all three per-animal-baseline groups plus stress the degenerate
paths in the interpolation module.

*Primary set (9 sessions, routine-case parity):*
- PS46: 20250307, 20250310, 20250313
- PS54: 20250506, 20250509, 20250512
- PS55: 20250501, 20250504, 20250507

*Stress-test set (3 sessions, little-to-no licking):* exercises the
degenerate-pool path — few or zero reward events means
`_build_reward_aligned_pool_mask` returns sparse masks, which in turn
stresses the PCHIP context-bracketing logic (fewer hi-lk samples
surrounding each gap; higher probability of hitting the linear
fallback or the `REQUIRE_BRACKETED_BY_HILK=True` rejection path).
- PS51: 20250430
- PS54: 20250501
- PS55: 20250502

*Later post-stroke set (2 sessions, recovery-period drift):* catches
drift patterns that only emerge well after the stroke — camera settling
+ baseline slow-drift + any per-animal recovery trajectory.
- PS54: 20250607
- PS55: 20250607

**Tolerances.**
- `x_final`, `y_final` — `atol=1e-6` element-wise
- `X0`, `Y0` — exact match (these are the per-animal config values;
  must match the NPZ-stored baselines)
- `fps`, `n_frames` — exact match

**scipy-version note.** PCHIP interpolation is implementation-dependent
across scipy versions (bugfixes / numerical-stability tweaks to the
cubic-Hermite constructor have landed historically). The parity script
asserts `scipy.__version__` matches the legacy-era scipy version.
Record the legacy-era scipy version from the legacy notebook's import
cell (likely visible in tongue Cell 1 / jaw Cell 1); pin the version in
the parity script header. `atol=1e-6` holds for scipy-version-matched
runs. If Priya explicitly accepts running parity under a newer scipy,
widen to `atol=1e-4` and log the scipy-version drift in DECISIONS.

**Parity script location.**
`tests/scripts/parity_phase7a_interpolation.py PS46 20250307 tongue`.
Invoked as part of 7a-impl sign-off, not as a pytest fixture (real-data
reads from MICROSCOPE mount).

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
      x0: "median_of_y_percentile_subset"   # see Knob 3 — not an independent percentile
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
      x0: "median_of_y_percentile_subset"   # see Knob 3 — not an independent percentile
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
- `test_parquet_schema` — emitted parquet has the 7 expected columns +
  the 9 expected file-level attributes.
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
- One-session end-to-end smoke run on an animal/date combo NOT in the
  parity set (e.g., PS50 20250306). Verifies the module runs to
  completion, produces the parquet + (when `emit_qc_bundle=True`) the
  QC NPZ with the expected schema. Catches integration glitches unit
  tests miss (path resolution, animals.yaml loading, SessionManifest
  threading).
- 14-session parity script passes (§6).
- `configs/defaults.yaml` has the `dlc_kinematics:` section (§7).
- `configs/animals.yaml` has `kinematics_baselines:` populated for
  PS46–PS55 (seeded from legacy NPZ `X0`/`Y0` keys per §3.1).
- `AnimalInfo` loads `kinematics_baselines`. The `exclusions`
  `applies_to` schema extension is Phase 7-pre territory (§3.2) — 7a
  depends on it landing first for the PS51/PS54/PS55 DLC exclusions.
- Ruff clean.
- DECISIONS entries: (a) the 4 knob resolutions, (b) per-animal
  per-bodypart baseline encoding rationale. No MIGRATION_LOG
  "deliberate divergence" entry (§3.1 is a faithful port).

---

## 10. Resolutions (2026-04-22 Cowork pass w/ Priya)

1. **Knob 1** — split emit confirmed; `fill_method` column added;
   `baseline_stage` metadata added.
2. **Knob 2** — PCHIP default + linear fallback; config knob in
   `defaults.yaml` with "do not change" comment.
3. **Knob 3** — keep data-driven path; percentile semantics clarified
   (Y0 = lowest *n*'th percentile of trial-aligned pool; X0 = median of
   X in Y-percentile subset, not an independent percentile).
4. **Knob 4** — keep `"lk"` for port parity.
5. **§3.1** — per-animal per-bodypart baselines in `animals.yaml`;
   faithful port, not a bug fix; parity target is
   `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/`.
6. **§3.2** — schema extension routed to Phase 7-pre mini-PR; 5
   exclusions added with correct `applies_to` scoping; sweep tongue
   Cell 23 for implicit date-skipping.
7. **§5** — Option A (pure-bodypart parquet).
8. **§6** — 14 sessions; stress-test (low-licking) + later post-stroke
   additions. scipy-version pin documented.

Brief signed off 2026-04-22, pending Cowork re-pass after edits land.
