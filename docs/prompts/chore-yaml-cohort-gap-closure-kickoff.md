# Chore-PR Kickoff — YAML cohort-gap closure (F-P-6, 111-session diff vs legacy `report.json`)

**Branch:** `chore/yaml-cohort-gap-closure` off latest `origin/main` (post-Phase-8a.10.1 close at `dc0e6bf`, tag `v8a.10.1-tone-reward-swap-fix`).
**Tag on merge:** `vchore-yaml-cohort-gap-closure` (optional — chore-PRs don't strictly require tags per CLAUDE.md, but a permanent reference is useful for the F-P-6 forward-pointer discharge; Priya confirms at PR-merge time).
**Prerequisites:** conda env `stroke_orofacial` active; Phase 8a.10.1 closed (PR #116 merged 2026-05-14); MICROSCOPE mount available (read-only — Task 1 reads legacy `report.json` files for the diff).
**Estimated scope:** small. 0-2 source/config files modified + 2 docs files (DECISIONS + MIGRATION_LOG) + this kickoff. Most of the work is Task 1 audit + Task 2 Priya adjudication on per-session disposition. ~3-5 commits, ~half-day to 1 day CC wall time (depending on adjudication pace).

---

## Context

Phase 8a.10 DECISIONS Decision 6 (2026-05-13) surfaced a discrepancy between `configs/animals.yaml` `sessions.start`/`end` ranges (the consolidated pipeline's cohort definition) and legacy `analysis/basic_behavior_analysis3/<mouse>/report.json[latency_bySession]` keys (the legacy pipeline's session list). 126 sessions appeared in legacy `report.json` but fell outside the YAML range. Most gap-sessions are pre-cohort-launch acquisition (low scientific signal).

Phase 8a.10's mid-phase commit `6070266` ("bump baseline start date to 2025-04-21 for PS51/54/55") tightened 3 animals' starts and partially closed the gap. The residual is **111 sessions** as of the Phase 8a.10.1 close DECISIONS F-P-6 — superset scope spanning **Cohort A + Cohort B** YAML ranges vs legacy `report.json` session keys for the same animals.

**Why now:** Phase 7b-light (next substantive phase per memory `project_phase_7b_light_ordering.md`) is independent of the cohort registry — neither extending nor narrowing the cohort affects 7b-light's source-rename scope. Running the chore first (per Q5.B lock in the 7b-light kickoff) closes F-P-6 cheaply before downstream phases (Phase 7c-dlc-cohort-reemit, Phase 7-pre-alignment-templates) that DO depend on the canonical cohort definition. Two reasons to land it now rather than later:

1. F-P-6 has aged through 4 phase-close cycles (Phase 8a.10 → 8a.10.1 → "next chore"). One more deferral risks it aging further.
2. The chore is small (half-day) and orthogonal — running it as a focused chore-PR is operationally simpler than bundling into a follow-on phase.

**Scientific impact:** The chore's outcome shifts the canonical cohort definition. After the chore lands:
- **If gap sessions are INCLUDED** (YAML range extended): downstream re-emits + visualizations expand by ~up-to-111 sessions per affected animal. Most are below criteria_performance floor, so most plots gain "pre-criterion" days at the leading edge.
- **If gap sessions are EXCLUDED** (YAML range stays, gap explicitly documented): the YAML is the authoritative cohort definition; legacy `report.json` keys outside the YAML are documented as out-of-scope. No downstream churn.
- **Hybrid (per-session adjudication):** likely the right answer for most sessions, mixed include/exclude based on per-session criteria.

Phase 8a.10 Decision 6 went with path (b) DEFERRED ("treating the YAML range as the authoritative cohort definition for this phase"). This chore revisits that decision and produces the canonical adjudication.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements" — light version for chore-PR)

### Legacy file disambiguation

Not applicable — chore touches `configs/animals.yaml` + `configs/session_overrides.yaml` (consolidated pipeline files) and reads-only from legacy `report.json` (single canonical source per animal under `analysis/basic_behavior_analysis3/<mouse>/`).

### Dead code identification

Not applicable — config-only chore. No source code or test code modified.

### Sub-phase breakdown

Per Task structure below. Total ~3-5 commits.

| Task | Files touched | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup | (none) | 0 | <5 min |
| Task 1 — Diff audit (STOP-and-report) | (read-only; deliverable: scratch markdown + JSON) | 0 | 30-60 min |
| Task 2 — Priya adjudication | (none — interactive) | 0 | 1-3 hr (Priya pace) |
| Task 3 — YAML edits | 1-2 config files | 1-2 | 30-60 min |
| Task 4 — Diff re-verification | (read-only; deliverable: scratch markdown) | 0 | 15 min |
| Task 5 — DECISIONS + MIGRATION_LOG entries | 2 docs files | 1 | 30-60 min |

### Parity strategy

**Not applicable in the legacy-parity-gate sense** — this is a config-only chore; no analysis outputs change as a result. The chore's verdict is the diff-count: after Task 3 lands, Task 4 re-runs Task 1's diff and expects either zero gap (all 111 sessions included) or a count matching Task 2's explicit exclusions (with each excluded session documented in DECISIONS).

### Hardcoded constants

None. The cohort definition itself IS the constant being adjusted.

---

## Locked scoping decisions (Priya 2026-05-14, pending confirmation at Task 2)

### Q1 — Disposition policy — DEFAULT Q1.A (per-session adjudication; see Task 2)

Per-session include / exclude decision. Default heuristic for Task 1 PROPOSAL (Priya overrides at Task 2):

- **Propose INCLUDE** if the legacy `report.json[latency_bySession]` entry for that session indicates the animal passed criterion 3+ (or the equivalent criteria-performance threshold used by the existing cohort definition).
- **Propose EXCLUDE** if the session is pre-cohort-launch acquisition (day-of-life timing puts it before standard baseline-training onset), pilot / habituation day, or visibly below the criteria_performance floor.
- **Propose AMBIGUOUS** (STOP-and-ask) for everything else.

Priya overrides at Task 2 with per-session lock. The Task 1 audit produces the proposal table; Task 2 produces the lock table.

### Q2 — YAML edit mechanism — LOCKED Q2.A (range extension preferred; per-session lists fallback)

**Preferred:** extend `sessions.start`/`end` per-animal in `configs/animals.yaml` (Cohort A) and add explicit entries to `secondary_spout_sessions:` (Cohort B). This is the simplest mechanism and matches the YAML's current per-animal-range convention.

**Fallback:** if the include-disposition is non-contiguous (e.g., "include 2025-03-05 but exclude 2025-03-06"), use an explicit `excluded_dates:` list at the animal level. The current `configs/animals.yaml` schema doesn't have this field; if Task 2 surfaces non-contiguous cases, propose the schema extension at that time.

**Cohort B mechanism:** Cohort B (`secondary_spout_sessions:` in `configs/session_overrides.yaml`) is already per-(animal, date) explicit. Gap closure means adding new dated entries with optional subdir overrides — same convention as the existing 24 entries.

### Q3 — Tagging — DEFAULT Q3.A (tag on merge; can decline at PR-merge time)

Tag the merge commit as `vchore-yaml-cohort-gap-closure` for permanent reference. CLAUDE.md's "every phase-close PR gets a tag" rule applies strictly to phases; chore-PRs are optional. Pro-tag: F-P-6 discharge is a coherent unit of work and tagging makes it referenceable in future state-doc + DECISIONS entries. Con-tag: chore-PRs are routine and could clutter the tag list.

**Default: tag on merge.** Priya can decline at PR-merge time.

### Q4 — PS52 / PS53 disposition — LOCKED Q4.A (out-of-scope; report only)

`scripts/.scratch_phase_8a_10/inspect_report_json.py` audits PS46-PS55 inclusive; PS52 + PS53 are NOT in the cohort (not in `configs/animals.yaml`). If Task 1 surfaces `report.json` data for PS52 / PS53, document it in the audit as "out-of-cohort, no action" and proceed. Do NOT add PS52 / PS53 to the YAML — that would be an unrelated scope expansion.

### Q5 — Cohort B scope — LOCKED Q5.A (in scope; same diff logic)

Cohort B (secondary-spout sessions in `configs/session_overrides.yaml`, 24 entries across PS51/54/55) is in scope per the F-P-6 "superset" language at Phase 8a.10.1 close. Diff: each (animal, date) in legacy `report.json[latency_bySession]` for PS51/54/55 that's NOT in `secondary_spout_sessions:` (and is also outside the Cohort A range for that animal — those are Cohort A inclusion candidates already, not Cohort B). The Cohort B diff is the residual after subtracting Cohort A coverage.

### Q6 — Source-of-truth conflict resolution — LOCKED Q6.A (legacy report.json is the gap-audit source; YAML is the authoritative cohort post-chore)

For Task 1's diff, the legacy `report.json[latency_bySession]` keys are the "what sessions actually exist" reference. The YAML is "what sessions the consolidated pipeline currently knows about." The chore reconciles them. Post-chore, the YAML is the single source of truth and `report.json` becomes a frozen legacy reference (not consulted by the consolidated pipeline at runtime — and was never consulted, only used for this audit).

---

## Execute on branch `chore/yaml-cohort-gap-closure`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD at `dc0e6bf` (or later if main has moved). Confirm `conda activate stroke_orofacial` succeeds, `python -c "import stroke_orofacial"` exits 0. Confirm MICROSCOPE mount accessible (`ls "/Volumes/Neurobio/MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp/analysis/basic_behavior_analysis3/" | head` returns animal subdirs).

Do NOT create the feature branch yet — Task 1 is read-only and produces a STOP-and-report.

### Task 1 — Diff audit (STOP-and-report)

**Goal:** Produce the canonical 111-session gap list with per-session proposed disposition (INCLUDE / EXCLUDE / AMBIGUOUS per Q1.A heuristic).

**Reference script:** existing `.scratch_phase_8a_10/inspect_report_json.py` reads `report.json` per animal. Re-use the pattern; extend if needed.

**Steps:**

1. For each animal in Cohort A (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55), load `analysis/basic_behavior_analysis3/<animal>/report.json` and extract `latency_bySession` keys (the session date list).
2. For each animal, compute the diff: dates in `latency_bySession` NOT covered by:
   - `configs/animals.yaml` `<animal>.sessions.start <= date <= <animal>.sessions.end`
   - `configs/session_overrides.yaml` `secondary_spout_sessions[<animal>][date]` (Cohort B)
3. For each gap (animal, date), pull contextual data from `report.json`:
   - Criterion-passing flags (criteria_3, criteria_4, etc. — whatever the legacy report tracks).
   - Trial count (rough proxy for whether the animal was engaged).
   - Day-of-life timing (animal's date_of_birth + first-cohort-day baseline).
4. Apply Q1.A heuristic to propose INCLUDE / EXCLUDE / AMBIGUOUS for each gap session.
5. For Cohort B animals (PS51 / PS54 / PS55), distinguish gap sessions that fall inside the Cohort A range (Cohort A inclusion candidates) from those that match the Cohort B pattern (closer-spout sessions, would expand `secondary_spout_sessions:`). Separate proposal tables.

**Anomaly handling:**

- PS52 / PS53 `report.json` data: Q4.A — report only, no action.
- Animals with missing or unparseable `report.json`: STOP-and-report (this is a data-availability issue unrelated to the gap).
- Sessions where `report.json` entries indicate corruption (e.g., zero trials, parse errors): flag in the audit, recommend EXCLUDE.

**STOP-and-report deliverable.** Two artifacts at `.scratch_chore_yaml_cohort_gap/`:

1. `gap_audit_proposal.md` — human-readable per-animal table:

   ```
   ## PS46 — current YAML range: 2025-03-07 to 2025-04-06
   
   Gap sessions (in report.json, outside YAML range):
   
   | Date | Day-of-life | Criterion-3 | Trials | Proposed | Rationale |
   |------|-------------|-------------|--------|----------|-----------|
   | 2025-02-28 | 95 | False | 14 | EXCLUDE | Pre-cohort-launch acquisition, sub-floor trial count |
   | 2025-03-05 | 100 | True | 156 | INCLUDE | Criterion passed; 2 days pre-current-YAML-start |
   | ...
   
   Suggested YAML edit if accepting all proposals:
     sessions:
       start: 2025-03-05   # was: 2025-03-07
       end: 2025-04-06     # unchanged
   ```

2. `gap_audit_raw.json` — machine-readable per-(animal, date) record for reproducibility:

   ```json
   {
     "PS46": {
       "yaml_range": ["2025-03-07", "2025-04-06"],
       "gap_sessions": [
         {"date": "2025-02-28", "day_of_life": 95, "criteria_3": false, "n_trials": 14, "proposed": "EXCLUDE", "rationale": "..."}
       ]
     },
     ...
   }
   ```

**Anomaly escalation trigger:** if AMBIGUOUS count is ≥ 20 (~18% of 111), recommend Priya splits the chore into a multi-pass adjudication (e.g., Pass 1 = clear INCLUDE/EXCLUDE; Pass 2 = AMBIGUOUS via richer criteria like manual cohort-launch-day inspection).

Task 1 produces zero commits.

### Task 2 — Priya adjudication

**Goal:** Convert Task 1's per-session proposals into locks.

**Mechanism:** Priya reviews `gap_audit_proposal.md` and either (a) accepts the proposal table as-is, (b) edits per-session dispositions inline, or (c) requests Task 1 re-run with different heuristic (e.g., "include all post-day-95-of-life sessions regardless of criteria_3").

**Lock format.** Priya produces or annotates a final adjudication table — same shape as Task 1's proposal table, with the "Proposed" column replaced by "LOCKED" and "Rationale" optionally edited. Lives at `.scratch_chore_yaml_cohort_gap/gap_audit_locked.md`.

**Wall time estimate:** 1-3 hr depending on AMBIGUOUS count and Priya's per-session review pace.

Task 2 produces zero commits.

### Task 3 — YAML edits

**Branch:** `chore/yaml-cohort-gap-closure`, created off latest `main`.

**Commit pattern:**

- **Commit 1 (Cohort A edits, if any):** `chore(yaml-cohort-gap): extend animals.yaml sessions ranges per F-P-6 adjudication` — bumps per-animal `sessions.start`/`end` per Task 2 locks. Inline comment per edited animal referencing this chore's DECISIONS entry. If non-contiguous include/exclude surfaces, escalate to Q2.A fallback (add `excluded_dates:` field with schema extension; surface as STOP-and-ask before commit).
- **Commit 2 (Cohort B edits, if any):** `chore(yaml-cohort-gap): extend secondary_spout_sessions per F-P-6 adjudication` — adds per-(animal, date) entries to `configs/session_overrides.yaml` `secondary_spout_sessions:`. Mirrors existing-entry format (with optional subdir overrides if the Task 2 lock specifies any).
- **Acceptance criteria for Task 3:** `pytest -q tests/test_animals.py tests/test_session_overrides.py` (or whichever tests exercise YAML load) PASS. `python -c "from stroke_orofacial.animals import load_animals; load_animals()"` exits 0. `python -c "from stroke_orofacial.manifest import load_secondary_spout_sessions; load_secondary_spout_sessions()"` exits 0.

### Task 4 — Diff re-verification

**Goal:** Confirm post-edit YAML matches Task 2's adjudication.

**Steps:**

1. Re-run Task 1's diff audit script against the post-edit YAML.
2. Expected outcome: zero gap sessions remain INCLUDED-but-not-in-YAML; explicit EXCLUDED list matches Task 2 locks.

**Failure mode:** any mismatch → STOP, report which Task 2 locks didn't propagate to the YAML correctly. Fix in Task 3 follow-up commit.

**Deliverable:** `.scratch_chore_yaml_cohort_gap/post_edit_verification.md` — short markdown confirming zero unresolved gap + listing the locked-EXCLUDED set as the documented out-of-scope cohort.

Task 4 produces 0-1 commits (only if a Task 3 follow-up fix is needed).

### Task 5 — DECISIONS + MIGRATION_LOG entries

**`docs/DECISIONS.md` new top entry (Path Y format — no `<FILL>` placeholders):**

```markdown
## 2026-MM-DD — Chore: YAML cohort-gap closure (F-P-6 discharge)

**Chore metadata.** Branch `chore/yaml-cohort-gap-closure`, opened 2026-MM-DD off main at the Phase 8a.10.1 merge commit `dc0e6bf`. Tag `vchore-yaml-cohort-gap-closure` on the merge commit (if Q3.A confirmed at merge). Kickoff `docs/prompts/chore-yaml-cohort-gap-closure-kickoff.md`. F-P-6 forward-pointer (from Phase 8a.10.1 close) discharged by this chore.

### Decision 1 — Diff source-of-truth and audit method
[Per Q6.A. Reference Task 1 audit method, legacy report.json paths.]

### Decision 2 — Disposition policy applied
[Per Q1.A heuristic + Q2 adjudication outcome. Summarize per-session adjudication count: N INCLUDED, M EXCLUDED, K ambiguous resolved manually.]

### Decision 3 — YAML edit mechanism
[Per Q2 lock. Range extension counts per animal; per-session lists added (Cohort B). Schema extensions if any.]

### Decision 4 — PS52 / PS53 out-of-cohort confirmation
[Per Q4.A. Document report.json data exists but is out-of-scope.]

### Decision 5 — Post-chore cohort totals
[Cohort A: per-animal session-count delta. Cohort B: total session-count delta. Combined cohort size after chore.]

### Enforced at
- `configs/animals.yaml` (per Q2.A Commit 1 if any).
- `configs/session_overrides.yaml` (per Q2.A Commit 2 if any).
- `.scratch_chore_yaml_cohort_gap/gap_audit_locked.md` (audit-trail; not committed to git but referenced by SHA at merge time if needed).

### Findings carried forward
- (none expected; F-P-6 discharge is the chore's product. If Task 2 adjudication surfaces unanticipated cohort-definition questions, document as forward-pointers here.)
```

**`docs/MIGRATION_LOG.md` append:**

```markdown
## Chore — YAML cohort-gap closure (F-P-6 discharge)

**Date:** 2026-MM-DD
**Tag on merge:** `vchore-yaml-cohort-gap-closure` (if Q3.A confirmed at merge)
**Branch:** `chore/yaml-cohort-gap-closure`

**Scope.** Discharge F-P-6 (111-session YAML-cohort gap chore, forward-pointer from Phase 8a.10.1 close). Reconcile `configs/animals.yaml` `sessions.start`/`end` ranges + `configs/session_overrides.yaml` `secondary_spout_sessions:` registry against legacy `analysis/basic_behavior_analysis3/<animal>/report.json[latency_bySession]` keys.

**What landed.** [Cohort A per-animal range bumps + Cohort B per-(animal, date) additions per Task 2 adjudication. Reference DECISIONS Decisions 2-3 for the per-session table.]

**Sessions adjudicated.** 111 gap sessions (Cohort A + Cohort B): [N] INCLUDED, [M] EXCLUDED. Per-session table in DECISIONS Decision 2.

**Intentional behavior differences vs legacy.** Legacy `report.json` keys remain the historical reference; consolidated YAML is now the authoritative cohort definition post-chore. Sessions in legacy `report.json` that are EXCLUDED-by-this-chore remain in legacy outputs but are not consumed by the consolidated pipeline.

**Exit criteria met.** Task 4 diff re-verification PASS (zero unresolved gap; explicit EXCLUDED set matches Task 2 locks). YAML load tests PASS. No source code or analysis output changes.

**Forward-pointers queued.** None from this chore. Phase 7b-light is the next item per memory `project_phase_7b_light_ordering.md`.

**Tag:** `vchore-yaml-cohort-gap-closure` on the merge commit (Q3.A confirmation at merge).
```

**`docs/COWORK_SESSION_STATE.md` — Cowork updates separately** (Cowork drafts state-doc refresh; Priya pastes; do NOT modify in CC session).

### Chore-PR

**PR title:** `Chore: YAML cohort-gap closure (F-P-6 discharge, 111-session adjudication)`

**PR body:** short — chore summary, diff-count delta, link to Task 2 adjudication table, DECISIONS / MIGRATION_LOG links.

**Post-merge obligations (if Q3.A tag confirmed at merge):**

1. `git tag -a vchore-yaml-cohort-gap-closure <merge-sha> -m "Chore: YAML cohort-gap closure (F-P-6 discharge)"` and `git push origin vchore-yaml-cohort-gap-closure`.
2. Verify `git ls-remote --tags origin | grep vchore-yaml-cohort-gap-closure` shows the tag on origin.
3. Phase 7b-light kickoff at `docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md` is the next-up; its Task 0 branch-base check confirms the chore landed before 7b-light's feature branch is created.

---

## Cowork ↔ CC handoff

Cowork drafted this chore-PR kickoff 2026-05-14. Q1, Q4-Q6 LOCKED; Q2 + Q3 pending Task 2 + PR-merge time confirmation respectively. Paste-ready CC handoff prompt drafted alongside this kickoff — see workspace-root `chore-yaml-cohort-gap-closure-cc-handoff-prompt.md`.

Standard CC handoff blurb:

> Read `docs/prompts/chore-yaml-cohort-gap-closure-kickoff.md` in full, then execute Tasks 0 → 5 in order. STOP-and-report at Task 1 audit close. Task 2 is interactive (Priya adjudication); CC waits on the locked adjudication table before Task 3. CLAUDE.md ground rules apply throughout.

**Mid-chore re-specs:** any scope changes land as sequentially-numbered Addenda at the end of this kickoff (Addendum #1, #2, …) with the "ALL OTHER LOCKS UNCHANGED" footer per `feedback_iterative_addenda_pattern.md` memory.

---

## Addendum #1 — Re-scope from inclusion adjudication to policy lock (Priya 2026-05-14, post-Task-1)

CC's Task 1 audit completed successfully (STOP-and-report at `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` + `gap_audit_raw.json`; 69 unique-date gaps across PS46-PS55, 0 AMBIGUOUS, 0 Cohort B additions needed). During Task 2 adjudication review, the chore's framing was re-examined and re-scoped.

### Finding — original kickoff misread Decision 6's intent

Phase 8a.10 DECISIONS Decision 6 (2026-05-13) settled the cohort-inclusion question with **path (b): "treat YAML as authoritative."** F-P-6 was queued as a forward-pointer chore-PR with the framing "low scientific signal" and "small chore-PR" — indicating its purpose was to formally close Decision 6's deferral, NOT to re-litigate per-session inclusion. The original kickoff's Q1 (criterion-passing heuristic policy) and Q2 (YAML edit mechanism) framed the chore as inclusion re-adjudication. That framing was a misread.

### Re-scope — RE-LOCKED Q1.B, Q2.B

**Q1.B (supersedes Q1.A):** YAML is authoritative; no per-session inclusion adjudication. All 69 gap dates documented as out-of-scope-by-experimenter-design. CC's Task 1 audit-trail artifacts (`gap_audit_proposal.md` + `gap_audit_raw.json`) remain useful as a one-time "what's in legacy `report.json` outside our cohort" diagnostic but are NOT consumed as a cohort-inclusion policy.

**Q2.B (supersedes Q2.A):** No semantic YAML edits. `configs/animals.yaml` `sessions.start`/`sessions.end` values stay unchanged. The chore-PR is docs+comments only: header comment block + 8 per-animal inline `sessions:` breadcrumb comments + DECISIONS + MIGRATION_LOG entries (Path C — Priya 2026-05-14).

### Re-scope — supplements

**PS50 pre-tone-change retraining (new Decision 3 in Task 5 template):** PS50's current `sessions.start` of 2025-03-19 is later than PS46-PS48 (2025-03-07) and PS49 (2025-03-10) because the animal was not learning the task well under the original tones; tones were changed mid-experiment and the animal needed retraining time. Pre-2025-03-19 sessions are pre-tone-change retraining under a different stimulus regime — criterion-passing on that regime is NOT scientifically equivalent to cohort criterion-passing. The 20 pre-2025-03-19 gap days for PS50 are excluded by experimenter design (this codifies the implicit reason; CC's Task 1 heuristic misclassified them as INCLUDE because it only looks at session-level criterion, not stimulus-regime continuity).

**Q3 (tagging) — unchanged.** `vchore-yaml-cohort-gap-closure` on merge if Priya confirms; chore is now small enough to live un-tagged if Priya prefers.

**Q4-Q6 — unchanged.**

### Re-scope — task structure

**Task 1 — UNCHANGED** (completed). Audit-trail artifacts stay at `.scratch_chore_yaml_cohort_gap/`.

**Task 2 — RE-LOCKED.** All 69 EXCLUDE. `gap_audit_locked.md` optional (a one-line summary file is fine; or skip entirely and let DECISIONS reference the proposal directly).

**Task 3 — RE-SCOPED.** Inline YAML breadcrumb comments only — no semantic edits.

Single commit: `chore(yaml-cohort-gap): inline breadcrumb comments per animal pointing to F-P-6 close`

Add at the top of `configs/animals.yaml` (after the existing convention block, before the first animal entry):

```yaml
# Cohort-boundary policy (F-P-6 close, vchore-yaml-cohort-gap-closure):
# Per-animal `sessions.start`/`sessions.end` ranges reflect experimenter
# cohort-definition judgment. Sessions in the legacy
# `basic_behavior_analysis3/<animal>/report.json[latency_bySession]` that
# fall OUTSIDE these ranges are out-of-scope by intent — they include
# pre-cohort-launch baseline acquisition (animal-learning-the-task
# sessions), pre-tone-change retraining (PS50), and other
# experimenter-excluded contexts that are not scientifically equivalent
# to the criterion-cohort data. The 69-session out-of-scope set is
# documented in scratch artifacts at
# `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md`
# (audit-trail; not consumed by the pipeline). See DECISIONS.md
# 2026-MM-DD chore entry for full rationale.
```

Per animal: add a 1-line inline comment immediately after each `sessions:` line, e.g.:

```yaml
PS46:
  ...
  sessions:  # cohort-boundary policy: see header comment + DECISIONS
    start: 2025-03-07
    end: 2025-04-06
```

8 animals total (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55) — same comment text on each. Do NOT add the comment to `configs/session_overrides.yaml`'s `secondary_spout_sessions:` block.

**Acceptance criteria:** `git diff configs/animals.yaml` shows only comment additions; zero semantic changes. `pytest -q tests/test_animals.py` (or equivalent YAML-load tests) PASS.

**Task 4 — SIMPLIFIED.** Re-run CC's Task 1 audit against post-Task-3 YAML; expect unchanged 69-session gap count (zero semantic changes). Deliverable at `.scratch_chore_yaml_cohort_gap/post_close_verification.md`.

**Task 5 — RE-DRAFTED.** Replace the kickoff's original DECISIONS + MIGRATION_LOG templates with the corrected language below.

`docs/DECISIONS.md` new top entry:

```markdown
## 2026-MM-DD — Chore: YAML cohort-gap policy lock (F-P-6 discharge)

**Chore metadata.** Branch `chore/yaml-cohort-gap-closure`, opened 2026-MM-DD off main at the Phase 8a.10.1 merge commit `dc0e6bf`. Tag `vchore-yaml-cohort-gap-closure` on the merge commit (Priya confirms at PR-merge). Kickoff `docs/prompts/chore-yaml-cohort-gap-closure-kickoff.md` (re-scoped via Addendum #1, 2026-MM-DD). F-P-6 forward-pointer (from Phase 8a.10.1 close DECISIONS) discharged by this chore.

### Decision 1 — YAML is authoritative; no inclusion adjudication

Per Phase 8a.10 Decision 6 path (b), the per-animal `sessions.start`/`sessions.end` ranges in `configs/animals.yaml` reflect experimenter cohort-definition judgment. The 69-session out-of-scope set (sessions in legacy `report.json[latency_bySession]` outside the YAML range) is **intentional by design**, not an oversight requiring per-session re-adjudication. The chore-PR's kickoff initially queued a criterion-passing inclusion heuristic (Q1 of the kickoff); Addendum #1 reverses that framing — the heuristic is a diagnostic for "when did the animal learn the task," NOT a cohort-inclusion policy.

### Decision 2 — Out-of-scope sessions enumerated as audit-trail artifacts

CC's Task 1 produced two artifacts that document the 69-session out-of-scope set:
- `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` — human-readable per-animal table with day-of-life, criterion-3 max, trial count, and pre-Addendum-#1 heuristic INCLUDE/EXCLUDE proposals.
- `.scratch_chore_yaml_cohort_gap/gap_audit_raw.json` — machine-readable per-(animal, date) records.

These stay at `.scratch_chore_yaml_cohort_gap/` as permanent audit-trail references (not committed; reproducible from CC's Task 1 audit script). Future readers asking "what's in legacy report.json that's not in our cohort?" find the answer there.

### Decision 3 — PS50 pre-tone-change retraining note

PS50's `sessions.start` is 2025-03-19 (vs PS46-PS48 at 2025-03-07 and PS49 at 2025-03-10). The pre-2025-03-19 sessions are pre-tone-change retraining under a different stimulus regime — the animal was not learning the task well on the original tones, and the tones were changed mid-experiment with subsequent retraining. Criterion-passing on the pre-tone-change regime is NOT scientifically equivalent to cohort criterion-passing, so the 20 pre-2025-03-19 gap days are excluded by experimenter design. (Per Priya 2026-MM-DD chore-PR Task 2 adjudication.)

### Decision 4 — Inline YAML breadcrumb comments

`configs/animals.yaml` gains a header comment block and per-animal inline comments on each `sessions:` line pointing readers to this chore-PR + DECISIONS entry. No semantic YAML changes. Rationale: future readers running the same diff (legacy `report.json` vs YAML) shouldn't ask "why are these sessions missing?" without a breadcrumb to the policy answer.

### Decision 5 — PS52 / PS53 out-of-cohort confirmation

Per Q4.A: PS52 (16 session keys in `report.json`, range 2025-04-16 to 2025-05-01) and PS53 (20 session keys, range 2025-04-16 to 2025-05-03) appear in legacy `report.json` but are not part of the consolidated cohort — no entries in `configs/animals.yaml`. Out-of-scope; no action.

### Enforced at
- `configs/animals.yaml` — header comment block + 8 per-animal `sessions:` inline comments (Path C breadcrumbs).
- `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` (uncommitted audit-trail).
- `.scratch_chore_yaml_cohort_gap/gap_audit_raw.json` (uncommitted audit-trail).
- `.scratch_chore_yaml_cohort_gap/post_close_verification.md` (uncommitted; documents the 69-session gap as policy-locked).

### Findings carried forward
- None. F-P-6 discharged.
```

`docs/MIGRATION_LOG.md` append:

```markdown
## Chore — YAML cohort-gap policy lock (F-P-6 discharge)

**Date:** 2026-MM-DD
**Tag on merge:** `vchore-yaml-cohort-gap-closure` (if Priya confirms at PR-merge)
**Branch:** `chore/yaml-cohort-gap-closure`

**Scope.** Discharge F-P-6 (111-session — actually 69 unique-date — YAML-cohort gap chore, forward-pointer from Phase 8a.10.1 close). Re-scoped mid-chore via kickoff Addendum #1: original kickoff framed the chore as per-session inclusion adjudication; correct framing per Phase 8a.10 Decision 6 path (b) is policy lock + audit-trail documentation, no YAML semantic edits.

**What landed.** Single docs+comments commit on `chore/yaml-cohort-gap-closure`:
- `configs/animals.yaml` header comment block (cohort-boundary policy) + 8 per-animal inline `sessions:` comments. No semantic changes.
- `docs/DECISIONS.md` entry (this chore's close record).
- `docs/MIGRATION_LOG.md` entry (this entry).

**Sessions adjudicated.** 69 unique-date gaps across PS46-PS55 (Cohort A) + 0 gaps for Cohort B (`secondary_spout_sessions:` registry confirmed complete by CC's Task 1 audit). All 69 documented as out-of-scope-by-design; YAML ranges unchanged.

**Intentional behavior differences vs legacy.** None. Pipeline behavior is unchanged (no YAML semantic edits). Legacy `report.json` remains a historical reference; YAML stays the authoritative cohort definition. The new breadcrumb comments are documentation-only.

**Exit criteria met.** Task 4 diff re-verification confirms unchanged gap count (69) post-close. YAML load tests PASS. No source code or analysis output changes.

**Forward-pointers queued.** None from this chore. Phase 7b-light is the next item per memory `project_phase_7b_light_ordering.md`.

**Tag:** `vchore-yaml-cohort-gap-closure` on the merge commit (Priya confirms at PR-merge; if declined, log as untagged chore).
```

Final commit sequence:
1. `chore(yaml-cohort-gap): inline breadcrumb comments per animal pointing to F-P-6 close`
2. `docs(yaml-cohort-gap): DECISIONS + MIGRATION_LOG entries for F-P-6 policy lock`
3. (no Task 4 commit unless `post_close_verification.md` is committed — Priya's call; default uncommitted)

Open chore-PR with title: `Chore: YAML cohort-gap policy lock (F-P-6 discharge; docs + comments only)`.

### Process note

The original kickoff's locked-decision body (Q1.A, Q2.A) remains untouched in the audit trail above this Addendum. This Addendum is the override; the body documents what was originally drafted and why it was re-scoped. Per `feedback_iterative_addenda_pattern.md`: focused Addendum per re-spec, "ALL OTHER LOCKS UNCHANGED" — the "all-other-locks-unchanged" applies to Q3-Q6 above; Q1 and Q2 are explicitly re-locked here.

### ALL OTHER LOCKS UNCHANGED

(Q3 tagging, Q4 PS52/PS53 out-of-scope, Q5 Cohort B in scope, Q6 legacy report.json is the gap-audit source.)

---

## Addendum #1 — Re-scope from inclusion adjudication to policy lock (Priya 2026-05-14, post-Task-1)

CC's Task 1 audit completed successfully (STOP-and-report at `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` + `gap_audit_raw.json`; 69 unique-date gaps across PS46-PS55, 0 AMBIGUOUS, 0 Cohort B additions needed). During Task 2 adjudication review, the chore's framing was re-examined and re-scoped.

### Finding — original kickoff misread Decision 6's intent

Phase 8a.10 DECISIONS Decision 6 (2026-05-13) settled the cohort-inclusion question with **path (b): "treat YAML as authoritative."** F-P-6 was queued as a forward-pointer chore-PR with the framing "low scientific signal" and "small chore-PR" — indicating its purpose was to formally close Decision 6's deferral, NOT to re-litigate per-session inclusion. The original kickoff's Q1 (criterion-passing heuristic policy) and Q2 (YAML edit mechanism) framed the chore as inclusion re-adjudication. That framing was a misread.

### Re-scope — RE-LOCKED Q1.B, Q2.B

**Q1.B (supersedes Q1.A):** YAML is authoritative; no per-session inclusion adjudication. All 69 gap dates documented as out-of-scope-by-experimenter-design. CC's Task 1 audit-trail artifacts (`gap_audit_proposal.md` + `gap_audit_raw.json`) remain useful as a one-time "what's in legacy `report.json` outside our cohort" diagnostic but are NOT consumed as a cohort-inclusion policy.

**Q2.B (supersedes Q2.A):** No semantic YAML edits. `configs/animals.yaml` `sessions.start`/`sessions.end` values stay unchanged. The chore-PR is docs+comments only: header comment block + 8 per-animal inline `sessions:` breadcrumb comments + DECISIONS + MIGRATION_LOG entries (Path C — Priya 2026-05-14).

### Re-scope — supplements

**PS50 pre-tone-change retraining (new Decision 3 in Task 5 template):** PS50's current `sessions.start` of 2025-03-19 is later than PS46-PS48 (2025-03-07) and PS49 (2025-03-10) because the animal was not learning the task well under the original tones; tones were changed mid-experiment and the animal needed retraining time. Pre-2025-03-19 sessions are pre-tone-change retraining under a different stimulus regime — criterion-passing on that regime is NOT scientifically equivalent to cohort criterion-passing. The 20 pre-2025-03-19 gap days for PS50 are excluded by experimenter design (this codifies the implicit reason; CC's Task 1 heuristic misclassified them as INCLUDE because it only looks at session-level criterion, not stimulus-regime continuity).

**Q3 (tagging) — unchanged.** `vchore-yaml-cohort-gap-closure` on merge if Priya confirms; chore is now small enough to live un-tagged if Priya prefers.

**Q4-Q6 — unchanged.**

### Re-scope — task structure

**Task 1 — UNCHANGED** (completed). Audit-trail artifacts stay.

**Task 2 — RE-LOCKED.** All 69 EXCLUDE. `gap_audit_locked.md` optional (a one-line summary file is fine; or skip entirely and let DECISIONS reference the proposal directly).

**Task 3 — RE-SCOPED.** Inline YAML breadcrumb comments only — no semantic edits. One commit. See CC reply at `chore-yaml-cohort-gap-cc-reply-task2.md` (Cowork-drafted; in workspace root) for the exact comment text + per-animal application pattern.

**Task 4 — SIMPLIFIED.** Diff re-verification expects unchanged 69-session gap count. Deliverable at `.scratch_chore_yaml_cohort_gap/post_close_verification.md`.

**Task 5 — RE-DRAFTED.** Replace the kickoff's original DECISIONS / MIGRATION_LOG templates with the corrected language at `chore-yaml-cohort-gap-cc-reply-task2.md` (Cowork-drafted). The corrected language locks the policy (Decision 1), references audit-trail artifacts (Decision 2), captures the PS50 context (Decision 3), documents the breadcrumb-comments approach (Decision 4), and confirms PS52/PS53 out-of-cohort (Decision 5).

### Process note

The original kickoff's locked-decision body (Q1.A, Q2.A) remains untouched in the audit trail above this Addendum. This Addendum is the override; the body documents what was originally drafted and why it was re-scoped. Per `feedback_iterative_addenda_pattern.md`: focused Addendum per re-spec, "ALL OTHER LOCKS UNCHANGED" — the "all-other-locks-unchanged" applies to Q3-Q6 above; Q1 and Q2 are explicitly re-locked here.

### ALL OTHER LOCKS UNCHANGED

(Q3 tagging, Q4 PS52/PS53 out-of-scope, Q5 Cohort B in scope, Q6 legacy report.json is the gap-audit source.)
