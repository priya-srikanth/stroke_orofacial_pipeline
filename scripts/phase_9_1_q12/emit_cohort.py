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
from stroke_orofacial.cohort_filters import (  # noqa: E402
    SessionFilter,
    apply_session_filter,
    load_filter_spec_from_defaults,
)
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
from stroke_orofacial.figures.phenotype_wasserstein_recovery_boxplot import (  # noqa: E402
    FIGURE_SUBDIR as W2_FIGURE_SUBDIR,
    emit_phenotype_wasserstein_recovery_boxplot_figures,
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
from stroke_orofacial.stats.spatial_wasserstein import (  # noqa: E402
    compute_per_animal_per_session_w2_long,
    compute_per_animal_wasserstein2,
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
    filter_spec: SessionFilter | None = None,
) -> tuple[
    list[dict], list[dict], list[dict], list[dict[str, object]],
]:
    """Run Stage 1 over (bp × side × epoch) for one animal.

    Returns ``(records, w2_records, audit_rows)``:

    - ``records`` is a list of per-(animal, side, bp, post_epoch) dicts
      directly consumable by
      :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`.
      One record per produced D array (None-D records are skipped).
    - ``w2_records`` is the parallel list of W-2 scalar dicts
      (one per produced D record), consumable by
      :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_wasserstein`.
      Same animal/side/bp/post_epoch keys + ``w2`` scalar.
    - ``audit_rows`` is a list of one-row-per-(side, bp, post_epoch)
      bookkeeping dicts (also including pre-pool computation for the
      sample-size table) recording status, wall-time, sample counts,
      a |D|.p99 sanity stat, and the W-2 distance. Sent into the
      Stage 4 per-animal manifest CSV.
    """
    animal_info = animals_map[animal]
    all_dates = yaml_driven_session_dates(
        animal, animal_info=animal_info, analysis_context="dlc.spatial",
    )
    # Q-lock 12a: apply session-level lick filter before pre/post split.
    if filter_spec is not None and not filter_spec.is_pass_through():
        flt = apply_session_filter(animal, all_dates, resolver, filter_spec)
        if flt.dropped:
            logger.info(
                "[%s] session filter dropped %d session(s); kept %d",
                animal, len(flt.dropped), len(flt.kept_dates),
            )
            for d, reason in flt.dropped[:10]:
                logger.info("  drop %s: %s", d.isoformat(), reason)
        all_dates = flt.kept_dates
    pre_dates, post_dates = _split_pre_post_dates(all_dates, animal_info)
    by_epoch = split_post_dates_by_epoch(animal_info, post_dates)
    logger.info(
        "[%s] dates: pre=%d, acute=%d, sub_acute=%d, chronic=%d",
        animal, len(pre_dates),
        len(by_epoch["acute"]), len(by_epoch["sub_acute"]),
        len(by_epoch["chronic"]),
    )

    records: list[dict] = []
    w2_records: list[dict] = []
    per_session_w2_rows: list[dict] = []
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
                "abs_d_p99": np.nan, "w2": np.nan, "error": "",
            })

            # Q-lock 12a: per-session W-2 for pre sessions against the
            # full pre-pool (naive lock — small bias toward 0 acceptable
            # as noise-floor reference). Per-pre-session rows for the
            # boxplot ``Pre`` group.
            pre_session_rows = compute_per_animal_per_session_w2_long(
                animal=animal, pre_pool=pre_pool, post_dates=pre_dates,
                side=side, bodypart=bodypart, resolver=resolver,
                defaults=defaults, animal_info=animal_info,
                epoch_label="pre",
            )
            for row in pre_session_rows:
                row["recovery_phenotype"] = animal_info.recovery_phenotype
            per_session_w2_rows.extend(pre_session_rows)

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
                # Addendum #5: exact W-2 from the same H_pre / H_post.
                t_w2 = time.perf_counter()
                try:
                    w2 = compute_per_animal_wasserstein2(
                        pre_pool=pre_pool,
                        H_post_counts=rec["H_post_counts"],
                        extent=rec["extent"],
                    )
                except Exception as exc:
                    logger.exception(
                        "[%s/%s/%s/%s] W-2 compute FAILED: %s",
                        animal, bodypart, side, post_epoch, exc,
                    )
                    w2 = float("nan")
                w2_elapsed = time.perf_counter() - t_w2
                audit_rows.append({
                    "animal": animal, "bodypart": bodypart,
                    "side": side, "epoch": post_epoch,
                    "status": "OK",
                    "wall_time_s": ep_elapsed + w2_elapsed,
                    "n_sessions": rec["n_post_sessions"],
                    "n_trials": rec["n_post_trials"],
                    "n_total_frames": rec["n_total_post_frames"],
                    "abs_d_p99": p99, "w2": w2, "error": "",
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
                w2_records.append({
                    "animal": animal,
                    "side": side,
                    "bodypart": bodypart,
                    "post_epoch": post_epoch,
                    "w2": w2,
                })

                # Q-lock 12a: per-session W-2 against per-animal pre-pool
                # for the per-epoch dates. Each session gets its own LP.
                post_session_rows = compute_per_animal_per_session_w2_long(
                    animal=animal, pre_pool=pre_pool,
                    post_dates=by_epoch[post_epoch],
                    side=side, bodypart=bodypart, resolver=resolver,
                    defaults=defaults, animal_info=animal_info,
                    epoch_label=post_epoch,
                )
                for row in post_session_rows:
                    row["recovery_phenotype"] = animal_info.recovery_phenotype
                per_session_w2_rows.extend(post_session_rows)
                logger.info(
                    "[%s/%s/%s/%s] OK in %.2fs+W2 %.2fs (n_post_sess=%d, "
                    "n_post_trials=%d, |D|.p99=%.4f, W-2=%.2f)",
                    animal, bodypart, side, post_epoch, ep_elapsed,
                    w2_elapsed, rec["n_post_sessions"], rec["n_post_trials"],
                    p99, w2,
                )

    return records, w2_records, per_session_w2_rows, audit_rows


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
        "--session-filter-config",
        type=Path,
        default=None,
        help=(
            "Optional YAML file overriding configs/defaults.yaml "
            "cohort_filters.default with per-emit thresholds. Fields: "
            "min_licks_total, min_licks_per_side, "
            "min_trials_with_licks_per_side."
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

    # Q-lock 12a: load session filter (configs/defaults.yaml or CLI override).
    filter_spec = load_filter_spec_from_defaults(defaults)
    if args.session_filter_config is not None:
        import yaml as _yaml
        with open(args.session_filter_config) as f:
            user_block = _yaml.safe_load(f) or {}
        filter_spec = SessionFilter(
            min_licks_total=user_block.get("min_licks_total"),
            min_licks_per_side=user_block.get("min_licks_per_side"),
            min_trials_with_licks_per_side=user_block.get(
                "min_trials_with_licks_per_side",
            ),
        )
    if filter_spec.is_pass_through():
        logger.info("Session filter: pass-through (no thresholds active).")
    else:
        logger.info(
            "Session filter active: min_licks_total=%s, "
            "min_licks_per_side=%s, min_trials_with_licks_per_side=%s.",
            filter_spec.min_licks_total,
            filter_spec.min_licks_per_side,
            filter_spec.min_trials_with_licks_per_side,
        )

    all_records: list[dict] = []
    all_w2_records: list[dict] = []
    all_per_session_w2: list[dict] = []
    all_audit_rows: list[dict[str, object]] = []
    for animal in animals:
        animal_t0 = time.perf_counter()
        records, w2_records, per_session_w2, audit_rows = compute_per_animal_records(
            animal=animal, resolver=resolver,
            defaults=defaults, animals_map=animals_map, logger=logger,
            filter_spec=filter_spec,
        )
        animal_elapsed = time.perf_counter() - animal_t0
        all_records.extend(records)
        all_w2_records.extend(w2_records)
        all_per_session_w2.extend(per_session_w2)
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

    # Stage 5d: figure emit (heatmaps)
    logger.info("Emitting 4 SVG heatmap figures (2 bodyparts x 2 sides)...")
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
        "  heatmap figures OK=%d SKIP=%d FAIL=%d",
        len(figs_result["OK"]), len(figs_result["SKIP"]),
        len(figs_result["FAIL"]),
    )

    # Stage 5d2 (Q-lock 12a Addendum #6): per-session W-2 boxplots.
    import pandas as _pd
    per_session_w2_df = _pd.DataFrame(
        all_per_session_w2,
        columns=[
            "animal", "date", "side", "bodypart", "epoch_label",
            "recovery_phenotype", "w2",
        ],
    )
    logger.info(
        "Per-session W-2 records: %d", len(per_session_w2_df),
    )

    if args.output_dir is not None:
        w2_out_dir = args.output_dir
    elif args.remap_phenotypes == "3tier":
        w2_out_dir = resolver.pipeline_outputs(
            subdir=f"{W2_FIGURE_SUBDIR}/{FIGURE_SUBDIR_3TIER_SUFFIX}",
        )
    else:
        w2_out_dir = None  # let renderer default to W2_FIGURE_SUBDIR

    logger.info(
        "Emitting 4 SVG W-2 boxplot figures (2 bodyparts x 2 sides)...",
    )
    # Q-lock 12a: pass remapped phenotype labels into the boxplot DataFrame
    # so 3-tier emit pools (mod-severe → moderate). The animals_map was
    # already remapped earlier; per_session_w2_df["recovery_phenotype"]
    # was set from animal_info.recovery_phenotype at emit time, which
    # for 3-tier reflects the remap.
    w2_figs_result = emit_phenotype_wasserstein_recovery_boxplot_figures(
        per_session_w2_df,
        resolver=resolver,
        output_dir=w2_out_dir,
        overwrite=args.overwrite,
        phenotype_order=phenotype_order,
    )
    logger.info(
        "  W-2 boxplot figures OK=%d SKIP=%d FAIL=%d",
        len(w2_figs_result["OK"]), len(w2_figs_result["SKIP"]),
        len(w2_figs_result["FAIL"]),
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
            "n_sessions", "n_trials", "n_total_frames", "abs_d_p99", "w2",
            "error",
        ],
    ).to_csv(audit_csv, index=False)
    logger.info("Wrote per-animal audit manifest: %s", audit_csv)

    # Q-lock 12a: per-session W-2 long-form CSV (one row per
    # (animal, date, side, bp, epoch_label) with the scalar W-2 used in
    # the boxplot).
    per_session_csv = out_dir / "q12a_per_session_w2.csv"
    per_session_w2_df.to_csv(per_session_csv, index=False)
    logger.info("Wrote per-session W-2 CSV: %s", per_session_csv)

    total_elapsed = time.perf_counter() - overall_t0
    logger.info("=" * 72)
    logger.info(
        "Stage 5 cohort emit complete in %.1fs (n_animals=%d, "
        "n_records=%d, shared_vmax=%.5f)",
        total_elapsed, len(animals), len(all_records), shared_vmax,
    )
    logger.info("=" * 72)

    # Exit nonzero on any FAIL — either compute or render (heatmap or W-2).
    fails = [r for r in all_audit_rows if r["status"] == "FAIL"]
    if fails or figs_result["FAIL"] or w2_figs_result["FAIL"]:
        logger.error(
            "%d compute FAIL(s), %d heatmap render FAIL(s), "
            "%d W-2 render FAIL(s) — see manifests.",
            len(fails), len(figs_result["FAIL"]),
            len(w2_figs_result["FAIL"]),
        )
        for r in fails[:5]:
            logger.error(
                "  compute %s/%s/%s/%s — %s",
                r["animal"], r["bodypart"], r["side"], r["epoch"], r["error"],
            )
        for key, err in figs_result["FAIL"][:5]:
            logger.error("  heatmap render %s — %s", key, err)
        for key, err in w2_figs_result["FAIL"][:5]:
            logger.error("  W-2 render %s — %s", key, err)
        return 1

    # Final JSON summary on stdout for downstream parsing.
    print(json.dumps({
        "n_animals": len(animals),
        "n_records": len(all_records),
        "n_pooled": len(pooled),
        "n_per_session_w2": len(per_session_w2_df),
        "shared_vmax": float(shared_vmax),
        "wall_time_s": float(total_elapsed),
        "heatmap_figures_ok": [list(k) for k in figs_result["OK"]],
        "heatmap_figures_skip": [list(k) for k in figs_result["SKIP"]],
        "w2_figures_ok": [list(k) for k in w2_figs_result["OK"]],
        "w2_figures_skip": [list(k) for k in w2_figs_result["SKIP"]],
        "heatmap_manifest_csv": str(figs_result["manifest_csv"]),
        "w2_manifest_csv": str(w2_figs_result["manifest_csv"]),
        "audit_csv": str(audit_csv),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
