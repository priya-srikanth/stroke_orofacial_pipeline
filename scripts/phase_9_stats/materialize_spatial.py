"""Phase 9 Task 2 (Commit C) — Spatial stats inputs materializer.

Per Addenda #1/#2/#3/#5: 12 spatial endpoints (4 family entries × 3
metrics) materialized at three temporal granularities (per_session /
per_bin / per_epoch). One parquet per (animal, endpoint_slug); each
parquet contains rows for all three granularities.

Family entries (4):

- ``tongue_spout_midpoint``   — tongue centered on spout_midpoint
- ``jaw_eye_midpoint``        — jaw centered on eye_midpoint
- ``nose_eye_midpoint``       — nose centered on eye_midpoint
- ``whiskers_eye_midpoint``   — 6 whisker bodyparts SUMMED, centered on eye_midpoint

Whiskers multi-bodypart aggregation (Commit C audit finding 2026-05-23):
the existing 7c.2 rendering iterates 6 whisker bps and emits one PANEL
per bp (see ``_compute_composite_panels``). The Phase 9 inventory
treats ``spatial_*_whiskers_eye_midpoint`` as ONE endpoint per metric,
so the materializer SUMS the 6 per-bp histograms BEFORE computing the
metric — yielding a single "whisker tip ensemble" scalar per (animal,
granularity, anchor).

Metrics (3):

- ``wasserstein`` — Wasserstein-2 (POT ``ot.emd2`` with squared-Euclidean
  cost on grid centers; normalized to ``[0, 1]`` via division by C.max()).
  HEADLINE per Addendum #3.
- ``uot_cost`` — Unbalanced OT cost via ``ot.unbalanced.sinkhorn_unbalanced``
  with the Phase 7c.2 ``_compute_unbalanced_ot_plan`` parameters
  (``reg=0.02``, ``reg_m=10.0``, ``stopThr=1e-6``, ``numItermax=500``).
  Cost scalar = ``(G * C).sum()`` (transport plan G dotted with cost
  matrix C — matches what ``ot.unbalanced.sinkhorn_unbalanced2`` would
  return).
- ``js_divergence`` — Jensen-Shannon divergence via
  ``scipy.spatial.distance.jensenshannon`` on flattened histograms.

Schema (15 columns = 11 standard + 4 spatial per Addendum #5 (C)):

  animal, date, rel_day, trial_idx, side, ipsi_contra, endpoint_slug,
  value, is_sentinel, cohort_bin_size, epoch_label,
  granularity, rel_day_anchor, n_sessions_aggregated, n_frames_aggregated

For spatial endpoints:
- ``trial_idx``: null (no trial granularity)
- ``side``: ``"global"`` (2D histograms are not side-keyed at the
  family-entry level)
- ``ipsi_contra``: ``"global"``
- ``date``: for ``per_session`` = the session date; for ``per_bin`` /
  ``per_epoch`` = the earliest date in the group (lexically sortable)
- ``epoch_label``: per row, derived from ``rel_day_anchor`` via
  ``assign_epoch_label`` (per_session/per_bin); for per_epoch it's the
  epoch label itself

Run:

  conda run -n stroke_orofacial python scripts/phase_9_stats/materialize_spatial.py

Estimated wall time: ~6-10 hours full cohort per Addendum #5 (H).
Parallel-safe across (animal, family). Use ``--animals`` /
``--families`` flags for partial runs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allow `python scripts/phase_9_stats/materialize_spatial.py` direct invocation
# (project root is NOT on sys.path by default when invoking a script directly).
# Pytest already adds it via conftest discovery; only the CLI path needs help.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy.spatial.distance as spd  # noqa: E402

import ot  # noqa: E402
from ot import unbalanced as ot_unb  # noqa: E402

from stroke_orofacial.animals import AnimalInfo, load_animals  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402

from stroke_orofacial.dlc_spatial.render_on_demand import (  # noqa: E402
    TASK5_TONE_WINDOW_MS,
    _resolve_family_entry,
    _split_pre_post_dates,
    compute_animal_aggregated_histogram,
)
from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    iter_cohort_a_sessions,
)

from scripts.phase_9_stats.materialize_inputs import (  # noqa: E402
    DEFAULT_INVENTORY_PATH,
    load_inventory,
)


# UOT regularization parameters — match Phase 7c.2's existing
# _compute_unbalanced_ot_plan (render_on_demand.py:2839-2844) so spatial
# scalar values are commensurate with the 7c.2 figure tree.
_OT_REG: float = 0.02              # entropic regularization
_OT_REG_M: float = 10.0            # marginal mass relaxation penalty
_OT_NUMITERMAX: int = 500
_OT_STOPTHR: float = 1e-6
_OT_MIN_MASS: float = 1e-4         # threshold below which marginal treated as zero
_OT_EPS: float = 1e-8              # floor on marginals to stabilize sinkhorn

# Wasserstein numItermax — bumped from POT default 100k after benchmark
# showed convergence warnings at the larger n_bins. Cohort emit needs
# robust convergence.
_W_NUMITERMAX: int = 1_000_000

# Histogram resolution — matches compute_animal_aggregated_histogram's
# default_nbins=80 (configs/defaults.yaml dlc_spatial_tone_aligned).
# The 7c.2 figure tree renders at this resolution, so spatial scalars
# computed here are comparable. Wall-time tradeoff: ~4-7s per metric
# call at 80×80 vs ~200ms at 40×40 (per `_benchmark_ot.py`).
_DEFAULT_NBINS: int | None = None  # None = use config default (80×80)


_SPATIAL_PARQUET_COLUMNS: tuple[str, ...] = (
    "animal", "date", "rel_day", "trial_idx", "side", "ipsi_contra",
    "endpoint_slug", "value", "is_sentinel", "cohort_bin_size", "epoch_label",
    # 4 Addendum #5 (C) additions:
    "granularity", "rel_day_anchor", "n_sessions_aggregated",
    "n_frames_aggregated",
)


_MANIFEST_COLUMNS: tuple[str, ...] = (
    "endpoint_slug", "animal", "status", "n_rows", "n_sentinel",
    "output_path", "wall_time_s",
)


# Family entries handled by Commit C. Maps to inventory slug suffixes.
_FAMILY_ENTRIES: tuple[str, ...] = (
    "tongue_spout_midpoint",
    "jaw_eye_midpoint",
    "nose_eye_midpoint",
    "whiskers_eye_midpoint",
)


# Metrics × inventory slug prefix.
_METRICS: tuple[tuple[str, str], ...] = (
    ("wasserstein", "spatial_wasserstein"),
    ("uot_cost", "spatial_uot_cost"),
    ("js_divergence", "spatial_js_divergence"),
)


# ===========================================================================
# Histogram aggregation (per-family, multi-bodypart-aware)
# ===========================================================================


@dataclass
class _AggregatedHistogram:
    """Single aggregated 2D histogram for one (date-group, family) pair."""
    H: np.ndarray                # 2D counts; same shape across all of an animal-family
    extent: list[float]          # [xmin, xmax, ymin, ymax]
    n_sessions: int              # contributing sessions (after upstream filtering)
    n_frames: int                # sum of per-session window-frame counts


def _aggregate_family_hist(
    animal: str,
    dates: list[dt.date],
    bodyparts: list[str],
    center_mode: str,
    resolver: PathResolver,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> _AggregatedHistogram | None:
    """Aggregate the per-bp histograms into ONE family-level histogram.

    For non-whisker families (single bp) this is a passthrough. For
    ``whiskers_eye_midpoint`` (6 whisker bps) the per-bp histograms are
    SUMMED into one composite — matching the "whisker tip ensemble"
    interpretation per Commit C audit finding.

    Returns None when every contributing per-bp call yields None (no
    sessions / all dropped by upstream filter).
    """
    H_total: np.ndarray | None = None
    extent: list[float] | None = None
    n_sessions_max = 0     # max across bps (every bp is over the same dates)
    n_frames_total = 0
    for bp in bodyparts:
        H_bp, ext, n_sess, _n_tones, n_frames = compute_animal_aggregated_histogram(
            animal, dates, bp, center_mode, resolver,
            trial_group="all", window_ms=TASK5_TONE_WINDOW_MS,
            defaults=defaults, animal_info=animal_info,
            nbins_override=_DEFAULT_NBINS,
        )
        if H_bp is None:
            continue
        if H_total is None:
            H_total = H_bp.astype(float, copy=True)
            extent = list(ext)  # type: ignore[arg-type]
        else:
            # Same shape guaranteed by the shared (extent, nbins) config.
            H_total = H_total + H_bp.astype(float)
        n_sessions_max = max(n_sessions_max, int(n_sess))
        n_frames_total += int(n_frames)
    if H_total is None:
        return None
    return _AggregatedHistogram(
        H=H_total,
        extent=extent,  # type: ignore[arg-type]
        n_sessions=int(n_sessions_max),
        n_frames=int(n_frames_total),
    )


# ===========================================================================
# Metric kernels (operate on already-aggregated H_pre, H_post)
# ===========================================================================


def _build_cost_matrix(extent: list[float], nx: int, ny: int) -> np.ndarray:
    """Squared-Euclidean cost matrix on bin centers, normalized to [0, 1]
    via division by C.max(). Matches the 7c.2 ``_compute_unbalanced_ot_plan``
    convention (line 2922-2923) so cross-metric / cross-bin comparability
    is preserved with the existing UOT figure tree.
    """
    dx = (extent[1] - extent[0]) / nx
    dy = (extent[3] - extent[2]) / ny
    xs = np.linspace(extent[0] + dx / 2, extent[1] - dx / 2, nx)
    ys = np.linspace(extent[2] + dy / 2, extent[3] - dy / 2, ny)
    Xg, Yg = np.meshgrid(xs, ys, indexing="ij")
    coords = np.column_stack([Xg.ravel(), Yg.ravel()])
    # 7c.2 uses metric="euclidean"; for Wasserstein-2 we use sqeuclidean.
    # Both are valid OT cost choices; sqeuclidean is the canonical
    # Wasserstein-2 cost. UOT just sums G*C, so it's robust to either.
    # We use sqeuclidean for both; normalize to [0, 1] so reg/reg_m values
    # are comparable to 7c.2's (which used euclidean — there's a small
    # numerical offset, documented in the Commit C close report).
    C = ot.dist(coords, coords, metric="sqeuclidean")
    return C / max(C.max(), 1e-9)


def _normalize_marginals(
    H_pre: np.ndarray, H_post: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Proportion-normalize both histograms (each sums to 1). Returns
    None when both marginals are essentially empty per the 7c.2
    convention (sum ≤ _OT_MIN_MASS)."""
    a = H_pre.astype(float).ravel()
    b = H_post.astype(float).ravel()
    a[a < 0] = 0.0
    b[b < 0] = 0.0
    sum_a, sum_b = float(a.sum()), float(b.sum())
    if sum_a <= _OT_MIN_MASS or sum_b <= _OT_MIN_MASS:
        return None
    return a / sum_a, b / sum_b


def _clip_eps(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Clip both marginals to a small floor + renormalize. Mirrors the
    7c.2 stabilization pattern (render_on_demand.py:2907-2913)."""
    a = np.clip(a, _OT_EPS, None)
    b = np.clip(b, _OT_EPS, None)
    a = a / a.sum()
    b = b / b.sum()
    return a, b


def _metric_wasserstein(
    H_pre: np.ndarray, H_post: np.ndarray, C: np.ndarray,
) -> float | None:
    """Wasserstein-2 distance via ``ot.emd2``. Returns None if marginals
    are empty.
    """
    marg = _normalize_marginals(H_pre, H_post)
    if marg is None:
        return None
    a, b = _clip_eps(*marg)
    try:
        return float(ot.emd2(a, b, C, numItermax=_W_NUMITERMAX))
    except Exception:
        return None


def _metric_uot_cost(
    H_pre: np.ndarray, H_post: np.ndarray, C: np.ndarray,
) -> float | None:
    """Unbalanced OT cost = ``(G * C).sum()`` where G is the
    sinkhorn_unbalanced transport plan with 7c.2 reg/reg_m params.
    Returns None on marginal-empty / sinkhorn-divergence.
    """
    marg = _normalize_marginals(H_pre, H_post)
    if marg is None:
        return None
    a, b = _clip_eps(*marg)
    try:
        G = ot_unb.sinkhorn_unbalanced(
            a, b, C,
            reg=_OT_REG, reg_m=_OT_REG_M,
            stopThr=_OT_STOPTHR, numItermax=_OT_NUMITERMAX,
            verbose=False,
        )
    except Exception:
        return None
    return float((G * C).sum())


def _metric_js_divergence(
    H_pre: np.ndarray, H_post: np.ndarray, C: np.ndarray | None = None,
) -> float | None:
    """Jensen-Shannon divergence via ``scipy.spatial.distance.jensenshannon``.
    Returns the JS distance (not squared), bounded in ``[0, sqrt(ln 2)]``.
    """
    marg = _normalize_marginals(H_pre, H_post)
    if marg is None:
        return None
    a, b = marg
    js = float(spd.jensenshannon(a, b))
    if not np.isfinite(js):
        return None
    return js


_METRIC_FNS = {
    "wasserstein": _metric_wasserstein,
    "uot_cost": _metric_uot_cost,
    "js_divergence": _metric_js_divergence,
}


# ===========================================================================
# Granularity grouping
# ===========================================================================


def _bin_groups(
    post_dates_rel: dict[dt.date, int],
    bin_days: int,
) -> dict[int, list[dt.date]]:
    """Group post-stroke dates into bins of width ``bin_days`` anchored
    on rel_day = 0.

    Bin k covers ``rel_day in [k*bin_days + 1, (k+1)*bin_days]``. Bin
    midpoint = ``k * bin_days + (bin_days + 1) // 2``.

    Returns ``{bin_midpoint_rel_day: [date1, date2, ...]}`` sorted by
    midpoint.
    """
    groups: dict[int, list[dt.date]] = defaultdict(list)
    for d, rel in post_dates_rel.items():
        bin_idx = (rel - 1) // bin_days
        bin_mid = bin_idx * bin_days + (bin_days + 1) // 2
        groups[bin_mid].append(d)
    return {k: sorted(groups[k]) for k in sorted(groups)}


# Note: Addendum #5's _epoch_groups helper (grouping post-stroke dates
# into {acute, sub_acute, chronic} buckets at materialize-time) was
# REMOVED per Addendum #6 (C). per_epoch is no longer an emit-time
# granularity; it's a Task 4 runtime view (filter per_session rows by
# epoch_label + additive baseline normalization). The bare epoch label
# is computed per-row via assign_epoch_label inside the per_session
# emit loops below.


# ===========================================================================
# Per-animal-family driver
# ===========================================================================


def _emit_one_family_for_animal(
    *,
    animal: str,
    animal_info: AnimalInfo,
    family_entry: str,
    resolver: PathResolver,
    defaults: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Emit rows for one (animal, family) tuple across all 3 metrics.

    Per Addendum #6 (revised from #5): emit two granularities only.
    - ``per_session`` for ALL sessions (pre + post). Pre-stroke values
      come from leave-one-out: each pre-stroke session's metric is
      computed vs the pre-pool MINUS that session, yielding the
      noise-floor distribution of the metric under pre-stroke
      variability alone. Post-stroke values are computed vs the FULL
      pre-pool.
    - ``per_bin`` for post-stroke bins only (per ``AnimalInfo.bin_days``;
      anchored on rel_day=0). Bin histograms are summed from the
      already-computed per-session post-stroke histograms.

    ``per_epoch`` is a Task 4 runtime view (filter per_session rows by
    ``epoch_label`` + additive baseline normalization); no per_epoch
    emit at materialization time.

    Returns ``(rows_by_metric_slug, telemetry)``.
    """
    t0 = time.monotonic()
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    # Enumerate all dates in the animal's session range; let
    # compute_animal_aggregated_histogram silently drop missing parquets.
    all_dates_str = iter_cohort_a_sessions(
        animal, resolver, require_on_disk=False,
    )
    all_dates = [
        dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        for s in all_dates_str
    ]
    pre_dates, post_dates = _split_pre_post_dates(all_dates, animal_info)

    # Build per-pre-date histograms one at a time so we can construct
    # both the full pre-pool (their sum) AND leave-one-out per-session
    # baselines (pre_pool − H_d). Per Addendum #6 (D) compute cost
    # ~50ms × N_pre × N_bp; small relative to per-post-session compute.
    H_per_pre_date: dict[dt.date, _AggregatedHistogram] = {}
    for d in pre_dates:
        agg = _aggregate_family_hist(
            animal, [d], bodyparts, center_mode, resolver, defaults, animal_info,
        )
        if agg is None:
            continue
        H_per_pre_date[d] = agg

    if not H_per_pre_date:
        # No pre-stroke data — can't establish baseline. Emit zero rows.
        return {}, {
            "family_entry": family_entry,
            "n_pre_sessions": 0,
            "n_post_sessions": len(post_dates),
            "n_per_session_pre_anchors": 0,
            "n_per_session_post_anchors": 0,
            "n_per_bin_anchors": 0,
            "wall_time_s": round(time.monotonic() - t0, 2),
            "skipped_no_pre_pool": True,
        }

    # Aggregate pre-pool from the per-pre-date histograms.
    first_pre_agg = next(iter(H_per_pre_date.values()))
    H_pre = np.zeros_like(first_pre_agg.H, dtype=float)
    n_pre_sessions = 0
    n_pre_frames = 0
    for agg in H_per_pre_date.values():
        if agg.H.shape != H_pre.shape:
            continue
        H_pre = H_pre + agg.H
        n_pre_sessions += agg.n_sessions
        n_pre_frames += agg.n_frames
    extent = first_pre_agg.extent
    nx, ny = H_pre.shape

    # Cost matrix — built once per family per animal.
    C = _build_cost_matrix(extent, nx, ny)

    # Per-date post-stroke histograms (build once; reuse for per_bin).
    H_per_post_date: dict[dt.date, _AggregatedHistogram] = {}
    post_dates_rel: dict[dt.date, int] = {}
    for d in post_dates:
        agg = _aggregate_family_hist(
            animal, [d], bodyparts, center_mode, resolver, defaults, animal_info,
        )
        if agg is None or agg.H.shape != H_pre.shape:
            continue
        H_per_post_date[d] = agg
        post_dates_rel[d] = animal_info.day_relative_to_stroke(d)

    # Bin grouping (post-stroke only per Addendum #6 (C)).
    bin_groups = _bin_groups(post_dates_rel, animal_info.bin_days)

    rows_by_slug: dict[str, list[dict[str, Any]]] = {
        f"{prefix}_{family_entry}": []
        for _metric_name, prefix in _METRICS
    }

    def _emit_row(
        *,
        granularity: str,
        anchor_rel_day: int,
        row_date: dt.date,
        epoch_label_value: str,
        H_a: np.ndarray, H_b: np.ndarray,
        n_sessions_aggregated: int,
        n_frames_aggregated: int,
    ) -> None:
        for metric_name, prefix in _METRICS:
            slug = f"{prefix}_{family_entry}"
            metric_fn = _METRIC_FNS[metric_name]
            value = metric_fn(H_a, H_b, C)
            is_sentinel = value is None or not np.isfinite(value)
            rows_by_slug[slug].append({
                "animal": animal,
                "date": row_date,
                "rel_day": int(anchor_rel_day),
                "trial_idx": None,
                "side": "global",
                "ipsi_contra": "global",
                "endpoint_slug": slug,
                "value": None if is_sentinel else float(value),
                "is_sentinel": bool(is_sentinel),
                "cohort_bin_size": int(animal_info.bin_days),
                "epoch_label": epoch_label_value,
                "granularity": granularity,
                "rel_day_anchor": int(anchor_rel_day),
                "n_sessions_aggregated": int(n_sessions_aggregated),
                "n_frames_aggregated": int(n_frames_aggregated),
            })

    # 1. per_session emit for PRE-stroke sessions via leave-one-out:
    #    each pre session's metric is computed against the pre-pool
    #    MINUS that session. Yields a per-session "noise floor" sample.
    for d, agg in sorted(H_per_pre_date.items()):
        if agg.H.shape != H_pre.shape:
            continue
        H_pre_minus_self = H_pre - agg.H
        if H_pre_minus_self.sum() <= 0:
            # Only one pre-stroke session — can't leave-one-out. Skip
            # rather than emit a degenerate row (it would be metric vs
            # all-zero, returning is_sentinel anyway).
            continue
        rel = animal_info.day_relative_to_stroke(d)
        _emit_row(
            granularity="per_session",
            anchor_rel_day=rel,
            row_date=d,
            epoch_label_value="pre",
            H_a=agg.H, H_b=H_pre_minus_self,
            n_sessions_aggregated=1,
            n_frames_aggregated=agg.n_frames,
        )

    # 2. per_session emit for POST-stroke sessions: metric vs full pre-pool.
    for d in sorted(H_per_post_date):
        agg = H_per_post_date[d]
        rel = post_dates_rel[d]
        eb_label = assign_epoch_label(int(rel), animal_info)
        if eb_label is None:
            # Transitional gap — skip per Addendum #6 semantics; only
            # categorized epochs participate in per_epoch downstream.
            continue
        _emit_row(
            granularity="per_session",
            anchor_rel_day=rel,
            row_date=d,
            epoch_label_value=eb_label,
            H_a=agg.H, H_b=H_pre,
            n_sessions_aggregated=1,
            n_frames_aggregated=agg.n_frames,
        )

    # 3. per_bin emit for POST-stroke bins: aggregated bin histogram
    #    vs full pre-pool.
    for anchor, dates in sorted(bin_groups.items()):
        H_bin = np.zeros_like(H_pre)
        n_sess = 0
        n_frames = 0
        for d in dates:
            ag = H_per_post_date.get(d)
            if ag is None:
                continue
            H_bin = H_bin + ag.H
            n_sess += ag.n_sessions
            n_frames += ag.n_frames
        if H_bin.sum() == 0:
            continue
        eb_label = assign_epoch_label(int(anchor), animal_info)
        if eb_label is None:
            eb_label = "transitional_gap"  # rare; still emit so the row isn't silently lost
        _emit_row(
            granularity="per_bin",
            anchor_rel_day=anchor,
            row_date=sorted(dates)[0],
            epoch_label_value=eb_label,
            H_a=H_bin, H_b=H_pre,
            n_sessions_aggregated=n_sess,
            n_frames_aggregated=n_frames,
        )

    telemetry = {
        "family_entry": family_entry,
        "n_pre_sessions": int(n_pre_sessions),
        "n_post_sessions": int(len(post_dates_rel)),
        "n_per_session_pre_anchors": int(len(H_per_pre_date)),
        "n_per_session_post_anchors": int(len(H_per_post_date)),
        "n_per_bin_anchors": int(len(bin_groups)),
        "wall_time_s": round(time.monotonic() - t0, 2),
    }
    return rows_by_slug, telemetry


# ===========================================================================
# Parquet + manifest writers
# ===========================================================================


def _output_path(resolver: PathResolver, slug: str, animal: str) -> Path:
    out_root = resolver.pipeline_outputs(subdir="stats") / "inputs" / slug
    out_root.mkdir(parents=True, exist_ok=True)
    return out_root / f"{animal}.parquet"


def _write_spatial_parquet(rows: list[dict[str, Any]], path: Path) -> int:
    """Write spatial rows to parquet (15 columns)."""
    if not rows:
        df = pd.DataFrame(columns=list(_SPATIAL_PARQUET_COLUMNS))
        df.to_parquet(path, index=False)
        return 0
    df = pd.DataFrame(rows, columns=list(_SPATIAL_PARQUET_COLUMNS))
    df["trial_idx"] = df["trial_idx"].astype("Int64")
    df["rel_day"] = df["rel_day"].astype("Int64")
    df["cohort_bin_size"] = df["cohort_bin_size"].astype("Int64")
    df["rel_day_anchor"] = df["rel_day_anchor"].astype("Int64")
    df["n_sessions_aggregated"] = df["n_sessions_aggregated"].astype("Int64")
    df["n_frames_aggregated"] = df["n_frames_aggregated"].astype("Int64")
    df.to_parquet(path, index=False)
    return len(df)


# ===========================================================================
# Main driver
# ===========================================================================


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--animals", nargs="*", default=None)
    p.add_argument(
        "--families", nargs="*", default=None,
        help=f"Subset of family entries; default = all 4 ({_FAMILY_ENTRIES}).",
    )
    p.add_argument(
        "--skip-existing", action="store_true",
        help="Skip (animal, slug) pairs whose parquet exists.",
    )
    p.add_argument(
        "--manifest", type=Path,
        default=REPO_ROOT / ".scratch_phase_9" / "materialize_spatial_manifest.csv",
    )
    p.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY_PATH)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    specs = load_inventory(args.inventory)
    spatial_specs = [
        s for s in specs
        if s.is_primary
        and s.value_type in ("scalar_per_animal_time", "scalar_per_animal_bin")
    ]
    # Index by (metric, family) → slug.
    slug_by_metric_family: dict[tuple[str, str], str] = {}
    for s in spatial_specs:
        for metric_name, prefix in _METRICS:
            if s.slug.startswith(f"{prefix}_"):
                fam = s.slug[len(f"{prefix}_"):]
                slug_by_metric_family[(metric_name, fam)] = s.slug

    animals_map = load_animals()
    cohort = sorted(animals_map.keys())
    target_animals = [
        a for a in cohort if args.animals is None or a in args.animals
    ]
    families = (
        list(args.families) if args.families is not None else list(_FAMILY_ENTRIES)
    )

    print("Phase 9 Commit C — spatial materialize")
    print(f"  animals in scope:  {len(target_animals)}")
    print(f"  families in scope: {len(families)}")
    print(f"  metrics:           {[m for m, _ in _METRICS]}")
    print(f"  total (animal, family, metric) emits: "
          f"{len(target_animals) * len(families) * len(_METRICS)}")
    print()

    resolver = PathResolver()
    defaults = load_defaults()

    manifest_rows: list[dict[str, Any]] = []
    for animal in target_animals:
        print(f"=== {animal} ===")
        animal_info = animals_map[animal]
        for family_entry in families:
            # Skip-existing check: all 3 metric parquets for this (animal,
            # family) must already exist.
            if args.skip_existing:
                metric_slugs = [
                    slug_by_metric_family[(m, family_entry)]
                    for m, _ in _METRICS
                    if (m, family_entry) in slug_by_metric_family
                ]
                all_exist = all(
                    _output_path(resolver, s, animal).exists() for s in metric_slugs
                )
                if all_exist and len(metric_slugs) == len(_METRICS):
                    print(f"  {family_entry}: skip (all 3 metric parquets exist)")
                    for s in metric_slugs:
                        manifest_rows.append({
                            "endpoint_slug": s, "animal": animal,
                            "status": "skipped_existing",
                            "n_rows": 0, "n_sentinel": 0,
                            "output_path": str(_output_path(resolver, s, animal)),
                            "wall_time_s": 0.0,
                        })
                    continue

            try:
                rows_by_slug, telemetry = _emit_one_family_for_animal(
                    animal=animal,
                    animal_info=animal_info,
                    family_entry=family_entry,
                    resolver=resolver,
                    defaults=defaults,
                )
            except Exception as exc:
                print(f"  {family_entry}: ERROR ({type(exc).__name__}: {exc})")
                for metric_name, prefix in _METRICS:
                    manifest_rows.append({
                        "endpoint_slug": f"{prefix}_{family_entry}",
                        "animal": animal,
                        "status": f"error: {type(exc).__name__}: {exc}",
                        "n_rows": 0, "n_sentinel": 0,
                        "output_path": "",
                        "wall_time_s": 0.0,
                    })
                continue

            n_pre = telemetry.get("n_per_session_pre_anchors", 0)
            n_post = telemetry.get("n_per_session_post_anchors", 0)
            n_per_bin = telemetry.get("n_per_bin_anchors", 0)
            wall = telemetry.get("wall_time_s", 0.0)
            print(
                f"  {family_entry}: "
                f"per_session pre={n_pre} post={n_post}, "
                f"per_bin={n_per_bin}  ({wall:.1f} s)",
            )

            for slug, rows in rows_by_slug.items():
                out_path = _output_path(resolver, slug, animal)
                n_rows = _write_spatial_parquet(rows, out_path)
                n_sentinel = sum(1 for r in rows if r["is_sentinel"])
                manifest_rows.append({
                    "endpoint_slug": slug,
                    "animal": animal,
                    "status": (
                        "skipped_no_pre_pool"
                        if telemetry.get("skipped_no_pre_pool")
                        else "success"
                    ),
                    "n_rows": int(n_rows),
                    "n_sentinel": int(n_sentinel),
                    "output_path": str(out_path),
                    "wall_time_s": round(wall / len(rows_by_slug), 3),
                })

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(_MANIFEST_COLUMNS))
        w.writeheader()
        for row in manifest_rows:
            w.writerow(row)

    n_success = sum(1 for r in manifest_rows if r["status"] == "success")
    n_skip = sum(1 for r in manifest_rows if r["status"].startswith("skipped"))
    n_error = sum(1 for r in manifest_rows if r["status"].startswith("error"))
    print()
    print(f"Manifest: {args.manifest}")
    print(f"  success: {n_success}")
    print(f"  skipped: {n_skip}")
    print(f"  errors:  {n_error}")
    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
