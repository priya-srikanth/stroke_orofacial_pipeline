"""Recovery-trajectory data assembly and plotting for Phase 8a.8.

Consumes Phase 8a per-session ``spout_endpoints.json`` payloads and builds
stroke-relative per-animal / cohort trajectories. The module is intentionally
small and side-effect-light:

- JSON loading and metric extraction are pure helpers.
- Cohort summaries are deterministic Python data structures.
- Plotting returns a Matplotlib ``Figure``; callers choose whether/where to save.

Phenotype classification is out of scope for Phase 8a.8. The only phenotype
surface here is a grouping hook: callers may map ``animal -> group`` for
visualization, with the default mapping placing every animal in one ``"all"``
group. Phase 9.1 can later pass real phenotype labels without changing this
plotting layer.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GroupFn = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    """One scalar endpoint value for one animal/session."""

    animal: str
    date: _dt.date
    day_relative_to_stroke: int
    endpoint_name: str
    metric_path: str
    value: float
    group: str = "all"
    n_trials: int | None = None


@dataclass(frozen=True, slots=True)
class CohortSummaryPoint:
    """Mean/SEM summary for one group and stroke-relative day."""

    group: str
    day_relative_to_stroke: int
    mean: float
    sem: float
    n: int


def load_endpoint_payload(path: Path | str) -> dict[str, Any]:
    """Load one ``spout_endpoints.json`` payload."""
    return json.loads(Path(path).read_text())


def discover_endpoint_jsons(
    endpoints_root: Path | str,
    *,
    animals: Sequence[str] | None = None,
) -> list[Path]:
    """Return sorted per-session endpoint JSON paths from an endpoints root.

    Parameters
    ----------
    endpoints_root : Path or str
        Directory shaped like ``spout_behavior/endpoints/{ANIMAL}/{YYYYMMDD}.json``.
    animals : sequence of str, optional
        Restrict discovery to these animals. When omitted, all animal
        subdirectories under ``endpoints_root`` are searched.
    """
    root = Path(endpoints_root)
    if animals is None:
        animal_dirs = [p for p in root.iterdir() if p.is_dir()] if root.exists() else []
    else:
        animal_dirs = [root / animal for animal in animals]
    paths: list[Path] = []
    for animal_dir in animal_dirs:
        if animal_dir.exists():
            paths.extend(animal_dir.glob("*.json"))
    return sorted(paths, key=lambda p: (p.parent.name, p.stem))


def _parse_date(value: str) -> _dt.date:
    """Parse ISO ``YYYY-MM-DD`` or compact ``YYYYMMDD`` session dates."""
    clean = value.replace("-", "")
    return _dt.datetime.strptime(clean, "%Y%m%d").date()


def _is_sentinel(value: Any) -> bool:
    """Return True for explicit sentinel dicts emitted by the writer."""
    return isinstance(value, dict) and "status" in value and "per_session_aggregate" not in value


def value_at_path(payload: dict[str, Any], dotted_path: str) -> Any:
    """Read a nested value from a dict using a dot-separated path.

    Example: ``value_at_path(endpoint, "per_session_aggregate.mean_s")``.
    Integer path components index into lists/tuples.
    """
    current: Any = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, (list, tuple)):
            current = current[int(part)]
        else:
            raise KeyError(
                f"Cannot descend into {type(current).__name__} at component {part!r} "
                f"of path {dotted_path!r}"
            )
    return current


def _coerce_scalar(value: Any) -> float:
    """Coerce JSON scalar-ish values to float, preserving missing as NaN."""
    if hasattr(value, "item") and callable(value.item):
        value = value.item()
    if value is None:
        return float("nan")
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"Metric value must be scalar numeric/bool/None, got {type(value).__name__}")


def extract_endpoint_metric(
    payload: dict[str, Any],
    endpoint_name: str,
    metric_path: str,
) -> float:
    """Extract one scalar metric from a per-session endpoint JSON payload.

    Sentinel endpoint slots, such as ``inter_session_persistence`` in the
    per-session writer, return NaN.
    """
    endpoint = payload["endpoints"][endpoint_name]
    if _is_sentinel(endpoint):
        return float("nan")
    return _coerce_scalar(value_at_path(endpoint, metric_path))


def build_trajectory_points(
    payloads: Iterable[dict[str, Any]],
    *,
    endpoint_name: str,
    metric_path: str,
    grouping_function: GroupFn | None = None,
    include_nan: bool = False,
) -> list[TrajectoryPoint]:
    """Build scalar trajectory points from endpoint JSON payloads.

    Parameters
    ----------
    payloads : iterable of dict
        Loaded ``spout_endpoints.json`` payloads.
    endpoint_name : str
        Key inside the payload's ``endpoints`` block.
    metric_path : str
        Dot path inside that endpoint value, e.g.
        ``"per_session_aggregate.mean_s"`` or ``"per_session_aggregate.L"``.
    grouping_function : callable, optional
        Maps animal ID to a visualization group. Defaults to ``"all"``.
    include_nan : bool, default False
        Keep points whose extracted value is NaN. Defaults to dropping them so
        cohort summaries and plots are based on observed values only.
    """
    group_of = grouping_function or (lambda _animal: "all")
    points: list[TrajectoryPoint] = []
    for payload in payloads:
        metadata = payload["metadata"]
        animal = str(metadata["animal"])
        date = _parse_date(str(metadata["date"]))
        day = metadata.get("day_relative_to_stroke")
        if day is None:
            continue
        value = extract_endpoint_metric(payload, endpoint_name, metric_path)
        if not include_nan and math.isnan(value):
            continue
        points.append(
            TrajectoryPoint(
                animal=animal,
                date=date,
                day_relative_to_stroke=int(day),
                endpoint_name=endpoint_name,
                metric_path=metric_path,
                value=value,
                group=str(group_of(animal)),
                n_trials=metadata.get("n_trials"),
            )
        )
    return sorted(points, key=lambda p: (p.group, p.animal, p.day_relative_to_stroke, p.date))


def build_trajectory_points_from_paths(
    paths: Iterable[Path | str],
    *,
    endpoint_name: str,
    metric_path: str,
    grouping_function: GroupFn | None = None,
    include_nan: bool = False,
) -> list[TrajectoryPoint]:
    """Load endpoint JSONs from disk and build trajectory points."""
    payloads = [load_endpoint_payload(path) for path in paths]
    return build_trajectory_points(
        payloads,
        endpoint_name=endpoint_name,
        metric_path=metric_path,
        grouping_function=grouping_function,
        include_nan=include_nan,
    )


def summarize_cohort(points: Sequence[TrajectoryPoint]) -> list[CohortSummaryPoint]:
    """Compute mean and SEM by ``(group, day_relative_to_stroke)``."""
    buckets: dict[tuple[str, int], list[float]] = defaultdict(list)
    for point in points:
        if not math.isnan(point.value):
            buckets[(point.group, point.day_relative_to_stroke)].append(point.value)

    out: list[CohortSummaryPoint] = []
    for (group, day), values in sorted(buckets.items()):
        n = len(values)
        mean = float(statistics.fmean(values)) if n else float("nan")
        sem = float(statistics.stdev(values) / math.sqrt(n)) if n > 1 else 0.0
        out.append(
            CohortSummaryPoint(
                group=group,
                day_relative_to_stroke=day,
                mean=mean,
                sem=sem,
                n=n,
            )
        )
    return out


def plot_recovery_trajectories(
    points: Sequence[TrajectoryPoint],
    *,
    title: str | None = None,
    ylabel: str | None = None,
    show_individual: bool = True,
    stroke_boundary_x: float | None = 0.5,
):
    """Plot per-animal trajectories plus cohort mean +/- SEM.

    Returns
    -------
    matplotlib.figure.Figure
        Caller owns saving/closing the figure.
    """
    if not points:
        raise ValueError("No trajectory points to plot.")

    # Local import keeps JSON/data-assembly users from importing Matplotlib.
    import matplotlib.pyplot as plt

    groups = sorted({p.group for p in points})
    fig_width = max(4.5, 4.2 * len(groups))
    fig, axes = plt.subplots(
        1, len(groups), figsize=(fig_width, 3.6), squeeze=False, sharey=True
    )
    summary = summarize_cohort(points)

    for ax, group in zip(axes[0], groups, strict=True):
        group_points = [p for p in points if p.group == group]
        by_animal: dict[str, list[TrajectoryPoint]] = defaultdict(list)
        for point in group_points:
            by_animal[point.animal].append(point)

        if show_individual:
            for animal, animal_points in sorted(by_animal.items()):
                xs = [p.day_relative_to_stroke for p in animal_points]
                ys = [p.value for p in animal_points]
                ax.plot(xs, ys, marker="o", linewidth=1.0, alpha=0.35, label=animal)

        group_summary = [s for s in summary if s.group == group]
        xs = [s.day_relative_to_stroke for s in group_summary]
        means = [s.mean for s in group_summary]
        lower = [s.mean - s.sem for s in group_summary]
        upper = [s.mean + s.sem for s in group_summary]
        ax.plot(xs, means, color="black", marker="o", linewidth=2.0, label="mean")
        ax.fill_between(xs, lower, upper, color="black", alpha=0.14)

        if stroke_boundary_x is not None:
            ax.axvline(stroke_boundary_x, color="crimson", linestyle="--", linewidth=1.0)
        ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
        ax.set_title(group)
        ax.set_xlabel("Day relative to stroke")
        ax.grid(True, axis="y", color="0.9", linewidth=0.8)

    axes[0][0].set_ylabel(ylabel or points[0].metric_path)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    return fig


def save_trajectory_figure(fig: Any, output_path: Path | str, *, dpi: int = 200) -> Path:
    """Save a trajectory figure, creating parent directories."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path


def _bootstrap_post_stroke_slope_band(
    points: Sequence[TrajectoryPoint],
    *,
    n_boot: int = 500,
    ci: float = 0.95,
    rng_seed: int = 0,
) -> tuple[list[int], list[float], list[float]] | None:
    """Bootstrap a per-rel_day CI ribbon for the post-stroke slope fit.

    Resamples ANIMALS with replacement (preserves per-session correlation
    structure within each animal), refits a simple OLS line per resample
    on the resampled animals' post-stroke points, and returns the
    pointwise 2.5%/97.5% percentiles of the predicted line for each unique
    rel_day > 0 in the input.

    Returns ``(xs, lower, upper)`` or ``None`` if fewer than 3 animals
    have post-stroke points (insufficient for a meaningful bootstrap).
    """
    import numpy as np

    by_animal: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for p in points:
        if p.day_relative_to_stroke > 0 and not math.isnan(p.value):
            by_animal[p.animal].append((p.day_relative_to_stroke, p.value))
    animals = sorted(a for a, vs in by_animal.items() if len(vs) >= 2)
    if len(animals) < 3:
        return None
    rel_days = sorted({rd for vs in by_animal.values() for rd, _ in vs})
    if not rel_days:
        return None

    rng = np.random.default_rng(rng_seed)
    # Stack each bootstrap fit's predicted line into a [n_boot, len(rel_days)] array.
    preds = np.empty((n_boot, len(rel_days)))
    preds.fill(np.nan)
    for i in range(n_boot):
        sampled_animals = rng.choice(animals, size=len(animals), replace=True)
        xs: list[int] = []
        ys: list[float] = []
        for a in sampled_animals:
            for rd, v in by_animal[a]:
                xs.append(rd)
                ys.append(v)
        if len(xs) < 3:
            continue
        x_arr = np.asarray(xs, dtype=float)
        y_arr = np.asarray(ys, dtype=float)
        # OLS slope + intercept; degenerate if x has no variance.
        x_mean = x_arr.mean()
        x_var = ((x_arr - x_mean) ** 2).sum()
        if x_var <= 0:
            continue
        slope = ((x_arr - x_mean) * (y_arr - y_arr.mean())).sum() / x_var
        intercept = y_arr.mean() - slope * x_mean
        preds[i] = intercept + slope * np.asarray(rel_days, dtype=float)

    alpha = 1.0 - ci
    lower = np.nanpercentile(preds, 100 * alpha / 2.0, axis=0).tolist()
    upper = np.nanpercentile(preds, 100 * (1.0 - alpha / 2.0), axis=0).tolist()
    return rel_days, lower, upper


def plot_recovery_trajectories_with_fit(
    points: Sequence[TrajectoryPoint],
    fit_result: Any,
    *,
    ax: Any | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    show_individual: bool = True,
    show_cohort_mean: bool = True,
    stroke_boundary_x: float | None = 0.5,
    ci: float = 0.95,
    n_boot: int = 500,
    rng_seed: int = 0,
    cohort_points: Sequence[TrajectoryPoint] | None = None,
):
    """Overlay a FitResult-driven recovery fit on scatter + mean/SEM trajectories.

    Phase 9 Task 6 wire-up — overlays the predicted recovery line +
    bootstrap CI ribbon (per Addendum #6 Option C: stats fit on raw
    values per Addendum #9; figure-render normalization is the
    caller's choice via the y-axis label, NOT applied here).

    The fit line uses ``fit_result.details["slope"]`` and
    ``fit_result.details["intercept"]`` (set by
    :func:`stroke_orofacial.stats.models.fit_recovery_mixedlm`). The CI
    ribbon is computed via per-animal bootstrap resampling (refits a
    simple OLS line per resample; faster + more visualizable than a
    full LMM bootstrap).

    Parameters
    ----------
    points : Sequence[TrajectoryPoint]
        Per-animal scatter + cohort summary data.
    fit_result : FitResult
        From :func:`fit_recovery_mixedlm`. Must carry ``details["slope"]``
        and ``details["intercept"]``; otherwise the function falls back
        to plotting scatter + mean/SEM only (no fit overlay).
    ax : matplotlib Axes, optional
        Render into an existing axes. If None, a new Figure + Axes are
        created.
    title, ylabel, show_individual, show_cohort_mean,
    stroke_boundary_x : visual config (mirrors
        :func:`plot_recovery_trajectories`).
    ci : float, default 0.95
        Bootstrap CI level. Pass 0.0 to skip the ribbon.
    n_boot : int, default 500
    rng_seed : int, default 0
    cohort_points : Sequence[TrajectoryPoint], optional
        Points used for the bootstrap CI ribbon computation. When the
        ``points`` argument contains data for a single animal (per-mouse
        visual-gate panels) the bootstrap is degenerate; pass cohort-
        wide points here to get a meaningful CI ribbon while
        ``points`` drives the scatter + per-animal mean/SEM. Defaults
        to ``points`` if not provided.

    Returns
    -------
    matplotlib.figure.Figure
        Caller owns saving/closing.
    """
    if not points:
        raise ValueError("No trajectory points to plot.")
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(5.5, 3.6))
    else:
        fig = ax.figure

    # 1. Per-animal scatter (faint).
    if show_individual:
        by_animal: dict[str, list[TrajectoryPoint]] = defaultdict(list)
        for p in points:
            by_animal[p.animal].append(p)
        for animal in sorted(by_animal):
            xs = [p.day_relative_to_stroke for p in by_animal[animal]]
            ys = [p.value for p in by_animal[animal]]
            ax.plot(
                xs, ys, marker="o", linewidth=0.8, alpha=0.25,
                label=animal if len(by_animal) <= 10 else None,
            )

    # 2. Cohort mean + SEM band (all groups pooled — this is a per-
    # animal visual_gate panel, not phenotype-stratified).
    if show_cohort_mean:
        summary = summarize_cohort(points)
        # Pool across whatever group keys exist (visual_gate consumer
        # passes points without grouping_function, so all rows are
        # group="all").
        s_xs = [s.day_relative_to_stroke for s in summary]
        means = [s.mean for s in summary]
        lower_sem = [s.mean - s.sem for s in summary]
        upper_sem = [s.mean + s.sem for s in summary]
        ax.plot(s_xs, means, color="black", marker="o", linewidth=1.6, label="mean")
        ax.fill_between(s_xs, lower_sem, upper_sem, color="black", alpha=0.12)

    # 3. Fit overlay (recovery_mixedlm: slope + intercept on post-stroke days).
    fit_drawn = False
    if fit_result is not None:
        details = getattr(fit_result, "details", {}) or {}
        slope = details.get("slope")
        intercept = details.get("intercept")
        if slope is not None and intercept is not None and not (
            math.isnan(slope) or math.isnan(intercept)
        ):
            post_rel_days = [
                p.day_relative_to_stroke for p in points
                if p.day_relative_to_stroke > 0
            ]
            if post_rel_days:
                x_min = max(1, min(post_rel_days))
                x_max = max(post_rel_days)
                xs_fit = list(range(x_min, x_max + 1))
                ys_fit = [intercept + slope * x for x in xs_fit]
                ax.plot(
                    xs_fit, ys_fit, color="C3", linewidth=2.0,
                    label=f"LMM fit (slope={slope:.3g})",
                )
                # 4. Bootstrap CI ribbon — uses cohort_points if provided,
                # otherwise the same points used for scatter. Clip x-range
                # to the per-animal `points` post-stroke range so the
                # ribbon doesn't extend past the panel's visible data.
                if ci > 0:
                    band = _bootstrap_post_stroke_slope_band(
                        cohort_points if cohort_points is not None else points,
                        n_boot=n_boot, ci=ci, rng_seed=rng_seed,
                    )
                    if band is not None:
                        b_xs, b_lo, b_hi = band
                        # Clip to per-animal x-range.
                        clipped = [
                            (x, lo, hi) for x, lo, hi in zip(b_xs, b_lo, b_hi)
                            if x_min <= x <= x_max
                        ]
                        if clipped:
                            c_xs = [c[0] for c in clipped]
                            c_lo = [c[1] for c in clipped]
                            c_hi = [c[2] for c in clipped]
                            ax.fill_between(
                                c_xs, c_lo, c_hi, color="C3", alpha=0.18,
                                label=f"{int(ci*100)}% bootstrap CI",
                            )
                fit_drawn = True

    if stroke_boundary_x is not None:
        ax.axvline(stroke_boundary_x, color="crimson", linestyle="--", linewidth=1.0)
    ax.axhline(0, color="0.85", linewidth=0.8, zorder=0)
    ax.set_xlabel("Day relative to stroke")
    ax.set_ylabel(ylabel or (points[0].metric_path if points else "value"))
    if title:
        ax.set_title(title)
    if not fit_drawn and fit_result is not None:
        # Still annotate so the consumer knows the fit was attempted
        # but didn't produce a usable line.
        status = (fit_result.details or {}).get("status", "no_fit")
        ax.text(
            0.02, 0.95, f"[fit status: {status}]",
            transform=ax.transAxes, fontsize=8, color="0.5",
            verticalalignment="top",
        )
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    fig.tight_layout()
    return fig
