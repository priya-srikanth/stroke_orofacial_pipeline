"""Phase 7a.4 — visual gate runner: render comparison grids vs legacy PNGs.

Produces consolidated PNGs + side-by-side comparison grids for human
review. NOT a numerical pass/fail — output is for Priya's eyeball
verdict on whether the consolidated plots match legacy semantics
(curve shapes, peak positions, sign conventions, distribution shapes).

Sessions covered (kickoff §5b):

- ``PS50/2025-03-19`` — smoke session. Auto-derive trial events; render
  6 PNGs + 6 comparison grids. PS50's `angle_phase_exploratory/` has
  legacy figures for several dates; 2025-03-19 may or may not be
  present.
- ``PS46/2025-03-07``, ``PS46/2025-03-10``, ``PS46/2025-03-13`` — the
  PS46 family with saved legacy figures (Task 4 demo confirmed
  6-of-6 match for 2025-03-07).

Per (animal, date):

1. Render consolidated PNGs to
   ``<emit_root>/dlc_kinematics/figures_qc/tongue/<animal>/<YYYYMMDD>/``.
2. Render comparison grids to
   ``<emit_root>/dlc_kinematics/figures_qc/tongue_comparison/<animal>/<YYYYMMDD>/``.
3. Report per-grid file size + per-family legacy-match status.

By default emits to MICROSCOPE under
``stroke_orofacial_pipeline_outputs/dlc_kinematics/figures_qc/...``.
Pass ``--emit-root=<path>`` to redirect for sandbox runs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Sequence

from stroke_orofacial.dlc_kinematics import (
    build_tongue_visual_bundle_by_animal_date,
    render_comparison_grid,
    render_tongue_qc_figures,
)
from stroke_orofacial.paths import PathResolver

CENTER_MODE = "centered_spout_midpoint"

# (animal, YYYYMMDD) — kickoff §5b explicit list.
DEFAULT_SESSIONS: tuple[tuple[str, dt.date], ...] = (
    ("PS50", dt.date(2025, 3, 19)),
    ("PS46", dt.date(2025, 3, 7)),
    ("PS46", dt.date(2025, 3, 10)),
    ("PS46", dt.date(2025, 3, 13)),
)


def _legacy_figures_root(animal: str, real_resolver: PathResolver) -> Path:
    return (
        real_resolver.dlc_output_dir(animal)
        / f"{animal}_tongue_kinematics"
        / "kinematics_figures"
        / CENTER_MODE
        / "angle_phase_exploratory"
    )


def _expected_legacy_filenames(
    animal: str, date: dt.date,
    *,
    time_mode: str = "first_multi",
    phase_mode: str = "first_multi",
    xy_mode: str = "first_multi",
) -> dict[str, list[str]]:
    """Map family → expected legacy filenames (for the 2025-03-07 family
    1 emits 2 per-side PNGs)."""
    date_str = date.strftime("%Y%m%d")
    return {
        "qc_trials": [
            f"{animal}_{date_str}_L_anglePhase_QCtrials.png",
            f"{animal}_{date_str}_R_anglePhase_QCtrials.png",
        ],
        "first_peak_aligned": [
            f"{animal}_{date_str}_anglePhase_firstPeakAlignedAngle.png",
        ],
        "reward_aligned": [
            f"{animal}_{date_str}_anglePhase_rewardAlignedAngle_{time_mode}.png",
        ],
        "phase_aligned_angle": [
            f"{animal}_{date_str}_anglePhase_phaseAlignedAngle_{phase_mode}.png",
        ],
        "xy_by_phase": [
            f"{animal}_{date_str}_anglePhase_XYphase_{xy_mode}.png",
        ],
    }


def _render_session(
    animal: str,
    date: dt.date,
    real_resolver: PathResolver,
    emit_resolver: PathResolver,
) -> dict:
    """Render one session's consolidated PNGs + comparison grids.

    Returns a status dict with paths + sizes + legacy-match counts.
    """
    print(f"[{animal} {date.isoformat()}] building bundle ...")
    try:
        bundle = build_tongue_visual_bundle_by_animal_date(
            animal=animal, date=date, resolver=real_resolver,
        )
    except FileNotFoundError as exc:
        print(f"  SKIP — bundle build failed: {exc}")
        return {"animal": animal, "date": date, "status": "skip_bundle_error"}
    print(f"  bundle.df_trials.shape = {bundle.df_trials.shape}")

    qc_out = render_tongue_qc_figures(
        animal=animal, date=date, resolver=emit_resolver,
        bundle=bundle, overwrite="force",
    )
    qc_paths_flat = [p for paths in qc_out.values() for p in paths]
    print(f"  consolidated PNGs: {len(qc_paths_flat)}")
    for family, paths in qc_out.items():
        for p in paths:
            size_kb = p.stat().st_size / 1024
            print(f"    [{family}] {p.name}  ({size_kb:.1f} KB)")

    legacy_root = _legacy_figures_root(animal, real_resolver)
    legacy_present = legacy_root.exists()
    print(f"  legacy_root: {legacy_root}")
    print(f"    exists = {legacy_present}")

    expected = _expected_legacy_filenames(animal, date)
    legacy_status: dict[str, list[bool]] = {}
    if legacy_present:
        for family, names in expected.items():
            legacy_status[family] = [
                (legacy_root / name).exists() for name in names
            ]
    else:
        for family, names in expected.items():
            legacy_status[family] = [False] * len(names)
    n_expected = sum(len(v) for v in legacy_status.values())
    n_found = sum(sum(v) for v in legacy_status.values())
    print(f"  legacy match: {n_found}/{n_expected} expected PNGs found")
    for family, found_list in legacy_status.items():
        names = expected[family]
        for name, found in zip(names, found_list):
            mark = "✓" if found else "✗"
            print(f"    {mark} [{family}] {name}")

    cmp_out = render_comparison_grid(
        animal=animal, date=date, resolver=emit_resolver,
        legacy_figures_root=legacy_root,
    )
    cmp_paths_flat = [p for paths in cmp_out.values() for p in paths]
    print(f"  comparison grids: {len(cmp_paths_flat)}")
    for family, paths in cmp_out.items():
        for p in paths:
            size_kb = p.stat().st_size / 1024
            print(f"    [{family}] {p.name}  ({size_kb:.1f} KB)")

    return {
        "animal": animal,
        "date": date,
        "status": "ok",
        "n_consolidated": len(qc_paths_flat),
        "n_comparison": len(cmp_paths_flat),
        "legacy_match": f"{n_found}/{n_expected}",
        "legacy_status": legacy_status,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7a.4 visual gate runner.",
    )
    parser.add_argument(
        "--emit-root", type=Path, default=None,
        help="Redirect output to this dir instead of pipeline_outputs.",
    )
    parser.add_argument(
        "--sessions", default="default",
        help="Comma-separated <animal>:<YYYYMMDD> pairs, or 'default'.",
    )
    args = parser.parse_args(argv)

    real_resolver = PathResolver()
    emit_resolver = (
        PathResolver(output_root=args.emit_root)
        if args.emit_root is not None else real_resolver
    )

    if args.sessions == "default":
        sessions = list(DEFAULT_SESSIONS)
    else:
        sessions = []
        for tok in args.sessions.split(","):
            tok = tok.strip()
            if not tok:
                continue
            animal, date_str = tok.split(":")
            sessions.append((animal, dt.date.fromisoformat(date_str)))

    print("Phase 7a.4 visual gate runner")
    print(f"  emit_root: {args.emit_root or '<pipeline_outputs default>'}")
    print(f"  sessions: {[f'{a}:{d.isoformat()}' for a, d in sessions]}")
    print()

    results = []
    for animal, date in sessions:
        result = _render_session(animal, date, real_resolver, emit_resolver)
        results.append(result)
        print()

    print("=" * 80)
    print("Visual gate summary:")
    for r in results:
        if r["status"] != "ok":
            print(f"  {r['animal']}/{r['date'].isoformat()}: {r['status']}")
            continue
        print(
            f"  {r['animal']}/{r['date'].isoformat()}: "
            f"{r['n_consolidated']} PNGs + {r['n_comparison']} grids; "
            f"legacy match {r['legacy_match']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
