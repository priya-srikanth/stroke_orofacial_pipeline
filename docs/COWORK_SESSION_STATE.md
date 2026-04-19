# Cowork Session State

This file is the single warm-start document for a new Cowork session. Paste this into a fresh Cowork chat to pick up where the previous one left off:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full before answering any questions.

It captures what a new Cowork session needs beyond what's already in the canonical docs (`CLAUDE.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/MIGRATION_LOG.md`): current phase state, active tasks, open decisions awaiting human input, recent decisions pending transcription, and operational knowledge (two-tool workflow, env setup, known gotchas).

**Maintenance rule.** Cowork updates this file (a) at the end of every meaningful session, and (b) mid-session when a major decision lands. The "current state" and "active tasks" sections should never be stale by more than one session.

---

## Warm-start checklist

A new Cowork session works through this in order before doing anything else:

1. Read `CLAUDE.md` — project ground rules (apply to any code-execution path, including Claude Code in VSCode that Cowork hands off to).
2. Read `docs/DESIGN.md` — full phase plan, architecture, cohort details.
3. Read `docs/DECISIONS.md` — decisions record (append-only).
4. Read `docs/MIGRATION_LOG.md` — scan the last 2–3 phase entries for recent delivery context.
5. Read the "Current state" and "Active tasks" sections of this file.
6. Read "Open decisions awaiting human input" and "Recent decisions (not yet in DECISIONS.md)" — these are the time-sensitive items.
7. Skim "Operational knowledge" if unfamiliar with the two-tool workflow.
8. Ask Priya if the in-flight item listed under "Current state" is still live or has moved on since the last maintenance entry.

---

## Current state

**As of:** 2026-04-17 (end-of-session snapshot)

**Repo phase:** Mid-consolidation audit in progress (Items 1–10). Phases 1 through 6 delivered and on `main`.

**Current branch:** `audit-item-6-phase5-details` (off `main` at tag `v0.6-phase-6-complete`). Has uncommitted or partially-committed experimental notebook work from this session (the eye-affine exploration and the cross-session alignment sweep notebook).

**In flight when last updated:** Cross-session alignment regime sweep notebook (`notebooks/experiments/cross_session_alignment_sweep.ipynb`) running in VSCode Claude Code as background task. Execution pattern: `jupyter nbconvert --to notebook --execute --inplace` in the `frsb` conda env. Expected outputs under `notebooks/experiments/outputs/alignment_sweep/` (three top-level figures + per-animal subfolders + `summary.txt`). Purpose: inform Phase 4.5 (eye-affine cross-session alignment) decision.

**Completed this session (summary):**

- Audit Item 1 — renamed `pipeline_outputs_v2` → `stroke_orofacial_pipeline_outputs` throughout configs + code.
- Audit Item 2 — per-camera alignment template directory structure under `cam2/templates/`.
- Audit Item 3 — decision to wire `SessionManifest` in properly via Phase 6.7 refactor (kickoff prompt drafted at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`).
- Audit Item 4 — `load_centered_fresh()` utility specced into Phase 6.7c (on-the-fly centering for interactive exploration, complements parquets).
- Audit Item 5 — Phase 8 split into 8a (spout-only, moved ahead of Phase 7) and 8b (DLC-dependent).
- Audit Item 6 sub-decisions:
  - 6.4: fine-grid heatmap NPZ arrays saved alongside PNGs (added to Phase 6.7d scope).
  - 6.6: all-bodyparts overlay heatmap with per-bodypart colormaps, L/R pairs share colormap, eyes/spouts excluded by default.
  - 6.7: single-animal eye-affine experiment notebook (PS46) — executed, committed. Now generalized to a full-cohort sweep (in flight).
- `configs/defaults.yaml` dead-placeholder `dlc.bodyparts` block corrected to canonical names (was stale `medial_edge_*` / `whisker_L1` / `spout_L` — now `L_eye` / `L_whiskers_1` / `L_spout` etc.). The block wasn't consumed by any code but was actively misleading for future drafters.

---

## Active task list

The authoritative source is the Cowork TaskList widget in the current session. Mirrored here for persistence across sessions.

**In progress:**

1. Run cross-session alignment sweep notebook (background in VSCode Claude Code).

**Next up (blocked on sweep completing):**

2. Commit sweep notebook + outputs on `audit-item-6-phase5-details` (two commits: notebook, then outputs).
3. Decide Phase 4.5 scope based on sweep results — one of:
   - **Build**: `eye_affine` dominates → write `docs/prompts/phase-4.5-eye-affine-alignment-kickoff.md`.
   - **Build-lite**: `eye_centered` ≈ `eye_affine` and both beat `spout_centered` → write Phase 4.5-lite kickoff (eye-midpoint centering only).
   - **Skip**: regimes indistinguishable → close the observation with a `DECISIONS.md` entry, no new phase.

**Remaining audit items:**

4. Item 7 — Phase 6 (reward-aligned DLC) details review. Mirror of Item 6 but for `reward_aligned.py`, `configs/defaults.yaml` `dlc_spatial_reward_aligned` block, `notebooks/12_dlc_spatial_reward_aligned.ipynb`.
5. Item 8 — Phase 5.5 SSH-from-notebook workflow. Standardize how notebooks invoke O2 (HMS cluster) operations. Likely a thin wrapper in `src/stroke_orofacial/dlc_inference_o2/`.
6. Item 9 — SVG outputs + figure-folder reorganization. Add SVG alongside every PNG, reorganize output dirs by figure-type for publication assembly.
7. Item 10 — Scientific endpoints review. Catalog all endpoints (tests, stratifications, recovery-phenotype splits) from legacy code into a new section of `docs/DESIGN.md`. Feeds into Phase 10 (full scientific audit).

**Audit wrap-up gate:**

8. Merge `audit-item-6-phase5-details` → `main`, tag `v0.6.5-audit-complete`. Blocked on #2–#7 all resolving.

**Queued phases (all blocked on #8 — the audit merge gate):**

9. Phase 6.7 — SessionManifest refactor execution. Kickoff prompt already written at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`. Sub-phases 6.7a–6.7e; pause after 6.7a for Priya mid-phase review.
10. Phase 8a — spout-only recovery trajectories. High-priority mid-experiment deliverable (lets Priya review recovery patterns while experiments continue). Moved ahead of Phase 7 per earlier decision.
11. Phase 7 — reward-aligned DLC cohort extension. Extend Phase 6 (PS46-only) to full 8-animal cohort. Blocked on #9 + #10.
12. Phase 8b / 9 / 10 bundle — DLC-dependent recovery trajectories, fine-grid spatial statistics, full scientific audit. Blocked on #11. Each will get its own kickoff prompt when it's time.

**Phase-transition rule:** no new phase starts until the audit branch is merged to main and tagged. Keeps the audit as one atomic chunk rather than interleaving with new-phase work.

---

## Open decisions awaiting human input

*(Empty at the moment. All in-flight items have default directions Cowork can execute without Priya's input unless a specific blocker surfaces.)*

When a decision point appears that genuinely needs Priya:

- List it here with the question, the options, and Cowork's tentative recommendation.
- Mark the related task as `pending` with a `blockedBy` pointing to a stub "decision: X" task.
- Don't make the call unilaterally.

---

## Recent decisions (pending transcription into `docs/DECISIONS.md`)

These were decided this session but haven't yet been written into the canonical decisions record. Next maintenance pass should transcribe and delete from this section.

- **Per-animal reference frame for eye-affine alignment** = mean of all pre-stroke session eye medians (more robust to per-session DLC noise than any single-session anchor). One-line toggle in USER INPUTS to flip back to last-pre-stroke-session if needed.
- **Alignment regime sweep scope** = all 8 animals × all sessions in each animal's recording range × 9 bodyparts × 3 regimes (`eye_affine`, `eye_centered`, `spout_centered`).
- **Primary sweep metrics** = mean pairwise Pearson r (higher = better) + mean pairwise Jensen-Shannon divergence (lower = better) of flattened normalized 2D histograms across sessions.
- **Phase 4.5 will be scoped post-sweep**, not predetermined. Decision tree documented in task #3 above.
- **`configs/defaults.yaml` canonical bodypart roster** (lines 240–255) corrected to match the DLC model output: L_eye, R_eye, L_spout, R_spout, nose, jaw, tongue, L_whiskers_{1,2,3}, R_whiskers_{1,2,3}. The stale placeholder names (`medial_edge_L_eye`, `whisker_L1`, `spout_L`, etc.) had no downstream code consumer but were misleading. The block is now canonical documentation of the DLC roster.

---

## Operational knowledge

### Two-tool workflow

**Cowork (this chat)** is the advisor/reviewer. It has:

- Read/write access to the repo folder (`/Volumes/Neurobio/MICROSCOPE/Priya` is NOT mounted in Cowork's sandbox).
- No conda env; only a minimal Python sandbox without DLC dependencies.
- A TaskList widget for tracking state across tool calls within one session.

**Claude Code in VSCode** (on Priya's Mac) is the executor. It has:

- The `frsb` conda env with pandas / numpy / matplotlib / h5py / tables / pyarrow / jupyter / nbconvert.
- Live SMB mount to `/Volumes/Neurobio/MICROSCOPE/Priya` (assumes the Mac is awake; remount after sleep).
- The repo checked out.
- Git access with `.githooks/pre-commit` that blocks direct commits to `main` / `master`.

**Handoff pattern.** Cowork drafts "paste-in prompts" (usually in block-quote form) that Priya pastes into the Claude Code sidebar in VSCode. Claude Code reports back to Priya; she relays the summary to Cowork. Cowork reads committed outputs directly from its folder view of the repo — no separate upload step.

### Opening Claude Code in VSCode

1. File → Open Folder → select the `stroke_orofacial_pipeline` repo.
2. Open the integrated terminal (Ctrl+backtick) and `conda activate frsb`. This ensures Claude Code inherits the right env when it shells out.
3. Cmd+Esc toggles the Claude Code sidebar. Command Palette ("Claude Code: Focus") is a fallback.
4. Paste the prompt into the chat input at the bottom of the sidebar.

### SMB mount health

- Path: `/Volumes/Neurobio/MICROSCOPE/Priya`.
- Goes stale after the Mac sleeps. Symptoms: long hangs, permission errors, or empty `ls`.
- Fix: `diskutil unmount /Volumes/Neurobio` then Finder → Go → Connect to Server → reconnect to the research fileserver.

### nbconvert streaming quirk

- `jupyter nbconvert --execute --inplace` does NOT stream cell stdout. Cell prints are buffered until the whole notebook is written back at the end.
- To see live per-cell progress, use: `jupyter nbconvert --to script <nb.ipynb> --stdout | python -u 2>&1 | tee /tmp/run.log`. Then rerun with `--execute --inplace` so outputs get baked into the `.ipynb` for commit.

### Memory footprint heuristic (for sweep-style notebooks)

- ~1 MB per (session, bodypart, regime) of aligned-point arrays at steady state.
- For the alignment sweep: 8 animals × 9 bodyparts × 3 regimes × ~30 sessions ≈ 6–8 GB RSS. Plateaus, doesn't grow unbounded.
- On ≥16 GB machines: no swap concerns. On 8 GB machines: expect swap under sweep-style runs.

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
- Phase kickoff prompts (Cowork → Claude Code handoffs): `docs/prompts/phase-*-kickoff.md`.
- Cowork session state (this file): `docs/COWORK_SESSION_STATE.md`.
- Data model doc: `docs/DATA_MODEL.md`.
- Stats pipeline doc: `docs/STATS_PIPELINE.md`.
- Configs: `configs/animals.yaml`, `configs/defaults.yaml`, `configs/paths.yaml`, `configs/session_overrides.yaml`.
- Experimental (throwaway) notebooks: `notebooks/experiments/`.
- Production notebooks: `notebooks/*.ipynb`.
- Pipeline outputs on MICROSCOPE: `/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/`.

---

## Cowork-on-Windows status (as of 2026-04-19)

**Do not attempt to get Cowork working on Priya's Windows Enterprise machine.**

Extensive troubleshooting on 2026-04-19 did not yield a working Cowork install on
Windows despite:

- Windows 11 Enterprise edition (correct tier for Hyper-V).
- Max subscription confirmed at account level.
- Claude Desktop 1.3109.0 (current release).
- Hyper-V enabled and running (`vmms` and `vmcompute` services both `Running`,
  `systeminfo` confirms "A hypervisor has been detected").
- Computer use toggled on in Settings.
- Clean full reinstall of Claude Desktop with cache-directory wipe
  (`%APPDATA%\Claude`, `%LOCALAPPDATA%\Claude`) after Hyper-V activation.
- Sign-out / sign-back-in.

Result: no Cowork tab appears in the Windows desktop app. The Claude VM
(`yukonSilver` or equivalent) is never provisioned (`Get-VM` returns nothing).
Likely cause is an account-level feature flag or staged-rollout gate that
Anthropic controls server-side. Would require a support-ticket conversation
with Anthropic to resolve, which is deferred indefinitely.

**Permanent workflow is Mac Cowork + Windows Claude Code in VSCode.** See
"Two-tool workflow" section below for details. When Cowork writes new files
(DECISIONS updates, kickoff prompts, etc.), Priya runs a 30-second
`git add / commit / push` on her Mac, then `git pull` on Windows. This is the
only friction added by the split.

---

## Known gotchas

- **`configs/defaults.yaml` naming consistency.** The live spatial blocks (lines 94–178, 195–228) use canonical bodypart names. The `dlc.bodyparts` block (lines 240–255) was stale placeholder text corrected this session. If another stale block appears, prefer names from an actual DLC H5 file via the diagnostic in cell 3 of the eye-affine experiment notebook.
- **nbconvert stdout buffering.** See "Operational knowledge → nbconvert streaming quirk" above.
- **SMB mount stale-after-sleep.** See "Operational knowledge → SMB mount health" above.
- **Plot file paths under `nbconvert`.** Jupyter's `__file__` is not defined inside a kernel. Robust pattern for notebook output dirs:
  ```python
  _cwd = Path.cwd().resolve()
  if _cwd.name == "experiments" and _cwd.parent.name == "notebooks":
      OUTPUT_DIR = _cwd / "outputs" / "<experiment_name>"
  else:
      OUTPUT_DIR = _cwd / "notebooks" / "experiments" / "outputs" / "<experiment_name>"
  ```
- **Whiskers naming.** The DLC model uses `L_whiskers_1` (plural "whiskers", left/right as prefix). Legacy `whisker_L1` / `whisker_R1` style appears in some stale configs and should be rejected.
- **Eye bodypart names.** DLC uses `L_eye` / `R_eye`, not `medial_edge_L_eye` / `medial_edge_R_eye` (that's a stale legacy convention from the DLC training project name — the actual trained bodypart labels are the short form).

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge. Next expected update: after sweep completes and Phase 4.5 decision lands.
