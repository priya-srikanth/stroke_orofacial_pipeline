"""Six-position scalar panel with the v26 star band (S11A C2_reach_first, S11B C2_speed_first; also Fig 4B/4C of the
same chain), render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what manuscript_code/figures/c2_scalar_compact_v26.py drew through c2_matched.endpoint and
c2_panels.grouped (inlined here, unchanged) for the live C2_reach_first_FINAL_ccB1123 and C2_speed_first_FINAL_ccB1123
(288 x 109.98 pt), from the tables that stage_c2_scalar_tables.py wrote. Nothing is recomputed. Imports only numpy,
pandas, matplotlib and vls_style.py (next to this file). Refuses to overwrite.

Usage: render_c2_scalar.py <sessions.csv> <stats.csv> <spec.json> <out_stem> [--set NAME=VALUE ...]

Presentation settings are in the block below; with the defaults the output is byte-identical to the live PDFs.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                          # noqa: E402
import matplotlib.pyplot as plt                # noqa: E402
from matplotlib.patches import Rectangle       # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
FIG_W_IN = 4.0                 # figure width (in); the height is set by the margins + AX_H below
AX_H = 0.95                    # axes height (in)
MARGINS = dict(left=0.16, right=0.99, bottom=0.25, top=0.92)   # subplots_adjust of the 4.0 x 1.75 in draft canvas
ROW_TOP_PT = 4.5               # center of the first (acute) star row below the axes top (pt)
ROW_STEP_PT = 6.0              # distance between epoch star rows (pt)
BAND_EXTRA_PT = 4.5            # band = ROW_TOP_PT + 2 * ROW_STEP_PT + this (pt), reserved above the data
ROW = {'acute': 0, 'subacute': 1, 'chronic': 2}   # star row per epoch (top to bottom)
EPS = ['pre', 'acute', 'subacute', 'chronic']     # epoch order within a position (marker columns)
POS = ['close_ipsi', 'close_mid', 'close_contra', 'far_ipsi', 'far_mid', 'far_contra']   # group order
XT = ['near\nipsi', 'near\nmid', 'near\ncontra', 'far\nipsi', 'far\nmid', 'far\ncontra']   # x tick labels
C = S.EP                       # epoch colors
W_EP = 0.19                    # marker column spacing within a position
JITTER_SEED = 5                # session-dot jitter
DOT = dict(ms=1.9, alpha=0.35); MARK = dict(ms=4.2, mew=0.4, elinewidth=1.0)
STAR_FS = {2: 8, 1: 9}         # star font size by level ('**' / '*')
YLIM_PCT = (1, 99); YLIM_PAD = 0.08   # data limits: 1st-99th percentile of the session changes +- 8 % of that range
LEGEND = None                  # e.g. dict(loc='lower right', ncol=4, bbox_to_anchor=(1.0, 1.0)) to add an epoch key
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


_STARS, _TOP = [], {}


def grouped(ax, pos, s_get, t_get, w=W_EP, seed=JITTER_SEED):
    """= c2_panels.grouped + c2_scalar_compact.grouped's record of the highest drawn value per position."""
    rng = np.random.RandomState(seed)
    for j, ep in enumerate(EPS):
        for i, p in enumerate(pos):
            x0 = i + (j - 1.5) * w
            v = s_get(p, ep)
            if len(v):
                ax.plot(x0 + (rng.rand(len(v)) - .5) * w * .62, v, 'o', ms=DOT['ms'], mfc=C[ep], mec='none', alpha=DOT['alpha'], zorder=1)
            r = t_get(p, ep)
            if r is None:
                if len(v): ax.plot([x0], [np.mean(v)], 'o', ms=MARK['ms'], mfc=C[ep], mec='k', mew=MARK['mew'], zorder=3)
                continue
            pt, lo, hi, sig = r
            ax.errorbar([x0], [pt], yerr=[[pt - lo], [hi - pt]], fmt='o', ms=MARK['ms'], color=C[ep], mfc=C[ep], mec='k', mew=MARK['mew'],
                        elinewidth=MARK['elinewidth'], capsize=0, zorder=3)
    _TOP.clear()
    for i, p in enumerate(pos):
        vals = []
        for e in EPS:
            v = np.asarray(s_get(p, e), float); vals += list(v[np.isfinite(v)])
            r = t_get(p, e)
            if r is not None: vals.append(r[2])
        _TOP[i] = max(vals) if vals else np.nan
    return w


def epoch_legend(ax, loc='lower left', ncol=2):
    h = [plt.Line2D([], [], marker='o', ls='none', ms=4, color=C[e], mfc=C[e], mec='k', mew=0.4, label=e) for e in EPS]
    lg = ax.legend(handles=h, loc=loc, ncol=ncol, handlelength=0.8, columnspacing=0.7, labelspacing=0.25, borderaxespad=0.15)
    for t in lg.get_texts(): t.set_fontsize(6.6)


def save(fig, stem):
    """= c2_scalar_compact_v26.save (stars in the top band, one row per epoch; axes resized to AX_H)."""
    ax = fig.axes[0]
    y0, y1 = ax.get_ylim()
    tops = [v for v in _TOP.values() if np.isfinite(v)]
    if tops: y1 = min(max(y1, max(tops) + 0.03 * (y1 - y0)), y1 + 0.25 * (y1 - y0))
    band_pt = ROW_TOP_PT + 2 * ROW_STEP_PT + BAND_EXTRA_PT
    band = band_pt / (AX_H * 72.0)
    y1n = y0 + (y1 - y0) / (1.0 - band)
    clip = Rectangle((-10, y0), 20, y1 - y0, transform=ax.transData, fill=False, visible=False)
    ax.add_patch(clip)
    for a in list(ax.lines) + list(ax.collections):
        a.set_clip_path(clip)
    tk = [t for t in ax.get_yticks() if y0 <= t <= y1]
    ax.set_yticks(tk); ax.set_ylim(y0, y1n)
    for a, x, ep, col, lev in _STARS:
        if a is not ax: continue
        yf = 1.0 - (ROW_TOP_PT + ROW[ep] * ROW_STEP_PT) / (AX_H * 72.0)
        ax.text(x, yf, '*' * lev, transform=ax.get_xaxis_transform(), ha='center', va='center', color=col,
                fontsize=STAR_FS[lev], fontweight='bold', gid='sigstar', clip_on=False)
    _STARS.clear()
    ax.set_ylabel(ax.get_ylabel().replace('3-D', '3D').replace('sub-acute', 'subacute'))
    if ax.get_title(): ax.set_title(ax.get_title().replace('3-D', '3D'))
    sp = fig.subplotpars; W, H = fig.get_size_inches()
    bot_in, top_in = sp.bottom * H, (1 - sp.top) * H
    if LEGEND:
        epoch_legend(ax, loc=LEGEND.get('loc', 'lower right'), ncol=LEGEND.get('ncol', 4))
        lg = ax.get_legend(); lg.set_bbox_to_anchor(LEGEND.get('bbox_to_anchor', (1.0, 1.0))); lg.set_frame_on(False); top_in = max(top_in, 0.2)
    H2 = bot_in + AX_H + top_in
    fig.set_size_inches(W, H2); fig.subplots_adjust(bottom=bot_in / H2, top=1 - top_in / H2)
    clash = [f'{stem}.{x}' for x in ('pdf', 'svg', 'png') if os.path.exists(f'{stem}.{x}')]
    if clash: sys.exit('refusing to overwrite:\n  ' + '\n  '.join(clash))
    S.save(fig, stem)


def endpoint(d, t, ylab, stem, level=2):
    """= c2_matched.endpoint (the star call collects for the band; S.headroom is a no-op in the compact chain)."""
    S.apply()
    fig, ax = plt.subplots(figsize=(FIG_W_IN, 1.75)); S.zero_line(ax)
    def tg(p, e):
        r = t[(t.pos == p) & (t.epoch == e)]
        if e == 'pre' or r.empty: return None
        r = r.iloc[0]; return r.boot_change, r.boot_lo, r.boot_hi, int(r.agree == 'both')
    w = grouped(ax, POS, lambda p, e: d[(d.pos == p) & (d.epoch == e)].chg.values, tg)
    v = d.chg.values; lo_, hi_ = np.nanpercentile(v, YLIM_PCT[0]), np.nanpercentile(v, YLIM_PCT[1]); pad = YLIM_PAD * (hi_ - lo_)
    ax.set_ylim(lo_ - pad, hi_ + pad)
    ax.set_xticks(range(6)); ax.set_xticklabels(XT); ax.set_xlim(-.5, 5.5); ax.set_ylabel(ylab)
    for i, p in enumerate(POS):
        for j, e in enumerate(EPS):
            r = tg(p, e)
            if r and r[3]: _STARS.append((ax, i + (j - 1.5) * w, EPS[j], C[e], int(level)))
    fig.subplots_adjust(**MARGINS); save(fig, stem)


def main(sessions, stats, spec, out_stem):
    d = pd.read_csv(sessions)
    t = pd.read_csv(stats); t = t.assign(agree=np.where(t.star_aligned == 1, 'both', ''))
    sp = json.load(open(spec, encoding='utf-8'))
    endpoint(d, t, sp['ylabel'], out_stem)
    print('wrote', out_stem, 'stars:', int(t.star_aligned.sum()))


if __name__ == '__main__':
    a = apply_overrides(sys.argv[1:])
    main(*a[:4])
