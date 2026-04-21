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
2. **Never modify files in the legacy repos**. There are two, both read-only references for this consolidation:
   - `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya` — Priya's working fork.
   - `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp` — Rich's upstream repo. Some helpers (e.g., `make_alignment_templates_20251216.py`) live only here.

   Work happens in this new repo only. If either legacy repo contains multiple candidate implementations of the same functionality, apply the disambiguation policy below to identify the canonical version.
3. **Never modify files Claude Code did not create itself in this consolidation project**, with one exception: inside this repo, Claude Code may modify files it created on a previous turn in the same or prior session.
4. **If Claude Code believes an existing analysis output should be overwritten**, stop and ask first, describing exactly what would be overwritten and why.
5. **Default migration pattern: copy, do not move.** Legacy notebook → new module = implement in this repo; legacy notebook stays untouched.
6. **Output writes go to new output directories under `stroke_orofacial_pipeline_outputs/`** (e.g. `stroke_orofacial_pipeline_outputs/spout_behavior/`, `stroke_orofacial_pipeline_outputs/dlc_analysis/`) — never on top of existing `session_processing3/` or existing per-animal analysis folders on the server.
7. **Before any large refactor or delete-like operation**, use plan mode (Shift+Tab → Plan) and show the plan for approval.
8. **Git discipline:**
   - Every change lands as a commit on a feature branch. Never force-push.
   - **Before every `git commit`, run `git branch --show-current` and confirm
     you are NOT on `main` (or `master`).** If you are on a protected branch,
     STOP and ask Priya to switch branches. Never commit directly to `main`.
     A pre-commit hook in `.githooks/pre-commit` enforces this; if the hook
     blocks a commit, do not bypass with `--no-verify` without explicit
     Priya approval.
   - Never delete a feature branch with `git branch -D` (force-delete). Use
     `git branch -d` (lowercase), which refuses to delete unmerged branches,
     and only after the branch has been PR-merged to main and the merge has
     been verified locally. **Important `-d` subtlety:** `git branch -d` only
     checks that the branch tip is reachable from its configured upstream
     (i.e., fully pushed), NOT whether the PR was merged to main. A fully-
     pushed but unmerged branch will delete cleanly under `-d`. The merged-
     to-main check is yours to enforce — confirm the PR shows as merged on
     GitHub (`gh pr view <N>` → `state: MERGED`) before running `-d`.
   - After PR-merge, leave the feature branch intact on origin as a permanent
     reference. Pruning is Priya's call, not Claude Code's.
   - **Phase-close tags — every merge gets one.** Every PR that
     represents a phase close (numbered phase, dotted sub-phase, or
     letter-suffix atomic fix within a phase) gets a tag on its merge
     commit. Format: `v{phase}-{short-slug}` where `{phase}` is the full
     dotted-or-lettered phase identifier (e.g. `6.7`, `6.7a`, `6.8`, `7`,
     `7.1`, `8a.7.5`) — NOT a repo-level semver. `{short-slug}` is a
     hyphen-separated summary; do not repeat `phase-N` in the slug (the
     version prefix already encodes it). Examples from existing history:
     `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`,
     `v8a.7.5-criteria-hierarchy-port`. Earlier tags use a legacy
     `v0.X-phase-N-slug` format (visible in `git tag --list`); do not
     rename them — they are permanent references in the history.
   - **Tag message format.** `Phase {phase}: {short summary}`. Examples:
     `Phase 6.7: SessionManifest refactor — every analysis takes a
     manifest + resolver`; `Phase 6.8: wavesurfer↔mouse-frame
     boundary-layer L/R translation`. Keep messages to one line where
     possible; expand only when the short summary genuinely loses
     critical information.
   - **Push the tag immediately** so origin has the reference. Standard
     sequence after a phase-close PR merges on main:
     `git tag -a v{phase}-{slug} <merge-sha> -m "Phase {phase}: {summary}"`
     then `git push origin v{phase}-{slug}`. Verify with
     `git tag --list | tail -5`.
   - Before any potentially destructive git operation (`git reset --hard`,
     `git branch -D`, `git rebase`, `git checkout -- <file>`, `git clean -fd`,
     force-push), STOP and ask Priya first. Describe exactly what will change
     and request explicit approval.

---

## Environment activation

Before any `pytest`, `ruff`, `pip`, `python`, `papermill`, `jupyter`, or
notebook-execution command at the start of every Claude Code session:

```bash
conda activate stroke_orofacial
which python                            # must print a path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"     # must succeed without error
```

If `conda activate` fails (PATH not set in the shell), fall back to
`conda run -n stroke_orofacial <command>` per-command. If the `import`
check fails with `ModuleNotFoundError`, run `pip install -e . --no-deps`
in the activated env and retry.

**Do not begin any test/ruff/implementation work until `pytest --collect-only`
completes without import errors.** A silent collection failure means the
post-implementation test suite isn't validating anything — "N tests pass"
is meaningless if only M of N tests were actually collected.

---

## Legacy code version disambiguation

When the legacy codebase contains multiple files that appear to implement the
same functionality (e.g., multiple dated copies of a notebook, or several
`_v0`/`_mod`-suffixed helper `.py` files), identify the canonical version using
this strict priority:

1. **Latest `YYYYMMDD` in the filename wins, WITHIN A FAMILY OF FILES THAT DO
   THE SAME THING.** Files with distinct *scope markers* in the filename
   (e.g., `_tongue` vs `_jaw`, `_baseline` vs `_post_stroke`, different
   analysis types) are **siblings**, not duplicates — each may need to be
   ported independently. Apply date-based supersession only when the rest of
   the filename indicates the same functional scope. When in doubt, prefer
   treating files as siblings (trigger rule 3 STOP-and-ask) rather than
   silently choosing one. Suffixes like `_v0`, `_mod`, `_old`, `_backup`,
   `_copy`, `-Copy1` are strong signals of deprecated branches and should be
   treated as non-canonical unless their date beats every alternative.
2. **When filenames do not uniquely resolve it** (no date, or tied dates),
   check the latest modification time of the files each candidate produced in
   downstream output directories (e.g. `session_processing3/`,
   `O2_analysis/PS*/...`). The candidate that wrote the most recent output is
   the working version.
3. **When (1) and (2) do not resolve it**, STOP and ask Priya. Present the
   candidates, the disambiguation attempts made, and request a human decision.
   Do not guess, silently pick, or merge behavior across versions.

---

## Phase plan requirements

Every phase plan proposed by Claude Code in plan mode must include, at minimum:

1. **Legacy file disambiguation** applied per the 3-tier rule above. Report
   each candidate and the resolution.
2. **Dead code identification.** For each legacy source file (notebook or
   `.py`) that might be ported, walk through its cells (for notebooks) or
   top-level functions/blocks (for `.py` files) and classify each one as:
   - *Production* — its output feeds a downstream module or the final
     analysis outputs.
   - *Exploratory* — data inspection, debugging, troubleshooting, one-off
     experimentation, commented-out historical code.
   - *Deprecated* — older version, `_v0`/`_mod`/`_old` suffix, superseded
     branch.
   - *Ambiguous* — unclear whether used.

   Only *production* items get ported. *Exploratory* and *deprecated* items
   must be listed explicitly in the plan as non-ports (so Priya can sanity-check
   the classification before anything is written). *Ambiguous* items must
   STOP-and-ask for Priya's decision before the plan is finalized.
3. **Sub-phase breakdown** with per-file line-count estimates and a clear
   dependency order.
4. **Parity strategy** — what existing outputs to compare against, what arrays,
   what tolerances.
5. **Hardcoded constants** — list any numeric thresholds, channel names,
   path literals, etc. that should move out of source into
   `configs/defaults.yaml` or `configs/session_overrides.yaml`.

The plan must pause for Priya's explicit approval before any files are written.

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
