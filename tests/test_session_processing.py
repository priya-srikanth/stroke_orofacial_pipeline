"""Tests for stroke_orofacial.spout_behavior.session_processing."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.session_processing import (
    _params_json_path,
    _save_session_params,
)


def _assert_bool_near_equal(
    actual: np.ndarray,
    desired: np.ndarray,
    max_frac: float,
    err_msg: str = "",
) -> None:
    """Assert two bool arrays agree except for up to ``max_frac`` mismatched samples.

    See the identical helper in tests/test_bouts.py for rationale.
    """
    actual = np.asarray(actual, dtype=bool)
    desired = np.asarray(desired, dtype=bool)
    assert actual.shape == desired.shape, (
        f"{err_msg}: shape mismatch {actual.shape} vs {desired.shape}"
    )
    n_mismatch = int(np.count_nonzero(actual != desired))
    max_allowed = int(np.ceil(max_frac * actual.size))
    if n_mismatch > max_allowed:
        raise AssertionError(
            f"{err_msg}: {n_mismatch} mismatched samples exceeds tolerance "
            f"{max_allowed} ({max_frac:.0e} of {actual.size})"
        )


class TestParamsJsonPath:
    def test_path_structure(self, tmp_path):
        result = _params_json_path(tmp_path, "PS46", "20250307")
        assert result == tmp_path / "params" / "PS46" / "20250307.json"


class TestProcessSessionRaisesOnMissingWavesurfer:
    """Pure-unit-level guard: process_session must raise a clear error when
    the manifest has no wavesurfer file (regardless of whether real data is
    mounted)."""

    def test_raises_when_wavesurfer_file_is_none(self, tmp_path):
        from unittest.mock import MagicMock

        from stroke_orofacial.config_loader import (
            load_defaults,
            load_session_overrides,
        )
        from stroke_orofacial.manifest import SessionManifest
        from stroke_orofacial.paths import PathResolver
        from stroke_orofacial.spout_behavior.session_processing import process_session

        # Mock resolver: pipeline_outputs returns an empty tmp dir so that
        # _check_overwrite sees no existing outputs and proceeds to the
        # wavesurfer-load step (which is where the FileNotFoundError fires).
        resolver = MagicMock(spec=PathResolver)
        resolver.pipeline_outputs.return_value = tmp_path

        # Empty dlc_h5_files / dlc_csv_files (defaults) intentionally:
        # process_session must NOT check DLC fields — Phase 2 is DLC-free
        # by design. The error must originate from the missing wavesurfer
        # file, not from the missing DLC files.
        manifest = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
            wavesurfer_file=None,
        )
        with pytest.raises(FileNotFoundError, match="wavesurfer"):
            process_session(
                manifest, resolver, overwrite="force",
                defaults=load_defaults(),
                overrides_config=load_session_overrides(),
            )


class TestSaveSessionParams:
    def test_writes_json_with_all_fields(self, tmp_path):
        params = {
            "process_treadmill_signal": {"offset_in_volts": 1.259},
            "find_running_bouts": {"thresh_speed": 5},
            "find_licks_and_rewards": {"lick_detection": {"thresh_upper": 2.5}},
            "find_grooming_bouts": {"duration_maxThresh_long": 0.4},
            "find_quiet_bouts": {"speed_threshold": 1},
            "find_peri_reward_periods": {"window_around_reward": [0, 6]},
            "unrelated_key": "should be excluded",
        }
        log = [{"action": "skipped", "type": "running_bouts", "path": "/some/path"}]

        path = _save_session_params(
            tmp_path, "PS46", datetime.date(2025, 3, 7), "20250307",
            params, log, skipped=False,
        )

        assert path.exists()
        with open(path) as f:
            record = json.load(f)

        assert record["session_id"] == "PS46_20250307"
        assert record["animal"] == "PS46"
        assert record["date"] == "2025-03-07"
        assert "run_timestamp" in record
        assert record["skipped"] is False
        assert "process_treadmill_signal" in record["params"]
        assert "find_running_bouts" in record["params"]
        # Unrelated keys excluded
        assert "unrelated_key" not in record["params"]
        assert record["processing_log"] == log

    def test_writes_on_skip(self, tmp_path):
        params = {
            "process_treadmill_signal": {"offset_in_volts": 1.259},
            "find_running_bouts": {},
            "find_licks_and_rewards": {},
            "find_grooming_bouts": {},
            "find_quiet_bouts": {},
            "find_peri_reward_periods": {},
        }
        log = [
            {"action": "skipped", "type": t, "path": f"/some/{t}.npz"}
            for t in [
                "wavesurfer_signals_processed", "treadmill_signals_preprocessed",
                "licks_and_rewards", "running_bouts", "grooming_bouts",
                "quiet_bouts", "peri_reward_periods",
            ]
        ]

        path = _save_session_params(
            tmp_path, "PS46", datetime.date(2025, 3, 7), "20250307",
            params, log, skipped=True,
        )

        with open(path) as f:
            record = json.load(f)

        assert record["skipped"] is True
        assert len(record["processing_log"]) == 7

    def test_per_session_path_layout(self, tmp_path):
        """params.json goes to params/{animal}/{date}.json, not root."""
        params = {
            "process_treadmill_signal": {},
            "find_running_bouts": {},
            "find_licks_and_rewards": {},
            "find_grooming_bouts": {},
            "find_quiet_bouts": {},
            "find_peri_reward_periods": {},
        }
        path = _save_session_params(
            tmp_path, "PS51", datetime.date(2025, 4, 25), "20250425",
            params, [], skipped=False,
        )
        assert path == tmp_path / "params" / "PS51" / "20250425.json"
        assert path.exists()


# ---- Integration: parity check on MICROSCOPE outputs ----

_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)
_SP3 = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3"
)
_V2 = Path(
    "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/spout_behavior"
)


_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists() or not _MOUNT.exists(),
    reason="Wavesurfer data or MICROSCOPE mount not available",
)
class TestIntegrationProcessSession:
    """Run process_session via the by_animal_date wrapper on real data and
    verify params.json provenance.

    The wrapper builds a SessionManifest internally; the primary
    ``process_session(manifest, resolver, ...)`` API is exercised separately
    in ``TestIntegrationProcessSessionWithManifest`` below.
    """

    def test_process_and_params_json_written(self, monkeypatch):
        """process_session_by_animal_date writes per-session params.json with skipped=False."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.paths import PathResolver
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        resolver = PathResolver()
        date = datetime.date(2025, 3, 7)
        result = process_session_by_animal_date("PS46", date, resolver, overwrite="force")

        # Should have returned paths for all 7 output types
        assert len(result) == 7

        # Per-session params.json should exist
        params_path = _V2 / "params" / "PS46" / "20250307.json"
        assert params_path.exists()
        with open(params_path) as f:
            record = json.load(f)
        assert record["session_id"] == "PS46_20250307"
        assert record["skipped"] is False
        assert "run_timestamp" in record
        assert "process_treadmill_signal" in record["params"]

    def test_skip_path_writes_params_json(self, monkeypatch):
        """When overwrite='skip' and outputs exist, params.json is still written."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.paths import PathResolver
        from stroke_orofacial.spout_behavior.session_processing import (
            process_session_by_animal_date,
        )

        resolver = PathResolver()
        date = datetime.date(2025, 3, 7)

        # First run ensures outputs exist (force)
        process_session_by_animal_date("PS46", date, resolver, overwrite="force")

        # Second run with skip — should return empty dict but write params.json
        result = process_session_by_animal_date("PS46", date, resolver, overwrite="skip")
        assert result == {}

        params_path = _V2 / "params" / "PS46" / "20250307.json"
        assert params_path.exists()
        with open(params_path) as f:
            record = json.load(f)
        assert record["skipped"] is True
        assert len(record["processing_log"]) == 7
        assert all(e["action"] == "skipped" for e in record["processing_log"])


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists() or not _MOUNT.exists(),
    reason="Wavesurfer data or MICROSCOPE mount not available",
)
class TestIntegrationProcessSessionWithManifest:
    """Exercise the manifest-first primary signature of process_session.

    The notebook orchestrator pattern (build manifest in a visible cell,
    pass to process_session) is the canonical entry point post-Phase-6.7.
    These tests verify the manifest-first path on real data.
    """

    def test_process_session_with_manifest(self, monkeypatch):
        """Build manifest explicitly, pass to process_session(manifest, ...)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver
        from stroke_orofacial.spout_behavior.session_processing import process_session

        resolver = PathResolver()
        date = datetime.date(2025, 3, 7)
        animal_info = get_animal("PS46")
        manifest = build_manifest("PS46", date, resolver, animal_info)

        # Manifest must have wavesurfer_file populated for process_session.
        assert manifest.wavesurfer_file is not None, (
            "build_manifest did not locate the wavesurfer .h5"
        )
        assert manifest.animal == "PS46"
        assert manifest.date == date

        result = process_session(manifest, resolver, overwrite="force")
        assert len(result) == 7

    def test_process_session_succeeds_with_empty_dlc(self, monkeypatch):
        """Phase 2 is DLC-free: manifest with empty dlc_h5_files still
        processes successfully (sessions where DLC inference hasn't run
        yet, or where video failed but wavesurfer is clean)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver
        from stroke_orofacial.spout_behavior.session_processing import process_session

        resolver = PathResolver()
        date = datetime.date(2025, 3, 7)
        animal_info = get_animal("PS46")
        manifest = build_manifest("PS46", date, resolver, animal_info)

        # Synthesize the DLC-less case by clearing the discovered DLC fields.
        # Wavesurfer must still be present (Phase 2 requires it).
        manifest.dlc_h5_files = []
        manifest.dlc_csv_files = []
        assert manifest.wavesurfer_file is not None

        result = process_session(manifest, resolver, overwrite="force")
        assert len(result) == 7



@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists() or not _MOUNT.exists(),
    reason="Wavesurfer data or MICROSCOPE mount not available",
)
class TestIntegrationNewKeys:
    """Verify Phase 2.5 additive keys are present in stroke_orofacial_pipeline_outputs."""

    def test_tone_indices_in_licks_and_rewards(self):
        lr = dict(np.load(
            _V2 / "licks_and_rewards" / "PS46" / "20250307.npz", allow_pickle=True
        ))
        assert "Tone_L" in lr
        assert "Tone_R" in lr
        assert lr["Tone_L"].size > 0  # tones should be detected

    def test_per_side_masks_in_peri_reward_periods(self):
        peri = dict(np.load(
            _V2 / "peri_reward_periods" / "PS46" / "20250307.npz", allow_pickle=True
        ))
        for key in ("peri_reward_L", "peri_reward_R", "peri_tone_L", "peri_tone_R"):
            assert key in peri, f"Missing {key}"
            assert peri[key].dtype == bool
            assert peri[key].shape[0] > 0
        # Consolidated peri_reward_bool still present
        assert "peri_reward_bool" in peri


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists()
    or not (_SP3 / "licks_and_rewards" / "PS46" / "20250307.npz").exists(),
    reason="Wavesurfer data or session_processing3 not available",
)
class TestIntegrationParity:
    """Verify stroke_orofacial_pipeline_outputs matches session_processing3 exactly."""

    # Method tags:
    #   "equal"          — np.testing.assert_array_equal (strict byte match).
    #   "allclose"       — np.testing.assert_allclose at rtol/atol=1e-10.
    #   "bool_near_equal" — allow a bounded mismatch fraction on bool arrays
    #                       produced by code paths that call the vendored
    #                       widen_bool_sparse / set_short_bool_to_low helpers.
    #                       Those helpers intentionally diverge from upstream
    #                       bnpm 0.6.0 to fix two upstream bugs; the drift vs.
    #                       the frozen session_processing3 baseline on
    #                       PS46/20250307 is 2 samples (lick_bool_bad) and
    #                       51 samples (quiet_bool), max_frac=1e-4 cap gives
    #                       ~7x headroom. This is NOT LAPACK jitter — the
    #                       unrelated rtol change in tests/test_timebase.py
    #                       is the polyfit/interp1d LAPACK drift mitigation.
    #                       See docs/DECISIONS.md "2026-04-20 Phase 13 vendor
    #                       bnpm" and docs/MIGRATION_LOG.md Phase 13b for the
    #                       full rationale.
    CHECKS = {
        "treadmill_signals_preprocessed": [("Treadmill_smoothed", "allclose")],
        "licks_and_rewards": [
            ("Lick_L", "equal"), ("Lick_R", "equal"),
            ("Reward_L", "equal"), ("Reward_R", "equal"),
            ("Fs", "equal"), ("n_samples", "equal"),
        ],
        "running_bouts": [("running_bouts", "equal")],
        "grooming_bouts": [("lick_bool_bad", "bool_near_equal")],
        "quiet_bouts": [("quiet_bool", "bool_near_equal")],
        "peri_reward_periods": [("peri_reward_bool", "bool_near_equal")],
    }

    @pytest.mark.parametrize("date_str", ["20250307", "20250320"])
    def test_parity(self, date_str):
        for output_type, arrays in self.CHECKS.items():
            ref_path = _SP3 / output_type / "PS46" / f"{date_str}.npz"
            new_path = _V2 / output_type / "PS46" / f"{date_str}.npz"

            if not ref_path.exists():
                pytest.skip(f"Reference {ref_path} not found")
            if not new_path.exists():
                pytest.fail(f"New output {new_path} not found — run process_session first")

            ref = dict(np.load(ref_path, allow_pickle=True))
            new = dict(np.load(new_path, allow_pickle=True))

            # Un-flip post-task-#17 mouse-frame labels back to wavesurfer
            # frame before comparing to the frozen session_processing3
            # baseline (which is wavesurfer-frame). Internal array values
            # are byte-identical; only the L/R key names differ.
            new = _unflip_new_to_wavesurfer_frame(new)

            for arr_name, method in arrays:
                r, n = ref[arr_name], new[arr_name]
                if method == "equal":
                    np.testing.assert_array_equal(
                        r, n, err_msg=f"{output_type}/{arr_name} on {date_str}"
                    )
                elif method == "allclose":
                    np.testing.assert_allclose(
                        r, n, rtol=1e-10, atol=1e-10,
                        err_msg=f"{output_type}/{arr_name} on {date_str}",
                    )
                elif method == "bool_near_equal":
                    _assert_bool_near_equal(
                        n, r, max_frac=1e-4,
                        err_msg=f"{output_type}/{arr_name} on {date_str}",
                    )


class TestSideConventionAtEmit:
    """Regression guards for the task-#17 boundary-layer translation.

    Exercises :func:`_translate_side_keys` and
    :func:`_save_npz_with_side_convention` from
    :mod:`stroke_orofacial.spout_behavior.session_processing` directly
    — avoids needing a real wavesurfer session on disk and keeps the
    guard focused on the exact behaviors commit 3 introduces.
    """

    def test_translate_side_keys_no_op_when_matched(self):
        from stroke_orofacial.spout_behavior.session_processing import (
            _translate_side_keys,
        )
        payload = {"Lick_L": [1, 2], "Lick_R": [3, 4], "Fs": 1000}
        out = _translate_side_keys(payload, wavesurfer_matches=True)
        assert out == payload
        assert out is not payload  # defensive copy

    def test_translate_side_keys_swaps_L_and_R_when_mirrored(self):
        from stroke_orofacial.spout_behavior.session_processing import (
            _translate_side_keys,
        )
        payload = {
            "Lick_L": np.array([1, 2]),
            "Lick_R": np.array([3, 4]),
            "Reward_L": np.array([10]),
            "Reward_R": np.array([20]),
            "Fs": 1000,
        }
        out = _translate_side_keys(payload, wavesurfer_matches=False)
        # Keys with _L/_R suffix flipped; value arrays pass through.
        np.testing.assert_array_equal(out["Lick_R"], payload["Lick_L"])
        np.testing.assert_array_equal(out["Lick_L"], payload["Lick_R"])
        np.testing.assert_array_equal(out["Reward_R"], payload["Reward_L"])
        np.testing.assert_array_equal(out["Reward_L"], payload["Reward_R"])
        # Non-suffixed keys pass through unchanged.
        assert out["Fs"] == 1000

    def test_translate_side_keys_preserves_non_LR_keys(self):
        from stroke_orofacial.spout_behavior.session_processing import (
            _translate_side_keys,
        )
        payload = {"xedges": np.arange(5), "nbins": 100, "Fs": 1000}
        out = _translate_side_keys(payload, wavesurfer_matches=False)
        assert out == payload

    @pytest.mark.parametrize("ws_match", [True, False])
    def test_save_npz_stamps_convention_scalars(self, tmp_path, ws_match):
        """Every NPZ written via the task-#17 wrapper carries the two
        convention scalars, regardless of whether L/R translation fired."""
        from stroke_orofacial.lr_convention import (
            SIDE_CONVENTION_MATCH_KEY,
            SIDE_CONVENTION_VERSION,
            SIDE_CONVENTION_VERSION_KEY,
        )
        from stroke_orofacial.spout_behavior.session_processing import (
            _save_npz_with_side_convention,
        )
        path = tmp_path / "out.npz"
        _save_npz_with_side_convention(
            path,
            {"Lick_L": np.array([1]), "Lick_R": np.array([2])},
            ws_match,
            has_side_keys=True,
        )
        loaded = dict(np.load(path, allow_pickle=True))
        assert SIDE_CONVENTION_MATCH_KEY in loaded
        assert SIDE_CONVENTION_VERSION_KEY in loaded
        assert bool(loaded[SIDE_CONVENTION_MATCH_KEY]) is ws_match
        assert int(loaded[SIDE_CONVENTION_VERSION_KEY]) == SIDE_CONVENTION_VERSION

    def test_save_npz_flipped_cohort_emits_mouse_frame_labels(self, tmp_path):
        """On a flipped cohort (ws_match=False), wavesurfer-L lick indices
        are emitted under the 'Lick_R' key (mouse-R = wavesurfer-L on
        the mirrored rig) and vice versa — the foundational invariant
        task #17 establishes."""
        from stroke_orofacial.spout_behavior.session_processing import (
            _save_npz_with_side_convention,
        )
        ws_lick_L = np.array([100, 200, 300])  # wavesurfer-L indices
        ws_lick_R = np.array([150, 250])  # wavesurfer-R indices
        path = tmp_path / "out.npz"
        _save_npz_with_side_convention(
            path,
            {"Lick_L": ws_lick_L, "Lick_R": ws_lick_R},
            wavesurfer_matches=False,
            has_side_keys=True,
        )
        loaded = dict(np.load(path, allow_pickle=True))
        # Mouse-frame "Lick_L" contains what was wavesurfer-R indices.
        np.testing.assert_array_equal(loaded["Lick_L"], ws_lick_R)
        np.testing.assert_array_equal(loaded["Lick_R"], ws_lick_L)

    def test_save_npz_matched_cohort_no_flip(self, tmp_path):
        """On a matched cohort (ws_match=True), labels pass through
        unchanged — the translation is a strict no-op."""
        from stroke_orofacial.spout_behavior.session_processing import (
            _save_npz_with_side_convention,
        )
        ws_lick_L = np.array([100, 200, 300])
        ws_lick_R = np.array([150, 250])
        path = tmp_path / "out.npz"
        _save_npz_with_side_convention(
            path,
            {"Lick_L": ws_lick_L, "Lick_R": ws_lick_R},
            wavesurfer_matches=True,
            has_side_keys=True,
        )
        loaded = dict(np.load(path, allow_pickle=True))
        np.testing.assert_array_equal(loaded["Lick_L"], ws_lick_L)
        np.testing.assert_array_equal(loaded["Lick_R"], ws_lick_R)


def _unflip_new_to_wavesurfer_frame(
    new_payload: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Translate a post-task-#17 mouse-frame NPZ payload back to wavesurfer frame.

    Task #17 (2026-04-20) moved output-NPZ L/R labels from wavesurfer
    frame to mouse frame via boundary-layer translation at emit time.
    The frozen ``session_processing3`` baseline predates task #17 and
    is wavesurfer-frame, so integration-parity tests need to un-flip
    the new emitter's output before comparing.

    The NPZ's own ``wavesurfer_sides_match_mouse_sides`` scalar drives
    the un-flip: if True (matched rig, no translation at emit) the
    payload is returned unchanged; if False (mirrored rig, L↔R swapped
    at emit) keys ending in ``_L`` / ``_R`` are swapped back. The
    ``side_convention_version`` / ``wavesurfer_sides_match_mouse_sides``
    scalars themselves are dropped from the returned dict so downstream
    ``ref[key]`` lookups don't see them.

    This helper is test-side only; production code should never un-flip
    — the emitted mouse-frame labels are the canonical artifact contract.
    """
    from stroke_orofacial.lr_convention import (
        SIDE_CONVENTION_MATCH_KEY,
        SIDE_CONVENTION_VERSION_KEY,
    )

    flag = new_payload.get(SIDE_CONVENTION_MATCH_KEY)
    if flag is None:
        # NPZ predates task #17. Pass through unchanged.
        return new_payload
    flag = bool(flag)  # numpy 0-d bool array → Python bool

    out: dict[str, np.ndarray] = {}
    for key, value in new_payload.items():
        if key in (SIDE_CONVENTION_MATCH_KEY, SIDE_CONVENTION_VERSION_KEY):
            continue
        if flag:
            out[key] = value
            continue
        if key.endswith("_L"):
            out[key[:-2] + "_R"] = value
        elif key.endswith("_R"):
            out[key[:-2] + "_L"] = value
        else:
            out[key] = value
    return out
