# Phase 7a.2 Kickoff — `interpolation.py` implementation + 14-session parity

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.2-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.1 merged 2026-04-22 as PR #81 on branch
`phase/7a.1-kinematics-baselines-parity-scaffold`, tagged
`v7a.1-kinematics-baselines-parity-scaffold`. It landed:

- `configs/animals.yaml` — `kinematics_baselines:` block per animal
  (PS46–PS55), populated from the PR #79 scope-filtered seed table
  (16 STABLE / 0 NHD / 0 INSUFFICIENT).
- `src/stroke_orofacial/animals.py` — `AnimalInfo.kinematics_baselines:
  dict[str, dict[str, float]]` field + `get_kinematics_baseline(bodypart)`
  accessor + strict `_parse_kinematics_baselines()` validator.
- `tests/scripts/parity_phase7a_interpolation.py` — 14-session parity
  harness scaffold (scope filter + legacy-NPZ loader + `atol=1e-6`
  comparator). Consolidated-side `_load_consolidated_trace()` STUBBED
  with `NotImplementedError` — exit code 2 on the 7a.1 smoke runs.
- `docs/phase-7/scipy-pilot-results.md` — second-session stress pilot on
  PS51/20250430 (99.88% NaN-in) confirmed Option A bit-identical (max|Δ|
  = 0.0 on x and y across 906,310 common non-NaN frames). DECISIONS
  2026-04-22 caveat 1 resolved.

Phase 7a.2 is **the single focused PR that writes the interpolation
module code**. Everything structural is in place; this PR fills in the
one missing piece: `src/stroke_orofacial/dlc_kinematics/interpolation.py`
(currently absent from the module directory — `__init__.py`, `features.py`,
`filters.py`, `reward_aligned.py` are there; `interpolation.py` is not).

The design brief at `docs/phase-7/interpolation-strategy.md` §10 closed
all 8 knobs on 2026-04-22; the per-animal `(X0, Y0)` baselines are in
`configs/animals.yaml`; the parity harness waits on one stub replacement.
7a.2 ends with a merged PR + tag, cohort-wide bit-identical parity on
the 14-session set, and a smoke run on a non-parity session.

### What 7a.2 delivers end-to-end

1. `configs/defaults.yaml` — new `dlc_kinematics:` block (bodypart-
   parametric constants per §7 of the strategy brief).
2. `src/stroke_orofacial/dlc_kinematics/interpolation.py` — the module
   itself, porting the 7-stage v5p3 pipeline from the vendored tongue
   Cell 23 + jaw Cell 22 into one bodypart-parametric implementation.
3. `src/stroke_orofacial/paths.py` — add an `interpolated_trace(bodypart,
   animal, date)` helper (small surface-area addition; rounds out the
   resolver's public API so downstream 7b/7c can consume it).
4. `tests/test_dlc_interpolation.py` — ~14 unit tests per strategy §8.
5. `tests/scripts/parity_phase7a_interpolation.py` — replace
   `_load_consolidated_trace` stub with the real parquet reader.
6. One-session smoke run on PS50/20250306 (NOT in the 14-session parity
   set per §9, so it catches integration issues the parity set might
   miss).
7. 14-session parity at `atol=1e-6` under consolidated env scipy
   1.17.1 — primary + stress + late-post-stroke.
8. `docs/DECISIONS.md` entry folding the 4 knob resolutions + §5 Option
   A (pure-bodypart parquet) + §3.1 baseline-encoding rationale.
9. `docs/MIGRATION_LOG.md` Phase 7a.2 entry.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five
items. Unlike 7a.1 (config + scaffold only, items 1-2 were N/A), 7a.2
is a full port and must address all five.

1. **Legacy file disambiguation.** Two source files, both already
   vendored under `docs/legacy_snippets/` in PR #79 with full
   3-tier-rule provenance headers:
   - `tongue_cell23_interp_v5p3.py` — Cell 23 of
     `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
     (SHA256 `41f54f0d04...`, 763 lines).
   - `jaw_cell22_interp_v5p3.py` — Cell 22 of
     `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
     (SHA256 `a9277879...`, 755 lines).

   The vendored headers document sibling files (distinct-scope
   notebooks like `DLC_build-parquet_reward-aligned_*`) that are NOT
   ports. No new legacy-file discovery required in 7a.2; trust the
   PR #79 disambiguation.

2. **Dead code identification.** Inside both Cell 23 and Cell 22,
   classify each block:
   - **Production (port):** `compute_session_x_range`, `_fill_nan_with`,
     `interp_small_gaps_method`, `_build_reward_aligned_pool_mask`,
     `process_one_session`'s 7-stage sequence (raw → xrange → thr →
     drop → interp → interp_filled → final), baseline computation
     (forced path + data-driven path).
   - **Exploratory (do NOT port):** plot-interpolation-steps QC cells
     (tongue Cell 29, jaw Cell 28 — inside the same notebook as the
     cells being vendored, not inside the vendored cells themselves).
     The interp-QC arrays (`xrange`, `thr`, `drop`, `interp`,
     `interp_filled`) are preserved in the optional `.qc.npz` sidecar
     per Knob 1 split-emit decision, NOT as interactive plot cells.
   - **Deprecated (do NOT port):** N/A — the vendored cells are
     already the canonical v5p3 under 3-tier-rule disambiguation.
   - **Ambiguous (stop-and-ask if hit):** `DATE_START`/`DATE_END`
     per-animal hardcoded literals at lines ~108–109 of tongue Cell 23
     — these are the legacy's way of ad-hoc scope-narrowing. In the
     consolidated pipeline that job is handled by `animals.yaml
     sessions.{start, end}` via `SessionManifest`. Port behavior: the
     module reads scope from `AnimalInfo`, not from module-level
     constants. If the notebook has additional ad-hoc date-skip
     patterns beyond the `EXCLUDE_DATES` dict (Phase 7-pre's
     `AnimalInfo.exclusions` schema already covers that), STOP and
     ask before inventing new schema.

3. **Sub-phase breakdown.** 7 commits (6 tasks + a kickoff-commit),
   estimated line counts:
   - Commit 1 (Task 0 bundled with preflight): this kickoff doc.
   - Commit 2 (Task 1): `configs/defaults.yaml` `dlc_kinematics:`
     block (~45 YAML lines). `PathResolver.interpolated_trace()` + 1
     unit test (~30 lines).
   - Commit 3 (Task 2): `src/stroke_orofacial/dlc_kinematics/
     interpolation.py` (~550–750 lines across the 7 stages + module
     API + `InterpolationResult` dataclass). Bodypart-parametric, one
     module, two entry points (`tongue`, `jaw`) — ratio-of-sharing
     confirmed during classification (§1 of the strategy brief: "same
     7-stage control flow, differ only in bodypart-parametric
     constants"). `src/stroke_orofacial/dlc_kinematics/__init__.py`
     export of new public symbols.
   - Commit 4 (Task 3): `tests/test_dlc_interpolation.py` (~350–450
     lines, 14 unit tests per strategy §8 + helper fixtures).
   - Commit 5 (Task 4): `tests/scripts/parity_phase7a_interpolation.py`
     — replace `_load_consolidated_trace` stub with real parquet
     reader (~25 lines swapped; everything else stays). PS50/20250306
     smoke run + 14-session parity results recorded in the
     stop-and-report (not committed).
   - Commit 6 (Task 5): `docs/DECISIONS.md` + `docs/MIGRATION_LOG.md`
     entries.
   - Commit 7 (Task 6): PR open + tag post-merge.

4. **Parity strategy.** Strategy brief §6 locks this: legacy NPZs at
   `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/
   {animal}_{bodypart}_kinematics/processed_interpolated_data/
   {center_mode}/{animal}_{date}_cam2_{bodypart}_interp_v5p3.npz`;
   14-session set = 9 primary (PS46/PS54/PS55 × 3 dates each) + 3
   stress (PS51/20250430, PS54/20250501, PS55/20250502) + 2 late
   post-stroke (PS54/20250607, PS55/20250607), run across both
   bodyparts = 28 comparisons; `atol=1e-6` element-wise on `x_final`/
   `y_final`; exact match on `X0/Y0/fps/n_frames`. Consolidated env
   scipy 1.17.1 per Option A (bit-identical to legacy 1.15.1 across
   both pilots). The harness already enforces all of the above; 7a.2
   just wires the consolidated-side loader.

   **Acceptance:** all 28 comparisons return `status = pass` (or, for
   sessions where the legacy NPZ is genuinely missing on MICROSCOPE —
   7a.1 observed 2/28 such cases at PS54/20250512 — `status =
   skip_missing` is tolerated and reported but does not block merge).
   Any `status = fail` at any session → STOP and report.

5. **Hardcoded constants.** Every bodypart-parametric constant lands
   in `configs/defaults.yaml` under `dlc_kinematics.<bodypart>.*` per
   strategy brief §7. No numeric literals inside `interpolation.py`
   that vary per bodypart or per animal. The module reads:
   - Per-bodypart constants (x_range_pm, lk_thr, n_neigh, etc.) from
     `params["dlc_kinematics"][bodypart][...]`.
   - Per-animal `(X0, Y0)` from
     `animal_info.get_kinematics_baseline(bodypart)` (delivered by
     7a.1).
   - Static top-level constants — the method names `pchip` / `linear`
     — are OK to embed as string literals inside the module because
     they name a fixed set of behaviors, not a tunable parameter.
     They are still surfaced in `defaults.yaml` under an explicit "do
     not change without DECISIONS entry" comment per Knob 2.

---

## Execute on a new feature branch

Branch name: `phase/7a.2-interpolation-impl`
PR base: `main`
Tag on merge: `v7a.2-interpolation-impl`

---

### Preflight

1. Read `CLAUDE.md` in full. All rules apply.
2. Environment activation:
   ```bash
   conda activate stroke_orofacial
   which python                              # must print a path under .conda/envs/stroke_orofacial/
   python -c "import stroke_orofacial"
   python -c "import scipy; print(scipy.__version__)"   # must print 1.17.1
   ```
3. `pytest --collect-only` must complete without import errors
   (CLAUDE.md gate). Capture the "N tests collected" count for the
   pre-check.
4. Branch setup from main:
   ```bash
   git checkout main
   git pull origin main
   git branch --show-current                 # must print: main
   git log --oneline -5                      # confirm PR #81 merge commit (98e6ccd) is in history
   git tag --list | tail -5                  # confirm v7a.1-kinematics-baselines-parity-scaffold present
   git checkout -b phase/7a.2-interpolation-impl
   git branch --show-current                 # must print: phase/7a.2-interpolation-impl
   ```
5. MICROSCOPE UNC reachability (needed for task 4 parity run):
   ```powershell
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics\processed_interpolated_data\centered_spout_midpoint\PS46_20250307_cam2_tongue_interp_v5p3.npz"
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_jaw_kinematics\processed_interpolated_data\centered_eye_midpoint\PS46_20250307_cam2_jaw_interp_v5p3.npz"
   # both must print True
   ```
   If either False — STOP and ask Priya before task 4. (Tasks 1–3 are
   pure-Python; they do not require MICROSCOPE.)
6. Interpolation module directory is empty as expected:
   ```bash
   ls src/stroke_orofacial/dlc_kinematics/
   # expect: __init__.py features.py filters.py reward_aligned.py
   # interpolation.py MUST be absent — if present, STOP (branch dirty or concurrent work).
   ```
7. Commit the kickoff doc itself as commit 1 of this branch (matches
   the 7a.1 in-branch kickoff-provenance pattern):
   ```bash
   git status                                # expect: docs/prompts/phase-7a.2-kickoff.md untracked
   git add docs/prompts/phase-7a.2-kickoff.md
   git commit -m "docs(prompts): Phase 7a.2 kickoff"
   git push -u origin phase/7a.2-interpolation-impl
   ```

---

### Task 1 — `configs/defaults.yaml dlc_kinematics:` block + `PathResolver.interpolated_trace()`

**Goal.** Land the bodypart-parametric constants so `interpolation.py`
(Task 2) reads them as a first-class config; add the output-path
helper the module will write to.

#### 1a. Add `dlc_kinematics:` block to `configs/defaults.yaml`

Per strategy brief §7 (copied here verbatim — if the YAML in the brief
and the YAML in this kickoff diverge, the brief is canonical):

```yaml
# --- DLC kinematics (Phase 7a.2) -----------------------------------------
# Bodypart-parametric constants for the v5p3 interpolation pipeline.
# Per-animal (X0, Y0) baselines live in configs/animals.yaml under
# each animal's kinematics_baselines: block (seeded PR #81, 7a.1).
#
# DO NOT change interpolation_method or interpolation_fallback without
# a DECISIONS entry — see 2026-04-22 Knob-2 resolution.
dlc_kinematics:
  interpolation_version: v5p3
  interpolation_method: pchip
  interpolation_fallback: linear
  tongue:
    center_mode: centered_spout_midpoint
    interpolation:
      x_range_pm: 150.0
      x_range_source: lk          # keep "lk" for port parity (Knob 4)
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
      x0: "median_of_y_percentile_subset"
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
      x0: "median_of_y_percentile_subset"
```

Place the block after the existing top-level sections (match the file
ordering — `spout_behavior:` comes before alphabetically, so insert
after it). Load-time parsing is via the existing `load_defaults()`
pattern — no parser extension needed if the module reads the nested
dict directly.

#### 1b. Add `PathResolver.interpolated_trace()` helper

In `src/stroke_orofacial/paths.py`, add (near `pipeline_outputs()`):

```python
def interpolated_trace(
    self,
    bodypart: str,
    animal: str,
    date: datetime.date,
    *,
    variant: str = "parquet",
) -> Path:
    """Return the output path for a Phase 7a interpolated-trace artifact.

    E.g. ``<outputs>/dlc_analysis/interpolated_traces/tongue/PS46/20250307.parquet``

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
    animal : str
        Animal identifier (e.g. "PS46").
    date : datetime.date
    variant : {"parquet", "qc_npz"}
        "parquet" → canonical output (always emitted).
        "qc_npz"  → optional QC sidecar (emitted when
                    ``emit_qc_bundle=True`` is passed to
                    ``build_interpolated_trace``).

    Parent directory is created eagerly. Mirrors ``pipeline_outputs``'s
    ``output_root`` test-override behavior.
    """
    date_str = date.strftime("%Y%m%d")
    ext = {"parquet": "parquet", "qc_npz": "qc.npz"}[variant]
    out = (
        self.pipeline_outputs(subdir="dlc_analysis")
        / "interpolated_traces"
        / bodypart
        / animal
        / f"{date_str}.{ext}"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
```

#### 1c. Tests

Add to `tests/test_paths.py` (extend existing file; do NOT create a
new test file):

- `test_interpolated_trace_parquet_path` — `PathResolver(output_root=
  tmp_path).interpolated_trace("tongue", "PS46", date(2025, 3, 7))`
  returns `tmp_path / "dlc_analysis/interpolated_traces/tongue/PS46/
  20250307.parquet"`; parent directory exists after the call.
- `test_interpolated_trace_qc_npz_variant` — same, `variant="qc_npz"`
  returns path ending in `20250307.qc.npz`.
- `test_interpolated_trace_invalid_variant_raises` — `variant="foo"`
  raises `KeyError`.

#### 1d. Run tests + ruff

```bash
pytest tests/test_paths.py -v
pytest
ruff check src/stroke_orofacial/paths.py tests/test_paths.py configs/defaults.yaml
```

#### 1e. Commit

```bash
git add configs/defaults.yaml src/stroke_orofacial/paths.py tests/test_paths.py
git diff --cached --stat
git commit -m "feat(config,paths): dlc_kinematics defaults + interpolated_trace() resolver"
git push
```

**STOP and report to Priya:**
- diff of `configs/defaults.yaml` showing the new `dlc_kinematics:`
  block,
- new-tests count + full-suite pass count,
- any surprise in the defaults.yaml merge (e.g., YAML indentation
  collision).

---

### Task 2 — `src/stroke_orofacial/dlc_kinematics/interpolation.py` port

**Only run Task 2 after Priya acknowledges the Task 1 report.**

**Goal.** Port the 7-stage v5p3 pipeline from vendored tongue Cell 23 +
jaw Cell 22 into one bodypart-parametric module.

#### 2a. Read the vendored cells end-to-end

Before touching the module, read both vendored files in full:

```bash
wc -l docs/legacy_snippets/tongue_cell23_interp_v5p3.py  # expect 763
wc -l docs/legacy_snippets/jaw_cell22_interp_v5p3.py     # expect 755
```

Build a mental map of:
- the 7-stage control flow (raw → xrange → thr → drop → interp →
  interp_filled → final),
- which helpers are pure (`compute_session_x_range`, `_fill_nan_with`,
  `interp_small_gaps_method`, `_build_reward_aligned_pool_mask`) —
  these become private functions in `interpolation.py`,
- which top-level constants are bodypart-parametric — these read from
  `params["dlc_kinematics"][bodypart]`,
- which top-level constants are per-animal — these read from
  `animal_info.get_kinematics_baseline(bodypart)`,
- where the legacy `REQUIRE_BRACKETED_BY_HILK=True` / `N_NEIGH` /
  `INTERP_N_SIDE` gates fire.

Do not copy-paste. Transcribe the algorithm, test the transcription
with the unit tests in Task 3, and verify parity in Task 4. The
vendored files stay untouched (`# ruff: noqa; # fmt: off`) — they are
read-only reference only.

#### 2b. Module structure

Create `src/stroke_orofacial/dlc_kinematics/interpolation.py` with this
shape (signatures locked by strategy brief §4):

```python
"""Phase 7a.2 — bodypart-parametric v5p3 interpolation.

Ports tongue Cell 23 + jaw Cell 22 from
``docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py``
into a single module with two entry points.

Public API
----------
``build_interpolated_trace(manifest, bodypart, resolver, params, *, overwrite, emit_qc_bundle)``
    Session-level driver. Writes canonical parquet + optional QC NPZ.
``build_interpolated_trace_by_animal_date(animal, date, bodypart, resolver, **kwargs)``
    Convenience wrapper for (animal, date) callers.
``InterpolationResult``
    Dataclass carrying the 7 stages + final traces + metadata.

Knob decisions (2026-04-22 DECISIONS — see interpolation-strategy.md §10)
------------------------------------------------------------------------
- Knob 1: split-emit (canonical parquet + optional .qc.npz).
- Knob 2: PCHIP + linear fallback; not a runtime-tunable knob.
- Knob 3: data-driven baseline path preserved; forced path is default.
- Knob 4: x_range_source="lk" for port parity.
- §5 Option A: pure-bodypart parquet; no side labels.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.interpolate import PchipInterpolator

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

INTERPOLATION_VERSION = "v5p3"
_FILL_METHOD_ENUM = {"none": 0, "pchip": 1, "linear": 2, "baseline": 3}


@dataclass
class InterpolationResult:
    # 7-stage arrays (all length n_frames)
    x_raw: np.ndarray
    y_raw: np.ndarray
    lk_raw: np.ndarray
    x_xrange: np.ndarray
    y_xrange: np.ndarray
    x_thr: np.ndarray
    y_thr: np.ndarray
    x_drop: np.ndarray
    y_drop: np.ndarray
    x_interp: np.ndarray
    y_interp: np.ndarray
    x_interp_filled: np.ndarray
    y_interp_filled: np.ndarray
    x_final: np.ndarray
    y_final: np.ndarray
    # provenance masks
    is_interp_fill: np.ndarray   # bool; True where PCHIP/linear fill fired
    is_baseline_fill: np.ndarray # bool; True where _fill_nan_with(X0/Y0) fired
    fill_method: np.ndarray      # int8; _FILL_METHOD_ENUM categorical
    # scalar metadata
    X0: float
    Y0: float
    fps: float
    n_frames: int
    center_mode: str
    baseline_stage: str
    interpolation_version: str = INTERPOLATION_VERSION
    bodypart: str = ""
    animal: str = ""
    date: dt.date | None = None


def _stage_xrange(x, y, lk, *, x_range_pm, x_range_source, lk_thr):
    """Stage 1 — drop outliers outside median(x[lk>=thr]) ± x_range_pm."""
    ...


def _stage_thr(x, y, lk, *, lk_thr):
    """Stage 2 — drop samples with likelihood below lk_thr."""
    ...


def _stage_drop(x, y, lk, *, lk_thr, n_neigh, neighbor_ms, fps):
    """Stage 3 — drop isolated hi-lk points (fewer than n_neigh neighbors)."""
    ...


def _stage_interp(
    x, y, hi_mask, *,
    max_gap_f, require_bracketed_by_hilk,
    interp_n_side, interp_min_total_context,
    method, fallback,
):
    """Stage 4 — PCHIP-with-linear-fallback, gap-bounded, bracket-aware."""
    ...


def _stage_interp_filled(x, y, X0, Y0):
    """Stage 5 — fill remaining NaNs with per-animal (X0, Y0) baselines."""
    ...


def _stage_final(x, y, X0, Y0):
    """Stage 6 — subtract baselines → zero-centered x_final, y_final."""
    return x - X0, y - Y0


def _compute_reward_aligned_pool_mask(
    n_frames: int, reward_centers_cam: np.ndarray, fps: float, win_ms,
) -> np.ndarray:
    """Bool mask over frames inside any post-reward window (for baseline calc)."""
    ...


def _compute_baseline_forced(animal_info: AnimalInfo, bodypart: str) -> tuple[float, float]:
    """Read per-animal (x0, y0) from AnimalInfo.kinematics_baselines."""
    baseline = animal_info.get_kinematics_baseline(bodypart)
    return float(baseline["x0"]), float(baseline["y0"])


def _compute_baseline_data_driven(
    x, y, lk, pool_mask, *,
    y0_lk_thr, y0_percentile, require_finite_x,
) -> tuple[float, float]:
    """Data-driven baseline per Knob-3 semantics.

    Y0 = median(Y) among frames in pool_mask with lk >= y0_lk_thr,
         restricted to the lowest y0_percentile'th percentile of Y.
    X0 = median(X) among the SAME frames (conditional median, NOT an
         independent X percentile — see 2026-04-22 DECISIONS Knob 3).
    """
    ...


def _interpolate_bodypart_core(
    df: pd.DataFrame,
    bodypart: str,
    center_mode: str,
    params: dict,
    reward_centers_cam: np.ndarray,
    animal_info: AnimalInfo | None = None,
) -> InterpolationResult:
    """Stage-by-stage v5p3 interpolation on a single session.

    Pure function — no I/O. Reads DLC columns from ``df`` (columns:
    ``{bodypart}_x``, ``{bodypart}_y``, ``{bodypart}_likelihood``; see
    Phase 4.5-lite centered-parquet schema). Returns an
    :class:`InterpolationResult` with all 7 stages + metadata.
    """
    ...


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
      - ``{outputs}/dlc_analysis/interpolated_traces/{bodypart}/{animal}/{date}.parquet``
        (always).
      - ``...{date}.qc.npz`` (only if ``emit_qc_bundle=True``).

    Returns the parquet Path, or None if ``overwrite="skip"`` and the
    parquet already exists.

    Raises
    ------
    ValueError
        If ``bodypart`` not in {"tongue", "jaw"}.
    KeyError
        If ``animal_info.kinematics_baselines`` lacks ``bodypart``
        (propagated from ``AnimalInfo.get_kinematics_baseline``).
    """
    ...


def build_interpolated_trace_by_animal_date(
    animal: str,
    date: dt.date,
    bodypart: Literal["tongue", "jaw"],
    resolver: PathResolver,
    **kwargs,
) -> Path | None:
    """Convenience wrapper — builds manifest internally.

    Equivalent to
      ``build_interpolated_trace(build_manifest(animal, date, resolver, get_animal(animal), analysis_type="kinematics"), bodypart, resolver, **kwargs)``
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info, analysis_type="kinematics",
    )
    return build_interpolated_trace(manifest, bodypart, resolver, **kwargs)
```

Export the public symbols from
`src/stroke_orofacial/dlc_kinematics/__init__.py`:

```python
from stroke_orofacial.dlc_kinematics.interpolation import (
    InterpolationResult,
    build_interpolated_trace,
    build_interpolated_trace_by_animal_date,
)

__all__ = [
    "InterpolationResult",
    "build_interpolated_trace",
    "build_interpolated_trace_by_animal_date",
    # ... existing features/filters/reward_aligned exports if already present
]
```

Check `__init__.py` for existing exports before editing — the 7a.2
module adds to whatever is there, does not replace it.

#### 2c. Parquet schema (per strategy brief §2 Knob 1)

The canonical parquet carries **one row per camera frame** with
columns:
- `frame_idx` (int64)
- `x_final` (float64)
- `y_final` (float64)
- `likelihood_raw` (float64)
- `is_interp_fill` (bool)
- `is_baseline_fill` (bool)
- `fill_method` (int8, enum per `_FILL_METHOD_ENUM`)

File-level metadata (written to parquet file metadata; read back with
`pyarrow.parquet.ParquetFile(path).metadata.metadata`):
- `X0`, `Y0`, `fps`, `n_frames`, `center_mode`, `baseline_stage`,
  `interpolation_version`, `bodypart`, `animal`, `date`.

Write via `pyarrow.Table.from_pandas(df)` + `pq.write_table(table,
path, compression="snappy")`; attach metadata dict via
`schema.with_metadata({k.encode(): str(v).encode() for ...})`.

#### 2d. QC NPZ schema (when `emit_qc_bundle=True`)

Sidecar `.qc.npz` carries the intermediate arrays useful for legacy-
style QC inspection (tongue Cell 29 / jaw Cell 28 patterns):
`x_xrange, y_xrange, x_thr, y_thr, x_drop, y_drop, x_interp, y_interp,
x_interp_filled, y_interp_filled`, plus `X0, Y0, fps, n_frames,
reward_centers_cam, baseline_stage, interpolation_version`.

#### 2e. Ruff + targeted unit tests (smoke pass)

```bash
ruff check src/stroke_orofacial/dlc_kinematics/interpolation.py src/stroke_orofacial/dlc_kinematics/__init__.py
# Module imports cleanly (catches syntax + missing import errors before tests):
python -c "from stroke_orofacial.dlc_kinematics import build_interpolated_trace, InterpolationResult; print('ok')"
```

Unit tests come in Task 3. Task 2 ends at a clean module that imports
and passes ruff.

#### 2f. Commit

```bash
git add src/stroke_orofacial/dlc_kinematics/interpolation.py src/stroke_orofacial/dlc_kinematics/__init__.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): v5p3 interpolation.py port (7-stage tongue+jaw)"
git push
```

**STOP and report to Priya:**
- line count of `interpolation.py`,
- list of private helpers + their line-count estimate,
- any unresolved algorithmic questions from the vendored cells
  (ambiguous-classification items per Plan-shape §2 above),
- confirmation that the module imports cleanly + ruff passes.

---

### Task 3 — Unit tests per strategy §8

**Only run Task 3 after Priya acknowledges the Task 2 report.**

**Goal.** Pin every stage of the algorithm + the module API surface so
later edits cannot silently regress.

Create `tests/test_dlc_interpolation.py`. Every test uses
`PathResolver(output_root=tmp_path)` — do NOT write to the real
`stroke_orofacial_pipeline_outputs/` tree (CLAUDE.md testing
conventions).

#### 3a. Test list (14 unit tests per strategy §8)

1. `test_stage_xrange_drops_outliers` — `_stage_xrange` removes
   expected samples outside `median(x[lk>=thr]) ± x_range_pm`.
2. `test_stage_thr_drops_low_likelihood` — `_stage_thr` NaNs out
   samples below `lk_thr`, preserves samples at or above.
3. `test_stage_drop_isolated_hilk` — `_stage_drop` drops a hi-lk
   sample with 0 or 1 hi-lk neighbors in the `neighbor_ms` window,
   preserves it with `n_neigh` or more neighbors. Parameterize over
   edge cases (0, 1, n_neigh-1, n_neigh, N).
4. `test_stage_interp_fills_short_gaps` — `_stage_interp` fills a gap
   of length below `max_gap_ms` via PCHIP with `atol=1e-10` against a
   hand-computed PCHIP reference.
5. `test_stage_interp_preserves_long_gaps` — gaps above `max_gap_ms`
   stay NaN (no fill).
6. `test_stage_interp_filled_baseline_substitution` — `_stage_
   interp_filled` replaces remaining NaNs with the supplied
   `(X0, Y0)`.
7. `test_stage_final_baseline_subtraction` — `_stage_final` returns
   `(x - X0, y - Y0)`.
8. `test_bodypart_dispatch_tongue` — `_interpolate_bodypart_core`
   reads `tongue_x`, `tongue_y`, `tongue_likelihood` columns and
   applies the tongue parameter set.
9. `test_bodypart_dispatch_jaw` — same for jaw, with the jaw
   parameter set (different `x_range_pm`, `n_neigh`, `max_gap_ms`).
10. `test_force_baseline_from_animal_info` — with
    `baseline.force=true`, the module reads
    `AnimalInfo.get_kinematics_baseline(bodypart)` and raises
    `KeyError` when absent.
11. `test_excluded_session_returns_none` — when the session is excluded
    under `applies_to: [dlc]` (Phase 7-pre schema), `build_
    interpolated_trace` returns None without writing output.
12. `test_parquet_schema` — emitted parquet has the 7 columns per §2c
    above with correct dtypes; file-level metadata carries the 10
    required keys.
13. `test_overwrite_skip_respects_existing` — with `overwrite="skip"`
    and the parquet already on disk, returns the existing Path
    without overwriting; with `overwrite="force"`, overwrites.
14. `test_emit_qc_bundle_emits_npz` — with `emit_qc_bundle=True`, the
    companion `.qc.npz` is written at the path returned by
    `resolver.interpolated_trace(..., variant="qc_npz")` with the
    expected array keys.

Additional helper fixtures: `_make_synthetic_df(n_frames, nan_frac,
...)` for building synthetic DLC dataframes with controllable NaN
patterns; `_make_minimal_manifest(animal, date, tmp_path)` for
building a SessionManifest with a tmp_path-backed resolver.

#### 3b. Run + commit

```bash
pytest tests/test_dlc_interpolation.py -v            # 14 pass
pytest                                                # full suite, no regressions
ruff check tests/test_dlc_interpolation.py

git add tests/test_dlc_interpolation.py
git diff --cached --stat
git commit -m "test(dlc_interpolation): 14 unit tests per strategy §8"
git push
```

**STOP and report to Priya:**
- the 14 test-name list with pass status,
- full-suite pass/skip/fail counts,
- any synthetic-fixture implementation surprise (e.g., a hand-computed
  PCHIP reference was non-trivial to stabilize — did you pin via
  `atol=1e-10` or did it require `atol=1e-8`?).

---

### Task 4 — Parity wire-in, PS50/20250306 smoke, 14-session parity

**Only run Task 4 after Priya acknowledges the Task 3 report.**

**Goal.** Flip the parity-harness stub to the real reader; confirm the
module runs end-to-end on a non-parity session; confirm bit-identity
vs legacy on all 14 parity sessions × 2 bodyparts.

#### 4a. Replace `_load_consolidated_trace` stub

In `tests/scripts/parity_phase7a_interpolation.py`, replace the stub:

```python
def _load_consolidated_trace(animal: str, date: dt.date, bodypart: str) -> dict:
    """Load x_final, y_final, X0, Y0 from the consolidated-pipeline parquet."""
    from stroke_orofacial.paths import PathResolver
    import pyarrow.parquet as pq
    import pandas as pd

    resolver = PathResolver()
    path = resolver.interpolated_trace(bodypart=bodypart, animal=animal, date=date)
    if not path.exists():
        raise FileNotFoundError(f"Consolidated parquet not found: {path}")
    df = pd.read_parquet(path)
    meta = pq.ParquetFile(path).metadata.metadata
    return {
        "x_final": df["x_final"].to_numpy().astype(float),
        "y_final": df["y_final"].to_numpy().astype(float),
        "X0": float(meta[b"X0"]),
        "Y0": float(meta[b"Y0"]),
        "fps": float(meta[b"fps"]),
        "n_frames": int(meta[b"n_frames"]),
        "path": path,
    }
```

Remove the `NotImplementedError` stub + its 7a.1 comment.

#### 4b. Smoke run on PS50/20250306 (NOT in parity set)

Per strategy §9, run the module on one non-parity session to catch
integration glitches unit tests miss (path resolution, animals.yaml
loading, SessionManifest threading):

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_interpolated_trace_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
for bodypart in ("tongue", "jaw"):
    path = build_interpolated_trace_by_animal_date(
        animal="PS50", date=dt.date(2025, 3, 6), bodypart=bodypart,
        resolver=resolver, overwrite="force", emit_qc_bundle=True,
    )
    print(f"{bodypart}: {path}")
PY
```

Expected: prints both parquet paths; files exist on disk; `.qc.npz`
sidecars exist. Read the parquets back with pandas and confirm the
expected 7 columns + 10 metadata keys are present.

If any error — STOP and report. This smoke is the acceptance gate
for the module being minimally runnable end-to-end.

#### 4c. Run the 14-session parity set

```bash
python tests/scripts/parity_phase7a_interpolation.py --sessions auto | tee /tmp/parity_7a2.log
echo "exit=$?"
```

Expected under Option A (scipy 1.17.1, atol=1e-6):
- exit code `0` (all pass).
- `by_status = {'pass': 28, ...}` or `{'pass': 26, 'skip_missing': 2}`
  if the PS54/20250512 MICROSCOPE gap observed in 7a.1 still holds.
- Per-session `max|Δ|` on x and y all report `0.000e+00` (the
  bit-identical regime confirmed by the two scipy pilots).

If ANY session returns `status = fail`:
- capture the session(s), `max|Δ|`, dim, and which scalar metadata
  mismatched;
- **STOP and report** — do not widen the tolerance, do not advance to
  Task 5. A fail is the signal that the port has a bug; Priya decides
  how to triage.

If a new `skip_missing` appears beyond the PS54/20250512 pattern —
note it but do not block; the harness's `skip_missing` is tolerated
(no MICROSCOPE write has happened).

#### 4d. Build the consolidated cohort outputs (optional, Priya's call)

If Priya asks for the full cohort emit (7a-equivalent of the Phase
6.8a cohort first-emit), run:

```bash
python - <<'PY'
# cohort emit across animals × dates × bodyparts
# (loops over animals.yaml sessions.{start, end})
# ... scripted per Priya's scope (may be out of 7a.2 scope)
PY
```

Otherwise skip this — cohort-emit infrastructure is sized for a
separate mini-phase. 7a.2 acceptance is: module works + parity
passes. Full cohort emit can follow.

#### 4e. Commit

```bash
git add tests/scripts/parity_phase7a_interpolation.py
git diff --cached --stat
git commit -m "feat(parity): wire Phase 7a harness to real consolidated parquet reader"
git push
```

**STOP and report to Priya:**
- PS50/20250306 smoke result (both bodyparts path + file sizes),
- full parity `by_status` count,
- per-session max|Δ| table (28 rows × 2 dims),
- any skip_missing beyond PS54/20250512,
- any fail → STOP AND WAIT for Priya's triage decision before
  advancing.

---

### Task 5 — DECISIONS + MIGRATION_LOG entries

**Only run Task 5 after Task 4 reports all-pass.**

#### 5a. `docs/DECISIONS.md` — Phase 7a.2 entry

Insert a new 2026-04-22 (or current date) entry above the existing
reverse-chronological entries. Use Priya's usual entry format. Content:

```markdown
## 2026-04-2X — Phase 7a.2 interpolation port + Knob resolutions codified

**Context.** Phase 7a.2 ported the v5p3 7-stage interpolation pipeline
(tongue Cell 23 + jaw Cell 22) into
`src/stroke_orofacial/dlc_kinematics/interpolation.py`. The 8 knob
decisions from `docs/phase-7/interpolation-strategy.md` §10 are now
executed in code + config; this entry records them as the standing
architectural baseline for all future edits.

**Decisions enacted.**

1. **Knob 1 — split emit.** Canonical parquet (7 columns per frame +
   10 file-level metadata keys) + optional `.qc.npz` sidecar (7-stage
   intermediate arrays). Parquet is what downstream phases (7b, 7c,
   7e, 7f) consume; QC NPZ is opt-in via `emit_qc_bundle=True`.
2. **Knob 2 — PCHIP with linear fallback.** Interpolation method is
   not a runtime-tunable knob — exposed in `defaults.yaml` with an
   explicit "do not change without DECISIONS entry" comment.
3. **Knob 3 — data-driven baseline path preserved; forced path is
   default.** `baseline.force=true` by default in `defaults.yaml`;
   per-animal `(X0, Y0)` read from `animals.yaml` via
   `AnimalInfo.get_kinematics_baseline(bodypart)`. Data-driven
   semantics clarified: Y0 = lowest `y0_percentile'th` of Y in the
   reward-aligned hi-lk pool; X0 = median of X in the same subset
   (conditional median, NOT an independent X percentile).
4. **Knob 4 — `x_range_source="lk"` for port parity.** Preserves
   bit-identity against legacy NPZs. Revisiting to `"finite"` is a
   post-7a scope change; documented here as the future exit ramp if a
   session's xrange stage is observed to cause false-positive
   rejections.
5. **§5 Option A — pure-bodypart parquet.** No per-reward side labels
   in the interpolated-trace parquet. Side labels enter downstream at
   7b/7c per-trial endpoint modules that re-read reward events from
   Phase 2 `licks_and_rewards/{animal}/{date}.npz` and apply the
   boundary-layer L↔R translation at emit.
6. **§3.1 — per-animal `(X0, Y0)` in `animals.yaml`.** Faithful port
   of the legacy manual-editing protocol, NOT a bug fix; legacy
   `O2_analysis/PS*/...` NPZs carry the actually-used baselines for
   each run. Cohort-wide values seeded in PR #81 (16 STABLE combos).

**Parity verification (14-session set at atol=1e-6).** <PASTE by_status
table from Task 4c run>. Bit-identical on all in-scope sessions under
scipy 1.17.1 — reinforces the two pilot-level confirmations (PR #79
PS46/20250307 + PR #81 PS51/20250430, both max|Δ|=0.0).

**Enforced at.** `configs/defaults.yaml dlc_kinematics:`,
`configs/animals.yaml kinematics_baselines:`,
`src/stroke_orofacial/dlc_kinematics/interpolation.py` module,
`tests/scripts/parity_phase7a_interpolation.py`,
`tests/test_dlc_interpolation.py`.

**Forward implication.** 7b (tongue endpoints), 7c (jaw endpoints +
mismatch classifier), 7e (face-velocity PCs), 7f (PSD) consume
`interpolated_traces/{bodypart}/{animal}/{date}.parquet`. Any future
edit to the 7-stage pipeline that changes `x_final` / `y_final` by
more than atol=1e-6 on any in-scope session requires a DECISIONS
entry documenting the drift and re-running the 14-session parity.
```

#### 5b. `docs/MIGRATION_LOG.md` — Phase 7a.2 entry

Append after the Phase 7a.1 entry:

```markdown
## Phase 7a.2 — `interpolation.py` v5p3 port + cohort parity

**Date:** 2026-04-2X
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.2-interpolation-impl`
**Branch:** `phase/7a.2-interpolation-impl`

**Scope.** The v5p3 7-stage interpolation pipeline ported from
`docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py` into
`src/stroke_orofacial/dlc_kinematics/interpolation.py`. Delivers the
single piece of code that blocked Phases 7b–7f: a bodypart-parametric
pure-function `_interpolate_bodypart_core` wrapped by the session-level
`build_interpolated_trace` writer, emitting a 7-column canonical
parquet and optional `.qc.npz` sidecar.

**What landed.**

1. **`configs/defaults.yaml` `dlc_kinematics:` block.** Bodypart-
   parametric constants per `interpolation-strategy.md` §7 (x_range_pm,
   lk_thr, n_neigh, neighbor_ms, max_gap_ms, interp_n_side,
   require_bracketed_by_hilk, x_range_source, plus baseline knobs).
2. **`PathResolver.interpolated_trace(bodypart, animal, date, *,
   variant)` helper.** Returns
   `{outputs}/dlc_analysis/interpolated_traces/{bodypart}/{animal}/
   {date}.{parquet|qc.npz}`. Mirrors `pipeline_outputs()`'s
   `output_root` override for tests.
3. **`src/stroke_orofacial/dlc_kinematics/interpolation.py`.** <N>-line
   module:
   - `InterpolationResult` dataclass (7 stages × 2 dims + masks +
     metadata).
   - `_stage_xrange`, `_stage_thr`, `_stage_drop`, `_stage_interp`,
     `_stage_interp_filled`, `_stage_final` private helpers.
   - `_compute_reward_aligned_pool_mask`, `_compute_baseline_forced`,
     `_compute_baseline_data_driven` baseline helpers.
   - `_interpolate_bodypart_core` pure-function driver (no I/O).
   - `build_interpolated_trace` session-level writer (parquet + optional
     QC NPZ).
   - `build_interpolated_trace_by_animal_date` convenience wrapper.
4. **14 unit tests in `tests/test_dlc_interpolation.py`.** Covers every
   stage, bodypart dispatch (tongue + jaw), forced/data-driven
   baseline paths, excluded-session skip, parquet schema, overwrite
   semantics, QC NPZ emission.
5. **Parity harness wire-in.** `_load_consolidated_trace` stub in
   `tests/scripts/parity_phase7a_interpolation.py` replaced with the
   real parquet reader; 14-session parity set re-run returns
   `by_status = <PASTE>`. Max|Δ| = 0.0 on every in-scope dim (as
   expected per the two scipy pilots).

**Behavior differences vs. legacy notebooks.**

- Split emit replaces the 7-stage monolithic NPZ (Knob 1). Legacy NPZ
  is preserved on MICROSCOPE read-only; consolidated writes parquet +
  optional QC NPZ to
  `{outputs}/dlc_analysis/interpolated_traces/...`.
- `X0`/`Y0` read from `AnimalInfo.get_kinematics_baseline(bodypart)`
  instead of top-of-notebook literal values. Faithful port — the
  literals were per-animal-edited at run time in the legacy workflow;
  the baselines match the ones actually used for the legacy NPZs.
- No `[all]` exclusion sentinel; `applies_to` extension from Phase
  7-pre (PR #75) means the PS51 2025-05-17 (`[dlc, alignment]`) and
  2025-04-26 (`[dlc, spout_behavior]`) exclusions correctly skip DLC
  runs without blocking spout behavior.
- Otherwise byte-equivalent on the 14-session parity set within
  `atol=1e-6` (actually exact-equal / max|Δ|=0.0 per the cohort-wide
  parity run).

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified (legacy NPZs read-only). Rule 2 — no legacy-repo edits.
Rule 6 — new outputs live under `stroke_orofacial_pipeline_outputs/
dlc_analysis/interpolated_traces/`. Rule 8 — feature branch, tag
pushed post-merge.

**Forward follow-ups for Phase 7b/7c/7e/7f.** Per-trial endpoint
modules read `interpolated_trace(bodypart, animal, date)` and the
`reward_events` sub-table from Phase 2 `licks_and_rewards/...npz`.
Side labels (L/R) are applied at 7b/7c emit via the Phase 6.8
boundary-layer translator per §5 Option A.
```

#### 5c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.2): DECISIONS + MIGRATION_LOG entries"
git push
```

---

### Task 6 — PR + tag

#### 6a. Open the PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.2: interpolation.py v5p3 port + 14-session cohort parity" \
  --body - <<'EOF'
Phase 7a.2 closes the interpolation port that 7a.0 (vendoring + probe)
and 7a.1 (config + scaffold) set up.

## What lands

1. `src/stroke_orofacial/dlc_kinematics/interpolation.py` — v5p3 7-stage
   bodypart-parametric port (tongue Cell 23 + jaw Cell 22) with
   `InterpolationResult`, `_interpolate_bodypart_core` pure-function
   driver, `build_interpolated_trace` writer, and
   `build_interpolated_trace_by_animal_date` convenience wrapper.
2. `configs/defaults.yaml dlc_kinematics:` block per
   interpolation-strategy.md §7 (bodypart-parametric constants).
3. `PathResolver.interpolated_trace(bodypart, animal, date, *, variant)`
   helper rounding out the resolver's API for downstream 7b/7c.
4. `tests/test_dlc_interpolation.py` — 14 unit tests per §8.
5. `tests/scripts/parity_phase7a_interpolation.py` wire-in — stub
   replaced with real reader; 14-session parity set all pass.
6. DECISIONS entry codifying Knobs 1–4 + §5 Option A + §3.1 baseline
   encoding.
7. MIGRATION_LOG Phase 7a.2 entry.

## Parity / tests / ruff

- Full pytest: <PASTE> passed / <PASTE> skipped / 0 failed
  (+14 new tests in test_dlc_interpolation.py).
- Ruff clean on all touched `.py` files.
- Parity harness `--sessions auto` exit code 0;
  by_status = <PASTE>.
- PS50/20250306 smoke run: tongue + jaw parquets written +
  `.qc.npz` sidecars present.
- Max|Δ| on all in-scope dims: 0.000e+00 (bit-identical to legacy
  NPZs, scipy 1.17.1 Option A).

## Tag on merge

`v7a.2-interpolation-impl`

## Not in this PR

- Cohort-wide full emit across all 8 animals × all dates × both
  bodyparts. Scope for a separate mini-phase if Priya wants it; the
  parity gate on the 14-session set is sufficient acceptance for the
  module itself.
- Phase 7b (tongue per-trial endpoints), 7c (jaw per-trial endpoints
  + mismatch classifier), 7e (face-velocity PCs), 7f (PSD) — each is
  its own downstream phase reading the 7a.2 parquets.
EOF
```

#### 6b. Final verification

```bash
# Commits on the branch since main:
git log --oneline origin/main..HEAD
# Expected: 6 commits — kickoff, defaults+paths, interpolation.py,
# unit tests, parity wire-in, DECISIONS+MIGRATION_LOG.

# Touched file summary:
git diff --stat origin/main..HEAD
# Expected paths:
#   docs/prompts/phase-7a.2-kickoff.md            (task 0)
#   configs/defaults.yaml                           (task 1)
#   src/stroke_orofacial/paths.py                   (task 1)
#   tests/test_paths.py                             (task 1)
#   src/stroke_orofacial/dlc_kinematics/interpolation.py        (task 2)
#   src/stroke_orofacial/dlc_kinematics/__init__.py             (task 2)
#   tests/test_dlc_interpolation.py                 (task 3)
#   tests/scripts/parity_phase7a_interpolation.py   (task 4)
#   docs/DECISIONS.md                               (task 5)
#   docs/MIGRATION_LOG.md                           (task 5)

# Ruff + pytest one more time for the PR record:
ruff check .
pytest -q

# After PR merges on main, tag and push:
# git checkout main && git pull
# git tag -a v7a.2-interpolation-impl <merge-sha> -m "Phase 7a.2: v5p3 interpolation port + 14-session parity"
# git push origin v7a.2-interpolation-impl
```

Report to Priya: PR URL, the 6 commit SHAs, ruff + pytest counts,
parity `by_status` + max|Δ| table, PS50/20250306 smoke paths. STOP.
**Do not merge.** Priya reviews, merges from the GitHub UI, then
tags on the merge commit herself.

---

## Constraints (across all 6 tasks)

- **Phase 7a.2 scope is module-implementation + unit tests + parity
  wire-in + docs ONLY.** No Phase 7b/7c/7e/7f endpoint modules in
  this PR. No notebook work. No changes to `configs/animals.yaml`
  (baselines are already seeded per PR #81).
- **Seven commits, not one.** Each task = one commit (except Task 0 /
  preflight, which is bundled with the kickoff commit). Review
  granularity matters for a multi-hundred-line port.
- **Stop-and-report between tasks 1 / 2 / 3 / 4.** Tasks 5 and 6
  chain through only after task 4 reports all-pass on parity.
- **No MICROSCOPE writes.** All MICROSCOPE access is
  `np.load` / `pd.read_parquet` / `Path.glob` only. Consolidated
  outputs go under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/interpolated_traces/`.
- **No force-push.** All pushes are additive to
  `phase/7a.2-interpolation-impl`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit, per CLAUDE.md §"Git discipline" precedent.
- **If the parity harness reports any `status = fail` in Task 4c:**
  STOP. Do not widen the tolerance. Do not write DECISIONS or
  MIGRATION_LOG entries claiming success. Report the failing session
  + max|Δ| + dim + scalar metadata mismatch to Priya; she decides
  whether the port has a bug, whether the legacy NPZ is
  non-canonical, or whether Option A needs revisiting.
- **If a new `skip_missing` pattern appears beyond PS54/20250512:**
  note it and proceed; `skip_missing` does not block merge but
  should be added to the Task 4 report for Priya's awareness.
- **If `interpolation.py` already exists on `main` when the branch
  is cut:** STOP. Either someone else is editing concurrently or
  the branch is stale. Ask Priya before proceeding.
- **Legacy snippets under `docs/legacy_snippets/` stay READ-ONLY.**
  Their `# ruff: noqa` + `# fmt: off` headers preserve byte-identity
  with capture time; do NOT edit, reformat, or lint them.
