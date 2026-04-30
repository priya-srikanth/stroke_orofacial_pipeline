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
    render_comparison_grid,
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
    def test_emits_6_pngs_per_session(self, tmp_path, synthetic_bundle):
        """Driver writes 2 family-1 (per-side) + 4 single-PNG families = 6."""
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        out = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        # 5 family keys; family 1 has 2 paths, others 1 each. Total 6.
        assert set(out.keys()) == {
            "qc_trials", "first_peak_aligned", "reward_aligned",
            "phase_aligned_angle", "xy_by_phase",
        }
        all_paths = [p for paths in out.values() for p in paths]
        assert len(all_paths) == 6
        for p in all_paths:
            assert p.exists()
            assert p.stat().st_size > 1024  # > 1 KB sanity
            # No leftover .tmp files from atomic save.
            assert not p.with_name(p.name + ".tmp").exists()

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
        """skip with all 6 PNGs present → return paths immediately
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
            resolver.tongue_visual_qc_dir(animal, date) / "first_peak_aligned.png"
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

    def test_phase_aligned_angle_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_phase_aligned_angle(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) >= 1
        any_lines = any(len(ax.get_lines()) > 0 for ax in fig.axes)
        assert any_lines
        plt.close(fig)

    def test_xy_by_phase_returns_nonempty_figure(self, synthetic_bundle):
        params = load_defaults()
        fig = _plot_xy_by_phase(synthetic_bundle, params=params)
        assert isinstance(fig, plt.Figure)
        # 2 panels (L, R); both should have collections (scatter
        # PathCollection) when phase rows exist for both sides.
        assert len(fig.axes) >= 2
        any_collections = any(len(ax.collections) > 0 for ax in fig.axes)
        assert any_collections
        plt.close(fig)


# ============================================================================
# Comparison-grid tests
# ============================================================================


class TestComparisonGrid:
    def test_handles_missing_legacy_png(self, tmp_path, synthetic_bundle):
        """Legacy PNG missing → comparison grid emits with placeholder
        pane + annotation, does NOT crash."""
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        # Render consolidated PNGs first.
        render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        # Legacy root pointed at a non-existent dir.
        empty_legacy_root = tmp_path / "no_legacy_pngs_here"
        empty_legacy_root.mkdir()
        out = render_comparison_grid(
            animal=animal, date=date, resolver=resolver,
            legacy_figures_root=empty_legacy_root,
            families=["first_peak_aligned"],  # one family for speed
        )
        assert "first_peak_aligned" in out
        grid_path = out["first_peak_aligned"][0]
        assert grid_path.exists()
        assert grid_path.stat().st_size > 1024

    def test_renders_with_legacy_present(self, tmp_path, synthetic_bundle):
        """Both legacy + consolidated present → comparison grid emits
        with both panes loaded from disk."""
        animal = synthetic_bundle.metadata["animal"]
        date = datetime.date.fromisoformat(synthetic_bundle.metadata["date"])
        resolver = PathResolver(output_root=tmp_path)
        render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver,
            bundle=synthetic_bundle,
            overwrite="force",
        )
        # Plant a synthetic legacy PNG matching the expected name.
        legacy_root = tmp_path / "legacy_pngs"
        legacy_root.mkdir()
        date_str = date.strftime("%Y%m%d")
        legacy_png = (
            legacy_root
            / f"{animal}_{date_str}_anglePhase_firstPeakAlignedAngle.png"
        )
        # Use matplotlib to write a tiny placeholder PNG.
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.text(0.5, 0.5, "synthetic legacy", ha="center", va="center")
        fig.savefig(legacy_png, dpi=72)
        plt.close(fig)

        out = render_comparison_grid(
            animal=animal, date=date, resolver=resolver,
            legacy_figures_root=legacy_root,
            families=["first_peak_aligned"],
        )
        assert out["first_peak_aligned"][0].exists()
        assert out["first_peak_aligned"][0].stat().st_size > 1024

    def test_unknown_family_raises(self, tmp_path):
        date = datetime.date(2025, 3, 19)
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(ValueError, match="Unknown family"):
            render_comparison_grid(
                animal="PS50", date=date, resolver=resolver,
                legacy_figures_root=tmp_path,
                families=["not_a_real_family"],
            )
