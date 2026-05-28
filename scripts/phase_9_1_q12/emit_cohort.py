"""Phase 9.1 Q-lock 12 Stage 4 — cohort emit driver.

Iterates the 8-animal cohort, computes per-(animal, side, bodypart,
post_epoch) within-baseline proportion-diff arrays via the Stage 1
module, phenotype-pools via the Stage 2 aggregator, then renders the 4
SVG figures via the Stage 3 renderer. Produces a per-animal manifest
CSV (``q12_per_animal_manifest.csv``) and the figure-emit manifest
(``emit_manifest.csv`` from Stage 3) under the Q12-J output directory.

Confirm-once-then-force pattern matching Q-lock 13b's
``scripts/phase_9_1_q13b/emit_cohort.py``: pass ``--overwrite=force``
to actually overwrite existing SVGs. Default ``prompt`` will RAISE on
the first existing target so the operator must consciously rerun with
``force``.

Usage::

    # Pilot — PS46 only, force overwrite (so a re-run on top of the
    # previous PS46 pilot output overwrites).
    conda run -n stroke_orofacial python scripts/phase_9_1_q12/emit_cohort.py \\
        --animals PS46 --overwrite force

    # Full 8-animal cohort.
    conda run -n stroke_orofacial python scripts/phase_9_1_q12/emit_cohort.py \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 --overwrite force

STAGE 4 LOCK (Q12-L per kickoff): this script is built but NOT yet
launched. STOP and ask Priya before invoking — per-invocation Priya
approval required per GR7.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path bootstrap (so the script runs from a clone without needing the
# editable install — useful for sandbox / one-off runs).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_spatial.render_on_demand import (  # noqa: E402
    _split_pre_post_dates,
)
from stroke_orofacial.figures.palette import PHENOTYPE_ORDER  # noqa: E402
from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (  # noqa: E402
    FIGURE_SUBDIR,
    compute_cohort_shared_vmax,
    emit_phenotype_pooled_proportion_diff_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_phenotype_pooled_spatial_diff,
)
from stroke_orofacial.stats.spatial_proportion_diff import (  # noqa: E402
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
    compute_per_animal_per_epoch_diff,
    compute_per_animal_pre_pool,
    split_post_dates_by_epoch,
)


COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# Phenotype remap variants. ``none`` keeps the canonical 4-tier YAML
# labels (PHENOTYPE_ORDER). ``3tier`` merges ``moderate-severe`` into
# ``moderate``, producing a 3-tier phenotype-pooled figure with one
# more animal per moderate-tier panel. Output directory is suffixed
# with ``3_phenotype/`` so the 4-tier figures are not clobbered.
PHENOTYPE_REMAP_3TIER: dict[str, str] = {"moderate-severe": "moderate"}
PHENOTYPE_ORDER_3TIER: tuple[str, ...] = ("mild", "moderate", "severe")
FIGURE_SUBDIR_3TIER_SUFFIX: str = "3_phenotype"


# ---------------------------------------------------------------------------
# Stage 4a — per-animal compute
# ---------------------------------------------------------------------------


def compute_per_animal_records(
    *,
    animal: str,
    resolver: PathResolver,
    defaults: dict,
    animals_map: dict,
    logger: logging.Logger,
) -> tuple[list[dict], list[dict[str, object]]]:
    """Run Stage 1 over (bp × side × epoch) for one animal.

    Returns ``(records, audit_rows)``:

    - ``records`` is a list of per-(animal, side, bp, post_epoch) dicts
      directly consumable by
      :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`.
      One record per produced D array (None-D records are skipped).
    - ``audit_rows`` is a list of one-row-per-(side, bp, post_epoch)
      bookkeeping dicts (also including pre-pool computation for the
      sample-size table) recording status, wall-time, sample counts,
      and a |D|.p99 sanity stat. Sent into the Stage 4 per-animal
      manifest CSV.
    """
    animal_info = animals_map[animal]
    all_dates = yaml_driven_session_dates(
        animal, animal_info=animal_info, analysis_context="dlc.spatial",
    )
    pre_dates, post_dates = _split_pre_post_dates(all_dates, animal_info)
    by_epoch = split_post_dates_by_epoch(animal_info, post_dates)
    logger.info(
        "[%s] dates: pre=%d, acute=%d, sub_acute=%d, chronic=%d",
        animal, len(pre_dates),
        len(by_epoch["acute"]), len(by_epoch["sub_acute"]),
        len(by_epoch["chronic"]),
    )

    records: list[dict] = []
    audit_rows: list[dict[str, object]] = []
    for bodypart in BODYPART_CENTER_MODES:
        for side in SIDES:
            t_pre = time.perf_counter()
            try:
                pre_pool = compute_per_animal_pre_pool(
                    animal=animal, bodypart=bodypart, side=side,
                    resolver=resolver, defaults=defaults,
                    animal_info=animal_info, pre_dates=pre_dates,
                )
            except Exception as exc:
                pre_elapsed = time.perf_counter() - t_pre
                logger.exception(
                    "[%s/%s/%s] pre-pool computation FAILED: %s",
                    animal, bodypart, side, exc,
                )
                audit_rows.append({
                    "animal": animal, "bodypart": bodypart, "side": side,
                    "epoch": "pre",
                    "status": "FAIL", "wall_time_s": pre_elapsed,
                    "n_sessions": 0, "n_trials": 0, "n_total_frames": 0,
                    "abs_d_p99": np.nan,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                # Skip the per-epoch diffs because there's no baseline.
                continue
            pre_elapsed = time.perf_counter() - t_pre
            if pre_pool is None:
                logger.warning(
                    "[%s/%s/%s] pre-pool empty (no contributing sessions); "
                    "skipping all post-epoch diffs.",
                    animal, bodypart, side,
                )
                audit_rows.append({
                    "animal": animal, "bodypart": bodypart, "side": side,
                    "epoch": "pre",
                    "status": "EMPTY_POOL", "wall_time_s": pre_elapsed,
                    "n_sessions": 0, "n_trials": 0, "n_total_frames": 0,
                    "abs_d_p99": np.nan, "error": "",
                })
                continue
            audit_rows.append({
                "animal": animal, "bodypart": bodypart, "side": side,
                "epoch": "pre",
                "status": "OK", "wall_time_s": pre_elapsed,
                "n_sessions": pre_pool["n_pre_sessions"],
                "n_trials": pre_pool["n_pre_trials"],
                "n_total_frames": pre_pool["n_total_pre_frames"],
                "abs_d_p99": np.nan, "error": "",
            })

            for post_epoch in POST_EPOCHS:
                t_ep = time.perf_counter()
                try:
                    rec = compute_per_animal_per_epoch_diff(
                        animal=animal, bodypart=bodypart, side=side,
                        post_epoch=post_epoch, pre_pool=pre_pool,
                        resolver=resolver, defaults=defaults,
                        animal_info=animal_info,
                        post_dates_by_epoch=by_epoch,
                    )
                except Exception as exc:
                    ep_elapsed = time.perf_counter() - t_ep
                    logger.exception(
                        "[%s/%s/%s/%s] epoch diff FAILED: %s",
                        animal, bodypart, side, post_epoch, exc,
                    )
                    audit_rows.append({
                        "animal": animal, "bodypart": bodypart,
                        "side": side, "epoch": post_epoch,
                        "status": "FAIL", "wall_time_s": ep_elapsed,
                        "n_sessions": 0, "n_trials": 0, "n_total_frames": 0,
                        "abs_d_p99": np.nan,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    continue
                ep_elapsed = time.perf_counter() - t_ep
                if rec is None:
                    logger.info(
                        "[%s/%s/%s/%s] empty epoch (no contributing sessions)",
                        animal, bodypart, side, post_epoch,
                    )
                    audit_rows.append({
                        "animal": animal, "bodypart": bodypart,
                        "side": side, "epoch": post_epoch,
                        "status": "EMPTY_EPOCH",
                        "wall_time_s": ep_elapsed,
                        "n_sessions": 0, "n_trials": 0, "n_total_frames": 0,
                        "abs_d_p99": np.nan, "error": "",
                    })
                    continue
                D = rec["D"]
                finite_abs = np.abs(D[np.isfinite(D)])
                p99 = float(np.percentile(finite_abs, 99.0)) if finite_abs.size else np.nan
                audit_rows.append({
                    "animal": animal, "bodypart": bodypart,
                    "side": side, "epoch": post_epoch,
                    "status": "OK", "wall_time_s": ep_elapsed,
                    "n_sessions": rec["n_post_sessions"],
                    "n_trials": rec["n_post_trials"],
                    "n_total_frames": rec["n_total_post_frames"],
                    "abs_d_p99": p99, "error": "",
                })
                records.append({
                    "animal": animal,
                    "side": side,
                    "bodypart": bodypart,
                    "post_epoch": post_epoch,
                    "D": D,
                    "extent": rec["extent"],
                    "n_pre_trials": rec["n_pre_trials"],
                    "n_post_trials": rec["n_post_trials"],
                })
                logger.info(
                    "[%s/%s/%s/%s] OK in %.2fs (n_post_sess=%d, "
                    "n_post_trials=%d, |D|.p99=%.4f)",
                    animal, bodypart, side, post_epoch, ep_elapsed,
                    rec["n_post_sessions"], rec["n_post_trials"], p99,
                )

    return records, audit_rows


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def parse_animals(raw: str) -> list[str]:
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
) -> None:
    logger.info("=" * 72)
    logger.info("Phase 9.1 Q-lock 12 Stage 4/5 cohort emit — scope summary")
    logger.info("=" * 72)
    logger.info("Animals: %s", ", ".join(animals))
    logger.info("Overwrite mode: %s", overwrite)
    logger.info(
        "Bodyparts x sides x epochs: %d x %d x %d = %d D arrays / animal",
        len(BODYPART_CENTER_MODES), len(SIDES), len(POST_EPOCHS),
        len(BODYPART_CENTER_MODES) * len(SIDES) * len(POST_EPOCHS),
    )
    logger.info("Output: pipeline_outputs/%s/", FIGURE_SUBDIR)
    logger.info("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 9.1 Q-lock 12 Stage 4 cohort emit driver.",
    )
    parser.add_argument(
        "--animals",
        type=parse_animals,
        default=list(COHORT_8),
        help=(
            "Comma-separated animal IDs (default: 8-animal Q-lock 12/13b "
            "cohort). Example: PS46 for the pilot subset."
        ),
    )
    parser.add_argument(
        "--overwrite",
        choices=("skip", "force", "prompt"),
        default="prompt",
        help=(
            "Confirm-once-then-force pattern. prompt (default): raise on "
            "first existing SVG. skip: leave existing SVGs untouched. "
            "force: overwrite without prompting."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Optional override for the figure output dir "
            "(default: pipeline_outputs/<Q12-J subdir>)."
        ),
    )
    parser.add_argument(
        "--remap-phenotypes",
        choices=("none", "3tier"),
        default="none",
        help=(
            "Phenotype remap before pooling. 'none' (default): use the "
            "4-tier YAML labels (mild, moderate, moderate-severe, severe). "
            "'3tier' merges moderate-severe into moderate, producing a "
            "3-tier (mild, moderate, severe) phenotype-pooled figure. "
            "3tier output lands in a '3_phenotype/' subdir so the 4-tier "
            "figures aren't clobbered."
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
    logger = logging.getLogger("phase_9_1_q12.emit_cohort")

    resolver = PathResolver()
    defaults = load_defaults()
    animals = args.animals
    if isinstance(animals, str):
        animals = parse_animals(animals)

    print_scope_summary(
        animals=animals, resolver=resolver,
        overwrite=args.overwrite, logger=logger,
    )

    # Stage 4a/5a: per-animal compute
    overall_t0 = time.perf_counter()
    animals_map = {a: info for a, info in load_animals().items() if a in animals}
    missing = set(animals) - set(animals_map.keys())
    if missing:
        logger.error("animals not found in animals.yaml: %s", sorted(missing))
        return 1

    # Apply phenotype remap (if any) BEFORE the per-animal compute loop —
    # the per-animal D arrays don't depend on phenotype labels, but
    # logging the remapped phenotype here makes the audit log self-
    # documenting.
    if args.remap_phenotypes == "3tier":
        logger.info(
            "Remapping phenotypes: %s (merge moderate-severe into moderate).",
            PHENOTYPE_REMAP_3TIER,
        )
        animals_map = {
            a: dataclasses.replace(
                info,
                recovery_phenotype=PHENOTYPE_REMAP_3TIER.get(
                    info.recovery_phenotype, info.recovery_phenotype,
                ),
            )
            for a, info in animals_map.items()
        }
        phenotype_order = PHENOTYPE_ORDER_3TIER
    else:
        phenotype_order = PHENOTYPE_ORDER

    all_records: list[dict] = []
    all_audit_rows: list[dict[str, object]] = []
    for animal in animals:
        animal_t0 = time.perf_counter()
        records, audit_rows = compute_per_animal_records(
            animal=animal, resolver=resolver,
            defaults=defaults, animals_map=animals_map, logger=logger,
        )
        animal_elapsed = time.perf_counter() - animal_t0
        all_records.extend(records)
        all_audit_rows.extend(audit_rows)
        n_ok = sum(1 for r in audit_rows if r["status"] == "OK"
                   and r["epoch"] in POST_EPOCHS)
        logger.info(
            "[%s] %d OK epoch-records in %.1fs",
            animal, n_ok, animal_elapsed,
        )

    # Stage 5b: phenotype-pool
    logger.info("Phenotype-pooling %d per-animal records...", len(all_records))
    pooled = aggregate_phenotype_pooled_spatial_diff(
        all_records, animals_map,
    )
    logger.info(
        "  pooled records: %d (phenotypes x sides x bps x epochs)",
        len(pooled),
    )

    # Stage 5c: cohort-wide shared_vmax
    shared_vmax = compute_cohort_shared_vmax(pooled)
    logger.info(
        "Cohort-wide shared_vmax (p99 of |D_pooled|): %.5f", shared_vmax,
    )

    # Resolve output directory: --output-dir wins; else 3-tier suffix
    # when remapped; else canonical Q12-J subdir.
    if args.output_dir is not None:
        out_dir_emit = args.output_dir
    elif args.remap_phenotypes == "3tier":
        out_dir_emit = resolver.pipeline_outputs(
            subdir=f"{FIGURE_SUBDIR}/{FIGURE_SUBDIR_3TIER_SUFFIX}",
        )
    else:
        out_dir_emit = None  # let emit_* resolve to FIGURE_SUBDIR

    # Stage 5d: figure emit
    logger.info("Emitting 4 SVG figures (2 bodyparts x 2 sides)...")
    figs_result = emit_phenotype_pooled_proportion_diff_figures(
        pooled,
        resolver=resolver,
        output_dir=out_dir_emit,
        overwrite=args.overwrite,
        shared_vmax=shared_vmax,
        phenotype_order=phenotype_order,
        defaults=defaults,
    )
    logger.info(
        "  figures OK=%d SKIP=%d FAIL=%d",
        len(figs_result["OK"]), len(figs_result["SKIP"]),
        len(figs_result["FAIL"]),
    )

    # Stage 5e: per-animal audit manifest CSV (lands next to the figures
    # so 4-tier vs 3-tier audits don't overwrite each other).
    if args.output_dir is not None:
        out_dir = args.output_dir
    elif args.remap_phenotypes == "3tier":
        out_dir = resolver.pipeline_outputs(
            subdir=f"{FIGURE_SUBDIR}/{FIGURE_SUBDIR_3TIER_SUFFIX}",
        )
    else:
        out_dir = resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_csv = out_dir / "q12_per_animal_manifest.csv"
    pd.DataFrame(
        all_audit_rows,
        columns=[
            "animal", "bodypart", "side", "epoch", "status", "wall_time_s",
            "n_sessions", "n_trials", "n_total_frames", "abs_d_p99", "error",
        ],
    ).to_csv(audit_csv, index=False)
    logger.info("Wrote per-animal audit manifest: %s", audit_csv)

    total_elapsed = time.perf_counter() - overall_t0
    logger.info("=" * 72)
    logger.info(
        "Stage 5 cohort emit complete in %.1fs (n_animals=%d, "
        "n_records=%d, shared_vmax=%.5f)",
        total_elapsed, len(animals), len(all_records), shared_vmax,
    )
    logger.info("=" * 72)

    # Exit nonzero on any FAIL — either compute or render.
    fails = [r for r in all_audit_rows if r["status"] == "FAIL"]
    if fails or figs_result["FAIL"]:
        logger.error(
            "%d compute FAIL(s), %d render FAIL(s) — see manifests.",
            len(fails), len(figs_result["FAIL"]),
        )
        for r in fails[:5]:
            logger.error(
                "  compute %s/%s/%s/%s — %s",
                r["animal"], r["bodypart"], r["side"], r["epoch"], r["error"],
            )
        for key, err in figs_result["FAIL"][:5]:
            logger.error("  render %s — %s", key, err)
        return 1

    # Final JSON summary on stdout for downstream parsing.
    print(json.dumps({
        "n_animals": len(animals),
        "n_records": len(all_records),
        "n_pooled": len(pooled),
        "shared_vmax": float(shared_vmax),
        "wall_time_s": float(total_elapsed),
        "figures_ok": [list(k) for k in figs_result["OK"]],
        "figures_skip": [list(k) for k in figs_result["SKIP"]],
        "manifest_csv": str(figs_result["manifest_csv"]),
        "audit_csv": str(audit_csv),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
