# Cowork Session State

This file is the single warm-start document for a new Cowork session. See the "Best warm-start prompt" section at the end of this file for the exact paste-in to use in a fresh Cowork chat.

It captures what a new Cowork session needs beyond what's already in the canonical docs (`CLAUDE.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/MIGRATION_LOG.md`): current phase state, active tasks, open decisions awaiting human input, operational knowledge (two-tool workflow, env setup, known gotchas), and a record of completed work since this file was last updated.

**Maintenance rule.** Cowork updates this file (a) at the end of every meaningful session, and (b) mid-session when a major decision lands. The "Current state" and "Active tasks" sections should never be stale by more than one session.

---

## Warm-start checklist

A new Cowork session works through this in order before answering any substantive question:

1. Read `CLAUDE.md` — project ground rules (apply to any code-execution path, including Claude Code in VSCode that Cowork hands off to).
2. Read `docs/DESIGN.md` — full phase plan, architecture, cohort details.
3. Read `docs/DECISIONS.md` — decisions record, especially the most recent 5–10 entries (they're reverse-chronological).
4. Read `docs/MIGRATION_LOG.md` — scan the last 2–3 phase entries for recent delivery context.
5. Read `docs/SCIENTIFIC_ENDPOINTS.md` if the current work involves scientific endpoints, stats, or Phase 10 audit planning (currently relevant — see "Open decisions awaiting human input" below).
6. Read the "Current state", "Active tasks", and "Open decisions awaiting human input" sections of this file.
7. Skim "Operational knowledge" if unfamiliar with the two-tool workflow.
8. Ask Priya what she wants to work on, or pick up from the in-flight item listed under "Current state" if one exists.

---

## Current state

**As of:** 2026-04-22 (Phase 6.8a.3 notebook-12 save-loop skip-diagnostic split + task-runner pipefail fix merged as PR #68 merge-commit `5b20dd5`, tagged `v6.8a.3-notebook-12-skip-diagnostic`. The full Phase 6.8a arc — 6.8a → 6.8a.1 → 6.8a.2 → 6.8a.3 — is now closed on `main` with every sub-phase tagged. Phase 6.8a.2 unattended runners + runbook §8/§9 merged 2026-04-21 as PR #63 squash-commit `1f1b202`, tagged `v6.8a.2-unattended-runners`; cohort-first-emit-results docs merged same day as PR #66 onto main; Phase 6.8a.1 distinct-prereq-errors fix merged 2026-04-21 as PR #64, tagged `v6.8a.1-distinct-prereq-errors`; Phase 6.8a trial_group translation + first-emit NPZ writer merged 2026-04-21 as PR #62, tagged `v6.8a-phase-5-6-trial-group-translation`; Phase 7.0b cell-classification merged as PR #60, tagged `v7.0b-cell-classification`. Phase 6.8a cohort first emit completed on Windows CC under `feat/phase-6-8a-first-emit-runner` — 13,821 NPZs across 256 (animal, date) pairs, per-NPZ health check 13,821/13,821 pass, per-bundle health check 4,605/4,608 (99.93%), the 3 bundle failures at PS51/20250430 traced to benign "no qualifying tongue DLC frames in tight window" skip condition (the specific case v6.8a.3 was cut to make diagnosable). v6.8a.3 verification on PS51/20250430 reproduced the benign skip as the new `skip_no_frames=1` counter + matching `INFO: skip_no_frames` log line; pytest 464/34/0 post-change.)

**Repo phase:** Phases 1–6 + 4.5-lite + 6.7 + 6.8 + 6.8a + 6.8a.1 + 6.8a.2 + 6.8a.3 + 7.0b + 13 + 8a.1–8a.7.5 delivered on `main`. Task #17 closed the last cross-cutting convention decision blocking Phase 7 (DLC kinematics): NPZ / JSON / parquet side-keys now emit in mouse frame with version+flag stamps. Phase 6.8a threaded the convention through the reward-aligned writer and opened first-time Phase 6 NPZ emits for programmatic drift measurement. Phase 6.8a.1 refactored `build_reward_aligned_analysis` prerequisite-miss paths from silent `return None` to distinct `FileNotFoundError` so the cohort's 14,202-failure triage is diagnosable. Phase 6.8a.2 added unattended-runner scripts (`run_notebook_10_phase_4_centering.py`, `run_notebook_12_first_emit.py`) + runbook §8 / §9 for cohort-scale headless emits; validated end-to-end by the 2026-04-21 first emit (13,821 NPZs, 99.93% bundle pass). Phase 6.8a.3 closed out the diagnostic-gap carve-out from that first emit: notebook 12 + runner save-loop split the conflated `n_err` bucket into `n_skip_no_rewards` + `n_skip_no_frames` with distinct log lines, `scripts/task_runner_wrapper.sh` committed with `set -o pipefail` to defeat the `| tail -80` exit-code masking bug, runbook §8.4 refreshed to the current 6-bucket layout. Latest tags: `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`, `v6.8a-phase-5-6-trial-group-translation`, `v6.8a.1-distinct-prereq-errors`, `v6.8a.2-unattended-runners`, `v6.8a.3-notebook-12-skip-diagnostic`, `v7.0b-cell-classification`, `v8a.7-spout-endpoints-json-writer`, `v8a.7.5-criteria-hierarchy-port` (per the 2026-04-21 tag-convention-Path-A decision — every phase-close merge gets a tag, including letter-suffix atomic fixes).

**Current branch:** `main` at `5b20dd5` (PR #68 merge-commit — Phase 6.8a.3 notebook-12 skip-diagnostic split + task-runner pipefail; tag `v6.8a.3-notebook-12-skip-diagnostic` applied to the merge commit). Prior tips traversed since last state refresh: PR #67 merge at `ca01c05` (session-state refresh + embedded v6.8a.3 Windows-CC kickoff, no tag); PR #66 merge at `201923e` (cohort-first-emit-results docs, no tag, retroactive). Before the 2026-04-21 / 2026-04-22 run: PR #63 squash-merge `1f1b202` (Phase 6.8a.2 unattended runners, tag `v6.8a.2-unattended-runners`); PR #64 squash-merge `00ab3b7` then `a1844b1` (Phase 6.8a.1 distinct-prereq-errors, tag `v6.8a.1-distinct-prereq-errors`); PR #65 merge at `c8db81c` (runbook §8 tightening + kickoff rewrite, no tag); PR #62 (Phase 6.8a trial_group translation + first-emit NPZ writer + health-report script + runbook §8, tagged `v6.8a-phase-5-6-trial-group-translation`); PR #60 (Phase 7.0b cell classification, 5 classification docs, tagged `v7.0b-cell-classification`); earlier: PR #57 (test-hygiene), PR #56 (tag-convention), PR #55 (Phase 2 re-emit log), PR #54 (Task #17 implementation). All feature branches preserved on origin per CLAUDE.md §8.

**In flight:**

*(None — the full Phase 6.8a arc is closed on `main`. v6.8a.3 merged
2026-04-22 as PR #68 merge-commit `5b20dd5` and tagged
`v6.8a.3-notebook-12-skip-diagnostic`. Next session picks from the
"Next-phase candidates" list below, most likely Phase 7 — DLC
kinematics — which has a current kickoff prompt at
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`.)*

**Deferred / carry-forward housekeeping:** `scripts/parity_external_bnpm.py`
(the Phase 13 external-bnpm parity sweep script that surfaced the
clamp bug — carry-forward from 2026-04-20). Decide post-Phase-7-kickoff
whether to (a) `.gitignore` it permanently as scratch, or (b) promote
it to a permanent `scripts/` location with a docstring for future
bnpm-release re-parity runs. No rush; does not block any next-phase work.

**Test state (post-clamp-fix, PR #46 pre-merge):**

- Mac pytest on the impacted paths (`test_indexing.py` + `test_criteria.py` + `test_bouts.py` + `test_session_processing.py`): **58/58 pass**. Includes `TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it` (PS50 production regression guard), `tests/test_indexing.py` 12/12 (3 clamp-bug regressions + 7 edge cases + 2 random-parity), and both `TestIntegrationParity` session_processing3 baselines (PS46/20250307 zero-drift, PS50/20250320 zero-drift on the non-overhang path).
- Windows pytest (last full-suite measurement in the 8a.7.5 session): 361 pass / 28 skip / 0 fail. Phase 8a.7.5 merge added +20 criteria tests + 6 writer-schema tests. Not yet re-measured post-merge or post-clamp-fix; worth a non-blocking re-run at quiet moment to confirm the clamp-fix PR didn't introduce Windows-specific drift (not expected — the fix is pure numpy arithmetic).
- Pre-existing ruff warnings: 8 unused-import errors carried forward from before 8a (noted in prior Claude Code session summaries). Backlog item; not blocking.

**Next-phase candidates** (in rough priority order, post-task-#17 / #20 / #8 close):

1. **Phase 7 — DLC kinematics (tongue, jaw, whisker, nose).** Newly unblocked by task #17 (L/R convention). Kickoff prompt exists and is current: `docs/prompts/phase-7-dlc-kinematics-kickoff.md` (refreshed 2026-04-21 to reflect #17 landed + the deferred Phase 5/6 heatmap trial_group translation as a Phase-7-blocking follow-up). Scope per Audit Item 10 Q6: 6 core endpoints (tongue amplitude, tongue velocity, jaw amplitude, jaw velocity, whisker frequency, whisker angle) + 4 secondary (W1 baseline whisker angle, W2 whisker angle RMS, W3 whisker protraction event counts, F1 face-velocity PC1 power / N1 nose RMS) + face-velocity PCs 1–3 + PSD on tongue / jaw / whisker angle; per-trial AND whole-session granularity. HARD prerequisite: carry forward Priya's existing interpolated continuous kinematic traces for tongue/jaw (occlusion handling). Phase 7 kickoff must re-read `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` from MICROSCOPE `code/`.
2. **#10 remainder — Phase 8a.8** (visualization + recovery-phenotype prototype). First actual user-facing output of Phase 8a. No kickoff prompt yet; will need Cowork drafting. Orthogonal to Phase 7, can run in parallel.
3. **#10 remainder — Phase 8a.9** (close-out — legacy behavior-report walkthrough rollup per Audit Item 10 Q9). Scope TBD at 8a.8 close.
4. **Phase 5/6 heatmap trial_group translation (Phase-7-blocking if Phase 7 emits `reward_{side}_trials` slugs).** Deferred from task #17 per `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7. Small scope (thread the `wavesurfer_sides_match_mouse_sides` flag through notebook 12's reward-aligned `trial_group` path layer). Ungated; can run any time before Phase 7 first output-writing sub-phase.
5. **#18 — Add `sex` + `date_of_birth` to `AnimalInfo` schema + `configs/animals.yaml`.** Ungated, small. Nice to land before any Phase 9 stats work begins.
6. **#16 — Phase 5.5 polish** (SSH helper, recovery docs, ControlMaster, auto-rename, unified SVG save, DTW per-edge-shift QC plot). Ungated.

**Deferred follow-ups still pending (from earlier sessions):**

- **Cohort-wide Phase 5 re-run** (after the Phase 4.5-lite eye-midpoint centering landed — affects eye-centered outputs). Not yet scheduled; ask Priya whether to batch with 8a.8.
- **Phase 6 reward-aligned live-data re-test** with the new 4.5-lite-aware pipeline. Same category.
- **Windows housekeeping** (from Phase 13): stale admin-owned `C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini\` + `.pytest_cache\` directories — only if a future pytest run actually hits `WinError 5` again.

**Recent session log — 2026-04-21 (Task #17 L/R boundary-layer + Task #20 test-hygiene + Task #8 tag convention + Phase 7 prep):**

- **PR #53 merged** (`0ff6fd9`) before the main cycle: landed the Phase 7 kickoff-doc L/R-awareness edit from 2026-04-20. This added the §14 boundary-layer policy to the Phase 7 kickoff in docs/prompts/ — a prerequisite for the subsequent task-#17 PR.
- **PR #54 merged (`d7c1571`, 5-commit merge)** on branch `feat/wavesurfer-side-convention`: task #17 wavesurfer L/R ↔ mouse-frame boundary-layer translation. New `AnimalInfo.wavesurfer_sides_match_mouse_sides: bool = False` field; all 8 PS46–PS55 animals explicitly `false` in `configs/animals.yaml`; new `src/stroke_orofacial/lr_convention.py` (`to_mouse_frame`, `stamp_side_convention`, `SIDE_CONVENTION_VERSION = 1`); `SessionManifest` threads the flag through every orchestrator; Phase 2 NPZ writer (`_translate_side_keys` + `_save_npz_with_side_convention`) and Phase 8a `write_session_endpoints_json` translate + stamp at emit. New `docs/DESIGN.md §14 "CONVENTIONS"` codifying the project-wide rule. 14 new regression tests across `TestSideConventionAtEmit` in `test_session_processing.py` + `test_endpoints_writer.py`; 31 new tests in `test_lr_convention.py`. Full suite 454 → 482 passed. Mac integration parity (PS46/20250307 + PS46/20250320 un-flipped against session_processing3 baselines): zero drift on array values. Tagged `v6.8-wavesurfer-side-convention`.
- **PR #55 merged (`38b1781`)** on branch `docs/phase-2-reemit-task-17`: task #17 Phase 2 cohort re-emit log. Runbook-driven re-emit of PS46–PS55 (257 sessions, 1799 NPZs, 0 errors) to reconstruct the full Phase 2 output tree in mouse frame. `.pre-task17.bak/` sibling backup (16 files, 0.397 GB, spout_behavior subtree only — Phase 5/6 outputs untouched so narrower backup scope). §5 (Phase 8a.7.5 JSON re-emit) observed as no-op — no cohort orchestrator currently calls `write_session_endpoints_json()`. Known-benign drift on `Treadmill_smoothed` (max abs 1.78e-14, scipy filter-order reordering on rerun) inside `TestIntegrationParity` rtol=1e-10. Full `pytest -q` post-re-emit: 439 pass / 34 skip / 0 fail on Windows. No source data modified.
- **Test-hygiene smell flagged during re-emit investigation.** The PS46/20250307 backup was observed already post-task-#17 with `run_timestamp 2026-04-21T06:17:15` (before the runbook ran). Traced to two `tests/test_session_processing.py` integration tests writing to the real `stroke_orofacial_pipeline_outputs/spout_behavior/` tree via `overwrite="force"` + default `PathResolver`. Broader sweep found 4 offenders, not 2.
- **PR #56 merged (`56d3b6f`)** on branch `docs/tag-convention-task-8`: codified the phase-close tag convention in CLAUDE.md §8. Path A (tag every phase-close PR, including dotted sub-phases and letter-suffix atomic fixes). Three new bullets replacing the single ambiguous "tags per phase" bullet: (i) format `v{phase}-{slug}`, legacy `v0.X-phase-N-slug` preserved; (ii) tag message `Phase {phase}: {summary}`; (iii) push-immediately sequence. Decision originated in meta-discussion: Priya asked "what is the actual utility of the tag?" → enumerated 4 utilities (named checkout, diff anchor, branch-survival redundancy, narrative boundary) → all benefit from per-phase-close coverage.
- **PR #57 merged (`0d18a2b`, 3-commit merge)** on branch `fix/test-hygiene-task-20`: task #20 test-hygiene sweep. Commit 1: new `output_root: Path | str | None = None` kwarg on `PathResolver.__init__`; `pipeline_outputs()` returns `output_root / subdir` when override is set. Commit 2: the 4 offender tests (`test_process_and_params_json_written`, `test_skip_path_writes_params_json`, `test_process_session_with_manifest`, `test_process_session_succeeds_with_empty_dlc`) redirected to `PathResolver(output_root=tmp_path)`. Commit 3: new `docs/testing-conventions.md` + CLAUDE.md Repo Conventions link. Mac-side mtime + SHA-256 diff before/after: empty (the redirected tests write to `tmp_path` only). Full-suite Mac: 469 pass / 6 skip / 0 fail.
- **Docs rollup (uncommitted at session end, to land as `docs/phase-7-readiness`):** DECISIONS.md gained two 2026-04-21 entries (task #17 L/R boundary-layer; tag-convention Path A). MIGRATION_LOG.md gained a "Task #20 — Test-hygiene sweep" entry. `docs/prompts/phase-7-dlc-kinematics-kickoff.md` line 203 refreshed: stale "if task #17 hasn't landed, STOP" replaced with a "status as of kickoff" note pointing at `v6.8-wavesurfer-side-convention` + a deferred-follow-up note on the Phase 5/6 heatmap trial_group translation. This file refreshed.
- **Today's tag inventory:** `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`, `v8a.7-spout-endpoints-json-writer`, `v8a.7.5-criteria-hierarchy-port` all follow the new Path A convention.

---

**Recent session log — 2026-04-20 (post-8a.7.5 merge — external-bnpm parity finding + Phase 5/6-prep + clamp-fix chain):**

- **PR #42 merged (`7953b97`)** via merge commit after the Windows `TestRealDataParityPS46_20250307` skip was resolved (PR #41, `b86c779`, fixed the silent skip when wavesurfer path mismatched). Phase 8a.7.5 closed on main. No divergence surfaced during implementation / review.
- **PR #43 docs post-review updates merged (`d60e240` via `ac91771`)** to reflect the 8a.7.5 PR #42 review outcomes and document the Phase 6 indexing-refactor prereq surfaced during the review.
- **External bnpm parity sweep executed on Mac** via scratch script `scripts/parity_external_bnpm.py` (not committed; see "In flight → housekeeping" above). Compared the new repo's `build_criteria_block` against a re-implementation of `behavior_report_PS.py:455-551` with live `bnpm.indexing.find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1 session each. One Category 2 divergence surfaced at PS50/20250324 trial k=40, L side. **Root cause:** bnpm 0.6.0's `find_idx_within_eps` has a `len(arr) - 1` clamp bug at the right edge — `np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr)` when the window extends past the last element, upstream clamps to `len(arr) - 1`, drops `arr[-1]`. Production `criteria.py:_sub_window_counts` (numpy mask on pre-windowed `TrialRecord.licks_*_indices_in_window`) is correct. **Verdict:** intentional divergence from upstream under the Phase 13 vendoring pattern.
- **PR #44 docs+test merged (`d6f8e90`, squash)** on branch `docs/8a.7.5-external-bnpm-parity-findings`: DECISIONS.md 2026-04-20 "Phase 8a architecture" entry gained a new "External bnpm parity finding" bullet with accompanying rationale + Enforced-at amendments. MIGRATION_LOG.md Phase 8a.7.5 entry gained a post-merge appendix capturing the PS50 reproducer. New regression guard `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`. **Forward obligation set:** the same clamp bug exists in the private `_find_idx_within_eps` port at `bouts.py:236-256`; fix-PR must land before Phase 5/6 kickoff.
- **PR #45 Phase 5/6-prep indexing-module refactor merged (`92b5d88`, squash)** on branch `prep-indexing-module-for-phase-5-6`: byte-identical move of `_find_idx_within_eps` from `src/stroke_orofacial/spout_behavior/bouts.py` into the new `src/stroke_orofacial/_utils/indexing.py` module. `bouts.py` imports rewritten (2 caller sites unchanged). No behavior change — deliberately scoped to make the subsequent clamp-fix reviewable in isolation. Append-tail merge conflict with PR #44's MIGRATION_LOG additions resolved locally (semantic ordering: 8a.7.5 appendix went INSIDE the 8a.7.5 entry before the `---` separator; Phase 5/6-prep entry is a NEW section after the `---`). 25/25 tests passed post-resolve.
- **PR #46 clamp-fix opened, about-to-merge** on branch `fix/indexing-find-idx-within-eps-clamp-bug`: removed both `il = min(max(0, il), len(arr) - 1)` and `ir = min(max(0, ir), len(arr) - 1)` clamps; expanded module + function docstrings with divergence rationale and right-edge no-clamp semantics; added `tests/test_indexing.py` (12 tests across `TestClampBugRegression`, `TestEdgeCases`, `TestRandomParity`) mirroring the divergent-port pattern from `test_vendored_bool_indexing.py`; appended new MIGRATION_LOG "Clamp-fix for `_utils/indexing.py:_find_idx_within_eps`" section. Measured drift: zero drift on PS46/20250307 session_processing3 baseline (the frozen non-overhang animal-session); intentional drift on PS50/20250324 trial k=40 (already guarded). 58/58 pass across impact set. Commit `192d5d2`. **Closure stamps applied:** DECISIONS.md "External bnpm parity finding" bullet gained a "Closure (2026-04-20)" sentence; MIGRATION_LOG Phase 5/6-prep entry gained a "Closure (2026-04-20)" sentence; MIGRATION_LOG Clamp-fix entry is the authoritative landing record.
- **Docstring-code mismatch at lower bound flagged as out-of-scope backlog item** (not fixed in clamp-fix PR): `side="right"` at the lower bound enforces strict `arr[i] > v - eps[0]`, not the half-open `[v - eps[0], v + eps[1])` that the upstream docstring implies. Latent inherited-from-bnpm ambiguity; only matters when `arr` contains a value exactly equal to `v - eps[0]` (rare in production lick/reward index arrays). Documented in `_utils/indexing.py` function docstring; investigation deferred until a caller actually needs the half-open convention.
- **CLAUDE.md `-d` subtlety clarification added** to Ground Rule 8: `git branch -d` checks "branch tip fully pushed to upstream" (NOT "merged to main"), so a fully-pushed unmerged branch deletes cleanly under `-d`. The merged-to-main check must be enforced by the caller (`gh pr view <N>` → `state: MERGED`). This bit us mid-session when two feature branches deleted despite their PRs not yet being merged.

**Recent session log — 2026-04-20 continuation (Phase 8a.7.5 implementation + PR #42 review):**

- **Windows Claude Code completed the 8a.7.5 port** on `phase-8a-part4-criteria-hierarchy` at `27f2432`: new `src/stroke_orofacial/spout_behavior/criteria.py` (~330 lines, pure-function C3/C4/C2 compute + `build_criteria_block` aggregator + fail-loud TrialRecord-window-coverage contract), `endpoints_writer.py` gains required `criteria` kwarg with strict validation and C1 auto-fill with the existing `INTER_SESSION_REQUIRES_COHORT_SENTINEL`, retires `CRITERIA_NOT_YET_COMPUTED_SENTINEL`, bumps `metadata.phase` to `"8a.7.5"`. 20 new tests in `tests/test_criteria.py` + 6 net in `tests/test_endpoints_writer.py`; full-suite 361 passed / 28 skipped. `ruff check` clean. PR #42 opened. No legacy bugs surfaced.
- **Cowork PR #42 review (2026-04-20).** Assessments: (i) `criteria.py` well-structured, half-open boundary semantics documented, config-snapshot embedded for provenance, legacy NaN-on-empty-side preserved. (ii) **Inline-reference independence verdict: PASSES.** `_reference_criteria_block` in `test_criteria.py:315` uses `int(w * Fs)` (truncation) vs production's `int(round(w * trial.Fs))`, operates on raw lick arrays vs production's pre-windowed TrialRecord arrays, and iterates via nested for-loops vs production's list comprehensions. Shares only the numpy `(>= lo) & (< hi)` primitive — mitigated by explicit synthetic boundary tests. (iii) Writer signature change (`criteria` becomes required kwarg) is a breaking API change but no external callers exist (grep confirmed) so no silent breakage. (iv) New `CALLER_SUPPLIED_CRITERIA_SLUGS` / `COHORT_AGGREGATED_CRITERIA_SLUG` module constants make the contract explicit; new slug-map cross-check guards against defaults.yaml drift. (v) MIGRATION_LOG thorough with three intentional-divergence bullets (C1 sentinel, per-side list shape, TrialRecord window contract); no DECISIONS divergence entry needed since no legacy bugs hit. (vi) `metadata.phase` change is a value bump, not a schema change (confirmed via `git show main:...`).
- **Review gate issue surfaced.** `TestRealDataParityPS46_20250307::test_build_criteria_block_matches_inline_reference` reports SKIPPED on Windows even with `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` mounted. Root cause under diagnosis — candidate causes: `PathResolver.wavesurfer_dir()` resolving to a path where the `20250307\PS46` subtree doesn't exist under the current mount scope, a pathlib-on-UNC quirk on Windows `Path.exists()`, or the helper's `except OSError` silently swallowing an unreachable-path error. Windows Claude Code diagnostic prompt cut with a decision tree for fix (either path-config fix, test-harness tighten, or UNC-existence fallback). Merge of PR #42 gated on test running non-skip.
- **External-bnpm parity hardening task queued.** Mac Claude Code one-off: `scripts/parity_external_bnpm.py` (scratch, not committed) runs the new repo's `build_criteria_block` vs a re-implementation of `behavior_report_PS.py:455-551` that imports real `bnpm.indexing.find_idx_within_eps` (or a pinned copy) on 3 sessions × 3 animals. Closes the residual "inline reference shares `(>= lo) & (< hi)` primitive with production" concern. Not a merge blocker; results roll into a DECISIONS 2026-04-20 "Phase 8a architecture" addendum entry documenting external-bnpm parity coverage as part of 8a.9 hardening.
- **`find_idx_within_eps` downstream audit** (triggered by Priya's Phase 5/6 8-s post-reward window question). Grep across both legacy repos + consolidated: legacy `find_peri_reward_periods.py` (Priya fork) and `find_peri_reward_and_tone_periods.py` (Rich upstream) each define their OWN inlined `find_idx_within_eps` — they do NOT import from bnpm. Identical semantics as the consolidated `_find_idx_within_eps` port. Conclusion: no new vendoring needed for Phase 5/6 kinematics/DLC perireward windows; same half-open helper serves. Backlog-add: factor `_find_idx_within_eps` out of `bouts.py` into `src/stroke_orofacial/indexing.py` (trivial refactor, blocks nothing).

**Recent session log — 2026-04-20 (Phase 4.5-lite + Phase 8a.1 through 8a.7 + 8a.7.5 kickoff prep):**

- **Phase 4.5-lite execution** (eye-midpoint centering), branch `phase-4.5-lite-eye-midpoint-centering`. Gate 1 + Gate 2 committed and PR-merged as PR #33 (`685d3f7`), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Post-merge validation follow-up merged as PR #34 (`d2a928c`). PS46/20250307 parquet hashes preserved across the centering change. Image-boundary axis-limit clamp tracked as Phase 5.x polish item (PR #35).
- **Phase 8a.1** (merged via PR #36, `1c798cb`): criteria slug-rename foundation — slug map + bijective validator in `src/stroke_orofacial/spout_behavior/criteria_slugs.py`; hardcoded constants renamed in `configs/defaults.yaml`. Four final slugs locked: `criteria_first_correct_lick_present`, `criteria_correct_lick_count_threshold`, `criteria_session_trial_pass_fraction_above_threshold`, `criteria_training_pass_consecutive_sessions` (see DECISIONS 2026-04-20 "Phase 8a architecture" entry).
- **Phase 8a.2–8a.6** (merged via PR #37, `531c5d7`): lick-bout detector (`find_lick_bouts`, `LickBout`); per-trial endpoint primitives + shared contracts (`TrialRecord`, `EndpointResult`, `build_per_trial_records`); within-session trend endpoints (`within_session_learning_curve`, `within_session_change`); inter-session persistence scaffold (per-session side; cross-session aggregation deferred to cohort layer); engagement-extras endpoints (`switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`).
- **Phase 8a.7** (merged via PR #38, `65d8917`): per-session JSON writer + schema 2.0.0 with all criteria emitted as sentinels. `src/stroke_orofacial/spout_behavior/endpoints_writer.py` with `write_session_endpoints_json()` + `lick_bouts_to_endpoint_result()` adapter + `SCHEMA_VERSION = "2.0.0"` + `CANONICAL_ENDPOINT_NAMES` frozenset + two sentinel dicts. Schema 2.0.0 has three top-level blocks (`metadata`, `endpoints`, `criteria`). Strict key validation; atomic write; SHA-256 provenance hashing. Parallel to legacy `report.json` (no parity required). D5–D8 scoping decisions captured in the DECISIONS 2026-04-20 "Phase 8a architecture" entry. Post-8a.7 housekeeping: `_v2` suffix dropped from file/config/kwarg/test-fixture names in the live codebase (`a41b643`); frozen archaeology / kickoff docs retain `_v2` as historical context.
- **Phase 8a.7.5 kickoff drafted** (merged via PR #39, `7164ffa`): `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` saved as a first-class repo artifact. Scope: port C3, C4, C2 as real per-session-computable values; C1 stays sentinel per provenance contract (cohort aggregation deferred to a future phase). Parity reference: `behavior_report_PS.py:455-551` on PS46/20250307.
- **Env-activation rule + legacy-snippets pattern** (merged via PR #40, `209acd4`): bundle of three changes. (a) New "Environment activation" section in `CLAUDE.md` (durable rule for all future sessions). (b) Mirror of the env-activation block into the 8a.7.5 kickoff (follow-up after PR #39 merged without it due to an SMB mount write race). (c) First instance of the legacy-snippets pattern: `docs/legacy_snippets/behavior_report_PS_455_551.py` is a read-only in-repo excerpt of canonical `behavior_report_PS.py:385-565` (C3/C4/C34/C2/C1 + `fn_convert_window_to_samples` + `fn_flip_lr`) with a provenance header. This unblocks byte-identical parity validation on machines without the legacy Github clone (specifically Windows).
- **Scope note surfaced while reading legacy C3/C4:** `bnpm.indexing.find_idx_within_eps` is a **fifth** bnpm helper used in the legacy C3/C4 path that is NOT in the Phase 13 vendored set (which covers `idx2bool`, `widen_bool_sparse`, `set_short_bool_to_low`, `gaussian_smooth_1d`). The 8a.7.5 port should **sidestep** it by using `TrialRecord`'s per-trial lick/reward indices (established in 8a.3) rather than vendoring a fifth helper. Flagged in the legacy-snippet provenance header and in the 8a.7.5 kickoff.

**Recent session log — 2026-04-19 through 2026-04-20 (Phase 13 closure):**

- **Mac-side vendoring work (cross two Mac Claude Code sessions):** Vendored 4 bnpm helpers into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT license (© 2021 RichieHakim) with full license-text reproduction in the module docstring. Strict ports: `idx2bool`, `gaussian_smooth_1d`. Intentional divergences (bug fixes over bnpm 0.6.0): `widen_bool_sparse` (upstream over-widens falling edges by `n_after + 1`), `set_short_bool_to_low` (upstream under-counts trailing True runs by 1). Dropped `bnpm[core]` + `numba` + `cmake` from `environment.yml` and `pyproject.toml`. Moved `pywavesurfer` out of `pyproject.toml` into post-env-create `pip install --no-deps` (its wheel pins `h5py==3.8.0` with no Py3.11 wheel). `wavesurfer_io.py` numpy 2.x fix: `float(Fs_in)` → `float(np.asarray(Fs_in).item())`. Integration-test tolerances un-lumped into two effects: `test_timebase.py` rtol 1e-10→1e-8 (LAPACK drift from numpy/scipy bump, unrelated) vs `test_bouts.py` + `test_session_processing.py` bool-array `bool_near_equal` helper with `max_frac=1e-4` (measured drift from vendored bug fixes).
- **Drift quantification on PS46/20250307 against frozen `session_processing3/*.npz`:** running_bouts 0 differ (identical), lick_bool_bad 2 differ (5.4e-7 fraction, max-run=2), quiet_bool 51 differ (1.4e-5 fraction, max-run=1 isolated singletons), peri_reward_bool 0 differ (identical). Scope of affected downstream artifacts: **none** — bool masks are terminal outputs, no module under `src/stroke_orofacial/` reads them as input.
- **Docs un-lumping (commit `cdd1e1e`, docs-only):** Reframed the narrative from "parity vendoring" to "vendoring + two intentional bug fixes over upstream bnpm 0.6.0." MIGRATION_LOG Sub-phase 13b expanded to 7-point Intentional-behavior-differences section with drift table and scope analysis. DECISIONS.md 2026-04-20 entry rewritten with dedicated "Intentional bug fixes" block between Decision and Rationale. In-source test comments in `test_bouts.py` and `test_session_processing.py` corrected from "LAPACK jitter" to "measured drift from vendored bug fixes."
- **Windows verification:** New `stroke_orofacial` env created on Windows under the per-user prefix `C:\Users\sabatini\.conda\envs\stroke_orofacial\` (not the ProgramData default, which was write-locked to non-admin shells). First rebuild attempt hit `EnvironmentNotWritableError`; cleared via admin-shell `conda env remove`, then the per-user rebuild succeeded cleanly. Full suite green (201/28/0). Torch/bnpm/numba/llvmlite/cmake all confirmed absent.
- **PR + merge + tag (commits `5de3597` + `e244c0b`, then merge `d031486`):** `5de3597` added a Windows-env-prefix note to MIGRATION_LOG Sub-phase 13a. Doc sweep (`e244c0b`) rewrote README Setup blocks into a single unified recipe and updated `docs/DESIGN.md` §2.3, §3 repo-layout tree, and §8 Environment Setup to reflect the unified env. PR #31 merged via `gh pr merge --merge` (matching prior-phase convention); `--delete-branch` intentionally not passed so the feature branch stays on origin. Tag `v0.7-phase-13-env-unification` annotated on `d031486` and pushed.

**Recent session log — 2026-04-19 (Phase 13 env-unification drafting, after audit merge):**

- Audit branch merged to `main`; `v0.6.5-audit-complete` tag pushed to origin.
- Feature branch `phase-13-env-unification` cut from `main`.
- Full import audit of pipeline: walked `src/`, `tests/`, `notebooks/`, and every notebook under `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`. Confirmed `opencv-contrib-python` and `tqdm` are unused anywhere (dropped). Found `scicomap` (6 nbs), `pot` (3 nbs), `patsy` (2 nbs — the locked Q6 Phase 7 re-read notebooks) as needed-for-Phase-5/7/9 additions.
- Confirmed the DLC/CUDA/PyTorch/ffmpeg stack is needed ONLY by `dlc_inference_o2/runner.py` (which runs on O2 inside the `deeplabcut` env) and by the legacy `20251112` O2 batch notebook (already consolidated). None of it belongs in the analysis env.
- Confirmed Keypoint-MoSeq (jax, jax_moseq, keypoint_moseq) is out-of-scope for v1 and should not contaminate the analysis env.
- Drafted `environment.yml` (unified, Python 3.11, conda-forge primary, `bnpm[core]` per https://pypi.org/project/bnpm/, pip-only for `scicomap` + `pywavesurfer` + `bnpm[core]`).
- Brought `pyproject.toml` into agreement with `environment.yml`.
- Reduced `environment-mac.yml` and `environment-windows.yml` to deprecation stubs.
- Priya reported Windows test-env install stuck on jinja2 — likely pip backtracking on the jupyter stack. Resolution deferred to next session.

**Recent session log (2026-04-18 through 2026-04-19, consolidated — audit work):**

Completed across the multi-day session:

- Audit Items 1–6 (renames, per-camera alignment structure, SessionManifest wiring plan, `load_centered_fresh` util spec, Phase 8 split into 8a/8b, Phase 5 sub-decisions including fine-grid NPZ save and all-bodyparts overlay design).
- **Eye-affine alignment experiment** — single-animal exploration (PS46) then full-cohort sweep (8 animals × 4 regimes × 13 bodyparts × all session dates). Per-animal outputs + cross-animal metric overview PNGs + `summary.txt` all committed under `notebooks/experiments/outputs/alignment_sweep/`.
- **Phase 4.5-lite decision locked** — eye-centered wins 8/9 movement bodyparts; spout_centered wins tongue; similarity and rigid transforms rejected (noise-amplification dominated signal-correction benefit). Kickoff doc at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`. DECISIONS entry 2026-04-19.
- **Audit Item 7 (Phase 6 reward-aligned DLC) closed** — 7 sub-items resolved via Phase 6.7 (rolled in 7.1/7.3/7.4/7.5), new Phase 6.8 task (7.2 — full heatmap/binned/Δ × session/reward-aligned matrix), new axis-sharing task (7.6/7.7). DECISIONS entry 2026-04-19.
- **Audit Item 8 (SSH workflow) closed** — 5 polish items batched into new Phase 5.5 polish task. DECISIONS entry 2026-04-19.
- **Audit Item 9 (SVG + output reorg) closed** — SVG via unified `save_figure` helper (rolled into Phase 5.5 polish task). Directory reorg to figure-type-first within existing `spout_behavior/` and `dlc_analysis/` top-levels. New Phase 6.75 task, sequenced between 6.7 and 6.8. DECISIONS entry 2026-04-19.
- **Audit Item 10 archaeology phase** — Explore agent cataloged 26 endpoints across 6 categories from two legacy repos; written to `docs/SCIENTIFIC_ENDPOINTS.md`. Discussion phase (Q1–Q10) deferred to next session.
- **Cowork-on-Windows declared permanently unavailable** for Priya's machine despite Hyper-V running + Max subscription; account-level feature-flag block. Mac-Cowork + Windows-Claude-Code split is the permanent workflow.
- **Audit Item 10 closure (this session)** — Walked Q1–Q10 with Priya, all decisions landed as a single grouped DECISIONS entry at top of `docs/DECISIONS.md`. Key outcomes:
  - *Q1:* Phase 3 linear alignment stays canonical; DTW notebook's end output is strictly worse (collapses back to linear fit with only first/last anchors vs Phase 3's polyfit over all matched edges). Per-edge-shift QC plot carve-out rolls into task #16 (Phase 5.5 polish).
  - *Q2:* `criteria_1/2/3/4` renamed to descriptive slugs — exact slugs finalized at Phase 8a kickoff.
  - *Q3:* Phenotype viz in Phase 8a; phenotype **classification** is a new Phase 9.1 between 9a and 9b.
  - *Q4:* Quiet-period endpoint reserved for FaceRhythm (v2).
  - *Q5:* `facerhythm_tca` stub reserved in Phase 11+ slot.
  - *Q6:* Phase 7 scope locked = 6 core + 4 secondary + face-velocity PCs 1–3 + PSD on tongue/jaw/whisker; per-trial AND whole-session; HARD prerequisite = interpolated continuous traces for tongue/jaw must carry forward from Priya's legacy code; re-read `20260203` and `20260416` DLC kinematic notebooks at Phase 7 kickoff.
  - *Q7:* Add `sex` AND `date_of_birth` to `AnimalInfo` + `animals.yaml`; cohort = mixed (sex/age as covariates, not strata).
  - *Q8:* Phase 9 splits into 9a (spout stats framework + spout endpoints) → 9.1 (phenotype classification) → 9b (DLC kinematic stats).
  - *Q9:* 8 new spout endpoints locked: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`. Phase 8a kickoff includes legacy-behavior-report walkthrough to match / discard / surface-additional metrics.
  - *Q10:* No re-prioritization needed; derived ordering matches existing task queue.

---

## Active task list

The authoritative source is the Cowork TaskList widget in the current session. Mirrored here for persistence across sessions. Numbers are Cowork's task IDs.

**In progress:**

*(None at the moment — v6.8a.3 closed as PR #68. Next work item is
picked from the "Next-phase candidates" list in the Current-state
section; most likely Phase 7 — DLC kinematics — via the existing
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`.)*

**Pending open (new 2026-04-21):**

- **PS48 2025-03-14 multi-session (two-half) handling.** Port the
  legacy DLC analysis's two-half merge into the new pipeline at two
  load boundaries: (a) Phase 2 `wavesurfer_io.py` (accept ordered list
  of `.h5` paths, concatenate per-sweep samples, preserve per-half
  provenance in `SessionManifest`); (b) Phase 4+ DLC I/O
  (`dlc_io/parquet.py` + upstream DLC H5 reader: accept ordered list
  of per-half DLC H5s + timestamp CSVs, concatenate in
  acquisition-time order, preserve per-half provenance in
  parquet-column metadata). `configs/session_overrides.yaml` may gain
  a `multi_half_sessions` registry. Ungated; can be scoped into Phase
  7 kickoff or cut as its own mini-phase. Known case: PS48 20250314;
  opportunistically audit the other 7 animals when the first fixture
  lands. See DECISIONS 2026-04-21 entry.

**Completed since last state refresh:**

- **#19 — Phase 6.8a.3 notebook-12 save-loop skip-diagnostic split +
  task-runner pipefail fix (PR #68, merge-commit `5b20dd5`,
  2026-04-22).** Windows CC work. Split the notebook 12 reward-loop
  guard `if result is None or result["histogram"] is None` into two
  distinct cases (`n_skip_no_rewards` for zero-rewards-for-trial_group;
  `n_skip_no_frames` for zero-qualifying-DLC-frames-in-window) with a
  per-case `logging.info` line and an updated 5-counter summary print.
  Mirrored the split in `scripts/run_notebook_12_first_emit.py`.
  Committed `scripts/task_runner_wrapper.sh` as the canonical reference
  wrapper with `set -euo pipefail` so the `| tail -80` stage no longer
  masks the health-report script's exit code. Refreshed runbook §8.4
  to the current 6-bucket layout (3 `FileNotFoundError` types from
  v6.8a.1 + 2 counter-split skip modes from v6.8a.3 + catch-all `Exception`).
  3 new unit tests in `tests/test_notebook_runners.py`. Post-change
  pytest 464/34/0; ruff clean. PS51/20250430 reproducer reported
  `skip_no_frames=1 err=0` exactly as predicted. Tagged
  `v6.8a.3-notebook-12-skip-diagnostic` on the merge commit.
  Scope surprises: the task-runner wrapper did not exist as a
  committed file anywhere on the Windows box (wrote it from scratch);
  the health-report script reads the on-disk NPZ tree not the runner
  stdout (no parser extension needed); `NotebookEdit` re-serialized
  the reward-loop cell's `source` from a line-array to a single JSON
  string and normalized `\u2014` → `—` elsewhere — semantically
  identical but produces a larger notebook diff than expected.
- **Phase 6.8a.2 unattended runners + runbook §8/§9 (PR #63,
  `1f1b202`, 2026-04-21 late).** `scripts/run_notebook_10_phase_4_centering.py`
  (Phase 4 parquet emit runner) + `scripts/run_notebook_12_first_emit.py`
  (Phase 6.8a reward-aligned NPZ emit runner) + runbook
  `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §8 (runner
  invocation sequence) + §9 (troubleshooting / health-report
  interpretation). 5 commits (3 original + 2 merge commits
  `9274cb7`/`d901f4c` for the origin/main reconciliation). Validated
  end-to-end by the same-day cohort first emit (13,821 NPZs, 99.93%
  bundle pass). Tagged `v6.8a.2-unattended-runners`.
- **Cohort-first-emit-results docs (PR #66, 2026-04-21 late).**
  Retroactive-docs PR off `c8db81c` (PR #65 squash-merge commit).
  Added 51-line MIGRATION_LOG Phase 6.8a.1 "Cohort first emit
  (2026-04-21, PS46–PS55)" section + COWORK_SESSION_STATE refresh
  moving cohort-emit from in-flight to completed. No tag (retroactive
  docs refresh). Commit `c4e7d08`.
- **Phase 6.8a cohort first emit (Windows CC, 2026-04-21).** Notebook
  12 executed under `OVERWRITE="force"` across PS46–PS55 on the
  `feat/phase-6-8a-first-emit-runner` branch (origin/main merged in at
  Step 0 to carry the `v6.8a.1-distinct-prereq-errors` fix). Outputs:
  13,821 NPZs written under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/spatial_reward_aligned/`
  across 256 (animal, date) pairs. Per-NPZ health check: 13,821/13,821
  pass. Per-bundle health check: 4,605/4,608 (99.93%). 7,509 prereq-miss
  errors all carry distinct artefact-specific `FileNotFoundError`
  messages (the exact triage-enabling behavior Phase 6.8a.1 was cut
  for). The 3 failing bundles are all PS51/20250430 tongue
  `eye_midpoint` R-side in the tight -100to1000ms window; traced to a
  benign data condition (sibling -500to5000ms window passes for the
  same trials, so R rewards exist; tongue DLC likelihood falls below
  threshold in the tight window → `build_histogram` returns None →
  notebook line 166 guard skips without emitting an NPZ). Full cohort
  results logged in MIGRATION_LOG Phase 6.8a.1 "Cohort first emit
  (2026-04-21, PS46–PS55)" section. Surfaced two diagnostic gaps
  forwarded into #19 (v6.8a.3): notebook-12 save-loop guard conflates
  two skip conditions; task-runner `| tail -80` masks exit codes.
- **#17** — Task #17 wavesurfer L/R ↔ mouse-frame boundary-layer translation. Merged via PR #54 (`d7c1571`, 5-commit merge) + PR #55 (`38b1781`, Phase 2 cohort re-emit log). Tagged `v6.8-wavesurfer-side-convention`. Full details in MIGRATION_LOG "Task #17" entry + DECISIONS 2026-04-21 entry.
- **#8** — Tag convention Path A decision. Merged via PR #56 (`56d3b6f`). CLAUDE.md §8 codified with three new bullets (format, message, push-immediately). DECISIONS 2026-04-21 entry captures rationale (4 tag utilities).
- **#20** — Test-hygiene sweep: redirect integration tests off production output paths. Merged via PR #57 (`0d18a2b`, 3-commit merge). New `PathResolver(output_root=...)` kwarg; 4 offender tests redirected to `tmp_path`; new `docs/testing-conventions.md`. Mac-side mtime+SHA256 diff before/after confirms no production contamination. Full details in MIGRATION_LOG "Task #20" entry.
- **#10 (subtask) — Phase 8a.7.5 criteria hierarchy port.** Merged via PR #42 (`7953b97`, merge commit). 8 files changed, +1399 insertions. `criteria.py` implements C3/C4/C2 as real per-session-computable values; C1 stays sentinel per the per-session-JSON provenance contract. `endpoints_writer.py` gains required `criteria` kwarg with strict validation + C1 auto-fill + slug-map drift guard. 20 new `test_criteria.py` tests + 6 net `test_endpoints_writer.py` tests. Full details in MIGRATION_LOG Phase 8a.7.5 entry.
- **#10 (subtask) — Windows real-data parity skip fix.** Merged via PR #41 (`b86c779`). Resolved the silent skip of `TestRealDataParityPS46_20250307` caused by a path-resolver vs SMB-mount mismatch — clearing the blocker for PR #42 merge.
- **#10 (subtask) — 8a.7.5 docs post-review updates.** Merged via PR #43 (`d60e240` via `ac91771`, merge commit). Documented the PR #42 review outcomes + the Phase 6 indexing-refactor prereq surfaced during review.
- **#10 (subtask) — External bnpm parity finding (docs + PS50 regression guard).** Merged via PR #44 (`d6f8e90`, squash). DECISIONS 2026-04-20 "Phase 8a architecture → External bnpm parity finding" bullet + MIGRATION_LOG 8a.7.5 post-merge appendix + `tests/test_criteria.py::TestClampBugRegressionGuards`. Triaged the PS50/20250324 trial k=40 Category 2 divergence to upstream bnpm 0.6.0's `len(arr) - 1` clamp bug; verdict intentional Phase-13-pattern divergence from upstream.
- **#10 (subtask) — Phase 5/6-prep indexing-module refactor.** Merged via PR #45 (`92b5d88`, squash). `_find_idx_within_eps` moved byte-identically from `spout_behavior/bouts.py` into new package-private module `src/stroke_orofacial/_utils/indexing.py`. Deliberately scoped as pure move — no behavior change — so the subsequent clamp-fix would be reviewable in isolation.
- **#10 (subtask) — Clamp-bug fix in `_utils/indexing.py`.** Merged via PR #46 (squash, commit `9f3378d`). Removed the inherited bnpm 0.6.0 `len(arr) - 1` clamp; mirror-in-minimum regression coverage in new `tests/test_indexing.py` (12 tests: PS50/20250324 reproducer + synthetic boundary cases + random-input parity vs. independent numpy-mask oracle). Zero drift on PS46/20250307 session_processing3 baseline; intentional drift on PS50/20250324 trial k=40 already guarded. Closes the forward obligation set in the DECISIONS "External bnpm parity finding" bullet and the MIGRATION_LOG Phase 5/6-prep entry.
- **#3** — Phase 4.5-lite execution (eye-midpoint centering). Merged via PR #33 (`685d3f7`), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Post-merge validation (PR #34, `d2a928c`). Image-boundary axis-limit clamp carved out to Phase 5.x polish (PR #35). Full details in MIGRATION_LOG.md Phase 4.5-lite.
- **#10 (subtasks 8a.1 through 8a.7)** — Phase 8a criteria slug foundation + lick-bout detector + per-trial endpoint primitives + within-session / inter-session / engagement-extras endpoints + per-session JSON writer with schema 2.0.0. Merged via PRs #36, #37, #38 and the housekeeping / kickoff / unblock follow-ups #39 + #40. Full details in MIGRATION_LOG.md Phase 8a.7 entry + DECISIONS.md 2026-04-20 "Phase 8a architecture" entry.
- **#13** — Phase 13 env unification + bnpm vendoring. Full details in MIGRATION_LOG.md Phase 13 (sub-phases 13a + 13b) and DECISIONS.md 2026-04-19 + 2026-04-20 entries. Merged to main as `d031486`, tagged `v0.7-phase-13-env-unification`. Feature branch `phase-13-env-unification` preserved on origin.
- **#8** — Audit branch `audit-item-6-phase5-details` merged to `main` and tagged `v0.6.5-audit-complete`. Branch preserved as permanent reference per CLAUDE.md rule 8.

**Pending — queued phases and mini-phases**, in rough execution order (dependencies noted):
- **Phase 5/6 kickoff (new, unblocked 2026-04-20 by clamp-fix).** Reward-aligned kinematics / DLC peri-reward window ports (including 8-s-post-reward windows). No kickoff prompt yet; first task of next Cowork session may be drafting it. Overlaps with task #11 (Phase 7 DLC kinematic extension) — scoping clarification needed at kickoff. Ungated except by drafting effort.
- **#10 (subtask) — Phase 8a.8 recovery-trajectory visualization + phenotype-classification prototype.** Unblocked now that 8a.7.5 is merged. Needs Cowork-drafted kickoff prompt. Orthogonal to Phase 5/6; can run in parallel.
- **#10 (subtask) — Phase 8a.9 close-out** (legacy behavior-report systematic walkthrough per Audit Item 10 Q9; surface additional worth-keeping endpoints; discard stale ones). Scope TBD at 8a.8 close.
- **#9** — Phase 6.7 SessionManifest refactor. Kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`. Unblocked; can run in parallel with 8a.8 / 8a.9 (orthogonal code paths).
- **#17** — Phase 6.75 output directory reorganization (figure-type-first inside dlc_analysis and spout_behavior). Blocked on #9 so Phase 6.7's byte-parity checks remain valid at old paths.
- **#14** — Phase 6.8 full heatmap/binned/Δ × session/reward-aligned matrix. Blocked on #17.
- **#15** — Axis sharing (`share_xy_within_mouse` + percentile fallback + reward-aligned-specific axis config). Blocked on #14.
- **#10** — Phase 8a spout-only recovery trajectories (mid-experiment deliverable — DLC-independent). Blocked on #8 only; can execute in parallel with Phase 6.7/6.75/6.8 stack if resources allow. **Scope expansion from Audit Item 10:** also includes (a) finalizing the descriptive slug names for the renamed `criteria_1/2/3/4`, (b) Phase 8a viz of recovery phenotypes (faceting / coloring by fast / slow / non-recoverer), (c) 8 new spout endpoints from Q9 (`within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`), (d) systematic walkthrough of legacy `facerhythm_stroke_biomarker_exp_Priya` spout behavior code to match each of the 8 to existing implementations + surface additional worth-keeping metrics + explicitly discard stale/redundant ones.
- **#11** — Phase 7 reward-aligned DLC cohort extension + kinematic endpoints. Blocked on #9 + #10. **Scope locked per Audit Item 10 Q6:** 6 core (tongue amplitude, tongue velocity, jaw amplitude, jaw velocity, whisker frequency, whisker angle) + 4 secondary (W1 baseline whisker angle, W2 whisker angle RMS, W3 whisker protraction event counts, F1 face-velocity PC1 power / N1 nose RMS) + face-velocity PCs 1–3 + PSD on tongue / jaw / whisker angle; per-trial AND whole-session granularity. HARD prerequisite: carry forward Priya's existing interpolated continuous kinematic traces for tongue/jaw (occlusion handling). Phase 7 kickoff must re-read `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` from MICROSCOPE `code/`.
- **#12a** — Phase 8b DLC-based recovery trajectory visualization. Blocked on #11.
- **#12b** — Phase 9a stats framework + spout endpoint stats. Blocked on #10 (spout data pipeline) but independent of DLC.
- **#12c** — Phase 9.1 recovery-phenotype classification (fast / slow / non-recoverer fit). Blocked on #12b.
- **#12d** — Phase 9b DLC kinematic stats. Blocked on #11 + #12c (uses phenotype as covariate).
- **#12e** — Phase 10 cross-animal / cohort-level synthesis. Blocked on #12a + #12d.
- **#16** — Phase 5.5 polish (SSH monitoring helper, recovery docs, SSH setup, ControlMaster, auto-rename + SVG unified save helper). **Scope expansion from Audit Item 10 Q1:** also includes porting the one valuable diagnostic from the DTW notebook — the per-edge-shift QC plot (~20 lines) — as an alignment-diagnostic figure to surface any sessions with clear mid-session breakpoints that would need piecewise-linear transform fitting. Ungated — can execute any time.
- **#18 (new — Audit Item 10 Q7)** — Add `sex` and `date_of_birth` fields to `AnimalInfo` dataclass and populate `configs/animals.yaml` for all 8 mice. Downstream enables age-at-session and age-at-stroke as covariates in Phase 9. Ungated — small schema task, can execute any time before Phase 9a.
- **#19 (new — Audit Item 10 Q5)** — `facerhythm_tca` stub placeholder (Phase 11+ slot). Not a v1 deliverable; created as a tracking task so v2 planning has a handle. Deferred indefinitely.

**Phase-transition rule:** No new phase starts until the audit branch is merged to main and tagged (#8). Keeps the audit as one atomic chunk.

---

## Open decisions awaiting human input

*(None at the moment — Q1–Q10 from `docs/SCIENTIFIC_ENDPOINTS.md` all resolved this session and captured as the 2026-04-19 "Audit Item 10" grouped entry at the top of `docs/DECISIONS.md`. This section will re-populate when new decisions emerge.)*

**Note on SCIENTIFIC_ENDPOINTS.md:** the Q1–Q10 section at the bottom of that doc is now *historical* — superseded by the DECISIONS entry. The 26-endpoint catalog itself (categories A–F) remains the authoritative reference for what exists in legacy, what's planned for v1, and what's deferred.

---

## Recent decisions (pending transcription into `docs/DECISIONS.md`)

*(None at the moment. All in-session decisions from 2026-04-18 / 2026-04-19 have been written into DECISIONS.md. This section will re-populate when new decisions land before transcription.)*

---

## Operational knowledge

### Two-tool workflow (permanent since 2026-04-19)

**Cowork (this chat)** is the advisor/reviewer. It has:

- Read/write access to the Mac-side repo folder (at `/Volumes/Neurobio/...` from Cowork's sandbox view) — but NOT to MICROSCOPE data.
- No conda env; minimal Python sandbox without DLC dependencies.
- A TaskList widget for tracking state within one session.
- Cannot `git push` (sandbox has no GitHub auth); writes to the Mac's disk but Priya commits via Mac.

**Claude Code in VSCode** (on Priya's Windows machine, ethernet-connected to MICROSCOPE) is the executor. It has:

- The unified `stroke_orofacial` conda env on Windows (Python 3.11, conda-forge primary; see `environment.yml`). Installed at the per-user prefix `C:\Users\sabatini\.conda\envs\stroke_orofacial\` because `C:\ProgramData\anaconda3\envs\` is write-locked to non-admin shells. Same env name and deps as Mac. Legacy envs still exist and are parallel: `deeplabcut` remains the correct env for DLC training / O2 inference / Keypoint-MoSeq; `frsb` on Mac is preserved so the strict-port bnpm parity tests can run against live bnpm 0.6.0 on demand.
- Direct ethernet access to MICROSCOPE at `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` (Windows UNC path; no VPN).
- The repo checked out at `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`.
- Git access with `.githooks/pre-commit` that blocks direct commits to `main` / `master`.

**Cowork-on-Windows is NOT AVAILABLE** on Priya's setup despite meeting all published prerequisites — see "Cowork-on-Windows status" section below.

**Handoff pattern.** Cowork drafts "paste-in prompts" (usually in block-quote form) that Priya pastes into Claude Code's chat panel in VSCode on Windows. Claude Code reports back to Priya; she relays the summary to Cowork. Cowork reads committed outputs directly from its folder view of the repo.

**Mac-commit roundtrip.** When Cowork writes files (DECISIONS updates, new kickoff prompts, SCIENTIFIC_ENDPOINTS.md, etc.), the files land on the Mac's disk (which Cowork mounts) but are uncommitted. Priya runs a 30-second `git add / git commit / git push` sequence on Mac to get them to origin. Then Windows does `git pull` to see them. This is the only friction added by the split.

### Opening Claude Code in VSCode on Windows

1. File → Open Folder → select `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`.
2. Open the integrated terminal (Ctrl+backtick) and `conda activate stroke_orofacial` (the unified env from Phase 13; `conda activate deeplabcut` still works but is only correct for DLC training / O2 inference / Keypoint-MoSeq).
3. Click the Claude Code icon in the left activity bar (or Ctrl+Esc as the shortcut).
4. Paste the Cowork-drafted prompt.

### SMB / MICROSCOPE mount health

- Windows path: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\`.
- Mac path: `/Volumes/Neurobio/MICROSCOPE/Priya` (for when Priya uses the Mac directly).
- Mac mount goes stale after sleep. Symptoms: hangs, permission errors, empty `ls`. Fix: unmount + remount via Finder → Go → Connect to Server.
- Windows mount is stable (no VPN, no sleep issue).

### nbconvert streaming quirk

- `jupyter nbconvert --execute --inplace` does NOT stream cell stdout. Cell prints are buffered until the whole notebook is written back at the end.
- To see live per-cell progress: `jupyter nbconvert --to script <nb.ipynb> --stdout | python -u 2>&1 | tee /tmp/run.log`. Then rerun with `--execute --inplace` so outputs get baked into the `.ipynb` for commit.

### Memory / disk footprint heuristics (for sweep-style notebooks)

- Slim-cache pattern (learned from alignment-sweep): aligned-point arrays are transient; only small histograms survive into pickles. ~30–50 MB per animal pickle.
- Pre-slim-refactor version produced 5–19 GB per animal pickles that OOM-killed the kernel on long-record animals. Don't repeat that mistake.
- Per-animal incremental output (render figures and checkpoint pickle before moving to next animal) is the robust pattern for long-running sweeps.

---

## Cohort at a glance

8 mice from `configs/animals.yaml`:

| Animal | Stroke date | Session range | Notes |
|--------|-------------|---------------|-------|
| PS46   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS47   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS48   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS49   | 2025-03-17  | 2025-03-10 → 2025-04-06 | |
| PS50   | 2025-03-23  | 2025-03-19 → 2025-04-06 | |
| PS51   | 2025-04-29  | 2025-04-16 → 2025-07-09 | 2025-04-26 excluded (Rose Bengal sham) |
| PS54   | 2025-04-30  | 2025-04-16 → 2025-07-09 | 2025-04-26 excluded (Rose Bengal sham) |
| PS55   | 2025-04-30  | 2025-04-16 → 2025-07-09 | 2025-04-27 + 2025-04-28 excluded |

**Convention:** `stroke_date` is the date of the **last pre-stroke session**. Stroke is induced after that day's behavioral session. Sessions on `stroke_date` are baseline; sessions strictly after are post-stroke. `AnimalInfo.day_relative_to_stroke(date)` returns a signed int (negative = pre-stroke, 0 = stroke_date, positive = post-stroke).

**DLC status:** all 8 animals have full DLC inference done as of 2026-04-19 — no in-progress-inference edge cases to handle currently.

---

## Canonical DLC bodypart roster

The DLC model tracks 13 bodyparts, producing 39 DataFrame columns (`{bodypart}_x`, `{bodypart}_y`, `{bodypart}_likelihood`):

- `L_eye`, `R_eye`
- `L_spout`, `R_spout`
- `nose`, `jaw`, `tongue`
- `L_whiskers_1`, `L_whiskers_2`, `L_whiskers_3`
- `R_whiskers_1`, `R_whiskers_2`, `R_whiskers_3`

To confirm empirically from a fresh session, load any filtered H5 via `read_dlc()` and print `sorted(set(c.rsplit("_", 1)[0] for c in df.columns if c.endswith(("_x", "_y", "_likelihood"))))`.

---

## Key file locations

- Project ground rules (Claude Code): `CLAUDE.md` at repo root.
- Design doc: `docs/DESIGN.md`.
- Decisions record (append-only): `docs/DECISIONS.md`.
- Phase history: `docs/MIGRATION_LOG.md`.
- **Scientific endpoint inventory (new this session): `docs/SCIENTIFIC_ENDPOINTS.md`.** Has the Q1–Q10 discussion questions.
- Phase kickoff prompts (Cowork → Claude Code handoffs): `docs/prompts/phase-*-kickoff.md`.
- Cowork session state (this file): `docs/COWORK_SESSION_STATE.md`.
- Data model doc: `docs/DATA_MODEL.md`.
- Stats pipeline doc: `docs/STATS_PIPELINE.md`.
- Configs: `configs/animals.yaml`, `configs/defaults.yaml`, `configs/paths.yaml`, `configs/session_overrides.yaml`.
- Experimental (throwaway) notebooks: `notebooks/experiments/`.
- Production notebooks: `notebooks/*.ipynb`.
- Pipeline outputs on MICROSCOPE: `/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/` (Mac) or `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\` (Windows).
- Alignment-sweep experimental outputs: `notebooks/experiments/outputs/alignment_sweep/` (cross-animal `summary.txt` + metric overview PNGs + per-animal subfolders).

---

## Cowork-on-Windows status (as of 2026-04-19)

**Do not attempt to get Cowork working on Priya's Windows Enterprise machine.**

Extensive troubleshooting on 2026-04-19 did not yield a working Cowork install on Windows despite:

- Windows 11 Enterprise edition (correct tier for Hyper-V).
- Max subscription confirmed at account level.
- Claude Desktop 1.3109.0 (current release).
- Hyper-V enabled and running (`vmms` and `vmcompute` services both `Running`, `systeminfo` confirms "A hypervisor has been detected").
- Computer use toggled on in Settings.
- Clean full reinstall of Claude Desktop with cache-directory wipe (`%APPDATA%\Claude`, `%LOCALAPPDATA%\Claude`) after Hyper-V activation.
- Sign-out / sign-back-in.

Result: no Cowork tab appears in the Windows desktop app. The Claude VM (`yukonSilver` or equivalent) is never provisioned (`Get-VM` returns nothing). Likely cause is an account-level feature flag or staged-rollout gate that Anthropic controls server-side. Would require a support-ticket conversation with Anthropic to resolve, deferred indefinitely.

**Permanent workflow is Mac Cowork + Windows Claude Code in VSCode.** See "Operational knowledge → Two-tool workflow" above.

---

## Known gotchas

- **`configs/defaults.yaml` naming consistency.** Live spatial blocks use canonical bodypart names. A stale `dlc.bodyparts` placeholder block (lines 240–255) was corrected earlier in this session. If another stale block appears, prefer names from an actual DLC H5 file.
- **nbconvert stdout buffering.** See "Operational knowledge → nbconvert streaming quirk" above.
- **SMB mount stale-after-sleep** (Mac only; Windows is stable).
- **Plot file paths under `nbconvert`.** Jupyter's `__file__` is not defined inside a kernel. Robust pattern for notebook output dirs:
  ```python
  _cwd = Path.cwd().resolve()
  if _cwd.name == "experiments" and _cwd.parent.name == "notebooks":
      OUTPUT_DIR = _cwd / "outputs" / "<experiment_name>"
  else:
      OUTPUT_DIR = _cwd / "notebooks" / "experiments" / "outputs" / "<experiment_name>"
  ```
- **Whiskers naming.** The DLC model uses `L_whiskers_1` (plural "whiskers", left/right as prefix). Legacy `whisker_L1` / `whisker_R1` style appears in some stale configs and should be rejected.
- **Eye bodypart names.** DLC uses `L_eye` / `R_eye`, not `medial_edge_L_eye` / `medial_edge_R_eye` (stale legacy convention).
- **Slim-cache pattern for sweeps.** Aligned-point arrays are transient — derive histograms + drop `aligned_points` before pickling. See Phase 4.5 alignment-sweep notebook for the reference implementation. Retaining raw points in the per-animal pickle produces 5–19 GB files and OOM-kills the kernel on long-record animals.
- **Conda env cross-platform.** As of Phase 13 the unified analysis env is `stroke_orofacial` on both Mac and Windows (created from `environment.yml`). Legacy envs are preserved as parallel: `deeplabcut` (Windows) remains the DLC training / O2 inference / Keypoint-MoSeq env; `frsb` (Mac) is kept so strict-port bnpm parity tests can run against live bnpm 0.6.0. Use `stroke_orofacial` for all pipeline-analysis work; only fall back to `deeplabcut` / `frsb` for their specific residual purposes.
- **Windows env prefix.** On Priya's Windows box, `stroke_orofacial` is installed at `C:\Users\sabatini\.conda\envs\` (per-user, user-writable) rather than `C:\ProgramData\anaconda3\envs\` (machine-level, write-locked to non-admin shells). If a rebuild ever hits `EnvironmentNotWritableError` on ProgramData, use an admin-shell `conda env remove` to clear, then re-create from a non-admin shell so conda defaults to the per-user location.
- **Stale admin-owned pytest tmpdirs on Windows.** `C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini\` and `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline\.pytest_cache\` can end up owned by an elevated account after a prior admin-shell pytest run and will produce `PermissionError: [WinError 5]` on setup from a non-elevated shell. Workaround: `pytest --basetemp=C:/Users/sabatini/pytest_tmp`. Proper fix: elevated PowerShell `Remove-Item -Recurse -Force` on both paths.
- **Cowork's folder view can be stale.** If Priya pushes from Windows and doesn't pull on Mac, Cowork's read of the Mac's disk lags behind origin. Workaround: have Priya `git pull` on Mac before Cowork needs the fresh files, or have Cowork ask her to pull when it seems stale.
- **Multi-half acquisition sessions require merging at load time.** At least one session (PS48 2025-03-14) was acquired in two halves within a single behavior day — two sets of Flea3 `.avi` videos + timestamp CSVs + two Wavesurfer `.h5` files, one set per acquisition half. Legacy DLC analysis code merges these into one logical session; the new consolidated pipeline does **not yet handle this case**. Must be implemented at the two load boundaries (wavesurfer I/O for Phase 2, DLC H5 + timestamp-CSV + parquet I/O for Phase 4+) before any output-writing run on PS48 20250314 or similar multi-half sessions can be trusted. See TaskList task #18 and DECISIONS 2026-04-21 entry. Until the fix lands, a Phase 2 / Phase 4+ run on PS48 2025-03-14 will silently use only one half of the data (whichever path the discovery layer happens to return first) — a silent-wrongness failure mode with no loud error.
- **`| tail -80` (or any pipeline-wrapped invocation) silently masks non-zero exit codes unless `set -o pipefail` is active.** In bash, a pipeline's exit code is the exit code of the *last* stage by default — and `tail`, `head`, `grep` with matches, `tee`, etc. almost always exit 0 — so piping a failing command through any of them turns the wrapper's overall exit code into a lie. This bit the 2026-04-21 Phase 6.8a cohort-emit task-runner wrapper: `python scripts/phase_6_8a_first_run_health_report.py --verbose 2>&1 | tail -80` surfaced as "task completed successfully" while conda's `execute(125)` rode the first stage to the floor. Fix: `set -euo pipefail` at the top of any wrapper script. The canonical committed wrapper lives at `scripts/task_runner_wrapper.sh` (v6.8a.3) — source it or copy its prologue into any Windows Task Scheduler / ad-hoc invocation. `PIPESTATUS[0]` is the alternative if `pipefail` is not available.
- **`NotebookEdit` can re-serialize cells beyond the intended change (diff-size surprise, not a behavior issue).** When editing a cell whose `source` is stored as a JSON array of lines, `NotebookEdit` may rewrite the whole cell's `source` to a single JSON string, and may also normalize escaped unicode (`\u2014` → literal `—`) in *other* cells that get re-serialized as a side effect. Semantically identical JSON — pytest + integration verification confirmed no behavior change on the Phase 6.8a.3 edit — but the `git diff` of the notebook looks much larger than the logical edit. If you see an unexpectedly large notebook diff after a targeted edit, inspect a couple of the "extra" hunks: if they are line-array↔string reshapes or `\u####` → literal-char normalizations, they are cosmetic and safe. Don't try to revert them by hand; that fight isn't worth the time.

---

## Best warm-start prompt (paste into a new Cowork chat)

Phase 6.8a arc closed cleanly across 2026-04-21 / 2026-04-22: 6.8a → 6.8a.1 → 6.8a.2 → 6.8a.3, all tagged, cohort first emit validated (13,821 NPZs, 99.93% bundle pass, 3 benign PS51/20250430 tongue R-side skip-condition failures documented in MIGRATION_LOG and now surfaced as `skip_no_frames=1` by the v6.8a.3 counter split). Main is clean at `5b20dd5` (PR #68 merge-commit, tag `v6.8a.3-notebook-12-skip-diagnostic`). No in-flight work. Next candidate is Phase 7 — DLC kinematics — via `docs/prompts/phase-7-dlc-kinematics-kickoff.md`; the "Next-phase candidates" list under Current state has the full priority order.

**Open Cowork prompt for a fresh session (Mac or Windows desktop):**

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. The full Phase 6.8a arc (6.8a → 6.8a.1 → 6.8a.2 → 6.8a.3) closed on main, all tagged. No in-flight work. Ask me what we're working on — most likely Phase 7 DLC kinematics (kickoff prompt exists at `docs/prompts/phase-7-dlc-kinematics-kickoff.md`), but the "Next-phase candidates" list has other unblocked options.

*(The v6.8a.3 Windows-CC kickoff prompt that lived here has been retired — the work shipped as PR #68 merge-commit `5b20dd5`, tagged `v6.8a.3-notebook-12-skip-diagnostic`. See MIGRATION_LOG Phase 6.8a.3 entry for full details. Any future "fold a skip-bucket into its own counter + log line" work is scoped small enough to be described inline rather than needing a dedicated kickoff prompt.)*

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge.
- **2026-04-19** — Major refresh at end of multi-day session. Audit progressed from 6/10 to 9/10 items resolved; Phase 4.5-lite decision locked; several new tasks created (#14, #15, #16, #17); Cowork-on-Windows permanently deferred; `docs/SCIENTIFIC_ENDPOINTS.md` created with Q1–Q10 for next session. Transcribed all session decisions into DECISIONS.md. Next expected update: after Item 10 Q1–Q10 discussion completes.
- **2026-04-19 (audit closure)** — Walked Q1–Q10 with Priya in a focused second session the same day; all 10 decisions landed as a single grouped entry at the top of DECISIONS.md. Audit now 10/10. Phase 9 split into 9a/9.1/9b; task #12 refactored into #12a–e; new tasks #18 (sex/DOB schema) and #19 (facerhythm_tca stub) created; task #16 extended with DTW per-edge-shift QC plot carve-out; task #10 and #11 scopes expanded with locked Phase 8a/7 content. Next session opens with audit merge (#8).
- **2026-04-19 (Phase 13 drafting)** — Third session same day. Audit branch merged to `main`, tagged `v0.6.5-audit-complete`. Feature branch `phase-13-env-unification` cut from `main`. Full import audit performed across `src/`, `tests/`, `notebooks/`, and `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` to determine the minimum dep set for the new unified env. Drafted `environment.yml` (single env, Python 3.11, conda-forge primary, `bnpm[core]`). Added `patsy`, `pot`, `scicomap` (in-flight-port prereqs). Dropped `opencv-contrib-python` and `tqdm` (audit confirms zero imports). Brought `pyproject.toml` into agreement. Reduced old per-platform env files to deprecation stubs. Cowork context compacted mid-session (summary preserved). Windows test-env install was still spinning on jinja2 at session end — resolution deferred to next session.
- **2026-04-20 (Phase 13 closure)** — Windows env couldn't import bnpm because the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` that collides with conda-forge MKL's `libomp.dll` (`OMP: Error #15` + `WinError 127` on `shm.dll`). Resolved by vendoring the 4 pure-numpy bnpm helpers the repo actually uses into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT attribution and dropping `bnpm[core]` + `numba` + `cmake` from the env. Two vendored helpers intentionally diverge from upstream bnpm 0.6.0 to fix off-by-one bugs discovered while writing parity tests; drift measured (0 / 2 / 51 / 0 per-array on PS46/20250307 terminal masks; scope downstream: none). Full Mac + Windows verification green (Mac 223/6/0; Windows 201/28/0). PR #31 merged to main as `d031486`; tag `v0.7-phase-13-env-unification` pushed; feature branch preserved on origin. README + DESIGN.md §§2.3/3/8 + MIGRATION_LOG.md 13a+13b + DECISIONS.md 2026-04-19 + 2026-04-20 all written/reframed to reflect the unified env and the vendor-plus-bug-fixes narrative. All three next-phase candidates (#3 / #9 / #10) unblocked.
- **2026-04-20 (Phase 4.5-lite + Phase 8a.1 through 8a.7 + 8a.7.5 prep)** — Multi-session sweep executed predominantly on Windows Claude Code with Cowork-on-Mac providing advisory + kickoff-drafting + session-state maintenance. Phase 4.5-lite eye-midpoint centering merged (PR #33 + #34 + #35), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Phase 8a sub-phases 8a.1 (slug foundation, PR #36), 8a.2–8a.6 (bout detector + per-trial primitives + within-session / inter-session / engagement-extras endpoints, PR #37), and 8a.7 (JSON writer + schema 2.0.0 with sentinel criteria, PR #38) all landed. `_v2` suffix dropped from file / config / kwarg / test-fixture names (`a41b643`); frozen historical docs retain `_v2` as decision-trail context. Phase 8a.7.5 kickoff prompt saved as first-class repo artifact (PR #39). Follow-up PR #40 bundled three changes: new "Environment activation" durable rule in CLAUDE.md, mirror of the env-activation block into the 8a.7.5 kickoff, and new `docs/legacy_snippets/behavior_report_PS_455_551.py` establishing the legacy-snippets pattern (unblocks Windows byte-identical parity validation for the 8a.7.5 port without the legacy Github clone being present locally). DECISIONS.md 2026-04-20 "Phase 8a architecture" entry captures criteria slug finalization (fulfills Q2), 8a sub-phasing, schema 2.0.0 design, 8a.7.5 split rationale, `_v2` drop, and the legacy-snippets pattern.
- **2026-04-20 (Phase 8a.7.5 implementation + PR #42 review)** — Windows Claude Code completed the 8a.7.5 port on `phase-8a-part4-criteria-hierarchy` at `27f2432`: 8 files changed, +1399 insertions, full suite 361 passed / 28 skipped, ruff clean. PR #42 opened. Cowork PR review in one continued session: inline-reference independence verified (different data path, different window-index arithmetic, different iteration style vs production); writer diff clean with no external callers broken; MIGRATION_LOG thorough. Two review gates opened: (a) `TestRealDataParityPS46_20250307` skipping silently on Windows despite mapped SMB mount — Windows Claude Code diagnostic prompt cut with decision-tree fix guidance (merge blocker); (b) external-bnpm parity across 3 animals × 1 session each as a Mac Claude Code one-off — hardening-not-blocker, results roll into DECISIONS 2026-04-20 addendum if clean. Side discovery during review: `find_idx_within_eps` audit across both legacy repos confirms `find_peri_reward_periods.py` (Priya) and `find_peri_reward_and_tone_periods.py` (Rich) each inline their own copy — no new vendoring needed for Phase 5/6 kinematics/DLC perireward windows. Backlog-add: factor `_find_idx_within_eps` out of `bouts.py` into `src/stroke_orofacial/indexing.py` (Phase 5/6 prep, trivial).
- **2026-04-20 (post-8a.7.5 merge — external-bnpm parity + Phase 5/6-prep + clamp-fix chain)** — Five PRs landed on main in sequence: PR #41 (`b86c779`, Windows skip fix unblocking PR #42); PR #42 (`7953b97`, 8a.7.5 impl, merge commit); PR #43 (`d60e240` via `ac91771`, post-review docs); PR #44 (`d6f8e90`, external-bnpm parity finding docs + PS50 regression guard); PR #45 (`92b5d88`, Phase 5/6-prep indexing-module refactor — byte-identical move); PR #46 (`9f3378d`, clamp-fix). Each of PRs #44/#45/#46 followed the standard Phase-13-pattern narrative: identify an upstream divergence, document it in DECISIONS + MIGRATION_LOG, land a regression guard + scoped-minimum fix, preserve parity against session_processing3 baselines where unrelated paths are unaffected. Measured drift on PS46/20250307 after the clamp-fix: zero. Intentional drift on PS50/20250324 trial k=40 L-side: guarded. The forward obligation chain set by the external-bnpm finding ("clamp-fix before Phase 5/6 kickoff") is discharged. Closure stamps added to DECISIONS "External bnpm parity finding" bullet + MIGRATION_LOG Phase 5/6-prep entry. CLAUDE.md Ground Rule 8 gained a `git branch -d` subtlety clarification (the `-d` flag enforces "fully pushed to upstream", NOT "merged to main"; the latter check is the caller's responsibility) after two feature branches deleted cleanly before their PRs merged mid-session. `scratch/` + `scripts/parity_external_bnpm.py` remain local-untracked pending a gitignore vs. promote-to-scripts decision.
- **2026-04-21 (Phase 7.0b + 6.8a + 6.8a.1 + Windows first-emit kickoff + doc state refresh)** — Four meaningful merges landed between the last refresh and this one: PR #60 (Phase 7.0b cell-classification, 5 classification docs under `docs/phase-7/`, tagged `v7.0b-cell-classification`); PR #62 (Phase 6.8a trial_group translation — load-stamp verification + build_reward_aligned_analysis flag plumbing + save_reward_aligned_npz writer + notebook 12 NPZ emit + health-report script + runbook §8 additions, tagged `v6.8a-phase-5-6-trial-group-translation`); PR #64 (Phase 6.8a.1 distinct-prereq-errors — three `return None` paths in `build_reward_aligned_analysis` converted to `FileNotFoundError` with artefact-specific messages; zero-rewards path kept as `return None`; squash-merged as `00ab3b7`, tagged `v6.8a.1-distinct-prereq-errors` on the merge commit `a1844b1`). Phase 6.8a.1 was a Path B sequencing (PR-merged-before-cohort-emit) so the 14,202-failure triage would run under the distinct-error contract; Windows CC picked up the fix via a `git merge origin/main` Step 0 before kicking off the notebook 12 cohort emit. Two carry-forwards: (a) `feat/phase-6-8a-first-emit-runner` branch has 3 commits (Phase 6.8a runner, Phase 4 runner, runbook update) pending a PR once the Windows cohort run confirms the runners work — tag target `v6.8a.2-unattended-runners`; (b) PS48 2025-03-14 multi-session (two-half acquisition) handling surfaced as a new port requirement (legacy DLC code merges the two halves; new pipeline doesn't) — captured as TaskList #18 + DECISIONS 2026-04-21 entry; ungated port at two load boundaries (Phase 2 wavesurfer I/O + Phase 4+ DLC I/O). This doc refresh is the third — it closes out Phase 6.8a + 6.8a.1 in the state doc and sets Windows up to warm-start a fresh Cowork session (once Cowork-on-Windows returns) or a fresh Mac session without friction.
- **2026-04-21 (Phase 6.8a cohort first emit completion + docs PR #65 + cohort-results follow-up PR)** — Windows CC completed the first Phase 6.8a cohort emit under the distinct-error contract: 13,821 NPZs across 256 (animal, date) pairs, per-NPZ health 13,821/13,821, per-bundle health 4,605/4,608 (99.93%). The 3 failing bundles (all PS51/20250430 tongue eye_midpoint R-side in the tight -100to1000ms window) triaged to a benign skip condition — sibling wider-window passes show R rewards exist; tongue DLC likelihood falls below threshold in the tight window; `build_histogram` returns None; notebook 12's save-loop guard at line 166 skips without emitting. Verdict: no Phase 6.8a code bug; surfaces a diagnostic opportunity (the notebook conflates `result is None` with `result["histogram"] is None`) plus a task-runner pipefail bug (`| tail -80` absorbs the health-report script's non-zero exit) — both carved out as TaskList #19 for `v6.8a.3`. Docs PR #65 (`docs/phase-6-8a-1-cohort-emit-kickoff`) squash-merged as `c8db81c` with runbook §8 tightening + kickoff rewrite, but landed before the +42-line MIGRATION_LOG cohort-results diff was ready. Decision: route the cohort-results diff (MIGRATION_LOG Phase 6.8a.1 "Cohort first emit" section) + this state-doc refresh onto a new `docs/cohort-first-emit-results` branch off `c8db81c`, as a retroactive no-tag docs PR that preserves scope hygiene for PR #63 (runner-branch, tag-bearing) and PR #65 (merged).
- **2026-04-21 late (Phase 6.8a.2 runner PR + cohort-results PR both merged + state doc refresh for v6.8a.3 handoff)** — PR #66 (cohort-first-emit-results docs) merged first as intended; PR #63 (`feat/phase-6-8a-first-emit-runner`) then reconciled (branch fast-forwarded to `d901f4c` after Windows CC's local `git merge origin/main` picked up the v6.8a.1 fix) and merged as squash-commit `1f1b202`, tagged `v6.8a.2-unattended-runners`. Ordering note: Mac CC's tag sequence correctly used `gh pr view 63 --json mergeCommit` to fetch the authoritative merge SHA rather than `git rev-parse HEAD` — the latter would have tagged the wrong commit if PR #66 had merged after PR #63. PR body of #63 was updated mid-flight to reflect the actual committed filenames (`run_notebook_10_phase_4_centering.py` + `run_notebook_12_first_emit.py`, not the guessed `phase_4_unattended_runner.py` + `phase_6_8a_unattended_runner.py`) + sharper Validation section citing the full cohort results. Next: v6.8a.3 (TaskList #19) notebook-12 skip-diagnostic split + task-runner pipefail fix — small Windows CC PR, kickoff prompt included at the end of this file.
- **2026-04-22 (Phase 6.8a.3 closed — notebook 12 skip-diagnostic split + task-runner pipefail fix)** — Windows CC merged PR #68 (`fix/notebook-12-skip-diagnostic-and-pipefail`) as merge-commit `5b20dd5` (feature commit `19c3664`); tagged `v6.8a.3-notebook-12-skip-diagnostic` on the merge commit and pushed to origin. 5 files changed, +335 / −126: notebook 12 reward-loop guard split (`result is None` → `n_skip_no_rewards`, `result["histogram"] is None` → `n_skip_no_frames`, each with its own `INFO: skip_no_…` log line + a 5-counter summary print), runner-script mirror in `scripts/run_notebook_12_first_emit.py`, new `scripts/task_runner_wrapper.sh` canonical wrapper with `set -euo pipefail` defeating the `| tail -80` exit-code mask, runbook §8.4 rewrite to the current 6-bucket layout, and 3 new unit tests in `tests/test_notebook_runners.py`. Post-change pytest 464 passed / 34 skipped / 0 failed; ruff clean on touched files. PS51/20250430 reproducer reported `skip_no_frames=1 err=0` exactly as predicted by the pre-PR scope analysis — the single benign "no qualifying tongue DLC frames in the tight -100to1000ms window" skip from the 2026-04-21 cohort first emit is now surfaced as a distinct counter + log line instead of a misleading `err=1`. Three scope surprises in the Windows CC report, all captured in MIGRATION_LOG Phase 6.8a.3 "Scope surprises" section: (a) task-runner wrapper did not exist on disk as a committed file — Windows CC wrote `scripts/task_runner_wrapper.sh` from scratch as the canonical reference; existing Windows Task Scheduler / ad-hoc invocations still need manual `set -o pipefail` or to source the new wrapper; (b) the health-report script walks the on-disk NPZ tree directly so no stdout-parser contract existed to preserve — the counter-name change is stdout-only; (c) `NotebookEdit` re-serialized the reward-loop cell's `source` from a line-array to a single JSON string and normalized `\u2014` → literal `—` elsewhere in the notebook — semantically identical JSON but a larger diff than expected; pytest + PS51 verification confirm behavior is correct. Phase 6.8a arc (6.8a → 6.8a.1 → 6.8a.2 → 6.8a.3) now fully closed on main with every sub-phase tagged. Full Phase 6.8a.3 narrative is in MIGRATION_LOG. Next-phase work resumes from the "Next-phase candidates" list — top candidate is Phase 7 DLC kinematics via the existing kickoff at `docs/prompts/phase-7-dlc-kinematics-kickoff.md`.
