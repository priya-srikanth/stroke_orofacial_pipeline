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
