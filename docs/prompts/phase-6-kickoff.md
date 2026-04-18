# Phase 6 Kickoff — DLC Spatial (Reward-Aligned)

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-6-kickoff.md` and follow the instructions in full.

---

## Context

Phase 6 per `docs/DESIGN.md` §7: port the reward-aligned variants of the
DLC spatial analyses, generalizing Phase 5's whole-session functions to
accept a `window` argument. The reward-aligned window defaults to (0, 8000)
ms per `DESIGN.md` §4.3 and is parameterizable per analysis.

**Phase 6 extends Phase 5 — it does not duplicate it.** Phase 5's
`build_histogram`, `plot_heatmap`, `compute_difference_map`, etc. should be
*refactored* to accept a window selector, not *rewritten*. The existing
whole-session behavior is preserved by passing a `WholeSessionWindow` (the
stub already in `src/stroke_orofacial/dlc_spatial/window_selector.py`).

Scope:
- Extend `window_selector.py` with reward-aligned and (forward-looking)
  cue-aligned event-window selectors.
- Generalize Phase 5 spatial functions to accept a `window` argument.
- Port reward-aligned cells (especially cell 16 of `20260323_..._tongue_jaw.ipynb`,
  classified Exploratory in Phase 4 and reclassified Production for Phase 6).
- New thin notebook `notebooks/12_dlc_spatial_reward_aligned.ipynb`.
- Parity vs legacy reward-aligned outputs.

Non-goals:
- Statistics on reward-aligned maps (Phase 9 — per DECISIONS.md "Phase 5
  defers permutation/inferential spatial stats to Phase 9").
- Cue-aligned spatial analysis as a first-class workflow (the window
  selector will support it architecturally, but a dedicated cue-aligned
  notebook is a later decision).
- Kinematics (Phase 7).

## Before anything else

Re-read these and confirm in one sentence that the constraints are
internalized:

- `CLAUDE.md` — full file. All ground rules + plan requirements apply.
- `docs/DESIGN.md` §4.3 (time-base contract), §7 Phase 6.
- `docs/MIGRATION_LOG.md` Phases 4, 5, 5.5 (what exists to build on — especially
  Phase 5's `dlc_spatial/` module structure and the window_selector scaffold).
- `docs/DECISIONS.md` — especially:
  - **"2026-04-18 — Plot axis limits must be per-(bodypart, center_mode)"** —
    may need to extend to per-(bodypart, center_mode, window_type) if the
    reward-aligned window calls for different axis limits than whole-session.
  - **"2026-04-18 — Phase 5 defers permutation/inferential spatial stats to
    Phase 9"** — applies to Phase 6 too. Phase 6 produces descriptive maps;
    Phase 9 does stats on them.
  - **"2026-04-18 — Legacy notebooks may receive active edits; re-read at
    each phase kickoff"** — re-read the current `20260323` notebook (cell 16
    is the primary Phase 6 source).

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath   # must print: .githooks
git checkout -b phase-6-dlc-spatial-reward-aligned
git branch --show-current          # must print: phase-6-dlc-spatial-reward-aligned
```

All commits on `phase-6-dlc-spatial-reward-aligned`. Before each commit,
`git branch --show-current` must print that branch. Pre-commit hook backstops.

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements:

1. **Legacy file disambiguation.** The primary source is cell 16 of
   `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` (already
   identified in Phase 4's dead-code classification as "Reward-aligned DLC
   bodypart heatmaps," Phase 5-6 scope). Re-check for any other
   reward-aligned spatial code in `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`
   and both legacy repos. Apply the refined CLAUDE.md rule 1 if ambiguous.
2. **Dead code identification.** For the 20260323 notebook (revisit Phase 4's
   cell-by-cell table): cell 16 was classified Exploratory then → reclassify
   to Production for Phase 6. Confirm no other Phase 4-deferred cells belong
   to Phase 6.
3. **Sub-phase breakdown.** Expected shape:
   - **6a**: Extend `window_selector.py` with event-aligned selectors +
     config.
   - **6b**: Generalize Phase 5's spatial functions to accept `window`.
   - **6c**: Port cell 16 (reward-aligned heatmaps specifically).
   - **6d**: Orchestrator notebook + parity check.
   - **6e**: Tests + MIGRATION_LOG + DECISIONS.md.
4. **Parity strategy.** Compare reward-aligned heatmaps from the new pipeline
   against whatever reward-aligned outputs the legacy notebook produced —
   likely PNGs, possibly NPZ files in `PS46_*_heatmap_bins/` or similar
   subdirs on MICROSCOPE. If only PNGs exist, array-level parity isn't
   possible; visual + structural parity is the fallback. Document the
   limitation.
5. **Hardcoded constants → `configs/defaults.yaml`**. Reward-aligned-specific:
   - `reward_window_ms`: default (0, 8000).
   - Whether to align on reward onset, cue onset, or both (check the legacy
     notebook for which event channel cell 16 uses — might be
     `consolidated_reward_bool` from Phase 2, or per-side `peri_reward_L/R`
     from Phase 2.5).
   - Any reward-window-specific axis limits or colormaps (if different from
     whole-session).

Wait for my explicit approval before writing any files.

## Expected scope (to seed plan mode, not prescriptive)

Likely shape:

### window_selector.py extension

```python
class WindowSelector(Protocol):
    def get_mask(self, n_frames: int, alignment: AlignmentResult | None = None) -> np.ndarray[bool]: ...

class WholeSessionWindow:  # already scaffolded in Phase 5
    def get_mask(self, n_frames, alignment=None):
        return np.ones(n_frames, dtype=bool)

class EventAlignedWindow:
    """Window around each occurrence of an event. Generic over event type."""
    def __init__(self, events_frame_idx: np.ndarray, window_frames: tuple[int, int]): ...
    def get_mask(self, n_frames, alignment=None): ...

class RewardAlignedWindow(EventAlignedWindow):
    """Thin convenience wrapper: takes reward events (wavesurfer samples),
    converts to frame indices via AlignmentResult, applies window_ms range."""
    def __init__(self, reward_ws_samples, alignment, window_ms=(0, 8000)): ...

# Optional for future cue-aligned work (decide in plan mode whether to include now):
class CueAlignedWindow(EventAlignedWindow):
    """Takes tone events (wavesurfer samples) and a window_ms range."""
```

Phase 5's `build_histogram()` signature changes from
`build_histogram(df, bodypart, config)` to
`build_histogram(df, bodypart, config, window=WholeSessionWindow())`. The
function applies the window mask before binning. Whole-session calls don't
need to change (default preserves behavior).

### Spatial function generalization

Refactor Phase 5's `pixel_bins.py`, `heatmaps.py`, `difference_maps.py`:

- Each function accepts `window: WindowSelector` with
  `WholeSessionWindow()` default.
- Mask is applied after likelihood-gating, before histogram computation.
- No behavior change for whole-session callers (Phase 5 notebook still works).

Verify this doesn't break any Phase 5 tests — whole-session default should
preserve existing parity.

### Reward event sourcing

The reward events live in Phase 2's outputs at
`pipeline_outputs_v2/spout_behavior/licks_and_rewards/{animal}/{YYYYMMDD}.npz`
(keys: `Reward_L`, `Reward_R` — wavesurfer sample indices). Phase 2.5 added
`peri_reward_L` / `peri_reward_R` / `peri_reward_bool` to the
`peri_reward_periods/` NPZ, but those are already-windowed boolean masks in
wavesurfer-sample space.

For Phase 6 spatial analyses we need:
1. Reward onset sample indices (from `licks_and_rewards` NPZ).
2. Conversion to video-frame indices via Phase 3's `AlignmentResult.sig_wsIdx__idx_cam`
   (inverse: which camera frame corresponds to this WS sample).
3. Build a per-frame boolean mask: True for frames within (0, 8000) ms of
   any reward.

Plan should clarify which formulation to use. The legacy cell 16 likely used
a specific approach — inspect it during plan mode.

### Per-(bodypart, center_mode, window_type) plotting parameters

Phase 5's `dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}` schema may
need to extend to
`dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}.windows.{window_type}`
for reward-aligned-specific axis limits. Or reward-aligned windows might use
the same limits as whole-session — test during implementation, add the extra
nesting only if the legacy cell 16 uses different limits for reward-aligned
output.

## Constraints

- No writes outside `~/Github/stroke_orofacial_pipeline/` except to
  `pipeline_outputs_v2/dlc_analysis/spatial_reward_aligned/` on MICROSCOPE.
- Both legacy repos, DLC inference outputs, camera data, alignment_templates
  — all read-only.
- Phase 5's `pipeline_outputs_v2/dlc_analysis/centered_{mode}/` parquets are
  **inputs**, read-only.
- Phase 5 code in `dlc_spatial/` — refactored (add `window` argument), not
  rewritten. Existing whole-session behavior preserved.
- Phase 5 tests — all still passing after the refactor.
- Pre-commit hook in force.
- Before every commit, `git branch --show-current` must print
  `phase-6-dlc-spatial-reward-aligned`.

## Exit criteria

- Plan approved by Priya, sub-phases executed with per-sub-phase commits.
- Phase 5 tests all still pass (whole-session default preserves behavior).
- New reward-aligned tests pass.
- Parity check against legacy cell 16 output (at whatever level possible
  given legacy output format).
- Lint clean.
- `docs/MIGRATION_LOG.md` Phase 6 entry documents sub-phases, what was
  refactored vs added, parity status, intentional behavior differences.
- `docs/DECISIONS.md` gets new entries for any cross-cutting decisions
  (especially if the config schema extends, or if the reward-event
  sourcing approach is non-obvious).
- Pause after parity check (before tests + MIGRATION_LOG sub-phase) for
  Priya's mid-phase review.

If refactoring Phase 5 functions to accept a `window` argument breaks any
existing Phase 5 tests, STOP and ask — the refactor should be additive
(add a parameter with a default preserving existing behavior), not
behavior-changing.

If the legacy cell 16 uses an event-alignment approach that doesn't cleanly
fit the proposed `EventAlignedWindow` API (e.g., it aggregates across events
differently, or it uses a different alignment reference), STOP and ask
before forcing it into the proposed abstraction.
