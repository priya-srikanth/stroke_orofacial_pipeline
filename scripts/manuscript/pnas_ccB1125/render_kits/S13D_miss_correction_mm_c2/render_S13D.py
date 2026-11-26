"""S13D (six-position correction after a miss, millimeter version, v3), render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what widefield_pipeline scripts/caption_review_1123/s12d_mm_render.py (branch ccb/s12d-mm-1123) drew for
S12D_miss_correction_mm_v3_ccB1123 (236.16 x 93.6 pt). The live main.tex file S12D_miss_correction_mm_v3_ccB1123_E is
CC-A's copy of that PDF with the letter E overlaid on the right panel (pypdf); this kit makes the panel itself.
Plot only: session values and the family statistics are read from the two tables next to this script.
Imports only numpy, pandas, matplotlib and vls_style.py. Refuses to overwrite.

  left   gain_miss_lat (filled) and gain_hit_lat (open), both in the epoch color: fraction of lick k's lateral error
         (mm) corrected by lick k+1, session change from the animal's own pre-stroke session mean; marker and bar =
         nested bootstrap estimate and 95 % CI (4,000 draws, seed 0).
  right  binned_lat: lateral correction after a miss, error-matched (0.25-mm |error| bins x spout side) vs the
         animal's own pre-stroke misses; change from own pre.
Star rule: '**' = session Mann-Whitney U q < 0.05 in the six-position family (162 + S12 recovery cells, BH once) AND
the bootstrap CI excludes 0 (`star` column of s12d_mm_family_stats.csv).

Usage: render_S13D.py <kit_dir> <out_stem> [--set NAME=VALUE ...]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as VS                      # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
RC = {"font.size": 6.8, "axes.labelsize": 6.8, "axes.titlesize": 6.8, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
      "legend.fontsize": 6.0, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
      "xtick.major.size": 2, "ytick.major.size": 2}
EPS = ["pre", "acute", "subacute", "chronic"]   # x order
XL = ["pre", "ac", "sub", "chr"]                 # x tick labels
XLIM = (-0.55, 3.55)
LEG = "0.2"              # legend marker color (neutral dark)
DX = 0.19                # miss / hit half-offset within an epoch (x units)
H_IN, LEFT_IN, GAP_IN, RIGHT_IN = 1.3, 0.5, 0.62, 0.06   # canvas height, margins and gap (in)
W0_IN, W1_IN = 1.30, 0.80                                # left / right panel widths (in)
BOTTOM, TOP = 0.2, 0.86                                  # axes bottom / top (figure fraction)
YPAD_LO, YPAD_HI = 0.06, 0.30                            # y range padding below / above the data (fraction of range; top = star band)
MARK = "**"; STAR_FS = {2: 7, 1: 8}
YLAB0 = "Δ correction gain\n(fraction of lateral error)"
YLAB1 = "Δ correction after a miss,\nerror-matched (mm)"
LEGEND = dict(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, frameon=False, borderaxespad=0.1, handlelength=1.0,
              handletextpad=0.3, columnspacing=1.2)
LEG_LABELS = ["after a miss", "after a hit"]
JITTER_SEED = 3
# -------------------------------------------------------------------------------------------------------------------


def apply_overrides(argv):
    """--set NAME=VALUE (repeatable): override any setting of the block above; values are Python literals."""
    import ast
    out, i = [], 0
    while i < len(argv):
        if argv[i] == '--set':
            k, v = argv[i + 1].split('=', 1)
            if k not in globals(): sys.exit(f'unknown setting {k}')
            try: v = ast.literal_eval(v)
            except (ValueError, SyntaxError): pass
            globals()[k] = v; i += 2
        else:
            out.append(argv[i]); i += 1
    return out


def main(kit, stem):
    for x in ("pdf", "svg", "png"):
        if os.path.exists(f"{stem}.{x}"): sys.exit(f"refusing to overwrite {stem}.{x}")
    S = pd.read_csv(os.path.join(kit, "s12d_alt_sessions.csv"))
    ST = pd.read_csv(os.path.join(kit, "s12d_mm_family_stats.csv")).rename(columns={"boot_change": "est", "boot_lo": "lo", "boot_hi": "hi"})
    ST["star"] = ST["star"].astype(int).eq(1)
    VS.apply()
    plt.rcParams.update(RC)
    C = VS.EP
    rng = np.random.RandomState(JITTER_SEED)

    def chg(m):
        d = S[np.isfinite(S[m])].copy()
        d["chg"] = d[m] - d.animal.map(d[d.epoch == "pre"].groupby("animal")[m].mean())
        return d

    def draw(ax, m, dx, hollow, stars):
        d = chg(m)
        for j, ep in enumerate(EPS):
            x = j + dx
            v = d[d.epoch == ep].chg.to_numpy()
            col = C[ep]
            pt = dict(mfc="none", mec=col, mew=0.45) if hollow else dict(mfc=col, mec="none")
            mk = dict(mfc="white", mec=col, mew=0.9) if hollow else dict(mfc=col, mec="k", mew=0.4)
            ax.plot(x + (rng.rand(len(v)) - .5) * 0.13, v, "o", ms=1.8 if hollow else 1.6, alpha=0.4, zorder=1, **pt)
            if ep == "pre":
                ax.plot([x], [0], "o", ms=3.6, zorder=3, **mk)
                continue
            r = ST[(ST.metric == m) & (ST.epoch == ep)].iloc[0]
            ax.errorbar([x], [r.est], yerr=[[r.est - r.lo], [r.hi - r.est]], fmt="o", ms=3.6, color=col,
                        elinewidth=0.9, capsize=0, zorder=3, **mk)
            if r.star:
                stars.append((x, col))
        return d

    def finish(ax, vals, stars, ylab):
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        rg = hi - lo
        ax.set_ylim(lo - YPAD_LO * rg, hi + YPAD_HI * rg)
        for x, col in stars:
            ax.text(x, 0.99, MARK, transform=ax.get_xaxis_transform(), ha="center", va="top", color=col,
                    fontsize=STAR_FS[2] if len(MARK) > 1 else STAR_FS[1], fontweight="bold")
        VS.zero_line(ax)
        ax.set_xticks(range(4))
        ax.set_xticklabels(XL)
        ax.set_xlim(*XLIM)
        ax.set_ylabel(ylab)
        ax.spines[["top", "right"]].set_visible(False)

    w_in = LEFT_IN + W0_IN + GAP_IN + W1_IN + RIGHT_IN
    fig = plt.figure(figsize=(w_in, H_IN))
    b, t = BOTTOM, TOP
    a0 = fig.add_axes([LEFT_IN / w_in, b, W0_IN / w_in, t - b])
    a1 = fig.add_axes([(LEFT_IN + W0_IN + GAP_IN) / w_in, b, W1_IN / w_in, t - b])
    st0, st1 = [], []
    d1 = draw(a0, "gain_miss_lat", -DX / 1.0 * 0.95, False, st0)
    d2 = draw(a0, "gain_hit_lat", DX * 0.95, True, st0)
    finish(a0, np.r_[d1.chg, d2.chg], st0, YLAB0)
    hm = plt.Line2D([], [], marker="o", ls="none", ms=3.6, mfc=LEG, mec=LEG, mew=0.4)
    hh = plt.Line2D([], [], marker="o", ls="none", ms=3.6, mfc="white", mec=LEG, mew=0.9)
    a0.legend([hm, hh], LEG_LABELS, **LEGEND)
    d3 = draw(a1, "binned_lat", 0.0, False, st1)
    finish(a1, d3.chg.to_numpy(), st1, YLAB1)
    for x in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{x}", dpi=300 if x == "png" else None)
    print(f"canvas {w_in * 72:.2f} x {H_IN * 72:.2f} pt -> {stem}")


if __name__ == "__main__":
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
