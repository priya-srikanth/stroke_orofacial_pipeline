"""S8D (two-tone correction after a miss, px, v5), render kit for CC-A (CC-B, 2026-11-25): verbatim copy of
stroke_orofacial_pipeline scripts/manuscript/recovery_mechanics/s8d_miss_correction_plot.py (af450c9), the script that
made S8D_miss_correction_px_v5_ccB1123 (the D panel of the live S8 composite; CC-A moved its legend 56.9 pt left in
_legleft2). Reads data_px/s8d_alt_sessions_primary.csv and data_px/s8d_alt_stats_primary.csv under the kit folder.
Star rule: ** = q < 0.05 (s8d_alt_px family, BH) AND nested bootstrap CI excludes 0; dagger = single-animal cell,
q < 0.05 AND within-animal CI excludes 0. Settings (canvas, offsets, band, fonts) are the module constants below; any
of them can be given as --set NAME=VALUE.

Usage: render_S8D.py <kit_dir> [out_stem] [--set NAME=VALUE ...]

Original docstring: S8D candidate figure (CC-B 11-23): correction after a miss, LATERAL error (px), change from each animal's pre-stroke.

v3 (Priya 11-23): 2 x 2 grid, rows = ipsilesional cue / contralesional cue, columns = correction gain (miss vs hit) /
error-matched check (10-px |lateral error| bins vs the animal's own pre-stroke misses, miss-weighted).
Hit vs miss styling = the six-position S12D v2 exactly (wf_ccb_s12dmm1123 scripts/caption_review_1123/s12d_mm_render.py,
22e599b2), with the GRADE color in place of the epoch color:
  circles; summary marker ms 3.6, miss = filled (mec k, mew 0.4), hit = open (white face, mec = color, mew 0.9);
  session points miss filled ms 1.6 / hit open ms 1.8 (mew 0.45), alpha 0.4; CI = errorbar elinewidth 0.9, no caps;
  v4 (Priya 11-23): each grade's miss + hit = a tight PAIR, centers PAIR_IN = 0.06 in apart (miss left, hit right);
  grade pairs GRADE_PITCH_IN = 0.19 in apart (gap between pairs 0.13 in, > 2x the pair spacing); epochs farther apart
  still; order mild, moderate, severe in every panel. All offsets are set in INCHES and converted per panel.
Grades sit side by side within an epoch (mild, moderate, severe). Markers: nested animal -> session bootstrap estimate and
95 % CI; single-animal cells: smaller marker (ms 2.6) and DASHED CI (the within-animal bootstrap CI).
Marks in each panel's top band (S8 style, one row per grade in the grade color): ** = q < 0.05 AND CI excludes 0;
dagger = single-animal cell with q < 0.05 AND within-animal CI excludes 0; each mark sits directly above the circle it refers to (miss or hit; v5), in its grade's row, and
the y range is set so that a BAND_PT top band lies above all data and CIs (v4).
Canvas 4.85 x 3.2 in (gain panels 2.70 in, matched panels 1.05 in); faint epoch separators, Arial 6.5 pt, no top / right spine.

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
XL = ['pre', 'ac', 'sub', 'chr']                                           # as S12D
SEV = {'mild': '#F2C02A', 'moderate': '#E0702A', 'severe': '#8E0012'}     # Fig 2 palette (vls_style.SEV)
LEG = '0.2'
W_IN, H_IN = 4.85, 3.2
L_IN, R_IN, GAP_IN = 0.50, 0.05, 0.55
W_GAIN, W_MATCH = 2.70, 1.05
B_IN, T_IN, VGAP_IN = 0.24, 0.30, 0.42
XLIM = (-0.55, 3.55)
PAIR_IN = 0.06            # miss / hit centers within a grade pair (inches)
GRADE_PITCH_IN = {'gain': 0.19, 'match': 0.085}   # grade-to-grade center spacing (inches)
JIT_IN = 0.022            # total width of the session-point jitter (inches)
ROW_PT = 6.5              # one mark row per grade in the top band (points)
BAND_PT = 3 * ROW_PT + 3  # top band height reserved above ALL data and CIs (star_top / reserve_headroom rule)
FS = 6.5
RC = {'font.family': 'Arial', 'font.size': FS, 'axes.labelsize': FS, 'axes.titlesize': FS, 'xtick.labelsize': FS,
      'ytick.labelsize': FS, 'legend.fontsize': FS, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
      'ytick.major.width': 0.6, 'xtick.major.size': 2, 'ytick.major.size': 2, 'pdf.fonttype': 42,
      'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False, 'axes.labelpad': 1.5}


def chg(S, m, side):
    d = S[(S.side == side) & np.isfinite(S[m])].copy()
    d['chg'] = d[m] - d.animal.map(d[d.epoch == 'pre'].groupby('animal')[m].mean())
    return d


def draw(ax, S, R, m, side, gsp, dx=0.0, hollow=False, marks=True, jit=0.03):
    """One class (miss filled / hit hollow) for all grades; returns the values that set the y range."""
    vals = []
    rng = np.random.RandomState(3)
    d = chg(S, m, side)
    for k, gr in enumerate(GRADES):
        col = SEV[gr]
        pt = dict(mfc='none', mec=col, mew=0.45) if hollow else dict(mfc=col, mec='none')
        mk = dict(mfc='white', mec=col, mew=0.9) if hollow else dict(mfc=col, mec='k', mew=0.4)
        g = d[d.grade == gr]
        for i, ep in enumerate(EPOCHS):
            x = i + (k - 1) * gsp + dx
            v = g[g.epoch == ep].chg.to_numpy()
            if len(v):
                ax.plot(x + (rng.rand(len(v)) - .5) * jit, v, 'o', ms=1.8 if hollow else 1.6, alpha=0.4, zorder=1,
                        **pt)
                vals.extend(v)
            if ep == 'pre':
                if len(v):
                    ax.plot([x], [0], 'o', ms=3.6, zorder=3, **mk)
                continue
            r = R[(R.measure == m) & (R.side == side) & (R.grade == gr) & (R.post_epoch == ep)]
            if r.empty:
                continue
            r = r.iloc[0]
            one = bool(r.single_animal)
            est, lo, hi = (r.wa1_effect, r.wa1_ci_lo, r.wa1_ci_hi) if one else (r.nb_effect, r.nb_ci_lo, r.nb_ci_hi)
            if not np.isfinite(est):
                continue
            ax.plot([x, x], [lo, hi], color=col, lw=0.9, ls=(0, (2.0, 1.2)) if one else '-', zorder=2,
                    solid_capstyle='butt')
            ax.plot([x], [est], 'o', ms=2.6 if one else 3.6, zorder=3, **mk)
            vals.extend([lo, hi])
            if marks and isinstance(r.mark, str) and r.mark:
                ax.annotate(r.mark, (x, 1.0), xycoords=('data', 'axes fraction'),   # v5: over the circle it refers to
                            xytext=(0, -1.0 - ROW_PT * k), textcoords='offset points', ha='center', va='top',
                            color=col, fontsize=FS, fontweight='bold')
    return vals


def main(d: str, stem: str = 'S8D_miss_correction_px_v5_ccB1123'):
    d = Path(d)
    if any((d / f'{stem}.{e}').exists() for e in ('pdf', 'png')):
        sys.exit(f'refusing to overwrite {d / stem}')
    S = pd.read_csv(d / 'data_px/s8d_alt_sessions_primary.csv')
    R = pd.read_csv(d / 'data_px/s8d_alt_stats_primary.csv', encoding='utf-8')
    R = R[R.grade.isin(GRADES)]
    plt.rcdefaults()
    plt.rcParams.update(RC)
    fig = plt.figure(figsize=(W_IN, H_IN))
    ph = (H_IN - B_IN - T_IN - VGAP_IN) / 2
    upi = {'gain': (XLIM[1] - XLIM[0]) / W_GAIN, 'match': (XLIM[1] - XLIM[0]) / W_MATCH}   # epoch units per inch
    dx_gain = PAIR_IN / 2 * upi['gain']
    gs = {k: GRADE_PITCH_IN[k] * upi[k] for k in upi}
    axs = {}
    for row, sd in enumerate(['ipsi', 'contra']):
        y0 = B_IN + (1 - row) * (ph + VGAP_IN)
        axs[(row, 0)] = fig.add_axes([L_IN / W_IN, y0 / H_IN, W_GAIN / W_IN, ph / H_IN])
        axs[(row, 1)] = fig.add_axes([(L_IN + W_GAIN + GAP_IN) / W_IN, y0 / H_IN, W_MATCH / W_IN, ph / H_IN])
    vg, vm = [], []
    for row, sd in enumerate(['ipsi', 'contra']):
        jg, jm = JIT_IN * upi['gain'], JIT_IN * upi['match']
        vg.append(draw(axs[(row, 0)], S, R, 'gain_miss_lat', sd, gs['gain'], -dx_gain, False, jit=jg)
                  + draw(axs[(row, 0)], S, R, 'gain_hit_lat', sd, gs['gain'], dx_gain, True, jit=jg))
        vm.append(draw(axs[(row, 1)], S, R, 'binned_lat', sd, gs['match'], jit=jm))
    for col, vv in ((0, vg), (1, vm)):                                     # one y scale per column (both cues)
        v = np.asarray(vv[0] + vv[1], float)
        lo, hi = np.nanmin(v), np.nanmax(v)
        rg = hi - lo
        for row in (0, 1):
            f = BAND_PT / (ph * 72)                                    # band as a fraction of the axes height
            y0_ = lo - 0.04 * rg
            axs[(row, col)].set_ylim(y0_, y0_ + (hi + 0.02 * rg - y0_) / (1 - f))   # data + CIs end below the band
            tk = [t for t in axs[(row, col)].get_yticks() if y0_ <= t <= hi + 0.02 * rg]   # no ticks in the band
            axs[(row, col)].set_yticks(tk)
    for (row, col), ax in axs.items():
        ax.axhline(0, color='0.6', lw=0.6, ls='--', zorder=0)
        for xb in (0.5, 1.5, 2.5):                                         # faint epoch separators
            ax.axvline(xb, color='0.88', lw=0.5, zorder=0)
        ax.set_xticks(range(4), XL)
        ax.set_xlim(*XLIM)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_title(f'{"ipsilesional" if row == 0 else "contralesional"} cue', fontsize=FS, pad=3)
        ax.set_ylabel('$\\Delta$ correction gain\n(fraction of lateral error)' if col == 0
                      else '$\\Delta$ correction after a miss,\nerror-matched (px)')
    h = [plt.Line2D([], [], marker='o', ls='none', ms=3.6, mfc=SEV[g], mec='k', mew=0.4, label=g) for g in GRADES]
    h += [plt.Line2D([], [], marker='o', ls='none', ms=3.6, mfc=LEG, mec=LEG, mew=0.4, label='after a miss'),
          plt.Line2D([], [], marker='o', ls='none', ms=3.6, mfc='white', mec=LEG, mew=0.9, label='after a hit'),
          plt.Line2D([], [], color=LEG, lw=0.9, ls=(0, (2.0, 1.2)), marker='o', ms=2.6, mfc=LEG, mec='k', mew=0.4,
                     label='one animal')]
    fig.legend(handles=h, ncol=6, loc='upper center', bbox_to_anchor=(0.5, 1.0), frameon=False, borderaxespad=0.15,
               handlelength=1.0, handletextpad=0.3, columnspacing=1.0)
    for e in ('pdf', 'png'):
        fig.savefig(d / f'{stem}.{e}', dpi=600 if e == 'png' else None)
    plt.close(fig)
    print(f'canvas {W_IN} x {H_IN} in; gain panel {W_GAIN} in, matched panel {W_MATCH} in; miss/hit dx {dx_gain:.3f} u, grade pitch {gs}')


def apply_overrides(argv):
    """--set NAME=VALUE (repeatable): override any module-level setting; values are Python literals."""
    import ast
    out, i = [], 0
    while i < len(argv):
        if argv[i] == '--set':
            k, v = argv[i + 1].split('=', 1)
            try: v = ast.literal_eval(v)
            except (ValueError, SyntaxError): pass
            globals()[k] = v; i += 2
        else:
            out.append(argv[i]); i += 1
    return out


if __name__ == '__main__':
    main(*apply_overrides(sys.argv[1:])[:2])
