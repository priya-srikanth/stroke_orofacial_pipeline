# Phase 7a.3 Kickoff — kinematic features (tongue + jaw): velocity, angle, amplitude

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.3-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.2 merged 2026-04-24 as PR #83 on branch
`phase/7a.2-interpolation-impl`, tagged `v7a.2-interpolation-impl`
(merge commit `fbe91fd`). It landed:

- `src/stroke_orofacial/dlc_kinematics/interpolation.py` — the v5p3
  7-stage bodypart-parametric port (tongue Cell 23 + jaw Cell 22)
  with `InterpolationResult`, `_interpolate_bodypart_core`,
  `build_interpolated_trace`, and the by-animal-date wrapper.
- `configs/defaults.yaml dlc_kinematics:` block — bodypart-parametric
  constants per `interpolation-strategy.md` §7.
- `PathResolver.interpolated_trace(bodypart, animal, date, *, variant)`
  helper.
- `tests/test_dlc_interpolation.py` — 14 unit tests per strategy §8.
- 14-session × 2-bodypart parity at `atol=1e-6` against legacy NPZs:
  cohort-wide bit-identical (`max|Δ|x = max|Δ|y = 0.000e+00` on every
  in-scope dim under scipy 1.17.1 Option A).
- DECISIONS 2026-04-24 entry codifying Knobs 1–4 + §5 Option A + §3.1
  baseline encoding; locks the 9 file-level metadata keys
  (`X0, Y0, fps, n_frames, center_mode, baseline_stage,
  interpolation_version, wavesurfer_sides_match_mouse_sides,
  side_convention_version`) and the 7 parquet columns as the standing
  schema for all downstream consumers.

Phase 7a.3 is the **first downstream phase** that consumes those
interpolated-trace parquets. It ports the per-frame and per-trial
kinematic features that the legacy notebooks (`20260203_..._tongue.ipynb`
and `20260416_..._jaw.ipynb`) compute on top of the v5p3 traces:

- **Per-frame derived metrics** — tongue velocity, tongue angle (deviation
  from the eye-midpoint → spout-midpoint reference line), jaw velocity.
- **Per-trial scalars** — tongue amplitude, tongue velocity peak, tongue
  angle peak, jaw amplitude, jaw velocity peak — each emitted over a
  wide reward-aligned window (-500 to 5000 ms) and a tight window
  (-100 to 1000 ms).

Tongue X/Y and jaw X/Y per-frame positions are **already shipped** in
the 7a.2 `interpolated_traces/{bodypart}/{animal}/{date}.parquet`
(columns `x_final`, `y_final`); 7a.3 does not duplicate them.

Phase 7a.3 ends with a merged PR + tag, cohort-wide bit-identical (or
within `atol=1e-6`) parity on the 14-session set against legacy NPZs,
and the two new output products on disk:
`{outputs}/dlc_kinematics/features/{bodypart}/{animal}/{date}.parquet`
+ `{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json`.

### What 7a.3 delivers end-to-end

1. `docs/legacy_snippets/tongue_velocity_amplitude_angle.py` and
   `docs/legacy_snippets/jaw_velocity_amplitude.py` — vendored cells
   from the canonical tongue + jaw notebooks with full SHA256
   provenance headers (legacy-snippet pattern from PR #79 / 7a.0).
2. `configs/defaults.yaml` — new
   `dlc_kinematics.feature_extraction:` block (windows, smoothing,
   peak-detection knobs).
3. `configs/animals.yaml` — extended **only if** Task 0 audit finds
   per-animal variation in window bounds, smoothing kernels, or peak-
   detection thresholds in the legacy notebooks. If cohort-uniform,
   no `animals.yaml` change.
4. `src/stroke_orofacial/dlc_kinematics/features.py` — new module
   computing velocity (per-frame), tongue angle (per-frame), per-trial
   amplitude / velocity peak / angle peak over wide + tight windows.
   Bodypart-parametric where shared, bodypart-specific where required
   (angle is tongue-only).
5. `src/stroke_orofacial/paths.py` — add
   `kinematic_features_parquet(bodypart, animal, date)` and
   `kinematic_endpoints_json(animal, date)` resolver helpers.
6. `src/stroke_orofacial/dlc_kinematics/__init__.py` — export the new
   public symbols.
7. `tests/test_dlc_features.py` — unit tests covering per-frame
   computation, per-trial aggregation, window edges, schema, and
   atomic write semantics.
8. `tests/scripts/parity_phase7a3_features.py` — 14-session × 2-bodypart
   parity harness against legacy NPZs (per-frame velocity / angle) and
   per-trial scalar tables (amplitude / velocity peak / angle peak).
9. `docs/DECISIONS.md` Phase 7a.3 entry — codifies the per-frame
   features parquet schema, per-trial endpoints JSON schema, window
   bounds, and parity acceptance.
10. `docs/MIGRATION_LOG.md` Phase 7a.3 entry.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five items.

1. **Legacy file disambiguation.** Two source notebooks under
   `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/`:
   - `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` —
     tongue velocity + tongue amplitude + tongue angle. Same notebook
     vendored for 7a.2's interpolation Cell 23. The velocity / amplitude
     / angle cells are downstream of Cell 23 in the same notebook.
   - `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` — jaw
     velocity + jaw amplitude. Same notebook vendored for 7a.2's
     interpolation Cell 22.

   Apply the three-tier rule:
   - Both notebooks are the latest-dated within their bodypart family
     (tongue: `20260203`; jaw: `20260416`). Older variants like
     `20251216_*` are explicitly superseded.
   - No sibling notebooks with distinct scope markers
     (e.g. no `_baseline_only`, `_post_stroke_only` variants for the
     velocity/amplitude/angle cells).
   - Scoped distinctions like `*_reward-aligned_*` notebooks ARE
     siblings with different scope (per-trial reward-aligned arrays vs.
     full-session traces) — they are NOT duplicates of these. Do not
     port from those siblings; the canonical velocity/angle/amplitude
     cells are inside the two notebooks above.

   Trust 7a.2's prior 3-tier resolution; 7a.3 adds no new candidates,
   only new cell selection within the same already-canonical notebooks.

2. **Dead code identification.** Cell-level walk inside each notebook,
   classifying each cell:
   - **Production (port):** velocity computation cells, angle computation
     cell (tongue only), per-trial windowing helpers, per-trial peak /
     amplitude aggregators, NPZ writers (their schema → our parquet +
     JSON schema).
   - **Exploratory (do NOT port):** plot-velocity-traces QC cells,
     plot-amplitude-distribution cells, ad-hoc histogram cells. These
     are inspection-only.
   - **Deprecated (do NOT port):** any cells inside the notebook that
     reference earlier `_v0`/`_mod`/`_old`-suffixed helpers from the
     same notebook author's history.
   - **Ambiguous (stop-and-ask if hit):** any cell that mixes
     analysis with manual per-animal date-window editing (analogous
     to the `DATE_START` / `DATE_END` pattern from 7a.2). In the
     consolidated pipeline, scope comes from `animals.yaml` via
     `SessionManifest`, not from notebook-level constants. If a cell
     embeds `if animal == "PSXX": ...` branches, STOP and report
     before porting — Priya decides whether they become
     per-animal `animals.yaml` entries or whether they're bug-fix
     experiments that don't propagate.

   Task 0 is the place where this classification happens — its
   STOP-and-report includes the per-cell classification table.

3. **Sub-phase breakdown.** 8 commits (7 tasks + kickoff commit),
   estimated line counts:
   - Commit 1 (Task 0 bundled with preflight): this kickoff doc.
   - Commit 2 (Task 1): legacy-cell vendoring + per-animal audit. Two
     new files under `docs/legacy_snippets/` (~150–250 lines vendored
     each, depending on how many cells are production-classified) +
     audit findings reported to Priya.
   - Commit 3 (Task 2): `configs/defaults.yaml
     dlc_kinematics.feature_extraction:` block (~30–50 YAML lines) +
     `configs/animals.yaml` extension if Task 0 audit demands it
     (only if the audit found per-animal variation) +
     `PathResolver.kinematic_features_parquet()` and
     `PathResolver.kinematic_endpoints_json()` helpers (~50 lines
     paths.py) + 4–6 path unit tests.
   - Commit 4 (Task 3): `src/stroke_orofacial/dlc_kinematics/
     features.py` (~350–500 lines: per-frame velocity, per-frame angle,
     per-trial windowing, per-trial aggregators, session-level writer
     emitting parquet + JSON atomically).
     `src/stroke_orofacial/dlc_kinematics/__init__.py` export of new
     public symbols.
   - Commit 5 (Task 4): `tests/test_dlc_features.py` (~250–350 lines,
     unit tests + helper fixtures).
   - Commit 6 (Task 5): `tests/scripts/parity_phase7a3_features.py`
     parity harness (~200–250 lines). Cohort run results recorded in
     the stop-and-report (not committed).
   - Commit 7 (Task 6): `docs/DECISIONS.md` + `docs/MIGRATION_LOG.md`
     entries.
   - Commit 8 (Task 7): PR open. Tag is post-merge.

4. **Parity strategy.** Same 14-session set as 7a.2 — 9 primary
   (PS46/PS54/PS55 × 3 dates each) + 3 stress (PS51/20250430,
   PS54/20250501, PS55/20250502) + 2 late post-stroke (PS54/20250607,
   PS55/20250607), across both bodyparts = 28 (animal, date, bodypart)
   triplets. Per-frame velocity (tongue + jaw) and tongue angle
   compared element-wise at `atol=1e-6` against the corresponding
   arrays in legacy NPZs at
   `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/
   {animal}_{bodypart}_kinematics/<feature_dir>/...npz` (exact paths
   resolved at Task 5 from the audit findings — they may live under
   a sibling subdir of the v5p3 NPZs from 7a.2). Per-trial scalars
   (amplitude, velocity peak, angle peak) compared per-trial at the
   same tolerance against the corresponding scalar arrays.

   **Acceptance:** all 28 (per-frame velocity) + 14 (tongue angle) +
   28 × 2 windows (per-trial scalars per bodypart) comparisons return
   `status = pass`, with `skip_missing` tolerated for sessions where
   the legacy NPZ is genuinely absent (PS54/20250512 was the 7a.2
   gap). Any `status = fail` → STOP and report; do not widen the
   tolerance, do not advance to Task 6.

5. **Hardcoded constants.** All numerical knobs land in
   `configs/defaults.yaml` under
   `dlc_kinematics.feature_extraction.<key>`:
   - Velocity smoothing kernel size + filter type.
   - Peak-detection thresholds (if used in legacy aggregators).
   - Window bounds: `wide: {pre_ms: 500, post_ms: 5000}` and
     `tight: {pre_ms: 100, post_ms: 1000}`.
   - Angle reference-line endpoints (`tongue_angle.reference: ["eye_midpoint", "spout_midpoint"]`).

   Per-animal variation (if Task 0 audit finds any) lives under
   `configs/animals.yaml` per animal, mirroring the existing
   `kinematics_baselines:` and `analysis_params.break_thr_*` patterns.
   Module reads from
   `params["dlc_kinematics"]["feature_extraction"][...]` first, then
   per-animal overrides via `animal_info` if present.

   No numeric literals inside `features.py` that vary per bodypart,
   per animal, or per cohort. The reference-line endpoint *names*
   (`"eye_midpoint"`, `"spout_midpoint"`) name fixed manifest-resolver
   keys, not tunable parameters — they are OK as string literals
   inside the module, but still surfaced in `defaults.yaml` with a
   "do not change without DECISIONS entry" comment.

---

## Execute on a new feature branch

Branch name: `phase/7a.3-kinematic-features-tongue-jaw`
PR base: `main`
Tag on merge: `v7a.3-kinematic-features-tongue-jaw`

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
   pre-check (post-7a.2 baseline is 517; record actual.)
4. Branch setup from main:
   ```bash
   git checkout main
   git pull origin main
   git branch --show-current                 # must print: main
   git log --oneline -5                      # confirm PR #83 merge commit (fbe91fd) is in history
   git tag --list | tail -5                  # confirm v7a.2-interpolation-impl present
   git checkout -b phase/7a.3-kinematic-features-tongue-jaw
   git branch --show-current                 # must print: phase/7a.3-kinematic-features-tongue-jaw
   ```
5. MICROSCOPE UNC reachability (needed for Task 1 vendoring + Task 5
   parity run):
   ```powershell
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics"
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_jaw_kinematics"
   # both must print True
   ```
   If either False — STOP and ask Priya before Task 1. (Tasks 2–4 are
   pure-Python; they do not require MICROSCOPE.)
6. Confirm 7a.2 outputs are reachable for downstream wiring:
   ```bash
   ls src/stroke_orofacial/dlc_kinematics/
   # expect: __init__.py features.py filters.py interpolation.py reward_aligned.py
   # interpolation.py MUST be present (7a.2 landed it).
   # features.py MAY exist as a stub from earlier scaffolding — read it
   # before editing to confirm it's the empty/stub variant. If it
   # already contains a velocity/angle implementation, STOP (concurrent
   # work or stale branch).
   ```
7. Commit the kickoff doc itself as commit 1 of this branch (matches
   the 7a.2 in-branch kickoff-provenance pattern):
   ```bash
   git status                                # expect: docs/prompts/phase-7a.3-kickoff.md untracked
   git add docs/prompts/phase-7a.3-kickoff.md
   git commit -m "docs(prompts): Phase 7a.3 kickoff"
   git push -u origin phase/7a.3-kinematic-features-tongue-jaw
   ```

---

### Task 1 — Legacy-cell vendoring + per-animal audit

**Goal.** Vendor the velocity / angle / amplitude cells from the two
canonical notebooks into `docs/legacy_snippets/` with full provenance
headers, and audit them for per-animal variation that would force
`animals.yaml` changes in Task 2.

#### 1a. Identify the canonical cells

Open each notebook in read-only mode (no edits — both are inside
`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` per
CLAUDE.md rule 2):

- **Tongue notebook** (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`):
  walk every cell after Cell 23 (the v5p3 interpolation cell vendored
  for 7a.2). Identify:
  - the velocity-computation cell(s),
  - the angle-computation cell(s) — looking for code that uses both
    `eye_midpoint` and `spout_midpoint` as reference points and
    computes an angular deviation,
  - the amplitude / per-trial aggregation cell(s),
  - the writer cell(s) that emit NPZ files containing these arrays.
- **Jaw notebook** (`20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`):
  walk every cell after Cell 22 (the v5p3 interpolation cell vendored
  for 7a.2). Identify the velocity + amplitude + per-trial aggregation
  + writer cells. Jaw has no angle metric.

For each candidate cell, classify per Plan-shape §2 above:
Production / Exploratory / Deprecated / Ambiguous. Only Production
cells get vendored.

#### 1b. Vendor the cells

Create two new files under `docs/legacy_snippets/`:

- `docs/legacy_snippets/tongue_velocity_amplitude_angle.py`
- `docs/legacy_snippets/jaw_velocity_amplitude.py`

Each file MUST have a header in the 7a.0 / 7a.2 vendoring style:

```python
"""Vendored from <source notebook path> Cells <N>, <M>, ...
Captured for Phase 7a.3 — 2026-04-2X.

3-tier-rule disambiguation: <one-sentence summary; reference 7a.2
disambiguation already accepted for the parent notebook>.

Source SHA256: <hash of the parent .ipynb file at capture time>
Cells included: <list>
Cells excluded (and why): <list of any cells classified
Exploratory/Deprecated/Ambiguous, with the classification reason>

DO NOT edit, reformat, or lint this file. # ruff: noqa, # fmt: off
preserve byte-identity with capture time.
"""
# ruff: noqa
# fmt: off
```

Compute the SHA256 with:
```bash
sha256sum "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/<notebook>.ipynb"
```

Inside each file, paste the production cells **verbatim** (preserving
indentation, comments, blank lines, magic commands replaced with
`# %%` markers if any), separated by `# %% Cell <N>` markers between
cells.

If any cell has an Ambiguous classification — STOP and report before
vendoring it. Do not silently vendor or silently exclude.

#### 1c. Per-animal audit

Walk the vendored cells (and their parent notebooks for context) for:

- **Window-bound variation.** Does any cell embed
  `if animal == "PS46": pre_ms = 500 else: pre_ms = 750`-style branches?
  Does the wide window or tight window differ per animal?
- **Smoothing-kernel variation.** Does the velocity smoothing window or
  filter type differ per animal?
- **Peak-detection variation.** Do per-trial peak-detection thresholds
  differ per animal?
- **Reference-point variation (tongue angle).** Are `eye_midpoint` and
  `spout_midpoint` always the reference, or do some animals use a
  different anatomical landmark?

Cross-reference with `configs/animals.yaml` to see which existing
per-animal fields might be relevant (`kinematics_baselines`,
`analysis_params.break_thr_*`).

#### 1d. Audit report

Produce a written summary captured in the Task 1 stop-and-report:

- Per-cell classification table (one row per candidate cell with the
  classification + reason).
- SHA256 of each parent notebook.
- Audit verdict: **cohort-uniform** (no per-animal variation found,
  defaults.yaml only) OR **per-animal variation present** (list which
  fields and which animals; propose `animals.yaml` schema additions
  for Task 2).

#### 1e. Commit

```bash
git add docs/legacy_snippets/tongue_velocity_amplitude_angle.py docs/legacy_snippets/jaw_velocity_amplitude.py
git diff --cached --stat
git commit -m "docs(legacy_snippets): vendor tongue+jaw velocity/angle/amplitude cells"
git push
```

**STOP and report to Priya:**
- the per-cell classification table,
- vendored file paths + line counts + SHA256 provenance,
- audit verdict (cohort-uniform vs per-animal variation),
- if per-animal variation present: proposed `animals.yaml` schema
  additions + which animals get which values,
- any Ambiguous cells encountered (and STOP — wait for Priya's
  decision before Task 2).

---

### Task 2 — Config + PathResolver helpers

**Only run Task 2 after Priya acknowledges the Task 1 report.**

**Goal.** Land the constants and resolver helpers that
`features.py` (Task 3) reads at module level.

#### 2a. Add `dlc_kinematics.feature_extraction:` block to `configs/defaults.yaml`

Extend the existing `dlc_kinematics:` block (added in 7a.2) with a new
nested `feature_extraction:` section. Default skeleton:

```yaml
# --- DLC kinematic features (Phase 7a.3) ---------------------------------
# Per-frame derived metrics (velocity, angle) and per-trial scalars
# (amplitude, velocity peak, angle peak). Reads interpolated traces
# from {outputs}/dlc_analysis/interpolated_traces/{bodypart}/{animal}/
# {date}.parquet. Emits per-frame parquet to dlc_kinematics/features/
# and per-trial JSON scalars to dlc_kinematics/endpoints/.
#
# DO NOT change angle.reference without a DECISIONS entry — the
# eye_midpoint → spout_midpoint reference line is locked at 7a.3.
dlc_kinematics:
  # ... existing 7a.2 block (interpolation_version, interpolation_method,
  # interpolation_fallback, tongue:, jaw:) — leave intact ...

  feature_extraction:
    velocity:
      smoothing_window_frames: <fill from Task 1 audit>
      smoothing_filter: <fill from Task 1 audit>      # e.g. "savgol", "moving_average"
      # Additional knobs the audit surfaces — leave commented placeholders
      # for any knob whose audit-resolved value is "no smoothing applied".
    tongue_angle:
      reference: ["eye_midpoint", "spout_midpoint"]
      # Reference-line endpoints resolved from SessionManifest. Both
      # names must match resolver keys in src/stroke_orofacial/manifest.py.
    windows:
      wide:
        pre_ms: 500
        post_ms: 5000
      tight:
        pre_ms: 100
        post_ms: 1000
    peak_detection:
      # Filled from Task 1 audit. Common knobs: min_height, min_distance_ms.
      ...
```

Place the new sub-block under the existing `dlc_kinematics:` block.
Load-time parsing uses the existing `load_defaults()` pattern.

#### 2b. Conditional `configs/animals.yaml` extension

Only if Task 1 audit verdict is "per-animal variation present", extend
`configs/animals.yaml` per-animal with the proposed schema. Mirror the
existing `kinematics_baselines:` placement under each animal's block.
If audit verdict is cohort-uniform, skip 2b.

#### 2c. Add `PathResolver.kinematic_features_parquet()` helper

In `src/stroke_orofacial/paths.py`, add (near the existing 7a.2
`interpolated_trace()` method):

```python
def kinematic_features_parquet(
    self,
    bodypart: str,
    animal: str,
    date: datetime.date,
) -> Path:
    """Return the output path for a Phase 7a.3 per-frame kinematic-features parquet.

    E.g. ``<outputs>/dlc_kinematics/features/tongue/PS46/20250307.parquet``

    Parameters
    ----------
    bodypart : {"tongue", "jaw"}
    animal : str
    date : datetime.date

    Parent directory is created eagerly. Mirrors ``pipeline_outputs``'s
    ``output_root`` test-override behavior.
    """
    date_str = date.strftime("%Y%m%d")
    out = (
        self.pipeline_outputs(subdir="dlc_kinematics")
        / "features"
        / bodypart
        / animal
        / f"{date_str}.parquet"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
```

#### 2d. Add `PathResolver.kinematic_endpoints_json()` helper

```python
def kinematic_endpoints_json(
    self,
    animal: str,
    date: datetime.date,
) -> Path:
    """Return the output path for a Phase 7a.3 per-trial kinematic-endpoints JSON.

    E.g. ``<outputs>/dlc_kinematics/endpoints/PS46/20250307.json``

    One JSON file per (animal, date) — both bodyparts' per-trial scalars
    are merged into a single JSON to keep per-trial co-indexing trivial
    for downstream readers.

    Parent directory is created eagerly.
    """
    date_str = date.strftime("%Y%m%d")
    out = (
        self.pipeline_outputs(subdir="dlc_kinematics")
        / "endpoints"
        / animal
        / f"{date_str}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
```

#### 2e. Tests

Add to `tests/test_paths.py` (extend existing file):

- `test_kinematic_features_parquet_path` — `PathResolver(output_root=
  tmp_path).kinematic_features_parquet("tongue", "PS46",
  date(2025, 3, 7))` returns `tmp_path / "dlc_kinematics/features/
  tongue/PS46/20250307.parquet"`; parent directory exists.
- `test_kinematic_features_parquet_jaw` — same for jaw.
- `test_kinematic_endpoints_json_path` — `PathResolver(output_root=
  tmp_path).kinematic_endpoints_json("PS46", date(2025, 3, 7))`
  returns `tmp_path / "dlc_kinematics/endpoints/PS46/20250307.json"`;
  parent directory exists.
- `test_kinematic_features_and_endpoints_disjoint` — features and
  endpoints paths share no parent below `dlc_kinematics/` (proves
  the directory split — features per-bodypart subdir, endpoints
  flat per-animal).

#### 2f. Run tests + ruff

```bash
pytest tests/test_paths.py -v
pytest
ruff check src/stroke_orofacial/paths.py tests/test_paths.py configs/defaults.yaml
```

#### 2g. Commit

```bash
git add configs/defaults.yaml src/stroke_orofacial/paths.py tests/test_paths.py
# Plus configs/animals.yaml ONLY if Task 1 audit demanded it.
git diff --cached --stat
git commit -m "feat(config,paths): dlc_kinematics.feature_extraction defaults + 7a.3 path helpers"
git push
```

**STOP and report to Priya:**
- diff of `configs/defaults.yaml` showing the new
  `feature_extraction:` sub-block,
- diff of `configs/animals.yaml` if extended, or note "cohort-uniform,
  no animals.yaml change",
- new-tests count + full-suite pass count,
- any surprise in the YAML merge.

---

### Task 3 — `src/stroke_orofacial/dlc_kinematics/features.py` implementation

**Only run Task 3 after Priya acknowledges the Task 2 report.**

**Goal.** Port the velocity / angle / amplitude / per-trial-aggregator
algorithms from the vendored cells into one consolidated module.

#### 3a. Read the vendored cells end-to-end

Before touching the module, read both vendored files in full:

```bash
wc -l docs/legacy_snippets/tongue_velocity_amplitude_angle.py
wc -l docs/legacy_snippets/jaw_velocity_amplitude.py
```

Build a mental map of:
- the velocity computation (gradient → smoothing → optional
  magnitude/component split),
- the tongue angle computation: which manifest-resolver keys produce
  `eye_midpoint`/`spout_midpoint` coordinates? How does the legacy
  compute the deviation angle? (atan2 of cross/dot? Signed vs. unsigned?
  Radians vs. degrees? Per-frame or only at peak?)
- the per-trial windowing (reward-aligned slicing → wide/tight
  windows),
- the per-trial aggregators (max amplitude, peak velocity, peak angle —
  by what measure: absolute peak, signed peak, RMS, percentile?),
- the legacy NPZ schema(s) — note exact array names + dtypes for the
  parity comparison in Task 5.

Do not copy-paste. Transcribe the algorithm; verify behavior with
unit tests in Task 4; verify parity in Task 5.

#### 3b. Module structure

Replace `src/stroke_orofacial/dlc_kinematics/features.py` (currently a
stub or empty file from earlier scaffolding) with the full
implementation:

```python
"""Phase 7a.3 — per-frame velocity / tongue angle + per-trial scalars.

Ports velocity / angle / amplitude cells from
``docs/legacy_snippets/tongue_velocity_amplitude_angle.py`` and
``docs/legacy_snippets/jaw_velocity_amplitude.py`` into one
consolidated module.

Public API
----------
``build_kinematic_features(manifest, resolver, params, *, overwrite)``
    Session-level driver. Reads 7a.2 interpolated_traces parquet for
    both bodyparts, computes per-frame velocity (tongue + jaw) and
    per-frame tongue angle, computes per-trial scalars over wide +
    tight windows, writes per-frame parquet (one per bodypart) +
    per-trial JSON.
``build_kinematic_features_by_animal_date(animal, date, resolver, **kwargs)``
    Convenience wrapper.
``KinematicFeaturesResult``
    Dataclass carrying per-frame arrays + per-trial scalar dicts +
    metadata.

Output schemas (locked by 7a.3 DECISIONS entry)
-----------------------------------------------
Per-frame parquet (one row per camera frame):
- frame_idx (int64)
- velocity (float64)              # tongue or jaw, per file
- velocity_x (float64), velocity_y (float64)  # if legacy splits components
- angle_deg (float64)             # tongue file ONLY; jaw file omits
[plus any additional production columns surfaced by Task 1]

Per-trial JSON (one file per session, both bodyparts merged):
{
  "schema_version": "7a.3",
  "animal": "PS46",
  "date": "2025-03-07",
  "n_trials": <int>,
  "trial_indices": [...],
  "windows": {
    "wide":  {"pre_ms": 500, "post_ms": 5000},
    "tight": {"pre_ms": 100, "post_ms": 1000}
  },
  "tongue": {
    "wide":  {"amplitude_max": [...], "velocity_peak": [...], "angle_peak_deg": [...]},
    "tight": {"amplitude_max": [...], "velocity_peak": [...], "angle_peak_deg": [...]}
  },
  "jaw": {
    "wide":  {"amplitude_max": [...], "velocity_peak": [...]},
    "tight": {"amplitude_max": [...], "velocity_peak": [...]}
  },
  "metadata": {
    "fps": <float>,
    "interpolation_version": "v5p3",
    "feature_extraction_version": "7a.3"
  }
}
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

FEATURE_EXTRACTION_VERSION = "7a.3"


@dataclass
class KinematicFeaturesResult:
    # Per-frame arrays, per bodypart
    tongue_velocity: np.ndarray
    tongue_angle_deg: np.ndarray
    jaw_velocity: np.ndarray
    # Per-trial scalar arrays, per (bodypart, window)
    tongue_wide_amplitude_max: np.ndarray
    tongue_wide_velocity_peak: np.ndarray
    tongue_wide_angle_peak_deg: np.ndarray
    tongue_tight_amplitude_max: np.ndarray
    tongue_tight_velocity_peak: np.ndarray
    tongue_tight_angle_peak_deg: np.ndarray
    jaw_wide_amplitude_max: np.ndarray
    jaw_wide_velocity_peak: np.ndarray
    jaw_tight_amplitude_max: np.ndarray
    jaw_tight_velocity_peak: np.ndarray
    # Trial bookkeeping
    trial_indices: np.ndarray
    n_trials: int
    fps: float
    animal: str
    date: dt.date


def _compute_velocity(
    x: np.ndarray, y: np.ndarray, fps: float, *, smoothing_window_frames: int, smoothing_filter: str,
) -> np.ndarray:
    """Per-frame speed (or velocity vector magnitude) on the centered trace."""
    ...


def _compute_tongue_angle(
    x: np.ndarray, y: np.ndarray,
    eye_midpoint: tuple[float, float],
    spout_midpoint: tuple[float, float],
) -> np.ndarray:
    """Per-frame angular deviation of (x, y) from the eye→spout reference line.

    Reference line direction: ``v_ref = spout_midpoint - eye_midpoint``.
    Per-frame target direction: ``v_t = (x[t], y[t]) - eye_midpoint``.
    Returns the signed angle in degrees between ``v_t`` and ``v_ref``,
    using ``atan2(cross(v_ref, v_t), dot(v_ref, v_t))``.

    NaN frames in (x, y) propagate to NaN angles.
    """
    ...


def _slice_per_trial(
    arr: np.ndarray,
    reward_centers_cam: np.ndarray,
    fps: float,
    *,
    pre_ms: float,
    post_ms: float,
) -> list[np.ndarray]:
    """Return a list of length n_trials of windowed slices."""
    ...


def _aggregate_per_trial(
    slices: list[np.ndarray], *, agg: Literal["max", "peak_signed", "max_abs"],
) -> np.ndarray:
    """Aggregate each trial's slice into a single scalar."""
    ...


def _build_features_core(
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict,
    animal_info: AnimalInfo | None = None,
) -> KinematicFeaturesResult:
    """Pure function — reads 7a.2 parquets, computes features, returns result.

    No I/O writes. Loads tongue + jaw interpolated_trace parquets,
    resolves eye_midpoint + spout_midpoint from manifest, computes
    per-frame velocity + tongue angle, computes per-trial scalars over
    wide + tight windows, packages everything into the result dataclass.
    """
    ...


def build_kinematic_features(
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path] | None:
    """Build kinematic features for one session (both bodyparts).

    Writes:
      - ``{outputs}/dlc_kinematics/features/tongue/{animal}/{date}.parquet``
      - ``{outputs}/dlc_kinematics/features/jaw/{animal}/{date}.parquet``
      - ``{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json``

    Returns a dict mapping {"tongue_parquet", "jaw_parquet",
    "endpoints_json"} -> Path on success, or None if overwrite="skip"
    and ALL three exist (partial existence still triggers full rebuild
    under "skip" — partial output is treated as torn write).

    Parquets are written via pyarrow with snappy compression. JSON is
    written atomically (temp + rename) to survive concurrent reads.
    """
    ...


def build_kinematic_features_by_animal_date(
    animal: str,
    date: dt.date,
    resolver: PathResolver,
    **kwargs,
) -> dict[str, Path] | None:
    """Convenience wrapper — builds manifest internally."""
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info, analysis_type="kinematics",
    )
    return build_kinematic_features(manifest, resolver, **kwargs)
```

Export the public symbols from
`src/stroke_orofacial/dlc_kinematics/__init__.py`:

```python
from stroke_orofacial.dlc_kinematics.features import (
    KinematicFeaturesResult,
    build_kinematic_features,
    build_kinematic_features_by_animal_date,
)

# Append to existing __all__; do NOT replace the 7a.2 entries.
```

#### 3c. Per-frame parquet schema

For each bodypart's parquet, file-level metadata (analogous to 7a.2's
9 keys, mirroring the schema for downstream consistency):
`fps, n_frames, animal, date, bodypart, feature_extraction_version,
interpolation_version, smoothing_window_frames, smoothing_filter`.

Tongue parquet adds: `angle_reference_eye_x, angle_reference_eye_y,
angle_reference_spout_x, angle_reference_spout_y` — the resolved
reference-point coordinates used for the angle computation. (Forensic
reproducibility: the angle depends on which reference points were
resolved at compute time.)

#### 3d. Per-trial JSON atomic write

```python
import tempfile
import os

def _write_json_atomic(path: Path, payload: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.stem + ".", suffix=".json.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=False)
        os.replace(tmp, path)  # atomic on POSIX + Windows
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

#### 3e. Ruff + smoke import

```bash
ruff check src/stroke_orofacial/dlc_kinematics/features.py src/stroke_orofacial/dlc_kinematics/__init__.py
python -c "from stroke_orofacial.dlc_kinematics import build_kinematic_features, KinematicFeaturesResult; print('ok')"
```

Unit tests come in Task 4. Task 3 ends at a clean module that imports
and passes ruff.

#### 3f. Commit

```bash
git add src/stroke_orofacial/dlc_kinematics/features.py src/stroke_orofacial/dlc_kinematics/__init__.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): velocity/angle/amplitude features module (7a.3)"
git push
```

**STOP and report to Priya:**
- line count of `features.py`,
- list of private helpers + their line-count estimate,
- the per-trial aggregator decision (`max`, `max_abs`, `peak_signed`,
  etc.) for each scalar — this is a transcription decision from Task 1
  vendored cells; report it explicitly so Priya can sanity-check,
- any unresolved algorithmic questions from the vendored cells,
- confirmation that the module imports cleanly + ruff passes.

---

### Task 4 — Unit tests

**Only run Task 4 after Priya acknowledges the Task 3 report.**

**Goal.** Pin every layer of the algorithm + module API surface so
later edits cannot silently regress.

Create `tests/test_dlc_features.py`. Every test uses
`PathResolver(output_root=tmp_path)` — do NOT write to the real
`stroke_orofacial_pipeline_outputs/` tree (CLAUDE.md testing
conventions).

#### 4a. Test list (target ~14 tests)

1. `test_compute_velocity_constant_motion` — synthetic linear motion
   gives constant velocity equal to `√(vx² + vy²)`.
2. `test_compute_velocity_smoothing_kernel_applied` — pre-smoothing
   the trace with a known filter changes the velocity in the expected
   direction; smoothing-window-1 reduces to raw gradient.
3. `test_compute_velocity_nan_propagation` — NaN frames in (x, y)
   propagate to NaN velocity.
4. `test_compute_tongue_angle_zero_on_reference_line` — when
   (x[t], y[t]) is on the eye→spout reference line, angle is 0
   degrees.
5. `test_compute_tongue_angle_perpendicular` — when (x[t], y[t]) is
   perpendicular to the reference line at eye_midpoint, angle is
   ±90 degrees (sign per the cross-product convention chosen).
6. `test_compute_tongue_angle_signed_consistency` — angle sign flips
   when the reference direction is reversed.
7. `test_compute_tongue_angle_nan_propagation` — NaN positions →
   NaN angles.
8. `test_slice_per_trial_window_extents` — given known reward centers
   + fps, the slices have the expected length and start/end indices.
9. `test_slice_per_trial_clipped_at_session_edges` — a reward near
   the start or end of the session yields a shorter slice (or NaN-
   padded? port the legacy behavior — note which in the test docstring).
10. `test_aggregate_per_trial_max_against_known_arrays` — given
    hand-built per-trial slices, the aggregator returns the expected
    scalar for each trial.
11. `test_build_features_emits_three_files` — `build_kinematic_features`
    on a synthetic manifest writes both bodypart parquets + the JSON.
12. `test_build_features_overwrite_skip_respects_existing` — with
    `overwrite="skip"` and all three files present, returns None;
    with `overwrite="force"`, overwrites.
13. `test_build_features_overwrite_skip_partial_rebuild` — with
    `overwrite="skip"` and only the JSON missing, rebuilds (treats
    partial as torn write).
14. `test_endpoints_json_schema` — emitted JSON has the expected
    top-level keys (`schema_version`, `animal`, `date`, `n_trials`,
    `windows`, `tongue`, `jaw`, `metadata`); per-trial arrays have
    length `n_trials`.

Helper fixtures: `_make_synthetic_interpolated_trace_parquet(tmp_path,
animal, date, bodypart, n_frames, ...)` — writes a 7a.2-shaped parquet
that the features module can consume. `_make_minimal_manifest(animal,
date, tmp_path)` — analogous to the 7a.2 fixture.

#### 4b. Run + commit

```bash
pytest tests/test_dlc_features.py -v
pytest
ruff check tests/test_dlc_features.py

git add tests/test_dlc_features.py
git diff --cached --stat
git commit -m "test(dlc_features): unit tests for velocity/angle/amplitude (7a.3)"
git push
```

**STOP and report to Priya:**
- the test-name list with pass status,
- full-suite pass/skip/fail counts,
- any synthetic-fixture implementation surprise.

---

### Task 5 — Parity harness + cohort run

**Only run Task 5 after Priya acknowledges the Task 4 report.**

**Goal.** Run consolidated 7a.3 outputs against legacy NPZs on the
14-session × 2-bodypart cohort. Bit-identity (or `atol=1e-6`) on every
in-scope dim is the acceptance gate.

#### 5a. Build the parity harness

Create `tests/scripts/parity_phase7a3_features.py` modelled on
`tests/scripts/parity_phase7a_interpolation.py` (the 7a.2 harness).
Reuse the scope filter + `atol=1e-6` comparator infrastructure.

Per-frame comparisons:
- `tongue_velocity` consolidated vs. legacy.
- `jaw_velocity` consolidated vs. legacy.
- `tongue_angle_deg` consolidated vs. legacy.

Per-trial scalar comparisons (per bodypart, per window):
- `amplitude_max`, `velocity_peak`, `angle_peak_deg` (tongue only).

Legacy NPZ paths resolved at Task 1 audit (record them in the harness
as a small lookup). Likely subdir pattern:
`{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/
{animal}_{bodypart}_kinematics/<feature_subdir>/...npz`.

#### 5b. Build the cohort outputs

Run the consolidated module across the 14-session set:

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_kinematic_features_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
SESSIONS = [
    # 9 primary
    ("PS46", dt.date(2025, 3, 7)),
    # ... fill from 7a.2 parity scope ...
    # 3 stress
    ("PS51", dt.date(2025, 4, 30)),
    # ... etc ...
    # 2 late post-stroke
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]
for animal, date in SESSIONS:
    paths = build_kinematic_features_by_animal_date(
        animal=animal, date=date, resolver=resolver, overwrite="force",
    )
    print(animal, date, paths)
PY
```

Confirm all 14 sessions emitted both parquets + JSON.

#### 5c. Run the parity harness

```bash
python tests/scripts/parity_phase7a3_features.py --sessions auto | tee /tmp/parity_7a3.log
echo "exit=$?"
```

Expected:
- exit code `0` (all pass),
- `by_status = {'pass': N, 'skip_missing': M}` where N + M = total
  comparisons (28 per-frame velocity + 14 per-frame angle + per-trial
  scalars × 2 windows × bodyparts).
- Per-comparison `max|Δ|` reports — ideally `0.000e+00` (bit-
  identical), tolerated up to `atol=1e-6`.

If ANY comparison returns `status = fail`:
- capture the (animal, date, bodypart, dim, window) tuple and
  `max|Δ|`,
- **STOP and report** — do not widen the tolerance, do not advance to
  Task 6. A fail is the signal that the port has a bug or the legacy
  NPZ uses a different convention; Priya decides triage.

#### 5d. Commit

```bash
git add tests/scripts/parity_phase7a3_features.py
git diff --cached --stat
git commit -m "feat(parity): Phase 7a.3 features parity harness (14-session × 2-bodypart)"
git push
```

**STOP and report to Priya:**
- cohort emit confirmation (14 sessions × 3 files each = 42 files),
- per-comparison `by_status` count,
- per-session `max|Δ|` table for every comparison dim,
- any skip_missing patterns,
- any fail → STOP AND WAIT for Priya's triage decision.

---

### Task 6 — DECISIONS + MIGRATION_LOG entries

**Only run Task 6 after Task 5 reports all-pass.**

#### 6a. `docs/DECISIONS.md` — Phase 7a.3 entry

Insert a new dated entry above the existing reverse-chronological
entries. Suggested template (fill bracketed values from the actual
audit + parity results):

```markdown
## 2026-04-2X — Phase 7a.3 kinematic features (velocity, angle, amplitude)

**Context.** Phase 7a.3 ported the per-frame and per-trial kinematic
feature computations from `20260203_..._tongue.ipynb` and
`20260416_..._jaw.ipynb` (the same canonical notebooks vendored for
7a.2's interpolation port) into
`src/stroke_orofacial/dlc_kinematics/features.py`. The output schemas
and window bounds are now standing architectural decisions for all
downstream phases (7a.4 face-velocity / PSD branches, 7a.5 per-trial
PSD endpoints).

**Decisions enacted.**

1. **Per-frame features parquet** at
   `{outputs}/dlc_kinematics/features/{bodypart}/{animal}/{date}.parquet`.
   Columns: <fill from §3c>. File-level metadata: <fill>.
2. **Per-trial endpoints JSON** at
   `{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json`. Schema
   v7a.3 with both bodyparts merged for per-trial co-indexing.
3. **Window bounds locked**: wide = (-500, +5000) ms, tight = (-100,
   +1000) ms. Driven by Task 1 audit; if per-animal variation was
   found, the windows live in `animals.yaml`, otherwise in
   `defaults.yaml`. Locked: <fill which file>.
4. **Tongue angle reference**: line from `eye_midpoint` to
   `spout_midpoint`. Per-frame angle = signed angle between the
   per-frame (x, y) - eye_midpoint vector and the reference line,
   computed via `atan2(cross, dot)` in degrees. Reference-point
   coordinates baked into the parquet metadata for forensic
   reproducibility.
5. **Per-trial aggregator semantics**: <fill from Task 3 transcription
   decisions — e.g. amplitude_max is `max(|y_final|)` over the window,
   velocity_peak is `max(velocity)`, angle_peak_deg is
   `peak_signed(angle_deg)`>.

**Parity verification (14-session set at atol=1e-6).** <PASTE
by_status table from Task 5c run>. <Bit-identical? Within tolerance?>
on all in-scope dims under scipy 1.17.1.

**Enforced at.** `configs/defaults.yaml dlc_kinematics.feature_extraction:`,
`src/stroke_orofacial/dlc_kinematics/features.py` module,
`tests/scripts/parity_phase7a3_features.py`,
`tests/test_dlc_features.py`.

**Forward implication.** 7a.4 (whisker/face-velocity/PSD) consumes
the per-frame features parquets directly. 7a.5 (per-trial PSD
endpoints) extends the per-trial endpoints JSON with PSD scalars
(new keys under `tongue.<window>` / `jaw.<window>`). Downstream
edits that change the per-frame parquet columns or the JSON schema
require a DECISIONS entry.
```

#### 6b. `docs/MIGRATION_LOG.md` — Phase 7a.3 entry

Append after the Phase 7a.2 entry. Standard format:

```markdown
## Phase 7a.3 — kinematic features port (velocity, angle, amplitude)

**Date:** 2026-04-2X
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.3-kinematic-features-tongue-jaw`
**Branch:** `phase/7a.3-kinematic-features-tongue-jaw`

**Scope.** Per-frame velocity (tongue + jaw), per-frame tongue angle
(deviation from eye_midpoint → spout_midpoint reference line), and
per-trial scalars (amplitude max, velocity peak, angle peak) over
wide (-500, +5000 ms) and tight (-100, +1000 ms) reward-aligned
windows. First downstream phase consuming the 7a.2
interpolated_traces parquets.

**What landed.**

1. Vendored cells under `docs/legacy_snippets/` (tongue + jaw,
   SHA256 provenance per 7a.0 pattern).
2. `configs/defaults.yaml dlc_kinematics.feature_extraction:` block.
3. <`configs/animals.yaml` per-animal `feature_extraction:` extension
   if Task 1 audit demanded it, OR "no animals.yaml change — cohort
   uniform">.
4. `PathResolver.kinematic_features_parquet()` and
   `PathResolver.kinematic_endpoints_json()` helpers.
5. `src/stroke_orofacial/dlc_kinematics/features.py` (~<N>-line
   module) with `KinematicFeaturesResult` dataclass, per-frame +
   per-trial helpers, session writer.
6. <N> unit tests in `tests/test_dlc_features.py`.
7. `tests/scripts/parity_phase7a3_features.py` parity harness;
   14-session × 2-bodypart cohort returns `by_status = <PASTE>`.

**Behavior differences vs. legacy notebooks.**

- Per-frame and per-trial outputs split across parquet (per-frame)
  and JSON (per-trial). Legacy emits monolithic NPZs containing
  both; the split keeps per-trial JSON readable / queryable
  without parquet tooling.
- Per-trial JSON merges both bodyparts into one file per (animal,
  date) for per-trial co-indexing. Legacy keeps tongue and jaw
  scalars in separate per-bodypart NPZs.
- Tongue angle reference-point coordinates are baked into the
  parquet metadata (forensic reproducibility). Legacy did not
  capture them post-hoc.
- Otherwise within `atol=1e-6` (or bit-identical, per Task 5
  results) on the 14-session parity set.

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified (legacy NPZs read-only). Rule 2 — no legacy-repo edits.
Rule 6 — new outputs live under
`stroke_orofacial_pipeline_outputs/dlc_kinematics/features/` and
`/endpoints/`. Rule 8 — feature branch, tag pushed post-merge.

**Forward follow-ups.** Phase 7a.4 (whisker / face-velocity / PSD
branches of strategy §7) and Phase 7a.5 (per-trial PSD endpoints)
consume these outputs. Phase 7b/7c (tongue/jaw per-trial endpoints
+ mismatch classifier) is the next downstream block after 7a.5.
```

#### 6c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.3): DECISIONS + MIGRATION_LOG entries"
git push
```

---

### Task 7 — PR + tag

#### 7a. Open the PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.3: kinematic features (velocity, angle, amplitude) — tongue + jaw" \
  --body - <<'EOF'
Phase 7a.3 ports the per-frame velocity / tongue angle / per-trial
scalar computations from the canonical tongue + jaw notebooks. First
downstream phase consuming the 7a.2 interpolated_traces parquets.

## What lands

1. `docs/legacy_snippets/{tongue_velocity_amplitude_angle,jaw_velocity_amplitude}.py`
   — vendored cells with SHA256 provenance (7a.0 pattern).
2. `src/stroke_orofacial/dlc_kinematics/features.py` — full module
   with per-frame velocity (tongue + jaw), per-frame tongue angle,
   per-trial scalars (amplitude max, velocity peak, angle peak)
   over wide + tight reward-aligned windows.
3. `configs/defaults.yaml dlc_kinematics.feature_extraction:` block.
4. `configs/animals.yaml` per-animal extension <if Task 1 audit
   demanded it>.
5. `PathResolver.kinematic_features_parquet()` and
   `kinematic_endpoints_json()` helpers.
6. `tests/test_dlc_features.py` — <N> unit tests.
7. `tests/scripts/parity_phase7a3_features.py` — 14-session ×
   2-bodypart parity harness.
8. DECISIONS entry codifying schemas + window bounds + angle
   reference-line definition.
9. MIGRATION_LOG Phase 7a.3 entry.

## Parity / tests / ruff

- Full pytest: <PASTE> passed / <PASTE> skipped / 0 failed
  (+<N> new tests in test_dlc_features.py).
- Ruff clean on all touched `.py` files.
- Parity harness `--sessions auto` exit code 0;
  by_status = <PASTE>.
- Cohort emit: 14 sessions × (tongue_parquet + jaw_parquet +
  endpoints_json) = 42 files written.
- Max|Δ| on all in-scope dims: <PASTE> (target 0.000e+00 for bit-
  identical; tolerated up to 1e-6 atol).

## Tag on merge

`v7a.3-kinematic-features-tongue-jaw`

## Not in this PR

- Phase 7a.4 (whisker / face-velocity / PSD) — separate phase
  consuming these per-frame parquets.
- Phase 7a.5 (per-trial PSD endpoints) — separate phase extending
  the per-trial endpoints JSON.
- Phase 7b/7c (tongue/jaw per-trial endpoints + mismatch
  classifier) — downstream.
EOF
```

#### 7b. Final verification

```bash
# Commits on the branch since main:
git log --oneline origin/main..HEAD
# Expected: 8 commits — kickoff, vendoring, config+paths, features module,
# unit tests, parity, DECISIONS+MIGRATION_LOG, [tag commit lives on main, not branch].

# Touched file summary:
git diff --stat origin/main..HEAD
# Expected paths:
#   docs/prompts/phase-7a.3-kickoff.md                          (preflight)
#   docs/legacy_snippets/tongue_velocity_amplitude_angle.py     (task 1)
#   docs/legacy_snippets/jaw_velocity_amplitude.py              (task 1)
#   configs/defaults.yaml                                        (task 2)
#   src/stroke_orofacial/paths.py                                (task 2)
#   tests/test_paths.py                                          (task 2)
#   configs/animals.yaml                                         (task 2, IF audit demanded)
#   src/stroke_orofacial/dlc_kinematics/features.py              (task 3)
#   src/stroke_orofacial/dlc_kinematics/__init__.py              (task 3)
#   tests/test_dlc_features.py                                   (task 4)
#   tests/scripts/parity_phase7a3_features.py                    (task 5)
#   docs/DECISIONS.md                                            (task 6)
#   docs/MIGRATION_LOG.md                                        (task 6)

# Ruff + pytest one more time for the PR record:
ruff check .
pytest -q

# After PR merges on main, tag and push:
# git checkout main && git pull
# git tag -a v7a.3-kinematic-features-tongue-jaw <merge-sha> -m "Phase 7a.3: kinematic features (velocity, angle, amplitude) — tongue + jaw"
# git push origin v7a.3-kinematic-features-tongue-jaw
```

Report to Priya: PR URL, the 7 commit SHAs (kickoff + 6 task
commits + [Task 7 PR-open is the same as Task 6 commit; only 7
total]), ruff + pytest counts, parity `by_status` + max|Δ|
table, cohort emit confirmation. STOP. **Do not merge.** Priya
reviews, merges from the GitHub UI, then tags on the merge commit
herself.

---

## Constraints (across all 7 tasks)

- **Phase 7a.3 scope is per-frame velocity/angle + per-trial
  scalars + parity ONLY.** No PSD, no whisker/face-velocity, no
  Phase 7b/7c endpoint modules in this PR. No notebook work
  (notebooks orchestrate but do not implement, per CLAUDE.md
  conventions). No changes to `interpolation.py` or 7a.2's parquet
  schema — the 7 columns + 9 metadata keys are LOCKED.
- **Eight commits, not one.** Each task = one commit (Task 0 /
  preflight bundled with the kickoff commit). Review granularity
  matters for a multi-hundred-line port.
- **Stop-and-report between tasks 1 / 2 / 3 / 4 / 5.** Tasks 6 and 7
  chain through only after Task 5 reports all-pass on parity.
- **No MICROSCOPE writes.** All MICROSCOPE access is `np.load` /
  `pd.read_parquet` / `Path.glob` / read-only notebook reads only.
  Consolidated outputs go under `stroke_orofacial_pipeline_outputs/
  dlc_kinematics/features/` and `/endpoints/`.
- **No force-push.** All pushes are additive to
  `phase/7a.3-kinematic-features-tongue-jaw`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit, per CLAUDE.md §"Git discipline".
- **If the parity harness reports any `status = fail` in Task 5c:**
  STOP. Do not widen the tolerance. Do not write DECISIONS or
  MIGRATION_LOG entries claiming success. Report the failing
  comparison + max|Δ| + dim + window + scalar metadata mismatch to
  Priya; she decides whether the port has a bug, whether the legacy
  NPZ uses a different convention, or whether the feature definition
  needs revisiting.
- **If Task 1 audit hits an Ambiguous cell:** STOP. Do not silently
  vendor or silently exclude. Report the cell + classification
  reasoning to Priya for decision.
- **If the per-animal audit finds variation that demands
  `animals.yaml` extension:** include the proposed schema in the
  Task 1 report; let Priya approve before Task 2 writes it. Mirror
  existing per-animal blocks (`kinematics_baselines:`,
  `analysis_params.break_thr_*`) for placement style.
- **If `features.py` already contains a non-stub implementation when
  the branch is cut:** STOP. Either someone else is editing
  concurrently or the branch is stale. Ask Priya before proceeding.
- **Legacy snippets under `docs/legacy_snippets/` stay READ-ONLY.**
  Their `# ruff: noqa` + `# fmt: off` headers preserve byte-identity
  with capture time; do NOT edit, reformat, or lint them.
- **The 7a.2 angle reference-line is locked.** `eye_midpoint` →
  `spout_midpoint`. Changes to the reference-point names or
  direction require a DECISIONS entry.
