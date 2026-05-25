"""Tests for Phase 8a.8 recovery-trajectory assembly and plotting."""
from __future__ import annotations

import json
import math
import subprocess
import sys

import pytest

from stroke_orofacial.spout_behavior.recovery_trajectories import (
    build_trajectory_points,
    discover_endpoint_jsons,
    extract_endpoint_metric,
    load_endpoint_payload,
    plot_recovery_trajectories,
    save_trajectory_figure,
    summarize_cohort,
)


def _can_import_matplotlib() -> bool:
    result = subprocess.run(
        [sys.executable, "-c", "import matplotlib.pyplot"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _payload(
    animal: str,
    day: int,
    value: float,
    *,
    date: str = "2025-03-07",
    n_trials: int = 20,
) -> dict:
    return {
        "schema_version": "2.0.0",
        "metadata": {
            "animal": animal,
            "date": date,
            "phase": "8a.7.5",
            "day_relative_to_stroke": day,
            "n_trials": n_trials,
        },
        "endpoints": {
            "first_lick_latency_per_trial": {
                "per_session_aggregate": {"mean_s": value, "n": n_trials},
                "per_trial_array": [value, value + 0.1],
                "per_trial_type_split": {
                    "L": {"mean_s": value},
                    "R": {"mean_s": value + 0.2},
                },
                "provenance": {"endpoint_name": "first_lick_latency_per_trial"},
            },
            "tone_trial_count_per_session": {
                "per_session_aggregate": {"L": 4, "R": 6, "total": 10},
                "per_trial_array": None,
                "per_trial_type_split": None,
                "provenance": {"endpoint_name": "tone_trial_count_per_session"},
            },
            "inter_session_persistence": {
                "status": "requires_cohort_aggregation",
                "computed_at": "cohort_aggregation_stage",
            },
        },
        "criteria": {},
    }


class TestMetricExtraction:
    def test_extracts_nested_scalar_metric(self):
        payload = _payload("PS46", -3, 0.25)
        value = extract_endpoint_metric(
            payload,
            "first_lick_latency_per_trial",
            "per_session_aggregate.mean_s",
        )
        assert value == pytest.approx(0.25)

    def test_extracts_side_aware_metric(self):
        payload = _payload("PS46", -3, 0.25)
        value = extract_endpoint_metric(
            payload,
            "tone_trial_count_per_session",
            "per_session_aggregate.total",
        )
        assert value == 10.0

    def test_sentinel_endpoint_returns_nan(self):
        payload = _payload("PS46", -3, 0.25)
        value = extract_endpoint_metric(
            payload,
            "inter_session_persistence",
            "per_session_aggregate.lag_k_autocorr",
        )
        assert math.isnan(value)


class TestTrajectoryPoints:
    def test_build_points_drops_nan_and_applies_grouping(self):
        payloads = [
            _payload("PS46", -3, 0.3),
            _payload("PS47", -2, 0.4),
            _payload("PS48", -1, float("nan")),
        ]
        points = build_trajectory_points(
            payloads,
            endpoint_name="first_lick_latency_per_trial",
            metric_path="per_session_aggregate.mean_s",
            grouping_function=lambda animal: "mock_fast" if animal == "PS46" else "all",
        )
        assert [p.animal for p in points] == ["PS47", "PS46"]
        assert [p.group for p in points] == ["all", "mock_fast"]
        assert all(not math.isnan(p.value) for p in points)

    def test_build_points_skips_missing_day_relative_to_stroke(self):
        payload = _payload("PS46", -3, 0.3)
        payload["metadata"]["day_relative_to_stroke"] = None
        points = build_trajectory_points(
            [payload],
            endpoint_name="first_lick_latency_per_trial",
            metric_path="per_session_aggregate.mean_s",
        )
        assert points == []


class TestCohortSummary:
    def test_summarize_cohort_mean_and_sem(self):
        payloads = [
            _payload("PS46", 1, 1.0),
            _payload("PS47", 1, 3.0),
            _payload("PS48", 2, 5.0),
        ]
        points = build_trajectory_points(
            payloads,
            endpoint_name="first_lick_latency_per_trial",
            metric_path="per_session_aggregate.mean_s",
        )
        summary = summarize_cohort(points)
        day1 = next(s for s in summary if s.day_relative_to_stroke == 1)
        day2 = next(s for s in summary if s.day_relative_to_stroke == 2)
        assert day1.mean == pytest.approx(2.0)
        assert day1.sem == pytest.approx(1.0)
        assert day1.n == 2
        assert day2.mean == pytest.approx(5.0)
        assert day2.sem == 0.0
        assert day2.n == 1


class TestJsonDiscovery:
    def test_discovers_sorted_endpoint_jsons_and_loads_payload(self, tmp_path):
        root = tmp_path / "spout_behavior" / "endpoints"
        for animal, date, value in [
            ("PS47", "20250308", 0.4),
            ("PS46", "20250307", 0.3),
        ]:
            path = root / animal / f"{date}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_payload(animal, -1, value, date=date)))

        paths = discover_endpoint_jsons(root)
        assert [p.as_posix().split("/")[-2:] for p in paths] == [
            ["PS46", "20250307.json"],
            ["PS47", "20250308.json"],
        ]
        loaded = load_endpoint_payload(paths[0])
        assert loaded["metadata"]["animal"] == "PS46"


class TestPlotting:
    def test_plot_and_save_representative_cohort_figure(self, tmp_path):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib import unavailable in this environment")
        import matplotlib

        matplotlib.use("Agg", force=True)
        payloads = [
            _payload("PS46", -1, 0.5, date="2025-03-12"),
            _payload("PS46", 1, 0.8, date="2025-03-14"),
            _payload("PS47", -1, 0.4, date="2025-03-12"),
            _payload("PS47", 1, 0.7, date="2025-03-14"),
        ]
        points = build_trajectory_points(
            payloads,
            endpoint_name="first_lick_latency_per_trial",
            metric_path="per_session_aggregate.mean_s",
        )
        fig = plot_recovery_trajectories(
            points,
            title="First lick latency",
            ylabel="Latency (s)",
        )
        try:
            out = save_trajectory_figure(fig, tmp_path / "cohort.png")
            assert out.exists()
            assert out.stat().st_size > 0
            assert fig.axes[0].get_ylabel() == "Latency (s)"
        finally:
            import matplotlib.pyplot as plt

            plt.close(fig)


class TestPlotRecoveryTrajectoriesWithFit:
    """Phase 9 Task 6 — overlay FitResult + bootstrap CI on recovery trajectories."""

    def _make_points(self, animals, pre_n=4, post_n=10, post_shift=0.3, rng_seed=0):
        import datetime as _dt
        import numpy as np
        from stroke_orofacial.spout_behavior.recovery_trajectories import TrajectoryPoint
        rng = np.random.default_rng(rng_seed)
        points = []
        for a in animals:
            offset = float(rng.normal(0, 0.1))
            for i in range(pre_n):
                rd = -pre_n + i
                points.append(TrajectoryPoint(
                    animal=a, date=_dt.date(2025, 3, 1) + _dt.timedelta(days=pre_n + i),
                    day_relative_to_stroke=rd,
                    endpoint_name="ep", metric_path="ep",
                    value=offset + 0.5 + float(rng.normal(0, 0.05)),
                    group="all",
                ))
            for j in range(1, post_n + 1):
                points.append(TrajectoryPoint(
                    animal=a, date=_dt.date(2025, 3, 10) + _dt.timedelta(days=j),
                    day_relative_to_stroke=j,
                    endpoint_name="ep", metric_path="ep",
                    value=offset + 0.5 + post_shift * j + float(rng.normal(0, 0.05)),
                    group="all",
                ))
        return points

    def _fit_proxy(self, slope: float, intercept: float):
        class _P:
            pass
        p = _P()
        p.details = {"status": "ok", "slope": slope, "intercept": intercept, "slope_se": 0.01}
        p.model_name = "recovery_mixedlm"
        p.statistic = slope
        p.p_value = 1e-6
        return p

    def test_overlays_fit_line_with_slope_label(self, tmp_path):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib import unavailable in this environment")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.spout_behavior.recovery_trajectories import (
            plot_recovery_trajectories_with_fit, save_trajectory_figure,
        )
        points = self._make_points(["PS46", "PS47", "PS48", "PS49"])
        fit = self._fit_proxy(slope=0.3, intercept=0.5)
        fig = plot_recovery_trajectories_with_fit(
            points, fit, title="Test", ylabel="ep", n_boot=100,
        )
        try:
            out = save_trajectory_figure(fig, tmp_path / "withfit.png")
            assert out.exists()
            # Slope label should appear in one of the legend handles.
            ax = fig.axes[0]
            labels = [t.get_text() for t in ax.get_legend().get_texts()]
            assert any("slope" in label.lower() for label in labels)
        finally:
            import matplotlib.pyplot as plt
            plt.close(fig)

    def test_renders_without_fit_when_details_missing(self, tmp_path):
        """FitResult with no slope/intercept → plot still renders (just
        scatter + mean/SEM) + tagged with [fit status: ...]."""
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib import unavailable in this environment")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.spout_behavior.recovery_trajectories import (
            plot_recovery_trajectories_with_fit,
        )
        points = self._make_points(["PS46", "PS47", "PS48"])

        class _P:
            pass

        p = _P()
        p.details = {"status": "insufficient_data"}
        p.model_name = "recovery_mixedlm"
        p.statistic = float("nan")
        p.p_value = float("nan")
        fig = plot_recovery_trajectories_with_fit(points, p, n_boot=50)
        try:
            ax = fig.axes[0]
            # Status annotation should be present.
            texts = [t.get_text() for t in ax.texts]
            assert any("fit status" in t for t in texts)
        finally:
            import matplotlib.pyplot as plt
            plt.close(fig)

    def test_cohort_points_kwarg_used_for_bootstrap(self):
        """When `points` is from one animal but `cohort_points` is from
        many, the bootstrap CI ribbon should be computed off
        `cohort_points`."""
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib import unavailable in this environment")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.spout_behavior.recovery_trajectories import (
            plot_recovery_trajectories_with_fit,
        )
        cohort = self._make_points(["PS46", "PS47", "PS48", "PS49"], pre_n=4, post_n=10)
        per_animal = [p for p in cohort if p.animal == "PS46"]
        fit = self._fit_proxy(slope=0.3, intercept=0.5)
        fig = plot_recovery_trajectories_with_fit(
            per_animal, fit, cohort_points=cohort, n_boot=100,
        )
        try:
            ax = fig.axes[0]
            labels = [t.get_text() for t in ax.get_legend().get_texts()]
            assert any("bootstrap CI" in label for label in labels), (
                "Expected bootstrap CI label when cohort_points provided."
            )
        finally:
            import matplotlib.pyplot as plt
            plt.close(fig)

    def test_ci_zero_skips_ribbon(self):
        if not _can_import_matplotlib():
            pytest.skip("Matplotlib import unavailable in this environment")
        import matplotlib
        matplotlib.use("Agg", force=True)
        from stroke_orofacial.spout_behavior.recovery_trajectories import (
            plot_recovery_trajectories_with_fit,
        )
        points = self._make_points(["PS46", "PS47", "PS48"])
        fit = self._fit_proxy(slope=0.3, intercept=0.5)
        fig = plot_recovery_trajectories_with_fit(points, fit, ci=0.0)
        try:
            ax = fig.axes[0]
            labels = [t.get_text() for t in ax.get_legend().get_texts()]
            assert not any("bootstrap CI" in label for label in labels)
        finally:
            import matplotlib.pyplot as plt
            plt.close(fig)
