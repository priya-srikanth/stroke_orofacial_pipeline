# CLAUDE.md

Project-level instructions for Claude Code. Read in full at the start of every session.

---

## Ground Rules (non-negotiable)

These rules bind every Claude Code session working on this project.

1. **Never modify, overwrite, rename, or delete source data.** "Source data" = any raw file produced by an instrument, experiment, or upstream processing that is not already produced by this new consolidated codebase. Concretely this includes, but is not limited to:
   - Raw wavesurfer `.h5` files.
   - Raw videos (Flea3 recordings).
   - DLC inference outputs on the MICROSCOPE server (`O2_analysis/PS*/...` H5 and CSV files).
   - The DLC training config and project at `DLC_train_config/`.
   - The existing `alignment_templates/` directory contents.
   - The existing processed behavior outputs in `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/`.
2. **Never modify files in the legacy repo** `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya`. It is a read-only reference. Work happens in this new repo only.
3. **Never modify files Claude Code did not create itself in this consolidation project**, with one exception: inside this repo, Claude Code may modify files it created on a previous turn in the same or prior session.
4. **If Claude Code believes an existing analysis output should be overwritten**, stop and ask first, describing exactly what would be overwritten and why.
5. **Default migration pattern: copy, do not move.** Legacy notebook → new module = implement in this repo; legacy notebook stays untouched.
6. **Output writes go to new output directories** (e.g. `session_processing_v2/`, `dlc_analysis_v2/`) — never on top of existing `session_processing3/` or existing per-animal analysis folders on the server.
7. **Before any large refactor or delete-like operation**, use plan mode (Shift+Tab → Plan) and show the plan for approval.
8. **Git discipline:** every change lands as a commit on a feature branch; never force-push.

---

## Repo Conventions

- Code lives in `src/stroke_orofacial/`; notebooks orchestrate, they do not contain analytical code.
- No absolute paths in source; use `PathResolver` from `stroke_orofacial.paths`.
- No hardcoded animal metadata; load from `configs/animals.yaml`.
- Every analysis output goes to a new output directory, not on top of an existing one.
- Every notebook has a single clearly-banner-commented "USER INPUTS" cell at the top for user-editable variables; all other cells only import from `stroke_orofacial` and orchestrate.
- Before any refactor that touches more than 5 files, propose a plan and wait for approval.
- Add docstrings to every public function. Inline comments should explain **why** a choice was made, not just what a line does.

---

## Reference

The full design doc is at `docs/DESIGN.md`. Read it before starting any phase. Every phase ends with a short entry in `docs/MIGRATION_LOG.md` documenting what changed and any intentional behavior differences vs. the legacy notebooks.

---

## Current phase

At session start, check `docs/MIGRATION_LOG.md` for the last completed phase. If the log is empty or missing, we are on Phase 0 (repo skeleton), as specified in §7 of `docs/DESIGN.md`.
