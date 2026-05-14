"""Load and preprocess wavesurfer .h5 session files.

Ported from legacy modules (Rule 1 / Rule 3 resolved):
  - process_ws_signals.py (only version)
  - calibrate_and_smooth_treadmill_signal_PS.py (confirmed canonical by Priya)
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pywavesurfer.ws

from stroke_orofacial._utils.bool_indexing import gaussian_smooth_1d


def _apply_tone_reward_swap(signals: dict[str, np.ndarray]) -> None:
    """In-place pairwise swap of ``Reward_<side>`` ↔ ``Tone_<side>`` content.

    Phase 8a.10.1 Tone↔Reward channel-label fix. The raw `.h5` channel
    labels emitted by the rig are inverted cohort-wide: the digital
    channel labeled ``Reward_*`` carries ~200 ms pulses (auditory tone
    TTL); the channel labeled ``Tone_*`` carries ~26 ms pulses (reward
    solenoid drive). Cohort-wide confirmed by Task 0.5 pulse-width audit
    (271/271 sessions — see
    ``.scratch_phase_8a_10_1/task_0_5_audit_report.md`` and
    ``.scratch_phase_8a_10_1/reward_tone_swap_extended_diagnostic.md``).

    Swap is per-side: ``Reward_L`` ↔ ``Tone_L`` and ``Reward_R`` ↔
    ``Tone_R`` independently. Silent no-op when only one side of a pair
    is present (defensive: never mutates a partially-populated signals
    dict). Mutates ``signals`` in place; returns nothing.
    """
    for side in ("L", "R"):
        r_key = f"Reward_{side}"
        t_key = f"Tone_{side}"
        if r_key in signals and t_key in signals:
            signals[r_key], signals[t_key] = signals[t_key], signals[r_key]


def load_wavesurfer_signals(
    path_ws: Path | str,
    *,
    tone_reward_swap_enabled: bool = True,
) -> dict[str, np.ndarray]:
    """Load analog and digital channel signals from a WaveSurfer .h5 file.

    Faithfully ports ``process_ws_signals.load_wavesurfer_signals``.

    Phase 8a.10.1: gated post-read swap of ``Reward_<side>`` ↔
    ``Tone_<side>`` digital channels corrects a cohort-wide acquisition-
    layer label inversion. See :func:`_apply_tone_reward_swap` for the
    semantic rationale + Task 0.5 audit pointer. Default ``True`` —
    swap is applied for the current cohort. Set ``False`` only as a
    kill-switch for hypothetical future correctly-labeled cohorts (or
    in unit tests of the un-swapped loader path).

    Parameters
    ----------
    path_ws : Path or str
        Path to the WaveSurfer .h5 file.
    tone_reward_swap_enabled : bool, keyword-only, default True
        When True (default), applies the Tone↔Reward dict-key swap fix
        after loading raw channels. Controls the
        ``wavesurfer.tone_reward_swap_enabled`` flag in
        ``configs/defaults.yaml``.

    Returns
    -------
    dict[str, np.ndarray]
        Channel names mapped to 1-D arrays. Includes ``sample_rate_input``
        (float) as a special key. Post-fix (``tone_reward_swap_enabled
        =True``) the ``Reward_*`` keys hold actual reward-delivery sample
        indices and the ``Tone_*`` keys hold actual tone-onset sample
        indices.
    """
    path_ws = Path(path_ws)
    data_ws = pywavesurfer.ws.loadDataFile(str(path_ws))

    # --- Sample rate ---
    Fs_in = data_ws["header"]["AcquisitionSampleRate"]

    # --- Identify sweep ---
    sweep_names = [k for k in data_ws.keys() if "sweep" in k]
    if len(sweep_names) != 1:
        warnings.warn(
            f"Expected exactly 1 sweep, found {len(sweep_names)}: {sweep_names}",
            stacklevel=2,
        )
    name_sweep = sorted(sweep_names)[-1]
    if name_sweep != "sweep_0001":
        warnings.warn(
            f"Using sweep '{name_sweep}' instead of 'sweep_0001'.",
            stacklevel=2,
        )

    # --- Analog channels ---
    raw_names = data_ws["header"]["AIChannelNames"]
    active_mask = data_ws["header"]["IsAIChannelActive"][:, 0].astype(bool)
    names_analog = {
        idx: name.decode()
        for idx, name in enumerate(raw_names[active_mask])
    }
    signals_analog = {
        names_analog[idx]: data_ws[name_sweep]["analogScans"][idx]
        for idx in names_analog
    }

    # --- Digital channels ---
    raw_bits = data_ws[name_sweep]["digitalScans"][0]
    bits = np.unpackbits(raw_bits).reshape(-1, 8).astype(bool)
    names_digital = {
        idx: dn.decode()
        for idx, dn in enumerate(data_ws["header"]["DIChannelNames"])
    }
    # Bit index offset: channel idx maps to bit column idx+1
    signals_digital = {
        names_digital[idx]: bits[:, idx + 1]
        for idx in names_digital
    }

    # Combine
    signals: dict[str, np.ndarray] = {}
    signals.update(signals_analog)
    signals.update(signals_digital)
    # pywavesurfer returns AcquisitionSampleRate as a shape-(1,) ndarray.
    # numpy 2.x removed the implicit float(1d-array) coercion, so normalize
    # via .item() — works for both 0-D scalars and single-element arrays.
    signals["sample_rate_input"] = float(np.asarray(Fs_in).item())

    if tone_reward_swap_enabled:
        _apply_tone_reward_swap(signals)
    return signals


def find_wavesurfer_file(session_dir: Path) -> Path:
    """Find the wavesurfer .h5 file in a session directory.

    Globs for ``*.h5`` files, excluding any containing "kHz" in the name
    (per legacy convention). Expects exactly one match.

    Parameters
    ----------
    session_dir : Path
        Directory containing the session's wavesurfer file(s).

    Returns
    -------
    Path
        The discovered .h5 file path.

    Raises
    ------
    FileNotFoundError
        If the directory doesn't exist or no matching .h5 file is found.
    ValueError
        If multiple .h5 files are found (ambiguous).
    """
    if not session_dir.exists():
        raise FileNotFoundError(f"Wavesurfer session directory not found: {session_dir}")

    h5_files = [
        f for f in sorted(session_dir.glob("*.h5"))
        if "kHz" not in f.name
    ]

    if not h5_files:
        raise FileNotFoundError(
            f"No wavesurfer .h5 files found in {session_dir} "
            f"(excluded files containing 'kHz')."
        )
    if len(h5_files) > 1:
        names = [f.name for f in h5_files]
        raise ValueError(
            f"Multiple wavesurfer .h5 files found in {session_dir}: {names}. "
            f"Expected exactly one. Check for session merge entries in "
            f"configs/session_overrides.yaml."
        )
    return h5_files[0]


# ---- Treadmill calibration (ported from calibrate_and_smooth_treadmill_signal_PS.py) ----


def calibrate_treadmill(
    signal_in_volts: np.ndarray,
    offset_in_volts: float,
    voltSec_per_rot: float,
    mm_per_rot: float,
) -> np.ndarray:
    """Convert raw treadmill voltage to speed in mm/s.

    Parameters
    ----------
    signal_in_volts : np.ndarray
        Raw treadmill voltage trace.
    offset_in_volts : float
        Voltage offset to subtract.
    voltSec_per_rot : float
        Volt-seconds per wheel rotation.
    mm_per_rot : float
        Millimeters per wheel rotation (circumference).

    Returns
    -------
    np.ndarray
        Calibrated speed in mm/s.
    """
    return (signal_in_volts - offset_in_volts) * (1.0 / voltSec_per_rot) * mm_per_rot


def smooth_treadmill(
    signal: np.ndarray, Fs: float, sigma_sec: float
) -> np.ndarray:
    """Apply Gaussian smoothing to a treadmill signal.

    Parameters
    ----------
    signal : np.ndarray
        Calibrated treadmill speed (mm/s).
    Fs : float
        Sampling rate in Hz.
    sigma_sec : float
        Gaussian kernel sigma in seconds.

    Returns
    -------
    np.ndarray
        Smoothed signal.
    """
    sigma_samples = int(sigma_sec * Fs)
    return gaussian_smooth_1d(signal, sig=sigma_samples)


def _normalize_date_candidates(date: str | None) -> list[str]:
    """Return candidate date strings for override lookup.

    Supports: '20250425', '20250425a', '2025-04-25'.
    """
    if date is None:
        return []
    date_str = str(date)
    candidates = [date_str]

    digits8 = re.search(r"(\d{8})", date_str)
    if digits8:
        candidates.append(digits8.group(1))

    date_iso = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", date_str)
    if date_iso:
        candidates.append("".join(date_iso.groups()))

    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def resolve_treadmill_offset(
    params: dict[str, Any],
    session_params: dict[str, Any] | None = None,
) -> tuple[float, bool, str]:
    """Resolve which treadmill voltage offset to use.

    Priority:
      1. session_params["process_treadmill_signal"]["offset_in_volts"]
         (from session_overrides.yaml, already merged by the caller)
      2. params["offset_in_volts"] (cohort-wide default from defaults.yaml)

    Parameters
    ----------
    params : dict
        The ``process_treadmill_signal`` section from defaults.yaml.
    session_params : dict or None
        The ``process_treadmill_signal`` section from session_overrides.yaml
        for this specific animal+date, or None if no override exists.

    Returns
    -------
    tuple[float, bool, str]
        (offset_used, override_applied, source_description)
    """
    default_offset = float(params["offset_in_volts"])

    if session_params is not None:
        override_val = session_params.get("offset_in_volts")
        if override_val is not None:
            return float(override_val), True, "session_overrides.yaml"

    return default_offset, False, "defaults.yaml"
