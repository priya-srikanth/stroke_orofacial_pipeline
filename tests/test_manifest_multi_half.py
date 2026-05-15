"""Phase 7-pre-multi-half tests for SessionManifest's per-half discovery.

Covers the audit-locked Pattern A scope (single session: PS48 20250314)
and the defensive check that fires on Pattern A signals when no
``multi_half_sessions:`` entry covers the (animal, date) pair. Pattern B
(n_dlc=1 + n_ws=2 + n_cam=2) tests verify the existing single-half code
path remains unchanged — Pattern B sessions are exploratory by design
and silently use the unlabeled-half data only.

Fixtures lay out tmp_path with the on-disk shapes documented in
``docs/phase-7-pre/multi_half_scan_results.md``:

  Pattern A (PS48 20250314):
    {tmp_path}/wavesurfer/20250314a/PS48/stroke_0001.h5
    {tmp_path}/wavesurfer/20250314b/PS48/stroke_0002.h5
    {tmp_path}/dlc/PS48/video2_2025-03-14T12_31_07DLC_*_filtered.{h5,csv}
    {tmp_path}/dlc/PS48/video2_2025-03-14T13_09_29DLC_*_filtered.{h5,csv}
    {tmp_path}/camera/20250314a/PS48/{video,timestamp}*_2025-03-14T12_31_07.*
    {tmp_path}/camera/20250314b/PS48/{video,timestamp}*_2025-03-14T13_09_2{8,9}.*

  Pattern B (PS54 20250620):
    {tmp_path}/wavesurfer/20250620/PS54/stroke_0001.h5
    {tmp_path}/wavesurfer/20250620b/PS54/stroke_0001.h5
    {tmp_path}/dlc/PS54/video2_2025-06-20T12_19_35DLC_*_filtered.{h5,csv}
    {tmp_path}/camera/20250620/PS54/...
    {tmp_path}/camera/20250620b/PS54/...
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stroke_orofacial.animals import AnimalInfo, Exclusion
from stroke_orofacial.manifest import (
    HalfSpec,
    MultiHalfNotDeclaredError,
    _file_timestamp_minute_prefix,
    build_manifest,
)
from stroke_orofacial.paths import PathResolver


# ---------- helpers ----------


def _touch_dlc(dlc_dir: Path, date_iso: str, hh_mm_ss: str) -> tuple[Path, Path]:
    """Create a filtered DLC H5 + CSV pair at the flat O2_analysis level."""
    dlc_dir.mkdir(parents=True, exist_ok=True)
    base = (
        f"video2_{date_iso}T{hh_mm_ss}DLC_Resnet50_video2Jan26shuffle5_snapshot_060"
    )
    h5 = dlc_dir / f"{base}_filtered.h5"
    csv = dlc_dir / f"{base}_filtered.csv"
    h5.touch()
    csv.touch()
    return h5, csv


def _touch_ws_subdir(ws_root: Path, subdir: str, animal: str, h5_name: str) -> Path:
    """Create a per-half WS subdir with one .h5 file."""
    d = ws_root / subdir / animal
    d.mkdir(parents=True, exist_ok=True)
    h5 = d / h5_name
    h5.touch()
    return h5


def _touch_camera_subdir(
    cam_root: Path,
    subdir: str,
    animal: str,
    *,
    video_ts: str,
    timestamp_ts: str,
    n_cams: int = 4,
) -> Path:
    """Create a per-half camera subdir with cam1-cam{n_cams} video + timestamp files.

    ``video_ts`` and ``timestamp_ts`` are the HH_MM_SS portions for the .avi
    and .csv filenames respectively — they may differ by ~1 second on real
    PS48 20250314 half-b, so the helper exposes both.
    """
    d = cam_root / subdir / animal
    d.mkdir(parents=True, exist_ok=True)
    for cam in range(1, n_cams + 1):
        (d / f"video{cam}_{video_ts}.avi").touch()
        (d / f"timestamp{cam}_{timestamp_ts}.csv").touch()
    return d


def _make_resolver_for_layout(
    ws_root: Path, dlc_root: Path, cam_root: Path
) -> MagicMock:
    """Build a MagicMock PathResolver routing the four convenience methods
    used by ``build_manifest`` to the supplied root paths.

    ``wavesurfer_dir`` and ``camera_dir`` honor both the Phase 7-pre-
    multi-half ``half_subdir`` kwarg (Pattern A) and the Phase
    7-pre-secondary-spout ``subdir_override`` kwarg (Pattern B) so
    per-half discovery resolves to the correct per-half subdir under
    either dispatch. Mutually exclusive (matching the real resolver).
    """
    resolver = MagicMock(spec=PathResolver)

    def _ws_dir(date, animal, *, half_subdir=None, subdir_override=None):
        if half_subdir is not None and subdir_override is not None:
            raise ValueError(
                "half_subdir and subdir_override are mutually exclusive"
            )
        explicit = half_subdir if half_subdir is not None else subdir_override
        subdir = explicit if explicit is not None else date.strftime("%Y%m%d")
        return ws_root / subdir / animal

    def _cam_dir(date, animal, *, half_subdir=None, subdir_override=None):
        if half_subdir is not None and subdir_override is not None:
            raise ValueError(
                "half_subdir and subdir_override are mutually exclusive"
            )
        explicit = half_subdir if half_subdir is not None else subdir_override
        subdir = explicit if explicit is not None else date.strftime("%Y%m%d")
        return cam_root / subdir / animal

    def _dlc_output_dir(animal):
        return dlc_root / animal

    def _alignment_template_legacy_read(
        animal, date, cam="cam2", *, session_suffix=None,
    ):
        # No alignment template emitted in fixture (build_manifest only checks
        # existence and stores None when missing). Renamed in the
        # 2026-05-05 incident response: the resolver method that build_manifest
        # uses for legacy template discovery is alignment_template_legacy_read.
        # Phase 7-pre-secondary-spout: also accept session_suffix kwarg
        # (Task 5 added it to the real resolver). Mirror suffix-aware
        # filename behavior for Pattern B b-half discovery.
        date_str = date.strftime("%Y%m%d") + (session_suffix or "")
        return ws_root.parent / "alignment_templates" / cam / animal / (
            f"{date_str}.npz"
        )

    resolver.wavesurfer_dir.side_effect = _ws_dir
    resolver.camera_dir.side_effect = _cam_dir
    resolver.dlc_output_dir.side_effect = _dlc_output_dir
    resolver.alignment_template_legacy_read.side_effect = _alignment_template_legacy_read
    return resolver


# ---------- file_timestamp prefix helper ----------


class TestFileTimestampMinutePrefix:
    """Verify the HH_MM-prefix helper handles the off-by-1-second case."""

    def test_strips_seconds_segment(self):
        # Real PS48 20250314 half-b: video=T13_09_29, csv=T13_09_28
        assert (
            _file_timestamp_minute_prefix("2025-03-14T13_09_29")
            == "2025-03-14T13_09"
        )

    def test_keeps_full_string_when_no_seconds_segment(self):
        # Defensive fallback: degraded format returns the input verbatim
        # so the camera-side glob still fires (with a stricter match).
        assert _file_timestamp_minute_prefix("2025-03-14T13_09") == "2025-03-14T13_09"

    def test_keeps_full_string_when_trailing_segment_non_numeric(self):
        # Garbage input is passed through.
        assert (
            _file_timestamp_minute_prefix("2025-03-14T13_09_abc")
            == "2025-03-14T13_09_abc"
        )


# ---------- Pattern A: full multi-half discovery ----------


@pytest.fixture()
def ps48_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS48",
        stroke_date=datetime.date(2025, 3, 19),
        session_start=datetime.date(2025, 3, 5),
        session_end=datetime.date(2025, 4, 30),
    )


@pytest.fixture()
def pattern_a_layout(tmp_path: Path) -> dict[str, Path]:
    """Build a Pattern A on-disk layout for PS48 20250314."""
    ws_root = tmp_path / "wavesurfer"
    dlc_root = tmp_path / "dlc"
    cam_root = tmp_path / "camera"
    # WS per-half
    _touch_ws_subdir(ws_root, "20250314a", "PS48", "stroke_0001.h5")
    _touch_ws_subdir(ws_root, "20250314b", "PS48", "stroke_0002.h5")
    # DLC: 2 filtered H5 at flat O2_analysis level
    _touch_dlc(dlc_root / "PS48", "2025-03-14", "12_31_07")
    _touch_dlc(dlc_root / "PS48", "2025-03-14", "13_09_29")
    # Camera per-half — half b has off-by-1-second (csv at _28, video at _29)
    _touch_camera_subdir(
        cam_root, "20250314a", "PS48",
        video_ts="2025-03-14T12_31_07", timestamp_ts="2025-03-14T12_31_07",
    )
    _touch_camera_subdir(
        cam_root, "20250314b", "PS48",
        video_ts="2025-03-14T13_09_29", timestamp_ts="2025-03-14T13_09_28",
    )
    return {"ws_root": ws_root, "dlc_root": dlc_root, "cam_root": cam_root}


@pytest.fixture()
def pattern_a_overrides() -> dict:
    """The PS48 20250314 multi_half_sessions: entry as a Python dict."""
    return {
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
                    "reason": "Pattern A test fixture",
                }
            }
        }
    }


class TestPatternAMultiHalf:
    """Pattern A YAML entry → halves populated, parent-level fields cleared."""

    def test_halves_populated_with_two_specs(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.halves is not None
        assert len(manifest.halves) == 2
        assert manifest.halves[0].id == "a"
        assert manifest.halves[1].id == "b"
        assert manifest.halves[0].ws_subdir == "20250314a"
        assert manifest.halves[0].cam_subdir == "20250314a"
        assert manifest.halves[0].file_timestamp == "2025-03-14T12_31_07"

    def test_parent_level_ws_and_video_cleared_when_multi_half(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        """Per the manifest contract, when halves is populated the parent
        level wavesurfer_file / video_files are empty — downstream Phase
        2/3 consumers read per-half WS + video from halves[i].

        Phase 7c.2 Task 2 F-P-5 wiring fix: parent-level dlc_h5_files /
        dlc_csv_files now carry [halves[0].dlc_h5_file] /
        [halves[0].dlc_csv_file] (half-A's DLC paths) so Phase 7a
        consumers find the merged centered parquet via half-A's H5
        filename — see ``TestPatternAMultiHalfDlcFilesWiring`` below.
        """
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.wavesurfer_file is None
        assert manifest.video_files == []

    def test_per_half_ws_discovery(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.halves is not None
        a, b = manifest.halves
        assert a.wavesurfer_file is not None
        assert a.wavesurfer_file.name == "stroke_0001.h5"
        assert a.wavesurfer_file.parent.name == "PS48"
        assert a.wavesurfer_file.parent.parent.name == "20250314a"
        assert b.wavesurfer_file is not None
        assert b.wavesurfer_file.name == "stroke_0002.h5"
        assert b.wavesurfer_file.parent.parent.name == "20250314b"

    def test_per_half_dlc_discovery(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.halves is not None
        a, b = manifest.halves
        assert a.dlc_h5_file is not None
        assert "2025-03-14T12_31_07" in a.dlc_h5_file.name
        assert a.dlc_csv_file is not None
        assert "2025-03-14T12_31_07" in a.dlc_csv_file.name
        assert b.dlc_h5_file is not None
        assert "2025-03-14T13_09_29" in b.dlc_h5_file.name

    def test_per_half_camera_discovery_off_by_one_second(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        """Half b has video filenames at T13_09_29 but timestamp CSVs at
        T13_09_28 — the loose HH_MM-prefix glob picks up both."""
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.halves is not None
        b = manifest.halves[1]
        # 4 cams (cam1-cam4) per half
        assert len(b.video_files) == 4
        assert len(b.timestamp_csv_files) == 4
        # video uses _29, csv uses _28 — both matched by the loose prefix
        assert any("13_09_29" in p.name for p in b.video_files)
        assert any("13_09_28" in p.name for p in b.timestamp_csv_files)

    def test_alignment_template_remains_at_parent_level(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        """Even for multi-half, the parent-level alignment_template field
        points at the merged-file path. (Not yet present on disk in the
        fixture; build_manifest emits None when path doesn't exist.)"""
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        # Resolver was asked for the merged path, but file doesn't exist
        # (Phase 3 hasn't run yet). Per the manifest's optional-discovery
        # contract, missing artefact → None.
        assert manifest.alignment_template is None
        # And per-half templates haven't been populated either (Task 5
        # populates them when Phase 3 emits per-half output).
        assert manifest.halves is not None
        assert all(h.alignment_template is None for h in manifest.halves)


# ---------- Defensive check: Pattern A undeclared raises ----------


class TestMultiHalfNotDeclaredCheck:
    def test_raises_when_two_dlc_files_and_no_yaml_entry(
        self, pattern_a_layout, ps48_info
    ):
        """The audit-locked safety rule: n_dlc>=2 + no YAML entry → raise."""
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        empty_overrides = {"multi_half_sessions": {}}
        with pytest.raises(MultiHalfNotDeclaredError) as excinfo:
            build_manifest(
                "PS48",
                datetime.date(2025, 3, 14),
                resolver,
                ps48_info,
                analysis_context="spout_behavior",
                overrides_config=empty_overrides,
            )
        msg = str(excinfo.value)
        # Embedded stub gives the user a copy-pasteable starting point
        assert "multi_half_sessions" in msg
        assert "PS48" in msg
        assert '"20250314"' in msg
        # Auto-detected timestamps appear in the stub
        assert "2025-03-14T12_31_07" in msg
        assert "2025-03-14T13_09_29" in msg
        # Letters assigned by acquisition order
        assert "id: a" in msg
        assert "id: b" in msg

    def test_does_not_raise_when_yaml_entry_present(
        self, pattern_a_layout, pattern_a_overrides, ps48_info
    ):
        """With a registered entry the defensive check is bypassed."""
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            ps48_info,
            analysis_context="spout_behavior",
            overrides_config=pattern_a_overrides,
        )
        assert manifest.halves is not None

    def test_excluded_session_skips_check(
        self, pattern_a_layout
    ):
        """Excluded sessions never trip the defensive check, even with
        n_dlc>=2 on disk. Exclusion is a stronger signal."""
        info = AnimalInfo(
            animal_id="PS48",
            stroke_date=datetime.date(2025, 3, 19),
            session_start=datetime.date(2025, 3, 5),
            session_end=datetime.date(2025, 4, 30),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 3, 14),
                    "test exclusion",
                    ["dlc", "spout_behavior"],
                ),
            ],
        )
        resolver = _make_resolver_for_layout(**pattern_a_layout)
        # No multi_half_sessions entry — would raise if the session weren't
        # excluded. With exclusion in place, build_manifest returns cleanly
        # and the manifest carries excluded=True.
        manifest = build_manifest(
            "PS48",
            datetime.date(2025, 3, 14),
            resolver,
            info,
            analysis_context="spout_behavior",
            overrides_config={"multi_half_sessions": {}},
        )
        assert manifest.excluded is True
        assert manifest.halves is None  # no YAML entry; single-half discovery


# ---------- Pattern B: silent half-a-only path is unchanged ----------


@pytest.fixture()
def ps54_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS54",
        stroke_date=datetime.date(2025, 4, 28),
        session_start=datetime.date(2025, 4, 20),
        session_end=datetime.date(2025, 7, 1),
    )


@pytest.fixture()
def pattern_b_layout(tmp_path: Path) -> dict[str, Path]:
    """Build a Pattern B on-disk layout for PS54 20250620.

    Pattern B is n_ws=2 + n_cam=2 + n_dlc=1: WS and camera have a
    bare {DATE} subdir + a {DATE}b subdir, but DLC inference was only
    run on one half (the bare {DATE} half — half-a by convention).
    """
    ws_root = tmp_path / "wavesurfer"
    dlc_root = tmp_path / "dlc"
    cam_root = tmp_path / "camera"
    # Two WS subdirs: bare + b-suffixed
    _touch_ws_subdir(ws_root, "20250620", "PS54", "stroke_0001.h5")
    _touch_ws_subdir(ws_root, "20250620b", "PS54", "stroke_0001.h5")
    # ONE DLC filtered H5 (half-a only)
    _touch_dlc(dlc_root / "PS54", "2025-06-20", "12_19_35")
    # Two camera subdirs
    _touch_camera_subdir(
        cam_root, "20250620", "PS54",
        video_ts="2025-06-20T12_19_35", timestamp_ts="2025-06-20T12_19_35",
    )
    _touch_camera_subdir(
        cam_root, "20250620b", "PS54",
        video_ts="2025-06-20T13_45_00", timestamp_ts="2025-06-20T13_45_00",
    )
    return {"ws_root": ws_root, "dlc_root": dlc_root, "cam_root": cam_root}


class TestPatternBSilentSingleHalfPath:
    """Pattern B sessions stay on the existing single-half discovery path
    by design. The defensive check uses n_dlc>=2 as the trigger so n_dlc=1
    Pattern B sessions never trip it."""

    def test_does_not_raise_when_n_dlc_is_one(self, pattern_b_layout, ps54_info):
        resolver = _make_resolver_for_layout(**pattern_b_layout)
        manifest = build_manifest(
            "PS54",
            datetime.date(2025, 6, 20),
            resolver,
            ps54_info,
            analysis_context="spout_behavior",
            overrides_config={"multi_half_sessions": {}},
        )
        # No raise. halves stays None, single-half discovery picks up the
        # bare {DATE} subdir's WS file (half-a by convention).
        assert manifest.halves is None
        assert manifest.wavesurfer_file is not None
        assert manifest.wavesurfer_file.parent.parent.name == "20250620"  # bare
        # DLC parent-level field carries the single filtered H5 (half-a)
        assert len(manifest.dlc_h5_files) == 1
        assert "2025-06-20T12_19_35" in manifest.dlc_h5_files[0].name


# ---------- HalfSpec dataclass shape ----------


class TestHalfSpecDataclass:
    """Smoke tests on the HalfSpec dataclass — defaults, equality, repr."""

    def test_minimal_construction(self):
        spec = HalfSpec(
            id="a",
            ws_subdir="20250314a",
            cam_subdir="20250314a",
            file_timestamp="2025-03-14T12_31_07",
        )
        assert spec.id == "a"
        assert spec.wavesurfer_file is None
        assert spec.dlc_h5_file is None
        assert spec.dlc_csv_file is None
        assert spec.video_files == []
        assert spec.timestamp_csv_files == []
        assert spec.alignment_template is None

    def test_default_lists_are_independent(self):
        """Mutable default factories must not be shared between instances."""
        a = HalfSpec(id="a", ws_subdir="x", cam_subdir="y", file_timestamp="t")
        b = HalfSpec(id="b", ws_subdir="x", cam_subdir="y", file_timestamp="t")
        a.video_files.append(Path("/tmp/foo"))
        assert b.video_files == []
