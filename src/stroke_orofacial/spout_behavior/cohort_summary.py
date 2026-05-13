"""Phase 8a.10 sub-deliverable A — cohort-summary tile grids.

Port of legacy ``summary_PS.py`` (analysis/behavior_report/). Tiles
per-mouse PNGs from
:func:`stroke_orofacial.paths.PathResolver.spout_behavior_figures_dir`
into a near-square cohort grid (one tile-figure per plot family). Used
by Phase 8a.10 sub-deliverable A's verdict Phase B for cross-animal
spot-check (Priya 2026-05-13 verdict mechanism).

Pure tile-and-render — NO new plot computation. Reads the pre-rendered
per-mouse PNGs that :mod:`stroke_orofacial.spout_behavior.visual_gate`
already emitted; embeds each into a subplot; saves the composite as
SVG + PNG.

Recovery-trajectory rendering from legacy playground cell 56 is
**deferred** to a future phase per Priya 2026-05-13 decision (cohort_summary
scope intentionally tiler-only for Phase 8a.10).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal, Sequence

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.visual_gate import load_visual_gate_config


def _grid(n: int) -> tuple[int, int]:
    """Near-square ``(nrows, ncols)`` for ``n`` subplots.

    Mirrors legacy ``summary_PS._grid`` (analysis/behavior_report/
    summary_PS.py:48-51). For n=8: returns ``(3, 3)`` (9 cells, 1 empty).
    """
    ncols = int(math.ceil(math.sqrt(n)))
    nrows = int(math.ceil(n / ncols))
    return nrows, ncols


def make_summary_folder_name(animals: Sequence[str]) -> str:
    """Default cohort-summary filename-stem prefix.

    Returns ``"summary_" + "_".join(animals)``. **Task 3 Round 2
    continuation (2026-05-13):** this is now a FILE-STEM prefix
    (not a subdir name) under the shared
    :meth:`PathResolver.spout_behavior_figures_summary_dir`. E.g.
    output paths become
    ``spout_behavior_figures/summary/<this-prefix>__<family>{suffix}.{svg,png}``.
    """
    return "summary_" + "_".join(animals)


def make_summary_figures(
    animals: Sequence[str],
    resolver: PathResolver,
    *,
    plot_families: Sequence[str] | None = None,
    align_to_stroke: bool = True,
    output_dir_name: str | None = None,
    skip_plots: set[str] | None = None,
    config: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> Path:
    """Tile per-animal PNGs into cohort-summary grids — one tile-figure
    per plot family, saved as SVG + PNG.

    Mirrors legacy ``summary_PS.make_summary_figures``
    (analysis/behavior_report/summary_PS.py:58-125).

    Parameters
    ----------
    animals : sequence of str
        Cohort animal IDs in display order (e.g.
        ``("PS46", "PS47", ..., "PS55")``). The tile grid uses this
        order top-to-bottom, left-to-right.
    resolver : PathResolver
        Used for both reading per-animal PNG sources
        (:meth:`PathResolver.spout_behavior_figures_dir`) and writing
        the composite output
        (:meth:`PathResolver.spout_behavior_figures_summary_dir`).
    plot_families : sequence of str, optional
        Plot families to tile. ``None`` reads
        ``visual_gate.summary_default_plots`` from
        ``configs/defaults.yaml``. The ``skip_plots`` filter is applied
        AFTER the default-list lookup.
    align_to_stroke : bool, default ``True``
        Per-family suffix: ``_relStroke`` when ``True`` (the per-animal
        renderers emit at the same suffix), ``_absDate`` otherwise.
    output_dir_name : str, optional
        **Filename-stem prefix** (NOT a subdir — historical kwarg name
        retained for API compatibility). Defaults to
        :func:`make_summary_folder_name`. Output paths become
        ``<spout_behavior_figures_summary_dir>/<output_dir_name>__<family>{suffix}.{svg,png}``.
    skip_plots : set of str, optional
        Always-skipped families. ``None`` reads
        ``visual_gate.summary_skip_plots`` (legacy default ``{"lick_raster"}``).
    config : dict, optional
        Pre-loaded ``visual_gate:`` block. ``None`` calls
        :func:`load_visual_gate_config`.
    overwrite : {"force", "skip", "raise"}
        Per-target overwrite policy (matches
        :func:`save_visual_gate_figure`).

    Returns
    -------
    Path
        The shared cohort-summary output directory
        (:meth:`PathResolver.spout_behavior_figures_summary_dir`). The
        dir contains
        ``<output_dir_name>__<family>{suffix}.{svg,png}`` pairs.
    """
    config = config or load_visual_gate_config()
    if plot_families is None:
        plot_families = list(config.get("summary_default_plots", []))
    if skip_plots is None:
        skip_plots = set(config.get("summary_skip_plots", []))
    plot_families = [p for p in plot_families if p not in skip_plots]

    if output_dir_name is None:
        output_dir_name = make_summary_folder_name(animals)

    suffix = "_relStroke" if align_to_stroke else "_absDate"

    out_dir = resolver.spout_behavior_figures_summary_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    n_animals = len(animals)
    nrows, ncols = _grid(n_animals)
    cell_w, cell_h = config.get("summary_figsize_per_cell", [4, 3])
    dpi = int(config.get("summary_dpi", 300))

    for family in plot_families:
        fig, axs = plt.subplots(
            nrows=nrows, ncols=ncols,
            figsize=(cell_w * ncols, cell_h * nrows),
            squeeze=False,
        )
        axs_flat = axs.flatten()
        # Turn off unused trailing axes (when n_animals < nrows * ncols).
        for ax in axs_flat[n_animals:]:
            ax.axis("off")

        for i, animal in enumerate(animals):
            ax = axs_flat[i]
            png_path = (
                resolver.spout_behavior_figures_dir(animal)
                / f"{family}{suffix}.png"
            )
            if not png_path.exists():
                # Missing per-animal PNG → text placeholder per legacy
                # line 105-107.
                ax.axis("off")
                ax.text(
                    0.5, 0.5,
                    f"{animal}\nMISSING\n{png_path.name}",
                    ha="center", va="center",
                )
                continue
            try:
                img = mpimg.imread(png_path)
                ax.imshow(img)
                ax.set_title(animal, fontsize="medium")
                ax.axis("off")
            except Exception as exc:  # noqa: BLE001 — legacy line 114
                ax.axis("off")
                ax.text(
                    0.5, 0.5,
                    f"{animal}\nERROR\n{type(exc).__name__}",
                    ha="center", va="center",
                )

        fig.suptitle(f"{output_dir_name}__{family}{suffix}", y=0.995)
        fig.tight_layout(rect=[0, 0, 1, 0.98])

        for ext in ("svg", "png"):
            target = out_dir / f"{output_dir_name}__{family}{suffix}.{ext}"
            if target.exists():
                if overwrite == "raise":
                    plt.close(fig)
                    raise FileExistsError(f"cohort-summary target exists: {target}")
                if overwrite == "skip":
                    continue
            fig.savefig(target, dpi=dpi if ext == "png" else None)
        plt.close(fig)

    return out_dir
