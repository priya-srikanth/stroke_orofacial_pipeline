"""Render the VLS-manuscript versions of the close-vs-standard spout
summaries (Supplementary Fig. S5B: PS51, PS55, PS54).

Manuscript-only styling (Priya, 2026-11-19; DECISIONS 2026-11-19
"S5B spout close-vs-standard summaries: manuscript styling"):
  - text ~1.4x the ``spout_close_vs_std:`` config sizes (the panels
    print at ~1/3 page width);
  - raster row 1.8x the height of rows 1-3 (rows 1-3 keep their
    pipeline height, so the figure grows from 14 to 16.8 in);
  - incorrect raster licks red (#D62728) instead of magenta, because
    magenta is the R-cue color in rows 1-3;
  - suptitle uses the manuscript animal labels (#6 / #7 / #8).

The pipeline figures in ``spout_close_vs_std/cohort/`` are never
touched: outputs go to ``--out-dir`` as ``<animal>_summary_ms.{png,svg}``
(png at 300 dpi), and the script refuses to run if any of them exists.

Usage::

    python -m scripts.manuscript.render_s5_spout_close_summaries \
        --out-dir <SRV>/vls_stroke_paper/figure_review/S5_summaries
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.spout_close_vs_std import (
    render_animal_summary_spout_close_vs_std,
)

# Manuscript animal labels (Fig. S5B panel order: PS51, PS55, PS54).
MS_LABELS: dict[str, str] = {"PS51": "#6", "PS55": "#8", "PS54": "#7"}

PIPELINE_FIGSIZE = (10.0, 14.0)
HEIGHT_RATIOS = (1.0, 1.0, 1.0, 1.8)
FONT_SCALE = 1.4
INCORRECT_COLOR = "#D62728"
ROW_HEIGHT_SCALE = 1.15


def main(argv: list[str] | None = None) -> list[Path]:
    """Render the three manuscript summaries; return the written paths."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--animals", nargs="+", default=list(MS_LABELS))
    args = ap.parse_args(argv)

    existing = sorted(args.out_dir.glob("*_summary_ms.*")) if args.out_dir.exists() else []
    if existing:
        raise SystemExit(
            "refusing to overwrite existing manuscript summaries:\n  "
            + "\n  ".join(str(p) for p in existing)
        )

    # Width stays at the pipeline 10 in so the 1.4x text is 1.4x at print
    # width. Height = pipeline row height x ROW_HEIGHT_SCALE per row unit
    # (rows 1-3 a bit taller than the pipeline's, so the 1.4x wrapped
    # y-labels fit), times the 1:1:1:1.8 ratios.
    height = PIPELINE_FIGSIZE[1] / 4.0 * ROW_HEIGHT_SCALE * sum(HEIGHT_RATIOS)
    resolver = PathResolver()
    written: list[Path] = []
    for animal in args.animals:
        svg, png = render_animal_summary_spout_close_vs_std(
            animal,
            resolver=resolver,
            overwrite="raise",
            figsize=(PIPELINE_FIGSIZE[0], height),
            height_ratios=HEIGHT_RATIOS,
            font_scale=FONT_SCALE,
            raster_incorrect_color=INCORRECT_COLOR,
            title_label=MS_LABELS[animal],
            out_dir=args.out_dir,
            out_stem=f"{animal}_summary_ms",
            wrap_labels=True,
        )
        written += [png, svg]
        print(png)
        print(svg)
    return written


if __name__ == "__main__":
    main()
