"""Two-tone cohort (PS46-PS55): blind video review set for jaw-only trials (CC-B 2026-11-27; prompt
vls_stroke_paper/PROMPT_CC_B_twotone_blind_jaw_review_2026-11-27.md, Priya approved).

  select  draws the sample (fixed seed) and writes the KEY (outside the clip folder) + a blind scoring sheet
  clips   cuts the blind clips from the raw four-camera videos (read only) for every key row

Trials and classes: the LIVE Fig 2B table = stats/results/trial_outcomes/c1_trial_classes.csv with jaw_only / no_resp
re-split by `jaw_only_v2` of dlc_kinematics/tongue_jaw_mismatch/jaw_onset_after_cue/c1_jaw_onset_trials.parquet
(`trial_outcomes.override_jaw_only`, exactly as the jawv2 distribution test behind Fig 2B; unknown = dropped). The jaw
call is `jaw_pertrial.jaw_onset_after_cue` (onset 0-5,000 ms after the tone, re-onset after an at-cue deflection).

Strata (post-stroke trials only; contralesional = cue side R):
  J_sev_mod_contra  jaw_only, PS51 / PS54 / PS55, acute + subacute, cue R      8
  J_sev_mod_ipsi    jaw_only, PS51 / PS54 / PS55, acute + subacute, cue L      4
  J_PS46_acute      jaw_only, PS46 acute                                       4
  J_mild            jaw_only, PS47-PS50, any post epoch                        4
  N_near_threshold  jaw_only, any animal / post epoch, sustained deflection 1.00-1.15 x threshold   4
  C_incomplete      incomplete, PS46 / PS51 / PS54 / PS55 acute + subacute     3
  C_no_resp         no_resp,    PS46 / PS51 / PS54 / PS55 acute + subacute     3
Near-threshold is drawn first; every draw is uniform at random within its stratum (seed SEED), at most 2 trials per
session per stratum, only sessions with one video2 file whose frame count equals the jaw trace length.
"Sustained deflection / threshold" = the largest level that the density test (>= 5 of 8 frames) would still pass, in
the 0-5,000 ms detect window, over the trial's applied threshold max(4 x baseline sd, 4 px) (>= 1 = jaw call passes);
"peak / threshold" = the peak |jaw - baseline| over the same threshold.

Clips: -1.0 .. +5.0 s around the tone (video2 frames tone - 250 .. tone + 1250), 2 x 2 tiles: video2 front (the
jaw-call camera) | video4 below (vertically flipped, = widefield cam1 orientation) / video1 side | video3 side.
Side / below frames matched to video2 by the per-camera frame counter (timestamp CSV column 0, counted from each
camera's first frame; a few-frame start offset between cameras can remain). One overlay: a small yellow square in the
top-left corner from the tone frame on. Real time (50 fps, every 5th frame) and 0.25x (every frame at 62.5 fps).
Usage: PYTHONPATH=<worktree>/src MKL_THREADING_LAYER=SEQUENTIAL python c1_blind_jaw_review_ccB1127.py select|clips
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261127
SO = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs")
DLC = SO / "dlc_kinematics"
CAM = Path("M:/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera")
VLS = SO / "vls_stroke_paper"
CLIPS = VLS / "blind_review_twotone_ccB1127"
KEYDIR = VLS / "blind_review_keys_ccB1127"
KEY = KEYDIR / "KEY_DO_NOT_OPEN_twotone_ccB1127.csv"
FFMPEG = r"C:/Users/SabatiniLab/miniconda3/envs/stroke_orofacial/Library/bin/ffmpeg.exe"
LABEL = {"PS47": "#1", "PS48": "#2", "PS49": "#3", "PS50": "#4", "PS46": "#5", "PS51": "#6", "PS54": "#7", "PS55": "#8"}
SEVMOD, CTRL = ["PS51", "PS54", "PS55"], ["PS46", "PS51", "PS54", "PS55"]
MILD = ["PS47", "PS48", "PS49", "PS50"]
NEAR = (1.0, 1.15)
PRE_S, POST_S, FPS = 1.0, 5.0, 250
SHEET_COLS = ["clip_id", "clip_realtime", "clip_quarter_speed",
              "tongue_protrusion_after_tone (Y/N/unsure)", "jaw_opening_after_tone (Y/N/unsure)",
              "jaw_movement_before_tone_in_1s_shown (Y/N/unsure)", "first_post_tone_movement_onset_s (approx)",
              "if_tongue_visible_reached_toward_spout (Y/N)", "note", "confidence (1-3)"]


def live_classes() -> pd.DataFrame:
    """Fig 2B per-trial classes under the adopted after-cue jaw rule, with the jaw onset."""
    from stroke_orofacial.stats import trial_outcomes as to
    K = pd.read_csv(SO / "stats/results/trial_outcomes/c1_trial_classes.csv", dtype={"date": str})
    B = pd.read_parquet(DLC / "tongue_jaw_mismatch/jaw_onset_after_cue/c1_jaw_onset_trials.parquet")
    L = to.override_jaw_only(K, B, "jaw_only_v2")
    B = B.rename(columns={"trial_index": "trial"})[["animal", "date", "trial", "onset_ms", "moved_after_cue"]]
    return L.merge(B.assign(date=B.date.astype(str)), on=["animal", "date", "trial"], how="left", validate="one_to_one")


def video_files(animal: str, date: str) -> dict[int, str] | None:
    """video1-4 of the session, None when video2 is missing or ambiguous (multi-part sessions)."""
    out = {}
    for k in (1, 2, 3, 4):
        h = sorted(glob.glob(str(CAM / date / animal / f"video{k}_*.avi")))
        if len(h) == 1:
            out[k] = h[0]
        elif k == 2:
            return None
    return out


def margin_job(args) -> pd.DataFrame:
    """Deflection / threshold of the 0-5 s jaw call for the given trials of one session."""
    animal, date, trials = args
    from numpy.lib.stride_tricks import sliding_window_view

    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP
    jp = load_defaults()["dlc_kinematics"]["jaw_pertrial"]
    det, base = tuple(jp["detect_win_ms"]), tuple(jp["baseline_win_ms"])
    W = int(jp["sustained_window_n_frames"])
    Kk = int(np.ceil(float(jp["sustained_density_threshold"]) * W))
    jy = pd.read_parquet(DLC / f"cleaned_traces/jaw/{animal}/{date}.parquet", columns=["y_final"]).y_final.to_numpy(float)
    C = pd.read_parquet(DLC / f"tongue_jaw_mismatch/candidate_trials/{animal}/{date}.parquet",
                        columns=["trial_index", "tone_frame_idx", "fps"]).set_index("trial_index")
    vf = video_files(animal, date)
    n_ts = None
    if vf is not None:                                   # video2 frame count from the AVI header (no full read)
        q = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_frames", "-of", "csv=p=0", vf[2]],
                           capture_output=True, text=True, creationflags=0x08000000)
        n_ts = int(q.stdout.strip()) if q.stdout.strip().isdigit() else None
    rows = []
    for t in trials:
        fps, c = float(C.at[t, "fps"]), int(C.at[t, "tone_frame_idx"])
        lo, hi = min(base[0], det[0]), max(base[1], det[1])
        pre_f, post_f = abs(JP._ms_to_frames(lo, fps)), abs(JP._ms_to_frames(hi, fps))
        t_ms = np.arange(-pre_f, post_f + 1) * (1000.0 / fps)
        yw = JP._snippet(jy, c, pre_f, post_f, len(jy))
        bm, bs = JP._compute_jaw_baseline(yw, t_ms, baseline_win_ms=base)
        thr = np.nan
        sus = peak = np.nan
        if np.isfinite(bm) and np.isfinite(bs) and bs > 0:
            thr, _ = JP._compute_jaw_threshold(bs, sd_mult=float(jp["deflection_threshold_sd_multiplier"]),
                                               min_px=float(jp["deflection_threshold_min_px"]))
            dev = np.abs(yw - bm)[JP._window_mask(t_ms, det)]
            dev = np.where(np.isfinite(dev), dev, 0.0)
            sus = float(np.sort(sliding_window_view(dev, W), axis=1)[:, W - Kk].max()) / thr
            peak = float(dev.max()) / thr
        rows.append(dict(animal=animal, date=date, trial=int(t), tone_frame=c, fps=fps, jaw_threshold_px=thr,
                         sustained_deflection_over_threshold=sus, peak_deflection_over_threshold=peak,
                         video_ok=bool(vf is not None and n_ts == len(jy) and fps == FPS
                                       and c - PRE_S * FPS >= 0 and c + POST_S * FPS < len(jy))))
    return pd.DataFrame(rows)


def draw(pool: pd.DataFrame, n: int, rng, taken: set, cap: int = 2) -> pd.DataFrame:
    """Uniform random draw of n rows, at most `cap` per session, skipping already taken trials."""
    pool = pool[pool.video_ok & ~pool.set_index(["animal", "date", "trial"]).index.isin(taken)]
    order = rng.permutation(len(pool))
    out, per = [], {}
    for i in order:
        r = pool.iloc[i]
        s = (r.animal, r.date)
        if per.get(s, 0) >= cap:
            continue
        per[s] = per.get(s, 0) + 1
        out.append(i)
        if len(out) == n:
            break
    return pool.iloc[out]


def cmd_select() -> int:
    for p in (KEY, CLIPS / "scoring_sheet_twotone_ccB1127.csv"):
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
    L = live_classes()
    post = L[L.epoch != "pre"]
    ac_sub = post.epoch.isin(["acute", "subacute"])
    need = post[(post.cls == "jaw_only") | ((post.cls.isin(["incomplete", "no_resp"])) & post.animal.isin(CTRL) & ac_sub)]
    jobs = [(a, d, g.trial.tolist()) for (a, d), g in need.groupby(["animal", "date"])]
    with Pool(3) as p:
        M = pd.concat(p.map(margin_job, jobs, chunksize=1), ignore_index=True)
    P = need.merge(M, on=["animal", "date", "trial"], how="left", validate="one_to_one")
    print("candidate trials", len(P), "with usable video", int(P.video_ok.sum()))
    jo = P[P.cls == "jaw_only"]
    rng = np.random.default_rng(SEED)
    taken: set = set()
    strata = [
        ("N_near_threshold", jo[jo.sustained_deflection_over_threshold.between(*NEAR, inclusive="right")], 4),
        ("J_sev_mod_contra", jo[jo.animal.isin(SEVMOD) & jo.epoch.isin(["acute", "subacute"]) & (jo.cue_side == "R")], 8),
        ("J_sev_mod_ipsi", jo[jo.animal.isin(SEVMOD) & jo.epoch.isin(["acute", "subacute"]) & (jo.cue_side == "L")], 4),
        ("J_PS46_acute", jo[(jo.animal == "PS46") & (jo.epoch == "acute")], 4),
        ("J_mild", jo[jo.animal.isin(MILD)], 4),
        ("C_incomplete", P[P.cls == "incomplete"], 3),
        ("C_no_resp", P[P.cls == "no_resp"], 3),
    ]
    picks, pools = [], {}
    for name, pool, n in strata:
        d = draw(pool, n, rng, taken).assign(stratum=name)
        pools[name] = dict(pool_trials=int(len(pool)), pool_with_video=int(pool.video_ok.sum()), drawn=int(len(d)))
        taken |= set(zip(d.animal, d.date, d.trial))
        picks.append(d)
    S = pd.concat(picks, ignore_index=True)
    S["clip_id"] = [f"clip_{i + 1:03d}" for i in rng.permutation(len(S))]   # shuffled across strata
    S["ms_id"] = S.animal.map(LABEL)
    S["cue_side_lesion"] = S.cue_side.map({"R": "contra", "L": "ipsi"})
    S = S.sort_values("clip_id")
    cols = ["clip_id", "stratum", "animal", "ms_id", "grp", "date", "rel_day", "trial", "cue_side", "cue_side_lesion",
            "epoch", "cls", "cls_v1", "onset_ms", "moved_after_cue", "jaw_threshold_px",
            "sustained_deflection_over_threshold", "peak_deflection_over_threshold", "tone_frame"]
    KEYDIR.mkdir(parents=True, exist_ok=True)
    S[cols].to_csv(KEY, index=False)
    meta = dict(seed=SEED, near_threshold_range=NEAR, strata=pools, n_clips=int(len(S)),
                classes_source="stats/results/trial_outcomes/c1_trial_classes.csv + jaw_only_v2 override "
                               "(jaw_onset_after_cue/c1_jaw_onset_trials.parquet)", script=__file__)
    (KEYDIR / "selection_meta_twotone_ccB1127.json").write_text(json.dumps(meta, indent=2))
    CLIPS.mkdir(parents=True, exist_ok=True)
    sh = pd.DataFrame({c: "" for c in SHEET_COLS}, index=range(len(S)))
    sh["clip_id"] = S.clip_id.to_numpy()
    sh["clip_realtime"] = [f"{c}_1x.mp4" for c in S.clip_id]
    sh["clip_quarter_speed"] = [f"{c}_0.25x.mp4" for c in S.clip_id]
    sh.to_csv(CLIPS / "scoring_sheet_twotone_ccB1127.csv", index=False)
    try:
        sh.to_excel(CLIPS / "scoring_sheet_twotone_ccB1127.xlsx", index=False)
    except Exception as e:                                              # openpyxl missing -> csv only
        print("xlsx not written:", e)
    print(json.dumps(pools, indent=1))
    print("wrote", KEY, "and the scoring sheet in", CLIPS)
    return 0


def counter_map(animal: str, date: str, frames2: np.ndarray) -> dict[int, np.ndarray]:
    """video2 frame index -> the frame of each other camera with the same trigger count since its first frame."""
    def cnt(k):
        h = sorted(glob.glob(str(CAM / date / animal / f"timestamp{k}_*.csv")))
        if len(h) != 1:
            return None
        c = pd.read_csv(h[0], header=None, usecols=[0]).iloc[:, 0].to_numpy(np.int64)
        return c - c[0]
    c2 = cnt(2)
    out = {2: frames2}
    for k in (1, 3, 4):
        ck = cnt(k)
        if ck is None:
            continue
        out[k] = np.minimum(np.searchsorted(ck, c2[frames2]), len(ck) - 1)
    return out


def clip_job(r: dict) -> dict:
    animal, date, tf, cid = r["animal"], r["date"], int(r["tone_frame"]), r["clip_id"]
    o1, o4 = CLIPS / f"{cid}_1x.mp4", CLIPS / f"{cid}_0.25x.mp4"
    if o1.exists() or o4.exists():
        return dict(clip_id=cid, status="exists, skipped")
    vf = video_files(animal, date)
    starts = counter_map(animal, date, np.array([tf - int(PRE_S * FPS)]))
    n = int((PRE_S + POST_S) * FPS) + 1
    args, filt, have = [FFMPEG, "-v", "error", "-nostdin"], [], {}
    for i, k in enumerate((2, 4, 1, 3)):
        if k in vf and k in starts:
            args += ["-ss", f"{int(starts[k][0]) / FPS:.4f}", "-i", vf[k]]
            have[k] = int(starts[k][0])
        else:
            args += ["-f", "lavfi", "-i", f"color=c=black:s=800x600:r={FPS}"]
        flip = ",vflip" if k == 4 else ""
        filt.append(f"[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,format=gray{flip},scale=640:480[v{i}]")
    filt.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,format=yuv420p,"
                f"drawbox=x=14:y=14:w=22:h=22:color=yellow:t=fill:enable='gte(n,{int(PRE_S * FPS)})',split[a][b]")
    filt.append("[a]fps=50[r]")
    filt.append("[b]setpts=4*PTS[q]")
    enc = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-map_metadata", "-1",
           "-fflags", "+bitexact", "-flags:v", "+bitexact"]
    args += ["-filter_complex", ";".join(filt), "-map", "[r]", *enc, "-r", "50", str(o1),
             "-map", "[q]", *enc, "-r", "125/2", str(o4)]
    p = subprocess.run(args, capture_output=True, text=True, creationflags=0x08000000)
    return dict(clip_id=cid, status="ok" if p.returncode == 0 else f"ffmpeg {p.returncode}: {p.stderr[-300:]}",
                cams=",".join(f"video{k}" for k in (2, 4, 1, 3) if k in have),
                **{f"start_frame_video{k}": v for k, v in have.items()})


def cmd_clips(jobs: int, only: list[str] | None) -> int:
    S = pd.read_csv(KEY, dtype={"date": str})
    if only:
        S = S[S.clip_id.isin(only)]
    with Pool(jobs) as p:
        res = p.map(clip_job, S.to_dict("records"), chunksize=1)
    R = pd.DataFrame(res)
    st = KEYDIR / "clip_render_status_twotone_ccB1127.csv"      # holds video frame numbers -> stays with the key
    if st.exists():
        R = pd.concat([pd.read_csv(st), R], ignore_index=True)
    R.to_csv(st, index=False)
    print(R.status.value_counts().to_string())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["select", "clips"])
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    return cmd_select() if a.cmd == "select" else cmd_clips(a.jobs, a.only)


if __name__ == "__main__":
    sys.exit(main())
