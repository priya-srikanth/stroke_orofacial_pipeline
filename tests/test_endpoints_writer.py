"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_writer` (Phase 8a.7.5).

Schema 2.0.0 — three top-level blocks (metadata / endpoints / criteria) with
strict key validation on both the ``endpoints`` and ``criteria`` inputs,
auto-filled C1 sentinel, SHA-256 NPZ provenance hashes, and atomic-write-via-
temp-file semantics.

No parity tests — schema is a clean break from legacy ``report.json``
(per kickoff scoping decision Q6, with legacy staying byte-stable). Criteria
parity lives in ``tests/test_criteria.py``.
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
    CALLER_SUPPLIED_CRITERIA_SLUGS,
    CANONICAL_ENDPOINT_NAMES,
    COHORT_AGGREGATED_CRITERIA_SLUG,
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


def _make_full_criteria_dict() -> dict[str, dict[str, Any]]:
    """Minimal valid ``criteria`` dict covering the 3 caller-supplied slugs."""
    return {
        "criteria_first_correct_lick_present": {
            "status": "computed",
            "per_side_per_trial_pass": {"L": [True, False], "R": [True]},
            "config_snapshot": {"window_seconds": [0.0, 2.0]},
        },
        "criteria_correct_lick_count_threshold": {
            "status": "computed",
            "per_side_per_trial_pass": {"L": [True, True], "R": [False]},
            "config_snapshot": {
                "window_seconds": [0.0, 2.5],
                "num_licks_correct_min": 5,
                "num_licks_incorrect_max": 0,
            },
        },
        "criteria_session_trial_pass_fraction_above_threshold": {
            "status": "computed",
            "per_side_pass": {"L": True, "R": False},
            "per_side_fraction": {"L": 0.5, "R": 0.0},
            "per_side_n_trials": {"L": 2, "R": 1},
            "config_snapshot": {"fraction_pass": 0.6},
        },
    }


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
        "criteria": _make_full_criteria_dict(),
        "source_npz_paths": {
            "licks_and_rewards": npz_a,
            "wavesurfer_signals_processed": npz_b,
        },
        "output_path": tmp_path / "out" / "PS46" / "20250307.json",
        "defaults": DEFAULTS_STUB,
        "n_trials": 87,
        "day_relative_to_stroke": -3,
        # Task #17: matched-rig default in the fixture keeps the
        # pre-existing per-side assertions semantically unchanged
        # (no L/R flip at emit). TestSideConventionStamp /
        # TestLRFlipAtEmit (added in commit 4) cover the flipped-rig
        # path explicitly.
        "wavesurfer_sides_match_mouse_sides": True,
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
            # Task #17 side-convention stamp.
            "wavesurfer_sides_match_mouse_sides", "side_convention_version",
        }
        assert meta["animal"] == "PS46"
        assert meta["date"] == "2025-03-07"
        assert meta["phase"] == "8a.7.5"
        assert meta["day_relative_to_stroke"] == -3
        assert meta["n_trials"] == 87
        assert set(meta["source_npz_hashes"].keys()) == {
            "licks_and_rewards", "wavesurfer_signals_processed",
        }
        # The fixture passes wavesurfer_sides_match_mouse_sides=True, so
        # the stamp records the matched-rig case here.
        assert meta["wavesurfer_sides_match_mouse_sides"] is True
        assert meta["side_convention_version"] == 1

    def test_endpoints_block_keys_match_canonical_set(
        self, writer_kwargs: dict[str, Any],
    ):
        out_path = write_session_endpoints_json(**writer_kwargs)
        endpoints = json.loads(out_path.read_text())["endpoints"]
        assert frozenset(endpoints.keys()) == CANONICAL_ENDPOINT_NAMES


# ---------------------------------------------------------------------------
# 5. Sentinel patterns
# ---------------------------------------------------------------------------


class TestCriteriaComputed:
    def test_computed_c3_c4_c2_pass_through_unchanged(
        self, writer_kwargs: dict[str, Any],
    ):
        """Caller-supplied C3/C4/C2 blocks serialize byte-identical."""
        out_path = write_session_endpoints_json(**writer_kwargs)
        criteria = json.loads(out_path.read_text())["criteria"]
        caller_block = _make_full_criteria_dict()
        for slug in CALLER_SUPPLIED_CRITERIA_SLUGS:
            assert criteria[slug] == caller_block[slug], slug

    def test_c1_auto_filled_with_cohort_sentinel(
        self, writer_kwargs: dict[str, Any],
    ):
        """Writer fills C1 with ``requires_cohort_aggregation`` — caller did not pass it."""
        out_path = write_session_endpoints_json(**writer_kwargs)
        criteria = json.loads(out_path.read_text())["criteria"]
        c1 = criteria[COHORT_AGGREGATED_CRITERIA_SLUG]
        assert c1 == INTER_SESSION_REQUIRES_COHORT_SENTINEL
        assert c1["status"] == "requires_cohort_aggregation"
        assert c1["computed_at"] == "cohort_aggregation_stage"

    def test_criteria_block_has_all_four_slugs(
        self, writer_kwargs: dict[str, Any],
    ):
        """All 4 criteria slugs present — 3 computed + C1 cohort sentinel."""
        out_path = write_session_endpoints_json(**writer_kwargs)
        criteria = json.loads(out_path.read_text())["criteria"]
        assert set(criteria.keys()) == (
            set(CALLER_SUPPLIED_CRITERIA_SLUGS)
            | {COHORT_AGGREGATED_CRITERIA_SLUG}
        )


class TestSentinels:
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


class TestCriteriaValidation:
    def test_missing_criteria_key_rejected(self, writer_kwargs: dict[str, Any]):
        bad_criteria = dict(writer_kwargs["criteria"])
        del bad_criteria["criteria_first_correct_lick_present"]
        bad_kwargs = dict(writer_kwargs, criteria=bad_criteria)
        with pytest.raises(ValueError, match="missing criteria keys"):
            write_session_endpoints_json(**bad_kwargs)

    def test_unknown_criteria_key_rejected(self, writer_kwargs: dict[str, Any]):
        bad_criteria = dict(writer_kwargs["criteria"])
        bad_criteria["criteria_made_up"] = {"status": "computed"}
        bad_kwargs = dict(writer_kwargs, criteria=bad_criteria)
        with pytest.raises(ValueError, match="unknown criteria keys"):
            write_session_endpoints_json(**bad_kwargs)

    def test_c1_slug_in_criteria_rejected(self, writer_kwargs: dict[str, Any]):
        """Caller must not supply C1 — writer owns that slot."""
        bad_criteria = dict(writer_kwargs["criteria"])
        bad_criteria[COHORT_AGGREGATED_CRITERIA_SLUG] = {
            "status": "caller_tried_to_override",
        }
        bad_kwargs = dict(writer_kwargs, criteria=bad_criteria)
        with pytest.raises(ValueError, match="must not include"):
            write_session_endpoints_json(**bad_kwargs)

    def test_empty_criteria_rejected(self, writer_kwargs: dict[str, Any]):
        bad_kwargs = dict(writer_kwargs, criteria={})
        with pytest.raises(ValueError, match="missing criteria keys"):
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


def _trial(idx: int, tone_idx: int, *, Fs: float = 1000.0) -> TrialRecord:
    """Build a minimal TrialRecord with a 0–2.5 s scoring window.

    Phase 8a.10.1 Q-A.β + Q-B.α (2026-05-14): trial anchor renamed
    ``reward_idx → tone_idx`` and side field ``reward_side → tone_side``.
    Reward paired synchronously at tone_idx (cohort's actual property).
    """
    return TrialRecord(
        trial_idx=idx,
        tone_side="L",
        tone_idx=tone_idx,
        reward_idx=tone_idx,
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


# ---------------------------------------------------------------------------
# Side-convention regression guards (task #17 commit 4/5)
# ---------------------------------------------------------------------------


class TestSideConventionAtEmit:
    """Regression guards for task-#17 L/R translation inside
    ``write_session_endpoints_json``. Exercises both the matched-rig
    (flag=True, no flip) and flipped-rig (flag=False, L↔R swapped)
    paths, plus the convention-scalar stamping in the metadata block."""

    def _writer_kwargs_with_flag(
        self, tmp_path: Path, ws_match: bool,
    ) -> dict[str, Any]:
        """Helper: writer_kwargs variant with an explicit flag value."""
        npz = _write_synthetic_npz(
            tmp_path / "src" / "licks_and_rewards.npz",
            {"x": np.arange(3)},
        )
        return {
            "animal": "PS46",
            "date": datetime.date(2025, 3, 7),
            "endpoints": _make_full_endpoints_dict(),
            "criteria": _make_full_criteria_dict(),
            "source_npz_paths": {"licks_and_rewards": npz},
            "output_path": tmp_path / "out.json",
            "defaults": DEFAULTS_STUB,
            "n_trials": 87,
            "day_relative_to_stroke": -3,
            "wavesurfer_sides_match_mouse_sides": ws_match,
        }

    def test_matched_rig_preserves_per_side_keys_unchanged(self, tmp_path):
        """flag=True → no translation. L/R values survive byte-for-byte."""
        kwargs = self._writer_kwargs_with_flag(tmp_path, ws_match=True)
        out = write_session_endpoints_json(**kwargs)
        loaded = json.loads(out.read_text())
        c3 = loaded["criteria"]["criteria_first_correct_lick_present"]
        # Caller passed per_side_per_trial_pass={"L": [T, F], "R": [T]}.
        # Matched rig → emitted unchanged.
        assert c3["per_side_per_trial_pass"]["L"] == [True, False]
        assert c3["per_side_per_trial_pass"]["R"] == [True]
        c2 = loaded["criteria"][
            "criteria_session_trial_pass_fraction_above_threshold"
        ]
        assert c2["per_side_pass"] == {"L": True, "R": False}
        assert c2["per_side_fraction"] == {"L": 0.5, "R": 0.0}
        assert c2["per_side_n_trials"] == {"L": 2, "R": 1}

    def test_flipped_rig_swaps_per_side_keys_in_criteria(self, tmp_path):
        """flag=False → per-side dict keys flipped at emit. Caller-supplied
        wavesurfer-frame L values are emitted under mouse-frame L = old R."""
        kwargs = self._writer_kwargs_with_flag(tmp_path, ws_match=False)
        out = write_session_endpoints_json(**kwargs)
        loaded = json.loads(out.read_text())

        # C3: caller passed L=[T, F], R=[T]. Flipped rig emits L=[T], R=[T, F].
        c3 = loaded["criteria"]["criteria_first_correct_lick_present"]
        assert c3["per_side_per_trial_pass"]["L"] == [True]
        assert c3["per_side_per_trial_pass"]["R"] == [True, False]

        # C4: caller passed L=[T, T], R=[F]. Flipped → L=[F], R=[T, T].
        c4 = loaded["criteria"]["criteria_correct_lick_count_threshold"]
        assert c4["per_side_per_trial_pass"]["L"] == [False]
        assert c4["per_side_per_trial_pass"]["R"] == [True, True]

        # C2: all three per_side_* dicts flip.
        c2 = loaded["criteria"][
            "criteria_session_trial_pass_fraction_above_threshold"
        ]
        assert c2["per_side_pass"] == {"L": False, "R": True}
        assert c2["per_side_fraction"] == {"L": 0.0, "R": 0.5}
        assert c2["per_side_n_trials"] == {"L": 1, "R": 2}

    def test_flipped_rig_swaps_per_trial_type_split_in_endpoints(self, tmp_path):
        """flag=False also flips per_trial_type_split L/R keys in
        every endpoint that has that field."""
        kwargs = self._writer_kwargs_with_flag(tmp_path, ws_match=False)
        out = write_session_endpoints_json(**kwargs)
        loaded = json.loads(out.read_text())

        # The fixture's _make_endpoint_result sets
        # per_trial_type_split={"L": {"mean": 0.15}, "R": {"mean": 0.45}}.
        # Flipped rig emits L={"mean": 0.45}, R={"mean": 0.15}.
        for name, endpoint in loaded["endpoints"].items():
            if name == "inter_session_persistence":
                continue  # sentinel, no per_trial_type_split
            split = endpoint["per_trial_type_split"]
            assert split["L"] == {"mean": 0.45}, name
            assert split["R"] == {"mean": 0.15}, name

    @pytest.mark.parametrize("ws_match", [True, False])
    def test_metadata_block_stamped_with_convention_scalars(
        self, tmp_path, ws_match,
    ):
        """Every emitted JSON's metadata block carries the two
        convention scalars regardless of flag value."""
        kwargs = self._writer_kwargs_with_flag(tmp_path, ws_match=ws_match)
        out = write_session_endpoints_json(**kwargs)
        meta = json.loads(out.read_text())["metadata"]
        assert meta["wavesurfer_sides_match_mouse_sides"] is ws_match
        assert meta["side_convention_version"] == 1

    def test_c1_sentinel_passes_through_unchanged_on_flipped_rig(self, tmp_path):
        """The C1 cohort-aggregation sentinel has no L/R structure;
        translation must leave it as the verbatim sentinel dict."""
        kwargs = self._writer_kwargs_with_flag(tmp_path, ws_match=False)
        out = write_session_endpoints_json(**kwargs)
        loaded = json.loads(out.read_text())
        assert loaded["criteria"][COHORT_AGGREGATED_CRITERIA_SLUG] == dict(
            INTER_SESSION_REQUIRES_COHORT_SENTINEL
        )
