"""Phase 7a.6 Task 4 (C4.1) — smoke tests for ``mean_sem_visual``.

Lightweight tests covering:

- Pure-function helpers (``_mean_sem``, ``_snippet``, ``_stack_snippets``,
  day-bin layout, ``_compute_binned``).
- End-to-end plot emission via the public ``build_*`` entry points by
  constructing synthetic ``SessionAggregates`` + ``CohortAggregates`` and
  passing them through the ``cohort=`` kwarg (skips the upstream parquet
  + spout_behavior loader).

Full parametric coverage (window formatting, Q6 / Q7 enforcement,
multi-bin handling, ``with_frame_timestamps``, etc.) lands in Task 5
under ``tests/test_mean_sem_visual.py``.
"""

from __future__ import annotations

import datetime
import platform
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.dlc_kinematics import mean_sem_visual as msv
from stroke_orofacial.paths import PathResolver

_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


# ---------------------------------------------------------------------------
# Pure-function helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Direct ports of legacy ``mean_sem`` / ``snippet`` / ``stack`` etc.
    Verify NaN handling + edge cases match the legacy contract.
    """

    def test_mean_sem_finite_input(self):
        A = np.array([[1.0, 2.0, 3.0], [3.0, 4.0, 5.0], [5.0, 6.0, 7.0]])
        m, s = msv._mean_sem(A)
        np.testing.assert_allclose(m, [3.0, 4.0, 5.0])
        # Legacy uses np.nanstd default (ddof=0). For column [1, 3, 5]:
        #   std0 = sqrt(((1-3)^2 + 0 + (5-3)^2) / 3) = sqrt(8/3)
        #   SEM = std0 / sqrt(3 finite samples)
        expected_sem = np.sqrt(8 / 3) / np.sqrt(3)
        np.testing.assert_allclose(s, np.full(3, expected_sem))

    def test_mean_sem_with_nan(self):
        A = np.array([[1.0, np.nan], [3.0, 4.0]])
        m, s = msv._mean_sem(A)
        np.testing.assert_allclose(m, [2.0, 4.0])
        # Column 0: 2 finite samples; column 1: 1 finite sample.
        np.testing.assert_allclose(s[0], 1.0 / np.sqrt(2))
        np.testing.assert_allclose(s[1], 0.0)

    def test_mean_sem_empty(self):
        A = np.zeros((0, 5))
        m, s = msv._mean_sem(A)
        assert m.shape == (5,)
        assert s.shape == (5,)
        assert np.all(np.isnan(m))
        assert np.all(np.isnan(s))

    def test_snippet_within_range(self):
        arr = np.arange(20.0)
        s = msv._snippet(arr, c=10, pre_f=2, post_f=3)
        np.testing.assert_array_equal(s, [8.0, 9.0, 10.0, 11.0, 12.0, 13.0])

    def test_snippet_left_edge_nan_pad(self):
        arr = np.arange(20.0)
        s = msv._snippet(arr, c=1, pre_f=3, post_f=2)
        # First two slots NaN-padded (out of range), then 0, 1, 2, 3.
        assert np.all(np.isnan(s[:2]))
        np.testing.assert_array_equal(s[2:], [0.0, 1.0, 2.0, 3.0])

    def test_snippet_right_edge_nan_pad(self):
        arr = np.arange(10.0)
        s = msv._snippet(arr, c=8, pre_f=2, post_f=3)
        # 6, 7, 8, 9, then NaN, NaN.
        np.testing.assert_array_equal(s[:4], [6.0, 7.0, 8.0, 9.0])
        assert np.all(np.isnan(s[4:]))

    def test_stack_snippets_empty_centers(self):
        arr = np.arange(10.0)
        out = msv._stack_snippets(arr, centers=[], pre_f=2, post_f=3)
        assert out.shape == (0, 6)

    def test_stack_snippets_multi(self):
        arr = np.arange(20.0)
        out = msv._stack_snippets(
            arr, centers=[5, 10], pre_f=1, post_f=1,
        )
        np.testing.assert_array_equal(out, [[4, 5, 6], [9, 10, 11]])

    def test_make_rel_day_bins_pre_only(self):
        rel = np.array([-6, -5, -4, -3, -2, -1, 0])
        bins = msv._make_rel_day_bins(rel, bin_size=2)
        # Bins anchored at 0 backward: (-1,0), (-3,-2), (-5,-4), (-7,-6).
        # Sorted by lo: (-7,-6), (-5,-4), (-3,-2), (-1,0).
        assert bins == [(-7, -6), (-5, -4), (-3, -2), (-1, 0)]

    def test_make_rel_day_bins_pre_and_post(self):
        rel = np.array([-3, -2, -1, 0, 1, 2, 3, 4, 5])
        bins = msv._make_rel_day_bins(rel, bin_size=2)
        # Pre: (-3,-2), (-1,0). Post: (1,2), (3,4), (5,6) — extends past 5.
        assert bins == [(-3, -2), (-1, 0), (1, 2), (3, 4), (5, 6)]

    def test_make_rel_day_bins_empty(self):
        bins = msv._make_rel_day_bins(np.array([]), bin_size=2)
        assert bins == []

    def test_make_rel_day_bins_min_size_one(self):
        rel = np.array([-2, -1, 0, 1, 2])
        bins = msv._make_rel_day_bins(rel, bin_size=1)
        # bin_size=1 → singleton bins.
        assert bins == [(-2, -2), (-1, -1), (0, 0), (1, 1), (2, 2)]

    def test_assign_to_bin(self):
        bins = [(-3, -2), (-1, 0), (1, 2), (3, 4)]
        assert msv._assign_to_bin(-3, bins) == (-3, -2)
        assert msv._assign_to_bin(0, bins) == (-1, 0)
        assert msv._assign_to_bin(2, bins) == (1, 2)
        assert msv._assign_to_bin(99, bins) is None

    def test_finite_minmax(self):
        a = np.array([1.0, 2.0, np.nan, 4.0])
        b = np.array([0.5, np.inf, np.nan])
        lo, hi = msv._finite_minmax([a, b, None])
        assert lo == 0.5
        assert hi == 4.0

    def test_finite_minmax_all_nan(self):
        a = np.array([np.nan, np.nan])
        lo, hi = msv._finite_minmax([a])
        assert np.isnan(lo) and np.isnan(hi)

    def test_pad_axis_limits(self):
        lo, hi = msv._pad_axis_limits(0.0, 10.0, frac=0.05)
        assert lo == pytest.approx(-0.5)
        assert hi == pytest.approx(10.5)

    def test_pad_axis_limits_singleton(self):
        # Singleton range → ±1 (matches legacy).
        lo, hi = msv._pad_axis_limits(5.0, 5.0)
        assert (lo, hi) == (4.0, 6.0)


# ---------------------------------------------------------------------------
# Synthetic SessionAggregates + CohortAggregates
# ---------------------------------------------------------------------------


def _make_synthetic_session(
    animal: str,
    date: datetime.date,
    bodypart: str,
    rel_day: int | None,
    fps: float = 250.0,
    pre_ms: float = 100.0,
    post_ms: float = 1000.0,
    n_L_trials: int = 8,
    n_R_trials: int = 6,
    seed: int = 0,
) -> msv.SessionAggregates:
    """Generate a SessionAggregates with deterministic random arrays.

    Used by smoke tests to bypass the parquet + spout_behavior loader.
    """
    rng = np.random.default_rng(seed)
    pre_f = int(round(pre_ms / 1000.0 * fps))
    post_f = int(round(post_ms / 1000.0 * fps))
    T = pre_f + post_f + 1
    t_ms = np.arange(-pre_f, post_f + 1) * (1000.0 / fps)

    # Synthetic per-trial arrays (rows = trials, columns = time bins).
    Ayl = rng.normal(loc=0.0, scale=5.0, size=(n_L_trials, T))
    Ayr = rng.normal(loc=2.0, scale=5.0, size=(n_R_trials, T))
    Axl = rng.normal(loc=-3.0, scale=2.0, size=(n_L_trials, T))
    Axr = rng.normal(loc=3.0, scale=2.0, size=(n_R_trials, T))
    myl, syl = msv._mean_sem(Ayl)
    myr, syr = msv._mean_sem(Ayr)
    mxl, sxl = msv._mean_sem(Axl)
    mxr, sxr = msv._mean_sem(Axr)

    legend = (
        msv._dlabel(rel_day) if rel_day is not None
        else date.strftime("%Y%m%d")
    )

    return msv.SessionAggregates(
        animal=animal,
        date=date,
        bodypart=bodypart,
        fps=fps,
        n_frames=20_000,
        pre_ms=pre_ms,
        post_ms=post_ms,
        pre_f=pre_f,
        post_f=post_f,
        t_ms=t_ms,
        n_L=n_L_trials,
        n_R=n_R_trials,
        Ayl=Ayl, Ayr=Ayr, Axl=Axl, Axr=Axr,
        myl=myl, syl=syl, myr=myr, syr=syr,
        mxl=mxl, sxl=sxl, mxr=mxr, sxr=sxr,
        rel_day=rel_day,
        legend=legend,
        interp_version="v5p3",
        source_path=Path(f"/synth/{animal}_{date.strftime('%Y%m%d')}.parquet"),
    )


def _make_synthetic_cohort(
    animal: str,
    bodypart: str,
    n_pre: int = 3,
    n_post: int = 3,
    fps: float = 250.0,
    pre_ms: float = 100.0,
    post_ms: float = 1000.0,
    bin_days: int = 1,
) -> msv.CohortAggregates:
    """Build a CohortAggregates with N synthetic sessions spanning d-N..d+N."""
    sessions: list[msv.SessionAggregates] = []
    base_date = datetime.date(2025, 3, 7)
    for k in range(-n_pre, n_post + 1):
        if k == 0:
            continue
        d = base_date + datetime.timedelta(days=(k + n_pre + 1))
        sessions.append(
            _make_synthetic_session(
                animal=animal, date=d, bodypart=bodypart,
                rel_day=k,
                fps=fps, pre_ms=pre_ms, post_ms=post_ms,
                seed=k + 100,
            ),
        )

    pre_f = sessions[0].pre_f
    post_f = sessions[0].post_f
    t_ms = sessions[0].t_ms

    # Cohort axis limits — use the actual mean+SEM extents.
    y_lo, y_hi = msv._finite_minmax([
        *(s.myl - s.syl for s in sessions),
        *(s.myl + s.syl for s in sessions),
        *(s.myr - s.syr for s in sessions),
        *(s.myr + s.syr for s in sessions),
    ])
    x_lo, x_hi = msv._finite_minmax([
        *(s.mxl - s.sxl for s in sessions),
        *(s.mxl + s.sxl for s in sessions),
        *(s.mxr - s.sxr for s in sessions),
        *(s.mxr + s.sxr for s in sessions),
    ])
    y_lim = msv._pad_axis_limits(y_lo, y_hi, frac=0.05)
    x_lim = msv._pad_axis_limits(x_lo, x_hi, frac=0.05)
    trial_y_lim = (-30.0, 30.0)
    trial_x_lim = (-15.0, 15.0)

    rel_days = np.array([s.rel_day for s in sessions], float)
    bins = msv._make_rel_day_bins(rel_days, bin_size=bin_days)
    binned = msv._compute_binned(sessions, bins)

    return msv.CohortAggregates(
        bodypart=bodypart,
        animal=animal,
        pre_ms=pre_ms,
        post_ms=post_ms,
        pre_f=pre_f,
        post_f=post_f,
        fps=fps,
        t_ms=t_ms,
        sessions=sessions,
        y_lim=y_lim,
        x_lim=x_lim,
        trial_y_lim=trial_y_lim,
        trial_x_lim=trial_x_lim,
        bin_days=bin_days,
        bins=bins,
        binned=binned,
        cam="cam2",
        interp_version="v5p3",
        suffix=(
            f"{sessions[0].date.strftime('%Y%m%d')}-"
            f"{sessions[-1].date.strftime('%Y%m%d')}_"
            f"{int(pre_ms)}pre-{int(post_ms)}post"
        ),
    )


class TestComputeBinned:
    """``_compute_binned`` aggregates per-session means within day-bins."""

    def test_compute_binned_one_session_per_bin(self):
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)
        # 6 sessions × bin_days=1 → 6 singleton bins → each bin has 1 session.
        assert len(cohort.binned) == 6
        for entry in cohort.binned:
            assert entry["n_sessions"] == 1
            # SEM across-sessions for n=1 → 0.
            assert np.allclose(entry["syl"], 0.0)

    def test_compute_binned_multiple_sessions_per_bin(self):
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=2)
        # bin_days=2 over rel_days [-3,-2,-1,1,2,3] with skip of 0.
        # Pre bins (-3,-2), (-1,0); post bins (1,2), (3,4). Sessions in
        # each: (-3,-2)=2, (-1,0)=1, (1,2)=2, (3,4)=1. Some bins have
        # >1 session → SEM should be finite & nonzero.
        n_per_bin = sorted(b["n_sessions"] for b in cohort.binned)
        assert n_per_bin == [1, 1, 2, 2]
        any_nonzero_sem = any(
            np.any(np.asarray(b["syl"]) > 0.0)
            for b in cohort.binned if b["n_sessions"] > 1
        )
        assert any_nonzero_sem


# ---------------------------------------------------------------------------
# Smoke tests for the public build_* entry points
# ---------------------------------------------------------------------------


class TestBuildPerSession:
    """End-to-end PNG emission via build_individual_sessions /
    build_trial_overlays. Use synthetic ``cohort=`` to bypass upstream
    parquet + spout_behavior loading.
    """

    def test_build_individual_sessions_emits_png(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)
        target_date = cohort.sessions[0].date

        out_path = msv.build_individual_sessions(
            "tongue", "PS46", target_date, resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert out_path is not None
        assert out_path.exists()
        assert out_path.suffix == ".png"
        # Q6: lowercase tongue dir on path.
        assert "Tongue" not in str(out_path)
        # Q7: per-window subdir present.
        assert "rewardAligned_100pre-1000post" in str(out_path)
        # Filename matches legacy ``meanSEM_2x2`` pattern.
        assert "meanSEM_2x2" in out_path.name

    def test_build_trial_overlays_emits_png(self, monkeypatch, tmp_path):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "jaw", bin_days=1)
        target_date = cohort.sessions[0].date

        out_path = msv.build_trial_overlays(
            "jaw", "PS46", target_date, resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert out_path is not None
        assert out_path.exists()
        assert "meanSEM_2x2_trials" in out_path.name
        assert "rewardAligned_100pre-1000post" in str(out_path)

    def test_build_individual_sessions_skip_uses_existing(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)
        target_date = cohort.sessions[0].date

        # First call writes.
        first = msv.build_individual_sessions(
            "tongue", "PS46", target_date, resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert first is not None
        first_mtime = first.stat().st_mtime_ns

        # Second call with overwrite="skip" should NOT rewrite.
        second = msv.build_individual_sessions(
            "tongue", "PS46", target_date, resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="skip",
        )
        assert second == first
        assert second.stat().st_mtime_ns == first_mtime

    def test_build_individual_sessions_unknown_date_returns_none(
        self, monkeypatch, tmp_path,
    ):
        """When ``date`` isn't in the cohort, return None gracefully."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)
        out_path = msv.build_individual_sessions(
            "tongue", "PS46", datetime.date(1999, 1, 1), resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert out_path is None


class TestBuildCohort:
    """End-to-end PNG emission via build_session_overlays /
    build_binned_overlays.
    """

    def test_build_session_overlays_emits_4_pngs(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)

        paths = msv.build_session_overlays(
            "tongue", "PS46", resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert len(paths) == 4
        names = sorted(p.name for p in paths)
        # Y/X × L/R = 4 plots.
        assert any("overlay_Y_mouseLrewards" in n for n in names)
        assert any("overlay_Y_mouseRrewards" in n for n in names)
        assert any("overlay_X_mouseLrewards" in n for n in names)
        assert any("overlay_X_mouseRrewards" in n for n in names)
        for p in paths:
            assert p.exists()
            assert "Tongue" not in str(p)  # Q6

    def test_build_binned_overlays_emits_4_pngs(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "jaw", bin_days=2)
        # The synthetic cohort has stroke-relative-day metadata so the
        # binned aggregate should be non-empty.
        assert cohort.binned

        paths = msv.build_binned_overlays(
            "jaw", "PS46", resolver,
            reward_pre_ms=500, reward_post_ms=5000,
            cohort=cohort, overwrite="force",
        )
        assert len(paths) == 4
        for p in paths:
            assert p.exists()
            assert "BIN2d" in p.name

    def test_build_binned_overlays_no_bins_returns_empty(
        self, monkeypatch, tmp_path,
    ):
        """Cohort without binned aggregates → no-op (returns ``[]``)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", "tongue", bin_days=1)
        # Strip the binned aggregate from the synthetic cohort.
        cohort_no_bins = msv.CohortAggregates(
            bodypart=cohort.bodypart, animal=cohort.animal,
            pre_ms=cohort.pre_ms, post_ms=cohort.post_ms,
            pre_f=cohort.pre_f, post_f=cohort.post_f, fps=cohort.fps,
            t_ms=cohort.t_ms, sessions=cohort.sessions,
            y_lim=cohort.y_lim, x_lim=cohort.x_lim,
            trial_y_lim=cohort.trial_y_lim, trial_x_lim=cohort.trial_x_lim,
            bin_days=cohort.bin_days, bins=[], binned=[],
            cam=cohort.cam, interp_version=cohort.interp_version,
            suffix=cohort.suffix,
        )
        paths = msv.build_binned_overlays(
            "tongue", "PS46", resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort_no_bins, overwrite="force",
        )
        assert paths == []


# ---------------------------------------------------------------------------
# Bodypart parametricity (Q2 lock)
# ---------------------------------------------------------------------------


class TestBodypartParametric:
    """Q2: same module entry point handles both bodyparts; only filename
    + path tokens differ.
    """

    @pytest.mark.parametrize("bodypart", ["tongue", "jaw"])
    def test_individual_sessions_works_for_both_bodyparts(
        self, monkeypatch, tmp_path, bodypart,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        cohort = _make_synthetic_cohort("PS46", bodypart, bin_days=1)
        target_date = cohort.sessions[0].date
        out_path = msv.build_individual_sessions(
            bodypart, "PS46", target_date, resolver,
            reward_pre_ms=100, reward_post_ms=1000,
            cohort=cohort, overwrite="force",
        )
        assert out_path is not None
        assert out_path.exists()
        # Bodypart slot in path matches input.
        assert f"/mean_sem/{bodypart}/" in str(out_path).replace("\\", "/")

    def test_unknown_bodypart_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        # The cohort builder rejects unknown bodyparts internally via
        # ``_KNOWN_BODYPARTS`` check.
        with pytest.raises(ValueError, match="bodypart must be one of"):
            msv.build_cohort_aggregates(
                "fake_bodypart", "PS46", resolver,
                reward_pre_ms=100, reward_post_ms=1000,
            )
