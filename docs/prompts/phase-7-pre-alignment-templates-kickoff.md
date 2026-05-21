# Phase 7-pre-alignment-templates Kickoff — Cohort-wide alignment template emit + consumer cutover from legacy tree

**Branch:** `phase/7-pre-alignment-templates` off latest `origin/main` (post-Phase-7c.2 close + post-Phase-7d-if-merged-first, tag matching latest pre-Phase-9 close).
**Tag on phase-close merge:** `v7-pre-alignment-templates`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 7c.2 closed (PR merged + tag pushed); MICROSCOPE mount available (R/W on new tree; read-only on legacy tree per CLAUDE.md Rule 1); CC has read the memory entry `project_phase_7_pre_alignment_templates_forward_pointer.md` for context.
**Estimated scope:** medium. Cohort-wide emit + per-session parity validation + 6 consumer call-site cutovers + 5+ docstring references update + tests. ~6-12 commits, ~3-5 days CC wall time including ~30-60 min for cohort emit run.

---

## Context

Phase 8a.10.1 Task 5 audit (2026-05-14) surfaced a consolidation gap on the alignment template layer. Current state:

- **Phase 3 builder exists.** `src/stroke_orofacial/alignment/frame_sync.py` provides `make_alignment_template` (the per-session Phase 3 builder).
- **PathResolver methods exist.** `paths.py` has BOTH `alignment_template_legacy_read()` (routing to legacy tree) AND `alignment_template_new()` (routing to new tree).
- **Multi-half Pattern A merge wired.** `alignment/timebase.py` `compute_and_merge_alignment_multi_half` builds + writes merged templates to the NEW-tree path via `alignment_template_new()`.
- **But cohort-wide emit hasn't been done.** The new tree at `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` has only ~3 templates (one-off 2026-05-05 PS48 incident-response restore). The legacy tree at `MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/` has 345 templates across PS46-PS50, PS51, PS54, PS55.
- **All production read sites use legacy.** 6 consumer call sites currently route through `alignment_template_legacy_read()`: `manifest.py`, `dlc_spatial/tone_aligned.py`, `dlc_spatial/render_on_demand.py`, `dlc_kinematics/interpolation.py`, `dlc_kinematics/mean_sem_visual.py`, `dlc_kinematics/tongue_pertrial.py`. Plus 5 docstring references in `alignment/timebase.py`.

The pipeline isn't self-sufficient on the alignment-template layer — it depends on the legacy tree existing as a read source. F-P-7 closes that gap.

**Why this matters:** Phase 9 stats + pub-figures both want the pipeline to be reproducibly self-contained against `pipeline_outputs/`. As long as alignment templates only exist in legacy, any teardown or migration of the legacy tree breaks every DLC consumer. F-P-7 makes the new tree authoritative + leaves legacy as a fall-through fallback for safety.

**Verification per Phase 8a.10.1 Q1.A reversal:** Phase 3 is Sync-anchored (not Tone-anchored). The Tone↔Reward swap fix from Phase 8a.10.1 doesn't propagate to alignment templates — re-emitting from the new builder should produce byte-identical templates to the legacy tree for all sessions except known multi-half cases where Phase 7-pre-multi-half's merge code now applies.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Not applicable — Phase 3 builder + alignment timebase logic are already consolidated. Phase F-P-7 is operational cohort emit + consumer cutover; no legacy notebook port.

### Dead code identification

No dead code to remove. After cutover, `alignment_template_legacy_read()` remains as the fallback path (per "Legacy preservation" below). Outright deletion of the legacy-read method is deferred to a future cleanup phase (Phase 7-pre-alignment-templates-cleanup or rolled into pub-figures).

### Sub-phase breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch | (none) | 0 | <5 min |
| Task 1 — Cohort enumeration + emit dry-run | `.scratch_phase_7_pre_aligntmpl/cohort_manifest.csv` + dry-run log | 0 | 30 min |
| Task 2 — Cohort-wide emit | new-tree templates + per-session manifest | 1-2 | 30-60 min operational compute |
| Task 3 — Parity validation vs legacy tree | parity report + per-session byte-diff stats | 1 | 1-2 hr |
| Task 4 — Consumer cutover | switch 6 call sites + 5 docstring refs to new resolver | 2-3 | 1-2 days (most of the time is testing) |
| Task 5 — Unified read resolver + fallback | new method `alignment_template_for_reading()` | 1 | 4-6 hr |
| Task 6 — Test fixture + integration test updates | updated tests + new integration test | 1-2 | half day |
| Task 7 — Spot-check verification (STOP-and-report) | `.scratch_phase_7_pre_aligntmpl/verdict.md` | 0 | 30 min (CC) + Priya review |
| Task 8 — DECISIONS + MIGRATION_LOG | 2 docs files | 1 | 30 min |

### Parity strategy

**Two-axis verification:**

1. **Per-session byte-equality of new-tree vs legacy-tree templates** (Task 3). Phase 3 is Sync-anchored; if `make_alignment_template` is deterministic against fixed Wavesurfer Sync events + camera timestamps, the new-tree output should match the legacy-tree output byte-for-byte. Compute sha256 of every (animal, date) template in both trees; report:
   - **Identical** count: expected ~all single-half sessions.
   - **Different** count: surface for triage. Likely causes: multi-half sessions (Pattern A handled by `compute_and_merge_alignment_multi_half`); pre-Phase-3-refactor template versions in legacy; any sessions where legacy was hand-edited.
   - **Missing-in-new** count: should be 0 after Task 2 emit; nonzero means Task 2 cohort enumeration missed sessions.
   - **Missing-in-legacy** count: nonzero is okay — implies new pipeline can emit templates for sessions legacy never had (e.g., post-incident sessions).

2. **Consumer functional equivalence post-cutover** (Task 6). For 5-10 spot-check sessions, run a downstream DLC analysis (e.g., `dlc_spatial.tone_aligned.build_tone_aligned_analysis_by_animal_date`) twice: once with consumers reading legacy (pre-cutover code), once with consumers reading new (post-cutover code). Compare sha256 of analysis outputs; expect byte-identical.

### Hardcoded constants

No new constants. Phase 3 already uses `cam="cam2"` for the default camera; F-P-7 preserves this.

---

## Tasks

### Task 0 — Setup + branch

```bash
git fetch origin
git checkout main
git pull
git checkout -b phase/7-pre-alignment-templates
conda activate stroke_orofacial
which python
python -c "import stroke_orofacial"
pytest --collect-only
```

### Task 1 — Cohort enumeration + emit dry-run

Enumerate the (animal, date) sessions that need alignment templates from `configs/animals.yaml`:

```python
# scripts/phase_7_pre_aligntmpl/enumerate_cohort.py
from stroke_orofacial.config import load_animals
import datetime

cohort = []
for animal_info in load_animals().animals.values():
    start = animal_info.sessions.start
    end = animal_info.sessions.end
    excluded = set(animal_info.excluded_sessions or [])
    
    date = start
    while date <= end:
        if date.isoformat() not in excluded:
            cohort.append((animal_info.animal, date))
        date += datetime.timedelta(days=1)

# Plus secondary_spout_sessions (b-half) per Cohort B definition
for animal, b_half_dates in cohort_b_b_half_sessions.items():
    for date in b_half_dates:
        cohort.append((animal, date))
```

Expected count: ~341 Cohort A sessions + ~14 Cohort B b-half sessions ≈ 355 total. Cross-check against legacy tree's 345 templates — small delta is expected (legacy may have pre-cohort baseline sessions or post-cohort sessions outside YAML range; new pipeline is YAML-strict).

**Dry-run:** call `make_alignment_template` on 3 sample sessions WITHOUT writing — verify the function returns valid output for each. Catalog any failures in `.scratch_phase_7_pre_aligntmpl/dry_run_failures.csv`. **STOP-and-report** if any session fails — likely indicates a Phase 3 builder gap that needs separate diagnosis.

### Task 2 — Cohort-wide emit

Driver script `scripts/phase_7_pre_aligntmpl/emit_cohort.py`:

- Iterates the cohort manifest from Task 1.
- For each (animal, date): call `make_alignment_template`, write to `alignment_template_new()` path via PathResolver.
- For multi-half Pattern A sessions (PS48/2025-03-14 etc.): call `compute_and_merge_alignment_multi_half` instead, which writes the merged template at the parent path.
- Per-session manifest in `.scratch_phase_7_pre_aligntmpl/emit_manifest.csv`: columns (animal, date, status, error_msg, output_path, output_sha256, wall_time_s).
- Resumable: skip sessions already marked OK in the manifest.

Expected wall time: ~5-10s per session × ~355 sessions = ~30-60 min. Single-machine; no parallelization needed at this scale.

**Per CLAUDE.md Rule 6 (output writes go to new directories):** verify all writes go to `pipeline_outputs/dlc_analysis/alignment_templates/cam2/`, NOT on top of legacy `MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/`.

### Task 3 — Parity validation

Script `scripts/phase_7_pre_aligntmpl/parity_validate.py`:

```python
for (animal, date) in cohort_manifest:
    new_path = resolver.alignment_template_new(animal, date, cam="cam2")
    legacy_path = resolver.alignment_template_legacy_read(animal, date, cam="cam2")
    
    new_sha = sha256_of_file(new_path) if new_path.exists() else None
    legacy_sha = sha256_of_file(legacy_path) if legacy_path.exists() else None
    
    status = {
        ("identical", True, True): "IDENTICAL",
        # ...
    }[(legacy_sha == new_sha, new_path.exists(), legacy_path.exists())]
    parity_report.append((animal, date, status, new_sha, legacy_sha))
```

Output `.scratch_phase_7_pre_aligntmpl/parity_report.csv` with columns (animal, date, status, new_sha256, legacy_sha256).

Expected status distribution:
- **IDENTICAL**: ~all single-half sessions in cohort.
- **DIFFERENT**: multi-half Pattern A sessions (new tree has merged template; legacy has one of the half templates) + any pre-Phase-3-refactor legacy templates.
- **MISSING_LEGACY**: post-incident sessions; new pipeline emits for sessions legacy never had.
- **MISSING_NEW**: should be 0 (Task 2 emit was supposed to be exhaustive).

**STOP-and-report** if MISSING_NEW > 0 OR if DIFFERENT count is unexpectedly high.

For DIFFERENT cases: dig into the per-session level — open the legacy template + new template side-by-side, compute structural diff (e.g., `np.testing.assert_allclose` on numerical arrays + literal comparison on metadata). Document each DIFFERENT case in `.scratch_phase_7_pre_aligntmpl/different_cases.md`. Categorize:
- (A) Expected differences (multi-half merge, post-incident).
- (B) Suspicious differences requiring Priya review.

### Task 4 — Consumer cutover

Update the 6 active read sites to use the new tree (via Task 5's unified resolver method):

| File | Line | Change |
|---|---|---|
| `manifest.py` | ~827 | `alignment_template_legacy_read` → `alignment_template_for_reading` |
| `dlc_spatial/tone_aligned.py` | ~439 | same |
| `dlc_spatial/render_on_demand.py` | ~127 | same |
| `dlc_kinematics/interpolation.py` | ~555 | same |
| `dlc_kinematics/mean_sem_visual.py` | ~571 | same |
| `dlc_kinematics/tongue_pertrial.py` | ~1419 | same |

Plus update docstring references in `alignment/timebase.py` (lines ~163, 259, 359-360, 556, 558).

(Line numbers from memory snapshot 2026-05-14; verify against current code before editing — memories are point-in-time observations.)

### Task 5 — Unified read resolver + fallback

Add a new PathResolver method that prefers the new tree, falls back to legacy:

```python
# src/stroke_orofacial/paths.py

def alignment_template_for_reading(
    self,
    animal: str,
    date: datetime.date,
    cam: str = "cam2",
) -> pathlib.Path:
    """Returns the path to read an alignment template.
    
    Prefers the new-tree path under pipeline_outputs/; falls back to
    the legacy tree under MICROSCOPE/Priya/DeepLabCut/O2_analysis/ if
    the new-tree file doesn't exist.
    
    Used by every downstream DLC consumer that needs an alignment
    template. After Phase F-P-7 cohort emit + cutover, the new tree
    should be authoritative; the legacy fallback is retained as a
    safety net for sessions the new pipeline can't emit (e.g., very
    old sessions, hand-emitted incident-response templates).
    """
    new_path = self.alignment_template_new(animal, date, cam=cam)
    if new_path.exists():
        return new_path
    legacy_path = self.alignment_template_legacy_read(animal, date, cam=cam)
    if legacy_path.exists():
        return legacy_path
    raise FileNotFoundError(
        f"No alignment template for {animal}/{date.isoformat()} cam={cam} "
        f"at new path {new_path} or legacy path {legacy_path}"
    )
```

This method is the new canonical entry point for ALL downstream DLC consumers reading templates. The existing `alignment_template_new()` (write path) and `alignment_template_legacy_read()` (legacy-only read path) remain available for cases that explicitly need one or the other.

### Task 6 — Test fixture + integration test updates

- Update test fixtures that mock alignment template paths to use the new resolver method.
- Add `test_alignment_template_for_reading_prefers_new_tree`: creates a fixture session where both new and legacy paths exist; asserts new-tree path returned.
- Add `test_alignment_template_for_reading_falls_back_to_legacy`: legacy-only session; asserts legacy path returned.
- Add `test_alignment_template_for_reading_raises_if_neither`: neither path exists; asserts `FileNotFoundError`.
- Run full test suite: `pytest -x`. Expect post-7c.2 baseline + new tests passing.
- **Consumer functional equivalence spot-check (Task 3 parity strategy axis 2):** for 5 sessions (e.g., 1 single-half + 1 Pattern A multi-half + 3 random), run `dlc_spatial.tone_aligned.build_tone_aligned_analysis_by_animal_date` under pre-cutover code (git stash the cutover commits) vs post-cutover code. sha256 of analysis outputs should be byte-identical (modulo path renames).

### Task 7 — Spot-check verification (STOP-and-report)

Generate `.scratch_phase_7_pre_aligntmpl/verdict.md` summarizing:
- Task 2 emit: N sessions emitted; M failures (should be 0).
- Task 3 parity: K identical, L different (categorized), M missing-in-legacy, 0 missing-in-new.
- Task 6 functional equivalence: 5 sessions byte-identical post-cutover.

STOP-and-report to Priya for review before proceeding to phase-close PR.

### Task 8 — DECISIONS + MIGRATION_LOG entries

- `docs/DECISIONS/2026-XX-XX-phase-7-pre-alignment-templates.md` — 5-8 decisions:
  1. New-tree authoritative + legacy fallback strategy (Task 5).
  2. `alignment_template_for_reading()` as the new canonical read entry.
  3. Legacy `alignment_template_legacy_read()` preserved (not deleted) for safety.
  4. Per-session parity verdict (Task 3 numbers).
  5. Multi-half Pattern A handled via Phase 7-pre-multi-half's existing merge code (no new dev needed here).
  6. Any unexpected DIFFERENT cases from Task 3 surfaced for Priya review.
  7. Test additions for the unified resolver method.

- Append entry to `docs/MIGRATION_LOG.md` for Phase F-P-7 close.

---

## Verification

See Task 7 for the STOP-and-report verification gate. Acceptance signals:

- Task 2 emit produces ~355 templates with 0 failures.
- Task 3 parity report shows expected status distribution (mostly IDENTICAL; small number of categorized DIFFERENT).
- Task 6 functional equivalence: 5 spot-check sessions byte-identical pre vs post cutover.
- Test suite passes (post-7c.2 baseline + new tests).
- Phase-close PR opens against `main` with full task summary.
- Tag `v7-pre-alignment-templates` applied + pushed on merge.

---

## Acceptance criteria

- All sub-tasks (0-8) complete.
- New-tree templates emitted for full cohort (~355 sessions).
- Parity validation passes per axis-1 (byte-equality where expected; categorized differences understood).
- Consumer cutover applied to all 6 read sites + docstring updates.
- Test suite passes at post-7c.2 baseline + new tests.
- Spot-check functional equivalence verified.
- DECISIONS + MIGRATION_LOG entries land.
- Phase-close PR + tag follow CLAUDE.md conventions.

---

## Out of scope

- Deleting `alignment_template_legacy_read()` from PathResolver. The fallback path is retained for safety; deletion is deferred to a future cleanup phase.
- Changes to Phase 3 builder logic (`make_alignment_template`). F-P-7 uses the existing builder verbatim.
- Changes to multi-half Pattern A merge logic. Already shipped in Phase 7-pre-multi-half + wired in Phase 7c.2 Task 2.
- Changes to the legacy tree under MICROSCOPE/Priya/DeepLabCut/. Per CLAUDE.md Rule 1, legacy is read-only.

---

## Reference

- Memory: `project_phase_7_pre_alignment_templates_forward_pointer.md` (originating memory; 2026-05-14).
- Phase 8a.10.1 close DECISIONS — Decision 4 captures the F-P-7 origin (Phase 3 Sync-anchored ⇒ Q1.A reversal ⇒ F-P-7 surfaced as separate consolidation gap).
- `src/stroke_orofacial/alignment/frame_sync.py:make_alignment_template` — the existing Phase 3 builder.
- `src/stroke_orofacial/alignment/timebase.py:compute_and_merge_alignment_multi_half` — the existing Phase 7-pre-multi-half merge entry point for Pattern A sessions.
- `src/stroke_orofacial/paths.py` — existing `alignment_template_legacy_read` + `alignment_template_new`; F-P-7 adds `alignment_template_for_reading`.
- CLAUDE.md Rule 1 (read-only on legacy) + Rule 6 (output writes to new dirs) + Rule 7 (destructive-ops policy applies if cleanup queues a future legacy-removal phase).
