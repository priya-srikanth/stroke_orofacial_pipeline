# Phase 7-pre-alignment-templates — Verdict (5 axes per kickoff + Addenda #1-#3)

**Date:** 2026-05-22
**Branch:** `phase/7-pre-alignment-templates`
**HEAD (pre-PR-open):** see `git rev-parse HEAD` (`ede86bb` at time of writing)
**Tag (post-PR-merge):** `v7-pre-alignment-templates`
**Commits on branch (since `origin/main` = post-7d merge `fb9c283`):** 11

---

## Axis 1 — Test suite passes at post-7d baseline

Phase 7d baseline (pre-F-P-7): **1512 tests collected** (Phase 7d verification.md axis 1).

Phase 7-pre-alignment-templates HEAD: **1520 tests collected** = 1512 baseline + 5 Task-3.6B (wavesurfer_file_overrides plumbing) + 3 Task-5 (alignment_template_for_reading) = 1520.

Latest full run (post Task 4 follow-up commit `ede86bb`):

```
1481 passed, 39 skipped, 8 warnings in 213.24s (0:03:33)
```

Math: 1481 passed + 39 skipped = **1520 collected ✅** Zero failures, zero regressions.

New tests breakdown:
- **Task 3.6B** — `wavesurfer_file_overrides:` plumbing (5 tests):
  - `tests/test_wavesurfer_io.py::TestFindWavesurferFile`:
    - `test_with_override_returns_named_file`
    - `test_with_override_none_falls_through_to_glob`
    - `test_with_override_missing_raises`
  - `tests/test_manifest.py::TestWavesurferFileOverride`:
    - `test_manifest_builder_honors_wavesurfer_file_override`
    - `test_manifest_builder_no_override_uses_existing_disambig`
- **Task 5** — `alignment_template_for_reading()` (3 tests):
  - `tests/test_paths.py::TestNewConvenienceMethods`:
    - `test_alignment_template_for_reading_prefers_new_tree`
    - `test_alignment_template_for_reading_falls_back_to_legacy`
    - `test_alignment_template_for_reading_raises_if_neither`

Commit-by-commit count progression:
- After `363cf0c` (Task 3.6B): 1512 → 1517 (+5)
- After `42580e5` (Task 5): 1517 → 1520 (+3)
- After `deb8603` (Task 4 cutover): 1520 (3 mock-fixture failures triaged + 1 test signature mismatch surfaced)
- After `ede86bb` (Task 4 follow-up): 1520 collected; 1481/39/0; **0 regressions**.

---

## Axis 2 — New-tree populated; legacy tree preserved read-only

**New tree:** `pipeline_outputs/dlc_analysis/alignment_templates/cam2/`

Final state (verified at end of Task 3.6D + held stable through Tasks 4/5/6):

```
$ find <pipeline_outputs>/dlc_analysis/alignment_templates/cam2/ -name "*.npz" | wc -l
280
```

**280 templates total** broken down as:
- **277 OK rows in Task 2 emit_manifest.csv** = 276 single_half + secondary_spout_b_half rows + 1 multi_half_A row (PS48/2025-03-14, which produces 3 NPZs on disk: 1 merged at parent + 2 per-half under `20250314ab/`). Sum of NPZs on disk from Task 2 = 276 × 1 + 1 × 3 = 279.
- **1 PS55/2025-06-06 single-half template** emitted in Task 3.6D resume run (post-`wavesurfer_file_overrides:` fix, sha256 `379704cd7dbe6a26f5f009126f9cfd7591af4ea257fbad80bf243c8f28693f16`). → 279 + 1 = **280 NPZs on disk** ✓.

Task 2's force_recompute=True overwrote the pre-existing PS48/2025-03-14 templates from the 2026-05-05 incident-response restore (3 files at parent + per-half subdir).

Per-animal NPZ counts on disk (verified via `find <new_tree>/cam2 -name "*.npz" | grep /PS<NN>/ | wc -l`):
- PS46: **21** NPZs = 21 OK single_half rows (10 SKIP_NO_INPUT — recordings stopped 2025-03-27, YAML range extends to 2025-04-06)
- PS47: **21** NPZs = 21 OK single_half rows (10 SKIP)
- PS48: **23** NPZs = 20 OK single_half rows + 1 OK multi_half_A row × 3 NPZs (merged + 2 per-half) — (10 SKIP_NO_INPUT)
- PS49: **22** NPZs = 22 OK single_half rows (6 SKIP)
- PS50: **19** NPZs = 19 OK single_half rows (0 SKIP)
- PS51: **53** NPZs = 51 OK single_half + 2 OK b-half (28 single_half SKIP + 2 b-half SKIP)
- PS54: **63** NPZs = 52 OK single_half + 11 OK b-half (28 single_half SKIP + 2 b-half SKIP)
- PS55: **58** NPZs = 51 OK single_half + 6 OK b-half + 1 PS55/2025-06-06 from Task 3.6D (29 single_half SKIP + 1 b-half SKIP)

Sum: 21 + 21 + 23 + 22 + 19 + 53 + 63 + 58 = **280** ✓.

**SKIP_NO_INPUT total: 125** = 121 single_half (legitimate "no on-disk WS data" — legacy tree also has no template for these dates) + 5 secondary_spout_b_half registry entries with no on-disk b-half WS data (PS51/2025-04-24, PS51/2025-04-25, PS54/2025-04-24, PS54/2025-04-25, PS55/2025-04-25). Addendum #3 L6 lock: SKIP_NO_INPUT count ≤ 6 b-half + N single_half-no-data; cross-checked against legacy absence per session — every SKIP matched legacy missing.

**Legacy tree:** `MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/` (345 templates pre-phase, unchanged post-phase).

**CLAUDE.md Rule 1 verification:** 0 destructive operations on the legacy tree. The legacy tree was READ-ONLY throughout F-P-7 (parity validation reads + Task 6 spot-check reads only). Verified by reviewing all 11 commits + the driver scripts.

Reference: `.scratch_phase_7_pre_aligntmpl/new_tree_initial_state.md` (Task 1.1 pre-state), `.scratch_phase_7_pre_aligntmpl/emit_manifest.csv` (Task 2 + 3.6D outcomes).

---

## Axis 3 — Per-session parity full accounting

403 cohort_manifest.csv rows fully categorized per Addendum #1 L2 verdict structure (refined by Addendum #3 L8 to lock the practical tolerance pair):

| Category | Count | Mechanism |
|---|---|---|
| `IDENTICAL` | **0** | Per Addendum #1 L2 prediction (scipy 1.15→1.17 drift propagates to NPZ-level bytes) — confirmed empirically. |
| `DIFFERENT_STRUCTURAL_EQUIVALENT_a_multihalf` | **1** | PS48/2025-03-14: legacy has single template; new pipeline produces merged-from-halves template via `compute_and_merge_alignment_multi_half`. Expected per Phase 7-pre-multi-half. |
| `DIFFERENT_STRUCTURAL_EQUIVALENT_b_scipy` | **275** | Dominant category. `np.testing.assert_allclose(rtol=1e-5, atol=1e-6, equal_nan=True)` passes — scipy version drift in `scipy.interpolate.interp1d` + `np.polyfit` outputs is sub-bit relative to the data magnitudes. Predicted by Phase 7a.0 L2 baseline-seed precedent. |
| `DIFFERENT_STRUCTURALLY_DIVERGENT` | **2** | Documented outliers (see below). |
| `MISSING_LEGACY` | **0** | New pipeline did not emit for any session legacy didn't have. |
| `MISSING_NEW` | **0** | Discharged by Task 3.6D PS55/2025-06-06 re-emit (was 1 prior to L9 fix). |
| `MISSING_BOTH` | **125** | Sessions both new and legacy correctly omit (= 126 SKIPs from Task 2 minus 1 MISSING_NEW that became OK after 3.6D, both verified per kickoff axis 2 cross-check against legacy absence). |
| **Total** | **403** | matches cohort_manifest.csv row count |

**Tolerance pair lock:** `rtol=1e-5, atol=1e-6, equal_nan=True` (Addendum #3 L8 — canonical practical tolerance for post-Option-A-scipy parity).

**`DIFFERENT_STRUCTURALLY_DIVERGENT` outliers (2):**

1. **PS54/2025-06-26 (secondary_spout_b_half):** `sig_wsIdx__idx_cam` fails allclose with `max_abs=2.095e-06` (~2× atol), `max_rel=3.058e-04` (~30× rtol). Edge-of-category-b magnitude — scipy drift at the upper magnitude tail. Per Addendum #3 L7, documented as a category-b outlier; magnitude is genuinely small (2 microseconds on WS-sample-index mapping). No code fix needed.

2. **PS55/2025-05-02 (single_half):** 1-sample shape delta — new `sig_camTimesCommon__idx_cam.shape=(908112,)`, legacy `=(908111,)`. Root-caused in Task 3.5 ([.scratch_phase_7_pre_aligntmpl/ps55_20250502_root_cause.md](.scratch_phase_7_pre_aligntmpl/ps55_20250502_root_cause.md)): **Hypothesis C — legacy CSV-loader dropped the trailing row; new pipeline (pandas-based) ingests the full 908,112 rows.** New is more correct than legacy; scientifically equivalent (extra 3ms of trailing recording, far from any task-relevant window). Session-specific to PS55/2025-05-02 (no other session triggered the legacy quirk).

Reference: `.scratch_phase_7_pre_aligntmpl/parity_summary.md` (final categorization), `.scratch_phase_7_pre_aligntmpl/parity_report.csv` (per-session detail), `.scratch_phase_7_pre_aligntmpl/ps55_20250502_root_cause.md` (Hypothesis C verdict).

---

## Axis 4 — PathResolver method + consumer cutovers + functional-equivalence

**`alignment_template_for_reading()` PathResolver method** added at `src/stroke_orofacial/paths.py` (commit `42580e5`). Signature mirrors `alignment_template_new` + `alignment_template_legacy_read` including the Phase 7-pre-secondary-spout `session_suffix=` kwarg.

Semantics:
- Prefer new-tree path (`alignment_template_new(...)`); if exists, return.
- Else fall back to legacy-tree path (`alignment_template_legacy_read(...)`); if exists, return.
- Else raise `FileNotFoundError` naming BOTH candidate paths.

3 unit tests in `tests/test_paths.py::TestNewConvenienceMethods` assert the 3 cases (prefer-new, fallback-legacy, raise-if-neither).

**8 consumer call-site cutovers** (commit `deb8603` + Task 4 follow-up `ede86bb`):

| File | Line | Site |
|---|---|---|
| `src/stroke_orofacial/manifest.py` | 917 | `build_manifest`'s alignment_template caching path (wrapped in try/except FileNotFoundError → preserves None-when-missing) |
| `src/stroke_orofacial/alignment/timebase.py` | 259 | **Audit-missed +1 site** (see Axis 5): `load_or_compute_alignment`'s existing-template branch |
| `src/stroke_orofacial/dlc_spatial/render_on_demand.py` | 128 | tone-aligned compute-on-demand wrapper |
| `src/stroke_orofacial/dlc_spatial/render_on_demand.py` | 182 | whole-session compute-on-demand wrapper |
| `src/stroke_orofacial/dlc_spatial/tone_aligned.py` | 439 | `build_tone_aligned_analysis` consumer |
| `src/stroke_orofacial/dlc_kinematics/interpolation.py` | 547 | Phase 7a.2 interpolation consumer |
| `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` | 566 | Phase 7a.6 mean/sem visual consumer |
| `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` | 1411 | Phase 7a.3 tongue per-trial consumer |

**4 test fixtures updated** to mock `alignment_template_for_reading` instead of `alignment_template_legacy_read`:
- `tests/test_manifest.py` — 7 sites (1 mock_resolver fixture + 6 individual tests; missing-case mocks raise `FileNotFoundError` to model the new resolver's contract).
- `tests/test_manifest_multi_half.py` — `_alignment_template_legacy_read` helper renamed + raises FileNotFoundError.
- `tests/test_tongue_pertrial.py::TestTrialEventsAutoDerive::test_derive_trial_events_raises_on_missing_alignment_template` — added `session_suffix=` to the mock lambda + new `alignment_template_for_reading` monkeypatch (commit `ede86bb`).

**5-session functional-equivalence spot-check** ([.scratch_phase_7_pre_aligntmpl/functional_equivalence_magnitudes.md](.scratch_phase_7_pre_aligntmpl/functional_equivalence_magnitudes.md)):

| Session | Pattern | Tier | bin reassignments |
|---|---|---|---|
| PS46/2025-03-07 | single_half | `TIER_2_DISCRETE_IDENTICAL` | 0 |
| PS48/2025-03-14 | multi_half_A | `TIER_2_DISCRETE_IDENTICAL` | 0 |
| PS48/2025-03-24 | single_half | `TIER_2_DISCRETE_IDENTICAL` | 0 |
| PS46/2025-03-20 | single_half | `TIER_2_DISCRETE_IDENTICAL` | 0 |
| PS51/2025-06-11 | single_half | `TIER_2_DISCRETE_IDENTICAL` | 0 |

**Aggregate metrics:**

- `max(max_abs)` across all sessions × all keys = **0.000e+00** (vs atol=1e-6)
- `max(max_rel)` across all sessions × all keys = **0.000e+00** (vs rtol=1e-5)
- Total discrete attribute drift count = **0** (target: 0 for TIER_2)
- Total histogram bin reassignment count = **0** (target: 0 for TIER_2)

Consumer outputs (every numerical and discrete key) are **BIT-IDENTICAL** pre/post cutover — not merely allclose-equivalent.

**Mechanism: integer-rounding firewall.** The `int(round(camIdx_at_ws_sample))` step in `build_tone_aligned_analysis` maps tone-onset WS samples → cam-frame integer indices. The ~1e-6 scipy drift in upstream `sig_camIdx__idx_ws` is well below the 0.5 integer-rounding threshold for every tone-onset sample → integer frame indices identical between pre/post → ToneAlignedWindow bool mask identical → selected DLC rows identical → 2D heatmap (H_counts, H_proportion, xedges, yedges, extent, n_total_frames) identical. Property generalizes: any future scipy version bump producing sub-0.5-rounding-threshold drift will leave consumer outputs identical at this layer.

---

## Axis 5 — Audit-missed-site sweep (sibling to Phase 7d Task 6 lesson)

**Kickoff Addendum #1 S2 listed 7 alignment_template_legacy_read consumer call sites** identified via re-grep on 2026-05-22 against current code:

```
| manifest.py | 827 |
| dlc_spatial/render_on_demand.py | 128 |
| dlc_spatial/render_on_demand.py | 182 |
| dlc_spatial/tone_aligned.py | 439 |
| dlc_kinematics/interpolation.py | 547 |
| dlc_kinematics/mean_sem_visual.py | 566 |
| dlc_kinematics/tongue_pertrial.py | 1411 |
```

**Task 4 implementation found 8** — the +1 site was at [src/stroke_orofacial/alignment/timebase.py:259](src/stroke_orofacial/alignment/timebase.py#L259), inside `load_or_compute_alignment`'s "existing-template path" branch when `cam_idx != 2` OR `manifest.alignment_template is None`. This site was a real Addendum-#1 audit miss caught via Task 4's pre-cutover re-grep.

Discharged in-phase via the same cutover commit (`deb8603`) — the +1 site uses the same try/except FileNotFoundError pattern as the other 7 sites that need fallback semantics.

**Sibling lesson** to Phase 7d Task 6 PathResolver-bypass sweep: an initial manual audit + a re-grep verification step catches more than the initial audit alone. Sweep-style verification (re-grep against the current code state at task-start) should be standard before a cutover-style task.

Memory ref: `feedback_lock_language_is_not_implementation_verification.md` — lock prose ≠ implementation state; verify against current code.

**Grep verification post-cutover** — remaining `alignment_template_legacy_read` references in `src/`:

| File | Line | Purpose |
|---|---|---|
| `paths.py` | 192 | method definition (KEEP per Addendum #1 L3 indefinite fallback) |
| `paths.py` | 295 | docstring inside `alignment_template_for_reading` referencing the fallback |
| `paths.py` | 346 | actual call inside `alignment_template_for_reading` body — THIS is the legacy fallback |
| `timebase.py` | 163, 377, 576 | docstrings (PRESERVED per kickoff guidance — reference method name as documentation) |
| `timebase.py` | 275 | code-comment breadcrumb pointing at the pre-cutover behavior (intentional documentation) |

All remaining references are intentional. No untouched call site.

---

## Acceptance — all 5 axes verified

| Axis | Status | Key numbers |
|---|---|---|
| 1 — Test suite at post-7d baseline | ✅ | 1481 passed + 39 skipped = 1520 collected; +8 new tests (5 Task 3.6B + 3 Task 5); 0 regressions |
| 2 — New-tree populated; legacy preserved read-only | ✅ | 280 new-tree templates; 125 SKIP_NO_INPUT match legacy absence; 0 destructive ops on legacy |
| 3 — Per-session parity full accounting | ✅ | 403 cohort rows fully categorized; 0 MISSING_NEW; 2 documented divergent outliers (PS54/2025-06-26 + PS55/2025-05-02) |
| 4 — Resolver + cutovers + functional-equivalence | ✅ | 8 call sites cut over; 5/5 sessions TIER_2_DISCRETE_IDENTICAL with max_abs=max_rel=0.000e+00 (bit-identical consumer outputs) |
| 5 — Audit-missed-site sweep | ✅ | +1 site at timebase.py:259 discharged in-phase; sibling lesson to Phase 7d Task 6 |

---

## STOP — awaiting Priya's review before opening the phase-close PR

Next steps after Priya's approval:
1. Open phase-close PR titled "Phase 7-pre-alignment-templates: F-P-7 cohort emit + consumer cutover".
2. PR body covers task-by-task summary + Addenda #1-3 lock summary + 5-axis acceptance + Task 6 augment magnitudes (TIER_2_DISCRETE_IDENTICAL).
3. After PR-merge on main, apply tag `v7-pre-alignment-templates` to the merge commit with message: "Phase 7-pre-alignment-templates: F-P-7 cohort emit + 8-site consumer cutover from legacy tree + wavesurfer_file_overrides schema + integer-rounding firewall finding".
4. Push the tag to origin.
