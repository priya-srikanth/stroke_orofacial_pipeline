"""[Mac-runnable package copy: vls_style.py and band_rule.py from this folder, c2_panels pieces inlined; otherwise
identical to scripts/manuscript/pnas_ccB1125/fr_fig5_right_pnas.py on branch ccB-pnas-panels-20261125.
Deps: python 3.11, numpy, pandas, matplotlib 3.11.2, Arial.]

PNAS Figure 5 right column (CC-B 2026-11-25; PROMPT_CC_B_pnas_panels_2026-11-25 item 2).

Copy of manuscript_code/figures/fr_fig5_right_v28.py (verbatim copy kept as mc_copies/fr_fig5_right_v28.py; the
original is not edited). Same data, statistics, marks, fonts, axes sizes and positions as the live
FR_fig5_right_contact_terms_v28b_loo02_fourcam_ccB1123 (run with --no-spout-header semantics: no G/H spout header).
Changes (Priya's PNAS star rules, mirroring CC-A's c2_scalar_compact_v28.py):
  1. VLS_SPINE_TO_TICKS=1 (vls_style hook): y-axis line stops at the top tick inside the data area;
  2. marks in a fixed top band, one row per epoch (acute top, subacute, chronic; as c2 v28), first row 3.5 pt below
     the band top, 4.5 pt between rows, 2 pt below the last row; each mark keeps its live x (epoch column), text,
     colour and font size;
  3. data area ends 1 % of the range above the highest drawn point (session dot or marker +- SEM/CI, at most the live
     upper limit) and always holds the dashed zero line with a 5 % margin; data artists clipped to the data area.
     F keeps its "contra spout | ipsi spout" labels: they get their own 8 pt line at the top of F's band.
The figure is drawn once at the live canvas (2.45 x 5.98 in, axes at the live positions, y labels aligned across all
four as live) and saved as two crops (bbox in inches, full width 176.4 pt):
  out_stem with '{part}' -> 'EF' (E and F, main figure) and 'GH' (G and H, SI).
Usage: fr_fig5_right_pnas.py <session_scalars_per_session.csv> <fr_session_scalars.csv> <dir with peak_*_side.csv>
       <out_stem containing {part}> [--v29]       (refuses to overwrite)
--v29 (PROMPT_CC_B_layout_inputs_2026-11-25 item 1): data-area top / ticks by band_rule v29.
"""
import os
import sys
from pathlib import Path

os.environ['VLS_SPINE_TO_TICKS'] = '1'          # before vls_style.apply()
sys.path.insert(0, str(Path(__file__).resolve().parent))   # vls_style.py, band_rule.py next to this script
import numpy as np, pandas as pd, matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402
import vls_style as S  # noqa: E402
import band_rule as BR  # noqa: E402
MODE = 'v29' if '--v29' in sys.argv else 'v28'   # v29: band_rule v29 (axis line covers the data, labelled top tick)
sys.argv = [x for x in sys.argv if x != '--v29']
# ---- from manuscript_code/figures/c2_panels.py (verbatim; that module also imports scipy and its own S.apply())
EPS = ['pre', 'acute', 'subacute', 'chronic']
C = S.EP


def epoch_legend(ax, loc='lower left', ncol=2):
    h = [plt.Line2D([], [], marker='o', ls='none', ms=4, color=C[e], mfc=C[e], mec='k', mew=0.4, label=e) for e in EPS]
    lg = ax.legend(handles=h, loc=loc, ncol=ncol, handlelength=0.8, columnspacing=0.7, labelspacing=0.25, borderaxespad=0.15)
    for t in lg.get_texts(): t.set_fontsize(6.6)


def grouped(ax, pos, s_get, t_get, w=0.19, seed=1):
    rng = np.random.RandomState(seed); ns = 0
    for j, ep in enumerate(EPS):
        for i, p in enumerate(pos):
            x0 = i + (j - 1.5) * w
            v = s_get(p, ep)
            if len(v):
                ax.plot(x0 + (rng.rand(len(v)) - .5) * w * .62, v, 'o', ms=1.9, mfc=C[ep], mec='none', alpha=0.35, zorder=1)
            r = t_get(p, ep)
            if r is None:
                if len(v): ax.plot([x0], [np.mean(v)], 'o', ms=4.2, mfc=C[ep], mec='k', mew=0.4, zorder=3)
                continue
            pt, lo, hi, sig = r
            ax.errorbar([x0], [pt], yerr=[[pt - lo], [hi - pt]], fmt='o', ms=4.2, color=C[ep], mfc=C[ep], mec='k', mew=0.4,
                        elinewidth=1.0, capsize=0, zorder=3)
    return w
# ----
S.apply()
S.apply()
pts, stf, fd, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4]
assert '{part}' in out, out
for sfx in ('EF', 'GH'):
    for x in ('pdf', 'svg', 'png'):
        if Path(out.replace('{part}', sfx) + f'.{x}').exists():
            sys.exit(f'refusing to overwrite {out} {sfx}.{x}')
P = pd.read_csv(pts); ST = pd.read_csv(stf)
if 'measure' in P.columns:
    P = P[P.measure.isin(['angle_spatial', 'angle_spectral', 'side_spec'])].rename(columns={'unit': 'factor'})
    P['axes'] = P.measure.map({'angle_spatial': 2, 'angle_spectral': 3, 'side_spec': 4})
NAME = {'lick_right': 'lick\ncontra', 'lick_left': 'lick\nipsi', 'slow_jaw': 'slow\njaw', 'whisk_run': 'whisk\nrun'}
MEAS = {2: 'angle_spatial', 3: 'angle_spectral', 4: 'side_spec'}
W, L, R = 2.45, 0.66, 0.05
HS = [1.0, 1.0, 0.80, 0.80]
GAP = [0.28, 0.5, 0.62, 0.62]
BOT = 0.36
H = BOT + sum(HS) + sum(GAP)
fig = plt.figure(figsize=(W, H))
axs = []; y = H
for h, g in zip(HS, GAP):
    y -= g + h; axs.append(fig.add_axes([L / W, y / H, 1 - (L + R) / W, h / H]))

ROW_TOP_PT, ROW_STEP_PT, BELOW_PT = 3.5, 4.5, 2.0
ROW = {'acute': 0, 'subacute': 1, 'chronic': 2}
SPOUT_PT = 8.0                                    # F only: line for the spout labels above the star rows
MARKS = {id(a): [] for a in axs}                  # (x, epoch, colour, text, fontsize)
LIVE_TOP = {}
LOG = []


def shapes(ax, a, facs, w=0.21):
    rng = np.random.RandomState(3)
    for i, f in enumerate(facs):
        for j, e in enumerate(EPS):
            x0 = i + (j - 1.5) * w; q = P[(P['axes'] == a) & (P.factor == f) & (P.epoch == e)]
            v = q.value.values
            if len(v): ax.plot(x0 + (rng.rand(len(v)) - .5) * w * .62, v, 'o', ms=1.9, mfc=C[e], mec='none', alpha=0.35, zorder=1)
            if len(q):
                m, se = q.value.mean(), q.value.std(ddof=1) / np.sqrt(len(q))
                ax.errorbar([x0], [m], yerr=[se], fmt='o', ms=4.0, color=C[e], mfc=C[e], mec='k', mew=0.4, elinewidth=1.0, capsize=0, zorder=3)
    ax.set_xticks(range(len(facs))); ax.set_xticklabels([NAME[f] for f in facs]); ax.set_xlim(-.5, len(facs) - .5); S.zero_line(ax)
    v = P[(P['axes'] == a) & P.factor.isin(facs)].value; lo, hi = v.quantile(0.005), v.max()
    ax.set_ylim(lo - 0.06 * (hi - lo), hi + 0.06 * (hi - lo))
    y0, y1 = ax.get_ylim(); top = {}
    for i, f in enumerate(facs):
        q = P[(P['axes'] == a) & (P.factor == f)].value; top[i] = q.max()
        for j, e in enumerate(EPS[1:], 1):
            r = ST[(ST.measure == MEAS[a]) & (ST.unit == f) & (ST.epoch == e)]
            if r.empty: continue
            ph = r.p_holm.iloc[0]; lev = 2 if ph < 0.01 else 1 if ph < 0.05 else 0
            if lev: MARKS[id(ax)].append((i + (j - 1.5) * w, e, C[e], '*' * lev, 7 if len(facs) > 2 else 8))
    LIVE_TOP[id(ax)] = max(y1, max(top.values()) + 0.36 * (y1 - y0))   # live upper limit (for the log / cap)
    ax.set_ylim(y0, y1)


def letter(ax, s): return ax.text(-L / (W - L - R), 1.0 + 0.16 / (ax.get_position().height * H), s, transform=ax.transAxes, fontsize=8, weight='bold', va='bottom')


def drawn_y(ax):
    from matplotlib.collections import LineCollection, PathCollection
    ys = []
    for c in ax.collections:
        if isinstance(c, LineCollection):
            for sg in c.get_segments(): ys.extend(np.asarray(sg, float)[:, 1])
        elif isinstance(c, PathCollection):
            o = np.asarray(c.get_offsets(), float)
            if o.ndim == 2 and o.shape[0]: ys.extend(o[:, 1])
    for ln in ax.lines:
        yd = np.asarray(ln.get_ydata(), float)
        if yd.size and not (np.allclose(yd, 0) and ln.get_linestyle() in ('--', 'dashed')): ys.extend(yd)
    ys = np.asarray(ys, float); return ys[np.isfinite(ys)]


def finish(ax, name, extra_pt=0.0):
    """Data area to the highest drawn point (zero line inside), fixed band above, marks in epoch rows."""
    y0, _ = ax.get_ylim(); live_top = LIVE_TOP[id(ax)]
    ticks = list(ax.get_yticks())
    ax.set_ylim(y0, live_top); live_ticks = list(ax.get_yticks())
    ys = drawn_y(ax); vis = ys[(ys >= y0) & (ys <= live_top)]
    top = vis.max(); yd1, keep_ticks, spine_tick = BR.data_top(top, y0, live_ticks, MODE)
    ah_pt = ax.get_position().height * H * 72
    band_pt = extra_pt + ROW_TOP_PT + 2 * ROW_STEP_PT + BELOW_PT
    y1n = y0 + (yd1 - y0) / (1 - band_pt / ah_pt)
    clip = Rectangle((-10, y0), 20, yd1 - y0, transform=ax.transData, fill=False, visible=False); ax.add_patch(clip)
    for a_ in list(ax.lines) + list(ax.collections):
        if a_.get_gid() != 'keep': a_.set_clip_path(clip)
    ax.set_yticks(keep_ticks); ax.set_ylim(y0, y1n)
    for x, e, col, txt, fs in MARKS[id(ax)]:
        yf = 1 - (extra_pt + ROW_TOP_PT + ROW[e] * ROW_STEP_PT) / ah_pt
        ax.text(x, yf, txt, transform=ax.get_xaxis_transform(), ha='center', va='center', color=col, fontsize=fs,
                fontweight='bold', clip_on=False, gid='sigmark')
    LOG.append(dict(panel=name, mode=MODE, y0=y0, live_top=live_top, highest_point=top, spine_tick=spine_tick, data_top=yd1, ylim_top=y1n, band_pt=band_pt,
                    axes_h_pt=round(ah_pt, 2), n_points=len(ys), below_y0=int((ys < y0).sum()),
                    above_live_top=int((ys > live_top).sum()), newly_clipped=int(((ys > yd1) & (ys <= live_top)).sum()),
                    marks=';'.join(f'{t}@{x:.3f}/{e}' for x, e, _, t, _ in MARKS[id(ax)])))
    return yd1, y1n


# E
shapes(axs[0], 4, ['lick_right', 'lick_left']); axs[0].set_ylabel('side specificity\n(Δ vs own pre)')
# F
t = pd.read_csv(fd / 'peak_epoch_stats_side.csv'); s = pd.read_csv(fd / 'peak_sessions_side.csv')
CELLS = [('contra', 'lick_right'), ('contra', 'lick_left'), ('ipsi', 'lick_right'), ('ipsi', 'lick_left')]
ax = axs[1]; S.zero_line(ax)
def tg(c, e):
    r = t[(t.group == c[0]) & (t.name == c[1]) & (t.epoch == e)]
    if r.empty: return None
    r = r.iloc[0]; return r.delta, r.ci_lo, r.ci_hi, (2 if r.p_holm < 0.05 else (1 if bool(r.excludes_0) else 0))
w = grouped(ax, CELLS, lambda c, e: s[(s.group == c[0]) & (s.name == c[1]) & (s.epoch == e)].log2_vs_pre.values, tg, seed=5)
ax.set_xticks(range(4)); ax.set_xticklabels(['lick\ncontra', 'lick\nipsi'] * 2)
ax.set_ylabel('lick component amplitude\n(log$_2$ vs own pre)'); ax.set_xlim(-.5, 3.5)
y0f, y1f = ax.get_ylim(); LIVE_TOP[id(ax)] = y1f + (y1f - y0f) * 0.45      # live: S.headroom(ax, 0.45)
for i, c in enumerate(CELLS):
    for j, e in enumerate(EPS):
        r = tg(c, e)
        if r and r[3]:
            MARKS[id(ax)].append((i + (j - 1.5) * w, e, C[e], '*' * int(r[3]), 8 if r[3] == 2 else 9))
epoch_legend(ax, loc='lower center', ncol=4); lg = ax.get_legend(); lg.set_bbox_to_anchor((0.42, 1.0)); lg.set_frame_on(False)
# G, H
G4 = ['lick_right', 'lick_left', 'slow_jaw', 'whisk_run']
shapes(axs[2], 2, G4); axs[2].set_ylabel('spatial angle\n(Δ deg vs own pre)')
shapes(axs[3], 3, G4); axs[3].set_ylabel('spectral angle\n(Δ deg vs own pre)')
finish(axs[0], 'E')
finish(axs[1], 'F', extra_pt=SPOUT_PT)
for x, lab in [(0.5, 'contra spout'), (2.5, 'ipsi spout')]:     # live text, now on its own line at the band top
    axs[1].text(x, 1 - 1.0 / (axs[1].get_position().height * H * 72), lab, transform=axs[1].get_xaxis_transform(),
                ha='center', va='top', fontsize=6.5)
axs[1].axvline(1.5, color='0.85', lw=0.7, zorder=0, gid='keep')   # divider: full axes height, as live
finish(axs[2], 'G'); finish(axs[3], 'H')
lets = [letter(a_, s_) for a_, s_ in zip(axs, 'EFGH')]
fig.align_ylabels(axs)
# crops: cut halfway between F's lowest ink (tick labels) and the top of the G letter
fig.canvas.draw(); r = fig.canvas.get_renderer(); dpi = fig.dpi
f_bot = axs[1].get_tightbbox(r).y0 / dpi
g_top = lets[2].get_window_extent(r).y1 / dpi
cut = (f_bot + g_top) / 2
assert g_top < f_bot, (g_top, f_bot)
crops = {'EF': Bbox([[0, cut], [W, H]]), 'GH': Bbox([[0, 0], [W, cut]])}
# freeze the four-axes y-label alignment (as live), then hide the other pair in each crop so each file holds only its
# own panels (a bbox crop alone keeps the hidden ink in the PDF/SVG)
import matplotlib.cbook as cbook  # noqa: E402
import matplotlib.transforms as mtr  # noqa: E402
ext0 = [a_.yaxis.label.get_window_extent(r).x0 for a_ in axs]
lx = [a_.yaxis.label.get_position()[0] for a_ in axs]          # display px after the aligned draw
fig._align_label_groups['y'] = cbook.Grouper()
for a_, x_ in zip(axs, lx):
    a_.yaxis.set_label_coords(x_ / fig.bbox.width, 0.5, transform=mtr.blended_transform_factory(fig.transFigure, a_.transAxes))
fig.canvas.draw()
ext1 = [a_.yaxis.label.get_window_extent(fig.canvas.get_renderer()).x0 for a_ in axs]
assert np.allclose(ext0, ext1, atol=0.01), (ext0, ext1)
SHOW = {'EF': (0, 1), 'GH': (2, 3)}
for sfx, bb in crops.items():
    for k in range(4):
        axs[k].set_visible(k in SHOW[sfx]); lets[k].set_visible(k in SHOW[sfx])
    for x in ('pdf', 'svg', 'png'):
        fig.savefig(out.replace('{part}', sfx) + f'.{x}', dpi=300, bbox_inches=bb)
plt.close(fig)
pd.DataFrame(LOG).to_csv(out.replace('{part}', 'EFGH') + '_band_log.csv', index=False)
print(f'cut at {cut:.3f} in (F ink bottom {f_bot:.3f}, G letter top {g_top:.3f}); EF {W*72:.1f} x {(H-cut)*72:.2f} pt, '
      f'GH {W*72:.1f} x {cut*72:.2f} pt')
