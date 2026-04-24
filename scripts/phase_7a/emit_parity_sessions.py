"""Pre-emit consolidated interpolated-trace parquets for the Phase 7a parity set.

A durable verification helper (promoted from ``scratch/phase-7a2-probe/``
as part of the Phase 7a.2 wrap-up): runs
:func:`stroke_orofacial.dlc_kinematics.build_interpolated_trace_by_animal_date`
over the 14-session × 2-bodypart parity set (matching the list in
``docs/prompts/phase-7a.2-kickoff.md`` and
``tests/scripts/parity_phase7a_interpolation.py::PARITY_SESSIONS_14``)
so the parity harness's ``_load_consolidated_trace`` reader finds every
parquet already on disk when invoked.

The pre-emit step exists because the parity harness only reads; it does
not emit. Running this script before
``python tests/scripts/parity_phase7a_interpolation.py --sessions auto``
ensures any post-Phase-7a.2 kinematics algorithm change (per the
2026-04-22 DECISIONS parity-gate principle) can be re-validated in one
sweep without manually walking the 14 × 2 = 28 ``build_interpolated_trace``
calls.

Tolerates MICROSCOPE-gap sessions (e.g. PS54/20250512 where neither
Phase 4.5-lite centered parquet nor legacy NPZ exists) by catching
``FileNotFoundError`` and reporting ``skip_missing``. Those lines are
symmetric with the legacy-side gap the parity harness will also
report.

Usage::

    python scripts/phase_7a/emit_parity_sessions.py

Exit codes:
    0 — emit batch completed (all sessions either OK or cleanly skipped).
    1 — at least one session raised an unexpected (non-FileNotFound) error.
"""
from __future__ import annotations

import datetime as dt
import sys
import time

from stroke_orofacial.dlc_kinematics import build_interpolated_trace_by_animal_date
from stroke_orofacial.paths import PathResolver


# Kept in sync with tests/scripts/parity_phase7a_interpolation.py::PARITY_SESSIONS_14.
# If interpolation-strategy.md §6's 14-session set changes, update both.
PARITY_SESSIONS_14: list[tuple[str, dt.date]] = [
    ("PS46", dt.date(2025, 3, 7)),
    ("PS46", dt.date(2025, 3, 10)),
    ("PS46", dt.date(2025, 3, 13)),
    ("PS54", dt.date(2025, 5, 6)),
    ("PS54", dt.date(2025, 5, 9)),
    ("PS54", dt.date(2025, 5, 12)),
    ("PS55", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 4)),
    ("PS55", dt.date(2025, 5, 7)),
    ("PS51", dt.date(2025, 4, 30)),
    ("PS54", dt.date(2025, 5, 1)),
    ("PS55", dt.date(2025, 5, 2)),
    ("PS54", dt.date(2025, 6, 7)),
    ("PS55", dt.date(2025, 6, 7)),
]


def main() -> int:
    resolver = PathResolver()
    n_ok = 0
    n_skip_missing = 0
    n_fail = 0
    failures: list[tuple[str, dt.date, str, str]] = []

    todo = [
        (a, d, bp)
        for (a, d) in PARITY_SESSIONS_14
        for bp in ("tongue", "jaw")
    ]
    total = len(todo)
    print(f"Pre-emit {total} consolidated parquets (14 sessions × 2 bodyparts)")
    print("-" * 100)
    for i, (animal, date, bodypart) in enumerate(todo, 1):
        t0 = time.time()
        tag = f"{animal} {date.isoformat()} {bodypart:6s}"
        try:
            path = build_interpolated_trace_by_animal_date(
                animal=animal, date=date, bodypart=bodypart,
                resolver=resolver, overwrite="force",
            )
        except FileNotFoundError as e:
            dt_s = time.time() - t0
            print(f"  [{i:2d}/{total}] {tag}  SKIP_MISSING  ({dt_s:.1f}s)  "
                  f"{str(e).splitlines()[0][:80]}")
            n_skip_missing += 1
            continue
        except Exception as e:
            dt_s = time.time() - t0
            print(f"  [{i:2d}/{total}] {tag}  FAIL          ({dt_s:.1f}s)  "
                  f"{type(e).__name__}: {e}")
            failures.append((animal, date, bodypart, f"{type(e).__name__}: {e}"))
            n_fail += 1
            continue
        dt_s = time.time() - t0
        if path is None:
            print(f"  [{i:2d}/{total}] {tag}  EXCLUDED      ({dt_s:.1f}s)")
            continue
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  [{i:2d}/{total}] {tag}  OK            "
              f"({dt_s:.1f}s, {size_mb:.1f} MB)")
        n_ok += 1

    print("-" * 100)
    print(f"Summary: ok={n_ok}, skip_missing={n_skip_missing}, fail={n_fail}")
    if failures:
        print("\nFailures:")
        for animal, date, bodypart, msg in failures:
            print(f"  {animal} {date} {bodypart}: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
