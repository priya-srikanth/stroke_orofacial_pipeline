"""Phase 7a.5 — visual gate runner: render mismatch figures + side-by-side
legacy comparisons.

Produces consolidated PNGs (4 plot families) + side-by-side comparison
grids for human review. NOT a numerical pass/fail — output is for
Priya's eyeball verdict on whether the consolidated mismatch plots
match legacy semantics.

Sessions covered (kickoff §6b):

- ``PS46/2025-03-07`` — pre-stroke baseline (Task 5 smoke session;
  legacy figures present at MICROSCOPE; expected ~0% candidate rate
  because the mouse is actively licking).
- ``PS55/2025-05-02`` — post-stroke d+2 (PS55 d0 = 2025-04-30); the
  upstream 7a.2 parquet exists in the 14-session parity scope (it's
  the PS55 STRESS session). Exercises the candidate-rate-non-zero
  path.
- ``PS55/2025-06-07`` — post-stroke d+38 (the PS55 LATE session).
  Late recovery; should still show some candidate trials.

PS46 post-stroke (e.g. 2025-03-14, 2025-03-20) was originally proposed
in the kickoff but is NOT emittable today: the 7a.2 interpolation
pipeline emits only the 14-session parity scope, which for PS46 covers
2025-03-07, 2025-03-10, 2025-03-13 — all pre-stroke (d0=2025-03-13).
Post-stroke PS46 visual verification requires the cohort-wide 7a.2
re-emit deferred from Phase 7a.4 (publication-grade follow-up).

Per (animal, date):

1. Render consolidated within-session PNGs to
   ``<emit_root>/dlc_kinematics/tongue_jaw_mismatch/figures_qc/<animal>/<YYYYMMDD>/``.
2. Build comparison grids legacy | consolidated for each within-session
   family.
3. Per-mouse: render cross-session figures + comparison grids.
4. Report per-grid file size + per-family legacy-match status.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (  # noqa: E402
    classify_tongue_jaw_mismatch_by_animal_date,
    render_cross_session_figures,
    render_within_session_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402

# Default cohort-wide visual gate sessions. Covers (a) pre-stroke baseline
# (PS46 smoke) and (b) post-stroke candidate-rate-non-zero exercise (PS55).
# All three are in the 14-session parity scope.
DEFAULT_SESSIONS: tuple[tuple[str, dt.date], ...] = (
    ("PS46", dt.date(2025, 3, 7)),
    ("PS55", dt.date(2025, 5, 2)),
    ("PS55", dt.date(2025, 6, 7)),
)
DEFAULT_CROSS_ANIMALS: tuple[str, ...] = ("PS46", "PS55")


def _legacy_mismatch_dir(animal: str, real_resolver: PathResolver) -> Path:
    return (
        real_resolver.dlc_output_dir(animal)
        / f"{animal}_jaw_kinematics" / "kinematics_figures"
        / "centered_eye_midpoint" / "jaw_tongue_candidate_trials"
    )


def _expected_within_session_filenames(
    animal: str, date: dt.date,
) -> dict[str, str]:
    date_str = date.strftime("%Y%m%d")
    return {
        "individual_trials": (
            f"{animal}_{date_str}_individualTrials2col_candidateVsNoncandidate_jawBaselineSub.png"
        ),
        "session_overlay_grid": (
            f"{animal}_{date_str}_sessionOverlayGrid4x2_jawBaselineSub.png"
        ),
    }


def _expected_cross_session_filenames(
    animal: str, bin_days: int,
) -> dict[str, str]:
    return {
        "cross_session_overlay": (
            f"{animal}_crossSessionOverlay2x2_jawBaselineSub.png"
        ),
        "cross_session_binned": (
            f"{animal}_crossSessionBinned2x2_bins{bin_days}_jawBaselineSub.png"
        ),
    }


def _render_comparison_grid(
    legacy_path: Path | None, consolidated_path: Path, out_path: Path,
    *, title: str,
) -> None:
    """2-col side-by-side comparison: legacy | consolidated.

    Mirrors :func:`stroke_orofacial.dlc_kinematics.tongue_visual._save_comparison_grid`
    (vendored locally to keep cross-module import surface minimal).
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    panes = [(legacy_path, "legacy"), (consolidated_path, "consolidated")]
    for ax, (pane_path, label) in zip(axes, panes):
        if pane_path is not None and pane_path.exists():
            try:
                img = mpimg.imread(pane_path)
                ax.imshow(img)
                ax.set_title(f"{label}\n{pane_path.name}", fontsize=9)
            except Exception as exc:  # noqa: BLE001
                ax.text(
                    0.5, 0.5,
                    f"{label}: load error\n{type(exc).__name__}: {exc}",
                    ha="center", va="center", transform=ax.transAxes,
                )
        else:
            ax.text(
                0.5, 0.5,
                f"{label}: not found\n{pane_path}",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="0.5",
            )
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp" + out_path.suffix)
    fig.savefig(tmp, dpi=120, bbox_inches="tight", format="png")
    plt.close(fig)
    tmp.replace(out_path)


def _render_session(
    animal: str, date: dt.date,
    real_resolver: PathResolver, emit_resolver: PathResolver,
) -> dict:
    """Render one (animal, date)'s consolidated PNGs + within-session
    comparison grids."""
    print(f"[{animal} {date.isoformat()}] classifying ...")
    try:
        ct_path = classify_tongue_jaw_mismatch_by_animal_date(
            animal=animal, date=date, resolver=emit_resolver,
            overwrite="force",
        )
    except FileNotFoundError as exc:
        print(f"  SKIP — classifier failed: {exc}")
        return {"animal": animal, "date": date, "status": "skip_classify_error",
                "note": str(exc)}
    print(f"  candidate_trials parquet: {ct_path}")

    # Consolidated within-session PNGs.
    fig_paths = render_within_session_figures(
        animal=animal, date=date, resolver=emit_resolver,
        overwrite="force",
    )
    flat = [p for paths in fig_paths.values() for p in paths]
    print(f"  consolidated PNGs: {len(flat)}")
    for family, paths in fig_paths.items():
        for p in paths:
            kb = p.stat().st_size / 1024
            print(f"    [{family}] {p.name}  ({kb:.1f} KB)")

    legacy_root = _legacy_mismatch_dir(animal, real_resolver)
    legacy_present = legacy_root.exists()
    print(f"  legacy_root: {legacy_root}  exists={legacy_present}")

    expected = _expected_within_session_filenames(animal, date)
    legacy_status: dict[str, bool] = {}
    for family, name in expected.items():
        legacy_path = legacy_root / name
        legacy_status[family] = legacy_path.exists()
        mark = "✓" if legacy_status[family] else "✗"
        print(f"    {mark} [{family}] {name}")

    # Comparison grids land alongside figures_qc + cross_session under the
    # tongue_jaw_mismatch root. The qc_dir helper sits 3 levels below the
    # tongue_jaw_mismatch root (figures_qc/{animal}/{date}); walk up 3
    # levels to reach the root, then descend into comparison_grids.
    cmp_dir = (
        emit_resolver.tongue_jaw_mismatch_qc_dir(animal, date).parent.parent.parent
        / "comparison_grids" / animal / date.strftime("%Y%m%d")
    )
    cmp_paths: list[Path] = []
    for family, paths in fig_paths.items():
        consolidated = paths[0]
        legacy_name = expected[family]
        legacy_path = legacy_root / legacy_name if legacy_present else None
        cmp_path = cmp_dir / f"{animal}_{date.strftime('%Y%m%d')}_{family}_compare.png"
        _render_comparison_grid(
            legacy_path, consolidated, cmp_path,
            title=f"{animal} {date.isoformat()} | {family} | legacy vs consolidated",
        )
        cmp_paths.append(cmp_path)
        kb = cmp_path.stat().st_size / 1024
        print(f"  [cmp] {family}: {cmp_path.name} ({kb:.1f} KB)")

    return {
        "animal": animal, "date": date, "status": "ok",
        "consolidated_paths": flat,
        "comparison_paths": cmp_paths,
        "legacy_status": legacy_status,
    }


def _render_cross_session(
    animal: str,
    real_resolver: PathResolver, emit_resolver: PathResolver,
) -> dict:
    """Render per-mouse cross-session PNGs + comparison grids."""
    print(f"[{animal}] cross-session ...")
    from stroke_orofacial.animals import get_animal

    animal_info = get_animal(animal)
    fig_paths = render_cross_session_figures(
        animal=animal, resolver=emit_resolver, overwrite="force",
        animal_info=animal_info,
    )
    print(f"  consolidated cross-session PNGs: {len(fig_paths)}")
    for family, p in fig_paths.items():
        kb = p.stat().st_size / 1024
        print(f"    [{family}] {p.name}  ({kb:.1f} KB)")

    legacy_root = _legacy_mismatch_dir(animal, real_resolver)
    expected = _expected_cross_session_filenames(animal, animal_info.bin_days)
    legacy_status: dict[str, bool] = {}
    for family, name in expected.items():
        legacy_path = legacy_root / name
        legacy_status[family] = legacy_path.exists()
        mark = "✓" if legacy_status[family] else "✗"
        print(f"    {mark} [{family}] {name}")

    cmp_dir = (
        emit_resolver.tongue_jaw_mismatch_cross_session_dir(animal).parent.parent
        / "comparison_grids" / animal / "cross_session"
    )
    cmp_paths: list[Path] = []
    for family, consolidated in fig_paths.items():
        legacy_name = expected[family]
        legacy_path = legacy_root / legacy_name if legacy_root.exists() else None
        cmp_path = cmp_dir / f"{animal}_{family}_compare.png"
        _render_comparison_grid(
            legacy_path, consolidated, cmp_path,
            title=f"{animal} | {family} | legacy vs consolidated",
        )
        cmp_paths.append(cmp_path)
        kb = cmp_path.stat().st_size / 1024
        print(f"  [cmp] {family}: {cmp_path.name} ({kb:.1f} KB)")

    return {
        "animal": animal, "status": "ok",
        "consolidated_paths": list(fig_paths.values()),
        "comparison_paths": cmp_paths,
        "legacy_status": legacy_status,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7a.5 mismatch visual gate runner.",
    )
    parser.add_argument(
        "--emit-root", type=Path, default=None,
        help="Redirect emit to this dir (default: MICROSCOPE pipeline_outputs).",
    )
    parser.add_argument(
        "--sessions", default="default",
        help="Comma-separated <animal>:<YYYY-MM-DD> pairs, or 'default'.",
    )
    parser.add_argument(
        "--cross-animals", default="default",
        help="Comma-separated animals for cross-session render, or 'default'.",
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

    if args.cross_animals == "default":
        cross_animals = list(DEFAULT_CROSS_ANIMALS)
    else:
        cross_animals = [
            a.strip() for a in args.cross_animals.split(",") if a.strip()
        ]

    print("Phase 7a.5 mismatch visual gate runner")
    print(f"  emit_root: {args.emit_root or '<MICROSCOPE pipeline_outputs default>'}")
    print(f"  sessions: {[f'{a}:{d.isoformat()}' for a, d in sessions]}")
    print(f"  cross_animals: {cross_animals}")
    print()

    session_results = []
    for animal, date in sessions:
        result = _render_session(animal, date, real_resolver, emit_resolver)
        session_results.append(result)
        print()

    cross_results = []
    for animal in cross_animals:
        result = _render_cross_session(animal, real_resolver, emit_resolver)
        cross_results.append(result)
        print()

    print("=" * 80)
    print("Within-session summary:")
    for r in session_results:
        if r["status"] != "ok":
            print(f"  {r['animal']}/{r['date'].isoformat()}: {r['status']} — {r.get('note', '')}")
            continue
        legacy_match = sum(r["legacy_status"].values())
        legacy_total = len(r["legacy_status"])
        print(
            f"  {r['animal']}/{r['date'].isoformat()}: "
            f"{len(r['consolidated_paths'])} consolidated PNGs + "
            f"{len(r['comparison_paths'])} cmp grids; "
            f"legacy match {legacy_match}/{legacy_total}",
        )

    print("Cross-session summary:")
    for r in cross_results:
        if r["status"] != "ok":
            print(f"  {r['animal']}: {r['status']}")
            continue
        legacy_match = sum(r["legacy_status"].values())
        legacy_total = len(r["legacy_status"])
        print(
            f"  {r['animal']}: {len(r['consolidated_paths'])} cross-session PNGs + "
            f"{len(r['comparison_paths'])} cmp grids; "
            f"legacy match {legacy_match}/{legacy_total}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
