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
) -> None:
    """Apply axis decorations to a single phenotype-pooled panel.

    Phase 9.1 V4 default layout = one panel per endpoint, multi-trace (one per
    phenotype tier). Caller draws traces + SEM bands; this helper applies the
    cross-figure consistent decorations.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    endpoint_slug : str
        Endpoint identifier used in the title.
    n_by_tier : dict[str, int]
        ``{phenotype_tier: n_animals}`` for the legend / annotation. n=1
        tiers (moderate, moderate-severe) get the "n=1 single-animal trace"
        marker per kickoff Critical Caveat 1.
    xlabel : str, optional
        X-axis label. Default tracks the V4 ``bin_midpoint_rel_day`` convention.
    ylabel : str, optional
        Y-axis label. Defaults to the endpoint slug.
    """
    # Stroke onset reference line (rel_day = 0). Phase 9 V2 puts it at
    # rel_day = 0.5; we draw it at 0.5 too so the line falls between the
    # bin_idx=0 (rel_day=0 baseline-included) and bin_idx=1 (first post-stroke
    # bin) midpoints, matching the V2 visual convention.
    ax.axvline(0.5, color="crimson", linestyle="--", linewidth=1.0, zorder=1)
    ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel or endpoint_slug)
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
