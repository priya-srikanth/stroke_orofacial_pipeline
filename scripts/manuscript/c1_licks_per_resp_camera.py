"""Two-tone camera-detected licks per responded trial (caption review item 30, CC-B 2026-11-23).

The two-tone family has camera lick COUNTS only per trial over ALL trials (tongue_num_correct_licks_dlc /
tongue_num_incorrect_licks_dlc: zero-lick trials included) and the spout-contact counts of Fig 1F; no count per
RESPONDED trial. Here, as six-position S10D (fourcam_lick_metrics: mean number of post-cue licks over trials with
>= 1 post-cue lick, licks from 70 ms after the cue):
  per trial = tongue_n_licks (per-trial JSON n_licks_family.n_licks: every v7-kept camera lick, either spout, peaks in
              the production lick-count window 70-5000 ms after the cue), stats/inputs/filtered_v1/tongue_n_licks;
  responded = >= 1 such lick; session value = mean over responded trials (a count: mean, as six-position).
Added to the scalar family of `--family` (BH over the whole family, star rule unchanged).

Writes (new only): <stats>/inputs/sessmedian_times/tongue_n_licks_per_responded_trial_per_session.csv,
<stats>/results/phenotype_pooled/3_tier/<family>_lpr.csv, <tables>/c1_licks_per_resp_cells.csv
Usage: python scripts/manuscript/c1_licks_per_resp_camera.py <tables_out_dir> [--family NAME]
"""
from __future__ import annotations

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

EP = "tongue_n_licks_per_responded_trial"


def main() -> int:
    tables = Path(sys.argv[1])
    famname = sys.argv[sys.argv.index("--family") + 1] if "--family" in sys.argv else \
        "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian"
    r = PathResolver()
    st = r.pipeline_outputs(subdir="stats")
    r3 = st / "results" / "phenotype_pooled" / "3_tier"
    out_csv = r3 / f"{famname}_lpr.csv"
    sess_csv = st / "inputs" / "sessmedian_times" / f"{EP}_per_session.csv"
    for p in (out_csv, sess_csv):
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
    t = kept_trials(r, "tongue_n_licks")
    resp = t[t.value >= 1]
    s = resp.groupby(["animal", "date", "side"], as_index=False).agg(
        value=("value", "mean"), n_resp_trials=("value", "size"), epoch_label=("epoch_label", "first"))
    tot = t.groupby(["animal", "date", "side"]).size().rename("n_trials").reset_index()
    s = s.merge(tot, on=["animal", "date", "side"])
    s["endpoint"] = EP
    s.to_csv(sess_csv, index=False)
    print("sessions x side", len(s), "responded trials", int(s.n_resp_trials.sum()), "of", int(s.n_trials.sum()),
          "; min responded per session x side", s.n_resp_trials.min())
    cells = run_cells(s[["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
    fam_all = pd.read_csv(r3 / f"{famname}.csv")
    fam = fam_all[fam_all.family == "scalar"]
    cols = list(cells.columns)
    merged = pd.concat([fam[cols], cells[cols]], ignore_index=True)
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        merged = merged.rename(columns={pcol: "p_value"})
        merged = apply_correction_to_results_df(merged, group_cols=("family",))
        merged = merged.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    merged["headline_test"] = "mwu_session+nested_bootstrap"
    merged["headline_p_fdr"] = merged["mwu_session_p_fdr"]
    merged["headline_sig"] = merged["headline_p_fdr"] < 0.05
    merged["headline_and_bootstrap_sig"] = merged["headline_sig"] & merged["nb_excludes_zero"].astype(bool)
    pd.concat([merged, fam_all[fam_all.family != "scalar"]], ignore_index=True).to_csv(out_csv, index=False)
    k = ["endpoint", "recovery_phenotype", "side", "post_epoch"]
    old = fam.set_index(k).headline_and_bootstrap_sig
    new = merged.set_index(k).headline_and_bootstrap_sig
    flips = new.reindex(old.index) != old
    print("family", len(fam), "->", len(merged), "cells; other cells changing star:", int(flips.sum()))
    if flips.any():
        print(old[flips])
    c = merged[merged.endpoint == EP][k[1:] + ["n_pre_sessions", "n_post_sessions", "nb_effect", "nb_ci_lo", "nb_ci_hi",
                                              "mwu_session_p_fdr", "headline_and_bootstrap_sig"]]
    # pre-stroke level per grade x side (session mean, for context)
    pre = s[s.epoch_label == "pre"].groupby("side").value.mean()
    tables.mkdir(parents=True, exist_ok=True)
    c.to_csv(tables / "c1_licks_per_resp_cells.csv", index=False)
    pd.set_option("display.width", 220)
    print(c.round(4).to_string(index=False))
    print("pre-stroke licks per responded trial, mean of sessions, by cue side:\n", pre.round(2).to_string())
    print("wrote", out_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
