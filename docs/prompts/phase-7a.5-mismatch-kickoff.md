# Phase 7a.5-mismatch Kickoff — Audit-first investigation of tongue-jaw mismatch trial classifier + visualization

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.5-mismatch-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.4 merged 2026-04-30 as PR #86, tagged
`v7a.4-tongue-visual-and-day-binned`. Phase 7a.3-jaw closed 2026-04-30
as PR #87 (tag `v7a.3-jaw-audit-no-pertrial-features`) — Outcome A
audit-only finding that the jaw notebook contains no per-trial
features beyond what 7a.2 already ports.

Phase 7a.5-mismatch is the next outstanding piece Priya flagged
2026-04-30: the tongue-jaw mismatch trial classifier + visualization
code that lives in the canonical tongue notebook under a markdown
header `## Tongue-jaw mismatch trials`, post-Cell-50. This code:

- **Classifies trials** as mismatch / non-mismatch (criterion TBD by
  audit; likely something like "tongue is licking but jaw isn't
  responding" or vice versa).
- **Plots candidate trials** (saved PNGs on MICROSCOPE per Priya's
  recall).
- **Saves outputs** to disk somewhere on MICROSCOPE — locations
  discovered by Task 1d output-discovery walk.

The 7a.3 V3 audit only walked Cells 33/36/39/42/50 (the per-trial-
features scope chartered for 7a.3 V3). Cells beyond Cell 50 — including
the entire `## Tongue-jaw mismatch trials` section — were not
classified during 7a.3 V3 work. This phase fills that gap.

### Side-finding to anticipate

The 7a.3-jaw audit (PR #87) confirmed the JAW NOTEBOOK has no
per-trial features. But the tongue-jaw mismatch logic in the TONGUE
notebook needs jaw "behavior" timestamps to compare against tongue
licks. So the mismatch cells likely contain jaw per-trial logic
(inline detector, per-trial scalars) that the 7a.3-jaw audit didn't
surface — correctly, given that audit's scope was the jaw notebook
only. **The mismatch audit may turn out to be where jaw per-trial
logic actually lives**, even though jaw-the-notebook has none. This is
worth surfacing explicitly during the audit.

### Audit-first scope (deliberate)

Same pattern as 7a.3-jaw. Task 1 = audit + STOP; Tasks 2-N depend on
findings. Three possible outcome branches considered at Task 1:

- **Outcome A — minimal port**: classifier is simple, plots are
  small. Small module addition + DECISIONS + tests.
- **Outcome B — substantial port**: classifier has its own per-trial
  detection layer, multiple plot families, saved outputs. Full port.
- **Outcome C — partial / refactor**: mid-sized.

### Audit findings (Task 1 STOP-and-report, 2026-04-30)

**Outcome B locked** (sub-variant: hybrid — two modules, single phase).

Section spans cells 51–55 (5 cells, 1903 source lines, all
production). Side-finding the kickoff anticipated CONFIRMED: Cell 53
contains inline jaw per-trial scalars (`jaw_baseline_mean`,
`jaw_baseline_sd`, `jaw_peak_{pos,neg,abs,selected}_deflection`,
`jaw_thresh_abs`, `jaw_thresh_px_used`, `jaw_n_frames_over_thresh`,
`jaw_pass_qc`) — usable jaw per-trial features in their own right,
not just decision intermediates. The 7a.3-jaw audit (PR #87) was
correct that the JAW NOTEBOOK has no per-trial features; the
mismatch port is where the jaw per-trial logic actually lives.

**Classification rule (verbatim from Cell 53):**

```
candidate_no_lick_with_jaw_move = quiet_tongue_pass AND jaw_pass_qc
```

- `quiet_tongue_pass` = strictly zero detected tongue licks in the
  (70, 5000) ms post-reward window, using the same dy/dt slope-rise+fall
  detector as Cell 33 (`SLOPE_THR_PX_PER_S=250`, `RISE_MIN_MS=FALL_MIN_MS=16`,
  `MIN_PEAK_Y_ABS=20`, `PEAK_PAD_MS=52`, no smoothing).
- `jaw_pass_qc` = per-trial baseline (mean+sd over (-500, 0) ms);
  then `|jaw_y - baseline_mean| > max(4·baseline_sd, 4 px)`
  sustained at ≥5/8 density in any rolling 8-frame window inside
  (0, 5000) ms.

**Saved outputs (all found on MICROSCOPE, recent):** 8 per-mouse
canonical CSVs (`*_v5p3.csv`, 37 cols, ~2k–4.5k rows each, mtime
2026-04-17), 264 within-session individual-trial PNGs, 264
within-session 4×2 grid PNGs, 8 cross-session overlay PNGs, 8
cross-session binned PNGs. PS46 sample density: 75 candidates /
2019 trials = 3.7%. All under
`\\research...\Priya\DeepLabCut\O2_analysis\{mouse}\{mouse}_jaw_kinematics\kinematics_figures\centered_eye_midpoint\jaw_tongue_candidate_trials\`.

**Scientific rationale (Priya, 2026-04-30):** post-stroke (bilateral)
lack of licking is NOT due to perceptual or motivational deficits —
demonstrated by trials where the mouse shows post-cue jaw movement
without licking. The dissociation isolates the deficit to **tongue
motor control specifically**: jaw motor system spared (mouse moves
jaw on cue) while tongue motor system impaired (no licking).
Mismatch trials are the primary positive evidence for this
interpretation, not just a QC gate.

**Locked decisions (2026-04-30):**

1. **Sub-variant: hybrid (B1.5).** Two modules, single phase, single
   PR + tag. Cleaner architecture than B1's bundled-into-mismatch
   approach; faster execution than B2's two-PR split.
   - `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py` — public
     module mirroring `tongue_pertrial.py` at smaller scale; jaw
     per-trial scalars from Cell 53 inline-extraction logic. Reusable
     building block for any future jaw-related work.
   - `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py` —
     classifier (consumes `jaw_pertrial` + 7a.3 V3 endpoints JSON) +
     plotter + atomic writers.
2. **Output tree**: `<outputs>/dlc_kinematics/tongue_jaw_mismatch/`
   (consistent with 7a.x family). Per-session candidate-trial parquet
   at `candidate_trials/{animal}/{date}.parquet`; within-session
   figures at `figures_qc/{animal}/{date}/...png`; cross-session
   figures at `cross_session/{animal}/...png`.
3. **Per-session emit cadence** (modern pattern). Legacy 8-per-mouse
   aggregated CSVs not byte-identically reproduced; per-session
   parquet captures the same 37 cols + per-session metadata.
   Cross-mouse aggregation (if downstream demands) is a separate
   step.
4. **`_sessionBaseline_` predecessor**: out of scope.
5. **Per-mouse override infrastructure**: dropped. YAGNI; if per-mouse
   overrides ever become needed, the `detector_per_cell:` /
   `bout_per_cell:` precedent from 7a.3 V3 / 7a.4 extends naturally.
6. **Parity scope**: standing 14-session envelope. PS54/2025-05-12
   skip_missing. Cohort run + legacy_approximate parity at
   `atol=1e-6` against saved `*_v5p3.csv` files.

### Scope NOT in this phase

- Re-running 7a.3 V3 / 7a.4 / 7a.2 / 7a.3-jaw work (all shipped + cohort-validated).
- Whisker / face-velocity / PSD branches (separate phases per strategy §7).
- Cohort-wide 7a.2/7a.3 upstream re-emit (deferred from 7a.4 as a
  publication-grade follow-up).
- Green-field jaw per-trial design (deferred from 7a.3-jaw — separate
  phase if pursued; the mismatch audit may surface adjacent inline
  logic but full green-field design stays separate).

---

## Plan shape (per CLAUDE.md phase-plan requirements)

Items 1 + 5 concrete now; items 2-4 lock at Task 1 STOP.

### 1. Legacy file disambiguation

One source notebook (same as 7a.3 V3 + 7a.4):
- `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
- SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
- Already vendored byte-identically as Cells 33/36/39/42/50 in `docs/legacy_snippets/tongue_pertrial_features.py` (Phase 7a.3 V3, commit `0b78128`); the mismatch section is OUTSIDE that vendor scope.

3-tier rule resolution: trust 7a.2's prior 3-tier resolution for the
parent notebook; this phase adds no new candidates, only new cell
selection within the same already-canonical notebook.

### 2. Dead code identification

Cell-level walk of the `## Tongue-jaw mismatch trials` section
(Task 1b). Each cell classified as production / exploratory /
deprecated / ambiguous. Pay specific attention to:

- **Inline jaw-behavior detection** — if mismatch logic computes its
  own jaw lick-equivalent timestamps, the detector code is a
  jaw-per-trial-features finding adjacent to mismatch.
- **Cross-bodypart classification rule** — what predicate defines a
  mismatch trial?
- **Plot families** — same shape question as 7a.4 Cell 50 visual gate
  (which families, what inputs, where saved).
- **Saved outputs on MICROSCOPE** — found via Task 1d.

### 3. Sub-phase breakdown

Locks at Task 1 STOP. Sketches:

- **Outcome A** (minimal port): Tasks 2-5. Vendor cells + small
  classifier module + tests + DECISIONS + PR. ~3-5 commits.
- **Outcome B** (substantial port): Tasks 2-7 mirror 7a.3 V3 structure.
  Vendor + config/paths + module + tests + parity harness +
  DECISIONS + PR. ~7-10 commits.
- **Outcome C** (partial / refactor): Tasks 2-5. Mid-sized.

### 4. Parity strategy

Locks at Task 1 STOP based on what's found. If audit finds mismatch
classifier emits CSV/NPZ outputs on MICROSCOPE: legacy_approximate
parity harness modeled on 7a.3 V3's. If audit finds only PNG outputs:
visual gate harness modeled on 7a.4's. If neither (Outcome A unlikely
case where mismatch is in-memory only): synthetic unit tests.

### 5. Hardcoded constants

Knobs captured by Task 1 audit move to `configs/defaults.yaml` under
a new sub-block (likely `dlc_kinematics.tongue_jaw_mismatch:` or
similar — exact naming locked at Task 2 if Outcome B/C). Existing
7a.2 / 7a.3 V3 / 7a.4 schemas stay LOCKED.

---

## Execute on branch `phase/7a.5-mismatch`

### Preflight

```bash
git checkout main
git pull
git status                           # clean working tree
git log --oneline -1                 # at PR #87 merge commit (7a.3-jaw close)
git tag --list | grep -E 'v7a\.(3|3-jaw|4)'   # 7a.3, 7a.3-jaw, 7a.4 tags present locally

git checkout -b phase/7a.5-mismatch
git push -u origin phase/7a.5-mismatch
```

Activate the conda environment per CLAUDE.md:

```bash
conda activate stroke_orofacial
which python                         # path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"  # must succeed
pytest --collect-only                # baseline 623 tests + 35 skipped (unchanged from 7a.4)
```

Confirm MICROSCOPE access to the canonical tongue notebook (same as
7a.3 V3 + 7a.4 audits):

```bash
ls -la "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb"
# Should show ~404 MB file size + recent mtime
```

### Task 0 — Kickoff prep (this commit, Cowork's job)

Cowork writes this kickoff doc. Priya commits + pushes + pastes the
handoff line. Do not re-execute Task 0 from CC.

### Task 1 — Comprehensive mismatch-section audit

**Goal.** Walk the `## Tongue-jaw mismatch trials` section of the
canonical tongue notebook. Classify every cell. Identify the
classification rule. Inventory plot families. Discover saved outputs.
Surface any inline jaw-per-trial logic that 7a.3-jaw audit didn't
have scope to find. Report findings sufficient for Priya to pick
Outcome A / B / C.

#### 1a. Notebook provenance + section location

Re-confirm the canonical tongue notebook SHA256 matches the vendor
header in `docs/legacy_snippets/tongue_pertrial_features.py`
(`ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).
If the SHA differs, the notebook has been edited upstream — STOP and
report.

Locate the `## Tongue-jaw mismatch trials` markdown header:

```python
import json
from pathlib import Path
nb_path = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb")
nb = json.loads(nb_path.read_text(encoding="utf-8"))
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "markdown":
        src = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        if "Tongue-jaw mismatch" in src or "tongue-jaw mismatch" in src.lower():
            print(f"cell {i}: {src[:200]}")
```

Capture the cell-index range covered by the mismatch section (header
to next H2 markdown header or end-of-notebook). Record cell count +
total source-line count for that range.

#### 1b. Per-cell walk + classification

Iterate through every cell in the mismatch section. For each, record:

- **Cell index** (0-indexed in the notebook).
- **First non-empty source line** (semantic anchor).
- **Length** in lines.
- **Classification**: production / exploratory / deprecated /
  ambiguous.
- **Imports** specific to this cell.
- **Inputs read**: tongue per-trial CSVs/NPZs (from 7a.3 V3 vendor
  scope — Cells 33/36/39/42/50 outputs), jaw interpolation parquets,
  raw DLC parquets, alignment templates, custom files.
- **Outputs written**: filenames emitted (CSV / NPZ / parquet / PNG).
  CRITICAL — this drives Task 1d output discovery.
- **Match to existing patterns**: if cell mirrors structure of
  Cell 50 visual gate (per-trial filtering + plotting), Cell 42 dyn
  (cross-bodypart aggregation), or Cell 33 detector (inline lick
  detection on jaw), note the mapping. If it's mismatch-unique
  (cross-bodypart classification rule with no analog), flag
  explicitly.

Output: markdown table or YAML in
`.scratch_7a5_mismatch/cell_walk.md` (gitignored under existing
`.scratch_*/` pattern).

Pay specific attention to:

- **Cells with `mismatch`, `match`, `discordant`, `inconsistent`,
  `tongue_only`, `jaw_only`, `paired`, or similar in source** — these
  are the classification anchors.
- **Cells importing or computing jaw per-trial logic** — inline
  detectors, slope analysis on jaw position, jaw lick/chew
  identification. THIS IS THE JAW-PER-TRIAL SIDE-FINDING the kickoff
  context flagged.
- **Plot family cells** — matplotlib calls saving PNGs. Note saved
  filename patterns.
- **Aggregator cells** — cross-session summary tables, cohort-level
  reports.

#### 1c. Classification rule extraction

Find the cell(s) that DEFINE what a mismatch trial is. Capture
verbatim:

- The exact predicate (e.g., `tongue.n_licks >= 5 AND jaw.n_chews < 2`
  or whatever the actual rule is).
- All tunable thresholds + their literal values.
- Whether the rule has variants (per-animal, per-session, per-
  category).
- Whether the rule is documented in adjacent markdown cells with
  scientific rationale.

Output to `.scratch_7a5_mismatch/classification_rule.md`.

#### 1d. Output-discovery walk on MICROSCOPE

For every "outputs written" entry from 1b, attempt to locate the
saved files on MICROSCOPE. Pattern likely:
- `\\research...\Priya\DeepLabCut\O2_analysis\{animal}\{animal}_<some_subdir>\...`
- Or `\\research...\Priya\stroke_orofacial_pipeline_outputs\<some_subdir>\...`
- Or a custom path pattern unique to mismatch work.

For each found output, capture:
- File extension + size + mtime (approximate vintage of the analysis).
- Sample header / first row (for CSVs) or schema (for parquets).
- For PNGs: filename + which cell it's emitted by.

If outputs are NOT found on MICROSCOPE — that's worth reporting too.
Could mean: outputs are emitted to a different drive, the cells were
never run on the cohort, or the outputs were pruned. Each
implication shifts the outcome recommendation.

Output to `.scratch_7a5_mismatch/output_inventory.md`.

#### 1e. Cross-bodypart dependency analysis

For the production-classified cells, document the dependency chain:

- What does the mismatch code consume?
  - 7a.3 V3 endpoints JSON fields? (e.g., `lick1_t_peak_ms`, `n_licks`)
  - 7a.2 jaw interpolation parquet?
  - Raw DLC parquets?
  - Custom intermediate artifacts?
- Does the mismatch code COMPUTE jaw per-trial features inline?
  - If yes: capture the inline detector + per-trial scalar shape.
    This is the load-bearing finding for the "is there hidden jaw
    per-trial logic?" question.
  - If no: confirm explicitly.

Output to `.scratch_7a5_mismatch/dependencies.md`.

#### 1f. Outcome proposal

Based on findings 1a-1e, propose one of:

- **Outcome A — minimal port**: classifier is a simple predicate on
  existing 7a.3 V3 / 7a.2 outputs. Plots are 1-2 small families.
  Recommend small port phase: ~200-400 line classifier module +
  small visual extension + tests + DECISIONS + PR. Estimate 3-5
  commits.
- **Outcome B — substantial port**: classifier has inline jaw
  per-trial detection layer (the side-finding lands), multiple plot
  families, structured saved outputs. Recommend full port phase
  mirroring 7a.3 V3 / 7a.4: vendor + config/paths + module + tests +
  parity harness + DECISIONS + PR. Estimate 7-10 commits. May spawn
  a sibling "Phase 7a.5-jaw-pertrial" if the inline jaw logic
  warrants its own scope.
- **Outcome C — partial / refactor**: meaningful but smaller scope.
  Specifics depend on what the audit finds.

Each outcome proposal should include:
- Recommended deliverable list.
- Estimated commit count.
- Estimated line count.
- Parity strategy (numerical vs visual vs synthetic-only).
- Any open scope questions for Priya.

#### 1g. STOP-and-report

Report to Priya:

- Notebook SHA256 confirmation + section location (cell-index range,
  cell count, source-line count).
- Per-cell classification summary (counts per class).
- Classification rule extracted verbatim.
- Output inventory (paths found on MICROSCOPE, sample contents).
- Dependency analysis (consumes what, computes what inline).
- Side-finding result on inline jaw per-trial logic
  (yes/no/partial).
- Outcome recommendation: A / B / C with one-paragraph justification.
- All scratch notes at `.scratch_7a5_mismatch/`.

#### 1h. Commit (only if any non-scratch docs were written)

```bash
# .scratch_7a5_mismatch/ is gitignored via the .scratch_*/ pattern.
# Task 1 produces no committed files — pure investigation.
# If the audit naturally surfaces a small docs note worth committing
# (vs scratch), capture it as a separate commit; otherwise no commit.
git status
```

### Tasks 2–8 (hybrid B1.5 sub-variant locked 2026-04-30)

Outcome B with two-modules-single-phase shape. ~8-9 commits total.
Each task has a STOP-and-report after; do NOT chain past a STOP without
Priya's acknowledgment.

### Task 2 — Vendor Cells 51-55 to `docs/legacy_snippets/`

**Goal.** Byte-identical capture of the 5-cell mismatch section per the
7a.0/7a.3 vendoring pattern.

#### 2a. Vendor

Create `docs/legacy_snippets/tongue_jaw_mismatch.py` with:

- `# ruff: noqa` + `# fmt: off` headers.
- Provenance docstring: notebook path, full notebook SHA256
  (`ED12C54...`), per-cell SHA256s for Cells 51-55, vendor capture
  date (2026-04-30).
- `# %% Cell N` separators between the 5 cells.
- Source preserved EXACTLY from the notebook — no edits, no
  reformats, no lint passes.

#### 2b. Run + commit

```bash
ruff check docs/legacy_snippets/tongue_jaw_mismatch.py    # should pass via the # ruff: noqa header

git add docs/legacy_snippets/tongue_jaw_mismatch.py
git diff --cached --stat
git commit -m "docs(legacy_snippets): vendor tongue-jaw mismatch cells 51-55 (7a.5)"
git push
```

**STOP and report:**
- Vendored file size + line count.
- Per-cell SHA256s (capture for kickoff cross-reference).
- Confirmation: byte-identical to canonical notebook (re-extract +
  diff = empty).

### Task 3 — `configs/defaults.yaml` + `paths.py` + path tests

**Only run Task 3 after Priya acknowledges Task 2 report.**

#### 3a. `configs/defaults.yaml` — two new sub-blocks

Add under `dlc_kinematics:`:

```yaml
dlc_kinematics:
  # ... existing 7a.x keys (tongue_pertrial, tongue_visual, etc.) — DO NOT modify ...

  jaw_pertrial:
    # =========================================================
    # Jaw per-trial features (7a.5 — extracted from Cell 53
    # inline-detection logic). Mirrors tongue_pertrial.py
    # architecture at smaller scale. Reusable building block for
    # future jaw-related work.
    # =========================================================
    detect_win_ms: [0, 5000]              # post-reward window for jaw deflection detection
    baseline_win_ms: [-500, 0]            # pre-reward baseline window for mean+sd
    deflection_threshold_sd_multiplier: 4.0   # |jaw_y - baseline| > 4 * baseline_sd
    deflection_threshold_min_px: 4.0          # OR > 4 px (whichever is larger)
    sustained_density_threshold: 0.625    # >= 5/8 frames over threshold
    sustained_window_n_frames: 8          # rolling 8-frame window
    feature_extraction_version: "v7a.5"
    interpolation_version: "v5p3"

  tongue_jaw_mismatch:
    # =========================================================
    # Tongue-jaw mismatch trial classifier + plotter (7a.5 — Cell
    # 53 classifier + Cell 55 plotter ports).
    # Scientific rationale: post-stroke (bilateral) lack of licking
    # is NOT due to perceptual or motivational deficits.
    # Demonstrated by trials where the mouse shows post-cue jaw
    # movement WITHOUT licking — jaw motor system spared while
    # tongue motor system impaired. Mismatch trials are the primary
    # positive evidence for this dissociation, not just a QC gate.
    # =========================================================
    classifier:
      quiet_tongue_win_ms: [70, 5000]      # window for "zero detected tongue licks"
      # Tongue-side detector knobs MIRROR Cell 33 verbatim — no
      # smoothing, no MIN_FINITE filter (matches legacy mismatch
      # classifier). These are LOCAL to mismatch; do NOT pull from
      # tongue_pertrial.detector (which is a different shape per V3).
      tongue_detector:
        slope_thr_px_per_s: 250.0
        rise_min_ms: 16.0
        fall_min_ms: 16.0
        min_peak_y_abs: 20.0
        peak_pad_ms: 52.0
        do_smooth_y_for_detection: false
    plotter:
      individual_trials:
        enabled: true
        n_cols: 2                          # legacy individualTrials2col
        figure_width_inches: 10.0
        figure_height_inches: 12.0
        dpi: 100
      session_overlay_grid:
        enabled: true
        n_rows: 4
        n_cols: 2                          # legacy sessionOverlayGrid4x2
        figure_width_inches: 12.0
        figure_height_inches: 14.0
      cross_session_overlay:
        enabled: true                      # per-mouse, all sessions
      cross_session_binned:
        enabled: true                      # per-mouse, day-binned (uses bin_days from animals.yaml)
    feature_extraction_version: "v7a.5"
    interpolation_version: "v5p3"
```

Validate YAML loads:

```bash
python -c "
import yaml
with open('configs/defaults.yaml') as f:
    cfg = yaml.safe_load(f)
jp = cfg['dlc_kinematics']['jaw_pertrial']
tjm = cfg['dlc_kinematics']['tongue_jaw_mismatch']
assert jp['detect_win_ms'] == [0, 5000]
assert jp['baseline_win_ms'] == [-500, 0]
assert jp['deflection_threshold_sd_multiplier'] == 4.0
assert tjm['classifier']['quiet_tongue_win_ms'] == [70, 5000]
assert tjm['classifier']['tongue_detector']['slope_thr_px_per_s'] == 250.0
assert tjm['plotter']['session_overlay_grid']['n_rows'] == 4
print('YAML loads + V5 mismatch knob assertions pass.')
"
```

#### 3b. `src/stroke_orofacial/paths.py` — four new resolver helpers

```python
def jaw_pertrial_endpoints_json(self, animal: str, date: dt.date) -> Path:
    """Per-trial jaw scalars JSON for one (animal, date)."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "jaw_pertrial" / "endpoints"
        / animal / f"{date.strftime('%Y%m%d')}.json"
    )

def tongue_jaw_mismatch_candidate_trials_parquet(
    self, animal: str, date: dt.date,
) -> Path:
    """Per-session mismatch candidate-trials parquet."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "tongue_jaw_mismatch"
        / "candidate_trials" / animal / f"{date.strftime('%Y%m%d')}.parquet"
    )

def tongue_jaw_mismatch_qc_dir(self, animal: str, date: dt.date) -> Path:
    """Per-session within-session figures (individual trials + session overlay grid)."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "tongue_jaw_mismatch"
        / "figures_qc" / animal / f"{date.strftime('%Y%m%d')}"
    )

def tongue_jaw_mismatch_cross_session_dir(self, animal: str) -> Path:
    """Cross-session figures (overlay + binned) per mouse."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "tongue_jaw_mismatch"
        / "cross_session" / animal
    )
```

#### 3c. `tests/test_paths.py` — extend with 4 new tests

Tests under `TestPhase7a5Paths` class. `STROKE_PIPELINE_MACHINE` →
`_HOST_KEY` monkeypatch pattern.

#### 3d. Run + commit

```bash
ruff check src/stroke_orofacial/paths.py tests/test_paths.py
pytest tests/test_paths.py -v
pytest --collect-only

git add configs/defaults.yaml src/stroke_orofacial/paths.py tests/test_paths.py
git diff --cached --stat
git commit -m "feat(config+paths): jaw_pertrial + tongue_jaw_mismatch schemas + 4 resolvers (7a.5)"
git push
```

**STOP and report:**
- YAML knob count (target ~25 keys across both sub-blocks).
- Path test pass count (target 4 new).
- Full-suite collection clean.

### Task 4 — `jaw_pertrial.py` module + tests

**Only run Task 4 after Priya acknowledges Task 3 report.**

**Goal.** Port Cell 53's inline jaw per-trial scalar extraction into a
public reusable module mirroring `tongue_pertrial.py` architecture.

#### 4a. Module structure (~250 lines)

`src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`:

```python
"""Phase 7a.5 — Jaw per-trial features (extracted from canonical tongue
notebook Cell 53 inline-detection logic).

Reusable building block for jaw-related per-trial analyses. Mirrors
tongue_pertrial.py architecture at smaller scale.

Inputs:
  - 7a.2 jaw interpolated_traces parquet (jaw_x_final, jaw_y_final, frame_idx)
  - SessionManifest (trials, fps, side, reward timestamps)

Outputs (atomic JSON):
  - {outputs}/dlc_kinematics/jaw_pertrial/endpoints/{animal}/{date}.json

Per-trial scalars (8 fields):
  - jaw_baseline_mean: float
  - jaw_baseline_sd: float
  - jaw_peak_pos_deflection: float (max positive deviation from baseline)
  - jaw_peak_neg_deflection: float (max negative deviation from baseline)
  - jaw_peak_abs_deflection: float (max absolute deviation)
  - jaw_peak_selected_deflection: float (signed selected per legacy convention)
  - jaw_thresh_abs: float (max(4 * baseline_sd, 4 px))
  - jaw_thresh_px_used: float (which threshold won — sd-scaled or floor)
  - jaw_n_frames_over_thresh: int (count in apply window)
  - jaw_pass_qc: bool (sustained ≥5/8 density check)
"""

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

@dataclass(frozen=True)
class JawPertrialResult:
    endpoints: dict
    metadata: dict


def build_jaw_pertrial(
    manifest: SessionManifest, resolver: PathResolver,
    trial_events: list,                              # reuse 7a.3 V3 TrialEvent type
    params: dict | None = None,
    *, overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Build per-trial jaw scalars for one session. Atomic JSON write."""
    ...


def build_jaw_pertrial_by_animal_date(
    animal: str, date: dt.date, resolver: PathResolver,
    *, trial_events=None, **kwargs,
) -> Path | None:
    """Convenience wrapper. Auto-derives trial_events from spout_behavior
    if None — reuses 7a.3 V3's `_derive_trial_events_from_spout_behavior`.
    """
    ...


# ============================================================================
# Helpers
# ============================================================================

def _compute_jaw_baseline(
    jaw_y: np.ndarray, t_ms: np.ndarray, *, baseline_win_ms: tuple[float, float],
) -> tuple[float, float]:
    """Mean + SD of jaw_y over baseline_win_ms (typically (-500, 0))."""
    ...


def _compute_jaw_deflections(
    jaw_y: np.ndarray, t_ms: np.ndarray, baseline_mean: float,
    *, detect_win_ms: tuple[float, float],
) -> dict[str, float]:
    """Peak deflections (positive, negative, absolute, selected) within detect window."""
    ...


def _compute_jaw_threshold(
    baseline_sd: float, *, sd_mult: float, min_px: float,
) -> tuple[float, float]:
    """Returns (threshold_value, threshold_used_label).
    threshold_value = max(sd_mult * baseline_sd, min_px)
    threshold_used_label tracks which one won.
    """
    ...


def _check_sustained_density(
    jaw_y: np.ndarray, t_ms: np.ndarray, baseline_mean: float, threshold: float,
    *, detect_win_ms: tuple[float, float], window_n: int, density_thr: float,
) -> tuple[bool, int]:
    """Returns (pass_qc, n_frames_over_thresh). pass_qc is True if any
    rolling window_n-frame window in detect_win_ms has >= density_thr
    fraction of frames over threshold.
    """
    ...
```

#### 4b. Tests (`tests/test_jaw_pertrial.py`, ~10 tests)

1. `test_compute_jaw_baseline_mean_and_sd_correct` — synthetic flat-then-rising trace.
2. `test_compute_jaw_baseline_handles_nan` — NaN in baseline window → np.nanmean / np.nanstd.
3. `test_compute_jaw_deflections_pos_neg_abs_selected` — synthetic trace with known +ve and -ve deflections; verify all 4 values.
4. `test_compute_jaw_threshold_sd_scaled_wins` — large SD case → returns sd_mult * sd; label = "sd_scaled".
5. `test_compute_jaw_threshold_floor_wins` — small SD case → returns min_px; label = "px_floor".
6. `test_check_sustained_density_passes_at_5_of_8` — synthetic 8-frame window with 5 frames over threshold → passes.
7. `test_check_sustained_density_fails_below_density` — 4/8 → fails.
8. `test_build_jaw_pertrial_emits_json` — driver writes JSON with expected schema.
9. `test_build_jaw_pertrial_overwrite_semantics` — skip vs force.
10. `test_build_jaw_pertrial_endpoints_schema_locked` — JSON has expected top-level keys + per-trial array shapes.

#### 4c. Run + commit

```bash
ruff check src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_jaw_pertrial.py
pytest tests/test_jaw_pertrial.py -v
pytest

git add src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_jaw_pertrial.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): jaw_pertrial module — per-trial jaw scalars from Cell 53 inline logic (7a.5)"
git push
```

**STOP and report:**
- Module line count + helper list.
- Test pass count (target ~10 new).
- Full-suite remains 0 failed.
- Smoke run on PS50/2025-03-19: bundle shape + sample baseline_mean / baseline_sd / pass_qc distribution.

### Task 5 — `tongue_jaw_mismatch.py` module + tests

**Only run Task 5 after Priya acknowledges Task 4 report.**

**Goal.** Port Cell 53 classifier + Cell 55 plotter. Consumes
`jaw_pertrial` (Task 4) + 7a.3 V3 endpoints JSON.

#### 5a. Module structure (~700 lines — classifier + 4 plot families + writers)

`src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`:

```python
"""Phase 7a.5 — Tongue-jaw mismatch trial classifier + plotter.

Identifies trials where the mouse shows post-cue jaw movement WITHOUT
licking. Scientific rationale: post-stroke (bilateral) lack of
licking is not due to perceptual or motivational deficits — the
dissociation isolates the deficit to tongue motor control.

Inputs:
  - 7a.2 tongue interpolated_traces parquet (x_final, y_final)
  - 7a.5 jaw_pertrial endpoints JSON (jaw_pass_qc per trial)
  - 7a.3 V3 endpoints JSON (lick1_t_peak_ms / n_licks for tongue-side
    quiet check — but uses Cell 33 detector locally with mismatch-
    specific knobs, not 7a.3 V3 emit-set values)

Outputs:
  - candidate_trials parquet (per-session)
  - within-session figures (individual trials + session overlay grid)
  - cross-session figures (overlay + binned)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.dlc_kinematics.jaw_pertrial import (
    JawPertrialResult, build_jaw_pertrial,
)
from stroke_orofacial.dlc_kinematics._detector import _slope_detect_lick_peaks  # reuse 7a.3 V3 primitive
from stroke_orofacial.paths import PathResolver

# ============================================================================
# Public API
# ============================================================================

def classify_tongue_jaw_mismatch(
    manifest, resolver, trial_events, params=None,
    *, overwrite="skip",
) -> Path:
    """Per-session classifier. Emits candidate_trials parquet.

    Per trial:
      quiet_tongue_pass = (zero peaks via Cell 33 detector in (70, 5000) ms)
      jaw_pass_qc = jaw_pertrial.jaw_pass_qc
      candidate_no_lick_with_jaw_move = quiet_tongue_pass AND jaw_pass_qc

    Output schema (37 cols matching legacy CSV):
      mouse, date, side, trial_index, reward_frame_idx,
      <tongue scalars: lick_count, ...>,
      <jaw scalars: baseline_mean, baseline_sd, peak_*, thresh_*, n_frames_over_thresh, pass_qc>,
      <classifier outputs: quiet_tongue_pass, jaw_pass_qc, candidate>,
      <metadata: fps, params_version>
    """
    ...


def render_within_session_figures(
    animal, date, resolver, params=None,
    *, candidate_trials_df=None, overwrite="skip",
) -> dict[str, list[Path]]:
    """Per-session: individual_trials_2col + session_overlay_grid_4x2."""
    ...


def render_cross_session_figures(
    animal, resolver, params=None,
    *, overwrite="skip",
) -> dict[str, Path]:
    """Per-mouse cross-session: overlay + binned (uses bin_days from animals.yaml)."""
    ...


# ============================================================================
# Helpers (sketch)
# ============================================================================

def _detect_quiet_tongue(tongue_y, t_ms, *, detector_params, win_ms) -> bool:
    """Return True if zero peaks in window per Cell 33 detector."""
    ...

def _build_candidate_trials_df(
    manifest, trial_events, jaw_pertrial: JawPertrialResult, tongue_traces, params,
) -> pd.DataFrame:
    """Build the 37-col per-trial table."""
    ...

def _plot_individual_trials_2col(...): ...
def _plot_session_overlay_grid_4x2(...): ...
def _plot_cross_session_overlay(...): ...
def _plot_cross_session_binned(...): ...
def _write_candidate_trials_parquet_atomic(...): ...
```

#### 5b. Tests (`tests/test_tongue_jaw_mismatch.py`, ~12 tests)

Smoke + classifier-correctness tests. Visual fidelity is the parity
harness's job (Task 6).

1. `test_detect_quiet_tongue_zero_peaks_returns_true` — synthetic trace with no peaks → True.
2. `test_detect_quiet_tongue_one_peak_returns_false` — single peak → False.
3. `test_classify_candidate_trial_predicate_truth_table` — 4 combinations of (quiet_tongue, jaw_pass) → expected candidate value.
4. `test_classifier_emits_37_col_parquet` — output schema matches.
5. `test_classifier_handles_session_with_no_candidates` — emits parquet with 0 candidate rows but full trial roster.
6. `test_classifier_handles_session_with_all_candidates` — degenerate sanity.
7. `test_classifier_overwrite_semantics`.
8-10. One smoke test per plot family (3 plot families × smoke = 3 tests; the 4th plot family `cross_session_binned` covered in 11).
11. `test_render_cross_session_binned_uses_bin_days_from_animals_yaml`.
12. `test_render_overwrite_skip_semantics`.

#### 5c. Run + commit

```bash
ruff check src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_tongue_jaw_mismatch.py
pytest tests/test_tongue_jaw_mismatch.py -v
pytest

git add src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py src/stroke_orofacial/dlc_kinematics/__init__.py tests/test_tongue_jaw_mismatch.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): tongue_jaw_mismatch — classifier + 4 plot families (7a.5)"
git push
```

**STOP and report:**
- Module line count + helper list.
- Test pass count (target ~12 new).
- Full-suite remains 0 failed.
- Smoke run on PS46/2025-03-07: candidate count + sides distribution +
  4-PNG render sanity.

### Task 6 — Parity harness + cohort runs

**Only run Task 6 after Priya acknowledges Task 5 report.**

**Goal.** legacy_approximate parity at `atol=1e-6` against 8 saved
per-mouse CSVs from MICROSCOPE on the 14-session parity cohort, plus
visual gate runner for human review.

#### 6a. `tests/scripts/parity_phase7a5_mismatch.py`

Mirror 7a.4's day-binned harness. CLI:

```bash
python tests/scripts/parity_phase7a5_mismatch.py \
    --mode {default, legacy_approximate} --sessions auto --atol 1e-6
```

`legacy_approximate` overrides:
- Tongue-side detector knobs already match Cell 33 — no overrides
  needed (mismatch classifier never used MIN_FINITE_SAMPLES_PER_LICK
  or smoothing per the audit).
- Jaw-side: confirm legacy Cell 53 knobs match V5 defaults; surface
  any divergences in legacy_approximate override table.
- Per-mouse CSV reader: aggregates per-session consolidated parquets
  back to per-mouse for comparison vs legacy CSV (since legacy emits
  per-mouse, consolidated emits per-session).

Comparator: per-trial-row, per-column NaN-aware
`np.isclose(a, b, atol=1e-6, equal_nan=True)`.

Acceptance: all comparisons pass at atol=1e-6 OR document residual
band per 7a.3 V3 / 7a.4 precedent if numerical-precision noise applies.

#### 6b. Visual gate runner (`tests/scripts/parity_phase7a5_visual_gate.py`)

Render 4-family figures for at least PS46/2025-03-07 (legacy figures
present at `\\research...\jaw_tongue_candidate_trials\`). Side-by-side
comparison grids for human review.

#### 6c. Cohort runs

```bash
# Default-mode emit (per-session parquets across 14-session cohort)
python -c "..."   # similar to 7a.4 cohort emit

# legacy_approximate parity
python tests/scripts/parity_phase7a5_mismatch.py --mode legacy_approximate --sessions auto --atol 1e-6 | tee /tmp/parity_7a5.log

# Visual gate cohort
python tests/scripts/parity_phase7a5_visual_gate.py | tee /tmp/visual_7a5.log
```

#### 6d. Commit

```bash
git add tests/scripts/parity_phase7a5_mismatch.py tests/scripts/parity_phase7a5_visual_gate.py
git diff --cached --stat
git commit -m "feat(parity): Phase 7a.5 mismatch parity harness + visual gate runner (7a.5)"
git push
```

**STOP and report:**
- Cohort emit confirmation (14 sessions × N parquets per session).
- legacy_approximate parity by_status + per-(animal, metric) max|Δ|.
- Visual gate output paths for human review.
- Any residual band requiring documentation.

### Task 7 — DECISIONS + MIGRATION_LOG entries

**Only run Task 7 after Priya acknowledges Task 6 report.** If parity
or visual gate flagged issues requiring triage, address those first.

#### 7a. `docs/DECISIONS.md` Phase 7a.5 entry

Insert above existing reverse-chronological entries. Codify the 6
locked decisions + classifier rule + scientific rationale + side-
finding (jaw_pertrial extraction from mismatch context) + parity
acceptance.

#### 7b. `docs/MIGRATION_LOG.md` Phase 7a.5 entry

Append after Phase 7a.3-jaw entry.

#### 7c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.5): DECISIONS + MIGRATION_LOG entries"
git push
```

### Task 8 — PR + tag prep

`gh pr create --base main --title "Phase 7a.5: tongue-jaw mismatch trial classifier + jaw per-trial features"` per the §"What 7a.5 delivers" template.

Tag on merge: `v7a.5-tongue-jaw-mismatch` (Priya's call post-merge).

STOP at PR-open.

---

## Constraints (across all tasks)

- **Phase 7a.5-mismatch scope is tongue-jaw mismatch trial classifier
  + visualization audit + (if audit demands) port + tests + parity
  ONLY.** No tongue-side per-trial-feature changes (7a.3 V3 locked).
  No jaw-side per-trial green-field design (separate phase if
  pursued). No 7a.4 visual-gate or day-binned changes (7a.4 locked).
- **No source data modification.** Tongue notebook stays read-only
  on MICROSCOPE. Vendor (if Outcome B/C demands) follows the
  7a.0/7a.3 byte-identical pattern.
- **No legacy-repo edits.**
- **No 7a.2 / 7a.3 V3 / 7a.4 / 7a.3-jaw module changes.** All locked
  by their respective phase merges; additive helpers allowed only if
  Task 1 finds the mismatch port genuinely needs to expose existing
  in-memory products from 7a.3 V3 (analogous to 7a.4's
  `build_tongue_visual_bundle` pattern).
- **STOP-and-report at Task 1.** Outcome decision is Priya's call.
- **No advancing past Task 1** until Priya picks A/B/C and (if B/C)
  Cowork extends the kickoff with Task 2+ specifics.
- **No force-push.** All pushes additive to `phase/7a.5-mismatch`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit per CLAUDE.md ground rule 8.
- **MICROSCOPE access required** for Task 1 (notebook read + saved
  output discovery).
- **If the canonical tongue notebook SHA256 differs** from the
  expected `ED12C54...`: STOP and report. The vendored snippets in
  `docs/legacy_snippets/tongue_pertrial_features.py` are byte-locked
  to that SHA; an upstream notebook edit would invalidate the lock
  and require re-vendoring decisions.
- **If the audit surfaces inline jaw per-trial logic** (the side-
  finding the kickoff anticipates): explicitly call it out in the
  STOP-and-report. It may warrant a sibling Phase 7a.5-jaw-pertrial
  or be foldable into Outcome B's scope; Priya decides.
- **If saved outputs on MICROSCOPE are NOT found** for the cells
  Task 1b classifies as production: report the gap. Could mean cells
  weren't run cohort-wide, outputs were pruned, or saved to a
  non-obvious path. Each shifts outcome reasoning.

---

## Reference points for the auditor

- **Canonical tongue notebook** —
  `\\research...\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  (SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).
- **Vendored Cells 33/36/39/42/50** at
  `docs/legacy_snippets/tongue_pertrial_features.py` (Phase 7a.3 V3,
  commit `0b78128`). Reference for the per-trial-features pipeline
  shape; not the mismatch section.
- **Existing tongue per-trial outputs** that mismatch logic likely
  consumes:
  - `<outputs>/dlc_kinematics/endpoints/{animal}/{date}.json` (7a.3 V3
    per-trial scalars: lick1/lick2 metrics, peak velocity, n_licks
    family, licking dynamics reductions, tongue angle, Cell 50
    own-bout scalars, session inclusion flags).
  - `<outputs>/dlc_kinematics/features/tongue/{animal}/{date}.parquet`
    (7a.3 V3 per-frame angle).
  - `<outputs>/dlc_kinematics/licking_dynamics/traces/{animal}/{date}.parquet`
    (7a.3 V3 per-session × side traces).
- **Existing jaw outputs** that mismatch logic likely consumes:
  - `<outputs>/dlc_kinematics/interpolated_traces/jaw/{animal}/{date}.parquet`
    (7a.2 per-frame jaw position, 7-column + 9-key schema).
- **Existing tongue visual gate** (7a.4) — likely the structural
  template for any mismatch plot families:
  - `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` (5 plot
    families × per-side variants).
  - `src/stroke_orofacial/dlc_kinematics/_day_binned.py` (cross-session
    aggregation pattern).
- **DECISIONS Phase 7a.3 V3 entry** — context for what 7a.3 V3
  deliberately ported + what was carved out.
- **DECISIONS Phase 7a.3-jaw entry** — context for the jaw-notebook-
  audit-empty finding; the mismatch audit may surface adjacent
  inline jaw logic.
- **DECISIONS Phase 7a.4 entry** — context for the bundle helper +
  visual gate + day-binned aggregation patterns; mismatch port may
  reuse these patterns.
- **`docs/phase-7/interpolation-strategy.md`** — phase 7a design
  brief; §6 parity scope at 14 sessions.
