"""Phase 7-pre-multi-half tests for process_session's per-half loop.

Verifies the per-half routing and on-disk layout for Pattern A
multi-half sessions. The actual Phase 2 algorithm (WS load, treadmill
calibration, lick detection, bouts) is mocked at the
``_run_phase2_pipeline`` boundary so these tests run fast without
needing real wavesurfer .h5 files — the algorithm itself is covered by
``test_session_processing.py`` on a single-half integration session
(PS46 / 2025-03-07).

Tests focus on:
  - path construction (per-half subdir layout under
    ``{date_str}{halves_concat_label}/``).
  - dispatch (one call to ``_run_phase2_pipeline`` per half with the
    correct ws_file + per-half output_paths).
  - return dict shape (composite-keyed for multi-half;
    non-overlapping with single-half keys).
  - overwrite gating (skip / force across the full per-half path set).
  - fail-loud paths (per-half WS file is None).
  - helper functions (``_halves_concat_label`` /
    ``_per_half_output_path``).
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from stroke_orofacial.manifest import HalfSpec, SessionManifest
from stroke_orofacial.spout_behavior.session_processing import (
    OUTPUT_TYPES,
    _halves_concat_label,
    _per_half_output_path,
    process_session,
)


# ---------- Helpers ----------


def _make_pattern_a_manifest(
    tmp_path: Path,
    *,
    animal: str = "PS48",
    date: datetime.date = datetime.date(2025, 3, 14),
    ws_files_exist: bool = True,
) -> SessionManifest:
    """Build a Pattern A multi-half SessionManifest with two HalfSpecs.

    Touches synthetic per-half WS .h5 files so HalfSpec.wavesurfer_file
    points at real (empty) on-disk files when ``ws_files_exist=True``.
    With ``ws_files_exist=False`` the WS path is None on each half so
    callers can verify the FileNotFoundError fail-loud path.
    """
    ws_a = tmp_path / "ws" / "20250314a" / animal / "stroke_0001.h5"
    ws_b = tmp_path / "ws" / "20250314b" / animal / "stroke_0002.h5"
    if ws_files_exist:
        for p in (ws_a, ws_b):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()

    halves = [
        HalfSpec(
            id="a",
            ws_subdir="20250314a",
            cam_subdir="20250314a",
            file_timestamp="2025-03-14T12_31_07",
            wavesurfer_file=ws_a if ws_files_exist else None,
        ),
        HalfSpec(
            id="b",
            ws_subdir="20250314b",
            cam_subdir="20250314b",
            file_timestamp="2025-03-14T13_09_29",
            wavesurfer_file=ws_b if ws_files_exist else None,
        ),
    ]

    return SessionManifest(
        session_id=f"{animal}_{date.strftime('%Y%m%d')}",
        animal=animal,
        date=date,
        day_relative_to_stroke=-5,
        phase="baseline",
        wavesurfer_file=None,  # per multi-half contract
        video_files=[],
        dlc_h5_files=[],
        dlc_csv_files=[],
        alignment_template=None,
        excluded=False,
        wavesurfer_sides_match_mouse_sides=True,
        halves=halves,
    )


def _make_resolver(tmp_path: Path):
    """Real PathResolver pointing pipeline_outputs at tmp_path."""
    from stroke_orofacial.paths import PathResolver

    # output_root override redirects pipeline_outputs() only — other roots
    # (wavesurfer_raw etc.) keep resolving from the real config but that's
    # fine here since process_session() only writes via pipeline_outputs.
    return PathResolver(output_root=tmp_path / "outputs")


@pytest.fixture()
def minimal_defaults() -> dict:
    """Minimal defaults dict — _run_phase2_pipeline is mocked so the
    actual params don't drive any computation."""
    return {
        "process_treadmill_signal": {
            "offset_in_volts": 0.0,
            "voltSec_per_rot": 0.382,
            "mm_per_rot": 29.25,
            "smoothing_sigma": 0.15,
        },
        "find_running_bouts": {},
        "find_licks_and_rewards": {},
        "find_grooming_bouts": {},
        "find_quiet_bouts": {},
        "find_peri_reward_periods": {},
        "find_peri_reward_and_tone_periods": {},
    }


# ---------- Path-helper smoke ----------


class TestHalvesConcatLabel:
    def test_two_halves(self):
        assert _halves_concat_label(["a", "b"]) == "ab"

    def test_three_halves(self):
        assert _halves_concat_label(["a", "b", "c"]) == "abc"

    def test_single_half_edge_case(self):
        # Defensive: a single-id list still returns the id verbatim. The
        # multi-half writer never gets here because halves is None for
        # single-half manifests, but the helper is otherwise general.
        assert _halves_concat_label(["a"]) == "a"


class TestPerHalfOutputPath:
    def test_pattern_a_layout(self, tmp_path: Path):
        out = _per_half_output_path(
            tmp_path / "outputs" / "spout_behavior",
            output_type="licks_and_rewards",
            animal="PS48",
            date_str="20250314",
            halves_concat_label="ab",
            half_id="a",
        )
        assert out == (
            tmp_path / "outputs" / "spout_behavior" / "licks_and_rewards"
            / "PS48" / "20250314ab" / "20250314a.npz"
        )

    def test_half_b_path(self, tmp_path: Path):
        out = _per_half_output_path(
            tmp_path / "outputs" / "spout_behavior",
            output_type="treadmill_signals_preprocessed",
            animal="PS48",
            date_str="20250314",
            halves_concat_label="ab",
            half_id="b",
        )
        assert out.parent.name == "20250314ab"
        assert out.name == "20250314b.npz"


# ---------- Multi-half routing ----------


class TestProcessSessionMultiHalf:
    def test_runs_pipeline_once_per_half(
        self, tmp_path: Path, minimal_defaults
    ):
        """One ``_run_phase2_pipeline`` call per half, with the correct
        per-half WS file and per-half output_paths."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as mock_pipeline:
            result = process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        # 2 halves -> 2 pipeline invocations
        assert mock_pipeline.call_count == 2

        # Inspect call args by half order — kwargs/positional both fine
        # since _run_phase2_pipeline is positional-only at the call site.
        call_a, call_b = mock_pipeline.call_args_list
        # First positional arg is ws_file
        assert call_a.args[0] == manifest.halves[0].wavesurfer_file
        assert call_b.args[0] == manifest.halves[1].wavesurfer_file

        # 14 entries returned (7 output types × 2 halves)
        assert len(result) == 14
        # Composite keys
        assert "licks_and_rewards__a" in result
        assert "licks_and_rewards__b" in result

    def test_per_half_paths_use_subdir_layout(
        self, tmp_path: Path, minimal_defaults
    ):
        """Per-half outputs land in ``{date_str}{halves_concat_label}/``
        subdir; merged-file path (parent level) is NOT written here."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as _mock:
            result = process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        for output_type in OUTPUT_TYPES:
            for half_id in ("a", "b"):
                key = f"{output_type}__{half_id}"
                p = result[key]
                # Parent dir is the per-(animal, date) subdir
                assert p.parent.name == "20250314ab"
                # File name encodes the half_id
                assert p.name == f"20250314{half_id}.npz"
                # Animal and output_type segments correct
                assert p.parent.parent.name == "PS48"
                assert p.parent.parent.parent.name == output_type
                # Per-half NPZs do NOT shadow the parent-level merged path
                merged_path = p.parent.parent / "20250314.npz"
                assert p != merged_path

    def test_pipeline_receives_per_half_output_paths(
        self, tmp_path: Path, minimal_defaults
    ):
        """The output_paths arg passed to _run_phase2_pipeline maps each
        OUTPUT_TYPE to that half's per-half NPZ path (not merged)."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as mock_pipeline:
            process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        call_a, call_b = mock_pipeline.call_args_list
        out_paths_a = call_a.args[3]
        out_paths_b = call_b.args[3]

        for output_type in OUTPUT_TYPES:
            assert out_paths_a[output_type].name == "20250314a.npz"
            assert out_paths_b[output_type].name == "20250314b.npz"
            assert out_paths_a[output_type].parent.name == "20250314ab"
            assert out_paths_b[output_type].parent.name == "20250314ab"

    def test_skip_when_all_per_half_outputs_exist(
        self, tmp_path: Path, minimal_defaults
    ):
        """overwrite='skip' returns an empty dict and does NOT invoke
        _run_phase2_pipeline when every per-half NPZ already exists."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)
        out_root = tmp_path / "outputs" / "spout_behavior"

        # Pre-create all 14 per-half NPZs so the overwrite check trips skip.
        for output_type in OUTPUT_TYPES:
            for half_id in ("a", "b"):
                p = (
                    out_root / output_type / "PS48" / "20250314ab"
                    / f"20250314{half_id}.npz"
                )
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as mock_pipeline:
            result = process_session(
                manifest, resolver,
                overwrite="skip",
                defaults=minimal_defaults,
                overrides_config={},
            )

        assert result == {}
        mock_pipeline.assert_not_called()
        # Skip path still emits params.json for audit trail
        assert (out_root / "params" / "PS48" / "20250314.json").exists()

    def test_force_overwrite_invokes_pipeline_even_when_outputs_exist(
        self, tmp_path: Path, minimal_defaults
    ):
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)
        out_root = tmp_path / "outputs" / "spout_behavior"
        # Pre-create one per-half NPZ to confirm overwrite path fires
        p = (
            out_root / "licks_and_rewards" / "PS48" / "20250314ab"
            / "20250314a.npz"
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as mock_pipeline:
            result = process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        assert mock_pipeline.call_count == 2
        assert len(result) == 14

    def test_raises_when_per_half_ws_file_is_none(
        self, tmp_path: Path, minimal_defaults
    ):
        """Fail-loud when build_manifest didn't populate a half's WS file
        — error message names the half_id and ws_subdir so the user can
        debug the WS mount / glob."""
        manifest = _make_pattern_a_manifest(tmp_path, ws_files_exist=False)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ):
            with pytest.raises(FileNotFoundError) as excinfo:
                process_session(
                    manifest, resolver,
                    overwrite="force",
                    defaults=minimal_defaults,
                    overrides_config={},
                )

        msg = str(excinfo.value)
        assert "halves[a].wavesurfer_file is None" in msg
        assert "20250314a" in msg  # ws_subdir named in the error
        assert "PS48" in msg

    def test_single_params_json_written_at_session_level(
        self, tmp_path: Path, minimal_defaults
    ):
        """Multi-half emits ONE params.json per (animal, date), not one
        per half. The provenance file lives at the session level."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)
        out_root = tmp_path / "outputs" / "spout_behavior"

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ):
            process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        # Single per-session params.json (no half_id in filename)
        assert (out_root / "params" / "PS48" / "20250314.json").exists()
        # No per-half params files
        assert not (out_root / "params" / "PS48" / "20250314a.json").exists()
        assert not (out_root / "params" / "PS48" / "20250314b.json").exists()


class TestSingleHalfPathUnchanged:
    """halves=None routes to the existing single-half pipeline."""

    def test_returns_seven_keyed_dict(self, tmp_path: Path, minimal_defaults):
        # Build a single-half manifest (halves=None — default)
        ws_file = tmp_path / "ws" / "20250307" / "PS46" / "stroke_0001.h5"
        ws_file.parent.mkdir(parents=True, exist_ok=True)
        ws_file.touch()
        manifest = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
            wavesurfer_file=ws_file,
        )
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as mock_pipeline:
            result = process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        # 7 entries — single-half shape preserved
        assert len(result) == 7
        assert set(result.keys()) == set(OUTPUT_TYPES)
        # Pipeline invoked exactly once
        mock_pipeline.assert_called_once()
        # Output paths match the legacy single-half layout (no subdir)
        assert result["licks_and_rewards"].name == "20250307.npz"
        assert result["licks_and_rewards"].parent.name == "PS46"
