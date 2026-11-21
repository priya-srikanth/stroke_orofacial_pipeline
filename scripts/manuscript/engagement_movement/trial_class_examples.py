"""SUPPLEMENTARY CANDIDATE (Priya 2026-11-20): example trials of each outcome, both cohorts, jaw + tongue keypoints from
the existing pipeline outputs. Rows = cohort; columns = pre-stroke LICK trials (jaw + tongue), post-stroke (acute)
JAW WITHOUT TONGUE, post-stroke (acute) NO RESPONSE; K trials each, drawn at random (seed 0) from the trials that pass
the stated CLARITY rule (so the legend can state how examples were chosen).

Window -0.5 .. +4 s from the cue. Jaw = y minus its -500..0 ms mean (px, + = down in the image). Tongue = distance from
the mouth (px), 0 = in the mouth.

TWO-TONE (stroke_orofacial dlc_kinematics; cleaned_traces jaw / tongue, candidate_trials; 250 fps):
  lick        pre session; quiet_tongue_pass False (tongue peaks 70 ms..5 s), >= 3 licks, jaw_pass_qc, AND clean_lick
              (BOTH cohorts, Priya 11-20: no tongue before the cue, first tongue-out 0.1..0.5 s, jaw tracked >= 98 %,
              jaw open > 4 px on >= 90 % of tongue-out frames)
  jaw only    acute; candidate_no_lick_with_jaw_move AND the NEW after-cue rule (jaw_pertrial.jaw_onset_after_cue,
              branch c1-jaw-onset-after-cue) with onset 50..1000 ms, AND tongue in the mouth on every frame -0.5..4 s,
              AND |jaw| >= 8 px (2x the 4 px floor) within 0.5 s of the onset
  no response acute; quiet_tongue_pass AND NOT jaw_pass_qc AND tongue in the mouth on every frame -0.5..4 s
SIX-POSITION (widefield LP v36 cam4 clean.npz / windows.npz; imaging_encoding/qc s1_trial_classes_cue_stop (Fig 3B
classes, working period) + jaw_onsets.csv; close_center excluded, chin hidden on cam4):
  lick        pre; cls contact AND clean_lick (as above) AND a sustained bout like the two-tone cohort's (Priya 11-20): tongue out over >= 1.8 s
              of 0..4 s with no in-mouth gap > 0.5 s
  jaw only    acute (ALL acute sessions); cls jaw_only, onset (not at cue) 50..1000 ms, jaw_dir open, |jaw| >= 8 px
              within 0.5 s of the onset, tongue in the mouth on every frame -0.5..4 s, AND rhythmic (Priya 11-20):
              >= 3 jaw peaks (prominence >= 4 px, >= 80 ms apart) within 1.5 s of the onset
  no response acute; cls no_response, tongue in the mouth on every frame -0.5..4 s
(Fig 3B working period = cues up to the session's last contact or incomplete lick; the jaw-only column has its own
jaw scale)
Sessions: two-tone PS54 (severe) + PS51 (moderate), pre 04-21, acute 05-08 / 05-01; six-position: each animal's last
August pre session and first acute session. Usage: PYTHONPATH=<stroke_orofacial worktree>/src python trial_class_examples.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP  # noqa: E402

OUT = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/review/c2_treadmill_2026-11-20/jaw_only_examples")
SO = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/dlc_kinematics")
LP = Path("M:/MICROSCOPE/Priya/Widefield/LP_analysis/lp_r4_heatmap_20261013__clean_v36")
QC = LP / "imaging_encoding/qc"
T0, T1, K = -0.5, 4.0, 4
rng = np.random.default_rng(0)
jp = load_defaults()["dlc_kinematics"]["jaw_pertrial"]
KW = dict(detect_win_ms=tuple(jp["detect_win_ms"]), baseline_win_ms=tuple(jp["baseline_win_ms"]),
          sd_mult=float(jp["deflection_threshold_sd_multiplier"]), min_px=float(jp["deflection_threshold_min_px"]),
          density_thr=float(jp["sustained_density_threshold"]), window_n=int(jp["sustained_window_n_frames"]))
CLASSES = ["lick", "jaw only", "no response"]


MIN_JAW = 8.0      # px: 2x the 4 px detector floor, reached within 0.5 s of the detected onset


def near_onset(t, j, onset_s):
    """Largest |jaw displacement| in onset .. onset + 0.5 s (the movement the onset marks, on the plotted trace)."""
    m = (t >= onset_s) & (t <= onset_s + 0.5)
    return float(np.nanmax(np.abs(j[m]))) if m.any() else 0.0


BOUT_S, GAP_S = 1.8, 0.5         # six-position lick examples: tongue out over >= 1.8 s, no in-mouth gap > 0.5 s
RHY_N, RHY_PROM, RHY_S = 3, 4.0, 1.5   # six-position jaw-only examples: >= 3 jaw peaks (prominence >= 4 px, >= 80 ms
                                       # apart) within 1.5 s of the onset


def long_bout(t, tongue):
    """Tongue-out frames in 0..4 s span >= BOUT_S with no gap longer than GAP_S (a sustained bout, as in two-tone)."""
    tt = t[(t >= 0) & (tongue > 0)]
    return tt.size > 1 and tt[-1] - tt[0] >= BOUT_S and np.diff(tt).max() <= GAP_S


def rhythmic(t, j, onset_s):
    """>= RHY_N jaw peaks (prominence >= RHY_PROM px, >= 80 ms apart) in onset .. onset + RHY_S."""
    from scipy.signal import find_peaks
    m = (t >= onset_s) & (t <= onset_s + RHY_S)
    if m.sum() < 10:
        return False
    fps = 1.0 / np.median(np.diff(t[m]))
    pk, _ = find_peaks(np.nan_to_num(j[m]), prominence=RHY_PROM, distance=max(1, int(0.08 * fps)))
    return pk.size >= RHY_N


def clean_lick(t, j, tongue):
    """Lick example rules, both cohorts (Priya 11-20 review of v4): no tongue out before the cue (-0.5..0 s); first
    tongue-out 0.1..0.5 s after the cue (a prompt response, no delayed start); jaw tracked on >= 98 % of frames; the jaw
    open > 4 px on >= 90 % of tongue-out frames (every lick has its jaw movement)."""
    out = tongue > 0
    if out[t < 0].any() or not out.any() or not np.isfinite(j).mean() >= 0.98:
        return False
    first = t[out][0]
    return 0.1 <= first <= 0.5 and float(np.mean(np.nan_to_num(j[out]) > 4.0)) >= 0.9


def pick(rows):
    return [rows[i] for i in np.sort(rng.choice(len(rows), min(K, len(rows)), replace=False))] if rows else []


def c1_session(animal, d, epoch):
    C = pd.read_parquet(SO / f"tongue_jaw_mismatch/candidate_trials/{animal}/{d}.parquet")
    jy = pd.read_parquet(SO / f"cleaned_traces/jaw/{animal}/{d}.parquet", columns=["y_final"]).y_final.to_numpy(float)
    tg = pd.read_parquet(SO / f"cleaned_traces/tongue/{animal}/{d}.parquet", columns=["x_final", "y_final"])
    tl = np.hypot(tg.x_final.to_numpy(float), tg.y_final.to_numpy(float))
    out = {c: [] for c in CLASSES}
    for r in C.itertuples():
        fps, c = float(r.fps), int(r.tone_frame_idx)
        f = np.arange(int(T0 * fps), int(T1 * fps) + 1)
        if c + f[0] < 0 or c + f[-1] >= len(jy):
            continue
        j = jy[c + f] - np.nanmean(jy[c + int(-0.5 * fps):c + 1])
        t = tl[c + f]
        quiet_all = bool(np.nanmax(t) == 0)
        d0 = dict(t=f / fps, jaw=j, tongue=t, onset=np.nan,
                  lab=f"{animal} {d[4:6]}-{d[6:]} tr {r.trial_index} {r.side}")
        if (epoch == "pre" and not r.quiet_tongue_pass and r.n_licks_in_quiet_win >= 3 and r.jaw_pass_qc
                and clean_lick(f / fps, j, t)):
            out["lick"].append(d0)
        if epoch == "acute" and r.candidate_no_lick_with_jaw_move and quiet_all:
            o = JP.jaw_onset_after_cue(jy, fps, c, **KW)
            if (o["onset_frames"] > 0 and 50 <= o["onset_ms"] <= 1000
                    and near_onset(f / fps, j, o["onset_ms"] / 1000) >= MIN_JAW):
                out["jaw only"].append({**d0, "onset": o["onset_ms"] / 1000})
        if epoch == "acute" and r.quiet_tongue_pass and not r.jaw_pass_qc and quiet_all:
            out["no response"].append(d0)
    return out


def c2_session(label, epoch, S, O):
    animal, mmdd = label.split("_")
    sd = LP / f"sessions/{animal}/2026{mmdd}"
    w = np.load(sd / "windows.npz")
    ix = pd.DataFrame({k[3:]: w[k] for k in w.files if k.startswith("ix_")})
    c = np.load(sd / "clean.npz")
    x0, y0 = c["tongue_origin"]
    ix["jaw"] = c["jaw_y"]
    ix["tongue"] = np.where(c["tongue_fill"] == 0, np.hypot(c["tongue_x"] - x0, c["tongue_y"] - y0), 0.0)
    ix["cue_daq"] = ix.daq_s - ix.t_daq_ms / 1000
    cue_of = ix.groupby("trial_id").cue_daq.median()
    Ss = S[S.label == label]
    last = Ss[Ss.cls.isin(["contact", "incomplete"])].cue_idx.max()    # Fig 3B working period (load_outcomes)
    Ss = Ss[(Ss.cue_idx <= last) & (Ss.position != "close_center")]
    Os = O[O.session == f"{animal}_2026{mmdd}"].set_index("trial_id")
    out = {k: [] for k in CLASSES}
    want = {"pre": {"contact": "lick"}, "acute": {"jaw_only": "jaw only", "no_response": "no response"}}[epoch]
    for r in Ss[Ss.cls.isin(list(want))].itertuples():
        tid = int((cue_of - r.cue_s).abs().idxmin())
        if abs(cue_of[tid] - r.cue_s) > 0.05:
            continue
        g = ix[(ix.trial_id == tid) & (ix.t_daq_ms >= T0 * 1000) & (ix.t_daq_ms <= T1 * 1000)]
        if len(g) < 0.9 * (T1 - T0) * 250:
            continue
        b = g[g.t_daq_ms <= 0].jaw.mean()
        d0 = dict(t=g.t_daq_ms.to_numpy() / 1000, jaw=g.jaw.to_numpy() - b, tongue=g.tongue.to_numpy(), onset=np.nan,
                  lab=f"{animal} {mmdd[:2]}-{mmdd[2:]} tr {tid} {r.position}")
        k = want[r.cls]
        if k == "jaw only":
            if tid not in Os.index:
                continue
            o = Os.loc[tid]
            if (bool(o.onset_at_cue) or not (50 <= o.jaw_onset_ms <= 1000) or o.jaw_dir != "open"
                    or g.tongue.max() > 0 or near_onset(d0["t"], d0["jaw"], o.jaw_onset_ms / 1000) < MIN_JAW
                    or not rhythmic(d0["t"], d0["jaw"], o.jaw_onset_ms / 1000)):
                continue
            d0["onset"] = o.jaw_onset_ms / 1000
        if k == "lick" and not (long_bout(d0["t"], d0["tongue"]) and clean_lick(d0["t"], d0["jaw"], d0["tongue"])):
            continue
        if k == "no response" and g.tongue.max() > 0:
            continue
        out[k].append(d0)
    return out


def merge(dicts):
    return {k: sum((d[k] for d in dicts), []) for k in CLASSES}


c1 = merge([c1_session("PS54", "20250421", "pre"), c1_session("PS51", "20250421", "pre"),
            c1_session("PS54", "20250508", "acute"), c1_session("PS51", "20250501", "acute")])
S = pd.read_csv(QC / "s1_trial_classes_cue_stop.csv.gz")
O = pd.read_csv(QC / "jaw_onsets.csv")
E = O.drop_duplicates("session").assign(label=lambda x: x.animal + "_" + x.date.astype(str).str[-4:])
pre = E[(E.epoch == "pre") & (E.date.astype(str).str[-4:] >= "0806")].groupby("animal").label.max()
acu = E[E.epoch == "acute"].label.sort_values()            # ALL acute sessions (rhythmic jaw-only trials are rarer)
c2 = merge([c2_session(lb, "pre", S, O) for lb in pre] + [c2_session(lb, "acute", S, O) for lb in acu])
print("eligible two-tone:", {k: len(v) for k, v in c1.items()}, "six-position:", {k: len(v) for k, v in c2.items()})
print("six-position sessions: pre", list(pre), "acute", list(acu))

rows = [("Two-tone", c1), ("Six-position", c2)]
heads = ["Pre-stroke: lick (jaw + tongue)", "Post-stroke (acute): jaw without tongue", "Post-stroke (acute): no response"]
fig = plt.figure(figsize=(15, 2 * K * 2 + 1.6))
top, *sub = fig.subfigures(3, 1, hspace=0.04, height_ratios=[0.6, 2 * K, 2 * K])   # top strip = legend
for (cname, data), sf in zip(rows, sub):
    picks = {k: pick(data[k]) for k in CLASSES}
    jl_all = max(np.nanmax(np.abs(d["jaw"])) for v in picks.values() for d in v) * 1.05
    jl_jo = max(np.nanmax(np.abs(d["jaw"])) for d in picks["jaw only"]) * 1.1   # jaw-only column zoomed (own scale)
    tlim = max(1.0, max(np.nanmax(d["tongue"]) for v in picks.values() for d in v)) * 1.05
    ax = sf.subplots(K, 3, sharex=True, squeeze=False)
    sf.suptitle(cname + " cohort", fontsize=11, fontweight="bold")
    for j, k in enumerate(CLASSES):
        jlim = jl_jo if k == "jaw only" else jl_all
        zoom = "\n(jaw axis zoomed)" if k == "jaw only" else ""       # pool sizes go to the printout / legend text,
        ax[0, j].set_title(f"{heads[j]}{zoom}", fontsize=9)         # not the panel (Priya 11-20: unclear on the figure)
        for i in range(K):
            a = ax[i, j]
            if i >= len(picks[k]):
                a.axis("off")
                continue
            d = picks[k][i]
            a.plot(d["t"], d["jaw"], color="#1f77b4", lw=1)
            a.set_ylim(-jlim, jlim)
            b = a.twinx()
            b.fill_between(d["t"], 0, d["tongue"], color="#c51b8a", alpha=0.35, lw=0)
            b.set_ylim(0, tlim)
            for s in (a, b):
                s.spines["top"].set_visible(False)
                s.tick_params(labelsize=7)
            if j < 2:
                b.set_yticklabels([])
            else:
                b.set_ylabel("tongue (px)", color="#c51b8a", fontsize=8)
            if j == 0:
                a.set_ylabel("jaw (px)", color="#1f77b4", fontsize=8)
            a.axvline(0, color="k", lw=0.8)
            if np.isfinite(d["onset"]):
                a.axvline(d["onset"], color="#1f77b4", lw=0.8, ls="--")
            a.text(0.01, 0.97, d["lab"], transform=a.transAxes, fontsize=7, va="top")
    for a in ax[-1]:
        a.set_xlabel("time from cue (s)", fontsize=8)
# Legend (Priya 11-20): what each mark is, once for the whole figure, in the top margin
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
top.legend(handles=[Line2D([], [], color="#1f77b4", lw=1.5, label="jaw movement (px from pre-cue mean)"),
                    Patch(color="#c51b8a", alpha=0.35, label="tongue out (px from mouth)"),
                    Line2D([], [], color="k", lw=0.8, label="cue"),
                    Line2D([], [], color="#1f77b4", lw=0.8, ls="--", label="detected jaw onset")],
           loc="center", ncol=4, fontsize=10, frameon=False)
for ext in ("png", "svg"):
    p = OUT / f"trial_class_examples_both_cohorts.{ext}"
    assert not p.exists(), f"refusing to overwrite {p}"
    fig.savefig(p, dpi=150)
print("wrote", OUT)
