# Phase 7c.1-dlc-source-rename-and-pilot Kickoff — Source-side on-disk-string renames (Addendum #1 deferrals from 7b-light) + 3-session pilot re-emit

**Branch:** `phase/7c.1-dlc-source-rename-and-pilot` off latest `origin/main` (post-Phase-7b-light close at `d80d7c0`, tag `v7b-light-dlc-narrative-cleanup`).
**Tag on phase-close merge:** `v7c.1-dlc-source-rename-and-pilot`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 7b-light closed (PR merged 2026-05-15, tag pushed); MICROSCOPE mount available (R/W for pilot re-emit; read-only for audit).
**Estimated scope:** small-to-mid. Source-side on-disk-string renames (resolving 7b-light Addendum #1 deferrals; ~5-8 commits) + 3-session pilot re-emit (~3 sessions of operational compute) + pilot verification + phase close. ~8-12 commits, ~3-5 days CC wall time.

**Why split (a) into 7c.1 + 7c.2:** the cohort re-emit (~355 sessions × hours-per-session of DLC compute) is operationally heavy and risk-concentrated. Phase 7c.1 lands the source-side renames + validates the operational pipeline on a 3-session pilot; Phase 7c.2 picks up the cohort completion + Phase 7a.7 visual gate fold-in + legacy-path cleanup once 7c.1's pilot confirms the pipeline works end-to-end and gives a realistic per-session wall-time estimate. Reviewers see two focused PRs; if 7c.2's cohort compute stalls, 7c.1's source-side work doesn't sit on a long-lived branch.

---

## Context

Phase 8a.10.1 corrected the cohort-wide Tone↔Reward channel-label swap at the wavesurfer read boundary and re-emitted 276 Phase 2 NPZs. The X1-β surgical rename + Phase 7b-light's deeper source-side narrative rename together corrected the DLC code to read tone-anchored events with semantically-aligned identifiers. But the on-disk DLC outputs at `pipeline_outputs/dlc_analysis/{spatial_reward_aligned, dlc_kinematics/...}/` are **stale post-8a.10.1** — they were generated from pre-fix Phase 2 NPZs. Only 4 sessions reflect post-fix data (PS46/2025-03-07, PS54/2025-05-03, PS48/2025-03-14 from 8a.10.1 Task 4.5 + PS46 again from Phase 7b-light Task 5 spot-check).

Phase 7b-light Addendum #1 deferred on-disk-string renames (output subdir paths, NPZ schema keys, window-dir tokens, family-name tokens, CLI flag spellings, figure filename suffixes) to Phase 7c. Phase 7c.1 lands those renames + a 3-session pilot re-emit to validate the pipeline end-to-end before Phase 7c.2's cohort-wide rollout.

**Scientific impact of 7c.1:** zero at the cohort level (only 3 sessions re-emitted). The new on-disk paths (`spatial_tone_aligned/`, `toneAligned_*`, etc.) get fresh outputs for the 3 pilot sessions. The legacy paths (`spatial_reward_aligned/`, etc.) remain untouched and continue to hold the pre-fix cohort outputs. Phase 7c.2 closes the cohort transition.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Not applicable — Phase 7c.1 is on-disk-string source renames + pilot re-emit. Existing DLC code (post-7b-light at `d80d7c0`) is the canonical implementation.

### Dead code identification

Task 1 audit enumerates on-disk-string locations across the DLC subtree (the same files Phase 7b-light touched, plus `paths.py` path-construction methods, YAML config schemas, NPZ-writer modules). No dead-code deletions in this phase; legacy on-disk tree cleanup deferred to Phase 7c.2 Task 5.

### Sub-phase breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup | (none) | 0 | <5 min |
| Task 1 — On-disk-string rename audit (STOP-and-report) | `.scratch_phase_7c1/on_disk_string_audit.md` | 0 | 1-2 hr |
| Task 2 — Source-side on-disk-string renames | per audit; one commit per coherent group | 4-6 | 1-2 days |
| Task 3 — 3-session pilot re-emit | driver script + per-session manifest | 1-2 | 4-8 hr (operational compute) |
| Task 4 — Pilot verification (STOP-and-report) | `.scratch_phase_7c1/pilot_verdict.md` | 0 | 1-2 hr |
| Task 5 — DECISIONS + MIGRATION_LOG + 7c.2 forward-pointer | 3 docs files | 1 | 30-60 min |

### Parity strategy

**Two-axis verification (sample-scale, not cohort-scale):**

1. **PS46/2025-03-07 byte-equality.** The post-rename outputs at `pipeline_outputs/dlc_analysis/spatial_tone_aligned/...` for PS46/2025-03-07 should be byte-identical to legacy `spatial_reward_aligned/...` outputs (modulo path prefix). PS46 is swap-fix-invariant per Phase 8a.10.1 Task 4.5 + Phase 7b-light Task 5. This verifies the rename + re-emit is a no-op at the data level for the clean baseline case.

2. **PS54/2025-05-03 pre-fix vs post-fix sanity.** PS54 is withhold-bearing post-stroke; the swap fix grew its baseline pool by 86 events (45 L + 41 R withholds) per Task 4.5. The new post-rename re-emit should reproduce this delta. Verify: post-rename `n_tones` ≈ pre-fix `n_rewards` + 86 (or whatever the corrected count is).

3. **PS50/2025-03-25 pilot for post-tone-change regime context.** Spot-check that the post-tone-change session re-emits correctly (no errors, plausible outputs). Light sanity check; no quantitative verdict expected.

**Phase 7a.7 visual gate fold-in is deferred to Phase 7c.2** — running it on a 3-session pilot wouldn't give a cohort-wide verdict, and the heatmap families need the full cohort to produce meaningful tile-grids.

### Hardcoded constants

Task 1 audit confirms whether any numeric thresholds are co-located with the renamed identifiers; default disposition is "value unchanged; only the identifier renames." Surface any candidates for relocation to `configs/defaults.yaml` as STOP-and-ask.

---

## Locked scoping decisions (Priya 2026-05-15)

### Q1 — Pilot session set — LOCKED Q1.A

3 sessions covering 3 scenarios:

- **PS46/2025-03-07** — bilateral, swap-fix-invariant baseline (verifies rename is no-op at data level via byte-equality vs legacy `spatial_reward_aligned/`).
- **PS54/2025-05-03** — withhold-bearing post-stroke (verifies swap-fix propagation via pre-fix vs post-fix delta sanity).
- **PS50/2025-03-25** — post-tone-change regime (pilot for cross-regime session execution; light sanity check).

PS48/2025-03-14 (Pattern A multi-half) explicitly NOT in scope — pre-existing F-P-4 infrastructure gaps deferred to Phase 7-pre-multi-half-dlc F-P-5.

### Q2 — On-disk-string rename audit policy — LOCKED Q2.A (mirror Phase 7b-light Task 1 pattern)

Task 1 enumerates every on-disk-affecting string in the post-7b-light source tree + classifies per the bifurcation-rule inverse (Phase 7b-light PRESERVED these; Phase 7c.1 RENAMES these to match the source-side identifier rename). Cross-reference each rename target with consumers (Phase 9 / pub-figures candidates) to surface any string-format dependencies before they break downstream.

### Q3 — Output safety / overwrite pattern — LOCKED Q3.A (new-tree write; legacy preserved)

Pilot re-emit writes to NEW on-disk paths (`spatial_tone_aligned/`, `toneAligned_<N>pre-<M>post/`, etc.). Legacy paths (`spatial_reward_aligned/`, etc.) untouched. Pilot writes ONLY for the 3 sessions in Q1.A. Legacy tree cleanup deferred to Phase 7c.2 Task 5 (cohort-wide; happens only after the cohort completes + Phase 7c.2 verification PASSes).

### Q4 — PathResolver — LOCKED Q4.A (no infrastructure change)

Mirror Phase 7c parent's Q7.A. Bare `PathResolver()` writes to MICROSCOPE production paths (new tree). No scratch-write contortion; pilot writes to production new-tree paths directly. Phase 7b-light Task 5's read/write routing complication doesn't apply because we ARE writing to production (the desired end state); no override needed.

### Q5 — Pilot verification scope — LOCKED Q5.A

Per the Parity strategy section: PS46 byte-equality + PS54 pre-fix-vs-post-fix delta sanity + PS50 light sanity. STOP-and-report at Task 4. If any PILOT verification FAILs, STOP for Priya adjudication before opening the phase-close PR.

### Q6 — Phase 7c.2 forward-pointer — LOCKED Q6.A

Phase 7c.2 (cohort completion + Phase 7a.7 visual gate fold-in + legacy-path cleanup) is queued as the next phase. Cowork drafts the 7c.2 kickoff post-7c.1-merge, incorporating per-session wall-time estimates from the Task 3 pilot manifest.

### Q7 — Legacy-tree cleanup — DEFERRED to 7c.2

Legacy `spatial_reward_aligned/` etc. trees STAY in place through Phase 7c.1 close. Cleanup belongs to Phase 7c.2 Task 5 (after cohort-wide verification PASSes). This phase doesn't touch the legacy tree at all.

---

## Execute on branch `phase/7c.1-dlc-source-rename-and-pilot`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD at `d80d7c0` (or later if main has moved). Run `git branch --show-current` and confirm NOT on `main` — pre-commit hook enforces; do not bypass. Confirm `conda activate stroke_orofacial` succeeds, `python -c "import stroke_orofacial"` exits 0, `pytest --collect-only -q` exits 0 with 1417+ tests collected. Confirm MICROSCOPE mount accessible (R/W).

Do NOT create the feature branch yet — Task 1 first.

### Task 1 — On-disk-string rename audit (STOP-and-report)

**Goal:** Enumerate every on-disk-affecting string in the post-7b-light source tree + cross-reference consumers. Mirror Phase 7b-light Task 1 audit pattern (inverted direction — 7b-light PRESERVED these; 7c.1 RENAMES them).

**Steps:**

1. Grep across `src/stroke_orofacial/dlc_spatial/` + `dlc_kinematics/` + `paths.py` + `configs/defaults.yaml` + `notebooks/12_dlc_spatial_tone_aligned.ipynb` + `scripts/run_notebook_12_first_emit.py` for string literals containing `reward` (case-insensitive). Classify each per the bifurcation-rule inverse:
   - **RENAME** (Case 2 on-disk; corresponds to source-side renames already landed in 7b-light): output subdir paths (`spatial_reward_aligned`), window-dir tokens (`rewardAligned_<N>pre-<M>post`), NPZ schema keys (`n_rewards`, `reward_idx_in_session`, etc.), family-name tokens (`reward_aligned:` plot family in YAML), CLI flag spellings (`--reward-windows-ms`), figure filename suffixes (`mouseLrewards`).
   - **PRESERVE** (genuinely reward-anchored on-disk semantics, OR cross-reference to legacy/Phase-8a tree): legacy `report.json` key citations, Phase-8a spout-behavior cross-refs, comments referring to legacy directory layouts.

2. Build a per-rename string-pair map: `(old_string, new_string, source_file:line)` for every RENAME target.

3. Cross-reference each new string against existing consumers in `figures/`, `reports/`, `stats/`, and notebook orchestration code — surface any string-format dependencies that would break if the rename ships without consumer updates.

4. Audit `paths.py` for path-construction methods that emit the affected strings. Confirm each constructor method renames in lockstep.

5. Audit NPZ-writer + parquet-writer modules in `dlc_kinematics/` for schema-key emission. Confirm each writer renames in lockstep.

**STOP-and-report deliverable.** Markdown at `.scratch_phase_7c1/on_disk_string_audit.md`:

- Per-string-pair RENAME table with file:line context.
- Consumer cross-reference table.
- PathResolver constructor inventory.
- NPZ + parquet schema-key emission inventory.
- Open questions if any string falls in a "third bucket" (e.g., partially on-disk, partially cross-reference) — STOP-and-ask Priya.

**Anomaly escalation:** if RENAME count is unexpectedly large (>50 string-pairs) or AMBIGUOUS >5, recommend a multi-pass approach (Pass 1 = unambiguous; Pass 2 = adjudicated).

Task 1 produces zero commits.

### Task 2 — Source-side on-disk-string renames

**Branch:** `phase/7c.1-dlc-source-rename-and-pilot`, created off `d80d7c0`.

**Commit pattern:** one commit per coherent group, mirroring Phase 7b-light's structure:

- C1 (`dlc_spatial/` on-disk strings): output subdir paths + family-name tokens + figure filename suffix templates.
- C2 (`dlc_kinematics/` on-disk strings): NPZ schema keys (`n_rewards` → `n_tones`, etc.) + window-dir tokens + CLI flag spellings.
- C3 (`paths.py` path-constructor methods + docstrings): align with new on-disk strings.
- C4 (`configs/defaults.yaml`): family-name token rename (`tongue_visual.plot_families.reward_aligned:` → `tone_aligned:`) — note this was PRESERVED in 7b-light per Addendum #1 edge case; 7c.1 is the natural moment to flip it.
- C5 (notebook 12 + `scripts/run_notebook_12_first_emit.py`): align with new on-disk paths.
- C6 (test fixture + assertion path strings): update test files where assertions reference the renamed paths/keys.

**Acceptance criteria for Task 2:** `pytest -q` (full suite) PASSES at the post-7b-light baseline (1417+/39+/0) throughout — renames are no-ops at runtime since no re-emit has happened yet; tests run on fixture data that uses the new path strings. Ruff clean.

### Task 3 — 3-session pilot re-emit

**Driver script:** `scripts/phase_7c1/reemit_pilot.py` (new). Invokes DLC kinematics + spatial pipeline for the 3 pilot sessions per Q1.A; writes outputs to new on-disk paths.

**Pilot sessions (Q1.A-locked):**
1. PS46/2025-03-07 — bilateral baseline.
2. PS54/2025-05-03 — withhold-bearing post-stroke.
3. PS50/2025-03-25 — post-tone-change regime sanity.

**Output safety:** Q3.A (new-tree write; legacy untouched). Outputs go to `pipeline_outputs/dlc_analysis/spatial_tone_aligned/...` + `pipeline_outputs/dlc_analysis/dlc_kinematics/.../<new on-disk subdir>/...` per the post-Task-2 renamed paths.

**Per-session manifest:** record (animal, date, runtime_seconds, output sha256s, success/failure, anomaly notes). Aggregate at `.scratch_phase_7c1/pilot_manifest.csv`. Surface unexpected failures as STOP-and-report.

**Commit pattern:** driver script + manifest committed; NPZ/parquet outputs are written to MICROSCOPE production paths (not git).

### Task 4 — Pilot verification (STOP-and-report)

**Goal:** Verify pilot re-emit per the Parity strategy section.

**Steps:**

1. **PS46/2025-03-07 byte-equality.** Compare new `pipeline_outputs/dlc_analysis/spatial_tone_aligned/...` outputs against legacy `spatial_reward_aligned/...` outputs (modulo path prefix). PS46 is swap-fix-invariant; outputs MUST be byte-identical. Use `numpy.testing.assert_array_equal` on parquet arrays + sha256 on NPZ payloads.

2. **PS54/2025-05-03 pre-fix vs post-fix delta sanity.** Compare new outputs against legacy outputs; document the trial-pool growth on the withhold side. Expected: post-rename `n_tones` field ≈ pre-fix `n_rewards` + 86 (per 8a.10.1 Task 4.5; the exact delta will be re-verified by this re-emit).

3. **PS50/2025-03-25 light sanity.** Confirm re-emit ran without errors; spot-check that output values are plausible (trial counts within expected range; no NaN-poisoning; figure axes well-defined). No quantitative verdict required.

**STOP-and-report deliverable.** Markdown at `.scratch_phase_7c1/pilot_verdict.md`:

- PS46 byte-equality PASS/FAIL with sha256s.
- PS54 pre-fix vs post-fix delta table; matches Task-4.5-expected pattern PASS/FAIL.
- PS50 sanity-check summary.
- **Wall-time data for 7c.2 budgeting:** per-session runtime from the pilot manifest (mean + range). Cowork uses this to size the 7c.2 cohort re-emit budget.
- If any FAIL: side-by-side diff narrative + STOP for Priya adjudication before Task 5.

### Task 5 — DECISIONS + MIGRATION_LOG entries (Path Y format)

`docs/DECISIONS.md` new top entry:

```markdown
## 2026-MM-DD — Phase 7c.1-dlc-source-rename-and-pilot close — Source-side on-disk-string renames + 3-session pilot re-emit

**Phase metadata.** Branch `phase/7c.1-dlc-source-rename-and-pilot`, opened off main at the Phase 7b-light merge commit `d80d7c0`. Tag `v7c.1-dlc-source-rename-and-pilot` on the merge commit. Kickoff `docs/prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md`. Discharges Phase 7b-light Addendum #1 on-disk-string deferrals for the renamed source surface; cohort completion deferred to Phase 7c.2.

### Decision 1 — Pilot session set: PS46/2025-03-07 + PS54/2025-05-03 + PS50/2025-03-25 per Q1.A
### Decision 2 — On-disk-string rename inventory (Task 1 audit results — link to scratch markdown)
### Decision 3 — Output safety: new-tree write; legacy preserved per Q3.A
### Decision 4 — PathResolver: no infrastructure change per Q4.A
### Decision 5 — Pilot verification: two-axis (PS46 byte-equality + PS54 delta sanity + PS50 light sanity) per Q5.A; verdict PASS — see scratch verdict
### Decision 6 — Phase 7c.2 forward-pointer locked; Cowork drafts kickoff post-merge incorporating Task 3 wall-time data

### Enforced at
[Files list — ~5-8 source/test/config/notebook + 3 docs.]

### Findings carried forward
- Phase 7c.2-dlc-cohort-completion (cohort-wide re-emit on the renamed source + Phase 7a.7 visual gate fold-in + legacy-path cleanup; ~352 remaining sessions). Bandwidth budget informed by Task 3 pilot wall-time data.
- Phase 7-pre-alignment-templates F-P-7.
- Phase 7-pre-multi-half-dlc F-P-5 (PS48 spot-check deferral from 7b-light + Pattern A merge wiring).
- Phase 9 stats (blocked on 7c.2).
- Phase 7-pre-secondary-spout-compare-DLC (blocked on b-half DLC inference).
- Pub-figures phase (blocked on 7c.2).
- Phase 7a.7 retired into Phase 7c.2 as a sub-task.
```

`docs/MIGRATION_LOG.md` append: standard structure per Phase 7b-light template, covering scope (source-side on-disk-string renames + 3-session pilot re-emit), what landed (per-Task-2 commit list), pilot verification PASS, wall-time data for 7c.2 budgeting.

**`docs/COWORK_SESSION_STATE.md` — Cowork updates separately** on merge.

### Phase-close PR

**PR title:** `Phase 7c.1-dlc-source-rename-and-pilot — Source-side on-disk-string renames (Addendum #1 deferrals) + 3-session pilot re-emit`

**Post-merge obligations:**
1. `git tag -a v7c.1-dlc-source-rename-and-pilot <merge-sha> -m "Phase 7c.1: Source-side on-disk-string renames + 3-session pilot re-emit"` and `git push origin v7c.1-dlc-source-rename-and-pilot`.
2. Verify tag on origin.
3. Hand back to Cowork with merge SHA + the pilot wall-time data — Cowork drafts state-doc refresh + Phase 7c.2 kickoff (incorporating wall-time estimates for the ~352-session cohort re-emit).

---

## Cowork ↔ CC handoff

Cowork drafted this kickoff 2026-05-15 post-Phase-7b-light merge, split from a combined Phase 7c kickoff per Priya 2026-05-15 (option (a) split). Q1-Q7 default-locked; Priya can adjust at draft review or via Addendum mid-phase. Paste-ready CC handoff prompt delivered inline in Cowork chat (per `feedback_direct_doc_edits_and_paste_ready_prompts.md` workflow).

**Mid-phase re-specs:** any scope changes land as sequentially-numbered Addenda at the end of this kickoff (Addendum #1, #2, …) with the "ALL OTHER LOCKS UNCHANGED" footer per `feedback_iterative_addenda_pattern.md`. Expected mid-phase Addenda candidates: Q1 pilot session set adjustment if Task 1 audit surfaces edge cases not covered by the 3 default sessions; Q3 output-safety adjustment if pilot collisions with downstream consumers surface; PathResolver scope re-open if Q4.A breaks under pilot operations.
