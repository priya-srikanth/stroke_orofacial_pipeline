# Phase 7-pre-secondary-spout Kickoff — Pattern B closer-spout 2nd-acquisition handling

**Branch:** `phase/7-pre-secondary-spout` off latest `origin/main`.
**Tag on phase-close merge:** `v7-pre-secondary-spout`.
**Prerequisites:** MICROSCOPE mount; conda env `stroke_orofacial` active; the v7-pre-multi-half-tagged `main` HEAD (Phase 7-pre-multi-half + its production-wiring follow-up + close-out polish all merged).
**Estimated scope:** ~mid-size, comparable to Phase 7-pre-multi-half. 10-15 source/test files + 3 docs files + this kickoff.

---

## Context

Phase 7-pre-multi-half (closed 2026-05-12, tagged `v7-pre-multi-half`) handled Pattern A — multi-half acquisition where one logical session is split across two halves due to technical interruption. PS48 20250314 was the sole Pattern A session in scope; merge-intent only; coalesces into a single parent-level set of outputs.

Task 7 of that phase ran a productized cohort scan (`scripts/phase_7_pre/scan_for_multi_half_candidates.py`) and surfaced **19 sessions across PS51/PS54/PS55 with `n_dlc=1, n_ws=2, n_cam=2`** — mechanically Pattern B. Priya clarified 2026-05-09 that these are **NOT exploratory mistakes**: each is a deliberate experimental manipulation where the second acquisition (b half) was run with the water spouts positioned closer to the mouse. Scientific intent: bare-vs-b comparison for the recovery-trajectory phenotype Priya observes (animals return to closer spouts BEFORE returning to standard further-away spouts).

Currently the pipeline silently single-half-processes these sessions through the bare-`{DATE}` half; the `{DATE}b` half data is discarded. This phase fixes that.

**Architecture is mostly locked already** by [DECISIONS 2026-05-12 Decision 5](../DECISIONS.md) (four compatibility commitments) and the [Pattern B forward-pointer in the multi-half kickoff](phase-7-pre-multi-half-kickoff.md) (lines 970-1057). The phase is **audit-first** per the multi-half kickoff's framing: Task 1 walks legacy code for any existing bare-vs-b comparative analysis before any implementation lands.

---

## Cohort in scope (19 sessions, from `multi_half_scan_latest.md`)

| Animal | Date | WS dirs | n_dlc | Cam dirs | Notes |
|---|---|---|---|---|---|
| PS51 | 20250430 | `20250430`, `20250430b` | 1 | `20250430`, `20250430b` | |
| PS51 | 20250505 | `20250505`, `20250505b` | 1 | `20250505`, `20250505b` | |
| PS54 | 20250430 | `20250430`, `20250430b` | 1 | `20250430`, `20250430b` | |
| PS54 | 20250530 | `20250530`, `20250530b` | 1 | `20250530`, `20250530b` | |
| PS54 | 20250616 | `20250616`, `20250616b` | 1 | `20250616`, `20250616b` | |
| PS54 | 20250618 | `20250618`, `20250618b` | 1 | `20250618`, `20250618b` | |
| PS54 | 20250619 | `20250619`, `20250619b` | 1 | `20250619`, `20250619b` | |
| PS54 | 20250620 | `20250620`, `20250620b` | 1 | `20250620`, `20250620b` | |
| PS54 | 20250621 | `20250621`, `20250621b` | 1 | `20250621`, `20250621b` | |
| PS54 | 20250623 | `20250623`, `20250623b` | 1 | `20250623`, `20250623b` | |
| PS54 | 20250624 | `20250624`, `20250624b` | 1 | `20250624`, `20250624b` | |
| PS54 | 20250625 | `20250625`, `20250625b` | 1 | `20250625`, `20250625b` | |
| PS54 | 20250626 | `20250626`, `20250626b` | 1 | `20250626`, `20250626b` | |
| PS55 | 20250424 | **`20250424a`**, `20250424b` | 1 | `20250424`, `20250424b` | **a-suffix** on bare WS dir; cam dir is bare. Edge case. |
| PS55 | 20250428 | `20250428`, `20250428b` | **0** | `20250428`, `20250428b` | **n_dlc=0** — DLC didn't run on either half. Both halves have WS + cam; Phase 2 + Phase 3 still applicable; Phase 4 skips. |
| PS55 | 20250430 | `20250430`, `20250430b` | 1 | `20250430`, `20250430b` | |
| PS55 | 20250530 | `20250530`, `20250530b` | 1 | `20250530`, `20250530b` | |
| PS55 | 20250601 | `20250601`, `20250601b` | 1 | `20250601`, `20250601b` | |
| PS55 | 20250605 | `20250605`, `20250605b` | 1 | `20250605`, `20250605b` | |

**Weak candidates (2; OUT OF SCOPE):** PS51/20250429, PS54/20250508 — these have `n_ws=1, n_dlc=1, n_cam=2` (only camera has 2 dirs). The scan flagged them as "weak — needs manual review." Treated as single-half by the existing pipeline; this phase doesn't change that. The Task 1 audit should confirm this is the right call.

---

## Architecture commitments (locked by [DECISIONS 2026-05-12 Decision 5](../DECISIONS.md))

These four commitments are forward-binding contracts that this phase implements. Do NOT reopen them mid-phase; if any seems wrong as Task 1 audit findings come in, STOP-and-report rather than re-architecting.

**(a) `multi_half_sessions:` is merge-intent only.** Don't repurpose it for Pattern B. The new `secondary_spout_sessions:` registry is compare-intent only.

**(b) Session-id schema must allow letter suffixes.** Today `SessionManifest.session_id = f"{animal}_{date.strftime('%Y%m%d')}"`. This phase adds `session_suffix: str | None = None` to `SessionManifest` and threads it through `build_manifest()`, `PathResolver` resolvers, and output path construction. The session-id is `f"{animal}_{date_str}{suffix or ''}"`. Existing single-half + multi-half-merged sessions keep `session_suffix = None`; b-half sessions get `session_suffix = "b"`. **From this PR forward: treat `session_id` as an opaque caller-constructed string.** Audit existing code for places that bake in `{animal}_{YYYYMMDD}` exactly and fix them to round-trip through the new field.

**(c) The defensive `MultiHalfNotDeclaredError` check needs a Pattern-B branch.** When Priya eventually DLC-infers a b half (currently out of scope; see Forward-pointers), the session becomes `n_dlc=2` and trips the current defensive check. This phase implements: when `(animal, date)` is covered by `secondary_spout_sessions:`, the multi-half defensive check declines to demand a merge declaration AND refuses to merge if `multi_half_sessions:` accidentally also lists the same (animal, date) — those two registries are MUTUALLY EXCLUSIVE per (a).

**(d) Phase 2/3/4 pipelines process manifests opaquely; output separation is via session-id.** Spout-behavior (Phase 2) and alignment (Phase 3) MUST output for every manifest they receive. The manifest-construction layer (`build_manifest()`) decides whether a `(animal, date)` pair yields:
- ONE single-half manifest (the default — `session_suffix=None`), OR
- ONE multi-half-merged manifest (when in `multi_half_sessions:` — `session_suffix=None`, `halves` populated), OR
- TWO single-half manifests (when in `secondary_spout_sessions:` — one with `session_suffix=None` for bare, one with `session_suffix="b"` for b-half).

Downstream cross-session analyses filter by session-id subset. Phase 2/3/4 code stays generic.

---

## Audit-first scope (deliberate)

Per the multi-half kickoff's Pattern B forward-pointer (lines 1052-1057): "Audit-first kickoff pattern: walk the legacy code for any bare-vs-b cross-session comparison logic Priya may have, decide on registry shape, decide on session-id schema extension, port whatever comparative analyses already exist."

Task 1 walks `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` (read-only per CLAUDE.md ground rule 2) for any existing bare-vs-b analysis code and produces a STOP-and-report recommending Outcome A or B:

- **Outcome A — infrastructure-only.** Legacy has no bare-vs-b comparison code; this phase ships infrastructure (registry + session_suffix + Phase 2/3 processes both halves) and stops. A future phase ships comparison analyses.
- **Outcome B — infrastructure + port comparison analyses.** Legacy has bare-vs-b plot code or scalar analyses worth porting; this phase ships infrastructure + the ported comparison layer.
- **Outcome C — something the audit surfaces that doesn't fit A/B.** STOP and report; Priya picks scope.

The locked architecture commitments above apply regardless of Outcome.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

No direct legacy port is locked at kickoff time — the audit determines whether ports happen at all. If Outcome B materializes:
- Walk `facerhythm_stroke_biomarker_exp_Priya/analysis/` for any notebook with "b" / "closer" / "secondary" / "spout_distance" / "spout_position" / "20250430b" / similar tokens.
- Apply the 3-tier disambiguation rule (latest YYYYMMDD within a family; downstream-output mtime tiebreaker; STOP-and-ask if (1) and (2) don't resolve).
- Report findings in Task 1 STOP-and-report.

### Dead code identification

Same audit framing as 7a.3-jaw / 7a.5-mismatch: for each legacy source file candidate, classify cells/blocks as Production / Exploratory / Deprecated / Ambiguous. Only Production gets ported. Report classification in Task 1 STOP-and-report.

### Sub-phase breakdown

Per task structure below. Tasks 2-5 are roughly 1-2 commits each; Task 6 (parity) is ~3-5 commits; Tasks 7 (Outcome-B port) varies; Tasks 8-9 are 2 commits.

### Parity strategy

Three-layer live parity gate at Task 6. See "Parity gate spec" section below for layer-by-layer detail. Pre-PR baseline hashes are captured in Task 0.5 before the feature branch is created.

### Hardcoded constants to extract / scan-for

- Any place baking in `session_id = {animal}_{YYYYMMDD}` exactly (per Decision 5(b)). Audit must surface these in Task 3.
- Any file-system regex hardcoding `{YYYYMMDD}` without optional letter-suffix support.
- Any path resolver building per-session subdirs from `(animal, date)` only, ignoring `session_suffix`.

Task 1's audit produces a checklist of these for Task 3 to address.

---

## Registry shape (locked: lighter than `multi_half_sessions:`)

Per Priya's scoping decision 2026-05-12: lighter shape, mirrors `multi_half_sessions:`'s structure WITHOUT the per-half ws_subdir / cam_subdir / file_timestamp fields. The b half is discoverable from the standard `{DATE}b` subdir convention; explicit per-half metadata is only needed when the convention is broken (PS48 Pattern A used `20250314a` + `20250314b` because the merge demanded explicit ordering).

**Shape (canonical, in `configs/session_overrides.yaml`):**

```yaml
secondary_spout_sessions:
  PS51:
    - "2025-04-30"
    - "2025-05-05"
  PS54:
    - "2025-04-30"
    - "2025-05-30"
    - "2025-06-16"
    - "2025-06-18"
    - "2025-06-19"
    - "2025-06-20"
    - "2025-06-21"
    - "2025-06-23"
    - "2025-06-24"
    - "2025-06-25"
    - "2025-06-26"
  PS55:
    - "2025-04-24"  # NOTE: bare WS dir is "20250424a" not "20250424"
    - "2025-04-28"  # NOTE: n_dlc=0 (DLC didn't run on either half)
    - "2025-04-30"
    - "2025-05-30"
    - "2025-06-01"
    - "2025-06-05"
```

Each entry declares "treat this `(animal, date)` as having TWO logical sessions: a bare half AND a `b` half." The `build_manifest()` discovery layer reads both:
- Bare half: the existing `{DATE}` (or `{DATE}a` if the bare-name dir is absent — PS55/20250424 case)
- b half: `{DATE}b`

Audit (Task 1) confirms whether the YAML shape needs a richer form to cover the PS55/20250424 + PS55/20250428 edge cases. If yes, the shape may grow to:

```yaml
secondary_spout_sessions:
  PS55:
    "2025-04-24":
      bare_ws_subdir_override: "20250424a"   # only when bare dir name diverges
```

Defer the richer shape to Task 1 audit findings; the canonical lighter form above is the starting point.

---

## Execute on branch `phase/7-pre-secondary-spout`

### Task 0 — Setup

Run the warm-start checklist from `docs/COWORK_SESSION_STATE.md` in full. Confirm:
- `conda activate stroke_orofacial` succeeds; `python -c "import stroke_orofacial"` exits 0.
- `pytest --collect-only` exits 0 with no import errors.
- MICROSCOPE mounted at `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` (Windows UNC path). Confirm directories exist for PS51/20250430, PS54/20250616, PS55/20250424 (sample of the 19-session cohort).
- Local `main` is at the `v7-pre-multi-half-closeout-polish` PR merge (PR #101 or equivalent — check `git log origin/main -3`).

Do NOT create the feature branch yet — Task 0.5 captures baselines first.

### Task 0.5 — Pre-PR baseline-hash capture

**Why this lives BEFORE branch creation:** the Layer 1 parity gate in Task 6 needs SHA256 hashes of the existing single-half outputs for all 19 Pattern B sessions, captured against `main`'s current behavior (b halves discarded). Capturing post-branch risks: if any commit between branching and Task 6 accidentally changes single-half output paths or behavior, the baseline becomes "what the feature branch produces" rather than "what main produces."

**Steps:**

1. On `main` (no branch yet), create the baseline-capture script at `scripts/phase_7_pre/capture_secondary_spout_baselines.py`. Read-only script that:
   - Iterates the 19 (animal, date) pairs.
   - Runs `process_session(...)` on each with `output_root=tmp_path` (per `docs/testing-conventions.md` — no writes to real `stroke_orofacial_pipeline_outputs/`).
   - Captures SHA256 of every emitted output file (7 output types × 1 single-half output per session).
   - Writes results to `tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json` as `{(animal, date_str, output_type): sha256_hex}`.
   - Records script version + git SHA of `main` at capture time + capture timestamp.

2. Run the capture script. Verify the output JSON has 19 × 7 = 133 entries (or appropriately fewer if some output types don't apply to all sessions).

3. **Commit the baselines on `main` directly.** This is intentional — it's pure-additive test data, not a behavior change, and creating a feature branch for "add baseline JSON" introduces ordering hazards. Use commit message `chore(phase-7-pre-secondary-spout): capture pre-PR single-half output baselines on main`. Get Priya's explicit approval before pushing this commit per CLAUDE.md §"Git discipline" (no direct-to-main commits without sign-off).

   **Alternative if Priya doesn't want a direct-to-main commit:** Create a 1-commit feature branch `chore/phase-7-pre-secondary-spout-baselines` containing the baseline JSON + capture script, open a PR, merge, and ONLY THEN create `phase/7-pre-secondary-spout` off the post-merge `main`.

4. Push (or merge if the alternative was used). `main` now contains the baselines.

5. **STOP and report** after baseline-capture lands. Priya verifies the captured hashes look reasonable (no surprise zero-byte outputs, all 19 sessions present). Task 1 starts after that confirmation.

### Task 1 — AUDIT (STOP-and-report)

**Branch:** `phase/7-pre-secondary-spout`, created off the post-baseline `main`.

Walk `facerhythm_stroke_biomarker_exp_Priya/` (read-only per CLAUDE.md ground rule 2) for any existing bare-vs-b analysis code or evidence of secondary-spout handling. Specifically:

1. **Grep tokens:** `b/` (in paths), `_b\.`, `secondary_spout`, `closer_spout`, `closer-spout`, `spout_distance`, `spout_position`, `20250430b`, `compare.*bare`, `bare.*compare`.

2. **Notebook walks:** any notebook under `analysis/behavior_report/`, `analysis/dlc_analysis/`, `analysis/session_processing*/` whose date matches the Pattern B cohort.

3. **Per-cell classification** for each candidate notebook: Production / Exploratory / Deprecated / Ambiguous. Apply the 3-tier disambiguation rule.

4. **Existing scientific text:** any markdown / doc / DECISIONS-like file in the legacy repo describing the closer-spout manipulation.

5. **Hardcoded-constant scan in the consolidated repo:**
   - `grep -rn "{animal}_{date" src/stroke_orofacial/` for direct session-id construction patterns.
   - `grep -rn "date.strftime" src/stroke_orofacial/` for places that bake YYYYMMDD into a path.
   - `grep -rn "session_id" src/stroke_orofacial/` and audit each call site for Decision 5(b) compatibility.

6. **Cohort confirmation:** re-run `python scripts/phase_7_pre/scan_for_multi_half_candidates.py` and confirm the 19-session Pattern B list matches the table above. Cross-reference each (animal, date) against `configs/animals.yaml`'s `sessions.start` / `sessions.end` windows to ensure all 19 are within scope.

**STOP-and-report deliverable.** Post a Cowork-readable summary including:

- Outcome recommendation (A / B / C) with rationale.
- For Outcome A: any legacy code worth NOT porting (so it's clear nothing was missed).
- For Outcome B: per-cell classification table for the porting candidates; estimated lines / files / complexity.
- Hardcoded-constant scan results: a complete list of call sites in `src/stroke_orofacial/` that bake in `session_id = {animal}_{YYYYMMDD}` and need Task 3 fixes.
- Cohort confirmation: 19/19 sessions verified in animals.yaml windows OR list of any out-of-window sessions (which would change the count).
- Recommendation on registry-shape edge cases (PS55/20250424 a-suffix; PS55/20250428 n_dlc=0).
- Recommendation on weak-candidate handling (PS51/20250429, PS54/20250508) — confirm they stay out of scope OR move into scope.

Priya picks Outcome and confirms scope before Task 2.

### Task 2 — Registry block + cohort population

**Files:**
- `configs/session_overrides.yaml` — add `secondary_spout_sessions:` block per the canonical shape locked above. Populate 19 sessions. Include header comment citing Decision 5 + Phase 7-pre-secondary-spout.
- `configs/defaults.yaml` — add `secondary_spout:` block if needed for any tunables (e.g., `b_suffix: "b"` if Task 1 audit surfaces a reason to make the suffix configurable; otherwise hardcode).

**Tests:**
- `tests/test_session_overrides.py` (or wherever the existing registry loader tests live) — load the new block; assert all 19 sessions parse; assert mutual exclusion with `multi_half_sessions:` (no overlap with PS48 20250314 or any other Pattern A entries).

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): secondary_spout_sessions: registry block + 19-session population`.

### Task 3 — `session_suffix` threading + Pattern-B defensive-check branch

**Files (estimated; audit findings may add more):**
- `src/stroke_orofacial/manifest.py` — add `SessionManifest.session_suffix: str | None = None`; update `session_id` computed property to incorporate suffix; update `build_manifest()` to:
  - Read `secondary_spout_sessions:` from session_overrides.
  - For Pattern B sessions, return TWO manifests (bare + b) from one `(animal, date)` query, OR change the API to return a list / introduce a new `build_manifests_for_animal_date()` discovery function. Decision: pick whichever surface preserves single-half callers' expectations best. Audit Task 3.0 step recommends which.
  - Update `MultiHalfNotDeclaredError` Pattern-B branch: when `(animal, date)` is in `secondary_spout_sessions:`, the multi-half check is satisfied (separate sessions, not merge candidates). Validate `multi_half_sessions:` and `secondary_spout_sessions:` are mutually exclusive (raise `OverlappingRegistryError` or similar on conflict).
- `src/stroke_orofacial/paths.py` — every per-session path resolver that takes `(animal, date)` needs to also accept `session_suffix` and incorporate it into the directory layout. New session-output subdir convention: `{output_root}/<output_type>/{animal}/{date_str}{suffix or ""}/`. Bare halves use `{date_str}/` unchanged (backward-compatible). b halves use `{date_str}b/`.
- Hardcoded-constant fixes per Task 1's audit checklist.

**Tests:**
- `tests/test_manifest.py` — `session_suffix` field round-trips; `build_manifest()` yields two manifests for a Pattern B (animal, date) pair; mutually-exclusive registry validation raises on conflict; defensive-check Pattern-B branch tests.
- `tests/test_paths.py` — every resolver round-trips a `session_suffix` correctly; bare-suffix paths are byte-identical to pre-PR paths.

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): session_suffix field + Pattern-B branch in defensive check`.

### Task 4 — Phase 2 (spout-behavior) processes both halves

**Files:**
- `src/stroke_orofacial/spout_behavior/session_processing.py` — extend `process_session_by_animal_date()` (or wherever the per-(animal, date) entry point lives) so that when `build_manifest()` returns two manifests for a Pattern B session, both flow through `process_session()` independently. The b half emits outputs under `{output_root}/<output_type>/{animal}/{date_str}b/{date_str}b.<ext>` per the convention from Task 3.
- `src/stroke_orofacial/spout_behavior/process_animal.py` (or wherever the cohort-loop driver lives) — confirm that iterating sessions naturally picks up the new b-half manifests with no extra wiring needed.

**Tests:**
- `tests/test_session_processing_secondary_spout.py` (new) — synthetic Pattern B session fixture (two halves with distinct WS files); assert process_session yields TWO sets of outputs at the expected paths; assert bare-half output schema matches pre-PR single-half schema; assert b-half output schema matches single-half schema.

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): Phase 2 processes both halves of secondary-spout sessions`.

### Task 5 — Phase 3 (alignment) processes both halves

**Files:**
- `src/stroke_orofacial/alignment/timebase.py` — when `build_manifest()` yields two Pattern B manifests, alignment-template computation runs on both halves independently. Output: `{output_root}/dlc_analysis/alignment_templates/cam2/{animal}/{date_str}/{date_str}.npz` for bare; `{output_root}/dlc_analysis/alignment_templates/cam2/{animal}/{date_str}b/{date_str}b.npz` for b. NO MERGE (this is compare-intent, not merge-intent).

**Tests:**
- `tests/test_timebase_secondary_spout.py` (new) — synthetic Pattern B fixture; assert two separate alignment templates written; assert schema parity with single-half output.

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): Phase 3 emits separate alignment templates per half`.

### Task 6 — PARITY GATE (3-layer live)

Net-new harness at `tests/scripts/parity_phase7_pre_secondary_spout.py` (~600-800L). Three layers, exit-code-driven verdict.

**Layer 1 — Bare-half byte-identity vs Task 0.5 baselines.** For each of the 19 Pattern B sessions:
- Run `process_session(...)` on the post-PR feature-branch checkout with `output_root=tmp_path`.
- Capture SHA256 of every bare-half output file.
- Compare against `tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json`.
- **Verdict:** byte-identical for every (animal, date, output_type) triplet. Any mismatch = FAIL (signals an accidental behavior change in the single-half path).

**Layer 2 — b-half structural validation.** For each of the 19 Pattern B sessions:
- Verify the b-half output exists at the expected path: `{tmp_path}/<output_type>/{animal}/{date_str}b/{date_str}b.<ext>`.
- For licks_and_rewards NPZs: structural schema check — required keys present (`Lick_L/R`, `Reward_L/R`, `Tone_L/R`, `Fs`, `n_samples`, side-convention stamps); event arrays are 1D int; `Fs` matches the bare half's `Fs`; `n_samples` is plausible (>0, <100M).
- For alignment template NPZs: required cell-16 REQ_KEYS present; `Fs_ws_input` matches bare half's; sig_* arrays have expected shapes.
- For all output types: side-convention stamps present and match the bare half's stamps.
- **Verdict:** structurally valid for every (animal, date, output_type) triplet. Any missing file or schema failure = FAIL.

**Layer 3 — Defensive-check Pattern-B branch.** Synthetic test (no MICROSCOPE required for this layer): construct a synthetic manifest scenario where `(PS51, 2025-04-30)` is listed in BOTH `secondary_spout_sessions:` AND `multi_half_sessions:` (simulating a future operator error). Verify `build_manifest()` raises `OverlappingRegistryError` (or whatever name Task 3 picks). Verify the existing PS48 20250314 multi-half flow still works (no regression to Pattern A behavior). Verify that DLC-on-b-halves future-proofing works: simulate `n_dlc=2` on a Pattern B session and confirm `MultiHalfNotDeclaredError` does NOT fire (because the secondary-spout registry override takes precedence).

**Skip-no-legacy semantics.** N/A — Layer 1's baseline is from `main` (captured in Task 0.5), so it always exists. Layer 2 has no legacy comparison (b halves were discarded pre-PR; no legacy artifact to compare against). Layer 3 is purely synthetic.

**Verdict log:** `.scratch_phase_7_pre/parity_run_secondary_spout_{timestamp}.log`. Archive on PR merge.

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): Task 6 parity harness (3 layers)`.

### Task 7 — (Outcome B only) port bare-vs-b comparison analyses

Conditional on Task 1 audit returning Outcome B. Spec: TBD per audit findings. Likely a new module `src/stroke_orofacial/spout_behavior/secondary_spout_compare.py` consuming the per-session outputs Task 4 produces and rendering bare-vs-b comparison plots / scalars.

**Commit message pattern:** `feat(phase-7-pre-secondary-spout): port bare-vs-b comparison analyses (Outcome B)`.

### Task 8 — DECISIONS + MIGRATION_LOG entries

**Files:**
- `docs/DECISIONS.md` — new 2026-MM-DD entry consolidating the phase's decisions: registry shape (lighter), session_suffix threading, mutually-exclusive registries, Pattern-B defensive-check branch, parity strategy, Outcome A vs B verdict, Forward-pointers (DLC b-half processing, bare-vs-b comparison if deferred).
- `docs/MIGRATION_LOG.md` — new `## Phase 7-pre-secondary-spout — ...` section appended after the Phase 7-pre-multi-half entry. Capture: PR # + tag (`v7-pre-secondary-spout`) + branch + scope + what landed + parity verdict + intentional behavior differences vs legacy (the b half was previously discarded; now it's processed — this IS an intentional behavior difference, though there's no legacy artifact for the b half to compare against, so there's no "drift").

**Commit message pattern:** `docs(phase-7-pre-secondary-spout): DECISIONS + MIGRATION_LOG entries`.

### Task 9 — State-doc refresh + open PR

**Files:**
- `docs/COWORK_SESSION_STATE.md` — refresh: bump "Latest local refresh" banner; move "Phase 7-pre-secondary-spout" from Next-phase candidates (item #0) to "Recent session log" with the close-out summary; renumber subsequent candidates; refresh "Current branch" / "In flight" sections.

**Push + open PR:**
- `git push -u origin phase/7-pre-secondary-spout`
- `gh pr create --base main --head phase/7-pre-secondary-spout --title "Phase 7-pre-secondary-spout — Pattern B closer-spout 2nd-acquisition handling (PS51/PS54/PS55, 19 sessions)" --body <body>`
- PR body summarizes: the 19-session cohort, the four locked compatibility commitments honored, Layer 1/2/3 parity verdict, Task 1 audit outcome (A or B), forward-pointers.
- Squash-merge per project convention.

**Commit message pattern:** `docs(phase-7-pre-secondary-spout): state-doc refresh + open PR`.

### Tag push (post-merge)

After PR merges on `main`:
```
git tag -a v7-pre-secondary-spout <merge-sha> -m "Phase 7-pre-secondary-spout: PS51/PS54/PS55 closer-spout 2nd-acquisition handling — 19 sessions; secondary_spout_sessions: registry + session_suffix threading + Pattern-B defensive-check branch"
git push origin v7-pre-secondary-spout
```

Verify: `git ls-remote --tags origin | grep secondary-spout`.

---

## Parity gate spec (Task 6 detail)

### Layer 1 — Bare-half byte-identity

**Goal:** prove this PR does NOT change how bare halves are processed.

**Mechanism:** Task 0.5 captured `tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json` against `main`. Layer 1 re-runs the same pipeline on the feature branch and SHA256s every bare-half output, asserting byte-identity.

**Coverage:** all 19 Pattern B sessions × all 7 output types from `OUTPUT_TYPES` in `session_processing.py` (≤133 file hashes). Plus 2-3 control sessions from PS46/PS47/PS48 that are NOT in `secondary_spout_sessions:` — to catch accidental contamination of the single-half code path.

**Failure mode:** any byte-mismatch fails Layer 1. Common causes: hardcoded-constant fix in Task 3 inadvertently changed a session-id-construction call site; new `session_suffix` parameter propagation introduced an off-by-one in a path resolver; baseline-capture script disagrees with Task-time pipeline.

**Verdict:** PASS / FAIL per (animal, date, output_type). Overall PASS = all-pass.

### Layer 2 — b-half structural validation

**Goal:** prove b halves now flow through the pipeline AND produce structurally-valid outputs.

**Mechanism:** for each Pattern B (animal, date), check the b-half output exists, parses, and has expected schema. No legacy comparison (b halves were discarded pre-PR).

**Per-output-type structural checks:**

- **licks_and_rewards NPZ:** required keys (`Lick_L`, `Lick_R`, `Reward_L`, `Reward_R`, `Tone_L`, `Tone_R`, `Fs`, `n_samples`, `side_convention_version`, `wavesurfer_sides_match_mouse_sides`); event arrays 1D int; `Fs` matches bare half's; `n_samples > 0` and `< 100_000_000` (sanity); side-convention stamps match bare half's.
- **alignment_templates NPZ:** required cell-16 REQ_KEYS; `Fs_ws_input` matches bare half's; sig_* arrays non-empty.
- **(other output types as applicable per `OUTPUT_TYPES`).**

**Failure mode:** missing file, missing key, dtype mismatch, side-convention stamp mismatch with bare half, implausible scalar value.

**Verdict:** PASS / FAIL per (animal, date, output_type). Overall PASS = all-pass.

### Layer 3 — Defensive-check Pattern-B branch (synthetic)

**Goal:** prove the new defensive-check logic correctly distinguishes Pattern A (merge) from Pattern B (keep separate).

**Synthetic test scenarios:**

1. **Pattern A still works:** synthetic manifest for PS48 20250314 (declared in `multi_half_sessions:`) — verify `build_manifest()` returns ONE merge-intent manifest with `halves` populated.
2. **Pattern B works:** synthetic manifest for PS51 20250430 (declared in `secondary_spout_sessions:`) — verify `build_manifest()` returns TWO manifests, one with `session_suffix=None`, one with `session_suffix="b"`. Both have `halves=None` (single-half each).
3. **Overlapping-registry error:** synthetic state where PS51 20250430 is listed in BOTH registries — verify `build_manifest()` (or registry loader) raises `OverlappingRegistryError`.
4. **Future-DLC-on-b-half:** synthetic `n_dlc=2` for a Pattern B session — verify `MultiHalfNotDeclaredError` does NOT fire because the secondary-spout registry override takes precedence.
5. **Future-DLC-on-bare-half-only:** synthetic `n_dlc=1` for a Pattern B session (the current state) — verify `build_manifest()` yields the two single-half manifests as expected.

**Verdict:** PASS / FAIL per scenario. Overall PASS = all-pass.

### Verdict log

`.scratch_phase_7_pre/parity_run_secondary_spout_{ISO8601_timestamp}.log` archived in the PR description and `MIGRATION_LOG.md` Phase 7-pre-secondary-spout entry.

---

## Scope NOT in this phase (forward-pointers)

- **DLC processing of b halves (Phase 4).** Blocked on Priya running DLC inference on the `{DATE}b` cam dirs. The defensive check is built to handle the future `n_dlc=2` case but no production DLC-side wiring needed yet. When Priya DLC-infers the b halves, a small follow-up phase wires Phase 4 to produce b-half centered parquets per the same `session_suffix="b"` convention.
- **bare-vs-b cross-session comparison analyses.** Outcome A from Task 1 audit defers these to a future phase. (Outcome B includes them.) Whether to ship as a separate phase or fold into Phase 8a.10 (spout-behavior visual gate) or a new comparative-trajectory phase is open.
- **bnpm dep rationalization** (Finding 1 carried forward from 7-pre-multi-half). Still pending; restore script needs bnpm in the active env. Out of scope here.
- **Orphan cam{1,3,4}/PS48/20250314{a,b}.npz housekeeping** (Finding 3 carried forward). Still pending. Out of scope here.
- **Weak candidates (PS51/20250429, PS54/20250508).** Confirmed out of scope per scan note unless Task 1 audit surfaces a reason to revisit. The existing single-half discovery path handles them correctly (camera has 2 dirs but WS + DLC have 1; effectively a single-half session).

---

## File-touch allowlist

Tasks 2-6 should touch ONLY these files (paths from repo root):

```
# Source
src/stroke_orofacial/manifest.py
src/stroke_orofacial/paths.py
src/stroke_orofacial/spout_behavior/session_processing.py
src/stroke_orofacial/alignment/timebase.py

# Configs
configs/session_overrides.yaml
configs/defaults.yaml

# Tests
tests/test_manifest.py
tests/test_paths.py
tests/test_session_processing_secondary_spout.py    (new)
tests/test_timebase_secondary_spout.py              (new)
tests/test_session_overrides.py                     (or wherever the registry-loader tests live)
tests/scripts/parity_phase7_pre_secondary_spout.py  (new)
tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json  (new, created Task 0.5)

# Scripts
scripts/phase_7_pre/capture_secondary_spout_baselines.py  (new, Task 0.5)

# Docs (Tasks 8-9)
docs/DECISIONS.md
docs/MIGRATION_LOG.md
docs/COWORK_SESSION_STATE.md
```

If Task 1 audit surfaces a need to touch additional files (e.g., a hardcoded-constant call site in an unexpected module, or an Outcome-B port adds new source files), the audit STOP-and-report extends this allowlist with explicit approval from Priya before Task 2 starts.

**Out-of-scope touches that would violate this allowlist:**
- ANY edit to `src/stroke_orofacial/dlc_io/parquet.py` or `src/stroke_orofacial/dlc_kinematics/*` (DLC handling is forward-pointer-only).
- ANY edit to `src/stroke_orofacial/spout_behavior/multi_half_merge.py` or the multi-half-specific resolvers (multi-half infrastructure is locked from Phase 7-pre-multi-half).
- ANY edit to `tests/scripts/parity_phase7_pre_multi_half.py` (locked).

---

## CLAUDE.md compliance checklist

Before every commit:
- [ ] `git branch --show-current` returns `phase/7-pre-secondary-spout` (NOT `main` or `master`).
- [ ] No source data modified (CLAUDE.md ground rule 1).
- [ ] No legacy-repo files modified (CLAUDE.md ground rule 2).
- [ ] No files modified that Claude Code didn't create itself in this consolidation project (CLAUDE.md ground rule 3) — except files this same Claude Code session created on prior turns OR consolidation-repo files explicitly within the touch allowlist above.
- [ ] Outputs go to `stroke_orofacial_pipeline_outputs/` subtree, not on top of `session_processing3/` or per-animal analysis folders (ground rule 6).
- [ ] Tests using pipeline writers use `PathResolver(output_root=tmp_path)` (CLAUDE.md test convention).
- [ ] `pytest --collect-only` passes (no import errors).
- [ ] `ruff check src/stroke_orofacial/manifest.py src/stroke_orofacial/paths.py` etc. on every touched source file — ruff clean.
- [ ] Public functions have docstrings; inline comments explain *why* not *what*.

Before the phase-close PR is opened:
- [ ] Full pytest pass: target ~1024-1100 (the 7-pre-multi-half-closeout-polish baseline plus net-new tests from this phase).
- [ ] Layer 1/2/3 parity gate cleared.
- [ ] DECISIONS + MIGRATION_LOG entries match the 7-pre-multi-half format.
- [ ] State-doc refresh complete.

---

## Forward-pointers (deliberately tracked, not in this phase)

1. **Phase 7-pre-secondary-spout-compare-DLC.** Lands after Priya DLC-infers the 19 b-half cam dirs. Wires Phase 4 (centered parquet) to produce b-half outputs per the same `session_suffix="b"` convention; ports bare-vs-b DLC cross-session comparison analyses.

2. **Phase 8a.x-spout-recovery-trajectory-compare.** Whether bare-vs-b spout-behavior comparison lives here or as a fold-in to Phase 8a.10 (spout-behavior visual gate). Decide post-this-phase.

3. **`secondary_spout_sessions:` registry shape may grow** if Task 1 audit surfaces the need to handle PS55/20250424 (a-suffix bare WS dir) and PS55/20250428 (n_dlc=0) without manual overrides. The lighter shape is the starting point; the richer per-session shape is the fallback.

4. **bnpm dep + orphan cam{1,3,4} housekeeping** carried forward from 7-pre-multi-half. Still pending; orthogonal to this phase.

5. **Cohort-wide spout-behavior re-emit.** Once Phase 2 + Phase 3 produce b-half outputs, the existing cohort-emit runners need a one-time re-run to populate the new b-half output paths. Decide whether to bundle into Task 9's PR (small CC re-emit step) or carve out as a separate follow-up.

---

## DECISIONS entry sketch (for Task 8)

> **2026-MM-DD — Phase 7-pre-secondary-spout close — Pattern B closer-spout 2nd-acquisition handling for PS51/PS54/PS55 (19 sessions).**
>
> **Phase metadata.** Branch `phase/7-pre-secondary-spout`, opened YYYY-MM-DD off `main` at `<sha>` (PR #N kickoff merge). PR #M merged YYYY-MM-DD as merge-commit `<sha>`, tagged `v7-pre-secondary-spout`. Kickoff `docs/prompts/phase-7-pre-secondary-spout-kickoff.md`.
>
> **Context.** Phase 7-pre-multi-half (Decision 5) locked four compatibility commitments for a future Pattern B phase. This phase honors all four.
>
> ### Decision 1 — `secondary_spout_sessions:` registry shape
>
> Lighter than `multi_half_sessions:`: declares "this `(animal, date)` has a b half" without per-half ws_subdir / cam_subdir / file_timestamp ceremony. Standard `{DATE}b` subdir discovery suffices for 17 of 19 sessions; the 2 edge cases (PS55/20250424 a-suffix bare WS dir; PS55/20250428 n_dlc=0) are handled via Task 1 audit findings.
>
> Mutually exclusive with `multi_half_sessions:` (raise `OverlappingRegistryError` on conflict) per Decision 5(a).
>
> ### Decision 2 — `session_suffix` field threading
>
> Per Decision 5(b): `SessionManifest.session_suffix: str | None = None` threaded through `build_manifest()`, `PathResolver` resolvers, and output path construction. `session_id = f"{animal}_{date_str}{suffix or ''}"`. Bare halves use `session_suffix=None`; b halves use `session_suffix="b"`; multi-half-merged sessions use `session_suffix=None`.
>
> Existing call sites that baked in `{animal}_{YYYYMMDD}` exactly were fixed per Task 1's audit checklist (list every fixed site here).
>
> ### Decision 3 — Pattern-B branch in defensive check
>
> Per Decision 5(c): `MultiHalfNotDeclaredError` includes a Pattern-B branch — when `(animal, date)` is in `secondary_spout_sessions:`, the multi-half check is satisfied. Future DLC-on-b-half scenarios (when Priya DLC-infers the b halves and `n_dlc=2`) flow through this branch without triggering the merge requirement.
>
> ### Decision 4 — Phase 2 + Phase 3 process both halves opaquely
>
> Per Decision 5(d): `build_manifest()` for a Pattern B `(animal, date)` returns two single-half manifests (`session_suffix=None` for bare, `session_suffix="b"` for b). Phase 2 (spout-behavior) and Phase 3 (alignment) process both independently. Phase 4 (DLC) skips b halves until DLC inference runs there.
>
> ### Decision 5 — Parity strategy: byte-identity-vs-baseline + structural-validation
>
> Layer 1 byte-identity vs Task 0.5 baselines (proves bare-half path unchanged); Layer 2 structural validation on b halves (no legacy comparison; b halves were discarded pre-PR); Layer 3 synthetic defensive-check branch test. Pre-PR baseline capture on `main` BEFORE branch creation, per the 7-pre-multi-half lesson on real-pipeline-fixture forward rule.
>
> ### Outcome A vs Outcome B (audit verdict)
>
> Task 1 audit returned Outcome [A or B]. [If A: legacy has no bare-vs-b comparison code; this phase shipped infrastructure only. If B: legacy has [N] notebook(s) with bare-vs-b plots; ported as [list].]
>
> ### Enforced at
>
> [List of source / config / test / docs files per the Phase 7-pre-multi-half pattern.]
>
> ### Findings carried forward
>
> [Any new findings from Task 1 audit not already captured.]

---

## MIGRATION_LOG entry sketch (for Task 8)

> ## Phase 7-pre-secondary-spout — Pattern B closer-spout 2nd-acquisition handling
>
> **Date:** YYYY-MM-DD
> **PR:** #M
> **Tag on merge:** `v7-pre-secondary-spout`
> **Branch:** `phase/7-pre-secondary-spout`
>
> **Scope.** Add `secondary_spout_sessions:` registry honoring Phase 7-pre-multi-half Decision 5's four compatibility commitments. The 19 sessions across PS51/PS54/PS55 with closer-spout 2nd acquisitions previously had their b halves silently discarded; this phase processes both halves as separate logical sessions through Phase 2 (spout-behavior) and Phase 3 (alignment). Phase 4 (DLC) is forward-pointer only — DLC inference on b halves runs out-of-band; this phase prepares the manifest + defensive-check infrastructure for that future state.
>
> **What landed.** [Per-file changes per the 7-pre-multi-half format.]
>
> **Layer 1/2/3 parity verdict.** [Verdict log + bullet summary.]
>
> **Intentional behavior differences vs pre-PR `main`.** The b half of every Pattern B `(animal, date)` now flows through Phase 2 + Phase 3 instead of being discarded. No legacy artifact for the b half exists for comparison; structural validation only.
>
> **Exit criteria met.**
> - [ ] Layer 1 byte-identity: 19/19 sessions × N output types PASS vs Task 0.5 baselines.
> - [ ] Layer 2 structural validation: 19/19 sessions × N output types PASS on b-half outputs.
> - [ ] Layer 3 synthetic defensive-check tests: 5/5 scenarios PASS.
> - [ ] Full pytest suite green: ~1100+ passed / 38 skipped.
> - [ ] DECISIONS entry + MIGRATION_LOG entry + state-doc refresh complete.
>
> **Forward-pointers queued for future phases:**
> 1. **Phase 7-pre-secondary-spout-compare-DLC** — Phase 4 wiring + bare-vs-b DLC comparison; blocked on DLC inference of b halves.
> 2. **Phase 8a.x-spout-recovery-trajectory-compare** — bare-vs-b spout-behavior comparison (deferred from Outcome A) OR folded into Phase 8a.10.
> 3. **bnpm dep + orphan cam{1,3,4} housekeeping** carried forward.
>
> **Tag:** `v7-pre-secondary-spout` on the merge commit.
