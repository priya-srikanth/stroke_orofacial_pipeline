"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoint_result` (Phase 8a.3)."""
from __future__ import annotations

import json
import math

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult


def _make_result() -> EndpointResult:
    return EndpointResult(
        per_session_aggregate={"mean": 0.5, "std": 0.1, "n": 10},
        per_trial_array=np.array([0.1, 0.2, float("nan"), 0.4]),
        per_trial_type_split={
            "L": {"mean": 0.3, "n": 2},
            "R": {"mean": 0.7, "n": 2},
        },
        provenance={
            "endpoint_name": "test_endpoint",
            "config_snapshot": {"key": "value", "nested": {"x": 1}},
            "n_trials_input": 4,
            "n_trials_used": 3,
        },
    )


class TestToDict:
    def test_basic_to_dict_keys(self):
        d = _make_result().to_dict()
        assert set(d.keys()) == {
            "per_session_aggregate", "per_trial_array",
            "per_trial_type_split", "provenance",
        }

    def test_numpy_array_becomes_list(self):
        d = _make_result().to_dict()
        assert isinstance(d["per_trial_array"], list)
        assert d["per_trial_array"][0] == 0.1
        assert math.isnan(d["per_trial_array"][2])

    def test_none_per_trial_array_preserved(self):
        r = EndpointResult(
            per_session_aggregate=0.5, per_trial_array=None,
            per_trial_type_split=None,
            provenance={"endpoint_name": "x", "config_snapshot": {},
                        "n_trials_input": 0, "n_trials_used": 0},
        )
        d = r.to_dict()
        assert d["per_trial_array"] is None
        assert d["per_trial_type_split"] is None

    def test_round_trip_through_json(self):
        # NaN requires allow_nan=True (Python default).
        d = _make_result().to_dict()
        s = json.dumps(d)
        d2 = json.loads(s)
        # NaN -> "NaN" literal through Python json; reload yields float nan.
        assert math.isnan(d2["per_trial_array"][2])


class TestFromDict:
    def test_from_dict_round_trip_equivalent(self):
        r = _make_result()
        r2 = EndpointResult.from_dict(r.to_dict())
        assert r2.per_session_aggregate == r.per_session_aggregate
        assert r2.per_trial_type_split == r.per_trial_type_split
        assert r2.provenance == r.provenance
        # per_trial_array round-trips to np.ndarray.
        assert isinstance(r2.per_trial_array, np.ndarray)
        np.testing.assert_array_equal(
            np.nan_to_num(r2.per_trial_array, nan=-1),
            np.nan_to_num(r.per_trial_array, nan=-1),
        )
        assert math.isnan(r2.per_trial_array[2])

    def test_from_dict_with_none_array(self):
        d = {
            "per_session_aggregate": 0.5,
            "per_trial_array": None,
            "per_trial_type_split": None,
            "provenance": {"endpoint_name": "x", "config_snapshot": {},
                           "n_trials_input": 0, "n_trials_used": 0},
        }
        r = EndpointResult.from_dict(d)
        assert r.per_trial_array is None
        assert r.per_trial_type_split is None


class TestFrozen:
    def test_cannot_mutate(self):
        import dataclasses
        r = _make_result()
        try:
            r.per_session_aggregate = 99.0  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            return
        raise AssertionError("Expected FrozenInstanceError on frozen dataclass")
