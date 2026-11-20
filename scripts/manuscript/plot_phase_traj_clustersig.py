"""Phase-aligned first-lick trajectories (3-tier, v3) with cluster-permutation
significance shading. Regenerated 2026-09-16.

Inputs (stats/results/phenotype_pooled/phase_aligned_trajectories/3_tier/v3/):
  phenotype_pooled_phase_bin_mean_sem.csv   -> mean +/- SEM curves
  trajectory_cluster_permutation_bh_fdr.csv -> shaded windows (reject == True,
      i.e. BH-FDR q < 0.05, cluster vs pre-stroke)
Shading spans bin edges [start_bin/n_bins, (end_bin+1)/n_bins].
side L = ipsilesional, R = contralesional (all-left-lesion cohort).
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams["svg.fonttype"] = "none"   # editable text in Illustrator
matplotlib.rcParams["pdf.fonttype"] = 42

res_dir = Path(sys.argv[1]); out_dir = Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)
m = pd.read_csv(res_dir / "phenotype_pooled_phase_bin_mean_sem.csv")
c = pd.read_csv(res_dir / "trajectory_cluster_permutation_bh_fdr.csv")

PHENOS = ["mild", "moderate", "severe"]
COLORS = {"mild": "#F2C02A", "moderate": "#F0802C", "severe": "#B00012"}  # sampled from the manuscript panel
EPOCHS = [("pre", "Pre-stroke"), ("acute", "Acute"),
          ("sub_acute", "Subacute"), ("chronic", "Chronic")]
SIDES = {"L": "ipsilesional", "R": "contralesional"}
SIGNALS = {"angle_deg": "tongue angle", "x_centered": "tongue x", "y_centered": "tongue y"}
from matplotlib.ticker import FormatStrFormatter
VARIANTS = {"delta": "(norm. to pre-stroke across lick phase)", "raw": ""}

for sig, sig_name in SIGNALS.items():
    for var, var_lab in VARIANTS.items():
        for side, side_name in SIDES.items():
            d = m[(m.signal == sig) & (m.variant == var) & (m.side == side)]
            if d.empty:
                continue
            dd = m[(m.signal == sig) & (m.variant == var)]   # y shared across ipsi/contra
            ymin = min(0, (dd["mean"] - dd["sem"]).min()); ymax = (dd["mean"] + dd["sem"]).max()
            pad = 0.08 * (ymax - ymin)
            fig, axes = plt.subplots(3, 4, figsize=(13, 7.5), sharex=True, sharey=True)
            for i, ph in enumerate(PHENOS):
                for j, (ep, ep_name) in enumerate(EPOCHS):
                    ax = axes[i, j]
                    p = d[(d.recovery_phenotype == ph) & (d.epoch_label == ep)].sort_values("phase_bin")
                    col = COLORS[ph]
                    if ep != "pre" and not p.empty:
                        nb = int(d[d.recovery_phenotype == ph].phase_bin.max()) + 1
                        cl = c[(c.signal == sig) & (c.variant == var) & (c.side == side)
                               & (c.recovery_phenotype == ph) & (c.post_epoch == ep)
                               & (c.reject == True)]
                        for _, r in cl.iterrows():
                            ax.axvspan(r.start_bin / nb, (r.end_bin + 1) / nb,
                                       color=col, alpha=0.16, lw=0, zorder=0)
                    ax.axhline(0, color="0.5", ls="--", lw=0.8, zorder=1)
                    if not p.empty:
                        x = p.phase_bin_center.values
                        ax.fill_between(x, p["mean"] - p["sem"], p["mean"] + p["sem"],
                                        color=col, alpha=0.30, lw=0, zorder=2)
                        ax.plot(x, p["mean"], color=col, lw=2, zorder=3)
                        ax.text(0.97, 0.95, f"n={int(p.n_trials.max())} trials",
                                transform=ax.transAxes, ha="right", va="top", fontsize=9)
                    ax.set_ylim(ymin - pad, ymax + pad); ax.set_xlim(-0.03, 1.03)
                    ax.set_xticks([0, .25, .5, .75, 1])
                    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
                    ax.tick_params(axis="both", labelsize=10)
                    if i == 0: ax.set_title(ep_name, fontsize=15)
                    if j == 0: ax.set_ylabel(ph.capitalize(), fontsize=12)
                    if i == 2: ax.set_xlabel("Phase (0, 1)", fontsize=12)
            unit = "" if var == "delta" else " (deg)" if sig == "angle_deg" else " (px)"
            ylab = (f"Delta {sig_name}\n{var_lab}" if var == "delta"
                    else f"{sig_name[0].upper() + sig_name[1:]}{unit}")
            fig.supylabel(ylab, fontsize=13)
            fig.suptitle(f"First-lick {sig_name} trajectory, {side_name} trials",
                         fontsize=16, fontweight="bold")
            fig.text(0.5, -0.01, "Shaded = cluster-based permutation-significant phase window "
                     "vs pre-stroke (BH-FDR q<0.05)", ha="center", fontsize=9, style="italic")
            fig.tight_layout()
            stem = f"{sig}_{var}_{side}_{side_name}_mean_sem_clustersig"
            for ext in ("svg", "png", "pdf"):
                fig.savefig(out_dir / f"{stem}.{ext}", bbox_inches="tight", dpi=200)
            plt.close(fig)
            print("wrote", stem)
