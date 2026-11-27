"""Two-tone cohort (PS46-PS55): cue-locked jaw-movement rate on no-lick trials, pseudo-cue method (CC-B 2026-11-27).

Mirrors the six-position test of SECTION_jaw3d_classes.md 9.3 / 10.3 (widefield scripts/jaw3d_floor_null.py +
jaw3d_fix_eval.pseudo) with the two-tone jaw call (`jaw_pertrial.jaw_onset_after_cue`, the adopted after-cue rule,
same threshold / density parameters as configs/defaults.yaml jaw_pertrial):

  pseudo1  a PSEUDO-CUE 1,000 ms before the tone: baseline -1,500 .. -1,000 ms, detect -1,000 .. 0 ms
  real1    the real tone: baseline -500 .. 0 ms, detect 0 .. 1,000 ms (same length as the null)
  pseudo5  a pseudo-cue 5,000 ms before the tone: baseline -5,500 .. -5,000 ms, detect -5,000 .. 0 ms
  real5    the class window: baseline -500 .. 0 ms, detect 0 .. 5,000 ms (= the Fig 2B jaw call)

Call per window = moved_after_cue (1 / 0; NaN = deflected at the window start and never settled and moved again =
unjudged, dropped from that window's rate, as the six-position "class-equivalent" call).
Exclusion (as six-position exclusion B): trials with a lick in the pre-cue span are dropped -- a DAQ spout contact OR a
DLC tongue-out frame (cleaned tongue trace, distance from the mouth > 0) in -1,500 .. 0 ms (1-s windows) or
-5,500 .. 0 ms (5-s windows). For the 5-s windows the previous tone must also be >= 10.5 s earlier, so the pseudo window
does not overlap the previous trial's 0-5 s response window.
Trial sets: "no_lick" = live Fig 2B classes jaw_only or no_resp before the jaw re-split (no spout contact 0-5 s, no
tongue 70-5,000 ms; = the six-position "jaw-decided" set); "lick_free_all" = every trial passing the exclusion
(licks after the cue allowed; reference only).

Classes / epochs / grades: stats/results/trial_outcomes/c1_trial_classes.csv (the Fig 2B table). Cue side R =
contralesional. Also writes the interval from the previous tone for every trial (ITI check).

Writes (refuses to overwrite) <out>/: pseudo_cue_trials_ccB1127.csv.gz (one row per trial x window),
iti_check_ccB1127.csv, and summary tables pseudo_cue_*_ccB1127.csv.
Usage: PYTHONPATH=<worktree>/src MKL_THREADING_LAYER=SEQUENTIAL python c1_jaw_pseudo_cue_ccB1127.py --out DIR [--jobs 3]
"""
from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

SO = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs")
DLC = SO / "dlc_kinematics"
CLS = SO / "stats/results/trial_outcomes/c1_trial_classes.csv"
LABEL = {"PS47": "#1", "PS48": "#2", "PS49": "#3", "PS50": "#4", "PS46": "#5", "PS51": "#6", "PS54": "#7", "PS55": "#8"}
# window: (pseudo-cue shift in s before the tone, detect length ms, pre-cue lick-exclusion span s, min prev-tone gap s)
WINDOWS = {"pseudo1": (1.0, 1000, 1.5, 0.0), "real1": (0.0, 1000, 1.5, 0.0),
           "pseudo5": (5.0, 5000, 5.5, 10.5), "real5": (0.0, 5000, 5.5, 10.5)}


def session_job(args) -> pd.DataFrame | None:
    animal, date = args
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP
    cf = DLC / f"tongue_jaw_mismatch/candidate_trials/{animal}/{date}.parquet"
    jf, tf = DLC / f"cleaned_traces/jaw/{animal}/{date}.parquet", DLC / f"cleaned_traces/tongue/{animal}/{date}.parquet"
    nz = SO / f"spout_behavior/licks_and_rewards/{animal}/{date}.npz"
    if not (cf.exists() and jf.exists() and tf.exists() and nz.exists()):
        return None
    jp = load_defaults()["dlc_kinematics"]["jaw_pertrial"]
    kw = dict(baseline_win_ms=tuple(jp["baseline_win_ms"]), sd_mult=float(jp["deflection_threshold_sd_multiplier"]),
              min_px=float(jp["deflection_threshold_min_px"]), density_thr=float(jp["sustained_density_threshold"]),
              window_n=int(jp["sustained_window_n_frames"]))
    assert tuple(jp["baseline_win_ms"]) == (-500, 0)
    jy = pd.read_parquet(jf, columns=["y_final"]).y_final.to_numpy(float)
    tg = pd.read_parquet(tf, columns=["x_final", "y_final"])
    tout = np.hypot(tg.x_final.to_numpy(float), tg.y_final.to_numpy(float)) > 0      # NaN -> False
    ctout = np.concatenate([[0], np.cumsum(tout)])
    z = np.load(nz, allow_pickle=True)
    fs = float(z["Fs"])
    tones = np.sort(np.concatenate([z["Tone_R"], z["Tone_L"]]).astype(float))
    licks = np.sort(np.concatenate([z["Lick_R"], z["Lick_L"]]).astype(float))
    C = pd.read_parquet(cf, columns=["trial_index", "side", "tone_frame_idx", "fps"])
    if len(C) != len(tones):
        return None
    rows = []
    for r in C.itertuples():
        fps, c, ti = float(r.fps), int(r.tone_frame_idx), int(r.trial_index)
        t_ws = tones[ti]
        prev_gap = (t_ws - tones[ti - 1]) / fs if ti > 0 else np.inf
        for w, (shift, det, excl, gap) in WINDOWS.items():
            c0 = c - int(round(shift * fps))
            e0 = c - int(round(excl * fps))
            if e0 < 0 or c + int(det / 1000 * fps) >= len(jy):
                continue
            daq_pre = bool(((licks >= t_ws - excl * fs) & (licks < t_ws)).any())
            dlc_pre = bool(ctout[c] - ctout[e0] > 0)
            o = JP.jaw_onset_after_cue(jy, fps, c0, detect_win_ms=(0, det), **kw)
            rows.append(dict(animal=animal, date=date, trial=ti, cue_side=r.side, window=w, prev_tone_gap_s=prev_gap,
                             gap_ok=prev_gap >= gap, daq_lick_pre=daq_pre, dlc_tongue_pre=dlc_pre,
                             call=o["moved_after_cue"], onset_ms=o["onset_ms"]))
    return pd.DataFrame(rows)


def rates(D: pd.DataFrame, keys: list[str], pair=("pseudo1", "real1")) -> pd.DataFrame:
    """Per-key judged rate in each window of the pair (NaN calls dropped per window), excess = real - pseudo."""
    D = D[D.window.isin(pair)]
    g = D.groupby(keys + ["window"]).call
    R = pd.concat([g.mean().rename("rate"), g.count().rename("n")], axis=1).unstack("window")
    R.columns = [f"{a}_{b}" for a, b in R.columns]
    R["excess"] = R[f"rate_{pair[1]}"] - R[f"rate_{pair[0]}"]
    return R.reset_index()


def animal_mean(R: pd.DataFrame, keys: list[str], pair) -> pd.DataFrame:
    """Mean over animals of the per-animal rates (each animal weighted equally), with the count of positive excesses."""
    cols = [f"rate_{pair[0]}", f"rate_{pair[1]}", "excess"]
    g = R.groupby(keys) if keys else R.assign(_all="all").groupby("_all")
    out = g[cols].mean()
    out["n_animals"] = g.excess.count()
    out["n_animals_positive"] = g.excess.apply(lambda s: int((s > 0).sum()))
    return out.reset_index()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    tr_path = a.out / "pseudo_cue_trials_ccB1127.csv.gz"
    if tr_path.exists():
        sys.exit(f"refusing to overwrite {tr_path}")
    K = pd.read_csv(CLS, dtype={"date": str})
    sess = sorted(K[["animal", "date"]].drop_duplicates().itertuples(index=False, name=None))
    with Pool(a.jobs) as p:
        res = p.map(session_job, sess, chunksize=1)
    T = pd.concat([r for r in res if r is not None], ignore_index=True)
    T = T.merge(K[["animal", "date", "trial", "cls", "epoch", "side", "grp"]], on=["animal", "date", "trial"],
                how="inner", validate="many_to_one")
    T["lick_pre"] = T.daq_lick_pre | T.dlc_tongue_pre
    T["no_lick"] = T.cls.isin(["jaw_only", "no_resp"])
    T.to_csv(tr_path, index=False)
    print(f"sessions {T[['animal', 'date']].drop_duplicates().shape[0]} of {len(sess)}, trials {T.groupby(['animal', 'date', 'trial']).ngroups}")

    # ITI check: interval from the previous tone, and where -1.5 .. 0 s falls
    one = T[T.window == "real1"]
    it = one.groupby("animal").prev_tone_gap_s.describe(percentiles=[0.01, 0.5])
    it["min_all"] = one.groupby("animal").prev_tone_gap_s.min()
    it.reset_index().to_csv(a.out / "iti_check_ccB1127.csv", index=False)
    print("previous-tone gap (s): min", round(one.prev_tone_gap_s.min(), 2), "1st pct",
          round(one.prev_tone_gap_s.quantile(0.01), 2))

    tables = {}
    for setn, sel in (("no_lick", lambda d: d.no_lick), ("lick_free_all", lambda d: d.cls.notna())):
        for pair, tag in ((("pseudo1", "real1"), "1s"), (("pseudo5", "real5"), "5s")):
            D = T[sel(T) & ~T.lick_pre & T.gap_ok & T.window.isin(pair)]
            pa = rates(D, ["animal"], pair)
            pa_side = rates(D, ["animal", "side"], pair)
            pa_side_ep = rates(D, ["animal", "side", "epoch"], pair)
            pa_ep = rates(D, ["animal", "epoch"], pair)
            pooled_trials = rates(D.assign(_all="all"), ["_all"], pair)
            pooled_trials_side = rates(D, ["side"], pair)
            pooled_trials_grp = rates(D, ["grp", "side", "epoch"], pair)
            am = animal_mean(pa, [], pair)
            am_side = animal_mean(pa_side, ["side"], pair)
            am_ep = animal_mean(pa_ep, ["epoch"], pair)
            Dpp = D.assign(prepost=np.where(D.epoch == "pre", "pre", "post"))
            pa_pp = rates(Dpp, ["animal", "prepost"], pair)
            am_pp = animal_mean(pa_pp, ["prepost"], pair)
            for k, v in dict(per_animal=pa, per_animal_side=pa_side, per_animal_epoch=pa_ep,
                             per_animal_side_epoch=pa_side_ep, per_animal_prepost=pa_pp,
                             pooled_trials=pooled_trials, pooled_trials_side=pooled_trials_side,
                             pooled_trials_grade_side_epoch=pooled_trials_grp, animal_mean=am,
                             animal_mean_side=am_side, animal_mean_epoch=am_ep, animal_mean_prepost=am_pp).items():
                if "animal" in v.columns:
                    v.insert(1, "ms_id", v.animal.map(LABEL))
                tables[f"{setn}_{tag}_{k}"] = v
    for k, v in tables.items():
        p = a.out / f"pseudo_cue_{k}_ccB1127.csv"
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
        v.round(4).to_csv(p, index=False)
    for k in ("no_lick_1s_animal_mean", "no_lick_1s_per_animal", "no_lick_5s_animal_mean", "no_lick_1s_animal_mean_side"):
        print(k)
        print(tables[k].round(3).to_string(index=False))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
