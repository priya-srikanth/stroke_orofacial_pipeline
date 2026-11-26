"""SI panel for the lick-order supplementary figure family: six-position within-trial aim correction (render kit; CC-B,
2026-11-25; PROMPT_CC_B_withintrial_aim item 4). Live file FigS_kinematics_bylicknum_withintrial_aim_ccB1125.

Content: change in 3-D tongue angle (deg, + = contralesional) from each animal's own pre-stroke value at the same lick
number, lick numbers 1-10, trials with >= 10 post-cue licks only (the same trials supply every lick number). Left:
all positions (per session the mean over positions); right: far contralesional spout. Epochs as lines (Tol colors),
line = paired animal-weighted nested bootstrap estimate, band = 95 % interval (4,000 draws). Marks = contrast (a),
licks 2-5 minus lick 1, vs pre: '*' = session MWU q < 0.05 (BH within the 42-cell within-trial family) AND the
bootstrap CI excludes 0 (all six are positive = toward contralesional; an arrow after the star is available with
--set SHOW_ARROW=True). One band row per epoch (acute, subacute, chronic). Thin gray lines bound licks 2-5.

Style: Fig 3B fonts at print size (7.1 pt ticks, 7.6 pt axis labels, 7 pt headers / legend / marks); v30 axis-cover
and star-band rules (band_rule.py of ccB_layout_inputs_2026-11-25/v30_renderers, inlined below unchanged): tick step
from 1/2/2.5/4/5 x 10^k with 4-8 ticks, the data area and the left spine end at the first tick at or above the
highest drawn point (band tops included); band rows 3.0 pt below the band top, 4.0 pt apart, 1.5 pt below the last
row; lower limit 2 % of the range below the lowest drawn point. Shared y across the two panels.

Usage (in the kit folder): python render_withintrial_aim.py . <out_dir> [--stem NAME] [--set NAME=VALUE ...]
Imports only numpy, pandas, matplotlib. Refuses to overwrite.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# ---------------- presentation settings (override with --set NAME=VALUE) ----------------
W_PT, H_PT = 300.0, 128.0              # page (pt) at print size (include at 100 %)
LEFT_PT, AX_W_PT, GAP_PT = 36.0, 92.0, 16.0
BOTTOM_PT, AX_H_PT = 26.0, 84.0
FT_TICK, FT_LAB, FT_HDR, FT_LEG, FT_MARK = 7.1, 7.6, 7.0, 7.0, 7.0
LW_AX, LW_LINE, BAND_ALPHA = 0.7, 0.9, 0.28
EP = {"acute": "#AA3377", "subacute": "#4477AA", "chronic": "#228833"}
EPOCH_ROWS = ["acute", "subacute", "chronic"]     # band row order
PANELS = [("pooled", "all positions"), ("far_contra", "far contra spout")]
YLABEL = "Δ 3D angle (deg)"
XLABEL = "Lick number in trial"
XTICKS = [1, 2, 5, 10]
MARK_X = 3.5                       # marks centered over licks 2-5
VLINES = (1.5, 5.5)                # thin gray lines bounding licks 2-5 (contrast window vs lick 1), data area only
VLINE_COLOR, VLINE_LW = "0.8", 0.6
#: arrows after the star are OFF by default: every glyph tried (Arial fallback, mathtext) is taller than the 4 pt
#: band-row step and runs into the next row; all six marked contrasts are positive (caption says so)
SHOW_ARROW = False
ARROW_UP, ARROW_DOWN = r"$\uparrow$", r"$\downarrow$"
LEG_X_PT, LEG_Y_PT = 4.0, 0.0      # legend offset from the right panel's right edge / top of data area
LOWER_PAD = 0.02
LINES = "lines_withintrial_aim_c2_bout10_ccB1125.csv"
MARKS = "marks_withintrial_aim_c2_bout10_ccB1125.csv"
STEM = "FigS_kinematics_bylicknum_withintrial_aim_ccB1125"

# ---------------- band_rule.py (v30), inlined ----------------
ROW_TOP_PT_V30, ROW_STEP_PT_V30, BELOW_PT_V30 = 3.0, 4.0, 1.5


def tick_step_v30(top, y0):
    rng = top - y0
    best = None
    for k in range(-4, 6):
        for m in (1, 2, 2.5, 4, 5):
            st = m * 10.0 ** k
            lo_t = np.floor(y0 / st + 1e-9) * st
            if lo_t < y0 - 1e-9: lo_t += st
            tp = st * np.ceil(top / st - 1e-9)
            n = int(round((tp - lo_t) / st)) + 1
            if 4 <= n <= 8:
                gap = (tp - top) / rng
                if best is None or gap < best[0] - 1e-9: best = (gap, st, lo_t, tp)
    return None if best is None else best[1:]


def data_top_v30(top, y0):
    step, lo_t, tick = tick_step_v30(top, y0)
    tick = round(float(tick), 10)
    yd1 = max(tick, top + 0.01 * (top - y0))
    if y0 < 0:
        yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
    grid = [round(float(v), 10) for v in np.arange(lo_t, tick + step / 2, step)]
    return yd1, [t for t in grid if y0 - 1e-9 <= t <= tick + 1e-9], tick


def band_pt(used_rows, extra_pt=0.0):
    if not used_rows: return extra_pt
    return extra_pt + ROW_TOP_PT_V30 + max(used_rows) * ROW_STEP_PT_V30 + BELOW_PT_V30


def row_y(row, ah_pt, extra_pt=0.0):
    return 1.0 - (extra_pt + ROW_TOP_PT_V30 + row * ROW_STEP_PT_V30) / ah_pt


def apply_overrides(argv):
    import ast
    out, i = [], 0
    while i < len(argv):
        if argv[i] == "--set":
            k, v = argv[i + 1].split("=", 1)
            try: v = ast.literal_eval(v)
            except (ValueError, SyntaxError): pass
            globals()[k] = v; i += 2
        else:
            out.append(argv[i]); i += 1
    return out


def main():
    global STEM
    args = apply_overrides(sys.argv[1:])
    if "--stem" in args:
        STEM = args[args.index("--stem") + 1]
    kit, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / f"{STEM}.{e}" for e in ("pdf", "svg", "png")]
    for t in targets:
        if t.exists():
            sys.exit(f"refusing to overwrite {t}")
    plt.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"], "font.size": FT_LAB,
                         "axes.labelsize": FT_LAB, "xtick.labelsize": FT_TICK, "ytick.labelsize": FT_TICK,
                         "legend.fontsize": FT_LEG, "legend.frameon": False, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.linewidth": LW_AX, "xtick.major.width": LW_AX,
                         "ytick.major.width": LW_AX, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
                         "xtick.major.pad": 1.5, "ytick.major.pad": 1.5, "axes.labelpad": 2.0})
    L = pd.read_csv(kit / LINES)
    M = pd.read_csv(kit / MARKS)
    fig = plt.figure(figsize=(W_PT / 72, H_PT / 72))
    axes = []
    for i, (pos, hdr) in enumerate(PANELS):
        x0 = LEFT_PT + i * (AX_W_PT + GAP_PT)
        ax = fig.add_axes([x0 / W_PT, BOTTOM_PT / H_PT, AX_W_PT / W_PT, AX_H_PT / H_PT])
        ax.axhline(0, color="0.6", lw=0.6, ls="--", zorder=0.5)
        for ep, col in EP.items():
            d = L[(L.pos == pos) & (L.epoch == ep)].sort_values("lick")
            ax.fill_between(d.lick, d.lo, d.hi, color=col, alpha=BAND_ALPHA, lw=0, zorder=1)
            ax.plot(d.lick, d.est, color=col, lw=LW_LINE, zorder=3)
        ax.set_xlim(0.5, 10.5)
        ax.set_xticks(XTICKS)
        ax.set_xlabel(XLABEL)
        if i == 0:
            ax.set_ylabel(YLABEL)
        ax.set_title(hdr, fontsize=FT_HDR, pad=1.5)
        axes.append(ax)
    # shared y, v30 rule over everything drawn (bands included)
    top, low = float(L.hi.max()), float(L.lo.min())
    y0 = low - LOWER_PAD * (top - low)
    yd1, ticks, spine_tick = data_top_v30(top, y0)
    used = sorted({EPOCH_ROWS.index(r.epoch) for r in M.itertuples() if bool(r.star)})
    bpt = band_pt(used)
    y1n = y0 + (yd1 - y0) / (1.0 - bpt / AX_H_PT)
    for i, (pos, _) in enumerate(PANELS):
        ax = axes[i]
        ax.set_ylim(y0, y1n)
        ax.set_yticks(ticks)
        if i > 0:
            ax.set_yticklabels([])
        ax.spines["left"].set_bounds(y0, spine_tick)
        for xv in VLINES:
            ax.plot([xv, xv], [y0, yd1], color=VLINE_COLOR, lw=VLINE_LW, zorder=0.4)
        for r in M[M.pos == pos].itertuples():
            if bool(r.star):
                ax.text(MARK_X, row_y(EPOCH_ROWS.index(r.epoch), AX_H_PT), "*" + ((ARROW_UP if r.est > 0 else ARROW_DOWN) if SHOW_ARROW else ""),
                        transform=ax.get_xaxis_transform(), color=EP[r.epoch], ha="center", va="center",
                        fontsize=FT_MARK, fontweight="bold", clip_on=False)
    # legend right of the far-contra panel, top aligned with the data area
    p = axes[-1].get_position()
    data_top_fig = p.y0 + p.height * (1.0 - bpt / AX_H_PT)
    h = [plt.Line2D([], [], color=c, lw=1.2, label=e) for e, c in EP.items()]
    fig.legend(handles=h, loc="upper left", bbox_to_anchor=(p.x1 + LEG_X_PT / W_PT, data_top_fig + LEG_Y_PT / H_PT),
               handlelength=1.6, borderaxespad=0, labelspacing=0.3)
    for t in targets:
        fig.savefig(t, dpi=600 if t.suffix == ".png" else 300)
        print("wrote", t)
    print(f"LOG y0={y0:.4g} data_top={top:.4g} spine_tick={spine_tick} ticks={ticks} band_pt={bpt} rows={used} "
          f"ylim_top={y1n:.4g}")


if __name__ == "__main__":
    main()
