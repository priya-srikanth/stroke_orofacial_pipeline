"""S8D candidate figure (CC-B 11-23): correction after a miss, LATERAL error (px), change from each animal's pre-stroke.

Layout mirrors the six-position S12D figure: left pair = correction gain after a miss (FILLED marker, grade color) with
the gain after a hit beside it (OPEN marker, same grade color; v2 style, Priya 11-23); right pair = the error-matched check (10-px |lateral error| bins
vs the animal's own pre-stroke misses, miss-weighted). Each pair = ipsilesional cue, contralesional cue (as S8D).
Points: per-session change, faint; markers: nested animal -> session bootstrap estimate and 95 % CI (single-animal cells:
smaller marker, DASHED CI line = the within-animal bootstrap CI; open vs filled is reserved for hit vs miss). Marks in the top band (S8 style): ** = q < 0.05 AND CI excludes 0,
dagger = single-animal cell (q < 0.05 AND within-animal CI excludes 0), shifted 0.30 epoch right.
Canvas 3.25 x 1.55 in (the live S8D panel), Arial 6.5 pt.

    python s8d_miss_correction_plot.py <twotone_s8d dir> [stem]
Refuses to overwrite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

GRADES = ['mild', 'moderate', 'severe']
EPOCHS = ['pre', 'acute', 'sub_acute', 'chronic']
EPL = ['pre', 'acute', 'subacute', 'chronic']
SEV = {'mild': '#F2C02A', 'moderate': '#E0702A', 'severe': '#8E0012'}     # Fig 2 palette (vls_style.SEV)
MK = {'mild': 'o', 'moderate': 's', 'severe': 'D'}
OFF = {'mild': -0.24, 'moderate': -0.02, 'severe': 0.20}
HIT_DX = 0.09
DAG_DX = 0.30
RC = {'font.family': 'Arial', 'font.size': 6.5, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
      'ytick.major.width': 0.6, 'xtick.major.size': 2, 'ytick.major.size': 2, 'pdf.fonttype': 42,
      'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False, 'axes.labelpad': 1.5}


def chg(S, m, side):
    d = S[(S.side == side) & np.isfinite(S[m])].copy()
    d['chg'] = d[m] - d.animal.map(d[d.epoch == 'pre'].groupby('animal')[m].mean())
    return d


def draw(ax, S, R, m, side, hit_m=None):
    vals, cis = [], []
    for kind, mm in (('miss', m), ('hit', hit_m)):
        if mm is None:
            continue
        d = chg(S, mm, side)
        for gr in GRADES:
            g = d[d.grade == gr]
            for i, ep in enumerate(EPOCHS):
                x = i + OFF[gr] + (HIT_DX if kind == 'hit' else 0)
                col = SEV[gr]
                mfc = 'white' if kind == 'hit' else col
                v = g[g.epoch == ep].chg.to_numpy()
                if len(v) and kind == 'miss':
                    ax.scatter(x + np.random.default_rng(i).uniform(-.03, .03, len(v)), v, s=2, color=col,
                               alpha=0.18, linewidths=0, zorder=1)
                vals.extend(v)
                if ep == 'pre':
                    if len(v):
                        ax.plot([x], [0], MK[gr], ms=2.6, color=col, mfc=mfc, mec='k' if kind == 'miss' else col,
                                mew=0.3 if kind == 'miss' else 0.6, zorder=3)
                    continue
                r = R[(R.measure == mm) & (R.side == side) & (R.grade == gr) & (R.post_epoch == ep)]
                if r.empty:
                    continue
                r = r.iloc[0]
                one = bool(r.single_animal)
                est, lo, hi = ((r.wa1_effect, r.wa1_ci_lo, r.wa1_ci_hi) if one else (r.nb_effect, r.nb_ci_lo, r.nb_ci_hi))
                if not np.isfinite(est):
                    continue
                ax.plot([x, x], [lo, hi], color=col, lw=0.7, ls=(0, (1.6, 1.0)) if one else '-', zorder=2)
                ax.plot([x], [est], MK[gr], ms=1.8 if one else 2.6, mfc=mfc, color=col,
                        mec='k' if kind == 'miss' else col, mew=0.3 if kind == 'miss' else 0.6, zorder=3)
                cis.extend([lo, hi])
                if kind == 'miss' and isinstance(r.mark, str) and r.mark:
                    k = GRADES.index(gr)
                    ax.annotate(r.mark, (i + (DAG_DX if r.mark != '**' else 0), 1.0),
                                xycoords=('data', 'axes fraction'), xytext=(0, 1 - 5.2 * k), textcoords='offset points',
                                ha='center', va='top', color=SEV[gr], fontsize=6.5, fontweight='bold')
    v = np.asarray(vals, float)
    v = v[np.isfinite(v)]
    lo_, hi_ = min(np.percentile(v, 1), min(cis)), max(np.percentile(v, 99), max(cis))
    rng_ = hi_ - lo_
    return lo_ - 0.06 * rng_, hi_ + 0.45 * rng_          # top band reserved for the three mark rows


def main(d: str, stem: str = 'S8D_miss_correction_px_v2_ccB1123'):
    d = Path(d)
    if any((d / f'{stem}.{e}').exists() for e in ('pdf', 'png')):
        sys.exit(f'refusing to overwrite {d / stem}')
    S = pd.read_csv(d / 'data_px/s8d_alt_sessions_primary.csv')
    R = pd.read_csv(d / 'data_px/s8d_alt_stats_primary.csv', encoding='utf-8')
    R = R[R.grade.isin(GRADES)]
    plt.rcParams.update(RC)
    fig = plt.figure(figsize=(3.25, 1.55))
    L, B, H, W, WS, GAP = 0.135, 0.22, 0.565, 0.163, 0.018, 0.15
    axs = [fig.add_axes([L, B, W, H]), None, None, None]
    axs[1] = fig.add_axes([L + W + WS, B, W, H], sharey=axs[0])
    x2 = L + 2 * W + WS + GAP
    axs[2] = fig.add_axes([x2, B, W, H])
    axs[3] = fig.add_axes([x2 + W + WS, B, W, H], sharey=axs[2])
    yl = [draw(axs[k], S, R, 'gain_miss_lat', sd, 'gain_hit_lat') for k, sd in ((0, 'ipsi'), (1, 'contra'))]
    axs[0].set_ylim(min(a for a, _ in yl), max(b for _, b in yl))
    yl = [draw(axs[k], S, R, 'binned_lat', sd) for k, sd in ((2, 'ipsi'), (3, 'contra'))]
    axs[2].set_ylim(min(a for a, _ in yl), max(b for _, b in yl))
    for k, ax in enumerate(axs):
        ax.axhline(0, color='0.6', lw=0.5, ls='--', zorder=0)
        ax.set_xticks(range(4), EPL, rotation=40, ha='right')
        ax.tick_params(labelsize=6.0, pad=1)
        ax.set_xlim(-0.5, 3.5)
        ax.set_title('ipsilesional\ncue' if k % 2 == 0 else 'contralesional\ncue', fontsize=6.0, pad=1.5,
                     linespacing=0.95)
        if k % 2:
            ax.tick_params(labelleft=False)
    axs[0].set_ylabel('$\\Delta$ correction gain,\nlateral (fraction)', fontsize=6.0)
    axs[2].set_ylabel('$\\Delta$ correction after a miss,\nerror-matched (px)', fontsize=6.0)
    h = [plt.Line2D([], [], color=SEV[g], marker=MK[g], ls='none', mec='k', mew=0.3, ms=3, label=g) for g in GRADES]
    h += [plt.Line2D([], [], color='0.3', marker='o', ls='none', mec='k', mew=0.3, ms=3, label='after a miss'),
          plt.Line2D([], [], color='0.3', marker='o', ls='none', mfc='white', mec='0.3', mew=0.6, ms=3,
                     label='after a hit'),
          plt.Line2D([], [], color='0.3', ls=(0, (1.6, 1.0)), lw=0.7, label='one animal')]
    fig.legend(handles=h, ncol=6, loc='upper center', bbox_to_anchor=(0.5, 1.0), fontsize=5.6, frameon=False,
               handletextpad=0.1, columnspacing=0.6, borderaxespad=0.1, handlelength=1.2)
    for e in ('pdf', 'png'):
        fig.savefig(d / f'{stem}.{e}', dpi=600 if e == 'png' else None)
    plt.close(fig)


if __name__ == '__main__':
    main(*sys.argv[1:3])
