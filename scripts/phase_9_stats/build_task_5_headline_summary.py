"""Phase 9 Task 5 — Build .scratch_phase_9/task_5_headline_summary.csv (v2).

Per Priya 2026-05-24 directive + Addendum #10 (2026-05-25 lock):
produce ~180-220 rows of headline-plus-priority endpoint results,
one row per (endpoint × axis × comparison) at the endpoint's default
confirmatory granularity per value_type.

V2 schema (Addendum #10):

- `comparison` column NEW. Values:
  - `collapsed_post` for axis in {pre_post, ipsi_contra, trial_group}
    — the existing paired-test framing (collapses all post-stroke
    sessions into a single post bucket).
  - `continuous_rel_day_slope` for axis=recovery, non-spatial — the
    LMM slope on rel_day at per_session granularity.
  - `continuous_bin_midpoint_slope` for axis=recovery, spatial — the
    LMM slope at per_bin granularity (spatial confirmatory default
    per Addendum #5 F).
  - `pre_vs_acute` / `pre_vs_sub_acute` / `pre_vs_chronic` for
    axis=recovery at per_epoch granularity — per-coefficient
    extraction from `fit_per_epoch_lmm` details.
- `q_within_axis_comparison_family_bh` (renamed from
  `q_value_within_axis_granularity_family`) — BH-FDR within
  (axis, comparison) family across confirmatory endpoints.
- `q_within_endpoint_holm` NEW — Bonferroni-Holm sequential correction
  within each endpoint's 3 pre-vs-each-epoch comparisons. Populated
  only for axis=recovery / comparison=pre_vs_* rows.
- `bonferroni_passed` (per Addendum #10 C):
  - For per_epoch comparison rows + confirmatory: requires BOTH
    `q_within_endpoint_holm < 0.05` AND
    `q_within_axis_comparison_family_bh < 0.05`.
  - For per_epoch comparison rows + non-confirmatory: just
    `q_within_endpoint_holm < 0.05`.
  - For all other rows: unchanged from v1 (Bonferroni within axis
    family, confirmatory only).

Scope (unchanged from v1): endpoints where ``is_confirmatory=true``
OR ``n_permutations_override=100000`` in the inventory.

Confirmatory granularity per value_type:

- scalar_per_session       → per_session
- scalar_per_trial         → per_session (mean-across-trials per session)
- vector_per_session       → per_session (KS via Addendum #4)
- scalar_per_animal_time   → per_bin (spatial confirmatory granularity)
- scalar_per_session_trial_group → per_session
- bool_per_trial           → per_session

Sort: category → axis → comparison → abs(effect_size) DESC.

Reads from `pipeline_outputs/stats/results/<axis>/per_<gran>/_all.csv`
files written by `run_stats_axis.py`. Bootstrap CIs computed on the
underlying per-animal parquet data.

Run:
  conda run -n stroke_orofacial python scripts/phase_9_stats/build_task_5_headline_summary.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import (  # noqa: E402
    benjamini_hochberg_fdr,
    bonferroni_holm_within_endpoint,
)
from stroke_orofacial.stats.permutation import bootstrap_ci  # noqa: E402


DEFAULT_INVENTORY = REPO_ROOT / ".scratch_phase_9" / "endpoint_inventory.csv"
DEFAULT_N_PERMS = 10_000
PRIORITY_N_PERMS = 100_000
OUT_PATH = REPO_ROOT / ".scratch_phase_9" / "task_5_headline_summary.csv"

SPATIAL_VALUE_TYPE: str = "scalar_per_animal_time"

# Confirmatory granularity defaults per Addendum #5 (E).
_CONFIRMATORY_GRANULARITY: dict[str, str] = {
    "scalar_per_session": "per_session",
    "scalar_per_trial": "per_session",
    "vector_per_session": "per_session",
    "scalar_per_animal_time": "per_bin",
    "scalar_per_session_trial_group": "per_session",
    "bool_per_trial": "per_session",
}

# Effect-size metric per (model_name, comparison) tuple.
_EFFECT_METRIC: dict[str, str] = {
    "paired_pre_post_wilcoxon": "median_diff",
    "ipsi_contra_wilcoxon": "median_diff",
    "trial_group_friedman": "friedman_chi_sq",
    "pre_post_ks_distribution_shape": "ks_statistic",
    "recovery_mixedlm": "slope",
    "per_epoch_lmm": "epoch_coef",  # per-comparison row's effect = coef
}

_POST_EPOCH_COMPARISONS: tuple[str, ...] = (
    "pre_vs_acute", "pre_vs_sub_acute", "pre_vs_chronic",
)
_EPOCH_FROM_COMPARISON: dict[str, str] = {
    "pre_vs_acute": "acute",
    "pre_vs_sub_acute": "sub_acute",
    "pre_vs_chronic": "chronic",
}


def _parse_details_dict(details_str: str) -> dict:
    """Parse the str(dict) repr stored in the _all.csv `details` column.

    Substitutes nan/inf bare literals (rejected by ast.literal_eval)
    with None before parsing. Mirrors visual_gate._parse_recovery_fit_details.
    """
    if not isinstance(details_str, str) or not details_str.strip():
        return {}
    try:
        import ast
        cleaned = re.sub(
            r"\b(nan|NaN|NAN|inf|-inf|Inf)\b", "None", details_str,
        )
        return ast.literal_eval(cleaned)
    except Exception:
        return {}


def _load_inventory(path: Path) -> list[dict[str, Any]]:
    return list(csv.DictReader(open(path, "r", encoding="utf-8")))


def _filter_to_headline_priority(inv: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in inv:
        if not r.get("value_type"):
            continue
        is_conf = (r.get("is_confirmatory", "").lower() == "true")
        n_perm_raw = (r.get("n_permutations_override") or "").strip()
        is_priority = n_perm_raw == str(PRIORITY_N_PERMS)
        if is_conf or is_priority:
            out.append(r)
    return out


def _parse_axes_in_scope(raw: str) -> list[str]:
    if not raw:
        return []
    return [a.strip() for a in raw.split(";") if a.strip()]


def _resolved_n_permutations(row: dict) -> int:
    n_raw = (row.get("n_permutations_override") or "").strip()
    if not n_raw:
        return DEFAULT_N_PERMS
    try:
        return int(n_raw)
    except ValueError:
        return DEFAULT_N_PERMS


def _load_axis_gran_all_csv(
    out_root: Path, axis: str, gran: str,
) -> pd.DataFrame:
    p = out_root / axis / f"per_{gran.replace('per_', '')}" / "_all.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _effect_size_signed(
    row: pd.Series, model_name: str, comparison: str,
    details: dict,
) -> float:
    """Return signed effect for one fit row at one comparison."""
    if model_name == "paired_pre_post_wilcoxon":
        return float(details.get("median_diff", float("nan")))
    if model_name == "ipsi_contra_wilcoxon":
        return float(details.get("median_diff", float("nan")))
    if model_name == "recovery_mixedlm":
        return float(details.get("slope", float("nan")))
    if model_name == "pre_post_ks_distribution_shape":
        return float(row["statistic"])  # KS D (always non-negative)
    if model_name == "trial_group_friedman":
        return float(row["statistic"])  # chi-square (always non-negative)
    if model_name == "per_epoch_lmm" and comparison.startswith("pre_vs_"):
        epoch = _EPOCH_FROM_COMPARISON[comparison]
        per_epoch = details.get("per_epoch", {}) or {}
        e = per_epoch.get(epoch, {})
        return float(e.get("coef", float("nan")))
    return float(row.get("statistic", float("nan")))


def _bootstrap_ci_for(
    parquet_dir: Path, model_name: str, axis: str, comparison: str,
    *, rng_seed: int = 0,
) -> tuple[float, float]:
    """Compute a bootstrap CI on the signed effect for one row.

    Pragmatic surrogates per model type; see Task 4 close report.
    """
    parquets = sorted(parquet_dir.glob("*.parquet"))
    if not parquets:
        return float("nan"), float("nan")
    df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    if df.empty:
        return float("nan"), float("nan")

    try:
        if model_name in ("paired_pre_post_wilcoxon", "ipsi_contra_wilcoxon"):
            if model_name == "paired_pre_post_wilcoxon":
                key_col, left, right = "epoch_label", "acute", "pre"
            else:
                key_col, left, right = "ipsi_contra", "ipsi", "contra"
            grouped = df.groupby(["animal", key_col])["value"].mean().unstack(key_col)
            if left not in grouped.columns or right not in grouped.columns:
                return float("nan"), float("nan")
            diffs = (grouped[left] - grouped[right]).dropna().to_numpy()
            if diffs.size < 2:
                return float("nan"), float("nan")
            lo, hi = bootstrap_ci(
                diffs, statistic=lambda a: float(np.median(a)),
                n_boot=2000, ci=0.95, random_state=rng_seed,
            )
            return lo, hi
        elif model_name == "recovery_mixedlm":
            if "epoch_label" not in df.columns:
                return float("nan"), float("nan")
            grouped = df.groupby(["animal", "epoch_label"])["value"].mean().unstack("epoch_label")
            if "pre" not in grouped.columns:
                return float("nan"), float("nan")
            post_epochs = [c for c in ("acute", "sub_acute", "chronic") if c in grouped.columns]
            if not post_epochs:
                return float("nan"), float("nan")
            post_mean = grouped[post_epochs].mean(axis=1)
            diffs = (post_mean - grouped["pre"]).dropna().to_numpy()
            if diffs.size < 2:
                return float("nan"), float("nan")
            lo, hi = bootstrap_ci(
                diffs, statistic=lambda a: float(np.mean(a)),
                n_boot=2000, ci=0.95, random_state=rng_seed,
            )
            return lo, hi
        elif model_name == "per_epoch_lmm" and comparison.startswith("pre_vs_"):
            epoch = _EPOCH_FROM_COMPARISON[comparison]
            if "epoch_label" not in df.columns:
                return float("nan"), float("nan")
            grouped = df.groupby(["animal", "epoch_label"])["value"].mean().unstack("epoch_label")
            if "pre" not in grouped.columns or epoch not in grouped.columns:
                return float("nan"), float("nan")
            diffs = (grouped[epoch] - grouped["pre"]).dropna().to_numpy()
            if diffs.size < 2:
                return float("nan"), float("nan")
            lo, hi = bootstrap_ci(
                diffs, statistic=lambda a: float(np.mean(a)),
                n_boot=2000, ci=0.95, random_state=rng_seed,
            )
            return lo, hi
        elif model_name == "pre_post_ks_distribution_shape":
            pre = df.loc[df["epoch_label"] == "pre", "value"].dropna().to_numpy()
            post = df.loc[df["epoch_label"] == "acute", "value"].dropna().to_numpy()
            if pre.size < 5 or post.size < 5:
                return float("nan"), float("nan")
            from scipy.stats import ks_2samp
            rng = np.random.default_rng(rng_seed)
            stats = np.empty(500)
            for i in range(500):
                pre_b = rng.choice(pre, size=pre.size, replace=True)
                post_b = rng.choice(post, size=post.size, replace=True)
                stats[i] = ks_2samp(pre_b, post_b).statistic
            return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))
        else:
            return float("nan"), float("nan")
    except Exception:
        return float("nan"), float("nan")


def _n_animals_from_inputs(parquet_dir: Path) -> int:
    return len(list(parquet_dir.glob("*.parquet")))


def _build_row(
    *,
    inv_row: dict,
    fit_row: pd.Series,
    axis: str,
    granularity: str,
    comparison: str,
    p_value: float,
    effect_size: float,
    n_observations: int,
    n_animals: int,
    ci_lower: float,
    ci_upper: float,
    status: str,
    model_name: str,
) -> dict[str, Any]:
    return {
        "endpoint_slug": inv_row["endpoint_slug"],
        "category": inv_row.get("category", ""),
        "is_confirmatory": inv_row["is_confirmatory"].lower() == "true",
        "n_permutations": _resolved_n_permutations(inv_row),
        "axis": axis,
        "granularity": granularity,
        "comparison": comparison,
        "effect_size": effect_size,
        "effect_size_metric": _EFFECT_METRIC.get(model_name, "statistic"),
        "p_value": p_value,
        "q_within_axis_comparison_family_bh": float("nan"),  # filled later
        "q_within_endpoint_holm": float("nan"),              # filled later
        "bonferroni_passed": False,                          # filled later
        "n_animals": n_animals,
        "n_observations": n_observations,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "status": status,
        "model_name": model_name,  # internal helper; kept in output
    }


def main() -> int:
    resolver = PathResolver()
    inv = _load_inventory(DEFAULT_INVENTORY)
    headline = _filter_to_headline_priority(inv)
    print(f"Headline + priority endpoints: {len(headline)}")

    results_root = resolver.pipeline_outputs(subdir="stats") / "results"
    inputs_root = resolver.pipeline_outputs(subdir="stats") / "inputs"

    all_csv_cache: dict[tuple[str, str], pd.DataFrame] = {}

    def _get_all_csv(axis: str, gran: str) -> pd.DataFrame:
        k = (axis, gran)
        if k not in all_csv_cache:
            all_csv_cache[k] = _load_axis_gran_all_csv(results_root, axis, gran)
        return all_csv_cache[k]

    rows: list[dict[str, Any]] = []

    for inv_row in headline:
        slug = inv_row["endpoint_slug"]
        value_type = inv_row["value_type"]
        axes = _parse_axes_in_scope(inv_row["comparison_axes_in_scope"])
        default_gran = _CONFIRMATORY_GRANULARITY.get(value_type, "per_session")
        parquet_dir = inputs_root / slug
        n_animals = _n_animals_from_inputs(parquet_dir)

        for axis in axes:
            if axis == "recovery":
                # Continuous slope row at default confirmatory granularity.
                slope_gran = default_gran  # per_bin for spatial; per_session otherwise
                slope_df = _get_all_csv(axis, slope_gran)
                slope_match = slope_df[slope_df["endpoint_slug"] == slug] if not slope_df.empty else pd.DataFrame()
                if not slope_match.empty:
                    r = slope_match.iloc[0]
                    model_name = r["model_name"]
                    details = _parse_details_dict(r.get("details", ""))
                    comparison = (
                        "continuous_bin_midpoint_slope" if value_type == SPATIAL_VALUE_TYPE
                        else "continuous_rel_day_slope"
                    )
                    effect = _effect_size_signed(r, model_name, comparison, details)
                    ci_lo, ci_hi = _bootstrap_ci_for(parquet_dir, model_name, axis, comparison)
                    rows.append(_build_row(
                        inv_row=inv_row, fit_row=r, axis=axis,
                        granularity=slope_gran, comparison=comparison,
                        p_value=float(r["p_value"]) if pd.notna(r["p_value"]) else float("nan"),
                        effect_size=effect, n_observations=int(r["n_observations"]) if pd.notna(r["n_observations"]) else 0,
                        n_animals=n_animals,
                        ci_lower=ci_lo, ci_upper=ci_hi,
                        status=r.get("status", ""),
                        model_name=model_name,
                    ))

                # Per-coefficient pre_vs_<epoch> rows from recovery/per_epoch.
                ep_df = _get_all_csv("recovery", "per_epoch")
                ep_match = ep_df[ep_df["endpoint_slug"] == slug] if not ep_df.empty else pd.DataFrame()
                if not ep_match.empty:
                    r = ep_match.iloc[0]
                    model_name = r["model_name"]
                    details = _parse_details_dict(r.get("details", ""))
                    per_epoch = details.get("per_epoch", {}) or {}
                    for comparison in _POST_EPOCH_COMPARISONS:
                        epoch = _EPOCH_FROM_COMPARISON[comparison]
                        e = per_epoch.get(epoch)
                        if e is None:
                            continue
                        p_val = float(e.get("p_value", float("nan")))
                        coef = float(e.get("coef", float("nan")))
                        ci_lo, ci_hi = _bootstrap_ci_for(
                            parquet_dir, model_name, axis, comparison,
                        )
                        rows.append(_build_row(
                            inv_row=inv_row, fit_row=r, axis=axis,
                            granularity="per_epoch", comparison=comparison,
                            p_value=p_val, effect_size=coef,
                            n_observations=int(r["n_observations"]) if pd.notna(r["n_observations"]) else 0,
                            n_animals=n_animals,
                            ci_lower=ci_lo, ci_upper=ci_hi,
                            status=details.get("status", ""),
                            model_name=model_name,
                        ))
            else:
                # axis in {pre_post, ipsi_contra, trial_group} → 1 row at default gran.
                family_df = _get_all_csv(axis, default_gran)
                match = family_df[family_df["endpoint_slug"] == slug] if not family_df.empty else pd.DataFrame()
                if match.empty:
                    continue
                r = match.iloc[0]
                model_name = r["model_name"]
                details = _parse_details_dict(r.get("details", ""))
                comparison = "collapsed_post"
                effect = _effect_size_signed(r, model_name, comparison, details)
                ci_lo, ci_hi = _bootstrap_ci_for(parquet_dir, model_name, axis, comparison)
                rows.append(_build_row(
                    inv_row=inv_row, fit_row=r, axis=axis,
                    granularity=default_gran, comparison=comparison,
                    p_value=float(r["p_value"]) if pd.notna(r["p_value"]) else float("nan"),
                    effect_size=effect,
                    n_observations=int(r["n_observations"]) if pd.notna(r["n_observations"]) else 0,
                    n_animals=n_animals,
                    ci_lower=ci_lo, ci_upper=ci_hi,
                    status=r.get("status", ""),
                    model_name=model_name,
                ))

    if not rows:
        print("No headline rows produced — check inventory + results tree.")
        return 1
    df = pd.DataFrame(rows)

    # Bonferroni-Holm within each (endpoint × axis) over the 3 per_epoch comparisons.
    holm_mask = df["comparison"].isin(_POST_EPOCH_COMPARISONS)
    for (endpoint_slug, axis), grp in df[holm_mask].groupby(["endpoint_slug", "axis"]):
        p_by_comp = {row["comparison"]: row["p_value"] for _, row in grp.iterrows()}
        q_by_comp = bonferroni_holm_within_endpoint(p_by_comp)
        for idx, row in grp.iterrows():
            df.at[idx, "q_within_endpoint_holm"] = q_by_comp.get(
                row["comparison"], float("nan"),
            )

    # Cross-endpoint BH-FDR within (axis, comparison) family — confirmatory only
    # contributes to the family for the q-value semantics; non-confirmatory rows
    # get NaN at this column.
    for (axis, comparison), grp in df.groupby(["axis", "comparison"]):
        sub = grp[grp["is_confirmatory"].astype(bool)]
        if sub.empty:
            continue
        p_adj, _ = benjamini_hochberg_fdr(
            sub["p_value"].to_numpy(), alpha=0.05,
        )
        df.loc[sub.index, "q_within_axis_comparison_family_bh"] = p_adj

    # bonferroni_passed (Addendum #10 C):
    # - per_epoch comparison rows + confirmatory: BOTH holm AND BH-FDR < 0.05
    # - per_epoch comparison rows + non-confirmatory: holm < 0.05
    # - other rows + confirmatory: BH-FDR < 0.05 (cross-endpoint family)
    # - other rows + non-confirmatory: NaN
    def _decide_bonferroni_passed(row: pd.Series) -> Any:
        is_holm_row = row["comparison"] in _POST_EPOCH_COMPARISONS
        is_conf = bool(row["is_confirmatory"])
        if is_holm_row:
            holm_pass = (
                pd.notna(row["q_within_endpoint_holm"])
                and row["q_within_endpoint_holm"] < 0.05
            )
            if is_conf:
                bh_pass = (
                    pd.notna(row["q_within_axis_comparison_family_bh"])
                    and row["q_within_axis_comparison_family_bh"] < 0.05
                )
                return bool(holm_pass and bh_pass)
            return bool(holm_pass)
        if is_conf:
            bh_pass = (
                pd.notna(row["q_within_axis_comparison_family_bh"])
                and row["q_within_axis_comparison_family_bh"] < 0.05
            )
            return bool(bh_pass)
        return pd.NA

    df["bonferroni_passed"] = df.apply(_decide_bonferroni_passed, axis=1)

    # Sort: category → axis → comparison → abs(effect_size) DESC.
    df["_abs_effect"] = df["effect_size"].abs().fillna(0)
    df = df.sort_values(
        ["category", "axis", "comparison", "_abs_effect"],
        ascending=[True, True, True, False],
    ).drop(columns=["_abs_effect"])
    # Drop the internal model_name helper column from the final CSV.
    df = df.drop(columns=["model_name"], errors="ignore")
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH} ({len(df)} rows)")

    # Summary stats.
    n_conf = (df["is_confirmatory"]).sum()
    n_bonf_pass = (df["bonferroni_passed"] == True).sum()  # noqa: E712
    print()
    print(f"Confirmatory rows: {n_conf}")
    print(f"Bonferroni-passed confirmatory rows: {n_bonf_pass}")
    print()
    print("Per-(axis, comparison) confirmatory significance (q_bh<0.05):")
    for (axis, comparison), grp in df.groupby(["axis", "comparison"]):
        sub = grp[grp["is_confirmatory"].astype(bool)]
        if sub.empty:
            continue
        n_sig = (sub["q_within_axis_comparison_family_bh"] < 0.05).sum()
        n_bonf = (sub["bonferroni_passed"] == True).sum()  # noqa: E712
        print(
            f"  {axis:13s} {comparison:30s}  q_bh<0.05: {n_sig:3d}/{len(sub):3d}  "
            f"bonferroni-pass: {n_bonf:3d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
