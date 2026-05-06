"""Test-scope fixtures + autouse safety guards.

Phase 7-pre-multi-half added the autouse ``_block_writes_to_legacy_paths``
fixture after the 2026-05-05 alignment-template overwrite incident
(see :mod:`stroke_orofacial._writeguard` module docstring + the
incident report in COWORK_SESSION_STATE.md). The fixture patches the
major write APIs (numpy savez / pandas to_parquet / pathlib write_*
+ replace) so any test that constructs a destination under a known-
legacy MICROSCOPE / Mac source-data root raises
:class:`stroke_orofacial._writeguard.WriteGuardError` instead of
silently overwriting production data.

This is layer 3 of the three-layer guard system:

  - Layer 1 (Commit 4 — paths.py resolver split): structural
    prevention. Production code only writes via ``_new`` resolvers
    that route through ``pipeline_outputs/`` (a safe tree).
  - Layer 2 (Commit 2 — writeguard module): runtime check. Production
    write sites can call ``assert_safe_write_path`` to defend against
    hand-constructed paths that bypass the resolver discipline.
  - Layer 3 (this fixture): test-time backstop. Catches any test
    that bypasses both the resolver split AND the production
    writeguard call. Autouse so no test can opt out by forgetting
    to apply it.

Production code outside pytest is NOT affected — the patches are
installed by ``monkeypatch`` which is fixture-scoped (test-only).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial._writeguard import assert_safe_write_path


# Captured at module import (before any test patches them) so the
# fixture below can dispatch through the real implementations after
# the writeguard check.
_ORIGINAL_NP_SAVEZ = np.savez
_ORIGINAL_NP_SAVEZ_COMPRESSED = np.savez_compressed
_ORIGINAL_DF_TO_PARQUET = pd.DataFrame.to_parquet
_ORIGINAL_PATH_WRITE_TEXT = Path.write_text
_ORIGINAL_PATH_WRITE_BYTES = Path.write_bytes
_ORIGINAL_PATH_REPLACE = Path.replace


def _guarded_savez(file, *args, **kwargs):
    """np.savez with a writeguard pre-check on ``file``."""
    assert_safe_write_path(file)
    return _ORIGINAL_NP_SAVEZ(file, *args, **kwargs)


def _guarded_savez_compressed(file, *args, **kwargs):
    """np.savez_compressed with a writeguard pre-check on ``file``."""
    assert_safe_write_path(file)
    return _ORIGINAL_NP_SAVEZ_COMPRESSED(file, *args, **kwargs)


def _guarded_to_parquet(self, path, *args, **kwargs):
    """DataFrame.to_parquet with a writeguard pre-check on ``path``.

    Method form: ``self`` is the DataFrame instance. The default
    behavior is preserved when ``path`` is None (pandas can return
    bytes when the path arg is omitted) — we only check truthy paths.
    """
    if path is not None:
        assert_safe_write_path(path)
    return _ORIGINAL_DF_TO_PARQUET(self, path, *args, **kwargs)


def _guarded_path_write_text(self, *args, **kwargs):
    """Path.write_text with writeguard on ``self``."""
    assert_safe_write_path(self)
    return _ORIGINAL_PATH_WRITE_TEXT(self, *args, **kwargs)


def _guarded_path_write_bytes(self, *args, **kwargs):
    """Path.write_bytes with writeguard on ``self``."""
    assert_safe_write_path(self)
    return _ORIGINAL_PATH_WRITE_BYTES(self, *args, **kwargs)


def _guarded_path_replace(self, target):
    """Path.replace with writeguard on ``target`` (the destination).

    Atomic-rename idiom — write_centered_parquet uses this to move
    a temp parquet into the final path. We must check ``target`` (the
    final dest), not ``self`` (the temp).
    """
    assert_safe_write_path(target)
    return _ORIGINAL_PATH_REPLACE(self, target)


@pytest.fixture(autouse=True)
def _block_writes_to_legacy_paths(monkeypatch):
    """Autouse safety net: block writes to legacy MICROSCOPE / Mac
    source-data paths during test execution.

    The fixture monkey-patches the major write APIs to call
    :func:`stroke_orofacial._writeguard.assert_safe_write_path` on
    the destination before delegating to the real implementation.
    Tests that use legitimate destinations (``tmp_path`` /
    ``stroke_orofacial_pipeline_outputs``) pass through unchanged.

    Patched APIs:
      - ``numpy.savez`` and ``numpy.savez_compressed``
      - ``pandas.DataFrame.to_parquet``
      - ``pathlib.Path.write_text`` / ``write_bytes`` / ``replace``

    Coverage rationale: the multi-half pipeline writes data only via
    these APIs (NPZ for licks + alignment, parquet for centered DLC,
    plus atomic-rename via Path.replace inside
    :func:`write_centered_parquet`). Other write APIs (e.g. raw
    ``open(..., 'w')``) are NOT patched; production code that writes
    via those should call ``assert_safe_write_path`` itself. This
    deliberately leaves a small surface uncovered — wrapping every
    write API in Python is intrusive and brittle. The targeted
    coverage above catches the incident class that triggered the
    guard system.

    Test-only: the patches are installed via ``monkeypatch`` which
    pytest reverts at fixture teardown. Production code paths
    (running the pipeline outside pytest) see unmodified write APIs.
    """
    monkeypatch.setattr(np, "savez", _guarded_savez)
    monkeypatch.setattr(np, "savez_compressed", _guarded_savez_compressed)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", _guarded_to_parquet)
    monkeypatch.setattr(Path, "write_text", _guarded_path_write_text)
    monkeypatch.setattr(Path, "write_bytes", _guarded_path_write_bytes)
    monkeypatch.setattr(Path, "replace", _guarded_path_replace)
    yield
    # monkeypatch undoes the setattrs at teardown; nothing extra here.
