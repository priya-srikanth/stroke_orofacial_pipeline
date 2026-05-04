"""Phase 7a.4 — unit tests for the Cell 50 visual gate renderer.

Smoke + schema only. Visual fidelity is the parity harness's job
(Task 5 visual-gate runner against legacy MICROSCOPE PNGs).

All tests build synthetic :class:`TongueVisualBundle` instances directly
(via ``_make_synthetic_bundle``) — no upstream parquet fixture is needed
because the renderer consumes the bundle in-memory. Every test that
invokes a writer uses :class:`PathResolver` with ``output_root=tmp_path``
per :doc:`docs/testing-conventions.md`.
"""

from __future__ import annotations

import datetime
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # match the production module's backend

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    TongueVisualBundle,
)
from stroke_orofacial.dlc_kinematics.tongue_visual import (  # noqa: E402
    _plot_first_peak_aligned,
    _plot_per_trial_qc_traces,
    _plot_phase_aligned_angle,
    _plot_reward_aligned,
    _plot_xy_by_phase,
    render_tongue_qc_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402


# ============================================================================
# Synthetic-bundle fixture
# ============================================================================


def _make_synthetic_bundle(
    *,
    animal: str = "PS50",
    date: datetime.date = datetime.date(2025, 3, 19),
    n_trials_per_side: int = 4,
    sides: Sequence[str] = ("L", "R"),
    fps: float = 250.0,
    plot_win_ms: tuple[float, float] = (0.0, 1000.0),
    detect_win_ms: tuple[float, float] = (70.0, 800.0),
    first_peak_align_win_ms: tuple[float, float] = (-100.0, 400.0),
    n_phase_bins: int = 18,  # smaller than production 72 — keeps fixture light
    n_peaks_per_trial: int = 3,
    seed: int = 7,
) -> TongueVisualBundle:
    """Build a small but realistic :class:`TongueVisualBundle`.

    - ``df_trials`` carries one row per trial with array-snippet columns
      shaped per ``plot_win_ms`` and ``first_peak_align_win_ms``.
    - ``df_bouts`` mixes bout-summary rows (peak_t_ms NaN) and per-peak
      rows (bout_t0_ms preserved across both — the renderer queries
      both subsets by NaN-mask of ``peak_t_ms``).
    - ``df_phase`` provides multi-bout per-frame phase rows for at least
      one trial per side, populated across phase bins.
    - ``angle_per_frame`` is a small synthetic session trace.
    """
    rng = np.random.default_rng(seed)

    pre_f = max(0, int(np.floor(-plot_win_ms[0] / 1000.0 * fps)))
    post_f = max(0, int(np.ceil(plot_win_ms[1] / 1000.0 * fps)))
    snip_len = pre_f + post_f + 1
    t_ms = (np.arange(-pre_f, post_f + 1, dtype=np.float64) / fps) * 1000.0

    pre_fp = max(0, int(np.floor(-first_peak_align_win_ms[0] / 1000.0 * fps)))
    post_fp = max(0, int(np.ceil(first_peak_align_win_ms[1] / 1000.0 * fps)))
    fp_len = pre_fp + post_fp + 1
    t_fp = (np.arange(-pre_fp, post_fp + 1, dtype=np.float64) / fps) * 1000.0

    phase_bin_edges = np.linspace(0.0, 1.0, n_phase_bins + 1, dtype=np.float64)
    phase_bin_centers = 0.5 * (phase_bin_edges[:-1] + phase_bin_edges[1:])

    trial_rows: list[dict] = []
    bout_rows: list[dict] = []
    phase_rows: list[dict] = []
    trial_index_global = 0
    for side in sides:
        for i in range(n_trials_per_side):
            # Base traces with a slight per-trial offset for visual variation.
            base = 30.0 * np.sin(2 * np.pi * t_ms / 500.0)
            noise = rng.normal(0, 1.0, size=snip_len)
            y_snip = base + 100.0 + noise
            angle_snip = base * (1 if side == "L" else -1) + rng.normal(0, 0.5, size=snip_len)

            # Build a bout structure — n_peaks_per_trial peaks evenly
            # spaced inside detect_win_ms.
            peak_t_arr = np.linspace(
                detect_win_ms[0] + 50.0, detect_win_ms[1] - 50.0,
                n_peaks_per_trial,
            )
            peak_local_idxs = np.searchsorted(t_ms, peak_t_arr)
            peak_y = np.array([float(y_snip[idx]) for idx in peak_local_idxs])
            peak_x = rng.normal(0, 5, size=n_peaks_per_trial)
            angle_at_peaks = np.array(
                [float(angle_snip[idx]) for idx in peak_local_idxs]
            )

            # Bout time bounds (single multi-lick bout per trial; legacy
            # half-ILI extension).
            lead = 0.5 * (peak_t_arr[1] - peak_t_arr[0])
            tail = 0.5 * (peak_t_arr[-1] - peak_t_arr[-2])
            bt0 = float(peak_t_arr[0] - lead)
            bt1 = float(peak_t_arr[-1] + tail)

            # Bout angle masks.
            angle_allbouts = np.full_like(angle_snip, np.nan)
            angle_firstbout = np.full_like(angle_snip, np.nan)
            angle_firstmulti = np.full_like(angle_snip, np.nan)
            ib_lo = int(max(0, np.searchsorted(t_ms, bt0, side="left")))
            ib_hi = int(min(snip_len, np.searchsorted(t_ms, bt1, side="right")))
            angle_allbouts[ib_lo:ib_hi] = angle_snip[ib_lo:ib_hi]
            angle_firstbout[ib_lo:ib_hi] = angle_snip[ib_lo:ib_hi]
            angle_firstmulti[ib_lo:ib_hi] = angle_snip[ib_lo:ib_hi]

            # First-peak-aligned snippet — just synthetic.
            angle_firstpeak = (
                30.0 * np.sin(2 * np.pi * t_fp / 300.0)
                + rng.normal(0, 0.5, size=fp_len)
            )

            trial_rows.append({
                "side": side,
                "trial_index": trial_index_global,
                "n_peaks": int(n_peaks_per_trial),
                "n_bouts": 1,
                "n_multi_lick_bouts": 1,
                "first_peak_t_ms": float(peak_t_arr[0]),
                "t_ms": t_ms.copy(),
                "y_snip": y_snip,
                "angle_snip": angle_snip,
                "angle_allbouts_snip": angle_allbouts,
                "angle_firstbout_snip": angle_firstbout,
                "angle_firstmulti_snip": angle_firstmulti,
                "t_firstpeak_align_ms": t_fp.copy(),
                "angle_firstpeak_snip": angle_firstpeak,
            })

            # Bout-summary row (peak_t_ms NaN).
            bout_rows.append({
                "side": side,
                "trial_index": trial_index_global,
                "bout_idx": 0,
                "bout_rank": 0,
                "multi_bout_rank": 0.0,
                "n_peaks": int(n_peaks_per_trial),
                "bout_t0_ms": bt0,
                "bout_t1_ms": bt1,
                "peak_t0_ms": float(peak_t_arr[0]),
                "peak_t1_ms": float(peak_t_arr[1]),
                "peak_y0": float(peak_y[0]),
                "peak_angle0": float(angle_at_peaks[0]),
                "peak_y1": float(peak_y[1]),
                "peak_angle1": float(angle_at_peaks[1]),
                "peak_t_ms": float("nan"),
                "peak_y": float("nan"),
                "peak_x": float("nan"),
                "peak_angle_deg": float("nan"),
            })
            # Per-peak rows (bout_t0/t1 still set, but peak_t0/t1 NaN).
            for j in range(n_peaks_per_trial):
                bout_rows.append({
                    "side": side,
                    "trial_index": trial_index_global,
                    "bout_idx": 0,
                    "bout_rank": 0,
                    "multi_bout_rank": 0.0,
                    "n_peaks": int(n_peaks_per_trial),
                    "bout_t0_ms": bt0,
                    "bout_t1_ms": bt1,
                    "peak_t0_ms": float("nan"),
                    "peak_t1_ms": float("nan"),
                    "peak_y0": float("nan"),
                    "peak_angle0": float("nan"),
                    "peak_y1": float("nan"),
                    "peak_angle1": float("nan"),
                    "peak_t_ms": float(peak_t_arr[j]),
                    "peak_y": float(peak_y[j]),
                    "peak_x": float(peak_x[j]),
                    "peak_angle_deg": float(angle_at_peaks[j]),
                })

            # Phase rows: simulate phase ∈ [0, 1) sweeping across the
            # multi-lick bout.
            n_phase_pts = max(8, ib_hi - ib_lo)
            for k, fr_idx in enumerate(np.linspace(ib_lo, ib_hi - 1, n_phase_pts).astype(int)):
                ph = float((k / max(1, n_phase_pts - 1)))
                bin_idx = int(np.clip(
                    np.searchsorted(phase_bin_edges, ph, side="right") - 1,
                    0, len(phase_bin_centers) - 1,
                ))
                phase_rows.append({
                    "side": side,
                    "trial_index": trial_index_global,
                    "bout_idx": 0,
                    "bout_rank": 0,
                    "multi_bout_rank": 0,
                    "t_ms": float(t_ms[fr_idx]),
                    "phase": ph,
                    "phase_bin": bin_idx,
                    "phase_bin_center": float(phase_bin_centers[bin_idx]),
                    "angle_deg": float(angle_snip[fr_idx]),
                    "x_geom": float(rng.normal(0, 10)),
                    "y_geom": float(rng.normal(100, 20)),
                })

            trial_index_global += 1

    df_trials = pd.DataFrame(trial_rows)
    df_bouts = pd.DataFrame(bout_rows)
    df_phase = pd.DataFrame(phase_rows)

    # Tiny session-length angle parquet for completeness.
    n_frames_session = 1000
    angle_per_frame = pd.DataFrame({
        "frame_idx": np.arange(n_frames_session, dtype=np.int64),
        "angle_deg_smoothed": rng.normal(0, 5, size=n_frames_session).astype(
            np.float64,
        ),
    })

    metadata = {
        "animal": animal,
        "date": date.isoformat(),
        "fps": float(fps),
        "n_frames": int(n_frames_session),
        "eye_in_spout_frame_x": 0.0,
        "eye_in_spout_frame_y": -200.0,
        "angle_sign_flip": -1.0,
        "smoothing_gaussian_sigma_ms": 8.0,
        "feature_extraction_version": "v7a.3",
        "interpolation_version": "v5p3",
        "plot_win_ms": list(plot_win_ms),
        "detect_win_ms": list(detect_win_ms),
        "first_peak_align_win_ms": list(first_peak_align_win_ms),
        "n_phase_bins": int(n_phase_bins),
        "max_licks_per_trial": 40,
    }

    return TongueVisualBundle(
        df_trials=df_trials,
        df_bouts=df_bouts,
        df_phase=df_phase,
        angle_per_frame=angle_per_frame,
        metadata=metadata,
    )


@pytest.fixture()
def synthetic_bundle() -> TongueVisualBundle:
    return _make_synthetic_bundle()


# ============================================================================
# Driver tests
# ============================================================================


class TestRenderTongueQCFigures:
    def test_emits_9_pngs_per_session(self, tmp_path, synthetic_bundle):
        """Driver writes 6 family keys: 2 PNGs from qc_trials (per-side)
        + 3 PNGs from phase_aligned_angle (mode-suffixed
        _1st_lick / _all_licks / _first_{N}_licks) + 1 PNG each from
        first_peak_aligned, reward_aligned, first_vs_second_peak_scatter,
        xy_by_phase = 9 total.

        Updated 2026-05-04 per Addendum #11 Part B: new
        first_vs_second_peak_scatter family (per-trial scatter of
        peak[0] angle vs peak[1] angle) inserted between
        phase_aligned_angle and xy_by_phase in _FAMILIES_ALL.
        """
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        out = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        assert set(out.keys()) == {
            "qc_trials", "first_peak_aligned", "reward_aligned",
            "phase_aligned_angle", "first_vs_second_peak_scatter",
            "xy_by_phase",
        }
        all_paths = [p for paths in out.values() for p in paths]
        assert len(all_paths) == 9
        for p in all_paths:
            assert p.exists()
            assert p.stat().st_size > 1024  # > 1 KB sanity
            # No leftover .tmp files from atomic save.
            assert not p.with_name(p.name + ".tmp").exists()

    def test_phase_aligned_angle_emits_mode_suffixed_pngs(
        self, tmp_path, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addenda #3 / #11 Part A
        (2026-05-04): the bare ``phase_aligned_angle.png`` filename is
        retired. The driver emits three mode-suffixed PNGs per session:
        ``_1st_lick.png`` (mode = ``first_lick``, Addendum #9),
        ``_all_licks.png`` (mode = ``all_multi``, Addendum #10), and
        ``_first_{N}_licks.png`` where ``N`` =
        ``phase_aligned_first_n_peaks`` config knob (default 2,
        Addendum #11 Part A).
        """
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        out = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            families=["phase_aligned_angle"],
            overwrite="force",
        )
        paths = out["phase_aligned_angle"]
        assert len(paths) == 3
        names = {p.name for p in paths}
        assert names == {
            "phase_aligned_angle_1st_lick.png",
            "phase_aligned_angle_all_licks.png",
            "phase_aligned_angle_first_2_licks.png",
        }
        # The bare filename must NOT be emitted.
        bare = (
            resolver.tongue_angle_dir(animal, date) / "phase_aligned_angle.png"
        )
        assert not bare.exists()

    def test_first_n_licks_filename_tracks_config_knob(
        self, tmp_path, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #11 Part A
        (2026-05-04): the ``phase_aligned_angle_first_{N}_licks.png``
        filename tracks the
        ``dlc_kinematics.tongue_visual.phase_aligned_first_n_peaks``
        config knob. Override the knob → the suffix changes
        accordingly.
        """
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        params = load_defaults()
        params["dlc_kinematics"]["tongue_visual"][
            "phase_aligned_first_n_peaks"
        ] = 3
        out = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            families=["phase_aligned_angle"],
            params=params,
            overwrite="force",
        )
        names = {p.name for p in out["phase_aligned_angle"]}
        # Override → the variant suffix is now "first_3_licks"
        assert "phase_aligned_angle_first_3_licks.png" in names
        assert "phase_aligned_angle_first_2_licks.png" not in names

    def test_per_trial_qc_emits_separate_png_per_side(
        self, tmp_path, synthetic_bundle,
    ):
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        out = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            families=["qc_trials"],
            overwrite="force",
        )
        paths = out["qc_trials"]
        assert len(paths) == 2
        names = {p.name for p in paths}
        assert names == {"qc_trials_side_L.png", "qc_trials_side_R.png"}

    def test_overwrite_skip_does_not_rewrite(
        self, tmp_path, synthetic_bundle,
    ):
        """skip with all 9 PNGs present → return paths immediately
        (sentinel-content detection: stomp one PNG with junk; verify it's
        unchanged after skip-mode rerun)."""
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        out1 = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        # Stomp one PNG with sentinel bytes.
        sentinel = out1["qc_trials"][0]
        sentinel.write_bytes(b"SENTINEL")
        out2 = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="skip",
        )
        assert out2["qc_trials"][0] == sentinel
        assert sentinel.read_bytes() == b"SENTINEL"

    def test_overwrite_force_rewrites(self, tmp_path, synthetic_bundle):
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        sentinel_path = (
            resolver.tongue_angle_dir(animal, date) / "first_peak_aligned.png"
        )
        sentinel_path.write_bytes(b"SENTINEL")
        render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        assert sentinel_path.read_bytes() != b"SENTINEL"
        assert sentinel_path.stat().st_size > 1024

    def test_uses_side_colors_from_yaml(self, synthetic_bundle):
        """Sentinel side colours from a patched params dict propagate to
        the family-2 figure (verified via plotted line colours)."""
        params = load_defaults()
        # Sentinel colours unique to this test.
        params["dlc_kinematics"]["tongue_visual"]["side_colors"] = {
            "L": "#11ff11",
            "R": "#ff1111",
        }
        fig = _plot_first_peak_aligned(synthetic_bundle, params=params)
        # Each Line2D drawn by plot() carries the side colour.
        ax = fig.axes[0]
        line_colors = [line.get_color() for line in ax.get_lines() if line.get_label() != "_nolegend_"]
        # At least one line per side; convert to lower-case hex if needed.
        normalized = {matplotlib.colors.to_hex(c).lower() for c in line_colors}
        assert "#11ff11" in normalized or "#ff1111" in normalized
        plt.close(fig)


# ============================================================================
# Plot-family helper smoke tests
# ============================================================================


class TestPlotFamilies:
    """Smoke + schema only: each helper produces a non-empty Figure on
    synthetic input. Pixel-level fidelity is the parity harness's job."""

    def test_per_trial_qc_traces_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_per_trial_qc_traces(synthetic_bundle, "L", params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 1
        # At least one Axes has at least one Line2D drawn.
        any_lines = any(len(ax.get_lines()) > 0 for ax in fig.axes)
        assert any_lines
        plt.close(fig)

    def test_first_peak_aligned_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_first_peak_aligned(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 1
        any_lines = any(len(ax.get_lines()) > 0 for ax in fig.axes)
        assert any_lines
        plt.close(fig)

    def test_reward_aligned_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_reward_aligned(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 1
        any_lines = any(len(ax.get_lines()) > 0 for ax in fig.axes)
        assert any_lines
        plt.close(fig)

    def test_reward_aligned_clips_x_axis_to_display_window(self):
        """Phase 7a.4-cross-session-angle Addendum #4 (2026-05-04):
        ``_plot_reward_aligned`` clips the x-axis to
        ``dlc_kinematics.tongue_visual.reward_aligned_display_window_ms``
        regardless of the bundle's wider ``plot_win_ms``. Locks the
        contract that per-session and cross-session reward-aligned
        plots share the same x-axis byte-for-byte.

        Builds a fixture with the production-default wide bundle window
        (``[-180, 8000]`` ms) and asserts the rendered xlim matches the
        narrow display window (``[-180, 1000]`` ms by default).
        """
        bundle = _make_synthetic_bundle(plot_win_ms=(-180.0, 8000.0))
        params = load_defaults()
        display_win = tuple(
            params["dlc_kinematics"]["tongue_visual"][
                "reward_aligned_display_window_ms"
            ]
        )
        fig = _plot_reward_aligned(bundle, params=params)
        ax = fig.axes[0]
        xlim_lo, xlim_hi = ax.get_xlim()
        assert xlim_lo == pytest.approx(float(display_win[0]))
        assert xlim_hi == pytest.approx(float(display_win[1]))
        plt.close(fig)

    def test_reward_aligned_display_window_overrides_bundle_data_extent(self):
        """Same locked contract, exercised the other way: even when the
        bundle's t_ms extends to 8000 ms, the rendered x-axis is bounded
        by the display knob, NOT by the data's max(t_ms). Catches a
        regression where ``set_xlim`` is dropped and matplotlib
        auto-fits to the data.
        """
        bundle = _make_synthetic_bundle(plot_win_ms=(-180.0, 8000.0))
        # Override knob to a tight window distinct from the production
        # default so any leakage from auto-fit is visible.
        params = load_defaults()
        params["dlc_kinematics"]["tongue_visual"][
            "reward_aligned_display_window_ms"
        ] = [-100.0, 500.0]
        fig = _plot_reward_aligned(bundle, params=params)
        ax = fig.axes[0]
        xlim_lo, xlim_hi = ax.get_xlim()
        assert xlim_lo == pytest.approx(-100.0)
        assert xlim_hi == pytest.approx(500.0)
        plt.close(fig)

    def test_phase_aligned_angle_returns_nonempty_figure(self, synthetic_bundle):
        """Default mode path (no ``mode`` arg → falls back to config
        ``modes.phase_summary``)."""
        params = load_defaults()
        fig = _plot_phase_aligned_angle(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 1
        any_lines = any(len(ax.get_lines()) > 0 for ax in fig.axes)
        assert any_lines
        plt.close(fig)

    def test_phase_aligned_angle_mode_first_lick_uses_centered_builder(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addenda #9 + #10
        (2026-05-04): when called with ``mode="first_lick"``,
        ``_plot_phase_aligned_angle`` dispatches via
        ``_phase_rows_for_mode`` to
        :func:`build_first_lick_centered_phase_rows`. The figure is
        non-empty and the title carries the ``first_lick`` mode
        token.
        """
        params = load_defaults()
        fig = _plot_phase_aligned_angle(
            synthetic_bundle, params=params, mode="first_lick",
        )
        assert isinstance(fig, plt.Figure)
        ax = fig.axes[0]
        # Title carries the user-facing ``1st lick`` token (Phase
        # 7a.4-cross-session-angle Addendum #15 title convention).
        assert "1st lick" in ax.get_title()
        plt.close(fig)

    def test_phase_aligned_angle_mode_all_multi_uses_centered_builder(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #10: mode
        ``"all_multi"`` dispatches to
        :func:`build_all_licks_centered_phase_rows` (every peak
        in every multi-bout, centered with forward ILI; last peak
        per bout dropped). The all-licks centered output must
        contain at least as many rows as the first-lick-only
        output (which is a single-peak subset).
        """
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
            build_first_lick_centered_phase_rows,
        )
        # Compare row counts under explicit real_only mode (synthetic
        # fixture has no per-animal pre-stroke median ILI in metadata,
        # so synthetic_only / hybrid would raise; real_only is the
        # consistent comparable). The renderer below uses the
        # production default (synthetic_only with NaN-fallback to
        # real_only when synthetic ILI missing).
        n_first_lick = len(
            build_first_lick_centered_phase_rows(
                synthetic_bundle, ili_source="real_only",
            ),
        )
        n_all_multi = len(
            build_all_licks_centered_phase_rows(
                synthetic_bundle, ili_source="real_only",
            ),
        )
        assert n_first_lick <= n_all_multi
        # Renderer smoke check + title token assertion.
        params = load_defaults()
        fig = _plot_phase_aligned_angle(
            synthetic_bundle, params=params, mode="all_multi",
        )
        # Title carries the user-facing ``all licks`` token.
        assert "all licks" in fig.axes[0].get_title()
        plt.close(fig)

    def test_phase_aligned_angle_mode_first_n_licks_dispatches(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #11 Part A
        (2026-05-04): mode ``"first_n_licks"`` dispatches via
        :func:`_phase_rows_for_mode` to
        :func:`build_first_n_licks_centered_phase_rows` and renders
        a multi-cycle plot with x-axis spanning ``[0, n_peaks]``.
        Title carries ``"first {N} licks"``; xlim is ``(0, N)``.
        """
        params = load_defaults()
        fig = _plot_phase_aligned_angle(
            synthetic_bundle, params=params,
            mode="first_n_licks", n_peaks=2,
        )
        ax = fig.axes[0]
        assert "first 2 licks" in ax.get_title()
        xlim = ax.get_xlim()
        assert xlim[0] == pytest.approx(0.0)
        assert xlim[1] == pytest.approx(2.0)
        plt.close(fig)

    def test_first_vs_second_peak_scatter_uses_cam_view_subplot_ordering(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #11 Part B
        (2026-05-04): the LEFT subplot must show R-trials and the
        RIGHT subplot must show L-trials per the cam-view convention
        (mirrors 7a.4-orientation-fix + 7a.6 C7.2 + Addendum #16
        per-cycle convention). Pin against silent regression.
        """
        from stroke_orofacial.dlc_kinematics.tongue_visual import (
            _plot_first_vs_second_peak_scatter,
        )
        params = load_defaults()
        fig = _plot_first_vs_second_peak_scatter(
            synthetic_bundle, params=params,
        )
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 2
        assert "R trials" in fig.axes[0].get_title(), (
            f"expected 'R trials' in left-panel title; got "
            f"{fig.axes[0].get_title()!r}"
        )
        assert "L trials" in fig.axes[1].get_title(), (
            f"expected 'L trials' in right-panel title; got "
            f"{fig.axes[1].get_title()!r}"
        )
        plt.close(fig)

    def test_first_vs_second_peak_scatter_has_diagonal_reference(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #11 Part B
        (2026-05-04): each subplot includes a y=x diagonal
        reference line spanning the full axis range. Pin via
        the line's slope (≈1 in axis-data coordinates with
        equal aspect)."""
        from stroke_orofacial.dlc_kinematics.tongue_visual import (
            _plot_first_vs_second_peak_scatter,
        )
        params = load_defaults()
        fig = _plot_first_vs_second_peak_scatter(
            synthetic_bundle, params=params,
        )
        for ax in fig.axes[:2]:
            # The diagonal line goes from (-max, -max) to (+max, +max);
            # slope = 1.
            slopes = []
            for line in ax.get_lines():
                xd = np.asarray(line.get_xdata())
                yd = np.asarray(line.get_ydata())
                if xd.size == 2 and yd.size == 2 and xd[0] != xd[1]:
                    slopes.append((yd[1] - yd[0]) / (xd[1] - xd[0]))
            assert any(
                abs(s - 1.0) < 1e-6 for s in slopes
            ), (
                f"expected a y=x diagonal line; got slopes {slopes!r}"
            )
        plt.close(fig)

    def test_first_n_licks_renders_per_cycle_line_segments(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-cross-session-angle Addendum #16 (2026-05-04):
        multi-cycle plots render each cycle as an independent line
        segment so the boundary discontinuity at x=1, 2, ..., N-1
        is visible (under Mode 3, synthetic cycle width does not
        match real per-trial peak-to-peak timing — a connected
        line would draw between physically distinct time-points).

        Pin: no mean-curve Line2D may span more than one cycle's
        x range (= 1.0 wide). Synthetic fixture has no pre-stroke
        median ILI in metadata; force ``ili_source="real_only"``
        so the helper has data to render.
        """
        params = load_defaults()
        fig = _plot_phase_aligned_angle(
            synthetic_bundle, params=params,
            mode="first_n_licks", n_peaks=2,
            ili_source="real_only",
        )
        ax = fig.axes[0]
        # Mean-curve lines have many sample points; axhline /
        # axvline reference lines have exactly 2. Filter on length.
        mean_lines = [
            ln for ln in ax.get_lines()
            if len(ln.get_xdata()) > 5
        ]
        assert len(mean_lines) >= 2, (
            f"expected ≥2 mean-curve Line2D artists for multi-cycle "
            f"plot (per-side × per-cycle); got {len(mean_lines)}"
        )
        # No mean-curve line should span more than one cycle's
        # x range (cycle width = 1.0). Per-cycle segmentation
        # confines each line to a sub-region of [i, i+1).
        for line in mean_lines:
            xdata = np.asarray(line.get_xdata())
            if xdata.size == 0:
                continue
            x_span = float(np.nanmax(xdata) - np.nanmin(xdata))
            assert x_span < 1.0 + 1e-6, (
                f"line spans {x_span:.3f} of x; expected < 1.0 "
                f"(per-cycle segmentation)"
            )
        plt.close(fig)

    def test_xy_by_phase_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_xy_by_phase(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        # 2 panels (cam-view: R-trials on figure left, L-trials on
        # figure right per Phase 7a.4-orientation-fix); both should have
        # collections (scatter PathCollection) when phase rows exist for
        # both sides.
        assert len(fig.axes) >= 2
        any_collections = any(len(ax.collections) > 0 for ax in fig.axes)
        assert any_collections
        plt.close(fig)

    def test_xy_by_phase_uses_cam_view_subplot_ordering(
        self, synthetic_bundle,
    ):
        """Phase 7a.4-orientation-fix (2026-05-03): the LEFT subplot
        must show R-trials and the RIGHT subplot must show L-trials
        (cam-view convention; the camera mirror-images the mouse so
        mouse-left appears on the right of the camera frame). Locks
        the convention against silent regression. Mirrors the 7a.6
        C7.2 ``side_to_ax = {"R": ax_left, "L": ax_right}`` mapping
        used by ``mean_sem_visual._plot_mean_xy_overlays``.
        """
        params = load_defaults()
        fig = _plot_xy_by_phase(synthetic_bundle, params=params)
        # First two axes are the L/R panels; any subsequent axes
        # (e.g., colorbar) are appended after via ``fig.add_axes``.
        # Titles set via ``ax.set_title(f"{side} trials")``.
        assert len(fig.axes) >= 2
        assert "R trials" in fig.axes[0].get_title(), (
            f"expected 'R trials' in left-panel title; got "
            f"{fig.axes[0].get_title()!r}"
        )
        assert "L trials" in fig.axes[1].get_title(), (
            f"expected 'L trials' in right-panel title; got "
            f"{fig.axes[1].get_title()!r}"
        )
        plt.close(fig)

    def test_qc_traces_angle_subplot_renders_peak_scatter(
        self, synthetic_bundle,
    ):
        """C5.5 (2026-04-30) — smoke check that the angle subplot has
        at least one peak-marker scatter layer. The data-fidelity check
        (``peak_angle_deg`` actually matches ``angle_snip`` at peak
        frame) is the integration-level
        ``test_visual_bundle_peak_angle_matches_angle_snip`` in
        :file:`test_tongue_pertrial.py` — this synthetic fixture
        constructs peak_angle_deg by hand and so can't catch the
        underlying bundle-helper bug.
        """
        params = load_defaults()
        fig = _plot_per_trial_qc_traces(synthetic_bundle, "L", params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 2
        ax_a = fig.axes[1]
        scatters = [
            c for c in ax_a.collections if hasattr(c, "get_offsets")
        ]
        assert any(len(s.get_offsets()) > 0 for s in scatters), (
            "angle subplot has no peak-marker scatter"
        )
        plt.close(fig)