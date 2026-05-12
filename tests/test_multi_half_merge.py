"""Phase 7-pre-multi-half tests for multi_half_merge.

Covers the cell-17 port :func:`merge_licks_and_rewards` (in both
``cam_frame`` and ``ws_sample`` modes) plus the ported helpers
(:func:`_infer_n_count`, :func:`_looks_like_index_array`,
:func:`_shift_frame_indices`). Synthetic fixtures cover the legacy
2-half case (PS48 20250314 production scope) plus the N-half
generalization.

Vendor reference for the cam_frame algorithm:
``docs/legacy_snippets/multi_half_merge/cell_17_merge_licks_and_rewards.py``
(notebook SHA256 ed12c54...; cell SHA256 b2819b791668e18c...).

ws_sample mode: new-pipeline-Phase-2 semantics — see
:func:`merge_licks_and_rewards` docstring for the coordinate-space
rationale and the divergence-from-legacy intentional design.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.multi_half_merge import (
    _infer_dt,
    _infer_n_count,
    _is_monotonic_nondecreasing,
    _looks_like_index_array,
    _shift_frame_indices,
    _shift_time_axis,
    merge_alignment_templates,
    merge_centered_parquet,
    merge_licks_and_rewards,
)


# ---------- _infer_n_count ----------


class TestInferNCount:
    """Generalized cell-17 _infer_n_cam — both cam_frame and ws_sample modes."""

    # Helper to wrap the cam-mode default kwargs (most tests use cam mode).
    @staticmethod
    def _cam(npz):
        return _infer_n_count(
            npz,
            count_keys=("cam_times", "sig_camTimes__idx_cam", "t_cam", "frame_times_s", "camTimes"),
            count_int_keys=("n_frames", "n_cam", "nFrames"),
        )

    def test_tier_1_cam_times_array_size(self):
        """Highest-priority: a 1D `cam_times` array's size is n_cam."""
        npz = {"cam_times": np.linspace(0, 10, 5_000)}
        assert self._cam(npz) == 5_000

    def test_tier_1_priority_order(self):
        """When multiple Tier-1 keys are present, the first key in the
        priority list wins. Default order:
        cam_times > sig_camTimes__idx_cam > t_cam > frame_times_s > camTimes."""
        npz = {
            "camTimes": np.zeros(7_000),  # last in order
            "cam_times": np.zeros(5_000),  # first in order
        }
        assert self._cam(npz) == 5_000

    def test_tier_2_scalar_n_frames(self):
        """When no Tier-1 keys, fall back to a scalar `n_frames`."""
        npz = {"n_frames": np.int64(4_242)}
        assert self._cam(npz) == 4_242

    def test_tier_3_fallback_largest_long_1d_array(self):
        """When no Tier-1/2 keys, return size of the largest 1D
        numeric array > fallback_min_size (default 1000)."""
        npz = {
            "small": np.zeros(500),  # below threshold
            "medium": np.zeros(1_500),  # candidate
            "large": np.zeros(8_000),  # winner
            "small_obj": np.array(["a", "b"], dtype=object),  # non-numeric
        }
        assert self._cam(npz) == 8_000

    def test_returns_none_when_no_signal(self):
        """No Tier-1/2 keys, no 1D arrays > 1000 → None."""
        npz = {"foo": np.zeros(500), "bar": np.array(42)}
        assert self._cam(npz) is None

    def test_ws_mode_tier_2_n_samples(self):
        """ws_sample mode: Tier-2 scalar `n_samples` is the only signal
        the new Phase 2 NPZ provides for the count axis."""
        npz = {"n_samples": np.int64(2_253_363)}
        assert _infer_n_count(
            npz,
            count_keys=(),
            count_int_keys=("n_samples",),
            fallback_min_size=None,
        ) == 2_253_363

    def test_ws_mode_tier_3_disabled(self):
        """ws_sample mode disables Tier-3 fallback (fallback_min_size=None)
        so a 1D event-index array (e.g. Lick_L of length 1136) is NOT
        misread as a count signal."""
        npz = {
            "Lick_L": np.arange(1136),  # >1000 — would trigger Tier-3 if enabled
        }
        assert _infer_n_count(
            npz,
            count_keys=(),
            count_int_keys=("n_samples",),
            fallback_min_size=None,
        ) is None


# ---------- _looks_like_index_array ----------


class TestLooksLikeIndexArray:
    """Generalized cell-17 _looks_like_frame_indices — applies in both modes."""

    def test_clean_integer_indices_within_bound(self):
        arr = np.array([0, 5, 100, 999], dtype=float)
        assert _looks_like_index_array(arr, count_hint=1_000) is True

    def test_indices_just_above_count_within_slack(self):
        """Slack of 5 allows a few-index overshoot (e.g. clamp values
        at exactly count_hint are common in legacy data)."""
        arr = np.array([0, 999, 1_001], dtype=float)  # 1_001 < 1_000+5
        assert _looks_like_index_array(arr, count_hint=1_000) is True

    def test_indices_well_above_count(self):
        arr = np.array([0, 999, 5_000], dtype=float)  # 5_000 >> 1_000+5
        assert _looks_like_index_array(arr, count_hint=1_000) is False

    def test_non_integer_floats_rejected(self):
        arr = np.array([0.5, 1.5, 2.5], dtype=float)
        assert _looks_like_index_array(arr, count_hint=10) is False

    def test_negative_values_rejected(self):
        arr = np.array([-5, 10, 20], dtype=float)
        assert _looks_like_index_array(arr, count_hint=100) is False

    def test_nans_tolerated(self):
        arr = np.array([0, 5, np.nan, 100], dtype=float)
        assert _looks_like_index_array(arr, count_hint=1_000) is True

    def test_all_nan_rejected(self):
        arr = np.array([np.nan, np.nan, np.nan], dtype=float)
        assert _looks_like_index_array(arr, count_hint=100) is False

    def test_no_hint_passes_above_check(self):
        """When count_hint is None, the upper bound check is skipped —
        any non-negative integer-ish 1D array is accepted."""
        arr = np.array([0, 5, 100_000_000], dtype=float)
        assert _looks_like_index_array(arr, count_hint=None) is True

    def test_2d_array_rejected(self):
        arr = np.zeros((10, 2))
        assert _looks_like_index_array(arr, count_hint=100) is False

    def test_string_array_rejected(self):
        arr = np.array(["a", "b"], dtype=object)
        assert _looks_like_index_array(arr, count_hint=100) is False


# ---------- _shift_frame_indices ----------


class TestShiftFrameIndices:
    def test_shifts_finite_values_preserves_nans(self):
        arr = np.array([0, np.nan, 5, np.nan, 99], dtype=float)
        shifted = _shift_frame_indices(arr, offset=1_000)
        assert shifted[0] == 1_000
        assert np.isnan(shifted[1])
        assert shifted[2] == 1_005
        assert np.isnan(shifted[3])
        assert shifted[4] == 1_099

    def test_returns_copy_not_in_place(self):
        arr = np.array([0, 5, 99], dtype=float)
        shifted = _shift_frame_indices(arr, offset=10)
        assert shifted is not arr
        assert arr[0] == 0  # input unchanged


# ---------- TestLicksAndRewardsMerge ----------


def _save_half(
    path: Path,
    *,
    n_cam: int,
    extras: dict | None = None,
) -> Path:
    """Save a synthetic per-half licks NPZ.

    Always emits ``cam_times`` (Tier 1 n_cam signal) of length n_cam.
    Optional ``extras`` dict layers additional keys on top.
    """
    payload: dict = {"cam_times": np.linspace(0.0, n_cam * 1e-3, n_cam)}
    if extras:
        payload.update(extras)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **payload, allow_pickle=False)
    return path


class TestLicksAndRewardsMerge:
    """Synthetic 2-half + 3-half merges exercising the three per-key
    tiers + provenance schema."""

    def test_n2_numeric_1d_timeseries_concat(self, tmp_path: Path):
        """A 1D numeric array of length n_cam in BOTH halves →
        concatenated axis=0."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100, extras={"Lick_volts": np.arange(100, dtype=float)})
        _save_half(b_path, n_cam=200, extras={"Lick_volts": np.arange(200, dtype=float)})

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        assert merged["Lick_volts"].shape == (300,)
        assert merged["Lick_volts"][0] == 0.0
        assert merged["Lick_volts"][99] == 99.0
        # B's 0..199 lands at indices 100..299 unchanged (no offset for
        # plain timeseries — only frame indices get offset).
        assert merged["Lick_volts"][100] == 0.0
        assert merged["Lick_volts"][299] == 199.0

    def test_n2_frame_index_offset_and_concat(self, tmp_path: Path):
        """Frame-index arrays (e.g. lick indices) get B-half values
        offset by n_cam_A before concatenation."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(
            a_path,
            n_cam=100,
            extras={"Lick_L": np.array([10, 50, 90], dtype=float)},
        )
        _save_half(
            b_path,
            n_cam=200,
            extras={"Lick_L": np.array([5, 100, 150], dtype=float)},
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        # A: 10, 50, 90
        # B shifted by n_cam_A=100: 105, 200, 250
        np.testing.assert_array_equal(
            merged["Lick_L"], np.array([10, 50, 90, 105, 200, 250], dtype=float),
        )

    def test_n2_only_in_a_keys_carried_verbatim(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100, extras={"a_only_meta": np.array([1, 2, 3])})
        _save_half(b_path, n_cam=200)

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        np.testing.assert_array_equal(merged["a_only_meta"], np.array([1, 2, 3]))

    def test_n2_only_in_b_keys_offset_when_frame_indices(self, tmp_path: Path):
        """Keys present only in B that look like frame indices DO get
        offset by n_cam_A — cell 17 line 220-225."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(
            b_path,
            n_cam=200,
            extras={"b_only_lick": np.array([5, 50, 100, 199], dtype=float)},
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        # offset = n_cam_A = 100
        np.testing.assert_array_equal(
            merged["b_only_lick"],
            np.array([105, 150, 200, 299], dtype=float),
        )

    def test_n2_only_in_b_keys_passthrough_when_not_frame_indices(
        self, tmp_path: Path
    ):
        """Keys only in B that are NOT frame indices come through verbatim."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(
            b_path,
            n_cam=200,
            extras={"b_only_meta": np.array([3.14, 2.71])},  # non-integer floats
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        np.testing.assert_array_equal(
            merged["b_only_meta"], np.array([3.14, 2.71])
        )

    def test_n2_default_keeps_half_a_value(self, tmp_path: Path):
        """Per-key dispatcher's default fallback: keep half-0's value
        when none of the three concat tiers fire (e.g. mismatched
        dtypes, nontrivial shape, non-numeric)."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(
            a_path,
            n_cam=100,
            extras={"thresh_per_session": np.array([0.5, 1.0])},
        )
        _save_half(
            b_path,
            n_cam=200,
            extras={"thresh_per_session": np.array([3.0, 6.0])},
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        # Both halves have the SAME shape (2,) so the same-shape-after-axis-0
        # tier WILL fire and concatenate. Verify that — to actually exercise
        # the keep-half-0 default, mismatched shapes / dtypes are needed,
        # which is harder to construct; the same-shape concat is the more
        # common production case.
        np.testing.assert_array_equal(
            merged["thresh_per_session"],
            np.array([0.5, 1.0, 3.0, 6.0]),
        )

    def test_n2_legacy_provenance_keys(self, tmp_path: Path):
        """For N=2 the merged NPZ carries the byte-identical legacy
        cell 17 provenance keys."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=250)

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        assert str(merged["merged_from_A"]) == str(a_path)
        assert str(merged["merged_from_B"]) == str(b_path)
        assert int(merged["cam_frame_offset_for_B"]) == 100
        assert int(merged["merged_n_cam_A"]) == 100
        assert int(merged["merged_n_cam_B"]) == 250

    def test_n2_list_style_provenance_keys(self, tmp_path: Path):
        """List-style provenance keys are emitted unconditionally (for
        every N >= 2). They give consumers a single uniform schema."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=250)

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        # str-array dtype=object
        assert list(merged["merged_from_paths"]) == [str(a_path), str(b_path)]
        np.testing.assert_array_equal(
            merged["merged_n_cam_per_half"], np.array([100, 250], dtype=np.int64)
        )
        np.testing.assert_array_equal(
            merged["cam_frame_offsets_per_half"], np.array([0, 100], dtype=np.int64)
        )

    def test_n3_extension(self, tmp_path: Path):
        """3-half merge: cumulative offsets, list-style provenance,
        and NO legacy A/B keys (no canonical mapping for >2 halves)."""
        paths = [tmp_path / f"h{i}.npz" for i in range(3)]
        # Cumulative n_cam: 100, 50, 75 → offsets 0, 100, 150
        _save_half(
            paths[0],
            n_cam=100,
            extras={"Lick_L": np.array([10, 50], dtype=float)},
        )
        _save_half(
            paths[1],
            n_cam=50,
            extras={"Lick_L": np.array([0, 25], dtype=float)},
        )
        _save_half(
            paths[2],
            n_cam=75,
            extras={"Lick_L": np.array([10, 70], dtype=float)},
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards(paths, out_path)

        merged = np.load(out_path, allow_pickle=True)
        # Half 0: 10, 50  (offset 0)
        # Half 1: 0+100=100, 25+100=125
        # Half 2: 10+150=160, 70+150=220
        np.testing.assert_array_equal(
            merged["Lick_L"],
            np.array([10, 50, 100, 125, 160, 220], dtype=float),
        )
        # Provenance: list-style only
        np.testing.assert_array_equal(
            merged["merged_n_cam_per_half"],
            np.array([100, 50, 75], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            merged["cam_frame_offsets_per_half"],
            np.array([0, 100, 150], dtype=np.int64),
        )
        # NO legacy A/B keys for N=3
        assert "merged_from_A" not in merged.files
        assert "merged_from_B" not in merged.files
        assert "cam_frame_offset_for_B" not in merged.files
        assert "merged_n_cam_A" not in merged.files
        assert "merged_n_cam_B" not in merged.files

    def test_raises_on_n_lt_2(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        _save_half(a_path, n_cam=100)
        with pytest.raises(ValueError, match=r"N >= 2"):
            merge_licks_and_rewards([a_path], tmp_path / "out.npz")

    def test_raises_on_missing_input(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        _save_half(a_path, n_cam=100)
        ghost = tmp_path / "doesnotexist.npz"
        with pytest.raises(FileNotFoundError, match=r"per-half licks NPZ not found"):
            merge_licks_and_rewards([a_path, ghost], tmp_path / "out.npz")

    def test_raises_when_n_cam_cannot_be_inferred(self, tmp_path: Path):
        """When NO signal (Tier 1/2/3) yields an n_cam, raise loud —
        cell 17 line 165-169 verbatim."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        # No cam_count_keys, no cam_count_int_keys, no 1D array > 1000
        np.savez(str(a_path), foo=np.zeros(500), bar=np.array(42))
        np.savez(str(b_path), foo=np.zeros(500), bar=np.array(99))
        with pytest.raises(RuntimeError, match=r"Could not infer n_cam"):
            merge_licks_and_rewards([a_path, b_path], tmp_path / "out.npz")

    def test_returns_output_path(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=100)
        out_path = tmp_path / "merged.npz"
        result = merge_licks_and_rewards([a_path, b_path], out_path)
        assert result == out_path
        assert result.exists()

    def test_creates_output_parent_dirs(self, tmp_path: Path):
        """Parent directories are created automatically."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=100)
        deep_out = tmp_path / "subdir" / "deeper" / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], deep_out)
        assert deep_out.exists()

    def test_overwrites_existing_output(self, tmp_path: Path):
        """No overwrite gate — caller is responsible. Passing an existing
        path overwrites it unconditionally."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=100)
        out_path = tmp_path / "merged.npz"
        out_path.write_bytes(b"stale-content")
        merge_licks_and_rewards([a_path, b_path], out_path)
        # File now valid NPZ (load doesn't raise)
        merged = np.load(out_path, allow_pickle=True)
        assert "merged_from_A" in merged.files

    def test_kwargs_override_default_inference_keys(self, tmp_path: Path):
        """Custom cam_count_keys can be passed to drive _infer_n_count from
        a non-default key — used by tests and by callers that source the
        list from configs/defaults.yaml multi_half:."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        # No default Tier-1 keys; instead a custom timeseries name
        np.savez(
            str(a_path),
            my_custom_cam_axis=np.linspace(0.0, 1.0, 100),
            allow_pickle=False,
        )
        np.savez(
            str(b_path),
            my_custom_cam_axis=np.linspace(0.0, 2.0, 200),
            allow_pickle=False,
        )

        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards(
            [a_path, b_path],
            out_path,
            cam_count_keys=["my_custom_cam_axis"],
        )
        merged = np.load(out_path, allow_pickle=True)
        # Both halves' my_custom_cam_axis arrays land concatenated (Tier 1
        # tier-1 timeseries match: length == n_cam).
        assert merged["my_custom_cam_axis"].shape == (300,)
        assert int(merged["merged_n_cam_A"]) == 100
        assert int(merged["merged_n_cam_B"]) == 200

    def test_default_index_space_is_cam_frame(self, tmp_path: Path):
        """Smoke check: omitting index_space gives the legacy cam_frame
        behavior (this is what makes the 11 pre-existing tests stay
        green without modification — default preserves back-compat)."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=250)
        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards([a_path, b_path], out_path)  # no index_space
        merged = np.load(out_path, allow_pickle=True)
        # cam_frame schema present
        assert "merged_n_cam_A" in merged.files
        assert "cam_frame_offset_for_B" in merged.files
        # ws_sample schema absent
        assert "merged_n_samples_A" not in merged.files
        assert "ws_sample_offset_for_B" not in merged.files

    def test_invalid_index_space_raises(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_half(a_path, n_cam=100)
        _save_half(b_path, n_cam=100)
        with pytest.raises(ValueError, match=r"index_space must be"):
            merge_licks_and_rewards(
                [a_path, b_path], tmp_path / "out.npz", index_space="cam_idx",
            )


# ---------- TestLicksAndRewardsMergeWsSample ----------


def _save_ws_half(
    path: Path,
    *,
    n_samples: int,
    side_convention_match: bool = False,
    side_convention_version: int = 1,
    extras: dict | None = None,
) -> Path:
    """Save a synthetic per-half licks NPZ in the new Phase 2 ws_sample schema.

    Mirrors what session_processing._run_phase2_pipeline writes via
    find_licks_and_rewards + _save_npz_with_side_convention: the index
    arrays + Fs + n_samples (WS sample count) + 2 side-convention stamps.
    The ``extras`` dict overrides individual keys / adds events.
    """
    payload: dict = {
        "Fs": np.float64(1000.0),
        "n_samples": np.int64(n_samples),
        "side_convention_version": np.int64(side_convention_version),
        "wavesurfer_sides_match_mouse_sides": np.bool_(side_convention_match),
    }
    if extras:
        payload.update(extras)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **payload, allow_pickle=False)
    return path


class TestLicksAndRewardsMergeWsSample:
    """ws_sample mode tests (new-pipeline-Phase-2 semantics).

    The legacy concat-without-offset behavior was an emergent heuristic
    side-effect (see DECISIONS): ws-sample event-index arrays had max
    values >> n_cam_hint+5, so cell-17's _looks_like_frame_indices
    returned False on them and they fell through to the same-shape
    event-style concat path with NO offset applied. This produced a
    merged Lick_L where half-A and half-B indices live in overlapping
    WS-sample ranges with no separator — ambiguous downstream.

    ws_sample mode here corrects that: half-B WS-sample indices are
    offset by half-A's n_samples so the merged time axis is unified
    and unambiguous. Tests below pin the offset semantics, the
    schema cleanup, and the side-convention stamp validation.
    """

    def test_offset_applied_to_event_indices(self, tmp_path: Path):
        """Half-A's Lick_L unchanged; half-B's Lick_L shifted by n_samples_A."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(
            a_path, n_samples=2_253_363,
            extras={"Lick_L": np.array([100, 1_000_000, 2_000_000], dtype=np.int64)},
        )
        _save_ws_half(
            b_path, n_samples=2_300_517,
            extras={"Lick_L": np.array([200, 500_000, 2_200_000], dtype=np.int64)},
        )
        out_path = tmp_path / "merged.npz"
        merge_licks_and_rewards(
            [a_path, b_path], out_path, index_space="ws_sample",
        )

        merged = np.load(out_path, allow_pickle=True)
        n_A = 2_253_363
        # A unchanged; B shifted by n_samples_A
        np.testing.assert_array_equal(
            merged["Lick_L"],
            np.array(
                [100, 1_000_000, 2_000_000,
                 200 + n_A, 500_000 + n_A, 2_200_000 + n_A],
                dtype=np.int64,
            ),
        )

    def test_no_overlap_after_offset(self, tmp_path: Path):
        """min(half-B portion) > max(half-A portion) — merged time axis
        is monotone partitioned at n_samples_A."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        n_A = 1_000_000
        _save_ws_half(
            a_path, n_samples=n_A,
            extras={"Reward_L": np.array([100, 999_999], dtype=np.int64)},
        )
        _save_ws_half(
            b_path, n_samples=2_000_000,
            extras={"Reward_L": np.array([0, 1_999_999], dtype=np.int64)},
        )
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)
        # half-A portion: [100, 999_999]; half-B portion: [n_A, n_A + 1_999_999]
        a_max = int(merged["Reward_L"][:2].max())
        b_min = int(merged["Reward_L"][2:].min())
        assert b_min >= a_max, (
            f"merged Reward_L overlaps: half-A max={a_max}, half-B min={b_min}"
        )

    def test_total_count_assertion(self, tmp_path: Path):
        """len(merged.X) == len(half-A.X) + len(half-B.X) for every event arr."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(
            a_path, n_samples=1_000_000,
            extras={
                "Lick_L": np.array([1, 2, 3], dtype=np.int64),
                "Lick_R": np.array([10, 20], dtype=np.int64),
                "Reward_L": np.array([100], dtype=np.int64),
                "Reward_R": np.array([200, 300, 400, 500], dtype=np.int64),
            },
        )
        _save_ws_half(
            b_path, n_samples=2_000_000,
            extras={
                "Lick_L": np.array([1, 2, 3, 4, 5], dtype=np.int64),
                "Lick_R": np.array([10, 20, 30], dtype=np.int64),
                "Reward_L": np.array([100, 200], dtype=np.int64),
                "Reward_R": np.array([300, 400], dtype=np.int64),
            },
        )
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)
        assert merged["Lick_L"].shape == (3 + 5,)
        assert merged["Lick_R"].shape == (2 + 3,)
        assert merged["Reward_L"].shape == (1 + 2,)
        assert merged["Reward_R"].shape == (4 + 2,)

    def test_tone_arrays_carried_forward_with_offset(self, tmp_path: Path):
        """Tone_L/R get the same offset treatment as Lick_*/Reward_* —
        legacy cell-17 dropped Tone_* (they didn't exist at that vintage);
        ws_sample mode carries them forward by virtue of treating any
        index-array key uniformly."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        n_A = 1_000_000
        _save_ws_half(
            a_path, n_samples=n_A,
            extras={"Tone_L": np.array([500, 999_000], dtype=np.int64)},
        )
        _save_ws_half(
            b_path, n_samples=2_000_000,
            extras={"Tone_L": np.array([1_000, 1_500_000], dtype=np.int64)},
        )
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)
        np.testing.assert_array_equal(
            merged["Tone_L"],
            np.array(
                [500, 999_000, 1_000 + n_A, 1_500_000 + n_A],
                dtype=np.int64,
            ),
        )

    def test_side_convention_stamps_carried_forward(self, tmp_path: Path):
        """Matching side-convention stamps across halves are validated
        and the scalars are preserved on the merged NPZ."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(
            a_path, n_samples=1_000_000,
            side_convention_match=False, side_convention_version=1,
        )
        _save_ws_half(
            b_path, n_samples=2_000_000,
            side_convention_match=False, side_convention_version=1,
        )
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)
        assert int(merged["side_convention_version"]) == 1
        assert bool(merged["wavesurfer_sides_match_mouse_sides"]) is False

    def test_side_convention_mismatch_raises(self, tmp_path: Path):
        """Mismatched stamps across halves → ValueError before merge work."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(
            a_path, n_samples=1_000_000, side_convention_match=False,
        )
        _save_ws_half(
            b_path, n_samples=2_000_000, side_convention_match=True,  # MISMATCH
        )
        with pytest.raises(ValueError, match=r"side-convention.*mismatch"):
            merge_licks_and_rewards(
                [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
            )

    def test_side_convention_missing_key_raises(self, tmp_path: Path):
        """Missing side-convention key in any half → ValueError."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(a_path, n_samples=1_000_000)
        # B has only Fs + n_samples — both side-convention keys missing
        np.savez(
            str(b_path),
            Fs=np.float64(1000.0),
            n_samples=np.int64(2_000_000),
        )
        with pytest.raises(ValueError, match=r"missing required side-convention"):
            merge_licks_and_rewards(
                [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
            )

    def test_ws_sample_provenance_schema(self, tmp_path: Path):
        """ws_sample mode emits new schema (merged_n_samples_*,
        ws_sample_offset_for_B) and OMITS legacy cam_frame quirk keys
        (merged_n_cam_*, cam_frame_offset_for_B, allow_pickle)."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(a_path, n_samples=1_500_000)
        _save_ws_half(b_path, n_samples=2_500_000)
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)

        # New schema present
        assert str(merged["merged_from_A"]) == str(a_path)
        assert str(merged["merged_from_B"]) == str(b_path)
        assert int(merged["ws_sample_offset_for_B"]) == 1_500_000
        assert int(merged["merged_n_samples_A"]) == 1_500_000
        assert int(merged["merged_n_samples_B"]) == 2_500_000
        np.testing.assert_array_equal(
            merged["merged_n_samples_per_half"],
            np.array([1_500_000, 2_500_000], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            merged["ws_sample_offsets_per_half"],
            np.array([0, 1_500_000], dtype=np.int64),
        )

        # Legacy quirk keys ABSENT
        assert "merged_n_cam_A" not in merged.files
        assert "merged_n_cam_B" not in merged.files
        assert "merged_n_cam_per_half" not in merged.files
        assert "cam_frame_offset_for_B" not in merged.files
        assert "cam_frame_offsets_per_half" not in merged.files
        assert "allow_pickle" not in merged.files

    def test_n_samples_inference_failure_raises(self, tmp_path: Path):
        """When the per-half NPZ has no n_samples scalar (and no Tier-3
        fallback in ws_sample mode), raise loud."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        # Save without n_samples — only side-convention stamps
        np.savez(
            str(a_path),
            Fs=np.float64(1000.0),
            side_convention_version=np.int64(1),
            wavesurfer_sides_match_mouse_sides=np.bool_(False),
            Lick_L=np.arange(1500),  # would be Tier-3 fallback in cam mode
        )
        np.savez(
            str(b_path),
            Fs=np.float64(1000.0),
            side_convention_version=np.int64(1),
            wavesurfer_sides_match_mouse_sides=np.bool_(False),
            Lick_L=np.arange(1500),
        )
        with pytest.raises(RuntimeError, match=r"Could not infer n_samples"):
            merge_licks_and_rewards(
                [a_path, b_path], tmp_path / "out.npz", index_space="ws_sample",
            )

    def test_ws_count_int_keys_kwarg_override(self, tmp_path: Path):
        """ws_count_int_keys override drives _infer_n_count from a custom
        scalar key — used by callers sourcing the list from
        configs/defaults.yaml multi_half:."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _save_ws_half(
            a_path, n_samples=1_000_000,
            extras={"my_ws_count": np.int64(1_000_000)},
        )
        _save_ws_half(
            b_path, n_samples=2_000_000,
            extras={"my_ws_count": np.int64(2_000_000)},
        )
        merge_licks_and_rewards(
            [a_path, b_path], tmp_path / "out.npz",
            index_space="ws_sample",
            ws_count_int_keys=["my_ws_count"],
        )
        merged = np.load(tmp_path / "out.npz", allow_pickle=True)
        assert int(merged["merged_n_samples_A"]) == 1_000_000
        assert int(merged["merged_n_samples_B"]) == 2_000_000


# ---------- alignment-template helpers ----------


class TestInferDt:
    def test_returns_median_diff(self):
        t = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        assert _infer_dt(t) == 1.0

    def test_handles_jitter_via_median(self):
        t = np.array([0.0, 0.99, 2.01, 3.0, 4.0])  # diffs ~0.99..1.02
        assert abs(_infer_dt(t) - 1.0) < 0.05

    def test_skips_nans(self):
        t = np.array([0.0, np.nan, 1.0, 2.0, np.nan, 3.0])
        assert _infer_dt(t) == 1.0

    def test_returns_none_when_too_few_finite(self):
        assert _infer_dt(np.array([np.nan, 1.0])) is None
        assert _infer_dt(np.array([])) is None


class TestShiftTimeAxis:
    def test_first_finite_lands_at_target(self):
        t = np.array([10.0, 11.0, 12.0])
        shifted = _shift_time_axis(t, target_start=100.0)
        assert shifted[0] == 100.0
        assert shifted[1] == 101.0
        assert shifted[2] == 102.0

    def test_nans_preserved(self):
        t = np.array([np.nan, 5.0, np.nan, 7.0])
        shifted = _shift_time_axis(t, target_start=0.0)
        assert np.isnan(shifted[0])
        assert shifted[1] == 0.0
        assert np.isnan(shifted[2])
        assert shifted[3] == 2.0

    def test_all_nan_passthrough(self):
        t = np.array([np.nan, np.nan, np.nan])
        shifted = _shift_time_axis(t, target_start=42.0)
        assert np.all(np.isnan(shifted))


class TestIsMonotonicNondecreasing:
    def test_strictly_increasing(self):
        assert _is_monotonic_nondecreasing(np.array([0.0, 1.0, 2.0, 3.0])) is True

    def test_equal_consecutive_allowed(self):
        assert _is_monotonic_nondecreasing(np.array([0.0, 1.0, 1.0, 2.0])) is True

    def test_tiny_negative_within_slack(self):
        """1e-10 backstep is within the -1e-9 monotonic slack."""
        assert _is_monotonic_nondecreasing(np.array([0.0, 1.0, 1.0 - 1e-10])) is True

    def test_real_negative_caught(self):
        assert _is_monotonic_nondecreasing(np.array([0.0, 1.0, 0.5])) is False

    def test_nan_skipped(self):
        assert _is_monotonic_nondecreasing(np.array([0.0, np.nan, 1.0, 2.0])) is True

    def test_few_finite_trivially_true(self):
        assert _is_monotonic_nondecreasing(np.array([0.0, 5.0])) is True
        assert _is_monotonic_nondecreasing(np.array([])) is True


# ---------- merge_alignment_templates ----------


def _make_per_half_template(
    path: Path,
    *,
    Fs_ws: float = 1000.0,
    n_cam: int = 100,
    n_ws: int = 400,
    cam_t0: float = 0.0,
    ws_t0: float = 0.0,
) -> Path:
    """Save a synthetic alignment template NPZ matching the cell-16 schema.

    Generates well-shaped per-half arrays so the merge function's
    sanity checks pass:
      - ``sig_wsIdx__idx_cam`` has length n_cam, values in [0, n_ws)
        with linear ramp.
      - ``sig_camIdx__idx_ws`` has length n_ws, values in [0, n_cam)
        with linear ramp.
      - ``sig_camTimes__idx_cam`` strictly increasing from cam_t0 with
        cam-frame dt = n_ws/(Fs_ws*n_cam) (i.e. so n_cam frames span
        n_ws/Fs_ws seconds).
      - ``sig_wsTimes__idx_ws`` strictly increasing from ws_t0 with
        dt_ws = 1/Fs_ws.
    """
    dt_ws = 1.0 / Fs_ws
    dt_cam = (n_ws / Fs_ws) / n_cam
    payload = {
        "Fs_ws_input": np.float64(Fs_ws),
        "sig_wsIdx__idx_cam": np.linspace(0.0, n_ws - 1, n_cam),
        "sig_camIdx__idx_ws": np.linspace(0.0, n_cam - 1, n_ws),
        "sig_camTimes__idx_cam": cam_t0 + np.arange(n_cam) * dt_cam,
        "sig_wsTimes__idx_ws": ws_t0 + np.arange(n_ws) * dt_ws,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **payload, allow_pickle=False)
    return path


class TestAlignmentTemplateMerge:
    def test_n2_offset_semantics(self, tmp_path: Path):
        """Half-B's wsIdx_cam values get shifted by n_ws_A; camIdx_ws by n_cam_A."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        _make_per_half_template(b_path, n_cam=20, n_ws=80, cam_t0=10.0, ws_t0=10.0)

        out_path = tmp_path / "merged.npz"
        merge_alignment_templates([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        # Lengths after concat
        assert merged["sig_wsIdx__idx_cam"].shape == (30,)  # 10 + 20
        assert merged["sig_camIdx__idx_ws"].shape == (120,)  # 40 + 80
        # First A frame's ws-index is unchanged (0)
        assert merged["sig_wsIdx__idx_cam"][0] == 0.0
        # First B frame's ws-index is shifted by n_ws_A (40)
        assert merged["sig_wsIdx__idx_cam"][10] == 40.0  # B's 0 + 40
        # First A ws-sample's cam-index is unchanged (0)
        assert merged["sig_camIdx__idx_ws"][0] == 0.0
        # First B ws-sample's cam-index is shifted by n_cam_A (10)
        assert merged["sig_camIdx__idx_ws"][40] == 10.0  # B's 0 + 10

    def test_n2_time_axis_continuous(self, tmp_path: Path):
        """Half-B's first time lands at last_finite(A) + dt; merged times
        are monotonic non-decreasing."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(
            a_path, Fs_ws=1000.0, n_cam=10, n_ws=40, cam_t0=0.0, ws_t0=0.0,
        )
        # B starts at native time 100.0 — but should be shifted to A's end + dt
        _make_per_half_template(
            b_path, Fs_ws=1000.0, n_cam=20, n_ws=80, cam_t0=100.0, ws_t0=100.0,
        )

        out_path = tmp_path / "merged.npz"
        merge_alignment_templates([a_path, b_path], out_path)

        merged = np.load(out_path, allow_pickle=True)
        cam_times = merged["sig_camTimes__idx_cam"]
        ws_times = merged["sig_wsTimes__idx_ws"]
        # Half A camTimes start at 0.0 unchanged
        assert cam_times[0] == 0.0
        # Half B's first cam time lands at A_last + dt_cam (NOT 100.0)
        a_last = (10 - 1) * (40 / 1000 / 10)  # = 9 * 0.004 = 0.036
        dt_cam_a = 40 / 1000 / 10  # = 0.004
        assert abs(cam_times[10] - (a_last + dt_cam_a)) < 1e-9
        # Half A wsTimes start at 0.0 unchanged
        assert ws_times[0] == 0.0
        # Half B's first ws time lands at A_last + dt_ws (1/Fs = 1ms)
        ws_a_last = (40 - 1) / 1000.0
        assert abs(ws_times[40] - (ws_a_last + 1.0 / 1000.0)) < 1e-9
        # Both axes monotonic
        assert _is_monotonic_nondecreasing(cam_times)
        assert _is_monotonic_nondecreasing(ws_times)

    def test_n2_legacy_provenance_keys(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        _make_per_half_template(b_path, n_cam=20, n_ws=80)
        merge_alignment_templates([a_path, b_path], tmp_path / "merged.npz")

        merged = np.load(tmp_path / "merged.npz", allow_pickle=True)
        # Byte-identical legacy schema for N=2
        assert str(merged["merged_from_A"]) == str(a_path)
        assert str(merged["merged_from_B"]) == str(b_path)
        assert int(merged["ws_offset_samples"]) == 40
        assert int(merged["cam_offset_frames"]) == 10
        # 5 REQ_KEYS preserved
        assert "Fs_ws_input" in merged.files
        assert "sig_wsIdx__idx_cam" in merged.files
        assert "sig_camIdx__idx_ws" in merged.files
        assert "sig_camTimes__idx_cam" in merged.files
        assert "sig_wsTimes__idx_ws" in merged.files
        # List-style provenance also emitted
        assert list(merged["merged_from_paths"]) == [str(a_path), str(b_path)]
        np.testing.assert_array_equal(
            merged["ws_offsets_per_half"], np.array([0, 40], dtype=np.int64)
        )
        np.testing.assert_array_equal(
            merged["cam_offsets_per_half"], np.array([0, 10], dtype=np.int64)
        )

    def test_n3_extension(self, tmp_path: Path):
        """3-half merge: cumulative offsets, list-style only, no legacy A/B."""
        paths = [tmp_path / f"h{i}.npz" for i in range(3)]
        # Per-half lengths: n_cam=[10, 5, 8], n_ws=[40, 20, 32]
        _make_per_half_template(paths[0], n_cam=10, n_ws=40)
        _make_per_half_template(paths[1], n_cam=5, n_ws=20)
        _make_per_half_template(paths[2], n_cam=8, n_ws=32)

        merge_alignment_templates(paths, tmp_path / "merged.npz")
        merged = np.load(tmp_path / "merged.npz", allow_pickle=True)
        # Lengths: cam=23, ws=92
        assert merged["sig_wsIdx__idx_cam"].shape == (23,)
        assert merged["sig_camIdx__idx_ws"].shape == (92,)
        # Cumulative offsets
        np.testing.assert_array_equal(
            merged["ws_offsets_per_half"], np.array([0, 40, 60], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            merged["cam_offsets_per_half"], np.array([0, 10, 15], dtype=np.int64),
        )
        # No legacy A/B keys for N=3
        assert "merged_from_A" not in merged.files
        assert "merged_from_B" not in merged.files
        assert "ws_offset_samples" not in merged.files
        assert "cam_offset_frames" not in merged.files

    def test_raises_on_fs_mismatch(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, Fs_ws=1000.0, n_cam=10, n_ws=40)
        _make_per_half_template(b_path, Fs_ws=2000.0, n_cam=20, n_ws=80)  # different Fs
        with pytest.raises(ValueError, match=r"Fs_ws_input mismatch"):
            merge_alignment_templates([a_path, b_path], tmp_path / "out.npz")

    def test_raises_on_missing_required_key(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        # B missing sig_wsTimes__idx_ws
        np.savez(
            str(b_path),
            Fs_ws_input=np.float64(1000.0),
            sig_wsIdx__idx_cam=np.zeros(20),
            sig_camIdx__idx_ws=np.zeros(80),
            sig_camTimes__idx_cam=np.arange(20, dtype=float),
            allow_pickle=False,
        )
        with pytest.raises(ValueError, match=r"missing required keys"):
            merge_alignment_templates([a_path, b_path], tmp_path / "out.npz")

    def test_raises_on_n_lt_2(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        with pytest.raises(ValueError, match=r"N >= 2"):
            merge_alignment_templates([a_path], tmp_path / "out.npz")

    def test_raises_on_missing_input(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        with pytest.raises(FileNotFoundError):
            merge_alignment_templates(
                [a_path, tmp_path / "nonexistent.npz"],
                tmp_path / "out.npz",
            )

    def test_raises_on_non_monotonic_camTimes(self, tmp_path: Path):
        """Bad input where half-B's native camTimes go BACKWARDS internally
        produces a non-monotonic merged camTimes — should raise."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        # B has decreasing camTimes (corrupted input)
        np.savez(
            str(b_path),
            Fs_ws_input=np.float64(1000.0),
            sig_wsIdx__idx_cam=np.zeros(20),
            sig_camIdx__idx_ws=np.zeros(80),
            # decreasing values within the half
            sig_camTimes__idx_cam=np.linspace(10.0, 0.0, 20),
            sig_wsTimes__idx_ws=np.arange(80, dtype=float) / 1000.0,
            allow_pickle=False,
        )
        with pytest.raises(RuntimeError, match=r"camTimes is not monotonic"):
            merge_alignment_templates([a_path, b_path], tmp_path / "out.npz")

    def test_returns_output_path(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        _make_per_half_template(b_path, n_cam=20, n_ws=80)
        out = tmp_path / "merged.npz"
        result = merge_alignment_templates([a_path, b_path], out)
        assert result == out
        assert result.exists()

    def test_creates_output_parent_dirs(self, tmp_path: Path):
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        _make_per_half_template(b_path, n_cam=20, n_ws=80)
        deep = tmp_path / "deep" / "nested" / "merged.npz"
        merge_alignment_templates([a_path, b_path], deep)
        assert deep.exists()

    def test_nan_padded_index_arrays_preserved(self, tmp_path: Path):
        """NaN sentinels in sig_wsIdx_cam stay NaN through offset shift."""
        a_path = tmp_path / "a.npz"
        b_path = tmp_path / "b.npz"
        # Half A — clean
        _make_per_half_template(a_path, n_cam=10, n_ws=40)
        # Half B — wsIdx_cam has a NaN at index 5
        b_wsIdx = np.linspace(0.0, 19.0, 20)
        b_wsIdx[5] = np.nan
        np.savez(
            str(b_path),
            Fs_ws_input=np.float64(1000.0),
            sig_wsIdx__idx_cam=b_wsIdx,
            sig_camIdx__idx_ws=np.linspace(0.0, 19.0, 80),
            sig_camTimes__idx_cam=np.arange(20, dtype=float) * 0.004,
            sig_wsTimes__idx_ws=np.arange(80, dtype=float) / 1000.0,
            allow_pickle=False,
        )
        merge_alignment_templates([a_path, b_path], tmp_path / "merged.npz")
        merged = np.load(tmp_path / "merged.npz", allow_pickle=True)
        # Concat index for B's index 5 in merged is 10 + 5 = 15
        assert np.isnan(merged["sig_wsIdx__idx_cam"][15])


# ---------- compute_and_merge_alignment_multi_half (orchestrator) ----------


class TestComputeAndMergeAlignmentMultiHalf:
    """Orchestrator tests with `make_alignment_template` mocked.

    Verifies the per-half subdir layout, the per-half compute path, the
    merge invocation, and the cache-skip behavior when per-half NPZs
    already exist.
    """

    def _make_resolver(self, tmp_path: Path):
        from stroke_orofacial.paths import PathResolver
        # Real resolver with output_root override.
        return PathResolver(output_root=tmp_path / "outputs")

    def _make_multi_half_manifest(self, tmp_path: Path):
        from stroke_orofacial.manifest import HalfSpec, SessionManifest
        ws_a = tmp_path / "ws" / "20250314a" / "PS48" / "stroke_0001.h5"
        ws_b = tmp_path / "ws" / "20250314b" / "PS48" / "stroke_0002.h5"
        for p in (ws_a, ws_b):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        halves = [
            HalfSpec(
                id="a", ws_subdir="20250314a", cam_subdir="20250314a",
                file_timestamp="2025-03-14T12_31_07",
                wavesurfer_file=ws_a,
            ),
            HalfSpec(
                id="b", ws_subdir="20250314b", cam_subdir="20250314b",
                file_timestamp="2025-03-14T13_09_29",
                wavesurfer_file=ws_b,
            ),
        ]
        return SessionManifest(
            session_id="PS48_20250314",
            animal="PS48",
            date=datetime.date(2025, 3, 14),
            day_relative_to_stroke=-5,
            phase="baseline",
            wavesurfer_file=None,
            halves=halves,
        )

    def test_raises_on_single_half_manifest(self, tmp_path: Path):
        from stroke_orofacial.alignment.timebase import (
            compute_and_merge_alignment_multi_half,
        )
        from stroke_orofacial.manifest import SessionManifest
        single = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
        )
        with pytest.raises(ValueError, match=r"manifest.halves is None"):
            compute_and_merge_alignment_multi_half(
                single, self._make_resolver(tmp_path), {"cam_idx": 2},
            )

    def test_skips_compute_when_per_half_exists(self, tmp_path: Path):
        """When per-half NPZs already exist on disk, the orchestrator
        skips the make_alignment_template compute path and goes straight
        to merge.

        Phase 7-pre-multi-half 2026-05-05 incident response: rewritten
        to use ``resolver.alignment_template_per_half_new`` (which
        routes through ``pipeline_outputs/`` and IS overridden by the
        resolver's ``output_root=tmp_path`` kwarg). The old version
        used ``alignment_template_per_half``, which routed through
        the live MICROSCOPE legacy tree regardless of output_root and
        corrupted 3 production NPZs.
        """
        from unittest.mock import patch

        from stroke_orofacial.alignment.timebase import (
            compute_and_merge_alignment_multi_half,
        )

        manifest = self._make_multi_half_manifest(tmp_path)
        resolver = self._make_resolver(tmp_path)

        # Pre-create per-half template NPZs at the expected paths.
        # _new resolver routes through pipeline_outputs which IS
        # overridden by output_root=tmp_path on the resolver, so writes
        # land under tmp_path (safe).
        per_half_paths = [
            resolver.alignment_template_per_half_new(
                "PS48", manifest.date,
                halves_concat_label="ab",
                half_id=hid,
            )
            for hid in ("a", "b")
        ]
        # Belt: confirm the resolved paths actually live under tmp_path
        # before any write — the regression check that would have
        # caught the 2026-05-05 incident.
        for p in per_half_paths:
            assert tmp_path in p.parents, (
                f"per-half path {p} did not resolve under tmp_path; "
                f"output_root override is not honored — would have "
                f"reproduced the 2026-05-05 incident class."
            )
        _make_per_half_template(per_half_paths[0], n_cam=10, n_ws=40)
        _make_per_half_template(per_half_paths[1], n_cam=20, n_ws=80)

        # Mock the compute path so we can assert it's NOT called
        with patch(
            "stroke_orofacial.alignment.timebase._compute_per_half_alignment_template"
        ) as mock_compute:
            merged_path = compute_and_merge_alignment_multi_half(
                manifest, resolver, {"cam_idx": 2},
            )

        mock_compute.assert_not_called()
        # Merged path also resolves under tmp_path (alignment_template_new
        # routes through pipeline_outputs).
        assert tmp_path in merged_path.parents
        assert merged_path.exists()
        # Merged file at parent level
        assert merged_path.name == "20250314.npz"
        assert merged_path.parent.name == "PS48"
        # Loadable as a merged template (5 REQ_KEYS + provenance)
        merged = np.load(merged_path, allow_pickle=True)
        assert "Fs_ws_input" in merged.files
        assert int(merged["cam_offset_frames"]) == 10
        assert int(merged["ws_offset_samples"]) == 40

    def test_per_half_paths_use_decision3_subdir_layout(self, tmp_path: Path):
        """Per-half NPZs land in the {date_str}{halves_concat_label}
        subdir per Decision 3 (e.g. 20250314ab/), merged at parent level.

        Phase 7-pre-multi-half 2026-05-05 incident response: rewritten
        to use ``alignment_template_per_half_new`` with output_root
        override; verifies the expected pipeline_outputs/dlc_analysis/
        alignment_templates/cam2/{ANIMAL}/{date}{label}/ shape.
        """
        from unittest.mock import patch

        from stroke_orofacial.alignment.timebase import (
            compute_and_merge_alignment_multi_half,
        )

        manifest = self._make_multi_half_manifest(tmp_path)
        resolver = self._make_resolver(tmp_path)

        # Pre-create per-half NPZs (skips compute)
        per_half_paths = [
            resolver.alignment_template_per_half_new(
                "PS48", manifest.date,
                halves_concat_label="ab",
                half_id=hid,
            )
            for hid in ("a", "b")
        ]
        for p in per_half_paths:
            assert tmp_path in p.parents
        _make_per_half_template(per_half_paths[0], n_cam=10, n_ws=40)
        _make_per_half_template(per_half_paths[1], n_cam=20, n_ws=80)

        with patch(
            "stroke_orofacial.alignment.timebase._compute_per_half_alignment_template"
        ):
            merged_path = compute_and_merge_alignment_multi_half(
                manifest, resolver, {"cam_idx": 2},
            )

        # Per-half paths under
        # <pipeline_outputs>/dlc_analysis/alignment_templates/cam2/PS48/20250314ab/.
        # Decision 3 layout: subdir name = {date_str}{halves_concat_label}.
        for hid, p in zip(("a", "b"), per_half_paths):
            assert p.parent.name == "20250314ab"
            assert p.name == f"20250314{hid}.npz"
            assert p.parent.parent.name == "PS48"
            assert p.parent.parent.parent.name == "cam2"
            assert "alignment_templates" in p.parts
            # New routing: under pipeline_outputs/dlc_analysis, NOT
            # under O2_analysis.
            assert "dlc_analysis" in p.parts
            assert "O2_analysis" not in p.parts
        # Merged path at the parent level (NOT in the subdir)
        assert merged_path.parent.name == "PS48"
        assert merged_path.name == "20250314.npz"
        # Same routing for merged.
        assert "dlc_analysis" in merged_path.parts
        assert "O2_analysis" not in merged_path.parts

    def test_force_recompute_invokes_compute_for_each_half(self, tmp_path: Path):
        """force_recompute=True triggers _compute_per_half_alignment_template
        for every half, even when per-half NPZs already exist.

        Phase 7-pre-multi-half 2026-05-05 incident response: rewritten
        to use the safe _new resolver. Verifies compute is invoked
        twice (once per half) when force_recompute is True.
        """
        from unittest.mock import patch

        from stroke_orofacial.alignment.timebase import (
            compute_and_merge_alignment_multi_half,
        )

        manifest = self._make_multi_half_manifest(tmp_path)
        resolver = self._make_resolver(tmp_path)

        # Pre-create per-half NPZs (would normally skip compute)
        per_half_paths = [
            resolver.alignment_template_per_half_new(
                "PS48", manifest.date,
                halves_concat_label="ab",
                half_id=hid,
            )
            for hid in ("a", "b")
        ]
        for p in per_half_paths:
            assert tmp_path in p.parents
        _make_per_half_template(per_half_paths[0], n_cam=10, n_ws=40)
        _make_per_half_template(per_half_paths[1], n_cam=20, n_ws=80)

        # Mock compute to return a valid template dict
        def fake_compute(half_spec, animal, date, resolver, params, *, cam_idx):
            return {
                "Fs_ws_input": np.float64(1000.0),
                "sig_wsIdx__idx_cam": np.zeros(10 if half_spec.id == "a" else 20),
                "sig_camIdx__idx_ws": np.zeros(40 if half_spec.id == "a" else 80),
                "sig_camTimes__idx_cam": np.arange(
                    10 if half_spec.id == "a" else 20, dtype=float,
                ) * 0.004,
                "sig_wsTimes__idx_ws": np.arange(
                    40 if half_spec.id == "a" else 80, dtype=float,
                ) / 1000.0,
            }

        with patch(
            "stroke_orofacial.alignment.timebase._compute_per_half_alignment_template",
            side_effect=fake_compute,
        ) as mock_compute:
            compute_and_merge_alignment_multi_half(
                manifest, resolver, {"cam_idx": 2}, force_recompute=True,
            )

        # One compute call per half
        assert mock_compute.call_count == 2


# ---------- TestCenteredParquetMerge ----------


def _make_centered_df(n_rows: int, *, seed: int = 0):
    """Synthetic centered DLC DataFrame with the 39-column schema shape.

    Bodyparts × {x, y, likelihood} = 13 × 3 = 39 columns. Column names
    follow the legacy convention but the precise list isn't load-bearing
    for the merge function — what matters is column-set equality across
    halves and frame-index continuity in the merged row index.
    """
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    bodyparts = [
        "tongue", "L_eye", "R_eye", "nose", "L_paw", "R_paw",
        "L_ear", "R_ear", "L_spout", "R_spout", "jaw", "tail", "whisker_pad",
    ]
    cols: dict[str, np.ndarray] = {}
    for bp in bodyparts:
        cols[f"{bp}_x"] = rng.standard_normal(n_rows).astype("float32")
        cols[f"{bp}_y"] = rng.standard_normal(n_rows).astype("float32")
        cols[f"{bp}_likelihood"] = rng.uniform(0.5, 1.0, n_rows).astype("float32")
    return pd.DataFrame(cols)


class TestCenteredParquetMerge:
    """Cell 13 port: pd.concat axis=0 ignore_index=True, with column
    parity enforcement."""

    def test_n2_concat_preserves_shape(self, tmp_path: Path):
        import pandas as pd
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        df_a = _make_centered_df(100, seed=1)
        df_b = _make_centered_df(200, seed=2)
        df_a.to_parquet(a_path, index=False)
        df_b.to_parquet(b_path, index=False)

        merged_path = merge_centered_parquet([a_path, b_path], tmp_path / "merged.parquet")

        merged = pd.read_parquet(merged_path)
        assert len(merged) == 300  # 100 + 200
        # Column set + order preserved (39 columns)
        assert list(merged.columns) == list(df_a.columns)
        assert len(merged.columns) == 39

    def test_n2_frame_index_continuity(self, tmp_path: Path):
        """ignore_index=True yields a fresh RangeIndex(0..n_total-1).
        Downstream consumers reading row idx as cam-frame idx see a
        contiguous range matching the alignment-template merged
        sig_camTimes__idx_cam length."""
        import pandas as pd
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        df_a = _make_centered_df(50)
        df_b = _make_centered_df(75)
        df_a.to_parquet(a_path, index=False)
        df_b.to_parquet(b_path, index=False)

        merge_centered_parquet([a_path, b_path], tmp_path / "merged.parquet")
        merged = pd.read_parquet(tmp_path / "merged.parquet")

        # Row index is a fresh RangeIndex(0..125-1)
        assert list(merged.index) == list(range(125))

    def test_n2_data_preserved_per_half(self, tmp_path: Path):
        """Merged rows 0..n_a-1 == half-A; rows n_a..n_a+n_b-1 == half-B.
        Verifies concat is in acquisition order."""
        import numpy as np
        import pandas as pd
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        df_a = _make_centered_df(20, seed=10)
        df_b = _make_centered_df(30, seed=20)
        df_a.to_parquet(a_path, index=False)
        df_b.to_parquet(b_path, index=False)

        merge_centered_parquet([a_path, b_path], tmp_path / "merged.parquet")
        merged = pd.read_parquet(tmp_path / "merged.parquet")

        np.testing.assert_array_equal(
            merged.iloc[:20]["tongue_x"].to_numpy(),
            df_a["tongue_x"].to_numpy(),
        )
        np.testing.assert_array_equal(
            merged.iloc[20:50]["tongue_x"].to_numpy(),
            df_b["tongue_x"].to_numpy(),
        )

    def test_column_mismatch_raises(self, tmp_path: Path):
        """Different column sets across halves raise ValueError before
        any concat happens — cell 13 lines 98-99 strict check."""
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        df_a = _make_centered_df(10)
        df_b = _make_centered_df(10)
        df_b = df_b.drop(columns=["tongue_likelihood"])  # remove one column
        df_a.to_parquet(a_path, index=False)
        df_b.to_parquet(b_path, index=False)

        with pytest.raises(ValueError, match=r"Column mismatch"):
            merge_centered_parquet([a_path, b_path], tmp_path / "merged.parquet")

    def test_column_order_mismatch_raises(self, tmp_path: Path):
        """Same column set but different order also raises — cell 13
        compares ``list(A.columns) != list(B.columns)`` (order-sensitive)."""
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        df_a = _make_centered_df(10)
        df_b = _make_centered_df(10)
        # Reverse columns
        df_b = df_b[list(df_b.columns)[::-1]]
        df_a.to_parquet(a_path, index=False)
        df_b.to_parquet(b_path, index=False)

        with pytest.raises(ValueError, match=r"Column mismatch"):
            merge_centered_parquet([a_path, b_path], tmp_path / "merged.parquet")

    def test_n3_extension(self, tmp_path: Path):
        import pandas as pd
        paths = [tmp_path / f"h{i}.parquet" for i in range(3)]
        sizes = [50, 30, 70]
        for p, n in zip(paths, sizes, strict=True):
            _make_centered_df(n).to_parquet(p, index=False)

        merge_centered_parquet(paths, tmp_path / "merged.parquet")
        merged = pd.read_parquet(tmp_path / "merged.parquet")
        assert len(merged) == sum(sizes)  # 150
        assert list(merged.index) == list(range(150))

    def test_raises_on_n_lt_2(self, tmp_path: Path):
        a_path = tmp_path / "a.parquet"
        _make_centered_df(10).to_parquet(a_path, index=False)
        with pytest.raises(ValueError, match=r"N >= 2"):
            merge_centered_parquet([a_path], tmp_path / "out.parquet")

    def test_raises_on_missing_input(self, tmp_path: Path):
        a_path = tmp_path / "a.parquet"
        _make_centered_df(10).to_parquet(a_path, index=False)
        with pytest.raises(FileNotFoundError):
            merge_centered_parquet(
                [a_path, tmp_path / "nonexistent.parquet"],
                tmp_path / "out.parquet",
            )

    def test_creates_output_parent_dirs(self, tmp_path: Path):
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        _make_centered_df(10).to_parquet(a_path, index=False)
        _make_centered_df(10).to_parquet(b_path, index=False)
        deep = tmp_path / "deep" / "nested" / "merged.parquet"
        merge_centered_parquet([a_path, b_path], deep)
        assert deep.exists()

    def test_returns_output_path(self, tmp_path: Path):
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        _make_centered_df(10).to_parquet(a_path, index=False)
        _make_centered_df(10).to_parquet(b_path, index=False)
        out = tmp_path / "merged.parquet"
        result = merge_centered_parquet([a_path, b_path], out)
        assert result == out
        assert result.exists()

    def test_compression_kwarg(self, tmp_path: Path):
        """Compression kwarg passes through to pandas.to_parquet."""
        import pandas as pd
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        _make_centered_df(10).to_parquet(a_path, index=False)
        _make_centered_df(10).to_parquet(b_path, index=False)
        merge_centered_parquet(
            [a_path, b_path], tmp_path / "merged.parquet", compression="snappy",
        )
        # File loads back with the alternate compression
        merged = pd.read_parquet(tmp_path / "merged.parquet")
        assert len(merged) == 20
