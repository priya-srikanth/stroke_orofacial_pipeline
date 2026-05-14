# Phase 8a.10.1 Kickoff — Tone↔Reward swap fix at WS read-time + cohort-wide Phase 2 re-emit

**Branch:** `phase/8a.10.1-tone-reward-swap-fix` off latest `origin/main` (post-Phase-8a.10 close at `46a237e`, tag `v8a.10-spout-visual-gate`).
**Tag on phase-close merge:** `v8a.10.1-tone-reward-swap-fix`.
**Prerequisites:** MICROSCOPE mount; conda env `stroke_orofacial` active; Phase 8a.10 closed (PR #113 merged 2026-05-14, fill-in PR #114 merged).
**Estimated scope:** small-to-mid. Single-point fix in `wavesurfer_io.py` (~10-30 LoC) + Phase 2 cohort-wide re-emit (~360 sessions) + verification (~50-100 LoC test scripts) + Phase 8a.10 figure re-render. ~5-10 source/test files + 3 docs files + this kickoff. Most of the wall time is the cohort re-emit, not code.

---

## Context

Phase 8a.10 surfaced a cohort-wide Tone↔Reward channel-label swap in the wavesurfer acquisition pipeline (Priya 2026-05-12, confirmed via extended diagnostic in `.scratch_phase_8a_10/reward_tone_swap_extended_diagnostic.md`). The evidence is solenoid pulse-width analysis on raw `.h5` files:

- Channel labeled `"Reward"` produces ~200 ms pulses → these are actually **tones** (auditory cues).
- Channel labeled `"Tone"` produces ~26 ms pulses → these are actually **rewards** (solenoid valve opens for ~25 ms to deliver water).

The swap is **cohort-wide on both rigs**, present in every wavesurfer session inspected (including the legacy outputs in `analysis/session_processing3/`, which were generated from the same swapped raw data). Legacy and current pipeline both consume the swapped labels — outputs are systematically wrong on the tone/reward axis but consistent with each other.

Phase 8a.10's DECISIONS Decision 4 deferred the fix here (Option 1: swap at WS read time + cohort-wide re-emit). This phase executes that decision.

**Scientific impact of the swap:** every Phase 2 NPZ has `rewards_idx` holding tone-onset sample indices and `tones_idx` holding reward-delivery sample indices. Every downstream analysis that uses tone alignment (Phase 3 alignment templates, lick raster trial alignment, latency endpoints) is currently aligning to reward delivery instead. Every analysis that uses reward indices (criterion 3, first-correct-lick semantics, lickRate) is using tone-onset timing instead. The asymmetry between these two events is ~150-300 ms in typical sessions; downstream metrics that operate on post-reward windows have been operating on post-tone windows, and vice versa.

**Why Option 1 (WS read-time swap) over Option 2 (rename consumers):**
- Single-point fix; lowest blast radius in source code.
- Forces a Phase 2 re-emit, which surfaces the cohort-wide impact rather than hiding it behind label renames.
- Downstream code (Phase 3, Phase 7, Phase 8a) consumes `rewards_idx`/`tones_idx` by name and doesn't need to change — the names now hold semantically correct content.
- Tests that exercise these consumers automatically validate against the corrected data.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

This is a fix, not a port — but the WS read-time logic lives in `src/stroke_orofacial/io/wavesurfer_io.py` (or wherever in the repo the channel-mapping happens; Task 1 audit locates the exact file/function). No legacy notebook port involved.

### Dead code identification

Not applicable — single-fix scope. Task 1 audit confirms no compensating-logic elsewhere in the codebase that already partial-corrects the swap (e.g., if any consumer has a `# swap tone/reward here` comment, that compensating logic must be removed alongside the WS-read-time fix to avoid double-swapping).

### Sub-phase breakdown

Per Task structure below.

### Parity strategy

**Pre-fix vs post-fix comparison.** For a sample of N=5-10 sessions across animals + dates:

1. Load pre-fix NPZ (from current `pipeline_outputs/spout_behavior/licks_and_rewards/`).
2. Load post-fix NPZ (re-emitted after the WS fix).
3. Verify `rewards_idx_post == tones_idx_pre` (the array contents swap).
4. Verify `tones_idx_post == rewards_idx_pre`.
5. Verify per-trial post-reward licks pattern shifts in the expected direction (post-reward window now begins at the actual reward, not the tone — earlier-onset licks should drop, later-onset licks should rise).

**Raw-data ground-truth check.** For the same N=5-10 sessions, directly inspect raw `.h5` via the existing diagnostic pattern (pulse-width on each labeled channel; confirm 200 ms pulses are on what's now labeled `tones_idx` and 26 ms pulses are on what's now labeled `rewards_idx`).

### Hardcoded constants

The fix introduces no new constants. If channel-name strings (`"Reward"`, `"Tone"`) are hardcoded in `wavesurfer_io.py`, the swap is a single read-mapping change. If a pulse-width-based auto-detect were considered as an alternative implementation, that would introduce thresholds (~30 ms boundary between reward and tone pulse-widths) — but I recommend avoiding pulse-width auto-detect for this phase; the label-based swap is simpler and explicit.

---

## Locked scoping decisions (Priya 2026-05-14)

All 8 questions answered. Locked verdicts below; this section is now an audit trail rather than a pending-decision queue.

### Q1 — Phase 3 alignment template re-emit scope — LOCKED Q1.A

Phase 3 alignment templates re-emit as part of Phase 8a.10.1. ~341 templates on disk (Cohort A scope; Cohort B's 14 sessions add minimally). Adds ~30-60 min wall time + verification work. Rationale: carrying swapped templates forward would bake the swap into Phase 7 / future analyses; correcting at source closes the issue completely within this phase.

### Q2 — Phase 8a.10 figure re-render scope — LOCKED Q2.A

Re-render sub-deliverable A (8 animals × 11 plot families) and sub-deliverable B (3 animals × 4-row + per-trial 2×2) on the post-fix Phase 2 NPZs. Phase 8a.10's PASS verdict gets superseded; new visual-verdict round runs on the corrected figures. Rationale: the visual gate is the verdict mechanism; without re-rendering we don't have visual confirmation the fix is correct AND we don't know whether Phase 8a.10's scientific conclusion survives.

### Q3 — Phase 7 / 7a re-run scope — LOCKED Q3.B (defer)

Phase 7 / 7a re-run carved out as a future sibling phase (likely Phase 7b or 8a.10.4 — scoped separately when picked up). 7a parity baselines (7a.0 / 7a.2 / 7a.3 / 7a.4 / 7a.5 / 7a.6) were established under the swap; re-baselining them is substantial work that doesn't fit inside 8a.10.1's swap-fix scope.

### Q4 — Cohort scope for re-emit — LOCKED Q4.B (A + B)

Re-emit Cohort A (341 sessions, 8 animals) + Cohort B (14 secondary-spout sessions, 3 animals). Total: ~355 sessions. The 111-session YAML-cohort gap stays a separate forward-pointer chore.

### Q5 — Tag convention — LOCKED Path Y (Priya 2026-05-14)

DECISIONS / MIGRATION_LOG / COWORK_SESSION_STATE entries reference the tag `v8a.10.1-tone-reward-swap-fix` only. No `<FILL>` / `#FILL` placeholders. Merge-SHA + PR# are recoverable via `git rev-list -n 1 v8a.10.1-tone-reward-swap-fix` and `gh pr list --search 'v8a.10.1'` respectively. **No fill-in PR after the main close PR — phase close is a single PR.**

### Task 1 config flag — LOCKED opt-in flag

Add `wavesurfer.tone_reward_swap_enabled: true` to `configs/defaults.yaml`. Default value `true` — swap is applied for the current cohort by default. Can be set to `false` to disable for hypothetical future correctly-labeled cohorts (kill-switch semantics). Inline doc-comment references this kickoff + the pulse-width evidence in `.scratch_phase_8a_10/reward_tone_swap_extended_diagnostic.md`.

If Priya intended different polarity ("opt in" → flag default `false`, fix off until enabled), flag this back at kickoff-doc-PR review.

### Task 2 output-safety — LOCKED Option α (in-place overwrite)

Phase 2 re-emit overwrites existing outputs at `pipeline_outputs/spout_behavior/licks_and_rewards/` in-place. Pre-fix baselines recoverable from git history of prior chore-emit PRs + the manifest sha256 lookup. Rationale: fix is single-point and verifiable from raw `.h5` data; pre-fix baselines aren't load-bearing once the fix is verified.

### Task 0.5 anomaly policy — LOCKED A1 + A2 (STOP-and-report defaults)

**Kind 1 (inverted-swap session — correctly labeled):** exclude from re-emit. STOP-and-report. Priya adjudicates inline before Task 1 starts.

**Kind 2 (truly anomalous — pulse-widths match neither pattern):** exclude from re-emit. STOP-and-report. Priya adjudicates inline.

Escalation path: if Task 0.5 surfaces an unexpectedly high anomaly count (5+ of either kind), CC pauses and recommends switching to richer handling (B1 — per-session config override; B2 — per-anomaly auto-diagnostic). Priya picks the escalation.

---

## Execute on branch `phase/8a.10.1-tone-reward-swap-fix`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD at `46a237e` (or later if main has moved). Confirm MICROSCOPE mount. Confirm `import stroke_orofacial` + `pytest --collect-only -q` both exit 0.

Do NOT create the feature branch yet — Task 0.5 first.

### Task 0.5 — Cohort-wide pulse-width audit (STOP-and-report)

**Goal:** Confirm the swap is universal across the cohort (Q4-locked scope) and identify any session-specific exceptions (e.g., a rig configuration change mid-cohort that flipped the swap).

**Steps:**

1. For every (animal, date) in scope (per Q4 verdict), open the raw `.h5` via `wavesurfer_io.read_wavesurfer_session` (or equivalent low-level reader).
2. For the `"Reward"`-labeled channel, compute the modal pulse-width across all detected pulses. Expected: ~200 ms (tone).
3. For the `"Tone"`-labeled channel, compute the modal pulse-width. Expected: ~26 ms (reward solenoid).
4. Flag any session where the pulse-widths are reversed (i.e., "Reward" channel has ~26 ms pulses — meaning the swap is INVERTED for that session, which would mean no fix is needed). These would be the rare correctly-labeled sessions, if any exist.
5. Flag any session where pulse-widths don't match either expected value (anomalous; needs manual review).

**STOP-and-report deliverable.** Markdown summary including:

- Total sessions inspected.
- Sessions confirming the swap (expected majority — ideally 100%).
- Sessions with inverted swap (no fix needed — likely zero). Per A1 anomaly policy: exclude from Task 2 re-emit; STOP-and-report list to Priya.
- Anomalous sessions (manual review). Per A2 anomaly policy: exclude from Task 2 re-emit; STOP-and-report list to Priya.
- Per-animal histogram of modal pulse-widths on each labeled channel (sanity check).

**Anomaly escalation trigger:** if total anomaly count across Kind 1 + Kind 2 is ≥ 5, CC pauses and recommends switching to richer handling (B1: per-session config override registry; B2: per-anomaly auto-diagnostic). Priya picks escalation path or stays with A1/A2 exclude defaults.

Task 0.5 produces zero commits on the feature branch.

### Task 1 — WS read-time swap fix + unit tests

**Branch:** `phase/8a.10.1-tone-reward-swap-fix`, created off post-Task-0.5 `main`.

**Files:**
- `src/stroke_orofacial/io/wavesurfer_io.py` — single-point fix at channel-read mapping. Apply the swap post-read inside the loader, gated by the config flag. Document the fix inline with a comment referencing this kickoff + the pulse-width evidence in `.scratch_phase_8a_10/reward_tone_swap_extended_diagnostic.md`.
- `configs/defaults.yaml` — add `wavesurfer.tone_reward_swap_enabled: true` (LOCKED Task-1 flag verdict). Default `true` = swap applied. Kill-switch semantics: set to `false` to disable for hypothetical future correctly-labeled cohorts.
- `tests/test_wavesurfer_io.py` — extend with:
  - `test_reward_channel_holds_short_pulses` — fixture or synthetic case where the labeled "Reward" channel has ~26 ms pulses, asserting `rewards_idx` after read is the short-pulse channel.
  - `test_tone_channel_holds_long_pulses` — converse.
  - `test_swap_fix_compensates_for_label_inversion` — explicitly documents the swap; serves as regression guard.
  - `test_swap_disabled_when_flag_false` — set `wavesurfer.tone_reward_swap_enabled: false`, confirm loader returns the raw (un-swapped) mapping.

**Per-CLAUDE.md commit pattern:** single commit (`fix(phase-8a.10.1): swap Tone↔Reward channels at wavesurfer read time`).

### Task 2 — Phase 2 cohort-wide re-emit

**Files:**
- `scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py` (new) — driver that walks Q4-scope (animal, date) pairs, calls `process_session_by_animal_date` for each, writes outputs to the existing `pipeline_outputs/spout_behavior/licks_and_rewards/` paths (which overwrites the swapped baselines — confirm `overwrite="force"` semantics; Priya may want a sibling output tree for safety, see below).

**Output safety: LOCKED Option α — in-place overwrite.** Existing `pipeline_outputs/spout_behavior/licks_and_rewards/` files are overwritten with post-fix outputs. Pre-fix baselines recoverable from chore-emit PR git history + the per-session sha256 manifest emitted in Task 2.

**Wall-time estimate:** ~30-90 min depending on Q4 scope (341 sessions @ ~5-15 sec/session including I/O).

**Commit pattern:** `chore(phase-8a.10.1): Phase 2 cohort-wide re-emit post-swap-fix (N sessions)` — single commit, NPZ files (binary, large) are NOT committed to git; only the driver script + a summary manifest of (animal, date, pre-fix-sha256, post-fix-sha256) for audit purposes.

### Task 3 — Verification

**Steps:**

1. **Sample-comparison check.** For 5-10 sessions across animals + dates, load pre-fix and post-fix NPZs. Assert `rewards_idx_post == tones_idx_pre` and `tones_idx_post == rewards_idx_pre` element-wise. (The pre-fix NPZs are recoverable from `git show` on the chore-PR commits that emitted them, or via the manifest sha256 lookup.)

2. **Pulse-width ground-truth re-check.** Same 5-10 sessions, re-open raw `.h5`, confirm post-fix `rewards_idx` indices correspond to ~26 ms pulses (solenoid) and post-fix `tones_idx` indices correspond to ~200 ms pulses (auditory cue). Verifies the fix at the data-content level, not just at the array-position-swap level.

3. **Downstream-shift sanity check.** For 2-3 sessions, recompute Phase 8a.10 `accuracy_firstCorrectLickAll` on post-fix NPZs. Compare to pre-fix value. Expected shift: the "post-reward" window now actually starts at reward; first licks that previously fell in the pre-tone-but-pre-reward gap are no longer counted as "post-reward correct" because they're now pre-reward. Direction-of-shift will depend on per-session timing; just confirm the metric MOVES (it would be suspicious if it didn't).

**Commit pattern:** Verification scripts under `tests/scripts/phase_8a_10_1/`; STOP-and-report findings to Priya before Task 4.

### Task 4 — Phase 8a.10 figure re-render (LOCKED Q2.A)

Re-render sub-deliverable A (8 animals × 11 plot families) and sub-deliverable B (3 animals × 4-row + 2×2 per-trial) using the post-fix Phase 2 NPZs. Output paths unchanged (overwrites the `v8a.10-spout-visual-gate` figures in-place). Priya eyeball-verdict per family on the re-rendered figures.

Expected behavior change: Phase 8a.10's scientific message (spout-close-vs-standard excursion-limit demonstration) survives or strengthens. If it weakens or inverts, STOP-and-report — that's a separate scientific concern worth pausing for and discussing before phase close.

Per-family verdict mirrors Phase 8a.10 pattern (C1/C2 rounds if needed). Document new verdict in this phase's DECISIONS entry (supersedes Phase 8a.10's verdict table).

### Task 5 — Phase 3 alignment template re-emit (LOCKED Q1.A)

Re-emit Phase 3 alignment templates using post-fix Phase 2 tone timestamps. Output tree `pipeline_outputs/dlc_analysis/alignment_templates/`. ~341 templates (Cohort A) × ~10-30 sec each + Cohort B's 14 sessions. Output-safety mirrors Task 2: in-place overwrite; pre-fix templates recoverable from chore-emit git history.

Verification: spot-check 5-10 templates against post-fix Phase 2 NPZs — confirm alignment now anchors to actual tone-onset (the channel that was previously labeled "Reward"). Compare against pulse-width-confirmed raw `.h5` timing for the same sessions.

### Task 6 — DECISIONS + MIGRATION_LOG entries

**Path Y format (no `<FILL>` placeholders):**

`docs/DECISIONS.md` new top entry:

```markdown
## 2026-MM-DD — Phase 8a.10.1 close — Tone↔Reward swap fix at WS read-time + cohort-wide Phase 2 re-emit

**Phase metadata.** Branch `phase/8a.10.1-tone-reward-swap-fix`, opened 2026-MM-DD off main at the Phase 8a.10 merge commit. Tag `v8a.10.1-tone-reward-swap-fix` on the merge commit. Kickoff `docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md`.

### Decision 1 — Fix location: wavesurfer_io.py at channel-read mapping
[Single-point swap. No config flag. Rationale.]

### Decision 2 — Re-emit cohort scope: [Q4 verdict]
[Cohort A only / A+B / full YAML. Rationale.]

### Decision 3 — Output safety: [Option α/β]
[In-place overwrite vs parallel tree. Rationale.]

### Decision 4 — Phase 3 re-emit: [Q1 verdict]
### Decision 5 — Phase 8a.10 figure re-render: [Q2 verdict]
### Decision 6 — Phase 7/7a re-run: [Q3 verdict — deferred to follow-on phase if Q3.B]

### Enforced at
[Files list.]

### Findings carried forward
- Phase 7/7a re-run (if Q3.B).
- Phase 9 stats (still pending; now sits on top of corrected data).
- [Other forward-pointers.]
```

`docs/MIGRATION_LOG.md` append:

```markdown
## Phase 8a.10.1 — Tone↔Reward swap fix at WS read-time + cohort-wide Phase 2 re-emit

**Date:** 2026-MM-DD
**Tag on merge:** `v8a.10.1-tone-reward-swap-fix`
**Branch:** `phase/8a.10.1-tone-reward-swap-fix`

**Scope.** [2-3 sentence summary.]

**What landed.** [Per-file changes; ~5-10 source/test/script files + 3 docs.]

**Sessions re-emitted.** [N sessions across M animals; manifest at scripts/phase_8a_10_1/reemit_manifest.json.]

**Verification.** [Spot-check N=5-10 sessions; raw-data ground-truth re-check passed; downstream metric shifts in expected direction.]

**Intentional behavior differences vs legacy.** Legacy outputs also embed the swap (legacy was generated from the same swapped raw data). Post-fix outputs no longer align with legacy on tone/reward axes — this is an intentional correctness divergence, NOT a parity regression. Phase 8a.10's per-family parity gates were established under the swap; re-running them against post-fix outputs would show systematic shifts. Phase 7/7a baselines similarly. Address in follow-on phases.

**Exit criteria met.** [Checklist.]

**Forward-pointers queued.** [List.]

**Tag:** `v8a.10.1-tone-reward-swap-fix` on the merge commit.
```

### Task 7 — State-doc refresh + open PR

**Files:**
- `docs/COWORK_SESSION_STATE.md` — refresh per existing close-out pattern (banner / in-flight / next-phase candidates renumber / completed block / recent session log / 2026-MM-DD warm-start prompt prepended).
- `gh pr create` with body summarizing fix + re-emit + verification.

Path Y: PR body can reference `v8a.10.1-tone-reward-swap-fix` tag, but skips merge-SHA placeholders. No fill-in PR after merge.

---

## Scope NOT in this phase (forward-pointers)

1. **Phase 7 / 7a re-run.** If Q3.B locked, Phase 7 + all 7a.X analyses sit on top of corrected Phase 3 alignment templates but haven't been re-validated. Carve out as Phase 7b or similar.

2. **Legacy `session_processing3/` outputs.** These embed the same swap. We don't fix legacy outputs — they remain a historical reference for parity comparisons under the swap. Future phases that want to compare against legacy must do so on the now-superseded swapped axis, OR re-emit legacy in a follow-on chore (not 8a.10.1's job).

3. **Phase 9 stats.** Builds on top of corrected data; can proceed after this phase regardless of Q1/Q2/Q3 verdicts.

4. **111-session YAML-cohort gap chore.** Independent; covers sessions YAML lists but were never on disk. Doesn't conflict with the swap fix; can land before or after.

5. **Phase 7-pre-secondary-spout-compare-DLC.** Still blocked on b-half DLC inference.

6. **Pub-figures phase.** Builds on top of corrected data; can proceed after this phase.

---

## File-touch allowlist

Tasks 1-6 should touch ONLY these files (paths from repo root):

```
# Source
src/stroke_orofacial/io/wavesurfer_io.py                                    (single-point fix)
configs/defaults.yaml                                                        (optional, Priya-call: swap-enabled flag)

# Tests
tests/test_wavesurfer_io.py                                                  (regression pins)
tests/scripts/phase_8a_10_1/verify_swap_fix.py                              (new)
tests/scripts/phase_8a_10_1/manifest.json                                   (re-emit audit)

# Scripts
scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py                       (new; cohort re-emit driver)
scripts/phase_8a_10_1/audit_pulse_widths.py                                 (Task 0.5 driver)

# Docs
docs/DECISIONS.md
docs/MIGRATION_LOG.md
docs/COWORK_SESSION_STATE.md
docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md                  (THIS file)
```

Per Q1.A (Phase 3 re-emit — LOCKED):
```
scripts/phase_8a_10_1/reemit_phase_3_alignment_templates.py                 (new; Phase 3 re-emit driver)
```

Per Q2.A (Phase 8a.10 figure re-render — LOCKED):
```
src/stroke_orofacial/spout_behavior/visual_gate.py                          (NO source change — re-render only)
src/stroke_orofacial/spout_behavior/spout_close_vs_std.py                   (NO source change — re-render only)
notebooks/15_spout_behavior_visual_gate.ipynb                               (re-run only; no code change unless verdict surfaces a bug)
```

NO other files touched. Specifically:
- ANY edit to existing Phase 2/3/7/7a/8a source code (other than `wavesurfer_io.py`) — the fix is single-point.
- ANY edit to legacy `session_processing3/` outputs — they stay as historical reference.

---

## CLAUDE.md compliance checklist

Before every commit:
- [ ] `git branch --show-current` returns `phase/8a.10.1-tone-reward-swap-fix`.
- [ ] No source data modified (raw `.h5` + camera + DLC inference + alignment_templates pre-existing).
- [ ] No legacy-repo files modified.
- [ ] No files modified outside the touch allowlist above.
- [ ] Tests use `PathResolver(output_root=tmp_path)`.
- [ ] `pytest --collect-only` passes.
- [ ] `ruff check` clean on every touched source file.

Before the phase-close PR:
- [ ] Task 0.5 audit shows universal swap (or anomalies adjudicated).
- [ ] Task 1 fix + tests committed.
- [ ] Task 2 re-emit complete; manifest sha256-validated.
- [ ] Task 3 verification: spot-check passed; raw-data pulse-width confirms post-fix labels.
- [ ] Task 4 figure re-render (if Q2.A): per-family Priya eyeball-verdict.
- [ ] Task 5 Phase 3 re-emit (if Q1.A): manifest sha256-validated.
- [ ] DECISIONS + MIGRATION_LOG entries match Path Y format (no `<FILL>` placeholders).
- [ ] State-doc refresh complete with 2026-MM-DD warm-start prompt prepended.

---

## Forward-pointers (deliberately tracked, not in this phase)

1. **Phase 7 / 7a re-run** if Q3.B locked.
2. **Phase 9 stats** — playground cells 56-65 stat-inferential plots.
3. **111-session YAML-cohort gap chore.**
4. **Phase 7-pre-secondary-spout-compare-DLC** — blocked on b-half DLC inference.
5. **Pub-figures phase** — ipsi/contra labels via `stroke_laterality` scaffolding.

---

## Implementation-ready — all 8 decisions locked

| Decision | Verdict | Locked |
|---|---|---|
| Q1 (Phase 3 re-emit) | Q1.A — fold into 8a.10.1 | 2026-05-14 |
| Q2 (Phase 8a.10 figure re-render) | Q2.A — fold into 8a.10.1 | 2026-05-14 |
| Q3 (Phase 7 / 7a re-run) | Q3.B — defer to sibling phase | 2026-05-14 |
| Q4 (cohort scope) | Q4.B — A + B (~355 sessions) | 2026-05-14 |
| Q5 (tag convention) | Path Y — no `<FILL>` placeholders | 2026-05-14 |
| Task 2 output-safety | Option α — in-place overwrite | 2026-05-14 |
| Task 1 config flag | Opt-in flag `tone_reward_swap_enabled: true` | 2026-05-14 |
| Task 0.5 anomaly policy | A1 + A2 (STOP-and-report defaults); escalate to B1/B2 if ≥ 5 anomalies | 2026-05-14 |

**Next step: open the kickoff-doc PR** (`docs(phase-8a.10.1): kickoff doc`) targeting `main`. Mirrors the Phase 8a.10 PR #100 pattern (kickoff-doc PR merges first, then feature branch opens off the post-merge `main`).

After kickoff-doc PR merges: create feature branch `phase/8a.10.1-tone-reward-swap-fix`, start Task 0.5 (cohort-wide pulse-width audit on Cohort A + B — STOP-and-report).

---

## Addendum #1 — Task 0.5 PASS + Case-2-universal verdict + insert Task 0.75 consumer audit

**Date:** 2026-05-14.
**Trigger:** Task 0.5 PASS verdict + Priya 2026-05-14 confirmation that **Case 2 holds universally** — every legacy consumer of `rewards_idx` intended tone alignment, not reward-delivery alignment. The swap fix at WS read time will break every downstream consumer unless paired with coordinated consumer-side renames.

### Task 0.5 result (CLOSED, PASS)

- **Scope:** 271 raw `.h5` files on disk (255 Cohort A bare + 1 Pattern A half-a + 1 Pattern A half-b + 14 Cohort B b-half). Smaller than the kickoff's ~355 estimate because `iter_cohort_a_sessions` is filtered by on-disk Phase-2 NPZ existence (the 71-missing audit narrowed several sessions out).
- **Verdict:** 271/271 swap-confirmed. Zero Kind 1 (inverted-swap), zero Kind 2 (anomalous). Per-animal histograms are cleanly bimodal — every animal shows N pulses in `[20,30)` ms (rewards) and N pulses in `[180,220)` ms (tones), nothing in between.
- **Implication:** safe to apply unconditional single-point swap fix at WS read time. No exclusion list, no per-session config overrides required.
- **Artifacts** (gitignored, scratch): `.scratch_phase_8a_10_1/task_0_5_audit_report.md`, `.scratch_phase_8a_10_1/audit_pulse_widths.py`, `.scratch_phase_8a_10_1/per_file_results.json`.

### Scientific clarification: Case 2 holds universally (Priya 2026-05-14)

Every legacy consumer of `rewards_idx` was scientifically intended as tone-alignment. The variable name `rewards_idx` was chosen because the wavesurfer channel was *labeled* "Reward" — the original author trusted the label without verifying the pulse-width semantics. Cross-codebase:

- Trial alignment is to the **auditory cue (tone onset)** — animals respond to the tone; trial-window math is anchored there.
- "L / R reward trials" is a misnomer; the correct semantic is "L / R tone trials" (i.e., trials where the cue tone was on the L or R side).
- Criteria 3 window ("first lick within X seconds post-reward") is actually "first lick within X seconds **post-tone-onset**".
- Latency-bySession measures latency from tone-onset, not from reward delivery.
- Lick raster x-axis is tone-onset, not reward-delivery.

The new `rewards_idx` (which post-fix actually holds reward-delivery timestamps) is **currently not consumed by any analysis**. Reward delivery is a downstream consequence of correct licking, not an alignment anchor.

### Scope impact: consumer-side renames REQUIRED throughout

The Option 1 single-point fix claim ("Downstream code (Phase 3, Phase 7, Phase 8a) consumes `rewards_idx`/`tones_idx` by name and doesn't need to change") **is wrong** under Case 2. Every consumer of `rewards_idx` must rename to `tones_idx` to preserve scientific intent. Without the rename, post-fix code consumes actual reward delivery timestamps where it should be consuming tone-onset — silently producing incorrect downstream outputs.

**Estimated scope expansion:** kickoff originally estimated "small-to-mid" (~5-10 source/test/script files). With consumer renames, expand to **mid-to-large** (likely 15-40 source/test files touched). Consumer renames + WS swap fix ship together as a single coordinated PR for atomic semantic update.

### Insert Task 0.75 — Consumer audit (STOP-and-report)

Inserts between Task 0.5 (closed) and Task 1 (WS swap fix). Required to identify every Case-2 site before Task 1 implementation lands.

**Steps:**

1. Grep the codebase for every consumer of `rewards_idx`, `tones_idx`, and related access patterns:
   ```
   grep -rn "rewards_idx\|tones_idx\|Reward_L\|Reward_R\|Tone_L\|Tone_R\|reward.*idx\|tone.*idx" src/ tests/ scripts/ notebooks/
   ```
   Also check NPZ-key access patterns: `data\["rewards"\]`, `npz_data\[..."Reward"...\]`, etc.

2. For each consumer site, classify:
   - **Case-1 (rare):** code is correctly named for its scientific intent. Variable name matches what the code intends to do (e.g., a hypothetical "time-from-reward-delivery-to-next-trial-start" analysis using `rewards_idx` would be correctly named). **No rename needed.**
   - **Case-2 (expected default):** variable name diverges from scientific intent. Code uses `rewards_idx` but intends tone alignment. **Rename: `rewards_idx` → `tones_idx`** (and any related downstream variable / key / docstring / comment).

3. Special attention to:
   - `src/stroke_orofacial/spout_behavior/visual_gate.py` — `compute_first_lick_correct`, `compute_trial_lick_delays`, `compute_first_correct_lick_sample_idx`, `compute_criteria_3`, `compute_criteria_4`, `compute_criteria_34`, `compute_criteria_acc_bySession`, `compute_firstLickCorrect_bySession`, `compute_median_lick_rate_bySession`, `compute_num_licks_bySession`, `compute_latency_bySession`. The "post-reward" window definitions are the highest-density Case-2 sites.
   - `src/stroke_orofacial/spout_behavior/session_processing.py`, `session_manifest.py`, `endpoints_writer.py`.
   - `src/stroke_orofacial/spout_behavior/criteria.py`.
   - `src/stroke_orofacial/dlc_analysis/alignment_templates*.py` — Phase 3 alignment is to the auditory cue.
   - `src/stroke_orofacial/io/wavesurfer_io.py` itself — variable names in the reader may be misleading.
   - `notebooks/15_spout_behavior_visual_gate.ipynb` — USER INPUTS + orchestration.
   - All NPZ schema documentation in `docs/`.
   - All tests under `tests/` that pin the field names.

4. Also check for downstream variable names derived from `rewards_idx`/`tones_idx`:
   - `data.rewards_idx`, `SessionPlotData.rewards_idx` field name in dataclass — needs rename
   - `trial_lick_delays["Reward_L"]`, `trial_lick_delays["Reward_R"]` dict keys — needs rename to `"Tone_L"`, `"Tone_R"`
   - `Lick_L`, `Lick_R` — these reference lick-side, not reward-side; leave as-is
   - `side_reward` loop variable names — semantically about which cue side; rename to `side_tone` if it tracks the cue side

5. NPZ-on-disk key rename considerations:
   - The Phase 2 emitter writes NPZ files with `rewards_idx`, `tones_idx` keys. After Task 1, the emitter swaps content correctly (rewards_idx holds reward-delivery; tones_idx holds tone-onset).
   - If consumer code is also renamed (rewards_idx → tones_idx in source), the NPZ-on-disk schema must align: the on-disk key consumed by tone-alignment code must be `tones_idx`. Post-fix Phase 2 emission writes the on-disk `tones_idx` key with the (newly correct) tone content. Consumer reads `tones_idx`. ✓
   - The new `rewards_idx` on-disk key (holding actual reward-delivery) has no current consumer but is preserved for future use (Phase 9 stats may want it; pub-figures may want it for "time-to-reward" plots).

**STOP-and-report deliverable** to `.scratch_phase_8a_10_1/task_0_75_consumer_audit.md`:

- Per-consumer-site classification: Case 1 vs Case 2.
- Recommended remediation per Case 2 site (rename target).
- Estimated total source-file touch count.
- Any sites where Case 1 vs Case 2 classification is ambiguous → STOP-and-ask Priya (per CLAUDE.md ground rule 5).
- Highest-risk sites called out explicitly (criteria definitions, alignment generation, NPZ schema).
- Recommended ordering for Task 1 implementation (e.g., "rename in `visual_gate.py` first, then propagate to tests, then notebooks").

Task 0.75 produces zero commits on the feature branch. The audit report lives under `.scratch_phase_8a_10_1/` (matches Task 0.5 convention).

### Task 1 scope expansion (per Task 0.75 verdict)

Task 1 (originally "WS read-time swap fix + unit tests") expands to include consumer-side renames as coordinated commits in the same PR. New scope:

1. **Commit A — WS swap fix.** `src/stroke_orofacial/io/wavesurfer_io.py` single-point swap + `configs/defaults.yaml` opt-in flag + `tests/test_wavesurfer_io.py` regression pins. ~30-50 LoC.
2. **Commit B — Consumer renames per Task 0.75 audit.** Mass rename across `src/stroke_orofacial/`, `tests/`, `notebooks/`. ~15-40 files. Use a checklist from Task 0.75 to ensure no consumer is missed.
3. **Commit C — Test sync.** Update test pins that reference the old field names. Update mock/fixture data NPZ schema if applicable.
4. **Commit D — Docstring + comment sync.** Update inline comments referencing "post-reward" → "post-tone" wherever scientific intent is tone alignment. Update DESIGN.md / module docstrings.

Per-commit commit pattern allows clean review + easy revert of individual layers if Task 4 verdict surfaces issues.

### Task 4 watch-item: threshold tuning

Even with consumer renames correctly preserving scientific intent (tone alignment), some endpoint **thresholds** may have been empirically tuned to swapped data. Example:
- Criteria 3 time-window `X` was tuned for "first lick within X seconds post-`rewards_idx`" — but pre-fix `rewards_idx` was tone-onset, so X was tuned for tone-anchored behavior.
- Post-fix with consumer rename: code says "first lick within X seconds post-`tones_idx`" — still tone-anchored, same intent. **Threshold X transfers correctly.** ✓

No threshold re-tuning expected if Case 2 is universal — the rename + swap together preserve the original tone-anchored semantics. Task 4 figure re-render should reproduce Phase 8a.10's results closely (modulo any small content-change effects from the new actual-reward channel being available, which no current consumer uses).

If Task 4 surfaces large unexpected metric shifts: that's a signal something was Case 1 (not Case 2) and got incorrectly renamed. STOP-and-report.

### Updated file-touch allowlist (Phase 8a.10.1 with Task 0.75 + expanded Task 1)

Per Task 0.75 verdict, the allowlist expands to encompass all Case-2 consumer sites. The original allowlist (lines under §"File-touch allowlist") becomes a *minimum* set; Task 0.75's audit report defines the *actual* set. Explicit allow-list addition for the consumer renames:

```
src/stroke_orofacial/spout_behavior/visual_gate.py         (consumer renames; field rename in SessionPlotData)
src/stroke_orofacial/spout_behavior/criteria.py            (criteria_3, criteria_4 semantics)
src/stroke_orofacial/spout_behavior/endpoints_writer.py    (endpoint name + content sync)
src/stroke_orofacial/spout_behavior/session_processing.py  (Phase 2 emitter; rewards_idx vs tones_idx on-disk keys)
src/stroke_orofacial/spout_behavior/session_manifest.py    (any reward/tone references)
src/stroke_orofacial/spout_behavior/spout_close_vs_std.py  (Cohort B renderer; consumers of trial-lick delays)
src/stroke_orofacial/spout_behavior/cohort_summary.py      (sub-A cohort tiler)
src/stroke_orofacial/dlc_analysis/alignment_templates*.py  (Phase 3 alignment generation)
notebooks/15_spout_behavior_visual_gate.ipynb              (orchestration + USER INPUTS naming)
tests/test_visual_gate.py, test_spout_close_vs_std.py, test_criteria.py, test_endpoints_writer.py  (test pins)
```

Per Task 0.75 audit, additional files surface — those land in the same PR per coordinated atomic update.

### Updated estimated scope

| Item | Pre-Addendum-#1 estimate | Post-Addendum-#1 estimate |
|---|---|---|
| Source/test/script files touched | ~5-10 | ~15-40 |
| LoC delta | ~100-300 | ~500-1500 |
| Wall time | 1-3 days CC + verification | 3-5 days CC + verification |
| Verdict mechanism | Task 4 figure re-render | Same; figure re-render now also doubles as Case-2-remediation verification |

### Addendum #1 ALL OTHER LOCKS UNCHANGED

All 8 prior decisions hold: Q1.A (Phase 3 re-emit), Q2.A (figure re-render), Q3.B (Phase 7/7a defer), Q4.B (~355 sessions narrowed to 271 on-disk), Path Y (no `<FILL>`), Option α (in-place overwrite), opt-in flag default true, A1+A2 anomaly defaults (moot post-Task-0.5).

---

## Addendum #2 — DLC consumer spot-check + cascade-safety gate

**Date:** 2026-05-14.
**Trigger:** Q3.B locks Phase 7/7a re-run as deferred to a sibling phase, BUT the Phase 2 NPZ key rename in Task 1 Commit B will silently change what DLC consumers read. If `dlc_spatial/reward_aligned.py`, `dlc_kinematics/reward_aligned.py`, `dlc_kinematics/tongue_pertrial.py`, or `dlc_kinematics/interpolation.py` touch the renamed NPZ keys (`Reward_L` / `Reward_R`), they'll silently switch from consuming tone events to consuming actual reward-delivery events. The file names alone (`*reward_aligned*`) strongly suggest Case 2 — DLC trial alignment was intended to be tone-anchored (auditory cue → DLC frame windows) but named after the bug-labeled channel.

### Risk model

Two cascade-failure scenarios:

- **Scenario A (acute):** DLC code reads Phase 2 NPZ key `Reward_L`/`Reward_R` (or `rewards_idx`-derived data) directly. Post-Task-2 re-emit, those keys hold actual reward-delivery timestamps. DLC silently consumes wrong content. Next Phase 7 run produces incorrect outputs. **Q3.B doesn't protect against this — the deferral is about Phase 7 *re-run*, not about future Phase 7 runs picking up a corrupted Phase 2 schema.**

- **Scenario B (less acute):** DLC code consumes Phase 3 alignment templates. After Q1.A Task 5 re-emit, templates anchor to corrected tone-onset (was: reward-anchored via the bug). The alignment shifts ~150-300 ms cohort-wide. DLC code itself doesn't break syntactically; its OUTPUTS shift. This is the alignment-shift effect Q3.B explicitly defers.

### Insert Task 0.85 — DLC consumer spot-check (STOP-and-report)

Inserts between Task 0.75 (consumer audit, complete) and Task 1 (WS swap fix). Determines whether Q3.B's deferral interacts with the Phase 2 NPZ schema rename in a way that requires scoping decisions before Task 1 starts.

**Steps:**

1. Grep DLC code for NPZ-key access patterns AND Phase 2 derived data consumption:
   ```
   grep -rn "Reward_L\|Reward_R\|Tone_L\|Tone_R\|rewards_idx\|tones_idx\|reward.*indices\|tone.*indices" \
     src/stroke_orofacial/dlc_*/ \
     tests/test_dlc_*.py
   ```
   Also check whether DLC code calls into `spout_behavior` functions that derive from these keys (e.g., `compute_trial_lick_delays`, `compute_first_correct_lick_sample_idx`).

2. For each DLC consumer site, classify:
   - **Pure Phase-3 consumer:** reads `alignment_templates/` only; doesn't touch Phase 2 NPZ keys. Scenario B applies; Q3.B-deferred behavior.
   - **Phase-2 NPZ-key consumer:** reads `Reward_L`/`Reward_R` or `rewards_idx`/`tones_idx` directly. Scenario A applies — silent-break risk.
   - **Indirect Phase-2 consumer:** calls into `spout_behavior` functions that derive from these keys. Scenario A applies via dependency chain.

3. For each Scenario-A site, classify Case 1 vs Case 2 (same convention as Task 0.75 — does the variable/key access pattern match scientific intent?).

**STOP-and-report deliverable** to `.scratch_phase_8a_10_1/task_0_85_dlc_consumer_audit.md`:

- Per-DLC-file enumeration of consumer sites + classification.
- Count of Scenario-A vs Scenario-B sites.
- For each Scenario-A + Case-2 site: recommended remediation.
- Scoping recommendation: which of the options below fits best given the audit.

### Scoping options (Priya decides at Task 0.85 STOP-and-report)

- **Option X1 — Selective Q3.B revoke.** Fold the affected DLC files into Phase 8a.10.1 Task 1 Commit B as additional renames. Pros: completes the Case-2 cleanup atomically; no backward-compat schema needed. Cons: contradicts Q3.B; expands scope mid-phase.
- **Option X2 — Backward-compat NPZ schema.** Phase 2 emitter writes both renamed-canonical keys (`Tone_L`/`Tone_R` for tone events; `Reward_L`/`Reward_R` for actual reward delivery) AND legacy-alias keys that point to the correct content under the old names (e.g., `Reward_L_TONE_LEGACY_ALIAS` pointing to the tone events that DLC code currently reads via `Reward_L`). DLC code keeps reading the legacy alias until Phase 7b. Pros: preserves Q3.B literally. Cons: schema pollution; legacy aliases ossify; needs explicit cleanup in Phase 7b.
- **Option X3 — DLC feature flag.** Add `dlc_analysis.enabled: false` (or similar) to `defaults.yaml`; Phase 8a.10.1 sets it false. DLC code stays untouched but is gated off until Phase 7b explicitly re-enables. Pros: lowest scope-creep risk. Cons: any active DLC consumer (notebook, downstream code) needs to explicitly opt out / handle the gate.
- **Option X4 — Defer Task 2 re-emit narrowing.** Only re-emit the Phase 2 NPZs that aren't read by current DLC consumers; leave the rest as pre-fix. Pros: minimal blast radius. Cons: pipeline now has heterogeneous Phase 2 NPZs across the cohort. Highly problematic for any cohort-wide analysis.

I lean **X1 (selective Q3.B revoke)** if the Scenario-A + Case-2 site count is small (say, ≤ 4 files — which matches the deferred list in Q3.B exactly). The Q3.B deferral was about avoiding the Phase 7 *re-run* (which involves re-baselining 7a parity gates), not about leaving the DLC source code in a broken state. Renaming DLC consumers to match the new NPZ schema is a small surgical fix that doesn't trigger 7a parity re-baselining — that's a separate concern, deferred to Phase 7b.

If the audit surfaces > 4 Scenario-A files, X2 (backward-compat schema) becomes more attractive.

### Insert Task 4.5 — DLC spot-check on post-fix data (between Tasks 4 and 5)

After Phase 8a.10 figures re-render (Task 4) and before Phase 3 alignment template re-emit (Task 5), sanity-run the DLC code on 1-3 sessions using post-fix Phase 2 NPZs:

1. Pick 1-3 sessions across animals (e.g., one PS46 + one PS50 + one PS55).
2. Run whatever DLC analysis is currently runnable (per Q3.B, no FULL re-run — just spot-check that the code executes without crashing on post-fix NPZs + plots render and look qualitatively reasonable).
3. Compare to pre-fix DLC outputs for the same sessions. The outputs SHOULD differ (alignment shifted), but the code should not crash, NaN out, or produce wildly anomalous values.

**STOP-and-report:** post-spot-check verdict. If DLC outputs look sensible → proceed to Task 5 (Phase 3 alignment template re-emit). If anything looks broken → diagnose and decide whether to (a) hot-fix the DLC consumer in 8a.10.1 (further Q3.B revoke), (b) gate the broken DLC paths with a feature flag, (c) STOP-and-report wider for Priya scope-decision.

Task 4.5 deliverable lives at `.scratch_phase_8a_10_1/task_4_5_dlc_spot_check.md`.

### Updated execute flow

```
Task 0    (Setup)
Task 0.5  (Pulse-width audit) — CLOSED
Task 0.75 (Consumer audit) — CLOSED
Task 0.85 (DLC consumer spot-check audit) — INSERT, STOP-and-report
Task 1    (WS swap fix + spout_behavior consumer renames)
  Commit A    WS swap fix + flag + verification on 5-10 NPZs
  Commit B    Consumer renames per Task 0.75 + Task 0.85 verdict
  Commit C    Test sync
  Commit D    Docstring + docs/ polish
Task 2    (Phase 2 cohort-wide re-emit, ~271 sessions)
Task 3    (Verification — spot-check + downstream-shift)
Task 4    (Phase 8a.10 figure re-render — Q2.A)
Task 4.5  (DLC spot-check on post-fix data) — INSERT, STOP-and-report
Task 5    (Phase 3 alignment template re-emit — Q1.A)
Task 6    (DECISIONS + MIGRATION_LOG)
Task 7    (State-doc refresh + PR)
```

### Addendum #2 ALL OTHER LOCKS UNCHANGED

All Addendum #1 outcomes preserved. The DLC consumer spot-check is a scope-CLARIFY at the Q3.B / Task 2 interface, not a scope-CHANGE. If Task 0.85 audit surfaces no Scenario-A + Case-2 sites, the cascade-safety gate is satisfied trivially and Q3.B holds verbatim.

---

## Addendum #3 — Q1.A reversal: Phase 3 alignment is Sync-anchored, not Tone-anchored

**Date:** 2026-05-14.
**Trigger:** CC's Task 5 scope/premise audit before kicking off the Phase 3 alignment template re-emit. The audit surfaced that the Q1.A re-emit lock was based on a wrong premise about Phase 3's data dependency.

### Finding

The Phase 3 alignment template builder (`src/stroke_orofacial/alignment/frame_sync.py:143 make_alignment_template`) reads:
- `ws_signals["Sync_signal"]` (camera-frame TTL from the Phase 1 `wavesurfer_signals_processed` NPZ tree)
- Raw camera CSV from Rich's read-only tree

Neither input is touched by the Tone↔Reward swap fix. The alignment template is a frame-to-sample mapping derived purely from the sync TTL; it does NOT consume the `Tone_L`/`Tone_R`/`Reward_L`/`Reward_R` keys whose semantics changed in Task 2.

### Data-flow chain (corrected)

- **Phase 1** (`wavesurfer_signals_processed` containing `Sync_signal`) → unchanged by swap fix (not re-emitted by Task 2; pre-dates the swap fix).
- **Phase 3 alignment templates** (built from Phase 1 `Sync_signal`) → **unchanged by swap fix**. Byte-identical pre/post-fix on all 276 sessions.
- **Phase 2** (`Tone_L`/`Reward_L` etc. in `licks_and_rewards` NPZ) → changed by swap fix (Task 2 re-emit handled this).
- **Phase 7 DLC analyses** (read Phase 2 Tone events via Phase 3 alignment templates as a frame-lookup) → potentially changed on withhold sessions. Task 4.5 DLC spot-check already verified this layer.

The swap-fix propagation stops at Phase 2. Phase 3 sits upstream of the tone/reward axis entirely.

### Q1.A re-emit was unnecessary

The original Q1.A justification ("Phase 3 templates feed Phase 7 DLC kinematics + any downstream alignment-dependent analysis; carrying swapped templates forward bakes the swap into more outputs") was wrong. Phase 3 templates are sync-anchored frame mappings, not tone-anchored event windows. The swap doesn't propagate through them.

Additional findings:
- The on-disk new-tree (`pipeline_outputs/dlc_analysis/alignment_templates/cam2/`) has only 3 templates (from the 2026-05-05 incident-response restore for PS48). Every production DLC consumer reads from the legacy tree (`O2_analysis/alignment_templates/cam2/`, 345 templates) via `alignment_template_legacy_read()`. The new-tree cutover is out of scope per Q3.B (Phase 7b-light).
- Re-emitting 276 templates would produce byte-identical orphan outputs in a tree no production code reads.

### Decision: SKIP Task 5

Task 5 is reversed from execute to skip. Q1.A as locked in the kickoff body is overridden by this addendum. Rationale:

- Phase 3 alignment templates are unchanged by the swap fix (sync-anchored, not tone-anchored).
- Re-emit produces orphan outputs (no production consumer reads the new tree).
- Wall time saved: ~30-90 min.
- No scientific loss: byte-identical outputs aren't scientifically meaningful re-validation.

### Updated execute flow (post-Addendum-#3)

```
Task 0    (Setup) — CLOSED
Task 0.5  (Pulse-width audit) — CLOSED
Task 0.75 (Consumer audit) — CLOSED
Task 0.85 (DLC consumer spot-check audit) — CLOSED
Task 1    (WS swap fix + spout_behavior consumer renames) — CLOSED
Task 2    (Phase 2 cohort-wide re-emit, 276 sessions) — CLOSED
Task 3    (Verification — sample-comparison + raw-data + downstream-shift) — CLOSED
Task 4    (Phase 8a.10 figure re-render — Q2.A) — CLOSED
Task 4.5  (DLC spot-check on post-fix data) — CLOSED
Task 5    (Phase 3 alignment template re-emit — Q1.A) — SKIPPED per Addendum #3
Task 6    (DECISIONS + MIGRATION_LOG)
Task 7    (State-doc refresh + PR open)
```

### Implication for Phase 7b-light forward-pointer

If Phase 7b-light or a later phase cuts DLC consumers over from the legacy alignment-templates tree to the new tree, that future phase will need to populate the new tree at that time. The Phase 3 builder is ready (the 3 incident-response templates and CC's Task 5 audit confirm the builder runs end-to-end); only the cohort-wide population would need to happen.

This is captured as a forward-pointer in the Phase 8a.10.1 close-out DECISIONS entry — sibling to the existing Phase 7b-light + Phase 7-pre-multi-half-dlc forward-pointers.

### Addendum #3 ALL OTHER LOCKS UNCHANGED

All Addendum #1 and #2 outcomes preserved. The Q1.A re-emit decision is the only lock reversed; everything else (consumer renames, Phase 2 re-emit, Phase 8a.10 figure re-render, DLC spot-check) holds.
