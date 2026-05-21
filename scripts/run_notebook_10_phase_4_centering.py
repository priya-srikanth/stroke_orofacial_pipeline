"""Standalone runner that reproduces notebook 10's Phase 4 centering emit loop.

Companion to ``scripts/run_notebook_12_first_emit.py``. Notebook 10
(``notebooks/10_dlc_build_parquets.ipynb``) is the interactive entry
point for DLC centering (Phase 4); this script is the non-interactive
equivalent so cohort-scale parquet emission can run unattended on a
headless machine (e.g. the Windows box while Priya's Mac is closed).
It imports the same helpers, calls them in the same order, and writes
to the same on-disk paths — no duplicated arithmetic.

Phase 4 is the first DLC-consuming phase. For each (manifest, mode)
it reads ``manifest.dlc_h5_files`` (upstream DLC inference output on
MICROSCOPE), centers coordinates on the chosen landmark, and writes
``{pipeline_outputs}/dlc_analysis/centered_{mode}/{animal}/<h5>.intermediate.<sig>.parquet``.
Phase 4 is prerequisite for Phase 5 (whole-session spatial), Phase 6
(reward-aligned spatial), and Phase 7 (kinematics).

Usage::

    python scripts/run_notebook_10_phase_4_centering.py                    # mirrors notebook default
    python scripts/run_notebook_10_phase_4_centering.py --overwrite force  # full re-emit
    python scripts/run_notebook_10_phase_4_centering.py --animals PS46 PS47
    python scripts/run_notebook_10_phase_4_centering.py \
        --center-modes nose --dates 20250307

After this script finishes, validate the fan-out with::

    python -c "
    from pathlib import Path
    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.paths import PathResolver
    r = PathResolver()
    root = r.pipeline_outputs('dlc_analysis')
    for animal in load_animals():
        for mode in ['nose','spout_midpoint','eye_midpoint']:
            d = root/f'centered_{mode}'/animal
            n = len(list(d.glob('*.parquet'))) if d.exists() else 0
            print(f'{animal}/{mode}: {n} parquets')
    "

Then re-run ``scripts/run_notebook_12_first_emit.py --overwrite force``
on Windows to consume the new centered parquets.

Exit codes:
    0 — loop completed (per-session failures are logged, not fatal)
    1 — unrecoverable setup error (bad args, missing config, etc.)
"""
from __future__ import annotations

import argparse
import datetime
import logging
import sys

from stroke_orofacial.animals import load_animals
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_io.parquet import (
    _save_dlc_session_params,
    build_centered_parquet,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver


def _parse_date(spec: str) -> datetime.date:
    """Parse ``YYYYMMDD`` into a ``datetime.date``."""
    try:
        return datetime.datetime.strptime(spec, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--dates token must be YYYYMMDD, got {spec!r}"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--animals", nargs="*", default=None,
        help="Animal IDs (default: every animal in configs/animals.yaml).",
    )
    parser.add_argument(
        "--dates", nargs="*", type=_parse_date, default=None,
        help="Dates as YYYYMMDD (default: every date in the animal's session range).",
    )
    parser.add_argument(
        "--center-modes", nargs="*",
        default=["nose", "spout_midpoint", "eye_midpoint"],
        help="Centering modes to build (default: nose spout_midpoint eye_midpoint).",
    )
    parser.add_argument(
        "--overwrite", choices=["skip", "force"], default="skip",
        help=(
            "'skip' (default, matches notebook) leaves existing parquets alone; "
            "'force' re-emits every parquet. Use 'force' for a full rebuild after "
            "a Phase 4 logic change; 'skip' for a partial fill-in."
        ),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Increase log verbosity (DEBUG instead of INFO).",
    )
    return parser


def _build_manifests(
    animal_ids: list[str],
    dates: list[datetime.date] | None,
    animals_config,
    resolver: PathResolver,
) -> list[tuple[str, datetime.date, object]]:
    """Replicates notebook 10 cell 3's manifest-building loop."""
    manifests: list[tuple[str, datetime.date, object]] = []
    for animal_id in animal_ids:
        info = animals_config[animal_id]
        if dates is not None:
            iter_dates: list[datetime.date] = list(dates)
        else:
            n_days = (info.session_end - info.session_start).days + 1
            iter_dates = [
                info.session_start + datetime.timedelta(days=i) for i in range(n_days)
            ]
        for date in iter_dates:
            manifest = build_manifest(animal_id, date, resolver, info)
            manifests.append((animal_id, date, manifest))
    return manifests


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    log = logging.getLogger("phase_4.centering")

    resolver = PathResolver()
    animals_config = load_animals()
    defaults = load_defaults()
    dlc_params = defaults.get("dlc_centering", {})
    output_root = resolver.pipeline_outputs("dlc_analysis")

    animal_ids = args.animals if args.animals is not None else list(animals_config.keys())
    unknown = sorted(set(animal_ids) - set(animals_config.keys()))
    if unknown:
        log.error("Unknown animal IDs (not in animals.yaml): %s", unknown)
        return 1

    # Cell 3: manifests
    manifests = _build_manifests(animal_ids, args.dates, animals_config, resolver)
    n_with_dlc = sum(1 for _, _, m in manifests if m.dlc_h5_files)
    n_without_dlc = sum(1 for _, _, m in manifests if not m.dlc_h5_files)
    log.info("Built %d manifests", len(manifests))
    log.info("  with DLC files (will process):    %d", n_with_dlc)
    log.info("  without DLC files (will skip):    %d", n_without_dlc)
    log.info(
        "Config: overwrite=%s  center_modes=%s  output_root=%s",
        args.overwrite, args.center_modes, output_root,
    )

    # Cell 4: per-session × per-mode emit.
    n_written = n_skipped = n_error = 0
    for animal_id, date, manifest in manifests:
        date_str = date.strftime("%Y%m%d")
        any_written = False
        for mode in args.center_modes:
            try:
                result = build_centered_parquet(
                    manifest, mode, resolver,
                    params=dlc_params, overwrite=args.overwrite,
                )
                if result is not None:
                    any_written = True
                    n_written += 1
                else:
                    n_skipped += 1
            except (FileNotFoundError, RuntimeError) as e:
                n_error += 1
                log.warning("Error %s/%s/%s: %s", animal_id, date_str, mode, e)

        # Per-session params.json (always written, captures skipped status)
        _save_dlc_session_params(
            output_root, animal_id, date_str, list(args.center_modes),
            dlc_params, skipped=(not any_written),
        )

    print(
        f"\nDone: Written={n_written} Skipped={n_skipped} Errors={n_error}"
        f" (output_root={output_root})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
