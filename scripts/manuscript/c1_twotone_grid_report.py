"""Two-tone star grid: tables (grid, star counts, gains / losses vs live and vs adopted) and comparison PNGs.
Reads <out>/tables/grid_cells_grid_ccB1123.csv and <out>/per_session/ written by c1_twotone_grid.py.
PNG 1: rows = speed, protrusion; columns = all licks (i)-(iii), licks 1-5 (i)-(iii), each with both cue sides.
PNG 2: first lick (i), (ii). Same y scale per row across both PNGs; marks as drawn (* star, dagger), dotted bridge.
Usage: python scripts/manuscript/c1_twotone_grid_report.py <out_dir>"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path.insert(0, str(MC))
import c1_panels as C  # noqa: E402

S = C.S
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
from scripts.manuscript.c1_bridge_v29style import BRIDGE  # noqa: E402

DAG = "\u2020"
SUF = "_grid_ccB1123"
R3 = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats/results/phenotype_pooled/3_tier")
OUT = Path(sys.argv[1])
T = OUT / "tables"
G = pd.read_csv(T / f"grid_cells{SUF}.csv", keep_default_na=False, na_values=[""])
G["mark"] = G["mark"].fillna("")
LIVE = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv").query("family == 'scalar'")
LIVEXY = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")
FIN = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv").query("family == 'scalar'")
K = ["recovery_phenotype", "side", "post_epoch"]
LS_T = {"all": "all licks", "l15": "licks 1-5", "first": "first lick"}
SM_T = {"mean": "(i) mean", "median": "(ii) median", "trialmed": "(iii) per-trial median, then mean"}
SM_S = {"mean": "(i)", "median": "(ii)", "trialmed": "(iii)"}
ORDER = [("mild", "L", "acute"), ("mild", "L", "sub_acute"), ("mild", "L", "chronic"),
         ("mild", "R", "acute"), ("mild", "R", "sub_acute"), ("mild", "R", "chronic"),
         ("moderate", "L", "acute"), ("moderate", "L", "sub_acute"), ("moderate", "L", "chronic"),
         ("moderate", "R", "acute"), ("moderate", "R", "sub_acute"), ("moderate", "R", "chronic"),
         ("severe", "L", "sub_acute"), ("severe", "L", "chronic"), ("severe", "R", "sub_acute"),
         ("severe", "R", "chronic")]
EPS = {"acute": "ac", "sub_acute": "sub", "chronic": "chr"}
SIDES = {"L": "ipsi", "R": "contra"}
VERS = [("all", "mean"), ("all", "median"), ("all", "trialmed"), ("l15", "mean"), ("l15", "median"),
        ("l15", "trialmed"), ("first", "mean"), ("first", "median")]


def ref(meas, ls, which):
    """Reference cells: live panel or adopted (final family)."""
    if which == "live":
        if ls == "first":
            return (LIVEXY, "tongue_lick1_xy_peak") if meas == "xy" else (None, None)
        return (LIVE, "tongue_median_vxy_peak_per_trial") if meas == "speed" else (LIVEXY, "tongue_median_xy_peak_per_trial")
    ep = {"first": {"speed": "tongue_lick1_onsetpeak_vxy_peak", "xy": "tongue_lick1_xy_peak"}}.get(
        ls, {"speed": "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "xy": "tongue_sessmean_xy_peak"})[meas]
    return FIN, ep


def md(df):
    """Markdown table without tabulate."""
    def c(x):
        return f"{x:.4g}" if isinstance(x, float) else str(x)
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(c(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def fmt(v, meas):
    if not np.isfinite(v):
        return ""
    return f"{v:.0f}" if meas == "speed" else f"{v:.1f}"


rows, wide, changes, counts = [], [], [], []
for meas in ("speed", "xy"):
    for ls, sm in VERS:
        g = G[(G.measure == meas) & (G.lick_set == ls) & (G.summary == sm)].set_index(K)
        refs = {}
        for which in ("live", "adopted"):
            sh, ep = ref(meas, ls, which)
            refs[which] = None if sh is None else sh[sh.endpoint == ep].set_index(K)
        w = {"measure": meas, "lick set": LS_T[ls], "summary": SM_S[sm]}
        for k in ORDER:
            c = g.loc[k]
            eff = c.nb_effect if np.isfinite(c.nb_effect) else c.wa1_effect
            lo = c.nb_ci_lo if np.isfinite(c.nb_effect) else c.wa1_ci_lo
            hi = c.nb_ci_hi if np.isfinite(c.nb_effect) else c.wa1_ci_hi
            rec = dict(measure=meas, lick_set=ls, summary=sm, grade=k[0], cue=SIDES[k[1]], epoch=k[2],
                       effect=eff, ci_lo=lo, ci_hi=hi, n_animals=c.nb_n_animals, q=c.mwu_session_p_fdr, mark=c.mark,
                       ci_type="within-animal (#5)" if c.single_animal else "nested")
            for which, rf in refs.items():
                s_ref = None if rf is None else bool(rf.loc[k].headline_and_bootstrap_sig)
                rec[f"star_{which}"] = s_ref
                if s_ref is not None and s_ref != (c.mark == "*"):
                    changes.append(dict(measure=meas, lick_set=ls, summary=sm, vs=which, grade=k[0], cue=SIDES[k[1]],
                                        epoch=k[2], change="GAINED" if c.mark == "*" else "LOST",
                                        ref_effect=rf.loc[k].nb_effect, new_effect=eff, new_q=c.mwu_session_p_fdr,
                                        new_ci=f"[{fmt(lo, meas)}, {fmt(hi, meas)}]"))
            rows.append(rec)
            w[f"{k[0][:3]} {SIDES[k[1]]} {EPS[k[2]]}"] = f"{fmt(eff, meas)}{c.mark}" if np.isfinite(eff) else "1 animal"
        wide.append(w)
        cnt = dict(measure=meas, lick_set=LS_T[ls], summary=SM_T[sm], stars=int((g["mark"] == "*").sum()),
                   daggers=int((g["mark"] == DAG).sum()))
        for which, rf in refs.items():
            cnt[f"stars_{which}"] = "" if rf is None else int(rf.headline_and_bootstrap_sig.sum())
        counts.append(cnt)
L = pd.DataFrame(rows); W = pd.DataFrame(wide); CH = pd.DataFrame(changes); CN = pd.DataFrame(counts)
L.to_csv(T / f"grid_long{SUF}.csv", index=False, encoding="utf-8")
W.to_csv(T / f"grid_wide{SUF}.csv", index=False, encoding="utf-8")
CH.to_csv(T / f"star_changes{SUF}.csv", index=False, encoding="utf-8")
CN.to_csv(T / f"star_counts{SUF}.csv", index=False, encoding="utf-8")
# per-version totals (both measures)
TOT = L.groupby(["lick_set", "summary"]).agg(stars=("mark", lambda m: int((m == "*").sum())),
                                             daggers=("mark", lambda m: int((m == DAG).sum()))).reset_index()
TOT.to_csv(T / f"star_totals_per_version{SUF}.csv", index=False)
with open(T / f"grid_tables{SUF}.md", "w", encoding="utf-8") as f:
    for meas in ("speed", "xy"):
        f.write(f"\n### {meas}\n\n" + W[W.measure == meas].drop(columns="measure").pipe(md) + "\n")
    f.write("\n### Star counts\n\n" + md(CN) + "\n")
    f.write("\n### Gains and losses\n\n" + md(CH) + "\n")
print(CN.to_string()); print(TOT.to_string()); print(CH.to_string())


# ---------------- figures
def sess(meas, ls, sm):
    d = pd.read_csv(OUT / "per_session" / f"tt_{meas}_{ls}_{sm}{SUF}_per_session.csv")
    return C.baseline(d[d.passes_min_licks][["animal", "date", "side", "value", "epoch_label"]], 1)


def draw(ax, d, side, g, y0, y1, meas):
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
    for row, ph in enumerate(['severe', 'moderate', 'mild']):
        for i, (e, _) in enumerate(C.EPOCHS[1:], start=1):
            m = g[(g.recovery_phenotype == ph) & (g.side == side) & (g.post_epoch == e)]
            if m.empty or not m.iloc[0]["mark"]:
                continue
            mk = m.iloc[0]["mark"]
            ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), "**" if mk == "*" else DAG, color=S.SEV[ph],
                    ha='center', va='center', fontsize=8 if mk == "*" else 6, fontweight='bold')


MEAS = [("speed", "Δ peak speed, onset to peak (px/s)"), ("xy", "Δ peak protrusion, xy (px)")]
D = {(m, ls, sm): sess(m, ls, sm) for m, _ in MEAS for ls, sm in VERS}
YL = {}
for m, _ in MEAS:
    allv = pd.concat([D[(m, ls, sm)].delta for ls, sm in VERS]); lo, hi = allv.quantile(0.01), allv.quantile(0.99)
    sp = hi - lo; YL[m] = (lo - 0.08 * sp, hi + 0.42 * sp)
for name, vers in (("twotone_grid_alllicks_licks15", VERS[:6]), ("twotone_grid_firstlick", VERS[6:])):
    nc = 2 * len(vers)
    fig, axes = plt.subplots(2, nc, figsize=(1.0 * nc + 0.9, 4.9), squeeze=False)
    for r, (m, ylab) in enumerate(MEAS):
        for v, (ls, sm) in enumerate(vers):
            g = G[(G.measure == m) & (G.lick_set == ls) & (G.summary == sm)]
            for j, side in enumerate(("L", "R")):
                ax = axes[r, 2 * v + j]
                draw(ax, D[(m, ls, sm)], side, g, *YL[m], m)
                if v or j:
                    ax.tick_params(labelleft=False)
        axes[r, 0].set_ylabel(ylab)
    fig.subplots_adjust(left=0.75 / (1.0 * nc + 0.9), right=0.995, bottom=0.13 if nc >= 8 else 0.17, top=0.88, wspace=0.12, hspace=0.68)
    for r, (m, _) in enumerate(MEAS):
        for v, (ls, sm) in enumerate(vers):
            a, b = axes[r, 2 * v].get_position(), axes[r, 2 * v + 1].get_position()
            n = int((G[(G.measure == m) & (G.lick_set == ls) & (G.summary == sm)]["mark"] == "*").sum())
            fig.text((a.x0 + b.x1) / 2, a.y1 + 0.045, f"{LS_T[ls]}, {SM_S[sm]}\n{n} stars", ha="center",
                     va="bottom", fontsize=7, fontweight="bold")
    foot = ("Two-tone, mice #1-#8; change from each animal's own pre-stroke mean. (i) session mean, (ii) session "
             "median, (iii) per-trial median then session mean.\n** = MWU q < 0.05 (BH, 518-cell scalar family, this "
             "version swapped in) and nested-bootstrap 95% CI excludes 0; " + DAG + " = one animal (#5): q < 0.05 and "
             "within-animal CI excludes 0")
    if nc < 8:   # narrow figure: wrap the footer
        import textwrap
        foot = "\n".join(textwrap.wrap(foot.replace("\n", " "), 95))
    fig.text(0.5, 0.005, foot, ha="center", va="bottom", fontsize=6)
    fig.savefig(OUT / f"{name}{SUF}.png", dpi=200)
    fig.savefig(OUT / f"{name}{SUF}.pdf")
    print("wrote", OUT / f"{name}{SUF}.png")
