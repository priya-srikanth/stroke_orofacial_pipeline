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

---

## Addendum #1 — Warm-start state refresh (2026-05-22, post-7c.2 + post-7d close)

Original kickoff was drafted 2026-05-15, before Phase 7c.2 closed (2026-05-21) and before Phase 7d closed (2026-05-22). Warm-start verification on 2026-05-22 surfaced 5 state-drift updates + 3 locked decisions. **ALL OTHER LOCKS UNCHANGED.**

### State-drift updates

**S1 — F-P-5 (Phase 7-pre-multi-half-dlc) DISCHARGED 2026-05-21.** The SessionManifest Pattern A wiring fix was folded into Phase 7c.2 Task 2 per Q9.A bundling lock; PS48/2025-03-14 was re-emitted as part of cohort. References in this kickoff to "Phase 7-pre-multi-half-dlc" as a pending sibling phase are stale — F-P-5 is discharged. The merge code is wired at `src/stroke_orofacial/manifest.py:948-973` (verified 2026-05-22). Phase 7c.2 close DECISIONS.md Decision 3 documents the discharge.

**S2 — Task 4 consumer call-site count: 7 sites, not 6.** Phase 7c.2's compute-on-demand spatial render architecture (Decision 3 in 7c.2 close) added `src/stroke_orofacial/dlc_spatial/render_on_demand.py`, which has TWO `alignment_template_legacy_read` call sites (lines 128 + 182). Updated Task 4 table:

| File | Line (verified 2026-05-22) | Change |
|---|---|---|
| `manifest.py` | 827 | `alignment_template_legacy_read` → `alignment_template_for_reading` |
| `dlc_spatial/render_on_demand.py` | 128 | same |
| `dlc_spatial/render_on_demand.py` | 182 | same (NEW from 7c.2 compute-on-demand pivot) |
| `dlc_spatial/tone_aligned.py` | 439 | same |
| `dlc_kinematics/interpolation.py` | 547 | same |
| `dlc_kinematics/mean_sem_visual.py` | 566 | same |
| `dlc_kinematics/tongue_pertrial.py` | 1411 | same |

Plus 7 docstring references in `alignment/timebase.py` (lines 163, 259, 359, 360, 553, 556, 558) — update where call-site references appear inline; preserve where they document the PathResolver method names directly.

**S3 — PathResolver-bypass sweep already complete (Phase 7d Task 6).** Phase 7d ran a full source-tree sweep for PathResolver-bypassing path literals (5 grep patterns, 17 findings discharged). Verified 2026-05-22: no rogue `alignment_templates` literals exist in `src/` outside `paths.py` resolver methods + the writeguard declarative deny-list. Task 4's scope is the 7 explicit `legacy_read` call sites only — no hidden bypass surface to discover mid-phase.

**S4 — New-tree current state TBD; CC verifies at Task 1 start.** Kickoff Context claims "~3 templates from 2026-05-05 PS48 incident-response restore." This count is from 2026-05-15 and predates Phase 7c.2 cohort completion (which may have triggered Pattern A merge writes to the new tree for any multi-half sessions processed). Task 1's first sub-step: `find <pipeline_outputs>/dlc_analysis/alignment_templates/cam2/ -name "*.npz" | wc -l` + report the actual count + per-animal breakdown before the dry-run.

**S5 — F-P-5 reference updates in Out-of-scope.** Replace "Already shipped in Phase 7-pre-multi-half + wired in Phase 7c.2 Task 2" with the cleaner present-state framing: "Multi-half Pattern A merge code is shipped at `spout_behavior/multi_half_merge.py` + wired at `alignment/timebase.py:compute_and_merge_alignment_multi_half` (Phase 7-pre-multi-half, `v7-pre-multi-half`) and downstream SessionManifest.dlc_h5_files population is wired at `manifest.py:948-973` (Phase 7c.2 Task 2, F-P-5 discharge)."

### Locked decisions (3)

**L1 — Co-discharge cohort-enumeration-YAML-driven forward-pointer.** Task 1's enumeration driver iterates `configs/animals.yaml <animal>.sessions.start → .sessions.end` (filtered by `excluded_sessions`). This IS the clean YAML-driven pattern that `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` wants. Phase 7-pre-alignment-templates discharges that forward-pointer as a side effect — Task 8 DECISIONS adds Decision N: "Cohort-enumeration YAML-driven refactor forward-pointer co-discharged; driver pattern is now canonical for future cohort phases."

**L2 — Task 3 parity verdict: 4 pre-expected DIFFERENT categories + structural-allclose triage.**

`make_alignment_template` (frame_sync.py:143) uses `scipy.interpolate.interp1d` (line 136) + `np.polyfit` (lines 243, 248). These are exactly the floating-point-sensitive operations that surfaced version drift in Phase 7a.0 baseline-seed probe (PR #79, scipy 1.15→1.17 caused PS49/PS50 tongue Y0 retune). Legacy templates were emitted on the pre-Option-A scipy environment; new pipeline runs scipy 1.17.1. **Byte-equality across 345 sessions is expected to be partial — possibly low.**

Updated Task 3 parity verdict structure:

1. **IDENTICAL (sha256 byte-equal)** — legacy was emitted on the same scipy version as the new pipeline runs; expected for a subset of sessions.
2. **DIFFERENT — structurally-equivalent under `np.testing.assert_allclose`** — categorize via the cause:
   - (a) Multi-half Pattern A merge (legacy has one half template; new has merged).
   - (b) **scipy/numpy version drift** (sub-bit floating-point divergence, scientifically equivalent).
   - (c) Post-incident hand-emit (legacy template was hand-emitted from a different code path).
   - (d) Pre-Phase-3-refactor legacy version (old code path).
3. **DIFFERENT — structurally divergent** (assert_allclose fails) — REAL issue; STOP-and-report each case for Priya review.
4. **MISSING_LEGACY** — new pipeline emits for sessions legacy never had.
5. **MISSING_NEW** — should be 0; STOP-and-report if nonzero.

Task 3 logic: sha256 first-pass for fast categorization; for every non-IDENTICAL session, run `np.testing.assert_allclose` (default rtol=1e-7, atol=0) on each numerical array in the NPZ + literal compare on metadata. Categorize per the structure above. STOP-and-report only on category-3 (structurally divergent).

**L3 — Indefinite legacy fallback in `alignment_template_for_reading()`.** Replace Out-of-scope text "Deleting `alignment_template_legacy_read()` from PathResolver. The fallback path is retained for safety; deletion is deferred to a future cleanup phase" with: "Deleting `alignment_template_legacy_read()` from PathResolver. The fallback path is retained **indefinitely** as a safety net per CLAUDE.md Rule 1 (legacy is read-only and authoritative for archival sessions). No future cleanup phase queued — legacy fallback is a permanent feature of `alignment_template_for_reading()`."

### Addendum scope statement

All other locks (Tasks 0-2, 5-8; parity strategy axis 2; acceptance criteria; reference list) UNCHANGED. Addendum #1 only adjusts Task 4's call-site table (S2), Task 3's parity verdict structure (L2), Task 8's DECISIONS list (L1 co-discharge), Context (S1, S4), and Out-of-scope (S5, L3).

---

## Addendum #2 — Task 1 post-execution refinements (2026-05-22)

CC ran Task 1 cleanly. New-tree initial state is 3 templates (all under PS48/20250314 — kickoff's stale-state-warning was unnecessary; original count was accurate). Cohort enumeration produced 403 rows vs kickoff's ~355 estimate (+13%) — delta source-isolated by CC and benign. Dry-run 3/3 PASS. Two locks for Task 2 + a Task 1 count refinement. **ALL OTHER LOCKS UNCHANGED.**

### Task 1 count refinement (informational, not a lock change)

Kickoff's ~355 estimate is superseded by Task 1 enumeration:

| Source | Count | Notes |
|---|---|---|
| Cohort A single-half | 378 | YAML-strict + complete-by-default; +37 vs legacy tree's 308 (PS51/PS54/PS55 each had ~20-27 missing in-range templates legacy never emitted) |
| Cohort B b-half (`secondary_spout_sessions`) | 24 | Registry grew from ~14 → 24 between 2026-05-15 kickoff draft and 2026-05-22 (PS51=4, PS54=13, PS55=7) |
| Multi-half Pattern A | 1 | PS48/2025-03-14 only |
| **Total cohort_manifest.csv rows** | **403** | |

Expected Task 2 emit count: ~398 (403 − ~5 SKIP_NO_INPUT per L4 below).

### L4 — Task 2 emit driver SKIP_NO_INPUT handling (Priya 2026-05-22)

Task 1 surfaced 5 secondary_spout_b_half registry entries with no on-disk b-half WS data: PS51/2025-04-24, PS51/2025-04-25, PS54/2025-04-24, PS54/2025-04-25, and one of PS55/2025-04-24-or-25. Cross-check: legacy tree has 19 `*b.npz` files vs 24 registry entries = 5 missing, matching CC's per-animal accounting. These are registry entries that never had separate b-half acquisitions on disk.

**Lock.** Task 2 emit driver treats `manifest.wavesurfer_file is None` as a per-session **SKIP_NO_INPUT** event (log + continue), NOT a fatal cohort failure. Per-session manifest at `.scratch_phase_7_pre_aligntmpl/emit_manifest.csv` tags those rows `SKIP_NO_INPUT` with a populated `error_msg` column ("wavesurfer_file is None — no b-half WS acquisition on disk"). Acceptance criterion at Task 7 verdict: SKIP_NO_INPUT count ≤ 6 (5 expected + 1 buffer); any unexpected SKIP cases STOP-and-report.

*Enforced at:* Task 2 driver in `scripts/phase_7_pre_aligntmpl/emit_cohort.py`; `.scratch_phase_7_pre_aligntmpl/emit_manifest.csv` status column.

### L5 — Lock `analysis_context="alignment"` for cohort enumeration (Priya 2026-05-22)

Task 1 enumeration used `analysis_context="alignment"` (broader than DLC-strict), which keeps 4 sessions that are DLC-excluded but Phase-3-valid. Alignment templates are a Phase 3 product; they're emitted independently of DLC QC status. Consistent with "new pipeline complete-by-default" philosophy. CC's current `cohort_manifest.csv` uses this; no re-enumeration needed.

**Lock.** All F-P-7 cohort emit + parity validation uses `analysis_context="alignment"`. Future phases that need DLC-strict cohort enumeration (e.g., Phase 9 stats) use `analysis_context="dlc"` independently — F-P-7's choice doesn't constrain them.

*Enforced at:* `scripts/phase_7_pre_aligntmpl/enumerate_cohort.py` `analysis_context` parameter; `.scratch_phase_7_pre_aligntmpl/cohort_manifest.csv` row count (403 with "alignment"; would be 399 with "dlc").

### Addendum #2 scope statement

All other locks UNCHANGED. Addendum #2 only adjusts Task 1 count expectation (informational), Task 2 SKIP_NO_INPUT semantics (L4), and locks the cohort enumeration analysis_context (L5).

---

## Addendum #3 — Task 2 + Task 3 post-execution refinements (2026-05-22)

CC ran Task 2 + Task 3 cleanly. Task 2 emit: 277 OK + 126 SKIP_NO_INPUT (all legitimate "no WS data on disk" — see L6) + 0 FAIL. Task 3 parity: 0 IDENTICAL (Addendum #1 L2 scipy-drift prediction CONFIRMED), 1 expected multi-half divergence (PS48/2025-03-14), 274 scipy-drift-equivalent (category-b dominant as predicted), 2 borderline-divergent + 1 MISSING_NEW requiring per-case adjudication, 125 MISSING_BOTH (legitimate cutoff). Four locks for Task 4 + 3 pre-Task-4 actions. **ALL OTHER LOCKS UNCHANGED.**

### L6 — SKIP_NO_INPUT threshold revision (Priya 2026-05-22)

Addendum #2 L4's "≤6 threshold" anticipated only the 5 b-half registry-vs-disk-data gaps. Task 2 enumeration surfaced 121 additional single_half SKIPs from YAML-range-vs-recording-extent skew (sessions where YAML `sessions.start → .sessions.end` extends past the actual recording cutoff). CC verified all 126 SKIPs are legitimate: legacy tree also has no template for these dates, so the new pipeline is matching legacy correctly — the YAML range is the upper bound, not the actual recording extent.

**Revised acceptance criterion.** SKIP_NO_INPUT count ≤ 6 b-half SKIPs + N single_half SKIPs where N matches no-on-disk-data sessions (legacy also missing). Task 7 verdict cross-checks each SKIP against legacy tree absence. Any single_half SKIP where legacy DOES have a template → STOP-and-report as anomaly.

The cross-check identified exactly 1 such anomaly: PS55/2025-06-06 (legacy has template; new SKIP'd on ambiguous-h5 ValueError). Discharge via L9 below.

*Enforced at:* Task 7 verdict in `.scratch_phase_7_pre_aligntmpl/verdict.md`; Task 2 driver continues SKIP_NO_INPUT logic without threshold change.

### L7 — Task 3 parity threshold adjustment + outlier documentation (Priya 2026-05-22)

Addendum #1 L2's `np.testing.assert_allclose(rtol=1e-7, atol=0)` thresholds were too tight for actual scipy 1.15→1.17 drift magnitude. CC ran the practical pair `rtol=1e-5, atol=1e-6` which correctly categorized 274/277 as scipy-drift-equivalent (category-b). Two non-categorizable cases surfaced:

**Outlier #1 — PS54/2025-06-26 (b-half):** sig_wsIdx__idx_cam fails with max_abs=2.095e-06 (~2× atol), max_rel=3.058e-04 (~30× rtol). The magnitude is at the upper end of scipy interp1d/polyfit floating-point drift — unambiguously category-b in nature, just sitting at the high-magnitude tail.

**Outlier #2 — PS55/2025-05-02 (single_half):** sig_camTimesCommon__idx_cam + sig_camTimes__idx_cam + sig_wsIdx__idx_cam show a 1-sample shape delta (new=908112 vs legacy=908111). Substantively different from sub-bit drift — either scipy.interp1d boundary-inclusion semantics changed between versions, OR the `_find_rising_edges` detector counted differently due to floating-point comparisons against `edge_threshold`. **Required Task 3.5 root-cause investigation before Task 4.**

**Task 3.5 root-cause verdict (2026-05-22, CC investigation):** Neither Hypothesis A (scipy.interpolate.interp1d boundary semantics) nor Hypothesis B (`_find_rising_edges` divergence). Confirmed **Hypothesis C — legacy CSV-loader dropped the trailing row**, new pipeline ingests the full CSV faithfully. Evidence:
- Source-of-truth CSV has 908,112 rows (verified `wc -l`); file mtime 2025-05-02 (stable, not a growing-file race).
- New pipeline `sig_camTimes__idx_cam.shape = (908112,)` — matches CSV exactly.
- Legacy pipeline `sig_camTimes__idx_cam.shape = (908111,)` — missing one row at the tail.
- Element-wise: legacy `[-1]` value is the second-to-last CSV row (camera tick 111228430); new `[-1]` is the actual last CSV row (camera tick 111228431). The 1-frame delta at ~350 fps is ~3 ms of trailing recording — far from any task-relevant signal window.
- Session-specific: 274 other sessions have shape-matching arrays (just sub-bit scipy drift); only PS55/2025-05-02 triggered the legacy loader's trailing-row drop. Likely a per-CSV-formatting quirk (trailing newline, EOF byte handling, etc.) that no other session's CSV exhibited.

**Verdict:** New pipeline is **more correct than legacy** (faithful CSV ingest); scientifically equivalent at every magnitude. Categorize as edge-of-category-b in Task 8 DECISIONS. **Task 4 proceed cleared on the outlier-#2 axis.**

*Captured in Task 8 DECISIONS (forthcoming) — Decision N: "Phase 7-pre-alignment-templates surfaces a legacy CSV-loader trailing-row-drop bug (session-specific, PS55/2025-05-02). New pipeline's pandas-based CSV ingest is more faithful; the 1-sample delta at trailing tail is scientifically equivalent at downstream consumer scale (interpolation-array index resolution). No fix needed — new behavior is correct."*

**Lock.** PS54/2025-06-26 is documented as a category-b outlier in `.scratch_phase_7_pre_aligntmpl/parity_summary.md` with the magnitude flag preserved. PS55/2025-05-02 gates on Task 3.5 root-cause: if scipy boundary semantics, document as category-b boundary-edge outlier and proceed. If `_find_rising_edges` divergence, that's a Phase 3 builder behavior difference that needs Priya review before Task 4.

*Enforced at:* `.scratch_phase_7_pre_aligntmpl/parity_summary.md` outlier table; Task 3.5 in `.scratch_phase_7_pre_aligntmpl/ps55_20250502_root_cause.md`.

### L8 — Practical parity tolerance revision (Priya 2026-05-22, implicit via L7)

Override Addendum #1 L2's `(rtol=1e-7, atol=0)` tolerance pair. **Locked: `rtol=1e-5, atol=1e-6, equal_nan=True`.** Rationale: scipy 1.15→1.17 numerical drift in `scipy.interpolate.interp1d` + `np.polyfit` produces sub-bit differences in the 1e-6 to 1e-5 magnitude range; the practical tolerance pair categorizes them as expected (category-b) without false-positives at 1e-7 rigor. Future phases doing parity validation against legacy outputs should use the same tolerance pair as the default.

*Enforced at:* `scripts/phase_7_pre_aligntmpl/parity_validate.py` allclose call; documented in Task 8 DECISIONS as the canonical post-Option-A-scipy parity tolerance.

### L9 — In-phase fix for PS55/2025-06-06 ambiguous h5 (Priya 2026-05-22)

PS55/2025-06-06 has two `stroke_000{1,2}.h5` files in the WS dir. `find_wavesurfer_file` (`spout_behavior/wavesurfer_io.py:140`) raises ValueError on multiple matches. Priya's manual choice: **`stroke_0002.h5` is canonical; disregard `stroke_0001.h5`.**

**Lock.** F-P-7 closes this gap in-phase via Task 3.6 (new sub-task between Task 3 and Task 4):

1. **Task 3.6A schema proposal STOP-and-ask** — DISCHARGED 2026-05-22. CC proposed 3 schema options; Priya locked **Option A1** (new top-level `wavesurfer_file_overrides:` section, parallel to existing filesystem-discovery registries `secondary_spout_sessions:` / `multi_half_sessions:`). Schema shape:

   ```yaml
   wavesurfer_file_overrides:
     PS55:
       "2025-06-06":
         bare_ws_h5_filename: "stroke_0002.h5"
   ```

   The `bare_ws_h5_filename` field name reserves the `b_ws_h5_filename` naming slot for future b-half ambiguity (no consumer yet; out-of-scope for F-P-7).

2. CC plumbs the override through (Task 3.6B):
   - `find_wavesurfer_file(session_dir, *, preferred_filename: str | None = None)` — if `preferred_filename` is set AND the file exists in `session_dir`, return it; else execute existing glob-disambig logic. Override + ambiguity → override wins. Override set but file missing → raise `FileNotFoundError` naming both the configured override and actual disk contents (catches YAML-vs-disk drift early).
   - New `load_wavesurfer_file_overrides(overrides_config)` helper sibling to `load_secondary_spout_sessions` in the overrides-loader module.
   - `manifest.py` builder — when building a single_half manifest, look up `(animal, iso_date_str)` in the loaded `wavesurfer_file_overrides`; pass the override into `find_wavesurfer_file` via `preferred_filename=`.
   - Add unit tests for both `find_wavesurfer_file` paths (override present + override absent) AND for manifest builder honoring the override.

3. Add `configs/session_overrides.yaml` entry for PS55/2025-06-06 → `stroke_0002.h5` per the locked A1 schema (Task 3.6C).

4. Re-emit just the PS55/2025-06-06 row (Task 3.6D):
   - Update `emit_manifest.csv` to remove the existing SKIP_NO_INPUT row for PS55/2025-06-06 (so the resume-logic processes it).
   - Re-run `scripts/phase_7_pre_aligntmpl/emit_cohort.py` in resume mode.
   - Verify the new row lands as OK with `output_path` + `output_sha256` populated.

5. Re-run Task 3 parity check against just PS55/2025-06-06 (Task 3.6E); categorize alongside the rest. Update `.scratch_phase_7_pre_aligntmpl/parity_summary.md` with the post-fix verdict + 0 MISSING_NEW.

Out-of-scope for Task 3.6: any other ambiguous-h5 cases. The A1 override mechanism is general but the entry list stays at 1 row for F-P-7.

*Enforced at:* `configs/session_overrides.yaml` new section; `src/stroke_orofacial/spout_behavior/wavesurfer_io.py:find_wavesurfer_file` optional param; `src/stroke_orofacial/manifest.py` builder override lookup; `.scratch_phase_7_pre_aligntmpl/emit_manifest.csv` updated row.

### Pre-Task-4 sequence

Task 3.5 (PS55/2025-05-02 root-cause) and Task 3.6 (PS55/2025-06-06 in-phase fix) both gate Task 4. Suggested order: 3.5 → 3.6 → combined STOP-and-report → Priya "go" → Task 4. Task 3.5 is investigation-only (no code/data writes); Task 3.6 has CC's schema STOP-and-ask in the middle.

### Addendum #3 scope statement

All other locks UNCHANGED. Addendum #3 adjusts SKIP threshold acceptance (L6), Task 3 outlier documentation (L7), parity tolerance pair (L8), and adds Task 3.6 in-phase fix for PS55/2025-06-06 (L9). Task 4 consumer cutover scope unchanged; gated on Task 3.5 + 3.6 + Priya go.
