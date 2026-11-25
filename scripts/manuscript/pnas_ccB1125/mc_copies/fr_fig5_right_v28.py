"""v28 copy of fr_fig5_right.py (2026-11-23, CC-A; Priya v27 review item 7). Same data, statistics and canvas
(2.45 x 5.98 in = 176.4 x 430.56 pt). Changes: the spatial-angle row keeps its x tick labels; the spectral-angle row is
its own panel (letters E, F, G spatial, H spectral); G and H carry the "contra spout | ipsi spout" header of F over the
two lick components; G and H axes 0.80 in tall (were 0.95) to make room. fr_fig5_right.py is unchanged.

Figure 5 right-hand column (v41, Priya 11-19): E side specificity, F lick-factor amplitude by spout side, G spatial
and spectral angle to the animal's own pre-stroke factor, stacked with their y axes aligned, in the manuscript style
(epoch colours vls_style.EP, faded session dots, marker = mean +- SEM) instead of the recoloured pipeline readout.
E, G: session values from the pipeline's per-session table (data/fr/session_scalars_per_session.csv, written by the
FaceRhythm session-shape tests, face_rhythm_session_shape_tests.py; v42 onward; the SVG read-back of
fr_session_scalars_v2.svg is used only if the first argument lacks a 'measure' column); markers, mean
+- SEM across sessions; stars from fr_session_scalars_v2.csv (within-animal shuffles of session labels): * Holm p < 0.05,
** Holm p < 0.01 (the rule the readout figure used).
F: as c2_panels.fr_side (peak_epoch_stats_side.csv, peak_sessions_side.csv).
Usage: fr_fig5_right_v28.py <session_scalars_per_session.csv | frss_points.csv> <fr_session_scalars_v2.csv> <dir with peak_*_side.csv> <out_stem>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import vls_style as S
from c2_panels import grouped, star, epoch_legend, EPS, C
S.apply()
NO_HDR = '--no-spout-header' in sys.argv   # v28b (Priya 2026-11-23): drop the G/H spout header, keep x tick labels
sys.argv = [x for x in sys.argv if x != '--no-spout-header']
pts, stf, fd, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4]
P = pd.read_csv(pts); ST = pd.read_csv(stf)
if 'measure' in P.columns:   # v42: the pipeline's session table (session_scalars_per_session.csv) instead of the SVG read-back
    P = P[P.measure.isin(['angle_spatial', 'angle_spectral', 'side_spec'])].rename(columns={'unit': 'factor'})
    P['axes'] = P.measure.map({'angle_spatial': 2, 'angle_spectral': 3, 'side_spec': 4})
INV = {v: k for k, v in S.LABEL.items()}
NAME = {'lick_right': 'lick\ncontra', 'lick_left': 'lick\nipsi', 'slow_jaw': 'slow\njaw', 'whisk_run': 'whisk\nrun'}
MEAS = {2: 'angle_spatial', 3: 'angle_spectral', 4: 'side_spec'}
W, L, R = 2.45, 0.66, 0.05                     # figure width, left and right margins (in): y axes aligned
HS = [1.0, 1.0, 0.80, 0.80]                    # axes heights E, F, G spatial, G spectral (in)
GAP = [0.28, 0.5, 0.62, 0.62]                   # space above each axes (in)
BOT = 0.36
H = BOT + sum(HS) + sum(GAP)
fig = plt.figure(figsize=(W, H))
axs = []; y = H
for h, g in zip(HS, GAP):
    y -= g + h; axs.append(fig.add_axes([L / W, y / H, 1 - (L + R) / W, h / H]))


def shapes(ax, a, facs, w=0.21):
    rng = np.random.RandomState(3)
    for i, f in enumerate(facs):
        for j, e in enumerate(EPS):
            x0 = i + (j - 1.5) * w; q = P[(P['axes'] == a) & (P.factor == f) & (P.epoch == e)]
            v = q.value.values   # faded session dots, as every other scalar panel (Priya v41)
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
            # staggered by epoch (acute lowest), as in E and F (Priya 11-20)
            if lev: ax.text(i + (j - 1.5) * w, top[i] + (0.03 + 0.075 * (j - 1)) * (y1 - y0), '*' * lev, ha='center', va='bottom', color=C[e], fontsize=7 if len(facs) > 2 else 8, fontweight='bold')
    ax.set_ylim(y0, max(y1, max(top.values()) + 0.36 * (y1 - y0)))


def letter(ax, s): ax.text(-L / (W - L - R), 1.0 + 0.16 / (ax.get_position().height * H), s, transform=ax.transAxes, fontsize=8, weight='bold', va='bottom')


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
ax.set_ylabel('lick component amplitude\n(log$_2$ vs own pre)'); ax.set_xlim(-.5, 3.5); S.headroom(ax, 0.45)
y0, y1 = ax.get_ylim()
for x, lab in [(0.5, 'contra spout'), (2.5, 'ipsi spout')]:
    ax.text(x, y1 - (y1 - y0) * 0.015, lab, ha='center', va='top', fontsize=6.5)
ax.axvline(1.5, color='0.85', lw=0.7, zorder=0)
for i, c in enumerate(CELLS):
    for j, e in enumerate(EPS):
        r = tg(c, e)
        if r and r[3]: star(ax, i + (j - 1.5) * w, j, C[e], band=0.72, level=r[3])
epoch_legend(ax, loc='lower center', ncol=4); lg = ax.get_legend(); lg.set_bbox_to_anchor((0.42, 1.0)); lg.set_frame_on(False)
# G
G4 = ['lick_right', 'lick_left', 'slow_jaw', 'whisk_run']
shapes(axs[2], 2, G4); axs[2].set_ylabel('spatial angle\n(Δ deg vs own pre)')
shapes(axs[3], 3, G4); axs[3].set_ylabel('spectral angle\n(Δ deg vs own pre)')
for a_ in ([] if NO_HDR else axs[2:]):   # v28: spout header as in F, over the two lick components (columns 0, 1), above the axes
    for x, lab in [(0, 'contra\nspout'), (1, 'ipsi\nspout')]:
        a_.text(x, 1.02, lab, transform=a_.get_xaxis_transform(), ha='center', va='bottom', fontsize=6.5, linespacing=1.0)
    a_.axvline(0.5, ymin=1.0, ymax=1.0 + 0.24 / (a_.get_position().height * H), color='0.85', lw=0.7, clip_on=False, zorder=0)
for a_, s_ in zip(axs, 'EFGH'): letter(a_, s_)
fig.align_ylabels(axs)
S.save(fig, out)
