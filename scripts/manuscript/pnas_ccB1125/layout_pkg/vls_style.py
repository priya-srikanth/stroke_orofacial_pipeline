"""Shared figure style for the VLS stroke manuscript (both cohorts and VFSS).

Typography follows the K08 2026 grant panels (grant_panels.py): Arial, 8 pt labels,
7.5 pt ticks, no top/right spines, editable text in SVG.

Colours (decided 2026-11-17):
  severity (cohort 1, VFSS)  S2: mild #F2C02A, moderate #E0702A, severe #8E0012
  epoch (cohort 2, FR)       Paul Tol, colour-blind safe: pre #BBBBBB, acute #AA3377,
                             subacute #4477AA, chronic #228833
Sign convention: tongue / aim angles are POSITIVE TOWARD THE CONTRALESIONAL SIDE in every
panel. Cohort-1 angles were stored positive = ipsilesional and are multiplied by -1 here.
Significance marks: * = 95 % interval (or test) excludes 0 / p < 0.05 for that panel's
stated test; ** = also survives the panel's multiple-comparison correction.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Trajectory and path panels, both cohorts (Priya 2026-11-19): one set of plotting conventions
TRAJ_LW = 0.9        # mean line (paths too, no extra alpha)
TRAJ_BAND = 0.28     # SEM band alpha (SEM across sessions)
SIG_LW = 2.2         # significance bar width
SIG_ALPHA = 0.4      # significance bar alpha
SIG_STEP = 0.06      # vertical spacing between stacked significance bars (axes fraction)
TRAJ_MIN_SESSIONS = 3   # draw a bin's line and band only where n_sessions >= 3

SEV = {'mild': '#F2C02A', 'moderate': '#E0702A', 'severe': '#8E0012'}
SEV_N = {'mild': 4, 'moderate': 2, 'severe': 2}
SEV_MK = {'mild': 'o', 'moderate': 's', 'severe': 'D'}
EP = {'pre': '#BBBBBB', 'acute': '#AA3377', 'subacute': '#4477AA', 'chronic': '#228833'}
EP_DARK = {'pre': '#777777', 'acute': '#AA3377', 'subacute': '#4477AA', 'chronic': '#228833'}
# cohort-2 animal identity colors (S6, S7): Tol indigo/rose/olive/cyan, unused elsewhere in the paper
C2COL = {'PS92': '#332288', 'PS93': '#CC6677', 'PS94': '#999933', 'PS95': '#33BBEE'}
AN_MK = {'PS92': 'o', 'PS93': 's', 'PS94': '^', 'PS95': 'D'}
ANGLE_SIGN_C1 = -1.0          # cohort-1 stored + = ipsilesional -> + = contralesional

OLD_TO_NEW = {                # hex swaps for recolouring existing SVG panels
    '#f2c12e': SEV['mild'], '#f2c02a': SEV['mild'], '#f0822e': SEV['moderate'], '#f0802c': SEV['moderate'],
    '#b4001e': SEV['severe'], '#b00012': SEV['severe'],
    '#808080': EP['pre'], '#e0218a': EP['acute'], '#d4a017': EP['subacute'], '#1b7f79': EP['chronic'],
}


# CC-A 2026-11-24 (Priya): opt-in. With VLS_SPINE_TO_TICKS=1 in the environment, every figure saved after apply()
# has its left spine stopped at the highest y tick inside the axis limits, so the star band above the data has no
# axis line. Without the variable nothing changes. Implemented as a savefig wrapper so scripts that call
# fig.savefig directly (not save()) are covered too.
def _spine_to_ticks(fig):
    for ax in fig.axes:
        sp = ax.spines.get('left')
        if sp is None or not sp.get_visible() or not ax.get_yticks().size:
            continue
        lo, hi = sorted(ax.get_ylim())
        ticks = [t for t in ax.get_yticks() if lo - 1e-12 <= t <= hi + 1e-12]
        if __import__('os').environ.get('VLS_SPINE_DEBUG'):
            print('[vls spine]', ax.get_ylim(), list(ax.get_yticks()), ticks)
        if ticks:
            sp.set_bounds(ax.get_ylim()[0], max(ticks)) if ax.get_ylim()[0] < ax.get_ylim()[1] else sp.set_bounds(min(ticks), ax.get_ylim()[0])


def _install_spine_hook():
    import os
    import matplotlib.figure as _mf
    if not os.environ.get('VLS_SPINE_TO_TICKS') or getattr(_mf.Figure.savefig, '_vls_spine', False):
        return
    _orig = _mf.Figure.savefig
    def savefig(self, *a, **k):
        _spine_to_ticks(self)
        return _orig(self, *a, **k)
    savefig._vls_spine = True
    _mf.Figure.savefig = savefig


def apply():
    _install_spine_hook()
    plt.rcParams.update({
        'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Liberation Sans', 'DejaVu Sans'],
        'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8,
        'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 6.8,
        'legend.frameon': False, 'legend.handletextpad': 0.4, 'legend.borderaxespad': 0.3,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.7,
        'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
        'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'lines.linewidth': 1.0,
    })


def zero_line(ax):
    ax.axhline(0, color='0.6', lw=0.6, ls='--', zorder=0)


def headroom(ax, frac=0.3):
    y0, y1 = ax.get_ylim()
    ax.set_ylim(y0, y1 + (y1 - y0) * frac)


def save(fig, stem):
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{ext}', dpi=300, bbox_inches=None)
    plt.close(fig)

# Manuscript animal labels (ANIMAL_KEY.md): two-tone 1-8 by severity, six-position 9-12, swallowing F1-F8 (PS90 excluded 2026-11-19: pre-stroke swallowing outlier).
LABEL = {'PS47': '#1', 'PS48': '#2', 'PS49': '#3', 'PS50': '#4', 'PS46': '#5', 'PS51': '#6', 'PS54': '#7', 'PS55': '#8',
         'PS92': '#9', 'PS93': '#10', 'PS94': '#11', 'PS95': '#12',
         'PS89': 'F1', 'PS91': 'F2', 'PS107': 'F3', 'PS105': 'F4', 'PS124': 'F5', 'PS126': 'F6', 'PS127': 'F7', 'PS129': 'F8'}
def lab(a): return LABEL.get(a, a)
