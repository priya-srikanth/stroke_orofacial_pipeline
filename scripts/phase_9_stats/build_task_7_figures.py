"""Phase 9 Task 7 — build per-animal figure family + V1/V2/V3 headline grid.

Output tree:

    pipeline_outputs/stats/figures/
      headlines/<endpoint>/
        v1_per_session_recovery.{svg,png}
        v2_per_bin_recovery.{svg,png}
        v3_per_epoch_boxplot.{svg,png}
      per_animal/<endpoint>/
        recovery_curve.{svg,png}
        paired_diff_distribution_pre_post.{svg,png}
        paired_diff_distribution_ipsi_contra.{svg,png}
      forest_plots/
        forest_<axis>_<comparison>.{svg,png}

Modes:
  --mode headlines  : V1/V2/V3 grid for 7 Addendum #8 headline kinematics
                      (default; smaller scope; ~21 figures)
  --mode confirmatory: all confirmatory endpoints — per_animal/<endpoint>/
                      recovery_curve + paired_diff (~50-80 figures)
  --mode forest     : forest plots per (axis, comparison) — ~7 figures
  --mode all        : all of the above

Run:
  conda run -n stroke_orofacial python scripts/phase_9_stats/build_task_7_figures.py --mode all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.figures import (  # noqa: E402
    load_cohort_parquet,
    load_recovery_lmm_result,
    plot_forest_by_endpoint,
    plot_paired_diff_distribution,
    plot_v1_per_session_recovery,
    plot_v2_per_bin_recovery,
    plot_v3_per_epoch_boxplot,
    save_figure,
    _load_animal_epoch_boundaries,
)


# Figure scope for the filtered_v1 tongue family. EXPANDED to the FULL set of
# 23 filtered tongue scalar endpoints (chore tongue-substrate-v7-routing-fix,
# 2026-05-30, Priya): previously only the 7 Addendum #8 headline kinematics
# got V1/V2/V3 figures, leaving 16 primary tongue scalars stats-only (no
# filtered figure). The substrate fix re-materialized all 23, so all 23 now
# get figures so the corrected cells (incl. the severe/mod-severe acute
# collapse) are visualized cohort-wide. (Kept the HEADLINE_KINEMATICS name
# for call-site stability; it now means "all filtered tongue scalar figures".)
HEADLINE_KINEMATICS: tuple[str, ...] = (
    # lick-1 / lick-2 first-peak scalars
    "tongue_lick1_y_peak",
    "tongue_lick1_t_peak_ms",
    "tongue_lick1_x_at_ypeak",
    "tongue_lick1_angle_at_ypeak",
    "tongue_lick2_y_peak",
    "tongue_lick2_t_peak_ms",
    "tongue_lick2_x_at_ypeak",
    "tongue_lick2_angle_at_ypeak",
    # peak velocity (y-only + 2D), per-lick + first-5 + per-trial median
    "tongue_lick1_vy_peak",
    "tongue_lick1_vxy_peak",
    "tongue_max_vy_peak_first5",
    "tongue_max_vxy_peak_first5",
    "tongue_mean_vxy_peak_first5",
    "tongue_median_vy_peak_per_trial",
    "tongue_median_vxy_peak_per_trial",
    # angle scalars
    "tongue_median_angle_at_peak_velocity",
    "tongue_median_angle_max_signed_per_lick",
    # bout / rate / timing
    "tongue_first_peak_t_ms",
    "tongue_lick_rate_hz",
    "tongue_mean_within_bout_ili_ms",
    # lick-count family (values changed by the n_licks_family routing)
    "tongue_n_licks",
    "tongue_n_left",
    "tongue_n_right",
)


def _close(fig) -> None:
    plt.close(fig)


def _build_headlines(
    figures_root: Path, inputs_root: Path, results_root: Path,
    headline_summary_path: Path, eb_by_animal: dict,
) -> int:
    n = 0
    headline_df = (
        pd.read_csv(headline_summary_path)
        if headline_summary_path.exists() else pd.DataFrame()
    )
    for slug in HEADLINE_KINEMATICS:
        cohort = load_cohort_parquet(slug, inputs_root)
        if cohort.empty:
            print(f"  SKIP {slug} (no cohort parquet)")
            continue
        out_dir = figures_root / "headlines" / slug
        fit_proxy = load_recovery_lmm_result(slug, results_root)
        headline_rows = (
            headline_df[headline_df["endpoint_slug"] == slug]
            if not headline_df.empty else pd.DataFrame()
        )

        fig = plot_v1_per_session_recovery(
            cohort, endpoint_slug=slug, fit_proxy=fit_proxy,
        )
        save_figure(fig, out_dir / "v1_per_session_recovery")
        _close(fig)
        n += 1

        fig = plot_v2_per_bin_recovery(
            cohort, endpoint_slug=slug,
        )
        save_figure(fig, out_dir / "v2_per_bin_recovery")
        _close(fig)
        n += 1

        fig = plot_v3_per_epoch_boxplot(
            cohort, endpoint_slug=slug,
            headline_rows=headline_rows, eb_by_animal=eb_by_animal,
        )
        save_figure(fig, out_dir / "v3_per_epoch_boxplot")
        _close(fig)
        n += 1
        print(f"  OK  {slug}: V1 + V2 + V3 → headlines/{slug}/")
    return n


def _confirmatory_endpoints(headline_summary_path: Path) -> list[str]:
    if not headline_summary_path.exists():
        return []
    df = pd.read_csv(headline_summary_path)
    return sorted(
        df.loc[df["is_confirmatory"].astype(bool), "endpoint_slug"].unique().tolist()
    )


def _build_per_animal(
    figures_root: Path, inputs_root: Path, results_root: Path,
    headline_summary_path: Path,
) -> int:
    n = 0
    slugs = _confirmatory_endpoints(headline_summary_path)
    print(f"  Confirmatory endpoints: {len(slugs)}")
    for slug in slugs:
        cohort = load_cohort_parquet(slug, inputs_root)
        if cohort.empty:
            print(f"  SKIP {slug} (no parquet)")
            continue
        out_dir = figures_root / "per_animal" / slug
        fit_proxy = load_recovery_lmm_result(slug, results_root)

        # Recovery curve — reuse V1-style with cohort overlay.
        fig = plot_v1_per_session_recovery(
            cohort, endpoint_slug=slug, fit_proxy=fit_proxy,
            title=f"{slug} — recovery curve (cohort)",
        )
        save_figure(fig, out_dir / "recovery_curve")
        _close(fig)
        n += 1

        # Paired-diff distributions per axis.
        for axis in ("pre_post", "ipsi_contra"):
            fig = plot_paired_diff_distribution(
                cohort, endpoint_slug=slug, axis=axis,
            )
            save_figure(fig, out_dir / f"paired_diff_distribution_{axis}")
            _close(fig)
            n += 1
        print(f"  OK  {slug}: recovery_curve + 2 paired_diff → per_animal/{slug}/")
    return n


def _build_forest(
    figures_root: Path, headline_summary_path: Path,
) -> int:
    n = 0
    if not headline_summary_path.exists():
        return 0
    df = pd.read_csv(headline_summary_path)
    out_dir = figures_root / "forest_plots"
    # Forest one per (axis, comparison) family that has confirmatory rows.
    pairs = (
        df[df["is_confirmatory"].astype(bool)]
        .groupby(["axis", "comparison"]).size().reset_index()
    )
    for _, row in pairs.iterrows():
        axis, comp = row["axis"], row["comparison"]
        fig = plot_forest_by_endpoint(
            df, axis=axis, comparison=comp,
            title=f"Forest plot — {axis} / {comp}",
        )
        save_figure(fig, out_dir / f"forest_{axis}_{comp}")
        _close(fig)
        n += 1
        print(f"  OK  forest_{axis}_{comp}.{{svg,png}}")
    return n


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--mode", choices=("headlines", "confirmatory", "forest", "all"),
        default="all",
    )
    p.add_argument(
        "--filter-variant", choices=("none", "filtered_v1"), default="none",
        help=(
            "none (default): read/write the unfiltered stats trees. "
            "filtered_v1: read stats/inputs/filtered_v1 + stats/results/filtered_v1 "
            "and write figures to stats/figures/filtered_v1 (alongside unfiltered)."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    resolver = PathResolver()
    variant = None if args.filter_variant == "none" else args.filter_variant
    stats_root = resolver.pipeline_outputs(subdir="stats")
    inputs_root = (stats_root / "inputs" / variant) if variant else (stats_root / "inputs")
    results_root = (stats_root / "results" / variant) if variant else (stats_root / "results")
    figures_root = (stats_root / "figures" / variant) if variant else (stats_root / "figures")
    headline_summary = REPO_ROOT / ".scratch_phase_9" / (
        f"task_5_headline_summary_{variant}.csv" if variant
        else "task_5_headline_summary.csv"
    )
    eb_by_animal = _load_animal_epoch_boundaries()

    print("Phase 9 Task 7 — figure build")
    print(f"  inputs_root:  {inputs_root}")
    print(f"  results_root: {results_root}")
    print(f"  figures_root: {figures_root}")
    print(f"  headline csv: {headline_summary.name}")
    print(f"  mode:         {args.mode}")
    print()

    total = 0
    if args.mode in ("headlines", "all"):
        print("=== Headlines (V1/V2/V3 for 7 kinematic endpoints) ===")
        total += _build_headlines(
            figures_root, inputs_root, results_root,
            headline_summary, eb_by_animal,
        )
    if args.mode in ("confirmatory", "all"):
        print("=== Per-animal (recovery_curve + paired_diff per confirmatory) ===")
        total += _build_per_animal(
            figures_root, inputs_root, results_root, headline_summary,
        )
    if args.mode in ("forest", "all"):
        print("=== Forest plots (per axis × comparison) ===")
        total += _build_forest(figures_root, headline_summary)

    print()
    print(f"Total figures written: {total} (each as SVG + PNG = {total * 2} files)")
    print(f"Output root: {figures_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
