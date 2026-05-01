# Phase 7a.3-jaw Kickoff — Audit-first per-trial-features investigation for jaw bodypart

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.3-jaw-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.4 merged 2026-04-30 as PR #86, tagged
`v7a.4-tongue-visual-and-day-binned`. The full tongue per-trial-features
arc is closed on `main`: 7a.3 V3 ported Cells 33/36/39/42/50; 7a.4
added the Cell 50 visual gate + Cell 42 day-binned cross-session
aggregator.

Phase 7a.3-jaw is the parallel investigation for the **jaw** bodypart.
It was deferred from 7a.3 V3 explicitly because:

- 7a.3 V3's V1→V2 audit (2026-04-25) reported that the jaw notebook
  contains NO per-trial features in the form 7a.3 V3 ported for
  tongue. Specifically, Cell 41 of the jaw notebook was reportedly a
  copy-paste of tongue code against files the jaw notebook never
  produces.
- That finding was **incidental to scoping 7a.3 V3**, not a formal
  audit. Phase 7a.3-jaw is the **formal audit** that confirms or
  refutes it, and decides what (if any) jaw-specific work belongs in
  the consolidated pipeline.

The jaw bodypart already has 7a.2 v5p3 interpolation support shipped
on `main` (Cell 22 vendored as `jaw_cell22_interp_v5p3.py`; per-frame
jaw position parquet + `dlc_kinematics.jaw:` config block + 14-session
cohort-wide bit-identical parity). That covers per-frame jaw
position. **What this phase audits is everything DOWNSTREAM of
per-frame interpolation** — per-trial features, cross-session
aggregation, QC visualization — none of which has shipped for jaw.

### Audit-first scope (deliberate)

This kickoff is structurally different from 7a.3/7a.4. Those phases
locked deliverables before kickoff (we knew what to port). 7a.3-jaw
locks **Task 1 (audit) only**; Tasks 2-N depend on what the audit
finds. Three possible outcome branches:

- **Outcome A — confirmed empty.** Audit confirms the V2 incidental
  finding: jaw notebook has no per-trial features beyond what 7a.2
  already ports (Cell 22 interpolation). Phase becomes a small
  docs-only close: DECISIONS entry codifying the audit findings +
  MIGRATION_LOG entry + tag (`v7a.3-jaw-no-pertrial-features-confirmed`
  or similar). No code changes. Closes the open question durably.
- **Outcome B — incidental finding was wrong / incomplete.** Audit
  finds jaw-specific per-trial features the V2 incidental audit
  missed (e.g., chewing dynamics, jaw protrusion-velocity for
  non-licking behaviors, jaw QC plots, jaw-specific aggregation).
  Kickoff expands (or new kickoff written) to port them + tests +
  parity. Substantial work; could rival 7a.3 V3 in scope.
- **Outcome C — partial.** Audit finds a few small features worth
  porting, or QC plots worth rendering, but nothing approaching
  7a.3 V3's scope. Mid-sized phase.

The audit IS the deliverable for now. Outcome decision happens at the
Task 1 STOP-and-report.

### Scope NOT in this phase

- Re-running 7a.2 jaw interpolation (already shipped + cohort-validated).
- Extending tongue-side modules (`tongue_pertrial.py`, `tongue_visual.py`,
  `_day_binned.py`) to jaw — those are tongue-specific by design.
- Whisker / face-velocity / PSD branches (those are separate phases).
- Cohort-wide 7a.2/7a.3 upstream re-emit (deferred from 7a.4 as a
  publication-grade follow-up).

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five
items. Items 1 + 5 are concrete now; items 2-4 lock at Task 1 STOP.

### 1. Legacy file disambiguation

One source notebook for this phase:

- `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`

Apply the three-tier rule:
- This is the latest-dated (`20260416`) within the jaw family. Older
  variants like `20251216_*_jaw.ipynb` (if any) are explicitly
  superseded.
- Sibling notebooks — confirm Task 1a whether any
  `*_reward-aligned_*_jaw.ipynb` exists alongside the canonical one;
  apply the date-priority rule if found.
- Trust 7a.2's prior 3-tier resolution for the parent jaw-notebook
  family (Cell 22 vendored from this same notebook).

The tongue notebook (canonical for 7a.3 V3 + 7a.4):
- `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
  SHA256
  `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
- Used as the comparison reference for jaw audit (Task 1e).

### 2. Dead code identification

Cell-level walk of the jaw notebook (Task 1b). Each cell classified
as:
- **Production** — would feed downstream consolidated pipeline if
  ported.
- **Exploratory** — data inspection, debugging, one-off
  experimentation.
- **Deprecated** — older version, `_v0`/`_mod`/`_old`-suffixed,
  superseded.
- **Ambiguous** — unclear whether used.

Production cells are candidates for porting in subsequent tasks (if
Outcome B or C). Audit STOPs and reports the per-cell classification
table; Priya picks which (if any) to port.

### 3. Sub-phase breakdown

Locks at Task 1 STOP. Sketches:

- **Outcome A:** Tasks 2-3 only. Task 2 = DECISIONS + MIGRATION_LOG
  entries documenting the no-features finding. Task 3 = PR open + tag.
  Total ~3 commits (kickoff + DECISIONS + PR-prep).
- **Outcome B:** Tasks 2-7 mirror 7a.3 V3 structure. Vendor cells +
  config/paths + module + tests + parity harness + DECISIONS + PR.
  Total ~8-12 commits.
- **Outcome C:** Tasks 2-5. Vendor cells + module + tests +
  DECISIONS + PR. Total ~5-7 commits.

### 4. Parity strategy

Locks at Task 1 STOP based on what's found:
- If audit finds per-trial features: legacy_approximate harness
  modeled on 7a.3 V3's, comparing consolidated outputs against legacy
  CSV/NPZ if those exist. Same per-cell knob override mechanism if
  needed.
- If audit finds visual outputs: visual gate harness modeled on 7a.4's.
- If neither (Outcome A): no parity gate; documentation acceptance
  only.

### 5. Hardcoded constants

If Outcome B or C: any per-cell knobs, windows, smoothing parameters,
etc. captured in Task 1 audit move to `configs/defaults.yaml` under a
new `dlc_kinematics.jaw_pertrial:` block (mirroring 7a.3 V3's
`dlc_kinematics.tongue_pertrial:`). The 7a.2 `dlc_kinematics.jaw:`
interpolation block stays untouched (locked by 7a.2).

---

## Execute on branch `phase/7a.3-jaw`

### Preflight

```bash
git checkout main
git pull
git status                           # clean working tree
git log --oneline -1                 # at PR #86 merge commit
git tag --list | grep -E 'v7a\.(3|4)$|v7a\.[34]-'   # 7a.3 + 7a.4 tags present locally

git checkout -b phase/7a.3-jaw
git push -u origin phase/7a.3-jaw
```

Activate the conda environment per CLAUDE.md:

```bash
conda activate stroke_orofacial
which python                         # path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"  # must succeed
pytest --collect-only                # baseline 623 tests + 35 skipped
```

Confirm MICROSCOPE access to the canonical jaw notebook:

```bash
ls -la "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb"
# Should show file size + recent mtime; if "No such file or directory" or permission denied,
# STOP and report — MICROSCOPE mount is the prerequisite for Task 1.
```

### Task 0 — Kickoff prep (this commit, Cowork's job)

Cowork writes this kickoff doc. Priya commits + pushes + pastes the
handoff line. Do not re-execute Task 0 from CC.

### Task 1 — Comprehensive jaw notebook audit

**Goal.** Walk the canonical jaw notebook end-to-end. Classify every
cell. Identify any per-trial feature candidates (or confirm absence).
Compare to tongue Cells 33/36/39/42/50 patterns. Report findings
sufficient for Priya to pick Outcome A / B / C.

#### 1a. Notebook provenance

Capture forensic provenance:

```bash
sha256sum "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb"
# Capture SHA256 + file size + mtime + cell count
```

Also confirm via Python (more reliable on Windows UNC paths):

```python
import hashlib
from pathlib import Path
nb_path = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb")
print(f"size: {nb_path.stat().st_size:,} B")
print(f"sha256: {hashlib.sha256(nb_path.read_bytes()).hexdigest()}")

# Cell count + cell-type distribution
import json
nb = json.loads(nb_path.read_text(encoding="utf-8"))
cells = nb["cells"]
print(f"total cells: {len(cells)}")
print(f"  code:     {sum(1 for c in cells if c['cell_type'] == 'code')}")
print(f"  markdown: {sum(1 for c in cells if c['cell_type'] == 'markdown')}")
```

Sibling-notebook check:

```bash
ls -la "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\" | grep -i jaw
# Confirm no other *_jaw*.ipynb files exist that would compete via
# the 3-tier rule. If multiple jaw notebooks present, capture all
# names + dates + sizes and apply the rule.
```

#### 1b. Per-cell walk + classification

Iterate through every code cell. For each, record:

- **Cell index** (0-indexed in the notebook).
- **First non-empty source line** (gives a quick semantic anchor).
- **Length** in lines.
- **Classification**: production / exploratory / deprecated /
  ambiguous.
- **Imports** specific to this cell (not session-wide).
- **Inputs read**: legacy NPZ paths, parquet paths, config dicts,
  upstream products consumed.
- **Outputs written**: filenames emitted (CSV / NPZ / parquet / PNG).
  CRITICAL — this is the load-bearing field for the audit. If a cell
  emits nothing or emits to a path the jaw notebook never reads later,
  it's likely exploratory or stale.
- **Match to tongue cells**: if the cell mirrors the structure of
  tongue Cell 22 / 23 / 33 / 36 / 39 / 42 / 50, note the mapping. If
  it's jaw-unique (no tongue analog), flag explicitly.

Output format: a markdown table or YAML in
`.scratch_7a3_jaw/cell_walk.md` (gitignored under the existing
`.scratch_*/` pattern).

Pay specific attention to:
- **Cell 41** (V2 incidental audit flagged it as a copy-paste of
  tongue code against jaw-non-existent files). Verify or refute the
  V2 finding. If it IS a copy-paste against non-existent files,
  capture the exact tongue cell it mirrors, the exact files it tries
  to read, and the path resolution that fails.
- **Any cells with `_pertrial`, `_dayBinned`, `lick`, `bout`,
  `phase`, `angle` in their source** — these are the pattern markers
  for the tongue-side analysis 7a.3 V3 ported.
- **Jaw-specific computation** that doesn't exist in tongue: e.g.,
  jaw-protrusion-velocity, chewing-cycle detection, jaw-Y-baseline-
  drift-correction, jaw-only QC plots. These would be Outcome B / C
  candidates.

#### 1c. Per-trial feature inventory

From the cell-walk, extract a candidate list:

| Cell index | Feature name | Output(s) | Tongue analog (if any) | Outcome bucket |
|---|---|---|---|---|
| ... | ... | ... | ... | (A confirmed-empty / B production-port / C small-feature) |

If the table is **empty after filtering for production cells with
real outputs**, that's the strong signal for Outcome A.

If the table has rows mirroring tongue's per-trial pipeline, those
are Outcome B candidates.

If the table has a few rows of jaw-unique features (no tongue
analog) without the full per-trial-pipeline shape, those are
Outcome C candidates.

#### 1d. Jaw-specific code-path identification

Independently flag anything in the notebook that is JAW-UNIQUE — not
a copy-paste of tongue. The V2 incidental finding was that Cell 41
specifically WAS a copy-paste, but the rest of the jaw notebook
might have legitimately jaw-specific work that wasn't compared to
tongue.

Examples to look for:
- Jaw-baseline-drift correction (jaw position drifts more slowly
  than tongue; might have its own correction logic).
- Chewing dynamics (rhythmic jaw motion during eating, distinct from
  licking).
- Jaw-protrusion velocity for non-licking behaviors.
- Jaw-yaw / jaw-pitch decomposition (3D rotation features tongue
  doesn't have).
- Cross-bodypart features that depend on jaw + another bodypart
  jointly (e.g., jaw-tongue coordination metrics).

If any of these surface AND are production-classified, they're
Outcome B / C candidates regardless of whether tongue has analogs.

#### 1e. Compare to tongue Cells 33/36/39/42/50

Cross-reference the jaw cell-walk against the tongue notebook's
production cells (vendored at
`docs/legacy_snippets/tongue_pertrial_features.py`, Cells 33/36/39/
42/50). For each tongue per-trial cell:

- Does the jaw notebook have an analog cell?
- If yes: is the analog production-classified? Does it emit real
  outputs that downstream code (notebooks or scripts) consumes?
- If no: confirm the absence. Note the gap explicitly.

#### 1f. Outcome proposal

Based on findings 1a-1e, propose one of:

- **Outcome A** — audit confirms no jaw per-trial features beyond
  7a.2 interpolation. Recommend small docs-only close.
- **Outcome B** — audit finds N production per-trial cells + M
  visual/aggregation cells worth porting. Recommend full
  port-+-tests-+-parity phase. Estimate scope (file counts, line
  counts, parity-gate complexity).
- **Outcome C** — audit finds < N production cells worth porting,
  or finds jaw-unique features that don't fit the tongue template.
  Recommend mid-sized phase. Sketch the deliverable list.

#### 1g. STOP-and-report

Report to Priya:

- Notebook SHA256 + size + cell count + sibling-check result.
- Per-cell classification summary (counts per class).
- Per-trial feature inventory table (or empty if Outcome A).
- Cell 41 status: V2-finding-confirmed or V2-finding-refuted with
  details.
- Jaw-unique code-path findings (1d list).
- Tongue-cells comparison gap analysis (1e).
- Outcome recommendation: A / B / C with one-paragraph justification.
- Full audit notes at `.scratch_7a3_jaw/cell_walk.md` + any
  supplementary files.

#### 1h. Commit (only if scratch notes were written)

```bash
# .scratch_7a3_jaw/ is already gitignored via the .scratch_*/ pattern.
# Task 1 produces no committed files — pure investigation.
# If you wrote any docs/scratch/ notes (vs .scratch_*/), commit them:
git status
# Should show only working-tree mods to .scratch_7a3_jaw/ (gitignored).
# If clean, no commit. If you wrote a docs/ note, commit it.
```

### Task 1.5+ — TBD pending Task 1 outcome

DO NOT proceed past Task 1's STOP without Priya's outcome decision.
The remaining tasks depend on which outcome lands.

#### Outcome A path (small docs close, ~3 commits total)

- **Task 2.A** — `docs/DECISIONS.md` Phase 7a.3-jaw entry. Codifies:
  audit findings, no-per-trial-features confirmation, V2-incidental-
  audit status, Cell 41 disposition, jaw-unique-code-path findings.
- **Task 3.A** — `docs/MIGRATION_LOG.md` entry. PR open. Tag on merge:
  `v7a.3-jaw-no-pertrial-features-confirmed` (or similar — final
  naming at PR-open time).

#### Outcome B path (substantial port, ~8-12 commits)

Mirror 7a.3 V3 structure. Cowork rewrites this kickoff (or writes
a new V2 kickoff doc) once the audit findings lock the deliverables.
Likely shape:

- Task 2.B — vendor relevant cells to `docs/legacy_snippets/jaw_pertrial_features.py`.
- Task 3.B — `configs/defaults.yaml dlc_kinematics.jaw_pertrial:`
  block + path resolvers + tests.
- Task 4.B — `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`
  module (likely with sibling `_detector.py` / `_angle.py` / `_writers.py`
  pattern from 7a.3 V3 if scope warrants).
- Task 5.B — unit tests.
- Task 6.B — parity harness (default + legacy_approximate modes).
- Task 7.B — DECISIONS + MIGRATION_LOG entries.
- Task 8.B — PR + tag.

#### Outcome C path (mid-sized, ~5-7 commits)

Port the smaller feature set the audit identified. Cowork rewrites
this kickoff (or writes a new V2) to lock the specific features.
Likely shape: vendor + 1-2 modules + tests + DECISIONS + PR.

---

## Constraints (across all tasks)

- **Phase 7a.3-jaw scope is jaw-bodypart per-trial-features audit + (if
  audit demands) port + tests + parity ONLY.** No tongue-side changes.
  No whisker / face-velocity / PSD work. No cohort-wide upstream
  re-emit.
- **No source data modification.** Jaw notebook stays read-only on
  MICROSCOPE. Vendor (if Outcome B/C demands) follows the 7a.0/7a.3
  byte-identical pattern: `# ruff: noqa` + `# fmt: off` headers,
  SHA256 provenance in the docstring, no edits/reformats/lint passes.
- **No legacy-repo edits.**
- **No 7a.2 jaw interpolation changes.** `dlc_kinematics.jaw:` config
  block + per-frame jaw parquet schema + Cell 22 vendored snippet all
  stay LOCKED.
- **No 7a.3 V3 / 7a.4 tongue-side module changes.** `tongue_pertrial.py`,
  `tongue_visual.py`, `_day_binned.py`, `_detector.py`, `_angle.py`,
  `_writers.py` — all locked by their respective phase merges.
- **STOP-and-report at Task 1.** Outcome decision is Priya's call.
- **No advancing past Task 1** until Priya picks A / B / C and (if
  B/C) Cowork extends the kickoff with Task 2+ specifics.
- **No force-push.** All pushes additive to `phase/7a.3-jaw`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit per CLAUDE.md ground rule 8.
- **MICROSCOPE access required** for Task 1 (notebook read).
- **If sibling jaw notebooks surface** that compete via the 3-tier
  rule: STOP and report. Don't silently pick.
- **If Cell 41's V2 incidental finding is REFUTED** (i.e., Cell 41
  IS production-classified and emits real outputs the notebook
  reads): STOP and report. This is a meaningful divergence from
  prior assumptions and should surface at audit time, not get
  buried in a routine cell-walk.
- **If audit finds production cells the V2 incidental audit
  completely missed** (not just Cell 41 status): same STOP-and-report
  treatment. Surface the gap explicitly.

---

## Reference points for the auditor

- **Tongue Cells 33/36/39/42/50** — vendored byte-identically at
  `docs/legacy_snippets/tongue_pertrial_features.py` (Phase 7a.3 V3,
  commit `0b78128`). Use as the comparison template for the jaw
  cell-walk.
- **Tongue notebook** —
  `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  (SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).
- **DECISIONS Phase 7a.3 V3 entry** — context for what was deliberately
  NOT ported in 7a.3 V3 (the V2 incidental jaw finding lives in
  Decision 2 of the V3 entry).
- **DECISIONS Phase 7a.4 entry** — context for the visual-gate +
  day-binned aggregator patterns; if Outcome B/C and jaw has analog
  features, these patterns extend.
- **MIGRATION_LOG Phase 7a.2 entry** — context for what 7a.2 did port
  for jaw (Cell 22 interpolation only).
- **`docs/phase-7/interpolation-strategy.md`** — phase 7a design brief;
  §6 parity scope at 14 sessions.
