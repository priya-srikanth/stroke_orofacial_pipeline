"""Supplementary Figure S4C (VLS manuscript): per-animal incorrect licks per trial by post-stroke day,
two-tone cohort (PS46-55, #1-#8), plus the per-animal epoch check of the moderate-animal Results claims.

Measure and filters are those of Fig 1F (correct licks per trial), only the spout changes:
  stats inputs ``no_filter/num_incorrect_licks_per_trial_rw/<animal>.parquet`` (materialize_inputs.py:
  per-session mean over trials of licks to the NON-cued spout with cue + 70 ms <= t <= cue + 8 s;
  visual_gate.compute_num_licks_bySession), sentinel rows and NaN values dropped, pipeline L/R frame
  (all lesions left, so L = ipsilesional, R = contralesional; ``ipsi_contra`` column checked).
  (i)  side L (ipsilesional cue): licks to the R (contralesional, wrong) spout.
  (ii) side R (contralesional cue): licks to the L (ipsilesional, wrong) spout.
Epochs: ``epoch_label`` re-derived from configs/animals.yaml with recovery_epochs.assign_epoch_label (as
c1_panels_c2aligned.py --relabel-epochs; the run fails if a stored label disagrees). Pre = all pre-stroke
sessions (Fig 1F baseline).

Panel style follows S4A (manuscript_code/figures/supp_c1_restyle.py): same 4-column grid geometry and width
(7.2 in), mild row #1-#4, moderate #5-#6 and severe #7-#8, grade-coloured titles and row labels, linear
days-from-stroke axis with pre-stroke sessions in one continuous line, acute / subacute / chronic shading
from derived_epoch_boundaries (stamped columns). Black = licks to the contralesional spout, blue dashed =
licks to the ipsilesional spout (the colours of the contralesional index and the ipsilesional trace in A).

Statistics (descriptive): the pipeline has no per-animal epoch test (pooled_endpoint_suite tests each grade);
per animal, each post epoch vs pre by a two-sided session-level Mann-Whitney U (scipy), no correction.

Outputs (refuses to overwrite):
  <out_fig>.{pdf,png,svg}          panel C alone (7.2 in wide, A/B column geometry)
  <out_table>                      per-animal per-session table
  <out_stats>                      per-animal per-epoch means, n, MWU vs pre

Usage:
  python scripts/manuscript/s4c_incorrect_licks.py <stats_inputs_no_filter_dir> <derived_epoch_boundaries.csv>
         <out_fig_stem> <out_table.csv> <out_stats.csv> [--style-dir <manuscript_code/figures>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'src'), str(REPO)]
from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402

ORDER = ['PS47', 'PS48', 'PS49', 'PS50', 'PS46', 'PS51', 'PS54', 'PS55']
GRADE = {'PS47': 'mild', 'PS48': 'mild', 'PS49': 'mild', 'PS50': 'mild', 'PS46': 'moderate', 'PS51': 'moderate',
         'PS54': 'severe', 'PS55': 'severe'}
EPOCHS = ['pre', 'acute', 'sub_acute', 'chronic']
MEAS = {  # column: (side in the inputs, description)
    'ipsi_cue_contra_spout': ('L', 'ipsilesional-cue trials, licks to the contralesional (wrong) spout'),
    'contra_cue_ipsi_spout': ('R', 'contralesional-cue trials, licks to the ipsilesional (wrong) spout'),
}
CONTRA_COL, IPSI_COL = 'black', '#0077BB'     # as S4A: contralesional index black, ipsilesional trace blue dashed
MILD_TXT = '#B8860B'


def load_table(inp: Path, endpoint: str) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(inp / endpoint / f'{a}.parquet') for a in ORDER], ignore_index=True)
    d = d[~d.is_sentinel.astype(bool)].dropna(subset=['value'])
    want = {'L': 'ipsi', 'R': 'contra'}
    bad = d[d.side.map(want) != d.ipsi_contra]
    if len(bad):
        raise SystemExit(f'side / ipsi_contra mismatch in {endpoint}: {bad[["animal", "side", "ipsi_contra"]].drop_duplicates()}')
    amap = load_animals()
    days = pd.to_datetime(d['date'].astype(str), format='mixed').dt.date
    new = [assign_epoch_label(int(amap[a].day_relative_to_stroke(x)), amap[a]) for a, x in zip(d.animal, days)]
    rel = [int(amap[a].day_relative_to_stroke(x)) for a, x in zip(d.animal, days)]
    if (d.epoch_label.to_numpy() != np.array(new)).any() or (d.rel_day.to_numpy() != np.array(rel)).any():
        raise SystemExit(f'stored epoch_label / rel_day differ from configs/animals.yaml in {endpoint}; re-materialize')
    return d


def session_table(inp: Path) -> pd.DataFrame:
    inc = load_table(inp, 'num_incorrect_licks_per_trial_rw')
    cor = load_table(inp, 'num_correct_licks_per_trial_rw')
    keys = ['animal', 'date', 'rel_day', 'epoch_label']
    out = None
    for col, (side, _) in MEAS.items():
        t = inc[inc.side == side][keys + ['value']].rename(columns={'value': col})
        out = t if out is None else out.merge(t, on=keys, how='outer')
    for side, col in (('L', 'correct_ipsi_cue'), ('R', 'correct_contra_cue')):  # Fig 1F values, for reference
        out = out.merge(cor[cor.side == side][keys + ['value']].rename(columns={'value': col}), on=keys, how='left')
    out.insert(1, 'label', out.animal.map(lambda a: '#' + str(ORDER.index(a) + 1)))
    out.insert(2, 'grade', out.animal.map(GRADE))
    out['date'] = pd.to_datetime(out['date'].astype(str), format='mixed').dt.strftime('%Y-%m-%d')
    out['animal'] = pd.Categorical(out.animal, ORDER, ordered=True)
    return out.sort_values(['animal', 'rel_day']).reset_index(drop=True)


def epoch_stats(tab: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for a in ORDER:
        g = tab[tab.animal == a]
        for col in MEAS:
            pre = g.loc[g.epoch_label == 'pre', col].dropna().to_numpy()
            for ep in EPOCHS:
                v = g.loc[g.epoch_label == ep, col].dropna().to_numpy()
                r = {'animal': a, 'label': '#' + str(ORDER.index(a) + 1), 'grade': GRADE[a], 'measure': col,
                     'epoch': ep, 'n_sessions': v.size, 'mean': v.mean() if v.size else np.nan,
                     'sem': v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else np.nan,
                     'median': np.median(v) if v.size else np.nan,
                     'diff_vs_pre': (v.mean() - pre.mean()) if v.size else np.nan,
                     'mwu_U_vs_pre': np.nan, 'mwu_p_vs_pre': np.nan}
                if ep != 'pre' and v.size and pre.size:
                    u, p = mannwhitneyu(v, pre, alternative='two-sided')
                    r.update(mwu_U_vs_pre=float(u), mwu_p_vs_pre=float(p))
                rows.append(r)
    return pd.DataFrame(rows)


def render(tab: pd.DataFrame, epb: pd.DataFrame, stem: Path, S) -> None:
    import matplotlib.pyplot as plt
    S.apply()
    # Same geometry as S4A (7.2 x 7.6 in, 4 rows, left .12 right .98 top .95 bottom .06, wspace .38, hspace .75):
    # identical axes width and height, 3 rows instead of 4.
    W, H_A = 7.2, 7.6
    h_ax = 0.89 * H_A / (4 + 3 * 0.75)            # axes height in A (in)
    top_in, bot_in = 0.05 * H_A, 0.06 * H_A
    H = top_in + bot_in + h_ax * (3 + 2 * 0.75)
    fig, ax = plt.subplots(3, 4, figsize=(W, H), squeeze=False)
    fig.subplots_adjust(left=0.12, right=0.98, top=1 - top_in / H, bottom=bot_in / H, wspace=0.38, hspace=0.75)
    slots = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (2, 0), (2, 1)]
    for (r, c) in [(1, 2), (1, 3), (2, 2), (2, 3)]:
        ax[r, c].axis('off')
    for a, (r, c) in zip(ORDER, slots):
        x = ax[r, c]; g = tab[tab.animal == a].sort_values('rel_day'); e = epb.loc[a]
        xmax = g.rel_day.max(); acl, chf = e.acute_max_stamped, e.chronic_min_stamped
        x.axvspan(0.5, acl + 0.5, color=S.EP['acute'], alpha=0.18, lw=0)
        x.axvspan(acl + 0.5, chf - 0.5, color=S.EP['subacute'], alpha=0.18, lw=0)
        x.axvspan(chf - 0.5, xmax + 0.5, color=S.EP['chronic'], alpha=0.18, lw=0)
        pre = g[g.epoch_label == 'pre']
        for col, colr, ls in (('contra_cue_ipsi_spout', IPSI_COL, '--'), ('ipsi_cue_contra_spout', CONTRA_COL, '-')):
            x.axhline(pre[col].mean(), color=colr, ls=':', lw=0.6)
            x.plot(g.rel_day, g[col], color=colr, lw=1.0 if ls == '-' else 0.8, ls=ls)
        top = np.nanmax(g[list(MEAS)].to_numpy())
        step = 0.5 if top <= 1.5 else 1 if top <= 3 else 2 if top <= 6 else 5
        ymax = np.ceil(top * 1.05 / step) * step
        x.set_ylim(-0.04 * ymax, ymax); x.set_yticks(np.arange(0, ymax + 1e-9, step) if ymax / step <= 4
                                                       else np.arange(0, ymax + 1e-9, 2 * step))
        x.set_title(S.lab(a), fontsize=7.5, color=MILD_TXT if GRADE[a] == 'mild' else S.SEV[GRADE[a]])
        x.tick_params(labelsize=6.5)
        if c == 0:
            x.set_ylabel('incorrect licks / trial', fontsize=7)
    for r, gname in enumerate(['mild', 'moderate', 'severe']):
        ax[r, 0].annotate(gname, xy=(-0.48, 0.5), xycoords='axes fraction', rotation=90, ha='center', va='center',
                          fontsize=8.5, fontweight='bold', color=MILD_TXT if gname == 'mild' else S.SEV[gname])
    ax[0, 0].text(-0.62, 1.18, 'C', transform=ax[0, 0].transAxes, fontsize=10, fontweight='bold')
    for (r, c) in [(2, 0), (2, 1), (1, 1)]:
        ax[r, c].set_xlabel('days from stroke', fontsize=7)
    h = [plt.Rectangle((0, 0), 1, 1, color=S.EP[k], alpha=0.35, label=k) for k in ['acute', 'subacute', 'chronic']] + \
        [plt.Line2D([], [], color=CONTRA_COL, lw=1.0, label='ipsilesional cue:\nlicks to contralesional spout'),
         plt.Line2D([], [], color=IPSI_COL, lw=0.8, ls='--', label='contralesional cue:\nlicks to ipsilesional spout'),
         plt.Line2D([], [], color='0.3', lw=0.6, ls=':', label='pre-stroke mean (trace colour)')]
    ax[1, 2].legend(handles=h, loc='center left', fontsize=6.3, bbox_to_anchor=(0.05, 0.0))
    S.save(fig, str(stem))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', type=Path); ap.add_argument('epochs', type=Path); ap.add_argument('out_fig', type=Path)
    ap.add_argument('out_table', type=Path); ap.add_argument('out_stats', type=Path)
    ap.add_argument('--style-dir', type=Path, default=Path.home() / 'Documents/Sabatini Lab/Manuscripts/'
                    'VLS stroke methods paper/manuscript_code/figures')
    a = ap.parse_args()
    targets = [a.out_table, a.out_stats] + [a.out_fig.with_suffix(s) for s in ('.pdf', '.png', '.svg')]
    if any(t.exists() for t in targets):
        raise SystemExit('refusing to overwrite: ' + ', '.join(str(t) for t in targets if t.exists()))
    sys.path.insert(0, str(a.style_dir))
    import vls_style as S
    tab = session_table(a.inputs)
    st = epoch_stats(tab)
    epb = pd.read_csv(a.epochs).set_index('animal')
    tab.to_csv(a.out_table, index=False, float_format='%.6g')
    st.to_csv(a.out_stats, index=False, float_format='%.6g')
    render(tab, epb, a.out_fig, S)
    pd.set_option('display.width', 200)
    m = st[st.animal.isin(['PS46', 'PS51'])]
    print(m.round(4).to_string(index=False))
    print('wrote', *targets, sep='\n  ')


if __name__ == '__main__':
    main()
