"""Manuscript-style mean +/- SEM endpoint panels (with ** significance).

Regenerates the `meanSEM_sig_panels` and `angle_panels` figures whose original
scripts were never saved (the June-30 renders). Three endpoint families:

* ``scalar`` (default) -- the `meanSEM_sig_panels` set, 30 endpoints
* ``phase_aligned_endpoints`` -- first-lick family; ``peak_angle_deg`` is the
  published `angle_panels/angle_firstlick_peak`
* ``phase_aligned_endpoints_all_licks`` -- all-lick family; ``peak_angle_deg``
  is `angle_panels/angle_alllick_peak` (Figure 3 P/Q)

For the scalar family the recipe matches the published panels:

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

The phase-aligned families read the per-session substrate the stats build wrote,
``stats/results/phenotype_pooled/<family>/<scope>/<version>/per_session_means.csv``
(column ``mean``), and are baseline-corrected the same way. Gaps left by an epoch
with no qualifying sessions (severe / acute) are bridged with a dashed segment,
the convention of the published angle panels; this now applies to every family,
including the scalar panels (``--solid-gaps`` restores the old solid bridge).

Usage::

    # meanSEM_sig_panels
    python scripts/manuscript/plot_scalar_meansem_panels.py \
        <outputs>/stats <outputs>/stats/results/phenotype_pooled/3_tier/pooled_phenotype_stats.csv \
        <out_dir> [--endpoints tongue_mean_within_bout_ili_ms] [--sig-col ...]

    # angle_panels (Figure 3 N-Q)
    python scripts/manuscript/plot_scalar_meansem_panels.py \
        <outputs>/stats <outputs>/.../pooled_phenotype_stats.csv <out_dir> \
        --family phase_aligned_endpoints_all_licks --endpoints peak_angle_deg
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


# per-family: (results subdir, value column, {endpoint: (title, ylabel)}, subtitle,
#              dashed bridge over missing epochs, output stem template)
PHASE_LABELS = {
    "peak_angle_deg": ("{lickset} peak tongue angle (Δ from pre-stroke)",
                       "Δ peak angle (deg)"),
    "signed_angle_at_max_abs_phase_0_075_deg":
        ("{lickset} signed tongue angle at max |phase 0-0.075|", "Δ angle (deg)"),
    "signed_x_at_max_abs_phase_0_075_px":
        ("{lickset} signed tongue x at max |phase 0-0.075|", "Δ x (px)"),
}
PHASE_FAMILY = {
    "phase_aligned_endpoints": ("First-lick", "angle_firstlick"),
    "phase_aligned_endpoints_all_licks": ("All-lick", "angle_alllick"),
}
PHASE_SUB = ("mean ± SEM (baseline-subtracted); filtered_v1 sessions; ** = q<0.05 "
             "(session MWU+BH-FDR) & session-bootstrap CI of the post−pre "
             "difference in means excludes 0")


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


def load_phase_per_session(results_root: Path, family: str, scope: str,
                           version: str) -> pd.DataFrame:
    """Per-session, baseline-corrected values for a phase-aligned family.

    Source is the substrate the stats build wrote, so panel and sheet agree.
    ``side`` is ipsi/contra here and L/R in the sheet; all animals are
    left-lesioned, so ipsi -> L and contra -> R.
    """
    p = results_root / family / scope / version / "per_session_means.csv"
    if not p.is_file():
        raise SystemExit(f"no per-session means at {p}")
    d = pd.read_csv(p)
    d = d.rename(columns={"mean": "value"})
    d["side"] = d.side.map({"ipsi": "L", "contra": "R"}).fillna(d.side)
    base = (d[d.epoch_label == "pre"]
            .groupby(["animal", "side", "endpoint"]).value.mean().rename("baseline"))
    d = d.merge(base, on=["animal", "side", "endpoint"], how="left")
    d["delta"] = d.value - d.baseline
    d["recovery_phenotype"] = d.recovery_phenotype.replace(
        {"moderate-severe": "moderate"})          # 3-tier
    return d.dropna(subset=["delta", "recovery_phenotype"])


def render(d: pd.DataFrame, sig: pd.DataFrame, *, endpoint: str,
           out_stem: Path, sig_col: str, labels: tuple[str, str] | None = None,
           subtitles: tuple[str, ...] = (SUB1, SUB2),
           dashed_gaps: bool = True, value_col: str = "delta") -> None:
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
    d = d.rename(columns={value_col: "_v"}) if value_col != "_v" else d
    lo = d._v.min(); hi = d._v.max(); span = max(hi - lo, 1e-9)
    ymin, ymax = lo - 0.05 * span, hi + 0.30 * span      # headroom for the ** band
    for ax, side in zip(axes, sides):
        ds = d[d.side == side]
        for ph in PHENOS:
            dp = ds[ds.recovery_phenotype == ph]
            if dp.empty:
                continue
            xs, ms, es = [], [], []
            for i, (ep, _) in enumerate(EPOCHS):
                v = dp[dp.epoch_label == ep]._v
                if v.empty:
                    continue
                ax.scatter([i + 0.02 * (PHENOS.index(ph) - 1)] * len(v), v, s=14,
                           color=COLORS[ph], alpha=0.16, marker=MARKERS[ph], linewidths=0)
                xs.append(i); ms.append(v.mean())
                es.append(v.std(ddof=1) / max(len(v) ** 0.5, 1) if len(v) > 1 else 0.0)
            if dashed_gaps:
                # solid between adjacent epochs, dashed across an epoch with no
                # qualifying sessions (e.g. severe / acute)
                ax.errorbar(xs, ms, yerr=es, color=COLORS[ph], marker=MARKERS[ph],
                            ms=7, lw=0, capsize=3, zorder=3)
                for k in range(len(xs) - 1):
                    style = "-" if xs[k + 1] - xs[k] == 1 else "--"
                    ax.plot(xs[k:k + 2], ms[k:k + 2], style, color=COLORS[ph],
                            lw=2, zorder=3)
            else:
                ax.errorbar(xs, ms, yerr=es, color=COLORS[ph], marker=MARKERS[ph],
                            ms=7, lw=2, capsize=3, zorder=3)
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
    title, ylab = labels or LABELS.get(endpoint,
                                       (endpoint.replace("_", " "), "Δ value"))
    if value_col == "value":
        ylab = ylab.replace("Δ ", "").replace("Δ", "").strip() or "value"
    axes[0].set_ylabel(ylab, fontsize=FS_AXLAB)
    fig.suptitle(title, fontsize=FS_TITLE, fontweight="bold", y=0.995)
    for k, sub in enumerate(subtitles):
        fig.text(0.5, 0.935 - 0.035 * k, sub, ha="center", fontsize=FS_SUB,
                 style="italic")
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
    ap.add_argument("--absolute", action="store_true",
                    help="plot the raw per-session values instead of the change from "
                         "each animal's pre-stroke mean (the meanSEM_abs_panels set)")
    ap.add_argument("--solid-gaps", action="store_true",
                    help="draw a solid segment across an epoch with no qualifying "
                         "sessions; default is the dashed-bridge convention of the "
                         "published angle panels")
    ap.add_argument("--family", default="scalar",
                    choices=("scalar", "phase_aligned_endpoints",
                             "phase_aligned_endpoints_all_licks"))
    ap.add_argument("--results-root", type=Path, default=None,
                    help="stats/results/phenotype_pooled (phase-aligned families; "
                         "default <stats_root>/results/phenotype_pooled)")
    ap.add_argument("--scope", default="3_tier")
    ap.add_argument("--version", default="v3")
    ap.add_argument("--filter-variant", default="auto",
                    choices=("auto", "no_filter"),
                    help="auto = stats-build precedence (filtered_v1 then no_filter); "
                         "no_filter reproduces the June-30 panels")
    a = ap.parse_args(argv)
    sig = pd.read_csv(a.stats_sheet)
    if "family" in sig.columns:
        sig = sig[sig.family == a.family]

    if a.family != "scalar":
        lickset, stem_prefix = PHASE_FAMILY[a.family]
        root = a.results_root or (a.stats_root / "results" / "phenotype_pooled")
        d_all = load_phase_per_session(root, a.family, a.scope, a.version)
        eps = a.endpoints or sorted(d_all.endpoint.unique())
        for ep in eps:
            d = d_all[d_all.endpoint == ep]
            if d.empty:
                print("skip (no data):", ep)
                continue
            t, ylab = PHASE_LABELS.get(ep, (ep.replace("_", " "), "Δ value"))
            stem = (f"{stem_prefix}_peak" if ep == "peak_angle_deg"
                    else f"{stem_prefix}_{ep}")
            render(d, sig, endpoint=ep, out_stem=a.out_dir / stem,
                   sig_col=a.sig_col, labels=(t.format(lickset=lickset), ylab),
                   subtitles=(PHASE_SUB,), dashed_gaps=not a.solid_gaps,
                   value_col="value" if a.absolute else "delta")
        return 0

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
        vcol = "value" if a.absolute else "delta"
        sub = ((("mean ± SEM (absolute, not baseline-subtracted); faded=sessions"),
                SUB2) if a.absolute else (SUB1, SUB2))
        stem = f"meanSEM_{ep}_abs" if a.absolute else f"meanSEM_{ep}"
        render(d, sig, endpoint=ep, out_stem=a.out_dir / stem,
               sig_col=a.sig_col, dashed_gaps=not a.solid_gaps,
               value_col=vcol, subtitles=sub)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
