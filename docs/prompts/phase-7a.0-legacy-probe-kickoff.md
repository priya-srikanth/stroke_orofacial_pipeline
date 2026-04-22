# Phase 7a.0 Kickoff — Legacy-Cell Vendoring + NPZ Baseline Probe (docs-only)

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation to invoke:

> Read `docs/prompts/phase-7a.0-legacy-probe-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a (DLC-kinematics interpolation port) is gated on three artifacts that
do not yet exist in this repo:

1. **Vendored legacy cells.** The canonical legacy interpolation logic lives
   in two large notebook cells on the Mac workstation. They are not readable
   from the Windows VSCode host without either (a) shelling into the Mac or
   (b) vendoring a read-only excerpt into this repo. Phase 8a.7.5 set the
   precedent with `docs/legacy_snippets/behavior_report_PS_455_551.py` — a
   permanent, git-tracked, `# ruff: noqa`-headered snippet with a provenance
   preamble documenting source path, line range, and CLAUDE.md §"Legacy code
   version disambiguation" resolution. 7a needs the same pattern for tongue
   Cell 23 (~763 lines) and jaw Cell 22 (~755 lines).

2. **scipy-version pin.** `docs/phase-7/interpolation-strategy.md` §6 parity
   strategy notes that PCHIP is implementation-dependent across scipy
   versions. The parity script must pin `scipy.__version__` to the
   legacy-era version; that version is not yet recorded. It's visible in
   the legacy notebook's Cell 1 import block (`scipy.__version__` printed
   or pinned) — 7a.0 extracts it and records it so 7a.1+ can wire it into
   the parity harness.

3. **Per-animal per-bodypart baseline seed table.** Per
   `docs/phase-7/interpolation-strategy.md` §3.1, each legacy NPZ at
   ```
   {MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS{NN}/PS{NN}_{bodypart}_kinematics/processed_interpolated_data/{center_mode}/PS{NN}_{YYYYMMDD}_cam2_{bodypart}_interp_v5p3.npz
   ```
   carries its own `X0` / `Y0` keys. These are the authoritative seed for
   `configs/animals.yaml kinematics_baselines:` in 7a.2. Before we can fill
   `animals.yaml` confidently we need a probe showing, for each
   `(animal, bodypart)` combo, **whether X0/Y0 is stable across sessions** —
   because the §3.1 acceptance gate says "If a value is missing or ambiguous
   (e.g., the per-animal X0/Y0 differs across sessions for the same
   bodypart, suggesting Priya retuned mid-cohort), STOP and ask".

This sub-phase is **docs-only** — no `src/` edits, no `configs/` edits, no
tests. It lands three artifacts:

- `docs/legacy_snippets/tongue_cell23_interp_v5p3.py` — tongue Cell 23
  vendored with provenance header.
- `docs/legacy_snippets/jaw_cell22_interp_v5p3.py` — jaw Cell 22 vendored
  with provenance header.
- `docs/phase-7/baseline-seed-table.md` — per `(animal, bodypart)` X0/Y0
  probe results + scipy-version pin + disambiguation findings, with an
  "all-stable / needs human decision" verdict line per combo.

No tag for 7a.0 (docs-only, no behavior change). Phase-close tag convention
(`v{phase}-{slug}`) resumes at 7a.1 when the interpolation module lands.

## Before anything else

Re-read (order matters — CLAUDE.md first, design brief last):

- `CLAUDE.md` — all rules apply. Especially §"Ground Rules" (no
  modification of legacy repos; no modification of source data; copy, do
  not move), §"Legacy code version disambiguation" (3-tier rule), §"Git
  discipline" (feature branch, pre-commit hook, never force-push), and
  §"Environment activation".
- `docs/DECISIONS.md` — scan the 2026-04-22 entries (namespaced-tag
  applies_to schema, Phase 7a brief §10 canonical, parity-gate principle).
- `docs/phase-7/interpolation-strategy.md` — §1 scope, §3.1 per-animal
  baselines, §6 parity strategy, §10 sign-off resolutions. This brief is
  the authoritative spec — 7a.0 reads from it, does not rewrite it.
- `docs/legacy_snippets/behavior_report_PS_455_551.py` — **template for
  the provenance preamble** you will add to both vendored cells. Match
  its shape exactly: `# ruff: noqa` / `# fmt: off` header, `Purpose`,
  `Source provenance`, `Disambiguation`, `CLAUDE.md compliance` sections,
  then the verbatim legacy source.

## Environment activation

Required before any `pytest`, `ruff`, `pip`, `python`, `papermill`, or
notebook-execution command:

```bash
conda activate stroke_orofacial
which python                                      # must print a path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"               # must succeed without error
```

If `conda activate` fails, fall back to `conda run -n stroke_orofacial
<command>` per-command. If the `import` check fails with
`ModuleNotFoundError`, run `pip install -e . --no-deps` in the activated
env and retry. Do not begin work until `pytest --collect-only` completes
without import errors.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath           # should print: .githooks
git checkout -b docs/phase-7a-legacy-probe
git branch --show-current                 # must print: docs/phase-7a-legacy-probe
```

## Precheck

Before doing any file writes, verify three access paths:

1. **Legacy Mac notebook access.** Claude Code inside VSCode on Windows
   does not have a local clone of `/Users/Priya2/Github/...`. Priya will
   have pushed a working copy of both notebooks to a known location on
   the Windows filesystem (or to the MICROSCOPE UNC mount). Ask her for
   the on-Windows path to:
   - `tongue_reward_aligned_interp_v5p3.ipynb` (or its dated-parent
     notebook) — Cell 23 source.
   - `jaw_reward_aligned_interp_v5p3.ipynb` (or its dated-parent
     notebook) — Cell 22 source.

   If Priya has not pre-staged these files, STOP and ask her to do so
   before proceeding. Do not attempt to extract cells over SSH or
   screen-scrape.

2. **MICROSCOPE UNC reachability.** Verify the probe target directory is
   readable:
   ```powershell
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis"
   # must print True
   Get-ChildItem "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis" -Directory | Select-Object -First 3
   # must list PS* folders
   ```
   If `Test-Path` returns False or the listing is empty, STOP and ask
   Priya to re-mount the share. Do not try to paper over UNC access
   issues with ad-hoc mount commands.

3. **scipy version probe.** Get the legacy-era scipy version. Two
   complementary sources (report both if they agree):
   - The legacy notebook's Cell 1 import block — if it prints or pins
     `scipy.__version__`, record it.
   - If a representative legacy NPZ was saved with scipy metadata, load
     one with `np.load(..., allow_pickle=True)` and check for a
     `scipy_version` or similar key (unlikely but cheap to verify).

   If neither source records the scipy version explicitly, STOP and ask
   Priya what conda env she last ran the legacy notebooks in — the
   `conda list | grep scipy` output from that env is the pin.

## Sequence

### 1. Vendor tongue Cell 23

1. Extract the Cell 23 source verbatim from the legacy tongue notebook
   Priya pre-staged. Do NOT edit the source — no reformat, no lint,
   no import-hoist, no "fix" of dead code inside the cell. This is a
   faithful capture.
2. Write to `docs/legacy_snippets/tongue_cell23_interp_v5p3.py` with the
   provenance preamble:
   ```python
   # ruff: noqa
   # fmt: off
   """
   Legacy reference snippet — READ-ONLY.

   Purpose
   -------
   Read-only reference for Phase 7a (DLC-kinematics interpolation port).
   Captured here so the Windows VSCode workstation (which does not have a
   local clone of the Mac-side legacy Github repo) can perform byte-identical
   parity validation of the v5p3 interpolation algorithm against the canonical
   legacy implementation.

   Source provenance
   -----------------
   Canonical source file:
       <legacy-notebook-absolute-path-on-Mac>
   Cell index (0-indexed): 23
   Cell line range captured: <N to M of the full Cell 23 source>
   Cell SHA256 at capture time: <hex>

   Disambiguation
   --------------
   Per CLAUDE.md §"Legacy code version disambiguation" 3-tier rule, the
   canonical version was selected as follows within the notebook family:

       Candidate                                              mod time          resolution
       -----------------------------------------------------  ----------------  ----------
       <list every tongue_*interp*.ipynb Priya has>           <mtime>           <CANONICAL | SUPERSEDED by YYYYMMDD | DEPRECATED (_v0)>

   The canonical version is <filename> (<reason from 3-tier rule>).

   CLAUDE.md compliance
   --------------------
   - This file is a NEW read-only reference committed into the consolidation
     repo. It does NOT modify, overwrite, rename, or delete the canonical
     legacy source. (CLAUDE.md Ground Rules §1, §2.)
   - `# ruff: noqa` and `# fmt: off` ensure the legacy source is NEVER
     linted, reformatted, or auto-fixed by this repo's tooling. The source
     must stay byte-identical to capture time.
   """

   # === BEGIN VERBATIM CELL 23 SOURCE ===
   <verbatim cell source>
   # === END VERBATIM CELL 23 SOURCE ===
   ```
3. Verify byte-identicality: re-extract the cell source independently and
   `diff` against the written file's BEGIN→END region. Must be empty.

### 2. Vendor jaw Cell 22

Same pattern as Step 1, targeting the legacy jaw notebook's Cell 22,
written to `docs/legacy_snippets/jaw_cell22_interp_v5p3.py`.

### 3. NPZ baseline probe — ALL sessions per (animal, bodypart) combo

For each combo in the cross-product of:

- animal ∈ {PS46, PS47, PS48, PS49, PS50, PS51, PS52, PS53, PS54, PS55}
  (every PS-prefixed folder under `O2_analysis/`; enumerate live rather
  than hardcoding — an empty cohort list is a reportable finding)
- bodypart ∈ {tongue, jaw}
- center_mode derived from bodypart:
  - tongue → `centered_spout_midpoint`
  - jaw → `centered_eye_midpoint`

enumerate **every available NPZ** in
```
{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/{animal}_{bodypart}_kinematics/processed_interpolated_data/{center_mode}/
```
matching the pattern `{animal}_{YYYYMMDD}_cam2_{bodypart}_interp_v5p3.npz`.
For each NPZ load with `np.load(..., allow_pickle=True)` and extract:

- `X0` (scalar float)
- `Y0` (scalar float)
- `fps` (scalar)
- `n_frames` (scalar)
- `baseline_stage` (string — the legacy-recorded "which stage produced this
  baseline" tag; preserve for provenance)

**Cross-session stability analysis per combo.** For each `(animal, bodypart)`:

- `N_sessions` — count of NPZs found
- `X0_min`, `X0_max`, `X0_median`, `X0_std` across all sessions
- `Y0_min`, `Y0_max`, `Y0_median`, `Y0_std` across all sessions
- `max |ΔX0|` = `X0_max − X0_min`, `max |ΔY0|` = `Y0_max − Y0_min`
- `verdict`:
  - `STABLE` — max |ΔX0| < 1e-3 AND max |ΔY0| < 1e-3 (values are
    floats to 6+ decimals in the NPZs; differences in this range are
    floating-point noise and confirm Priya kept a single baseline
    throughout the cohort). Seed `animals.yaml` with the median.
  - `NEEDS_HUMAN_DECISION` — max |ΔX0| ≥ 1e-3 OR max |ΔY0| ≥ 1e-3.
    Priya retuned mid-cohort; do not seed. Report for her decision.
  - `INSUFFICIENT` — `N_sessions == 0` (combo has no NPZs — animal
    may have been excluded from that bodypart's analysis). Flag for
    her review, do not seed.

Threshold rationale: legacy X0/Y0 are hand-tuned by plot inspection in
pixels. Priya does not set baselines with sub-pixel precision. Any
cross-session spread ≥ 1e-3 px is a deliberate retune, not noise. This
threshold is a starting point — the probe report surfaces the actual
spreads, so if the empirical distribution suggests a different cut
point, 7a.1 plan-mode can revise before anything writes to `animals.yaml`.

### 4. Emit `docs/phase-7/baseline-seed-table.md`

Structure:

```markdown
# Phase 7a Baseline Seed Table — Per-Animal Per-Bodypart X0/Y0 Probe

**Generated by Phase 7a.0 prep run (CC-in-VSCode), <YYYY-MM-DD>.**
**Unblocks:** 7a.2 (`configs/animals.yaml kinematics_baselines:` seeding).

## scipy-version pin

- Legacy-era scipy version: `<x.y.z>`
- Source: <legacy notebook Cell 1 import block | legacy conda env
  `scipy` entry | NPZ metadata key>
- Current `stroke_orofacial` env scipy version: `<x.y.z>`
- Parity script pin decision: <match | widen tolerance per §6>.

## Legacy-notebook disambiguation

Applied CLAUDE.md 3-tier rule to `tongue_*interp*.ipynb` and
`jaw_*interp*.ipynb` families. Findings:

| Family | Candidates found | Canonical | Reason |
|---|---|---|---|
| tongue | <list all filenames+mtimes> | <chosen> | <3-tier rule cite> |
| jaw    | <list all filenames+mtimes> | <chosen> | <3-tier rule cite> |

Any `_v0` / `_mod` / `_old` siblings: <list> — treated as DEPRECATED,
not used.

## Cohort enumeration

Animals found under `O2_analysis/`: <PS46, PS47, ..., PS55>. Any cohort
animal absent from this list: <none | list with rationale>.

## Per-combo probe results

### Summary table

| Animal | Bodypart | N_sessions | X0 median | X0 min/max | max|ΔX0| | Y0 median | Y0 min/max | max|ΔY0| | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| PS46 | tongue | <N> | <m> | <mn>/<mx> | <Δ> | <m> | <mn>/<mx> | <Δ> | STABLE | NEEDS_HUMAN_DECISION | INSUFFICIENT |
| PS46 | jaw    | ... |
| PS47 | tongue | ... |
| ... (every (animal, bodypart) combo) ...

### Detailed per-session appendix

For each combo, list every NPZ's X0, Y0, baseline_stage, fps, n_frames.
Collapsed under a `<details>` block per combo so the summary stays
scannable; open the detail only for combos with `NEEDS_HUMAN_DECISION`.

<details>
<summary>PS46 tongue — per-session detail (N sessions)</summary>

| Session date | NPZ path | X0 | Y0 | baseline_stage | fps | n_frames |
|---|---|---|---|---|---|---|
| 20250307 | .../PS46_20250307_cam2_tongue_interp_v5p3.npz | <x> | <y> | <stage> | 250 | <N> |
| ... |

</details>

<details>
<summary>PS46 jaw — per-session detail (N sessions)</summary>
...
</details>

...

## Verdicts requiring human decision

For each combo with `NEEDS_HUMAN_DECISION`:

- **{animal} {bodypart}:** X0 ranges from <mn> to <mx> (Δ=<d>); Y0 ranges
  from <mn> to <mx> (Δ=<d>). Retune pattern (monotonic drift / single
  mid-cohort jump / bimodal / other): <pattern>. Sessions on each side
  of the retune point: <list>.
  **Question for Priya:** which X0/Y0 is the intended "current" baseline
  for this animal, or should `animals.yaml` carry a date-scoped baseline
  (e.g., `kinematics_baselines.tongue.y0_by_date`)? If the latter, the
  config schema in `interpolation-strategy.md` §3.1 needs revision
  before 7a.2 can proceed.

For each combo with `INSUFFICIENT`:

- **{animal} {bodypart}:** no NPZs found at
  `{MICROSCOPE}/.../O2_analysis/{animal}/{animal}_{bodypart}_kinematics/processed_interpolated_data/{center_mode}/`.
  Confirm this animal is correctly excluded from `{bodypart}` analysis
  (likely already captured in `AnimalInfo.exclusions` with
  `applies_to: [dlc.{bodypart}]`), or that the missing-data condition
  should be added to the exclusions list before 7a.1 lands.

## Unblocks for 7a.1 / 7a.2

- 7a.1 parity harness: scipy pin recorded above, legacy cells vendored
  at `docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py`.
- 7a.2 `animals.yaml` seeding: for every combo marked STABLE, the median
  is the seed value. Combos marked NEEDS_HUMAN_DECISION block 7a.2
  until Priya answers the question listed above. Combos marked
  INSUFFICIENT block 7a.2 only if their animal+bodypart was not already
  excluded in Phase 7-pre.
```

### 5. Commit + push + open PR

```bash
git add docs/legacy_snippets/tongue_cell23_interp_v5p3.py \
        docs/legacy_snippets/jaw_cell22_interp_v5p3.py \
        docs/phase-7/baseline-seed-table.md
git status                                     # must show ONLY those three files
git diff --cached --stat                       # sanity check
git commit -m "docs(phase-7a.0): vendor legacy cells + NPZ baseline probe"
git push -u origin docs/phase-7a-legacy-probe
gh pr create --base main --fill
```

PR description body (paste verbatim, fill the bracketed items):

```
Phase 7a.0 — prep for Phase 7a interpolation implementation. Docs-only,
no behavior change, no tag.

Artifacts:
- docs/legacy_snippets/tongue_cell23_interp_v5p3.py (<N> lines, verbatim
  capture of <notebook>:Cell 23, SHA256 <hex>)
- docs/legacy_snippets/jaw_cell22_interp_v5p3.py (<N> lines, verbatim
  capture of <notebook>:Cell 22, SHA256 <hex>)
- docs/phase-7/baseline-seed-table.md — per-(animal,bodypart) X0/Y0
  probe, scipy-version pin, disambiguation findings.

Unblocks:
- 7a.1 — parity harness (needs vendored cells + scipy pin)
- 7a.2 — animals.yaml kinematics_baselines seeding (needs STABLE verdicts)

Outstanding questions for Priya (see baseline-seed-table.md
"Verdicts requiring human decision"):
- <list each NEEDS_HUMAN_DECISION combo verbatim, or "none — all STABLE">
- <list each INSUFFICIENT combo, or "none">

No tag — 7a.0 is docs-only. Phase-close tagging resumes at 7a.1.
```

## Verification commands (run before the `gh pr create` step)

```bash
# 1. Confirm no src/ or configs/ changes snuck in:
git diff --cached --stat | grep -E '^(src|configs|tests)/' && echo "FAIL: non-docs changes in commit" || echo "OK: docs-only"

# 2. Confirm legacy snippets are marked noqa + fmt-off:
head -3 docs/legacy_snippets/tongue_cell23_interp_v5p3.py
head -3 docs/legacy_snippets/jaw_cell22_interp_v5p3.py
# must show `# ruff: noqa` then `# fmt: off` in first two lines

# 3. Ruff smoke — legacy snippets must be ignored:
ruff check docs/legacy_snippets/  # must report 0 errors
# If ruff reports errors on the vendored files, the noqa header is wrong;
# fix the header, do not edit the legacy source.

# 4. Markdown lint smoke on the seed table:
# (no repo-configured markdown linter; visual review is acceptable.
# Confirm the per-combo summary table renders as a table — every row has
# the same pipe count as the header.)

# 5. Sanity: every cohort animal appears in the seed table:
grep -c '^| PS' docs/phase-7/baseline-seed-table.md
# must equal 2 × (cohort size); e.g. 20 for a 10-animal cohort.

# 6. Branch check before commit:
git branch --show-current  # must be docs/phase-7a-legacy-probe (NOT main)
```

## Constraints

- **Docs-only.** No `src/`, `configs/`, `tests/`, `notebooks/`, or
  `.conda/` changes. The commit diff must touch only `docs/legacy_snippets/`
  and `docs/phase-7/`.
- **Faithful capture.** The vendored legacy cells are NOT cleaned up, NOT
  reformatted, NOT linted. They exist to be byte-identically referenced
  by parity validation. Any "fix" of the legacy source belongs in 7a.1
  against the in-repo `src/` port, not in `docs/legacy_snippets/`.
- **No MICROSCOPE writes.** Every probe operation is `np.load` + read-only
  access to metadata. No `np.save`, no directory creates, no NPZ
  overwrites. If the probe accidentally modifies the O2_analysis tree,
  that's a CLAUDE.md §"Ground Rules" §1 violation — STOP.
- **No silent workarounds if UNC access fails.** If `Test-Path` returns
  False mid-probe, STOP the probe, report the access failure, and ask
  Priya. Do not skip combos silently.
- **Stop-and-ask triggers:**
  - Legacy-notebook candidates that the 3-tier rule cannot uniquely
    resolve (tied mtimes, no dated suffix on any candidate).
  - Legacy notebook's Cell 1 does not record scipy version AND Priya's
    legacy conda env is not recoverable.
  - A combo with `N_sessions ≥ 1` but X0 or Y0 missing from the NPZ
    (legacy save path wrote the NPZ without populating these keys —
    real risk for old sessions).
  - `npz` files whose `X0`/`Y0` are not numpy scalars (e.g., arrays or
    tuples — shape drift suggests the legacy algorithm evolved
    mid-cohort in ways the brief didn't anticipate).

## Exit criteria

- Branch `docs/phase-7a-legacy-probe` pushed to origin.
- PR opened against `main` with the body template above, filled.
- All three artifacts present, ruff-clean on legacy snippets, markdown
  table formatting valid.
- `baseline-seed-table.md` "Verdicts requiring human decision" section
  populated (may be empty if all combos STABLE — that's fine, note
  "none — all STABLE" explicitly).
- PR description lists every NEEDS_HUMAN_DECISION and INSUFFICIENT combo
  verbatim for Priya's review queue.

Post-merge: 7a.0 does NOT get a phase-close tag. Merge commit stands on
its own in history; tagging resumes at the first code-landing sub-phase
(7a.1).
