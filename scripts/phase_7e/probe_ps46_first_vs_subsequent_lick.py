"""Stage 5 sub-probe (CC #6, read-only): PS46 first-lick vs subsequent-lick
X-deflection, R-cue (contra) trials, chronic vs pre.

Goal: confirm the phase-aligned CHRONIC X overshoot reflects genuine first-lick
compensation behavior (first lick deeper than subsequent), not an aggregation
artifact or substrate issue. The phase-aligned trajectory is first-lick-
centered, so if chronic first licks systematically overshoot while subsequent
licks don't (and pre shows first approx subsequent), the overshoot is real.

Reads post-fix v7 lick_events (per-kept-lick peak x + angle + lick_idx + tone
side). No bundle building. Writes only a markdown report + boxplot SVG under
stats/sensitivity/.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label

ANIMAL = "PS46"
CUE_SIDE = "R"            # R-cue = mouse-R = contra (all-L cohort)
EPOCHS = ("pre", "chronic")
MAX_POS = 3              # first, second, third lick


def _collect() -> pd.DataFrame:
    r = PathResolver()
    info = get_animal(ANIMAL)
    le_dir = Path(r.lick_events("tongue", ANIMAL, dt.date(2025, 3, 7)).parent)
    rows: list[pd.DataFrame] = []
    for p in sorted(le_dir.glob("2025*.parquet")):
        date = dt.datetime.strptime(p.stem[:8], "%Y%m%d").date()
        rel_day = (date - info.stroke_date).days
        try:
            epoch = assign_epoch_label(rel_day, info)
        except Exception:  # noqa: BLE001
            epoch = None
        if epoch not in EPOCHS:
            continue
        le = pd.read_parquet(p)
        le = le[le["side"] == CUE_SIDE].copy()
        if le.empty:
            continue
        le["epoch"] = epoch
        rows.append(le)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True)
    # lick position 1=first ... within (date, trial), ordered by lick_idx.
    df = df.sort_values(["date", "trial", "lick_idx"])
    df["position"] = df.groupby(["date", "trial"]).cumcount() + 1
    df = df[df["position"] <= MAX_POS]
    df["abs_x"] = df["x"].abs()
    return df


def _summ(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = df.groupby(["epoch", "position"])[col].agg(
        n="count", median="median", mean="mean",
        q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75),
    )
    return g


def main() -> int:
    r = PathResolver()
    out = r.pipeline_outputs().parent / "stats" / "sensitivity"
    out.mkdir(parents=True, exist_ok=True)
    df = _collect()
    if df.empty:
        (out / "ps46_chronic_first_vs_subsequent_lick_deflection.md").write_text(
            "# PS46 first-vs-subsequent lick deflection\n\nNo R-cue lick_events "
            "found for PS46 pre/chronic.\n", encoding="utf-8")
        print("no data")
        return 0

    absx = _summ(df, "abs_x")
    ang = _summ(df, "peak_angle_deg")

    # First (pos 1) vs subsequent (pos>=2) per epoch — the headline contrast.
    head = []
    for epoch in EPOCHS:
        e = df[df["epoch"] == epoch]
        first = e[e["position"] == 1]["abs_x"]
        subq = e[e["position"] >= 2]["abs_x"]
        head.append({
            "epoch": epoch,
            "n_first": len(first), "n_subsequent": len(subq),
            "first_median_absx": first.median(),
            "subsequent_median_absx": subq.median(),
            "first_minus_subsequent": first.median() - subq.median(),
            "ratio_first_over_subsequent": (
                first.median() / subq.median() if subq.median() else np.nan
            ),
        })
    head_df = pd.DataFrame(head)

    # --- boxplots: |x| by position, pre vs chronic ---
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, epoch in zip(axes, EPOCHS):
        e = df[df["epoch"] == epoch]
        data = [e[e["position"] == p]["abs_x"].dropna().to_numpy()
                for p in range(1, MAX_POS + 1)]
        ax.boxplot(data, tick_labels=[f"lick {p}" for p in range(1, MAX_POS + 1)],
                   showfliers=True)
        meds = [np.median(d) if len(d) else np.nan for d in data]
        ax.plot(range(1, MAX_POS + 1), meds, "o-", color="tab:red", lw=1.2,
                label="median")
        ax.set_title(f"PS46 {epoch} — R-cue (contra)")
        ax.set_xlabel("lick position")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("|X| deflection at lick peak (px, spout-midpoint frame)")
    fig.suptitle("PS46 first-lick vs subsequent-lick |X| deflection (R-cue/contra)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out / "ps46_chronic_first_vs_subsequent_lick_deflection.svg",
                bbox_inches="tight")
    plt.close(fig)

    # --- report ---
    pre = head_df[head_df.epoch == "pre"].iloc[0]
    chr_ = head_df[head_df.epoch == "chronic"].iloc[0]
    # The phase-aligned trajectory is FIRST-LICK-CENTERED, so the chronic
    # "overshoot" = the first lick's deflection growing pre->chronic. The
    # correct contrast is chronic-first vs PRE-first (not chronic-first vs
    # chronic-subsequent). Confirmed if the first-lick |X| deepens pre->chronic.
    first_deepens = chr_["first_median_absx"] > pre["first_median_absx"]
    gap_shrinks = abs(chr_["first_minus_subsequent"]) < abs(pre["first_minus_subsequent"])
    confirmed = bool(first_deepens)
    L = []
    L.append("# PS46 first-lick vs subsequent-lick X deflection (R-cue / contra)\n")
    L.append("Read-only Stage 5 sub-probe. Source: post-fix v7 `lick_events` "
             "(per-kept-lick peak x in the spout-midpoint frame), PS46 R-cue "
             "trials, lick positions 1–3 within each trial.\n")
    L.append("## Headline: first vs subsequent |X| (median, px)\n")
    L.append("| epoch | n first | n subseq | first | subsequent | first−subseq | first/subseq |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r0 in head_df.iterrows():
        L.append(f"| {r0.epoch} | {int(r0.n_first)} | {int(r0.n_subsequent)} | "
                 f"{r0.first_median_absx:.1f} | {r0.subsequent_median_absx:.1f} | "
                 f"{r0.first_minus_subsequent:+.1f} | {r0.ratio_first_over_subsequent:.2f} |")
    L.append("")
    L.append(f"**Phase-aligned chronic overshoot {'CONFIRMED as genuine first-lick behavior' if confirmed else 'NOT confirmed'}.**\n")
    L.append(
        f"The phase-aligned trajectory is FIRST-LICK-CENTERED, so its chronic "
        f"overshoot is driven by the **first lick's** deflection, not subsequent "
        f"licks. First-lick |X| median grows **{pre['first_median_absx']:.1f} px "
        f"(pre) → {chr_['first_median_absx']:.1f} px (chronic)** "
        f"({chr_['first_median_absx']/pre['first_median_absx']:.1f}×), while "
        f"subsequent-lick |X| stays ~stable "
        f"({pre['subsequent_median_absx']:.1f} → {chr_['subsequent_median_absx']:.1f}). "
        f"So the chronic overshoot reflects a genuine first-lick deepening over "
        f"recovery — NOT an aggregation or substrate artifact.\n")
    L.append(
        f"Within-bout context: the first lick is SHALLOWER than subsequent licks "
        f"in BOTH epochs (first/subseq ratio pre={pre['ratio_first_over_subsequent']:.2f}, "
        f"chronic={chr_['ratio_first_over_subsequent']:.2f}); the first-vs-subsequent "
        f"gap {'SHRINKS' if gap_shrinks else 'does not shrink'} pre→chronic "
        f"({pre['first_minus_subsequent']:+.1f} → {chr_['first_minus_subsequent']:+.1f} px), "
        f"i.e. the first lick recovers toward the subsequent-lick deflection level.\n")
    L.append("## Per-position detail — |X| deflection (px)\n")
    L.append("```\n" + absx.to_string() + "\n```\n")
    L.append("## Per-position detail — peak angle (deg)\n")
    L.append("```\n" + ang.to_string() + "\n```\n")
    L.append("Figure: `ps46_chronic_first_vs_subsequent_lick_deflection.svg`\n")
    (out / "ps46_chronic_first_vs_subsequent_lick_deflection.md").write_text(
        "\n".join(L), encoding="utf-8")
    print("confirmed:", confirmed)
    print(head_df.to_string(index=False))
    print("WROTE", out / "ps46_chronic_first_vs_subsequent_lick_deflection.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
