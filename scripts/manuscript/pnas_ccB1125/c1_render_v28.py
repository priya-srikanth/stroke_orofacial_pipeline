"""PNAS re-render of the two-tone c1 panels (CC-B 2026-11-25; PROMPT_CC_B_pnas_panels_2026-11-25 item 1).

Fig 1E-G (F1_accuracy, F1_correct_licks, F1_latency) and Fig 2C-F (F2_first_lick_time, S_xy_all, F2_speed_all,
F2_angle_first), same data, marks and canvas as the live _FINAL_ccB1123 panels (c1_final_render.py), with Priya's three
PNAS style changes, mirroring CC-A's c2_scalar_compact_v28.py:
  1. run with VLS_SPINE_TO_TICKS=1 (vls_style hook): the y-axis line stops at the top tick inside the data area;
  2. grade star rows closer together: first (severe) row 3.5 pt below the axes top, 4.5 pt between rows (live: 7 % and
     8.5 % of the axes height = 4.5 and 5.5 pt), 2 pt below the last row;
  3. the band starts just above the highest drawn point (session dot or mean +- SEM, at most the live upper limit;
     1 % of the data range above it) and the data area always holds the dashed zero line with a 5 % margin; data
     artists are clipped to the data area, nothing but marks is drawn in the band.
Axes height / canvas unchanged (fig 1.55 in tall, same margins), so the panel band has a fixed 14.5 pt.

The master renderer manuscript_code/figures/c1_panels.py is NOT edited: it is exec'd into a new module and its
render() replaced by render_v28() below (a copy of render() with the band changes). --repro runs the unchanged master
render() instead (check against the live panels).

v29 (--v29; PROMPT_CC_B_layout_inputs_2026-11-25 item 1): data-area top / kept ticks by band_rule v29 (the axis line
covers the data: it ends at the first major tick at or above the highest drawn point, labelled); suffix _FINAL_v29_ccB1125.

Usage: python c1_render_v28.py <out_dir> [--repro | --v29] [--dump <dir>: write the pre-plot tables per panel, no render]
"""
import os
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from c1_bridge_v29style import MC  # noqa: E402
sys.path.insert(0, str(HERE))
import band_rule as BR  # noqa: E402
import c1_final_render as FR  # noqa: E402  (STATS, FINAL sheet name, FILES, SINGLE specs)

STEMS = ["F1_accuracy", "F1_correct_licks", "F1_latency", "F2_first_lick_time", "S_xy_all", "F2_speed_all",
         "F2_angle_first"]
ROW_TOP_PT, ROW_STEP_PT = 3.5, 4.5
BAND_PT = ROW_TOP_PT + 2 * ROW_STEP_PT + 2.0
LOG = []
DUMP = None
MODE = "v28"          # --v29: band_rule v29 (spine ends at the first major tick >= the highest drawn point)


def load_master():
    src = (MC / "c1_panels.py").read_text(encoding="utf-8")
    mod = types.ModuleType("c1_panels")
    mod.__file__ = str(MC / "c1_panels.py")
    sys.modules["c1_panels"] = mod
    exec(compile(src, str(MC / "c1_panels.py"), "exec"), mod.__dict__)
    return mod


def _drawn_y(ax):
    """y of every drawn data point: scatter offsets, error-bar segment ends, marker / bridge lines (not the zero line)."""
    from matplotlib.collections import LineCollection, PathCollection
    ys = []
    for c in ax.collections:
        if isinstance(c, LineCollection):
            for s in c.get_segments():
                ys.extend(np.asarray(s, float)[:, 1])
        elif isinstance(c, PathCollection):
            o = np.asarray(c.get_offsets(), float)
            if o.ndim == 2 and o.shape[0]:
                ys.extend(o[:, 1])
    for ln in ax.lines:
        yd = np.asarray(ln.get_ydata(), float)
        if yd.size and not (np.allclose(yd, 0) and ln.get_linestyle() in ("--", "dashed")):
            ys.extend(yd)
    ys = np.asarray(ys, float)
    return ys[np.isfinite(ys)]


def make_render_v28(C):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    S, EPOCHS, PHENOS, SIDE_T = C.S, C.EPOCHS, C.PHENOS, C.SIDE_T

    def render_v28(d, sheet, fam, ep, ylab, stem):
        sides = [x for x in ('L', 'R', 'global') if x in set(d.side)]
        fig, axes = plt.subplots(1, len(sides), figsize=(1.45 * len(sides) + 0.35, 1.55), sharey=True, squeeze=False)
        axes = axes[0]
        lo, hi = d.delta.quantile(0.01), d.delta.quantile(0.99)
        span = hi - lo
        for ax, side in zip(axes, sides):          # data: identical to c1_panels.render
            ds = d[d.side == side]
            S.zero_line(ax)
            for k, ph in enumerate(PHENOS):
                dp = ds[ds.ph == ph]; xs, ms, es = [], [], []
                for i, (e, _) in enumerate(EPOCHS):
                    v = dp[dp.epoch_label == e].delta
                    if v.empty: continue
                    off = (k - 1) * 0.09
                    ax.scatter(i + off + np.random.default_rng(i + 10 * k).uniform(-.03, .03, len(v)), v, s=4,
                               color=S.SEV[ph], alpha=0.18, lw=0, zorder=1)
                    xs.append(i + off); ms.append(v.mean()); es.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0)
                ax.errorbar(xs, ms, yerr=es, color=S.SEV[ph], marker=S.SEV_MK[ph], ms=3.6, mec='k', mew=0.35,
                            lw=0, elinewidth=0.9, capsize=0, zorder=3)
                for j in range(len(xs) - 1):
                    gap = round(xs[j + 1] - xs[j]) > 1
                    if gap:
                        ax.plot(xs[j:j + 2], ms[j:j + 2], color=S.SEV[ph], lw=1.0, ls=(0, (1, 1.6)), alpha=0.4, zorder=0.5)
                    else:
                        ax.plot(xs[j:j + 2], ms[j:j + 2], '-', color=S.SEV[ph], lw=1.0, zorder=2)
            ax.set_xticks(range(4)); ax.set_xticklabels([n for _, n in EPOCHS], rotation=32, ha='right', rotation_mode='anchor')
            ax.set_xlim(-0.5, 3.5)
            if SIDE_T[side]: ax.set_title(SIDE_T[side], fontsize=7.5, pad=2)
        y0, live_y1 = lo - 0.08 * span, hi + 0.42 * span
        axes[0].set_ylim(y0, live_y1)
        live_ticks = list(axes[0].get_yticks())
        axes[0].set_ylabel(ylab)
        fig.subplots_adjust(left=0.30 if len(sides) == 1 else 0.20, right=0.98, bottom=0.28, top=0.86, wspace=0.12)
        # --- v28 band: data top = highest drawn point (<= live upper limit), zero line inside, fixed 14.5 pt band
        ys = np.concatenate([_drawn_y(ax) for ax in axes])
        vis = ys[(ys >= y0) & (ys <= live_y1)]
        top = vis.max()
        yd1, keep_ticks, spine_tick = BR.data_top(top, y0, live_ticks, MODE)
        ah_pt = axes[0].get_position().height * fig.get_size_inches()[1] * 72.0
        band = BAND_PT / ah_pt
        y1n = y0 + (yd1 - y0) / (1.0 - band)
        n_below, n_above_live = int((ys < y0).sum()), int((ys > live_y1).sum())
        n_clip_new = int(((ys > yd1) & (ys <= live_y1)).sum())
        for ax in axes:
            clip = Rectangle((-10, y0), 20, yd1 - y0, transform=ax.transData, fill=False, visible=False)
            ax.add_patch(clip)
            for a in list(ax.lines) + list(ax.collections):
                a.set_clip_path(clip)
        axes[0].set_yticks(keep_ticks)
        axes[0].set_ylim(y0, y1n)
        marks = []
        for ax, side in zip(axes, sides):
            for row, ph in enumerate(['severe', 'moderate', 'mild']):
                for i, (e, _) in enumerate(EPOCHS[1:], start=1):
                    mk = C.mark_for(sheet, fam, ep, ph, side, e)
                    if mk:
                        ax.text(i + (C.DAG_DX if mk != '**' else 0), 1.0 - (ROW_TOP_PT + row * ROW_STEP_PT) / ah_pt, mk,
                                transform=ax.get_xaxis_transform(), color=S.SEV[ph], ha='center', va='center',
                                fontsize=8 * (C.DAG_SCALE if mk != '**' else 1), fontweight='bold', clip_on=False)
                        marks.append((side, ph, e, mk))
        LOG.append(dict(stem=Path(stem).name, mode=MODE, y0=y0, live_y1=live_y1, highest_point=top, spine_tick=spine_tick, data_top=yd1, ylim_top=y1n, band_pt=BAND_PT,
                        axes_h_pt=round(ah_pt, 2), n_points=len(ys), below_y0_live_and_new=n_below,
                        above_live_top=n_above_live, newly_clipped=n_clip_new, marks=marks))
        S.save(fig, stem)

    return render_v28


def main():
    import matplotlib
    matplotlib.use("Agg")
    global MODE, DUMP
    out = Path(sys.argv[1])
    DUMP = Path(sys.argv[sys.argv.index("--dump") + 1]) if "--dump" in sys.argv else None
    repro = "--repro" in sys.argv
    MODE = "v29" if "--v29" in sys.argv else "v28"
    if not repro:
        os.environ["VLS_SPINE_TO_TICKS"] = "1"       # must be set before vls_style.apply() (c1_panels import)
    sfx = "_REPRO_ccB1125" if repro else f"_FINAL_{MODE}_ccB1125"
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob(f"*{sfx}.*")):
        sys.exit(f"refusing to overwrite *{sfx}.* in {out}")
    repo = HERE.parents[2]
    os.environ["PIPELINE_REPO"] = str(repo)
    sys.path[:0] = [str(MC), str(MC / "recovery_mechanics")]
    C = load_master()
    import c1_panels_c2aligned as A
    sheet = pd.read_csv(FR.STATS / f"results/phenotype_pooled/3_tier/{FR.FINAL}.csv", encoding="utf-8",
                        keep_default_na=False, na_values=[""])
    sheet["mark"] = sheet["mark"].fillna("")
    relab = A.epoch_relabeller()
    orig_pss = C.per_session_scalar

    def per_session_final(root, ep):          # = c1_final_render.per_session_final
        if ep in FR.FILES:
            d = pd.read_csv(FR.STATS / "inputs" / FR.FILES[ep] / f"{ep}_per_session.csv")
            if "passes_min_licks" in d:
                d = d[d.passes_min_licks.astype(bool)]
            return d[["animal", "date", "side", "value", "epoch_label"]]
        return orig_pss(root, ep)
    C.per_session_scalar = per_session_final
    rnd = C.render if repro else make_render_v28(C)
    matplotlib.rcParams["axes.labelpad"] = 1.5
    spec = dict(FR.SINGLE)
    for stem in STEMS:
        sp = spec[stem]
        src, ep, fam, ylab, sign = C.PANELS[sp] if isinstance(sp, str) else sp
        ep = A.C2_RENAME.get(ep, ep)
        s = C.per_session_scalar(FR.STATS, ep) if src == "scalar" else C.per_session_phase(FR.STATS, fam, ep)
        d = C.baseline(relab(s), sign)
        if DUMP:                        # layout inputs: the exact pre-plot tables (no render)
            pdir = DUMP / stem; pdir.mkdir(parents=True, exist_ok=True)
            d.to_csv(pdir / f"{stem}_sessions.csv", index=False, float_format="%.17g")
            mk = sheet[sheet.endpoint == ep]
            mk = mk[mk.family == fam] if fam else mk
            mk.to_csv(pdir / f"{stem}_marks.csv", index=False, encoding="utf-8")
            (pdir / f"{stem}_spec.json").write_text(__import__("json").dumps(
                {"endpoint": ep, "family": fam, "ylabel": ylab, "sign": sign}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            continue
        rnd(d, sheet, fam, ep, ylab, str(out / f"{stem}_lp_ps47d5{sfx}"))
        print("wrote", stem, flush=True)
    if LOG:
        pd.DataFrame(LOG).to_csv(out / f"c1_band_log{sfx}.csv", index=False)


if __name__ == "__main__":
    main()
