# Phase 7e.4 — dlc_spatial cleaned-traces routing (`use_v7_cleaned`)

**Status:** DRAFT — kickoff posted, awaiting Priya approval before any
production-code or test changes are written.
**Branch:** `phase/7e.4-spatial-cleaned-traces-routing`
**Worktree:** `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline-7e4`
**Branch point:** `cd9698f` (main at Phase 7e Stage 5 close, PR #145).

**Upstream driver:** F-P-1 v7 spatial-impact audit (PR #147 / chore branch
`chore/v7-spatial-impact-audit`). Verdict: 14/24 cells FAIL — all 12
tongue cells + 2 PS47 jaw tone-aligned cells. Recommended fix logged in
PR #147 comment.

---

## 1. The bug this phase fixes

Production `dlc_spatial` heatmap rendering filters DLC frames by per-bp
`likelihood_threshold = 0.80` only. The Phase 7e cleaned_traces cleanup
(merged via PRs #133/#137/#140/#141/#143/#144/#145) added a different
membership classifier — `is_baseline_fill` — that marks frames where the
bodypart was not detected, with a placeholder `y_final = 0.0`. Kinematic
consumers (mean_sem, lick1_y_peak, cumulative-y, tongue-jaw-mismatch)
were already routed to read cleaned_traces with NaN-masking on
`is_baseline_fill` via the same `use_v7_cleaned=True` kwarg pattern that
Phase 7e.1 / 7e.2 / 7e.3 introduced. Spatial consumers were left on the
legacy filter.

F-P-1 audit (Wasserstein-1, Wasserstein-2, KL on the 3 acute sessions ×
4 scopes × 2 bodyparts grid) showed the legacy filter mis-represents the
spatial distribution for tongue catastrophically (because tongue is
~99% baseline-fill at acute timepoints; R1 carries that mass on top of
the spout baseline pixels) and for jaw at small-mass tone-aligned
scopes on PS47 (mild). Verdict overall: **FAIL**.

The fix routes spatial through the same cleaned_traces filter as the
kinematic consumers: `~is_baseline_fill` becomes the membership mask;
per-bp likelihood gate is dropped.

---

## 2. Files touched (16 — > 5; CLAUDE.md plan-required threshold)

| file | role | est. LOC delta |
|---|---|---:|
| `src/stroke_orofacial/dlc_spatial/pixel_bins.py` | core filter chain | +25 / -2 |
| `src/stroke_orofacial/dlc_spatial/heatmaps.py` | `plot_heatmap` + `save_heatmap_npz` callers | +15 / -2 |
| `src/stroke_orofacial/dlc_spatial/tone_aligned.py` | `build_tone_aligned_analysis` caller | +20 / -2 |
| `src/stroke_orofacial/dlc_spatial/render_on_demand.py` | 40+ call sites; the heavy consumer | +60 / -10 |
| `src/stroke_orofacial/dlc_spatial/__init__.py` | re-exports if any new helper needs surfacing | +2 |
| `src/stroke_orofacial/dlc_kinematics/cleaned_traces_io.py` (NEW) | shared cleaned_traces baseline-fill loader (used by spatial AND already used implicitly by kinematics; refactor extraction) | +90 |
| `scripts/phase_7c2/reemit_cohort.py` | cohort driver — opt in `use_v7_cleaned=True` | +6 / -2 |
| `scripts/phase_7c1/reemit_pilot.py` | pilot driver | +6 / -2 |
| `scripts/phase_9_stats/materialize_spatial.py` | Phase 9 stats driver | +6 / -2 |
| `scripts/run_notebook_12_first_emit.py` | notebook 12 wrapper | +6 / -2 |
| `tests/test_pixel_bins.py` | unit tests for new filter path | +120 |
| `tests/test_heatmaps.py` | end-to-end at heatmap level | +60 |
| `tests/test_tone_aligned.py` | end-to-end at tone-aligned level | +60 |
| `tests/test_dlc_spatial_side_convention.py` | side-convention stays unchanged | +20 |
| `tests/test_materialize_spatial.py` | Phase 9 stats driver smoke test | +40 |
| `configs/defaults.yaml` | document `dlc_spatial.use_v7_cleaned` default + comment block | +15 |

Total: ~550 lines added / ~30 removed.

---

## 3. API design — `use_v7_cleaned` kwarg pattern

Pattern matches Phase 7e.1 / 7e.2 / 7e.3 same-class kinematic fix
(`mean_sem`, `tongue_jaw_mismatch`, `lick1_y_peak` all carry the same
flag). Default is **opt-in** (`False`) so a Phase 7e.4 merge does not
silently change existing outputs until a re-emit (Stage 5) runs.

### 3.1 `pixel_bins.get_masked_xy`

```python
def get_masked_xy(
    df: pd.DataFrame,
    bodypart: str,
    likelihood_threshold: float,
    x_range: tuple[float, float] | None = None,
    frame_mask: np.ndarray | None = None,
    *,
    baseline_fill_mask: np.ndarray | None = None,   # NEW
    drop_likelihood_gate: bool = False,             # NEW
) -> tuple[np.ndarray | None, np.ndarray | None]:
```

- `baseline_fill_mask` (length = len(df), bool): when not None, ANDed
  with the inverted mask (`~baseline_fill_mask`) into the row selector.
  Caller responsibility to align frame_idx 0..N-1 with df row index
  (cleaned_traces are dense per F-P-1 §3 verification).
- `drop_likelihood_gate=True`: skips the `lik >= likelihood_threshold`
  step. Other gates (finite x/y, frame_mask, x_range) still apply.

These two kwargs are *independent*: caller can pass only one of them.
The F-P-1 R3 variant uses both together; R2 uses only `baseline_fill_mask`.

### 3.2 `pixel_bins.build_histogram`

Adds passthrough kwargs `baseline_fill_mask` + `drop_likelihood_gate`,
forwards them to `get_masked_xy`. No other change.

### 3.3 `heatmaps.plot_heatmap` + `heatmaps.save_heatmap_npz`

Adds the same passthrough kwargs. `save_heatmap_npz` NPZ schema gains
two boolean scalar keys: `applied_cleaned_traces_mask` (true/false) and
`dropped_likelihood_gate` (true/false), stamped per the existing
`stamp_side_convention` pattern so downstream consumers can tell
which filter pipeline produced the NPZ.

### 3.4 `tone_aligned.build_tone_aligned_analysis`

Adds `use_v7_cleaned: bool = False`. When True:
- Loads `cleaned_trace(bodypart, animal, date)` parquet via
  PathResolver. Validates length matches the centered parquet (raises
  with a triage-friendly message if not).
- Extracts `is_baseline_fill` column as a bool array, passes to
  `build_histogram(baseline_fill_mask=..., drop_likelihood_gate=True)`.
- Stamps the result dict + NPZ with the two new flags.

When `use_v7_cleaned=False`, behavior is byte-identical to today.

### 3.5 `render_on_demand.*`

`compute_animal_aggregated_histogram` + `render_h_counts_panel` + the 6
high-level `render_*` functions all gain `use_v7_cleaned: bool = False`.
The per-session loader inside `compute_animal_aggregated_histogram` is
the cleaned-traces load point; it joins per (animal, date, bp) and
passes the mask into `build_histogram`. Per-bp call sites that loop over
multiple bps inside one function (composites; Pattern B) load each bp's
cleaned_traces once per session — N (bp) × M (sessions) parquet reads
per call.

### 3.6 NEW: `dlc_kinematics/cleaned_traces_io.py`

Extract the cleaned-traces-loading boilerplate that Phase 7e.1/7e.2/7e.3
re-implemented N times into one helper. Three functions:

```python
def load_baseline_fill_mask(
    bodypart: str, animal: str, date: dt.date,
    resolver: PathResolver, *, expected_n_frames: int,
) -> np.ndarray: ...

def load_cleaned_xy_with_nan_baseline(
    bodypart: str, animal: str, date: dt.date,
    resolver: PathResolver,
) -> pd.DataFrame: ...

def cleaned_traces_path_or_none(
    bodypart: str, animal: str, date: dt.date, resolver: PathResolver,
) -> Path | None: ...
```

The first is consumed by spatial (Stage 1-2). The second already exists
inline in Phase 7e.1 mean_sem code; extraction is opt-in to keep the
phase scope tight — defer to a follow-on cleanup phase if it widens
the diff too much.

---

## 4. Stage breakdown

### Stage 1 — `pixel_bins.py` + `heatmaps.py` + new `cleaned_traces_io.py` helper

Net ~150 LOC. Pure function changes; no driver coupling. New unit tests
in `test_pixel_bins.py`:
- `test_get_masked_xy_baseline_fill_mask_excludes_those_rows`
- `test_get_masked_xy_drop_likelihood_gate_admits_below_threshold`
- `test_get_masked_xy_combined_R3_variant_matches_F_P_1_audit`
- `test_get_masked_xy_baseline_mask_length_mismatch_raises`

Stage 1 ships as commit 1 on the branch.

### Stage 2 — `tone_aligned.py` + `render_on_demand.py`

Net ~80 LOC. Wire the new kwargs through ~46 call sites in
`render_on_demand.py`. Each call site is a 1-3 line passthrough
addition; the loader logic concentrates in
`compute_animal_aggregated_histogram` (~20 LOC for the per-session
cleaned-traces load + mask build).

New tests:
- `test_tone_aligned.py`: `test_build_tone_aligned_analysis_use_v7_cleaned_path`
- `test_heatmaps.py`: `test_plot_heatmap_use_v7_cleaned_matches_R3_audit_arrays`

Stage 2 ships as commit 2.

### Stage 3 — driver scripts

Net ~30 LOC. Each of the 4 driver scripts gains a CLI flag
`--use-v7-cleaned` (default False; opt-in until Stage 5 re-emit).

Stage 3 ships as commit 3.

### Stage 4 — parity tests against F-P-1 audit arrays

Pin the 24 R1 + 24 R3 `H_proportion` arrays from F-P-1 (the Wasserstein
inputs) as test fixtures (~1 MB total NPZ). Add
`test_phase_7e_4_parity.py` that recomputes them via the new
`use_v7_cleaned=True` path and asserts allclose at 1e-12 (no
numerical noise since both come from `np.histogram2d`).

Net ~80 LOC + ~1 MB fixture. Stage 4 ships as commit 4.

### Stage 5 — cohort re-emit to parallel `_cleaned_trace` subdir

Drives `scripts/phase_7c2/reemit_cohort.py --use-v7-cleaned` over the
8-animal cohort (PS46/47/48/49/50/51/54/55). **Per Priya 2026-05-27:
existing legacy outputs are NOT touched.** New outputs land in a
parallel `_cleaned_trace` subdirectory (see §4.5 Output-tree convention)
so the audit-trail of pre-7e.4 figures + stats stays browsable
indefinitely.

Manifest-tracked (`.scratch_phase_7e_4_reemit/`).

Gate (d): pre-emit + post-emit JSON snapshots of the same 3 acute
sessions × 4 scopes × 2 bodyparts that F-P-1 audited. Expected
distribution shift = exactly the F-P-1 audit's R3 vs R1 deltas.
Verdict-side check: comparing post-emit `_cleaned_trace` H_counts to
the F-P-1 R3 reference at `docs/audit_results/v7_spatial/` —
allclose at 1e-12 (same filter chain, same parquets).

Stage 5 ships as commit 5 with the gate (d) verdict committed.

### Stage 6 — Phase 7e.4 close + merge + tag

PR is taken off draft after Stage 5 gate (d) passes. Merge tag:
`v7e.4-spatial-cleaned-traces-routing` with message
`Phase 7e.4: spatial use_v7_cleaned routing (cleaned-traces baseline
mask + lik-gate drop)`.

Worktree torn down per CLAUDE.md Ground Rule 9 after merge.

---

## 4.5 Output-tree convention (per Priya 2026-05-27)

Legacy outputs stay where they are; cleaned-trace outputs land in a
parallel tree with a `_cleaned_trace` suffix on the leaf directory.
This keeps Phase 6 / 7c.2 figures + Phase 9 stats browsable as
"how production looked before 7e.4" indefinitely.

Resolver method names follow the existing pattern with a
`_cleaned_trace` suffix on the writer / reader:

| existing path / method | new parallel path / method |
|---|---|
| `pipeline_outputs/dlc_analysis/spatial_tone_aligned/...` (opt-in NPZ cache via `emit_cache=True`) | `.../spatial_tone_aligned_cleaned_trace/...` |
| `pipeline_outputs/dlc_analysis/spatial_whole_session/...` | `.../spatial_whole_session_cleaned_trace/...` |
| `pipeline_outputs/dlc_analysis/heatmaps/...` (PNG outputs) | `.../heatmaps_cleaned_trace/...` |
| `pipeline_outputs/phase_9_stats/spatial/...` | `.../spatial_cleaned_trace/...` |
| `resolver.spatial_tone_aligned_npz(...)` | `resolver.spatial_tone_aligned_npz_cleaned_trace(...)` (new) |
| `resolver.heatmap_png(...)` | `resolver.heatmap_png_cleaned_trace(...)` (new) |

Driver scripts route their writes based on the `--use-v7-cleaned` CLI
flag → `*_cleaned_trace` resolver methods. When `--use-v7-cleaned=False`
they continue to write to the legacy tree (no change).

The matching `cleaned_trace` suffix appears on Phase 9 stats outputs
+ figure outputs too — so a user browsing the spatial outputs sees
the legacy/cleaned_trace split at every level of the pipeline.
Figures and stats that mix bodyparts (e.g., tongue-jaw composites) get
the `_cleaned_trace` suffix when any input bp routed through the new
filter.

## 5. Parity strategy

Two parity guarantees:

1. **Legacy behavior preservation** — `use_v7_cleaned=False` (default)
   yields byte-identical `H_counts` arrays to pre-Phase-7e.4 code, for
   every call site. Stage 4 test fixture: pin the 24 R1 arrays from
   F-P-1; assert allclose at 1e-12.
2. **Audit verdict realization** — `use_v7_cleaned=True` yields
   byte-identical `H_counts` arrays to the F-P-1 audit's R3 variant
   (where R3 = drop lik gate + apply `~is_baseline_fill` mask). Same
   pinned fixture, opposite assertion.

Parity is tested at the `H_counts` array level (not the rendered
PNG level) because:
- PNGs add LogNorm / cmap / DPI sources of non-determinism.
- Phase 9 stats consume `H_counts` (via NPZ); parity at this level is
  what gives downstream confidence.

---

## 6. Hardcoded constants — none move

This phase adds two boolean kwargs; no new numeric thresholds, no
config-level constants worth surfacing. The `likelihood_threshold = 0.8`
that the new path SKIPS continues to live in the per-bp config block
for backward-compat callers that pass `use_v7_cleaned=False`.

---

## 7. Out of scope (intentional)

- **Whisker / fiducial composites (Pattern B).** F-P-1 audited only
  tongue + jaw because Phase 7e cleanup applies only to those. Other
  bodyparts' Pattern B renders stay on the legacy lik gate. If a future
  audit shows a similar bug there, that's a separate phase.
- **Phase 4 centered parquet re-emit.** The centered parquets are
  unchanged inputs; this phase reads them as-is.
- **PNG output schema** (axis limits, cmap, DPI). Stays as-is.
- **Stats grid (`build_stats_grid`)** under cleaned-traces routing.
  Same filter chain underneath, so the parity carries over; explicitly
  testing it can be a Stage 4 add-on if Priya requests.
- **`cleaned_traces_io.py` extraction of mean_sem / lick1 / etc.
  cleaned-traces loaders.** The new file lands with one function used
  by spatial; backfilling the kinematic loaders is a separate cleanup.

---

## 8. Inputs needed from Priya before Stage 1 starts

Q1. **API approval** — `use_v7_cleaned` kwarg pattern (Section 3) vs.
   alternative (e.g., enum-typed `SpatialFilterMode`).
   **→ proposed default: kwarg pattern (matches Phase 7e.1/7e.2/7e.3
   precedent).**
Q2. **Default value** — `use_v7_cleaned=False` (opt-in; recommended for
   merge safety) vs. `True` (production switches immediately on merge).
   **→ proposed default: `False` for source-level functions; driver
   scripts (`reemit_cohort.py` etc.) expose `--use-v7-cleaned` as a CLI
   flag with no default flip on merge.**
Q3. **Re-emit scope (Stage 5)** — given the parallel `_cleaned_trace`
   tree (no legacy overwrite per §4.5), the scope expansion is cheap:
   - **(a)** tongue + jaw only (matches F-P-1 audit scope; smallest disk
     footprint)
   - **(b)** tongue + jaw + nose (3 single-bp families; modest footprint)
   - **(c)** all bodyparts (tongue + jaw + nose + fiducial pairs +
     whisker composites); fiducials + whiskers run through the same
     filter chain but Phase 7e cleanup applies only to tongue + jaw, so
     for non-tongue/jaw bps the `~is_baseline_fill` mask is a no-op (no
     cleaned_traces parquet exists → mask=all-False → audit-equivalent
     output)
   **→ proposed default: (a) tongue + jaw.** Spending disk on (b)/(c)
   only makes sense if you expect to compare layouts side-by-side.
Q4. **Re-emit timing** — Stage 5 runs immediately after Stage 4 merges,
   or held until Priya kicks off via separate `--use-v7-cleaned` driver
   invocation.
   **→ proposed default: immediate post-Stage-4 (continuous within this
   phase) so the gate (d) verdict closes 7e.4 cleanly.**

Priya confirmed §4.5 (parallel `_cleaned_trace` tree; no legacy overwrite)
on 2026-05-27.

No production-code or test changes are written until Q1-Q4 are pinned.

---

## 9. Exhaustive consumer enumeration (Priya 2026-05-27 EXTRA REQUEST)

Grep result from `from stroke_orofacial.dlc_spatial` across `src/` +
`scripts/` + `tests/` + `notebooks/`. Each consumer classified by what
it imports and whether routing is required.

### 9.1 Spatial-internal modules (filter logic lives here — ROUTE)

| consumer | symbols imported | routing change |
|---|---|---|
| `src/stroke_orofacial/dlc_spatial/pixel_bins.py` | (defines `get_masked_xy`, `build_histogram`, `build_stats_grid`, `build_baseline_histogram`) | **Stage 1.** Add `baseline_fill_mask` + `drop_likelihood_gate` kwargs to `get_masked_xy`; passthrough on `build_histogram`/`build_stats_grid`/`build_baseline_histogram` |
| `src/stroke_orofacial/dlc_spatial/heatmaps.py` | `_get_per_center_mode_params`, `build_histogram`, `get_masked_xy` | **Stage 1.** `plot_heatmap` + `save_heatmap_npz` gain `baseline_fill_mask` + `drop_likelihood_gate` kwargs (low-level pass-through, no default-True because they don't load cleaned_traces themselves) |
| `src/stroke_orofacial/dlc_spatial/tone_aligned.py` | `build_histogram` (line 382) | **Stage 2.** `build_tone_aligned_analysis(use_v7_cleaned=True)` default; loads cleaned_traces from (manifest.animal, manifest.date, bodypart) and forwards the mask. `build_tone_aligned_analysis_by_animal_date(use_v7_cleaned=True)` mirror default. NPZ schema gains `applied_cleaned_traces_mask` + `dropped_likelihood_gate` keys |
| `src/stroke_orofacial/dlc_spatial/render_on_demand.py` | `_get_per_center_mode_params`, `build_histogram`, `build_tone_aligned_window`, `load_tone_events` | **Stage 2.** `compute_animal_aggregated_histogram(use_v7_cleaned=True)` default; loads per-session cleaned_traces. All 7 public `render_*` entry points gain `use_v7_cleaned=True` default passthrough. ~46 internal call sites get the mask passed through |
| `src/stroke_orofacial/dlc_spatial/difference_maps.py` | (none from spatial filter chain) | **No change.** Consumes pre-computed `H_counts` arrays; inherits filter via upstream callers |

### 9.2 Production driver scripts (output emitters — ROUTE + path)

| consumer | imports | routing change |
|---|---|---|
| `scripts/phase_7c2/reemit_cohort.py` | (per Section 2 — Phase 7c.2 cohort entry) | **Stage 3.** `--use-v7-cleaned` CLI flag default True; routes writes to resolver's `*_cleaned_trace()` path methods when True |
| `scripts/phase_7c2/render_heatmaps.py` (NEW finding) | `derive_log_norm_range`, `derive_symmetric_diff_vmax`, `derive_uot_bucket_ranges`, `precompute_individual_session_h_proportions`, `precompute_binned_sessions_h_proportions` from render_on_demand | **Stage 3.** Same `--use-v7-cleaned` CLI + path routing. Calls the pre-compute helpers; routing flows through `compute_animal_aggregated_histogram`'s default-True |
| `scripts/phase_7c1/reemit_pilot.py` | `build_tone_aligned_analysis_by_animal_date`, `save_tone_aligned_npz` | **Stage 3.** Same CLI + path routing |
| `scripts/phase_9_stats/materialize_spatial.py` | `compute_animal_aggregated_histogram`, `TASK5_TONE_WINDOW_MS`, `_resolve_family_entry`, `_split_pre_post_dates` | **Stage 3.** Same CLI + path routing. Phase 9 stats land in `pipeline_outputs/phase_9_stats/spatial_cleaned_trace/` by default |
| `scripts/run_notebook_12_first_emit.py` | `build_tone_aligned_analysis`, `save_tone_aligned_npz` | **Stage 3.** Same CLI + path routing |

### 9.3 Kinematic modules importing spatial (utility-only — NO ROUTING)

These import `load_tone_events` / `ws_samples_to_frame_indices` —
pure utility helpers that read tone events from the Phase 2 NPZ and
convert WS samples to camera frames. **Zero semantic interaction with
the bp-level filter chain**; routing is irrelevant here.

| consumer | imports | rationale |
|---|---|---|
| `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` | `load_tone_events`, `ws_samples_to_frame_indices` | Phase 7e.1 consumer; already on cleaned_traces via `use_v7_cleaned=True` on its own surface (kinematic side). Spatial-side imports here are for tone-window construction, NOT bp histogram filtering |
| `src/stroke_orofacial/dlc_kinematics/interpolation.py` | `load_tone_events` | Used to slice tone windows during interpolation; not a spatial-filter call site |
| `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` | `load_tone_events`, `ws_samples_to_frame_indices` | Same — tone-window helpers only |

### 9.4 Experimental notebooks (private; no routing)

| consumer | imports | rationale |
|---|---|---|
| `notebooks/experiments/q65_pd_comparison.py` | `TASK5_TONE_WINDOW_MS`, `_build_tone_window`, `_ws_cam_frame_bounds` | Constants + private window helpers. Notebook has its OWN local `_build_histogram` at line 246 (independent of `dlc_spatial.pixel_bins`). Stays on legacy semantics |
| `notebooks/experiments/per_bin_numeric_comparison.py` | same | Same — exploratory notebook, no production output writes |
| `notebooks/experiments/per_bin_numeric_comparison_pre_stroke.py` | same | Same |

### 9.5 Tests (mirror routing of their target)

| consumer | imports | routing change |
|---|---|---|
| `tests/test_pixel_bins.py` | `_get_per_center_mode_params`, `build_baseline_histogram`, `build_histogram`, `build_stats_grid`, `get_masked_xy` | **Stage 4.** New tests for `baseline_fill_mask` + `drop_likelihood_gate` kwarg paths; existing legacy assertions stay valid (low-level functions still default to legacy when mask=None) |
| `tests/test_heatmaps.py` | `plot_heatmap`, `save_heatmap_npz`, `save_heatmap_png`, `build_histogram` | **Stage 4.** Mirror — new tests for the new kwargs |
| `tests/test_tone_aligned.py` | `load_tone_events`, `ws_samples_to_frame_indices` + dynamic imports of `build_tone_aligned_analysis`, `build_tone_aligned_analysis_by_animal_date` | **Stage 4.** Existing default-checking assertions (`emit_cache=False` at line 294) need a parallel `use_v7_cleaned=True` default check. New tests for the routing path. **CAUTION:** `assert sig.parameters["emit_cache"].default is False` style assertions will fail if I get the default wrong — update lockstep with source |
| `tests/test_dlc_spatial_side_convention.py` | `build_tone_aligned_analysis`, `build_tone_aligned_analysis_by_animal_date`, `save_tone_aligned_npz` | **Stage 4 (audit).** Stamps `wavesurfer_sides_match_mouse_sides`; routing only matters if the new path stamps differ. Recommend adding a smoke test that the new path still stamps correctly |
| `tests/test_difference_maps.py` | `compute_difference_map`, `plot_difference_map`, `save_difference_map_png` | **No change** (consumes pre-computed `H_counts`) |
| `tests/test_materialize_spatial.py` | (Phase 9 stats driver smoke) | **Stage 4.** Smoke test the new path-routing in the driver — CLI flag flips output path |
| `tests/test_window_selector.py` | `EventAlignedWindow`, `ToneAlignedWindow`, `WholeSessionWindow`, `_ws_to_cam_frames` | **No change** (pure window selectors, no filter) |
| `tests/test_notebook_runners.py` | (referenced in Section 2) | **Verify only** — likely no change; smoke-test the runner script flag |
| `tests/test_manifest_multi_half.py` | (referenced in Section 2) | **No change** (manifest tests) |
| `tests/test_tongue_pertrial.py` | mocks `stroke_orofacial.dlc_spatial.tone_aligned` (line 1893) | **No change** — mock-only, the mock target string stays stable |
| `tests/test_config_loader.py` | (referenced in Section 2) | **No change** — config schema tests |

### 9.6 Total source/test file impact (updated count)

Initial Section 2 estimate: 16 files. Section 9 enumeration revealed **2
additional consumers** (`scripts/phase_7c2/render_heatmaps.py` and
`src/stroke_orofacial/dlc_spatial/difference_maps.py`), bringing the
production-side consumer count to 9 (up from 8 in Section 2).
`difference_maps.py` is no-op (consumes downstream of the filter), so
the actual source-edit count is 9 production files (4 spatial modules +
5 driver scripts) + 7 affected test files. Section 2 line-count
estimates remain valid.

**The 3 kinematic-module imports and 3 experiment-notebook imports are
verified no-ops for routing — they only consume `load_tone_events` /
`ws_samples_to_frame_indices` / constants / private window helpers,
none of which are part of the bp-level filter chain.**

## 10. Addenda

### Addendum #4 — corrected mechanism (post-Stage-5, 2026-05-27)

User flagged during Stage 5 cohort burn that the PS46 tone-aligned-all
proportion_diff "cleaned" heatmap looked NOISIER than the legacy. Initial
hypothesis ("y=0 baseline-fill mass distorts legacy") was investigated
via a per-mode census at production parameters
(`lik >= 0.5`, `x_range = [-150, 150]` for tongue_spout_midpoint).

**Original framing in §1 + F-P-1 audit verdict — INCOMPLETE:**

> "Production filters by per-bp lik >= 0.80; the v7 cleaned_traces
> cleanup added is_baseline_fill which marks frames where the bodypart
> was not detected with placeholder y_final=0.0."

The §1 framing called out lik=0.80, but production tongue + jaw actually
use lik=0.50 (per `dlc_spatial_tone_aligned.families`). At lik=0.50,
the contamination story is more nuanced.

**Census at correct production parameters:**

| session | label | legacy admits | cleaned admits | bf-with-lik≥0.5 | interp_fill-with-lik<0.5 |
|---|---|---:|---:|---:|---:|
| PS46 2025-03-07 | moderate, pre | 98,739 | 111,404 | 518 | 13,183 |
| PS46 2025-03-25 | moderate, post | 109,357 | 127,566 | 597 | 18,806 |
| PS54 2025-04-21 | severe, pre | 56,663 | 81,797 | 2,127 | 27,261 |
| **PS54 2025-05-06** | **severe, F-P-1 acute** | **9,362** | **7,470** | **3,184** | **1,292** |
| PS54 2025-06-13 | severe, chronic | 50,699 | 62,874 | 324 | 12,499 |

**Two regimes, two different effects:**

1. **Typical sessions (most of cohort, including all PS46 + non-acute
   PS54):** baseline-fill contamination is small (<1% of legacy frames).
   The cleaned-vs-legacy R3 vs R1 difference is dominated by the
   `is_interp_fill=True` frames where DLC lik<0.5 but the cleanup
   pipeline imputed x/y via short-gap interpolation from confident
   neighbors. Cleaned admits ~1.1-1.4× more frames than legacy,
   adding the interpolated trajectory between high-confidence
   detections. The "noisier" cleaned PD on PS46 = the interp_fill tail
   adding mass to bins that legacy left empty. **Feature, not bug.**

2. **Extreme-deficit sessions (e.g. PS54 2025-05-06 acute, 99.17%
   baseline_fill):** baseline-fill contamination IS material. Legacy
   includes 3,184 bf frames at lik>=0.5 out of 9,362 admitted = 34%
   bf contamination. Cleaned excludes them, leaving 7,470 real-only
   frames. **F-P-1's "baseline-fill mass distorts legacy" framing
   applies HERE specifically** — these are the cases where the audit
   measured W2=111.79 (PS54 tongue tone_R).

**Why R3 (drop lik gate) is still correct:**

The cleaned_traces pipeline ALREADY applies `lik >= 0.5` as part of its
is-real classification. **Every** original-DLC-detection row
(`is_interp_fill=False, is_baseline_fill=False`) has `likelihood_raw >=
0.50` — verified across 5 test sessions on both tongue + jaw, zero
exceptions.

Frames classified by cleaned_traces as `is_interp_fill=True` have
`likelihood_raw < 0.50` BUT carry valid imputed x/y values from short-
gap interpolation. Re-applying the lik gate in spatial (the R2 hybrid)
would WRONGLY exclude those legitimate interpolated positions.

R3 (drop lik gate + apply `~is_baseline_fill`) is correct because:
- The cleaned_traces pipeline already validated `lik >= 0.5` upstream
  for is-real classification
- Cleaned admits both DLC-confident detections AND short-gap
  interpolated imputations
- Excluding interp_fill frames would discard the dense trajectory
  between confident detections

**Implication for downstream paper figures:**

The cleaned_trace cohort outputs at
`dlc_kinematics/<tree>_cleaned_trace/` contain:
- The DLC-confident detections (lik>=0.5, also in legacy)
- The interpolated imputations (interp_fill=True, NOT in legacy)
- NOT the placeholder mass (is_baseline_fill=True, excluded)

This is a slightly different population from "legacy with bf removed"
(R2 hybrid). Downstream consumers (Q-lock 12 phenotype-pooled
proportion_diff figures) should understand they're seeing the
interpolated-trajectory-augmented distribution, not just the lik-gate-
filtered detection distribution.

**No code or path changes — the routing is correct.** This addendum
records the corrected mechanism understanding so future readers
(including the Q-lock 12 implementer) don't inherit the §1 / F-P-1
"y=0 baseline-fill mass" framing as the only mechanism.

### Addendum #3 — proportion_diff family confirmed in scope + path convention locked to `dlc_kinematics/` (Priya 2026-05-27)

**Scope confirmation (Priya 2026-05-27 question):** The Phase 7c.2
cohort-level proportion_diff figure family IS in Phase 7e.4 scope —
implicitly via the §9.2 consumer enumeration entry
`scripts/phase_7c2/render_heatmaps.py`, which imports
`precompute_proportion_diffs` from `render_on_demand` along with
`precompute_individual_session_h_proportions` and
`precompute_binned_sessions_h_proportions`. All three precompute
helpers cascade through `compute_animal_aggregated_histogram`'s
default-True (Stage 2 commit `03d3f33`), so any driver invocation of
`render_heatmaps.py` after Stage 3 wiring will re-emit ALL of
{individual_session, binned_sessions, proportion_diff} families to
`_cleaned_trace` paths in lockstep.

Paper-relevance + Q-lock 12 (Phase 9.1 phenotype-pooled
proportion_diff, 80 figures) gating both reinforce that this family
must close cleanly in 7e.4. Now explicit in Stage 5 verdict criteria:

- Stage 5 cohort re-emit MUST produce non-empty `_cleaned_trace`
  outputs for all 3 family entries × all bp scopes (tongue + jaw)
  the proportion_diff plot type renders.

**Path convention locked (resolves Addendum #2 open question):** the
new cleaned_trace spatial outputs land under `dlc_kinematics/` (NOT
the `dlc_analysis/` family that Phase 7c.2 / Phase 9 legacy outputs
live under). Priya's 2026-05-27 path hint
(`pipeline_outputs/dlc_kinematics/proportion_diff_cleaned_trace/`)
matches the same prefix as Q-lock 12's compute-source
(`dlc_kinematics/tone_aligned_heatmaps_cleaned_trace/`).

Stage 3 resolver methods land at:

| artifact | new resolver method | output path |
|---|---|---|
| tone-aligned heatmap NPZ | `tone_aligned_heatmap_npz_cleaned_trace(...)` | `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps_cleaned_trace/{bp}_{cm}/trials-{tg}_{win}/{animal}/heatmap_{date}_cleaned_trace.npz` |
| whole-session heatmap NPZ | `whole_session_heatmap_npz_cleaned_trace(...)` | `pipeline_outputs/dlc_kinematics/whole_session_heatmaps_cleaned_trace/{bp}_{cm}/{animal}/heatmap_{date}_cleaned_trace.npz` |
| individual-session heatmap PNG | `individual_session_heatmap_png_cleaned_trace(...)` | `pipeline_outputs/dlc_kinematics/individual_session_heatmaps_cleaned_trace/{family}_{scope}/{animal}/heatmap_{date}_cleaned_trace.png` |
| binned-sessions heatmap PNG | `binned_sessions_heatmap_png_cleaned_trace(...)` | `pipeline_outputs/dlc_kinematics/binned_sessions_heatmaps_cleaned_trace/{family}_{scope}_{bin_size}d/{animal}/heatmap_{rel_day_bin}_cleaned_trace.png` |
| proportion_diff heatmap PNG | `proportion_diff_heatmap_png_cleaned_trace(...)` | `pipeline_outputs/dlc_kinematics/proportion_diff_cleaned_trace/{family}_{scope}_{bin_size}d/{animal}/diff_{rel_day_bin}_cleaned_trace.png` |
| Phase 9 stats output | `phase_9_stats_spatial_cleaned_trace(...)` | `pipeline_outputs/phase_9_stats/spatial_cleaned_trace/...` |

Filename includes `_cleaned_trace` per Q-lock 15.2 (so a misplaced
file outside its `_cleaned_trace/` directory still self-identifies).
Subtitle/footer per Q-lock 15.3 — implemented in the
`scripts/phase_7c2/render_heatmaps.py` figure-render call path.

Legacy paths (no `_cleaned_trace` suffix on directory or filename)
remain on disk untouched as the historical audit trail.

### Addendum #2 — Q-lock 15 cleaned_trace marker convention applied (Priya 2026-05-26 amendment)

Priya's 2026-05-26 evening directive (Phase 9.1 trajectory expansion +
cleaned_trace marker convention) added three new locks that Phase 7e.4
must honor on its output side because Q-lock 12 (phenotype-pooled
proportion_diff figures, 80 figures) gates on Phase 7e.4 close and
consumes 7e.4's outputs as input.

**Q-lock 15 marker convention** (binding on Phase 7e.4 Stage 3 + 5):

1. **Directory-level:** outputs land at `..._cleaned_trace/` suffixed
   paths (already aligned with §4.5).
2. **Filename:** every emitted artifact (PNG, NPZ, CSV) must include
   the `_cleaned_trace` token in its filename — not just the
   directory. Example:
   - PNG: `heatmap_PS54_20250506_tongue_spout_midpoint_tone_all_cleaned_trace.png`
     (NOT `heatmap_PS54_20250506_tongue_spout_midpoint_tone_all.png`
     under a `_cleaned_trace/` directory)
   - NPZ: `heatmap_PS54_20250506_..._cleaned_trace.npz`
3. **Figure subtitle/footer:** suptitle suffix or right-bottom-corner
   annotation reading literally: `"Source: v7-cleaned-trace cohort
   re-emit (Phase 7e + Phase 7e.4)"`. Survives PDF/paper export so
   downstream readers can trace provenance from the figure alone.

Stage 3 implementation impact:
- Resolver `*_cleaned_trace()` methods (already in §4.5) build paths
  with the `_cleaned_trace` suffix on the directory **and** prepend
  the token to the filename slug.
- Driver scripts (`scripts/phase_7c2/render_heatmaps.py`,
  `scripts/phase_7c2/reemit_cohort.py`) pass the routing flag to the
  figure renderer, which appends the §15.3 footer to every figure.
- For figures that mix tongue+jaw (composites), `_cleaned_trace`
  applies when **any** input bp routed through the new filter — i.e.,
  always for tongue+jaw composites in Phase 7e.4's scope.

**Q-lock 12 gating** (informational; not binding on 7e.4 source code):
- Phase 9.1's Q-lock 12 (80 phenotype-pooled proportion_diff figures)
  consumes the cleaned_trace NPZ tree that Stage 5 emits.
- Compute-source path per Q-lock 12: `pipeline_outputs/
  dlc_kinematics/tone_aligned_heatmaps_cleaned_trace/`.
- **Open question RESOLVED in Addendum #3:** option (b) — Phase 7e.4
  writes to `dlc_kinematics/<artifact>_cleaned_trace/` paths.

### Addendum #1 — Section 8 inputs locked (Priya, 2026-05-27)

| input | locked value | note |
|---|---|---|
| Q1 API pattern | **APPROVED — `use_v7_cleaned` kwarg, Phase 7e.X precedent** | matches 7e.1/7e.2/7e.3 |
| Q2 default value | **PUSHBACK — default `True` (NOT False)** | Cowork rationale: default-False is the exact shape that caused the 7e.1/7e.2/7e.3/F-P-1 cascade; F-P-1 validated v7 is material on both bodyparts + has a clean severity gradient; conservative-default-False is moot. Default True ensures downstream consumers auto-pick-up v7 unless explicitly opted out. Parallel-outputs preservation per §4.5 is still on (defensive A/B) but consumer defaults point to v7 |
| Q3 re-emit scope | **APPROVED (a) — tongue + jaw only** | Only option that's possible: nose/whiskers don't have cleaned_traces yet. If a future audit finds nose impact, queue as Phase 7g forward-pointer |
| Q4 re-emit timing | **APPROVED — immediate post-Stage-4, continuous within phase** | Gate (d) closes 7e.4 cleanly |
| §8 EXTRA REQUEST | **DONE — see §9 exhaustive consumer enumeration** | 2 new consumers discovered (`render_heatmaps.py` + `difference_maps.py`); 3 kinematic + 3 notebook imports verified no-op |

**Default-True implication (revised from §3 / §4.5):**

- Low-level pure functions (`pixel_bins.get_masked_xy`,
  `pixel_bins.build_histogram`, `heatmaps.plot_heatmap`,
  `heatmaps.save_heatmap_npz`) cannot default to True at the API level
  because they don't have access to (animal, date, bp) tuples needed
  to load cleaned_traces. They take `baseline_fill_mask=None` +
  `drop_likelihood_gate=False` as **caller-supplied inputs**;
  default behavior is byte-identical to legacy when mask=None.
- High-level functions that DO have (animal, date, bp) resolution
  (`tone_aligned.build_tone_aligned_analysis`,
  `render_on_demand.compute_animal_aggregated_histogram`, all 7 public
  `render_*` entry points) get `use_v7_cleaned=True` default and
  internally load cleaned_traces.
- Driver scripts get `--use-v7-cleaned` CLI flag, default True; flag
  determines both the source-level kwarg AND the output path
  (legacy vs `_cleaned_trace`).
- Stage 4 parity test `test_phase_7e_4_parity.py` exercises BOTH paths:
  default True must match F-P-1 R3 arrays; explicit False must match
  F-P-1 R1 arrays (=current production).

§8 inputs locked; Stage 1 can begin.
