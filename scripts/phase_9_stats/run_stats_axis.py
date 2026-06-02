"""Phase 9 Task 4 driver — per-axis hypothesis testing across cohort endpoints.

Reads ``endpoint_inventory.csv`` to enumerate endpoints + their
(value_type, comparison_axes_in_scope, is_confirmatory) attributes,
then for each (endpoint, axis, granularity) tuple in scope:

1. Loads the materialized parquet from ``stats/inputs/<slug>/``
   (concatenated across all 8 cohort animals).
2. Dispatches to :func:`stroke_orofacial.stats.runners.run_axis_for_endpoint`.
3. Collects the FitResult into an in-memory results table.

After all results are collected, applies BH-FDR within (axis,
granularity) families. For confirmatory endpoints, also applies
Bonferroni at the confirmatory granularity (defaults: per_session for
non-spatial, per_bin for spatial) and emits a separate
``p_adj_bonferroni`` column.

Output tree (per Addendum #5):

  pipeline_outputs/stats/results/
    <axis>/per_<granularity>/<endpoint>.csv   # 1-row per-endpoint result
    <axis>/per_<granularity>/_all.csv         # concat across endpoints w/ FDR + Bonferroni cols

Run:

  conda run -n stroke_orofacial python scripts/phase_9_stats/run_stats_axis.py \\
      --axis pre_post --granularity per_session

  conda run -n stroke_orofacial python scripts/phase_9_stats/run_stats_axis.py \\
      --axis all --granularity all   # full sweep

Estimated wall: ~30 sec serial for the full cohort (the heavy lifting is
in the materialized parquets; runners are lightweight scipy/statsmodels
calls).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import (  # noqa: E402
    apply_correction_to_results_df,
)
from stroke_orofacial.stats.runners import (  # noqa: E402
    run_axis_for_endpoint,
)


DEFAULT_INVENTORY = REPO_ROOT / ".scratch_phase_9" / "endpoint_inventory.csv"
VALID_AXES: tuple[str, ...] = ("pre_post", "recovery", "ipsi_contra", "trial_group")
VALID_GRANULARITIES: tuple[str, ...] = ("per_session", "per_bin", "per_epoch")
SPATIAL_VALUE_TYPE: str = "scalar_per_animal_time"
# Confirmatory-granularity defaults per Addendum #5 (E).
CONFIRMATORY_GRANULARITY_NON_SPATIAL: str = "per_session"
CONFIRMATORY_GRANULARITY_SPATIAL: str = "per_bin"


def _parse_axes_in_scope(raw: str) -> list[str]:
    """Parse comparison_axes_in_scope CSV field; semicolon-separated."""
    if not raw or not raw.strip():
        return []
    return [a.strip() for a in raw.split(";") if a.strip()]


def _load_inventory(inventory_path: Path) -> list[dict[str, Any]]:
    """Load endpoint inventory CSV; return list of dict-rows.

    Filters to endpoints where the materialized parquet path is set
    AND value_type is not in the skip list (vector_per_trial, etc).
    Excludes Commit C v1 orphan rows (materialized_path_template empty
    or non-conforming).
    """
    rows = list(csv.DictReader(open(inventory_path, "r", encoding="utf-8")))
    out: list[dict[str, Any]] = []
    for r in rows:
        path = r.get("materialized_path_template", "").strip()
        if not path.startswith("stats/inputs/"):
            continue
        if not r.get("value_type"):
            continue
        out.append(r)
    return out


def _load_endpoint_parquets(
    endpoint_slug: str, resolver: PathResolver, *, variant: str | None = None,
) -> pd.DataFrame:
    """Concat all per-animal parquets for one endpoint slug.

    Returns an empty DataFrame if the endpoint's directory doesn't
    exist (graceful degradation for missing endpoints — e.g. non-tongue
    endpoints have no ``filtered_v1`` input, so a filtered run naturally
    restricts to the tongue family).

    ``variant`` (e.g. ``"filtered_v1"``) reads from
    ``stats/inputs/<variant>/<slug>/`` instead of ``stats/inputs/<slug>/``.
    """
    base = resolver.pipeline_outputs(subdir="stats") / "inputs"
    in_dir = (base / variant / endpoint_slug) if variant else (base / endpoint_slug)
    if not in_dir.exists():
        return pd.DataFrame()
    parquets = sorted(in_dir.glob("*.parquet"))
    if not parquets:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)


def _result_row(
    endpoint_slug: str, axis: str, granularity: str, result,
) -> dict[str, Any]:
    """Flatten a FitResult into a CSV-friendly row dict."""
    return {
        "endpoint_slug": endpoint_slug,
        "axis": axis,
        "granularity": granularity,
        "model_name": result.model_name,
        "statistic": result.statistic,
        "p_value": result.p_value,
        "n_observations": result.n_observations,
        "status": result.details.get("status", "unknown"),
        "value_type": result.details.get("value_type", ""),
        "is_confirmatory": result.details.get("is_confirmatory", False),
        "details": str(result.details),
    }


def _confirmatory_granularity(value_type: str) -> str:
    return (
        CONFIRMATORY_GRANULARITY_SPATIAL
        if value_type == SPATIAL_VALUE_TYPE
        else CONFIRMATORY_GRANULARITY_NON_SPATIAL
    )


def _emit_csvs(
    results_df: pd.DataFrame, axis: str, granularity: str, out_root: Path,
) -> int:
    """Write per-endpoint + _all.csv for one (axis, granularity) slice.

    Returns count of CSVs written (1 per endpoint + 1 _all = N+1).
    """
    family_df = results_df[
        (results_df["axis"] == axis) & (results_df["granularity"] == granularity)
    ].copy()
    if family_df.empty:
        return 0
    # BH-FDR within this family.
    family_df = apply_correction_to_results_df(
        family_df, method="bh_fdr", group_cols=(),
        alpha=0.05, p_adj_col="p_adj_bh", reject_col="reject_bh",
    )
    # Bonferroni: applied within confirmatory subset of the family.
    family_df["p_adj_bonferroni"] = pd.NA
    family_df["reject_bonferroni"] = False
    confirmatory_mask = family_df["is_confirmatory"].astype(bool)
    if confirmatory_mask.any():
        # Build a sub-family with just the confirmatory rows + correct.
        sub = family_df[confirmatory_mask].copy()
        sub = apply_correction_to_results_df(
            sub, method="bonferroni", group_cols=(),
            alpha=0.05,
            p_adj_col="p_adj_bonferroni_tmp",
            reject_col="reject_bonferroni_tmp",
        )
        family_df.loc[confirmatory_mask, "p_adj_bonferroni"] = (
            sub["p_adj_bonferroni_tmp"].to_numpy()
        )
        family_df.loc[confirmatory_mask, "reject_bonferroni"] = (
            sub["reject_bonferroni_tmp"].to_numpy()
        )

    out_dir = out_root / axis / f"per_{granularity.replace('per_', '')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    n_written = 0
    for endpoint_slug, group in family_df.groupby("endpoint_slug"):
        path = out_dir / f"{endpoint_slug}.csv"
        group.to_csv(path, index=False)
        n_written += 1
    # _all.csv concat (sorted by p_adj_bh).
    all_df = family_df.sort_values(
        ["is_confirmatory", "p_adj_bh"], ascending=[False, True],
    )
    all_df.to_csv(out_dir / "_all.csv", index=False)
    n_written += 1
    return n_written


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--axis", choices=list(VALID_AXES) + ["all"], default="all",
    )
    p.add_argument(
        "--granularity", choices=list(VALID_GRANULARITIES) + ["all"], default="all",
    )
    p.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    p.add_argument(
        "--endpoints", nargs="*", default=None,
        help="Subset of endpoint slugs to run; default = all in scope.",
    )
    p.add_argument(
        "--filter-variant", choices=("none", "filtered_v1"), default="none",
        help=(
            "none (default): read stats/inputs/<slug>/ and write "
            "stats/results/. filtered_v1: read stats/inputs/filtered_v1/<slug>/ "
            "and write stats/results/filtered_v1/. Non-tongue endpoints have no "
            "filtered_v1 input, so the filtered BH-FDR family is tongue-only."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    axes = list(VALID_AXES) if args.axis == "all" else [args.axis]
    grans = list(VALID_GRANULARITIES) if args.granularity == "all" else [args.granularity]

    resolver = PathResolver()
    variant: str | None = (
        None if args.filter_variant == "none" else args.filter_variant
    )
    inventory = _load_inventory(args.inventory)
    if args.endpoints:
        inventory = [r for r in inventory if r["endpoint_slug"] in args.endpoints]

    print("Phase 9 Task 4 — per-axis hypothesis testing")
    print(f"  inventory:    {args.inventory.name} ({len(inventory)} endpoints in scope)")
    print(f"  axes:         {axes}")
    print(f"  granularities:{grans}")
    if variant:
        print(f"  filter variant: {variant} (tongue-only family)")
    print()

    results: list[dict[str, Any]] = []
    cache: dict[str, pd.DataFrame] = {}
    for row in inventory:
        slug = row["endpoint_slug"]
        value_type = row["value_type"]
        is_confirmatory = row["is_confirmatory"].lower() == "true"
        in_scope = _parse_axes_in_scope(row["comparison_axes_in_scope"])
        if not in_scope:
            continue
        for axis in axes:
            if axis not in in_scope:
                continue
            for gran in grans:
                if slug not in cache:
                    cache[slug] = _load_endpoint_parquets(
                        slug, resolver, variant=variant,
                    )
                df = cache[slug]
                if df.empty:
                    continue
                try:
                    result = run_axis_for_endpoint(
                        df, axis=axis, granularity=gran,
                        value_type=value_type,
                        is_confirmatory=is_confirmatory,
                    )
                except Exception as exc:
                    print(f"  ERROR {slug}/{axis}/{gran}: {type(exc).__name__}: {exc}")
                    continue
                results.append(_result_row(slug, axis, gran, result))

    if not results:
        print("No results produced. Exiting.")
        return 0

    results_df = pd.DataFrame(results)
    results_base = resolver.pipeline_outputs(subdir="stats") / "results"
    # Symmetric filter-variant wrapper: no-filter -> results/no_filter/,
    # filtered_v1 -> results/filtered_v1/. The unfiltered wrapper is named
    # "no_filter" (not "none") to match the phenotype_pooled figure convention
    # (<ep>/<scope>/no_filter/ vs /v3/) — one consistent filter-variant dir name
    # across results/ and figures/ (2026-06-01 cleanup).
    out_root = results_base / (variant or "no_filter")
    out_root.mkdir(parents=True, exist_ok=True)

    total_csvs = 0
    for axis in axes:
        for gran in grans:
            n = _emit_csvs(results_df, axis, gran, out_root)
            if n > 0:
                print(f"  [{axis}/per_{gran.replace('per_', '')}] wrote {n} CSVs")
            total_csvs += n

    print()
    print(f"Total results: {len(results_df)} fits across {len(axes)} axes × {len(grans)} granularities")
    print(f"Total CSVs:    {total_csvs}")
    print(f"Output root:   {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
