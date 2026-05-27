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

## 9. Addenda

(none yet — Addendum #1 will record Priya's Section 8 answers)
