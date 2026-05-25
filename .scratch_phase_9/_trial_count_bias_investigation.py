"""Phase 9 Task 8 mid-flight investigation — trial-count bias check.

Per Priya 2026-05-25 methodological concern: elevated tongue acute
results may be skewed by low-trial-count sessions where DLC tracking
degradation + outlier dominance inflate session means. PS51/PS54/PS55
acute periods have dramatically reduced lick frequency due to stroke;
sessions with only a few detected trials could dominate the session-
level aggregate that the LMM consumes.

Non-destructive analysis only. No parquet writes; no production code
changes.

Suspect endpoints:
  - tongue_lick1_y_peak
  - tongue_lick1_vxy_peak
  - tongue_max_vxy_peak_first5
  - tongue_mean_vxy_peak_first5

For each (animal, epoch):
  1. Bucket sessions by n_detected_trials (non-sentinel rows per session)
  2. Compare low-n vs high-n session-level statistics
  3. Counterfactual LMM acute coefficient on filtered data (n_trials >= 10)
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRATCH = Path(__file__).resolve().parent
import sys
REPO_ROOT = SCRATCH.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.animals import load_animals  # noqa: E402


SUSPECT_ENDPOINTS = (
    "tongue_lick1_y_peak",
    "tongue_lick1_vxy_peak",
    "tongue_max_vxy_peak_first5",
    "tongue_mean_vxy_peak_first5",
)

# Phenotype groupings per the cohort definition.
PHENOTYPE_GROUPS = {
    "mild (PS47-PS50)": ["PS47", "PS48", "PS49", "PS50"],
    "moderate (PS46)": ["PS46"],
    "moderate-severe (PS51)": ["PS51"],
    "severe (PS54, PS55)": ["PS54", "PS55"],
}

N_TRIAL_BUCKETS = [
    ("<5", lambda n: n < 5),
    ("5-9", lambda n: 5 <= n < 10),
    ("10-19", lambda n: 10 <= n < 20),
    (">=20", lambda n: n >= 20),
]


def _load(slug: str, inputs_root: Path) -> pd.DataFrame:
    d = inputs_root / slug
    if not d.exists():
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in d.glob("*.parquet")], ignore_index=True)


def _session_n_trials(df: pd.DataFrame) -> pd.DataFrame:
    """Compute n_detected_trials per (animal, date) from non-sentinel rows."""
    non_sentinel = df[~df["is_sentinel"].astype(bool)]
    n = non_sentinel.groupby(["animal", "date", "rel_day", "epoch_label"]).size()
    means = non_sentinel.groupby(["animal", "date", "rel_day", "epoch_label"])["value"].mean()
    out = pd.DataFrame({"n_trials": n, "session_mean": means}).reset_index()
    return out


def _bucket_label(n: int) -> str:
    for label, fn in N_TRIAL_BUCKETS:
        if fn(n):
            return label
    return "?"


# ---------------------------------------------------------------------------
# 1. Per-(animal, epoch) trial-count distribution
# ---------------------------------------------------------------------------

def report_trial_count_distribution(per_session: pd.DataFrame) -> None:
    print("\n--- 1. Trial-count distribution per (animal, epoch) ---")
    bucket_names = [b[0] for b in N_TRIAL_BUCKETS]
    rows = []
    for animal in sorted(per_session["animal"].unique()):
        for epoch in ("pre", "acute", "sub_acute", "chronic"):
            sub = per_session[
                (per_session["animal"] == animal) & (per_session["epoch_label"] == epoch)
            ]
            if sub.empty:
                continue
            counts = {b: 0 for b in bucket_names}
            for n in sub["n_trials"]:
                counts[_bucket_label(int(n))] += 1
            rows.append({"animal": animal, "epoch": epoch, "n_sessions": len(sub), **counts})
    df = pd.DataFrame(rows)
    # Highlight PS51/PS54/PS55 acute.
    print(df.to_string(index=False))


# ---------------------------------------------------------------------------
# 2. Low-n vs high-n session-mean comparison
# ---------------------------------------------------------------------------

def report_low_vs_high_n(per_session: pd.DataFrame, endpoint: str) -> None:
    print(f"\n--- 2. {endpoint}: low-n (<10) vs high-n (>=10) session-mean comparison ---")
    rows = []
    # Per (group, epoch) summary.
    for group_name, animals in PHENOTYPE_GROUPS.items():
        for epoch in ("pre", "acute", "sub_acute", "chronic"):
            sub = per_session[
                per_session["animal"].isin(animals)
                & (per_session["epoch_label"] == epoch)
            ]
            if sub.empty:
                continue
            low = sub[sub["n_trials"] < 10]
            high = sub[sub["n_trials"] >= 10]
            row = {
                "group": group_name,
                "epoch": epoch,
                "n_low_sess": len(low),
                "n_high_sess": len(high),
                "low_mean": low["session_mean"].mean() if not low.empty else float("nan"),
                "high_mean": high["session_mean"].mean() if not high.empty else float("nan"),
                "low_median": low["session_mean"].median() if not low.empty else float("nan"),
                "high_median": high["session_mean"].median() if not high.empty else float("nan"),
                "low_max": low["session_mean"].max() if not low.empty else float("nan"),
                "high_max": high["session_mean"].max() if not high.empty else float("nan"),
            }
            if pd.notna(row["low_mean"]) and pd.notna(row["high_mean"]) and row["high_mean"] != 0:
                row["ratio_low/high"] = row["low_mean"] / row["high_mean"]
            else:
                row["ratio_low/high"] = float("nan")
            rows.append(row)
    df = pd.DataFrame(rows)
    print(df.round(3).to_string(index=False))


# ---------------------------------------------------------------------------
# 3. Counterfactual LMM acute coefficient if n_trials < 10 sessions excluded
# ---------------------------------------------------------------------------

def report_counterfactual_lmm(per_session: pd.DataFrame, endpoint: str) -> None:
    print(f"\n--- 3. {endpoint}: Counterfactual LMM acute coefficient (n_trials >= 10 filter) ---")
    # Reproduce production LMM math: fit_per_epoch_lmm with epoch as
    # categorical predictor + animal random intercept on RAW values.
    from statsmodels.regression.mixed_linear_model import MixedLM

    def _fit(df: pd.DataFrame, label: str) -> dict:
        if df["epoch_label"].nunique() < 2:
            return {"status": "insufficient_data"}
        epoch_levels = sorted(df["epoch_label"].dropna().unique().tolist())
        if "pre" in epoch_levels:
            epoch_levels = ["pre"] + [e for e in epoch_levels if e != "pre"]
        df = df.copy()
        df["epoch_label"] = pd.Categorical(
            df["epoch_label"], categories=epoch_levels, ordered=False,
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                md = MixedLM.from_formula(
                    "session_mean ~ C(epoch_label)",
                    groups=df["animal"],
                    data=df,
                )
                mdf = md.fit(method="lbfgs", reml=True)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}
        if not mdf.converged:
            return {"status": "convergence_failed"}
        per_epoch = {}
        for param_name, coef in mdf.fe_params.items():
            if param_name == "Intercept":
                continue
            epoch = param_name.split("[T.")[-1].rstrip("]")
            per_epoch[epoch] = {
                "coef": float(coef),
                "p_value": float(mdf.pvalues[param_name]),
                "se": float(mdf.bse_fe[param_name]),
            }
        return {"status": "ok", "per_epoch": per_epoch}

    full = _fit(per_session, "FULL (no filter)")
    filtered = _fit(per_session[per_session["n_trials"] >= 10], "FILTERED (n_trials >= 10)")

    rows = []
    for epoch in ("acute", "sub_acute", "chronic"):
        full_e = full.get("per_epoch", {}).get(epoch, {})
        filt_e = filtered.get("per_epoch", {}).get(epoch, {})
        full_coef = full_e.get("coef", float("nan"))
        filt_coef = filt_e.get("coef", float("nan"))
        if pd.notna(full_coef) and full_coef != 0:
            pct_change = (filt_coef - full_coef) / abs(full_coef) * 100.0
        else:
            pct_change = float("nan")
        rows.append({
            "epoch": epoch,
            "full_coef": full_coef,
            "filtered_coef": filt_coef,
            "pct_change": pct_change,
            "full_p": full_e.get("p_value", float("nan")),
            "filtered_p": filt_e.get("p_value", float("nan")),
        })
    print(pd.DataFrame(rows).round(4).to_string(index=False))

    n_full = len(per_session)
    n_filt = len(per_session[per_session["n_trials"] >= 10])
    print(f"  sessions FULL: {n_full}   FILTERED: {n_filt}  ({n_full - n_filt} dropped at n_trials<10)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    resolver = PathResolver()
    inputs_root = resolver.pipeline_outputs(subdir="stats") / "inputs"
    print("=" * 70)
    print("Phase 9 Task 8 mid-flight — trial-count bias investigation")
    print("=" * 70)

    all_endpoint_summary: dict[str, dict] = {}
    for slug in SUSPECT_ENDPOINTS:
        print(f"\n{'=' * 70}\n{slug}\n{'=' * 70}")
        cohort = _load(slug, inputs_root)
        if cohort.empty:
            print(f"  MISSING: no parquets at stats/inputs/{slug}/")
            continue
        per_session = _session_n_trials(cohort)
        report_trial_count_distribution(per_session)
        report_low_vs_high_n(per_session, slug)
        report_counterfactual_lmm(per_session, slug)

    print("\n" + "=" * 70)
    print("Done. See verdict below for interpretation.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
