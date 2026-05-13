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

import numpy as np

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
    """

    date_label: str
    lick_idx: dict[str, np.ndarray]
    rewards_idx: dict[str, np.ndarray]
    sample_rate: float


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
    with np.load(ws_path, allow_pickle=True) as ws:
        sample_rate = float(ws["sample_rate_input"])
    return SessionPlotData(
        date_label=date_label,
        lick_idx=lick_idx,
        rewards_idx=rewards_idx,
        sample_rate=sample_rate,
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
