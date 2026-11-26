"""S13F (six-position far-contralesional first-lick angle on session thirds, working period), render kit for CC-A
(CC-B, 2026-11-25).

Draws exactly what widefield_pipeline scripts/caption_review_1123/s12f_thirds_boot.py render() (with
thirds_recovery_core.draw_animal, inlined here unchanged) drew for the live
S12F_daycourse_firstangle_thirdsboot_v2_wp_ccB1123 (403.2 x 97.2 pt). Plot only, from thirds_sessions_sixpos_wp_ccB1123.csv:
one row per session with the first-lick 3-D angle of its early / mid / late third of trials (early, mid, late) and the
session mean (M); pre = August pre-stroke sessions (post = 0), post = post-stroke days 1-14 (post = 1). Each animal:
its last three pre sessions (gray) then the post window; y = change from the animal's mean over its pre sessions.
No marks in this panel (the statistics are in thirds_boot_lmm_sixpos_wp_ccB1123.csv, caption only).
Imports only numpy, pandas, matplotlib and vls_style.py. Refuses to overwrite.

Usage: render_S13F.py <thirds_sessions.csv> <out_stem> [--set NAME=VALUE ...]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as St                      # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
RC = {'font.size': 6.8, 'axes.labelsize': 6.8, 'axes.titlesize': 6.8, 'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
      'legend.fontsize': 6.3, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
      'xtick.major.size': 2, 'ytick.major.size': 2}
FIG_W_IN, FIG_H_IN = 5.6, 1.35
MARGINS = dict(left=0.1, right=0.995, bottom=0.24, top=0.86, wspace=0.32)
AN = ["PS92", "PS93", "PS94", "PS95"]                      # panel order
TITLE = dict(zip(AN, ["#9", "#10", "#11", "#12"]))          # panel titles (manuscript ids)
TITLE_PAD = 2
XLABEL, XLABEL_PAD = "sessions (thirds)", 8
YLABEL = "Δ first-lick\nangle (deg)"
N_PRE = 3                  # pre-stroke sessions drawn before the post window
PRE_LABEL_FS = 6.3
MARKER = "o"
STYLE = {"ms": 1.8, "lw": 0.9, "lw_conn": 0.7, "conn_color": "0.55", "dash_next": (0, (2.59, 1.12)),
         "dash_gap": (0, (0.7, 1.155)), "lw_zero": 0.6, "zero_color": "0.6", "dash_zero": (0, (2.22, 0.96))}
PRE_COLOR = "0.3"
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


def draw_animal(ax, d, color_of, marker, n_pre=3, pre_label_fs=6.5):
    """= thirds_recovery_core.draw_animal: last n_pre pre sessions (gray) then the post window, each session its early /
    mid / late thirds joined by a solid line; dashed = next calendar day, dotted = longer gap; y = change from the
    animal's pre-stroke value (mean of its pre-stroke session means). No day axis."""
    d = d.sort_values("day")
    b0 = d[d.post == 0].M.mean()
    seq = pd.concat([d[d.post == 0].tail(n_pre), d[d.post == 1]])
    x, prev = 0.0, None
    for _, r in seq.iterrows():
        xs = [x, x + 0.5, x + 1.0]
        ys = [r.early - b0, r.mid - b0, r.late - b0]
        col = PRE_COLOR if r.post == 0 else color_of(r)
        ax.plot(xs, ys, "-", color=col, lw=STYLE["lw"], zorder=2)
        ax.plot(xs, ys, marker, color=col, ms=STYLE["ms"], mec="none", zorder=3)
        if prev is not None:
            ax.plot([prev[0], xs[0]], [prev[1], ys[0]], ls=STYLE["dash_next"] if r.day - prev[2] == 1 else
                    STYLE["dash_gap"], color=STYLE["conn_color"], lw=STYLE["lw_conn"], zorder=1)
        prev = (xs[-1], ys[-1], r.day)
        x += 1.6
    npre = min(n_pre, int((d.post == 0).sum()))
    ax.axhline(0, color=STYLE["zero_color"], lw=STYLE["lw_zero"], ls=STYLE["dash_zero"], zorder=0)
    ax.set_xticks([])
    ax.set_xlim(-0.5, x - 0.1)
    ax.text((npre - 1) * 1.6 / 2 + 0.5, -0.03, "pre", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=pre_label_fs, color=PRE_COLOR)
    return b0


def main(path, stem):
    for x in ("pdf", "svg", "png"):
        if os.path.exists(f"{stem}.{x}"): sys.exit(f"refusing to overwrite {stem}.{x}")
    S = pd.read_csv(path)
    St.apply()
    plt.rcParams.update(RC)
    fig, axs = plt.subplots(1, len(AN), figsize=(FIG_W_IN, FIG_H_IN))
    for ax, a in zip(axs, AN):
        draw_animal(ax, S[S.animal == a], lambda r: St.EP[r.epoch], MARKER, n_pre=N_PRE, pre_label_fs=PRE_LABEL_FS)
        ax.set_title(TITLE[a], pad=TITLE_PAD)
        ax.set_xlabel(XLABEL, labelpad=XLABEL_PAD)
    axs[0].set_ylabel(YLABEL)
    fig.subplots_adjust(**MARGINS)
    for x in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{x}", dpi=300 if x == "png" else None)
    plt.close(fig)
    print('wrote', stem)


if __name__ == "__main__":
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
