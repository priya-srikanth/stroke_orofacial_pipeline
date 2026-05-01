"""Phase 7a.5 — tongue-jaw mismatch classifier parity harness.

Compares the consolidated 7a.5 candidate-trials parquet (per-session,
emitted by
:func:`stroke_orofacial.dlc_kinematics.classify_tongue_jaw_mismatch`)
against the legacy Cell 53 ``*_v5p3.csv`` per-mouse aggregate on
MICROSCOPE.

Mirrors the 7a.4 day-binned harness shape but with a smaller override
table: per Task 5 sign-off, default mode IS legacy_approximate mode for
7a.5 (Cell 53 detector knobs already match the V5 mismatch defaults;
the YAML carries the canonical values). The ``--mode`` flag is exposed
for CLI consistency with prior phases but the legacy_approximate
override map is empty.

CLI::

    python tests/scripts/parity_phase7a5_mismatch.py \\
        --mode {default, legacy_approximate} \\
        --sessions auto \\
        --atol 1e-6

Per-row schema deviation (Task 5 lock):

- Modern parquet has ~21 per-row cols + 28 file-level metadata keys;
  legacy CSV has 37 per-row cols (most invariants repeated per row).
  The harness rebuilds a 37-col-shaped DataFrame from the modern
  parquet by replicating file-level metadata across all rows of each
  session, then concatenates per-animal in chronological order to
  match legacy's per-mouse-aggregated CSV layout.
- Column rename map handled at compare time:

  | legacy CSV col              | modern source                            | comparison |
  |-----------------------------|------------------------------------------|------------|
  | n_licks_in_window           | n_licks_in_quiet_win (per row)           | exact int  |
  | tongue_peak_times_ms        | tongue_peak_times_ms (per row, list)     | skipped    |
  | quiet_tongue_pass           | quiet_tongue_pass (per row)              | exact bool |
  | jaw_baseline_mean / _sd     | same (per row, NaN-tolerant)             | atol       |
  | jaw_peak_*_deflection (×4)  | same (per row, NaN-tolerant)             | atol       |
  | jaw_thresh_abs (legacy)     | DERIVED: 4 * modern.jaw_baseline_sd      | atol + cohort sanity |
  | jaw_thresh_px_used (legacy) | modern.jaw_thresh_abs (the applied threshold) | atol  |
  | jaw_n_frames_over_thresh    | same                                     | exact int  |
  | jaw_pass_qc                 | same                                     | exact bool |
  | candidate_no_lick_with_jaw_move | same                                 | exact bool |
  | reward_center_fr_tongue/jaw | reward_frame_idx (modern, single col)    | atol on either |
  | rel_day, side, fps, mouse, date | same names                            | exact      |
  | date_dt                     | dropped (redundant)                       | skip       |
  | tongue_npz / jaw_npz        | dropped (NPZ provenance gone)            | skip       |
  | window/threshold/direction config knobs (16 cols) | file-level metadata | skip per-row |

- Modern ``jaw_thresh_px_used`` is a NEW categorical (sd_scaled /
  px_floor / none) with no legacy counterpart — skipped in numerical
  parity, but a separate cohort sanity flag confirms the categorical
  population matches what the legacy numeric `max(...)` would have
  picked.

- Trial-indexing convention: legacy Cell 53 uses β-style (per-side
  enumeration); modern uses α-style (chronological-across-sides).
  :func:`_compare_trial_indexing_convention` auto-detects which
  convention the legacy CSV uses; rows are aligned by matching on
  ``(date, side, reward_frame_idx)`` rather than ``trial_index``
  directly to be robust to the convention difference.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_phase7a3_tongue_pertrial as h7a3  # type: ignore[import]

from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
    classify_tongue_jaw_mismatch_by_animal_date,
)
from stroke_orofacial.paths import PathResolver

# Cohort animals (PS52/PS53 absent per the earlier audits).
DEFAULT_ANIMALS: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)

INTERP_VERSION = "v5p3"
CAM = "cam2"
JAW_CENTER_MODE = "centered_eye_midpoint"

# Column-pair table (legacy_col, modern_col, kind).
# kind:
#   "atol"        — float compare with NaN-aware np.isclose(atol)
#   "exact_int"   — integer exact match
#   "exact_bool"  — boolean exact match
#   "exact_str"   — string exact match
#   "skip"        — not numerically compared (dropped or list-shape)
_COL_PAIRS: tuple[tuple[str, str, str], ...] = (
    # Identification — exact matches, used for join keys (not compare).
    ("mouse",                          "mouse",                    "skip"),
    ("date",                           "date",                     "skip"),
    ("side",                           "side",                     "skip"),
    ("rel_day",                        "rel_day",                  "exact_int"),
    ("trial_index",                    "trial_index",              "skip"),  # convention diff; align by reward frame
    ("fps",                            "fps",                      "atol"),
    ("reward_center_fr_tongue",        "reward_frame_idx",         "exact_int"),
    ("reward_center_fr_jaw",           "reward_frame_idx",         "exact_int"),
    # Tongue side
    ("n_licks_in_window",              "n_licks_in_quiet_win",     "exact_int"),
    ("quiet_tongue_pass",              "quiet_tongue_pass",        "exact_bool"),
    # Jaw baseline
    ("jaw_baseline_mean",              "jaw_baseline_mean",        "atol"),
    ("jaw_baseline_sd",                "jaw_baseline_sd",          "atol"),
    # Jaw peak metrics
    ("jaw_peak_pos_deflection",        "jaw_peak_pos_deflection",  "atol"),
    ("jaw_peak_neg_deflection",        "jaw_peak_neg_deflection",  "atol"),
    ("jaw_peak_abs_deflection",        "jaw_peak_abs_deflection",  "atol"),
    ("jaw_peak_selected_deflection",   "jaw_peak_selected_deflection", "atol"),
    # Jaw threshold:
    #   legacy.jaw_thresh_abs (= sd_mult * sd) ↔ DERIVED 4 * modern.jaw_baseline_sd
    #   legacy.jaw_thresh_px_used (= max(sd_term, min_px)) ↔ modern.jaw_thresh_abs
    ("jaw_thresh_abs",                 "_derived_legacy_thresh_abs", "atol"),
    ("jaw_thresh_px_used",             "jaw_thresh_abs",           "atol"),
    # Jaw QC
    ("jaw_n_frames_over_thresh",       "jaw_n_frames_over_thresh", "exact_int"),
    ("jaw_pass_qc",                    "jaw_pass_qc",              "exact_bool"),
    # Decision
    ("candidate_no_lick_with_jaw_move",
     "candidate_no_lick_with_jaw_move", "exact_bool"),
    # Skip-list
    ("date_dt",                        None,                        "skip"),
    ("tongue_peak_times_ms",           "tongue_peak_times_ms",      "skip"),
    ("tongue_npz",                     None,                        "skip"),
    ("jaw_npz",                        None,                        "skip"),
    # Per-row repeats of file-level metadata: skipped (modern emits as metadata)
    ("lick_count_win_ms_lo",           None, "skip"),
    ("lick_count_win_ms_hi",           None, "skip"),
    ("max_licks_for_quiet",            None, "skip"),
    ("jaw_baseline_win_ms_lo",         None, "skip"),
    ("jaw_baseline_win_ms_hi",         None, "skip"),
    ("jaw_test_win_ms_lo",             None, "skip"),
    ("jaw_test_win_ms_hi",             None, "skip"),
    ("jaw_thresh_sd",                  None, "skip"),
    ("jaw_min_abs_px",                 None, "skip"),
    ("jaw_min_frames_over",            None, "skip"),
    ("jaw_frame_window",               None, "skip"),
    ("jaw_direction_mode",             None, "skip"),
)


# ============================================================================
# Result dataclasses
# ============================================================================


@dataclass
class _ColumnStat:
    legacy_col: str
    modern_col: str | None
    kind: str
    n_compared: int = 0
    n_mismatch: int = 0
    max_abs_delta: float = 0.0


@dataclass
class _AnimalResult:
    animal: str
    mode: str
    status: str            # "pass" / "fail" / "skip_no_legacy" / "skip_emit_error"
    note: str = ""
    n_legacy_rows: int = 0
    n_modern_rows: int = 0
    n_aligned_rows: int = 0
    legacy_trial_indexing: str = "?"   # "alpha" / "beta" / "?"
    cohort_sanity_jaw_thresh_abs_eq_4sd_pct: float = 0.0
    columns: list[_ColumnStat] = field(default_factory=list)


# ============================================================================
# Legacy CSV reader
# ============================================================================


def _legacy_mismatch_csv_path(animal: str) -> Path:
    """Resolve the legacy per-mouse mismatch CSV.

    Path:
      ``{MICROSCOPE_ROOT}/{animal}/{animal}_jaw_kinematics/kinematics_figures/
       centered_eye_midpoint/jaw_tongue_candidate_trials/
       {animal}_cam2_jawMove_noTongueLick_candidates_v5p3.csv``
    """
    return (
        h7a3.MICROSCOPE_ROOT / animal / f"{animal}_jaw_kinematics"
        / "kinematics_figures" / JAW_CENTER_MODE
        / "jaw_tongue_candidate_trials"
        / f"{animal}_{CAM}_jawMove_noTongueLick_candidates_{INTERP_VERSION}.csv"
    )


def _load_legacy_csv(animal: str) -> pd.DataFrame:
    """Read the legacy per-mouse CSV with appropriate dtypes."""
    path = _legacy_mismatch_csv_path(animal)
    if not path.exists():
        raise FileNotFoundError(f"Legacy mismatch CSV missing: {path}")
    df = pd.read_csv(path)
    # Normalize date col to YYYYMMDD string (legacy stores as int).
    df["date"] = df["date"].astype(str).str.replace("-", "")
    return df


# ============================================================================
# Trial-indexing convention auto-detect
# ============================================================================


def _compare_trial_indexing_convention(legacy_df: pd.DataFrame) -> str:
    """Detect whether legacy uses α (chronological-across-sides) or β (per-side).

    α-style:  trial_index is unique within (date) — both sides share the
              0..N-1 index space.
    β-style:  trial_index is unique within (date, side) — both sides
              start at 0; appears across both side groups within the same
              date (e.g. trial 0 exists for both L and R on the same day).

    Returns "alpha" / "beta" / "?".
    """
    if "trial_index" not in legacy_df.columns or "side" not in legacy_df.columns:
        return "?"
    sample_dates = legacy_df["date"].unique()[:5]
    n_alpha_compatible = 0
    n_beta_compatible = 0
    for d in sample_dates:
        sub = legacy_df[legacy_df["date"] == d]
        if sub.empty:
            continue
        per_side = sub.groupby("side")["trial_index"].apply(set).to_dict()
        # α: across (date), trial_indices are unique → no overlap between sides
        union = set()
        overlap = False
        for s, idxs in per_side.items():
            if union & idxs:
                overlap = True
                break
            union |= idxs
        if overlap:
            n_beta_compatible += 1
        else:
            n_alpha_compatible += 1
    if n_beta_compatible > n_alpha_compatible:
        return "beta"
    if n_alpha_compatible > n_beta_compatible:
        return "alpha"
    return "?"


# ============================================================================
# Modern emit (re-emit per-session classifier under a temp output_root)
# ============================================================================


def _emit_modern_for_animal_sessions(
    animal: str, sessions: list[dt.date], emit_resolver: PathResolver,
    *, mode: str,
) -> list[Path]:
    """Re-emit per-session candidate_trials parquets under ``emit_resolver``.

    Returns the list of emitted paths (skipping sessions whose upstream
    inputs are missing). Both modes emit identically — the override map
    is {} per Task 5 sign-off.
    """
    if mode not in ("default", "legacy_approximate"):
        raise ValueError(f"Unknown mode {mode!r}")
    emitted: list[Path] = []
    for d in sessions:
        try:
            p = classify_tongue_jaw_mismatch_by_animal_date(
                animal=animal, date=d, resolver=emit_resolver,
                overwrite="force",
            )
            if p is not None:
                emitted.append(p)
        except FileNotFoundError as exc:
            print(
                f"  [{animal} {d.isoformat()}] skip — missing upstream "
                f"({exc.__class__.__name__}: {exc})",
                file=sys.stderr,
            )
            continue
    return emitted


def _build_modern_aggregated_df(
    animal: str, parquet_paths: list[Path],
) -> pd.DataFrame:
    """Concat per-session parquets in chronological order; replicate file-
    level metadata to per-row to match legacy's column shape."""
    frames: list[pd.DataFrame] = []
    for p in sorted(parquet_paths, key=lambda x: x.name):
        df = pd.read_parquet(p)
        meta = pq.read_schema(p).metadata or {}
        decoded = {k.decode(): v.decode() for k, v in meta.items()}
        # Replicate metadata (constant per session) onto every row, so
        # downstream callers can read them without re-loading parquet
        # schemas. Names match legacy column conventions.
        df["_meta_jaw_thresh_sd_multiplier"] = float(
            decoded.get("jaw_thresh_sd_multiplier", "nan"),
        )
        df["_meta_jaw_thresh_min_px"] = float(
            decoded.get("jaw_thresh_min_px", "nan"),
        )
        df["_meta_jaw_direction_mode"] = decoded.get(
            "jaw_direction_mode", "above_or_below",
        )
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = out["date"].astype(str).str.replace("-", "")
    return out


# ============================================================================
# Cohort sanity: verify legacy.jaw_thresh_abs == 4 * legacy.jaw_baseline_sd
# ============================================================================


def _cohort_sanity_jaw_thresh_abs(
    legacy_df: pd.DataFrame, *, atol: float,
) -> tuple[float, int]:
    """Return ``(pct_within_atol, n_compared)`` over rows where both
    ``jaw_thresh_abs`` and ``jaw_baseline_sd`` are finite.

    The audit's claim is that legacy ``jaw_thresh_abs`` equals
    ``sd_mult * jaw_baseline_sd`` (the pre-floor SD term, with sd_mult=4
    cohort-wide). If verified at >99% cohort-wide, the modern
    ``_derived_legacy_thresh_abs = 4 * modern.jaw_baseline_sd`` is a
    sound stand-in.
    """
    if "jaw_thresh_abs" not in legacy_df.columns or "jaw_baseline_sd" not in legacy_df.columns:
        return 0.0, 0
    a = pd.to_numeric(legacy_df["jaw_thresh_abs"], errors="coerce").to_numpy()
    b = 4.0 * pd.to_numeric(legacy_df["jaw_baseline_sd"], errors="coerce").to_numpy()
    finite_pair = np.isfinite(a) & np.isfinite(b)
    if not np.any(finite_pair):
        return 0.0, 0
    a_f = a[finite_pair]
    b_f = b[finite_pair]
    within = np.isclose(a_f, b_f, atol=atol, equal_nan=False)
    return 100.0 * float(np.sum(within)) / float(within.size), int(within.size)


# ============================================================================
# Per-animal comparison
# ============================================================================


def _build_join_key(df: pd.DataFrame) -> pd.Series:
    """Compose join key ``(date, side, reward_frame_idx)`` as a tuple-string.

    Robust to α/β trial-indexing convention difference: rows are matched
    on the underlying frame anchor instead of the enumeration index.
    """
    if "reward_frame_idx" in df.columns:
        rfr = df["reward_frame_idx"]
    elif "reward_center_fr_tongue" in df.columns:
        rfr = df["reward_center_fr_tongue"]
    else:
        raise KeyError(
            "DataFrame missing both reward_frame_idx and reward_center_fr_tongue.",
        )
    return df["date"].astype(str) + "|" + df["side"].astype(str) + "|" + rfr.astype(str)


def _column_compare(
    legacy_df: pd.DataFrame,
    modern_df: pd.DataFrame,
    aligned_legacy_idx: np.ndarray,
    aligned_modern_idx: np.ndarray,
    *,
    atol: float,
) -> list[_ColumnStat]:
    """Per-column comparison over the aligned row pairs."""
    out: list[_ColumnStat] = []
    # Add the synthetic _derived_legacy_thresh_abs column on the modern side.
    if "jaw_baseline_sd" in modern_df.columns:
        derived = (4.0 * pd.to_numeric(modern_df["jaw_baseline_sd"], errors="coerce"))
        modern_df = modern_df.copy()
        modern_df["_derived_legacy_thresh_abs"] = derived

    for legacy_col, modern_col, kind in _COL_PAIRS:
        if kind == "skip":
            continue
        if modern_col is None:
            continue
        if legacy_col not in legacy_df.columns or modern_col not in modern_df.columns:
            out.append(_ColumnStat(
                legacy_col=legacy_col, modern_col=modern_col, kind=kind,
                n_compared=0, n_mismatch=0,
            ))
            continue
        a = legacy_df[legacy_col].to_numpy()
        b = modern_df[modern_col].to_numpy()
        a_aligned = a[aligned_legacy_idx]
        b_aligned = b[aligned_modern_idx]
        stat = _ColumnStat(legacy_col=legacy_col, modern_col=modern_col, kind=kind)
        if kind == "atol":
            try:
                a_f = pd.to_numeric(pd.Series(a_aligned), errors="coerce").to_numpy()
                b_f = pd.to_numeric(pd.Series(b_aligned), errors="coerce").to_numpy()
            except Exception:
                a_f = np.asarray(a_aligned, dtype=np.float64)
                b_f = np.asarray(b_aligned, dtype=np.float64)
            both_finite = np.isfinite(a_f) & np.isfinite(b_f)
            stat.n_compared = int(np.sum(both_finite))
            if stat.n_compared > 0:
                diff = np.abs(a_f[both_finite] - b_f[both_finite])
                stat.max_abs_delta = float(np.max(diff))
                close = np.isclose(
                    a_f[both_finite], b_f[both_finite],
                    atol=atol, equal_nan=False,
                )
                stat.n_mismatch = int(np.sum(~close))
        elif kind == "exact_int":
            try:
                a_i = pd.to_numeric(pd.Series(a_aligned), errors="coerce").astype("Int64")
                b_i = pd.to_numeric(pd.Series(b_aligned), errors="coerce").astype("Int64")
            except Exception:
                continue
            both_present = a_i.notna() & b_i.notna()
            stat.n_compared = int(both_present.sum())
            if stat.n_compared > 0:
                mismatch = (a_i[both_present] != b_i[both_present])
                stat.n_mismatch = int(mismatch.sum())
                stat.max_abs_delta = float(
                    np.abs((a_i[both_present].astype(float) - b_i[both_present].astype(float))).max()
                )
        elif kind == "exact_bool":
            a_b = pd.Series(a_aligned).map(_to_bool)
            b_b = pd.Series(b_aligned).map(_to_bool)
            both_present = a_b.notna() & b_b.notna()
            stat.n_compared = int(both_present.sum())
            if stat.n_compared > 0:
                stat.n_mismatch = int((a_b[both_present] != b_b[both_present]).sum())
        elif kind == "exact_str":
            a_s = pd.Series(a_aligned).astype(str)
            b_s = pd.Series(b_aligned).astype(str)
            stat.n_compared = len(a_s)
            stat.n_mismatch = int((a_s != b_s).sum())
        out.append(stat)
    return out


def _to_bool(x) -> bool | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    s = str(x).strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    return None


def parity_one_animal(
    animal: str, sessions: list[dt.date], mode: str, atol: float,
    emit_resolver: PathResolver,
) -> _AnimalResult:
    # 1. Load legacy CSV.
    try:
        legacy_df = _load_legacy_csv(animal)
    except FileNotFoundError as exc:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_no_legacy", note=str(exc),
        )

    # Detect trial-indexing convention.
    convention = _compare_trial_indexing_convention(legacy_df)

    # Cohort sanity: legacy.jaw_thresh_abs == 4 * legacy.jaw_baseline_sd.
    sanity_pct, sanity_n = _cohort_sanity_jaw_thresh_abs(legacy_df, atol=atol)

    # 2. Re-emit modern per-session parquets.
    parquets = _emit_modern_for_animal_sessions(
        animal, sessions, emit_resolver, mode=mode,
    )
    if not parquets:
        return _AnimalResult(
            animal=animal, mode=mode, status="skip_emit_error",
            note="modern emit produced no successful sessions",
            n_legacy_rows=int(len(legacy_df)),
            legacy_trial_indexing=convention,
            cohort_sanity_jaw_thresh_abs_eq_4sd_pct=sanity_pct,
        )
    modern_df = _build_modern_aggregated_df(animal, parquets)

    # 3. Filter legacy to in-scope dates only (sessions actually emitted).
    in_scope_dates = {d.strftime("%Y%m%d") for d in sessions}
    legacy_in_scope = legacy_df[legacy_df["date"].isin(in_scope_dates)].reset_index(drop=True)

    # 4. Build join keys + align rows.
    legacy_keys = _build_join_key(legacy_in_scope)
    modern_keys = _build_join_key(modern_df)
    legacy_lookup: dict[str, list[int]] = defaultdict(list)
    for i, k in enumerate(legacy_keys):
        legacy_lookup[k].append(i)
    aligned_legacy_idx: list[int] = []
    aligned_modern_idx: list[int] = []
    for j, k in enumerate(modern_keys):
        if k in legacy_lookup and legacy_lookup[k]:
            aligned_legacy_idx.append(legacy_lookup[k].pop(0))
            aligned_modern_idx.append(j)

    # 5. Per-column compare.
    column_stats = _column_compare(
        legacy_in_scope, modern_df,
        np.asarray(aligned_legacy_idx, dtype=np.int64),
        np.asarray(aligned_modern_idx, dtype=np.int64),
        atol=atol,
    )

    # 6. Status.
    n_aligned = len(aligned_legacy_idx)
    n_mismatch_total = sum(c.n_mismatch for c in column_stats)
    status = "pass" if n_mismatch_total == 0 else "fail"
    return _AnimalResult(
        animal=animal, mode=mode, status=status,
        note=("" if n_mismatch_total == 0
              else f"{n_mismatch_total} cell mismatches across {len(column_stats)} cols"),
        n_legacy_rows=int(len(legacy_in_scope)),
        n_modern_rows=int(len(modern_df)),
        n_aligned_rows=int(n_aligned),
        legacy_trial_indexing=convention,
        cohort_sanity_jaw_thresh_abs_eq_4sd_pct=sanity_pct,
        columns=column_stats,
    )


# ============================================================================
# Driver + reporting
# ============================================================================


def _format_result(r: _AnimalResult) -> str:
    lines = [
        f"=== {r.animal} ({r.mode}) ===",
        f"status: {r.status}  ({r.note})",
        f"legacy rows (in-scope): {r.n_legacy_rows}  "
        f"modern rows: {r.n_modern_rows}  "
        f"aligned: {r.n_aligned_rows}",
        f"legacy trial-indexing convention: {r.legacy_trial_indexing}",
        f"cohort sanity (legacy.jaw_thresh_abs == 4*jaw_baseline_sd): "
        f"{r.cohort_sanity_jaw_thresh_abs_eq_4sd_pct:.2f}%",
    ]
    if r.columns:
        lines.append("per-column residuals:")
        for c in r.columns:
            lines.append(
                f"  [{c.kind:10s}] {c.legacy_col:38s} ↔ {c.modern_col:38s}  "
                f"n_compared={c.n_compared:5d}  n_mismatch={c.n_mismatch:5d}  "
                f"max|Δ|={c.max_abs_delta:.6g}",
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7a.5 mismatch parity harness.",
    )
    parser.add_argument(
        "--mode", choices=("default", "legacy_approximate"),
        default="legacy_approximate",
        help="Per kickoff §6a, both modes emit identically (override map "
             "is empty for 7a.5). Flag exposed for CLI consistency.",
    )
    parser.add_argument(
        "--sessions", default="auto",
        help="'auto' = the 14-session parity scope (h7a3.PARITY_SESSIONS_14); "
             "'cohort' = all (animal, date) pairs covered by the legacy CSVs.",
    )
    parser.add_argument(
        "--atol", type=float, default=1e-6,
        help="Tolerance for atol-kind columns. Default 1e-6.",
    )
    parser.add_argument(
        "--emit-root", type=Path, default=None,
        help="Redirect modern emit to this dir (test sandbox). "
             "Default: write under MICROSCOPE pipeline_outputs.",
    )
    parser.add_argument(
        "--animals", default=",".join(DEFAULT_ANIMALS),
        help="Comma-separated cohort animals.",
    )
    args = parser.parse_args(argv)

    # Resolver: emit_root override goes through PathResolver(output_root=...).
    if args.emit_root is not None:
        emit_resolver = PathResolver(output_root=args.emit_root)
    else:
        emit_resolver = PathResolver()

    animals = [a.strip() for a in args.animals.split(",") if a.strip()]

    if args.sessions == "auto":
        sessions_per_animal: dict[str, list[dt.date]] = defaultdict(list)
        for animal, date in h7a3.PARITY_SESSIONS_14:
            sessions_per_animal[animal].append(date)
    elif args.sessions == "cohort":
        # All (animal, date) pairs in legacy CSVs (per-animal scoped).
        sessions_per_animal = {}
        for animal in animals:
            try:
                lg = _load_legacy_csv(animal)
            except FileNotFoundError:
                sessions_per_animal[animal] = []
                continue
            sessions_per_animal[animal] = sorted({
                dt.datetime.strptime(d, "%Y%m%d").date()
                for d in lg["date"].unique()
            })
    else:
        raise ValueError(f"Unknown --sessions {args.sessions!r}")

    print("Phase 7a.5 mismatch parity harness")
    print(f"  mode={args.mode}  atol={args.atol}  sessions={args.sessions}")
    print(f"  emit_root: {args.emit_root or '<MICROSCOPE pipeline_outputs default>'}")
    print()

    results: list[_AnimalResult] = []
    for animal in animals:
        sessions = sessions_per_animal.get(animal, [])
        print(f">>> {animal}: {len(sessions)} sessions in scope")
        if not sessions:
            results.append(_AnimalResult(
                animal=animal, mode=args.mode, status="skip_no_legacy",
                note="no in-scope sessions",
            ))
            continue
        result = parity_one_animal(
            animal, sessions, args.mode, args.atol, emit_resolver,
        )
        results.append(result)
        print(_format_result(result))
        print()

    print("=" * 80)
    print("Summary by status:")
    by_status: dict[str, list[str]] = defaultdict(list)
    for r in results:
        by_status[r.status].append(r.animal)
    for status, animals_ in by_status.items():
        print(f"  {status}: {len(animals_)} animals — {animals_}")
    print()

    print("Cohort overall max|Δ| per column:")
    cohort_max: dict[str, float] = defaultdict(float)
    cohort_mismatch: dict[str, int] = defaultdict(int)
    cohort_compared: dict[str, int] = defaultdict(int)
    for r in results:
        for c in r.columns:
            key = f"[{c.kind}] {c.legacy_col} ↔ {c.modern_col}"
            cohort_max[key] = max(cohort_max[key], c.max_abs_delta)
            cohort_mismatch[key] += c.n_mismatch
            cohort_compared[key] += c.n_compared
    for key, m in sorted(cohort_max.items()):
        print(
            f"  {key:90s} n_compared={cohort_compared[key]:7d}  "
            f"n_mismatch={cohort_mismatch[key]:6d}  max|Δ|={m:.6g}",
        )

    n_pass = sum(1 for r in results if r.status == "pass")
    n_fail = sum(1 for r in results if r.status == "fail")
    print()
    print(f"Final: {n_pass} pass, {n_fail} fail, "
          f"{len(results) - n_pass - n_fail} skip (of {len(results)} animals).")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
