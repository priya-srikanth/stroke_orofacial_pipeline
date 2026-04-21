# Classification: 20251111_DLC_analysis_whiskers.ipynb

Companion to `docs/phase-7/notebook-structure-whiskers.md`. Produced during
Phase 7 sub-phase 7.0b for the dead-code classification requirement in
CLAUDE.md §"Phase plan requirements." Same format as
`docs/phase-7/classification-tongue.md` and
`docs/phase-7/classification-jaw.md`.

Source: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\old_code\20251111_DLC_analysis_whiskers.ipynb`
(320 KB, 67 cells: 36 code, 31 markdown).

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
  into `outputs/whiskers_dump_prod.txt` for a second pass. Every
  Ambiguous entry below has since been resolved.

For every **Production** cell, port-surface extraction records:
**algorithm (1 sentence) → inputs → outputs → sub-phase owner → port
approach**.

## Summary

| Label        | Code cells | Indices                                                                          |
|--------------|------------|----------------------------------------------------------------------------------|
| Production   | **0**      | —                                                                                |
| Exploratory  | 20         | 1, 3, 4, 6, 7, 9, 10, 13, 14, 16, 18, 19, 21, 28, 32, 34, 36, 44, 60, 65         |
| Deprecated   | 15         | 23, 24, 26, 29, 39, 41, 43, 47, 49, 51, 54, 56, 58, 61, 63                       |
| Ambiguous    | 0          | (all resolved during port-surface extraction pass)                               |
| Empty        | 1          | 66                                                                               |

Cross-check against the sub-phase breakdown in
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`:

| Sub-phase | Owned cells (whiskers notebook)                                                                                     |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| 7a        | —                                                                                                                    |
| 7b        | — (tongue endpoints come from the canonical tongue notebook)                                                         |
| 7c        | — (whisker endpoints are **NEW surface area**; see §"Important scope finding for 7c" below)                          |
| 7d        | — (the face-velocity-aggregate PSD driver ships from the canonical tongue/jaw PSDs, not from this notebook's cells)  |
| 7e        | —                                                                                                                    |
| Data repair (pre-7a) | —                                                                                                         |

### Important scope finding for 7c

**This notebook is a misnomer.** Despite the filename
`20251111_DLC_analysis_whiskers.ipynb`, fewer than 10% of its code is
whisker-specific, and *zero cells are Production*. The breakdown:

* **Cells 14 / 16 / 18 (the only whisker-touching cells)** are
  multi-bodypart 2-D histogram overlays — nose + jaw + tongue + 6
  whisker positions (L_whiskers_1..3, R_whiskers_1..3) rendered on a
  single axis with per-part stacked colorbars. The *per-bodypart*
  versions of these heatmaps (per-session, binned, and baseline-subtracted
  Δ) are **already ported** to Phase 5/6:
  - `src/stroke_orofacial/dlc_spatial/heatmaps.py` (per-bodypart 2D
    histogram, per-session & binned)
  - `src/stroke_orofacial/dlc_spatial/difference_maps.py` (baseline
    subtraction)
  - `src/stroke_orofacial/dlc_spatial/pixel_bins.py` (histogram builder
    + per-`(bodypart, center_mode)` axis/config wiring)
  The **multi-bodypart-on-one-figure overlay** variant is an
  exploratory visualization — it is not persisted to disk as analytical
  output, it is not consumed downstream, and the per-bodypart versions
  already in Phase 5/6 are strictly cleaner (per-bodypart config,
  per-`(bodypart, center_mode)` axis limits, no stacked colorbar
  hackery). Listed as **Exploratory**, not Deprecated, because they
  are not direct duplicates — they are a visualization aggregation
  that could live as a thin plotting wrapper in Phase 9 if Priya wants
  the overlay view. Do not port in 7c.

* **Cells 23–29** are **tongue** kinematics v2 (gap-robust linear
  bridging + bout-based L/R classification + per-bout scatters). This
  is the predecessor of the canonical tongue v5p3 interpolation
  (tongue notebook Cell 23) and is superseded in every respect:
  v5p3 replaces linear bridging with PCHIP small-gap fill, replaces
  the bout side classifier with DLC-visual X-threshold side
  classification, and adds per-trial dY/dt first-lick detection. No
  downstream consumer reads `kinematics_session_summary.csv` /
  `kinematics_bouts_summary.csv`; confirmed by grep across the
  stroke_orofacial codebase. Listed as **Deprecated**.

* **Cells 39–63** are **tongue** PSD / spectrogram figures at
  `fs = 150` Hz. The canonical tongue notebook runs at 250 Hz (and the
  canonical tongue PSD cells do too). Using 150 Hz on 250-Hz-sampled
  data would mis-scale the frequency axis by a factor of 250/150 =
  1.67× — i.e., a true 5-Hz lick peak would show at ~3 Hz. **This is
  a latent bug**, now irrelevant because the canonical tongue PSD
  cells supersede the whole block, but worth noting in
  `docs/MIGRATION_LOG.md` when 7d-design lands so we're not tempted to
  lift any "helper" from these cells. Listed as **Deprecated**.

* **Cells 34 / 36** are per-session tongue X/Y histograms by density.
  These were superseded long ago by tongue pixel-bin histograms
  already in Phase 5/6 (`dlc_spatial/pixel_bins.py`). Listed as
  **Exploratory** (they do not write persistent analytical output —
  they are inline density previews).

**Therefore**: 7c-impl for whiskers has **no legacy reference code to
port**. Whisker-specific kinematic endpoints — the Q6 list references
mean whisking amplitude, per-whisker setpoint, whisking asymmetry
(L–R bias of setpoint and/or amplitude), retraction-phase duration,
whisker-to-lick-phase locking, etc. — must be implemented from scratch
in 7c-impl. 7c-design must draft the whisker endpoint list *ab
initio*, not expect to inherit them from this notebook.

This also means the previously-cited expectation in the jaw
classification's closing note ("whiskers is the largest non-tongue
notebook and will likely reveal more Production surface area than jaw
did") is **wrong**. The whiskers notebook is the smallest
Production-surface notebook in Phase 7, with zero Production cells.
Update for 7c-design to internalize: jaw provides Cell 22 (v5p3
interpolation); whiskers provides nothing; nose still TBD (classified
next).

### Anticipated 7c whisker-endpoint inputs (for 7c-design)

Since no whisker endpoint code exists in legacy, 7c-design will need
to invent the port surface. Inputs for whisker endpoints are expected
to be:

- DLC bodyparts `L_whiskers_{1,2,3}` and `R_whiskers_{1,2,3}` from the
  Phase 4 parquet cache (loaded via the SessionManifest resolver from
  Phase 6.7).
- Centered in the mouse frame with `CENTER_MODE = "eye_midpoint"`
  (confirmed from Cell 6: whiskers analysis in the legacy notebook
  explicitly sets `CENTER_MODE = "eye_midpoint"`, unlike tongue which
  uses `"spout_midpoint"` and jaw which also uses `"eye_midpoint"`).
- Baseline likelihood threshold per-whisker from legacy:
  `WHISKER_LIKE_THR = 0.80` (Cells 14/16/18). Promote to
  `configs/defaults.yaml` under `dlc_kinematics.whiskers.lk_thr`.
- Reward-aligned windowing (Phase 7e boundary-layer) is the same as
  for tongue/jaw — whisker endpoints should be computed in the same
  trial-aligned window specification.

The interpolation approach for whiskers should follow the jaw
parametric scheme already scoped in the jaw classification
(bodypart-parametric `interpolate_bodypart()` entrypoint reading the
per-bodypart config subtree under `dlc_kinematics.whiskers:` merged
with the shared `interpolation_template:` anchor).

---

## Per-cell classification

### Cell 0 — markdown
Header: `# Import packages`. Not classified (markdown).

### Cell 1 — code (29 lines) — Exploratory
Python/pandas/numpy/matplotlib/seaborn imports and matplotlib rc
config. Boilerplate; re-done in every Phase 7 module port.

### Cell 2 — markdown
Header: `# Load files and appoint labels`. Not classified.

### Cell 3 — code (63 lines) — Exploratory
File discovery: globs `folder_path` for DLC CSV/H5 files, builds
`csv_files` and `folder_path` (hardcoded to
`~/Documents/data/DLC/<mouse>`). Superseded by Phase 4
`load_parquet_cache()` + SessionManifest from Phase 6.7, which enumerate
sessions by animal + date range rather than by local-file globbing.
Also hardcodes `animal = "PS46"` — superseded by SessionManifest's
animal-scoped loading.

### Cell 4 — code (47 lines) — Exploratory
Builds `file_labels` dict (filename → `"YYYY-MM-DD HH:MM"` human
label) and regex-extracts date from filenames. Superseded by
SessionManifest (dates + animals live in `configs/animals.yaml` /
per-session metadata, not parsed from filenames at runtime).

### Cell 5 — markdown
Header: `# Loop through files, filter data`. Not classified.

### Cell 6 — code (222 lines) — Exploratory
Data build loop: for each CSV/H5, reads DLC output, computes
per-session centering (default `CENTER_MODE = "eye_midpoint"`, median
of L_eye+R_eye at `CENTER_LIK_THR = 0.7`), subtracts from all `*_x`
and `*_y` columns, atomically writes a parquet cache keyed by a
parameter-signature hash, and emits a `centers_used.csv` +
`analysis_run_*.json` provenance report.

Superseded by Phase 4 `load_parquet_cache()` — the Phase 4 parquet
cache already stores centered DLC per `(session, center_mode)`. The
cache-signature + provenance-JSON pattern is philosophically carried
forward in Phase 4 (dataset versioning) and SessionManifest (session
provenance), so no specific constant is rescued.

**Only fact that survives from this cell into 7c-design**: whiskers
analysis uses `CENTER_MODE = "eye_midpoint"` (matching jaw), not
`"spout_midpoint"` (which tongue uses). This selection is already
captured in the jaw classification's hardcoded-constants table and
will re-appear in the 7c-design whisker entry.

### Cell 7 — code (81 lines) — Exploratory
Backup utility: re-writes caches from Cell 6 with atomic rename and
skip-existing. Pure orchestration variant of Cell 6; no new logic.

### Cell 8 — markdown
Header: `## Load already-existing parquet files`. Not classified.

### Cell 9 — code (99 lines) — Exploratory
Alternate loader that reads Cell 6's cache without regenerating it
(skips the DLC CSV/H5 read path). Superseded by Phase 4 parquet
loader.

### Cell 10 — code (103 lines) — Exploratory
Sanity-check cell: per-session, recomputes the centering center using
the same CENTER_MODE logic and verifies the cached data has
approximately zero median at the chosen reference points. QC-only; no
output consumed downstream. Superseded by Phase 4 QC which bakes this
in during cache write.

### Cell 11, 12 — markdown
`# Heatmaps` / `## Heatmap by counts vs proportion, by date`. Not classified.

### Cell 13 — code (5 lines) — Exploratory
Scratch TODO list comments (`## try: # moving analysis to O2 …`). No
code.

### Cell 14 — code (186 lines) — Exploratory
Multi-bodypart + whisker per-session heatmap: for each session, renders
a single 8×6 figure with `hist2d(density=True, LogNorm)` per part
(nose, jaw, tongue, L_whiskers_1..3, R_whiskers_1..3) all overlaid on
one axis with per-part stacked horizontal colorbars on the right.
Per-part likelihood thresholds hardcoded: nose=0.80, jaw=0.80,
tongue=0.70, whiskers=0.80. Fixed x_limits=(−200, 200),
y_limits=(50, 550).

**Why Exploratory, not Production**: the per-bodypart version of this
heatmap is already ported to
`src/stroke_orofacial/dlc_spatial/heatmaps.py` with cleaner
per-`(bodypart, center_mode)` axis config from
`configs/defaults.yaml`. The multi-bodypart overlay on one axis is a
visualization aggregation; it is not persisted to disk as analytical
output and it is not an analytical primitive — it is a figure style.
If Priya wants this overlay view post-port, a thin wrapper in
`dlc_spatial/` that calls the existing per-bodypart heatmap N times
and composes them on one axis with stacked cbars would be the right
shape, and that belongs in Phase 9 (exploratory viz), not 7c.

Nothing ports to 7c from this cell.

### Cell 15 — markdown
Header: `## Binned heatmaps by counts vs proportion`. Not classified.

### Cell 16 — code (501 lines) — Exploratory
Binned multi-bodypart + whisker heatmap: same as Cell 14 but with
rel_day binning (SWEEPS over bin_width_days = {5, 7}, hist_mode =
{counts, proportion}). Output: one figure per bin × sweep + a
montage grid.

**Why Exploratory**: exact same reasoning as Cell 14 — the
per-bodypart binned-heatmap primitive is already in
`dlc_spatial/heatmaps.py` with rel_day binning support. The
multi-bodypart overlay is exploratory viz.

Nothing ports to 7c from this cell.

### Cell 17 — markdown
Header: `## Subtracted proportion heatmaps`. Not classified.

### Cell 18 — code (685 lines) — Exploratory
Δ multi-bodypart + whisker heatmap vs pre-stroke baseline: for each
rel_day bin, computes H_bin − H_pre per bodypart, renders on one
figure with diverging per-part cmaps (RdBu_r, PuOr, PiYG, BrBG,
coolwarm, bwr). SWEEPS over `PRE_BASE_REL_RANGE = {None, (−10,−1),
(−7,−1)}`.

**Why Exploratory**: per-bodypart baseline subtraction is already
ported to `dlc_spatial/difference_maps.py` (cell 12 of the nose
notebook and cell 7 of the pixelbin notebook were its source, per the
module docstring). The multi-bodypart overlay variant is exploratory
viz.

Nothing ports to 7c from this cell.

### Cell 19 — code (3 lines) — Exploratory
`for i, f in enumerate(intermediate_data_frames.keys()): print(i, os.path.basename(f))`. Interactive list.

### Cell 20 — markdown
Header: `## Colormap testing`. Not classified.

### Cell 21 — code (92 lines) — Exploratory
One-shot colormap grid: plots a single tongue heatmap rendered with
~10 different matplotlib cmaps side-by-side for human inspection.
Exploratory viz; no persistent output.

### Cell 22 — markdown
Header: `# Kinematics`. Not classified.

### Cell 23 — code (325 lines) — Deprecated
**Tongue kinematics v2** (gap-robust): bridges NaN runs ≤ 4 frames
with linear interpolation (rejecting jumps > 30 px and L↔R side
crossings), optional median/savgol smoothing, head-axis rotation
using L_eye/R_eye medians, per-step dt/speed/angle computation with
gap-aware dt, and bout detection (≥ 10 consecutive same-side frames
above `LATERAL_THRESHOLD_PX = 5.0`).

**Why Deprecated**: superseded by the canonical tongue v5p3
interpolation (tongue notebook Cell 23, jaw notebook Cell 22). v5p3
uses:
- PCHIP small-gap fill instead of linear bridging (smoother
  derivatives, better for dY/dt first-lick detection).
- Explicit baseline-from-reward-window masking
  (`_build_reward_aligned_pool_mask`) instead of global session
  statistics.
- DLC-visual X-threshold side classification (matched to
  spout-pixel-midpoint frame), not rotated-X bout classification.
- Per-trial endpoints (first-lick dY/dt, peak velocity, licks/trial,
  lick-rate, bout ILI) instead of per-session bout summaries.

No downstream consumer reads
`kinematics_session_summary.csv` / `kinematics_bouts_summary.csv`
(confirmed by grep across `src/stroke_orofacial/` and
`stroke_orofacial_pipeline_outputs/` references). Entirely superseded.

### Cell 24 — code (158 lines) — Deprecated
RUN harness for Cell 23: iterates sessions, collects per-date session
stats and bout rows, writes `kinematics_session_summary.csv` and
`kinematics_bouts_summary.csv`, plots 4 PNGs (median_speed_vs_day,
median_angle_vs_day, bout_peak_speed_vs_day, bout_duration_vs_day) +
a multi-page PDF. Runs the Cell 23 v2 pipeline end-to-end.

**Why Deprecated**: runner for Cell 23 (v2 tongue kinematics); its
outputs are v2-era and have no downstream consumer. Whisker v5p3
will re-derive these quantities from reward-aligned windowed data in
7b/7e, not from session-global bout stats.

### Cell 25 — markdown
Header: `## Save kinematics intermediates`. Not classified.

### Cell 26 — code (87 lines) — Deprecated
Saves Cell 23/24 outputs + preprocessed parquet cache + run manifest.
Skip-existing utility; purely persistence layer for v2 kinematics.
Superseded by v5p3's Cell 22 NPZ persistence in the jaw notebook
(and Cell 23 in the tongue notebook).

### Cell 27 — markdown
Header: `## Kinematics test run`. Not classified.

### Cell 28 — code (136 lines) — Exploratory
Single-session dry-run with `MAX_FRAMES_FOR_TEST = 150_000` truncation,
prints stats, plots speed histogram + rotated-x timeline + bouts
scatter. Dev-time smoke test for Cell 23; not a Production path.

### Cell 29 — code (137 lines) — Deprecated
Per-bout trajectory renderer: for each bout from Cell 23's detector,
plots raw (centered) tongue XY with direction arrows and start/end
markers. Consumes v2 bouts; not used downstream.

**Why Deprecated**: per-bout overlays are subsumed by 7b/7e's
per-trial windowed plots (already scoped in the tongue classification
§Cell 30 / Cell 32). The v2 bout definition is not how the canonical
analysis slices trials.

### Cell 30, 31 — markdown
`# Histograms` / `## Histogram by frequency, filtered data`. Not classified.

### Cell 32 — code (18 lines) — Exploratory
Entire cell is commented out (`# for file, dlcTable_filtered in
manipulated_data_frames.items(): # plt.figure(...) # …`). Dead code.

### Cell 33 — markdown
Header: `## USE ME: Histograms by density, X & Y, filtered data`. Not classified.

### Cell 34 — code (61 lines) — Exploratory
Per-session tongue X and Y 1-D density histograms (matplotlib
`plt.hist(density=True)`), rendered one per session.

**Why Exploratory**: 1-D marginal density previews. No persisted
analytical output. Superseded by `dlc_spatial/pixel_bins.py` (2-D
histograms) if Priya wants the primary output view, or by tongue
v5p3's per-trial kinematics for analytical endpoints.

### Cell 35 — markdown
Header: `## Histograms by density, X & Y, with replaced data`. Not classified.

### Cell 36 — code (60 lines) — Exploratory
Same as Cell 34 but on `intermediate_data_frames` instead of
`manipulated_data_frames`. Commented-out header comments (`plt.clf()`).
Duplicate of Cell 34 with a different input-dict name. Exploratory.

### Cell 37, 38 — markdown
`# Power spectral density and Spectrogram visualizations` /
`## USE ME: tongue_x PSD and Spectrograms, broken axis`. Not classified.

### Cell 39 — code (179 lines) — Deprecated
Tongue X PSD + spectrogram (Welch, scipy.signal.welch) with broken-Y
log axis. **`fs = 150` hardcoded** — but this notebook's data is
sampled at 250 Hz (confirmed by tongue notebook Cell 22 which states
`FPS = 250`, jaw notebook Cell 22 which also uses 250, and by the
Flea3 acquisition pipeline). Using 150 on 250-Hz data mis-scales the
frequency axis by 250/150 ≈ 1.67× — a real 5-Hz lick peak would
appear at ≈ 3 Hz. Saves PNGs to
`<folder_path>/<name>_tongue_spect/tongue_x_PSD_<label>.png`,
`tongue_x_spect_<label>.png`, and `tongue_x_combined_<label>.png`.

**Why Deprecated**: superseded by the canonical tongue notebook's PSD
cells (62/64, which use `fs = 250`). The fs=150 literal here is a
latent bug; it is NOT a datum to preserve.

### Cell 40 — markdown
Header: `## USE ME: tongue_y PSD and Spectrograms`. Not classified.

### Cell 41 — code (136 lines) — Deprecated
Tongue Y PSD + spectrogram (non-broken axis). Same `fs = 150` bug.
Same supersession as Cell 39.

### Cell 42 — markdown
Header: `### Broken axis for Y PSD`. Not classified.

### Cell 43 — code (180 lines) — Deprecated
Tongue Y PSD + spectrogram with broken-Y axis. Same `fs = 150` bug.
Same supersession as Cell 39.

### Cell 44 — code (2 lines) — Exploratory
`# # Print the maximum power value for "tongue_y"` — fully commented out.

### Cell 45, 46 — markdown
`## Combined X + Y PSD and Spectrograms` / `### Unmodified axes`. Not classified.

### Cell 47 — code (101 lines) — Deprecated
Combined X+Y PSD + spectrograms on unmodified axes. Same fs=150 bug.
Superseded by canonical tongue PSD.

### Cell 48 — markdown
Header: `### USE ME: Broken axis for X PSD, define frames to use`. Not classified.

### Cell 49 — code (132 lines) — Deprecated
Combined X+Y PSD with broken X axis + define frames_to_use. Same
fs=150 bug. Superseded.

### Cell 50 — markdown
Header: `### Broken X and Y axis`. Not classified.

### Cell 51 — code (142 lines) — Deprecated
Combined X+Y PSD with broken X and broken Y axes. Same fs=150 bug.
Superseded.

### Cell 52, 53 — markdown
`## Overlay X & Y PSD plots across days` / `### Standard log axis for X PSD`.
Not classified.

### Cell 54 — code (71 lines) — Deprecated
Overlay PSD across sessions (X & Y, cumulative): iterates sessions
end-to-end and re-plots PSD with each new session added, producing
`psd_plot_1.png … psd_plot_N.png`. Colored with scicomap `turbo`. Same
`fs = 150` bug. Superseded by canonical tongue PSD overlay.

### Cell 55 — markdown
Header: `### USE ME: Broken axis for X PSD, define frames to use`. Not classified.

### Cell 56 — code (124 lines) — Deprecated
Same overlay as Cell 54 but with broken X axis and `frames_to_use =
10 * 60 * fs` (first 10 minutes). Same fs=150 bug. Also hardcodes an
`exclude_files` list of four PS45 CSVs — not a port target. Superseded.

### Cell 57 — markdown
Header: `### Broken X and Y axis, overlaid PSD, define frames to use`. Not classified.

### Cell 58 — code (128 lines) — Deprecated
Overlay PSD with broken X and Y axes. `frames_to_use = 65 * 60 * fs`
(65 minutes, despite the comment "10 minutes in frames"). Same fs=150
bug. Superseded.

### Cell 59 — markdown
Header: `### USE ME: Overlaid PSD plots for pre- vs post-stroke`. Not classified.

### Cell 60 — code (149 lines) — Exploratory
**Defines hardcoded `pre_stroke_files` and `post_stroke_files` lists
per-mouse** (PS36, PS38, PS39, PS40, PS46 — most commented out; only
PS46 active). Also defines `custom_labels` mapping each CSV filename
to `"day -N"` / `"day +N"` strings. This is legacy metadata wiring
that is entirely superseded by SessionManifest + `animals.yaml`
(stroke_date_str per mouse + rel_day derivation) from Phase 6.7.

**Why Exploratory** (not Deprecated): it is not an "older version" of
a canonical pattern — it's a hand-maintained config dict that has
been replaced by the structured YAML config. No code ports; the
animal+date content is already in `animals.yaml`.

### Cell 61 — code (207 lines) — Deprecated
Overlay PSD pre/post-stroke for tongue X only, broken Y axis. Same
`fs = 150` bug. Uses Cell 60's pre/post lists + custom_labels.
Superseded.

### Cell 62 — markdown
Header: `#### PSD overlaid, pre- and post-stroke, with broken X and Y axis`.
Not classified.

### Cell 63 — code (222 lines) — Deprecated
Overlay PSD pre/post/combined for tongue X and Y, broken Y axes with
independent breakpoints (`break_val_x = 10**−1.5`, `break_val_y =
10**−0.5`). Same `fs = 150` bug. Superseded.

### Cell 64 — markdown
Header: `### Testing different colormaps`. Not classified.

### Cell 65 — code (68 lines) — Exploratory
Iterates over `['guppy_r', 'spectral', 'turbo', 'vanimo',
'watermelon']` and re-runs PSD overlay with each cmap. Colormap
selection trial; same fs=150 bug inherited; no persistent output
consumed downstream.

### Cell 66 — code (0 lines) — (empty)
Empty cell. Not classified.

---

## Hardcoded constants inventory

Despite this notebook having zero Production cells, a small number of
constants referenced here should inform the config for whisker-aware
modules (per-bodypart likelihood thresholds, whisker bodypart list,
whisker `center_mode`) — all promoted per CLAUDE.md to
`configs/defaults.yaml` under the `dlc_kinematics.whiskers:` subtree.

| Constant                       | Cells              | Legacy value                                      | New home                                                             |
|--------------------------------|--------------------|---------------------------------------------------|----------------------------------------------------------------------|
| `CENTER_MODE` for whiskers     | 6                  | `"eye_midpoint"`                                  | `configs/defaults.yaml` → `dlc_kinematics.whiskers.center_mode`      |
| `CENTER_LIK_THR`               | 6                  | `0.7`                                             | Shared `dlc_kinematics.interpolation_template.center_lk_thr`         |
| `WHISKER_LIKE_THR`             | 14, 16, 18         | `0.80`                                            | `dlc_kinematics.whiskers.lk_thr`                                     |
| `NOSE_LIKE_THR`                | 14, 16, 18         | `0.80`                                            | `dlc_kinematics.nose.lk_thr` (see nose classification)               |
| `JAW_LIKE_THR`                 | 14, 16, 18         | `0.80`                                            | Already captured in jaw classification                               |
| `TONGUE_LIKE_THR`              | 14, 16, 18         | `0.70`                                            | Already captured in tongue classification                            |
| Whisker bodypart list          | 14, 16, 18         | `L_whiskers_{1,2,3}`, `R_whiskers_{1,2,3}`         | `dlc_kinematics.whiskers.bodyparts` (list of 6)                      |
| `APPLY_X_RANGE`, `X_MIN/MAX`   | 14, 16, 18         | `True`, `(−200, 200)`                             | Shared `dlc_spatial` hist range (already in defaults.yaml via `dlc_spatial.pixel_bins`) |
| Whisker diverging cmaps        | 18                 | `BrBG`, `coolwarm`, `bwr`                          | Not promoted — plot-level viz choice; lives in plotting wrapper if Phase 9 overlay is ever built |
| `fs = 150` for PSD             | 39, 41, 43, 47, 49, 51, 54, 56, 58, 61, 63 | `150`     | **BUG — do not promote**; canonical tongue/jaw PSD runs at 250 (`dlc_kinematics.psd.fs = 250`) |

---

## Reconciliation with the jaw classification's forward-looking note

The jaw classification (§Next Cowork turn) predicted:

> Whiskers is the largest non-tongue notebook and will likely reveal
> more Production surface area than jaw did (per Q6 whisker-specific
> endpoints include mean whisking amplitude, whisking asymmetry, and
> per-whisker setpoint/retraction traces).

This prediction was wrong. Whiskers is the **smallest** Production
surface of the four non-tongue notebooks examined so far (jaw: 6 Prod;
whiskers: 0 Prod; pixelbin/nose pending). The whisker-specific
endpoints referenced in the Q6 list (mean whisking amplitude,
whisking asymmetry, per-whisker setpoint/retraction traces) are
**NOT** present in this notebook in any form — neither as Production
nor as Deprecated-older-version. They must be designed and
implemented fresh in 7c-design/7c-impl, against the DLC whisker
bodyparts read from the Phase 4 parquet cache.

7c-design should therefore:

1. **Draft the whisker endpoint list from scratch** in
   `docs/phase-7/whisker-endpoints-design.md`, referencing Q6 but not
   expecting any legacy scaffolding.
2. **Parametrize the interpolation module** for 6 whisker bodyparts
   (`L_whiskers_{1,2,3}`, `R_whiskers_{1,2,3}`), reusing the shared
   `interpolate_bodypart()` entrypoint scoped in the jaw
   classification. Per-bodypart tuning constants live under
   `dlc_kinematics.whiskers.interpolation` in `configs/defaults.yaml`.
3. **Share the reward-aligned windowing** from 7b/7e — whisker
   endpoints compute in the same per-trial window as tongue and jaw
   endpoints, emitted in the mouse frame per Phase 6.8 L/R
   convention.
4. **Audit the whisker bodypart quality** during 7c-design: confirm
   that the DLC model actually tracks all 6 whiskers with usable
   likelihood across the PS46–PS55 cohort. If some whiskers drop
   below usable likelihood on enough sessions, the endpoint set may
   need to be reduced or made per-mouse-configurable via
   `animals.yaml`.

---

## Next Cowork turn

Classification of the pixelbin notebook
(`20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`, 26 cells,
14 code) under `docs/phase-7/classification-pixelbin.md`, same format.
Per the pixelbin notebook name + the `dlc_spatial/pixel_bins.py`
module docstring that already references cell 5 and cell 7 of this
notebook as Phase 5/6 source material, pixelbin is expected to have
more significant Phase-5/6 overlap — classification should note which
cells are already ported vs. which remain for 7d (the face-velocity
aggregate PSD is the leading candidate that has not yet landed
anywhere).
