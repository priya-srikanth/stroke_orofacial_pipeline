"""Shared "line + per-session jittered dots" plot-convention primitive.

Single source of truth for the canonical phenotype-pooled rendering
convention introduced by Q-lock 11 (V5) and adopted as the cohort-wide
standard by Q-lock 14's spout-behavior renderer:

  * **Background underlay** — per-(animal, session) scalar values drawn as
    small faded dots, horizontally jittered around each nominal x-position
    so identical-x points don't overplot. Same color as the foreground
    series; ``zorder`` below the line.
  * **Foreground** — a connecting line through the cohort summary (mean)
    with optional SEM error bars; ``zorder`` above the dots.

Extracted (chore ``vChore-dlc-pooled-phenotype-unification``, Stage 1) from
``phenotype_pooled._draw_v5_delta_line_with_scatter`` +
``_layout.jittered_x_positions`` so the Q12 / Q13 / Q13b / Q13c v2 re-emit
renderers can all call one implementation instead of each re-deriving the
convention.

Design note — *why line stats are passed explicitly* rather than computed
from the per-session values: the phenotype-pooled summary ``mean``/``sem``
come from an upstream cohort-pooled aggregation (pool across animals with
its own SEM definition), which is **not** the simple mean/SEM of the
scatter points. Recomputing here would silently change every existing
figure. The primitive therefore takes the line statistics as inputs and
treats the scatter values as a pure visual underlay.

All functions here are pure (draw into a caller-supplied ``ax``; no I/O, no
global state) and import nothing from the rest of the package except the
already-canonical :func:`jittered_x_positions`, keeping this module free of
import cycles.
"""
from __future__ import annotations

from typing import Any, Sequence

# Re-export the canonical jitter helper so callers can reach the whole
# convention through this one module. The implementation stays in _layout
# (its original home + existing test coverage); importing it here is a
# one-directional dependency (_layout never imports this module), so no cycle.
from ._layout import _JITTER_SEED, jittered_x_positions

#: Canonical aggregation-method footer line for the mean+SEM phenotype-pooled
#: convention (chore vChore-dlc-pooled-phenotype-unification, matching Q14).
#: Rendered as the SECOND footer line, beneath each figure's provenance line,
#: by every line+jitter v2 renderer (Q13b / Q13 / Q13c / Q12 W-2). Q12
#: proportion-diff heatmaps are a different family and do NOT carry it.
AGGREGATION_SUBTITLE: str = (
    "Mean ± SEM session-pooled (n = animals per phenotype; per-cell "
    "n_sessions in stats CSV); per-session values shown as faded dots."
)

__all__ = [
    "jittered_x_positions", "render_line_with_jitter_dots",
    "AGGREGATION_SUBTITLE", "_JITTER_SEED",
]


def render_line_with_jitter_dots(
    ax: Any,
    *,
    line_x: Sequence[float],
    line_y: Sequence[float],
    line_yerr: Sequence[float] | None = None,
    band_halfwidth: Sequence[float] | None = None,
    scatter_centers: Sequence[float] = (),
    scatter_values: Sequence[Sequence[float]] = (),
    color: Any,
    marker: str = "o",
    label: str | None = None,
    jitter_width: float = 0.15,
    jitter_seed: int = _JITTER_SEED,
    scatter_size: float = 12.0,
    scatter_alpha: float = 0.25,
    scatter_zorder: float = 1.0,
    band_alpha: float = 0.2,
    band_zorder: float = 2.0,
    line_width: float = 2.0,
    marker_size: float = 6.0,
    capsize: float = 3.5,
    line_zorder: float = 3.0,
) -> dict[str, Any]:
    """Draw one series as a line+SEM with a jittered per-session dot underlay.

    Renders a single colored series (e.g. one phenotype tier) using the
    canonical convention. Call once per series; ``zorder`` defaults keep
    every series' dots beneath every series' lines regardless of draw order.

    Parameters
    ----------
    ax
        Matplotlib axes to draw into.
    line_x, line_y
        Nominal x-positions and summary (mean) y-values for the foreground
        connecting line. Must be the same length; pass them already ordered
        along x (the caller owns ordering, matching the legacy V5 behavior
        of plotting only the epochs that have pooled data).
    line_yerr
        Per-point SEM for error bars. ``None`` → line drawn with no error
        bars.
    band_halfwidth
        Per-point half-width of a shaded ±band around the line (e.g. SEM),
        same length as ``line_x``. ``None`` → no band. Drawn as a translucent
        ``fill_between`` beneath the line (and above the dot underlay) so the
        central-tendency uncertainty reads as a distinct layer from the
        per-session dots. Mutually compatible with ``line_yerr`` (you can
        show both, though typically only one is used).
    scatter_centers
        Nominal x-centers for the background dot underlay (typically the
        same integer epoch positions as ``line_x``, but kept independent so
        the underlay can cover x-positions the line skips, exactly as the
        legacy V5 draw did — scatter where sessions exist, line where the
        pool has a summary). Empty → no underlay.
    scatter_values
        Parallel to ``scatter_centers``: ``scatter_values[i]`` is the list
        of per-session scalar values plotted (jittered) around
        ``scatter_centers[i]``.
    color
        Series color, shared by dots and line.
    marker
        Marker shape, shared by dots and line (per-tier silhouette identity
        carries into the faded underlay, Q-lock 11 Task 1a v5).
    label
        Legend label for the foreground line (the underlay is never
        labelled, matching legacy behavior).
    jitter_width, jitter_seed
        Passed through to :func:`jittered_x_positions`. The deterministic
        seed keeps SVG diffs stable across re-emits.
    scatter_size, scatter_alpha, scatter_zorder
        Underlay dot styling. Defaults reproduce the legacy V5 underlay
        (s=12, α=0.25, zorder=1).
    line_width, marker_size, capsize, line_zorder
        Foreground line styling. Defaults reproduce the legacy V5 line
        (linewidth=2, markersize=6, capsize=3.5, zorder=3).

    Returns
    -------
    dict
        ``{"scatter": [PathCollection, ...], "line": ErrorbarContainer,
        "band": PolyCollection | None}`` — the artists created, for caller
        inspection / testing. ``"line"`` is ``None`` if ``line_x`` is empty;
        ``"band"`` is ``None`` unless ``band_halfwidth`` was given.

    Raises
    ------
    ValueError
        If ``line_x``/``line_y`` lengths differ, ``line_yerr`` is given with
        a mismatched length, or ``scatter_centers``/``scatter_values``
        lengths differ.
    """
    line_x = list(line_x)
    line_y = list(line_y)
    if len(line_x) != len(line_y):
        raise ValueError(
            f"line_x ({len(line_x)}) and line_y ({len(line_y)}) "
            "must be the same length."
        )
    if line_yerr is not None:
        line_yerr = list(line_yerr)
        if len(line_yerr) != len(line_x):
            raise ValueError(
                f"line_yerr ({len(line_yerr)}) must match line_x "
                f"({len(line_x)})."
            )
    if band_halfwidth is not None:
        band_halfwidth = list(band_halfwidth)
        if len(band_halfwidth) != len(line_x):
            raise ValueError(
                f"band_halfwidth ({len(band_halfwidth)}) must match line_x "
                f"({len(line_x)})."
            )
    scatter_centers = list(scatter_centers)
    scatter_values = list(scatter_values)
    if len(scatter_centers) != len(scatter_values):
        raise ValueError(
            f"scatter_centers ({len(scatter_centers)}) and scatter_values "
            f"({len(scatter_values)}) must be the same length."
        )

    # --- Background underlay: jittered per-session dots ---------------------
    scatter_artists: list[Any] = []
    for center, values in zip(scatter_centers, scatter_values):
        values = list(values)
        if not values:
            continue
        xs = jittered_x_positions(
            len(values), center, width=jitter_width, seed=jitter_seed,
        )
        scatter_artists.append(
            ax.scatter(
                xs, values,
                s=scatter_size, marker=marker,
                facecolor=color, edgecolor="none",
                alpha=scatter_alpha, zorder=scatter_zorder,
            )
        )

    # --- Mid layer: shaded ±band (e.g. SEM) beneath the line ---------------
    band_artist = None
    if band_halfwidth is not None and line_x:
        lower = [y - h for y, h in zip(line_y, band_halfwidth)]
        upper = [y + h for y, h in zip(line_y, band_halfwidth)]
        band_artist = ax.fill_between(
            line_x, lower, upper,
            color=color, alpha=band_alpha, linewidth=0.0,
            zorder=band_zorder,
        )

    # --- Foreground: line connector + SEM error bars -----------------------
    line_artist = None
    if line_x:
        line_artist = ax.errorbar(
            line_x, line_y,
            yerr=line_yerr,
            color=color, marker=marker, markersize=marker_size,
            linewidth=line_width, capsize=capsize,
            label=label, zorder=line_zorder,
        )

    return {"scatter": scatter_artists, "line": line_artist, "band": band_artist}
