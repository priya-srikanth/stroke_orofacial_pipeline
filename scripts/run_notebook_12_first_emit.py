"""Standalone runner that reproduces notebook 12's tone-aligned emit loop.

Phase 6.8a addition. Notebook 12
(``notebooks/12_dlc_spatial_tone_aligned.ipynb``) is the interactive
entry point for the DLC tone-aligned heatmap + NPZ emit; this script
is the non-interactive equivalent so the first Phase-6 emit can run
unattended on a headless machine (e.g. the Windows box while Priya's
Mac laptop is closed). It imports the same modules, calls the same
helpers, and writes to the same on-disk paths — no duplicated
arithmetic. The notebook remains the canonical reference for the
orchestration logic; this script just skips the kernel.

Usage::

    python scripts/run_notebook_12_first_emit.py                    # mirrors notebook default
    python scripts/run_notebook_12_first_emit.py --overwrite force  # first-emit / full re-emit
    python scripts/run_notebook_12_first_emit.py --animals PS46 PS47
    python scripts/run_notebook_12_first_emit.py \
        --bodyparts tongue --center-modes nose \
        --tone-windows-ms=-500,5000 --tone-windows-ms=-100,1000 \
        --trial-groups L R all

Note: ``--tone-windows-ms`` is ``action='append'`` (one window per
invocation) and values must use the ``=`` form (``--tone-windows-ms=-500,5000``)
because the leading minus would otherwise be parsed as a flag.

Rationale for "script rather than nbconvert": running
``jupyter nbconvert --execute`` would require either editing the
``OVERWRITE`` constant in the notebook (violating CLAUDE.md rule 3 on
drive-by edits) or wrapping in papermill (extra dep, no other uses in
the repo). A dedicated runner keeps the one-time migration auditable
as a committed artifact and is trivial to re-run per-animal later.

After this script finishes, run the health report to validate::

    python scripts/phase_6_8a_first_run_health_report.py --verbose

Exit codes:
    0 — loop completed (individual session failures are logged, not fatal)
    1 — unrecoverable setup error (bad args, missing config, etc.)
"""
from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from stroke_orofacial.animals import load_animals
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_analysis,
    save_tone_aligned_npz,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver


def _parse_window_ms(spec: str) -> tuple[float, float]:
    """Parse a ``--tone-windows-ms`` token like ``-500,5000`` into a tuple."""
    try:
        pre, post = spec.split(",")
        return (float(pre), float(post))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--tone-windows-ms token must be 'pre,post' floats (e.g. -500,5000), got {spec!r}"
        ) from exc


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
        "--bodyparts", nargs="*",
        default=["tongue", "jaw", "nose"],
        help="Bodyparts to render (default: tongue jaw nose).",
    )
    parser.add_argument(
        "--center-modes", nargs="*",
        default=["nose", "spout_midpoint", "eye_midpoint"],
        help="Centering modes to render (default: nose spout_midpoint eye_midpoint).",
    )
    parser.add_argument(
        "--tone-windows-ms", action="append", type=_parse_window_ms,
        default=None, metavar="PRE,POST",
        help=(
            "Reward window as comma-separated pre,post ms. Repeat the flag for "
            "multiple windows; leading-minus values require the '=' form, e.g. "
            "--tone-windows-ms=-500,5000 --tone-windows-ms=-100,1000. "
            "Default (no flags): -500,5000 and -100,1000."
        ),
    )
    parser.add_argument(
        "--trial-groups", nargs="*",
        default=["all", "L", "R"],
        help="Trial-group filters (default: all L R).",
    )
    parser.add_argument(
        "--overwrite", choices=["skip", "force"], default="skip",
        help=(
            "'skip' (default, matches notebook) writes only when PNG is absent; "
            "'force' re-emits PNG+NPZ everywhere. Use 'force' for the Phase 6.8a "
            "first emit so NPZs are written even where PNGs already exist from "
            "pre-6.8a runs."
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
    """Replicates notebook 12 cell 3's manifest-building loop."""
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


def _render_and_save(
    result: dict,
    *,
    animal_id: str,
    date_str: str,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    win_tag: str,
    out_path: Path,
) -> None:
    """Replicates cell 4's matplotlib rendering + NPZ save."""
    hist = result["histogram"]
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    if hist["H_counts"].sum() > 0:
        ax.imshow(
            hist["H_proportion"].T,
            extent=hist["extent"],
            origin="lower",
            aspect="auto",
            cmap="magma",
            norm=LogNorm(vmin=1e-5),
        )
    ax.set_title(
        f"{animal_id} {bodypart} {date_str}\n"
        f"{center_mode} | {trial_group} | {win_tag}\n"
        f"tones={result['n_tones']}, frames={result['n_selected_frames']}"
    )
    ax.set_xlabel(f"{bodypart}_x")
    ax.set_ylabel(f"{bodypart}_y")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Phase 6.8a: also save the histogram as NPZ. The helper stamps the
    # per-animal L/R flag from ``result`` so the trial_group label is
    # unambiguous at read time.
    save_tone_aligned_npz(result, out_path.with_suffix(".npz"))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    log = logging.getLogger("phase_6_8a.first_emit")

    resolver = PathResolver()
    animals_config = load_animals()
    defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    output_root = resolver.pipeline_outputs("dlc_analysis") / "spatial_tone_aligned"

    animal_ids = args.animals if args.animals is not None else list(animals_config.keys())
    unknown = sorted(set(animal_ids) - set(animals_config.keys()))
    if unknown:
        log.error("Unknown animal IDs (not in animals.yaml): %s", unknown)
        return 1

    # argparse can't default ``action="append"`` to a list without the
    # default leaking into user-supplied runs; do the fallback here so
    # the bare ``--tone-windows-ms=-500,5000`` invocation overrides
    # the notebook default cleanly.
    tone_windows_ms = (
        args.tone_windows_ms
        if args.tone_windows_ms is not None
        else [(-500.0, 5000.0), (-100.0, 1000.0)]
    )

    # Cell 3: manifests
    manifests = _build_manifests(animal_ids, args.dates, animals_config, resolver)
    n_with_dlc = sum(1 for _, _, m in manifests if m.dlc_h5_files)
    n_with_align = sum(1 for _, _, m in manifests if m.alignment_template is not None)
    log.info("Built %d manifests", len(manifests))
    log.info("  with DLC files:           %d", n_with_dlc)
    log.info("  with alignment template:  %d", n_with_align)
    log.info(
        "Config: overwrite=%s  bodyparts=%s  center_modes=%s  windows=%s  trial_groups=%s",
        args.overwrite,
        args.bodyparts,
        args.center_modes,
        tone_windows_ms,
        args.trial_groups,
    )

    # Cell 4: quadruple-nested loop.
    grand_ok = grand_skip = grand_err = 0
    grand_skip_no_tones = grand_skip_no_frames = 0
    for center_mode in args.center_modes:
        for bodypart in args.bodyparts:
            for window_ms in tone_windows_ms:
                for trial_group in args.trial_groups:
                    n_ok = n_skip = n_err = 0
                    n_skip_no_tones = n_skip_no_frames = 0
                    win_tag = f"{int(window_ms[0])}to{int(window_ms[1])}ms"

                    for animal_id, date, manifest in manifests:
                        date_str = date.strftime("%Y%m%d")
                        out_dir = (
                            output_root / f"{bodypart}_{center_mode}"
                            / f"trials-{trial_group}_{win_tag}" / animal_id
                        )
                        out_path = out_dir / f"heatmap_{date_str}.png"

                        if args.overwrite == "skip" and out_path.exists():
                            n_skip += 1
                            continue

                        try:
                            animal_info = animals_config[animal_id]
                            result = build_tone_aligned_analysis(
                                manifest, bodypart, center_mode, trial_group,
                                window_ms, resolver,
                                spatial_config, tone_config,
                                wavesurfer_sides_match_mouse_sides=(
                                    animal_info.wavesurfer_sides_match_mouse_sides
                                ),
                            )
                            # Phase 6.8a.3: split the two legitimate-empty
                            # skip conditions so the emit log
                            # distinguishes them. See notebook 12 cell 4
                            # for rationale.
                            if result is None:
                                n_skip_no_tones += 1
                                log.info(
                                    "skip_no_tones %s/%s/%s/%s/%s/%s",
                                    animal_id, date_str, bodypart,
                                    center_mode, trial_group, win_tag,
                                )
                                continue
                            if result["histogram"] is None:
                                n_skip_no_frames += 1
                                log.info(
                                    "skip_no_frames %s/%s/%s/%s/%s/%s",
                                    animal_id, date_str, bodypart,
                                    center_mode, trial_group, win_tag,
                                )
                                continue
                            _render_and_save(
                                result,
                                animal_id=animal_id,
                                date_str=date_str,
                                bodypart=bodypart,
                                center_mode=center_mode,
                                trial_group=trial_group,
                                win_tag=win_tag,
                                out_path=out_path,
                            )
                            n_ok += 1
                        except FileNotFoundError as e:
                            n_err += 1
                            log.warning(
                                "%s/%s/%s/%s/%s: %s",
                                animal_id, date_str, bodypart, center_mode,
                                trial_group, e,
                            )
                        except Exception as e:  # noqa: BLE001 — mirror notebook cell 4
                            n_err += 1
                            log.warning(
                                "%s/%s/%s/%s/%s: %s",
                                animal_id, date_str, bodypart, center_mode,
                                trial_group, e,
                            )

                    tag = f"{bodypart}/{center_mode}/trials-{trial_group}/{win_tag}"
                    if (
                        n_ok + n_skip + n_err
                        + n_skip_no_tones + n_skip_no_frames
                        > 0
                    ):
                        print(
                            f"  {tag}: ok={n_ok} skip={n_skip} "
                            f"skip_no_tones={n_skip_no_tones} "
                            f"skip_no_frames={n_skip_no_frames} err={n_err}"
                        )
                    grand_ok += n_ok
                    grand_skip += n_skip
                    grand_skip_no_tones += n_skip_no_tones
                    grand_skip_no_frames += n_skip_no_frames
                    grand_err += n_err

    print(
        f"\nTotals: ok={grand_ok} skip={grand_skip} "
        f"skip_no_tones={grand_skip_no_tones} "
        f"skip_no_frames={grand_skip_no_frames} err={grand_err} "
        f"(output_root={output_root})"
    )
    print(
        "Next: python scripts/phase_6_8a_first_run_health_report.py --verbose"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
