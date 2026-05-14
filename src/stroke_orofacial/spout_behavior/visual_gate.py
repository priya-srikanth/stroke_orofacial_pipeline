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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults, load_session_overrides
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
    require_on_disk: bool = True,
    overrides_config: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> list[str]:
    """Return the animal's sorted Cohort A session labels.

    Cohort definition (Task 3 Round 2 continuation, 2026-05-13):
    Walk every calendar date from ``AnimalInfo.session_start`` through
    ``AnimalInfo.session_end`` inclusive. Drop dates with a matching
    ``AnimalInfo.exclusions`` entry tagged for ``spout_behavior``.
    The on-disk filter (``require_on_disk=True``) then trims to
    sessions whose Phase-2 ``licks_and_rewards`` NPZ actually exists,
    silently dropping dates that fall in the configured range but
    have no real session (e.g. weekends, equipment-down days).

    This replaces the prior legacy-``report.json``-based cohort
    definition. The YAML range is the single source of truth; the
    on-disk filter handles the "no Phase-2 output yet" case.

    Pattern A multi-half augmentation (PS48/2025-03-14) is preserved:
    if ``multi_half_sessions:`` registers the session AND the merged
    NPZ exists at the bare-date path, the entry is kept. (Multi-half
    sessions are NOT excluded by the AnimalInfo exclusion filter —
    they're real session dates by construction.)

    Parameters
    ----------
    animal : str
        e.g. ``"PS51"``.
    resolver : PathResolver
        For ``pipeline_outputs("spout_behavior")`` on-disk filter.
    include_b_half : bool, default ``False``
        Longitudinal plots default — drops ``[a-z]``-suffixed entries.
        Set ``True`` for bare-vs-b scope.
    require_on_disk : bool, default ``True``
        Filter to sessions with a ``licks_and_rewards`` NPZ on disk.
        Set ``False`` for tests / inspection that want the raw YAML
        range.
    overrides_config : dict, optional
        Pre-loaded ``session_overrides.yaml``. Used for
        ``multi_half_sessions:`` (Pattern A bare-date augmentation).
    animal_info : AnimalInfo, optional
        Pre-loaded :class:`stroke_orofacial.animals.AnimalInfo`.
        ``None`` calls :func:`stroke_orofacial.animals.get_animal`.
    """
    if animal_info is None:
        animal_info = get_animal(animal)

    # Walk session_start → session_end inclusive.
    raw_keys: list[str] = []
    current = animal_info.session_start
    end = animal_info.session_end
    one_day = datetime.timedelta(days=1)
    while current <= end:
        excluded, _ = animal_info.is_excluded(current, "spout_behavior")
        if not excluded:
            raw_keys.append(current.strftime("%Y%m%d"))
        current += one_day

    # b-suffix filter is a no-op when generating from a date range
    # (no per-half entries are produced) — but keep the kwarg for API
    # parity and Pattern A augmentation logic below.
    if not include_b_half:
        if overrides_config is None:
            overrides_config = load_session_overrides()
        multi_half = overrides_config.get("multi_half_sessions", {}) or {}
        # Multi-half augmentation: ensure each registered (animal, date)
        # has its bare-date entry present. Date-range walk already
        # includes bare dates within the range, so this is a no-op for
        # the in-range case. Outside-range registered entries get added
        # too (defensive — should never happen in practice).
        for date_yyyymmdd in multi_half.get(animal, {}):
            if date_yyyymmdd not in raw_keys:
                raw_keys.append(date_yyyymmdd)

    if require_on_disk:
        sp_root = resolver.pipeline_outputs("spout_behavior")
        raw_keys = [
            k for k in raw_keys
            if (sp_root / "licks_and_rewards" / animal / f"{k}.npz").exists()
        ]
    return sorted(raw_keys)


def _resolve_session_npz_path(
    output_type: str,
    animal: str,
    date_str: str,
    half_suffix: str,
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
) -> Path:
    """Resolve the on-disk NPZ path for a session × output_type.

    Routes between flat single-half/Pattern B layout and Pattern A
    nested per-half layout based on the ``multi_half_sessions:``
    registry.

    Parameters
    ----------
    output_type : str
        Phase-2 output subdirectory: ``"licks_and_rewards"``,
        ``"wavesurfer_signals_processed"``, ``"running_bouts"``, etc.
    animal : str
        e.g. ``"PS48"``.
    date_str : str
        Bare ``YYYYMMDD`` label (no suffix).
    half_suffix : str
        ``""`` for bare/merged; ``"a"`` or ``"b"`` for per-half
        Pattern A access.
    resolver : PathResolver
        For ``pipeline_outputs("spout_behavior")`` root.
    overrides_config : dict, optional
        Pre-loaded ``session_overrides.yaml`` block for the Pattern A
        registry lookup. ``None`` loads via
        :func:`stroke_orofacial.config_loader.load_session_overrides`.

    Returns
    -------
    Path
        Resolved NPZ path. **Caller verifies existence.**

    Path conventions
    ----------------
    - Bare/single-half (``half_suffix=""``):
      ``{licks_root}/<animal>/<date_str>.npz``.
      Pattern A merged file lives here too (Phase 7-pre-multi-half
      emission); no registry lookup needed.
    - Pattern A per-half (``half_suffix`` in ``"a"``/``"b"`` AND
      ``(animal, date_str)`` in ``multi_half_sessions:``):
      ``{licks_root}/<animal>/<date_str><concat_label>/
      <date_str><half_suffix>.npz``.
      ``<concat_label>`` is the joined half ids (e.g. ``"ab"`` for
      PS48/20250314).
    - Pattern B b-half / non-registered suffix (``half_suffix`` in
      ``"a"``/``"b"`` AND ``(animal, date_str)`` NOT in
      ``multi_half_sessions:``):
      ``{licks_root}/<animal>/<date_str><half_suffix>.npz`` (flat).
    """
    sp_root = resolver.pipeline_outputs("spout_behavior")
    type_root = sp_root / output_type / animal
    if half_suffix == "":
        return type_root / f"{date_str}.npz"
    # Determine routing: Pattern A nested vs Pattern B flat.
    if overrides_config is None:
        overrides_config = load_session_overrides()
    multi_half = overrides_config.get("multi_half_sessions", {}) or {}
    animal_entry = multi_half.get(animal, {})
    if date_str in animal_entry:
        # Pattern A: nested under <date_str><halves_concat_label>/.
        spec = animal_entry[date_str] or {}
        halves = spec.get("halves", [])
        half_ids = [h["id"] for h in halves] if halves else ["a", "b"]
        concat_label = "".join(half_ids)
        return (
            type_root / f"{date_str}{concat_label}"
            / f"{date_str}{half_suffix}.npz"
        )
    # Pattern B b-half or non-registered: flat path.
    return type_root / f"{date_str}{half_suffix}.npz"


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

    Reads ``longitudinal_xtick_fontsize``, ``stroke_linewidth``,
    ``stroke_vline_color``, ``stroke_vline_linestyle``,
    ``stroke_vline_alpha`` from ``visual_gate_config`` (the
    ``visual_gate:`` block of ``configs/defaults.yaml``).

    Note: ``longitudinal_xtick_fontsize`` is distinct from the
    raster-only ``xtick_fontsize`` knob. The longitudinal-family
    knob is sized for dense cohorts where adjacent day labels
    (e.g. d+31 / d+32) would otherwise overlap.
    """
    ax.set_xticks(longitudinal_axis.x_vals)
    ax.set_xticklabels(
        longitudinal_axis.x_ticklabels,
        rotation=90,
        fontsize=visual_gate_config["longitudinal_xtick_fontsize"],
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

    Phase 8a.10.1 Q-A.β rename (2026-05-14): the trial-anchor field
    ``rewards_idx`` renamed to ``tones_idx``. Under Case-2 universal,
    every legacy consumer of the old ``rewards_idx`` was scientifically
    intended as tone-onset alignment; the pre-fix name reflected the
    swapped WS channel label, not the actual content. Post-Commit-A
    swap-fix, the on-disk NPZ's ``Tone_L``/``Tone_R`` keys hold the
    actual tone-onset sample indices — exactly what every "post-reward"
    window math in this module has always meant.

    Attributes
    ----------
    date_label : str
        Bare ``YYYYMMDD`` label (no suffix; longitudinal-only scope).
    lick_idx : dict[str, np.ndarray]
        Mouse-frame lick sample indices: ``{"Lick_L": ..., "Lick_R": ...}``.
        Post-Phase-6.8 the labels are mouse-frame directly (no further
        translation needed).
    tones_idx : dict[str, np.ndarray]
        Mouse-frame tone-onset sample indices: ``{"Tone_L": ...,
        "Tone_R": ...}``. Q-A.β rename from ``rewards_idx`` — content
        unchanged (it was tone-onset all along under Case-2 universal);
        dict keys updated to match the on-disk NPZ schema post-Commit-A.
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
        and silently skip the post-last-tone window. Mirrors legacy
        ``n_samps = data_ws[date][next(iter(data_ws[date]))].shape[0]``
        (behavior_report_PS.py:862).
    """

    date_label: str
    lick_idx: dict[str, np.ndarray]
    tones_idx: dict[str, np.ndarray]
    sample_rate: float
    n_samples_session: int = 0


def load_session_plot_data(
    animal: str,
    date_label: str,
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
    *,
    half_suffix: str = "",
) -> SessionPlotData:
    """Load Phase-2 + Phase-1 inputs for one session.

    Reads:
      - ``pipeline_outputs/spout_behavior/licks_and_rewards/<animal>/
        <date_label>{half_suffix}.npz`` for ``Lick_{L,R}`` +
        ``Tone_{L,R}`` (Q-A.β post-2026-05-14: tone-onset is the
        always-present trial anchor; pre-Commit-A this read ``Reward_{L,R}``
        keys, which held tone-onset content under the WS channel-label
        swap. Post-Commit-A the on-disk ``Tone_{L,R}`` keys hold the
        same content semantically-correctly).
      - Wavesurfer NPZ for ``sample_rate_input`` + total session
        sample count (1D signal length).

    Pattern A multi-half handling (Task 3 Round 2 fix; applies when
    ``half_suffix=""``): for registered ``multi_half_sessions:``
    entries (e.g. PS48/2025-03-14) the licks NPZ is merged at the
    bare-date path, but the wavesurfer NPZ stays per-half under
    ``<date_label><concat_label>/<date_label><half_id>.npz``. The
    loader reads from per-half "a" for sample_rate and SUMS the
    per-half session lengths (a + b) for ``n_samples_session`` so
    downstream lickiness windows use the full virtual-session length
    the merged licks indices reference.

    For Pattern B / single-half sessions (the common case): both
    NPZs live at the flat bare-date path.

    Per-half access (``half_suffix="a"`` or ``"b"``, added Phase
    8a.10 sub-deliverable B): bypasses the multi-half merge logic
    and reads BOTH licks and WS from the per-half path. For Pattern
    A this resolves to the nested ``<date_label><concat_label>/
    <date_label><half_suffix>.npz`` location; for Pattern B b-half
    it's the flat ``<date_label>b.npz`` path.
    ``n_samples_session`` is the per-half length (NOT summed).

    Raises
    ------
    FileNotFoundError
        If either NPZ is missing on disk.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    multi_half = overrides_config.get("multi_half_sessions", {}) or {}
    is_pattern_a = (
        animal in multi_half and date_label in (multi_half.get(animal) or {})
    )

    # Per-half access bypasses Pattern A merge logic: both licks and
    # WS load from the per-half path, n_samples is per-half (not
    # summed). Pattern B b-half + Pattern A per-half both flow here.
    if half_suffix:
        licks_path = _resolve_session_npz_path(
            "licks_and_rewards", animal, date_label, half_suffix,
            resolver=resolver, overrides_config=overrides_config,
        )
        if not licks_path.exists():
            raise FileNotFoundError(
                f"licks_and_rewards NPZ missing: {licks_path}"
            )
        with np.load(licks_path, allow_pickle=True) as licks:
            lick_idx = {key: licks[key] for key in ("Lick_L", "Lick_R")}
            tones_idx = {
                key: licks[key] for key in ("Tone_L", "Tone_R")
            }
        ws_path = _resolve_session_npz_path(
            "wavesurfer_signals_processed", animal, date_label,
            half_suffix, resolver=resolver,
            overrides_config=overrides_config,
        )
        if not ws_path.exists():
            raise FileNotFoundError(
                f"wavesurfer_signals_processed NPZ missing: {ws_path}"
            )
        n_samples_session = 0
        with np.load(ws_path, allow_pickle=True) as ws:
            sample_rate = float(ws["sample_rate_input"])
            for key in ws.files:
                arr = ws[key]
                if arr.ndim == 1:
                    n_samples_session = int(arr.shape[0])
                    break
        return SessionPlotData(
            date_label=date_label,
            lick_idx=lick_idx,
            tones_idx=tones_idx,
            sample_rate=sample_rate,
            n_samples_session=n_samples_session,
        )

    licks_path = _resolve_session_npz_path(
        "licks_and_rewards", animal, date_label, "",
        resolver=resolver, overrides_config=overrides_config,
    )
    if not licks_path.exists():
        raise FileNotFoundError(f"licks_and_rewards NPZ missing: {licks_path}")
    with np.load(licks_path, allow_pickle=True) as licks:
        lick_idx = {key: licks[key] for key in ("Lick_L", "Lick_R")}
        tones_idx = {key: licks[key] for key in ("Tone_L", "Tone_R")}

    if is_pattern_a:
        spec = multi_half[animal][date_label] or {}
        halves = spec.get("halves") or [{"id": "a"}, {"id": "b"}]
        sample_rate = 0.0
        n_samples_session = 0
        for half in halves:
            half_id = half["id"]
            ws_path = _resolve_session_npz_path(
                "wavesurfer_signals_processed", animal, date_label, half_id,
                resolver=resolver, overrides_config=overrides_config,
            )
            if not ws_path.exists():
                raise FileNotFoundError(
                    f"Pattern A per-half WS NPZ missing: {ws_path}"
                )
            with np.load(ws_path, allow_pickle=True) as ws:
                if sample_rate == 0.0:
                    sample_rate = float(ws["sample_rate_input"])
                for key in ws.files:
                    arr = ws[key]
                    if arr.ndim == 1:
                        n_samples_session += int(arr.shape[0])
                        break
    else:
        ws_path = _resolve_session_npz_path(
            "wavesurfer_signals_processed", animal, date_label, "",
            resolver=resolver, overrides_config=overrides_config,
        )
        if not ws_path.exists():
            raise FileNotFoundError(
                f"wavesurfer_signals_processed NPZ missing: {ws_path}"
            )
        n_samples_session = 0
        with np.load(ws_path, allow_pickle=True) as ws:
            sample_rate = float(ws["sample_rate_input"])
            # First 1D signal's length = total session sample count.
            for key in ws.files:
                arr = ws[key]
                if arr.ndim == 1:
                    n_samples_session = int(arr.shape[0])
                    break

    return SessionPlotData(
        date_label=date_label,
        lick_idx=lick_idx,
        tones_idx=tones_idx,
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
    ``{resolver.spout_behavior_figures_dir(animal)}/{plot_family}{suffix}.{svg,png}``.
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
    out_dir = resolver.spout_behavior_figures_dir(animal)
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
    ``{"Tone_L": {reward_idx: {"Lick_L": delays, "Lick_R": delays}}, "Tone_R": {...}}``
    where ``delays`` is an array of lick sample indices relative to the
    reward sample (i.e. ``lick_sample - tone_sample``). Negative
    values = lick before reward.
    """
    window_samples = _window_to_samples(window_seconds, session_data.sample_rate)
    out: dict[str, dict[int, dict[str, np.ndarray]]] = {}
    for side_tone in ("L", "R"):
        tones = session_data.tones_idx[f"Tone_{side_tone}"]
        per_trial: dict[int, dict[str, np.ndarray]] = {}
        for idx_tone, tone_sample in enumerate(tones):
            per_side_licks: dict[str, np.ndarray] = {}
            for side_lick in ("L", "R"):
                licks = session_data.lick_idx[f"Lick_{side_lick}"]
                positions = _find_idx_within_window(
                    licks, int(tone_sample), window_samples,
                )
                per_side_licks[f"Lick_{side_lick}"] = (
                    licks[positions] - int(tone_sample)
                )
            per_trial[idx_tone] = per_side_licks
        out[f"Tone_{side_tone}"] = per_trial
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
        tones = session_data.tones_idx[f"Tone_{side}"]
        correct_licks = session_data.lick_idx[f"Lick_{side}"]
        per_trial: dict[int, int | None] = {}
        for idx_tone, tone_sample in enumerate(tones):
            positions = _find_idx_within_window(
                correct_licks, int(tone_sample), window_samples,
            )
            if positions.size == 0:
                per_trial[idx_tone] = None
            else:
                per_trial[idx_tone] = int(correct_licks[positions[0]])
        out[side] = per_trial
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
            for idx, fcl in per_trial.items()
        }
        for side, per_trial in first_correct_lick_idx.items()
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
    for side_tone in ("L", "R"):
        tones = session_data.tones_idx[f"Tone_{side_tone}"]
        per_trial: dict[int, bool] = {}
        for idx_tone, tone_sample in enumerate(tones):
            n_correct = _find_idx_within_window(
                session_data.lick_idx[f"Lick_{side_tone}"],
                int(tone_sample),
                window_samples,
            ).size
            other_side = "R" if side_tone == "L" else "L"
            n_incorrect = _find_idx_within_window(
                session_data.lick_idx[f"Lick_{other_side}"],
                int(tone_sample),
                window_samples,
            ).size
            per_trial[idx_tone] = bool(
                (n_correct >= n_corr_min) and (n_incorrect <= n_incorr_max)
            )
        out[side_tone] = per_trial
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
    for side_tone in ("L", "R"):
        per_trial: dict[int, bool | None] = {}
        for idx_tone, by_side in trial_lick_delays[f"Tone_{side_tone}"].items():
            other_side = "R" if side_tone == "L" else "L"
            correct_delays = by_side[f"Lick_{side_tone}"]
            incorrect_delays = by_side[f"Lick_{other_side}"]
            correct_post = correct_delays[correct_delays >= 0]
            incorrect_post = incorrect_delays[incorrect_delays >= 0]
            if len(correct_post) > 0:
                if len(incorrect_post) > 0:
                    per_trial[idx_tone] = bool(correct_post[0] < incorrect_post[0])
                else:
                    per_trial[idx_tone] = True
            else:
                if len(incorrect_post) > 0:
                    per_trial[idx_tone] = False
                else:
                    per_trial[idx_tone] = None
        out[side_tone] = per_trial
    return out


def compute_criteria_acc_bySession(
    criteria_34: dict[str, dict[int, bool]],
) -> dict[str, float]:
    """Fraction of trials passing criteria 3 AND 4, per side."""
    out: dict[str, float] = {}
    for side, per_trial in criteria_34.items():
        if len(per_trial) == 0:
            out[side] = float("nan")
        else:
            out[side] = float(np.mean(list(per_trial.values())))
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
    for side, per_trial in first_lick_correct.items():
        if treat_none_as_zero:
            arr = np.array(
                [0.0 if v is None else float(v) for v in per_trial.values()],
                dtype=float,
            )
            out[side] = float(arr.mean()) if arr.size > 0 else float("nan")
        else:
            arr = np.array(
                [np.nan if v is None else float(v) for v in per_trial.values()],
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
    for side_tone in ("L", "R"):
        rates: list[float] = []
        for by_side in trial_lick_delays[f"Tone_{side_tone}"].values():
            correct_delays = by_side[f"Lick_{side_tone}"]
            ilis = np.diff(correct_delays)
            if ilis.size == 0:
                rates.append(0.0)
            else:
                med = float(np.median(ilis))
                hz = 0.0 if med <= 0 else float(1.0 / (med / sample_rate))
                rates.append(0.0 if not np.isfinite(hz) else hz)
        if len(rates) == 0:
            per_side[side_tone] = {"mean": float("nan"), "std": float("nan")}
        else:
            per_side[side_tone] = {
                "mean": float(np.nanmean(rates)),
                "std": float(np.nanstd(rates)),
            }
    return per_side


def compute_num_licks_bySession(
    trial_lick_delays: dict[str, dict[int, dict[str, np.ndarray]]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Per-side mean ± std of per-trial lick counts.

    Returns a 3-level dict:
    ``{"correct": {"Tone_L": {"mean": x, "std": y}, "Tone_R": ...},
       "all":     {"Tone_L": ..., "Tone_R": ...},
       "incorrect": {"Tone_L": ..., "Tone_R": ...}}``

    Mirrors legacy ``sig_meanStd_numCorrectLicksPerTrial`` /
    ``sig_meanStd_numAllLicksPerTrial`` /
    ``sig_meanStd_numIncorrectLicksPerTrial`` (lines 705-747).
    """
    out: dict[str, dict[str, dict[str, float]]] = {
        "correct": {}, "all": {}, "incorrect": {},
    }
    for side_tone in ("L", "R"):
        other = "R" if side_tone == "L" else "L"
        n_correct: list[int] = []
        n_all: list[int] = []
        n_incorrect: list[int] = []
        for by_side in trial_lick_delays[f"Tone_{side_tone}"].values():
            n_correct.append(int(by_side[f"Lick_{side_tone}"].size))
            n_all.append(int(by_side["Lick_L"].size + by_side["Lick_R"].size))
            n_incorrect.append(int(by_side[f"Lick_{other}"].size))
        for kind, values in (
            ("correct", n_correct), ("all", n_all), ("incorrect", n_incorrect),
        ):
            if len(values) == 0:
                out[kind][f"Tone_{side_tone}"] = {
                    "mean": float("nan"), "std": float("nan"),
                }
            else:
                out[kind][f"Tone_{side_tone}"] = {
                    "mean": float(np.nanmean(values)),
                    "std": float(np.nanstd(values)),
                }
    return out


def compute_latency_bySession(
    first_correct_lick_idx: dict[str, dict[int, int | None]],
    tones_idx: dict[str, np.ndarray],
    sample_rate: float,
) -> dict[str, dict[str, float]]:
    """Per-side mean ± std of latency (seconds) to first correct lick.

    Q-A.β rename (2026-05-14): parameter ``rewards_idx → tones_idx``;
    latency is measured from tone-onset to first correct-side lick.
    Pre-fix the parameter was named for the swapped channel label, but
    the underlying anchor was tone-onset all along under Case-2
    universal. Mirrors legacy ``latency_meanStd_bySide`` (lines 805-829).
    ``None`` first-correct-lick entries become ``NaN`` and excluded
    from the mean/std.
    """
    out: dict[str, dict[str, float]] = {}
    for side in ("L", "R"):
        tones = tones_idx[f"Tone_{side}"]
        latencies: list[float] = []
        for idx_tone, fcl in first_correct_lick_idx[side].items():
            if fcl is None:
                latencies.append(float("nan"))
            else:
                latencies.append(
                    (fcl - int(tones[idx_tone])) / sample_rate
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
        "correct": {"Tone_L": [], "Tone_R": []},
        "all": {"Tone_L": [], "Tone_R": []},
        "incorrect": {"Tone_L": [], "Tone_R": []},
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
            fcl_idx, data.tones_idx, data.sample_rate,
        )

        for side in ("L", "R"):
            criteria_acc[side].append(acc[side])
            flc_excl[side].append(flc_exclude[side])
            flc_zero[side].append(flc_treat_zero[side])
            median_rate[side].append(ms_rate[side])
            latency[side].append(ms_lat[side])
        for kind in ("correct", "all", "incorrect"):
            for side_tone in ("Tone_L", "Tone_R"):
                num_licks[kind][side_tone].append(ms_num[kind][side_tone])

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
            d["mean"] for d in stats.numLicks[kind][f"Tone_{side}"]
        ]
        stds = [
            d["std"] for d in stats.numLicks[kind][f"Tone_{side}"]
        ]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means,
            yerr=[[0] * len(stds), stds],  # upper-only error bar
            label=f"Tone {side}",
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
    for side_tone, linestyle, kind in [
        ("Tone_R", "-", "correct"),
        ("Tone_L", "-", "correct"),
        ("Tone_R", "--", "incorrect"),
        ("Tone_L", "--", "incorrect"),
    ]:
        side = side_tone.split("_")[1]
        means = [d["mean"] for d in stats.numLicks[kind][side_tone]]
        stds = [d["std"] for d in stats.numLicks[kind][side_tone]]
        offset = 0.1 if side == "R" else -0.1
        ax.errorbar(
            x=axis.x_vals + offset, y=means,
            yerr=[[0] * len(stds), stds],
            linestyle=linestyle, marker="o", markersize=2,
            color=SIDE_COLORS[side],
            label=f"Tone {side} {kind}",
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
# coded).
#
# Reuses CG-2 helpers:
#   - compute_trial_lick_delays — per-trial lick timing relative to reward
#
# Mirrors legacy ``plot_raster`` (behavior_report_PS.py:415-448) +
# emission (line 531-533). Intentional deviations from legacy:
#   1. Side-naming convention — legacy uses ``fn_flip_lr(side_tone)``
#      on the ylabel because legacy operates WS-frame internally; the
#      new pipeline reads side_tone as mouse-frame directly.
#   2. ``raster_dot_alpha`` (Priya 2026-05-13) — dots use
#      ``alpha=0.6`` (config-driven) instead of legacy's opaque 1.0.
#      Lets the under-layer peek through; mitigates label-side-
#      dependent occlusion (R-on-top of L) when lick counts are
#      asymmetric across sides.
#   3. ``criteria_34`` pass/fail horizontal-bar overlay REMOVED
#      (Priya 2026-05-13). Eliminates row-level color clutter so the
#      dot pattern reads cleanly. Legacy lines 428-430 (the
#      ``axs[ii, jj].plot([-1, 4], [idx, idx], "g" if crit else "r",
#      alpha=0.3)`` block) intentionally not ported.
#   4. Explicit zorder on dots (Priya 2026-05-13 Round 2.7) —
#      incorrect (magenta) drawn on top of correct (green) so errors
#      are always visible regardless of subplot. Legacy used
#      insertion-order, so visibility depended on per-cell lick counts.
#   5. Figure-level ``Time (s)`` xlabel via fig.supxlabel (Round 2.7)
#      replaces the per-axis xlabel × N_sessions of legacy.
#   6. Smaller xtick labels (raster_dot_alpha-paired): xtick_fontsize
#      reduced 10→6 + explicit raster_xticks + thinner reward marker
#      (Round 2.7). Resolves the "0 tick perceptually merged into
#      reward marker" issue Priya flagged 2026-05-13.


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
        side_tone``; ``raster_dot_incorrect_color`` (magenta)
        otherwise. Per-dot ``alpha=visual_gate.raster_dot_alpha``
        (intentional deviation; see module-level note 2).
      - Vertical reward-marker line at x=0, color
        ``raster_reward_marker_color``, alpha
        ``raster_reward_marker_alpha``, linewidth
        ``raster_reward_marker_linewidth`` (intentional deviation;
        thinner than legacy default to avoid merging with the "0"
        xtick label).
      - X-axis limit ``raster_xlim`` + explicit
        ``raster_xticks`` (intentional deviation; matplotlib's
        auto-locator placed -1 which crowded the reward marker).
      - Top-row only: per-cell title (rotated 90°) = session label
        formatted via :func:`legend_label_for_date`.
      - Bottom-row only: xtick label sizing via
        ``xtick_fontsize`` (the "Time (s)" xlabel itself is now a
        figure-level supxlabel; intentional deviation from legacy's
        per-axis xlabel × N_sessions repetition).
      - Left-column only: ylabel "Trials   (side: mouse {side_tone})".

    The legacy criteria_34 pass/fail horizontal-line overlay
    (behavior_report_PS.py:428-430) is intentionally NOT ported —
    see module-level note 3.

    Suptitle:
      ``"Licks after rewards. Dots: (green=corr, magenta=incorr)."``

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

    # Compute per-session lick delays in one pass.
    per_date_delays: dict[str, dict[str, dict[int, dict[str, np.ndarray]]]] = {}
    for date in dates:
        data = load_session_plot_data(animal, date, resolver)
        per_date_delays[date] = compute_trial_lick_delays(
            data, window_around,
        )

    fig, axs = plt.subplots(
        nrows=2, ncols=len(dates),
        figsize=tuple(config["figsize_raster_grid"]),
        squeeze=False,
    )
    for ii, side_tone in enumerate(("L", "R")):
        for jj, date in enumerate(dates):
            ax = axs[ii, jj]
            delays_by_trial = per_date_delays[date][f"Tone_{side_tone}"]
            # Load sample_rate from the same SessionPlotData? We need it
            # for the lick-delay → seconds conversion. Reload here to
            # avoid keeping all SessionPlotData live; lookup is cheap.
            data = load_session_plot_data(animal, date, resolver)
            for idx_tone, by_side in delays_by_trial.items():
                for side_lick in ("L", "R"):
                    lick_delays = by_side[f"Lick_{side_lick}"]
                    if lick_delays.size == 0:
                        continue
                    is_correct = (side_lick == side_tone)
                    color = (
                        config["raster_dot_correct_color"] if is_correct
                        else config["raster_dot_incorrect_color"]
                    )
                    dot_zorder = (
                        config["raster_dot_correct_zorder"] if is_correct
                        else config["raster_dot_incorrect_zorder"]
                    )
                    ax.scatter(
                        lick_delays / data.sample_rate,
                        np.full_like(lick_delays, idx_tone, dtype=float),
                        s=config["raster_dot_size"],
                        color=color,
                        alpha=config["raster_dot_alpha"],
                        zorder=dot_zorder,
                    )
            # Reward marker (vertical line at x=0).
            n_trials = len(delays_by_trial)
            ax.plot(
                [0, 0], [0, n_trials],
                config["raster_reward_marker_color"],
                alpha=config["raster_reward_marker_alpha"],
                linewidth=config["raster_reward_marker_linewidth"],
            )
            ax.set_xlim(*config["raster_xlim"])
            ax.set_xticks(config["raster_xticks"])
            # Top-row title (column header).
            if ii == 0:
                title = legend_label_for_date(
                    date, align_to_stroke=align_to_stroke, d0=d0,
                )
                ax.set_title(title, rotation=90, fontsize="x-small")
                ax.set_xticklabels([])
            # Bottom-row xtick label sizing (the "Time (s)" xlabel is
            # set figure-level via fig.supxlabel below).
            if ii == 1:
                ax.tick_params(axis="x", labelsize=config["xtick_fontsize"])
            # Left-column ylabel. New-pipeline side convention: read
            # mouse-frame directly (no fn_flip_lr).
            if jj == 0:
                ax.set_ylabel(f"Trials   (side: mouse {side_tone})")
            else:
                ax.set_yticklabels([])

    fig.supxlabel(
        "Time (s)", fontsize=config["raster_xlabel_fontsize"],
    )
    fig.suptitle(
        "Licks after rewards. Dots: (green=corr, magenta=incorr).",
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
    # Q-A.β: anchor consolidation is over tone-onset events (the
    # always-present trial cue). The synchronous-event property
    # (per .scratch_phase_8a_10/reward_tone_swap_extended_diagnostic.md
    # §C) means pre-fix "inter-reward windows" computed over the
    # swapped-labeled channel were already inter-tone windows
    # numerically.
    all_tones = np.sort(np.concatenate([
        session_data.tones_idx["Tone_L"],
        session_data.tones_idx["Tone_R"],
    ]))
    if all_tones.size == 0:
        return out

    # Inter-tone windows.
    for tone, next_tone in zip(all_tones[:-1], all_tones[1:]):
        start = int(tone) + upper
        end = min(int(next_tone), int(tone) + mx)
        if end <= start:
            continue
        for side in ("L", "R"):
            ls = session_data.lick_idx[f"Lick_{side}"]
            out[side] += int(np.sum((ls > start) & (ls < end)))

    # Post-last-tone window. Capped at n_samples_session when known;
    # uncapped otherwise (fallback when WS NPZ had no 1D signal).
    last = int(all_tones[-1])
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
    for side_tone in ("L", "R"):
        trials = trial_lick_delays[f"Tone_{side_tone}"]
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
