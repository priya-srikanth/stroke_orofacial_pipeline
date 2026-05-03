# Phase 7a.6 Kickoff — Tongue + jaw "Per session and combined mean/SEM plots" visual gate (audit-first, bodypart-symmetric)

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.6-mean-sem-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.5-mismatch merged 2026-04-30 as PR #88, tagged
`v7a.5-tongue-jaw-mismatch` — closes the per-trial kinematic family
of phases for both tongue (Cells 33/36/39/42/50 in 7a.3 V3 + visual
gate in 7a.4 + mismatch in 7a.5) and jaw (audit-only-no-features in
7a.3-jaw + jaw_pertrial scalars surfaced in 7a.5-mismatch's Cell 53
side-finding).

Phase 7a.6 is the next visual-gate phase Priya picked 2026-04-30:
port the **"Per session and combined mean/SEM plots"** sections from
both ws_aligned notebooks to the consolidated pipeline + visual-gate
verify against legacy figures.

**Bodypart-symmetric scope.** Both notebooks have a section under
the same markdown anchor:
- **Tongue source**: `\\research...\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
  section `## Per session and combined mean/SEM plots` → up to (not
  including) `## Tongue-jaw mismatch trials` (which 7a.5 covered).
- **Jaw source**: `\\research...\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`,
  section `## Per session and combined mean/SEM plots` → up to (not
  including) `OLD - Jaw-Tongue session comparisons`.

The 7a.3-jaw audit (PR #87) classified the jaw notebook's 6
production-viz cells (30/32/34/37/39/43) in this region; some/all of
those likely ARE the mean/SEM plot family this phase ports. Cell 43
PSD (deferred from 7a.3-jaw) MAY fold in here naturally OR stay its
own small follow-up — audit decides.

The tongue side has analogous production-viz cells. The 7a.4 visual
gate covered Cell 50 specifically (per-frame angle + per-trial angle
scalars + 5 angle/phase plot families). Cell 50 may be PART of this
section's mean/SEM family OR adjacent to it — audit needs to identify
the exact section boundaries to avoid re-porting what 7a.4 already
shipped.

### Audit-first scope (deliberate)

Same pattern as 7a.3-jaw + 7a.5-mismatch. Task 1 = audit + STOP;
Tasks 2-N depend on findings. Three possible outcome branches:

- **Outcome A — minimal port**: small set of plot helpers in both
  bodyparts; can fold into existing `tongue_visual.py` (extending
  with mean/SEM plot families) + a new small `jaw_visual.py` mirror.
  ~3-5 commits.
- **Outcome B — substantial port**: meaningful per-bodypart plotting
  modules with cross-session aggregation logic + per-trial overlays
  + bodypart-specific axis conventions. Full per-bodypart visual
  modules + parity harness + visual gate runner. ~7-10 commits.
- **Outcome C — partial / refactor**: medium scope; e.g., share a
  single bodypart-parametric `mean_sem_visual.py` module rather than
  per-bodypart sibling modules. ~5-7 commits.

The audit also resolves three structural questions:

1. **Tongue-Cell-50 overlap**: does the tongue notebook's "Per session
   and combined mean/SEM plots" section include Cell 50 (already
   covered by 7a.4) or stop before it? If overlap, scope is jaw-only
   net-new + tongue's mean/SEM-but-not-Cell-50 cells. If no overlap,
   scope is fully bodypart-symmetric.
2. **Cell 43 PSD fold-in**: does Cell 43 belong to this section
   (per-session jaw frequency-domain QC IS a per-session plot) or to
   a future face-rhythmicity / strategy §7 PSD phase? Audit reads
   adjacent markdown headers + Cell 43 source to decide.
3. **Architecture**: per-bodypart sibling modules
   (`tongue_mean_sem_visual.py` + `jaw_mean_sem_visual.py`) OR
   bodypart-parametric single module
   (`mean_sem_visual.py` parameterized by `bodypart` arg)? Depends
   on how much code overlaps between tongue and jaw plotting cells.

### Notebook authoring bundles into this phase (Priya 2026-05-01)

The orchestration notebooks `notebooks/13_dlc_kinematics_tongue.ipynb`
and `notebooks/14_dlc_kinematics_jaw.ipynb` are 2-cell skeletons
(title + `ANIMALS = [...]` only) — the entire 7a.x consolidation arc
shipped modules + parity tests but never wired any of it through the
analyst-facing notebook entry points. Phase 7a.6 closes this debt as
a final task in the chosen outcome path: populate notebooks 13 + 14
with USER INPUTS → manifest building → per-(animal, date) calls
through the full chain (7a.2 interpolation → 7a.3/7a.5 per-trial →
7a.4 angle/phase visual gate → 7a.5 mismatch → 7a.6 mean/SEM →
optional 7a.3-jaw / Cell 43 PSD per outcome).

Pattern is set by `notebooks/10_dlc_build_parquets.ipynb`,
`11_dlc_spatial_whole_session.ipynb`, `12_dlc_spatial_reward_aligned.ipynb`
— populated end-to-end with USER INPUTS → resolver/manifests →
processing loop, no analytical code (per repo rule "notebooks
orchestrate, src/ analyzes"). Target ~80-150 lines per notebook,
all imports + orchestration.

Audit Task 1 inventories what cells need to be wired (see 1j).
Outcome A / B / C each end with a "Populate notebooks 13 + 14" task
before the DECISIONS+PR step.

### Scope NOT in this phase

- Per-frame interpolation (already shipped in 7a.2 for both bodyparts).
- Per-trial features (tongue: 7a.3 V3; jaw: 7a.5-mismatch's
  jaw_pertrial.py).
- Cell 50 angle/phase visual gate (7a.4 already shipped).
- Tongue-jaw mismatch (7a.5 already shipped).
- DLC heatmaps (Phase 7a.7, 3 separate legacy notebook sources —
  parallel-workflow, not this phase).
- New reward-aligned heatmaps (Phase 7a.8, builds on 7a.7).
- Spout behavior plots (Phase 8a.10, separate notebook source).
- Stats plots (Phase 9 forward-pointer).
- Whisker / face-velocity / PSD branches of strategy §7 (separate
  phases). Cell 43 PSD MAY fold here per audit.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

Items 1 + 5 concrete now; items 2-4 lock at Task 1 STOP.

### 1. Legacy file disambiguation

Two source notebooks (both already canonical from prior phases):

- **Tongue**: `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  (SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).
  Same notebook 7a.3 V3 / 7a.4 / 7a.5-mismatch ported from. Cells
  outside the per-trial-features + angle + mismatch scopes are this
  phase's targets.
- **Jaw**: `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
  (SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`).
  Same notebook 7a.3-jaw audited. The 6 production-viz cells
  (30/32/34/37/39/43) are this phase's primary targets; Cell 43 PSD
  fold-in TBD by audit.

3-tier rule resolution: trust prior 3-tier work for both notebooks;
this phase adds no new candidates.

### 2. Dead code identification

Cell-level walk of both sections (Task 1b). Each cell classified as
production / exploratory / deprecated / ambiguous.

Production cells in both bodyparts get ported. Compare cell shapes
across tongue and jaw to determine architecture choice (sibling
modules vs bodypart-parametric).

### 3. Sub-phase breakdown

LOCKED 2026-05-01 (Task 1 outcome): 8 sub-phase tasks (Task 2 through
Task 9) under Outcome B + bodypart-parametric architecture. Detailed
specs in §"Task 1 outcome — LOCKED 2026-05-01" and Tasks 2-9 below.
Estimated 10-12 commits.

### 4. Parity strategy

Numerical parity: emit consolidated outputs (per-session +
combined-cohort mean/SEM data tables) → comparator vs legacy outputs
at `atol=1e-6`. May or may not have legacy CSVs/NPZs — audit
discovers + scopes accordingly.

Visual gate: render comparison grids for example sessions per
bodypart against legacy saved PNGs. Same pattern as 7a.4 / 7a.5-mismatch.

Acceptance: numerical parity within atol=1e-6 (or documented residual
band per 7a.3 V3 / 7a.4 / 7a.5 precedent if numerical-precision noise
applies); visual gate verdict PASS from Priya.

### 5. Hardcoded constants

Knobs go under new `dlc_kinematics.{tongue, jaw}_mean_sem_visual:`
sub-blocks (or single bodypart-parametric block depending on
architecture choice from Task 1).

7a.x family standing schemas (interpolation, per-trial features,
visual, day-binned, mismatch) all stay LOCKED. This phase adds new
knobs without modifying existing blocks.

---

## Execute on branch `phase/7a.6-mean-sem`

### Preflight

```bash
git checkout main
git pull
git status                            # clean working tree
git log --oneline -1                  # at PR #88 merge commit (7a.5-mismatch close)
git tag --list | grep -E 'v7a\.[2-5]' # 7a.2 / 7a.3 / 7a.3-jaw / 7a.4 / 7a.5 tags present locally

git checkout -b phase/7a.6-mean-sem
git push -u origin phase/7a.6-mean-sem
```

Activate the conda environment per CLAUDE.md:

```bash
conda activate stroke_orofacial
which python                          # path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"   # must succeed
pytest --collect-only                 # baseline (post-7a.5: 667 tests + 35 skipped)
```

Confirm MICROSCOPE access to both canonical notebooks:

```bash
ls -la "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb"
ls -la "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb"
# If either path fails, STOP — MICROSCOPE access is the prerequisite.
```

### Task 0 — Kickoff prep (this commit, Cowork's job)

Cowork writes this kickoff doc. Priya commits + pushes + pastes the
handoff line. Do not re-execute Task 0 from CC.

### Task 1 — Bodypart-symmetric mean/SEM section audit

**Goal.** Walk both notebook sections end-to-end. Classify every cell.
Identify the per-session + combined-cohort mean/SEM plot families.
Resolve the three structural questions (tongue-Cell-50 overlap, Cell
43 PSD fold-in, architecture choice). Report findings sufficient for
Priya to pick Outcome A / B / C.

#### 1a. Notebook + section locations

Re-confirm both canonical SHA256s match the expected values
(`ED12C54...` for tongue, `7be0eee0...` for jaw). If either differs,
upstream edited — STOP and report.

Locate the `## Per session and combined mean/SEM plots` markdown
header in each notebook:

```python
import json
from pathlib import Path

for nb_path in [
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb",
]:
    nb = json.loads(Path(nb_path).read_text(encoding="utf-8"))
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "markdown":
            src = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            if "Per session and combined mean/SEM" in src:
                print(f"{Path(nb_path).name} cell {i}: {src[:200]}")
```

Capture the cell-index range covered by each section (header to next
section header). Record cell count + total source-line count for
each.

#### 1b. Per-cell walk + classification (both bodyparts)

For each cell in each section, record:
- Cell index, type (code/markdown), first non-empty line, length.
- Classification (production / exploratory / deprecated / ambiguous).
- Inputs read (parquets, NPZs, configs, upstream products).
- Outputs written (CSV / NPZ / parquet / PNG with filename pattern).
- Match to existing patterns: does it mirror Cell 50 visual gate
  (7a.4)? Cell 42 day-binned (7a.4)? Cell 53 classifier or Cell 55
  plots (7a.5)? Or is it mean/SEM-unique without analog in prior
  phases?

Output to `.scratch_7a6/cell_walk_tongue.md` and
`.scratch_7a6/cell_walk_jaw.md` (gitignored).

Pay specific attention to:

- **Tongue notebook**: where does the mean/SEM section START relative
  to Cell 50? Did 7a.4's Cell 50 visual gate include some of the
  mean/SEM cells already? If yes, capture which cells are
  already-shipped-via-7a.4 vs net-new for this phase.
- **Jaw notebook**: cells 30/32/34/37/39/43 (production-viz per
  7a.3-jaw audit) — which belong to the mean/SEM family vs other
  plot types? Cell 43 PSD specifically: does the section header
  span over Cell 43 or stop before it?
- **Cross-bodypart code overlap**: are the plot helpers in tongue
  and jaw notebooks ~identical (just bodypart-token-swap) or
  bodypart-specific (different aesthetic / axes / aggregation)?
  Determines architecture choice (sibling modules vs parametric).

#### 1c. Plot-family inventory + comparison

Cross-tabulate the plot families found in both bodyparts:

| Plot family | Tongue cell(s) | Jaw cell(s) | Shape | Outputs |
|---|---|---|---|---|
| ... | ... | ... | (per-session OR cross-cohort OR both) | (CSV / PNG / etc) |

If a plot family exists in both bodyparts with same shape, that's a
parametric-module candidate. If shapes diverge, sibling modules.

#### 1d. Saved-output inventory on MICROSCOPE

For each production cell's output, locate the saved files. Pattern
likely:
- `\\research...\Priya\DeepLabCut\O2_analysis\{mouse}\{mouse}_{tongue,jaw}_kinematics\kinematics_figures\centered_{spout,eye}_midpoint\<plot_family_subdir>\...`

Capture: file extensions + sizes + mtimes (vintage of analysis) +
sample headers (CSVs) or filename patterns (PNGs).

If outputs aren't found for any production cell, that's worth
reporting — could mean cells weren't run cohort-wide, were pruned,
or saved to a non-obvious path. Each shifts outcome reasoning.

Output to `.scratch_7a6/output_inventory.md`.

#### 1e. Cross-bodypart dependency analysis

Document what each section's code consumes:
- 7a.2 interpolated_traces parquet (per-frame X/Y) — likely yes for
  both bodyparts.
- 7a.3 V3 endpoints JSON (tongue per-trial scalars) — likely tongue-side.
- 7a.5 jaw_pertrial endpoints JSON — likely jaw-side, if the section
  uses any per-trial scalars.
- Reward-frame timestamps — likely consumed for reward-aligned mean/SEM.
- Bodypart-specific intermediates that may NOT exist in the
  consolidated pipeline yet — flag explicitly.

If the audit surfaces consumed inputs that don't have consolidated
equivalents, that's a structural gap: either backfill the upstream
emit (separate phase) or use a different consolidated input that
serves the same purpose.

#### 1f-pre. Notebook skeleton inventory

Read both target notebooks + the three pattern notebooks:

```bash
ls -la C:\Users\sabatini\GitHub\stroke_orofacial_pipeline\notebooks\
# Targets (currently 2-cell skeletons):
#   13_dlc_kinematics_tongue.ipynb
#   14_dlc_kinematics_jaw.ipynb
# Patterns (fully populated, follow this shape):
#   10_dlc_build_parquets.ipynb
#   11_dlc_spatial_whole_session.ipynb
#   12_dlc_spatial_reward_aligned.ipynb
```

Confirm 13 + 14 are still skeletons (title + USER INPUTS only). If
populated by anyone since the kickoff, STOP and report — that's a
3-tier disambiguation moment.

Inventory the public entry points already on the modules that 13 +
14 will need to call. Likely surface area:

- `stroke_orofacial.dlc_kinematics.interpolation` — 7a.2 per-frame
  interpolated traces builder.
- `stroke_orofacial.dlc_kinematics.tongue_pertrial` — 7a.3 V3 per-trial
  tongue scalars.
- `stroke_orofacial.dlc_kinematics.jaw_pertrial` — 7a.5 per-trial jaw
  scalars.
- `stroke_orofacial.dlc_kinematics.tongue_visual` — 7a.4 angle/phase
  plots.
- `stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch` — 7a.5
  classifier + 4 plot families (tongue notebook only).
- `stroke_orofacial.dlc_kinematics.{tongue,jaw}_mean_sem_visual` (or
  parametric module) — this phase's new deliverable.

For each module, identify the `build_*_by_animal_date(animal, date,
resolver, ...)` -shaped wrappers that the orchestration notebooks
should call. If any are missing (modules expose only lower-level
internals + parity-script-only convenience functions), flag for
Outcome decision — the notebook task may need to add small wrappers
to the existing modules (additive only, no algorithm changes).

Output to `.scratch_7a6/notebook_inventory.md`: target notebook
state, pattern notebook structure, list of public wrappers per
module + gaps.

#### 1f. Cell 43 PSD fold-in decision

Read Cell 43 carefully + the markdown headers immediately before and
after it. Determine:
- Is Cell 43 inside the `## Per session and combined mean/SEM plots`
  section, or in a sibling/adjacent section?
- Does it conceptually fit (per-session jaw output, time-series shape)
  or diverge (frequency-domain analysis, distinct from time-domain
  mean/SEM)?

Recommend fold-in or defer. Priya picks at outcome decision.

#### 1g. Outcome proposal

Based on findings 1a-1f, propose Outcome A / B / C with:
- Recommended deliverable list (vendor / config / paths / module(s) / tests / parity / DECISIONS / PR).
- Estimated commit count + line counts.
- Architecture recommendation (sibling modules vs bodypart-parametric).
- Cell 43 PSD fold-in recommendation.
- Tongue-Cell-50 overlap resolution.
- Any open scope questions for Priya.

#### 1h. STOP-and-report

Report to Priya:
- Both notebook SHA256s confirmed unchanged.
- Per-cell classification summaries (counts per class, per bodypart).
- Plot-family inventory cross-tabulated tongue vs jaw.
- Saved-output paths on MICROSCOPE (or gaps if any).
- Cross-bodypart dependency analysis.
- Cell 43 PSD fold-in recommendation.
- Tongue-Cell-50 overlap resolution.
- Architecture recommendation (sibling vs parametric).
- Notebook skeleton state confirmed (13 + 14 unchanged 2-cell
  skeletons) + public wrapper inventory per consumed module + any
  gaps where additive `build_*_by_animal_date(...)` helpers would
  be needed.
- Outcome recommendation: A / B / C with one-paragraph justification.
- Any structural gaps (consumed inputs without consolidated
  equivalents) that would require pre-work.
- All scratch notes at `.scratch_7a6/`.

#### 1i. Commit (only if non-scratch docs were written)

```bash
# .scratch_7a6/ is gitignored via the .scratch_*/ pattern.
# Task 1 produces no committed files — pure investigation.
git status   # should be clean modulo gitignored scratch
```

### Task 1 outcome — LOCKED 2026-05-01

Priya picked all 7 of Cowork's recommendations. Outcomes A and C are
no longer in play; Outcomes A/C blocks below have been removed.

| # | Question | Decision |
|---|---|---|
| 1 | Outcome | **B** (substantial port; ~10-12 commits given 5,287L net-new) |
| 2 | Architecture | **Bodypart-parametric** `mean_sem_visual.py` (single module taking `bodypart: Literal["tongue", "jaw"]`) |
| 3 | Cell 43 PSD | **Defer** to a future Phase 7a.x-PSD (tongue 60-86 + jaw 43 + face PSD together) |
| 4 | Tongue trial viewers (cells 34/37/40/43) | **Skip** — exploratory `plt.show()`-only, no saved outputs (~1,414L excluded) |
| 5 | Tongue mean video (cells 47+48) | **Consolidate** into single function with `with_frame_timestamps: bool = True` kwarg, matching jaw Cell 34 shape |
| 6 | Tongue path casing | **Lowercase `_tongue_kinematics/`** — fix legacy Cell 31 bug; consolidated tree already uses lowercase from 7a.3 V3 / 7a.4 |
| 7 | Output layout | **Adopt jaw's per-window subdirs** (`rewardAligned_{pre}-{post}/...`) uniformly — fixes latent tongue-overwrite bug |

All seven decisions are documented in `.scratch_7a6/AUDIT_REPORT.md` §1g
and re-stated in DECISIONS at Task 9.

### Net-new scope after locks

7 production cells, ~3,873L (5,287L — 1,414L exploratory skipped):

- **Tongue net-new**: cells 31 (master mean/SEM, ~722L), 45 (mean trace),
  47+48 (mean video → consolidate into one).
- **Jaw net-new**: cells 30 (master mean/SEM, ~722L), 32 (mean trace,
  multi-bin), 34 (mean video).
- **Plot families** (from master cells 31/30, byte-near-identical):
  `individual_sessions`, `trial_overlays`, `session_overlays`,
  `binned_overlays`. Plus `mean_trace` (with multi-bin support
  ported to tongue from jaw) and `mean_video` (consolidated).

### Task 2 — Vendor production cells

Goal: byte-identical capture of the 7 production cells under
`docs/legacy_snippets/`, mirroring the 7a.0/7a.3/7a.5 pattern.

Files to write (4 vendored snippet files, NOT the exploratory cells):

- `docs/legacy_snippets/tongue_mean_sem_section.py` — concatenates
  cells 31 + 45 + 47 + 48 from
  `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` byte-
  identically, with cell-boundary delimiter comments
  (`# === Cell 31 ===`, etc.) so each cell is greppable.
- `docs/legacy_snippets/jaw_mean_sem_section.py` — concatenates cells
  30 + 32 + 34 from
  `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` byte-
  identically, with cell-boundary delimiters.

Verify byte-identicality:

```python
# After vendor: re-extract source from notebook JSON, compare against
# the vendored .py minus the delimiter comments. Diff must be empty.
```

Report cell-source line counts in commit message. Single commit:

```bash
git add docs/legacy_snippets/tongue_mean_sem_section.py
git add docs/legacy_snippets/jaw_mean_sem_section.py
git commit -m "Phase 7a.6 Task 2: vendor mean/SEM section cells (byte-identical)

Tongue: cells 31, 45, 47, 48 from 20260203 ws_aligned notebook.
Jaw: cells 30, 32, 34 from 20260416 ws_aligned notebook.
Exploratory tongue cells 34/37/40/43 deliberately excluded per Task 1
outcome decision (plt.show()-only, no saved outputs)."
git push
```

### Task 3 — Config + paths + tests scaffolding

Add to `configs/defaults.yaml` under `dlc_kinematics:`:

```yaml
dlc_kinematics:
  # ... (existing 7a.2/7a.3/7a.4/7a.5 blocks unchanged) ...
  mean_sem_visual:
    # Top-level knobs from master cells 31/30 (byte-near-identical).
    # Keep all knob names verbatim from legacy KNOBS section.
    plot_individual_sessions: true
    trial_overlays: true
    session_overlays: true
    binned_overlays: true
    # Reward window (used in subdir naming + data extraction):
    reward_pre_s: 2.0
    reward_post_s: 5.0
    # Per-bodypart knobs that diverge between tongue and jaw.
    # Audit-confirmed divergent values; identical values stay at top
    # level above.
    tongue:
      # ... bodypart-specific overrides ...
    jaw:
      # ... bodypart-specific overrides ...
      multi_bin_mean_trace: true   # jaw-only feature, ported to tongue too
```

Audit task: enumerate every KNOB defined in master cells 31/30,
classify as "shared" (identical between bodyparts) or "divergent"
(different value per bodypart), structure config block accordingly.

Path resolvers in `src/stroke_orofacial/paths.py`:

```python
def mean_sem_visual_dir(
    self, bodypart: Literal["tongue", "jaw"],
    center_mode: str, reward_pre_s: float, reward_post_s: float,
    plot_family: str, animal: str,
) -> Path:
    """Per-window subdir layout (Q7 decision):
    {outputs}/dlc_kinematics/mean_sem/{bodypart}/{center_mode}/
    rewardAligned_{pre}-{post}/{plot_family}/{animal}/
    """
    pre = _format_window_int(reward_pre_s)
    post = _format_window_int(reward_post_s)
    window_dir = f"rewardAligned_{pre}-{post}"
    return (
        self.pipeline_outputs("dlc_kinematics") / "mean_sem"
        / bodypart / center_mode / window_dir / plot_family / animal
    )
```

Tests for the path resolver under
`tests/test_paths_mean_sem_visual.py`:
- Parametric over both bodyparts.
- Window formatting: `(2.0, 5.0)` → `rewardAligned_2-5`.
- Asserts lowercase `_tongue_kinematics/`-equivalent subdir naming
  (no capital-T anywhere in consolidated tree).

Single commit:

```bash
git add configs/defaults.yaml
git add src/stroke_orofacial/paths.py
git add tests/test_paths_mean_sem_visual.py
git commit -m "Phase 7a.6 Task 3: mean_sem_visual config block + path resolver

Bodypart-parametric config with shared knobs at top level + per-
bodypart override blocks. Path resolver implements Q7 per-window
subdir layout (rewardAligned_{pre}-{post}/...) and Q6 lowercase
tongue convention.

7a.x family schemas (interpolation, per-trial features, visual,
day-binned, mismatch) unchanged."
git push
```

### Task 4 — Bodypart-parametric `mean_sem_visual.py` module

Create `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`. Public
API:

```python
def build_individual_sessions(
    bodypart: Literal["tongue", "jaw"],
    animal: str, date: datetime.date,
    resolver: PathResolver, params: dict,
    overwrite: Literal["skip", "force", "prompt"] = "skip",
) -> Path | None: ...

def build_trial_overlays(...) -> Path | None: ...
def build_session_overlays(...) -> Path | None: ...   # cohort
def build_binned_overlays(...) -> Path | None: ...     # cohort
def build_mean_trace(
    bodypart: Literal["tongue", "jaw"],
    animal: str, date: datetime.date,
    resolver: PathResolver, params: dict,
    multi_bin: bool = True,   # default-true; tongue gets the upgrade
    overwrite: Literal["skip", "force", "prompt"] = "skip",
) -> Path | None: ...

def build_mean_video(
    bodypart: Literal["tongue", "jaw"],
    animal: str, date: datetime.date,
    resolver: PathResolver, params: dict,
    with_frame_timestamps: bool = True,   # Q5 consolidate
    overwrite: Literal["skip", "force", "prompt"] = "skip",
) -> Path | None: ...

# Composite wrappers (called by orchestration notebooks):
def build_mean_sem_by_animal_date(
    bodypart: Literal["tongue", "jaw"],
    animal: str, date: datetime.date,
    resolver: PathResolver, params: dict,
    overwrite: Literal["skip", "force", "prompt"] = "skip",
) -> dict[str, Path | None]:
    """Calls all per-session families. Returns {family_name: output_path | None}."""
    ...

def build_mean_sem_cohort(
    bodypart: Literal["tongue", "jaw"],
    animals: list[str], date_range: tuple[date, date],
    resolver: PathResolver, params: dict,
    overwrite: Literal["skip", "force", "prompt"] = "skip",
) -> dict[str, Path | None]:
    """Calls all cross-session families."""
    ...
```

Bodypart-parametric implementation rules:

- Where master cells 31/30 are byte-identical, write one
  implementation that takes `bodypart` as a string token (e.g., for
  filename composition: `f"{bodypart}_kinematics"`, where the
  parametrically-passed value is `"tongue"` or `"jaw"`).
- Where they diverge (tongue 47/48 split → consolidate, jaw 32 multi-
  bin → port to tongue too), write `if bodypart == "tongue": ...
  elif bodypart == "jaw": ...` branches with explanatory `# why`
  comments.
- Do NOT introduce new bodypart strings. The two locked values are
  `"tongue"` and `"jaw"`.

Pure-rendering work allowed without parity break (per 7a.5
precedent): figure size, DPI, axis label font, colorbar position,
faint-trial overlay alpha/linewidth — match legacy values verbatim
from the master cells. Numerical outputs (CSVs / NPZs) must be bit-
stable.

Likely 1-2 commits given ~700L of port:

```bash
# Commit C4.1: skeleton + per-session families (individual_sessions,
# mean_trace, mean_video). Smoke-test against 1 (animal, date).
git add src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py
git commit -m "Phase 7a.6 Task 4 (C4.1): mean_sem_visual.py per-session families

Parametric over bodypart. individual_sessions / mean_trace /
mean_video. Tongue mean_video consolidates legacy cells 47+48 via
with_frame_timestamps kwarg (Q5). Tongue mean_trace gains multi-bin
support from jaw (Q5/Task 1 finding)."

# Commit C4.2: cohort families (trial_overlays, session_overlays,
# binned_overlays) + composite wrappers.
git commit -am "Phase 7a.6 Task 4 (C4.2): cohort families + composite wrappers

trial_overlays, session_overlays, binned_overlays. Composite
build_mean_sem_by_animal_date + build_mean_sem_cohort wrappers
matching the by_animal_date pattern from 7a.2/7a.3/7a.5."
git push
```

### Task 5 — Unit tests

Tests under `tests/test_mean_sem_visual.py`:

- Parametric: every public function exercised with `bodypart="tongue"`
  AND `bodypart="jaw"`.
- Synthetic data fixtures small enough to run in <30s total.
- `tmp_path`-based output roots per the project's tests-don't-write-
  to-real-outputs rule (CLAUDE.md §"Tests must not write to the real
  stroke_orofacial_pipeline_outputs/ tree").
- Smoke-tests that verify the public API contracts (return shapes,
  file existence, basic header schemas of emitted CSVs/NPZs).
- Multi-bin handling in mean_trace: explicit test with `multi_bin=False`
  AND `multi_bin=True`.
- `with_frame_timestamps` handling in mean_video: both branches.
- Per-window subdir formatting verified (Q7).
- Lowercase tongue path verified (Q6).

```bash
pytest tests/test_mean_sem_visual.py -v
git add tests/test_mean_sem_visual.py
git commit -m "Phase 7a.6 Task 5: unit tests for mean_sem_visual

Parametric over both bodyparts. Synthetic-data fixtures, tmp_path
output roots. Q5 (with_frame_timestamps, multi_bin) and Q6/Q7 path
conventions covered."
git push
```

### Task 6 — Parity harness + cohort run

Parity script under
`tests/scripts/parity_phase7a6_mean_sem.py`. Two modes (matching
7a.2/7a.3/7a.5 precedent):

- `default` mode: bit-stable comparison against in-repo reference
  (consolidated re-emit). Fast.
- `legacy_approximate` mode: comparison against legacy MICROSCOPE
  outputs at `atol=1e-6` over the 14-session scope (matching prior
  7a.x phases — same animals, same dates).

Numerical-parity targets per plot family (where data files exist
on legacy side):

| Family | Legacy artifact | Atol |
|---|---|---|
| individual_sessions | per-session CSV (X/Y traces, mean, SEM) | 1e-6 |
| mean_trace | per-session NPZ (binned trace arrays) | 1e-6 |
| trial_overlays | per-cohort CSV (per-trial means) | 1e-6 |
| session_overlays | per-cohort CSV (per-session means) | 1e-6 |
| binned_overlays | per-cohort CSV (binned-by-day means) | 1e-6 |
| mean_video | not parity-comparable (video frames); visual-gate only | n/a |

If the audit's output-inventory found that some plot families don't
have legacy data artifacts (just PNGs), document the gap and flag
those families as visual-gate-only (no numerical parity). Per the
7a.4 precedent that's acceptable when the plotting code is the only
producer.

Cohort run: emit consolidated outputs over the 14-session set, both
bodyparts. Capture into `.scratch_7a6/cohort_run/` (gitignored).

```bash
git add tests/scripts/parity_phase7a6_mean_sem.py
git commit -m "Phase 7a.6 Task 6: parity harness + 14-session cohort run

default mode: bit-stable. legacy_approximate mode: atol=1e-6 over
14-session legacy parity scope. Per-family parity targets documented.
mean_video is visual-gate-only (no numerical artifact)."
git push
```

If parity holds at atol=1e-6 across all comparable families, proceed
to Task 7. If residual band shows up (matching prior 7a.x precedents
e.g. scipy drift), document the residual + atol bump in DECISIONS and
proceed.

### Task 7 — Visual gate iteration (C7.x)

Visual-gate runner under `tests/scripts/parity_phase7a6_visual_gate.py`,
matching 7a.4/7a.5 machinery:

- Aspect-aware `fig_h = panel_w / consolidated_aspect` for crisp
  consolidated PNG rendering.
- LANCZOS resampling in PIL for compare-grid downsampling.
- Comparison grid per (bodypart, plot_family, sample-session-set):
  consolidated PNG | legacy PNG side-by-side.
- Renders to `.scratch_7a6/visual_gate/` (gitignored).
- For each comparison grid, runner writes a verdict prompt that
  Priya fills in directly in the kickoff feedback loop.

Iteration pattern (C7.1 / C7.2 / C7.3 commits as needed) — same
disposition as 7a.5-mismatch's C6.1/C6.2/C6.3:

- C7.1: first-pass renders. Priya eyeballs all comparison grids.
- C7.2: pure-rendering fixes (figsize, axis labels, colorbar
  position, faint-trial overlay alpha/linewidth, sort order). No
  algorithm changes; numerical parity from Task 6 must remain bit-
  stable across these commits.
- C7.3: any final tweaks to land all grids at PASS verdict.

Each iteration commit:

```bash
git commit -am "Phase 7a.6 Task 7 (C7.N): visual gate fix — <description>"
git push
```

Each commit must include a `pytest -q tests/scripts/parity_phase7a6_mean_sem.py`
re-run that confirms numerical parity unchanged (matching the C6.x
discipline from 7a.5).

### Task 8 — Populate notebooks 13 + 14

Pattern from `notebooks/10_dlc_build_parquets.ipynb`,
`notebooks/11_dlc_spatial_whole_session.ipynb`,
`notebooks/12_dlc_spatial_reward_aligned.ipynb`.

`notebooks/13_dlc_kinematics_tongue.ipynb` — full pipeline:

```
Cell 0  (markdown)  Title
Cell 1  (code)      USER INPUTS — ANIMALS, DATES, OVERWRITE, knobs
Cell 2  (code)      Imports + resolver + animals_config + defaults
Cell 3  (code)      Build manifests per (animal, date)
Cell 4  (code)      Per-(animal, date) loop — interpolation (7a.2)
Cell 5  (code)      Per-(animal, date) loop — per-trial scalars (7a.3 V3)
Cell 6  (code)      Per-(animal, date) loop — angle/phase visual (7a.4)
Cell 7  (code)      Per-(animal, date) loop — mismatch classifier (7a.5)
Cell 8  (code)      Per-(animal, date) loop — mean/SEM per-session (7a.6)
Cell 9  (code)      Cohort — mean/SEM cross-session families (7a.6)
Cell 10 (code)      Summary print
```

`notebooks/14_dlc_kinematics_jaw.ipynb` — full jaw pipeline:

```
Cell 0  (markdown)  Title
Cell 1  (code)      USER INPUTS — ANIMALS, DATES, OVERWRITE, knobs
Cell 2  (code)      Imports + resolver + animals_config + defaults
Cell 3  (code)      Build manifests per (animal, date)
Cell 4  (code)      Per-(animal, date) loop — interpolation (7a.2)
Cell 5  (code)      Per-(animal, date) loop — per-trial scalars (7a.5 jaw_pertrial)
Cell 6  (code)      Per-(animal, date) loop — mean/SEM per-session (7a.6)
Cell 7  (code)      Cohort — mean/SEM cross-session families (7a.6)
Cell 8  (code)      Summary print
```

Notebook contract reminders:

- Notebooks orchestrate; no analytical code. Every cell after USER
  INPUTS imports from `stroke_orofacial` and calls public functions.
- Every cell handles per-session errors gracefully (try/except, log,
  continue) — matching the patterns in notebooks 10/11/12.
- Smoke-test by executing each notebook against 1 (animal, date)
  sample. Add the smoke-test command to the kickoff retrospective
  notes in DECISIONS.

If any module from prior phases lacks a public
`build_*_by_animal_date(...)`-shaped wrapper that these notebooks
need (per the Task 1 audit's notebook-inventory step), add an
additive helper to the relevant prior-phase module — additive only
(no algorithm changes, no signature changes to existing exports).
Document each additive helper in DECISIONS.

```bash
# Smoke-test:
jupyter nbconvert --to notebook --execute \
    notebooks/13_dlc_kinematics_tongue.ipynb \
    --output /tmp/13_smoke.ipynb 2>&1 | tail -20
jupyter nbconvert --to notebook --execute \
    notebooks/14_dlc_kinematics_jaw.ipynb \
    --output /tmp/14_smoke.ipynb 2>&1 | tail -20

git add notebooks/13_dlc_kinematics_tongue.ipynb
git add notebooks/14_dlc_kinematics_jaw.ipynb
# Plus any additive helpers + their tests if needed:
git add src/stroke_orofacial/dlc_kinematics/<module>.py tests/<corresponding test>
git commit -m "Phase 7a.6 Task 8: populate notebooks 13 + 14 end-to-end

13: full tongue pipeline (7a.2 → 7a.3 → 7a.4 → 7a.5 → 7a.6).
14: full jaw pipeline (7a.2 → 7a.5 jaw_pertrial → 7a.6).
Pattern from notebooks 10/11/12. Smoke-tested against 1 (animal,
date) sample per notebook. Closes the 7a.x notebook-population debt
flagged 2026-05-01."
git push
```

### Task 9 — DECISIONS + MIGRATION_LOG + PR + tag

Append to `docs/DECISIONS.md` a `## Phase 7a.6 — Mean/SEM visual gate`
section. Cover all 7 Task 1 decisions verbatim from the table above,
plus implementation-time decisions discovered during Tasks 2-8 (any
additive wrappers added, any residual atol bumps, any visual-gate
deviations from legacy that survived to PASS).

Append to `docs/MIGRATION_LOG.md` a Phase 7a.6 entry summarizing:

- Net-new modules: `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`.
- Net-new path resolver: `mean_sem_visual_dir(...)`.
- Notebooks populated: `notebooks/13_dlc_kinematics_tongue.ipynb`,
  `notebooks/14_dlc_kinematics_jaw.ipynb`.
- Behavior diffs vs. legacy: tongue path lowercased (Q6), per-window
  subdirs uniform (Q7), tongue mean video consolidated (Q5), tongue
  mean_trace gained multi-bin (audit finding).
- Skipped: tongue exploratory cells 34/37/40/43, Cell 43 PSD
  (deferred).
- Parity scope: 14-session legacy_approximate at atol=1e-6. Visual
  gate verdict: PASS (Priya, dated).

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git commit -m "Phase 7a.6 Task 9: DECISIONS + MIGRATION_LOG"
git push

gh pr create --base main --head phase/7a.6-mean-sem \
    --title "Phase 7a.6: Mean/SEM visual gate (tongue + jaw, parametric)" \
    --body "$(cat <<'EOF'
## Summary

Closes Phase 7a.6 — bodypart-parametric mean/SEM visual gate for
tongue + jaw. ~3,873L net-new (after exploratory skip). 7 production
cells ported across both ws_aligned notebooks. New
`mean_sem_visual.py` module, parity at atol=1e-6 over 14-session
scope, visual gate PASS, notebooks 13 + 14 populated.

See `docs/DECISIONS.md` Phase 7a.6 section for the 7 Task 1 decisions
+ implementation deviations.

## Test plan

- [x] `pytest tests/test_mean_sem_visual.py` passes
- [x] `pytest tests/scripts/parity_phase7a6_mean_sem.py` (default mode) bit-stable
- [x] `parity_phase7a6_mean_sem.py --mode legacy_approximate` atol=1e-6 PASS
- [x] Visual gate PASS verdict from Priya
- [x] Notebooks 13 + 14 smoke-tested against 1 (animal, date) sample

## Closes the 7a.x notebooks debt

Notebooks 13 + 14 were 2-cell skeletons since Phase 6 created them.
This PR populates both end-to-end with the full 7a.x chain.
EOF
)"
```

After Priya merges + tags `v7a.6-mean-sem`, branch can be left in
place per CLAUDE.md ground rule 8.

---

## Constraints (across all tasks)

- **Phase 7a.6 scope is tongue + jaw "Per session and combined mean/SEM
  plots" sections ONLY.** No DLC heatmaps (7a.7). No new reward-aligned
  heatmaps (7a.8). No spout behavior (8a.10). No stats plots (Phase 9).
  No green-field jaw per-trial design. No whisker / face-velocity /
  PSD work (separate phase, even if Cell 43 PSD folds in here it
  stays narrow to the one cell).
- **No source data modification.** Tongue + jaw notebooks stay read-
  only on MICROSCOPE. Vendor (if Outcome B/C demands) follows the
  7a.0/7a.3/7a.5 byte-identical pattern.
- **No legacy-repo edits.**
- **No 7a.2 / 7a.3 V3 / 7a.4 / 7a.3-jaw / 7a.5-mismatch module
  changes.** All locked by their respective phase merges; additive
  helpers allowed only if Task 1 finds the port genuinely needs to
  expose existing in-memory products (analogous to 7a.4's
  `build_tongue_visual_bundle` pattern). Notebook authoring (Outcome
  A Task 5 / Outcome B Task 7 / Outcome C analog) MAY require
  additive `build_*_by_animal_date(...)`-shaped wrappers on prior
  7a.x modules — these are allowed and follow the same additive-
  only rule (no algorithm changes, no signature changes to existing
  exports).
- **STOP-and-report at Task 1.** Outcome decision is Priya's call.
- **No advancing past Task 1** until Priya picks A/B/C + architecture
  + Cell 43 fold-in + Cowork extends the kickoff with Task 2+ specifics.
- **No force-push.** All pushes additive to `phase/7a.6-mean-sem`.
- **No tag until after merge.** Tagging is Priya's call on the merge
  commit per CLAUDE.md ground rule 8.
- **MICROSCOPE access required** for Task 1 (notebook reads + saved-
  output discovery) and for any later parity/visual-gate work.
- **If sibling notebooks surface** that compete via the 3-tier rule:
  STOP and report.
- **If Task 1 surfaces structural gaps** (consumed inputs without
  consolidated equivalents): STOP and report. Don't silently work
  around — Priya may need to schedule pre-work.
- **If Cell 43 PSD belongs to the mean/SEM section structurally but
  Priya prefers to defer to strategy §7 PSD work**: split decision
  acceptable; defer Cell 43 to its own follow-up.

---

## Reference points for the auditor

- **Tongue notebook** (canonical) —
  `\\research...\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
  (SHA256 `ED12C54...`).
- **Jaw notebook** (canonical) —
  `\\research...\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`
  (SHA256 `7be0eee0...`).
- **Vendored Cells from prior phases**:
  - `docs/legacy_snippets/tongue_pertrial_features.py` — Cells
    33/36/39/42/50 (Phase 7a.3 V3, commit `0b78128`).
  - `docs/legacy_snippets/tongue_jaw_mismatch.py` — Cells 51-55
    (Phase 7a.5, commit `4d34a8f`).
- **Existing consolidated outputs** likely consumed by mean/SEM
  cells:
  - `<outputs>/dlc_kinematics/interpolated_traces/{tongue, jaw}/{animal}/{date}.parquet`
    (Phase 7a.2 — both bodyparts).
  - `<outputs>/dlc_kinematics/endpoints/{animal}/{date}.json`
    (Phase 7a.3 V3 tongue per-trial scalars).
  - `<outputs>/dlc_kinematics/jaw_pertrial/endpoints/{animal}/{date}.json`
    (Phase 7a.5 jaw per-trial scalars).
  - `<outputs>/dlc_kinematics/features/tongue/{animal}/{date}.parquet`
    (Phase 7a.3 V3 per-frame angle).
  - `<outputs>/dlc_kinematics/licking_dynamics/traces/{animal}/{date}.parquet`
    (Phase 7a.3 V3 per-session traces).
  - `<outputs>/spout_behavior/...` — reward-frame indices via
    `RewardAlignedWindow` etc.
- **Existing visual modules** worth examining for pattern-reuse:
  - `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` (7a.4 — 5
    plot families for tongue angle/phase).
  - `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`
    (7a.5 — classifier + 4 plot families for mismatch).
- **Notebook pattern** (orchestration shape this phase's notebooks
  must match):
  - `notebooks/10_dlc_build_parquets.ipynb` — manifest-driven
    per-(animal, date, mode) loop calling `build_centered_parquet`.
  - `notebooks/11_dlc_spatial_whole_session.ipynb` — manifest-driven
    per-(animal, date, bodypart, mode) loop with per-bodypart output
    directories + skip/force overwrite handling.
  - `notebooks/12_dlc_spatial_reward_aligned.ipynb` — analogous shape
    with reward-window inputs.
  - All three: USER INPUTS markdown banner cell, then imports +
    resolver, then manifest build, then processing loop. No
    analytical code; everything imports from `stroke_orofacial`.
- **Notebook targets** (currently 2-cell skeletons; Phase 7a.6
  populates):
  - `notebooks/13_dlc_kinematics_tongue.ipynb` — full 7a.2 → 7a.3 →
    7a.4 → 7a.5 → 7a.6 chain for tongue.
  - `notebooks/14_dlc_kinematics_jaw.ipynb` — full 7a.2 → 7a.5 jaw_pertrial
    → 7a.6 (+ Cell 43 PSD if folded) chain for jaw.
- **DECISIONS Phase 7a.3-jaw entry** — context for the 6
  production-viz cells in jaw notebook + Cell 43 PSD deferral.
- **DECISIONS Phase 7a.5-mismatch entry** — context for the visual-
  gate iteration patterns (C6.1 / C6.2 / C6.3) which 7a.6 may inherit.
- **DECISIONS Phase 7a.4 entry** — context for visual-gate machinery
  + comparison-grid LANCZOS resampling + aspect-aware figsize that
  7a.6 should reuse.
- **`docs/phase-7/interpolation-strategy.md`** — phase 7a design
  brief; §6 parity scope at 14 sessions.
