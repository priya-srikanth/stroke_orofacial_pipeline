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

import numpy as np
import pytest

from stroke_orofacial.manifest import HalfSpec, SessionManifest
from stroke_orofacial.spout_behavior.session_processing import (
    OUTPUT_TYPES,
    _halves_concat_label,
    _per_half_output_path,
    process_session,
)


# Module path of the merge function used by _process_session_multi_half.
# Patched in tests that mock _run_phase2_pipeline (so per-half NPZs are
# never actually written to disk) — without the merge patch, the merge
# call inside production code would raise FileNotFoundError on the
# missing per-half NPZs. Tests that exercise the real merge (see
# TestMergeWiring) leave this unpatched.
_MERGE_PATCH_TARGET = (
    "stroke_orofacial.spout_behavior.session_processing.merge_licks_and_rewards"
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
        ) as mock_pipeline, patch(_MERGE_PATCH_TARGET):
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
        subdir; the returned dict keys per-half NPZ paths (the merged
        parent-level NPZ written by ``merge_licks_and_rewards`` lives
        at ``...{output_type}/{animal}/{date_str}.npz`` — NOT in the
        per-half subdir)."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
        ) as _mock, patch(_MERGE_PATCH_TARGET):
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
        ) as mock_pipeline, patch(_MERGE_PATCH_TARGET):
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
        ) as mock_pipeline, patch(_MERGE_PATCH_TARGET):
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
        ), patch(_MERGE_PATCH_TARGET):
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
        ), patch(_MERGE_PATCH_TARGET):
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


class TestMergeWiring:
    """End-to-end wiring of ``merge_licks_and_rewards`` into the multi-half
    branch of ``process_session``.

    Unlike the dispatch tests above, these tests do NOT mock the merge —
    they stub ``_run_phase2_pipeline`` to write minimal-but-valid per-half
    licks NPZs (n_samples + WS-sample-indexed event arrays + side-
    convention stamps) so the real merge function can consume them. This
    is the integration boundary between the per-half loop (Phase 2) and
    the licks merge (Task 4 ``merge_licks_and_rewards``) — verifying it
    here closes the deferred-from-Task-4 loop noted in the kickoff doc.
    """

    @staticmethod
    def _write_synthetic_per_half_npzs(
        ws_file: Path,
        params: dict,
        ws_match: bool,
        output_paths: dict[str, Path],
        *,
        half_a_marker: str,
        half_b_marker: str,
        n_samples_a: int,
        n_samples_b: int,
        half_a_licks: np.ndarray,
        half_b_licks: np.ndarray,
    ) -> None:
        """Stand-in for ``_run_phase2_pipeline`` that writes per-half NPZs.

        Identifies which half is being processed by inspecting the
        ws_file name — the per-half manifest puts a stable marker in
        each half's WS path (``stroke_0001.h5`` for A, ``stroke_0002.h5``
        for B in :func:`_make_pattern_a_manifest`). The licks NPZ
        carries the keys the real merge needs (n_samples + 6 event
        arrays + side-convention stamps); the other 6 output types are
        written as empty NPZs so on-disk file-existence holds for any
        downstream check.
        """
        if half_a_marker in str(ws_file):
            n_samples = n_samples_a
            lick_l = half_a_licks
        else:
            assert half_b_marker in str(ws_file), (
                f"unexpected ws_file: {ws_file}"
            )
            n_samples = n_samples_b
            lick_l = half_b_licks

        licks_payload = {
            "n_samples": np.int64(n_samples),
            "Fs": np.float64(20000.0),
            "Lick_L": lick_l.astype(np.int64, copy=False),
            "Lick_R": np.array([], dtype=np.int64),
            "Reward_L": np.array([], dtype=np.int64),
            "Reward_R": np.array([], dtype=np.int64),
            "Tone_L": np.array([], dtype=np.int64),
            "Tone_R": np.array([], dtype=np.int64),
            "side_convention_version": np.int64(1),
            "wavesurfer_sides_match_mouse_sides": True,
        }

        for output_type, path in output_paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if output_type == "licks_and_rewards":
                np.savez_compressed(path, **licks_payload)
            else:
                # Empty NPZ — the merge only reads licks_and_rewards/;
                # the other 6 outputs just need to exist on disk for
                # consistency with the real pipeline behavior.
                np.savez_compressed(path)

    def test_merged_licks_npz_written_alongside_per_half(
        self, tmp_path: Path, minimal_defaults
    ):
        """``process_session`` on a multi-half manifest emits per-half
        licks NPZs AND a merged parent-level licks NPZ.

        Verifies the full path of artefacts:
          - 2 per-half NPZs at ``.../licks_and_rewards/PS48/20250314ab/{date}{half}.npz``
          - 1 merged NPZ at ``.../licks_and_rewards/PS48/20250314.npz``

        Verifies offset semantics in ws_sample mode: half-A indices
        pass through unchanged, half-B indices land at ``half_b_value
        + n_samples_A`` (so the merged time axis is a unified WS-sample
        timeline with no overlap between halves).
        """
        n_samples_a = 100_000
        n_samples_b = 120_000
        half_a_licks = np.array([10, 50, 99_999], dtype=np.int64)
        half_b_licks = np.array([5, 60_000, 119_999], dtype=np.int64)

        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)
        out_root = tmp_path / "outputs" / "spout_behavior"

        def fake_pipeline(ws_file, params, ws_match, output_paths):
            self._write_synthetic_per_half_npzs(
                ws_file, params, ws_match, output_paths,
                half_a_marker="stroke_0001.h5",
                half_b_marker="stroke_0002.h5",
                n_samples_a=n_samples_a,
                n_samples_b=n_samples_b,
                half_a_licks=half_a_licks,
                half_b_licks=half_b_licks,
            )

        with patch(
            "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline",
            side_effect=fake_pipeline,
        ):
            result = process_session(
                manifest, resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config={},
            )

        # Per-half licks NPZs exist on disk
        per_half_a = (
            out_root / "licks_and_rewards" / "PS48"
            / "20250314ab" / "20250314a.npz"
        )
        per_half_b = (
            out_root / "licks_and_rewards" / "PS48"
            / "20250314ab" / "20250314b.npz"
        )
        assert per_half_a.exists()
        assert per_half_b.exists()
        # Returned dict still keys per-half paths (shape unchanged by
        # the merge wiring — the merged path is derivable but not
        # included in the dict to keep single-half / multi-half return
        # shapes orthogonal).
        assert result["licks_and_rewards__a"] == per_half_a
        assert result["licks_and_rewards__b"] == per_half_b

        # Merged NPZ at parent-level path (no halves_concat_label segment)
        merged_path = (
            out_root / "licks_and_rewards" / "PS48" / "20250314.npz"
        )
        assert merged_path.exists(), (
            f"merged licks NPZ missing — merge_licks_and_rewards "
            f"wiring did not fire: {merged_path}"
        )

        # Provenance round-trip: merged carries per-half counts + offset
        merged = np.load(merged_path, allow_pickle=True)
        assert int(merged["merged_n_samples_A"]) == n_samples_a
        assert int(merged["merged_n_samples_B"]) == n_samples_b
        assert int(merged["ws_sample_offset_for_B"]) == n_samples_a

        # Offset semantics: half-A indices preserved, half-B indices
        # shifted by n_samples_A so they sit in [n_samples_A, total).
        merged_lick_l = np.asarray(merged["Lick_L"])
        expected = np.concatenate(
            [half_a_licks, half_b_licks + n_samples_a]
        )
        np.testing.assert_array_equal(merged_lick_l, expected)
        # No overlap between half-A and half-B portions
        assert int(merged_lick_l[:half_a_licks.size].max()) < int(
            merged_lick_l[half_a_licks.size:].min()
        )
