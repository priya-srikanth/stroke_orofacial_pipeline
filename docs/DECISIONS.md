# Project Decisions Log

Project-wide decisions that affect design, architecture, or workflow. Distinct
from per-phase migration notes in `MIGRATION_LOG.md` (which document *what* was
ported) — this file records *why* choices were made, so future readers (human
or agent) can understand intent without re-deriving it.

Entries are reverse-chronological (newest at top). Format:

- **Date — Short title.**
- *Context:* What prompted the decision.
- *Decision:* What was chosen.
- *Rationale:* Why.
- *Enforced at:* Code or docs where the decision lives.

---

## 2026-04-18 — DLC inference notebook generates SSH/rsync/sbatch commands but never executes them

- *Context:* Phase 5.5's inference workflow requires SSH to O2 and rsync of large video/output files. Executing these from the notebook would require password/credential handling inside the automation layer.
- *Decision:* Local actions (YAML generation, script writing, post-copy file rename) execute directly in the notebook. SSH/rsync/sbatch commands are generated as strings with user-specific inputs substituted and printed for the user to paste into their own Terminal. No SSH connection is made from within the notebook or any Python module.
- *Rationale:* Keeps secrets out of the automation layer entirely. User retains manual control over when SSH connections are made. Matches the password-handling rules in DECISIONS.md "DLC inference port scheduled as dedicated mini-phase."
- *Enforced at:* `notebooks/20_dlc_inference.ipynb`, `src/stroke_orofacial/dlc_inference_o2/transfer.py`.

## 2026-04-18 — Plot axis limits must be per-(bodypart, center_mode)

- *Context:* Phase 5 parity check revealed the legacy `y_limits=(50, 550)` were for un-centered pixel coordinates. Nose-centered data needs `y_limits=(-120, 130)`. The legacy code implicitly assumed un-centered input. Using legacy limits on centered data produced empty heatmaps (0 counts in the visible range).
- *Decision:* The `dlc_spatial` config in `configs/defaults.yaml` uses per-(bodypart, center_mode) axis limits under `bodyparts.{bp}.per_center_mode.{mode}.{xlim,ylim}`. For each combination, explicit limits are set rather than inheriting a single default. Limits set to `null` for untested combinations will be filled in when Phase 6+ exercises those paths.
- *Rationale:* Centered-data plots need different axis ranges than un-centered-data plots; conflating them produces cropped or mis-scaled figures. First real surfacing of the DECISIONS.md "Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters" prediction.
- *Enforced at:* `configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}`.

## 2026-04-18 — Phase 5 defers permutation/inferential spatial stats to Phase 9

- *Context:* The `20251202_all_bodyparts_stats_pixelbin` notebook (cells 8-10) computes permutation nulls and per-day occupancy significance. The `20251201_2KSD_spatial-maps` notebook computes 2D-KS-distance and energy distance with significance tests. Both produce inferential results (p-values).
- *Decision:* Phase 5 produces descriptive spatial maps only (histograms, heatmaps, difference maps, baseline aggregates). All inferential statistics on spatial maps — permutation p-values, KS/energy distance, any other significance testing — are deferred to Phase 9. This includes the 2KSD notebook's visualization, which is tightly coupled to its stats computation.
- *Rationale:* Keeps Phase 5 boundary clean at descriptive analyses. Phase 9 becomes the single home for all inferential spatial-maps stats.
- *Enforced at:* Phase 5 plan (cells 8-10 of `20251202` classified "Deferred to Phase 9"); `docs/MIGRATION_LOG.md` Phase 5 entry.

## 2026-04-18 — DLC inference port scheduled as dedicated mini-phase

- *Context:* `20251112_DLC_batch_video_analysis_O2.ipynb` runs DLC inference on the HMS O2 GPU cluster and copies outputs to MICROSCOPE. The design doc §3 already anticipates this lives in `src/stroke_orofacial/dlc_inference_o2/` as a standalone tool, but §7 didn't include an explicit phase for porting it. Priya wants it ported and cleaned up.
- *Decision:* Add a dedicated DLC-inference port as a mini-phase after Phase 5 and before Phase 6. Scope: port the canonical notebook into `src/stroke_orofacial/dlc_inference_o2/`, apply the full Phase plan requirements (disambiguation + dead code + hardcoded constants), write a README documenting the O2 workflow. Parity verification optional — if a small test video + O2 rerun is feasible, do it; otherwise rely on code review + functional test on a short clip.
- *Rationale:* DLC inference is infrastructure that doesn't block the analysis-pipeline phases (existing DLC outputs on MICROSCOPE are what Phases 4-7 consume). Porting it as a discrete mini-phase avoids interrupting the analysis-phase momentum. Placing it between Phase 5 and Phase 6 means the consolidated repo contains the inference tool before reward-aligned spatial analyses are added.
- *Password/SSH handling:* Strongly recommend SSH key auth to O2 (one-time setup via `ssh-keygen` + `ssh-copy-id`). If not set up, use interactive password entry per SSH command — password goes to stdin, not Claude Code's context. Never pass passwords via `sshpass -p`, environment variables, or any persistent store. Claude Code does not persist secrets across sessions.
- *Enforced at:* Future `docs/prompts/phase-5.5-dlc-inference-kickoff.md` (to be written after Phase 5 completes); design doc §7 to be updated with the new phase.

## 2026-04-18 — Keypoint-MoSeq deferred past v1 consolidation

- *Context:* `20260209_keypoint_moseq_parquet.ipynb` and `20260209_keypoint_moseq.ipynb` implement unsupervised pose-sequence segmentation using keypoint-MoSeq. This is a different analysis paradigm from the spatial/kinematic work in the current phases and was not included in the original design doc §7.
- *Decision:* Deferred past v1 consolidation. Treat similarly to FaceRhythm — scaffold a sibling module only if/when we get to it. Not out-of-scope forever; just not scheduled into v1.
- *Rationale:* V1 consolidation is already substantial. Adding keypoint-MoSeq would expand scope without clear blocking dependency. Can be added as a new phase when Priya has bandwidth to integrate.
- *Enforced at:* `docs/DECISIONS.md` "Deferred to later phases" section.

---

## 2026-04-18 — Disambiguation rule refined: siblings vs duplicates

- *Context:* The original CLAUDE.md rule 1 said "latest YYYYMMDD wins" without distinguishing between dated versions of the same file (true supersession) and files with distinct scope markers like `_tongue` vs `_jaw` (siblings that both need porting). Phase 4 planning surfaced the risk that `20260203_..._tongue.ipynb` and `20260416_..._jaw.ipynb` could be silently treated as old+new of the same thing, losing the tongue notebook entirely.
- *Decision:* Refine rule 1 — date-based supersession applies only within a family of files doing the same thing. Files with distinct scope markers (bodypart name, analysis type, phase tag) are siblings; each may need independent porting. When in doubt, trigger rule 3 (STOP-and-ask).
- *Rationale:* Prevents silently dropping sibling files with unique capabilities that happen to have older dates.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" rule 1.

## 2026-04-18 — Phase 4 orchestrator: iterate over animals without notebook restart

- *Context:* The legacy DLC parquet-building notebook accumulated state (loaded parquets in memory, globals) so moving to the next animal required clearing + restarting the notebook. Priya wants the new pipeline to loop over animals and dates cleanly.
- *Decision:* Phase 4's orchestrator exposes a pure function `build_centered_parquet(animal, date, center_mode, resolver) -> Path` callable in a loop without accumulating module-level state. The notebook orchestrates via an animal × date × center_mode loop. All three center modes (NOSE, SPOUT_MIDPOINT, EYE_MIDPOINT) are built by default; USER INPUTS cell can restrict to a subset. Matches the Phase 2 `process_animal()` pattern.
- *Rationale:* Removes a major friction point from downstream analyses; makes cohort-wide processing a single notebook run.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` orchestrator (Phase 4c), `notebooks/10_dlc_build_parquets.ipynb`.

## 2026-04-18 — Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters

- *Context:* Plotting parameters for heatmaps, proportion-difference maps, unbalanced-OT maps and related analyses (axis scales, filter ranges, baseline values) vary by both bodypart and centering mode in the legacy notebooks. Priya's usage: spout-midpoint centering for tongue analyses; eye-midpoint for jaw and whisker analyses; nose-centering for other uses.
- *Decision:* When Phase 5+ phases port downstream analyses, per-(bodypart, center_mode) plotting parameters must be extracted from the legacy notebooks into `configs/defaults.yaml` (or an analysis-specific config) rather than coalesced into a single default set. Each analysis function accepts `bodypart` and `center_mode` and looks up the appropriate parameters.
- *Rationale:* Silently averaging or picking one bodypart's parameters would produce wrong plots (e.g., tongue-appropriate axis limits applied to jaw analyses would clip or stretch).
- *Enforced at:* Phase 5+ plan requirements, to be captured in each downstream-analysis phase's kickoff prompt.

## 2026-04-18 — Phase 4 decision: keep all frames (no 975K cap)

- *Context:* The old tongue-only parquet-building notebook (`20260111_DLC_analysis_build-parquet_tongue.ipynb`) filtered DLC outputs to the first 975,000 frames. The newer notebook (`20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`) keeps all frames.
- *Decision:* Phase 4 ports from 20260323. The new pipeline keeps all frames in the output parquet (output row count = source DLC frame count). Phase 4d parity check includes an assertion that the new parquet's row count equals the source frame count AND matches the legacy parquet's row count (to catch hidden caps).
- *Rationale:* The 975K cap was a limitation of the older notebook, not a desired behavior. Keeping all frames is necessary for any analysis that spans the full session.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` Phase 4 implementation; `tests/test_dlc_parquet.py` parity check; MIGRATION_LOG Phase 4 entry.

---

## 2026-04-18 — Phase plan requirements: dead code identification step

- *Context:* Porting legacy notebooks risks carrying over exploratory/debugging cells, deprecated code branches, and commented-out historical artifacts. Without explicit classification, dead code silently enters the consolidated repo.
- *Decision:* Every phase plan must include a dead-code identification step. Each cell (notebook) or function/block (.py) in the legacy source is classified as *Production*, *Exploratory*, *Deprecated*, or *Ambiguous*. Only *Production* items get ported. *Exploratory*/*Deprecated* are listed as non-ports. *Ambiguous* triggers STOP-and-ask.
- *Rationale:* Prevents scope creep and ensures Priya can review the classification before any code is written. Applies from Phase 4 onward (Phases 2-3 predated this requirement).
- *Enforced at:* `CLAUDE.md` "Phase plan requirements" section.

## 2026-04-18 — Phase 3 parity tolerance: rtol=1e-8 for affine fit

- *Context:* Alignment template parity checking compares re-computed templates against existing `alignment_templates/` NPZs. The edge-sequence pattern matcher uses a sliding-window L-p norm that can break ties differently depending on floating-point evaluation order, potentially producing slightly different matched-edge sets.
- *Decision:* Interpolated float arrays (`sig_camIdx__idx_ws`, `sig_wsIdx__idx_cam`) use `rtol=1e-10`. Affine fit scalars (`slope_ws_per_camFrame`, `intercept_ws_samples`) use `rtol=1e-8` to absorb minor tie-break variations. Integer edge arrays (`idxCam_edges`, `idxWS_edges`) are not compared directly (they're input to the fit, not output). Any mismatch on `matched_camEdge_i`/`matched_wsEdge_i` must be investigated and documented, not silently accepted.
- *Rationale:* Avoids false parity failures from tie-break non-determinism while still catching real algorithmic bugs.
- *Enforced at:* `tests/test_timebase.py`, `docs/MIGRATION_LOG.md` Phase 3 entry.

## 2026-04-18 — Branch-protection pre-commit hook installed

- *Context:* During Phase 2.5 execution, a batch of commits accidentally landed directly on `main` instead of the intended feature branch. The error was caught but required a manual fix (Priya created the branch retroactively and reset `main`).
- *Decision:* `.githooks/pre-commit` refuses commits on `main`/`master`. `scripts/setup-hooks.sh` activates via `git config core.hooksPath .githooks`. Enforced at `CLAUDE.md` rule 8 ("before every `git commit`, run `git branch --show-current` and confirm you are NOT on `main`").
- *Rationale:* Layer 1 (GitHub branch protection) is unavailable on private-free-tier accounts. Layers 2 (local pre-commit hook) and 3 (CLAUDE.md instruction to Claude Code) are the active defense. Belt-and-suspenders: Claude Code checks the branch before committing, and the hook blocks it if the check is missed.
- *Enforced at:* `.githooks/pre-commit`, `scripts/setup-hooks.sh`, `CLAUDE.md` rule 8.

## 2026-04-18 — Workflow: phase kickoff prompts as files; running decisions log

- *Context:* Copy-pasting long multi-paragraph kickoff prompts from Cowork into Claude Code is friction. No product-level integration exists between the two.
- *Decision:* For each phase or sub-phase, Cowork writes the full kickoff prompt to `docs/prompts/phase-N-*.md`. Priya pastes a one-liner to Claude Code ("Read `docs/prompts/<file>` and follow the instructions."). Prompts are committed to git as a permanent audit trail of what Claude Code was instructed to do. Cross-cutting decisions recorded here in `DECISIONS.md`.
- *Rationale:* Reduces pasting, creates a reproducible record, keeps `MIGRATION_LOG.md` focused on per-phase implementation.
- *Enforced at:* `docs/prompts/README.md`, `docs/DECISIONS.md` (this file).

## 2026-04-18 — Tone events + per-side peri-periods restored (Phase 2.5)

- *Context:* Phase 2 ported from Priya's fork of the legacy repo, which had dropped tone detection (Tone_L / Tone_R rising edges) and per-side peri-reward masks that exist in Rich's upstream repo. Phase 4+ cue-aligned analyses require tone timing.
- *Decision:* Add Phase 2.5 as a strictly additive gap-fill. Extend `lick_detection.py` to detect tones; extend `bouts.py` with per-side peri-reward and peri-tone masks. New keys added to existing NPZ outputs; no existing key changes value.
- *Rationale:* Proper tone capture is more robust than post-hoc L/R inference from reward side (which breaks on omitted trials, licking errors, and tone-reward delay).
- *Enforced at:* `src/stroke_orofacial/spout_behavior/lick_detection.py`, `bouts.py`, `configs/defaults.yaml`, `docs/MIGRATION_LOG.md` Phase 2.5 entry.

## 2026-04-18 — Both legacy repos are read-only references

- *Context:* Cross-repo diff revealed that some legacy helpers (e.g., `make_alignment_templates_20251216.py`) live only in Rich's upstream repo `facerhythm_stroke_biomarker_exp`, not in Priya's fork `facerhythm_stroke_biomarker_exp_Priya`. The original `CLAUDE.md` rule 2 only protected the Priya fork.
- *Decision:* Both legacy repos are read-only references. Neither may be modified.
- *Rationale:* Upstream helpers are genuinely needed for some phases (Phase 3 alignment, potentially later). Making read-only status explicit prevents any ambiguity.
- *Enforced at:* `CLAUDE.md` ground rule 2.

## 2026-04-17 — Per-session `params.json` with "always write" policy

- *Context:* Phase 2's initial design wrote one cohort-level `params.json` at output root, overwritten per session. This lost per-session params provenance and didn't record skip decisions.
- *Decision:* Write one `params.json` per session at `{output_root}/params/{animal}/{YYYYMMDD}.json`. Include session_id, animal, date, run_timestamp, skipped flag, merged params used, processing_log. Write even when the session is skipped (records full audit trail).
- *Rationale:* Reproducibility — we want to always be able to reconstruct exactly what params were used for any session, and whether a given run processed or skipped it.
- *Enforced at:* `src/stroke_orofacial/spout_behavior/session_processing.py`, MIGRATION_LOG Phase 2d.

## 2026-04-17 — Overwrite protection default is "skip"

- *Context:* Re-running the pipeline over the full cohort risks silently overwriting hours of processed outputs if the user isn't careful.
- *Decision:* Three modes — `"skip"` (default; if output NPZ exists, skip and log), `"prompt"` (interactive per-file y/N/all/quit), `"force"` (explicit opt-in). Notebook default is `"skip"`.
- *Rationale:* Accidents cost hours of reprocessing. Opt-in to overwrite is the safer default.
- *Enforced at:* `process_session()` / `process_animal()` in `session_processing.py`.

## 2026-04-17 — Output location: MICROSCOPE, not Mac local

- *Context:* Legacy outputs lived at Mac-local `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/`. Priya works from both Mac and Windows workstations.
- *Decision:* New pipeline outputs go to `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/` (Mac SMB mount) or the equivalent UNC path (Windows). Layout under the v2 root: `spout_behavior/`, `alignment/`, `dlc_analysis/`, `stats/`. Legacy `session_processing3/` is read-only and untouched.
- *Rationale:* Single source of truth across both workstations. Server backup. No local duplicates to keep in sync.
- *Enforced at:* `configs/paths.yaml` (`microscope_pipeline_outputs` logical root), `PathResolver.pipeline_outputs()`.

## 2026-04-17 — Cross-platform `wavesurfer_raw` with fallback chain

- *Context:* Raw wavesurfer `.h5` files lived only on Priya's Mac local disk. Pipeline needed to run from Windows too.
- *Decision:* `paths.yaml` declares `wavesurfer_raw` as a list-mount on Mac — tries MICROSCOPE first, falls back to Mac-local. Single UNC path on Windows. `PathResolver.root()` supports list mounts by returning the first existing path. Wavesurfer raw data is mirrored to MICROSCOPE (one-time rsync 2026-04-18).
- *Rationale:* Cross-platform capability without forcing data duplication management on the user.
- *Enforced at:* `configs/paths.yaml`, `PathResolver.root()`.

## 2026-04-17 — `stroke_date` = last pre-stroke session date

- *Context:* Legacy notebooks use `stroke_date` to refer to the last pre-stroke session date; stroke is induced after that session. Early in Phase 1, the implementation treated `stroke_date` as the first post-stroke day, which would mis-classify every baseline session on that date.
- *Decision:* `stroke_date` is the date of the last pre-stroke session. `AnimalInfo.phase(session_date)` returns `"baseline"` for `session_date <= stroke_date`, `"post_stroke"` otherwise. `day_relative_to_stroke` = `(session_date - stroke_date).days` (day 0 = last baseline; day 1+ = post-stroke).
- *Rationale:* Matches legacy notebook semantics and Priya's lab-notebook convention. Avoids contaminating post-stroke analyses with baseline data from the stroke day.
- *Enforced at:* `src/stroke_orofacial/animals.py`, tests.

## 2026-04-17 — Exclusion semantics: `applies_to: [all]` for the current cohort

- *Context:* Legacy notebooks declared exclusions per-analysis (`[tongue]` in the tongue notebook, `[jaw]` in the jaw notebook). Priya reviewed the underlying reasons (Rose Bengal sham sessions, reward-delivery failures) and determined they invalidate all analyses, not just the one the exclusion was originally declared under.
- *Decision:* All existing exclusions in `animals.yaml` use `applies_to: [all]`. Schema supports per-analysis exclusions (`applies_to: [tongue]`, etc.) if a future exclusion is analysis-specific.
- *Rationale:* Reasons driving the current exclusions are universal.
- *Enforced at:* `configs/animals.yaml`, `AnimalInfo.is_excluded()`.

## 2026-04-17 — Legacy code version disambiguation (3-tier rule)

- *Context:* Legacy repos contain multiple dated copies of the same notebook and `_v0` / `_mod` suffixed helper files. Silent selection could anoint the wrong version.
- *Decision:* 3-tier rule — (1) Latest `YYYYMMDD` in filename wins; (2) if undated, pick the candidate whose output has the most recent mtime in downstream output dirs; (3) if still ambiguous, STOP and ask Priya.
- *Rationale:* Deterministic, auditable, refuses to guess.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" section.

## 2026-04-17 — Git discipline: feature branches preserved, tags per phase

- *Context:* Risk of losing work through `git branch -D`, `git reset --hard`, or force-push during an active multi-phase refactor.
- *Decision:* Every change on a feature branch off `main`. PR-merge to main. Never force-push. Never `branch -D`. After PR-merge, feature branches kept on origin as permanent references. Each phase gets a tag `vX.Y-phase-N-short-name` on its merge commit. Destructive git operations require explicit Priya approval each time.
- *Rationale:* Hours of work safe from a single bad command.
- *Enforced at:* `CLAUDE.md` ground rule 8.

## Deferred to later phases

The following decisions are **deliberately deferred** — recorded here so they don't get lost:

- **Recovery phenotype classification scheme** — §6.3 of `docs/DESIGN.md`. Will be a data-driven classification (rule-based, changepoint, HMM, or hybrid) to be chosen in Phase 9 after per-animal trajectories are visible across canonical endpoints.
- **Session-merge implementation** — PS48 2025-03-14 combines two wavesurfer files. Logged in `configs/session_overrides.yaml` under `merges:`; `check_merge_required()` raises `NotImplementedError` if encountered. Implementation deferred until a second merge-case arises or Priya needs to re-process PS48.
- **Wavesurfer QC figure generation** — legacy pipeline produced `wavesurfer_figures/` for visual QC. Deferred to Phase 8 (behavior report) which will build a unified figures layer.
- **FaceRhythm module** — scoped out of v1 consolidation entirely. Will be added in a later phase as a sibling module to `spout_behavior/`, `alignment/`, etc.
