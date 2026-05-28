"""Phase 9.1 Q-lock 13 Stage 4 — cohort emit driver.

Walks the 8-animal cohort (PS46/47/48/49/50/51/54/55) × every on-disk
DLC session, builds the in-memory ``TongueVisualBundle`` per session,
extracts centered-on-first-lick phase rows (Q-lock 13b substrate
extended with ``x_centered``), pools across the cohort, and renders
the 8 trajectory mean+SEM figures (Stage 3).

**Read-only on upstream artifacts.** Per Q-lock 13 kickoff Stage 5:
this driver writes ONLY the 8 SVG figures + a manifest CSV + the
phenotype-pooled CSV under
``stats/figures/phenotype_pooled/phase_aligned_trajectories/``. It
does NOT modify ``per_trial/tongue/*.json``,
``cleaned_traces/tongue/*.parquet``, or ``lick_events/tongue/*.parquet``
— Stage 5 byte-equivalence verification confirms this.

Confirm-once-then-force overwrite pattern matches Q-lock 13b's
``emit_cohort.py``. Default ``--overwrite=skip`` is safe and re-emits
nothing if all 8 figures already exist; pass ``--overwrite=force`` for
a clean cohort emit.

Usage::

    # Pilot — PS46 only (~31 sessions, ~5-10 min wall-time).
    python scripts/phase_9_1_q13/emit_cohort.py \\
        --animals PS46 --overwrite force

    # Full 8-animal cohort (~250 sessions, ~30-60 min wall-time).
    python scripts/phase_9_1_q13/emit_cohort.py \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 --overwrite force
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import logging
import re
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import AnimalInfo, load_animals  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    build_first_lick_centered_phase_rows,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.figures.phase_aligned_trajectories import (  # noqa: E402
    FIGURE_SUBDIR,
    compute_trajectory_wilcoxon_stats,
    emit_phase_aligned_trajectory_figures,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    aggregate_phenotype_pooled_phase_bin_mean_sem,
    apply_phase_bin_baseline_delta,
    compute_per_animal_phase_bin_baseline,
    compute_per_animal_trajectory_scalar,
    densify_phase_rows_via_interp,
    enumerate_session_dates,
)
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402


COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")


# Q-lock 13.4 — phenotype remap modes (mirrors Q-lock 12 Addendum #4).
# "none": canonical 4-tier per F-P-1.
# "3tier": merge moderate-severe into moderate → 3-tier
#          (mild, moderate, severe). PS51 (sole moderate-severe) pools
#          with PS46 (moderate) for n=2 in the merged tier.
PHENOTYPE_REMAP_3TIER: dict[str, str] = {
    "moderate-severe": "moderate",
}
PHENOTYPE_ORDER_3TIER: tuple[str, ...] = ("mild", "moderate", "severe")


def remap_animals_to_3tier(
    animals_map: dict[str, "AnimalInfo"],
) -> dict[str, "AnimalInfo"]:
    """Return a copy of ``animals_map`` with phenotypes remapped per
    :data:`PHENOTYPE_REMAP_3TIER`.

    Uses :func:`dataclasses.replace` so ``AnimalInfo``'s immutability
    is preserved; the original map is not mutated.
    """
    out: dict[str, AnimalInfo] = {}
    for k, info in animals_map.items():
        phen = info.recovery_phenotype
        new_phen = PHENOTYPE_REMAP_3TIER.get(phen, phen) if phen else phen
        if new_phen != phen:
            out[k] = dataclasses.replace(info, recovery_phenotype=new_phen)
        else:
            out[k] = info
    return out


# ---------------------------------------------------------------------------
# Per-session phase-rows compute (read-only on upstream)
# ---------------------------------------------------------------------------


def build_session_phase_rows(
    *,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, float, str]:
    """Build centered phase rows for one (animal, date).

    Returns
    -------
    (rows, wall_time_s, status)
        ``rows`` has the substrate columns plus ``animal`` + ``date``
        added for downstream join. Empty when the bundle yields no
        phase rows (no detected first-lick peaks, no finite synthetic
        ILI, or trial-events list empty).
        ``status`` ∈ {"OK", "SKIP_NO_ILI", "SKIP_EMPTY", "FAIL: ..."}.
    """
    t0 = time.perf_counter()
    try:
        bundle = build_tongue_visual_bundle_by_animal_date(
            animal=animal, date=date, resolver=resolver,
        )
        synth = float(bundle.metadata.get(
            "pre_stroke_median_ili_ms", float("nan"),
        ))
        if not (np.isfinite(synth) and synth > 0):
            return (
                pd.DataFrame(),
                time.perf_counter() - t0,
                "SKIP_NO_ILI",
            )
        rows = build_first_lick_centered_phase_rows(
            bundle,
            synthetic_ili_ms=synth,
            ili_source="synthetic_only",
        )
        if rows.empty:
            return (
                pd.DataFrame(),
                time.perf_counter() - t0,
                "SKIP_EMPTY",
            )
        rows = rows.copy()
        rows["animal"] = animal
        rows["date"] = date
        return (rows, time.perf_counter() - t0, "OK")
    except Exception as exc:  # pragma: no cover — surfaces in manifest
        logger.exception(
            "phase-rows build FAILED for %s/%s: %s",
            animal, date.isoformat(), exc,
        )
        return (
            pd.DataFrame(),
            time.perf_counter() - t0,
            f"FAIL: {type(exc).__name__}",
        )


def walk_cohort(
    *,
    animals: list[str],
    resolver: PathResolver,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """For each (animal, date), build phase rows. Returns cohort df + manifest."""
    cohort_frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, object]] = []
    for animal in animals:
        dates = enumerate_session_dates(animal, resolver)
        logger.info("[%s] walking %d session(s)", animal, len(dates))
        for d in dates:
            df, elapsed, status = build_session_phase_rows(
                animal=animal, date=d, resolver=resolver, logger=logger,
            )
            if not df.empty:
                cohort_frames.append(df)
            manifest_rows.append({
                "animal": animal,
                "date": d.isoformat(),
                "status": status,
                "wall_time_s": elapsed,
                "n_rows": len(df),
            })
            logger.info(
                "  [%s/%s] %s in %.2fs (n_rows=%d)",
                animal, d.isoformat(), status, elapsed, len(df),
            )
    if cohort_frames:
        cohort_df = pd.concat(cohort_frames, ignore_index=True)
    else:
        cohort_df = pd.DataFrame()
    return cohort_df, manifest_rows


# ---------------------------------------------------------------------------
# Session-level phenotype + epoch attach (vectorized via merge)
# ---------------------------------------------------------------------------


def build_session_epoch_table(
    cohort_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
) -> pd.DataFrame:
    """One row per distinct (animal, date) with phenotype + epoch_label.

    Vectorized alternative to ``attach_phenotype_and_epoch``'s per-row
    iteration — phase-row DataFrames are ~10x bigger than per-session
    scalar DataFrames so the iteration cost is non-trivial. We compute
    the epoch lookup once per session and merge it onto the phase-row
    DataFrame.
    """
    if cohort_df.empty:
        return pd.DataFrame(columns=[
            "animal", "date", "recovery_phenotype", "rel_day", "epoch_label",
        ])
    sessions = (
        cohort_df[["animal", "date"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    rows: list[dict[str, object]] = []
    for _, row in sessions.iterrows():
        animal_id = str(row["animal"])
        info = animals_map.get(animal_id)
        if info is None or info.recovery_phenotype is None:
            continue
        d = row["date"]
        rel_day = (d - info.stroke_date).days
        epoch = assign_epoch_label(rel_day, info)
        rows.append({
            "animal": animal_id,
            "date": d,
            "recovery_phenotype": info.recovery_phenotype,
            "rel_day": int(rel_day),
            "epoch_label": epoch,
        })
    return pd.DataFrame(rows)


def attach_metadata(
    cohort_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
) -> pd.DataFrame:
    """Inner-merge phenotype + epoch onto cohort_df.

    Rows for animals missing from ``animals_map`` (or with no
    recovery_phenotype) are dropped via the inner join.
    """
    if cohort_df.empty:
        return cohort_df
    session_table = build_session_epoch_table(cohort_df, animals_map)
    if session_table.empty:
        return cohort_df.iloc[0:0]
    return cohort_df.merge(
        session_table, on=["animal", "date"], how="inner",
    )


# ---------------------------------------------------------------------------
# Stage 4 wrapper — Stage 1 baseline + Stage 1 delta + Stage 2 + emit
# ---------------------------------------------------------------------------


def run_stats_and_figures(
    cohort_df: pd.DataFrame,
    *,
    resolver: PathResolver,
    overwrite: str,
    output_dir: Path | None,
    logger: logging.Logger,
    animals_map: dict[str, AnimalInfo] | None = None,
    phenotype_order: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Run Stages 1→2→3 on the cohort phase-row DataFrame.

    Returns a dict with paths to produced artifacts + figure-emit result.
    """
    if cohort_df.empty:
        logger.error("walk_cohort returned 0 rows; skipping stats + figures")
        return {"status": "no_rows"}

    # Q-lock 13.2: per-trial linear interp at bin centers. Removes
    # cross-animal-pool jaggedness caused by per-animal ILI mismatch
    # under the frame-grained substrate.
    logger.info(
        "Stage 0.5: densify phase rows via per-trial linear interp "
        "(removes ILI-lattice jaggedness)...",
    )
    n_rows_before = len(cohort_df)
    cohort_df = densify_phase_rows_via_interp(cohort_df)
    logger.info(
        "  densified rows: %d (was %d frame-grained)",
        len(cohort_df), n_rows_before,
    )

    logger.info("Stage 1: per-animal phase-bin baseline (epoch_label=pre)...")
    baseline = compute_per_animal_phase_bin_baseline(cohort_df)
    logger.info(
        "  baseline rows: %d (n animals × phase_bins × signals)",
        len(baseline),
    )

    logger.info("Stage 1: apply delta = signal - per-animal-baseline...")
    cohort_with_delta = apply_phase_bin_baseline_delta(cohort_df, baseline)

    logger.info("Stage 2: phenotype-pooled phase-bin mean + SEM...")
    pooled = aggregate_phenotype_pooled_phase_bin_mean_sem(
        cohort_with_delta, by_side=True,
    )
    logger.info("  pooled rows: %d", len(pooled))

    logger.info("Stage 3: emit 8 trajectory figures...")
    figure_kwargs: dict = {
        "resolver": resolver,
        "output_dir": output_dir,
        "overwrite": "force" if overwrite == "force" else "prompt",
    }
    if phenotype_order is not None:
        figure_kwargs["phenotype_order"] = phenotype_order
    figure_result = emit_phase_aligned_trajectory_figures(
        pooled, **figure_kwargs,
    )
    logger.info(
        "  figures emitted=%d skipped=%d",
        len(figure_result["emitted"]),
        len(figure_result["skipped"]),
    )

    out_dir = (
        output_dir if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    pooled_csv = out_dir / "phenotype_pooled_phase_bin_mean_sem.csv"
    pooled.to_csv(pooled_csv, index=False)
    logger.info("Wrote phenotype-pooled summary CSV: %s", pooled_csv)

    baseline_csv = out_dir / "per_animal_phase_bin_baseline.csv"
    baseline.to_csv(baseline_csv, index=False)
    logger.info("Wrote per-animal baseline CSV: %s", baseline_csv)

    # Stage 6.1 — per-animal trajectory scalar + paired Wilcoxon family.
    logger.info(
        "Stage 6.1: per-animal trajectory scalar (raw signal, by epoch)...",
    )
    scalar_df = compute_per_animal_trajectory_scalar(cohort_df)
    logger.info("  per-animal scalar rows: %d", len(scalar_df))
    scalar_csv = out_dir / "per_animal_trajectory_scalar.csv"
    scalar_df.to_csv(scalar_csv, index=False)
    logger.info("Wrote per-animal trajectory scalar CSV: %s", scalar_csv)

    logger.info(
        "Stage 6.1: paired Wilcoxon × BH-FDR — "
        "48-test family (4 phen × 2 sides × 2 signals × 3 post epochs)...",
    )
    if animals_map is None:
        animals_map = load_animals()
    wilcoxon_df = compute_trajectory_wilcoxon_stats(scalar_df, animals_map)
    logger.info("  Wilcoxon rows: %d", len(wilcoxon_df))
    wilcoxon_csv = out_dir / "trajectory_paired_wilcoxon_bh_fdr.csv"
    wilcoxon_df.to_csv(wilcoxon_csv, index=False)
    logger.info("Wrote trajectory Wilcoxon stats CSV: %s", wilcoxon_csv)
    n_reject = int(wilcoxon_df["reject"].fillna(False).sum())
    n_finite = int(wilcoxon_df["p_value"].notna().sum())
    logger.info(
        "  Wilcoxon family summary: %d/%d significant at α=0.05 BH-FDR",
        n_reject, n_finite,
    )

    return {
        "status": "ok",
        "cohort_rows": len(cohort_df),
        "baseline_rows": len(baseline),
        "pooled_rows": len(pooled),
        "scalar_rows": len(scalar_df),
        "wilcoxon_rows": len(wilcoxon_df),
        "wilcoxon_n_reject": n_reject,
        "pooled_csv": pooled_csv,
        "baseline_csv": baseline_csv,
        "scalar_csv": scalar_csv,
        "wilcoxon_csv": wilcoxon_csv,
        "figures_emitted": [str(p) for p in figure_result["emitted"]],
        "figures_skipped": [str(p) for p in figure_result["skipped"]],
    }


# ---------------------------------------------------------------------------
# Driver — argparse + scope summary + main
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
    """Pre-flight summary — animal × session counts.

    Does NOT actually load bundles or write anything; just reads
    on-disk per-trial JSON inventory via :func:`enumerate_session_dates`.
    """
    logger.info("=" * 72)
    logger.info("Phase 9.1 Q-lock 13 Stage 4 cohort emit — scope summary")
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
    logger.info("Total sessions to walk: %d", total)
    logger.info(
        "Outputs will land under: pipeline_outputs/%s/", FIGURE_SUBDIR,
    )
    logger.info("=" * 72)
    return per_animal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 9.1 Q-lock 13 Stage 4 cohort emit driver.",
    )
    parser.add_argument(
        "--animals",
        type=parse_animals,
        default=list(COHORT_8),
        help=(
            "Comma-separated animal IDs (default: 8-animal Q-lock 13 cohort). "
            "Example: --animals PS46 for the Stage 5 pilot."
        ),
    )
    parser.add_argument(
        "--overwrite",
        choices=("skip", "force", "prompt"),
        default="skip",
        help=(
            "skip (default): existing SVGs left as-is. "
            "force: overwrite without prompt — pass for Stage 5 cohort emit. "
            "prompt: confirm-once on first existing target."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Optional override for the figure / CSV output dir "
            "(default: pipeline_outputs/<Q-lock 15 subdir>)."
        ),
    )
    parser.add_argument(
        "--remap-phenotypes",
        choices=("none", "3tier"),
        default="none",
        help=(
            "Phenotype-tier mapping mode. 'none' (default): canonical "
            "4-tier per F-P-1. '3tier': merge moderate-severe → "
            "moderate (Q-lock 12 Addendum #4 precedent). Output dir "
            "auto-routed to '<FIGURE_SUBDIR>/3_phenotype/' in 3tier "
            "mode."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("phase_9_1_q13.emit_cohort")

    resolver = PathResolver()
    animals = args.animals
    if isinstance(animals, str):
        animals = parse_animals(animals)

    overall_t0 = time.perf_counter()
    print_scope_summary(
        animals=animals, resolver=resolver,
        overwrite=args.overwrite, logger=logger,
    )

    cohort_df, manifest_rows = walk_cohort(
        animals=animals, resolver=resolver, logger=logger,
    )

    # Per-animal wall-time + status summary.
    wt_by_animal: dict[str, float] = {}
    status_counts: dict[str, int] = {}
    for r in manifest_rows:
        wt_by_animal[str(r["animal"])] = (
            wt_by_animal.get(str(r["animal"]), 0.0)
            + float(r["wall_time_s"])
        )
        status = str(r["status"]).split(":", 1)[0]
        status_counts[status] = status_counts.get(status, 0) + 1
    logger.info("Per-animal walk wall-time:")
    for animal, wt in wt_by_animal.items():
        n = sum(1 for r in manifest_rows if r["animal"] == animal)
        logger.info(
            "  %s: %.1fs across %d sessions (%.2fs/session avg)",
            animal, wt, n, wt / max(1, n),
        )
    logger.info(
        "Status counts: %s", json.dumps(status_counts),
    )

    # Walk manifest lands in the canonical 4-tier dir (sessions walked
    # are identical across remap modes — no point duplicating).
    walk_manifest_dir = (
        args.output_dir if args.output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    walk_manifest_dir.mkdir(parents=True, exist_ok=True)
    if manifest_rows:
        walk_manifest_csv = walk_manifest_dir / "stage4_walk_manifest.csv"
        pd.DataFrame(manifest_rows).to_csv(walk_manifest_csv, index=False)
        logger.info("Wrote walk manifest CSV: %s", walk_manifest_csv)

    # Attach phenotype + epoch — applies phenotype remap when requested
    # so downstream Stage 1 baseline + Stage 2 aggregator + Stage 6.1
    # Wilcoxon all see the remapped tier (mod-severe → moderate).
    if not cohort_df.empty:
        logger.info(
            "Attaching phenotype + epoch on %d cohort rows...",
            len(cohort_df),
        )
        animals_map = {
            a: info
            for a, info in load_animals().items()
            if a in animals
        }
        if args.remap_phenotypes == "3tier":
            logger.info(
                "Phenotype remap = 3tier (mod-severe → moderate). "
                "Output subdir: %s/3_phenotype/", FIGURE_SUBDIR,
            )
            animals_map = remap_animals_to_3tier(animals_map)
            phenotype_order = PHENOTYPE_ORDER_3TIER
            # Auto-route output to a 3_phenotype subdir (only when
            # user didn't pass an explicit --output-dir).
            output_dir = args.output_dir
            if output_dir is None:
                output_dir = (
                    resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
                    / "3_phenotype"
                )
        else:
            phenotype_order = None
            output_dir = args.output_dir
        cohort_df = attach_metadata(cohort_df, animals_map)
        logger.info(
            "  cohort rows after phenotype/epoch attach: %d",
            len(cohort_df),
        )
    else:
        animals_map = None
        phenotype_order = None
        output_dir = args.output_dir

    # Stages 1 → 2 → 3.
    result = run_stats_and_figures(
        cohort_df,
        resolver=resolver,
        overwrite=args.overwrite,
        output_dir=output_dir,
        logger=logger,
        animals_map=animals_map,
        phenotype_order=phenotype_order,
    )
    logger.info(
        "Stats + figures result: %s",
        json.dumps(
            {
                k: v for k, v in result.items()
                if k not in ("figures_emitted", "figures_skipped")
            },
            default=str, indent=2,
        ),
    )

    total_elapsed = time.perf_counter() - overall_t0
    logger.info("=" * 72)
    logger.info(
        "Stage 4 cohort emit complete in %.1fs (%.1f min)",
        total_elapsed, total_elapsed / 60.0,
    )
    logger.info("=" * 72)

    fails = [r for r in manifest_rows if str(r["status"]).startswith("FAIL")]
    if fails:
        logger.error("%d session walk FAILURE(s):", len(fails))
        for r in fails:
            logger.error("  %s/%s — %s", r["animal"], r["date"], r["status"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
