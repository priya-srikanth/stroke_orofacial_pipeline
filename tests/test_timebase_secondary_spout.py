"""Phase 7-pre-secondary-spout Task 5 — Phase 3 alignment driver per-suffix wiring.

Covers ``load_or_compute_alignment_by_animal_date`` after it was rewired
to iterate :func:`stroke_orofacial.manifest.iter_session_suffixes`.
Pattern B sessions compute alignment templates for BOTH halves as
independent single-half templates (no merge — separate templates per
suffix, distinguished by suffix-aware on-disk filenames).

Also pins the Task 5.3 audit-finding fixes:
  - ``load_or_compute_alignment`` cache-discovery (resolver call inside
    the function) threads ``manifest.session_suffix``.
  - ``build_manifest``'s alignment-template discovery threads
    ``session_suffix``.

Fixture strategy mirrors ``tests/test_session_processing_secondary_spout.py``:
synthetic ``paths.yaml`` per-test redirecting all relevant logical
roots at ``tmp_path`` subdirs; touch synthetic WS+CSV files at expected
layouts; mock the actual alignment-compute boundary
(``load_or_compute_alignment`` or deeper) so tests don't require real
DLC-aligned WS data.
"""

from __future__ import annotations

import datetime
import platform as _platform_module
import textwrap
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from stroke_orofacial.alignment.timebase import (
    AlignmentResult,
    load_or_compute_alignment_by_animal_date,
)
from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver


_HOST_KEY = "windows" if _platform_module.system() == "Windows" else "mac"


# ---------- Helpers ----------


def _write_paths_yaml_full(
    tmp_path: Path,
    ws_root: Path,
    cam_root: Path,
    pipeline_outputs_root: Path,
    microscope_server_root: Path,
) -> Path:
    """Write a synthetic paths.yaml exposing all 4 logical roots Phase 3
    can touch: microscope_pipeline_outputs (new-pipeline writes),
    microscope_server (legacy alignment-template cache reads),
    wavesurfer_raw, camera_raw."""
    cfg = tmp_path / "paths.yaml"
    cfg.write_text(
        textwrap.dedent(f"""\
            logical_roots:
              microscope_pipeline_outputs:
                description: "outputs"
                mounts:
                  {_HOST_KEY}:
                    - "{pipeline_outputs_root.as_posix()}"
              microscope_server:
                description: "legacy server"
                mounts:
                  {_HOST_KEY}:
                    - "{microscope_server_root.as_posix()}"
              wavesurfer_raw:
                description: "raw ws"
                mounts:
                  {_HOST_KEY}:
                    - "{ws_root.as_posix()}"
              camera_raw:
                description: "raw camera"
                mounts:
                  {_HOST_KEY}:
                    - "{cam_root.as_posix()}"
        """)
    )
    return cfg


def _touch_ws_file(
    ws_root: Path, subdir: str, animal: str, filename: str = "stroke_0001.h5",
) -> Path:
    p = ws_root / subdir / animal / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_animal_info(animal: str = "PS99") -> AnimalInfo:
    return AnimalInfo(
        animal_id=animal,
        stroke_date=datetime.date(2025, 1, 15),
        session_start=datetime.date(2025, 1, 1),
        session_end=datetime.date(2025, 12, 31),
    )


def _ps48_animal_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS48",
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
    )


def _make_fake_alignment_result(source: str = "computed") -> AlignmentResult:
    """A simple AlignmentResult for mocking purposes."""
    return AlignmentResult(
        sig_camIdx__idx_ws=np.array([1, 2, 3], dtype=np.int64),
        sig_wsIdx__idx_cam=np.array([10, 20, 30], dtype=np.int64),
        slope_ws_per_camFrame=4.0,
        intercept_ws_samples=0.0,
        Fs_ws=20000.0,
        source=source,
    )


@pytest.fixture()
def alignment_params() -> dict:
    return {"cam_idx": 2}


@pytest.fixture()
def pattern_b_layout(tmp_path: Path, monkeypatch):
    """Pattern B fixture with both halves' synthetic WS files on disk.

    Returns a dict with the resolver, the synthetic overrides config,
    animal info, and the relevant root paths.
    """
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    ws_root = tmp_path / "wavesurfer"
    ws_root.mkdir()
    cam_root = tmp_path / "camera"
    cam_root.mkdir()
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()
    microscope_server_root = tmp_path / "microscope_server"
    microscope_server_root.mkdir()

    _touch_ws_file(ws_root, "20250101", "PS99")
    _touch_ws_file(ws_root, "20250101b", "PS99")
    (cam_root / "20250101" / "PS99").mkdir(parents=True)
    (cam_root / "20250101b" / "PS99").mkdir(parents=True)

    cfg = _write_paths_yaml_full(
        tmp_path, ws_root, cam_root, outputs_root, microscope_server_root,
    )
    resolver = PathResolver(cfg, output_root=outputs_root)
    overrides = {
        "secondary_spout_sessions": {
            "PS99": {"2025-01-01": {}},
        },
    }
    return {
        "resolver": resolver,
        "overrides_config": overrides,
        "animal_info": _make_animal_info(),
        "tmp_path": tmp_path,
        "ws_root": ws_root,
        "outputs_root": outputs_root,
        "microscope_server_root": microscope_server_root,
    }


_LOAD_OR_COMPUTE_PATCH = (
    "stroke_orofacial.alignment.timebase.load_or_compute_alignment"
)
_GET_ANIMAL_PATCH = "stroke_orofacial.alignment.timebase.get_animal"


# ---------- Return-shape tests ----------


class TestReturnShape:
    def test_non_pattern_b_session_returns_single_entry_dict(
        self, pattern_b_layout, alignment_params,
    ):
        """Vanilla session NOT in secondary_spout_sessions: → one
        bare-half AlignmentResult keyed by None."""
        fx = pattern_b_layout
        overrides = {"secondary_spout_sessions": {}}
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(
            _LOAD_OR_COMPUTE_PATCH,
            return_value=_make_fake_alignment_result(),
        ):
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                alignment_params,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None}
        assert isinstance(result[None], AlignmentResult)

    def test_pattern_b_session_returns_two_entry_dict(
        self, pattern_b_layout, alignment_params,
    ):
        """Pattern B with both halves on disk → both bare and b
        AlignmentResults returned."""
        fx = pattern_b_layout
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(
            _LOAD_OR_COMPUTE_PATCH,
            return_value=_make_fake_alignment_result(),
        ) as mock_compute:
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                alignment_params,
                overrides_config=fx["overrides_config"],
            )

        assert set(result.keys()) == {None, "b"}
        # load_or_compute_alignment called twice (once per suffix)
        assert mock_compute.call_count == 2
        # First call: bare manifest (session_suffix=None)
        bare_manifest = mock_compute.call_args_list[0].args[0]
        b_manifest = mock_compute.call_args_list[1].args[0]
        assert bare_manifest.session_suffix is None
        assert b_manifest.session_suffix == "b"
        # session_id reflects the suffix
        assert bare_manifest.session_id == "PS99_20250101"
        assert b_manifest.session_id == "PS99_20250101b"

    def test_pattern_b_session_with_bare_ws_subdir_override(
        self, tmp_path: Path, monkeypatch, alignment_params,
    ):
        """Synthetic Pattern B with bare_ws_subdir_override (mirrors
        PS55/2025-04-24's asymmetric layout). The bare manifest's
        wavesurfer_file resolves from the override dir."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        ms_root = tmp_path / "microscope_server"
        ms_root.mkdir()
        _touch_ws_file(ws_root, "20250424a", "PS99")  # bare override target
        _touch_ws_file(ws_root, "20250424b", "PS99")
        (cam_root / "20250424" / "PS99").mkdir(parents=True)
        (cam_root / "20250424b" / "PS99").mkdir(parents=True)

        cfg = _write_paths_yaml_full(
            tmp_path, ws_root, cam_root, outputs_root, ms_root,
        )
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {
                    "2025-04-24": {
                        "bare_ws_subdir_override": "20250424a",
                    },
                },
            },
        }

        with patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(
            _LOAD_OR_COMPUTE_PATCH,
            return_value=_make_fake_alignment_result(),
        ) as mock_compute:
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 4, 24), resolver,
                alignment_params,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None, "b"}
        bare_manifest = mock_compute.call_args_list[0].args[0]
        # Bare manifest's wavesurfer_file resolved via the override
        assert bare_manifest.wavesurfer_file is not None
        assert bare_manifest.wavesurfer_file.parent.parent.name == "20250424a"


# ---------- Partial-failure tolerance ----------


class TestPartialFailure:
    def test_pattern_b_bare_missing_returns_b_only(
        self, tmp_path: Path, monkeypatch, alignment_params, caplog,
    ):
        """Only b half on disk → result has {"b": ...} only; bare logged."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        ms_root = tmp_path / "microscope_server"
        ms_root.mkdir()
        # Only b half on disk
        _touch_ws_file(ws_root, "20250101b", "PS99")
        (cam_root / "20250101b" / "PS99").mkdir(parents=True)

        cfg = _write_paths_yaml_full(
            tmp_path, ws_root, cam_root, outputs_root, ms_root,
        )
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        # Mock load_or_compute_alignment to raise FileNotFoundError when
        # the manifest's wavesurfer_file is None (the bare-half manifest
        # will fail to discover any WS file).
        def fake_loc(manifest, resolver, params, **kwargs):
            if manifest.wavesurfer_file is None:
                raise FileNotFoundError(
                    f"{manifest.session_id}: ws file is None"
                )
            return _make_fake_alignment_result()

        import logging

        with caplog.at_level(logging.WARNING), patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_LOAD_OR_COMPUTE_PATCH, side_effect=fake_loc):
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), resolver,
                alignment_params,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {"b"}
        assert any(
            "skipping alignment for PS99/2025-01-01 suffix=None"
            in rec.message
            for rec in caplog.records
        ), f"expected bare-half skip warning in {[r.message for r in caplog.records]}"

    def test_pattern_b_b_missing_returns_bare_only(
        self, tmp_path: Path, monkeypatch, alignment_params, caplog,
    ):
        """Only bare half on disk → result has {None: ...} only; b logged."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        ms_root = tmp_path / "microscope_server"
        ms_root.mkdir()
        # Only bare half on disk
        _touch_ws_file(ws_root, "20250101", "PS99")
        (cam_root / "20250101" / "PS99").mkdir(parents=True)

        cfg = _write_paths_yaml_full(
            tmp_path, ws_root, cam_root, outputs_root, ms_root,
        )
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        def fake_loc(manifest, resolver, params, **kwargs):
            if manifest.wavesurfer_file is None:
                raise FileNotFoundError(
                    f"{manifest.session_id}: ws file is None"
                )
            return _make_fake_alignment_result()

        import logging

        with caplog.at_level(logging.WARNING), patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_LOAD_OR_COMPUTE_PATCH, side_effect=fake_loc):
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), resolver,
                alignment_params,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None}
        assert any(
            "suffix='b'" in rec.message
            for rec in caplog.records
        ), f"expected b-half skip warning in {[r.message for r in caplog.records]}"

    def test_pattern_b_both_missing_raises(
        self, tmp_path: Path, monkeypatch, alignment_params,
    ):
        """Neither half on disk → raises FIRST FileNotFoundError."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        ms_root = tmp_path / "microscope_server"
        ms_root.mkdir()
        # NO halves touched

        cfg = _write_paths_yaml_full(
            tmp_path, ws_root, cam_root, outputs_root, ms_root,
        )
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        def fake_loc(manifest, resolver, params, **kwargs):
            if manifest.wavesurfer_file is None:
                raise FileNotFoundError(
                    f"{manifest.session_id}: ws file is None"
                )
            return _make_fake_alignment_result()

        with patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_LOAD_OR_COMPUTE_PATCH, side_effect=fake_loc):
            with pytest.raises(FileNotFoundError):
                load_or_compute_alignment_by_animal_date(
                    "PS99", datetime.date(2025, 1, 1), resolver,
                    alignment_params,
                    overrides_config=overrides,
                )


# ---------- Pattern A regression ----------


class TestPatternAUnchanged:
    def test_pattern_a_session_unchanged_behavior(
        self, tmp_path: Path, monkeypatch, alignment_params,
    ):
        """Pattern A (PS48/2025-03-14, in multi_half_sessions:) flows
        through unchanged → single-entry {None: AlignmentResult(...)}.
        The multi-half merge dispatch fires inside
        load_or_compute_alignment when manifest.halves is not None."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        ms_root = tmp_path / "microscope_server"
        ms_root.mkdir()
        _touch_ws_file(ws_root, "20250314a", "PS48")
        _touch_ws_file(ws_root, "20250314b", "PS48")
        (cam_root / "20250314a" / "PS48").mkdir(parents=True)
        (cam_root / "20250314b" / "PS48").mkdir(parents=True)

        cfg = _write_paths_yaml_full(
            tmp_path, ws_root, cam_root, outputs_root, ms_root,
        )
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "multi_half_sessions": {
                "PS48": {
                    "20250314": {
                        "halves": [
                            {
                                "id": "a", "ws_subdir": "20250314a",
                                "cam_subdir": "20250314a",
                                "file_timestamp": "2025-03-14T12_31_07",
                            },
                            {
                                "id": "b", "ws_subdir": "20250314b",
                                "cam_subdir": "20250314b",
                                "file_timestamp": "2025-03-14T13_09_29",
                            },
                        ],
                    },
                },
            },
        }
        merged_alignment = _make_fake_alignment_result(
            source="merged_multi_half",
        )

        with patch(
            _GET_ANIMAL_PATCH, return_value=_ps48_animal_info(),
        ), patch(_LOAD_OR_COMPUTE_PATCH, return_value=merged_alignment):
            result = load_or_compute_alignment_by_animal_date(
                "PS48", datetime.date(2025, 3, 14), resolver,
                alignment_params,
                overrides_config=overrides,
            )

        # Single-entry dict keyed by None — Pattern A is NOT in
        # secondary_spout_sessions: so iter_session_suffixes returns [None].
        assert set(result.keys()) == {None}
        assert result[None].source == "merged_multi_half"


# ---------- Suffix-aware path threading ----------


class TestSuffixAwarePaths:
    def test_pattern_b_alignment_templates_resolve_at_suffix_aware_paths(
        self, pattern_b_layout, alignment_params,
    ):
        """build_manifest's alignment_template discovery uses the suffix-
        aware path. Pre-populate ``{ms_root}/.../{date_str}b.npz`` and
        verify the b-half manifest's ``alignment_template`` field
        resolves to that file (not the bare-half path)."""
        fx = pattern_b_layout
        # Construct the legacy-read paths for both halves
        bare_path = fx["resolver"].alignment_template_legacy_read(
            "PS99", datetime.date(2025, 1, 1), cam="cam2",
            session_suffix=None,
        )
        b_path = fx["resolver"].alignment_template_legacy_read(
            "PS99", datetime.date(2025, 1, 1), cam="cam2",
            session_suffix="b",
        )
        # Different filenames per Phase 7-pre-secondary-spout Task 3c
        assert bare_path.name == "20250101.npz"
        assert b_path.name == "20250101b.npz"
        # Touch only the b half's cache file
        b_path.parent.mkdir(parents=True, exist_ok=True)
        b_path.touch()

        # Capture the manifests built by the wrapper (mock alignment compute)
        captured_manifests: list = []

        def fake_loc(manifest, resolver, params, **kwargs):
            captured_manifests.append(manifest)
            return _make_fake_alignment_result()

        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(_LOAD_OR_COMPUTE_PATCH, side_effect=fake_loc):
            load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                alignment_params,
                overrides_config=fx["overrides_config"],
            )

        bare_manifest, b_manifest = captured_manifests
        # Bare manifest's alignment_template: NOT found (only b touched)
        assert bare_manifest.alignment_template is None
        # b-half manifest's alignment_template: resolves to {date_str}b.npz
        assert b_manifest.alignment_template == b_path
        assert b_manifest.alignment_template.name == "20250101b.npz"

    def test_pattern_b_cache_discovery_returns_loaded_for_b_half(
        self, pattern_b_layout, alignment_params,
    ):
        """Pre-populate REAL NPZs at BOTH halves' cache paths (with
        distinct contents); verify each half's AlignmentResult sources
        the correct cache file. Exercises both build_manifest's
        ``alignment_template`` resolution AND
        load_or_compute_alignment's cache-hit early-return — for both
        halves.

        Writing real NPZs at both cache paths sidesteps a tangential
        h5py-empty-file failure on the bare-half "compute" path; the
        test's focus is suffix-aware cache discovery, not compute-path
        error handling."""
        fx = pattern_b_layout
        bare_path = fx["resolver"].alignment_template_legacy_read(
            "PS99", datetime.date(2025, 1, 1), cam="cam2",
            session_suffix=None,
        )
        b_path = fx["resolver"].alignment_template_legacy_read(
            "PS99", datetime.date(2025, 1, 1), cam="cam2",
            session_suffix="b",
        )
        bare_path.parent.mkdir(parents=True, exist_ok=True)
        b_path.parent.mkdir(parents=True, exist_ok=True)
        # Write distinct synthetic NPZs so we can tell them apart by
        # content if the wrapper mixes up suffix → cache mapping.
        np.savez_compressed(
            bare_path,
            sig_camIdx__idx_ws=np.array([10, 20, 30], dtype=np.int64),
            sig_wsIdx__idx_cam=np.array([1, 2, 3], dtype=np.int64),
            slope_ws_per_camFrame=np.float64(4.0),
            intercept_ws_samples=np.float64(0.0),
            Fs_ws_input=np.float64(20000.0),
        )
        np.savez_compressed(
            b_path,
            sig_camIdx__idx_ws=np.array([100, 200, 300], dtype=np.int64),
            sig_wsIdx__idx_cam=np.array([11, 22, 33], dtype=np.int64),
            slope_ws_per_camFrame=np.float64(4.0),
            intercept_ws_samples=np.float64(0.0),
            Fs_ws_input=np.float64(20000.0),
        )

        # Don't mock load_or_compute_alignment — exercise it for real
        # so the cache-hit early-return is what produces both results.
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ):
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                alignment_params,
                overrides_config=fx["overrides_config"],
            )

        # Both halves hit their respective caches
        assert set(result.keys()) == {None, "b"}
        assert result[None].source == "loaded"
        assert result["b"].source == "loaded"
        # Suffix-aware cache hit: each result has the values from its
        # OWN cache file (not mixed up).
        np.testing.assert_array_equal(
            result[None].sig_camIdx__idx_ws,
            np.array([10, 20, 30], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            result["b"].sig_camIdx__idx_ws,
            np.array([100, 200, 300], dtype=np.int64),
        )


# ---------- Lazy-load overrides ----------


class TestLazyOverridesLoad:
    def test_overrides_config_lazy_loaded_when_none(
        self, pattern_b_layout, alignment_params,
    ):
        """When overrides_config kwarg is None, the function should call
        load_session_overrides() under the hood (mirrors Task 4's
        process_session_by_animal_date pattern)."""
        fx = pattern_b_layout
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(
            _LOAD_OR_COMPUTE_PATCH,
            return_value=_make_fake_alignment_result(),
        ), patch(
            "stroke_orofacial.config_loader.load_session_overrides",
            return_value=fx["overrides_config"],
        ) as mock_load:
            result = load_or_compute_alignment_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                alignment_params,
                # overrides_config NOT passed — should trigger lazy-load
            )

        mock_load.assert_called_once()
        # And the loaded config drove Pattern B detection
        assert set(result.keys()) == {None, "b"}
