"""End-to-end session processing orchestrator.

Replaces the legacy ``batch_process_20260410PS.ipynb`` notebook (Rule 1:
latest YYYYMMDD). Loads wavesurfer data, calibrates treadmill, detects
licks/rewards, and runs all four bout detectors. Writes 7 NPZ files per
session to the MICROSCOPE pipeline_outputs_v2/spout_behavior/ tree.
"""

from __future__ import annotations

import copy
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Literal

import numpy as np

from stroke_orofacial.config_loader import (
    check_merge_required,
    get_session_params,
    load_defaults,
    load_session_overrides,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.bouts import (
    find_grooming_bouts,
    find_peri_reward_and_tone_periods,
    find_peri_reward_periods,
    find_quiet_bouts,
    find_running_bouts,
)
from stroke_orofacial.spout_behavior.lick_detection import find_licks_and_rewards
from stroke_orofacial.spout_behavior.wavesurfer_io import (
    calibrate_treadmill,
    find_wavesurfer_file,
    load_wavesurfer_signals,
    smooth_treadmill,
)

logger = logging.getLogger(__name__)

# The 7 output subdirectory names, matching session_processing3 layout
OUTPUT_TYPES = [
    "wavesurfer_signals_processed",
    "treadmill_signals_preprocessed",
    "licks_and_rewards",
    "running_bouts",
    "grooming_bouts",
    "quiet_bouts",
    "peri_reward_periods",
]


def _output_path(output_root: Path, output_type: str, animal: str, date_str: str) -> Path:
    """Return the NPZ output path for a given type/animal/date."""
    return output_root / output_type / animal / f"{date_str}.npz"


def _save_npz(path: Path, data: dict[str, Any], allow_pickle: bool = False) -> None:
    """Save a dict to NPZ, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **data, allow_pickle=allow_pickle)


def _params_json_path(output_root: Path, animal: str, date_str: str) -> Path:
    """Return the per-session params.json path."""
    return output_root / "params" / animal / f"{date_str}.json"


def _save_session_params(
    output_root: Path,
    animal: str,
    date: datetime.date,
    date_str: str,
    params: dict[str, Any],
    processing_log: list[dict],
    skipped: bool,
) -> Path:
    """Write per-session params.json with full provenance metadata.

    Always written, even when the session is skipped, to maintain a
    complete audit trail.
    """
    spout_keys = [
        "process_treadmill_signal", "find_running_bouts", "find_licks_and_rewards",
        "find_grooming_bouts", "find_quiet_bouts", "find_peri_reward_periods",
        "find_peri_reward_and_tone_periods",
    ]
    params_subset = {k: params[k] for k in spout_keys if k in params}

    record = {
        "session_id": f"{animal}_{date_str}",
        "animal": animal,
        "date": date.isoformat(),
        "run_timestamp": datetime.datetime.now().isoformat(),
        "skipped": skipped,
        "params": params_subset,
        "processing_log": processing_log,
    }

    path = _params_json_path(output_root, animal, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    return path


def _check_overwrite(
    paths: dict[str, Path],
    overwrite: str,
    log: list[dict],
) -> bool:
    """Check whether to proceed with writing, based on overwrite mode.

    Parameters
    ----------
    paths : dict
        Mapping of output_type -> Path for all 7 outputs.
    overwrite : str
        One of "skip", "prompt", "force".
    log : list
        Mutable list to append skip/overwrite decisions to.

    Returns
    -------
    bool
        True if processing should proceed, False if skipped.
    """
    existing = {k: p for k, p in paths.items() if p.exists()}

    if not existing:
        return True  # nothing exists, always proceed

    if overwrite == "skip":
        for k, p in existing.items():
            log.append({"action": "skipped", "type": k, "path": str(p)})
            logger.info("Skipping %s (exists): %s", k, p)
        return False

    if overwrite == "force":
        for k, p in existing.items():
            log.append({"action": "overwrite", "type": k, "path": str(p)})
            logger.info("Overwriting %s: %s", k, p)
        return True

    if overwrite == "prompt":
        print(f"\n  Existing outputs found ({len(existing)} of {len(paths)}):")
        for k, p in existing.items():
            print(f"    {k}: {p}")
        while True:
            choice = input("  Overwrite? [y/N/all/quit]: ").strip().lower()
            if choice in ("", "n"):
                for k, p in existing.items():
                    log.append({"action": "skipped_by_user", "type": k, "path": str(p)})
                return False
            if choice == "y":
                for k, p in existing.items():
                    log.append({"action": "overwrite_by_user", "type": k, "path": str(p)})
                return True
            if choice == "all":
                for k, p in existing.items():
                    log.append({"action": "overwrite_all_by_user", "type": k, "path": str(p)})
                return True
            if choice == "quit":
                raise KeyboardInterrupt("User chose quit during overwrite prompt")
            print("  Please enter y, N, all, or quit.")

    raise ValueError(f"Unknown overwrite mode: {overwrite!r}. Use 'skip', 'prompt', or 'force'.")


def process_session(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    overwrite: Literal["skip", "prompt", "force"] = "skip",
    defaults: dict[str, Any] | None = None,
    overrides_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Run the full spout-behavior pipeline for one session.

    Parameters
    ----------
    animal : str
        Animal ID (e.g. "PS46").
    date : datetime.date
        Session date.
    resolver : PathResolver
        Configured path resolver.
    overwrite : str
        Overwrite mode: "skip" (default), "prompt", or "force".
    defaults : dict, optional
        Pre-loaded defaults.yaml. Loaded fresh if None.
    overrides_config : dict, optional
        Pre-loaded session_overrides.yaml. Loaded fresh if None.

    Returns
    -------
    dict[str, Path]
        Mapping of output_type -> written Path for each of the 7 outputs.
        Empty dict if session was skipped.

    Raises
    ------
    NotImplementedError
        If this session has a ``merges`` entry in session_overrides.yaml.
    FileNotFoundError
        If wavesurfer file or directory is missing.
    """
    date_str = date.strftime("%Y%m%d")
    output_root = resolver.pipeline_outputs("spout_behavior")
    processing_log: list[dict] = []

    # Load configs
    if defaults is None:
        defaults = load_defaults()
    if overrides_config is None:
        overrides_config = load_session_overrides()

    # Check for merge requirement (deferred — raises if present)
    check_merge_required(animal, date_str, overrides_config)

    # Merge per-session overrides on top of defaults
    params = get_session_params(defaults, animal, date_str, overrides_config)

    # Build output paths
    paths = {t: _output_path(output_root, t, animal, date_str) for t in OUTPUT_TYPES}

    # Check overwrite
    if not _check_overwrite(paths, overwrite, processing_log):
        # Still write params.json even when skipping, for audit trail
        _save_session_params(
            output_root, animal, date, date_str, params, processing_log, skipped=True
        )
        logger.info("Session %s/%s skipped (all outputs exist).", animal, date_str)
        return {}

    logger.info("Processing %s/%s ...", animal, date_str)

    # ---- Step 1: Load wavesurfer signals ----
    ws_dir = resolver.wavesurfer_dir(date, animal)
    ws_file = find_wavesurfer_file(ws_dir)
    signals = load_wavesurfer_signals(ws_file)
    Fs = float(signals["sample_rate_input"])

    # Save wavesurfer_signals_processed
    _save_npz(paths["wavesurfer_signals_processed"], signals)

    # ---- Step 2: Calibrate and smooth treadmill ----
    tm_params = params["process_treadmill_signal"]
    # Resolve offset (session override already merged into tm_params)
    offset_used = float(tm_params["offset_in_volts"])

    calibrated = calibrate_treadmill(
        signals["Treadmill"],
        offset_in_volts=offset_used,
        voltSec_per_rot=float(tm_params["voltSec_per_rot"]),
        mm_per_rot=float(tm_params["mm_per_rot"]),
    )

    sigma_sec = tm_params.get("smoothing_sigma")
    if sigma_sec is not None:
        treadmill_smoothed = smooth_treadmill(calibrated, Fs, float(sigma_sec))
    else:
        treadmill_smoothed = calibrated

    tm_out = {
        "Treadmill_smoothed": treadmill_smoothed,
        "Fs": Fs,
    }
    tm_out.update(tm_params)
    _save_npz(paths["treadmill_signals_preprocessed"], tm_out)

    # ---- Step 3: Lick and reward detection ----
    lr_result = find_licks_and_rewards(signals, params["find_licks_and_rewards"])
    n_samples = int(lr_result["n_samples"])

    lr_out = copy.deepcopy(lr_result)
    _save_npz(paths["licks_and_rewards"], lr_out, allow_pickle=True)

    lick_idx = {"Lick_L": lr_result["Lick_L"], "Lick_R": lr_result["Lick_R"]}
    reward_idx = {"Reward_L": lr_result["Reward_L"], "Reward_R": lr_result["Reward_R"]}
    tone_idx = {"Tone_L": lr_result["Tone_L"], "Tone_R": lr_result["Tone_R"]}

    # ---- Step 4: Running bouts ----
    running = find_running_bouts(treadmill_smoothed, Fs, params["find_running_bouts"])
    run_out: dict[str, Any] = {"running_bouts": running}
    run_out.update(params["find_running_bouts"])
    _save_npz(paths["running_bouts"], run_out)

    # ---- Step 5: Grooming bouts ----
    grooming = find_grooming_bouts(lick_idx, n_samples, Fs, params["find_grooming_bouts"])
    groom_out: dict[str, Any] = {"lick_bool_bad": grooming}
    groom_out.update(params["find_grooming_bouts"])
    _save_npz(paths["grooming_bouts"], groom_out)

    # ---- Step 6: Quiet bouts ----
    quiet = find_quiet_bouts(
        treadmill_smoothed, grooming, lick_idx, reward_idx, n_samples, Fs,
        params["find_quiet_bouts"],
    )
    quiet_out: dict[str, Any] = {"quiet_bool": quiet}
    quiet_out.update(params["find_quiet_bouts"])
    _save_npz(paths["quiet_bouts"], quiet_out)

    # ---- Step 7: Peri-reward periods (consolidated + per-side + per-tone) ----
    peri_reward = find_peri_reward_periods(
        reward_idx, n_samples, Fs, params["find_peri_reward_periods"],
    )
    peri_sided = find_peri_reward_and_tone_periods(
        reward_idx, tone_idx, n_samples, Fs,
        params["find_peri_reward_and_tone_periods"],
    )
    peri_out: dict[str, Any] = {"peri_reward_bool": peri_reward}
    peri_out.update(peri_sided)  # peri_reward_L/R, peri_tone_L/R
    peri_out.update(params["find_peri_reward_periods"])
    _save_npz(paths["peri_reward_periods"], peri_out)

    # ---- Save per-session params.json ----
    _save_session_params(
        output_root, animal, date, date_str, params, processing_log, skipped=False
    )

    logger.info("Session %s/%s complete. Outputs: %s", animal, date_str, output_root)
    return paths


def process_animal(
    animal: str,
    dates: list[datetime.date],
    resolver: PathResolver,
    *,
    overwrite: Literal["skip", "prompt", "force"] = "skip",
) -> list[dict[str, Path]]:
    """Run the spout-behavior pipeline for all sessions of one animal.

    Parameters
    ----------
    animal : str
        Animal ID.
    dates : list[datetime.date]
        List of session dates to process.
    resolver : PathResolver
        Configured path resolver.
    overwrite : str
        Overwrite mode passed to ``process_session()``.

    Returns
    -------
    list[dict[str, Path]]
        One dict per date (empty dict for skipped sessions).
    """
    # Load configs once for the whole animal
    defaults = load_defaults()
    overrides_config = load_session_overrides()

    results = []
    for date in dates:
        try:
            result = process_session(
                animal, date, resolver,
                overwrite=overwrite,
                defaults=defaults,
                overrides_config=overrides_config,
            )
            results.append(result)
        except NotImplementedError as e:
            logger.warning("Skipping %s/%s: %s", animal, date, e)
            results.append({})
        except FileNotFoundError as e:
            logger.warning("Skipping %s/%s: %s", animal, date, e)
            results.append({})
    return results
