"""PNAS Fig 4B (v29/v30 S8G, aim vs contralesional accuracy) as a standalone panel (CC-B 2026-11-25; PROMPT item 3B).

The live panel exists only inside S8_aim_recovery_v30c_L.pdf, drawn there by manuscript_code/figures/recovery_mechanics/
s8_compact_v30.py build() -> s8_compact_v28.aim_axes(fax, ses, st, F_COMPACT) with x ticks every 0.5, y ticks every 2,
two-line x label, two-column legend (fontsize 6.5, handletextpad 0.15, labelspacing 0.12, columnspacing 0.4,
handlelength 0.9). This script calls the same aim_axes (unedited) with the same inputs, rc (RC_RM) and fonts; only the
canvas changes. No marks in this panel, so the star rules do not apply and the axes are drawn as live.
Two variants:
  <stem>_legbelow   panel block 110 x 120 pt (axes + labels), legend below in two columns (as live)
  <stem>_legright   panel block 110 x 120 pt, legend at the right in one column
Usage: python s8g_aim_vs_accuracy_standalone.py <c1_aim_acc_sessions.csv> <c1_aim_acc_stats.csv> <out_stem>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402

MC = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/manuscript_code/figures")
sys.path[:0] = [str(MC / "recovery_mechanics"), str(MC)]
import c1_panels  # noqa: E402,F401  (as s8_compact_v30.build: imported before the rc reset)
import s8_compact_v28 as V  # noqa: E402

PW, PH = 110 / 72, 120 / 72          # panel block (in)
L_M, B_M, T_M, R_M = 0.44, 0.40, 0.06, 0.06   # left (two-line y label + ticks), bottom (two-line x label), top, right
LEG_KW = dict(fontsize=V.F_COMPACT['legend'], handletextpad=0.15, labelspacing=0.12, columnspacing=0.4,
              handlelength=0.9, borderaxespad=0, frameon=False)


def panel(fig, W, H, x0, y0):
    ax = fig.add_axes([(x0 + L_M) / W, (y0 + B_M) / H, (PW - L_M - R_M) / W, (PH - B_M - T_M) / H])
    h = V.aim_axes(ax, SES, ST, V.F_COMPACT)
    ax.xaxis.set_major_locator(mt.MultipleLocator(0.5))
    ax.yaxis.set_major_locator(mt.MultipleLocator(2))
    ax.set_xlabel(ax.get_xlabel().replace(' (', '\n('), fontsize=V.F_COMPACT['label'], labelpad=1)
    return ax, h


def ink_inside(fig, stem):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    bb = fig.get_tightbbox(r)
    W, H = fig.get_size_inches()
    ok = bb.x0 >= -1e-3 and bb.y0 >= -1e-3 and bb.x1 <= W + 1e-3 and bb.y1 <= H + 1e-3
    print(f"{Path(stem).name}: page {W * 72:.1f} x {H * 72:.1f} pt; ink bbox (in) {bb.x0:.3f},{bb.y0:.3f} - "
          f"{bb.x1:.3f},{bb.y1:.3f}; inside page: {ok}")
    assert ok


def save(fig, stem):
    for x in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{x}', dpi=600 if x == 'png' else None, bbox_inches=None)
    plt.close(fig)


if __name__ == "__main__":
    SES, ST, stem = sys.argv[1], sys.argv[2], sys.argv[3]
    for v in ('_legbelow', '_legright'):
        for x in ('pdf', 'svg', 'png'):
            if Path(f'{stem}{v}.{x}').exists():
                sys.exit(f'refusing to overwrite {stem}{v}.{x}')
    plt.rcdefaults(); plt.rcParams.update(V.RC_RM); plt.rcParams.update({'legend.frameon': False})
    # legend below (two columns, as live)
    LEG_H = 0.74
    W, H = PW, PH + LEG_H
    fig = plt.figure(figsize=(W, H))
    ax, h = panel(fig, W, H, 0, LEG_H)
    fig.legend(handles=h, ncol=2, loc='upper left', bbox_to_anchor=(0.04 / W, (LEG_H - 0.02) / H), **LEG_KW)
    ink_inside(fig, stem + '_legbelow'); save(fig, stem + '_legbelow')
    # legend at the right (one column)
    plt.rcdefaults(); plt.rcParams.update(V.RC_RM); plt.rcParams.update({'legend.frameon': False})
    LEG_W = 0.80
    W, H = PW + LEG_W, PH
    fig = plt.figure(figsize=(W, H))
    ax, h = panel(fig, W, H, 0, 0)
    fig.legend(handles=h, ncol=1, loc='center left', bbox_to_anchor=((PW + 0.02) / W, (B_M + (PH - B_M - T_M) / 2) / H), **LEG_KW)
    ink_inside(fig, stem + '_legright'); save(fig, stem + '_legright')
