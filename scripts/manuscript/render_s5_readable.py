"""Render the readable (r3) versions of the VLS-manuscript close-vs-standard
spout summaries (Supplementary Fig. S5 B-D: PS51 #6, PS55 #8, PS54 #7).

Why a separate renderer (Priya, 2026-11-21: "dots too large in the accuracy,
lick number plots and rasters not readable"): the ``print`` preset of
``render_s5_spout_close_summaries.py`` shrinks the pipeline 4x2 layout, so its
markers, per-session "0" ticks and pooled raster do not survive reduction. This
script redraws the same quantities, from the same pipeline loaders and per-half
helpers, in the manuscript style (``manuscript_code/figures/vls_style.py``):

- Rows 1-3 (accuracy, correct and incorrect licks per trial): session markers
  at the scalar-panel size (s = 6 pt^2, as the Fig 4 session dots), thin grey
  same-day connectors, mean bar; 3 y ticks (accuracy 0 / 0.5 / 1; licks/trial
  0 and a round maximum shared within the row).
- Row 4 (rasters): one block per session in date order (earliest at the top),
  close-position trials above a thin separator and standard trials below it;
  every session block has a fixed height, so the raster grows with the number
  of sessions; licks are short 0.5 pt ticks; post-stroke day labels on the left;
  "Close (top) / Standard (bottom)" written once above the rasters.

The quantities are identical to the pipeline summary
(``render_animal_summary_spout_close_vs_std``): first-lick accuracy over all
trials of the cue type, mean correct / incorrect licks per trial, and lick
delays within ``behavior_report.window_around_tones``. Only the layout differs.

Pipeline figures and the earlier manuscript files are never touched: outputs
go to ``--out-dir`` as ``<animal>_summary_r3.{pdf,png,svg}`` and the script
refuses to run if any of them exists.

Usage::

    python -m scripts.manuscript.render_s5_readable --out-dir <dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from stroke_orofacial.animals import get_animal  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.spout_behavior.spout_close_vs_std import (  # noqa: E402
    _half_accuracy_firstCorrectLickAll_per_side,
    _half_mean_licks_per_trial_per_side,
    iter_cohort_b_sessions,
)
from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    SIDE_COLORS,
    compute_trial_lick_delays,
    load_behavior_report_params,
    load_visual_gate_config,
)

# Manuscript animal labels (Fig. S5 panel order: B PS51, C PS55, D PS54).
MS_LABELS: dict[str, str] = {"PS51": "#6", "PS55": "#8", "PS54": "#7"}

# --- Manuscript style (vls_style.py), sized for placement at scale 0.94 ---
FONT = 7.0          # labels and titles (prints at ~6.6 pt)
TICK_FONT = 6.5     # tick labels (~6.1 pt)
AXES_LW = 0.6
WIDTH_IN = 3.15     # unchanged from r2, so B and C still fit side by side
# Rows 1-3 keep a fixed height; the raster row is a fixed height per session
# (with a floor for the 1- and 3-session animals).
SCALAR_ROW_IN = 0.78
SESSION_BLOCK_IN = 0.25
RASTER_MIN_IN = 1.35
TOP_IN, BOTTOM_IN = 0.30, 0.45
GAP_SCALAR_IN, GAP_RASTER_IN = 0.34, 0.42
LEFT_IN, RIGHT_IN, WSPACE_IN = 0.50, 0.06, 0.30

DOT_S = 6.0          # pt^2, the Fig 4 session-dot size
DOT_LW = 0.6
CONNECT = {"color": "0.65", "lw": 0.4, "zorder": 1}
MEAN_LW = 1.1
INCORRECT_COLOR = "#D62728"   # magenta is the R-cue color in rows 1-3
CORRECT_COLOR = "#1E8C1E"   # darker than tab:green so 0.5 pt ticks stay visible
TICK_LW = 0.5                 # raster lick ticks, pt
TICK_LEN = 1.0                # one full trial row (rows are ~0.3 pt tall in #7)

# Round maxima for the licks/trial axes; even values give a middle tick.
_ROUND_MAX = (1, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 40, 50)


def _round_max(v: float) -> float:
    """Smallest entry of ``_ROUND_MAX`` that is >= ``v``."""
    for m in _ROUND_MAX:
        if v <= m:
            return float(m)
    return float(np.ceil(v / 10.0) * 10.0)


def _style_axes(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_linewidth(AXES_LW)
    ax.tick_params(width=AXES_LW, length=2.0, labelsize=TICK_FONT, pad=1.5)


def _scalar_panel(ax, side: str, std_vals, close_vals, ylim, yticks) -> None:
    """Session markers (filled standard, open close), connectors, mean bars."""
    col = SIDE_COLORS[side]
    for a, b in zip(std_vals, close_vals, strict=True):
        if np.isfinite(a) and np.isfinite(b):
            ax.plot([0, 1], [a, b], **CONNECT)
    for x, vals, fc in ((0, std_vals, col), (1, close_vals, "white")):
        v = np.asarray(vals, dtype=float)
        v = v[np.isfinite(v)]
        ax.scatter(np.full(v.size, x), v, s=DOT_S, marker="o", facecolor=fc,
                   edgecolor=col, linewidth=DOT_LW, zorder=2, clip_on=False)
        if v.size:
            ax.hlines(v.mean(), x - 0.28, x + 0.28, color=col, lw=MEAN_LW,
                      zorder=3)
    ax.set_xlim(-0.5, 1.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Standard", "Close"])
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    _style_axes(ax)


def _raster_panel(ax, side: str, sessions, window, raster_xlim, label_days,
                  animal_info) -> None:
    """One block per session (earliest at top): close trials, separator,
    standard trials. y grows downward (axis inverted)."""
    y0 = 0.0
    xmin, xmax = raster_xlim
    for k, pair in enumerate(sessions):
        n_close = len(pair.b.tones_idx[f"Tone_{side}"])
        n_std = len(pair.bare.tones_idx[f"Tone_{side}"])
        n = max(n_close + n_std, 1)
        row_h = 1.0 / n     # every session block is 1 unit tall
        segs = {True: [], False: []}
        for half_i, (sess, n_half) in enumerate(((pair.b, n_close), (pair.bare, n_std))):
            base = 0 if half_i == 0 else n_close
            delays = compute_trial_lick_delays(sess, window)[f"Tone_{side}"]
            for idx_tone, by_side in delays.items():
                yc = y0 + (base + idx_tone + 0.5) * row_h
                for lick_side in ("L", "R"):
                    t = by_side[f"Lick_{lick_side}"] / sess.sample_rate
                    # keep ticks inside the plotted window (collections
                    # added this way are not clipped to the axes)
                    t = t[(t >= xmin) & (t <= xmax)]
                    if t.size == 0:
                        continue
                    lo, hi = yc - TICK_LEN * row_h / 2, yc + TICK_LEN * row_h / 2
                    segs[lick_side == side] += [((x, lo), (x, hi)) for x in t]
        for correct, color in ((True, CORRECT_COLOR), (False, INCORRECT_COLOR)):
            if segs[correct]:
                ax.add_collection(LineCollection(
                    segs[correct], colors=color, linewidths=TICK_LW, capstyle="butt",
                    zorder=3 if not correct else 2))
        # close / standard separator inside the block (thin, light)
        if n_close and n_std:
            ax.hlines(y0 + n_close * row_h, xmin, xmax, color="0.55", lw=0.35,
                      ls=(0, (2, 1.5)), zorder=4)
        # block boundary (darker) below each session except the last
        if k < len(sessions) - 1:
            ax.hlines(y0 + 1.0, xmin, xmax, color="0.15", lw=0.5, zorder=4)
        if label_days:
            d = animal_info.day_relative_to_stroke(pair.date)
            ax.text(xmin - 0.12 * (xmax - xmin), y0 + 0.5, f"{d}",
                    ha="right", va="center", fontsize=TICK_FONT,
                    clip_on=False)
        y0 += 1.0
    ax.axvline(0, color="0.35", lw=0.5, zorder=1)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(len(sessions), 0)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xticks(range(int(np.ceil(xmin)), int(np.floor(xmax)) + 1))
    ax.set_xlabel("Time from cue (s)", fontsize=FONT, labelpad=1.5)
    _style_axes(ax)
    ax.spines["left"].set_visible(False)


def render(animal: str, out_dir: Path, resolver: PathResolver) -> list[Path]:
    """Render one animal's r3 summary; return the written paths."""
    vg = load_visual_gate_config()
    window = load_behavior_report_params()["window_around_tones"]
    info = get_animal(animal)
    sessions = sorted(iter_cohort_b_sessions(resolver, animals=[animal]),
                      key=lambda p: p.date)
    if not sessions:
        raise ValueError(f"no post-stroke close/standard sessions for {animal}")

    acc = {h: {s: [] for s in "LR"} for h in ("std", "close")}
    cor = {h: {s: [] for s in "LR"} for h in ("std", "close")}
    inc = {h: {s: [] for s in "LR"} for h in ("std", "close")}
    for p in sessions:
        for h, sess in (("std", p.bare), ("close", p.b)):
            a = _half_accuracy_firstCorrectLickAll_per_side(sess, window)
            n = _half_mean_licks_per_trial_per_side(sess, window)
            for s in "LR":
                acc[h][s].append(a[s])
                cor[h][s].append(n[s]["correct"])
                inc[h][s].append(n[s]["incorrect"])

    def _rowmax(d):
        v = np.concatenate([np.asarray(d[h][s], float) for h in d for s in "LR"])
        v = v[np.isfinite(v)]
        return _round_max(float(v.max()) if v.size else 1.0)

    raster_in = max(RASTER_MIN_IN, SESSION_BLOCK_IN * len(sessions))
    height = (TOP_IN + 3 * SCALAR_ROW_IN + 2 * GAP_SCALAR_IN + GAP_RASTER_IN
              + raster_in + BOTTOM_IN)
    fig = plt.figure(figsize=(WIDTH_IN, height))
    plt.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    ax_w = (WIDTH_IN - LEFT_IN - RIGHT_IN - WSPACE_IN) / 2

    def _axes(row_top_in, h_in, col):
        x = LEFT_IN + col * (ax_w + WSPACE_IN)
        return fig.add_axes([x / WIDTH_IN, 1 - (row_top_in + h_in) / height,
                             ax_w / WIDTH_IN, h_in / height])

    rows = [
        ("Accuracy", acc, (0, 1.04), [0, 0.5, 1]),
        ("Correct licks\nper trial", cor, None, None),
        ("Incorrect licks\nper trial", inc, None, None),
    ]
    top = TOP_IN
    for r, (ylab, d, ylim, yt) in enumerate(rows):
        if ylim is None:
            m = _rowmax(d)
            ylim = (0, m * 1.04)
            yt = [0, m / 2, m] if m % 2 == 0 and m >= 2 else [0, m]
            yt = [int(t) if float(t).is_integer() else t for t in yt]
        for c, s in enumerate("LR"):
            ax = _axes(top, SCALAR_ROW_IN, c)
            _scalar_panel(ax, s, d["std"][s], d["close"][s], ylim, yt)
            if r == 0:
                ax.set_title(f"Tone {s}", fontsize=FONT, pad=3)
            if c == 0:
                ax.set_ylabel(ylab, fontsize=FONT, labelpad=1.5)
            else:
                ax.set_yticklabels([])
        top += SCALAR_ROW_IN + GAP_SCALAR_IN
    top += GAP_RASTER_IN - GAP_SCALAR_IN
    rax = []
    for c, s in enumerate("LR"):
        ax = _axes(top, raster_in, c)
        _raster_panel(ax, s, sessions, window, vg["raster_xlim"],
                      label_days=(c == 0), animal_info=info)
        rax.append(ax)
    # "Post-stroke day" axis title, left of the day labels
    rax[0].text(-0.36, 0.5, "Post-stroke day", rotation=90, ha="center",
                va="center", fontsize=FONT, transform=rax[0].transAxes)
    # one-line orientation key above the rasters, with the color key
    ytxt = 1 - (top - 0.07) / height
    fig.text(0.5, ytxt, "Each session: close (top) / standard (bottom)",
             ha="center", va="bottom", fontsize=FONT)
    handles = [Line2D([], [], color=CORRECT_COLOR, lw=1.2, label="correct lick"),
               Line2D([], [], color=INCORRECT_COLOR, lw=1.2, label="incorrect lick")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               fontsize=TICK_FONT, bbox_to_anchor=(0.5, 0.0), handlelength=1.0,
               columnspacing=1.2, borderaxespad=0.1)
    days = [info.day_relative_to_stroke(p.date) for p in sessions]
    span = f"day {days[0]}" if len(days) == 1 else f"days {days[0]}–{days[-1]}"
    n = len(sessions)
    fig.text(0.5, 1 - 0.06 / height,
             f"{MS_LABELS.get(animal, animal)}: {n} session{'s' if n > 1 else ''}, {span}",
             ha="center", va="top", fontsize=FONT)

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for ext in ("pdf", "svg", "png"):
        p = out_dir / f"{animal}_summary_r3.{ext}"
        fig.savefig(p, dpi=600 if ext == "png" else None)
        written.append(p)
    plt.close(fig)
    print(f"{animal}: {n} sessions, figure {WIDTH_IN:.2f} x {height:.2f} in")
    return written


def main(argv: list[str] | None = None) -> list[Path]:
    """Render the three summaries; refuse to overwrite existing r3 files."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--animals", nargs="+", default=list(MS_LABELS))
    args = ap.parse_args(argv)
    existing = [p for a in args.animals
                for p in args.out_dir.glob(f"{a}_summary_r3.*")] if args.out_dir.exists() else []
    if existing:
        raise SystemExit("refusing to overwrite:\n  " + "\n  ".join(map(str, existing)))
    resolver = PathResolver()
    out: list[Path] = []
    for a in args.animals:
        out += render(a, args.out_dir, resolver)
    return out


if __name__ == "__main__":
    main()
