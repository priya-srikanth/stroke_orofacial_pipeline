# stroke_orofacial_pipeline

Consolidated analysis pipeline for post-stroke orofacial motor plasticity in mice.

Covers spout-behavior processing (wavesurfer), video/DLC alignment, DLC bodypart analyses
(spatial maps, kinematics), and cross-animal statistics.

## Setup (macOS + Windows)

A single unified `environment.yml` creates the `stroke_orofacial` env on
both platforms (Python 3.11, conda-forge primary).

```bash
# Create the conda environment
conda env create -f environment.yml

# Activate
conda activate stroke_orofacial

# Install the package in editable mode
pip install -e .

# Install pywavesurfer without pulling its pinned h5py==3.8.0 (would
# collide with the conda HDF5 stack). Its runtime h5py usage is basic
# and works against any modern h5py.
pip install pywavesurfer --no-deps
```

The legacy per-platform envs (`frsb` on macOS, `deeplabcut` on Windows)
are NOT touched by this install — they run parallel to the new env.
`deeplabcut` remains the correct env for DLC training / O2 inference /
Keypoint-MoSeq work.

**Windows note:** `conda env create` defaults the env prefix to the
per-user `C:\Users\<user>\.conda\envs\` rather than
`C:\ProgramData\anaconda3\envs\` when the latter is write-locked to
non-admin shells. This matches where `deeplabcut` already lives on
Priya's Windows box and is the recommended location.

## Project structure

- `src/stroke_orofacial/` — All analysis code (importable package).
- `notebooks/` — Orchestration notebooks; no analytical code, just imports and USER INPUTS.
- `configs/` — YAML configs for paths, animal metadata, and analysis defaults.
- `docs/` — Design doc, data model, stats rationale, migration log.
- `tests/` — Test suite.
- `scripts/` — CLI entry points (thin wrappers around notebook workflows).
- `pipeline_outputs/` — All analysis outputs (lives on MICROSCOPE server, not in this repo).

## Running the pipeline (new-user walkthrough)

### Prerequisites

1. **Env activated:** `conda activate stroke_orofacial` (per Setup section above; verify `which python` points under `.conda/envs/stroke_orofacial/`).
2. **MICROSCOPE mounted:** the pipeline reads + writes under `pipeline_outputs/` on the MICROSCOPE network volume. Confirm mount + access before running any notebook.
3. **Animals registered:** verify `configs/animals.yaml` has entries for the animals you want to process (per-animal `sessions:` date ranges + metadata).
4. **Optional but recommended:** read `docs/DESIGN.md` for the architectural overview and `docs/DATA_MODEL.md` for the canonical schema of every output type.

### Notebook order

Each notebook has a single banner-commented "USER INPUTS" cell at the top — edit there, then run the rest top-to-bottom. All analytical code lives in `src/stroke_orofacial/`; the notebooks orchestrate via library calls.

| # | Notebook | Purpose | Depends on |
|---|---|---|---|
| 1 | `notebooks/00_session_processing.ipynb` | **Phase 2 — Spout behavior.** Wavesurfer .h5 → per-session licks, rewards, treadmill traces, bouts. Outputs land under `pipeline_outputs/spout_behavior/`. No DLC dependency — sessions without DLC inference yet still process correctly. Orchestration via `SessionManifest` (Phase 6.7+). | Raw wavesurfer .h5 |
| 2 | `notebooks/01_spout_behavior_figures.ipynb` | **Phase 8a.10 spout-behavior figures.** Renders 11 canonical per-mouse plot families (raster, latency series, criteria overlays, side splits) + cohort-summary tile grids across all 8 cohort animals × ~341 (animal, date) pairs. Designed to run on pure-spout sessions before DLC inference is available; per-trial endpoint overlays layer in once kinematics outputs (steps 6-7) exist. | Spout behavior (step 1); optional per-trial endpoints from steps 6-7 for kinematics-enhanced panels |
| 3 | `notebooks/02_alignment.ipynb` | **Phase 3 — Wavesurfer ↔ Video ↔ DLC alignment.** Aligns wavesurfer samples with video frames via sync signal. Default: loads existing templates from `pipeline_outputs/dlc_analysis/alignment_templates/cam2/`. Recomputes only if missing or `FORCE_RECOMPUTE=True` in user-inputs cell. Outputs alignment templates + per-session params + run log. | Wavesurfer (step 1) + raw video + optional DLC |
| 4 | `notebooks/10_dlc_inference.ipynb` | **DLC inference (on O2 cluster, upstream of this repo).** Generates per-session DLC inference scripts + sbatch commands to run on HMS O2. Local actions (video discovery, YAML writing, script generation) execute in the notebook; SSH/rsync/sbatch commands are PRINTED for you to paste into a terminal — no SSH is executed by the notebook. See `src/stroke_orofacial/dlc_inference_o2/README.md` for the full O2 workflow. | Raw video on MICROSCOPE |
| 5 | `notebooks/11_dlc_build_parquets.ipynb` | **Phase 4 — DLC centered parquets.** Loads DLC inference h5 outputs, centers coordinates on a reference landmark (spout_midpoint, eye_midpoint, or other per-bodypart per Phase 4.5-lite), writes whole-session centered parquets. All three centering modes built by default. First DLC-required orchestrator. | DLC inference (step 4) + alignment (step 3) |
| 6 | `notebooks/12_dlc_kinematics_tongue.ipynb` | **Phase 7a tongue.** Full tongue kinematics chain: 7a.2 v5p3 interpolated traces → 7a.3 V3 per-trial scalars + angles + endpoints → 7a.4 angle/phase QC visuals (5 families per session) → 7a.5 tongue-jaw mismatch classifier + per-session QC → 7a.6 mean/SEM cohort families (session_overlays, binned_overlays, mean_trace, mean_video). **v7 pipeline default ON** post Phase 7e (pre-clean + detector + gates produce `cleaned_traces/` + `lick_events/` outputs; legacy path preserved behind `use_v7_pipeline: false`). | Centered parquets (step 5) + spout behavior (step 1) |
| 7 | `notebooks/13_dlc_kinematics_jaw.ipynb` | **Phase 7a jaw.** Mirror of tongue chain: 7a.2 interpolated traces + 7a.5 per-trial 10-endpoint scalars (JSON per session) + 7a.6 mean/SEM cohort families. No jaw-side angle/phase visual family (jaw kinematics are simpler than tongue). **Phase 7f v3.4 cleanup pipeline default ON** post-2026-05-27 (analog to Phase 7e tongue v7; produces `cleaned_traces/jaw/`). Can run in parallel with step 6. | Centered parquets (step 5) + spout behavior (step 1) |
| 8 | `notebooks/20_stats_cross_animal.ipynb` | **Phase 9 cross-animal stats.** LMM-based statistical comparisons across all animals + endpoints + axes (pre_post, recovery, ipsi_contra). Outputs forest plots, recovery curves, paired-distribution figures, headline summary CSV. Consumes the materialized per-trial endpoint parquets at `pipeline_outputs/stats/inputs/`. | Per-trial endpoints (steps 6-7) + spout behavior (step 1) |

### Notes on parallelism + re-runs

- **Steps 6 + 7 can run in parallel** (independent bodyparts, different output trees).
- **Re-runs:** most orchestrators use a per-session manifest + skip-if-exists pattern. To force re-emit on a subset, edit the `overwrite=` kwarg in the USER INPUTS cell to `"force"` for the sessions you want re-rendered. Re-emitting EVERYTHING is a destructive op — see CLAUDE.md Ground Rule 7 (per-invocation approval required).
- **Failed sessions:** each notebook's per-session loop catches errors per-session and emits a manifest CSV at the end summarizing OK / FAIL / SKIP per (animal, date) — review that before assuming a clean run.
- **Wall-time anchors** (approximate, per-session): step 1 spout behavior ~30 s; step 2 spout-behavior figures ~few minutes per animal; step 5 centered parquets ~60 s; step 6 tongue full chain ~73 s (Phase 7c.1 pilot anchor); step 7 jaw ~37-41 min (dominated by mean_video MP4 encoding); step 8 stats ~few minutes per axis × granularity combination.

### Auxiliary references

- **`docs/DESIGN.md`** — full architectural design + phase numbering scheme.
- **`docs/DATA_MODEL.md`** — canonical schemas for every output parquet / JSON / NPZ.
- **`docs/SCIENTIFIC_ENDPOINTS.md`** — per-endpoint scientific rationale + statistical interpretation.
- **`docs/STATS_PIPELINE.md`** — Phase 9 stats methodology (LMM, permutation, multiple-comparisons correction).
- **`docs/MIGRATION_LOG.md`** — per-phase migration history (what changed when + why).
- **`docs/DECISIONS.md`** — project-wide decisions log with Context / Decision / Rationale / Enforced-at format.
- **`docs/COWORK_SESSION_STATE.md`** — running session-by-session state log for Cowork+CC parallel work.
- **`docs/prompts/`** — per-phase kickoff docs + addenda (the canonical artifacts of each phase's planning).
- **`docs/runbooks/`** — operational runbooks for common multi-step workflows.

## Documentation

See `docs/DESIGN.md` for the full design document and migration plan.
