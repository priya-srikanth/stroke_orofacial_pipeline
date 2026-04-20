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

**As of:** 2026-04-20 (Phase 13 closed).

**Repo phase:** Mid-consolidation audit **complete** (tag `v0.6.5-audit-complete`). Phases 1 through 6 + 13 delivered. Phase 13 merged via PR #31 as `d031486` and tagged `v0.7-phase-13-env-unification`. No work in flight; ready to pick the next phase.

**Current branch:** `main` at `d031486`. The `phase-13-env-unification` branch is preserved on origin at `e244c0b` per CLAUDE.md §8.

**In flight:** *None.* Phase 13 is fully closed on both Mac and Windows:

- Mac pytest (in the new `stroke_orofacial` env): 223 passed / 6 skipped / 0 failed. The 6 skips are `pytest.importorskip("bnpm.*")` strict-port parity gates; they run and pass when the suite is executed inside `frsb` (which still has bnpm 0.6.0).
- Windows pytest (in the new `stroke_orofacial` env on Priya's Windows box, via `--basetemp=C:/Users/sabatini/pytest_tmp` to sidestep stale admin-owned tmpdirs): 201 passed / 28 skipped / 0 failed. Skip split = 22 pre-existing integration/real-data gates + 6 bnpm-importorskip gates. Torch/bnpm/numba/llvmlite/cmake all absent from the new Windows env.
- HDF5 stack clean on both: `h5py==3.16.0`, `pytables==3.10.2`, `pywavesurfer` loads without DLL errors.
- Drift from vendored bnpm bug fixes measured on PS46/20250307 terminal masks — scope of affected downstream artifacts: **none** (running_bouts 0 differ, lick_bool_bad 2 differ / 5.4e-7, quiet_bool 51 differ / 1.4e-5 isolated singletons, peri_reward_bool 0 differ). Table lives in MIGRATION_LOG.md Sub-phase 13b.

**Outstanding housekeeping (non-code, do when back at the Windows box):**

From an elevated PowerShell:
```powershell
Remove-Item -Recurse -Force C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini
Remove-Item -Recurse -Force C:\Users\sabatini\GitHub\stroke_orofacial_pipeline\.pytest_cache
```
Both are stale admin-owned directories that produced `WinError 5: Access is denied` on the non-elevated Windows #1 pytest run. Not a code issue; not in scope for any phase.

**Next-phase candidates** (all unblocked now that #13 is done — Priya to pick):

1. **#3 — Phase 4.5-lite execution** (eye-midpoint centering). Smallest deliverable; already has a kickoff prompt at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md` from the audit-closure session. Decision trail: DECISIONS entry 2026-04-19 "Phase 4.5-lite eye-midpoint centering".
2. **#9 — Phase 6.7 SessionManifest refactor** (kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`). Unblocks #17 → #14 → #15, the main DLC-spatial queue.
3. **#10 — Phase 8a spout-only recovery trajectories.** Mid-experiment deliverable — DLC-independent, parallelizable with 6.7/6.75/6.8. Scope per Audit Item 10 Q9: 8 new spout endpoints + recovery-phenotype viz + legacy `facerhythm_stroke_biomarker_exp_Priya` behavior-report walkthrough. No kickoff prompt yet.

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

- *(none — Phase 13 closed this session)*

**Completed since last state refresh:**

- **#13** — Phase 13 env unification + bnpm vendoring. Full details in MIGRATION_LOG.md Phase 13 (sub-phases 13a + 13b) and DECISIONS.md 2026-04-19 + 2026-04-20 entries. Merged to main as `d031486`, tagged `v0.7-phase-13-env-unification`. Feature branch `phase-13-env-unification` preserved on origin.
- **#8** — Audit branch `audit-item-6-phase5-details` merged to `main` and tagged `v0.6.5-audit-complete`. Branch preserved as permanent reference per CLAUDE.md rule 8.

**Pending — queued phases and mini-phases**, in rough execution order (dependencies noted):
- **#3 (completed)** — Phase 4.5 decision was "build lite". **Execution of Phase 4.5-lite** per `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md` does not have its own task yet; unblocked and available as a candidate next phase.
- **#9** — Phase 6.7 SessionManifest refactor. Kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`. Unblocked (Phase 13 done); ready to execute.
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

Phase 13 is closed (merged as `d031486`, tagged `v0.7-phase-13-env-unification`). Mac + Windows are on the unified `stroke_orofacial` env. No work is in flight. Use this prompt to open the next session:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Phase 13 (env unification + bnpm vendoring with two upstream bug fixes) merged to main as `d031486` and is tagged `v0.7-phase-13-env-unification`. I want to pick the next phase to work on. The Current-state section lists the three unblocked candidates — #3 (Phase 4.5-lite eye-midpoint centering, smallest, has a kickoff prompt), #9 (Phase 6.7 SessionManifest refactor, unblocks the DLC-spatial queue, has a kickoff prompt), and #10 (Phase 8a spout-only recovery trajectories, DLC-independent, mid-experiment deliverable, no kickoff prompt yet). Summarize the tradeoffs briefly and ask me which one to go with before doing anything else.

For sessions further out, once you've moved past whichever phase you pick here, the generic warm-start remains:

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Then ask me what we're working on.

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge.
- **2026-04-19** — Major refresh at end of multi-day session. Audit progressed from 6/10 to 9/10 items resolved; Phase 4.5-lite decision locked; several new tasks created (#14, #15, #16, #17); Cowork-on-Windows permanently deferred; `docs/SCIENTIFIC_ENDPOINTS.md` created with Q1–Q10 for next session. Transcribed all session decisions into DECISIONS.md. Next expected update: after Item 10 Q1–Q10 discussion completes.
- **2026-04-19 (audit closure)** — Walked Q1–Q10 with Priya in a focused second session the same day; all 10 decisions landed as a single grouped entry at the top of DECISIONS.md. Audit now 10/10. Phase 9 split into 9a/9.1/9b; task #12 refactored into #12a–e; new tasks #18 (sex/DOB schema) and #19 (facerhythm_tca stub) created; task #16 extended with DTW per-edge-shift QC plot carve-out; task #10 and #11 scopes expanded with locked Phase 8a/7 content. Next session opens with audit merge (#8).
- **2026-04-19 (Phase 13 drafting)** — Third session same day. Audit branch merged to `main`, tagged `v0.6.5-audit-complete`. Feature branch `phase-13-env-unification` cut from `main`. Full import audit performed across `src/`, `tests/`, `notebooks/`, and `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` to determine the minimum dep set for the new unified env. Drafted `environment.yml` (single env, Python 3.11, conda-forge primary, `bnpm[core]`). Added `patsy`, `pot`, `scicomap` (in-flight-port prereqs). Dropped `opencv-contrib-python` and `tqdm` (audit confirms zero imports). Brought `pyproject.toml` into agreement. Reduced old per-platform env files to deprecation stubs. Cowork context compacted mid-session (summary preserved). Windows test-env install was still spinning on jinja2 at session end — resolution deferred to next session.
- **2026-04-20 (Phase 13 closure)** — Windows env couldn't import bnpm because the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` that collides with conda-forge MKL's `libomp.dll` (`OMP: Error #15` + `WinError 127` on `shm.dll`). Resolved by vendoring the 4 pure-numpy bnpm helpers the repo actually uses into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT attribution and dropping `bnpm[core]` + `numba` + `cmake` from the env. Two vendored helpers intentionally diverge from upstream bnpm 0.6.0 to fix off-by-one bugs discovered while writing parity tests; drift measured (0 / 2 / 51 / 0 per-array on PS46/20250307 terminal masks; scope downstream: none). Full Mac + Windows verification green (Mac 223/6/0; Windows 201/28/0). PR #31 merged to main as `d031486`; tag `v0.7-phase-13-env-unification` pushed; feature branch preserved on origin. README + DESIGN.md §§2.3/3/8 + MIGRATION_LOG.md 13a+13b + DECISIONS.md 2026-04-19 + 2026-04-20 all written/reframed to reflect the unified env and the vendor-plus-bug-fixes narrative. All three next-phase candidates (#3 / #9 / #10) unblocked.
