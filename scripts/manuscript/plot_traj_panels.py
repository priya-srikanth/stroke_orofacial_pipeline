"""Manuscript phase-aligned tongue trajectories with cluster-permutation
significance shading (3-tier, v3). Style matched to the June-30 manuscript
panels (traj_panels/traj_firstlick_ipsi.svg): font sizes, colors, alphas.

Usage: python3 plot_traj_panels.py <phenotype_pooled_results_dir> <out_dir>
  <phenotype_pooled_results_dir> = stats/results/phenotype_pooled
Reads, per lick set:
  phase_aligned_trajectories[_all_licks]/3_tier/v3/phenotype_pooled_phase_bin_mean_sem.csv
  phase_aligned_trajectories[_all_licks]/3_tier/v3/trajectory_cluster_permutation_bh_fdr.csv
Shading = clusters with reject == True (Maris-Oostenveld cluster permutation vs
pre-stroke, BH-FDR q<0.05); span = [start_bin/n_bins, (end_bin+1)/n_bins].
Side L = ipsilesional, R = contralesional (all-left-lesion cohort).
Y-axis shared between ipsi and contra within a lick set / signal / variant.

Outputs:
  traj_<firstlick|alllick>_<ipsi|contra>.{svg,png,pdf}   (delta tongue angle; manuscript set)
  extra/<lickset>_<signal>_<variant>_<ipsi|contra>.{svg,png,pdf}   (x, y, raw variants)
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, MaxNLocator

matplotlib.rcParams["svg.fonttype"] = "none"   # editable text in Illustrator
matplotlib.rcParams["pdf.fonttype"] = 42

# --- style (measured from the June-30 manuscript SVG) ---
FS_TITLE, FS_COL, FS_ROW, FS_XLAB, FS_TICK, FS_N, FS_YLAB, FS_CAPTION = 24, 21, 18, 18, 15, 12, 19, 13
LW_MEAN, LW_ZERO = 2.6, 1.2
ZERO_COLOR = "#999999"
BAND_ALPHA, SHADE_ALPHA = 0.25, 0.16
COLORS = {"mild": "#f2c12e", "moderate": "#f0822e", "severe": "#b4001e"}
FIGSIZE = (15.5, 8.6)

PHENOS = ["mild", "moderate", "severe"]
EPOCHS = [("pre", "Pre-stroke"), ("acute", "Acute"),
          ("sub_acute", "Subacute"), ("chronic", "Chronic")]
SIDES = {"L": "ipsi", "R": "contra"}
SIDE_LONG = {"L": "ipsilesional", "R": "contralesional"}
LICKSETS = {"firstlick": ("phase_aligned_trajectories", "First-lick"),
            "alllick": ("phase_aligned_trajectories_all_licks", "All-lick")}
SIGNALS = {"angle_deg": ("tongue angle", "deg"),
           "x_centered": ("tongue x", "px"),
           "y_centered": ("tongue y", "px")}
CAPTION = ("Shaded = cluster-based permutation–significant phase window "
           "vs pre-stroke (BH-FDR q<0.05)")


def render(d, c, ylim, *, title, ylabel, out_stem):
    fig, axes = plt.subplots(3, 4, figsize=FIGSIZE, sharex=True, sharey=True)
    for i, ph in enumerate(PHENOS):
        col = COLORS[ph]
        dph = d[d.recovery_phenotype == ph]
        nb = int(dph.phase_bin.max()) + 1 if not dph.empty else 72
        for j, (ep, ep_name) in enumerate(EPOCHS):
            ax = axes[i, j]
            p = dph[dph.epoch_label == ep].sort_values("phase_bin")
            if ep != "pre" and not p.empty:
                cl = c[(c.recovery_phenotype == ph) & (c.post_epoch == ep) & (c.reject == True)]
                for _, r in cl.iterrows():
                    ax.axvspan(r.start_bin / nb, (r.end_bin + 1) / nb,
                               facecolor=col, edgecolor=col, alpha=SHADE_ALPHA, zorder=0)
            ax.axhline(0, color=ZERO_COLOR, ls="--", lw=LW_ZERO, zorder=1)
            if not p.empty:
                x = p.phase_bin_center.values
                ax.fill_between(x, p["mean"] - p["sem"], p["mean"] + p["sem"],
                                color=col, alpha=BAND_ALPHA, lw=0, zorder=2)
                ax.plot(x, p["mean"], color=col, lw=LW_MEAN, zorder=3)
                ax.text(0.97, 0.94, f"n={int(p.n_trials.max())} trials",
                        transform=ax.transAxes, ha="right", va="top", fontsize=FS_N)
            ax.set_ylim(*ylim)
            ax.set_xlim(-0.03, 1.03)
            ax.set_xticks([0, .25, .5, .75, 1])
            ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
            ax.tick_params(axis="both", labelsize=FS_TICK)
            if i == 0:
                ax.set_title(ep_name, fontsize=FS_COL, pad=10)
            if j == 0:
                ax.set_ylabel(ph.capitalize(), fontsize=FS_ROW)
            if i == 2:
                ax.set_xlabel("Phase (0, 1)", fontsize=FS_XLAB)
    fig.tight_layout(rect=[0.045, 0.035, 1, 0.93])
    fig.suptitle(title, fontsize=FS_TITLE, fontweight="bold", y=0.99)
    fig.text(0.004, 0.5, ylabel, rotation=90, ha="left", va="center",
             multialignment="center", fontsize=FS_YLAB)
    fig.text(0.5, 0.005, CAPTION, ha="center", fontsize=FS_CAPTION, style="italic")
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png", "pdf"):
        fig.savefig(f"{out_stem}.{ext}", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("wrote", out_stem)


def main(res_root, out_dir):
    for ls_key, (subdir, ls_name) in LICKSETS.items():
        rd = res_root / subdir / "3_tier" / "v3"
        m = pd.read_csv(rd / "phenotype_pooled_phase_bin_mean_sem.csv")
        cc = pd.read_csv(rd / "trajectory_cluster_permutation_bh_fdr.csv")
        for sig, (sig_name, unit) in SIGNALS.items():
            for var in ("delta", "raw"):
                dd = m[(m.signal == sig) & (m.variant == var)
                       & m.recovery_phenotype.isin(PHENOS)]
                if dd.empty:
                    continue
                lo = min(0.0, (dd["mean"] - dd["sem"]).min())
                hi = (dd["mean"] + dd["sem"]).max()
                pad = 0.05 * (hi - lo)
                ylim = (lo - pad, hi + pad)
                if var == "delta":
                    ylabel = f"Delta {sig_name}\n(norm. to pre-stroke across lick phase)"
                else:
                    ylabel = f"{sig_name[0].upper() + sig_name[1:]} ({unit})"
                for side, s_short in SIDES.items():
                    d = dd[dd.side == side]
                    c = cc[(cc.signal == sig) & (cc.variant == var) & (cc.side == side)]
                    title = f"{ls_name} {sig_name} trajectory, {SIDE_LONG[side]} trials"
                    if var == "raw":
                        title += " (raw)"
                    if sig == "angle_deg" and var == "delta":
                        stem = out_dir / f"traj_{ls_key}_{s_short}"
                    else:
                        stem = out_dir / "extra" / f"traj_{ls_key}_{sig}_{var}_{s_short}"
                    render(d, c, ylim, title=title, ylabel=ylabel, out_stem=stem)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
