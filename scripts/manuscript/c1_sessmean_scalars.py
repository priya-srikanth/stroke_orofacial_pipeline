"""Two-tone all-lick scalars as the SESSION MEAN over licks + merged scalar family (CC-B, 2026-11-23,
caption review items 19 and 20).

Item 19. Fig 2D (peak protrusion, xy, all licks) and Fig 2E (peak tongue speed, all licks) were the session
mean of PER-TRIAL MEDIANS over each trial's licks (materialize_inputs: tongue_median_xy_peak_per_trial,
tongue_median_vxy_peak_per_trial). Here each becomes the plain mean over every lick of the session x cue side,
with the SAME lick set and the SAME trials:
  - trials: the non-sentinel rows of stats/inputs/filtered_v1/<old slug>/<animal>.parquet (DLC trial + session
    filter, epoch labels of the ps47d5 run);
  - xy: every v7-kept lick of those trials in the [70, 3000] ms window, hypot(x, y) at the lick's Y-peak
    (dlc_kinematics/lick_events/tongue/<animal>/<date>.parquet), as _median_xy_per_trial;
  - speed: the per-lick vxy peaks of those trials (per-trial JSON peak_velocity_per_lick.vxy_peaks_bylick),
    which hold licks 1-5 of each trial (the vector is capped at five), as the old median used.
Minimum-lick rule (six-position): a session x side enters only with >= MIN_LICKS licks.

Item 20. The xy pair (first-lick tongue_lick1_xy_peak, S6D; all-lick, Fig 2D) joins the single two-tone scalar
BH family instead of its own two-endpoint family.

Stats are those of build_pooled_phenotype_stats --test-set c2_aligned: change from the animal's pre mean per
cue side, session MWU, nested animals -> sessions bootstrap (pooled_endpoint_suite, seed 0), BH within family;
star = q < 0.05 AND bootstrap CI excludes 0. Unchanged cells are copied from the ps47d5 sheets (their MWU p and
seeded bootstrap are deterministic; checked by recomputing the old Fig 2E cells, see --check), so only the
family membership changes their q.

Writes NEW files only (refuses to overwrite):
  <stats>/results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv
  <stats>/inputs/sessmean_licks/<slug>_per_session.csv   (per-session values + lick counts)
Usage: python scripts/manuscript/c1_sessmean_scalars.py [--check]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402

MIN_LICKS = 5
OLD2NEW = {"tongue_median_xy_peak_per_trial": "tongue_sessmean_xy_peak",
           "tongue_median_vxy_peak_per_trial": "tongue_sessmean_vxy_peak"}
SHEET = "pooled_phenotype_stats_c2aligned_v3_ps47d5"
XY_SHEET = "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5"
OUT_SHEET = SHEET + "_sessmean"
REMAP3 = {"moderate-severe": "moderate"}


def kept_trials(r: PathResolver, slug: str) -> pd.DataFrame:
    src = r.pipeline_outputs(subdir="stats") / "inputs" / "filtered_v1" / slug
    df = pd.concat([pd.read_parquet(p) for p in sorted(src.glob("*.parquet"))], ignore_index=True)
    return df[~df["is_sentinel"].astype(bool)].dropna(subset=["value"])


def per_lick(r: PathResolver, slug: str, trials: pd.DataFrame) -> pd.DataFrame:
    """One row per lick of the kept trials: animal, date, side, trial_idx, epoch_label, value."""
    out = []
    for (animal, date), tr in trials.groupby(["animal", "date"]):
        d = date if isinstance(date, datetime.date) else pd.Timestamp(date).date()
        lab = d.strftime("%Y%m%d")
        keep = set(zip(tr["trial_idx"].astype(int), tr["side"]))
        ep = tr["epoch_label"].iloc[0]
        if slug == "tongue_median_xy_peak_per_trial":
            le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                                 / f"{lab}.parquet", columns=["trial", "side", "x", "y"])
            v = np.hypot(le["x"].to_numpy(float), le["y"].to_numpy(float))
            rows = pd.DataFrame({"trial_idx": le["trial"].astype(int).to_numpy(), "side": le["side"].to_numpy(),
                                 "value": v})
        else:
            J = json.load(open(r.tongue_pertrial_endpoints_json(animal, d), encoding="utf-8"))
            vec = J["tongue"]["peak_velocity_per_lick"]["vxy_peaks_bylick"]
            recs = [(int(ti), s, float(x)) for ti, s, vv in zip(J["trial_indices"], J["sides"], vec)
                    for x in (vv or []) if x is not None]
            rows = pd.DataFrame(recs, columns=["trial_idx", "side", "value"])
        rows = rows[np.isfinite(rows["value"])]
        rows = rows[[k in keep for k in zip(rows["trial_idx"], rows["side"])]]
        rows = rows.assign(animal=animal, date=d, epoch_label=ep)
        out.append(rows)
    return pd.concat(out, ignore_index=True)


def run_cells(long_df: pd.DataFrame, family: str) -> pd.DataFrame:
    """Same engine as build_pooled_phenotype_stats._run_family (c2_aligned, 3_tier)."""
    amap = {a: i.recovery_phenotype for a, i in load_animals().items()}
    df = long_df.assign(recovery_phenotype=long_df["animal"].map(amap).map(lambda p: REMAP3.get(p, p)))
    rows = []
    for ep, ep_df in df.groupby("endpoint"):
        norm = SUITE.normalize_to_pre_baseline(ep_df, group_cols=("animal", "side"), value_col="value")
        for side in sorted(norm["side"].dropna().unique()):
            for phen, ph in norm[norm["side"] == side].groupby("recovery_phenotype"):
                for post in SUITE.POST_EPOCHS:
                    if post not in set(ph["epoch_label"]):
                        continue
                    res = SUITE.compute_endpoint_cell_suite(ph, post_epoch=post, value_col="value_norm",
                                                            test_set="c2_aligned", within_animal=True)
                    res.update({"family": family, "endpoint": ep, "recovery_phenotype": phen, "side": side})
                    rows.append(res)
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="recompute the OLD Fig 2E/2D cells and compare")
    a = ap.parse_args(argv)
    r = PathResolver()
    st = r.pipeline_outputs(subdir="stats")
    r3 = st / "results" / "phenotype_pooled" / "3_tier"
    sheet = pd.read_csv(r3 / f"{SHEET}.csv")
    xys = pd.read_csv(r3 / f"{XY_SHEET}.csv")
    key = ["endpoint", "recovery_phenotype", "side", "post_epoch"]

    if a.check:   # reproduce the old cells from the per-trial values (session mean of per-trial medians)
        for slug, sh in (("tongue_median_vxy_peak_per_trial", sheet), ("tongue_median_xy_peak_per_trial", xys)):
            t = kept_trials(r, slug)
            s = t.groupby(["animal", "date", "side"], as_index=False).agg(value=("value", "mean"),
                                                                          epoch_label=("epoch_label", "first"))
            new = run_cells(s.assign(endpoint=slug), "scalar")
            m = new.merge(sh[sh.endpoint == slug], on=key, suffixes=("", "_old"))
            print(slug, len(new), "cells; max |dp|", np.nanmax(np.abs(m.mwu_session_p - m.mwu_session_p_old)),
                  "max |d effect|", np.nanmax(np.abs(m.nb_effect - m.nb_effect_old)),
                  "max |d ci|", np.nanmax(np.abs(m.nb_ci_lo - m.nb_ci_lo_old)))
        return 0

    out_csv = r3 / f"{OUT_SHEET}.csv"
    sess_dir = st / "inputs" / "sessmean_licks"
    if out_csv.exists():
        raise SystemExit(f"refusing to overwrite {out_csv}")
    sess_dir.mkdir(parents=True, exist_ok=True)
    long_new, excl = [], []
    for old, new in OLD2NEW.items():
        t = kept_trials(r, old)
        lk = per_lick(r, old, t)
        s = lk.groupby(["animal", "date", "side"], as_index=False).agg(
            value=("value", "mean"), n_licks=("value", "size"), n_trials=("trial_idx", "nunique"),
            epoch_label=("epoch_label", "first"))
        s["endpoint"] = new
        s["passes_min_licks"] = s["n_licks"] >= MIN_LICKS
        p = sess_dir / f"{new}_per_session.csv"
        if p.exists():
            raise SystemExit(f"refusing to overwrite {p}")
        s.to_csv(p, index=False)
        excl.append({"endpoint": new, "sessions": len(s), "excluded_sessions": int((~s.passes_min_licks).sum()),
                     "licks": int(s.n_licks.sum()), "excluded_licks": int(s.loc[~s.passes_min_licks, "n_licks"].sum()),
                     "licks_per_session_median": float(s.n_licks.median()), "licks_per_session_min": int(s.n_licks.min())})
        long_new.append(s[s.passes_min_licks])
    print(pd.DataFrame(excl).to_string())
    pd.DataFrame(excl).to_csv(sess_dir / "min_lick_exclusions.csv", index=False)
    new_cells = run_cells(pd.concat(long_new, ignore_index=True)[["animal", "date", "side", "value", "epoch_label",
                                                                   "endpoint"]], "scalar")
    # Merged family: the old scalar family minus the old all-lick speed, plus the first-lick xy cells (copied),
    # plus the two session-mean cells sets.
    fam = sheet[(sheet.family == "scalar") & (sheet.endpoint != "tongue_median_vxy_peak_per_trial")]
    xy1 = xys[xys.endpoint == "tongue_lick1_xy_peak"]
    cols = [c for c in new_cells.columns]
    merged = pd.concat([fam[cols], xy1[cols], new_cells[cols]], ignore_index=True)
    merged = merged.rename(columns={"mwu_session_p": "p_value"})
    merged = apply_correction_to_results_df(merged, group_cols=("family",))
    merged = merged.rename(columns={"p_value": "mwu_session_p", "p_adj": "mwu_session_p_fdr"}).drop(columns=["reject"])
    merged["headline_test"] = "mwu_session+nested_bootstrap"
    merged["headline_p_fdr"] = merged["mwu_session_p_fdr"]
    merged["headline_sig"] = merged["headline_p_fdr"] < 0.05
    merged["headline_and_bootstrap_sig"] = merged["headline_sig"] & merged["nb_excludes_zero"].astype(bool)
    # within-animal permutation (sensitivity column only) re-corrected over the merged family
    merged = merged.rename(columns={"wa_p": "p_value"})
    merged = apply_correction_to_results_df(merged, group_cols=("family",))
    merged = merged.rename(columns={"p_value": "wa_p", "p_adj": "wa_p_fdr"}).drop(columns=["reject"])
    others = sheet[sheet.family != "scalar"]
    pd.concat([merged, others], ignore_index=True).to_csv(out_csv, index=False)
    print("wrote", out_csv, len(merged), "scalar-family cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
