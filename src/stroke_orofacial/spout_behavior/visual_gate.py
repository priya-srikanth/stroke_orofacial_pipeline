"""Phase 8a.10 sub-deliverable A — per-mouse legacy-parity visual gate.

Shared infrastructure for the 11 per-mouse plot-family renderers
ported in subsequent commit-groups. This module hosts:

- Date-label parsing helpers (port of ``behavior_report_PS.py:43-67``).
- Cohort A iteration (authoritative cohort from legacy
  ``basic_behavior_analysis3/<mouse>/report.json`` keys per Task 0.5
  extension audit; bare-date subset for longitudinal plots).
- Stroke-alignment longitudinal-axis helper (port of
  ``behavior_report_PS.py:346-370``).
- Per-session Phase-2 NPZ loader.
- File saver writing SVG + PNG to ``pipeline_outputs/spout_behavior/
  visual_gate/<animal>/``.
- ``SIDE_COLORS`` constant — INVERTED vs legacy (legacy operated
  wavesurfer-frame internally and re-labeled at plot output via
  ``fn_flip_lr()``; the new pipeline operates mouse-frame post-
  Phase-6.8). Loaded from ``configs/defaults.yaml visual_gate:`` block.

This file intentionally contains NO plot-family renderers — those land
in commit-groups 2-4. The shape of the public API here is the contract
those renderers consume.
"""
from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver


# ---- Date helpers (port of behavior_report_PS.py:43-67) ----

_BASE_DATE_RE = re.compile(r"^(?P<base>\d{8})")


def parse_base_date(session_label: str) -> str:
    """Extract the bare ``YYYYMMDD`` from a session label.

    Examples: ``"20250430"`` → ``"20250430"``, ``"20250430b"`` →
    ``"20250430"``, ``"20250314a"`` → ``"20250314"``. Raises
    :class:`ValueError` if the label doesn't start with 8 digits.
    """
    m = _BASE_DATE_RE.match(str(session_label))
    if m is None:
        raise ValueError(f"Could not parse base date from session label: {session_label}")
    return m.group("base")


def ymd_to_date(ymd: str) -> datetime.date:
    """Convert a ``YYYYMMDD`` string to :class:`datetime.date`."""
    return datetime.date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))


def format_rel_day(rel_day: int) -> str:
    """Format a stroke-relative day as ``"d0"`` / ``"d-3"`` / ``"d+5"``."""
    if rel_day == 0:
        return "d0"
    return f"d{rel_day:+d}"


# ---- Cohort A iteration ----


def iter_cohort_a_sessions(
    animal: str,
    resolver: PathResolver,
    *,
    include_b_half: bool = False,
) -> list[str]:
    """Return the animal's sorted Cohort A session labels.

    Authoritative cohort definition per Task 0.5 extension audit: the
    keys of ``latency_bySession`` in legacy
    ``basic_behavior_analysis3/<animal>/report.json``. This is what
    legacy actually emitted (more reliable than rebuilding from
    MOUSE_SPECS ``include_dates ∖ exclude_dates``).

    Parameters
    ----------
    animal : str
        e.g. ``"PS51"``.
    resolver : PathResolver
        Source: ``{local_processed_spout}/basic_behavior_analysis3/
        <animal>/report.json``.
    include_b_half : bool, default ``False``
        Longitudinal plots default. When ``False``, session labels
        ending in a single ``[a-z]`` suffix (e.g. ``20250430b``) are
        dropped — those are Pattern B b-half sessions and the bare-vs-b
        comparison is a separate sub-deliverable. The PS48/2025-03-14
        Pattern A multi-half session is naturally included because its
        merged-licks NPZ lives at the bare-date path ``20250314.npz``
        (Phase 7-pre-multi-half emission). Set ``True`` for bare-vs-b
        scope.
    """
    report_path = (
        resolver.root("local_processed_spout")
        / "basic_behavior_analysis3"
        / animal
        / "report.json"
    )
    if not report_path.exists():
        raise FileNotFoundError(
            f"Cohort A report.json missing for {animal}: {report_path}"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw_keys = list(report.get("latency_bySession", {}).keys())
    if not include_b_half:
        # Keep labels that are exactly 8 digits (no suffix). Legacy
        # label format is YYYYMMDD[a-z]? per parse_base_date(); the
        # canonical Cohort-A longitudinal subset is the no-suffix
        # entries. PS48/20250314 lands here automatically.
        raw_keys = [k for k in raw_keys if re.fullmatch(r"\d{8}", k)]
    return sorted(raw_keys)


# ---- Longitudinal-axis helper (port of behavior_report_PS.py:346-370) ----


@dataclass
class LongitudinalAxis:
    """Resolved x-axis for a per-mouse longitudinal plot.

    Attributes
    ----------
    x_vals : np.ndarray
        Numeric x-positions per session. For ``align_to_stroke=True``,
        these are stroke-relative day counts (negative = pre-stroke);
        otherwise ``np.arange(len(dates))``.
    x_ticklabels : list[str]
        Per-session tick label text. For stroke-aligned: ``"d-3"``,
        ``"d0"``, ``"d+5"`` form. Otherwise the session label itself.
    vline_x : float or None
        X-position of the stroke-day vertical marker, or ``None`` when
        not stroke-aligned (no marker).
    suffix : str
        Filename suffix passed to :func:`save_visual_gate_figure`:
        ``"_relStroke"`` when aligned, ``"_absDate"`` otherwise.
    """

    x_vals: np.ndarray
    x_ticklabels: list[str]
    vline_x: float | None
    suffix: str


def compute_longitudinal_axis(
    dates: list[str],
    *,
    align_to_stroke: bool,
    d0: datetime.date | None,
    display_dates: dict[str, str] | None = None,
    vline_x: float = 0.5,
) -> LongitudinalAxis:
    """Resolve the x-axis for a per-mouse longitudinal plot.

    Parameters
    ----------
    dates : list[str]
        Cohort A session labels (bare YYYYMMDD strings; see
        :func:`iter_cohort_a_sessions`).
    align_to_stroke : bool
        When ``True``, x_vals are stroke-relative day counts and
        ``d0`` is required.
    d0 : datetime.date or None
        Last pre-stroke session date (the ``stroke_date`` field on
        :class:`stroke_orofacial.animals.AnimalInfo`). Required when
        ``align_to_stroke=True``.
    display_dates : dict[str, str] or None
        Optional override mapping ``date_label → tick_label`` used
        only when ``align_to_stroke=False``. Defaults to identity
        (each date is its own tick label).
    vline_x : float, default 0.5
        Stroke marker x-offset (legacy default: 0.5, i.e. midway
        between the last pre-stroke day and the first post-stroke day).
    """
    if align_to_stroke and d0 is None:
        raise ValueError("compute_longitudinal_axis: align_to_stroke=True requires d0")
    if align_to_stroke:
        x_vals = np.array(
            [(ymd_to_date(d) - d0).days for d in dates], dtype=int,
        )
        x_ticklabels = [format_rel_day(int(v)) for v in x_vals]
        return LongitudinalAxis(
            x_vals=x_vals,
            x_ticklabels=x_ticklabels,
            vline_x=vline_x,
            suffix="_relStroke",
        )
    display = display_dates or {d: d for d in dates}
    return LongitudinalAxis(
        x_vals=np.arange(len(dates), dtype=int),
        x_ticklabels=[display.get(d, d) for d in dates],
        vline_x=None,
        suffix="_absDate",
    )


def apply_longitudinal_axis(
    ax,
    longitudinal_axis: LongitudinalAxis,
    visual_gate_config: dict[str, Any],
) -> None:
    """Set xticks, xticklabels, and the stroke-day vertical marker.

    Reads ``xtick_fontsize``, ``stroke_linewidth``, ``stroke_vline_color``,
    ``stroke_vline_linestyle``, ``stroke_vline_alpha`` from
    ``visual_gate_config`` (the ``visual_gate:`` block of
    ``configs/defaults.yaml``).
    """
    ax.set_xticks(longitudinal_axis.x_vals)
    ax.set_xticklabels(
        longitudinal_axis.x_ticklabels,
        rotation=90,
        fontsize=visual_gate_config["xtick_fontsize"],
    )
    if longitudinal_axis.vline_x is not None:
        ax.axvline(
            longitudinal_axis.vline_x,
            color=visual_gate_config["stroke_vline_color"],
            linestyle=visual_gate_config["stroke_vline_linestyle"],
            linewidth=visual_gate_config["stroke_linewidth"],
            alpha=visual_gate_config["stroke_vline_alpha"],
        )


def legend_label_for_date(
    date_label: str,
    *,
    align_to_stroke: bool,
    d0: datetime.date | None,
    display_dates: dict[str, str] | None = None,
) -> str:
    """Return the legend / title label for a single session.

    Stroke-aligned: ``"d-3"`` / ``"d0"`` / ``"d+5"`` form. Otherwise
    the display label (defaults to the bare date string).
    """
    if align_to_stroke:
        if d0 is None:
            raise ValueError(
                "legend_label_for_date: align_to_stroke=True requires d0"
            )
        rel = (ymd_to_date(parse_base_date(date_label)) - d0).days
        return format_rel_day(int(rel))
    if display_dates is not None and date_label in display_dates:
        return display_dates[date_label]
    return str(date_label)


# ---- Per-session Phase-2 NPZ loader ----


@dataclass
class SessionPlotData:
    """Per-session inputs for one Cohort A entry.

    Attributes
    ----------
    date_label : str
        Bare ``YYYYMMDD`` label (no suffix; longitudinal-only scope).
    lick_idx : dict[str, np.ndarray]
        Mouse-frame lick sample indices: ``{"Lick_L": ..., "Lick_R": ...}``.
        Post-Phase-6.8 the labels are mouse-frame directly (no further
        translation needed).
    rewards_idx : dict[str, np.ndarray]
        Mouse-frame reward sample indices: ``{"Reward_L": ...,
        "Reward_R": ...}``.
    sample_rate : float
        Wavesurfer sample rate (Hz). Pulled from the Phase 1
        ``wavesurfer_signals_processed`` NPZ's ``sample_rate_input``
        scalar.
    n_samples_session : int
        Total wavesurfer-signal length in samples for this session.
        Read from the first 1D signal in the
        ``wavesurfer_signals_processed`` NPZ (e.g. ``Treadmill``).
        ``0`` falls back when the NPZ has no 1D signal — downstream
        consumers (lickiness window cap) treat 0 as "no cap available"
        and silently skip the post-last-reward window. Mirrors legacy
        ``n_samps = data_ws[date][next(iter(data_ws[date]))].shape[0]``
        (behavior_report_PS.py:862).
    """

    date_label: str
    lick_idx: dict[str, np.ndarray]
    rewards_idx: dict[str, np.ndarray]
    sample_rate: float
    n_samples_session: int = 0


def load_session_plot_data(
    animal: str,
    date_label: str,
    resolver: PathResolver,
) -> SessionPlotData:
    """Load Phase-2 + Phase-1 inputs for one Cohort A session.

    Reads:
      - ``pipeline_outputs/spout_behavior/licks_and_rewards/<animal>/
        <date_label>.npz`` for ``Lick_{L,R}`` + ``Reward_{L,R}``.
      - ``pipeline_outputs/spout_behavior/wavesurfer_signals_processed/
        <animal>/<date_label>.npz`` for ``sample_rate_input``.

    The PS48/2025-03-14 Pattern A multi-half merge naturally lands at
    the bare-date path ``20250314.npz`` (Phase 7-pre-multi-half
    emission). No special-case here; the loader reads the same flat
    path for every Cohort A entry.

    Raises
    ------
    FileNotFoundError
        If either NPZ is missing on disk.
    """
    sp_root = resolver.pipeline_outputs("spout_behavior")
    licks_path = sp_root / "licks_and_rewards" / animal / f"{date_label}.npz"
    ws_path = (
        sp_root / "wavesurfer_signals_processed" / animal / f"{date_label}.npz"
    )
    if not licks_path.exists():
        raise FileNotFoundError(f"licks_and_rewards NPZ missing: {licks_path}")
    if not ws_path.exists():
        raise FileNotFoundError(
            f"wavesurfer_signals_processed NPZ missing: {ws_path}"
        )
    with np.load(licks_path, allow_pickle=True) as licks:
        lick_idx = {key: licks[key] for key in ("Lick_L", "Lick_R")}
        rewards_idx = {key: licks[key] for key in ("Reward_L", "Reward_R")}
    n_samples_session = 0
    with np.load(ws_path, allow_pickle=True) as ws:
        sample_rate = float(ws["sample_rate_input"])
        # First 1D signal's length = total session sample count. Phase
        # 2 wavesurfer_signals_processed NPZs typically include
        # ``Treadmill`` / ``Lick_L_signal`` etc.; any 1D entry works
        # (they all share the session length). Scalars and 0-d arrays
        # (e.g. ``sample_rate_input``) are skipped.
        for key in ws.files:
            arr = ws[key]
            if arr.ndim == 1:
                n_samples_session = int(arr.shape[0])
                break
    return SessionPlotData(
        date_label=date_label,
        lick_idx=lick_idx,
        rewards_idx=rewards_idx,
        sample_rate=sample_rate,
        n_samples_session=n_samples_session,
    )


# ---- Side-convention config + file saver ----


def load_visual_gate_config(
    defaults_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return the ``visual_gate:`` block of ``configs/defaults.yaml``.

    Raises :class:`KeyError` if the block is absent (loud failure beats
    silent default-blowback).
    """
    defaults = load_defaults(defaults_path)
    if "visual_gate" not in defaults:
        raise KeyError(
            "configs/defaults.yaml: 'visual_gate:' block missing — "
            "Phase 8a.10 commit-group 1 should have added it"
        )
    return defaults["visual_gate"]


def _load_side_colors() -> dict[str, str]:
    """Module-load-time resolution of the SIDE_COLORS dict.

    Pulled from ``visual_gate.side_colors`` in defaults.yaml. Validates
    that both ``"L"`` and ``"R"`` keys are present.
    """
    cfg = load_visual_gate_config()
    sc = cfg.get("side_colors", {})
    if set(sc.keys()) != {"L", "R"}:
        raise KeyError(
            "configs/defaults.yaml: visual_gate.side_colors must have "
            f"exactly 'L' and 'R' keys; got {set(sc.keys())}"
        )
    return {"L": str(sc["L"]), "R": str(sc["R"])}


SIDE_COLORS: dict[str, str] = _load_side_colors()
"""Mouse-frame side color palette.

INVERTED vs the legacy `side_colors` dict in
`behavior_report_PS.py:250`. Legacy had
``{"L": "mediumvioletred", "R": "dodgerblue"}`` because legacy
operated in wavesurfer-frame internally and re-labeled at plot output
via `fn_flip_lr()`. The new pipeline operates in mouse-frame post-
Phase-6.8 — `data["Lick_L"]` is mouse-L lick data — so the color↔
mouse-side mapping is direct: mouse-L → dodgerblue, mouse-R →
mediumvioletred.

Pinned by ``test_side_colors_inverted_vs_legacy`` to catch any
regression to the legacy WS-frame palette.
"""


def save_visual_gate_figure(
    fig,
    animal: str,
    plot_family: str,
    suffix: str,
    resolver: PathResolver,
    *,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Save a figure to the per-mouse visual-gate output directory.

    Writes SVG + PNG at
    ``{resolver.visual_gate_dir(animal)}/{plot_family}{suffix}.{svg,png}``.
    The legacy emitter saved SVG + PNG via ``bnpm.plotting_helpers.
    Figure_Saver``; this is a slim equivalent (no bnpm dependency).

    Parameters
    ----------
    suffix : str
        Filename suffix from :class:`LongitudinalAxis.suffix` —
        ``"_relStroke"`` or ``"_absDate"`` — or ``""`` for plot
        families that aren't longitudinal (e.g. the lick raster).
    overwrite : {"force", "skip", "raise"}
        ``"force"``: always overwrite. ``"skip"``: silently skip if a
        target file exists; returns the existing paths. ``"raise"``:
        :class:`FileExistsError` if any target file exists.

    Returns
    -------
    tuple[Path, Path]
        ``(svg_path, png_path)``.
    """
    out_dir = resolver.visual_gate_dir(animal)
    svg_path = out_dir / f"{plot_family}{suffix}.svg"
    png_path = out_dir / f"{plot_family}{suffix}.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    for target in (svg_path, png_path):
        if not target.exists():
            continue
        if overwrite == "raise":
            raise FileExistsError(f"visual_gate target exists: {target}")
        if overwrite == "skip":
            return svg_path, png_path
    fig.savefig(svg_path, format="svg")
    fig.savefig(png_path, format="png", dpi=300)
    return svg_path, png_path


# =====================================================================
# Commit-group 2: per-trial compute helpers + longitudinal-mean renderers
# =====================================================================
#
# Shared compute helpers ported from behavior_report_PS.py's main() body
# (lines 390-850). The legacy emitter built these compute structures
# inline and re-used them across plot calls; the new pipeline factors
# them into testable helpers. Each helper operates on ONE
# :class:`SessionPlotData` and returns the equivalent of the legacy
# `sig_*` dicts.
#
# The 8 render functions (the longitudinal-mean subset of sub-deliverable
# A) consume these helpers + the CG-1 longitudinal-axis infrastructure.
# All renderers follow the same shape: iterate Cohort A → load
# SessionPlotData → compute per-side per-session statistics → render
# longitudinal plot → save via :func:`save_visual_gate_figure`.


def load_behavior_report_params(
    defaults_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return the ``behavior_report:`` block of ``configs/defaults.yaml``.

    Cohort-wide criteria + window params (mirrors legacy
    ``batch_process_behavior_report_20260116PS.ipynb`` cell-3 ``params``
    dict). Raises :class:`KeyError` if the block is absent — loud
    failure beats silent default-blowback.
    """
    defaults = load_defaults(defaults_path)
    if "behavior_report" not in defaults:
        raise KeyError(
            "configs/defaults.yaml: 'behavior_report:' block missing — "
            "Phase 8a.10 commit-group 2 should have added it"
        )
    return defaults["behavior_report"]


# ---- Private compute primitives ----


def _window_to_samples(
    window_seconds: tuple[float, float] | list[float],
    sample_rate: float,
) -> tuple[int, int]:
    """Convert a ``(before, after)`` seconds window to sample counts.

    Mirrors legacy ``fn_convert_window_to_samples`` lambda.
    """
    return int(window_seconds[0] * sample_rate), int(window_seconds[1] * sample_rate)


def _find_idx_within_window(
    sample_indices: np.ndarray,
    query_sample: int,
    window_samples: tuple[int, int],
) -> np.ndarray:
    """Return positions in ``sample_indices`` within
    ``[query - before, query + after]`` (inclusive).

    Replaces legacy ``bnpm.indexing.find_idx_within_eps`` with
    ``eps=(before, after)`` semantics. No bnpm dep.
    """
    lo = query_sample - window_samples[0]
    hi = query_sample + window_samples[1]
    return np.where(
        (sample_indices >= lo) & (sample_indices <= hi)
    )[0]


# ---- Public compute helpers (per-session) ----


def compute_trial_lick_delays(
    session_data: SessionPlotData,
    window_seconds: tuple[float, float] | list[float],
) -> dict[str, dict[int, dict[str, np.ndarray]]]:
    """Per-reward, per-side lick delays around each reward delivery.

    Mirrors legacy ``sig_idxLickDelays__idx_idxLicks[date]`` (lines
    390-408). Returns nested dict:
    ``{"Reward_L": {reward_idx: {"Lick_L": delays, "Lick_R": delays}}, "Reward_R": {...}}``
    where ``delays`` is an array of lick sample indices relative to the
    reward sample (i.e. ``lick_sample - reward_sample``). Negative
    values = lick before reward.
    """
    window_samples = _window_to_samples(window_seconds, session_data.sample_rate)
    out: dict[str, dict[int, dict[str, np.ndarray]]] = {}
    for side_reward in ("L", "R"):
        rewards = session_data.rewards_idx[f"Reward_{side_reward}"]
        per_reward: dict[int, dict[str, np.ndarray]] = {}
        for idx_reward, reward_sample in enumerate(rewards):
            per_side_licks: dict[str, np.ndarray] = {}
            for side_lick in ("L", "R"):
                licks = session_data.lick_idx[f"Lick_{side_lick}"]
                positions = _find_idx_within_window(
                    licks, int(reward_sample), window_samples,
                )
                per_side_licks[f"Lick_{side_lick}"] = (
                    licks[positions] - int(reward_sample)
                )
            per_reward[idx_reward] = per_side_licks
        out[f"Reward_{side_reward}"] = per_reward
    return out


def compute_first_correct_lick_sample_idx(
    session_data: SessionPlotData,
    criteria_3_window_seconds: tuple[float, float] | list[float],
) -> dict[str, dict[int, int | None]]:
    """First correct lick sample index per (side, trial), within
    criteria_3 window after each reward. ``None`` if no correct lick.

    Mirrors legacy ``sig_idxFirstCorrectLick__idx_idxLicks`` (lines
    455-472). Note: this uses a TIGHTER window than
    :func:`compute_trial_lick_delays` (criteria_3 window, typically
    ``(0, 2.0)``).
    """
    window_samples = _window_to_samples(
        criteria_3_window_seconds, session_data.sample_rate,
    )
    out: dict[str, dict[int, int | None]] = {}
    for side in ("L", "R"):
        rewards = session_data.rewards_idx[f"Reward_{side}"]
        correct_licks = session_data.lick_idx[f"Lick_{side}"]
        per_reward: dict[int, int | None] = {}
        for idx_reward, reward_sample in enumerate(rewards):
            positions = _find_idx_within_window(
                correct_licks, int(reward_sample), window_samples,
            )
            if positions.size == 0:
                per_reward[idx_reward] = None
            else:
                per_reward[idx_reward] = int(correct_licks[positions[0]])
        out[side] = per_reward
    return out


def compute_criteria_3(
    first_correct_lick_idx: dict[str, dict[int, int | None]],
) -> dict[str, dict[int, bool]]:
    """Criteria 3: a correct lick exists within criteria_3 window.

    Mirrors legacy lines 474-480.
    """
    return {
        side: {
            idx: (fcl is not None)
            for idx, fcl in per_reward.items()
        }
        for side, per_reward in first_correct_lick_idx.items()
    }


def compute_criteria_4(
    session_data: SessionPlotData,
    criteria_4_params: dict[str, Any],
) -> dict[str, dict[int, bool]]:
    """Criteria 4: ≥num_licks_correct_min correct licks AND
    ≤num_licks_incorrect_max incorrect licks within criteria_4 window.

    Mirrors legacy ``sig_ws__idx_LicksWithinEps`` (lines 484-503) +
    criteria_4 evaluation (lines 505-518). Uses a SEPARATE window
    from :func:`compute_trial_lick_delays`.
    """
    window_samples = _window_to_samples(
        criteria_4_params["window"], session_data.sample_rate,
    )
    n_corr_min = int(criteria_4_params["num_licks_correct_min"])
    n_incorr_max = int(criteria_4_params["num_licks_incorrect_max"])
    out: dict[str, dict[int, bool]] = {}
    for side_reward in ("L", "R"):
        rewards = session_data.rewards_idx[f"Reward_{side_reward}"]
        per_reward: dict[int, bool] = {}
        for idx_reward, reward_sample in enumerate(rewards):
            n_correct = _find_idx_within_window(
                session_data.lick_idx[f"Lick_{side_reward}"],
                int(reward_sample),
                window_samples,
            ).size
            other_side = "R" if side_reward == "L" else "L"
            n_incorrect = _find_idx_within_window(
                session_data.lick_idx[f"Lick_{other_side}"],
                int(reward_sample),
                window_samples,
            ).size
            per_reward[idx_reward] = bool(
                (n_correct >= n_corr_min) and (n_incorrect <= n_incorr_max)
            )
        out[side_reward] = per_reward
    return out


def compute_criteria_34(
    criteria_3: dict[str, dict[int, bool]],
    criteria_4: dict[str, dict[int, bool]],
) -> dict[str, dict[int, bool]]:
    """Per-trial AND of criteria 3 and 4. Mirrors legacy lines 520-529."""
    return {
        side: {
            idx: bool(criteria_3[side][idx] and criteria_4[side][idx])
            for idx in criteria_3[side]
        }
        for side in criteria_3
    }


def compute_first_lick_correct(
    trial_lick_delays: dict[str, dict[int, dict[str, np.ndarray]]],
) -> dict[str, dict[int, bool | None]]:
    """First-lick correctness per trial.

    Mirrors legacy ``sig_firstLickCorrect`` (lines 583-596). For each
    reward, considers only post-reward licks (delay ≥ 0): correct =
    first correct lick precedes any incorrect lick; ``None`` if no
    post-reward licks on either side (no information to score).
    """
    out: dict[str, dict[int, bool | None]] = {}
    for side_reward in ("L", "R"):
        per_reward: dict[int, bool | None] = {}
        for idx_reward, by_side in trial_lick_delays[f"Reward_{side_reward}"].items():
            other_side = "R" if side_reward == "L" else "L"
            correct_delays = by_side[f"Lick_{side_reward}"]
            incorrect_delays = by_side[f"Lick_{other_side}"]
            correct_post = correct_delays[correct_delays >= 0]
            incorrect_post = incorrect_delays[incorrect_delays >= 0]
            if len(correct_post) > 0:
                if len(incorrect_post) > 0:
                    per_reward[idx_reward] = bool(correct_post[0] < incorrect_post[0])
                else:
                    per_reward[idx_reward] = True
            else:
                if len(incorrect_post) > 0:
                    per_reward[idx_reward] = False
                else:
                    per_reward[idx_reward] = None
        out[side_reward] = per_reward
    return out


def compute_criteria_acc_bySession(
    criteria_34: dict[str, dict[int, bool]],
) -> dict[str, float]:
    """Fraction of trials passing criteria 3 AND 4, per side."""
    out: dict[str, float] = {}
    for side, per_reward in criteria_34.items():
        if len(per_reward) == 0:
            out[side] = float("nan")
        else:
            out[side] = float(np.mean(list(per_reward.values())))
    return out


def compute_firstLickCorrect_bySession(
    first_lick_correct: dict[str, dict[int, bool | None]],
    *,
    treat_none_as_zero: bool = False,
) -> dict[str, float]:
    """Mean first-lick-correct per side.

    ``treat_none_as_zero=False`` (default) matches ``accuracy_firstCorrectLick``
    semantics — None values excluded (nanmean over float-cast).
    ``True`` matches ``accuracy_firstCorrectLickAll`` semantics — None
    treated as 0 (incorrect / no-lick counts against accuracy).
    """
    out: dict[str, float] = {}
    for side, per_reward in first_lick_correct.items():
        if treat_none_as_zero:
            arr = np.array(
                [0.0 if v is None else float(v) for v in per_reward.values()],
                dtype=float,
            )
            out[side] = float(arr.mean()) if arr.size > 0 else float("nan")
        else:
            arr = np.array(
                [np.nan if v is None else float(v) for v in per_reward.values()],
                dtype=float,
            )
            out[side] = float(np.nanmean(arr)) if arr.size > 0 else float("nan")
    return out


def compute_median_lick_rate_bySession(
    trial_lick_delays: dict[str, dict[int, dict[str, np.ndarray]]],
    sample_rate: float,
) -> dict[str, dict[str, float]]:
    """Per-side mean ± std of trial-median correct-lick rates (Hz).

    Mirrors legacy ``sig_meanStd_MedianCorrectLickRate`` (lines 642-678).
    """
    per_side: dict[str, dict[str, float]] = {}
    for side_reward in ("L", "R"):
        rates: list[float] = []
        for by_side in trial_lick_delays[f"Reward_{side_reward}"].values():
            correct_delays = by_side[f"Lick_{side_reward}"]
            ilis = np.diff(correct_delays)
            if ilis.size == 0:
                rates.append(0.0)
            else:
                med = float(np.median(ilis))
                hz = 0.0 if med <= 0 else float(1.0 / (med / sample_rate))
                rates.append(0.0 if not np.isfinite(hz) else hz)
        if len(rates) == 0:
            per_side[side_reward] = {"mean": float("nan"), "std": float("nan")}
        else:
            per_side[side_reward] = {
                "mean": float(np.nanmean(rates)),
                "std": float(np.nanstd(rates)),
            }
    return per_side


def compute_num_licks_bySession(
    trial_lick_delays: dict[str, dict[int, dict[str, np.ndarray]]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Per-side mean ± std of per-trial lick counts.

    Returns a 3-level dict:
    ``{"correct": {"Reward_L": {"mean": x, "std": y}, "Reward_R": ...},
       "all":     {"Reward_L": ..., "Reward_R": ...},
       "incorrect": {"Reward_L": ..., "Reward_R": ...}}``

    Mirrors legacy ``sig_meanStd_numCorrectLicksPerTrial`` /
    ``sig_meanStd_numAllLicksPerTrial`` /
    ``sig_meanStd_numIncorrectLicksPerTrial`` (lines 705-747).
    """
    out: dict[str, dict[str, dict[str, float]]] = {
        "correct": {}, "all": {}, "incorrect": {},
    }
    for side_reward in ("L", "R"):
        other = "R" if side_reward == "L" else "L"
        n_correct: list[int] = []
        n_all: list[int] = []
        n_incorrect: list[int] = []
        for by_side in trial_lick_delays[f"Reward_{side_reward}"].values():
            n_correct.append(int(by_side[f"Lick_{side_reward}"].size))
            n_all.append(int(by_side["Lick_L"].size + by_side["Lick_R"].size))
            n_incorrect.append(int(by_side[f"Lick_{other}"].size))
        for kind, values in (
            ("correct", n_correct), ("all", n_all), ("incorrect", n_incorrect),
        ):
            if len(values) == 0:
                out[kind][f"Reward_{side_reward}"] = {
                    "mean": float("nan"), "std": float("nan"),
                }
            else:
                out[kind][f"Reward_{side_reward}"] = {
                    "mean": float(np.nanmean(values)),
                    "std": float(np.nanstd(values)),
                }
    return out


def compute_latency_bySession(
    first_correct_lick_idx: dict[str, dict[int, int | None]],
    rewards_idx: dict[str, np.ndarray],
    sample_rate: float,
) -> dict[str, dict[str, float]]:
    """Per-side mean ± std of latency (seconds) to first correct lick.

    Mirrors legacy ``latency_meanStd_bySide`` (lines 805-829).
    ``None`` first-correct-lick entries become ``NaN`` and excluded
    from the mean/std.
    """
    out: dict[str, dict[str, float]] = {}
    for side in ("L", "R"):
        rewards = rewards_idx[f"Reward_{side}"]
        latencies: list[float] = []
        for idx_reward, fcl in first_correct_lick_idx[side].items():
            if fcl is None:
                latencies.append(float("nan"))
            else:
                latencies.append(
                    (fcl - int(rewards[idx_reward])) / sample_rate
                )
        arr = np.array(latencies, dtype=float)
        if arr.size == 0:
            out[side] = {"mean": float("nan"), "std": float("nan")}
        else:
            out[side] = {
                "mean": float(np.nanmean(arr)),
                "std": float(np.nanstd(arr)),
            }
    return out


# ---- Renderer skeleton: per-session compute aggregation ----


@dataclass
class _PerSessionStats:
    """Per-session compute outputs aggregated across Cohort A.

    Internal-detail dataclass used by the longitudinal-mean renderers.
    """
    dates: list[str]
    criteria_acc: dict[str, list[float]]
    firstLickCorrect_excludeNone: dict[str, list[float]]
    firstLickCorrect_treatNoneZero: dict[str, list[float]]
    medianLickRate: dict[str, list[dict[str, float]]]
    numLicks: dict[str, dict[str, list[dict[str, float]]]]
    latency: dict[str, list[dict[str, float]]]


def _compute_per_session_stats(
    animal: str,
    resolver: PathResolver,
    behavior_params: dict[str, Any],
) -> _PerSessionStats:
    """Iterate Cohort A and compute every per-session statistic the
    CG-2 renderers need. Single pass over the cohort to avoid
    re-loading NPZs per renderer.
    """
    dates = iter_cohort_a_sessions(animal, resolver)
    window_around = behavior_params["window_around_rewards"]
    crit3_window = behavior_params["criteria_3"]["window"]

    criteria_acc: dict[str, list[float]] = {"L": [], "R": []}
    flc_excl: dict[str, list[float]] = {"L": [], "R": []}
    flc_zero: dict[str, list[float]] = {"L": [], "R": []}
    median_rate: dict[str, list[dict[str, float]]] = {"L": [], "R": []}
    num_licks: dict[str, dict[str, list[dict[str, float]]]] = {
        "correct": {"Reward_L": [], "Reward_R": []},
        "all": {"Reward_L": [], "Reward_R": []},
        "incorrect": {"Reward_L": [], "Reward_R": []},
    }
    latency: dict[str, list[dict[str, float]]] = {"L": [], "R": []}

    for date in dates:
        data = load_session_plot_data(animal, date, resolver)
        delays = compute_trial_lick_delays(data, window_around)
        fcl_idx = compute_first_correct_lick_sample_idx(data, crit3_window)
        c3 = compute_criteria_3(fcl_idx)
        c4 = compute_criteria_4(data, behavior_params["criteria_4"])
        c34 = compute_criteria_34(c3, c4)
        first_corr = compute_first_lick_correct(delays)

        acc = compute_criteria_acc_bySession(c34)
        flc_exclude = compute_firstLickCorrect_bySession(
            first_corr, treat_none_as_zero=False,
        )
        flc_treat_zero = compute_firstLickCorrect_bySession(
            first_corr, treat_none_as_zero=True,
        )
        ms_rate = compute_median_lick_rate_bySession(delays, data.sample_rate)
        ms_num = compute_num_licks_bySession(delays)
        ms_lat = compute_latency_bySession(
            fcl_idx, data.rewards_idx, data.sample_rate,
        )

        for side in ("L", "R"):
            criteria_acc[side].append(acc[side])
            flc_excl[side].append(flc_exclude[side])
            flc_zero[side].append(flc_treat_zero[side])
            median_rate[side].append(ms_rate[side])
            latency[side].append(ms_lat[side])
        for kind in ("correct", "all", "incorrect"):
            for side_reward in ("Reward_L", "Reward_R"):
                num_licks[kind][side_reward].append(ms_num[kind][side_reward])

    return _PerSessionStats(
        dates=dates,
        criteria_acc=criteria_acc,
        firstLickCorrect_excludeNone=flc_excl,
        firstLickCorrect_treatNoneZero=flc_zero,
        medianLickRate=median_rate,
        numLicks=num_licks,
        latency=latency,
    )


def _resolve_d0(
    animal_info: AnimalInfo | None, animal: str, align_to_stroke: bool,
) -> datetime.date | None:
    if not align_to_stroke:
        return None
    if animal_info is None:
        animal_info = get_animal(animal)
    return animal_info.stroke_date


# ---- 8 longitudinal-mean renderers ----


def render_criteria_performance(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Render the per-mouse criteria-performance longitudinal plot.

    Mirrors legacy ``criteria_performance`` (behavior_report_PS.py:556-565):
    fraction of trials passing criteria 3 AND 4 per session, one line
    per mouse-frame side.

    Returns ``(svg_path, png_path)``.
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        ax.plot(
            axis.x_vals, stats.criteria_acc[side], "o-",
            color=SIDE_COLORS[side], label=f"mouse {side}",
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(*config["accuracy_y_range"])
    ax.set_ylabel("fraction of trials meeting criteria 3 and 4")
    ax.set_title("Criteria performance by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "criteria_performance", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_accuracy_firstCorrectLick(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Fraction of LICKING trials with correct first lick (None excluded).

    Mirrors legacy ``accuracy_firstCorrectLick`` (behavior_report_PS.py:607-616).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        ax.plot(
            axis.x_vals, stats.firstLickCorrect_excludeNone[side], "o-",
            color=SIDE_COLORS[side], label=f"mouse {side}",
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(*config["accuracy_y_range"])
    ax.set_ylabel("Fraction of trials with correct 1st lick")
    ax.set_title("Fraction of licking trials with correct first lick, by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "accuracy_firstCorrectLick", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_accuracy_firstCorrectLickAll(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Fraction of ALL trials with correct first lick (None treated as 0).

    Mirrors legacy ``accuracy_firstCorrectLickAll`` (behavior_report_PS.py:628-637).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        ax.plot(
            axis.x_vals, stats.firstLickCorrect_treatNoneZero[side], "o-",
            color=SIDE_COLORS[side], label=f"mouse {side}",
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(*config["accuracy_y_range"])
    ax.set_ylabel("Fraction of all trials with correct 1st lick")
    ax.set_title("Fraction of all trials with correct first lick, by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "accuracy_firstCorrectLickAll", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_lickRate_bySession(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Per-side mean ± std of trial-median correct lick rate (Hz).

    Mirrors legacy ``lickRate_bySession`` (behavior_report_PS.py:681-700).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        means = [d["mean"] for d in stats.medianLickRate[side]]
        stds = [d["std"] for d in stats.medianLickRate[side]]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means, yerr=stds,
            color=SIDE_COLORS[side], label=f"mouse {side}",
            marker="o", markersize=2,
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(0, config["lickrate_y_max"])
    ax.set_ylabel("lick rate (Hz)  [avg ± std of trial median lick rates]")
    ax.set_title("avg correct lick rate by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "lickRate_bySession", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_latency_bySession(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Per-side mean ± std of latency (seconds) to first correct lick.

    Mirrors legacy ``latency_bySession`` (behavior_report_PS.py:831-850).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        means = [d["mean"] for d in stats.latency[side]]
        stds = [d["std"] for d in stats.latency[side]]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means, yerr=stds,
            color=SIDE_COLORS[side], label=f"mouse {side}",
            marker="o", markersize=2,
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(0, config["latency_y_max"])
    ax.set_ylabel("avg latency (s)  [avg ± std]")
    ax.set_title("avg latency to correct lick by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "latency_bySession", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def _render_numLicks_bySession_kind(
    animal: str,
    resolver: PathResolver,
    kind: Literal["correct", "all"],
    *,
    align_to_stroke: bool,
    config: dict[str, Any],
    behavior_params: dict[str, Any],
    animal_info: AnimalInfo | None,
    overwrite: Literal["force", "skip", "raise"],
    stats: _PerSessionStats | None,
) -> tuple[Path, Path]:
    """Shared body for the correct + all variants of numLicks_bySession.

    Mirrors legacy lines 749-771 — the loop that emits both
    ``numLicks_bySession_correct`` and ``numLicks_bySession_all``
    from the same skeleton.
    """
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        means = [
            d["mean"] for d in stats.numLicks[kind][f"Reward_{side}"]
        ]
        stds = [
            d["std"] for d in stats.numLicks[kind][f"Reward_{side}"]
        ]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means,
            yerr=[[0] * len(stds), stds],  # upper-only error bar
            label=f"Reward {side}",
            marker="o", markersize=2,
            color=SIDE_COLORS[side],
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(0, config["numlicks_y_max"])
    ax.set_ylabel("Avg licks per trial  [avg + std]")
    title = (
        "Avg correct licks per trial by session" if kind == "correct"
        else "Avg all licks per trial by session"
    )
    ax.set_title(title)
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, f"numLicks_bySession_{kind}", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_numLicks_bySession_correct(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Per-side mean correct-licks per trial. Legacy lines 749-771 (correct)."""
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    return _render_numLicks_bySession_kind(
        animal, resolver, "correct",
        align_to_stroke=align_to_stroke, config=config,
        behavior_params=behavior_params, animal_info=animal_info,
        overwrite=overwrite, stats=stats,
    )


def render_numLicks_bySession_all(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """Per-side mean all-licks per trial. Legacy lines 749-771 (all)."""
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    return _render_numLicks_bySession_kind(
        animal, resolver, "all",
        align_to_stroke=align_to_stroke, config=config,
        behavior_params=behavior_params, animal_info=animal_info,
        overwrite=overwrite, stats=stats,
    )


def render_numLicks_bySession_correct_and_incorrect(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
    stats: _PerSessionStats | None = None,
) -> tuple[Path, Path]:
    """4-line plot: correct (solid) + incorrect (dashed) × L/R sides.

    Mirrors legacy ``numLicks_bySession_correct_and_incorrect``
    (behavior_report_PS.py:773-800).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    stats = stats or _compute_per_session_stats(animal, resolver, behavior_params)
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        stats.dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )
    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side_reward, linestyle, kind in [
        ("Reward_R", "-", "correct"),
        ("Reward_L", "-", "correct"),
        ("Reward_R", "--", "incorrect"),
        ("Reward_L", "--", "incorrect"),
    ]:
        side = side_reward.split("_")[1]
        means = [d["mean"] for d in stats.numLicks[kind][side_reward]]
        stds = [d["std"] for d in stats.numLicks[kind][side_reward]]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means,
            yerr=[[0] * len(stds), stds],
            linestyle=linestyle, marker="o", markersize=2,
            color=SIDE_COLORS[side],
            label=f"Reward {side} {kind}",
        )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylim(0, config["numlicks_y_max"])
    ax.set_ylabel("Avg licks per trial  [avg + std]")
    ax.set_title("Avg correct & incorrect licks per trial by session")
    ax.legend(loc="upper right", ncol=2)
    paths = save_visual_gate_figure(
        fig, animal, "numLicks_bySession_correct_and_incorrect",
        axis.suffix, resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


# =====================================================================
# Commit-group 3: lick raster (per-trial × per-session multi-panel grid)
# =====================================================================
#
# Standalone renderer — does NOT share the longitudinal-mean skeleton
# (CG-2's _PerSessionStats aggregation). The raster is a 2 × N_sessions
# grid where rows = reward side and columns = sessions; each cell shows
# per-trial post-reward licks as a scatter (correct vs incorrect color-
# coded) with a criteria_34 pass/fail horizontal line overlay per trial.
#
# Reuses CG-2 helpers:
#   - compute_trial_lick_delays — per-trial lick timing relative to reward
#   - compute_first_correct_lick_sample_idx → compute_criteria_3
#   - compute_criteria_4
#   - compute_criteria_34 — combined pass/fail for the line overlay
#
# Mirrors legacy ``plot_raster`` (behavior_report_PS.py:415-448) +
# emission (line 531-533). Faithful port: side-naming convention is the
# only deviation — legacy uses ``fn_flip_lr(side_reward)`` on the ylabel
# because legacy operates WS-frame internally; the new pipeline reads
# side_reward as mouse-frame directly.


def render_lick_raster(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Render the per-mouse lick raster: 2 × N_sessions panel grid.

    Rows = reward side (top: Reward L; bottom: Reward R).
    Columns = sessions in Cohort A bare-date order.

    Per-cell content (legacy lines 417-442):
      - For each trial × side_lick, scatter lick delays (seconds
        relative to reward) at y=trial_idx, dot size from
        ``visual_gate.raster_dot_size`` config. Color
        ``raster_dot_correct_color`` (green) when ``side_lick ==
        side_reward``; ``raster_dot_incorrect_color`` (magenta)
        otherwise.
      - Per trial, a horizontal line at y=trial_idx spanning
        ``raster_criteria_xrange``, colored
        ``raster_criteria_pass_color`` (green) when criteria_34
        passes for that trial, ``raster_criteria_fail_color`` (red)
        otherwise. Alpha from ``raster_criteria_alpha``.
      - Vertical reward-marker line at x=0, color
        ``raster_reward_marker_color``, alpha
        ``raster_reward_marker_alpha``.
      - X-axis limit ``raster_xlim``.
      - Top-row only: per-cell title (rotated 90°) = session label
        formatted via :func:`legend_label_for_date`.
      - Bottom-row only: xlabel "Time (s)" (rotated 90°).
      - Left-column only: ylabel "Trials   (side: mouse {side_reward})".

    Suptitle (legacy line 444-447):
      ``"Licks after rewards. Dots: (green=corr, magenta=incorr).
      Lines: (green=pass, red=fail)"``

    Raises
    ------
    ValueError
        If Cohort A is empty for ``animal`` (no sessions → cannot
        build the 2 × 0 panel grid).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    dates = iter_cohort_a_sessions(animal, resolver)
    if len(dates) == 0:
        raise ValueError(
            f"render_lick_raster: no Cohort A sessions for {animal} — "
            "cannot build the 2 × N_sessions panel grid"
        )
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    # Reuse CG-1's longitudinal-axis helper purely for the suffix +
    # legend-label formatting. The raster doesn't plot on a longitudinal
    # x-axis but the per-cell column title shares the same date-label
    # rendering with the longitudinal-mean renderers.
    axis = compute_longitudinal_axis(
        dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )

    window_around = behavior_params["window_around_rewards"]
    crit3_window = behavior_params["criteria_3"]["window"]
    crit_xrange = config["raster_criteria_xrange"]

    # Compute per-session lick delays + criteria_34 in one pass.
    per_date_delays: dict[str, dict[str, dict[int, dict[str, np.ndarray]]]] = {}
    per_date_crit34: dict[str, dict[str, dict[int, bool]]] = {}
    for date in dates:
        data = load_session_plot_data(animal, date, resolver)
        per_date_delays[date] = compute_trial_lick_delays(
            data, window_around,
        )
        fcl_idx = compute_first_correct_lick_sample_idx(data, crit3_window)
        c3 = compute_criteria_3(fcl_idx)
        c4 = compute_criteria_4(data, behavior_params["criteria_4"])
        per_date_crit34[date] = compute_criteria_34(c3, c4)

    fig, axs = plt.subplots(
        nrows=2, ncols=len(dates),
        figsize=tuple(config["figsize_raster_grid"]),
        squeeze=False,
    )
    for ii, side_reward in enumerate(("L", "R")):
        for jj, date in enumerate(dates):
            ax = axs[ii, jj]
            delays_by_reward = per_date_delays[date][f"Reward_{side_reward}"]
            crit34_by_reward = per_date_crit34[date][side_reward]
            # Load sample_rate from the same SessionPlotData? We need it
            # for the lick-delay → seconds conversion. Reload here to
            # avoid keeping all SessionPlotData live; lookup is cheap.
            data = load_session_plot_data(animal, date, resolver)
            for idx_reward, by_side in delays_by_reward.items():
                for side_lick in ("L", "R"):
                    lick_delays = by_side[f"Lick_{side_lick}"]
                    if lick_delays.size == 0:
                        continue
                    is_correct = (side_lick == side_reward)
                    color = (
                        config["raster_dot_correct_color"] if is_correct
                        else config["raster_dot_incorrect_color"]
                    )
                    ax.scatter(
                        lick_delays / data.sample_rate,
                        np.full_like(lick_delays, idx_reward, dtype=float),
                        s=config["raster_dot_size"],
                        color=color,
                    )
            # Criteria_34 pass/fail overlay (per trial).
            for idx_reward, passed in crit34_by_reward.items():
                line_color = (
                    config["raster_criteria_pass_color"] if passed
                    else config["raster_criteria_fail_color"]
                )
                ax.plot(
                    crit_xrange, [idx_reward, idx_reward],
                    line_color, alpha=config["raster_criteria_alpha"],
                )
            # Reward marker (vertical line at x=0).
            n_trials = len(delays_by_reward)
            ax.plot(
                [0, 0], [0, n_trials],
                config["raster_reward_marker_color"],
                alpha=config["raster_reward_marker_alpha"],
            )
            ax.set_xlim(*config["raster_xlim"])
            # Top-row title (column header).
            if ii == 0:
                title = legend_label_for_date(
                    date, align_to_stroke=align_to_stroke, d0=d0,
                )
                ax.set_title(title, rotation=90, fontsize="x-small")
                ax.set_xticklabels([])
            # Bottom-row xlabel.
            if ii == 1:
                ax.set_xlabel("Time (s)", rotation=90)
                ax.tick_params(axis="x", labelsize=config["xtick_fontsize"])
            # Left-column ylabel. New-pipeline side convention: read
            # mouse-frame directly (no fn_flip_lr).
            if jj == 0:
                ax.set_ylabel(f"Trials   (side: mouse {side_reward})")
            else:
                ax.set_yticklabels([])

    fig.suptitle(
        "Licks after rewards. Dots: (green=corr, magenta=incorr). "
        "Lines: (green=pass, red=fail)",
        y=-0.075,
    )
    paths = save_visual_gate_figure(
        fig, animal, "lick_raster", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


# =====================================================================
# Commit-group 4: lickiness + switchiness
# =====================================================================
#
# Two engagement-quality plot families ported from canonical
# behavior_report_PS.py (lines 852-935). Both follow CG-2's
# longitudinal-mean style; one new compute helper per family.
#
# Lickiness: per-session count of "late licks" — licks within the
# inter-reward window after the standard post-reward window expires
# but before the next reward (or 60s, whichever is shorter). High
# lickiness = the mouse is licking even when not cued by a recent
# reward.
#
# Switchiness: per-trial mean count of L↔R lick transitions within
# the standard post-reward window. High switchiness = the mouse is
# rapidly switching sides during a single trial.


def compute_lickiness_bySession(
    session_data: SessionPlotData,
    *,
    late_window_start_seconds: float,
    late_window_end_seconds: float,
) -> dict[str, int]:
    """Per-side count of "late licks" within the inter-reward window.

    Mirrors legacy ``lickiness`` (behavior_report_PS.py:855-883). For
    each consecutive reward pair (rew, next_rew):
      - Late-lick window opens at ``rew + late_window_start_seconds``.
      - Window closes at ``min(next_rew, rew + late_window_end_seconds)``.
      - Licks STRICTLY between window start and end (exclusive on
        both ends, per legacy ``>`` and ``<``).
    For the LAST reward: closes at ``min(rew + end, n_samples_session)``
    when ``n_samples_session > 0``; falls back to ``rew + end``
    otherwise (no session-length cap available).

    Returns ``{"L": <count>, "R": <count>}``.
    """
    sr = session_data.sample_rate
    upper = int(late_window_start_seconds * sr)
    mx = int(late_window_end_seconds * sr)
    n_samps = session_data.n_samples_session

    out: dict[str, int] = {"L": 0, "R": 0}
    all_rews = np.sort(np.concatenate([
        session_data.rewards_idx["Reward_L"],
        session_data.rewards_idx["Reward_R"],
    ]))
    if all_rews.size == 0:
        return out

    # Inter-reward windows.
    for rew, next_rew in zip(all_rews[:-1], all_rews[1:]):
        start = int(rew) + upper
        end = min(int(next_rew), int(rew) + mx)
        if end <= start:
            continue
        for side in ("L", "R"):
            ls = session_data.lick_idx[f"Lick_{side}"]
            out[side] += int(np.sum((ls > start) & (ls < end)))

    # Post-last-reward window. Capped at n_samples_session when known;
    # uncapped otherwise (fallback when WS NPZ had no 1D signal).
    last = int(all_rews[-1])
    start = last + upper
    end = last + mx
    if n_samps > 0:
        end = min(end, n_samps)
    if end > start:
        for side in ("L", "R"):
            ls = session_data.lick_idx[f"Lick_{side}"]
            out[side] += int(np.sum((ls > start) & (ls < end)))
    return out


def compute_switchiness_bySession(
    trial_lick_delays: dict[str, dict[int, dict[str, np.ndarray]]],
) -> dict[str, float]:
    """Average per-trial L→R + R→L lick-side transition counts.

    Mirrors legacy ``switchiness`` compute (behavior_report_PS.py:895-920).
    For each trial (across both reward sides), interleave the per-side
    lick events (timestamp + side), sort chronologically, count
    consecutive-event transitions where ``prev != current``. ``L→R``
    counts L-then-R transitions; ``R→L`` counts R-then-L. Returned
    values are the cohort-wide mean across all trials in the session.

    Input is mouse-frame post-Phase-6.8 (``trial_lick_delays`` from
    :func:`compute_trial_lick_delays` with mouse-frame side keys), so
    no WS-frame flip is applied to the output.
    """
    lr_counts: list[int] = []
    rl_counts: list[int] = []
    for side_reward in ("L", "R"):
        trials = trial_lick_delays[f"Reward_{side_reward}"]
        for trial_lick_dict in trials.values():
            events = (
                [(int(t), "L") for t in trial_lick_dict["Lick_L"]]
                + [(int(t), "R") for t in trial_lick_dict["Lick_R"]]
            )
            events.sort(key=lambda x: x[0])
            c_LR = c_RL = 0
            if len(events) > 1:
                prev = events[0][1]
                for _, side in events[1:]:
                    if prev == "L" and side == "R":
                        c_LR += 1
                    elif prev == "R" and side == "L":
                        c_RL += 1
                    prev = side
            lr_counts.append(c_LR)
            rl_counts.append(c_RL)
    return {
        "L->R": float(np.mean(lr_counts)) if lr_counts else float("nan"),
        "R->L": float(np.mean(rl_counts)) if rl_counts else float("nan"),
    }


# ---- Renderers ----


def render_lickiness_bySession(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Per-mouse late-lick count per side, longitudinal.

    Mirrors legacy ``lickiness_bySession`` (behavior_report_PS.py:885-893).
    Y-axis intentionally NOT bounded (legacy auto-scales — high
    lickiness = behavioral disengagement; the absolute range varies
    by animal). Late-window start = ``behavior_report.window_around_rewards[1]``
    (post-reward window end); end = ``visual_gate.lickiness_window_seconds``
    (60s cap by default).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    dates = iter_cohort_a_sessions(animal, resolver)
    if len(dates) == 0:
        raise ValueError(
            f"render_lickiness_bySession: no Cohort A sessions for {animal}"
        )
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )

    late_start = float(behavior_params["window_around_rewards"][1])
    late_end = float(config["lickiness_window_seconds"])

    per_side: dict[str, list[int]] = {"L": [], "R": []}
    for date in dates:
        data = load_session_plot_data(animal, date, resolver)
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=late_start,
            late_window_end_seconds=late_end,
        )
        for side in ("L", "R"):
            per_side[side].append(counts[side])

    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    for side in ("L", "R"):
        ax.plot(
            axis.x_vals, per_side[side], "-o",
            color=SIDE_COLORS[side], markersize=4,
            label=f"mouse {side}",
        )
    apply_longitudinal_axis(ax, axis, config)
    # Legacy ylabel uses literal "≤60 s" — preserve the exact string
    # since visual_gate.lickiness_window_seconds is 60 by default. If a
    # downstream caller overrides the config to a different value, the
    # ylabel string lies — acceptable for chase-fidelity-with-legacy.
    ax.set_ylabel("Late licks per session\n(> window_after_reward & ≤60 s)")
    ax.set_title("Lickiness by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "lickiness_bySession", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_switchiness_bySession(
    animal: str,
    resolver: PathResolver,
    *,
    align_to_stroke: bool = True,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Per-mouse mean L↔R transition count per trial, longitudinal.

    Mirrors legacy ``switchiness_bySession`` (behavior_report_PS.py:914-935).

    **Color-to-label mapping**: legacy assigns ``side_colors["L"]``
    (WS-L = mouse-R color = mediumvioletred) to the ``"L→R"`` label
    line, and ``side_colors["R"]`` (WS-R = mouse-L = dodgerblue) to
    the ``"R→L"`` label line. This produces a visual where the
    transition label color matches the DESTINATION side in mouse-
    frame. Faithful-port preserves the visual: new pipeline assigns
    ``SIDE_COLORS["R"]`` to ``"L→R"`` (mouse-R color for L→R) and
    ``SIDE_COLORS["L"]`` to ``"R→L"`` (mouse-L color for R→L). This
    is the ONE CG-4 deviation beyond CG-1's locked SIDE_COLORS
    inversion — documented for the DECISIONS entry.
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    dates = iter_cohort_a_sessions(animal, resolver)
    if len(dates) == 0:
        raise ValueError(
            f"render_switchiness_bySession: no Cohort A sessions for {animal}"
        )
    d0 = _resolve_d0(animal_info, animal, align_to_stroke)
    axis = compute_longitudinal_axis(
        dates, align_to_stroke=align_to_stroke, d0=d0,
        vline_x=config["stroke_vline_x"],
    )

    window_around = behavior_params["window_around_rewards"]
    per_direction: dict[str, list[float]] = {"L->R": [], "R->L": []}
    for date in dates:
        data = load_session_plot_data(animal, date, resolver)
        delays = compute_trial_lick_delays(data, window_around)
        sw = compute_switchiness_bySession(delays)
        per_direction["L->R"].append(sw["L->R"])
        per_direction["R->L"].append(sw["R->L"])

    fig, ax = plt.subplots(figsize=tuple(config["figsize_longitudinal"]))
    # Color-by-destination per the docstring deviation note.
    ax.plot(
        axis.x_vals, per_direction["L->R"], "-o",
        color=SIDE_COLORS["R"], markersize=4, label="L→R",
    )
    ax.plot(
        axis.x_vals, per_direction["R->L"], "-o",
        color=SIDE_COLORS["L"], markersize=4, label="R→L",
    )
    apply_longitudinal_axis(ax, axis, config)
    ax.set_ylabel("Avg switches per trial")
    ax.set_title("Switchiness by session")
    ax.legend()
    paths = save_visual_gate_figure(
        fig, animal, "switchiness_bySession", axis.suffix, resolver,
        overwrite=overwrite,
    )
    plt.close(fig)
    return paths
