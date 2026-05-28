"""Re-render the 8 Q-lock 13 SVGs from a saved pooled CSV.

Skips the cohort walk + Stage 1/2 compute; reads
``phenotype_pooled_phase_bin_mean_sem.csv`` from disk and re-renders.
Used for fast iteration on figure-only changes (display-window clip,
shared y-axis, palette tweaks, error band type, etc.).

Usage::

    # Re-render the canonical 4-tier figures from the 4-tier CSV.
    python scripts/phase_9_1_q13/rerender_from_pooled_csv.py

    # Re-render the 3-tier (mod-severe → moderate) variant from its CSV.
    python scripts/phase_9_1_q13/rerender_from_pooled_csv.py \\
        --remap-phenotypes 3tier
"""
from __future__ import annotations

import argparse
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

# Import remap helpers from the sibling emit_cohort.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from emit_cohort import PHENOTYPE_ORDER_3TIER  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-render Q-lock 13 figures from pooled CSV.",
    )
    parser.add_argument(
        "--remap-phenotypes",
        choices=("none", "3tier"),
        default="none",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("phase_9_1_q13.rerender")

    resolver = PathResolver()
    base_dir = resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    if args.remap_phenotypes == "3tier":
        out_dir = base_dir / "3_phenotype"
        phenotype_order = PHENOTYPE_ORDER_3TIER
    else:
        out_dir = base_dir
        phenotype_order = None

    pooled_csv = out_dir / "phenotype_pooled_phase_bin_mean_sem.csv"
    if not pooled_csv.exists():
        logger.error("pooled CSV not found at %s", pooled_csv)
        return 1
    logger.info("Reading pooled CSV: %s", pooled_csv)
    pooled = pd.read_csv(pooled_csv)
    logger.info("  loaded %d rows", len(pooled))

    logger.info(
        "Re-rendering — SEM (canonical) + SD (sd_band/ subdir) ...",
    )
    kwargs: dict = {
        "resolver": resolver,
        "overwrite": "force",
    }
    if phenotype_order is not None:
        kwargs["phenotype_order"] = phenotype_order
    sem_result = emit_phase_aligned_trajectory_figures(
        pooled, output_dir=out_dir, error_band_type="sem", **kwargs,
    )
    logger.info(
        "  SEM emitted=%d skipped=%d → %s",
        len(sem_result["emitted"]), len(sem_result["skipped"]), out_dir,
    )
    sd_dir = out_dir / "sd_band"
    sd_result = emit_phase_aligned_trajectory_figures(
        pooled, output_dir=sd_dir, error_band_type="sd", **kwargs,
    )
    logger.info(
        "  SD  emitted=%d skipped=%d → %s",
        len(sd_result["emitted"]), len(sd_result["skipped"]), sd_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
