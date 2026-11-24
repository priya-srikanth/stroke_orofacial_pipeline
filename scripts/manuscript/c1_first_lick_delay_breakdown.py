"""Two-tone first-lick delay breakdown, the S10A analysis for the first cohort (caption review item 32, CC-B 2026-11-23).

What the first-lick latency is made of, per trial: cue -> first movement (JAW OPENING ONLY; item 5 showed the
six-position movement->lick lengthening rests on the FaceRhythm vigor signal) and first movement -> first lick, as
six-position `revup_behaviour.py` with jaw only:
  first lick  ONSET (rise_start_ms) of the trial's first v7-kept camera lick whose PEAK is 70-3000 ms after the cue
              (dlc_kinematics/lick_events/tongue; the six-position rule: onset of the first lick whose peak >= cue + 70)
  jaw opening the after-cue jaw onset of `jaw_pertrial.jaw_onset_after_cue` (the two-tone jaw-only class's call, Fig 2B;
              front camera DLC jaw, deflection > max(4 SD of the -500..0 ms baseline, 4 px) sustained in >= 5 of 8
              frames, searched 0-5000 ms; the re-onset when the jaw was already deflected at the cue), table
              tongue_jaw_mismatch/jaw_onset_after_cue/c1_jaw_onset_trials.parquet
  move_ms     the jaw onset when it is <= the first-lick onset, else none: wait = move_ms (cue -> first movement),
              revup = latency - move_ms (first movement -> first lick); no jaw onset before the lick -> revup 0,
              wait = latency (the six-position rule)
Trials: licked trials of the Fig 2 trial set (stats/inputs/filtered_v1/tongue_median_xy_peak_per_trial non-sentinel
rows: DLC trial + session filter, ps47d5 epochs). Cells: per animal x cue side x epoch, the median over the pooled
trials of latency, wait and revup (as revup_cells); bars = mean over the grade's animals of the per-animal medians,
whiskers = SEM across animals, dots = per-animal sums. Descriptive (no statistics), as S10A.

Writes (refuses to overwrite): <out>/tables/c1_delay_breakdown_trials.csv.gz, c1_delay_breakdown_cells.csv,
<out>/S6_c1_first_lick_delay_breakdown_jawonly.{pdf,png,svg} (234 x 132 pt, the S10A cell size; v28b colors).
Usage: python scripts/manuscript/c1_first_lick_delay_breakdown.py <out_dir>
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import kept_trials  # noqa: E402

REMAP = {"moderate-severe": "moderate"}
EPS = [("pre", "pre"), ("acute", "ac"), ("sub_acute", "sub"), ("chronic", "chr")]
GROUPS = [(g, s) for g in ("mild", "moderate", "severe") for s in ("L", "R")]
SIDEL = {"L": "ipsi", "R": "contra"}
MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")


def trials(r: PathResolver) -> pd.DataFrame:
    t = kept_trials(r, "tongue_median_xy_peak_per_trial")[["animal", "date", "trial_idx", "side", "epoch_label"]]
    t = t.drop_duplicates()
    jaw = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "tongue_jaw_mismatch" / "jaw_onset_after_cue"
                          / "c1_jaw_onset_trials.parquet", columns=["animal", "date", "trial_index", "side", "onset_ms",
                                                                     "moved_after_cue"])
    jaw["date"] = pd.to_datetime(jaw["date"], format="%Y%m%d").dt.date
    out = []
    for (animal, date), tr in t.groupby(["animal", "date"]):
        d = date if isinstance(date, datetime.date) else pd.Timestamp(date).date()
        le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                             / f"{d.strftime('%Y%m%d')}.parquet", columns=["trial", "side", "t_ms", "rise_start_ms"])
        le = le[(le.t_ms >= 70) & (le.t_ms <= 3000)].sort_values("t_ms")
        fl = le.groupby(["trial", "side"], as_index=False).first().rename(columns={"trial": "trial_idx"})
        x = tr.assign(trial_idx=tr.trial_idx.astype(int), date=d).merge(fl.assign(trial_idx=fl.trial_idx.astype(int)),
                                                                        on=["trial_idx", "side"], how="inner")
        out.append(x)
    T = pd.concat(out, ignore_index=True)
    T = T.merge(jaw.rename(columns={"trial_index": "trial_idx"}), on=["animal", "date", "trial_idx", "side"], how="left")
    T["latency_ms"] = T.rise_start_ms.astype(float)
    jaw_before = T.onset_ms.notna() & (T.onset_ms <= T.latency_ms)
    T["jaw_before_lick"] = jaw_before
    T["wait_ms"] = np.where(jaw_before, T.onset_ms, T.latency_ms)
    T["revup_ms"] = T.latency_ms - T.wait_ms
    info = load_animals()
    T["grade"] = T.animal.map(lambda a: REMAP.get(info[a].recovery_phenotype, info[a].recovery_phenotype))
    return T


def render(C: pd.DataFrame, stem: Path) -> None:
    sys.path.insert(0, str(MC))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.transforms as mt
    import vls_style as S
    S.apply()
    FS = 6.5
    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
                         "legend.fontsize": FS, "axes.labelpad": 1.5, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
                         "ytick.major.width": 0.6, "xtick.major.size": 2.0, "ytick.major.size": 2.0,
                         "xtick.major.pad": 1.5, "ytick.major.pad": 1.5, "font.family": "Arial"})
    CW, CR = "#8C8C8C", "#F5C27A"                       # S10A v28b: grey under light amber, thin whiskers
    EB = dict(elinewidth=0.45, capsize=0.8, capthick=0.45)
    W, H, L, B, AXW, AXH = 234.0, 132.0, 40.0, 38.0, 188.0, 72.0
    fig = plt.figure(figsize=(W / 72, H / 72))
    ax = fig.add_axes([L / W, B / H, AXW / W, AXH / H])
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    x0, ticks, tl = 0.0, [], []
    for g, s in GROUPS:
        st = x0
        for e, el in EPS:
            c = C[(C.grade == g) & (C.side == s) & (C.epoch_label == e)]
            if c.empty:
                x0 += 1
                continue
            w, r = c.wait_med_ms.to_numpy(), c.revup_med_ms.to_numpy()
            ax.bar(x0, w.mean(), 0.8, color=CW, edgecolor="0.3", lw=0.4)
            ax.bar(x0, r.mean(), 0.8, bottom=w.mean(), color=CR, edgecolor="0.3", lw=0.4)
            if len(c) > 1:
                ax.errorbar(x0 - 0.15, w.mean(), yerr=w.std(ddof=1) / np.sqrt(len(w)), fmt="none", ecolor="0.15", **EB)
                ax.errorbar(x0 + 0.15, w.mean() + r.mean(), yerr=r.std(ddof=1) / np.sqrt(len(r)), fmt="none",
                            ecolor="0.15", **EB)
            ep = {"sub_acute": "subacute"}.get(e, e)
            ax.scatter(np.full(len(c), x0) + np.linspace(-0.25, 0.25, len(c)), w + r, s=5, color=S.EP_DARK[ep],
                       edgecolor="white", lw=0.3, zorder=4)
            ticks.append(x0)
            tl.append(el)
            x0 += 1
        ax.text((st + x0 - 1) / 2, 0.0, f"{g}\n{SIDEL[s]}", ha="center", va="top", fontsize=FS, linespacing=1.0,
                transform=ax.get_xaxis_transform() + mt.ScaledTranslation(0, -15 / 72, fig.dpi_scale_trans))
        x0 += 0.6
    ax.set_xticks(ticks)
    ax.set_xticklabels(tl, rotation=90)
    ax.set_xlim(-0.7, x0 - 0.9)
    ax.set_ylabel("median latency (ms)")
    h = [plt.Rectangle((0, 0), 1, 1, fc=CW, ec="0.3", lw=0.4, label="cue → jaw opening"),
         plt.Rectangle((0, 0), 1, 1, fc=CR, ec="0.3", lw=0.4, label="jaw opening → first lick")]
    ax.legend(handles=h, loc="upper left", frameon=False, handlelength=1.4, handleheight=0.8, labelspacing=0.3,
              borderaxespad=0.2, bbox_to_anchor=(0.0, 1.06))
    for ext in ("pdf", "png", "svg"):
        fig.savefig(f"{stem}.{ext}", dpi=600 if ext == "png" else 300)
    plt.close(fig)


def main() -> int:
    out = Path(sys.argv[1])
    stem = out / "S6_c1_first_lick_delay_breakdown_jawonly"
    tdir = out / "tables"
    files = [tdir / "c1_delay_breakdown_trials.csv.gz", tdir / "c1_delay_breakdown_cells.csv",
             *(Path(f"{stem}.{x}") for x in ("pdf", "png", "svg"))]
    clash = [str(f) for f in files if f.exists()]
    if clash:
        sys.exit("refusing to overwrite " + ", ".join(clash))
    T = trials(PathResolver())
    print("licked trials", len(T), "; jaw table matched", int(T.moved_after_cue.notna().sum()),
          "; jaw onset before the first lick", round(float(T.jaw_before_lick.mean()), 3))
    C = T.groupby(["grade", "animal", "side", "epoch_label"], as_index=False).agg(
        n=("latency_ms", "size"), lat_med_ms=("latency_ms", "median"), wait_med_ms=("wait_ms", "median"),
        revup_med_ms=("revup_ms", "median"), share_jaw_before_lick=("jaw_before_lick", "mean"))
    tdir.mkdir(parents=True, exist_ok=True)
    T.to_csv(files[0], index=False)
    C.to_csv(files[1], index=False)
    pd.set_option("display.width", 220)
    G = C.groupby(["grade", "side", "epoch_label"]).agg(n_animals=("animal", "size"), trials=("n", "sum"),
                                                        wait=("wait_med_ms", "mean"), revup=("revup_med_ms", "mean"),
                                                        lat=("lat_med_ms", "mean"),
                                                        jaw_first=("share_jaw_before_lick", "mean"))
    order = {e: i for i, (e, _) in enumerate(EPS)}
    G = G.reset_index().sort_values(["grade", "side", "epoch_label"], key=lambda s: s.map(order) if s.name ==
                                    "epoch_label" else s)
    print(G.round(1).to_string(index=False))
    print(C.sort_values(["grade", "side", "animal"]).round(1).to_string(index=False))
    render(C, stem)
    print("wrote", stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
