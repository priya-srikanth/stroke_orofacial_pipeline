"""Phase 9.1 panel-grid + ipsi/contra side-split layout helpers.

Module-private (``_layout``) — matplotlib layout primitives shared across the
phenotype-pooled / spatial / latency_hist / ipsi-shift families. Keeps each
per-family runner focused on data assembly + per-panel rendering; cross-family
panel arrangement lives here.

Q-locks:
- Q-lock 1 — panel grid domain is the 4-tier phenotype set.
- Q-lock 4 — side labels via ``mouse_side_to_ipsi_contra`` + caption caveat.
- Q-lock 7 / 8 — layout enum (``four_separate`` vs ``single_4panel``) selected
  per family.
"""
from __future__ import annotations

from typing import Any

from .palette import PHENOTYPE_ORDER, phenotype_palette


def phenotype_panel(
    ax: Any,
    *,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
    xlabel: str = "Day relative to stroke (bin midpoint)",
    ylabel: str | None = None,
    set_title: bool = True,
    draw_stroke_onset: bool = True,
) -> None:
    """Apply axis decorations to a single phenotype-pooled panel.

    Phase 9.1 V4 single-panel layout = one panel per endpoint, multi-trace
    (one per phenotype tier). Side-split layout calls this on each of the
    ipsi + contra axes; for that case the caller sets ``set_title=False`` so
    the panel keeps its "ipsi (mouse-L)" / "contra (mouse-R)" title from
    :func:`phenotype_side_split_panels`.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    endpoint_slug : str
        Endpoint identifier used in the title (when ``set_title=True``).
    n_by_tier : dict[str, int]
        ``{phenotype_tier: n_animals}`` for the legend / annotation. n=1
        tiers (moderate, moderate-severe) get the "n=1 single-animal trace"
        marker per kickoff Critical Caveat 1.
    xlabel : str, optional
        X-axis label. Default tracks the V4 ``bin_midpoint_rel_day`` convention.
    ylabel : str, optional
        Y-axis label. Defaults to the endpoint slug.
    set_title : bool, optional
        When True (single-panel layout), set ``ax.set_title(endpoint_slug)``.
        When False (side-split, ipsi/contra titles already set), skip.
    draw_stroke_onset : bool, optional
        When True (V4 per_bin curves), draw the crimson dashed line at
        x=0.5 marking stroke onset. V5 (per_epoch boxplots) doesn't have a
        meaningful x-position for stroke onset (epoch is categorical), so
        callers pass False.
    """
    if draw_stroke_onset:
        # Stroke onset reference line (rel_day = 0). Phase 9 V2 puts it at
        # rel_day = 0.5; we draw it at 0.5 too so the line falls between the
        # bin_idx=0 (rel_day=0 baseline-included) and bin_idx=1 (first
        # post-stroke bin) midpoints, matching the V2 visual convention.
        ax.axvline(0.5, color="crimson", linestyle="--", linewidth=1.0, zorder=1)
    ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel or endpoint_slug)
    if set_title:
        ax.set_title(endpoint_slug)


def phenotype_legend(
    ax: Any,
    *,
    n_by_tier: dict[str, int],
    loc: str = "best",
) -> None:
    """Emit a 4-tier phenotype legend with per-tier n labels.

    Single-animal tiers (n=1) get an explicit "(n=1, single-animal trace)"
    suffix per Critical Caveat 1.
    """
    handles_labels = ax.get_legend_handles_labels()
    handles, labels = handles_labels
    # Re-order to canonical mild → severe.
    by_label: dict[str, Any] = dict(zip(labels, handles))
    ordered_handles: list[Any] = []
    ordered_labels: list[str] = []
    for tier in PHENOTYPE_ORDER:
        if tier not in by_label:
            continue
        n = n_by_tier.get(tier, 0)
        suffix = " (n=1, single-animal trace)" if n == 1 else f" (n={n})"
        ordered_handles.append(by_label[tier])
        ordered_labels.append(f"{tier}{suffix}")
    if ordered_handles:
        ax.legend(
            ordered_handles, ordered_labels,
            loc=loc, fontsize=8, framealpha=0.85,
        )


def trace_color(tier: str) -> str:
    """Convenience re-export of the palette lookup (saves an import)."""
    return phenotype_palette(tier)


# ---------------------------------------------------------------------------
# Side-split panels (Q-lock 10(a))
# ---------------------------------------------------------------------------

SIDE_TO_PANEL_LABEL: dict[str, str] = {"L": "ipsi", "R": "contra"}


def phenotype_side_split_panels(
    *,
    figsize: tuple[float, float] = (12.0, 4.0),
    sharey: bool = True,
):
    """Return (fig, ipsi_ax, contra_ax) — the standard V4/V5 side-split layout.

    Q-lock 10(a) — ipsi panel + contra panel, side-by-side, sharing y-range
    for direct visual comparison. All 8 cohort animals are L-stroke (Q-lock 4),
    so panel labels are ``"ipsi" = mouse-L`` and ``"contra" = mouse-R``; the
    cohort-uniformity caveat goes in the figure caption via
    :func:`stroke_orofacial.figures.palette.figure_caption_caveat`.

    Caller draws traces + SEM bands (V4) or boxplots (V5) into the two axes;
    then calls :func:`phenotype_panel` and :func:`phenotype_legend` per panel
    to apply consistent decorations.
    """
    import matplotlib.pyplot as plt
    fig, (ipsi_ax, contra_ax) = plt.subplots(
        1, 2, figsize=figsize, sharey=sharey,
    )
    ipsi_ax.set_title("ipsi (mouse-L)")
    contra_ax.set_title("contra (mouse-R)")
    return fig, ipsi_ax, contra_ax


def cohort_pooled_panel(
    *,
    figsize: tuple[float, float] = (7.5, 4.0),
):
    """Return (fig, ax) — the V4/V5 single-panel fallback layout.

    Q-lock 10(c) fallback: endpoints whose ``side`` column is absent or
    all-NaN render as a single panel with no ipsi/contra split. Caller still
    draws 4 phenotype traces (or boxplots) into the single ax.
    """
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax


def apply_side_split_suptitle(fig: Any, endpoint_slug: str) -> None:
    """Add a figure-level title above the ipsi + contra panels.

    Per-panel titles already say "ipsi (mouse-L)" / "contra (mouse-R)";
    the suptitle carries the endpoint identifier so both panels stay
    decluttered. Includes a small caption caveat below the suptitle per
    Q-lock 4.
    """
    from .palette import figure_caption_caveat
    fig.suptitle(endpoint_slug, fontsize=11, fontweight="bold", y=1.02)
    fig.text(
        0.5, -0.04,
        figure_caption_caveat(),
        ha="center", va="top", fontsize=8, color="0.35",
    )
