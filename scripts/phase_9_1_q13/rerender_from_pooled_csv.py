"""Re-render the 8 Q-lock 13 SVGs from a saved pooled CSV.

Skips the cohort walk + Stage 1/2 compute; reads
``phenotype_pooled_phase_bin_mean_sem.csv`` from disk and re-renders.
Used for fast iteration on figure-only changes (display-window clip,
shared y-axis, color tweaks, etc.).

Usage::

    python scripts/phase_9_1_q13/rerender_from_pooled_csv.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.figures.phase_aligned_trajectories import (  # noqa: E402
    FIGURE_SUBDIR,
    emit_phase_aligned_trajectory_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("phase_9_1_q13.rerender")

    resolver = PathResolver()
    pooled_csv = (
        resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
        / "phenotype_pooled_phase_bin_mean_sem.csv"
    )
    if not pooled_csv.exists():
        logger.error("pooled CSV not found at %s", pooled_csv)
        return 1
    logger.info("Reading pooled CSV: %s", pooled_csv)
    pooled = pd.read_csv(pooled_csv)
    logger.info("  loaded %d rows", len(pooled))

    logger.info("Re-rendering 8 figures...")
    result = emit_phase_aligned_trajectory_figures(
        pooled, resolver=resolver, overwrite="force",
    )
    logger.info(
        "  emitted=%d skipped=%d",
        len(result["emitted"]), len(result["skipped"]),
    )
    for p in result["emitted"]:
        logger.info("  → %s", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
