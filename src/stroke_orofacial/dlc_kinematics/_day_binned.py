"""Phase 7a.4 — Cell 42 day-binned cross-session traces aggregator.

.. deprecated:: chore substrate-routing-and-secondary-spout-per-half-fix (2026-05-31)
    This aggregator writes ``dlc_kinematics/licking_dynamics/day_binned/`` — a
    WRITE-ONLY ORPHAN. No code reads the parquet: the binned figure renderers in
    ``mean_sem_visual`` + ``tongue_angle_cohort`` do their own rel-day binning
    from the trace (they import only the :func:`_compute_rel_day_bin_label`
    helper below, not this parquet). The stale output dir was deleted and the
    sole producer call (``scripts/phase_7c2/reemit_cohort_aggregates.py`` E4
    stage) disabled, per Priya 2026-05-31. The functions are retained for the
    ``_compute_rel_day_bin_label`` helper (still imported elsewhere) and test
    coverage; do NOT re-wire :func:`aggregate_licking_dynamics_day_binned` into a
    production driver without a confirmed downstream consumer.

Ported from the canonical tongue notebook
(``20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb``,
SHA256 ``ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643``,
Cell 42 day-binning block at the bottom of the cell — vendored at
``docs/legacy_snippets/tongue_pertrial_features.py`` lines 3635-3691).

Inputs
------
- Per-session × side licking-dynamics traces parquet (7a.3 V3 emit, schema
  locked): wide-form, one row per ``(timebin_ms, side)``, value columns
  ``lick_rate_per_t``, ``ili_within_bout_rate_per_t``, ``p_lick_per_t``,
  ``p_within_bout_per_t``.
- Per-animal :class:`AnimalInfo` (provides ``bin_days`` and ``stroke_date``
  used to anchor the rel_day binning).

Outputs (one parquet per ``(animal, rel_day_bin_label)``)
---------------------------------------------------------
``<outputs>/dlc_kinematics/licking_dynamics/day_binned/<animal>/<label>.parquet``,
with one row per ``(side, timebin_ms)`` and value columns:

- ``lick_rate_per_t_mean`` / ``lick_rate_per_t_sem`` /
  ``lick_rate_per_t_n_support_sessions``
- ``bout_rate_mean_hz_mean`` / ``bout_rate_mean_hz_sem`` /
  ``bout_rate_mean_hz_n_support_sessions``  (renamed from 7a.3's
  ``ili_within_bout_rate_per_t`` to a more descriptive day-binned name —
  Task 3 spec 2026-04-30)
- ``p_lick_per_t_mean`` / ``p_lick_per_t_sem`` /
  ``p_lick_per_t_n_support_sessions``
- ``p_within_bout_per_t_mean`` / ``p_within_bout_per_t_sem`` /
  ``p_within_bout_per_t_n_support_sessions``

``*_sem`` columns are gated by ``day_binned.emit_sem`` (default true).
``*_n_support_sessions`` columns are gated by
``day_binned.emit_n_support_sessions`` (default true).

The legacy ``f"{lo}..{hi}"`` rel_day_bin label format is preserved
(literal ``..`` in the filename — NTFS-legal, Task 1.5a audit §9).

Critical asymmetry (preserved from 7a.3 V3, do NOT alter)
---------------------------------------------------------
``lick_rate_per_t`` is **already per-trial pre-smoothed** in the 7a.3
session-traces input (Gaussian σ=50 ms applied per-trial before the
nanmean across trials). The other 3 metrics (``ili_within_bout_rate_per_t``,
``p_lick_per_t``, ``p_within_bout_per_t``) are NOT smoothed at the
session level. The day-binned aggregator does NOT apply additional
smoothing to ANY metric; legacy plot-time smoothing on the un-smoothed
3 is the consumer's responsibility (downstream of this aggregator).
Re-smoothing ``lick_rate_per_t`` here would double-smooth it.

SEM formula
-----------
The default-mode SEM uses unbiased standard deviation
(``np.nanstd(values, axis=session_axis, ddof=1)``) divided by
``sqrt(n_support_sessions)`` per timebin (= number of sessions
contributing finite values, NOT total sessions in the bin). This is
the statistically correct estimator. Legacy Cell 42 used ``ddof=0`` and
divided by ``sqrt(max(1, n_total_sessions_in_bin))`` — the parity
harness applies the known correction factor at compare time
(``SEM(ddof=0) = SEM(ddof=1) * sqrt((n-1)/n)``); no config knob here.
"""

from __future__ import annotations

import datetime
import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver

# Version stamps. ``DAY_BINNED_VERSION`` is the schema version of this
# module's output; bumping requires a DECISIONS entry. The
# ``feature_extraction_version`` / ``interpolation_version`` carried in
# file metadata are passed through from the input session-traces parquet
# (single source of truth: 7a.3 V3 emit).
DAY_BINNED_VERSION: str = "v7a.4"

# Metric column mapping — Task 3 spec 2026-04-30. The day-binned output
# renames ``ili_within_bout_rate_per_t`` (the 7a.3 input) to
# ``bout_rate_mean_hz`` (more descriptive in the cross-session context;
# closer to the legacy CSV's metric name). Other 3 columns keep their
# 7a.3 names for traceability. Order matches the 7a.3 emit set.
_METRICS: tuple[tuple[str, str], ...] = (
    # (input column name, output base name)
    ("lick_rate_per_t",                "lick_rate_per_t"),
    ("ili_within_bout_rate_per_t",     "bout_rate_mean_hz"),
    ("p_lick_per_t",                   "p_lick_per_t"),
    ("p_within_bout_per_t",            "p_within_bout_per_t"),
)


# ============================================================================
# Public API
# ============================================================================


@dataclass
class DayBinnedResult:
    """In-memory container for a day-binned aggregation across sessions.

    Attributes
    ----------
    by_rel_day_bin
        ``{rel_day_bin_label: wide_form_DataFrame}``. One DataFrame per
        rel_day_bin; each carries one row per ``(side, timebin_ms)``.
    metadata
        ``{rel_day_bin_label: {key: str_value}}``. Per-bin file-level
        metadata strings to embed in the output parquet schema.
    """

    by_rel_day_bin: dict[str, pd.DataFrame]
    metadata: dict[str, dict[str, str]]


def aggregate_licking_dynamics_day_binned(
    animal: str,
    sessions: Sequence[datetime.date],
    resolver: PathResolver,
    *,
    params: dict[str, Any] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> dict[str, Path]:
    """Aggregate per-session licking-dynamics traces into day-binned parquets.

    Reads the 7a.3 V3 per-session traces parquet for each session in
    ``sessions``, groups by ``(rel_day_bin_label, side, timebin_ms)``,
    and emits one parquet per rel_day_bin under
    ``<outputs>/dlc_kinematics/licking_dynamics/day_binned/<animal>/<label>.parquet``.

    Parameters
    ----------
    animal
        Animal identifier (e.g. ``"PS46"``).
    sessions
        Session dates to include. Sessions outside the
        ``[stroke_date - bin_days*K, ...]`` range still get a label
        assigned by :func:`_compute_rel_day_bin_label`; the caller
        is responsible for any pre-filtering (typical use: pass the
        full cohort date list).
    resolver
        Configured PathResolver. Reads inputs via
        :meth:`PathResolver.tongue_pertrial_licking_dynamics_traces_parquet`;
        writes outputs via
        :meth:`PathResolver.tongue_pertrial_licking_dynamics_day_binned_parquet`.
    params
        Loaded :func:`load_defaults` block. If ``None``, loads the repo
        default. Reads ``dlc_kinematics.tongue_pertrial.day_binned`` keys
        ``aggregation_function``, ``emit_sem``, ``emit_n_support_sessions``.
    overwrite
        ``"skip"`` returns existing paths if ALL labels' parquets already
        exist; if any are missing, all are recomputed (the per-bin
        aggregation is cheap once sessions are loaded). ``"force"``
        always rewrites.
    animal_info
        Optional :class:`AnimalInfo`. If ``None``, loaded via
        :func:`get_animal`. Provides ``bin_days`` and ``stroke_date``.

    Returns
    -------
    dict[str, Path]
        ``{rel_day_bin_label: parquet_path}``. Sorted by label.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(f"overwrite must be 'skip' or 'force'; got {overwrite!r}.")

    if animal_info is None:
        animal_info = get_animal(animal)
    if params is None:
        params = load_defaults()

    db_params = (
        params["dlc_kinematics"]["tongue_pertrial"]["day_binned"]
    )
    if db_params["aggregation_function"] != "mean":
        raise NotImplementedError(
            f"Only aggregation_function='mean' is implemented; got "
            f"{db_params['aggregation_function']!r}."
        )

    # Group sessions by their rel_day_bin label.
    sessions_by_bin: dict[str, list[datetime.date]] = {}
    for session_date in sessions:
        label = _compute_rel_day_bin_label(
            session_date=session_date,
            d0=animal_info.stroke_date,
            bin_days=animal_info.bin_days,
        )
        sessions_by_bin.setdefault(label, []).append(session_date)
    # Sort each bucket; deterministic write order.
    for label in sessions_by_bin:
        sessions_by_bin[label].sort()

    out_paths = {
        label: resolver.tongue_pertrial_licking_dynamics_day_binned_parquet(
            animal, label,
        )
        for label in sorted(sessions_by_bin)
    }

    if overwrite == "skip" and all(p.exists() for p in out_paths.values()):
        return out_paths

    # Load every session's traces once; segregate by bin during aggregation.
    per_session_traces: dict[datetime.date, pd.DataFrame] = {}
    upstream_versions: dict[str, str] = {}
    for session_date in sorted(set(sessions)):
        df, file_meta = _load_session_traces(animal, session_date, resolver)
        per_session_traces[session_date] = df
        # Capture upstream version stamps from the first session; verify
        # the rest match (mismatched versions across an animal's cohort
        # is a misconfiguration we want to fail loud on).
        for key in ("feature_extraction_version", "interpolation_version"):
            v = file_meta.get(key, "")
            if key not in upstream_versions:
                upstream_versions[key] = v
            elif upstream_versions[key] != v:
                raise RuntimeError(
                    f"{animal} session {session_date.isoformat()}: "
                    f"upstream {key}={v!r} differs from earlier "
                    f"sessions ({upstream_versions[key]!r}). Cross-version "
                    f"day-binning is not supported."
                )

    emit_sem = bool(db_params["emit_sem"])
    emit_nss = bool(db_params["emit_n_support_sessions"])

    for label, dates in sessions_by_bin.items():
        bin_dfs = [per_session_traces[d] for d in dates]
        wide_df = _aggregate_across_sessions(
            bin_dfs,
            emit_sem=emit_sem,
            emit_n_support_sessions=emit_nss,
        )
        meta = {
            "animal": animal,
            "rel_day_bin_label": label,
            "bin_days": str(int(animal_info.bin_days)),
            "stroke_date": animal_info.stroke_date.isoformat(),
            "n_sessions": str(int(len(dates))),
            "sessions_iso_dates": json.dumps(
                [d.isoformat() for d in dates]
            ),
            "aggregation_function": str(db_params["aggregation_function"]),
            "feature_extraction_version": upstream_versions.get(
                "feature_extraction_version", "",
            ),
            "interpolation_version": upstream_versions.get(
                "interpolation_version", "",
            ),
            "day_binned_version": DAY_BINNED_VERSION,
            "emit_sem": str(emit_sem),
            "emit_n_support_sessions": str(emit_nss),
        }
        _write_day_binned_parquet_atomic(out_paths[label], wide_df, meta)

    return out_paths


def aggregate_licking_dynamics_day_binned_by_animal(
    animal: str,
    resolver: PathResolver,
    *,
    sessions: Sequence[datetime.date] | None = None,
    params: dict[str, Any] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path]:
    """Convenience wrapper: derive sessions from existing per-session parquets.

    Globs the
    ``<outputs>/dlc_kinematics/licking_dynamics/traces/<animal>/`` directory
    for ``%Y%m%d.parquet`` filenames and uses those as the session list.
    Useful for cohort-wide runs where the caller doesn't pre-track which
    sessions emitted successfully.

    If ``sessions`` is provided explicitly, this wrapper just forwards to
    :func:`aggregate_licking_dynamics_day_binned`.
    """
    if sessions is None:
        animal_info = get_animal(animal)
        traces_dir = (
            resolver.tongue_pertrial_licking_dynamics_traces_parquet(
                animal, animal_info.stroke_date,
            ).parent
        )
        if not traces_dir.exists():
            raise FileNotFoundError(
                f"No per-session traces directory for {animal!r} at "
                f"{traces_dir}. Run build_tongue_pertrial first."
            )
        sessions = sorted(
            datetime.datetime.strptime(p.stem, "%Y%m%d").date()
            for p in traces_dir.glob("*.parquet")
        )
        if not sessions:
            raise FileNotFoundError(
                f"No per-session traces parquets found under {traces_dir}."
            )
    else:
        animal_info = None
    return aggregate_licking_dynamics_day_binned(
        animal=animal,
        sessions=sessions,
        resolver=resolver,
        params=params,
        overwrite=overwrite,
        animal_info=animal_info,
    )


# ============================================================================
# Helpers
# ============================================================================


def _compute_rel_day_bin_label(
    session_date: datetime.date,
    d0: datetime.date,
    bin_days: int,
) -> str:
    """Return the legacy ``f"{lo}..{hi}"`` rel_day_bin label for one session.

    Anchored on ``rel_day=0`` (the day of stroke induction itself, which
    is the LAST PRE-STROKE SESSION per the ``stroke_date`` convention).
    For ``B = bin_days``:

    - ``rel_day <= 0`` (pre): last pre-bin is ``[-(B-1), 0]``; older bins
      decrement by ``B``.
    - ``rel_day >= 1`` (post): first post-bin is ``[1, B]``; later bins
      increment by ``B``.

    Bit-identical to legacy Cell 50's ``_bin_rel_day`` helper (lines
    4026-4037 of the vendored snippet) and to legacy Cell 42's
    ``_rel_day_bin_edges`` + ``_assign_rel_day_to_bin`` pair.
    """
    if not isinstance(bin_days, int) or isinstance(bin_days, bool):
        raise TypeError(
            f"bin_days must be int; got {type(bin_days).__name__}."
        )
    if bin_days < 1:
        raise ValueError(f"bin_days must be >= 1; got {bin_days}.")
    rel_day = (session_date - d0).days
    b = int(bin_days)
    if rel_day >= 1:
        lo = ((rel_day - 1) // b) * b + 1
        hi = lo + b - 1
    else:
        # Mirror Cell 50: end = -((|rel_day|) // b) * b; start = end - (b-1).
        hi = -((abs(rel_day)) // b) * b
        lo = hi - (b - 1)
    return f"{lo}..{hi}"


def _load_session_traces(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Read 7a.3 V3 per-session licking-dynamics traces parquet + metadata.

    Returns
    -------
    df : DataFrame
        Wide-form, one row per ``(timebin_ms, side)``, 6 columns total.
    file_meta : dict[str, str]
        File-level pyarrow schema metadata (decoded UTF-8). Keys include
        ``feature_extraction_version`` / ``interpolation_version`` which
        the day-binner propagates into its own emit metadata.
    """
    path = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
        animal, date,
    )
    if not path.exists():
        raise FileNotFoundError(
            f"Missing 7a.3 per-session traces parquet for {animal} "
            f"{date.isoformat()}: {path}"
        )
    table = pq.read_table(str(path))
    df = table.to_pandas()
    raw_meta = table.schema.metadata or {}
    file_meta = {
        k.decode("utf-8"): v.decode("utf-8")
        for k, v in raw_meta.items()
        # Skip pandas's own internal schema metadata (binary blob, not ours).
        if not k.startswith(b"pandas")
    }
    return df, file_meta


def _aggregate_across_sessions(
    per_session_dfs: list[pd.DataFrame],
    *,
    emit_sem: bool,
    emit_n_support_sessions: bool,
) -> pd.DataFrame:
    """Aggregate a list of per-session traces DataFrames into wide-form output.

    Each input DataFrame is expected to have columns
    ``timebin_ms`` (float64), ``side`` (str), and the 4 metric columns
    in :data:`_METRICS`. All sessions in the input list MUST share the
    same ``(timebin_ms, side)`` grid (this is true for any same-animal
    cohort emitted by 7a.3 V3 with stable detect/apply windows).

    Output: one row per ``(side, timebin_ms)``, sorted by ``(side, timebin_ms)``,
    with ``<base>_mean`` / optional ``<base>_sem`` / optional
    ``<base>_n_support_sessions`` columns per metric.
    """
    if not per_session_dfs:
        raise ValueError(
            "_aggregate_across_sessions called with empty session list."
        )

    # Establish the (side, timebin_ms) grid from the first session and
    # verify every other session matches. The 7a.3 V3 emit is uniform
    # across the cohort by construction, but we fail loud on any drift.
    ref = per_session_dfs[0]
    for col in ("timebin_ms", "side"):
        if col not in ref.columns:
            raise KeyError(
                f"Per-session traces DataFrame missing required column "
                f"{col!r}. Expected the 7a.3 V3 schema."
            )
    for input_col, _ in _METRICS:
        if input_col not in ref.columns:
            raise KeyError(
                f"Per-session traces DataFrame missing required metric "
                f"column {input_col!r}."
            )
    ref_grid = (
        ref[["side", "timebin_ms"]]
        .sort_values(["side", "timebin_ms"], kind="mergesort")
        .reset_index(drop=True)
    )
    for i, df in enumerate(per_session_dfs[1:], start=1):
        grid = (
            df[["side", "timebin_ms"]]
            .sort_values(["side", "timebin_ms"], kind="mergesort")
            .reset_index(drop=True)
        )
        if not grid.equals(ref_grid):
            raise ValueError(
                f"Session {i} (side, timebin_ms) grid differs from session "
                f"0 — heterogeneous detect/apply windows are not supported "
                f"by the day-binner."
            )

    # Sort each session by (side, timebin_ms) and stack into a 3D array
    # of shape (n_sessions, n_rows, n_metrics). Then aggregate along
    # axis=0 (the session axis).
    n_rows = len(ref_grid)
    n_sessions = len(per_session_dfs)
    n_metrics = len(_METRICS)
    stacked = np.full((n_sessions, n_rows, n_metrics), np.nan, dtype=np.float64)
    for s_idx, df in enumerate(per_session_dfs):
        ordered = (
            df.sort_values(["side", "timebin_ms"], kind="mergesort")
            .reset_index(drop=True)
        )
        for m_idx, (input_col, _) in enumerate(_METRICS):
            stacked[s_idx, :, m_idx] = ordered[input_col].to_numpy(
                dtype=np.float64,
            )

    # Per-cell aggregation: mean (nan-aware), SEM (nan-aware, ddof=1,
    # divided by sqrt(n_finite)), and per-cell n_support count.
    out = {
        "timebin_ms": ref_grid["timebin_ms"].to_numpy(dtype=np.float64),
        "side": ref_grid["side"].to_numpy(),
    }
    n_support = np.sum(np.isfinite(stacked), axis=0).astype(np.int64)
    with np.errstate(invalid="ignore", divide="ignore"), \
         warnings.catch_warnings():
        # ddof=1 unbiased SEM produces benign "Degrees of freedom <= 0"
        # warnings when n_support < 2 and "Mean of empty slice" when
        # n_support == 0 — the np.where mask below assigns NaN to those
        # cells, so the warnings are correct-but-noisy. Suppress here
        # rather than in the test fixtures.
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning,
            message=r"(Mean of empty slice|Degrees of freedom <= 0)",
        )
        means = np.nanmean(stacked, axis=0)
        stds = np.nanstd(stacked, axis=0, ddof=1)
        sems = np.where(
            n_support >= 2,
            stds / np.sqrt(np.maximum(n_support, 1)),
            np.nan,
        )
    # Where every session was NaN, nanmean returns NaN with a warning;
    # the np.where call above guarantees SEM is NaN for n_support < 2.
    # No additional masking needed for means.

    for m_idx, (_, out_base) in enumerate(_METRICS):
        out[f"{out_base}_mean"] = means[:, m_idx].astype(np.float64)
        if emit_sem:
            out[f"{out_base}_sem"] = sems[:, m_idx].astype(np.float64)
        if emit_n_support_sessions:
            out[f"{out_base}_n_support_sessions"] = (
                n_support[:, m_idx].astype(np.int64)
            )

    return pd.DataFrame(out)


def _write_day_binned_parquet_atomic(
    path: Path,
    df: pd.DataFrame,
    metadata: dict[str, str],
) -> None:
    """Atomic parquet writer for the day-binned emit.

    Vendored locally (rather than importing from
    ``stroke_orofacial.dlc_kinematics._writers``) to keep the 7a.3
    ``_writers`` module untouched per the Phase 7a.4 constraint that
    7a.3 V3 modules stay locked. The pattern (pyarrow snappy + temp +
    os.replace + bytes-encoded schema metadata) mirrors
    ``_writers._write_traces_parquet_atomic`` exactly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_bytes = {
        k.encode("utf-8"): v.encode("utf-8") for k, v in metadata.items()
    }
    existing = table.schema.metadata or {}
    merged = {
        **{bytes(k): bytes(v) for k, v in existing.items()},
        **meta_bytes,
    }
    table = table.replace_schema_metadata(merged)
    tmp_path = path.with_name(path.name + ".tmp")
    pq.write_table(table, str(tmp_path), compression="snappy")
    os.replace(tmp_path, path)
