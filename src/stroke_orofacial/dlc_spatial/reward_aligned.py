"""Reward-aligned spatial analysis functions.

Ported from cell 16 (and cells 18, 20) of canonical notebook
``20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb``.

Loads reward events from Phase 2's ``licks_and_rewards`` NPZ, converts
WS sample indices → camera frame indices via Phase 3's alignment template,
builds peri-reward frame windows, and produces reward-aligned heatmaps.

This is the first phase without array-level parity reference — the legacy
cell 16 was coded but never run to produce saved outputs on MICROSCOPE.
Tongue config is legacy-ported; jaw, nose, and whisker configs are
sanity-check-only defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from stroke_orofacial.dlc_spatial.window_selector import (
    RewardAlignedWindow,
    _ws_to_cam_frames,
)


def load_reward_events(
    licks_npz_path: Path | str,
    trial_group: str = "all",
) -> np.ndarray:
    """Load reward onset indices from a licks_and_rewards NPZ.

    Parameters
    ----------
    licks_npz_path : Path or str
        Path to the ``licks_and_rewards/{animal}/{YYYYMMDD}.npz`` file
        from Phase 2.
    trial_group : str
        ``"all"`` (both sides), ``"L"`` (left rewards only), or
        ``"R"`` (right rewards only).

    Returns
    -------
    np.ndarray
        Sorted array of reward onset indices in wavesurfer sample space.
    """
    data = np.load(str(licks_npz_path), allow_pickle=True)

    if trial_group == "L":
        return np.sort(data["Reward_L"].astype(int))
    elif trial_group == "R":
        return np.sort(data["Reward_R"].astype(int))
    else:
        return np.sort(np.concatenate([
            data.get("Reward_L", np.array([], dtype=int)).astype(int),
            data.get("Reward_R", np.array([], dtype=int)).astype(int),
        ]))


def ws_samples_to_frame_indices(
    ws_samples: np.ndarray,
    sig_camIdx__idx_ws: np.ndarray,
    n_cam_frames: int,
) -> np.ndarray:
    """Convert wavesurfer sample indices to camera frame indices.

    Thin wrapper around ``_ws_to_cam_frames`` for public use.

    Parameters
    ----------
    ws_samples : np.ndarray
        Reward onset indices in WS sample space.
    sig_camIdx__idx_ws : np.ndarray
        Alignment lookup table from ``AlignmentResult``.
    n_cam_frames : int
        Total number of camera/DLC frames.

    Returns
    -------
    np.ndarray
        Frame indices (int). Invalid entries are -1.
    """
    return _ws_to_cam_frames(ws_samples, sig_camIdx__idx_ws, n_cam_frames)


def build_reward_aligned_window(
    reward_ws_samples: np.ndarray,
    sig_camIdx__idx_ws: np.ndarray,
    window_ms: tuple[float, float],
    fps: float,
    n_frames: int,
) -> RewardAlignedWindow:
    """Construct a RewardAlignedWindow from reward events + alignment data.

    Parameters
    ----------
    reward_ws_samples : np.ndarray
        Reward onset indices in WS sample space.
    sig_camIdx__idx_ws : np.ndarray
        Alignment lookup from Phase 3.
    window_ms : tuple[float, float]
        (pre_ms, post_ms) — e.g. ``(-500, 5000)`` for 500ms before to
        5000ms after each reward.
    fps : float
        Camera frame rate (250 Hz).
    n_frames : int
        Total DLC/camera frames in the session.

    Returns
    -------
    RewardAlignedWindow
    """
    return RewardAlignedWindow(
        reward_ws_samples=reward_ws_samples,
        sig_camIdx__idx_ws=sig_camIdx__idx_ws,
        window_ms=window_ms,
        fps=fps,
        n_frames=n_frames,
    )


def build_reward_aligned_analysis(
    animal: str,
    date_str: str,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    window_ms: tuple[float, float],
    resolver: Any,
    spatial_config: dict[str, Any],
    reward_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Run a complete reward-aligned spatial analysis for one session.

    Pure function — no module-level state. Loads all inputs from disk,
    builds the reward-aligned window, computes the histogram, and returns
    the results.

    Parameters
    ----------
    animal : str
        Animal ID.
    date_str : str
        Session date (YYYYMMDD).
    bodypart : str
        Bodypart name.
    center_mode : str
        Centering mode (nose, spout_midpoint, eye_midpoint).
    trial_group : str
        "all", "L", or "R".
    window_ms : tuple[float, float]
        Reward window in ms.
    resolver : PathResolver
        Configured path resolver.
    spatial_config : dict
        The ``dlc_spatial`` section from defaults.yaml.
    reward_config : dict
        The ``dlc_spatial_reward_aligned`` section from defaults.yaml.

    Returns
    -------
    dict or None
        ``{"histogram": ..., "window": ..., "n_rewards": ..., "n_selected_frames": ...}``
        or None if data is missing.
    """
    from stroke_orofacial.dlc_io.loaders import discover_dlc_filtered_files
    from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet
    from stroke_orofacial.dlc_spatial.pixel_bins import build_histogram

    # Load centered parquet
    dlc_dir = resolver.dlc_output_dir(animal)
    h5_files = discover_dlc_filtered_files(dlc_dir, date_str)
    if not h5_files:
        return None

    lik_thr_centering = 0.7  # Phase 4 centering threshold
    sig = _param_sig(center_mode, lik_thr_centering)
    parquet_dir = resolver.pipeline_outputs("dlc_analysis") / f"centered_{center_mode}" / animal
    parquet_name = f"{h5_files[0].name}.intermediate.{sig}.parquet"
    parquet_path = parquet_dir / parquet_name
    if not parquet_path.exists():
        return None

    df = read_centered_parquet(parquet_path)
    n_frames = len(df)

    # Load reward events
    spout_root = resolver.pipeline_outputs("spout_behavior")
    licks_path = spout_root / "licks_and_rewards" / animal / f"{date_str}.npz"
    if not licks_path.exists():
        return None

    reward_ws = load_reward_events(licks_path, trial_group)
    if len(reward_ws) == 0:
        return None

    # Load alignment template
    import datetime as dt
    date = dt.datetime.strptime(date_str, "%Y%m%d").date()
    align_path = resolver.alignment_template(animal, date, cam="cam2")
    if not align_path.exists():
        return None

    align_data = np.load(str(align_path), allow_pickle=True)
    sig_camIdx = align_data["sig_camIdx__idx_ws"]

    # Build reward-aligned window
    fps = float(reward_config.get("fps", 250.0))
    window = build_reward_aligned_window(reward_ws, sig_camIdx, window_ms, fps, n_frames)

    # Build histogram with window.
    # Reward-aligned analyses use the Phase 6 `dlc_spatial_reward_aligned`
    # config for likelihood thresholds and (per-bodypart, non-center-mode-aware)
    # x_range filters; axis limits come from the Phase 5 `dlc_spatial` config
    # which IS per-(bodypart, center_mode).
    bp_config = reward_config.get("bodyparts", {}).get(bodypart, {})
    bp_x_range_reward = bp_config.get("x_range")
    lik_thresholds = bp_config.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8

    nbins_list = reward_config.get("default_nbins", [80, 80])
    nbins = nbins_list[0] if isinstance(nbins_list[0], int) else int(nbins_list[0])

    # Override only the likelihood threshold (reward-aligned thresholds differ
    # from whole-session thresholds). All other per-(bodypart, center_mode)
    # values (xlim, ylim, x_range) come from the Phase 5 spatial_config via
    # the build_histogram center_mode kwarg.
    config_for_hist = dict(spatial_config)
    config_for_hist["bodyparts"] = dict(config_for_hist.get("bodyparts", {}))
    existing_bp = dict(config_for_hist["bodyparts"].get(bodypart, {}))
    existing_bp["likelihood_threshold"] = lik_thr
    config_for_hist["bodyparts"][bodypart] = existing_bp

    # Reward-aligned per-bodypart x_range (Phase 6 config) takes precedence
    # over the Phase 5 per_center_mode.x_range when provided; fall back to
    # Phase 5's value otherwise by passing x_range=None to build_histogram.
    x_range_override = tuple(bp_x_range_reward) if bp_x_range_reward is not None else None

    histogram = build_histogram(
        df, bodypart, config_for_hist,
        center_mode=center_mode,
        x_range=x_range_override,
        nbins=nbins,
        window=window,
    )

    return {
        "histogram": histogram,
        "window": window,
        "n_rewards": window.n_events,
        "n_selected_frames": window.n_selected,
        "trial_group": trial_group,
        "window_ms": window_ms,
        "bodypart": bodypart,
        "center_mode": center_mode,
    }
