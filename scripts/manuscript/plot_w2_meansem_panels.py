"""Manuscript-style mean +/- SEM W-2 occupancy panels (with ** significance).

Rebuilds the `wass_panels` style of the June-30 manuscript panels (the original
script was not saved) for the Wasserstein-2 occupancy endpoints, reading:

* per-session W-2:
  ``stats/results/phenotype_pooled/{wasserstein_recovery,normalized_wasserstein_recovery}/
  <scope>/<w2_version>/*/wasserstein_recovery_per_session.csv``
* significance: the consolidated sheet (``pooled_phenotype_stats*.csv``), columns
  ``headline_and_bootstrap_sig`` (``**``) and, when present, ``wa_sig``.

Values are plotted as the change from each animal's own pre-stroke mean, per
side; points are sessions, symbols are mean +/- SEM across sessions, and ``**``
marks cells that are FDR-significant and bootstrap-corroborated, stacked
severe (top) / moderate / mild.

Usage::

    python scripts/manuscript/plot_w2_meansem_panels.py \
        <outputs>/stats/results/phenotype_pooled \
        pooled_phenotype_stats_w2loo_within_animal.csv \
        <out_dir> [--w2-version v2_loo] [--scope 3_tier] [--sig-col headline_and_bootstrap_sig]
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["pdf.fonttype"] = 42

# Style measured from meanSEM_sig_panels/*.svg (June-30 panels).
FS_TITLE, FS_SUB, FS_PANEL, FS_TICK, FS_AXLAB, FS_STAR, FS_LEG = 14, 7, 13, 13, 15, 12, 10
COLORS = {"mild": "#f2c12e", "moderate": "#f0822e", "severe": "#b4001e"}
MARKERS = {"mild": "o", "moderate": "s", "severe": "D"}
N_ANIMALS = {"mild": 4, "moderate": 2, "severe": 2}
PHENOS = ["mild", "moderate", "severe"]          # legend order
STAR_ORDER = ["severe", "moderate", "mild"]      # top -> bottom
EPOCHS = [("pre", "Pre"), ("acute", "Acute"), ("sub_acute", "Subacute"), ("chronic", "Chronic")]
SIDE_TITLE = {"ipsi": "Ipsilesional cue (mouse-L)", "contra": "Contralesional cue (mouse-R)",
              "both": "Both cue sides"}
FAMILY_LABEL = {
    "wasserstein_recovery": ("{bp} spatial occupancy", "Δ W-2 from pre-stroke (px)"),
    "normalized_wasserstein_recovery": ("{bp} spatial occupancy (normalized)",
                                        "Δ W-2 (x pre-stroke baseline)"),
}
SUB1 = "mean ± SEM (baseline-subtracted); faded=sessions"
SUB2 = ("** = q<0.05 (session MWU+BH-FDR) & session-bootstrap CI of the "
        "post−pre difference in means excludes 0")


def load_per_session(res_root: Path, family: str, scope: str, version: str) -> pd.DataFrame:
    pat = str(res_root / family / scope / version / "*" / "wasserstein_recovery_per_session.csv")
    frames = [pd.read_csv(f) for f in sorted(glob.glob(pat))]
    if not frames:
        raise SystemExit(f"no per-session W-2 under {pat}")
    d = pd.concat(frames, ignore_index=True)
    d = d.drop_duplicates(subset=["animal", "date", "side", "endpoint", "epoch_label"])
    base = d[d.epoch_label == "pre"].groupby(["animal", "side", "endpoint"]).w2.mean()
    d["delta"] = d.w2 - d.set_index(["animal", "side", "endpoint"]).index.map(base)
    if "recovery_phenotype" not in d.columns or d["recovery_phenotype"].isna().all():
        # the normalized whisker/nose per-session writer drops the phenotype column
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        from stroke_orofacial.animals import load_animals
        amap = {a: i.recovery_phenotype for a, i in load_animals().items()}
        d["recovery_phenotype"] = d.animal.map(amap)
    d["recovery_phenotype"] = d["recovery_phenotype"].replace(
        {"moderate-severe": "moderate"})   # 3-tier scope
    return d.dropna(subset=["delta", "recovery_phenotype"])


def render(d: pd.DataFrame, sig: pd.DataFrame, *, family: str, bodypart: str,
           out_stem: Path, sig_col: str) -> None:
    sides = [s for s in ("ipsi", "contra", "both") if s in set(d.side)]
    # Canvas and axes geometry are matched exactly to the published manuscript
    # panels in ``meanSEM_sig_panels`` so these figures are drop-in replacements
    # inside the multi-panel Illustrator files:
    #   two-panel  720.0 x 331.2 pt, axes left 0.110/0.49469, w 0.30531
    #   one-panel  424.8 x 331.2 pt, axes left 0.185,         w 0.47500
    #   both       bottom 0.145, height 0.575; legend anchored at the same x
    two = len(sides) > 1
    fig, axes = plt.subplots(1, len(sides), figsize=(10.0 if two else 5.9, 4.6),
                             squeeze=False)
    axes = axes[0]
    ax_lefts = (0.110, 0.49469) if two else (0.185,)
    ax_width = 0.30531 if two else 0.47500
    legend_x = 0.82 if two else 0.70
    for ax, left in zip(axes, ax_lefts):
        ax.set_position([left, 0.145, ax_width, 0.575])
    lo = d.delta.min(); hi = d.delta.max(); span = max(hi - lo, 1e-9)
    ymin, ymax = lo - 0.05 * span, hi + 0.30 * span      # headroom for the ** band
    for ax, side in zip(axes, sides):
        ds = d[d.side == side]
        for ph in PHENOS:
            dp = ds[ds.recovery_phenotype == ph]
            if dp.empty:
                continue
            xs, ms, es = [], [], []
            for i, (ep, _) in enumerate(EPOCHS):
                v = dp[dp.epoch_label == ep].delta
                if v.empty:
                    continue
                ax.scatter([i + 0.02 * (PHENOS.index(ph) - 1)] * len(v), v, s=14,
                           color=COLORS[ph], alpha=0.16, marker=MARKERS[ph], linewidths=0)
                xs.append(i); ms.append(v.mean())
                es.append(v.std(ddof=1) / max(len(v) ** 0.5, 1) if len(v) > 1 else 0.0)
            ax.errorbar(xs, ms, yerr=es, color=COLORS[ph], marker=MARKERS[ph], ms=7,
                        lw=2, capsize=3, zorder=3)
        # ** band: one row per phenotype, severe on top
        for row, ph in enumerate(STAR_ORDER):
            y = ymax - (0.045 + 0.055 * row) * (ymax - ymin)
            for i, (ep, _) in enumerate(EPOCHS):
                if ep == "pre":
                    continue
                m = sig[(sig.family == family) & (sig.endpoint == bodypart)
                        & (sig.recovery_phenotype == ph) & (sig.side == side)
                        & (sig.post_epoch == ep)]
                if not m.empty and bool(m.iloc[0][sig_col]):
                    ax.text(i, y, "**", color=COLORS[ph], fontsize=FS_STAR,
                            ha="center", va="center", fontweight="bold")
        ax.axhline(0, color="#b2b2b2", lw=0.8, zorder=1)
        ax.set_xticks(range(len(EPOCHS)), [n for _, n in EPOCHS], fontsize=FS_TICK)
        ax.tick_params(axis="y", labelsize=FS_TICK)
        ax.set_xlabel("Epoch", fontsize=FS_AXLAB)
        ax.set_title(SIDE_TITLE[side], fontsize=FS_PANEL)
        ax.set_ylim(ymin, ymax)
        ax.spines[["top", "right"]].set_visible(False)
    title_fmt, ylab = FAMILY_LABEL[family]
    axes[0].set_ylabel(ylab, fontsize=FS_AXLAB)
    fig.suptitle(title_fmt.format(bp=bodypart.capitalize()), fontsize=FS_TITLE,
                 fontweight="bold", y=0.995)
    fig.text(0.5, 0.935, SUB1, ha="center", fontsize=FS_SUB, style="italic")
    fig.text(0.5, 0.900, SUB2, ha="center", fontsize=FS_SUB, style="italic")
    handles = [plt.Line2D([], [], color=COLORS[p], marker=MARKERS[p], ms=7, lw=2,
                          label=f"{p} (n={N_ANIMALS[p]})") for p in PHENOS]
    fig.legend(handles=handles, title="phenotype", fontsize=FS_LEG, title_fontsize=FS_LEG,
               loc="center left", bbox_to_anchor=(legend_x, 0.5), frameon=True)
    # no tight_layout / bbox_inches="tight": both would resize the canvas away
    # from the published 720 x 331.2 pt (or 424.8 x 331.2 pt) panel size.
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png", "pdf"):
        fig.savefig(f"{out_stem}.{ext}", dpi=200)
    plt.close(fig)
    print("wrote", out_stem)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_root", type=Path, help="stats/results/phenotype_pooled")
    ap.add_argument("stats_sheet", help="sheet filename inside <results_root>/<scope>/")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--scope", default="3_tier")
    ap.add_argument("--w2-version", default="v2_loo")
    ap.add_argument("--sig-col", default="headline_and_bootstrap_sig",
                    choices=("headline_and_bootstrap_sig", "wa_sig"))
    a = ap.parse_args(argv)
    sig = pd.read_csv(a.results_root / a.scope / a.stats_sheet)
    for family in FAMILY_LABEL:
        d = load_per_session(a.results_root, family, a.scope, a.w2_version)
        for bp in sorted(d.endpoint.unique()):
            render(d[d.endpoint == bp], sig, family=family, bodypart=bp,
                   out_stem=a.out_dir / f"meanSEM_{family}_{bp}", sig_col=a.sig_col)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
