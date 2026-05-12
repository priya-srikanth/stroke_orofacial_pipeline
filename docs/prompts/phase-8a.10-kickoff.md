# Phase 8a.10 Kickoff — Spout-behavior visual gate + bare-vs-b comparison

**Branch:** `phase/8a.10-spout-visual-gate` off latest `origin/main`.
**Tag on phase-close merge:** `v8a.10-spout-visual-gate`.
**Prerequisites:** MICROSCOPE mount; conda env `stroke_orofacial` active; `main` HEAD at the post-Phase-7-pre-secondary-spout-chore + close-out-polish merges (b-half data durably on disk for the 19 Pattern B sessions).
**Estimated scope:** mid-to-large. Comparable to Phase 7a.5-mismatch (substantial per-family port) + bare-vs-b additive scope. Likely 15-25 source/test files + 3 docs files + this kickoff.

---

## Context

Phase 8a.10 was originally scoped (per `docs/COWORK_SESSION_STATE.md` Next-phase candidates list) as a "spout-behavior visual gate" — render comparison grids for the canonical `batch_process_behavior_report_20260116PS.ipynb` against the new pipeline's outputs, eyeball-verdict by Priya. Scope was **expanded 2026-05-12** per [Phase 7-pre-secondary-spout DECISIONS](../DECISIONS.md) fold-in decision: this phase also covers bare-vs-b spout-behavior outcome comparison for the 19 Pattern B sessions across PS51/PS54/PS55. The b-half data is now durably on disk in `pipeline_outputs/` (via the Phase 7-pre-secondary-spout chore re-emit PR).

**Audit-first** per the multi-half / secondary-spout / 7a.5-mismatch / 7a.6 pattern: Task 1 walks the legacy code and produces a per-plot-family port plan that Priya signs off on before any implementation commits land.

The phase has **two sub-deliverables in one PR**:

- **Sub-deliverable A — Legacy-parity gates (cohort-wide, full plot coverage).** Render every non-stat visualization the canonical behavior-report code produces; parity-check each rendering against the legacy PNGs.
- **Sub-deliverable B — Bare-vs-b comparison.** Five endpoints; 19 Pattern B sessions; reuses A's rendering code for endpoints 1-4; endpoint 5 is new.

The two sub-deliverables share rendering code (sub-deliverable B reuses A's renderers) but have different cohort scopes and verdict mechanisms.

---

## Cohort scope

### Cohort A — Legacy-parity gates

The full set of (animal, date) pairs covered by the legacy notebook's resolved `include_dates ∖ exclude_sessions` for PS46-PS55. Task 0.5 confirms inputs (Phase 2 outputs at `pipeline_outputs/spout_behavior/`) are durably on disk; Task 1 audit extracts the authoritative cohort definition from legacy code.

Approximate size: 100-200 sessions across 8 animals. Exact size locked at Task 1 STOP-and-report.

### Cohort B — Bare-vs-b comparison

The 19 Pattern B sessions from Phase 7-pre-secondary-spout:

- PS51 × 2: 2025-04-30, 2025-05-05
- PS54 × 11: 2025-04-30, 2025-05-30, 2025-06-16, 2025-06-18, 2025-06-19, 2025-06-20, 2025-06-21, 2025-06-23, 2025-06-24, 2025-06-25, 2025-06-26
- PS55 × 6: 2025-04-24 (with `bare_ws_subdir_override: "20250424a"`), 2025-04-28 (n_dlc=0; Phase 2 DLC-free so still produces outputs), 2025-04-30, 2025-05-30, 2025-06-01, 2025-06-05

All 19 sessions have b-half outputs on disk per the Phase 7-pre-secondary-spout chore PR.

---

## Sub-deliverable A — Legacy-parity gates

### Scope

Render every non-stat visualization produced by the canonical legacy behavior-report code:

- **`analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb`** — canonical per-mouse driver (latest YYYYMMDD; supersedes `*_20250503PS`, `*_20250528PS_mod`, base `batch_process_behavior_report` per 3-tier rule).
- **`analysis/behavior_report/behavior_report_PS.py`** — the module the notebook imports; defines endpoint computation + plot rendering for per-mouse outputs.
- **`analysis/behavior_report/summary_PS.py`** — cohort-summary visualizations. Task 1 audit confirms whether this is a visualization module or stats-only.
- **`analysis/behavior_report/playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65** — cross-session aggregation visualizations. Visualization-subset only; cells with stat-inferential output (paired t-tests, MixedLM, mean ± SD with significance overlays) get classified as **Phase 9 forward-pointer**, not 8a.10 scope.

Per Priya: the endpoint families known to be in scope include (non-exhaustive — Task 1 audit enumerates):

- First lick accuracy
- Correct + incorrect licks per side
- Lick raster
- First-lick latency
- Lick rate
- Lickiness
- Switchiness
- (others — Task 1 audit completes the list)
- Recovery trajectories (Phase 8a.8 functionality; covered here as the cohort-summary recovery visualization)

### Verdict mechanism

Per-family eyeball verdict. For each plot family, the parity gate renders:

- Legacy PNG (left) — sourced from Task 0.75 baseline capture.
- New pipeline rendering (right) — sourced from `visual_gate.py` ports.
- (Optional) diff or annotation panel below — only if pixel-level diff is informative for the family.

Priya signs off per family. Multiple iterative C-rounds expected (mirrors Phase 7a.5-mismatch C6.x / Phase 7a.6 C7.x iterative-visual-fix patterns).

### Implementation surface

- New module: `src/stroke_orofacial/spout_behavior/visual_gate.py`. Per-family render functions. Stateless; reads from `pipeline_outputs/spout_behavior/` NPZs + per-mouse JSON; writes PNGs to `pipeline_outputs/spout_behavior/visual_gate/{animal}/`.
- New module possibly: `src/stroke_orofacial/spout_behavior/cohort_summary.py` — cohort-level rendering (recovery trajectories + cross-session aggregation visualizations from playground cells 56-65). Split from `visual_gate.py` if the audit surfaces strong separation; otherwise fold in.
- New path resolvers under `PathResolver` for visual-gate output locations.

---

## Sub-deliverable B — Bare-vs-b comparison

### Scope

Five endpoints, 19 Pattern B sessions. Endpoints:

1. **First lick accuracy** — per-session bar (bare vs b), possibly stacked by trial-side. Cohort: per-animal recovery curve, rel_day on x, accuracy on y, bare + b as separate lines.
2. **Correct/incorrect licks per side** — faceted bar (L/R columns; correct/incorrect rows; bare vs b color/side). Cohort: per-side recovery curve.
3. **Lick raster** — side-by-side rasters (bare on left, b on right; same trial-ordering scheme as legacy). No cohort aggregation — sample N representative sessions (e.g., 1 per animal × pre/post-stroke phase).
4. **First-lick latency** — side-by-side distribution (violin or KDE) per session. Cohort: per-animal recovery curve of median latency.
5. **Reward acquisition rate over time** — within-session cumulative-rewards curve, bare + b overlaid per session. Cohort: per-animal recovery curve of session-level slope or AUC. **No legacy reference** — new visualization specified per kickoff (Task 1 audit may surface partial precedent in legacy code).

### Verdict mechanism

Feature-driven; no legacy baseline to compare against (legacy uniformly skipped b halves). Verdict is Priya eyeball-PASS on the comparison panels' clarity + scientific informativeness. Iterative C-rounds expected.

### Implementation surface

- Same module(s) as sub-deliverable A: reuse renderers for endpoints 1-4; add endpoint 5 + paired-panel composition + cohort-curve aggregation.
- Path resolvers extended for bare-vs-b output locations (e.g., `pipeline_outputs/spout_behavior/bare_vs_b/{animal}/{date}.png`).

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Apply the 3-tier rule (latest YYYYMMDD within a family; downstream-output mtime tiebreaker; STOP-and-ask). Candidate sources:

- `batch_process_behavior_report_20260116PS.ipynb` (canonical, latest YYYYMMDD) — supersedes 3 older copies (per Phase 7-pre-secondary-spout Task 1 audit).
- `behavior_report_PS.py` (canonical, latest) — supersedes `behavior_report_PS_20250528.py` + `behavior_report_PS_v0.py`.
- `summary_PS.py` — only version present.
- `playground_analyze_behavior_report_PS20250610.ipynb` — only version present.

Task 1 confirms no further disambiguation surprises.

### Dead code identification

Per-cell / per-function classification (Production / Exploratory / Deprecated / Ambiguous). Only Production gets ported. Task 1 reports the classification table.

Stat-inferential cells (paired t-tests, MixedLM, scipy.stats wrappers) → classify as **Phase 9 forward-pointer** rather than "deprecated"; they're legitimate code, just not 8a.10's scope.

### Sub-phase breakdown

Per Task structure below.

### Parity strategy

Per Sub-deliverable A's verdict mechanism: eyeball-PASS per family against Task 0.75 baseline PNGs. Mirrors 7a.X visual-gate verdict patterns.

### Hardcoded constants

The legacy notebook + module likely bake in many threshold / window / inclusion-criterion constants. Task 1 audit surfaces them; the port faithfully preserves them (visual-gate goal is reproduce-legacy, not re-design). Any constant that needs to vary per-animal goes to `configs/animals.yaml`; any cohort-wide constant goes to `configs/defaults.yaml`.

---

## Execute on branch `phase/8a.10-spout-visual-gate`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD is at the post-Phase-7-pre-secondary-spout-close-out-polish + chore-PR merges. Confirm MICROSCOPE mount. Confirm `import stroke_orofacial` + `pytest --collect-only -q` both exit 0.

Do NOT create the feature branch yet — Task 0.5 first.

### Task 0.5 — Cohort-on-disk audit

**Goal:** confirm sub-deliverable A's inputs (Phase 2 outputs) are durably present at `pipeline_outputs/spout_behavior/` for every (animal, date) in Cohort A.

**Steps:**

1. Define Cohort A. Read legacy's resolved `include_dates ∖ exclude_sessions` from:
   - `batch_process_behavior_report_20260116PS.ipynb` cell-2 (per Phase 7-pre-secondary-spout Task 1 audit, this is where `include_dates` is enumerated cohort-wide).
   - `playground_analyze_behavior_report_PS20250610.ipynb` cell-55 (the `mice_to_process = {..., exclude_sessions: [...]}` skip-list).

   Compute the resolved set as a Python `set[tuple[str, str]]` of `(animal, ISO-date)` pairs.

2. For each (animal, date) in Cohort A, check disk presence:
   ```python
   from stroke_orofacial.paths import PathResolver
   r = PathResolver()
   licks_path = r.pipeline_outputs("spout_behavior") / "licks_and_rewards" / animal / date_str / f"{date_str}.npz"
   exists = licks_path.exists()
   ```
   Tabulate: how many sessions have inputs on disk vs missing.

3. **STOP-and-report decision branch:**
   - **All inputs present** → proceed to Task 0.75.
   - **Gaps exist** → STOP and report which sessions are missing. Two recovery paths Priya picks from:
     - Spin a `chore/phase-8a.10-cohort-phase-2-reemit` PR (analogous to the Phase 7-pre-secondary-spout chore PR) that runs `process_session_by_animal_date` on the missing cohort. Merge before Task 0.75 starts.
     - Narrow Cohort A to "sessions with inputs on disk" — exclude missing sessions from sub-deliverable A's coverage; document the exclusion in DECISIONS.

### Task 0.75 — Legacy notebook execution + baseline capture

**Goal:** run `batch_process_behavior_report_20260116PS.ipynb` end-to-end on MICROSCOPE; capture all emitted PNGs to a baseline directory; these PNGs become sub-deliverable A's parity-comparison references.

**Steps:**

1. Locate legacy's per-mouse output dir: per Phase 7-pre-secondary-spout Task 1 audit, this is `basic_behavior_analysis3/` (the legacy `batch_process_behavior_report_20260116PS.ipynb` writes here). Confirm path under MICROSCOPE.

2. **If the legacy outputs are already on disk in `basic_behavior_analysis3/`** (from prior production runs), copy/snapshot them to `tests/scripts/_baselines/phase_8a_10/legacy_pngs/` for durable reference. Capture the snapshot's timestamp + a SHA256 manifest.

3. **If the legacy outputs need re-rendering** (e.g., notebook updated since last run, or Priya wants a fresh baseline): run the legacy notebook on MICROSCOPE via the `frsb` env (legacy-compatible) per Phase 7-pre-multi-half's `bnpm` dependency convention. Capture outputs to the baseline directory.

4. STOP-and-report: list the captured PNG count + per-mouse breakdown. Verify reasonable (one PNG per (mouse, plot-family) at minimum).

**No commits in Tasks 0.5/0.75 to the feature branch — these are pre-branch state-establishment.** Baseline PNGs land under `tests/scripts/_baselines/phase_8a_10/legacy_pngs/` as a chore-PR mirroring `tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json` from Phase 7-pre-secondary-spout's Task 0.5. The baselines commit happens on `main` directly (small chore PR, like PR #104 for Phase 7-pre-secondary-spout).

### Task 1 — AUDIT (STOP-and-report)

**Branch:** `phase/8a.10-spout-visual-gate`, created off the post-baseline `main`.

Walk the canonical legacy code:

1. **Per-cell / per-function classification.** For each candidate source listed in the "Legacy file disambiguation" section above:
   - Open the source; iterate cells (notebooks) or top-level functions (modules).
   - Classify each as Production / Exploratory / Deprecated / Ambiguous.
   - For Production items: record the plot family produced + dependencies (which Phase 2 NPZ fields it consumes) + estimated lines-to-port.

2. **Per-plot-family port plan.** For every Production plot family:
   - Name (e.g., "first_lick_accuracy", "lick_raster", etc.).
   - Source: `<file>::<function or cell>`.
   - Legacy output filename pattern (e.g., `{animal}_{date}_first_lick_accuracy.png`).
   - Phase 2 NPZ keys consumed.
   - Per-mouse vs cohort-level.
   - Estimated complexity: Trivial (< 50 lines) / Small (50-200) / Medium (200-500) / Large (> 500).

3. **Cohort A definition extracted.** Verify Task 0.5's preliminary cohort matches the audit's actual resolution of `include_dates ∖ exclude_sessions`. If divergence: report + reconcile.

4. **Stat-inferential plot enumeration.** List every plot/cell that produces stat output (p-values, F-statistics, model summaries). These get Phase 9 forward-pointer classification, not 8a.10 scope.

5. **Hardcoded-constant scan.** Surface every threshold / window / inclusion-criterion constant the legacy renderers consume. These will need to land in `configs/defaults.yaml` (cohort-wide) or `configs/animals.yaml` (per-animal) during Task 2.

6. **`summary_PS.py` classification.** Confirm whether this module produces visualization plots (in scope) or pure stats (Phase 9 forward-pointer) or mix (port viz parts; defer stats parts).

**STOP-and-report deliverable.** Post a Cowork-readable markdown summary including:

- Per-plot-family port plan table (~10-20 rows expected).
- Cohort A definitive size + (animal, date) list.
- Stat-inferential plot list (Phase 9 forward-pointer).
- Hardcoded-constant list.
- Recommendation on module-split: single `visual_gate.py` vs split `visual_gate.py` + `cohort_summary.py`.
- Outcome A or B recommendation:
  - **Outcome A — full coverage as scoped.** All Production plot families port; estimated total scope ≤ ~3,000 LoC.
  - **Outcome B — narrow first.** If the audit surfaces >25 plot families or >5,000 estimated LoC, recommend porting the top N "most scientifically important" families first; defer the rest to a follow-up phase. Priya picks.
  - **Outcome C — something else the audit surfaces.**

Priya picks Outcome before Task 2 starts. Task 1 produces zero commits on the feature branch.

### Task 2 — Per-family port (sub-deliverable A core implementation)

**Files:**
- `src/stroke_orofacial/spout_behavior/visual_gate.py` (new)
- Possibly `src/stroke_orofacial/spout_behavior/cohort_summary.py` (new; per Task 1 module-split recommendation)
- `src/stroke_orofacial/paths.py` — add resolvers for visual-gate output directories
- `configs/defaults.yaml` — add `visual_gate:` block for cohort-wide constants
- `configs/animals.yaml` — extend animal entries with any per-animal renderer constants surfaced by Task 1

**Per-family commit pattern:**
- One commit per plot family OR per family-group (judge based on inter-family coupling).
- Each commit: port function(s) into visual_gate.py + minimal unit tests in `tests/test_visual_gate.py` (or new test file).
- Tests focus on: function-signature contract, NPZ-key consumption, plot-axes labels/titles, key style choices (color palette, line widths). NOT pixel-perfect reproduction — eyeball-verdict in Task 3 handles that.

**Constraints:**
- NO writes to `pipeline_outputs/` from tests — `PathResolver(output_root=tmp_path)` per `docs/testing-conventions.md`.
- All public functions have docstrings.
- Inline comments explain *why* a port choice was made vs the legacy (especially for any documented deviations from legacy behavior).
- Faithful-port discipline: when in doubt, reproduce legacy exactly. Deviations require explicit DECISIONS entries (no silent improvements).

### Task 3 — Cohort-wide parity-gate execution + visual-verdict iteration

**Steps:**

1. Build a parity-comparison rendering script: `tests/scripts/parity_phase8a_10.py`. Mirror the multi-half / secondary-spout parity-harness skeleton. For each plot family × every Cohort A session:
   - Render the new-pipeline version.
   - Look up the legacy PNG at the Task 0.75 baseline directory.
   - Emit a comparison grid (legacy left / new right / annotation below) to `.scratch_phase_8a_10/comparison_grids/{family}/{animal}_{date}.png`.

2. Cohort-wide execution + Priya eyeball verdict per family. C1/C2/... iterative rounds expected:
   - C1: initial render; Priya reviews a sample (e.g., 5 sessions per family) + flags issues.
   - C2: fix issues from C1; re-render; Priya re-reviews.
   - ... iterate until Priya signs PASS per family.

3. **STOP-and-report** at each C-round so Priya can paste verdict findings.

4. Final verdict: per-family PASS/FAIL table. Goal is all-PASS. Per-family deferrals (FAIL after N rounds → carved out as future fix-up) get explicit DECISIONS entries.

### Task 4 — Sub-deliverable B: bare-vs-b extensions

**Files (extending Task 2's modules):**
- `src/stroke_orofacial/spout_behavior/visual_gate.py` — add bare-vs-b paired-panel composition functions for endpoints 1-4 (reuse Task 2's renderers).
- `src/stroke_orofacial/spout_behavior/visual_gate.py` — add endpoint 5: reward acquisition rate over time (new visualization).
- `src/stroke_orofacial/spout_behavior/visual_gate.py` — add per-animal cohort recovery curves for endpoints 1-2-4-5 (raster excluded — no cohort aggregation).
- `src/stroke_orofacial/paths.py` — bare-vs-b output resolvers.
- `tests/test_visual_gate.py` — extend with bare-vs-b composition tests.

**Per-endpoint commit pattern:**
- One commit per endpoint OR one commit per layer (per-session paired + per-animal cohort).

**Visual verdict iteration:** Same C-round pattern as Task 3, but no legacy reference to compare against. Verdict is "this comparison panel is scientifically informative and clear" — Priya signs off per-endpoint.

### Task 5 — DECISIONS + MIGRATION_LOG entries

**Files:**
- `docs/DECISIONS.md` — new top entry (reverse-chronological) capturing phase-close decisions:
  - Outcome A/B/C verdict from Task 1
  - Module-split decision (single `visual_gate.py` vs split)
  - Faithful-port discipline + any explicit deviations
  - Stats-plot Phase 9 forward-pointer scoping
  - Bare-vs-b endpoint-5 (reward acquisition rate over time) new-visualization spec
  - Task 0.5 cohort gaps decision (if any)
  - Task 3/4 per-family verdict + any deferrals
- `docs/MIGRATION_LOG.md` — append `## Phase 8a.10 — ...` section after Phase 7-pre-secondary-spout.

### Task 6 — State-doc refresh + open PR

**Files:**
- `docs/COWORK_SESSION_STATE.md` — refresh per the existing close-out pattern (banner / in-flight / next-phase candidates renumber / completed block / recent session log / warm-start prompt).
- `gh pr create` with comprehensive PR body summarizing the 4 sub-deliverables × per-family verdict table.

---

## Scope NOT in this phase (forward-pointers)

1. **Phase 9 stats forward-pointer.** Stat-inferential plots from `playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 (paired t-tests, MixedLM, mean ± SD with significance overlays) are out of scope. The Task 1 audit surfaces the precise list; they get a clean handoff to a future Phase 9 (statistics framework + spout endpoint stats).

2. **DLC bare-vs-b comparison.** Phase 7-pre-secondary-spout-compare-DLC. Blocked on DLC inference on b-half cam dirs. Out of scope here.

3. **8a.7 + 8a.7.5 broader coverage.** The original-spec 8a.10 was scoped to also cover the full 8a.7 endpoint slug list + 8a.7.5 criteria hierarchy visualizations. Priya 2026-05-12 narrowed to "all plots in behavior-report code"; the 8a.7 + 8a.7.5 broader coverage is implicitly deferred. If a clear consumer surfaces, carve out as a separate phase.

4. **Cohort-wide spout-behavior re-emit.** Task 0.5 audits whether Cohort A's inputs are present. If gaps exist, the recovery chore-PR is a sibling, not in scope here.

---

## File-touch allowlist

Tasks 2-4 should touch ONLY these files (paths from repo root):

```
# Source
src/stroke_orofacial/spout_behavior/visual_gate.py          (new)
src/stroke_orofacial/spout_behavior/cohort_summary.py       (new, conditional on Task 1 module-split)
src/stroke_orofacial/paths.py

# Configs
configs/defaults.yaml
configs/animals.yaml                                         (only if Task 1 surfaces per-animal constants)

# Tests
tests/test_visual_gate.py                                    (new)
tests/test_cohort_summary.py                                 (new, conditional)
tests/test_paths.py                                          (extensions for new resolvers)
tests/scripts/parity_phase8a_10.py                           (new)
tests/scripts/_baselines/phase_8a_10/legacy_pngs/*           (Task 0.75; lives on `main` via chore PR)

# Docs
docs/DECISIONS.md
docs/MIGRATION_LOG.md
docs/COWORK_SESSION_STATE.md
docs/prompts/phase-8a.10-kickoff.md                          (THIS file; already on main once kickoff-doc PR merges)
```

If Task 1 audit surfaces a need to touch additional files (e.g., a hardcoded-constant call site in an unexpected module, or a path-resolver refactor that extends beyond `paths.py`), the audit STOP-and-report extends this allowlist with explicit Priya approval.

**Out-of-scope touches that would violate this allowlist:**
- ANY edit to `src/stroke_orofacial/dlc_*` (DLC-side bare-vs-b is forward-pointer-only).
- ANY edit to `src/stroke_orofacial/spout_behavior/multi_half_merge.py` (Pattern A merge infrastructure locked).
- ANY edit to `src/stroke_orofacial/spout_behavior/session_processing.py` (Pattern B per-suffix driver locked).
- ANY edit to the existing 8a.7 / 8a.7.5 / 8a.8 modules unless Task 1 surfaces a specific need + Priya approves.

---

## CLAUDE.md compliance checklist

Before every commit:
- [ ] `git branch --show-current` returns `phase/8a.10-spout-visual-gate`.
- [ ] No source data modified.
- [ ] No legacy-repo files modified (read-only audit).
- [ ] No files modified that Claude Code didn't create itself in this consolidation project — except this same Claude Code session's prior turns OR consolidation-repo files within the touch allowlist above.
- [ ] Outputs go to `pipeline_outputs/spout_behavior/visual_gate/` (or similar subtree), not on top of `session_processing3/` or per-animal analysis folders.
- [ ] Tests use `PathResolver(output_root=tmp_path)`.
- [ ] `pytest --collect-only` passes.
- [ ] `ruff check` clean on every touched source file.

Before the phase-close PR:
- [ ] Full pytest pass; net-new test count grows by an amount proportional to the per-family port count.
- [ ] All Task 3 family verdicts: PASS or deferred-with-DECISIONS-entry.
- [ ] All Task 4 endpoint verdicts: PASS.
- [ ] DECISIONS + MIGRATION_LOG entries match the Phase 7-pre-secondary-spout format.
- [ ] State-doc refresh complete.

---

## Forward-pointers (deliberately tracked, not in this phase)

1. **Phase 9 stats** — stat-inferential plots from playground cells 56-65 deferred per scope note above.
2. **Phase 7-pre-secondary-spout-compare-DLC** — Phase 4 DLC b-half processing + bare-vs-b DLC comparison. Blocked on DLC inference of b-half cam dirs.
3. **Cohort-wide spout-behavior re-emit** — surfaced in Task 0.5 if gaps exist; resolved as a sibling chore-PR or by narrowing Cohort A's scope.
4. **8a.7 + 8a.7.5 broader coverage** — implicitly deferred per Priya 2026-05-12 narrowing.
5. **PS51/2025-04-29 + PS54/2025-05-08 weak candidates** — carried forward from Phase 7-pre-secondary-spout. Out of scope.
6. **bnpm dep + orphan cam{1,3,4} housekeeping** — carried forward from Phase 7-pre-multi-half. Orthogonal.

---

## DECISIONS entry sketch (for Task 5)

> **YYYY-MM-DD — Phase 8a.10 close — Spout-behavior visual gate + bare-vs-b comparison ([Outcome] per Task 1 audit).**
>
> **Phase metadata.** Branch `phase/8a.10-spout-visual-gate`, opened YYYY-MM-DD off `main` at `<sha>` (PR #N kickoff-doc merge). PR #M merged YYYY-MM-DD as merge-commit `<FILL>`, tagged `v8a.10-spout-visual-gate`. Kickoff `docs/prompts/phase-8a.10-kickoff.md`.
>
> **Context.** [Two sub-deliverables in one PR: legacy-parity gates (cohort-wide, all behavior-report plots) + bare-vs-b comparison (19 Pattern B sessions, 5 endpoints). Fold-in scope from Phase 7-pre-secondary-spout DECISIONS 2026-05-12.]
>
> ### Decision 1 — Module structure
> [Single `visual_gate.py` vs split `visual_gate.py` + `cohort_summary.py`. Cite Task 1 recommendation + rationale.]
>
> ### Decision 2 — Outcome A/B/C verdict + Cohort A scope
> [Final cohort size + plot-family count + any narrowing decisions.]
>
> ### Decision 3 — Faithful-port discipline + explicit deviations
> [List every deviation from legacy behavior. Each deviation justified with a reason.]
>
> ### Decision 4 — Stats-plot Phase 9 forward-pointer
> [List the specific cells/functions classified as Phase 9 scope.]
>
> ### Decision 5 — Bare-vs-b endpoint-5 new-visualization spec
> [Reward acquisition rate over time: visualization design + scientific motivation.]
>
> ### Decision 6 — Task 0.5 cohort gaps resolution (if any)
> [What gaps existed; how resolved (chore-PR vs narrow).]
>
> ### Decision 7 — Per-family verdict
> [Verdict table: family / PASS-after-C-rounds / deferrals.]
>
> ### Enforced at
> [Source / config / test / docs files list.]
>
> ### Findings carried forward
> [Forward-pointers per the section above.]

---

## MIGRATION_LOG entry sketch (for Task 5)

> ## Phase 8a.10 — Spout-behavior visual gate + bare-vs-b comparison
>
> **Date:** YYYY-MM-DD
> **PR:** #M
> **Tag on merge:** `v8a.10-spout-visual-gate`
> **Branch:** `phase/8a.10-spout-visual-gate`
>
> **Scope.** [2-3 sentence summary.]
>
> **What landed.** [Per-file changes; ~15-25 files.]
>
> **Task 3 verdict.** [Per-family PASS table.]
>
> **Task 4 verdict.** [Per-endpoint PASS for bare-vs-b.]
>
> **Intentional behavior differences vs legacy.** [List every deviation; cite DECISIONS Decision 3.]
>
> **Exit criteria met.** [Checklist.]
>
> **Forward-pointers queued.** [Match DECISIONS Findings-carried-forward.]
>
> **Tag:** `v8a.10-spout-visual-gate` on the merge commit.
