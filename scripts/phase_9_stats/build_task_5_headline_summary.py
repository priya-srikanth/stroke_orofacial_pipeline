"""Phase 9 Task 5 — Build .scratch_phase_9/task_5_headline_summary.csv.

Per Priya 2026-05-24 directive: produce ~70-100 rows of headline-plus-
priority endpoint results for spot-check BEFORE Task 6/7 figure work.

Scope: endpoints where ``is_confirmatory=true`` OR
``n_permutations_override=100000`` in the inventory. One row per
(endpoint, axis) pair at the endpoint's default confirmatory
granularity per value_type:

- scalar_per_session       → per_session
- scalar_per_trial         → per_session (mean-across-trials per session)
- vector_per_session       → per_session (KS via Addendum #4)
- scalar_per_animal_time   → per_bin (spatial confirmatory granularity)
- scalar_per_session_trial_group → per_session
- bool_per_trial           → per_session (mean-across-trials per session)

Columns: endpoint_slug, category, is_confirmatory, n_permutations,
axis, granularity, effect_size (signed), effect_size_metric, p_value,
q_value_within_axis_granularity_family (BH-FDR), bonferroni_passed
(bool; populated only if is_confirmatory=true), n_animals,
n_observations, ci_lower, ci_upper (bootstrap CI on effect size),
status (FitResult.status).

Sort: category → axis → abs(effect_size) DESC.

Reads from `pipeline_outputs/stats/results/<axis>/per_<gran>/_all.csv`
files written by `run_stats_axis.py`. Bootstrap CIs computed on the
underlying per-animal parquet data.

Run:
  conda run -n stroke_orofacial python scripts/phase_9_stats/build_task_5_headline_summary.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.permutation import bootstrap_ci  # noqa: E402


DEFAULT_INVENTORY = REPO_ROOT / ".scratch_phase_9" / "endpoint_inventory.csv"
DEFAULT_N_PERMS = 10_000
PRIORITY_N_PERMS = 100_000
OUT_PATH = REPO_ROOT / ".scratch_phase_9" / "task_5_headline_summary.csv"

# Confirmatory granularity defaults per Addendum #5 (E).
_CONFIRMATORY_GRANULARITY: dict[str, str] = {
    "scalar_per_session": "per_session",
    "scalar_per_trial": "per_session",
    "vector_per_session": "per_session",
    "scalar_per_animal_time": "per_bin",
    "scalar_per_session_trial_group": "per_session",
    "bool_per_trial": "per_session",
}

# Effect-size metric per model_name.
_EFFECT_METRIC: dict[str, str] = {
    "paired_pre_post_wilcoxon": "median_diff",
    "ipsi_contra_wilcoxon": "median_diff",
    "trial_group_friedman": "friedman_chi_sq",
    "pre_post_ks_distribution_shape": "ks_statistic",
    "recovery_mixedlm": "slope",
    "per_epoch_lmm": "max_abs_coef",
}


def _load_inventory(path: Path) -> list[dict[str, Any]]:
    return list(csv.DictReader(open(path, "r", encoding="utf-8")))


def _filter_to_headline_priority(inv: list[dict]) -> list[dict]:
    """Headline (is_confirmatory=true) ∪ priority (n_permutations_override=100000)."""
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


def _parse_details_dict(details_str: str) -> dict:
    """Parse the str(dict) repr stored in the _all.csv `details` column.

    Substitutes nan/inf literals (which ``ast.literal_eval`` rejects)
    with None before parsing — matches the parser in
    ``visual_gate._parse_recovery_fit_details``.
    """
    if not isinstance(details_str, str) or not details_str.strip():
        return {}
    try:
        import ast
        import re
        cleaned = re.sub(
            r"\b(nan|NaN|NAN|inf|-inf|Inf)\b", "None", details_str,
        )
        return ast.literal_eval(cleaned)
    except Exception:
        return {}


def _effect_size_from_fit_row(
    row: pd.Series, model_name: str,
) -> tuple[float, str]:
    """Return (signed_effect, metric_name) for one fit row."""
    metric = _EFFECT_METRIC.get(model_name, "statistic")
    details = _parse_details_dict(row.get("details", ""))
    if model_name == "paired_pre_post_wilcoxon":
        v = details.get("median_diff", float("nan"))
    elif model_name == "ipsi_contra_wilcoxon":
        v = details.get("median_diff", float("nan"))
    elif model_name == "recovery_mixedlm":
        v = details.get("slope", float("nan"))
    elif model_name == "pre_post_ks_distribution_shape":
        v = row["statistic"]  # KS D
    elif model_name == "trial_group_friedman":
        v = row["statistic"]  # chi-square
    elif model_name == "per_epoch_lmm":
        per_epoch = details.get("per_epoch", {})
        if per_epoch:
            v = max(
                (e["coef"] for e in per_epoch.values()),
                key=lambda x: abs(x),
            )
        else:
            v = float("nan")
    else:
        v = row["statistic"]
    return float(v), metric


def _bootstrap_effect_ci(
    parquet_dir: Path, slug: str, model_name: str, axis: str,
    *, rng_seed: int = 0,
) -> tuple[float, float]:
    """Bootstrap CI on the effect size for one (endpoint, axis).

    For Wilcoxon (pre_post + ipsi_contra): CI on median paired diff.
    For KS: CI on the KS statistic (resample within each pool).
    For LMM-type fits (recovery, per_epoch): CI on the mean post-pre
    difference (pragmatic surrogate; full LMM bootstrap is too slow
    for a 70-row sweep).

    Returns (NaN, NaN) on failure / insufficient data.
    """
    parquets = sorted(parquet_dir.glob("*.parquet"))
    if not parquets:
        return float("nan"), float("nan")
    df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    if df.empty:
        return float("nan"), float("nan")

    try:
        if model_name in ("paired_pre_post_wilcoxon", "ipsi_contra_wilcoxon"):
            # Build per-animal paired diffs.
            if model_name == "paired_pre_post_wilcoxon":
                key_col = "epoch_label"
                left, right = "acute", "pre"
            else:
                key_col = "ipsi_contra"
                left, right = "ipsi", "contra"
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
        elif model_name in ("recovery_mixedlm", "per_epoch_lmm"):
            # Pragmatic surrogate: bootstrap CI on per-animal post-mean
            # minus pre-mean.
            if "epoch_label" not in df.columns:
                return float("nan"), float("nan")
            grouped = df.groupby(["animal", "epoch_label"])["value"].mean().unstack("epoch_label")
            if "pre" not in grouped.columns:
                return float("nan"), float("nan")
            post_epochs = [c for c in ("acute", "sub_acute", "chronic") if c in grouped.columns]
            if not post_epochs:
                return float("nan"), float("nan")
            # Take the post mean across whichever epochs are present.
            post_mean = grouped[post_epochs].mean(axis=1)
            diffs = (post_mean - grouped["pre"]).dropna().to_numpy()
            if diffs.size < 2:
                return float("nan"), float("nan")
            lo, hi = bootstrap_ci(
                diffs, statistic=lambda a: float(np.mean(a)),
                n_boot=2000, ci=0.95, random_state=rng_seed,
            )
            return lo, hi
        elif model_name == "pre_post_ks_distribution_shape":
            # KS D bootstrap: resample within each pool independently.
            pre = df.loc[df["epoch_label"] == "pre", "value"].dropna().to_numpy()
            post = df.loc[df["epoch_label"] == "acute", "value"].dropna().to_numpy()
            if pre.size < 5 or post.size < 5:
                return float("nan"), float("nan")
            # Stratified bootstrap (resample pre + post separately).
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
    parquets = list(parquet_dir.glob("*.parquet"))
    return len(parquets)  # one per animal


def main() -> int:
    resolver = PathResolver()
    inv = _load_inventory(DEFAULT_INVENTORY)
    headline = _filter_to_headline_priority(inv)
    print(f"Headline + priority endpoints: {len(headline)}")

    results_root = resolver.pipeline_outputs(subdir="stats") / "results"
    inputs_root = resolver.pipeline_outputs(subdir="stats") / "inputs"

    # Cache _all.csv reads per (axis, gran).
    all_csv_cache: dict[tuple[str, str], pd.DataFrame] = {}

    rows: list[dict[str, Any]] = []
    for inv_row in headline:
        slug = inv_row["endpoint_slug"]
        value_type = inv_row["value_type"]
        category = inv_row.get("category", "")
        is_conf = inv_row["is_confirmatory"].lower() == "true"
        n_perm = _resolved_n_permutations(inv_row)
        gran = _CONFIRMATORY_GRANULARITY.get(value_type, "per_session")
        axes = _parse_axes_in_scope(inv_row["comparison_axes_in_scope"])
        for axis in axes:
            cache_key = (axis, gran)
            if cache_key not in all_csv_cache:
                all_csv_cache[cache_key] = _load_axis_gran_all_csv(
                    results_root, axis, gran,
                )
            family_df = all_csv_cache[cache_key]
            if family_df.empty:
                continue
            row_match = family_df[family_df["endpoint_slug"] == slug]
            if row_match.empty:
                continue
            r = row_match.iloc[0]
            effect, metric = _effect_size_from_fit_row(r, r["model_name"])
            parquet_dir = inputs_root / slug
            ci_lo, ci_hi = _bootstrap_effect_ci(
                parquet_dir, slug, r["model_name"], axis,
            )
            n_animals = _n_animals_from_inputs(parquet_dir)
            bonf = (
                bool(r.get("reject_bonferroni", False))
                if is_conf else None
            )
            rows.append({
                "endpoint_slug": slug,
                "category": category,
                "is_confirmatory": is_conf,
                "n_permutations": n_perm,
                "axis": axis,
                "granularity": gran,
                "effect_size": effect,
                "effect_size_metric": metric,
                "p_value": float(r["p_value"]) if pd.notna(r["p_value"]) else float("nan"),
                "q_value_within_axis_granularity_family": float(r["p_adj_bh"]) if pd.notna(r["p_adj_bh"]) else float("nan"),
                "bonferroni_passed": bonf,
                "n_animals": n_animals,
                "n_observations": int(r["n_observations"]) if pd.notna(r["n_observations"]) else 0,
                "ci_lower": ci_lo,
                "ci_upper": ci_hi,
                "status": r.get("status", ""),
            })

    if not rows:
        print("No headline rows produced — check inventory + results tree.")
        return 1

    df = pd.DataFrame(rows)
    # Sort: category → axis → abs(effect_size) DESC.
    df["_abs_effect"] = df["effect_size"].abs().fillna(0)
    df = df.sort_values(
        ["category", "axis", "_abs_effect"], ascending=[True, True, False],
    ).drop(columns=["_abs_effect"])
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH} ({len(df)} rows)")

    # Brief summary stats.
    n_conf = (df["is_confirmatory"]).sum()
    n_bonf_pass = (df["bonferroni_passed"] == True).sum()  # noqa: E712
    print()
    print(f"Confirmatory rows: {n_conf}")
    print(f"Bonferroni-passed confirmatory rows: {n_bonf_pass}")
    print()
    print("Per-axis confirmatory significance (q < 0.05):")
    for axis in sorted(df["axis"].unique()):
        sub = df[(df["axis"] == axis) & df["is_confirmatory"]]
        n_sig = (sub["q_value_within_axis_granularity_family"] < 0.05).sum()
        n_bonf = (sub["bonferroni_passed"] == True).sum()  # noqa: E712
        print(f"  {axis:15s}  q<0.05: {n_sig:3d}/{len(sub):3d}  bonferroni-pass: {n_bonf:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
