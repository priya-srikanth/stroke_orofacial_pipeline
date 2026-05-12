"""Phase 7-pre-secondary-spout Task 4 — Phase 2 driver per-suffix wiring.

Covers ``process_session_by_animal_date`` + ``process_animal`` after
they were rewired to iterate
:func:`stroke_orofacial.manifest.iter_session_suffixes`. Non-Pattern-B
and Pattern A sessions still process once (suffix=None); Pattern B
sessions process the bare half (suffix=None) AND the b half
(suffix="b") as independent logical sessions. Partial-failure
tolerance: if one half's data is missing on disk, the other half's
result is still returned; if BOTH halves fail, the FIRST
``FileNotFoundError`` is re-raised.

Fixture strategy: write a synthetic ``paths.yaml`` per-test that
redirects ``wavesurfer_raw`` / ``camera_raw`` / ``microscope_pipeline_outputs``
at ``tmp_path`` subdirs, touch the synthetic WS ``.h5`` files at the
expected layout, and mock ``_run_phase2_pipeline`` so the test
doesn't require real wavesurfer data. Per
:mod:`docs/testing-conventions`, the resolver's ``output_root``
override ensures all writes land in ``tmp_path`` — never in the
real ``stroke_orofacial_pipeline_outputs/`` tree.
"""

from __future__ import annotations

import datetime
import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver


# Match the host-platform key used by tests/test_paths.py so the
# synthetic paths.yaml is reachable on both Mac and Windows runs.
import platform as _platform_module
_HOST_KEY = "windows" if _platform_module.system() == "Windows" else "mac"


# ---------- Fixtures ----------


def _write_paths_yaml(
    tmp_path: Path,
    ws_root: Path,
    cam_root: Path,
    pipeline_outputs_root: Path,
) -> Path:
    """Write a synthetic paths.yaml that routes the 3 logical roots
    Phase 2 needs at ``tmp_path`` subdirs.

    Microscope_server is intentionally NOT defined — build_manifest
    will fall back to a None root for ``alignment_template_legacy_read``
    discovery; since the alignment file doesn't exist, the resolver
    just yields ``alignment_template = None`` on the manifest (the
    Phase 2 spout-behavior code doesn't read it).
    """
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
                description: "legacy server (unused in Phase 2 tests)"
                mounts:
                  {_HOST_KEY}:
                    - "{(tmp_path / "no_microscope_server").as_posix()}"
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
    """Touch a synthetic wavesurfer .h5 file at the layout
    ``{ws_root}/{subdir}/{animal}/{filename}``."""
    p = ws_root / subdir / animal / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_animal_info(animal: str = "PS99") -> AnimalInfo:
    """Synthetic AnimalInfo for a test mouse with a broad session window."""
    return AnimalInfo(
        animal_id=animal,
        stroke_date=datetime.date(2025, 1, 15),
        session_start=datetime.date(2025, 1, 1),
        session_end=datetime.date(2025, 12, 31),
    )


@pytest.fixture()
def setup_pattern_b_layout(tmp_path: Path, monkeypatch):
    """Test fixture that lays out a synthetic Pattern B session under
    ``tmp_path`` and returns ``(resolver, overrides_config, animal_info)``.

    Synthetic session: PS99/2025-01-01. Bare half at
    ``ws_root/20250101/PS99/``; b half at ``ws_root/20250101b/PS99/``.
    Both with a touched ``stroke_0001.h5`` (empty file — the test
    mocks ``_run_phase2_pipeline`` so no real WS data is parsed).
    Cam dirs touched as empty directories so ``discover_video_files``
    doesn't fail (it accepts empty dirs).

    Returns
    -------
    dict
        ``{"resolver": PathResolver, "overrides_config": dict,
        "animal_info": AnimalInfo, "tmp_path": Path,
        "ws_root": Path, "outputs_root": Path}``.
    """
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    ws_root = tmp_path / "wavesurfer"
    ws_root.mkdir()
    cam_root = tmp_path / "camera"
    cam_root.mkdir()
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()

    # Touch synthetic WS files for both halves
    _touch_ws_file(ws_root, "20250101", "PS99")
    _touch_ws_file(ws_root, "20250101b", "PS99")
    # Cam dirs (empty — discover_video_files returns [] when no AVIs)
    (cam_root / "20250101" / "PS99").mkdir(parents=True)
    (cam_root / "20250101b" / "PS99").mkdir(parents=True)

    cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
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
    }


def _fake_run_phase2_pipeline(
    ws_file: Path, params: dict, ws_match: bool, output_paths: dict[str, Path],
) -> None:
    """Stand-in for ``_run_phase2_pipeline`` that writes empty NPZ
    placeholder files at each output path.

    The real pipeline parses ``ws_file`` and writes 7 NPZs with
    computed analysis arrays; the test fixture's WS files are empty
    so the real pipeline would fail at h5 parsing. We mock at the
    pipeline boundary and write touch-only stubs so downstream
    file-existence checks (``params.json`` writer, the merge call
    in the multi-half branch) succeed.
    """
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


@pytest.fixture()
def minimal_defaults() -> dict:
    """Minimal defaults dict; _run_phase2_pipeline is mocked so the
    actual param values don't drive any computation."""
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


_PIPELINE_PATCH = (
    "stroke_orofacial.spout_behavior.session_processing._run_phase2_pipeline"
)
_GET_ANIMAL_PATCH = (
    "stroke_orofacial.spout_behavior.session_processing.get_animal"
)


# ---------- Pattern B return shape ----------


class TestPatternBReturnShape:
    """``process_session_by_animal_date`` returns a per-suffix dict.

    Non-Pattern-B and Pattern A sessions get a single-entry
    ``{None: {...}}``. Pattern B gets ``{None: {...bare...}, "b": {...b...}}``.
    """

    def test_non_pattern_b_session_returns_single_entry_dict(
        self, setup_pattern_b_layout, minimal_defaults,
    ):
        """Vanilla session NOT in secondary_spout_sessions: → one
        bare-half result keyed by None."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        fx = setup_pattern_b_layout
        # No secondary_spout_sessions entry for this animal+date pair
        overrides = {"secondary_spout_sessions": {}}
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None}
        assert len(result[None]) == 7  # 7 output types per OUTPUT_TYPES

    def test_pattern_b_session_returns_two_entry_dict(
        self, setup_pattern_b_layout, minimal_defaults,
    ):
        """Pattern B with both halves on disk → both bare and b
        results returned."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        fx = setup_pattern_b_layout
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=fx["overrides_config"],
            )

        assert set(result.keys()) == {None, "b"}
        assert len(result[None]) == 7
        assert len(result["b"]) == 7
        # The b-half output filenames carry the suffix
        b_licks = result["b"]["licks_and_rewards"]
        assert b_licks.name == "20250101b.npz"
        # Bare-half output filenames do NOT carry a suffix
        bare_licks = result[None]["licks_and_rewards"]
        assert bare_licks.name == "20250101.npz"

    def test_pattern_b_session_with_bare_ws_subdir_override(
        self, tmp_path: Path, monkeypatch, minimal_defaults,
    ):
        """Synthetic Pattern B with ``bare_ws_subdir_override``
        (mirrors PS55/2025-04-24's asymmetric ``20250424a`` WS dir).
        Bare half resolves to the override dir; b half uses
        ``{DATE}b`` convention."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # Bare WS dir is "20250424a" (override); b half is conventional
        _touch_ws_file(ws_root, "20250424a", "PS99")
        _touch_ws_file(ws_root, "20250424b", "PS99")
        # Cam dirs (b uses convention; bare cam IS bare "20250424" by
        # default since we don't override bare_cam_subdir_override)
        (cam_root / "20250424" / "PS99").mkdir(parents=True)
        (cam_root / "20250424b" / "PS99").mkdir(parents=True)

        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
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
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline) as mock_pipe:
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 4, 24), resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None, "b"}
        # The bare-half pipeline call was given the override-discovered ws_file
        bare_call_ws_file = mock_pipe.call_args_list[0].args[0]
        b_call_ws_file = mock_pipe.call_args_list[1].args[0]
        assert bare_call_ws_file.parent.name == "PS99"
        assert bare_call_ws_file.parent.parent.name == "20250424a"
        assert b_call_ws_file.parent.parent.name == "20250424b"


# ---------- Partial-failure tolerance ----------


class TestPatternBPartialFailure:
    def test_pattern_b_session_bare_missing_returns_b_only(
        self, tmp_path: Path, monkeypatch, minimal_defaults, caplog,
    ):
        """Only b half on disk → result dict has {"b": ...} only;
        bare half logged as warning; no raise."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # Only the b half exists
        _touch_ws_file(ws_root, "20250101b", "PS99")
        (cam_root / "20250101b" / "PS99").mkdir(parents=True)
        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        import logging

        with caplog.at_level(logging.WARNING), patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {"b"}
        # Warning logged for the bare-half failure
        assert any(
            "skipping PS99/2025-01-01 suffix=None" in rec.message
            for rec in caplog.records
        ), f"expected bare-half skip warning in {[r.message for r in caplog.records]}"

    def test_pattern_b_session_b_missing_returns_bare_only(
        self, tmp_path: Path, monkeypatch, minimal_defaults, caplog,
    ):
        """Only bare half on disk → result has {None: ...} only;
        b half logged as warning; no raise."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # Only the bare half exists
        _touch_ws_file(ws_root, "20250101", "PS99")
        (cam_root / "20250101" / "PS99").mkdir(parents=True)
        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        import logging

        with caplog.at_level(logging.WARNING), patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=overrides,
            )

        assert set(result.keys()) == {None}
        assert any(
            "suffix='b'" in rec.message
            for rec in caplog.records
        ), f"expected b-half skip warning in {[r.message for r in caplog.records]}"

    def test_pattern_b_session_both_missing_raises(
        self, tmp_path: Path, monkeypatch, minimal_defaults,
    ):
        """Neither half on disk → raises FileNotFoundError (single-half
        callers' existing semantics preserved when nothing succeeds)."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # NO halves touched on disk
        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        with patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            with pytest.raises(FileNotFoundError):
                process_session_by_animal_date(
                    "PS99", datetime.date(2025, 1, 1), resolver,
                    overwrite="force",
                    defaults=minimal_defaults,
                    overrides_config=overrides,
                )


# ---------- Pattern A regression guard ----------


class TestPatternAUnchanged:
    """Pattern A multi-half-merged sessions still return a single
    ``{None: {...merged...}}`` dict. Iteration produces ``[None]``
    for Pattern A (Pattern A isn't in secondary_spout_sessions:);
    process_session's multi-half branch fires inside that single
    iteration."""

    def test_pattern_a_session_unchanged_behavior(
        self, tmp_path: Path, monkeypatch, minimal_defaults,
    ):
        """PS48/2025-03-14 (in multi_half_sessions:) flows through
        unchanged — single-entry {None: {...}} dict, halves merged
        inside process_session."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # Pattern A per-half subdirs
        _touch_ws_file(ws_root, "20250314a", "PS48")
        _touch_ws_file(ws_root, "20250314b", "PS48")
        (cam_root / "20250314a" / "PS48").mkdir(parents=True)
        (cam_root / "20250314b" / "PS48").mkdir(parents=True)

        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
        resolver = PathResolver(cfg, output_root=outputs_root)
        # Synthetic Pattern A registry entry; no secondary_spout block.
        overrides = {
            "multi_half_sessions": {
                "PS48": {
                    "20250314": {
                        "halves": [
                            {
                                "id": "a",
                                "ws_subdir": "20250314a",
                                "cam_subdir": "20250314a",
                                "file_timestamp": "2025-03-14T12_31_07",
                            },
                            {
                                "id": "b",
                                "ws_subdir": "20250314b",
                                "cam_subdir": "20250314b",
                                "file_timestamp": "2025-03-14T13_09_29",
                            },
                        ],
                    },
                },
            },
        }
        ps48_info = AnimalInfo(
            animal_id="PS48",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
        )

        # Patch the merge as well — fake pipeline writes empty NPZs
        # which the real merge can't consume.
        _MERGE_PATCH = (
            "stroke_orofacial.spout_behavior.session_processing"
            ".merge_licks_and_rewards"
        )
        with patch(
            _GET_ANIMAL_PATCH, return_value=ps48_info,
        ), patch(
            _PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline,
        ), patch(_MERGE_PATCH):
            result = process_session_by_animal_date(
                "PS48", datetime.date(2025, 3, 14), resolver,
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=overrides,
            )

        # Single-entry dict keyed by None — Pattern A is NOT in
        # secondary_spout_sessions: so iter_session_suffixes returns [None].
        # process_session's multi-half branch fires inside, returning
        # a composite-keyed dict (14 entries for 7 outputs × 2 halves).
        assert set(result.keys()) == {None}
        assert len(result[None]) == 14  # 7 outputs × 2 halves
        assert "licks_and_rewards__a" in result[None]
        assert "licks_and_rewards__b" in result[None]


# ---------- process_animal collects per-suffix results ----------


class TestProcessAnimalReturnShape:
    def test_process_animal_collects_per_suffix_results(
        self, tmp_path: Path, monkeypatch, minimal_defaults,
    ):
        """Multi-date input: one Pattern B date + one vanilla date →
        list[dict[str | None, dict[str, Path]]] with 2 outer entries;
        the Pattern B entry has {None, 'b'} keys, the vanilla has
        {None} only."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_animal,
        )

        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        ws_root = tmp_path / "wavesurfer"
        ws_root.mkdir()
        cam_root = tmp_path / "camera"
        cam_root.mkdir()
        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()
        # Pattern B date 2025-01-01 with both halves
        _touch_ws_file(ws_root, "20250101", "PS99")
        _touch_ws_file(ws_root, "20250101b", "PS99")
        (cam_root / "20250101" / "PS99").mkdir(parents=True)
        (cam_root / "20250101b" / "PS99").mkdir(parents=True)
        # Vanilla date 2025-02-02 — single-half only
        _touch_ws_file(ws_root, "20250202", "PS99")
        (cam_root / "20250202" / "PS99").mkdir(parents=True)

        cfg = _write_paths_yaml(tmp_path, ws_root, cam_root, outputs_root)
        resolver = PathResolver(cfg, output_root=outputs_root)
        overrides = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }

        # process_animal calls load_session_overrides() internally — patch
        # it so the synthetic overrides are used.
        with patch(
            _GET_ANIMAL_PATCH, return_value=_make_animal_info(),
        ), patch(
            _PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline,
        ), patch(
            "stroke_orofacial.spout_behavior.session_processing.load_defaults",
            return_value=minimal_defaults,
        ), patch(
            "stroke_orofacial.spout_behavior.session_processing.load_session_overrides",
            return_value=overrides,
        ):
            results = process_animal(
                "PS99",
                [datetime.date(2025, 1, 1), datetime.date(2025, 2, 2)],
                resolver,
                overwrite="force",
            )

        assert len(results) == 2
        # First date (Pattern B) — two suffixes
        assert set(results[0].keys()) == {None, "b"}
        # Second date (vanilla) — one suffix
        assert set(results[1].keys()) == {None}


# ---------- Provenance carries suffix ----------


class TestSuffixProvenance:
    def test_pattern_b_session_id_in_provenance_carries_suffix(
        self, setup_pattern_b_layout, minimal_defaults,
    ):
        """Both halves emit a per-session params.json; the b half's
        params dict has session_id ending in 'b'. Regression guard for
        Task 3d (manifest.session_id reads through to provenance)."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        fx = setup_pattern_b_layout
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(_PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline):
            process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                overwrite="force",
                defaults=minimal_defaults,
                overrides_config=fx["overrides_config"],
            )

        # Per-suffix params JSON paths land in
        # outputs/spout_behavior/params/PS99/{date_str}{suffix}.json
        params_dir = (
            fx["outputs_root"] / "spout_behavior" / "params" / "PS99"
        )
        bare_params = params_dir / "20250101.json"
        b_params = params_dir / "20250101b.json"
        assert bare_params.exists()
        assert b_params.exists()

        bare_rec = json.loads(bare_params.read_text())
        b_rec = json.loads(b_params.read_text())
        assert bare_rec["session_id"] == "PS99_20250101"
        assert b_rec["session_id"] == "PS99_20250101b"


# ---------- Lazy-load overrides_config ----------


class TestLazyOverridesLoad:
    def test_overrides_config_lazy_loaded_when_none(
        self, setup_pattern_b_layout, minimal_defaults,
    ):
        """When overrides_config kwarg is None, the function should call
        load_session_overrides() under the hood. Mirrors build_manifest's
        lazy-load pattern so callers can use process_session_by_animal_date
        as a one-shot entry point without pre-loading the YAML."""
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        fx = setup_pattern_b_layout
        with patch(
            _GET_ANIMAL_PATCH, return_value=fx["animal_info"],
        ), patch(
            _PIPELINE_PATCH, side_effect=_fake_run_phase2_pipeline,
        ), patch(
            "stroke_orofacial.spout_behavior.session_processing.load_session_overrides",
            return_value=fx["overrides_config"],
        ) as mock_load:
            result = process_session_by_animal_date(
                "PS99", datetime.date(2025, 1, 1), fx["resolver"],
                overwrite="force",
                defaults=minimal_defaults,
                # overrides_config NOT passed — should trigger lazy-load
            )

        mock_load.assert_called_once()
        # And the loaded config drove Pattern B detection
        assert set(result.keys()) == {None, "b"}
