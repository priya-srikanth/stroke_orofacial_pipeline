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
