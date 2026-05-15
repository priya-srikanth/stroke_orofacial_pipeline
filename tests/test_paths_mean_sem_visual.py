"""Tests for ``PathResolver.mean_sem_visual_dir`` (Phase 7a.6).

Bodypart-parametric mean/SEM visual gate output directory resolver.
Architecture: single resolver, ``bodypart`` argument either ``"tongue"``
or ``"jaw"`` (Q2 locked 2026-05-01); returns

    {outputs}/dlc_kinematics/mean_sem/{bodypart}/{center_mode}/
    toneAligned_{pre_ms}pre-{post_ms}post/{plot_family}/{animal}/

Q6 / Q7 are exercised explicitly:

- Q6: lowercase ``{bodypart}`` only — the consolidated tree never gets
  the legacy capital-T tongue subdir bug.
- Q7: per-window ``toneAligned_{pre}-{post}`` subdir layout for
  BOTH bodyparts (tongue's flat legacy layout is not replicated).

The resolver is a directory resolver, not a file resolver, so no
parent mkdir occurs eagerly (matches the
``tongue_visual_qc_dir`` / ``tongue_jaw_mismatch_qc_dir`` convention).
"""

from __future__ import annotations

import platform

import pytest

from stroke_orofacial.paths import PathResolver

# Match the host platform so tmp_path-derived strings parse cleanly
# (PureWindowsPath for Windows tmp paths like "C:/Users/...",
# PurePosixPath for Mac/Linux). Mirrors the convention in test_paths.py.
_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


# Plot-family names exercised by the parametric tests. These are the
# legacy subdir names found in the Phase 7a.6 Task 1 output inventory.
_PLOT_FAMILIES = (
    "individual_sessions",
    "trial_overlays",
    "session_overlays",
    "binned_overlays",
    "mean_xy_overlays",
)


class TestMeanSemVisualDir:
    """``mean_sem_visual_dir`` — bodypart-parametric directory resolver.

    Phase 7a.6 (locked 2026-05-01):
    - Q2: bodypart-parametric single resolver (``bodypart`` arg).
    - Q6: lowercase ``{bodypart}`` only (no capital-T legacy bug).
    - Q7: per-window ``toneAligned_{pre}pre-{post}post`` subdir layout
      for both bodyparts.

    Window units (deviation from kickoff): the legacy filename + jaw
    subdir convention is millisecond-based
    (``toneAligned_100pre-1000post/``). The kickoff template sketched
    seconds (``(2.0, 5.0) → toneAligned_2-5``); we use milliseconds
    (int) here to keep visual-gate filename comparison bit-comparable
    with legacy outputs.
    """

    @pytest.mark.parametrize(
        ("bodypart", "center_mode"),
        [
            ("tongue", "centered_spout_midpoint"),
            ("jaw", "centered_eye_midpoint"),
        ],
    )
    @pytest.mark.parametrize("plot_family", _PLOT_FAMILIES)
    def test_path_layout(
        self, monkeypatch, tmp_path, bodypart, center_mode, plot_family
    ):
        """Bodypart × plot-family path layout matches the locked Q7 layout."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.mean_sem_visual_dir(
            bodypart,
            center_mode=center_mode,
            tone_pre_ms=100,
            tone_post_ms=1000,
            plot_family=plot_family,
            animal="PS46",
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "mean_sem"
            / bodypart
            / center_mode
            / "toneAligned_100pre-1000post"
            / plot_family
            / "PS46"
        )
        assert path == expected
        # Q6 acceptance: lowercase bodypart only — no capital-T anywhere
        # in the resolved tree. Renderer / consumer code must not write
        # to ``Tongue_*`` paths.
        assert "Tongue" not in str(path)
        # Directory resolver convention: no eager mkdir.
        assert not path.exists()
        # Ancestor up to {outputs}/dlc_kinematics also remains uncreated.
        # Phase 7a.5 mismatch_qc_dir test enforces the same invariant.
        assert not (tmp_path / "dlc_kinematics" / "mean_sem").exists()

    @pytest.mark.parametrize(
        ("pre_ms", "post_ms", "expected_subdir"),
        [
            (100, 1000, "toneAligned_100pre-1000post"),
            (500, 5000, "toneAligned_500pre-5000post"),
            (200, 2500, "toneAligned_200pre-2500post"),
            (0, 8000, "toneAligned_0pre-8000post"),
        ],
    )
    def test_window_subdir_format(
        self, monkeypatch, tmp_path, pre_ms, post_ms, expected_subdir
    ):
        """Window subdir renders as ``toneAligned_{pre}pre-{post}post`` (ms)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.mean_sem_visual_dir(
            "tongue",
            center_mode="centered_spout_midpoint",
            tone_pre_ms=pre_ms,
            tone_post_ms=post_ms,
            plot_family="individual_sessions",
            animal="PS46",
        )
        # The window dir is the 5th component from the end:
        # mean_sem / tongue / center_mode / WINDOW / plot_family / animal
        assert path.parts[-3] == expected_subdir
        # Confirm the full window-dir slug appears verbatim.
        assert expected_subdir in str(path)

    def test_q2_bodypart_parametric_single_resolver(
        self, monkeypatch, tmp_path
    ):
        """Q2 (locked 2026-05-01): bodypart-parametric single resolver.

        Tongue and jaw share the resolver entry point, differing only in
        the ``bodypart`` argument and the per-bodypart ``center_mode``.
        Path structure is identical otherwise.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        common = dict(
            tone_pre_ms=100,
            tone_post_ms=1000,
            plot_family="individual_sessions",
            animal="PS49",
        )
        tongue = resolver.mean_sem_visual_dir(
            "tongue", center_mode="centered_spout_midpoint", **common,
        )
        jaw = resolver.mean_sem_visual_dir(
            "jaw", center_mode="centered_eye_midpoint", **common,
        )
        # Same prefix up to the bodypart slot.
        assert tongue.parts[:-5] == jaw.parts[:-5]
        # Diverge at bodypart and center_mode.
        assert tongue.parts[-5] == "tongue"
        assert jaw.parts[-5] == "jaw"
        assert tongue.parts[-4] == "centered_spout_midpoint"
        assert jaw.parts[-4] == "centered_eye_midpoint"
        # Identical from the window slot onward.
        assert tongue.parts[-3:] == jaw.parts[-3:]

    def test_q6_lowercase_tongue_no_capital_t(
        self, monkeypatch, tmp_path
    ):
        """Q6 (locked 2026-05-01): lowercase tongue subdir only.

        Legacy Cell 31 wrote to BOTH ``mouse_Tongue_kinematics/`` (capital
        T, the bug) and ``mouse_tongue_kinematics/`` (lowercase) on
        MICROSCOPE; consolidated tree uses lowercase only. This is path-
        structural, not a string-replace — assert the resolver never
        emits capital-T anywhere even when called with the lowercase
        ``"tongue"`` arg.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.mean_sem_visual_dir(
            "tongue",
            center_mode="centered_spout_midpoint",
            tone_pre_ms=100,
            tone_post_ms=1000,
            plot_family="individual_sessions",
            animal="PS46",
        )
        # Capital-T tongue would only appear if a downstream consumer
        # mistakenly assembled paths with the capitalized token. The
        # resolver path components are deterministic; verify directly.
        for part in path.parts:
            assert "Tongue" not in part, (
                f"capital-T leak in path component {part!r} (Q6 violation)"
            )

    def test_q7_uniform_per_window_layout_for_both_bodyparts(
        self, monkeypatch, tmp_path
    ):
        """Q7 (locked 2026-05-01): tongue adopts jaw's per-window subdir.

        Both bodyparts produce ``toneAligned_{pre}pre-{post}post/`` as
        an explicit dir component. Tongue's legacy flat-layout
        (saved files at the family-subdir level with the window encoded
        only in the filename, not the dir tree) is NOT replicated.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        for bodypart, center_mode in (
            ("tongue", "centered_spout_midpoint"),
            ("jaw", "centered_eye_midpoint"),
        ):
            path = resolver.mean_sem_visual_dir(
                bodypart,
                center_mode=center_mode,
                tone_pre_ms=100,
                tone_post_ms=1000,
                plot_family="binned_overlays",
                animal="PS47",
            )
            assert path.parts[-3] == "toneAligned_100pre-1000post"

    def test_no_eager_mkdir(self, monkeypatch, tmp_path):
        """Resolver returns the path without creating any ancestor dirs.

        Mirrors the directory-resolver convention shared with
        ``tongue_visual_qc_dir``, ``tongue_jaw_mismatch_qc_dir``, and
        ``tongue_jaw_mismatch_cross_session_dir``: rendering side
        creates the directory.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.mean_sem_visual_dir(
            "jaw",
            center_mode="centered_eye_midpoint",
            tone_pre_ms=500,
            tone_post_ms=5000,
            plot_family="overlays",
            animal="PS48",
        )
        # Nothing along the path should exist yet — verify each ancestor
        # all the way up to {outputs}/dlc_kinematics.
        cursor = path
        while cursor != tmp_path:
            assert not cursor.exists(), f"{cursor} unexpectedly exists"
            cursor = cursor.parent
        # Caller-driven mkdir succeeds (sanity-check the round-trip).
        path.mkdir(parents=True)
        assert path.is_dir()

    def test_arbitrary_plot_family_passed_through(
        self, monkeypatch, tmp_path
    ):
        """Resolver does not validate ``plot_family``.

        Phase 7a.6 Task 4 may name new plot families during the module
        port (e.g., separate dirs for mean_trace and mean_video, even
        though they currently share ``mean_xy_overlays`` legacy-side).
        The resolver passes the value through verbatim; it is the
        caller's responsibility to use a stable token. Exercise this
        with a non-canonical value.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.mean_sem_visual_dir(
            "tongue",
            center_mode="centered_spout_midpoint",
            tone_pre_ms=100,
            tone_post_ms=1000,
            plot_family="some_future_family",
            animal="PS54",
        )
        assert path.parts[-2] == "some_future_family"
