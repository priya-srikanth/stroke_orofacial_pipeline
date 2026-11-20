"""Lateral-angle test, one animal (argv[1], default PS46): does the front-view (video2) per-lick angle change pre -> post the same way as the
lateral tongue position seen from below (video4)?

Per lick (first 5 licks/trial, the pipeline's own lick times): the pipeline's angle_max_signed_per_lick (A2), the
front-view spout-centered x at that frame / front rod separation (L2), and from video4 the signed max-|lateral|
tongue position within the same +-52 ms window, relative to the rod-tip midpoint / rod-tip separation (L4).
The +-52 ms window (the pipeline's peak_pad_ms) absorbs the unknown 0-5-frame camera start offset."""

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

O = "M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
PAD = 13  # 52 ms at 250 fps
A = sys.argv[1] if len(sys.argv) > 1 else "PS46"
# stroke date from the repo's animal metadata (configs/animals.yaml), as YYYYMMDD
_cfg = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "configs" / "animals.yaml").read_text()
)
STROKE = pd.Timestamp(str(_cfg[A]["stroke_date"])).strftime("%Y%m%d")
rows = []
for f in sorted(glob.glob(f"clips/{A}_*_index.npz")):
    d = f.split("_")[1]
    pc = glob.glob(f"preds/{A}_{d}_video4_trials_*.csv")
    if not pc:
        continue
    Z = np.load(f)
    idx4 = Z["idx4"]
    trig2, trig4 = Z["trig2"], Z["trig4"]
    tone2 = Z["tone2"]
    tips = json.loads(Path(f"clips/{A}_{d}_tips.json").read_text())["tips"]
    x0 = int(Z["x0"])  # rods.py v3 (centerline jump)
    (xa, ya, _), (xb, yb, _) = tips
    mx, my, s4 = 0.5 * (xa + xb) - x0, 0.5 * (ya + yb), abs(xb - xa)
    P = pd.read_csv(pc[0], header=[0, 1, 2], index_col=0)
    t = P.xs("tongue", level=1, axis=1)
    tx, ty, tl = (t.xs(k, level=1, axis=1).iloc[:, 0].values for k in ("x", "y", "likelihood"))
    assert len(tx) == len(idx4), (len(tx), len(idx4))
    lat4 = np.where(tl > 0.9, (tx - mx) / s4, np.nan)
    fwd4 = np.where(tl > 0.9, (my - ty) / s4, np.nan)
    row_of = {v: i for i, v in enumerate(idx4)}
    J = json.loads(Path(f"{O}/dlc_kinematics/per_trial/tongue/{A}/{d}.json").read_text())
    assert list(J["sides"]) == list(Z["sides"]), "trial sides differ"
    ct = pd.read_parquet(f"{O}/dlc_kinematics/cleaned_traces/tongue/{A}/{d}.parquet")
    pf = pd.read_parquet(f"{O}/dlc_kinematics/per_frame/tongue/{A}/{d}.parquet")[
        "angle_deg_smoothed"
    ].values
    x2, y2 = ct["x_final"].values, ct["y_final"].values
    dd = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    sp = pd.read_parquet(
        glob.glob(f"{O}/dlc_analysis/centered_spout_midpoint/{A}/video2_{dd}T*.parquet")[0]
    )

    def med(bp, ax, sp=sp):
        ok = sp[f"{bp}_likelihood"].values >= 0.9
        return float(np.nanmedian(sp[f"{bp}_{ax}"].values[ok]))

    s2 = abs(med("R_spout", "x") - med("L_spout", "x"))
    tl_ms = J["tongue"]["peak_velocity_per_lick"]["lick_t_peaks_bylick"]
    amax = J["tongue"]["tongue_angle"]["angle_max_signed_per_lick"]
    for i, (side, licks) in enumerate(zip(J["sides"], tl_ms)):
        for k, tms in enumerate(licks):
            if tms is None or not np.isfinite(tms):
                continue
            c2 = int(tone2[i] + round(tms * 0.25))
            w2 = np.arange(max(0, c2 - PAD), min(len(pf), c2 + PAD + 1))
            j2 = w2[np.nanargmax(np.abs(pf[w2]))] if np.isfinite(pf[w2]).any() else None
            c4 = int(np.searchsorted(trig4, trig2[c2]))
            r = [row_of[v] for v in range(c4 - PAD, c4 + PAD + 1) if v in row_of]
            lv = lat4[r]
            L4 = F4 = np.nan
            n4 = int(np.isfinite(lv).sum())
            if n4 >= 2:
                jj = r[int(np.nanargmax(np.abs(lv)))]
                L4, F4 = lat4[jj], fwd4[jj]
            rows.append(
                {
                    "date": d,
                    "epoch": "pre" if d < STROKE else "post",
                    "side": side,
                    "lick": k + 1,
                    "A2": amax[i][k],
                    "L2": x2[j2] / s2 if j2 is not None else np.nan,
                    "Y2": y2[j2] if j2 is not None else np.nan,
                    "L4": L4,
                    "F4": F4,
                    "n4": n4,
                    "s2": s2,
                    "s4": s4,
                }
            )
    print(
        d,
        "licks",
        sum(r["date"] == d for r in rows),
        "rod sep front/below px",
        round(s2),
        round(s4),
        flush=True,
    )
D = pd.DataFrame(rows)
D.to_csv(f"licks_{A}.csv", index=False)
ok = D.dropna(subset=["A2", "L4", "L2"])
print("\nlicks with both views:", len(ok), "of", len(D))
print("corr per session (A2~L4, L2~L4):")
for d, g in ok.groupby("date"):
    print(
        " ",
        d,
        g.epoch.iloc[0],
        len(g),
        round(np.corrcoef(g.A2, g.L4)[0, 1], 2),
        round(np.corrcoef(g.L2, g.L4)[0, 1], 2),
    )
print("\nper-session means by trial side:")
print(ok.groupby(["date", "epoch", "side"])[["A2", "L2", "L4", "Y2", "F4"]].mean().round(3))

# ---- pre -> post: is the angle change explained by the true lateral change? ----
# Map the below-view lateral to front-angle degrees with a fit on PRE licks only (A2 = a*L4 + b); then for each
# session x trial side compare the observed mean angle with the angle predicted from the below view.
pre = ok[ok.epoch == "pre"]
a, b = np.polyfit(pre.L4, pre.A2, 1)
ok = ok.assign(A2_from_L4=a * ok.L4 + b)
print(
    f"\npre fit: A2 = {a:.2f} * L4 + {b:.2f}  (r = {np.corrcoef(pre.A2, pre.L4)[0, 1]:.2f}, n = {len(pre)})"
)
S = (
    ok.groupby(["date", "epoch", "side"])
    .agg(n=("A2", "size"), A2=("A2", "mean"), A2_from_L4=("A2_from_L4", "mean"), Y2=("Y2", "mean"))
    .reset_index()
)
base = S[S.epoch == "pre"].groupby("side")[["A2", "A2_from_L4", "Y2"]].mean()
S["dA2"] = S.A2 - S.side.map(base.A2)
S["dA2_from_L4"] = S.A2_from_L4 - S.side.map(base.A2_from_L4)
S["dY2"] = S.Y2 - S.side.map(base.Y2)
print("\nchange from the pre mean (deg; Y2 px), per session x trial side:")
print(S.round(2).to_string(index=False))
S.to_csv(f"sessions_{A}.csv", index=False)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
for ep, c in (("pre", "#4C72B0"), ("post", "#DD8452")):
    g = ok[ok.epoch == ep]
    ax[0].scatter(g.L4, g.A2, s=4, alpha=0.35, c=c, label=f"{ep} ({len(g)} licks)")
xx = np.linspace(ok.L4.min(), ok.L4.max(), 10)
ax[0].plot(xx, a * xx + b, "k-", lw=1, label="pre fit")
ax[0].set_xlabel("below view: lateral tongue position (rod-tip spacings from rod midpoint)")
ax[0].set_ylabel("front view: pipeline angle (deg)")
ax[0].legend(frameon=False, fontsize=8)
ax[0].set_title("A. Per lick, both views", loc="left", fontsize=10)
dates = sorted(S.date.unique())
xpos = {d: i for i, d in enumerate(dates)}
for side, mk in (("L", "o"), ("R", "s")):
    g = S[S.side == side]
    ax[1].plot(
        [xpos[d] for d in g.date],
        g.dA2,
        mk,
        mfc="none",
        mec="k",
        label=f"{side} trials: front angle",
    )
    ax[1].plot(
        [xpos[d] + 0.15 for d in g.date],
        g.dA2_from_L4,
        mk,
        mfc="none",
        mec="#55A868",
        label=f"{side} trials: predicted from below view",
    )
ax[1].axhline(0, c="0.7", lw=0.8)
ax[1].axvline(sum(d < STROKE for d in dates) - 0.5, c="0.5", ls="--", lw=0.8)
ax[1].set_xticks(range(len(dates)))
ax[1].set_xticklabels([f"{d[4:6]}-{d[6:]}" for d in dates], fontsize=8)
ax[1].set_ylabel("change from pre mean (deg)")
ax[1].legend(frameon=False, fontsize=7)
ax[1].set_title("B. Session means vs pre (stroke = dashed line)", loc="left", fontsize=10)
for x in ax:
    x.spines[["top", "right"]].set_visible(False)
fig.suptitle(
    f"{A}: front-view angle vs below-view lateral position (first 5 licks per trial)", fontsize=10
)
fig.tight_layout()
fig.savefig(f"lateral_test_{A}.png", dpi=150)

# ---- per-lick residual vs the pre fit, and side agreement (added 11-19) ----
ok["res"] = ok.A2 - (a * ok.L4 + b)
print("per-lick residual vs the pre fit (deg): session, n, SD of A2, residual RMS, median |res|")
for d, g in ok.groupby("date"):
    print(
        d,
        g.epoch.iloc[0],
        len(g),
        round(g.A2.std(), 2),
        round(np.sqrt((g.res**2).mean()), 2),
        round(g.res.abs().median(), 2),
    )
print(
    "fraction of licks to the L side (front A2 > 0 | below, pre-fit angle > 0), per session x trial side:"
)
for (d, sd), g in ok.groupby(["date", "side"]):
    print(" ", d, sd, round((g.A2 > 0).mean(), 2), round(((a * g.L4 + b) > 0).mean(), 2))
side4 = np.sign(a * ok.L4 + b)  # below-view side in angle units (zero crossing of the pre fit)
clear = (ok.A2.abs() > 2) & ((a * ok.L4 + b).abs() > 2)
dis = clear & (np.sign(ok.A2) != side4)
print(
    "licks where both views are clearly to one side (|angle| > 2 deg):",
    int(clear.sum()),
    " side disagreement:",
    int(dis.sum()),
    f"({100 * dis.sum() / clear.sum():.1f} %)",
)
print(ok[dis].groupby(["date"]).size().to_dict())
# analysis runs in the stroke_orofacial env via conda run (Priya 11-19: not arhmm)
