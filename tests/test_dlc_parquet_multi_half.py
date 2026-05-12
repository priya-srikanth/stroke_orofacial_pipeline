"""Phase 7-pre-multi-half tests for build_centered_parquet's per-half path.

Verifies the per-half routing in
:func:`stroke_orofacial.dlc_io.parquet.build_centered_parquet` —
output paths land per Decision 3 (per-half subdir
``{date_str}{halves_concat_label}/``; merged at parent level using
half-A's H5 filename), per-half compute fires once per half, single-half
manifests still go through the existing single-half path unchanged.

The DLC h5 read + centering compute is mocked at the
``_center_one_h5`` boundary so these tests don't need real DLC h5
fixtures — algorithm-side coverage stays in
``test_centering.py`` / ``test_loaders.py`` etc.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from stroke_orofacial.dlc_io.parquet import build_centered_parquet
from stroke_orofacial.manifest import HalfSpec, SessionManifest
from stroke_orofacial.paths import PathResolver


def _make_centered_df(n_rows: int):
    """Tiny synthetic centered DataFrame — only the columns load-bearing
    for the merge function's column-parity check."""
    import numpy as np
    return pd.DataFrame({
        "tongue_x": np.zeros(n_rows, dtype="float32"),
        "tongue_y": np.zeros(n_rows, dtype="float32"),
        "tongue_likelihood": np.full(n_rows, 0.99, dtype="float32"),
    })


def _make_resolver(tmp_path: Path) -> PathResolver:
    """Real PathResolver with output_root pointing at tmp_path."""
    return PathResolver(output_root=tmp_path / "outputs")


def _make_pattern_a_manifest(tmp_path: Path) -> SessionManifest:
    """Pattern A two-half manifest (PS48 20250314) with synthetic per-half
    DLC H5 files touched on disk."""
    h5_a = (
        tmp_path / "dlc" / "PS48"
        / "video2_2025-03-14T12_31_07DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
    )
    h5_b = (
        tmp_path / "dlc" / "PS48"
        / "video2_2025-03-14T13_09_29DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
    )
    for p in (h5_a, h5_b):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    halves = [
        HalfSpec(
            id="a", ws_subdir="20250314a", cam_subdir="20250314a",
            file_timestamp="2025-03-14T12_31_07",
            dlc_h5_file=h5_a,
        ),
        HalfSpec(
            id="b", ws_subdir="20250314b", cam_subdir="20250314b",
            file_timestamp="2025-03-14T13_09_29",
            dlc_h5_file=h5_b,
        ),
    ]
    return SessionManifest(
        session_id="PS48_20250314",
        animal="PS48",
        date=datetime.date(2025, 3, 14),
        day_relative_to_stroke=-5,
        phase="baseline",
        halves=halves,
    )


# ---------- Multi-half routing ----------


class TestBuildCenteredParquetMultiHalf:

    def test_routes_to_multi_half_when_halves_populated(self, tmp_path: Path):
        """A multi-half manifest fires _build_centered_parquet_multi_half
        even though manifest.dlc_h5_files is empty — the per-half DLC
        files live on HalfSpec records."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        # Mock the centering compute so we don't need real DLC h5 data
        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(100),
        ) as mock_center:
            merged = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        # Two compute calls — one per half
        assert mock_center.call_count == 2
        # Merged path returned
        assert merged is not None
        assert merged.exists()
        assert merged.parent.name == "PS48"
        # Filename uses half-A's H5 basename + .intermediate.{sig}.parquet
        assert merged.name.startswith("video2_2025-03-14T12_31_07")
        assert merged.name.endswith(".parquet")

    def test_per_half_paths_use_decision3_subdir_layout(self, tmp_path: Path):
        """Per-half parquets land in {date_str}{halves_concat_label}/
        subdir; merged at parent level."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(100),
        ):
            build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        # Per-half subdir
        per_half_dir = (
            tmp_path / "outputs" / "dlc_analysis" / "centered_spout_midpoint"
            / "PS48" / "20250314ab"
        )
        assert per_half_dir.is_dir()
        per_half_files = sorted(per_half_dir.glob("*.parquet"))
        assert len(per_half_files) == 2
        # Per-half files retain their per-half H5 filename → distinct
        names = [p.name for p in per_half_files]
        assert any("12_31_07" in n for n in names)
        assert any("13_09_29" in n for n in names)

        # Merged at parent level — exactly ONE parquet there (using half-A's name)
        parent_dir = per_half_dir.parent
        parent_files = sorted(p for p in parent_dir.glob("*.parquet") if p.is_file())
        assert len(parent_files) == 1
        assert "12_31_07" in parent_files[0].name  # half-A's timestamp

    def test_merged_concatenates_per_half_data(self, tmp_path: Path):
        """The merged parquet's row count == sum of per-half row counts."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        # Distinct row counts per half
        def _per_half(h5, mode, lt):
            return _make_centered_df(100 if "12_31_07" in h5.name else 250)

        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=_per_half,
        ):
            merged = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        merged_df = pd.read_parquet(merged)
        assert len(merged_df) == 350  # 100 + 250
        # RangeIndex 0..349
        assert list(merged_df.index) == list(range(350))

    def test_skip_when_merged_exists(self, tmp_path: Path):
        """overwrite='skip' returns the existing merged path without
        recomputing per-half parquets."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        # First run to populate
        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(50),
        ):
            merged_first = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        # Second run with skip: should NOT recompute
        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
        ) as mock_center_2:
            merged_second = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="skip",
            )

        assert merged_first == merged_second
        mock_center_2.assert_not_called()

    def test_force_overwrite_recomputes(self, tmp_path: Path):
        """overwrite='force' triggers recompute even when files exist."""
        manifest = _make_pattern_a_manifest(tmp_path)
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(50),
        ):
            build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        # Force again — recomputes per half
        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(75),
        ) as mock_center:
            merged = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        assert mock_center.call_count == 2  # 2 per-half computes
        # Merged now has 150 rows (75 × 2)
        merged_df = pd.read_parquet(merged)
        assert len(merged_df) == 150

    def test_raises_when_per_half_dlc_h5_is_none(self, tmp_path: Path):
        """If a HalfSpec has no dlc_h5_file (DLC inference didn't run for
        that half), build_centered_parquet raises FileNotFoundError with
        the half_id and animal/date in the message."""
        # Build a manifest where half-b has no DLC file
        h5_a = (
            tmp_path / "dlc" / "PS48"
            / "video2_2025-03-14T12_31_07_filtered.h5"
        )
        h5_a.parent.mkdir(parents=True, exist_ok=True)
        h5_a.touch()
        halves = [
            HalfSpec(
                id="a", ws_subdir="20250314a", cam_subdir="20250314a",
                file_timestamp="2025-03-14T12_31_07",
                dlc_h5_file=h5_a,
            ),
            HalfSpec(
                id="b", ws_subdir="20250314b", cam_subdir="20250314b",
                file_timestamp="2025-03-14T13_09_29",
                dlc_h5_file=None,  # missing
            ),
        ]
        manifest = SessionManifest(
            session_id="PS48_20250314",
            animal="PS48",
            date=datetime.date(2025, 3, 14),
            day_relative_to_stroke=-5,
            phase="baseline",
            halves=halves,
        )
        resolver = _make_resolver(tmp_path)

        with pytest.raises(FileNotFoundError) as excinfo:
            with patch(
                "stroke_orofacial.dlc_io.parquet._center_one_h5",
                side_effect=lambda h5, mode, lt: _make_centered_df(50),
            ):
                build_centered_parquet(
                    manifest, "spout_midpoint", resolver,
                    params={"likelihood_threshold": 0.7, "compression": "zstd"},
                    overwrite="force",
                )

        msg = str(excinfo.value)
        assert "halves[b].dlc_h5_file is None" in msg
        assert "PS48" in msg
        assert "20250314" in msg


# ---------- Single-half path unchanged ----------


class TestSingleHalfPathUnchanged:
    def test_single_half_does_not_route_to_multi_half(self, tmp_path: Path):
        """A manifest with halves=None (default) still goes through the
        existing single-half loop. Verifies no regression in the
        canonical Phase 4 path."""
        h5_path = (
            tmp_path / "dlc" / "PS46"
            / "video2_2025-03-07T12_11_32_filtered.h5"
        )
        h5_path.parent.mkdir(parents=True, exist_ok=True)
        h5_path.touch()

        manifest = SessionManifest(
            session_id="PS46_20250307",
            animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6,
            phase="baseline",
            dlc_h5_files=[h5_path],
        )
        resolver = _make_resolver(tmp_path)

        with patch(
            "stroke_orofacial.dlc_io.parquet._center_one_h5",
            side_effect=lambda h5, mode, lt: _make_centered_df(50),
        ) as mock_center:
            result = build_centered_parquet(
                manifest, "spout_midpoint", resolver,
                params={"likelihood_threshold": 0.7, "compression": "zstd"},
                overwrite="force",
            )

        # Single compute call (one h5 file)
        assert mock_center.call_count == 1
        # Output at the legacy single-half layout — directly under
        # centered_{mode}/{ANIMAL}/{h5_name}.intermediate.{sig}.parquet
        # (NO halves_concat_label subdir)
        assert result is not None
        assert result.parent.name == "PS46"  # animal dir directly
        assert "video2_2025-03-07T12_11_32" in result.name
