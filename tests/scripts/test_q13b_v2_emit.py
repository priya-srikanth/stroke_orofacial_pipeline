"""Tests for the Q13b v2 re-emit pure units (cell-loss + renderer).

Chore ``vChore-dlc-pooled-phenotype-unification``. The on-the-fly filter +
recode load path reads real per-trial JSONs and is exercised by the PS46
pilot; here we cover the pure, fixture-free units: the v2-vs-no_filter
cell-loss comparison and the line+jitter renderer. All file output goes to
tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.chore_dlc_pooled_phenotype import q13b_v2_emit as q


def _pooled(rows: list[tuple]) -> pd.DataFrame:
    """Build a minimal pooled frame from (phenotype, epoch, side, endpoint, n)."""
    return pd.DataFrame(
        rows,
        columns=["recovery_phenotype", "epoch_label", "side", "endpoint",
                 "n_sessions"],
    )


def test_cell_loss_flags_emptied_cell() -> None:
    """A cell populated in no_filter but absent in v2 is flagged."""
    nofilter = _pooled([
        ("severe", "acute", "ipsi", "peak_angle_deg", 4),
        ("mild", "pre", "ipsi", "peak_angle_deg", 6),
    ])
    filtered = _pooled([
        ("mild", "pre", "ipsi", "peak_angle_deg", 6),
    ])  # severe/acute/ipsi dropped entirely by the filter
    warns = q._cell_loss_check(filtered, nofilter, "4_tier")
    assert len(warns) == 1
    assert "severe/acute/ipsi/peak_angle_deg" in warns[0]
    assert "no_filter n=4" in warns[0]


def test_cell_loss_silent_when_nothing_lost() -> None:
    """No warnings when every no_filter cell survives the filter."""
    nofilter = _pooled([("mild", "pre", "ipsi", "peak_angle_deg", 6)])
    filtered = _pooled([("mild", "pre", "ipsi", "peak_angle_deg", 4)])
    assert q._cell_loss_check(filtered, nofilter, "4_tier") == []


def test_cell_loss_ignores_empty_nofilter_cells() -> None:
    """A cell that was 0 in no_filter too is not a loss."""
    nofilter = _pooled([("severe", "acute", "ipsi", "peak_angle_deg", 0)])
    filtered = _pooled([])
    assert q._cell_loss_check(filtered, nofilter, "4_tier") == []


def _mean_inputs(endpoint: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-session (mean) + pooled (mean/sem/n_sessions) inputs for one cell."""
    per_session = pd.DataFrame({
        "animal": ["PS46", "PS46", "PS46", "PS46"],
        "recovery_phenotype": ["mild"] * 4,
        "epoch_label": ["pre", "pre", "acute", "acute"],
        "side": ["ipsi"] * 4,
        "endpoint": [endpoint] * 4,
        "mean": [1.0, 1.2, 2.0, 2.4],
    })
    pooled = pd.DataFrame({
        "recovery_phenotype": ["mild", "mild"],
        "epoch_label": ["pre", "acute"],
        "side": ["ipsi", "ipsi"],
        "endpoint": [endpoint, endpoint],
        "mean": [1.1, 2.2],
        "sem": [0.1, 0.2],
        "n_sessions": [2, 2],
        "n_animals": [1, 1],
    })
    return per_session, pooled


def test_renderer_writes_svg_and_png(tmp_path: Path) -> None:
    """render_endpoint_v2_figure produces both an SVG and a PNG sibling."""
    endpoint = "peak_angle_deg"
    per_session, pooled = _mean_inputs(endpoint)
    out = tmp_path / "peak_angle_deg_ipsi_v2.svg"
    q.render_endpoint_v2_figure(
        per_session_df=per_session, pooled_df=pooled,
        endpoint=endpoint, sides=("ipsi",),
        phenotype_order=("mild",), output_path=out,
    )
    assert out.exists() and out.stat().st_size > 0
    assert out.with_suffix(".png").exists()


def test_renderer_footer_has_both_lines(tmp_path: Path) -> None:
    """Footer carries BOTH the provenance line and the aggregation subtitle.

    Renders with svg.fonttype='none' so the text is searchable in the SVG.
    """
    import matplotlib
    endpoint = "peak_angle_deg"
    per_session, pooled = _mean_inputs(endpoint)
    out = tmp_path / "footer.svg"
    with matplotlib.rc_context({"svg.fonttype": "none"}):
        q.render_endpoint_v2_figure(
            per_session_df=per_session, pooled_df=pooled,
            endpoint=endpoint, sides=("ipsi",),
            phenotype_order=("mild",), output_path=out,
        )
    svg = out.read_text(encoding="utf-8")
    assert "filtered_v1" in svg          # provenance line
    assert "Mean" in svg and "SEM" in svg  # aggregation subtitle line
    assert "animals per phenotype" in svg  # n=animals legend phrasing


def test_renderer_skips_absent_phenotype(tmp_path: Path) -> None:
    """A phenotype with no data contributes nothing but doesn't crash."""
    endpoint = "peak_angle_deg"
    per_session, pooled = _mean_inputs(endpoint)
    out = tmp_path / "x.svg"
    q.render_endpoint_v2_figure(
        per_session_df=per_session, pooled_df=pooled,
        endpoint=endpoint, sides=("ipsi",),
        phenotype_order=("mild", "severe"),  # severe absent
        output_path=out,
    )
    assert out.exists()


def test_signed_endpoints_cover_all_three() -> None:
    """All 3 phase-aligned endpoints are treated as signed (sign-flip set)."""
    from stroke_orofacial.stats.aggregators import PHASE_ALIGNED_ENDPOINT_SLUGS
    assert q.SIGNED_ENDPOINTS == frozenset(PHASE_ALIGNED_ENDPOINT_SLUGS)
    assert len(q.SIGNED_ENDPOINTS) == 3
