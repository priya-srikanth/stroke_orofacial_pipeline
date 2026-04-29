# Phase 7a.4 Kickoff — Cell 50 visual gate + Cell 42 day-binned cross-session traces

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.4-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.3 V3 merged 2026-04-29 as PR #85 on branch
`phase/7a.3-tongue-pertrial-features`, tagged
`v7a.3-tongue-pertrial-features` (merge commit `5063b5e`). It landed:

- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` + 3 sibling
  `_detector.py` / `_angle.py` / `_writers.py` files implementing the
  unified slope detector + 5 cell extractors + atomic 3-file writer.
- Three output products per session: per-frame angle parquet, per-session
  × side licking-dynamics traces parquet, per-trial endpoints JSON.
- Auto-derive `_derive_trial_events_from_spout_behavior` reusing 7a.2's
  alignment infrastructure.
- 4 PathResolver helpers + `detector_per_cell:` / `bout_per_cell:` YAML
  override mechanism.
- 51-test unit suite + 1031-line two-mode parity harness.
- Cohort parity result: Cells 33 + 36 bit-identical (max|Δ| ≤ 1.8e-12);
  Cell 39 ~2% trials with 1-peak CSV-stale residual (accepted);
  Cell 42 numerical-precision drift on per-bin traces (accepted).

**Two carve-outs explicitly deferred from 7a.3 V3 to this phase:**

1. **Cell 50 visual gate.** The 7a.3 V3 acceptance criterion deferred
   the visual comparison against legacy figures at
   `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\
   O2_analysis\PS46\PS46_tongue_kinematics\kinematics_figures\
   centered_spout_midpoint\angle_phase_exploratory\` to a follow-up
   phase. Cell 50 acceptance for 7a.3 was unit-test correctness (9
   tests in `TestCell50Angle` on synthetic geometry) + schema lock.
   Phase 7a.4 closes the visual-comparison gap.
2. **Cell 42 day-binned cross-session traces.** Legacy Cell 42
   emitted both per-session traces (`*_perSessionTraces_*.csv`, ported
   in 7a.3) AND day-binned cross-session aggregation
   (`*_dayBinnedTraces_*.csv`, deferred to 7a.4) using per-animal
   `bin_days` (PS46–50: 2; PS51/54/55: 7). Phase 7a.4 ports the
   day-binned aggregator + parity harness extension.

Both are small, focused additions that consume 7a.3's outputs without
modifying its core modules. Bundled into one PR for review economy.

### Phase 7a.4 scope: visual gate + day-binned aggregation

**Cell 50 visual gate (~300–400 lines).** Render the 5 plot families
from a session's per-frame angle parquet + per-trial endpoints JSON;
save consolidated PNGs; side-by-side compare against legacy PNGs from
MICROSCOPE; emit a comparison grid for human review.

**Cell 42 day-binned aggregator (~200–300 lines).** Aggregate
per-session × side traces parquet across sessions by
`(rel_day_bin, side, timebin)` using per-animal `bin_days`; emit
day-binned parquet; legacy_approximate parity at atol=1e-6 against
`*_dayBinnedTraces_*.csv`.

**What 7a.4 delivers end-to-end:**

1. `configs/animals.yaml` — extend with per-animal `bin_days` field
   (PS46–50: 2; PS51/54/55: 7). Source of truth for the day-binning
   aggregator.
2. `configs/defaults.yaml dlc_kinematics.tongue_pertrial:` — add a
   `day_binned:` sub-block (rel-day-bin definition, smoothing knobs
   if needed) AND a new top-level `tongue_visual:` block (figure
   sizing, color schemes, plot-family enable/disable flags).
3. `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` — new
   module: `render_tongue_qc_figures(animal, date, resolver, ...)`
   driver + 5 plot-family helpers (`_plot_per_trial_angle_traces`,
   `_plot_first_peak_aligned`, `_plot_reward_aligned`,
   `_plot_phase_aligned_angle`, `_plot_xy_by_phase`) + side-by-side
   comparison helper.
4. `src/stroke_orofacial/dlc_kinematics/_day_binned.py` — new module:
   `aggregate_licking_dynamics_day_binned(animals, dates, resolver,
   *, params)` driver; per-animal-day grouping; cross-session
   averaging per (rel_day_bin, side, timebin).
5. `src/stroke_orofacial/paths.py` — three new resolver helpers:
   - `tongue_visual_qc_dir(animal, date)` — output dir for
     consolidated PNGs.
   - `tongue_visual_comparison_dir(animal, date)` — output dir for
     side-by-side comparison grids.
   - `tongue_pertrial_licking_dynamics_day_binned_parquet(animal,
     rel_day_bin_label)` — day-binned aggregated traces parquet.
6. `src/stroke_orofacial/dlc_kinematics/__init__.py` — export new
   public symbols.
7. `tests/test_tongue_visual.py` — synthetic-data unit tests for the
   plot-family helpers (smoke test: each helper produces a non-empty
   figure without crashing on synthetic input). Visual fidelity is
   the parity harness's job.
8. `tests/test_day_binned.py` — synthetic-data unit tests for the
   day-binned aggregator (per-animal-day grouping, cross-session
   averaging, edge cases — single session per bin, empty bins).
9. `tests/scripts/parity_phase7a4_day_binned.py` — 14-session parity
   harness for day-binned traces, mirrors the 7a.3 harness's
   `--mode {default, legacy_approximate}` flag.
10. `tests/scripts/parity_phase7a4_visual_gate.py` — visual
    comparison runner: emits side-by-side comparison grids for
    PS46/<dates with saved legacy figures>; output is for human
    review (not numerical pass/fail).
11. `docs/DECISIONS.md` Phase 7a.4 entry — codifies the visual-gate
    pass criteria (semantic match: curve shapes, peak positions, sign
    conventions, distribution shapes); the day-binned schema; the
    `bin_days` per-animal placement.
12. `docs/MIGRATION_LOG.md` Phase 7a.4 entry.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five
items.

### 1. Legacy file disambiguation

One source notebook for both carve-outs:
`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
— same canonical tongue notebook 7a.2 + 7a.3 vendored from. Cells:

- **Cell 42 day-binned aggregator block.** Already vendored byte-
  identically in `docs/legacy_snippets/tongue_pertrial_features.py`
  (Cell 42 SHA256 `986d008ab6fd41c5abf99e3d6f47ed88e7558969ea2bb9bbd02817540e5cc455`,
  Task 1 commit `0b78128`). The day-binning code lives at the bottom
  of the same Cell 42 block — Task 1 audit (2026-04-25) noted
  `*_dayBinnedTraces_*.csv` is part of Cell 42's emit set and called
  it out as deferred to 7a.4. **Re-read the vendored Cell 42 block at
  Task 1.5 below to extract the day-binning aggregation pattern.**
- **Cell 50 plotting cells.** Vendored as part of the Cell 50 block
  (SHA256 `940f172a996002f49ddae2b3fa4695bbb74b4369005426bf01160bd64c91bf2e`).
  V3 Task 1 audit classified the plotting code as Exploratory (do not
  port) at the time, with the visual gate planned to compare against
  saved figures rather than re-emit plot code. 7a.4 PORTS the
  plotting code in `tongue_visual.py` — the plot families ARE in the
  legacy notebook, vendored, ready to port. **Task 1.5 extracts the
  plot-family code from the vendored snippet.**

No new candidate notebooks. Trust 7a.3's prior 3-tier resolution for
the parent notebook.

### 2. Dead code identification (per-cell V3 production scope)

Two Cell families now in scope (vendored byte-identically in commit
`0b78128`, no re-vendor needed):

**Production (port):**

- **Cell 42 day-binning block** — emits
  `*_dayBinnedTraces_*.csv` per animal × per `rel_day_bin` × per
  side. Aggregator: groups sessions by `(animal, rel_day_bin)`; per
  group, averages the per-session × side time-binned traces across
  sessions. Per-animal `bin_days` controls the binning (PS46–50: 2;
  PS51/54/55: 7). Parameter: `MIN_TRIALS_PER_BIN=3` already in
  defaults.yaml.
- **Cell 50 plot families** — 5 plot families (per-trial angle traces
  filtered by inclusion criteria, session-wide first-peak-aligned,
  session-wide reward-aligned, phase-aligned, XY-by-phase). Each
  consumes the per-frame angle parquet + per-trial endpoints JSON
  emitted by 7a.3.

**Exploratory (do NOT port):** legacy plot-styling tweaks (font sizes,
color overrides, ad-hoc figure annotations) that don't affect plot
semantics. Use sensible defaults; let `tongue_visual:` block in
`defaults.yaml` carry the user-tunable knobs.

**Deprecated:** none.

**Ambiguous:** Task 1.5 audits the vendored snippets to confirm; flag
any ambiguity for Priya.

### 3. Sub-phase breakdown (6 commits, 6 tasks)

| Commit | Task | Description | Est. lines | Stop-and-report? |
|---|---|---|---|---|
| C1 | 0 | Phase 7a.4 kickoff (this doc, written by Cowork) | ~700 doc | No (preflight) |
| C2 | 1.5 | Re-read vendored Cell 42 day-binning + Cell 50 plot families; surface schemas + extraction notes | ~30 doc | YES |
| C3 | 2 | configs/animals.yaml `bin_days:` + configs/defaults.yaml `day_binned:` + `tongue_visual:` blocks + 3 path resolvers + path tests | ~250 src/test | YES |
| C4 | 3 | `_day_binned.py` aggregator module + tests | ~400 src/test | YES |
| C5 | 4 | `tongue_visual.py` rendering module + tests | ~500 src/test | YES |
| C6 | 5 | Parity harness (day-binned legacy_approximate) + visual comparison runner + cohort runs | ~400 test | YES |
| C7 | 6 | DECISIONS + MIGRATION_LOG entries | ~80 doc | No |
| C8 | 7 | PR open + tag prep | n/a | No (final) |

### 4. Parity strategy

**Day-binned (numerical):** legacy_approximate-mode parity harness
(`tests/scripts/parity_phase7a4_day_binned.py`) compares the
consolidated day-binned parquet against legacy
`*_dayBinnedTraces_*.csv` at `atol=1e-6` per-(rel_day_bin, side,
timebin) cell. Reuses 7a.3 harness's per-cell knob override
mechanism if needed. Acceptance: all comparisons pass at atol=1e-6
(or document residual band per 7a.3 V3 precedent if numerical-
precision noise applies here too).

**Visual gate (semantic):** visual comparison runner
(`tests/scripts/parity_phase7a4_visual_gate.py`) renders consolidated
PNGs for at least PS50/2025-03-19 (smoke session) + 1–2 cohort
sessions (PS46 family, dates with saved legacy figures present at
`\\research.files...\centered_spout_midpoint\angle_phase_exploratory\`).
Saves side-by-side comparison grids (legacy PNG | consolidated PNG | diff
zoom if useful). Output is for human (Priya) review — no numerical
pass/fail. Acceptance: figures match SEMANTICALLY (curve shapes, peak
positions, sign conventions, distribution shapes, color-coding
behavior). Small numerical drift in y-values tolerated; structural
divergence triggers STOP-and-report.

### 5. Hardcoded constants → defaults.yaml schema

Day-binning knobs go under `dlc_kinematics.tongue_pertrial.day_binned:`
(min_sessions_per_bin, smoothing if any, etc. — Task 1.5 audits
the vendored cell to determine the exact knob set).

Visual-gate knobs go under a new top-level `dlc_kinematics.tongue_visual:`
(figure sizes per plot family, color scheme, line widths, font sizes
if needed, comparison grid layout). Follows 7a.3 V3's pattern of
surfacing all user-tunable constants in YAML.

Per-animal `bin_days` lands in `configs/animals.yaml` (NOT
`defaults.yaml`) since it's per-animal data.

---

## Execute on branch `phase/7a.4-tongue-visual-and-day-binned`

### Preflight

```bash
git checkout main
git pull
git status                            # clean working tree
git log --oneline -1                  # 5063b5e (PR #85 merge)
git tag --list | grep v7a.3           # v7a.3-tongue-pertrial-features present

git checkout -b phase/7a.4-tongue-visual-and-day-binned
git push -u origin phase/7a.4-tongue-visual-and-day-binned
```

Activate the conda environment per CLAUDE.md:

```bash
conda activate stroke_orofacial
which python                          # path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"   # must succeed
pytest --collect-only                 # must collect without import errors (594 tests + 7a.3 V3's 51 = 645 baseline)
```

### Task 0 — Phase 7a.4 kickoff (this doc)

**Status:** Cowork writes this doc; CC consumes it. Once Priya commits
+ pushes the kickoff and pastes the handoff line, Task 0 is complete.

(Do not re-execute Task 0 from inside Claude Code. The kickoff is
Cowork's responsibility; Claude Code consumes it.)

### Task 1.5 — Re-read vendored Cell 42 day-binning + Cell 50 plot families

**Goal.** Audit the vendored snippets to extract the exact day-binning
aggregation pattern + the 5 plot-family code blocks. The vendor is at
`docs/legacy_snippets/tongue_pertrial_features.py` (Task 1 commit
`0b78128`, byte-identical, do NOT re-vendor).

#### 1.5a — Day-binning audit

Read the Cell 42 block from the vendored snippet. Find:

1. The day-binning loop / aggregator (likely a pandas groupby on
   `(rel_day_bin, side, timebin)` or a similar pattern).
2. The exact list of columns aggregated (should be the 4 trace
   columns: `lick_rate_per_t`, `ili_within_bout_rate_per_t`,
   `p_lick_per_t`, `p_within_bout_per_t`).
3. The aggregation function (mean? mean+SEM? median?). Capture
   exactly.
4. The `bin_days` lookup logic — confirm per-animal mapping
   (PS46–50: 2; PS51/54/55: 7).
5. The `MIN_TRIALS_PER_BIN` filter behavior on aggregated bins.
6. The output CSV schema — column names, row identifiers, NaN
   handling.

Write findings to `.scratch_7a4/cell42_day_binned_audit.md`
(gitignored).

#### 1.5b — Cell 50 plot-families audit

Read the Cell 50 block from the vendored snippet. For each of the 5
plot families:

1. **Per-trial tongue-angle traces** (filtered by inclusion criteria).
   What trials are included? (n_multi_lick_bouts >= 1? Cell 50
   `tongue_angle_pass`? — recall V3 dropped that.) What's the y-axis
   range? Trace alignment (reward-aligned?)? Color-coding?
2. **Session-wide tongue-phase first-peak-aligned traces.** Alignment
   point: first peak per trial. What x-axis range? What does "phase"
   mean here — temporal phase or angular phase?
3. **Session-wide tongue-phase reward-aligned traces.** Alignment
   point: reward delivery. Same questions.
4. **Phase-aligned tongue angle.** "Phase" likely means lick-cycle
   phase (0 to 2π or 0 to 360°). What's the binning (n_phase_bins=72
   per defaults.yaml)? What's the y-axis (smoothed angle)?
5. **XY location color-coded by phase.** Per-frame XY scatter colored
   by lick-cycle phase. What's the spatial extent? Color map?

For each plot family, capture the exact matplotlib calls, the input
data sources (which columns from which output product), and the
output filename pattern. Write findings to
`.scratch_7a4/cell50_plot_families_audit.md` (gitignored).

#### 1.5c — STOP-and-report

Report:

- Day-binning aggregator pattern (groupby keys, aggregation function,
  filter behavior).
- Output CSV schema for `*_dayBinnedTraces_*.csv` (column names,
  rel_day_bin labeling convention).
- Per plot family (1–5): input data sources, axis ranges, color
  scheme, alignment point, output filename pattern.
- Any ambiguity or surprising findings.
- Proposed `dlc_kinematics.tongue_pertrial.day_binned:` YAML schema
  (knob list).
- Proposed `dlc_kinematics.tongue_visual:` YAML schema (knob list).

Do NOT advance to Task 2 until Priya acknowledges the audit findings
+ the proposed YAML schemas.

### Task 2 — `configs/animals.yaml` + `configs/defaults.yaml` + `paths.py` + path tests

**Only run Task 2 after Priya acknowledges the Task 1.5 report.**

#### 2a. `configs/animals.yaml` — `bin_days:` per-animal field

Extend each PS46–PS55 animal entry with a `bin_days` field:

```yaml
PS46:
  # ... existing fields ...
  bin_days: 2

PS50:
  # ... existing fields ...
  bin_days: 2

PS51:
  # ... existing fields ...
  bin_days: 7

PS54:
  # ... existing fields ...
  bin_days: 7

PS55:
  # ... existing fields ...
  bin_days: 7
```

(Apply to all 8 PS46–PS55 animals — PS47/PS48/PS49/PS52 follow the
same per-cohort pattern; verify against legacy `MOUSE_SPECS` /
`ANIMALS` dicts in vendored Cell 42 audit notes.)

`AnimalInfo` dataclass extends with `bin_days: int = 1` (sensible
default for any future animal). Loader validates int type. New tests
in `tests/test_animals.py` covering the new field.

#### 2b. `configs/defaults.yaml` — `day_binned:` + `tongue_visual:` blocks

Add under `dlc_kinematics.tongue_pertrial:`:

```yaml
dlc_kinematics:
  tongue_pertrial:
    # ... existing 7a.3 V3 keys (do not modify) ...

    # =========================================================
    # Day-binned cross-session aggregation (Phase 7a.4)
    # =========================================================
    day_binned:
      # Knob list TBD by Task 1.5 audit. Likely candidates:
      #   min_sessions_per_bin: 1
      #   aggregation_function: "mean"  # or "median"
      #   emit_sem: false               # if true, emits sem alongside mean
      #   ...
      <fill-from-1.5a>
```

Add new top-level (sibling of `tongue_pertrial:`):

```yaml
dlc_kinematics:
  tongue_pertrial:
    # ...

  # =========================================================
  # Tongue visual gate rendering (Phase 7a.4)
  # =========================================================
  tongue_visual:
    figure:
      width_inches: 12.0
      height_inches: 8.0
      dpi: 100
    plot_families:
      # Each family enable/disable + family-specific tweaks
      per_trial_angle_traces:
        enabled: true
        y_range_deg: [-90, 90]
        # ... knob list TBD by Task 1.5b audit
      first_peak_aligned:
        enabled: true
        # ...
      reward_aligned:
        enabled: true
        # ...
      phase_aligned_angle:
        enabled: true
        n_phase_bins: 72   # mirrors tongue_pertrial.phase.n_phase_bins
        # ...
      xy_by_phase:
        enabled: true
        # ...
    comparison_grid:
      cols: 2  # legacy | consolidated
      include_diff: false  # zoom inset of difference, if useful
```

Validate YAML loads + assertion check on key values.

#### 2c. `src/stroke_orofacial/paths.py` — three new resolver helpers

```python
def tongue_visual_qc_dir(self, animal: str, date: dt.date) -> Path:
    """Output directory for consolidated tongue-visual QC PNGs."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "figures_qc" / "tongue"
        / animal / f"{date.strftime('%Y%m%d')}"
    )

def tongue_visual_comparison_dir(self, animal: str, date: dt.date) -> Path:
    """Output directory for legacy-vs-consolidated side-by-side comparison grids."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "figures_qc" / "tongue_comparison"
        / animal / f"{date.strftime('%Y%m%d')}"
    )

def tongue_pertrial_licking_dynamics_day_binned_parquet(
    self, animal: str, rel_day_bin_label: str,
) -> Path:
    """Day-binned cross-session traces parquet, per-animal × per-rel_day_bin.

    rel_day_bin_label: e.g. 'pre', 'post_d0_d2', 'post_d3_d5' (exact
    labeling decided in Task 1.5a audit + 2b YAML config).
    """
    return (
        self.pipeline_outputs("dlc_kinematics") / "licking_dynamics"
        / "day_binned" / animal / f"{rel_day_bin_label}.parquet"
    )
```

#### 2d. `tests/test_paths.py` — extend

```python
def test_tongue_visual_qc_dir_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_visual_qc_dir("PS50", dt.date(2025, 3, 19))
    assert p == tmp_path / "dlc_kinematics" / "figures_qc" / "tongue" / "PS50" / "20250319"

def test_tongue_visual_comparison_dir_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_visual_comparison_dir("PS46", dt.date(2025, 5, 1))
    assert p == tmp_path / "dlc_kinematics" / "figures_qc" / "tongue_comparison" / "PS46" / "20250501"

def test_tongue_pertrial_licking_dynamics_day_binned_parquet_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_pertrial_licking_dynamics_day_binned_parquet("PS54", "post_d0_d6")
    assert p == tmp_path / "dlc_kinematics" / "licking_dynamics" / "day_binned" / "PS54" / "post_d0_d6.parquet"
```

#### 2e. Run + commit

```bash
ruff check configs/defaults.yaml || true
ruff check src/stroke_orofacial/paths.py tests/test_paths.py src/stroke_orofacial/animals.py tests/test_animals.py
pytest tests/test_paths.py tests/test_animals.py -v
pytest --collect-only

git add configs/animals.yaml configs/defaults.yaml src/stroke_orofacial/paths.py src/stroke_orofacial/animals.py tests/test_paths.py tests/test_animals.py
git diff --cached --stat
git commit -m "feat(config+paths): bin_days per-animal + day_binned/tongue_visual schemas + 3 resolvers (7a.4)"
git push
```

**STOP and report to Priya:**
- bin_days values seeded for all 8 PS46–PS55 animals.
- `day_binned:` + `tongue_visual:` YAML schemas filled in per Task 1.5
  audit.
- Path-test pass count (target: 3 new tests pass).
- Animals-test pass count (target: ~3 new tests for `bin_days` field).
- Full-suite collection clean.

### Task 3 — `_day_binned.py` aggregator module

**Only run Task 3 after Priya acknowledges the Task 2 report.**

#### 3a. Module structure (target ~400 lines)

`src/stroke_orofacial/dlc_kinematics/_day_binned.py`:

```python
"""Phase 7a.4 — Cell 42 day-binned cross-session traces aggregator.

Ported from the canonical tongue notebook
(20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb,
SHA256 ED12C54...), Cell 42 day-binning block.

Inputs:
  - Per-animal per-session licking-dynamics traces parquet (7a.3 V3
    output, schema locked).
  - Per-animal `bin_days` from `configs/animals.yaml` (PS46–50: 2;
    PS51/54/55: 7).

Output:
  - Per-animal per-rel_day_bin licking-dynamics traces parquet:
    {outputs}/dlc_kinematics/licking_dynamics/day_binned/{animal}/{rel_day_bin_label}.parquet
"""

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.paths import PathResolver

# ============================================================================
# Public API
# ============================================================================

@dataclass
class DayBinnedResult:
    """Container for in-memory day-binned aggregation."""
    by_rel_day_bin: dict[str, pd.DataFrame]
    metadata: dict


def aggregate_licking_dynamics_day_binned(
    animal: str,
    sessions: list[dt.date],
    resolver: PathResolver,
    *,
    params: dict | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path]:
    """Aggregate per-session traces parquets into day-binned parquets.

    For each rel_day_bin (defined by animal.bin_days + d0/stroke date),
    average the 4 trace columns across sessions in that bin.
    """
    ...


# ============================================================================
# Helpers
# ============================================================================

def _compute_rel_day_bin_label(
    session_date: dt.date, d0: dt.date, bin_days: int,
) -> str:
    """Compute the rel_day_bin label for a session.

    Pattern (TBD by 1.5a audit; placeholder):
      'pre' — sessions before d0
      'post_dN_dM' — sessions in days [N, M] post-d0, where M-N+1 = bin_days
    """
    ...


def _load_session_traces(
    animal: str, date: dt.date, resolver: PathResolver,
) -> tuple[pd.DataFrame, dict]:
    """Read 7a.3 V3 per-session traces parquet."""
    ...


def _aggregate_across_sessions(
    per_session_dfs: list[pd.DataFrame], *, params: dict,
) -> pd.DataFrame:
    """Group by (side, timebin); average the 4 trace columns across sessions."""
    ...


def _write_day_binned_parquet_atomic(
    path: Path, df: pd.DataFrame, metadata: dict,
) -> None:
    """pyarrow snappy + temp + os.replace."""
    ...
```

#### 3b. Output schema

Columns (one row per (timebin, side)):
- `timebin_ms` (float64)
- `side` (string)
- `lick_rate_per_t_mean` (float64)
- `ili_within_bout_rate_per_t_mean` (float64)
- `p_lick_per_t_mean` (float64)
- `p_within_bout_per_t_mean` (float64)
- (Optionally `*_sem` columns if Task 1.5a audit confirms legacy emits SEM)
- `n_sessions_in_bin` (int64) — provenance, count of sessions averaged

File-level metadata: `animal, rel_day_bin_label, bin_days, n_sessions,
sessions_iso_dates, aggregation_function, feature_extraction_version,
interpolation_version`.

#### 3c. Tests

`tests/test_day_binned.py` — synthetic-data unit tests:

1. `test_aggregate_two_sessions_same_bin_averages_correctly` — 2
   synthetic per-session traces parquets; verify mean of 4 columns is
   exactly the average per (side, timebin).
2. `test_aggregate_one_session_per_bin_passes_through` — 1 session in
   bin → output equals input (with `n_sessions_in_bin=1`).
3. `test_aggregate_handles_nan_per_session` — NaN in one session's
   trace → mean ignores NaN (np.nanmean semantics).
4. `test_aggregate_skips_bins_below_min_sessions` — bin with fewer
   than `min_sessions_per_bin` sessions → not emitted.
5. `test_compute_rel_day_bin_label_pre_d0` — date before d0 → 'pre'.
6. `test_compute_rel_day_bin_label_post_d0_bin_days_2` —
   bin_days=2 → labels group into 2-day bins (e.g. days 0-1, 2-3).
7. `test_compute_rel_day_bin_label_post_d0_bin_days_7` —
   bin_days=7 → labels group into 7-day bins.
8. `test_aggregate_emits_metadata_keys` — output parquet metadata
   has all expected keys.
9. `test_aggregate_overwrite_skip_semantics` — skip with file present;
   force overwrite.

#### 3d. Run + commit

```bash
ruff check src/stroke_orofacial/dlc_kinematics/_day_binned.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_day_binned.py
pytest tests/test_day_binned.py -v
pytest

git add src/stroke_orofacial/dlc_kinematics/_day_binned.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_day_binned.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): _day_binned cross-session traces aggregator (7a.4)"
git push
```

**STOP and report to Priya:**
- Line count of `_day_binned.py`.
- Test pass count (target: ~9 new tests).
- Full-suite remains 0 failed.
- Ruff clean.

### Task 4 — `tongue_visual.py` rendering module

**Only run Task 4 after Priya acknowledges the Task 3 report.**

#### 4a. Module structure (target ~500 lines)

`src/stroke_orofacial/dlc_kinematics/tongue_visual.py`:

```python
"""Phase 7a.4 — Cell 50 visual gate: render tongue QC figures.

Ported from the canonical tongue notebook Cell 50 plot families.
Consumes 7a.3 V3 outputs (per-frame angle parquet + per-trial
endpoints JSON) and emits 5 PNG plot families per session for
visual comparison against legacy figures.
"""

import datetime as dt
import json
from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from stroke_orofacial.animals import get_animal
from stroke_orofacial.paths import PathResolver

# ============================================================================
# Public API
# ============================================================================

def render_tongue_qc_figures(
    animal: str, date: dt.date, resolver: PathResolver,
    *, params: dict | None = None,
    families: list[str] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path]:
    """Render the 5 plot families for one (animal, date).

    families: list of family names to render. Defaults to all 5.
    Returns {family_name: png_path}.
    """
    ...


def render_comparison_grid(
    animal: str, date: dt.date, resolver: PathResolver,
    legacy_figures_root: Path,
    *, families: list[str] | None = None,
) -> dict[str, Path]:
    """Render legacy-vs-consolidated side-by-side comparison grids.

    legacy_figures_root: e.g.
      Path(r"\\research.files...\angle_phase_exploratory")
    Returns {family_name: comparison_png_path}.
    """
    ...


# ============================================================================
# Plot families (5 helpers)
# ============================================================================

def _plot_per_trial_angle_traces(
    angle_df: pd.DataFrame, endpoints: dict, *, params: dict,
) -> plt.Figure:
    """Per-trial tongue-angle traces, filtered by inclusion criteria."""
    ...


def _plot_first_peak_aligned(
    angle_df: pd.DataFrame, endpoints: dict, *, params: dict,
) -> plt.Figure:
    """Session-wide tongue-phase first-peak-aligned traces."""
    ...


def _plot_reward_aligned(
    angle_df: pd.DataFrame, endpoints: dict, *, params: dict,
) -> plt.Figure:
    """Session-wide tongue-phase reward-aligned traces."""
    ...


def _plot_phase_aligned_angle(
    angle_df: pd.DataFrame, endpoints: dict, *, params: dict,
) -> plt.Figure:
    """Phase-aligned tongue angle (n_phase_bins binning)."""
    ...


def _plot_xy_by_phase(
    angle_df: pd.DataFrame, endpoints: dict, *, params: dict,
) -> plt.Figure:
    """XY tongue location color-coded by lick-cycle phase."""
    ...


# ============================================================================
# Helpers
# ============================================================================

def _load_angle_parquet(
    animal: str, date: dt.date, resolver: PathResolver,
) -> pd.DataFrame:
    """Read 7a.3 V3 per-frame angle parquet."""
    ...


def _load_endpoints_json(
    animal: str, date: dt.date, resolver: PathResolver,
) -> dict:
    """Read 7a.3 V3 per-trial endpoints JSON."""
    ...


def _load_legacy_png(
    family: str, animal: str, date: dt.date, legacy_figures_root: Path,
) -> Path | None:
    """Resolve legacy PNG path. Returns None if missing."""
    ...


def _save_comparison_grid(
    legacy_png: Path | None, consolidated_png: Path, output_path: Path,
) -> None:
    """Build legacy | consolidated side-by-side via PIL or matplotlib."""
    ...
```

#### 4b. Tests

`tests/test_tongue_visual.py` — smoke tests (each helper produces a
non-empty figure on synthetic input):

1. `test_render_tongue_qc_figures_emits_5_pngs` — driver writes 5 PNGs.
2. `test_render_per_trial_angle_traces_handles_empty_inclusion` — no
   trials pass inclusion → emit empty plot with annotation, do NOT
   crash.
3. `test_plot_phase_aligned_uses_n_phase_bins_from_params` — knob
   propagates from defaults.yaml.
4. `test_render_overwrite_skip_semantics` — skip with PNG present;
   force overwrites.
5. `test_render_comparison_grid_handles_missing_legacy_png` — legacy
   PNG missing → emit single-pane consolidated only with annotation
   "legacy figure not found".
6–10. One smoke test per plot family (`_plot_per_trial_angle_traces`
through `_plot_xy_by_phase`) — synthetic inputs; assert figure has
at least one Axes object with at least one line/scatter/image.

Visual fidelity is the parity harness's job; unit tests are smoke +
schema only.

#### 4c. Run + commit

```bash
ruff check src/stroke_orofacial/dlc_kinematics/tongue_visual.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_tongue_visual.py
pytest tests/test_tongue_visual.py -v
pytest

git add src/stroke_orofacial/dlc_kinematics/tongue_visual.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_tongue_visual.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): tongue_visual.py — 5 plot families + comparison grid (7a.4)"
git push
```

**STOP and report to Priya:**
- Line count of `tongue_visual.py`.
- Test pass count (target: ~10 new tests).
- Full-suite remains 0 failed.
- Ruff clean.

### Task 5 — Parity harness + cohort runs

**Only run Task 5 after Priya acknowledges the Task 4 report.**

#### 5a. Day-binned legacy_approximate parity

Create `tests/scripts/parity_phase7a4_day_binned.py` modelled on
`tests/scripts/parity_phase7a3_tongue_pertrial.py`. Reuses the
14-session scope filter + per-animal `bin_days` lookup.

CLI: `--mode {default, legacy_approximate} --sessions auto --atol 1e-6`.

Reader: legacy `*_dayBinnedTraces_*.csv` from MICROSCOPE
(exact path resolved from Task 1.5a audit).

Comparator: per-(rel_day_bin, side, timebin) at atol=1e-6.

Acceptance: all comparisons pass; or document residual band per 7a.3
V3 precedent (precision noise on aggregation).

#### 5b. Visual gate runner

Create `tests/scripts/parity_phase7a4_visual_gate.py`. For:
- PS50/2025-03-19 (smoke session, no parity but has consolidated outputs)
- PS46/<dates with saved legacy figures, e.g. 2025-03-07>
  (consolidated outputs + legacy figures both present)

Run `render_tongue_qc_figures` + `render_comparison_grid`. Save
output paths. Report to Priya for human review.

#### 5c. Day-binned cohort emit (default mode)

Run aggregator across all 8 animals (or just the 5 in scope) for the
14-session cohort. Confirm per-animal × per-rel_day_bin parquet
emit. Capture file count + sizes.

#### 5d. Day-binned legacy_approximate parity run

```bash
python tests/scripts/parity_phase7a4_day_binned.py \
    --mode legacy_approximate --sessions auto --atol 1e-6 \
    | tee /tmp/parity_7a4_day_binned.log
echo "exit=$?"
```

If any `status = fail`: capture details + STOP-and-report.

#### 5e. Commit

```bash
git add tests/scripts/parity_phase7a4_day_binned.py tests/scripts/parity_phase7a4_visual_gate.py
git diff --cached --stat
git commit -m "feat(parity): Phase 7a.4 day-binned parity + visual gate runner (7a.4)"
git push
```

**STOP and report to Priya:**
- Day-binned cohort emit confirmation (per-animal × per-rel_day_bin
  file count).
- Day-binned legacy_approximate parity by_status counts + per-bin
  max|Δ| table.
- Visual gate output paths for PS50 + PS46 sessions; comparison grids
  ready for human review.
- Any fail → STOP AND WAIT.

### Task 6 — DECISIONS + MIGRATION_LOG entries

**Only run Task 6 after Task 5 reports clean numerical parity + visual
gate human-review-ready.**

#### 6a. `docs/DECISIONS.md` — Phase 7a.4 entry

Insert above existing reverse-chronological entries. Codifies:

- Phase 7a.4 scope: bundle Cell 50 visual gate + Cell 42 day-binned
  cross-session traces.
- Day-binned schema: per-animal × per-rel_day_bin parquet at
  `{outputs}/dlc_kinematics/licking_dynamics/day_binned/`.
- `bin_days` placement: per-animal in `animals.yaml` (NOT
  `defaults.yaml` since it's per-animal data).
- Visual gate pass criterion: SEMANTIC match (curve shapes, peak
  positions, sign conventions, distribution shapes), not pixel-
  identical. Output is for human review.
- Forward implications: future bodyparts (jaw, whisker) reuse the
  visual-gate machinery + day-binned aggregator pattern.

Plus the cohort numerical results + visual-gate human-review verdict.

#### 6b. `docs/MIGRATION_LOG.md` — Phase 7a.4 entry

Append after Phase 7a.3 V3.

#### 6c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.4): DECISIONS + MIGRATION_LOG entries"
git push
```

### Task 7 — PR + tag prep

#### 7a. Open PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.4: Cell 50 visual gate + Cell 42 day-binned cross-session traces" \
  --body - <<'EOF'
Phase 7a.4 ports the two carve-outs from 7a.3 V3 into a single PR:
the Cell 50 visual gate (5 plot families + side-by-side legacy
comparison) and the Cell 42 day-binned cross-session aggregator.
Both consume 7a.3 V3's outputs without modifying the core modules.

## What lands

1. `configs/animals.yaml` — `bin_days:` per-animal (PS46–50: 2;
   PS51/54/55: 7).
2. `configs/defaults.yaml` — `dlc_kinematics.tongue_pertrial.day_binned:`
   block + new top-level `dlc_kinematics.tongue_visual:` block.
3. `src/stroke_orofacial/dlc_kinematics/_day_binned.py` —
   cross-session aggregator.
4. `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` — 5 plot
   families + comparison grid renderer.
5. 3 new `PathResolver` helpers.
6. `tests/test_day_binned.py` (~9 tests) +
   `tests/test_tongue_visual.py` (~10 tests) +
   `tests/test_paths.py` (3 new tests) + `tests/test_animals.py`
   (~3 new tests).
7. `tests/scripts/parity_phase7a4_day_binned.py` — 14-session
   parity harness for day-binned traces (default + legacy_approximate
   modes).
8. `tests/scripts/parity_phase7a4_visual_gate.py` — visual
   comparison runner for PS50 + PS46 sessions.
9. DECISIONS + MIGRATION_LOG entries.

## Parity / tests / ruff

- Full pytest: <PASTE> passed / <PASTE> skipped / 0 failed.
- Ruff clean.
- Day-binned parity: by_status = <PASTE>; per-bin max|Δ| <PASTE>.
- Visual gate: comparison grids rendered for PS50/2025-03-19 +
  PS46/<date>; human-review verdict <PASTE>.

## Tag on merge

`v7a.4-tongue-visual-and-day-binned`

## Not in this PR

- Phase 7a.3-jaw — jaw per-trial features (separate phase, distinct
  design).
- Future face-velocity / PSD / mismatch-classifier phases.
- Whisker visual gate (would extend the same machinery).
EOF
```

#### 7b. Final verification

```bash
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD

ruff check .
pytest -q

# After PR merges:
# git checkout main && git pull
# git tag -a v7a.4-tongue-visual-and-day-binned <merge-sha> \
#   -m "Phase 7a.4: Cell 50 visual gate + Cell 42 day-binned cross-session traces"
# git push origin v7a.4-tongue-visual-and-day-binned
```

Report PR URL + commit SHAs + ruff + pytest counts + parity numerics +
visual gate output paths. STOP. **Do not merge.** Priya reviews,
merges from GitHub UI, then tags on the merge commit herself.

---

## Constraints (across all 7 tasks)

- **Phase 7a.4 scope is Cell 50 visual gate + Cell 42 day-binned ONLY.**
  No new bodypart work. No Phase 7a.3-jaw (separate phase). No
  algorithm changes to 7a.3 V3 modules (`tongue_pertrial.py`,
  `_detector.py`, `_angle.py`, `_writers.py`) — all 4 stay locked.
- **Seven commits on top of `main` post-7a.3 merge.** Kickoff +
  Task 1.5 + 5 task commits + PR. Each task = one commit.
- **Stop-and-report between Tasks 1.5 / 2 / 3 / 4 / 5.** Tasks 6 and
  7 chain after Task 5 reports clean numerical parity + visual gate
  human-review-ready.
- **No MICROSCOPE writes.** All MICROSCOPE access is read-only
  (legacy CSV reads + legacy PNG reads). Consolidated outputs go
  under `stroke_orofacial_pipeline_outputs/dlc_kinematics/`.
- **No force-push.** All pushes additive to
  `phase/7a.4-tongue-visual-and-day-binned`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit.
- **If day-binned legacy_approximate parity reports `status = fail`:**
  STOP. Do not widen tolerance. Do not write DECISIONS / MIGRATION_LOG
  claiming success.
- **If visual-gate comparison grid surfaces a structural divergence
  (wrong curve shape, missing peaks, wrong sign):** STOP and report.
  Priya decides whether to triage in this phase or defer to a follow-up.
- **If Task 1.5 audit hits an Ambiguous code block:** STOP. Do not
  silently choose; let Priya pick.
- **Vendored snippets at `docs/legacy_snippets/` stay READ-ONLY.**
  `# ruff: noqa` + `# fmt: off` headers preserve byte-identity with
  capture time; do NOT edit, reformat, or lint them.
- **7a.3 V3 module schema is LOCKED.** Per-frame angle parquet,
  per-session licking-dynamics traces parquet, per-trial endpoints
  JSON — schemas locked by 7a.3 V3 acceptance + tag. 7a.4 consumes
  these schemas as-is; any consumed-key changes require revisiting
  the lock.
- **Test gap from 7a.3 (NaN-walking unit test dropped in C5.1):** if
  Task 1.5 audit naturally exposes a failing-trial captured-fixture
  pattern that would also serve as the NaN-walking regression test,
  capture it as a follow-up commit. Otherwise leave for a separate
  cleanup task.
- **Path-resolver cleanup from 7a.3:** factor `licks_npz(animal,
  date)` into `PathResolver` if Task 5a's day-binned aggregator needs
  to read it (the day-binner shouldn't, but if it does, surface the
  helper). Otherwise leave for a separate cleanup.
