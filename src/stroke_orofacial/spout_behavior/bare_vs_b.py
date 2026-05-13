"""Phase 8a.10 sub-deliverable B — bare-vs-b comparison.

Scope: post-stroke comparison of bare-half (single-spout) vs b-half
(secondary-spout) session conditions for the 14 Pattern B sessions
across PS51, PS54, PS55. Five endpoints (per kickoff 2026-05-13):

  1. First-lick accuracy (per-session bar + cohort recovery curve)
  2. Correct/incorrect licks per side (faceted bar + cohort curve)
  3. Lick raster (side-by-side; no cohort aggregation)
  4. First-lick latency (side-by-side distributions + cohort curve)
  5. Reward acquisition rate over time (NEW; cohort curve)

This module ships:
  - CG-B1: shared infrastructure — :class:`SessionPairData`,
    :func:`iter_cohort_b_sessions`, :func:`iter_cohort_b_session_keys`.
  - CG-B2: per-session paired-panel renderers for the 5 endpoints
    (added Priya 2026-05-13, PS55 pilot scope first).
  - CG-B3: per-animal cohort recovery curves (deferred to a later
    commit).

Endpoint 5 color palette
------------------------
The 4 endpoints that share L/R semantics reuse SIDE_COLORS
(mouse-L=dodgerblue, mouse-R=mediumvioletred). Endpoint 5 ("reward
acquisition rate over time") would conflict — its two lines split
on bare-vs-b, not L-vs-R. To avoid the visual collision, endpoint
5 uses a distinct palette: bare=black, b=tab:orange (pinned via
:data:`BARE_VS_B_LINE_COLORS`). Endpoint 5 plots cumulative rewards
combined across L/R per half (2 lines total) for the cleanest
first-cut visualization. DECISIONS-entry queued for phase wrap.

Cohort B (Pattern B) registry lives in
``configs/session_overrides.yaml`` under ``secondary_spout_sessions:``.
This module reads that registry, filters to post-stroke sessions
(:meth:`AnimalInfo.day_relative_to_stroke` ``>= 2``; cuts both d0
and d+1 — Priya 2026-05-13), and pairs each survivor's bare half
with its b half via :func:`load_session_plot_data` (extended for
this phase to accept a ``half_suffix`` kwarg).

Filter convention note: ``rel_day >= 2`` (NOT ``>= 1``). The d+1
session is the immediate stroke-aftermath day and is excluded
alongside d0. Filter intent is "strictly post first post-stroke
day". DECISIONS-entry deferred to phase wrap.

Forward-pointer to Phase 8a.10.1
--------------------------------
Endpoint 5 ("reward acquisition rate over time") currently plots
tone-cue acquisition rate, not reward-acquisition rate, due to the
deferred Tone↔Reward swap (Phase 8a.10.1). Renderer code is
faithful; underlying data is mis-labeled until 8a.10.1's re-emit.
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

# Endpoint 5 (reward acquisition rate over time) color palette.
# DISTINCT from SIDE_COLORS because endpoint 5 splits on bare/b, not
# L/R. Pinned via test_bare_vs_b_endpoint_5_color_palette.
BARE_VS_B_LINE_COLORS: dict[str, str] = {
    "bare": "black",
    "b": "tab:orange",
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
    ``ANIMALS_BARE_VS_B`` to all registered animals.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    secondary = overrides_config.get("secondary_spout_sessions", {}) or {}
    return sorted(secondary.keys())


# =====================================================================
# Commit-group B2: per-session paired-panel rendering (5 endpoints)
# =====================================================================
#
# Per-session output: bare_vs_b/<animal>/<date_str>_<endpoint>.{svg,png}
#
# Style: reuses sub-deliverable A's polish — SIDE_COLORS for L/R,
# raster_dot_alpha=0.6 + zorder + raster_xticks=[0,5] +
# xtick_fontsize=5 + raster_reward_marker_linewidth=0.5 for the lick
# raster endpoint. Endpoint 5 uses BARE_VS_B_LINE_COLORS instead of
# SIDE_COLORS to disambiguate the bare-vs-b axis from the L/R axis.


def save_bare_vs_b_figure(
    fig,
    animal: str,
    date_str: str,
    endpoint: str,
    resolver: PathResolver,
    *,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Save a bare-vs-b figure to the per-animal nested directory.

    Writes SVG + PNG at
    ``{resolver.bare_vs_b_dir(animal)}/{date_str}_{endpoint}.{svg,png}``.

    Parameters
    ----------
    endpoint : str
        Endpoint slug used in the filename — e.g.
        ``"first_lick_accuracy"``, ``"correct_incorrect_per_side"``,
        ``"lick_raster"``, ``"first_lick_latency"``,
        ``"reward_acquisition_over_time"``.
    overwrite : {"force", "skip", "raise"}
        Same semantics as :func:`save_visual_gate_figure`.
    """
    out_dir = resolver.bare_vs_b_dir(animal)
    svg_path = out_dir / f"{date_str}_{endpoint}.svg"
    png_path = out_dir / f"{date_str}_{endpoint}.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    for target in (svg_path, png_path):
        if not target.exists():
            continue
        if overwrite == "raise":
            raise FileExistsError(f"bare_vs_b target exists: {target}")
        if overwrite == "skip":
            return svg_path, png_path
    fig.savefig(svg_path, format="svg")
    fig.savefig(png_path, format="png", dpi=300)
    return svg_path, png_path


def _session_title(pair: SessionPairData) -> str:
    """Standard suptitle: animal + ISO date."""
    return f"{pair.animal}  {pair.date.isoformat()}"


def _half_accuracy_per_side(
    session: SessionPlotData,
    window_around_rewards: tuple[float, float] | list[float],
) -> dict[str, float]:
    """Mean first-lick-correct per side for one half.

    Wraps :func:`compute_first_lick_correct` +
    :func:`compute_firstLickCorrect_bySession` for the per-half case.
    None values are excluded from the mean (matches
    accuracy_firstCorrectLick semantics).
    """
    delays = compute_trial_lick_delays(session, window_around_rewards)
    flc = compute_first_lick_correct(delays)
    out: dict[str, float] = {}
    for side in ("L", "R"):
        per_reward = flc[side]
        arr = np.array(
            [np.nan if v is None else float(v) for v in per_reward.values()],
            dtype=float,
        )
        out[side] = float(np.nanmean(arr)) if arr.size > 0 else float("nan")
    return out


def render_bare_vs_b_first_lick_accuracy(
    pair: SessionPairData,
    resolver: PathResolver,
    *,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Endpoint 1: per-session first-lick accuracy, bare vs b.

    Grouped bar chart with 4 bars: bare-L, bare-R, b-L, b-R. Y-axis
    is fraction-correct ∈ [0, 1]; reuses SIDE_COLORS (mouse-L =
    dodgerblue, mouse-R = mediumvioletred). The bare-vs-b axis is
    encoded via x-position (bare on left, b on right) + a vertical
    separator.
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    window = behavior_params["window_around_rewards"]

    bare_acc = _half_accuracy_per_side(pair.bare, window)
    b_acc = _half_accuracy_per_side(pair.b, window)

    fig, ax = plt.subplots(figsize=(4, 3))
    xs = [0, 1, 2.5, 3.5]
    heights = [bare_acc["L"], bare_acc["R"], b_acc["L"], b_acc["R"]]
    colors = [
        SIDE_COLORS["L"], SIDE_COLORS["R"],
        SIDE_COLORS["L"], SIDE_COLORS["R"],
    ]
    ax.bar(xs, heights, color=colors, width=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(
        ["bare L", "bare R", "b L", "b R"],
        fontsize=config["xtick_fontsize"],
    )
    ax.axvline(1.75, color="grey", linestyle=":", linewidth=0.8)
    ax.set_ylim(*config["accuracy_y_range"])
    ax.set_ylabel("First-lick accuracy")
    ax.set_title(_session_title(pair))
    fig.tight_layout()
    paths = save_bare_vs_b_figure(
        fig, pair.animal, pair.date.strftime("%Y%m%d"),
        "first_lick_accuracy", resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def _half_lick_counts_per_side(
    session: SessionPlotData,
    window_around_rewards: tuple[float, float] | list[float],
) -> dict[str, dict[str, int]]:
    """Total post-reward lick counts split by (reward_side,
    correctness). Window comes from ``window_around_rewards`` (the
    same one used for the raster, NOT the criteria_4 tighter window).

    Returns ``{"L": {"correct": n, "incorrect": n}, "R": {...}}``.
    """
    delays = compute_trial_lick_delays(session, window_around_rewards)
    out: dict[str, dict[str, int]] = {"L": {}, "R": {}}
    for side_reward in ("L", "R"):
        n_correct = 0
        n_incorrect = 0
        for _idx, by_side in delays[f"Reward_{side_reward}"].items():
            n_correct += int(by_side[f"Lick_{side_reward}"].size)
            other = "R" if side_reward == "L" else "L"
            n_incorrect += int(by_side[f"Lick_{other}"].size)
        out[side_reward] = {"correct": n_correct, "incorrect": n_incorrect}
    return out


def render_bare_vs_b_correct_incorrect_per_side(
    pair: SessionPairData,
    resolver: PathResolver,
    *,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Endpoint 2: per-session correct/incorrect lick counts by side.

    Two sub-panels (bare on left, b on right). Each panel has 4 bars:
    L-correct, L-incorrect, R-correct, R-incorrect. Color = side
    (SIDE_COLORS); hatch differentiates correct (solid) from
    incorrect (hatched).
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    window = behavior_params["window_around_rewards"]

    bare_counts = _half_lick_counts_per_side(pair.bare, window)
    b_counts = _half_lick_counts_per_side(pair.b, window)

    fig, axs = plt.subplots(1, 2, figsize=(7, 3), sharey=True)
    for ax, counts, title in (
        (axs[0], bare_counts, "bare"),
        (axs[1], b_counts, "b"),
    ):
        xs = [0, 1, 2, 3]
        labels = ["L corr", "L incorr", "R corr", "R incorr"]
        heights = [
            counts["L"]["correct"], counts["L"]["incorrect"],
            counts["R"]["correct"], counts["R"]["incorrect"],
        ]
        colors = [
            SIDE_COLORS["L"], SIDE_COLORS["L"],
            SIDE_COLORS["R"], SIDE_COLORS["R"],
        ]
        hatches = ["", "//", "", "//"]
        bars = ax.bar(xs, heights, color=colors, edgecolor="white")
        for bar, hatch in zip(bars, hatches, strict=True):
            bar.set_hatch(hatch)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=config["xtick_fontsize"])
        ax.set_title(title)
    axs[0].set_ylabel("Lick count (within window)")
    fig.suptitle(_session_title(pair))
    fig.tight_layout()
    paths = save_bare_vs_b_figure(
        fig, pair.animal, pair.date.strftime("%Y%m%d"),
        "correct_incorrect_per_side", resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def render_bare_vs_b_lick_raster(
    pair: SessionPairData,
    resolver: PathResolver,
    *,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Endpoint 3: side-by-side per-session lick rasters.

    Layout: 2 rows × 2 cols.
      - Rows = reward side (top: Reward L; bottom: Reward R).
      - Cols = half (left: bare; right: b).
    Per-cell content matches sub-deliverable A's ``render_lick_raster``:
    dot scatter with green=correct / magenta=incorrect, alpha=0.6,
    zorder layering (incorrect on top), explicit xticks [0, 5],
    thin reward marker at x=0.
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    window = behavior_params["window_around_rewards"]

    fig, axs = plt.subplots(
        nrows=2, ncols=2,
        figsize=(5, 4),
        squeeze=False, sharex=True,
    )
    for jj, (label, session) in enumerate(
        (("bare", pair.bare), ("b", pair.b)),
    ):
        delays_full = compute_trial_lick_delays(session, window)
        for ii, side_reward in enumerate(("L", "R")):
            ax = axs[ii, jj]
            delays_by_reward = delays_full[f"Reward_{side_reward}"]
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
                    dot_zorder = (
                        config["raster_dot_correct_zorder"] if is_correct
                        else config["raster_dot_incorrect_zorder"]
                    )
                    ax.scatter(
                        lick_delays / session.sample_rate,
                        np.full_like(lick_delays, idx_reward, dtype=float),
                        s=config["raster_dot_size"],
                        color=color,
                        alpha=config["raster_dot_alpha"],
                        zorder=dot_zorder,
                    )
            n_trials = len(delays_by_reward)
            ax.plot(
                [0, 0], [0, n_trials],
                config["raster_reward_marker_color"],
                alpha=config["raster_reward_marker_alpha"],
                linewidth=config["raster_reward_marker_linewidth"],
            )
            ax.set_xlim(*config["raster_xlim"])
            ax.set_xticks(config["raster_xticks"])
            if ii == 0:
                ax.set_title(label)
            if ii == 1:
                ax.tick_params(
                    axis="x", labelsize=config["xtick_fontsize"],
                )
            if jj == 0:
                ax.set_ylabel(f"Trials (mouse {side_reward})")
            else:
                ax.set_yticklabels([])
    fig.supxlabel(
        "Time (s)", fontsize=config["raster_xlabel_fontsize"],
    )
    fig.suptitle(_session_title(pair))
    fig.tight_layout()
    paths = save_bare_vs_b_figure(
        fig, pair.animal, pair.date.strftime("%Y%m%d"),
        "lick_raster", resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def _first_lick_latencies_per_side(
    session: SessionPlotData,
    window_around_rewards: tuple[float, float] | list[float],
) -> dict[str, np.ndarray]:
    """First post-reward lick latencies per side (seconds).

    For each reward side, returns an array of first post-reward
    correct-side lick latencies (one per trial; NaN when no correct
    post-reward lick exists). Used by the latency endpoint.
    """
    delays_full = compute_trial_lick_delays(session, window_around_rewards)
    out: dict[str, np.ndarray] = {}
    for side_reward in ("L", "R"):
        latencies: list[float] = []
        for _idx, by_side in delays_full[f"Reward_{side_reward}"].items():
            correct_post = by_side[f"Lick_{side_reward}"]
            correct_post = correct_post[correct_post >= 0]
            if correct_post.size > 0:
                latencies.append(
                    float(correct_post[0]) / session.sample_rate,
                )
            else:
                latencies.append(float("nan"))
        out[side_reward] = np.array(latencies, dtype=float)
    return out


def render_bare_vs_b_first_lick_latency(
    pair: SessionPairData,
    resolver: PathResolver,
    *,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Endpoint 4: per-session first-lick latency distributions.

    Strip + box plot, x = ["bare L", "bare R", "b L", "b R"],
    y = latency (s). Color = side (SIDE_COLORS); a vertical
    separator divides bare from b.
    """
    config = config or load_visual_gate_config()
    behavior_params = behavior_params or load_behavior_report_params()
    window = behavior_params["window_around_rewards"]

    bare_lat = _first_lick_latencies_per_side(pair.bare, window)
    b_lat = _first_lick_latencies_per_side(pair.b, window)

    fig, ax = plt.subplots(figsize=(4, 3))
    positions = [0, 1, 2.5, 3.5]
    datasets = [
        bare_lat["L"], bare_lat["R"],
        b_lat["L"], b_lat["R"],
    ]
    colors = [
        SIDE_COLORS["L"], SIDE_COLORS["R"],
        SIDE_COLORS["L"], SIDE_COLORS["R"],
    ]
    for pos, data, color in zip(positions, datasets, colors, strict=True):
        finite = data[np.isfinite(data)]
        if finite.size > 0:
            # Strip plot (jittered) under a translucent box.
            jitter = 0.12 * (np.random.RandomState(42).rand(finite.size) - 0.5)
            ax.scatter(
                np.full_like(finite, pos) + jitter, finite,
                s=4, color=color, alpha=0.5, zorder=2,
            )
            ax.boxplot(
                [finite], positions=[pos], widths=0.35,
                showfliers=False, zorder=3,
                medianprops={"color": "black", "linewidth": 1.0},
                boxprops={"color": color, "linewidth": 1.0},
                whiskerprops={"color": color, "linewidth": 1.0},
                capprops={"color": color, "linewidth": 1.0},
            )
    ax.axvline(1.75, color="grey", linestyle=":", linewidth=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels(
        ["bare L", "bare R", "b L", "b R"],
        fontsize=config["xtick_fontsize"],
    )
    ax.set_ylim(0, config["latency_y_max"])
    ax.set_ylabel("First-lick latency (s)")
    ax.set_title(_session_title(pair))
    fig.tight_layout()
    paths = save_bare_vs_b_figure(
        fig, pair.animal, pair.date.strftime("%Y%m%d"),
        "first_lick_latency", resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


def _cumulative_rewards_over_time(
    session: SessionPlotData,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(t_seconds, cumulative_count)`` arrays.

    Combines L and R rewards into one cumulative count. ``t_seconds``
    starts at 0 (session start). Both arrays are step-style: each
    reward event adds a new (t, count) point. An initial (0, 0)
    point anchors the line.

    Forward-pointer to Phase 8a.10.1: ``rewards_idx`` currently
    carries TONE-cue indices (not actual rewards) due to the
    cohort-wide Tone↔Reward swap. Endpoint code is correct;
    semantic label will retroactively match data after 8a.10.1's
    re-emit.
    """
    all_rewards = np.concatenate(
        [session.rewards_idx["Reward_L"], session.rewards_idx["Reward_R"]]
    ).astype(int)
    all_rewards.sort()
    t = all_rewards / session.sample_rate
    counts = np.arange(1, t.size + 1, dtype=int)
    # Prepend (0, 0).
    t = np.concatenate([[0.0], t])
    counts = np.concatenate([[0], counts])
    return t, counts


def render_bare_vs_b_reward_acquisition_over_time(
    pair: SessionPairData,
    resolver: PathResolver,
    *,
    config: dict[str, Any] | None = None,
    behavior_params: dict[str, Any] | None = None,
    overwrite: Literal["force", "skip", "raise"] = "force",
) -> tuple[Path, Path]:
    """Endpoint 5 (NEW; no legacy precedent): cumulative rewards
    over within-session time, bare vs b overlaid.

    Layout: 1 panel, 2 lines (bare, b). Uses
    :data:`BARE_VS_B_LINE_COLORS` (bare=black, b=tab:orange) — NOT
    SIDE_COLORS, because the two lines split on bare-vs-b condition
    and the L/R distinction is collapsed (L and R rewards are summed
    per half for a cleanest first-cut visualization).

    Forward-pointer to Phase 8a.10.1
    --------------------------------
    Plots TONE-cue acquisition rate currently (cohort-wide Tone↔Reward
    swap deferred to 8a.10.1). Endpoint code is faithful; semantic
    labels will retroactively match data after 8a.10.1's re-emit.
    """
    _ = config or load_visual_gate_config()
    _ = behavior_params or load_behavior_report_params()

    t_bare, n_bare = _cumulative_rewards_over_time(pair.bare)
    t_b, n_b = _cumulative_rewards_over_time(pair.b)

    fig, ax = plt.subplots(figsize=(5, 3))
    ax.step(
        t_bare, n_bare, where="post",
        color=BARE_VS_B_LINE_COLORS["bare"], label="bare",
    )
    ax.step(
        t_b, n_b, where="post",
        color=BARE_VS_B_LINE_COLORS["b"], label="b",
    )
    ax.set_xlabel("Time within session (s)")
    ax.set_ylabel("Cumulative rewards (L+R combined)")
    ax.legend(loc="lower right")
    ax.set_title(_session_title(pair))
    fig.tight_layout()
    paths = save_bare_vs_b_figure(
        fig, pair.animal, pair.date.strftime("%Y%m%d"),
        "reward_acquisition_over_time", resolver, overwrite=overwrite,
    )
    plt.close(fig)
    return paths


# Convenience: list of (endpoint_slug, render_fn) pairs so the
# orchestrator can iterate cleanly.
PER_SESSION_RENDERERS: list[tuple[str, Any]] = [
    ("first_lick_accuracy", render_bare_vs_b_first_lick_accuracy),
    ("correct_incorrect_per_side",
     render_bare_vs_b_correct_incorrect_per_side),
    ("lick_raster", render_bare_vs_b_lick_raster),
    ("first_lick_latency", render_bare_vs_b_first_lick_latency),
    ("reward_acquisition_over_time",
     render_bare_vs_b_reward_acquisition_over_time),
]


__all__ = [
    "BARE_VS_B_LINE_COLORS",
    "COHORT_B_REL_DAY_MIN",
    "PER_SESSION_RENDERERS",
    "SessionPairData",
    "iter_cohort_b_session_keys",
    "iter_cohort_b_sessions",
    "list_cohort_b_animals",
    "render_bare_vs_b_correct_incorrect_per_side",
    "render_bare_vs_b_first_lick_accuracy",
    "render_bare_vs_b_first_lick_latency",
    "render_bare_vs_b_lick_raster",
    "render_bare_vs_b_reward_acquisition_over_time",
    "save_bare_vs_b_figure",
]
