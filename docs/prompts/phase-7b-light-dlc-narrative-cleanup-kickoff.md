# Phase 7b-light Kickoff — DLC source narrative cleanup (module + var + docstring "reward" → "tone" rename, Case-2-discriminating)

**Branch:** `phase/7b-light-dlc-narrative-cleanup` off latest `origin/main` (post-Phase-8a.10.1 close at `dc0e6bf`, tag `v8a.10.1-tone-reward-swap-fix`).
**Tag on phase-close merge:** `v7b-light-dlc-narrative-cleanup`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 8a.10.1 closed (PR #116 merged 2026-05-14, tag pushed to origin); MICROSCOPE mount available for Task 5 spot-check.
**Estimated scope:** small-to-mid. 4 file-level changes (3 renames + 1 deletion): `dlc_spatial/reward_aligned.py` → `tone_aligned.py` source rename; `dlc_kinematics/reward_aligned.py` dead-stub deletion; `tests/test_reward_aligned.py` → `test_tone_aligned.py` test rename; `notebooks/12_dlc_spatial_reward_aligned.ipynb` → `12_dlc_spatial_tone_aligned.ipynb` notebook rename. Plus Case-2-discriminating local-var + docstring + comment sweep across ~10 DLC source files + `configs/defaults.yaml` YAML key renames + `dlc_kinematics/__init__.py` public-API rename (`build_reward_aligned_cohort` → `build_tone_aligned_cohort`) + 3-session spot-check verdict. ~12-15 source/test/config/notebook files + 3 docs files + this kickoff. Python import-site ripple is 8 files (sanity-sweep verified pre-CC handoff). ~6-10 commits, ~1-2 weeks CC wall time.

---

## Context

Phase 8a.10.1 (closed 2026-05-14, tag `v8a.10.1-tone-reward-swap-fix`) corrected a cohort-wide Tone↔Reward channel-label swap at the wavesurfer read boundary. The fix surfaced that **every DLC reward-aligned analysis was scientifically tone-anchored all along** — the auditory cue is the temporal anchor for DLC frame windows, and the pre-fix "reward" naming was a Case-2 misnomer mirroring the swapped WS channel label. This is the **Case-2 universal interpretation** locked in Phase 8a.10.1 DECISIONS Decision 1.

Phase 8a.10.1 X1-β fold-in (per kickoff Addendum #2) performed a **surgical rename at the function-call boundary** to keep cascade-safety verified within 8a.10.1's swap-fix scope:

- `dlc_spatial/reward_aligned.py:load_reward_events` → `load_tone_events`.
- 3 indirect callers updated: `dlc_kinematics/{interpolation,tongue_pertrial,mean_sem_visual}.py`.

Phase 8a.10.1 DECISIONS Q3.B explicitly **deferred deeper narrative cleanup** (module names, local variables, docstrings, comments) to Phase 7b-light. This kickoff executes that deferral.

**Scientific impact of this phase:** zero at the data level. All renames are no-ops on the byte content of pipeline outputs — the X1-β fold-in already corrected the runtime semantics. This phase is **pure narrative hygiene** so that source-code identifiers match the Case-2-corrected scientific interpretation. The spot-check verdict in Task 5 is "outputs are scientifically sensible," NOT a legacy-parity gate (legacy carries the swap; comparing against it would be misleading).

**Why now (after 8a.10.1, before 7-pre-multi-half-dlc / 7-pre-alignment-templates):** every downstream Phase 7-pre-* phase touches the DLC subtree. Building those phases on cleaned source avoids double-rename churn (rename "reward" → "tone" once here, not in each follow-on phase). Memory `project_phase_7b_light_ordering.md` locks this ordering.

**Important: on-disk cohort DLC outputs remain stale post-this-phase.** Phase 7b-light is source-only narrative cleanup. The on-disk cohort outputs at `dlc_kinematics/{features,licking_dynamics,endpoints,tongue_angle,mean_sem_visual}/...` + `dlc_spatial/heatmaps/...` were generated from pre-Phase-8a.10.1 Phase 2 NPZs (i.e., before the Tone↔Reward swap fix). Only 3 sessions (the Task 4.5 spot-check from 8a.10.1) reflect post-fix data. Phase 7b-light does NOT regenerate these cohort outputs — that is the **Phase 7c-dlc-cohort-reemit** forward-pointer (see "Findings carried forward" in Task 6 DECISIONS template), which lands after 7b-light. Downstream consumers (Phase 9 stats, pub-figures phase) wait on Phase 7c.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

**Not applicable.** This is a new-code refactor, not a legacy notebook port. No `YYYYMMDD`-suffixed candidates to disambiguate; no `_v0`/`_mod`/`_old` suffixes; no per-family date-tie scenarios. Every file touched in this phase was authored in the consolidated repo.

### Dead code identification

Walked through every "reward"-naming hit in `dlc_spatial/` + `dlc_kinematics/` (the two subtrees this phase touches). Classification:

| File | "reward" hits | Classification | Action in 7b-light |
|---|---|---|---|
| `dlc_spatial/reward_aligned.py` | 66 | Production | Rename file → `tone_aligned.py`; Case-2-discriminating local-var/docstring/comment sweep |
| `dlc_kinematics/reward_aligned.py` | 1 (docstring only) | **Dead code — never populated, zero importers** | **DELETE** (see below) |
| `dlc_kinematics/mean_sem_visual.py` | 120 | Production (X1-β indirect caller) | Case-2-discriminating local-var/docstring/comment sweep |
| `dlc_kinematics/tongue_pertrial.py` | 47 | Production (X1-β indirect caller) | Case-2-discriminating sweep |
| `dlc_kinematics/tongue_angle_cohort.py` | 38 | Production | Case-2-discriminating sweep |
| `dlc_kinematics/interpolation.py` | 29 | Production (X1-β indirect caller) | Case-2-discriminating sweep |
| `dlc_kinematics/tongue_visual.py` | 14 | Production | Case-2-discriminating sweep |
| `dlc_spatial/window_selector.py` | 12 | Production | Case-2-discriminating sweep |
| `dlc_kinematics/tongue_jaw_mismatch.py` | 12 | Production | Case-2-discriminating sweep |
| `dlc_kinematics/_angle.py` | 5 | Production (private helper) | Case-2-discriminating sweep |
| `dlc_kinematics/jaw_pertrial.py` | 4 | Production | Case-2-discriminating sweep |
| `tests/test_reward_aligned.py` | (test module) | Production | Rename file → `test_tone_aligned.py`; sync internals |
| `src/stroke_orofacial/dlc_kinematics/__init__.py` | exports `build_reward_aligned_cohort` | Production | Public-API rename: `build_reward_aligned_cohort` → `build_tone_aligned_cohort` (defined in `tongue_angle_cohort.py:1358` — Case-2 cross-session family render) |
| `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py` | hosts `build_reward_aligned_cohort` definition | Production | Function rename in lockstep with `__init__.py` re-export; sweep internal vars + docstring per Q2 |
| `src/stroke_orofacial/paths.py` | docstring references to `reward_aligned` plot family in path-resolver methods (lines 501, 641) | Production | Docstring sweep; audit for resolver method names with `_reward_aligned_` infix (Task 1 STOP-and-report if any surface) |
| `configs/defaults.yaml` | top-level `dlc_spatial_reward_aligned:` config block + `reward_aligned_display_window_ms:` parameter + `reward_aligned:` plot-family sub-keys | Production | YAML key renames in lockstep with source; backward-compat audit at Task 1 (see Q7 below) |
| `notebooks/12_dlc_spatial_reward_aligned.ipynb` | notebook filename + internal content | Production | Notebook file rename: `12_dlc_spatial_reward_aligned.ipynb` → `12_dlc_spatial_tone_aligned.ipynb`; update notebook USER INPUTS cell + orchestration cells if any reference the renamed module |
| `scripts/run_notebook_12_first_emit.py` | references the notebook by name | Production | Update notebook-filename string literal |

**Sanity-sweep verified import-graph (2026-05-14, pre-CC handoff):**

- **Python import sites for `dlc_spatial.reward_aligned` module:** 8 files (the 4 X1-β indirect callers + `tests/test_reward_aligned.py` + `tests/test_dlc_spatial_side_convention.py` + notebook 12 + `scripts/run_notebook_12_first_emit.py`). Smaller surface than the memory-estimated "~20+ import sites" — that figure likely counted individual import statements + cross-references.
- **Public API symbols to rename:** `load_reward_events` (already done in 8a.10.1 X1-β → `load_tone_events`), `build_reward_aligned_cohort` → `build_tone_aligned_cohort`, plus internal helpers per Task 1 audit.
- **Filename renames in lockstep:** 1 source module + 1 stub deletion + 1 test module + 1 notebook = 4 file-level changes (3 renames + 1 deletion).

**Dead-code rationale for `dlc_kinematics/reward_aligned.py` deletion.** The file is a 1-line docstring stub (`"""Per-reward-event kinematic windows."""`) — no functions, no classes, no imports. `grep -rn 'dlc_kinematics.reward_aligned\|from stroke_orofacial.dlc_kinematics import reward_aligned\|from .reward_aligned'` across `src/`, `tests/`, `notebooks/`, `scripts/` returns **zero hits**. Per-event kinematic work on the kinematics side is already distributed across `interpolation.py`, `tongue_pertrial.py`, `mean_sem_visual.py` (the X1-β indirect callers). The stub never had a job to do. Keeping it would be parallel-module confusion at zero benefit; renaming it to `tone_aligned.py` would create a parallel empty stub mirroring the spatial-side real module. **Recommend DELETE; document in DECISIONS as Decision 4.**

### Sub-phase breakdown

Per Task structure below. Total ~5-10 commits.

| Task | Files touched | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup | (none) | 0 | <5 min |
| Task 1 — Discovery audit | (read-only) | 0 (deliverable: scratch markdown) | 30-60 min |
| Task 2 — Module rename + stub delete | 2 source files + ~20 import sites | 1-2 | 1-2 hr |
| Task 3 — Local-var + docstring sweep | ~9 DLC source files | 2-4 | 1-2 days |
| Task 4 — Test sync | `tests/test_reward_aligned.py` → `tests/test_tone_aligned.py` + internals + other affected tests | 1 | 2-4 hr |
| Task 5 — Spot-check verdict | (read-only run; deliverable: scratch markdown + figures) | 1 (scripts only) | 1-3 days |
| Task 6 — DECISIONS + MIGRATION_LOG + state-doc | 3 docs files | 1 | 30-60 min |

### Parity strategy

**NOT a legacy-parity gate.** Phase 8a.10.1 corrected the cohort data; legacy outputs carry the swap. Comparing post-rename DLC outputs against legacy would show systematic Tone↔Reward shifts and is scientifically meaningless against post-fix data (memory `project_phase_7b_light_ordering.md`).

**Replacement: pre-rename vs post-rename byte-equality check.** Renames are pure-identifier changes; output bytes MUST be identical pre-rename and post-rename for non-withhold sessions. Withhold-bearing sessions are similarly byte-identical because Phase 8a.10.1's two-anchor `TrialRecord` model (Q-A.β: `tone_idx: int` always-present anchor + `reward_idx: int | None` optional outcome) is already in place at the function-call boundary; the rename doesn't change which trials enter the trial-record stream.

**Operational verdict bar (Task 5):**

1. **Numeric sanity (3 sessions).** Run DLC kinematics pipeline pre-rename vs post-rename on:
   - PS46/2025-03-07 (baseline bilateral session, no withholds)
   - PS54/2025-05-03 (post-stroke withhold-bearing session — 45 L + 41 R withholds per Phase 8a.10.1 Task 4.5 spot-check)
   - PS48/2025-03-14 (Pattern A multi-half; tests the merged-DLC interaction)

   Assert byte-equality on output parquet files (or numeric equivalence within `atol=1e-12` if any non-deterministic float ops surface).

2. **Eyeball verdict (3 sessions, same set).** Render DLC plot families (heatmaps from `dlc_spatial/`, kinematics traces from `dlc_kinematics/`) and confirm visual identity pre-rename vs post-rename. Eyeball-PASS / eyeball-FAIL per family.

**Failure mode.** If numeric sanity fails on any of the 3 sessions, STOP-and-report. Either (a) a rename touched something semantically (not just nominally) — bug to fix; or (b) there's pre-existing non-determinism in the DLC pipeline — separate concern, document and proceed only with Priya's adjudication.

### Hardcoded constants

None expected — this is a rename phase, not a behavior change. Task 1 audit confirms by grep-sweeping for numeric literals adjacent to "reward"-suffixed identifiers in the touched files; any surfaced literals (e.g., a window offset hardcoded near `reward_idx` reads) get logged in the scratch audit for Priya review. Default disposition: leave constants in place unless they're obviously misnamed (e.g., `REWARD_WINDOW_S = 0.5` that should be `TONE_WINDOW_S` under Case-2). Confirm at Task 1 STOP-and-report.

---

## Locked scoping decisions (Priya 2026-05-14)

### Q1 — Scope sweep — LOCKED Q1.A

Sweep `dlc_spatial/` + `dlc_kinematics/` source + `tests/test_reward_aligned.py`. `dlc_inference_o2/` + `dlc_io/` audited by Task 1 discovery (rename only if Case-2 hits surface; STOP-and-report at audit close if any do). Other top-level subpackages (`alignment/`, `spout_behavior/`, `figures/`, `reports/`, `stats/`) explicitly **out of scope** — their "reward" naming is either legacy-stamp output-key references (don't touch — Phase 2 NPZs still emit `Reward_<side>` keys post-8a.10.1 swap; that's the channel layer, not the Case-2 misnomer layer) or genuinely refers to lick-driven reward (Case 1, preserve).

### Q2 — Rename precision — LOCKED Q2.A (Case-2-discriminating)

Rename "reward" → "tone" only where scientific intent is **tone-anchoring** (event aligned to trial-start auditory cue — Case 2). Preserve "reward" where:

- It's a genuine lick-driven reward event semantic (Case 1).
- It's a NPZ-key string literal referring to the Phase 2 output key (`Reward_L` / `Reward_R` — those carry the post-8a.10.1 corrected reward channel; don't rename the keys).
- It's a Phase 8a / spout-behavior identifier referring to actual reward delivery for spout-behavior analyses.

This is the same X1-β surgical-rename policy from Phase 8a.10.1, extended to the module + local-var + docstring + comment layer. CC should err on the side of preserving "reward" when uncertain and STOP-and-ask at Task 1 audit close with a per-file resolution list.

### Q3 — Test sync — LOCKED Q3.A

Rename `tests/test_reward_aligned.py` → `tests/test_tone_aligned.py` in lockstep with the source module rename. Update test internals (variable names, parametrize IDs, fixture names, assertion messages) per the Case-2-discriminating policy. Any other test files that exercise the touched DLC source — rename per same policy.

### Q4 — Spot-check session set — LOCKED Q4.A

3-session set covering 3 trial-archetype scenarios:

- PS46/2025-03-07 (baseline bilateral)
- PS54/2025-05-03 (post-stroke withhold-bearing)
- PS48/2025-03-14 (Pattern A multi-half — tests merged-DLC interaction)

Pad to 5 if Task 1 audit surfaces unanticipated complexity (e.g., a `dlc_inference_o2/` rename that touches paths not exercised by the 3 above). Verdict criteria: dual eyeball-PASS + numeric byte-equality per session.

### Q5 — Ordering relative to 111-session YAML-cohort gap chore — LOCKED Q5.B (chore first)

**111-session YAML-cohort gap chore lands FIRST as a sibling chore-PR (~1-2 days CC work, likely half-day).** 7b-light starts after the chore-PR merges to main.

**Scope of the chore (for context — separate chore-PR, NOT part of this kickoff):** close the gap between `configs/animals.yaml`'s `sessions.start/end` per-animal date ranges and the legacy `report.json[latency_bySession]` keys across 111 sessions (formerly 126 at Phase 8a.10 close, narrowed after the baseline-date bump). Most gap-sessions are pre-cohort-launch acquisition with low scientific signal. Code change is likely date-range bumps for ~8-10 animals in `configs/animals.yaml`, not 111 individual entries.

**Rationale for chore-first:** chore is short and orthogonal to DLC source naming; doing it first keeps the queue order memory-locked from `project_phase_7b_light_ordering.md`. Phase 7b-light starts off the chore-PR's merge commit rather than off `dc0e6bf`.

**Branch base for Phase 7b-light:** `origin/main` post-chore-merge. Confirm in Task 0 — if the chore hasn't merged yet, STOP and ask Priya about ordering.

### Q6 — Dead-stub disposition — LOCKED Q6.A (delete)

Delete `dlc_kinematics/reward_aligned.py` (1-line docstring stub, zero importers). Document in DECISIONS Decision 4. Per-event kinematic work is already distributed across `interpolation.py`, `tongue_pertrial.py`, `mean_sem_visual.py`; no need for a parallel dedicated module on the kinematics side.

**Alternative considered and rejected:** rename stub to `dlc_kinematics/tone_aligned.py`. Rejected because it would create a parallel empty stub mirroring the spatial-side real module, exact same confusion hazard with a different name. If a future phase needs a kinematics-side tone-aligned module, it can be created at that time with real content.

### Q7 — YAML config-key backward compatibility — LOCKED Q7.A (no shim, hard rename)

`configs/defaults.yaml` renames in lockstep with source — `dlc_spatial_reward_aligned:` → `dlc_spatial_tone_aligned:`; `reward_aligned_display_window_ms:` → `tone_aligned_display_window_ms:`; plot-family sub-keys `reward_aligned:` → `tone_aligned:` (where Case-2-discriminating).

**No backward-compatibility shim** (no temporary alias mapping old key → new key). Rationale: this is an internal-only config; no external consumer reads `configs/defaults.yaml` outside the consolidation pipeline; and `configs/session_overrides.yaml` (if any references exist) is in the same git repo and gets updated in the same PR. Task 1 audit confirms `session_overrides.yaml` references (if any).

**Failure mode:** any out-of-tree consumer of these YAML keys breaks loudly at config-load time. Acceptable — surfaces the gap rather than hides it behind a shim.

---

## Execute on branch `phase/7b-light-dlc-narrative-cleanup`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD at `dc0e6bf` (or later if main has moved). Run `git branch --show-current` and confirm NOT on `main` (a pre-commit hook enforces this; do not bypass). Confirm `conda activate stroke_orofacial` succeeds, `which python` shows env path, `python -c "import stroke_orofacial"` exits 0, `pytest --collect-only -q` exits 0 with 1417+ tests collected (Phase 8a.10.1 baseline).

Do NOT create the feature branch yet — Task 1 first.

### Task 1 — Discovery audit (STOP-and-report)

**Goal:** Produce per-file resolution list for the Case-2-discriminating sweep before any rename lands. Avoids mid-phase re-spec when CC encounters an ambiguous "reward" identifier and has to pause.

**Steps:**

1. For each file in the Dead code table above (production rows), enumerate every "reward"-containing identifier (variable names, function names, parameter names, docstring text, comments) and classify per Q2 policy:
   - **Rename "reward" → "tone"** (Case 2 — tone-anchoring intent).
   - **Preserve "reward"** (Case 1 — genuine reward intent, OR NPZ-key string literal, OR Phase 8a / spout-behavior cross-reference).
   - **Ambiguous — STOP-and-ask** (intent unclear from local context).

2. Audit `dlc_inference_o2/` + `dlc_io/` for "reward" hits not previously enumerated. Classify each per Q2 policy.

3. Audit for numeric literals adjacent to renamed identifiers — log any surfaced constants for Priya review.

4. Audit test files that import the touched DLC source — produce list of test files needing internal-identifier sync.

5. **`configs/defaults.yaml` audit (Q7 dimension):** enumerate every `reward`-containing YAML key and classify per Q2 policy. Audit `configs/session_overrides.yaml` for any references to the soon-to-be-renamed keys. STOP-and-report list of YAML key renames + any out-of-tree consumer concerns Priya should adjudicate before Task 2 lands.

6. **Notebook 12 audit:** inventory the USER INPUTS cell + orchestration cells in `notebooks/12_dlc_spatial_reward_aligned.ipynb` for references to the renamed module + `build_reward_aligned_cohort` + YAML keys. Plan the notebook-rename + content-update commit.

7. **`src/stroke_orofacial/paths.py` audit:** confirm whether `reward_aligned` only appears in docstrings (sanity-sweep finding) or also in resolver method names / path-segment constants. STOP-and-report if any resolver-side identifier renames surface (those have broader blast radius than docstring-only).

**STOP-and-report deliverable.** Markdown summary at `.scratch_phase_7b_light/case_2_rename_audit.md`:

- Per-file rename / preserve / ambiguous tally.
- Full ambiguous-identifier list with file:line + surrounding context excerpt (3-5 lines) for Priya to adjudicate inline.
- Hardcoded constants list (if any).
- Affected test file list.
- Import-graph rendering for `dlc_spatial/reward_aligned.py` (callers of the soon-to-be-renamed module) — confirms the ~20+ import-sites estimate from memory.

**Anomaly escalation trigger:** if ambiguous count is ≥ 10, CC pauses and recommends extending Task 1 with a second pass (e.g., per-bodypart sub-grouping rules). Priya picks escalation or stays with one-by-one resolution.

Task 1 produces zero commits on the feature branch. Branch created in Task 2.

### Task 2 — File-level renames + stub deletion

**Branch:** `phase/7b-light-dlc-narrative-cleanup`, created off the chore-PR's merge commit on `main` (per Q5.B; if chore hasn't merged yet, STOP and ask Priya).

**Commit 1 — Module rename:**

- `git mv src/stroke_orofacial/dlc_spatial/reward_aligned.py src/stroke_orofacial/dlc_spatial/tone_aligned.py`
- Update all 8 Python importers (per Task 1 import-graph rendering + the sanity-sweep verified list: 4 X1-β indirect callers in `dlc_kinematics/{interpolation,tongue_pertrial,mean_sem_visual,tongue_angle_cohort}.py` + 2 tests + notebook 12 + `scripts/run_notebook_12_first_emit.py`) — `from stroke_orofacial.dlc_spatial.reward_aligned import …` → `from stroke_orofacial.dlc_spatial.tone_aligned import …`.
- DO NOT yet touch identifiers inside the renamed file — defer to Task 3 to keep this commit a pure mechanical mv + import-update.
- `pytest --collect-only` must exit 0 post-commit.
- Commit message: `refactor(phase-7b-light): rename dlc_spatial.reward_aligned → dlc_spatial.tone_aligned (Case-2 universal; module name; import sites only)`.

**Commit 2 — Stub deletion:**

- `git rm src/stroke_orofacial/dlc_kinematics/reward_aligned.py`
- Confirm no importers exist (re-run `grep -rln 'dlc_kinematics.reward_aligned\|from stroke_orofacial.dlc_kinematics import reward_aligned\|from .reward_aligned' src/ tests/ notebooks/ scripts/` returns zero).
- `pytest --collect-only` must exit 0 post-commit.
- Commit message: `refactor(phase-7b-light): delete dlc_kinematics.reward_aligned (1-line stub, zero importers; per-event kinematic work distributed across existing modules)`.

**Commit 3 — Notebook rename:**

- `git mv notebooks/12_dlc_spatial_reward_aligned.ipynb notebooks/12_dlc_spatial_tone_aligned.ipynb`
- Update `scripts/run_notebook_12_first_emit.py` notebook-filename string literal.
- DO NOT yet touch notebook USER INPUTS / orchestration cells for identifier renames — defer to Task 3.
- Commit message: `refactor(phase-7b-light): rename notebook 12 dlc_spatial_reward_aligned → dlc_spatial_tone_aligned (filename only; cell content sync deferred to Task 3)`.

**Acceptance criteria for Task 2:** `pytest -q` (full suite) PASSES at 1417+ post-Task-2 (no test count regression; renames are no-ops at runtime).

### Task 3 — Identifier + docstring + comment + YAML sweep

**Source-code files (production rows from Dead-code table, minus the file-level renames from Task 2):**

- `src/stroke_orofacial/dlc_spatial/tone_aligned.py` (post-rename; was `reward_aligned.py`)
- `src/stroke_orofacial/dlc_spatial/window_selector.py`
- `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`
- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`
- `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py` (includes `build_reward_aligned_cohort` → `build_tone_aligned_cohort` function rename)
- `src/stroke_orofacial/dlc_kinematics/interpolation.py`
- `src/stroke_orofacial/dlc_kinematics/tongue_visual.py`
- `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`
- `src/stroke_orofacial/dlc_kinematics/_angle.py`
- `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`
- `src/stroke_orofacial/dlc_kinematics/__init__.py` (public-API rename: re-export `build_tone_aligned_cohort` instead of `build_reward_aligned_cohort`; sync `__all__` list)
- `src/stroke_orofacial/paths.py` (docstring sweep; Task 1 audit confirms whether resolver method names also need rename)
- Plus any `dlc_inference_o2/` + `dlc_io/` files Task 1 surfaced.

**Config + notebook files:**

- `configs/defaults.yaml` — Q7-locked YAML key renames (`dlc_spatial_reward_aligned:` → `dlc_spatial_tone_aligned:`; `reward_aligned_display_window_ms:` → `tone_aligned_display_window_ms:`; plot-family sub-keys `reward_aligned:` → `tone_aligned:`). No backward-compat shim. Sync any `configs/session_overrides.yaml` references Task 1 surfaced.
- `notebooks/12_dlc_spatial_tone_aligned.ipynb` (post-Task-2-Commit-3 rename) — USER INPUTS cell + orchestration cells: update `build_reward_aligned_cohort` → `build_tone_aligned_cohort` calls, YAML key references, module-name references, and any docstring / markdown-cell narrative text per Case 2.

**Commit pattern (one commit per coherent group):**

1. Apply the per-file resolution from Task 1's audit:
   - Local variables (e.g., `reward_centers` → `tone_centers`, `reward_idx` → `tone_idx` where Case 2; preserve where Case 1 / NPZ-key / cross-ref).
   - Function names (Case-2-misnamed public/private functions, e.g., `build_reward_aligned_cohort` → `build_tone_aligned_cohort`).
   - Docstring text (Case 2 narrative passages → tone-anchored phrasing).
   - Inline comments (Case 2 explanations → tone-anchored).
   - YAML keys (Q7 lock — hard rename, no shim).
2. Run `pytest -q` on the affected test modules per file. PASS required before commit.
3. Commit messages: `refactor(phase-7b-light): Case-2 sweep in <file>` (one commit per file, or grouped commits like `refactor(phase-7b-light): Case-2 sweep in dlc_kinematics tongue_* family`).
4. Suggest grouping the public-API rename (`__init__.py` + `tongue_angle_cohort.py`) into a single commit so the re-export and definition stay in sync within one revision.

**Acceptance criteria for Task 3:** `pytest -q` (full suite) PASSES at 1417+. Ruff clean. `python -c "from stroke_orofacial.dlc_kinematics import build_tone_aligned_cohort"` succeeds; reverse import (`build_reward_aligned_cohort`) raises `ImportError`. YAML config loads without warnings (`python -c "from stroke_orofacial.config_loader import load_config; load_config()"` or equivalent).

### Task 4 — Test sync

**File:** `tests/test_reward_aligned.py` → `tests/test_tone_aligned.py` (lockstep with Task 2 Commit 1's source rename).

- `git mv tests/test_reward_aligned.py tests/test_tone_aligned.py`
- Update test internals per Q2 policy (var names, parametrize IDs, fixture names, assertion messages).
- Update any other test file from Task 1's affected-tests list with internal-identifier sync.
- `pytest -q tests/test_tone_aligned.py` + other affected test modules PASS.
- Commit message: `test(phase-7b-light): rename test_reward_aligned → test_tone_aligned + internal sync`.

**Acceptance criteria for Task 4:** `pytest -q` (full suite) PASSES at 1417+ (no regression). `pytest --collect-only` exits 0; test count unchanged.

### Task 5 — Spot-check verdict (STOP-and-report)

**Goal:** Confirm renames are no-ops at the output-data level on 3 trial-archetype-spanning sessions.

**Steps:**

1. **Pre-rename baseline.** Via `git stash` (or by checking out `main` locally in a sibling worktree) to restore pre-7b-light source state, run DLC kinematics + spatial pipeline on the 3 sessions (Q4-locked set: PS46/2025-03-07, PS54/2025-05-03, PS48/2025-03-14). Write outputs to `.scratch_phase_7b_light/spot_check/<animal>_<date>/pre_rename/`.

   **NOTE — invalid alternative:** an earlier draft of this task suggested using existing `pipeline_outputs/dlc_analysis/` outputs as the pre-rename baseline. That alternative is **invalid**: existing on-disk DLC outputs were generated from pre-Phase-8a.10.1 Phase 2 NPZs (swap-buggy), while a post-rename re-run consumes post-8a.10.1 Phase 2 NPZs (corrected). Even with a perfect no-op rename, post-rename outputs would differ from existing on-disk outputs because Phase 2 inputs changed underneath — the comparison would mix swap-fix effects with rename effects and couldn't isolate the rename verdict. Always snapshot the pre-rename baseline by running pre-rename code against the same (post-8a.10.1) Phase 2 inputs the post-rename run will use.

2. **Post-rename re-run.** Restore 7b-light branch state, re-run the same DLC pipeline on the same 3 sessions, writing outputs to `.scratch_phase_7b_light/spot_check/<animal>_<date>/post_rename/`. Spot-check outputs go to the scratch tree, **not** to `pipeline_outputs/dlc_analysis/` — writing to production would inadvertently produce a partial Phase 7c cohort re-emit.

3. **Numeric sanity check.** For each session, `numpy.testing.assert_array_equal` (or `assert_allclose(atol=1e-12)` if any non-determinism) on the parquet output arrays. PASS = byte-equality; FAIL = STOP-and-report.

4. **Eyeball verdict.** Render DLC plot families (heatmaps from `dlc_spatial/` + kinematics traces from `dlc_kinematics/`) for the 3 sessions, both pre-rename and post-rename. Priya eyeball verdict per family: PASS / FAIL.

**STOP-and-report deliverable.** Markdown at `.scratch_phase_7b_light/spot_check_verdict.md`:

- Per-session numeric-sanity PASS/FAIL.
- Per-session per-family eyeball verdict table.
- If any FAIL: side-by-side figure pairs + diff narrative explaining the divergence.

**Failure handling.** Numeric FAIL on any session = STOP. Eyeball FAIL on any family = STOP. Both demand Priya adjudication before Task 6.

Task 5 produces 0-1 commits (scripts only if any new scratch-driver code needed; figures not committed).

### Task 6 — DECISIONS + MIGRATION_LOG + COWORK_SESSION_STATE entries (Path Y format, no `<FILL>` placeholders)

**`docs/DECISIONS.md` new top entry:**

```markdown
## 2026-MM-DD — Phase 7b-light close — DLC source narrative cleanup (Case-2 module + var + docstring rename)

**Phase metadata.** Branch `phase/7b-light-dlc-narrative-cleanup`, opened 2026-MM-DD off main at the Phase 8a.10.1 merge commit `dc0e6bf`. Tag `v7b-light-dlc-narrative-cleanup` on the merge commit. Kickoff `docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md`.

### Decision 1 — Scope: dlc_spatial + dlc_kinematics + tests, Case-2-discriminating
[Per Q1 + Q2 lock. List touched files.]

### Decision 2 — Stub deletion: dlc_kinematics/reward_aligned.py removed
[Per Q6 lock. 1-line stub, zero importers, per-event kinematic work distributed across existing modules.]

### Decision 3 — Module rename: dlc_spatial.reward_aligned → dlc_spatial.tone_aligned
[~20+ import sites updated. Test module renamed in lockstep.]

### Decision 4 — Parity strategy: pre-rename vs post-rename byte-equality, NOT legacy parity
[Renames are no-ops at output data level. Legacy carries swap; not a valid baseline post-8a.10.1.]

### Decision 5 — Ambiguous-identifier resolutions
[Per Task 1 audit. List file:identifier → rename/preserve decisions.]

### Decision 6 — YAML-cohort gap chore ordering
[Per Q5 lock. Chore lands AFTER this phase, BEFORE 7-pre-alignment-templates / 7-pre-multi-half-dlc.]

### Enforced at
[Files list — 10-12 source/test files + 3 docs.]

### Findings carried forward
- 111-session YAML-cohort gap chore (next).
- Phase 7-pre-alignment-templates F-P-7 (cohort emit + consumer cutover from legacy tree).
- Phase 7-pre-multi-half-dlc F-P-5 (Pattern A DLC merge wiring).
- Phase 9 stats (recovery-trajectory + stat-inferential endpoints).
- Phase 7-pre-secondary-spout-compare-DLC (blocked on b-half DLC inference).
- Pub-figures phase (AnimalInfo.stroke_laterality consumer).
- Phase 7a.7 (DLC heatmaps visual gate; longstanding).
```

**`docs/MIGRATION_LOG.md` append:**

```markdown
## Phase 7b-light — DLC source narrative cleanup (Case-2 module + var + docstring rename)

**Date:** 2026-MM-DD
**Tag on merge:** `v7b-light-dlc-narrative-cleanup`
**Branch:** `phase/7b-light-dlc-narrative-cleanup`

**Scope.** Case-2-discriminating rename pass across `dlc_spatial/` + `dlc_kinematics/` source + parallel test module. Completes the Q3.B-deferred narrative cleanup from Phase 8a.10.1.

**What landed.** Module rename `dlc_spatial/reward_aligned.py` → `tone_aligned.py` (+ ~20 import sites). Dead-stub deletion `dlc_kinematics/reward_aligned.py`. Local-variable + docstring + comment sweep across ~10 DLC source files. Test module rename `test_reward_aligned.py` → `test_tone_aligned.py` + internal sync. Total ~10-12 source/test files modified + 3 docs files.

**Sessions spot-checked.** PS46/2025-03-07 (baseline bilateral), PS54/2025-05-03 (post-stroke withhold-bearing), PS48/2025-03-14 (Pattern A multi-half). All 3: numeric byte-equality PASS pre-rename vs post-rename; eyeball verdict PASS on all DLC plot families.

**Intentional behavior differences vs legacy.** None at the data level — this phase is pure narrative hygiene. Legacy outputs are not a comparison baseline post-Phase-8a.10.1 (legacy carries the Tone↔Reward swap).

**Exit criteria met.** `pytest -q` PASSES at 1417+ (no test count regression). Ruff clean. Spot-check Task 5 verdict PASS on all 3 sessions. DECISIONS + MIGRATION_LOG + COWORK_SESSION_STATE entries landed.

**Forward-pointers queued.** 111-session YAML-cohort gap chore (next). Phase 7-pre-alignment-templates F-P-7. Phase 7-pre-multi-half-dlc F-P-5. Phase 9 stats. Phase 7-pre-secondary-spout-compare-DLC (blocked). Pub-figures phase. Phase 7a.7.

**Tag:** `v7b-light-dlc-narrative-cleanup` on the merge commit.
```

**`docs/COWORK_SESSION_STATE.md` — Cowork updates separately** (Cowork drafts; Priya pastes; do NOT modify in CC session).

### Phase-close PR

**PR title:** `Phase 7b-light — DLC source narrative cleanup (Case-2 module + var + docstring rename)`

**PR body:** standard structure — phase summary, sub-phase commit list, spot-check verdict link, DECISIONS / MIGRATION_LOG links, test count delta (expected: zero).

**Post-merge obligations:**

1. `git tag -a v7b-light-dlc-narrative-cleanup <merge-sha> -m "Phase 7b-light: DLC source narrative cleanup — Case-2 module + var + docstring rename"` and `git push origin v7b-light-dlc-narrative-cleanup`.
2. Verify `git ls-remote --tags origin | grep v7b-light-dlc-narrative-cleanup` shows the tag on origin.
3. Confirm DECISIONS / MIGRATION_LOG / state-doc Path-Y entries reference tag only (no `<FILL>` placeholders). PR# + merge SHA recoverable via `git rev-list -n 1 v7b-light-dlc-narrative-cleanup` + `gh pr list --search 'v7b-light'`.

---

## Cowork ↔ CC handoff

Cowork drafted this kickoff 2026-05-14. All Q1-Q7 scoping decisions locked by Priya same day. Sanity-sweep on the import-graph verified pre-handoff (8 Python import-site files; 4 file-level renames; additional surfaces in configs/defaults.yaml + dlc_kinematics/__init__.py + tongue_angle_cohort.py + paths.py + notebook 12 + scripts/run_notebook_12_first_emit.py). Paste-ready CC handoff prompt drafted alongside this kickoff — see workspace-root `phase-7b-light-cc-handoff-prompt.md` for the copy-pasteable CC-session-opening block.

Standard CC handoff blurb (shorthand version; full version in the handoff-prompt file):

> Read `docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md` in full, then execute Tasks 0 → 6 in order. STOP-and-report at Task 1 audit close and Task 5 spot-check verdict. CLAUDE.md ground rules apply throughout (especially: never modify `main`; pre-commit hook enforces branch check; never delete legacy tree files). Phase 7b-light feature branch is created off the YAML-chore-PR's merge commit per Q5.B, NOT off `dc0e6bf` directly — STOP at Task 0 if chore hasn't landed yet.

**Mid-phase re-specs:** any mid-phase scope changes land as sequentially-numbered Addenda at the end of this kickoff (Addendum #1, #2, …) with the "ALL OTHER LOCKS UNCHANGED" footer per `feedback_iterative_addenda_pattern.md` memory.

---

## Addendum #1 — On-disk-layout strings preserved for Phase 7c (Priya 2026-05-14, post-Task-1)

CC's Task 1 audit completed (~440 "reward" hits across 14 in-scope source files + 1 config + 1 notebook + 1 script + 12 tests; ~370 unambiguous RENAME, ~50 unambiguous PRESERVE, ~20 hits collapsing to a single scoping question; AMBIGUOUS below 20-threshold; 0 hits in `dlc_inference_o2/` or `dlc_io/` Case-2 contexts; 0 resolver method names in `paths.py` using `_reward_aligned_` infix; 1 hardcoded constant `_REWARD_COLOR` at `tongue_jaw_mismatch.py:749` — identifier rename only, value unchanged; 12 test files affected; 8-importer estimate confirmed for `dlc_spatial.reward_aligned`).

CC's STOP-and-ask: does Phase 7b-light rename on-disk-layout-affecting strings (output subdir names like `spatial_reward_aligned`, window-dir tokens like `rewardAligned_100pre-1000post`, NPZ schema keys like `"n_rewards"`, family-name string tokens, CLI flag `--reward-windows-ms`, figure-filename suffixes `mouseLrewards`) in lockstep with source identifiers, OR preserve those for Phase 7c-dlc-cohort-reemit?

### Decision — PRESERVE on-disk-layout-affecting strings; bifurcate the rename across 7b-light + 7c

**LOCKED:** Phase 7b-light renames **source-side narrative identifiers only**. On-disk-layout-affecting strings are PRESERVED at their current `reward_aligned` / `n_rewards` / `rewardAligned_*` / `mouseLrewards` / `--reward-windows-ms` literals. Phase 7c (cohort re-emit) handles the on-disk rename in lockstep with re-emitting cohort outputs from corrected Phase 2 NPZs.

**Rationale:**

1. **Schema-key renames require re-emit.** If `"n_rewards"` → `"n_tones"` in code, existing NPZs on disk carry the OLD key. Either a compat-shim (defeats the rename's purpose) or re-emit (Phase 7c). Renaming the key in source without re-emit creates a runtime mismatch.
2. **Path-string renames break the Task 5 spot-check.** Task 5's verdict bar is byte-equality pre-rename vs post-rename on 3 sessions at the same paths. If output paths change, the spot-check requires manual path remapping or fresh baselines at new paths — defeats verification cleanliness.
3. **Figure filename suffix renames create on-disk inconsistency** without re-emit. Existing figures keep old suffixes; new figures get new suffixes. Mixed-suffix tree until 7c.
4. **Phase 7c is the natural moment** to switch on-disk layout — re-emit writes to new paths automatically as new code writes to new paths during cohort regeneration.

### Scope clarification — what 7b-light RENAMES (source-side narrative)

- Function names, parameter names, local + module-level variable names (`reward_centers` → `tone_centers`, etc.).
- Module file rename `dlc_spatial/reward_aligned.py` → `dlc_spatial/tone_aligned.py`; test file rename; notebook file rename; stub deletion. Per kickoff Q1, Q3, Q6 locks.
- Docstrings + inline comments (Case-2 narrative passages).
- Public-API export `build_reward_aligned_cohort` → `build_tone_aligned_cohort` (`dlc_kinematics/__init__.py` re-export + `tongue_angle_cohort.py:1358` definition).
- YAML internal config keys in `configs/defaults.yaml` per Q7 lock (consumed by code in lockstep; not on-disk-output schema).
- `_REWARD_COLOR` → `_TONE_COLOR` constant identifier rename at `tongue_jaw_mismatch.py:749`. Value `"red"` unchanged.

### Scope clarification — what 7b-light PRESERVES (on-disk-affecting; deferred to Phase 7c)

- Output subdir path components: `spatial_reward_aligned/`, any other directory names with `reward` infix that govern on-disk output tree layout.
- Window-dir tokens: `rewardAligned_100pre-1000post`-shaped strings used to build output subdir names.
- NPZ schema keys: `"n_rewards"`, `"reward_idx"` (if used as a stored key), any other `reward`-named keys in NPZ payloads.
- Family-name string tokens used in output filenames or as path keys.
- CLI flag spellings: `--reward-windows-ms` and any sibling `--reward-*` flags.
- Figure filename suffix templates: `mouseLrewards`, `mouseRrewards`, and analogous.

### Bounded inconsistency — intentional carve-out

This bifurcation creates intentional local inconsistency: inside `dlc_spatial/tone_aligned.py` (post-rename), a function like `render_tone_aligned()` will write to a path literal `spatial_reward_aligned/`. The function name reflects scientific intent (tone-anchored window); the path literal preserves on-disk layout for Phase 7c. The inconsistency is **bounded, scoped, and time-limited** — Phase 7c resolves it by renaming on-disk strings + re-emitting cohort outputs to new paths in one atomic phase.

**Documentation requirement (Task 6 DECISIONS):** the Phase 7b-light close DECISIONS entry includes a Decision titled "On-disk strings preserved for Phase 7c" that captures the bifurcation, lists the preserved string categories, and forward-points to Phase 7c for resolution.

### Edge cases — flagged for CC's attention during Task 3

- **Test assertions referencing on-disk filenames or paths.** Preserve the path strings in assertion text (matches on-disk reality); rename the test function name itself if it mentions `reward_aligned` (e.g., `test_render_reward_aligned_outputs` → `test_render_tone_aligned_outputs`).
- **Resolver methods that build paths from string fragments.** If a resolver method like `dlc_spatial_reward_aligned_path()` exists, the method name itself is source-side and renames to `dlc_spatial_tone_aligned_path()`, but the path string it constructs preserves `spatial_reward_aligned`. CC handles the source/string boundary case-by-case per this rule.
- **Notebook 12 USER INPUTS cell.** If it sets a string like `OUTPUT_SUBDIR = "spatial_reward_aligned"`, that string is PRESERVED (on-disk). But the variable name itself can rename to e.g., `TONE_ALIGNED_OUTPUT_SUBDIR` (source identifier).
- **Anywhere CC is uncertain about a specific hit**, classify as PRESERVE (conservative default) and flag in Task 1 follow-up addendum or Task 5 spot-check report.

### ALL OTHER LOCKS UNCHANGED

(Q1 scope, Q2 Case-2 discrimination, Q3 test sync, Q4 spot-check sessions, Q5 chore-first ordering [already discharged], Q6 stub deletion, Q7 YAML internal config keys [those rename normally — distinct from on-disk-output schema].)

---

## Addendum #2 — Task 5 spot-check scope reduced to PS46/2025-03-07 only (Priya 2026-05-14, post-Task-5 entry)

CC entered Task 5 and surfaced a real operational constraint that wasn't anticipated when Task 5 was drafted: `PathResolver(output_root=...)` routes BOTH reads AND writes through the override. Pipeline modules like `build_tone_aligned_analysis` read Phase 4 centered parquets via `resolver.pipeline_outputs("dlc_analysis") / centered_<mode> / animal`. An `output_root` override to `.scratch_phase_7b_light/...` makes the build function unable to find the centered parquets (which live on MICROSCOPE). The kickoff Task 5 spec's `.scratch_phase_7b_light/spot_check/` write target is unreachable without either (a) symlink-staging the production inputs into the scratch tree or (b) extending PathResolver to separate read/write roots.

### Re-scope — Option 3 adopted (eyeball-only on PS46/2025-03-07)

Three options weighed:

- **Option 1 — Full strict path:** symlink-stage centered parquets + Phase 2 NPZs + alignment templates into a scratch tree for all 3 sessions; run pre-rename + post-rename pipelines into the staged tree; byte-compare. ~3-6 hours operational. Most rigorous.
- **Option 2 — Skip session-level spot-check; pytest 1417/39/0 IS the gate.** Bifurcation guarantee + pytest gate provide pre-hoc evidence renames are no-ops at the data layer. No empirical end-to-end confirmation on real cohort data.
- **Option 3 — Eyeball-only on PS46/2025-03-07.** Run notebook 12 + cohort posts post-rename on PS46 only. Compare against existing on-disk `pipeline_outputs/dlc_analysis/` outputs — valid for PS46 because Phase 8a.10.1 Task 4.5 verified PS46's baseline pool was byte-identical pre/post swap fix (bilateral session, no withholds — swap fix is a no-op for synchronous events).

**LOCKED — Option 3.** Empirical end-to-end confirmation on PS46/2025-03-07; PS54/PS48 verification deferred per the rationale below.

### Rationale — Why PS46/2025-03-07 alone is sufficient

PS46/2025-03-07 is a **clean comparison case** for 7b-light's rename verdict specifically:

- Bilateral / no-withhold session — Phase 8a.10.1's swap fix produced byte-identical DLC outputs (Task 4.5 verified: baseline pool size 96 pre and post).
- Existing on-disk DLC outputs at this session are therefore valid pre-rename baselines (they're swap-fix-invariant + pre-7b-light-rename).
- A post-rename DLC run on PS46 can be byte-compared against existing on-disk outputs without contamination from the Phase 8a.10.1 swap-fix delta.
- Avoids the PathResolver read-routing complication entirely: run with bare `PathResolver()`, write to scratch via the sentinel-suffix workaround if needed, byte-compare to existing on-disk PS46 outputs.

### Residual scope reduction — what 7b-light does NOT verify (and why that's acceptable)

- **PS54/2025-05-03 NOT spot-checked in 7b-light.** Phase 8a.10.1 Task 4.5 already verified PS54's cascade safety under the X1-β surgical rename (baseline pool grew by exactly 86 events = 45 L-withholds + 41 R-withholds — predicted swap-fix outcome). 7b-light extends the X1-β rename to docstrings/local variables/comments per the Addendum #1 bifurcation rule; that's strictly weaker than the X1-β function-call boundary rename Task 4.5 already verified. PS54's verdict inherits.
- **PS48/2025-03-14 NOT spot-checked in 7b-light.** Phase 8a.10.1 Task 4.5 surfaced F-P-4 (PS48 Pattern A pre-existing infrastructure gaps: missing `interpolated_traces/tongue/PS48/20250314.parquet` + empty `SessionManifest.dlc_h5_files` for the multi-half merge pattern). Those gaps are upstream of 7b-light's rename scope; running the spot-check would re-encounter them without producing rename-relevant signal. Pattern A re-verification belongs to **Phase 7-pre-multi-half-dlc (F-P-5)**.
- The 3-session original spec is scientifically narrowed to 1 session on the strength of Addendum #1's bifurcation guarantee + 1417/39/0 pytest gate + Phase 8a.10.1's already-discharged Task 4.5 verdict for the other two.

### Residual risk

Low. The bifurcation rule + pytest pass + Task 4.5's prior verdict combined provide strong pre-hoc evidence that 7b-light's deeper rename is a no-op at the output-data layer. PS46's empirical PASS adds end-to-end execution confirmation on real cohort data. Phase 7c-dlc-cohort-reemit provides cohort-wide byte-equality verdict against post-rename code as a natural consequence of its re-emit step — so the comprehensive cohort verdict happens there, not here.

### ALL OTHER LOCKS UNCHANGED

(Q1-Q7 locks above; Addendum #1 bifurcation rule applies to Task 5's post-rename spot-check run.)
