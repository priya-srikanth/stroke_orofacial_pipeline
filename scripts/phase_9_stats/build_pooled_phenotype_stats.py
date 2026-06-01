"""Driver — consolidated phenotype-pooled stats suite (kickoff doc, 2026-06-01).

Runs the scalar stats engine (`stats.pooled_endpoint_suite`) over EVERY
phenotype-pooled scalar family, on the pre-stroke-baseline-normalized Δ at
session grain, split by trial cue side, for the 3 post-vs-pre contrasts
(acute/sub_acute/chronic vs pre) and BOTH scopes (3_tier, 4_tier). BH-FDR within
family. Writes ONE consolidated sheet per scope:

    stats/results/phenotype_pooled/<scope>/pooled_phenotype_stats.csv

Families + per-session sources:
  - scalar    : stats/inputs/<ep>/<animal>.parquet (tongue/jaw + spout-behavior
                d_prime / first_lick_accuracy_all / ... ) -> per-session mean.
  - phase_aligned_endpoints : per-trial JSON via
                load_session_phase_aligned_endpoints_long -> per-session mean.
  - wasserstein / normalized_wasserstein : the persisted per-session W-2 CSV.

(Trajectories already carry the full suite incl. cluster permutation, which is
N/A for scalars. Per-trial MWU skipped per Priya.)

Usage::
  python scripts/phase_9_stats/build_pooled_phenotype_stats.py
  python scripts/phase_9_stats/build_pooled_phenotype_stats.py --families scalar
  python scripts/phase_9_stats/build_pooled_phenotype_stats.py --n-boot 5000
"""
from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.aggregators import (  # noqa: E402
    load_session_phase_aligned_endpoints_long,
)
from stroke_orofacial.stats.multiple_comparisons import (  # noqa: E402
    apply_correction_to_results_df,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("build_pooled_phenotype_stats")

PHENOTYPE_REMAP_3TIER = {"moderate-severe": "moderate"}
PHASE_ALIGNED_ENDPOINTS = (
    "peak_angle_deg",
    "signed_angle_at_max_abs_phase_0_075_deg",
    "signed_x_at_max_abs_phase_0_075_px",
)
# Behavior d'/criterion pool across cue sides -> can't split by cue side.
CROSS_CUE_ENDPOINTS = frozenset({"d_prime", "criterion_c"})


def _persession_from_pertrial(df: pd.DataFrame, endpoint: str) -> pd.DataFrame:
    """Per-(animal, date, side) mean of finite per-trial values."""
    if df.empty:
        return df
    if "is_sentinel" in df.columns:
        df = df[~df["is_sentinel"].astype(bool)]
    df = df.dropna(subset=["value"])
    g = (df.groupby(["animal", "date", "side"], as_index=False)
           .agg(value=("value", "mean"), epoch_label=("epoch_label", "first")))
    g["endpoint"] = endpoint
    return g


def load_scalar_family(resolver: PathResolver) -> pd.DataFrame:
    """All stats/inputs scalar endpoints -> per-session long-form."""
    inp = resolver.pipeline_outputs(subdir="stats") / "inputs"
    eps = sorted(
        d.name for d in inp.iterdir()
        if d.is_dir() and not d.name.startswith(("filtered", "_", "inputs"))
    )
    frames = []
    for ep in eps:
        pqs = glob.glob(str(inp / ep / "*.parquet"))
        if not pqs:
            continue
        df = pd.concat([pd.read_parquet(p) for p in pqs], ignore_index=True)
        if "epoch_label" not in df.columns or "value" not in df.columns:
            continue
        sess = _persession_from_pertrial(df, ep)
        if not sess.empty:
            sess["family"] = "scalar"
            frames.append(sess)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_phase_aligned_family(resolver: PathResolver, animals: list[str]) -> pd.DataFrame:
    """First-lick phase-aligned endpoints (per-trial JSON) -> per-session."""
    import datetime

    from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
    from stroke_orofacial.stats.recovery_epochs import assign_epoch_label
    amap = load_animals()
    rows = []
    for animal in animals:
        info = amap.get(animal)
        if info is None:
            continue
        for d in yaml_driven_session_dates(animal):
            if isinstance(d, str):
                d = datetime.date.fromisoformat(d)
            ep_long = load_session_phase_aligned_endpoints_long(animal, d, resolver)
            if ep_long.empty:
                continue
            # The JSON loader doesn't carry epoch_label; derive from rel_day.
            rel = int(info.day_relative_to_stroke(d))
            epoch = assign_epoch_label(rel, info)
            for ep in PHASE_ALIGNED_ENDPOINTS:
                sub = ep_long[ep_long["endpoint"] == ep]
                if sub.empty:
                    continue
                rows.append(_persession_from_pertrial(
                    sub.assign(is_sentinel=False, epoch_label=epoch), ep))
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out["family"] = "phase_aligned_endpoints"
    return out


def load_wasserstein_family(resolver: PathResolver) -> pd.DataFrame:
    """Persisted per-session W-2 (absolute + normalized) -> per-session long-form."""
    res = resolver.pipeline_outputs(subdir="stats") / "results" / "phenotype_pooled"
    frames = []
    for fam, sub in [("wasserstein_recovery", "wasserstein_recovery"),
                     ("normalized_wasserstein_recovery",
                      "normalized_wasserstein_recovery")]:
        for f in glob.glob(str(res / sub / "**" / "wasserstein_recovery_per_session.csv"),
                           recursive=True):
            df = pd.read_csv(f)
            if df.empty or "w2" not in df.columns:
                continue
            keep = df.rename(columns={"endpoint": "bodypart"})[
                ["animal", "date", "side", "bodypart", "epoch_label", "w2"]].copy()
            keep = keep.rename(columns={"w2": "value"})
            keep["endpoint"] = keep["bodypart"]
            keep["family"] = fam
            frames.append(keep.drop(columns=["bodypart"]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _attach_phenotype(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    amap = {a: i.recovery_phenotype for a, i in load_animals().items()}
    df = df.copy()
    df["recovery_phenotype"] = df["animal"].map(amap)
    df = df.dropna(subset=["recovery_phenotype"])
    if scope == "3_tier":
        df["recovery_phenotype"] = df["recovery_phenotype"].map(
            lambda p: PHENOTYPE_REMAP_3TIER.get(p, p))
    return df


def _run_family(long_df: pd.DataFrame, *, n_boot: int) -> pd.DataFrame:
    """Engine over every (family, endpoint, phenotype, side, post_epoch) cell."""
    out_rows: list[dict] = []
    for endpoint, ep_df in long_df.groupby("endpoint"):
        family = ep_df["family"].iloc[0]
        cross_cue = endpoint in CROSS_CUE_ENDPOINTS
        # Δ-from-pre per (animal, side) [or per animal if cross-cue].
        grp = ("animal",) if cross_cue else ("animal", "side")
        norm = SUITE.normalize_to_pre_baseline(ep_df, group_cols=grp, value_col="value")
        sides = ["both"] if cross_cue else sorted(
            s for s in norm["side"].dropna().unique())
        for side in sides:
            side_df = norm if cross_cue else norm[norm["side"] == side]
            for phen, phen_df in side_df.groupby("recovery_phenotype"):
                for post_epoch in SUITE.POST_EPOCHS:
                    if post_epoch not in set(phen_df["epoch_label"]):
                        continue
                    res = SUITE.compute_endpoint_cell_suite(
                        phen_df, post_epoch=post_epoch, value_col="value_norm",
                        n_boot=n_boot)
                    res.update({"family": family, "endpoint": endpoint,
                                "recovery_phenotype": phen, "side": side})
                    out_rows.append(res)
    return pd.DataFrame(out_rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--families", nargs="*",
                   default=["scalar", "phase_aligned_endpoints", "wasserstein"])
    p.add_argument("--n-boot", type=int, default=5000)
    p.add_argument("--scopes", nargs="*", default=["4_tier", "3_tier"])
    args = p.parse_args(argv)

    resolver = PathResolver()
    animals = sorted(load_animals().keys())

    base_long = []
    if "scalar" in args.families:
        log.info("loading scalar family ...")
        base_long.append(load_scalar_family(resolver))
    if "phase_aligned_endpoints" in args.families:
        log.info("loading phase_aligned family ...")
        base_long.append(load_phase_aligned_family(resolver, animals))
    if "wasserstein" in args.families:
        log.info("loading wasserstein family ...")
        base_long.append(load_wasserstein_family(resolver))
    base_long = [d for d in base_long if not d.empty]
    if not base_long:
        log.error("no family data loaded")
        return 1
    long_all = pd.concat(base_long, ignore_index=True)
    log.info("per-session rows: %d across %d endpoints",
             len(long_all), long_all["endpoint"].nunique())

    for scope in args.scopes:
        scoped = _attach_phenotype(long_all, scope)
        res = _run_family(scoped, n_boot=args.n_boot)
        if res.empty:
            log.warning("[%s] no results", scope)
            continue
        # BH-FDR within family, per test column.
        for pcol, adj in [("wilcoxon_p", "wilcoxon_p_fdr"),
                          ("mwu_session_p", "mwu_session_p_fdr"),
                          ("lmm_p", "lmm_p_fdr")]:
            res = res.rename(columns={pcol: "p_value"})
            res = apply_correction_to_results_df(res, group_cols=("family",))
            res = res.rename(columns={"p_value": pcol, "p_adj": adj})
            res = res.drop(columns=["reject"], errors="ignore")
        out_dir = (resolver.pipeline_outputs(subdir="stats") / "results"
                   / "phenotype_pooled" / scope)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "pooled_phenotype_stats.csv"
        res.to_csv(out_path, index=False)
        n_sig = int((res["lmm_p_fdr"] < 0.05).sum()) if "lmm_p_fdr" in res else 0
        log.info("[%s] %d rows (%d LMM-FDR-sig) -> %s",
                 scope, len(res), n_sig, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
