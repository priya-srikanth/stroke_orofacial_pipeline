"""Emit 7a.2 interpolation + 7a.3 per-trial outputs across the full cohort.

Phase 7a.4-cross-session-angle Addendum #13 (2026-05-04) prerequisite:
the centered-phase plots' Addendum #12 synthetic ILI is computed from
each animal's pre-stroke multi-bout intervals — which requires the
upstream interpolation + per-trial parquets to be on disk for every
pre-stroke session in the animal's session range.

This script walks every (animal, date) in
``configs/animals.yaml`` ``session_start..session_end`` for the eight
production animals (PS46-50, PS51, PS54, PS55) and runs the two upstream
builders with ``overwrite="skip"`` so existing emits are untouched and
only the missing sessions get computed. The downstream
:func:`compute_pre_stroke_median_ili_ms` then has the full pre-stroke
session set to median over.

Tolerates:
  - Sessions excluded per ``animal_info.exclusions`` (the per-trial
    builder's internal ``manifest.excluded`` check returns ``None``).
  - Sessions missing upstream DLC inference (catches
    ``FileNotFoundError`` raised by the builder when DLC parquets /
    alignment templates / spout_behavior products are absent on disk).

Idempotent — safe to interrupt and resume; existing parquets stay.

Usage::

    python scripts/phase_7a/emit_cohort_for_pre_stroke_median.py

Exit codes:
    0 — emit batch completed (all sessions either OK or cleanly skipped).
    1 — at least one session raised an unexpected (non-FileNotFound) error.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
import traceback
from collections import Counter

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.dlc_kinematics import (
    build_interpolated_trace_by_animal_date,
    build_tongue_pertrial_by_animal_date,
)
from stroke_orofacial.paths import PathResolver


COHORT: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50",
    "PS51", "PS54", "PS55",
)


def _date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    """Inclusive list of dates from ``start`` to ``end``."""
    n = (end - start).days
    return [start + dt.timedelta(days=i) for i in range(n + 1)]


def _emit_one_session(
    animal: str, date: dt.date, *, resolver: PathResolver,
    animal_info: AnimalInfo,
) -> str:
    """Emit interpolation (tongue + jaw) + per-trial scalars for one
    (animal, date). Returns a status token: ``ok`` / ``skip_excluded``
    / ``skip_missing`` / ``err``.

    Each builder runs its own ``is_excluded`` check internally
    (see :func:`build_interpolated_trace` for tongue/jaw and
    :func:`_build_tongue_pertrial_core` via the wrapper for per-trial
    scalars). Builders return ``None`` on excluded sessions, which
    we treat as ``skip_excluded`` here.
    """
    excluded, _reason = animal_info.is_excluded(
        date, analysis_context="dlc.kinematics.tongue",
    )
    if excluded:
        return "skip_excluded"

    try:
        for bodypart in ("tongue", "jaw"):
            build_interpolated_trace_by_animal_date(
                animal, date, bodypart=bodypart, resolver=resolver,
                overwrite="skip",
            )
    except FileNotFoundError:
        return "skip_missing"
    except Exception:
        traceback.print_exc()
        return "err"

    try:
        build_tongue_pertrial_by_animal_date(
            animal, date, resolver=resolver, overwrite="skip",
        )
    except FileNotFoundError:
        return "skip_missing"
    except Exception:
        traceback.print_exc()
        return "err"

    return "ok"


def main() -> int:
    resolver = PathResolver()
    grand_counts: Counter[str] = Counter()
    grand_t0 = time.time()

    for animal in COHORT:
        animal_info = get_animal(animal)
        dates = _date_range(animal_info.session_start, animal_info.session_end)
        print(
            f"\n=== {animal}: {animal_info.session_start.isoformat()} → "
            f"{animal_info.session_end.isoformat()} ({len(dates)} dates, "
            f"stroke={animal_info.stroke_date.isoformat()}, "
            f"excl={len(animal_info.exclusions)}) ===",
            flush=True,
        )
        per_animal: Counter[str] = Counter()
        animal_t0 = time.time()
        for d in dates:
            t0 = time.time()
            status = _emit_one_session(
                animal, d, resolver=resolver, animal_info=animal_info,
            )
            dt_s = time.time() - t0
            per_animal[status] += 1
            grand_counts[status] += 1
            rel_day = animal_info.day_relative_to_stroke(d)
            tag = f"d{rel_day:+d}" if rel_day is not None else "d?"
            if status == "ok":
                print(
                    f"  {animal}/{d.isoformat()} [{tag}] ok ({dt_s:.1f}s)",
                    flush=True,
                )
            elif status == "err":
                print(
                    f"  {animal}/{d.isoformat()} [{tag}] ERR",
                    flush=True,
                )
        animal_dt = time.time() - animal_t0
        print(
            f"  ── {animal} done in {animal_dt:.1f}s; "
            f"counts={dict(per_animal)}",
            flush=True,
        )

    grand_dt = time.time() - grand_t0
    print(
        f"\n=== GRAND TOTAL: {grand_dt:.1f}s; "
        f"counts={dict(grand_counts)} ===",
        flush=True,
    )
    return 1 if grand_counts.get("err", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
