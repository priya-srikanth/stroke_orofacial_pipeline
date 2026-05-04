"""Phase 7a.4-cross-session-angle (2026-05-04): unit tests for the
``tongue_angle_cohort`` module.

Smoke-level coverage of the pure-logic helpers (NaN-safe mean ± SEM,
day-binning) + a renderer smoke test with a synthetic cohort
aggregate. Real-data integration coverage comes from the visual
gate render (PS46/PS50/PS55) at session close.
"""
from __future__ import annotations

import datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pytest


_HOST_KEY = "mac"


# ============================================================================
# _robust_mean_sem
# ============================================================================


class TestRobustMeanSEM:
    def test_basic_mean_sem(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _robust_mean_sem,
        )
        # Three trials × 4 t-bins; trivial input.
        M = np.array([
            [1.0, 2.0, 3.0, 4.0],
            [2.0, 4.0, 6.0, 8.0],
            [3.0, 6.0, 9.0, 12.0],
        ])
        mu, sem, n_trials = _robust_mean_sem(M)
        assert mu.tolist() == [2.0, 4.0, 6.0, 8.0]
        # ddof=0 SD per column = sqrt(2/3) per col-0; SEM = sd / sqrt(3).
        expected_sem_col0 = np.sqrt(2.0 / 3.0) / np.sqrt(3.0)
        assert sem[0] == pytest.approx(expected_sem_col0, abs=1e-9)
        assert n_trials == 3

    def test_nan_safe(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _robust_mean_sem,
        )
        M = np.array([
            [1.0, np.nan, 3.0],
            [np.nan, np.nan, 4.0],
            [3.0, 4.0, np.nan],
        ])
        mu, sem, n_trials = _robust_mean_sem(M)
        # Col 0: finite vals = [1, 3] → mu=2; col 1: [4] → mu=4; col 2: [3, 4] → mu=3.5.
        assert mu[0] == pytest.approx(2.0)
        assert mu[1] == pytest.approx(4.0)
        assert mu[2] == pytest.approx(3.5)
        # n_trials = number of trials with at least one finite value across t-bins
        # All 3 trials have ≥1 finite value → n_trials = 3.
        assert n_trials == 3

    def test_all_nan_column(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _robust_mean_sem,
        )
        M = np.array([
            [np.nan, 1.0],
            [np.nan, 2.0],
        ])
        mu, sem, n_trials = _robust_mean_sem(M)
        assert np.isnan(mu[0])
        assert mu[1] == pytest.approx(1.5)
        assert np.isnan(sem[0])  # all-NaN column → NaN SEM
        assert n_trials == 2

    def test_1d_input_promoted(self):
        """Passing a 1D array (single trial) is promoted to a (1, N)
        matrix; SEM is 0 (n=1)."""
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _robust_mean_sem,
        )
        v = np.array([1.0, 2.0, 3.0])
        mu, sem, n_trials = _robust_mean_sem(v)
        assert mu.tolist() == [1.0, 2.0, 3.0]
        # ddof=0 SD of single sample = 0; SEM = 0.
        assert (sem == 0).all()
        assert n_trials == 1


# ============================================================================
# Day-binning
# ============================================================================


class TestDayBinning:
    def test_pre_stroke_pools_into_one_bin(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _make_rel_day_bins,
        )
        # Pre-stroke: -6, -3, -1; post-stroke: 1, 5, 12 with bin_days=2.
        bins = _make_rel_day_bins([-6, -3, -1, 1, 5, 12], bin_days=2)
        # Pre-stroke pools: (-6, -1).
        assert (-6, -1) in bins
        # Post-stroke: 1 → bin (0, 1); 5 → bin (4, 5); 12 → bin (12, 13).
        post_bins = [b for b in bins if b[0] >= 0]
        assert (0, 1) in post_bins
        assert (4, 5) in post_bins
        assert (12, 13) in post_bins

    def test_no_pre_stroke(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _make_rel_day_bins,
        )
        bins = _make_rel_day_bins([0, 5, 7, 38], bin_days=7)
        # 0 → (0, 6); 5 → (0, 6); 7 → (7, 13); 38 → (35, 41).
        assert (0, 6) in bins
        assert (7, 13) in bins
        assert (35, 41) in bins
        # Sorted by lo.
        for prev, nxt in zip(bins, bins[1:]):
            assert prev[0] < nxt[0]

    def test_assign_to_bin(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _assign_to_bin, _make_rel_day_bins,
        )
        bins = _make_rel_day_bins([-3, 1, 8], bin_days=7)
        assert _assign_to_bin(-2, bins) == (-3, -1)
        assert _assign_to_bin(3, bins) == (0, 6)
        assert _assign_to_bin(8, bins) == (7, 13)
        # Out-of-range day → None.
        assert _assign_to_bin(-100, bins) is None

    def test_empty_input(self):
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _make_rel_day_bins,
        )
        assert _make_rel_day_bins([], bin_days=2) == []


# ============================================================================
# Renderer smoke (synthetic cohort)
# ============================================================================


def _make_synthetic_cohort_first_peak_aligned(
    *,
    animal: str = "PS50",
    bin_days: int = 2,
    rel_days: tuple[int, ...] = (-3, -1, 0, 2, 5),
    n_t_bins: int = 50,
    seed: int = 7,
) -> Any:
    """Build a synthetic :class:`TongueAngleCohortAggregates` with
    ``first_peak_aligned`` family rows for renderer smoke tests.
    """
    from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
        TimeSeriesSessionAggregate,
        TongueAngleCohortAggregates,
    )
    rng = np.random.default_rng(seed)
    t = np.linspace(-180.0, 1000.0, n_t_bins)
    rows: list[TimeSeriesSessionAggregate] = []
    for rel_day in rel_days:
        d = (
            datetime.date(2025, 3, 13)
            + datetime.timedelta(days=int(rel_day))
        )
        for side in ("L", "R"):
            base = (
                10.0 * np.sin(2 * np.pi * t / 400.0)
                * (1 if side == "R" else -1)
            )
            mu = base + rng.normal(0, 0.5, size=n_t_bins)
            sem = np.full_like(mu, 0.5)
            rows.append(TimeSeriesSessionAggregate(
                family="first_peak_aligned",
                side=side, date=d, rel_day=rel_day,
                n_trials=20, t=t, mu=mu, sem=sem,
            ))
    return TongueAngleCohortAggregates(
        animal=animal, bin_days=bin_days, ts_rows=rows,
    )


class TestFirstPeakAlignedRenderers:
    def test_session_overlays_returns_two_panel_figure(self):
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _plot_first_peak_aligned_session_overlays,
        )
        cohort = _make_synthetic_cohort_first_peak_aligned()
        params = load_defaults()
        fig = _plot_first_peak_aligned_session_overlays(cohort, params=params)
        assert isinstance(fig, plt.Figure)
        # 1×2 cam-view: left panel = R-trials, right panel = L-trials.
        assert len(fig.axes) >= 2
        assert "R trials" in fig.axes[0].get_title()
        assert "L trials" in fig.axes[1].get_title()
        # Each panel has one Line2D per session (5 sessions in
        # synthetic) plus axhline / axvline reference lines.
        for ax in fig.axes[:2]:
            mean_lines = [
                ln for ln in ax.get_lines()
                if len(ln.get_xdata()) > 5
            ]
            # Synthetic has 5 rel_days × 1 side per panel = 5 mean
            # curves expected.
            assert len(mean_lines) == 5
        plt.close(fig)

    def test_binned_overlays_returns_two_panel_figure(self):
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_kinematics.tongue_angle_cohort import (
            _plot_first_peak_aligned_binned_overlays,
        )
        cohort = _make_synthetic_cohort_first_peak_aligned(
            bin_days=2,
            rel_days=(-3, -1, 0, 2, 5),
        )
        params = load_defaults()
        fig = _plot_first_peak_aligned_binned_overlays(cohort, params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 2
        # Bins for synthetic data: pre = (-3, -1); post bins (0, 1),
        # (2, 3) wait — bin_days=2 ⇒ post bins start at 0 with width 2:
        # 0→(0, 1), 2→(2, 3), 5→(4, 5). 4 bins total expected.
        # Binned rendering must produce at least 1 line per side
        # per bin that meets min_sessions_per_bin=1.
        for ax in fig.axes[:2]:
            mean_lines = [
                ln for ln in ax.get_lines()
                if len(ln.get_xdata()) > 5
            ]
            assert len(mean_lines) >= 1
        plt.close(fig)
