"""Tests for :mod:`stroke_orofacial.lr_convention` (task #17 commit 2/5).

Covers :func:`to_mouse_frame` (side string translation) and
:func:`stamp_side_convention` (payload-dict metadata stamping),
including input validation paths that protect downstream emitters
from silent bugs.
"""
from __future__ import annotations

import pytest

from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
    stamp_side_convention,
    to_mouse_frame,
)


class TestToMouseFrame:
    def test_match_returns_input_unchanged(self):
        assert to_mouse_frame("L", wavesurfer_matches=True) == "L"
        assert to_mouse_frame("R", wavesurfer_matches=True) == "R"

    def test_mismatch_flips_L_to_R(self):
        assert to_mouse_frame("L", wavesurfer_matches=False) == "R"

    def test_mismatch_flips_R_to_L(self):
        assert to_mouse_frame("R", wavesurfer_matches=False) == "L"

    @pytest.mark.parametrize(
        "bad_side",
        ["", "l", "r", "left", "right", "LR", "B", " L", "L ", "lr"],
    )
    def test_rejects_non_canonical_side_strings(self, bad_side):
        """Only exact 'L' / 'R' allowed — permissive inputs would mask
        emitter bugs where the caller forgot to pass the canonical form."""
        with pytest.raises(ValueError, match="must be exactly"):
            to_mouse_frame(bad_side, wavesurfer_matches=True)

    def test_rejects_none_and_non_string(self):
        with pytest.raises(ValueError, match="must be exactly"):
            to_mouse_frame(None, wavesurfer_matches=True)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="must be exactly"):
            to_mouse_frame(0, wavesurfer_matches=False)  # type: ignore[arg-type]


class TestStampSideConvention:
    def test_adds_both_scalars(self):
        payload = {"Lick_L": [1, 2], "Lick_R": [3, 4]}
        out = stamp_side_convention(payload, wavesurfer_matches=False)
        assert out[SIDE_CONVENTION_MATCH_KEY] is False
        assert out[SIDE_CONVENTION_VERSION_KEY] == SIDE_CONVENTION_VERSION

    def test_returns_same_dict_object(self):
        """Mutates-and-returns semantics — the writer does
        `payload = stamp_side_convention(payload, ...)` and expects
        the same dict back so it can pass it straight to np.savez/json.dump."""
        payload = {"data": "x"}
        out = stamp_side_convention(payload, wavesurfer_matches=True)
        assert out is payload

    def test_preserves_existing_keys(self):
        payload = {"Lick_L": [1], "Lick_R": [2], "Fs": 1000}
        out = stamp_side_convention(payload, wavesurfer_matches=True)
        assert out["Lick_L"] == [1]
        assert out["Lick_R"] == [2]
        assert out["Fs"] == 1000

    def test_default_version_is_current(self):
        payload: dict = {}
        out = stamp_side_convention(payload, wavesurfer_matches=False)
        assert out[SIDE_CONVENTION_VERSION_KEY] == SIDE_CONVENTION_VERSION

    def test_explicit_version_override(self):
        """Allows a caller to stamp a different version — used only in
        migration / re-emit contexts."""
        payload: dict = {}
        out = stamp_side_convention(payload, wavesurfer_matches=False, version=2)
        assert out[SIDE_CONVENTION_VERSION_KEY] == 2

    def test_true_flag_stamped_as_true(self):
        out = stamp_side_convention({}, wavesurfer_matches=True)
        assert out[SIDE_CONVENTION_MATCH_KEY] is True

    @pytest.mark.parametrize(
        "bad_flag", [0, 1, "false", "true", None, "no", "yes"],
    )
    def test_rejects_non_bool_match_flag(self, bad_flag):
        """Non-bool inputs (including int 0/1, which would otherwise be
        truthy-compatible) must fail fast to prevent silent corruption
        of artifact metadata."""
        with pytest.raises(TypeError, match="wavesurfer_matches must be bool"):
            stamp_side_convention({}, wavesurfer_matches=bad_flag)  # type: ignore[arg-type]

    def test_rejects_non_int_version(self):
        with pytest.raises(TypeError, match="version must be int"):
            stamp_side_convention({}, wavesurfer_matches=True, version=1.5)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="version must be int"):
            stamp_side_convention({}, wavesurfer_matches=True, version="1")  # type: ignore[arg-type]

    def test_rejects_bool_as_version(self):
        """bool is a subclass of int in Python; accepting True as version=1
        would be surprising behavior, so reject explicitly."""
        with pytest.raises(TypeError, match="version must be int"):
            stamp_side_convention({}, wavesurfer_matches=True, version=True)  # type: ignore[arg-type]

    def test_rejects_collision_on_match_key(self):
        """Overwriting a pre-existing convention scalar is almost
        certainly a bug — fail loud instead of silently clobbering."""
        payload = {SIDE_CONVENTION_MATCH_KEY: True}
        with pytest.raises(ValueError, match="refusing to overwrite"):
            stamp_side_convention(payload, wavesurfer_matches=False)

    def test_rejects_collision_on_version_key(self):
        payload = {SIDE_CONVENTION_VERSION_KEY: 99}
        with pytest.raises(ValueError, match="refusing to overwrite"):
            stamp_side_convention(payload, wavesurfer_matches=False)
