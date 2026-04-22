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
