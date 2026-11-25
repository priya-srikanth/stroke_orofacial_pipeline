"""PNAS Fig 4C (v29 S8F day course; CC-B 2026-11-25, PROMPT_CC_B_pnas_panels_2026-11-25 item 3C).

S8E_daycourse_thirdsboot_v2_all8_yshared_all_ccB1123 re-arranged as 4 columns x 2 rows (#1-#4 mild on top, #5-#8
moderate / severe below). Same input (ccB_caption_review_2026-11-23/thirds/data_twotone_v2/thirds_sessions_twotone.csv),
same drawing (thirds_recovery_core.draw_animal), same fonts (Arial 6.5 pt, 7 pt titles), same panel size (1.19 x
0.85 in), same margins and gaps, one y scale shared by all eight panels (as the live 'all' variant). The only change is
the grid: 4 x 2 instead of 2 x 4 (page 6.11 x 2.33 in = 439.9 x 167.8 pt). x label on the bottom row. No marks in this
panel, so the star rules do not apply and the axes are drawn as live.

Usage: python s8e_daycourse_4x2.py <thirds_sessions_twotone.csv> <out_stem>            (new layout)
       python s8e_daycourse_4x2.py <thirds_sessions_twotone.csv> <out_stem> --repro    (live 2 x 4, check)
Refuses to overwrite.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "recovery_mechanics"))
import c1_thirds_boot as CB  # noqa: E402
import thirds_recovery_core as TC  # noqa: E402


def render_4x2(S: pd.DataFrame, stem: str, yshare: str = "all"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mt
    plt.rcdefaults()
    plt.rcParams.update({'font.family': 'Arial', 'font.size': 6.5, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
                         'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none', 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.labelpad': 1.5, 'xtick.labelsize': 6.5,
                         'ytick.labelsize': 6.5})
    eL, eR, eB, eT, eWS, eHS, ah = 0.47, 0.04, 0.2, 0.13, 0.28, 0.3, 0.85     # as live
    aw = (3.17 - eL - eR - eWS) / 2                                            # live panel width, 1.19 in
    ncol, nrow = 4, 2
    W, H = eL + ncol * aw + (ncol - 1) * eWS + eR, eB + eT + (nrow - 1) * eHS + nrow * ah
    fig = plt.figure(figsize=(W, H))
    an = sorted(S.animal.unique(), key=lambda a: CB.FIG_LABEL[a])
    axs = []
    for k, a in enumerate(an):
        r, c = divmod(k, ncol)
        ax = fig.add_axes([(eL + c * (aw + eWS)) / W, (H - eT - (r + 1) * ah - r * eHS) / H, aw / W, ah / H])
        d = S[S.animal == a]
        gr = d.grade.iloc[0]
        TC.draw_animal(ax, d, lambda _r, g=gr: CB.COLORS[g], CB.MARKERS[gr], pre_label_fs=6.0)
        ax.set_title(f'{CB.NUM[a]} ({gr})', fontsize=7, pad=2)
        axs.append(ax)
    grp = {a: (S[S.animal == a].grade.iloc[0] if yshare == 'grade' else 'all') for a in an}
    if yshare != 'none':
        for g in set(grp.values()):
            ks = [k for k, a in enumerate(an) if grp[a] == g]
            lo = min(axs[k].get_ylim()[0] for k in ks)
            hi = max(axs[k].get_ylim()[1] for k in ks)
            for k in ks:
                axs[k].set_ylim(lo, hi)
    for ax in axs:
        lo, hi = ax.get_ylim()
        ax.yaxis.set_major_locator(mt.MultipleLocator(20 if hi - lo > 30 else 10))
    for ax in axs[-ncol:]:
        ax.set_xlabel('sessions (thirds)', fontsize=6.5, labelpad=5)
    fig.text(0.085 / W, (eB + (H - eB - eT) / 2) / H, r'$\Delta$ contralesional-cue first-lick angle (deg)',
             rotation=90, ha='center', va='center', fontsize=6.5)
    for x in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{x}', dpi=600 if x == 'png' else None)
    plt.close(fig)
    return W, H, axs[0].get_ylim() if axs else None


if __name__ == "__main__":
    csv, stem = sys.argv[1], sys.argv[2]
    for x in ('pdf', 'svg', 'png'):
        if Path(f'{stem}.{x}').exists():
            sys.exit(f'refusing to overwrite {stem}.{x}')
    if "--repro" in sys.argv:
        CB.render(pd.read_csv(csv), stem, 'all')
        print("repro written", stem)
    else:
        W, H, yl = render_4x2(pd.read_csv(csv), stem)
        print(f"wrote {stem}: {W:.3f} x {H:.3f} in = {W * 72:.1f} x {H * 72:.1f} pt; shared ylim {yl}")
