# Claude Code prompt — re-run pooled-phenotype analysis with updated epochs

Paste the block below into Claude Code, running in the `stroke_orofacial_pipeline`
repo.

---

We have changed the recovery-epoch boundaries and the severity grading scheme,
and I need the **entire pooled-phenotype analysis re-run** against the new
definitions. This is a large, multi-artifact refactor: do NOT start editing or
re-running anything until you have completed an audit and I have approved a
plan. Follow the project CLAUDE.md ground rules exactly (feature branch, never
commit to main, no destructive ops without per-invocation approval, copy-not-
move, outputs to existing output dirs via `overwrite="force"` at write time —
never pre-wipe with `rm -rf`).

## What changed (already committed/edited on a feature branch — confirm with `git status`/`git diff`)

1. **`configs/animals.yaml` → `epoch_boundaries`** re-derived 2026-06-08 from a
   combined recovery-index criterion (see `docs/epoch_criteria.md` and
   `src/stroke_orofacial/stats/epoch_derivation.py`). New per-animal values:
   - PS46 acute_max 5 / subacute_max 8 / chronic_min 9   (unchanged)
   - PS47 1 / 2 / 3      (was 1 / 4 / 5)
   - PS48 1 / 2 / 3      (was 1 / 4 / 5)
   - PS49 1 / 5 / 6      (was 1 / 4 / 5)
   - PS50 1 / 4 / 5      (unchanged)
   - PS51 6 / 31 / 32    (was 6 / 30 / 31)
   - PS54 19 / 38 / 39   (was 17 / 39 / 40)
   - PS55 19 / 50 / 51   (was 17 / 49 / 50)
2. **Severity grading is now THREE-tier** (mild / moderate / severe) in
   `src/stroke_orofacial/severity.py` (`_grade`): `severe` if persistence > 0.6
   or bilateral-cessation ≥ 10 d; `moderate` if cessation ≥ 2 d or contra-absent
   ≥ 3 d; else `mild`. The unified suppression threshold is 25 %. This yields
   mild {PS47–50}, moderate {PS46, PS51}, severe {PS54, PS55}.
3. **`recovery_phenotype` in `animals.yaml` is unchanged (still FOUR-tier**:
   mild / moderate / moderate-severe / severe, with PS51 = moderate-severe).

So there are now two phenotype groupings in play, and I want the pooled analysis
reproduced under BOTH:
   - **4-tier** = the `recovery_phenotype` field in `animals.yaml`.
   - **3-tier** = the behavioral `severity.severity_grade()` output.

## Phase 0 — setup
- `conda activate stroke_orofacial`; confirm `which python` is under the env and
  `python -c "import stroke_orofacial"` succeeds; `pytest --collect-only` must
  complete with no import errors before any other work.
- Confirm the feature branch and that the changes above are present
  (`git branch --show-current`, `git diff --stat`). If they are not yet on a
  branch, stop and tell me.

## Phase 1 — AUDIT ONLY (plan mode, change nothing)
Build a complete inventory of everything that depends on epoch boundaries or
phenotype grouping. Do this by searching the repo, not from memory — I may be
missing things. At minimum grep for and trace usages of:
- `epoch_boundaries`, `acute_max_rel_day`, `subacute_max_rel_day`,
  `chronic_min_rel_day`, `assign_epoch_label`, `assign_epoch_labels_to_inputs_df`,
  `epoch_label`, `cohort_phenotype_summary`, `recovery_phenotype`, `severity_grade`,
  `cohort_grade`, `phenotype`, `pooled`, `mixed`, `mixed-effects`, `lmer`/`mixedlm`,
  `mod-severe` / `moderate-severe`.
- The stats-inputs materialization (e.g. `scripts/phase_9_stats/` /
  `materialize_inputs`) that writes the `epoch_label` column into the
  `stats/inputs/**/<metric>/<animal>.parquet` trees — these are STALE (labeled
  from the old boundaries) and must be re-materialized.
- Every figure-generating and stats script/notebook that bins, pools, facets, or
  models by epoch or phenotype (Phase 9 / 9.1 pooled-phenotype figures,
  mixed-effects models, any per-epoch summaries), plus the severity outputs
  (`run_severity_burden.py`, `docs/figures/severity/*`) and the epoch-criteria
  figure (`run_epoch_derivation.py`, `docs/figures/epochs/*`).
- Any cached/intermediate outputs under `stroke_orofacial_pipeline_outputs/`
  that are derived from epoch labels or phenotype pooling.
- Tests that hard-code the OLD boundaries or the OLD 4-count phenotype
  distribution (e.g. `tests/test_animals.py` asserting PS54=40 / PS55=50 or
  `{mild:4, moderate:1, moderate-severe:1, severe:2}`), and any test asserting
  epoch labels.

Deliver, as a markdown table I can review, an **inventory** with one row per
artifact: path, type (materialized data / figure / stats result / test / doc),
what it depends on (epoch labels? which phenotype grouping?), whether it needs
regeneration, and the command that regenerates it. Flag anything ambiguous
(STOP-and-ask rather than guess). Also explicitly list anything you determine
does NOT need regeneration and why.

## Phase 2 — plan, then wait
Propose an ordered execution plan with a clear dependency chain (re-materialize
epoch_label inputs FIRST, then everything downstream). Specify how the 3-tier and
4-tier runs will be kept separate (distinct output subdirs / filename suffixes,
e.g. `..._pheno4tier` vs `..._pheno3tier`) so neither overwrites the other and
both are available for comparison. List every output that will be overwritten
with `overwrite="force"` and confirm no `rm -rf`/destructive step is needed.
**Pause for my explicit approval before writing anything.**

## Phase 3 — execute (after approval)
- Re-materialize the stats-inputs `epoch_label` column from the new boundaries.
- Re-run severity grading (3-tier) and regenerate its CSVs/figures.
- Re-run the epoch-criteria derivation/figure.
- Re-run every pooled-phenotype figure and statistical model under BOTH the
  4-tier (`recovery_phenotype`) and 3-tier (`severity_grade`) groupings, writing
  to the separated locations from the plan.
- Use `overwrite="force"` at write time; do not pre-wipe. Per
  CLAUDE.md/testing-conventions, no test may write to the real
  `stroke_orofacial_pipeline_outputs/` tree.
- Update tests that asserted old boundaries/phenotype counts to the new values,
  and update any doc tables that cite the old numbers (`docs/epoch_criteria.md`
  is already current; check `docs/severity_clustering.md`, MIGRATION_LOG, DESIGN,
  and any phase docs).

## Phase 4 — systematic verification (use a subagent for an independent audit)
This is the part I care most about — prove that nothing stale survives:
1. Re-run the Phase-1 grep audit and confirm every regenerable artifact's
   mtime is newer than the `animals.yaml` edit; list any figure/CSV under the
   outputs tree NOT touched by the re-run and explain why (should be only
   epoch/phenotype-independent ones).
2. Grep all regenerated figures' companion data/CSVs and docs for the OLD
   boundary values and the OLD 4-count phenotype distribution; confirm none
   remain except in clearly-labeled "previous value" comments.
3. Confirm the materialized `epoch_label` columns now match
   `assign_epoch_label` under the new boundaries for a few spot-checked
   (animal, rel_day) pairs straddling each new boundary (e.g. PS48 rel_day 2 vs
   3, PS54 rel_day 19 vs 20 vs 38 vs 39, PS55 rel_day 50 vs 51).
4. Run the full test suite (`pytest`), confirm collection count is unchanged and
   all pass.
5. Produce a final reconciliation table: artifact → old value/summary → new
   value/summary → regenerated? (yes/mtime) → verified? (yes). Anything you
   could not regenerate or verify must be called out explicitly.

## Phase 5 — log + commit
- Add a `docs/MIGRATION_LOG.md` entry describing the epoch re-derivation, the
  3-tier severity scheme, both pooled re-runs, and any intentional behavior
  differences.
- Commit on the feature branch with a clear message; do not commit to main; do
  not push tags until the PR is merged (I'll handle the merge + phase-close tag).

Throughout: if at any point the audit reveals an analysis output whose
regeneration is ambiguous or would overwrite something I might want to keep,
STOP and ask before proceeding.
