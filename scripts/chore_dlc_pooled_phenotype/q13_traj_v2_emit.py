"""Q13/Q13c v2 re-emit — phase-aligned trajectories, filtered + ipsi/contra.

Chore ``vChore-dlc-pooled-phenotype-unification`` Stage 3.

v2 vs the shipped (no_filter) trajectory figures:

1. **On-the-fly DLC filtering** of the phase rows (trajectory signals are NOT
   in the materialized ``filtered_v1`` tree — same situation as Q13b):
   - ``DlcTrialFilter`` (phase-aligned-trajectory family) joined per-trial on
     (animal, date, side, trial_index) via ``build_dlc_pertrial_lick_frame``;
   - ``DlcSessionFilter`` (``min_trials_with_detected_lick``) drops sparse
     (animal, date, side) sessions.
2. **Ipsi/contra coding** — on the current **all-L cohort** this is a pure
   relabel (ipsi = mouse-L, contra = mouse-R): pooling by rig-side is
   identical to ipsi/contra pooling, and the signed-metric sign-flip is the
   identity. So v2 keeps the existing L/R pooling machinery unchanged and only
   relabels the panel side label + subtitle. **Forward-caveat:** when a
   right-stroke animal joins the cohort, this must switch to a true ipsi/contra
   recode (relabel the ``side`` column + sign-flip ``angle_deg``/``x_centered``
   per ``stroke_laterality``, ``y_centered`` symmetric) and pool on that — which
   requires parametrizing the 6 trajectory stats families' side iteration.
3. **Convention unchanged**: continuous phase-bin mean +/- SEM band curves
   (Priya 2026-05-29 — the line+jitter dot convention is for discrete-epoch
   figures only). Full v2 = figures (SEM + SD) + all 6 stats families.

Output: ``stats/figures/phenotype_pooled/phase_aligned_trajectories/<scope>/v2/``
(figures) + ``stats/results/.../<scope>/v2/`` (CSVs). ``<scope>`` ∈ {4_tier,
3_tier}.

Usage::

    # PS46 pilot, 4-tier (~5-10 min bundle rebuild).
    python -m scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit \\
        --animals PS46 --overwrite force --remap-phenotypes none

    # Full cohort, both scopes (~30-60 min).
    python -m scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit \\
        --animals PS46,PS47,PS48,PS49,PS50,PS51,PS54,PS55 \\
        --overwrite force --remap-phenotypes both
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.cohort_filters import (  # noqa: E402
    DLC_SESSION_N_KEPT_LICKS_COL,
    DLC_SESSION_N_TRIALS_TOTAL_COL,
    DLC_SESSION_N_TRIALS_WITH_LICK_COL,
    DLC_TRIAL_N_LICKS_COL,
    DlcSessionFilter,
    build_dlc_pertrial_lick_frame,
    compute_dlc_session_lick_stats,
    load_dlc_filter_spec_from_defaults,
    resolve_dlc_trial_filter,
)
from stroke_orofacial.figures.phase_aligned_trajectories import (  # noqa: E402
    FIGURE_SUBDIR,
    RESULTS_SUBDIR,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.aggregators import enumerate_session_dates  # noqa: E402

# Reuse the shipped Q13 machinery (heavy bundle walk + the full stats/figure
# pipeline) verbatim — v2 only changes the inputs (filtered) + the output
# paths + the figure subtitle/side labels.
from scripts.phase_9_1_q13.emit_cohort import (  # noqa: E402
    PHENOTYPE_ORDER_3TIER,
    attach_metadata,
    parse_animals,
    remap_animals_to_3tier,
    run_stats_and_figures,
    walk_cohort,
)

logger = logging.getLogger("chore.q13_traj_v2_emit")

COHORT_8 = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

V2_TRAJ_SUBTITLE = (
    "Source: filtered_v1 (on-the-fly DlcSession+TrialFilter) + ipsi/contra "
    "coding; mean ± SEM session-pooled "
    "(chore vChore-dlc-pooled-phenotype-unification)"
)
# v3 substrate-version marker (chore tongue-substrate-v7-routing-fix,
# 2026-05-30). Same methodology as v2 — the ONLY change is the data source:
# the phase-aligned substrate now reads the v7-cleaned trace, not the
# pre-clean interpolated trace. Marker is required for downstream audit.
V3_TRAJ_SUBTITLE = (
    "Source: filtered_v1 (substrate v3 — v7-cleaned-trace routing fix per "
    "chore vChore-tongue-substrate-v7-routing-fix); mean ± SEM session-pooled"
)
TRAJ_SUBTITLE_BY_VERSION = {"v2": V2_TRAJ_SUBTITLE, "v3": V3_TRAJ_SUBTITLE}
# All-L cohort: ipsi = mouse-L, contra = mouse-R.
SIDE_DISPLAY = {"L": "Ipsi (mouse-L)", "R": "Contra (mouse-R)"}


def filter_phase_rows(
    cohort_df: pd.DataFrame,
    *,
    animals: list[str],
    resolver: PathResolver,
    defaults: dict,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply DlcTrialFilter + DlcSessionFilter to the phase-row DataFrame.

    Returns ``(filtered_df, report)``. Trial filter drops phase rows whose
    (animal, date, side, trial_index) has < ``min_licks_per_trial`` detected
    licks; session filter drops all rows of sparse (animal, date, side)
    sessions.
    """
    n_in = len(cohort_df)
    trial_filter = resolve_dlc_trial_filter("dlc_tongue_trajectory_metrics", defaults)
    session_filter: DlcSessionFilter = load_dlc_filter_spec_from_defaults(defaults)
    logger.info(
        "TrialFilter min_licks_per_trial=%s; SessionFilter "
        "min_trials_with_detected_lick=%s",
        trial_filter.min_licks_per_trial,
        session_filter.min_trials_with_detected_lick,
    )

    df = cohort_df
    # Trial-level filter: join per-trial lick counts, drop sub-threshold trials.
    if not trial_filter.is_pass_through():
        lick_frames = []
        for animal in animals:
            for d in enumerate_session_dates(animal, resolver):
                lf = build_dlc_pertrial_lick_frame(animal, d, resolver)
                if lf is not None:
                    lick_frames.append(lf)
        if lick_frames:
            licks = pd.concat(lick_frames, ignore_index=True)
            df = df.merge(
                licks[["animal", "date", "side", "trial_index",
                       DLC_TRIAL_N_LICKS_COL]],
                on=["animal", "date", "side", "trial_index"], how="left",
            )
            keep = (
                df[DLC_TRIAL_N_LICKS_COL].isna()
                | (df[DLC_TRIAL_N_LICKS_COL] >= trial_filter.min_licks_per_trial)
            )
            df = df[keep].drop(columns=[DLC_TRIAL_N_LICKS_COL]).copy()
    n_after_trial = len(df)

    # Session-level filter: drop sparse (animal, date, side) sessions.
    n_sess_in = n_sess_kept = 0
    if not session_filter.is_pass_through():
        sess_rows = []
        for animal in animals:
            for d in enumerate_session_dates(animal, resolver):
                stats = compute_dlc_session_lick_stats(animal, d, resolver)
                if stats is None:
                    continue
                for s in stats:
                    sess_rows.append({
                        "animal": s.animal, "date": s.date, "side": s.side,
                        DLC_SESSION_N_TRIALS_TOTAL_COL: s.n_trials_of_side,
                        DLC_SESSION_N_TRIALS_WITH_LICK_COL:
                            s.n_trials_with_detected_lick,
                        DLC_SESSION_N_KEPT_LICKS_COL: s.n_kept_licks,
                    })
        if sess_rows:
            sess_df = pd.DataFrame(sess_rows)
            kept_sess, result = session_filter.filter(sess_df)
            n_sess_in, n_sess_kept = result.n_sessions_in, result.n_sessions_kept
            kept_keys = {
                (r["animal"], r["date"], r["side"])
                for _, r in kept_sess.iterrows()
            }
            df = df[
                df.apply(
                    lambda r: (r["animal"], r["date"], r["side"]) in kept_keys,
                    axis=1,
                )
            ].copy()

    return df, {
        "rows_in": n_in, "rows_after_trial": n_after_trial,
        "rows_out": len(df), "sessions_in": n_sess_in,
        "sessions_kept": n_sess_kept,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animals", type=parse_animals, default=list(COHORT_8))
    parser.add_argument(
        "--overwrite", choices=("skip", "force", "prompt"), default="force",
    )
    parser.add_argument(
        "--remap-phenotypes", choices=("none", "3tier", "both"), default="none",
    )
    parser.add_argument(
        "--out-version", choices=("v2", "v3"), default="v3",
        help="Output subdir + subtitle marker. v3 (default) = the "
             "v7-cleaned-trace substrate fix; v2 = the pre-fix audit copy "
             "(retained, not overwritten by a v3 run).",
    )
    parser.add_argument(
        "--lick-set", choices=("first_lick", "all_multi"), default="first_lick",
        help="Which lick peaks center the phase rows. 'first_lick' (default) "
             "= each trial's first lick (the shipped pooled trajectory). "
             "'all_multi' = EVERY detected lick peak across all bouts; routes "
             "to the sibling 'phase_aligned_trajectories_all_licks/' family.",
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    )

    resolver = PathResolver()
    from stroke_orofacial.config_loader import load_defaults
    defaults = load_defaults()
    animals = args.animals
    animals_map_full = {a: i for a, i in load_animals().items() if a in animals}

    logger.info("=" * 72)
    logger.info("Q13/Q13c trajectory v2 re-emit — animals=%s remap=%s",
                ",".join(animals), args.remap_phenotypes)
    logger.info("=" * 72)

    # Heavy step: walk the cohort once (bundle rebuild -> phase rows).
    cohort_df, _manifest = walk_cohort(
        animals=animals, resolver=resolver, logger=logger,
        lick_set=args.lick_set,
    )
    if cohort_df.empty:
        logger.error("walk_cohort returned 0 rows; aborting.")
        return 1

    # Filter once (scope-independent).
    cohort_df, report = filter_phase_rows(
        cohort_df, animals=animals, resolver=resolver, defaults=defaults,
    )
    logger.info(
        "Filter: rows %d->%d (trial->%d); sessions %d->%d",
        report["rows_in"], report["rows_out"], report["rows_after_trial"],
        report["sessions_in"], report["sessions_kept"],
    )
    if cohort_df.empty:
        logger.error("No phase rows after filtering; aborting.")
        return 1

    scopes: list[tuple[str, tuple[str, ...] | None, dict]] = []
    if args.remap_phenotypes in ("none", "both"):
        scopes.append(("4_tier", None, animals_map_full))
    if args.remap_phenotypes in ("3tier", "both"):
        scopes.append(("3_tier", PHENOTYPE_ORDER_3TIER,
                       remap_animals_to_3tier(animals_map_full)))

    # all_multi routes to a sibling family so it never collides with the
    # shipped first-lick pooled trajectory (F, Priya 2026-06-01).
    _suffix = "_all_licks" if args.lick_set == "all_multi" else ""
    fig_root = resolver.pipeline_outputs(subdir=FIGURE_SUBDIR + _suffix)
    res_root = resolver.pipeline_outputs(subdir=RESULTS_SUBDIR + _suffix)
    for scope, phenotype_order, amap in scopes:
        out_dir = fig_root / scope / args.out_version
        res_dir = res_root / scope / args.out_version
        logger.info("[%s] attach metadata + run stats/figures (%s) -> %s",
                    scope, args.out_version, out_dir)
        scoped = attach_metadata(cohort_df, amap)
        result = run_stats_and_figures(
            scoped,
            resolver=resolver, overwrite=args.overwrite,
            output_dir=out_dir, results_dir=res_dir, logger=logger,
            animals_map=amap, phenotype_order=phenotype_order,
            figure_subtitle_override=TRAJ_SUBTITLE_BY_VERSION[args.out_version],
            figure_side_display=SIDE_DISPLAY,
        )
        logger.info(
            "[%s] status=%s figs=%d", scope, result.get("status"),
            len(result.get("figures_emitted", [])),
        )

    logger.info("Q13/Q13c trajectory v2 re-emit complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
