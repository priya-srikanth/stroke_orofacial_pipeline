"""Phase 9.1 Q-lock 13b Stage 5 — cohort emit driver.

Re-emits per-trial tongue endpoints JSONs across a cohort with the
new ``tongue.phase_aligned_endpoints`` block, then runs Stages 2–4
(per-session + phenotype-pooled aggregation, 72-test Wilcoxon ×
BH-FDR family, 6-figure renderer). Produces the manifest CSV
(``emit_manifest.csv``) summarizing OK/SKIP/FAIL per session and per
figure.

Confirm-once-then-force pattern per Priya 2026-05-27 Stage 5
direction: pass ``--overwrite=force`` to actually rewrite. The
default is ``skip``, which is safe but typically a no-op (the
phase_aligned_endpoints block won't be added if the JSON exists).

Usage::

    # Pilot — PS46 only.
    python scripts/phase_9_1_q13b/emit_cohort.py \\
        --animals PS46 --overwrite force

    # Full 8-animal cohort.
    python scripts/phase_9_1_q13b/emit_cohort.py \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 --overwrite force
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    build_tongue_pertrial_by_animal_date,
)
from stroke_orofacial.figures.phase_aligned_endpoint_stats import (  # noqa: E402
    FIGURE_SUBDIR,
    compute_phase_aligned_endpoint_stats,
    emit_phase_aligned_endpoint_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_per_session_median_iqr,
    aggregate_phenotype_pooled_median_iqr,
    attach_phenotype_and_epoch,
    enumerate_session_dates,
    load_cohort_phase_aligned_endpoints_long,
)


COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")


# ---------------------------------------------------------------------------
# Stage 5a — per-session re-emit
# ---------------------------------------------------------------------------


def reemit_session(
    *,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    overwrite: str,
    logger: logging.Logger,
) -> tuple[str, float, str]:
    """Re-emit one (animal, date) per-trial tongue artifact.

    Returns
    -------
    (status, wall_time_s, error_message)
        Status one of "OK", "SKIP", "FAIL". Wall-time is the seconds
        elapsed in this call. error_message is "" on success.
    """
    t0 = time.perf_counter()
    try:
        result = build_tongue_pertrial_by_animal_date(
            animal=animal, date=date, resolver=resolver,
            overwrite=overwrite,
        )
        elapsed = time.perf_counter() - t0
        if result is None:
            return ("SKIP", elapsed, "")
        return ("OK", elapsed, "")
    except Exception as exc:  # pragma: no cover — surfaces in manifest
        elapsed = time.perf_counter() - t0
        logger.exception(
            "re-emit FAILED for %s/%s: %s",
            animal, date.isoformat(), exc,
        )
        return ("FAIL", elapsed, f"{type(exc).__name__}: {exc}")


def reemit_animal(
    *,
    animal: str,
    resolver: PathResolver,
    overwrite: str,
    logger: logging.Logger,
) -> list[dict[str, object]]:
    """Re-emit every on-disk session for one animal. Returns per-session manifest rows."""
    dates = enumerate_session_dates(animal, resolver)
    logger.info(
        "[%s] re-emitting %d session(s) with overwrite=%s",
        animal, len(dates), overwrite,
    )
    rows: list[dict[str, object]] = []
    for d in dates:
        status, elapsed, err = reemit_session(
            animal=animal, date=d, resolver=resolver,
            overwrite=overwrite, logger=logger,
        )
        logger.info(
            "  [%s/%s] %s in %.2fs%s",
            animal, d.isoformat(), status, elapsed,
            f" — {err}" if err else "",
        )
        rows.append({
            "animal": animal,
            "date": d.isoformat(),
            "status": status,
            "wall_time_s": elapsed,
            "error": err,
        })
    return rows


# ---------------------------------------------------------------------------
# Stage 5b — cohort-wide stats + figures
# ---------------------------------------------------------------------------


def run_stats_and_figures(
    *,
    animals: list[str],
    resolver: PathResolver,
    overwrite: str,
    output_dir: Path | None,
    logger: logging.Logger,
) -> dict[str, object]:
    """Run Stages 2 → 3 → 4 on the re-emitted cohort and write outputs.

    Returns a dict with paths to the produced artifacts + Stage 4
    renderer return value.
    """
    logger.info("Loading cohort long-form rows from re-emitted JSONs...")
    long_df = load_cohort_phase_aligned_endpoints_long(
        animals=animals, resolver=resolver,
    )
    logger.info("  loaded %d long-form rows", len(long_df))

    if long_df.empty:
        logger.error(
            "load_cohort_phase_aligned_endpoints_long returned 0 rows — "
            "re-emit may have failed or no JSONs carry the phase_aligned_endpoints "
            "block. Skipping stats + figures.",
        )
        return {"status": "no_rows"}

    logger.info("Stage 2: per-session median + IQR aggregation...")
    per_session = aggregate_per_session_median_iqr(long_df)
    logger.info("  per-session rows: %d", len(per_session))

    logger.info("Stage 3: phenotype + epoch attachment...")
    animals_map = {a: info for a, info in load_animals().items() if a in animals}
    per_session_meta = attach_phenotype_and_epoch(per_session, animals_map)
    logger.info(
        "  per-session rows after phenotype attach: %d (dropped %d)",
        len(per_session_meta), len(per_session) - len(per_session_meta),
    )

    pooled = aggregate_phenotype_pooled_median_iqr(per_session_meta, by_side=True)
    logger.info("  phenotype-pooled rows: %d", len(pooled))

    logger.info("Stage 4a: 72-test Wilcoxon × BH-FDR compute...")
    stats_df = compute_phase_aligned_endpoint_stats(per_session_meta)
    logger.info("  stats rows: %d", len(stats_df))

    logger.info("Stage 4b: 6-figure render + manifest...")
    figure_result = emit_phase_aligned_endpoint_figures(
        per_session_df=per_session_meta,
        stats_df=stats_df,
        resolver=resolver,
        output_dir=output_dir,
        overwrite="force" if overwrite == "force" else "prompt",
    )
    logger.info(
        "  figures OK=%d SKIP=%d FAIL=%d",
        len(figure_result["OK"]), len(figure_result["SKIP"]),
        len(figure_result["FAIL"]),
    )

    out_dir = (
        output_dir if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    # Also save the phenotype-pooled summary alongside.
    pooled_csv = out_dir / "phenotype_pooled_median_iqr.csv"
    pooled.to_csv(pooled_csv, index=False)
    logger.info("Wrote phenotype-pooled summary CSV: %s", pooled_csv)

    return {
        "status": "ok",
        "long_df_rows": len(long_df),
        "per_session_rows": len(per_session_meta),
        "pooled_rows": len(pooled),
        "stats_csv": figure_result["stats_csv"],
        "per_session_csv": figure_result["per_session_csv"],
        "manifest_csv": figure_result["manifest_csv"],
        "pooled_csv": pooled_csv,
        "figures_ok": list(figure_result["OK"]),
        "figures_skip": list(figure_result["SKIP"]),
        "figures_fail": list(figure_result["FAIL"]),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def parse_animals(raw: str) -> list[str]:
    """Parse a comma-separated --animals arg."""
    out: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not re.fullmatch(r"PS\d{2}", tok):
            raise argparse.ArgumentTypeError(
                f"animal id must match PSdd; got {tok!r}",
            )
        out.append(tok)
    if not out:
        raise argparse.ArgumentTypeError("no animals provided")
    return out


def print_scope_summary(
    *,
    animals: list[str],
    resolver: PathResolver,
    overwrite: str,
    logger: logging.Logger,
) -> dict[str, int]:
    """Pre-flight summary — animal × session counts + size estimate."""
    logger.info("=" * 72)
    logger.info("Phase 9.1 Q-lock 13b Stage 5 cohort emit — scope summary")
    logger.info("=" * 72)
    logger.info("Animals: %s", ", ".join(animals))
    logger.info("Overwrite mode: %s", overwrite)
    total = 0
    per_animal: dict[str, int] = {}
    for animal in animals:
        n = len(enumerate_session_dates(animal, resolver))
        per_animal[animal] = n
        total += n
        logger.info("  %s: %d sessions", animal, n)
    logger.info("Total sessions to re-emit: %d", total)
    logger.info("=" * 72)
    return per_animal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 9.1 Q-lock 13b Stage 5 cohort emit driver.",
    )
    parser.add_argument(
        "--animals",
        type=parse_animals,
        default=list(COHORT_8),
        help=(
            "Comma-separated animal IDs (default: 8-animal Q-lock 13b cohort). "
            "Example: PS46,PS47 for a pilot subset."
        ),
    )
    parser.add_argument(
        "--overwrite",
        choices=("skip", "force"),
        default="skip",
        help=(
            "skip (default, safe) re-emits only sessions missing any output. "
            "force always rewrites — pass for Stage 5 cohort re-emit."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Optional override for the figure / stats output dir "
            "(default: pipeline_outputs/<Q-lock 15 subdir>)."
        ),
    )
    parser.add_argument(
        "--skip-reemit",
        action="store_true",
        help=(
            "Skip per-session re-emit; just re-run Stages 2-4 on whatever "
            "JSONs are on disk. Useful for re-rendering figures after a "
            "manual JSON adjustment."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("phase_9_1_q13b.emit_cohort")

    resolver = PathResolver()
    animals = args.animals
    if isinstance(animals, str):
        animals = parse_animals(animals)

    overall_t0 = time.perf_counter()
    print_scope_summary(
        animals=animals, resolver=resolver,
        overwrite=args.overwrite, logger=logger,
    )

    all_session_rows: list[dict[str, object]] = []
    if not args.skip_reemit:
        for animal in animals:
            rows = reemit_animal(
                animal=animal, resolver=resolver,
                overwrite=args.overwrite, logger=logger,
            )
            all_session_rows.extend(rows)
        # Per-animal wall-time summary.
        wt_by_animal: dict[str, float] = {}
        for r in all_session_rows:
            wt_by_animal[r["animal"]] = (
                wt_by_animal.get(r["animal"], 0.0) + float(r["wall_time_s"])
            )
        logger.info("Per-animal re-emit wall-time:")
        for animal, wt in wt_by_animal.items():
            n = sum(1 for r in all_session_rows if r["animal"] == animal)
            logger.info(
                "  %s: %.1fs across %d sessions (%.2fs/session avg)",
                animal, wt, n, wt / max(1, n),
            )
    else:
        logger.info("--skip-reemit: skipping per-session re-emit phase")

    # Write the per-session re-emit manifest alongside the cohort outputs.
    out_dir = (
        args.output_dir if args.output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    if all_session_rows:
        reemit_manifest_csv = out_dir / "stage5_reemit_manifest.csv"
        pd.DataFrame(all_session_rows).to_csv(
            reemit_manifest_csv, index=False,
        )
        logger.info("Wrote re-emit manifest CSV: %s", reemit_manifest_csv)

    # Run Stages 2-4.
    figs_result = run_stats_and_figures(
        animals=animals, resolver=resolver,
        overwrite=args.overwrite, output_dir=args.output_dir,
        logger=logger,
    )
    logger.info("Stats + figures result: %s", json.dumps(
        {k: str(v) if isinstance(v, (Path,)) else v
         for k, v in figs_result.items() if k not in ("figures_ok",
                                                       "figures_skip",
                                                       "figures_fail")},
        default=str,
        indent=2,
    ))

    total_elapsed = time.perf_counter() - overall_t0
    logger.info("=" * 72)
    logger.info("Stage 5 cohort emit complete in %.1fs", total_elapsed)
    logger.info("=" * 72)

    # FAIL exit code if any session re-emit FAILED.
    fails = [r for r in all_session_rows if r["status"] == "FAIL"]
    if fails:
        logger.error(
            "%d session re-emit FAILURE(s):",
            len(fails),
        )
        for r in fails:
            logger.error("  %s/%s — %s", r["animal"], r["date"], r["error"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
