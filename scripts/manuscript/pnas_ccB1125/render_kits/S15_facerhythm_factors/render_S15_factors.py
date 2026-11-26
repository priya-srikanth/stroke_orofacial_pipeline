"""S15 (all twelve frozen pre-stroke FaceRhythm factors), render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what manuscript_code/figures/fr_s13_factors.py (v3) drew for the live FR_S13_factors_terms_v3_fourcam_ccB1123
(403.2 x 619.2 pt), run without the treadmill argument: one row per factor, spatial factor on the face with the mesh |
direction of motion | spectral factor with its peak | cue-aligned amplitude by spout (pre-stroke sessions, working-period
grid trials, mean +- SEM across sessions). The spout palette and the spectral line color that v3 read from
fr_fig5_col_v26b.py with ast are written out here (PCOL, SPEC_COL). No stars. Imports only numpy, matplotlib, PIL and
vls_style.py. Refuses to overwrite.

Usage: render_S15_factors.py <kit_dir> <out_stem> [--set NAME=VALUE ...]
   kit_dir holds master.npz, master_face.png, fr_pre_timecourses_abs_fourcam_ccB1123.npz, fr_master_labels.json
"""
import colorsys
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                       # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402
from PIL import Image                       # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
FS = 6.5
FIG_W_IN, FIG_H_IN = 5.6, 8.6
GRID = dict(width_ratios=[1.0, 1.0, 0.85, 1.15], wspace=0.42, hspace=0.32, left=0.15, right=0.98, top=0.975, bottom=0.075)
X0, X1, Y0, Y1 = 60, 610, 0, 415            # face crop (image px)
POS = [('close_L', 'near ipsi'), ('close_center', 'near mid'), ('close_R', 'near contra'),
       ('far_L', 'far ipsi'), ('far_center', 'far mid'), ('far_R', 'far contra')]
PCOL = {'close_L': '#DFC27D', 'close_center': '#BDBDBD', 'close_R': '#80CDC1',
        'far_L': '#8C510A', 'far_center': '#525252', 'far_R': '#01665E'}       # = fr_fig5_col_v26b.py PCOL (BrBG)
SPEC_COL = 'k'                                                                 # = fr_fig5_col_v26b.py spectral line
ROW_LABEL_ROT = 0; ROW_LABEL_X = -0.06; ROW_LABEL_HA = 'right'; ROW_LABEL_WEIGHT = 'bold'
ROW_LABEL = '{k}  {name}'                   # row label text: factor index and lesion-relative name
TITLES = ['spatial factor', 'direction of motion', 'spectral factor', 'amplitude, cue-aligned']
SPEC_XTICKS, SPEC_XTL = [1, 10, 60], ['1', '10', '60']
AMP_XTICKS, AMP_XTL = [0, 1000, 2000], ['0', '1', '2']
LEGEND = dict(fontsize=FS - 0.5, frameon=False, handlelength=0.9, labelspacing=0.1, columnspacing=0.8, loc='upper center',
              bbox_to_anchor=(-0.3, -0.7), borderaxespad=0, ncol=3)             # below the last amplitude panel
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


def main(kit, out):
    for ext in ('pdf', 'svg', 'png'):
        if os.path.exists(f'{out}.{ext}'): sys.exit(f'refusing to overwrite {out}.{ext}')
    S.apply()
    Z = np.load(os.path.join(kit, 'master.npz')); H = Z['home']; SP = Z['spatial']; SPEC = Z['spectral']; FQ = Z['freqs']
    FACE = np.asarray(Image.open(os.path.join(kit, 'master_face.png')).convert('L'))
    TC = np.load(os.path.join(kit, 'fr_pre_timecourses_abs_fourcam_ccB1123.npz')); T = TC['t_ms']
    LAB = {int(k): v.replace('lick_right', 'lick contra').replace('lick_left', 'lick ipsi').replace('_', ' ')
           for k, v in json.load(open(os.path.join(kit, 'fr_master_labels.json'))).items()}

    def face_ax(ax):
        ax.imshow(FACE, cmap='gray', vmin=0, vmax=255); ax.set_xlim(X0, X1); ax.set_ylim(Y1, Y0); ax.set_aspect('equal'); ax.axis('off')

    def dir_colours(k):
        v = SP[:, :, k].T; w = np.hypot(v[:, 0], v[:, 1]); w = w / w.max()
        ang = np.degrees(np.arctan2(np.abs(v[:, 1]), np.abs(v[:, 0])))
        return np.c_[np.array([colorsys.hsv_to_rgb(2 / 3 * (1 - a / 90), 1, 0.95) for a in ang]), w ** 0.7]

    n = SP.shape[2]
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN))
    g = fig.add_gridspec(n, 4, **GRID)
    for k in range(n):
        w = np.hypot(SP[0, :, k], SP[1, :, k])
        ax = fig.add_subplot(g[k, 0]); face_ax(ax); ax.scatter(H[:, 0], H[:, 1], c=w / w.max(), cmap='magma', vmin=0, vmax=1, s=0.8, lw=0)
        ax.text(ROW_LABEL_X, 0.5, ROW_LABEL.format(k=k, name=LAB[k]), transform=ax.transAxes, ha=ROW_LABEL_HA, va='center',
                fontsize=FS, weight=ROW_LABEL_WEIGHT, rotation=ROW_LABEL_ROT, rotation_mode='anchor' if ROW_LABEL_ROT else 'default')
        if k == 0: ax.set_title(TITLES[0], fontsize=FS, pad=2)
        ax = fig.add_subplot(g[k, 1]); face_ax(ax); wk = w / w.max(); o = np.argsort(wk)
        ax.scatter(H[o, 0], H[o, 1], c=dir_colours(k)[o], s=0.1 + 1.4 * wk[o], lw=0)
        if k == 0: ax.set_title(TITLES[1], fontsize=FS, pad=2)
        ax = fig.add_subplot(g[k, 2]); sp = SPEC[:, k] / SPEC[:, k].max()
        ax.plot(FQ, sp, color=SPEC_COL, lw=S.TRAJ_LW); ax.set_xscale('log'); ax.set_xlim(1, 60); ax.set_ylim(0, 1.15)
        pk = FQ[np.argmax(sp)]; ax.axvline(pk, color='0.7', lw=0.4, ls=':'); left = pk > 8
        ax.text(0.03 if left else 0.98, 0.97, f'{pk:.1f} Hz', transform=ax.transAxes, ha='left' if left else 'right', va='top', fontsize=FS - 0.5)
        ax.set_xticks(SPEC_XTICKS); ax.set_xticklabels(SPEC_XTL if k == n - 1 else []); ax.set_yticks([0, 1])
        ax.tick_params(labelsize=FS - 0.5, length=2, width=0.4)
        if k == n - 1: ax.set_xlabel('frequency (Hz)', fontsize=FS, labelpad=1)
        if k == 0: ax.set_title(TITLES[2], fontsize=FS, pad=2)
        ax = fig.add_subplot(g[k, 3]); sel = (T >= -500) & (T <= 2000)
        for p, pn in POS:
            a = TC[p][:, :, k]; nn = np.isfinite(a).sum(0); m = np.nanmean(a, 0); se = np.nanstd(a, 0, ddof=1) / np.sqrt(nn)
            ax.fill_between(T[sel], (m - se)[sel], (m + se)[sel], color=PCOL[p], alpha=S.TRAJ_BAND, lw=0)
            ax.plot(T[sel], m[sel], color=PCOL[p], lw=S.TRAJ_LW, label=pn)
        ax.axvline(0, color='0.75', lw=0.4); ax.set_xlim(-500, 2000); ax.set_xticks(AMP_XTICKS)
        ax.set_xticklabels(AMP_XTL if k == n - 1 else []); ax.tick_params(labelsize=FS - 0.5, length=2, width=0.4)
        ax.yaxis.set_major_locator(plt.MaxNLocator(3))
        if k == 0: ax.set_title(TITLES[3], fontsize=FS, pad=2)
        if k == n - 1:
            ax.set_xlabel('time from cue (s)', fontsize=FS, labelpad=1)
            hh, ll = ax.get_legend_handles_labels()
            blank = plt.Line2D([], [], color='none')
            if len(hh) == 7: hh, ll = hh + [blank, blank], ll + ['', '']
            ax.legend(hh, ll, **LEGEND)
    S.save(fig, out)
    print('wrote', out)


if __name__ == '__main__':
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
