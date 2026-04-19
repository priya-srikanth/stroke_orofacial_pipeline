# Phase 4.5-lite Kickoff — Eye-Midpoint Centering

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md` and follow the instructions in full.

---

## Context

The cross-session alignment regime sweep
(`notebooks/experiments/cross_session_alignment_sweep.ipynb`) tested four
alignment regimes (`eye_affine`, `eye_rigid`, `eye_centered`, `spout_centered`)
across all 8 cohort animals, 13 bodyparts, and every session date. Cohort-wide
result: **`eye_centered` wins 8 of 9 movement bodyparts on both Pearson r and
JS divergence metrics; `spout_centered` wins only for `tongue`**. Full decision
record in `docs/DECISIONS.md` entry dated 2026-04-19.

This mini-phase implements the "lite" version of the originally-proposed
Phase 4.5: add **eye-midpoint centering** as a supported `center_mode`, and
update per-bodypart defaults to use it for face-anchored bodyparts (jaw, nose,
whiskers). **Do NOT implement** the full similarity-transform (`eye_affine`)
or rotation-only (`eye_rigid`) versions — the experiment showed they
underperform or tie translation-only eye-midpoint centering due to eye-fiducial
noise amplification into the warp field.

Scope is intentionally small — strictly additive, no changes to existing
center-mode behavior. Estimated ~150–200 lines of source + test code across
3 files, plus config updates and parquet regeneration.

## Before anything else

Re-read:

- `CLAUDE.md` — all rules apply.
- `docs/DESIGN.md` §4.x (DLC centering architecture).
- `docs/DECISIONS.md` — the 2026-04-19 Phase 4.5-lite decision entry in full.
  The rationale for why we are NOT implementing `eye_affine` or `eye_rigid`
  is important: if you find yourself tempted to add them, STOP and re-read
  the entry.
- `src/stroke_orofacial/dlc_io/centering.py` — existing `compute_center`,
  `apply_centering`, and the `nose` / `spout_midpoint` implementations.
- `tests/test_dlc_centering.py` — existing test patterns.
- `configs/defaults.yaml` — the `dlc_spatial.bodyparts.{bp}.per_center_mode`
  block and the comment at line 76 noting that `"eye_midpoint"` is already
  listed as a supported mode (it was listed before being implemented;
  this phase makes that real).

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath   # should print: .githooks
git checkout -b phase-4.5-lite-eye-midpoint-centering
git branch --show-current           # must print: phase-4.5-lite-eye-midpoint-centering
```

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements.
Expected shape:

1. **Legacy file disambiguation** — **N/A for this phase.** Eye-midpoint
   centering is not a port of legacy code; it's a new feature motivated by
   the sweep experiment. Note and skip.
2. **Dead code identification** — N/A for the same reason. Note and skip.
3. **Sub-phase breakdown** with per-file line-count estimates:
   - **4.5a — Core centering support** (~60 lines src + ~40 lines tests):
     Add the `"eye_midpoint"` branch to `compute_center()` in
     `src/stroke_orofacial/dlc_io/centering.py`. The branch computes the
     per-session median of `(L_eye + R_eye) / 2` after likelihood-gating both
     eyes at the config-defined threshold. Follows the exact pattern of the
     existing `"spout_midpoint"` branch. Add a test in
     `tests/test_dlc_centering.py` that exercises the new mode on a small
     synthetic DataFrame. Verify tests pass before proceeding.
   - **4.5b — Per-bodypart default config** (~30 lines config + ~15 lines tests):
     In `configs/defaults.yaml`, update the `dlc_spatial.bodyparts.{bp}`
     block to set a per-bodypart default `center_mode`:
     - `tongue` → `spout_midpoint` (unchanged)
     - `jaw`, `nose`, `L_whiskers_1`, `L_whiskers_2`, `L_whiskers_3`,
       `R_whiskers_1`, `R_whiskers_2`, `R_whiskers_3` → `eye_midpoint` (new)
     The bodypart keys for eyes and spouts themselves (`L_eye`, `R_eye`,
     `L_spout`, `R_spout`) get `center_mode: null` — these are fiducials and
     have no meaningful downstream centering. Add test validating the config
     loads with the new defaults.
   - **4.5c — Regenerate centered parquets** (~0 new lines; execute existing
     Phase 4 `build_centered_parquet` with new defaults):
     For each animal × date with DLC output available, rebuild centered
     parquets under the new defaults. New parquets for bodyparts that
     switched from nose/spout_midpoint to eye_midpoint; tongue parquets
     (on spout_midpoint) should be byte-identical to the prior build —
     verify via hash comparison against the Phase 4 parity hashes
     `c23dc714`, `2a6efb6a`, `b13af51c` listed in
     `docs/MIGRATION_LOG.md` Phase 4 entry.
     Run through the existing `notebooks/10_dlc_build_parquets.ipynb` with
     the updated config; capture hash signatures for the new eye_midpoint
     parquets so future parity checks have a baseline.
   - **4.5d — Phase 5 + 6 axis limits for new combos** (~15 lines config):
     Phase 5 plotting config
     (`configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.per_center_mode.eye_midpoint`)
     has `xlim` / `ylim` set to `null` for most bodyparts. For the bodyparts
     newly defaulting to eye_midpoint, either (a) set explicit axis limits
     derived from the sweep's pooled-heatmap data, or (b) leave them `null`
     and let `plot_heatmap` auto-scale. Recommend (b) for this phase —
     explicit limits can be tuned in a follow-up once eye_midpoint plots
     have been visually reviewed across the cohort. Parity: Phase 5/6
     regressions for `tongue` (still `spout_midpoint`) should be
     byte-identical. Phase 5/6 outputs for `jaw`/`nose`/whiskers are
     new artifacts under the new center_mode — not parity-tested against
     prior runs.
   - **4.5e — Docs + test suite sweep** (~40 lines docs):
     Add `docs/MIGRATION_LOG.md` Phase 4.5-lite entry summarizing the change,
     list of bodyparts whose default shifted, link to the DECISIONS entry,
     and note that `eye_affine` / `eye_rigid` were tested and rejected.
     Cross-reference the experimental record at
     `notebooks/experiments/outputs/alignment_sweep/`. Run `pytest` end-to-end;
     all pre-existing tests must pass, new tests from 4.5a/4.5b must pass.
     Run `ruff check` — must be clean.
4. **Parity strategy** —
   - Full pytest suite passes before and after.
   - Tongue-centered parquet hashes (`c23dc714`, `2a6efb6a`, `b13af51c` per
     Phase 4 MIGRATION_LOG) are byte-identical post-4.5c.
   - Phase 5/6 outputs for tongue are byte-identical (same center_mode, same
     parquet, same plotting code path).
   - Phase 5/6 outputs for non-tongue bodyparts are NEW artifacts under the
     new default; record their hashes but don't parity-test against prior
     (which used `nose` centering).
5. **Hardcoded constants** — none new. The eye-midpoint computation uses
   the existing `EYE_LIKELIHOOD_THRESHOLD` from
   `configs/defaults.yaml`.

The plan must pause for Priya's explicit approval before any files are written.

## Refactor pattern — to apply consistently

For the new `eye_midpoint` branch in `compute_center()`, mirror the existing
`spout_midpoint` pattern exactly:

```python
# BEFORE — existing structure in compute_center()
def compute_center(df: pd.DataFrame, mode: str, thr: float) -> np.ndarray:
    """..."""
    if mode == "nose":
        ...
    elif mode == "spout_midpoint":
        lx, ly = _median_from_lik(df, "L_spout_x", "L_spout_y", "L_spout_likelihood", thr)
        rx, ry = _median_from_lik(df, "R_spout_x", "R_spout_y", "R_spout_likelihood", thr)
        return np.array([(lx + rx) / 2, (ly + ry) / 2])
    else:
        raise ValueError(f"Unknown center mode: {mode!r}")

# AFTER — add eye_midpoint branch
def compute_center(df: pd.DataFrame, mode: str, thr: float) -> np.ndarray:
    """..."""
    if mode == "nose":
        ...
    elif mode == "spout_midpoint":
        ...  # unchanged
    elif mode == "eye_midpoint":
        lx, ly = _median_from_lik(df, "L_eye_x", "L_eye_y", "L_eye_likelihood", thr)
        rx, ry = _median_from_lik(df, "R_eye_x", "R_eye_y", "R_eye_likelihood", thr)
        return np.array([(lx + rx) / 2, (ly + ry) / 2])
    else:
        raise ValueError(f"Unknown center mode: {mode!r}")
```

Apply the same pattern in `apply_centering()` if it has a mode-dispatch path
(likely it just consumes the center returned by `compute_center` so may not
need changes — verify).

## Exit criteria

- All pre-existing tests still pass.
- New test for `eye_midpoint` center mode passes.
- Config test confirming per-bodypart defaults loads correctly passes.
- Tongue parquets rebuild with byte-identical hashes (`c23dc714` etc.).
- New eye-midpoint parquets generated for jaw, nose, all 6 whiskers, for
  every animal × date with DLC output available.
- Phase 5 output regression (tongue heatmaps byte-identical; new heatmaps
  for jaw / nose / whiskers under new center mode).
- `ruff check` clean.
- `docs/MIGRATION_LOG.md` Phase 4.5-lite entry summarizes what changed,
  bodypart list, and links to both the DECISIONS entry and the sweep
  experiment record.
- `docs/DECISIONS.md` Phase 4.5-lite entry (already written 2026-04-19) is
  accurate vis-à-vis the actual implementation — amend only if implementation
  differs from design (it shouldn't).
- PR description includes sweep metric summary (3-line table showing per-bodypart
  regime winner).

## Constraints

- Strictly additive. No changes to existing `compute_center` modes
  (`nose`, `spout_midpoint`). No changes to the `_median_from_lik` helper.
- No implementation of `eye_affine` or `eye_rigid` in production code —
  these are explicitly rejected per the DECISIONS entry. If they become
  relevant in the future (e.g., a new drift pattern emerges), re-run the
  sweep experiment with updated data and revisit.
- Per-bodypart `center_mode` defaults in `configs/defaults.yaml` apply to
  every downstream consumer (Phase 5 whole-session, Phase 6 reward-aligned,
  Phase 7+ future phases). If any downstream notebook explicitly overrides
  `center_mode`, that override wins — the default only applies when the
  caller doesn't specify.
- Fiducial bodyparts (`L_eye`, `R_eye`, `L_spout`, `R_spout`) get
  `center_mode: null` — they are not centered for downstream analysis;
  they're used to *derive* the center for others.

If the refactor reveals a place where the new default breaks an existing
analysis silently (e.g., a Phase 5/6 notebook whose axis limits were tuned
for nose-centered data and now shows empty heatmaps under eye_midpoint),
STOP and ask. The solution is likely additional per-(bodypart, center_mode)
axis-limit config entries, not reverting the default.
