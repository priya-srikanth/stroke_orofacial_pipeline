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
findings. Three possible outcome branches:

- **Outcome A — minimal port**: classifier is simple (e.g., a
  threshold-based rule on existing 7a.3 V3 endpoints JSON fields +
  jaw interpolation parquet), plotting is small (1-2 plot families).
  Phase ships as a small module addition (~200-400 lines) +
  DECISIONS + tests, no new schema work needed.
- **Outcome B — substantial port**: classifier has its own per-trial
  detection layer (e.g., the audit surfaces inline jaw-licking
  detector code), multiple plot families, saved outputs in a
  structured tree on MICROSCOPE. Full port phase mirroring 7a.3 V3 /
  7a.4 in scope (~1000-2000 lines + new schemas + parity harness).
- **Outcome C — partial / refactor candidate**: classifier is
  meaningful but small; plots are dense and worth porting; or audit
  finds the mismatch code is already substantially covered by
  existing 7a.3 V3 endpoints + 7a.2 interpolation outputs and just
  needs a thin orchestrating wrapper. Mid-sized phase.

The audit determines which outcome lands. Outcome decision happens
at Task 1's STOP-and-report.

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

### Task 1.5+ — TBD pending Task 1 outcome

DO NOT proceed past Task 1's STOP without Priya's outcome decision.

#### Outcome A path (minimal port, ~3-5 commits)

- Task 2.A — vendor mismatch cells to
  `docs/legacy_snippets/tongue_jaw_mismatch.py` (byte-identical, SHA256
  provenance per 7a.0/7a.3 pattern).
- Task 3.A — small classifier module +
  `configs/defaults.yaml dlc_kinematics.tongue_jaw_mismatch:` block
  if knobs warrant + path resolvers if new outputs.
- Task 4.A — unit tests on synthetic input.
- Task 5.A — visual extension (extends `tongue_visual.py` with
  mismatch plot families IF Outcome A's visual scope is small enough
  to fold cleanly).
- Task 6.A — DECISIONS + MIGRATION_LOG entries + PR.

#### Outcome B path (substantial port, ~7-10 commits)

Mirror 7a.3 V3 structure. Cowork rewrites this kickoff once Task 1
findings lock the deliverables. Likely shape:
- Task 2.B — vendor cells.
- Task 3.B — config + paths + tests.
- Task 4.B — module(s) including any inline jaw per-trial detector.
- Task 5.B — unit tests.
- Task 6.B — parity harness + cohort run.
- Task 7.B — visual extension if applicable.
- Task 8.B — DECISIONS + MIGRATION_LOG.
- Task 9.B — PR + tag.

#### Outcome C path (partial, ~5-7 commits)

Mid-sized. Cowork rewrites kickoff to lock specifics.

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
