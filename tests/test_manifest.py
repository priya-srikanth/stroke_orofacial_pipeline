"""Tests for stroke_orofacial.manifest."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stroke_orofacial.animals import AnimalInfo, Exclusion, EpochBoundaries
from stroke_orofacial.manifest import (
    SessionManifest,
    build_manifest,
    _discover_dlc_files,
)
from stroke_orofacial.paths import PathResolver


@pytest.fixture()
def mock_dlc_dir(tmp_path: Path) -> Path:
    """Create a fake DLC directory with files for 2025-03-07."""
    dlc_dir = tmp_path / "PS46"
    dlc_dir.mkdir()
    # Create filtered DLC files matching the real naming pattern
    base = "video2_2025-03-07T12_11_32DLC_Resnet50_video2Jan26shuffle5_snapshot_060"
    (dlc_dir / f"{base}_filtered.h5").touch()
    (dlc_dir / f"{base}_filtered.csv").touch()
    # Also create unfiltered files (should not be picked up)
    (dlc_dir / f"{base}.h5").touch()
    (dlc_dir / f"{base}.csv").touch()
    return dlc_dir


@pytest.fixture()
def mock_alignment_dir(tmp_path: Path) -> Path:
    """Create a fake alignment template directory."""
    tmpl_dir = tmp_path / "alignment_templates" / "cam2" / "PS46"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "20250307.npz").touch()
    return tmp_path / "alignment_templates"


@pytest.fixture()
def ps46_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS46",
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
        epoch_boundaries=EpochBoundaries(1, 4, 5),
    )


@pytest.fixture()
def mock_resolver(tmp_path, mock_dlc_dir, mock_alignment_dir) -> MagicMock:
    """Create a mock PathResolver that points to tmp_path fixtures."""
    resolver = MagicMock(spec=PathResolver)
    resolver.dlc_output_dir.return_value = mock_dlc_dir
    # Phase 7-pre-alignment-templates Task 4 cutover: build_manifest now
    # calls alignment_template_for_reading (prefer-new-then-legacy);
    # mock that method on the resolver. The fixture file exists (per
    # mock_alignment_dir fixture), so the mock returns the path — same
    # as the pre-cutover behavior would have produced for an existing
    # legacy file.
    resolver.alignment_template_for_reading.return_value = (
        mock_alignment_dir / "cam2" / "PS46" / "20250307.npz"
    )
    return resolver


class TestDiscoverDlcFiles:
    def test_finds_filtered_files(self, mock_dlc_dir):
        h5s, csvs = _discover_dlc_files(mock_dlc_dir, datetime.date(2025, 3, 7))
        assert len(h5s) == 1
        assert len(csvs) == 1
        assert "_filtered.h5" in h5s[0].name
        assert "_filtered.csv" in csvs[0].name

    def test_no_files_for_missing_date(self, mock_dlc_dir):
        h5s, csvs = _discover_dlc_files(mock_dlc_dir, datetime.date(2025, 1, 1))
        assert h5s == []
        assert csvs == []


class TestBuildManifest:
    def test_basic_manifest(self, mock_resolver, ps46_info):
        manifest = build_manifest(
            "PS46",
            datetime.date(2025, 3, 7),
            mock_resolver,
            ps46_info,
        )
        assert manifest.session_id == "PS46_20250307"
        assert manifest.animal == "PS46"
        assert manifest.date == datetime.date(2025, 3, 7)
        assert manifest.day_relative_to_stroke == -6
        assert manifest.phase == "baseline"
        assert len(manifest.dlc_h5_files) == 1
        assert len(manifest.dlc_csv_files) == 1
        assert manifest.alignment_template is not None
        assert manifest.excluded is False
        assert manifest.wavesurfer_file is None
        assert manifest.video_files == []

    def test_post_stroke_phase(self, mock_resolver, tmp_path):
        """A date after stroke should have phase='post_stroke'."""
        # Create DLC files for 2025-03-20
        dlc_dir = mock_resolver.dlc_output_dir.return_value
        base = "video2_2025-03-20T10_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060"
        (dlc_dir / f"{base}_filtered.h5").touch()
        (dlc_dir / f"{base}_filtered.csv").touch()
        # Point alignment template to a non-existent file
        # Post-cutover: alignment_template_for_reading raises FileNotFoundError
        # when neither tree has the template; build_manifest catches and
        # sets alignment_template=None. Mock the raise to model that.
        mock_resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
            "test fixture: no alignment template for this (animal, date)"
        )

        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        manifest = build_manifest("PS46", datetime.date(2025, 3, 20), mock_resolver, info)
        assert manifest.phase == "post_stroke"
        assert manifest.day_relative_to_stroke == 7
        assert manifest.alignment_template is None  # non-existent

    def test_excluded_session_top_level_scope(self, mock_resolver):
        """An exclusion scoped to [dlc, spout_behavior] fires for any
        analysis_context under either of those namespaces."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 3, 7),
                    "bad frames",
                    ["dlc", "spout_behavior"],
                ),
            ],
        )
        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.spatial",
        )
        assert manifest.excluded is True
        assert manifest.exclusion_reason == "bad frames"

    def test_analysis_specific_exclusion(self, mock_resolver):
        """Bodypart-scoped exclusion: prefix-match means
        [dlc.kinematics.tongue] hits dlc.kinematics.tongue but not
        dlc.kinematics.jaw."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 3, 7),
                    "tongue issue",
                    ["dlc.kinematics.tongue"],
                ),
            ],
        )
        # Excluded for tongue kinematics
        m = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.kinematics.tongue",
        )
        assert m.excluded is True
        # Not excluded for jaw kinematics
        m = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.kinematics.jaw",
        )
        assert m.excluded is False

    def test_missing_dlc_dir_yields_empty_lists(self, ps46_info, tmp_path):
        """When DLC dir is missing, build_manifest emits a manifest with
        empty dlc_h5_files / dlc_csv_files (no raise).

        DLC is symmetric with wavesurfer/video: discoverable-if-present,
        empty-if-not. The "I need DLC" assertion belongs to each
        DLC-consuming orchestrator, not to manifest construction.
        """
        resolver = MagicMock(spec=PathResolver)
        resolver.dlc_output_dir.return_value = Path("/nonexistent/path")
        # Alignment template path is constructed but won't exist
        # Post-cutover: alignment_template_for_reading raises when neither
        # tree has the template (vs the pre-cutover legacy resolver which
        # returned a non-existent path that build_manifest then existence-
        # checked).
        resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
            "test fixture: no alignment template for this (animal, date)"
        )

        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), resolver, ps46_info
        )
        assert manifest.session_id == "PS46_20250307"
        assert manifest.animal == "PS46"
        assert manifest.dlc_h5_files == []
        assert manifest.dlc_csv_files == []
        assert manifest.alignment_template is None

    def test_no_dlc_files_yields_empty_lists(self, mock_resolver, ps46_info):
        """When DLC dir exists but no filtered files match the date,
        build_manifest emits empty lists (no raise)."""
        # Date with no matching files in mock_dlc_dir
        manifest = build_manifest(
            "PS46", datetime.date(2025, 1, 1), mock_resolver, ps46_info,
        )
        assert manifest.session_id == "PS46_20250101"
        assert manifest.dlc_h5_files == []
        assert manifest.dlc_csv_files == []


# ---- Phase 7-pre-secondary-spout Task 3b: build_manifest session_suffix ----


def _ps51_info() -> AnimalInfo:
    """PS51 metadata fixture. Stroke date 2025-04-29 (per
    batch_process_behavior_report_20260116PS d0); session window
    matches the legacy notebook."""
    return AnimalInfo(
        animal_id="PS51",
        stroke_date=datetime.date(2025, 4, 30),
        session_start=datetime.date(2025, 4, 16),
        session_end=datetime.date(2025, 7, 9),
        epoch_boundaries=EpochBoundaries(1, 4, 5),
    )


def _ps55_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS55",
        stroke_date=datetime.date(2025, 5, 1),
        session_start=datetime.date(2025, 4, 16),
        session_end=datetime.date(2025, 7, 9),
        epoch_boundaries=EpochBoundaries(1, 4, 5),
    )


def _ps48_info() -> AnimalInfo:
    """PS48 fixture (Pattern A multi-half session)."""
    return AnimalInfo(
        animal_id="PS48",
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
        epoch_boundaries=EpochBoundaries(1, 4, 5),
    )


def _mock_resolver_for_pattern_b(tmp_path: Path) -> MagicMock:
    """PathResolver mock that returns non-existent ws/cam dirs (so
    discovery skips cleanly) but records the call args for assertion.
    Mirrors the mock_resolver fixture pattern but without DLC + alignment
    set up — Pattern B tests don't need those."""
    resolver = MagicMock(spec=PathResolver)
    resolver.dlc_output_dir.return_value = tmp_path / "no_dlc_dir"
    # Post-cutover (Phase 7-pre-alignment-templates Task 4): mock the
    # for_reading method to raise (mimics "neither tree has template").
    resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
        "test fixture: no alignment template for Pattern B test"
    )
    resolver.wavesurfer_dir.return_value = tmp_path / "no_ws_dir"
    resolver.camera_dir.return_value = tmp_path / "no_cam_dir"
    return resolver


class TestBuildManifestSessionSuffix:
    """build_manifest's session_suffix kwarg + Pattern-B override
    consumption + Pattern-B branch in MultiHalfNotDeclaredError.

    Uses synthetic overrides_config dicts so the tests don't depend
    on configs/session_overrides.yaml. Resolver is mocked to return
    non-existent dirs (discovery skips cleanly); call-arg spies
    verify the subdir_override kwarg was threaded correctly.
    """

    def test_session_suffix_threads_through_to_session_id(self, tmp_path):
        """session_suffix='b' → session_id ends in 'b'."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS51": {"2025-04-30": {}},
            },
        }
        manifest = build_manifest(
            "PS51", datetime.date(2025, 4, 30), resolver, _ps51_info(),
            overrides_config=overrides, session_suffix="b",
        )
        assert manifest.session_id == "PS51_20250430b"
        assert manifest.session_suffix == "b"

    def test_pattern_b_bare_uses_override_when_present(self, tmp_path):
        """PS55/2025-04-24 with bare_ws_subdir_override='20250424a' →
        wavesurfer_dir called with subdir_override='20250424a'."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS55": {
                    "2025-04-24": {
                        "bare_ws_subdir_override": "20250424a",
                    },
                },
            },
        }
        build_manifest(
            "PS55", datetime.date(2025, 4, 24), resolver, _ps55_info(),
            overrides_config=overrides, session_suffix=None,
        )
        # Spy: wavesurfer_dir should have been called with the override
        kwargs = resolver.wavesurfer_dir.call_args.kwargs
        assert kwargs.get("subdir_override") == "20250424a"
        # cam_dir has no override → None (resolver uses date_str)
        cam_kwargs = resolver.camera_dir.call_args.kwargs
        assert cam_kwargs.get("subdir_override") is None

    def test_pattern_b_bare_no_override_uses_date_str(self, tmp_path):
        """Pattern B bare half without overrides → resolver called with
        subdir_override=None (resolver falls back to date_str)."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS51": {"2025-04-30": {}},
            },
        }
        build_manifest(
            "PS51", datetime.date(2025, 4, 30), resolver, _ps51_info(),
            overrides_config=overrides, session_suffix=None,
        )
        # Spy: no override passed → resolver falls back to date_str
        assert resolver.wavesurfer_dir.call_args.kwargs.get(
            "subdir_override"
        ) is None
        assert resolver.camera_dir.call_args.kwargs.get(
            "subdir_override"
        ) is None

    def test_pattern_b_b_half_uses_override_when_present(self, tmp_path):
        """Pattern B b-half with b_ws_subdir_override='customb' →
        wavesurfer_dir called with subdir_override='customb'."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS55": {
                    "2025-04-24": {
                        "b_ws_subdir_override": "20250424b_custom",
                    },
                },
            },
        }
        build_manifest(
            "PS55", datetime.date(2025, 4, 24), resolver, _ps55_info(),
            overrides_config=overrides, session_suffix="b",
        )
        assert resolver.wavesurfer_dir.call_args.kwargs.get(
            "subdir_override"
        ) == "20250424b_custom"

    def test_pattern_b_b_half_no_override_uses_date_b(self, tmp_path):
        """Pattern B b-half without override → resolver called with
        subdir_override='{date_str}b' (the locked default convention)."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS51": {"2025-04-30": {}},
            },
        }
        build_manifest(
            "PS51", datetime.date(2025, 4, 30), resolver, _ps51_info(),
            overrides_config=overrides, session_suffix="b",
        )
        assert resolver.wavesurfer_dir.call_args.kwargs.get(
            "subdir_override"
        ) == "20250430b"
        assert resolver.camera_dir.call_args.kwargs.get(
            "subdir_override"
        ) == "20250430b"

    def test_non_pattern_b_unchanged_behavior(
        self, mock_resolver, ps46_info,
    ):
        """Regression guard: a non-Pattern-B session passes
        subdir_override=None to the resolver. Verifies the
        existing single-half code path is byte-identical to pre-PR."""
        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, ps46_info,
            overrides_config={},
        )
        assert manifest.session_id == "PS46_20250307"
        assert manifest.session_suffix is None
        # wavesurfer_dir called with no override (resolver uses date_str)
        ws_kwargs = mock_resolver.wavesurfer_dir.call_args.kwargs
        assert ws_kwargs.get("subdir_override") is None

    def test_session_suffix_without_registry_entry_raises(
        self, tmp_path,
    ):
        """Passing session_suffix='b' for an (animal, date) NOT in
        secondary_spout_sessions: raises ValueError. The suffix only
        has a defined meaning under registry coverage."""
        resolver = _mock_resolver_for_pattern_b(tmp_path)
        with pytest.raises(ValueError, match="NOT registered"):
            build_manifest(
                "PS46", datetime.date(2025, 3, 7), resolver,
                AnimalInfo(
                    animal_id="PS46",
                    stroke_date=datetime.date(2025, 3, 13),
                    session_start=datetime.date(2025, 3, 7),
                    session_end=datetime.date(2025, 4, 6),
                    epoch_boundaries=EpochBoundaries(1, 4, 5),
                ),
                overrides_config={}, session_suffix="b",
            )

    def test_pattern_b_in_registry_suppresses_multi_half_check(
        self, tmp_path,
    ):
        """Per DECISIONS 2026-05-12 Decision 5(c): an n_dlc>=2 signal on
        a Pattern B session does NOT trip MultiHalfNotDeclaredError —
        the registry coverage means "these halves are separate sessions,
        not merge candidates." Simulates the future state where Priya
        DLC-infers the b halves."""
        resolver = MagicMock(spec=PathResolver)
        # Synthesize a DLC dir with 2 filtered files for 2025-04-30 to
        # trigger the Pattern A signal.
        dlc_dir = tmp_path / "PS51_dlc"
        dlc_dir.mkdir()
        for ts in ("12_00_00", "13_30_00"):
            base = (
                f"video2_2025-04-30T{ts}DLC_Resnet50_video2"
                "Jan26shuffle5_snapshot_060"
            )
            (dlc_dir / f"{base}_filtered.h5").touch()
            (dlc_dir / f"{base}_filtered.csv").touch()
        resolver.dlc_output_dir.return_value = dlc_dir
        # Post-cutover: mock for_reading to raise (mimics no template).
        resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
            "test fixture: no alignment template"
        )
        resolver.wavesurfer_dir.return_value = tmp_path / "no_ws"
        resolver.camera_dir.return_value = tmp_path / "no_cam"

        overrides = {
            "secondary_spout_sessions": {
                "PS51": {"2025-04-30": {}},
            },
        }
        # No raise: Pattern B registry coverage suppresses the check.
        manifest = build_manifest(
            "PS51", datetime.date(2025, 4, 30), resolver, _ps51_info(),
            overrides_config=overrides,
        )
        # Bare manifest got built; session_suffix stays None.
        assert manifest.session_id == "PS51_20250430"
        assert manifest.session_suffix is None
        # And the n_dlc=2 DLC files DID get discovered (they exist on
        # disk in the fixture) — confirms the check didn't short-circuit
        # the discovery.
        assert len(manifest.dlc_h5_files) == 2

    def test_pattern_b_NOT_in_registry_still_raises_when_n_dlc_2(
        self, tmp_path,
    ):
        """Regression guard for the registry-gating: a session with
        n_dlc=2 and NO registry entry (neither multi_half_sessions: nor
        secondary_spout_sessions:) STILL raises MultiHalfNotDeclaredError.
        Confirms the Pattern-B branch is registry-gated, not
        blanket-disabled."""
        from stroke_orofacial.manifest import MultiHalfNotDeclaredError

        resolver = MagicMock(spec=PathResolver)
        dlc_dir = tmp_path / "PS99_dlc"
        dlc_dir.mkdir()
        for ts in ("12_00_00", "13_30_00"):
            base = (
                f"video2_2026-01-01T{ts}DLC_Resnet50_video2"
                "Jan26shuffle5_snapshot_060"
            )
            (dlc_dir / f"{base}_filtered.h5").touch()
            (dlc_dir / f"{base}_filtered.csv").touch()
        resolver.dlc_output_dir.return_value = dlc_dir
        # Post-cutover: mock for_reading to raise (mimics no template).
        resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
            "test fixture: no alignment template"
        )
        resolver.wavesurfer_dir.return_value = tmp_path / "no_ws"
        resolver.camera_dir.return_value = tmp_path / "no_cam"

        info = AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2026, 1, 1),
            session_start=datetime.date(2026, 1, 1),
            session_end=datetime.date(2026, 1, 31),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        # No registry entries → defensive check fires.
        with pytest.raises(MultiHalfNotDeclaredError):
            build_manifest(
                "PS99", datetime.date(2026, 1, 1), resolver, info,
                overrides_config={},
            )


class TestWavesurferFileOverride:
    """Phase 7-pre-alignment-templates Addendum #3 L9 — per-session
    h5-filename disambiguation via wavesurfer_file_overrides:.

    Covers the bare-half lookup path; b-half override is reserved but
    not consumed in F-P-7 (see _WAVESURFER_FILE_OVERRIDE_KEYS).
    """

    @pytest.fixture()
    def ps99_info(self) -> AnimalInfo:
        return AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2026, 1, 15),
            session_start=datetime.date(2026, 1, 1),
            session_end=datetime.date(2026, 1, 31),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )

    @pytest.fixture()
    def ambiguous_ws_dir(self, tmp_path) -> Path:
        """Create a fake WS session dir with TWO h5 files (ambiguous)."""
        ws_dir = tmp_path / "ws" / "20260105" / "PS99"
        ws_dir.mkdir(parents=True)
        (ws_dir / "stroke_0001.h5").touch()
        (ws_dir / "stroke_0002.h5").touch()
        return ws_dir

    @pytest.fixture()
    def resolver_with_ws_dir(self, ambiguous_ws_dir) -> MagicMock:
        """Mock resolver routing wavesurfer_dir to the ambiguous fixture."""
        resolver = MagicMock(spec=PathResolver)
        resolver.wavesurfer_dir.return_value = ambiguous_ws_dir
        # Pad out the resolver surface enough for build_manifest to finish
        # (camera + alignment + DLC dirs all return non-existent paths so
        # the respective discovery branches no-op).
        resolver.camera_dir.return_value = (
            ambiguous_ws_dir.parent.parent / "cam_nonexistent"
        )
        # Post-cutover: mock for_reading to raise (no template).
        resolver.alignment_template_for_reading.side_effect = FileNotFoundError(
            "test fixture: no alignment template for wavesurfer_file_overrides test"
        )
        resolver.dlc_output_dir.return_value = (
            ambiguous_ws_dir.parent.parent / "dlc_nonexistent"
        )
        return resolver

    def test_manifest_builder_honors_wavesurfer_file_override(
        self, resolver_with_ws_dir, ps99_info,
    ):
        """build_manifest looks up (animal, iso_date_str) in the new
        wavesurfer_file_overrides registry; when an entry sets
        bare_ws_h5_filename, manifest.wavesurfer_file points to that
        specific file even though the dir has multiple h5 candidates.
        """
        overrides = {
            "wavesurfer_file_overrides": {
                "PS99": {
                    "2026-01-05": {
                        "bare_ws_h5_filename": "stroke_0002.h5",
                    },
                },
            },
        }
        manifest = build_manifest(
            "PS99", datetime.date(2026, 1, 5),
            resolver_with_ws_dir, ps99_info,
            overrides_config=overrides,
        )
        assert manifest.wavesurfer_file is not None
        assert manifest.wavesurfer_file.name == "stroke_0002.h5"

    def test_manifest_builder_no_override_uses_existing_disambig(
        self, resolver_with_ws_dir, ps99_info,
    ):
        """Without a wavesurfer_file_overrides entry, find_wavesurfer_file
        raises ValueError on multiple h5s; build_manifest catches and
        sets wavesurfer_file=None. (This was the PS55/2025-06-06 pre-fix
        behavior in cohort emit.)
        """
        manifest = build_manifest(
            "PS99", datetime.date(2026, 1, 5),
            resolver_with_ws_dir, ps99_info,
            overrides_config={},
        )
        # ValueError on ambiguity was caught by build_manifest's try/except
        # → wavesurfer_file falls back to None (SKIP_NO_INPUT semantics).
        assert manifest.wavesurfer_file is None


# ---- Integration test (requires real mount) ----

_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")


@pytest.mark.skipif(
    not _MOUNT.exists(),
    reason="MICROSCOPE server not mounted",
)
class TestIntegrationManifest:
    def test_ps46_baseline_session(self, monkeypatch):
        """Build a manifest for PS46 on 2025-03-07 (baseline, day -6)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        manifest = build_manifest("PS46", datetime.date(2025, 3, 7), resolver, info)

        assert manifest.session_id == "PS46_20250307"
        assert manifest.phase == "baseline"
        assert manifest.day_relative_to_stroke == -6
        assert len(manifest.dlc_h5_files) >= 1
        assert len(manifest.dlc_csv_files) >= 1
        # All discovered files should actually exist
        for f in manifest.dlc_h5_files + manifest.dlc_csv_files:
            assert f.exists(), f"Expected {f} to exist"
        # Alignment template should exist for this date
        assert manifest.alignment_template is not None
        assert manifest.alignment_template.exists()


# ---------- Phase 7-pre-secondary-spout Task 3a: session_suffix field ----------


class TestSessionSuffixField:
    """Field-level tests for SessionManifest.session_suffix (Task 3a).

    The dataclass holds session_suffix as a passed field, not a
    computed property — the "session_id ends in suffix" contract is
    enforced at session_id-construction time (build_manifest in
    Task 3a; b-half-aware callers in Tasks 3b+). These tests pin the
    field's default behavior + that the dataclass can carry a
    suffix-aware session_id alongside its session_suffix field.
    """

    def _make_manifest(self, **overrides) -> SessionManifest:
        """Build a minimal SessionManifest with sane defaults."""
        defaults = dict(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
        )
        defaults.update(overrides)
        return SessionManifest(**defaults)

    def test_session_suffix_default_is_none(self):
        m = self._make_manifest()
        assert m.session_suffix is None

    def test_session_id_uses_session_suffix_when_set(self):
        """A synthetic Pattern B b-half manifest can carry both fields
        consistently. The dataclass doesn't enforce the relationship;
        build_manifest is responsible for emitting consistent values."""
        m = self._make_manifest(
            session_id="PS51_20250430b",
            animal="PS51",
            date=datetime.date(2025, 4, 30),
            session_suffix="b",
        )
        assert m.session_suffix == "b"
        assert m.session_id.endswith("b")
        assert m.session_id == "PS51_20250430b"

    def test_session_id_unchanged_when_session_suffix_is_none(self):
        """Regression: standard single-half + Pattern A multi-half-merged
        manifests carry session_suffix=None and session_id WITHOUT a
        suffix. This is the pre-PR shape and must remain the default."""
        m = self._make_manifest()
        assert m.session_suffix is None
        assert m.session_id == "PS46_20250307"
        assert not m.session_id.endswith("b")
