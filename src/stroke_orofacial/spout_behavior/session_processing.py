"""End-to-end session processing orchestrator.

Replaces the legacy ``batch_process_20260410PS.ipynb`` notebook (Rule 1:
latest YYYYMMDD). Loads wavesurfer data, calibrates treadmill, detects
licks/rewards, and runs all four bout detectors. Writes 7 NPZ files per
session to the MICROSCOPE stroke_orofacial_pipeline_outputs/spout_behavior/ tree.
"""

from __future__ import annotations

import copy
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Literal

import numpy as np

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import (
    check_merge_required,
    get_session_params,
    load_defaults,
    load_session_overrides,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.bouts import (
    find_grooming_bouts,
    find_peri_reward_and_tone_periods,
    find_peri_reward_periods,
    find_quiet_bouts,
    find_running_bouts,
)
from stroke_orofacial.lr_convention import stamp_side_convention
from stroke_orofacial.spout_behavior.lick_detection import find_licks_and_rewards
from stroke_orofacial.spout_behavior.wavesurfer_io import (
    calibrate_treadmill,
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


def _translate_side_keys(
    payload: dict[str, Any], wavesurfer_matches: bool,
) -> dict[str, Any]:
    """Rename ``*_L``/``*_R`` suffixed keys to mouse frame.

    When ``wavesurfer_matches`` is True this is a no-op. When False the
    L/R suffixes are swapped, so what the caller passed as ``Lick_L`` —
    wavesurfer-frame L — becomes the emitted ``Lick_R`` (since
    wavesurfer-L is mouse-R on the mirrored rig). Only exact ``_L``/
    ``_R`` suffixes are translated; keys like ``x_limits`` or
    ``xedges`` pass through unchanged.

    The translation is key-name-only — array values (lick indices,
    bool masks) are byte-identical. The convention flip is purely
    re-labeling.
    """
    if wavesurfer_matches:
        return dict(payload)
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key.endswith("_L"):
            out[key[:-2] + "_R"] = value
        elif key.endswith("_R"):
            out[key[:-2] + "_L"] = value
        else:
            out[key] = value
    return out


def _save_npz(path: Path, data: dict[str, Any], allow_pickle: bool = False) -> None:
    """Save a dict to NPZ, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **data, allow_pickle=allow_pickle)


def _save_npz_with_side_convention(
    path: Path,
    data: dict[str, Any],
    wavesurfer_matches: bool,
    *,
    has_side_keys: bool,
    allow_pickle: bool = False,
) -> None:
    """Translate L/R keys (if any) to mouse frame, stamp convention, write NPZ.

    ``has_side_keys=True`` triggers :func:`_translate_side_keys` on the
    payload; False skips translation (for NPZs whose payload has no
    side labels — the stamp is still applied so every emitted artifact
    carries its convention metadata). The stamp records the rig
    orientation that was active at emit time; it does not depend on
    whether the particular payload had translatable keys.
    """
    payload = _translate_side_keys(data, wavesurfer_matches) if has_side_keys else dict(data)
    stamp_side_convention(payload, wavesurfer_matches)
    _save_npz(path, payload, allow_pickle=allow_pickle)


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
    manifest: SessionManifest,
    resolver: PathResolver,
    *,
    overwrite: Literal["skip", "prompt", "force"] = "skip",
    defaults: dict[str, Any] | None = None,
    overrides_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Run the full spout-behavior pipeline for one session.

    Primary entry point — consumes a ``SessionManifest`` produced by
    ``build_manifest()``. The wavesurfer file path is read from
    ``manifest.wavesurfer_file``; animal/date come from the manifest.

    For callers that prefer the legacy (animal, date) entry point, see
    ``process_session_by_animal_date()`` below.

    Parameters
    ----------
    manifest : SessionManifest
        Per-session manifest. Must have ``wavesurfer_file`` populated.
    resolver : PathResolver
        Configured path resolver (used for output-tree placement).
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
        If ``manifest.wavesurfer_file`` is None (wavesurfer data not
        located when the manifest was built).
    """
    animal = manifest.animal
    date = manifest.date
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
    ws_file = manifest.wavesurfer_file
    if ws_file is None:
        raise FileNotFoundError(
            f"manifest.wavesurfer_file is None for {animal}/{date_str}. "
            f"build_manifest() did not locate a wavesurfer .h5 — is the "
            f"wavesurfer_raw mount available?"
        )
    signals = load_wavesurfer_signals(ws_file)
    Fs = float(signals["sample_rate_input"])

    # Rig-orientation flag — mirrored downstream to every emitted NPZ so
    # consumers can interpret L/R labels unambiguously.
    ws_match = manifest.wavesurfer_sides_match_mouse_sides

    # Save wavesurfer_signals_processed — raw channel names include
    # Lick_L/Lick_R etc., translated here to mouse frame at emit.
    _save_npz_with_side_convention(
        paths["wavesurfer_signals_processed"], signals, ws_match,
        has_side_keys=True,
    )

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
    # No L/R content, but stamped for consistency so downstream readers
    # can assert the convention-metadata contract on every NPZ.
    _save_npz_with_side_convention(
        paths["treadmill_signals_preprocessed"], tm_out, ws_match,
        has_side_keys=False,
    )

    # ---- Step 3: Lick and reward detection ----
    # Internal lick_idx / reward_idx / tone_idx dicts stay in the
    # wavesurfer frame so Phase 4/5/6 downstream logic is arithmetically
    # unchanged. Translation to mouse frame happens only at the NPZ emit
    # line below.
    lr_result = find_licks_and_rewards(signals, params["find_licks_and_rewards"])
    n_samples = int(lr_result["n_samples"])

    lr_out = copy.deepcopy(lr_result)
    _save_npz_with_side_convention(
        paths["licks_and_rewards"], lr_out, ws_match,
        has_side_keys=True, allow_pickle=True,
    )

    lick_idx = {"Lick_L": lr_result["Lick_L"], "Lick_R": lr_result["Lick_R"]}
    reward_idx = {"Reward_L": lr_result["Reward_L"], "Reward_R": lr_result["Reward_R"]}
    tone_idx = {"Tone_L": lr_result["Tone_L"], "Tone_R": lr_result["Tone_R"]}

    # ---- Step 4: Running bouts ----
    running = find_running_bouts(treadmill_smoothed, Fs, params["find_running_bouts"])
    run_out: dict[str, Any] = {"running_bouts": running}
    run_out.update(params["find_running_bouts"])
    _save_npz_with_side_convention(
        paths["running_bouts"], run_out, ws_match, has_side_keys=False,
    )

    # ---- Step 5: Grooming bouts ----
    grooming = find_grooming_bouts(lick_idx, n_samples, Fs, params["find_grooming_bouts"])
    groom_out: dict[str, Any] = {"lick_bool_bad": grooming}
    groom_out.update(params["find_grooming_bouts"])
    _save_npz_with_side_convention(
        paths["grooming_bouts"], groom_out, ws_match, has_side_keys=False,
    )

    # ---- Step 6: Quiet bouts ----
    quiet = find_quiet_bouts(
        treadmill_smoothed, grooming, lick_idx, reward_idx, n_samples, Fs,
        params["find_quiet_bouts"],
    )
    quiet_out: dict[str, Any] = {"quiet_bool": quiet}
    quiet_out.update(params["find_quiet_bouts"])
    _save_npz_with_side_convention(
        paths["quiet_bouts"], quiet_out, ws_match, has_side_keys=False,
    )

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
    # peri_reward_L/R + peri_tone_L/R keys translated at emit.
    _save_npz_with_side_convention(
        paths["peri_reward_periods"], peri_out, ws_match, has_side_keys=True,
    )

    # ---- Save per-session params.json ----
    _save_session_params(
        output_root, animal, date, date_str, params, processing_log, skipped=False
    )

    logger.info("Session %s/%s complete. Outputs: %s", animal, date_str, output_root)
    return paths


def process_session_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    overwrite: Literal["skip", "prompt", "force"] = "skip",
    defaults: dict[str, Any] | None = None,
    overrides_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Convenience wrapper: builds a SessionManifest then calls process_session().

    Equivalent to::

        animal_info = get_animal(animal)
        manifest = build_manifest(animal, date, resolver, animal_info)
        return process_session(manifest, resolver, ...)

    Phase 2 (spout behavior) is DLC-free by design: ``build_manifest()``
    treats DLC files as optional and yields empty lists when missing, so
    this wrapper works for sessions where DLC inference hasn't run yet
    or where video recording failed but wavesurfer is still clean.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info)
    return process_session(
        manifest,
        resolver,
        overwrite=overwrite,
        defaults=defaults,
        overrides_config=overrides_config,
    )


def process_animal(
    animal: str,
    dates: list[datetime.date],
    resolver: PathResolver,
    *,
    overwrite: Literal["skip", "prompt", "force"] = "skip",
) -> list[dict[str, Path]]:
    """Run the spout-behavior pipeline for all sessions of one animal.

    Thin loop over ``process_session_by_animal_date()``. Loads
    ``defaults.yaml`` and ``session_overrides.yaml`` once for the whole
    animal.

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
            result = process_session_by_animal_date(
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
