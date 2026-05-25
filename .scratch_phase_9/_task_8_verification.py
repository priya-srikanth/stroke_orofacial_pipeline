"""Phase 9 Task 8 — verification gate analyses.

Produces 4 verification tables for `.scratch_phase_9/verdict.md`:

1. Methodology sanity — 2-3 endpoints per axis, expected sign + magnitude
2. Internal consistency — paired Wilcoxon (used in production) vs paired
   t-test (legacy) on the same per-animal pre/post pairs; agreement
   at alpha=0.05
3. Permutation reproducibility — seeded re-run of permutation null
   matches first run exactly
4. Cohort pool vs per-cohort-bin-size sensitivity — per-animal effect
   vs pooled effect; flag any endpoint where leave-one-animal-out
   sensitivity exceeds Cohen's d 0.3

Output: prints tables to stdout, writes one JSON-ish summary to
.scratch_phase_9/_task_8_results.txt for verdict.md generation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import ttest_rel, wilcoxon  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.permutation import (  # noqa: E402
    paired_permutation_null,
    permutation_p_value,
)


SCRATCH = Path(__file__).resolve().parent
RESULTS = {}


def _load_cohort(slug: str, inputs_root: Path) -> pd.DataFrame:
    d = inputs_root / slug
    if not d.exists():
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in d.glob("*.parquet")], ignore_index=True)


def _per_animal_pre_post(df: pd.DataFrame, post_epoch: str = "acute") -> dict[str, tuple[float, float]]:
    """Return {animal: (pre_mean, post_mean)} from a stats-input parquet."""
    df = df[~df["is_sentinel"].astype(bool)].dropna(subset=["value"])
    pre = df[df["epoch_label"] == "pre"].groupby("animal")["value"].mean()
    post = df[df["epoch_label"] == post_epoch].groupby("animal")["value"].mean()
    return {a: (float(pre[a]), float(post[a])) for a in pre.index if a in post.index}


# ---------------------------------------------------------------------------
# 8a — Methodology sanity (2-3 endpoints per axis)
# ---------------------------------------------------------------------------

def methodology_sanity(headline_df: pd.DataFrame) -> dict:
    """For each axis, pick 2-3 high-impact confirmatory endpoints and
    report effect direction + sign matches scientific expectation."""
    print("\n=== 8a — Methodology sanity ===")
    expectations = {
        "pre_post": {
            # endpoint_slug -> (expected direction sign, why)
            "first_lick_accuracy_all": (-1, "stroke reduces accuracy"),
            "num_correct_licks_per_trial": (-1, "stroke reduces correct licks/trial"),
            "tongue_lick1_t_peak_ms": (+1, "stroke increases lick latency"),
        },
        "recovery": {
            "first_lick_accuracy_all": (+1, "recovery slope positive (returns to baseline)"),
            "num_incorrect_licks_per_trial": (-1, "incorrect licks decline over time"),
            "tongue_lick1_y_peak": (-1, "y_peak declines toward baseline post-acute spike"),
        },
        "ipsi_contra": {
            "tongue_lick1_x_at_ypeak": (+1, "tongue X shifts toward ipsi (stroke-side bias)"),
            "tongue_lick1_angle_at_ypeak": (+1, "angle shifts toward ipsi"),
        },
    }
    rows = []
    for axis, expected in expectations.items():
        # For recovery, use continuous_rel_day_slope; for pre_post/ipsi_contra use collapsed_post.
        comparison = "continuous_rel_day_slope" if axis == "recovery" else "collapsed_post"
        for slug, (expected_sign, why) in expected.items():
            sub = headline_df[
                (headline_df["axis"] == axis)
                & (headline_df["comparison"] == comparison)
                & (headline_df["endpoint_slug"] == slug)
            ]
            if sub.empty:
                rows.append((axis, slug, "MISSING", "MISSING", expected_sign, why))
                continue
            r = sub.iloc[0]
            observed = float(r["effect_size"])
            observed_sign = 1 if observed > 0 else (-1 if observed < 0 else 0)
            sig = float(r["q_within_axis_comparison_family_bh"])
            verdict = "OK" if observed_sign == expected_sign and sig < 0.05 else "REVIEW"
            rows.append((axis, slug, f"{observed:+.3g}", f"{sig:.2e}", expected_sign, why, verdict))
    for row in rows:
        if len(row) == 7:
            axis, slug, eff, q, expected, why, verdict = row
            print(f"  [{verdict}] {axis:13s} {slug:55s} eff={eff:>10s} q={q}  expect_sign={expected:+d} ({why})")
        else:
            axis, slug, eff, q, expected, why = row
            print(f"  [MISSING] {axis:13s} {slug}")
    RESULTS["methodology_sanity"] = [list(r) for r in rows]
    pass_count = sum(1 for r in rows if len(r) == 7 and r[6] == "OK")
    total = len(rows)
    print(f"  Pass: {pass_count}/{total}")
    return {"pass_count": pass_count, "total": total, "rows": rows}


# ---------------------------------------------------------------------------
# 8b — Internal consistency (Wilcoxon vs paired t-test)
# ---------------------------------------------------------------------------

def internal_consistency(inputs_root: Path) -> dict:
    print("\n=== 8b — Internal consistency (paired Wilcoxon vs paired t-test) ===")
    endpoints = [
        "first_lick_accuracy_all",
        "num_correct_licks_per_trial",
        "tongue_lick1_y_peak",
        "tongue_lick1_t_peak_ms",
        "spatial_wasserstein_jaw_eye_midpoint_tone_aligned_all",
    ]
    rows = []
    for slug in endpoints:
        cohort = _load_cohort(slug, inputs_root)
        if cohort.empty:
            rows.append((slug, "MISSING", "MISSING", "MISSING"))
            continue
        pre_post = _per_animal_pre_post(cohort)
        if len(pre_post) < 3:
            rows.append((slug, "INSUFFICIENT", "INSUFFICIENT", "INSUFFICIENT"))
            continue
        pre = np.asarray([v[0] for v in pre_post.values()])
        post = np.asarray([v[1] for v in pre_post.values()])
        try:
            w_stat, w_p = wilcoxon(post, pre, alternative="two-sided")
        except Exception as exc:
            w_p = float("nan")
        try:
            t_stat, t_p = ttest_rel(post, pre)
        except Exception as exc:
            t_p = float("nan")
        agree = (
            (w_p < 0.05) == (t_p < 0.05)
            if (not np.isnan(w_p) and not np.isnan(t_p)) else False
        )
        rows.append((
            slug, f"{w_p:.3e}", f"{t_p:.3e}",
            "AGREE" if agree else "DIVERGE",
        ))
    for slug, w_p, t_p, verdict in rows:
        print(f"  [{verdict}] {slug:55s}  Wilcoxon p={w_p:>12s}  t-test p={t_p:>12s}")
    RESULTS["internal_consistency"] = rows
    agree_count = sum(1 for r in rows if r[-1] == "AGREE")
    print(f"  Agree at alpha=0.05: {agree_count}/{len(rows)}")
    return {"agree_count": agree_count, "total": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# 8c — Permutation reproducibility
# ---------------------------------------------------------------------------

def permutation_reproducibility() -> dict:
    print("\n=== 8c — Permutation reproducibility (seeded re-run) ===")
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 30)
    y = x + rng.normal(2, 0.5, 30)  # known shift

    null1 = paired_permutation_null(x, y, n_perm=1000, random_state=42)
    null2 = paired_permutation_null(x, y, n_perm=1000, random_state=42)
    null3 = paired_permutation_null(x, y, n_perm=1000, random_state=99)  # different seed

    identical = np.allclose(null1, null2)
    different = not np.allclose(null1, null3)

    obs = float(np.mean(x) - np.mean(y))
    p1 = permutation_p_value(obs, null1, alternative="two-sided")
    p2 = permutation_p_value(obs, null2, alternative="two-sided")
    p_match = p1 == p2

    print(f"  Same seed (42) → identical null arrays:    {identical}")
    print(f"  Different seed (99) → null array differs:  {different}")
    print(f"  Same-seed p_values match exactly:          {p_match} (p1={p1:.4f}, p2={p2:.4f})")
    verdict = "PASS" if (identical and different and p_match) else "FAIL"
    print(f"  Verdict: {verdict}")
    result = {
        "verdict": verdict,
        "same_seed_identical": bool(identical),
        "different_seed_differs": bool(different),
        "p_value_reproducible": bool(p_match),
        "obs_p_value": p1,
    }
    RESULTS["permutation_reproducibility"] = result
    return result


# ---------------------------------------------------------------------------
# 8d — Cohort pool vs leave-one-out sensitivity (Cohen's d threshold)
# ---------------------------------------------------------------------------

def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return float("nan")
    s_pooled = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2.0)
    if s_pooled <= 0:
        return float("nan")
    return float((np.mean(a) - np.mean(b)) / s_pooled)


def sensitivity_loo(headline_df: pd.DataFrame, inputs_root: Path) -> dict:
    print("\n=== 8d — Cohort pool vs per-animal sensitivity (|Cohen's d| > 0.3 threshold) ===")
    # Limit to confirmatory pre_post endpoints for tractability.
    confirmatory = headline_df[
        headline_df["is_confirmatory"].astype(bool)
        & (headline_df["axis"] == "pre_post")
        & (headline_df["comparison"] == "collapsed_post")
    ]["endpoint_slug"].unique().tolist()
    rows = []
    for slug in sorted(confirmatory):
        cohort = _load_cohort(slug, inputs_root)
        if cohort.empty:
            continue
        pre_post = _per_animal_pre_post(cohort)
        if len(pre_post) < 4:
            continue
        animals = list(pre_post.keys())
        diffs = np.asarray([pre_post[a][1] - pre_post[a][0] for a in animals])
        pooled_mean = float(np.mean(diffs))
        # Leave-one-animal-out divergence: per-LOO mean diff vs pooled mean diff,
        # expressed as Cohen's d using the within-LOO SD as denominator.
        max_d = 0.0
        max_animal = None
        for i, a in enumerate(animals):
            mask = np.ones(len(diffs), dtype=bool)
            mask[i] = False
            loo_diffs = diffs[mask]
            if loo_diffs.size < 2:
                continue
            d = (pooled_mean - float(np.mean(loo_diffs))) / max(
                float(np.std(loo_diffs, ddof=1)), 1e-9,
            )
            if abs(d) > abs(max_d):
                max_d = d
                max_animal = a
        flag = "FLAG" if abs(max_d) > 0.3 else "OK"
        rows.append((slug, f"{pooled_mean:+.4g}", f"{max_d:+.3f}", max_animal or "-", flag))
    rows.sort(key=lambda r: -abs(float(r[2]) if r[2] not in ("MISSING", "INSUFFICIENT") else 0))
    for slug, pm, d, animal, flag in rows:
        print(f"  [{flag}] {slug:55s}  pooled_diff={pm:>10s}  max|d|={d:>8s} (drop {animal})")
    n_flag = sum(1 for r in rows if r[-1] == "FLAG")
    print(f"  Flagged (|Cohen's d| > 0.3): {n_flag}/{len(rows)}")
    RESULTS["sensitivity_loo"] = rows
    return {"flagged": n_flag, "total": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    resolver = PathResolver()
    inputs_root = resolver.pipeline_outputs(subdir="stats") / "inputs"
    headline = SCRATCH / "task_5_headline_summary.csv"
    if not headline.exists():
        print("Headline summary not found; run build_task_5_headline_summary.py first.")
        return 1
    headline_df = pd.read_csv(headline)

    methodology_sanity(headline_df)
    internal_consistency(inputs_root)
    permutation_reproducibility()
    sensitivity_loo(headline_df, inputs_root)

    out = SCRATCH / "_task_8_results.json"
    out.write_text(json.dumps(RESULTS, indent=2, default=str))
    print(f"\nResults written to {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
