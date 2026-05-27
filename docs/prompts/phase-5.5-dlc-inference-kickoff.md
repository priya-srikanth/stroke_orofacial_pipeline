# Phase 5.5 Kickoff — DLC Inference Port (O2)

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-5.5-dlc-inference-kickoff.md` and follow the instructions in full.

---

## Context

Phase 5.5 per `docs/DECISIONS.md` "2026-04-18 — DLC inference port scheduled
as dedicated mini-phase": port the DeepLabCut inference code from the legacy
notebook `20251112_DLC_batch_video_analysis_O2.ipynb` into
`src/stroke_orofacial/dlc_inference_o2/`. This module is a **standalone tool
that runs on the HMS O2 GPU cluster**, not on Priya's workstation.

This is a smaller, self-contained mini-phase sitting between Phase 5
(whole-session spatial) and Phase 6 (reward-aligned spatial). It does NOT
block any other phase — existing DLC outputs on MICROSCOPE are what Phases
4-7 consume. Porting it here means the consolidated repo contains the
inference tool before Phase 6 starts.

Scope:
- Port the notebook's inference pipeline (running DLC on Flea3 videos on O2
  GPU nodes, then copying outputs to MICROSCOPE).
- Clean up: apply disambiguation, dead-code identification, and hardcoded-
  constant extraction just like other phases.
- Document the O2 workflow in a README: env setup on O2, how to invoke,
  inputs, outputs, failure modes.
- Parity verification: optional. If a short test video can be run on O2, do
  it. Otherwise rely on code-review + structural parity against the legacy
  notebook.

## Before anything else

Re-read these and confirm in one sentence that the data-safety, password-
handling, and plan-requirements constraints are internalized:

- `CLAUDE.md` — full file. All eight ground rules, the disambiguation
  policy, and the "Phase plan requirements" section apply.
- `docs/DESIGN.md` §3 (note: `src/stroke_orofacial/dlc_inference_o2/` is
  already named in the target repo layout — this phase fills it in).
- `docs/MIGRATION_LOG.md` Phases 0-5 (context on what exists).
- `docs/DECISIONS.md` — pay special attention to "2026-04-18 — DLC inference
  port scheduled as dedicated mini-phase" which has the password-handling
  strategy baked in.

## Known O2 details (pre-confirmed)

- **Priya's O2 login:** `ps150@o2.hms.harvard.edu`.
- **SSH key auth is already set up** on Priya's MacBook — `ssh ps150@o2.hms.harvard.edu` logs in without a password prompt. Use key auth exclusively; do not attempt password workflows.
- **O2 DLC conda env:** `deeplabcut`. Activate via
  `conda activate deeplabcut` after connecting.
- **O2 filesystem convention for DLC code + outputs:** the legacy notebook uses specific paths on O2 — discover these in plan mode by reading the notebook, and capture them in the module's README.

## SSH / password handling (non-negotiable)

This phase involves SSH connections to HMS O2. Priya's directive (per
DECISIONS.md):

1. **Strongly prefer SSH key auth over password auth.** If Priya has
   `ssh-keygen`'d and `ssh-copy-id`'d her key to O2 already, no password
   prompts will occur. If not set up, this is a one-time setup she handles
   herself; do not automate it.
2. **If password entry is needed during this session**, Claude Code may
   prompt Priya to enter it at the interactive terminal prompt. The password
   goes to stdin of the running command (ssh), not to Claude Code's context.
   The terminal masks the input so it does not appear in scrollback.
3. **Never** pass passwords via `sshpass -p <password>`, environment
   variables (`SSHPASS=...`), or any persistent store. These make the
   password visible in shell history, process listings, or Claude Code's
   scrollback. Hard-forbidden.
4. **Never** save a password to any file, commit, or config. Claude Code
   does not persist secrets across sessions and should not create any
   mechanism that would.
5. **If an SSH operation requires credentials and key auth isn't set up,
   STOP and ask Priya** rather than attempting sshpass or env-var workarounds.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath        # must print: .githooks
git checkout -b phase-5.5-dlc-inference
git branch --show-current              # must print: phase-5.5-dlc-inference
```

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements:

1. **Legacy file disambiguation.** Inspect
   `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` and both legacy
   repos for any DLC-inference-related files. Apply the 3-tier rule.
   Candidates so far:
   - `20251112_DLC_batch_video_analysis_O2.ipynb` — likely canonical.
   - Anything else in `old_code/` or elsewhere that does DLC inference.
2. **Dead code identification.** Cell-by-cell classification of the
   canonical notebook. Production (actually runs DLC on videos) vs.
   Exploratory (one-off test, debugging a specific video, timing
   experiments) vs. Deprecated (older versions / commented out).
3. **Sub-phase breakdown.** Likely small: a module refactor + a README + a
   small test or sanity check. Expected ~3-4 sub-phases.
4. **Parity strategy.** Difficult here because inference produces large H5
   files via GPU compute. Options in order of preference:
   - Run the new module on one short test video on O2 and compare H5 outputs
     to the legacy output byte-level for that same video. Requires Priya's
     O2 credentials and ~15 min.
   - Visual/shape parity: same input video → same output keypoints with the
     same model, verify file structure matches DLC's canonical format.
   - Code-only review: faithful port of the legacy algorithm with clean
     structure, no behavior verification. Weakest but acceptable for
     infrastructure code.
   Plan should propose one and flag the tradeoffs; Priya decides.
5. **Hardcoded constants → `configs/defaults.yaml`.** DLC project path on
   O2, video file glob pattern, output destination path template, GPU queue
   name, conda env name, any resource limits.

Wait for explicit Priya approval before writing any files.

## Expected scope (to seed plan mode, not prescriptive)

Likely shape:

- `src/stroke_orofacial/dlc_inference_o2/__init__.py`
- `src/stroke_orofacial/dlc_inference_o2/runner.py` — core: given a video
  path and DLC project, invoke DLC's inference API and write outputs to the
  expected MICROSCOPE location.
- `src/stroke_orofacial/dlc_inference_o2/batch.py` — discovers videos for
  an animal/date range, loops over them invoking `runner`.
- `src/stroke_orofacial/dlc_inference_o2/o2_job.py` or similar — wraps batch
  invocation in an SBATCH script for queue submission. Generates the SBATCH
  file, submits, monitors.
- `src/stroke_orofacial/dlc_inference_o2/README.md` — **required.** The O2
  workflow is operationally distinct from the rest of the repo, and future
  users (or future you) need explicit instructions.
- `notebooks/10_dlc_inference.ipynb` — optional thin orchestrator if invoking
  interactively from Priya's workstation is useful.

O2 env setup (captured in the module's README):
- The O2 DLC env lives somewhere like `/n/hms/.../dlc-env` or a conda env
  named `deeplabcut`. The README documents how to activate it.
- GPU partition name and resource requests (CPU, memory, time) as configured
  in the legacy notebook.

## Constraints

- No writes outside `~/Github/stroke_orofacial_pipeline/` except when SSH'd
  to O2 (in which case writes go to O2's filesystem at whatever path the
  legacy notebook uses — not to MICROSCOPE directly; output copy to
  MICROSCOPE is a separate step).
- DLC model project files at
  `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/DLC_train_config/` are
  read-only per CLAUDE.md ground rule 1.
- DLC inference outputs already on MICROSCOPE (from previous runs) are
  read-only — do not overwrite.
- Camera data (`.avi` + `timestamp*.csv` files in Rich's data tree) are
  read-only per CLAUDE.md ground rule 1.
- Pre-commit hook must not be bypassed.
- Before every commit, `git branch --show-current` must print
  `phase-5.5-dlc-inference`.
- SSH / password handling per the non-negotiable section above.

## Exit criteria

- Plan approved by Priya.
- Port produces a clean, documented module + README.
- Parity strategy from plan executed (whichever level Priya approves).
- Tests pass (may be thin — inference tests require GPU). Lint clean.
- `docs/MIGRATION_LOG.md` Phase 5.5 entry documents sub-phases, legacy
  disambiguation, dead-code classification, parity status (and what
  specifically wasn't verified), and any intentional behavior differences.
- `docs/DESIGN.md` §7 gets a new Phase 5.5 entry added (or §3 tree updated
  if the scope clarifies). This is the one place a design-doc edit is
  allowed in this phase — to reflect that DLC inference is now a real,
  implemented module rather than a named-but-empty subdirectory.
- `docs/DECISIONS.md` gets new entries for any cross-cutting decisions made
  during Phase 5.5 execution (likely: parity-level choice, any SSH-related
  convention).
- Pause for closeout review before PR.

If SSH operations or O2 env access surface blockers that Priya needs to
resolve (missing SSH key, wrong DLC env version, O2 queue policy changes),
STOP and ask rather than working around.
