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
    so panel labels are ``"Ipsi (mouse-L)"`` and ``"Contra (mouse-R)"``
    (capitalized per Task 1a v5 casing convention; mouse-side designations
    stay lowercase per technical convention). The cohort-uniformity caveat
    goes in the figure caption via
    :func:`stroke_orofacial.figures.palette.figure_caption_caveat`.

    Caller draws traces + SEM bands (V4) or line+scatter (V5) into the two
    axes; then calls :func:`phenotype_panel` and :func:`phenotype_legend`
    per panel to apply consistent decorations.
    """
    import matplotlib.pyplot as plt
    fig, (ipsi_ax, contra_ax) = plt.subplots(
        1, 2, figsize=figsize, sharey=sharey,
    )
    ipsi_ax.set_title("Ipsi (mouse-L)")
    contra_ax.set_title("Contra (mouse-R)")
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


def apply_side_split_suptitle(
    fig: Any,
    endpoint_slug: str,
    *,
    baseline_subtracted: bool = False,
) -> None:
    """Add a figure-level title above the ipsi + contra panels.

    Wraps :func:`apply_figure_suptitle` and additionally drops the Q-lock 4
    cohort-uniformity caveat at the bottom of the figure. Per-panel titles
    ("ipsi (mouse-L)" / "contra (mouse-R)") are set by
    :func:`phenotype_side_split_panels`.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
    endpoint_slug : str
        Endpoint identifier — looked up in ``ENDPOINT_DISPLAY_NAMES`` for
        the long-form display name; falls back to the slug verbatim.
    baseline_subtracted : bool, optional
        When True, adds the italic gray "baseline-subtracted" subheading
        below the bold endpoint title (Q-lock 11). V5 figures pass True;
        V4 passes False (V4 plots cohort recovery curves of raw values).
    """
    from .palette import figure_caption_caveat
    display_name, _ = get_endpoint_labels(endpoint_slug)
    apply_figure_suptitle(fig, display_name, baseline_subtracted=baseline_subtracted)
    fig.text(
        0.5, -0.04,
        figure_caption_caveat(),
        ha="center", va="top", fontsize=8, color="0.35",
    )


# ---------------------------------------------------------------------------
# Endpoint display-name + short y-label lookup (Task 1a v4)
# ---------------------------------------------------------------------------

# Stored as (display_name, short_y_label) per endpoint. ``short_y_label`` is
# the FULL label as it appears on the y-axis (including "delta " prefix where
# semantically appropriate). Priya 2026-05-25 Task 1a v3 review settled on
# "delta X (unit)" form for V5 (baseline-subtracted) figures; V4 (raw recovery
# curves) currently reuses these same labels — flagged for Task 1b clarification
# on whether V4 should drop the "delta " prefix or whether V4 should also
# become baseline-subtracted. Editable per endpoint; fallback is
# (slug, "delta value") for any endpoint not in the dict.
ENDPOINT_DISPLAY_NAMES: dict[str, tuple[str, str]] = {
    "first_lick_accuracy_all": (
        "First-lick accuracy (all trials)",
        "Delta accuracy",
    ),
    "num_correct_licks_per_trial": (
        "Correct licks per trial",
        "Delta licks / trial",
    ),
    "tongue_lick1_y_peak": (
        "Tongue lick-1 Y peak",
        "Delta Y peak (px)",
    ),
    "tongue_lick1_angle_at_ypeak": (
        "Tongue lick-1 angle at Y-peak",
        "Delta angle (deg)",
    ),
    "tongue_lick1_x_at_ypeak": (
        "Tongue lick-1 X at Y-peak",
        "Delta X (px)",
    ),
}


def get_endpoint_labels(endpoint_slug: str) -> tuple[str, str]:
    """Return ``(display_name, short_y_label)`` for one endpoint.

    Lookups go through :data:`ENDPOINT_DISPLAY_NAMES`. Endpoints not yet
    present fall back to ``(endpoint_slug, "Delta value")`` — Priya iterates
    on the broader 35-endpoint dict at Task 1b / Task 1c.
    """
    return ENDPOINT_DISPLAY_NAMES.get(endpoint_slug, (endpoint_slug, "Delta value"))


# ---------------------------------------------------------------------------
# Epoch display labels (Task 1a v5 — relabel + capitalize for x-ticks)
# ---------------------------------------------------------------------------

# Per Priya 2026-05-25 Task 1a v4 review: replace raw ``epoch_label`` values
# with publication-ready capitalized + relabeled equivalents. Used by V5
# x-tick labels (and any future epoch-axis figure). ``epoch_label`` values
# in the underlying parquet stay as-is for stats / data consistency; the
# display mapping is purely cosmetic.
EPOCH_DISPLAY_LABELS: dict[str, str] = {
    "pre":       "Pre-stroke",
    "acute":     "Acute",
    "sub_acute": "Subacute",
    "chronic":   "Chronic",
}


def get_epoch_display(epoch_label: str) -> str:
    """Return the publication-facing display label for one epoch.

    Falls back to ``epoch_label`` verbatim for any value not in
    :data:`EPOCH_DISPLAY_LABELS` (e.g., a future epoch added upstream).
    """
    return EPOCH_DISPLAY_LABELS.get(epoch_label, epoch_label)


def apply_figure_suptitle(
    fig: Any,
    display_name: str,
    *,
    baseline_subtracted: bool,
) -> None:
    """Apply the two-line suptitle layout locked at Task 1a v5.

    Line 1: ``display_name`` at y=0.99 (bold, larger). Line 2 (V5 only when
    ``baseline_subtracted=True``): "baseline-subtracted" at y=0.93 (italic,
    gray rgb 0.4). Subheading omitted on V4 since V4 plots raw recovery
    curves, not deltas.

    Callers should use :func:`apply_top_room` AFTER drawing all panels to
    reserve top whitespace; without it ``fig.tight_layout()`` would crowd
    the suptitle.
    """
    fig.suptitle(display_name, fontsize=12, fontweight="bold", y=0.99)
    if baseline_subtracted:
        fig.text(
            0.5, 0.93, "baseline-subtracted",
            fontsize=8, fontstyle="italic",
            color=(0.4, 0.4, 0.4), ha="center",
        )


def apply_top_room(fig: Any, *, top: float = 0.86) -> None:
    """Reserve top whitespace for the two-line suptitle (Task 1a v5).

    Calls ``fig.tight_layout(rect=[0, 0, 1, top])`` so subplot axes don't
    crowd the suptitle / subheading. Default ``top=0.86`` matches the
    suptitle at y=0.99 + subheading at y=0.93 layout from
    :func:`apply_figure_suptitle`.

    Use this in place of ``fig.tight_layout()`` after all panel drawing
    finishes; it composes with matplotlib's auto-layout via the ``rect``
    parameter (which reserves the top 14% for the suptitle band).
    """
    fig.tight_layout(rect=[0.0, 0.0, 1.0, top])


# ---------------------------------------------------------------------------
# Scatter underlay jitter (Q-lock 11 V5 + reusable for any categorical-x plot)
# ---------------------------------------------------------------------------

# Fixed seed for reproducibility — the V5 scatter jitter is purely cosmetic
# (avoids overplotting at identical x), so a deterministic shuffle is
# preferable to an emit-time-varying one. Seed picked at task draft;
# never change without bumping all V5 figures together.
_JITTER_SEED: int = 42


def jittered_x_positions(
    n_points: int,
    epoch_idx: int,
    *,
    width: float = 0.15,
    seed: int = _JITTER_SEED,
) -> list[float]:
    """Return n_points x-coordinates centered at epoch_idx with uniform jitter.

    Q-lock 11 — V5 scatter underlay overplot mitigation. Each per-(animal,
    session) data point sits within ``±width`` of the epoch's nominal
    x-position. A deterministic seed ensures the same emit produces the
    same scatter every time (important for SVG diffs at PR review).

    Parameters
    ----------
    n_points : int
        Number of jittered positions to return.
    epoch_idx : int
        Nominal x-position (0=pre, 1=acute, 2=sub_acute, 3=chronic).
    width : float, optional
        Half-width of the jitter band. Default 0.15 → jitter spans ±0.15
        epoch units around the epoch center, well within the 0.5-unit
        gap between adjacent epoch positions.
    seed : int, optional
        RNG seed for reproducibility. Default ``_JITTER_SEED`` (= 42).
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    if n_points <= 0:
        return []
    return [
        float(epoch_idx) + float(off)
        for off in rng.uniform(-width, width, n_points)
    ]
