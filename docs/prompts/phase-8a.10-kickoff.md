# Phase 8a.10 Kickoff — Spout-behavior visual gate + bare-vs-b comparison

**Branch:** `phase/8a.10-spout-visual-gate` off latest `origin/main`.
**Tag on phase-close merge:** `v8a.10-spout-visual-gate`.
**Prerequisites:** MICROSCOPE mount; conda env `stroke_orofacial` active; `main` HEAD post chore PR #109 (Cohort A inputs durably on disk for 341 sessions; uniformly stamped).
**Estimated scope:** mid-to-large. Comparable to Phase 7a.5-mismatch (substantial per-family port) + bare-vs-b additive scope. Likely 15-25 source/test files + 3 docs files + this kickoff.

---

## Context

Phase 8a.10 was originally scoped (per `docs/COWORK_SESSION_STATE.md` Next-phase candidates list) as a "spout-behavior visual gate" — render comparison grids for the canonical `batch_process_behavior_report_20260116PS.ipynb` against the new pipeline's outputs, eyeball-verdict by Priya. Scope was **expanded 2026-05-12** per [Phase 7-pre-secondary-spout DECISIONS](../DECISIONS.md) fold-in decision: this phase also covers bare-vs-b spout-behavior outcome comparison for the 19 Pattern B sessions across PS51/PS54/PS55. The b-half data is now durably on disk in `pipeline_outputs/` (via the Phase 7-pre-secondary-spout chore re-emit PR).

**Audit-first** per the multi-half / secondary-spout / 7a.5-mismatch / 7a.6 pattern: Task 1 walks the legacy code and produces a per-plot-family port plan that Priya signs off on before any implementation commits land.

Task 0.5 ran 2026-05-13 (per status banner below); chore PR #109 landed the recovery. Task 0.75 + Task 1 onward are the active work scope when this phase resumes.

The phase has **two sub-deliverables in one PR**:

- **Sub-deliverable A — Legacy-parity gates (cohort-wide, full plot coverage).** Render every non-stat visualization the canonical behavior-report code produces; parity-check each rendering against the legacy PNGs.
- **Sub-deliverable B — Bare-vs-b comparison.** Five endpoints; 19 Pattern B sessions; reuses A's rendering code for endpoints 1-4; endpoint 5 is new.

The two sub-deliverables share rendering code (sub-deliverable B reuses A's renderers) but have different cohort scopes and verdict mechanisms.

---

## Cohort scope

### Cohort A — Legacy-parity gates

The 341 (animal, date) pairs in Cohort A, defined by walking legacy `basic_behavior_analysis3/<mouse>/report.json`'s `latency_bySession` keys (per Task 0.5 extension audit). Spans 8 animals: PS46/47/48/49/50/51/54/55. Date ranges per animal:

- PS46: 30 sessions (20250225 → 20250327; 2025-02-26 narrowed per DECISIONS — dual-h5)
- PS47: 30 sessions (20250225 → 20250327; 2025-03-02 phase-2-only, no cam data)
- PS48: 31 sessions (20250225 → 20250327; includes Pattern A multi-half 2025-03-14)
- PS49: 34 sessions (20250225 → 20250331; 2025-03-03 phase-2-only, no cam data)
- PS50: 38 sessions (20250227 → 20250406; 2025-03-18 narrowed per DECISIONS — nested cam subdir)
- PS51: 55 sessions (20250416 → 20250626)
- PS54: 64 sessions (20250416 → 20250626)
- PS55: 59 sessions (20250416 → 20250626; 2025-06-06 phase-3-skip, dual-h5)

Sub-deliverable A's parity gate runs against this cohort. All inputs (Phase 2 outputs + Phase 3 alignment templates where available) durably present at `pipeline_outputs/spout_behavior/` and `pipeline_outputs/dlc_analysis/alignment_templates/` after chore PR #109.

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

**SCOPE LOCKED 2026-05-13 (Q1 Option 2):** 11 canonical families from `behavior_report_PS.py`. The 7 trimmed families (`anyLick_accuracy_{L,R}_byCategory`, `firstLick_accuracy_{L,R}_byCategory`, `latency_hist`, `lickRate_byTrial`, `numLicks_byTrial`) deferred to Phase 9+ forward-pointer. Per Priya: the endpoint families in scope are:

- First lick accuracy (`accuracy_firstCorrectLick`, `accuracy_firstCorrectLickAll`)
- Correct + incorrect licks per side (`numLicks_bySession_{correct,all,correct_and_incorrect}`)
- Lick raster (`lick_raster`)
- First-lick latency (`latency_bySession`)
- Lick rate (`lickRate_bySession`)
- Lickiness (`lickiness_bySession`)
- Switchiness (`switchiness_bySession`)
- Criteria performance (`criteria_performance`)
- ~~Recovery trajectories~~ — **DEFERRED to Phase 9+** per Priya 2026-05-13 decision (alongside the 7 trimmed families above). Forward-pointer captured in the final CG-6-wrap DECISIONS entry.

### Verdict mechanism

Per-mouse-aggregate parity verdict. Legacy PNGs at `basic_behavior_analysis3/<mouse>/<plot_family>.svg` are PER-MOUSE aggregates (one PNG per plot family per mouse, aggregating across all sessions in that mouse's cohort), NOT per-session. Per-session info lives in `report.json` (consumed by aggregate plots but never rendered individually). Total parity-gate target: 8 animals × ~10-15 plot families = ~80-120 PNGs to eyeball-PASS.

For each plot family × each mouse, the parity gate renders:

- Legacy SVG (left) — sourced from Task 0.75 baseline capture.
- New pipeline rendering (right) — sourced from `visual_gate.py`.
- (Optional) diff or annotation panel.

Priya signs off per (mouse, plot_family) pair. Multiple iterative C-rounds expected (mirrors 7a.5-mismatch / 7a.6 patterns).

Per-session rendering (if any plot family produces per-session output) is a separate sub-scope locked at Task 1 audit.

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

**STATUS: DONE 2026-05-13.** Audit at `.scratch_phase_8a_10/cohort_a_audit.md` + `cohort_a_audit_part_b.md` enumerated Cohort A at 343 sessions across 8 animals. Recovery landed via chore PR #109 — 68 sessions re-emitted (Bucket-1 + 5 Pattern B representational-mismatch + 1 PS48 Pattern A + 1 PS55/2025-06-06 dual-h5 special-case), 2 sessions narrowed (PS46/2-26 + PS50/3-18), 2 sessions phase-2-only (PS47/3-2 + PS49/3-3), 1 session phase-3-skip (PS55/6-06). Final Cohort A coverage: 341 sessions. All licks NPZs uniformly stamped (Path-2 audit confirmed K=0 pre-Phase-6.8 unstamped emissions). Task can be skipped on future warm-starts; preserved here for historical reference.

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

1. Canonical legacy-PNG directory CONFIRMED (Task 0.5 extension audit): `analysis/basic_behavior_analysis3/<mouse>/<plot_family>.svg`. Per-mouse aggregate plots; ~10-15 plot families × 8 mice = ~80-120 SVGs total. mtimes 2025-06-13 (PS46-50) + 2025-06-26 (PS51/54/55). These are real legacy outputs from production runs; sub-deliverable A's parity gate uses them as the canonical baseline.

   Task 0.75 captures these SVGs to `tests/scripts/_baselines/phase_8a_10/legacy_svgs/<mouse>/<plot_family>.svg` via a small chore PR (mirroring PR #104 baseline-capture pattern from Phase 7-pre-secondary-spout). NO re-execution of the legacy notebook needed — the SVGs already exist on MICROSCOPE from Priya's prior production runs.

2. Copy/snapshot to `tests/scripts/_baselines/phase_8a_10/legacy_svgs/` for durable reference. Capture the snapshot's timestamp + a SHA256 manifest.

3. STOP-and-report: list the captured SVG count + per-mouse breakdown. Verify reasonable (one SVG per (mouse, plot-family) at minimum).

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
7. **`wavesurfer_file_overrides:` block in `session_overrides.yaml`.** Generalizes the PR #109 PS55/2025-06-06 dual-h5 one-off hack. Maps `(animal, date)` → specific filename when `find_wavesurfer_file` can't disambiguate multiple `.h5`s. Lands when a 2nd dual-h5 case surfaces.
8. **`wavesurfer_subdir_overrides:` block in `session_overrides.yaml`.** Cleans up the 5 PR #109 representational-mismatch entries in `secondary_spout_sessions:` (PS51/2025-04-24 + 4-25, PS54/2025-04-24 + 4-25, PS55/2025-04-25) which are bare-only sessions borrowing the Pattern B override mechanism. Single-half manifest with WS subdir override; no Pattern B compare-intent claimed. Lands when Pattern B test semantics start to bite or a 6th similar case surfaces.
9. **Parallel dual-h5 hack for Phase 3 alignment recompute.** PR #109's PS55/2025-06-06 special-case only handled Phase 2 (`process_session` direct). Phase 3 alignment template for that session is currently a documented-skip. Lands when (7) or (8) generalizes the override mechanism.

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

---

## Addendum #1 — Sub-deliverable B scope replacement (CG-B3 cohort-only)

**Date:** 2026-05-13.
**Supersedes:** Original Task 4 sub-deliverable B spec (5 endpoints; per-session + cohort layers). CG-B1 (registry + loader) and CG-B2 (per-session renderers, PS55 pilot) stay in git history but are superseded by this addendum.

### Rationale

Per Priya 2026-05-13, per-session paired panels expand rendering surface area without supporting the scientific message. Cohort B = 14 sessions across 3 animals; per-session views obscure the cohort-level signal. The story lives at the cohort level: closer spouts (b) → post-stroke mice contact more frequently than with standard distance (bare), consistent with **excursion limitation relieved by proximity** (cue response + motor command preserved; reach amplitude limits spout contact at standard distance).

All three retained endpoints are expected to go b > bare:
- Reach success (Row 1, `accuracy_firstCorrectLickAll`) — they get to the spout at all.
- Contact count once reached (Row 2, `numLicks_bySession`) — once there, they contact more.
- Visual density (Row 3, `lick_raster`) — qualitative confirmation.

### Scope (LOCKED)

- **3 endpoints retained:** `accuracy_firstCorrectLickAll`, `numLicks_bySession` (correct + incorrect per side), `lick_raster`.
- **2 endpoints dropped:** first-lick-latency, reward-acquisition-rate-over-time. Renderers + tests deleted from `bare_vs_b.py` / `test_bare_vs_b.py`.
- **Per-session paired panels eliminated.** `PER_SESSION_RENDERERS`, `render_per_session_bare_vs_b_pair`, and any per-session plumbing deleted.
- **Cohort-only output:** one figure per animal, 3 rows × 2 cols layout, written to `pipeline_outputs/spout_behavior/spout_behavior_figures/bare_vs_b/cohort/<animal>_summary.{svg,png}`.
- **Cohort B definition UNCHANGED:** 14 sessions, post-stroke filter `rel_day >= 2` (literal reading of "AFTER d1"): PS51 ×1 (2025-05-05), PS54 ×10 (2025-05-30, 6/16, 6/18, 6/19, 6/20, 6/21, 6/23, 6/24, 6/25, 6/26), PS55 ×3 (2025-05-30, 6/1, 6/5).

### Renderer spec — `render_animal_summary_bare_vs_b(animal, sessions, resolver, ...)`

**Figure:** 3 rows × 2 cols. Default figsize ~10in × 12in (tunable via `defaults.yaml`).

**Row 1 — `accuracy_firstCorrectLickAll` (one panel per side: L, R):**
- X axis: `{bare, b}` (categorical).
- Y axis: `[0, 1]`, first-correct-lick fraction.
- One dot per `(session, condition)`. Same-date bare/b pairs connected by a thin gray line (`linewidth=0.5`, `alpha=0.4`).
- Mean across sessions per condition overlaid as a horizontal bar in red.
- **Denominator semantics PIN:** use `compute_firstLickCorrect_bySession(first_corr, treat_none_as_zero=True)` per session. Denominator is ALL trials of that cue type; no-lick trials counted as 0. Worked example: 2 first-correct-licks across 48 cue trials → 0.042 (NOT 2/2 = 1.0). This matches the legacy `accuracy_firstCorrectLickAll` family. **DO NOT** use the `treat_none_as_zero=False` (`excludeNone`) variant — that's the non-"All" sibling and would silently change the denominator semantics.

**Row 2 — `numLicks_bySession` (one panel per side: L, R):**
- X axis: `{bare, b}` (categorical).
- Y axis: mean licks per trial (numeric).
- Layering: replicate the visual gate's existing `numLicks_bySession_correct_and_incorrect` stacking convention (correct + incorrect stacked or paired — match exactly to keep cross-figure visual consistency). Check `visual_gate.py` for the canonical pattern before implementing.
- Per-session dot + same-date connector + mean bar (same pattern as Row 1).

**Row 3 — `lick_raster` (pooled across sessions, one panel per side: L, R):**
- Within each panel: bare-trials on top half, b-trials on bottom half, separated by a horizontal divider line. Y-axis ticks at the divider labeled "bare" / "b".
- X axis: time around tone/reward; same x-range and tick convention as the visual gate single-session raster (`raster_xticks`, `raster_xlabel_fontsize` from `defaults.yaml`).
- Dot conventions inherited from visual gate raster: `raster_dot_alpha=0.6`, `raster_dot_correct_zorder=2`, `raster_dot_incorrect_zorder=3`, `raster_reward_marker_linewidth=0.5` from `visual_gate:` config block.
- Trial ordering within each half: chronological-within-session, sessions in date order. Concatenate trials end-to-end; do not interleave sessions.

### Naming alignment

In `bare_vs_b.py`:
- Rename `render_bare_vs_b_first_lick_accuracy` → `render_bare_vs_b_accuracy_firstCorrectLickAll` (matches `accuracy_firstCorrectLickAll` legacy family).
- Verify + align other retained renderer names against their visual gate siblings (the cohort renderer wraps them).
- Delete `render_bare_vs_b_first_lick_latency`.
- Delete `render_bare_vs_b_reward_acquisition_over_time`.

Update `tests/test_bare_vs_b.py` to reflect the renames + deletions + new cohort renderer pin set.

### Notebook orchestration (`notebooks/15_spout_behavior_visual_gate.ipynb`)

USER INPUTS additions:
```python
ANIMALS_BARE_VS_B: list[str] = ["PS55"]      # pilot first, then expand to ["PS51", "PS54", "PS55"]
CLEAN_ORPHANED_PER_SESSION_OUTPUTS: bool = True  # delete CG-B2 per-session pilot dirs before new render
```

USER INPUTS removals:
- Drop the per-session render loop (CG-B2 era) entirely.

Render call:
```python
from stroke_orofacial.spout_behavior.bare_vs_b import render_animal_summary_bare_vs_b
for animal in ANIMALS_BARE_VS_B:
    render_animal_summary_bare_vs_b(animal, resolver=resolver, overwrite=OVERWRITE)
```

### Orphan cleanup (CG-B3 pre-render)

Before the new render runs, delete the per-session pilot outputs at `pipeline_outputs/spout_behavior/spout_behavior_figures/bare_vs_b/<animal>/` for each animal in `ANIMALS_BARE_VS_B`. CG-B2 emitted 30 files for PS55 (6 sessions × 5 endpoints × 2 formats minus 0); these become orphaned under the cohort-only design.

Implementation (in notebook, gated by `CLEAN_ORPHANED_PER_SESSION_OUTPUTS`):
```python
import shutil
for animal in ANIMALS_BARE_VS_B:
    orphan_dir = resolver.bare_vs_b_dir(animal=animal)   # the per-animal subdir, NOT cohort/
    if CLEAN_ORPHANED_PER_SESSION_OUTPUTS and orphan_dir.exists():
        print(f"Removing orphaned per-session outputs: {orphan_dir}")
        shutil.rmtree(orphan_dir, ignore_errors=True)
```

The `.../cohort/` subdir survives — that's where the new outputs land.

Verify `resolver.bare_vs_b_dir(animal=None)` already resolves to `.../bare_vs_b/cohort/` per the existing CG-B1 path resolver scaffold; if it returns a different path or doesn't accept `None`, extend `paths.py` (smallest possible change).

### Pilot-first execution

1. Implement renames + cohort renderer + tests on branch.
2. Run notebook with `ANIMALS_BARE_VS_B=["PS55"]`. STOP-and-report: post the 2 PS55 files (`PS55_summary.svg` + `.png`) for Priya eyeball-verdict.
3. After PS55-PASS: expand to `["PS51", "PS54", "PS55"]`, re-render. STOP-and-report: post all 6 files.
4. Priya eyeball-PASS each animal → CG-B3 complete; proceed to phase-close (DECISIONS + MIGRATION_LOG + state-doc + PR).

### File-touch allowlist (CG-B3)

```
src/stroke_orofacial/spout_behavior/bare_vs_b.py      (renames + new cohort renderer + endpoint deletions)
src/stroke_orofacial/paths.py                          (only if bare_vs_b_dir(animal=None) doesn't already resolve to cohort/)
configs/defaults.yaml                                  (optional: bare_vs_b cohort knobs if introduced)
tests/test_bare_vs_b.py                                (sync with bare_vs_b.py changes)
notebooks/15_spout_behavior_visual_gate.ipynb          (drop per-session loop + cleanup flag + new renderer call)
```

NO touches outside this list. Specifically:
- `src/stroke_orofacial/spout_behavior/visual_gate.py` — reused but unchanged.
- `src/stroke_orofacial/spout_behavior/cohort_summary.py` — Cohort A only.

### DECISIONS addendum (folds into Task 5 entry)

Add **Decision 8 — Sub-deliverable B scope replacement: cohort-only, 3 endpoints, Option-1 story-strip layout.** Rationale per the "Rationale" section above. Note the two endpoint deletions (latency, reward-acquisition-rate-over-time) as scoped-out — not deferred — because they don't support the excursion-limit scientific message and don't have a downstream consumer.

### MIGRATION_LOG addendum

In "What landed" section, note: "Sub-deliverable B reshaped mid-phase from 5-endpoint per-session-and-cohort to 3-endpoint cohort-only (per Addendum #1)."

### Scientific-message check (do not skip)

Before declaring PS55-pilot PASS, verify visually that the three rows tell a coherent story for at least one of L/R cue sides:
- Row 1 b > bare (accuracy improved with closer spouts).
- Row 2 b > bare (more correct licks per trial with closer spouts).
- Row 3 visibly denser bottom half (b) than top half (bare).

If any row contradicts, STOP-and-report before expanding to PS51/PS54. Contradictions may reflect (a) the tone/reward label swap (Phase 8a.10.1 forward-pointer) flipping L/R interpretation, (b) a renderer bug, or (c) a real null result worth discussing before iterating. Don't paper over with a re-render.

### ALL OTHER LOCKS UNCHANGED

Sub-deliverable A scope (11 plot families, cohort-wide, ~80-120 PNGs to PASS), Cohort A definition (341 sessions), Task 3 verdict mechanism, Tasks 2-3 file-touch allowlist, all forward-pointers — all preserved.

---

## Addendum #2 — CG-B3 Round 2 polish (pre-PS55-PASS-verdict)

**Date:** 2026-05-13.
**Trigger:** Priya review of CG-B3 PS55 pilot (commit `055ef53`). Scientific message lands cleanly (L-side: 0.098 → 0.611 accuracy; 0.60 → 5.22 mean correct licks per trial). Four polish tweaks before PS55-PASS + expansion.

### Tweak 1 — Relabel half identifiers as "Standard" / "Close"; x-axis title = "Spout Distance"

Label-only change. The underlying `half_suffix` identifiers ("bare" / "b") stay in code, NPZ keys, paths, and registry semantics — only visible rendered labels change.

Recommended:
```python
BARE_VS_B_DISPLAY_LABELS = {"bare": "Standard", "b": "Close"}
BARE_VS_B_XAXIS_TITLE = "Spout Distance"
```

Apply:
- Row 1 + Row 2 x-tick labels → `["Standard", "Close"]` (same order as the underlying half iteration).
- Row 3 y-axis half labels (the divider-line annotations) → "Standard" on top, "Close" on bottom.
- X-axis title `"Spout Distance"` on the bottom row (or all 3 rows — bottom-only is cleaner if columns visually align).

Test pin (`test_bare_vs_b.py`): SVG contains "Standard", "Close", "Spout Distance"; does NOT contain visible "bare" / "b" tick-label text (case-sensitive; underlying SVG metadata / code attributes still containing "bare"/"b" are fine — only the rendered tick-label text needs to be Standard/Close).

### Tweak 2 — Mean line same color as dots; narrower

Per-condition mean lines, each colored to match the dots of that condition. Suggested `linewidth=0.75` (tune empirically if it looks too thin or too bold).

If the current implementation uses a single color for all dots: introduce a per-condition palette:
```python
BARE_VS_B_CONDITION_COLORS = {"bare": "...", "b": "..."}   # palette TBD; Priya's eyeball-verdict picks
```
Color both dots and the mean line per-condition. The same-date gray connector stays gray (spans both conditions).

Test pin: per-condition mean line `stroke=` attribute matches the `stroke=` (or `fill=`) of dots in the same x-position.

### Tweak 3 — Row 3 raster: dividing lines between sessions within each half

Within the Standard half and within the Close half, thin horizontal lines between consecutive sessions. Suggested: `linewidth=0.3`, `color="lightgray"`, `alpha=0.5`, `zorder=1`. The existing horizontal divider between Standard / Close stays as the thicker / darker boundary line.

Implementation note: extend `_plot_row_lick_raster` to track cumulative trial-count offsets as it concatenates trials chronologically; emit one `axhline` per inter-session boundary in each half.

Test pin: count of inter-session boundary lines in each Row 3 panel = `(n_standard_sessions - 1) + (n_close_sessions - 1)`. PS55: 3 + 3 → 2 + 2 = 4 lines per panel. PS54: 10 + 10 → 9 + 9 = 18 per panel. PS51: 1 + 1 → 0 + 0 = 0 lines.

### Tweak 4 — Y-axis shared within row across L/R panels

Empirically per-row, then sync L and R.

- Row 1: `y_min = 0`, `y_max = max(row1_L_data, row1_R_data) + small_padding`, clipped to `[0, 1]` (accuracy bounds). Apply `set_ylim(y_min, y_max)` to both L and R panels.
- Row 2: `y_min = 0`, `y_max = max(row2_L_data, row2_R_data) + small_padding`. Apply to both panels.
- Row 3 raster: y is trial-index. If pooled trial counts are equal across L and R sides per panel (PS55 report showed L=139+144, R=139+144 → equal), the panels auto-share. If unequal: pad the shorter side with whitespace so the bare/close divider lines up across L and R panels. Leave per-panel only if equality is structurally guaranteed; otherwise sync.

Test pin: Row 1 and Row 2 L+R panels have matching `get_ylim()` per row.

### Execute order

1. Implement 4 tweaks + test pins on the existing CG-B3 branch (no new branch).
2. Re-render PS55. STOP-and-report: post `PS55_summary.{svg,png}` for Priya eyeball-verdict.
3. After PS55 polish-PASS: expand `ANIMALS_BARE_VS_B = ["PS51", "PS54", "PS55"]`, re-render. STOP-and-report all 6 files.
4. Final cohort PASS → phase-close (DECISIONS Decision 8 + MIGRATION_LOG addendum + state-doc refresh + PR).

### File-touch (CG-B3 R2)

Same allowlist as Addendum #1. No new files. Expected churn:
- `src/stroke_orofacial/spout_behavior/bare_vs_b.py` — display-label mapping, palette, narrower mean line, raster session-boundary lines, shared y-lims.
- `tests/test_bare_vs_b.py` — 4 new test pins (one per tweak).
- `configs/defaults.yaml` — optional: palette + linewidth knobs under `bare_vs_b:` block if introduced.

### ALL OTHER LOCKS UNCHANGED

Addendum #1 scope (3 endpoints, cohort-only, 3×2 layout), denominator semantics pin, orphan cleanup, scientific-message check, file-touch allowlist scope, forward-pointers — all preserved.

---

## Addendum #3 — CG-B3 Round 3 polish (pre-PS55-PASS-verdict)

**Date:** 2026-05-13.
**Trigger:** Priya review of CG-B3 Round 2 PS55 output (commit `5fc9a1b`). Six tweaks across structural rename, color scheme, layout split, label conventions, and typography.

### Tweak 1 — Full rename: `bare_vs_b` → `spout_close_vs_std` (Q1 Option B)

User-facing nomenclature is "spout close vs standard"; internal code follows suit. Underlying `half_suffix="bare"`/`"b"` identifiers + `secondary_spout_sessions:` registry keys + NPZ keys stay legacy-locked (cross-codebase reach).

**File renames** (use `git mv` to preserve history):
- `src/stroke_orofacial/spout_behavior/bare_vs_b.py` → `spout_close_vs_std.py`
- `tests/test_bare_vs_b.py` → `test_spout_close_vs_std.py`

**Symbol renames:**
- `render_animal_summary_bare_vs_b` → `render_animal_summary_spout_close_vs_std`
- `iter_cohort_b_session_keys`, `iter_cohort_b_sessions`, `list_cohort_b_animals`, `SessionPairData`, `COHORT_B_REL_DAY_MIN` — keep as-is (Cohort B is the registry-bound cohort identifier; doesn't need to leak the "bare_vs_b" phrase since it doesn't).
- `BARE_VS_B_DISPLAY_LABELS` → `SPOUT_DISTANCE_DISPLAY_LABELS` (or similar).
- `BARE_VS_B_XAXIS_TITLE` → `SPOUT_DISTANCE_XAXIS_TITLE`.
- `BARE_VS_B_CONDITION_COLORS` — **delete** (per Tweak 2 below; per-condition palette goes away).

**Path resolver:** `PathResolver.bare_vs_b_dir()` → `PathResolver.spout_close_vs_std_dir()`. Semantics unchanged: `animal=None` returns `.../spout_close_vs_std/cohort/`; `animal="PS55"` returns `.../spout_close_vs_std/PS55/` (the orphan-cleanup target, though under the cohort-only design no per-animal subdirs are emitted).

**Output dir:** `pipeline_outputs/spout_behavior/spout_behavior_figures/bare_vs_b/` → `.../spout_close_vs_std/`. The existing `bare_vs_b/cohort/` directory (containing CG-B3 R2's PS55 outputs) becomes orphaned — delete it as part of Round 3 cleanup, alongside the existing CG-B2 per-session orphan deletion logic.

**Notebook + config + DECISIONS-sketch references** — sweep for "bare_vs_b" string occurrences in `notebooks/15_spout_behavior_visual_gate.ipynb`, `configs/defaults.yaml`, the in-flight DECISIONS Decision 8 sketch, and update to `spout_close_vs_std`.

**Half_suffix identifiers stay unchanged** — `"bare"` and `"b"` continue to identify the two halves in NPZ paths, registry keys, and the `load_session_plot_data(half_suffix=...)` signature. Renaming those is a Phase 8a.10.2+ concern (cross-codebase).

### Tweak 2 — Revert per-condition palette → per-mouse-side palette + Standard/Close dot-fill convention (Q2)

**Dots + mean line color** = mouse-side cue color (matches the visual gate convention):
- L-cue panel: `dodgerblue` for all dots + mean line.
- R-cue panel: `mediumvioletred` for all dots + mean line.

**Standard vs Close distinguished by dot fill style** (color encodes mouse-side; fill encodes condition):
- Standard: filled dots (`markerfacecolor=mouse_side_color`).
- Close: open dots (`markerfacecolor="none"`, `markeredgecolor=mouse_side_color`).

Mean line color matches mouse-side (same color for both Standard and Close mean within a panel). Mean line `linewidth=0.75` (carried from Round 2). Consider linestyle differentiation for Standard vs Close mean lines if visual ambiguity persists at review (e.g., solid for Standard, dashed for Close) — leave as solid-only initially, defer until PS55 review.

**Connector line stays gray** (`color="gray"` or current shade, `linewidth=0.5`, `alpha=0.4`). Pairs same-date dots across conditions; neutrality intentional.

Constants:
```python
SPOUT_DISTANCE_DOT_STYLE = {
    "bare": {"markerfacecolor": "<mouse_side_color>", "markeredgecolor": "<mouse_side_color>"},     # filled
    "b":    {"markerfacecolor": "none",                "markeredgecolor": "<mouse_side_color>"},     # open
}
```
(or implement as keyword construction inside the plotting helper; `<mouse_side_color>` resolves per panel.)

Pull `dodgerblue` / `mediumvioletred` from the existing `visual_gate.SIDE_COLORS` config if possible (avoid hardcoding); if not present, add to `configs/defaults.yaml`.

### Tweak 3 — Split mean licks into correct + incorrect → 4-row layout (Q3)

New per-animal figure layout: **4 rows × 2 cols = 8 panels**.

| Row | Endpoint | Y-axis sharing |
|---|---|---|
| 1 | `accuracy_firstCorrectLickAll` | L↔R shared, clipped `[0, 1]` |
| 2 | mean **correct** licks per trial | L↔R shared (independent of Row 3) |
| 3 | mean **incorrect** licks per trial | L↔R shared (independent of Row 2) |
| 4 | lick raster (pooled, Standard/Close stacked) | L↔R synced via trial-count padding |

Row 2 and Row 3 each compute their own L+R max → padded → applied to both panels in that row. Do NOT share y-axis range between Row 2 and Row 3 (incorrect-lick magnitudes are typically much smaller; sharing would crush Row 3 detail).

The previous helper `_half_mean_licks_per_trial_per_side` likely returns correct-side licks only. Split or extend to also return incorrect-side licks. Both rows use the same `_plot_row_per_session_dots_and_means` plotting helper with different data dicts.

Default figsize bumps to accommodate the new row: ~10in × 14-16in (tune at PS55 review).

### Tweak 4 — Raster session-block labels: post-stroke day, outside right spine, rotated 90° (Q4)

Each session-block in the Row 4 raster gets one "d+N" label, where:
- N = `animal_info.day_relative_to_stroke(date)` (existing helper in `animals.py`).
- Vertical position: centered on the session's trial-row range within the panel.
- Horizontal position: outside the right axis spine. Use `ax.text(...)` with `transform=ax.get_yaxis_transform()`, `x` slightly > 1.0 (e.g., 1.02).
- Rotation: 90° (or -90°, whichever orients the "d" left and digits right when reading top-to-bottom).
- Font size: small but readable (suggested 7-8; tune at review).

For PS55 (3 Standard + 3 Close sessions): 6 day labels per panel × 2 panels = 12 labels in Row 4.

The horizontal divider line between Standard and Close halves is unchanged.

### Tweak 5 — Raster session-divider styling: darker (Q5)

Update `RASTER_INTRA_HALF_BOUNDARY_KWARGS`:
```python
RASTER_INTRA_HALF_BOUNDARY_KWARGS = {
    "color": "gray",          # was "lightgray"
    "linewidth": 0.5,         # was 0.3
    "alpha": 0.8,             # was 0.5
    "zorder": 1,
}
```

### Tweak 6 — Typography bumps (Q6)

Add knobs to `defaults.yaml` under whatever config block currently holds the cohort renderer settings (likely `spout_close_vs_std:` post-rename, or fold into `visual_gate:`). Suggested values:
- Panel title fontsize: 11 → **14**
- Raster xtick fontsize: inherits `visual_gate.xtick_fontsize=5` → override to **9** for the cohort raster
- Raster "Time (s)" axis label fontsize: inherits `visual_gate.raster_xlabel_fontsize=8` → override to **11** for the cohort raster

The visual-gate single-session rasters keep their existing smaller font sizes (this is a cohort-renderer-specific bump; do not change `visual_gate:` knobs).

### Round 3 orphan cleanup

Add to the notebook's `CLEAN_ORPHANED_PER_SESSION_OUTPUTS` block: also delete the legacy `bare_vs_b/` cohort directory (`pipeline_outputs/spout_behavior/spout_behavior_figures/bare_vs_b/`) since the rename moves outputs to `spout_close_vs_std/`. Single `shutil.rmtree(..., ignore_errors=True)` gated by the same flag.

The new `spout_close_vs_std/cohort/` directory is freshly created on the first re-render.

### Test pin updates

Beyond the renames (test file move + symbol renames), add these pins:

- `test_dot_fill_filled_standard_open_close` — Standard dots have `markerfacecolor` matching mouse-side; Close dots have `markerfacecolor="none"`.
- `test_dot_edgecolor_mouse_side` — both Standard and Close dots in the L panel share `markeredgecolor="dodgerblue"`; both in R panel share `mediumvioletred`.
- `test_mean_line_color_matches_mouse_side` — mean line in L panel = `dodgerblue`; mean line in R panel = `mediumvioletred`.
- `test_connector_stays_gray` — connector `color="gray"` (or whatever shade currently used), regardless of panel.
- `test_layout_is_4_rows_2_cols` — 8 axes_groups in SVG (was 6 in Round 2).
- `test_row_3_incorrect_licks_separate_ylim_from_row_2` — Row 2 `get_ylim()` ≠ Row 3 `get_ylim()` (assuming nonzero magnitudes; if all-zero in pilot data, skip or use synthetic fixture).
- `test_raster_day_labels_outside_right_spine` — count `ax.texts` entries with `x > 1.0` in axes coords = `n_sessions_total` per panel (PS55: 6 per panel).
- `test_raster_divider_kwargs` — color="gray", linewidth=0.5, alpha=0.8 on the inter-session axhlines.
- `test_title_fontsize_14` — panel title rendered at fontsize 14 (or whichever knob locked).

Delete the Round 2 `test_tweak_2_per_condition_palette` pin if it exists (per-condition palette is gone).

### File-touch (CG-B3 R3)

```
src/stroke_orofacial/spout_behavior/bare_vs_b.py → spout_close_vs_std.py  (git mv + edits)
src/stroke_orofacial/paths.py                                              (rename resolver fn)
configs/defaults.yaml                                                       (rename config block + new typography knobs)
tests/test_bare_vs_b.py → test_spout_close_vs_std.py                       (git mv + edits)
tests/test_paths.py                                                         (resolver fn rename sync)
notebooks/15_spout_behavior_visual_gate.ipynb                               (rename references + Row 4 expectations + cleanup of legacy bare_vs_b dir)
```

NO new files. Module split if rename grows the file beyond comfortable limits is left to CC's judgment (likely not needed; file is already focused).

### Execute order

1. Implement Tweak 1 rename first (git mv + sweep for "bare_vs_b" references). Commit. Run `pytest --collect-only` to confirm no import breaks.
2. Implement Tweaks 2-6 in sequence (or batched as preferred). One commit per tweak or per logical bundle.
3. Re-render PS55 → STOP-and-report `spout_close_vs_std/cohort/PS55_summary.{svg,png}`.
4. After PS55-PASS: expand to `["PS51", "PS54", "PS55"]`, re-render, STOP-and-report.
5. Phase-close.

### ALL OTHER LOCKS UNCHANGED

Addendum #1 scope (3 endpoints, but 4 rows now per Tweak 3 split — accuracy + correct + incorrect + raster), cohort-only output, denominator semantics pin, orphan cleanup (extended in Round 3), scientific-message check, file-touch allowlist (extended with `test_paths.py` for resolver-fn rename sync), forward-pointers — all preserved.

---

## Addendum #4 — CG-B3 Round 4 typography + label-rotation polish

**Date:** 2026-05-13.
**Trigger:** Priya review of CG-B3 Round 3 PS55 output. Three label / typography refinements.

### Tweak 1 — Raster xtick + "Time (s)" label: bigger, and "Time (s)" closer to plots

Current values (Round 3):
- Raster xtick fontsize: 9
- Raster "Time (s)" xlabel fontsize: 11
- xlabel `labelpad` defaults to matplotlib's ~4 (visual effect = too much whitespace between raster panels and "Time (s)" label).

Bump:
- Raster xtick fontsize: 9 → **11** (suggested; tune at review)
- Raster "Time (s)" xlabel fontsize: 11 → **13** (suggested)
- xlabel `labelpad` → **2** (or 1 — bring "Time (s)" close to the tick labels). Apply via `ax.set_xlabel("Time (s)", fontsize=..., labelpad=2)` on the Row 4 panels.

Config knobs (`defaults.yaml`):
```yaml
spout_close_vs_std:
  raster_xtick_fontsize: 11
  raster_xlabel_fontsize: 13
  raster_xlabel_labelpad: 2
```
(Names align with existing `visual_gate.raster_xlabel_fontsize` / `xtick_fontsize` naming convention but live under the cohort renderer's config block, not `visual_gate:`.)

### Tweak 2 — Raster day labels: rotate 180° (bottom of letters adjacent to plot)

Current Round 3 implementation: `rotation=90` (counterclockwise). With the labels positioned outside the right spine, this puts the **top** of each character closest to the plotting area (the "2" in "d+32" reads toward the plot; the "d" reads away).

Fix: `rotation=270` (or equivalently `rotation=-90`). Clockwise 90° puts the **bottom** of each character adjacent to the plotting area — the "d" in "d+32" reads toward the plot, the "2" reads away.

Update wherever the day-label `ax.text(...)` call lives in `spout_close_vs_std.py`:
```python
ax.text(
    1.02, y_session_center, f"d{rel_day:+d}",
    transform=ax.get_yaxis_transform(),
    rotation=270,          # was 90; flip 180° so character bottoms are plot-adjacent
    rotation_mode="anchor",
    ha="left",             # or "right" — pick whichever positions the text correctly post-rotation
    va="center",
    fontsize=...,
)
```
Verify `ha`/`va` post-rotation visually at PS55 review — anchor semantics flip under rotation; the label needs to remain centered on the session block and offset cleanly outside the spine.

Test pin update: change `rotation=90` assertion (if present) to `rotation=270`.

### Tweak 3 — Licking-plot (Rows 1-3) x-axis label sizes: bigger

Current: panel x-tick labels ("Standard" / "Close") + x-axis title ("Spout Distance") on Row 3 (bottom row of the licking block) inherit default matplotlib sizes (~10 / ~10).

Bump:
- "Standard" / "Close" tick label fontsize: → **12** (suggested)
- "Spout Distance" xlabel fontsize: → **13** (suggested; matches the Tweak 1 "Time (s)" size for visual consistency)

Config knobs (`defaults.yaml` under `spout_close_vs_std:`):
```yaml
spout_close_vs_std:
  licking_xtick_fontsize: 12         # "Standard" / "Close" tick labels in Rows 1-3
  spout_distance_xlabel_fontsize: 13 # "Spout Distance" axis title on Row 3
```

Apply via `ax.tick_params(axis='x', labelsize=...)` on Rows 1-3 panels, and `ax.set_xlabel("Spout Distance", fontsize=...)` on the bottom-of-licking-block panels (Row 3, both L and R).

Test pins: parse the rendered SVG for "Standard" / "Close" tick-label font-size ≥ 12 and "Spout Distance" font-size ≥ 13. (Exact matches are brittle across matplotlib backend versions; use ≥ assertions.)

### File-touch (CG-B3 R4)

Same allowlist as Addendum #3. Expected churn:
- `src/stroke_orofacial/spout_behavior/spout_close_vs_std.py` — 3 fontsize knobs threaded through; rotation flip.
- `configs/defaults.yaml` — 5 new knobs under `spout_close_vs_std:` block (3 raster + 2 licking).
- `tests/test_spout_close_vs_std.py` — update rotation pin + add fontsize pins.

### Execute order

1. Implement 3 tweaks (single commit acceptable since they're all typography/rotation).
2. Re-render PS55. STOP-and-report `spout_close_vs_std/cohort/PS55_summary.{svg,png}`.
3. After PS55-PASS: expand to PS51 + PS54, re-render, STOP-and-report all 6 files.
4. Phase-close.

### ALL OTHER LOCKS UNCHANGED

All prior Addendum locks (scope, layout, palette, dot-fill convention, denominator semantics, orphan cleanup, scientific-message check, file-touch allowlist, forward-pointers) preserved.

---

## Addendum #5 — CG-B3 Round 5 raster polish + expand to all 3 animals

**Date:** 2026-05-13.
**Trigger:** Priya review of CG-B3 Round 4 PS55 output. Three raster-specific polish tweaks; pilot-pause skipped this round (render all 3 animals together).

### Tweak 1 — Raster xticks every 1s

Currently raster xticks inherit `visual_gate.raster_xticks=[0, 5]` (endpoints only). Priya wants ticks at every integer second across the visible window.

Change to:
```python
raster_xticks: [0, 1, 2, 3, 4, 5]
```

Add as a cohort-renderer-specific knob under `spout_close_vs_std:` in `defaults.yaml`:
```yaml
spout_close_vs_std:
  raster_xticks: [0, 1, 2, 3, 4, 5]
```
(or whatever the underlying window range is — confirm from `behavior_report.window_around_rewards` config and place tick at every integer second within that range).

Apply via `ax.set_xticks([0, 1, 2, 3, 4, 5])` on Row 4 panels. The single-session visual gate raster keeps its sparser tick set (`visual_gate.raster_xticks=[0, 5]`); do not modify the visual_gate config.

Test pin: Row 4 panels have ≥ 6 xtick values.

### Tweak 2 — Day-label vertical centering fix

After Round 4's `rotation=270` flip, day labels render shifted down relative to their session block (top-of-letter no longer aligned to top-of-session). Likely cause: `rotation_mode="anchor"` + `va="center"` semantics interacting with the rotation such that the anchor point lands at the visual top of the rotated text, not the visual center.

Debug + fix paths:
- Option A: switch `rotation_mode="default"` (matplotlib's default rotation around the text bounding-box center). Test visually.
- Option B: keep `rotation_mode="anchor"` and adjust `va` post-rotation — try `va="baseline"` or `va="bottom"` with a small empirical y-offset.
- Option C: explicit offset — add half the text height (in axes coords) to the y position to compensate. Fragile across matplotlib versions; least preferred.

Recommended: try Option A first (simplest). If it doesn't center cleanly, try Option B. Confirm at PS55 review (the day labels should sit visually centered on each session's row-range).

Test pin: leave the existing rotation pin as-is; centering is a visual-verdict not test-pin concern.

### Tweak 3 — Raster Y axis: "Trials" label + numeric ticks + earlier-trials-at-bottom

Three sub-tweaks:

**3a — Y-axis title:** `ax.set_ylabel("Trials")` on Row 4 panels. Replace any current y-axis label.

**3b — Numeric y-ticks:** replace the existing Standard/Close half-label y-ticks with numeric trial-index ticks. Show at minimum:
- `0` (first trial)
- Total trial count (e.g., `"40"` if 40 trials total per panel)

Optional middle tick (e.g., `"20"`) if the panel is large enough to not crowd. Sample values:
```python
n_trials = n_standard_trials + n_close_trials
ax.set_yticks([0, n_trials])   # minimal
ax.set_yticklabels(["0", str(n_trials)])
```

Use fontsize aligned with the new licking-xtick fontsize (12) for consistency, configurable via `defaults.yaml`:
```yaml
spout_close_vs_std:
  raster_ytick_fontsize: 11
  raster_ylabel_fontsize: 13
```

**3c — Earlier trials at bottom:** matches the visual gate single-session raster convention. Y-axis goes 0 at bottom, max-trial-count at top. If current implementation uses `ax.invert_yaxis()` or `origin="upper"` semantics → remove that. Trial concatenation order: first Standard session at bottom, last Close session at top (chronological from bottom up). The Standard/Close divider line sits at y = n_standard_trials.

**Standard / Close half labels — where they go now:** y-ticks now show numeric values, so the existing Standard/Close text needs a new visual location. Two options:
- **Option α:** small text annotations on the LEFT side outside the left spine (mirroring the day labels on the right). Centered vertically on each half. Standard-half label at vertical center of trials [0, n_standard]; Close-half label at vertical center of trials [n_standard, n_total]. Rotated 90° so the text reads bottom-to-top (top of letters away from plot, opposite Tweak 4.2 direction for day labels).
- **Option β:** inline text annotations inside the plot area at the top-left corner of each half (small, semi-transparent).

Recommended Option α — clean separation; mirrors day-label visual language. Add config knob:
```yaml
spout_close_vs_std:
  raster_half_label_fontsize: 11
```

If Option α leaves the figure too wide / cluttered → fall back to Option β.

Test pins:
- `ax.get_ylabel()` on Row 4 panels = "Trials"
- numeric y-tick values present (`"0"` + total count or similar)
- y-axis NOT inverted: `ax.get_ylim()[0] < ax.get_ylim()[1]` (bottom = 0, top = max-trial)

### Tweak 4 — Render all 3 animals

Skip the PS55-pilot-pause. Set `ANIMALS_BARE_VS_B = ["PS51", "PS54", "PS55"]` (or whatever the post-Round-3 variable rename calls it — likely `ANIMALS_SPOUT_CLOSE_VS_STD`). Re-render all 3 in one pass.

STOP-and-report all 6 files (`PS51_summary.{svg,png}`, `PS54_summary.{svg,png}`, `PS55_summary.{svg,png}`) for cohort verdict.

### File-touch (CG-B3 R5)

Same allowlist as Addendum #3. Expected churn:
- `src/stroke_orofacial/spout_behavior/spout_close_vs_std.py` — xticks, day-label centering, y-axis label/ticks/orientation, half-label relocation.
- `configs/defaults.yaml` — 4 new knobs under `spout_close_vs_std:` (raster_xticks, raster_ytick_fontsize, raster_ylabel_fontsize, raster_half_label_fontsize).
- `tests/test_spout_close_vs_std.py` — sync test pins.
- `notebooks/15_spout_behavior_visual_gate.ipynb` — set ANIMALS to all 3.

### Execute order

1. Implement 3 raster tweaks (single commit acceptable; all raster-localized).
2. Render all 3 animals. STOP-and-report all 6 files.
3. After cohort-PASS: phase-close (DECISIONS Decision 8 + MIGRATION_LOG addendum + state-doc refresh + PR).

### ALL OTHER LOCKS UNCHANGED

All prior Addendum locks preserved.

---

## Addendum #6 — CG-B3 Round 6 raster day-label de-rotation (PS54 readability fix)

**Date:** 2026-05-13.
**Trigger:** Priya review of CG-B3 Round 5 output. PS54 has 20 sessions (10 Standard + 10 Close) → 20 day labels stacked vertically in the right margin; rotated labels are unreadable at PS54's session density.

### Tweak — Day labels horizontal (rotation 270° → 0°)

In `spout_close_vs_std.py`'s day-label `ax.text(...)` call:

```python
ax.text(
    1.02, y_session_center, f"d{rel_day:+d}",
    transform=ax.get_yaxis_transform(),
    rotation=0,             # was 270 (Round 4); now horizontal for readability
    ha="left",              # text anchored to its left edge at x=1.02
    va="center",             # centered vertically on the session block
    fontsize=...,            # may need to drop slightly for PS54 density; tune at review
)
```

The label text reads left-to-right ("d+32") parallel to the x-axis, sitting just outside the right spine, centered on each session's row range.

For PS54 specifically (20 labels per panel), 8pt fontsize may be needed to avoid vertical overlap. Other animals (PS51 n=2, PS55 n=6) have more vertical room — same fontsize is fine. Recommend CC pick a single fontsize that works for PS54 (the constraining case) and apply uniformly via `defaults.yaml` knob.

Config knob name (already added in Round 4 — value bump only if needed):
```yaml
spout_close_vs_std:
  raster_day_label_fontsize: 8   # was higher; drop to fit PS54
```

### Scope — raster-only re-render workflow

Matplotlib doesn't support partial figure re-renders; the full 4×2 figure re-renders. But the only code change is the day-label `ax.text(...)` call (rotation + fontsize) and the only visual change is in Row 4. Renders should remain fast (~3.4s per animal × 3 = ~10s total).

### Execute order

1. Single commit: change `rotation=270` → `rotation=0`, adjust `ha`/`va`, tune fontsize for PS54 density.
2. Re-render all 3 animals.
3. STOP-and-report all 6 files for cohort verdict.

### File-touch (CG-B3 R6)

- `src/stroke_orofacial/spout_behavior/spout_close_vs_std.py` — single ax.text(...) call adjustment.
- `configs/defaults.yaml` — fontsize knob value bump if needed.
- `tests/test_spout_close_vs_std.py` — update rotation pin if present (`rotation=270` → `rotation=0`).

### ALL OTHER LOCKS UNCHANGED

All prior Addendum locks preserved. Tweaks 1, 3a-c from Addendum #5 (xticks, Trials label + numeric ticks, earlier-at-bottom orientation) and Tweak 2 day-label vertical centering fix all stay as-implemented.

---

## Addendum #7 — CG-B3 Round 7 raster y-ticks per-session-relative

**Date:** 2026-05-13.
**Trigger:** Priya review of cumulative-trial-index y-ticks (Round 5 Tweak 3b). Per-session-relative trial counts are more interpretable than cumulative — each session resets to 0.

### Tweak — Replace cumulative y-ticks with per-session "0" markers

**Supersedes Addendum #5 Tweak 3b only.** All other Round 5 raster decisions (Y-axis label "Trials", earlier-trials-at-bottom orientation, fontsize knobs) stay as-implemented.

For each session block in the raster, place a y-tick at the y-coordinate corresponding to the **bottom of that session's row range** (i.e., the first trial of the session) and label it `"0"`. Within each session, trial index runs 0 to N_session-1 from bottom to top of that session's block.

Implementation sketch:
```python
# When concatenating session trials chronologically (first session at bottom):
y_session_starts: list[int] = []   # y-coord at the BOTTOM of each session's row range
y_cursor = 0
for session_trials in sessions_in_order:   # all Standard then all Close
    y_session_starts.append(y_cursor)
    y_cursor += len(session_trials)

# Set y-ticks at those starts, all labeled "0"
ax.set_yticks(y_session_starts)
ax.set_yticklabels(["0"] * len(y_session_starts))
```

Net effect: PS54 (20 sessions) has 20 "0" markers per panel; PS55 (6 sessions) has 6; PS51 (2 sessions) has 2. The bottom-of-block "0" is the natural anchor — each "0" sits at the y-coordinate where session-local trial 0 lives.

### Optional consideration — readability at high session counts

For PS54's 20 stacked "0" markers, vertical spacing may be tight. If the labels visually crowd, two fallback options:
- **Fallback α:** keep fontsize aligned with `raster_ytick_fontsize` already in `defaults.yaml`; trust the spacing — "0" is only 1 character so collision risk is low.
- **Fallback β:** label only every Nth session's "0" (e.g., every 3rd) for the high-density case. Adds branching logic; defer unless visual confirms crowding.

Recommend Fallback α first; revisit at PS54 review if needed.

### Y-axis title

`ax.set_ylabel("Trials")` stays as set in Round 5 Tweak 3a.

### Test pin update

Update `test_raster_y_ticks_have_numeric_zero_and_max` (or whatever name Round 5 assigned) to:
- Count of y-tick labels per panel = `n_sessions_total` (was 2 — just "0" and max in Round 5).
- All y-tick labels equal the string `"0"`.

### File-touch (CG-B3 R7)

- `src/stroke_orofacial/spout_behavior/spout_close_vs_std.py` — replace cumulative `set_yticks([0, n_total])` with per-session-start `set_yticks(y_session_starts)`.
- `tests/test_spout_close_vs_std.py` — sync test pin.

No `defaults.yaml` change needed.

### Execute order

1. Single commit (tweak is localized).
2. Re-render all 3 animals.
3. STOP-and-report all 6 files.

### ALL OTHER LOCKS UNCHANGED

All prior Addendum locks preserved, except Addendum #5 Tweak 3b (cumulative y-ticks) is explicitly superseded.

---

## Addendum #8 — Post-hoc capture: per-trial cohort renderer

**Date:** 2026-05-13.
**Status:** POST-HOC. The per-trial renderer was implemented + committed during CG-B3 Round 7 follow-on work (commit `02be4b0`) ahead of this addendum being drafted. This addendum is descriptive — captures what landed so the kickoff doc reflects ground truth — not prescriptive.

### Scientific framing

Adds a per-trial counts-distribution view that complements the cohort summary's per-session mean-correct-licks endpoint (Rows 2-3 of `render_animal_summary_spout_close_vs_std`). The cohort summary aggregates to per-session means and shows that the average correct-lick-count per trial increases with closer spouts. The per-trial plot shows **the distributional shift underlying that mean**: with closer spouts, more trials accumulate multiple licks (3+, 5+, etc.) rather than capping at 1-2. This is an evidence-of-engagement signal — at standard distance, post-stroke mice frequently produce only a single contact per trial; at close distance, they engage with the spout repeatedly within a trial. Together with the cohort summary, it disambiguates "more average licks" between (a) more trials having any licks (already shown in Row 1 accuracy) vs (b) trials being more deeply engaged (this plot).

### Renderer

`render_animal_per_trial_spout_close_vs_std(animal, *, resolver, ...)` (or similar — confirm name from `02be4b0`'s implementation). Layout: 2×2 panels = (correct, incorrect) × (L cue, R cue). Pooled scatter across all Cohort B sessions for the animal. Each dot is one trial; condition (Standard vs Close) distinguished via the same convention as the cohort summary (filled = Standard, open = Close; dodgerblue / mediumvioletred for L / R cue panels).

### Output

`pipeline_outputs/spout_behavior/spout_behavior_figures/spout_close_vs_std/cohort/<animal>_per_trial.{svg,png}` (or whatever the implementation chose — confirm path).

### File-touch

Already landed in commit `02be4b0`:
- `src/stroke_orofacial/spout_behavior/spout_close_vs_std.py` — new renderer function.
- `tests/test_spout_close_vs_std.py` — pins added.
- `notebooks/15_spout_behavior_visual_gate.ipynb` — orchestration call.

### Scope deviation note

The original kickoff (and Addendum #1 sub-deliverable B scope-replacement) locked sub-deliverable B at 3 endpoints (accuracy + correct/incorrect licks + raster) cohort-only. The per-trial plot is effectively a 4th endpoint-shape (distributional view of per-trial lick counts), added after the cohort summary made visible that mean values alone don't convey the distributional shift. DECISIONS Decision 9 captures the rationale.

### ALL OTHER LOCKS UNCHANGED.
