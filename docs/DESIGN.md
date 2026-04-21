# Consolidation Design Doc — Stroke Behavior & DLC Analysis Codebase

**Author context:** Priya Srikanth, MD-PhD, systems neuroscientist. Study: post-stroke orofacial motor plasticity in mice after unilateral L ventrolateral striatal (VLS) stroke. Cohort 1 = 8 animals (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55) with pre- and post-stroke behavioral recordings (Flea3 @ 250 fps) during a Pavlovian L/R-cued licking task.

**Purpose of this doc:** Single source of truth to hand Claude Code (running in a terminal on the Mac) so it can consolidate the existing messy codebase into a clean, cross-platform, well-annotated GitHub repo. The doc is prescriptive about data safety, repo structure, and core abstractions; it is intentionally TODO/placeholder in several analysis-specific areas where the work requires actually reading existing code.

**Status legend in this doc:**

- `[DECIDED]` — lock this in; do not re-litigate without asking Priya.
- `[TO BE CONFIRMED]` — sensible default proposed here; confirm against existing code/notebooks before committing.
- `[TODO]` — genuine open work, defer to later milestones.

---

## 0. DATA SAFETY GROUND RULES (non-negotiable) `[DECIDED]`

These rules bind every Claude Code session working on this project. They should be the first thing Claude Code reads at session start (via `CLAUDE.md`).

1. **Never modify, overwrite, rename, or delete source data.** "Source data" = any raw file produced by an instrument, experiment, or upstream processing that is not already produced by this new consolidated codebase. Concretely this includes, but is not limited to:
   - Raw wavesurfer `.h5` files.
   - Raw videos (Flea3 recordings).
   - DLC inference outputs on the MICROSCOPE server (`O2_analysis/PS*/...` H5 and CSV files).
   - The DLC training config and project at `DLC_train_config/`.
   - The existing `alignment_templates/` directory contents.
   - The existing processed behavior outputs in `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/`.
2. **Never modify files in the legacy repo** `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya`. It is a read-only reference. Work happens in a new repo.
3. **Never modify files Claude Code did not create itself in this consolidation project**, with one exception: inside the new consolidation repo, Claude Code may modify files it created on a previous turn in the same or prior session.
4. **If Claude Code believes an existing analysis output should be overwritten**, it must stop and ask Priya first, describing exactly what would be overwritten and why.
5. **Default migration pattern: copy, do not move.** Legacy notebook → new module = implement in new repo; legacy notebook stays untouched.
6. **Output writes go to new output directories under `stroke_orofacial_pipeline_outputs/`** (e.g. `stroke_orofacial_pipeline_outputs/spout_behavior/`, `stroke_orofacial_pipeline_outputs/dlc_analysis/`) — never on top of existing `session_processing3/` or existing per-animal analysis folders on the server.
7. **Before any large refactor or delete-like operation**, use plan mode (`Shift+Tab` → Plan) and show the plan for approval.
8. **Git discipline:** every change lands as a commit on a feature branch, so anything wrong is one `git revert` away. Never force-push.

---

## 1. PROJECT GOALS (v1 scope)

1. Create one fresh, private GitHub repo that consolidates:
   - Wavesurfer-based spout-behavior processing (currently in `facerhythm_stroke_biomarker_exp_Priya`).
   - Wavesurfer ↔ video ↔ DLC alignment.
   - DLC output loading, centering, filtering, and interpolation.
   - DLC per-bodypart location analyses (tongue, nose, jaw) — both whole-session and reward-aligned.
   - DLC spatial-map / pixel-bin analyses, refactored to accept a "window selector" (whole session OR cue-aligned OR reward-aligned, e.g. (0, 8000) ms post-reward).
   - DLC tongue and jaw kinematics (filter, interpolate, reward/cue-aligned features).
   - A unified statistics pipeline capable of handling the strong between-animal heterogeneity in stroke phenotype severity and recovery timecourse.
   - A unified plotting layer with consistent styling across modules.
2. Eliminate redundancy from the legacy notebooks while preserving every specific analysis Priya currently runs.
3. Cross-platform (macOS + Windows) with a single `paths` abstraction.
4. Well-annotated code, with docstrings and inline comments explaining **why** choices were made and **where the user must edit inputs**. All notebook-level user-edit points live in a clearly-marked "USER INPUTS" cell at the top.
5. A staged migration plan that never risks existing data or existing outputs.

## 1a. NON-GOALS (v1)

- FaceRhythm analyses `[DECIDED, deferred to v2]` — scaffold a placeholder module but write no real code.
- DLC retraining or network changes.
- 2-photon imaging / pan-cortical widefield / striatal photometry code — future modules, not in v1.
- Public release of the repo — stays private initially; design avoids anything that would be blocking for a future public release (no hardcoded usernames in source, no embedded credentials).

---

## 2. EXISTING CODE & DATA INVENTORY

### 2.1 Legacy code locations `[DECIDED]`

**Spout behavior code (Mac, local):**
- Root: `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya`
- Key notebooks (latest-dated filename = canonical when duplicates exist):
  - `batch_process_20260410PS.ipynb` — wavesurfer → session data (licks, rewards, bouts).
  - `batch_process_behavior_report_20260116PS.ipynb` — session data → cross-session figures per animal.
  - `batch_process_alignment_20251216PS.ipynb` — wavesurfer ↔ video ↔ DLC alignment.
  - `playground_analyze_behavior_report_PS20250610.ipynb` — exploratory stats, incl. the 10-day-bin MixedLM/OLS cell flagged for refinement.

**DLC code (server):**
- Root (Mac SMB): `smb://research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`
- Root (Windows UNC): `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\`
- Key notebooks:
  - `20251112_DLC_batch_video_analysis_O2.ipynb` — runs DLC inference on HMS O2, copies outputs to MICROSCOPE.
  - `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` — builds centered parquets (nose / spout midpoint / eyes midpoint), reward-aligned.
  - `20260111_DLC_analysis_build-parquet_tongue.ipynb`
  - `20251117_DLC_analysis_nose.ipynb`
  - `20251117_DLC_analysis_jaw.ipynb`
  - `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` — session-wide pixel-bin stats.
  - `20251201_DLC_analysis_all_bodyparts_2KSD_spatial-maps.ipynb` — exploratory 2-KSD spatial maps.
  - `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` — filter/interpolate tongue + reward-aligned kinematics; also contains master animal metadata (stroke dates, session ranges, exclusions).
  - `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` — same, for jaw; also master metadata.

### 2.2 Data locations `[DECIDED]`

| Data | Mac path (SMB) | Windows path (UNC) |
|---|---|---|
| Server root | `smb://research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/` | `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` |
| DLC output per-animal | `.../DeepLabCut/O2_analysis/PS{NN}/` | `...\DeepLabCut\O2_analysis\PS{NN}\` |
| DLC train config | `.../DeepLabCut/DLC_train_config/` | `...\DeepLabCut\DLC_train_config\` |
| Alignment templates | `.../DeepLabCut/O2_analysis/alignment_templates/` | `...\DeepLabCut\O2_analysis\alignment_templates\` |
| DLC code (legacy) | `.../DeepLabCut/code/` | `...\DeepLabCut\code\` |
| Spout-behavior processed (local) | `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/` | N/A (Mac only) |

**Animals:** `PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55` (8 total).

**Tracked bodyparts (DLC):** medial edge L eye, medial edge R eye, nose, 3 whisker points × L/R (6 total), jaw, tongue, L spout, R spout.

### 2.3 Environments `[DECIDED]`

- **Mac + Windows:** single unified conda env `stroke_orofacial` created from `environment.yml` (Python 3.11, conda-forge primary). Replaces the earlier per-platform pair as of Phase 13 (see MIGRATION_LOG §"Phase 13"). Legacy envs (`frsb` on Mac, `deeplabcut` on Windows) are not touched and run parallel to the new env.
- **O2 (HMS):** inference-only; separate env, not in scope for consolidation.

### 2.4 Canonical master metadata (currently scattered) `[DECIDED]`

Stroke dates, session ranges, session exclusions, and animal IDs are currently re-declared across multiple notebooks and across cells within notebooks. The most recent "master list" lives in `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`. **In the consolidation, this becomes a single versioned YAML file** (`configs/animals.yaml`) and no analysis notebook is allowed to redefine it.

---

## 3. TARGET REPO LAYOUT `[DECIDED, proposal]`

Repo name (pick whatever you like; suggestion): **`stroke_orofacial_pipeline`** — generic enough to hold future neural-recording modules.

```
stroke_orofacial_pipeline/
├── README.md
├── CLAUDE.md                      # data-safety rules + repo conventions; auto-loaded by Claude Code
├── pyproject.toml                 # installable package `stroke_orofacial`
├── environment.yml                # unified conda env (`stroke_orofacial`, Mac + Windows)
├── .gitignore
├── .gitattributes                 # exclude large binaries, set LF line endings
├── docs/
│   ├── DESIGN.md                  # this document
│   ├── DATA_MODEL.md              # session manifest schema, parquet schemas, column dictionaries
│   ├── STATS_PIPELINE.md          # stats design rationale
│   └── MIGRATION_LOG.md           # notebook → module migration tracking
├── configs/
│   ├── paths.yaml                 # machine-agnostic logical-path roots + per-machine mount overrides
│   ├── animals.yaml               # per-animal stroke date, session start/end, session exclusions, recovery-phenotype label (TODO)
│   └── defaults.yaml              # default analysis parameters (likelihood thresholds, smoothing windows, reward window ms, bin sizes, etc.)
├── src/stroke_orofacial/
│   ├── __init__.py
│   ├── paths.py                   # PathResolver — logical → per-machine path
│   ├── manifest.py                # SessionManifest — single source of truth for "what belongs to this session"
│   ├── animals.py                 # loader + dataclasses for animals.yaml
│   ├── spout_behavior/
│   │   ├── __init__.py
│   │   ├── wavesurfer_io.py
│   │   ├── lick_detection.py
│   │   ├── trial_segmentation.py
│   │   ├── bouts.py
│   │   └── session_processing.py  # replaces batch_process_20260410PS
│   ├── alignment/
│   │   ├── __init__.py
│   │   ├── timebase.py            # one definition of "session time" + converters ws↔video↔DLC
│   │   ├── frame_sync.py
│   │   └── templates.py           # reads alignment_templates/
│   ├── dlc_io/
│   │   ├── __init__.py
│   │   ├── loaders.py             # H5/CSV → tidy DataFrame; likelihood gating
│   │   ├── centering.py           # nose / spout-midpoint / eyes-midpoint centering
│   │   └── parquet.py             # read/write centered parquets
│   ├── dlc_kinematics/
│   │   ├── __init__.py
│   │   ├── filters.py             # per-bodypart smoothing + interpolation
│   │   ├── features.py            # tongue protrusion amplitude, velocity, angle, jaw opening, coordination
│   │   └── reward_aligned.py      # per-reward-event kinematic windows
│   ├── dlc_spatial/
│   │   ├── __init__.py
│   │   ├── pixel_bins.py
│   │   ├── heatmaps.py
│   │   ├── difference_maps.py     # difference proportions + permutation stats
│   │   └── window_selector.py     # whole session | cue-aligned | reward-aligned (0, 8000) ms | custom
│   ├── stats/
│   │   ├── __init__.py
│   │   ├── normalization.py       # baseline Z, log ratio, rank, etc.; floor-effect safe
│   │   ├── recovery_epochs.py     # recovery phenotype classification (TODO section below)
│   │   ├── models.py              # MixedLM, GLMM wrappers, OLS fallback
│   │   ├── multiple_comparisons.py
│   │   └── permutation.py
│   ├── figures/
│   │   ├── __init__.py
│   │   ├── style.py               # one place for colors/fonts/sizes
│   │   ├── behavior_plots.py
│   │   ├── kinematic_plots.py
│   │   └── spatial_plots.py
│   ├── reports/
│   │   ├── __init__.py
│   │   └── behavior_report.py     # replaces batch_process_behavior_report_20260116PS
│   └── dlc_inference_o2/          # standalone; runs only on O2 with GPU
│       ├── __init__.py
│       ├── README.md              # explicit: this submodule is O2-only
│       └── batch_video_analysis.py
├── notebooks/
│   ├── 00_session_processing.ipynb
│   ├── 01_alignment.ipynb
│   ├── 02_behavior_report.ipynb
│   ├── 10_dlc_build_parquets.ipynb
│   ├── 11_dlc_spatial_whole_session.ipynb
│   ├── 12_dlc_spatial_reward_aligned.ipynb
│   ├── 13_dlc_kinematics_tongue.ipynb
│   ├── 14_dlc_kinematics_jaw.ipynb
│   └── 20_stats_cross_animal.ipynb
├── scripts/
│   └── (thin CLI entry points that mirror each notebook for batch runs)
└── tests/
    ├── fixtures/                  # tiny synthetic wavesurfer + DLC samples
    └── test_*.py
```

**Notebook convention:**

- Each notebook has a single **USER INPUTS** cell at the top, clearly banner-commented, containing only variables a user would change (e.g. animal list, date range, reward window ms). Everything below that cell imports from `stroke_orofacial` and is generic.
- Each analysis function lives in `src/` and is imported into the notebook. Notebooks do not contain analytical code; they orchestrate.

---

## 4. CORE ABSTRACTIONS (the things to build first)

Build these before migrating any analysis. They are what make the rest of the repo cohesive.

### 4.1 `paths.py` / `configs/paths.yaml` `[DECIDED]`

A `PathResolver` class that:
- Loads `configs/paths.yaml` which defines **logical roots**:
  - `microscope_server` (the root shared across mac SMB, windows UNC).
  - `local_processed_spout` (currently Mac-only, `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/`).
- Auto-detects the machine via `platform.system()` + user-overrideable env var (`STROKE_PIPELINE_MACHINE`) and picks the correct concrete mount:
  - Mac → `/Volumes/MICROSCOPE/Priya/` (or `smb://...` form — confirm what appears after auto-mount).
  - Windows → `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\`.
- Exposes convenience methods: `resolver.dlc_output_dir(animal="PS46")`, `resolver.alignment_templates_dir()`, `resolver.session_processing_out(version="v2")`.
- **Never** hardcodes an absolute path inside any analysis module.
- All logical paths documented in `DATA_MODEL.md`.

**Open detail `[TO BE CONFIRMED]`:** On Mac, does the SMB mount show up at `/Volumes/MICROSCOPE` or under a different mount name? Claude Code should check and bake it into the default `paths.yaml` after reading.

### 4.2 `SessionManifest` `[DECIDED, schema below]`

Per-session single source of truth, cached to disk in the new outputs area.

```python
@dataclass
class SessionManifest:
    session_id: str          # canonical: f"{animal}_{yyyymmdd}" (derived, reproducible)
    animal: str              # e.g. "PS46"
    date: datetime.date      # session date parsed from any naming scheme
    day_relative_to_stroke: int | None   # from configs/animals.yaml; None pre-enrollment or excluded
    phase: Literal["baseline", "post_stroke"]  # derived from day_relative_to_stroke
    wavesurfer_file: Path
    video_files: list[Path]  # may be multiple per session
    dlc_h5_files: list[Path]
    dlc_csv_files: list[Path]
    alignment_template: Path | None
    # plus any excluded flag + reason, and arbitrary extra metadata
    excluded: bool
    exclusion_reason: str | None
```

Built by a `build_manifest(animal: str, date: date) -> SessionManifest` function that:
- Resolves paths via `PathResolver`.
- Tolerates mixed naming (date in filename OR directory) by trying a prioritized list of regex patterns, all YYYYMMDD.
- Fails loudly if any required file is missing, with a clear error message naming which file and where it was looked for.

Every analysis module takes `SessionManifest` as its input contract, not raw paths. This is the single biggest win for code clarity.

### 4.3 `configs/animals.yaml` `[DECIDED, authoritative going forward]`

Replaces the scattered animal-metadata cells. Example shape:

```yaml
# configs/animals.yaml
PS46:
  stroke_date: 2025-09-10   # YYYY-MM-DD; required
  sessions:
    start: 2025-08-15
    end:   2026-03-01
  exclusions:
    - { date: 2025-09-12, reason: "video capture error, frame drops" }
    - { date: 2025-10-03, reason: "wavesurfer crashed mid-session" }
  recovery_phenotype: null   # filled in later by recovery_epochs module; see §6
PS47: { ... }
...
```

**Initial population rule:** Claude Code reads the current master-list cells in `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` (and cross-checks against the jaw notebook and the spout-behavior notebooks) and transcribes them into `animals.yaml`. The generated YAML must be reviewed and signed off by Priya before any analysis uses it.

### 4.4 Time base / alignment contract `[DECIDED]`

There is exactly one "session time" (seconds, float, starts at 0 = wavesurfer session start). Three converters:

- `ws_samples → session_time` (divide by sample rate; `[TO BE CONFIRMED]` what sample rate, likely 20 kHz or 40 kHz).
- `video_frame_index → session_time` (from Flea3 trigger/strobe line in wavesurfer; Claude Code to read current alignment notebook to codify this).
- `dlc_frame_index → session_time` (equals video_frame_index by construction).

All analyses operate in `session_time` internally. Every dataframe has a `session_time_s` column. Any per-frame data also keeps `frame_index` for backtracking.

---

## 5. NOTEBOOK → MODULE MIGRATION MAP `[PROPOSAL, TO BE CONFIRMED ONCE CODE IS READ]`

| Legacy notebook | New module(s) | Notes |
|---|---|---|
| `batch_process_20260410PS.ipynb` | `spout_behavior/session_processing.py` + `notebooks/00_session_processing.ipynb` | Preserve trial segmentation and bout definitions exactly; factor out lick-detection thresholds to `configs/defaults.yaml`. |
| `batch_process_behavior_report_20260116PS.ipynb` | `reports/behavior_report.py` + `notebooks/02_behavior_report.ipynb` | Keep every current figure; refactor repeated plotting into `figures/behavior_plots.py`. |
| `batch_process_alignment_20251216PS.ipynb` | `alignment/*` + `notebooks/01_alignment.ipynb` | Single place for ws↔video↔DLC alignment. Consumes `alignment_templates/` read-only. |
| `playground_analyze_behavior_report_PS20250610.ipynb` (10-day-bin cell) | `stats/*` + `notebooks/20_stats_cross_animal.ipynb` | The 10-day-bin MixedLM/OLS cell is the seed; full redesign per §6. |
| `20251112_DLC_batch_video_analysis_O2.ipynb` | `dlc_inference_o2/batch_video_analysis.py` | Runs on O2 only; clearly documented in its README as a standalone tool. |
| `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` | `dlc_io/*` + `notebooks/10_dlc_build_parquets.ipynb` | Centering options (nose / spout midpoint / eyes midpoint) expressed as enums; reward-alignment uses shared `window_selector`. |
| `20260111_DLC_analysis_build-parquet_tongue.ipynb` | Merged into `dlc_io/parquet.py` | Same family as above; redundant branches merged. |
| `20251117_DLC_analysis_nose.ipynb`, `…_jaw.ipynb` | `dlc_spatial/*` + `notebooks/11_dlc_spatial_whole_session.ipynb` | One notebook runs all bodyparts via a loop; no per-bodypart notebook needed. |
| `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` | `dlc_spatial/pixel_bins.py` + shared stats | Stats moved into `stats/`. |
| `20251201_DLC_analysis_all_bodyparts_2KSD_spatial-maps.ipynb` | `dlc_spatial/heatmaps.py` (exploratory flag) | Kept, marked exploratory in docstrings. |
| `20260203_…_tongue.ipynb`, `20260416_…_jaw.ipynb` | `dlc_kinematics/*` + `notebooks/13_…`, `14_…` | The master animal metadata cells → `configs/animals.yaml`. Kinematic filters/features → `dlc_kinematics/`. Stats cells → `stats/`. |

**After migration**, a `docs/MIGRATION_LOG.md` tracks, for each legacy notebook, which commit in the new repo subsumes it and any behavior changes (there should be **zero** silent behavior changes; any intentional change is called out in the log).

---

## 6. STATISTICS PIPELINE DESIGN

This is the part that needs the most thought. The scientific problem is hard and no single off-the-shelf recipe fits. This section lays out the architecture and flags the choices for deliberate decision-making; some are `[TODO]` on purpose.

### 6.1 The heterogeneity problem (restated for the record)

Post L-VLS stroke phenotypes range from:
- **Mild/transient**: 1 day of directionally inaccurate licking, then recovery.
- **Severe/staged**: weeks of near-zero licking, then partial recovery of L-licks first, later partial (incomplete) recovery of R-licks.
- Intermediates thereof.

Naive pooling with a MixedLM on "day post-stroke" will (a) drown mild animals in variance from severe animals and (b) under-weight the early-post-stroke biological signal where severe animals are at floor. Any meaningful cross-animal comparison must respect these trajectories.

### 6.2 Architectural decisions `[DECIDED]`

1. **Three orthogonal axes** structure the stats pipeline, and every analysis selects one value per axis:
   - **Endpoint axis:** what is being measured (lick rate, first-lick accuracy, tongue protrusion amplitude, jaw opening velocity, pixel-bin occupancy, etc.). Endpoints are registered in a small registry so new ones drop in with metadata (units, distributional expectations, null hypothesis).
   - **Time axis:** raw calendar day, day-relative-to-stroke, **recovery epoch** (see §6.3), or fixed bins (e.g. 10-day).
   - **Comparison axis:** pre vs. post, across-animal pooled, per-animal trajectory, or phenotype-group comparison.
2. **All endpoints produce the same tidy-data shape** (long format: animal, session_time / day / epoch, endpoint_name, value, n_trials, …), so the stats layer is endpoint-agnostic.
3. **Normalization is a named strategy**, not an ad-hoc transform. Strategies live in `stats/normalization.py` and are applied before modeling. Each strategy is explicit about what it does at the floor (zero baseline or zero value).

### 6.3 Recovery epoch classification `[TODO — major scientific design task]`

Animals should be re-aligned not only to calendar time post-stroke but also to **data-driven recovery phases**. This is the central methodological piece to work through. Directions to evaluate:

1. **Rule-based epochs per animal** using a small number of quantitative criteria applied to lick behavior (e.g. `baseline`, `acute` (first n days with ≤X% of baseline lick rate), `partial_L_recovery` (L-lick rate crosses Y fraction of baseline for Z consecutive sessions), `R_recovery_attempt`, `chronic_stable`). Pros: transparent, reproducible from `animals.yaml` + rules. Cons: threshold-sensitive.
2. **Changepoint detection** on a derived per-session summary statistic per animal (e.g. PELT or Bayesian online changepoint on lick rate or accuracy). Pros: data-driven. Cons: interprets changepoints as biology only if the endpoint chosen is the right summary.
3. **Hidden Markov / latent-state models** over session-level features, with states interpreted post hoc. Pros: principled, handles multi-feature state. Cons: heavier, requires justification.
4. **Hybrid:** rule-based epoch skeleton, refined by changepoint on a canonical endpoint; encoded as a per-animal, per-date `epoch` column in the manifest.

**Concrete next action** when work on stats starts: pick 2–3 canonical per-session endpoints (e.g. `overall_lick_rate`, `first_lick_accuracy_L`, `first_lick_accuracy_R`) and inspect each animal's trajectory side by side before choosing an epoch-classification method.

### 6.4 Normalization strategies `[DECIDED MENU, selection per-analysis]`

Each endpoint analysis chooses one of:

- `baseline_z` — z-score vs. that animal's pre-stroke baseline sessions. Floor handling: if baseline SD = 0 or value = 0 structurally, report as censored.
- `baseline_ratio` — `value / baseline_mean`. Undefined when baseline_mean = 0; caller must pick an alternative.
- `baseline_difference` — `value − baseline_mean`. Safe at floor, loses scale information.
- `log1p_ratio` — `log1p(value) − log1p(baseline_mean)`. Often the right choice for rates with structural zeros.
- `rank_within_animal` — ordinal rank of the session's endpoint among that animal's sessions. Robust to scale heterogeneity across animals.
- `none` — raw, for models that include animal random effects and handle scale differences via random slopes.

### 6.5 Structural zeros vs. missing data `[DECIDED]`

- A session where the animal did not lick at all is a **real zero**, not missing. The stats module must never drop these.
- A session **excluded for technical reasons** (listed in `animals.yaml`) is missing and is dropped.
- A session where the animal licked but an endpoint is undefined (e.g. "first-lick accuracy given no first lick") is **NaN with a documented reason**, and the endpoint's aggregator decides the rule for that case.

### 6.6 Models `[DECIDED PROGRESSION]`

Apply in this order and use the first one whose assumptions are defensible for the endpoint:

1. **Descriptive first**: per-animal trajectory plots, cross-animal mean ± bootstrap CI by epoch or day-bin. No p-values yet.
2. **Permutation / cluster-based tests** on epoch differences within animal, then across animals. Avoids parametric assumptions, natural fit for heterogeneity.
3. **Linear mixed models** with animal as random intercept (and random slope on epoch when identifiable), fixed effect = epoch or day-bin. OLS fallback when MixedLM fails to converge (your current pattern) — keep the fallback but log which branch fired.
4. **Generalized linear mixed models** for counts (e.g. lick counts, bout counts) with Poisson/NB families.
5. **Trajectory models** (functional data / GAMM) for reward-aligned kinematic time series, when per-trial endpoints are not enough.

All model outputs go through a unified reporter that yields a dataframe: `endpoint, comparison, effect_size, ci_low, ci_high, stat, df, p_raw, p_adj, n_animals, n_sessions, n_trials, normalization, model_used, fallback_fired`.

### 6.7 Multiple comparisons `[DECIDED]`

- Within a figure, use **Benjamini-Hochberg FDR** across the family of simultaneous tests shown.
- Across figures, families are declared explicitly in the analysis notebook; the stats module records the family a test belongs to.
- Significance annotations on plots **use adjusted p-values**, and the raw p-values remain in the output dataframe.

---

## 7. STAGED MIGRATION PLAN

Each phase ends with a commit on a branch + a short section added to `MIGRATION_LOG.md`. Nothing touches source data at any phase.

**Phase 0 — Repo skeleton (Claude Code, first session).**
- Create the directory tree.
- Write `README.md`, `CLAUDE.md`, empty `docs/*`, `configs/defaults.yaml`.
- `pyproject.toml` with `stroke_orofacial` package, minimal deps.
- `environment-mac.yml` generated from current `frsb` env (via `conda env export --from-history`) and `environment-windows.yml` generated from current `deeplabcut` env.
- `.gitignore`, `.gitattributes`.
- Exit criterion: `pip install -e .` works in `frsb`; empty test suite passes.

**Phase 1 — Paths + manifest + animals metadata.**
- Implement `PathResolver`, `SessionManifest`, `animals.yaml` loader.
- Port master animal metadata from `20260203_…_tongue.ipynb` into `animals.yaml` (Claude Code reads the legacy notebook, transcribes, and Priya reviews the YAML before merge).
- Tests against a couple of real session folders (read-only).

**Phase 2 — Spout behavior.**
- Port `batch_process_20260410PS.ipynb` into `spout_behavior/*` + notebook `00_session_processing.ipynb`.
- Outputs go to a **new** directory (`stroke_orofacial_pipeline_outputs/spout_behavior/`) — never overwriting `session_processing3/`.
- Verify byte-level or value-level parity with a few sessions' `session_processing3/` outputs before moving on.

**Phase 3 — Alignment.**
- Port `batch_process_alignment_20251216PS.ipynb` into `alignment/*` + notebook `01_alignment.ipynb`.

**Phase 4 — DLC I/O + centering.**
- Port the parquet-build notebooks.
- Match existing parquet schemas exactly; diff outputs against existing parquets on a sample session.

**Phase 5 — DLC spatial (whole session).**
- Port pixel-bin + spatial-map + difference-map analyses.
- Produce side-by-side reproducibility check against legacy notebooks.

**Phase 6 — DLC spatial (reward-aligned).**
- Implement `window_selector` with reward-aligned (0, 8000) ms default and parameterizable.
- Generalize all spatial analyses to accept a window selector.
- **Prereq:** `_find_idx_within_eps` (currently private inside `src/stroke_orofacial/spout_behavior/bouts.py`) must be factored into a shared package-private helper at `src/stroke_orofacial/_utils/indexing.py` so reward-aligned peri-event extraction can import it without depending on the lick-bout module. Trivial refactor (~20 lines moved, two import sites updated, byte-identical behavior), executed as its own PR before Phase 6 code writes begin. The same half-open `[v - eps[0], v + eps[1])` convention serves both the lick-bout window used in `spout_behavior` and the 8-s-post-reward windows used downstream in Phase 6 / Phase 7 kinematics. Matches the existing `_utils/bool_indexing.py` vendoring convention (package-private, bnpm-provenance-documented).

**Phase 8a — Spout behavior report.** *(Moved ahead of Phase 7 for mid-experiment usability.)*
- Port the spout-behavior-only portions of `batch_process_behavior_report_20260116PS.ipynb` into `reports/spout_behavior_report.py` + notebook `02a_spout_behavior_report.ipynb`.
- Wavesurfer QC figures per session (deferred from Phase 2).
- Cross-session spout metrics: first-lick accuracy, latencies (per-side), correct/incorrect counts, bout structure, L/R bias, lickiness, switchiness.
- Per-animal time course figures (each metric across sessions).
- Consumes ONLY Phase 2 (+ 2.5) outputs. **Zero DLC dependency** — runnable mid-experiment to support decisions like stroke-induction timing.
- Output directory: `stroke_orofacial_pipeline_outputs/behavior_report/spout/`.

**Phase 7 — DLC kinematics.**
- Port tongue and jaw filter/interpolate + features + reward-aligned analyses.

**Phase 8b — DLC behavior report.**
- Port the DLC-dependent portions of `batch_process_behavior_report_20260116PS.ipynb` (and any DLC-summary cells from kinematics notebooks) into `reports/dlc_behavior_report.py` + notebook `02b_dlc_behavior_report.ipynb`.
- Cross-session DLC kinematic summaries (tongue/jaw amplitude and velocity time courses).
- Cross-session spatial-map grids (bodyparts × days layouts).
- Integrated spout-DLC figures where useful (e.g., lick rate overlaid with tongue kinematics).
- Consumes Phases 4-7 outputs plus Phase 8a.
- Output directory: `stroke_orofacial_pipeline_outputs/behavior_report/dlc/`.

**Phase 9 — Stats pipeline.**
- Recovery epoch classification (§6.3) — first concrete design decision round with Priya.
- Normalization + models + multiple-comparisons framework.
- Re-run the 10-day-bin analysis through the new pipeline; verify parity or document deliberate improvements.

**Phase 10 — Cleanup, scientific end-to-end audit, & docs.**
- Prune anything obsolete (dead code, stale stubs, unused imports).
- Finalize `DATA_MODEL.md` and `STATS_PIPELINE.md`.
- **Scientific end-to-end audit on one exemplar animal** (PS46): enumerate every output the consolidated pipeline produces (per-session NPZs, parquets, figures, cross-session aggregates, params.json provenance records) across all phases. Map each output to its scientific purpose. Identify gaps vs. Priya's research needs, excesses that aren't used, and desired edits. Gaps become either pre-v0.1.0 fixes or post-v0.1.0 backlog items. This audit happens in Cowork, not Claude Code — it's review + decision work, not code editing.
- A **mid-consolidation audit** (smaller-scope version of the above) is scheduled separately after Phase 6 per `docs/DECISIONS.md` "End-to-end output audits scheduled at two points." Phase 10's audit is the comprehensive final pass.
- Tag `v0.1.0`.

---

## 8. ENVIRONMENT SETUP

**Current state (post-Phase 13):** a single unified `environment.yml` creates the `stroke_orofacial` conda env on both macOS and Windows. See README §"Setup" for the install recipe. Legacy per-platform envs (`frsb` on Mac, `deeplabcut` on Windows) are intentionally left intact and run parallel to the new env — `deeplabcut` remains the correct env for DLC training / O2 inference / Keypoint-MoSeq work, and `frsb` is preserved primarily so strict-port parity tests for the vendored bnpm helpers can run against live bnpm on demand.

**Historical note (Phase 0 → Phase 13):** the repo originally shipped a per-platform pair (`environment-mac.yml` generated from `frsb`, `environment-windows.yml` generated from `deeplabcut`). Phase 13 consolidated these into the single `environment.yml` after (a) auditing real imports and (b) vendoring four pure-numpy helpers out of `bnpm` so the env closure no longer depends on torch (which broke pytest collection on Windows via an OpenMP runtime collision). See `docs/DECISIONS.md` entries "2026-04-19 Phase 13 env unification" and "2026-04-20 Phase 13 vendor bnpm" and `docs/MIGRATION_LOG.md` Phase 13 for the full trail.

---

## 9. GIT STRATEGY

1. Create a new **private** GitHub repo named (suggestion) `stroke_orofacial_pipeline`.
2. Initialize locally first (`git init` in the new directory), commit the skeleton on `main`, then push to GitHub.
3. Each migration phase = its own feature branch off `main`, PR-merged (even as a solo developer — it keeps the migration log clean and reversible).
4. `.gitignore` excludes: everything in `data/`, `outputs/`, `*.parquet`, `*.h5`, `*.mp4`, `*.avi`, `*.pkl`, `.ipynb_checkpoints/`, `__pycache__/`, `.DS_Store`.
5. Use `nbstripout` (optional) so notebook outputs don't bloat the git history.

---

## 10. CLAUDE CODE: FIRST-TIME USER SETUP (macOS)

### 10.1 Install

In Terminal on your Mac, either:
```bash
curl -fsSL https://claude.ai/install.sh | bash
```
or
```bash
brew install --cask claude-code
```

### 10.2 Authenticate

Run `claude` from any directory; a browser window opens for login. You can authenticate via your **Claude Pro/Max subscription** (claude.com login) or via a **Claude Console / API** account. Billing specifics change — when in doubt, check the current `https://code.claude.com/docs/en/authentication.md` and `https://platform.claude.com/docs/en/about-claude/pricing.md` pages before committing to a plan. If you have a Pro/Max subscription already, start there — it's the cheapest entry point and you can switch to API billing later if you need more throughput.

### 10.3 Terminal vs. desktop vs. IDE

- **Terminal (CLI)** is the primary interface and is sufficient for this project. Use it unless you have a specific reason otherwise.
- A **desktop app** variant exists (parallel sessions, visual diff review). Nice-to-have; not required.
- A **VS Code extension** and **JetBrains plugin** exist and are useful if you already work in those editors — they give inline diff review and @-file mentions. If you already use VS Code, install the extension and use it as a coding surface on top of the CLI.

My recommendation for this project: **start in Terminal**. Once you're comfortable, optionally add the VS Code extension so diffs are easier to review.

### 10.4 First launch

```bash
# create the new repo directory
mkdir -p ~/Github/stroke_orofacial_pipeline
cd ~/Github/stroke_orofacial_pipeline

# (optional but recommended) create an empty git repo now
git init -b main

# launch Claude Code in this directory
claude
```

The `cd` matters: Claude Code anchors to the current working directory.

### 10.5 `CLAUDE.md` — project-level memory

Claude Code auto-loads a file called `CLAUDE.md` at the project root at the start of every session. This is where the data-safety rules belong so they're re-read every time.

**First thing to do inside the new repo:** save the "Ground Rules" and "Repo Conventions" sections of this doc into `CLAUDE.md`. Concretely, paste the entire §0 "DATA SAFETY GROUND RULES" above, plus a short "Conventions" section:

```markdown
# CLAUDE.md

## Ground Rules (read every session)
[paste §0 here verbatim]

## Repo Conventions
- Code lives in `src/stroke_orofacial/`; notebooks orchestrate, they do not contain analytical code.
- No absolute paths in source; use `PathResolver`.
- No hardcoded animal metadata; load from `configs/animals.yaml`.
- Every analysis output goes to a new output directory, not on top of an existing one.
- Before any refactor that touches >5 files, propose a plan and wait for approval.
```

You can also reference this larger design doc inline: `read docs/DESIGN.md and summarize the migration phases` — Claude Code will read and honor it.

### 10.6 Plan mode (use liberally early on)

Press **Shift+Tab** inside a Claude Code session to cycle permission modes. Choose **Plan**. In plan mode, Claude Code can read anything but cannot write or run destructive commands. It produces a plan you approve, then switches to execution. For a cautious refactor project like this, use plan mode for Phases 0–2 at minimum.

Alternative: launch directly into plan mode with `claude --permission-mode plan`.

### 10.7 Permissions defaults

Out of the box, Claude Code asks before file edits and shell commands. Keep that default for this project. You can allow specific trusted commands (e.g. `pytest`, `git status`) without prompting by editing `.claude/settings.json` once you've built trust.

### 10.8 Accessing the MICROSCOPE server from within Claude Code

On macOS, once the SMB share is mounted in Finder, it appears under `/Volumes/<share_name>/`. Claude Code can read files there if you reference them by absolute path and grant permission on first access. **Recommendation:** mount the share once in Finder (Cmd+K in Finder, paste the `smb://…` URL), confirm the mount point (e.g. `/Volumes/MICROSCOPE`), then tell Claude Code the mount point when you set up `configs/paths.yaml`.

Gotcha: if the share is not mounted, Claude Code will see `/Volumes/MICROSCOPE` as nonexistent. Make it a habit to mount the share before `claude` sessions that need it.

### 10.9 Memory across sessions

- `CLAUDE.md` at the repo root auto-loads every session → that's where persistent rules go.
- Claude Code also auto-saves incremental learnings. If you want durable facts remembered across sessions (e.g. "the SMB mount on Priya's Mac is at `/Volumes/MICROSCOPE`"), tell Claude Code to record that in `CLAUDE.md` or use the `/memory`-family commands.

### 10.10 Useful slash commands

Type `/` inside Claude Code to see all. Ones worth knowing up front:

- `/init` — guided creation of `CLAUDE.md`.
- `/plan` — activate plan mode mid-session.
- `/resume` — resume a previous session.
- `/model` — switch models (Opus for deep reasoning, Sonnet for day-to-day, Haiku for simple edits).
- `/context` — see what's using your context window.
- `/config` — configuration including thinking depth, auto-update channel.
- `/clear` — reset the conversation (keeps `CLAUDE.md`).
- `/mcp` — list MCP servers connected.

### 10.11 Git integration

Claude Code understands your current branch and uncommitted changes; it can run `git status`, `git diff`, `git add`, `git commit` and will follow the repo's conventions once they're in `CLAUDE.md`. For GitHub PRs it uses `gh`, which you'll want installed: `brew install gh && gh auth login`.

---

## 11. FIRST PROMPTS TO USE IN CLAUDE CODE

### 11.1 Initial "handshake" prompt (session 1)

Paste this at the top of your first Claude Code session in the new empty repo:

> I'm starting a consolidation of a messy research codebase into this new repo. Please read `docs/DESIGN.md` (I'll create it in a moment by pasting a markdown file) and `CLAUDE.md` (same). Your job in this session is Phase 0 only: create the repo skeleton exactly as specified in §3 and §7 of the design doc. Do **not** touch anything outside this directory. Do **not** read or modify anything under `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya`, `/Users/Priya2/Documents/data/`, or `/Volumes/MICROSCOPE/`. Before you write any file, enter plan mode and show me your plan.

### 11.2 Practical session 1 steps

1. `mkdir -p ~/Github/stroke_orofacial_pipeline && cd ~/Github/stroke_orofacial_pipeline`
2. `git init -b main`
3. Create `docs/DESIGN.md` and paste this entire document into it.
4. Create `CLAUDE.md` with the contents described in §10.5.
5. Run `claude`.
6. Paste the handshake prompt from §11.1.
7. When Claude Code asks for plan-mode approval, read the plan carefully. If anything violates §0 or deviates from §3/§7, say "stop, revise the plan to …".
8. Approve and let it build the skeleton.
9. First commit on `main`, then create GitHub repo (private) and `git push`.

### 11.3 Session 2+ prompts (template)

> We are on Phase N of `docs/DESIGN.md`. Please:
> 1. Summarize in 5 bullets what Phase N requires.
> 2. Enter plan mode and propose the file-by-file changes you will make.
> 3. Wait for my approval before writing.
> Constraints: (a) no source data modifications per §0; (b) outputs go to new directories under `stroke_orofacial_pipeline_outputs/`; (c) preserve analytical behavior of legacy notebooks unless I explicitly approve a change.

### 11.4 "Safety check" prompt to sprinkle in

> Before proceeding, confirm in 2 sentences that the change you're about to make does not touch any file under the source-data paths listed in `CLAUDE.md`.

---

## 12. OPEN QUESTIONS / DECISIONS DEFERRED

These are `[TODO]` on purpose; they need either more code-reading or Priya's scientific input before locking in.

1. Exact mount point of the SMB share on Priya's Mac (e.g. `/Volumes/MICROSCOPE`?).
2. Wavesurfer sample rate and which analog/digital channel carries the Flea3 frame trigger/strobe.
3. Canonical lick-detection method currently in use (threshold on which channel, debounce window) — to be read from `batch_process_20260410PS.ipynb`.
4. DLC likelihood threshold currently in use and per-bodypart variation — to be read from existing DLC notebooks.
5. Recovery epoch classification scheme (see §6.3).
6. Whether there are other master-metadata cells (beyond the tongue/jaw DLC notebooks) that must be reconciled into `animals.yaml`.
7. Whether DLC re-inference is ever expected inside the consolidated repo (decision: probably no, keep `dlc_inference_o2/` as a standalone tool).
8. Whether to use `nbstripout` and/or Jupytext for notebooks.
9. Target Python version (suggest 3.11; must match what DLC and the `frsb` env tolerate).

---

## 13. A NOTE ON SCOPE DISCIPLINE

This project is tractable only if each migration phase closes cleanly. The two most common ways these refactors go wrong:

1. **Silent behavior changes** in ported code. Mitigation: every phase includes a parity check against legacy outputs on at least one session, documented in `MIGRATION_LOG.md`.
2. **Scope creep into stats while migrating I/O.** Mitigation: Phases 2–8 are strictly "port and tidy"; Phase 9 is where the stats pipeline is redesigned. Resist the urge to rewrite stats during earlier phases.

---

## 14. CONVENTIONS

Project-wide invariants that every module must honor. Separate from module-specific rules (those live in module docstrings).

### 14.1 L/R frame: wavesurfer (experimenter) vs. mouse

The wavesurfer acquisition records four side-labeled digital channels: `Lick_L`, `Lick_R`, `Reward_L`, `Reward_R`. These labels are in the **experimenter frame** — physical left/right from the experimenter's perspective facing the rig. Whether those labels correspond to the *mouse's* left/right sides depends on the rig layout (camera/spout mirroring). The entire PS46–PS55 cohort was acquired on a mirrored rig: **wavesurfer L = mouse R, wavesurfer R = mouse L**. Future cohorts acquired on a matched-orientation rig will have wavesurfer L = mouse L.

The project handles this via **boundary-layer translation** (introduced by task #17, 2026-04-20):

- **Internal pipeline arithmetic stays on the wavesurfer frame.** Every Phase 2–8a module (lick detection, bout detection, criteria computation, endpoint aggregation) keeps side-keyed dicts and arrays in wavesurfer frame throughout. This preserves byte-for-byte parity against the frozen Phase 3/4/5/6 baselines and means no churn inside the logic modules.
- **Translation happens at every output emission boundary.** Just before an NPZ / JSON / parquet is written, the emitter applies [`to_mouse_frame`](../src/stroke_orofacial/lr_convention.py) to side labels and [`stamp_side_convention`](../src/stroke_orofacial/lr_convention.py) to payload metadata. The emitted artifact carries mouse-frame labels and the convention metadata so downstream readers can assert the frame.
- **The flag lives on `AnimalInfo`.** `configs/animals.yaml` carries `wavesurfer_sides_match_mouse_sides: bool` per animal (default `False`, fail-conservative for the current cohort). `SessionManifest` copies the flag from `AnimalInfo` at `build_manifest()` time so every orchestrator has it without re-loading the config.
- **Every stamped artifact carries two scalars**: `wavesurfer_sides_match_mouse_sides` (bool) and `side_convention_version` (int, currently `1`). The version bumps on any change to the scheme itself (e.g., renaming the scalars, adding a third side category). Downstream code gates on the version to refuse artifacts it doesn't understand.
- **Consumers must never un-flip** in production code paths. The emitted mouse-frame labels are the canonical artifact contract; any code that reads an NPZ or JSON should treat `"L"` as mouse-L, full stop. The only exception is test code that compares against the pre-task-#17 `session_processing3` baselines (which are wavesurfer-frame) — see [`tests/test_session_processing.py::_unflip_new_to_wavesurfer_frame`](../tests/test_session_processing.py) for the test-side helper.

**Implications:**

- When a notebook loads `licks_and_rewards.npz` and reads `Lick_L`, the array is mouse-L lick indices on every post-task-#17 artifact. This differs from the `session_processing3` legacy artifacts, which are wavesurfer-frame.
- When plotting output, side labels on axes (`"L"`, `"R"`) already refer to the mouse — no additional translation needed.
- When porting a legacy notebook that loaded wavesurfer data directly and applied its own flip (like `20260203_..._tongue.ipynb` cell 25's `ws_lick_mouseL = lk["Lick_R"]`), the new code should load from the consolidated NPZ and skip the ad-hoc flip — the emit boundary already did it.

See `docs/MIGRATION_LOG.md` "Task #17 — Wavesurfer L/R ↔ mouse-frame boundary-layer translation" for the full migration narrative and `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` for the re-emit procedure when a yaml flag flips.

---

End of design doc. When you're ready, follow §11.2 in Claude Code.
