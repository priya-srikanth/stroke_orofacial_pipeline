"""Phase 8a.10 sub-deliverable B — bare-vs-b comparison.

Scope (Addendum #1 2026-05-13 — cohort-only design): post-stroke
comparison of bare-half (single-spout) vs b-half (secondary-spout)
session conditions for the 14 Pattern B sessions across PS51, PS54,
PS55. The scientific message is *excursion limitation relieved by
proximity*: post-stroke mice reach the closer secondary spout more
reliably than the standard-distance bare spout, and contact more
frequently once there.

3 retained endpoints, rendered as a single 3×2 cohort grid per
animal (rows = endpoint, cols = mouse-side L vs R):

  Row 1: ``accuracy_firstCorrectLickAll`` — first-correct-lick
    fraction, denominator = ALL trials of that cue type. Matches
    the legacy ``accuracy_firstCorrectLickAll`` family. Per-session
    dot, same-date bare/b connector, red horizontal mean bar.
  Row 2: ``numLicks_bySession`` (correct + incorrect) — mean licks
    per trial. Replicates the layering convention of visual_gate's
    ``render_numLicks_bySession_correct_and_incorrect``. Per-session
    dots + connectors + mean bar (same pattern as Row 1).
  Row 3: ``lick_raster`` — bare trials top half, b trials bottom
    half, horizontal divider. Trials pooled across sessions in date
    order. Dot conventions inherited from visual_gate raster
    (alpha=0.6, zorder layering, explicit xticks, thin reward
    marker).

Superseded scope (CG-B2): per-session paired panels for 5 endpoints
were implemented under CG-B2 (commit d757294) but eliminated per
Addendum #1. The 2 dropped endpoints (first-lick-latency, reward-
acquisition-rate-over-time) had no downstream scientific consumer.

Cohort B (Pattern B) registry lives in
``configs/session_overrides.yaml`` under ``secondary_spout_sessions:``.
:func:`iter_cohort_b_sessions` reads that registry, filters to
post-stroke sessions (:meth:`AnimalInfo.day_relative_to_stroke`
``>= 2`` — drops both d0 and d+1), and pairs each survivor's bare
half with its b half via :func:`load_session_plot_data` (extended
for this phase to accept a ``half_suffix`` kwarg).

Forward-pointer to Phase 8a.10.1
--------------------------------
The Reward_{L,R} channels carry tone-cue indices (not reward
indices) cohort-wide due to the deferred Tone↔Reward swap (Phase
8a.10.1). Renderer code is faithful; semantic labels will
retroactively match data after 8a.10.1's re-emit. Affects Row 3's
"reward marker" line semantics (currently marks tone onset, not
reward delivery).
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.visual_gate import (
    SIDE_COLORS,
    SessionPlotData,
    compute_first_lick_correct,
    compute_trial_lick_delays,
    load_behavior_report_params,
    load_session_plot_data,
    load_visual_gate_config,
)


# Post-stroke filter cutoff. Priya 2026-05-13: rel_day >= 2 — drops
# both d0 (e.g. PS54/2025-04-30) AND d+1 (e.g. PS51/2025-04-30).
# Treat d+1 as immediate stroke-aftermath, not recovery. Cuts the
# cohort from 19 (pre-filter) to 14 (post-filter).
COHORT_B_REL_DAY_MIN = 2

# Cohort renderer x-axis category positions (categorical: bare, b).
_X_BARE = 0
_X_B = 1

# Display labels (Addendum #2 Tweak 1, 2026-05-13). Code identifiers
# ("bare" / "b") stay everywhere; only the rendered tick labels +
# axis title change. Row 3 raster's y-axis half labels also use these.
SPOUT_DISTANCE_DISPLAY_LABELS: dict[str, str] = {
    "bare": "Standard",
    "b": "Close",
}
SPOUT_DISTANCE_XAXIS_TITLE = "Spout Distance"

# Dot fill convention (Addendum #3 Tweak 2). Color encodes mouse
# cue side (SIDE_COLORS); fill style encodes spout distance
# condition. Standard (bare half) = filled; Close (b half) = open
# outline. The mean line color matches the mouse-side color (same
# for both Standard and Close means within a panel).
# Constants list the FACE-color treatment only; edge color is
# always the mouse-side color and is wired in
# _plot_row_per_session_dots_and_means.
SPOUT_DISTANCE_DOT_FILL: dict[str, str] = {
    "bare": "filled",   # markerfacecolor = mouse-side color
    "b": "open",        # markerfacecolor = "none"
}
# Mean horizontal bar linewidth (carried from Addendum #2 Round 2).
COHORT_MEAN_BAR_LINEWIDTH = 0.75

# Style for same-date bare/b connector lines (unchanged; gray;
# neutral — spans both conditions).
COHORT_CONNECTOR_KWARGS: dict[str, Any] = {
    "color": "gray",
    "linewidth": 0.5,
    "alpha": 0.4,
}

# Row 4 inter-session boundary line styling (Addendum #3 Tweak 5:
# darker than R2's lightgray/0.3/0.5).
RASTER_INTRA_HALF_BOUNDARY_KWARGS: dict[str, Any] = {
    "color": "gray",
    "linewidth": 0.5,
    "alpha": 0.8,
    "zorder": 1,
}


@dataclass
class SessionPairData:
    """Per-session bare-vs-b paired inputs.

    Attributes
    ----------
    animal : str
        e.g. ``"PS55"``.
    date : datetime.date
        Session date.
    bare : SessionPlotData
        Bare-half Phase-2 + Phase-1 inputs (single-spout
        condition; read with ``half_suffix=""``).
    b : SessionPlotData
        B-half Phase-2 + Phase-1 inputs (secondary-spout
        condition; read with ``half_suffix="b"`` from
        ``licks_and_rewards/<animal>/<YYYYMMDD>b.npz``).
    """

    animal: str
    date: datetime.date
    bare: SessionPlotData
    b: SessionPlotData


def _iso_to_yyyymmdd(iso: str) -> str:
    """Convert ``"YYYY-MM-DD"`` (registry key form) → ``"YYYYMMDD"``."""
    return iso.replace("-", "")


def _iso_to_date(iso: str) -> datetime.date:
    return datetime.date.fromisoformat(iso)


def iter_cohort_b_session_keys(
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
    *,
    animals: list[str] | None = None,
    require_on_disk: bool = True,
    animal_info_cache: dict[str, AnimalInfo] | None = None,
) -> Iterator[tuple[str, datetime.date]]:
    """Yield (animal, date) keys for the filtered Cohort B.

    Same filter logic as :func:`iter_cohort_b_sessions` but does NOT
    load NPZs — pure registry walk + filter. Use this for tests that
    probe the iteration order/filter without needing on-disk data,
    or for orchestrator code that just needs to count or enumerate
    the cohort.

    Parameters mirror :func:`iter_cohort_b_sessions`; see that
    function's docstring.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    secondary = overrides_config.get("secondary_spout_sessions", {}) or {}

    if animals is None:
        target_animals = sorted(secondary.keys())
    else:
        target_animals = [a for a in animals if a in secondary]

    if animal_info_cache is None:
        animal_info_cache = {}

    sp_root = resolver.pipeline_outputs("spout_behavior")

    for animal in target_animals:
        if animal not in animal_info_cache:
            animal_info_cache[animal] = get_animal(animal)
        info = animal_info_cache[animal]

        iso_dates = sorted(secondary[animal].keys())
        for iso in iso_dates:
            date = _iso_to_date(iso)
            if info.day_relative_to_stroke(date) < COHORT_B_REL_DAY_MIN:
                continue

            date_str = _iso_to_yyyymmdd(iso)
            if require_on_disk:
                # b-half existence gate. Both bare and b NPZs are
                # under licks_and_rewards/<animal>/. For Pattern B
                # (which all Cohort B entries are by construction),
                # bare is at <date_str>.npz and b is at <date_str>b.npz.
                bare_npz = sp_root / "licks_and_rewards" / animal / f"{date_str}.npz"
                b_npz = sp_root / "licks_and_rewards" / animal / f"{date_str}b.npz"
                if not bare_npz.exists() or not b_npz.exists():
                    continue

            yield animal, date


def iter_cohort_b_sessions(
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
    *,
    animals: list[str] | None = None,
    require_on_disk: bool = True,
    animal_info_cache: dict[str, AnimalInfo] | None = None,
) -> Iterator[SessionPairData]:
    """Yield bare-vs-b paired session data for the filtered Cohort B.

    Walks the ``secondary_spout_sessions:`` registry in
    ``configs/session_overrides.yaml``. For each ``(animal, iso_date)``
    entry whose ``rel_day >= COHORT_B_REL_DAY_MIN`` (= 2), loads the
    bare-half and b-half Phase-2 NPZs and yields a
    :class:`SessionPairData` carrying both.

    Skip rules (silent):
      - Pre-filter rel_day < 2 (i.e. baseline, d0, or d+1) — these
        Pattern B entries exist in the registry but pre-stroke
        comparisons aren't part of sub-deliverable B's scope.
      - The b-half NPZ doesn't exist on disk (``require_on_disk=True``)
        — e.g. pre-stroke Pattern B sessions whose b half was never
        recorded.

    Parameters
    ----------
    resolver : PathResolver
        For Phase-2 NPZ path resolution.
    overrides_config : dict, optional
        Pre-loaded ``session_overrides.yaml`` mapping (the dict, not
        the file path). ``None`` loads via
        :func:`stroke_orofacial.config_loader.load_session_overrides`.
    animals : list of str, optional
        Restrict to a subset of the cohort. Default ``None`` walks all
        registered animals. Used for the PS55 pilot
        (``animals=["PS55"]`` yields exactly 3 SessionPairData).
    require_on_disk : bool, default True
        Skip sessions whose b-half NPZ doesn't exist on disk. Set
        ``False`` for tests that probe the registry without populating
        the filesystem.
    animal_info_cache : dict, optional
        Optional pre-loaded ``{animal: AnimalInfo}`` map; the loader
        otherwise calls :func:`get_animal` once per animal. Pass when
        testing with synthetic AnimalInfo records (e.g.
        ``stroke_date`` overrides).

    Yields
    ------
    SessionPairData
        Sorted by (animal_id, date) ascending. ``bare`` and ``b``
        fields come from :func:`load_session_plot_data` with
        ``half_suffix=""`` and ``half_suffix="b"`` respectively.
    """
    for animal, date in iter_cohort_b_session_keys(
        resolver, overrides_config,
        animals=animals,
        require_on_disk=require_on_disk,
        animal_info_cache=animal_info_cache,
    ):
        date_str = date.strftime("%Y%m%d")
        bare = load_session_plot_data(
            animal, date_str, resolver,
            overrides_config=overrides_config,
        )
        b = load_session_plot_data(
            animal, date_str, resolver,
            overrides_config=overrides_config,
            half_suffix="b",
        )
        yield SessionPairData(
            animal=animal, date=date, bare=bare, b=b,
        )


def list_cohort_b_animals(
    overrides_config: dict[str, Any] | None = None,
) -> list[str]:
    """Return sorted Cohort B animal IDs from the registry.

    Convenience helper for the orchestrator notebook to default
    ``ANIMALS_SPOUT_CLOSE_VS_STD`` to all registered animals.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    secondary = overrides_config.get("secondary_spout_sessions", {}) or {}
    return sorted(secondary.keys())


# =====================================================================
# Commit-group B3: cohort-only animal summary (3 endpoints × L/R grid)
# =====================================================================
#
# Output: spout_close_vs_std/cohort/<animal>_summary.{svg,png}
# Layout: 3 rows × 2 cols.
#   Row 1: accuracy_firstCorrectLickAll per side (L, R)
#   Row 2: numLicks_bySession (correct + incorrect) per side
#   Row 3: lick_raster per side, bare top / b bottom


def _half_accuracy_firstCorrectLickAll_per_side(
    session: SessionPlotData,
    window_around_rewards: tuple[float, float] | list[float],
) -> dict[str, float]:
    """Mean first-lick-correct per side for one half, ALL-trials
    denominator (treat_none_as_zero=True semantics).

    Matches the legacy ``accuracy_firstCorrectLickAll`` family
    (visual_gate.compute_firstLickCorrect_bySession with
    ``treat_none_as_zero=True``). Per Addendum #1: no-lick trials
    counted as 0, denominator = ALL trials of that cue type.

    Worked example (from addendum): 2 first-correct-licks across 48
    cue trials → 0.042 (NOT 2/2 = 1.0).
    """
    delays = compute_trial_lick_delays(session, window_around_rewards)
    flc = compute_first_lick_correct(delays)
    out: dict[str, float] = {}
    for side in ("L", "R"):
        per_reward = flc[side]
        if len(per_reward) == 0:
            out[side] = float("nan")
            continue
        # treat_none_as_zero=True: None (no post-reward licks at all)
        # counted as 0 (incorrect). Denominator = ALL trials.
        vals = [0.0 if v is None else float(v) for v in per_reward.values()]
        out[side] = float(np.mean(vals))
    return out


def _half_mean_licks_per_trial_per_side(
    session: SessionPlotData,
    window_around_rewards: tuple[float, float] | list[float],
) -> dict[str, dict[str, float]]:
    """Mean licks per trial within window, split by (reward_side,
    correctness). Returns
    ``{"L": {"correct": float, "incorrect": float}, "R": {...}}``.

    Replicates visual_gate's ``numLicks_bySession_correct_and_incorrect``
    convention: per-trial counts averaged across trials of that
    reward side. Correct = lick on same side as reward; incorrect =
    lick on other side.
    """
    delays = compute_trial_lick_delays(session, window_around_rewards)
    out: dict[str, dict[str, float]] = {"L": {}, "R": {}}
    for side_reward in ("L", "R"):
        per_reward = delays[f"Reward_{side_reward}"]
        n_trials = len(per_reward)
        if n_trials == 0:
            out[side_reward] = {
                "correct": float("nan"), "incorrect": float("nan"),
            }
            continue
        correct_counts: list[int] = []
        incorrect_counts: list[int] = []
        for _idx, by_side in per_reward.items():
            correct_counts.append(int(by_side[f"Lick_{side_reward}"].size))
            other = "R" if side_reward == "L" else "L"
            incorrect_counts.append(int(by_side[f"Lick_{other}"].size))
        out[side_reward] = {
            "correct": float(np.mean(correct_counts)),
            "incorrect": float(np.mean(incorrect_counts)),
        }
    return out


def _plot_row_per_session_dots_and_means(
    ax,
    side_reward: Literal["L", "R"],
    *,
    bare_vals: list[float],
    b_vals: list[float],
    licking_xtick_fontsize: int | float | None = None,
) -> None:
    """Generic dot-plot helper for Rows 1, 2, 3.

    Plots one dot per session per condition at x ∈ {0 (bare), 1 (b)},
    same-date gray connectors, and per-mouse-side horizontal mean
    bars. Dot color encodes mouse cue side (SIDE_COLORS); fill style
    encodes spout distance condition (Addendum #3 Tweak 2):
      - Standard (bare): filled dot (markerfacecolor=mouse_side_color).
      - Close (b):       open dot   (markerfacecolor="none",
                                     markeredgecolor=mouse_side_color).
    Mean line color = mouse_side_color (same for both Standard and
    Close mean within a panel; differentiation comes from x-position).

    Addendum #4 Tweak 3: ``licking_xtick_fontsize`` controls the
    "Standard"/"Close" xtick label size. ``None`` keeps the
    matplotlib default (~10).

    Caller sets y-axis limits, labels, titles.
    """
    n_sessions = len(bare_vals)
    if n_sessions != len(b_vals):
        raise ValueError(
            f"per-session value mismatch: bare={n_sessions}, "
            f"b={len(b_vals)}"
        )
    mouse_side_color = SIDE_COLORS[side_reward]
    # Same-date connectors (one line per session; gray; spans both
    # conditions — neutrality is intentional).
    for v_bare, v_b in zip(bare_vals, b_vals, strict=True):
        if np.isnan(v_bare) or np.isnan(v_b):
            continue
        ax.plot(
            [_X_BARE, _X_B], [v_bare, v_b],
            **COHORT_CONNECTOR_KWARGS, zorder=1,
        )
    # Per-session dots — color = mouse_side_color; fill style
    # differentiates Standard (filled) vs Close (open).
    for x, vals, condition in (
        (_X_BARE, bare_vals, "bare"),
        (_X_B, b_vals, "b"),
    ):
        is_filled = SPOUT_DISTANCE_DOT_FILL[condition] == "filled"
        facecolor = mouse_side_color if is_filled else "none"
        for v in vals:
            if np.isnan(v):
                continue
            ax.scatter(
                x, v, s=24, marker="o",
                facecolor=facecolor, edgecolor=mouse_side_color,
                linewidth=0.8, zorder=2,
            )
    # Mean bars — color = mouse_side_color (same for Standard and
    # Close). Differentiation = x-position only.
    bare_arr = np.array(bare_vals, dtype=float)
    b_arr = np.array(b_vals, dtype=float)
    bare_mean = float(np.nanmean(bare_arr)) if bare_arr.size > 0 else float("nan")
    b_mean = float(np.nanmean(b_arr)) if b_arr.size > 0 else float("nan")
    for x, m in ((_X_BARE, bare_mean), (_X_B, b_mean)):
        if np.isnan(m):
            continue
        ax.hlines(
            m, x - 0.3, x + 0.3,
            color=mouse_side_color,
            linewidth=COHORT_MEAN_BAR_LINEWIDTH, zorder=3,
        )
    # X-axis ticks for the categorical pair. Addendum #2 Tweak 1:
    # rendered labels are "Standard" / "Close"; underlying code
    # identifiers stay "bare" / "b".
    ax.set_xticks([_X_BARE, _X_B])
    ax.set_xticklabels([
        SPOUT_DISTANCE_DISPLAY_LABELS["bare"],
        SPOUT_DISTANCE_DISPLAY_LABELS["b"],
    ])
    if licking_xtick_fontsize is not None:
        ax.tick_params(axis="x", labelsize=licking_xtick_fontsize)
    ax.set_xlim(-0.5, 1.5)


def _plot_row_lick_raster(
    ax,
    side_reward: Literal["L", "R"],
    sessions: list[SessionPairData],
    *,
    window: tuple[float, float] | list[float],
    config: dict[str, Any],
    cohort_config: dict[str, Any],
    animal_info: AnimalInfo,
    y_range: tuple[float, float] | None = None,
) -> tuple[int, int]:
    """Row 4: pooled cohort lick raster, bare top / b bottom.

    Trials are pooled across sessions in date order:
      - rows ``0 .. n_bare-1`` (top): bare-half trials of cue
        ``side_reward``, concatenated chronologically across
        sessions.
      - horizontal divider line at y = n_bare.
      - rows ``n_bare .. n_bare + n_b - 1`` (bottom): b-half trials,
        same ordering.

    Addendum #2 Tweak 3 / Addendum #3 Tweak 5: gray horizontal
    lines (RASTER_INTRA_HALF_BOUNDARY_KWARGS — color="gray",
    linewidth=0.5, alpha=0.8 in R3) mark inter-session boundaries
    within each half. Count per panel = ``(n_bare_sessions - 1) +
    (n_b_sessions - 1)``.

    Addendum #3 Tweak 4: per-session "d+N" labels rendered outside
    the right axis spine, rotated 90°, where ``N =
    animal_info.day_relative_to_stroke(session.date)``. One label
    per session-block (Standard + Close, both halves emit labels).

    Addendum #2 Tweak 4: caller may pass ``y_range`` to enforce a
    shared y-limit across L/R panels (pads the shorter side with
    whitespace below the data). Default ``None`` falls back to a
    snug per-panel ylim.

    Returns
    -------
    tuple[int, int]
        ``(n_bare, n_b)`` — total trial counts per half for this
        side. Callers use this to compute the shared y-range across
        L/R panels (Tweak 4).
    """
    # First pass: count trials per session in each half to assign
    # global y indices.
    bare_trials_per_session: list[int] = []
    b_trials_per_session: list[int] = []
    for pair in sessions:
        bare_n = len(pair.bare.rewards_idx[f"Reward_{side_reward}"])
        b_n = len(pair.b.rewards_idx[f"Reward_{side_reward}"])
        bare_trials_per_session.append(bare_n)
        b_trials_per_session.append(b_n)
    n_bare = sum(bare_trials_per_session)
    n_b = sum(b_trials_per_session)

    # Second pass: scatter dots at global y indices.
    bare_y_offset = 0
    b_y_offset = n_bare + 1  # +1 for divider gap
    for pair, n_bare_session, n_b_session in zip(
        sessions, bare_trials_per_session, b_trials_per_session, strict=True,
    ):
        for _half, session, y_base in (
            ("bare", pair.bare, bare_y_offset),
            ("b", pair.b, b_y_offset),
        ):
            delays_full = compute_trial_lick_delays(session, window)
            delays_by_reward = delays_full[f"Reward_{side_reward}"]
            for idx_reward, by_side in delays_by_reward.items():
                trial_y = y_base + idx_reward
                for side_lick in ("L", "R"):
                    lick_delays = by_side[f"Lick_{side_lick}"]
                    if lick_delays.size == 0:
                        continue
                    is_correct = (side_lick == side_reward)
                    color = (
                        config["raster_dot_correct_color"] if is_correct
                        else config["raster_dot_incorrect_color"]
                    )
                    dot_zorder = (
                        config["raster_dot_correct_zorder"] if is_correct
                        else config["raster_dot_incorrect_zorder"]
                    )
                    ax.scatter(
                        lick_delays / session.sample_rate,
                        np.full_like(lick_delays, trial_y, dtype=float),
                        s=config["raster_dot_size"],
                        color=color,
                        alpha=config["raster_dot_alpha"],
                        zorder=dot_zorder,
                    )
        bare_y_offset += n_bare_session
        b_y_offset += n_b_session

    # Inter-session boundary lines within each half (Tweak 3 /
    # Tweak 5 darker styling). One line between consecutive
    # sessions; count per half = n_sessions - 1.
    xmin, xmax = config["raster_xlim"]
    cum_bare = 0
    for i, n_session in enumerate(bare_trials_per_session):
        if i == len(bare_trials_per_session) - 1:
            break  # no boundary after the last session
        cum_bare += n_session
        ax.hlines(
            cum_bare - 0.5, xmin=xmin, xmax=xmax,
            **RASTER_INTRA_HALF_BOUNDARY_KWARGS,
        )
    cum_b = n_bare + 1  # b half starts at this y offset
    for i, n_session in enumerate(b_trials_per_session):
        if i == len(b_trials_per_session) - 1:
            break
        cum_b += n_session
        ax.hlines(
            cum_b - 0.5, xmin=xmin, xmax=xmax,
            **RASTER_INTRA_HALF_BOUNDARY_KWARGS,
        )

    # Per-session "d+N" labels outside the right axis spine
    # (Addendum #3 Tweak 4). N = day_relative_to_stroke. One per
    # session-block in EACH half (bare + b emit independently).
    day_label_fontsize = cohort_config["raster_day_label_fontsize"]
    bare_y_running = 0
    for pair, n_session in zip(
        sessions, bare_trials_per_session, strict=True,
    ):
        if n_session == 0:
            continue
        center_y = bare_y_running + n_session / 2
        rel_day = animal_info.day_relative_to_stroke(pair.date)
        ax.text(
            1.02, center_y, f"d{rel_day:+d}",
            transform=ax.get_yaxis_transform(),
            rotation=270,
            rotation_mode="default",
            ha="center", va="center",
            fontsize=day_label_fontsize,
        )
        bare_y_running += n_session
    b_y_running = n_bare + 1
    for pair, n_session in zip(
        sessions, b_trials_per_session, strict=True,
    ):
        if n_session == 0:
            continue
        center_y = b_y_running + n_session / 2
        rel_day = animal_info.day_relative_to_stroke(pair.date)
        ax.text(
            1.02, center_y, f"d{rel_day:+d}",
            transform=ax.get_yaxis_transform(),
            rotation=270,
            rotation_mode="default",
            ha="center", va="center",
            fontsize=day_label_fontsize,
        )
        b_y_running += n_session

    # Reward marker — single line covering both halves' x=0.
    ax.plot(
        [0, 0], [0, max(1, n_bare + n_b + 1)],
        config["raster_reward_marker_color"],
        alpha=config["raster_reward_marker_alpha"],
        linewidth=config["raster_reward_marker_linewidth"],
    )
    # Divider line between bare ("Standard") and b ("Close") halves
    # — kept thicker / darker than the intra-half boundary lines.
    ax.hlines(
        n_bare + 0.5,
        xmin=xmin, xmax=xmax,
        color="black", linewidth=0.8, linestyle="-", zorder=4,
    )
    ax.set_xlim(xmin, xmax)
    # Addendum #5 Tweak 1: cohort raster shows xticks at every
    # integer second (visual_gate single-session raster keeps its
    # sparser [0, 5] endpoint-only ticks; cohort overrides via the
    # spout_close_vs_std-scoped knob).
    ax.set_xticks(cohort_config["raster_xticks"])
    # Cohort raster gets larger xticks than visual_gate's
    # single-session raster (Addendum #3 Tweak 6 / Addendum #4
    # Tweak 1).
    ax.tick_params(
        axis="x", labelsize=cohort_config["raster_xtick_fontsize"],
    )
    # Addendum #5 Tweak 3: numeric trial-count y-ticks (was R3/R4's
    # Standard/Close text ticks). Y-axis NOT inverted — y=0 at
    # bottom, max-trial-count at top (matches visual_gate single-
    # session raster convention; "earlier trials at bottom").
    n_total = n_bare + n_b
    ax.set_yticks([0, n_total])
    ax.set_yticklabels(["0", str(n_total)])
    ax.tick_params(
        axis="y", labelsize=cohort_config["raster_ytick_fontsize"],
    )
    # Y-limit: per-panel snug by default; caller can pass y_range
    # to enforce a shared limit across L/R panels (Tweak 4).
    if y_range is None:
        ax.set_ylim(-0.5, n_total + 1.5)
    else:
        ax.set_ylim(*y_range)
    # NOTE: ax.invert_yaxis() removed in R5 Tweak 3c. With the
    # natural y-axis orientation (0 at bottom), first Standard
    # trial sits at bottom; last Close trial at top.
    # Half labels: "Standard" / "Close" outside the LEFT spine
    # (Addendum #5 Tweak 3 Option α). Rotated 90° CCW: bottom-to-
    # top reading; mirrors the day-labels' rotated-270° right-spine
    # convention.
    half_label_fs = cohort_config["raster_half_label_fontsize"]
    if n_bare > 0:
        ax.text(
            -0.08, n_bare / 2,
            SPOUT_DISTANCE_DISPLAY_LABELS["bare"],
            transform=ax.get_yaxis_transform(),
            rotation=90,
            rotation_mode="default",
            ha="center", va="center",
            fontsize=half_label_fs,
        )
    if n_b > 0:
        ax.text(
            -0.08, n_bare + 0.5 + n_b / 2,
            SPOUT_DISTANCE_DISPLAY_LABELS["b"],
            transform=ax.get_yaxis_transform(),
            rotation=90,
            rotation_mode="default",
            ha="center", va="center",
            fontsize=half_label_fs,
        )
    ax.set_title(
        f"Reward {side_reward}",
        fontsize=cohort_config["panel_title_fontsize"],
    )
    return n_bare, n_b


def load_cohort_config(defaults_path: Path | str | None = None) -> dict[str, Any]:
    """Return the ``spout_close_vs_std:`` block of
    ``configs/defaults.yaml``.

    Cohort-renderer-specific typography knobs (Addendum #3 Tweak 6):
    ``panel_title_fontsize``, ``raster_xtick_fontsize``,
    ``raster_xlabel_fontsize``, ``raster_day_label_fontsize``.
    """
    from stroke_orofacial.config_loader import load_defaults
    defaults = load_defaults(defaults_path)
    if "spout_close_vs_std" not in defaults:
        raise KeyError(
            "configs/defaults.yaml: 'spout_close_vs_std:' block "
            "missing — Phase 8a.10 Addendum #3 Tweak 6 should have "
            "added it"
        )
    return defaults["spout_close_vs_std"]


def render_animal_summary_spout_close_vs_std(
    animal: str,
    *,
    sessions: list[SessionPairData] | None = None,
    resolver: PathResolver,
    config: dict[str, Any] | None = None,
    cohort_config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Render one 4×2 cohort summary figure for one animal.

    Addendum #1 (2026-05-13) cohort-only design + Addendum #3
    (2026-05-13) Tweak 3 4-row layout split. Output:
    ``{resolver.spout_close_vs_std_dir(animal=None)}/<animal>_summary.{svg,png}``
    (the ``animal=None`` branch resolves to
    ``.../spout_close_vs_std/cohort/``).

    Layout (4 rows × 2 cols):
      - Row 1, cols (L, R): accuracy_firstCorrectLickAll. Per-session
        dot, same-date bare/b connector, mouse-side-color horizontal
        mean bar. Y ∈ [0, 1]. Denominator = ALL trials
        (treat_none_as_zero=True).
      - Row 2, cols (L, R): mean CORRECT licks per trial.
      - Row 3, cols (L, R): mean INCORRECT licks per trial.
        (Independent y-axis from Row 2: incorrect-lick magnitudes
        are typically much smaller; sharing would crush detail.)
      - Row 4, cols (L, R): pooled lick raster, bare top / b bottom,
        divider line. Trials pooled chronologically across sessions.
        Per-session "d+N" labels outside the right axis spine.

    Color/fill convention (Addendum #3 Tweak 2):
      - Dot color = mouse cue side (SIDE_COLORS: L=dodgerblue,
        R=mediumvioletred).
      - Dot fill = condition: Standard (bare) filled, Close (b) open.
      - Mean line color = mouse side (same color for both
        Standard and Close mean within a panel).
      - Connector line: gray (neutral; spans both conditions).

    Parameters
    ----------
    animal : str
        e.g. ``"PS55"``.
    sessions : list of SessionPairData, optional
        Pre-loaded post-stroke Cohort B sessions for this animal.
        ``None`` loads via :func:`iter_cohort_b_sessions` with
        ``animals=[animal]``.
    resolver : PathResolver
        For input NPZ paths + output figure paths.
    config : dict, optional
        Pre-loaded ``visual_gate:`` block from
        ``configs/defaults.yaml``. ``None`` loads via
        :func:`load_visual_gate_config`.
    cohort_config : dict, optional
        Pre-loaded ``spout_close_vs_std:`` block (Tweak 6
        typography knobs). ``None`` loads via
        :func:`load_cohort_config`.
    behavior_params : dict, optional
        Pre-loaded ``behavior_report:`` block. ``None`` loads via
        :func:`load_behavior_report_params`.
    animal_info : AnimalInfo, optional
        Pre-loaded :class:`stroke_orofacial.animals.AnimalInfo` —
        required for the Row 4 "d+N" labels (Tweak 4). ``None``
        calls :func:`get_animal`.
    overwrite : {"force", "skip", "raise"}
        Same semantics as :func:`save_visual_gate_figure`.

    Returns
    -------
    tuple[Path, Path]
        ``(svg_path, png_path)``.

    Raises
    ------
    ValueError
        If the animal has zero post-stroke Cohort B sessions.
    """
    config = config or load_visual_gate_config()
    cohort_config = cohort_config or load_cohort_config()
    behavior_params = behavior_params or load_behavior_report_params()
    window = behavior_params["window_around_rewards"]
    if animal_info is None:
        animal_info = get_animal(animal)

    if sessions is None:
        sessions = list(iter_cohort_b_sessions(
            resolver, animals=[animal],
        ))
    if len(sessions) == 0:
        raise ValueError(
            f"render_animal_summary_spout_close_vs_std: no post-stroke "
            f"Cohort B sessions for {animal!r} — cannot build the 4×2 "
            f"summary grid"
        )

    # ---- Compute per-session scalars (Rows 1 + 2 + 3) ----
    bare_acc: dict[str, list[float]] = {"L": [], "R": []}
    b_acc: dict[str, list[float]] = {"L": [], "R": []}
    bare_n_correct: dict[str, list[float]] = {"L": [], "R": []}
    bare_n_incorrect: dict[str, list[float]] = {"L": [], "R": []}
    b_n_correct: dict[str, list[float]] = {"L": [], "R": []}
    b_n_incorrect: dict[str, list[float]] = {"L": [], "R": []}
    for pair in sessions:
        a_bare = _half_accuracy_firstCorrectLickAll_per_side(pair.bare, window)
        a_b = _half_accuracy_firstCorrectLickAll_per_side(pair.b, window)
        n_bare = _half_mean_licks_per_trial_per_side(pair.bare, window)
        n_b = _half_mean_licks_per_trial_per_side(pair.b, window)
        for side in ("L", "R"):
            bare_acc[side].append(a_bare[side])
            b_acc[side].append(a_b[side])
            bare_n_correct[side].append(n_bare[side]["correct"])
            bare_n_incorrect[side].append(n_bare[side]["incorrect"])
            b_n_correct[side].append(n_b[side]["correct"])
            b_n_incorrect[side].append(n_b[side]["incorrect"])

    # ---- Compute shared y-limits (Addendum #2 Tweak 4) ----
    # Empirical per-row max across BOTH L and R panels; padded 10%.
    def _empirical_ymax(*lists: list[float]) -> float:
        flat = np.concatenate([np.asarray(L, dtype=float) for L in lists])
        if flat.size == 0:
            return 0.0
        return float(np.nanmax(flat))
    # Row 1: accuracy. Clip to [0, 1] (accuracy bounds).
    row1_max = _empirical_ymax(
        bare_acc["L"], b_acc["L"], bare_acc["R"], b_acc["R"],
    )
    row1_ylim = (0.0, min(1.0, row1_max * 1.1 + 0.05))
    # Row 2: mean CORRECT licks per trial — shared L/R.
    row2_max = _empirical_ymax(
        bare_n_correct["L"], b_n_correct["L"],
        bare_n_correct["R"], b_n_correct["R"],
    )
    row2_ylim = (0.0, max(1.0, row2_max * 1.1))
    # Row 3: mean INCORRECT licks per trial — shared L/R, INDEPENDENT
    # from Row 2 (Addendum #3 Tweak 3).
    row3_max = _empirical_ymax(
        bare_n_incorrect["L"], b_n_incorrect["L"],
        bare_n_incorrect["R"], b_n_incorrect["R"],
    )
    row3_ylim = (0.0, max(1.0, row3_max * 1.1))

    # ---- Build figure ----
    figsize = (10.0, 14.0)
    fig, axs = plt.subplots(
        nrows=4, ncols=2, figsize=figsize, squeeze=False,
    )
    panel_title_fontsize = cohort_config["panel_title_fontsize"]
    licking_xtick_fontsize = cohort_config["licking_xtick_fontsize"]
    spout_distance_xlabel_fontsize = cohort_config[
        "spout_distance_xlabel_fontsize"
    ]
    raster_xlabel_fontsize = cohort_config["raster_xlabel_fontsize"]
    raster_xlabel_labelpad = cohort_config["raster_xlabel_labelpad"]

    # Row 1: accuracy_firstCorrectLickAll
    for jj, side in enumerate(("L", "R")):
        ax = axs[0, jj]
        _plot_row_per_session_dots_and_means(
            ax, side,
            bare_vals=bare_acc[side],
            b_vals=b_acc[side],
            licking_xtick_fontsize=licking_xtick_fontsize,
        )
        ax.set_ylim(*row1_ylim)
        ax.set_title(
            f"Reward {side}: first-lick correct (all trials)",
            fontsize=panel_title_fontsize,
        )
        if jj == 0:
            ax.set_ylabel("Accuracy (first-lick correct / all trials)")

    # Row 2: mean CORRECT licks per trial
    for jj, side in enumerate(("L", "R")):
        ax = axs[1, jj]
        _plot_row_per_session_dots_and_means(
            ax, side,
            bare_vals=bare_n_correct[side],
            b_vals=b_n_correct[side],
            licking_xtick_fontsize=licking_xtick_fontsize,
        )
        ax.set_ylim(*row2_ylim)
        ax.set_title(
            f"Reward {side}: mean correct licks/trial",
            fontsize=panel_title_fontsize,
        )
        if jj == 0:
            ax.set_ylabel("Mean correct licks per trial")

    # Row 3: mean INCORRECT licks per trial (separate ylim from Row 2)
    for jj, side in enumerate(("L", "R")):
        ax = axs[2, jj]
        _plot_row_per_session_dots_and_means(
            ax, side,
            bare_vals=bare_n_incorrect[side],
            b_vals=b_n_incorrect[side],
            licking_xtick_fontsize=licking_xtick_fontsize,
        )
        ax.set_ylim(*row3_ylim)
        ax.set_title(
            f"Reward {side}: mean incorrect licks/trial",
            fontsize=panel_title_fontsize,
        )
        # Addendum #2 Tweak 1: "Spout Distance" xlabel on Row 3
        # (bottom of the licking block). Addendum #4 Tweak 3: bumped
        # fontsize from matplotlib default to spout_distance_xlabel_fontsize.
        ax.set_xlabel(
            SPOUT_DISTANCE_XAXIS_TITLE,
            fontsize=spout_distance_xlabel_fontsize,
        )
        if jj == 0:
            ax.set_ylabel("Mean incorrect licks per trial")

    # Row 4: pooled lick raster, shared y-range across L/R.
    row4_totals: dict[str, tuple[int, int]] = {}
    for side in ("L", "R"):
        n_bare_side = sum(
            len(p.bare.rewards_idx[f"Reward_{side}"]) for p in sessions
        )
        n_b_side = sum(
            len(p.b.rewards_idx[f"Reward_{side}"]) for p in sessions
        )
        row4_totals[side] = (n_bare_side, n_b_side)
    row4_max_total = max(
        row4_totals["L"][0] + row4_totals["L"][1],
        row4_totals["R"][0] + row4_totals["R"][1],
    )
    row4_ylim = (-0.5, row4_max_total + 1.5)
    for jj, side in enumerate(("L", "R")):
        ax = axs[3, jj]
        _plot_row_lick_raster(
            ax, side, sessions,
            window=window, config=config,
            cohort_config=cohort_config,
            animal_info=animal_info,
            y_range=row4_ylim,
        )
        # Addendum #4 Tweak 1: per-panel "Time (s)" xlabel
        # (replaces the prior figure-level supxlabel so labelpad
        # applies). Smaller labelpad pulls the label closer to the
        # tick labels.
        ax.set_xlabel(
            "Time (s)",
            fontsize=raster_xlabel_fontsize,
            labelpad=raster_xlabel_labelpad,
        )
        # Addendum #5 Tweak 3a: Row 4 ylabel = "Trials" (replaces
        # R3-R4's "(Standard top / Close bottom)"; the half labels
        # now sit outside the left spine).
        if jj == 0:
            ax.set_ylabel(
                "Trials",
                fontsize=cohort_config["raster_ylabel_fontsize"],
            )
    fig.suptitle(
        f"{animal}  spout close vs standard  "
        f"(n={len(sessions)} post-stroke sessions)",
        fontsize=panel_title_fontsize,
    )
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])

    # Save.
    out_dir = resolver.spout_close_vs_std_dir(animal=None)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / f"{animal}_summary.svg"
    png_path = out_dir / f"{animal}_summary.png"
    for target in (svg_path, png_path):
        if not target.exists():
            continue
        if overwrite == "raise":
            plt.close(fig)
            raise FileExistsError(
                f"spout_close_vs_std cohort target exists: {target}"
            )
        if overwrite == "skip":
            plt.close(fig)
            return svg_path, png_path
    fig.savefig(svg_path, format="svg")
    fig.savefig(png_path, format="png", dpi=300)
    plt.close(fig)
    return svg_path, png_path


__all__ = [
    "COHORT_B_REL_DAY_MIN",
    "RASTER_INTRA_HALF_BOUNDARY_KWARGS",
    "SPOUT_DISTANCE_DISPLAY_LABELS",
    "SPOUT_DISTANCE_DOT_FILL",
    "SPOUT_DISTANCE_XAXIS_TITLE",
    "SessionPairData",
    "iter_cohort_b_session_keys",
    "iter_cohort_b_sessions",
    "list_cohort_b_animals",
    "load_cohort_config",
    "render_animal_summary_spout_close_vs_std",
]

