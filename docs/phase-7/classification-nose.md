# Classification: 20251117_DLC_analysis_nose.ipynb

Companion to `docs/phase-7/notebook-structure-nose.md`. Produced during
Phase 7 sub-phase 7.0b for the dead-code classification requirement in
CLAUDE.md §"Phase plan requirements." Same format as
`docs/phase-7/classification-tongue.md`,
`docs/phase-7/classification-jaw.md`,
`docs/phase-7/classification-whiskers.md`, and
`docs/phase-7/classification-pixelbin.md`.

Source: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20251117_DLC_analysis_nose.ipynb`
(98 KB, 17 cells: 9 code, 8 markdown). This is the **smallest of the
five Phase 7 reference notebooks** and the last to be classified in the
7.0b sequence.

## Labels

Per CLAUDE.md:

* **Production** — the cell's output feeds a downstream module or one of
  Priya's final analysis outputs. These are the cells the new repo ports.
* **Exploratory** — data inspection, debugging, one-off troubleshooting,
  plot-only cells, and commented-out historical code. Not ported as a
  unit; specific utilities inside may be lifted selectively.
* **Deprecated** — an older version superseded by another cell later in
  the same notebook or by another canonical notebook.
* **Ambiguous** — preview not sufficient to resolve; full source pulled
  into `outputs/nose_dump_prod.txt` for a second pass. Every Ambiguous
  entry below has since been resolved.

For every **Production** cell, port-surface extraction records:
**algorithm (1 sentence) → inputs → outputs → sub-phase owner → port
approach**.

## Scope scoping — nose is a Phase 5 notebook, not a Phase 7 one

Like `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`, this
notebook contains **no Phase 7 port surface**. Its analytical content
is entirely about nose spatial-occupancy maps (per-session, binned, Δ
vs pre-stroke) — Phase 5 territory that is already ported or scheduled
under the Phase 5.x mini kickoff.

What's explicitly **absent** from this notebook versus tongue / jaw /
whisker:

* **No interpolation cell.** Nose uses the raw Phase 4.5 centered
  parquet directly. There is no nose analog of tongue Cell 23 / jaw
  Cell 22 / whisker Cell 25 v5p3. Consequently **nothing in this
  notebook is a 7a port target**.
* **No per-trial endpoint cells.** There is no first-lick detector,
  no peak-velocity cell, no lick-rate cell, no bout-ILI cell, no
  trial-aligned mean-X/Y cell. Consequently **nothing is a 7b or 7c
  port target**. (Consistent with the Q6 locked endpoint list in the
  kickoff doc, which does **not** include any nose-specific kinematic
  endpoints — nose participates only in the 7d face-velocity PSD
  cohort as one of several bodyparts.)
* **No PSD cell.** Unlike tongue Cells 62/64 and jaw Cell 43, the
  nose notebook has zero PSD content. The `scipy.signal.welch/
  spectrogram` imports in Cell 1 are inherited from the shared
  template and not used here. Consequently **nothing is a 7d port
  target** in this notebook — the nose trace's contribution to 7d
  will be computed in 7d from the Phase 4.5 centered parquet
  directly (same mechanism as jaw + the 6 whiskers).
* **No trial-window cells.** Nothing for 7e either.
* **No alignment-template or lick-file merge cells.** The nose
  notebook doesn't host the multi-video-per-session merge cells that
  tongue / jaw / whisker do (those sit in tongue Cell 13 / jaw Cell
  13 / whisker Cell 13 as Production → Phase-3/Phase-2/Phase-4
  extensions). Nose relies on Phase 4.5's cache having already merged
  multi-video sessions, which is the correct layering. **Nothing
  pre-7a is sourced from this notebook.**

**Zero cells in this notebook are Phase-7 port targets.** Production
cells below all have out-of-Phase-7 owners (Phase 4.5 — already ported
— or Phase 5 — already ported — or Phase 5.x mini — not yet ported).
The summary table's category labels describe each cell's role within
*its own* scheduled phase, not Phase 7 specifically.

## Summary

| Label                                                 | Code cells | Indices                    |
|-------------------------------------------------------|------------|----------------------------|
| Production(Phase 4.5, already ported)                  | 2          | 6, 8                       |
| Production(Phase 5, already ported — see notes)        | 2          | 11, 15                     |
| Production(Phase 5.x mini, not yet ported)             | 1          | 13                         |
| Exploratory                                            | 4          | 1, 3, 4, 16                |
| Deprecated                                             | 0          | —                          |
| Ambiguous                                              | 0          | (all resolved)             |

Cross-check against the sub-phase breakdown in
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`:

| Sub-phase | Owned cells (nose notebook)                         |
|-----------|------------------------------------------------------|
| 7a        | —                                                    |
| 7b        | —                                                    |
| 7c        | —                                                    |
| 7d        | — (no PSD in this notebook; 7d reads nose_x/nose_y   |
|           |   straight from the Phase 4.5 centered parquet)      |
| 7e        | —                                                    |
| Data repair (pre-7a) | —                                         |

**Nose contributes nothing to Phase 7.** Its content is already split
across Phase 4.5 (already ported: cells 6, 8), Phase 5 (already
ported: cells 11, 15 — per-bodypart heatmap + Δ map), and Phase 5.x
mini (cell 13 — binned overlay, subsumed by pixelbin cell 13's
multi-bodypart canonical).

## Cross-reference with pixelbin classification

The nose notebook is, structurally, a **single-bodypart precursor of
the pixelbin notebook**. Each of its three analytical cells has a
multi-bodypart canonical in pixelbin:

| Nose cell | Pixelbin cell | Canonical status                                  |
|-----------|---------------|----------------------------------------------------|
| 11 (per-session) | 11 (per-session × 9 bodyparts) | Pixelbin version is the Phase 5.x mini canonical for overlay; single-bodypart case is already ported as `dlc_spatial.heatmaps.plot_heatmap()`. |
| 13 (binned by rel_day) | 13 (binned × 9 bodyparts)      | Pixelbin version is the Phase 5.x mini canonical; nose cell 13 is the single-bodypart variant — subsumed when the mini's `plot_all_bodyparts_heatmap_binned(..., bodyparts=["nose"])` ships. |
| 15 (Δ vs pre-stroke) | 15 (Δ × 9 bodyparts)          | Pixelbin version is the Phase 5.x mini canonical; `difference_maps.compute_difference_map()` + `plot_difference_map()` is the per-bodypart primitive, already ported. |

This is why `dlc_spatial/heatmaps.py` and `dlc_spatial/difference_maps.py`
cite **both** the nose notebook and the pixelbin notebook in their
docstrings: they were consolidated from the two sources into one
parameterized module during Phase 5.

---

## Cell-by-cell classification

### Cell 0 — markdown
Header: `# Import packages`. Not classified.

### Cell 1 — code (29 lines) — Exploratory
Top-of-notebook imports: `os`, `sys`, `pandas`, `numpy`, `matplotlib`
(+ `gridspec`, `Slider`), `scipy.signal.welch/spectrogram`, optional
`scicomap` with `get_afmhot_like()` fallback. Identical shape to
pixelbin Cell 1. **`scipy.signal.welch`/`spectrogram` are unused** in
this notebook — inherited from the shared template; no nose-PSD code
exists here. Module preludes in `stroke_orofacial.dlc_spatial.*` ship
the actually-used imports per-module. No port.

### Cell 2 — markdown
Header: `# Load files and appoint labels`. Not classified.

### Cell 3 — code (63 lines) — Exploratory
`folder_path` discovery with a hard-coded UNC path
(`r"\\research.files.med.harvard.edu\...\PS49"`), optional
`*filtered_5s/86s.{csv|h5}` variants, and `fs = 250` (**correct** —
matches the canonical 250 Hz camera rate, no fs=150 bug like the
whisker notebook). Fully superseded by `PathResolver` +
`SessionManifest` + `animals.yaml` discovery in Phase 6.7. No port.

### Cell 4 — code (47 lines) — Exploratory
Builds `{basename: "ANIMAL M/D"}` label map via `video2_YYYY-MM-DD`
regex. Hard-coded `animal = "PS49"`. Fully superseded by
`SessionManifest` (`animal`, `session_date`, `session_key`,
`display_label`). No port.

### Cell 5 — markdown
Header: `# Load parquet files`. Not classified.

### Cell 6 — code (107 lines) — Production(Phase 4.5, already ported)
**Algorithm (1 sentence):** Signature-gated parquet-cache loader —
given `CENTER_MODE = "eye_midpoint"` (nose uses the eye-midpoint
reference, same as jaw) and `CENTER_LIK_THR = 0.70`, computes the
expected MD5-derived 8-char signature, globs
`<basename>.intermediate.<sig>.parquet` files under
`<folder_path>/_dlc_cache_centered_<CENTER_MODE>/`, picks matching /
override / newest files, and populates
`intermediate_data_frames[full_csv_path] -> DataFrame`.

**Inputs:** `folder_path`, `CENTER_MODE`, `CENTER_LIK_THR`, optional
`SIGNATURE_OVERRIDE` / `REQUIRE_EXPECTED_SIG`, and
`MAX_FRAMES_PER_VIDEO = 975000` cap.

**Outputs:** in-memory `intermediate_data_frames` dict; no files
written.

**Sub-phase owner:** Already owned by Phase 4.5
(`dlc_centering/cache.py`); consumed via
`PathResolver.centered_parquet_path(mode, lk_thr)` in Phase 5/6. This
cell is the notebook-level historical reference.

**Port approach:** Already ported — no action. Phase 7 notebooks
read parquet via
`stroke_orofacial.io.load_centered_parquet(session_manifest)`.

### Cell 7 — markdown
Header: `## Sanity check, verify centering`. Not classified.

### Cell 8 — code (103 lines) — Production(Phase 4.5, already ported)
**Algorithm (1 sentence):** Per-session masked-vs-unmasked median
check for the centering anchor — prints unmasked and
likelihood-masked medians for the anchor bodyparts
(`nose` / `L_spout+R_spout` midpoint / `L_eye+R_eye` midpoint,
depending on `CENTER_MODE`), confirming the masked anchor median is
`≈ (0, 0)` within `TOL = 1e-6`. The function body also always prints
jaw and nose unmasked medians as a secondary reference.

**Inputs:** `intermediate_data_frames`, `CENTER_MODE`,
`CENTER_LIK_THR`.

**Outputs:** stdout-only per-session report; no files written.

**Sub-phase owner:** Already owned by Phase 4.5
(`dlc_centering/verify.py`) and surfaced in Phase 5 output as a
per-session `centering_check.json`.

**Port approach:** Already ported — no action. Functionally
identical to pixelbin Cell 8 and jaw Cell 9.

### Cell 9 — markdown
Header: `# Heatmaps`. Not classified.

### Cell 10 — markdown
Header: `## Heatmap by counts vs proportion, by date`. Not
classified. `dlc_spatial/heatmaps.py` docstring references
"cells 10-11 of `20251117_DLC_analysis_nose.ipynb`" — the 10 is this
markdown header (start of the per-session section) and 11 is the
code cell below.

### Cell 11 — code (292 lines) — Production(Phase 5, already ported — see gap note)
**Algorithm (1 sentence):** Per-session 2-D histogram of **nose only**
(`nose_x` × `nose_y`, `bins = (50, 50)`, `LogNorm` / `PowerNorm` /
`Normalize` via `NORM_MODE`, counts mode or proportion mode with
`NORMALIZE_TO_TOTAL` choosing total-rows vs filtered-rows denominator)
with auto-VMIN per mode and global-vmax percentile across sessions,
rendered as a `magma` colormap heatmap per session, deduplicated by
`(animal, date)`.

**Inputs:** `intermediate_data_frames`, `NOSE_LIKE_THR` (sweep:
`{0.70, 0.80}`), `APPLY_X_RANGE = True`, `X_MIN/X_MAX = (−80, 80)`
for PS46-54 (`(−100, 100)` for PS55), `nbins_xy = (50, 50)` (sweep:
`{(40, 40), (50, 50)}`), `hist_mode ∈ {"counts", "proportion"}`
(sweep), `NORMALIZE_TO_TOTAL` flag, `NORM_MODE ∈ {"log", "power",
"linear"}` with `GAMMA = 0.5`, `VMIN_LOG_PROP = 1e-6`,
`VMIN_LOG_COUNTS = 1e0`, `use_global_vmax = True`,
`vmax_percentile = 99.0`, axis shaping (`x_trim_each_side = 80`
for PS48-50, `300` for PS46-47/51/54, `150` for PS55;
`y_min_override = 0` for PS46-54, `None` for PS55;
`invert_y_axis = True`, `place_x_ticks_top = False`; DPI 200).

**Outputs (persisted):** per-session PNG at
`<folder_path>/<animal>_nose_heatmap/centered_<CENTER_MODE>/<mode>/
lik<thr>_xr<X_MIN>-<X_MAX>_nx<nx>_ny<ny>/nose_heatmap_<animal>_<date>.png`
(200 DPI).

**Sub-phase owner:** Phase 5 (already ported). `plot_heatmap(df,
bodypart, config, center_mode=…)` in
`src/stroke_orofacial/dlc_spatial/heatmaps.py` handles the
single-bodypart per-session case. Out of Phase 7 scope.

**Port approach:** Already ported for the default mode
(proportion / `density=True` / `LogNorm`, per-`(bodypart,
center_mode)` axis limits + `x_range` + `likelihood_threshold` from
`config["bodyparts"]["nose"]`). The `NPZ` sidecar is also already
wired via `save_heatmap_npz(df, bodypart, config, path, …)` per the
DECISIONS.md 2026-04-19 "Save fine-grid heatmap NPZ" entry.

**Gap vs current port** (non-blocking, small follow-up):

* The legacy cell supports `hist_mode = "counts"` (raw count
  histograms) as an alternative to density/proportion. The current
  port uses `density=True` (proportion) unconditionally. If Priya
  wants the counts-mode variant preserved as a config-selectable
  mode, add a `config["dlc_spatial"]["hist_mode"]` knob (default
  `"proportion"`) to `plot_heatmap()` and branch on it. **Not
  required for Phase 7.**
* The legacy cell supports `NORMALIZE_TO_TOTAL` = `False` (divide
  by filtered-rows count instead of total rows). Same
  config-selectable enhancement, same non-blocking priority.
* The legacy cell supports `NORM_MODE ∈ {"power", "linear"}` in
  addition to `"log"`. The current port hardcodes `LogNorm`. Same
  non-blocking enhancement; most output uses the `"log"` mode
  anyway per the SWEEPS list in cell source.

These gaps should get one housekeeping PR against
`dlc_spatial/heatmaps.py` — not a Phase 7 work item.

### Cell 12 — markdown
Header: `## Binned heatmaps by counts vs proportion`. Not classified.

### Cell 13 — code (484 lines) — Production(Phase 5.x mini, not yet ported — subsumed by pixelbin cell 13)
**Algorithm (1 sentence):** Session grouping by `rel_day` bins
(sweep over `bin_width_days ∈ {2, 5, 7}`, `nose_like_thr ∈ {0.70,
0.80}`, `nbins_xy ∈ {(40, 40), (50, 50)}`, `hist_mode ∈ {"counts",
"proportion"}`, `NORMALIZE_TO_TOTAL`), per-bin nose-only 2-D
histogram (session-averaged counts for counts mode, pooled
proportion for proportion mode), one PNG per bin + an
all-bins-overlaid grid (`GRID_NCOLS = 3`, `TILE_SIZE = (6, 4)`).

**Inputs:** `intermediate_data_frames`, `stroke_date_str =
"2025-03-17"` (PS49), `USE_FIRST_ALLOWED_DATE = True`,
`first_allowed_date_str = "2025-03-10"` (PS49 pre-stroke cutoff),
`NOSE_LIKE_THR`, `APPLY_X_RANGE + X_MIN/X_MAX`, `x_trim_each_side`,
`y_min_override`, `y_max_offset = −75`, `nbins_xy`, `hist_mode`,
`NORMALIZE_TO_TOTAL`, `cmap_name = "magma"`, `NORM_MODE = "log"`,
`VMIN_LOG_COUNTS = 5e1`, `VMIN_LOG_PROP = 1e-5`, `GAMMA = 0.5`,
`use_global_vmax = True`, `vmax_percentile = 99.0`,
`invert_y_axis = True`, `place_x_ticks_top = False`.

**Outputs (persisted):** per-bin + all-bins-grid PNGs under
`<folder_path>/<animal>_nose_heatmap_bins/centered_<CENTER_MODE>/<denom_tag>/lik<thr>_xr<Xmin>-<Xmax>_bins<W>_nx<nx>_ny<ny>/`
(200 DPI).

**Important convention:** `relative_day(d)` uses `return -1 if
delta == 0 else delta` — stroke day groups with pre-stroke sessions
as `rel_day = −1`. **Same convention as pixelbin cell 13.** When
the Phase 5.x mini ships, drop this remap in favor of the Phase 6.7
canonical `rel_day = (session_date - stroke_date).days` with stroke
day at 0 (see Reconciliation §2 below).

**Sub-phase owner:** Phase 5.x mini, per DECISIONS.md 2026-04-18
"Phase 5 all-bodyparts overlay heatmap design." Out of Phase 7
scope. **Subsumed by the pixelbin-canonical
`plot_all_bodyparts_heatmap_binned()` when it ships** — calling
that function with `config["dlc_spatial"]["bodyparts"]["nose"]`
selected covers the nose-only variant.

**Port approach:** In the future Phase 5.x mini kickoff
(`docs/prompts/phase-5.x-all-bodyparts-heatmap-kickoff.md`), add
`plot_all_bodyparts_heatmap_binned(manifest_group, config,
bin_width_days)` per the pixelbin classification §Cell 13 port
plan. Nose is then served by the same function with the bodypart
list filtered to `["nose"]`, preserving the full sweep knobs via
`config["dlc_spatial"]["overlay"]`. Drop the `stroke → −1` remap.
Preserve `USE_FIRST_ALLOWED_DATE` / `first_allowed_date` via
`configs/animals.yaml.animals.{PS*}.first_allowed_date`. Not a
Phase 7 port.

### Cell 14 — markdown
Header: `## Subtracted proportion heatmaps`. Not classified.
`dlc_spatial/difference_maps.py` docstring references
"cell 12 (subtraction maps) of `20251117_DLC_analysis_nose.ipynb`"
— cell 12 in the current extract is actually a markdown header for
the *binned* section (not the Δ section); the Δ section code lives
at cell 15 below its own markdown header at cell 14. Noted as doc
cleanup in Reconciliation §3.

### Cell 15 — code (585 lines) — Production(Phase 5, already ported — see gap note)
**Algorithm (1 sentence):** Δ nose proportion heatmaps vs a
pre-stroke baseline — pools sessions with `rel_day ∈ PRE_BASE_REL_RANGE`
(or all `rel_day < 0` if `PRE_BASE_REL_RANGE = None`) into a
`H_pre` histogram, renders the baseline with `magma` +
`LogNorm`, then for each post-stroke `rel_day` bin subtracts the
baseline bin-by-bin and renders `D = H_bin - H_pre` with a
diverging cmap (`RdBu_r` + `TwoSlopeNorm(vmin=-vmax, vcenter=0,
vmax=+vmax)`) using `vmax_percentile = 99.0`, plus an
all-bins-grid. Supports `hist_mode ∈ {"counts", "proportion"}` and
`NORMALIZE_TO_TOTAL`.

**Inputs:** same as cell 13 plus `PRE_BASE_REL_RANGE` (sweep:
`{None, (-10, -1), (-7, -1)}`), `DIFF_CMAP_NAME = "RdBu_r"`,
`DIFF_VMAX_PERCENTILE = 99.0`, `use_global_diff_vmax = True`,
`fixed_diff_vmax = None`, `COLOR_FOR_NO_DATA = "white"`,
`MASK_NEAR_ZERO_EPS = 0`.

**Outputs (persisted):** per-bin Δ PNG + baseline PNG + grid PNG
under
`<folder_path>/<animal>_nose_heatmap_bins/centered_<CENTER_MODE>/<denom_tag>/diff_lik<thr>_xr<Xmin>-<Xmax>_vs_<pre_range_tag>_bins<W>_nx<nx>_ny<ny>/`.

**Sub-phase owner:** Phase 5 (already ported for the compute
primitive — `dlc_spatial/difference_maps.py`
`compute_difference_map(H_post, H_baseline, mode)` +
`plot_difference_map(diff, extent, bodypart, …)`). Out of Phase 7
scope. The cell's **end-to-end driver** (baseline assembly +
per-bin iteration + grid composition) is a Phase 5.x mini
responsibility (ships alongside cells 11/13).

**Port approach:** Already ported for the Δ computation + the
diverging-cmap figure. Use as the per-bodypart primitive inside
the Phase 5.x mini's
`plot_all_bodyparts_difference_heatmap_binned()`. The nose cell
then reduces to: "pick pre-stroke sessions per
`PRE_BASE_REL_RANGE` from manifests, build `H_pre` via
`build_baseline_histogram()` (already in
`dlc_spatial/pixel_bins.py`), iterate post-stroke bins, call
`compute_difference_map()` + `plot_difference_map()` per bin".

**Gap vs current port** (non-blocking, small follow-up):

* The legacy cell has a `PRE_BASE_REL_RANGE` knob
  (`None | (-10, -1) | (-7, -1) | …`) that restricts which
  pre-stroke sessions enter the baseline. The current
  `build_baseline_histogram()` accepts a manifest list and
  pools whatever the caller hands it, so the knob is
  **structurally covered** — but no config field yet exists
  to express "pre-stroke window for baseline" at the Phase
  5.x mini layer. Add `config["dlc_spatial"]["overlay"]["baseline_window_rel_days"]
  = null | [lo, hi]` when the mini ships. **Not required for
  Phase 7.**
* The `TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=+vmax)`
  symmetric-diverging normalization is already the default in
  `plot_difference_map()` (via `vmax` kwarg). OK.
* The baseline heatmap is rendered separately (same
  `magma`/`LogNorm` choice as cell 11) — already covered by
  `plot_heatmap(H_pre, …)`.

### Cell 16 — code (3 lines) — Exploratory
```python
# List all available sessions
for i, f in enumerate(intermediate_data_frames.keys()):
    print(i, os.path.basename(f))
```
Trivial debug print ("show me which sessions are loaded"). Not
port-worthy.

---

## Hardcoded constants inventory

This notebook contains constants already promoted elsewhere (via
prior classifications — see pixelbin, tongue, jaw, and whisker)
plus a small handful of nose-specific axis knobs that will be
promoted as part of Phase 5 or Phase 5.x mini, not Phase 7.

| Constant                               | Cells          | Legacy value                             | New home                                                                 |
|----------------------------------------|----------------|------------------------------------------|--------------------------------------------------------------------------|
| `fs` (sampling frequency)               | 3              | `250` (✓ correct)                         | Already in `configs/defaults.yaml.dlc_kinematics.common.fps = 250`       |
| `CENTER_MODE` / `CENTER_LIK_THR`        | 6              | `"eye_midpoint"` / `0.70`                  | Already owned by `dlc_centering` config; `dlc_kinematics.nose.center_mode = eye_midpoint` |
| `MAX_FRAMES_PER_VIDEO`                  | 6              | `975000`                                  | Already in Phase 4.5 config                                              |
| `NOSE_LIKE_THR`                         | 11, 13, 15     | `0.70` (default) / `0.80` (sweep)          | `dlc_kinematics.nose.likelihood_threshold = 0.80` (Phase 5 default; 0.70 is a sweep variant — **confirm default with Priya**) |
| `APPLY_X_RANGE` / `X_MIN, X_MAX`         | 11, 13, 15     | `True` / `(−80, 80)` PS46-54; `(−100, 100)` PS55 | `dlc_spatial.bodyparts.nose.per_center_mode.eye_midpoint.x_range` with per-mouse override in `configs/animals.yaml.animals.{PS*}.nose_x_range` for PS55 |
| `nbins_xy` (heatmap resolution)          | 11, 13, 15     | `(50, 50)` default / `(40, 40)` sweep      | Already in `dlc_spatial.heatmap_nbins = 100` (note: nose uses 50; this is a smaller-resolution per-nose choice — `dlc_spatial.bodyparts.nose.heatmap_nbins = 50`) |
| `x_trim_each_side`                      | 11, 13, 15     | `80` PS48-50; `300` PS46-47/51/54; `150` PS55 | Per-mouse in `configs/animals.yaml.animals.{PS*}.nose_x_trim_each_side` **or** collapsed by using the percentile-based range (pixelbin cell 19 idiom) — Phase 5.x decision |
| `y_min_override`                        | 11, 13, 15     | `0` PS46-54; `None` PS55                   | Per-mouse in `configs/animals.yaml.animals.{PS*}.nose_y_min` |
| `y_max_offset`                          | 13, 15         | `−75` PS48-49 (eye centered)               | Per-mouse in `configs/animals.yaml.animals.{PS*}.nose_y_max_offset` |
| `invert_y_axis`                         | 11, 13, 15     | `True`                                      | Already in `dlc_spatial.overlay.invert_y_axis = true`                   |
| `place_x_ticks_top`                     | 11, 13, 15     | `False`                                     | `dlc_spatial.overlay.place_x_ticks_top = false`                         |
| `cmap_name` (per-session + baseline)    | 11, 13, 15     | `"magma"`                                   | Already in `dlc_spatial.bodyparts.nose.cmap = magma`                    |
| `NORM_MODE` / `GAMMA`                    | 11, 13, 15     | `"log"` / `0.5`                             | `dlc_spatial.overlay.norm_mode` / `.gamma` (Phase 5.x mini)              |
| `VMIN_LOG_PROP` / `VMIN_LOG_COUNTS`      | 11, 13, 15     | `1e-6` / `1e0` (cell 11); `1e-5` / `5e1` (cells 13, 15) | `dlc_spatial.overlay.vmin_log_proportion` / `.vmin_log_counts` (Phase 5.x mini — note: cells 13/15 use higher count floor than cell 11 because binned histograms accumulate more counts; keep both as separate knobs or use per-cell override) |
| `use_global_vmax` / `vmax_percentile`    | 11, 13, 15     | `True` / `99.0`                             | `dlc_spatial.overlay.global_vmax` / `.vmax_percentile`                  |
| `hist_mode`                              | 11, 13, 15     | `"counts"` | `"proportion"`                 | `dlc_spatial.overlay.hist_mode = proportion` (default); cell 11 gap note above |
| `NORMALIZE_TO_TOTAL`                    | 11, 13, 15     | `True`                                      | `dlc_spatial.overlay.normalize_to_total = true`                         |
| `bin_width_days`                         | 13, 15         | `{2, 5, 7}` sweep; default 7                | `dlc_spatial.overlay.bin_width_days = 7` (default); sweep convenience in the mini's driver |
| `stroke_date_str`                        | 13, 15         | `"2025-03-17"` (PS49)                       | Already in `configs/animals.yaml.animals.PS49.stroke_date`              |
| `USE_FIRST_ALLOWED_DATE` / `first_allowed_date_str` | 13, 15 | `True` / `"2025-03-10"` (PS49)              | Already in `configs/animals.yaml.animals.PS49.first_allowed_date`       |
| `LIKE_COL_NAME`                          | 13, 15         | `"nose_likelihood"`                         | Derived from bodypart name; not a config                                |
| `PRE_BASE_REL_RANGE`                     | 15             | `{None, (−10, −1), (−7, −1)}` sweep         | `dlc_spatial.overlay.baseline_window_rel_days` (Phase 5.x mini)         |
| `DIFF_CMAP_NAME` / `DIFF_VMAX_PERCENTILE`| 15             | `"RdBu_r"` / `99.0`                          | Already in `dlc_spatial.overlay.diff_cmap` / `.diff_vmax_percentile`    |
| `use_global_diff_vmax` / `fixed_diff_vmax` | 15           | `True` / `None`                             | `dlc_spatial.overlay.global_diff_vmax` / `.fixed_diff_vmax`              |
| `COLOR_FOR_NO_DATA`                     | 15             | `"white"`                                    | `dlc_spatial.overlay.no_data_color = white`                              |
| `MASK_NEAR_ZERO_EPS`                     | 15             | `0`                                          | `dlc_spatial.overlay.mask_near_zero_eps = 0`                             |
| `BASE_CMAP_NAME` / `BASE_NORM_MODE`       | 15             | `"magma"` / `"log"`                          | Same as per-session `cmap_name` / `NORM_MODE` (use one config entry)    |
| `BASE_VMIN_LOG_PROP` / `BASE_VMIN_LOG_COUNTS` | 15         | `1e-5` / `5e1`                                | Same as `VMIN_LOG_*` above                                               |
| `SAVE_DPI`                               | 11, 13, 15     | `200`                                         | Already in `dlc_spatial.overlay.dpi = 200`                               |
| `GRID_NCOLS` / `TILE_SIZE`                | 13, 15         | `3` / `(6, 4)`                                | `dlc_spatial.overlay.grid.ncols = 3` / `.tile_size = [6, 4]`              |
| `FONTS` (title/label/cbar/ticks)          | 13, 15         | `{title: 30, label: 30, cbar: 30, ticks: 25, grid_title: 20}` | `dlc_spatial.overlay.fonts.*` |
| `FIGSIZE_SINGLE`                          | 13, 15         | `(12, 8)`                                     | `dlc_spatial.overlay.figsize_single = [12, 8]`                           |

**None of the constants above get promoted in Phase 7** — they
belong to Phase 5 / Phase 5.x mini. Phase 7's config changes stay
tongue + jaw + whisker + nose-PSD-in-7d only. (Nose's
kinematic-endpoint-scope config is empty per the kickoff Q6 list.)

**Per-mouse nose knobs** (`x_trim_each_side`, `y_min_override`,
`y_max_offset`) are currently hard-coded per-mouse as inline
comments in the legacy cells. These **must move to
`configs/animals.yaml` as per-mouse nose axis overrides** during
the Phase 5.x mini port — the same treatment as whiskers cell-15
`session_override_spec` and pixelbin cell-19 percentile-range
fallback handled in those classifications.

---

## Reconciliation with prior classifications

### 1. Nose cells 11 / 13 / 15 vs pixelbin cells 11 / 13 / 15

The pixelbin notebook is the **multi-bodypart-overlay canonical** for
the Phase 5.x mini (per DECISIONS.md 2026-04-18). The nose notebook's
cells 11 / 13 / 15 are the **single-bodypart variants** of the same
three pixelbin patterns:

| Nose cell | Pixelbin cell | Relationship                                              |
|-----------|---------------|-----------------------------------------------------------|
| 11        | 11            | Pixelbin = 9-bodypart overlay; nose = single-bodypart. Both share the per-session × 2-D-histogram × LogNorm skeleton. |
| 13        | 13            | Pixelbin = 9-bodypart binned-by-rel_day overlay; nose = single-bodypart binned. Shared: session grouping, `SWEEPS`, `stroke → −1` remap, `USE_FIRST_ALLOWED_DATE` filter. |
| 15        | 15            | Pixelbin = 9-bodypart Δ overlay; nose = single-bodypart Δ. Shared: pre-stroke pooling, `TwoSlopeNorm` + `RdBu_r`, baseline rendering. Nose has the extra `PRE_BASE_REL_RANGE` knob. |

**Net reconciliation:** When the Phase 5.x mini ships
`plot_all_bodyparts_heatmap()` / `_heatmap_binned()` /
`_difference_heatmap_binned()` per the pixelbin classification §Cells
11/13/15, the nose notebook's cells 11/13/15 are **directly served**
by calling those functions with the bodypart list filtered to
`["nose"]`. The already-ported per-bodypart primitives
(`plot_heatmap()`, `build_histogram()`, `build_baseline_histogram()`,
`compute_difference_map()`, `plot_difference_map()`) continue to be
the compute layer the overlay wraps.

No edit to `classification-pixelbin.md` is required; this note
documents the single-bodypart case is covered by the multi-bodypart
mini. The same is true for the whisker notebook's cells 14/16/18
(see pixelbin Reconciliation §1).

### 2. `rel_day` remap convention

Nose cells 13 and 15 use `return -1 if delta == 0 else delta` — i.e.
stroke day groups with pre-stroke sessions as `rel_day = −1`. **Same
convention as pixelbin cell 13 and whisker cells 16/18.** The
canonical Phase 6.7 convention (`SessionManifest.rel_day =
(session_date - stroke_date).days`) keeps stroke day at 0.

When the Phase 5.x mini ships, **drop the `stroke → −1` remap** —
align on the Phase 6.7 canonical `rel_day = 0 at stroke`. This is
flagged identically in the pixelbin classification
§Reconciliation 3; recording again here so the nose-specific remap
doesn't sneak through a different code path during the mini port.

### 3. `dlc_spatial/difference_maps.py` docstring reference

The docstring at
`src/stroke_orofacial/dlc_spatial/difference_maps.py` reads:

> Ported from cell 12 (subtraction maps) of
> `20251117_DLC_analysis_nose.ipynb` and cell 7 of
> `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`.

In the current `notebook-structure-nose.md` extract, cell 12 is a
markdown header (`## Binned heatmaps by counts vs proportion`) and
the actual Δ code is at cell 15 (under markdown cell 14
`## Subtracted proportion heatmaps`). The docstring's "cell 12" is
therefore **off by 3 code/markdown-index units** from the current
extract — likely written against a pre-split or code-cells-only
numbering.

Recorded here so 7a–7f authors reading `difference_maps.py` don't
chase the wrong cell number. Follow-up documentation-only cleanup
(same scope as pixelbin Reconciliation §2); a 20-minute fix to
update docstrings to:

```
Ported from cell 15 (Δ baseline nose heatmap) of
`20251117_DLC_analysis_nose.ipynb` and cell 15 (Δ multi-bodypart
overlay) of `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`.
```

### 4. `dlc_spatial/heatmaps.py` docstring reference

Docstring reads "ported from cells 10-11 of
`20251117_DLC_analysis_nose.ipynb` and `20251117_DLC_analysis_jaw.ipynb`
(siblings, consolidated into one parameterized module), plus cell 5 of
`20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`."

For nose: cell 10 is the markdown section header and cell 11 is the
actual code — "cells 10-11" is a reasonable range-form reference
(markdown + code), **matches current extract**. No fix needed.

For jaw: need to verify against the jaw notebook structure —
classification-jaw.md lists the per-session nose/jaw heatmap cell at
jaw-notebook cell **30** (within the exploratory mean-XY-plot group)
rather than at a direct parallel to nose cell 11. That's because the
jaw notebook is the interpolation-centric sibling, not the heatmap
sibling — the sibling relationship for heatmap code is
`nose notebook ↔ jaw notebook` at the per-bodypart level, but the
specific cells are not directly parallel. The `heatmaps.py`
docstring's claim of "cells 10-11 of jaw.ipynb" appears to be
**incorrect** — there is no jaw-heatmap code at cells 10-11 of
the jaw notebook (per
`docs/phase-7/notebook-structure-jaw.md` those are exploratory QC
cells). The per-bodypart heatmap code as consolidated in
`heatmaps.py` plausibly came from an **earlier jaw-notebook copy**
that had heatmap code at cells 10-11, before the interpolation
cells were added and shifted the structure.

Treat as follow-up documentation cleanup: update the jaw-notebook
reference in `heatmaps.py` docstring to either drop it (if no jaw
notebook code directly ported) or point at the pre-shifted archive
copy. Not a Phase 7 port target; same scope as pixelbin
Reconciliation §2.

### 5. Nose has no multi-video-session merge cell

Unlike tongue cell 13 / jaw cell 13 / whisker cell 13, nose does
**not** have a multi-video-per-session merge cell. This is the
**correct** layering: nose reads from the already-merged Phase 4.5
cache, and the merge happens in Phase 4.5 (or Phase 3 for the
alignment template, or Phase 2 for the licks-and-rewards NPZ).

No reconciliation action — just documenting that the absence of
this cell in nose is not a gap.

---

## Next Cowork turn

**7.0b is complete.** Classification deliverables for all five
Phase 7 reference notebooks now exist under `docs/phase-7/`:

1. `classification-tongue.md`
2. `classification-jaw.md`
3. `classification-whiskers.md`
4. `classification-pixelbin.md`
5. `classification-nose.md` ← this document

Next actions in sequence:

1. ~~Mark task #11 completed.~~ **Done.**
2. ~~Resolve tongue cell 53 scope decision~~ **Resolved 2026-04-21:
   option (b) → 7c.** Updated in `classification-tongue.md` and
   `classification-jaw.md`.
3. **Commit + PR + merge + tag 7.0b.** Branch
   `docs/phase-7-cell-classification`. Tag `v7.0b-cell-classification`
   with message `Phase 7.0b: cell-by-cell dead-code classification
   for tongue / jaw / whiskers / pixelbin / nose notebooks`.
4. **7a-design brief** (`docs/phase-7/interpolation-strategy.md`)
   opens after 7.0b merges. Blocked by the Phase 5/6 trial_group
   translation mini-PR (`v6.8a-phase-5-6-trial-group-translation`)
   per task #7's resolution.

Phase-7 summary of port surface found across all 5 notebooks:

| Sub-phase | Source cells across all 5 notebooks                                                |
|-----------|-------------------------------------------------------------------------------------|
| 7a (interp) | tongue 23, jaw 22, whisker 25 (3 siblings → 1 bodypart-parametric module)        |
| 7b (tongue endpoints) | tongue 33, 36, 39, 42, 50                                                |
| 7c (jaw + whisker + nose endpoints + tongue-jaw mismatch) | new surface area (jaw), whisker 15–74 TBD, **tongue cell 53** (tongue-jaw mismatch classifier — resolved 2026-04-21), **nose: nothing** |
| 7d (face-velocity PSD) | tongue 62, 64, jaw 43 (+ nose/whisker from centered parquet, new)       |
| 7e (trial-aligned windowing) | shipped alongside 7b                                                |
| Data repair (pre-7a) | tongue 13/16/17/19, jaw 13/15/16/18                                         |

Pixelbin and nose notebooks contribute **zero** Phase 7 cells. Their
content is fully owned by Phase 5 (already ported), Phase 5.x mini
(scheduled), and Phase 9 (deferred inferential stats, pixelbin-only).
