r"""Phase 7a parity harness — legacy NPZ vs consolidated parquet, 14 sessions.

Scope: compares x_final / y_final / X0 / Y0 / fps / n_frames between the
legacy v5p3 NPZs on MICROSCOPE and the consolidated-pipeline parquets
written by ``src/stroke_orofacial/dlc_kinematics/interpolation.py``.

As of Phase 7a.1 the consolidated-side read is stubbed — the module
does not yet exist. Phase 7a.2 replaces the ``_load_consolidated_trace``
stub below with the real call. Everything else (legacy load, scope
filter, tolerance comparison, session enumeration) is ready.

Usage::

    python tests/scripts/parity_phase7a_interpolation.py \
        --animal PS46 --date 20250307 --bodypart tongue
    python tests/scripts/parity_phase7a_interpolation.py --sessions auto

``--sessions auto`` enumerates the 14 parity sessions from
``interpolation-strategy.md`` §6 (9 primary + 3 stress + 2
late-post-stroke) and runs each in sequence across both bodyparts.

Exit codes:
    0 — all compared sessions within atol
    1 — at least one session failed tolerance (actual mismatch)
    2 — pending-impl stub hit (expected in 7a.1; expected to
        disappear in 7a.2)
    3 — legacy NPZ missing / MICROSCOPE unreachable
    4 — scope-filter skipped all sessions (configuration error)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

# --- constants from interpolation-strategy.md §6 --------------------------

ATOL = 1e-6  # Phase 7a.0 Option A (DECISIONS 2026-04-22, scipy 1.15.1↔1.17.1 bit-identical)

MICROSCOPE_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis"
)

CENTER_MODE = {
    "tongue": "centered_spout_midpoint",
    "jaw": "centered_eye_midpoint",
}

# 14 parity sessions per interpolation-strategy.md §6.
PARITY_SESSIONS_PRIMARY = [
    ("PS46", dt.date(2025, 3, 7)),  ("PS46", dt.date(2025, 3, 10)), ("PS46", dt.date(2025, 3, 13)),
    ("PS54", dt.date(2025, 5, 6)),  ("PS54", dt.date(2025, 5, 9)),  ("PS54", dt.date(2025, 5, 12)),
    ("PS55", dt.date(2025, 5, 1)),  ("PS55", dt.date(2025, 5, 4)),  ("PS55", dt.date(2025, 5, 7)),
]
PARITY_SESSIONS_STRESS = [
    ("PS51", dt.date(2025, 4, 30)),
    ("PS54", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 2)),
]
PARITY_SESSIONS_LATE = [
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]
PARITY_SESSIONS_14 = (
    PARITY_SESSIONS_PRIMARY + PARITY_SESSIONS_STRESS + PARITY_SESSIONS_LATE
)


# --- dataclasses ---------------------------------------------------------


@dataclass
class ParityResult:
    """Single (animal, date, bodypart) parity-check outcome."""

    animal: str
    date: dt.date
    bodypart: str
    status: str  # "pass", "fail", "stub", "skip_scope", "skip_missing"
    max_abs_dx: float | None = None
    max_abs_dy: float | None = None
    note: str = ""


# --- scope filter --------------------------------------------------------


def load_scope(
    animals_yaml_path: Path,
) -> dict[str, tuple[dt.date, dt.date]]:
    """Return per-animal (start, end) session windows from animals.yaml.

    Animals whose ``sessions.start`` or ``sessions.end`` is null are
    skipped silently — they are placeholder entries (see e.g. the
    test fixtures' PS_PLACEHOLDER pattern) and are not parity targets.
    """
    with open(animals_yaml_path) as f:
        animals = yaml.safe_load(f)
    out: dict[str, tuple[dt.date, dt.date]] = {}
    for animal, blob in animals.items():
        scope = blob.get("sessions") or {}
        start = scope.get("start")
        end = scope.get("end")
        # YAML date literals (YYYY-MM-DD) parse as dt.date; string fallback
        # for the YYYYMMDD form that occasionally appears in test fixtures.
        if isinstance(start, str):
            start = dt.date.fromisoformat(start)
        if isinstance(end, str):
            end = dt.date.fromisoformat(end)
        if start is not None and end is not None:
            out[animal] = (start, end)
    return out


def is_in_scope(
    animal: str, date: dt.date, scope: dict[str, tuple[dt.date, dt.date]]
) -> bool:
    """Return True if ``date`` is in ``animal``'s configured session window."""
    if animal not in scope:
        return False
    start, end = scope[animal]
    return start <= date <= end


# --- legacy NPZ loader ---------------------------------------------------


def _legacy_npz_path(animal: str, date: dt.date, bodypart: str) -> Path:
    date_str = date.strftime("%Y%m%d")
    center = CENTER_MODE[bodypart]
    return (
        MICROSCOPE_ROOT
        / animal
        / f"{animal}_{bodypart}_kinematics"
        / "processed_interpolated_data"
        / center
        / f"{animal}_{date_str}_cam2_{bodypart}_interp_v5p3.npz"
    )


def load_legacy_trace(animal: str, date: dt.date, bodypart: str) -> dict:
    """Load x_final / y_final / X0 / Y0 / fps / n_frames from the legacy NPZ."""
    path = _legacy_npz_path(animal, date, bodypart)
    if not path.exists():
        raise FileNotFoundError(f"Legacy NPZ not found: {path}")
    data = np.load(path, allow_pickle=True)
    return {
        "x_final": data["x_final"].astype(float),
        "y_final": data["y_final"].astype(float),
        "X0": float(data["X0"]),
        "Y0": float(data["Y0"]),
        "fps": float(data["fps"]),
        "n_frames": int(data["n_frames"]),
        "path": path,
    }


# --- consolidated-side stub (7a.2 replaces this) -------------------------


def _load_consolidated_trace(animal: str, date: dt.date, bodypart: str) -> dict:
    """Load x_final / y_final / X0 / Y0 / fps / n_frames from the consolidated parquet.

    Real reader (replaces the 7a.1 NotImplementedError stub). Reads the
    Phase 7a.2 interpolated-trace parquet emitted by
    :func:`stroke_orofacial.dlc_kinematics.build_interpolated_trace`.
    The parquet schema (7 columns + 9 file-level metadata attributes) is
    locked by ``interpolation-strategy.md`` §2c.

    Raises ``FileNotFoundError`` if the consolidated parquet is absent —
    most commonly when the 14-session pre-emit step was skipped. The
    harness treats that the same as a missing legacy NPZ
    (``skip_missing``).
    """
    from stroke_orofacial.paths import PathResolver
    import pandas as pd
    import pyarrow.parquet as pq

    resolver = PathResolver()
    path = resolver.interpolated_trace(bodypart=bodypart, animal=animal, date=date)
    if not path.exists():
        raise FileNotFoundError(f"Consolidated parquet not found: {path}")
    df = pd.read_parquet(path)
    meta = pq.ParquetFile(path).metadata.metadata
    return {
        "x_final": df["x_final"].to_numpy().astype(float),
        "y_final": df["y_final"].to_numpy().astype(float),
        "X0": float(meta[b"X0"]),
        "Y0": float(meta[b"Y0"]),
        "fps": float(meta[b"fps"]),
        "n_frames": int(meta[b"n_frames"]),
        "path": path,
    }


# --- comparator ----------------------------------------------------------


def compare_session(animal: str, date: dt.date, bodypart: str) -> ParityResult:
    """Compare legacy vs consolidated outputs for one (animal, date, bodypart)."""
    legacy = load_legacy_trace(animal, date, bodypart)
    try:
        consolidated = _load_consolidated_trace(animal, date, bodypart)
    except NotImplementedError as e:
        return ParityResult(animal, date, bodypart, status="stub", note=str(e))

    # scalar metadata must match exactly
    for key in ("X0", "Y0", "fps", "n_frames"):
        if legacy[key] != consolidated[key]:
            return ParityResult(
                animal,
                date,
                bodypart,
                status="fail",
                note=(
                    f"{key} mismatch: legacy={legacy[key]}, "
                    f"consolidated={consolidated[key]}"
                ),
            )

    # trace arrays: atol=1e-6 element-wise on non-NaN common indices
    dx_max: float | None = None
    dy_max: float | None = None
    for axis in ("x_final", "y_final"):
        a = legacy[axis]
        b = consolidated[axis]
        if a.shape != b.shape:
            return ParityResult(
                animal,
                date,
                bodypart,
                status="fail",
                note=f"{axis} shape mismatch: {a.shape} vs {b.shape}",
            )
        mask = ~(np.isnan(a) | np.isnan(b))
        if mask.sum() == 0:
            continue
        max_abs_d = float(np.abs(a[mask] - b[mask]).max())
        if axis == "x_final":
            dx_max = max_abs_d
        else:
            dy_max = max_abs_d
        if max_abs_d > ATOL:
            return ParityResult(
                animal,
                date,
                bodypart,
                status="fail",
                max_abs_dx=dx_max,
                max_abs_dy=dy_max,
                note=f"{axis} max|Δ|={max_abs_d:.3e} > atol={ATOL:.1e}",
            )

    return ParityResult(
        animal, date, bodypart, status="pass", max_abs_dx=dx_max, max_abs_dy=dy_max
    )


# --- main ----------------------------------------------------------------


def _parse_yyyymmdd(s: str) -> dt.date:
    return dt.date.fromisoformat(f"{s[:4]}-{s[4:6]}-{s[6:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--animal", help="e.g. PS46")
    ap.add_argument("--date", help="YYYYMMDD", type=_parse_yyyymmdd)
    ap.add_argument("--bodypart", choices=("tongue", "jaw"))
    ap.add_argument(
        "--sessions",
        choices=("auto",),
        help="auto = run §6's 14-session parity set across both bodyparts",
    )
    ap.add_argument("--animals-yaml", default="configs/animals.yaml")
    args = ap.parse_args()

    scope = load_scope(Path(args.animals_yaml))

    if args.sessions == "auto":
        todo = [
            (a, d, bp)
            for (a, d) in PARITY_SESSIONS_14
            for bp in ("tongue", "jaw")
        ]
    else:
        if not (args.animal and args.date and args.bodypart):
            print(
                "error: provide --animal --date --bodypart or --sessions auto",
                file=sys.stderr,
            )
            return 4
        todo = [(args.animal, args.date, args.bodypart)]

    results: list[ParityResult] = []
    for animal, date, bodypart in todo:
        if not is_in_scope(animal, date, scope):
            results.append(
                ParityResult(
                    animal,
                    date,
                    bodypart,
                    status="skip_scope",
                    note=f"out of sessions.{{start,end}} for {animal}",
                )
            )
            continue
        try:
            results.append(compare_session(animal, date, bodypart))
        except FileNotFoundError as e:
            results.append(
                ParityResult(
                    animal, date, bodypart, status="skip_missing", note=str(e)
                )
            )

    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    print(f"\nParity summary: {by_status}")
    for r in results:
        print(f"  {r.animal} {r.date} {r.bodypart:6s} {r.status:14s} {r.note}")

    # Priority: hard failures > pending stub > all-skipped-scope > legacy NPZ
    # outright unreachable. The stub-wins-over-missing ordering is deliberate
    # for 7a.1: in the expected smoke, some sessions may be missing from
    # MICROSCOPE (PS54/20250512 is one such), but the overall run should
    # still signal "stub pending" so 7a.2 can land a real implementation.
    # In 7a.2 once the stub is replaced, skip_missing will no longer race
    # against a synthetic pending status.
    if by_status.get("fail", 0) > 0:
        return 1
    if by_status.get("stub", 0) > 0 and by_status.get("pass", 0) == 0:
        return 2
    if (
        not any(r.status == "pass" for r in results)
        and by_status.get("skip_scope", 0) == len(results)
    ):
        return 4
    # Terminal skip_missing-only case: MICROSCOPE read broken for every
    # attempted session. Exit 3 per the top-of-file code legend.
    if (
        by_status.get("skip_missing", 0) > 0
        and by_status.get("pass", 0) == 0
        and by_status.get("stub", 0) == 0
    ):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
