# stroke_orofacial_pipeline

Consolidated analysis pipeline for post-stroke orofacial motor plasticity in mice.

Covers spout-behavior processing (wavesurfer), video/DLC alignment, DLC bodypart analyses
(spatial maps, kinematics), and cross-animal statistics.

## Setup (macOS)

```bash
# Create / update the conda environment
conda env update -f environment-mac.yml

# Activate
conda activate frsb

# Install the package in editable mode
pip install -e .
```

## Setup (Windows)

```bash
conda env update -f environment-windows.yml
conda activate deeplabcut
pip install -e .
```

## Project structure

- `src/stroke_orofacial/` — All analysis code (importable package).
- `notebooks/` — Orchestration notebooks; no analytical code, just imports and USER INPUTS.
- `configs/` — YAML configs for paths, animal metadata, and analysis defaults.
- `docs/` — Design doc, data model, stats rationale, migration log.
- `tests/` — Test suite.
- `scripts/` — CLI entry points (thin wrappers around notebook workflows).

## Documentation

See `docs/DESIGN.md` for the full design document and migration plan.
