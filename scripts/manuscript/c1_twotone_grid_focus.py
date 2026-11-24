"""Focused comparison for Priya: ALL licks vs LICKS 1-5, both per-trial median then session mean, speed (onset to
peak) and protrusion (xy). CC-B, 2026-11-23, suffix _ccB1123.
  - F2DE_alls_vs_15_pertrialmedian_ccB1123.png: rows = speed, protrusion; columns = all licks | licks 1-5 (both cue
    sides); same y scale per row; marks as drawn (** star, dagger on its own grade row), dotted faint bridge.
  - single panels (live 2D/2E renderer and size, v29dag marks): F2_speed_{all,licks15}_pertrialmedian_grid_ccB1123,
    S_xy_{all,licks15}_pertrialmedian_grid_ccB1123 (.pdf/.png/.svg).
Marks come from each version's own 518-cell family (grid_cells_grid_ccB1123.csv).
Usage: python scripts/manuscript/c1_twotone_grid_focus.py <twotone_grid_dir>"""
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c1_bridge_v29style import BRIDGE, MC  # noqa: E402
from c1_dagger_render import C_SUBS, DAG_SCALE, DAGGER, load_subst  # noqa: E402

OUT = Path(sys.argv[1])
SUF = "_grid_ccB1123"
os.environ["PIPELINE_REPO"] = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, str(MC))
# the single-panel top band is tight: shift the dagger right of the star column so it never touches a mild **
C = load_subst(MC / "c1_panels.py", "c1_panels", C_SUBS + [(
    "ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), _mk,",
    "ax.text(i + (0 if _mk == '**' else 0.34), y1 - (0.07 + 0.085 * row) * (y1 - y0), _mk,", 1)])
S = C.S
G = pd.read_csv(OUT / "tables" / f"grid_cells{SUF}.csv", keep_default_na=False, na_values=[""])
G["mark"] = G["mark"].fillna("").replace({"*": "**"})
VERS = [("all", "all licks"), ("l15", "licks 1-5")]
MEAS = [("speed", "peak speed, onset to peak (px/s)"), ("xy", "peak protrusion, xy (px)")]


def sess(meas, ls):
    d = pd.read_csv(OUT / "per_session" / f"tt_{meas}_{ls}_trialmed{SUF}_per_session.csv")
    return C.baseline(d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]], 1)


def sheet(meas, ls):
    return G[(G.measure == meas) & (G.lick_set == ls) & (G.summary == "trialmed")]


def draw(ax, d, side, g, y0, y1):
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
            if round(xs[j + 1] - xs[j]) > 1:
                ax.plot(xs[j:j + 2], ms[j:j + 2], color=S.SEV[ph], lw=1.0, **BRIDGE)
            else:
                ax.plot(xs[j:j + 2], ms[j:j + 2], '-', color=S.SEV[ph], lw=1.0, zorder=2)
    ax.set_xticks(range(4)); ax.set_xticklabels([n for _, n in C.EPOCHS], rotation=32, ha='right', rotation_mode='anchor')
    ax.set_xlim(-0.5, 3.5); ax.set_ylim(y0, y1)
    ax.spines["top"].set_visible(False)
    ax.set_title(C.SIDE_T[side], fontsize=7, pad=2)
    # one row per grade in the top band (severe, moderate, mild), so the moderate dagger never meets a mild star
    for row, ph in enumerate(['severe', 'moderate', 'mild']):
        for i, (e, _) in enumerate(C.EPOCHS[1:], start=1):
            m = g[(g.recovery_phenotype == ph) & (g.side == side) & (g.post_epoch == e)]
            if m.empty or not m.iloc[0]["mark"]:
                continue
            mk = m.iloc[0]["mark"]
            ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), mk, color=S.SEV[ph], ha='center', va='center',
                    fontsize=8 * (1 if mk == "**" else DAG_SCALE), fontweight='bold')


D = {(m, ls): sess(m, ls) for m, _ in MEAS for ls, _ in VERS}
fig, axes = plt.subplots(2, 4, figsize=(6.2, 4.9))
for r, (m, ylab) in enumerate(MEAS):
    allv = pd.concat([D[(m, ls)].delta for ls, _ in VERS]); lo, hi = allv.quantile(0.01), allv.quantile(0.99)
    sp = hi - lo; y0, y1 = lo - 0.08 * sp, hi + 0.42 * sp
    for v, (ls, _) in enumerate(VERS):
        for j, side in enumerate(("L", "R")):
            ax = axes[r, 2 * v + j]
            draw(ax, D[(m, ls)], side, sheet(m, ls), y0, y1)
            if v or j:
                ax.tick_params(labelleft=False)
    axes[r, 0].set_ylabel("Δ " + ylab)
fig.subplots_adjust(left=0.12, right=0.99, bottom=0.17, top=0.88, wspace=0.12, hspace=0.68)
for r, (m, _) in enumerate(MEAS):
    for v, (ls, title) in enumerate(VERS):
        a, b = axes[r, 2 * v].get_position(), axes[r, 2 * v + 1].get_position()
        g = sheet(m, ls)
        fig.text((a.x0 + b.x1) / 2, a.y1 + 0.045, f"{title}: per-trial median, then mean\n{int((g['mark'] == '**').sum())}"
                 f" stars, {int((g['mark'] == DAGGER).sum())} {DAGGER}", ha="center", va="bottom", fontsize=7,
                 fontweight="bold")
fig.text(0.5, 0.005, "Two-tone, mice #1-#8; change from each animal's own pre-stroke mean. ** = MWU q < 0.05 (BH,\n"
         "518-cell scalar family, this version swapped in) and nested-bootstrap 95% CI excludes 0; " + DAGGER +
         " = one animal\n(#5, moderate acute): q < 0.05 and within-animal bootstrap CI excludes 0. Dotted = severe "
         "bridge (no acute video).", ha="center", va="bottom", fontsize=6)
fig.savefig(OUT / "F2DE_alls_vs_15_pertrialmedian_ccB1123.png", dpi=200)
fig.savefig(OUT / "F2DE_alls_vs_15_pertrialmedian_ccB1123.pdf")
print("wrote focused PNG", flush=True)

# single panels, live 2D / 2E renderer and size
matplotlib.rcParams["axes.labelpad"] = 1.5
for m, stem, lab in (("speed", "F2_speed", "Δ peak speed,\n{} (px/s)"), ("xy", "S_xy", "Δ peak protrusion, xy,\n{} (px)")):
    for ls, title in VERS:
        g = sheet(m, ls).assign(family="scalar")
        tag = {"all": "all", "l15": "licks15"}[ls]
        C.render(D[(m, ls)], g, "scalar", f"tt_{m}_{ls}_trialmed{SUF}", lab.format(title),
                 str(OUT / f"{stem}_{tag}_pertrialmedian{SUF}"))
print("wrote single panels")
