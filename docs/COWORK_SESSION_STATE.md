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

**As of:** 2026-04-20 (Phase 8a.7.5 implementation complete on branch; PR #42 in review; one Windows-side real-data-parity skip under diagnosis; external-bnpm parity across 3 animals teed up on Mac).

**Repo phase:** Phases 1–6 + 13 + 4.5-lite + 8a.1–8a.7 delivered on `main`. Phase 8a.7.5 implemented on `phase-8a-part4-criteria-hierarchy` at `27f2432`; PR #42 open. Latest tag: `v0.8-phase-4.5-lite-eye-midpoint`. Phase 8a sub-phases after 4.5-lite have not yet been tagged — the convention has been to tag at phase-close, and Phase 8a is still mid-flight.

**Current branch:** `main` at `209acd4` (PR #40 merge). PR #42 `phase-8a-part4-criteria-hierarchy` at `27f2432` is open: 8 files changed, +1399 insertions. All relevant feature branches preserved on origin per CLAUDE.md §8.

**In flight:** **Phase 8a.7.5 criteria hierarchy port — PR #42 review.** Implementation complete on `phase-8a-part4-criteria-hierarchy`. Cowork PR review assessment: `criteria.py` clean, inline reference in `test_criteria.py` meaningfully independent from production (different data path + different window-index arithmetic + different iteration style), writer diff clean (new required `criteria` kwarg with strict validation, C1 auto-fill, slug-map drift guard, retired `CRITERIA_NOT_YET_COMPUTED_SENTINEL`), MIGRATION_LOG thorough with 3 intentional-divergence bullets, no DECISIONS divergence entry needed. **Two review gates remain:** (a) the `TestRealDataParityPS46_20250307::test_build_criteria_block_matches_inline_reference` test is skipping silently on Windows despite the SMB mount being reachable — diagnostic Windows Claude Code prompt cut 2026-04-20 to find the path-resolver vs mount mismatch; (b) external-bnpm parity across 3 different animals × 1 session each teed up as a Mac Claude Code one-off to close the "inline reference shares `(>= lo) & (< hi)` primitive with production" residual risk. Merge gated on (a) passing; (b) is hardening-not-blocker and will be rolled into the DECISIONS 2026-04-20 "Phase 8a architecture" entry if PASS-across-the-board.

**Unblockers that landed in this session (for the 8a.7.5 Windows handoff):**

- `docs/legacy_snippets/behavior_report_PS_455_551.py` — in-repo read-only excerpt of canonical `behavior_report_PS.py:385-565` (C3/C4/C34/C2/C1 + helpers) with provenance header. Avoids the Windows-side blocker where the legacy Github clone is Mac-local only. First instance of the new "legacy-snippets pattern" — see DECISIONS 2026-04-20 "Phase 8a architecture" entry.
- `CLAUDE.md` — new "Environment activation" section requiring `conda activate stroke_orofacial` + `python -c "import stroke_orofacial"` + `pytest --collect-only` before any test/impl work. Durable rule for all future sessions.
- `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` — updated to reference the legacy snippet as the canonical parity source and include the env-activation block.

**Test state (pre-8a.7.5):**

- Windows pytest (in `stroke_orofacial` env on Priya's box): **335 passed / 28 skipped / 0 failed** (reported by Claude Code end of 8a.7 session). Skip split: 22 pre-existing integration/real-data gates + 6 bnpm-importorskip gates.
- Mac pytest state last measured at Phase 13 close was 223 pass / 6 skip; Phase 8a additions (~112 new tests across 8a.1–8a.7) not yet re-verified on Mac. Full-suite Mac re-run is not blocking — Phase 8a is Windows-driven execution. Worth running on Mac opportunistically at a quiet moment.
- Pre-existing ruff warnings: 8 unused-import errors carried forward from before 8a (noted in prior Claude Code session summaries). Backlog item; not blocking.

**Next-phase candidates** (after 8a.7.5 closes):

1. **#10 remainder — Phase 8a.8** (visualization + recovery-phenotype prototype). First actual user-facing output of Phase 8a. No kickoff prompt yet; will need Cowork drafting once 8a.7.5 is done.
2. **#10 remainder — Phase 8a.9** (close-out — legacy behavior-report walkthrough rollup per Audit Item 10 Q9's "systematic walkthrough of legacy behavior_report code to match each of the 8 new endpoints to existing implementations + surface additional worth-keeping metrics + explicitly discard stale/redundant ones"). Scope TBD at 8a.8 close.
3. **#9 — Phase 6.7 SessionManifest refactor** (kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`). Unblocks #17 → #14 → #15, the main DLC-spatial queue. Can execute in parallel with 8a.8 if resources allow (both DLC-independent + orthogonal code paths).
4. **#18 — Add `sex` + `date_of_birth` to `AnimalInfo` schema + `configs/animals.yaml`.** Ungated, small. Nice to land before any Phase 9 stats work begins.
5. **#16 — Phase 5.5 polish** (SSH helper, recovery docs, ControlMaster, auto-rename, unified SVG save, DTW per-edge-shift QC plot). Ungated.

**Deferred follow-ups still pending (from earlier sessions):**

- **Cohort-wide Phase 5 re-run** (after the Phase 4.5-lite eye-midpoint centering landed — affects eye-centered outputs). Not yet scheduled; ask Priya whether to batch with 8a.8.
- **Phase 6 reward-aligned live-data re-test** with the new 4.5-lite-aware pipeline. Same category.
- **Windows housekeeping** (from Phase 13): stale admin-owned `C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini\` + `.pytest_cache\` directories — only if a future pytest run actually hits `WinError 5` again.

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

- **#10 (subtask) — Phase 8a.7.5 criteria hierarchy port — PR #42 review.** Implementation complete on `phase-8a-part4-criteria-hierarchy` at `27f2432`. Review gates:
  - *Gate A (blocker):* diagnose why `TestRealDataParityPS46_20250307` is skipping on Windows despite `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` being mapped. Windows Claude Code prompt cut 2026-04-20 — diagnostic one-liner printing `PathResolver.wavesurfer_dir(...)` output + parent-dir contents; path-mismatch vs pathlib-on-UNC-path quirk vs mount-scope mismatch; decision tree for fix. Merge of PR #42 gated on test passing (not skipping) on Windows.
  - *Gate B (hardening, not blocker):* external-bnpm parity across 3 different animals × 1 session each, Mac Claude Code one-off. Closes the "inline numpy reference shares `(>= lo) & (< hi)` primitive with production" residual risk flagged during review. Writes scratch script `scripts/parity_external_bnpm.py` (not committed), reports PASS/FAIL summary, rolls into a DECISIONS 2026-04-20 addendum entry if clean. Can run in parallel with Gate A; doesn't gate merge.
- **#10 (subtask) — `_find_idx_within_eps` indexing-module refactor (Phase 5/6 prep).** Small backlog-add surfaced during PR #42 review: factor the vendored `_find_idx_within_eps` out of `src/stroke_orofacial/spout_behavior/bouts.py:236` into `src/stroke_orofacial/indexing.py` so Phase 5/6 peri-reward-period extraction (kinematics/DLC, variable perireward windows up to 8 s) can import it without pulling from a lick-bout module. Ungated, trivial (~20 lines moved + test import updates). Run opportunistically or at Phase 5/6 kickoff.

**Completed since last state refresh:**

- **#3** — Phase 4.5-lite execution (eye-midpoint centering). Merged via PR #33 (`685d3f7`), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Post-merge validation (PR #34, `d2a928c`). Image-boundary axis-limit clamp carved out to Phase 5.x polish (PR #35). Full details in MIGRATION_LOG.md Phase 4.5-lite.
- **#10 (subtasks 8a.1 through 8a.7)** — Phase 8a criteria slug foundation + lick-bout detector + per-trial endpoint primitives + within-session / inter-session / engagement-extras endpoints + per-session JSON writer with schema 2.0.0. Merged via PRs #36, #37, #38 and the housekeeping / kickoff / unblock follow-ups #39 + #40. Full details in MIGRATION_LOG.md Phase 8a.7 entry + DECISIONS.md 2026-04-20 "Phase 8a architecture" entry.
- **#13** — Phase 13 env unification + bnpm vendoring. Full details in MIGRATION_LOG.md Phase 13 (sub-phases 13a + 13b) and DECISIONS.md 2026-04-19 + 2026-04-20 entries. Merged to main as `d031486`, tagged `v0.7-phase-13-env-unification`. Feature branch `phase-13-env-unification` preserved on origin.
- **#8** — Audit branch `audit-item-6-phase5-details` merged to `main` and tagged `v0.6.5-audit-complete`. Branch preserved as permanent reference per CLAUDE.md rule 8.

**Pending — queued phases and mini-phases**, in rough execution order (dependencies noted):
- **#10 (subtask) — Phase 8a.7.5 criteria hierarchy port.** In progress (above). Next-up execution on Windows.
- **#10 (subtask) — Phase 8a.8 recovery-trajectory visualization + phenotype-classification prototype.** Blocked on 8a.7.5. Needs Cowork-drafted kickoff prompt once 8a.7.5 merges.
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

---

## Best warm-start prompt (paste into a new Cowork chat)

Phase 8a.7 is closed (merged as `65d8917`). Phase 8a.7.5 (criteria hierarchy port: C3/C4/C2 real; C1 stays sentinel) is teed up to execute on Windows — kickoff at `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md`. Follow-up PR #40 (`209acd4`) landed the env-activation rule, the kickoff's env block, and `docs/legacy_snippets/behavior_report_PS_455_551.py` so Windows parity validation is unblocked. Use this prompt to open the next Cowork session:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Phase 8a.7.5 (criteria hierarchy port) is queued for Windows Claude Code execution; the kickoff prompt and legacy-snippet unblocker are in place (merged as `209acd4` via PR #40). I want to [drive 8a.7.5 execution from the Cowork side / draft the 8a.8 kickoff / pick another task]. Confirm the current state and then ask me which direction before doing anything else.

The generic warm-start once you've moved past the in-flight work:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Then ask me what we're working on.

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge.
- **2026-04-19** — Major refresh at end of multi-day session. Audit progressed from 6/10 to 9/10 items resolved; Phase 4.5-lite decision locked; several new tasks created (#14, #15, #16, #17); Cowork-on-Windows permanently deferred; `docs/SCIENTIFIC_ENDPOINTS.md` created with Q1–Q10 for next session. Transcribed all session decisions into DECISIONS.md. Next expected update: after Item 10 Q1–Q10 discussion completes.
- **2026-04-19 (audit closure)** — Walked Q1–Q10 with Priya in a focused second session the same day; all 10 decisions landed as a single grouped entry at the top of DECISIONS.md. Audit now 10/10. Phase 9 split into 9a/9.1/9b; task #12 refactored into #12a–e; new tasks #18 (sex/DOB schema) and #19 (facerhythm_tca stub) created; task #16 extended with DTW per-edge-shift QC plot carve-out; task #10 and #11 scopes expanded with locked Phase 8a/7 content. Next session opens with audit merge (#8).
- **2026-04-19 (Phase 13 drafting)** — Third session same day. Audit branch merged to `main`, tagged `v0.6.5-audit-complete`. Feature branch `phase-13-env-unification` cut from `main`. Full import audit performed across `src/`, `tests/`, `notebooks/`, and `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` to determine the minimum dep set for the new unified env. Drafted `environment.yml` (single env, Python 3.11, conda-forge primary, `bnpm[core]`). Added `patsy`, `pot`, `scicomap` (in-flight-port prereqs). Dropped `opencv-contrib-python` and `tqdm` (audit confirms zero imports). Brought `pyproject.toml` into agreement. Reduced old per-platform env files to deprecation stubs. Cowork context compacted mid-session (summary preserved). Windows test-env install was still spinning on jinja2 at session end — resolution deferred to next session.
- **2026-04-20 (Phase 13 closure)** — Windows env couldn't import bnpm because the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` that collides with conda-forge MKL's `libomp.dll` (`OMP: Error #15` + `WinError 127` on `shm.dll`). Resolved by vendoring the 4 pure-numpy bnpm helpers the repo actually uses into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT attribution and dropping `bnpm[core]` + `numba` + `cmake` from the env. Two vendored helpers intentionally diverge from upstream bnpm 0.6.0 to fix off-by-one bugs discovered while writing parity tests; drift measured (0 / 2 / 51 / 0 per-array on PS46/20250307 terminal masks; scope downstream: none). Full Mac + Windows verification green (Mac 223/6/0; Windows 201/28/0). PR #31 merged to main as `d031486`; tag `v0.7-phase-13-env-unification` pushed; feature branch preserved on origin. README + DESIGN.md §§2.3/3/8 + MIGRATION_LOG.md 13a+13b + DECISIONS.md 2026-04-19 + 2026-04-20 all written/reframed to reflect the unified env and the vendor-plus-bug-fixes narrative. All three next-phase candidates (#3 / #9 / #10) unblocked.
- **2026-04-20 (Phase 4.5-lite + Phase 8a.1 through 8a.7 + 8a.7.5 prep)** — Multi-session sweep executed predominantly on Windows Claude Code with Cowork-on-Mac providing advisory + kickoff-drafting + session-state maintenance. Phase 4.5-lite eye-midpoint centering merged (PR #33 + #34 + #35), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Phase 8a sub-phases 8a.1 (slug foundation, PR #36), 8a.2–8a.6 (bout detector + per-trial primitives + within-session / inter-session / engagement-extras endpoints, PR #37), and 8a.7 (JSON writer + schema 2.0.0 with sentinel criteria, PR #38) all landed. `_v2` suffix dropped from file / config / kwarg / test-fixture names (`a41b643`); frozen historical docs retain `_v2` as decision-trail context. Phase 8a.7.5 kickoff prompt saved as first-class repo artifact (PR #39). Follow-up PR #40 bundled three changes: new "Environment activation" durable rule in CLAUDE.md, mirror of the env-activation block into the 8a.7.5 kickoff, and new `docs/legacy_snippets/behavior_report_PS_455_551.py` establishing the legacy-snippets pattern (unblocks Windows byte-identical parity validation for the 8a.7.5 port without the legacy Github clone being present locally). DECISIONS.md 2026-04-20 "Phase 8a architecture" entry captures criteria slug finalization (fulfills Q2), 8a sub-phasing, schema 2.0.0 design, 8a.7.5 split rationale, `_v2` drop, and the legacy-snippets pattern.
- **2026-04-20 (Phase 8a.7.5 implementation + PR #42 review)** — Windows Claude Code completed the 8a.7.5 port on `phase-8a-part4-criteria-hierarchy` at `27f2432`: 8 files changed, +1399 insertions, full suite 361 passed / 28 skipped, ruff clean. PR #42 opened. Cowork PR review in one continued session: inline-reference independence verified (different data path, different window-index arithmetic, different iteration style vs production); writer diff clean with no external callers broken; MIGRATION_LOG thorough. Two review gates opened: (a) `TestRealDataParityPS46_20250307` skipping silently on Windows despite mapped SMB mount — Windows Claude Code diagnostic prompt cut with decision-tree fix guidance (merge blocker); (b) external-bnpm parity across 3 animals × 1 session each as a Mac Claude Code one-off — hardening-not-blocker, results roll into DECISIONS 2026-04-20 addendum if clean. Side discovery during review: `find_idx_within_eps` audit across both legacy repos confirms `find_peri_reward_periods.py` (Priya) and `find_peri_reward_and_tone_periods.py` (Rich) each inline their own copy — no new vendoring needed for Phase 5/6 kinematics/DLC perireward windows. Backlog-add: factor `_find_idx_within_eps` out of `bouts.py` into `src/stroke_orofacial/indexing.py` (Phase 5/6 prep, trivial).
