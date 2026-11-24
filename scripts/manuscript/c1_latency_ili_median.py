"""Two-tone times as session MEDIANS (caption review items 29 + 34, CC-B 2026-11-23).

Priya's rule (item 34a): times (first-lick latency, first-correct-lick latency, inter-lick interval) = session MEDIAN
over trials; per-lick sizes / directions = session mean over licks (done by the other helper); proportions unchanged.
Item 29: one inter-lick-interval definition for both cohorts = the median within-bout interval per session, a
within-bout interval being the interval between consecutive licks of the same trial that is <= 300 ms.

Two-tone session values that change (all were the session MEAN of per-trial values in
build_pooled_phenotype_stats._persession_from_pertrial, or ms_lat[side]["mean"] in materialize_inputs):
  latency_to_first_correct_lick_s (Fig 1G)  -> latency_to_first_correct_lick_s_sessmedian: median over trials with a
      correct lick of the per-trial first-correct-lick latency (stats/inputs/no_filter/latency_hist, the per-trial
      values whose session mean IS the old endpoint; checked);
  tongue_first_peak_t_ms (Fig 2C), tongue_lick1_t_peak_ms, tongue_lick2_t_peak_ms -> *_sessmedian: median over the
      same filtered_v1 trials;
  tongue_mean_within_bout_ili_ms (S6A; per trial the mean ILI inside the FIRST multi-lick bout of [70, 5000] ms, valid
      80-300 ms, >= 3 licks in the bout; session mean) -> tongue_sessmedian_within_bout_ili_ms: every interval between
      consecutive v7-kept lick peaks of the same trial (dlc_kinematics/lick_events/tongue, peaks 70-3000 ms after the
      cue = the all-lick window of Fig 2D/2E) that is <= 300 ms, pooled over the session x cue side's trials (the
      filtered_v1 trial set of Fig 2D), median; >= MIN_INTERVALS intervals per session x side.
Stats unchanged (pooled_endpoint_suite c2_aligned, via c1_sessmean_scalars.run_cells); the new cells REPLACE the old
ones in the final 518-cell scalar family (pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv), BH within it.
--check reproduces the old cells from the per-trial values with the mean (exact).

Writes (new only):
  stats/results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian.csv
  stats/inputs/sessmedian_times/<endpoint>_per_session.csv
  <tables>/c1_times_median_old_vs_new.csv
Usage: python scripts/manuscript/c1_latency_ili_median.py <tables_out_dir> [--check]
"""
from __future__ import annotations

import datetime
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import kept_trials, run_cells  # noqa: E402

MIN_INTERVALS = 5
ILI_MAX_MS = 300.0
FAMILY = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123"
OUT_SHEET = FAMILY + "_timesmedian"
TRIAL_TIMES = ("tongue_first_peak_t_ms", "tongue_lick1_t_peak_ms", "tongue_lick2_t_peak_ms")
NEW = {"latency_to_first_correct_lick_s": "latency_to_first_correct_lick_s_sessmedian",
       **{s: s + "_sessmedian" for s in TRIAL_TIMES},
       "tongue_mean_within_bout_ili_ms": "tongue_sessmedian_within_bout_ili_ms"}
KEY = ["recovery_phenotype", "side", "post_epoch"]


def _sess(df: pd.DataFrame, how: str) -> pd.DataFrame:
    return df.groupby(["animal", "date", "side"], as_index=False).agg(
        value=("value", how), n=("value", "size"), epoch_label=("epoch_label", "first"))


def spout_latency_trials(r: PathResolver) -> pd.DataFrame:
    """Per-trial first-correct-lick latency (s) of the sessions that carry the old session endpoint."""
    nf = r.pipeline_outputs(subdir="stats") / "inputs" / "no_filter"
    h = pd.concat([pd.read_parquet(p) for p in glob.glob(str(nf / "latency_hist" / "*.parquet"))], ignore_index=True)
    h = h[~h.is_sentinel.astype(bool)].dropna(subset=["value"])
    s = pd.concat([pd.read_parquet(p) for p in glob.glob(str(nf / "latency_to_first_correct_lick_s" / "*.parquet"))],
                  ignore_index=True)
    s = s[~s.is_sentinel.astype(bool)].dropna(subset=["value"])
    for d in (h, s):
        d["date"] = pd.to_datetime(d["date"]).dt.date
    keep = set(zip(s.animal, s.date, s.side))
    h = h[[k in keep for k in zip(h.animal, h.date, h.side)]]
    # the per-trial rows must carry the session's epoch label of the session endpoint
    return h, s


def ili_per_interval(r: PathResolver) -> pd.DataFrame:
    """Every within-trial interval between consecutive kept lick peaks (70-3000 ms), trials of the Fig 2D set."""
    t = kept_trials(r, "tongue_median_xy_peak_per_trial")
    out = []
    for (animal, date), tr in t.groupby(["animal", "date"]):
        d = date if isinstance(date, datetime.date) else pd.Timestamp(date).date()
        le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                             / f"{d.strftime('%Y%m%d')}.parquet", columns=["trial", "side", "t_ms"])
        keep = tr[["trial_idx", "side", "epoch_label"]].drop_duplicates().rename(columns={"trial_idx": "trial"})
        keep["trial"] = keep["trial"].astype(int)
        le["trial"] = le["trial"].astype(int)
        le = le.merge(keep, on=["trial", "side"], how="inner").sort_values(["side", "trial", "t_ms"])
        le["ili"] = le.groupby(["side", "trial"]).t_ms.diff()
        iv = le.dropna(subset=["ili"])
        out.append(iv.assign(animal=animal, date=d)[["animal", "date", "side", "trial", "ili", "epoch_label"]])
    return pd.concat(out, ignore_index=True)


def main() -> int:
    tables = Path(sys.argv[1])
    check = "--check" in sys.argv
    r = PathResolver()
    st = r.pipeline_outputs(subdir="stats")
    r3 = st / "results" / "phenotype_pooled" / "3_tier"
    fam_all = pd.read_csv(r3 / f"{FAMILY}.csv")
    fam = fam_all[fam_all.family == "scalar"]
    out_csv = r3 / f"{OUT_SHEET}.csv"
    sdir = st / "inputs" / "sessmedian_times"
    if not check and out_csv.exists():
        sys.exit(f"refusing to overwrite {out_csv}")

    h, s_old = spout_latency_trials(r)
    trial_frames = {"latency_to_first_correct_lick_s": h}
    for slug in TRIAL_TIMES:
        trial_frames[slug] = kept_trials(r, slug)

    if check:
        for slug, tr in trial_frames.items():
            new = run_cells(_sess(tr, "mean").assign(endpoint=slug), "scalar")
            m = new.merge(fam[fam.endpoint == slug], on=KEY, suffixes=("", "_old"))
            print(slug, len(new), "/", int((fam.endpoint == slug).sum()), "cells; max|dp|",
                  np.nanmax(np.abs(m.mwu_session_p - m.mwu_session_p_old)), "max|d eff|",
                  np.nanmax(np.abs(m.nb_effect - m.nb_effect_old)))
        return 0

    sdir.mkdir(parents=True, exist_ok=True)
    sess = []
    for slug, tr in trial_frames.items():
        s = _sess(tr, "median").assign(endpoint=NEW[slug])
        sess.append(s)
    iv = ili_per_interval(r)
    n_all = len(iv)
    wb = iv[iv.ili <= ILI_MAX_MS]
    print(f"ILI: {n_all} within-trial intervals, {len(wb)} <= {ILI_MAX_MS:g} ms, {int((wb.ili < 80).sum())} < 80 ms")
    s = wb.groupby(["animal", "date", "side"], as_index=False).agg(value=("ili", "median"), n=("ili", "size"),
                                                                   epoch_label=("epoch_label", "first"))
    s["passes_min"] = s.n >= MIN_INTERVALS
    print("ILI sessions x side", len(s), "excluded by min", int((~s.passes_min).sum()), "median/min intervals",
          s.n.median(), s.n.min())
    sess.append(s[s.passes_min].drop(columns="passes_min").assign(endpoint=NEW["tongue_mean_within_bout_ili_ms"]))
    for x in sess:
        x.to_csv(sdir / f"{x.endpoint.iloc[0]}_per_session.csv", index=False)
    S = pd.concat(sess, ignore_index=True)
    cells = run_cells(S[["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
    cols = list(cells.columns)
    keep = fam[~fam.endpoint.isin(list(NEW))]
    merged = pd.concat([keep[cols], cells[cols]], ignore_index=True)
    assert len(merged) == len(fam), (len(merged), len(fam))
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        merged = merged.rename(columns={pcol: "p_value"})
        merged = apply_correction_to_results_df(merged, group_cols=("family",))
        merged = merged.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    merged["headline_test"] = "mwu_session+nested_bootstrap"
    merged["headline_p_fdr"] = merged["mwu_session_p_fdr"]
    merged["headline_sig"] = merged["headline_p_fdr"] < 0.05
    merged["headline_and_bootstrap_sig"] = merged["headline_sig"] & merged["nb_excludes_zero"].astype(bool)
    pd.concat([merged, fam_all[fam_all.family != "scalar"]], ignore_index=True).to_csv(out_csv, index=False)
    print("wrote", out_csv, len(merged), "scalar cells")

    c = ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "headline_and_bootstrap_sig", "n_pre_sessions",
         "n_post_sessions"]
    inv = {v: k for k, v in NEW.items()}
    f = merged.assign(old_endpoint=merged.endpoint.map(inv).fillna(merged.endpoint))
    m = f[["endpoint", "old_endpoint"] + KEY + c].merge(
        fam[["endpoint"] + KEY + c].rename(columns={"endpoint": "old_endpoint"}), on=["old_endpoint"] + KEY,
        how="left", suffixes=("", "_old"))
    m["change"] = np.where(m.headline_and_bootstrap_sig & ~m.headline_and_bootstrap_sig_old.astype(bool), "GAINED",
                  np.where(~m.headline_and_bootstrap_sig & m.headline_and_bootstrap_sig_old.astype(bool), "LOST", ""))
    tables.mkdir(parents=True, exist_ok=True)
    m.to_csv(tables / "c1_times_median_old_vs_new.csv", index=False)
    pd.set_option("display.width", 260)
    ch = m[m.old_endpoint.isin(list(NEW))]
    print(ch[["old_endpoint"] + KEY + ["nb_effect_old", "nb_ci_lo_old", "nb_ci_hi_old", "mwu_session_p_fdr_old",
                                         "headline_and_bootstrap_sig_old", "nb_effect", "nb_ci_lo", "nb_ci_hi",
                                         "mwu_session_p_fdr", "headline_and_bootstrap_sig", "change"]]
          .round(4).to_string(index=False))
    o = m[~m.old_endpoint.isin(list(NEW))]
    print("other cells changing star:", o[o.change != ""][["endpoint"] + KEY + ["change"]].to_string(index=False))
    print("stars old", int(m.headline_and_bootstrap_sig_old.astype(bool).sum()), "new",
          int(m.headline_and_bootstrap_sig.sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
