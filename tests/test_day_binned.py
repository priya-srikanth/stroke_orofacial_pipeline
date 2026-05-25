"""Phase 7a.4 — unit tests for the Cell 42 day-binned cross-session aggregator.

Synthetic-data tests only. Every test that invokes a writer uses
:class:`PathResolver` with ``output_root=tmp_path`` per
:doc:`docs/testing-conventions.md` (no test ever writes to the real
``stroke_orofacial_pipeline_outputs/`` tree).

Coverage:

- :class:`TestComputeRelDayBinLabel` — legacy ``f"{lo}..{hi}"`` label
  algorithm (anchor on ``rel_day=0``; last pre-bin = ``[-(B-1), 0]``;
  post bins start at ``[1, B]``); both bin_days values used in the cohort
  (2 and 7) plus invalid inputs.
- :class:`TestAggregator` — synthetic 2-3 session aggregation: nanmean
  correctness, NaN handling, no-re-smoothing of pre-smoothed
  ``lick_rate_per_t``, per-metric ``n_support_sessions``, SEM formula
  (ddof=1, divided by ``sqrt(n_support)``), file-level metadata keys.
- :class:`TestOverwriteSemantics` — skip vs force.
- :class:`TestSchemaGuard` — heterogeneous (side, timebin_ms) grids raise.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics._day_binned import (
    DAY_BINNED_VERSION,
    _aggregate_across_sessions,
    _compute_rel_day_bin_label,
    aggregate_licking_dynamics_day_binned,
)
from stroke_orofacial.paths import PathResolver


# ============================================================================
# Synthetic fixtures
# ============================================================================


_TIMEBINS_MS = np.array([0.0, 20.0, 40.0, 60.0, 80.0], dtype=np.float64)
_SIDES = ("L", "R")

_METRIC_INPUT_COLS = (
    "lick_rate_per_t",
    "ili_within_bout_rate_per_t",
    "p_lick_per_t",
    "p_within_bout_per_t",
)
_METRIC_OUT_BASES = (
    "lick_rate_per_t",
    "bout_rate_mean_hz",
    "p_lick_per_t",
    "p_within_bout_per_t",
)


def _make_session_traces_df(
    *,
    timebins_ms: np.ndarray = _TIMEBINS_MS,
    sides: Sequence[str] = _SIDES,
    fill: dict[str, float] | None = None,
    per_cell: dict[tuple[str, float, str], float] | None = None,
) -> pd.DataFrame:
    """Build a synthetic 7a.3-shaped wide-form per-session traces DataFrame.

    ``fill`` provides a per-metric scalar fill (default = 1.0 for every
    metric). ``per_cell`` overrides individual ``(metric, timebin_ms, side)``
    cells (NaN-friendly).
    """
    fill = fill if fill is not None else {m: 1.0 for m in _METRIC_INPUT_COLS}
    per_cell = per_cell or {}
    rows: list[dict] = []
    for side in sides:
        for tb in timebins_ms:
            row: dict = {"timebin_ms": float(tb), "side": side}
            for metric in _METRIC_INPUT_COLS:
                key = (metric, float(tb), side)
                row[metric] = (
                    per_cell[key] if key in per_cell
                    else float(fill.get(metric, 1.0))
                )
            rows.append(row)
    return pd.DataFrame(rows)


def _write_session_traces_parquet(
    path: Path,
    df: pd.DataFrame,
    *,
    feature_extraction_version: str = "v7a.3",
    interpolation_version: str = "v5p3",
) -> None:
    """Write a synthetic per-session traces parquet at ``path`` with metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_bytes = {
        b"feature_extraction_version": feature_extraction_version.encode(),
        b"interpolation_version": interpolation_version.encode(),
    }
    existing = table.schema.metadata or {}
    merged = {
        **{bytes(k): bytes(v) for k, v in existing.items()},
        **meta_bytes,
    }
    table = table.replace_schema_metadata(merged)
    pq.write_table(table, str(path), compression="snappy")


def _make_animal_info(
    *,
    animal_id: str = "PS50",
    stroke_date: datetime.date = datetime.date(2025, 3, 23),
    bin_days: int = 2,
) -> AnimalInfo:
    """Minimal AnimalInfo for the day-binner. Only stroke_date + bin_days
    are read — other fields use sensible defaults via the dataclass."""
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=stroke_date,
        session_start=stroke_date - datetime.timedelta(days=10),
        session_end=stroke_date + datetime.timedelta(days=30),
        epoch_boundaries=EpochBoundaries(1, 4, 5),
        bin_days=bin_days,
        kinematics_baselines={
            "tongue": {"x0": 0.0, "y0": -110.0},
            "jaw": {"x0": 0.0, "y0": 290.0},
        },
    )


# ============================================================================
# _compute_rel_day_bin_label
# ============================================================================


class TestComputeRelDayBinLabel:
    """Legacy bit-identical labels: ``f"{lo}..{hi}"`` anchored at rel_day=0.

    For ``B = bin_days``:
    - rel_day=0 falls in the LAST PRE-BIN ``[-(B-1), 0]``.
    - First post-bin is ``[1, B]``.
    """

    def test_d0_is_pre_anchor_bin_days_2(self):
        d0 = datetime.date(2025, 3, 23)
        assert _compute_rel_day_bin_label(d0, d0, 2) == "-1..0"

    def test_d0_minus_one_bin_days_2(self):
        d0 = datetime.date(2025, 3, 23)
        assert _compute_rel_day_bin_label(
            d0 - datetime.timedelta(days=1), d0, 2,
        ) == "-1..0"

    def test_d0_minus_two_bin_days_2(self):
        d0 = datetime.date(2025, 3, 23)
        assert _compute_rel_day_bin_label(
            d0 - datetime.timedelta(days=2), d0, 2,
        ) == "-3..-2"

    def test_post_bin_bin_days_2(self):
        d0 = datetime.date(2025, 3, 23)
        # rel_day=1 → bin [1, 2]; rel_day=2 → [1, 2]; rel_day=3 → [3, 4].
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=1), d0, 2,
        ) == "1..2"
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=2), d0, 2,
        ) == "1..2"
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=3), d0, 2,
        ) == "3..4"

    def test_post_bin_bin_days_7(self):
        d0 = datetime.date(2025, 4, 29)
        # rel_day=1 → [1, 7]; rel_day=7 → [1, 7]; rel_day=8 → [8, 14].
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=1), d0, 7,
        ) == "1..7"
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=7), d0, 7,
        ) == "1..7"
        assert _compute_rel_day_bin_label(
            d0 + datetime.timedelta(days=8), d0, 7,
        ) == "8..14"
        # rel_day=0 (d0) → last pre-bin is [-6, 0] for B=7.
        assert _compute_rel_day_bin_label(d0, d0, 7) == "-6..0"

    def test_invalid_bin_days_zero_raises(self):
        d0 = datetime.date(2025, 3, 23)
        with pytest.raises(ValueError, match="bin_days"):
            _compute_rel_day_bin_label(d0, d0, 0)

    def test_invalid_bin_days_bool_raises(self):
        """Python's bool-is-int subclass would silently coerce True → 1."""
        d0 = datetime.date(2025, 3, 23)
        with pytest.raises(TypeError, match="bin_days"):
            _compute_rel_day_bin_label(d0, d0, True)  # type: ignore[arg-type]


# ============================================================================
# _aggregate_across_sessions  (in-memory, no I/O)
# ============================================================================


class TestAggregator:
    """Per-cell mean / SEM / n_support across the session axis."""

    def test_two_sessions_same_bin_averages_correctly(self):
        s1 = _make_session_traces_df(fill={
            "lick_rate_per_t": 2.0,
            "ili_within_bout_rate_per_t": 4.0,
            "p_lick_per_t": 0.5,
            "p_within_bout_per_t": 0.5,
        })
        s2 = _make_session_traces_df(fill={
            "lick_rate_per_t": 4.0,
            "ili_within_bout_rate_per_t": 6.0,
            "p_lick_per_t": 0.7,
            "p_within_bout_per_t": 0.9,
        })
        out = _aggregate_across_sessions(
            [s1, s2], emit_sem=True, emit_n_support_sessions=True,
        )

        # 2 sides × 5 timebins = 10 rows.
        assert len(out) == 10
        # Means are the elementwise average of the two sessions.
        assert np.allclose(out["lick_rate_per_t_mean"], 3.0)
        assert np.allclose(out["bout_rate_mean_hz_mean"], 5.0)
        assert np.allclose(out["p_lick_per_t_mean"], 0.6)
        assert np.allclose(out["p_within_bout_per_t_mean"], 0.7)
        # All 4 metrics had 2 sessions contributing finite values everywhere.
        for base in _METRIC_OUT_BASES:
            assert (out[f"{base}_n_support_sessions"] == 2).all(), base

    def test_handles_nan_per_session(self):
        """NaN in one session's metric → nanmean ignores it; n_support drops."""
        s1 = _make_session_traces_df(fill={
            "lick_rate_per_t": 2.0,
            "ili_within_bout_rate_per_t": 4.0,
            "p_lick_per_t": 0.5,
            "p_within_bout_per_t": 0.5,
        })
        # Knock out two cells in s2 for ili_within_bout_rate_per_t.
        s2 = _make_session_traces_df(
            fill={
                "lick_rate_per_t": 4.0,
                "ili_within_bout_rate_per_t": 6.0,
                "p_lick_per_t": 0.7,
                "p_within_bout_per_t": 0.9,
            },
            per_cell={
                ("ili_within_bout_rate_per_t", 0.0, "L"): float("nan"),
                ("ili_within_bout_rate_per_t", 20.0, "L"): float("nan"),
            },
        )
        out = _aggregate_across_sessions(
            [s1, s2], emit_sem=True, emit_n_support_sessions=True,
        )
        # Sort to deterministic side-major order.
        out_sorted = out.sort_values(
            ["side", "timebin_ms"], kind="mergesort"
        ).reset_index(drop=True)
        # First two L rows for bout_rate: only s1 contributed (4.0); s2 NaN.
        assert out_sorted.iloc[0]["bout_rate_mean_hz_mean"] == 4.0
        assert out_sorted.iloc[1]["bout_rate_mean_hz_mean"] == 4.0
        assert out_sorted.iloc[0]["bout_rate_mean_hz_n_support_sessions"] == 1
        assert out_sorted.iloc[1]["bout_rate_mean_hz_n_support_sessions"] == 1
        # SEM with n_support=1 must be NaN (need >=2 samples for ddof=1 SEM).
        assert math.isnan(out_sorted.iloc[0]["bout_rate_mean_hz_sem"])
        # Other metrics unaffected — both sessions contribute everywhere.
        assert (
            out_sorted["lick_rate_per_t_n_support_sessions"] == 2
        ).all()

    def test_does_not_re_smooth_lick_rate(self):
        """Critical asymmetry: lick_rate_per_t arrives PRE-smoothed in the
        7a.3 emit (per-trial Gaussian σ=50ms applied before nanmean across
        trials). The day-binner must NOT re-smooth — it just averages
        across sessions. Verify by checking the output equals the direct
        elementwise mean of the inputs (no convolution shape distortion)."""
        # Sharp impulse: a 0/1/0/0/0 lick_rate trace per session.
        n_tb = len(_TIMEBINS_MS)
        s1_vals = np.zeros(n_tb, dtype=np.float64)
        s1_vals[1] = 1.0
        s2_vals = np.zeros(n_tb, dtype=np.float64)
        s2_vals[1] = 3.0
        per_cell_s1 = {
            ("lick_rate_per_t", float(tb), "L"): float(s1_vals[i])
            for i, tb in enumerate(_TIMEBINS_MS)
        }
        per_cell_s2 = {
            ("lick_rate_per_t", float(tb), "L"): float(s2_vals[i])
            for i, tb in enumerate(_TIMEBINS_MS)
        }
        s1 = _make_session_traces_df(per_cell=per_cell_s1)
        s2 = _make_session_traces_df(per_cell=per_cell_s2)
        out = _aggregate_across_sessions(
            [s1, s2], emit_sem=False, emit_n_support_sessions=False,
        )
        # Output for L side, sorted by timebin_ms: should be exactly the
        # elementwise mean of the two impulse traces — no Gaussian
        # blurring. mean = [0, 2, 0, 0, 0].
        l_rows = (
            out[out["side"] == "L"]
            .sort_values("timebin_ms", kind="mergesort")
            ["lick_rate_per_t_mean"]
            .to_numpy()
        )
        np.testing.assert_array_equal(l_rows, np.array([0.0, 2.0, 0.0, 0.0, 0.0]))

    def test_n_support_sessions_per_metric(self):
        """Each metric tracks its own n_support: NaN in one metric for one
        session does not affect another metric's count."""
        s1 = _make_session_traces_df()  # all 1.0
        s2 = _make_session_traces_df(  # NaN in p_lick_per_t at one cell
            per_cell={("p_lick_per_t", 40.0, "R"): float("nan")},
        )
        s3 = _make_session_traces_df()  # all 1.0
        out = _aggregate_across_sessions(
            [s1, s2, s3], emit_sem=False, emit_n_support_sessions=True,
        )
        out_R = (
            out[out["side"] == "R"]
            .sort_values("timebin_ms", kind="mergesort")
            .reset_index(drop=True)
        )
        # Cell (R, timebin=40) for p_lick_per_t: s2 was NaN → support=2.
        idx_40 = int(np.where(out_R["timebin_ms"].to_numpy() == 40.0)[0][0])
        assert out_R.iloc[idx_40]["p_lick_per_t_n_support_sessions"] == 2
        # Other metrics at the same cell: support=3 (no NaN injected).
        assert out_R.iloc[idx_40]["lick_rate_per_t_n_support_sessions"] == 3
        assert out_R.iloc[idx_40]["bout_rate_mean_hz_n_support_sessions"] == 3
        assert (
            out_R.iloc[idx_40]["p_within_bout_per_t_n_support_sessions"] == 3
        )

    def test_sem_ddof1_formula(self):
        """SEM = nanstd(values, ddof=1) / sqrt(n_support).

        For 3 sessions with values [1, 2, 3] and n_support=3:
        nanstd(ddof=1) = 1.0, SEM = 1 / sqrt(3) ≈ 0.5773502.
        """
        s1 = _make_session_traces_df(fill={
            "lick_rate_per_t": 1.0,
            "ili_within_bout_rate_per_t": 1.0,
            "p_lick_per_t": 1.0,
            "p_within_bout_per_t": 1.0,
        })
        s2 = _make_session_traces_df(fill={
            "lick_rate_per_t": 2.0,
            "ili_within_bout_rate_per_t": 2.0,
            "p_lick_per_t": 2.0,
            "p_within_bout_per_t": 2.0,
        })
        s3 = _make_session_traces_df(fill={
            "lick_rate_per_t": 3.0,
            "ili_within_bout_rate_per_t": 3.0,
            "p_lick_per_t": 3.0,
            "p_within_bout_per_t": 3.0,
        })
        out = _aggregate_across_sessions(
            [s1, s2, s3], emit_sem=True, emit_n_support_sessions=True,
        )
        expected_sem = 1.0 / math.sqrt(3.0)
        for base in _METRIC_OUT_BASES:
            assert np.allclose(out[f"{base}_sem"], expected_sem), base


# ============================================================================
# Driver: aggregate_licking_dynamics_day_binned with file I/O
# ============================================================================


def _seed_session(
    resolver: PathResolver,
    animal: str,
    date: datetime.date,
    fill: dict[str, float] | None = None,
    per_cell: dict[tuple[str, float, str], float] | None = None,
) -> Path:
    """Helper: write a synthetic 7a.3 per-session traces parquet at the
    resolver-target path, return the path."""
    df = _make_session_traces_df(fill=fill, per_cell=per_cell)
    path = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
        animal, date,
    )
    _write_session_traces_parquet(path, df)
    return path


class TestDriver:
    """End-to-end aggregator with PathResolver + on-disk parquet I/O."""

    def test_emits_metadata_keys(self, tmp_path):
        animal_info = _make_animal_info(bin_days=2)
        resolver = PathResolver(output_root=tmp_path)
        # Two sessions in the same post-bin [1..2].
        d1 = animal_info.stroke_date + datetime.timedelta(days=1)
        d2 = animal_info.stroke_date + datetime.timedelta(days=2)
        _seed_session(resolver, animal_info.animal_id, d1)
        _seed_session(resolver, animal_info.animal_id, d2)

        params = load_defaults()
        out_paths = aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id,
            sessions=[d1, d2],
            resolver=resolver,
            params=params,
            animal_info=animal_info,
        )
        assert set(out_paths.keys()) == {"1..2"}
        path = out_paths["1..2"]
        assert path.exists()
        # Read metadata back via pyarrow.
        table = pq.read_table(str(path))
        meta_raw = table.schema.metadata or {}
        meta = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in meta_raw.items()
            if not k.startswith(b"pandas")
        }
        assert meta["animal"] == animal_info.animal_id
        assert meta["rel_day_bin_label"] == "1..2"
        assert meta["bin_days"] == "2"
        assert meta["n_sessions"] == "2"
        assert json.loads(meta["sessions_iso_dates"]) == [
            d1.isoformat(), d2.isoformat(),
        ]
        assert meta["aggregation_function"] == "mean"
        assert meta["feature_extraction_version"] == "v7a.3"
        assert meta["interpolation_version"] == "v5p3"
        assert meta["day_binned_version"] == DAY_BINNED_VERSION
        assert meta["emit_sem"] == "True"
        assert meta["emit_n_support_sessions"] == "True"
        assert meta["stroke_date"] == animal_info.stroke_date.isoformat()

    def test_one_session_per_bin_passes_through(self, tmp_path):
        """Single session → mean equals input; SEM is NaN (n_support=1)."""
        animal_info = _make_animal_info(bin_days=2)
        resolver = PathResolver(output_root=tmp_path)
        d1 = animal_info.stroke_date + datetime.timedelta(days=1)
        _seed_session(
            resolver, animal_info.animal_id, d1,
            fill={
                "lick_rate_per_t": 5.0,
                "ili_within_bout_rate_per_t": 7.0,
                "p_lick_per_t": 0.4,
                "p_within_bout_per_t": 0.6,
            },
        )
        out_paths = aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id,
            sessions=[d1],
            resolver=resolver,
            animal_info=animal_info,
        )
        df = pq.read_table(str(out_paths["1..2"])).to_pandas()
        assert (df["lick_rate_per_t_mean"] == 5.0).all()
        assert (df["bout_rate_mean_hz_mean"] == 7.0).all()
        assert df["lick_rate_per_t_sem"].isna().all()
        assert (df["lick_rate_per_t_n_support_sessions"] == 1).all()


# ============================================================================
# Overwrite semantics
# ============================================================================


class TestOverwriteSemantics:
    def test_skip_returns_existing_when_all_present(self, tmp_path):
        """Re-running with overwrite='skip' AND all output files present
        returns paths immediately without rewriting. Sentinel-content
        detection (mtime is unreliable on Windows for back-to-back writes
        — NTFS rounds to ~100 ns, finer than one aggregation cycle)."""
        animal_info = _make_animal_info(bin_days=2)
        resolver = PathResolver(output_root=tmp_path)
        d1 = animal_info.stroke_date + datetime.timedelta(days=1)
        _seed_session(resolver, animal_info.animal_id, d1)
        out1 = aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id,
            sessions=[d1],
            resolver=resolver,
            animal_info=animal_info,
        )
        path = out1["1..2"]

        # Stomp the on-disk file with a sentinel schema; if skip-mode
        # rewrites, the sentinel column would disappear.
        sentinel_table = pa.table({"sentinel": [1, 2, 3]})
        pq.write_table(sentinel_table, str(path), compression="snappy")

        out2 = aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id,
            sessions=[d1],
            resolver=resolver,
            animal_info=animal_info,
            overwrite="skip",
        )
        assert out2 == out1
        df_after = pq.read_table(str(path)).to_pandas()
        assert "sentinel" in df_after.columns
        assert "lick_rate_per_t_mean" not in df_after.columns

    def test_force_rewrites(self, tmp_path):
        """overwrite='force' always rewrites."""
        animal_info = _make_animal_info(bin_days=2)
        resolver = PathResolver(output_root=tmp_path)
        d1 = animal_info.stroke_date + datetime.timedelta(days=1)
        _seed_session(resolver, animal_info.animal_id, d1)
        aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id, sessions=[d1], resolver=resolver,
            animal_info=animal_info,
        )
        path = resolver.tongue_pertrial_licking_dynamics_day_binned_parquet(
            animal_info.animal_id, "1..2",
        )
        # Stomp file with a sentinel.
        pq.write_table(
            pa.table({"sentinel": [1]}), str(path), compression="snappy",
        )
        aggregate_licking_dynamics_day_binned(
            animal=animal_info.animal_id, sessions=[d1], resolver=resolver,
            animal_info=animal_info, overwrite="force",
        )
        df_after = pq.read_table(str(path)).to_pandas()
        assert "sentinel" not in df_after.columns
        assert "lick_rate_per_t_mean" in df_after.columns


# ============================================================================
# Schema guards
# ============================================================================


class TestSchemaGuard:
    def test_heterogeneous_grids_raise(self):
        """Sessions with mismatched (side, timebin_ms) grids fail loud —
        the day-binner cannot meaningfully aggregate across them."""
        s1 = _make_session_traces_df(timebins_ms=np.array([0.0, 20.0, 40.0]))
        s2 = _make_session_traces_df(
            timebins_ms=np.array([0.0, 20.0, 40.0, 60.0]),
        )
        with pytest.raises(ValueError, match="grid differs"):
            _aggregate_across_sessions(
                [s1, s2], emit_sem=False, emit_n_support_sessions=False,
            )

    def test_missing_metric_column_raises(self):
        """Per-session DataFrame missing one of the 4 expected metric
        columns → KeyError naming the missing column."""
        s1 = _make_session_traces_df()
        s1_bad = s1.drop(columns=["p_lick_per_t"])
        with pytest.raises(KeyError, match="p_lick_per_t"):
            _aggregate_across_sessions(
                [s1_bad], emit_sem=False, emit_n_support_sessions=False,
            )
