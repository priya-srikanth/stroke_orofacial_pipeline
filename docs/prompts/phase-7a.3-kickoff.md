# Phase 7a.3 Kickoff — tongue per-trial features (lick1/lick2, per-lick velocity, licks-per-trial, licking dynamics, tongue angle)

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.3-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.2 merged 2026-04-24 as PR #83 on branch
`phase/7a.2-interpolation-impl`, tagged `v7a.2-interpolation-impl`
(merge commit `fbe91fd`). It landed:

- `src/stroke_orofacial/dlc_kinematics/interpolation.py` — the v5p3
  7-stage bodypart-parametric port (tongue Cell 23 + jaw Cell 22)
  with `InterpolationResult`, `_interpolate_bodypart_core`,
  `build_interpolated_trace`, and the by-animal-date wrapper.
- `configs/defaults.yaml dlc_kinematics:` block — bodypart-parametric
  constants per `interpolation-strategy.md` §7.
- `PathResolver.interpolated_trace(bodypart, animal, date, *, variant)`
  helper.
- `tests/test_dlc_interpolation.py` — 14 unit tests per strategy §8.
- 14-session × 2-bodypart parity at `atol=1e-6` against legacy NPZs:
  cohort-wide bit-identical on every in-scope dim under scipy 1.17.1
  Option A.
- DECISIONS 2026-04-24 entry codifying the 7 parquet columns + 9
  file-level metadata keys as the standing schema for all downstream
  consumers.

**The 7a.2 interpolated_traces parquet schema is LOCKED.** Phase 7a.3
does NOT touch it — every 7a.3 output goes to a new, separate output
tree.

### Phase 7a.3 scope: tongue per-trial features (NOT jaw, NOT velocity)

Phase 7a.3 is the first downstream phase that consumes the 7a.2
tongue interpolated-trace parquets. It ports the per-trial scalar
features and the per-frame tongue angle from the canonical tongue
notebook. **An audit on 2026-04-25 (caught V1 of this kickoff before
any code shipped) revealed:**

1. The legacy notebooks do NOT compute per-frame velocity as a stored
   product, do NOT compute per-trial amplitude_max / velocity_peak /
   angle_peak over the wide/tight reward-aligned windows that V1
   speculated about. V1's feature definitions did not match legacy
   reality. V2 (this doc) reflects the actual legacy.
2. The jaw notebook contains NO per-trial features. Its Cell 41 is a
   copy-paste of tongue code against files the jaw notebook never
   produces. Jaw per-trial work is deferred to a dedicated future
   **Phase 7a.3-jaw** with its own design discussion.

**What 7a.3 actually delivers, ported from the canonical tongue
notebook (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`):**

- **Cell 33 — lick1 / lick2 first-peak detection.** Slope-based
  rise/fall detector inside a 70–2000 ms post-reward window emits
  `(lick1_y_peak, lick1_t_peak_ms, lick1_x_at_ypeak, lick2_y_peak,
  lick2_t_peak_ms, lick2_x_at_ypeak)` per trial. CSV-only in legacy.
- **Cell 36 — per-lick peak velocity, first 5 licks per trial.**
  Slope-detector lick boundaries inside a 70–3000 ms post-reward
  window emit `vy_peaks_bylick: (n_trials, 5)` (and `vxy_peaks_bylick`
  if the legacy stores both). NPZ + CSV in legacy.
- **Cell 39 — licks-per-trial counts.** `n_licks` per trial.
- **Cell 42 — within-bout inter-lick-interval (ILI).** Bout-detected
  ILIs, lick rate, bout count. Bout parameters surface in Task 1
  audit as candidates for `defaults.yaml`.
- **Cell 50 — per-frame tongue angle.** Signed angle in spout-
  centered frame using a session-wide median eye_midpoint reference;
  per-trial angle scalars at lick1/lick2 peak and at per-lick peak
  velocity; per-trial pass criteria. Author labelled the cell
  "exploratory"; **Priya overrode to land it as production** — it is
  ready to include.

Everything else stays out of 7a.3. Phase 7a.3-jaw, future PSD phases,
whisker / face-velocity branches, and per-trial endpoint mismatch
classifiers are downstream.

### What 7a.3 delivers end-to-end

1. `docs/legacy_snippets/tongue_pertrial_features.py` — Cells 33, 36,
   39, 42, 50 vendored verbatim from the canonical tongue notebook
   with full SHA256 provenance header (legacy-snippet pattern from
   PR #79 / 7a.0).
2. `configs/defaults.yaml` — new
   `dlc_kinematics.tongue_pertrial:` block (lick-detector knobs, bout
   knobs, angle smoothing knobs, detection windows). Tongue-scoped;
   the existing 7a.2 `dlc_kinematics.tongue:` interpolation block
   stays intact.
3. `configs/animals.yaml` — extended **only if** Task 1 audit finds
   per-animal variation in lick-detector thresholds, bout parameters,
   detection windows, or angle pass criteria. If cohort-uniform, no
   `animals.yaml` change.
4. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` — new
   module computing per-trial scalars (lick1/lick2 metrics, per-lick
   peak velocity, n_licks, within-bout ILI / lick rate / bout count),
   per-frame tongue angle, and per-trial angle scalars. One session-
   level driver writes one parquet (per-frame angle) + one JSON
   (per-trial scalars) atomically.
5. `src/stroke_orofacial/paths.py` — add
   `tongue_pertrial_angle_parquet(animal, date)` and
   `tongue_pertrial_endpoints_json(animal, date)` resolver helpers.
6. `src/stroke_orofacial/dlc_kinematics/__init__.py` — export the new
   public symbols.
7. `tests/test_tongue_pertrial.py` — unit tests covering lick
   detection, peak-velocity aggregation, bout detection, angle
   computation, per-trial co-indexing, schema, and atomic write
   semantics.
8. `tests/scripts/parity_phase7a3_tongue_pertrial.py` — 14-session
   parity harness against legacy CSV/NPZ outputs (Cells 33 / 36 /
   39 / 42) and visual parity gate against legacy saved figures
   (Cell 50, comparison this phase or deferred).
9. `docs/DECISIONS.md` Phase 7a.3 entry — codifies the per-frame
   angle parquet schema, the per-trial endpoints JSON schema, the
   eye_midpoint = session-wide median convention, and parity
   acceptance.
10. `docs/MIGRATION_LOG.md` Phase 7a.3 entry.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five items.

1. **Legacy file disambiguation.** One source notebook:
   `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
   — the same notebook 7a.2 vendored Cell 23 from. Cells 33, 36, 39,
   42, 50 are downstream of Cell 23 in the same notebook.

   Apply the three-tier rule:
   - This notebook is the latest-dated within the tongue family
     (`20260203`). Older variants like `20251216_*` are explicitly
     superseded.
   - No sibling notebooks with distinct scope markers for these
     cells (`*_reward-aligned_*` siblings exist for upstream
     parquet-build work but do NOT contain per-trial scalar / angle
     cells; do not port from those siblings).
   - Trust 7a.2's prior 3-tier resolution for the parent notebook;
     7a.3 adds no new candidates, only new cell selection within the
     same already-canonical notebook.

   The jaw notebook (`20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`,
   SHA256 `7BE0EEE06777EAA4D1A954076CC39793EBB422E5A700B47A8615873E949E95DF`)
   is **explicitly out of scope** for 7a.3. Audit confirmed it has no
   per-trial features that this phase ports. Phase 7a.3-jaw is a
   separate future phase.

2. **Dead code identification.** Cell-level walk inside the tongue
   notebook (audit completed 2026-04-25), classifying each cell:

   - **Production (port):**
     - Cell 33 — lick1/lick2 first-peak slope detector, post-reward
       70–2000 ms window. Emits `lick1_y_peak`, `lick1_t_peak_ms`,
       `lick1_x_at_ypeak`, `lick2_*` per trial. CSV-only in legacy.
     - Cell 36 — per-lick peak velocity, first 5 licks per trial,
       post-reward 70–3000 ms window. NPZ + CSV in legacy. Detection
       knobs: `SLOPE_THR_PX_PER_S`, `RISE_MIN_MS`, `FALL_MIN_MS`,
       `MIN_PEAK_Y_ABS`, `PEAK_PAD_MS`, `STRICT_NO_FALLBACK = True`.
     - Cell 39 — licks-per-trial counts. `n_licks` per trial.
     - Cell 42 — within-bout ILI / lick rate / bout count. Bout
       parameters (ILI threshold, min-licks-per-bout, etc.) surface
       in Task 1 audit as candidates for `defaults.yaml`.
     - Cell 50 — per-frame tongue angle in spout-centered frame
       referenced to session-wide median eye_midpoint, gaussian σ=8 ms
       smoothing, `ANGLE_SIGN_FLIP = -1.0`. Per-trial angle scalars
       at lick1/lick2 peak (`lick1_angle_at_ypeak`,
       `lick2_angle_at_ypeak`), at per-lick peak velocity
       (`angle_at_peak_velocity_bylick: (n_trials, 5)`), and signed
       max angle per lick (`angle_max_signed_per_lick: (n_trials, 5)`).
       Per-trial pass criteria emit `tongue_angle_pass: bool[n_trials]`.
       Production despite author's "exploratory" label per Priya's
       2026-04-25 directive.
   - **Exploratory (do NOT port):** all plot-velocity-traces QC cells,
     plot-amplitude-distribution cells, ad-hoc histogram cells, and
     the `angle_phase_exploratory` plotting cells (legacy figures
     saved to MICROSCOPE; we compare against them visually rather
     than re-emitting plot code in this phase).
   - **Deprecated (do NOT port):** any cell referencing
     `_v0`/`_mod`/`_old`-suffixed helpers from the same notebook
     author's history.
   - **Ambiguous (stop-and-ask if hit):** any cell that mixes
     analysis with manual per-animal date-window editing (analogous
     to the `DATE_START` / `DATE_END` pattern from 7a.2). Scope in
     the consolidated pipeline comes from `animals.yaml` via
     `SessionManifest`, not from notebook-level constants. If a cell
     embeds `if animal == "PSXX": ...` branches, STOP and report
     before porting.

   Task 1's STOP-and-report includes the per-cell classification
   table with the actual cell line ranges + extracted user-tunable
   knobs.

3. **Sub-phase breakdown.** 8 commits (kickoff rewrite + 7 task
   commits), estimated line counts:

   - Commit 1 (preflight, this kickoff doc rewrite): replace V1
     content with V2 content + branch rename.
   - Commit 2 (Task 1): legacy-cell vendoring + per-animal audit.
     One new file under `docs/legacy_snippets/` (~400–600 lines
     vendored across Cells 33/36/39/42/50) + audit findings
     reported to Priya.
   - Commit 3 (Task 2): `configs/defaults.yaml
     dlc_kinematics.tongue_pertrial:` block (~50–80 YAML lines)
     + `configs/animals.yaml` extension if Task 1 audit demands it
     + `PathResolver.tongue_pertrial_angle_parquet()` and
     `PathResolver.tongue_pertrial_endpoints_json()` helpers (~50
     lines paths.py) + 4–6 path unit tests.
   - Commit 4 (Task 3): `src/stroke_orofacial/dlc_kinematics/
     tongue_pertrial.py` (~500–700 lines: lick detector, peak-
     velocity aggregator, bout detector, angle computation,
     per-trial scalar aggregators, session-level writer emitting
     parquet + JSON atomically).
     `src/stroke_orofacial/dlc_kinematics/__init__.py` export of new
     public symbols.
   - Commit 5 (Task 4): `tests/test_tongue_pertrial.py` (~350–500
     lines, unit tests + helper fixtures).
   - Commit 6 (Task 5): `tests/scripts/parity_phase7a3_tongue_pertrial.py`
     parity harness (~250–350 lines). Cohort run results recorded
     in the stop-and-report (not committed).
   - Commit 7 (Task 6): `docs/DECISIONS.md` + `docs/MIGRATION_LOG.md`
     entries.
   - Commit 8 (Task 7): PR open. Tag is post-merge.

4. **Parity strategy.** Same 14-session set as 7a.2 — 9 primary
   (PS46/PS54/PS55 × 3 dates each) + 3 stress (PS51/20250430,
   PS54/20250501, PS55/20250502) + 2 late post-stroke (PS54/20250607,
   PS55/20250607). Tongue-only this phase, so 14 (animal, date)
   sessions = 14 comparisons per metric.

   **Comparison plan, per legacy product:**
   - **Cell 33 (lick1/lick2 CSV):** consolidated emits same scalars in
     the per-trial JSON. Parity comparison loads legacy CSV via
     `pd.read_csv`, extracts the 6 columns, compares element-wise at
     `atol=1e-6` against the consolidated JSON arrays. Per-trial
     co-indexed via `trial_indices`.
   - **Cell 36 (peak velocity NPZ):** consolidated emits
     `vy_peaks_bylick` (and `vxy_peaks_bylick` if legacy emits both)
     in the per-trial JSON. Parity comparison loads legacy NPZ via
     `np.load`, compares `(n_trials, 5)` arrays at `atol=1e-6`.
   - **Cell 39 (n_licks):** scalar per trial; load legacy
     CSV/NPZ (whichever Task 1 audit confirms) and compare element-
     wise.
   - **Cell 42 (ILI / lick rate / bout count):** load legacy
     CSV/NPZ; compare per-trial arrays element-wise.
   - **Cell 50 (per-frame angle parquet + per-trial angle scalars +
     pass mask):** Cell 50 is exploratory in legacy and was NOT
     emitted to disk as NPZ — its consumable artifact is the saved
     plots at `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\
     Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics\
     kinematics_figures\centered_spout_midpoint\angle_phase_exploratory`.
     Parity comparison for Cell 50 is **visual** in this phase: side-
     by-side render of the consolidated outputs against the saved
     figures, on the smoke session, reported in the Task 5 stop-and-
     report. Numerical regression of the angle math is covered by the
     Task 4 unit tests (synthetic geometry); cross-session numerical
     parity is deferred to a follow-up if the visual comparison
     surfaces a discrepancy.

   **Acceptance:**
   - All 14 × 4 numerical comparisons (Cell 33, 36, 39, 42) return
     `status = pass` at `atol=1e-6`.
   - `skip_missing` is tolerated for sessions where the legacy
     CSV/NPZ is genuinely absent.
   - Cell 50 visual parity report on the smoke session shows no
     gross discrepancy with the saved figures (or, if the comparison
     is deferred, the deferral is recorded in the Task 5 report).
   - Any `status = fail` → STOP and report; do not widen the
     tolerance, do not advance to Task 6.

5. **Hardcoded constants.** All numerical knobs land in
   `configs/defaults.yaml` under
   `dlc_kinematics.tongue_pertrial.<key>`:
   - **Lick detector** (Cells 33 + 36):
     `slope_thr_px_per_s`, `rise_min_ms`, `fall_min_ms`,
     `min_peak_y_abs`, `peak_pad_ms`, `strict_no_fallback: true`.
   - **Detection windows (preserve verbatim per Q4 decision):**
     `lick12_window: {start_ms: 70, end_ms: 2000}` (Cell 33),
     `peak_velocity_window: {start_ms: 70, end_ms: 3000}` (Cell 36),
     `n_licks_per_lick: 5` (Cell 36).
   - **Bout detector** (Cell 42): bout parameters surfaced in Task 1
     audit; expected knobs include ILI bout-break threshold, min
     licks per bout. Surface explicitly so Priya can choose which to
     promote to per-animal vs cohort-uniform.
   - **Angle** (Cell 50):
     `eye_midpoint_aggregator: median`,
     `eye_landmark_source: <Task-1-resolved DLC eye column(s) +
     parquet path>`,
     `angle_smoothing_gaussian_sigma_ms: 8.0`,
     `angle_sign_flip: -1.0`,
     `tongue_angle_pass: <Task 1 audit defines criteria>`.
   - **Reference frame names**: `tongue.center_mode:
     centered_spout_midpoint` (already in 7a.2 block); the angle
     module reads this and translates the eye_midpoint into the
     spout-centered frame via `eye_in_spout_frame = eye_raw -
     spout_raw`.

   Per-animal variation (if Task 1 audit finds any) lives under
   `configs/animals.yaml` per animal, mirroring the existing
   `kinematics_baselines:` and `analysis_params.break_thr_*` patterns.
   Module reads from
   `params["dlc_kinematics"]["tongue_pertrial"][...]` first, then
   per-animal overrides via `animal_info` if present.

   No numeric literals inside `tongue_pertrial.py` that vary per
   animal or per cohort. Detection-window bounds, lick-detector
   thresholds, bout parameters, angle smoothing kernel, sign-flip
   constant — all surfaced in YAML.

---

## Execute on a renamed feature branch

**Old branch (V1):** `phase/7a.3-kinematic-features-tongue-jaw`
**New branch (V2):** `phase/7a.3-tongue-pertrial-features`
PR base: `main`
Tag on merge: `v7a.3-tongue-pertrial-features`
Tag message: `Phase 7a.3: tongue per-trial features (lick1/lick2, per-lick velocity, licks-per-trial, licking dynamics, tongue angle)`

The V1 branch already exists locally and on origin (commit `41304c6`
contains the V1 kickoff doc, scoped wrong, caught by audit). Preflight
renames the branch and overwrites the V1 doc with the V2 doc as the
first new commit. No force-push; the rename + remote-recreate is
standard non-destructive git.

---

### Preflight

1. Read `CLAUDE.md` in full. All rules apply.
2. Environment activation:
   ```bash
   conda activate stroke_orofacial
   which python                              # must print a path under .conda/envs/stroke_orofacial/
   python -c "import stroke_orofacial"
   python -c "import scipy; print(scipy.__version__)"   # must print 1.17.1
   ```
3. `pytest --collect-only` must complete without import errors
   (CLAUDE.md gate). Capture the "N tests collected" count for the
   pre-check (post-7a.2 baseline is 517; record actual).
4. Confirm the V1 branch state and rename it. The V2 doc you are
   reading right now is what overwrites the V1 doc on this branch:
   ```bash
   git checkout phase/7a.3-kinematic-features-tongue-jaw
   git pull origin phase/7a.3-kinematic-features-tongue-jaw
   git log --oneline -3
   # expect: 41304c6 docs(prompts): Phase 7a.3 kickoff
   #         (and main's PR #83 merge below it)

   git branch -m phase/7a.3-kinematic-features-tongue-jaw phase/7a.3-tongue-pertrial-features
   git branch --show-current                 # must print: phase/7a.3-tongue-pertrial-features
   git push -u origin phase/7a.3-tongue-pertrial-features
   git push origin --delete phase/7a.3-kinematic-features-tongue-jaw
   # If the GitHub UI prompts about deleting the old branch's remote
   # ref while a PR is open against it: there is NO open PR against
   # the V1 branch (V1 was kickoff-only). The delete is safe.
   ```
   Branch rename is non-destructive (no rebase, no force-push, no
   `git branch -D`). The V1 commit `41304c6` remains in the renamed
   branch's history; the V2 commit will sit on top of it.
5. Confirm the V2 kickoff doc is in the working tree (Cowork wrote
   it before this preflight ran):
   ```bash
   git status
   # expect: docs/prompts/phase-7a.3-kickoff.md modified
   #         (V1 committed at 41304c6; working tree has V2 content)
   git diff docs/prompts/phase-7a.3-kickoff.md | head -30
   # confirm: V2 title mentions "tongue per-trial features",
   #         V1 title mentioned "kinematic features (tongue + jaw)".
   ```
   If the file is NOT modified — STOP. Either the Cowork V2 write
   did not land, or the branch checkout mismatch.
6. MICROSCOPE UNC reachability (needed for Task 1 vendoring +
   Task 5 parity run):
   ```powershell
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics"
   Test-Path "\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics\kinematics_figures\centered_spout_midpoint\angle_phase_exploratory"
   # both must print True
   ```
   The second path is the saved-figures directory used for Cell 50
   visual parity. If False — STOP and ask Priya before Task 1.
   (Tasks 2–4 are pure-Python; they do not require MICROSCOPE.)
7. Confirm 7a.2 outputs are reachable for downstream wiring:
   ```bash
   ls src/stroke_orofacial/dlc_kinematics/
   # expect: __init__.py features.py filters.py interpolation.py reward_aligned.py
   # interpolation.py MUST be present (7a.2 landed it).
   # tongue_pertrial.py MUST be absent — if present, STOP (concurrent
   # work or stale branch). features.py is a 7a.2-era stub used for
   # an unrelated module slot; do NOT edit it.
   ```
8. Commit the V2 kickoff doc as commit 1 of the renamed branch
   (matches the 7a.2 in-branch kickoff-provenance pattern; this is a
   regular commit replacing the V1 content, NOT an amend, NOT a
   force-push):
   ```bash
   git status                                # docs/prompts/phase-7a.3-kickoff.md modified
   git add docs/prompts/phase-7a.3-kickoff.md
   git commit -m "docs(prompts): Phase 7a.3 kickoff V2 — tongue per-trial features post-audit"
   git push
   ```

---

### Task 1 — Legacy-cell vendoring + per-cell audit

**Goal.** Vendor Cells 33, 36, 39, 42, 50 from the canonical tongue
notebook into `docs/legacy_snippets/tongue_pertrial_features.py` with
full provenance header, and audit them for the user-tunable knobs +
eye-midpoint resolution path + bout parameters + angle pass criteria
that Task 2 will surface in YAML.

#### 1a. Identify the canonical cells

Open the tongue notebook in read-only mode (no edits — it lives
inside `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/`
per CLAUDE.md rule 2):

`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
Size 403,798,697 B

Walk the cells and locate by index. Expected cell indices (Plan §2
above is the audit spec; verify the actual indices match):

- **Cell 33** — lick1/lick2 first-peak slope detector. Look for the
  70–2000 ms post-reward window, the slope-based rise/fall logic,
  and the CSV writer.
- **Cell 36** — per-lick peak velocity detector. Look for the 70–
  3000 ms post-reward window, the `(n_trials, 5)` shape, and
  detection knobs `SLOPE_THR_PX_PER_S`, `RISE_MIN_MS`, `FALL_MIN_MS`,
  `MIN_PEAK_Y_ABS`, `PEAK_PAD_MS`, `STRICT_NO_FALLBACK = True`.
- **Cell 39** — `n_licks` per-trial counter.
- **Cell 42** — within-bout ILI + lick rate + bout count.
- **Cell 50** — tongue angle. Look for `atan2(cross, dot)`, gaussian
  σ smoothing, `ANGLE_SIGN_FLIP = -1.0`, the eye_midpoint resolution
  (per-frame DLC eye landmark → median aggregation), the per-trial
  pass criteria.

If the cell indices do NOT match the expected positions (notebook
has been edited since the SHA256 was captured) — STOP and report
the actual layout to Priya before vendoring.

For each cell, classify per Plan-shape §2 above: Production /
Exploratory / Deprecated / Ambiguous. The plan's classification
(Cells 33/36/39/42/50 = Production) is the expected outcome; if the
actual code in the cells contradicts that classification (e.g. Cell
50 has a `if animal == "PSXX"` branch), STOP and report.

#### 1b. Vendor the cells

Create one new file:

```
docs/legacy_snippets/tongue_pertrial_features.py
```

Header in the 7a.0 / 7a.2 vendoring style:

```python
"""Vendored from
/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Cells 33, 36, 39, 42, 50.

Captured for Phase 7a.3 — 2026-04-2X.

3-tier-rule disambiguation: the parent notebook is the same
canonical 20260203 tongue notebook 7a.2 vendored Cell 23 from. Cells
33/36/39/42/50 are downstream of Cell 23 in the same notebook. No
sibling notebooks contain alternative implementations of these
per-trial features.

Source SHA256: ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643
Source size: 403,798,697 B
Cells included:
  - Cell 33: lick1/lick2 first-peak slope detector (CSV writer)
  - Cell 36: per-lick peak velocity, first 5 licks per trial
            (NPZ + CSV writer)
  - Cell 39: licks-per-trial counter (n_licks per trial)
  - Cell 42: within-bout ILI + lick rate + bout count
  - Cell 50: per-frame tongue angle in spout-centered frame
            referenced to session-wide median eye_midpoint;
            per-trial angle scalars + pass criteria.
            (Author-labelled "exploratory"; ported as production
            per Priya's 2026-04-25 directive — Cell 50 is ready.)

Cells excluded (and why):
  - All plot-velocity-traces / plot-amplitude-distribution / plot-
    angle-phase-exploratory cells: Exploratory, inspection-only.
    Saved figures from these cells live on MICROSCOPE; Cell 50
    visual parity is comparison against those saved figures.
  - Any cell containing _v0/_mod/_old-suffixed helpers: Deprecated.
  - Cell 41 (jaw copy-paste against files the jaw notebook never
    produces — confirmed by audit): N/A; this file is tongue-only.

DO NOT edit, reformat, or lint this file. # ruff: noqa, # fmt: off
preserve byte-identity with capture time.
"""
# ruff: noqa
# fmt: off
```

Compute / verify the SHA256 with:
```bash
sha256sum "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb"
```

Inside the file, paste the production cells **verbatim** (preserving
indentation, comments, blank lines, magic commands replaced with
`# %%` markers if any), separated by `# %% Cell <N>` markers between
cells.

If any cell hits an Ambiguous classification — STOP and report
before vendoring it.

#### 1c. Per-cell audit

For each vendored cell, extract:

**Cell 33 audit:**
- Confirmed detection-window bounds (expected: 70–2000 ms post-
  reward).
- Lick-detector thresholds: `SLOPE_THR_PX_PER_S`, `RISE_MIN_MS`,
  `FALL_MIN_MS`, `MIN_PEAK_Y_ABS`, `PEAK_PAD_MS`, `STRICT_NO_FALLBACK`
  literal values.
- CSV column names + dtypes.
- Per-animal variation: any `if animal == "PSXX": ...` branches?

**Cell 36 audit:**
- Confirmed detection-window bounds (expected: 70–3000 ms post-
  reward).
- Confirmed `n_licks_per_trial = 5` (the `(n_trials, 5)` shape).
- NPZ array names + dtypes (note exact names: `vy_peaks_bylick`,
  possibly `vxy_peaks_bylick`).
- CSV column names + dtypes.
- Whether the lick-boundary detector reuses Cell 33 detection or
  has its own knobs (audit observation, not assumption).

**Cell 39 audit:**
- Output product type: scalar per trial. CSV vs NPZ.
- Window bounds (does it use Cell 33's window, Cell 36's window, or
  its own?).
- Whether `n_licks` counts all post-reward licks or only those
  inside a bound window.

**Cell 42 audit:**
- Bout parameters: ILI threshold for bout-break (commonly named
  `MAX_ILI_WITHIN_BOUT_MS` or similar), min-licks-per-bout, bout-
  start-time bounds. Surface every literal.
- Output products: `ili_within_bout_ms`, `lick_rate_hz`,
  `bout_count` per trial. Confirm exact array names + shapes from
  the legacy NPZ/CSV.

**Cell 50 audit (most complex; spend time here):**
- **Eye_midpoint resolution path.** The auditor mentioned a
  "separate parquet cache." Audit the actual code: does it (a) load
  the per-frame DLC eye landmark from a per-session parquet,
  aggregate to median; (b) read from a per-animal manifest field;
  (c) something else? Surface the exact resolution method and the
  parquet path / column name(s) so Task 2 can wire it into the
  `tongue_pertrial.eye_landmark_source:` config.
- **Spout-centered frame translation.** Confirm the cell computes
  `eye_in_spout_frame = (median(eye_x_perframe) - spout_x_raw,
  median(eye_y_perframe) - spout_y_raw)` BEFORE doing the angle
  math, since the tongue trace it consumes is already in spout-
  centered coordinates (per 7a.2's `tongue.center_mode:
  centered_spout_midpoint`).
- **Angle math.** Confirm the formula:
  `angle_raw = degrees(atan2(cross(B, A_t), dot(B, A_t)))` where
  `A_t = tongue_centered(t) - eye_in_spout_frame` and `B = (0, 0) -
  eye_in_spout_frame = -eye_in_spout_frame`.
- **Smoothing kernel.** Confirm gaussian σ in milliseconds (expected
  8.0 ms). Confirm the smoothing implementation
  (scipy.ndimage.gaussian_filter1d on the angle trace, or on the x/y
  traces before angle computation? The audit must surface this — the
  port replicates whichever path legacy uses).
- **Sign flip.** Confirm `ANGLE_SIGN_FLIP = -1.0` is applied after
  smoothing (or before; report whichever the legacy does).
- **Per-trial angle scalars.** Three families:
  - `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak`: scalar per trial,
    interpolated/sampled at the lick1/lick2 time stamps emitted by
    Cell 33.
  - `angle_at_peak_velocity_bylick: (n_trials, 5)`: angle sampled at
    the per-lick peak-velocity timestamps emitted by Cell 36.
  - `angle_max_signed_per_lick: (n_trials, 5)`: signed max angle
    within each lick's window.
  Confirm the exact temporal-sampling logic in legacy (linear
  interpolation? nearest-neighbor? frame-aligned cap?).
- **Pass criteria.** Cell 50 emits `tongue_angle_pass: bool[n_trials]`
  used by the legacy plotting cells to filter trials. Surface the
  full criteria definition (is it `n_licks >= K` AND `lick1_y_peak
  >= P` AND `tongue_present_fraction >= F`? Or different?). The
  audit transcribes the exact predicate — do not summarize.

#### 1d. Audit report

Produce a written summary captured in the Task 1 stop-and-report:

- Per-cell classification table (one row per candidate cell with the
  classification + reason + line range in the notebook).
- SHA256 of the parent notebook (verify-match against the kickoff).
- Per-cell user-tunable knob inventory (all literals that should
  surface in YAML — windows, detector thresholds, bout parameters,
  angle smoothing σ, sign flip, pass criteria predicate
  components).
- Per-animal variation findings: cohort-uniform OR per-animal.
- Cell 50 eye_midpoint resolution path: exact parquet path / column
  name / aggregation (median across the session).
- Cell 50 angle-math formula confirmation, smoothing kernel
  application order, sign-flip application order.
- Cell 42 bout parameters with literal values.
- Cell 50 pass-criteria predicate transcribed verbatim.

#### 1e. Commit

```bash
git add docs/legacy_snippets/tongue_pertrial_features.py
git diff --cached --stat
git commit -m "docs(legacy_snippets): vendor tongue per-trial cells (33,36,39,42,50)"
git push
```

**STOP and report to Priya:**
- the per-cell classification table,
- vendored file path + line count + SHA256 provenance,
- per-cell knob inventory (Task 2 YAML candidates),
- audit verdict (cohort-uniform vs per-animal variation), with
  proposed `animals.yaml` schema additions if variation present,
- Cell 50 eye_midpoint resolution path (Task 2 will wire it into
  `eye_landmark_source:`),
- Cell 50 angle-math formula, smoothing application, sign-flip
  application, pass-criteria predicate,
- Cell 42 bout parameters with literal values,
- any Ambiguous cells encountered (STOP — wait for Priya's
  decision before Task 2).

---

### Task 2 — Config + PathResolver helpers

**Only run Task 2 after Priya acknowledges the Task 1 report.**

**Goal.** Land the constants and resolver helpers that
`tongue_pertrial.py` (Task 3) reads at module level.

#### 2a. Add `dlc_kinematics.tongue_pertrial:` block to `configs/defaults.yaml`

Extend the existing `dlc_kinematics:` block (added in 7a.2) with a
new nested `tongue_pertrial:` section. Default skeleton (fill the
audit-resolved values from Task 1):

```yaml
# --- DLC kinematics — tongue per-trial features (Phase 7a.3) -------------
# Per-trial scalars (lick1/lick2 metrics, per-lick peak velocity,
# n_licks, within-bout ILI / lick rate / bout count) and per-frame
# tongue angle from the canonical tongue notebook Cells 33/36/39/42/50.
# Reads tongue interpolated traces from
# {outputs}/dlc_analysis/interpolated_traces/tongue/{animal}/{date}.parquet
# (already in spout-centered coordinates per 7a.2's
# dlc_kinematics.tongue.center_mode = centered_spout_midpoint).
# Emits per-frame angle parquet to dlc_kinematics/features/tongue/...
# and per-trial JSON scalars to dlc_kinematics/endpoints/...
#
# Detection windows are preserved verbatim from legacy (see Q4
# decision in DECISIONS 2026-04-2X). Eye_midpoint reference is the
# session-wide median of per-frame DLC eye landmark positions,
# translated into the spout-centered frame.
dlc_kinematics:
  # ... existing 7a.2 block (interpolation_version, interpolation_method,
  # interpolation_fallback, tongue:, jaw:) — leave intact ...

  tongue_pertrial:
    # ---- Lick detector (Cells 33 + 36) ----
    lick_detector:
      slope_thr_px_per_s: <fill from Task 1 audit>
      rise_min_ms: <fill>
      fall_min_ms: <fill>
      min_peak_y_abs: <fill>
      peak_pad_ms: <fill>
      strict_no_fallback: true

    # ---- Detection windows (preserved verbatim per Q4) ----
    windows:
      lick12: {start_ms: 70, end_ms: 2000}        # Cell 33
      peak_velocity: {start_ms: 70, end_ms: 3000} # Cell 36
      n_licks_per_trial_max: 5                     # Cell 36

    # ---- Bout detector (Cell 42) ----
    bouts:
      max_ili_within_bout_ms: <fill from Task 1 audit>
      min_licks_per_bout: <fill>
      # Additional bout knobs surfaced by Task 1 audit go here.

    # ---- Tongue angle (Cell 50) ----
    angle:
      eye_midpoint_aggregator: median
      eye_landmark_source: <fill from Task 1 audit — parquet path
                            template + column name(s)>
      smoothing_gaussian_sigma_ms: 8.0
      sign_flip: -1.0
      # Pass-criteria predicate (transcribed from Cell 50 audit):
      pass_criteria:
        # Example shape — fill from Task 1 audit. May include keys like
        #   min_n_licks: <int>
        #   min_lick1_y_peak: <float>
        #   min_tongue_present_fraction: <float>
        ...
```

Place the new sub-block under the existing `dlc_kinematics:` block,
after the existing `tongue:` and `jaw:` sub-blocks. Load-time parsing
uses the existing `load_defaults()` pattern.

#### 2b. Conditional `configs/animals.yaml` extension

Only if Task 1 audit verdict is "per-animal variation present", extend
`configs/animals.yaml` per-animal with the proposed schema. Mirror the
existing `kinematics_baselines:` placement under each animal's block.
If audit verdict is cohort-uniform, skip 2b.

#### 2c. Add `PathResolver.tongue_pertrial_angle_parquet()` helper

In `src/stroke_orofacial/paths.py`, add (near the existing 7a.2
`interpolated_trace()` method):

```python
def tongue_pertrial_angle_parquet(
    self,
    animal: str,
    date: datetime.date,
) -> Path:
    """Return the output path for a Phase 7a.3 per-frame tongue-angle parquet.

    E.g. ``<outputs>/dlc_kinematics/features/tongue/PS46/20250307.parquet``

    This parquet is SEPARATE from the 7a.2 interpolated_traces parquet
    (which is locked at 9 metadata + 7 data columns). 7a.3 emits its
    own per-frame product (angle only) at a different output tree.

    Parent directory is created eagerly. Mirrors ``pipeline_outputs``'s
    ``output_root`` test-override behavior.
    """
    date_str = date.strftime("%Y%m%d")
    out = (
        self.pipeline_outputs(subdir="dlc_kinematics")
        / "features"
        / "tongue"
        / animal
        / f"{date_str}.parquet"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
```

#### 2d. Add `PathResolver.tongue_pertrial_endpoints_json()` helper

```python
def tongue_pertrial_endpoints_json(
    self,
    animal: str,
    date: datetime.date,
) -> Path:
    """Return the output path for a Phase 7a.3 per-trial tongue endpoints JSON.

    E.g. ``<outputs>/dlc_kinematics/endpoints/PS46/20250307.json``

    One JSON file per (animal, date). Tongue per-trial scalars only at
    7a.3 — the structure leaves room for future jaw scalars (Phase
    7a.3-jaw) under a sibling top-level key without schema-breaking
    changes.

    Parent directory is created eagerly.
    """
    date_str = date.strftime("%Y%m%d")
    out = (
        self.pipeline_outputs(subdir="dlc_kinematics")
        / "endpoints"
        / animal
        / f"{date_str}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
```

#### 2e. Tests

Add to `tests/test_paths.py` (extend existing file):

- `test_tongue_pertrial_angle_parquet_path` — `PathResolver(output_root=
  tmp_path).tongue_pertrial_angle_parquet("PS46", date(2025, 3, 7))`
  returns `tmp_path / "dlc_kinematics/features/tongue/PS46/
  20250307.parquet"`; parent directory exists.
- `test_tongue_pertrial_endpoints_json_path` — `PathResolver(output_root=
  tmp_path).tongue_pertrial_endpoints_json("PS46", date(2025, 3, 7))`
  returns `tmp_path / "dlc_kinematics/endpoints/PS46/20250307.json"`;
  parent directory exists.
- `test_tongue_pertrial_paths_disjoint_from_7a2_parquet` — the
  feature parquet path and the 7a.2 interpolated_trace path share no
  parent below `dlc_kinematics/` (proves the directory split — 7a.2
  writes to `dlc_analysis/interpolated_traces/...`, 7a.3 writes to
  `dlc_kinematics/features/...`).
- `test_tongue_pertrial_features_and_endpoints_disjoint` — features
  and endpoints paths share no parent below `dlc_kinematics/`.

#### 2f. Run tests + ruff

```bash
pytest tests/test_paths.py -v
pytest
ruff check src/stroke_orofacial/paths.py tests/test_paths.py configs/defaults.yaml
```

#### 2g. Commit

```bash
git add configs/defaults.yaml src/stroke_orofacial/paths.py tests/test_paths.py
# Plus configs/animals.yaml ONLY if Task 1 audit demanded it.
git diff --cached --stat
git commit -m "feat(config,paths): dlc_kinematics.tongue_pertrial defaults + 7a.3 path helpers"
git push
```

**STOP and report to Priya:**
- diff of `configs/defaults.yaml` showing the new
  `tongue_pertrial:` sub-block,
- diff of `configs/animals.yaml` if extended, or note "cohort-uniform,
  no animals.yaml change",
- new-tests count + full-suite pass count,
- any surprise in the YAML merge.

---

### Task 3 — `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` implementation

**Only run Task 3 after Priya acknowledges the Task 2 report.**

**Goal.** Port Cells 33/36/39/42/50 from the vendored snippet into
one consolidated module emitting one parquet (per-frame angle) + one
JSON (per-trial scalars) per session.

#### 3a. Read the vendored cells end-to-end

```bash
wc -l docs/legacy_snippets/tongue_pertrial_features.py
```

Build a mental map of:
- Cell 33: lick1/lick2 first-peak slope detector + CSV writer.
- Cell 36: per-lick peak velocity over first 5 licks per trial +
  NPZ + CSV writer. Note exact array names (`vy_peaks_bylick`,
  possibly `vxy_peaks_bylick`).
- Cell 39: `n_licks` per trial.
- Cell 42: bout-detector → ILI / lick rate / bout count.
- Cell 50: angle math + smoothing + sign flip + per-trial scalars
  + pass criteria.

Do not copy-paste. Transcribe each algorithm; verify behavior with
unit tests in Task 4; verify parity in Task 5.

#### 3b. Module structure

Create `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`:

```python
"""Phase 7a.3 — tongue per-trial features + per-frame tongue angle.

Ports Cells 33/36/39/42/50 from
``docs/legacy_snippets/tongue_pertrial_features.py`` (canonical tongue
notebook 20260203, SHA256 ED12C54CD...) into one consolidated module.

Public API
----------
``build_tongue_pertrial(manifest, resolver, params, *, overwrite)``
    Session-level driver. Reads 7a.2 tongue interpolated_traces parquet,
    resolves session-wide median eye_midpoint, computes per-frame
    tongue angle (Cell 50), detects lick1/lick2 (Cell 33), per-lick
    peak velocity (Cell 36), n_licks (Cell 39), within-bout ILI
    (Cell 42), per-trial angle scalars + pass mask (Cell 50). Writes
    per-frame angle parquet + per-trial JSON atomically.

``build_tongue_pertrial_by_animal_date(animal, date, resolver, **kwargs)``
    Convenience wrapper.

``TonguePertrialResult``
    Dataclass carrying per-frame angle array + per-trial scalar dicts
    + metadata.

Output schemas (locked by 7a.3 DECISIONS entry)
-----------------------------------------------
Per-frame angle parquet (one row per camera frame; tongue only):
- frame_idx (int64)
- angle_deg_smoothed (float64)
File-level metadata (analogous to 7a.2's 9-key pattern):
- animal, date, fps, n_frames
- center_mode = "centered_spout_midpoint"
- eye_in_spout_frame_x, eye_in_spout_frame_y
- smoothing_gaussian_sigma_ms, angle_sign_flip
- feature_extraction_version = "7a.3"
- interpolation_version = "v5p3"

Per-trial endpoints JSON (one file per session; tongue at 7a.3, room
for jaw at future Phase 7a.3-jaw):
{
  "schema_version": "7a.3",
  "animal": "PS46",
  "date": "2025-03-07",
  "n_trials": <int>,
  "trial_indices": [...],         # top-level co-indexing array
  "tongue": {
    "lick1_lick2_metrics": {
      "lick1_y_peak":      [...],
      "lick1_t_peak_ms":   [...],
      "lick1_x_at_ypeak":  [...],
      "lick2_y_peak":      [...],
      "lick2_t_peak_ms":   [...],
      "lick2_x_at_ypeak":  [...]
    },
    "peak_velocity_per_lick": {
      "vy_peaks_bylick":   [[...], ..., [...]]   # (n_trials, 5)
      # plus vxy_peaks_bylick if Task 1 audit confirms legacy emits it
    },
    "licks_per_trial": {
      "n_licks":           [...]
    },
    "licking_dynamics": {
      "ili_within_bout_ms": [...],
      "lick_rate_hz":       [...],
      "bout_count":         [...]
    },
    "tongue_angle": {
      "lick1_angle_at_ypeak":         [...],
      "lick2_angle_at_ypeak":         [...],
      "angle_at_peak_velocity_bylick": [[...], ..., [...]],  # (n_trials, 5)
      "angle_max_signed_per_lick":     [[...], ..., [...]],  # (n_trials, 5)
      "tongue_angle_pass":             [bool, ..., bool]
    }
  },
  "metadata": {
    "fps": <float>,
    "feature_extraction_version": "7a.3",
    "interpolation_version": "v5p3",
    "windows": {
      "lick12":         {"start_ms": 70, "end_ms": 2000},
      "peak_velocity":  {"start_ms": 70, "end_ms": 3000}
    },
    "lick_detector":  {...},
    "bouts":          {...},
    "tongue_angle":   {
      "eye_in_spout_frame_x": <float>,
      "eye_in_spout_frame_y": <float>,
      "smoothing_gaussian_sigma_ms": 8.0,
      "sign_flip": -1.0,
      "pass_criteria": {...}
    }
  }
}
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.ndimage import gaussian_filter1d

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

FEATURE_EXTRACTION_VERSION = "7a.3"


@dataclass
class TonguePertrialResult:
    # Per-frame
    angle_deg_smoothed: np.ndarray
    # Per-trial — Cell 33
    lick1_y_peak: np.ndarray
    lick1_t_peak_ms: np.ndarray
    lick1_x_at_ypeak: np.ndarray
    lick2_y_peak: np.ndarray
    lick2_t_peak_ms: np.ndarray
    lick2_x_at_ypeak: np.ndarray
    # Per-trial — Cell 36
    vy_peaks_bylick: np.ndarray              # (n_trials, 5)
    vxy_peaks_bylick: np.ndarray | None      # (n_trials, 5) or None
    # Per-trial — Cell 39
    n_licks: np.ndarray
    # Per-trial — Cell 42
    ili_within_bout_ms: np.ndarray
    lick_rate_hz: np.ndarray
    bout_count: np.ndarray
    # Per-trial — Cell 50
    lick1_angle_at_ypeak: np.ndarray
    lick2_angle_at_ypeak: np.ndarray
    angle_at_peak_velocity_bylick: np.ndarray  # (n_trials, 5)
    angle_max_signed_per_lick: np.ndarray      # (n_trials, 5)
    tongue_angle_pass: np.ndarray              # bool
    # Trial bookkeeping
    trial_indices: np.ndarray
    n_trials: int
    fps: float
    animal: str
    date: dt.date
    # Angle-frame provenance
    eye_in_spout_frame_x: float
    eye_in_spout_frame_y: float


def _resolve_eye_midpoint_session_median(
    resolver: PathResolver, manifest: SessionManifest, params: dict,
) -> tuple[float, float]:
    """Load per-frame DLC eye landmark and return session-wide median (raw frame).

    Path + column resolution per Task 1 audit (config key
    ``dlc_kinematics.tongue_pertrial.angle.eye_landmark_source``).
    Returns (eye_x_median_raw, eye_y_median_raw) in pixel coordinates
    of the original camera frame (NOT yet translated into the
    spout-centered frame; that translation happens in
    ``_compute_tongue_angle``).
    """
    ...


def _compute_tongue_angle(
    x_centered: np.ndarray, y_centered: np.ndarray,
    eye_in_spout_frame: tuple[float, float],
    *,
    sigma_ms: float, fps: float, sign_flip: float,
) -> np.ndarray:
    """Per-frame signed tongue angle (degrees) in the spout-centered frame.

    Convention (Q2 — locked 2026-04-25 by Priya):
        eye_in_spout_frame = (median(eye_x_perframe) - spout_x_raw,
                              median(eye_y_perframe) - spout_y_raw)
        # tongue trace already in spout-centered coords → spout = (0, 0)
        A_t = (x_centered[t], y_centered[t]) - eye_in_spout_frame
        B   = (0, 0) - eye_in_spout_frame   = -eye_in_spout_frame
        angle_raw_deg[t] = degrees(atan2(cross(B, A_t), dot(B, A_t)))
        angle_smoothed = gaussian_filter1d(angle_raw, sigma_frames) * sign_flip

    Where sigma_frames = sigma_ms * fps / 1000. Smoothing-then-sign-flip
    or sign-flip-then-smoothing per Task 1 audit's confirmation of
    legacy order; transcribe whichever legacy uses.

    NaN frames in (x_centered, y_centered) propagate to NaN angles.
    """
    ...


def _detect_lick1_lick2(
    y_centered: np.ndarray, x_centered: np.ndarray,
    reward_centers_cam: np.ndarray, fps: float,
    *,
    window_start_ms: float, window_end_ms: float,
    slope_thr_px_per_s: float,
    rise_min_ms: float, fall_min_ms: float,
    min_peak_y_abs: float, peak_pad_ms: float,
    strict_no_fallback: bool,
) -> dict[str, np.ndarray]:
    """Cell 33 — slope-based rise/fall first-two-licks detector.

    Returns dict with arrays of shape (n_trials,):
        lick1_y_peak, lick1_t_peak_ms, lick1_x_at_ypeak,
        lick2_y_peak, lick2_t_peak_ms, lick2_x_at_ypeak.
    NaN per-trial when no lick detected (or strict_no_fallback raises
    per legacy semantics — Task 1 audit confirms which).
    """
    ...


def _detect_peak_velocity_per_lick(
    y_centered: np.ndarray, x_centered: np.ndarray,
    reward_centers_cam: np.ndarray, fps: float,
    *,
    window_start_ms: float, window_end_ms: float,
    n_licks_per_trial_max: int,
    # Lick-detector knobs (Cell 36 may share Cell 33's; Task 1 confirms)
    slope_thr_px_per_s: float, rise_min_ms: float, fall_min_ms: float,
    min_peak_y_abs: float, peak_pad_ms: float, strict_no_fallback: bool,
) -> dict[str, np.ndarray]:
    """Cell 36 — per-lick peak velocity, first n_licks_per_trial_max licks.

    Returns dict:
        vy_peaks_bylick:  (n_trials, n_licks_per_trial_max)
        vxy_peaks_bylick: (n_trials, n_licks_per_trial_max)  # if legacy emits
        lick_t_peaks_ms:  (n_trials, n_licks_per_trial_max)  # for Cell 50 sampling
    NaN-padded where fewer than n_licks_per_trial_max licks detected.
    """
    ...


def _count_licks_per_trial(...) -> np.ndarray:
    """Cell 39 — n_licks per trial."""
    ...


def _detect_bouts_and_ili(
    ..., *,
    max_ili_within_bout_ms: float, min_licks_per_bout: int,
) -> dict[str, np.ndarray]:
    """Cell 42 — within-bout ILI / lick rate / bout count per trial."""
    ...


def _sample_angle_at_lick_times(
    angle_smoothed: np.ndarray,
    lick_t_ms: np.ndarray,
    fps: float,
) -> np.ndarray:
    """Sample the per-frame angle trace at the per-lick timestamps.

    Shape-preserving: shape(out) == shape(lick_t_ms). NaN propagation
    on NaN timestamps. Uses the same temporal-sampling convention as
    Cell 50 (linear / nearest / frame-cap; Task 1 audit confirms).
    """
    ...


def _evaluate_tongue_angle_pass(
    *, n_licks: np.ndarray, lick1_y_peak: np.ndarray,
    angle_smoothed: np.ndarray, fps: float,
    pass_criteria: dict,
) -> np.ndarray:
    """Cell 50 per-trial pass mask. Predicate transcribed from Task 1 audit."""
    ...


def _build_tongue_pertrial_core(
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict,
    animal_info: AnimalInfo | None = None,
) -> TonguePertrialResult:
    """Pure function — reads 7a.2 tongue parquet, computes everything,
    returns result. No I/O writes. Sequence:

      1. Load tongue interpolated_trace parquet (frame-indexed,
         already spout-centered).
      2. Resolve session-wide median eye_midpoint (raw frame).
      3. Translate eye_midpoint into spout-centered frame:
         eye_in_spout_frame = eye_raw - spout_raw.
      4. Compute per-frame tongue angle (smoothed, sign-flipped).
      5. Detect lick1/lick2 (Cell 33) → 6 per-trial scalars.
      6. Detect per-lick peak velocity (Cell 36) → (n_trials, 5).
      7. Count licks per trial (Cell 39).
      8. Detect bouts and compute within-bout ILI / lick rate / bout
         count (Cell 42).
      9. Sample per-trial angle scalars (lick1/lick2 peak, peak-
         velocity, max-signed-per-lick) — Cell 50.
     10. Evaluate pass mask — Cell 50.
    """
    ...


def _write_json_atomic(path: Path, payload: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.stem + ".", suffix=".json.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=False)
        os.replace(tmp, path)  # atomic on POSIX + Windows
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def build_tongue_pertrial(
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path] | None:
    """Build tongue per-trial features for one session.

    Writes:
      - ``{outputs}/dlc_kinematics/features/tongue/{animal}/{date}.parquet``
        (per-frame smoothed signed angle).
      - ``{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json``
        (per-trial scalars).

    Returns dict {"angle_parquet", "endpoints_json"} -> Path on
    success, or None if overwrite="skip" and BOTH files exist
    (partial existence triggers full rebuild — partial output is
    treated as torn write).

    Parquet via pyarrow snappy. JSON atomic (temp + os.replace).
    """
    ...


def build_tongue_pertrial_by_animal_date(
    animal: str, date: dt.date, resolver: PathResolver, **kwargs,
) -> dict[str, Path] | None:
    """Convenience wrapper — builds manifest internally."""
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info, analysis_type="kinematics",
    )
    return build_tongue_pertrial(manifest, resolver, **kwargs)
```

Export the public symbols from
`src/stroke_orofacial/dlc_kinematics/__init__.py`:

```python
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    TonguePertrialResult,
    build_tongue_pertrial,
    build_tongue_pertrial_by_animal_date,
)

# Append to existing __all__; do NOT replace the 7a.2 entries.
```

#### 3c. Per-frame angle parquet schema

Columns (one row per camera frame):
- `frame_idx` (int64)
- `angle_deg_smoothed` (float64)

File-level metadata (analogous to 7a.2's 9-key pattern):
`animal, date, fps, n_frames, center_mode, eye_in_spout_frame_x,
eye_in_spout_frame_y, smoothing_gaussian_sigma_ms, angle_sign_flip,
feature_extraction_version, interpolation_version`. The
`eye_in_spout_frame_(x,y)` keys bake the resolved reference
coordinates into the parquet for forensic reproducibility (the
angle is sensitive to which reference point was used).

Write via `pyarrow.Table.from_pandas(df).replace_schema_metadata({...})`
+ `pq.write_table(..., compression="snappy")`.

#### 3d. Per-trial endpoints JSON

Schema per the docstring above. **Top-level `trial_indices`** array
(Q6 decision) — every per-trial array under `tongue.*` is co-
indexed with this top-level array. NaN for missing values; bool for
the pass mask. JSON-encode numpy arrays via `arr.tolist()`.

Atomic write via `_write_json_atomic` (temp + `os.replace`).

#### 3e. Ruff + smoke import

```bash
ruff check src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py
python -c "from stroke_orofacial.dlc_kinematics import build_tongue_pertrial, TonguePertrialResult; print('ok')"
```

Unit tests come in Task 4. Task 3 ends at a clean module that
imports and passes ruff.

#### 3f. Commit

```bash
git add src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): tongue per-trial features module (7a.3)"
git push
```

**STOP and report to Priya:**
- line count of `tongue_pertrial.py`,
- list of private helpers + their line-count estimate,
- transcription decisions per cell that reviewers should sanity-
  check (e.g. did you smooth-then-flip or flip-then-smooth? linear
  or nearest sampling for per-lick angle scalars? `n_licks` window
  if Cell 39 disagrees with Cells 33/36),
- any unresolved algorithmic questions from the vendored cells,
- confirmation that the module imports cleanly + ruff passes.

---

### Task 4 — Unit tests

**Only run Task 4 after Priya acknowledges the Task 3 report.**

**Goal.** Pin every layer of the algorithm + module API surface so
later edits cannot silently regress.

Create `tests/test_tongue_pertrial.py`. Every test uses
`PathResolver(output_root=tmp_path)` — do NOT write to the real
`stroke_orofacial_pipeline_outputs/` tree (CLAUDE.md testing
conventions).

#### 4a. Test list (target ~16 tests)

1. `test_compute_tongue_angle_zero_on_reference_line` — when the
   tongue point lies exactly on the eye→spout reference line in
   spout-centered coords, angle is 0 degrees (after smoothing on a
   constant-zero trace).
2. `test_compute_tongue_angle_perpendicular` — when the tongue point
   is perpendicular to the reference line at eye_in_spout_frame, angle
   is ±90 degrees (sign per the cross-product convention chosen).
3. `test_compute_tongue_angle_signed_consistency` — angle sign
   flips when the eye position is reflected across the spout origin
   (sanity test for the cross/dot orientation).
4. `test_compute_tongue_angle_smoothing_kernel_applied` — pre-
   smoothing with a known σ_ms transforms an impulse trace as
   expected; σ_frames computed correctly from σ_ms × fps / 1000.
5. `test_compute_tongue_angle_sign_flip_applied` — passing
   `sign_flip=-1.0` returns angles negated relative to
   `sign_flip=+1.0` on the same input.
6. `test_compute_tongue_angle_nan_propagation` — NaN positions →
   NaN angles.
7. `test_detect_lick1_lick2_synthetic_two_peaks` — synthetic
   y_centered with two known rise/fall peaks inside the 70–2000 ms
   window emits the expected timestamps and amplitudes.
8. `test_detect_lick1_lick2_no_lick_returns_nan` — empty trial
   (no rise above slope threshold) emits NaN per trial under
   `strict_no_fallback=True` semantics (or raises — port whichever
   legacy does).
9. `test_detect_peak_velocity_first_n_licks` — synthetic trial with
   7 licks returns peak velocity for first 5 only; trial with 3
   licks returns NaN-padded `(5,)` row.
10. `test_count_licks_per_trial_matches_synthetic` — synthetic trial
    with K detected licks emits `n_licks = K`.
11. `test_detect_bouts_within_session` — synthetic lick train with
    one within-bout cluster + one isolated lick yields the expected
    `bout_count`, `ili_within_bout_ms`, `lick_rate_hz`.
12. `test_sample_angle_at_lick_times_linear` — with a known angle
    trace and known lick timestamps, the sampled angles match
    `np.interp` (or nearest-neighbor / frame-cap per audit).
13. `test_evaluate_tongue_angle_pass_predicate` — predicate from
    Task 1 audit fires correctly on hand-built per-trial inputs.
14. `test_build_tongue_pertrial_emits_two_files` — driver writes
    both the angle parquet and the endpoints JSON.
15. `test_build_tongue_pertrial_overwrite_semantics` — `skip` with
    both present returns None; `force` overwrites; `skip` with one
    present rebuilds (partial = torn write).
16. `test_endpoints_json_schema` — emitted JSON has the locked
    top-level keys (`schema_version`, `animal`, `date`, `n_trials`,
    `trial_indices`, `tongue`, `metadata`); per-trial arrays have
    length `n_trials`; per-lick `(n_trials, 5)` arrays have second
    dim = 5.

Helper fixtures:
- `_make_synthetic_tongue_parquet(tmp_path, animal, date, n_frames,
  ...)` — writes a 7a.2-shaped parquet that the features module
  consumes.
- `_make_synthetic_eye_landmark_parquet(...)` — feeds the
  `_resolve_eye_midpoint_session_median` resolver.
- `_make_minimal_manifest(animal, date, tmp_path)` — analogous to
  7a.2 fixture.

#### 4b. Run + commit

```bash
pytest tests/test_tongue_pertrial.py -v
pytest
ruff check tests/test_tongue_pertrial.py

git add tests/test_tongue_pertrial.py
git diff --cached --stat
git commit -m "test(tongue_pertrial): unit tests for lick/velocity/bout/angle (7a.3)"
git push
```

**STOP and report to Priya:**
- the test-name list with pass status,
- full-suite pass/skip/fail counts,
- any synthetic-fixture implementation surprise.

---

### Task 5 — Parity harness + cohort run

**Only run Task 5 after Priya acknowledges the Task 4 report.**

**Goal.** Run consolidated 7a.3 outputs against legacy CSV/NPZ
emissions (Cells 33/36/39/42) on the 14-session cohort + visual parity
gate against legacy figures (Cell 50). `atol=1e-6` element-wise.

#### 5a. Smoke run on PS50/2025-03-19 (Q7-confirmed target)

Strategy brief precedent: smoke on a non-parity session catches
integration glitches unit tests miss.

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_tongue_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
paths = build_tongue_pertrial_by_animal_date(
    animal="PS50", date=dt.date(2025, 3, 19),
    resolver=resolver, overwrite="force",
)
print(paths)
PY
```

Expected: prints both file paths; both exist on disk; the parquet
has 2 columns + 11 metadata keys; the JSON parses + has the
expected top-level structure.

If any error — STOP and report.

#### 5b. Build the parity harness

Create `tests/scripts/parity_phase7a3_tongue_pertrial.py` modelled on
`tests/scripts/parity_phase7a_interpolation.py`. Reuse the scope-
filter + comparator infrastructure.

**Numerical comparisons (atol=1e-6, per-trial co-indexed):**
- **Cell 33 (CSV):** load legacy CSV via `pd.read_csv` from
  `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/
  {animal}_tongue_kinematics/<lick12_subdir>/...csv` (exact path
  resolved at Task 1). Compare the 6 lick1/lick2 columns against
  the consolidated JSON's `tongue.lick1_lick2_metrics.*` arrays.
- **Cell 36 (NPZ):** load legacy NPZ via `np.load` from
  `{MICROSCOPE}/.../<peak_velocity_subdir>/...npz`. Compare
  `vy_peaks_bylick` and `vxy_peaks_bylick` (if emitted) against
  `tongue.peak_velocity_per_lick.*`.
- **Cell 39 (CSV/NPZ — Task 1 audit confirms):** compare `n_licks`.
- **Cell 42 (CSV/NPZ — Task 1 audit confirms):** compare
  `ili_within_bout_ms`, `lick_rate_hz`, `bout_count`.

**Visual comparison (Cell 50):**
- For the smoke session (PS50/2025-03-19) and at minimum one parity
  session (recommended PS46/<date with saved figures present>), render
  the consolidated angle outputs in the same plot styles as the
  legacy figures at
  `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\
  O2_analysis\PS46\PS46_tongue_kinematics\kinematics_figures\
  centered_spout_midpoint\angle_phase_exploratory`:
    - per-trial tongue-angle traces (filtered to `tongue_angle_pass`),
    - session-wide tongue-phase first-peak-aligned traces,
    - session-wide tongue-phase reward-aligned traces,
    - phase-aligned tongue angle,
    - XY location color-coded by phase.
- Render the consolidated outputs to
  `{outputs}/dlc_kinematics/figures_qc/tongue/{animal}/{date}/...png`.
- Side-by-side comparison with the saved legacy PNGs is reported
  in the Task 5 stop-and-report.
- **If the visual comparison surfaces a discrepancy:** STOP and
  report. Cell 50 numerical regression on cohort sessions can be
  added as a follow-up phase if needed; for 7a.3 the unit tests
  (Task 4) cover the angle math on synthetic geometry, and the
  visual gate covers legacy-vs-port shape parity.
- **If Priya prefers to defer the visual comparison to a follow-up
  phase:** record the deferral explicitly in the Task 5 report
  (visual comparison is non-blocking for the parity gate; numerical
  parity on Cells 33/36/39/42 IS blocking).

#### 5c. Build the cohort outputs

Run the consolidated module across the 14-session set:

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_tongue_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
SESSIONS = [
    # 9 primary (PS46 / PS54 / PS55 × 3 dates each)
    # ... fill from the 7a.2 parity scope ...
    # 3 stress
    ("PS51", dt.date(2025, 4, 30)),
    ("PS54", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 2)),
    # 2 late post-stroke
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]
for animal, date in SESSIONS:
    paths = build_tongue_pertrial_by_animal_date(
        animal=animal, date=date, resolver=resolver, overwrite="force",
    )
    print(animal, date, paths)
PY
```

Confirm all 14 sessions emitted both files.

#### 5d. Run the parity harness

```bash
python tests/scripts/parity_phase7a3_tongue_pertrial.py --sessions auto | tee /tmp/parity_7a3.log
echo "exit=$?"
```

Expected:
- exit code `0` (all numerical pass).
- `by_status = {'pass': N, 'skip_missing': M}` where N + M =
  14 (Cell 33) + 14 (Cell 36) + 14 (Cell 39) + 14 (Cell 42) =
  56 numerical comparisons (per-comparison can split across multiple
  scalars / arrays internally; report at the granularity the harness
  outputs).
- Per-comparison `max|Δ|` reports — ideally `0.000e+00` (bit-
  identical), tolerated up to `atol=1e-6`.

If ANY numerical comparison returns `status = fail`:
- capture (animal, date, cell, dim) + `max|Δ|`,
- **STOP and report** — do not widen tolerance, do not advance.

If the visual comparison flags a discrepancy:
- capture the legacy-figure path + consolidated-figure path,
- **STOP and report** — Priya decides whether to triage in this
  phase or defer to a follow-up.

#### 5e. Commit

```bash
git add tests/scripts/parity_phase7a3_tongue_pertrial.py
git diff --cached --stat
git commit -m "feat(parity): Phase 7a.3 tongue per-trial parity harness (14-session)"
git push
```

**STOP and report to Priya:**
- PS50/2025-03-19 smoke result (file paths + sizes),
- cohort emit confirmation (14 sessions × 2 files = 28 files),
- per-comparison `by_status` count (Cells 33/36/39/42),
- per-session `max|Δ|` table,
- any skip_missing patterns,
- Cell 50 visual parity report (or deferral),
- any fail → STOP AND WAIT for Priya's triage decision.

---

### Task 6 — DECISIONS + MIGRATION_LOG entries

**Only run Task 6 after Task 5 reports all-pass on numerical
comparisons + Cell 50 visual gate (or explicit deferral).**

#### 6a. `docs/DECISIONS.md` — Phase 7a.3 entry

Insert above the existing reverse-chronological entries:

```markdown
## 2026-04-2X — Phase 7a.3 tongue per-trial features (post-audit V2)

**Context.** Phase 7a.3 V1 (kickoff dated 2026-04-24) was scoped
incorrectly — V1 promised per-frame velocity + per-trial scalars
(amplitude/velocity_peak/angle_peak) over wide/tight reward-aligned
windows that the legacy notebooks do NOT compute as stored products.
Audit on 2026-04-25 caught the mismatch before any code shipped. V2
(this entry's source phase) reflects the actual legacy: Cells 33,
36, 39, 42, 50 from the canonical tongue notebook
(`20260203_..._tongue.ipynb`, SHA256 ED12C54...).

**Decisions enacted.**

1. **Branch + tag rename.** V1 branch
   `phase/7a.3-kinematic-features-tongue-jaw` →
   `phase/7a.3-tongue-pertrial-features`. V1 tag plan
   `v7a.3-kinematic-features-tongue-jaw` → `v7a.3-tongue-pertrial-features`.
2. **Tongue-only scope.** Jaw per-trial work is deferred to
   future **Phase 7a.3-jaw** with its own design discussion. Audit
   confirmed the jaw notebook contains no per-trial features (its
   Cell 41 was a copy-paste of tongue code against files the jaw
   notebook never produces).
3. **Per-frame angle parquet** at
   `{outputs}/dlc_kinematics/features/tongue/{animal}/{date}.parquet`.
   Columns: `frame_idx, angle_deg_smoothed`. File-level metadata:
   `animal, date, fps, n_frames, center_mode,
   eye_in_spout_frame_x, eye_in_spout_frame_y,
   smoothing_gaussian_sigma_ms, angle_sign_flip,
   feature_extraction_version, interpolation_version`.
   **Separate** from 7a.2's locked interpolated_traces parquet —
   7a.2's 9-key + 7-column schema stays untouched.
4. **Per-trial endpoints JSON** at
   `{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json`. Schema
   v7a.3 with top-level `trial_indices` (Q6 decision) co-indexing
   every per-trial array. Tongue scalars only at 7a.3; structure
   leaves a sibling top-level key open for future Phase 7a.3-jaw.
5. **Eye_midpoint = session-wide MEDIAN** (Q2 follow-up — locked
   2026-04-25 by Priya). The reference is
   `eye_in_spout_frame = (median(eye_x_perframe) - spout_x_raw,
   median(eye_y_perframe) - spout_y_raw)`, used as a session
   constant for every frame's angle math. This avoids per-frame
   eye-position noise. Per-frame DLC eye landmark resolution path
   per Task 1 audit (`eye_landmark_source:` config key).
6. **Tongue angle in spout-centered frame.** Per-frame angle =
   `degrees(atan2(cross(B, A_t), dot(B, A_t)))` where
   `A_t = tongue_centered(t) - eye_in_spout_frame` and
   `B = -eye_in_spout_frame`. Smoothed with gaussian σ=8 ms;
   sign-flipped by `ANGLE_SIGN_FLIP = -1.0`. Reference-point
   coordinates baked into the parquet metadata for forensic
   reproducibility.
7. **Detection windows preserved verbatim** (Q4 decision):
   Cell 33 lick1/lick2 = 70–2000 ms post-reward; Cell 36 peak
   velocity = 70–3000 ms post-reward; Cell 36 first 5 licks per
   trial.
8. **Cell 50 production despite "exploratory" label** (Q2
   decision). Author's directory naming
   (`angle_phase_exploratory`) preserved as MICROSCOPE legacy-
   figure source for visual parity comparison; the angle math is
   landed as production in `tongue_pertrial.py`.
9. **Smoke target: PS50 / 2025-03-19** (Q7 decision — confirmed
   non-parity tongue session in scope per `animals.yaml`).
10. **Parity acceptance.** All Cells 33/36/39/42 numerical
    comparisons at `atol=1e-6` on the 14-session set. Cell 50
    visual parity against legacy figures at
    `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS46/
    PS46_tongue_kinematics/kinematics_figures/
    centered_spout_midpoint/angle_phase_exploratory` on at least the
    smoke session (deferred to follow-up if Priya elects).

**Parity verification (14-session set at atol=1e-6).** <PASTE
by_status table from Task 5d run>. <Bit-identical / within
tolerance> on all in-scope dims.

**Enforced at.** `configs/defaults.yaml dlc_kinematics.tongue_pertrial:`,
`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` module,
`tests/scripts/parity_phase7a3_tongue_pertrial.py`,
`tests/test_tongue_pertrial.py`.

**Forward implication.** Phase 7a.3-jaw will mirror this structure
with jaw-specific design (audit must establish what jaw per-trial
features even exist). Future face-velocity / PSD / mismatch-
classifier phases consume the per-frame angle parquet and per-trial
endpoints JSON.
```

#### 6b. `docs/MIGRATION_LOG.md` — Phase 7a.3 entry

Append after Phase 7a.2:

```markdown
## Phase 7a.3 — tongue per-trial features (lick1/lick2, per-lick velocity, n_licks, licking dynamics, tongue angle)

**Date:** 2026-04-2X
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.3-tongue-pertrial-features`
**Branch:** `phase/7a.3-tongue-pertrial-features` (renamed from
V1 branch `phase/7a.3-kinematic-features-tongue-jaw` post-audit)

**Scope.** Tongue per-trial scalars (Cells 33, 36, 39, 42) and
per-frame tongue angle (Cell 50) ported from the canonical tongue
notebook (`20260203_..._tongue.ipynb`, SHA256 ED12C54...). First
downstream phase consuming the 7a.2 tongue interpolated_traces
parquets. Jaw per-trial work explicitly deferred to future Phase
7a.3-jaw.

**What landed.**

1. Vendored cells under
   `docs/legacy_snippets/tongue_pertrial_features.py` (Cells
   33/36/39/42/50, SHA256 provenance per 7a.0 pattern).
2. `configs/defaults.yaml dlc_kinematics.tongue_pertrial:` block
   (lick-detector knobs, detection windows, bout parameters, angle
   smoothing + sign flip, pass criteria).
3. <`configs/animals.yaml` per-animal `tongue_pertrial:` extension
   if Task 1 audit demanded it, OR "no animals.yaml change — cohort
   uniform">.
4. `PathResolver.tongue_pertrial_angle_parquet()` and
   `PathResolver.tongue_pertrial_endpoints_json()` helpers.
5. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (~<N>-
   line module): `TonguePertrialResult` dataclass + lick / peak-
   velocity / bout / angle helpers + atomic session writer.
6. <N> unit tests in `tests/test_tongue_pertrial.py`.
7. `tests/scripts/parity_phase7a3_tongue_pertrial.py` parity
   harness; 14-session cohort returns `by_status = <PASTE>`. Cell
   50 visual parity gate <PASTE: passed on PS50 + PS46 / deferred>.

**Behavior differences vs. legacy notebooks.**

- **V1 → V2 rescoping (audit-driven).** V1 promised per-frame
  velocity + amplitude/velocity_peak/angle_peak over wide/tight
  windows; legacy doesn't compute those. V2 reflects actual legacy.
- **Output split.** Per-frame angle goes to parquet (one column +
  metadata). Per-trial scalars go to JSON, with top-level
  `trial_indices` for downstream co-indexing. Legacy emits
  monolithic per-cell CSVs/NPZs — the consolidated split keeps the
  parquet tooling-friendly and the JSON human-readable.
- **Eye_midpoint = session-wide median.** Legacy code path
  resolves a per-session median across DLC eye landmark frames,
  documented explicitly here as the canonical reference (was
  partially implicit in legacy).
- **Reference frame translation explicit.** The legacy operates in
  spout-centered coordinates already; the consolidated module
  documents and surfaces `eye_in_spout_frame` in parquet metadata
  for forensic reproducibility.
- **Cell 50 promoted from "exploratory" to production.** Per
  Priya's 2026-04-25 directive — the cell is ready.
- Otherwise within `atol=1e-6` (or bit-identical, per Task 5
  results) on the numerical Cells 33/36/39/42 parity set; Cell 50
  visual parity against saved legacy figures.

**Ground-rule compliance.** CLAUDE.md rule 1 — no source data
modified. Rule 2 — no legacy-repo edits. Rule 6 — new outputs
under `dlc_kinematics/features/tongue/` and
`dlc_kinematics/endpoints/`. Rule 8 — feature branch (renamed),
tag pushed post-merge.

**Forward follow-ups.** Phase 7a.3-jaw (separate phase, distinct
design discussion). Future face-velocity / PSD / mismatch-
classifier phases consume the 7a.3 outputs.
```

#### 6c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.3): DECISIONS + MIGRATION_LOG entries"
git push
```

---

### Task 7 — PR + tag

#### 7a. Open the PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.3: tongue per-trial features (lick1/lick2, per-lick velocity, n_licks, licking dynamics, tongue angle)" \
  --body - <<'EOF'
Phase 7a.3 ports the canonical tongue notebook's per-trial scalars
(Cells 33/36/39/42) and per-frame tongue angle (Cell 50) into
`tongue_pertrial.py`. First downstream phase consuming the 7a.2
tongue interpolated_traces parquets.

V1 of this phase (kickoff dated 2026-04-24, branch
`phase/7a.3-kinematic-features-tongue-jaw`) was scoped incorrectly;
audit caught the V1 mismatch with legacy reality before any code
shipped. V2 (this PR) reflects the actual legacy. Branch renamed to
`phase/7a.3-tongue-pertrial-features` accordingly.

## What lands

1. `docs/legacy_snippets/tongue_pertrial_features.py` — Cells
   33/36/39/42/50 vendored with SHA256 provenance.
2. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` — full
   module: lick detector, per-lick peak-velocity aggregator, bout
   detector, per-frame tongue angle, per-trial angle scalars + pass
   mask, atomic session writer.
3. `configs/defaults.yaml dlc_kinematics.tongue_pertrial:` block.
4. `configs/animals.yaml` per-animal extension <if Task 1 audit
   demanded it>.
5. `PathResolver.tongue_pertrial_angle_parquet()` and
   `tongue_pertrial_endpoints_json()` helpers.
6. `tests/test_tongue_pertrial.py` — <N> unit tests.
7. `tests/scripts/parity_phase7a3_tongue_pertrial.py` — 14-session
   parity harness (Cells 33/36/39/42 numerical, Cell 50 visual).
8. DECISIONS entry codifying schemas + windows + eye_midpoint
   median + angle math.
9. MIGRATION_LOG Phase 7a.3 entry.

## Parity / tests / ruff

- Full pytest: <PASTE> passed / <PASTE> skipped / 0 failed
  (+<N> new tests in test_tongue_pertrial.py).
- Ruff clean on all touched `.py` files.
- Parity harness `--sessions auto` exit code 0;
  by_status = <PASTE>.
- Cohort emit: 14 sessions × (angle_parquet + endpoints_json) =
  28 files written.
- Max|Δ| on Cells 33/36/39/42: <PASTE> (target 0.000e+00; tolerated
  up to 1e-6 atol).
- Cell 50 visual parity: <PASTE: passed on smoke + 1 cohort session
  / deferred>.

## Tag on merge

`v7a.3-tongue-pertrial-features`

Tag message: `Phase 7a.3: tongue per-trial features (lick1/lick2,
per-lick velocity, licks-per-trial, licking dynamics, tongue angle)`

## Not in this PR

- **Phase 7a.3-jaw** — jaw per-trial work. Audit confirmed jaw
  notebook has no per-trial features; that phase needs its own
  design.
- Future face-velocity / PSD / mismatch-classifier phases.
EOF
```

#### 7b. Final verification

```bash
# Commits on the renamed branch since main:
git log --oneline origin/main..HEAD
# Expected: 8 commits — V1 kickoff (41304c6, kept in history) +
#                       V2 kickoff rewrite (preflight) +
#                       6 task commits (vendoring, config+paths,
#                       module, unit tests, parity, DECISIONS+MIGRATION_LOG).

# Touched file summary:
git diff --stat origin/main..HEAD
# Expected paths:
#   docs/prompts/phase-7a.3-kickoff.md                          (V1 commit + V2 rewrite commit)
#   docs/legacy_snippets/tongue_pertrial_features.py            (task 1)
#   configs/defaults.yaml                                        (task 2)
#   src/stroke_orofacial/paths.py                                (task 2)
#   tests/test_paths.py                                          (task 2)
#   configs/animals.yaml                                         (task 2, IF audit demanded)
#   src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py       (task 3)
#   src/stroke_orofacial/dlc_kinematics/__init__.py              (task 3)
#   tests/test_tongue_pertrial.py                                (task 4)
#   tests/scripts/parity_phase7a3_tongue_pertrial.py             (task 5)
#   docs/DECISIONS.md                                            (task 6)
#   docs/MIGRATION_LOG.md                                        (task 6)

# Ruff + pytest one more time for the PR record:
ruff check .
pytest -q

# After PR merges on main, tag and push (CLAUDE.md §"Phase-close
# tags"):
# git checkout main && git pull
# git tag -a v7a.3-tongue-pertrial-features <merge-sha> \
#   -m "Phase 7a.3: tongue per-trial features (lick1/lick2, per-lick velocity, licks-per-trial, licking dynamics, tongue angle)"
# git push origin v7a.3-tongue-pertrial-features
```

Report to Priya: PR URL, the 8 commit SHAs, ruff + pytest counts,
parity `by_status` + max|Δ| table, cohort emit confirmation, Cell 50
visual gate result. STOP. **Do not merge.** Priya reviews, merges
from the GitHub UI, then tags on the merge commit herself.

---

## Constraints (across all 7 tasks)

- **Phase 7a.3 scope is tongue per-trial scalars + per-frame tongue
  angle ONLY.** No jaw per-trial features. No PSD. No whisker /
  face-velocity. No mismatch classifier. No notebook work
  (notebooks orchestrate but do not implement, per CLAUDE.md
  conventions). No changes to `interpolation.py` or 7a.2's
  interpolated_traces parquet schema — the 7 columns + 9 metadata
  keys are LOCKED.
- **Eight commits, not one.** V2 kickoff rewrite + 6 task commits +
  PR. Each task = one commit. Review granularity matters.
- **Stop-and-report between tasks 1 / 2 / 3 / 4 / 5.** Tasks 6 and
  7 chain through only after Task 5 reports all-pass on numerical
  parity (Cell 50 visual gate may be reported as "passed" or
  "deferred" — both unblock).
- **No MICROSCOPE writes.** All MICROSCOPE access is `np.load` /
  `pd.read_csv` / `pd.read_parquet` / `Path.glob` / read-only
  notebook reads only. Consolidated outputs go under
  `stroke_orofacial_pipeline_outputs/dlc_kinematics/features/tongue/`
  and `/endpoints/`.
- **No force-push.** All pushes are additive to
  `phase/7a.3-tongue-pertrial-features`. The V1 commit (`41304c6`,
  V1 kickoff doc with broken scope) stays in branch history; the V2
  rewrite is a regular new commit on top.
- **No tag until after merge.** Tagging is Priya's call on the
  merge commit, per CLAUDE.md §"Git discipline".
- **If the parity harness reports any `status = fail` in Task 5d:**
  STOP. Do not widen tolerance. Do not write DECISIONS or
  MIGRATION_LOG entries claiming success.
- **If Cell 50 visual comparison flags a discrepancy:** STOP and
  report. Priya decides whether to triage in this phase or defer
  to a follow-up.
- **If Task 1 audit hits an Ambiguous cell:** STOP. Do not silently
  vendor or silently exclude.
- **If the per-cell audit finds variation that demands
  `animals.yaml` extension:** include the proposed schema in the
  Task 1 report; let Priya approve before Task 2 writes it.
- **If `tongue_pertrial.py` already exists when the branch is cut:**
  STOP. Either someone else is editing concurrently or the branch
  is stale.
- **Legacy snippets under `docs/legacy_snippets/` stay READ-ONLY.**
  Their `# ruff: noqa` + `# fmt: off` headers preserve byte-identity
  with capture time; do NOT edit, reformat, or lint them.
- **The eye_midpoint = session-wide MEDIAN convention is locked**
  (Q2 follow-up, 2026-04-25). Changes to the aggregator or the
  reference-frame translation require a DECISIONS entry.
- **Cell 50 production status is locked** (Q2, 2026-04-25). The
  author's `_exploratory` directory naming on MICROSCOPE is
  preserved as legacy-figure source for visual parity, but the
  consolidated angle output ships as production.
