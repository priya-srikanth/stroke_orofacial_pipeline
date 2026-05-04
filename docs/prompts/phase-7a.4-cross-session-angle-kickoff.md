# Phase 7a.4-cross-session-angle — kickoff

**Status:** AUDIT-FIRST. STOP at Task 1 outcome lock before any code.

**Branch:** `phase/7a.4-cross-session-angle` off `main` (cut after
`phase/7a.4-paths-cleanup` merges + tag `v7a.4-paths-cleanup`
lands on `main`). The orientation flip (PR #93, tag
`v7a.4-orientation-fix-cam-view-flip`) and figures_qc/ retirement
(`phase/7a.4-paths-cleanup`) must both be on `main` before this
phase begins — it depends on the renamed `tongue_angle_dir`
resolver and the cam-view convention being established.

**Tag on merge:** `v7a.4-cross-session-angle` (or pick at close).

---

## Context

Phase 7a.4 (PR #86, 2026-04-30) shipped the per-(animal, date) tongue
angle/phase visual gate via `tongue_visual.py` — 5 plot families:
`qc_trials`, `first_peak_aligned`, `reward_aligned`,
`phase_aligned_angle`, `xy_by_phase`. All per-session only.

Phase 7a.4-orientation-fix (PR #93, tag
`v7a.4-orientation-fix-cam-view-flip`) flipped `xy_by_phase` to
cam-view L/R orientation. Phase 7a.4-paths-cleanup (tag
`v7a.4-paths-cleanup`) renamed `tongue_visual_qc_dir` →
`tongue_angle_dir` (path: `dlc_kinematics/tongue_angle/{animal}/{date}/`),
deleted the comparison-grid renderer, and dropped `figures_qc/`
from both 7a.4 and 7a.5 layouts.

This phase adds **cross-session aggregations** of three of the per-
session families, plus a **per-session mode split** for
`phase_aligned_angle`. Net-new design; no legacy reference.

## Why now

Priya wants per-mouse cross-session views of the angle/phase data
to evaluate post-stroke recovery trajectories at the angle level
(complementing the 7a.6 mean/SEM cross-session work which operates
on raw Y-position, and the 7a.5 mismatch cross-session work which
operates on candidate-trial classification). The pre-stroke-grey +
post-stroke-plasma colormap convention from 7a.5/7a.6 carries over.

## Scope

### A — new per-session plot family

`phase_aligned_angle` currently renders one PNG using
`phase_summary_mode = "first_multi"` (only the first multi-bout per
trial). The mode infrastructure already supports `"all_multi"` via
`_select_phase_rows` in `tongue_visual.py:679`.

Split into two distinct emitted PNGs per (animal, date):
- `phase_aligned_angle_1st_lick.png` (mode=`first_multi`)
- `phase_aligned_angle_all_licks.png` (mode=`all_multi`)

Locks open at Task 1:
- Naming: `_1st_lick`/`_all_licks` (Priya's preference) vs
  `_first_multi`/`_all_multi` (matches internal mode tokens)?
- Backward compat: should we also keep emitting the bare
  `phase_aligned_angle.png` for one of the two modes (=
  current default), or replace entirely?

### B — three new cross-session figure families

Per mouse, render these. All share the convention:
- L trials and R trials in **separate panels** (cam-view: R-trials
  on figure-left, L-trials on figure-right per the
  7a.4-orientation-fix DECISIONS entry, 2026-05-03)
- Pre-stroke sessions = grey
- Post-stroke sessions = plasma colormap by relative day
- Day-binning uses `animal_info.bin_days` from `configs/animals.yaml`
  (PS46–50: 2; PS51/54/55: 7) — same convention as 7a.4 day-binned
  (`_day_binned.py`) and 7a.6 mean/SEM cross-session

Three families:

1. **`first_peak_aligned_angle_cross_session`** — angle aligned to
   first detected lick peak, per side. Sub-variants:
   - session overlays
   - day-binned overlays
   - mean ± SEM (Priya specifically called this one out)

2. **`phase_aligned_angle_cross_session`** — phase-aligned angle,
   per side. Sub-variants: session overlays + binned overlays.
   **Two flavours each**, mirroring the per-session split (A above):
   `_1st_lick` and `_all_licks`.

3. **`reward_aligned_angle_cross_session`** — reward-aligned tongue
   angle, per side. Sub-variants: session overlays + binned overlays.
   Window: confirm with Priya at Task 1 (her suggestion: -150 to
   1000 ms; existing per-session `_plot_reward_aligned` uses the
   array column `t_arr` whose extent is determined by the bundle
   build window — likely matches one of 7a.6's `WINDOWS_MS` entries
   `(100, 1000)` or `(500, 5000)`).

Locks open at Task 1:
- Reward-aligned cross-session window (Priya's suggested -150/1000
  vs 7a.6's existing windows)
- Whether mean ± SEM applies to all 3 families or only first-peak-
  aligned (Priya's spec mentioned it explicitly only for #1)
- Whether to also emit a "trial overlays" sub-variant (per
  individual trial, like 7a.6's `trial_overlays`) or skip
- Whether `phase_aligned_angle_cross_session_all_licks` even makes
  sense (lots of licks across sessions → very dense; might want
  a sub-sample knob)

### Architecture options for B

Three plausible:

- **Option B1 — net-new module `tongue_angle_cohort.py`**, mirroring
  the 7a.6 `mean_sem_visual.py` shape. Self-contained. ~1,500–2,500
  LOC. Composite wrappers `build_tongue_angle_by_animal_date` +
  `build_tongue_angle_cohort` per the 7a.6 precedent.

- **Option B2 — extend `mean_sem_visual.py`** with an `axis: Literal
  ["y_pos", "angle_deg"]` parameter alongside the existing
  `bodypart` parametric. Reuses the per-window subdir machinery
  (`mean_sem_visual_dir(bodypart, ..., plot_family, animal)`) and
  the cohort aggregator pattern. Smaller diff but tongue_angle is
  tongue-only, so the bodypart param is half-vestigial.

- **Option B3 — three sibling modules** (one per family) under
  `dlc_kinematics/`, each ~500 LOC. Maximally readable but
  duplicates per-mouse-loop + colormap + axis-labelling boilerplate.

Lock at Task 1.

### Out of scope

- Bodyparts other than tongue (jaw angle/phase doesn't exist;
  jaw notebook has no per-trial angle features per the 7a.3-jaw
  audit).
- Cross-bodypart cross-session (e.g., tongue-vs-jaw angle
  comparison panels). That's its own phase.
- Cell 43 PSD (continues to be deferred to a future PSD phase).
- Legacy parity. None exists; the legacy notebook has no
  cross-session angle plots either.

## Acceptance gates

1. **pytest** — full suite green including new unit tests for the
   selected family-rendering helpers.
2. **Visual gate** — render on PS46 + PS50 + PS55 (one pre-stroke
   baseline animal, one early-post-stroke, one late-recovery).
   Priya's eyeball PASS verdict on the rendered cross-session PNGs.
3. **Smoke notebook 13** — once new families are wired into
   notebook 13's USER INPUTS + per-mouse loop, `jupyter nbconvert
   --execute` against PS46 completes without error.

No legacy-CSV parity (none exists). No bit-stability requirement
across re-runs (data-driven plots; SEM denominators are stable but
floating-point order may differ on the order of <1e-12).

## Path conventions for new outputs

Per-session new PNGs land alongside the existing 5 families at:
```
<outputs>/dlc_kinematics/tongue_angle/{animal}/{YYYYMMDD}/
  ├─ phase_aligned_angle_1st_lick.png
  ├─ phase_aligned_angle_all_licks.png
  └─ ... (existing 5 families unchanged)
```

Cross-session PNGs land at a **new** sibling directory mirroring the
7a.5 `cross_session/` pattern:
```
<outputs>/dlc_kinematics/tongue_angle_cohort/{animal}/
  ├─ {animal}_first_peak_aligned_session_overlays.png
  ├─ {animal}_first_peak_aligned_binned_overlays.png
  ├─ {animal}_first_peak_aligned_mean_sem.png
  ├─ {animal}_phase_aligned_1st_lick_session_overlays.png
  ├─ {animal}_phase_aligned_1st_lick_binned_overlays.png
  ├─ {animal}_phase_aligned_all_licks_session_overlays.png
  ├─ {animal}_phase_aligned_all_licks_binned_overlays.png
  ├─ {animal}_reward_aligned_session_overlays.png
  └─ {animal}_reward_aligned_binned_overlays.png
```

(File naming subject to Priya's confirmation at Task 1.) Add the
new resolver `tongue_angle_cohort_dir(animal)` to
`stroke_orofacial.paths.PathResolver`.

## Notebook integration

Notebook 13 (`13_dlc_kinematics_tongue.ipynb`) currently has 12
cells; cell 8 is the 7a.5 cross-session mismatch loop that landed
in 7a.4-orientation-and-paths-cleanup. Add a new per-mouse loop
cell (after cell 8 or wherever fits the flow) for tongue-angle
cross-session families. Mirror the 7a.5 cross-session cell shape:
- Toggle: `INCLUDE_TONGUE_ANGLE_COHORT = True` in USER INPUTS
- Sub-knob: `OVERWRITE_TONGUE_ANGLE_COHORT = None` (= inherit
  global `OVERWRITE`; set to `"force"` to regenerate iteratively)
- Loop over `ANIMALS`, call the public composite
  `build_tongue_angle_cohort(animal, resolver, overwrite=...)`
- Print `ok=N skip=M err=K` summary at end

## Three outcome branches (lock at Task 1)

- **A (minimal).** Per-session mode split (A) only; defer the
  cross-session families (B) to a follow-up. ~1–3 commits, ~100
  LOC. Use if the per-session split is high-value standalone and
  the cross-session work needs more design time.

- **B (substantial).** Full scope: per-session split + all 3
  cross-session families × all sub-variants. ~10–15 commits,
  2,000–4,000 LOC. Use if all three families' value is clearly
  established.

- **C (partial).** Per-session split + 1 cross-session family
  (probably first_peak_aligned, the highest-priority one Priya
  called out for mean ± SEM). Defer phase_aligned + reward_aligned
  cross-session to a follow-up. ~5–8 commits, 800–1,500 LOC. Use
  if first_peak is clearly highest value and the others can wait.

## Task plan template (audit-first)

1. **Task 1 — audit + scope lock.** Inventory what data
   `tongue_pertrial.TongueVisualBundle` already exposes that
   feeds each new family (list each by-frame array + dataframe
   column). Identify any gaps (does the per-session bundle have
   `t_firstpeak_align_ms` and `angle_firstpeak_snip` already? Does
   it have `phase_bin_center` × `angle_deg` for both
   `multi_bout_rank == 0` and the unfiltered set?). Confirm no
   legacy-vendor work is needed (net-new). Lock A/B/C outcome with
   Priya. Lock all open scope questions.

2. **Task 2 — config + paths scaffold.** Add new
   `dlc_kinematics.tongue_angle_cohort:` config block to
   `configs/defaults.yaml`. Add `tongue_angle_cohort_dir` resolver
   + tests in `tests/test_paths.py`. Update `__init__.py` exports.

3. **Task 3 — module port (A or B per Task 1 outcome).** Write
   the new module(s). Mirror 7a.6 `mean_sem_visual.py` for the
   `build_*_cohort` shape and the colormap helpers (look at
   `_color_for_rel_day_continuous` and the `pre_color` /
   `post_cmap` knobs).

4. **Task 4 — unit tests.** Synthetic-bundle tests covering each
   plot family + cross-session aggregation logic (NaN handling,
   day-binning correctness, pre/post grouping, colormap
   selection). Pattern after `tests/test_mean_sem_visual.py`.

5. **Task 5 — notebook 13 wiring.** Add the new cell + USER
   INPUTS knobs as specified above.

6. **Task 6 — smoke + visual gate.** Run notebook 13 on PS46;
   render cross-session PNGs for PS46 + PS50 + PS55; Priya's
   eyeball PASS verdict.

7. **Task 7 — DECISIONS + MIGRATION_LOG entries.** Codify the
   convention reuse (cam-view, pre-stroke grey + post-stroke
   plasma, day-binning from animals.yaml). Cite the precedents
   (7a.5 cross-session, 7a.6 mean/SEM cross-session, 7a.4
   orientation flip).

8. **Task 8 — PR + tag.** `v7a.4-cross-session-angle` on the
   merge commit.

## Hard constraints

- **CLAUDE.md ground rules** apply throughout. Especially:
  - Never modify legacy notebooks (none referenced here anyway).
  - Sandbox-git boundary: all `git` mutating ops from CC's
    Windows terminal, never from a Cowork sandbox.
  - Before any commit, run `git branch --show-current` and confirm
    NOT on `main`.
  - PR-merge → tag → push tag.

- **Cam-view L/R convention** is now project-wide standard.
  All L/R subplots use `side_to_ax = {"R": axes[0], "L":
  axes[1]}`. See `mean_sem_visual._plot_mean_xy_overlays` and
  `tongue_visual._plot_xy_by_phase` for precedent.

- **bin_days** comes from `animals.yaml`; do not hardcode.

- **No `figures_qc/` paths** — that subtree was retired in
  7a.4-orientation-and-paths-cleanup. New paths go directly under
  `dlc_kinematics/<feature_name>/`.

- **Pre-stroke grey + post-stroke plasma colormap** — reuse the
  helpers from `mean_sem_visual.py`
  (`_color_for_rel_day_continuous`, `pre_color`, `post_cmap`)
  rather than reimplementing.

## STOP-and-ask checkpoints

- After Task 1 audit, before any code: report findings, propose
  outcome A/B/C, lock all open scope qs.
- If Task 3 implementation surfaces design surprises (e.g., the
  bundle doesn't expose what the family needs), STOP and report
  before patching `tongue_pertrial` to add the missing accessor.
- If visual-gate verdict is FAIL on any family, STOP and report
  before iterating; multiple visual fixes per round (like 7a.6's
  C7.x arc) are expected; don't ship without explicit Priya PASS.

## Pointers

- Architecture template: `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`
  (~3,400 LOC, bodypart-parametric, cross-session aggregator + per-
  mouse cohort wrapper, day-binned + colormap helpers).
- Per-session bundle source:
  `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`
  (`TongueVisualBundle`, `build_tongue_visual_bundle_by_animal_date`).
- Per-session renderers to mirror:
  `src/stroke_orofacial/dlc_kinematics/tongue_visual.py`
  (`_plot_first_peak_aligned`, `_plot_phase_aligned_angle`,
  `_plot_reward_aligned`, `_select_phase_rows`).
- Cross-session precedents to mirror:
  - `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`
    `render_cross_session_figures` (per-mouse loop, pre/post
    colormap, bin_days from animals.yaml).
  - 7a.6 `mean_sem_visual.build_mean_sem_cohort` (cohort
    aggregator, per-window subdir).
- Day-binning aggregator precedent:
  `src/stroke_orofacial/dlc_kinematics/_day_binned.py`
  (Phase 7a.4 licking dynamics — same animals.yaml `bin_days`
  source, same ddof=1 SEM convention; reuse the helpers if natural).
