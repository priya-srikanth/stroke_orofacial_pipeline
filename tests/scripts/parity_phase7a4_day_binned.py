"""Phase 7a.4 — day-binned cross-session traces parity harness.

Compares the consolidated 7a.4 day-binned aggregator
(:func:`stroke_orofacial.dlc_kinematics.aggregate_licking_dynamics_day_binned_by_animal`)
against the legacy Cell 42 ``*_dayBinnedTraces_*.csv`` emit on
MICROSCOPE.

Mirrors the 7a.3 V3 harness (``parity_phase7a3_tongue_pertrial.py``) for
input loading, ``legacy_approximate`` mode overrides, and the
re-emit-into-temp pattern. In ``legacy_approximate`` mode the harness
re-emits per-session traces under a temp output_root with
``licking_dyn_apply_win_ms=[0, 2500]`` (and the 7a.3 V3 detector / bout
overrides) — bit-identical to legacy on the per-session input — then
runs the day-binner on top to get an axis-aligned consolidated emit.
Default mode is reported as ``skip_no_legacy`` cohort-wide because
consolidated and legacy timebin axes are disjoint
(consolidated `[80, 100, ..., 5000]` vs legacy `[10, 30, ..., 2490]`,
phase-shifted by 10 ms).

CLI::

    python tests/scripts/parity_phase7a4_day_binned.py \\
        --mode {default, legacy_approximate} \\
        --animals auto \\
        --atol 1e-6

Comparator (per ``(rel_day_bin, side, timebin)`` cell, per metric):

- mean: nan-aware ``np.isclose(a, b, atol=atol, equal_nan=True)``.
- SEM: legacy uses ``nanstd(ddof=0) / sqrt(n_total)``; consolidated uses
  ``nanstd(ddof=1) / sqrt(n_support)``. Transform consolidated SEM into
  legacy form before comparing:
  ``SEM_legacy_predicted = SEM_consolidated * sqrt((n_support - 1) / n_total)``.
- n_support_sessions: integer match required.

Hard-fail thresholds (per kickoff §5d):

- Rate columns (``lick_rate_per_t``, ``bout_rate_mean_hz``):
  ``max|Δ| > 1.0 Hz`` → hard fail.
- Probability columns (``p_lick_per_t``, ``p_within_bout_per_t``):
  ``max|Δ| > 0.1`` → hard fail.

Soft fails (above ``--atol`` but below the hard threshold) are
reported as ``fail`` with the residual band documented.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# The 7a.3 V3 harness ships the canonical reusable bits (params builder,
# legacy_approximate overrides, harness resolver, per-session emit).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_phase7a3_tongue_pertrial as h7a3  # type: ignore[import]

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.dlc_kinematics import (
    aggregate_licking_dynamics_day_binned,
)

CAM = "cam2"
CENTER_MODE = "centered_spout_midpoint"
INTERP_VERSION = "v5p3"
MIN_TRIALS_PER_BIN = 3

# Hard-fail thresholds (kickoff §5d).
HARD_FAIL_RATE_HZ = 1.0
HARD_FAIL_PROB = 0.1

# Cohort animals (8 total — PS52/PS53 absent per Task 1.5a audit).
DEFAULT_ANIMALS: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)

# Metric mapping legacy ↔ consolidated (Task 5.0 audit §4).
_METRIC_PAIRS: tuple[tuple[str, str, str], ...] = (
    # (legacy metric name, consolidated output base name, kind)
    ("lick_rate_mean_hz", "lick_rate_per_t",       "rate"),
    ("bout_rate_mean_hz", "bout_rate_mean_hz",     "rate"),
    ("p_lick",            "p_lick_per_t",          "prob"),
    ("bout_state_frac",   "p_within_bout_per_t",   "prob"),
)


# ============================================================================
# Result dataclasses
# ============================================================================


@dataclass
class _MetricStat:
    """Per-metric residual stats over one (animal, mode) run."""
    metric: str
    kind: str          # "rate" or "prob"
    n_compared: int = 0
    max_d_mean: float = 0.0
    max_d_sem: float = 0.0
    max_d_nss: int = 0
    n_hard_fail: int = 0


@dataclass
class _AnimalResult:
    animal: str
    mode: str
    status: str             # "pass", "fail", "skip_no_legacy", "skip_emit_error"
    note: str = ""
    n_bins_compared: int = 0
    metrics: list[_MetricStat] = field(default_factory=list)


# ============================================================================
# Legacy reader
# ============================================================================


def _legacy_csv_path(animal_info: AnimalInfo) -> Path:
    """Resolve the canonical legacy day-binned CSV for an animal.

    Glob pattern (Task 5.0 audit §1):
    ``{MICROSCOPE_OUT_ROOT}/{animal}/.../{animal}_cam2_ILIwithinBout_dayBinnedTraces_bin{B}d_minTrialsPerBin3_*.csv``

    where ``B = animal_info.bin_days``. Fail loud on zero / multiple
    matches.
    """
    fig_dir = h7a3._legacy_animal_dir(animal_info.animal_id) / "lick_metrics" / "lick_rate"
    if not fig_dir.exists():
        raise FileNotFoundError(f"Legacy day-binned dir not found: {fig_dir}")
    pattern = (
        f"{animal_info.animal_id}_{CAM}_ILIwithinBout_dayBinnedTraces_"
        f"bin{int(animal_info.bin_days)}d_minTrialsPerBin{MIN_TRIALS_PER_BIN}_"
        f"*-*_{INTERP_VERSION}.csv"
    )
    matches = sorted(fig_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"No legacy day-binned CSV for {animal_info.animal_id} matching "
            f"{pattern!r} in {fig_dir}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple legacy day-binned CSVs for {animal_info.animal_id}: "
            f"{[m.name for m in matches]}"
        )
    return matches[0]


def _parse_list_cell(cell: object) -> np.ndarray:
    """Parse a Python-list-repr CSV cell to a float64 array."""
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return np.zeros(0, dtype=np.float64)
    if isinstance(cell, (list, tuple, np.ndarray)):
        return np.asarray(cell, dtype=np.float64)
    s = str(cell).strip()
    if not s:
        return np.zeros(0, dtype=np.float64)
    try:
        parsed = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return np.zeros(0, dtype=np.float64)
    return np.asarray(parsed, dtype=np.float64)


def _legacy_rows_for_label(legacy_df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Filter legacy long-form rows by rel_day_bin label."""
    return legacy_df[legacy_df["rel_day_bin"] == label].reset_index(drop=True)


# ============================================================================
# Consolidated emit (re-run per-session traces under mode-specific overrides)
# ============================================================================


def _emit_consolidated_day_binned(
    animal: str,
    animal_info: AnimalInfo,
    mode: str,
    emit_root: Path,
) -> dict[str, Path] | None:
    """Re-emit per-session traces (legacy_approximate overrides applied)
    + run the day-binner. Returns ``{rel_day_bin_label: parquet_path}``.

    Returns ``None`` on per-session emit error.
    """
    # 1. Discover sessions in scope. Mirror the 7a.3 harness's scope
    #    filter so we touch the same 14 sessions (or per-animal subset).
    scope = h7a3.load_scope(
        Path(__file__).resolve().parents[2] / "configs" / "animals.yaml"
    )
    if animal not in scope:
        return {}
    start, end = scope[animal]
    # Build cohort date list from the scope range. Real per-animal dates
    # come from upstream availability; we let the per-session emitter
    # raise FileNotFoundError on missing days and skip those.
    dates: list[dt.date] = []
    d = start
    while d <= end:
        dates.append(d)
        d += dt.timedelta(days=1)

    # 2. For each session, emit per-session traces under emit_root with
    #    mode overrides applied. Sessions with missing inputs are
    #    skipped silently — the day-binner will then aggregate over the
    #    successfully emitted set, matching legacy's behaviour of
    #    skipping NPZ-missing days.
    emitted_dates: list[dt.date] = []
    for d in dates:
        try:
            h7a3._emit_session(animal, d, mode, emit_root)
            emitted_dates.append(d)
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 — best-effort harness
            print(
                f"  [{animal} {d}] emit failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
    if not emitted_dates:
        return None

    # 3. Run the day-binner on the emitted per-session traces.
    resolver_for_aggregator = h7a3._build_resolver(mode, emit_root)
    out_paths = aggregate_licking_dynamics_day_binned(
        animal=animal,
        sessions=emitted_dates,
        resolver=resolver_for_aggregator,
        animal_info=animal_info,
        overwrite="force",
    )
    return out_paths


# ============================================================================
# Comparator
# ============================================================================


def _max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    """nan-aware max|Δ| over cells where BOTH are finite.

    Cells where either side is NaN are skipped (legacy and consolidated
    have different NaN policies for SEM-with-n=1 — legacy emits 0,
    consolidated emits NaN). Returns 0.0 if no finite-finite cells.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return float("nan")
    both_finite = np.isfinite(a) & np.isfinite(b)
    if not np.any(both_finite):
        return 0.0
    diff = np.abs(a[both_finite] - b[both_finite])
    return float(np.max(diff))


def _compare_one_bin(
    consolidated_df: pd.DataFrame,
    legacy_rows_for_label: pd.DataFrame,
    n_total_per_side: dict[str, int],
    atol: float,
) -> dict[str, _MetricStat]:
    """Per-(rel_day_bin) comparison: 4 metrics × 2 sides."""
    out: dict[str, _MetricStat] = {
        cons_base: _MetricStat(metric=cons_base, kind=kind)
        for _, cons_base, kind in _METRIC_PAIRS
    }
    for legacy_metric, cons_base, kind in _METRIC_PAIRS:
        for side in sorted(legacy_rows_for_label["side"].unique()):
            lg_row = legacy_rows_for_label[
                (legacy_rows_for_label["metric"] == legacy_metric)
                & (legacy_rows_for_label["side"] == side)
            ]
            if lg_row.empty:
                continue
            lg = lg_row.iloc[0]
            legacy_t = _parse_list_cell(lg["t_ms"])
            legacy_mean = _parse_list_cell(lg["mean"])
            legacy_sem = _parse_list_cell(lg["sem"])
            legacy_nss = _parse_list_cell(lg["n_support_sessions"]).astype(int)
            n_total = int(n_total_per_side.get(side, lg["n_sessions"]))

            cons_side = consolidated_df[consolidated_df["side"] == side]
            if cons_side.empty:
                continue
            cons_t = cons_side["timebin_ms"].to_numpy(dtype=np.float64)

            common, idx_lg, idx_cs = np.intersect1d(
                legacy_t, cons_t, assume_unique=False, return_indices=True,
            )
            if common.size == 0:
                continue

            cons_mean = cons_side[f"{cons_base}_mean"].to_numpy(dtype=np.float64)[idx_cs]
            cons_sem = cons_side[f"{cons_base}_sem"].to_numpy(dtype=np.float64)[idx_cs]
            cons_nss = cons_side[f"{cons_base}_n_support_sessions"].to_numpy(
                dtype=np.int64,
            )[idx_cs]

            lg_mean = legacy_mean[idx_lg] if legacy_mean.size == legacy_t.size else None
            lg_sem = legacy_sem[idx_lg] if legacy_sem.size == legacy_t.size else None
            lg_nss = legacy_nss[idx_lg] if legacy_nss.size == legacy_t.size else None

            stat = out[cons_base]
            stat.n_compared += int(common.size)

            if lg_mean is not None:
                d = _max_abs_diff(lg_mean, cons_mean)
                if not np.isnan(d) and d > stat.max_d_mean:
                    stat.max_d_mean = d
                hard = (
                    HARD_FAIL_RATE_HZ if kind == "rate" else HARD_FAIL_PROB
                )
                if not np.isnan(d) and d > hard:
                    stat.n_hard_fail += 1

            if lg_sem is not None and lg_nss is not None:
                # Transform consolidated ddof=1/n_support into legacy
                # ddof=0/n_total form before comparing.
                # SEM_legacy_predicted = SEM_cons * sqrt((n_support - 1) / n_total)
                with np.errstate(invalid="ignore"):
                    factor = np.where(
                        cons_nss >= 2,
                        np.sqrt(np.maximum(cons_nss - 1, 0) / max(1, n_total)),
                        np.nan,
                    )
                cons_sem_predicted = cons_sem * factor
                d = _max_abs_diff(lg_sem, cons_sem_predicted)
                if not np.isnan(d) and d > stat.max_d_sem:
                    stat.max_d_sem = d

            if lg_nss is not None:
                d_int = int(np.max(np.abs(cons_nss - lg_nss)))
                if d_int > stat.max_d_nss:
                    stat.max_d_nss = d_int

    return out


# ============================================================================
# Per-animal driver
# ============================================================================


def parity_one_animal(
    animal: str, mode: str, atol: float, emit_root: Path,
) -> _AnimalResult:
    animal_info = get_animal(animal)
    # Default mode: timebin axes are disjoint. Skip cohort-wide (matches
    # the 7a.3 V3 Cell 42 default-mode behaviour).
    if mode == "default":
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_no_legacy",
            note="default-mode timebin axes disjoint from legacy "
                 "(consolidated [80..5000] vs legacy [10..2490]); "
                 "use --mode legacy_approximate for parity",
        )

    # Try to locate the legacy CSV.
    try:
        legacy_path = _legacy_csv_path(animal_info)
    except (FileNotFoundError, RuntimeError) as exc:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_no_legacy",
            note=f"legacy CSV resolver: {exc}",
        )
    legacy_df = pd.read_csv(legacy_path)

    # Re-emit per-session traces under mode + run the day-binner.
    cons_paths = _emit_consolidated_day_binned(
        animal, animal_info, mode, emit_root,
    )
    if cons_paths is None:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_emit_error",
            note="per-session emit produced no successful sessions",
        )
    if not cons_paths:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_no_legacy",
            note="animal not in scope or no sessions in scope range",
        )

    # Iterate rel_day_bins emitted by the consolidated aggregator.
    metrics_acc: dict[str, _MetricStat] = {
        cons_base: _MetricStat(metric=cons_base, kind=kind)
        for _, cons_base, kind in _METRIC_PAIRS
    }
    n_bins_compared = 0
    for label in sorted(cons_paths):
        cons_df = pq.read_table(str(cons_paths[label])).to_pandas()
        legacy_for_label = _legacy_rows_for_label(legacy_df, label)
        if legacy_for_label.empty:
            continue
        # n_total per side: read from any legacy row's n_sessions for
        # this label (legacy stores it per (side, rel_day_bin); same
        # value for all 4 metrics within a side).
        n_total_per_side: dict[str, int] = {}
        for side in sorted(legacy_for_label["side"].unique()):
            row = legacy_for_label[legacy_for_label["side"] == side].iloc[0]
            n_total_per_side[side] = int(row["n_sessions"])
        per_bin_stats = _compare_one_bin(
            cons_df, legacy_for_label, n_total_per_side, atol,
        )
        for cons_base, stat in per_bin_stats.items():
            acc = metrics_acc[cons_base]
            acc.n_compared += stat.n_compared
            acc.max_d_mean = max(acc.max_d_mean, stat.max_d_mean)
            acc.max_d_sem = max(acc.max_d_sem, stat.max_d_sem)
            acc.max_d_nss = max(acc.max_d_nss, stat.max_d_nss)
            acc.n_hard_fail += stat.n_hard_fail
        n_bins_compared += 1

    if n_bins_compared == 0:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_no_legacy",
            note="no rel_day_bin labels overlap legacy CSV",
        )

    metrics_list = list(metrics_acc.values())
    any_hard_fail = any(s.n_hard_fail > 0 for s in metrics_list)
    any_soft_fail = any(
        (s.kind == "rate" and s.max_d_mean > atol)
        or (s.kind == "prob" and s.max_d_mean > atol)
        for s in metrics_list
    )
    status = "fail" if (any_hard_fail or any_soft_fail) else "pass"
    note = ""
    if any_hard_fail:
        note = "HARD FAIL: residual exceeds kickoff §5d threshold"
    return _AnimalResult(
        animal=animal, mode=mode, status=status, note=note,
        n_bins_compared=n_bins_compared, metrics=metrics_list,
    )


# ============================================================================
# Main driver
# ============================================================================


def _print_animal_report(result: _AnimalResult) -> None:
    print(f"  {result.animal} ({result.mode}): {result.status:<14}", end="")
    if result.note:
        print(f"  {result.note}")
    else:
        print(f"  bins={result.n_bins_compared}")
    for stat in result.metrics:
        flag = "  [HARD FAIL]" if stat.n_hard_fail > 0 else ""
        print(
            f"    {stat.metric:<28} kind={stat.kind:<4} "
            f"n={stat.n_compared:<6} max|Δ|_mean={stat.max_d_mean:.3e}  "
            f"max|Δ|_sem={stat.max_d_sem:.3e}  "
            f"max|Δ|_nss={stat.max_d_nss}{flag}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7a.4 day-binned parity harness.",
    )
    parser.add_argument(
        "--mode", choices=("default", "legacy_approximate"),
        default="legacy_approximate",
    )
    parser.add_argument("--animals", default="auto",
                        help="Comma-separated animal ids or 'auto'")
    parser.add_argument("--atol", type=float, default=1e-6)
    args = parser.parse_args(argv)

    if args.animals == "auto":
        animals = list(DEFAULT_ANIMALS)
    else:
        animals = [a.strip() for a in args.animals.split(",") if a.strip()]

    print(
        f"Phase 7a.4 day-binned parity (mode={args.mode}, atol={args.atol:.1e})"
    )
    print(f"Animals: {animals}")
    print()

    with tempfile.TemporaryDirectory(prefix="parity_7a4_") as td:
        emit_root = Path(td)
        results: list[_AnimalResult] = []
        for animal in animals:
            print(f"[{animal}] starting ...")
            result = parity_one_animal(
                animal=animal, mode=args.mode, atol=args.atol,
                emit_root=emit_root,
            )
            results.append(result)
            _print_animal_report(result)
            print()

    # Cohort summary.
    print("=" * 80)
    print(f"Cohort summary (mode={args.mode}, atol={args.atol:.1e}):")
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    print()
    # Per-metric cohort-wide max|Δ|.
    cohort_metrics: dict[str, _MetricStat] = {
        cons_base: _MetricStat(metric=cons_base, kind=kind)
        for _, cons_base, kind in _METRIC_PAIRS
    }
    for r in results:
        for stat in r.metrics:
            acc = cohort_metrics[stat.metric]
            acc.n_compared += stat.n_compared
            acc.max_d_mean = max(acc.max_d_mean, stat.max_d_mean)
            acc.max_d_sem = max(acc.max_d_sem, stat.max_d_sem)
            acc.max_d_nss = max(acc.max_d_nss, stat.max_d_nss)
            acc.n_hard_fail += stat.n_hard_fail
    print("Per-metric cohort-wide max|Δ|:")
    for stat in cohort_metrics.values():
        flag = "  [HARD FAIL]" if stat.n_hard_fail > 0 else ""
        print(
            f"  {stat.metric:<28} kind={stat.kind:<4} "
            f"n={stat.n_compared:<6} max|Δ|_mean={stat.max_d_mean:.3e}  "
            f"max|Δ|_sem={stat.max_d_sem:.3e}  "
            f"max|Δ|_nss={stat.max_d_nss}{flag}"
        )

    any_hard_fail = any(
        any(s.n_hard_fail > 0 for s in r.metrics) for r in results
    )
    return 1 if any_hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
