"""Smoke tests for stroke_orofacial.stats.figures (Phase 9 Task 7).

End-to-end render checks with synthetic data. Each figure function
just needs to (a) accept the expected schema and (b) return a
Matplotlib Figure with at least one axes containing data.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest


def _can_import_matplotlib() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except Exception:
        return False


def _cohort_per_session_df(
    n_animals: int = 4, n_pre: int = 3, n_post: int = 12, rng_seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(rng_seed)
    rows = []
    for i in range(n_animals):
        aid = f"PS{40 + i}"
        offset = float(rng.normal(0, 0.2))
        for j in range(n_pre):
            rd = -n_pre + j
            rows.append({
                "animal": aid,
                "date": dt.date(2025, 3, 1) + dt.timedelta(days=j),
                "rel_day": rd, "side": "L", "value": offset + 0.5 + rng.normal(0, 0.05),
                "is_sentinel": False, "epoch_label": "pre", "cohort_bin_size": 7,
                "granularity": "per_session",
            })
            rows.append({
                "animal": aid,
                "date": dt.date(2025, 3, 1) + dt.timedelta(days=j),
                "rel_day": rd, "side": "R", "value": offset + 0.55 + rng.normal(0, 0.05),
                "is_sentinel": False, "epoch_label": "pre", "cohort_bin_size": 7,
                "granularity": "per_session",
            })
        for j in range(1, n_post + 1):
            rd = j
            ep = "acute" if j <= 5 else ("sub_acute" if j <= 10 else "chronic")
            rows.append({
                "animal": aid,
                "date": dt.date(2025, 3, 10) + dt.timedelta(days=j),
                "rel_day": rd, "side": "L", "value": offset + 0.5 + 0.2 * j + rng.normal(0, 0.05),
                "is_sentinel": False, "epoch_label": ep, "cohort_bin_size": 7,
                "granularity": "per_session",
            })
            rows.append({
                "animal": aid,
                "date": dt.date(2025, 3, 10) + dt.timedelta(days=j),
                "rel_day": rd, "side": "R", "value": offset + 0.55 + 0.18 * j + rng.normal(0, 0.05),
                "is_sentinel": False, "epoch_label": ep, "cohort_bin_size": 7,
                "granularity": "per_session",
            })
    return pd.DataFrame(rows)


class TestV1V2V3:

    def test_v1_renders(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib unavailable")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.stats.figures import plot_v1_per_session_recovery

        class _P:
            details = {"slope": 0.2, "intercept": 0.5, "status": "ok"}
        fig = plot_v1_per_session_recovery(
            _cohort_per_session_df(), endpoint_slug="test_ep", fit_proxy=_P(),
        )
        assert len(fig.axes) >= 1

    def test_v2_renders_with_side(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib unavailable")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.stats.figures import plot_v2_per_bin_recovery
        fig = plot_v2_per_bin_recovery(_cohort_per_session_df(), endpoint_slug="test_ep")
        ax = fig.axes[0]
        # Sides should produce L + R legend entries.
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        assert any(label in ("L", "R") for label in labels)

    def test_v3_renders_with_significance_markers(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib unavailable")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.stats.figures import plot_v3_per_epoch_boxplot

        # Hand-build headline_rows with known q_holm values.
        headline = pd.DataFrame([
            {"axis": "recovery", "comparison": "pre_vs_acute",
             "q_within_endpoint_holm": 0.001, "endpoint_slug": "test_ep"},
            {"axis": "recovery", "comparison": "pre_vs_sub_acute",
             "q_within_endpoint_holm": 0.04, "endpoint_slug": "test_ep"},
            {"axis": "recovery", "comparison": "pre_vs_chronic",
             "q_within_endpoint_holm": 0.5, "endpoint_slug": "test_ep"},
        ])
        eb = {f"PS{40 + i}": {"acute": 5, "subacute": 10, "chronic_min": 11}
              for i in range(4)}
        fig = plot_v3_per_epoch_boxplot(
            _cohort_per_session_df(), endpoint_slug="test_ep",
            headline_rows=headline, eb_by_animal=eb,
        )
        ax = fig.axes[0]
        # Asterisk text annotations should be present.
        texts = [t.get_text() for t in ax.texts]
        assert any("*" in t or t == "ns" for t in texts)


class TestForestPlot:

    def test_forest_plot_renders(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib unavailable")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.stats.figures import plot_forest_by_endpoint

        headline = pd.DataFrame([
            {"endpoint_slug": "a", "axis": "pre_post", "comparison": "collapsed_post",
             "effect_size": -0.5, "ci_lower": -0.7, "ci_upper": -0.3,
             "is_confirmatory": True, "effect_size_metric": "median_diff"},
            {"endpoint_slug": "b", "axis": "pre_post", "comparison": "collapsed_post",
             "effect_size": 0.2, "ci_lower": 0.0, "ci_upper": 0.4,
             "is_confirmatory": False, "effect_size_metric": "median_diff"},
        ])
        fig = plot_forest_by_endpoint(
            headline, axis="pre_post", comparison="collapsed_post",
        )
        assert len(fig.axes) >= 1


class TestPairedDiffDistribution:

    def test_paired_diff_renders(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib unavailable")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.stats.figures import plot_paired_diff_distribution

        eb = {f"PS{40 + i}": {"acute": 5, "subacute": 10, "chronic_min": 11}
              for i in range(4)}
        fig = plot_paired_diff_distribution(
            _cohort_per_session_df(), endpoint_slug="test_ep",
            axis="pre_post", post_epoch="acute", eb_by_animal=eb,
        )
        assert len(fig.axes) >= 1


class TestSignificanceMarker:

    def test_sig_thresholds(self):
        from stroke_orofacial.stats.figures import _sig_marker
        assert _sig_marker(0.0001) == "***"
        assert _sig_marker(0.005) == "**"
        assert _sig_marker(0.04) == "*"
        assert _sig_marker(0.5) == "ns"
        assert _sig_marker(float("nan")) == "ns"
