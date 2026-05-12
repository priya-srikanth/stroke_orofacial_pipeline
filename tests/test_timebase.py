"""Tests for stroke_orofacial.alignment.timebase."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.alignment.timebase import (
    AlignmentResult,
    frame_to_session_time,
    session_time_to_frame,
    ws_sample_to_session_time,
)


class TestWsSampleToSessionTime:
    def test_basic(self):
        result = ws_sample_to_session_time(1000, Fs=1000.0)
        assert result == 1.0

    def test_array(self):
        result = ws_sample_to_session_time(np.array([0, 500, 1000]), Fs=1000.0)
        np.testing.assert_allclose(result, [0.0, 0.5, 1.0])

    def test_zero(self):
        result = ws_sample_to_session_time(0, Fs=1000.0)
        assert result == 0.0


class TestFrameToSessionTime:
    @pytest.fixture()
    def alignment(self):
        # Simple linear mapping: ws_idx = 4 * cam_frame + 100
        n_cam = 100
        sig_wsIdx = np.arange(n_cam, dtype=np.float64) * 4.0 + 100.0
        return AlignmentResult(
            sig_camIdx__idx_ws=np.zeros(1000),  # not used by this test
            sig_wsIdx__idx_cam=sig_wsIdx,
            slope_ws_per_camFrame=4.0,
            intercept_ws_samples=100.0,
            Fs_ws=1000.0,
            source="test",
        )

    def test_frame_0(self, alignment):
        result = frame_to_session_time(np.array([0]), alignment)
        # ws_idx[0] = 100, session_time = 100/1000 = 0.1
        np.testing.assert_allclose(result, [0.1])

    def test_frame_50(self, alignment):
        result = frame_to_session_time(np.array([50]), alignment)
        # ws_idx[50] = 4*50+100 = 300, session_time = 0.3
        np.testing.assert_allclose(result, [0.3])

    def test_out_of_range_nan(self, alignment):
        result = frame_to_session_time(np.array([-1, 200]), alignment)
        assert np.all(np.isnan(result))


class TestSessionTimeToFrame:
    @pytest.fixture()
    def alignment(self):
        # Simple linear: cam_idx = (ws_sample - 100) / 4
        n_ws = 1000
        sig_camIdx = (np.arange(n_ws, dtype=np.float64) - 100.0) / 4.0
        return AlignmentResult(
            sig_camIdx__idx_ws=sig_camIdx,
            sig_wsIdx__idx_cam=np.zeros(100),
            slope_ws_per_camFrame=4.0,
            intercept_ws_samples=100.0,
            Fs_ws=1000.0,
            source="test",
        )

    def test_basic(self, alignment):
        # session_time=0.3 -> ws_sample=300 -> cam_idx=(300-100)/4=50
        result = session_time_to_frame(np.array([0.3]), alignment)
        np.testing.assert_allclose(result, [50.0])

    def test_out_of_range_nan(self, alignment):
        result = session_time_to_frame(np.array([10.0]), alignment)  # ws_sample=10000 > n_ws
        assert np.all(np.isnan(result))


# ---- Integration: load existing alignment template ----

_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")
_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)


@pytest.mark.skipif(
    not _MOUNT.exists() or not (_WS_LOCAL / "20250307" / "PS46").exists(),
    reason="MICROSCOPE mount or wavesurfer data not available",
)
class TestIntegrationAlignment:
    """Integration tests via the by_animal_date wrapper.

    The wrapper builds a SessionManifest internally; the manifest-first
    primary signature is exercised in
    ``TestIntegrationAlignmentWithManifest`` below.
    """

    def test_load_existing_template(self, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.alignment.timebase import (
            load_or_compute_alignment_by_animal_date,
        )
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        params = load_defaults()["alignment"]
        # Phase 7-pre-secondary-spout: wrapper now returns
        # dict[str | None, AlignmentResult]. PS46/2025-03-07 is a
        # vanilla single-half session → single-entry {None: ...}.
        result_per_suffix = load_or_compute_alignment_by_animal_date(
            "PS46", datetime.date(2025, 3, 7), resolver, params
        )
        assert set(result_per_suffix.keys()) == {None}
        result = result_per_suffix[None]
        assert result.source == "loaded"
        assert result.sig_camIdx__idx_ws.shape[0] > 0
        assert result.sig_wsIdx__idx_cam.shape[0] > 0
        assert np.isclose(result.slope_ws_per_camFrame, 4.0, rtol=0.01)

    def test_recompute_matches_existing(self, monkeypatch):
        """Recomputed template matches the existing one (parity)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.alignment.templates import load_alignment_template
        from stroke_orofacial.alignment.timebase import (
            load_or_compute_alignment_by_animal_date,
        )
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        params = load_defaults()["alignment"]
        date = datetime.date(2025, 3, 7)

        # Load existing
        ref_path = resolver.alignment_template_legacy_read("PS46", date, cam="cam2")
        ref = load_alignment_template(ref_path)

        # Recompute via wrapper. Phase 7-pre-secondary-spout: new
        # return shape is dict[str | None, AlignmentResult]; PS46 is
        # vanilla single-half so the dict has one None entry.
        result_per_suffix = load_or_compute_alignment_by_animal_date(
            "PS46", date, resolver, params, force_recompute=True
        )
        assert set(result_per_suffix.keys()) == {None}
        result = result_per_suffix[None]
        assert result.source == "computed"

        # Compare (tolerances per amendment 1 + Phase 13 env-migration note).
        # rtol bumped 1e-10 -> 1e-8 when the pipeline moved from frsb
        # (numpy 1.24, scipy 1.15) to stroke_orofacial (numpy 2.4, scipy 1.17):
        # a different LAPACK backend produces ~5-ULP drift in np.polyfit's
        # coefficients, which propagates through scipy.interpolate.interp1d
        # to ~1e-10 rel diff on the sample-index mapping. 1e-8 remains tight
        # enough to catch any real algorithmic regression while accommodating
        # the legitimate numeric floor of the chain.
        both_finite = np.isfinite(ref["sig_camIdx__idx_ws"]) & np.isfinite(
            result.sig_camIdx__idx_ws
        )
        np.testing.assert_allclose(
            result.sig_camIdx__idx_ws[both_finite],
            ref["sig_camIdx__idx_ws"][both_finite],
            rtol=1e-8,
        )
        np.testing.assert_allclose(
            result.slope_ws_per_camFrame,
            float(ref["slope_ws_per_camFrame"]),
            rtol=1e-8,
        )


@pytest.mark.skipif(
    not _MOUNT.exists() or not (_WS_LOCAL / "20250307" / "PS46").exists(),
    reason="MICROSCOPE mount or wavesurfer data not available",
)
class TestIntegrationAlignmentWithManifest:
    """Exercise the manifest-first primary signature on real data."""

    def test_load_with_manifest_uses_manifest_alignment_template(self, monkeypatch):
        """Build manifest explicitly, pass to load_or_compute_alignment(manifest, ...).

        The manifest's pre-resolved alignment_template path should be used
        verbatim for the existing-template load path."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.alignment.timebase import load_or_compute_alignment
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        params = load_defaults()["alignment"]
        date = datetime.date(2025, 3, 7)
        animal_info = get_animal("PS46")
        manifest = build_manifest("PS46", date, resolver, animal_info)
        assert manifest.alignment_template is not None, (
            "build_manifest did not locate the cam2 alignment template"
        )

        result = load_or_compute_alignment(manifest, resolver, params)
        assert result.source == "loaded"
        assert result.sig_camIdx__idx_ws.shape[0] > 0

    def test_recompute_with_manifest_uses_manifest_inputs(self, monkeypatch):
        """force_recompute path consumes manifest.wavesurfer_file +
        manifest.video_files[0].parent (for cam2 CSV discovery)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.alignment.timebase import load_or_compute_alignment
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        params = load_defaults()["alignment"]
        date = datetime.date(2025, 3, 7)
        animal_info = get_animal("PS46")
        manifest = build_manifest("PS46", date, resolver, animal_info)
        assert manifest.wavesurfer_file is not None
        assert len(manifest.video_files) > 0, (
            "build_manifest did not locate cam2 video files"
        )

        result = load_or_compute_alignment(
            manifest, resolver, params, force_recompute=True
        )
        assert result.source == "computed"
        assert result.sig_camIdx__idx_ws.shape[0] > 0


class TestLoadOrComputeAlignmentRaisesOnMissingWavesurfer:
    """Pure-unit guard: recompute path must raise when manifest lacks
    wavesurfer (and ws_signals not provided), regardless of mount state."""

    def test_raises_when_recompute_needed_but_wavesurfer_missing(self, tmp_path):
        from unittest.mock import MagicMock

        from stroke_orofacial.alignment.timebase import load_or_compute_alignment
        from stroke_orofacial.manifest import SessionManifest
        from stroke_orofacial.paths import PathResolver

        # Force-recompute on a manifest with no wavesurfer + no template path.
        resolver = MagicMock(spec=PathResolver)
        # Resolver-fallback path doesn't exist either (forces recompute branch).
        resolver.alignment_template_legacy_read.return_value = tmp_path / "nope.npz"

        manifest = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
            wavesurfer_file=None,  # the missing input
            alignment_template=None,
        )
        with pytest.raises(FileNotFoundError, match="wavesurfer"):
            load_or_compute_alignment(
                manifest, resolver, params={"cam_idx": 2}, force_recompute=True
            )


# ---- Phase 7-pre-multi-half Step 1: dispatch wiring ----


class TestLoadOrComputeAlignmentMultiHalfDispatch:
    """Step 1 wiring: when manifest.halves is not None,
    load_or_compute_alignment dispatches into
    compute_and_merge_alignment_multi_half and returns an
    AlignmentResult loaded from the merged NPZ.

    This is the single-entry-point integration test the Phase 7-pre-
    multi-half kickoff Step 1 specified — verifies that downstream
    callers don't need to know whether the session is single-half or
    multi-half; they just call load_or_compute_alignment(manifest, ...)
    and get an AlignmentResult.
    """

    def _make_per_half_template(
        self, path: Path, *, Fs_ws=1000.0, n_cam=10, n_ws=40,
    ) -> Path:
        """Synthetic per-half alignment template NPZ matching cell-16 schema.

        Mirrors the helper in tests/test_multi_half_merge.py but local
        to keep this test self-contained.
        """
        dt_ws = 1.0 / Fs_ws
        dt_cam = (n_ws / Fs_ws) / n_cam
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            str(path),
            Fs_ws_input=np.float64(Fs_ws),
            sig_wsIdx__idx_cam=np.linspace(0.0, n_ws - 1, n_cam),
            sig_camIdx__idx_ws=np.linspace(0.0, n_cam - 1, n_ws),
            sig_camTimes__idx_cam=np.arange(n_cam) * dt_cam,
            sig_wsTimes__idx_ws=np.arange(n_ws) * dt_ws,
            allow_pickle=False,
        )
        return path

    def test_multi_half_dispatch_returns_merged_alignment_result(self, tmp_path):
        """Synthetic 2-half manifest. Pre-create per-half templates
        under the _new resolver path so compute is skipped and merge
        runs deterministically. Then call load_or_compute_alignment
        AND compute_and_merge_alignment_multi_half directly; verify
        the AlignmentResult fields match the contents of the merged
        NPZ that the orchestrator writes.
        """
        from stroke_orofacial.alignment.templates import load_alignment_template
        from stroke_orofacial.alignment.timebase import (
            compute_and_merge_alignment_multi_half,
            load_or_compute_alignment,
        )
        from stroke_orofacial.manifest import HalfSpec, SessionManifest
        from stroke_orofacial.paths import PathResolver

        # Synthetic per-half WS files (paths only — orchestrator skips
        # compute when per-half templates already exist).
        ws_a = tmp_path / "ws" / "20250314a" / "PS48" / "stroke_0001.h5"
        ws_b = tmp_path / "ws" / "20250314b" / "PS48" / "stroke_0002.h5"
        for p in (ws_a, ws_b):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()

        manifest = SessionManifest(
            session_id="PS48_20250314",
            animal="PS48",
            date=datetime.date(2025, 3, 14),
            day_relative_to_stroke=-5,
            phase="baseline",
            halves=[
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
            ],
        )

        resolver = PathResolver(output_root=tmp_path / "outputs")

        # Pre-create per-half templates at the _new paths so the
        # orchestrator's compute branch is skipped (deterministic).
        per_half_paths = [
            resolver.alignment_template_per_half_new(
                "PS48", manifest.date,
                halves_concat_label="ab", half_id=hid,
            )
            for hid in ("a", "b")
        ]
        # Belt: per-half paths must land under tmp_path (the post-Commit-4
        # invariant; would have caught the 2026-05-05 incident).
        for p in per_half_paths:
            assert tmp_path in p.parents
        self._make_per_half_template(per_half_paths[0], n_cam=10, n_ws=40)
        self._make_per_half_template(per_half_paths[1], n_cam=20, n_ws=80)

        # Call load_or_compute_alignment — should dispatch into the
        # multi-half orchestrator without us asking explicitly.
        result_via_dispatch = load_or_compute_alignment(
            manifest, resolver, params={"cam_idx": 2},
        )

        # Call the orchestrator directly, load the merged NPZ via the
        # underlying loader, and compare against result_via_dispatch.
        merged_path = compute_and_merge_alignment_multi_half(
            manifest, resolver, params={"cam_idx": 2},
        )
        merged_dict = load_alignment_template(merged_path)

        # Field-by-field equivalence
        np.testing.assert_array_equal(
            result_via_dispatch.sig_camIdx__idx_ws,
            merged_dict["sig_camIdx__idx_ws"],
        )
        np.testing.assert_array_equal(
            result_via_dispatch.sig_wsIdx__idx_cam,
            merged_dict["sig_wsIdx__idx_cam"],
        )
        assert result_via_dispatch.Fs_ws == float(merged_dict["Fs_ws_input"])

        # slope/intercept conventions for multi-half (NaN — see
        # load_or_compute_alignment docstring).
        assert np.isnan(result_via_dispatch.slope_ws_per_camFrame)
        assert np.isnan(result_via_dispatch.intercept_ws_samples)

        # source field is the new "merged_multi_half" tag — distinct
        # from "loaded" / "computed" so callers can introspect.
        assert result_via_dispatch.source == "merged_multi_half"

        # Sanity: the merged file IS under pipeline_outputs/ (i.e.
        # tmp_path-rooted), confirming the dispatch routes through the
        # _new resolver and not _legacy_read.
        assert tmp_path in merged_path.parents
        assert "alignment_templates" in merged_path.parts
        assert "O2_analysis" not in merged_path.parts

    def test_single_half_manifest_does_not_dispatch_to_multi_half(
        self, tmp_path,
    ):
        """Regression guard: a single-half manifest (halves=None) goes
        through the existing _legacy_read flow, NOT the new dispatch.
        Confirmed by patching compute_and_merge_alignment_multi_half
        and asserting it was never called."""
        from unittest.mock import MagicMock, patch

        from stroke_orofacial.alignment.timebase import load_or_compute_alignment
        from stroke_orofacial.manifest import SessionManifest
        from stroke_orofacial.paths import PathResolver

        # Mock resolver — _legacy_read returns a non-existent path so
        # the flow falls into the recompute branch, where we expect a
        # FileNotFoundError (no wavesurfer_file). The point is to prove
        # the multi-half orchestrator was NOT invoked.
        resolver = MagicMock(spec=PathResolver)
        resolver.alignment_template_legacy_read.return_value = tmp_path / "nope.npz"

        manifest = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
            wavesurfer_file=None,
            alignment_template=None,
            halves=None,  # single-half
        )

        with patch(
            "stroke_orofacial.alignment.timebase.compute_and_merge_alignment_multi_half"
        ) as mock_orchestrator:
            with pytest.raises(FileNotFoundError, match="wavesurfer"):
                load_or_compute_alignment(
                    manifest, resolver, params={"cam_idx": 2},
                    force_recompute=True,
                )
        mock_orchestrator.assert_not_called()
