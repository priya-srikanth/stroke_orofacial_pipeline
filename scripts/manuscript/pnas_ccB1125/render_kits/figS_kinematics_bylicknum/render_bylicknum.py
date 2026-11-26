"""Supplementary figure: kinematic change from own pre BY LICK NUMBER in the trial, both cohorts (render kit for CC-A;
CC-B, 2026-11-25). Draws exactly what widefield_pipeline scripts/bylicknum_figure_v5_1123.py (branch
ccb/bylicknum-1123) drew for the live FigS_kinematics_bylicknum_v5_ccB1123 (468 x 518.4 pt), from the two cell tables
next to this script (c1_cells_bylicknum_v3_ccB1123.csv, c2_cells_bylicknum_v2_ccB1123.csv); the wfield_local.sig_marks
helpers (star_top, reserve_headroom) are inlined unchanged. Imports only matplotlib and pandas. Refuses to overwrite.

Star rule: per panel and color, one mark for the late-minus-early contrast (licks 6-15 minus licks 1-5): '*' = rank
test q < 0.05 (BH within the family) AND nested bootstrap CI excludes 0, arrow = sign; dagger = single-animal cell
(moderate acute, #5): q < 0.05 AND within-animal bootstrap CI excludes 0.

Usage: render_bylicknum.py <kit_dir> <out_dir> [--stem NAME] [--set NAME=VALUE ...]

Presentation settings: the module constants after the imports (fonts, palettes, page size, margins, gridspec, legend
anchors, headers). Original v5 docstring follows.

Supplementary figure v5 = v4 re-laid out at EXACTLY 6.5 in wide (the manuscript text block, 468 pt) so it is
included at 100% and the 6.5 pt text prints at 6.5 pt (CC-B 11-23). Same data, panels, headings, key and font sizes as
v4; margins and letter offsets are now fixed in inches, the six-position key is right-aligned to the page edge.

    python scripts/bylicknum_figure_v5_1123.py DIR [OUT]   (writes NEW files only)

v4 docstring follows. Supplementary figure v4 (v3 with every explanation moved to the caption; compact color keys only; 7.0 x 7.2 in)

v3 docstring follows. Supplementary figure v3 (manuscript conventions): kinematic change from own pre BY LICK NUMBER in the trial, both
cohorts (CC-B, 2026-11-23; FigS_kinematics_bylicknum_v3_ccB1123.{pdf,svg,png}).

v3 over v2 (Priya 11-23, for the paper):
  * manuscript supplement conventions: Arial 6.5 pt text, 7 pt headers, 9 pt bold panel letters, 8 pt stars, axes 0.7 pt,
    line 0.9 pt, band alpha 0.28 (vls_style TRAJ_LW / TRAJ_BAND), palettes vls_style SEV / EP, no top spine, stars in
    the top band (sig_marks.star_top + reserve_headroom);
  * ONE "two-tone" header over columns 1-3 and ONE "six-position" header over columns 4-5;
  * single-animal cells (moderate acute, #5 only) get the manuscript dagger rule (rank-test q < 0.05 AND within-animal
    bootstrap CI excluding 0; c1_dagger_single_animal.cell_result), drawn at 0.75x the star size, right of the stars;
  * the two-tone ipsilesional-cue companion is folded in as rows 4-6 (panels G-I); the legend sits beside them.

Rows 1-3 (panels A-F): peak speed (A two-tone, B six-position), peak protrusion / 3D reach (C, D), tongue angle at peak
extension (E, F; + = contralesional). Rows 4-6 (G-I): two-tone, ipsilesional cue (speed, protrusion, angle).
Two-tone columns = post epochs (grades as colors); six-position columns = all positions pooled and far contra (epochs
as colors). x = lick number 1-15; y = bootstrap change from the animal's own pre at the same lick number (line), 95% CI
(band); dashed 0 = pre. Marks = the late-minus-early contrast (licks 6-15 minus licks 1-5), its arrow = direction.

    python scripts/bylicknum_figure_v3_1123.py DIR   (DIR = bylicknum/ with c1_v3/ and c2_v2/; writes NEW files only)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


# ---- wfield_local.sig_marks (verbatim)
STEP = 0.075        # axes fraction per row of marks
PAD = 0.03          # extra free space under the lowest row


class sig_marks:
    @staticmethod
    def star_top(ax, x, text="*", color="k", row=0, fontsize=12, step=STEP):
        """Draw `text` at data x in the top band of the axes (row 0 = top line); tag the axes for `reserve_headroom`."""
        import matplotlib.patheffects as pe
        t = ax.text(x, 0.99 - step * row, text, color=color, ha="center", va="top", fontsize=fontsize, fontweight="bold",
                    transform=ax.get_xaxis_transform(), clip_on=False, zorder=6,
                    path_effects=[pe.withStroke(linewidth=2.5, foreground="w")])
        ax._wf_mark_rows = max(getattr(ax, "_wf_mark_rows", 0), row + 1)
        ax._wf_mark_step = step
        return t

    @staticmethod
    def reserve_headroom(fig):
        """Grow the y range of every axes carrying `star_top` marks so the top band is free of data (call once)."""
        done = set()
        for ax in fig.get_axes():
            if ax.axison:
                ax.spines["top"].set_visible(False)
            if not getattr(ax, "_wf_mark_rows", 0):
                continue
            sib = ax.get_shared_y_axes().get_siblings(ax) or [ax]
            key = frozenset(id(a) for a in sib)
            if key in done:
                continue
            done.add(key)
            n = max(getattr(a, "_wf_mark_rows", 0) for a in sib)
            lo, hi = ax.get_ylim()
            if getattr(ax, "_wf_headroom", None) == (lo, hi):
                continue
            frac = getattr(ax, "_wf_mark_step", STEP) * n + PAD
            ax.set_ylim(lo, hi + (hi - lo) * frac / (1 - frac))
            ax._wf_headroom = ax.get_ylim()


def apply_overrides(argv):
    """--set NAME=VALUE (repeatable): override any module-level setting; values are Python literals."""
    import ast
    out, i = [], 0
    while i < len(argv):
        if argv[i] == '--set':
            k, v = argv[i + 1].split('=', 1)
            try: v = ast.literal_eval(v)
            except (ValueError, SyntaxError): pass
            globals()[k] = v; i += 2
        else:
            out.append(argv[i]); i += 1
    return out


_ARGS = apply_overrides(sys.argv[1:])

D = Path(_ARGS[0])
OUT = Path(_ARGS[1]) if len(_ARGS) > 1 else D
STEM = _ARGS[_ARGS.index("--stem") + 1] if "--stem" in _ARGS else "FigS_kinematics_bylicknum_v5_ccB1123"
#: manuscript palettes and line conventions, copied exactly from manuscript_code/figures/vls_style.py
SEV = {"mild": "#F2C02A", "moderate": "#E0702A", "severe": "#8E0012"}
EP = {"acute": "#AA3377", "subacute": "#4477AA", "chronic": "#228833"}
TRAJ_LW, TRAJ_BAND = 0.9, 0.28
FS, FT, FSTAR, FLET = 6.5, 7.0, 8.0, 9.0          # as the live supplements (s6_onepage_v29)
FDAG = 0.75 * FSTAR
DAGGER = "†"
EPOCHS = ("acute", "subacute", "chronic")
plt.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "font.family": "sans-serif",
                     "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"], "font.size": FS,
                     "axes.labelsize": FS, "axes.titlesize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
                     "legend.fontsize": FS, "legend.frameon": False, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.linewidth": 0.7, "xtick.major.width": 0.7,
                     "ytick.major.width": 0.7, "xtick.major.size": 2.0, "ytick.major.size": 2.0,
                     "xtick.major.pad": 1.5, "ytick.major.pad": 1.5, "lines.linewidth": TRAJ_LW})
C1 = pd.read_csv(D / "c1_cells_bylicknum_v3_ccB1123.csv")
C2 = pd.read_csv(D / "c2_cells_bylicknum_v2_ccB1123.csv")
YL1 = {"speed": "Δ peak speed (px/s)", "xy": "Δ peak protrusion (px)", "angle": "Δ tongue angle (deg)"}
YL2 = {"speed": "Δ peak 3D speed (mm/s)", "reach": "Δ peak 3D reach (mm)", "angle": "Δ 3D angle (deg)"}


def _arrow(est):
    return "↓" if est < 0 else "↑"


def _line(ax, d, col, single=False):
    d = d.assign(x=d.bin.astype(int)).sort_values("x")
    if single:
        ax.plot(d.x, d.wa1_effect, color=col, lw=TRAJ_LW, ls=(0, (2.5, 1.5)), zorder=3)
        return
    ax.fill_between(d.x, d.lo, d.hi, color=col, alpha=TRAJ_BAND, lw=0, zorder=1)
    ax.plot(d.x, d.est, color=col, lw=TRAJ_LW, zorder=3)


def _tidy(ax, ylab, xlab):
    ax.axhline(0, color="0.6", lw=0.6, ls="--", zorder=0)
    ax.axvline(5.5, color="0.88", lw=0.6, zorder=0)
    ax.set_xlim(0.5, 15.5)
    ax.set_xticks([1, 5, 10, 15])
    if not xlab:
        ax.set_xticklabels([])
    else:
        ax.set_xlabel("Lick number in trial")
    if ylab:
        ax.set_ylabel(ylab)


def c1_panel(ax, meas, side, epoch):
    d = C1[(C1.measure == meas) & (C1.side == side) & (C1.epoch == epoch)]
    srow = 0
    for g, col in SEV.items():
        dl = d[(d.grade == g) & (d.kind == "licknum")].rename(columns={"nb_effect": "est", "nb_ci_lo": "lo",
                                                                      "nb_ci_hi": "hi"})
        if dl.empty:
            continue
        single = bool(dl.single_animal.all())
        _line(ax, dl, col, single)
        t = d[(d.grade == g) & (d.bin == "late_minus_early")]
        if not len(t):
            continue
        t = t.iloc[0]
        if bool(t.star):                      # stars from x = 12.6 leftward, one slot per grade
            sig_marks.star_top(ax, 12.6 - 2.7 * srow, "*" + _arrow(t.nb_effect), color=col, fontsize=FSTAR)
            srow += 1
        elif bool(t.dagger):                  # single-animal dagger: 0.75x, at the far right, clear of the stars
            sig_marks.star_top(ax, 15.2, DAGGER + _arrow(t.wa1_effect), color=col, fontsize=FDAG)


def c2_panel(ax, meas, pos):
    d = C2[(C2.measure == meas) & (C2.pos == pos)]
    srow = 0
    for e, col in EP.items():
        dl = d[(d.epoch == e) & (d.kind == "licknum")].rename(columns={"boot_change": "est", "boot_lo": "lo",
                                                                      "boot_hi": "hi"})
        _line(ax, dl, col)
        t = d[(d.epoch == e) & (d.bin == "late_minus_early")]
        if len(t) and bool(t.star.iloc[0]):
            sig_marks.star_top(ax, 12.6 - 2.7 * srow, "*" + _arrow(t.boot_change.iloc[0]), color=col, fontsize=FSTAR)
            srow += 1


def _share(axes):
    lo = min(a.get_ylim()[0] for a in axes)
    hi = max(a.get_ylim()[1] for a in axes)
    for a in axes:
        a.set_ylim(lo, hi)


W, H = 6.5, 7.2                                   # 6.5 in = 468 pt text block (v4: 7.0 in)
LEFT_IN, RIGHT_IN, WSPACE, SPACER = 0.56, 0.04, 0.44, 0.3   # margins in inches
fig = plt.figure(figsize=(W, H))
# two blocks (contralesional cue + six-position on top; two-tone ipsilesional cue below), one spacer column between
# the two-tone and six-position columns so the six-position y labels clear the two-tone chronic panels
WR = [1, 1, 1, SPACER, 1, 1]
GKW = dict(left=LEFT_IN / W, right=1 - RIGHT_IN / W, wspace=WSPACE, hspace=0.4, width_ratios=WR)
gtop = fig.add_gridspec(3, 6, bottom=0.53, top=0.945, **GKW)
gbot = fig.add_gridspec(3, 6, bottom=0.055, top=0.44, **GKW)
COLS = [0, 1, 2, 4, 5]
AX = [[None] * 5 for _ in range(6)]
for r in range(6):
    g, rr = (gtop, r) if r < 3 else (gbot, r - 3)
    for c in range(5):
        if r >= 3 and c >= 3:
            continue
        AX[r][c] = fig.add_subplot(g[rr, COLS[c]])

ROWS = [("speed", "speed"), ("xy", "reach"), ("angle", "angle")]
for r, (m1, m2) in enumerate(ROWS):
    for c, e in enumerate(EPOCHS):
        c1_panel(AX[r][c], m1, "contralesional", e)
        _tidy(AX[r][c], YL1[m1] if c == 0 else None, xlab=(r == 2))
        c1_panel(AX[r + 3][c], m1, "ipsilesional", e)
        _tidy(AX[r + 3][c], YL1[m1] if c == 0 else None, xlab=(r == 2))
    for c, pos in enumerate(("pooled", "far_contra")):
        c2_panel(AX[r][3 + c], m2, pos)
        _tidy(AX[r][3 + c], YL2[m2] if c == 0 else None, xlab=(r == 2))
    _share(AX[r][:3])
    _share(AX[r + 3][:3])
    _share(AX[r][3:5])
sig_marks.reserve_headroom(fig)


def _span_x(axes):
    return (axes[0].get_position().x0 + axes[-1].get_position().x1) / 2


# headers: ONE "two-tone" over columns 1-3, ONE "six-position" over columns 4-5; a cue-side line and column subtitles
y_top = AX[0][0].get_position().y1
# Priya 11-23: the contralesional-cue heading is styled exactly as the ipsilesional-cue heading over G-I
fig.text(_span_x(AX[0][:3]), y_top + 0.03, "two-tone, contralesional cue", ha="center", va="bottom", fontsize=FT,
         fontweight="bold")
fig.text(_span_x(AX[0][3:5]), y_top + 0.03, "six-position", ha="center", va="bottom", fontsize=FT, fontweight="bold")
y_bot = AX[3][0].get_position().y1
fig.text(_span_x(AX[3][:3]), y_bot + 0.03, "two-tone, ipsilesional cue", ha="center", va="bottom", fontsize=FT,
         fontweight="bold")
for c, e in enumerate(EPOCHS):
    fig.text(_span_x([AX[0][c]]), y_top + 0.012, e, ha="center", va="bottom", fontsize=FS)
    fig.text(_span_x([AX[3][c]]), y_bot + 0.012, e, ha="center", va="bottom", fontsize=FS)
for c, lab in enumerate(("all positions", "far contra spout")):
    fig.text(_span_x([AX[0][3 + c]]), y_top + 0.012, lab, ha="center", va="bottom", fontsize=FS)

# panel letters: one per row-block (cohort x measure), bold 9 pt at the block's top-left
LET = {(0, 0): "A", (0, 3): "B", (1, 0): "C", (1, 3): "D", (2, 0): "E", (2, 3): "F", (3, 0): "G", (4, 0): "H",
       (5, 0): "I"}
for (r, c), s in LET.items():
    p = AX[r][c].get_position()
    fig.text(p.x0 - (0.49 if c == 0 else 0.595) / W, p.y1 + 0.012, s, fontsize=FLET, fontweight="bold", ha="left",
             va="bottom")

# legend in the free space beside rows 4-6
lx = AX[0][3].get_position().x0 - 0.03
ly = AX[3][0].get_position().y1
h1 = [plt.Line2D([], [], color=c, lw=1.2, label=g) for g, c in SEV.items()]
h1.append(plt.Line2D([], [], color=SEV["moderate"], lw=TRAJ_LW, ls=(0, (2.5, 1.5)), label="moderate acute, #5"))
h2 = [plt.Line2D([], [], color=c, lw=1.2, label=e) for e, c in EP.items()]
leg1 = fig.legend(handles=h1, loc="upper left", bbox_to_anchor=(lx, ly + 0.01), title="two-tone grade",
                  title_fontsize=FS, handlelength=2.2, borderaxespad=0)
leg1._legend_box.align = "left"
leg2 = fig.legend(handles=h2, loc="upper right", bbox_to_anchor=(1 - 0.02 / W, ly + 0.01), title="six-position epoch",
                  title_fontsize=FS, handlelength=2.2, borderaxespad=0)
leg2._legend_box.align = "left"

for ext in ("pdf", "svg", "png"):
    p = OUT / f"{STEM}.{ext}"
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    fig.savefig(p, dpi=300 if ext != "png" else 600)
    print("wrote", p)
