"""Licks 1-5 candidate: single panels (live 2D/2E style) and a comparison PNG (rows = speed, protrusion; columns = live,
adopted all-lick, licks 1-5 candidate; both cue sides; one y scale per row; stars as drawn). CC-B, 2026-11-23 late.
Usage: python scripts/manuscript/c1_licks15_compare.py <out_dir>"""
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path.insert(0, str(MC))
import c1_panels as C  # noqa: E402

S = C.S
ROOT = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = ROOT / "results/phenotype_pooled/3_tier"
out = Path(sys.argv[1])


def sess(slug):
    d = pd.read_csv(ROOT / "inputs/sessmean_licks" / f"{slug}_per_session.csv")
    return d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]]


LIVE = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv")
LIVEXY = pd.concat([LIVE, pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")])
FIN = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv")
CAND = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_licks15_candidate.csv")
ROWS = [("peak speed (px/s)", [
            ("LIVE: per-trial median, licks 1-5", C.per_session_scalar(ROOT, "tongue_median_vxy_peak_per_trial"), LIVE, None,
             "tongue_median_vxy_peak_per_trial"),
            ("ADOPTED: all licks, onset to peak, mean", sess("tongue_alllicks_onsetpeak_sessmean_vxy_peak"), FIN, "scalar",
             "tongue_alllicks_onsetpeak_sessmean_vxy_peak"),
            ("CANDIDATE: licks 1-5, onset to peak, mean", sess("tongue_licks15_onsetpeak_vxy_peak"), CAND, "scalar",
             "tongue_licks15_onsetpeak_vxy_peak")]),
        ("peak protrusion, xy (px)", [
            ("LIVE: per-trial median, all licks", C.per_session_scalar(ROOT, "tongue_median_xy_peak_per_trial"), LIVEXY, None,
             "tongue_median_xy_peak_per_trial"),
            ("ADOPTED: all licks, mean", sess("tongue_sessmean_xy_peak"), FIN, "scalar", "tongue_sessmean_xy_peak"),
            ("CANDIDATE: licks 1-5, mean", sess("tongue_licks15_xy_peak"), CAND, "scalar", "tongue_licks15_xy_peak")])]


def draw(ax, d, side, sheet, fam, ep, y0, y1):
    ds = d[d.side == side]
    S.zero_line(ax)
    for k, ph in enumerate(C.PHENOS):
        dp = ds[ds.ph == ph]; xs, ms, es = [], [], []
        for i, (e, _) in enumerate(C.EPOCHS):
            v = dp[dp.epoch_label == e].delta
            if v.empty:
                continue
            off = (k - 1) * 0.09
            ax.scatter(i + off + np.random.default_rng(i + 10 * k).uniform(-.03, .03, len(v)), v, s=4, color=S.SEV[ph],
                       alpha=0.18, lw=0, zorder=1)
            xs.append(i + off); ms.append(v.mean()); es.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0)
        ax.errorbar(xs, ms, yerr=es, color=S.SEV[ph], marker=S.SEV_MK[ph], ms=3.6, mec='k', mew=0.35, lw=0,
                    elinewidth=0.9, capsize=0, zorder=3)
        for j in range(len(xs) - 1):
            gap = round(xs[j + 1] - xs[j]) > 1
            ax.plot(xs[j:j + 2], ms[j:j + 2], '--' if gap else '-', color=S.SEV[ph], lw=1.0, zorder=2)
    ax.set_xticks(range(4)); ax.set_xticklabels([n for _, n in C.EPOCHS], rotation=32, ha='right', rotation_mode='anchor')
    ax.set_xlim(-0.5, 3.5); ax.set_ylim(y0, y1)
    ax.set_title(C.SIDE_T[side], fontsize=7, pad=2)
    for row, ph in enumerate(['severe', 'moderate', 'mild']):
        for i, (e, _) in enumerate(C.EPOCHS[1:], start=1):
            if C.stars_for(sheet, fam, ep, ph, side, e):
                ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), '**', color=S.SEV[ph], ha='center', va='center',
                        fontsize=8, fontweight='bold')


# single panels (candidate), live renderer and size
matplotlib.rcParams["axes.labelpad"] = 1.5
C.render(C.baseline(sess("tongue_licks15_onsetpeak_vxy_peak"), 1), CAND, "scalar", "tongue_licks15_onsetpeak_vxy_peak",
         "Δ peak speed,\nlicks 1-5 (px/s)", str(out / "F2_speed_licks15_lp_ps47d5_onsetpeak_candidate"))
C.render(C.baseline(sess("tongue_licks15_xy_peak"), 1), CAND, "scalar", "tongue_licks15_xy_peak",
         "Δ peak protrusion, xy,\nlicks 1-5 (px)", str(out / "S_xy_licks15_lp_ps47d5_candidate"))
# comparison PNG
fig, axes = plt.subplots(2, 6, figsize=(10.5, 4.9))
for r, (ylab, vers) in enumerate(ROWS):
    D = [C.baseline(s, 1) for _, s, _, _, _ in vers]
    allv = pd.concat([d.delta for d in D]); lo, hi = allv.quantile(0.01), allv.quantile(0.99); sp = hi - lo
    y0, y1 = lo - 0.08 * sp, hi + 0.42 * sp
    for g, ((title, _, sheet, fam, ep), d) in enumerate(zip(vers, D)):
        for j, side in enumerate(("L", "R")):
            ax = axes[r, 2 * g + j]
            draw(ax, d, side, sheet, fam, ep, y0, y1)
            if g or j:
                ax.tick_params(labelleft=False)
    axes[r, 0].set_ylabel("Δ " + ylab)
fig.subplots_adjust(left=0.07, right=0.995, bottom=0.11, top=0.90, wspace=0.12, hspace=0.62)
for r, (ylab, vers) in enumerate(ROWS):
    for g, (title, *_x) in enumerate(vers):
        a, b = axes[r, 2 * g].get_position(), axes[r, 2 * g + 1].get_position()
        fig.text((a.x0 + b.x1) / 2, a.y1 + 0.045, title, ha="center", va="bottom", fontsize=7.5, fontweight="bold")
fig.text(0.5, 0.005, "Two-tone; change from each animal's pre-stroke mean; ** = MWU q < 0.05 (BH, scalar family) and "
         "nested-bootstrap 95% CI excludes 0; colors: mild / moderate / severe", ha="center", va="bottom", fontsize=6.5)
fig.savefig(out / "F2DE_licks15_compare_ccB1123.png", dpi=200)
print("wrote", out / "F2DE_licks15_compare_ccB1123.png")
