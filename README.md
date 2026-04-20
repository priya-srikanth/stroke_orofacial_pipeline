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

## Documentation

See `docs/DESIGN.md` for the full design document and migration plan.
