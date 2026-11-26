"""Fig 3D (six-position trial outcomes by position and epoch), render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what manuscript_code/figures/fig3_def_row_v28.py panel_d drew (--eb-thin) for the live file
FigureS11_trial_classes_c2_4cam_v28b_jaw3dmouth_new_wp_ccB1123 (209 x 128 pt), from the three plot-ready tables that
stage_fig3D_tables.py wrote. Nothing is recomputed: bars are the stored means, whiskers are the SEM across animals of
the cumulative per-animal fractions, markers and stars are read from the tables.

Imports only numpy, pandas, matplotlib and vls_style.py (next to this file). Refuses to overwrite.

Usage: render_fig3D.py <kit_dir> <out_stem> [--set NAME=VALUE ...]
       (kit_dir holds fig3D_bars.csv, fig3D_per_animal_fractions.csv, fig3D_animal_markers.csv)

All presentation settings are in the block below. With the defaults the output is byte-identical to the live PDF.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                       # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402
import matplotlib.patheffects as pe         # noqa: E402
import matplotlib.transforms as mtr         # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
FS, FS_T = 6.5, 7.0            # tick / label / legend font, and title / star font (pt)
W_PT, H_PT = 209.0, 128.0      # figure width and height (pt)   [fig3_def_row_v28 --wd / --h]
BOTTOM_PT, AXH_PT = 21.0, 74.0 # axes bottom and height (pt)    [--bottom / --axh]
LEFT_PT, RIGHT_PT = 30.5, 3.5  # axes left / right margins (pt) [--leftd]
XPAD = 3.5                     # x tick-label offset below the axes (pt)
LEG_NCOL = 4                   # legend columns (Priya 11-25 asked CC-A for a two-column legend: set 2)
LEG_LOC = 'lower center'       # legend anchor corner
LEG_Y_PT = 23.5                # legend bottom above the axes top (pt)   [--legy]
LEG_X_PT = 0.0                 # legend shift left (pt)                  [--legx]
LEG_FS = FS                    # legend font (pt)
LEG_KW = dict(handlelength=0.55, handleheight=0.75, handletextpad=0.2, columnspacing=0.3, borderaxespad=0.0, borderpad=0.0)
EPS = ['pre', 'acute', 'subacute', 'chronic']                       # epoch order within a position
EPL = {'pre': 'pre', 'acute': 'ac', 'subacute': 'sub', 'chronic': 'chr'}   # x tick labels
TICK_ROT = 90                                                       # x tick-label rotation
POS = [('close_L', 'near ipsi'), ('close_center', 'near mid'), ('close_R', 'near contra'),
       ('far_L', 'far ipsi'), ('far_center', 'far mid'), ('far_R', 'far contra')]   # group order and labels
CLS = ['complete', 'incomplete', 'jaw_only', 'no_resp']             # stacking order, bottom to top
LAB = {'complete': 'complete lick', 'incomplete': 'incomplete lick', 'jaw_only': 'jaw movement only', 'no_resp': 'no response'}
COL = {'complete': '#A6A6A6', 'incomplete': '#44AA99', 'jaw_only': '#BBCCEE', 'no_resp': '#FFFFFF'}
YLAB = 'fraction of\nworking-period trials'
YTICKS, YTL = [0, 0.5, 1], ['0', '0.5', '1']
W, GAP, DX, WOFF = 0.72, 0.35, 0.22, 0.19   # bar width, gap between positions, marker x step, whisker x offset
MS, MEW = 2.4, 0.4                          # per-animal marker size / edge width
EB = dict(elinewidth=0.45, capsize=0.8, capthick=0.45, halo=1.1)   # whiskers (--eb-thin); live default
STAR_DY_PT = 0.3                            # star offset above the axes top (pt)
HEAD_DY_PT, DIST_DY_PT, BRACKET_DY_PT = 6.5, 15.0, 14.5   # 'ipsi/mid/contra' row, 'near/far' row and bracket (pt)
# -------------------------------------------------------------------------------------------------------------------


def apply_overrides(argv):
    """--set NAME=VALUE (repeatable): override any setting of the block above from the command line, e.g.
    --set LEG_NCOL=2 --set C_ROW_ROT=90 --set "EPL={'pre':'pre','acute':'acute','subacute':'subacute','chronic':'chronic'}".
    Values are Python literals; strings may be given bare. Returns argv without the --set pairs."""
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


def save(fig, stem):
    clash = [f'{stem}.{x}' for x in ('pdf', 'svg', 'png') if os.path.exists(f'{stem}.{x}')]
    if clash: sys.exit('refusing to overwrite:\n  ' + '\n  '.join(clash))
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{ext}', dpi=600 if ext == 'png' else 300, bbox_inches=None)
    plt.close(fig)


def load(kit):
    bars = pd.read_csv(os.path.join(kit, 'fig3D_bars.csv'), keep_default_na=False)
    pa = pd.read_csv(os.path.join(kit, 'fig3D_per_animal_fractions.csv'))
    mk = pd.read_csv(os.path.join(kit, 'fig3D_animal_markers.csv'))
    F2 = {}
    for r in bars.itertuples():
        g = pa[(pa.position == r.position) & (pa.epoch == r.epoch)].set_index('animal')[CLS]
        F2[(r.position, r.epoch)] = (np.array([getattr(r, c) for c in CLS]), int(r.n_animals), g)
    STAR2 = {(r.position, r.epoch): r.star for r in bars.itertuples()}
    PA2 = {}
    for r in mk.itertuples():
        PA2.setdefault((r.position, r.epoch), []).append((r.animal, r.complete))
    return F2, STAR2, PA2


def render(kit, out_stem):
    F2, STAR2, PA2 = load(kit)
    rc()
    fig = plt.figure(figsize=(W_PT / 72, H_PT / 72))
    ax = fig.add_axes([LEFT_PT / W_PT, BOTTOM_PT / H_PT, (W_PT - LEFT_PT - RIGHT_PT) / W_PT, AXH_PT / H_PT])
    x0 = 0; ticks = []; tl = []; heads = []
    for p, pl in POS:
        start = x0
        for e in EPS:
            kk = (p, e)
            if kk in F2:
                f, n, pa = F2[kk]
                b = 0
                for i, c in enumerate(CLS):
                    ax.bar(x0, f[i], W, bottom=b, color=COL[c], edgecolor='0.25', lw=0.35); b += f[i]
                if pa is not None and len(pa) > 1:          # SEM across animals of the cumulative fraction
                    cum = pa[CLS].cumsum(axis=1).to_numpy(); m = cum.mean(0); se = cum.std(0, ddof=1) / np.sqrt(len(cum))
                    for i in range(len(CLS) - 1):
                        if se[i] <= 0: continue
                        ax.errorbar(x0 + WOFF * (1 if i % 2 else -1), m[i], yerr=se[i], fmt='none', ecolor='black',
                                    elinewidth=EB['elinewidth'], capsize=EB['capsize'], capthick=EB['capthick'], zorder=5,
                                    path_effects=[pe.withStroke(linewidth=EB['halo'], foreground='white')])
                ticks.append(x0); tl.append(EPL[e])
                st = STAR2.get(kk, '')
                if st:
                    ax.annotate(st, (x0, 1.0), xycoords=('data', 'axes fraction'), xytext=(0, STAR_DY_PT),
                                textcoords='offset points', ha='center', va='bottom', fontsize=FS_T)
                pts = sorted(PA2.get(kk, []))
                for j, (an, v) in enumerate(pts):
                    dx = (j - (len(pts) - 1) / 2) * DX
                    ax.plot(x0 + dx, v, ls='none', marker=S.AN_MK.get(an, 'o'), ms=MS, mfc='white', mec='black',
                            mew=MEW, zorder=6)
            x0 += 1
        heads.append((start - 0.5 + 0.1, x0 - 0.5 - 0.1, pl)); x0 += GAP
    # position titles in two tiers: direction over each group, distance ('near' / 'far') over its three groups
    for xa, xb, t_ in heads:
        dist, dirn = t_.split(' ', 1)
        ax.annotate(dirn, ((xa + xb) / 2, 1.0), xycoords=('data', 'axes fraction'), xytext=(0, HEAD_DY_PT),
                    textcoords='offset points', ha='center', va='bottom', fontsize=FS_T)
    for dist in ('near', 'far'):
        hs = [h for h in heads if h[2].startswith(dist + ' ')]
        if not hs: continue
        xa, xb = hs[0][0], hs[-1][1]
        off = mtr.offset_copy(ax.get_xaxis_transform(), fig=fig, x=0, y=BRACKET_DY_PT, units='points')
        ax.plot([xa, xb], [1.0, 1.0], transform=off, color='black', lw=0.5, clip_on=False, solid_capstyle='butt')
        ax.annotate(dist, ((xa + xb) / 2, 1.0), xycoords=('data', 'axes fraction'), xytext=(0, DIST_DY_PT),
                    textcoords='offset points', ha='center', va='bottom', fontsize=FS_T)
    ax.set_xticks(ticks); ax.set_xticklabels(tl, rotation=TICK_ROT); ax.set_ylim(0, 1)
    ax.set_yticks(YTICKS); ax.set_yticklabels(YTL)
    ax.set_ylabel(YLAB)
    ax.set_xlim(-0.5, x0 - GAP - 0.5)
    ax.tick_params(axis='x', length=0, pad=XPAD)
    hh = [plt.Rectangle((0, 0), 1, 1, fc=COL[c], ec='0.25', lw=0.35, label=LAB[c]) for c in CLS][::-1]
    fig.legend(handles=hh, loc=LEG_LOC, ncol=LEG_NCOL,
               bbox_to_anchor=(0.5 - LEG_X_PT / W_PT, (BOTTOM_PT + AXH_PT + LEG_Y_PT) / H_PT),
               fontsize=LEG_FS, frameon=False, **LEG_KW)
    save(fig, out_stem)
    print('wrote', out_stem)


if __name__ == '__main__':
    a = apply_overrides(sys.argv[1:])
    render(a[0], a[1])
