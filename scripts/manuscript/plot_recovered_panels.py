"""Re-render the manuscript panels whose original plotting code was not preserved.

Figure 1 F/G (caudoputamen area quantification, body weights) and the
videofluoroscopy panels (Figure 2 B/C in the current layout, supplementary forest)
were made outside this repository. ``extract_svg_series.py`` recovers their plotted
values from the published SVGs into ``data/recovered_figure_series/*.csv``; this
script redraws the panels from those tables, so every manuscript figure has code
that regenerates it from a checked-in data file.

The tables are a recovery of what the figure drew, not the upstream measurements.
Swap in the real source table (same tidy columns) if it turns up, and these panels
are then reproducible from source.

Usage::

    python scripts/manuscript/plot_recovered_panels.py <out_dir> [--figures Figure1_weights_normalized ...]
    python scripts/manuscript/plot_recovered_panels.py <out_dir> --data-dir data/recovered_figure_series
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["pdf.fonttype"] = 42

PHENO_BY_COLOR = {"#f2c12e": "mild", "#f0822e": "moderate", "#b4001e": "severe"}
N_ANIMALS = {"mild": 4, "moderate": 2, "severe": 2}

# figure -> (title, xlabel, ylabel, figsize, legend)
SPEC = {
    "Figure1_weights_normalized": (
        "Weights normalized to pre-stroke baseline",
        "Day relative to last pre-stroke session",
        "Weight (% pre-stroke baseline)", (7.9, 4.1), "phenotype"),
    "Figure1_weights_by_phenotype": (
        "Body weight by phenotype",
        "Day, relative to last pre-stroke session",
        "Weight (% pre-stroke baseline)", (7.9, 4.1), "phenotype"),
    "Figure1_caudoputamen_quant": (
        "Caudoputamen ipsi/contra % area", "", "Ipsi/contra % area",
        (5.1, 3.0), "phenotype"),
    "Figure1_caudoputamen_by_severity": (
        "Infarct area quantification", "Stroke phenotype severity",
        "Ipsi/contra % area", (5.1, 3.0), "phenotype"),
    "Figure4B_vfss_licks_per_swallow": (
        "Licks per swallow", "", "fold of pre-stroke", (4.4, 3.2), "animal"),
    "Figure4C_vfss_inter_swallow_interval": (
        "Inter-swallow interval", "", "fold of pre-stroke", (4.4, 3.2), "animal"),
    "FigureS5_vfss_forest": (
        "Videofluoroscopy effect sizes", "",
        "fold-change vs within-animal pre-stroke (95% CI)", (8.0, 11.0), None),
}
CAT_ORDER = {"Figure4B_vfss_licks_per_swallow": ["pre1", "pre2", "post1", "post2"],
             "Figure4C_vfss_inter_swallow_interval": ["pre1", "pre2", "post1", "post2"],
             "Figure1_caudoputamen_quant": ["PS47", "PS48", "PS49", "PS50",
                                            "PS46", "PS51", "PS54", "PS55"],
             "Figure1_caudoputamen_by_severity": ["mild", "moderate", "severe"]}


def _is_gridline(g: pd.DataFrame) -> bool:
    """A 2-point horizontal line = grid line or zero rule, not data."""
    if len(g) != 2:
        return False
    ys = _numeric(g.y)
    return bool(ys.notna().all() and abs(ys.iloc[0] - ys.iloc[1]) < 1e-9)


def _numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def render(d: pd.DataFrame, figure: str, out_stem: Path) -> None:
    title, xlab, ylab, figsize, legend_kind = SPEC.get(
        figure, (figure.replace("_", " "), "", "", (6.0, 4.0), None))
    fig, ax = plt.subplots(figsize=figsize)
    order = CAT_ORDER.get(figure)
    categorical = order is not None
    if not categorical and _numeric(d.x).isna().all():
        order = list(dict.fromkeys(d.x.astype(str)))      # categorical x, unlabelled
        categorical = True
    # a categorical y axis (the forest plot's endpoint rows)
    ycat = (list(dict.fromkeys(d.y.astype(str)))
            if _numeric(d.y).isna().all() else None)

    def xpos(v):
        if not categorical:
            return _numeric(pd.Series([v])).iloc[0]
        return order.index(v) if v in order else float("nan")

    def ypos(series):
        if ycat is None:
            return _numeric(series)
        return pd.Series([ycat.index(str(v)) if str(v) in ycat else float("nan")
                          for v in series])

    seen_pheno = set()
    for (kind, artist), g in d.groupby(["kind", "artist"], sort=True):
        if kind in ("bar", "bar_base"):
            continue                                    # axes frame / spans
        col = (g.color.dropna().iloc[0] if g.color.notna().any() else "") or "#444444"
        if kind == "line":
            if _is_gridline(g):
                continue
            x = [xpos(v) for v in g.x]
            y = ypos(g.y)
            ph = PHENO_BY_COLOR.get(col)
            lab = None
            if legend_kind == "phenotype" and ph and ph not in seen_pheno:
                lab = f"{ph} (n={N_ANIMALS[ph]})"
                seen_pheno.add(ph)
            ax.plot(x, y, "-", color=col, lw=1.6, alpha=0.9, label=lab,
                    marker="o" if categorical else None, ms=4)
        elif kind == "scatter":
            ax.scatter([xpos(v) for v in g.x], ypos(g.y), s=18, color=col,
                       alpha=0.75, linewidths=0)
        elif kind == "marker" and len(g) > 1:
            ax.plot([xpos(v) for v in g.x], ypos(g.y), "o", color=col, ms=5,
                    alpha=0.9)
    if categorical:
        ax.set_xticks(range(len(order)), order)
    if ycat is not None:
        ax.set_yticks(range(len(ycat)), ycat, fontsize=8)
    ax.set_title(title, fontsize=12, fontweight="bold")
    if xlab:
        ax.set_xlabel(xlab, fontsize=11)
    ax.set_ylabel(ylab, fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    if legend_kind == "phenotype" and seen_pheno:
        ax.legend(title="phenotype", fontsize=9, title_fontsize=9, frameon=True)
    fig.text(0.005, 0.005,
             "redrawn from data recovered from the published SVG "
             "(data/recovered_figure_series)", fontsize=6, style="italic",
             color="#777777")
    fig.tight_layout()
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png", "pdf"):
        fig.savefig(f"{out_stem}.{ext}", dpi=200)
    plt.close(fig)
    print("wrote", out_stem)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--data-dir", type=Path,
                    default=Path(__file__).resolve().parents[2]
                    / "data" / "recovered_figure_series")
    ap.add_argument("--figures", nargs="*", default=None)
    a = ap.parse_args(argv)
    figs = a.figures or sorted(p.stem for p in a.data_dir.glob("*.csv"))
    for f in figs:
        p = a.data_dir / f"{f}.csv"
        if not p.is_file():
            print("skip (no recovered data):", f)
            continue
        render(pd.read_csv(p), f, a.out_dir / f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
