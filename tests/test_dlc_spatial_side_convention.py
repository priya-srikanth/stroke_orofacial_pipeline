"""Side-convention plumbing tests for ``dlc_spatial.tone_aligned``.

Phase 6.8a: the heatmap NPZs produced by notebook 12 carry a mouse-frame
``trial_group`` label + the two convention scalars
(``wavesurfer_sides_match_mouse_sides`` / ``side_convention_version``).
This module covers the two new boundary layers:

* :func:`stroke_orofacial.dlc_spatial.tone_aligned.save_tone_aligned_npz`
  — writer that translates a result dict into the stamped NPZ payload.
* :func:`stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_analysis_by_animal_date`
  — wrapper that auto-populates the L/R flag from ``AnimalInfo`` when
  the caller doesn't pass it explicitly.

The stamp verification on *input* NPZs (pre-task-#17 rejection etc.) is
covered by ``test_reward_aligned.TestLoadRewardEventsStamp``; this file
focuses on *output* correctness + the wrapper's default behavior.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_analysis,
    build_tone_aligned_analysis_by_animal_date,
    save_tone_aligned_npz,
)
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _fake_histogram(nbins: int = 8) -> dict[str, Any]:
    """Minimal histogram dict shaped like ``pixel_bins.build_histogram``
    output — ``save_tone_aligned_npz`` cares about these four keys
    (``H_counts`` / ``H_proportion`` / ``xedges`` / ``yedges`` / ``extent``)
    plus uses the shape of ``H_counts`` to infer nbins."""
    counts = np.ones((nbins, nbins), dtype=np.int64)
    proportion = counts / counts.sum()
    xedges = np.linspace(-200.0, 200.0, nbins + 1)
    yedges = np.linspace(50.0, 550.0, nbins + 1)
    return {
        "H_counts": counts,
        "H_proportion": proportion,
        "xedges": xedges,
        "yedges": yedges,
        # pixel_bins stores extent as (x_min, x_max, y_min, y_max).
        "extent": (
            float(xedges[0]), float(xedges[-1]),
            float(yedges[0]), float(yedges[-1]),
        ),
    }


def _fake_result(
    *,
    wavesurfer_matches: bool = False,
    trial_group: str = "L",
    window_ms: tuple[float, float] = (-500.0, 5000.0),
    bodypart: str = "tongue",
    center_mode: str = "nose",
    histogram: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal result dict shaped like
    :func:`build_tone_aligned_analysis` output — exactly the fields
    :func:`save_tone_aligned_npz` reads."""
    hist = _fake_histogram() if histogram is None else histogram
    return {
        "histogram": hist,
        "window": None,  # save_tone_aligned_npz ignores this
        "n_rewards": 42,
        "n_selected_frames": 1337,
        "trial_group": trial_group,
        "window_ms": window_ms,
        "bodypart": bodypart,
        "center_mode": center_mode,
        "wavesurfer_sides_match_mouse_sides": wavesurfer_matches,
    }


# ---------------------------------------------------------------------------
# save_tone_aligned_npz — NPZ writer
# ---------------------------------------------------------------------------


class TestSaveToneAlignedNpz:
    """Schema, stamp correctness, and error paths for the Phase 6.8a
    heatmap NPZ writer."""

    def test_roundtrip_schema(self, tmp_path):
        """Every documented NPZ key is present after save → load and
        matches what the result dict held."""
        result = _fake_result(
            wavesurfer_matches=False,
            trial_group="L",
            window_ms=(-500.0, 5000.0),
            bodypart="tongue",
            center_mode="nose",
        )
        path = tmp_path / "heatmap.npz"
        save_tone_aligned_npz(result, path)

        data = np.load(path, allow_pickle=True)
        hist = result["histogram"]

        np.testing.assert_array_equal(data["H_counts"], hist["H_counts"])
        np.testing.assert_array_equal(
            data["H_proportion"], hist["H_proportion"],
        )
        np.testing.assert_array_equal(data["xedges"], hist["xedges"])
        np.testing.assert_array_equal(data["yedges"], hist["yedges"])
        np.testing.assert_array_equal(
            data["x_limits"],
            np.asarray([hist["extent"][0], hist["extent"][1]]),
        )
        np.testing.assert_array_equal(
            data["y_limits"],
            np.asarray([hist["extent"][2], hist["extent"][3]]),
        )
        assert int(data["nbins"]) == hist["H_counts"].shape[0]
        assert str(data["trial_group"]) == "L"
        np.testing.assert_array_equal(
            data["window_ms"], np.asarray([-500.0, 5000.0]),
        )
        assert int(data["n_rewards"]) == 42
        assert int(data["n_selected_frames"]) == 1337
        assert str(data["bodypart"]) == "tongue"
        assert str(data["center_mode"]) == "nose"
        assert bool(data[SIDE_CONVENTION_MATCH_KEY]) is False
        assert int(data[SIDE_CONVENTION_VERSION_KEY]) == SIDE_CONVENTION_VERSION

    @pytest.mark.parametrize("matches", [True, False])
    def test_stamp_matches_result_flag(self, tmp_path, matches):
        """The NPZ's ``wavesurfer_sides_match_mouse_sides`` scalar equals
        the value the result dict held — flag flip at the result level
        must propagate to disk."""
        result = _fake_result(wavesurfer_matches=matches)
        path = tmp_path / f"heatmap_{matches}.npz"
        save_tone_aligned_npz(result, path)

        data = np.load(path, allow_pickle=True)
        assert bool(data[SIDE_CONVENTION_MATCH_KEY]) is matches

    def test_flag_swap_breaks_equality(self, tmp_path):
        """Within-PR symmetry check: writing the same histogram under
        matches=True vs matches=False produces byte-different NPZs (the
        scalar lives in the NPZ, so this catches a writer that forgot
        to stamp). The array data is identical — the difference is only
        in the stamp scalar, which is sufficient for
        drift-diagnostic purposes."""
        hist = _fake_histogram()
        res_true = _fake_result(wavesurfer_matches=True, histogram=hist)
        res_false = _fake_result(wavesurfer_matches=False, histogram=hist)
        p_true = tmp_path / "true.npz"
        p_false = tmp_path / "false.npz"
        save_tone_aligned_npz(res_true, p_true)
        save_tone_aligned_npz(res_false, p_false)

        d_true = np.load(p_true, allow_pickle=True)
        d_false = np.load(p_false, allow_pickle=True)
        # arrays agree
        np.testing.assert_array_equal(d_true["H_counts"], d_false["H_counts"])
        # scalar disagrees
        assert bool(d_true[SIDE_CONVENTION_MATCH_KEY]) is True
        assert bool(d_false[SIDE_CONVENTION_MATCH_KEY]) is False

    def test_raises_on_none_histogram(self, tmp_path):
        """Empty/missing histogram shouldn't be silently skipped by the
        writer — the loop in notebook 12 checks for None *before* calling
        save_tone_aligned_npz, so reaching this function with None is
        a caller bug."""
        result = _fake_result()
        result["histogram"] = None
        path = tmp_path / "bad.npz"
        with pytest.raises(ValueError, match="histogram"):
            save_tone_aligned_npz(result, path)

    def test_raises_on_non_bool_flag(self, tmp_path):
        """stamp_side_convention validates the flag is bool; a non-bool
        coming through from a misconfigured caller must error at write
        rather than silently get coerced into a numpy scalar of the
        wrong dtype."""
        result = _fake_result()
        result["wavesurfer_sides_match_mouse_sides"] = 1  # int, not bool
        path = tmp_path / "nonbool.npz"
        with pytest.raises(
            (TypeError, ValueError),
            match="(?i)(bool|wavesurfer_sides_match_mouse_sides)",
        ):
            save_tone_aligned_npz(result, path)

    def test_creates_parent_directories(self, tmp_path):
        """Writer creates missing parent dirs so callers can save deep
        into the output tree without a pre-mkdir step."""
        nested = tmp_path / "a" / "b" / "c" / "heatmap.npz"
        assert not nested.parent.exists()
        save_tone_aligned_npz(_fake_result(), nested)
        assert nested.exists()

    def test_string_path_accepted(self, tmp_path):
        """Both Path and str work, matching save_heatmap_npz's signature."""
        p = tmp_path / "via_str.npz"
        save_tone_aligned_npz(_fake_result(), str(p))
        assert p.exists()


# ---------------------------------------------------------------------------
# build_tone_aligned_analysis — flag plumbing
# ---------------------------------------------------------------------------


class TestBuildToneAlignedAnalysisFlagPlumbing:
    """The primary entry point must forward the caller's flag through
    load_tone_events AND echo it on the return dict. We mock the heavy
    dependencies (parquet read, histogram build, alignment) and assert
    just the flag propagation."""

    def _stub_licks_npz(
        self,
        tmp_path: Path,
        animal: str,
        date_str: str,
        *,
        wavesurfer_matches: bool,
    ) -> Path:
        """Write a stamped Phase 2-shaped NPZ at the location the
        resolver will be mocked to return. Shared setup for the two
        tests below."""
        from stroke_orofacial.lr_convention import stamp_side_convention

        licks_dir = tmp_path / "spout_behavior" / "licks_and_rewards" / animal
        licks_dir.mkdir(parents=True)
        path = licks_dir / f"{date_str}.npz"
        payload: dict = {
            "Tone_L": np.array([100, 200, 300], dtype=int),
            "Tone_R": np.array([150, 250, 350], dtype=int),
        }
        stamp_side_convention(payload, wavesurfer_matches)
        np.savez(path, **payload)
        return path

    @pytest.mark.parametrize("matches", [True, False])
    def test_return_dict_echoes_caller_flag(self, tmp_path, matches):
        """When the caller supplies wavesurfer_sides_match_mouse_sides,
        the returned dict carries it back (so notebook 12 can stamp the
        Phase 6 NPZ without re-looking up AnimalInfo)."""
        from stroke_orofacial.manifest import SessionManifest

        animal = "PS99"
        date = datetime.date(2026, 1, 1)
        date_str = date.strftime("%Y%m%d")
        self._stub_licks_npz(
            tmp_path, animal, date_str, wavesurfer_matches=matches,
        )

        manifest = SessionManifest(
            session_id=f"{animal}_{date_str}",
            animal=animal,
            date=date,
            day_relative_to_stroke=-1,
            phase="baseline",
            dlc_h5_files=[tmp_path / "fake.h5"],  # non-empty so no FileNotFoundError
            dlc_csv_files=[],
        )
        resolver = MagicMock()
        resolver.pipeline_outputs.return_value = tmp_path

        # Short-circuit the centered-parquet read to a minimal DF, and
        # the histogram build to a minimal dict. The flag propagation
        # happens at load_tone_events → build_tone_aligned_analysis
        # return dict — the histogram values are irrelevant here.
        import pandas as pd

        fake_df = pd.DataFrame({"dummy": range(10)})
        with patch(
            "stroke_orofacial.dlc_io.parquet.read_centered_parquet",
            return_value=fake_df,
        ), patch(
            "pathlib.Path.exists", return_value=True,
        ), patch(
            "numpy.load",
        ) as mock_load, patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_window",
            return_value=MagicMock(n_events=3, n_selected=42),
        ), patch(
            "stroke_orofacial.dlc_spatial.pixel_bins.build_histogram",
            return_value=_fake_histogram(),
        ):
            # numpy.load is called twice: once by load_tone_events for
            # the licks NPZ, once by build_tone_aligned_analysis for the
            # alignment template. Side-effect dispatches by call order.
            stamped_licks = {
                "Tone_L": np.array([100, 200, 300], dtype=int),
                "Tone_R": np.array([150, 250, 350], dtype=int),
                SIDE_CONVENTION_VERSION_KEY: np.int32(SIDE_CONVENTION_VERSION),
                SIDE_CONVENTION_MATCH_KEY: np.bool_(matches),
            }
            fake_align = {"sig_camIdx__idx_ws": np.arange(100, dtype=float)}

            class _FakeNpz:
                def __init__(self, d):
                    self._d = d
                    self.files = list(d.keys())
                def __getitem__(self, k):
                    return self._d[k]
                def get(self, k, default=None):
                    return self._d.get(k, default)

            mock_load.side_effect = [
                _FakeNpz(stamped_licks),   # 1st: load_tone_events (single load — stamp check + Tone_L/R share the same NpzFile)
                _FakeNpz(fake_align),      # 2nd: alignment template
            ]

            result = build_tone_aligned_analysis(
                manifest, "tongue", "nose", "all",
                (-500.0, 5000.0), resolver,
                spatial_config={}, tone_config={},
                wavesurfer_sides_match_mouse_sides=matches,
            )

        assert result is not None
        assert result["wavesurfer_sides_match_mouse_sides"] is matches


class TestBuildToneAlignedAnalysisByAnimalDate:
    """The wrapper auto-populates the L/R flag from AnimalInfo when the
    caller passes None, and lets an explicit kwarg override when
    provided (used by tests that exercise the stamp-mismatch path)."""

    def _mock_animal_info(self, *, wavesurfer_matches: bool):
        info = MagicMock()
        info.wavesurfer_sides_match_mouse_sides = wavesurfer_matches
        info.session_start = datetime.date(2026, 1, 1)
        info.session_end = datetime.date(2026, 1, 31)
        info.stroke_date = datetime.date(2026, 1, 15)
        info.exclusions = []
        return info

    @pytest.mark.parametrize("yaml_flag", [True, False])
    def test_auto_populates_from_animal_info(self, yaml_flag):
        """Wrapper reads the flag from AnimalInfo when kwarg is None."""
        info = self._mock_animal_info(wavesurfer_matches=yaml_flag)
        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return None  # short-circuit; we only check the kwarg forwarding

        with patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.get_animal",
            return_value=info,
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_manifest",
            return_value=MagicMock(),
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_analysis",
            side_effect=_capture,
        ):
            build_tone_aligned_analysis_by_animal_date(
                "PS99", "20260115", "tongue", "nose", "all",
                (-500.0, 5000.0), MagicMock(),
                spatial_config={}, tone_config={},
            )

        assert captured["wavesurfer_sides_match_mouse_sides"] is yaml_flag

    def test_explicit_kwarg_wins_over_animal_info(self):
        """Explicit kwarg must override AnimalInfo. Used by tests that
        deliberately pass a mismatched value to exercise the stamp
        verification path inside load_tone_events."""
        info = self._mock_animal_info(wavesurfer_matches=False)
        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return None

        with patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.get_animal",
            return_value=info,
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_manifest",
            return_value=MagicMock(),
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_analysis",
            side_effect=_capture,
        ):
            build_tone_aligned_analysis_by_animal_date(
                "PS99", "20260115", "tongue", "nose", "all",
                (-500.0, 5000.0), MagicMock(),
                spatial_config={}, tone_config={},
                wavesurfer_sides_match_mouse_sides=True,
            )

        assert captured["wavesurfer_sides_match_mouse_sides"] is True
