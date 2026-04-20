"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_writer` (Phase 8a.7).

Schema 2.0.0 — three top-level blocks (metadata / endpoints / criteria) with
strict key validation, sentinel patterns for not-yet-computed slots,
SHA-256 NPZ provenance hashes, and atomic-write-via-temp-file semantics.

No parity tests — schema is a clean break from legacy ``report.json``
(per kickoff scoping decision Q6, with legacy staying byte-stable).
"""
from __future__ import annotations

import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult
from stroke_orofacial.spout_behavior.endpoints_writer import (
    CANONICAL_ENDPOINT_NAMES,
    CRITERIA_NOT_YET_COMPUTED_SENTINEL,
    INTER_SESSION_REQUIRES_COHORT_SENTINEL,
    SCHEMA_VERSION,
    lick_bouts_to_endpoint_result,
    write_session_endpoints_json,
)
from stroke_orofacial.spout_behavior.lick_bouts import LickBout
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


# Minimal defaults dict supplying the criteria_slug_map the writer needs.
# Mirrors the structure in configs/defaults.yaml (spout_behavior.endpoints.criteria_slug_map).
DEFAULTS_STUB: dict[str, Any] = {
    "spout_behavior": {
        "endpoints": {
            "criteria_slug_map": {
                "criteria_1": "criteria_training_pass_consecutive_sessions",
                "criteria_2": "criteria_session_trial_pass_fraction_above_threshold",
                "criteria_3": "criteria_first_correct_lick_present",
                "criteria_4": "criteria_correct_lick_count_threshold",
            },
        },
    },
}


def _make_endpoint_result(name: str) -> EndpointResult:
    """Minimal valid EndpointResult, named via provenance for traceability."""
    return EndpointResult(
        per_session_aggregate={"mean": 0.5, "n": 3},
        per_trial_array=np.array([0.1, 0.2, 0.3]),
        per_trial_type_split={"L": {"mean": 0.15}, "R": {"mean": 0.45}},
        provenance={
            "endpoint_name": name,
            "config_snapshot": {},
            "n_trials_input": 3,
            "n_trials_used": 3,
        },
    )


def _make_full_endpoints_dict() -> dict[str, EndpointResult | dict[str, Any]]:
    """All 10 canonical keys: 9 EndpointResults + the inter_session sentinel."""
    out: dict[str, EndpointResult | dict[str, Any]] = {
        name: _make_endpoint_result(name)
        for name in CANONICAL_ENDPOINT_NAMES
        if name != "inter_session_persistence"
    }
    out["inter_session_persistence"] = dict(INTER_SESSION_REQUIRES_COHORT_SENTINEL)
    return out


def _write_synthetic_npz(path: Path, content: dict[str, np.ndarray]) -> Path:
    """Write a small NPZ file at ``path`` and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **content)
    return path


@pytest.fixture
def writer_kwargs(tmp_path: Path) -> dict[str, Any]:
    """Standard writer call kwargs against tmp_path filesystem."""
    npz_a = _write_synthetic_npz(
        tmp_path / "src" / "licks_and_rewards.npz",
        {"x": np.arange(5)},
    )
    npz_b = _write_synthetic_npz(
        tmp_path / "src" / "wavesurfer_signals_processed.npz",
        {"y": np.array([1.0, 2.0, 3.0])},
    )
    return {
        "animal": "PS46",
        "date": datetime.date(2025, 3, 7),
        "endpoints": _make_full_endpoints_dict(),
        "source_npz_paths": {
            "licks_and_rewards": npz_a,
            "wavesurfer_signals_processed": npz_b,
        },
        "output_path": tmp_path / "out" / "PS46" / "20250307.json",
        "defaults": DEFAULTS_STUB,
        "n_trials": 87,
        "day_relative_to_stroke": -3,
    }


# ---------------------------------------------------------------------------
# 1. Round-trip
# ---------------------------------------------------------------------------


class TestSchemaRoundTrip:
    def test_schema_round_trip_json_loads(self, writer_kwargs: dict[str, Any]):
        out_path = write_session_endpoints_json(**writer_kwargs)
        assert out_path.exists()
        loaded = json.loads(out_path.read_text())
        # Top-level blocks all present and JSON-decodable.
        assert isinstance(loaded, dict)
        assert loaded["schema_version"] == SCHEMA_VERSION
        assert isinstance(loaded["metadata"], dict)
        assert isinstance(loaded["endpoints"], dict)
        assert isinstance(loaded["criteria"], dict)


# ---------------------------------------------------------------------------
# 2-4. Block-shape validation
# ---------------------------------------------------------------------------


class TestBlockShapes:
    def test_top_level_blocks_present(self, writer_kwargs: dict[str, Any]):
        out_path = write_session_endpoints_json(**writer_kwargs)
        loaded = json.loads(out_path.read_text())
        assert set(loaded.keys()) == {
            "schema_version", "metadata", "endpoints", "criteria",
        }

    def test_metadata_block_complete(self, writer_kwargs: dict[str, Any]):
        out_path = write_session_endpoints_json(**writer_kwargs)
        meta = json.loads(out_path.read_text())["metadata"]
        assert set(meta.keys()) == {
            "animal", "date", "phase", "day_relative_to_stroke",
            "n_trials", "source_npz_hashes", "writer_run_timestamp",
        }
        assert meta["animal"] == "PS46"
        assert meta["date"] == "2025-03-07"
        assert meta["phase"] == "8a.7"
        assert meta["day_relative_to_stroke"] == -3
        assert meta["n_trials"] == 87
        assert set(meta["source_npz_hashes"].keys()) == {
            "licks_and_rewards", "wavesurfer_signals_processed",
        }

    def test_endpoints_block_keys_match_canonical_set(
        self, writer_kwargs: dict[str, Any],
    ):
        out_path = write_session_endpoints_json(**writer_kwargs)
        endpoints = json.loads(out_path.read_text())["endpoints"]
        assert frozenset(endpoints.keys()) == CANONICAL_ENDPOINT_NAMES


# ---------------------------------------------------------------------------
# 5. Sentinel patterns
# ---------------------------------------------------------------------------


class TestSentinels:
    def test_criteria_block_sentinel_pattern(self, writer_kwargs: dict[str, Any]):
        """Every criteria value is the explicit sentinel — never None, never absent."""
        out_path = write_session_endpoints_json(**writer_kwargs)
        criteria = json.loads(out_path.read_text())["criteria"]
        expected_slugs = {
            "criteria_training_pass_consecutive_sessions",
            "criteria_session_trial_pass_fraction_above_threshold",
            "criteria_first_correct_lick_present",
            "criteria_correct_lick_count_threshold",
        }
        assert set(criteria.keys()) == expected_slugs
        for slug, value in criteria.items():
            assert value is not None, f"{slug} must not be null"
            assert value == CRITERIA_NOT_YET_COMPUTED_SENTINEL, (
                f"{slug} sentinel mismatch: {value}"
            )
            assert value["status"] == "not_yet_computed"
            assert value["port_scheduled_for"] == "8a.7.5"

    def test_inter_session_sentinel_passthrough(self, writer_kwargs: dict[str, Any]):
        """Caller-supplied inter_session sentinel survives serialization unchanged."""
        out_path = write_session_endpoints_json(**writer_kwargs)
        endpoints = json.loads(out_path.read_text())["endpoints"]
        assert endpoints["inter_session_persistence"] == (
            INTER_SESSION_REQUIRES_COHORT_SENTINEL
        )
        assert endpoints["inter_session_persistence"]["status"] == (
            "requires_cohort_aggregation"
        )


# ---------------------------------------------------------------------------
# 6-7. Provenance hashing
# ---------------------------------------------------------------------------


class TestProvenanceHashes:
    def test_provenance_hash_determinism(self, writer_kwargs: dict[str, Any]):
        """Same NPZ inputs across two writer calls → identical hashes."""
        first = write_session_endpoints_json(**writer_kwargs)
        first_hashes = json.loads(first.read_text())["metadata"]["source_npz_hashes"]
        # Second call to a different output path, same NPZs.
        second_kwargs = dict(writer_kwargs)
        second_kwargs["output_path"] = (
            writer_kwargs["output_path"].parent / "20250307_second.json"
        )
        second = write_session_endpoints_json(**second_kwargs)
        second_hashes = json.loads(second.read_text())["metadata"]["source_npz_hashes"]
        assert first_hashes == second_hashes
        assert all(len(h) == 64 for h in first_hashes.values())  # SHA-256 hex

    def test_provenance_hash_changes_when_npz_bytes_change(
        self, writer_kwargs: dict[str, Any], tmp_path: Path,
    ):
        first = write_session_endpoints_json(**writer_kwargs)
        first_hash = json.loads(first.read_text())["metadata"][
            "source_npz_hashes"
        ]["licks_and_rewards"]
        # Mutate the underlying NPZ contents.
        _write_synthetic_npz(
            writer_kwargs["source_npz_paths"]["licks_and_rewards"],
            {"x": np.arange(99)},
        )
        second_kwargs = dict(writer_kwargs)
        second_kwargs["output_path"] = (
            writer_kwargs["output_path"].parent / "20250307_after_mutation.json"
        )
        second = write_session_endpoints_json(**second_kwargs)
        second_hash = json.loads(second.read_text())["metadata"][
            "source_npz_hashes"
        ]["licks_and_rewards"]
        assert first_hash != second_hash


# ---------------------------------------------------------------------------
# 8. Schema version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_schema_version_is_2_0_0(self, writer_kwargs: dict[str, Any]):
        out_path = write_session_endpoints_json(**writer_kwargs)
        assert json.loads(out_path.read_text())["schema_version"] == "2.0.0"
        assert SCHEMA_VERSION == "2.0.0"


# ---------------------------------------------------------------------------
# 9. Atomic-write semantics
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_atomic_write_no_partial_on_exception(
        self,
        writer_kwargs: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """If serialization raises mid-write, no .json appears AND no .tmp leaks."""
        import stroke_orofacial.spout_behavior.endpoints_writer as mod

        def boom(*args: Any, **kwargs: Any) -> str:
            raise RuntimeError("simulated serialization failure")

        monkeypatch.setattr(mod.json, "dumps", boom)
        with pytest.raises(RuntimeError, match="simulated"):
            write_session_endpoints_json(**writer_kwargs)
        out_path: Path = writer_kwargs["output_path"]
        assert not out_path.exists(), "no partial output should be visible"
        # TemporaryDirectory cleanup → no .tmp.json sibling left behind.
        leftovers = list(out_path.parent.glob("*.tmp.json"))
        assert leftovers == [], f"unexpected leftovers: {leftovers}"


# ---------------------------------------------------------------------------
# 10-11. Strict key validation (D8)
# ---------------------------------------------------------------------------


class TestStrictKeyValidation:
    def test_invalid_endpoint_key_rejected(self, writer_kwargs: dict[str, Any]):
        bad_endpoints = dict(writer_kwargs["endpoints"])
        bad_endpoints["something_unknown"] = _make_endpoint_result("unknown")
        bad_kwargs = dict(writer_kwargs, endpoints=bad_endpoints)
        with pytest.raises(ValueError, match="unknown endpoint keys"):
            write_session_endpoints_json(**bad_kwargs)

    def test_missing_endpoint_key_rejected(self, writer_kwargs: dict[str, Any]):
        bad_endpoints = dict(writer_kwargs["endpoints"])
        del bad_endpoints["switch_cost_per_session"]
        bad_kwargs = dict(writer_kwargs, endpoints=bad_endpoints)
        with pytest.raises(ValueError, match="missing endpoint keys"):
            write_session_endpoints_json(**bad_kwargs)


# ---------------------------------------------------------------------------
# 12. NaN preservation
# ---------------------------------------------------------------------------


class TestNanPreservation:
    def test_nan_preserved(self, writer_kwargs: dict[str, Any]):
        """NaN values in per_trial_array survive JSON round-trip."""
        endpoints = dict(writer_kwargs["endpoints"])
        endpoints["first_lick_latency_per_trial"] = EndpointResult(
            per_session_aggregate={"mean": float("nan"), "n": 0},
            per_trial_array=np.array([0.1, float("nan"), 0.3]),
            per_trial_type_split=None,
            provenance={
                "endpoint_name": "first_lick_latency_per_trial",
                "config_snapshot": {},
                "n_trials_input": 3,
                "n_trials_used": 1,
            },
        )
        kwargs = dict(writer_kwargs, endpoints=endpoints)
        out_path = write_session_endpoints_json(**kwargs)
        loaded = json.loads(out_path.read_text())
        per_trial = loaded["endpoints"]["first_lick_latency_per_trial"][
            "per_trial_array"
        ]
        assert per_trial[0] == 0.1
        assert math.isnan(per_trial[1])
        assert per_trial[2] == 0.3


# ---------------------------------------------------------------------------
# Lick-bout adapter
# ---------------------------------------------------------------------------


def _trial(idx: int, reward_idx: int, *, Fs: float = 1000.0) -> TrialRecord:
    """Build a minimal TrialRecord with a 0–2.5 s scoring window."""
    return TrialRecord(
        trial_idx=idx,
        reward_side="L",
        reward_idx=reward_idx,
        tone_idx=None,
        trial_type="rewarded",
        licks_L_indices_in_window=np.array([], dtype=int),
        licks_R_indices_in_window=np.array([], dtype=int),
        window_seconds=(0.0, 2.5),
        Fs=Fs,
    )


class TestLickBoutAdapter:
    def test_empty_inputs(self):
        result = lick_bouts_to_endpoint_result(
            [], trials=[], Fs=1000.0, endpoints_params={"lick_bouts": {}},
        )
        agg = result.per_session_aggregate
        assert agg["n_bouts"] == 0
        assert math.isnan(agg["mean_n_licks"])
        assert math.isnan(agg["mean_within_bout_ili_s"])
        assert math.isnan(agg["mean_bout_duration_s"])
        assert math.isnan(agg["std_bouts_per_trial"])
        assert result.per_trial_array.size == 0

    def test_bouts_binned_into_trials_by_start_idx(self):
        # Two trials at sample 1000 and 5000, each with 2.5 s = 2500-sample window.
        trials = [_trial(0, 1000), _trial(1, 5000)]
        bouts = [
            LickBout(start_idx=1100, end_idx=1300, n_licks=3, mean_ili_s=0.1),
            LickBout(start_idx=1500, end_idx=1700, n_licks=2, mean_ili_s=0.2),
            LickBout(start_idx=5200, end_idx=5400, n_licks=4, mean_ili_s=0.05),
            LickBout(start_idx=9000, end_idx=9100, n_licks=2, mean_ili_s=0.05),
        ]
        result = lick_bouts_to_endpoint_result(
            bouts, trials=trials, Fs=1000.0, endpoints_params={"lick_bouts": {}},
        )
        # Trial 0 window [1000, 3500): bouts at 1100 + 1500 → 2.
        # Trial 1 window [5000, 7500): bout at 5200 → 1.
        # Bout at 9000 outside both windows: counted in n_bouts, not per_trial_array.
        np.testing.assert_array_equal(result.per_trial_array, np.array([2, 1]))
        assert result.per_session_aggregate["n_bouts"] == 4
        assert result.per_session_aggregate["mean_n_licks"] == pytest.approx(2.75)
        # std of per-trial counts [2, 1] = 0.5
        assert result.per_session_aggregate["std_bouts_per_trial"] == pytest.approx(0.5)
