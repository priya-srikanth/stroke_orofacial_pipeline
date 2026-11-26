"""Fig 5A-D (FaceRhythm column), render kit for CC-A (CC-B, 2026-11-25).

Draws exactly what widefield_pipeline scripts/fr_fig5_col_v26b_ptsv2.py (branch ccb/fr-fourcam-1123, fb4f8573) drew
for the live FR_fig5_col_v26b_terms_fourcam_v2_ccB1123 (313.2 x 388.75 pt). Differences from that script: the panel-B
maps and rings are read from fig5B_far_contra_lick_maps.csv (stage_fig5AD_tables.py) instead of the pickle cache plus
the permutation table, and the mesh spacing (point size in B) is computed with numpy instead of scipy's cKDTree (same
value to the last bit on this mesh; printed at run time). Imports only numpy, pandas, matplotlib, PIL and vls_style.py.

Usage: render_fig5AD.py <kit_dir> <out_stem> [--set NAME=VALUE ...]   (refuses to overwrite)
   kit_dir holds master.npz, master_face.png, fr_pre_timecourses_abs_fourcam_ccB1123.npz,
   session_maps_scaled_lick_points.csv, fig5B_far_contra_lick_maps.csv

A  point mesh on the mean face.  B  face movement speed per point, lick-aligned, far contralesional spout, epoch minus
pre (log2 ratio, mean of animals), rings = permutation clusters (dark red up, dark blue down).  C  four frozen
pre-stroke factors: spatial factor | direction | spectral factor | cue-aligned amplitude by spout (pre sessions, mean
+- SEM).  D  change in each lick factor's spatial loading per point, epoch minus pre, in the animal's own pre SD;
rings = permutation clusters p < .05.  Image left = contralesional.

Presentation settings are in the block below; with the defaults the output is byte-identical to the live PDF.
"""
import colorsys
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                                   # noqa: E402
import matplotlib.pyplot as plt                         # noqa: E402
from matplotlib import colormaps                        # noqa: E402
from matplotlib.colors import Normalize                 # noqa: E402
from matplotlib.cm import ScalarMappable                # noqa: E402
from PIL import Image                                   # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
FS = 6.5                                    # text size (figure drawn at 1:1)
FS_LETTER = 8                               # panel letters
FIG_W_IN = 4.35                             # figure width (in); height follows the row heights below
_HR = [0.72, 0.3, 2.75, 0.50, 1.45]         # row height ratios: A+B | gap | C | gap | D
LEFT, RIGHT = 0.13, 0.87                    # figure-fraction margins
X0, X1, Y0, Y1 = 60, 610, 0, 415            # crop of the 680 x 680 face image around the mesh (image px)
EPS = ['acute', 'subacute', 'chronic']
EP_TITLE = '{e} − pre'                 # B and D column titles
B_TITLE = 'face movement speed, far contralesional spout, lick-aligned'
B_CB_LABEL = 'speed vs pre\n(log$_2$ fold)'; B_CB_TICKS = [-1, 0, 1]
B_POINT_FRAC, B_RING_LW = 0.85, 0.2         # B point diameter / median mesh spacing; ring line width (pt)
RING_UP, RING_DOWN = '#67001f', '#053061'   # B ring colors (D uses '#67001F' / '#053061')
EX = [(4, 'lick\ncontra'), (5, 'lick\nipsi'), (9, 'whisking'), (10, 'pre-lick\njaw')]   # C rows: factor index, label
C_ROW_ROT = 0                               # C row-label rotation (deg); 90 = Priya 11-25 request
C_ROW_X, C_ROW_HA = -0.06, 'right'          # C row-label position (axes fraction of the spatial-factor map) / alignment
D_ROWS = ['lick contra', 'lick ipsi']       # D rows (factor names in session_maps_scaled_lick_points.csv)
D_ROW_ROT = 0                               # D row-label rotation (deg); 90 = Priya 11-25 request
D_ROW_X, D_ROW_HA = -0.06, 'right'
ROW_LABEL_WEIGHT = 'bold'
C_TITLES = ['spatial factor', 'direction of motion', 'spectral factor', 'amplitude, cue-aligned']
_CW = [0.636, 0.10, 0.636, 0.22, 0.44, 0.32, 0.64]   # C column widths (in): map | gap | map | gap | spectrum | gap | amplitude
POS = [('close_L', 'near ipsi'), ('close_center', 'near mid'), ('close_R', 'near contra'),
       ('far_L', 'far ipsi'), ('far_center', 'far mid'), ('far_R', 'far contra')]   # C amplitude legend order
PCOL = {'close_L': '#DFC27D', 'close_center': '#BDBDBD', 'close_R': '#80CDC1',     # ColorBrewer BrBG:
        'far_L': '#8C510A', 'far_center': '#525252', 'far_R': '#01665E'}           # ipsi brown, contra teal
LEG = dict(loc='upper left', bbox_to_anchor=(1.04, 1.0), ncol=1, fontsize=FS - 1, handlelength=0.9, handletextpad=0.35,
           labelspacing=0.25, borderaxespad=0, frameon=False)                     # C amplitude legend
SPEC_XTICKS, SPEC_XTL = [1, 10, 60], ['1', '10', '60']
AMP_XTICKS, AMP_XTL = [0, 1000, 2000], ['0', '1', '2']
D_CB_LABEL = 'spatial factor vs pre (SD)'; D_CB_TICKS = [-5, 0, 5]; D_NORM = (-5, 5)
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


def main(kit, out):
    for ext in ('pdf', 'svg', 'png'):
        if os.path.exists(f'{out}.{ext}'): sys.exit(f'refusing to overwrite {out}.{ext}')
    S.apply()
    Z = np.load(os.path.join(kit, 'master.npz')); H = Z['home']; SP = Z['spatial']; SPEC = Z['spectral']; FQ = Z['freqs']
    FACE = np.asarray(Image.open(os.path.join(kit, 'master_face.png')).convert('L'))
    MB = pd.read_csv(os.path.join(kit, 'fig5B_far_contra_lick_maps.csv'))
    MAPS = {e: g.sort_values('point').log2_ratio.to_numpy() for e, g in MB.groupby('epoch')}
    MASK = {e: g.sort_values('point').ring.astype(bool).to_numpy() for e, g in MB.groupby('epoch')}
    TC = np.load(os.path.join(kit, 'fr_pre_timecourses_abs_fourcam_ccB1123.npz')); T = TC['t_ms']
    LD = pd.read_csv(os.path.join(kit, 'session_maps_scaled_lick_points.csv'))
    if 'unit' in LD.columns:
        LD = LD.assign(factor=LD.unit.map({'lick_right': 'lick contra', 'lick_left': 'lick ipsi'}), value_sd=LD.value)

    def face_ax(ax, bg=True):
        if bg: ax.imshow(FACE, cmap='gray', vmin=0, vmax=255, alpha=0.55)
        ax.set_xlim(X0, X1); ax.set_ylim(Y1, Y0); ax.set_aspect('equal'); ax.axis('off')

    def side_labels(ax):
        ax.text(0.27, -0.02, 'contra', transform=ax.transAxes, ha='center', va='top', fontsize=FS - 0.5, color='0.35')
        ax.text(0.73, -0.02, 'ipsi', transform=ax.transAxes, ha='center', va='top', fontsize=FS - 0.5, color='0.35')
        ax.axvline(np.median(H[:, 0]), color='0.6', lw=0.4)

    def dir_colours(k):
        v = SP[:, :, k].T; w = np.hypot(v[:, 0], v[:, 1]); w = w / w.max()
        ang = np.degrees(np.arctan2(np.abs(v[:, 1]), np.abs(v[:, 0])))
        rgb = np.array([colorsys.hsv_to_rgb(2 / 3 * (1 - a / 90), 1, 0.95) for a in ang])
        return np.c_[rgb, w ** 0.7]

    _UNIT = (0.955 - 0.04) * 5.7 / 6.07
    _FH = 0.045 * 5.7 + 0.04 * 5.7 + _UNIT * sum(_HR)
    fig = plt.figure(figsize=(FIG_W_IN, _FH))
    _gs = fig.add_gridspec(5, 1, height_ratios=_HR, hspace=0, left=LEFT, right=RIGHT, top=1 - 0.045 * 5.7 / _FH, bottom=0.04 * 5.7 / _FH)
    gs0 = [_gs[0], _gs[2], _gs[4]]
    # ---------------------------------------------------------------- row 1: A, B
    g1 = gs0[0].subgridspec(1, 4, width_ratios=[1, 1, 1, 1], wspace=0.06)
    ax = fig.add_subplot(g1[0]); face_ax(ax, bg=False); ax.imshow(FACE, cmap='gray', vmin=0, vmax=255)
    ax.scatter(H[:, 0], H[:, 1], s=0.5, color='0.85', lw=0, alpha=0.8)
    ax.set_title('point mesh', fontsize=FS, pad=2); ax.text(-0.12, 1.12, 'A', transform=ax.transAxes, fontsize=FS_LETTER, weight='bold')
    nb = Normalize(-1, 1); cmb = colormaps['RdBu_r']
    H64 = H.astype(np.float64)                                   # median nearest-neighbor spacing (= scipy cKDTree value)
    _d = np.hypot(H64[:, None, 0] - H64[None, :, 0], H64[:, None, 1] - H64[None, :, 1]); np.fill_diagonal(_d, np.inf)
    _NN = float(np.median(_d.min(1)))
    _RLW = B_RING_LW
    for j, e in enumerate(EPS):
        ax = fig.add_subplot(g1[1 + j]); face_ax(ax, bg=False)
        v = MAPS[e]; mk = MASK[e]
        ax.apply_aspect()
        _ptpu = ax.get_position().width * fig.get_size_inches()[0] * 72 / (X1 - X0)
        _D = B_POINT_FRAC * _NN * _ptpu
        if j == 0:
            print(f'B: median NN {_NN!r} px = {_NN * _ptpu:.3f} pt; point {_D:.3f} pt; ring {_RLW} pt')
        ax.scatter(H[:, 0], H[:, 1], c=v, cmap=cmb, norm=nb, s=_D ** 2, lw=0)
        for sel, col in ((mk & (np.asarray(v) > 0), RING_UP), (mk & (np.asarray(v) <= 0), RING_DOWN)):
            if sel.any():
                ax.scatter(H[sel, 0], H[sel, 1], s=(_D - _RLW) ** 2, facecolor='none', edgecolor=col, lw=_RLW)
        side_labels(ax); ax.set_title(EP_TITLE.format(e=e), fontsize=FS, pad=2)
        if j == 0:
            ax.text(-0.08, 1.12, 'B', transform=ax.transAxes, fontsize=FS_LETTER, weight='bold')
            ax.text(1.55, 1.3, B_TITLE, transform=ax.transAxes, ha='center', fontsize=FS)
    p = fig.axes[-1].get_position()
    cax = fig.add_axes([p.x1 + 0.015, p.y0 + 0.1 * p.height, 0.012, 0.8 * p.height])
    cb = fig.colorbar(ScalarMappable(nb, cmb), cax=cax, ticks=B_CB_TICKS); cb.ax.tick_params(labelsize=FS, length=2, width=0.4)
    cb.set_label(B_CB_LABEL, fontsize=FS, labelpad=1); cb.outline.set_linewidth(0.4)
    # ---------------------------------------------------------------- C: one row per example factor
    _cb = gs0[1].get_position(fig); _FW = fig.get_size_inches()[0]; _x0 = LEFT * _FW
    _g2 = fig.add_gridspec(4, len(_CW), width_ratios=_CW, wspace=0, hspace=0.3, left=LEFT, right=(_x0 + sum(_CW)) / _FW,
                           top=_cb.y1, bottom=_cb.y0)
    g2 = {(r, c): _g2[r, 2 * c] for r in range(4) for c in range(4)}
    for r, (k, nm) in enumerate(EX):
        w = np.hypot(SP[0, :, k], SP[1, :, k])
        ax = fig.add_subplot(g2[r, 0]); face_ax(ax, bg=False); ax.imshow(FACE, cmap='gray', vmin=0, vmax=255)
        ax.scatter(H[:, 0], H[:, 1], c=w / w.max(), cmap='magma', vmin=0, vmax=1, s=0.8, lw=0)
        ax.text(C_ROW_X, 0.5, nm, transform=ax.transAxes, ha=C_ROW_HA, va='center', fontsize=FS, weight=ROW_LABEL_WEIGHT,
                linespacing=1.0, rotation=C_ROW_ROT, rotation_mode='anchor' if C_ROW_ROT else 'default')
        if r == 0:
            ax.set_title(C_TITLES[0], fontsize=FS, pad=2); ax.text(-0.62, 1.12, 'C', transform=ax.transAxes, fontsize=FS_LETTER, weight='bold')
        ax = fig.add_subplot(g2[r, 1]); face_ax(ax, bg=False); ax.imshow(FACE, cmap='gray', vmin=0, vmax=255)
        wk = np.hypot(SP[0, :, k], SP[1, :, k]); wk = wk / wk.max(); o = np.argsort(wk)
        ax.scatter(H[o, 0], H[o, 1], c=dir_colours(k)[o], s=0.1 + 1.6 * wk[o], lw=0)
        if r == 0: ax.set_title(C_TITLES[1], fontsize=FS, pad=2)
        ax = fig.add_subplot(g2[r, 2]); sp = SPEC[:, k] / SPEC[:, k].max()
        ax.plot(FQ, sp, color='k', lw=S.TRAJ_LW); ax.set_xscale('log'); ax.set_xlim(1, 60); ax.set_ylim(0, 1.45)
        pk = FQ[np.argmax(sp)]; ax.axvline(pk, ymax=1.0 / 1.45, color='0.7', lw=0.4, ls=':')
        fx = np.log(pk) / np.log(60)
        lx, lha = (0.07, 'left') if fx < 0.35 else (0.99, 'right') if fx > 0.65 else (fx, 'center')
        ax.text(lx, 0.99, f'{pk:.1f} Hz', transform=ax.transAxes, ha=lha, va='top', fontsize=FS - 0.5)
        ax.set_xticks(SPEC_XTICKS); ax.set_xticklabels(SPEC_XTL if r == 3 else []); ax.set_yticks([0, 1])
        ax.tick_params(labelsize=FS - 0.5, length=2, width=0.4)
        if r == 3: ax.set_xlabel('frequency (Hz)', fontsize=FS, labelpad=1)
        if r == 0: ax.set_title(C_TITLES[2], fontsize=FS, pad=2)
        ax = fig.add_subplot(g2[r, 3]); sel = (T >= -500) & (T <= 2000)
        for p_, pn in POS:
            a = TC[p_][:, :, k]; n = np.isfinite(a).sum(0); m = np.nanmean(a, 0); se = np.nanstd(a, 0, ddof=1) / np.sqrt(n)
            ax.fill_between(T[sel], (m - se)[sel], (m + se)[sel], color=PCOL[p_], alpha=S.TRAJ_BAND, lw=0)
            ax.plot(T[sel], m[sel], color=PCOL[p_], lw=S.TRAJ_LW, label=pn)
        ax.axvline(0, color='0.75', lw=0.4); ax.set_xlim(-500, 2000); ax.set_xticks(AMP_XTICKS)
        ax.set_xticklabels(AMP_XTL if r == 3 else []); ax.tick_params(labelsize=FS - 0.5, length=2, width=0.4)
        ax.yaxis.set_major_locator(plt.MaxNLocator(3))
        if r == 3: ax.set_xlabel('time from cue (s)', fontsize=FS, labelpad=1)
        if r == 0: ax.set_title(C_TITLES[3], fontsize=FS, pad=2)
        if r == 0:
            ax.legend(**LEG)
    # ---------------------------------------------------------------- D: lick-factor loading change
    g3 = gs0[2].subgridspec(2, 3, wspace=0.05, hspace=0.3)
    nd = Normalize(*D_NORM); cmd = colormaps['RdBu_r']
    for gi, fac in enumerate(D_ROWS):
        for j, e in enumerate(EPS):
            ax = fig.add_subplot(g3[gi, j]); face_ax(ax, bg=False)
            d = LD[(LD.factor == fac) & (LD.epoch == e)].sort_values('point')
            ax.scatter(H[:, 0], H[:, 1], c=d.value_sd.values, cmap=cmd, norm=nd, s=1.4, lw=0)
            for sgn, col in ((1, '#67001F'), (-1, '#053061')):
                q = d.ring.values == sgn
                ax.scatter(H[q, 0], H[q, 1], s=0.7, facecolor='none', edgecolor=col, lw=0.1)
            side_labels(ax)
            if gi == 0: ax.set_title(EP_TITLE.format(e=e), fontsize=FS, pad=2)
            if j == 0: ax.text(D_ROW_X, 0.5, fac.replace(' ', '\n'), ha=D_ROW_HA, va='center', transform=ax.transAxes,
                               fontsize=FS, weight=ROW_LABEL_WEIGHT, rotation=D_ROW_ROT,
                               rotation_mode='anchor' if D_ROW_ROT else 'default')
            if gi == 0 and j == 0: ax.text(-0.62, 1.12, 'D', transform=ax.transAxes, fontsize=FS_LETTER, weight='bold')
            if gi == 0 and j == 2: pD = ax.get_position()
            if gi == 1 and j == 2: pD1 = ax.get_position()
    cax = fig.add_axes([pD.x1 + 0.015, pD1.y0 + 0.1 * (pD.y1 - pD1.y0), 0.012, 0.8 * (pD.y1 - pD1.y0)])
    cb = fig.colorbar(ScalarMappable(nd, cmd), cax=cax, ticks=D_CB_TICKS, extend='max')
    cb.ax.tick_params(labelsize=FS - 1, length=2, width=0.4)
    cb.set_label(D_CB_LABEL, fontsize=FS - 1, labelpad=1); cb.outline.set_linewidth(0.4)
    S.save(fig, out)
    print('wrote', out)


if __name__ == '__main__':
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
