"""Side-by-side Fig 2E versions for Priya (CC-B, 2026-11-23): four versions x two cue sides, one shared y scale,
drawn with the c1_panels.render drawing code (same markers, colors, star rule and positions).
  1 LIVE: per-trial median of licks 1-5 (old tables, old sheet)      2 licks 1-5, session mean (item 19)
  3 all licks, rise to fall, session mean                           4 all licks, onset to peak, session mean (NEW)
Usage: python scripts/manuscript/c1_f2e_compare.py <out_png>"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path.insert(0, str(MC))
import c1_panels as C  # noqa: E402

S = C.S
ROOT = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = ROOT / "results/phenotype_pooled/3_tier"


def sess(slug):
    d = pd.read_csv(ROOT / "inputs/sessmean_licks" / f"{slug}_per_session.csv")
    return d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]]


V = [("1  LIVE 2E: per-trial median, licks 1-5", C.per_session_scalar(ROOT, "tongue_median_vxy_peak_per_trial"),
      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv"), None, "tongue_median_vxy_peak_per_trial"),
     ("2  licks 1-5, session mean", sess("tongue_sessmean_vxy_peak"),
      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv"), "scalar", "tongue_sessmean_vxy_peak"),
     ("3  all licks, rise to fall, session mean", sess("tongue_alllicks_sessmean_vxy_peak"),
      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_sessmean.csv"), "scalar",
      "tongue_alllicks_sessmean_vxy_peak"),
     ("4  all licks, onset to peak, session mean (NEW)", sess("tongue_alllicks_onsetpeak_sessmean_vxy_peak"),
      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_onsetpeak_sessmean.csv"), "scalar",
      "tongue_alllicks_onsetpeak_sessmean_vxy_peak")]
D = [C.baseline(s, 1) for _, s, _, _, _ in V]
allv = pd.concat([d.delta for d in D])
lo, hi = allv.quantile(0.01), allv.quantile(0.99)
span = hi - lo
y0, y1 = lo - 0.08 * span, hi + 0.42 * span
fig, axes = plt.subplots(1, 8, figsize=(13.5, 2.4), sharey=True,
                         gridspec_kw=dict(wspace=0.12, width_ratios=[1, 1, 1, 1, 1, 1, 1, 1]))
for g, ((title, _, sheet, fam, ep), d) in enumerate(zip(V, D)):
    for j, side in enumerate(("L", "R")):
        ax = axes[2 * g + j]
        ds = d[d.side == side]
        S.zero_line(ax)
        for k, ph in enumerate(C.PHENOS):
            dp = ds[ds.ph == ph]; xs, ms, es = [], [], []
            for i, (e, _) in enumerate(C.EPOCHS):
                v = dp[dp.epoch_label == e].delta
                if v.empty:
                    continue
                off = (k - 1) * 0.09
                ax.scatter(i + off + np.random.default_rng(i + 10 * k).uniform(-.03, .03, len(v)), v, s=4,
                           color=S.SEV[ph], alpha=0.18, lw=0, zorder=1)
                xs.append(i + off); ms.append(v.mean()); es.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0)
            ax.errorbar(xs, ms, yerr=es, color=S.SEV[ph], marker=S.SEV_MK[ph], ms=3.6, mec='k', mew=0.35,
                        lw=0, elinewidth=0.9, capsize=0, zorder=3)
            for jj in range(len(xs) - 1):
                gap = round(xs[jj + 1] - xs[jj]) > 1
                ax.plot(xs[jj:jj + 2], ms[jj:jj + 2], '--' if gap else '-', color=S.SEV[ph], lw=1.0, zorder=2)
        ax.set_xticks(range(4)); ax.set_xticklabels([n for _, n in C.EPOCHS], rotation=32, ha='right', rotation_mode='anchor')
        ax.set_xlim(-0.5, 3.5); ax.set_ylim(y0, y1)
        ax.set_title(C.SIDE_T[side], fontsize=7, pad=2)
        for row, ph in enumerate(['severe', 'moderate', 'mild']):
            for i, (e, _) in enumerate(C.EPOCHS[1:], start=1):
                if C.stars_for(sheet, fam, ep, ph, side, e):
                    ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), '**', color=S.SEV[ph], ha='center', va='center',
                            fontsize=8, fontweight='bold')
    x_mid = (axes[2 * g].get_position().x0 + axes[2 * g + 1].get_position().x1) / 2
    fig.text(x_mid, 0.97, title, ha='center', va='top', fontsize=8, fontweight='bold')
axes[0].set_ylabel('Δ peak speed (px/s)')
fig.subplots_adjust(left=0.05, right=0.995, bottom=0.25, top=0.80)
for g in range(4):   # re-place titles after layout
    pass
fig.texts.clear()
for g, (title, *_r) in enumerate(V):
    x_mid = (axes[2 * g].get_position().x0 + axes[2 * g + 1].get_position().x1) / 2
    fig.text(x_mid, 0.97, title, ha='center', va='top', fontsize=8, fontweight='bold')
fig.text(0.5, 0.005, "Two-tone Fig 2E versions; change from each animal's pre-stroke mean; ** = MWU q < 0.05 (BH, scalar family) "
         "and nested-bootstrap 95% CI excludes 0; colors: mild / moderate / severe", ha='center', va='bottom', fontsize=6.5)
fig.savefig(sys.argv[1], dpi=200)
print("wrote", sys.argv[1])
