# CLAUDE.md

Project-level instructions for Claude Code. Read in full at the start of every session.

---

## Ground Rules (non-negotiable)

These rules bind every Claude Code session working on this project.

1. **Never modify, overwrite, rename, or delete source data.** "Source data" = any raw file produced by an instrument, experiment, or upstream processing that is not already produced by this new consolidated codebase. Concretely this includes, but is not limited to:
   - Raw wavesurfer `.h5` files.
   - Raw Flea3 camera acquisition output on MICROSCOPE at
     `/Volumes/Neurobio/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera/{YYYYMMDD}/{animal}/`
     — both the `.avi` video files (`video{N}_{timestamp}.avi`) and the
     companion per-frame-timestamp CSVs (`timestamp{N}_{timestamp}.csv`).
     These are pure raw acquisition output, used for wavesurfer ↔ video
     alignment in Phase 3 and for DLC input in upstream inference.
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
8. **Git discipline:**
   - Every change lands as a commit on a feature branch. Never force-push.
   - Never delete a feature branch with `git branch -D` (force-delete). Use
     `git branch -d` (lowercase), which refuses to delete unmerged branches,
     and only after the branch has been PR-merged to main and the merge has
     been verified locally.
   - After PR-merge, leave the feature branch intact on origin as a permanent
     reference. Pruning is Priya's call, not Claude Code's.
   - When completing a phase, tag the merge commit on main with
     `vX.Y-phase-N-short-name` so there is a permanent named reference.
   - Before any potentially destructive git operation (`git reset --hard`,
     `git branch -D`, `git rebase`, `git checkout -- <file>`, `git clean -fd`,
     force-push), STOP and ask Priya first. Describe exactly what will change
     and request explicit approval.

---

## Legacy code version disambiguation

When the legacy codebase contains multiple files that appear to implement the
same functionality (e.g., multiple dated copies of a notebook, or several
`_v0`/`_mod`-suffixed helper `.py` files), identify the canonical version using
this strict priority:

1. **Latest `YYYYMMDD` in the filename wins.** Later date = more recent =
   canonical. Suffixes like `_v0`, `_mod`, `_old`, `_backup`, `_copy`, `-Copy1`
   are strong signals of deprecated branches and should be treated as
   non-canonical unless their date beats every alternative.
2. **When filenames do not uniquely resolve it** (no date, or tied dates),
   check the latest modification time of the files each candidate produced in
   downstream output directories (e.g. `session_processing3/`,
   `O2_analysis/PS*/...`). The candidate that wrote the most recent output is
   the working version.
3. **When (1) and (2) do not resolve it**, STOP and ask Priya. Present the
   candidates, the disambiguation attempts made, and request a human decision.
   Do not guess, silently pick, or merge behavior across versions.

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
