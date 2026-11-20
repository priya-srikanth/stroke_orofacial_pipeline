"""Figures for the lateral-angle test (results page + docs/POSE3D_2PRAM.md).

Reads the saved outputs in pose3d/lateral_test_20261119/ (licks_<A>.csv from analyze.py, below_tongue_cutoff_PS46.csv)
and the two-view clips; writes PNGs to pose3d/lateral_test_20261119/figures/. Animals = every licks_<A>.csv present.

Conventions (shared results-page rules): sessions as OPEN markers, shape = animal, color = epoch (pre black, acute
pink, subacute goldenrod, chronic teal; epochs from each animal's epoch_boundaries in configs/animals.yaml); no top
spine; no figure numbers inside images.

Lateral position, both views, in rod-tip spacings from the rod midpoint (+ = image right):
  front (video2): spout-centered tongue x at the frame of max |angle| within +-52 ms of the lick / front rod spacing
  below (video4): tongue x (zero-shot cam1 LP, p > 0.9) at max |lateral| within the same window / below rod spacing
Gate (default): below-view point near the mouth, |lateral| <= 1 and |forward| <= 0.6 rod spacings.
"""

import sys
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

O = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/pose3d")
D_IN = O / "lateral_test_20261119"
D_OUT = D_IN / "figures"
CLIPS = O / "clips/twoview_cam1zeroshot_v2_20261119"
REPO = Path(__file__).resolve().parents[3]
EPOCH_COLOR = {"pre": "k", "acute": "#d01c8b", "subacute": "#b8860b", "chronic": "#01665e"}
EPOCHS = list(EPOCH_COLOR)
MARKER = {"PS46": "o", "PS50": "s", "PS55": "^"}
CFG = yaml.safe_load((REPO / "configs" / "animals.yaml").read_text())
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def rel_day(a, d):
    return (pd.Timestamp(str(d)) - pd.Timestamp(CFG[a]["stroke_date"])).days


def epoch_of(a, d):
    r, b = rel_day(a, d), CFG[a]["epoch_boundaries"]
    if r < 1:
        return "pre"
    if r <= b["acute_max_rel_day"]:
        return "acute"
    return "subacute" if r <= b["subacute_max_rel_day"] else "chronic"


def load(a, gated=True):
    D = pd.read_csv(D_IN / f"licks_{a}.csv").dropna(subset=["A2", "L2", "L4"])
    if gated:
        D = D[(D.L4.abs() <= 1) & (D.F4.abs() <= 0.6)]
    D = D.assign(animal=a, ep=[epoch_of(a, d) for d in D.date], day=[rel_day(a, d) for d in D.date])
    return D


def session_changes(D):
    """Per session x trial side: mean lateral position in each view, minus the animal's own pre mean (same side)."""
    S = D.groupby(["animal", "date", "day", "ep", "side"])[["L2", "L4"]].agg(["mean", "size"])
    S.columns = ["L2", "n", "L4", "_"]
    S = S.drop(columns="_").reset_index()
    base = S[S.ep == "pre"].groupby(["animal", "side"])[["L2", "L4"]].mean()
    key = list(zip(S.animal, S.side))
    S["dL2"] = S.L2.values - base.loc[key, "L2"].values
    S["dL4"] = S.L4.values - base.loc[key, "L4"].values
    return S


def legend_handles(animals, eps):
    h = [Line2D([], [], ls="", marker=MARKER[a], mfc="none", mec="0.3", label=a) for a in animals]
    h += [Line2D([], [], ls="", marker="o", mfc="none", mec=EPOCH_COLOR[e], label=e) for e in eps]
    return h


def fig_example():
    """Two-view still, PS46 R trial pre (03-10 trial 12) vs post (03-16 trial 71), video row of the clip only."""
    rows = []
    for name, fr, lab in (
        ("twoview_PS46_20250310_pre_trial012_R", 121, "pre-stroke (03-10), R trial 12"),
        ("twoview_PS46_20250316_post_trial071_R", 78, "post-stroke day 3 (03-16), R trial 71"),
    ):
        cap = cv2.VideoCapture(str(CLIPS / f"{name}.mp4"))
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        _, f = cap.read()
        cap.release()
        rows.append((cv2.cvtColor(f[34:450], cv2.COLOR_BGR2RGB), lab))
    fig, ax = plt.subplots(2, 1, figsize=(8.4, 8.9))
    for x, (im, lab) in zip(ax, rows):
        x.imshow(im)
        x.set_axis_off()
        x.set_title(
            f"PS46, {lab}: front view (video2, left) | below view (video4, right)",
            fontsize=9,
            loc="left",
        )
    fig.suptitle(
        "Same lick seen from the front and from below: post-stroke R-trial licks go to the other spout",
        fontsize=10,
    )
    fig.tight_layout()
    return fig


def fig_change_scatter(S, animals):
    fig, ax = plt.subplots(1, 2, figsize=(9, 4.4), sharex=True, sharey=True)
    lim = max(0.75, float(np.nanmax(np.abs(S[["dL2", "dL4"]].values))) + 0.05)
    for x, side in zip(ax, ("L", "R")):
        g = S[S.side == side]
        x.plot([-lim, lim], [-lim, lim], c="0.7", lw=0.8, zorder=0)
        x.axhline(0, c="0.9", lw=0.6, zorder=0)
        x.axvline(0, c="0.9", lw=0.6, zorder=0)
        for _, r in g.iterrows():
            x.plot(r.dL4, r.dL2, MARKER[r.animal], mfc="none", mec=EPOCH_COLOR[r.ep], mew=1.4, ms=8)
        post = g[g.ep != "pre"]
        x.set_title(
            f"{side} trials: {len(post)} post sessions, max |front - below| = "
            f"{(post.dL2 - post.dL4).abs().max():.2f}",
            fontsize=9,
            loc="left",
        )
        x.set_xlabel("below view: change in lateral position (rod spacings)")
        x.set_xlim(-lim, lim)
        x.set_ylim(-lim, lim)
        x.set_aspect("equal")
    ax[0].set_ylabel("front view: change in lateral position (rod spacings)")
    eps = [e for e in EPOCHS if e in set(S.ep)]
    ax[1].legend(handles=legend_handles(animals, eps), frameon=False, fontsize=8, loc="upper left")
    fig.suptitle(
        "Change from each animal's own pre mean, per session x trial side: both views agree (gray = identity)",
        fontsize=10,
    )
    fig.tight_layout()
    return fig


def fig_timeline(S, animals):
    fig, ax = plt.subplots(
        len(animals), 2, figsize=(9, 2.6 * len(animals)), squeeze=False, sharey=True
    )
    for i, a in enumerate(animals):
        for j, side in enumerate(("L", "R")):
            x = ax[i, j]
            g = S[(S.animal == a) & (S.side == side)]
            x.axvline(0.5, c="0.6", ls="--", lw=0.8)
            x.axhline(0, c="0.9", lw=0.6, zorder=0)
            for _, r in g.iterrows():
                c = EPOCH_COLOR[r.ep]
                x.plot(r.day - 0.15, r.L2, MARKER[a], mfc="none", mec=c, mew=1.4, ms=7)
                x.plot(r.day + 0.15, r.L4, "x", c=c, mew=1.4, ms=7)
            x.set_title(f"{a}, {side} trials (stroke = dashed)", fontsize=9, loc="left")
            if j == 0:
                x.set_ylabel("lateral position\n(rod spacings, + = image right)")
            if i == len(animals) - 1:
                x.set_xlabel("day relative to stroke")
    h = [
        Line2D(
            [], [], ls="", marker="o", mfc="none", mec="0.3", label="front view (marker = animal)"
        ),
        Line2D([], [], ls="", marker="x", c="0.3", label="below view"),
    ]
    ax[0, 1].legend(handles=h, frameon=False, fontsize=8)
    fig.suptitle("Session mean lateral tongue position, front vs below view", fontsize=10)
    fig.tight_layout()
    return fig


def fig_per_lick(Ds, animals, ycol, ylab, title):
    fig, ax = plt.subplots(1, len(animals), figsize=(4.2 * len(animals), 4), squeeze=False)
    for x, a in zip(ax[0], animals):
        D = Ds[a]
        for ep in EPOCHS:
            g = D[D.ep == ep]
            if len(g):
                x.scatter(
                    g.L4, g[ycol], s=3, alpha=0.3, c=EPOCH_COLOR[ep], label=f"{ep} ({len(g)})", lw=0
                )
        pre = D[D.ep == "pre"]
        if ycol == "A2":
            a_, b_ = np.polyfit(pre.L4, pre.A2, 1)
            xx = np.array([-1, 1])
            x.plot(xx, a_ * xx + b_, c="0.5", lw=1, label="pre fit")
        rs = D.groupby("date")[["L4", ycol]].apply(lambda g: np.corrcoef(g.L4, g[ycol])[0, 1])
        x.set_title(f"{a}: per-session r {rs.min():.2f}-{rs.max():.2f}", fontsize=9, loc="left")
        x.set_xlabel("below view: lateral position (rod spacings)")
        x.legend(frameon=False, fontsize=7, markerscale=3, loc="upper left")
    ax[0, 0].set_ylabel(ylab)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    return fig


def fig_cutoff():
    C = pd.read_csv(D_IN / "below_tongue_cutoff_PS46.csv")
    c = C[C.kind == "cutoff"]
    g = C[C.kind == "cutoff+gate"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
    for d, s in c.groupby("date"):
        ep = epoch_of("PS46", d)
        kw = {"c": EPOCH_COLOR[ep], "marker": "o", "mfc": "none", "lw": 1, "ms": 5}
        ax[0].plot(s.p_lo, s.recall, label=f"{str(d)[4:6]}-{str(d)[6:]} ({ep})", **kw)
        ax[1].plot(s.p_lo, s.false_pos, **kw)
    for _, r in g.iterrows():
        col = EPOCH_COLOR[epoch_of("PS46", r.date)]
        ax[0].plot(r.p_lo - 0.02, r.recall, "*", c=col, ms=9)
        ax[1].plot(r.p_lo - 0.02, r.false_pos, "*", c=col, ms=9)
    ax[0].set_ylabel("share of front-view tongue-OUT frames\nwith a below-view tongue point")
    ax[1].set_ylabel("share of front-view tongue-IN frames\nwith a below-view tongue point")
    for x in ax:
        x.set_xlabel("below-view tongue likelihood cutoff")
        x.invert_xaxis()
    ax[0].legend(frameon=False, fontsize=7, title="PS46 session", title_fontsize=7)
    ax[1].text(
        0.98,
        0.6,
        "star = cutoff 0.4 + 40 px gate",
        transform=ax[1].transAxes,
        ha="right",
        va="top",
        fontsize=8,
    )
    fig.suptitle(
        "Below-view tongue (zero-shot cam1 model): lowering the cutoff below 0.9 recovers more licks; ~half stay missing",
        fontsize=10,
    )
    fig.tight_layout()
    return fig


def main():
    D_OUT.mkdir(exist_ok=True)
    animals = [a for a in MARKER if (D_IN / f"licks_{a}.csv").exists()]
    if len(sys.argv) > 1:
        animals = sys.argv[1:]
    Ds = {a: load(a) for a in animals}
    S = session_changes(pd.concat(Ds.values()))
    S.round(4).to_csv(D_OUT / "session_changes_gated.csv", index=False)
    figs = {
        "lat_example_frames": fig_example(),
        "lat_change_front_vs_below": fig_change_scatter(S, animals),
        "lat_session_timeline": fig_timeline(S, animals),
        "lat_per_lick_position": fig_per_lick(
            Ds,
            animals,
            "L2",
            "front view: lateral position (rod spacings)",
            "Per lick, gated: front-view vs below-view lateral position (color = epoch)",
        ),
        "lat_per_lick_angle": fig_per_lick(
            Ds,
            animals,
            "A2",
            "front view: pipeline lick angle (deg)",
            "Per lick, gated: the pipeline's front-view angle vs below-view lateral position",
        ),
        "below_tongue_cutoff_PS46": fig_cutoff(),
    }
    for k, f in figs.items():
        f.savefig(D_OUT / f"{k}.png", dpi=140)
        plt.close(f)
        print("wrote", D_OUT / f"{k}.png")
    print(S[S.ep != "pre"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
