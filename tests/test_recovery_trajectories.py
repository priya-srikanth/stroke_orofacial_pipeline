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
