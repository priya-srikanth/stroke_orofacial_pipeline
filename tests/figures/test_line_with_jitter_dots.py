"""Tests for the shared line+jitter-dots plot-convention primitive.

Chore ``vChore-dlc-pooled-phenotype-unification`` Stage 1. Pure in-memory
rendering checks — uses ``matplotlib.figure.Figure`` directly (no pyplot, no
backend, no file I/O), so nothing touches the real outputs tree.
"""
from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure

from stroke_orofacial.figures import _layout
from stroke_orofacial.figures._line_with_jitter_dots import (
    _JITTER_SEED,
    jittered_x_positions,
    render_line_with_jitter_dots,
)


def _ax():
    """A throwaway Axes backed by a non-interactive Figure (no pyplot)."""
    return Figure().add_subplot(1, 1, 1)


# ---------------------------------------------------------------------------
# Re-export: the convention is reachable through this one module
# ---------------------------------------------------------------------------

def test_reexports_canonical_jitter_helper() -> None:
    """jittered_x_positions re-exported here IS _layout's implementation."""
    assert jittered_x_positions is _layout.jittered_x_positions
    assert _JITTER_SEED == 42


# ---------------------------------------------------------------------------
# Scatter underlay: one collection per non-empty center, dots = session count
# ---------------------------------------------------------------------------

def test_scatter_collection_per_nonempty_center() -> None:
    """One PathCollection is drawn per center that has session values.

    Asserts on the returned ``scatter`` artists rather than
    ``ax.collections`` — the latter also picks up the errorbar's cap
    LineCollection, which is not part of the dot underlay.
    """
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax,
        line_x=[0, 1, 2],
        line_y=[1.0, 2.0, 3.0],
        line_yerr=[0.1, 0.1, 0.1],
        scatter_centers=[0, 1, 2],
        scatter_values=[[1.0, 1.1], [2.0], [3.0, 3.1, 3.2]],
        color="#ff0000",
        marker="o",
    )
    assert len(out["scatter"]) == 3


def test_total_dot_count_matches_session_values() -> None:
    """Per-session-dot count assertion: total offsets == total values."""
    ax = _ax()
    scatter_values = [[1.0, 1.1], [2.0], [3.0, 3.1, 3.2, 3.3]]
    out = render_line_with_jitter_dots(
        ax,
        line_x=[0, 1, 2],
        line_y=[1.0, 2.0, 3.0],
        scatter_centers=[0, 1, 2],
        scatter_values=scatter_values,
        color="C0",
    )
    total = sum(len(coll.get_offsets()) for coll in out["scatter"])
    assert total == sum(len(v) for v in scatter_values) == 7


def test_empty_center_draws_no_collection() -> None:
    """A center with an empty value list is skipped (no empty collection)."""
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax,
        line_x=[0, 1],
        line_y=[1.0, 2.0],
        scatter_centers=[0, 1],
        scatter_values=[[1.0, 1.1], []],
        color="C0",
    )
    assert len(out["scatter"]) == 1


def test_no_scatter_when_centers_empty() -> None:
    """No underlay drawn when scatter inputs are omitted."""
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax, line_x=[0, 1], line_y=[1.0, 2.0], color="C0",
    )
    assert out["scatter"] == []
    assert out["line"] is not None  # line still drawn


# ---------------------------------------------------------------------------
# Jitter geometry: dots sit within center ± width, deterministic across calls
# ---------------------------------------------------------------------------

def test_dots_within_jitter_band() -> None:
    """All scatter x-offsets lie within ``center ± jitter_width``."""
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax,
        line_x=[2],
        line_y=[5.0],
        scatter_centers=[2],
        scatter_values=[list(np.linspace(0.0, 1.0, 40))],
        color="C0",
        jitter_width=0.15,
    )
    xs = out["scatter"][0].get_offsets()[:, 0]
    assert np.all(xs >= 2.0 - 0.15 - 1e-9)
    assert np.all(xs <= 2.0 + 0.15 + 1e-9)


def test_jitter_deterministic_across_calls() -> None:
    """Same seed → identical scatter x-positions (stable SVG diffs)."""
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    outs = []
    for _ in range(2):
        outs.append(render_line_with_jitter_dots(
            _ax(), line_x=[0], line_y=[12.0],
            scatter_centers=[0], scatter_values=[values],
            color="C0", jitter_seed=123,
        ))
    xs1 = outs[0]["scatter"][0].get_offsets()[:, 0]
    xs2 = outs[1]["scatter"][0].get_offsets()[:, 0]
    assert np.array_equal(xs1, xs2)


# ---------------------------------------------------------------------------
# Layering + foreground line
# ---------------------------------------------------------------------------

def test_dots_below_line_by_zorder() -> None:
    """Underlay zorder is strictly below the foreground line zorder."""
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax,
        line_x=[0, 1],
        line_y=[1.0, 2.0],
        line_yerr=[0.1, 0.1],
        scatter_centers=[0, 1],
        scatter_values=[[1.0], [2.0]],
        color="C0",
    )
    scatter_z = out["scatter"][0].get_zorder()
    line_z = out["line"][0].get_zorder()
    assert scatter_z < line_z


def test_line_label_propagates() -> None:
    """The foreground line carries the legend label; underlay does not."""
    ax = _ax()
    render_line_with_jitter_dots(
        ax,
        line_x=[0, 1],
        line_y=[1.0, 2.0],
        scatter_centers=[0, 1],
        scatter_values=[[1.0], [2.0]],
        color="C0",
        label="mild",
    )
    handles, labels = ax.get_legend_handles_labels()
    assert labels == ["mild"]


def test_returns_none_line_when_no_line_data() -> None:
    """line artist is None when there is no line data, scatter still drawn."""
    ax = _ax()
    out = render_line_with_jitter_dots(
        ax, line_x=[], line_y=[],
        scatter_centers=[0], scatter_values=[[1.0, 2.0]],
        color="C0",
    )
    assert out["line"] is None
    assert len(out["scatter"]) == 1


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_raises_on_line_xy_length_mismatch() -> None:
    ax = _ax()
    with pytest.raises(ValueError, match="same length"):
        render_line_with_jitter_dots(
            ax, line_x=[0, 1], line_y=[1.0], color="C0",
        )


def test_raises_on_yerr_length_mismatch() -> None:
    ax = _ax()
    with pytest.raises(ValueError, match="line_yerr"):
        render_line_with_jitter_dots(
            ax, line_x=[0, 1], line_y=[1.0, 2.0],
            line_yerr=[0.1], color="C0",
        )


def test_raises_on_scatter_length_mismatch() -> None:
    ax = _ax()
    with pytest.raises(ValueError, match="scatter_centers"):
        render_line_with_jitter_dots(
            ax, line_x=[0], line_y=[1.0],
            scatter_centers=[0, 1], scatter_values=[[1.0]],
            color="C0",
        )
