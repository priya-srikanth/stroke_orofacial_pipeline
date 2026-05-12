"""Runtime safety: deny writes to known-legacy MICROSCOPE / Mac source-data roots.

Phase 7-pre-multi-half added this after the 2026-05-05 alignment-template
overwrite incident. Three legacy NPZs were corrupted by a test that
constructed write paths via ``PathResolver(output_root=tmp_path)`` —
``output_root`` only redirects ``pipeline_outputs()``, not
``alignment_templates_dir()``, and the alignment-template resolver
routes through the live MICROSCOPE share. The test wrote synthetic
data over real session artefacts.

The writeguard is layer 2 of the three-layer guard system (the
resolver split is layer 1 — structural prevention; the conftest
autouse fixture is layer 3 — test-time enforcement). It exists so any
production write site can call :func:`assert_safe_write_path` before
emitting; the function raises :class:`WriteGuardError` if the path
resolves under one of the deny roots listed in
``_LEGACY_DENY_ROOTS``.

Deny roots cover:

  - **Source data trees on MICROSCOPE** (DeepLabCut, raw wavesurfer,
    Rich's camera tree, the legacy `analysis/` subtree containing
    `session_processing3` + `basic_behavior_analysis3`).
  - **Mac mirrors** of the same trees (``/Volumes/Neurobio/MICROSCOPE/``)
    plus the Mac-local legacy data root and legacy GitHub repos
    (``/Users/Priya2/...``) per CLAUDE.md ground rules 1 + 2.

The new pipeline writes ONLY under
``microscope_pipeline_outputs/`` (or ``stroke_orofacial_pipeline_outputs/``,
the named alias under MICROSCOPE/Priya). That tree is NOT in the deny
list. Tests using ``PathResolver(output_root=tmp_path)`` write under
``tmp_path``, also not in the deny list.

If a future task legitimately needs to write to a legacy location
(e.g. a guarded restore script), it should NOT call this function on
that path — it should use a separate code path that documents the
intent. The writeguard is for unintentional writes; intentional
overrides are decisions, not API holes.
"""

from __future__ import annotations

import os

__all__ = ["WriteGuardError", "assert_safe_write_path", "is_safe_write_path"]


class WriteGuardError(RuntimeError):
    """Raised by :func:`assert_safe_write_path` when a write target
    resolves under a known-legacy MICROSCOPE / Mac source-data root.

    The error message includes the offending path AND the deny entry
    that matched, so the caller can diagnose the path-construction
    bug. See :mod:`stroke_orofacial._writeguard` module docstring for
    the rationale and the 2026-05-05 incident report.
    """


# Deny roots in their RAW form (Windows UNC + Mac POSIX).
# Normalized forms are computed once at import time.
_LEGACY_DENY_ROOTS_RAW: tuple[str, ...] = (
    # ---- Windows UNC: live MICROSCOPE share ----
    # DeepLabCut tree (alignment_templates, O2_analysis/{ANIMAL}/, DLC_train_config).
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut",
    # Legacy spout-behavior outputs: session_processing3/, basic_behavior_analysis3/
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\analysis",
    # Raw wavesurfer .h5 files (ground rule 1)
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\wavesurfer",
    # Rich's raw camera tree (.avi + timestamp .csv files; ground rule 1)
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Rich",

    # ---- Mac POSIX: same trees via /Volumes mount ----
    "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut",
    "/Volumes/Neurobio/MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp/analysis",
    "/Volumes/Neurobio/MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp/wavesurfer",
    "/Volumes/Neurobio/MICROSCOPE/Rich",

    # ---- Mac local: legacy data root + legacy repos ----
    # session_processing3/ + basic_behavior_analysis3/ Mac-local fallback
    # (paths.yaml local_processed_spout)
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis",
    # Raw WS Mac fallback
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer",
    # Legacy GitHub repos — CLAUDE.md ground rule 2 forbids modification
    "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya",
    "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp",
)


def _normalize(path: str | os.PathLike[str]) -> str:
    """Return a forward-slash, lowercase, normpath form of the input.

    Used for prefix comparison: legacy filesystems on the project
    span Windows UNC + Mac POSIX, both of which are effectively
    case-insensitive in practice. Lowercasing removes the false-
    negative class where a path differs from a deny root only in case
    (e.g. ``\\Research.Files...`` vs ``\\research.files...``).
    """
    s = str(path)
    if not s:
        return ""
    # Preserve UNC double-slash prefix on Windows. os.path.normpath
    # collapses internal redundancies but keeps the leading \\.
    normed = os.path.normpath(s)
    return normed.replace(os.sep, "/").lower()


# Precompute normalized deny roots once. Each entry's normalized form
# carries a trailing slash so prefix matching is unambiguous —
# "/users/priya2/foo" is NOT a parent of "/users/priya2/foobar".
_LEGACY_DENY_NORMALIZED: tuple[str, ...] = tuple(
    _normalize(r).rstrip("/") + "/" for r in _LEGACY_DENY_ROOTS_RAW
)


def assert_safe_write_path(path: str | os.PathLike[str]) -> None:
    """Raise :class:`WriteGuardError` if ``path`` is under a known-legacy
    source-data root.

    Intended to be called at every production write site that emits
    NPZ / parquet / .json / .csv files. Cheap (a handful of
    string-prefix comparisons) and idempotent — safe to call from
    inside every loop iteration.

    Parameters
    ----------
    path : str or PathLike
        Destination path for an upcoming write. Need not exist on
        disk; the check is purely syntactic against
        :data:`_LEGACY_DENY_ROOTS_RAW`.

    Raises
    ------
    WriteGuardError
        If the normalized form of ``path`` falls under any deny root.
    """
    candidate = _normalize(path)
    if not candidate:
        return  # empty path; let the caller's own validation handle it
    # Compare against deny + "/" so that a path EQUAL to the deny
    # root (writing AT the directory itself, which would mean creating
    # a file with that name) is caught too.
    candidate_with_sep = candidate.rstrip("/") + "/"
    for deny in _LEGACY_DENY_NORMALIZED:
        if (
            candidate_with_sep.startswith(deny)
            or candidate == deny.rstrip("/")
        ):
            raise WriteGuardError(
                f"refusing to write to legacy source-data path:\n"
                f"  candidate: {path}\n"
                f"  deny root: {deny.rstrip('/')}\n\n"
                f"This path is under a legacy MICROSCOPE / Mac tree the "
                f"new pipeline must not modify (CLAUDE.md ground rule 1: "
                f"never modify source data; or ground rule 2: never "
                f"modify legacy repos). New pipeline outputs go under "
                f"stroke_orofacial_pipeline_outputs/. If you intended to "
                f"write to the legacy location (e.g. a guarded restore), "
                f"do so via a separate code path that documents intent."
            )


def is_safe_write_path(path: str | os.PathLike[str]) -> bool:
    """Return True iff :func:`assert_safe_write_path` would NOT raise on ``path``.

    Convenience wrapper for callers that want to branch on safety
    rather than raise. Production write sites should prefer
    :func:`assert_safe_write_path` so the error message is preserved.
    """
    try:
        assert_safe_write_path(path)
    except WriteGuardError:
        return False
    return True
