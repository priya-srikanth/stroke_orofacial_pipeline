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

Presets (``--preset``):
  - ``ms`` (default): the 2026-11-19 styling above, 10 in wide, svg + png
    ``<animal>_summary_ms``;
  - ``print`` (2026-11-21): the size the manuscript places the panels at
    (two per row, ~0.48 of the text width): 3.15 x 5.6 in, font_scale 0.5
    (so text is ~5.5-7 pt at 1:1), same row ratios, wrapped labels, red
    incorrect licks and #6/#7/#8 titles, written as svg + png + pdf
    ``<animal>_summary_print`` (the manuscript uses the pdf).

Usage::

    python -m scripts.manuscript.render_s5_spout_close_summaries \
        --out-dir <SRV>/vls_stroke_paper/figure_review/S5_summaries [--preset print]
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
# Print preset: the manuscript layout places each summary at ~0.48 of the text
# width (two per row), so the figure is drawn at that size with smaller text
# instead of being scaled down in LaTeX (which shrank the text to ~3 pt).
PRINT_FIGSIZE = (3.15, 5.6)
PRINT_FONT_SCALE = 0.5


def main(argv: list[str] | None = None) -> list[Path]:
    """Render the three manuscript summaries; return the written paths."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--animals", nargs="+", default=list(MS_LABELS))
    ap.add_argument("--preset", choices=("ms", "print"), default="ms")
    args = ap.parse_args(argv)
    suffix = f"_summary_{args.preset}"

    existing = sorted(args.out_dir.glob(f"*{suffix}.*")) if args.out_dir.exists() else []
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
    if args.preset == "print":
        figsize, font_scale = PRINT_FIGSIZE, PRINT_FONT_SCALE
    else:
        figsize, font_scale = (PIPELINE_FIGSIZE[0], height), FONT_SCALE
    resolver = PathResolver()
    written: list[Path] = []
    for animal in args.animals:
        svg, png = render_animal_summary_spout_close_vs_std(
            animal,
            resolver=resolver,
            overwrite="raise",
            figsize=figsize,
            height_ratios=HEIGHT_RATIOS,
            font_scale=font_scale,
            raster_incorrect_color=INCORRECT_COLOR,
            title_label=MS_LABELS[animal],
            out_dir=args.out_dir,
            out_stem=f"{animal}{suffix}",
            wrap_labels=True,
            save_pdf=args.preset == "print",
        )
        written += [png, svg]
        print(png)
        print(svg)
    return written


if __name__ == "__main__":
    main()
