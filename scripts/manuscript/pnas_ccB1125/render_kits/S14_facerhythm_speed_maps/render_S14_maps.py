"""S14 (face movement speed maps, six-position cohort, cue- and lick-aligned), render kit for CC-A (CC-B, 2026-11-25).

Draws what widefield_pipeline scripts/fr_s13_maps_from_points.py (branch ccb/fr-fourcam-1123, 5d424aae) drew for the
live FR_aligned_maps_fourcam_w65_v2_ccB1123 (468 x 349.2 pt = 6.5 x 4.85 in) from the per-point permutation table
aligned_maps_perm_points_fourcam_ccB1123.csv (align, position, epoch, point, x, y, mean_log2, sig_cluster). Layout as
that script: A cue-aligned 0 to +2 s, B lick-aligned -0.1 to +0.2 s; rows near ipsi ... far contra; columns acute /
subacute / chronic minus pre; one shared colorbar (log2 change, -1..1, RdBu_r). Points and rings as Fig 5B: point
diameter = MARKER_FRAC x the median nearest-neighbor mesh spacing at the rendered scale (numpy instead of scipy's
cKDTree, same value), ring on the point's own outline, dark red up / dark blue down. Vertical line = face midline
(MIDLINE_X = the pipeline's MASTER_MIDLINE_X). Image left = contralesional.
Ring rule: sig_cluster = permutation-cluster point (10,000 within-animal shuffles of session labels, |t| > 2,
family-wise p < 0.05 within each map). No stars. Imports only numpy, pandas, matplotlib and vls_style.py.
Refuses to overwrite.

Usage: render_S14_maps.py <perm_points.csv> <out_stem> [--set NAME=VALUE ...]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vls_style as S                       # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402
from matplotlib import cm, colors           # noqa: E402

# ----------------------------------------------------------------------------------------------- presentation settings
W, H = 6.5, 4.85                            # page (in)
LEFT_IN = 0.30                              # left margin (in); 0.63 = the 7.0 x 5.2 in layout with horizontal row labels
RIGHT_IN, TOP_IN, BOTTOM_IN = 0.84, 0.598, 0.052   # margins fixed in inches
WSPACE, HSPACE = 0.03, 0.06
SPACER = 0.12                               # width ratio of the gap column between A and B
SUPP_FONTS = True                           # 6.5 / 7 bold / 9 bold (supplement convention); False = 7.5 / 8.5 / 10
VERTICAL_ROWS = True                        # row labels rotated 90 deg, centered on the row, wrapped if too tall
ROW_LABEL_DX_IN = 0.04                      # row label this far left of the first map (in)
MARKER_FRAC = 0.85                          # point diameter / median nearest-neighbor spacing (None = fixed 11-23 sizes)
RING_LW = 0.2                               # ring line width (pt); None = 13 % of the point diameter
RING_COLOR = None                           # one neutral ring color, or None = dark red up / dark blue down
MIDLINE_X = 342.0                           # face midline (master LP nose x, image px)
CBAR_LABEL = 'face speed change from pre'
CBAR_TICKS = [-1, 0, 1]
ROWS = [("close_L", "near ipsi"), ("close_center", "near mid"), ("close_R", "near contra"),
        ("far_L", "far ipsi"), ("far_center", "far mid"), ("far_R", "far contra")]
EPS = ["acute", "subacute", "chronic"]
COLS = ["acute − pre", "subacute − pre", "chronic − pre"]
TITLES = (("cue", "cue-aligned (0 to +2 s)"), ("lick", "lick-aligned (−0.1 to +0.2 s)"))
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


def main(points, out):
    for ext in ("pdf", "svg", "png"):
        if os.path.exists(f"{out}.{ext}"): sys.exit(f"refusing to overwrite {out}.{ext}")
    S.apply()
    P = pd.read_csv(points)
    nb, cmb = colors.Normalize(-1, 1), "RdBu_r"
    fig = plt.figure(figsize=(W, H))
    gs = fig.add_gridspec(6, 7, width_ratios=[1, 1, 1, SPACER, 1, 1, 1], left=LEFT_IN / W, right=1 - RIGHT_IN / W,
                          top=1 - TOP_IN / H, bottom=BOTTOM_IN / H, wspace=WSPACE, hspace=HSPACE)
    FS, FT, FL, TW = (6.5, 7.0, 9.0, "bold") if SUPP_FONTS else (7.5, 8.5, 10.0, "normal")
    g0 = P.iloc[:0]
    tiles = []
    for b, (al, title) in enumerate(TITLES):
        for i, (pos, lab) in enumerate(ROWS):
            for c, ep in enumerate(EPS):
                ax = fig.add_subplot(gs[i, c + 4 * b])
                g = P[(P["align"] == al) & (P.position == pos) & (P.epoch == ep)].sort_values("point")
                if g.empty:
                    ax.axis("off")
                    continue
                g0 = g
                tiles.append((ax, g))
                ax.axvline(MIDLINE_X, color="0.6", lw=0.4)
                ax.set_aspect("equal")
                ax.invert_yaxis()
                ax.axis("off")
                if i == 0:
                    ax.set_title(COLS[c], fontsize=FS, pad=3)
                if c == 0 and b == 0 and not VERTICAL_ROWS:
                    ax.text(-0.08, 0.5, lab, transform=ax.transAxes, ha="right", va="center", fontsize=FS)
        x0 = gs[0, 4 * b].get_position(fig).x0
        x1 = gs[0, 4 * b + 2].get_position(fig).x1
        fig.text((x0 + x1) / 2, 1 - 0.182 / H, title, ha="center", va="center", fontsize=FT, fontweight=TW)
        fig.text(x0 - 0.035 / W, 1 - 0.182 / H, "AB"[b], ha="right", va="center", fontsize=FL, fontweight="bold")
    xl = (g0.x.min() - 8, g0.x.max() + 8)
    yl = (g0.y.max() + 8, g0.y.min() - 8)
    for ax in fig.axes:
        ax.set_xlim(*xl)
        ax.set_ylim(*yl)
    if VERTICAL_ROWS:
        fig.canvas.draw()
        ren = fig.canvas.get_renderer()
        for i, (_, lab) in enumerate(ROWS):
            cell = fig.axes[3 * i].get_position()
            t = fig.text(cell.x0 - ROW_LABEL_DX_IN / W, (cell.y0 + cell.y1) / 2, lab, rotation=90, ha="right", va="center",
                         fontsize=FS, multialignment="center")
            if t.get_window_extent(ren).height > 0.95 * cell.height * H * fig.dpi:
                t.set_text(lab.replace(" ", "\n", 1))
    if MARKER_FRAC is None:
        s_pt, s_ring, lw_ring = 1.6, 1.5, 0.14
    else:
        xy = g0[["x", "y"]].to_numpy(float)
        d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1]); np.fill_diagonal(d, np.inf)
        nn = float(np.median(d.min(1)))                                   # = scipy cKDTree(xy).query(xy, k=2)[0][:, 1]
        ax0 = tiles[0][0]
        ax0.apply_aspect()
        pt_per_unit = ax0.get_position().width * W * 72 / (xl[1] - xl[0])
        d_pt = MARKER_FRAC * nn * pt_per_unit
        lw_ring = RING_LW if RING_LW is not None else max(0.08, 0.13 * d_pt)
        s_pt, s_ring = d_pt ** 2, (d_pt - lw_ring) ** 2
        print(f"median NN {nn!r} units = {nn * pt_per_unit:.3f} pt; point {d_pt:.3f} pt, ring lw {lw_ring:.3f} pt")
    for ax, g in tiles:
        x, y, v = g.x.to_numpy(), g.y.to_numpy(), g.mean_log2.to_numpy()
        mk = g.sig_cluster.astype(bool).to_numpy()
        ax.scatter(x, y, c=v, cmap=cmb, norm=nb, s=s_pt, lw=0)
        rings = (((mk, RING_COLOR),) if RING_COLOR else ((mk & (v > 0), "#67001f"), (mk & (v <= 0), "#053061")))
        for sel, col in rings:
            if sel.any():
                ax.scatter(x[sel], y[sel], s=s_ring, facecolor="none", edgecolor=col, lw=lw_ring)
    cax = fig.add_axes([1 - 0.735 / W, 0.5 - 0.78 / H, 0.084 / W, 1.56 / H])
    cb = fig.colorbar(cm.ScalarMappable(nb, cmb), cax=cax, ticks=CBAR_TICKS)
    cb.set_label(CBAR_LABEL.replace("\\n", "\n"), fontsize=FS)
    if SUPP_FONTS:
        cb.ax.tick_params(labelsize=FS)
    S.save(fig, out)
    print("->", out)


if __name__ == "__main__":
    a = apply_overrides(sys.argv[1:])
    main(a[0], a[1])
