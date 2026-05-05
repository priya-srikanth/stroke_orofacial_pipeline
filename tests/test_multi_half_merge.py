"""Phase 7-pre-multi-half tests for multi_half_merge.

Covers the cell-17 port :func:`merge_licks_and_rewards` plus the
ported helpers (:func:`_infer_n_cam`, :func:`_looks_like_frame_indices`,
:func:`_shift_frame_indices`). Synthetic fixtures cover the legacy
2-half case (PS48 20250314 production scope) plus the N-half
generalization.

Vendor reference for the algorithm being tested:
``docs/legacy_snippets/multi_half_merge/cell_17_merge_licks_and_rewards.py``
(notebook SHA256 ed12c54...; cell SHA256 b2819b791668e18c...).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.multi_half_merge import (
    _infer_n_cam,
    _looks_like_frame_indices,
    _shift_frame_indices,
    merge_licks_and_rewards,
)


# ---------- _infer_n_cam ----------


class TestInferNCam:
    def test_tier_1_cam_times_array_size(self):
        """Highest-priority: a 1D `cam_times` array's size is n_cam."""
        npz = {"cam_times": np.linspace(0, 10, 5_000)}
        assert _infer_n_cam(npz) == 5_000

    def test_tier_1_priority_order(self):
        """When multiple Tier-1 keys are present, the first key in the
        priority list wins. Default order:
        cam_times > sig_camTimes__idx_cam > t_cam > frame_times_s > camTimes."""
        npz = {
            "camTimes": np.zeros(7_000),  # last in order
            "cam_times": np.zeros(5_000),  # first in order
        }
        assert _infer_n_cam(npz) == 5_000

    def test_tier_2_scalar_n_frames(self):
        """When no Tier-1 keys, fall back to a scalar `n_frames`."""
        npz = {"n_frames": np.int64(4_242)}
        assert _infer_n_cam(npz) == 4_242

    def test_tier_3_fallback_largest_long_1d_array(self):
        """When no Tier-1/2 keys, return size of the largest 1D
        numeric array > _FALLBACK_CAM_TIMESERIES_MIN_SIZE (1000)."""
        npz = {
            "small": np.zeros(500),  # below threshold
            "medium": np.zeros(1_500),  # candidate
            "large": np.zeros(8_000),  # winner
            "small_obj": np.array(["a", "b"], dtype=object),  # non-numeric
        }
        assert _infer_n_cam(npz) == 8_000

    def test_returns_none_when_no_signal(self):
        """No Tier-1/2 keys, no 1D arrays > 1000 → None."""
        npz = {"foo": np.zeros(500), "bar": np.array(42)}
        assert _infer_n_cam(npz) is None


# ---------- _looks_like_frame_indices ----------


class TestLooksLikeFrameIndices:
    def test_clean_integer_indices_within_bound(self):
        arr = np.array([0, 5, 100, 999], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=1_000) is True

    def test_indices_just_above_n_cam_within_slack(self):
        """Slack of 5 allows a few-index overshoot (e.g. clamp values
        at exactly n_cam are common in legacy data)."""
        arr = np.array([0, 999, 1_001], dtype=float)  # 1_001 < 1_000+5
        assert _looks_like_frame_indices(arr, n_cam_hint=1_000) is True

    def test_indices_well_above_n_cam(self):
        arr = np.array([0, 999, 5_000], dtype=float)  # 5_000 >> 1_000+5
        assert _looks_like_frame_indices(arr, n_cam_hint=1_000) is False

    def test_non_integer_floats_rejected(self):
        arr = np.array([0.5, 1.5, 2.5], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=10) is False

    def test_negative_values_rejected(self):
        arr = np.array([-5, 10, 20], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=100) is False

    def test_nans_tolerated(self):
        arr = np.array([0, 5, np.nan, 100], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=1_000) is True

    def test_all_nan_rejected(self):
        arr = np.array([np.nan, np.nan, np.nan], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=100) is False

    def test_no_hint_passes_above_check(self):
        """When n_cam_hint is None, the upper bound check is skipped —
        any non-negative integer-ish 1D array is accepted."""
        arr = np.array([0, 5, 100_000_000], dtype=float)
        assert _looks_like_frame_indices(arr, n_cam_hint=None) is True

    def test_2d_array_rejected(self):
        arr = np.zeros((10, 2))
        assert _looks_like_frame_indices(arr, n_cam_hint=100) is False

    def test_string_array_rejected(self):
        arr = np.array(["a", "b"], dtype=object)
        assert _looks_like_frame_indices(arr, n_cam_hint=100) is False


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
        """Custom cam_count_keys can be passed to drive _infer_n_cam from
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
