"""Standalone, Mac-runnable renderer for the two-tone (cohort 1) per-epoch panels (CC-B 2026-11-25; layout inputs for
CC-A). Fig 1E-G, Fig 2C-F: F1_accuracy, F1_correct_licks, F1_latency, F2_first_lick_time, S_xy_all, F2_speed_all,
F2_angle_first.

Inputs (written by c1_render_v28.py --dump on the analysis desktop, branch ccB-pnas-panels-20261125):
  <stem>_sessions.csv  one row per animal x session x cue side: value (session value), b (the animal's pre mean for
                       that side), delta = (value - b) * sign (plotted), ph = severity grade, epoch_label
  <stem>_marks.csv     the stats-sheet rows of this endpoint (pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_
                       ccB1123): recovery_phenotype x side (L / R / both) x post_epoch, 'mark' = '**' (q < 0.05 and
                       nested bootstrap CI excludes 0) or the dagger (one animal: q < 0.05 and within-animal CI) or ''
  <stem>_spec.json     y label (and endpoint / family for reference)
Modes (output = <out_stem>.pdf/.svg/.png, refuses to overwrite):
  orig  the c1_panels.render drawing (= live *_FINAL_ccB1123)
  v28   PNAS band: grade rows 3.5 pt below the axes top, 4.5 pt apart, 14.5 pt band; data area to the highest drawn
        point (zero line kept inside); only ticks inside the data area (= *_FINAL_v28_ccB1125)
  v29   as v28, but the axis line covers the data: it ends at the first major tick at or above the highest drawn
        point, which keeps its label; the data area is raised to it (= *_FINAL_v29_ccB1125)
v28 / v29 set VLS_SPINE_TO_TICKS=1 for the vls_style.py next to this script (a verbatim copy of
manuscript_code/figures/vls_style.py as of 2026-11-25).

Usage: python render_c1_panel.py <sessions.csv> <marks.csv> <spec.json> <out_stem> --mode {orig,v28,v29,v30}
v30 (PROMPT_CC_B_ticks_stars_fig3D_v2 items 1, 2, 2b; = *_FINAL_v30_ccB1125): band_rule.py next to this script:
  tick step from 1/2/2.5/4/5 x 10^k (4-8 ticks), first tick at/above the data top closest to it, spine ends there;
  mark rows 3.0 pt below the band top, 4.0 pt apart, 1.5 pt below the last, only the rows (severe / moderate /
  mild) the panel uses; lower limit extended so every mean marker, SEM bar and connecting line is inside the
  data area (2 % of the live range below the lowest; session dots may fall below). Prints a one-line log.
Deps: python 3.11, numpy, pandas, matplotlib 3.11.2 (the version of the live files), Arial installed.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

EPOCHS = [('pre', 'pre'), ('acute', 'acute'), ('sub_acute', 'subacute'), ('chronic', 'chronic')]
PHENOS = ['mild', 'moderate', 'severe']
SIDE_T = {'L': 'ipsilesional cue', 'R': 'contralesional cue', 'global': ''}
SHEET_SIDE = {'L': 'L', 'R': 'R', 'global': 'both'}
DAG_SCALE, DAG_DX = 0.75, 0.30
ROW_TOP_PT, ROW_STEP_PT = 3.5, 4.5
BAND_PT = ROW_TOP_PT + 2 * ROW_STEP_PT + 2.0


def mark_for(marks, ph, side, epoch):
    m = marks[(marks.recovery_phenotype == ph) & (marks.side == SHEET_SIDE[side]) & (marks.post_epoch == epoch)]
    v = m.iloc[0]['mark'] if not m.empty else None
    return v if v in ('**', '†') else ''


def drawn_y(ax):
    from matplotlib.collections import LineCollection, PathCollection
    ys = []
    for c in ax.collections:
        if isinstance(c, LineCollection):
            for s in c.get_segments():
                ys.extend(np.asarray(s, float)[:, 1])
        elif isinstance(c, PathCollection):
            o = np.asarray(c.get_offsets(), float)
            if o.ndim == 2 and o.shape[0]:
                ys.extend(o[:, 1])
    for ln in ax.lines:
        yd = np.asarray(ln.get_ydata(), float)
        if yd.size and not (np.allclose(yd, 0) and ln.get_linestyle() in ('--', 'dashed')):
            ys.extend(yd)
    ys = np.asarray(ys, float)
    return ys[np.isfinite(ys)]


def data_top(top, y0, live_ticks, mode):
    """band_rule.py of the repo (v28 / v29)."""
    lt = np.asarray(sorted(live_ticks), float)
    if mode == 'v28':
        yd1 = top + 0.01 * (top - y0)
        if y0 < 0:
            yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
        return yd1, [t for t in lt if y0 <= t <= yd1 + 1e-12]
    step = float(np.median(np.diff(lt)))
    tick = round(float(lt[0] + np.ceil((top - lt[0]) / step - 1e-9) * step), 10)
    yd1 = max(tick, top + 0.01 * (top - y0))
    if y0 < 0:
        yd1 = max(yd1, 0.0 + 0.05 * (max(yd1, 0.0) - y0))
    n = int(np.floor((tick - lt[0]) / step + 1e-9))
    grid = [round(float(lt[0] + i * step), 10) for i in range(n + 1)]
    return yd1, [t for t in grid if y0 <= t <= tick + 1e-12]


def render(d, marks, ylab, stem, mode):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import vls_style as S
    sides = [x for x in ('L', 'R', 'global') if x in set(d.side)]
    fig, axes = plt.subplots(1, len(sides), figsize=(1.45 * len(sides) + 0.35, 1.55), sharey=True, squeeze=False)
    axes = axes[0]
    lo, hi = d.delta.quantile(0.01), d.delta.quantile(0.99)
    span = hi - lo
    for ax, side in zip(axes, sides):
        ds = d[d.side == side]
        S.zero_line(ax)
        for k, ph in enumerate(PHENOS):
            dp = ds[ds.ph == ph]; xs, ms, es = [], [], []
            for i, (e, _) in enumerate(EPOCHS):
                v = dp[dp.epoch_label == e].delta
                if v.empty: continue
                off = (k - 1) * 0.09
                ax.scatter(i + off + np.random.default_rng(i + 10 * k).uniform(-.03, .03, len(v)), v, s=4,
                           color=S.SEV[ph], alpha=0.18, lw=0, zorder=1)
                xs.append(i + off); ms.append(v.mean()); es.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0)
            ax.errorbar(xs, ms, yerr=es, color=S.SEV[ph], marker=S.SEV_MK[ph], ms=3.6, mec='k', mew=0.35,
                        lw=0, elinewidth=0.9, capsize=0, zorder=3)
            for j in range(len(xs) - 1):
                gap = round(xs[j + 1] - xs[j]) > 1
                if gap:      # epoch bridge (severe: no acute data): dotted, faint, behind the data
                    ax.plot(xs[j:j + 2], ms[j:j + 2], color=S.SEV[ph], lw=1.0, ls=(0, (1, 1.6)), alpha=0.4, zorder=0.5)
                else:
                    ax.plot(xs[j:j + 2], ms[j:j + 2], '-', color=S.SEV[ph], lw=1.0, zorder=2)
        ax.set_xticks(range(4)); ax.set_xticklabels([n for _, n in EPOCHS], rotation=32, ha='right', rotation_mode='anchor')
        ax.set_xlim(-0.5, 3.5)
        if SIDE_T[side]: ax.set_title(SIDE_T[side], fontsize=7.5, pad=2)
    if mode == 'orig':
        axes[0].set_ylim(lo - 0.08 * span, hi + 0.42 * span)
        y0, y1 = axes[0].get_ylim()
        for ax, side in zip(axes, sides):
            for row, ph in enumerate(['severe', 'moderate', 'mild']):
                for i, (e, _) in enumerate(EPOCHS[1:], start=1):
                    mk = mark_for(marks, ph, side, e)
                    if mk:
                        ax.text(i + (DAG_DX if mk != '**' else 0), y1 - (0.07 + 0.085 * row) * (y1 - y0), mk,
                                color=S.SEV[ph], ha='center', va='center',
                                fontsize=8 * (DAG_SCALE if mk != '**' else 1), fontweight='bold')
        axes[0].set_ylabel(ylab)
        fig.subplots_adjust(left=0.30 if len(sides) == 1 else 0.20, right=0.98, bottom=0.28, top=0.86, wspace=0.12)
        S.save(fig, stem)
        return
    y0, live_y1 = lo - 0.08 * span, hi + 0.42 * span
    y0_live = y0
    if mode == 'v30':                    # item 2b: every marker / SEM bar / connecting line inside the data area
        import band_rule as BR
        cl = min(BR.cover_low(ax) for ax in axes)
        if cl - 0.02 * span < y0: y0 = cl - 0.02 * span
    axes[0].set_ylim(y0, live_y1)
    live_ticks = list(axes[0].get_yticks())
    axes[0].set_ylabel(ylab)
    fig.subplots_adjust(left=0.30 if len(sides) == 1 else 0.20, right=0.98, bottom=0.28, top=0.86, wspace=0.12)
    ys = np.concatenate([drawn_y(ax) for ax in axes])
    top = ys[(ys >= y0) & (ys <= live_y1)].max()
    if mode == 'v30':
        import band_rule as BR
        yd1, ticks, spine_tick = BR.data_top(top, y0, live_ticks, 'v30')
        used = {row for row, ph in enumerate(['severe', 'moderate', 'mild']) for side in sides
                for e, _ in EPOCHS[1:] if mark_for(marks, ph, side, e)}
        band_pt = BR.band_pt(used)
    else:
        yd1, ticks = data_top(top, y0, live_ticks, mode); spine_tick = None; band_pt = BAND_PT
    ah_pt = axes[0].get_position().height * fig.get_size_inches()[1] * 72.0
    y1n = y0 + (yd1 - y0) / (1.0 - band_pt / ah_pt)
    for ax in axes:
        clip = Rectangle((-10, y0), 20, yd1 - y0, transform=ax.transData, fill=False, visible=False)
        ax.add_patch(clip)
        for a in list(ax.lines) + list(ax.collections):
            a.set_clip_path(clip)
    axes[0].set_yticks(ticks)
    axes[0].set_ylim(y0, y1n)
    for ax, side in zip(axes, sides):
        for row, ph in enumerate(['severe', 'moderate', 'mild']):
            for i, (e, _) in enumerate(EPOCHS[1:], start=1):
                mk = mark_for(marks, ph, side, e)
                if mk:
                    yf = BR.row_y(row, ah_pt) if mode == 'v30' else 1.0 - (ROW_TOP_PT + row * ROW_STEP_PT) / ah_pt
                    ax.text(i + (DAG_DX if mk != '**' else 0), yf, mk,
                            transform=ax.get_xaxis_transform(), color=S.SEV[ph], ha='center', va='center',
                            fontsize=8 * (DAG_SCALE if mk != '**' else 1), fontweight='bold', clip_on=False)
    S.save(fig, stem)
    if mode == 'v30':
        print(f'LOG {Path(stem).name}: y0_live={y0_live:.6g} y0={y0:.6g} lower_changed={y0 < y0_live} '
              f'data_top={top:.6g} spine_tick={spine_tick} ticks={ticks} band_pt={band_pt} rows={sorted(used)} '
              f'ylim_top={y1n:.6g} newly_clipped={int(((ys > yd1) & (ys <= live_y1)).sum())}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sessions'); ap.add_argument('marks'); ap.add_argument('spec'); ap.add_argument('out_stem')
    ap.add_argument('--mode', choices=['orig', 'v28', 'v29', 'v30'], required=True)
    a = ap.parse_args()
    for x in ('pdf', 'svg', 'png'):
        if Path(f'{a.out_stem}.{x}').exists():
            sys.exit(f'refusing to overwrite {a.out_stem}.{x}')
    if a.mode != 'orig':
        os.environ['VLS_SPINE_TO_TICKS'] = '1'      # before vls_style.apply()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import matplotlib
    matplotlib.use('Agg')
    import vls_style as S
    S.apply()
    matplotlib.rcParams['axes.labelpad'] = 1.5
    d = pd.read_csv(a.sessions)
    marks = pd.read_csv(a.marks, encoding='utf-8', keep_default_na=False, na_values=[''])
    marks['mark'] = marks['mark'].fillna('')
    spec = json.loads(Path(a.spec).read_text(encoding='utf-8'))
    render(d, marks, spec['ylabel'], a.out_stem, a.mode)


if __name__ == '__main__':
    main()
