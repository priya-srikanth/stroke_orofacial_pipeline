# Phase 7a.1 Kickoff — `animals.yaml kinematics_baselines` + parity-harness scaffold + stress-pilot (combined 7a.1)

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.1-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.0 merged 2026-04-22 as PR #79 on branch
`docs/phase-7a-legacy-probe`. It landed:

- `docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py`
  (vendored legacy Cell 23 + Cell 22 with provenance headers).
- `docs/phase-7/baseline-seed-table.md` with the full per-combo X0/Y0 probe
  and the 2026-04-22 **"Scope-filtered re-analysis"** section that resolves
  the PS49/PS50 tongue NEEDS_HUMAN_DECISION verdicts. Final roll-up:
  **16 STABLE / 0 NHD / 0 INSUFFICIENT** under the
  `animals.yaml sessions.{start, end}` scope filter.
- `docs/phase-7/scipy-pilot-results.md` with the scipy 1.15.1 vs 1.17.1
  PCHIP pilot on PS46/20250307 tongue: **max|Δ| = 0.0 on x and y**,
  `n_exact_equal / n_common = 914,012 / 914,012`. Bit-identical.
- `tests/scripts/scipy_version_pilot.py` (pilot runner).
- `docs/DECISIONS.md` 2026-04-22 grouped entry: **Parity-scope principle**
  (standing rule, all phases) + **scipy version handling — Option A**
  (atol=1e-6, no pin, no widening) with a caveat that a second-session
  stress pilot on PS51/20250430 lands alongside the 7a.1 parity harness.

Phase 7a.1 combines the three smallest unblocked pieces into one PR so
that Phase 7a.2 (interpolation.py impl) becomes the single focused PR
that writes module code:

1. **(A) Seed `animals.yaml kinematics_baselines:` + `AnimalInfo` loader
   extension.** Values from `baseline-seed-table.md` §"Scope-filtered
   re-analysis" — 16 STABLE combos, all verified via probe.
2. **(B) Parity-harness scaffold** — `tests/scripts/parity_phase7a_interpolation.py`
   with scope-filter + legacy-NPZ loading + stubbed consolidated-side
   comparison (the stub is what 7a.2 replaces with the real module call).
3. **(C) Second-session scipy stress pilot** on PS51/20250430 per the
   2026-04-22 DECISIONS caveat — high-NaN stress session, confirms Option A
   is robust beyond the first pilot's PS46/20250307 datapoint.

**No `src/stroke_orofacial/dlc_kinematics/` code in 7a.1.** The module
proper lands in 7a.2.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five items.
For 7a.1 they apply loosely — no notebook cells are being ported (that's
7a.2), so items 1-2 are no-ops:

1. **Legacy file disambiguation.** N/A for 7a.1 — no cells ported. Seed
   values come from legacy NPZs already probed in PR #79 (canonical per
   tier-2 output-mtime rule applied during the probe).
2. **Dead code identification.** N/A for 7a.1 — no notebook ports.
3. **Sub-phase breakdown.** Three commits (tasks 1–3), plus one docs
   commit (task 4), plus one PR-and-tag step (task 5). Per-commit line
   counts sketched below.
4. **Parity strategy.** 7a.1 itself has no parity gate — it *builds* the
   parity harness. The harness's comparator targets are specified in
   `interpolation-strategy.md` §6 (14 sessions, atol=1e-6 per 7a.0 Option
   A). 7a.2 is the first PR to pass parity.
5. **Hardcoded constants.** N/A — the `dlc_kinematics:` YAML block in
   `configs/defaults.yaml` lands in 7a.2. 7a.1 only touches
   `configs/animals.yaml` per-animal `kinematics_baselines:` block.

---

## Execute on a new feature branch

Branch name: `phase/7a.1-kinematics-baselines-parity-scaffold`
PR base: `main`
Tag on merge: `v7a.1-kinematics-baselines-parity-scaffold`

---

### Preflight

1. Read `CLAUDE.md` in full. All rules apply.
2. Environment activation:
   ```bash
   conda activate stroke_orofacial
   which python                              # .conda/envs/stroke_orofacial/
   python -c "import stroke_orofacial"
   ```
3. `pytest --collect-only` must complete without import errors (CLAUDE.md
   gate). Capture the "N tests collected" count for the pre-check.
4. Branch setup from main:
   ```bash
   git checkout main
   git pull origin main
   git branch --show-current                 # must print: main
   git log --oneline -3                      # confirm PR #79 merge commit is in history
   git checkout -b phase/7a.1-kinematics-baselines-parity-scaffold
   git branch --show-current                 # must print: phase/7a.1-kinematics-baselines-parity-scaffold
   ```
5. MICROSCOPE UNC reachability (needed for task 3 stress pilot):
   ```powershell
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS51\PS51_tongue_kinematics\processed_interpolated_data\centered_spout_midpoint\PS51_20250430_cam2_tongue_interp_v5p3.npz"
   # must print True
   ```
   If False — STOP and ask Priya before task 3.
6. Commit the kickoff doc itself as commit 1 of this branch:
   ```bash
   git status                                # expect: docs/prompts/phase-7a.1-kickoff.md untracked
   git add docs/prompts/phase-7a.1-kickoff.md
   git commit -m "docs(prompts): Phase 7a.1 kickoff"
   git push -u origin phase/7a.1-kinematics-baselines-parity-scaffold
   ```
   Rationale: unlike 7a.0 (where the kickoff was saved as its own docs-only
   PR first — PR #42 precedent), 7a.1 is small enough that save+execute in
   one PR is cleaner. The kickoff stays in-repo as permanent provenance of
   what this PR did.

---

### Task 1 — `kinematics_baselines` seed + `AnimalInfo` loader extension

**Goal.** Populate `configs/animals.yaml` with each animal's per-bodypart
`(X0, Y0)` baseline, and extend `AnimalInfo` so `interpolation.py` (in
7a.2) can read them via `animal_info.kinematics_baselines["tongue"]`.

#### 1a. Add `kinematics_baselines:` block to each animal in `configs/animals.yaml`

Seed values are from `docs/phase-7/baseline-seed-table.md` §"Scope-filtered
re-analysis", "Seed values for `configs/animals.yaml kinematics_baselines:`"
table. All 16 combos are STABLE with zero intra-combo variance across
in-scope sessions.

Under each animal's top-level block (after `sessions:`, `exclusions:`,
`analysis_params:` — mirror the existing field ordering for readability),
append:

```yaml
# PS46, PS47, PS48, PS49, PS50 — tongue uniform at (0, -110); jaw uniform at (0, 310)
PS46:
  # ... existing fields ...
  kinematics_baselines:
    tongue:
      x0: 0.0
      y0: -110.0
    jaw:
      x0: 0.0
      y0: 310.0

# PS51, PS54 — tongue at (0, -110); jaw at (12, 290)
PS51:
  # ... existing fields ...
  kinematics_baselines:
    tongue:
      x0: 0.0
      y0: -110.0
    jaw:
      x0: 12.0
      y0: 290.0

# PS55 — tongue at (0, -110); jaw at (0, 290)
PS55:
  # ... existing fields ...
  kinematics_baselines:
    tongue:
      x0: 0.0
      y0: -110.0
    jaw:
      x0: 0.0
      y0: 290.0
```

Apply to all 8 animals. The complete value grid:

| Animal | tongue.x0 | tongue.y0 | jaw.x0 | jaw.y0 |
|---|---|---|---|---|
| PS46 | 0.0 | -110.0 | 0.0 | 310.0 |
| PS47 | 0.0 | -110.0 | 0.0 | 310.0 |
| PS48 | 0.0 | -110.0 | 0.0 | 310.0 |
| PS49 | 0.0 | -110.0 | 0.0 | 310.0 |
| PS50 | 0.0 | -110.0 | 0.0 | 310.0 |
| PS51 | 0.0 | -110.0 | 12.0 | 290.0 |
| PS54 | 0.0 | -110.0 | 12.0 | 290.0 |
| PS55 | 0.0 | -110.0 | 0.0 | 290.0 |

**Do NOT invent fallbacks.** Every animal must have both `tongue` and
`jaw` keys; missing at load time is an error per 1b below.

#### 1b. Extend `AnimalInfo` in `src/stroke_orofacial/animals.py`

Add the field to the dataclass:

```python
@dataclass
class AnimalInfo:
    # ... existing fields ...
    kinematics_baselines: dict[str, dict[str, float]] = field(default_factory=dict)
```

Extend `load_animals()` (or the per-animal loader helper — match the
existing pattern) to parse the YAML block into
`{"tongue": {"x0": ..., "y0": ...}, "jaw": {"x0": ..., "y0": ...}}`.
Validation rules (fail loud at load time, with a clear error naming the
offending animal):

- Block is required for every animal. Missing → raise `ValueError` with
  message naming the animal.
- Each bodypart (`tongue`, `jaw`) must carry both `x0` and `y0` as numeric
  values (int or float; cast to float on load).
- Unknown bodyparts in the block → raise (guards against typos).

Add a convenience accessor:

```python
def get_kinematics_baseline(self, bodypart: str) -> dict[str, float]:
    """Return {'x0': float, 'y0': float} for the given bodypart.

    Raises KeyError if bodypart not configured. The interpolation module
    calls this with bodypart='tongue' or 'jaw' — either must be present
    per the 2026-04-22 schema decision.
    """
    if bodypart not in self.kinematics_baselines:
        raise KeyError(
            f"Animal {self.animal!r} has no kinematics_baselines for "
            f"bodypart {bodypart!r}; configured: "
            f"{sorted(self.kinematics_baselines)}"
        )
    return self.kinematics_baselines[bodypart]
```

#### 1c. Tests in `tests/test_animals.py`

Add unit tests to the existing file (extend, don't create a new file):

- `test_kinematics_baselines_loaded_for_all_animals` — every animal in
  `configs/animals.yaml` parses with both bodyparts present, x0 and y0
  are finite floats.
- `test_kinematics_baselines_tongue_uniform` — all 8 animals have
  `tongue.x0 == 0.0` and `tongue.y0 == -110.0`.
- `test_kinematics_baselines_jaw_per_animal_groups` — PS46–PS50 jaw at
  (0, 310); PS51, PS54 at (12, 290); PS55 at (0, 290).
- `test_kinematics_baselines_missing_raises` — synthetic YAML without the
  block → `load_animals()` raises with a message naming the animal.
- `test_kinematics_baselines_missing_bodypart_raises` — YAML with only
  `tongue:` → raises on load.
- `test_get_kinematics_baseline_unknown_bodypart_raises` — calling
  `animal.get_kinematics_baseline("whisker")` raises KeyError.

Use `PathResolver(output_root=tmp_path)` if any test needs a resolver.
Synthetic YAML fixtures go under `tmp_path` — do NOT write to
`configs/animals.yaml` from tests.

#### 1d. Run tests + ruff

```bash
pytest tests/test_animals.py -v                            # all green, including new tests
pytest                                                       # full suite, no regressions
ruff check src/stroke_orofacial/animals.py tests/test_animals.py configs/animals.yaml
```

#### 1e. Commit

```bash
git add configs/animals.yaml src/stroke_orofacial/animals.py tests/test_animals.py
git diff --cached --stat
git commit -m "feat(animals): kinematics_baselines schema + per-animal seed from PR #79 probe"
git push
```

**STOP and report to Priya:**
- new test count added + full-suite pass,
- diff of `configs/animals.yaml` showing the 8 `kinematics_baselines:` blocks,
- any unexpected findings from the parse.

---

### Task 2 — Parity-harness scaffold

**Goal.** Create `tests/scripts/parity_phase7a_interpolation.py` with
everything *except* the call into the 7a.2-pending `interpolation.py`
module. The stub cleanly identifies itself so when 7a.2 lands, a
single-function replacement gets the harness green.

**Only run task 2 after Priya acknowledges the task 1 report.**

#### 2a. Script skeleton

Create `tests/scripts/parity_phase7a_interpolation.py`:

```python
"""Phase 7a parity harness — legacy NPZ vs consolidated parquet, 14 sessions.

Scope: compares x_final / y_final / X0 / Y0 / fps / n_frames between the
legacy v5p3 NPZs on MICROSCOPE and the consolidated-pipeline parquets
written by src/stroke_orofacial/dlc_kinematics/interpolation.py.

As of Phase 7a.1 the consolidated-side read is stubbed — the module
does not yet exist. Phase 7a.2 replaces the `_load_consolidated_trace`
stub below with the real call. Everything else (legacy load, scope
filter, tolerance comparison, session enumeration) is ready.

Usage:
    python tests/scripts/parity_phase7a_interpolation.py \\
        --animal PS46 --date 20250307 --bodypart tongue
    python tests/scripts/parity_phase7a_interpolation.py --sessions auto

--sessions auto enumerates the 14 parity sessions from
interpolation-strategy.md §6 (9 primary + 3 stress + 2 late-post-stroke)
and runs each in sequence.

Exit codes:
    0 — all compared sessions within atol
    1 — at least one session failed tolerance (actual mismatch)
    2 — pending-impl stub hit (expected in 7a.1; expected to disappear in 7a.2)
    3 — legacy NPZ missing / MICROSCOPE unreachable
    4 — scope-filter skipped all sessions (configuration error)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

# --- constants from interpolation-strategy.md §6 --------------------------

ATOL = 1e-6  # Phase 7a.0 Option A (DECISIONS 2026-04-22, scipy 1.15.1↔1.17.1 bit-identical)

MICROSCOPE_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis"
)

CENTER_MODE = {
    "tongue": "centered_spout_midpoint",
    "jaw": "centered_eye_midpoint",
}

# 14 parity sessions per interpolation-strategy.md §6.
PARITY_SESSIONS_PRIMARY = [
    ("PS46", dt.date(2025, 3, 7)),  ("PS46", dt.date(2025, 3, 10)), ("PS46", dt.date(2025, 3, 13)),
    ("PS54", dt.date(2025, 5, 6)),  ("PS54", dt.date(2025, 5, 9)),  ("PS54", dt.date(2025, 5, 12)),
    ("PS55", dt.date(2025, 5, 1)),  ("PS55", dt.date(2025, 5, 4)),  ("PS55", dt.date(2025, 5, 7)),
]
PARITY_SESSIONS_STRESS = [
    ("PS51", dt.date(2025, 4, 30)),
    ("PS54", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 2)),
]
PARITY_SESSIONS_LATE = [
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]
PARITY_SESSIONS_14 = PARITY_SESSIONS_PRIMARY + PARITY_SESSIONS_STRESS + PARITY_SESSIONS_LATE


# --- dataclasses ---------------------------------------------------------


@dataclass
class ParityResult:
    animal: str
    date: dt.date
    bodypart: str
    status: str  # "pass", "fail", "stub", "skip_scope", "skip_missing"
    max_abs_dx: float | None = None
    max_abs_dy: float | None = None
    note: str = ""


# --- scope filter --------------------------------------------------------


def load_scope(animals_yaml_path: Path) -> dict[str, tuple[dt.date, dt.date]]:
    with open(animals_yaml_path) as f:
        animals = yaml.safe_load(f)
    out = {}
    for animal, blob in animals.items():
        scope = blob.get("sessions", {})
        start = scope.get("start")
        end = scope.get("end")
        if isinstance(start, str):
            start = dt.date.fromisoformat(start)
            end = dt.date.fromisoformat(end)
        if start and end:
            out[animal] = (start, end)
    return out


def is_in_scope(animal: str, date: dt.date, scope: dict) -> bool:
    if animal not in scope:
        return False
    start, end = scope[animal]
    return start <= date <= end


# --- legacy NPZ loader ---------------------------------------------------


def _legacy_npz_path(animal: str, date: dt.date, bodypart: str) -> Path:
    date_str = date.strftime("%Y%m%d")
    center = CENTER_MODE[bodypart]
    return (
        MICROSCOPE_ROOT / animal / f"{animal}_{bodypart}_kinematics"
        / "processed_interpolated_data" / center
        / f"{animal}_{date_str}_cam2_{bodypart}_interp_v5p3.npz"
    )


def load_legacy_trace(animal: str, date: dt.date, bodypart: str) -> dict:
    path = _legacy_npz_path(animal, date, bodypart)
    if not path.exists():
        raise FileNotFoundError(f"Legacy NPZ not found: {path}")
    data = np.load(path, allow_pickle=True)
    return {
        "x_final": data["x_final"].astype(float),
        "y_final": data["y_final"].astype(float),
        "X0": float(data["X0"]),
        "Y0": float(data["Y0"]),
        "fps": float(data["fps"]),
        "n_frames": int(data["n_frames"]),
        "path": path,
    }


# --- consolidated-side stub (7a.2 replaces this) -------------------------


def _load_consolidated_trace(animal: str, date: dt.date, bodypart: str) -> dict:
    """Load x_final, y_final, X0, Y0 from the consolidated-pipeline parquet.

    7a.1 STUB — raises NotImplementedError. 7a.2 replaces this with:
        path = resolver.interpolated_trace(bodypart=bodypart, animal=animal, date=date)
        df = pd.read_parquet(path)
        meta = pq.ParquetFile(path).metadata.metadata
        return {
            "x_final": df["x_final"].to_numpy(),
            "y_final": df["y_final"].to_numpy(),
            "X0": float(meta[b"X0"]),
            "Y0": float(meta[b"Y0"]),
            "fps": float(meta[b"fps"]),
            "n_frames": int(meta[b"n_frames"]),
        }
    """
    raise NotImplementedError(
        "Consolidated-pipeline read not implemented until Phase 7a.2. "
        f"Target: {animal} / {date} / {bodypart}. "
        "This stub is expected to disappear in 7a.2 — do not paper over it."
    )


# --- comparator ----------------------------------------------------------


def compare_session(animal: str, date: dt.date, bodypart: str) -> ParityResult:
    legacy = load_legacy_trace(animal, date, bodypart)
    try:
        consolidated = _load_consolidated_trace(animal, date, bodypart)
    except NotImplementedError as e:
        return ParityResult(animal, date, bodypart, status="stub", note=str(e))

    # scalar metadata must match exactly
    for key in ("X0", "Y0", "fps", "n_frames"):
        if legacy[key] != consolidated[key]:
            return ParityResult(
                animal, date, bodypart, status="fail",
                note=f"{key} mismatch: legacy={legacy[key]}, consolidated={consolidated[key]}",
            )

    # trace arrays: atol=1e-6 element-wise on non-NaN common indices
    for axis in ("x_final", "y_final"):
        a = legacy[axis]
        b = consolidated[axis]
        if a.shape != b.shape:
            return ParityResult(
                animal, date, bodypart, status="fail",
                note=f"{axis} shape mismatch: {a.shape} vs {b.shape}",
            )
        mask = ~(np.isnan(a) | np.isnan(b))
        if mask.sum() == 0:
            continue
        max_abs_d = float(np.abs(a[mask] - b[mask]).max())
        if max_abs_d > ATOL:
            return ParityResult(
                animal, date, bodypart, status="fail",
                max_abs_dx=max_abs_d if axis == "x_final" else None,
                max_abs_dy=max_abs_d if axis == "y_final" else None,
                note=f"{axis} max|Δ|={max_abs_d:.3e} > atol={ATOL:.1e}",
            )

    return ParityResult(animal, date, bodypart, status="pass")


# --- main ----------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--animal", help="e.g. PS46")
    ap.add_argument("--date", help="YYYYMMDD", type=lambda s: dt.date.fromisoformat(f"{s[:4]}-{s[4:6]}-{s[6:]}"))
    ap.add_argument("--bodypart", choices=("tongue", "jaw"))
    ap.add_argument("--sessions", choices=("auto",), help="auto = run §6's 14-session parity set across both bodyparts")
    ap.add_argument("--animals-yaml", default="configs/animals.yaml")
    args = ap.parse_args()

    scope = load_scope(Path(args.animals_yaml))

    if args.sessions == "auto":
        todo = [(a, d, bp) for (a, d) in PARITY_SESSIONS_14 for bp in ("tongue", "jaw")]
    else:
        if not (args.animal and args.date and args.bodypart):
            print("error: provide --animal --date --bodypart or --sessions auto", file=sys.stderr)
            return 4
        todo = [(args.animal, args.date, args.bodypart)]

    results: list[ParityResult] = []
    for animal, date, bodypart in todo:
        if not is_in_scope(animal, date, scope):
            results.append(ParityResult(animal, date, bodypart, status="skip_scope",
                                        note=f"out of sessions.{{start,end}} for {animal}"))
            continue
        try:
            results.append(compare_session(animal, date, bodypart))
        except FileNotFoundError as e:
            results.append(ParityResult(animal, date, bodypart, status="skip_missing", note=str(e)))

    # summary
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    print(f"\nParity summary: {by_status}")
    for r in results:
        print(f"  {r.animal} {r.date} {r.bodypart:6s} {r.status:14s} {r.note}")

    if by_status.get("fail", 0) > 0:
        return 1
    if by_status.get("stub", 0) > 0 and by_status.get("pass", 0) == 0:
        return 2
    if not any(r.status == "pass" for r in results) and by_status.get("skip_scope", 0) == len(results):
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 2b. Ruff + smoke run

```bash
ruff check tests/scripts/parity_phase7a_interpolation.py

# Smoke (both MUST work in 7a.1):
# 1. Single session, expect stub exit code 2:
python tests/scripts/parity_phase7a_interpolation.py --animal PS46 --date 20250307 --bodypart tongue
echo "exit=$?"      # expect 2

# 2. Full auto, expect stub for every in-scope session + skip_scope for any out-of-scope:
python tests/scripts/parity_phase7a_interpolation.py --sessions auto
echo "exit=$?"      # expect 2
```

Both should exit cleanly with code 2 (all-stub). If the scope-filter
drops the whole 14-session set — exit code 4 — STOP: something is wrong
with `sessions.{start, end}` vs. the hardcoded parity-session dates.

#### 2c. Commit

```bash
git add tests/scripts/parity_phase7a_interpolation.py
git diff --cached --stat
git commit -m "feat(tests/scripts): Phase 7a parity harness scaffold (stub until 7a.2)"
git push
```

**STOP and report to Priya:**
- exit codes from the two smoke runs,
- `by_status` counts,
- any sessions that came back `skip_missing` (would indicate MICROSCOPE
  access hiccup or legacy-NPZ gap in the 14-session set).

---

### Task 3 — Second-session scipy stress pilot (PS51/20250430)

**Goal.** Confirm the 2026-04-22 scipy Option A decision holds on a
second session with a different NaN profile. PS51/20250430 is the
brief-§6 stress-set high-NaN session.

**Only run task 3 after Priya acknowledges the task 2 report.**

Reuses `tests/scripts/scipy_version_pilot.py` (already committed in PR
#79). No code changes — just runs + writeup.

#### 3a. Run the pilot under both scipy versions

```bash
NPZ='//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS51/PS51_tongue_kinematics/processed_interpolated_data/centered_spout_midpoint/PS51_20250430_cam2_tongue_interp_v5p3.npz'

conda run -n sop_scipy_pilot python tests/scripts/scipy_version_pilot.py "$NPZ" > /tmp/stress_pilot_scipy_1p15p1.json
conda run -n stroke_orofacial python tests/scripts/scipy_version_pilot.py "$NPZ" > /tmp/stress_pilot_scipy_1p17p1.json

ls -la /tmp/stress_pilot_scipy_*.json
```

If `sop_scipy_pilot` env is missing (e.g., the workstation was reimaged
since PR #79) — re-create it per PR #79 Task 1a:

```bash
conda create -n sop_scipy_pilot python=3.11 -y
conda activate sop_scipy_pilot
pip install "scipy==1.15.1" numpy pandas pyarrow
python -c "import scipy; print(scipy.__version__)"   # must print 1.15.1
conda deactivate
```

#### 3b. Diff the two JSON payloads

Use the same diff block from PR #79's Task 1d (pasted inline, not committed):

```bash
python - <<'PY'
import json
import numpy as np

with open('/tmp/stress_pilot_scipy_1p15p1.json') as f:
    a = json.load(f)
with open('/tmp/stress_pilot_scipy_1p17p1.json') as f:
    b = json.load(f)

assert a['npz'] == b['npz']
assert a['n_frames'] == b['n_frames']
print(f"scipy A = {a['scipy_version']}, scipy B = {b['scipy_version']}")
print(f"n_frames = {a['n_frames']}, NaN-in x = {a['n_nan_input_x']}, NaN-in y = {a['n_nan_input_y']}")

x_a = np.array(a['x_interp']); x_b = np.array(b['x_interp'])
y_a = np.array(a['y_interp']); y_b = np.array(b['y_interp'])

for name, arr_a, arr_b in [('x', x_a, x_b), ('y', y_a, y_b)]:
    mask = ~(np.isnan(arr_a) | np.isnan(arr_b))
    n_common = int(mask.sum())
    if n_common == 0:
        print(f"{name}: no common non-NaN frames — investigate")
        continue
    diff = np.abs(arr_a[mask] - arr_b[mask])
    print(f"{name}: n_common={n_common}, max|Δ|={diff.max():.3e}, "
          f"median|Δ|={np.median(diff):.3e}, "
          f"p99|Δ|={np.percentile(diff, 99):.3e}, "
          f"n_exact_equal={(diff == 0).sum()}")
    nan_a = np.isnan(arr_a) & ~np.isnan(arr_b)
    nan_b = ~np.isnan(arr_a) & np.isnan(arr_b)
    print(f"{name}: NaN-only-in-1.15.1={nan_a.sum()}, NaN-only-in-1.17.1={nan_b.sum()}")
PY
```

Capture the numbers. Expected under Option A robustness: max|Δ|=0 on both
dims, same as the first pilot. If max|Δ| > 0 but < 1e-6: Option A still
holds but record the drift. If max|Δ| ≥ 1e-6 on this stress session:
**STOP and report** — Option A may need revisiting.

#### 3c. Append stress-pilot section to `docs/phase-7/scipy-pilot-results.md`

Below the existing first-pilot section, add:

```markdown
## Second-session stress pilot — PS51/20250430 tongue (2026-04-22)

Per DECISIONS 2026-04-22 "scipy version handling" caveat 1, this
second-session pilot validates Option A on a high-NaN stress-set
session from `interpolation-strategy.md` §6.

### Session probed

PS51 / 20250430 / tongue (STABLE combo per baseline-seed-table.md,
in-scope per PS51 sessions.start).

- NPZ: `O2_analysis/PS51/PS51_tongue_kinematics/.../PS51_20250430_cam2_tongue_interp_v5p3.npz`
- n_frames: <N>
- NaN-in x (post-drop, pre-PCHIP): <N>
- NaN-in y (post-drop, pre-PCHIP): <N>

### Diff summary

| Dim | max|Δ| | median|Δ| | p99|Δ| | n_exact_equal |
|---|---|---|---|---|
| x | <>   | <>       | <>    | <>           |
| y | <>   | <>       | <>    | <>           |

NaN-boundary deltas: NaN-only-in-1.15.1 = <x>/<y>, NaN-only-in-1.17.1 = <x>/<y>.

### Interpretation

<Expected>: max|Δ| = 0.0 on both dims, NaN masks identical. Confirms
Option A (atol=1e-6, no pin) holds across (at minimum) a
low-NaN-fraction session (PS46/20250307, pilot #1) and a
high-NaN-fraction stress session (PS51/20250430, this pilot). No
DECISIONS amendment beyond recording this datapoint.

<Alternative, if drift > 0>: revisit Option A — see STOP-and-report
directive above.
```

Fill the numbers from the diff output. Ensure the outcome statement is
explicit ("Option A confirmed" vs. "revisit").

#### 3d. DECISIONS amendment (if Option A confirmed)

If max|Δ| = 0 on this stress pilot (expected outcome), append a single
line under the existing "scipy version handling" entry's *Caveats*
bullet 1 (the "single-session pilot" caveat):

```markdown
  - **Update 2026-04-22 (Phase 7a.1):** Second-session stress pilot on
    PS51/20250430 tongue — max|Δ|=0.0 on both x and y, NaN masks
    identical. Caveat 1 is resolved; Option A now validated on both a
    low-NaN session (PS46/20250307) and a high-NaN stress session
    (PS51/20250430). No further scipy pilots required for 7a.
```

If drift > 0 — DO NOT append this line; instead, STOP and report.

#### 3e. Commit

```bash
git add docs/phase-7/scipy-pilot-results.md docs/DECISIONS.md
git diff --cached --stat
git commit -m "docs(phase-7a.1): second-session scipy stress pilot confirms Option A"
git push
```

**STOP and report to Priya:**
- the diff summary table values,
- confirm / revisit statement,
- whether the DECISIONS line was appended.

---

### Task 4 — MIGRATION_LOG + docs refresh

**Only run task 4 after task 3 reports success.**

#### 4a. `docs/MIGRATION_LOG.md` — add Phase 7a.0 AND Phase 7a.1 entries

Phase 7a.0 entry (retrospective — PR #79 landed 2026-04-22 but no
MIGRATION_LOG entry was written at that time):

```markdown
## Phase 7a.0 — Legacy-probe + NPZ baseline-seed probe + scipy pilot

**Date:** 2026-04-22
**PR:** #79 (merged, `v7a.0` NOT tagged — 7a.0 stayed docs-only per design)
**Branch:** `docs/phase-7a-legacy-probe`

**What was done:**

- Vendored legacy Cell 23 (tongue, 763 lines) and Cell 22 (jaw, 755
  lines) as `docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py`
  with provenance headers. Precedent: Phase 8a.7.5 `behavior_report`
  vendor pattern.
- Probed every legacy v5p3 NPZ on MICROSCOPE for X0/Y0 stability per
  `(animal, bodypart)`. Initial roll-up: 14 STABLE / 2
  NEEDS_HUMAN_DECISION (PS49 tongue, PS50 tongue). Amendment
  "Scope-filtered re-analysis" under the animals.yaml
  sessions.{start,end} filter: **16 STABLE / 0 NHD / 0 INSUFFICIENT**.
  The 13 out-of-scope PS49/PS50 early-session NPZs are pre-narrowing
  artifacts, not parity targets.
- Recorded the legacy-era scipy version (1.15.1 from Windows
  `deeplabcut` env) and ran a scipy 1.15.1 vs 1.17.1 PCHIP pilot on
  PS46/20250307 tongue: **max|Δ| = 0.0** on x and y,
  `n_exact_equal / n_common = 914,012 / 914,012`. Bit-identical.
- `tests/scripts/scipy_version_pilot.py` committed as a reusable template.

**Decisions produced (see DECISIONS.md 2026-04-22 entry):**

- **Parity-scope principle** (standing rule, all phases) — parity
  comparisons against legacy outputs are restricted to sessions within
  `configs/animals.yaml sessions.{start, end}` per animal.
- **scipy version handling — Option A** — Phase 7a.1 parity harness
  runs under consolidated env scipy 1.17.1 with `atol=1e-6`. No pin,
  no widening.

**Behavior differences vs. legacy notebooks:** None. Docs-only PR;
nothing touched source data, no `src/` edits.

**No tag.** 7a.0 is docs-only; phase-close tagging resumes at 7a.1.

**Forward follow-ups handed to 7a.1 (this PR):**
- Seed `configs/animals.yaml kinematics_baselines:` from the 16-STABLE
  scope-filtered table.
- Second-session scipy stress pilot on PS51/20250430 (caveat 1
  resolution).
- Parity-harness scaffold with stubbed consolidated-side read until
  7a.2 delivers `interpolation.py`.
```

Phase 7a.1 entry (this PR):

```markdown
## Phase 7a.1 — `kinematics_baselines` seed + parity-harness scaffold + stress pilot

**Date:** 2026-04-22
**PR:** #<FILL>
**Tag:** `v7a.1-kinematics-baselines-parity-scaffold` on merge commit
**Branch:** `phase/7a.1-kinematics-baselines-parity-scaffold`

**What was done:**

- `configs/animals.yaml` — added `kinematics_baselines:` block per
  animal (PS46–PS55) with `tongue.{x0, y0}` and `jaw.{x0, y0}` seeded
  from `docs/phase-7/baseline-seed-table.md` §"Scope-filtered
  re-analysis". Tongue uniform at (0, -110) across cohort; jaw varies
  per animal ((0, 310) for PS46–PS50, (12, 290) for PS51/PS54,
  (0, 290) for PS55).
- `src/stroke_orofacial/animals.py` — extended `AnimalInfo` with
  `kinematics_baselines: dict[str, dict[str, float]]` field;
  `load_animals()` parses the YAML block and fails loud on missing /
  malformed entries; added `AnimalInfo.get_kinematics_baseline(bodypart)`
  accessor.
- `tests/test_animals.py` — 6 new tests covering load, per-animal
  grouping, missing-block / missing-bodypart raises, accessor KeyError.
- `tests/scripts/parity_phase7a_interpolation.py` — 14-session parity
  harness scaffold. Legacy NPZ load + `animals.yaml sessions.{start, end}`
  scope filter + `atol=1e-6` comparator. Consolidated-side
  `_load_consolidated_trace` stubbed with explicit NotImplementedError
  until 7a.2 replaces it. Exit codes: 0 pass / 1 fail / 2 stub / 3
  missing / 4 scope.
- `docs/phase-7/scipy-pilot-results.md` — appended "Second-session
  stress pilot — PS51/20250430 tongue" section: <fill: max|Δ| = 0 or
  the measured value>. DECISIONS 2026-04-22 caveat 1 resolved.
- `docs/DECISIONS.md` — amended "scipy version handling" entry with
  the second-pilot datapoint.

**Behavior differences vs. legacy notebooks:** None. `kinematics_baselines`
YAML values match the X0/Y0 that legacy NPZs were computed with under
the in-scope session range — this is the faithful-port path per
`interpolation-strategy.md` §3.1 "faithful port, not a bug fix".

**Intentional convention:** `kinematics_baselines` block is REQUIRED
for every animal at load time (not silently defaulted). Rationale:
future animals joining the cohort must explicitly declare their
baselines so `interpolation.py` never silently runs with a
cross-contaminated baseline from another animal.

**Ground-rule compliance:** CLAUDE.md rule 1 — no source data
modified (only `np.load` / `Path.glob` on MICROSCOPE). Rule 8 —
feature branch, tag pushed. Tests + ruff green.
```

#### 4b. Commit

```bash
git add docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(migration-log): Phase 7a.0 + Phase 7a.1 entries"
git push
```

---

### Task 5 — PR + tag

#### 5a. Open the PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.1: kinematics_baselines + parity scaffold + stress pilot" \
  --body - <<'EOF'
Combined 7a.1 PR — the three smallest unblocked pieces between the 7a.0
close (PR #79) and the 7a.2 interpolation.py impl.

## What lands

1. `configs/animals.yaml` `kinematics_baselines:` block per animal (8 animals
   × 2 bodyparts = 16 values, all STABLE per `baseline-seed-table.md`
   §"Scope-filtered re-analysis").
2. `AnimalInfo.kinematics_baselines` + `get_kinematics_baseline(bodypart)`
   accessor + 6 new tests.
3. `tests/scripts/parity_phase7a_interpolation.py` — 14-session parity
   harness scaffold with stubbed consolidated-side read. 7a.2 replaces
   `_load_consolidated_trace` stub; everything else (scope filter,
   comparator, session list) is ready.
4. Second-session scipy stress pilot on PS51/20250430 confirming
   Option A holds under high-NaN conditions. DECISIONS caveat 1
   resolved.
5. MIGRATION_LOG retrospective entry for Phase 7a.0 (PR #79) + forward
   entry for this PR.

## Parity / tests / ruff

- Full pytest suite green (N collected, N passed, N added).
- ruff clean on all touched files.
- Parity harness smoke: `--animal PS46 --date 20250307 --bodypart tongue`
  returns exit code 2 (stub) as designed.
- Parity harness `--sessions auto` returns exit code 2 with all 14
  sessions × 2 bodyparts hitting the stub (in-scope, legacy NPZs reachable).

## Tag on merge

`v7a.1-kinematics-baselines-parity-scaffold`

## Not in this PR (7a.2 scope)

- `src/stroke_orofacial/dlc_kinematics/interpolation.py` (module impl)
- `configs/defaults.yaml` `dlc_kinematics:` block (bodypart-parametric
  constants, §7 of the brief)
- Parity harness real consolidated-side read
- One-session smoke (PS50/20250306) per §9
EOF
```

#### 5b. Final verification

```bash
# Commits on the branch since main:
git log --oneline origin/main..HEAD
# Expected: 5 commits — kickoff, animals.yaml/loader, parity scaffold,
# stress pilot, MIGRATION_LOG.

# Touched file summary:
git diff --stat origin/main..HEAD
# Expected paths:
#   docs/prompts/phase-7a.1-kickoff.md            (task 0, commit 1)
#   configs/animals.yaml                           (task 1)
#   src/stroke_orofacial/animals.py                (task 1)
#   tests/test_animals.py                          (task 1)
#   tests/scripts/parity_phase7a_interpolation.py  (task 2)
#   docs/phase-7/scipy-pilot-results.md            (task 3)
#   docs/DECISIONS.md                              (task 3)
#   docs/MIGRATION_LOG.md                          (task 4)

# Ruff + pytest one more time for the PR record:
ruff check .
pytest -q

# After PR merges on main, tag and push:
# git checkout main && git pull
# git tag -a v7a.1-kinematics-baselines-parity-scaffold <merge-sha> -m "Phase 7a.1: kinematics_baselines seed + parity-harness scaffold + second scipy pilot"
# git push origin v7a.1-kinematics-baselines-parity-scaffold
```

Report to Priya: PR URL, the 5 commit SHAs, ruff + pytest counts, parity
harness exit-code smoke results. STOP. **Do not merge.** Priya reviews
and merges from the GitHub UI, then tags on the merge commit herself.

---

## Constraints (across all 5 tasks)

- **Phase 7a.1 scope is config + loader + test + script + docs ONLY.**
  No `src/stroke_orofacial/dlc_kinematics/` code. The sole `src/` edit
  is `src/stroke_orofacial/animals.py` to add the
  `kinematics_baselines` field + accessor.
- **Five commits, not one.** Each task = one commit, for PR review
  granularity. Task 0 (kickoff-commit) is bundled with preflight before
  task 1.
- **Stop-and-report between tasks 1 / 2 / 3.** Tasks 4 and 5 chain
  through after task 3 confirms (Option A holds OR Priya handles the
  drift exception path).
- **No MICROSCOPE writes.** All MICROSCOPE access is `np.load` +
  `Path.glob` only.
- **No force-push.** All pushes are additive to
  `phase/7a.1-kinematics-baselines-parity-scaffold`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit, per CLAUDE.md §"Git discipline" precedent.
- **If the stress pilot shows drift > 0** in task 3 — STOP. Do not
  append the DECISIONS line; do not proceed to tasks 4 / 5. Report the
  numbers to Priya; she decides whether Option A stands or needs an
  amendment.
- **If any `configs/animals.yaml` animal already has a
  `kinematics_baselines:` block** — STOP. Either someone else is
  editing concurrently or the branch is dirty. Ask Priya before
  proceeding.
