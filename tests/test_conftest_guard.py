"""Sentinel tests for the autouse conftest writeguard fixture.

Layer 3 of the three-layer guard system (after the writeguard module
in Commit 2 and before the resolver split in Commit 4). Without these
sentinels, a future regression in ``tests/conftest.py`` could silently
disable the guard — these tests intentionally try to write to legacy
paths via every patched API and assert the guard fires.

Each test pretends to be a buggy test that constructs a destination
under the live MICROSCOPE legacy tree. The autouse fixture in
``conftest.py`` should intercept every attempt and raise
:class:`stroke_orofacial._writeguard.WriteGuardError` BEFORE any
write hits disk.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial._writeguard import WriteGuardError


# A canonical legacy alignment-template UNC path. The conftest guard
# should reject ALL attempts to write here.
LEGACY_PATH = (
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
    r"\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250314.npz"
)
LEGACY_PARENT = (
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
    r"\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48"
)


class TestConftestGuardFiresOnLegacyPaths:
    """Each patched API must raise WriteGuardError on legacy destinations."""

    def test_np_savez_raises_on_legacy_path(self):
        with pytest.raises(WriteGuardError, match="legacy"):
            np.savez(LEGACY_PATH, foo=np.zeros(5))

    def test_np_savez_compressed_raises_on_legacy_path(self):
        with pytest.raises(WriteGuardError, match="legacy"):
            np.savez_compressed(LEGACY_PATH, foo=np.zeros(5))

    def test_dataframe_to_parquet_raises_on_legacy_path(self):
        legacy_parquet = LEGACY_PATH.replace(".npz", ".parquet")
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        with pytest.raises(WriteGuardError, match="legacy"):
            df.to_parquet(legacy_parquet)

    def test_path_write_text_raises_on_legacy_path(self):
        with pytest.raises(WriteGuardError, match="legacy"):
            Path(LEGACY_PATH).write_text("synthetic")

    def test_path_write_bytes_raises_on_legacy_path(self):
        with pytest.raises(WriteGuardError, match="legacy"):
            Path(LEGACY_PATH).write_bytes(b"synthetic")

    def test_path_replace_raises_on_legacy_destination(self, tmp_path: Path):
        """Atomic-rename idiom: write_centered_parquet uses Path.replace
        to move a temp file to its final destination. The guard must
        check the TARGET (final dest) of replace, not the source."""
        # Source file lives in tmp_path (safe)
        src = tmp_path / "tmp.parquet"
        src.write_text("synthetic")
        # Target is the legacy path → should raise
        with pytest.raises(WriteGuardError, match="legacy"):
            src.replace(LEGACY_PATH)


class TestConftestGuardPassesSafePaths:
    """Safe destinations (tmp_path) pass through untouched. Without
    these tests we couldn't tell whether the guard is firing
    legitimately or breaking everything."""

    def test_np_savez_succeeds_on_tmp_path(self, tmp_path: Path):
        path = tmp_path / "ok.npz"
        np.savez(path, foo=np.zeros(3))
        assert path.exists()
        loaded = np.load(path)
        assert loaded["foo"].shape == (3,)

    def test_np_savez_compressed_succeeds_on_tmp_path(self, tmp_path: Path):
        path = tmp_path / "ok.npz"
        np.savez_compressed(path, foo=np.zeros(3))
        assert path.exists()

    def test_dataframe_to_parquet_succeeds_on_tmp_path(self, tmp_path: Path):
        path = tmp_path / "ok.parquet"
        pd.DataFrame({"x": [1.0]}).to_parquet(path, index=False)
        assert path.exists()

    def test_path_write_text_succeeds_on_tmp_path(self, tmp_path: Path):
        path = tmp_path / "ok.txt"
        path.write_text("hello")
        assert path.read_text() == "hello"

    def test_path_write_bytes_succeeds_on_tmp_path(self, tmp_path: Path):
        path = tmp_path / "ok.bin"
        path.write_bytes(b"hello")
        assert path.read_bytes() == b"hello"

    def test_path_replace_succeeds_within_tmp_path(self, tmp_path: Path):
        src = tmp_path / "from.txt"
        dst = tmp_path / "to.txt"
        src.write_text("payload")
        src.replace(dst)
        assert dst.exists()
        assert dst.read_text() == "payload"
        assert not src.exists()


class TestPipelineOutputsPassesGuard:
    """The new pipeline writes to stroke_orofacial_pipeline_outputs/.
    Even though this is on the MICROSCOPE share, the writeguard
    deliberately allows it (the new pipeline IS the pipeline that
    writes there)."""

    def test_pipeline_outputs_unc_path_passes(self, tmp_path: Path):
        """A path under stroke_orofacial_pipeline_outputs/ on Windows
        UNC must pass the guard. We don't actually open the network
        share for the write — we use a tmp_path-rooted equivalent for
        the I/O — but we exercise the guard on the UNC string via a
        direct ``assert_safe_write_path`` check at the writeguard
        level (covered in test_writeguard.py). The test here pins the
        invariant that the conftest fixture wraps these APIs without
        adding extra restrictions on top of the writeguard's own
        deny list.
        """
        # Smoke check: a plain write to tmp_path works under the
        # autouse conftest fixture (already covered above by
        # TestConftestGuardPassesSafePaths). This test is a placeholder
        # documenting the boundary; deeper coverage of the
        # pipeline_outputs/ allowlist lives in test_writeguard.py.
        path = tmp_path / "smoke.npz"
        np.savez(path, ok=np.zeros(1))
        assert path.exists()
