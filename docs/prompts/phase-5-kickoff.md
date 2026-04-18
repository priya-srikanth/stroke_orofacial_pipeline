# Phase 5 Kickoff — DLC Spatial Analyses (Whole Session)

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-5-kickoff.md` and follow the instructions in full.

---

## Context

Phase 5 per `docs/DESIGN.md` §7: port the DLC *whole-session* spatial
analyses — pixel-bin occupancy maps, 2D-KDE heatmaps, and difference maps
— from the legacy notebooks into `src/stroke_orofacial/dlc_spatial/` plus
`notebooks/11_dlc_spatial_whole_session.ipynb`.

**Phase 5 is whole-session only.** The reward-aligned / trial-windowed
variants of these same analyses are Phase 6 scope (per `DESIGN.md` §7), where
a shared `window_selector` abstraction will let Phase 5's functions accept
"whole session" or any reward-aligned window.

**Phase 5 does not include statistics.** The Jensen-Shannon / Wasserstein /
unbalanced-OT stats on the heatmaps are Phase 9 scope. Phase 5 produces the
spatial maps; Phase 9 compares them.

Consumes: centered parquets produced by Phase 4 at
`pipeline_outputs_v2/dlc_analysis/centered_{mode}/{animal}/`.

Produces: spatial maps and difference maps at
`pipeline_outputs_v2/dlc_analysis/spatial_whole_session/` on MICROSCOPE.

## Before anything else

Re-read these in full and confirm in one sentence that the data-safety and
plan-requirements constraints are internalized:

- `CLAUDE.md` — full file. Especially:
  - Ground rules 1-8 (data safety + git discipline).
  - "Legacy code version disambiguation" rule 1 (siblings vs duplicates —
    **Phase 5 has multiple legacy sources that need this distinction**).
  - "Phase plan requirements" (all five elements, including the dead code
    identification step).
- `docs/DESIGN.md` §3, §5 (notebook → module migration map for Phase 5), §7
  Phase 5 + §7 Phase 6 + §7 Phase 9 (to understand where future phases will
  hook in).
- `docs/MIGRATION_LOG.md` Phases 0-4 (so you know what's in place and can
  build on it, especially Phase 4's centered parquets and the
  `CenterMode` enum).
- `docs/DECISIONS.md` — project-wide decisions. Especially:
  - **"2026-04-18 — Phase 5+ downstream analyses: preserve per-(bodypart,
    center_mode) plotting parameters"** — this is the Phase where that
    requirement becomes directly actionable.
  - **"2026-04-18 — Phase 4 orchestrator: iterate over animals without
    notebook restart"** — apply the same pattern here.
- `configs/defaults.yaml` — note the `dlc_centering` section added in
  Phase 4.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath           # must print: .githooks
git checkout -b phase-5-dlc-spatial
git branch --show-current                  # must print: phase-5-dlc-spatial
```

All commits on `phase-5-dlc-spatial`. Before each commit, run
`git branch --show-current` and stop if it isn't that. The pre-commit hook
backstops this.

## Legacy sources to disambiguate (expected candidates; plan must verify)

Start with `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` and
`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` and
`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp/`. Expected Phase 5
candidate files:

- `20251117_DLC_analysis_nose.ipynb` — per-bodypart spatial analysis (nose).
- `20251117_DLC_analysis_jaw.ipynb` — per-bodypart spatial analysis (jaw).
  These two are **siblings** per the refined rule (distinct scope markers
  `_nose` vs `_jaw`, same date), NOT duplicates. Both must be considered.
  Likely outcome: port as **one unified module** that loops over bodyparts,
  consolidating their shared logic.
- `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` — pixel-bin
  analysis for all bodyparts. (Note: "stats" in the filename refers to
  summary statistics on the bins, not to inferential stats which are
  Phase 9 scope — verify in plan mode.)
- `20251201_DLC_analysis_all_bodyparts_2KSD_spatial-maps.ipynb` — 2D-KDE
  spatial maps. Per `DESIGN.md` §5, "Kept, marked exploratory in docstrings."
- **Cells 14-23 of the 20260323 notebook** — these cells were classified
  Exploratory (deferred) in Phase 4's dead-code analysis. Revisit: in Phase 5
  they may become Production, specifically the heatmap, binned heatmap, and
  subtraction-map cells (cells 14-20 per Phase 4's `MIGRATION_LOG` entry).
  Re-classify them under Phase 5's scope.

Apply the refined CLAUDE.md rule 1 (siblings vs duplicates) carefully. If any
ambiguity arises, trigger rule 3 STOP-and-ask.

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements:

1. **Legacy file disambiguation** — inspect every candidate listed above plus
   anything else you find. Apply the refined rule 1. Produce a classification
   table (same format as Phase 4's plan). Call out siblings explicitly
   (especially `_nose` vs `_jaw`). STOP-and-ask on ambiguous cases.
2. **Dead code identification** — for each canonical source (notebook or
   `.py`), cell-by-cell or function-by-function classification:
   *Production* / *Exploratory* / *Deprecated* / *Ambiguous*. Only
   *Production* is ported.
3. **Sub-phase breakdown** with per-file line-count estimates and dependency
   order.
4. **Parity strategy** — the legacy notebooks' outputs (likely PNG plots,
   possibly saved NPZ/parquet of bin counts or KDE grids) are the parity
   reference. Describe what to compare (arrays if available, visual
   similarity for PNGs), and what tolerances.
5. **Hardcoded constants** — list *everything* that should move to
   `configs/defaults.yaml`. **Pay particular attention to per-(bodypart,
   center_mode) parameters**: axis limits, colormap ranges, filter ranges,
   bin sizes, KDE bandwidths. These vary across bodypart and center_mode
   combinations and must be preserved as structured config, not coalesced
   into defaults.

Wait for my explicit approval before writing any files.

## Expected scope (to seed plan mode, not prescriptive)

Likely shape of the ported modules:

- `src/stroke_orofacial/dlc_spatial/heatmaps.py` — 2D-KDE heatmaps and
  raw scatter plots per (animal, session, bodypart, center_mode). Marked
  exploratory in docstrings per `DESIGN.md` §5.
- `src/stroke_orofacial/dlc_spatial/pixel_bins.py` — binned occupancy maps.
  Also computes the summary bin-count stats (per-bin fraction of total
  occupancy).
- `src/stroke_orofacial/dlc_spatial/difference_maps.py` — pairwise
  subtraction maps (e.g., post-stroke day X minus baseline mean). This
  consumes outputs from the other two modules.
- `src/stroke_orofacial/dlc_spatial/window_selector.py` — **scaffold only for
  Phase 5**. Just a simple "whole session" selector. Full
  reward-aligned-window implementation is Phase 6. The point is to establish
  the API (so Phase 5 functions take a `window` argument and Phase 6 extends
  without refactor).
- `notebooks/11_dlc_spatial_whole_session.ipynb` — thin orchestrator with
  USER INPUTS cell (animal list, date range, bodypart list, center_mode
  list). Loops over (animal × date × bodypart × center_mode). Stateless; no
  notebook restart required between animals.

### Per-(bodypart, center_mode) plotting parameters — DECISIONS.md requirement

Per `DECISIONS.md` "2026-04-18 — Phase 5+ downstream analyses: preserve
per-(bodypart, center_mode) plotting parameters", the analysis config must
capture:

- Per-bodypart parameters (likelihood threshold for gating in spatial
  analysis, spatial filter range, baseline reference period).
- Per-center_mode parameters (axis limits, colormap scale, bin edges).
- Per-(bodypart, center_mode) combinations where the legacy notebooks used
  distinct settings — e.g., tongue with spout_midpoint centering likely has
  different axis limits than tongue with nose centering.

Proposed config shape (to be refined in plan mode):

```yaml
# configs/defaults.yaml — new section
dlc_spatial:
  default_bin_size_px: 2
  default_kde_bandwidth_px: 5
  bodyparts:
    tongue:
      likelihood_threshold: 0.9
      preferred_center_mode: "spout_midpoint"
      plot_params:
        nose:
          xlim: [-100, 100]
          ylim: [-80, 80]
          # ...
        spout_midpoint:
          xlim: [-50, 50]
          ylim: [-50, 50]
          # ...
    jaw:
      preferred_center_mode: "eye_midpoint"
      # ...
```

Adjust based on what the legacy notebooks actually use — the above is a
template, not a spec. Extract the real values from the legacy sources during
plan exploration.

### Stateless orchestrator (DECISIONS.md requirement)

Per `DECISIONS.md` "2026-04-18 — Phase 4 orchestrator: iterate over animals
without notebook restart", Phase 5's orchestrator must follow the same
pattern. The primary function `build_spatial_map(animal, date, bodypart,
center_mode, resolver, params) -> Path` is pure — no module-level state,
no globals, no implicit caches.

### Overwrite protection

Same pattern as Phase 4: `skip` / `force`. `prompt` is optional and not
required — outputs are deterministic from the centered parquets, so prompt
mode is lower-value. Document the choice in MIGRATION_LOG.

## Constraints

- No writes outside `~/Github/stroke_orofacial_pipeline/` except to
  `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/dlc_analysis/spatial_whole_session/`.
- Both legacy repos remain read-only.
- DLC inference outputs and camera data remain read-only.
- Phase 4's centered parquets in
  `pipeline_outputs_v2/dlc_analysis/centered_{mode}/` are **inputs**,
  read-only.
- Legacy figure outputs (PNGs, NPZs) from the legacy notebooks — if
  discovered on MICROSCOPE or local disk — are read-only parity references.
- Pre-commit hook must not be bypassed.
- Before every commit, `git branch --show-current` must print
  `phase-5-dlc-spatial`.

## Exit criteria

- Plan approved by Priya, sub-phases executed with per-sub-phase commits.
- Parity check demonstrates faithful port of the three analysis types
  (heatmap, pixel-bin, difference-map) on at least one real session
  (PS46/20250307 as the default exemplar — consistent with Phases 2-4).
- Per-(bodypart, center_mode) plotting parameters in `configs/defaults.yaml`
  cover all combinations the legacy notebooks used.
- Tests pass, lint clean.
- `docs/MIGRATION_LOG.md` Phase 5 entry documents all sub-phases, legacy
  disambiguation (including the `_nose` / `_jaw` sibling handling),
  dead-code classification results, and any intentional behavior differences.
- `docs/DECISIONS.md` gets new entries for any cross-cutting decisions made
  during Phase 5 execution.
- Pause after parity check (before tests+MIGRATION_LOG sub-phase) for
  Priya's mid-phase review, then again at the end before pushing for PR.

If legacy output artifacts are hard to find or the parity references are
ambiguous (e.g., the legacy notebooks only ever produced plots, never saved
array data), STOP and ask Priya how to structure the parity check. Visual
parity on PNGs is less rigorous than array equality — we may need to
synthesize a parity reference if one doesn't exist.

If any of the legacy notebooks overlap in scope (e.g., both 20251117 and
20260323 cells do similar heatmaps), apply the disambiguation rule carefully
and report the resolution. Ambiguity here propagates downstream.
