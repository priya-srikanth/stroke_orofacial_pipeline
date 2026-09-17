"""Manuscript-style mean +/- SEM panels for the SCALAR endpoints (with ** significance).

Regenerates the `meanSEM_sig_panels` figures whose original script was never
saved (the June-30 renders). Same recipe as the published panels:

* per-trial values from ``stats/inputs/filtered_v1/<endpoint>/<animal>.parquet``
  when that tree exists, else ``stats/inputs/no_filter/<endpoint>/`` (matching
  ``load_scalar_family`` in ``scripts/phase_9_stats/build_pooled_phenotype_stats.py``);
  sentinels dropped, then the mean of finite values per (animal, date, side)
* baseline correction: minus that animal's own pre-stroke session mean, per side
  (``aggregators.compute_pre_baseline`` / ``apply_baseline_delta``)
* significance from the consolidated sheet ``pooled_phenotype_stats*.csv``,
  column ``headline_and_bootstrap_sig`` (``**``) or ``wa_sig`` (within-animal)

Differences from the June-30 files this replaces:

* the italic subtitle now reads "session-bootstrap CI of the post-pre difference
  in means", which is what the code actually computes (the old files said
  "bootstrap CI of median diff")
* canvas and axes geometry are pinned rather than produced by ``tight_layout`` +
  ``bbox_inches="tight"``, so every panel is exactly the published size

Usage::

    python scripts/manuscript/plot_scalar_meansem_panels.py \
        <outputs>/stats <outputs>/stats/results/phenotype_pooled/3_tier/pooled_phenotype_stats.csv \
        <out_dir> [--endpoints tongue_mean_within_bout_ili_ms tongue_lick1_t_peak_ms] \
        [--sig-col headline_and_bootstrap_sig|wa_sig]
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

# Style measured from the published meanSEM_sig_panels/*.svg (June-30 panels);
# identical to scripts/manuscript/plot_w2_meansem_panels.py.
FS_TITLE, FS_SUB, FS_PANEL, FS_TICK, FS_AXLAB, FS_STAR, FS_LEG = 14, 7, 13, 13, 15, 12, 10
COLORS = {"mild": "#f2c12e", "moderate": "#f0822e", "severe": "#b4001e"}
MARKERS = {"mild": "o", "moderate": "s", "severe": "D"}
N_ANIMALS = {"mild": 4, "moderate": 2, "severe": 2}
PHENOS = ["mild", "moderate", "severe"]          # legend order
STAR_ORDER = ["severe", "moderate", "mild"]      # top -> bottom
EPOCHS = [("pre", "Pre"), ("acute", "Acute"), ("sub_acute", "Subacute"),
          ("chronic", "Chronic")]
SIDE_TITLE = {"L": "Ipsilesional cue (mouse-L)", "R": "Contralesional cue (mouse-R)",
              "global": ""}
# the unsided endpoints (d_prime, criterion_c) are "global" in the per-trial
# inputs but "both" in the consolidated stats sheet
SIDE_IN_SHEET = {"L": "L", "R": "R", "global": "both"}
SUB1 = "mean ± SEM (baseline-subtracted); faded=sessions"
SUB2 = ("** = q<0.05 (session MWU+BH-FDR) & session-bootstrap CI of the "
        "post−pre difference in means excludes 0")

# (title, y-label) read off the published SVGs, one entry per endpoint slug.
LABELS = {
    "accuracy_difference_index": ("Accuracy-difference index", "Δ index"),
    "criterion_c": ("Response criterion (c)", "Δ c"),
    "d_prime": ("Discriminability (d′)", "Δ d′"),
    "first_lick_accuracy_all": ("First-lick accuracy (all trials)", "Δ accuracy"),
    "late_lickiness": ("Late lickiness (8–60 s)", "Δ late licks"),
    "latency_to_first_correct_lick_s": ("Latency to first correct lick", "Δ latency (s)"),
    "lickRate_byTrial": ("Lick rate (by trial)", "Δ lick rate"),
    "lick_switch_rate": ("Lick switch rate (L↔R)", "Δ switch rate"),
    "licks_per_bout": ("Licks per bout", "Δ licks/bout"),
    "mismatch_candidate_no_lick_with_jaw_move": ("Jaw move without tongue protrusion",
                                                 "Δ mismatch rate"),
    "num_all_licks_per_trial": ("All licks per trial", "Δ licks"),
    "num_correct_licks_per_trial": ("Correct licks per trial", "Δ correct licks"),
    "num_incorrect_licks_per_trial": ("Incorrect licks per trial", "Δ incorrect licks"),
    "tongue_lick1_angle_at_ypeak": ("First-lick tongue protrusion angle", "Δ angle (deg)"),
    "tongue_lick1_t_peak_ms": ("First-lick time-to-peak", "Δ t-peak (ms)"),
    "tongue_lick1_vxy_peak": ("First-lick peak tongue velocity", "Δ velocity"),
    "tongue_lick1_x_at_ypeak": ("First-lick tongue x at peak", "Δ x (px)"),
    "tongue_lick1_y_peak": ("First-lick peak tongue height", "Δ height (px)"),
    "tongue_lick2_angle_at_ypeak": ("Second-lick tongue protrusion angle", "Δ angle (deg)"),
    "tongue_lick2_t_peak_ms": ("Second-lick time-to-peak", "Δ t-peak (ms)"),
    "tongue_lick2_x_at_ypeak": ("Second-lick tongue x at peak", "Δ x (px)"),
    "tongue_lick2_y_peak": ("Second-lick peak tongue height", "Δ height (px)"),
    "tongue_lick_rate_hz": ("Tongue lick rate (Hz)", "Δ rate (Hz)"),
    "tongue_max_vxy_peak_first5": ("Max peak tongue velocity (first 5)", "Δ velocity"),
    "tongue_mean_vxy_peak_first5": ("Mean peak tongue velocity (first 5)", "Δ velocity"),
    "tongue_mean_within_bout_ili_ms": ("Mean within-bout inter-lick interval", "Δ ILI (ms)"),
    "tongue_n_left": ("Tongue licks to left", "Δ n left"),
    "tongue_n_right": ("Tongue licks to right", "Δ n right"),
    "tongue_num_correct_licks_dlc": ("Correct licks (DLC)", "Δ correct licks"),
    "tongue_num_incorrect_licks_dlc": ("Incorrect licks (DLC)", "Δ incorrect licks"),
}


def _phenotype_map() -> dict[str, str]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from stroke_orofacial.animals import load_animals
    return {a: i.recovery_phenotype for a, i in load_animals().items()}


def load_per_session(stats_root: Path, endpoint: str,
                     filter_variant: str = "auto") -> pd.DataFrame:
    """Per-session, baseline-corrected values for one scalar endpoint.

    ``filter_variant="auto"`` uses filtered_v1 when that tree exists for the
    endpoint, else no_filter -- the same precedence as ``load_scalar_family``
    in the stats build, so the panel and the significance sheet see the same
    sessions. The published June-30 panels were drawn from ``no_filter`` for
    every endpoint while the sheet used filtered_v1, which is why some of them
    show a point in a cell that carries no ``**`` and no row in the sheet (e.g.
    the severe acute point of ``tongue_mean_within_bout_ili_ms``, 11 QC-failing
    trials across PS54 and PS55). Pass ``--filter-variant no_filter`` to
    reproduce that older look.
    """
    inp = stats_root / "inputs"
    if filter_variant == "no_filter":
        src = inp / "no_filter" / endpoint
    else:
        src = inp / "filtered_v1" / endpoint
        if not src.is_dir():
            src = inp / "no_filter" / endpoint
    pqs = sorted(glob.glob(str(src / "*.parquet")))
    if not pqs:
        raise SystemExit(f"no per-trial parquet for {endpoint} under {inp}")
    df = pd.concat([pd.read_parquet(p) for p in pqs], ignore_index=True)
    if "is_sentinel" in df.columns:
        df = df[~df["is_sentinel"].astype(bool)]
    df = df.dropna(subset=["value"])
    sess = (df.groupby(["animal", "date", "side"], as_index=False)
              .agg(value=("value", "mean"), epoch_label=("epoch_label", "first")))
    base = (sess[sess.epoch_label == "pre"]
            .groupby(["animal", "side"]).value.mean().rename("baseline"))
    sess = sess.merge(base, on=["animal", "side"], how="left")
    sess["delta"] = sess.value - sess.baseline
    amap = _phenotype_map()
    sess["recovery_phenotype"] = (sess.animal.map(amap)
                                  .replace({"moderate-severe": "moderate"}))  # 3-tier
    return sess.dropna(subset=["delta", "recovery_phenotype"])


def render(d: pd.DataFrame, sig: pd.DataFrame, *, endpoint: str,
           out_stem: Path, sig_col: str) -> None:
    sides = [s for s in ("L", "R", "global") if s in set(d.side)]
    # Canvas and axes geometry are matched exactly to the published panels so
    # these are drop-in replacements inside the multi-panel Illustrator files:
    #   two-panel  720.0 x 331.2 pt, axes left 0.110/0.49469, w 0.30531
    #   one-panel  424.8 x 331.2 pt, axes left 0.185,         w 0.47500
    #   both       bottom 0.145, height 0.575; legend at y 0.407
    two = len(sides) > 1
    fig, axes = plt.subplots(1, len(sides), figsize=(10.0 if two else 5.9, 4.6),
                             squeeze=False)
    axes = axes[0]
    ax_lefts = (0.110, 0.49469) if two else (0.185,)
    ax_width = 0.30531 if two else 0.47500
    legend_x = 0.82 if two else 0.696
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
                m = sig[(sig.endpoint == endpoint) & (sig.recovery_phenotype == ph)
                        & (sig.side == SIDE_IN_SHEET.get(side, side))
                        & (sig.post_epoch == ep)]
                if not m.empty and bool(m.iloc[0][sig_col]):
                    ax.text(i, y, "**", color=COLORS[ph], fontsize=FS_STAR,
                            ha="center", va="center", fontweight="bold")
        ax.axhline(0, color="#b2b2b2", lw=0.8, zorder=1)
        ax.set_xticks(range(len(EPOCHS)), [n for _, n in EPOCHS], fontsize=FS_TICK)
        ax.tick_params(axis="y", labelsize=FS_TICK)
        ax.set_xlabel("Epoch", fontsize=FS_AXLAB)
        if SIDE_TITLE[side]:
            ax.set_title(SIDE_TITLE[side], fontsize=FS_PANEL)
        ax.set_ylim(ymin, ymax)
        ax.spines[["top", "right"]].set_visible(False)
    title, ylab = LABELS.get(endpoint, (endpoint.replace("_", " "), "Δ value"))
    axes[0].set_ylabel(ylab, fontsize=FS_AXLAB)
    fig.suptitle(title, fontsize=FS_TITLE, fontweight="bold", y=0.995)
    fig.text(0.5, 0.935, SUB1, ha="center", fontsize=FS_SUB, style="italic")
    fig.text(0.5, 0.900, SUB2, ha="center", fontsize=FS_SUB, style="italic")
    handles = [plt.Line2D([], [], color=COLORS[p], marker=MARKERS[p], ms=7, lw=2,
                          label=f"{p} (n={N_ANIMALS[p]})") for p in PHENOS]
    fig.legend(handles=handles, title="phenotype", fontsize=FS_LEG, title_fontsize=FS_LEG,
               loc="center left", bbox_to_anchor=(legend_x, 0.407), frameon=True)
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
    ap.add_argument("stats_root", type=Path, help="<outputs>/stats")
    ap.add_argument("stats_sheet", type=Path,
                    help="consolidated pooled_phenotype_stats*.csv (3_tier scope)")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--endpoints", nargs="*", default=None,
                    help="endpoint slugs; default = every slug in LABELS that has input data")
    ap.add_argument("--sig-col", default="headline_and_bootstrap_sig",
                    choices=("headline_and_bootstrap_sig", "wa_sig"))
    ap.add_argument("--filter-variant", default="auto",
                    choices=("auto", "no_filter"),
                    help="auto = stats-build precedence (filtered_v1 then no_filter); "
                         "no_filter reproduces the June-30 panels")
    a = ap.parse_args(argv)
    sig = pd.read_csv(a.stats_sheet)
    sig = sig[sig.family == "scalar"] if "family" in sig.columns else sig
    eps = a.endpoints or sorted(LABELS)
    missing = [e for e in eps if e not in LABELS]
    if missing:
        raise SystemExit(f"no title/label mapping for: {missing} (add to LABELS)")
    for ep in eps:
        inp = a.stats_root / "inputs"
        if not (inp / "filtered_v1" / ep).is_dir() and not (inp / "no_filter" / ep).is_dir():
            print("skip (no input data):", ep)
            continue
        d = load_per_session(a.stats_root, ep, a.filter_variant)
        render(d, sig, endpoint=ep, out_stem=a.out_dir / f"meanSEM_{ep}",
               sig_col=a.sig_col)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
