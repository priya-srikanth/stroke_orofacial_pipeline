"""S10A cell (six-position first-lick latency decomposition: cue -> first movement, first movement -> first lick),
render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what manuscript_code/figures/s10_lick_timing_v28.py panel_a drew with S10A_CONTRAST=1 (v28b style:
contrast colors, thin whiskers, position labels under the axis) for the cell
ccB_caption_review_2026-11-23/overnight/S10_lick_timing_v28c_jaw3dmouth_wp_ccB1123_A (234 x 132 pt), which CC-A
composed into the live S10_lick_timing_v29_jaw3dmouth_wp. Input: s10a_cells_jaw3dmouth_wp_ccB1123.csv (one row per
animal x spout x epoch: wait_med_ms = cue to first movement, revup_med_ms = first movement to first lick, medians over
working-period licked trials). Bars = mean over animals; whiskers = SEM across animals; dots = animals (epoch color).
No stars in this panel. Imports only numpy, pandas, matplotlib and vls_style.py. Refuses to overwrite.

Usage: render_S10A.py <s10a_cells.csv> <out_stem> [--set NAME=VALUE ...]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                              # noqa: E402
import matplotlib                                  # noqa: E402
import matplotlib.pyplot as plt                    # noqa: E402
import matplotlib.transforms as mt                 # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
FS, FS_T = 6.5, 7.0
CELL_W = 234.0                                   # cell width (pt) = half of the 468 pt page
R1 = dict(h=132.0, bottom=38.0, axh=72.0)        # cell height, axes bottom, axes height (pt)
AX_L, AX_W = 40.0, 188.0                         # axes left and width (pt)
POS_A = [('close_ipsi', 'near\nipsi'), ('close_mid', 'near\nmid'), ('close_contra', 'near\ncontra'),
         ('far_ipsi', 'far\nipsi'), ('far_mid', 'far\nmid'), ('far_contra', 'far\ncontra')]   # group order / labels
EPS = ['pre', 'acute', 'subacute', 'chronic']; EPL = {'pre': 'pre', 'acute': 'ac', 'subacute': 'sub', 'chronic': 'chr'}
TICK_ROT = 90
CW, CR, HATCH_R = '#8C8C8C', '#F5C27A', None     # wait color (cue -> first movement), rev-up color, hatch
EB = dict(elinewidth=0.45, capsize=0.8, capthick=0.45)   # whiskers
DOT_S = 5
POS_LABEL_DY_PT = 21                             # position labels this far below the axis (pt)
YLAB = 'median latency (ms)'
LEG_LABELS = ['cue → first movement', 'first movement → first lick']
LEGEND = dict(loc='upper left', frameon=False, handlelength=1.4, handleheight=0.8, labelspacing=0.3, borderaxespad=0.2,
              bbox_to_anchor=(0.0, 1.02))
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


def rc():
    S.apply()
    plt.rcParams.update({'font.size': FS, 'axes.labelsize': FS, 'axes.titlesize': FS_T, 'xtick.labelsize': FS,
                         'ytick.labelsize': FS, 'legend.fontsize': FS, 'axes.labelpad': 1.5,
                         'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
                         'xtick.major.size': 2.0, 'ytick.major.size': 2.0, 'xtick.major.pad': 1.5,
                         'ytick.major.pad': 1.5})


def restyle(fig):
    for ax in fig.axes:
        for t in ax.get_xticklabels() + ax.get_yticklabels(): t.set_fontsize(FS)
        ax.xaxis.label.set_fontsize(FS); ax.yaxis.label.set_fontsize(FS)
        ax.title.set_fontsize(FS_T)
        for t in ax.texts:
            t.set_fontsize(FS_T if set(t.get_text()) == {'*'} else FS)
        lg = ax.get_legend()
        if lg:
            for t in lg.get_texts(): t.set_fontsize(FS)
        ax.tick_params(width=0.6, length=2.0, pad=1.5)
        for s in ax.spines.values(): s.set_linewidth(0.6)


def main(cells, stem):
    clash = [f'{stem}.{x}' for x in ('pdf', 'svg', 'png') if os.path.exists(f'{stem}.{x}')]
    if clash: sys.exit('refusing to overwrite:\n  ' + '\n  '.join(clash))
    rc(); matplotlib.rcParams['hatch.linewidth'] = 0.5; matplotlib.rcParams['hatch.color'] = '0.45'
    d = pd.read_csv(cells)
    fig = plt.figure(figsize=(CELL_W / 72, R1['h'] / 72)); ax = fig.add_axes([0, 0, 1, 1]); x0 = 0; ticks, tl = [], []
    for p, pl in POS_A:
        st = x0
        for e in EPS:
            g = d[(d.pos == p) & (d.epoch == e)]
            if g.empty: x0 += 1; continue
            w, r = g.wait_med_ms.values, g.revup_med_ms.values
            ax.bar(x0, w.mean(), 0.8, color=CW, edgecolor='0.3', lw=0.4); ax.bar(x0, r.mean(), 0.8, bottom=w.mean(), color=CR, edgecolor='0.3', lw=0.4, hatch=HATCH_R)
            if len(g) > 1:
                ax.errorbar(x0 - 0.15, w.mean(), yerr=w.std(ddof=1) / np.sqrt(len(w)), fmt='none', ecolor='0.15', **EB)
                ax.errorbar(x0 + 0.15, w.mean() + r.mean(), yerr=r.std(ddof=1) / np.sqrt(len(r)), fmt='none', ecolor='0.15', **EB)
            ax.scatter(np.full(len(g), x0) + np.linspace(-0.25, 0.25, len(g)), w + r, s=DOT_S, color=S.EP_DARK[e],
                       edgecolor='white', lw=0.3, zorder=4)
            ticks.append(x0); tl.append(EPL[e]); x0 += 1
        ax.text((st + x0 - 1) / 2, 0.0, pl.replace('\n', ' '), ha='center', va='top', fontsize=FS,
                transform=ax.get_xaxis_transform() + mt.ScaledTranslation(0, -POS_LABEL_DY_PT / 72, fig.dpi_scale_trans))
        x0 += 0.6
    ax.set_xticks(ticks); ax.set_xticklabels(tl, fontsize=FS, rotation=TICK_ROT); ax.set_xlim(-0.7, x0 - 0.9)
    ax.set_ylabel(YLAB)
    h = [plt.Rectangle((0, 0), 1, 1, fc=CW, ec='0.3', lw=0.4, label=LEG_LABELS[0]),
         plt.Rectangle((0, 0), 1, 1, fc=CR, ec='0.3', lw=0.4, hatch=HATCH_R, label=LEG_LABELS[1])]
    ax.legend(handles=h, fontsize=FS, **LEGEND)
    W = fig.get_size_inches()[0] * 72
    ax.set_position([AX_L / W, R1['bottom'] / R1['h'], AX_W / W, R1['axh'] / R1['h']])
    restyle(fig)
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{ext}', dpi=600 if ext == 'png' else 300, bbox_inches=None)
    plt.close(fig)
    print('wrote', stem)


if __name__ == '__main__':
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
