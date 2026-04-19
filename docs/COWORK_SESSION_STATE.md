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

**As of:** 2026-04-19 (end of extensive session; Cowork-on-Mac + Windows-Claude-Code workflow now permanent).

**Repo phase:** Mid-consolidation audit nearing completion — 9 of 10 items resolved; Item 10's archaeology phase done, discussion-with-Priya phase deferred to next session. Phases 1 through 6 delivered and on `main`.

**Current branch:** `audit-item-6-phase5-details` (off `main` at tag `v0.6-phase-6-complete`). All work this session landed on this branch. Final uncommitted items sitting on Mac from the last edits: the DECISIONS.md additions for Audit Items 8/9 and the new `docs/SCIENTIFIC_ENDPOINTS.md`. See last commit instructions in the "Recent session log" below.

**In flight:** None. Between-session state is clean. Next session picks up at Audit Item 10 Q1–Q10 discussion.

**Recent session log (2026-04-18 through 2026-04-19, consolidated):**

Completed across the multi-day session:

- Audit Items 1–6 (renames, per-camera alignment structure, SessionManifest wiring plan, `load_centered_fresh` util spec, Phase 8 split into 8a/8b, Phase 5 sub-decisions including fine-grid NPZ save and all-bodyparts overlay design).
- **Eye-affine alignment experiment** — single-animal exploration (PS46) then full-cohort sweep (8 animals × 4 regimes × 13 bodyparts × all session dates). Per-animal outputs + cross-animal metric overview PNGs + `summary.txt` all committed under `notebooks/experiments/outputs/alignment_sweep/`.
- **Phase 4.5-lite decision locked** — eye-centered wins 8/9 movement bodyparts; spout_centered wins tongue; similarity and rigid transforms rejected (noise-amplification dominated signal-correction benefit). Kickoff doc at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`. DECISIONS entry 2026-04-19.
- **Audit Item 7 (Phase 6 reward-aligned DLC) closed** — 7 sub-items resolved via Phase 6.7 (rolled in 7.1/7.3/7.4/7.5), new Phase 6.8 task (7.2 — full heatmap/binned/Δ × session/reward-aligned matrix), new axis-sharing task (7.6/7.7). DECISIONS entry 2026-04-19.
- **Audit Item 8 (SSH workflow) closed** — 5 polish items batched into new Phase 5.5 polish task. DECISIONS entry 2026-04-19.
- **Audit Item 9 (SVG + output reorg) closed** — SVG via unified `save_figure` helper (rolled into Phase 5.5 polish task). Directory reorg to figure-type-first within existing `spout_behavior/` and `dlc_analysis/` top-levels. New Phase 6.75 task, sequenced between 6.7 and 6.8. DECISIONS entry 2026-04-19.
- **Audit Item 10 archaeology phase** — Explore agent cataloged 26 endpoints across 6 categories from two legacy repos; written to `docs/SCIENTIFIC_ENDPOINTS.md`. Discussion phase (Q1–Q10) deferred to next session.
- **Cowork-on-Windows declared permanently unavailable** for Priya's machine despite Hyper-V running + Max subscription; account-level feature-flag block. Mac-Cowork + Windows-Claude-Code split is the permanent workflow.

---

## Active task list

The authoritative source is the Cowork TaskList widget in the current session. Mirrored here for persistence across sessions. Numbers are Cowork's task IDs.

**In progress:**

- **#7** — Audit Item 10 (scientific endpoints). Phase 1 archaeology done (written to `docs/SCIENTIFIC_ENDPOINTS.md`). Phase 2 = walk Q1–Q10 with Priya, land decisions into DECISIONS.md.

**Pending — audit wrap-up gate:**

- **#8** — Merge `audit-item-6-phase5-details` → `main`, tag `v0.6.5-audit-complete`. Blocked on #7 only (all other audit items closed).

**Pending — queued phases and mini-phases**, in rough execution order (dependencies noted):

- **#13** — Unify analysis conda env to `stroke_orofacial` (cross-platform). Blocked on #8. Sequenced before any new long-running phase to avoid env-name drift.
- **#3 (completed)** — Phase 4.5 decision was "build lite". **Execution of Phase 4.5-lite** per `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md` does not have its own task yet; slot it after #13 unless Priya decides otherwise.
- **#9** — Phase 6.7 SessionManifest refactor. Kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`. Blocked on #13 (env unification).
- **#17** — Phase 6.75 output directory reorganization (figure-type-first inside dlc_analysis and spout_behavior). Blocked on #9 so Phase 6.7's byte-parity checks remain valid at old paths.
- **#14** — Phase 6.8 full heatmap/binned/Δ × session/reward-aligned matrix. Blocked on #17.
- **#15** — Axis sharing (`share_xy_within_mouse` + percentile fallback + reward-aligned-specific axis config). Blocked on #14.
- **#10** — Phase 8a spout-only recovery trajectories (mid-experiment deliverable — DLC-independent). Blocked on #8 only; can execute in parallel with Phase 6.7/6.75/6.8 stack if resources allow.
- **#11** — Phase 7 reward-aligned DLC cohort extension. Blocked on #9 + #10.
- **#12** — Phase 8b + Phase 9 + Phase 10 bundle. Blocked on #11.
- **#16** — Phase 5.5 polish (SSH monitoring helper, recovery docs, SSH setup, ControlMaster, auto-rename + SVG unified save helper). Ungated — can execute any time.

**Phase-transition rule:** No new phase starts until the audit branch is merged to main and tagged (#8). Keeps the audit as one atomic chunk.

---

## Open decisions awaiting human input

Currently-open decision points that need Priya's call in the next session. These are the Q1–Q10 from `docs/SCIENTIFIC_ENDPOINTS.md`, needed to fully close Audit Item 10:

- **Q1** — Confirm canonical-version disambiguation for legacy files (`behavior_report_PS.py`, `batch_process_behavior_report_20260116PS.ipynb`, `playground.ipynb` linear alignment). Was DTW alignment meant to replace linear or parallel?
- **Q2** — Criteria renaming (`criteria_1/2/3/4` → descriptive slugs).
- **Q3** — Recovery-phenotype stratification timing: Phase 8a or Phase 9/10?
- **Q4** — Quiet-period endpoint status: is `quiet_period_batch_playground.ipynb` integrated or not?
- **Q5** — Face-rhythm TCA scope: in-scope (Phase 11+) or out-of-scope?
- **Q6** — Kinematic endpoint design (whisker angle, tongue protrusion amplitude, jaw velocity, face-velocity PCs, others). Open; drives Phase 7 scope.
- **Q7** — Sex coding in cohort; does `animals.yaml` need a `sex` field?
- **Q8** — Stats integration timing (Phase 9 relative to cohort completion).
- **Q9** — New endpoints to add that aren't in legacy?
- **Q10** — Prioritization of the 6 gaps listed in SCIENTIFIC_ENDPOINTS.md's Gaps section.

When Priya's decisions land, transcribe each to `docs/DECISIONS.md` with its own dated entry, update this file's "Open decisions" section to remove the resolved Qs, and if the decision reshapes a queued phase's scope, amend that phase's kickoff prompt or task description accordingly.

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

- The `deeplabcut` conda env on Windows (analytics-capable; pandas / numpy / matplotlib / h5py / tables / pyarrow / jupyter / nbconvert). **Note:** Mac uses `frsb` env for the same purpose — cross-platform env-name unification is tracked as task #13.
- Direct ethernet access to MICROSCOPE at `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` (Windows UNC path; no VPN).
- The repo checked out at `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`.
- Git access with `.githooks/pre-commit` that blocks direct commits to `main` / `master`.

**Cowork-on-Windows is NOT AVAILABLE** on Priya's setup despite meeting all published prerequisites — see "Cowork-on-Windows status" section below.

**Handoff pattern.** Cowork drafts "paste-in prompts" (usually in block-quote form) that Priya pastes into Claude Code's chat panel in VSCode on Windows. Claude Code reports back to Priya; she relays the summary to Cowork. Cowork reads committed outputs directly from its folder view of the repo.

**Mac-commit roundtrip.** When Cowork writes files (DECISIONS updates, new kickoff prompts, SCIENTIFIC_ENDPOINTS.md, etc.), the files land on the Mac's disk (which Cowork mounts) but are uncommitted. Priya runs a 30-second `git add / git commit / git push` sequence on Mac to get them to origin. Then Windows does `git pull` to see them. This is the only friction added by the split.

### Opening Claude Code in VSCode on Windows

1. File → Open Folder → select `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`.
2. Open the integrated terminal (Ctrl+backtick) and `conda activate deeplabcut`.
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
- **Conda env cross-platform.** Mac env is `frsb`, Windows env is `deeplabcut` (inherited from legacy). Don't confuse them in paste-in prompts. Unification is task #13.
- **Cowork's folder view can be stale.** If Priya pushes from Windows and doesn't pull on Mac, Cowork's read of the Mac's disk lags behind origin. Workaround: have Priya `git pull` on Mac before Cowork needs the fresh files, or have Cowork ask her to pull when it seems stale.

---

## Best warm-start prompt (paste into a new Cowork chat)

For the next session specifically, use this prompt. It captures the "read the state doc, then tackle the open Q1–Q10" structure:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full before answering substantive questions. We're picking up the mid-consolidation audit at Item 10 — the scientific endpoint inventory. Read `docs/SCIENTIFIC_ENDPOINTS.md` after the state doc; it has 10 discussion questions (Q1–Q10) at the bottom. Walk me through them one at a time in order, pausing for my decision on each before moving to the next. Capture each decision as a DECISIONS.md entry as it lands (one entry per question, or a single grouped entry at the end — propose whichever is cleaner). After all 10 are decided, update this COWORK_SESSION_STATE.md to reflect the new state, and we'll be ready for the audit merge (#8). Audit is currently 9/10 done; this session closes the last item.

For future sessions after Item 10 is closed, the warm-start prompt is the more generic:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Then ask me what we're working on.

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge.
- **2026-04-19** — Major refresh at end of multi-day session. Audit progressed from 6/10 to 9/10 items resolved; Phase 4.5-lite decision locked; several new tasks created (#14, #15, #16, #17); Cowork-on-Windows permanently deferred; `docs/SCIENTIFIC_ENDPOINTS.md` created with Q1–Q10 for next session. Transcribed all session decisions into DECISIONS.md. Next expected update: after Item 10 Q1–Q10 discussion completes.
