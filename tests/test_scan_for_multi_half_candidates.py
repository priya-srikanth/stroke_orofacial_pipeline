"""Tests for scripts/phase_7_pre/scan_for_multi_half_candidates.py.

Verifies the productized scan's classification logic, YAML-comparison
exit-code, markdown report shape, and read-only invariant. Synthetic
fixtures lay out tmp_path-rooted WS/DLC/camera trees mirroring the
on-disk shape established in the Task 1b cohort audit.
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

from stroke_orofacial.animals import AnimalInfo


# ---------- Module load (script lives outside src/, no package import) ----------


def _load_scan_module():
    """Load the scan script as a module without using `import scripts...`.

    The scripts/ tree is NOT a regular package (no __init__.py in scripts/
    itself); load via importlib so tests stay self-contained.
    """
    spec = importlib.util.spec_from_file_location(
        "_scan_for_multi_half_candidates",
        Path(__file__).parent.parent
        / "scripts" / "phase_7_pre" / "scan_for_multi_half_candidates.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_scan_for_multi_half_candidates"] = module
    spec.loader.exec_module(module)
    return module


SCAN = _load_scan_module()


# ---------- Fixture helpers ----------


def _make_ws_dir(ws_root: Path, subdir: str, animal: str, h5_name: str = "stroke_0001.h5") -> Path:
    p = ws_root / subdir / animal / h5_name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_dlc_h5(
    dlc_root: Path, animal: str, date_iso: str, hh_mm_ss: str,
) -> Path:
    """Create a filtered DLC H5 file at the flat O2_analysis/{ANIMAL}/ level."""
    name = (
        f"video2_{date_iso}T{hh_mm_ss}DLC_Resnet50_video2Jan26shuffle5"
        "_snapshot_060_filtered.h5"
    )
    p = dlc_root / animal / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_cam_dir(
    cam_root: Path, subdir: str, animal: str,
    *, video_ts: str = "T12_31_07",
) -> Path:
    p = cam_root / subdir / animal / f"video2_{video_ts}.avi"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_animal_info(animal_id: str, start: datetime.date, end: datetime.date) -> AnimalInfo:
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=start + datetime.timedelta(days=10),
        session_start=start,
        session_end=end,
    )


# ---------- _classify ----------


class TestClassify:
    def test_pattern_a_when_two_dlc(self):
        # n_dlc>=2 wins regardless of n_ws / n_cam
        assert SCAN._classify(n_ws=2, n_dlc=2, n_cam=2) == "pattern_a"
        assert SCAN._classify(n_ws=1, n_dlc=2, n_cam=1) == "pattern_a"

    def test_pattern_b_when_n_dlc_lt_2_and_others_ge_2(self):
        assert SCAN._classify(n_ws=2, n_dlc=1, n_cam=2) == "pattern_b"
        assert SCAN._classify(n_ws=2, n_dlc=0, n_cam=2) == "pattern_b"

    def test_weak_when_only_one_signal_high(self):
        assert SCAN._classify(n_ws=1, n_dlc=1, n_cam=2) == "weak"
        assert SCAN._classify(n_ws=2, n_dlc=1, n_cam=1) == "weak"
        # n_dlc>=2 alone is Pattern A, NOT weak (n_dlc is the discriminator)
        assert SCAN._classify(n_ws=1, n_dlc=2, n_cam=0) == "pattern_a"

    def test_none_when_no_signal(self):
        assert SCAN._classify(n_ws=1, n_dlc=1, n_cam=1) is None
        assert SCAN._classify(n_ws=0, n_dlc=0, n_cam=0) is None


# ---------- _scan_single_session ----------


class TestScanSingleSession:
    def test_pattern_a_layout(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        # Pattern A: 2 ws subdirs, 2 DLC H5 files, 2 cam subdirs
        _make_ws_dir(ws, "20250314a", "PS48")
        _make_ws_dir(ws, "20250314b", "PS48")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "12_31_07")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "13_09_29")
        _make_cam_dir(cam, "20250314a", "PS48", video_ts="2025-03-14T12_31_07")
        _make_cam_dir(cam, "20250314b", "PS48", video_ts="2025-03-14T13_09_29")

        result = SCAN._scan_single_session(
            "PS48", datetime.date(2025, 3, 14), ws, dlc, cam,
        )
        assert result is not None
        assert result.classification == "pattern_a"
        assert result.n_ws == 2
        assert result.n_dlc == 2
        assert result.n_cam == 2
        assert sorted(result.ws_dirs) == ["20250314a", "20250314b"]
        # Filenames sorted by name (alphabetic ≈ acquisition order)
        assert "12_31_07" in result.dlc_filenames[0]
        assert "13_09_29" in result.dlc_filenames[1]

    def test_pattern_b_layout(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        # Pattern B: 2 ws subdirs (bare + b), 1 DLC, 2 cam subdirs
        _make_ws_dir(ws, "20250620", "PS54")
        _make_ws_dir(ws, "20250620b", "PS54")
        _make_dlc_h5(dlc, "PS54", "2025-06-20", "12_19_35")
        _make_cam_dir(cam, "20250620", "PS54")
        _make_cam_dir(cam, "20250620b", "PS54")

        result = SCAN._scan_single_session(
            "PS54", datetime.date(2025, 6, 20), ws, dlc, cam,
        )
        assert result is not None
        assert result.classification == "pattern_b"
        assert result.n_ws == 2
        assert result.n_dlc == 1
        assert result.n_cam == 2

    def test_weak_partial_acquisition(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        # Weak: 1 ws (no half-b), 1 DLC, 2 cam subdirs (camera kept rolling)
        _make_ws_dir(ws, "20250508", "PS54")
        _make_dlc_h5(dlc, "PS54", "2025-05-08", "12_20_45")
        _make_cam_dir(cam, "20250508", "PS54")
        _make_cam_dir(cam, "20250508b", "PS54")

        result = SCAN._scan_single_session(
            "PS54", datetime.date(2025, 5, 8), ws, dlc, cam,
        )
        assert result is not None
        assert result.classification == "weak"
        assert result.n_ws == 1
        assert result.n_dlc == 1
        assert result.n_cam == 2

    def test_returns_none_when_no_signal(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        # Single-half session: 1 ws, 1 DLC, 1 cam — all baseline
        _make_ws_dir(ws, "20250307", "PS46")
        _make_dlc_h5(dlc, "PS46", "2025-03-07", "12_11_32")
        _make_cam_dir(cam, "20250307", "PS46")

        result = SCAN._scan_single_session(
            "PS46", datetime.date(2025, 3, 7), ws, dlc, cam,
        )
        assert result is None

    def test_handles_missing_roots_gracefully(self, tmp_path: Path):
        """Roots that don't exist on disk shouldn't crash — scan returns
        None as if no signal."""
        # No setup at all
        result = SCAN._scan_single_session(
            "PS46", datetime.date(2025, 3, 7),
            tmp_path / "missing_ws",
            tmp_path / "missing_dlc",
            tmp_path / "missing_cam",
        )
        assert result is None


# ---------- scan_cohort ----------


class TestScanCohort:
    def test_empty_cohort(self, tmp_path: Path):
        animals = {"PS46": _make_animal_info(
            "PS46", datetime.date(2025, 3, 7), datetime.date(2025, 3, 9),
        )}
        # Single-half setup (1/1/1 each day)
        for d in (datetime.date(2025, 3, 7), datetime.date(2025, 3, 8)):
            _make_ws_dir(tmp_path / "ws", d.strftime("%Y%m%d"), "PS46")
            _make_dlc_h5(tmp_path / "dlc", "PS46", d.isoformat(), "12_00_00")
            _make_cam_dir(tmp_path / "cam", d.strftime("%Y%m%d"), "PS46")

        result = SCAN.scan_cohort(
            animals, tmp_path / "ws", tmp_path / "dlc", tmp_path / "cam",
        )
        assert result.pattern_a == []
        assert result.pattern_b == []
        assert result.weak == []
        assert result.n_sessions_scanned == 3  # 7,8,9

    def test_one_pattern_a_one_pattern_b(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        animals = {
            "PS48": _make_animal_info(
                "PS48", datetime.date(2025, 3, 14), datetime.date(2025, 3, 14),
            ),
            "PS54": _make_animal_info(
                "PS54", datetime.date(2025, 6, 20), datetime.date(2025, 6, 20),
            ),
        }
        # PS48 20250314 — Pattern A
        _make_ws_dir(ws, "20250314a", "PS48")
        _make_ws_dir(ws, "20250314b", "PS48")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "12_31_07")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "13_09_29")
        _make_cam_dir(cam, "20250314a", "PS48")
        _make_cam_dir(cam, "20250314b", "PS48")
        # PS54 20250620 — Pattern B
        _make_ws_dir(ws, "20250620", "PS54")
        _make_ws_dir(ws, "20250620b", "PS54")
        _make_dlc_h5(dlc, "PS54", "2025-06-20", "12_19_35")
        _make_cam_dir(cam, "20250620", "PS54")
        _make_cam_dir(cam, "20250620b", "PS54")

        result = SCAN.scan_cohort(animals, ws, dlc, cam)
        assert len(result.pattern_a) == 1
        assert result.pattern_a[0].animal == "PS48"
        assert result.pattern_a[0].date_str == "20250314"
        assert len(result.pattern_b) == 1
        assert result.pattern_b[0].animal == "PS54"
        assert result.pattern_b[0].date_str == "20250620"
        assert result.weak == []


# ---------- _yaml_declared_keys + comparison logic ----------


class TestYamlDeclaredKeys:
    def test_extracts_animal_date_pairs(self):
        cfg = {
            "multi_half_sessions": {
                "PS48": {
                    "20250314": {"halves": []},
                },
                "PS55": {
                    "20250424": {"halves": []},
                    "20250428": {"halves": []},
                },
            },
        }
        keys = SCAN._yaml_declared_keys(cfg)
        assert keys == {
            ("PS48", "20250314"),
            ("PS55", "20250424"),
            ("PS55", "20250428"),
        }

    def test_returns_empty_when_block_missing(self):
        assert SCAN._yaml_declared_keys({}) == set()
        assert SCAN._yaml_declared_keys({"multi_half_sessions": None}) == set()
        assert SCAN._yaml_declared_keys({"multi_half_sessions": {}}) == set()


# ---------- _format_yaml_stub_for_undeclared ----------


class TestFormatYamlStub:
    def test_pattern_a_two_halves(self, tmp_path: Path):
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        _make_ws_dir(ws, "20250314a", "PS48")
        _make_ws_dir(ws, "20250314b", "PS48")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "12_31_07")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "13_09_29")
        _make_cam_dir(cam, "20250314a", "PS48")
        _make_cam_dir(cam, "20250314b", "PS48")
        cand = SCAN._scan_single_session(
            "PS48", datetime.date(2025, 3, 14), ws, dlc, cam,
        )
        assert cand is not None
        stub = SCAN._format_yaml_stub_for_undeclared([cand])
        # Expected structure
        assert "multi_half_sessions:" in stub
        assert "  PS48:" in stub
        assert '    "20250314":' in stub
        assert "      halves:" in stub
        assert "        - id: a" in stub
        assert "        - id: b" in stub
        assert 'ws_subdir: "20250314a"' in stub
        assert 'ws_subdir: "20250314b"' in stub
        assert 'cam_subdir: "20250314a"' in stub
        assert 'file_timestamp: "2025-03-14T12_31_07"' in stub
        assert 'file_timestamp: "2025-03-14T13_09_29"' in stub

    def test_empty_candidates_returns_empty(self):
        assert SCAN._format_yaml_stub_for_undeclared([]) == ""


# ---------- main / CLI exit codes ----------


class TestMainExitCodes:
    @pytest.fixture()
    def synthetic_cohort_pattern_a_undeclared(self, tmp_path: Path, monkeypatch):
        """Synthetic single-Pattern-A-undeclared cohort.

        Set up tmp_path-based mounts + a tiny animals.yaml + an EMPTY
        session_overrides.yaml so the scan finds Pattern A but no YAML
        entry covers it → exit 1.
        """
        # Animals + overrides yaml
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        (configs_dir / "animals.yaml").write_text(
            "PS48:\n"
            "  stroke_date: 2025-03-19\n"
            "  session_start: 2025-03-14\n"
            "  session_end: 2025-03-14\n",
            encoding="utf-8",
        )
        (configs_dir / "session_overrides.yaml").write_text(
            "overrides: {}\n"
            "merges: {}\n"
            "multi_half_sessions: {}\n",
            encoding="utf-8",
        )
        # Pattern A on-disk
        ws = tmp_path / "ws"
        dlc = tmp_path / "dlc"
        cam = tmp_path / "cam"
        _make_ws_dir(ws, "20250314a", "PS48")
        _make_ws_dir(ws, "20250314b", "PS48")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "12_31_07")
        _make_dlc_h5(dlc, "PS48", "2025-03-14", "13_09_29")
        _make_cam_dir(cam, "20250314a", "PS48")
        _make_cam_dir(cam, "20250314b", "PS48")

        # Patch the loaders to read our synthetic configs
        monkeypatch.setattr(
            SCAN, "load_animals",
            lambda: {
                "PS48": _make_animal_info(
                    "PS48", datetime.date(2025, 3, 14), datetime.date(2025, 3, 14),
                ),
            },
        )
        monkeypatch.setattr(
            SCAN, "load_session_overrides",
            lambda: {
                "overrides": {}, "merges": {},
                "multi_half_sessions": {},
            },
        )
        # Patch the resolver factory to return our tmp_path-mounted roots
        class _FakeResolver:
            def root(self, name):
                from pathlib import Path as _P
                if name == "wavesurfer_raw":
                    return _P(ws)
                if name == "camera_raw":
                    return _P(cam)
                if name == "microscope_server":
                    # _path_roots_from_resolver appends DeepLabCut/O2_analysis
                    # to derive dlc_root
                    return _P(tmp_path)
                raise KeyError(name)
        monkeypatch.setattr(SCAN, "PathResolver", lambda: _FakeResolver())

        # Override default DLC root path: _path_roots_from_resolver returns
        # microscope_server / DeepLabCut / O2_analysis. Mirror that with a
        # symlink-equivalent: place dlc h5s under the resolved dlc path.
        target_dlc_root = tmp_path / "DeepLabCut" / "O2_analysis"
        # If dlc_root we created doesn't match what the script will resolve,
        # create the same shape.
        if not target_dlc_root.exists():
            (target_dlc_root / "PS48").mkdir(parents=True)
            for fname in (dlc / "PS48").glob("*.h5"):
                (target_dlc_root / "PS48" / fname.name).touch()

        return tmp_path

    def test_pattern_a_undeclared_returns_exit_1(
        self, synthetic_cohort_pattern_a_undeclared, capsys,
    ):
        out_path = synthetic_cohort_pattern_a_undeclared / "report.md"
        rc = SCAN.main(["--output", str(out_path), "--quiet"])
        assert rc == 1
        # Markdown report written
        assert out_path.exists()
        report = out_path.read_text(encoding="utf-8")
        assert "Pattern A undeclared" in report
        assert "PS48" in report
        assert "20250314" in report

    def test_pattern_a_declared_returns_exit_0(
        self, tmp_path: Path, monkeypatch,
    ):
        """When a Pattern A candidate IS in multi_half_sessions:, exit 0."""
        ws = tmp_path / "ws"
        dlc_o2 = tmp_path / "DeepLabCut" / "O2_analysis"
        cam = tmp_path / "cam"
        _make_ws_dir(ws, "20250314a", "PS48")
        _make_ws_dir(ws, "20250314b", "PS48")
        _make_dlc_h5(dlc_o2, "PS48", "2025-03-14", "12_31_07")
        _make_dlc_h5(dlc_o2, "PS48", "2025-03-14", "13_09_29")
        _make_cam_dir(cam, "20250314a", "PS48")
        _make_cam_dir(cam, "20250314b", "PS48")

        monkeypatch.setattr(
            SCAN, "load_animals",
            lambda: {"PS48": _make_animal_info(
                "PS48", datetime.date(2025, 3, 14), datetime.date(2025, 3, 14),
            )},
        )
        monkeypatch.setattr(
            SCAN, "load_session_overrides",
            lambda: {
                "overrides": {}, "merges": {},
                "multi_half_sessions": {
                    "PS48": {
                        "20250314": {
                            "halves": [
                                {"id": "a", "ws_subdir": "20250314a",
                                 "cam_subdir": "20250314a",
                                 "file_timestamp": "2025-03-14T12_31_07"},
                            ],
                        },
                    },
                },
            },
        )

        class _FakeResolver:
            def root(self, name):
                from pathlib import Path as _P
                if name == "wavesurfer_raw":
                    return _P(ws)
                if name == "camera_raw":
                    return _P(cam)
                if name == "microscope_server":
                    return _P(tmp_path)
                raise KeyError(name)
        monkeypatch.setattr(SCAN, "PathResolver", lambda: _FakeResolver())

        out_path = tmp_path / "report.md"
        rc = SCAN.main(["--output", str(out_path), "--quiet"])
        assert rc == 0
        report = out_path.read_text(encoding="utf-8")
        assert "Pattern A declared" in report

    def test_no_candidates_returns_exit_0(
        self, tmp_path: Path, monkeypatch,
    ):
        """Synthetic cohort with no multi-half candidates → exit 0."""
        ws = tmp_path / "ws"
        dlc_o2 = tmp_path / "DeepLabCut" / "O2_analysis"
        cam = tmp_path / "cam"
        # Single-half setup (1 ws, 1 dlc, 1 cam) — no candidates
        _make_ws_dir(ws, "20250307", "PS46")
        _make_dlc_h5(dlc_o2, "PS46", "2025-03-07", "12_00_00")
        _make_cam_dir(cam, "20250307", "PS46")

        monkeypatch.setattr(
            SCAN, "load_animals",
            lambda: {"PS46": _make_animal_info(
                "PS46", datetime.date(2025, 3, 7), datetime.date(2025, 3, 7),
            )},
        )
        monkeypatch.setattr(
            SCAN, "load_session_overrides",
            lambda: {"overrides": {}, "merges": {}, "multi_half_sessions": {}},
        )

        class _FakeResolver:
            def root(self, name):
                from pathlib import Path as _P
                if name == "wavesurfer_raw":
                    return _P(ws)
                if name == "camera_raw":
                    return _P(cam)
                if name == "microscope_server":
                    return _P(tmp_path)
                raise KeyError(name)
        monkeypatch.setattr(SCAN, "PathResolver", lambda: _FakeResolver())

        out_path = tmp_path / "report.md"
        rc = SCAN.main(["--output", str(out_path), "--quiet"])
        assert rc == 0


# ---------- Read-only invariant ----------


class TestReadOnlyInvariant:
    def test_does_not_write_to_session_overrides(self):
        """The scan script must NEVER write to session_overrides.yaml.
        Crude but effective: scan the module source line-by-line and
        flag any line that mentions ``session_overrides`` AND a
        write-call token (``write_text`` / ``write_bytes`` / ``open(``
        / ``replace`` / ``np.savez``). Lines that only mention the
        path in comments / docstrings are fine — we look at the
        intersection of (path mention, write token) within a single
        line.
        """
        scan_path = (
            Path(__file__).parent.parent
            / "scripts" / "phase_7_pre" / "scan_for_multi_half_candidates.py"
        )
        write_tokens = (
            "write_text(",
            "write_bytes(",
            ".write(",
            "open(",
            "savez(",
            "to_yaml(",
            "yaml.dump",
        )
        for line_no, line in enumerate(
            scan_path.read_text(encoding="utf-8").splitlines(), start=1,
        ):
            if "session_overrides" not in line:
                continue
            for token in write_tokens:
                assert token not in line, (
                    f"scan_for_multi_half_candidates.py:{line_no} contains "
                    f"both 'session_overrides' and the write token "
                    f"{token!r}: {line.strip()!r}"
                )
